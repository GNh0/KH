from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


BUNDLE_STATUS_VALUES = {
    "applied",
    "considered_not_needed",
    "skipped_with_rationale",
    "blocked",
}
BUNDLE_APPLICATION_MODES = {
    "runtime",
    "procedural",
    "considered",
    "blocked",
}
BUNDLE_MEMBER_SKILLS = [
    "request-complexity-router",
    "host-agent-orchestration",
    "goal-state-harness",
    "development-lifecycle-harness",
    "worktree-isolation-harness",
    "plan-execution-harness",
    "systematic-debugging-harness",
    "token-optimizer",
    "memory-state-harness",
    "parallel-orchestration-harness",
    "subagent-review-pipeline",
    "role-execution-audit-harness",
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
            "parallel_strategy_decision": self.parallel_strategy_decision,
            "memory_candidates": [dict(item) for item in self.memory_candidates],
            "compound_handoff": dict(self.compound_handoff),
            "metadata": dict(self.metadata),
        }


def build_large_work_orchestration_bundle(
    objective: str,
    workspace_strategy: str,
    token_optimizer_status: str,
    overrides: Dict[str, Dict[str, Any]] | None = None,
    parallel_strategy_decision: str = "sequential with rationale until independent write sets are proven",
    memory_candidates: List[Dict[str, Any]] | None = None,
    compound_handoff: Dict[str, Any] | None = None,
    metadata: Dict[str, Any] | None = None,
) -> LargeWorkOrchestrationBundle:
    overrides = overrides or {}
    skill_statuses = _default_skill_statuses()
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
        parallel_strategy_decision=parallel_strategy_decision,
        memory_candidates=memory_candidates or [],
        compound_handoff=compound_handoff
        or {
            "status": "pending",
            "rationale": "Evaluate reusable learning after review.",
        },
        metadata=metadata or {},
    )


def validate_large_work_orchestration_bundle(bundle: LargeWorkOrchestrationBundle) -> Dict[str, Any]:
    missing: List[str] = []
    if not bundle.objective.strip():
        missing.append("objective")
    if not bundle.workspace_strategy.strip():
        missing.append("workspace_strategy")
    if not bundle.token_optimizer_status.strip():
        missing.append("token_optimizer_status")
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
            "memory_candidates",
            "compound_handoff",
        ]
    return {
        "valid": not missing,
        "missing": missing,
        "evidence": evidence,
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
            status="applied",
            application_mode="procedural",
            evidence_note="Resolved host runtime, tool boundaries, and whether subagents can be used.",
            evidence_keys=["host_runtime_decision"],
        ),
        "goal-state-harness": SkillApplicationStatus(
            status="applied",
            application_mode="procedural",
            evidence_note="Created or refreshed objective, success criteria, and missing evidence state.",
            evidence_keys=["goal_state"],
        ),
        "development-lifecycle-harness": SkillApplicationStatus(
            status="applied",
            application_mode="procedural",
            evidence_note="Applied plan, work, review, verification, and integration loop.",
            evidence_keys=["task_status", "review_status"],
        ),
        "worktree-isolation-harness": SkillApplicationStatus(
            status="applied",
            application_mode="procedural",
            evidence_note="Selected workspace strategy before implementation or recorded the in-place exception.",
            evidence_keys=["workspace_strategy"],
        ),
        "plan-execution-harness": SkillApplicationStatus(
            status="applied",
            application_mode="procedural",
            evidence_note="Tracked task-plan execution through progress state, task status, and next-task handoff.",
            evidence_keys=["progress.json", "task_status", "next_task"],
        ),
        "systematic-debugging-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No unexpected failure or bug diagnosis loop has appeared yet.",
            evidence_keys=["debug_status"],
        ),
        "token-optimizer": SkillApplicationStatus(
            status="applied",
            application_mode="runtime",
            evidence_note="Used, blocked, passed through, or explicitly skipped context optimization.",
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
        "verification-before-completion-harness": SkillApplicationStatus(
            status="applied",
            application_mode="procedural",
            evidence_note="Requires fresh verification evidence before completion, commit, push, PR, or release claims.",
            evidence_keys=["verification_status", "completion_claim"],
        ),
        "branch-finishing-harness": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No branch commit, push, PR, merge, or cleanup decision has been reached yet.",
            evidence_keys=["branch_finish_status", "commit_sha"],
        ),
        "compound-engineering-harness": SkillApplicationStatus(
            status="applied",
            application_mode="procedural",
            evidence_note="Will produce learning capture, memory candidate, regression, or no-learning rationale after review.",
            evidence_keys=["compound_handoff"],
        ),
        "workflow-skill-distiller": SkillApplicationStatus(
            status="considered_not_needed",
            application_mode="considered",
            evidence_note="No repeated workflow has been selected for skill distillation yet.",
            evidence_keys=["compound_handoff"],
        ),
    }
