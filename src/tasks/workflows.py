import asyncio
import base64
import json
import multiprocessing
import os
from pathlib import Path
from typing import Any, List

from src.contracts import MemoryScope, WorkflowDispatchResult, WorkflowTaskResult
from src.core.snapshot_manager import SnapshotManager
from src.orchestration.artifacts import ArtifactStore, build_design_stage
from src.orchestration.evidence_producers import collect_metadata_evidence
from src.orchestration.goal_evidence import (
    RuntimeProducerBoundary,
    capture_evidence_envelope,
    collect_workflow_goal_evidence,
    evaluate_goal_evidence,
    sha256_text,
)
from src.orchestration.gate_evaluators import build_qa_check
from src.orchestration.goal_ledger import GoalLedger
from src.orchestration.handoff import ResumeHandoff
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryStore
from src.orchestration.quality_harnesses import audit_role_execution
from src.orchestration.role_orchestrator import (
    run_pre_implementation_roles,
    run_review_release_roles,
)
from src.orchestration.workflow_usability_runtime import (
    apply_workflow_usability_runtime,
    build_workflow_usability_preflight,
)
from src.tasks.workflow_checks import WorkflowCheckStage, goal_with_check_requirements
from src.tasks.runners import (
    LLMCodeGenerationAdapter,
    LocalTaskRunner,
    WorkflowTaskInput,
    task_id_for_file,
)


POST_REVIEW_EVIDENCE_KEYS = {
    "role execution audited",
}


def _task_id(file_name: str) -> str:
    return task_id_for_file(file_name)


def _project_id(project_dir: str) -> str:
    project_name = os.path.basename(os.path.normpath(project_dir))
    return project_name or "project"


def _requested_worker_limit() -> int:
    try:
        requested_workers = int(os.environ.get("AG_MAX_WORKERS", "50"))
    except ValueError:
        return 50
    return max(1, requested_workers)


def _safe_worker_count(file_count: int, cpu_count: int = None) -> int:
    if file_count <= 0:
        return 0

    requested_workers = _requested_worker_limit()
    cpu_cores = cpu_count if cpu_count is not None else (multiprocessing.cpu_count() or 4)
    hard_limit = max(1, cpu_cores * 10)
    return min(requested_workers, hard_limit, file_count)


def _task_ledger_summary(task_results: List[WorkflowTaskResult], pending_files: List[str]) -> dict:
    completed = [
        result.file_name
        for result in task_results
        if result.status == "success"
    ]
    blocked = [
        result.file_name
        for result in task_results
        if result.status != "success"
    ]
    finished = set(completed + blocked)
    pending = [
        file_name
        for file_name in pending_files
        if file_name not in finished
    ]
    return {
        "pending": pending,
        "in_progress": [],
        "completed": completed,
        "blocked": blocked,
    }


def _next_goal_action(goal: dict) -> str:
    if not goal:
        return ""
    if goal.get("status") == "complete":
        return "ready for release summary"
    if goal.get("status") == "blocked":
        missing = goal.get("metadata", {}).get("missing_evidence", [])
        if missing:
            return f"collect missing evidence: {', '.join(missing)}"
        return "resolve blocked workflow state"
    return "continue workflow dispatch"


def _merge_task_metadata(result: WorkflowTaskResult, metadata: dict) -> WorkflowTaskResult:
    merged_metadata = dict(result.metadata)
    merged_metadata.update(metadata)
    return WorkflowTaskResult(
        task_id=result.task_id,
        file_name=result.file_name,
        role=result.role,
        status=result.status,
        message=result.message,
        metadata=merged_metadata,
    )


def _local_task_runner_from_metadata(metadata: dict):
    if metadata.get("local_task_runner"):
        return metadata.get("local_task_runner")
    if metadata.get("local_generation_adapter"):
        return LocalTaskRunner(adapter=metadata.get("local_generation_adapter"))
    if metadata.get("llm_router"):
        return LocalTaskRunner(adapter=LLMCodeGenerationAdapter(metadata.get("llm_router")))
    return None


def _task_result_evidence(task_results: List[WorkflowTaskResult]) -> List[str]:
    evidence: List[str] = []
    for result in task_results:
        for item in collect_metadata_evidence(result.metadata):
            if item and item not in evidence:
                evidence.append(item)
    return evidence


def _gate_result_evidence(gate_results: List[dict]) -> List[str]:
    evidence_records: List[dict] = []
    for gate in gate_results:
        evidence_records.extend(gate.get("evidence_records", []) or [])
    return collect_metadata_evidence({"evidence_records": evidence_records})


def _goal_scope(goal: dict) -> dict:
    return dict((goal.get("metadata", {}) or {}).get("scope", {}) or {})


def _artifact_envelopes(
    evidence_keys: List[str],
    *,
    producer: str,
    scope: dict,
    locator: str,
    captured_output: Any,
    status: str = "passed",
    producer_boundary: RuntimeProducerBoundary,
) -> List[dict]:
    return [
        capture_evidence_envelope(
            evidence_type="artifact",
            evidence_key=key,
            producer=producer,
            scope=scope,
            status=status,
            locator=locator,
            captured_output=captured_output,
            producer_boundary=producer_boundary,
        )
        for key in _dedupe_strings(evidence_keys)
        if key
    ]


def _task_result_envelopes(
    task_results: List[WorkflowTaskResult],
    *,
    scope: dict,
    workflow_id: str,
    producer_boundary: RuntimeProducerBoundary,
) -> List[dict]:
    envelopes: List[dict] = []
    for result in task_results:
        evidence_keys = collect_metadata_evidence(result.metadata)
        if not evidence_keys:
            continue
        target_path = Path(str(result.metadata.get("target_path") or ""))
        if target_path.is_file():
            captured_output: Any = target_path.read_bytes()
            locator = str(target_path.resolve())
        else:
            captured_output = result.to_dict()
            locator = f"workflow:{workflow_id}:task:{result.task_id}"
        envelopes.extend(
            _artifact_envelopes(
                evidence_keys,
                producer=f"workflow.task_result:{result.metadata.get('runner') or result.role}",
                scope=scope,
                locator=locator,
                captured_output=captured_output,
                status="passed" if result.status == "success" else "failed",
                producer_boundary=producer_boundary,
            )
        )
    return envelopes


def _workflow_result_envelopes(
    *,
    goal: dict,
    workflow_id: str,
    project_dir: str,
    design_doc: str,
    file_list: List[str],
    task_results: List[WorkflowTaskResult],
    design_stage: dict,
    check_results,
    workflow_metadata: dict,
    workflow_success: bool,
    producer_boundary: RuntimeProducerBoundary,
) -> List[dict]:
    scope = _goal_scope(goal)
    envelopes: List[dict] = []
    if design_doc and design_doc.strip():
        envelopes.extend(
            _artifact_envelopes(
                ["design_doc"],
                producer="workflow.design_input",
                scope=scope,
                locator=f"workflow:{workflow_id}:design_doc",
                captured_output=design_doc,
                producer_boundary=producer_boundary,
            )
        )
    if file_list:
        envelopes.extend(
            _artifact_envelopes(
                ["target_files"],
                producer="workflow.target_files",
                scope=scope,
                locator=str(Path(project_dir).resolve()),
                captured_output=list(file_list),
                producer_boundary=producer_boundary,
            )
        )
    dispatch_output = {
        "workflow_id": workflow_id,
        "task_results": [result.to_dict() for result in task_results],
        "check_results": check_results.to_metadata(),
        "success": bool(workflow_success),
    }
    envelopes.append(
        capture_evidence_envelope(
            evidence_type="tool_receipt",
            evidence_key="workflow dispatch completed",
            producer="workflow.dispatch",
            scope=scope,
            status="passed" if workflow_success else "failed",
            tool_name="dispatch_project_workflow",
            tool_call_id=workflow_id,
            result_id=sha256_text(json.dumps(dispatch_output, ensure_ascii=False, sort_keys=True)),
            result_status="success" if workflow_success else "failed",
            captured_output=dispatch_output,
            producer_boundary=producer_boundary,
        )
    )
    envelopes.extend(
        _task_result_envelopes(
            task_results,
            scope=scope,
            workflow_id=workflow_id,
            producer_boundary=producer_boundary,
        )
    )
    envelopes.extend(
        _artifact_envelopes(
            list(design_stage.get("evidence", []) or []),
            producer="workflow.design_stage",
            scope=scope,
            locator=f"workflow:{workflow_id}:design_stage",
            captured_output=design_stage,
            producer_boundary=producer_boundary,
        )
    )
    for index, record in enumerate(check_results.command_results):
        metadata = dict(record.get("metadata", {}) or {})
        keys = list(record.get("evidence", []) or [])
        if metadata.get("evidence_key"):
            keys.append(metadata["evidence_key"])
        for key in _dedupe_strings(keys):
            envelopes.append(
                capture_evidence_envelope(
                    evidence_type="test",
                    evidence_key=key,
                    producer=str(metadata.get("runner") or "workflow.command_check"),
                    scope=scope,
                    status=str(record.get("status") or "failed"),
                    command=str(metadata.get("command") or ""),
                    command_id=f"{workflow_id}:command:{index}",
                    exit_code=int(metadata.get("exit_code", 1)),
                    captured_output={
                        "stdout": metadata.get("stdout", ""),
                        "stderr": metadata.get("stderr", ""),
                    },
                    producer_boundary=producer_boundary,
                )
            )
    for index, record in enumerate(check_results.browser_qa_results):
        metadata = dict(record.get("metadata", {}) or {})
        keys = list(record.get("evidence", []) or [])
        if metadata.get("evidence_key"):
            keys.append(metadata["evidence_key"])
        browser_specs = list(workflow_metadata.get("browser_qa_checks", []) or [])
        if index < len(browser_specs) and isinstance(browser_specs[index], dict):
            configured_key = browser_specs[index].get("evidence_key", "")
            if configured_key:
                keys.append(configured_key)
        for key in _dedupe_strings(keys):
            envelopes.append(
                capture_evidence_envelope(
                    evidence_type="tool_receipt",
                    evidence_key=key,
                    producer=str(metadata.get("runner") or "workflow.browser_qa"),
                    scope=scope,
                    status=str(record.get("status") or "failed"),
                    tool_name=str(metadata.get("adapter") or "browser_qa"),
                    tool_call_id=f"{workflow_id}:browser:{index}",
                    result_id=sha256_text(json.dumps(record, ensure_ascii=False, sort_keys=True)),
                    result_status=str(record.get("status") or "failed"),
                    captured_output=record,
                    producer_boundary=producer_boundary,
                )
            )
    return envelopes


def _review_envelopes(
    gate_results: List[dict],
    role_execution_audit: dict,
    *,
    goal: dict,
    workflow_id: str,
    producer_boundary: RuntimeProducerBoundary,
) -> List[dict]:
    scope = _goal_scope(goal)
    envelopes: List[dict] = []
    for gate in gate_results:
        keys = _gate_result_evidence([gate])
        for key in keys:
            envelopes.append(
                capture_evidence_envelope(
                    evidence_type="review",
                    evidence_key=key,
                    producer=f"workflow.review_gate:{gate.get('role', '')}",
                    scope=scope,
                    status=str(gate.get("status") or "failed"),
                    locator=str(gate.get("role") or "review"),
                    result_id=f"{workflow_id}:gate:{gate.get('role', '')}",
                    captured_output=gate,
                    producer_boundary=producer_boundary,
                )
            )
    envelopes.extend(
        _artifact_envelopes(
            list(role_execution_audit.get("evidence", []) or []),
            producer="workflow.role_execution_audit",
            scope=scope,
            locator=f"workflow:{workflow_id}:role_execution_audit",
            captured_output=role_execution_audit,
            status="passed" if role_execution_audit.get("status") == "passed" else "failed",
            producer_boundary=producer_boundary,
        )
    )
    return envelopes


def _goal_with_added_evidence(goal: dict, evidence_items: List[str]) -> dict:
    if not goal:
        return {}

    updated_goal = dict(goal)
    evidence = list(updated_goal.get("evidence", []))
    for item in evidence_items:
        if item and item not in evidence:
            evidence.append(item)
    updated_goal["evidence"] = evidence
    metadata = dict(updated_goal.get("metadata", {}))
    metadata["post_gate_evidence"] = list(evidence_items)
    updated_goal["metadata"] = metadata
    return updated_goal


def _memory_enabled(metadata: dict) -> bool:
    return bool(
        metadata.get("enable_memory")
        or metadata.get("memory_context")
        or metadata.get("memory_scope")
    )


def _thread_id_from_metadata(metadata: dict) -> str:
    app_context = metadata.get("app_context", {}) or {}
    return metadata.get("thread_id", "") or app_context.get("thread_id", "")


def _goal_with_memory_context(goal: dict, memory_context: dict) -> dict:
    if not goal or not memory_context:
        return goal

    updated_goal = dict(goal)
    metadata = dict(updated_goal.get("metadata", {}))
    metadata["memory_context"] = json.loads(json.dumps(memory_context))
    updated_goal["metadata"] = metadata
    return updated_goal


def _goal_with_design_stage(goal: dict, design_stage: dict) -> dict:
    if not goal or not design_stage:
        return goal

    updated_goal = dict(goal)
    metadata = dict(updated_goal.get("metadata", {}))
    metadata["domain_profile"] = json.loads(json.dumps(design_stage.get("domain_profile", {})))
    metadata["work_design"] = json.loads(json.dumps(design_stage.get("work_design", {})))
    metadata["artifact_manifest"] = json.loads(json.dumps(design_stage.get("manifest", {})))
    metadata["deliverable_exports"] = json.loads(json.dumps(design_stage.get("deliverable_exports", {})))
    updated_goal["metadata"] = metadata
    return updated_goal


def _goal_with_role_orchestration(goal: dict, role_metadata: dict) -> dict:
    if not goal or not role_metadata:
        return goal

    updated_goal = dict(goal)
    metadata = dict(updated_goal.get("metadata", {}))
    metadata["role_orchestration"] = json.loads(json.dumps(role_metadata.get("summary", {})))
    metadata["role_task_results"] = json.loads(json.dumps(role_metadata.get("results", [])))
    updated_goal["metadata"] = metadata
    return updated_goal


def _goal_for_review_gates(goal: dict) -> dict:
    """Remove post-review evidence from pre-release gate blocking checks."""
    if not goal:
        return goal

    updated_goal = dict(goal)
    metadata = dict(updated_goal.get("metadata", {}))
    missing = list(metadata.get("missing_evidence", []) or [])
    deferred = [
        item for item in missing
        if item in POST_REVIEW_EVIDENCE_KEYS
    ]
    if not deferred:
        return goal

    remaining = [
        item for item in missing
        if item not in POST_REVIEW_EVIDENCE_KEYS
    ]
    metadata["missing_evidence"] = remaining
    metadata["deferred_post_review_evidence"] = deferred
    updated_goal["metadata"] = metadata
    if not remaining and updated_goal.get("status") == "blocked":
        blocked_reason = updated_goal.get("blocked_reason", "")
        if blocked_reason.startswith("missing required evidence:"):
            updated_goal["status"] = "complete"
            updated_goal["blocked_reason"] = ""
    return updated_goal


def _role_task_results(role_orchestration: dict) -> List[WorkflowTaskResult]:
    return [
        WorkflowTaskResult.from_dict(result)
        for result in role_orchestration.get("results", []) or []
    ]


def _role_orchestration_metadata(*stages: dict) -> dict:
    stage_metadata = []
    role_results = []
    parallel_wave_count = 0
    wave_count = 0
    success = True
    for stage in stages:
        if not stage:
            continue
        waves = list(stage.get("waves", []))
        results = list(stage.get("results", []))
        parallel_wave_count += sum(1 for wave in waves if wave.get("parallel"))
        wave_count += len(waves)
        success = success and bool(stage.get("success"))
        stage_metadata.append({
            "success": bool(stage.get("success")),
            "wave_count": len(waves),
            "parallel_wave_count": sum(1 for wave in waves if wave.get("parallel")),
            "waves": waves,
        })
        role_results.extend(results)
    return {
        "summary": {
            "execution_model": "dag-asyncio-role-waves",
            "success": success,
            "stage_count": len(stage_metadata),
            "wave_count": wave_count,
            "parallel_wave_count": parallel_wave_count,
        },
        "stages": stage_metadata,
        "results": role_results,
    }


def _role_metadata_with_implementation(
    role_metadata: dict,
    implementation_results: List[WorkflowTaskResult],
    implementation_required: bool,
) -> dict:
    updated = json.loads(json.dumps(role_metadata))
    summary = dict(updated.get("summary", {}))
    summary["implementation_required"] = bool(implementation_required)
    updated["summary"] = summary
    existing = list(updated.get("results", []) or [])
    for result in implementation_results:
        item = result.to_dict()
        metadata = dict(item.get("metadata", {}) or {})
        metadata.setdefault("execution_model", "parallel-role-stage")
        if metadata.get("evidence") and not metadata.get("role_artifacts"):
            metadata["role_artifacts"] = [
                {
                    "role": "implementer",
                    "artifact_type": "implementation-task-output",
                    "title": item.get("file_name", ""),
                    "path": item.get("file_name", ""),
                    "evidence": "implementer role task completed",
                }
            ]
        item["metadata"] = metadata
        existing.append(item)
    updated["results"] = existing
    return updated


def _qa_checks_from_workflow_results(
    check_results,
    task_results: List[WorkflowTaskResult],
) -> List[dict]:
    checks: List[dict] = []
    for index, result in enumerate(check_results.command_results, start=1):
        metadata = result.get("metadata", {}) or {}
        checks.append(
            build_qa_check(
                requirement_id=f"CMD-{index:03d}",
                check_type="command",
                description=str(metadata.get("command", "command check")),
                status="passed" if result.get("status") == "passed" else "blocked",
                evidence=list(result.get("evidence", []) or []),
                notes=str(metadata.get("stderr", "") or metadata.get("stdout", ""))[:500],
            )
        )
    for index, result in enumerate(check_results.browser_qa_results, start=1):
        metadata = result.get("metadata", {}) or {}
        checks.append(
            build_qa_check(
                requirement_id=f"BROWSER-{index:03d}",
                check_type="browser",
                description=str(metadata.get("scenario") or metadata.get("target") or "browser QA"),
                status="passed" if result.get("status") == "passed" else "blocked",
                evidence=list(result.get("evidence", []) or []),
                notes=str(metadata.get("error_type", "") or metadata.get("message", "")),
            )
        )
    if checks:
        return checks

    task_evidence = _task_result_evidence(task_results)
    if task_results:
        status = "passed" if all(result.status == "success" for result in task_results) and task_evidence else "blocked"
        return [
            build_qa_check(
                requirement_id="TASK-EVIDENCE",
                check_type="implementation-evidence",
                description="Implementer task results include completion evidence",
                status=status,
                evidence=task_evidence,
                notes="Generated when no command or browser QA checks are configured.",
            )
        ]
    return [
        build_qa_check(
            requirement_id="QA-SKIP",
            check_type="approved-skip",
            description="No implementation files or external QA checks were requested for this workflow.",
            status="skipped",
            evidence=["qa skip approved"],
            scope="no-implementation-files",
            notes="Scoped no-op workflow skip generated by workflow dispatcher.",
        )
    ]


def _workflow_memory_context(project_dir: str, metadata: dict) -> tuple:
    if not _memory_enabled(metadata):
        return {}, {}

    if metadata.get("memory_context"):
        return (
            json.loads(json.dumps(metadata.get("memory_context"))),
            json.loads(json.dumps(metadata.get("memory_store", {}))),
        )

    scope_data = metadata.get("memory_scope")
    if isinstance(scope_data, dict):
        scope = MemoryScope.from_dict(scope_data)
    else:
        scope = MemoryScopeResolver.from_adapter_metadata(
            project_dir=project_dir,
            metadata=metadata,
            conversation_memory_root=metadata.get("conversation_memory_root", ""),
        )

    store = MemoryStore(MemoryScopeResolver.storage_path(scope), scope)
    context = store.build_context()
    store.append_event(
        "memory_context_loaded",
        {
            "record_count": context.get("record_count", 0),
            "namespace": scope.namespace,
        },
    )
    return context, store.describe_paths()


def _apply_retention_policy(
    project_dir: str,
    thread_id: str,
    metadata: dict,
    memory_store_metadata: dict,
) -> dict:
    policy = metadata.get("retention_policy", {}) or metadata.get("uaf_retention", {}) or {}
    if not policy:
        return {}

    summary = {}
    if policy.get("goal_events") is not None:
        summary["goal_events"] = GoalLedger(project_dir, thread_id=thread_id).trim_events(
            int(policy["goal_events"])
        )
    if policy.get("artifact_events") is not None:
        summary["artifact_events"] = ArtifactStore(project_dir, thread_id=thread_id).trim_events(
            int(policy["artifact_events"])
        )
    if policy.get("memory_events") is not None and memory_store_metadata.get("memory_dir"):
        summary["memory_events"] = MemoryStore(memory_store_metadata["memory_dir"]).trim_events(
            int(policy["memory_events"])
        )
    if policy.get("snapshots") is not None:
        summary["snapshots"] = SnapshotManager(project_dir, thread_id=thread_id).prune(
            int(policy["snapshots"])
        )
    return summary


async def _report_task_result_to_webhook(
    webhook_url: str,
    api_key: str,
    project_id: str,
    result: WorkflowTaskResult,
) -> dict:
    if not webhook_url:
        return {
            "status": "skipped",
            "reason": "AG_WEBHOOK_URL not configured",
        }

    result_payload = {
        result.file_name: {
            "status": result.status.upper(),
            "role": result.role,
            "message": result.message,
        }
    }
    b64_data = base64.b64encode(json.dumps(result_payload).encode("utf-8")).decode("utf-8")
    payload = {
        "project_id": project_id,
        "task_id": result.task_id,
        "base64_data": b64_data,
    }

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers={"X-API-Key": api_key},
            )
        response.raise_for_status()
        return {
            "status": "success",
            "http_status": response.status_code,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }


async def code_generation_worker(
    queue: asyncio.Queue,
    project_id: str,
    project_dir: str,
    results: List[WorkflowTaskResult],
    runner: LocalTaskRunner = None,
):
    webhook_url = os.environ.get("AG_WEBHOOK_URL", "").strip()
    api_key = os.environ.get("AG_API_KEY", "antigravity-secret-key-v2")
    task_runner = runner or LocalTaskRunner()

    while True:
        try:
            task_data = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        file_name = task_data["file_name"]
        role = task_data.get("role", "implementer")
        task_id = _task_id(file_name)

        print(f"[Worker] '{file_name}' task started as {role}.")

        try:
            task_input = WorkflowTaskInput(
                project_dir=project_dir,
                file_name=file_name,
                design_doc=task_data["design_doc"],
                platform_mode=task_data["platform_mode"],
                role=role,
                metadata={
                    "role_graph": task_data.get("role_graph", {}),
                },
            )
            runner_result = await task_runner.run(task_input)
            webhook_report = await _report_task_result_to_webhook(
                webhook_url,
                api_key,
                project_id,
                runner_result,
            )
            results.append(
                _merge_task_metadata(
                    runner_result,
                    {"webhook_report": webhook_report},
                )
            )
            print(f"[Worker] '{file_name}' task completed.")
        except Exception as exc:
            results.append(
                WorkflowTaskResult(
                    task_id=task_id,
                    file_name=file_name,
                    role=role,
                    status="failed",
                    message=str(exc),
                    metadata={"error_type": type(exc).__name__},
                )
            )
            print(f"[Worker] '{file_name}' failed: {exc}")
        finally:
            queue.task_done()


async def async_project_workflow(
    project_dir: str,
    file_list: list,
    design_doc: str,
    platform_mode: str,
    metadata: dict = None,
) -> WorkflowDispatchResult:
    queue = asyncio.Queue()
    project_id = _project_id(project_dir)
    workflow_id = f"workflow_{project_id}"
    producer_boundary = RuntimeProducerBoundary(f"workflow:{workflow_id}")
    metadata = metadata or {}
    workflow_usability_preflight = build_workflow_usability_preflight(project_dir, metadata)
    if workflow_usability_preflight:
        provider = workflow_usability_preflight.get("token_optimizer_provider", {})
        print(
            "[KH] workflow usability enabled: "
            f"token_optimizer_provider={provider.get('provider', '')} "
            f"status={provider.get('status', '')}"
        )
    check_stage = WorkflowCheckStage()
    goal_metadata = goal_with_check_requirements(metadata.get("goal", {}), metadata)
    memory_context, memory_store_metadata = _workflow_memory_context(project_dir, metadata)
    goal_metadata = _goal_with_memory_context(goal_metadata, memory_context)
    design_stage = build_design_stage(
        project_dir=project_dir,
        workflow_id=workflow_id,
        design_doc=design_doc,
        file_list=file_list,
        metadata=metadata,
    )
    role_context = {
        "workflow_id": workflow_id,
        "project_dir": project_dir,
        "domain_profile": design_stage.get("domain_profile", {}),
        "work_design": design_stage.get("work_design", {}),
        "artifact_manifest": design_stage.get("manifest", {}),
        "deliverable_exports": design_stage.get("deliverable_exports", {}),
        "metadata": metadata,
    }
    pre_role_orchestration = await run_pre_implementation_roles(role_context)
    pre_role_task_results = _role_task_results(pre_role_orchestration)
    goal_metadata = _goal_with_design_stage(goal_metadata, design_stage)
    role_metadata = _role_orchestration_metadata(pre_role_orchestration)
    goal_metadata = _goal_with_role_orchestration(goal_metadata, role_metadata)
    task_runner = _local_task_runner_from_metadata(metadata)
    results: List[WorkflowTaskResult] = []
    thread_id = _thread_id_from_metadata(metadata)
    ledger = GoalLedger(project_dir, thread_id=thread_id) if goal_metadata else None
    ledger_state = None
    goal_ledger_metadata = ledger.describe_paths() if ledger else {}
    resume_handoff_metadata = {}

    if ledger:
        existing_goal = ledger.load_current_goal()
        ledger_state = ledger.save_current_goal(
            goal_metadata,
            active_task="workflow dispatch",
            tasks={
                "pending": list(file_list),
                "in_progress": [],
                "completed": [],
                "blocked": [],
            },
            next_recommended_action="wait for workflow dispatch results",
            expected_revision=str(existing_goal.get("_ledger_revision", "")),
        )
        ledger.append_event(
            "goal_updated" if existing_goal else "goal_created",
            {
                "objective": goal_metadata.get("objective", ""),
                "status": goal_metadata.get("status", "active"),
                "workflow_id": workflow_id,
                "file_count": len(file_list),
            },
        )

    for file_name in file_list:
        queue.put_nowait({
            "file_name": file_name,
            "design_doc": design_doc,
            "platform_mode": platform_mode,
            "role": "implementer",
            "role_graph": metadata.get("role_graph", {}),
        })

    requested_workers = _requested_worker_limit()
    cpu_cores = multiprocessing.cpu_count() or 4
    hard_limit = max(1, cpu_cores * 10)
    num_workers = _safe_worker_count(len(file_list), cpu_cores)

    workers = [
        asyncio.create_task(code_generation_worker(queue, project_id, project_dir, results, runner=task_runner))
        for _ in range(num_workers)
    ]
    print(f"[Master] starting {num_workers} worker(s) (requested: {requested_workers} / hard limit: {hard_limit})")

    await queue.join()
    if workers:
        await asyncio.gather(*workers)

    order = {file_name: index for index, file_name in enumerate(file_list)}
    ordered_results = sorted(results, key=lambda result: order.get(result.file_name, len(order)))
    check_results = check_stage.run(project_dir, metadata)
    check_success = check_results.success
    task_success = len(ordered_results) == len(file_list) and all(
        result.status == "success"
        for result in ordered_results
    )
    initial_workflow_success = bool(
        pre_role_orchestration.get("success") and task_success and check_success
    )
    workflow_evidence = _workflow_result_envelopes(
        goal=goal_metadata,
        workflow_id=workflow_id,
        project_dir=project_dir,
        design_doc=design_doc,
        file_list=list(file_list),
        task_results=[*pre_role_task_results, *ordered_results],
        design_stage=design_stage,
        check_results=check_results,
        workflow_metadata=metadata,
        workflow_success=initial_workflow_success,
        producer_boundary=producer_boundary,
    )
    evaluated_goal = evaluate_goal_evidence(
        goal_metadata,
        workflow_evidence=workflow_evidence,
        workflow_success=initial_workflow_success,
        producer_boundary=producer_boundary,
    )
    review_role_context = dict(role_context)
    review_role_context["implementation_task_results"] = [
        result.to_dict()
        for result in ordered_results
    ]
    review_role_context["qa_checks"] = _qa_checks_from_workflow_results(check_results, ordered_results)
    review_role_context["goal"] = _goal_for_review_gates(evaluated_goal)
    review_role_orchestration = await run_review_release_roles(review_role_context)
    review_role_task_results = _role_task_results(review_role_orchestration)
    role_metadata = _role_metadata_with_implementation(
        _role_orchestration_metadata(pre_role_orchestration, review_role_orchestration),
        ordered_results,
        implementation_required=bool(file_list),
    )
    role_execution_audit = audit_role_execution(role_metadata)
    evaluated_goal = _goal_with_role_orchestration(evaluated_goal, role_metadata)
    gate_results_by_role = review_role_context.get("role_gate_results", {})
    gate_results = [
        gate_results_by_role[role]
        for role in [
            "spec-reviewer",
            "code-quality-reviewer",
            "qa-verifier",
            "security-reviewer",
            "release-manager",
        ]
        if role in gate_results_by_role
    ]
    gate_evidence = _gate_result_evidence(gate_results)
    post_gate_evidence = _review_envelopes(
        gate_results,
        role_execution_audit,
        goal=evaluated_goal,
        workflow_id=workflow_id,
        producer_boundary=producer_boundary,
    )
    role_success = (
        pre_role_orchestration.get("success")
        and review_role_orchestration.get("success")
        and role_execution_audit.get("status") == "passed"
    )
    final_goal = evaluate_goal_evidence(
        evaluated_goal,
        workflow_evidence=post_gate_evidence,
        workflow_success=role_success and task_success and check_success,
        producer_boundary=producer_boundary,
    )
    retention_summary = _apply_retention_policy(
        project_dir=project_dir,
        thread_id=thread_id,
        metadata=metadata,
        memory_store_metadata=memory_store_metadata,
    )
    success = role_success and task_success and check_success
    if final_goal:
        success = role_success and task_success and check_success and final_goal.get("status") == "complete"

    workflow_usability = apply_workflow_usability_runtime(
        project_dir=project_dir,
        workflow_id=workflow_id,
        file_list=list(file_list),
        task_results=ordered_results,
        gate_results=gate_results,
        metadata=metadata,
        final_goal=final_goal or goal_metadata,
        workflow_success=success,
        preflight=workflow_usability_preflight,
    )
    if workflow_usability.enabled and workflow_usability.status == "blocked":
        success = False
        final_goal = _block_goal_for_workflow_usability(final_goal or goal_metadata, workflow_usability.to_dict())
    if ledger and final_goal:
        ledger.append_event(
            "evidence_added",
            {
                "workflow_id": workflow_id,
                "evidence": list(final_goal.get("evidence", [])),
            },
        )
        ledger_state = ledger.save_current_goal(
            final_goal,
            active_task="",
            tasks=_task_ledger_summary(ordered_results, list(file_list)),
            next_recommended_action=_next_goal_action(final_goal),
            expected_revision=str((ledger_state or {}).get("_ledger_revision", "")),
        )
        resume_handoff_metadata = ResumeHandoff(project_dir, thread_id=thread_id).save()
        event_type = "goal_completed" if final_goal.get("status") == "complete" else "goal_updated"
        if final_goal.get("status") == "blocked":
            event_type = "goal_blocked"
        ledger.append_event(
            event_type,
            {
                "objective": final_goal.get("objective", ""),
                "status": final_goal.get("status", ""),
                "blocked_reason": final_goal.get("blocked_reason", ""),
                "missing_evidence": final_goal.get("metadata", {}).get("missing_evidence", []),
                "workflow_id": workflow_id,
            },
        )
    if workflow_usability.enabled and workflow_usability.progress_panel and not metadata.get("suppress_progress_panel"):
        print(workflow_usability.progress_panel.rstrip())

    print("[Master] async workflow completed.")
    return WorkflowDispatchResult(
        workflow_id=workflow_id,
        success=success,
        task_results=ordered_results,
        gate_results=gate_results,
        metadata={
            "file_count": len(file_list),
            "platform_mode": platform_mode,
            "orchestration_roles": metadata.get("orchestration_roles", []),
            "goal": final_goal or goal_metadata,
            "goal_ledger": goal_ledger_metadata,
            "resume_handoff": resume_handoff_metadata,
            "memory_context": memory_context,
            "memory_store": memory_store_metadata,
            "domain_profile": design_stage.get("domain_profile", {}),
            "work_design": design_stage.get("work_design", {}),
            "artifact_manifest": design_stage.get("manifest", {}),
            "artifact_store": design_stage.get("store", {}),
            "deliverable_exports": design_stage.get("deliverable_exports", {}),
            "role_orchestration": role_metadata.get("summary", {}),
            "role_orchestration_stages": role_metadata.get("stages", []),
            "role_task_results": role_metadata.get("results", []),
            "role_execution_audit": role_execution_audit,
            "retention": retention_summary,
            "workflow_usability": workflow_usability.to_dict(),
            **check_results.to_metadata(),
            "gate_evidence": gate_evidence,
        },
    )


def _block_goal_for_workflow_usability(goal: dict, workflow_usability: dict) -> dict:
    blocked_goal = dict(goal or {})
    metadata = dict(blocked_goal.get("metadata", {}) or {})
    required_next_skills = [
        str(item)
        for item in workflow_usability.get("required_next_skills", [])
        if str(item).strip()
    ]
    metadata["workflow_usability_status"] = workflow_usability.get("status", "")
    metadata["workflow_usability_required_next_skills"] = required_next_skills
    metadata["missing_evidence"] = _dedupe_strings([
        *list(metadata.get("missing_evidence", []) or []),
        *required_next_skills,
    ])
    blocked_goal["status"] = "blocked"
    blocked_goal["blocked_reason"] = (
        "workflow_usability_runtime blocked completion because required KH follow-up skills "
        f"were not applied or explicitly blocked: {', '.join(required_next_skills) or 'skill_transition_handoff'}"
    )
    evidence = list(blocked_goal.get("evidence", []) or [])
    if "skill_transition_handoff" not in evidence:
        evidence.append("skill_transition_handoff")
    blocked_goal["evidence"] = evidence
    blocked_goal["metadata"] = metadata
    return blocked_goal


def _dedupe_strings(items: list) -> list:
    seen = set()
    unique = []
    for item in items:
        text = str(item)
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def dispatch_project_workflow(
    project_dir: str,
    file_list: list,
    design_doc: str,
    platform_mode: str,
    metadata: dict = None,
) -> WorkflowDispatchResult:
    return asyncio.run(async_project_workflow(project_dir, file_list, design_doc, platform_mode, metadata))
