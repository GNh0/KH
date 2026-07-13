from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from src.orchestration.goal_runtime import (
    validate_goal_runtime_receipt,
    validate_host_goal_receipt,
)
from src.orchestration.goal_evidence import RuntimeProducerBoundary
from src.orchestration.quality_harnesses import audit_role_execution


BUNDLE_STATUS_VALUES = {
    "applied",
    "considered_not_needed",
    "skipped_with_rationale",
    "blocked",
    "pending_immediate_execution",
}
BUNDLE_APPLICATION_MODES = {
    "runtime",
    "procedural",
    "considered",
    "blocked",
    "immediate_gate",
}
TOKEN_OPTIMIZER_STATUS_VALUES = {
    "used",
    "considered_not_needed",
    "passthrough",
    "blocked",
}
GOAL_EXECUTION_EVIDENCE_KEYS = {
    "goal_runtime",
    "goal_ledger",
    "host_goal",
    "host_goal_evidence",
    "thread_goal_updated",
    "current_goal.json",
}
BUNDLE_MEMBER_SKILLS = [
    "request-complexity-router",
    "host-agent-orchestration",
    "domain-orchestration-harness",
    "goal-state-harness",
    "development-lifecycle-harness",
    "worktree-isolation-harness",
    "plan-execution-harness",
    "systematic-debugging-harness",
    "command-output-harness",
    "token-optimizer",
    "memory-state-harness",
    "parallel-orchestration-harness",
    "subagent-review-pipeline",
    "role-execution-audit-harness",
    "quality-gates-harness",
    "review-gate-harness",
    "qa-gate-harness",
    "artifact-render-qa-harness",
    "deliverable-template-quality-harness",
    "traceability-matrix-harness",
    "verification-before-completion-harness",
    "branch-finishing-harness",
    "compound-engineering-harness",
    "workflow-skill-distiller",
]


@dataclass(frozen=True)
class SkillApplicationStatus:
    status: str
    application_mode: str
    evidence_note: str
    evidence_keys: List[str] = field(default_factory=list)
    blocked_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillApplicationStatus":
        return cls(
            status=str(data.get("status", "")),
            application_mode=str(data.get("application_mode", "")),
            evidence_note=str(data.get("evidence_note", "")),
            evidence_keys=[str(item) for item in data.get("evidence_keys", [])],
            blocked_reason=str(data.get("blocked_reason", "")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class LargeWorkOrchestrationBundle:
    objective: str
    skill_statuses: Dict[str, SkillApplicationStatus]
    workspace_strategy: str
    token_optimizer_status: str
    token_optimizer_status_reason: str
    parallel_strategy_decision: str
    memory_candidates: List[Dict[str, Any]] = field(default_factory=list)
    compound_handoff: Dict[str, Any] = field(default_factory=dict)
    evidence_key: str = "large_work_orchestration_bundle"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_key": self.evidence_key,
            "objective": self.objective,
            "skill_statuses": {
                name: status.to_dict()
                for name, status in self.skill_statuses.items()
            },
            "workspace_strategy": self.workspace_strategy,
            "token_optimizer_status": self.token_optimizer_status,
            "token_optimizer_status_reason": self.token_optimizer_status_reason,
            "parallel_strategy_decision": self.parallel_strategy_decision,
            "memory_candidates": [dict(item) for item in self.memory_candidates],
            "compound_handoff": dict(self.compound_handoff),
            "metadata": dict(self.metadata),
        }


def build_large_work_orchestration_bundle(
    objective: str,
    workspace_strategy: str,
    token_optimizer_status: str,
    token_optimizer_status_reason: str = "",
    overrides: Dict[str, Dict[str, Any]] | None = None,
    parallel_strategy_decision: str = "sequential with rationale until independent write sets are proven",
    memory_candidates: List[Dict[str, Any]] | None = None,
    compound_handoff: Dict[str, Any] | None = None,
    metadata: Dict[str, Any] | None = None,
) -> LargeWorkOrchestrationBundle:
    overrides = overrides or {}
    skill_statuses = _default_skill_statuses()
    token_status = str(token_optimizer_status or "").strip()
    if token_status in TOKEN_OPTIMIZER_STATUS_VALUES and "token-optimizer" not in overrides:
        skill_statuses["token-optimizer"] = _token_optimizer_skill_status(token_status)
    for skill_name, override in overrides.items():
        base = skill_statuses.get(
            skill_name,
            SkillApplicationStatus(
                status="blocked",
                application_mode="blocked",
                evidence_note="Unknown skill in large-work bundle.",
                blocked_reason="unknown_skill",
            ),
        )
        merged = {
            **base.to_dict(),
            **dict(override),
        }
        skill_statuses[skill_name] = SkillApplicationStatus.from_dict(merged)
    return LargeWorkOrchestrationBundle(
        objective=objective,
        skill_statuses=skill_statuses,
        workspace_strategy=workspace_strategy,
        token_optimizer_status=token_optimizer_status,
        token_optimizer_status_reason=token_optimizer_status_reason
        or _default_token_optimizer_status_reason(token_optimizer_status),
        parallel_strategy_decision=parallel_strategy_decision,
        memory_candidates=memory_candidates or [],
        compound_handoff=compound_handoff
        or {
            "status": "pending",
            "rationale": "Evaluate reusable learning after review.",
        },
        metadata=metadata or {},
    )


def validate_large_work_orchestration_bundle(
    bundle: LargeWorkOrchestrationBundle,
    *,
    goal_runtime_producer_boundary: RuntimeProducerBoundary | None = None,
) -> Dict[str, Any]:
    missing: List[str] = []
    runtime_boundary = (
        goal_runtime_producer_boundary
        if isinstance(goal_runtime_producer_boundary, RuntimeProducerBoundary)
        else None
    )
    if not bundle.objective.strip():
        missing.append("objective")
    if not bundle.workspace_strategy.strip():
        missing.append("workspace_strategy")
    if not bundle.token_optimizer_status.strip():
        missing.append("token_optimizer_status")
    elif bundle.token_optimizer_status not in TOKEN_OPTIMIZER_STATUS_VALUES:
        missing.append("token_optimizer_status")
    if bundle.token_optimizer_status.strip() and not bundle.token_optimizer_status_reason.strip():
        missing.append("token_optimizer_status_reason")
    if not bundle.parallel_strategy_decision.strip():
        missing.append("parallel_strategy_decision")
    if not bundle.compound_handoff:
        missing.append("compound_handoff")
    for skill_name in BUNDLE_MEMBER_SKILLS:
        status = bundle.skill_statuses.get(skill_name)
        if status is None:
            missing.append(f"{skill_name}.status")
            continue
        if status.status not in BUNDLE_STATUS_VALUES:
            missing.append(f"{skill_name}.status")
        if status.application_mode not in BUNDLE_APPLICATION_MODES:
            missing.append(f"{skill_name}.application_mode")
        if not status.evidence_note.strip():
            missing.append(f"{skill_name}.evidence_note")
        if status.status == "blocked" and not status.blocked_reason.strip():
            missing.append(f"{skill_name}.blocked_reason")
        if (
            skill_name == "goal-state-harness"
            and status.status == "applied"
            and not GOAL_EXECUTION_EVIDENCE_KEYS.intersection(status.evidence_keys)
        ):
            missing.append("goal-state-harness.execution_evidence")
        if skill_name == "goal-state-harness" and status.status == "applied":
            receipt_metadata = dict(status.metadata or {})
            activation = receipt_metadata.get("goal_activation", {})
            activation = dict(activation) if isinstance(activation, dict) else {}
            activation_receipts = activation.get("runtime_receipts", {})
            activation_receipts = (
                dict(activation_receipts) if isinstance(activation_receipts, dict) else {}
            )
            project = str(bundle.metadata.get("project") or "")
            thread_id = str(bundle.metadata.get("thread_id") or "")
            task_id = str(bundle.metadata.get("task_id") or "")
            runtime_validation = validate_goal_runtime_receipt(
                receipt_metadata.get("goal_runtime_receipt")
                or activation_receipts.get("kh_goal_ledger"),
                project=project or ".",
                thread_id=thread_id,
                task_id=task_id,
                objective=bundle.objective,
                producer_boundary=runtime_boundary,
            )
            host_validation = validate_host_goal_receipt(
                receipt_metadata.get("host_goal_receipt")
                or activation_receipts.get("host_goal"),
                thread_id=thread_id,
                task_id=task_id,
                objective=bundle.objective,
            )
            if not runtime_validation["valid"] and not host_validation["valid"]:
                missing.append("goal-state-harness.validated_runtime_receipt")
        if (
            skill_name in {"parallel-orchestration-harness", "role-execution-audit-harness"}
            and (status.status == "applied" or status.application_mode == "runtime")
        ):
            artifact_validation = _validate_role_execution_artifacts(status, bundle)
            if (
                skill_name == "parallel-orchestration-harness"
                and not artifact_validation["valid_parallel_wave"]
            ):
                missing.append("parallel-orchestration-harness.validated_wave_artifacts")
            if (
                skill_name == "role-execution-audit-harness"
                and not artifact_validation["valid_role_artifacts"]
            ):
                missing.append("role-execution-audit-harness.validated_role_artifacts")
    for skill_name in set(bundle.skill_statuses) - set(BUNDLE_MEMBER_SKILLS):
        missing.append(f"{skill_name}.known_bundle_member")
    evidence = []
    if not missing:
        evidence = [
            "large_work_orchestration_bundle",
            "skill_statuses",
            "workspace_strategy",
            "parallel_strategy_decision",
            "token_optimizer_status",
            "token_optimizer_status_reason",
            "memory_candidates",
            "compound_handoff",
        ]
    return {
        "valid": not missing,
        "missing": missing,
        "evidence": evidence,
    }


def _validate_role_execution_artifacts(
    status: SkillApplicationStatus,
    bundle: LargeWorkOrchestrationBundle,
) -> Dict[str, bool]:
    metadata = dict(status.metadata or {})
    role_orchestration = metadata.get("role_orchestration") or bundle.metadata.get(
        "role_orchestration"
    )
    if not isinstance(role_orchestration, dict):
        return {"valid_parallel_wave": False, "valid_role_artifacts": False}
    required_roles = metadata.get("required_roles")
    audit = audit_role_execution(
        role_orchestration,
        required_roles=list(required_roles) if isinstance(required_roles, list) else None,
    )
    waves = list(role_orchestration.get("waves", []) or [])
    for stage in role_orchestration.get("stages", []) or []:
        if isinstance(stage, dict):
            waves.extend(stage.get("waves", []) or [])
    parallel_waves = [
        wave
        for wave in waves
        if isinstance(wave, dict)
        and wave.get("parallel") is True
        and wave.get("runtime_overlap") is True
        and wave.get("results")
    ]
    valid_parallel_wave = any(
        all(
            isinstance(result, dict)
            and result.get("status") == "success"
            and isinstance(result.get("metadata"), dict)
            and result["metadata"].get("role_artifacts")
            for result in wave.get("results", [])
        )
        for wave in parallel_waves
    )
    return {
        "valid_parallel_wave": valid_parallel_wave,
        "valid_role_artifacts": audit.get("status") == "passed",
    }


def _default_skill_statuses() -> Dict[str, SkillApplicationStatus]:
    return {
        "request-complexity-router": SkillApplicationStatus(
            status="applied",
            application_mode="procedural",
            evidence_note="Classified the request before selecting execution depth.",
            evidence_keys=["classification"],
        ),
        "host-agent-orchestration": SkillApplicationStatus(
            status="pending_immediate_execution",
            application_mode="immediate_gate",
            evidence_note="Pending host runtime, tool-boundary, and subagent-strategy evidence.",
            evidence_keys=["host_runtime_decision"],
        ),
        "domain-orchestration-harness": SkillApplicationStatus(
            status="pending_immediate_execution",
            application_mode="immediate_gate",
            evidence_note="Pending domain work-design and execution evidence.",
            evidence_keys=["domain_profile", "work_design"],
        ),
        "goal-state-harness": SkillApplicationStatus(
            status="pending_immediate_execution",
            application_mode="immediate_gate",
            evidence_note="Pending KH Goal runtime, GoalLedger, or authorized host Goal evidence.",
            evidence_keys=["goal_runtime", "goal_ledger", "host_goal_evidence"],
        ),
        "development-lifecycle-harness": SkillApplicationStatus(
            status="pending_immediate_execution",
            application_mode="immediate_gate",
            evidence_note="Pending plan, work, review, verification, and integration evidence.",
            evidence_keys=["task_status", "review_status"],
        ),
        "worktree-isolation-harness": SkillApplicationStatus(
            status="pending_immediate_execution",
            application_mode="immediate_gate",
            evidence_note="Pending workspace strategy or an explicit in-place exception.",
            evidence_keys=["workspace_strategy"],
        ),
        "plan-execution-harness": SkillApplicationStatus(
            status="pending_immediate_execution",
            application_mode="immediate_gate",
            evidence_note="Pending progress state, task status, and next-task handoff evidence.",
            evidence_keys=["progress.json", "task_status", "next_task"],
        ),
        "systematic-debugging-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No unexpected failure or bug diagnosis loop has appeared yet.",
            evidence_keys=["debug_status"],
        ),
        "command-output-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No long command output or log filtering has appeared yet.",
            evidence_keys=["command_output_filter_plan"],
        ),
        "token-optimizer": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="Token optimizer gate is required, but no command output, transcript, or artifact payload has been optimized yet.",
            evidence_keys=["token_optimizer_status"],
        ),
        "memory-state-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No durable project or conversation memory candidate identified yet.",
            evidence_keys=["memory_candidates"],
        ),
        "parallel-orchestration-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No independent parallel write set identified yet.",
            evidence_keys=["parallel_strategy_decision"],
        ),
        "subagent-review-pipeline": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="Subagent task split not selected yet.",
            evidence_keys=["review_status"],
        ),
        "role-execution-audit-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No runtime role DAG execution claimed yet.",
            evidence_keys=["role_execution_audit"],
        ),
        "quality-gates-harness": SkillApplicationStatus(
            status="pending_immediate_execution",
            application_mode="immediate_gate",
            evidence_note="Pending failing-first or quality-gate execution evidence.",
            evidence_keys=["quality_gate_status", "red_green_status"],
        ),
        "review-gate-harness": SkillApplicationStatus(
            status="pending_immediate_execution",
            application_mode="immediate_gate",
            evidence_note="Pending structured review findings or no-findings evidence.",
            evidence_keys=["review_status", "review_findings"],
        ),
        "qa-gate-harness": SkillApplicationStatus(
            status="pending_immediate_execution",
            application_mode="immediate_gate",
            evidence_note="Pending QA, regression, browser/app, or manual verification evidence.",
            evidence_keys=["qa_status", "regression_evidence"],
        ),
        "artifact-render-qa-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No renderable user-facing artifact has been generated yet.",
            evidence_keys=["render_validation"],
        ),
        "deliverable-template-quality-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No user-facing deliverable template quality check has been required yet.",
            evidence_keys=["deliverable_quality"],
        ),
        "traceability-matrix-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No source-to-deliverable traceability matrix has been required yet.",
            evidence_keys=["traceability_matrix"],
        ),
        "verification-before-completion-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No completion, commit, push, PR, or release claim has reached the final verification gate yet.",
            evidence_keys=["verification_status", "completion_claim"],
        ),
        "branch-finishing-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No branch commit, push, PR, merge, or cleanup decision has been reached yet.",
            evidence_keys=["branch_finish_status", "commit_sha"],
        ),
        "compound-engineering-harness": SkillApplicationStatus(
            status="pending_immediate_execution",
            application_mode="immediate_gate",
            evidence_note="Pending learning capture, regression, or no-learning rationale after review.",
            evidence_keys=["compound_handoff"],
        ),
        "workflow-skill-distiller": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No repeated workflow has been selected for skill distillation yet.",
            evidence_keys=["compound_handoff"],
        ),
    }


def _default_token_optimizer_status_reason(status: str) -> str:
    if status == "used":
        return "Token optimizer used; runtime token evidence should be attached by the workflow runtime."
    if status == "passthrough":
        return "Token optimizer not used because content was passed through unchanged for quality."
    if status == "blocked":
        return "Token optimizer not used because optimization was blocked and requires follow-up evidence."
    return "Token optimizer not used because the large-work bundle has not yet produced optimizable output."


def _token_optimizer_skill_status(status: str) -> SkillApplicationStatus:
    if status == "used":
        return SkillApplicationStatus(
            status="applied",
            application_mode="runtime",
            evidence_note="Token optimizer ran and produced runtime token evidence for this workflow.",
            evidence_keys=["token_optimizer_status", "token_usage"],
        )
    if status == "passthrough":
        return SkillApplicationStatus(
            status="applied",
            application_mode="procedural",
            evidence_note="Token optimizer gate was applied and content was passed through unchanged for quality.",
            evidence_keys=["token_optimizer_status", "not_used_reason"],
        )
    if status == "blocked":
        return SkillApplicationStatus(
            status="blocked",
            application_mode="blocked",
            evidence_note="Token optimizer gate was required but could not preserve required facts.",
            evidence_keys=["token_optimizer_status", "blocked_reason"],
            blocked_reason="token_optimizer_blocked",
        )
    return SkillApplicationStatus(
        status="applied",
        application_mode="procedural",
        evidence_note="Token optimizer decision gate was checked; optimization was not needed for this payload.",
        evidence_keys=["token_optimizer_status", "not_used_reason"],
    )
