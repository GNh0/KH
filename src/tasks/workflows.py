import asyncio
import base64
import json
import multiprocessing
import os
from typing import List

import httpx

from src.contracts import MemoryScope, WorkflowDispatchResult, WorkflowTaskResult
from src.orchestration.artifacts import build_design_stage
from src.orchestration.evidence_producers import collect_metadata_evidence
from src.orchestration.goal_evidence import (
    collect_workflow_goal_evidence,
    evaluate_goal_evidence,
)
from src.orchestration.goal_ledger import GoalLedger
from src.orchestration.handoff import ResumeHandoff
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryStore
from src.orchestration.roles import build_role_gate_results
from src.tasks.workflow_checks import WorkflowCheckStage, goal_with_check_requirements
from src.tasks.runners import (
    LLMCodeGenerationAdapter,
    LocalTaskRunner,
    WorkflowTaskInput,
    task_id_for_file,
)


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
    updated_goal["metadata"] = metadata
    return updated_goal


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


async def _report_task_result_to_webhook(
    client: httpx.AsyncClient,
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

    async with httpx.AsyncClient() as client:
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
                    client,
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
    metadata = metadata or {}
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
    goal_metadata = _goal_with_design_stage(goal_metadata, design_stage)
    task_runner = _local_task_runner_from_metadata(metadata)
    results: List[WorkflowTaskResult] = []
    ledger = GoalLedger(project_dir) if goal_metadata else None
    goal_ledger_metadata = ledger.describe_paths() if ledger else {}
    resume_handoff_metadata = {}

    if ledger:
        existing_goal = ledger.load_current_goal()
        ledger.save_current_goal(
            goal_metadata,
            active_task="workflow dispatch",
            tasks={
                "pending": list(file_list),
                "in_progress": [],
                "completed": [],
                "blocked": [],
            },
            next_recommended_action="wait for workflow dispatch results",
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
    workflow_evidence = collect_workflow_goal_evidence(
        design_doc=design_doc,
        file_list=file_list,
        workflow_completed=True,
    )
    workflow_evidence.extend(_task_result_evidence(ordered_results))
    workflow_evidence.extend(design_stage.get("evidence", []))
    workflow_evidence.extend(check_results.evidence)
    evaluated_goal = evaluate_goal_evidence(
        goal_metadata,
        workflow_evidence=workflow_evidence,
        workflow_success=task_success,
    )
    gate_results = build_role_gate_results([
        result.to_dict()
        for result in ordered_results
    ], goal=evaluated_goal)
    gate_evidence = _gate_result_evidence(gate_results)
    final_goal = _goal_with_added_evidence(evaluated_goal, gate_evidence)
    if ledger and final_goal:
        ledger.append_event(
            "evidence_added",
            {
                "workflow_id": workflow_id,
                "evidence": list(final_goal.get("evidence", [])),
            },
        )
        ledger.save_current_goal(
            final_goal,
            active_task="",
            tasks=_task_ledger_summary(ordered_results, list(file_list)),
            next_recommended_action=_next_goal_action(final_goal),
        )
        resume_handoff_metadata = ResumeHandoff(project_dir).save()
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
    success = task_success and check_success
    if final_goal:
        success = task_success and check_success and final_goal.get("status") == "complete"

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
            **check_results.to_metadata(),
            "gate_evidence": gate_evidence,
        },
    )


def dispatch_project_workflow(
    project_dir: str,
    file_list: list,
    design_doc: str,
    platform_mode: str,
    metadata: dict = None,
) -> WorkflowDispatchResult:
    return asyncio.run(async_project_workflow(project_dir, file_list, design_doc, platform_mode, metadata))
