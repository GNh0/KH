from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from src.contracts import WorkflowTaskResult
from src.orchestration.development_progress import (
    DevelopmentRunProgress,
    DevelopmentTaskProgress,
    validate_development_progress,
    write_development_progress,
)
from src.orchestration.progress_compound_bridge import write_progress_compound_artifacts
from src.orchestration.progress_panel import render_progress_panel, write_host_progress_panel
from src.orchestration.runtime_memory import (
    build_active_memory_preflight,
    record_workflow_memory_candidates,
)
from src.orchestration.runtime_token_optimizer import optimize_workflow_task_results
from src.orchestration.session_start_context import build_session_start_context
from src.orchestration.skill_application import (
    build_large_work_orchestration_bundle,
)
from src.orchestration.skill_transitions import validate_skill_transitions
from src.orchestration.token_optimizer_provider import resolve_token_optimizer_provider


@dataclass(frozen=True)
class WorkflowUsabilityRuntimeArtifacts:
    enabled: bool
    status: str = "skipped"
    session_start_context: Dict[str, Any] = field(default_factory=dict)
    token_optimizer_provider: Dict[str, Any] = field(default_factory=dict)
    token_optimization: Dict[str, Any] = field(default_factory=dict)
    memory_state: Dict[str, Any] = field(default_factory=dict)
    progress: Dict[str, Any] = field(default_factory=dict)
    progress_path: str = ""
    progress_panel: str = ""
    host_progress_panel: Dict[str, Any] = field(default_factory=dict)
    host_progress_panel_path: str = ""
    compound: Dict[str, Any] = field(default_factory=dict)
    skill_transition_handoff: Dict[str, Any] = field(default_factory=dict)
    required_next_skills: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    error_type: str = ""
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def workflow_usability_enabled(metadata: Dict[str, Any] | None) -> bool:
    metadata = metadata or {}
    app_context = metadata.get("app_context", {}) or {}
    return bool(
        metadata.get("workflow_usability_auto")
        or metadata.get("uaf_workflow_usability_auto")
        or app_context.get("workflow_usability_auto")
    )


def build_workflow_usability_preflight(
    project_dir: str,
    metadata: Dict[str, Any] | None,
) -> Dict[str, Any]:
    if not workflow_usability_enabled(metadata):
        return {}

    metadata = metadata or {}
    thread_id = _thread_id_from_metadata(metadata)
    objective = str(metadata.get("objective") or metadata.get("request") or metadata.get("goal") or "")
    session_context = build_session_start_context(
        project_dir,
        thread_id=thread_id,
        memory_root=metadata.get("memory_root") or None,
        max_items=int(metadata.get("session_context_max_items", 10)),
        objective=objective,
    )
    active_memory = build_active_memory_preflight(
        project_dir,
        metadata,
        objective=objective,
    )
    token_decision = resolve_token_optimizer_provider(
        token_optimizer_provider=metadata.get("token_optimizer_provider", "kh"),
        command=metadata.get("token_optimizer_command", "workflow dispatch"),
        content_kind=metadata.get("token_optimizer_content_kind", "auto"),
        rtk_available=bool(metadata.get("rtk_available", False)),
        strict=bool(metadata.get("token_optimizer_strict", False)),
    )
    return {
        "enabled": True,
        "session_start_context": session_context,
        "active_memory_preflight": active_memory,
        "token_optimizer_provider": token_decision.to_dict(),
        "evidence": [
            "workflow_usability_preflight",
            "session_start_context",
            *list(active_memory.get("evidence", [])),
            "token_optimizer_provider",
        ],
    }


def apply_workflow_usability_runtime(
    project_dir: str,
    workflow_id: str,
    file_list: List[str],
    task_results: List[WorkflowTaskResult],
    gate_results: List[Dict[str, Any]],
    metadata: Dict[str, Any] | None,
    final_goal: Dict[str, Any] | None,
    workflow_success: bool,
    preflight: Dict[str, Any] | None = None,
) -> WorkflowUsabilityRuntimeArtifacts:
    if not workflow_usability_enabled(metadata):
        return WorkflowUsabilityRuntimeArtifacts(enabled=False)

    metadata = metadata or {}
    preflight = preflight or build_workflow_usability_preflight(project_dir, metadata)
    try:
        optimized_task_results, token_optimization = optimize_workflow_task_results(
            task_results,
            metadata=metadata,
        )
        runtime_metadata = dict(metadata)
        runtime_metadata["token_optimization"] = token_optimization
        runtime_metadata["token_optimizer_status"] = token_optimization.get(
            "status",
            runtime_metadata.get("token_optimizer_status", ""),
        )
        runtime_metadata["token_optimizer_status_reason"] = token_optimization.get(
            "token_optimizer_status_reason",
            runtime_metadata.get("token_optimizer_status_reason", ""),
        )
        progress = build_workflow_development_progress(
            workflow_id=workflow_id,
            file_list=file_list,
            task_results=optimized_task_results,
            gate_results=gate_results,
            metadata=runtime_metadata,
            final_goal=final_goal or {},
            workflow_success=workflow_success,
        )
        validation = validate_development_progress(progress)
        if not validation["valid"]:
            raise ValueError(f"invalid workflow usability progress: {validation['missing']}")
        progress_path = write_development_progress(project_dir, progress)
        panel = render_progress_panel(progress)
        host_panel_host = str(metadata.get("host_panel_host") or metadata.get("platform") or metadata.get("host") or "generic")
        host_panel_path = write_host_progress_panel(project_dir, progress, host=host_panel_host)
        host_panel = progress_to_host_panel(host_panel_path)
        compound_artifacts = write_progress_compound_artifacts(project_dir, progress)
        memory_state = record_workflow_memory_candidates(
            project_dir,
            metadata,
            compound_artifacts.memory_candidates,
        )
        transition_handoff = _validate_runtime_skill_transitions(
            progress=progress,
            metadata=runtime_metadata,
            token_optimization=token_optimization,
            compound_artifacts=compound_artifacts.to_dict(),
            memory_state=memory_state,
        )
        required_next_skills = [
            str(item)
            for item in transition_handoff.get("required_next_skills", [])
            if str(item).strip()
        ]
        transition_valid = bool(transition_handoff.get("valid", False))
        runtime_status = _workflow_usability_runtime_status(
            workflow_success,
            transition_valid,
            transition_handoff,
        )
        return WorkflowUsabilityRuntimeArtifacts(
            enabled=True,
            status=runtime_status,
            session_start_context=dict(preflight.get("session_start_context", {})),
            token_optimizer_provider=dict(preflight.get("token_optimizer_provider", {})),
            token_optimization=token_optimization,
            memory_state=memory_state,
            progress=progress.to_dict(),
            progress_path=str(progress_path),
            progress_panel=panel,
            host_progress_panel=host_panel,
            host_progress_panel_path=str(host_panel_path),
            compound=compound_artifacts.to_dict(),
            skill_transition_handoff=transition_handoff,
            required_next_skills=required_next_skills,
            evidence=[
                "workflow_usability_runtime",
                "progress_json",
                "development_progress_valid",
                "progress_panel",
                "host_progress_panel",
                "compound_handoff",
                "skill_transition_handoff",
                *list(token_optimization.get("evidence", [])),
                *list(memory_state.get("evidence", [])),
                *list(compound_artifacts.evidence),
                *(["required_next_skills"] if required_next_skills else []),
            ],
        )
    except Exception as exc:
        return WorkflowUsabilityRuntimeArtifacts(
            enabled=True,
            status="blocked",
            session_start_context=dict(preflight.get("session_start_context", {})),
            token_optimizer_provider=dict(preflight.get("token_optimizer_provider", {})),
            token_optimization={},
            memory_state={},
            skill_transition_handoff={},
            required_next_skills=[],
            evidence=["workflow_usability_runtime"],
            error_type=type(exc).__name__,
            message=str(exc),
        )


def _validate_runtime_skill_transitions(
    progress: DevelopmentRunProgress,
    metadata: Dict[str, Any],
    token_optimization: Dict[str, Any],
    compound_artifacts: Dict[str, Any],
    memory_state: Dict[str, Any],
) -> Dict[str, Any]:
    compound_handoff = dict(compound_artifacts.get("handoff", {}) or {})
    memory_candidates = list(compound_artifacts.get("memory_candidates", []) or [])
    bundle = build_large_work_orchestration_bundle(
        objective=progress.objective,
        workspace_strategy=progress.workspace_strategy or "in-place",
        token_optimizer_status=progress.token_optimizer_status,
        token_optimizer_status_reason=progress.token_optimizer_status_reason,
        overrides=_runtime_skill_status_overrides(metadata, token_optimization, memory_state),
        parallel_strategy_decision=str(
            metadata.get("parallel_strategy_decision")
            or progress.metadata.get("parallel_strategy_decision")
            or "sequential single-worker execution"
        ),
        memory_candidates=memory_candidates,
        compound_handoff=compound_handoff,
        metadata={
            "source": "workflow_usability_runtime",
            "run_id": progress.run_id,
            "compound_paths": dict(compound_artifacts.get("paths", {}) or {}),
        },
    )
    handoff = validate_skill_transitions(bundle, phase="final")
    return {
        **handoff,
        "compound_next_skills": list(compound_handoff.get("next_skills", []) or []),
        "token_optimizer_status": progress.token_optimizer_status,
        "token_optimizer_status_reason": progress.token_optimizer_status_reason,
        "memory_state_status": str(memory_state.get("status", "")),
    }


def _runtime_skill_status_overrides(
    metadata: Dict[str, Any],
    token_optimization: Dict[str, Any],
    memory_state: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    overrides = _metadata_skill_status_overrides(metadata.get("skill_statuses", {}))
    overrides["compound-engineering-harness"] = {
        "status": "applied",
        "application_mode": "runtime",
        "evidence_note": "Workflow usability runtime wrote Compound capture and handoff artifacts.",
        "evidence_keys": ["compound_handoff", "compound_artifacts_written"],
    }
    token_status = str(token_optimization.get("status", "")).strip()
    if token_status == "used":
        overrides["token-optimizer"] = {
            "status": "applied",
            "application_mode": "runtime",
            "evidence_note": "Token optimizer ran during workflow usability runtime.",
            "evidence_keys": ["runtime_token_optimization", "token_usage"],
        }
    elif token_status in {"considered_not_needed", "passthrough"}:
        overrides["token-optimizer"] = {
            "status": "applied",
            "application_mode": "procedural",
            "evidence_note": "Token optimizer gate recorded a non-optimization decision.",
            "evidence_keys": ["token_optimizer_status", "token_optimizer_status_reason"],
        }
    elif token_status == "blocked":
        overrides["token-optimizer"] = {
            "status": "blocked",
            "application_mode": "blocked",
            "evidence_note": "Token optimizer gate was blocked during runtime.",
            "evidence_keys": ["token_optimizer_status", "token_optimizer_status_reason"],
            "blocked_reason": str(token_optimization.get("token_optimizer_status_reason", "blocked")),
        }

    if memory_state.get("status") == "candidates_recorded":
        overrides["memory-state-harness"] = {
            "status": "applied",
            "application_mode": "runtime",
            "evidence_note": "Runtime memory candidate recorder persisted scoped memory candidates.",
            "evidence_keys": ["memory_candidates_recorded"],
        }
    return overrides


def _workflow_usability_runtime_status(
    workflow_success: bool,
    transition_valid: bool,
    transition_handoff: Dict[str, Any],
) -> str:
    if not workflow_success:
        return "blocked"
    if transition_valid:
        return "complete"
    issues = list(transition_handoff.get("issues", []) or [])
    if issues and all(str(issue.get("rule", "")).startswith("compound_next_skill_requires_followup") for issue in issues):
        return "complete_with_followup"
    return "blocked"


def _metadata_skill_status_overrides(raw_statuses: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw_statuses, dict):
        return {}
    overrides: Dict[str, Dict[str, Any]] = {}
    for skill_name, raw_status in raw_statuses.items():
        name = str(skill_name).strip()
        if not name:
            continue
        if isinstance(raw_status, dict):
            status = str(raw_status.get("status", "")).strip() or "blocked"
            application_mode = str(raw_status.get("application_mode", "")).strip() or (
                "blocked" if status == "blocked" else "procedural"
            )
            overrides[name] = {
                "status": status,
                "application_mode": application_mode,
                "evidence_note": str(raw_status.get("evidence_note", "")).strip()
                or f"{name} status supplied by workflow metadata.",
                "evidence_keys": [str(item) for item in raw_status.get("evidence_keys", [])],
                "blocked_reason": str(raw_status.get("blocked_reason", "")).strip(),
                "metadata": dict(raw_status.get("metadata", {}) or {}),
            }
        else:
            status = str(raw_status).strip() or "blocked"
            overrides[name] = {
                "status": status,
                "application_mode": "blocked" if status == "blocked" else "procedural",
                "evidence_note": f"{name} status supplied by workflow metadata.",
                "evidence_keys": ["metadata_skill_status"],
                "blocked_reason": "metadata supplied blocked status" if status == "blocked" else "",
            }
    return overrides


def progress_to_host_panel(path: str | Any) -> Dict[str, Any]:
    import json
    from pathlib import Path

    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_workflow_development_progress(
    workflow_id: str,
    file_list: List[str],
    task_results: List[WorkflowTaskResult],
    gate_results: List[Dict[str, Any]],
    metadata: Dict[str, Any] | None,
    final_goal: Dict[str, Any],
    workflow_success: bool,
) -> DevelopmentRunProgress:
    metadata = metadata or {}
    goal = final_goal or metadata.get("goal", {}) or {}
    token_decision = resolve_token_optimizer_provider(
        token_optimizer_provider=metadata.get("token_optimizer_provider", "kh"),
        command=metadata.get("token_optimizer_command", "workflow dispatch"),
        content_kind=metadata.get("token_optimizer_content_kind", "auto"),
        rtk_available=bool(metadata.get("rtk_available", False)),
        strict=bool(metadata.get("token_optimizer_strict", False)),
    )
    task_statuses = _task_status_by_file(task_results)
    task_items = [
        _task_progress_for_file(
            file_name=file_name,
            index=index,
            result=task_statuses.get(file_name),
            gate_results=gate_results,
            workflow_success=workflow_success,
        )
        for index, file_name in enumerate(file_list, start=1)
    ]
    if not task_items:
        task_items = [_non_file_task_progress(workflow_success, gate_results)]

    status = "complete" if workflow_success else "blocked"
    return DevelopmentRunProgress(
        run_id=_safe_run_id(str(metadata.get("workflow_usability_run_id") or workflow_id)),
        objective=str(goal.get("objective") or metadata.get("objective") or "UAF workflow dispatch"),
        workspace_strategy=str(metadata.get("workspace_strategy") or _infer_workspace_strategy(metadata)),
        workspace_path=str(metadata.get("workspace_path") or metadata.get("host_workspace") or ""),
        branch=str(metadata.get("branch", "")),
        active_task="",
        task_status=status,
        review_status=_review_status(gate_results),
        commit_sha=str(metadata.get("commit_sha", "")),
        next_task=_next_task_id(task_items, workflow_success),
        token_optimizer_status=str(metadata.get("token_optimizer_status") or _token_optimizer_status(token_decision.to_dict())),
        token_optimizer_status_reason=str(
            metadata.get("token_optimizer_status_reason") or _token_optimizer_status_reason(token_decision.to_dict())
        ),
        skill_statuses=dict(metadata.get("skill_statuses", {})),
        tasks=task_items,
        artifacts=list(metadata.get("artifacts", []) or []),
        metadata={
            "source": "workflow_usability_runtime",
            "workflow_id": workflow_id,
            "token_optimizer_provider": token_decision.to_dict(),
            "token_optimization": dict(metadata.get("token_optimization", {})),
            "memory_state": dict(metadata.get("memory_state", {})),
            "learning_candidates": _learning_candidates(workflow_id, workflow_success, gate_results),
            "memory_candidates": _memory_candidates(workflow_id, workflow_success),
            "scenario_candidates": _scenario_candidates(workflow_id, workflow_success),
            "system_updates": ["Review workflow usability evidence for reusable KH automation improvements."],
            "regression_checks": ["python -m unittest tests.test_workflow_usability_layer tests.test_workflows"],
        },
    )


def _task_progress_for_file(
    file_name: str,
    index: int,
    result: WorkflowTaskResult | None,
    gate_results: List[Dict[str, Any]],
    workflow_success: bool,
) -> DevelopmentTaskProgress:
    result_success = bool(result and result.status == "success")
    commit_sha = _result_commit_sha(result, workflow_success)
    return DevelopmentTaskProgress(
        task_id=f"task-{index}",
        title=file_name,
        status="complete" if result_success and workflow_success else "blocked",
        red_status="not_applicable",
        green_status="passed" if result_success else "failed",
        spec_review_status=_role_gate_status(gate_results, "spec-reviewer"),
        code_quality_review_status=_role_gate_status(gate_results, "code-quality-reviewer"),
        fix_status="not_applicable",
        re_review_status="not_applicable",
        commit_sha=commit_sha,
        changed_files=[file_name],
        verification=list((result.metadata or {}).get("verification", []) or []) if result else [],
        next_action="" if result_success and workflow_success else "inspect workflow gate failure",
        metadata={
            "workflow_task_result": result.to_dict() if result else {},
            "review_findings": _review_findings(gate_results),
        },
    )


def _non_file_task_progress(
    workflow_success: bool,
    gate_results: List[Dict[str, Any]],
) -> DevelopmentTaskProgress:
    return DevelopmentTaskProgress(
        task_id="task-1",
        title="workflow gates",
        status="complete" if workflow_success else "blocked",
        red_status="not_applicable",
        green_status="passed" if workflow_success else "failed",
        spec_review_status=_role_gate_status(gate_results, "spec-reviewer"),
        code_quality_review_status=_role_gate_status(gate_results, "code-quality-reviewer"),
        fix_status="not_applicable",
        re_review_status="not_applicable",
        commit_sha="not_applicable" if workflow_success else "",
        next_action="" if workflow_success else "collect missing goal or gate evidence",
        metadata={"review_findings": _review_findings(gate_results)},
    )


def _task_status_by_file(task_results: List[WorkflowTaskResult]) -> Dict[str, WorkflowTaskResult]:
    return {result.file_name: result for result in task_results}


def _role_gate_status(gate_results: List[Dict[str, Any]], role: str) -> str:
    for gate in gate_results:
        if gate.get("role") != role:
            continue
        status = str(gate.get("status", "pending"))
        if status == "passed":
            return "passed"
        if status in {"with_fixes", "blocked"}:
            return status
        return "blocked"
    return "not_applicable"


def _review_status(gate_results: List[Dict[str, Any]]) -> str:
    statuses = {str(gate.get("status", "")) for gate in gate_results}
    if "blocked" in statuses:
        return "blocked"
    if "with_fixes" in statuses:
        return "with_fixes"
    if statuses and statuses <= {"passed", "not_applicable"}:
        return "passed"
    return "pending"


def _review_findings(gate_results: List[Dict[str, Any]]) -> List[str]:
    findings = []
    for gate in gate_results:
        status = gate.get("status")
        if status == "passed":
            continue
        role = gate.get("role", "gate")
        reason = gate.get("blocked_reason") or gate.get("message") or status
        findings.append(f"{role}: {reason}")
    return findings or ["No blocking workflow usability findings recorded."]


def _learning_candidates(
    workflow_id: str,
    workflow_success: bool,
    gate_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if workflow_success:
        return [
            {
                "title": f"Workflow {workflow_id} produced resumable KH usability evidence",
                "trigger": "UAF workflow completed with automatic progress and Compound handoff",
                "reusable_insight": "Future long KH runs should expose progress, token provider, session context, and Compound candidates without manual helper calls.",
                "evidence": ["progress_json", "progress_panel", "compound_handoff"],
                "target_update": "skill",
                "tags": ["workflow-usability", "resume", "compound"],
            }
        ]
    return [
        {
            "title": f"Workflow {workflow_id} blocked with visible KH usability evidence",
            "trigger": "UAF workflow blocked after review or gate evaluation",
            "reusable_insight": "Blocked KH runs should leave progress, review findings, missing evidence, and next action for the next session.",
            "evidence": ["progress_json", *_review_findings(gate_results)],
            "target_update": "scenario",
            "tags": ["workflow-usability", "blocked", "resume"],
        }
    ]


def _memory_candidates(workflow_id: str, workflow_success: bool) -> List[Dict[str, Any]]:
    status = "completed" if workflow_success else "blocked"
    return [
        {
            "scope": "project",
            "content": f"Workflow {workflow_id} {status}; resume from .kh/development/{_safe_run_id(workflow_id)}/state/progress.json and docs/kh/handoffs/{_safe_run_id(workflow_id)}-compound.md.",
            "evidence": ["progress_json", "compound_handoff"],
            "confidence": 0.7,
        }
    ]


def _scenario_candidates(workflow_id: str, workflow_success: bool) -> List[Dict[str, Any]]:
    return [
        {
            "title": f"Resume workflow {workflow_id} from KH usability artifacts",
            "source": "workflow_usability_runtime",
            "status": "complete" if workflow_success else "blocked",
            "evidence": ["session_start_context", "progress_json", "compound_handoff"],
            "next_skill": "scenario-evaluation-harness",
        }
    ]


def _token_optimizer_status(token_decision: Dict[str, Any]) -> str:
    if token_decision.get("command_strategy") == "quality-preserving-passthrough":
        return "passthrough"
    if token_decision.get("status") == "blocked":
        return "blocked"
    return "considered_not_needed"


def _token_optimizer_status_reason(token_decision: Dict[str, Any]) -> str:
    rationale = str(token_decision.get("rationale", "") or "").strip()
    status = _token_optimizer_status(token_decision)
    if status == "passthrough":
        return _join_reason("Token optimizer not used because content was passed through unchanged", rationale)
    if status == "blocked":
        return _join_reason("Token optimizer not used because optimization was blocked", rationale)
    return "Token optimizer not used because the workflow has not produced large command output or transcripts yet."


def _join_reason(prefix: str, reason: str) -> str:
    clean = reason.strip().rstrip(".")
    return f"{prefix}: {clean}." if clean else f"{prefix}."


def _result_commit_sha(result: WorkflowTaskResult | None, workflow_success: bool) -> str:
    if result and (result.metadata or {}).get("commit_sha"):
        return str((result.metadata or {}).get("commit_sha"))
    return "not_applicable" if workflow_success else ""


def _next_task_id(task_items: List[DevelopmentTaskProgress], workflow_success: bool) -> str:
    if workflow_success:
        return ""
    for task in task_items:
        if task.status != "complete":
            return task.task_id
    return task_items[0].task_id if task_items else ""


def _infer_workspace_strategy(metadata: Dict[str, Any]) -> str:
    if metadata.get("host_workspace"):
        return "host-worktree"
    workspace_path = str(metadata.get("workspace_path", ""))
    if ".worktrees" in workspace_path.replace("\\", "/"):
        return "project-local-worktree"
    if metadata.get("branch"):
        return "isolated-branch"
    return "current-checkout"


def _thread_id_from_metadata(metadata: Dict[str, Any]) -> str:
    app_context = metadata.get("app_context", {}) or {}
    return metadata.get("thread_id", "") or app_context.get("thread_id", "")


def _safe_run_id(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value.strip())
    return safe.strip(".-") or "workflow"
