"""Bounded GM-27/GM-30 validator for PB event and SAVE ownership parity.

The module is deliberately standalone and dependency-free.  It validates exact
artifact bindings before inspecting source, uses small language-aware scanners,
and reports only static contract evidence.  It does not claim a live WinForms
Designer load or database behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple


CONTRACT_ID = "pb-event-save-contract"
SCHEMA_VERSION = 3
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_APPROVAL_RECEIPTS = 128
_ALLOWED_APPROVAL_RECEIPT_PRODUCERS = {"pb-event-save-host"}
_ALLOWED_APPROVAL_RECEIPT_KINDS = {"runtime_invoked_tool_receipt"}

ISSUE_ARTIFACT_PATH_INVALID = "pb_event_save_artifact_path_invalid"
ISSUE_ARTIFACT_UNREADABLE = "pb_event_save_artifact_unreadable"
ISSUE_ARTIFACT_SHA256_INVALID = "pb_event_save_artifact_sha256_invalid"
ISSUE_ARTIFACT_SHA256_MISMATCH = "pb_event_save_artifact_sha256_mismatch"
ISSUE_ARTIFACT_SOURCE_MISMATCH = "pb_event_save_artifact_source_mismatch"
ISSUE_ARTIFACT_BINDING_MISMATCH = "pb_event_save_artifact_binding_mismatch"
ISSUE_PB_EVENT_ID_INVALID = "pb_event_id_invalid"
ISSUE_PB_EVENT_ID_DUPLICATE = "pb_event_id_duplicate"
ISSUE_PB_EVENT_MAPPING_MISSING = "pb_event_mapping_missing"
ISSUE_PB_EVENT_MAPPING_DUPLICATE = "pb_event_mapping_duplicate"
ISSUE_PB_EVENT_MAPPING_UNKNOWN = "pb_event_mapping_unknown"
ISSUE_EVENT_HANDLER_UNKNOWN = "pb_event_mapping_handler_unknown"
ISSUE_EVENT_SUBSCRIPTION_UNKNOWN = "pb_event_mapping_subscription_unknown"
ISSUE_EVENT_SUBSCRIPTION_MISMATCH = "pb_event_mapping_subscription_mismatch"
ISSUE_CSHARP_HANDLER_INVENTED = "csharp_event_handler_invented"
ISSUE_CSHARP_HANDLER_NOT_FOUND = "csharp_event_handler_not_found"
ISSUE_CSHARP_HANDLER_DUPLICATE = "csharp_event_handler_duplicate"
ISSUE_CSHARP_SUBSCRIPTION_INVENTED = "csharp_event_subscription_invented"
ISSUE_CSHARP_SUBSCRIPTION_NOT_FOUND = "csharp_event_subscription_not_found"
ISSUE_CSHARP_SUBSCRIPTION_DUPLICATE = "csharp_event_subscription_duplicate"
ISSUE_APPROVAL_INVALID = "csharp_event_invention_approval_invalid"
ISSUE_APPROVAL_RECEIPT_INVALID = "csharp_event_approval_receipt_invalid"
ISSUE_APPROVAL_PROVENANCE_INVALID = "csharp_event_approval_provenance_invalid"
ISSUE_APPROVAL_PROVENANCE_DUPLICATE = "csharp_event_approval_provenance_duplicate"
ISSUE_RECEIPT_ID_INVALID = "pb_event_receipt_id_invalid"
ISSUE_RECEIPT_ID_DUPLICATE = "pb_event_receipt_id_duplicate"
ISSUE_RECEIPT_CALL_ID_DUPLICATE = "pb_event_receipt_call_id_duplicate"
ISSUE_EVENT_INVENTORY_EMPTY = "pb_event_inventory_empty"
ISSUE_OWNERSHIP_LEDGER_EMPTY = "validation_ownership_ledger_empty"
ISSUE_DESIGNER_SERIALIZER_ILLEGAL = "designer_serializer_illegal_static_ui"
ISSUE_DESIGNER_LIFECYCLE_INVALID = "designer_lifecycle_invalid"
ISSUE_DESIGNER_DISPOSAL_INVALID = "designer_disposal_invalid"
ISSUE_STATIC_UI_IN_CODE_BEHIND = "static_ui_owned_by_code_behind"
ISSUE_OWNERSHIP_RULE_INVALID = "validation_ownership_rule_invalid"
ISSUE_OWNED_RULE_MISSING = "validation_owner_executable_missing"
ISSUE_SAVE_SP_RULE_DUPLICATED_IN_CSHARP = (
    "save_sp_owned_validation_duplicated_in_csharp"
)
ISSUE_CSHARP_RULE_MOVED_TO_SAVE_SP = "csharp_owned_validation_moved_to_save_sp"

OWNER_SAVE_SP = "save_sp"
OWNER_CSHARP = "csharp"
_OWNERS = {OWNER_SAVE_SP, OWNER_CSHARP}
_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_SHA256 = re.compile(r"^(?:sha256:)?[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class ArtifactBinding:
    """Exact readable artifact, expected SHA-256, and optional supplied text."""

    path: str
    sha256: str
    source: str | None = None

    @classmethod
    def from_value(cls, value: "ArtifactBinding | Mapping[str, Any]") -> "ArtifactBinding":
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("artifact must be ArtifactBinding or a mapping")
        return cls(
            path=str(value.get("path") or value.get("source_path") or ""),
            sha256=str(value.get("sha256") or value.get("source_sha256") or ""),
            source=(
                None
                if "source" not in value and "source_text" not in value
                else str(value.get("source", value.get("source_text", "")))
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {"path": self.path, "sha256": _normalized_sha(self.sha256)}
        payload["source_supplied"] = self.source is not None
        return payload


@dataclass(frozen=True)
class ContractIssue:
    code: str
    message: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    severity: str = "error"

    def to_dict(self) -> Dict[str, Any]:
        metadata = dict(self.metadata)
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            **metadata,
            "metadata": metadata,
        }


@dataclass(frozen=True)
class EventSaveContractResult:
    allowed: bool
    issues: Tuple[ContractIssue, ...]
    metadata: Mapping[str, Any]

    @property
    def success(self) -> bool:
        return self.allowed

    @property
    def exit_code(self) -> int:
        return 0 if self.allowed else 1

    @property
    def issue_codes(self) -> Tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)

    @property
    def integration_issues(self) -> Tuple[Dict[str, Any], ...]:
        return tuple(issue.to_dict() for issue in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "success": self.success,
            "exit_code": self.exit_code,
            "issue_codes": list(self.issue_codes),
            "issues": list(self.integration_issues),
            "metadata": dict(self.metadata),
        }


def sha256_text(value: str) -> str:
    """Return the exact UTF-8 digest format accepted by artifact bindings."""

    return "sha256:" + sha256(str(value).encode("utf-8")).hexdigest()


def approval_scope_sha256(
    kind: str,
    handler: str,
    *,
    event: str = "",
    owner: str = "",
) -> str:
    """Hash the exact approved handler/subscription scope."""

    scope = {
        "event": str(event or "").strip(),
        "handler": str(handler or "").strip(),
        "kind": str(kind or "").strip().lower(),
        "owner": str(owner or "").strip().lower(),
    }
    return sha256_text(json.dumps(scope, sort_keys=True, separators=(",", ":")))


def validate_pb_event_save_contract(
    *,
    pb_event_inventory: Sequence[Mapping[str, Any]],
    event_mappings: Sequence[Mapping[str, Any]],
    csharp_event_handlers: Sequence[Mapping[str, Any]],
    csharp_event_subscriptions: Sequence[Mapping[str, Any]],
    designer_artifact: ArtifactBinding | Mapping[str, Any],
    csharp_artifact: ArtifactBinding | Mapping[str, Any],
    save_sp_artifact: ArtifactBinding | Mapping[str, Any],
    ownership_ledger: Sequence[Mapping[str, Any]],
    approved_csharp_events: Sequence[Mapping[str, Any]] = (),
    approval_execution_receipts: Sequence[Mapping[str, Any]] = (),
    approval_host_runtime_receipt: Mapping[str, Any] | None = None,
    approval_runtime_receipt: Mapping[str, Any] | None = None,
    approval_invocation_ledger: Sequence[Mapping[str, Any]] = (),
    approval_runtime_receipt_factory: Any = None,
    event_work_claimed: bool = True,
) -> EventSaveContractResult:
    """Verify GM-27 event parity/Designer legality and GM-30 ownership.

    Inventory records are mappings so callers can persist the contract as JSON.
    Every record that identifies source accepts either ``artifact={...}`` or
    ``source_path``/``source_sha256``.  Ownership rules accept language-specific
    signatures under ``csharp`` and ``save_sp``; each signature may contain
    ``predicate``, ``message``, and ``guard``.
    """

    issues: list[ContractIssue] = []
    bindings = {
        "designer": ArtifactBinding.from_value(designer_artifact),
        "csharp": ArtifactBinding.from_value(csharp_artifact),
        "save_sp": ArtifactBinding.from_value(save_sp_artifact),
    }
    verified: Dict[str, Dict[str, Any]] = {}
    sources: Dict[str, str] = {}
    for role, binding in bindings.items():
        source, evidence = _verify_artifact(role, binding, issues)
        sources[role] = source
        verified[role] = evidence

    confirmed_events = [dict(item) for item in pb_event_inventory if item.get("confirmed", True) is True]
    mappings = [dict(item) for item in event_mappings]
    handlers = [dict(item) for item in csharp_event_handlers]
    subscriptions = [dict(item) for item in csharp_event_subscriptions]
    approvals = [dict(item) for item in approved_csharp_events]

    if event_work_claimed is True and not confirmed_events:
        issues.append(
            _issue(
                ISSUE_EVENT_INVENTORY_EMPTY,
                "A claimed event migration requires a non-empty confirmed PB event inventory.",
            )
        )
    if event_work_claimed is True and not ownership_ledger:
        issues.append(
            _issue(
                ISSUE_OWNERSHIP_LEDGER_EMPTY,
                "Claimed event/SAVE parity requires a non-empty validation ownership ledger.",
            )
        )

    host_runtime_receipt, callable_produced = _resolve_approval_runtime_receipt(
        approval_host_runtime_receipt,
        approval_runtime_receipt,
        approval_runtime_receipt_factory,
        approvals=approvals,
        issues=issues,
    )

    approval_keys, approval_findings = _validate_approval_receipts(
        approvals,
        approval_execution_receipts,
        bindings=bindings,
        host_runtime_receipt=host_runtime_receipt,
        invocation_ledger=approval_invocation_ledger,
        callable_produced=callable_produced,
        issues=issues,
    )

    _validate_inventory_bindings(
        confirmed_events,
        role="pb_event",
        expected=None,
        issues=issues,
    )
    _validate_inventory_bindings(
        handlers,
        role="csharp_handler",
        expected=bindings["csharp"],
        issues=issues,
    )
    _validate_subscription_bindings(subscriptions, bindings, issues)
    _validate_event_surface(
        confirmed_events,
        mappings,
        handlers,
        subscriptions,
        approval_keys,
        designer_source=sources["designer"],
        csharp_source=sources["csharp"],
        issues=issues,
    )
    designer_findings = _validate_designer_legality(
        sources["designer"], sources["csharp"], issues
    )
    ownership_findings = _validate_ownership(
        ownership_ledger,
        bindings=bindings,
        csharp_source=sources["csharp"],
        save_sp_source=sources["save_sp"],
        issues=issues,
    )

    issues.sort(key=lambda item: (item.code, json.dumps(dict(item.metadata), sort_keys=True, default=str)))
    metadata = {
        "contract_id": CONTRACT_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if not issues else "blocked",
        "verification_scope": "static_artifact_bound_source",
        "actual_live_designer_load_observed": False,
        "database_behavior_observed": False,
        "artifact_bindings": verified,
        "counts": {
            "confirmed_pb_events": len(confirmed_events),
            "event_mappings": len(mappings),
            "csharp_handlers": len(handlers),
            "csharp_subscriptions": len(subscriptions),
            "ownership_rules": len(ownership_ledger),
        },
        "designer": designer_findings,
        "ownership": ownership_findings,
        "approvals": approval_findings,
        "issue_codes": [issue.code for issue in issues],
    }
    metadata["receipt_sha256"] = sha256_text(
        json.dumps(metadata, sort_keys=True, separators=(",", ":"), default=str)
    )
    return EventSaveContractResult(not issues, tuple(issues), metadata)


def verify_pb_event_save_contract(**kwargs: Any) -> EventSaveContractResult:
    """Compatibility alias using the repository's verifier naming convention."""

    return validate_pb_event_save_contract(**kwargs)


def _issue(code: str, message: str, **metadata: Any) -> ContractIssue:
    return ContractIssue(code=code, message=message, metadata=metadata)


def _normalized_sha(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw and not raw.startswith("sha256:"):
        raw = "sha256:" + raw
    return raw


def _path_key(value: str) -> str:
    try:
        return os.path.normcase(str(Path(value).resolve(strict=False)))
    except (OSError, RuntimeError):
        return os.path.normcase(str(value))


def _bounded_read_bytes(path: Path) -> tuple[bytes, Path]:
    resolved = path.resolve(strict=True)
    before = resolved.stat()
    if not resolved.is_file() or before.st_size > MAX_ARTIFACT_BYTES:
        raise OSError("artifact is not a bounded regular file")
    with resolved.open("rb") as stream:
        data = stream.read(MAX_ARTIFACT_BYTES + 1)
    after = resolved.stat()
    if len(data) > MAX_ARTIFACT_BYTES or len(data) != before.st_size:
        raise OSError("artifact exceeds the bounded read limit")
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OSError("artifact changed during readback")
    return data, resolved


def _verify_artifact(
    role: str,
    binding: ArtifactBinding,
    issues: list[ContractIssue],
) -> tuple[str, Dict[str, Any]]:
    evidence: Dict[str, Any] = {
        "role": role,
        **binding.to_dict(),
        "status": "blocked",
    }
    path = Path(binding.path)
    if not binding.path or not path.is_absolute():
        issues.append(
            _issue(
                ISSUE_ARTIFACT_PATH_INVALID,
                "Artifact paths must be non-empty absolute paths.",
                artifact_role=role,
                path=binding.path,
            )
        )
        return "", evidence
    expected_sha = _normalized_sha(binding.sha256)
    if not _SHA256.fullmatch(str(binding.sha256 or "").strip()):
        issues.append(
            _issue(
                ISSUE_ARTIFACT_SHA256_INVALID,
                "Artifact SHA-256 must contain exactly 64 hexadecimal digits.",
                artifact_role=role,
                path=str(path),
            )
        )
    try:
        data, resolved = _bounded_read_bytes(path)
    except (OSError, ValueError) as exc:
        issues.append(
            _issue(
                ISSUE_ARTIFACT_UNREADABLE,
                "Artifact must exist and be readable.",
                artifact_role=role,
                path=str(path),
                error_type=type(exc).__name__,
            )
        )
        return "", evidence
    actual_sha = "sha256:" + sha256(data).hexdigest()
    evidence.update(
        {
            "resolved_path": str(resolved),
            "actual_sha256": actual_sha,
            "size_bytes": len(data),
            "crlf_count": data.count(b"\r\n"),
            "lone_lf_count": data.count(b"\n") - data.count(b"\r\n"),
            "byte_exact_readback": True,
        }
    )
    if actual_sha != expected_sha:
        issues.append(
            _issue(
                ISSUE_ARTIFACT_SHA256_MISMATCH,
                "Artifact bytes do not match the declared SHA-256.",
                artifact_role=role,
                path=str(resolved),
                expected_sha256=expected_sha,
                actual_sha256=actual_sha,
            )
        )
    try:
        source = data.decode("utf-8")
    except UnicodeDecodeError:
        issues.append(
            _issue(
                ISSUE_ARTIFACT_UNREADABLE,
                "Artifact source must be UTF-8 text.",
                artifact_role=role,
                path=str(resolved),
                error_type="UnicodeDecodeError",
            )
        )
        return "", evidence
    supplied_bytes = None if binding.source is None else binding.source.encode("utf-8")
    if supplied_bytes is not None and supplied_bytes != data:
        issues.append(
            _issue(
                ISSUE_ARTIFACT_SOURCE_MISMATCH,
                "Supplied source text must equal the exact readable artifact text.",
                artifact_role=role,
                path=str(resolved),
            )
        )
    evidence["status"] = (
        "passed"
        if actual_sha == expected_sha and (supplied_bytes is None or supplied_bytes == data)
        else "blocked"
    )
    return source, evidence


def _record_binding(item: Mapping[str, Any]) -> ArtifactBinding | None:
    value = item.get("artifact")
    if isinstance(value, (ArtifactBinding, Mapping)):
        return ArtifactBinding.from_value(value)
    if item.get("source_path") or item.get("source_sha256"):
        return ArtifactBinding.from_value(item)
    return None


def _binding_equal(left: ArtifactBinding, right: ArtifactBinding) -> bool:
    return _path_key(left.path) == _path_key(right.path) and _normalized_sha(left.sha256) == _normalized_sha(right.sha256)


def _validate_inventory_bindings(
    items: Sequence[Mapping[str, Any]],
    *,
    role: str,
    expected: ArtifactBinding | None,
    issues: list[ContractIssue],
) -> None:
    cache: set[tuple[str, str]] = set()
    for index, item in enumerate(items):
        binding = _record_binding(item)
        if binding is None:
            issues.append(
                _issue(
                    ISSUE_ARTIFACT_BINDING_MISMATCH,
                    "Every inventory record must carry an exact path/SHA artifact binding.",
                    inventory_role=role,
                    inventory_index=index,
                )
            )
            continue
        if expected is not None and not _binding_equal(binding, expected):
            issues.append(
                _issue(
                    ISSUE_ARTIFACT_BINDING_MISMATCH,
                    "Inventory binding does not match its exact candidate artifact.",
                    inventory_role=role,
                    inventory_index=index,
                    expected_path=expected.path,
                    actual_path=binding.path,
                )
            )
        if expected is None:
            key = (_path_key(binding.path), _normalized_sha(binding.sha256))
            if key not in cache:
                _verify_artifact(role, binding, issues)
                cache.add(key)


def _validate_subscription_bindings(
    subscriptions: Sequence[Mapping[str, Any]],
    bindings: Mapping[str, ArtifactBinding],
    issues: list[ContractIssue],
) -> None:
    for index, item in enumerate(subscriptions):
        owner = str(item.get("owner") or item.get("source_owner") or "").strip().lower()
        expected = bindings.get(owner)
        binding = _record_binding(item)
        if owner not in {"designer", "csharp"} or binding is None or expected is None or not _binding_equal(binding, expected):
            issues.append(
                _issue(
                    ISSUE_ARTIFACT_BINDING_MISMATCH,
                    "Subscriptions must bind to the exact Designer or C# artifact declared as owner.",
                    inventory_role="csharp_subscription",
                    inventory_index=index,
                    owner=owner,
                )
            )


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _approval_key(
    kind: str, handler: str, *, event: str = "", owner: str = ""
) -> tuple[str, str, str, str]:
    return kind, owner.strip().lower(), event.strip(), handler.strip()


def _resolve_approval_runtime_receipt(
    host_runtime_receipt: Mapping[str, Any] | None,
    runtime_receipt: Mapping[str, Any] | None,
    receipt_factory: Any,
    *,
    approvals: Sequence[Mapping[str, Any]],
    issues: list[ContractIssue],
) -> tuple[Mapping[str, Any] | None, bool]:
    if not approvals:
        return None, False
    supplied = [
        item for item in (host_runtime_receipt, runtime_receipt) if item is not None
    ]
    if len(supplied) > 1:
        issues.append(
            _issue(
                ISSUE_APPROVAL_PROVENANCE_INVALID,
                "Approval provenance must have one independently supplied host/runtime receipt.",
            )
        )
        return None, False
    if receipt_factory is not None:
        if supplied or not callable(receipt_factory):
            issues.append(
                _issue(
                    ISSUE_APPROVAL_PROVENANCE_INVALID,
                    "Approval provenance must come from one host receipt or one callable-produced receipt.",
                )
            )
            return None, False
        try:
            produced = receipt_factory()
        except Exception as exc:  # pragma: no cover - defensive host boundary
            issues.append(
                _issue(
                    ISSUE_APPROVAL_PROVENANCE_INVALID,
                    "The host/runtime approval receipt callable failed.",
                    error_type=type(exc).__name__,
                )
            )
            return None, False
        if not isinstance(produced, Mapping):
            issues.append(
                _issue(
                    ISSUE_APPROVAL_PROVENANCE_INVALID,
                    "The host/runtime approval receipt callable must return a mapping.",
                )
            )
            return None, False
        return produced, True
    if not supplied or not isinstance(supplied[0], Mapping):
        issues.append(
            _issue(
                ISSUE_APPROVAL_PROVENANCE_INVALID,
                "A separately supplied host/runtime approval receipt is required; caller JSON alone is not proof.",
            )
        )
        return None, False
    return supplied[0], False


def _provenance_field(receipt: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = str(receipt.get(name) or "").strip()
        if value:
            return value
    return ""


def _validate_invocation_ledger(
    ledger: Sequence[Mapping[str, Any]],
    *,
    issues: list[ContractIssue],
) -> Dict[str, Mapping[str, Any]]:
    by_call: Dict[str, Mapping[str, Any]] = {}
    indexes: Dict[str, Dict[str, list[int]]] = {
        "receipt_id": {},
        "tool_call_id": {},
        "tool_result_id": {},
    }
    for index, item in enumerate(ledger):
        if not isinstance(item, Mapping):
            issues.append(
                _issue(
                    ISSUE_APPROVAL_PROVENANCE_INVALID,
                    "Approval invocation ledger entries must be mappings supplied by the host/runtime.",
                    ledger_index=index,
                )
            )
            continue
        normalized = {
            "receipt_id": _provenance_field(item, "receipt_id", "host_receipt_id"),
            "tool_call_id": _provenance_field(item, "tool_call_id", "call_id"),
            "tool_result_id": _provenance_field(item, "tool_result_id", "result_id"),
            "producer": _provenance_field(item, "producer", "producer_name").lower(),
            "kind": _provenance_field(item, "kind", "receipt_kind").lower(),
            "runtime_invoked": item.get("runtime_invoked"),
        }
        for identity, value in normalized.items():
            if identity in indexes and value:
                indexes[identity].setdefault(value, []).append(index)
        if (
            not normalized["receipt_id"]
            or not normalized["tool_call_id"]
            or not normalized["tool_result_id"]
            or len({normalized["receipt_id"], normalized["tool_call_id"], normalized["tool_result_id"]}) != 3
            or normalized["producer"] not in _ALLOWED_APPROVAL_RECEIPT_PRODUCERS
            or normalized["kind"] not in _ALLOWED_APPROVAL_RECEIPT_KINDS
            or normalized["runtime_invoked"] is not True
        ):
            issues.append(
                _issue(
                    ISSUE_APPROVAL_PROVENANCE_INVALID,
                    "Invocation ledger entries require allowlisted producer/kind, runtime invocation, and distinct receipt/call/result IDs.",
                    ledger_index=index,
                )
            )
        if normalized["tool_call_id"]:
            by_call.setdefault(normalized["tool_call_id"], item)
    for identity, identity_indexes in indexes.items():
        for value, duplicate_indexes in sorted(identity_indexes.items()):
            if len(duplicate_indexes) > 1:
                issues.append(
                    _issue(
                        ISSUE_APPROVAL_PROVENANCE_DUPLICATE,
                        "Approval invocation ledger receipt, call, and result IDs must be unique.",
                        identity=identity,
                        value=value,
                        ledger_indexes=duplicate_indexes,
                    )
                )
    return by_call


def _validate_approval_runtime_provenance(
    host: Mapping[str, Any] | None,
    ledger_by_call: Mapping[str, Mapping[str, Any]],
    *,
    approval: Mapping[str, Any],
    execution_receipt: Mapping[str, Any],
    expected_binding: ArtifactBinding | None,
    output_evidence: Mapping[str, Any],
) -> tuple[Dict[str, Any], list[ContractIssue]]:
    local: list[ContractIssue] = []
    evidence: Dict[str, Any] = {"status": "blocked"}
    if not isinstance(host, Mapping):
        local.append(
            _issue(
                ISSUE_APPROVAL_PROVENANCE_INVALID,
                "Explicit approval requires a separately supplied host/runtime provenance receipt.",
            )
        )
        return evidence, local

    approval_id = str(approval.get("approval_id") or "").strip()
    call_id = str(approval.get("call_id") or "").strip()
    receipt_id = _provenance_field(host, "receipt_id", "host_receipt_id")
    tool_call_id = _provenance_field(host, "tool_call_id", "call_id")
    tool_result_id = _provenance_field(host, "tool_result_id", "result_id")
    producer = _provenance_field(host, "producer", "producer_name").lower()
    kind = _provenance_field(host, "kind", "receipt_kind").lower()
    target_kind = _provenance_field(host, "target_kind", "approval_kind").lower()
    handler = _handler_name(host)
    event = _event_name(host)
    owner = _provenance_field(host, "owner", "source_owner").lower()
    scope_sha = _normalized_sha(
        _provenance_field(
            host,
            "approved_handler_scope_sha256",
            "approved_scope_sha256",
            "handler_scope_sha256",
            "scope_sha256",
        )
    )
    artifact_path = _provenance_field(
        host,
        "approval_artifact_path",
        "approved_artifact_path",
        "artifact_path",
        "target_path",
    )
    artifact_sha = _normalized_sha(
        _provenance_field(
            host,
            "approval_artifact_sha256",
            "approved_artifact_sha256",
            "artifact_sha256",
            "target_sha256",
        )
    )
    output_path = _provenance_field(host, "output_path")
    output_sha = _normalized_sha(_provenance_field(host, "output_sha256"))
    timestamp = _timestamp(host.get("timestamp") or host.get("observed_at"))
    exit_status = host.get("exit_status", host.get("exit_code"))
    evidence.update(
        {
            "producer": producer,
            "kind": kind,
            "receipt_id": receipt_id,
            "tool_call_id": tool_call_id,
            "tool_result_id": tool_result_id,
        }
    )
    ledger_item = ledger_by_call.get(tool_call_id)
    ledger_call = _provenance_field(ledger_item or {}, "tool_call_id", "call_id")
    ledger_result = _provenance_field(ledger_item or {}, "tool_result_id", "result_id")
    expected_scope = approval_scope_sha256(
        target_kind or str(approval.get("kind") or ""),
        _handler_name(approval),
        event=_event_name(approval),
        owner=str(approval.get("owner") or approval.get("source_owner") or ""),
    )
    expected_artifact_path = expected_binding.path if expected_binding else ""
    expected_artifact_sha = _normalized_sha(expected_binding.sha256 if expected_binding else "")
    if (
        producer not in _ALLOWED_APPROVAL_RECEIPT_PRODUCERS
        or kind not in _ALLOWED_APPROVAL_RECEIPT_KINDS
        or host.get("runtime_invoked") is not True
        or not receipt_id
        or not tool_call_id
        or not tool_result_id
        or len({receipt_id, tool_call_id, tool_result_id}) != 3
        or receipt_id in {approval_id, str(execution_receipt.get("receipt_id") or "").strip()}
        or tool_call_id in {approval_id, str(execution_receipt.get("receipt_id") or "").strip()}
        or tool_result_id in {approval_id, str(execution_receipt.get("receipt_id") or "").strip()}
        or tool_call_id != call_id
        or not ledger_item
        or ledger_call != tool_call_id
        or ledger_result != tool_result_id
        or _provenance_field(ledger_item, "receipt_id", "host_receipt_id") != receipt_id
        or _provenance_field(ledger_item, "producer", "producer_name").lower() != producer
        or _provenance_field(ledger_item, "kind", "receipt_kind").lower() != kind
        or ledger_item.get("runtime_invoked") is not True
        or str(host.get("approval_id") or "").strip() != approval_id
        or target_kind != str(approval.get("kind") or "").strip().lower()
        or handler != _handler_name(approval)
        or event != _event_name(approval)
        or owner != str(approval.get("owner") or approval.get("source_owner") or "").strip().lower()
        or not _SHA256.fullmatch(scope_sha)
        or scope_sha != expected_scope
        or not artifact_path
        or not Path(artifact_path).is_absolute()
        or _path_key(artifact_path) != _path_key(expected_artifact_path)
        or not _SHA256.fullmatch(artifact_sha)
        or artifact_sha != expected_artifact_sha
        or not output_path
        or not Path(output_path).is_absolute()
        or _path_key(output_path) != _path_key(str(output_evidence.get("path") or ""))
        or not _SHA256.fullmatch(output_sha)
        or output_sha != _normalized_sha(str(execution_receipt.get("output_sha256") or ""))
        or timestamp is None
        or _timestamp(execution_receipt.get("observed_at")) != timestamp
        or isinstance(exit_status, bool)
        or exit_status != 0
    ):
        local.append(
            _issue(
                ISSUE_APPROVAL_PROVENANCE_INVALID,
                "Approval requires allowlisted host/runtime provenance bound to a separate invocation ledger, exact artifact/output bytes, approved scope, timestamp, and exit status.",
                call_id=call_id,
            )
        )
    try:
        artifact_bytes, resolved = _bounded_read_bytes(Path(artifact_path))
        actual_artifact_sha = "sha256:" + sha256(artifact_bytes).hexdigest()
        evidence["artifact_path"] = str(resolved)
        evidence["artifact_sha256"] = actual_artifact_sha
        if actual_artifact_sha != artifact_sha:
            local.append(
                _issue(
                    ISSUE_APPROVAL_PROVENANCE_INVALID,
                    "Host approval provenance artifact hash does not match exact readback bytes.",
                    call_id=call_id,
                )
            )
    except (OSError, ValueError):
        local.append(
            _issue(
                ISSUE_APPROVAL_PROVENANCE_INVALID,
                "Host approval provenance must identify a readable exact approval artifact.",
                call_id=call_id,
            )
        )
    host_output, host_output_evidence, host_output_issues = _receipt_output(
        host, "approval_host_runtime_receipt"
    )
    local.extend(host_output_issues)
    if host_output_issues:
        local.append(
            _issue(
                ISSUE_APPROVAL_PROVENANCE_INVALID,
                "Host approval provenance output must pass the exact byte-hash readback check.",
                call_id=call_id,
            )
        )
    evidence["output"] = host_output_evidence
    if host_output is not None and host_output_evidence.get("readback_sha256") != output_sha:
        local.append(
            _issue(
                ISSUE_APPROVAL_PROVENANCE_INVALID,
                "Host approval provenance output hash must match exact output readback bytes.",
                call_id=call_id,
            )
        )
    evidence["status"] = "passed" if not local else "blocked"
    return evidence, local


def _receipt_output(
    receipt: Mapping[str, Any], field: str
) -> tuple[Mapping[str, Any] | None, Dict[str, Any], list[ContractIssue]]:
    local: list[ContractIssue] = []
    path_text = str(receipt.get("output_path") or "").strip()
    expected_sha = _normalized_sha(str(receipt.get("output_sha256") or ""))
    evidence: Dict[str, Any] = {
        "path": path_text,
        "requested_sha256": expected_sha,
        "readback_sha256": "",
        "size_bytes": 0,
    }
    if not path_text or not Path(path_text).is_absolute():
        local.append(
            _issue(
                ISSUE_APPROVAL_RECEIPT_INVALID,
                "Approval execution output requires an exact absolute path.",
                field=f"{field}.output_path",
            )
        )
        return None, evidence, local
    if not _SHA256.fullmatch(str(receipt.get("output_sha256") or "").strip()):
        local.append(
            _issue(
                ISSUE_APPROVAL_RECEIPT_INVALID,
                "Approval execution output requires a complete SHA-256.",
                field=f"{field}.output_sha256",
            )
        )
    try:
        payload, resolved = _bounded_read_bytes(Path(path_text))
        actual_sha = "sha256:" + sha256(payload).hexdigest()
        evidence.update(
            {
                "path": str(resolved),
                "readback_sha256": actual_sha,
                "size_bytes": len(payload),
            }
        )
        if actual_sha != expected_sha:
            local.append(
                _issue(
                    ISSUE_APPROVAL_RECEIPT_INVALID,
                    "Approval output hash does not match exact readback bytes.",
                    field=f"{field}.output_sha256",
                )
            )
        if not payload.strip():
            raise ValueError("empty approval output")
        parsed = json.loads(payload.decode("utf-8"))
        if not isinstance(parsed, Mapping):
            raise ValueError("approval output is not an object")
    except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        local.append(
            _issue(
                ISSUE_APPROVAL_RECEIPT_INVALID,
                "Approval execution output must be readable, bounded, non-empty UTF-8 JSON.",
                field=f"{field}.output_path",
                error_type=type(exc).__name__,
            )
        )
        return None, evidence, local
    return parsed, evidence, local


def _validate_approval_receipts(
    approvals: Sequence[Mapping[str, Any]],
    execution_receipts: Sequence[Mapping[str, Any]],
    *,
    bindings: Mapping[str, ArtifactBinding],
    host_runtime_receipt: Mapping[str, Any] | None,
    invocation_ledger: Sequence[Mapping[str, Any]],
    callable_produced: bool,
    issues: list[ContractIssue],
) -> tuple[set[tuple[str, str, str, str]], list[Dict[str, Any]]]:
    receipts: list[Mapping[str, Any]] = []
    for index, item in enumerate(execution_receipts):
        if not isinstance(item, Mapping):
            issues.append(
                _issue(
                    ISSUE_APPROVAL_RECEIPT_INVALID,
                    "Approval execution receipts must be structured mappings supplied separately from caller approval JSON.",
                    receipt_index=index,
                )
            )
            continue
        receipts.append(item)
    for index, approval in enumerate(approvals):
        if isinstance(approval.get("execution_receipt"), Mapping):
            issues.append(
                _issue(
                    ISSUE_APPROVAL_RECEIPT_INVALID,
                    "Caller approval JSON may not carry its own execution receipt.",
                    approval_index=index,
                )
            )

    ledger_records = list(invocation_ledger)
    if approvals and not ledger_records and not callable_produced:
        issues.append(
            _issue(
                ISSUE_APPROVAL_PROVENANCE_INVALID,
                "Approval provenance requires a separate invocation ledger or a callable-produced host receipt.",
            )
        )
    if callable_produced and isinstance(host_runtime_receipt, Mapping):
        ledger_records = [host_runtime_receipt]
    ledger_by_call = _validate_invocation_ledger(ledger_records, issues=issues)

    if len(receipts) > MAX_APPROVAL_RECEIPTS:
        issues.append(
            _issue(
                ISSUE_APPROVAL_RECEIPT_INVALID,
                "Approval execution receipts exceed the bounded maximum.",
                receipt_count=len(receipts),
            )
        )
        receipts = receipts[:MAX_APPROVAL_RECEIPTS]

    call_indexes: Dict[str, list[int]] = {}
    receipt_indexes: Dict[str, list[int]] = {}
    for index, receipt in enumerate(receipts):
        receipt_id = str(receipt.get("receipt_id") or "").strip()
        call_id = str(receipt.get("call_id") or "").strip()
        if not receipt_id:
            issues.append(
                _issue(
                    ISSUE_RECEIPT_ID_INVALID,
                    "Each approval execution receipt requires a non-empty receipt_id.",
                    receipt_index=index,
                )
            )
        receipt_indexes.setdefault(receipt_id, []).append(index)
        call_indexes.setdefault(call_id, []).append(index)
    duplicate_receipt_ids = {
        receipt_id
        for receipt_id, indexes in receipt_indexes.items()
        if receipt_id and len(indexes) > 1
    }
    for receipt_id in sorted(duplicate_receipt_ids):
        issues.append(
            _issue(
                ISSUE_RECEIPT_ID_DUPLICATE,
                "Each approval execution must have one unique receipt_id.",
                receipt_id=receipt_id,
                receipt_indexes=receipt_indexes[receipt_id],
            )
        )
    duplicate_calls = {
        call_id for call_id, indexes in call_indexes.items() if call_id and len(indexes) > 1
    }
    for call_id in sorted(duplicate_calls):
        issues.append(
            _issue(
                ISSUE_RECEIPT_CALL_ID_DUPLICATE,
                "Each approval execution must have one unique call_id receipt.",
                call_id=call_id,
                receipt_indexes=call_indexes[call_id],
            )
        )
    receipts_by_call = {
        call_id: receipts[indexes[0]]
        for call_id, indexes in call_indexes.items()
        if call_id
        and len(indexes) == 1
        and str(receipts[indexes[0]].get("receipt_id") or "").strip()
        and str(receipts[indexes[0]].get("receipt_id") or "").strip()
        not in duplicate_receipt_ids
    }

    approval_ids: Dict[str, list[int]] = {}
    approval_targets: Dict[tuple[str, str, str, str], list[int]] = {}
    for index, approval in enumerate(approvals):
        approval_id = str(approval.get("approval_id") or "").strip()
        kind = str(approval.get("kind") or "").strip().lower()
        handler = _handler_name(approval)
        event = _event_name(approval)
        owner = str(approval.get("owner") or approval.get("source_owner") or "").strip().lower()
        approval_ids.setdefault(approval_id, []).append(index)
        approval_targets.setdefault(_approval_key(kind, handler, event=event, owner=owner), []).append(index)
    duplicate_approval_indexes: set[int] = set()
    for approval_id, indexes in approval_ids.items():
        if approval_id and len(indexes) > 1:
            duplicate_approval_indexes.update(indexes)
            issues.append(
                _issue(
                    ISSUE_APPROVAL_INVALID,
                    "Approval IDs must be unique before approval lookup construction.",
                    approval_id=approval_id,
                    approval_indexes=indexes,
                )
            )
    for target, indexes in approval_targets.items():
        if target[0] and target[3] and len(indexes) > 1:
            duplicate_approval_indexes.update(indexes)
            issues.append(
                _issue(
                    ISSUE_APPROVAL_INVALID,
                    "Approval targets must be unique before approval lookup construction.",
                    target=target,
                    approval_indexes=indexes,
                )
            )

    valid: set[tuple[str, str, str, str]] = set()
    findings: list[Dict[str, Any]] = []
    used_calls: set[str] = set()
    for index, approval in enumerate(approvals):
        local: list[ContractIssue] = []
        approval_id = str(approval.get("approval_id") or "").strip()
        call_id = str(approval.get("call_id") or "").strip()
        receipt_id = str(approval.get("receipt_id") or "").strip()
        kind = str(approval.get("kind") or "").strip().lower()
        handler = _handler_name(approval)
        event = _event_name(approval)
        owner = str(approval.get("owner") or approval.get("source_owner") or "").strip().lower()
        target_key = _approval_key(kind, handler, event=event, owner=owner)
        if (
            approval.get("approved") is not True
            or not approval_id
            or not call_id
            or not receipt_id
            or kind not in {"handler", "subscription"}
            or not handler
            or (kind == "subscription" and (not event or owner not in {"designer", "csharp"}))
            or index in duplicate_approval_indexes
        ):
            local.append(
                _issue(
                    ISSUE_APPROVAL_INVALID,
                    "Approval intent requires a unique approval_id/call_id and exact event target; approved=true alone is insufficient.",
                    approval_index=index,
                )
            )
        receipt = receipts_by_call.get(call_id)
        if receipt is None or call_id in duplicate_calls:
            local.append(
                _issue(
                    ISSUE_APPROVAL_RECEIPT_INVALID,
                    "Approval intent must correlate to one unique execution receipt.",
                    approval_index=index,
                    call_id=call_id,
                )
            )
            receipt = {}
        used_calls.add(call_id)

        expected_binding = bindings.get("csharp" if kind == "handler" else owner)
        observed_at = _timestamp(receipt.get("observed_at"))
        exit_code = receipt.get("exit_code")
        if (
            str(receipt.get("receipt_id") or "").strip() != receipt_id
            or str(receipt.get("call_id") or "").strip() != call_id
            or str(receipt.get("approval_id") or "").strip() != approval_id
            or str(receipt.get("kind") or "").strip().lower() != kind
            or _handler_name(receipt) != handler
            or _event_name(receipt) != event
            or str(receipt.get("owner") or receipt.get("source_owner") or "").strip().lower() != owner
            or expected_binding is None
            or _path_key(str(receipt.get("target_path") or "")) != _path_key(expected_binding.path if expected_binding else "")
            or _normalized_sha(str(receipt.get("target_sha256") or "")) != _normalized_sha(expected_binding.sha256 if expected_binding else "")
            or observed_at is None
            or isinstance(exit_code, bool)
            or exit_code != 0
        ):
            local.append(
                _issue(
                    ISSUE_APPROVAL_RECEIPT_INVALID,
                    "Approval receipt must bind unique receipt/call IDs, decision target, exact artifact path/hash, timezone-aware time, and exit_code=0.",
                    approval_index=index,
                    call_id=call_id,
                )
            )

        output, output_evidence, output_issues = _receipt_output(
            receipt, f"approval_execution_receipts[{index}]"
        )
        local.extend(output_issues)
        if output is not None:
            output_time = _timestamp(output.get("observed_at"))
            if (
                str(output.get("receipt_id") or "").strip() != receipt_id
                or str(output.get("call_id") or "").strip() != call_id
                or str(output.get("approval_id") or "").strip() != approval_id
                or str(output.get("decision") or "").strip().lower() != "approved"
                or str(output.get("kind") or "").strip().lower() != kind
                or _handler_name(output) != handler
                or _event_name(output) != event
                or str(output.get("owner") or output.get("source_owner") or "").strip().lower() != owner
                or expected_binding is None
                or _path_key(str(output.get("target_path") or "")) != _path_key(expected_binding.path if expected_binding else "")
                or _normalized_sha(str(output.get("target_sha256") or "")) != _normalized_sha(expected_binding.sha256 if expected_binding else "")
                or output_time is None
                or observed_at is None
                or output_time != observed_at
            ):
                local.append(
                    _issue(
                        ISSUE_APPROVAL_RECEIPT_INVALID,
                        "Observable approval output must exactly echo the correlated call, target, artifact, decision, and time.",
                        approval_index=index,
                        call_id=call_id,
                    )
                )
        provenance_evidence, provenance_issues = _validate_approval_runtime_provenance(
            host_runtime_receipt,
            ledger_by_call,
            approval=approval,
            execution_receipt=receipt,
            expected_binding=expected_binding,
            output_evidence=output_evidence,
        )
        local.extend(provenance_issues)
        issues.extend(local)
        if not local:
            valid.add(target_key)
        findings.append(
                {
                    "approval_id": approval_id,
                    "call_id": call_id,
                    "receipt_id": receipt_id,
                "target": target_key,
                "status": "passed" if not local else "blocked",
                "output": output_evidence,
                "provenance": provenance_evidence,
            }
        )

    for call_id, indexes in sorted(call_indexes.items()):
        if call_id and call_id not in used_calls:
            issues.append(
                _issue(
                    ISSUE_APPROVAL_RECEIPT_INVALID,
                    "Approval execution receipts may not target an unknown approval.",
                    call_id=call_id,
                    receipt_indexes=indexes,
                )
            )
    return valid, findings


def _approved(
    approvals: set[tuple[str, str, str, str]],
    *,
    kind: str,
    handler: str,
    event: str = "",
    owner: str = "",
) -> bool:
    return _approval_key(kind, handler, event=event, owner=owner) in approvals


def _event_id(item: Mapping[str, Any]) -> str:
    return str(item.get("event_id") or item.get("pb_event_id") or "").strip()


def _handler_name(item: Mapping[str, Any]) -> str:
    return str(item.get("handler") or item.get("handler_name") or item.get("method_name") or "").strip()


def _subscription_id(item: Mapping[str, Any]) -> str:
    return str(item.get("subscription_id") or item.get("id") or "").strip()


def _event_name(item: Mapping[str, Any]) -> str:
    return str(item.get("csharp_event") or item.get("event_name") or item.get("event") or "").strip()


def _validate_event_surface(
    events: Sequence[Mapping[str, Any]],
    mappings: Sequence[Mapping[str, Any]],
    handlers: Sequence[Mapping[str, Any]],
    subscriptions: Sequence[Mapping[str, Any]],
    approvals: set[tuple[str, str, str, str]],
    *,
    designer_source: str,
    csharp_source: str,
    issues: list[ContractIssue],
) -> None:
    event_ids: Dict[str, list[int]] = {}
    for index, item in enumerate(events):
        event_id = _event_id(item)
        if not event_id:
            issues.append(_issue(ISSUE_PB_EVENT_ID_INVALID, "Confirmed PB events require a stable event_id.", event_index=index))
        event_ids.setdefault(event_id, []).append(index)
    for event_id, indexes in sorted(event_ids.items()):
        if event_id and len(indexes) != 1:
            issues.append(_issue(ISSUE_PB_EVENT_ID_DUPLICATE, "Confirmed PB event IDs must be unique.", event_id=event_id, event_indexes=indexes))

    mappings_by_event: Dict[str, list[Mapping[str, Any]]] = {}
    for mapping in mappings:
        mappings_by_event.setdefault(_event_id(mapping), []).append(mapping)
    for event_id in sorted(key for key in event_ids if key):
        count = len(mappings_by_event.get(event_id, ()))
        if count == 0:
            issues.append(_issue(ISSUE_PB_EVENT_MAPPING_MISSING, "Every confirmed PB event must be mapped exactly once.", event_id=event_id, mapping_count=0))
        elif count != 1:
            issues.append(_issue(ISSUE_PB_EVENT_MAPPING_DUPLICATE, "Every confirmed PB event must be mapped exactly once.", event_id=event_id, mapping_count=count))
    for event_id, values in sorted(mappings_by_event.items()):
        if event_id not in event_ids:
            issues.append(_issue(ISSUE_PB_EVENT_MAPPING_UNKNOWN, "Mappings may reference only confirmed PB events.", event_id=event_id, mapping_count=len(values)))

    handler_indexes: Dict[str, list[int]] = {}
    for index, item in enumerate(handlers):
        handler_indexes.setdefault(_handler_name(item), []).append(index)
    duplicate_handlers = {
        name for name, indexes in handler_indexes.items() if len(indexes) > 1
    }
    for name in sorted(duplicate_handlers):
        issues.append(
            _issue(
                ISSUE_CSHARP_HANDLER_DUPLICATE,
                "C# handler inventory names must be unique before handler lookup construction.",
                handler=name,
                handler_indexes=handler_indexes[name],
            )
        )

    subscription_id_indexes: Dict[str, list[int]] = {}
    subscription_pair_indexes: Dict[tuple[str, str, str], list[int]] = {}
    for index, item in enumerate(subscriptions):
        subscription_id_indexes.setdefault(_subscription_id(item), []).append(index)
        pair = (
            str(item.get("owner") or item.get("source_owner") or "").strip().lower(),
            _event_name(item),
            _handler_name(item),
        )
        subscription_pair_indexes.setdefault(pair, []).append(index)
    duplicate_subscription_indexes: set[int] = set()
    for subscription_id, indexes in sorted(subscription_id_indexes.items()):
        if len(indexes) > 1:
            duplicate_subscription_indexes.update(indexes)
            issues.append(
                _issue(
                    ISSUE_CSHARP_SUBSCRIPTION_DUPLICATE,
                    "Subscription IDs must be unique before subscription lookup construction.",
                    subscription_id=subscription_id,
                    subscription_indexes=indexes,
                )
            )
    for pair, indexes in sorted(subscription_pair_indexes.items()):
        if all(pair) and len(indexes) > 1:
            duplicate_subscription_indexes.update(indexes)
            issues.append(
                _issue(
                    ISSUE_CSHARP_SUBSCRIPTION_DUPLICATE,
                    "Subscription owner/event/handler targets must be unique before lookup construction.",
                    owner=pair[0],
                    event=pair[1],
                    handler=pair[2],
                    subscription_indexes=indexes,
                )
            )

    handlers_by_name = {
        name: handlers[indexes[0]]
        for name, indexes in handler_indexes.items()
        if name and len(indexes) == 1
    }
    subscriptions_by_id = {
        subscription_id: subscriptions[indexes[0]]
        for subscription_id, indexes in subscription_id_indexes.items()
        if subscription_id and len(indexes) == 1
    }
    mapped_handlers: set[str] = set()
    mapped_subscriptions: set[str] = set()
    for mapping_index, mapping in enumerate(mappings):
        handler = _handler_name(mapping)
        subscription_id = _subscription_id(mapping)
        subscription = subscriptions_by_id.get(subscription_id)
        if handler not in handlers_by_name:
            issues.append(_issue(ISSUE_EVENT_HANDLER_UNKNOWN, "Event mappings must reference an inventoried C# handler.", mapping_index=mapping_index, handler=handler))
        else:
            mapped_handlers.add(handler)
        if subscription is None:
            issues.append(_issue(ISSUE_EVENT_SUBSCRIPTION_UNKNOWN, "Event mappings must reference an inventoried subscription.", mapping_index=mapping_index, subscription_id=subscription_id))
        else:
            mapped_subscriptions.add(subscription_id)
            if _handler_name(subscription) != handler or (
                _event_name(mapping) and _event_name(subscription) != _event_name(mapping)
            ):
                issues.append(_issue(ISSUE_EVENT_SUBSCRIPTION_MISMATCH, "Mapped handler/event must match the exact subscription record.", mapping_index=mapping_index, subscription_id=subscription_id, handler=handler))

    active_csharp = _mask_csharp_comments_and_strings(csharp_source)
    declared_handlers = _find_event_handler_declarations(active_csharp)
    actual_subscriptions = _find_csharp_subscriptions(designer_source, "designer") + _find_csharp_subscriptions(csharp_source, "csharp")

    for index, item in enumerate(handlers):
        name = _handler_name(item)
        approved = _approved(approvals, kind="handler", handler=name)
        if name not in mapped_handlers and not approved:
            issues.append(_issue(ISSUE_CSHARP_HANDLER_INVENTED, "Unmapped C# event handlers require explicit approval evidence.", handler=name, handler_index=index))
        if name and declared_handlers.count(name) != 1:
            issues.append(_issue(ISSUE_CSHARP_HANDLER_NOT_FOUND, "Inventoried C# handlers must have exactly one executable declaration.", handler=name, declaration_count=declared_handlers.count(name)))
    for name in sorted(set(declared_handlers) - set(handlers_by_name)):
        if not _approved(approvals, kind="handler", handler=name):
            issues.append(_issue(ISSUE_CSHARP_HANDLER_INVENTED, "Executable event-like handlers absent from inventory require explicit approval.", handler=name, source_discovered=True))

    inventory_pairs: Dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for index, item in enumerate(subscriptions):
        pair = (str(item.get("owner") or item.get("source_owner") or "").lower(), _event_name(item), _handler_name(item))
        if index not in duplicate_subscription_indexes:
            inventory_pairs[pair] = item
        approved = _approved(
            approvals,
            kind="subscription",
            handler=pair[2],
            event=pair[1],
            owner=pair[0],
        )
        if _subscription_id(item) not in mapped_subscriptions and not approved:
            issues.append(_issue(ISSUE_CSHARP_SUBSCRIPTION_INVENTED, "Unmapped C# subscriptions require explicit approval evidence.", subscription_id=_subscription_id(item), subscription_index=index))
        occurrence_count = actual_subscriptions.count(pair)
        if occurrence_count != 1:
            issues.append(_issue(ISSUE_CSHARP_SUBSCRIPTION_NOT_FOUND, "Inventoried subscriptions must occur exactly once in executable source.", subscription_id=_subscription_id(item), owner=pair[0], event=pair[1], handler=pair[2], occurrence_count=occurrence_count))
    for owner, event, handler in sorted(set(actual_subscriptions) - set(inventory_pairs)):
        if not _approved(approvals, kind="subscription", handler=handler, event=event, owner=owner):
            issues.append(_issue(ISSUE_CSHARP_SUBSCRIPTION_INVENTED, "Executable subscriptions absent from inventory require explicit approval.", owner=owner, event=event, handler=handler, source_discovered=True))


def _mask_csharp_comments_and_strings(source: str) -> str:
    return _mask_language(source, sql=False, mask_strings=True)


def _mask_csharp_comments(source: str) -> str:
    return _mask_language(source, sql=False, mask_strings=False)


def _mask_sql_comments_and_strings(source: str) -> str:
    return _mask_language(source, sql=True, mask_strings=True)


def _mask_sql_comments(source: str) -> str:
    return _mask_language(source, sql=True, mask_strings=False)


def _mask_language(source: str, *, sql: bool, mask_strings: bool) -> str:
    text = str(source or "")
    output = list(text)
    index = 0
    state = "code"
    quote = ""
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "-" and nxt == "-" and sql:
                output[index] = output[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if char == "/" and nxt == "/" and not sql:
                output[index] = output[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if char == "/" and nxt == "*":
                output[index] = output[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if (sql and char == "'") or (not sql and char in {'"', "'"}):
                quote = char
                if mask_strings:
                    output[index] = " "
                index += 1
                state = "string"
                continue
            index += 1
            continue
        if state == "line_comment":
            if char in "\r\n":
                state = "code"
            else:
                output[index] = " "
            index += 1
            continue
        if state == "block_comment":
            if char == "*" and nxt == "/":
                output[index] = output[index + 1] = " "
                index += 2
                state = "code"
            else:
                if char not in "\r\n":
                    output[index] = " "
                index += 1
            continue
        if mask_strings and char not in "\r\n":
            output[index] = " "
        if sql and char == quote and nxt == quote:
            if mask_strings:
                output[index + 1] = " "
            index += 2
            continue
        if not sql and char == "\\":
            if index + 1 < len(text) and mask_strings:
                output[index + 1] = " "
            index += 2
            continue
        if char == quote:
            state = "code"
        index += 1
    return "".join(output)


def _find_event_handler_declarations(source: str) -> list[str]:
    pattern = re.compile(
        rf"\b(?:private|protected|internal|public)\s+(?:async\s+)?(?:void|Task)\s+(?P<name>{_IDENTIFIER})\s*\(\s*[^,()]+\s+{_IDENTIFIER}\s*,\s*(?:[A-Za-z_][A-Za-z0-9_.<>]*EventArgs|EventArgs)\s+{_IDENTIFIER}\s*\)\s*{{",
        re.MULTILINE,
    )
    return [match.group("name") for match in pattern.finditer(source)]


def _find_csharp_subscriptions(source: str, owner: str) -> list[tuple[str, str, str]]:
    active = _mask_csharp_comments_and_strings(source)
    pattern = re.compile(
        rf"\.\s*(?P<event>{_IDENTIFIER})\s*\+=\s*(?:new\s+[A-Za-z_][A-Za-z0-9_.<>]*\s*\(\s*)?(?:this\s*\.\s*)?(?P<handler>{_IDENTIFIER})\s*\)?\s*;"
    )
    return [(owner, match.group("event"), match.group("handler")) for match in pattern.finditer(active)]


def _method_body(source: str, method_name: str) -> tuple[int, int] | None:
    active = _mask_csharp_comments_and_strings(source)
    match = re.search(rf"\b{re.escape(method_name)}\s*\([^;{{}}]*\)\s*{{", active)
    if not match:
        return None
    start = active.find("{", match.start())
    depth = 0
    for index in range(start, len(active)):
        if active[index] == "{":
            depth += 1
        elif active[index] == "}":
            depth -= 1
            if depth == 0:
                return start, index + 1
    return None


def _method_bodies(source: str, method_name: str) -> list[tuple[int, int]]:
    active = _mask_csharp_comments_and_strings(source)
    matches = re.finditer(
        rf"\b{re.escape(method_name)}\s*\([^;{{}}]*\)\s*{{", active
    )
    bodies: list[tuple[int, int]] = []
    for match in matches:
        start = active.find("{", match.start())
        depth = 0
        for index in range(start, len(active)):
            if active[index] == "{":
                depth += 1
            elif active[index] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append((start, index + 1))
                    break
    return bodies


def _line_number(source: str, offset: int) -> int:
    return source.count("\n", 0, max(0, offset)) + 1


def _validate_designer_legality(
    designer_source: str,
    csharp_source: str,
    issues: list[ContractIssue],
) -> Dict[str, Any]:
    designer_active = _mask_csharp_comments_and_strings(designer_source)
    body_span = _method_body(designer_source, "InitializeComponent")
    findings: list[Dict[str, Any]] = []
    lifecycle_findings: list[Dict[str, Any]] = []
    init_declarations = re.findall(
        rf"\b(?:private|protected|internal|public)\s+void\s+InitializeComponent\s*\([^;{{}}]*\)\s*{{",
        designer_active,
    )
    if len(init_declarations) != 1:
        lifecycle_findings.append(
            {"kind": "initialize_component_declaration_count", "count": len(init_declarations)}
        )
    if body_span is None:
        findings.append({"kind": "initialize_component_missing", "line": 0})
    else:
        start, end = body_span
        body = designer_active[start:end]
        illegal_patterns = (
            ("control_flow", re.compile(r"\b(?:if|for|foreach|while|switch|try)\s*\(")),
            ("local_component", re.compile(rf"\b(?:var|[A-Za-z_][A-Za-z0-9_.<>]*(?:Control|Column|Repository|Grid|Panel|Button|Edit))\s+{_IDENTIFIER}\s*=\s*new\b")),
            ("factory_assignment", re.compile(rf"\bthis\s*\.\s*{_IDENTIFIER}\s*=\s*(?!new\b)[^;=]*\b(?:Create|Build|Make)[A-Za-z0-9_]*\s*\(")),
            ("lambda", re.compile(r"=>")),
        )
        for kind, pattern in illegal_patterns:
            for match in pattern.finditer(body):
                findings.append({"kind": kind, "line": _line_number(designer_active, start + match.start())})
        serializer_ops = re.compile(
            rf"(?:\bthis\s*\.\s*{_IDENTIFIER}\s*=\s*new\b|\.(?:Controls|Columns|RepositoryItems|ViewCollection)\.(?:Add|AddRange)\s*\()"
        )
        for match in serializer_ops.finditer(designer_active):
            if not (start <= match.start() < end):
                findings.append({"kind": "serializer_operation_outside_initialize_component", "line": _line_number(designer_active, match.start())})
    for finding in findings:
        issues.append(_issue(ISSUE_DESIGNER_SERIALIZER_ILLEGAL, "Static Designer structure must remain serializer-legal inside InitializeComponent.", **finding))

    active = _mask_csharp_comments_and_strings(csharp_source)
    class_names = re.findall(rf"\bclass\s+(?P<name>{_IDENTIFIER})", active)
    constructor_calls = 0
    for class_name in class_names:
        constructor_pattern = re.compile(
            rf"\b(?:public|protected|internal|private)?\s*{re.escape(class_name)}\s*\([^;{{}}]*\)\s*{{"
        )
        for match in constructor_pattern.finditer(active):
            start = active.find("{", match.start())
            depth = 0
            for index in range(start, len(active)):
                if active[index] == "{":
                    depth += 1
                elif active[index] == "}":
                    depth -= 1
                    if depth == 0:
                        constructor_calls += len(
                            re.findall(r"\bInitializeComponent\s*\(\s*\)\s*;", active[start : index + 1])
                        )
                        break
    initialize_calls = len(re.findall(r"\bInitializeComponent\s*\(\s*\)\s*;", active))
    if initialize_calls != 1 or constructor_calls != 1:
        lifecycle_findings.append(
            {
                "kind": "constructor_initialize_component_call_count",
                "total_calls": initialize_calls,
                "constructor_calls": constructor_calls,
            }
        )

    dispose_bodies = _method_bodies(designer_source, "Dispose")
    dispose_declared = bool(
        re.search(r"\bDispose\s*\(\s*bool\s+disposing\s*\)", designer_active)
    )
    if not dispose_declared or len(dispose_bodies) != 1:
        lifecycle_findings.append(
            {
                "kind": "designer_dispose_declaration_count",
                "declared": dispose_declared,
                "count": len(dispose_bodies),
            }
        )
    elif not re.search(r"\bbase\s*\.\s*Dispose\s*\(\s*disposing\s*\)\s*;", designer_active[dispose_bodies[0][0] : dispose_bodies[0][1]]):
        lifecycle_findings.append({"kind": "designer_base_dispose_missing"})
    if re.search(r"\bcomponents\b", designer_active):
        if not dispose_bodies or not re.search(
            r"\bcomponents\s*\.\s*Dispose\s*\(\s*\)\s*;",
            designer_active[dispose_bodies[0][0] : dispose_bodies[0][1]] if dispose_bodies else "",
        ):
            issues.append(
                _issue(
                    ISSUE_DESIGNER_DISPOSAL_INVALID,
                    "Designer-owned components must be disposed in Dispose(bool disposing).",
                    kind="components_dispose_missing",
                )
            )
    for finding in lifecycle_findings:
        issues.append(
            _issue(
                ISSUE_DESIGNER_LIFECYCLE_INVALID,
                "Designer InitializeComponent and Dispose lifecycle must remain explicit and complete.",
                **finding,
            )
        )

    code_findings: list[Dict[str, Any]] = []
    static_patterns = (
        ("static_collection", re.compile(r"\.(?:Controls|Columns|RepositoryItems|ViewCollection)\.(?:Add|AddRange)\s*\(")),
        ("static_property", re.compile(rf"\bthis\s*\.\s*{_IDENTIFIER}\s*\.\s*(?:Name|Location|Size|Margin|Padding|Dock|Anchor|TabIndex|BindingField|FieldName|ColumnEdit|MainView)\s*=")),
        ("static_construction", re.compile(rf"\bthis\s*\.\s*{_IDENTIFIER}\s*=\s*new\s+[A-Za-z_][A-Za-z0-9_.<>]*(?:Control|Column|Repository|Grid|Panel|Button|Edit)\b")),
        ("runtime_factory_layout", re.compile(rf"\bthis\s*\.\s*{_IDENTIFIER}\s*=\s*[^;=]*\b(?:Create|Build|Make)[A-Za-z0-9_]*(?:Control|Column|Repository|Layout|Grid)\s*\(")),
        ("static_ui_field", re.compile(rf"\b(?:private|protected|internal|public)\s+(?:System\.Windows\.Forms\.)?(?:[A-Za-z_][A-Za-z0-9_.]*(?:Control|Column|Repository|Grid|Panel|Button|Edit))\s+{_IDENTIFIER}\s*(?:=|;)")),
        ("dispose_override", re.compile(r"\bDispose\s*\(\s*bool\s+disposing\s*\)")),
    )
    for kind, pattern in static_patterns:
        for match in pattern.finditer(active):
            code_findings.append({"kind": kind, "line": _line_number(active, match.start())})
    for finding in code_findings:
        issues.append(_issue(ISSUE_STATIC_UI_IN_CODE_BEHIND, "Static controls, columns, repositories, and layout belong in Designer source.", **finding))
    return {
        "serializer_findings": findings,
        "code_behind_static_findings": code_findings,
    }


def _rule_binding(rule: Mapping[str, Any], role: str) -> ArtifactBinding | None:
    artifacts = rule.get("artifacts")
    if isinstance(artifacts, Mapping) and isinstance(artifacts.get(role), (Mapping, ArtifactBinding)):
        return ArtifactBinding.from_value(artifacts[role])
    prefix = "save_sp" if role == "save_sp" else "csharp"
    if rule.get(prefix + "_path") or rule.get(prefix + "_sha256"):
        return ArtifactBinding(
            path=str(rule.get(prefix + "_path") or ""),
            sha256=str(rule.get(prefix + "_sha256") or ""),
        )
    return None


def _language_signatures(rule: Mapping[str, Any], role: str) -> Dict[str, str]:
    value = rule.get(role)
    if isinstance(value, Mapping):
        return {kind: str(value.get(kind) or "") for kind in ("predicate", "message", "guard")}
    return {kind: str(rule.get(kind) or "") for kind in ("predicate", "message", "guard")}


def _canonical_tokens(source: str, *, sql: bool) -> Tuple[str, ...]:
    active = _mask_sql_comments_and_strings(source) if sql else _mask_csharp_comments_and_strings(source)
    return tuple(token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|==|!=|<=|>=|&&|\|\||[(){}<>!=.+*/%-]", active))


def _contains_tokens(source: str, fragment: str, *, sql: bool) -> bool:
    haystack = _canonical_tokens(source, sql=sql)
    needle = _canonical_tokens(fragment, sql=sql)
    if not needle:
        return False
    width = len(needle)
    return any(haystack[index : index + width] == needle for index in range(len(haystack) - width + 1))


def _decode_csharp_string(token: str) -> str:
    raw = token
    if raw.startswith('@"'):
        return raw[2:-1].replace('""', '"')
    body = raw[1:-1]
    try:
        return bytes(body, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return body


def _executable_csharp_messages(source: str) -> set[str]:
    text = _mask_csharp_comments(source)
    pattern = re.compile(r'@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"')
    values: set[str] = set()
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 240) : match.start()]
        boundary = max(prefix.rfind(";"), prefix.rfind("{"), prefix.rfind("}"))
        context = prefix[boundary + 1 :]
        if re.search(r"\bthrow\b", context) or context.count("(") > context.count(")"):
            values.add(_decode_csharp_string(match.group(0)))
    return values


def _executable_sql_messages(source: str) -> set[str]:
    text = _mask_sql_comments(source)
    pattern = re.compile(r"N?'((?:''|[^'])*)'", re.IGNORECASE)
    values: set[str] = set()
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 240) : match.start()]
        if re.search(r"\bRAISERROR\s*\([^)]*$", prefix, re.IGNORECASE) or re.search(r"\bTHROW\s+\d+\s*,\s*$", prefix, re.IGNORECASE):
            values.add(match.group(1).replace("''", "'"))
    return values


def _signature_present(source: str, fragment: str, *, role: str, kind: str) -> bool:
    if not fragment:
        return False
    if kind == "message":
        values = _executable_sql_messages(source) if role == OWNER_SAVE_SP else _executable_csharp_messages(source)
        return fragment in values
    return _contains_tokens(source, fragment, sql=role == OWNER_SAVE_SP)


def _validate_ownership(
    ledger: Sequence[Mapping[str, Any]],
    *,
    bindings: Mapping[str, ArtifactBinding],
    csharp_source: str,
    save_sp_source: str,
    issues: list[ContractIssue],
) -> list[Dict[str, Any]]:
    findings: list[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_rule in enumerate(ledger):
        rule = dict(raw_rule)
        rule_id = str(rule.get("rule_id") or "").strip()
        owner = str(rule.get("owner") or "").strip().lower()
        if not rule_id or rule_id in seen_ids or owner not in _OWNERS:
            issues.append(_issue(ISSUE_OWNERSHIP_RULE_INVALID, "Ownership rules require a unique rule_id and owner csharp/save_sp.", rule_id=rule_id, rule_index=index, owner=owner))
            continue
        seen_ids.add(rule_id)
        binding_valid = True
        for role in (OWNER_CSHARP, OWNER_SAVE_SP):
            binding = _rule_binding(rule, role)
            if binding is None or not _binding_equal(binding, bindings[role]):
                binding_valid = False
                issues.append(_issue(ISSUE_ARTIFACT_BINDING_MISMATCH, "Ownership ledger rules must bind both exact candidate artifacts.", rule_id=rule_id, artifact_role=role))
        signatures = {
            OWNER_CSHARP: _language_signatures(rule, OWNER_CSHARP),
            OWNER_SAVE_SP: _language_signatures(rule, OWNER_SAVE_SP),
        }
        if not any(signatures[owner].values()):
            issues.append(_issue(ISSUE_OWNERSHIP_RULE_INVALID, "The owning language requires at least one predicate, message, or guard signature.", rule_id=rule_id, owner=owner))
            continue
        owner_source = save_sp_source if owner == OWNER_SAVE_SP else csharp_source
        other = OWNER_CSHARP if owner == OWNER_SAVE_SP else OWNER_SAVE_SP
        other_source = csharp_source if other == OWNER_CSHARP else save_sp_source
        result = {"rule_id": rule_id, "owner": owner, "binding_valid": binding_valid, "checks": []}
        for kind in ("predicate", "message", "guard"):
            owner_fragment = signatures[owner][kind]
            other_fragment = signatures[other][kind]
            owner_present = True if not owner_fragment else _signature_present(owner_source, owner_fragment, role=owner, kind=kind)
            other_present = False if not other_fragment else _signature_present(other_source, other_fragment, role=other, kind=kind)
            result["checks"].append({"kind": kind, "owner_present": owner_present, "non_owner_present": other_present})
            if owner_fragment and not owner_present:
                issues.append(_issue(ISSUE_OWNED_RULE_MISSING, "The declared owner must retain its executable validation/error signature.", rule_id=rule_id, owner=owner, signature_kind=kind))
            if other_present:
                code = ISSUE_SAVE_SP_RULE_DUPLICATED_IN_CSHARP if owner == OWNER_SAVE_SP else ISSUE_CSHARP_RULE_MOVED_TO_SAVE_SP
                message = (
                    "C# may invoke or forward SAVE results but cannot duplicate SAVE-SP-owned validation/errors."
                    if owner == OWNER_SAVE_SP
                    else "C#-owned validation cannot be silently moved to the SAVE procedure."
                )
                issues.append(_issue(code, message, rule_id=rule_id, owner=owner, signature_kind=kind))
        findings.append(result)
    return findings


__all__ = [
    "ArtifactBinding",
    "ContractIssue",
    "EventSaveContractResult",
    "validate_pb_event_save_contract",
    "verify_pb_event_save_contract",
    "sha256_text",
    "approval_scope_sha256",
]
