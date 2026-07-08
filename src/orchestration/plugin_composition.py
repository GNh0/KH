import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Set

from src.orchestration.request_classifier import RequestClassification, classify_request


CAPABILITY_ALIASES = {
    "browser": "browser_qa",
    "browser-test": "browser_qa",
    "browser-use": "browser_qa",
    "artifact": "artifact_qa",
    "artifact-checker": "artifact_qa",
    "render-check": "artifact_qa",
    "structure-check": "artifact_qa",
    "ci": "repo_pr_ci",
    "github": "repo_pr_ci",
    "gitlab": "repo_pr_ci",
    "notion": "knowledge_docs",
    "docs": "knowledge_docs",
    "memory": "memory_goal_resume",
    "goal": "memory_goal_resume",
    "resume": "memory_goal_resume",
    "tdd": "tdd_review",
    "review": "tdd_review",
    "worktree": "workspace_isolation",
    "workspace": "workspace_isolation",
    "verification": "completion_verification",
    "verify": "completion_verification",
    "finish": "branch_finishing",
    "ship": "branch_finishing",
    "debug": "systematic_debugging",
    "debugging": "systematic_debugging",
    "workflow": "workflow_control",
    "sql-formatting": "sql_formatting",
    "sql formatting": "sql_formatting",
    "sqlformatting": "sql_formatting",
    "tsql-formatting": "sql_formatting",
    "t-sql-formatting": "sql_formatting",
}

CONTROLLER_CAPABILITIES = {
    "workflow_control",
    "memory_goal_resume",
    "domain_orchestration",
    "planning_methodology",
    "tdd_review",
    "workspace_isolation",
    "completion_verification",
    "branch_finishing",
    "systematic_debugging",
    "repo_pr_ci",
    "knowledge_docs",
    "sql_formatting",
}

SPECIALIST_TRIGGERS = {
    "browser_qa": {
        "browser",
        "local web",
        "localhost",
        "screenshot",
        "screen",
        "click",
        "visual qa",
        "화면",
        "브라우저",
    },
    "artifact_qa": {
        "artifact qa",
        "artifact verification",
        "approved deliverable",
        "generated artifact",
        "render check",
        "structure check",
        "structural validation",
        "matching host tool",
    },
    "repo_pr_ci": {
        "pull request",
        "pr",
        "ci",
        "github",
        "issue",
        "review comment",
        "push",
    },
    "knowledge_docs": {
        "notion",
        "wiki",
        "meeting notes",
        "knowledge base",
        "문서화",
    },
    "image_generation": {
        "generate image",
        "edit image",
        "mockup image",
        "bitmap",
    },
    "host_automation": {
        "remind me",
        "schedule",
        "automation",
        "monitor",
    },
    "sql_formatting": {
        "sql-formatting",
        "sql formatting",
        "format sql",
        "format this sql",
        "format t-sql",
        "format this t-sql",
        "format tsql",
        "format query",
        "format this query",
        "clean sql",
        "clean up sql",
        "standardize sql",
        "refactor sql",
        "t-sql formatting",
        "tsql formatting",
    },
}

SQL_STATEMENT_PATTERN = re.compile(
    r"\b(?:select|insert\s+into|update|delete\s+from|merge|exec(?:ute)?|if\s+exists|raiserror|throw|openxml|begin\s+tran|rollback|create\s+(?:or\s+alter\s+)?procedure)\b",
    re.IGNORECASE,
)
SQL_NAMED_DML_PATTERN = re.compile(r"\b(?:insert|update|delete|merge)\b", re.IGNORECASE)
SQL_CONTEXT_PATTERN = re.compile(
    r"\b(?:from|where|join|set|values|group\s+by|order\s+by|procedure|proc|exec(?:ute)?|raiserror|openxml|if\s+exists|저장\s*프로시저|프로시저)\b|@[a-z_][a-z0-9_]*",
    re.IGNORECASE,
)
SQL_OUTPUT_REQUEST_MARKERS = (
    "align",
    "convert",
    "format",
    "clean",
    "normalize",
    "organize",
    "standardize",
    "refactor",
    "rewrite",
    "write",
    "create",
    "generate",
    "produce",
    "draft",
    "query",
    "procedure",
    "stored procedure",
    "proc",
    "save",
    "build",
    "make",
    "add",
    "change",
    "modify",
    "\uc815\ub9ac",
    "\uc791\uc131",
    "\ub9cc\ub4e4",
    "\uc800\uc7a5 \ud504\ub85c\uc2dc\uc800",
    "\ud504\ub85c\uc2dc\uc800",
    "\ucffc\ub9ac",
    "\ucd94\uac00",
    "\ubc14\uafd4",
    "\ub2ec\ub77c",
    "\uc870\ud68c\ub418\ub3c4\ub85d",
    "\uc815\ub82c",
    "\ub9de\ucdb0",
    "indent",
    "indentation",
    "block",
    "\ub4e4\uc5ec\uc4f0\uae30",
    "\ube14\ub7ed",
    "\ube14\ub85d",
    "\ubabb\ub9de\ucd94",
    "\ubabb \ub9de\ucd94",
    "\uc548\ub9de",
    "\uc548 \ub9de",
    "\ud558\uace0\uc2f6",
    "\ud558\uace0 \uc2f6",
    "\uc2f6\uac70\ub4e0",
    "\ub418\ub3c4\ub85d",
)
SQL_EQUIVALENCE_QUESTION_MARKERS = (
    "same behavior",
    "equivalent",
    "will this work",
    "\ub611\uac19",
    "\uac19\uc774 \ub3d9\uc791",
    "\ub3d9\uc791\ud560\uae4c",
    "\ud574\ub3c4 \ub420\uae4c",
    "\uac00\ub2a5\ud560\uae4c",
)
SQL_IMPERATIVE_MARKERS = (
    "align",
    "convert",
    "format",
    "clean",
    "normalize",
    "organize",
    "standardize",
    "refactor",
    "rewrite",
    "write",
    "create",
    "generate",
    "produce",
    "draft",
    "build",
    "make",
    "add",
    "change",
    "modify",
    "\uc815\ub9ac",
    "\uc791\uc131",
    "\ub9cc\ub4e4",
    "\ucd94\uac00",
    "\ubc14\uafd4",
    "\ub2ec\ub77c",
    "\uc870\ud68c\ub418\ub3c4\ub85d",
    "\uc815\ub82c",
    "\ub9de\ucdb0",
    "indent",
    "indentation",
    "block",
    "\ub4e4\uc5ec\uc4f0\uae30",
    "\ube14\ub7ed",
    "\ube14\ub85d",
    "\ubabb\ub9de\ucd94",
    "\ubabb \ub9de\ucd94",
    "\uc548\ub9de",
    "\uc548 \ub9de",
    "\ud558\uace0\uc2f6",
    "\ud558\uace0 \uc2f6",
    "\uc2f6\uac70\ub4e0",
    "\ub418\ub3c4\ub85d",
)

SQL_DIAGNOSTIC_QUESTION_MARKERS = (
    "why",
    "explain",
    "what does",
    "how does",
    "diagnose",
    "\uc65c",
    "\uc124\uba85",
    "\uc6d0\uc778",
    "\ubb50\uac00",
    "\ubb34\uc2a8",
)

SPECIALIST_FALLBACKS = {
    "browser_qa": "manual_qa_evidence",
    "artifact_qa": "manual_artifact_validation",
    "repo_pr_ci": "local_git_commands",
    "knowledge_docs": "docs_kh_markdown",
    "image_generation": "text_or_svg_artifact",
    "host_automation": "manual_follow_up_note",
    "sql_formatting": "manual_sql_style_rules",
}

COMMON_PROVIDER_WORDS = {
    "browser",
    "ci",
    "doc",
    "docs",
    "goal",
    "image",
    "memory",
    "pr",
    "pro",
}

EXPLICIT_PROVIDER_LEADS = (
    "use",
    "using",
    "with",
    "via",
    "through",
    "run",
    "select",
    "choose",
    "prefer",
    "force",
    "invoke",
    "call",
    "load",
    "apply",
    "route to",
    "delegate to",
)

MENTION_ONLY_CONTEXT_MARKERS = (
    "example",
    "examples",
    "risk",
    "risks",
    "concern",
    "concerns",
    "review",
    "audit",
    "compare",
    "comparison",
    "versus",
    "vs",
    "mention",
    "mentions",
    "mentioned",
    "hide",
    "hides",
    "mask",
    "masks",
    "not use",
    "not using",
    "not call",
    "not load",
    "does not use",
    "does not call",
    "cannot use",
    "can't use",
    "fails to use",
    "\uc608\uc2dc",
    "\ub9ac\uc2a4\ud06c",
    "\uc6b0\ub824",
    "\uac80\ud1a0",
    "\ud3c9\uac00",
    "\ube44\uad50",
    "\uc5b8\uae09",
    "\uac00\ub9bc",
    "\uac00\ub824",
    "\ubabb",
    "\uc54a",
)

MENTION_ONLY_SUFFIXES = (
    "etc",
    "etc.",
    "and so on",
    "among others",
    "\ub4f1",
)

NEGATED_TRIGGER_CONTEXT_MARKERS = (
    "not a request to",
    "not asking to",
    "do not",
    "don't",
    "never",
    "no need to",
    "without",
    "risk example",
    "only a risk",
    "only an example",
    "example, not",
    "\uc608\uc2dc",
    "\ub9ac\uc2a4\ud06c",
    "\uc694\uccad\uc774 \uc544\ub2d8",
    "\ud558\uc9c0 \ub9c8",
    "\ud558\uc9c0\ub9c8",
)


@dataclass(frozen=True)
class CapabilityProvider:
    provider_id: str
    capabilities: List[str] = field(default_factory=list)
    status: str = "available"
    display_name: str = ""
    aliases: List[str] = field(default_factory=list)
    self_forcing_rules: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderRole:
    provider_id: str
    capability: str = ""
    scope: str = ""
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PluginCompositionDecision:
    route: str
    controller: ProviderRole
    assistants: List[ProviderRole] = field(default_factory=list)
    conflict_policy: str = "delegated_scope"
    ignored_self_forcing: List[str] = field(default_factory=list)
    unavailable_capabilities: Dict[str, str] = field(default_factory=dict)
    explicit_user_request: bool = False
    ask_user: bool = False
    classification: Dict[str, Any] = field(default_factory=dict)
    available_providers_snapshot: List[Dict[str, Any]] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.75

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route,
            "controller": self.controller.to_dict(),
            "assistants": [assistant.to_dict() for assistant in self.assistants],
            "conflict_policy": self.conflict_policy,
            "ignored_self_forcing": list(self.ignored_self_forcing),
            "unavailable_capabilities": dict(self.unavailable_capabilities),
            "explicit_user_request": self.explicit_user_request,
            "ask_user": self.ask_user,
            "classification": dict(self.classification),
            "available_providers_snapshot": [dict(item) for item in self.available_providers_snapshot],
            "reasons": list(self.reasons),
            "confidence": self.confidence,
        }


def compose_plugin_route(
    text: str,
    providers: Iterable[CapabilityProvider | Dict[str, Any]] | None = None,
    context: Dict[str, Any] | None = None,
) -> PluginCompositionDecision:
    """Choose a direct, single-provider, hybrid, or clarification route by capability."""
    context = context or {}
    provider_list = [_normalize_provider(provider) for provider in providers or []]
    available = [provider for provider in provider_list if provider.status == "available"]
    classification = classify_request(text, context)
    lowered = str(text or "").lower()
    reasons: List[str] = []

    sql_meta_review = _has_sql_meta_review_context(lowered)
    explicit_provider = None if sql_meta_review else _explicit_provider_request(lowered, provider_list)
    if explicit_provider:
        if explicit_provider.status != "available":
            unavailable = {
                f"provider:{explicit_provider.provider_id}": f"provider_status:{explicit_provider.status}"
            }
            fallback_provider = _best_controller_provider(classification, available)
            if fallback_provider and classification.complexity not in {"light", "ambiguous"}:
                controller = _controller_role(fallback_provider, "fallback_after_explicit_provider_unavailable")
                assistants = _assistant_roles(lowered, available, {fallback_provider.provider_id})
                reasons.extend(
                    [
                        f"explicit_provider_unavailable:{explicit_provider.provider_id}",
                        f"fallback_controller:{fallback_provider.provider_id}",
                        *_controller_reasons(fallback_provider),
                    ]
                )
                return _decision(
                    route="hybrid" if assistants else "single",
                    controller=controller,
                    assistants=assistants,
                    providers=available,
                    classification=classification,
                    reasons=reasons,
                    unavailable_capabilities=unavailable,
                    explicit_user_request=True,
                    ask_user=_explicit_provider_is_required(lowered, explicit_provider),
                    confidence=min(classification.confidence, 0.68),
                )
            reasons.append(f"explicit_provider_unavailable:{explicit_provider.provider_id}")
            return _decision(
                route="clarify",
                controller=_none_role(),
                providers=available,
                classification=classification,
                reasons=reasons,
                unavailable_capabilities=unavailable,
                explicit_user_request=True,
                ask_user=True,
                confidence=min(classification.confidence, 0.55),
            )
        controller = _controller_role(explicit_provider, "explicit_user_request")
        assistants = _assistant_roles(lowered, available, {explicit_provider.provider_id})
        reasons.append(f"explicit_user_request:{explicit_provider.provider_id}")
        return _decision(
            route="hybrid" if assistants else "single",
            controller=controller,
            assistants=assistants,
            providers=available,
            classification=classification,
            reasons=reasons,
            explicit_user_request=True,
        )

    specialist_controller = _single_specialist_controller(lowered, available)
    if specialist_controller and _allow_single_specialist_controller(
        lowered,
        specialist_controller,
        classification.complexity,
    ):
        reasons.append(f"specialist_trigger:{specialist_controller.provider_id}:{specialist_controller.capability}")
        assistants = _assistant_roles(lowered, available, {specialist_controller.provider_id})
        return _decision(
            route="hybrid" if assistants else "single",
            controller=specialist_controller,
            assistants=assistants,
            providers=available,
            classification=classification,
            reasons=reasons,
            unavailable_capabilities=_unavailable_specialists(lowered, available),
        )

    project_provider = _project_context_provider(context, available)
    if project_provider and classification.complexity != "light":
        controller = _controller_role(project_provider, f"project_context:{project_provider.provider_id}")
        assistants = _assistant_roles(lowered, available, {project_provider.provider_id})
        reasons.append(f"project_context:{project_provider.provider_id}")
        return _decision(
            route="hybrid" if assistants else "single",
            controller=controller,
            assistants=assistants,
            providers=available,
            classification=classification,
            reasons=reasons,
        )

    if classification.complexity == "ambiguous":
        return _decision(
            route="clarify",
            controller=_none_role(),
            providers=available,
            classification=classification,
            reasons=["classification:ambiguous"],
            ask_user=True,
        )

    if classification.complexity == "light":
        return _decision(
            route="direct",
            controller=_none_role(),
            providers=available,
            classification=classification,
            reasons=["classification:light"],
        )

    controller_provider = _best_controller_provider(classification, available)
    if controller_provider is None:
        missing = {"workflow_control": "host_default_or_direct_execution"} if classification.complexity in {"heavy", "high_risk"} else {}
        return _decision(
            route="direct" if classification.complexity == "medium" else "clarify",
            controller=_none_role(),
            providers=available,
            classification=classification,
            reasons=["provider:fallback"],
            unavailable_capabilities=missing,
            ask_user=classification.complexity in {"heavy", "high_risk"},
            confidence=min(classification.confidence, 0.55),
        )

    assistants = _assistant_roles(lowered, available, {controller_provider.provider_id})
    unavailable = _unavailable_specialists(lowered, available)
    reasons.extend(_controller_reasons(controller_provider))
    return _decision(
        route="hybrid" if assistants else "single",
        controller=_controller_role(controller_provider, "best_capability_match"),
        assistants=assistants,
        providers=available,
        classification=classification,
        reasons=reasons,
        unavailable_capabilities=unavailable,
    )


def _decision(
    route: str,
    controller: ProviderRole,
    providers: List[CapabilityProvider],
    classification: RequestClassification,
    reasons: List[str],
    assistants: List[ProviderRole] | None = None,
    unavailable_capabilities: Dict[str, str] | None = None,
    explicit_user_request: bool = False,
    ask_user: bool = False,
    confidence: float | None = None,
) -> PluginCompositionDecision:
    assistants = assistants or []
    recorded_reasons = list(reasons)
    for assistant in assistants:
        assistant_reason = f"specialist_trigger:{assistant.provider_id}:{assistant.capability}"
        if assistant_reason not in recorded_reasons:
            recorded_reasons.append(assistant_reason)
    selected = {controller.provider_id, *(assistant.provider_id for assistant in assistants)}
    ignored = [
        provider.provider_id
        for provider in providers
        if provider.provider_id not in selected and provider.self_forcing_rules
    ]
    return PluginCompositionDecision(
        route=route,
        controller=controller,
        assistants=assistants,
        ignored_self_forcing=ignored,
        unavailable_capabilities=unavailable_capabilities or {},
        explicit_user_request=explicit_user_request,
        ask_user=ask_user,
        classification=classification.to_dict(),
        available_providers_snapshot=[provider.to_dict() for provider in providers],
        reasons=_dedupe(recorded_reasons),
        confidence=classification.confidence if confidence is None else confidence,
    )


def _normalize_provider(provider: CapabilityProvider | Dict[str, Any]) -> CapabilityProvider:
    if isinstance(provider, CapabilityProvider):
        source = provider.to_dict()
    else:
        source = dict(provider)
    provider_id = str(source.get("provider_id") or source.get("name") or "").strip().lower()
    capabilities = sorted({_normalize_capability(item) for item in source.get("capabilities", []) if str(item).strip()})
    aliases = [str(item).strip().lower() for item in source.get("aliases", []) if str(item).strip()]
    display_name = str(source.get("display_name") or source.get("displayName") or provider_id)
    self_forcing = [str(item) for item in source.get("self_forcing_rules", []) if str(item).strip()]
    description = str(source.get("description", ""))
    if _has_self_forcing_language(description):
        self_forcing.append(description)
    return CapabilityProvider(
        provider_id=provider_id or "unknown-provider",
        capabilities=capabilities,
        status=str(source.get("status", "available")),
        display_name=display_name,
        aliases=aliases,
        self_forcing_rules=self_forcing,
        metadata=dict(source.get("metadata", {})),
    )


def _normalize_capability(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return CAPABILITY_ALIASES.get(normalized, normalized)


def _explicit_provider_request(text: str, providers: List[CapabilityProvider]) -> CapabilityProvider | None:
    for provider in providers:
        names = {provider.provider_id, provider.display_name.lower(), *provider.aliases}
        for name in names:
            if _explicit_provider_name_match(text, name):
                return provider
    return None


def _explicit_provider_name_match(text: str, name: str) -> bool:
    normalized = str(name or "").strip().lower()
    if not normalized:
        return False
    if f"@{normalized}" in text or f"plugin://{normalized}" in text:
        return True
    if not _contains_provider_name(text, normalized):
        return False
    if _has_provider_mention_only_context(text, normalized):
        return False
    if _has_invocation_context(text, normalized):
        return True
    return not _is_common_provider_word(normalized)


def _contains_provider_name(text: str, name: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", text))


def _has_invocation_context(text: str, name: str) -> bool:
    lead = "|".join(re.escape(item) for item in EXPLICIT_PROVIDER_LEADS)
    lead_pattern = rf"(?<![a-z0-9])(?:{lead})(?:\s+(?:the|a|an))?\s+{re.escape(name)}(?![a-z0-9])"
    suffix_pattern = rf"(?<![a-z0-9]){re.escape(name)}\s+(?:plugin|tool|skill|provider|connector)(?![a-z0-9])"
    return bool(re.search(lead_pattern, text) or re.search(suffix_pattern, text))


def _has_provider_mention_only_context(text: str, name: str) -> bool:
    name_pattern = re.escape(name)
    if re.search(rf"(?<![a-z0-9]){name_pattern}\s*(?:,?\s*(?:{'|'.join(re.escape(item) for item in MENTION_ONLY_SUFFIXES)}))(?![a-z0-9])", text):
        return True
    for match in re.finditer(rf"(?<![a-z0-9]){name_pattern}(?![a-z0-9])", text):
        before = text[max(0, match.start() - 96) : match.start()]
        after = text[match.end() : min(len(text), match.end() + 96)]
        window = f"{before} {after}"
        if any(marker in window for marker in MENTION_ONLY_CONTEXT_MARKERS):
            return True
    return False


def _is_common_provider_word(name: str) -> bool:
    return (len(name) <= 3 and name.isalnum()) or name in COMMON_PROVIDER_WORDS


def _explicit_provider_is_required(text: str, provider: CapabilityProvider) -> bool:
    names = {provider.provider_id, provider.display_name.lower(), *provider.aliases}
    for name in names:
        normalized = str(name or "").strip().lower()
        if not normalized:
            continue
        if re.search(rf"(?<![a-z0-9])only\s+(?:use\s+)?{re.escape(normalized)}(?![a-z0-9])", text):
            return True
        if re.search(rf"(?<![a-z0-9]){re.escape(normalized)}\s+only(?![a-z0-9])", text):
            return True
    return False


def _project_context_provider(context: Dict[str, Any], providers: List[CapabilityProvider]) -> CapabilityProvider | None:
    markers = {str(marker).strip().lower() for marker in context.get("project_markers", [])}
    marker_preferences = [
        (".kh", "kh"),
        ("docs/kh", "kh"),
        (".superpowers", "superpowers"),
        ("docs/superpowers", "superpowers"),
    ]
    for marker, provider_id in marker_preferences:
        if marker not in markers:
            continue
        for provider in providers:
            if provider.provider_id == provider_id:
                return provider
    return None


def _best_controller_provider(
    classification: RequestClassification,
    providers: List[CapabilityProvider],
) -> CapabilityProvider | None:
    if not providers:
        return None
    scored = []
    for provider in providers:
        score = 0
        capabilities = set(provider.capabilities)
        if "workflow_control" in capabilities:
            score += 80
        if "memory_goal_resume" in capabilities and classification.complexity in {"heavy", "high_risk"}:
            score += 35
        if "domain_orchestration" in capabilities and classification.domain not in {"software", "general"}:
            score += 25
        if "tdd_review" in capabilities and classification.domain in {"software", "security", "product-design"}:
            score += 20
        if "workspace_isolation" in capabilities and classification.complexity in {"medium", "heavy", "high_risk"}:
            score += 15
        if "completion_verification" in capabilities and classification.complexity in {"medium", "heavy", "high_risk"}:
            score += 15
        if "branch_finishing" in capabilities and classification.domain == "software":
            score += 12
        if "systematic_debugging" in capabilities and classification.domain in {"software", "security"}:
            score += 12
        if "planning_methodology" in capabilities and classification.complexity in {"medium", "heavy"}:
            score += 15
        if "repo_pr_ci" in capabilities and classification.domain == "software":
            score += 10
        if capabilities & CONTROLLER_CAPABILITIES:
            score += 5
        if provider.self_forcing_rules:
            score -= 2
        scored.append((score, provider.provider_id, provider))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][2] if scored and scored[0][0] > 0 else None


def _assistant_roles(
    text: str,
    providers: List[CapabilityProvider],
    excluded_provider_ids: Set[str],
) -> List[ProviderRole]:
    roles: List[ProviderRole] = []
    used_capabilities: Set[str] = set()
    for capability, triggers in SPECIALIST_TRIGGERS.items():
        if not _contains_specialist_trigger(text, capability, triggers):
            continue
        provider = _best_provider_for_capability(capability, providers, excluded_provider_ids)
        if provider is None or capability in used_capabilities:
            continue
        used_capabilities.add(capability)
        roles.append(
            ProviderRole(
                provider_id=provider.provider_id,
                capability=capability,
                scope=_scope_for_capability(capability),
                reason=f"triggered:{capability}",
            )
        )
    return roles


def _single_specialist_controller(
    text: str,
    providers: List[CapabilityProvider],
) -> ProviderRole | None:
    roles = _assistant_roles(text, providers, set())
    if not roles:
        return None
    provider_ids = {role.provider_id for role in roles}
    if len(provider_ids) != 1:
        return None
    role = roles[0]
    return ProviderRole(
        provider_id=role.provider_id,
        capability=role.capability,
        scope=role.scope,
        reason="specialist_trigger",
    )


def _allow_single_sql_specialist_for_one_off_request(text: str, role: ProviderRole) -> bool:
    if role.capability != "sql_formatting":
        return False
    broad_markers = (
        " every ",
        " all ",
        " project",
        " folder",
        " files",
        " stored procedure",
        " procedure",
        " verification",
        " evidence",
        " commit",
        " pbl",
        " powerbuilder",
        "\\",
        "/",
        "\uc804\uccb4",
        "\ud504\ub85c\uc81d\ud2b8",
        "\ud3f4\ub354",
        "\ud30c\uc77c",
        "\ud504\ub85c\uc2dc\uc800",
        "\uac80\uc99d",
        "\uc99d\uac70",
        "\ucee4\ubc0b",
    )
    if any(marker in f" {text} " for marker in broad_markers):
        return False
    if looks_like_sql_output_request(text):
        return True
    return _looks_like_one_off_sql_style_request(text)


def _looks_like_one_off_sql_style_request(text: str) -> bool:
    normalized = f" {text.lower()} "
    return any(
        action in normalized
        for action in [
            " format ",
            " clean ",
            " cleanup ",
            " standardize ",
            " refactor ",
            " readability ",
            " align ",
        ]
    ) and any(
        marker in normalized
        for marker in [
            " sql ",
            " t-sql ",
            " tsql ",
            " query ",
        ]
    )


def _allow_single_specialist_controller(text: str, role: ProviderRole, complexity: str) -> bool:
    if role.capability == "sql_formatting":
        return _allow_single_sql_specialist_for_one_off_request(text, role)
    return complexity in {"light", "medium"}


def _unavailable_specialists(
    text: str,
    providers: List[CapabilityProvider],
) -> Dict[str, str]:
    unavailable: Dict[str, str] = {}
    for capability, triggers in SPECIALIST_TRIGGERS.items():
        if not _contains_specialist_trigger(text, capability, triggers):
            continue
        if _best_provider_for_capability(capability, providers, set()) is None:
            unavailable[capability] = SPECIALIST_FALLBACKS.get(capability, "manual_fallback")
    return unavailable


def _best_provider_for_capability(
    capability: str,
    providers: List[CapabilityProvider],
    excluded_provider_ids: Set[str],
) -> CapabilityProvider | None:
    for provider in sorted(providers, key=lambda item: item.provider_id):
        if provider.provider_id in excluded_provider_ids:
            continue
        if capability in provider.capabilities:
            return provider
    return None


def _controller_role(provider: CapabilityProvider, reason: str) -> ProviderRole:
    capability = _primary_controller_capability(provider)
    scope = "overall workflow control"
    if capability not in CONTROLLER_CAPABILITIES or capability == "sql_formatting":
        scope = _scope_for_capability(capability)
    return ProviderRole(
        provider_id=provider.provider_id,
        capability=capability,
        scope=scope,
        reason=reason,
    )


def _none_role() -> ProviderRole:
    return ProviderRole(provider_id="none", capability="", scope="direct answer or clarification")


def _primary_controller_capability(provider: CapabilityProvider) -> str:
    for capability in [
        "workflow_control",
        "memory_goal_resume",
        "domain_orchestration",
        "planning_methodology",
        "tdd_review",
        "repo_pr_ci",
        "knowledge_docs",
        "sql_formatting",
    ]:
        if capability in provider.capabilities:
            return capability
    return provider.capabilities[0] if provider.capabilities else ""


def _controller_reasons(provider: CapabilityProvider) -> List[str]:
    reasons = []
    for capability in provider.capabilities:
        if capability in CONTROLLER_CAPABILITIES:
            reasons.append(f"capability:{capability}")
    return reasons or ["capability:available_provider"]


def _scope_for_capability(capability: str) -> str:
    return {
        "browser_qa": "visual QA, screenshots, and local web verification",
        "artifact_qa": "artifact-specific QA, render checks, and structural validation",
        "repo_pr_ci": "repository, issue, pull request, CI, and publishing work",
        "knowledge_docs": "knowledge capture, wiki, and documentation storage",
        "image_generation": "bitmap image generation or image editing",
        "host_automation": "reminders, monitors, and scheduled follow-up",
        "sql_formatting": "SQL/T-SQL formatting and style normalization",
    }.get(capability, capability)


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    for needle in needles:
        if len(needle) <= 3 and needle.isalnum():
            if re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", text):
                return True
            continue
        if needle in text:
            return True
    return False


def _contains_specialist_trigger(text: str, capability: str, needles: Iterable[str]) -> bool:
    if capability == "sql_formatting" and _has_sql_meta_review_context(text):
        return False
    if capability == "sql_formatting" and looks_like_sql_output_request(text):
        return True
    for needle in needles:
        normalized = str(needle or "").strip().lower()
        if not normalized:
            continue
        if capability == "sql_formatting" and _has_negated_trigger_context(text, normalized):
            continue
        if capability == "sql_formatting" and normalized in {
            "sql-formatting",
            "sql formatting",
            "sql-formatting skill",
            "sql formatting skill",
            "t-sql formatting",
            "tsql formatting",
        }:
            if _contains_provider_name(text, normalized) and not _has_provider_mention_only_context(text, normalized):
                return True
            continue
        if len(normalized) <= 3 and normalized.isalnum():
            if re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text):
                return True
            continue
        if normalized in text:
            return True
    return False


def looks_like_sql_output_request(text: str) -> bool:
    """Detect actionable SQL/T-SQL output requests without requiring the user to name a skill."""
    lowered = str(text or "").lower()
    if _has_sql_meta_review_context(lowered):
        return False
    if _looks_like_named_dml_sql_style_request(lowered):
        return True
    if _looks_like_stored_procedure_output_request(lowered):
        return True
    if not SQL_STATEMENT_PATTERN.search(lowered) or not SQL_CONTEXT_PATTERN.search(lowered):
        return False
    if _has_sql_equivalence_question_without_output_request(lowered):
        return False
    if _has_sql_diagnostic_question_without_output_request(lowered):
        return False
    return any(marker in lowered for marker in SQL_OUTPUT_REQUEST_MARKERS)


def _looks_like_named_dml_sql_style_request(lowered: str) -> bool:
    statement_names = {match.group(0).lower() for match in SQL_NAMED_DML_PATTERN.finditer(lowered)}
    if len(statement_names) < 2:
        return False
    if not any(marker in lowered for marker in ("sql", "query", "\ucffc\ub9ac")):
        return False
    if _has_sql_equivalence_question_without_output_request(lowered):
        return False
    if _has_sql_diagnostic_question_without_output_request(lowered):
        return False
    return any(marker in lowered for marker in SQL_OUTPUT_REQUEST_MARKERS)


def _looks_like_stored_procedure_output_request(lowered: str) -> bool:
    action_markers = (
        "write",
        "create",
        "generate",
        "draft",
        "make",
        "save",
        "\uc791\uc131",
        "\ub9cc\ub4e4",
        "\uc800\uc7a5",
        "\uc815\ub9ac",
    )
    if not _has_stored_procedure_subject(lowered):
        return False
    if not any(marker in lowered for marker in action_markers):
        return False
    if _has_sql_equivalence_question_without_output_request(lowered):
        return False
    if _has_sql_diagnostic_question_without_output_request(lowered):
        return False
    return True


def _has_stored_procedure_subject(lowered: str) -> bool:
    if "stored procedure" in lowered:
        return True
    if "\ud504\ub85c\uc2dc\uc800" in lowered or "\uc800\uc7a5 \ud504\ub85c\uc2dc\uc800" in lowered:
        return True
    if re.search(r"(?<![a-z0-9_])(?:procedure|proc)(?![a-z0-9_])", lowered):
        return True
    return re.search(r"(?<![a-z0-9_])sp_[a-z0-9_]+\b", lowered) is not None


def _has_sql_meta_review_context(lowered: str) -> bool:
    meta_markers = (
        "review",
        "audit",
        "evaluate",
        "evaluation",
        "feedback",
        "risk",
        "complaint",
        "routing",
        "route",
        "classifier",
        "front-door",
        "front door",
        "session",
        "telemetry",
        "did not use",
        "unused",
        "\uac80\ud1a0",
        "\uac10\uc0ac",
        "\ud3c9\uac00",
        "\ub9ac\ubdf0",
        "\ub77c\uc6b0\ud305",
        "\ubd84\ub958",
        "\uc138\uc158",
    )
    provider_markers = ("sql-formatting", "sql formatting", "sql output", "sql verifier")
    if not any(marker in lowered for marker in meta_markers):
        return False
    return any(marker in lowered for marker in provider_markers)


def _has_sql_equivalence_question_without_output_request(lowered: str) -> bool:
    if not any(marker in lowered for marker in SQL_EQUIVALENCE_QUESTION_MARKERS):
        return False
    if any(marker in lowered for marker in ["\ubc14\uafd4\ub3c4", "\ubcc0\uacbd\ud574\ub3c4", "\ud574\ub3c4 \ub420"]):
        return True
    return not any(marker in lowered for marker in SQL_IMPERATIVE_MARKERS)


def _has_sql_diagnostic_question_without_output_request(lowered: str) -> bool:
    if not any(marker in lowered for marker in SQL_DIAGNOSTIC_QUESTION_MARKERS):
        return False
    return not any(marker in lowered for marker in SQL_IMPERATIVE_MARKERS)


def _has_negated_trigger_context(text: str, trigger: str) -> bool:
    pattern = re.escape(trigger)
    for match in re.finditer(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text):
        before = text[max(0, match.start() - 80) : match.start()]
        after = text[match.end() : min(len(text), match.end() + 80)]
        window = f"{before} {after}"
        if any(marker in window for marker in NEGATED_TRIGGER_CONTEXT_MARKERS):
            return True
    return False


def _has_self_forcing_language(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ["must use", "always use", "absolutely must", "mandatory"])


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compose a capability-based plugin route.")
    parser.add_argument("request", nargs="+", help="User request text.")
    parser.add_argument("--providers-json", default="[]", help="JSON list of capability providers.")
    args = parser.parse_args()
    providers = json.loads(args.providers_json)
    decision = compose_plugin_route(" ".join(args.request), providers=providers)
    print(json.dumps(decision.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
