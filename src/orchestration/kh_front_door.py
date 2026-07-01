import argparse
import json
import os
import re
import sys
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
    "always-on-front-door",
    "automatic-intake-harness",
    "plugin-composition-policy",
    "request-complexity-router",
    "skill-catalog",
    "token-optimizer",
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
    immediate_next_skills: List[str]
    skill_statuses: Dict[str, Dict[str, Any]]
    execution_gate: Dict[str, Any]
    execution_authorization: Dict[str, Any]
    required_next_actions: List[str]
    catalog_summary: Dict[str, Any] = field(default_factory=dict)
    large_work_orchestration_bundle: Dict[str, Any] | None = None
    large_work_bundle_validation: Dict[str, Any] | None = None
    token_optimizer_decision: Dict[str, Any] = field(default_factory=dict)
    memory_policy: Dict[str, Any] = field(default_factory=dict)
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
            "immediate_next_skills": list(self.immediate_next_skills),
            "skill_statuses": {name: dict(status) for name, status in self.skill_statuses.items()},
            "execution_gate": dict(self.execution_gate),
            "execution_authorization": dict(self.execution_authorization),
            "required_next_actions": list(self.required_next_actions),
            "catalog_summary": dict(self.catalog_summary),
            "large_work_orchestration_bundle": self.large_work_orchestration_bundle,
            "large_work_bundle_validation": self.large_work_bundle_validation,
            "token_optimizer_decision": dict(self.token_optimizer_decision),
            "token_optimizer_lifecycle": _token_optimizer_lifecycle_summary(self.token_optimizer_decision),
            "memory_policy": dict(self.memory_policy),
            "warnings": list(self.warnings),
        }

    def to_summary_dict(self) -> Dict[str, Any]:
        route_controller = self.plugin_route.get("controller", {})
        runtime_applied_skills = [
            name
            for name, status in self.skill_statuses.items()
            if status.get("status") == "applied" and status.get("application_mode") == "runtime"
        ]
        immediate_next = set(self.immediate_next_skills)
        selected_not_executed_skills = [
            name
            for name, status in self.skill_statuses.items()
            if name not in runtime_applied_skills and name not in immediate_next
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
            "immediate_next_skills": list(self.immediate_next_skills),
            "execution_gate": dict(self.execution_gate),
            "execution_authorization": dict(self.execution_authorization),
            "runtime_applied_skills": runtime_applied_skills,
            "selected_not_executed_skills": selected_not_executed_skills,
            "token_optimizer_decision": dict(self.token_optimizer_decision),
            "token_optimizer_gate": _token_optimizer_gate_summary(self.token_optimizer_decision),
            "token_optimizer_lifecycle": _token_optimizer_lifecycle_summary(self.token_optimizer_decision),
            "memory_policy": dict(self.memory_policy),
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

    def to_compact_summary_dict(self) -> Dict[str, Any]:
        route_controller = self.plugin_route.get("controller", {})
        runtime_applied_skills = [
            name
            for name, status in self.skill_statuses.items()
            if status.get("status") == "applied" and status.get("application_mode") == "runtime"
        ]
        immediate_next = set(self.immediate_next_skills)
        selected_not_executed_skills = [
            name
            for name, status in self.skill_statuses.items()
            if name not in runtime_applied_skills and name not in immediate_next
        ]
        return {
            "summary_mode": "compact",
            "front_door_status": self.front_door_status,
            "host": self.host,
            "project": self.project,
            "skill_source": _compact_skill_source(self.skill_source),
            "stale_or_missing_skill_paths": [
                _compact_host_skill_path_check(check)
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
            "immediate_next_skills": list(self.immediate_next_skills),
            "runtime_applied_skills": runtime_applied_skills,
            "selected_not_executed_skills": selected_not_executed_skills,
            "execution_gate": _compact_execution_gate(self.execution_gate),
            "execution_authorization": _compact_execution_authorization(self.execution_authorization),
            "required_next_actions": _compact_required_next_actions(
                self.required_next_actions,
                self.execution_authorization,
                self.immediate_next_skills,
                self.plugin_route,
            ),
            "required_next_actions_count": len(self.required_next_actions),
            "token_optimizer_decision": _compact_token_optimizer_decision(self.token_optimizer_decision),
            "token_optimizer_gate": _compact_token_optimizer_gate_summary(self.token_optimizer_decision),
            "token_optimizer_lifecycle": _compact_token_optimizer_lifecycle_summary(self.token_optimizer_decision),
            "memory_policy": _compact_memory_policy(self.memory_policy),
            "skill_status_summary": _compact_skill_status_summary(self.skill_statuses),
            "warnings": list(self.warnings),
        }


def build_kh_front_door(
    prompt: str,
    project: str | os.PathLike[str] | None = None,
    host: str = "codex",
    providers: Iterable[CapabilityProvider | Dict[str, Any]] | None = None,
    host_skill_paths: Sequence[str] | None = None,
    prefer_cache: bool = False,
    request_context: Dict[str, Any] | None = None,
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

    context = _merge_front_door_context(
        request_context,
        {
            "host": host,
            "project": str(project_path),
            "project_markers": _project_markers(project_path),
            "kh_front_door": True,
        },
    )
    classification = classify_request(prompt, context).to_dict()
    provider_snapshot = list(providers) if providers is not None else _default_providers(host)
    plugin_route = compose_plugin_route(prompt, providers=provider_snapshot, context=context).to_dict()
    recommended_skills = _recommended_skills(classification, plugin_route)
    skill_statuses = _front_door_skill_statuses(recommended_skills, classification, skill_source)
    token_optimizer_decision = _front_door_token_optimizer_decision(prompt, classification)
    skill_statuses = _apply_front_door_token_optimizer_gate(skill_statuses, token_optimizer_decision)
    execution_gate = _execution_gate(classification, plugin_route, recommended_skills)
    immediate_next_skills = _immediate_next_skills(classification, plugin_route, recommended_skills, execution_gate)
    skill_statuses = _mark_immediate_next_skill_statuses(skill_statuses, immediate_next_skills)
    required_next_actions = _required_next_actions(
        classification,
        plugin_route,
        recommended_skills,
        execution_gate,
        immediate_next_skills,
    )
    execution_authorization = _execution_authorization(
        execution_gate,
        immediate_next_skills,
        required_next_actions,
    )

    large_work_bundle = None
    large_work_validation = None
    if classification.get("complexity") in {"heavy", "high_risk"}:
        bundle = _build_front_door_bundle(prompt, classification, skill_statuses)
        large_work_bundle = bundle.to_dict()
        large_work_validation = validate_large_work_orchestration_bundle(bundle)

    if skill_source.exists and any(check.status == "stale_kh_cache_path" for check in host_path_checks):
        warnings.append(
            f"Resolved KH skills from {skill_source.source_type} at {skill_source.root} despite stale host skill path."
        )

    status = _front_door_status(skill_source)
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
        immediate_next_skills=immediate_next_skills,
        skill_statuses=skill_statuses,
        execution_gate=execution_gate,
        execution_authorization=execution_authorization,
        required_next_actions=required_next_actions,
        catalog_summary=catalog_summary,
        large_work_orchestration_bundle=large_work_bundle,
        large_work_bundle_validation=large_work_validation,
        token_optimizer_decision=token_optimizer_decision,
        memory_policy=_memory_policy(project_path, host),
        warnings=warnings,
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _memory_policy(project_path: Path, host: str) -> Dict[str, Any]:
    return {
        "scope": "project_chat",
        "project": str(project_path),
        "host": host,
        "global_codex_memory_allowed": False,
        "host_global_memory_write_allowed": False,
        "host_memory_lookup_before_front_door_allowed": False,
        "cross_scope_import_requires_explicit_user_approval": True,
        "subagent_scope": "child_chat_isolated_by_default",
    }


def _select_skill_source(
    repo_root: Path,
    cache_candidates: Sequence[SkillSource],
    *,
    prefer_cache: bool,
) -> SkillSource:
    repo_skills = repo_root / "skills"
    source_type, version, reason = _source_identity_for_root(repo_root)
    repo_source = SkillSource(
        source_type=source_type,
        root=str(repo_root),
        skills_dir=str(repo_skills),
        exists=repo_skills.is_dir(),
        version=version,
        reason=reason,
    )
    if repo_source.exists and not prefer_cache:
        return repo_source
    for candidate in cache_candidates:
        if candidate.exists:
            return candidate
    return repo_source


def _source_identity_for_root(repo_root: Path) -> tuple[str, str, str]:
    parts = list(repo_root.parts)
    lowered = [part.lower() for part in parts]
    for index in range(len(lowered) - 4):
        if lowered[index : index + 4] == ["plugins", "cache", "kh-uaf-marketplace", "kh-uaf"]:
            version = parts[index + 4] if index + 4 < len(parts) else repo_root.name
            return "codex-plugin-cache", version, "installed Codex plugin cache"
    return "repo-local", "", "current module repository root"


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


def _front_door_status(skill_source: SkillSource) -> str:
    if not skill_source.exists:
        return "blocked"
    return "ok"


def _project_markers(project_path: Path) -> List[str]:
    markers = []
    for marker in [".kh", "docs/kh", ".superpowers", "docs/superpowers", ".git"]:
        if (project_path / marker).exists():
            markers.append(marker)
    return markers


def _merge_front_door_context(
    request_context: Dict[str, Any] | None,
    base_context: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(request_context or {})
    base_markers = [str(marker) for marker in base_context.get("project_markers", [])]
    supplied_markers = [str(marker) for marker in merged.get("project_markers", [])]
    markers = _dedupe([*base_markers, *supplied_markers])
    merged.update(base_context)
    merged["project_markers"] = markers
    return merged


def _default_providers(host: str) -> List[Dict[str, Any]]:
    providers = [
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
    providers.extend(_host_local_skill_providers(host))
    return providers


def _host_local_skill_providers(host: str) -> List[Dict[str, Any]]:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    skills_root = codex_home / "skills"
    if not skills_root.is_dir():
        return []

    providers: List[Dict[str, Any]] = []
    for skill_dir in sorted(skills_root.iterdir(), key=lambda item: item.name.lower()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        manifest = _read_host_skill_manifest(skill_file)
        skill_name = str(manifest.get("name") or skill_dir.name).strip()
        description = str(manifest.get("description") or "").strip()
        capabilities = _host_skill_capabilities(skill_name, description)
        if not capabilities:
            continue
        display_name = skill_name or skill_dir.name
        aliases = _host_skill_aliases(skill_name, display_name, capabilities)
        providers.append(
            {
                "provider_id": skill_name.lower().replace("_", "-"),
                "display_name": display_name,
                "aliases": aliases,
                "capabilities": capabilities,
                "metadata": {
                    "host": host,
                    "source": "host-local-skill",
                    "path": str(skill_file),
                },
            }
        )
    return providers


def _read_host_skill_manifest(skill_file: Path) -> Dict[str, str]:
    try:
        text = skill_file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = skill_file.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    manifest: Dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        if key in {"name", "description"}:
            manifest[key] = value.strip().strip("\"'")
    return manifest


def _host_skill_capabilities(name: str, description: str) -> List[str]:
    lowered = f"{name} {description}".lower()
    capabilities: List[str] = []
    if (
        ("sql" in lowered or "t-sql" in lowered or "tsql" in lowered or "query" in lowered)
        and any(term in lowered for term in ["format", "clean", "standard", "refactor", "readability"])
    ):
        capabilities.append("sql_formatting")
    return capabilities


def _host_skill_aliases(name: str, display_name: str, capabilities: Sequence[str]) -> List[str]:
    aliases = {
        name.lower(),
        display_name.lower(),
        name.lower().replace("_", "-"),
        name.lower().replace("_", " "),
        name.lower().replace("-", " "),
    }
    if "sql_formatting" in capabilities:
        aliases.update(
            {
                "sql-formatting",
                "sql formatting",
                "sql-formatting skill",
                "sql formatting skill",
                "t-sql formatting",
                "tsql formatting",
            }
        )
    return sorted(alias for alias in aliases if alias)


def _recommended_skills(classification: Dict[str, Any], plugin_route: Dict[str, Any]) -> List[str]:
    skills: List[str] = []
    skills.extend(FRONT_DOOR_SKILLS)
    skills.extend(str(item) for item in classification.get("recommended_skills", []))
    skills.extend(str(item) for item in classification.get("required_harnesses", []))
    skills.extend(str(item) for item in classification.get("cross_cutting", []))
    controller = plugin_route.get("controller", {}) or {}
    if controller.get("provider_id") == "kh":
        skills.append("workflow-usability-harness")
    if _needs_sql_formatting_style_harness(classification, plugin_route):
        skills.append("sql-formatting-style-harness")
    if classification.get("complexity") in {"heavy", "high_risk"}:
        skills.extend(
            [
                "workflow-usability-harness",
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


def _needs_sql_formatting_style_harness(classification: Dict[str, Any], plugin_route: Dict[str, Any]) -> bool:
    selected_roles = [plugin_route.get("controller", {}) or {}]
    selected_roles.extend(plugin_route.get("assistants", []) or [])
    if not any(role.get("capability") == "sql_formatting" for role in selected_roles):
        return False
    if plugin_route.get("ask_user"):
        return False
    return True


def _front_door_skill_statuses(
    recommended_skills: Sequence[str],
    classification: Dict[str, Any],
    skill_source: SkillSource,
) -> Dict[str, Dict[str, Any]]:
    statuses: Dict[str, Dict[str, Any]] = {}
    for skill in recommended_skills:
        if skill == "always-on-front-door":
            statuses[skill] = _status(
                "applied",
                "runtime",
                "always-on-front-door forced KH intake before any other non-trivial skill or plugin.",
                ["kh_front_door", "classification", "plugin_route", "runtime_applied_skills"],
            )
        elif skill == "automatic-intake-harness":
            statuses[skill] = _status(
                "applied",
                "runtime",
                "kh_front_door executed the automatic intake contract before source exploration or edits.",
                ["kh_front_door", "classification", "plugin_route"],
            )
        elif skill == "plugin-composition-policy":
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


def _mark_immediate_next_skill_statuses(
    statuses: Dict[str, Dict[str, Any]],
    immediate_next_skills: Sequence[str],
) -> Dict[str, Dict[str, Any]]:
    if not immediate_next_skills:
        return statuses
    updated = {name: dict(status) for name, status in statuses.items()}
    for skill in immediate_next_skills:
        if skill not in updated:
            continue
        updated[skill] = _status(
            "pending_immediate_execution",
            "immediate_gate",
            "Front-door selected this skill as an immediate next gate; no runtime execution is claimed until applied, skipped_with_rationale, passthrough, or blocked evidence is recorded in the same turn.",
            ["immediate_next_skills", "required_next_actions"],
        )
        updated[skill]["metadata"] = {"front_door_immediate_gate": True}
    return updated


def _immediate_next_skills(
    classification: Dict[str, Any],
    plugin_route: Dict[str, Any],
    recommended_skills: Sequence[str],
    execution_gate: Dict[str, Any],
) -> List[str]:
    recommended = set(recommended_skills)
    controller = plugin_route.get("controller", {}) or {}
    controller_id = str(controller.get("provider_id") or "")

    status = str(execution_gate.get("status") or "")
    if status == "blocked_until_brainstorming_handoff":
        return ["brainstorming-harness"] if "brainstorming-harness" in recommended else []

    if status == "blocked_until_large_work_preflight":
        ordered = [
            "goal-state-harness",
            "workflow-usability-harness",
            "host-agent-orchestration",
            "parallel-orchestration-harness",
            "role-execution-audit-harness",
            "verification-before-completion-harness",
        ]
        return [skill for skill in ordered if skill in recommended][:4]

    if _needs_sql_formatting_style_harness(classification, plugin_route):
        return ["sql-formatting-style-harness"] if "sql-formatting-style-harness" in recommended else []

    if controller_id and controller_id not in {"kh", "none"}:
        return []

    ordered = [
        "command-output-harness",
        "workflow-usability-harness",
        "memory-state-harness",
        "verification-before-completion-harness",
    ]
    return [skill for skill in ordered if skill in recommended][:2]


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
    token_optimizer_status, token_optimizer_status_reason = _front_door_token_optimizer_contract(
        classification,
        front_door_statuses,
    )
    return build_large_work_orchestration_bundle(
        objective=prompt,
        workspace_strategy="front-door-only; select worktree strategy before edits",
        token_optimizer_status=token_optimizer_status,
        token_optimizer_status_reason=token_optimizer_status_reason,
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


def _front_door_token_optimizer_contract(
    classification: Dict[str, Any],
    front_door_statuses: Dict[str, Dict[str, Any]],
) -> tuple[str, str]:
    """Return token optimizer usage status, separate from skill application status."""
    skill_status = str(front_door_statuses.get("token-optimizer", {}).get("status") or "")
    decision = front_door_statuses.get("token-optimizer", {}).get("metadata", {}).get("token_optimizer_decision")
    if isinstance(decision, dict) and decision.get("token_optimizer_status"):
        return (
            str(decision.get("token_optimizer_status") or ""),
            str(decision.get("token_optimizer_status_reason") or ""),
        )
    evidence_required = set(classification.get("evidence_required", []) or [])
    needs_token_gate = bool(
        {"token_optimization", "token_optimizer_status"} & evidence_required
        or "token-optimizer" in (classification.get("cross_cutting", []) or [])
    )
    if skill_status == "pending_immediate_execution":
        return (
            "blocked",
            "Token optimizer was selected as an immediate next gate but has not run yet; do not report token savings until used, passthrough, considered_not_needed, or blocked evidence is recorded.",
        )
    if skill_status == "blocked":
        return (
            "blocked",
            str(front_door_statuses.get("token-optimizer", {}).get("blocked_reason") or "Token optimizer is blocked."),
        )
    if needs_token_gate:
        return (
            "considered_not_needed",
            "Front-door recorded the token decision gate; no large command output, transcript, or compressible artifact has been processed yet.",
        )
    return (
        "considered_not_needed",
        "No large/log-like content crossed the token optimization threshold during front-door intake.",
    )


def _front_door_token_optimizer_decision(prompt: str, classification: Dict[str, Any]) -> Dict[str, Any]:
    prompt_tokens = _local_token_estimate(prompt)
    prompt_lines = len((prompt or "").splitlines())
    usage = _front_door_token_usage(prompt or "")
    evidence_required = set(classification.get("evidence_required", []) or [])
    reasons = list(classification.get("reasons", []) or [])
    token_required = bool(
        {"token_optimization", "token_optimizer_status"} & evidence_required
        or "token-optimizer" in (classification.get("cross_cutting", []) or [])
    )
    if not token_required:
        status = "considered_not_needed"
        reason = "Token optimizer gate checked; request did not require optimization evidence."
    elif "token_optimization" in evidence_required or prompt_tokens >= 500 or prompt_lines > 50:
        status = "passthrough"
        reason = (
            "Token optimizer gate checked; the front-door preserved the exact user prompt and requires downstream "
            "command output, transcript, or artifact optimization before broad context growth."
        )
    else:
        status = "considered_not_needed"
        reason = (
            "Token optimizer gate checked; no command output, subagent transcript, or compressible artifact has been "
            "processed yet."
        )
    decision = {
        "provider": "kh",
        "token_optimizer_provider": "kh",
        "token_optimizer_status": status,
        "token_optimizer_status_reason": reason,
        "token_optimizer_gate_status": "checked",
        "token_optimizer_lifecycle_status": "gate_checked",
        "optimization_applied": status == "used",
        "actual_optimization_used": status == "used",
        "actual_optimization_claimed": status == "used",
        "actual_optimization_kind": "compression_filter_or_minify" if status == "used" else "none",
        "usage_kind": "optimization" if status == "used" else "gate_check_only",
        "actual_optimization_status": status,
        "actual_optimization_summary": _token_optimizer_actual_summary(status, usage, reason),
        "not_used_reason": reason if status != "used" else "",
        "records_count": 0,
        "optimized_payload_count": 0,
        **usage,
        "estimated_prompt_tokens": prompt_tokens,
        "prompt_line_count": prompt_lines,
        "front_door_gate": True,
        "evidence": ["front_door_token_optimizer_gate"],
        "classification_reasons": reasons,
    }
    return decision


def _apply_front_door_token_optimizer_gate(
    statuses: Dict[str, Dict[str, Any]],
    decision: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    if "token-optimizer" not in statuses:
        return statuses
    updated = {name: dict(status) for name, status in statuses.items()}
    status = str(decision.get("token_optimizer_status") or "considered_not_needed")
    reason = str(decision.get("token_optimizer_status_reason") or "")
    updated["token-optimizer"] = _status(
        "applied",
        "runtime",
        (
            "Front-door checked the Token Optimizer decision gate; no actual payload optimization is claimed "
            f"unless status=used. Actual optimization status={status}. {reason}"
        ),
        ["token_optimizer_decision", "token_optimizer_status", "token_optimizer_status_reason"],
    )
    updated["token-optimizer"]["metadata"] = {
        "token_optimizer_decision": dict(decision),
        "token_optimizer_lifecycle": _token_optimizer_lifecycle_summary(decision),
    }
    return updated


def _token_optimizer_actual_summary(status: str, usage: Dict[str, Any], reason: str) -> str:
    without_optimizer = int(usage.get("without_token_optimizer") or 0)
    with_optimizer = int(usage.get("with_token_optimizer") or 0)
    saved = int(usage.get("estimated_tokens_saved") or 0)
    ratio = float(usage.get("token_savings_ratio") or 0.0)
    if status == "used":
        return (
            f"Token Optimizer used; before={without_optimizer}, after={with_optimizer}, "
            f"saved={saved}, savings_ratio={ratio:.3f}."
        )
    return (
        f"Token Optimizer not used for payload compression at this stage; before={without_optimizer}, "
        f"after={with_optimizer}, saved={saved}, savings_ratio={ratio:.3f}. Reason: {reason}"
    )


def _token_optimizer_gate_summary(decision: Dict[str, Any]) -> Dict[str, Any]:
    status = str(decision.get("token_optimizer_status") or "unknown")
    return {
        "gate_status": str(decision.get("token_optimizer_gate_status") or "checked"),
        "provider": str(decision.get("token_optimizer_provider") or decision.get("provider") or ""),
        "actual_optimization_status": str(decision.get("actual_optimization_status") or status),
        "optimization_applied": bool(decision.get("optimization_applied")),
        "reason": str(decision.get("token_optimizer_status_reason") or decision.get("not_used_reason") or ""),
        "without_token_optimizer": int(decision.get("without_token_optimizer") or 0),
        "with_token_optimizer": int(decision.get("with_token_optimizer") or 0),
        "estimated_tokens_saved": int(decision.get("estimated_tokens_saved") or 0),
        "token_savings_ratio": float(decision.get("token_savings_ratio") or 0.0),
        "actual_usage_scope": str(decision.get("actual_usage_scope") or ""),
        "summary": str(decision.get("actual_optimization_summary") or ""),
    }


def _token_optimizer_lifecycle_summary(decision: Dict[str, Any]) -> Dict[str, Any]:
    status = str(decision.get("token_optimizer_status") or "unknown")
    actual_used = bool(decision.get("actual_optimization_used") or decision.get("optimization_applied"))
    return {
        "gate_status": str(decision.get("token_optimizer_gate_status") or "checked"),
        "lifecycle_status": str(decision.get("token_optimizer_lifecycle_status") or "gate_checked"),
        "decision_status": status,
        "actual_optimization_status": str(decision.get("actual_optimization_status") or status),
        "actual_optimization_used": actual_used,
        "actual_optimization_claimed": bool(decision.get("actual_optimization_claimed") or actual_used),
        "actual_optimization_kind": str(decision.get("actual_optimization_kind") or ("optimization" if actual_used else "none")),
        "usage_kind": str(decision.get("usage_kind") or ("optimization" if actual_used else "gate_check_only")),
        "not_used_reason": str(decision.get("not_used_reason") or ""),
        "reason": str(decision.get("token_optimizer_status_reason") or decision.get("not_used_reason") or ""),
    }


def _compact_skill_source(skill_source: SkillSource) -> Dict[str, Any]:
    return {
        "source_type": skill_source.source_type,
        "version": skill_source.version,
        "exists": skill_source.exists,
        "skill_count": skill_source.skill_count,
        "reason": skill_source.reason,
    }


def _compact_host_skill_path_check(check: HostSkillPathCheck) -> Dict[str, Any]:
    return {
        "path": check.path,
        "status": check.status,
        "exists": check.exists,
        "reason": check.reason,
    }


def _compact_execution_gate(execution_gate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": execution_gate.get("status"),
        "can_execute": execution_gate.get("can_execute"),
        "reason": execution_gate.get("reason"),
        "required_before_execution": list(execution_gate.get("required_before_execution", []) or []),
        "blocked_actions": list(execution_gate.get("blocked_actions", []) or []),
    }


def _compact_execution_authorization(authorization: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": authorization.get("status"),
        "can_execute_now": authorization.get("can_execute_now"),
        "can_start_task_work": authorization.get("can_start_task_work"),
        "must_stop_before_execution": authorization.get("must_stop_before_execution"),
        "pending_immediate_next_skills": list(authorization.get("pending_immediate_next_skills", []) or []),
        "required_before_execution": list(authorization.get("required_before_execution", []) or []),
        "forbidden_next_actions": list(authorization.get("forbidden_next_actions", []) or []),
        "strict_exit_code_when_blocked": authorization.get("strict_exit_code_when_blocked"),
    }


def _compact_token_optimizer_decision(decision: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "provider": decision.get("provider") or decision.get("token_optimizer_provider"),
        "token_optimizer_status": decision.get("token_optimizer_status"),
        "not_used_reason": decision.get("not_used_reason"),
        "optimization_applied": bool(decision.get("optimization_applied")),
        "actual_optimization_claimed": bool(decision.get("actual_optimization_claimed")),
        "usage_kind": decision.get("usage_kind"),
        "without_token_optimizer": int(decision.get("without_token_optimizer") or 0),
        "with_token_optimizer": int(decision.get("with_token_optimizer") or 0),
        "estimated_tokens_saved": int(decision.get("estimated_tokens_saved") or 0),
        "token_savings_ratio": float(decision.get("token_savings_ratio") or 0.0),
        "billing_tokens_available": bool(decision.get("billing_tokens_available")),
        "token_count_is_estimate": bool(decision.get("token_count_is_estimate", True)),
    }


def _compact_token_optimizer_gate_summary(decision: Dict[str, Any]) -> Dict[str, Any]:
    status = str(decision.get("token_optimizer_status") or "unknown")
    summary = (
        "used"
        if bool(decision.get("optimization_applied"))
        else f"not used; status={status}"
    )
    return {
        "gate_status": str(decision.get("token_optimizer_gate_status") or "checked"),
        "provider": str(decision.get("token_optimizer_provider") or decision.get("provider") or ""),
        "status": status,
        "optimization_applied": bool(decision.get("optimization_applied")),
        "summary": summary,
        "estimated_tokens_saved": int(decision.get("estimated_tokens_saved") or 0),
        "token_savings_ratio": float(decision.get("token_savings_ratio") or 0.0),
    }


def _compact_token_optimizer_lifecycle_summary(decision: Dict[str, Any]) -> Dict[str, Any]:
    status = str(decision.get("token_optimizer_status") or "unknown")
    actual_used = bool(decision.get("actual_optimization_used") or decision.get("optimization_applied"))
    return {
        "gate_status": str(decision.get("token_optimizer_gate_status") or "checked"),
        "lifecycle_status": str(decision.get("token_optimizer_lifecycle_status") or "gate_checked"),
        "decision_status": status,
        "actual_optimization_claimed": bool(decision.get("actual_optimization_claimed") or actual_used),
        "usage_kind": str(decision.get("usage_kind") or ("optimization" if actual_used else "gate_check_only")),
    }


def _compact_memory_policy(memory_policy: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "scope": memory_policy.get("scope"),
        "global_codex_memory_allowed": memory_policy.get("global_codex_memory_allowed"),
        "host_memory_lookup_before_front_door_allowed": memory_policy.get("host_memory_lookup_before_front_door_allowed"),
        "subagent_scope": memory_policy.get("subagent_scope"),
    }


def _compact_required_next_actions(
    required_next_actions: Sequence[str],
    authorization: Dict[str, Any],
    immediate_next_skills: Sequence[str],
    plugin_route: Dict[str, Any],
) -> List[str]:
    controller = plugin_route.get("controller", {}) or {}
    controller_id = str(controller.get("provider_id") or "")
    should_show = bool(
        authorization.get("must_stop_before_execution")
        or immediate_next_skills
        or controller_id not in {"", "none"}
    )
    if not should_show:
        return []
    return list(required_next_actions)[:3]


def _compact_skill_status_summary(statuses: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    by_mode: Dict[str, int] = {}
    for status in statuses.values():
        status_name = str(status.get("status") or "unknown")
        mode_name = str(status.get("application_mode") or "unknown")
        by_status[status_name] = by_status.get(status_name, 0) + 1
        by_mode[mode_name] = by_mode.get(mode_name, 0) + 1
    return {
        "total": len(statuses),
        "by_status": by_status,
        "by_application_mode": by_mode,
    }


def _execution_authorization(
    execution_gate: Dict[str, Any],
    immediate_next_skills: Sequence[str],
    required_next_actions: Sequence[str],
) -> Dict[str, Any]:
    gate_can_execute = bool(execution_gate.get("can_execute", True))
    pending_immediate = [str(skill) for skill in immediate_next_skills if str(skill)]
    blocked_actions = _dedupe(str(item) for item in execution_gate.get("blocked_actions", []) or [])
    if pending_immediate:
        blocked_actions = _dedupe(
            [
                *blocked_actions,
                "source_exploration_before_immediate_skill_evidence",
                "implementation_before_immediate_skill_evidence",
                "file_or_db_write_before_immediate_skill_evidence",
                "verification_or_completion_before_immediate_skill_evidence",
            ]
        )
    required = _dedupe(
        [
            *[str(item) for item in execution_gate.get("required_before_execution", []) or []],
            *(
                [
                    "immediate_next_skills_applied_skipped_or_blocked",
                    "same_turn_immediate_skill_evidence",
                ]
                if pending_immediate
                else []
            ),
        ]
    )
    if not gate_can_execute:
        status = "blocked_by_execution_gate"
    elif pending_immediate:
        status = "blocked_by_pending_immediate_skill_gate"
    else:
        status = "allowed"
    must_stop = status != "allowed"
    allowed_setup = _dedupe(
        [
            *[str(item) for item in execution_gate.get("allowed_setup_actions", []) or []],
            *(
                [
                    "read_immediate_skill_docs_only",
                    "record_immediate_skill_applied_skipped_or_blocked_evidence",
                ]
                if pending_immediate
                else []
            ),
        ]
    )
    if not allowed_setup and must_stop:
        allowed_setup = ["satisfy_execution_gate_required_evidence"]
    return {
        "status": status,
        "can_execute_now": not must_stop,
        "can_start_task_work": not must_stop,
        "must_stop_before_execution": must_stop,
        "gate_can_execute": gate_can_execute,
        "pending_immediate_next_skills": pending_immediate,
        "required_before_execution": required,
        "allowed_next_actions_only": allowed_setup,
        "forbidden_next_actions": blocked_actions,
        "completion_claim_allowed": not must_stop,
        "strict_exit_code_when_blocked": 3 if must_stop else 0,
        "hard_stop_message": (
            "STOP: do not run source exploration, implementation, file writes, DB writes, "
            "verification, subagent dispatch, or completion claims until required evidence exists."
            if must_stop
            else "Execution may continue after selected provider or skill setup."
        ),
        "required_next_action_preview": list(required_next_actions)[:3],
    }


def _local_token_estimate(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _front_door_token_usage(prompt: str) -> Dict[str, Any]:
    without_optimizer = _local_token_estimate(prompt)
    with_optimizer = without_optimizer
    raw_bytes = len(prompt.encode("utf-8"))
    raw_chars = len(prompt)
    usage = {
        "without_token_optimizer": without_optimizer,
        "with_token_optimizer": with_optimizer,
        "estimated_tokens_saved": 0,
        "token_savings_ratio": 0.0,
        "actual_usage_scope": "front_door_prompt_passthrough_payload",
        "token_count_method": "deterministic_local_estimate_chars_div_4",
        "token_count_is_estimate": True,
        "billing_tokens_available": False,
        "actual_without_token_optimizer": without_optimizer,
        "actual_with_token_optimizer": with_optimizer,
        "actual_tokens_saved": 0,
        "actual_token_savings_ratio": 0.0,
        "actual_without_token_optimizer_bytes": raw_bytes,
        "actual_with_token_optimizer_bytes": raw_bytes,
        "actual_bytes_saved": 0,
        "actual_byte_savings_ratio": 0.0,
        "actual_without_token_optimizer_chars": raw_chars,
        "actual_with_token_optimizer_chars": raw_chars,
        "actual_chars_saved": 0,
        "actual_char_savings_ratio": 0.0,
    }
    usage["actual_usage"] = {
        "scope": usage["actual_usage_scope"],
        "without_token_optimizer": without_optimizer,
        "with_token_optimizer": with_optimizer,
        "tokens_saved": 0,
        "token_savings_ratio": 0.0,
        "without_token_optimizer_bytes": raw_bytes,
        "with_token_optimizer_bytes": raw_bytes,
        "bytes_saved": 0,
        "byte_savings_ratio": 0.0,
        "without_token_optimizer_chars": raw_chars,
        "with_token_optimizer_chars": raw_chars,
        "chars_saved": 0,
        "char_savings_ratio": 0.0,
    }
    return usage


def _required_next_actions(
    classification: Dict[str, Any],
    plugin_route: Dict[str, Any],
    recommended_skills: Sequence[str],
    execution_gate: Dict[str, Any] | None = None,
    immediate_next_skills: Sequence[str] | None = None,
) -> List[str]:
    actions = [
        "Do not continue from `recommended_skills` as a loose checklist. Execute `immediate_next_skills` first, in order, and record applied/skipped/blocked evidence for each before source exploration, implementation, verification, or final claims.",
        "Read only the immediate next skills needed for the next step through `python -m src.skills.uaf_skill_catalog --read <skill>`.",
        "Do not claim runtime skill application unless a module, gate, artifact, or explicit passthrough evidence was produced.",
    ]
    if immediate_next_skills:
        immediate = ", ".join(f"`{skill}`" for skill in immediate_next_skills)
        if list(immediate_next_skills) == ["sql-formatting-style-harness"]:
            actions.insert(
                0,
                "NEXT SKILL EXECUTION: apply the selected SQL formatting provider first, then run `sql-formatting-style-harness` verifier or record a blocked reason before SQL output, DB writes, or final claims.",
            )
        else:
            actions.insert(
                0,
                f"NEXT SKILL EXECUTION: apply {immediate} now. Everything else in `selected_not_executed_skills` is deferred until these are applied, skipped with rationale, or blocked.",
            )
    if execution_gate and not execution_gate.get("can_execute", True):
        actions.insert(
            0,
            "BLOCKING FRONT-DOOR RESULT: `execution_authorization.must_stop_before_execution=true`. Only the gate's allowed setup actions may run next; source exploration, implementation, file writes, DB writes, verification, subagent dispatch, and completion claims are invalid until required evidence exists.",
        )
    controller = plugin_route.get("controller", {}) or {}
    controller_id = str(controller.get("provider_id") or "")
    selected_roles = [controller]
    selected_roles.extend(plugin_route.get("assistants", []) or [])
    sql_role_ids = [
        str(role.get("provider_id") or "")
        for role in selected_roles
        if isinstance(role, dict)
        and role.get("capability") == "sql_formatting"
        and str(role.get("provider_id") or "") not in {"", "kh", "none"}
    ]
    if sql_role_ids:
        formatted_roles = ", ".join(f"`{role_id}`" for role_id in _dedupe(sql_role_ids))
        actions.append(
            f"SQL PRE-OUTPUT GATE: before emitting, rewriting, or correcting any SQL/T-SQL, apply selected provider {formatted_roles}; read the host-local sql-formatting SKILL.md, preserve literals/comments/localized business text, and record sql-formatting-style-harness verifier evidence or an explicit blocked reason."
        )
    if controller_id and controller_id not in {"kh", "none"}:
        actions.append(
            f"Apply selected provider `{controller_id}` next; if it is a host-local skill, read that skill's SKILL.md and follow only its delegated scope."
        )
    for assistant in plugin_route.get("assistants", []):
        assistant = assistant or {}
        assistant_id = str(assistant.get("provider_id") or "")
        if assistant_id and assistant_id not in {"kh", "none", controller_id}:
            actions.append(
                f"Apply assistant provider `{assistant_id}` only for delegated capability `{assistant.get('capability', '')}`."
            )
    if plugin_route.get("ask_user"):
        actions.append("Ask a short clarification before source exploration or implementation.")
    if execution_gate and not execution_gate.get("can_execute", True):
        if execution_gate.get("status") == "blocked_until_large_work_preflight":
            actions.append(
                "HARD PRE-FLIGHT STOP: heavy or role_dag work cannot move into broad source exploration, file writes, DB writes, subagent dispatch, verification, or completion claims until large_work_orchestration_bundle, GoalState, workspace_strategy, token_optimizer_status, token_optimizer_status_reason, host/subagent strategy, parallel strategy, role audit decision, guard/rollback policy, and verification plan evidence are recorded."
            )
        else:
            actions.append(
                "HARD STOP: execution_gate.can_execute=false. Do not read MEMORY.md, use memory-derived implementation shortcuts, inspect parent/sibling run folders, scaffold files, write source, create deliverables, run verification, or start browser QA until the gate's required_before_execution items are satisfied."
            )
    if "brainstorming-harness" in recommended_skills:
        actions.append(
            "Apply `brainstorming-harness` before execution: progress through intent_frame, problem_frame, option_frame, design/spec review, approval_frame, and handoff_frame for product, process, analysis, design, document, operations, manufacturing/specification, investment, or other domain work; preserve `BrainstormSession`, `decision_log`, `validate_brainstorm_session`, and `brainstorm_handoff` or blocked rationale. Do not run `Test-Path`, `Get-ChildItem`, `rg`, `Get-Content`, target folder existence checks, parent/sibling scans, source reads, or target write preflight before the first visible brainstorm/handoff gate; mention the named target path only as user context. A user option choice is direction approval only; do not implement, lock implementation scope, list final KPI/form/table/storage scope, create analysis output, user deliverables, or domain artifacts until the reviewed handoff/spec exists and the user separately asks to implement, start work, create files, or generate deliverables. After option choice, ask the next focused design/spec question instead of saying `implementation scope is` or `I will set the implementation scope as follows`. For domain workflows, make the compact brainstorm domain-first: objective/operator, workflow boundary, 2-3 operating model choices, required records/data, one recommendation, and one approval question; do not offer only technology-stack choices such as HTML/React/WinForms."
        )
    if "memory-state-harness" in recommended_skills:
        actions.append(
            "Apply `memory-state-harness` with scoped evidence: record memory_scope, memory_provider_policy, prompt_snapshot_status, action_sensitive_memory_boundary, and global_memory_candidate_policy; default to project/chat-scoped prompt snapshots, treat host global Codex memory as a separate explicit promotion target, and keep important cross-project lessons as global_memory_candidate records until user-approved promotion evidence exists. Treat MEMORY.md/USER.md snapshots as frozen session-start context, use session search or scoped recall for old chats, and treat OpenClaw/Hermes-style external providers as additive evidence candidates rather than current truth."
        )
    if classification.get("complexity") in {"heavy", "high_risk"}:
        actions.extend(
            [
                "Create or update GoalState before implementation.",
                "Record workspace_strategy before edits.",
                "Record token_optimizer_status=used|considered_not_needed|passthrough|blocked and token_optimizer_status_reason before broad reads, implementation tools, subagent packets, or long command-output handling.",
                "Record host_runtime, nested_subagents_available or not_applicable, subagent_strategy with concrete rationale, parallel_strategy_decision with concrete rationale, and role_execution_audit.status before implementation.",
                "For DB writes, destructive commands, or shared production state, record guard_policy plus rollback/snapshot strategy before the write.",
                "When running inside a host subagent, record nested_subagents_available and subagent_strategy=dispatch|single-controller|review-only|blocked before implementation.",
                "Run verification-before-completion before any done, commit, push, or handoff claim.",
            ]
        )
    if "command-output-harness" in recommended_skills:
        actions.append(
            "Record command_output_filter_plan before broad command reads: preserve exit code, file paths, line numbers, error codes, SQL/query text, and user-requested facts; if preservation cannot be proven, use passthrough or wider-context fallback."
        )
    if any(
        skill in recommended_skills
        for skill in [
            "artifact-render-qa-harness",
            "deliverable-template-quality-harness",
            "traceability-matrix-harness",
        ]
    ):
        actions.append(
            "Record deliverable_render_quality_plan before generating user-facing artifacts: required output files, source-to-deliverable traceability, render/readability validation, and how requested SQL/text will be included in the user-facing response when requested."
        )
    deferred = [
        skill
        for skill in recommended_skills
        if skill not in FRONT_DOOR_SKILLS
        and skill not in set(immediate_next_skills or [])
    ]
    if deferred:
        actions.append(
            "Deferred selected skills are not applied yet: "
            + ", ".join(f"`{skill}`" for skill in deferred[:10])
            + ("." if len(deferred) <= 10 else f", and {len(deferred) - 10} more.")
            + " Do not report them as used until concrete evidence exists."
        )
    return _dedupe(actions)


def _execution_gate(
    classification: Dict[str, Any],
    plugin_route: Dict[str, Any],
    recommended_skills: Sequence[str],
) -> Dict[str, Any]:
    if classification.get("complexity") == "ambiguous" or classification.get("recommended_execution") == "clarify":
        return {
            "status": "blocked_until_clarification",
            "can_execute": False,
            "reason": "Request classification requires clarification before source exploration, memory lookup, or implementation.",
            "required_before_execution": ["user_clarification"],
            "blocked_actions": [
                "memory_lookup",
                "global_codex_memory",
                "cross_chat_or_subagent_memory",
                "target_or_sibling_folder_scan",
                "implementation",
                "deliverable_generation",
                "verification",
                "browser_qa",
            ],
        }
    if plugin_route.get("ask_user"):
        return {
            "status": "blocked_until_clarification",
            "can_execute": False,
            "reason": "The plugin route requires a user clarification before source exploration or implementation.",
            "required_before_execution": ["user_clarification"],
            "blocked_actions": [
                "memory_lookup",
                "global_codex_memory",
                "cross_chat_or_subagent_memory",
                "target_or_sibling_folder_scan",
                "implementation",
                "deliverable_generation",
                "verification",
                "browser_qa",
            ],
        }
    if "brainstorming-harness" in recommended_skills:
        return {
            "status": "blocked_until_brainstorming_handoff",
            "can_execute": False,
            "reason": (
                "brainstorming-harness was selected for an early direction-setting request; "
                "the user's development wording is not approval to skip brainstorming."
            ),
            "required_before_execution": [
                "brainstorming-harness",
                "intent_frame",
                "problem_frame",
                "option_frame",
                "approval_frame",
                "BrainstormSession",
                "decision_log",
                "validate_brainstorm_session",
                "brainstorm_handoff",
                "design_review_approval",
                "separate_implementation_approval",
            ],
            "blocked_actions": [
                "MEMORY.md_lookup",
                "global_codex_MEMORY.md",
                "cross_chat_or_subagent_memory",
                "memory_derived_shortcuts",
                "parent_or_sibling_run_reads",
                "target_folder_existence_check",
                "target_folder_inspection",
                "target_write_preflight",
                "Test-Path",
                "Get-ChildItem",
                "rg",
                "Get-Content",
                "source_reads",
                "implementation",
                "source_or_asset_scaffolding",
                "analysis_output",
                "user_deliverable_generation",
                "verification",
                "browser_qa",
            ],
        }
    if (
        classification.get("complexity") in {"heavy", "high_risk"}
        or classification.get("recommended_execution") == "role_dag"
    ):
        required_before_execution = [
            "goal-state-harness",
            "large_work_orchestration_bundle",
            "skill_statuses",
            "workspace_strategy",
            "token_optimizer_status",
            "host_runtime",
            "nested_subagents_available_or_not_applicable",
            "subagent_strategy_with_rationale",
            "parallel_strategy_decision_with_rationale",
            "role_execution_audit.status_or_pre_role_skip",
            "guard_policy_or_rollback_strategy",
            "verification_plan",
        ]
        if "command-output-harness" in recommended_skills:
            required_before_execution.append("command_output_filter_plan")
        if any(
            skill in recommended_skills
            for skill in [
                "artifact-render-qa-harness",
                "deliverable-template-quality-harness",
                "traceability-matrix-harness",
            ]
        ):
            required_before_execution.append("deliverable_render_quality_plan")
        return {
            "status": "blocked_until_large_work_preflight",
            "can_execute": False,
            "reason": (
                "Heavy or role_dag work selected orchestration, review, guard, token, "
                "and verification harnesses; implementation must wait until preflight "
                "evidence records how each selected harness will run, be skipped, or be blocked."
            ),
            "required_before_execution": required_before_execution,
            "allowed_setup_actions": [
                "read_selected_skill_docs",
                "create_or_update_goal_state",
                "record_large_work_orchestration_bundle",
                "record_workspace_strategy",
                "record_token_optimizer_status",
                "record_host_subagent_parallel_role_strategy",
                "record_command_output_filter_plan",
                "record_deliverable_render_quality_plan",
                "record_guard_or_rollback_policy",
                "record_verification_plan",
            ],
            "blocked_actions": [
                "broad_source_exploration",
                "implementation",
                "file_writes",
                "db_writes",
                "destructive_commands",
                "subagent_dispatch_without_strategy",
                "verification_run_as_completion_proof",
                "completion_claim",
                "claiming_selected_not_executed_skills_as_applied",
            ],
        }
    return {
        "status": "execution_allowed_after_selected_skill_setup",
        "can_execute": True,
        "reason": "No clarification or brainstorming stop gate was selected by front-door routing.",
        "required_before_execution": [],
        "blocked_actions": [],
    }


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
    parser.add_argument("--prompt", default="", help="User request text. Prefer --prompt-file for non-ASCII prompts on Windows.")
    parser.add_argument("--prompt-file", default="", help="UTF-8 file containing the user request text.")
    parser.add_argument("--prompt-stdin", action="store_true", help="Read the user request text from stdin.")
    parser.add_argument("--project", default="", help="Target project path. Defaults to current directory.")
    parser.add_argument("--host", default="codex", help="Host runtime label such as codex, antigravity, or local.")
    parser.add_argument(
        "--host-skill-path",
        action="append",
        default=[],
        help="Host-provided KH skill path to validate. Repeat for multiple paths.",
    )
    parser.add_argument("--providers-json", default="", help="Optional JSON provider snapshot.")
    parser.add_argument("--context-json", default="", help="Optional JSON request context from the host/session.")
    parser.add_argument("--context-file", default="", help="Optional UTF-8 JSON file containing request context.")
    parser.add_argument("--prefer-cache", action="store_true", help="Prefer the latest installed kh-uaf cache over repo-local skills.")
    parser.add_argument("--summary", action="store_true", help="Print a compact front-door summary.")
    parser.add_argument("--verbose-summary", action="store_true", help="Print the legacy detailed front-door summary.")
    parser.add_argument(
        "--strict-execution-gate",
        action="store_true",
        help="Return exit code 3 when the front-door result still blocks task work.",
    )
    args = parser.parse_args()
    prompt = _resolve_prompt_arg(args.prompt, args.prompt_file, args.prompt_stdin)

    providers = json.loads(args.providers_json) if args.providers_json else None
    request_context = _resolve_context_arg(args.context_json, args.context_file)
    result = build_kh_front_door(
        prompt=prompt,
        project=args.project or None,
        host=args.host,
        providers=providers,
        host_skill_paths=args.host_skill_path,
        prefer_cache=args.prefer_cache,
        request_context=request_context,
    )
    if args.summary and args.verbose_summary:
        raise SystemExit("choose only one of --summary or --verbose-summary")
    if args.verbose_summary:
        payload = result.to_summary_dict()
    elif args.summary:
        payload = result.to_compact_summary_dict()
    else:
        payload = result.to_dict()
    if args.summary:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if result.front_door_status != "ok":
        return 2
    if args.strict_execution_gate and result.execution_authorization.get("must_stop_before_execution"):
        return 3
    return 0


def _resolve_prompt_arg(prompt: str, prompt_file: str, prompt_stdin: bool) -> str:
    sources = [bool(prompt), bool(prompt_file), bool(prompt_stdin)]
    if sum(1 for source in sources if source) != 1:
        raise SystemExit("provide exactly one of --prompt, --prompt-file, or --prompt-stdin")
    if prompt_file:
        return Path(prompt_file).read_text(encoding="utf-8")
    if prompt_stdin:
        return sys.stdin.read()
    return prompt


def _resolve_context_arg(context_json: str, context_file: str) -> Dict[str, Any] | None:
    if context_json and context_file:
        raise SystemExit("provide only one of --context-json or --context-file")
    if context_file:
        return json.loads(Path(context_file).read_text(encoding="utf-8"))
    if context_json:
        return json.loads(context_json)
    return None


if __name__ == "__main__":
    raise SystemExit(main())
