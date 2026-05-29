from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class CompoundLearning:
    title: str
    trigger: str
    reusable_insight: str
    evidence: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    target_update: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompoundLearning":
        return cls(
            title=str(data.get("title", "")),
            trigger=str(data.get("trigger", "")),
            reusable_insight=str(data.get("reusable_insight", "")),
            evidence=[str(item) for item in data.get("evidence", [])],
            tags=[str(item) for item in data.get("tags", [])],
            target_update=str(data.get("target_update", "")),
        )


@dataclass(frozen=True)
class CompoundMemoryCandidate:
    scope: str
    content: str
    evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5
    promote_to_global: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope": self.scope,
            "content": self.content,
            "evidence": list(self.evidence),
            "confidence": self.confidence,
            "promote_to_global": self.promote_to_global,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompoundMemoryCandidate":
        return cls(
            scope=str(data.get("scope", "")),
            content=str(data.get("content", "")),
            evidence=[str(item) for item in data.get("evidence", [])],
            confidence=float(data.get("confidence", 0.5)),
            promote_to_global=bool(data.get("promote_to_global", False)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class CompoundCapture:
    objective: str
    completed_work: List[str] = field(default_factory=list)
    review_findings: List[str] = field(default_factory=list)
    learnings: List[CompoundLearning] = field(default_factory=list)
    system_updates: List[str] = field(default_factory=list)
    regression_checks: List[str] = field(default_factory=list)
    memory_candidates: List[CompoundMemoryCandidate] = field(default_factory=list)
    next_skills: List[str] = field(default_factory=lambda: ["workflow-skill-distiller"])
    source_references: List[str] = field(default_factory=list)
    no_reusable_learning_rationale: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "completed_work": list(self.completed_work),
            "review_findings": list(self.review_findings),
            "learnings": [learning.to_dict() for learning in self.learnings],
            "system_updates": list(self.system_updates),
            "regression_checks": list(self.regression_checks),
            "memory_candidates": [candidate.to_dict() for candidate in self.memory_candidates],
            "next_skills": list(self.next_skills),
            "source_references": list(self.source_references),
            "no_reusable_learning_rationale": self.no_reusable_learning_rationale,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompoundCapture":
        return cls(
            objective=str(data.get("objective", "")),
            completed_work=[str(item) for item in data.get("completed_work", [])],
            review_findings=[str(item) for item in data.get("review_findings", [])],
            learnings=[
                CompoundLearning.from_dict(item)
                for item in data.get("learnings", [])
                if isinstance(item, dict)
            ],
            system_updates=[str(item) for item in data.get("system_updates", [])],
            regression_checks=[str(item) for item in data.get("regression_checks", [])],
            memory_candidates=[
                CompoundMemoryCandidate.from_dict(item)
                for item in data.get("memory_candidates", [])
                if isinstance(item, dict)
            ],
            next_skills=[str(item) for item in data.get("next_skills", [])],
            source_references=[str(item) for item in data.get("source_references", [])],
            no_reusable_learning_rationale=str(data.get("no_reusable_learning_rationale", "")),
            metadata=dict(data.get("metadata", {})),
        )


def validate_compound_capture(capture: CompoundCapture) -> Dict[str, Any]:
    missing: List[str] = []
    if not capture.objective.strip():
        missing.append("objective")
    if not capture.completed_work:
        missing.append("completed_work")
    if not capture.review_findings:
        missing.append("review_findings")
    if not capture.learnings and not capture.no_reusable_learning_rationale.strip():
        missing.append("learning_or_no_learning_rationale")
    if capture.learnings and not capture.system_updates:
        missing.append("system_updates")
    if capture.learnings and not capture.regression_checks:
        missing.append("regression_checks")
    for candidate in capture.memory_candidates:
        if not candidate.scope.strip():
            missing.append("memory_candidate_scope")
        if candidate.scope == "global" and not candidate.promote_to_global:
            missing.append("explicit_global_memory_promotion")
        if not candidate.content.strip():
            missing.append("memory_candidate_content")
        if not candidate.evidence:
            missing.append("memory_candidate_evidence")
    if not capture.next_skills:
        missing.append("next_skills")
    return {
        "valid": not missing,
        "missing": missing,
        "evidence": _compound_evidence(capture) if not missing else [],
    }


def build_compound_handoff(capture: CompoundCapture) -> Dict[str, Any]:
    validation = validate_compound_capture(capture)
    return {
        "objective": capture.objective,
        "completed_work": list(capture.completed_work),
        "review_findings": list(capture.review_findings),
        "learnings": [learning.to_dict() for learning in capture.learnings],
        "system_updates": list(capture.system_updates),
        "regression_checks": list(capture.regression_checks),
        "memory_candidates": [candidate.to_dict() for candidate in capture.memory_candidates],
        "next_skills": list(capture.next_skills),
        "source_references": list(capture.source_references),
        "no_reusable_learning_rationale": capture.no_reusable_learning_rationale,
        "status": "ready_for_system_update" if validation["valid"] else "blocked",
        "blocked_reason": "" if validation["valid"] else f"missing compound fields: {', '.join(validation['missing'])}",
        "evidence": validation["evidence"],
        "metadata": {
            **dict(capture.metadata),
            "source": "compound-engineering-harness",
            "loop": "Plan -> Work -> Review -> Compound -> Repeat",
            "compound_required": True,
        },
    }


def _compound_evidence(capture: CompoundCapture) -> List[str]:
    evidence = ["compound_capture", "review_summary"]
    if capture.learnings:
        evidence.extend(["learning_candidates", "system_update_plan", "regression_check_plan"])
    if capture.no_reusable_learning_rationale:
        evidence.append("no_reusable_learning_rationale")
    if capture.memory_candidates:
        evidence.append("memory_candidates")
    if capture.source_references:
        evidence.append("benchmark_references")
    return evidence
