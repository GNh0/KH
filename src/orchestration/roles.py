from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


STAGE_ORDER: Tuple[str, ...] = (
    "executive",
    "advisory",
    "architecture",
    "planning",
    "implementation",
    "review",
    "release",
)


@dataclass(frozen=True)
class RoleProfile:
    name: str
    title: str
    stage: str
    purpose: str
    responsibilities: Tuple[str, ...]
    inputs: Tuple[str, ...]
    outputs: Tuple[str, ...]
    blocks_on: Tuple[str, ...] = field(default_factory=tuple)
    fanout_safe: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "stage": self.stage,
            "purpose": self.purpose,
            "responsibilities": list(self.responsibilities),
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "blocks_on": list(self.blocks_on),
            "fanout_safe": self.fanout_safe,
        }


def default_role_profiles() -> Tuple[RoleProfile, ...]:
    return (
        RoleProfile(
            name="ceo",
            title="CEO / Executive Sponsor",
            stage="executive",
            purpose="Own final business intent, priority, success criteria, and tradeoff approval.",
            responsibilities=(
                "Define the business outcome and non-negotiable constraints.",
                "Approve scope tradeoffs before architecture and implementation proceed.",
            ),
            inputs=("user requirement", "business constraints"),
            outputs=("approved objective", "success criteria", "priority order"),
        ),
        RoleProfile(
            name="advisor",
            title="Advisor Council",
            stage="advisory",
            purpose="Surface cross-domain risks, alternatives, and blind spots before design locks in.",
            responsibilities=(
                "Challenge assumptions from product, technical, operations, and user perspectives.",
                "Record risks that need mitigation or explicit acceptance.",
            ),
            inputs=("approved objective", "success criteria"),
            outputs=("risk register", "recommended constraints", "alternative options"),
            blocks_on=("ceo",),
        ),
        RoleProfile(
            name="product-strategist",
            title="Product Strategist",
            stage="advisory",
            purpose="Translate business intent into user outcomes, feature boundaries, and acceptance criteria.",
            responsibilities=(
                "Define user-facing behavior and scope boundaries.",
                "Prepare acceptance criteria that reviewers can check later.",
            ),
            inputs=("approved objective", "risk register"),
            outputs=("feature scope", "acceptance criteria"),
            blocks_on=("ceo", "advisor"),
        ),
        RoleProfile(
            name="system-architect",
            title="Development Architect",
            stage="architecture",
            purpose="Create the technical architecture, module boundaries, and implementation constraints.",
            responsibilities=(
                "Select architecture and design patterns that match the requested scale.",
                "Identify files, contracts, and integration boundaries for implementation.",
            ),
            inputs=("feature scope", "acceptance criteria", "risk register"),
            outputs=("design document", "target files", "technical constraints"),
            blocks_on=("product-strategist",),
        ),
        RoleProfile(
            name="implementation-planner",
            title="Implementation Planner",
            stage="planning",
            purpose="Break approved design into bounded tasks with test and verification steps.",
            responsibilities=(
                "Split work into independent tasks suitable for controller dispatch.",
                "Attach expected tests, artifacts, and completion evidence to each task.",
            ),
            inputs=("design document", "target files", "technical constraints"),
            outputs=("task plan", "test plan", "dispatch units"),
            blocks_on=("system-architect",),
        ),
        RoleProfile(
            name="controller",
            title="Controller / Orchestrator",
            stage="implementation",
            purpose="Coordinate role execution, shared state, retries, aggregation, and final reporting.",
            responsibilities=(
                "Dispatch implementers only when task inputs and dependencies are ready.",
                "Aggregate partial results, reviewer findings, blocked states, and audit metadata.",
            ),
            inputs=("task plan", "dispatch units", "role graph"),
            outputs=("dispatch records", "aggregated results", "blocked items"),
            blocks_on=("implementation-planner",),
        ),
        RoleProfile(
            name="implementer",
            title="Implementer",
            stage="implementation",
            purpose="Perform one bounded implementation task and report exact changes and checks.",
            responsibilities=(
                "Modify only the files required for the assigned task.",
                "Run the task-specific checks and report DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, or BLOCKED.",
            ),
            inputs=("dispatch unit", "design document", "acceptance criteria"),
            outputs=("changed files", "task result", "verification evidence"),
            blocks_on=("controller",),
            fanout_safe=True,
        ),
        RoleProfile(
            name="spec-reviewer",
            title="Spec Reviewer",
            stage="review",
            purpose="Verify that implementation matches the assigned specification and user constraints.",
            responsibilities=(
                "Find missing requested behavior and unrequested scope expansion.",
                "Send spec gaps back to the controller before quality review.",
            ),
            inputs=("task result", "acceptance criteria", "design document"),
            outputs=("spec findings", "spec approval"),
            blocks_on=("implementer",),
        ),
        RoleProfile(
            name="code-quality-reviewer",
            title="Code Quality Reviewer",
            stage="review",
            purpose="Review maintainability, integration risk, readability, and local pattern fit after spec pass.",
            responsibilities=(
                "Review code quality only after spec compliance is acceptable.",
                "Identify maintainability, integration, and test coverage issues by severity.",
            ),
            inputs=("spec approval", "changed files", "verification evidence"),
            outputs=("quality findings", "quality approval"),
            blocks_on=("spec-reviewer",),
        ),
        RoleProfile(
            name="qa-verifier",
            title="QA Verifier",
            stage="review",
            purpose="Run or inspect final verification evidence before completion is reported.",
            responsibilities=(
                "Map requirements to fresh verification evidence.",
                "Reject completion claims when evidence is missing or stale.",
            ),
            inputs=("quality approval", "test plan", "verification evidence"),
            outputs=("verification summary", "residual risks"),
            blocks_on=("code-quality-reviewer",),
        ),
        RoleProfile(
            name="security-reviewer",
            title="Security Reviewer",
            stage="review",
            purpose="Review tool permissions, file writes, command execution, credentials, and sandbox boundaries.",
            responsibilities=(
                "Check whether new execution paths respect permission and sandbox policy.",
                "Flag destructive, network, or credential-bearing behavior for explicit handling.",
            ),
            inputs=("quality approval", "changed files", "role graph"),
            outputs=("security findings", "policy approval"),
            blocks_on=("code-quality-reviewer",),
        ),
        RoleProfile(
            name="release-manager",
            title="Release Manager",
            stage="release",
            purpose="Package final status, commit or PR readiness, changelog notes, and integration decision.",
            responsibilities=(
                "Ensure review and verification gates are complete before release action.",
                "Summarize shipped behavior, evidence, and follow-up risks.",
            ),
            inputs=("verification summary", "security findings", "aggregated results"),
            outputs=("release summary", "integration action"),
            blocks_on=("qa-verifier", "security-reviewer"),
        ),
    )


def default_role_graph() -> Dict[str, Any]:
    profiles = default_role_profiles()
    stages = {stage: [] for stage in STAGE_ORDER}
    for profile in profiles:
        stages[profile.stage].append(profile.name)

    return {
        "stage_order": list(STAGE_ORDER),
        "stages": stages,
        "dependencies": {profile.name: list(profile.blocks_on) for profile in profiles},
        "roles": [profile.to_dict() for profile in profiles],
    }


def build_default_role_metadata() -> Dict[str, Any]:
    profiles = default_role_profiles()
    return {
        "orchestration_roles": [profile.name for profile in profiles],
        "role_count": len(profiles),
        "role_graph": default_role_graph(),
    }


def format_role_brief(profiles: Optional[Tuple[RoleProfile, ...]] = None) -> str:
    selected_profiles = profiles or default_role_profiles()
    lines = [
        "| Stage | Role | Purpose |",
        "|-------|------|---------|",
    ]
    for profile in selected_profiles:
        lines.append(f"| {profile.stage} | `{profile.name}` | {profile.purpose} |")
    return "\n".join(lines)


def build_role_gate_results(task_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    failed_tasks = [
        result
        for result in task_results
        if result.get("status") != "success"
    ]

    if failed_tasks:
        blocked_reason = f"{len(failed_tasks)} implementer task(s) failed"
        return [
            {
                "role": "spec-reviewer",
                "status": "failed",
                "message": blocked_reason,
                "blocks_on": ["implementer"],
            },
            {
                "role": "code-quality-reviewer",
                "status": "blocked",
                "message": "spec review did not pass",
                "blocks_on": ["spec-reviewer"],
            },
            {
                "role": "qa-verifier",
                "status": "blocked",
                "message": "quality review did not pass",
                "blocks_on": ["code-quality-reviewer"],
            },
            {
                "role": "security-reviewer",
                "status": "blocked",
                "message": "quality review did not pass",
                "blocks_on": ["code-quality-reviewer"],
            },
            {
                "role": "release-manager",
                "status": "blocked",
                "message": "verification and security gates did not pass",
                "blocks_on": ["qa-verifier", "security-reviewer"],
            },
        ]

    return [
        {
            "role": "spec-reviewer",
            "status": "passed",
            "message": "all implementer tasks reported success",
            "blocks_on": ["implementer"],
        },
        {
            "role": "code-quality-reviewer",
            "status": "passed",
            "message": "no failed task output to block quality review",
            "blocks_on": ["spec-reviewer"],
        },
        {
            "role": "qa-verifier",
            "status": "passed",
            "message": "all task evidence is successful",
            "blocks_on": ["code-quality-reviewer"],
        },
        {
            "role": "security-reviewer",
            "status": "passed",
            "message": "no task-level security blocker reported",
            "blocks_on": ["code-quality-reviewer"],
        },
        {
            "role": "release-manager",
            "status": "passed",
            "message": "review, verification, and security gates passed",
            "blocks_on": ["qa-verifier", "security-reviewer"],
        },
    ]
