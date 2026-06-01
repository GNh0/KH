import argparse
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from src.orchestration.plugin_composition import CapabilityProvider, compose_plugin_route
from src.orchestration.request_classifier import classify_request
from src.orchestration.skill_application import (
    BUNDLE_MEMBER_SKILLS,
    SkillApplicationStatus,
    build_large_work_orchestration_bundle,
    validate_large_work_orchestration_bundle,
)
from src.skills.uaf_skill_catalog import collect_packaged_skills


FRONT_DOOR_SKILLS = [
    "plugin-composition-policy",
    "request-complexity-router",
    "skill-catalog",
]


@dataclass(frozen=True)
class SkillSource:
    source_type: str
    root: str
    skills_dir: str
    exists: bool
    skill_count: int = 0
    version: str = ""
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HostSkillPathCheck:
    path: str
    exists: bool
    status: str
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class KhFrontDoorResult:
    front_door_status: str
    prompt: str
    host: str
    project: str
    skill_source: SkillSource
    cache_candidates: List[SkillSource]
    host_skill_path_checks: List[HostSkillPathCheck]
    classification: Dict[str, Any]
    plugin_route: Dict[str, Any]
    recommended_skills: List[str]
    skill_statuses: Dict[str, Dict[str, Any]]
    required_next_actions: List[str]
    catalog_summary: Dict[str, Any] = field(default_factory=dict)
    large_work_orchestration_bundle: Dict[str, Any] | None = None
    large_work_bundle_validation: Dict[str, Any] | None = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "front_door_status": self.front_door_status,
            "prompt": self.prompt,
            "host": self.host,
            "project": self.project,
            "skill_source": self.skill_source.to_dict(),
            "cache_candidates": [candidate.to_dict() for candidate in self.cache_candidates],
            "host_skill_path_checks": [check.to_dict() for check in self.host_skill_path_checks],
            "classification": dict(self.classification),
            "plugin_route": dict(self.plugin_route),
            "recommended_skills": list(self.recommended_skills),
            "skill_statuses": {name: dict(status) for name, status in self.skill_statuses.items()},
            "required_next_actions": list(self.required_next_actions),
            "catalog_summary": dict(self.catalog_summary),
            "large_work_orchestration_bundle": self.large_work_orchestration_bundle,
            "large_work_bundle_validation": self.large_work_bundle_validation,
            "warnings": list(self.warnings),
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        route_controller = self.plugin_route.get("controller", {})
        runtime_applied_skills = [
            name
            for name, status in self.skill_statuses.items()
            if status.get("status") == "applied" and status.get("application_mode") == "runtime"
        ]
        selected_not_executed_skills = [
            name
            for name, status in self.skill_statuses.items()
            if name not in runtime_applied_skills
        ]
        return {
            "front_door_status": self.front_door_status,
            "host": self.host,
            "project": self.project,
            "skill_source": self.skill_source.to_dict(),
            "stale_or_missing_skill_paths": [
                check.to_dict()
                for check in self.host_skill_path_checks
                if check.status != "ok"
            ],
            "classification": {
                "complexity": self.classification.get("complexity"),
                "domain": self.classification.get("domain"),
                "recommended_execution": self.classification.get("recommended_execution"),
                "confidence": self.classification.get("confidence"),
            },
            "plugin_route": {
                "route": self.plugin_route.get("route"),
                "controller": route_controller.get("provider_id"),
                "assistants": [
                    assistant.get("provider_id")
                    for assistant in self.plugin_route.get("assistants", [])
                ],
                "ask_user": self.plugin_route.get("ask_user"),
            },
            "recommended_skills": list(self.recommended_skills),
            "runtime_applied_skills": runtime_applied_skills,
            "selected_not_executed_skills": selected_not_executed_skills,
            "skill_status_summary": {
                name: {
                    "status": status.get("status"),
                    "application_mode": status.get("application_mode"),
                    "evidence_note": status.get("evidence_note"),
                }
                for name, status in self.skill_statuses.items()
            },
            "required_next_actions": list(self.required_next_actions),
            "warnings": list(self.warnings),
        }


def build_kh_front_door(
    prompt: str,
    project: str | os.PathLike[str] | None = None,
    host: str = "codex",
    providers: Iterable[CapabilityProvider | Dict[str, Any]] | None = None,
    host_skill_paths: Sequence[str] | None = None,
    prefer_cache: bool = False,
) -> KhFrontDoorResult:
    """Run KH intake before any source exploration or implementation work."""
    repo_root = _repo_root()
    project_path = Path(project).expanduser().resolve() if project else Path.cwd().resolve()
    cache_candidates = _discover_cache_sources()
    skill_source = _select_skill_source(repo_root, cache_candidates, prefer_cache=prefer_cache)
    host_path_checks = [_check_host_skill_path(path) for path in host_skill_paths or []]
    warnings = _warnings_from_path_checks(host_path_checks)

    catalog_summary: Dict[str, Any] = {}
    if skill_source.exists:
        catalog = collect_packaged_skills(skill_source.skills_dir)
        catalog_summary = {
            "total_skills_found": catalog.get("total_skills_found", 0),
            "valid": catalog.get("validation", {}).get("success", False),
            "invalid_count": len(catalog.get("validation", {}).get("issues", [])),
            "execution_levels": catalog.get("execution_levels", {}),
        }
        skill_source = SkillSource(
            source_type=skill_source.source_type,
            root=skill_source.root,
            skills_dir=skill_source.skills_dir,
            exists=skill_source.exists,
            skill_count=int(catalog.get("total_skills_found", 0) or 0),
            version=skill_source.version,
            reason=skill_source.reason,
        )
    else:
        warnings.append("No packaged KH skills directory was found.")

    context = {
        "host": host,
        "project": str(project_path),
        "project_markers": _project_markers(project_path),
        "kh_front_door": True,
    }
    classification = classify_request(prompt, context).to_dict()
    provider_snapshot = list(providers) if providers is not None else _default_providers(host)
    plugin_route = compose_plugin_route(prompt, providers=provider_snapshot, context=context).to_dict()
    recommended_skills = _recommended_skills(classification, plugin_route)
    skill_statuses = _front_door_skill_statuses(recommended_skills, classification, skill_source)

    large_work_bundle = None
    large_work_validation = None
    if classification.get("complexity") in {"heavy", "high_risk"}:
        bundle = _build_front_door_bundle(prompt, classification, skill_statuses)
        large_work_bundle = bundle.to_dict()
        large_work_validation = validate_large_work_orchestration_bundle(bundle)

    status = "ok" if skill_source.exists and not any(check.status.startswith("stale") for check in host_path_checks) else "blocked"
    return KhFrontDoorResult(
        front_door_status=status,
        prompt=prompt,
        host=host,
        project=str(project_path),
        skill_source=skill_source,
        cache_candidates=cache_candidates,
        host_skill_path_checks=host_path_checks,
        classification=classification,
        plugin_route=plugin_route,
        recommended_skills=recommended_skills,
        skill_statuses=skill_statuses,
        required_next_actions=_required_next_actions(classification, plugin_route, recommended_skills),
        catalog_summary=catalog_summary,
        large_work_orchestration_bundle=large_work_bundle,
        large_work_bundle_validation=large_work_validation,
        warnings=warnings,
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _select_skill_source(
    repo_root: Path,
    cache_candidates: Sequence[SkillSource],
    *,
    prefer_cache: bool,
) -> SkillSource:
    repo_skills = repo_root / "skills"
    repo_source = SkillSource(
        source_type="repo-local",
        root=str(repo_root),
        skills_dir=str(repo_skills),
        exists=repo_skills.is_dir(),
        reason="current module repository root",
    )
    if repo_source.exists and not prefer_cache:
        return repo_source
    for candidate in cache_candidates:
        if candidate.exists:
            return candidate
    return repo_source


def _discover_cache_sources() -> List[SkillSource]:
    base = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    kh_cache = base / "plugins" / "cache" / "kh-uaf-marketplace" / "kh-uaf"
    if not kh_cache.is_dir():
        return []
    candidates: List[SkillSource] = []
    for child in kh_cache.iterdir():
        if not child.is_dir():
            continue
        skills_dir = child / "skills"
        candidates.append(
            SkillSource(
                source_type="codex-plugin-cache",
                root=str(child),
                skills_dir=str(skills_dir),
                exists=skills_dir.is_dir(),
                version=child.name,
                reason="installed Codex plugin cache",
            )
        )
    return sorted(candidates, key=lambda item: _version_key(item.version), reverse=True)


def _version_key(value: str) -> tuple:
    parts = []
    for part in re.split(r"[^0-9]+", value):
        if part:
            parts.append(int(part))
    return tuple(parts or [0])


def _check_host_skill_path(value: str) -> HostSkillPathCheck:
    path = Path(value).expanduser()
    exists = path.exists()
    if exists:
        return HostSkillPathCheck(path=str(path), exists=True, status="ok")
    lowered = str(path).lower()
    if "kh-uaf-marketplace" in lowered and "kh-uaf" in lowered and "skills" in lowered:
        return HostSkillPathCheck(
            path=str(path),
            exists=False,
            status="stale_kh_cache_path",
            reason="The host supplied a KH skill path that does not exist in the current plugin cache.",
        )
    return HostSkillPathCheck(
        path=str(path),
        exists=False,
        status="missing",
        reason="The host supplied path does not exist.",
    )


def _warnings_from_path_checks(checks: Sequence[HostSkillPathCheck]) -> List[str]:
    warnings: List[str] = []
    for check in checks:
        if check.status == "stale_kh_cache_path":
            warnings.append(
                "A host skill path points to a stale KH cache. Resolve repo-local skills or the latest kh-uaf cache before continuing."
            )
        elif check.status == "missing":
            warnings.append(f"Host supplied missing skill path: {check.path}")
    return warnings


def _project_markers(project_path: Path) -> List[str]:
    markers = []
    for marker in [".kh", "docs/kh", ".superpowers", "docs/superpowers", ".git"]:
        if (project_path / marker).exists():
            markers.append(marker)
    return markers


def _default_providers(host: str) -> List[Dict[str, Any]]:
    return [
        {
            "provider_id": "kh",
            "display_name": "KH UAF",
            "aliases": ["kh", "kh uaf", "kh plugin", "kh-uaf"],
            "capabilities": [
                "workflow_control",
                "memory_goal_resume",
                "domain_orchestration",
                "planning_methodology",
                "tdd_review",
                "workspace_isolation",
                "completion_verification",
                "branch_finishing",
                "systematic_debugging",
            ],
            "metadata": {"host": host, "source": "kh_front_door"},
        }
    ]


def _recommended_skills(classification: Dict[str, Any], plugin_route: Dict[str, Any]) -> List[str]:
    skills: List[str] = []
    skills.extend(FRONT_DOOR_SKILLS)
    skills.extend(str(item) for item in classification.get("recommended_skills", []))
    skills.extend(str(item) for item in classification.get("required_harnesses", []))
    skills.extend(str(item) for item in classification.get("cross_cutting", []))
    controller = plugin_route.get("controller", {}) or {}
    if controller.get("provider_id") == "kh":
        skills.append("workflow-usability-harness")
    if classification.get("complexity") in {"heavy", "high_risk"}:
        skills.extend(
            [
                "host-agent-orchestration",
                "goal-state-harness",
                "development-lifecycle-harness",
                "worktree-isolation-harness",
                "plan-execution-harness",
                "quality-gates-harness",
                "review-gate-harness",
                "qa-gate-harness",
                "verification-before-completion-harness",
                "role-execution-audit-harness",
            ]
        )
    if "source_summary" in classification.get("evidence_required", []):
        skills.append("context-state-harness")
    return _dedupe(skills)


def _front_door_skill_statuses(
    recommended_skills: Sequence[str],
    classification: Dict[str, Any],
    skill_source: SkillSource,
) -> Dict[str, Dict[str, Any]]:
    statuses: Dict[str, Dict[str, Any]] = {}
    for skill in recommended_skills:
        if skill == "plugin-composition-policy":
            statuses[skill] = _status(
                "applied",
                "runtime",
                "compose_plugin_route selected the route before provider-specific workflow rules.",
                ["plugin_route"],
            )
        elif skill == "request-complexity-router":
            statuses[skill] = _status(
                "applied",
                "runtime",
                "classify_request selected request depth before source exploration.",
                ["classification"],
            )
        elif skill == "skill-catalog":
            statuses[skill] = _status(
                "applied" if skill_source.exists else "blocked",
                "runtime" if skill_source.exists else "blocked",
                "Resolved packaged KH skills from the current repository or plugin cache.",
                ["skill_source", "catalog_summary"],
                blocked_reason="" if skill_source.exists else "missing_packaged_skills",
            )
        elif skill == "token-optimizer":
            if (
                "token-optimizer" in classification.get("cross_cutting", [])
                or "token_optimizer_status" in classification.get("evidence_required", [])
                or "token_optimization" in classification.get("evidence_required", [])
            ):
                statuses[skill] = _status(
                    "skipped_with_rationale",
                    "considered",
                    "Selected as a token decision gate; front-door records the decision but does not compress source text.",
                    ["token_optimizer_status"],
                )
            else:
                statuses[skill] = _status(
                    "considered_not_needed",
                    "considered",
                    "No large/log-like content has crossed the token optimization threshold in the front-door prompt.",
                    ["token_optimizer_status"],
                )
        else:
            statuses[skill] = _status(
                "skipped_with_rationale",
                "procedural",
                "Selected for the workflow after front-door routing; this command records routing and does not claim runtime execution.",
                ["required_next_actions"],
            )
    return statuses


def _status(
    status: str,
    application_mode: str,
    evidence_note: str,
    evidence_keys: Sequence[str],
    blocked_reason: str = "",
) -> Dict[str, Any]:
    return SkillApplicationStatus(
        status=status,
        application_mode=application_mode,
        evidence_note=evidence_note,
        evidence_keys=list(evidence_keys),
        blocked_reason=blocked_reason,
    ).to_dict()


def _build_front_door_bundle(
    prompt: str,
    classification: Dict[str, Any],
    front_door_statuses: Dict[str, Dict[str, Any]],
):
    overrides: Dict[str, Dict[str, Any]] = {}
    for skill in BUNDLE_MEMBER_SKILLS:
        if skill in front_door_statuses:
            overrides[skill] = front_door_statuses[skill]
        else:
            overrides[skill] = _status(
                "skipped_with_rationale",
                "procedural",
                "Large-work skill selected for workflow execution after front-door routing; not executed by the front-door command.",
                ["large_work_orchestration_bundle"],
            )
    return build_large_work_orchestration_bundle(
        objective=prompt,
        workspace_strategy="front-door-only; select worktree strategy before edits",
        token_optimizer_status=front_door_statuses.get("token-optimizer", {}).get("status", "considered_not_needed"),
        overrides=overrides,
        parallel_strategy_decision="front-door-only; prove independent write sets before parallel execution",
        metadata={
            "front_door": True,
            "classification": {
                "complexity": classification.get("complexity"),
                "domain": classification.get("domain"),
                "recommended_execution": classification.get("recommended_execution"),
            },
        },
    )


def _required_next_actions(
    classification: Dict[str, Any],
    plugin_route: Dict[str, Any],
    recommended_skills: Sequence[str],
) -> List[str]:
    actions = [
        "Read only the selected skills needed for the next step through `python -m src.skills.uaf_skill_catalog --read <skill>`.",
        "Do not claim runtime skill application unless a module, gate, artifact, or explicit passthrough evidence was produced.",
    ]
    if plugin_route.get("ask_user"):
        actions.append("Ask a short clarification before source exploration or implementation.")
    if classification.get("complexity") in {"heavy", "high_risk"}:
        actions.extend(
            [
                "Create or update GoalState before implementation.",
                "Record workspace_strategy before edits.",
                "Run verification-before-completion before any done, commit, push, or handoff claim.",
            ]
        )
    for skill in recommended_skills:
        if skill in FRONT_DOOR_SKILLS or skill == "token-optimizer":
            continue
        actions.append(f"If needed next, apply `{skill}` and record concrete evidence or skipped/blocked rationale.")
    return _dedupe(actions)


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run KH front-door routing before source work.")
    parser.add_argument("--prompt", required=True, help="User request text.")
    parser.add_argument("--project", default="", help="Target project path. Defaults to current directory.")
    parser.add_argument("--host", default="codex", help="Host runtime label such as codex, antigravity, or local.")
    parser.add_argument(
        "--host-skill-path",
        action="append",
        default=[],
        help="Host-provided KH skill path to validate. Repeat for multiple paths.",
    )
    parser.add_argument("--providers-json", default="", help="Optional JSON provider snapshot.")
    parser.add_argument("--prefer-cache", action="store_true", help="Prefer the latest installed kh-uaf cache over repo-local skills.")
    parser.add_argument("--summary", action="store_true", help="Print a compact front-door summary.")
    args = parser.parse_args()

    providers = json.loads(args.providers_json) if args.providers_json else None
    result = build_kh_front_door(
        prompt=args.prompt,
        project=args.project or None,
        host=args.host,
        providers=providers,
        host_skill_paths=args.host_skill_path,
        prefer_cache=args.prefer_cache,
    )
    payload = result.to_summary_dict() if args.summary else result.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.front_door_status == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
