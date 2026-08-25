"""Claim-gated, execution-correlated PB/C# performance equivalence contract."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from src.contracts import HarnessResult


CONTRACT_ID = "pb-performance-equivalence-contract"
SCHEMA_VERSION = 1
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024
SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-fA-F]{64}$")
CLAIM_RE = re.compile(r"\b(?:performance|tuning|equivalence|faster|speed|runtime|logical\s+reads|execution\s+plan)\b", re.I)

ISSUE_CLAIM_RECEIPT_MISSING = "pb_performance_execution_receipts_missing"
ISSUE_RECEIPT_INVALID = "pb_performance_execution_receipt_invalid"
ISSUE_RECEIPT_DUPLICATE = "pb_performance_execution_receipt_duplicate"
ISSUE_RECEIPT_CALL_DUPLICATE = "pb_performance_execution_call_duplicate"
ISSUE_SQL_HASH_INVALID = "pb_performance_sql_hash_invalid"
ISSUE_SQL_HASH_MISMATCH = "pb_performance_sql_hash_mismatch"
ISSUE_SQL_ARTIFACT_INVALID = "pb_performance_sql_artifact_invalid"
ISSUE_CONTEXT_MISMATCH = "pb_performance_context_mismatch"
ISSUE_RESULT_SCHEMA_MISMATCH = "pb_performance_result_schema_mismatch"
ISSUE_RESULT_ROW_MISMATCH = "pb_performance_result_row_mismatch"
ISSUE_RESULT_VALUE_MISMATCH = "pb_performance_result_value_mismatch"
ISSUE_PLAN_HASH_INVALID = "pb_performance_plan_hash_invalid"
ISSUE_LOGICAL_READS_INVALID = "pb_performance_logical_reads_invalid"
ISSUE_RUNTIME_SAMPLES_INVALID = "pb_performance_runtime_samples_invalid"
ISSUE_EXECUTION_FAILED = "pb_performance_execution_failed"
ISSUE_PROVENANCE_UNTRUSTED = "pb_performance_provenance_untrusted"


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _norm_sha(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw.startswith("sha256:") else ("sha256:" + raw if raw else "")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "severity": "error", "message": message, **details}


def _result(success: bool, issues: list[dict[str, Any]], *, status: str, **metadata: Any) -> HarnessResult:
    payload = {
        "contract_id": CONTRACT_ID,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "issues": list(issues),
        **metadata,
    }
    payload["receipt_sha256"] = _sha(_canonical(payload).encode("utf-8"))
    return HarnessResult(
        success=success,
        stdout=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        stderr="" if success else "PB performance/equivalence contract validation failed.",
        exit_code=0 if success else 1,
        metadata=payload,
    )


def _read_bounded(path_value: Any) -> tuple[Path, bytes, str]:
    path = Path(str(path_value or ""))
    if not path.is_absolute():
        raise ValueError("artifact path must be absolute")
    resolved = path.resolve(strict=True)
    before = resolved.stat()
    if not resolved.is_file() or before.st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact is not a bounded regular file")
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    with resolved.open("rb") as stream:
        while True:
            chunk = stream.read(READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ARTIFACT_BYTES:
                raise ValueError("artifact exceeds bounded read limit")
            digest.update(chunk)
            chunks.append(chunk)
    after = resolved.stat()
    if total != before.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("artifact changed during bounded read")
    return resolved, b"".join(chunks), "sha256:" + digest.hexdigest()


def _claim_requested(claim: Any, explicit: Any, aliases: Mapping[str, Any]) -> bool:
    if explicit is False:
        return False
    if explicit is True:
        return True
    if isinstance(claim, Mapping) and "claimed" in claim:
        return claim.get("claimed") is True
    if isinstance(claim, bool):
        return claim
    if isinstance(claim, str):
        return CLAIM_RE.search(claim) is not None
    for key in ("performance_claim", "equivalence_claim", "request", "operation", "task"):
        value = aliases.get(key)
        if isinstance(value, str) and CLAIM_RE.search(value):
            return True
    return False


def _field(receipt: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in receipt:
            return receipt[name]
    return None


def _validate_digest(value: Any, code: str, label: str, issues: list[dict[str, Any]], *, receipt: int) -> str:
    raw = str(value or "")
    if not SHA256_RE.fullmatch(raw):
        issues.append(_issue(code, f"Receipt {receipt} requires a complete SHA-256 for {label}.", receipt=receipt, field=label))
        return ""
    return _norm_sha(raw)


def _validate_sql_artifact(receipt: Mapping[str, Any], index: int, declared: str, issues: list[dict[str, Any]]) -> None:
    path_value = _field(receipt, "sql_artifact_path", "sql_path")
    if not path_value:
        issues.append(_issue(ISSUE_SQL_ARTIFACT_INVALID, "Each execution receipt must bind SQL to a readable artifact path.", receipt=index))
        return
    try:
        _, _, actual = _read_bounded(path_value)
    except (OSError, ValueError) as exc:
        issues.append(_issue(ISSUE_SQL_ARTIFACT_INVALID, "SQL artifact is unreadable or outside the bounded limit.", receipt=index, error=str(exc)))
        return
    if actual != declared:
        issues.append(_issue(ISSUE_SQL_HASH_MISMATCH, "Receipt SQL hash does not match the SQL artifact bytes.", receipt=index, expected=declared, actual=actual))


def _validate_receipt(receipt: Mapping[str, Any], index: int, issues: list[dict[str, Any]]) -> dict[str, Any]:
    normalized: dict[str, Any] = {"index": index}
    receipt_id = str(receipt.get("receipt_id") or "").strip()
    call_id = str(receipt.get("call_id") or "").strip()
    side = str(_field(receipt, "side", "phase", "variant") or "").strip().lower()
    tool_name = str(receipt.get("tool_name") or receipt.get("tool") or "").strip()
    if not receipt_id or not call_id or not tool_name or side not in {"before", "after"}:
        issues.append(_issue(ISSUE_RECEIPT_INVALID, "Receipt requires unique receipt_id/call_id, tool_name, and before/after side.", receipt=index))
    observed_at = str(receipt.get("observed_at") or "")
    try:
        parsed_time = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if parsed_time.tzinfo is None:
            raise ValueError("timezone required")
    except ValueError:
        issues.append(_issue(ISSUE_RECEIPT_INVALID, "Receipt observed_at must be timezone-aware ISO-8601.", receipt=index))
    exit_code = receipt.get("exit_code")
    errors = _field(receipt, "errors", "error")
    if type(exit_code) is not int or exit_code != 0 or errors not in (None, "", [], {}):
        issues.append(_issue(ISSUE_EXECUTION_FAILED, "Every before/after execution must have exit_code=0 and no errors.", receipt=index))
    if receipt.get("success") is False or receipt.get("verified") is True and not receipt.get("call_id"):
        issues.append(_issue(ISSUE_PROVENANCE_UNTRUSTED, "Caller status fields cannot replace execution correlation.", receipt=index))
    sql_hash = _validate_digest(_field(receipt, "sql_sha256", "sql_hash"), ISSUE_SQL_HASH_INVALID, "sql_sha256", issues, receipt=index)
    _validate_sql_artifact(receipt, index, sql_hash, issues)
    plan_hash = _validate_digest(_field(receipt, "execution_plan_sha256", "plan_sha256", "execution_plan_hash"), ISSUE_PLAN_HASH_INVALID, "execution_plan_sha256", issues, receipt=index)
    db = _field(receipt, "database", "db", "database_name")
    environment = _field(receipt, "environment", "env")
    parameters = _field(receipt, "parameters", "parameter_set", "parameters_hash")
    if db in (None, "") or environment in (None, "") or parameters in (None, ""):
        issues.append(_issue(ISSUE_RECEIPT_INVALID, "Receipt requires database, environment, and parameters.", receipt=index))
    result = receipt.get("result") if isinstance(receipt.get("result"), Mapping) else receipt
    schema_hash = _validate_digest(_field(result, "schema_sha256", "result_schema_sha256", "result_schema_hash"), ISSUE_RECEIPT_INVALID, "result_schema_sha256", issues, receipt=index)
    value_hash = _validate_digest(_field(result, "value_sha256", "values_sha256", "result_value_sha256", "result_value_hash"), ISSUE_RECEIPT_INVALID, "result_value_sha256", issues, receipt=index)
    row_count = _field(result, "row_count", "result_row_count")
    if type(row_count) is not int or row_count < 0:
        issues.append(_issue(ISSUE_RECEIPT_INVALID, "Receipt requires a non-negative integer result row_count.", receipt=index))
    logical_reads = _field(receipt, "logical_reads", "logical_read_count")
    if type(logical_reads) is not int or logical_reads < 0:
        issues.append(_issue(ISSUE_LOGICAL_READS_INVALID, "Receipt requires non-negative integer logical_reads.", receipt=index))
    samples = _field(receipt, "runtime_samples_ms", "runtime_samples", "runtime_ms")
    if isinstance(samples, (int, float)) and not isinstance(samples, bool):
        samples = [samples]
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)) or not samples or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) < 0 for v in samples):
        issues.append(_issue(ISSUE_RUNTIME_SAMPLES_INVALID, "Receipt requires finite non-negative runtime samples.", receipt=index))
    normalized.update({"receipt_id": receipt_id, "call_id": call_id, "side": side, "tool_name": tool_name, "sql_sha256": sql_hash, "plan_sha256": plan_hash, "database": _canonical(db), "environment": _canonical(environment), "parameters": _canonical(parameters), "schema_sha256": schema_hash, "value_sha256": value_hash, "row_count": row_count, "logical_reads": logical_reads, "runtime_samples": list(samples) if isinstance(samples, Sequence) and not isinstance(samples, (str, bytes)) else samples})
    return normalized


def validate_pb_performance_equivalence_contract(
    claim: Any = None,
    execution_receipts: Sequence[Mapping[str, Any]] | None = None,
    *,
    performance_claimed: bool | None = None,
    tool_receipts: Sequence[Mapping[str, Any]] | None = None,
    **aliases: Any,
) -> HarnessResult:
    """Require measured before/after evidence only for explicit performance claims."""
    requested = _claim_requested(claim, performance_claimed, aliases)
    if not requested:
        return _result(True, [], status="not_requested", claim_requested=False, verification_scope="claim_gated")
    receipts = execution_receipts if execution_receipts is not None else tool_receipts
    if not isinstance(receipts, Sequence) or isinstance(receipts, (str, bytes)) or not receipts:
        return _result(False, [_issue(ISSUE_CLAIM_RECEIPT_MISSING, "A performance/equivalence claim requires separate execution-correlated tool receipts.")], status="blocked", claim_requested=True, verification_scope="execution_correlated_performance")
    issues: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    receipt_ids: set[str] = set()
    call_ids: set[str] = set()
    for index, raw in enumerate(receipts):
        if not isinstance(raw, Mapping):
            issues.append(_issue(ISSUE_RECEIPT_INVALID, "Execution receipts must be mappings supplied separately from caller claim JSON.", receipt=index))
            continue
        current = _validate_receipt(raw, index, issues)
        normalized.append(current)
        if current["receipt_id"] in receipt_ids:
            issues.append(_issue(ISSUE_RECEIPT_DUPLICATE, "Execution receipt IDs must be unique.", receipt_id=current["receipt_id"]))
        receipt_ids.add(current["receipt_id"])
        if current["call_id"] in call_ids:
            issues.append(_issue(ISSUE_RECEIPT_CALL_DUPLICATE, "Execution call IDs must be unique.", call_id=current["call_id"]))
        call_ids.add(current["call_id"])
    by_side = {item.get("side"): item for item in normalized if item.get("side") in {"before", "after"}}
    if set(by_side) != {"before", "after"} or len([item for item in normalized if item.get("side") == "before"]) != 1 or len([item for item in normalized if item.get("side") == "after"]) != 1:
        issues.append(_issue(ISSUE_RECEIPT_INVALID, "Exactly one valid before and one valid after receipt are required."))
    if "before" in by_side and "after" in by_side:
        before, after = by_side["before"], by_side["after"]
        for field, code, label in (("database", ISSUE_CONTEXT_MISMATCH, "database"), ("environment", ISSUE_CONTEXT_MISMATCH, "environment"), ("parameters", ISSUE_CONTEXT_MISMATCH, "parameters")):
            if before.get(field) != after.get(field):
                issues.append(_issue(code, f"Before and after {label} context differs.", field=label))
        if before.get("schema_sha256") != after.get("schema_sha256"):
            issues.append(_issue(ISSUE_RESULT_SCHEMA_MISMATCH, "Before and after result schemas differ."))
        if before.get("row_count") != after.get("row_count"):
            issues.append(_issue(ISSUE_RESULT_ROW_MISMATCH, "Before and after result row counts differ."))
        if before.get("value_sha256") != after.get("value_sha256"):
            issues.append(_issue(ISSUE_RESULT_VALUE_MISMATCH, "Before and after result values differ."))
    issues.sort(key=lambda item: (str(item.get("code")), _canonical(item)))
    return _result(not issues, issues, status="passed" if not issues else "blocked", claim_requested=True, verification_scope="execution_correlated_performance", receipt_ids=sorted(receipt_ids), measurements=normalized)


def verify_pb_performance_equivalence_contract(**kwargs: Any) -> HarnessResult:
    return validate_pb_performance_equivalence_contract(**kwargs)


__all__ = ["validate_pb_performance_equivalence_contract", "verify_pb_performance_equivalence_contract", "MAX_ARTIFACT_BYTES"]
