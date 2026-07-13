import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from src.contracts import GoalState


EVIDENCE_TYPES = {"command", "test", "artifact", "review", "tool_receipt"}
OBSERVATION_VALUES = {"asserted", "observed"}
SUCCESS_STATUSES = {"passed", "success", "approved", "complete", "active"}
FAILURE_STATUSES = {"failed", "error", "blocked"}
PENDING_STATUSES = {"pending", "unknown"}
EVIDENCE_STATUSES = SUCCESS_STATUSES | FAILURE_STATUSES | PENDING_STATUSES
STRICT_EVIDENCE_POLICY = "typed_observed_v1"
SCOPE_FIELDS = (
    "project_id",
    "thread_id",
    "task_id",
    "goal_id",
    "lineage_id",
    "objective_hash",
)
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
PRODUCER_BOUNDARY = "in_process_runtime_claim_v1"
LOCAL_RUNTIME_BOUNDARY = "durable_local_runtime_integrity_v1"


_DEFAULT_EVIDENCE_ALIAS_GROUPS = [
    ["design_doc", "design doc", "design document"],
    ["target_files", "target files", "target file list"],
    ["workflow dispatch completed", "workflow completed", "dispatch completed"],
    ["unit tests passed", "tests passed", "python tests passed", "unittest passed", "pytest passed"],
    ["python unittest passed", "unit tests passed", "tests passed", "unittest passed"],
    ["python compile passed", "compile passed", "python syntax passed"],
    ["browser qa passed", "qa passed", "browser check passed", "browser qa completed"],
]


class RuntimeProducerBoundary:
    """Tracks local runtime claims without presenting them as external proof."""

    def __init__(self, producer_name: str, state_dir: str | Path | None = None):
        name = str(producer_name or "").strip()
        if not name:
            raise ValueError("producer_name is required")
        self.producer_name = name
        self._state_dir = Path(state_dir).resolve() if state_dir is not None else None
        self._secret = b""
        if self._state_dir is None:
            self.boundary_id = f"boundary-{uuid.uuid4().hex}"
        else:
            self._state_dir.mkdir(parents=True, exist_ok=True)
            producer_id = hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]
            self.boundary_id = f"local-{producer_id}"
            self._secret_path = self._state_dir / f"{producer_id}.key"
            self._consumed_path = self._state_dir / f"{producer_id}.consumed.json"
            self._lock_path = self._state_dir / f"{producer_id}.lock"
            self._secret = _load_or_create_secret(self._secret_path)
        self._claims: Dict[str, str] = {}
        self._consumed: set[str] = set()
        self._lock = threading.Lock()

    def issue_claim(
        self,
        payload: Mapping[str, Any],
        *,
        claim_kind: str,
        claim_id_field: str,
        claim_id_prefix: str,
    ) -> Dict[str, Any]:
        issued = deepcopy(dict(payload))
        boundary_kind = LOCAL_RUNTIME_BOUNDARY if self._state_dir is not None else PRODUCER_BOUNDARY
        issued["producer_boundary"] = {
            "kind": boundary_kind,
            "boundary_id": self.boundary_id,
            "producer_name": self.producer_name,
            "claim_kind": str(claim_kind),
        }
        issued["authority"] = (
            "local_runtime_integrity" if self._state_dir is not None else "same_process_runtime_claim"
        )
        issued["external_authenticity"] = "unverified"
        issued[claim_id_field] = f"{claim_id_prefix}-{uuid.uuid4().hex}"
        claim = self._claim_digest(issued)
        issued["producer_claim"] = claim
        with self._lock:
            if self._state_dir is None:
                self._claims[str(issued[claim_id_field])] = claim
        return issued

    def validate_claim(
        self,
        payload: Mapping[str, Any],
        *,
        claim_kind: str,
        claim_id_field: str,
        consume: bool = False,
    ) -> List[str]:
        boundary = payload.get("producer_boundary", {})
        if not isinstance(boundary, Mapping):
            return ["runtime_producer_revalidation_required"]
        expected_kind = LOCAL_RUNTIME_BOUNDARY if self._state_dir is not None else PRODUCER_BOUNDARY
        if (
            str(boundary.get("kind") or "") != expected_kind
            or str(boundary.get("boundary_id") or "") != self.boundary_id
            or str(boundary.get("producer_name") or "") != self.producer_name
            or str(boundary.get("claim_kind") or "") != str(claim_kind)
        ):
            return ["runtime_producer_boundary_mismatch"]

        claim_id = str(payload.get(claim_id_field) or "")
        supplied = str(payload.get("producer_claim") or "")
        if not claim_id or not supplied:
            return ["runtime_producer_revalidation_required"]
        expected = self._claim_digest(payload)
        if self._state_dir is not None:
            if not hmac.compare_digest(supplied, expected):
                return ["runtime_producer_claim_mismatch"]
            return self._validate_durable_consumption(claim_id, consume=consume)
        with self._lock:
            issued = self._claims.get(claim_id)
            consumed = claim_id in self._consumed
            valid = bool(issued) and supplied == expected and supplied == issued
            if valid and consume and not consumed:
                self._consumed.add(claim_id)
        if not valid:
            return ["runtime_producer_claim_mismatch"]
        if consumed:
            return ["replayed_receipt"]
        return []

    @property
    def validation_scope(self) -> str:
        if self._state_dir is not None:
            return "durable_local_runtime_integrity_and_structure_correlation"
        return "same_process_runtime_claim_and_structure_correlation"

    def _claim_digest(self, payload: Mapping[str, Any]) -> str:
        claim_payload = json.dumps(
            _producer_claim_payload(payload),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        if self._state_dir is None:
            return "sha256:" + hashlib.sha256(claim_payload).hexdigest()
        return "hmac-sha256:" + hmac.new(self._secret, claim_payload, hashlib.sha256).hexdigest()

    def _validate_durable_consumption(self, claim_id: str, *, consume: bool) -> List[str]:
        with _exclusive_file_lock(self._lock_path):
            consumed = _read_consumed_claims(self._consumed_path)
            if claim_id in consumed:
                return ["replayed_receipt"]
            if consume:
                consumed.add(claim_id)
                _atomic_write_json(self._consumed_path, sorted(consumed))
        return []


def sha256_text(value: Any) -> str:
    return "sha256:" + hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def normalize_evidence_key(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


def build_evidence_envelope(
    *,
    evidence_type: str,
    evidence_key: str,
    observation: str,
    producer: str,
    scope: Mapping[str, Any],
    observed_at: str,
    status: str,
    locator: str = "",
    command: str = "",
    command_id: str = "",
    result_id: str = "",
    result_status: str = "",
    tool_name: str = "",
    tool_call_id: str = "",
    exit_code: int | None = None,
    output_hash: str = "",
    content_hash: str = "",
    blocker: Mapping[str, Any] | None = None,
    detail: str = "",
) -> Dict[str, Any]:
    envelope: Dict[str, Any] = {
        "schema_version": 1,
        "evidence_type": str(evidence_type or "").strip().lower(),
        "evidence_key": normalize_evidence_key(evidence_key),
        "observation": str(observation or "").strip().lower(),
        "producer": str(producer or "").strip(),
        "scope": {field: str(scope.get(field, "")) for field in SCOPE_FIELDS},
        "observed_at": str(observed_at or "").strip(),
        "status": str(status or "").strip().lower(),
    }
    optional = {
        "locator": locator,
        "command": command,
        "command_id": command_id,
        "result_id": result_id,
        "result_status": result_status,
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "output_hash": output_hash,
        "content_hash": content_hash,
        "detail": detail,
    }
    for key, value in optional.items():
        if str(value or "").strip():
            envelope[key] = str(value).strip()
    if exit_code is not None:
        envelope["exit_code"] = int(exit_code)
    if blocker:
        envelope["blocker"] = dict(blocker)
    return envelope


def capture_evidence_envelope(
    *,
    evidence_type: str,
    evidence_key: str,
    producer: str,
    scope: Mapping[str, Any],
    status: str,
    captured_output: Any,
    observed_at: str = "",
    locator: str = "",
    command: str = "",
    command_id: str = "",
    result_id: str = "",
    result_status: str = "",
    tool_name: str = "",
    tool_call_id: str = "",
    exit_code: int | None = None,
    blocker: Mapping[str, Any] | None = None,
    detail: str = "",
    supersedes: str = "",
    producer_boundary: RuntimeProducerBoundary | None = None,
) -> Dict[str, Any]:
    """Capture evidence; without an explicit boundary it remains a caller claim."""
    normalized_type = str(evidence_type or "").strip().lower()
    output_hash = sha256_value(captured_output)
    envelope = build_evidence_envelope(
        evidence_type=normalized_type,
        evidence_key=evidence_key,
        observation="observed" if producer_boundary is not None else "asserted",
        producer=producer,
        scope=scope,
        observed_at=observed_at or datetime.now(timezone.utc).isoformat(),
        status=status,
        locator=locator,
        command=command,
        command_id=command_id,
        result_id=result_id,
        result_status=result_status,
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        exit_code=exit_code,
        output_hash=output_hash if normalized_type != "artifact" else "",
        content_hash=output_hash if normalized_type == "artifact" else "",
        blocker=blocker,
        detail=detail,
    )
    if supersedes:
        envelope["supersedes"] = str(supersedes)
    if producer_boundary is None:
        envelope["authority"] = "claimed_unverified"
        envelope["external_authenticity"] = "unverified"
        return envelope
    return producer_boundary.issue_claim(
        envelope,
        claim_kind="evidence",
        claim_id_field="receipt_id",
        claim_id_prefix="evidence",
    )


def validate_evidence_envelope(
    envelope: Mapping[str, Any] | Any,
    *,
    expected_scope: Mapping[str, Any] | None = None,
    producer_boundary: RuntimeProducerBoundary | None = None,
) -> Dict[str, Any]:
    errors: List[str] = []
    if not isinstance(envelope, Mapping):
        return {"valid": False, "errors": ["untyped_evidence"], "evidence_key": ""}

    evidence_type = str(envelope.get("evidence_type") or "").strip().lower()
    evidence_key = normalize_evidence_key(envelope.get("evidence_key"))
    observation = str(envelope.get("observation") or "").strip().lower()
    status = str(envelope.get("status") or "").strip().lower()

    if evidence_type not in EVIDENCE_TYPES:
        errors.append("invalid_evidence_type" if evidence_type else "missing_evidence_type")
    if not evidence_key:
        errors.append("missing_evidence_key")
    if observation not in OBSERVATION_VALUES:
        errors.append("invalid_observation" if observation else "missing_observation")
    elif observation != "observed":
        errors.append("asserted_evidence")
    if not str(envelope.get("producer") or "").strip():
        errors.append("missing_producer")
    if observation == "observed":
        if producer_boundary is None:
            errors.append("runtime_producer_revalidation_required")
        else:
            errors.extend(
                producer_boundary.validate_claim(
                    envelope,
                    claim_kind="evidence",
                    claim_id_field="receipt_id",
                )
            )
    if status not in EVIDENCE_STATUSES:
        errors.append("invalid_status" if status else "missing_status")

    scope = envelope.get("scope")
    if not isinstance(scope, Mapping):
        errors.append("missing_scope")
        scope = {}
    else:
        for field in SCOPE_FIELDS:
            if field not in scope:
                errors.append(f"missing_scope_{field}")
    if expected_scope is not None and isinstance(scope, Mapping):
        if any(str(scope.get(field, "")) != str(expected_scope.get(field, "")) for field in SCOPE_FIELDS):
            errors.append("scope_mismatch")

    observed_at = str(envelope.get("observed_at") or "").strip()
    if not observed_at:
        errors.append("missing_observed_at")
    elif not _valid_timestamp(observed_at):
        errors.append("invalid_observed_at")

    if evidence_type in {"command", "test"}:
        _require_text(envelope, "command", errors)
        _require_text(envelope, "command_id", errors)
        if "exit_code" not in envelope or isinstance(envelope.get("exit_code"), bool):
            errors.append("missing_exit_code")
        elif not isinstance(envelope.get("exit_code"), int):
            errors.append("invalid_exit_code")
        _require_hash(envelope, "output_hash", errors)
        exit_code = envelope.get("exit_code")
        if isinstance(exit_code, int):
            if status in SUCCESS_STATUSES and exit_code != 0:
                errors.append("success_exit_code_mismatch")
            if status in FAILURE_STATUSES and exit_code == 0:
                errors.append("failure_exit_code_mismatch")
    elif evidence_type == "artifact":
        _require_text(envelope, "locator", errors)
        _require_hash(envelope, "content_hash", errors)
    elif evidence_type == "review":
        _require_text(envelope, "locator", errors)
        _require_text(envelope, "result_id", errors)
        _require_hash(envelope, "output_hash", errors)
    elif evidence_type == "tool_receipt":
        _require_text(envelope, "tool_name", errors)
        _require_text(envelope, "tool_call_id", errors)
        _require_text(envelope, "result_id", errors)
        _require_text(envelope, "result_status", errors)
        _require_hash(envelope, "output_hash", errors)

    return {
        "valid": not errors,
        "errors": _dedupe_text(errors),
        "evidence_key": evidence_key,
        "observation": observation,
        "status": status,
        "validation_scope": (
            producer_boundary.validation_scope
            if producer_boundary is not None
            else "unverified_caller_claim_and_structure_correlation"
        ),
        "external_authenticity": "unverified",
    }


def collect_workflow_goal_evidence(
    design_doc: str,
    file_list: Iterable[str],
    workflow_completed: bool,
) -> List[str]:
    # Legacy workflow adapters still emit evidence keys. GoalRuntime opts into the
    # strict envelope policy and never treats these strings as observed evidence.
    evidence: List[str] = []
    if design_doc and design_doc.strip():
        evidence.append("design_doc")
    if list(file_list):
        evidence.append("target_files")
    if workflow_completed:
        evidence.append("workflow dispatch completed")
    return evidence


def evaluate_goal_evidence(
    goal_data: Dict[str, Any],
    workflow_evidence: Iterable[Any],
    workflow_success: bool,
    producer_boundary: RuntimeProducerBoundary | None = None,
) -> Dict[str, Any]:
    if not goal_data:
        return {}
    metadata = dict(goal_data.get("metadata", {}))
    if metadata.get("evidence_policy") == STRICT_EVIDENCE_POLICY:
        return _evaluate_strict_goal_evidence(
            goal_data,
            workflow_evidence,
            workflow_success,
            producer_boundary=producer_boundary,
        )
    return _evaluate_legacy_goal_evidence(goal_data, workflow_evidence, workflow_success)


def _evaluate_strict_goal_evidence(
    goal_data: Dict[str, Any],
    workflow_evidence: Iterable[Any],
    workflow_success: bool,
    *,
    producer_boundary: RuntimeProducerBoundary | None,
) -> Dict[str, Any]:
    goal = GoalState.from_dict(goal_data)
    metadata = dict(goal.metadata)
    expected_scope = metadata.get("scope", {})
    envelopes: List[Any] = list(metadata.get("evidence_envelopes", []) or [])
    envelopes.extend(list(workflow_evidence or []))

    observed: List[str] = []
    asserted: List[str] = []
    failed: List[str] = []
    pending: List[str] = []
    invalid_reasons: List[str] = []
    fail_closed_reasons: List[str] = []
    validations: List[Dict[str, Any]] = []
    latest: Dict[str, tuple[Dict[str, Any], Mapping[str, Any], datetime, int]] = {}
    seen_receipts: set[str] = set()
    for index, item in enumerate(envelopes):
        if not isinstance(item, Mapping):
            key = normalize_evidence_key(item)
            if key:
                _append_unique(asserted, key)
            _append_unique(invalid_reasons, "untyped_evidence")
            continue
        checked = validate_evidence_envelope(
            item,
            expected_scope=expected_scope,
            producer_boundary=producer_boundary,
        )
        validations.append(checked)
        key = checked.get("evidence_key", "")
        if checked.get("observation") == "asserted" and key:
            _append_unique(asserted, key)
        for error in checked.get("errors", []):
            _append_unique(invalid_reasons, error)
            if checked.get("observation") == "observed":
                _append_unique(fail_closed_reasons, error)
        if not checked.get("valid"):
            continue
        receipt_id = str(item.get("receipt_id") or "")
        if receipt_id in seen_receipts:
            _append_unique(invalid_reasons, "replayed_evidence_receipt")
            _append_unique(fail_closed_reasons, "replayed_evidence_receipt")
            continue
        seen_receipts.add(receipt_id)
        observed_at = _parsed_timestamp(str(item.get("observed_at") or ""))
        current = latest.get(key)
        if current and (observed_at, index) <= (current[2], current[3]):
            continue
        if (
            current
            and checked.get("status") in SUCCESS_STATUSES
            and current[0].get("status") in FAILURE_STATUSES | PENDING_STATUSES
            and str(item.get("supersedes") or "") != str(current[1].get("receipt_id") or "")
        ):
            _append_unique(invalid_reasons, "missing_validated_supersession")
            _append_unique(fail_closed_reasons, "missing_validated_supersession")
            continue
        latest[key] = (checked, item, observed_at, index)

    for key, (checked, _item, _observed_at, _index) in latest.items():
        status = checked.get("status")
        if status in SUCCESS_STATUSES:
            _append_unique(observed, key)
        elif status in FAILURE_STATUSES:
            _append_unique(failed, key)
        else:
            _append_unique(pending, key)

    required = _normalized_list(goal.evidence_required)
    alias_map = _evidence_alias_map(metadata)
    evidence_set = set(observed)
    recorded_set = set(latest)
    missing: List[str] = []
    alias_matches: Dict[str, str] = {}
    for item in required:
        matching_key = _matching_evidence_key(item, recorded_set, alias_map)
        if not matching_key:
            missing.append(item)
        elif matching_key != item:
            alias_matches[item] = matching_key

    criteria = _normalized_list(goal.success_criteria)
    criterion_map = _normalized_criterion_map(metadata.get("criterion_evidence_map", {}))
    unmapped = [criterion for criterion in criteria if not criterion_map.get(criterion)]
    criterion_missing: Dict[str, List[str]] = {}
    for criterion, mapped_keys in criterion_map.items():
        if criterion not in criteria:
            continue
        missing_for_criterion = [
            key for key in mapped_keys if not _matching_evidence_key(key, recorded_set, alias_map)
        ]
        if missing_for_criterion:
            criterion_missing[criterion] = missing_for_criterion

    missing_goal_requirements: List[str] = []
    if metadata.get("goal_required") and not criteria:
        missing_goal_requirements.append("success_criteria")
    if metadata.get("goal_required") and not required:
        missing_goal_requirements.append("evidence_required")
    scope_complete = isinstance(expected_scope, Mapping) and all(
        field in expected_scope for field in SCOPE_FIELDS
    ) and all(
        str(expected_scope.get(field) or "")
        for field in ("project_id", "goal_id", "lineage_id", "objective_hash")
    )
    if metadata.get("goal_required") and not scope_complete:
        missing_goal_requirements.append("scope")

    metadata.update(
        {
            "evidence_policy": STRICT_EVIDENCE_POLICY,
            "missing_evidence": missing,
            "missing_goal_requirements": missing_goal_requirements,
            "evidence_alias_matches": alias_matches,
            "failed_evidence": failed,
            "pending_evidence": pending,
            "observed_evidence": observed,
            "passed_evidence": observed,
            "asserted_evidence": asserted,
            "invalid_evidence_reasons": invalid_reasons,
            "evidence_validations": validations,
            "evidence_envelopes": envelopes,
            "unmapped_success_criteria": unmapped,
            "criterion_missing_evidence": criterion_missing,
            "workflow_failure_asserted": not bool(workflow_success),
            "external_truth_boundary": (
                "Runtime validation proves receipt structure and scope correlation only; "
                "it does not independently prove the external event."
            ),
        }
    )
    metadata["fail_closed_evidence_reasons"] = fail_closed_reasons
    complete = bool(workflow_success) and not any(
        [
            missing,
            missing_goal_requirements,
            unmapped,
            criterion_missing,
            failed,
            pending,
            fail_closed_reasons,
        ]
    )
    return GoalState(
        objective=goal.objective,
        status="complete" if complete else "active",
        success_criteria=list(goal.success_criteria),
        evidence_required=required,
        evidence=observed,
        progress_notes=list(goal.progress_notes),
        blocked_reason="",
        metadata=metadata,
    ).to_dict()


def _evaluate_legacy_goal_evidence(
    goal_data: Dict[str, Any],
    workflow_evidence: Iterable[Any],
    workflow_success: bool,
) -> Dict[str, Any]:
    goal = GoalState.from_dict(goal_data)
    metadata = dict(goal.metadata)
    evidence_record_statuses = _evidence_record_statuses(goal_data, metadata)
    evidence: List[str] = []
    for item in goal.evidence:
        _append_passed_legacy_evidence(evidence, item, evidence_record_statuses)
    for item in workflow_evidence:
        _record_legacy_evidence_status(evidence_record_statuses, item)
        _append_passed_legacy_evidence(evidence, item, {})

    required = _normalized_list(goal.evidence_required)
    evidence_set = set(evidence)
    recorded_set = evidence_set | set(evidence_record_statuses)
    alias_map = _evidence_alias_map(metadata)
    missing: List[str] = []
    alias_matches: Dict[str, str] = {}
    for item in required:
        matching_key = _matching_evidence_key(item, recorded_set, alias_map)
        if not matching_key:
            missing.append(item)
        elif matching_key != item:
            alias_matches[item] = matching_key

    missing_goal_requirements: List[str] = []
    if metadata.get("goal_required") and not any(str(item).strip() for item in goal.success_criteria):
        missing_goal_requirements.append("success_criteria")
    if metadata.get("goal_required") and not required:
        missing_goal_requirements.append("evidence_required")

    failed = sorted(key for key, status in evidence_record_statuses.items() if status == "failed")
    pending = sorted(key for key, status in evidence_record_statuses.items() if status == "pending")
    metadata.update(
        {
            "evidence_policy": "legacy_string_compatibility",
            "legacy_evidence_compatibility": True,
            "missing_evidence": missing,
            "missing_goal_requirements": missing_goal_requirements,
            "evidence_alias_matches": alias_matches,
            "failed_evidence": failed,
            "pending_evidence": pending,
            "passed_evidence": list(evidence),
        }
    )

    status = "complete"
    blocked_reason = ""
    if not workflow_success:
        status = "blocked"
        blocked_reason = "workflow dispatch failed"
    elif missing_goal_requirements:
        status = "blocked"
        blocked_reason = "missing goal completion requirements: " + ", ".join(missing_goal_requirements)
    elif failed:
        status = "blocked"
        blocked_reason = f"required evidence failed: {', '.join(failed)}"
    elif pending:
        status = "blocked"
        blocked_reason = f"required evidence pending: {', '.join(pending)}"
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


def _append_alias_group(alias_map: Dict[str, List[str]], values: Iterable[Any]) -> None:
    group: List[str] = []
    for value in values:
        _append_unique(group, value)
    for key in group:
        alias_map.setdefault(key, [])
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
    for candidate in alias_map.get(required, [required]):
        if candidate in evidence_set:
            return candidate
    return ""


def _evidence_record_statuses(goal_data: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, str]:
    records = goal_data.get("evidence_records", metadata.get("evidence_records", []))
    statuses: Dict[str, str] = {}
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, Mapping):
                continue
            key = normalize_evidence_key(
                record.get("key") or record.get("evidence_key") or record.get("evidence")
            )
            status = normalize_evidence_key(record.get("status"))
            if key and status in {"passed", "failed", "pending"}:
                statuses[key] = status
    for key in metadata.get("failed_evidence", []) or []:
        normalized = normalize_evidence_key(key)
        if normalized:
            statuses[normalized] = "failed"
    for key in metadata.get("pending_evidence", []) or []:
        normalized = normalize_evidence_key(key)
        if normalized and statuses.get(normalized) != "failed":
            statuses[normalized] = "pending"
    return statuses


def _append_passed_legacy_evidence(
    evidence: List[str],
    item: Any,
    recorded_statuses: Dict[str, str],
) -> None:
    if isinstance(item, Mapping):
        key = normalize_evidence_key(
            item.get("key") or item.get("evidence_key") or item.get("evidence")
        )
        status = normalize_evidence_key(item.get("status") or "passed")
        if status == "passed":
            _append_unique(evidence, key)
        return
    key = normalize_evidence_key(item)
    if recorded_statuses.get(key, "passed") == "passed":
        _append_unique(evidence, key)


def _record_legacy_evidence_status(statuses: Dict[str, str], item: Any) -> None:
    if not isinstance(item, Mapping):
        return
    key = normalize_evidence_key(
        item.get("key") or item.get("evidence_key") or item.get("evidence")
    )
    status = normalize_evidence_key(item.get("status"))
    if not key:
        return
    if status in SUCCESS_STATUSES:
        statuses[key] = "passed"
    elif status in FAILURE_STATUSES:
        statuses[key] = "failed"
    elif status in PENDING_STATUSES:
        statuses[key] = "pending"


def _normalized_list(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        _append_unique(result, value)
    return result


def _normalized_criterion_map(value: Any) -> Dict[str, List[str]]:
    if not isinstance(value, Mapping):
        return {}
    result: Dict[str, List[str]] = {}
    for criterion, evidence_keys in value.items():
        normalized_criterion = normalize_evidence_key(criterion)
        if not normalized_criterion:
            continue
        if isinstance(evidence_keys, str):
            evidence_keys = [evidence_keys]
        result[normalized_criterion] = _normalized_list(evidence_keys or [])
    return result


def _append_unique(items: List[str], value: Any) -> None:
    normalized = normalize_evidence_key(value)
    if normalized and normalized not in items:
        items.append(normalized)


def _dedupe_text(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _require_text(envelope: Mapping[str, Any], field: str, errors: List[str]) -> None:
    if not str(envelope.get(field) or "").strip():
        errors.append(f"missing_{field}")


def _require_hash(envelope: Mapping[str, Any], field: str, errors: List[str]) -> None:
    value = str(envelope.get(field) or "").strip().lower()
    if not value:
        errors.append(f"missing_{field}")
    elif not HASH_PATTERN.fullmatch(value):
        errors.append(f"invalid_{field}")


def _valid_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _parsed_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def sha256_value(value: Any) -> str:
    if isinstance(value, bytes):
        payload = value
    elif isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _producer_claim_payload(value: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if key != "producer_claim"
    }


def _load_or_create_secret(path: Path) -> bytes:
    try:
        secret = path.read_bytes()
        if len(secret) < 32:
            raise ValueError("local runtime integrity key is invalid")
        return secret
    except FileNotFoundError:
        secret = secrets.token_bytes(32)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            secret = path.read_bytes()
            if len(secret) < 32:
                raise ValueError("local runtime integrity key is invalid")
            return secret
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(secret)
            handle.flush()
            os.fsync(handle.fileno())
        return secret


def _read_consumed_claims(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("local runtime receipt consumption state is malformed") from exc
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("local runtime receipt consumption state is invalid")
    return set(value)


def _atomic_write_json(path: Path, value: Any) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _exclusive_file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


__all__ = [
    "EVIDENCE_TYPES",
    "RuntimeProducerBoundary",
    "STRICT_EVIDENCE_POLICY",
    "build_evidence_envelope",
    "capture_evidence_envelope",
    "collect_workflow_goal_evidence",
    "evaluate_goal_evidence",
    "normalize_evidence_key",
    "sha256_text",
    "sha256_value",
    "validate_evidence_envelope",
]
