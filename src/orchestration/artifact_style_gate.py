"""Authenticated post-write style gates for C#, SQL, and visual artifacts.

Caller metadata may request a gate, but it can never satisfy one. Passing
evidence is created only after this module reads project-bounded files, invokes
the packaged verifier, and signs the exact result with RuntimeProducerBoundary.
"""

from __future__ import annotations

import json
import os
import re
import copy
import shutil
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

from src.orchestration.goal_evidence import RuntimeProducerBoundary
from src.orchestration.runtime_paths import runtime_root


CSHARP_STYLE_SKILL = "csharp-designer-style-harness"
SQL_FORMATTING_SKILL = "sql-formatting"
SQL_STYLE_SKILL = "sql-formatting-style-harness"
VISUAL_STYLE_SKILL = "artifact-render-qa-harness"

ARTIFACT_STYLE_PRODUCER = "kh-artifact-style-runtime"
ARTIFACT_STYLE_RECEIPT_KIND = "artifact_style_verifier_v1"
ARTIFACT_STYLE_SNAPSHOT_KIND = "artifact_style_snapshot_v1"
ARTIFACT_VISUAL_RECEIPT_KIND = "artifact_visual_qa_v1"
ARTIFACT_HOST_CALL_KIND = "artifact_host_call_v1"
ARTIFACT_HOST_RESULT_KIND = "artifact_host_result_v1"
ARTIFACT_GENERATION_PREWRITE_KIND = "artifact_generation_prewrite_v1"
ARTIFACT_GENERATION_PREWRITE_TOOL = "artifact-generation-prewrite-observer"
ARTIFACT_MODIFICATION_PREEDIT_KIND = "artifact_modification_preedit_v1"
ARTIFACT_MODIFICATION_PREEDIT_TOOL = "artifact-modification-preedit-snapshot"
ARTIFACT_OPERATION_RETRY_KIND = "artifact_operation_retry_v1"
ARTIFACT_RETRY_SNAPSHOT_MARKER_KIND = "artifact_retry_snapshot_marker_v1"
_ARTIFACT_RETRY_MARKER_FILE = ".kh-retry-snapshot.json"
_ABSENT_ARTIFACT_SHA256 = sha256(b"kh-artifact-path-absent-v1").hexdigest()

_CONTEXT_KEYS = ("runtime_context", "execution_context", "plan", "tool_metadata")
_ARTIFACT_KEYS = (
    "changed_artifacts",
    "generated_artifacts",
    "modified_artifacts",
    "artifact_manifest",
    "artifacts",
)
_RECEIPT_KEYS = (
    "style_receipts",
    "artifact_style_receipts",
    "verification_receipts",
)
_VISUAL_RECEIPT_KEYS = ("visual_qa_receipts", "render_qa_receipts")
_CHANGE_OPERATIONS = {
    "create", "created", "generate", "generated", "modify", "modified",
    "generation", "modification", "write", "written", "update", "updated",
}
_DEPLOY_OPERATIONS = {
    "deploy", "deployed", "execute", "executed", "db_deploy",
    "database_deploy",
}
_COMPLETION_KEYS = {
    "completion", "completion_claim", "implementation_complete", "release",
    "deployment", "deployment_claim", "build_success", "db_success",
    "database_success",
}
_VISUAL_COMPLETION_KEYS = {
    "ui_behavior_complete", "ui_behavior_completion",
    "ui_appearance_complete", "ui_appearance_completion", "visual_completion",
}
_ARTIFACT_ROLES = {
    "winforms_codebehind",
    "winforms_designer",
    "sql_candidate",
}
_VISUAL_PROVIDERS = {
    "browser",
    "in-app-browser",
    "playwright",
    "render",
    "designer",
}
_SUCCESS = {"passed", "pass", "success", "ok"}
_FAILURE = {"blocked", "failed", "fail", "error"}

_STYLE_TOOL_BY_GATE = {
    CSHARP_STYLE_SKILL: "csharp-designer-style-verifier",
    SQL_FORMATTING_SKILL: "sql-formatting-provider",
    SQL_STYLE_SKILL: "sql-formatting-style-verifier",
}

_HOST_REGISTRY_LOCK = threading.Lock()
_HOST_REGISTRIES: Dict[str, "HostCallResultRegistry"] = {}
_HOST_REGISTRY_ORDER: List[str] = []
_HOST_REGISTRY_LIMIT = 256
_CSHARP_RETRY_LIMIT = 16
_CSHARP_RETRY_TTL_SECONDS = 15 * 60
_CSHARP_RETRY_MAX_ATTEMPTS = 3
_CSHARP_OPERATION_RECEIPT_VALIDITY_SECONDS = 24 * 60 * 60
_CSHARP_RETRY_LOCK = threading.Lock()
_CSHARP_RETRY_STATES: Dict[str, Dict[str, Any]] = {}
_CSHARP_RETRY_PERSISTING: set[str] = set()
_GLOBAL_EXECUTION_SEQUENCE_LOCK = threading.Lock()
_GLOBAL_EXECUTION_SEQUENCE = 0
_EXECUTOR_REGISTRY_OWNERSHIP = object()


def sha256_bytes(value: bytes) -> str:
    return f"sha256:{sha256(value).hexdigest()}"


def _json_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return sha256_bytes(raw)


def _as_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_rows(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, Mapping):
        value = (
            value.get("items")
            or value.get("artifacts")
            or value.get("receipts")
            or [value]
        )
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _contexts(context: Mapping[str, Any] | None) -> List[Dict[str, Any]]:
    root = _as_mapping(context)
    result = [root]
    for key in _CONTEXT_KEYS:
        nested = root.get(key)
        if isinstance(nested, Mapping):
            result.append(dict(nested))
    return result


def _canonical_hash(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("sha256:"):
        text = text[7:]
    return f"sha256:{text}" if re.fullmatch(r"[0-9a-f]{64}", text) else ""


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _same_physical_file(first: Path, second: Path) -> bool:
    if _path_key(first) == _path_key(second):
        return True
    try:
        return os.path.samefile(first, second)
    except (OSError, ValueError):
        return False


def _canonical_project_root(value: Any) -> tuple[Path | None, str]:
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        return None, "project_root_missing"
    supplied = Path(str(value).strip())
    if not supplied.is_absolute() or ".." in supplied.parts:
        return None, "project_root_not_canonical_absolute"
    try:
        resolved = supplied.resolve(strict=False)
    except OSError:
        return None, "project_root_unresolvable"
    if not resolved.is_dir():
        return None, "project_root_missing"
    return resolved, ""


def _canonical_project_target(
    value: Any,
    project_root: Path,
) -> tuple[Path | None, str]:
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        return None, "artifact_path_missing"
    supplied = Path(str(value).strip())
    if not supplied.is_absolute():
        return None, "artifact_path_relative"
    if ".." in supplied.parts:
        return None, "artifact_path_parent_traversal"
    try:
        resolved = supplied.resolve(strict=False)
    except OSError:
        return None, "artifact_path_unresolvable"
    try:
        common = os.path.commonpath((_path_key(project_root), _path_key(resolved)))
    except ValueError:
        return None, "artifact_path_outside_project"
    if common != _path_key(project_root):
        return None, "artifact_path_outside_project"
    if not resolved.parent.is_dir():
        return None, "artifact_parent_missing"
    return resolved, ""


def _canonical_project_file(
    value: Any,
    project_root: Path,
) -> tuple[Path | None, str]:
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        return None, "artifact_path_missing"
    supplied = Path(str(value).strip())
    if not supplied.is_absolute():
        return None, "artifact_path_relative"
    if ".." in supplied.parts:
        return None, "artifact_path_parent_traversal"
    try:
        resolved = supplied.resolve(strict=False)
    except OSError:
        return None, "artifact_path_unresolvable"
    try:
        common = os.path.commonpath((_path_key(project_root), _path_key(resolved)))
    except ValueError:
        return None, "artifact_path_outside_project"
    if common != _path_key(project_root):
        return None, "artifact_path_outside_project"
    if not resolved.is_file():
        return None, "artifact_path_not_file"
    return resolved, ""


def _project_root(
    context: Mapping[str, Any] | None,
    explicit: str | os.PathLike[str] | None = None,
) -> tuple[Path | None, str]:
    root = _as_mapping(context)
    value = (
        explicit
        if explicit is not None
        else root.get("project") or root.get("project_root")
    )
    return _canonical_project_root(value)


def _artifact_style_runtime_state_dir(project_root: Path) -> Path:
    project_key = sha256(_path_key(project_root).encode("utf-8")).hexdigest()[:24]
    return runtime_root() / "runtime-receipts" / "artifact-style" / project_key


def _runtime_boundary(project_root: Path) -> RuntimeProducerBoundary:
    return RuntimeProducerBoundary(
        ARTIFACT_STYLE_PRODUCER,
        state_dir=_artifact_style_runtime_state_dir(project_root),
    )


def _retry_record_directory(project_root: Path) -> Path:
    return _artifact_style_runtime_state_dir(project_root) / "retry-snapshots"


def _retry_record_path(project_root: Path, retry_id: str) -> Path:
    record_name = sha256(str(retry_id).encode("utf-8")).hexdigest() + ".json"
    return _retry_record_directory(project_root) / record_name


def _runtime_output(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        if isinstance(converted, Mapping):
            return dict(converted)
    return {
        "status": "blocked",
        "success": False,
        "exit_code": 1,
        "error": "host_runner_result_not_mapping",
    }


def _runtime_output_passed(value: Mapping[str, Any]) -> bool:
    status = str(value.get("status") or "").strip().lower()
    success = value.get("success")
    exit_code = value.get("exit_code")
    if isinstance(exit_code, bool):
        return False
    if isinstance(exit_code, int) and exit_code != 0:
        return False
    return success is True or status in _SUCCESS


def _next_execution_sequence() -> int:
    global _GLOBAL_EXECUTION_SEQUENCE
    with _GLOBAL_EXECUTION_SEQUENCE_LOCK:
        _GLOBAL_EXECUTION_SEQUENCE = max(
            _GLOBAL_EXECUTION_SEQUENCE + 1,
            time.monotonic_ns(),
        )
        return _GLOBAL_EXECUTION_SEQUENCE


class HostCallResultRegistry:
    """Host-owned registry for exact runner calls and their returned results."""

    def __init__(
        self,
        producer_boundary: RuntimeProducerBoundary,
        *,
        _ownership_token: object | None = None,
    ):
        if not isinstance(producer_boundary, RuntimeProducerBoundary):
            raise TypeError("producer_boundary must be RuntimeProducerBoundary")
        self.producer_boundary = producer_boundary
        self.registry_id = f"host-registry-{uuid.uuid4().hex}"
        self._executor_owned = _ownership_token is _EXECUTOR_REGISTRY_OWNERSHIP
        self._lock = threading.Lock()
        self._records: Dict[str, Dict[str, Any]] = {}
        self._result_index: Dict[str, str] = {}

    @property
    def executor_owned(self) -> bool:
        return self._executor_owned

    def invoke(
        self,
        *,
        tool_name: str,
        producer_identity: str,
        artifact_path: str,
        artifact_sha256: str,
        input_payload: Mapping[str, Any],
        runner: Callable[[Dict[str, Any]], Any],
    ) -> Dict[str, Any]:
        if not callable(runner):
            raise ValueError("host runner is unavailable")
        sequence = _next_execution_sequence()
        normalized_tool = str(tool_name or "").strip()
        normalized_producer = str(producer_identity or "").strip()
        if not normalized_tool or not normalized_producer:
            raise ValueError("tool_name and producer_identity are required")
        request_payload = copy.deepcopy(dict(input_payload))
        input_hash = _json_hash(request_payload)
        call_issued_at = datetime.now(timezone.utc).isoformat()
        call_receipt = self.producer_boundary.issue_claim(
            {
                "schema_version": 1,
                "receipt_type": ARTIFACT_HOST_CALL_KIND,
                "host_registry_id": self.registry_id,
                "tool_name": normalized_tool,
                "producer_identity": normalized_producer,
                "sequence": sequence,
                "artifact_path": str(artifact_path),
                "artifact_sha256": str(artifact_sha256),
                "input_sha256": input_hash,
                "issued_at": call_issued_at,
            },
            claim_kind=ARTIFACT_HOST_CALL_KIND,
            claim_id_field="call_id",
            claim_id_prefix="artifact-call",
        )
        try:
            output = _runtime_output(runner(copy.deepcopy(request_payload)))
        except Exception as exc:  # Runtime failure is evidence, not a pass.
            output = {
                "status": "blocked",
                "success": False,
                "exit_code": 1,
                "error": type(exc).__name__,
                "message": str(exc),
            }
        result_status = "passed" if _runtime_output_passed(output) else "blocked"
        exit_code = output.get("exit_code")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int):
            exit_code = 0 if result_status == "passed" else 1
        result_artifact_path = str(
            output.get("artifact_path") or artifact_path
        )
        result_artifact_sha256 = _canonical_hash(
            output.get("formatted_sha256")
            or output.get("artifact_sha256")
        ) or str(artifact_sha256)
        result_issued_at = datetime.now(timezone.utc).isoformat()
        output_hash = _json_hash(output)
        result_receipt = self.producer_boundary.issue_claim(
            {
                "schema_version": 1,
                "receipt_type": ARTIFACT_HOST_RESULT_KIND,
                "host_registry_id": self.registry_id,
                "tool_name": normalized_tool,
                "producer_identity": normalized_producer,
                "sequence": sequence,
                "call_id": str(call_receipt["call_id"]),
                "artifact_path": result_artifact_path,
                "artifact_sha256": result_artifact_sha256,
                "input_sha256": input_hash,
                "output_sha256": output_hash,
                "status": result_status,
                "exit_code": exit_code,
                "issued_at": result_issued_at,
            },
            claim_kind=ARTIFACT_HOST_RESULT_KIND,
            claim_id_field="result_id",
            claim_id_prefix="artifact-result",
        )
        record = {
            "host_registry_id": self.registry_id,
            "tool_name": normalized_tool,
            "producer_identity": normalized_producer,
            "sequence": sequence,
            "artifact_path": str(artifact_path),
            "input_artifact_sha256": str(artifact_sha256),
            "input_payload": request_payload,
            "input_sha256": input_hash,
            "output": copy.deepcopy(output),
            "output_sha256": output_hash,
            "call_issued_at": call_issued_at,
            "result_issued_at": result_issued_at,
            "call_receipt": copy.deepcopy(call_receipt),
            "result_receipt": copy.deepcopy(result_receipt),
        }
        with self._lock:
            call_id = str(call_receipt["call_id"])
            result_id = str(result_receipt["result_id"])
            if call_id in self._records or result_id in self._result_index:
                raise RuntimeError("host call/result registry identity collision")
            self._records[call_id] = record
            self._result_index[result_id] = call_id
        return copy.deepcopy(record)

    def lookup(self, call_id: str) -> Dict[str, Any] | None:
        with self._lock:
            record = self._records.get(str(call_id or ""))
            return copy.deepcopy(record) if record is not None else None

    def lookup_result(self, result_id: str) -> Dict[str, Any] | None:
        with self._lock:
            call_id = self._result_index.get(str(result_id or ""))
            record = self._records.get(call_id or "")
            return copy.deepcopy(record) if record is not None else None


def _new_executor_host_registry(project_root: Path) -> HostCallResultRegistry:
    registry = HostCallResultRegistry(
        _runtime_boundary(project_root),
        _ownership_token=_EXECUTOR_REGISTRY_OWNERSHIP,
    )
    with _HOST_REGISTRY_LOCK:
        _HOST_REGISTRIES[registry.registry_id] = registry
        _HOST_REGISTRY_ORDER.append(registry.registry_id)
        while len(_HOST_REGISTRY_ORDER) > _HOST_REGISTRY_LIMIT:
            stale_id = _HOST_REGISTRY_ORDER.pop(0)
            _HOST_REGISTRIES.pop(stale_id, None)
    return registry


def _registered_host_registry(value: Any) -> HostCallResultRegistry | None:
    registry_id = str(value or "").strip()
    if not registry_id:
        return None
    with _HOST_REGISTRY_LOCK:
        registry = _HOST_REGISTRIES.get(registry_id)
    if registry is None or not registry.executor_owned:
        return None
    return registry


def _operation_registry_ids(rows: Sequence[Mapping[str, Any]]) -> List[str]:
    registry_ids: List[str] = []
    for row in rows:
        for key in (
            "generation_prewrite_receipt",
            "modification_preedit_receipt",
        ):
            receipt = row.get(key)
            if isinstance(receipt, Mapping):
                registry_id = str(receipt.get("host_registry_id") or "")
                if registry_id:
                    registry_ids.append(registry_id)
    return list(dict.fromkeys(registry_ids))


def _remove_host_registries(registry_ids: Iterable[str]) -> None:
    normalized = {str(item or "").strip() for item in registry_ids}
    normalized.discard("")
    if not normalized:
        return
    with _HOST_REGISTRY_LOCK:
        for registry_id in normalized:
            _HOST_REGISTRIES.pop(registry_id, None)
        _HOST_REGISTRY_ORDER[:] = [
            item for item in _HOST_REGISTRY_ORDER if item not in normalized
        ]


def _atomic_write_runtime_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
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


def _persist_csharp_retry_cleanup_record(
    *,
    project_root: Path,
    retry_receipt: Mapping[str, Any],
    snapshot_directory: str,
    snapshot_paths: Sequence[str],
) -> Dict[str, Any]:
    retry_id = str(retry_receipt.get("retry_id") or "")
    record_path = _retry_record_path(project_root, retry_id)
    marker: Dict[str, Any] = {}
    marker_path = ""
    if snapshot_directory:
        snapshot_dir, error = _canonical_project_target(
            snapshot_directory,
            project_root,
        )
        if (
            snapshot_dir is None
            or error
            or not snapshot_dir.is_dir()
            or snapshot_dir.parent != project_root
        ):
            raise ValueError("csharp_retry_snapshot_directory_not_owned")
        normalized_paths = []
        for path_text in snapshot_paths:
            snapshot, snapshot_error = _canonical_project_file(
                path_text,
                project_root,
            )
            if (
                snapshot is None
                or snapshot_error
                or snapshot.parent != snapshot_dir
            ):
                raise ValueError("csharp_retry_snapshot_path_not_owned")
            normalized_paths.append(
                {
                    "path": str(snapshot),
                    "sha256": sha256_bytes(snapshot.read_bytes()),
                }
            )
        marker_path = str(snapshot_dir / _ARTIFACT_RETRY_MARKER_FILE)
        marker = _runtime_boundary(project_root).issue_claim(
            {
                "schema_version": 1,
                "receipt_type": ARTIFACT_RETRY_SNAPSHOT_MARKER_KIND,
                "project_root": str(project_root),
                "retry_id": retry_id,
                "snapshot_directory": str(snapshot_dir),
                "snapshot_paths": normalized_paths,
                "marker_path": marker_path,
                "issued_at": datetime.now(timezone.utc).isoformat(),
            },
            claim_kind=ARTIFACT_RETRY_SNAPSHOT_MARKER_KIND,
            claim_id_field="marker_id",
            claim_id_prefix="artifact-retry-snapshot",
        )
    record = {
        "schema_version": 1,
        "retry_id": retry_id,
        "project_root": str(project_root),
        "retry_receipt": dict(retry_receipt),
        "snapshot_marker": marker,
    }
    try:
        _atomic_write_runtime_json(record_path, record)
        if marker_path:
            _atomic_write_runtime_json(Path(marker_path), marker)
    except Exception:
        record_path.unlink(missing_ok=True)
        if marker_path:
            Path(marker_path).unlink(missing_ok=True)
        raise
    return {
        "persistence_path": str(record_path),
        "snapshot_marker": marker,
    }


def _remove_authenticated_retry_snapshot(state: Mapping[str, Any]) -> bool:
    snapshot_directory = str(state.get("snapshot_directory") or "")
    if not snapshot_directory:
        return True
    marker = state.get("snapshot_marker")
    if not isinstance(marker, Mapping) or not marker:
        return False
    root, root_error = _canonical_project_root(marker.get("project_root"))
    if root is None or root_error:
        return False
    marker_errors = _runtime_boundary(root).validate_claim(
        marker,
        claim_kind=ARTIFACT_RETRY_SNAPSHOT_MARKER_KIND,
        claim_id_field="marker_id",
        consume=False,
    )
    if marker_errors or marker.get("receipt_type") != ARTIFACT_RETRY_SNAPSHOT_MARKER_KIND:
        return False
    snapshot_dir, error = _canonical_project_target(snapshot_directory, root)
    if (
        snapshot_dir is None
        or error
        or not snapshot_dir.is_dir()
        or snapshot_dir.parent != root
        or str(snapshot_dir) != str(marker.get("snapshot_directory") or "")
    ):
        return not Path(snapshot_directory).exists()
    marker_path = snapshot_dir / _ARTIFACT_RETRY_MARKER_FILE
    if str(marker_path) != str(marker.get("marker_path") or ""):
        return False
    if marker_path.exists():
        try:
            persisted_marker = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if _json_hash(persisted_marker) != _json_hash(marker):
            return False
    expected_paths: List[Path] = []
    for row in _as_rows(marker.get("snapshot_paths")):
        candidate = Path(str(row.get("path") or "")).resolve(strict=False)
        if candidate.parent != snapshot_dir:
            return False
        expected_paths.append(candidate)
    allowed = {_path_key(path) for path in expected_paths}
    allowed.add(_path_key(marker_path))
    try:
        children = list(snapshot_dir.iterdir())
    except OSError:
        return False
    if any(_path_key(child) not in allowed or not child.is_file() for child in children):
        return False
    try:
        for path in expected_paths:
            path.unlink(missing_ok=True)
        marker_path.unlink(missing_ok=True)
        snapshot_dir.rmdir()
    except OSError:
        return False
    return not snapshot_dir.exists()


def _remove_snapshot_directory(snapshot_directory: str) -> bool:
    path_text = str(snapshot_directory or "").strip()
    if not path_text:
        return True
    snapshot_path = Path(path_text)
    for attempt in range(3):
        try:
            shutil.rmtree(snapshot_path, ignore_errors=False)
        except FileNotFoundError:
            return True
        except OSError:
            if attempt < 2:
                time.sleep(0.01)
                continue
        return not snapshot_path.exists()
    return not snapshot_path.exists()


def _cleanup_csharp_retry_state(
    state: Dict[str, Any],
    *,
    terminal_reason: str,
) -> Dict[str, Any]:
    receipt = state.get("retry_receipt")
    claim_errors: List[str] = []
    if isinstance(receipt, Mapping):
        root, root_error = _canonical_project_root(receipt.get("project_root"))
        if root is None:
            claim_errors.append(root_error)
        else:
            claim_errors.extend(
                _runtime_boundary(root).validate_claim(
                    receipt,
                    claim_kind=ARTIFACT_OPERATION_RETRY_KIND,
                    claim_id_field="retry_id",
                    consume=True,
                )
            )
    snapshot_directory = str(state.get("snapshot_directory") or "")
    if state.get("persistence_path") or state.get("snapshot_marker"):
        snapshot_removed = _remove_authenticated_retry_snapshot(state)
    else:
        snapshot_removed = _remove_snapshot_directory(snapshot_directory)
    _remove_host_registries(state.get("operation_registry_ids", []))
    persistence_text = str(state.get("persistence_path") or "")
    if snapshot_removed and persistence_text:
        Path(persistence_text).unlink(missing_ok=True)
    state["context"] = {}
    state["targets"] = {}
    state["retry_receipt"] = {}
    state["operation_registry_ids"] = []
    state["snapshot_marker"] = {}
    state["persistence_path"] = ""
    return {
        "retry_id": str(receipt.get("retry_id") or "")
        if isinstance(receipt, Mapping)
        else "",
        "terminal_reason": terminal_reason,
        "snapshot_removed": snapshot_removed,
        "claim_errors": [
            item
            for item in claim_errors
            if item
            not in {"replayed_receipt", "runtime_producer_claim_expired"}
        ],
    }


def _persisted_retry_record_paths() -> List[Path]:
    root = runtime_root() / "runtime-receipts" / "artifact-style"
    if not root.is_dir():
        return []
    records: List[Path] = []
    for project_dir in root.iterdir():
        retry_dir = project_dir / "retry-snapshots"
        if not project_dir.is_dir() or not retry_dir.is_dir():
            continue
        records.extend(
            path for path in retry_dir.iterdir() if path.is_file() and path.suffix == ".json"
        )
    return sorted(records, key=lambda path: _path_key(path))


def _cleanup_abandoned_retry_records(active_retry_ids: set[str]) -> Dict[str, Any]:
    cleaned: List[Dict[str, Any]] = []
    rejected = 0
    for record_path in _persisted_retry_record_paths():
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            record_path.unlink(missing_ok=True)
            rejected += 1
            continue
        if not isinstance(record, Mapping):
            record_path.unlink(missing_ok=True)
            rejected += 1
            continue
        retry_receipt = record.get("retry_receipt")
        retry_id = str(record.get("retry_id") or "")
        if retry_id in active_retry_ids:
            continue
        if (
            not isinstance(retry_receipt, Mapping)
            or retry_id != str(retry_receipt.get("retry_id") or "")
        ):
            record_path.unlink(missing_ok=True)
            rejected += 1
            continue
        root, root_error = _canonical_project_root(record.get("project_root"))
        if (
            root is None
            or root_error
            or record_path != _retry_record_path(root, retry_id)
        ):
            record_path.unlink(missing_ok=True)
            rejected += 1
            continue
        receipt_errors = _runtime_boundary(root).validate_claim(
            retry_receipt,
            claim_kind=ARTIFACT_OPERATION_RETRY_KIND,
            claim_id_field="retry_id",
            consume=False,
        )
        if set(receipt_errors) - {
            "replayed_receipt",
            "runtime_producer_claim_expired",
        }:
            record_path.unlink(missing_ok=True)
            rejected += 1
            continue
        marker = record.get("snapshot_marker")
        snapshot_directory = (
            str(marker.get("snapshot_directory") or "")
            if isinstance(marker, Mapping)
            else ""
        )
        cleanup = _cleanup_csharp_retry_state(
            {
                "retry_receipt": dict(retry_receipt),
                "snapshot_directory": snapshot_directory,
                "snapshot_marker": dict(marker) if isinstance(marker, Mapping) else {},
                "persistence_path": str(record_path),
                "operation_registry_ids": [],
                "context": {},
                "targets": {},
            },
            terminal_reason="process_restart_invalidated",
        )
        if cleanup.get("snapshot_removed") and not cleanup.get("claim_errors"):
            cleaned.append(cleanup)
    return {
        "cleaned_count": len(cleaned),
        "rejected_record_count": rejected,
        "cleaned": cleaned,
    }


def sweep_csharp_artifact_retry_registry() -> Dict[str, Any]:
    """Expire bounded retry state and remove its snapshots and registries."""

    now = time.monotonic()
    expired: List[Dict[str, Any]] = []
    with _CSHARP_RETRY_LOCK:
        for retry_id, state in list(_CSHARP_RETRY_STATES.items()):
            if (
                not state.get("in_use")
                and float(state.get("expires_monotonic") or 0.0) <= now
            ):
                expired.append(_CSHARP_RETRY_STATES.pop(retry_id))
        active = len(_CSHARP_RETRY_STATES)
        active_retry_ids = set(_CSHARP_RETRY_STATES) | set(_CSHARP_RETRY_PERSISTING)
    cleaned = [
        _cleanup_csharp_retry_state(state, terminal_reason="expired")
        for state in expired
    ]
    abandoned = _cleanup_abandoned_retry_records(active_retry_ids)
    return {
        "status": "passed",
        "expired_count": len(cleaned),
        "active_count": active,
        "cleaned": cleaned,
        "restart_cleanup": abandoned,
        "limit": _CSHARP_RETRY_LIMIT,
        "ttl_seconds": _CSHARP_RETRY_TTL_SECONDS,
    }


def _register_csharp_retry_state(
    *,
    project_root: Path,
    pair_id: str,
    operation: str,
    context: Mapping[str, Any],
    targets: Mapping[str, Path],
    snapshot_directory: str,
    attempts: int,
) -> Dict[str, Any]:
    sweep_csharp_artifact_retry_registry()
    created_at = datetime.now(timezone.utc)
    ttl_seconds = max(0.0, float(_CSHARP_RETRY_TTL_SECONDS))
    expires_at = datetime.fromtimestamp(
        created_at.timestamp() + ttl_seconds,
        tz=timezone.utc,
    )
    rows = []
    for key in ("generated_artifacts", "changed_artifacts"):
        rows.extend(_as_rows(context.get(key)))
    snapshot_paths = [
        str(receipt.get("snapshot_path") or "")
        for row in rows
        for receipt in [row.get("modification_preedit_receipt")]
        if isinstance(receipt, Mapping)
        and str(receipt.get("snapshot_path") or "")
    ]
    payload = {
        "schema_version": 1,
        "receipt_type": ARTIFACT_OPERATION_RETRY_KIND,
        "status": "available",
        "project_root": str(project_root),
        "pair_id": pair_id,
        "operation": operation,
        "artifact_paths": {
            role: str(path) for role, path in sorted(targets.items())
        },
        "snapshot_paths": snapshot_paths,
        "context_sha256": _json_hash(context),
        "attempts": int(attempts),
        "max_attempts": int(_CSHARP_RETRY_MAX_ATTEMPTS),
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
    receipt = _runtime_boundary(project_root).issue_claim(
        payload,
        claim_kind=ARTIFACT_OPERATION_RETRY_KIND,
        claim_id_field="retry_id",
        claim_id_prefix="artifact-retry",
        validity_seconds=max(1.0, ttl_seconds),
    )
    retry_id = str(receipt["retry_id"])
    with _CSHARP_RETRY_LOCK:
        _CSHARP_RETRY_PERSISTING.add(retry_id)
    try:
        persistence = _persist_csharp_retry_cleanup_record(
            project_root=project_root,
            retry_receipt=receipt,
            snapshot_directory=snapshot_directory,
            snapshot_paths=snapshot_paths,
        )
    except Exception:
        with _CSHARP_RETRY_LOCK:
            _CSHARP_RETRY_PERSISTING.discard(retry_id)
        raise
    state = {
        "retry_receipt": copy.deepcopy(receipt),
        "context": copy.deepcopy(dict(context)),
        "targets": {role: str(path) for role, path in targets.items()},
        "snapshot_directory": snapshot_directory,
        "operation_registry_ids": _operation_registry_ids(rows),
        "attempts": int(attempts),
        "expires_monotonic": time.monotonic() + ttl_seconds,
        "in_use": False,
        **persistence,
    }
    evicted: List[Dict[str, Any]] = []
    registry_busy = False
    with _CSHARP_RETRY_LOCK:
        limit = max(1, int(_CSHARP_RETRY_LIMIT))
        while len(_CSHARP_RETRY_STATES) >= limit:
            oldest = next(
                (
                    retry_id
                    for retry_id, existing in _CSHARP_RETRY_STATES.items()
                    if not existing.get("in_use")
                ),
                "",
            )
            if not oldest:
                registry_busy = True
                break
            evicted.append(_CSHARP_RETRY_STATES.pop(oldest))
        if not registry_busy:
            _CSHARP_RETRY_STATES[retry_id] = state
        _CSHARP_RETRY_PERSISTING.discard(retry_id)
    for stale in evicted:
        _cleanup_csharp_retry_state(stale, terminal_reason="evicted")
    if registry_busy:
        _cleanup_csharp_retry_state(state, terminal_reason="registry_busy")
        raise RuntimeError("csharp_artifact_retry_registry_busy")
    return receipt


def _load_csharp_retry_state(
    retry_receipt: Mapping[str, Any] | Any,
    *,
    require_snapshots: bool = True,
) -> tuple[Dict[str, Any] | None, List[str]]:
    sweep_csharp_artifact_retry_registry()
    if not isinstance(retry_receipt, Mapping):
        return None, ["csharp_artifact_retry_receipt_missing"]
    root, root_error = _canonical_project_root(retry_receipt.get("project_root"))
    if root is None:
        return None, [root_error]
    errors = _runtime_boundary(root).validate_claim(
        retry_receipt,
        claim_kind=ARTIFACT_OPERATION_RETRY_KIND,
        claim_id_field="retry_id",
        consume=False,
    )
    if retry_receipt.get("receipt_type") != ARTIFACT_OPERATION_RETRY_KIND:
        errors.append("csharp_artifact_retry_receipt_type_mismatch")
    retry_id = str(retry_receipt.get("retry_id") or "")
    with _CSHARP_RETRY_LOCK:
        state = _CSHARP_RETRY_STATES.get(retry_id)
        state_copy = copy.deepcopy(state) if state is not None else None
    if state_copy is None:
        errors.append("csharp_artifact_retry_state_missing")
    else:
        if _json_hash(state_copy.get("context", {})) != retry_receipt.get(
            "context_sha256"
        ):
            errors.append("csharp_artifact_retry_context_mismatch")
        if state_copy.get("targets") != retry_receipt.get("artifact_paths"):
            errors.append("csharp_artifact_retry_targets_mismatch")
        snapshot_receipts = [
            receipt
            for key in ("generated_artifacts", "changed_artifacts")
            for row in _as_rows(state_copy.get("context", {}).get(key))
            for receipt in [row.get("modification_preedit_receipt")]
            if isinstance(receipt, Mapping)
        ]
        expected_snapshot_paths = [
            str(receipt.get("snapshot_path") or "")
            for receipt in snapshot_receipts
            if str(receipt.get("snapshot_path") or "")
        ]
        if expected_snapshot_paths != list(
            retry_receipt.get("snapshot_paths") or []
        ):
            errors.append("csharp_artifact_retry_snapshot_paths_mismatch")
        for receipt in snapshot_receipts if require_snapshots else []:
            snapshot, snapshot_error = _canonical_project_file(
                receipt.get("snapshot_path"),
                root,
            )
            if snapshot is None:
                errors.append(
                    f"csharp_artifact_retry_snapshot_unavailable:{snapshot_error}"
                )
                continue
            if sha256_bytes(snapshot.read_bytes()) != _canonical_hash(
                receipt.get("snapshot_sha256")
            ):
                errors.append("csharp_artifact_retry_snapshot_hash_mismatch")
    return state_copy if not errors else None, list(dict.fromkeys(errors))


def issue_csharp_generation_prewrite_receipt(
    *,
    project_root: str | os.PathLike[str],
    artifact_path: str | os.PathLike[str],
    artifact_role: str,
    pair_id: str,
) -> Dict[str, Any]:
    """Observe an absent C# target before creation and issue host-owned proof."""

    root, error = _canonical_project_root(project_root)
    if root is None:
        raise ValueError(error)
    target, error = _canonical_project_target(artifact_path, root)
    if target is None:
        raise ValueError(error)
    role = str(artifact_role or "").strip().lower()
    if role not in {"winforms_codebehind", "winforms_designer"}:
        raise ValueError("csharp_generation_artifact_role_invalid")
    normalized_pair_id = str(pair_id or "").strip()
    if not normalized_pair_id:
        raise ValueError("csharp_generation_pair_id_missing")
    if target.exists():
        raise ValueError("csharp_generation_target_already_exists")

    registry = _new_executor_host_registry(root)
    boundary = registry.producer_boundary
    absent_hash = f"sha256:{_ABSENT_ARTIFACT_SHA256}"
    producer_identity = (
        f"{ARTIFACT_STYLE_PRODUCER}:{ARTIFACT_GENERATION_PREWRITE_TOOL}"
    )
    request = {
        "project_root": str(root),
        "artifact_path": str(target),
        "artifact_role": role,
        "pair_id": normalized_pair_id,
        "expected_path_state": "absent",
    }

    def observe_absence(_request: Dict[str, Any]) -> Dict[str, Any]:
        observed_at = datetime.now(timezone.utc).isoformat()
        absent = not target.exists()
        return {
            "status": "passed" if absent else "blocked",
            "success": absent,
            "exit_code": 0 if absent else 1,
            "artifact_path": str(target),
            "artifact_sha256": absent_hash,
            "artifact_role": role,
            "pair_id": normalized_pair_id,
            "path_state": "absent" if absent else "present",
            "observed_at": observed_at,
        }

    execution = registry.invoke(
        tool_name=ARTIFACT_GENERATION_PREWRITE_TOOL,
        producer_identity=producer_identity,
        artifact_path=str(target),
        artifact_sha256=absent_hash,
        input_payload=request,
        runner=observe_absence,
    )
    output = dict(execution["output"])
    if (
        not _runtime_output_passed(output)
        or output.get("path_state") != "absent"
        or target.exists()
    ):
        raise RuntimeError("csharp_generation_prewrite_observation_failed")
    call_receipt = execution["call_receipt"]
    result_receipt = execution["result_receipt"]
    return boundary.issue_claim(
        {
            "schema_version": 1,
            "receipt_type": ARTIFACT_GENERATION_PREWRITE_KIND,
            "host_registry_id": registry.registry_id,
            "status": "passed",
            "project_root": str(root),
            "artifact_path": str(target),
            "artifact_role": role,
            "pair_id": normalized_pair_id,
            "path_state": "absent",
            "absent_artifact_sha256": absent_hash,
            "tool_name": ARTIFACT_GENERATION_PREWRITE_TOOL,
            "producer_identity": producer_identity,
            "sequence": int(call_receipt["sequence"]),
            "call_id": str(call_receipt["call_id"]),
            "result_id": str(result_receipt["result_id"]),
            "execution_output_sha256": str(result_receipt["output_sha256"]),
            "execution_input_artifact_sha256": absent_hash,
            "execution_call_receipt": dict(call_receipt),
            "execution_result_receipt": dict(result_receipt),
            "observed_at": str(output.get("observed_at") or ""),
            "issued_at": datetime.now(timezone.utc).isoformat(),
        },
        claim_kind=ARTIFACT_GENERATION_PREWRITE_KIND,
        claim_id_field="receipt_id",
        claim_id_prefix="artifact-generation-prewrite",
        validity_seconds=_CSHARP_OPERATION_RECEIPT_VALIDITY_SECONDS,
    )


def issue_csharp_modification_preedit_receipt(
    *,
    project_root: str | os.PathLike[str],
    artifact_path: str | os.PathLike[str],
    artifact_role: str,
    pair_id: str,
    snapshot_directory: str | os.PathLike[str],
) -> Dict[str, Any]:
    """Capture one host-owned pre-edit C# snapshot and bind its exact bytes."""

    root, error = _canonical_project_root(project_root)
    if root is None:
        raise ValueError(error)
    target, error = _canonical_project_file(artifact_path, root)
    if target is None:
        raise ValueError(error)
    role = str(artifact_role or "").strip().lower()
    if role not in {"winforms_codebehind", "winforms_designer"}:
        raise ValueError("csharp_modification_artifact_role_invalid")
    normalized_pair_id = str(pair_id or "").strip()
    if not normalized_pair_id:
        raise ValueError("csharp_modification_pair_id_missing")

    snapshot_root = Path(str(snapshot_directory or "").strip())
    if not snapshot_root.is_absolute():
        raise ValueError("csharp_modification_snapshot_directory_relative")
    snapshot_root = snapshot_root.resolve(strict=False)
    if not snapshot_root.is_dir():
        raise ValueError("csharp_modification_snapshot_directory_missing")
    try:
        common = os.path.commonpath(
            (_path_key(root), _path_key(snapshot_root))
        )
    except ValueError as exc:
        raise ValueError(
            "csharp_modification_snapshot_directory_outside_project"
        ) from exc
    if common != _path_key(root):
        raise ValueError("csharp_modification_snapshot_directory_outside_project")

    original_bytes = target.read_bytes()
    original_hash = sha256_bytes(original_bytes)
    snapshot = snapshot_root / (
        f"{role}-{uuid.uuid4().hex}.before.cs"
    )
    registry = _new_executor_host_registry(root)
    boundary = registry.producer_boundary
    producer_identity = (
        f"{ARTIFACT_STYLE_PRODUCER}:{ARTIFACT_MODIFICATION_PREEDIT_TOOL}"
    )
    request = {
        "project_root": str(root),
        "artifact_path": str(target),
        "artifact_role": role,
        "pair_id": normalized_pair_id,
        "original_artifact_sha256": original_hash,
        "snapshot_path": str(snapshot),
    }

    def capture_preedit(_request: Dict[str, Any]) -> Dict[str, Any]:
        current_bytes = target.read_bytes()
        current_hash = sha256_bytes(current_bytes)
        if current_hash != original_hash:
            return {
                "status": "blocked",
                "success": False,
                "exit_code": 1,
                "artifact_path": str(target),
                "artifact_sha256": current_hash,
                "reason": "source_changed_during_preedit_capture",
            }
        snapshot.write_bytes(current_bytes)
        captured_at = datetime.now(timezone.utc).isoformat()
        return {
            "status": "passed",
            "success": True,
            "exit_code": 0,
            "artifact_path": str(target),
            "artifact_sha256": original_hash,
            "artifact_role": role,
            "pair_id": normalized_pair_id,
            "snapshot_path": str(snapshot),
            "snapshot_sha256": sha256_bytes(snapshot.read_bytes()),
            "captured_at": captured_at,
        }

    execution = registry.invoke(
        tool_name=ARTIFACT_MODIFICATION_PREEDIT_TOOL,
        producer_identity=producer_identity,
        artifact_path=str(target),
        artifact_sha256=original_hash,
        input_payload=request,
        runner=capture_preedit,
    )
    output = dict(execution["output"])
    if (
        not _runtime_output_passed(output)
        or not snapshot.is_file()
        or sha256_bytes(snapshot.read_bytes()) != original_hash
        or sha256_bytes(target.read_bytes()) != original_hash
    ):
        raise RuntimeError("csharp_modification_preedit_capture_failed")
    call_receipt = execution["call_receipt"]
    result_receipt = execution["result_receipt"]
    return boundary.issue_claim(
        {
            "schema_version": 1,
            "receipt_type": ARTIFACT_MODIFICATION_PREEDIT_KIND,
            "host_registry_id": registry.registry_id,
            "status": "passed",
            "project_root": str(root),
            "artifact_path": str(target),
            "artifact_role": role,
            "pair_id": normalized_pair_id,
            "original_artifact_sha256": original_hash,
            "snapshot_path": str(snapshot),
            "snapshot_sha256": original_hash,
            "tool_name": ARTIFACT_MODIFICATION_PREEDIT_TOOL,
            "producer_identity": producer_identity,
            "sequence": int(call_receipt["sequence"]),
            "call_id": str(call_receipt["call_id"]),
            "result_id": str(result_receipt["result_id"]),
            "execution_output_sha256": str(result_receipt["output_sha256"]),
            "execution_input_artifact_sha256": original_hash,
            "execution_call_receipt": dict(call_receipt),
            "execution_result_receipt": dict(result_receipt),
            "captured_at": str(output.get("captured_at") or ""),
            "issued_at": datetime.now(timezone.utc).isoformat(),
        },
        claim_kind=ARTIFACT_MODIFICATION_PREEDIT_KIND,
        claim_id_field="receipt_id",
        claim_id_prefix="artifact-modification-preedit",
        validity_seconds=_CSHARP_OPERATION_RECEIPT_VALIDITY_SECONDS,
    )


def execute_csharp_artifact_operation(
    *,
    project_root: str | os.PathLike[str],
    pair_id: str,
    operation: str,
    codebehind_path: str | os.PathLike[str],
    designer_path: str | os.PathLike[str],
    write_artifacts: Callable[[Dict[str, Path]], Any],
    completion: bool = True,
    visual_completion: bool = False,
) -> Dict[str, Any]:
    """Execute one C# pair write through host-owned pre-write evidence and gates."""

    if not callable(write_artifacts):
        raise ValueError("csharp_artifact_writer_unavailable")
    sweep_csharp_artifact_retry_registry()
    root, error = _canonical_project_root(project_root)
    if root is None:
        raise ValueError(error)
    normalized_pair_id = str(pair_id or "").strip()
    if not normalized_pair_id:
        raise ValueError("csharp_artifact_pair_id_missing")
    from src.skills.csharp_designer_style import (
        normalize_csharp_source_operation,
    )

    normalized_operation = normalize_csharp_source_operation(operation)
    targets: Dict[str, Path] = {}
    for role, supplied in (
        ("winforms_codebehind", codebehind_path),
        ("winforms_designer", designer_path),
    ):
        if normalized_operation == "generation":
            target, target_error = _canonical_project_target(supplied, root)
            if target is not None and target.exists():
                target = None
                target_error = "csharp_generation_target_already_exists"
        else:
            target, target_error = _canonical_project_file(supplied, root)
        if target is None:
            raise ValueError(f"{target_error}:{supplied}")
        targets[role] = target
    if _same_physical_file(
        targets["winforms_codebehind"],
        targets["winforms_designer"],
    ):
        raise ValueError("csharp_artifact_pair_paths_not_distinct")

    def write_and_verify(
        rows: List[Dict[str, Any]],
        *,
        snapshot_directory: str = "",
    ) -> Dict[str, Any]:
        source_key = (
            "generated_artifacts"
            if normalized_operation == "generation"
            else "changed_artifacts"
        )
        context = {
            "project": str(root),
            source_key: rows,
            "completion": bool(completion),
            "visual_completion": bool(visual_completion),
        }
        writer_result: Any = None
        writer_error = ""
        try:
            writer_result = write_artifacts(dict(targets))
            missing = [
                str(target) for target in targets.values() if not target.is_file()
            ]
            if missing:
                raise RuntimeError(
                    "csharp_artifact_writer_missing_output:" + ",".join(missing)
                )
            gate = execute_artifact_style_precompletion(context)
        except Exception as exc:
            writer_error = f"{type(exc).__name__}:{exc}"
            gate = {
                "project_root": str(root),
                "required_skills": [CSHARP_STYLE_SKILL],
                "style_passed": False,
                "completion_blocked": True,
                "executor_status": "blocked",
                "executor_errors": [
                    f"csharp_artifact_writer_failed:{writer_error}"
                ],
                "operation_receipt_lifecycle": "retained_for_retry",
            }
        gate["artifact_operation"] = {
            "status": "passed" if gate.get("style_passed") else "blocked",
            "operation": normalized_operation,
            "pair_id": normalized_pair_id,
            "public_call_path": (
                "execute_csharp_artifact_operation>"
                "prewrite_or_preedit_receipt>write_artifacts>"
                "execute_artifact_style_precompletion"
            ),
            "writer_result_type": type(writer_result).__name__,
        }
        if writer_error:
            gate["artifact_operation"]["writer_error"] = writer_error
        if gate.get("style_passed"):
            snapshot_removed = _remove_snapshot_directory(snapshot_directory)
            _remove_host_registries(_operation_registry_ids(rows))
            if not snapshot_removed:
                gate["style_passed"] = False
                gate["completion_blocked"] = True
                gate["executor_status"] = "blocked"
                gate.setdefault("executor_errors", []).append(
                    "csharp_artifact_operation_snapshot_cleanup_failed"
                )
                gate["operation_receipt_lifecycle"] = "cleanup_blocked"
            gate["retry_state"] = {
                "status": "not_required" if snapshot_removed else "cleanup_blocked",
                "snapshot_cleanup": (
                    "completed" if snapshot_removed else "failed"
                ),
            }
            return gate

        try:
            retry_receipt = _register_csharp_retry_state(
                project_root=root,
                pair_id=normalized_pair_id,
                operation=normalized_operation,
                context=context,
                targets=targets,
                snapshot_directory=snapshot_directory,
                attempts=1,
            )
        except Exception as exc:
            _remove_snapshot_directory(snapshot_directory)
            _remove_host_registries(_operation_registry_ids(rows))
            gate.setdefault("executor_errors", []).append(
                "csharp_artifact_retry_registration_failed:"
                f"{type(exc).__name__}:{exc}"
            )
            gate["operation_receipt_lifecycle"] = "retry_unavailable"
            gate["retry_state"] = {"status": "unavailable"}
            return gate
        gate["operation_receipt_lifecycle"] = "retained_for_retry"
        gate["retry_receipt"] = retry_receipt
        gate["retry_state"] = {
            "status": "available",
            "attempts": 1,
            "max_attempts": _CSHARP_RETRY_MAX_ATTEMPTS,
            "expires_at": retry_receipt["expires_at"],
            "snapshot_paths": list(retry_receipt["snapshot_paths"]),
        }
        return gate

    if normalized_operation == "generation":
        rows = []
        try:
            for role, target in targets.items():
                receipt = issue_csharp_generation_prewrite_receipt(
                    project_root=root,
                    artifact_path=target,
                    artifact_role=role,
                    pair_id=normalized_pair_id,
                )
                rows.append(
                    {
                        "path": str(target),
                        "artifact_role": role,
                        "pair_id": normalized_pair_id,
                        "operation": "generation",
                        "generation_prewrite_receipt": receipt,
                    }
                )
        except Exception:
            _remove_host_registries(_operation_registry_ids(rows))
            raise
        return write_and_verify(rows)

    snapshot_directory = tempfile.mkdtemp(
        prefix=".kh-artifact-preedit-",
        dir=str(root),
    )
    rows = []
    try:
        for role, target in targets.items():
            receipt = issue_csharp_modification_preedit_receipt(
                project_root=root,
                artifact_path=target,
                artifact_role=role,
                pair_id=normalized_pair_id,
                snapshot_directory=snapshot_directory,
            )
            rows.append(
                {
                    "path": str(target),
                    "artifact_role": role,
                    "pair_id": normalized_pair_id,
                    "operation": "modification",
                    "modification_preedit_receipt": receipt,
                }
            )
    except Exception:
        _remove_snapshot_directory(snapshot_directory)
        _remove_host_registries(_operation_registry_ids(rows))
        raise
    return write_and_verify(rows, snapshot_directory=snapshot_directory)


def retry_csharp_artifact_operation(
    *,
    retry_receipt: Mapping[str, Any],
    write_artifacts: Callable[[Dict[str, Path]], Any],
) -> Dict[str, Any]:
    """Retry one failed C# operation with its preserved host-owned evidence."""

    if not callable(write_artifacts):
        raise ValueError("csharp_artifact_writer_unavailable")
    loaded, errors = _load_csharp_retry_state(retry_receipt)
    if loaded is None:
        return {
            "project_root": str(
                retry_receipt.get("project_root")
                if isinstance(retry_receipt, Mapping)
                else ""
            ),
            "style_passed": False,
            "completion_blocked": True,
            "executor_status": "blocked",
            "executor_errors": errors,
            "operation_receipt_lifecycle": "retry_unavailable",
            "retry_state": {"status": "unavailable"},
        }

    retry_id = str(retry_receipt.get("retry_id") or "")
    max_attempts = max(
        1,
        int(retry_receipt.get("max_attempts") or _CSHARP_RETRY_MAX_ATTEMPTS),
    )
    exhausted: Dict[str, Any] | None = None
    terminal_state: Dict[str, Any] | None = None
    attempts = 0
    with _CSHARP_RETRY_LOCK:
        state = _CSHARP_RETRY_STATES.get(retry_id)
        if state is None:
            return {
                "style_passed": False,
                "completion_blocked": True,
                "executor_status": "blocked",
                "executor_errors": ["csharp_artifact_retry_state_missing"],
                "operation_receipt_lifecycle": "retry_unavailable",
            }
        if state.get("in_use"):
            return {
                "style_passed": False,
                "completion_blocked": True,
                "executor_status": "blocked",
                "executor_errors": ["csharp_artifact_retry_already_in_use"],
                "operation_receipt_lifecycle": "retry_unavailable",
            }
        attempts = int(state.get("attempts") or 0) + 1
        if attempts > max_attempts:
            exhausted = _CSHARP_RETRY_STATES.pop(retry_id)
            state = None
        else:
            state["attempts"] = attempts
            state["in_use"] = True
            context = copy.deepcopy(state["context"])
            targets = {
                role: Path(path) for role, path in state["targets"].items()
            }
    if exhausted is not None:
        cleanup = _cleanup_csharp_retry_state(
            exhausted,
            terminal_reason="attempts_exhausted",
        )
        return {
            "style_passed": False,
            "completion_blocked": True,
            "executor_status": "blocked",
            "executor_errors": ["csharp_artifact_retry_attempts_exhausted"],
            "operation_receipt_lifecycle": "retry_exhausted",
            "retry_state": {"status": "exhausted", "cleanup": cleanup},
        }

    writer_result: Any = None
    writer_error = ""
    try:
        writer_result = write_artifacts(dict(targets))
        missing = [str(path) for path in targets.values() if not path.is_file()]
        if missing:
            raise RuntimeError(
                "csharp_artifact_writer_missing_output:" + ",".join(missing)
            )
        gate = execute_artifact_style_precompletion(context)
    except Exception as exc:
        writer_error = f"{type(exc).__name__}:{exc}"
        gate = {
            "project_root": str(retry_receipt.get("project_root") or ""),
            "style_passed": False,
            "completion_blocked": True,
            "executor_status": "blocked",
            "executor_errors": [
                f"csharp_artifact_retry_writer_failed:{writer_error}"
            ],
            "operation_receipt_lifecycle": "retained_for_retry",
        }

    gate["artifact_operation"] = {
        "status": "passed" if gate.get("style_passed") else "blocked",
        "operation": str(retry_receipt.get("operation") or ""),
        "pair_id": str(retry_receipt.get("pair_id") or ""),
        "public_call_path": (
            "retry_csharp_artifact_operation>write_artifacts>"
            "execute_artifact_style_precompletion"
        ),
        "writer_result_type": type(writer_result).__name__,
    }
    if writer_error:
        gate["artifact_operation"]["writer_error"] = writer_error

    if gate.get("style_passed"):
        with _CSHARP_RETRY_LOCK:
            terminal_state = _CSHARP_RETRY_STATES.pop(retry_id, None)
        cleanup = (
            _cleanup_csharp_retry_state(
                terminal_state,
                terminal_reason="succeeded",
            )
            if terminal_state is not None
            else {
                "terminal_reason": "succeeded",
                "snapshot_removed": True,
                "claim_errors": ["csharp_artifact_retry_state_missing"],
            }
        )
        if cleanup.get("claim_errors") or not cleanup.get("snapshot_removed"):
            gate["style_passed"] = False
            gate["completion_blocked"] = True
            gate["executor_status"] = "blocked"
            gate.setdefault("executor_errors", []).append(
                "csharp_artifact_retry_terminal_cleanup_failed"
            )
            gate["operation_receipt_lifecycle"] = "retry_cleanup_blocked"
            gate["artifact_operation"]["status"] = "blocked"
        gate["retry_state"] = {
            "status": (
                "completed"
                if gate.get("style_passed")
                else "cleanup_blocked"
            ),
            "cleanup": cleanup,
        }
        return gate

    current_missing = False
    with _CSHARP_RETRY_LOCK:
        current = _CSHARP_RETRY_STATES.get(retry_id)
        if current is not None:
            current["in_use"] = False
            attempts = int(current.get("attempts") or attempts)
            exhausted_now = attempts >= max_attempts
            if exhausted_now:
                terminal_state = _CSHARP_RETRY_STATES.pop(retry_id)
            else:
                terminal_state = None
        else:
            current_missing = True
    if current_missing:
        gate["operation_receipt_lifecycle"] = "retry_unavailable"
        gate.pop("retry_receipt", None)
        gate.setdefault("executor_errors", []).append(
            "csharp_artifact_retry_state_missing"
        )
        gate["retry_state"] = {"status": "unavailable"}
        return gate
    if terminal_state is not None:
        cleanup = _cleanup_csharp_retry_state(
            terminal_state,
            terminal_reason="attempts_exhausted",
        )
        gate["operation_receipt_lifecycle"] = "retry_exhausted"
        gate.pop("retry_receipt", None)
        gate["retry_state"] = {"status": "exhausted", "cleanup": cleanup}
        return gate

    gate["operation_receipt_lifecycle"] = "retained_for_retry"
    gate["retry_receipt"] = copy.deepcopy(dict(retry_receipt))
    gate["retry_state"] = {
        "status": "available",
        "attempts": attempts,
        "max_attempts": max_attempts,
        "expires_at": retry_receipt.get("expires_at"),
        "snapshot_paths": list(retry_receipt.get("snapshot_paths") or []),
    }
    return gate


def cancel_csharp_artifact_operation_retry(
    *,
    retry_receipt: Mapping[str, Any],
) -> Dict[str, Any]:
    """Cancel one retry and clean every host-owned snapshot and registry."""

    loaded, errors = _load_csharp_retry_state(
        retry_receipt,
        require_snapshots=False,
    )
    if loaded is None:
        return {
            "status": "blocked",
            "cancelled": False,
            "errors": errors,
        }
    retry_id = str(retry_receipt.get("retry_id") or "")
    with _CSHARP_RETRY_LOCK:
        state = _CSHARP_RETRY_STATES.get(retry_id)
        if state is None:
            return {
                "status": "blocked",
                "cancelled": False,
                "errors": ["csharp_artifact_retry_state_missing"],
            }
        if state.get("in_use"):
            return {
                "status": "blocked",
                "cancelled": False,
                "errors": ["csharp_artifact_retry_already_in_use"],
            }
        terminal_state = _CSHARP_RETRY_STATES.pop(retry_id)
    cleanup = _cleanup_csharp_retry_state(
        terminal_state,
        terminal_reason="cancelled",
    )
    return {
        "status": (
            "passed"
            if cleanup.get("snapshot_removed")
            and not cleanup.get("claim_errors")
            else "blocked"
        ),
        "cancelled": bool(
            cleanup.get("snapshot_removed")
            and not cleanup.get("claim_errors")
        ),
        "cleanup": cleanup,
    }


def _artifact_path(row: Mapping[str, Any]) -> str:
    return str(
        row.get("path") or row.get("artifact_path") or row.get("file") or ""
    ).strip()


def _artifact_role(row: Mapping[str, Any]) -> str:
    return str(row.get("artifact_role") or "").strip().lower()


def _artifact_hash(row: Mapping[str, Any]) -> str:
    return _canonical_hash(
        row.get("sha256")
        or row.get("artifact_hash")
        or row.get("content_sha256")
        or row.get("hash")
    )


def _is_changed(row: Mapping[str, Any], *, source_key: str) -> bool:
    if source_key in {
        "changed_artifacts",
        "generated_artifacts",
        "modified_artifacts",
    }:
        return True
    operation = str(
        row.get("operation")
        or row.get("change_type")
        or row.get("action")
        or ""
    ).strip().lower()
    return bool(
        row.get("generated") is True
        or row.get("modified") is True
        or row.get("changed") is True
        or operation in _CHANGE_OPERATIONS
    )


def _claim_is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {
        "true",
        "1",
        "yes",
        "passed",
        "success",
        "complete",
        "completed",
    }


def _completion_claimed(contexts: Iterable[Mapping[str, Any]]) -> bool:
    return any(
        _claim_is_true(row.get(key))
        for row in contexts
        for key in _COMPLETION_KEYS
    )


def _visual_completion_claimed(
    contexts: Iterable[Mapping[str, Any]],
) -> bool:
    return any(
        _claim_is_true(row.get(key))
        for row in contexts
        for key in _VISUAL_COMPLETION_KEYS
    )


def _nonempty_deployment_mapping(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and bool(value)
        and bool(_artifact_path(value))
        and _artifact_role(value) == "sql_candidate"
    )


def _db_deployment_evidence(
    contexts: Iterable[Mapping[str, Any]],
) -> bool:
    for row in contexts:
        for key in (
            "db_deployment",
            "database_deployment",
            "db_execution",
            "database_execution",
            "executed_candidate",
            "deployment_candidate",
        ):
            value = row.get(key)
            if _nonempty_deployment_mapping(value):
                return True
            if isinstance(value, list) and any(
                _nonempty_deployment_mapping(item) for item in value
            ):
                return True
        if any(
            str(row.get(key) or "").strip().lower() in _DEPLOY_OPERATIONS
            for key in ("operation", "action", "execution_kind")
        ):
            return bool(row.get("database_artifact_path"))
    return False


def _receipt_rows(
    contexts: Iterable[Mapping[str, Any]],
    keys: Sequence[str] = _RECEIPT_KEYS,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for context in contexts:
        for key in keys:
            rows.extend(_as_rows(context.get(key)))
    return rows


def _artifact_candidates(
    context: Mapping[str, Any] | None,
    project_root: Path,
    *,
    validated_operation_receipts: List[Dict[str, Any]] | None = None,
) -> tuple[List[Dict[str, Any]], List[str]]:
    candidates: List[Dict[str, Any]] = []
    errors: List[str] = []
    for source in _contexts(context):
        for key in _ARTIFACT_KEYS:
            for row in _as_rows(source.get(key)):
                role = _artifact_role(row)
                if (
                    role not in _ARTIFACT_ROLES
                    or not _is_changed(row, source_key=key)
                ):
                    continue
                path, error = _canonical_project_file(
                    _artifact_path(row),
                    project_root,
                )
                if error:
                    errors.append(f"{error}:{_artifact_path(row)}")
                    continue
                assert path is not None
                actual_hash = sha256_bytes(path.read_bytes())
                supplied_hash = _artifact_hash(row)
                if supplied_hash and supplied_hash != actual_hash:
                    errors.append(f"artifact_hash_mismatch:{path}")
                candidate = {
                    "path": str(path),
                    "path_key": _path_key(path),
                    "sha256": actual_hash,
                    "artifact_role": role,
                    "pair_id": str(
                        row.get("pair_id")
                        or row.get("artifact_pair_id")
                        or ""
                    ).strip(),
                    "operation": str(
                        row.get("operation")
                        or row.get("change_type")
                        or row.get("action")
                        or "modified"
                    ).strip().lower(),
                    "sequence": row.get("sequence"),
                    "result_id": str(row.get("result_id") or "").strip(),
                }
                if role in {"winforms_codebehind", "winforms_designer"}:
                    from src.skills.csharp_designer_style import (
                        normalize_csharp_source_operation,
                    )

                    try:
                        candidate["operation"] = normalize_csharp_source_operation(
                            candidate["operation"]
                        )
                    except ValueError:
                        errors.append(
                            f"csharp_source_operation_invalid:{path}:{candidate['operation']}"
                        )
                original_path_value = str(row.get("original_path") or "").strip()
                original_hash = _canonical_hash(row.get("original_sha256"))
                if (
                    role in {"winforms_codebehind", "winforms_designer"}
                    and candidate["operation"] == "generation"
                ):
                    if original_path_value or original_hash:
                        errors.append(
                            f"csharp_generation_original_conflict:{path}"
                        )
                    if key != "generated_artifacts":
                        errors.append(f"csharp_generation_context_invalid:{path}")
                    generation_receipt = row.get("generation_prewrite_receipt")
                    if not isinstance(generation_receipt, Mapping):
                        errors.append(
                            f"csharp_generation_prewrite_receipt_required:{path}"
                        )
                    else:
                        receipt_errors = (
                            _validate_csharp_generation_prewrite_receipt(
                                generation_receipt,
                                project_root=project_root,
                                artifact_path=path,
                                artifact_role=role,
                                pair_id=str(candidate.get("pair_id") or ""),
                                consume=False,
                            )
                        )
                        if receipt_errors:
                            errors.extend(
                                f"csharp_generation_prewrite_receipt_invalid:{path}:{item}"
                                for item in receipt_errors
                            )
                        else:
                            candidate["generation_prewrite_receipt_id"] = str(
                                generation_receipt.get("receipt_id") or ""
                            )
                            candidate["generation_prewrite_host_registry_id"] = str(
                                generation_receipt.get("host_registry_id") or ""
                            )
                            candidate["generation_prewrite_sequence"] = (
                                generation_receipt.get("sequence")
                            )
                            if validated_operation_receipts is not None:
                                validated_operation_receipts.append(
                                    {
                                        "kind": "generation",
                                        "receipt": generation_receipt,
                                        "path": path,
                                        "artifact_role": role,
                                        "pair_id": str(
                                            candidate.get("pair_id") or ""
                                        ),
                                    }
                                )
                if (
                    role in {"winforms_codebehind", "winforms_designer"}
                    and candidate["operation"] == "modification"
                ):
                    preedit_receipt = row.get("modification_preedit_receipt")
                    if not isinstance(preedit_receipt, Mapping):
                        errors.append(f"original_artifact_receipt_required:{path}")
                    else:
                        receipt_errors = (
                            _validate_csharp_modification_preedit_receipt(
                                preedit_receipt,
                                project_root=project_root,
                                artifact_path=path,
                                artifact_role=role,
                                pair_id=str(candidate.get("pair_id") or ""),
                                consume=False,
                            )
                        )
                        if receipt_errors:
                            errors.extend(
                                f"csharp_modification_preedit_receipt_invalid:{path}:{item}"
                                for item in receipt_errors
                            )
                        else:
                            original_path = Path(
                                str(preedit_receipt.get("snapshot_path") or "")
                            )
                            actual_original_hash = _canonical_hash(
                                preedit_receipt.get("snapshot_sha256")
                            )
                            if _same_physical_file(path, original_path):
                                errors.append(
                                    f"original_artifact_same_as_candidate:{path}"
                                )
                            else:
                                if original_path_value and (
                                    _path_key(Path(original_path_value))
                                    != _path_key(original_path)
                                ):
                                    errors.append(
                                        f"original_artifact_receipt_path_mismatch:{path}"
                                    )
                                if original_hash and original_hash != actual_original_hash:
                                    errors.append(
                                        f"original_artifact_receipt_hash_mismatch:{path}"
                                    )
                                candidate["original_path"] = str(original_path)
                                candidate["original_sha256"] = actual_original_hash
                                candidate["modification_preedit_receipt_id"] = str(
                                    preedit_receipt.get("receipt_id") or ""
                                )
                                candidate["modification_preedit_host_registry_id"] = str(
                                    preedit_receipt.get("host_registry_id") or ""
                                )
                                candidate["modification_preedit_sequence"] = (
                                    preedit_receipt.get("sequence")
                                )
                                if isinstance(row.get("edit_evidence"), Mapping):
                                    candidate["edit_evidence"] = dict(
                                        row["edit_evidence"]
                                    )
                                if validated_operation_receipts is not None:
                                    validated_operation_receipts.append(
                                        {
                                            "kind": "modification",
                                            "receipt": preedit_receipt,
                                            "path": path,
                                            "artifact_role": role,
                                            "pair_id": str(
                                                candidate.get("pair_id") or ""
                                            ),
                                        }
                                    )
                candidates.append(candidate)
        for key in (
            "db_deployment",
            "database_deployment",
            "deployment_candidate",
            "executed_candidate",
        ):
            for row in _as_rows(source.get(key)):
                if _artifact_role(row) != "sql_candidate":
                    continue
                path, error = _canonical_project_file(
                    _artifact_path(row),
                    project_root,
                )
                if error:
                    errors.append(f"{error}:{_artifact_path(row)}")
                    continue
                assert path is not None
                existing = [
                    item
                    for item in candidates
                    if item["path_key"] == _path_key(path)
                    and item["artifact_role"] == "sql_candidate"
                ]
                if existing:
                    supplied_hash = _artifact_hash(row)
                    if (
                        supplied_hash
                        and supplied_hash
                        != sha256_bytes(path.read_bytes())
                    ):
                        errors.append(
                            f"artifact_hash_mismatch:{path}"
                        )
                    continue
                candidates.append(
                    {
                        "path": str(path),
                        "path_key": _path_key(path),
                        "sha256": sha256_bytes(path.read_bytes()),
                        "artifact_role": "sql_candidate",
                        "pair_id": "",
                        "operation": "db_deploy",
                        "sequence": row.get("sequence"),
                        "result_id": str(row.get("result_id") or "").strip(),
                    }
                )

    by_path: Dict[str, List[Dict[str, Any]]] = {}
    for item in candidates:
        by_path.setdefault(item["path_key"], []).append(item)
    unique: List[Dict[str, Any]] = []
    for rows in by_path.values():
        if len(rows) != 1:
            errors.append(
                f"duplicate_or_replayed_artifact_path:{rows[0]['path']}"
            )
            continue
        row = dict(rows[0])
        row.pop("path_key", None)
        unique.append(row)
    unique.sort(key=lambda item: _path_key(Path(item["path"])))
    errors.extend(_validate_artifact_roles(unique))
    return unique, list(dict.fromkeys(errors))


def _partial_class_names(text: str) -> set[str]:
    return set(
        re.findall(
            r"\bpartial\s+class\s+([A-Za-z_][A-Za-z0-9_]*)",
            text,
        )
    )


def _validate_artifact_roles(
    artifacts: Sequence[Mapping[str, Any]],
) -> List[str]:
    errors: List[str] = []
    pairs: Dict[str, Dict[str, Mapping[str, Any]]] = {}
    for artifact in artifacts:
        role = str(artifact.get("artifact_role") or "")
        path = Path(str(artifact.get("path") or ""))
        if role == "sql_candidate":
            if path.suffix.casefold() not in {".sql", ".sproc", ".sp"}:
                errors.append(f"sql_artifact_role_mismatch:{path}")
            else:
                text = path.read_text(
                    encoding="utf-8-sig",
                    errors="replace",
                )
                if not re.search(
                    r"\b(?:SELECT|INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|EXEC)\b",
                    text,
                    re.IGNORECASE,
                ):
                    errors.append(f"sql_artifact_content_unverified:{path}")
            continue
        pair_id = str(artifact.get("pair_id") or "")
        if not pair_id:
            errors.append(f"winforms_pair_id_missing:{path}")
            continue
        pair = pairs.setdefault(pair_id, {})
        if role in pair:
            errors.append(f"winforms_pair_role_duplicate:{pair_id}:{role}")
        pair[role] = artifact
    for pair_id, pair in pairs.items():
        if set(pair) != {"winforms_codebehind", "winforms_designer"}:
            errors.append(f"winforms_pair_incomplete:{pair_id}")
            continue
        source = Path(str(pair["winforms_codebehind"]["path"]))
        designer = Path(str(pair["winforms_designer"]["path"]))
        expected_designer = f"{source.stem}.designer.cs".casefold()
        if (
            source.suffix.casefold() != ".cs"
            or designer.name.casefold() != expected_designer
        ):
            errors.append(f"winforms_pair_path_mismatch:{pair_id}")
            continue
        source_text = source.read_text(
            encoding="utf-8-sig",
            errors="replace",
        )
        designer_text = designer.read_text(
            encoding="utf-8-sig",
            errors="replace",
        )
        if (
            not (
                _partial_class_names(source_text)
                & _partial_class_names(designer_text)
            )
            or "InitializeComponent" not in designer_text
        ):
            errors.append(f"winforms_pair_structure_mismatch:{pair_id}")
    return errors


def _gate_for_role(role: str) -> List[str]:
    if role in {"winforms_codebehind", "winforms_designer"}:
        return [CSHARP_STYLE_SKILL]
    if role == "sql_candidate":
        return [SQL_FORMATTING_SKILL, SQL_STYLE_SKILL]
    return []


def _parse_issued_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _registry_for_receipt(
    receipt: Mapping[str, Any],
) -> tuple[HostCallResultRegistry | None, List[str]]:
    registry_id = str(receipt.get("host_registry_id") or "").strip()
    if not registry_id:
        return None, ["artifact_host_registry_id_missing"]
    registry = _registered_host_registry(registry_id)
    if registry is None:
        return None, ["artifact_host_registry_lookup_required"]
    return registry, []


def _validate_execution_correlation(
    receipt: Mapping[str, Any],
    *,
    registry: HostCallResultRegistry | None,
    expected_tool_name: str,
    expected_artifact_path: Path | None,
    expected_artifact_sha256: str,
) -> List[str]:
    errors: List[str] = []
    if registry is None:
        return ["artifact_host_registry_lookup_required"]
    boundary = registry.producer_boundary
    call = receipt.get("execution_call_receipt")
    result = receipt.get("execution_result_receipt")
    if not isinstance(call, Mapping):
        errors.append("artifact_execution_call_receipt_missing")
        call = {}
    else:
        errors.extend(
            boundary.validate_claim(
                call,
                claim_kind=ARTIFACT_HOST_CALL_KIND,
                claim_id_field="call_id",
                consume=False,
            )
        )
    if not isinstance(result, Mapping):
        errors.append("artifact_execution_result_receipt_missing")
        result = {}
    else:
        errors.extend(
            boundary.validate_claim(
                result,
                claim_kind=ARTIFACT_HOST_RESULT_KIND,
                claim_id_field="result_id",
                consume=False,
            )
        )

    call_id = str(receipt.get("call_id") or "").strip()
    result_id = str(receipt.get("result_id") or "").strip()
    registry_id = str(receipt.get("host_registry_id") or "").strip()
    producer_identity = str(receipt.get("producer_identity") or "").strip()
    tool_name = str(receipt.get("tool_name") or "").strip()
    sequence = receipt.get("sequence")
    if not call_id:
        errors.append("artifact_style_receipt_call_id_missing")
    if not result_id:
        errors.append("artifact_style_receipt_result_id_missing")
    if call_id and result_id and call_id == result_id:
        errors.append("artifact_execution_call_result_identity_collision")
    if registry_id != registry.registry_id:
        errors.append("artifact_host_registry_id_mismatch")
    expected_producer_identity = (
        f"{ARTIFACT_STYLE_PRODUCER}:{expected_tool_name}"
    )
    if producer_identity != expected_producer_identity:
        errors.append("artifact_style_receipt_producer_identity_mismatch")
    if tool_name != expected_tool_name:
        errors.append("artifact_style_receipt_tool_name_mismatch")
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= 0:
        errors.append("artifact_style_receipt_sequence_invalid")

    expected_path = str(expected_artifact_path) if expected_artifact_path else ""
    execution_input_hash = _canonical_hash(
        receipt.get("execution_input_artifact_sha256")
    ) or expected_artifact_sha256
    shared_expected = {
        "host_registry_id": registry.registry_id,
        "tool_name": expected_tool_name,
        "producer_identity": producer_identity,
        "sequence": sequence,
        "artifact_path": expected_path,
    }
    for key, value in shared_expected.items():
        if call.get(key) != value:
            errors.append(f"artifact_execution_call_{key}_mismatch")
        if result.get(key) != value:
            errors.append(f"artifact_execution_result_{key}_mismatch")
    if _canonical_hash(call.get("artifact_sha256")) != execution_input_hash:
        errors.append("artifact_execution_call_artifact_sha256_mismatch")
    if _canonical_hash(result.get("artifact_sha256")) != (
        expected_artifact_sha256
    ):
        errors.append("artifact_execution_result_artifact_sha256_mismatch")
    if str(call.get("call_id") or "") != call_id:
        errors.append("artifact_execution_call_id_mismatch")
    if str(result.get("call_id") or "") != call_id:
        errors.append("artifact_execution_result_call_id_mismatch")
    if str(result.get("result_id") or "") != result_id:
        errors.append("artifact_execution_result_id_mismatch")
    if call.get("input_sha256") != result.get("input_sha256"):
        errors.append("artifact_execution_input_hash_mismatch")
    output_hash = _canonical_hash(receipt.get("execution_output_sha256"))
    if not output_hash or output_hash != _canonical_hash(
        result.get("output_sha256")
    ):
        errors.append("artifact_execution_output_hash_mismatch")
    if (
        str(receipt.get("status") or "").strip().lower() in _SUCCESS
        and str(result.get("status") or "").strip().lower() not in _SUCCESS
    ):
        errors.append("artifact_execution_result_not_passed")

    call_record = registry.lookup(call_id)
    result_record = registry.lookup_result(result_id)
    if call_record is None or result_record is None:
        errors.append("artifact_host_registry_record_missing")
    elif call_record != result_record:
        errors.append("artifact_host_registry_one_to_one_mismatch")
    else:
        record = call_record
        if record.get("host_registry_id") != registry.registry_id:
            errors.append("artifact_host_registry_record_registry_mismatch")
        if record.get("tool_name") != expected_tool_name:
            errors.append("artifact_host_registry_tool_mismatch")
        if record.get("producer_identity") != producer_identity:
            errors.append("artifact_host_registry_producer_mismatch")
        if record.get("sequence") != sequence:
            errors.append("artifact_host_registry_sequence_mismatch")
        if record.get("artifact_path") != expected_path:
            errors.append("artifact_host_registry_input_path_mismatch")
        if _canonical_hash(record.get("input_artifact_sha256")) != execution_input_hash:
            errors.append("artifact_host_registry_input_artifact_hash_mismatch")
        if record.get("input_sha256") != call.get("input_sha256"):
            errors.append("artifact_host_registry_input_hash_mismatch")
        if _canonical_hash(record.get("output_sha256")) != output_hash:
            errors.append("artifact_host_registry_output_hash_mismatch")
        if record.get("call_receipt") != dict(call):
            errors.append("artifact_host_registry_call_receipt_mismatch")
        if record.get("result_receipt") != dict(result):
            errors.append("artifact_host_registry_result_receipt_mismatch")
        if _json_hash(record.get("input_payload")) != record.get("input_sha256"):
            errors.append("artifact_host_registry_input_payload_mismatch")
        if _json_hash(record.get("output")) != record.get("output_sha256"):
            errors.append("artifact_host_registry_output_payload_mismatch")

        call_time = _parse_issued_at(call.get("issued_at"))
        result_time = _parse_issued_at(result.get("issued_at"))
        receipt_time = _parse_issued_at(receipt.get("issued_at"))
        if call_time is None or result_time is None or receipt_time is None:
            errors.append("artifact_execution_timestamp_invalid")
        elif not call_time <= result_time <= receipt_time:
            errors.append("artifact_execution_timestamp_order_invalid")
        if record.get("call_issued_at") != call.get("issued_at"):
            errors.append("artifact_host_registry_call_timestamp_mismatch")
        if record.get("result_issued_at") != result.get("issued_at"):
            errors.append("artifact_host_registry_result_timestamp_mismatch")
    return list(dict.fromkeys(errors))


def _validate_csharp_generation_prewrite_receipt(
    receipt: Mapping[str, Any],
    *,
    project_root: Path,
    artifact_path: Path,
    artifact_role: str,
    pair_id: str,
    consume: bool,
) -> List[str]:
    errors: List[str] = []
    registry, registry_errors = _registry_for_receipt(receipt)
    errors.extend(registry_errors)
    boundary = registry.producer_boundary if registry is not None else None
    if boundary is not None:
        errors.extend(
            boundary.validate_claim(
                receipt,
                claim_kind=ARTIFACT_GENERATION_PREWRITE_KIND,
                claim_id_field="receipt_id",
                consume=False,
            )
        )

    target, target_error = _canonical_project_target(artifact_path, project_root)
    if target_error:
        errors.append(target_error)
        target = None
    absent_hash = f"sha256:{_ABSENT_ARTIFACT_SHA256}"
    expected_path = str(target) if target is not None else ""
    expected_producer = (
        f"{ARTIFACT_STYLE_PRODUCER}:{ARTIFACT_GENERATION_PREWRITE_TOOL}"
    )
    expected_fields = {
        "schema_version": 1,
        "receipt_type": ARTIFACT_GENERATION_PREWRITE_KIND,
        "status": "passed",
        "project_root": str(project_root),
        "artifact_path": expected_path,
        "artifact_role": artifact_role,
        "pair_id": pair_id,
        "path_state": "absent",
        "absent_artifact_sha256": absent_hash,
        "tool_name": ARTIFACT_GENERATION_PREWRITE_TOOL,
        "producer_identity": expected_producer,
    }
    for key, expected in expected_fields.items():
        if receipt.get(key) != expected:
            errors.append(f"generation_prewrite_{key}_mismatch")

    errors.extend(
        _validate_execution_correlation(
            receipt,
            registry=registry,
            expected_tool_name=ARTIFACT_GENERATION_PREWRITE_TOOL,
            expected_artifact_path=target,
            expected_artifact_sha256=absent_hash,
        )
    )

    call_id = str(receipt.get("call_id") or "")
    record = registry.lookup(call_id) if registry is not None else None
    if record is not None:
        expected_input = {
            "project_root": str(project_root),
            "artifact_path": expected_path,
            "artifact_role": artifact_role,
            "pair_id": pair_id,
            "expected_path_state": "absent",
        }
        if record.get("input_payload") != expected_input:
            errors.append("generation_prewrite_registry_input_mismatch")
        output = record.get("output")
        if not isinstance(output, Mapping):
            errors.append("generation_prewrite_registry_output_missing")
            output = {}
        expected_output = {
            "status": "passed",
            "success": True,
            "exit_code": 0,
            "artifact_path": expected_path,
            "artifact_sha256": absent_hash,
            "artifact_role": artifact_role,
            "pair_id": pair_id,
            "path_state": "absent",
        }
        for key, expected in expected_output.items():
            if output.get(key) != expected:
                errors.append(f"generation_prewrite_output_{key}_mismatch")
        if receipt.get("observed_at") != output.get("observed_at"):
            errors.append("generation_prewrite_observed_at_mismatch")
        call_time = _parse_issued_at(record.get("call_issued_at"))
        observed_time = _parse_issued_at(output.get("observed_at"))
        result_time = _parse_issued_at(record.get("result_issued_at"))
        receipt_time = _parse_issued_at(receipt.get("issued_at"))
        if None in {call_time, observed_time, result_time, receipt_time}:
            errors.append("generation_prewrite_timestamp_invalid")
        elif not call_time <= observed_time <= result_time <= receipt_time:
            errors.append("generation_prewrite_timestamp_order_invalid")

    errors = list(dict.fromkeys(errors))
    if not errors and consume and boundary is not None:
        errors.extend(
            boundary.validate_claim(
                receipt,
                claim_kind=ARTIFACT_GENERATION_PREWRITE_KIND,
                claim_id_field="receipt_id",
                consume=True,
            )
        )
    return list(dict.fromkeys(errors))


def _validate_csharp_modification_preedit_receipt(
    receipt: Mapping[str, Any],
    *,
    project_root: Path,
    artifact_path: Path,
    artifact_role: str,
    pair_id: str,
    consume: bool,
) -> List[str]:
    errors: List[str] = []
    registry, registry_errors = _registry_for_receipt(receipt)
    errors.extend(registry_errors)
    boundary = registry.producer_boundary if registry is not None else None
    if boundary is not None:
        errors.extend(
            boundary.validate_claim(
                receipt,
                claim_kind=ARTIFACT_MODIFICATION_PREEDIT_KIND,
                claim_id_field="receipt_id",
                consume=False,
            )
        )

    target, target_error = _canonical_project_file(artifact_path, project_root)
    if target_error:
        errors.append(target_error)
        target = None
    snapshot, snapshot_error = _canonical_project_file(
        receipt.get("snapshot_path"),
        project_root,
    )
    if snapshot_error:
        errors.append(f"modification_preedit_snapshot_{snapshot_error}")
        snapshot = None
    original_hash = _canonical_hash(
        receipt.get("original_artifact_sha256")
    )
    snapshot_hash = _canonical_hash(receipt.get("snapshot_sha256"))
    if not original_hash:
        errors.append("modification_preedit_original_hash_missing")
    if snapshot_hash != original_hash:
        errors.append("modification_preedit_snapshot_hash_mismatch")
    if snapshot is not None and sha256_bytes(snapshot.read_bytes()) != original_hash:
        errors.append("modification_preedit_snapshot_bytes_mismatch")

    expected_path = str(target) if target is not None else ""
    expected_snapshot = str(snapshot) if snapshot is not None else ""
    expected_producer = (
        f"{ARTIFACT_STYLE_PRODUCER}:{ARTIFACT_MODIFICATION_PREEDIT_TOOL}"
    )
    expected_fields = {
        "schema_version": 1,
        "receipt_type": ARTIFACT_MODIFICATION_PREEDIT_KIND,
        "status": "passed",
        "project_root": str(project_root),
        "artifact_path": expected_path,
        "artifact_role": artifact_role,
        "pair_id": pair_id,
        "snapshot_path": expected_snapshot,
        "snapshot_sha256": original_hash,
        "tool_name": ARTIFACT_MODIFICATION_PREEDIT_TOOL,
        "producer_identity": expected_producer,
        "execution_input_artifact_sha256": original_hash,
    }
    for key, expected in expected_fields.items():
        if receipt.get(key) != expected:
            errors.append(f"modification_preedit_{key}_mismatch")

    errors.extend(
        _validate_execution_correlation(
            receipt,
            registry=registry,
            expected_tool_name=ARTIFACT_MODIFICATION_PREEDIT_TOOL,
            expected_artifact_path=target,
            expected_artifact_sha256=original_hash,
        )
    )

    call_id = str(receipt.get("call_id") or "")
    record = registry.lookup(call_id) if registry is not None else None
    if record is not None:
        expected_input = {
            "project_root": str(project_root),
            "artifact_path": expected_path,
            "artifact_role": artifact_role,
            "pair_id": pair_id,
            "original_artifact_sha256": original_hash,
            "snapshot_path": expected_snapshot,
        }
        if record.get("input_payload") != expected_input:
            errors.append("modification_preedit_registry_input_mismatch")
        output = record.get("output")
        if not isinstance(output, Mapping):
            errors.append("modification_preedit_registry_output_missing")
            output = {}
        expected_output = {
            "status": "passed",
            "success": True,
            "exit_code": 0,
            "artifact_path": expected_path,
            "artifact_sha256": original_hash,
            "artifact_role": artifact_role,
            "pair_id": pair_id,
            "snapshot_path": expected_snapshot,
            "snapshot_sha256": original_hash,
        }
        for key, expected in expected_output.items():
            if output.get(key) != expected:
                errors.append(f"modification_preedit_output_{key}_mismatch")
        if receipt.get("captured_at") != output.get("captured_at"):
            errors.append("modification_preedit_captured_at_mismatch")
        call_time = _parse_issued_at(record.get("call_issued_at"))
        captured_time = _parse_issued_at(output.get("captured_at"))
        result_time = _parse_issued_at(record.get("result_issued_at"))
        receipt_time = _parse_issued_at(receipt.get("issued_at"))
        if None in {call_time, captured_time, result_time, receipt_time}:
            errors.append("modification_preedit_timestamp_invalid")
        elif not call_time <= captured_time <= result_time <= receipt_time:
            errors.append("modification_preedit_timestamp_order_invalid")

    errors = list(dict.fromkeys(errors))
    if not errors and consume and boundary is not None:
        errors.extend(
            boundary.validate_claim(
                receipt,
                claim_kind=ARTIFACT_MODIFICATION_PREEDIT_KIND,
                claim_id_field="receipt_id",
                consume=True,
            )
        )
    return list(dict.fromkeys(errors))


def _consume_csharp_operation_receipts(
    receipts: Sequence[Mapping[str, Any]],
    *,
    project_root: Path,
) -> List[str]:
    errors: List[str] = []
    for item in receipts:
        kind = str(item.get("kind") or "")
        receipt = item.get("receipt")
        path = item.get("path")
        if not isinstance(receipt, Mapping) or not isinstance(path, Path):
            errors.append("csharp_operation_receipt_binding_invalid")
            continue
        kwargs = {
            "project_root": project_root,
            "artifact_path": path,
            "artifact_role": str(item.get("artifact_role") or ""),
            "pair_id": str(item.get("pair_id") or ""),
            "consume": True,
        }
        if kind == "generation":
            receipt_errors = _validate_csharp_generation_prewrite_receipt(
                receipt,
                **kwargs,
            )
        elif kind == "modification":
            receipt_errors = _validate_csharp_modification_preedit_receipt(
                receipt,
                **kwargs,
            )
        else:
            receipt_errors = ["csharp_operation_receipt_kind_invalid"]
        errors.extend(
            f"csharp_{kind}_receipt_consume_failed:{path}:{error}"
            for error in receipt_errors
        )
    return list(dict.fromkeys(errors))


def _validate_verifier_receipt(
    receipt: Mapping[str, Any],
    project_root: Path,
) -> tuple[Dict[str, Any] | None, List[str]]:
    registry, errors = _registry_for_receipt(receipt)
    if registry is not None:
        errors.extend(
            registry.producer_boundary.validate_claim(
                receipt,
                claim_kind=ARTIFACT_STYLE_RECEIPT_KIND,
                claim_id_field="receipt_id",
                consume=False,
            )
        )
    gate = str(receipt.get("gate") or "").strip()
    role = str(receipt.get("artifact_role") or "").strip()
    if gate not in {
        CSHARP_STYLE_SKILL,
        SQL_FORMATTING_SKILL,
        SQL_STYLE_SKILL,
    }:
        errors.append("artifact_style_receipt_gate_invalid")
    if role not in _ARTIFACT_ROLES or gate not in _gate_for_role(role):
        errors.append("artifact_style_receipt_role_gate_mismatch")
    path, path_error = _canonical_project_file(
        receipt.get("artifact_path"),
        project_root,
    )
    if path_error:
        errors.append(path_error)
    actual_hash = sha256_bytes(path.read_bytes()) if path is not None else ""
    if _canonical_hash(receipt.get("artifact_sha256")) != actual_hash:
        errors.append("artifact_style_receipt_current_hash_mismatch")
    if str(receipt.get("status") or "").strip().lower() not in (
        _SUCCESS | _FAILURE
    ):
        errors.append("artifact_style_receipt_status_invalid")
    expected_tool = _STYLE_TOOL_BY_GATE.get(gate, "")
    errors.extend(
        _validate_execution_correlation(
            receipt,
            registry=registry,
            expected_tool_name=expected_tool,
            expected_artifact_path=path,
            expected_artifact_sha256=actual_hash,
        )
    )
    if _canonical_hash(receipt.get("verifier_result_sha256")) != (
        _canonical_hash(receipt.get("execution_output_sha256"))
    ):
        errors.append("artifact_style_receipt_result_hash_mismatch")
    if gate == SQL_FORMATTING_SKILL:
        formatted_hash = _canonical_hash(
            receipt.get("formatted_output_sha256")
        )
        if formatted_hash != actual_hash:
            errors.append("sql_formatter_output_current_hash_mismatch")
        formatter_history = receipt.get("formatter_history")
        if not isinstance(formatter_history, list) or not formatter_history or any(
            not isinstance(item, Mapping) for item in formatter_history
        ):
            errors.append("sql_formatter_execution_history_missing")
        elif _json_hash(formatter_history) != receipt.get(
            "formatter_history_sha256"
        ):
            errors.append("sql_formatter_execution_history_hash_mismatch")
        else:
            last_formatter = formatter_history[-1]
            if _canonical_hash(last_formatter.get("formatted_sha256")) != actual_hash:
                errors.append("sql_formatter_execution_history_output_mismatch")
        history = receipt.get("verifier_history")
        if not isinstance(history, list) or not history or any(
            not isinstance(item, Mapping) for item in history
        ):
            errors.append("sql_formatter_verifier_history_missing")
        elif _json_hash(history) != receipt.get("verifier_history_sha256"):
            errors.append("sql_formatter_verifier_history_hash_mismatch")
        else:
            metadata = history[-1].get("metadata", {})
            formatted = (
                metadata.get("formatted_sha256")
                if isinstance(metadata, Mapping)
                else ""
            )
            if _canonical_hash(formatted) != actual_hash:
                errors.append("sql_formatter_verifier_history_candidate_mismatch")
    return (
        dict(receipt) if not errors else None,
        list(dict.fromkeys(errors)),
    )


def _validate_visual_receipt(
    receipt: Mapping[str, Any],
    project_root: Path,
) -> tuple[Dict[str, Any] | None, List[str]]:
    registry, errors = _registry_for_receipt(receipt)
    if registry is not None:
        errors.extend(
            registry.producer_boundary.validate_claim(
                receipt,
                claim_kind=ARTIFACT_VISUAL_RECEIPT_KIND,
                claim_id_field="receipt_id",
                consume=False,
            )
        )
    path, path_error = _canonical_project_file(
        receipt.get("visual_artifact_path"),
        project_root,
    )
    if path_error:
        errors.append(path_error)
    actual_hash = sha256_bytes(path.read_bytes()) if path is not None else ""
    if _canonical_hash(receipt.get("visual_artifact_sha256")) != actual_hash:
        errors.append("visual_receipt_current_hash_mismatch")
    if (
        str(receipt.get("qa_provider") or "").strip().lower()
        not in _VISUAL_PROVIDERS
    ):
        errors.append("visual_receipt_provider_invalid")
    provider = str(receipt.get("qa_provider") or "").strip().lower()
    errors.extend(
        _validate_execution_correlation(
            receipt,
            registry=registry,
            expected_tool_name=f"artifact-render-qa:{provider}",
            expected_artifact_path=path,
            expected_artifact_sha256=actual_hash,
        )
    )
    host_result = receipt.get("host_result")
    if not isinstance(host_result, Mapping):
        errors.append("visual_receipt_host_result_missing")
        host_result = {}
    elif _json_hash(host_result) != _canonical_hash(
        receipt.get("execution_output_sha256")
    ):
        errors.append("visual_receipt_host_result_hash_mismatch")
    if str(host_result.get("artifact_path") or "") != (
        str(path) if path is not None else ""
    ):
        errors.append("visual_receipt_host_result_path_mismatch")
    if _canonical_hash(host_result.get("artifact_sha256")) != actual_hash:
        errors.append("visual_receipt_host_result_hash_mismatch")
    if str(host_result.get("provider") or "").strip().lower() != provider:
        errors.append("visual_receipt_host_result_provider_mismatch")

    structure_result: Dict[str, Any] = {}
    if path is not None:
        from src.orchestration.quality_harnesses import (
            evaluate_deliverable_quality,
        )

        structure_result = evaluate_deliverable_quality(
            {
                "deliverables": [
                    {
                        "path": str(path),
                        "file_name": path.name,
                        "format": path.suffix.lower().lstrip("."),
                        "artifact_type": "visual-evidence",
                        "template_not_applicable": True,
                    }
                ]
            }
        )
        if structure_result.get("status") != "passed":
            errors.append("visual_receipt_structure_qa_failed")
        if _json_hash(structure_result) != receipt.get(
            "structure_qa_sha256"
        ):
            errors.append("visual_receipt_structure_qa_mismatch")
    if str(receipt.get("status") or "").strip().lower() not in _SUCCESS:
        errors.append("visual_receipt_not_passed")
    return (
        dict(receipt) if not errors else None,
        list(dict.fromkeys(errors)),
    )


def _analyze(
    context: Mapping[str, Any] | None,
    *,
    project_root: Path,
    boundary: RuntimeProducerBoundary,
    artifacts: Sequence[Mapping[str, Any]] | None = None,
    artifact_errors: Sequence[str] = (),
) -> Dict[str, Any]:
    contexts = _contexts(context)
    if artifacts is None:
        artifacts, collected_errors = _artifact_candidates(
            context,
            project_root,
        )
        artifact_errors = [*artifact_errors, *collected_errors]
    artifacts = [dict(item) for item in artifacts]
    csharp_artifacts = [
        row
        for row in artifacts
        if row.get("artifact_role")
        in {"winforms_codebehind", "winforms_designer"}
    ]
    sql_artifacts = [
        row
        for row in artifacts
        if row.get("artifact_role") == "sql_candidate"
    ]
    db_deployment = _db_deployment_evidence(contexts)
    csharp_required = bool(csharp_artifacts)
    sql_required = bool(sql_artifacts or db_deployment)
    visual_required = bool(
        csharp_required and _visual_completion_claimed(contexts)
    )
    required: List[str] = []
    if csharp_required:
        required.append(CSHARP_STYLE_SKILL)
    if sql_required:
        required.extend([SQL_FORMATTING_SKILL, SQL_STYLE_SKILL])
    if visual_required:
        required.append(VISUAL_STYLE_SKILL)

    valid_receipts: List[Dict[str, Any]] = []
    receipt_errors: List[str] = []
    seen_ids: set[str] = set()
    seen_bindings: set[tuple[str, str]] = set()
    seen_call_ids: set[str] = set()
    seen_result_ids: set[str] = set()
    seen_sequences: set[int] = set()
    seen_registry_ids: set[str] = set()
    previous_sequence = 0
    for raw in _receipt_rows(contexts):
        receipt, errors = _validate_verifier_receipt(
            raw,
            project_root,
        )
        receipt_id = str(raw.get("receipt_id") or "")
        binding = (
            str(raw.get("gate") or ""),
            _path_key(Path(str(raw.get("artifact_path") or "."))),
        )
        if receipt_id in seen_ids or binding in seen_bindings:
            errors.append("artifact_style_receipt_duplicate_or_replay")
        call_id = str(raw.get("call_id") or "").strip()
        result_id = str(raw.get("result_id") or "").strip()
        sequence = raw.get("sequence")
        registry_id = str(raw.get("host_registry_id") or "").strip()
        if call_id in seen_call_ids or result_id in seen_result_ids:
            errors.append("artifact_style_execution_duplicate_or_replay")
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence in seen_sequences
            or sequence <= previous_sequence
        ):
            errors.append("artifact_style_execution_sequence_not_monotonic")
        seen_ids.add(receipt_id)
        seen_bindings.add(binding)
        if call_id:
            seen_call_ids.add(call_id)
        if result_id:
            seen_result_ids.add(result_id)
        if isinstance(sequence, int) and not isinstance(sequence, bool):
            seen_sequences.add(sequence)
            previous_sequence = max(previous_sequence, sequence)
        if registry_id:
            seen_registry_ids.add(registry_id)
        if errors:
            receipt_errors.extend(errors)
        elif receipt is not None:
            valid_receipts.append(receipt)

    missing_receipts: List[str] = []
    blocked_receipts: List[str] = []
    stale_receipts = [
        item
        for item in artifact_errors
        if item.startswith("artifact_hash_mismatch:")
    ]
    for artifact in artifacts:
        for gate in _gate_for_role(
            str(artifact.get("artifact_role") or "")
        ):
            matches = [
                item
                for item in valid_receipts
                if item.get("gate") == gate
                and _path_key(Path(str(item.get("artifact_path"))))
                == _path_key(Path(str(artifact.get("path"))))
                and _canonical_hash(item.get("artifact_sha256"))
                == artifact.get("sha256")
            ]
            if not matches:
                missing_receipts.append(f"{gate}:{artifact['path']}")
            elif any(
                str(item.get("status") or "").lower() in _FAILURE
                for item in matches
            ):
                blocked_receipts.append(f"{gate}:{artifact['path']}")

    valid_visual: List[Dict[str, Any]] = []
    visual_errors: List[str] = []
    visual_ids: set[str] = set()
    for raw in _receipt_rows(contexts, _VISUAL_RECEIPT_KEYS):
        receipt, errors = _validate_visual_receipt(
            raw,
            project_root,
        )
        receipt_id = str(raw.get("receipt_id") or "")
        call_id = str(raw.get("call_id") or "").strip()
        result_id = str(raw.get("result_id") or "").strip()
        sequence = raw.get("sequence")
        registry_id = str(raw.get("host_registry_id") or "").strip()
        if (
            receipt_id in visual_ids
            or receipt_id in seen_ids
            or call_id in seen_call_ids
            or result_id in seen_result_ids
        ):
            errors.append("visual_receipt_duplicate_or_replay")
        if (
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence in seen_sequences
            or sequence <= previous_sequence
        ):
            errors.append("artifact_execution_sequence_not_monotonic")
        visual_ids.add(receipt_id)
        if call_id:
            seen_call_ids.add(call_id)
        if result_id:
            seen_result_ids.add(result_id)
        if isinstance(sequence, int) and not isinstance(sequence, bool):
            seen_sequences.add(sequence)
            previous_sequence = max(previous_sequence, sequence)
        if registry_id:
            seen_registry_ids.add(registry_id)
        if errors:
            visual_errors.extend(errors)
        elif receipt is not None:
            valid_visual.append(receipt)
    if len(seen_registry_ids) > 1:
        receipt_errors.append("artifact_host_registry_mixed_execution")
    visual_passed = not visual_required or bool(
        valid_visual and not visual_errors
    )
    exact_receipts = bool(artifacts) and not (
        missing_receipts
        or stale_receipts
        or receipt_errors
        or artifact_errors
    )
    csharp_passed = not csharp_required or not any(
        item.startswith(f"{CSHARP_STYLE_SKILL}:")
        for item in missing_receipts + blocked_receipts
    )
    sql_formatting_passed = not sql_required or (
        bool(sql_artifacts)
        and not any(
            item.startswith(f"{SQL_FORMATTING_SKILL}:")
            for item in missing_receipts + blocked_receipts
        )
    )
    sql_style_passed = not sql_required or (
        bool(sql_artifacts)
        and not any(
            item.startswith(f"{SQL_STYLE_SKILL}:")
            for item in missing_receipts + blocked_receipts
        )
    )
    style_passed = bool(
        not artifact_errors
        and not receipt_errors
        and not blocked_receipts
        and exact_receipts
        and csharp_passed
        and sql_formatting_passed
        and sql_style_passed
        and visual_passed
        and not visual_errors
    )
    completion_claimed = _completion_claimed(contexts)
    return {
        "project_root": str(project_root),
        "changed_artifacts": artifacts,
        "csharp_artifacts": csharp_artifacts,
        "sql_artifacts": sql_artifacts,
        "csharp_required": csharp_required,
        "sql_required": sql_required,
        "db_deployment_evidence": db_deployment,
        "host_registry_id": (
            next(iter(seen_registry_ids))
            if len(seen_registry_ids) == 1
            else ""
        ),
        "exact_receipts": exact_receipts,
        "artifact_errors": list(dict.fromkeys(artifact_errors)),
        "receipt_errors": list(dict.fromkeys(receipt_errors)),
        "visual_receipt_errors": list(dict.fromkeys(visual_errors)),
        "missing_receipts": list(dict.fromkeys(missing_receipts)),
        "stale_receipts": list(dict.fromkeys(stale_receipts)),
        "blocked_receipts": list(dict.fromkeys(blocked_receipts)),
        "style_receipts": valid_receipts,
        "visual_qa_receipts": valid_visual,
        "style_receipt_status": {
            "csharp": (
                "passed"
                if csharp_required and csharp_passed and exact_receipts
                else ("blocked" if csharp_required else "not_applicable")
            ),
            "sql_formatting": (
                "passed"
                if sql_required and sql_formatting_passed and exact_receipts
                else ("blocked" if sql_required else "not_applicable")
            ),
            "sql_style": (
                "passed"
                if sql_required and sql_style_passed and exact_receipts
                else ("blocked" if sql_required else "not_applicable")
            ),
            "visual": (
                "passed"
                if visual_required and visual_passed
                else ("blocked" if visual_required else "not_applicable")
            ),
        },
        "required_skills": required,
        "completion_claimed": completion_claimed,
        "deployment_claimed": db_deployment
        or any(_claim_is_true(row.get("deployment")) for row in contexts),
        "visual_required": visual_required,
        "visual_passed": visual_passed,
        "style_passed": style_passed,
        "completion_blocked": bool(
            (completion_claimed or db_deployment) and not style_passed
        ),
    }


def analyze_artifact_style_context(
    context: Mapping[str, Any] | None,
    *,
    project_root: str | os.PathLike[str] | None = None,
    producer_boundary: RuntimeProducerBoundary | None = None,
) -> Dict[str, Any]:
    root, root_error = _project_root(context, project_root)
    if root is None:
        completion = _completion_claimed(_contexts(context))
        return {
            "project_root": "",
            "changed_artifacts": [],
            "csharp_artifacts": [],
            "sql_artifacts": [],
            "csharp_required": False,
            "sql_required": False,
            "db_deployment_evidence": False,
            "exact_receipts": False,
            "artifact_errors": [root_error],
            "receipt_errors": [],
            "visual_receipt_errors": [],
            "missing_receipts": [],
            "stale_receipts": [],
            "blocked_receipts": [],
            "style_receipts": [],
            "visual_qa_receipts": [],
            "style_receipt_status": {
                "csharp": "not_applicable",
                "sql_formatting": "not_applicable",
                "sql_style": "not_applicable",
                "visual": "not_applicable",
            },
            "required_skills": [],
            "completion_claimed": completion,
            "deployment_claimed": False,
            "visual_required": False,
            "visual_passed": False,
            "style_passed": False,
            "completion_blocked": completion,
        }
    return _analyze(
        context,
        project_root=root,
        boundary=producer_boundary or _runtime_boundary(root),
    )


def issue_visual_qa_receipt(
    *,
    project_root: str | os.PathLike[str],
    visual_artifact_path: str | os.PathLike[str],
    qa_provider: str,
    runtime_registry_id: str = "",
    host_registry: HostCallResultRegistry | None = None,
    qa_runner: Callable[[Dict[str, Any]], Any],
    producer_boundary: RuntimeProducerBoundary | None = None,
) -> Dict[str, Any]:
    root, error = _canonical_project_root(project_root)
    if root is None:
        raise ValueError(error)
    visual, error = _canonical_project_file(
        visual_artifact_path,
        root,
    )
    if visual is None:
        raise ValueError(error)
    provider = str(qa_provider or "").strip().lower()
    if provider not in _VISUAL_PROVIDERS:
        raise ValueError(
            "visual QA requires an allowlisted provider"
        )
    registry_id = runtime_registry_id or (
        host_registry.registry_id
        if isinstance(host_registry, HostCallResultRegistry)
        else ""
    )
    registry = _registered_host_registry(registry_id)
    if registry is None or (
        host_registry is not None and registry is not host_registry
    ):
        raise ValueError("visual QA requires an executor-owned host registry")
    boundary = registry.producer_boundary
    if producer_boundary is not None and (
        producer_boundary.boundary_id != boundary.boundary_id
        or producer_boundary.producer_name != boundary.producer_name
    ):
        raise ValueError("visual QA registry boundary mismatch")
    current_hash = sha256_bytes(visual.read_bytes())
    producer_identity = (
        f"{ARTIFACT_STYLE_PRODUCER}:artifact-render-qa:{provider}"
    )
    execution = registry.invoke(
        tool_name=f"artifact-render-qa:{provider}",
        producer_identity=producer_identity,
        artifact_path=str(visual),
        artifact_sha256=current_hash,
        input_payload={
            "project_root": str(root),
            "artifact_path": str(visual),
            "artifact_sha256": current_hash,
            "provider": provider,
        },
        runner=qa_runner,
    )
    host_result = dict(execution["output"])
    from src.orchestration.quality_harnesses import evaluate_deliverable_quality

    structure_result = evaluate_deliverable_quality(
        {
            "deliverables": [
                {
                    "path": str(visual),
                    "file_name": visual.name,
                    "format": visual.suffix.lower().lstrip("."),
                    "artifact_type": "visual-evidence",
                    "template_not_applicable": True,
                }
            ]
        }
    )
    host_binding_passed = (
        str(host_result.get("status") or "").strip().lower() in _SUCCESS
        and str(host_result.get("provider") or "").strip().lower()
        == provider
        and str(host_result.get("artifact_path") or "") == str(visual)
        and _canonical_hash(host_result.get("artifact_sha256"))
        == current_hash
    )
    status = (
        "passed"
        if host_binding_passed
        and structure_result.get("status") == "passed"
        and str(execution["result_receipt"].get("status") or "")
        in _SUCCESS
        else "blocked"
    )
    call_receipt = execution["call_receipt"]
    result_receipt = execution["result_receipt"]
    return boundary.issue_claim(
        {
            "schema_version": 1,
            "receipt_type": ARTIFACT_VISUAL_RECEIPT_KIND,
            "host_registry_id": registry.registry_id,
            "status": status,
            "project_root": str(root),
            "visual_artifact_path": str(visual),
            "visual_artifact_sha256": current_hash,
            "qa_provider": provider,
            "tool_name": f"artifact-render-qa:{provider}",
            "producer_identity": producer_identity,
            "sequence": int(call_receipt["sequence"]),
            "call_id": str(call_receipt["call_id"]),
            "result_id": str(result_receipt["result_id"]),
            "execution_output_sha256": str(
                result_receipt["output_sha256"]
            ),
            "execution_input_artifact_sha256": str(
                call_receipt["artifact_sha256"]
            ),
            "execution_call_receipt": dict(call_receipt),
            "execution_result_receipt": dict(result_receipt),
            "host_result": host_result,
            "structure_qa_sha256": _json_hash(structure_result),
            "issued_at": datetime.now(timezone.utc).isoformat(),
        },
        claim_kind=ARTIFACT_VISUAL_RECEIPT_KIND,
        claim_id_field="receipt_id",
        claim_id_prefix="artifact-visual",
    )


def _issue_style_receipt(
    *,
    boundary: RuntimeProducerBoundary,
    project_root: Path,
    artifact: Mapping[str, Any],
    gate: str,
    status: str,
    result: Mapping[str, Any],
    execution: Mapping[str, Any],
    extra: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    call_receipt = execution.get("call_receipt")
    result_receipt = execution.get("result_receipt")
    if not isinstance(call_receipt, Mapping) or not isinstance(
        result_receipt, Mapping
    ):
        raise ValueError("style receipt requires a correlated execution")
    payload = {
        "schema_version": 1,
        "receipt_type": ARTIFACT_STYLE_RECEIPT_KIND,
        "host_registry_id": str(call_receipt.get("host_registry_id") or ""),
        "status": status,
        "project_root": str(project_root),
        "gate": gate,
        "artifact_path": str(artifact["path"]),
        "artifact_sha256": str(artifact["sha256"]),
        "artifact_role": str(artifact["artifact_role"]),
        "pair_id": str(artifact.get("pair_id") or ""),
        "tool_name": str(call_receipt.get("tool_name") or ""),
        "producer_identity": str(
            call_receipt.get("producer_identity") or ""
        ),
        "sequence": int(call_receipt["sequence"]),
        "call_id": str(call_receipt["call_id"]),
        "result_id": str(result_receipt["result_id"]),
        "execution_output_sha256": str(
            result_receipt["output_sha256"]
        ),
        "execution_input_artifact_sha256": str(
            call_receipt["artifact_sha256"]
        ),
        "execution_call_receipt": dict(call_receipt),
        "execution_result_receipt": dict(result_receipt),
        "verifier_result_sha256": _json_hash(result),
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    if artifact.get("generation_prewrite_receipt_id"):
        payload["generation_prewrite_receipt_id"] = str(
            artifact["generation_prewrite_receipt_id"]
        )
        payload["generation_prewrite_host_registry_id"] = str(
            artifact.get("generation_prewrite_host_registry_id") or ""
        )
        payload["generation_prewrite_sequence"] = artifact.get(
            "generation_prewrite_sequence"
        )
    if artifact.get("modification_preedit_receipt_id"):
        payload["modification_preedit_receipt_id"] = str(
            artifact["modification_preedit_receipt_id"]
        )
        payload["modification_preedit_host_registry_id"] = str(
            artifact.get("modification_preedit_host_registry_id") or ""
        )
        payload["modification_preedit_sequence"] = artifact.get(
            "modification_preedit_sequence"
        )
    payload.update(dict(extra or {}))
    return boundary.issue_claim(
        payload,
        claim_kind=ARTIFACT_STYLE_RECEIPT_KIND,
        claim_id_field="receipt_id",
        claim_id_prefix="artifact-style",
    )


def _mask_csharp_noncode(value: str) -> str:
    result = list(str(value or ""))
    pattern = re.compile(
        r'//[^\r\n]*|/\*.*?\*/|\$?@"(?:""|[^"])*"|\$?"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
        re.DOTALL,
    )
    for match in pattern.finditer(str(value or "")):
        for index in range(match.start(), match.end()):
            if result[index] not in "\r\n":
                result[index] = " "
    return "".join(result)


def _designer_field_inventory(source: str) -> Dict[str, str]:
    code = _mask_csharp_noncode(source)
    pattern = re.compile(
        r"(?m)^\s*(?:(?:private|protected|internal|public|static|readonly)\s+)+"
        r"(?P<type>[A-Za-z_][A-Za-z0-9_.<>,\[\]?]*)\s+"
        r"@?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*[^;]*)?;"
    )
    return {
        match.group("name"): match.group("type")
        for match in pattern.finditer(code)
    }


def _designer_assignment_inventory(
    source: str,
    fields: Mapping[str, str],
) -> set[tuple[str, str]]:
    code = _mask_csharp_noncode(source)
    assignments: set[tuple[str, str]] = set()
    nested = re.compile(
        r"\b(?:this\.)?(?P<member>[A-Za-z_][A-Za-z0-9_]*)\."
        r"(?P<property>[A-Za-z_][A-Za-z0-9_.]*)\s*="
    )
    for match in nested.finditer(code):
        member = match.group("member")
        if member in fields:
            assignments.add((member, match.group("property")))
    direct = re.compile(
        r"\bthis\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)\s*="
    )
    for match in direct.finditer(code):
        member = match.group("member")
        assignments.add(
            (member, "$instance" if member in fields else "$form_property")
        )
    return assignments


def _verify_csharp_designer_modification_contract(
    original_source: str,
    candidate_source: str,
) -> Dict[str, Any]:
    original_fields = _designer_field_inventory(original_source)
    candidate_fields = _designer_field_inventory(candidate_source)
    original_assignments = _designer_assignment_inventory(
        original_source,
        original_fields,
    )
    candidate_assignments = _designer_assignment_inventory(
        candidate_source,
        candidate_fields,
    )
    issues: List[Dict[str, Any]] = []
    for name, type_name in sorted(original_fields.items()):
        if name not in candidate_fields:
            issues.append(
                {
                    "code": "designer_control_removed",
                    "identity": name,
                    "original_type": type_name,
                }
            )
        elif candidate_fields[name] != type_name:
            issues.append(
                {
                    "code": "designer_control_type_changed",
                    "identity": name,
                    "original_type": type_name,
                    "candidate_type": candidate_fields[name],
                }
            )
    for member, property_name in sorted(
        original_assignments - candidate_assignments
    ):
        issues.append(
            {
                "code": "designer_property_removed",
                "identity": member,
                "property": property_name,
            }
        )
    original_hash = sha256_bytes(original_source.encode("utf-8"))
    candidate_hash = sha256_bytes(candidate_source.encode("utf-8"))
    return {
        "status": "blocked" if issues else "passed",
        "success": not issues,
        "exit_code": 1 if issues else 0,
        "metadata": {
            "operation": "designer_modification_guard",
            "status": "blocked" if issues else "passed",
            "original_sha256": original_hash,
            "candidate_sha256": candidate_hash,
            "issues": issues,
            "checked_rules": [
                "preserve_existing_designer_controls",
                "preserve_existing_designer_control_types",
                "preserve_existing_designer_property_assignments",
            ],
        },
    }


def _validated_selected_sql_provider(
    value: Mapping[str, Any] | None,
) -> tuple[Dict[str, Any] | None, str]:
    if not isinstance(value, Mapping):
        return None, "sql_selected_provider_missing"
    provider = dict(value)
    provider_id = str(provider.get("provider_id") or "").strip()
    metadata = _as_mapping(provider.get("metadata"))
    capabilities = {
        str(item).strip().lower()
        for item in provider.get("capabilities", []) or []
    }
    capability = str(provider.get("capability") or "").strip().lower()
    compatibility = str(
        metadata.get("compatibility") or "compatible"
    ).strip().lower()
    status = str(provider.get("status") or "available").strip().lower()
    provider_path = Path(str(metadata.get("path") or "").strip())
    if not provider_id:
        return None, "sql_selected_provider_id_missing"
    if capability != "sql_formatting" and "sql_formatting" not in capabilities:
        return None, "sql_selected_provider_capability_mismatch"
    if compatibility not in {"compatible", "supported", "verified"}:
        return None, "sql_selected_provider_incompatible"
    if status not in {"available", "selected"}:
        return None, "sql_selected_provider_unavailable"
    if not provider_path.is_absolute() or not provider_path.is_file():
        return None, "sql_selected_provider_path_unavailable"
    provider["metadata"] = metadata
    return provider, ""


def run_packaged_sql_formatting_provider(
    request: Mapping[str, Any],
) -> Dict[str, Any]:
    """Run the packaged deterministic format-only preparation on one file."""

    from src.skills.sql_formatting_style import normalize_sql_join_layout

    provider_id = str(request.get("provider_id") or "").strip()
    candidate_path = Path(str(request.get("candidate_path") or "")).resolve()
    expected_hash = _canonical_hash(request.get("candidate_sha256"))
    candidate_text = request.get("candidate_text")
    try:
        source_bytes = candidate_path.read_bytes()
        source_hash = sha256_bytes(source_bytes)
        decoded = source_bytes.decode("utf-8-sig", errors="strict")
        if (
            not provider_id
            or not expected_hash
            or source_hash != expected_hash
            or not isinstance(candidate_text, str)
            or candidate_text != decoded
        ):
            raise ValueError("packaged formatter input binding mismatch")
        formatted = normalize_sql_join_layout(decoded)
        bom = b"\xef\xbb\xbf" if source_bytes.startswith(b"\xef\xbb\xbf") else b""
        formatted_bytes = bom + formatted.encode("utf-8")
        candidate_path.write_bytes(formatted_bytes)
        formatted_hash = sha256_bytes(formatted_bytes)
        history = [
            {
                "engine": (
                    "src.skills.sql_formatting_style."
                    "normalize_sql_join_layout"
                ),
                "operation": "formatting",
                "input_sha256": source_hash,
                "formatted_sha256": formatted_hash,
                "changed": formatted_bytes != source_bytes,
            }
        ]
        return {
            "status": "passed",
            "success": True,
            "exit_code": 0,
            "provider_id": provider_id,
            "execution_actor": "packaged-python-format-only",
            "artifact_path": str(candidate_path),
            "input_sha256": source_hash,
            "formatted_sha256": formatted_hash,
            "formatter_history": history,
            "formatter_history_sha256": _json_hash(history),
        }
    except (OSError, UnicodeError, ValueError) as exc:
        return {
            "status": "blocked",
            "success": False,
            "exit_code": 1,
            "provider_id": provider_id,
            "artifact_path": str(candidate_path),
            "error": type(exc).__name__,
            "message": str(exc),
        }


def execute_artifact_style_precompletion(
    context: Mapping[str, Any] | None,
    *,
    project_root: str | os.PathLike[str] | None = None,
    producer_boundary: RuntimeProducerBoundary | None = None,
    host_registry: HostCallResultRegistry | None = None,
    selected_sql_provider: Mapping[str, Any] | None = None,
    sql_formatter_runner: Callable[[Dict[str, Any]], Any] | None = None,
) -> Dict[str, Any]:
    """Run exact packaged verifiers and return authenticated runtime metadata."""

    root, root_error = _project_root(context, project_root)
    if root is None:
        gate = analyze_artifact_style_context(
            context,
            project_root=project_root,
            producer_boundary=producer_boundary,
        )
        gate["executor_status"] = "blocked"
        gate["executor_errors"] = [root_error]
        return gate
    # Caller boundaries and registries are compatibility inputs only. They never
    # own authoritative execution evidence; this executor creates and registers
    # the only registry accepted by later analyzers.
    _ = producer_boundary, host_registry
    registry = _new_executor_host_registry(root)
    boundary = registry.producer_boundary
    operation_receipts: List[Dict[str, Any]] = []
    artifacts, artifact_errors = _artifact_candidates(
        context,
        root,
        validated_operation_receipts=operation_receipts,
    )
    style_receipts: List[Dict[str, Any]] = []
    executor_errors = list(artifact_errors)

    pairs: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for artifact in artifacts:
        if artifact["artifact_role"] in {
            "winforms_codebehind",
            "winforms_designer",
        }:
            pairs.setdefault(
                str(artifact.get("pair_id") or ""),
                {},
            )[artifact["artifact_role"]] = artifact
    for pair_id, pair in pairs.items():
        if set(pair) != {
            "winforms_codebehind",
            "winforms_designer",
        }:
            continue
        from src.skills.csharp_designer_style_contract import (
            verify_csharp_designer_style,
        )
        from src.skills.csharp_designer_style import verify_csharp_edit_contract

        for artifact in pair.values():
            request = {
                "target_artifact_path": artifact["path"],
                "target_artifact_sha256": artifact["sha256"],
                "codebehind": {
                    "path": pair["winforms_codebehind"]["path"],
                    "sha256": pair["winforms_codebehind"]["sha256"],
                },
                "designer": {
                    "path": pair["winforms_designer"]["path"],
                    "sha256": pair["winforms_designer"]["sha256"],
                },
            }
            for role, request_key in (
                ("winforms_codebehind", "original_codebehind"),
                ("winforms_designer", "original_designer"),
            ):
                original_path = str(pair[role].get("original_path") or "")
                if original_path:
                    request[request_key] = {
                        "path": original_path,
                        "sha256": pair[role]["original_sha256"],
                    }
            edit_evidence = pair["winforms_codebehind"].get("edit_evidence")
            if isinstance(edit_evidence, Mapping):
                request["edit_evidence"] = dict(edit_evidence)

            def run_csharp_verifier(_request: Dict[str, Any]) -> Any:
                edit_result = None
                original_codebehind = _request.get("original_codebehind")
                if isinstance(original_codebehind, Mapping):
                    edit_result = verify_csharp_edit_contract(
                        Path(str(original_codebehind["path"])).read_text(
                            encoding="utf-8"
                        ),
                        Path(str(_request["codebehind"]["path"])).read_text(
                            encoding="utf-8"
                        ),
                        evidence=(
                            _request.get("edit_evidence")
                            if isinstance(_request.get("edit_evidence"), Mapping)
                            else None
                        ),
                        designer_source=Path(
                            str(_request["designer"]["path"])
                        ).read_text(encoding="utf-8"),
                    )
                    if not edit_result.success:
                        return edit_result
                designer_edit_result = None
                original_designer = _request.get("original_designer")
                if isinstance(original_designer, Mapping):
                    designer_edit_result = (
                        _verify_csharp_designer_modification_contract(
                            Path(str(original_designer["path"])).read_text(
                                encoding="utf-8"
                            ),
                            Path(str(_request["designer"]["path"])).read_text(
                                encoding="utf-8"
                            ),
                        )
                    )
                    if not _runtime_output_passed(designer_edit_result):
                        return designer_edit_result
                pair_result = verify_csharp_designer_style(
                    _request["codebehind"],
                    _request["designer"],
                )
                if edit_result is None and designer_edit_result is None:
                    return pair_result
                output = _runtime_output(pair_result)
                metadata = dict(output.get("metadata") or {})
                if edit_result is not None:
                    metadata["source_modification_contract"] = dict(
                        edit_result.metadata
                    )
                if designer_edit_result is not None:
                    metadata["designer_modification_contract"] = dict(
                        designer_edit_result.get("metadata") or {}
                    )
                output["metadata"] = metadata
                return output

            execution = registry.invoke(
                tool_name=_STYLE_TOOL_BY_GATE[CSHARP_STYLE_SKILL],
                producer_identity=(
                    f"{ARTIFACT_STYLE_PRODUCER}:"
                    f"{_STYLE_TOOL_BY_GATE[CSHARP_STYLE_SKILL]}"
                ),
                artifact_path=str(artifact["path"]),
                artifact_sha256=str(artifact["sha256"]),
                input_payload=request,
                runner=run_csharp_verifier,
            )
            payload = dict(execution["output"])
            status = (
                "passed" if _runtime_output_passed(payload) else "blocked"
            )
            if status != "passed":
                executor_errors.append(
                    f"csharp_verifier_blocked:{pair_id}:{artifact['path']}"
                )
                metadata = payload.get("metadata")
                if isinstance(metadata, Mapping):
                    for issue in _as_rows(metadata.get("issues")):
                        code = str(issue.get("code") or "").strip()
                        if code:
                            executor_errors.append(
                                f"csharp_verifier_issue:{code}:{artifact['path']}"
                            )
            style_receipts.append(
                _issue_style_receipt(
                    boundary=boundary,
                    project_root=root,
                    artifact=artifact,
                    gate=CSHARP_STYLE_SKILL,
                    status=status,
                    result=payload,
                    execution=execution,
                )
            )

    for artifact in [
        item
        for item in artifacts
        if item["artifact_role"] == "sql_candidate"
    ]:
        from src.skills.sql_formatting_style import (
            verify_sql_formatting_style,
        )

        effective_sql_provider = selected_sql_provider
        if effective_sql_provider is None:
            from src.skills.sql_formatting_provider import (
                packaged_sql_formatting_provider,
            )

            effective_sql_provider = packaged_sql_formatting_provider(
                host="codex"
            )
        provider_result, provider_error = _validated_selected_sql_provider(
            effective_sql_provider
        )
        if provider_result is None:
            executor_errors.append(
                f"{provider_error}:{artifact['path']}"
            )
            continue
        if not callable(sql_formatter_runner):
            executor_errors.append(
                f"sql_formatter_runner_unavailable:{artifact['path']}"
            )
            continue

        sql_path = Path(str(artifact["path"]))
        original_bytes = sql_path.read_bytes()
        original_hash = sha256_bytes(original_bytes)
        try:
            candidate_text = original_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            executor_errors.append(
                f"sql_candidate_not_utf8:{artifact['path']}"
            )
            continue
        provider_request = {
            "provider_id": str(provider_result.get("provider_id") or ""),
            "provider_path": str(
                provider_result.get("metadata", {}).get("path") or ""
            ),
            "execution_actor": str(
                provider_result.get("metadata", {}).get("execution_actor")
                or ""
            ),
            "candidate_path": str(sql_path),
            "candidate_sha256": original_hash,
            "candidate_text": candidate_text,
        }
        formatter_execution = registry.invoke(
            tool_name=_STYLE_TOOL_BY_GATE[SQL_FORMATTING_SKILL],
            producer_identity=(
                f"{ARTIFACT_STYLE_PRODUCER}:"
                f"{_STYLE_TOOL_BY_GATE[SQL_FORMATTING_SKILL]}"
            ),
            artifact_path=str(sql_path),
            artifact_sha256=original_hash,
            input_payload=provider_request,
            runner=sql_formatter_runner,
        )
        formatter_output = dict(formatter_execution["output"])
        formatter_history = formatter_output.get("formatter_history")
        current_path, current_error = _canonical_project_file(sql_path, root)
        current_hash = (
            sha256_bytes(current_path.read_bytes())
            if current_path is not None
            else ""
        )
        formatter_status = "passed"
        if (
            not _runtime_output_passed(formatter_output)
            or current_error
            or str(formatter_output.get("provider_id") or "")
            != str(provider_result.get("provider_id") or "")
            or str(formatter_output.get("artifact_path") or "")
            != str(sql_path)
            or _canonical_hash(formatter_output.get("input_sha256"))
            != original_hash
            or _canonical_hash(formatter_output.get("formatted_sha256"))
            != current_hash
            or not isinstance(formatter_history, list)
            or not formatter_history
            or _json_hash(formatter_history)
            != formatter_output.get("formatter_history_sha256")
            or _canonical_hash(formatter_history[-1].get("input_sha256"))
            != original_hash
            or _canonical_hash(formatter_history[-1].get("formatted_sha256"))
            != current_hash
        ):
            formatter_status = "blocked"
            executor_errors.append(
                f"sql_formatter_execution_unbound:{artifact['path']}"
            )
        if formatter_status != "passed":
            style_receipts.append(
                _issue_style_receipt(
                    boundary=boundary,
                    project_root=root,
                    artifact=artifact,
                    gate=SQL_FORMATTING_SKILL,
                    status="blocked",
                    result=formatter_output,
                    execution=formatter_execution,
                    extra={
                        "formatted_output_sha256": current_hash,
                        "formatter_history": (
                            formatter_history
                            if isinstance(formatter_history, list)
                            else []
                        ),
                        "formatter_history_sha256": _json_hash(
                            formatter_history
                            if isinstance(formatter_history, list)
                            else []
                        ),
                        "verifier_history": [],
                        "verifier_history_sha256": _json_hash([]),
                    },
                )
            )
            continue

        artifact["sha256"] = current_hash
        verifier_request = {
            "original_sha256": original_hash,
            "formatted_path": str(sql_path),
            "formatted_sha256": current_hash,
            "operation": "formatting",
        }

        def run_sql_style_verifier(_request: Dict[str, Any]) -> Any:
            return verify_sql_formatting_style(
                original_bytes,
                sql_path,
                operation="formatting",
            )

        verifier_execution = registry.invoke(
            tool_name=_STYLE_TOOL_BY_GATE[SQL_STYLE_SKILL],
            producer_identity=(
                f"{ARTIFACT_STYLE_PRODUCER}:"
                f"{_STYLE_TOOL_BY_GATE[SQL_STYLE_SKILL]}"
            ),
            artifact_path=str(sql_path),
            artifact_sha256=current_hash,
            input_payload=verifier_request,
            runner=run_sql_style_verifier,
        )
        verifier_payload = dict(verifier_execution["output"])
        verifier_status = (
            "passed"
            if _runtime_output_passed(verifier_payload)
            else "blocked"
        )
        verifier_history = [verifier_payload]
        style_receipts.append(
            _issue_style_receipt(
                boundary=boundary,
                project_root=root,
                artifact=artifact,
                gate=SQL_FORMATTING_SKILL,
                status="passed",
                result=formatter_output,
                execution=formatter_execution,
                extra={
                    "original_artifact_sha256": original_hash,
                    "formatted_output_sha256": current_hash,
                    "formatter_history": formatter_history,
                    "formatter_history_sha256": _json_hash(
                        formatter_history
                    ),
                    "verifier_history": verifier_history,
                    "verifier_history_sha256": _json_hash(
                        verifier_history
                    ),
                },
            )
        )
        style_receipts.append(
            _issue_style_receipt(
                boundary=boundary,
                project_root=root,
                artifact=artifact,
                gate=SQL_STYLE_SKILL,
                status=verifier_status,
                result=verifier_payload,
                execution=verifier_execution,
            )
        )
        if verifier_status != "passed":
            executor_errors.append(
                f"sql_style_verifier_blocked:{artifact['path']}"
            )

    runtime_context = dict(context or {})
    runtime_context["style_receipts"] = style_receipts
    gate = _analyze(
        runtime_context,
        project_root=root,
        boundary=boundary,
        artifacts=artifacts,
        artifact_errors=artifact_errors,
    )
    receipt_lifecycle = "not_applicable"
    if operation_receipts:
        if gate["style_passed"]:
            consumption_errors = _consume_csharp_operation_receipts(
                operation_receipts,
                project_root=root,
            )
            if consumption_errors:
                artifact_errors = [*artifact_errors, *consumption_errors]
                executor_errors.extend(consumption_errors)
                gate = _analyze(
                    runtime_context,
                    project_root=root,
                    boundary=boundary,
                    artifacts=artifacts,
                    artifact_errors=artifact_errors,
                )
                receipt_lifecycle = "consume_blocked"
            else:
                receipt_lifecycle = "consumed_after_style_pass"
        else:
            receipt_lifecycle = "retained_for_retry"
    gate["operation_receipt_lifecycle"] = receipt_lifecycle
    snapshot_payload = {
        "schema_version": 1,
        "receipt_type": ARTIFACT_STYLE_SNAPSHOT_KIND,
        "project_root": str(root),
        "manifest_sha256": _json_hash(artifacts),
        "receipt_ids": [
            str(item.get("receipt_id") or "")
            for item in style_receipts
        ],
        "visual_receipt_ids": [
            str(item.get("receipt_id") or "")
            for item in gate.get("visual_qa_receipts", [])
        ],
        "host_registry_id": registry.registry_id,
        "completion_claimed": bool(gate["completion_claimed"]),
        "deployment_claimed": bool(gate["deployment_claimed"]),
        "visual_required": bool(gate["visual_required"]),
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    gate["runtime_snapshot"] = boundary.issue_claim(
        snapshot_payload,
        claim_kind=ARTIFACT_STYLE_SNAPSHOT_KIND,
        claim_id_field="snapshot_id",
        claim_id_prefix="artifact-snapshot",
    )
    gate["executor_status"] = (
        "passed" if gate["style_passed"] else "blocked"
    )
    gate["host_registry_id"] = registry.registry_id
    gate["executor_errors"] = list(dict.fromkeys(executor_errors))
    return gate


def should_execute_artifact_style_precompletion(
    context: Mapping[str, Any] | None,
) -> bool:
    contexts = _contexts(context)
    if not (
        _completion_claimed(contexts)
        or _db_deployment_evidence(contexts)
    ):
        return False
    return any(
        _artifact_role(row) in _ARTIFACT_ROLES
        for source in contexts
        for key in (
            *_ARTIFACT_KEYS,
            "db_deployment",
            "database_deployment",
            "deployment_candidate",
            "executed_candidate",
        )
        for row in _as_rows(source.get(key))
    )


def validate_artifact_style_gate_snapshot(
    gate: Mapping[str, Any] | Any,
    *,
    producer_boundary: RuntimeProducerBoundary | None = None,
) -> Dict[str, Any]:
    """Recompute a serialized gate from its signed snapshot and current bytes."""

    if not isinstance(gate, Mapping):
        return {
            "valid": False,
            "errors": ["artifact_style_gate_missing"],
            "gate": {},
        }
    root, root_error = _canonical_project_root(gate.get("project_root"))
    if root is None:
        return {"valid": False, "errors": [root_error], "gate": {}}
    snapshot = gate.get("runtime_snapshot")
    if not isinstance(snapshot, Mapping):
        return {
            "valid": False,
            "errors": ["artifact_style_runtime_snapshot_missing"],
            "gate": {},
        }
    registry_id = str(snapshot.get("host_registry_id") or "").strip()
    registry = _registered_host_registry(registry_id)
    errors: List[str] = []
    if registry is None:
        errors.append("artifact_host_registry_lookup_required")
        boundary = _runtime_boundary(root)
    else:
        boundary = registry.producer_boundary
        errors.extend(
            boundary.validate_claim(
                snapshot,
                claim_kind=ARTIFACT_STYLE_SNAPSHOT_KIND,
                claim_id_field="snapshot_id",
                consume=False,
            )
        )
    if str(gate.get("host_registry_id") or "") != registry_id:
        errors.append("artifact_style_snapshot_registry_mismatch")
    # A caller boundary is never a substitute for the registered host record.
    _ = producer_boundary
    artifacts = [
        dict(item)
        for item in gate.get("changed_artifacts", [])
        if isinstance(item, Mapping)
    ]
    if _json_hash(artifacts) != snapshot.get("manifest_sha256"):
        errors.append("artifact_style_snapshot_manifest_mismatch")
    context = {
        "project": str(root),
        "changed_artifacts": artifacts,
        "style_receipts": [
            dict(item)
            for item in gate.get("style_receipts", [])
            if isinstance(item, Mapping)
        ],
        "visual_qa_receipts": [
            dict(item)
            for item in gate.get("visual_qa_receipts", [])
            if isinstance(item, Mapping)
        ],
        "completion": bool(snapshot.get("completion_claimed")),
        "deployment": bool(snapshot.get("deployment_claimed")),
        "visual_completion": bool(snapshot.get("visual_required")),
    }
    current_artifact_errors: List[str] = []
    for artifact in artifacts:
        path, path_error = _canonical_project_file(
            artifact.get("path"),
            root,
        )
        if path_error:
            current_artifact_errors.append(
                f"{path_error}:{artifact.get('path') or ''}"
            )
            continue
        assert path is not None
        if sha256_bytes(path.read_bytes()) != _canonical_hash(
            artifact.get("sha256")
        ):
            current_artifact_errors.append(f"artifact_hash_mismatch:{path}")
    recomputed = _analyze(
        context,
        project_root=root,
        boundary=boundary,
        artifacts=artifacts,
        artifact_errors=current_artifact_errors,
    )
    receipt_ids = [
        str(item.get("receipt_id") or "")
        for item in recomputed.get("style_receipts", [])
    ]
    visual_ids = [
        str(item.get("receipt_id") or "")
        for item in recomputed.get("visual_qa_receipts", [])
    ]
    if receipt_ids != list(snapshot.get("receipt_ids") or []):
        errors.append(
            "artifact_style_snapshot_receipt_correlation_mismatch"
        )
    if visual_ids != list(snapshot.get("visual_receipt_ids") or []):
        errors.append(
            "artifact_style_snapshot_visual_correlation_mismatch"
        )
    if (
        recomputed.get("artifact_errors")
        or recomputed.get("receipt_errors")
        or recomputed.get("visual_receipt_errors")
    ):
        errors.extend(recomputed.get("artifact_errors", []))
        errors.extend(recomputed.get("receipt_errors", []))
        errors.extend(recomputed.get("visual_receipt_errors", []))
        errors.append("artifact_style_snapshot_revalidation_failed")
    return {
        "valid": not errors,
        "errors": list(dict.fromkeys(errors)),
        "gate": recomputed,
    }


def is_csharp_designer_request(text: str) -> bool:
    normalized = str(text or "").lower()
    ui = bool(
        re.search(
            r"\b(?:winforms?|windows forms?|devexpress|konelib|designer)\b"
            r"|\.designer\.cs\b",
            normalized,
        )
    )
    action = bool(
        re.search(
            r"\b(?:create|modify|update|implement|build|generate|write|add|"
            r"fix|edit|change|refactor|design|convert|migrate)\b"
            r"|(?:해줘|해주세요|수정|변경|추가|구현|생성|작성|만들)",
            normalized,
        )
    )
    return ui and action


def style_requirements_for_request(
    text: str,
    *,
    pb_migration: bool = False,
) -> List[str]:
    requirements = (
        [CSHARP_STYLE_SKILL]
        if is_csharp_designer_request(text)
        else []
    )
    if pb_migration:
        requirements.extend(
            [
                CSHARP_STYLE_SKILL,
                SQL_FORMATTING_SKILL,
                SQL_STYLE_SKILL,
            ]
        )
    return list(dict.fromkeys(requirements))


def style_evidence_for_gate(gate: Mapping[str, Any]) -> List[str]:
    evidence = [
        "changed_artifacts",
        "authenticated_artifact_style_snapshot",
        "current_byte_sha256_receipts",
    ]
    if gate.get("stale_receipts"):
        evidence.append(
            "stale_artifact_receipt_invalidated_by_hash"
        )
    if gate.get("visual_required"):
        evidence.append(
            "authenticated_visual_completion_receipt"
        )
    return evidence
