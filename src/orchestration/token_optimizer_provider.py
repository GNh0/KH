from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


TOKEN_OPTIMIZER_PROVIDERS = {"kh", "rtk", "hybrid", "passthrough"}
HIGH_NOISE_COMMAND_MARKERS = (
    "pytest",
    "unittest",
    "vitest",
    "npm test",
    "npm run test",
    "cargo test",
    "go test",
    "gradle test",
    "mvn test",
    "git diff",
    "git status",
    "rg ",
    "grep ",
    "find ",
    "ls -r",
    "dir /s",
)
QUALITY_SENSITIVE_KINDS = {
    "contract-sensitive",
    "source-of-truth",
    "requirements",
    "review-finding",
    "security",
}


@dataclass(frozen=True)
class TokenOptimizerProviderDecision:
    provider: str
    requested_provider: str
    status: str
    command_strategy: str = ""
    fallback_provider: str = ""
    rationale: str = ""
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def resolve_token_optimizer_provider(
    token_optimizer_provider: str = "kh",
    command: str = "",
    content_kind: str = "auto",
    rtk_available: bool = False,
    strict: bool = False,
) -> TokenOptimizerProviderDecision:
    """Resolve the context-budget provider without requiring optional RTK runtime."""
    requested = _normalize_provider(token_optimizer_provider)
    kind = str(content_kind or "auto").strip().lower()
    command_text = str(command or "").strip()

    if requested == "passthrough":
        return _decision(
            provider="passthrough",
            requested_provider=requested,
            status="selected",
            command_strategy="quality-preserving-passthrough",
            rationale="Explicit passthrough selected; no compression is attempted.",
            command=command_text,
            content_kind=kind,
            rtk_available=rtk_available,
        )

    if kind in QUALITY_SENSITIVE_KINDS:
        return _decision(
            provider="passthrough",
            requested_provider=requested,
            status="selected",
            command_strategy="quality-preserving-passthrough",
            fallback_provider="passthrough",
            rationale="Content is quality-sensitive; exact evidence must be preserved.",
            command=command_text,
            content_kind=kind,
            rtk_available=rtk_available,
        )

    if requested == "kh":
        return _decision(
            provider="kh",
            requested_provider=requested,
            status="selected",
            command_strategy="kh-python-token-optimizer",
            rationale="Use KH's quality-first Python token optimizer.",
            command=command_text,
            content_kind=kind,
            rtk_available=rtk_available,
        )

    if requested == "rtk":
        if rtk_available:
            return _decision(
                provider="rtk",
                requested_provider=requested,
                status="selected",
                command_strategy="rtk-command-wrapper",
                rationale="Use the available RTK command-output provider.",
                command=command_text,
                content_kind=kind,
                rtk_available=rtk_available,
            )
        if strict:
            return _decision(
                provider="rtk",
                requested_provider=requested,
                status="blocked",
                command_strategy="rtk-command-wrapper",
                rationale="RTK was requested in strict mode but is not available.",
                command=command_text,
                content_kind=kind,
                rtk_available=rtk_available,
            )
        return _decision(
            provider="kh",
            requested_provider=requested,
            status="fallback",
            command_strategy="kh-python-token-optimizer",
            fallback_provider="kh",
            rationale="RTK is optional and unavailable; fall back to KH token optimizer.",
            command=command_text,
            content_kind=kind,
            rtk_available=rtk_available,
        )

    # Hybrid keeps KH as the baseline and uses RTK only when it is present and
    # the input looks like noisy command output.
    if _is_high_noise_command(command_text) and rtk_available:
        return _decision(
            provider="rtk",
            requested_provider=requested,
            status="selected",
            command_strategy="rtk-command-wrapper",
            fallback_provider="kh",
            rationale="Hybrid selected RTK for high-noise command output.",
            command=command_text,
            content_kind=kind,
            rtk_available=rtk_available,
        )
    return _decision(
        provider="kh",
        requested_provider=requested,
        status="selected" if requested == "hybrid" else "fallback",
        command_strategy="kh-python-token-optimizer",
        fallback_provider="kh" if requested != "hybrid" else "",
        rationale="Hybrid selected KH because RTK is unavailable or the content is not command-noise heavy.",
        command=command_text,
        content_kind=kind,
        rtk_available=rtk_available,
    )


def validate_token_optimizer_provider(value: str) -> Dict[str, Any]:
    provider = str(value or "").strip().lower()
    valid = provider in TOKEN_OPTIMIZER_PROVIDERS
    return {
        "valid": valid,
        "provider": provider if provider else "kh",
        "allowed": sorted(TOKEN_OPTIMIZER_PROVIDERS),
        "evidence": ["token_optimizer_provider"] if valid else [],
    }


def _normalize_provider(provider: str) -> str:
    normalized = str(provider or "kh").strip().lower()
    return normalized if normalized in TOKEN_OPTIMIZER_PROVIDERS else "hybrid"


def _is_high_noise_command(command: str) -> bool:
    lowered = command.lower()
    return any(marker in lowered for marker in HIGH_NOISE_COMMAND_MARKERS)


def _decision(
    provider: str,
    requested_provider: str,
    status: str,
    command_strategy: str,
    rationale: str,
    command: str,
    content_kind: str,
    rtk_available: bool,
    fallback_provider: str = "",
) -> TokenOptimizerProviderDecision:
    return TokenOptimizerProviderDecision(
        provider=provider,
        requested_provider=requested_provider,
        status=status,
        command_strategy=command_strategy,
        fallback_provider=fallback_provider,
        rationale=rationale,
        evidence=["token_optimizer_provider", f"provider:{provider}", f"status:{status}"],
        metadata={
            "command": command,
            "content_kind": content_kind,
            "rtk_available": rtk_available,
        },
    )
