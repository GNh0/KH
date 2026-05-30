import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from src.contracts import MemoryRecord
from src.orchestration.compound import (
    CompoundCapture,
    CompoundLearning,
    CompoundMemoryCandidate,
    build_compound_handoff,
)
from src.orchestration.development_progress import (
    DevelopmentRunProgress,
    DevelopmentTaskProgress,
    derive_review_status,
    derive_task_status,
)


@dataclass(frozen=True)
class ProgressCompoundArtifacts:
    capture: CompoundCapture
    handoff: Dict[str, Any]
    memory_candidates: List[MemoryRecord] = field(default_factory=list)
    skill_candidates: List[Dict[str, Any]] = field(default_factory=list)
    scenario_candidates: List[Dict[str, Any]] = field(default_factory=list)
    paths: Dict[str, str] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capture": self.capture.to_dict(),
            "handoff": dict(self.handoff),
            "memory_candidates": [record.to_dict() for record in self.memory_candidates],
            "skill_candidates": [dict(item) for item in self.skill_candidates],
            "scenario_candidates": [dict(item) for item in self.scenario_candidates],
            "paths": dict(self.paths),
            "evidence": list(self.evidence),
        }


def build_progress_compound_capture(progress: DevelopmentRunProgress) -> CompoundCapture:
    learning_items = _learning_items(progress)
    memory_items = _memory_items(progress)
    learnings = [_compound_learning(item, progress) for item in learning_items]
    memory_candidates = [_compound_memory_candidate(item) for item in memory_items]
    system_updates = _string_list(progress.metadata.get("system_updates"))
    regression_checks = _string_list(progress.metadata.get("regression_checks"))

    if learnings and not system_updates:
        system_updates = ["Review generated learning candidates for KH skill, memory, or scenario updates."]
    if learnings and not regression_checks:
        regression_checks = ["Run focused tests for the workflow area touched by this progress run."]

    no_learning = str(progress.metadata.get("no_reusable_learning_rationale", "")).strip()
    if not learnings and not no_learning:
        no_learning = "No explicit reusable learning candidate was recorded in development progress."

    return CompoundCapture(
        objective=progress.objective,
        completed_work=_completed_work(progress),
        review_findings=_review_findings(progress),
        learnings=learnings,
        system_updates=system_updates,
        regression_checks=regression_checks,
        memory_candidates=memory_candidates,
        next_skills=_next_skills(progress, learnings, memory_candidates),
        source_references=_source_references(progress),
        no_reusable_learning_rationale=no_learning if not learnings else "",
        metadata={
            "source": "development_progress",
            "run_id": progress.run_id,
            "task_status": progress.task_status or derive_task_status(progress.tasks),
            "review_status": progress.review_status or derive_review_status(progress.tasks),
            "token_optimizer_status": progress.token_optimizer_status,
            "workspace_strategy": progress.workspace_strategy,
        },
    )


def build_progress_compound_artifacts(progress: DevelopmentRunProgress) -> ProgressCompoundArtifacts:
    capture = build_progress_compound_capture(progress)
    handoff = build_compound_handoff(capture)
    memory_records = [
        _memory_record(candidate, progress)
        for candidate in capture.memory_candidates
    ]
    skill_candidates = _skill_candidates(progress, capture)
    scenario_candidates = _scenario_candidates(progress, capture)
    evidence = [
        "progress_compound_bridge",
        "compound_capture",
        "compound_handoff",
    ]
    if memory_records:
        evidence.append("memory_candidates")
    if skill_candidates:
        evidence.append("skill_candidates")
    if scenario_candidates:
        evidence.append("scenario_candidates")
    return ProgressCompoundArtifacts(
        capture=capture,
        handoff=handoff,
        memory_candidates=memory_records,
        skill_candidates=skill_candidates,
        scenario_candidates=scenario_candidates,
        evidence=evidence,
    )


def write_progress_compound_artifacts(
    project_root: str | Path,
    progress: DevelopmentRunProgress,
) -> ProgressCompoundArtifacts:
    artifacts = build_progress_compound_artifacts(progress)
    project_path = Path(project_root)
    state_dir = project_path / ".kh" / "development" / progress.run_id / "state"
    handoff_dir = project_path / "docs" / "kh" / "handoffs"
    state_dir.mkdir(parents=True, exist_ok=True)
    handoff_dir.mkdir(parents=True, exist_ok=True)

    capture_path = state_dir / "compound_capture.json"
    handoff_path = state_dir / "compound_handoff.json"
    candidates_path = state_dir / "compound_candidates.json"
    markdown_path = handoff_dir / f"{progress.run_id}-compound.md"

    capture_path.write_text(
        json.dumps(artifacts.capture.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    handoff_path.write_text(
        json.dumps(artifacts.handoff, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    candidates_path.write_text(
        json.dumps(
            {
                "memory_candidates": [record.to_dict() for record in artifacts.memory_candidates],
                "skill_candidates": artifacts.skill_candidates,
                "scenario_candidates": artifacts.scenario_candidates,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_compound_handoff_markdown(artifacts), encoding="utf-8")

    return ProgressCompoundArtifacts(
        capture=artifacts.capture,
        handoff=artifacts.handoff,
        memory_candidates=artifacts.memory_candidates,
        skill_candidates=artifacts.skill_candidates,
        scenario_candidates=artifacts.scenario_candidates,
        paths={
            "compound_capture": str(capture_path),
            "compound_handoff": str(handoff_path),
            "compound_candidates": str(candidates_path),
            "compound_markdown": str(markdown_path),
        },
        evidence=list(artifacts.evidence) + ["compound_artifacts_written"],
    )


def render_compound_handoff_markdown(artifacts: ProgressCompoundArtifacts) -> str:
    capture = artifacts.capture
    return "\n".join([
        "# KH Compound Handoff",
        "",
        f"- Objective: {capture.objective}",
        f"- Status: {artifacts.handoff.get('status', '')}",
        f"- Next skills: {', '.join(capture.next_skills) or 'none'}",
        "",
        "## Completed Work",
        _bullet_list(capture.completed_work),
        "",
        "## Review Findings",
        _bullet_list(capture.review_findings),
        "",
        "## Learning Candidates",
        _bullet_list([learning.title for learning in capture.learnings]),
        "",
        "## Memory Candidates",
        _bullet_list([record.content for record in artifacts.memory_candidates]),
        "",
        "## Skill Candidates",
        _bullet_list([candidate.get("title", "") for candidate in artifacts.skill_candidates]),
        "",
        "## Scenario Candidates",
        _bullet_list([candidate.get("title", "") for candidate in artifacts.scenario_candidates]),
        "",
    ])


def _completed_work(progress: DevelopmentRunProgress) -> List[str]:
    completed = []
    for task in progress.tasks:
        if task.status != "complete":
            continue
        suffix = f" ({', '.join(task.changed_files)})" if task.changed_files else ""
        completed.append(f"{task.task_id}: {task.title}{suffix}")
    return completed or [f"Progress run {progress.run_id}: {derive_task_status(progress.tasks)}"]


def _review_findings(progress: DevelopmentRunProgress) -> List[str]:
    findings: List[str] = []
    for task in progress.tasks:
        findings.extend(_task_metadata_strings(task, "review_findings"))
        findings.extend(_task_metadata_strings(task, "findings"))
        if task.spec_review_status == "with_fixes":
            findings.append(f"{task.task_id}: spec review required fixes")
        if task.code_quality_review_status == "with_fixes":
            findings.append(f"{task.task_id}: code-quality review required fixes")
        if task.status == "blocked":
            findings.append(f"{task.task_id}: task blocked")
    findings.extend(_string_list(progress.metadata.get("review_findings")))
    if findings:
        return _dedupe(findings)
    if derive_review_status(progress.tasks) == "passed":
        return ["No blocking review findings recorded."]
    return ["Review status is pending or incomplete."]


def _learning_items(progress: DevelopmentRunProgress) -> List[Dict[str, Any]]:
    items = _dict_items(progress.metadata.get("learning_candidates"))
    for task in progress.tasks:
        items.extend(_dict_items(task.metadata.get("learning_candidates")))
    return items


def _memory_items(progress: DevelopmentRunProgress) -> List[Dict[str, Any]]:
    items = _dict_items(progress.metadata.get("memory_candidates"))
    for task in progress.tasks:
        items.extend(_dict_items(task.metadata.get("memory_candidates")))
    return items


def _compound_learning(item: Dict[str, Any], progress: DevelopmentRunProgress) -> CompoundLearning:
    title = str(item.get("title") or item.get("name") or progress.objective or "Progress learning")
    trigger = str(item.get("trigger") or "Completed development progress run")
    reusable_insight = str(item.get("reusable_insight") or item.get("content") or item.get("insight") or title)
    return CompoundLearning(
        title=title,
        trigger=trigger,
        reusable_insight=reusable_insight,
        evidence=_string_list(item.get("evidence")) or ["development_progress"],
        tags=_string_list(item.get("tags")) or ["progress", "compound"],
        target_update=str(item.get("target_update", "")),
    )


def _compound_memory_candidate(item: Dict[str, Any]) -> CompoundMemoryCandidate:
    return CompoundMemoryCandidate(
        scope=str(item.get("scope", "project")),
        content=str(item.get("content") or item.get("reusable_insight") or item.get("title", "")),
        evidence=_string_list(item.get("evidence")) or ["development_progress"],
        confidence=_confidence_float(item.get("confidence", 0.7)),
        promote_to_global=bool(item.get("promote_to_global", False)),
        metadata=dict(item.get("metadata", {})),
    )


def _memory_record(candidate: CompoundMemoryCandidate, progress: DevelopmentRunProgress) -> MemoryRecord:
    return MemoryRecord(
        record_id=_stable_id("memory", progress.run_id, candidate.scope, candidate.content),
        kind="compound-memory-candidate",
        content=candidate.content,
        scope=candidate.scope,
        source="progress_compound_bridge",
        confidence=_confidence_label(candidate.confidence),
        metadata={
            **dict(candidate.metadata),
            "run_id": progress.run_id,
            "evidence": list(candidate.evidence),
            "promote_to_global": candidate.promote_to_global,
        },
    )


def _skill_candidates(progress: DevelopmentRunProgress, capture: CompoundCapture) -> List[Dict[str, Any]]:
    explicit = _dict_items(progress.metadata.get("skill_candidates"))
    generated = []
    for learning in capture.learnings:
        if learning.target_update and "skill" not in learning.target_update.lower():
            continue
        generated.append({
            "candidate_id": _stable_id("skill", progress.run_id, learning.title),
            "title": learning.title,
            "trigger": learning.trigger,
            "source": "compound_learning",
            "next_skill": "workflow-skill-distiller",
            "evidence": list(learning.evidence),
        })
    return explicit + generated


def _scenario_candidates(progress: DevelopmentRunProgress, capture: CompoundCapture) -> List[Dict[str, Any]]:
    explicit = _dict_items(progress.metadata.get("scenario_candidates"))
    generated = []
    for learning in capture.learnings:
        generated.append({
            "candidate_id": _stable_id("scenario", progress.run_id, learning.title),
            "title": f"Regression: {learning.title}",
            "source": "compound_learning",
            "next_skill": "scenario-evaluation-harness",
            "evidence": list(learning.evidence),
        })
    return explicit + generated


def _next_skills(
    progress: DevelopmentRunProgress,
    learnings: List[CompoundLearning],
    memory_candidates: List[CompoundMemoryCandidate],
) -> List[str]:
    explicit = _string_list(progress.metadata.get("next_skills"))
    if explicit:
        return _dedupe(explicit)
    next_skills: List[str] = []
    if learnings:
        next_skills.extend(["workflow-skill-distiller", "scenario-evaluation-harness"])
    if memory_candidates:
        next_skills.append("memory-state-harness")
    if not next_skills:
        next_skills.append("context-state-harness")
    return _dedupe(next_skills)


def _source_references(progress: DevelopmentRunProgress) -> List[str]:
    references = _string_list(progress.metadata.get("source_references"))
    references.append(f".kh/development/{progress.run_id}/state/progress.json")
    return _dedupe(references)


def _task_metadata_strings(task: DevelopmentTaskProgress, key: str) -> List[str]:
    return _string_list(task.metadata.get(key))


def _dict_items(value: Any) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [dict(value)]
    if isinstance(value, str):
        return [{"title": value, "content": value}]
    items = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict):
            items.append(dict(item))
        elif item:
            items.append({"title": str(item), "content": str(item)})
    return items


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [str(value)] if value else []
    return [str(item) for item in value if str(item).strip()] if isinstance(value, list) else [str(value)]


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def _confidence_float(value: Any) -> float:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "high":
            return 0.9
        if lowered == "medium":
            return 0.7
        if lowered == "low":
            return 0.3
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.7


def _stable_id(*parts: str) -> str:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{parts[0]}-{digest}"


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output


def _bullet_list(items: List[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)
