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
    execution_gate: Dict[str, Any]
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
            "execution_gate": dict(self.execution_gate),
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
            "execution_gate": dict(self.execution_gate),
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
    execution_gate = _execution_gate(classification, plugin_route, recommended_skills)

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
        skill_statuses=skill_statuses,
        execution_gate=execution_gate,
        required_next_actions=_required_next_actions(classification, plugin_route, recommended_skills, execution_gate),
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
    execution_gate: Dict[str, Any] | None = None,
) -> List[str]:
    actions = [
        "Read only the selected skills needed for the next step through `python -m src.skills.uaf_skill_catalog --read <skill>`.",
        "Do not claim runtime skill application unless a module, gate, artifact, or explicit passthrough evidence was produced.",
    ]
    controller = plugin_route.get("controller", {}) or {}
    controller_id = str(controller.get("provider_id") or "")
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
                "HARD PRE-FLIGHT STOP: heavy or role_dag work cannot move into broad source exploration, file writes, DB writes, subagent dispatch, verification, or completion claims until large_work_orchestration_bundle, GoalState, workspace_strategy, token_optimizer_status, host/subagent strategy, parallel strategy, role audit decision, guard/rollback policy, and verification plan evidence are recorded."
            )
        else:
            actions.append(
                "HARD STOP: execution_gate.can_execute=false. Do not read MEMORY.md, use memory-derived implementation shortcuts, inspect parent/sibling run folders, scaffold files, write source, create deliverables, run verification, or start browser QA until the gate's required_before_execution items are satisfied."
            )
    if "brainstorming-harness" in recommended_skills:
        actions.append(
            "Apply `brainstorming-harness` before execution: progress through intent_frame, problem_frame, option_frame, design/spec review, approval_frame, and handoff_frame for product, process, analysis, design, document, operations, manufacturing/specification, investment, or other domain work; preserve `BrainstormSession`, `decision_log`, `validate_brainstorm_session`, and `brainstorm_handoff` or blocked rationale. A user option choice is direction approval only; do not implement, lock implementation scope, list final KPI/form/table/storage scope, create analysis output, user deliverables, or domain artifacts until the reviewed handoff/spec exists and the user separately asks to implement, start work, create files, or generate deliverables. After option choice, ask the next focused design/spec question instead of saying `implementation scope is` or `I will set the implementation scope as follows`. For domain workflows, make the compact brainstorm domain-first: objective/operator, workflow boundary, 2-3 operating model choices, required records/data, one recommendation, and one approval question; do not offer only technology-stack choices such as HTML/React/WinForms."
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
                "Record token_optimizer_status=used|considered_not_needed|passthrough|blocked before broad reads, implementation tools, subagent packets, or long command-output handling.",
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
    for skill in recommended_skills:
        if skill in FRONT_DOOR_SKILLS or skill == "token-optimizer":
            continue
        actions.append(f"If needed next, apply `{skill}` and record concrete evidence or skipped/blocked rationale.")
    return _dedupe(actions)


def _execution_gate(
    classification: Dict[str, Any],
    plugin_route: Dict[str, Any],
    recommended_skills: Sequence[str],
) -> Dict[str, Any]:
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
    parser.add_argument("--prefer-cache", action="store_true", help="Prefer the latest installed kh-uaf cache over repo-local skills.")
    parser.add_argument("--summary", action="store_true", help="Print a compact front-door summary.")
    args = parser.parse_args()
    prompt = _resolve_prompt_arg(args.prompt, args.prompt_file, args.prompt_stdin)

    providers = json.loads(args.providers_json) if args.providers_json else None
    result = build_kh_front_door(
        prompt=prompt,
        project=args.project or None,
        host=args.host,
        providers=providers,
        host_skill_paths=args.host_skill_path,
        prefer_cache=args.prefer_cache,
    )
    payload = result.to_summary_dict() if args.summary else result.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.front_door_status == "ok" else 2


def _resolve_prompt_arg(prompt: str, prompt_file: str, prompt_stdin: bool) -> str:
    sources = [bool(prompt), bool(prompt_file), bool(prompt_stdin)]
    if sum(1 for source in sources if source) != 1:
        raise SystemExit("provide exactly one of --prompt, --prompt-file, or --prompt-stdin")
    if prompt_file:
        return Path(prompt_file).read_text(encoding="utf-8")
    if prompt_stdin:
        return sys.stdin.read()
    return prompt


if __name__ == "__main__":
    raise SystemExit(main())
