from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class RoleCommandEntrypoint:
    name: str
    aliases: List[str] = field(default_factory=list)
    phase: str = ""
    purpose: str = ""
    roles: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


ROLE_COMMANDS = [
    RoleCommandEntrypoint(
        name="/kh:brainstorm",
        aliases=["brainstorm", "discover", "ideate"],
        phase="plan",
        purpose="Narrow an unclear product, SaaS, feature, or design idea before architecture.",
        roles=["advisor", "product-strategist"],
        skills=["brainstorming-harness", "architect-pipeline"],
        expected_outputs=["brainstorm_handoff", "decision_log", "architect_handoff"],
    ),
    RoleCommandEntrypoint(
        name="/kh:spec",
        aliases=["spec", "design", "architecture"],
        phase="plan",
        purpose="Turn an approved direction into design artifacts and required evidence.",
        roles=["system-architect", "implementation-planner", "qa-verifier"],
        skills=["architect-pipeline", "domain-orchestration-harness", "traceability-matrix-harness"],
        expected_outputs=["design_artifacts", "task_plan", "evidence_plan"],
    ),
    RoleCommandEntrypoint(
        name="/kh:ceo-review",
        aliases=["ceo", "exec-review", "advisor-review"],
        phase="review",
        purpose="Challenge plan scope, priority, risk, and business fit before heavy work.",
        roles=["ceo", "advisor"],
        skills=["orchestration-role-graph", "review-gate-harness"],
        expected_outputs=["decision_record", "risk_questions", "approval_or_changes"],
    ),
    RoleCommandEntrypoint(
        name="/kh:eng-review",
        aliases=["eng-review", "code-review", "implementation-review"],
        phase="review",
        purpose="Review implementation, spec compliance, maintainability, and evidence gaps.",
        roles=["spec-reviewer", "code-quality-reviewer", "security-reviewer"],
        skills=["subagent-review-pipeline", "review-gate-harness", "role-execution-audit-harness"],
        expected_outputs=["review_findings", "fix_plan", "re_review_status"],
    ),
    RoleCommandEntrypoint(
        name="/kh:work",
        aliases=["work", "implement", "execute"],
        phase="work",
        purpose="Run an implementation task through isolated workspace, RED/GREEN, review, and commit.",
        roles=["controller", "implementer", "spec-reviewer", "code-quality-reviewer"],
        skills=[
            "development-lifecycle-harness",
            "worktree-isolation-harness",
            "plan-execution-harness",
            "quality-gates-harness",
            "systematic-debugging-harness",
            "subagent-review-pipeline",
        ],
        expected_outputs=["progress.json", "verification", "commit_sha"],
    ),
    RoleCommandEntrypoint(
        name="/kh:qa",
        aliases=["qa", "verify", "test"],
        phase="review",
        purpose="Collect QA, render, regression, and traceability evidence before completion.",
        roles=["qa-verifier", "security-reviewer"],
        skills=[
            "qa-gate-harness",
            "verification-before-completion-harness",
            "artifact-render-qa-harness",
            "traceability-matrix-harness",
        ],
        expected_outputs=["qa_evidence", "manual_test_mapping", "release_blockers"],
    ),
    RoleCommandEntrypoint(
        name="/kh:ship",
        aliases=["ship", "release", "finish"],
        phase="review",
        purpose="Decide whether the branch is ready to commit, push, PR, or hold.",
        roles=["release-manager", "security-reviewer", "qa-verifier"],
        skills=[
            "health-check-harness",
            "verification-before-completion-harness",
            "branch-finishing-harness",
            "review-gate-harness",
            "qa-gate-harness",
        ],
        expected_outputs=["release_decision", "workspace_strategy", "integration_state"],
    ),
    RoleCommandEntrypoint(
        name="/kh:learn",
        aliases=["learn", "compound", "distill"],
        phase="compound",
        purpose="Convert review outcomes into reusable skill, memory, scenario, or no-learning evidence.",
        roles=["advisor", "controller"],
        skills=["compound-engineering-harness", "workflow-skill-distiller", "memory-state-harness"],
        expected_outputs=["compound_capture", "memory_candidates", "scenario_candidates"],
    ),
    RoleCommandEntrypoint(
        name="/kh:resume",
        aliases=["resume", "restore", "continue"],
        phase="plan",
        purpose="Start the next session from KH project state instead of chat memory alone.",
        roles=["controller"],
        skills=["context-state-harness", "goal-state-harness", "memory-state-harness"],
        expected_outputs=["session_start_context", "latest_progress", "recommended_reads"],
    ),
]


def list_role_command_entrypoints() -> List[Dict[str, Any]]:
    return [command.to_dict() for command in ROLE_COMMANDS]


def resolve_role_command(command: str) -> RoleCommandEntrypoint:
    key = str(command or "").strip().lower()
    if not key:
        raise ValueError("role command is required")
    if not key.startswith("/kh:"):
        key = f"/kh:{key}"

    for entry in ROLE_COMMANDS:
        names = [entry.name.lower(), *[f"/kh:{alias.lower()}" for alias in entry.aliases]]
        if key in names:
            return entry
    raise ValueError(f"unknown KH role command: {command}")


def build_role_command_menu() -> str:
    lines = ["KH Role Commands"]
    for entry in ROLE_COMMANDS:
        roles = ", ".join(entry.roles)
        skills = ", ".join(entry.skills)
        lines.append(f"- {entry.name} [{entry.phase}] {entry.purpose} roles={roles}; skills={skills}")
    return "\n".join(lines)
