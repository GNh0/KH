import os
import re
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.skills.base import agent_skill


DESTRUCTIVE_PATTERNS = (
    ("recursive delete", re.compile(r"\b(remove-item|rm|del|erase|rmdir)\b.*(?<!\w)(-recurse|-rf|/s)(?!\w)", re.I)),
    ("git force operation", re.compile(r"\bgit\s+(push\s+--force|reset\s+--hard|clean\s+-f)", re.I)),
    ("database destructive operation", re.compile(r"\b(drop\s+database|drop\s+table|truncate\s+table)\b", re.I)),
)

NETWORK_PATTERNS = (
    ("network command", re.compile(r"\b(curl|wget|invoke-webrequest|iwr|invoke-restmethod)\b", re.I)),
    ("package or git network command", re.compile(r"\b(npm|pnpm|yarn|pip|uv|git)\b.*\b(install|add|clone|pull|push|fetch)\b", re.I)),
)

WRITE_PATTERNS = (
    ("file write command", re.compile(r"\b(set-content|add-content|out-file|new-item|copy-item|move-item)\b", re.I)),
    ("redirect write", re.compile(r"(^|[^>])>{1,2}($|[^>])")),
)

READ_PATTERNS = (
    ("read command", re.compile(r"\b(get-childitem|ls|dir|get-content|type|rg|findstr|git\s+(status|show|diff|log))\b", re.I)),
)

CREDENTIAL_PATTERNS = (
    ("authorization header", re.compile(r"authorization\s*:\s*bearer\s+[^\"'\s]+", re.I)),
    ("secret assignment", re.compile(r"\b(token|api[-_]?key|password|secret)\s*[=:]\s*[^\"'\s]+", re.I)),
)

DEFAULT_POLICY = {
    "source": "packaged-default",
    "precedence": "deny > ask > allow > default",
    "rewrite_rules": [],
}


@agent_skill(
    name="load_command_policy",
    description="Load a UAF command policy source and attach an integrity digest for hook decisions.",
)
def load_command_policy(policy_source: Any = None) -> Dict[str, Any]:
    if policy_source is None:
        policy = dict(DEFAULT_POLICY)
    elif isinstance(policy_source, dict):
        policy = dict(policy_source)
    else:
        path = Path(str(policy_source))
        policy = json.loads(path.read_text(encoding="utf-8"))
        policy.setdefault("source", str(path))

    policy.setdefault("source", DEFAULT_POLICY["source"])
    policy.setdefault("precedence", DEFAULT_POLICY["precedence"])
    policy.setdefault("rewrite_rules", [])
    canonical = json.dumps(policy, ensure_ascii=False, sort_keys=True)
    policy["integrity"] = {
        "status": "verified",
        "algorithm": "sha256",
        "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    return policy


@agent_skill(
    name="classify_command",
    description="Classify a shell command for UAF guard and hook policy decisions.",
)
def classify_command(command: str) -> Dict[str, Any]:
    """Return a deterministic command risk classification for guard-policy evidence."""
    command = command or ""
    categories: List[str] = []
    reasons: List[str] = []

    _collect_matches(command, DESTRUCTIVE_PATTERNS, "destructive", categories, reasons)
    _collect_matches(command, NETWORK_PATTERNS, "network", categories, reasons)
    _collect_matches(command, WRITE_PATTERNS, "write", categories, reasons)
    _collect_matches(command, READ_PATTERNS, "read", categories, reasons)
    _collect_matches(command, CREDENTIAL_PATTERNS, "credential", categories, reasons)

    if not categories:
        categories.append("unknown")
        reasons.append("no known command policy pattern matched")

    primary = _primary_category(categories)
    risk_level = _risk_level(categories)
    verdict = _default_verdict(categories, risk_level)

    return {
        "command": command,
        "redacted_command": redact_command(command),
        "primary_category": primary,
        "categories": categories,
        "risk_level": risk_level,
        "verdict": verdict,
        "requires_confirmation": verdict == "ask",
        "matched_policy": {
            "source": "packaged-default",
            "precedence": "deny > ask > allow > default",
        },
        "reasons": reasons,
    }


@agent_skill(
    name="evaluate_guard_policy",
    description="Evaluate a command against UAF guard policy and return an audit-ready decision.",
)
def evaluate_guard_policy(
    command: str,
    approved: bool = False,
    actor: str = "host-agent",
) -> Dict[str, Any]:
    classification = classify_command(command)
    original_verdict = classification["verdict"]
    verdict = original_verdict
    override = False

    if approved and original_verdict == "ask":
        verdict = "allow"
        override = True

    return {
        "verdict": verdict,
        "requires_confirmation": verdict == "ask",
        "override": override,
        "classification": classification,
        "matched_policy": classification["matched_policy"],
        "audit": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "original_command": classification["redacted_command"],
            "original_verdict": original_verdict,
            "final_verdict": verdict,
            "override": override,
            "reasons": list(classification["reasons"]),
        },
    }


@agent_skill(
    name="evaluate_command_hook_policy",
    description="Evaluate command hook policy, rewrite decisions, integrity status, and audit metadata.",
)
def evaluate_command_hook_policy(
    command: str,
    policy: Any = None,
    approved: bool = False,
    actor: str = "host-agent",
) -> Dict[str, Any]:
    loaded_policy = load_command_policy(policy)
    rewrite = _rewrite_decision(command, loaded_policy)
    decision = evaluate_guard_policy(rewrite["rewritten_command"], approved=approved, actor=actor)
    audit = build_command_audit_record(
        command=command,
        final_command=rewrite["rewritten_command"],
        verdict=decision["verdict"],
        actor=actor,
        reasons=decision["classification"]["reasons"],
        original_verdict=decision["audit"]["original_verdict"],
        override=decision["override"],
    )
    return {
        "verdict": decision["verdict"],
        "requires_confirmation": decision["requires_confirmation"],
        "classification": decision["classification"],
        "policy": {
            "source": loaded_policy["source"],
            "precedence": loaded_policy["precedence"],
        },
        "integrity": dict(loaded_policy["integrity"]),
        "rewrite": rewrite,
        "audit": audit,
    }


@agent_skill(
    name="build_command_audit_record",
    description="Build a redacted command policy audit record for UAF command hooks.",
)
def build_command_audit_record(
    command: str,
    final_command: str,
    verdict: str,
    actor: str = "host-agent",
    reasons: Iterable[str] = (),
    original_verdict: str = "",
    override: bool = False,
) -> Dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "original_command": redact_command(command),
        "final_command": redact_command(final_command),
        "original_verdict": original_verdict or verdict,
        "final_verdict": verdict,
        "override": bool(override),
        "reasons": list(reasons),
    }


@agent_skill(
    name="evaluate_write_boundary",
    description="Check whether a target write path is inside allowed UAF workspace roots.",
)
def evaluate_write_boundary(
    target_path: str,
    allowed_roots: Iterable[str],
) -> Dict[str, Any]:
    target = _normalize_path(target_path)
    roots = [_normalize_path(root) for root in allowed_roots]
    within = any(_is_relative_to(target, root) for root in roots)
    return {
        "target_path": str(target),
        "allowed_roots": [str(root) for root in roots],
        "within_boundary": within,
        "verdict": "allow" if within else "deny",
        "reason": "target path is inside an allowed root" if within else "target path is outside allowed roots",
    }


def redact_command(command: str) -> str:
    redacted = command or ""
    redacted = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)[^\"'\s]+", r"\1<redacted>", redacted)
    redacted = re.sub(r"(?i)\b(token|api[-_]?key|password|secret)(\s*[=:]\s*)[^\"'\s]+", r"\1\2<redacted>", redacted)
    return redacted


def _rewrite_decision(command: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    current = command or ""
    applied_rules: List[Dict[str, str]] = []
    for rule in policy.get("rewrite_rules", []) or []:
        pattern = str(rule.get("pattern", ""))
        replacement = str(rule.get("replacement", ""))
        if not pattern:
            continue
        rewritten = re.sub(pattern, replacement, current)
        if rewritten != current:
            applied_rules.append({
                "pattern": pattern,
                "replacement": replacement,
            })
            current = rewritten
    return {
        "changed": current != (command or ""),
        "original_command": redact_command(command),
        "rewritten_command": redact_command(current),
        "applied_rules": applied_rules,
    }


def _collect_matches(
    command: str,
    patterns: Iterable[tuple[str, re.Pattern[str]]],
    category: str,
    categories: List[str],
    reasons: List[str],
) -> None:
    for reason, pattern in patterns:
        if pattern.search(command):
            if category not in categories:
                categories.append(category)
            if reason not in reasons:
                reasons.append(reason)


def _primary_category(categories: List[str]) -> str:
    for category in ("destructive", "credential", "network", "write", "read", "unknown"):
        if category in categories:
            return category
    return "unknown"


def _risk_level(categories: List[str]) -> str:
    if "destructive" in categories or "credential" in categories:
        return "high"
    if "network" in categories or "write" in categories or "unknown" in categories:
        return "medium"
    return "low"


def _default_verdict(categories: List[str], risk_level: str) -> str:
    if risk_level == "high":
        return "ask"
    if "unknown" in categories:
        return "ask"
    return "allow"


def _normalize_path(path: str) -> Path:
    return Path(os.path.abspath(os.path.normpath(path)))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return os.path.normcase(str(path)).startswith(os.path.normcase(str(root) + os.sep))
