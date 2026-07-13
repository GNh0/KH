import argparse
import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from src.orchestration.goal_evidence import (
    RuntimeProducerBoundary,
    STRICT_EVIDENCE_POLICY,
    build_evidence_envelope,
    evaluate_goal_evidence,
    normalize_evidence_key,
    sha256_text,
    sha256_value,
    validate_evidence_envelope,
)
from src.orchestration.goal_ledger import GoalLedger


GOAL_BACKENDS = {"kh_ledger", "host_goal", "hybrid", "unavailable"}
TERMINAL_GOAL_STATUSES = {"complete", "blocked", "archived"}
_NO_GOAL_REASONS = {
    "localized_patch_continuation",
    "readonly_source_audit_request",
    "readonly_source_condition_question",
}
def resolve_goal_backend(context: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Choose a Goal channel without treating authorization as execution evidence."""
    context = dict(context or {})
    preference = str(
        context.get("goal_backend_preference") or context.get("goal_backend") or ""
    ).strip().lower()
    kh_available = _as_bool(context.get("kh_ledger_available"), default=True)
    host_available = _as_bool(context.get("host_goal_available"), default=False)
    intent = context.get("request_intent", {})
    structured_authorization = (
        intent.get("execution_authorization") if isinstance(intent, Mapping) else None
    )
    host_authorized = (
        structured_authorization is True
        or _as_bool(context.get("host_goal_authorized"), default=False)
        or _as_bool(context.get("user_authorized_host_goal"), default=False)
    )

    backend = "unavailable"
    reason = "no authorized Goal channel is available"
    if preference == "hybrid" and kh_available and host_available and host_authorized:
        backend = "hybrid"
        reason = "hybrid policy selected; each channel still requires its own receipt"
    elif preference == "host_goal" and host_available and host_authorized:
        backend = "host_goal"
        reason = "host Goal channel selected; authorization does not prove execution"
    elif kh_available:
        backend = "kh_ledger"
        reason = "automatic KH judgment selected the internal GoalLedger"
    elif host_available and host_authorized:
        backend = "host_goal"
        reason = "KH GoalLedger unavailable; authorized host channel selected pending receipt"

    return {
        "goal_backend": backend,
        "recommended_backend": backend,
        "kh_ledger_available": kh_available,
        "host_goal_available": host_available,
        "host_goal_authorized": host_authorized,
        "reason": reason,
    }


def build_goal_activation(
    classification: Mapping[str, Any],
    project: str,
    context: Mapping[str, Any] | None = None,
    *,
    objective: str = "",
) -> Dict[str, Any]:
    context = dict(context or {})
    reasons = {str(item) for item in classification.get("reasons", []) or []}
    complexity = str(classification.get("complexity") or "")
    required = complexity in {"heavy", "high_risk"} or "persistent_completion_request" in reasons
    if complexity == "light" or reasons & _NO_GOAL_REASONS:
        required = False

    goal_spec = _goal_spec(context, objective)
    policy = resolve_goal_backend(context)
    backend = policy["goal_backend"]
    thread_id = str(context.get("thread_id") or context.get("chat_id") or "")
    task_id = str(context.get("task_id") or "")

    kh_validation = validate_goal_runtime_receipt(
        context.get("goal_runtime_receipt"),
        project=project,
        thread_id=thread_id,
        task_id=task_id,
        objective=goal_spec["objective"],
        consume=required and backend in {"kh_ledger", "hybrid"},
        producer_boundary=context.get("goal_runtime_producer_boundary"),
    )
    host_validation = validate_host_goal_receipt(
        context.get("host_goal_receipt"),
        thread_id=thread_id,
        task_id=task_id,
        objective=goal_spec["objective"],
        consume=required and backend in {"host_goal", "hybrid"},
    )
    channels = {
        "routing": {
            "status": "required" if required else "not_required",
            "required": required,
        },
        "kh_goal_ledger": {
            "status": (
                "executed"
                if kh_validation["valid"]
                else "pending"
                if backend in {"kh_ledger", "hybrid"} and required
                else "not_executed"
            ),
            "validation": kh_validation,
        },
        "host_goal": {
            "status": (
                "executed"
                if host_validation["valid"]
                else "pending"
                if backend in {"host_goal", "hybrid"} and required
                else "not_executed"
            ),
            "validation": host_validation,
            "authorized": policy["host_goal_authorized"],
        },
    }

    execution_evidence: List[str] = []
    if kh_validation["valid"]:
        execution_evidence.append("goal_runtime_receipt")
    if host_validation["valid"]:
        execution_evidence.append("host_goal_receipt")
    backend_executed = (
        backend == "kh_ledger"
        and kh_validation["valid"]
        or backend == "host_goal"
        and host_validation["valid"]
        or backend == "hybrid"
        and kh_validation["valid"]
        and host_validation["valid"]
    )

    if not required:
        status = "not_required"
        next_action = "continue_without_goal_activation"
    elif backend == "unavailable":
        status = "unavailable"
        next_action = "configure_kh_goal_ledger_or_authorized_host_goal"
    elif backend_executed:
        status = "executed"
        next_action = "continue_with_validated_goal_runtime_receipt"
    elif backend == "host_goal":
        status = "pending"
        next_action = "invoke_host_create_goal_and_attach_correlated_host_goal_receipt"
    else:
        status = "pending"
        next_action = (
            "python -m src.orchestration.goal_runtime start using goal_activation.goal_spec"
        )

    return {
        "required": required,
        "status": status,
        "goal_backend": backend,
        "recommended_backend": policy["recommended_backend"],
        "next_action": next_action,
        "execution_evidence": execution_evidence,
        "host_goal_authorized": policy["host_goal_authorized"],
        "backend_reason": policy["reason"],
        "goal_spec": goal_spec,
        "channels": channels,
        "runtime_receipts": {
            "kh_goal_ledger": (
                dict(context.get("goal_runtime_receipt"))
                if kh_validation["valid"]
                else {}
            ),
            "host_goal": (
                dict(context.get("host_goal_receipt"))
                if host_validation["valid"]
                else {}
            ),
        },
        "receipt_validation_scope": "durable_local_runtime_integrity_and_state_correlation",
        "external_authenticity": "unverified",
    }


def validate_goal_runtime_receipt(
    receipt: Any,
    *,
    project: str,
    thread_id: str = "",
    task_id: str = "",
    objective: str = "",
    consume: bool = False,
    producer_boundary: RuntimeProducerBoundary | None = None,
) -> Dict[str, Any]:
    errors: List[str] = []
    if not isinstance(receipt, Mapping):
        return _receipt_validation(
            False,
            ["missing_goal_runtime_receipt"],
            validation_scope="durable_local_runtime_integrity_and_state_correlation",
        )
    expected_ledger = GoalLedger(project, thread_id=thread_id)
    boundary = producer_boundary or RuntimeProducerBoundary(
        "kh_goal_ledger_runtime",
        state_dir=expected_ledger.state_dir / "integrity",
    )
    if receipt.get("receipt_type") != "kh_goal_ledger":
        errors.append("invalid_receipt_type")
    operation = str(receipt.get("operation") or "")
    if operation not in {"start", "status", "add-evidence", "capture-evidence", "update", "evaluate", "close"}:
        errors.append("invalid_operation")
    if not str(receipt.get("result_id") or "").strip():
        errors.append("missing_result_id")
    if str(receipt.get("status") or "") not in {"active", "complete", "blocked"}:
        errors.append("invalid_result_status")
    if not _valid_timestamp(str(receipt.get("observed_at") or "")):
        errors.append("invalid_timestamp")
    expected_project_id = _project_id(project)
    expected_objective_hash = sha256_text(objective) if objective else ""
    state_path_value = str(receipt.get("state_path") or "").strip()
    if not state_path_value:
        errors.append("missing_state_path")
        return _receipt_validation(
            False,
            errors,
            validation_scope="durable_local_runtime_integrity_and_state_correlation",
        )
    state_path = Path(state_path_value)
    if not state_path.exists():
        errors.append("state_path_missing")
        return _receipt_validation(
            False,
            errors,
            validation_scope="durable_local_runtime_integrity_and_state_correlation",
        )
    try:
        resolved_path = state_path.resolve(strict=True)
        expected_state_dir = expected_ledger.state_dir.resolve()
        if not _is_within(resolved_path, expected_state_dir) or resolved_path != expected_ledger.current_goal_path.resolve():
            errors.append("state_path_outside_runtime_scope")
    except OSError:
        errors.append("state_path_unresolvable")
        return _receipt_validation(
            False,
            errors,
            validation_scope="durable_local_runtime_integrity_and_state_correlation",
        )

    raw = state_path.read_bytes()
    actual_content_hash = _sha256_bytes(raw)
    if str(receipt.get("content_hash") or "") != actual_content_hash:
        errors.append("content_hash_mismatch")
    try:
        state = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append("state_parse_failed")
        return _receipt_validation(
            False,
            errors,
            validation_scope="durable_local_runtime_integrity_and_state_correlation",
        )
    if not isinstance(state, dict) or not isinstance(state.get("goal"), dict):
        errors.append("state_schema_invalid")
        return _receipt_validation(
            False,
            errors,
            validation_scope="durable_local_runtime_integrity_and_state_correlation",
        )

    goal = state["goal"]
    metadata = goal.get("metadata", {}) if isinstance(goal.get("metadata"), dict) else {}
    scope = metadata.get("scope", {}) if isinstance(metadata.get("scope"), dict) else {}
    if str(receipt.get("project_id") or "") != expected_project_id or str(scope.get("project_id") or "") != expected_project_id:
        errors.append("project_scope_mismatch")
    if str(receipt.get("thread_id") or "") != str(thread_id) or str(scope.get("thread_id") or "") != str(thread_id):
        errors.append("thread_scope_mismatch")
    if str(receipt.get("task_id") or "") != str(task_id) or str(scope.get("task_id") or "") != str(task_id):
        errors.append("task_scope_mismatch")
    if expected_objective_hash and (
        str(receipt.get("objective_hash") or "") != expected_objective_hash
        or str(scope.get("objective_hash") or "") != expected_objective_hash
    ):
        errors.append("objective_hash_mismatch")
    goal_objective = str(goal.get("objective") or "")
    goal_objective_hash = sha256_text(goal_objective)
    if not goal_objective:
        errors.append("missing_goal_objective")
    if str(scope.get("objective_hash") or "") != goal_objective_hash:
        errors.append("goal_objective_hash_mismatch")
    if str(receipt.get("objective_hash") or "") != goal_objective_hash:
        errors.append("receipt_objective_hash_mismatch")
    for field, error in [
        ("goal_id", "goal_id_mismatch"),
        ("lineage_id", "lineage_mismatch"),
    ]:
        if not str(receipt.get(field) or "") or str(receipt.get(field)) != str(scope.get(field) or ""):
            errors.append(error)
    if str(receipt.get("status") or "") != str(goal.get("status") or ""):
        errors.append("goal_status_mismatch")
    if state.get("schema_version") != 1:
        errors.append("state_schema_version_mismatch")
    state_mirrors = {
        "objective": goal.get("objective", ""),
        "status": goal.get("status", "active"),
        "success_criteria": list(goal.get("success_criteria", [])),
        "evidence_required": list(goal.get("evidence_required", [])),
        "evidence": list(goal.get("evidence", [])),
        "blocked_reason": goal.get("blocked_reason", ""),
    }
    for field, expected_value in state_mirrors.items():
        if state.get(field) != expected_value:
            errors.append(f"state_{field}_mismatch")
    if str(receipt.get("observed_at") or "") != str(state.get("updated_at") or ""):
        errors.append("state_timestamp_mismatch")
    expected_goal_hash = _goal_content_hash(goal)
    if str(metadata.get("content_hash") or "") != expected_goal_hash:
        errors.append("goal_content_hash_mismatch")
    if str(receipt.get("goal_content_hash") or "") != expected_goal_hash:
        errors.append("receipt_goal_content_hash_mismatch")
    expected_result_id = sha256_text(
        f"{operation}:{actual_content_hash}:{scope.get('goal_id', '')}:{goal.get('status', '')}"
    )
    if str(receipt.get("result_id") or "") != expected_result_id:
        errors.append("result_id_mismatch")

    errors.extend(
        boundary.validate_claim(
            receipt,
            claim_kind="kh_goal_ledger_runtime",
            claim_id_field="producer_receipt_id",
            consume=consume and not errors,
        )
    )
    return _receipt_validation(
        not errors,
        errors,
        state_path=str(resolved_path),
        validation_scope="durable_local_runtime_integrity_and_state_correlation",
    )


def validate_host_goal_receipt(
    receipt: Any,
    *,
    thread_id: str,
    task_id: str = "",
    objective: str,
    consume: bool = False,
) -> Dict[str, Any]:
    errors: List[str] = []
    if not isinstance(receipt, Mapping):
        return _receipt_validation(False, ["missing_host_goal_receipt"])
    required_text = [
        "host",
        "tool_name",
        "tool_call_id",
        "result_id",
        "result_status",
        "goal_id",
        "thread_id",
        "objective_hash",
        "observed_at",
        "output_hash",
    ]
    for field in required_text:
        if not str(receipt.get(field) or "").strip():
            errors.append(f"missing_{field}")
    if receipt.get("receipt_type") != "host_goal_tool":
        errors.append("invalid_receipt_type")
    if str(receipt.get("tool_name") or "") not in {"create_goal", "update_goal"}:
        errors.append("invalid_host_goal_tool")
    if str(receipt.get("result_status") or "") not in {"success", "active", "complete", "blocked"}:
        errors.append("invalid_result_status")
    if str(receipt.get("thread_id") or "") != str(thread_id) or not thread_id:
        errors.append("thread_scope_mismatch")
    if str(receipt.get("task_id") or "") != str(task_id):
        errors.append("task_scope_mismatch")
    if str(receipt.get("objective_hash") or "") != sha256_text(objective):
        errors.append("objective_hash_mismatch")
    if not _valid_timestamp(str(receipt.get("observed_at") or "")):
        errors.append("invalid_timestamp")
    if not _valid_hash(str(receipt.get("output_hash") or "")):
        errors.append("invalid_output_hash")
    errors.append("external_host_execution_unverified")
    return _receipt_validation(not errors, errors)


def capture_host_goal_receipt(
    *,
    host: str,
    tool_name: str,
    tool_call_id: str,
    result_id: str,
    result_status: str,
    goal_id: str,
    thread_id: str,
    task_id: str,
    objective: str,
    captured_output: Any,
    observed_at: str = "",
) -> Dict[str, Any]:
    receipt = {
        "schema_version": 1,
        "receipt_type": "host_goal_tool",
        "host": str(host),
        "tool_name": str(tool_name),
        "tool_call_id": str(tool_call_id),
        "result_id": str(result_id),
        "result_status": str(result_status),
        "goal_id": str(goal_id),
        "thread_id": str(thread_id),
        "task_id": str(task_id),
        "objective_hash": sha256_text(objective),
        "observed_at": observed_at or _utc_now(),
        "output_hash": sha256_text(
            json.dumps(captured_output, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)
        ),
    }
    receipt["authority"] = "claimed_unverified"
    receipt["external_authenticity"] = "unverified"
    return receipt


class GoalRuntime:
    def __init__(self, project_dir: str, thread_id: str = "", task_id: str = ""):
        self.project_dir = str(Path(project_dir).resolve())
        self.thread_id = str(thread_id or "")
        self.task_id = str(task_id or "")
        self.ledger = GoalLedger(self.project_dir, thread_id=self.thread_id)
        integrity_dir = self.ledger.state_dir / "integrity"
        self.evidence_producer = RuntimeProducerBoundary(
            "kh_goal_runtime_evidence", state_dir=integrity_dir
        )
        self.receipt_producer = RuntimeProducerBoundary(
            "kh_goal_ledger_runtime", state_dir=integrity_dir
        )

    def start(
        self,
        *,
        objective: str,
        success_criteria: Iterable[str],
        evidence_required: Iterable[str],
        criterion_evidence_map: Mapping[str, Iterable[str]] | None = None,
        goal_required: bool = True,
        goal_backend: str = "kh_ledger",
        host_goal_authorized: bool = False,
        host_goal_receipt: Mapping[str, Any] | None = None,
        host_goal_evidence: Any = None,
        replacement_policy: Mapping[str, Any] | None = None,
        lineage_id: str = "",
        active_task: str = "",
        next_action: str = "",
    ) -> Dict[str, Any]:
        objective = str(objective or "").strip()
        criteria = _dedupe(success_criteria)
        required = _dedupe(evidence_required)
        backend = str(goal_backend or "kh_ledger").strip().lower()
        if not objective:
            raise ValueError("objective is required")
        if goal_required and not criteria:
            raise ValueError("nonempty success criteria are required for goal-required work")
        if goal_required and not required:
            raise ValueError("nonempty evidence requirements are required for goal-required work")
        if backend not in GOAL_BACKENDS or backend == "unavailable":
            raise ValueError(f"unsupported or unavailable goal backend: {backend}")
        if backend == "host_goal":
            raise ValueError("GoalRuntime cannot execute a host-native Goal; use the host create_goal tool")
        if host_goal_evidence is not None and host_goal_evidence != "":
            raise ValueError("arbitrary host_goal_evidence is not accepted; provide a structured receipt")
        if backend == "hybrid":
            if not host_goal_authorized:
                raise ValueError("hybrid backend requires host Goal authorization")
            checked = validate_host_goal_receipt(
                host_goal_receipt,
                thread_id=self.thread_id,
                task_id=self.task_id,
                objective=objective,
            )
            if not checked["valid"]:
                raise ValueError("hybrid backend requires a valid correlated host Goal receipt")

        mapping = _criterion_map(criteria, required, criterion_evidence_map)
        existing = self.ledger.load_current_goal()

        goal_id = f"goal-{uuid.uuid4().hex}"
        lineage = str(lineage_id or goal_id)
        objective_hash = sha256_text(objective)
        scope = {
            "project_id": _project_id(self.project_dir),
            "thread_id": self.thread_id,
            "task_id": self.task_id,
            "goal_id": goal_id,
            "lineage_id": lineage,
            "objective_hash": objective_hash,
        }
        goal = {
            "objective": objective,
            "status": "active",
            "success_criteria": criteria,
            "evidence_required": required,
            "evidence": [],
            "progress_notes": [],
            "blocked_reason": "",
            "metadata": {
                "goal_required": bool(goal_required),
                "goal_backend": backend,
                "host_goal_authorized": bool(host_goal_authorized),
                "host_goal_receipt": dict(host_goal_receipt or {}),
                "evidence_policy": STRICT_EVIDENCE_POLICY,
                "criterion_evidence_map": mapping,
                "evidence_envelopes": [],
                "evidence_records": [],
                "blocker_policy": {
                    "policy": "repeated_observation_v1",
                    "minimum_observations": 2,
                },
                "scope": scope,
            },
        }
        if existing and existing.get("goal"):
            archived = self._archive_for_replacement(existing, replacement_policy, objective)
            archived_goal = dict(archived["goal"])
            archived_scope = archived_goal.get("metadata", {}).get("scope", {})
            archive_path = (
                self.ledger.state_dir
                / "archived_goals"
                / f"{archived_scope.get('goal_id') or 'goal'}.json"
            )
            normalized_goal = self._normalized_goal(goal)
            with _runtime_only_goal_storage():
                state = self.ledger.replace_current_goal(
                    normalized_goal,
                    archived_goal=archived_goal,
                    archive_path=archive_path,
                    active_task=active_task,
                    next_recommended_action=next_action,
                    expected_revision=str(existing.get("_ledger_revision", "")),
                )
            self.ledger.append_event(
                "goal_archived",
                {
                    "goal_id": str(archived_scope.get("goal_id") or "goal"),
                    "archive_path": str(archive_path),
                    "reason": str((replacement_policy or {}).get("reason") or ""),
                },
            )
        else:
            state = self._save(
                goal,
                active_task=active_task,
                next_action=next_action,
                expected_revision="" if existing else None,
            )
        self.ledger.append_event("goal_started", {"goal": state["goal"]})
        return self._result("start", state)

    def status(self) -> Dict[str, Any]:
        state = self.ledger.load_current_goal()
        if not state:
            return {
                "command": "status",
                "status": "not_started",
                "goal_backend": "unavailable",
                "goal": {},
                "goal_ledger": self.ledger.describe_paths(),
                "runtime_channels": _runtime_channels("unavailable", False),
            }
        return self._result("status", state)

    def add_evidence(
        self,
        evidence: Iterable[Any],
        *,
        evidence_status: str = "passed",
        detail: str = "",
    ) -> Dict[str, Any]:
        status = str(evidence_status or "").strip().lower()
        if status not in {"passed", "failed", "pending"}:
            raise ValueError("evidence_status must be passed, failed, or pending")
        items = list(evidence)
        if not items:
            raise ValueError("at least one evidence item is required")

        state, goal = self._current(mutable=True)
        metadata = dict(goal.get("metadata", {}))
        scope = metadata.get("scope", {})
        envelopes = list(metadata.get("evidence_envelopes", []) or [])
        records = list(metadata.get("evidence_records", []) or [])
        added_keys: List[str] = []
        for item in items:
            if isinstance(item, Mapping):
                envelope = deepcopy(dict(item))
            else:
                envelope = build_evidence_envelope(
                    evidence_type="artifact",
                    evidence_key=str(item),
                    observation="asserted",
                    producer="unverified_assertion",
                    scope=scope,
                    observed_at=_utc_now(),
                    status=status,
                    detail=detail,
                )
            checked = validate_evidence_envelope(
                envelope,
                expected_scope=scope,
                producer_boundary=self.evidence_producer,
            )
            key = normalize_evidence_key(envelope.get("evidence_key"))
            if key:
                added_keys.append(key)
            envelopes.append(envelope)
            records.append(
                {
                    "key": key,
                    "status": str(envelope.get("status") or status),
                    "observation": str(envelope.get("observation") or "asserted"),
                    "valid": bool(checked.get("valid")),
                    "detail": str(envelope.get("detail") or detail or ""),
                }
            )
        metadata["evidence_envelopes"] = envelopes
        metadata["evidence_records"] = records
        goal["metadata"] = metadata
        saved = self._save_from_state(goal, state)
        self.ledger.append_event(
            "goal_evidence_added",
            {"evidence": added_keys, "observation_count": len(items)},
        )
        return self._result("add-evidence", saved)

    def capture_evidence(
        self,
        *,
        evidence_type: str,
        evidence_key: str,
        artifact: str = "",
        command_result_file: str = "",
        producer: str = "kh_goal_runtime_capture",
        detail: str = "",
    ) -> Dict[str, Any]:
        state, goal = self._current(mutable=True)
        scope = goal.get("metadata", {}).get("scope", {})
        normalized_type = str(evidence_type or "").strip().lower()
        if normalized_type == "artifact":
            if not artifact or command_result_file:
                raise ValueError("artifact capture requires only --artifact")
            source_path = Path(artifact).resolve(strict=True)
            if not source_path.is_file():
                raise ValueError("artifact capture source must be a file")
            source_bytes = source_path.read_bytes()
            envelope = build_evidence_envelope(
                evidence_type="artifact",
                evidence_key=evidence_key,
                observation="observed",
                producer=producer,
                scope=scope,
                observed_at=_utc_now(),
                status="passed",
                locator=str(source_path),
                content_hash=_sha256_bytes(source_bytes),
                detail=detail,
            )
            envelope["capture_source"] = "artifact_file"
            envelope["source_content_hash"] = _sha256_bytes(source_bytes)
            captured = self.evidence_producer.issue_claim(
                envelope,
                claim_kind="evidence",
                claim_id_field="receipt_id",
                claim_id_prefix="evidence",
            )
        elif normalized_type in {"command", "test"}:
            if not command_result_file or artifact:
                raise ValueError("command/test capture requires only --command-result-file")
            source_path = Path(command_result_file).resolve(strict=True)
            if not source_path.is_file():
                raise ValueError("command result source must be a file")
            source_bytes = source_path.read_bytes()
            try:
                command_result = json.loads(source_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("command result source must contain valid UTF-8 JSON") from exc
            if not isinstance(command_result, Mapping):
                raise ValueError("command result source must contain a JSON object")
            command = str(command_result.get("command") or "").strip()
            command_id = str(command_result.get("command_id") or "").strip()
            exit_code = command_result.get("exit_code")
            if not command or not command_id:
                raise ValueError("command result requires command and command_id")
            if isinstance(exit_code, bool) or not isinstance(exit_code, int):
                raise ValueError("command result exit_code must be an integer")
            captured_output = {
                "stdout": command_result.get("stdout", ""),
                "stderr": command_result.get("stderr", ""),
            }
            envelope = build_evidence_envelope(
                evidence_type=normalized_type,
                evidence_key=evidence_key,
                observation="observed",
                producer=producer,
                scope=scope,
                observed_at=_utc_now(),
                status="passed" if exit_code == 0 else "failed",
                locator=str(source_path),
                command=command,
                command_id=command_id,
                exit_code=exit_code,
                output_hash=sha256_value(captured_output),
                detail=detail,
            )
            envelope["capture_source"] = "command_result_file"
            envelope["source_content_hash"] = _sha256_bytes(source_bytes)
            captured = self.evidence_producer.issue_claim(
                envelope,
                claim_kind="evidence",
                claim_id_field="receipt_id",
                claim_id_prefix="evidence",
            )
        else:
            raise ValueError("capture evidence type must be artifact, command, or test")

        result = self.add_evidence([captured])
        result["command"] = "capture-evidence"
        result["captured_evidence"] = captured
        return result

    def update(
        self,
        *,
        success_criteria: Iterable[str] = (),
        evidence_required: Iterable[str] = (),
        criterion_evidence_map: Mapping[str, Iterable[str]] | None = None,
        progress_notes: Iterable[str] = (),
        active_task: str | None = None,
        next_action: str | None = None,
    ) -> Dict[str, Any]:
        state, goal = self._current(mutable=True)
        previous_criteria = _dedupe(goal.get("success_criteria", []))
        previous_required = _dedupe(goal.get("evidence_required", []))
        new_criteria = _dedupe([*previous_criteria, *success_criteria])
        new_required = _dedupe([*previous_required, *evidence_required])
        metadata = dict(goal.get("metadata", {}))
        configured_map = dict(metadata.get("criterion_evidence_map", {}) or {})
        if criterion_evidence_map:
            configured_map.update(dict(criterion_evidence_map))
        added_criteria = [item for item in new_criteria if item not in previous_criteria]
        added_required = [item for item in new_required if item not in previous_required]
        if added_criteria and not criterion_evidence_map and len(added_criteria) == len(added_required):
            configured_map.update(
                {
                    criterion: [added_required[index]]
                    for index, criterion in enumerate(added_criteria)
                }
            )
        metadata["criterion_evidence_map"] = _criterion_map(
            new_criteria,
            new_required,
            configured_map,
        )
        goal["metadata"] = metadata
        goal["success_criteria"] = new_criteria
        goal["evidence_required"] = new_required
        goal["progress_notes"] = _dedupe([*goal.get("progress_notes", []), *progress_notes])
        saved = self._save_from_state(goal, state, active_task=active_task, next_action=next_action)
        self.ledger.append_event("goal_updated", {"goal": saved["goal"]})
        return self._result("update", saved)

    def evaluate(
        self,
        *,
        workflow_evidence: Iterable[Any] = (),
        workflow_success: bool = True,
    ) -> Dict[str, Any]:
        state, goal = self._current(mutable=True)
        items = list(workflow_evidence)
        if items:
            metadata = dict(goal.get("metadata", {}))
            scope = metadata.get("scope", {})
            envelopes = list(metadata.get("evidence_envelopes", []) or [])
            records = list(metadata.get("evidence_records", []) or [])
            added_keys: List[str] = []
            for item in items:
                if isinstance(item, Mapping):
                    envelope = deepcopy(dict(item))
                else:
                    envelope = build_evidence_envelope(
                        evidence_type="artifact",
                        evidence_key=str(item),
                        observation="asserted",
                        producer="unverified_workflow_assertion",
                        scope=scope,
                        observed_at=_utc_now(),
                        status="passed",
                    )
                checked = validate_evidence_envelope(
                    envelope,
                    expected_scope=scope,
                    producer_boundary=self.evidence_producer,
                )
                key = normalize_evidence_key(envelope.get("evidence_key"))
                if key:
                    added_keys.append(key)
                envelopes.append(envelope)
                records.append(
                    {
                        "key": key,
                        "status": str(envelope.get("status") or ""),
                        "observation": str(envelope.get("observation") or "asserted"),
                        "valid": bool(checked.get("valid")),
                    }
                )
            metadata["evidence_envelopes"] = envelopes
            metadata["evidence_records"] = records
            goal["metadata"] = metadata
            self.ledger.append_event(
                "goal_evidence_added",
                {"evidence": added_keys, "observation_count": len(items), "source": "evaluate"},
            )
        evaluation = evaluate_goal_evidence(
            goal,
            (),
            workflow_success,
            producer_boundary=self.evidence_producer,
        )
        self._record_evaluation(state, goal, evaluation, workflow_success=workflow_success)
        self.ledger.append_event("goal_evaluated", {"evaluation": evaluation})
        return {
            "command": "evaluate",
            "ready_to_close": evaluation.get("status") == "complete",
            "evaluation": evaluation,
            "goal_backend": str(goal.get("metadata", {}).get("goal_backend", "kh_ledger")),
            "goal_ledger": self.ledger.describe_paths(),
            "runtime_channels": _runtime_channels(
                str(goal.get("metadata", {}).get("goal_backend", "kh_ledger")), True
            ),
        }

    def close(
        self,
        *,
        status: str = "complete",
        blocked_reason: str = "",
        blocker_code: str = "",
    ) -> Dict[str, Any]:
        state, goal = self._current(mutable=True)
        requested_status = str(status or "complete").strip().lower()
        if requested_status not in {"complete", "blocked"}:
            raise ValueError("close status must be complete or blocked")

        if requested_status == "blocked":
            code = normalize_evidence_key(blocker_code or blocked_reason).replace(" ", "_")
            observations = self._qualified_blocker_observations(goal, code)
            minimum = int(
                goal.get("metadata", {})
                .get("blocker_policy", {})
                .get("minimum_observations", 2)
                or 2
            )
            if not code or len(observations) < minimum:
                raise ValueError("blocked close requires repeated blocker observations")
            goal["status"] = "blocked"
            goal["blocked_reason"] = code
            metadata = dict(goal.get("metadata", {}))
            metadata["blocker_observation_ids"] = observations
            goal["metadata"] = metadata
            saved = self._save_from_state(goal, state, next_action="")
            self.ledger.append_event("goal_closed", {"goal": saved["goal"]})
            return {**self._result("close", saved), "closed": True}

        workflow_success = bool(
            goal.get("metadata", {}).get("last_workflow_success", True)
        )
        evaluation = evaluate_goal_evidence(
            goal,
            (),
            workflow_success,
            producer_boundary=self.evidence_producer,
        )
        if evaluation.get("status") != "complete":
            self._record_evaluation(state, goal, evaluation)
            self.ledger.append_event("goal_close_rejected", {"evaluation": evaluation})
            return {
                "command": "close",
                "closed": False,
                "status": "rejected",
                "evaluation": evaluation,
                "goal_backend": str(goal.get("metadata", {}).get("goal_backend", "kh_ledger")),
                "goal_ledger": self.ledger.describe_paths(),
                "runtime_channels": _runtime_channels(
                    str(goal.get("metadata", {}).get("goal_backend", "kh_ledger")), True
                ),
            }
        evaluation["status"] = "complete"
        evaluation["blocked_reason"] = ""
        saved = self._save_from_state(evaluation, state, next_action="")
        self.ledger.append_event("goal_closed", {"goal": saved["goal"]})
        return {**self._result("close", saved), "closed": True}

    def _current(self, *, mutable: bool = False) -> tuple[Dict[str, Any], Dict[str, Any]]:
        state = self.ledger.load_current_goal()
        goal = dict(state.get("goal", {})) if state else {}
        if not goal:
            raise ValueError("no current goal; run start first")
        if mutable and str(goal.get("status") or "") in TERMINAL_GOAL_STATUSES:
            raise ValueError("terminal goal is immutable")
        return state, goal

    def _archive_for_replacement(
        self,
        state: Dict[str, Any],
        replacement_policy: Mapping[str, Any] | None,
        new_objective: str,
    ) -> Dict[str, Any]:
        goal = dict(state.get("goal", {}))
        policy = dict(replacement_policy or {})
        if policy.get("mode") != "archive_current" or not str(policy.get("reason") or "").strip():
            state_label = "active goal" if goal.get("status") == "active" else "current goal"
            raise ValueError(f"{state_label} exists; explicit archive_current replacement policy required")
        archived = deepcopy(state)
        archived_goal = dict(archived.get("goal", {}))
        archived_goal["status"] = "archived"
        archived_metadata = dict(archived_goal.get("metadata", {}))
        archived_metadata["archived_at"] = _utc_now()
        archived_metadata["archive_reason"] = str(policy["reason"]).strip()
        archived_metadata["replacement_objective_hash"] = sha256_text(new_objective)
        archived_metadata.pop("content_hash", None)
        archived_goal["metadata"] = archived_metadata
        archived_metadata["content_hash"] = _goal_content_hash(archived_goal)
        archived_goal["metadata"] = archived_metadata
        archived["goal"] = archived_goal
        archived["status"] = "archived"
        return archived

    def _qualified_blocker_observations(self, goal: Dict[str, Any], code: str) -> List[str]:
        if not code:
            return []
        metadata = goal.get("metadata", {})
        scope = metadata.get("scope", {})
        observation_ids: List[str] = []
        for envelope in metadata.get("evidence_envelopes", []) or []:
            if not isinstance(envelope, Mapping):
                continue
            blocker = envelope.get("blocker", {})
            if not isinstance(blocker, Mapping):
                continue
            if blocker.get("policy") != "repeated_observation_v1":
                continue
            if normalize_evidence_key(blocker.get("code")).replace(" ", "_") != code:
                continue
            checked = validate_evidence_envelope(
                envelope,
                expected_scope=scope,
                producer_boundary=self.evidence_producer,
            )
            if not checked.get("valid") or checked.get("status") not in {"failed", "error", "blocked"}:
                continue
            observation_id = str(
                envelope.get("command_id")
                or envelope.get("result_id")
                or envelope.get("tool_call_id")
                or envelope.get("observed_at")
                or ""
            )
            if observation_id and observation_id not in observation_ids:
                observation_ids.append(observation_id)
        return observation_ids

    def _record_evaluation(
        self,
        state: Dict[str, Any],
        goal: Dict[str, Any],
        evaluation: Dict[str, Any],
        *,
        workflow_success: bool | None = None,
    ) -> Dict[str, Any]:
        metadata = dict(goal.get("metadata", {}))
        evaluation_metadata = dict(evaluation.get("metadata", {}))
        metadata["last_evaluation"] = {
            "status": evaluation.get("status", ""),
            "missing_evidence": list(evaluation_metadata.get("missing_evidence", [])),
            "missing_goal_requirements": list(
                evaluation_metadata.get("missing_goal_requirements", [])
            ),
            "unmapped_success_criteria": list(
                evaluation_metadata.get("unmapped_success_criteria", [])
            ),
        }
        if workflow_success is not None:
            metadata["last_workflow_success"] = bool(workflow_success)
        goal["metadata"] = metadata
        return self._save_from_state(goal, state)

    def _save_from_state(
        self,
        goal: Dict[str, Any],
        state: Dict[str, Any],
        *,
        active_task: str | None = None,
        next_action: str | None = None,
    ) -> Dict[str, Any]:
        return self._save(
            goal,
            active_task=state.get("active_task", "") if active_task is None else active_task,
            tasks=state.get("tasks", {}),
            next_action=state.get("next_recommended_action", "") if next_action is None else next_action,
            expected_revision=str(state.get("_ledger_revision", "")),
        )

    def _save(
        self,
        goal: Dict[str, Any],
        *,
        active_task: str = "",
        tasks: Dict[str, List[str]] | None = None,
        next_action: str = "",
        transition: str = "",
        expected_revision: str | None = None,
    ) -> Dict[str, Any]:
        normalized_goal = self._normalized_goal(goal)
        with _runtime_only_goal_storage():
            return self.ledger.save_current_goal(
                normalized_goal,
                active_task=active_task,
                tasks=tasks,
                next_recommended_action=next_action,
                transition=transition,
                expected_revision=expected_revision,
            )

    def _normalized_goal(self, goal: Mapping[str, Any]) -> Dict[str, Any]:
        normalized_goal = deepcopy(dict(goal))
        metadata = dict(normalized_goal.get("metadata", {}))
        metadata.pop("content_hash", None)
        normalized_goal["metadata"] = metadata
        metadata["content_hash"] = _goal_content_hash(normalized_goal)
        normalized_goal["metadata"] = metadata
        return normalized_goal

    def _result(self, command: str, state: Dict[str, Any]) -> Dict[str, Any]:
        goal = dict(state.get("goal", {}))
        backend = str(goal.get("metadata", {}).get("goal_backend", "kh_ledger"))
        return {
            "command": command,
            "status": goal.get("status", state.get("status", "unknown")),
            "goal_backend": backend,
            "goal": goal,
            "goal_ledger": self.ledger.describe_paths(),
            "runtime_receipt": self._runtime_receipt(command, state),
            "runtime_channels": _runtime_channels(backend, True),
        }

    def _runtime_receipt(self, operation: str, state: Dict[str, Any]) -> Dict[str, Any]:
        goal = state.get("goal", {})
        metadata = goal.get("metadata", {})
        scope = metadata.get("scope", {})
        content_hash = _sha256_bytes(self.ledger.current_goal_path.read_bytes())
        status = str(goal.get("status") or "")
        result_id = sha256_text(
            f"{operation}:{content_hash}:{scope.get('goal_id', '')}:{status}"
        )
        receipt = {
            "schema_version": 1,
            "receipt_type": "kh_goal_ledger",
            "operation": operation,
            "result_id": result_id,
            "status": status,
            "project_id": str(scope.get("project_id") or ""),
            "thread_id": str(scope.get("thread_id") or ""),
            "task_id": str(scope.get("task_id") or ""),
            "goal_id": str(scope.get("goal_id") or ""),
            "lineage_id": str(scope.get("lineage_id") or ""),
            "objective_hash": str(scope.get("objective_hash") or ""),
            "state_path": str(self.ledger.current_goal_path.resolve()),
            "content_hash": content_hash,
            "goal_content_hash": str(metadata.get("content_hash") or ""),
            "observed_at": str(state.get("updated_at") or _utc_now()),
        }
        return self.receipt_producer.issue_claim(
            receipt,
            claim_kind="kh_goal_ledger_runtime",
            claim_id_field="producer_receipt_id",
            claim_id_prefix="receipt",
        )


def _goal_spec(context: Mapping[str, Any], objective: str) -> Dict[str, Any]:
    configured = context.get("goal_spec", {})
    configured = dict(configured) if isinstance(configured, Mapping) else {}
    concrete_objective = str(configured.get("objective") or objective or context.get("objective") or "").strip()
    criteria = _dedupe(configured.get("success_criteria", []) or context.get("success_criteria", []) or [])
    required = _dedupe(configured.get("evidence_required", []) or context.get("goal_evidence_required", []) or [])
    return {
        "objective": concrete_objective,
        "success_criteria": criteria,
        "evidence_required": required,
    }


def _criterion_map(
    criteria: List[str],
    required: List[str],
    configured: Mapping[str, Iterable[str]] | None,
) -> Dict[str, List[str]]:
    if configured is None:
        if len(criteria) != len(required):
            raise ValueError("criterion evidence mapping is required for every success criterion")
        return {criterion: [required[index]] for index, criterion in enumerate(criteria)}
    normalized: Dict[str, List[str]] = {}
    for criterion, values in dict(configured).items():
        key = normalize_evidence_key(criterion)
        if isinstance(values, str):
            values = [values]
        normalized[key] = _dedupe(values or [])
    unmapped = [criterion for criterion in criteria if not normalized.get(criterion)]
    if unmapped:
        raise ValueError("criterion evidence mapping is required for every success criterion")
    unknown = [
        evidence_key
        for values in normalized.values()
        for evidence_key in values
        if evidence_key not in required
    ]
    if unknown:
        raise ValueError("criterion evidence mapping references undeclared evidence")
    return {criterion: normalized[criterion] for criterion in criteria}


def _goal_content_hash(goal: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(goal))
    metadata = dict(payload.get("metadata", {}))
    metadata.pop("content_hash", None)
    payload["metadata"] = metadata
    return sha256_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True))


def _project_id(project: str) -> str:
    return sha256_text(str(Path(project).resolve()).lower())


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _valid_hash(value: str) -> bool:
    return len(value) == 71 and value.startswith("sha256:") and all(
        character in "0123456789abcdef" for character in value[7:].lower()
    )


def _valid_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return False
    return parsed.tzinfo is not None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _receipt_validation(valid: bool, errors: Iterable[str], **extra: Any) -> Dict[str, Any]:
    return {
        "valid": bool(valid),
        "errors": _unique_strings(errors),
        "validation_scope": "unverified_receipt_structure_and_scope_correlation",
        "external_authenticity": "unverified",
        **extra,
    }


def _runtime_channels(backend: str, kh_executed: bool) -> Dict[str, Dict[str, Any]]:
    return {
        "routing": {"status": "required"},
        "kh_goal_ledger": {"status": "executed" if kh_executed else "not_executed"},
        "host_goal": {
            "status": "executed" if backend == "hybrid" else "not_executed"
        },
    }


def _dedupe(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        normalized = normalize_evidence_key(value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _unique_strings(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value or "")
        if text and text not in result:
            result.append(text)
    return result


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "allowed", "authorized"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def _runtime_only_goal_storage():
    configured = "UAF_PROJECT_MARKDOWN" in os.environ
    previous = os.environ.get("UAF_PROJECT_MARKDOWN")
    if not configured:
        os.environ["UAF_PROJECT_MARKDOWN"] = "0"
    try:
        yield
    finally:
        if not configured:
            os.environ.pop("UAF_PROJECT_MARKDOWN", None)
        elif previous is not None:
            os.environ["UAF_PROJECT_MARKDOWN"] = previous


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=".", help="Target project used to scope GoalLedger state.")
    parser.add_argument("--thread-id", default="", help="Optional host thread id for chat-scoped state.")
    parser.add_argument("--task-id", default="", help="Optional host task id for receipt correlation.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the dependency-free KH Goal runtime.")
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start")
    _add_common_arguments(start)
    start.add_argument("--objective", required=True)
    start.add_argument("--success-criterion", action="append", default=[])
    start.add_argument("--evidence-required", action="append", default=[])
    start.add_argument("--criterion-evidence-map-json", default="")
    start.add_argument("--goal-optional", action="store_true")
    start.add_argument("--backend", choices=sorted(GOAL_BACKENDS), default="kh_ledger")
    start.add_argument("--host-goal-authorized", action="store_true")
    start.add_argument("--host-goal-receipt-json", default="")
    start.add_argument("--replacement-policy-json", default="")
    start.add_argument("--active-task", default="")
    start.add_argument("--next-action", default="")

    status = commands.add_parser("status")
    _add_common_arguments(status)

    evidence = commands.add_parser("add-evidence")
    _add_common_arguments(evidence)
    evidence.add_argument("--evidence", action="append", default=[])
    evidence.add_argument("--envelope-json", action="append", default=[])
    evidence.add_argument("--evidence-status", choices=["passed", "failed", "pending"], default="passed")
    evidence.add_argument("--detail", default="")

    capture = commands.add_parser("capture-evidence")
    _add_common_arguments(capture)
    capture.add_argument("--evidence-type", choices=["artifact", "command", "test"], required=True)
    capture.add_argument("--evidence-key", required=True)
    capture.add_argument("--artifact", default="")
    capture.add_argument("--command-result-file", default="")
    capture.add_argument("--producer", default="kh_goal_runtime_capture")
    capture.add_argument("--detail", default="")

    update = commands.add_parser("update")
    _add_common_arguments(update)
    update.add_argument("--success-criterion", action="append", default=[])
    update.add_argument("--evidence-required", action="append", default=[])
    update.add_argument("--criterion-evidence-map-json", default="")
    update.add_argument("--progress-note", action="append", default=[])
    update.add_argument("--active-task", default=None)
    update.add_argument("--next-action", default=None)

    evaluate = commands.add_parser("evaluate")
    _add_common_arguments(evaluate)
    evaluate.add_argument("--envelope-json", action="append", default=[])
    evaluate.add_argument("--workflow-failed", action="store_true")

    close = commands.add_parser("close")
    _add_common_arguments(close)
    close.add_argument("--status", choices=["complete", "blocked"], default="complete")
    close.add_argument("--blocked-reason", default="")
    close.add_argument("--blocker-code", default="")
    return parser


def main(argv: List[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    runtime = GoalRuntime(args.project, thread_id=args.thread_id, task_id=args.task_id)
    try:
        if args.command == "start":
            result = runtime.start(
                objective=args.objective,
                success_criteria=args.success_criterion,
                evidence_required=args.evidence_required,
                criterion_evidence_map=(
                    json.loads(args.criterion_evidence_map_json)
                    if args.criterion_evidence_map_json
                    else None
                ),
                goal_required=not args.goal_optional,
                goal_backend=args.backend,
                host_goal_authorized=args.host_goal_authorized,
                host_goal_receipt=(
                    json.loads(args.host_goal_receipt_json)
                    if args.host_goal_receipt_json
                    else None
                ),
                replacement_policy=(
                    json.loads(args.replacement_policy_json)
                    if args.replacement_policy_json
                    else None
                ),
                active_task=args.active_task,
                next_action=args.next_action,
            )
        elif args.command == "status":
            result = runtime.status()
        elif args.command == "add-evidence":
            items: List[Any] = list(args.evidence)
            items.extend(json.loads(value) for value in args.envelope_json)
            result = runtime.add_evidence(items, evidence_status=args.evidence_status, detail=args.detail)
        elif args.command == "capture-evidence":
            result = runtime.capture_evidence(
                evidence_type=args.evidence_type,
                evidence_key=args.evidence_key,
                artifact=args.artifact,
                command_result_file=args.command_result_file,
                producer=args.producer,
                detail=args.detail,
            )
        elif args.command == "update":
            result = runtime.update(
                success_criteria=args.success_criterion,
                evidence_required=args.evidence_required,
                criterion_evidence_map=(
                    json.loads(args.criterion_evidence_map_json)
                    if args.criterion_evidence_map_json
                    else None
                ),
                progress_notes=args.progress_note,
                active_task=args.active_task,
                next_action=args.next_action,
            )
        elif args.command == "evaluate":
            result = runtime.evaluate(
                workflow_evidence=[json.loads(value) for value in args.envelope_json],
                workflow_success=not args.workflow_failed,
            )
        else:
            result = runtime.close(
                status=args.status,
                blocked_reason=args.blocked_reason,
                blocker_code=args.blocker_code,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.command == "close" and not result.get("closed", False):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
