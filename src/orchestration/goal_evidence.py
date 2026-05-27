from typing import Any, Dict, Iterable, List

from src.contracts import GoalState


_DEFAULT_EVIDENCE_ALIAS_GROUPS = [
    ["design_doc", "design doc", "design document"],
    ["target_files", "target files", "target file list"],
    ["workflow dispatch completed", "workflow completed", "dispatch completed"],
    ["unit tests passed", "tests passed", "python tests passed", "unittest passed", "pytest passed"],
    ["python unittest passed", "unit tests passed", "tests passed", "unittest passed"],
    ["python compile passed", "compile passed", "python syntax passed"],
    ["browser qa passed", "qa passed", "browser check passed", "browser qa completed"],
]


def normalize_evidence_key(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


def _append_unique(items: List[str], value: Any) -> None:
    normalized = normalize_evidence_key(value)
    if normalized and normalized not in items:
        items.append(normalized)


def collect_workflow_goal_evidence(
    design_doc: str,
    file_list: Iterable[str],
    workflow_completed: bool,
) -> List[str]:
    evidence: List[str] = []
    if design_doc and design_doc.strip():
        evidence.append("design_doc")
    if list(file_list):
        evidence.append("target_files")
    if workflow_completed:
        evidence.append("workflow dispatch completed")
    return evidence


def _append_alias_group(alias_map: Dict[str, List[str]], values: Iterable[Any]) -> None:
    group: List[str] = []
    for value in values:
        _append_unique(group, value)
    for key in group:
        if key not in alias_map:
            alias_map[key] = []
        for candidate in group:
            if candidate not in alias_map[key]:
                alias_map[key].append(candidate)


def _metadata_alias_groups(metadata: Dict[str, Any]) -> List[List[Any]]:
    configured = metadata.get("evidence_aliases", {})
    if not isinstance(configured, dict):
        return []

    groups: List[List[Any]] = []
    for canonical, aliases in configured.items():
        group = [canonical]
        if isinstance(aliases, str):
            group.append(aliases)
        elif isinstance(aliases, Iterable):
            group.extend(aliases)
        elif aliases:
            group.append(aliases)
        groups.append(group)
    return groups


def _evidence_alias_map(metadata: Dict[str, Any]) -> Dict[str, List[str]]:
    alias_map: Dict[str, List[str]] = {}
    for group in _DEFAULT_EVIDENCE_ALIAS_GROUPS:
        _append_alias_group(alias_map, group)
    for group in _metadata_alias_groups(metadata):
        _append_alias_group(alias_map, group)
    return alias_map


def _matching_evidence_key(required: str, evidence_set: set, alias_map: Dict[str, List[str]]) -> str:
    candidates = alias_map.get(required, [required])
    for candidate in candidates:
        if candidate in evidence_set:
            return candidate
    return ""


def evaluate_goal_evidence(
    goal_data: Dict[str, Any],
    workflow_evidence: Iterable[str],
    workflow_success: bool,
) -> Dict[str, Any]:
    if not goal_data:
        return {}

    goal = GoalState.from_dict(goal_data)
    evidence: List[str] = []
    for item in goal.evidence:
        _append_unique(evidence, item)
    for item in workflow_evidence:
        _append_unique(evidence, item)

    required: List[str] = []
    for item in goal.evidence_required:
        _append_unique(required, item)

    evidence_set = set(evidence)
    alias_map = _evidence_alias_map(goal.metadata)
    missing: List[str] = []
    alias_matches: Dict[str, str] = {}
    for item in required:
        matching_key = _matching_evidence_key(item, evidence_set, alias_map)
        if not matching_key:
            missing.append(item)
        elif matching_key != item:
            alias_matches[item] = matching_key

    metadata = dict(goal.metadata)
    metadata["missing_evidence"] = missing
    metadata["evidence_alias_matches"] = alias_matches

    status = "complete"
    blocked_reason = ""
    if not workflow_success:
        status = "blocked"
        blocked_reason = "workflow dispatch failed"
    elif missing:
        status = "blocked"
        blocked_reason = f"missing required evidence: {', '.join(missing)}"

    return GoalState(
        objective=goal.objective,
        status=status,
        success_criteria=list(goal.success_criteria),
        evidence_required=required,
        evidence=evidence,
        progress_notes=list(goal.progress_notes),
        blocked_reason=blocked_reason,
        metadata=metadata,
    ).to_dict()
