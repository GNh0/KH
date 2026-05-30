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
    "workflow": "workflow_control",
}

CONTROLLER_CAPABILITIES = {
    "workflow_control",
    "memory_goal_resume",
    "domain_orchestration",
    "planning_methodology",
    "tdd_review",
    "repo_pr_ci",
    "knowledge_docs",
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
}

SPECIALIST_FALLBACKS = {
    "browser_qa": "manual_qa_evidence",
    "repo_pr_ci": "local_git_commands",
    "knowledge_docs": "docs_kh_markdown",
    "image_generation": "text_or_svg_artifact",
    "host_automation": "manual_follow_up_note",
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

    explicit_provider = _explicit_provider_request(lowered, provider_list)
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
        reasons=_dedupe(reasons),
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
        if not _contains_any(text, triggers):
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


def _unavailable_specialists(
    text: str,
    providers: List[CapabilityProvider],
) -> Dict[str, str]:
    unavailable: Dict[str, str] = {}
    for capability, triggers in SPECIALIST_TRIGGERS.items():
        if not _contains_any(text, triggers):
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
    return ProviderRole(
        provider_id=provider.provider_id,
        capability=capability,
        scope="overall workflow control",
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
        "repo_pr_ci": "repository, issue, pull request, CI, and publishing work",
        "knowledge_docs": "knowledge capture, wiki, and documentation storage",
        "image_generation": "bitmap image generation or image editing",
        "host_automation": "reminders, monitors, and scheduled follow-up",
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
