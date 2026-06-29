from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from src.orchestration.project_markdown import KHProjectMarkdownStore


@dataclass(frozen=True)
class BrainstormOption:
    name: str
    tradeoffs: List[str] = field(default_factory=list)
    recommended: bool = False
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrainstormOption":
        return cls(
            name=str(data.get("name", "")),
            tradeoffs=[str(item) for item in data.get("tradeoffs", [])],
            recommended=bool(data.get("recommended", False)),
            rationale=str(data.get("rationale", "")),
        )


@dataclass(frozen=True)
class BrainstormDecision:
    key: str
    value: str
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrainstormDecision":
        return cls(
            key=str(data.get("key", "")),
            value=str(data.get("value", "")),
            rationale=str(data.get("rationale", "")),
        )


@dataclass(frozen=True)
class BrainstormSession:
    objective: str
    target_user: str = ""
    problem: str = ""
    options: List[BrainstormOption] = field(default_factory=list)
    decisions: List[BrainstormDecision] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    next_skill: str = "architect-pipeline"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "target_user": self.target_user,
            "problem": self.problem,
            "options": [option.to_dict() for option in self.options],
            "decisions": [decision.to_dict() for decision in self.decisions],
            "open_questions": list(self.open_questions),
            "constraints": list(self.constraints),
            "next_skill": self.next_skill,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrainstormSession":
        return cls(
            objective=str(data.get("objective", "")),
            target_user=str(data.get("target_user", "")),
            problem=str(data.get("problem", "")),
            options=[
                BrainstormOption.from_dict(item)
                for item in data.get("options", [])
                if isinstance(item, dict)
            ],
            decisions=[
                BrainstormDecision.from_dict(item)
                for item in data.get("decisions", [])
                if isinstance(item, dict)
            ],
            open_questions=[str(item) for item in data.get("open_questions", [])],
            constraints=[str(item) for item in data.get("constraints", [])],
            next_skill=str(data.get("next_skill", "architect-pipeline")),
            metadata=dict(data.get("metadata", {})),
        )


def validate_brainstorm_session(session: BrainstormSession) -> Dict[str, Any]:
    missing: List[str] = []
    if not session.objective.strip():
        missing.append("objective")
    if not session.target_user.strip():
        missing.append("target_user")
    if not session.problem.strip():
        missing.append("problem")
    if not session.options:
        missing.append("options")
    if session.options and not any(option.recommended for option in session.options):
        missing.append("recommended_option")
    if not session.decisions:
        missing.append("decisions")
    if not session.next_skill.strip():
        missing.append("next_skill")
    for checkpoint in [
        "intent_frame",
        "problem_frame",
        "option_frame",
        "approval_frame",
        "handoff_frame",
        "self_review",
    ]:
        if not session.metadata.get(checkpoint):
            missing.append(f"metadata.{checkpoint}")
    return {
        "valid": not missing,
        "missing": missing,
        "evidence": _brainstorm_evidence(session) if not missing else [],
    }


def build_architect_handoff(session: BrainstormSession) -> Dict[str, Any]:
    validation = validate_brainstorm_session(session)
    return {
        "objective": session.objective,
        "target_user": session.target_user,
        "problem": session.problem,
        "recommended_option": _recommended_option(session).to_dict() if _recommended_option(session) else {},
        "options": [option.to_dict() for option in session.options],
        "decisions": {decision.key: decision.value for decision in session.decisions},
        "decision_rationales": {
            decision.key: decision.rationale for decision in session.decisions if decision.rationale
        },
        "constraints": list(session.constraints),
        "open_questions": list(session.open_questions),
        "next_skill": session.next_skill,
        "status": "ready_for_architect" if validation["valid"] else "blocked",
        "blocked_reason": "" if validation["valid"] else f"missing brainstorm fields: {', '.join(validation['missing'])}",
        "evidence": validation["evidence"],
        "metadata": {
            **dict(session.metadata),
            "source": "brainstorming-harness",
            "handoff_target": session.next_skill,
        },
    }


def render_brainstorm_markdown(session: BrainstormSession) -> str:
    handoff = build_architect_handoff(session)
    recommended = handoff.get("recommended_option", {}) or {}
    return "\n".join([
        f"- Objective: {session.objective}",
        f"- Target user: {session.target_user or 'not specified'}",
        f"- Problem: {session.problem or 'not specified'}",
        f"- Status: {handoff.get('status', '')}",
        f"- Next skill: {session.next_skill}",
        "",
        "## Recommended Option",
        f"- {recommended.get('name', 'none')}",
        f"- Rationale: {recommended.get('rationale', 'none')}",
        "",
        "## Options",
        _option_markdown(session.options),
        "",
        "## Decisions",
        _decision_markdown(session.decisions),
        "",
        "## Constraints",
        _bullet_list(session.constraints),
        "",
        "## Open Questions",
        _bullet_list(session.open_questions),
    ])


def write_brainstorm_markdown_artifacts(
    project_dir: str,
    session: BrainstormSession,
    run_id: str = "",
) -> Dict[str, str]:
    store = KHProjectMarkdownStore(project_dir)
    result = store.write_markdown(
        kind="brainstorm",
        title=f"KH Brainstorm - {session.objective[:80] or 'Session'}",
        body=render_brainstorm_markdown(session),
        slug="brainstorm-handoff",
        run_id=run_id,
        metadata={
            "skill": "brainstorming-harness",
            "next_skill": session.next_skill,
        },
        doc_type="handoffs",
    )
    state_result = store.write_state(
        kind="brainstorm",
        run_id=result["run_id"],
        name="session",
        payload={
            "session": asdict(session),
            "handoff": build_architect_handoff(session),
        },
    )
    return {**result, **state_result}


def _recommended_option(session: BrainstormSession) -> BrainstormOption | None:
    for option in session.options:
        if option.recommended:
            return option
    return None


def _brainstorm_evidence(session: BrainstormSession) -> List[str]:
    evidence = [
        "brainstorm_handoff",
        "decision_log",
        "recommended_option",
        "intent_frame",
        "problem_frame",
        "option_frame",
        "approval_frame",
        "handoff_frame",
        "self_review",
    ]
    if session.open_questions:
        evidence.append("open_questions")
    if session.constraints:
        evidence.append("constraints")
    return evidence


def _option_markdown(options: List[BrainstormOption]) -> str:
    if not options:
        return "- none"
    lines: List[str] = []
    for option in options:
        marker = "recommended" if option.recommended else "option"
        lines.append(f"- {option.name} ({marker})")
        if option.rationale:
            lines.append(f"  - Rationale: {option.rationale}")
        for tradeoff in option.tradeoffs:
            lines.append(f"  - {tradeoff}")
    return "\n".join(lines)


def _decision_markdown(decisions: List[BrainstormDecision]) -> str:
    if not decisions:
        return "- none"
    lines: List[str] = []
    for decision in decisions:
        lines.append(f"- {decision.key}: {decision.value}")
        if decision.rationale:
            lines.append(f"  - Rationale: {decision.rationale}")
    return "\n".join(lines)


def _bullet_list(items: List[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)
