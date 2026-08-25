from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from src.contracts import HarnessResult


_SHA256_PATTERN = re.compile(r"(?:sha256:)?(?P<digest>[0-9a-fA-F]{64})\Z")
_ARTIFACT_ID_HEADER_PATTERN = re.compile(
    r"^\s*//\s*ARTIFACT-ID\s*:\s*(?P<value>[A-Za-z0-9][A-Za-z0-9_.:-]*)\s*$",
    flags=re.IGNORECASE | re.MULTILINE,
)
PROFILE_MAINTENANCE_ARTIFACT_MAX_BYTES = 8 * 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024


def _issue(code: str, message: str, **details: Any) -> Dict[str, Any]:
    return {"code": code, "severity": "error", "message": message, **details}


def _path_key(value: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(value)))


def _normalized_sha256(value: Any) -> str:
    match = _SHA256_PATTERN.fullmatch(str(value or "").strip())
    return match.group("digest").lower() if match else ""


def _normalize_keyed_mapping(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {_path_key(str(path)): item for path, item in value.items() if str(path).strip()}


def _normalize_allowlist(value: Any) -> tuple[list[str], bool]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return [], False
    raw_paths = [str(item).strip() for item in value]
    if not raw_paths or any(not item or not os.path.isabs(item) for item in raw_paths):
        return [], False
    normalized = [_path_key(item) for item in raw_paths]
    return normalized, len(normalized) == len(set(normalized))


def _normalize_procedure_program_key(value: Any) -> str:
    name = str(value or "").strip().strip("[]")
    if "." in name:
        name = name.split(".")[-1].strip().strip("[]")
    normalized = re.sub(r"[^A-Za-z0-9_]", "", name).upper()
    if normalized.startswith("SP_"):
        normalized = normalized[3:]
    for suffix in ("_SELECT", "_SAVE"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _class_program_key(value: Any) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "", str(value or "")).upper()
    for suffix in ("FORM", "FRM"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _read_current_artifact(path_value: str) -> tuple[str, int, bytes]:
    path = Path(path_value)
    try:
        before = path.stat()
    except OSError as exc:
        raise ValueError(f"artifact_unreadable:{exc}") from exc
    if not path.is_file():
        raise ValueError("artifact_not_regular_file")
    if before.st_size > PROFILE_MAINTENANCE_ARTIFACT_MAX_BYTES:
        raise ValueError("artifact_size_limit_exceeded")
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    try:
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(_READ_CHUNK_BYTES)
                if not chunk:
                    break
                total += len(chunk)
                if total > PROFILE_MAINTENANCE_ARTIFACT_MAX_BYTES:
                    raise ValueError("artifact_size_limit_exceeded")
                digest.update(chunk)
                chunks.append(chunk)
        after = path.stat()
    except OSError as exc:
        raise ValueError(f"artifact_unreadable:{exc}") from exc
    if total != before.st_size or (after.st_size, after.st_mtime_ns) != (
        before.st_size,
        before.st_mtime_ns,
    ):
        raise ValueError("artifact_changed_during_read")
    return digest.hexdigest(), total, b"".join(chunks)


def _validate_pre_read_contract(
    *,
    profile_id: str,
    profile_version: str,
    explicit_user_authorization: bool,
    artifact_allowlist: Any,
    expected_sha256: Any,
    independent_provenance: Any,
    custody_records: Any,
    uniqueness_decision: Any,
) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
    issues: list[Dict[str, Any]] = []
    allowlist, allowlist_unique = _normalize_allowlist(artifact_allowlist)
    expected = _normalize_keyed_mapping(expected_sha256)
    provenance = _normalize_keyed_mapping(independent_provenance)
    custody = _normalize_keyed_mapping(custody_records)

    if explicit_user_authorization is not True:
        issues.append(
            _issue(
                "profile_update_explicit_user_authorization_required",
                "Profile maintenance requires explicit user authorization for this exact candidate set.",
            )
        )
    if not str(profile_id or "").strip() or not str(profile_version or "").strip():
        issues.append(
            _issue(
                "profile_update_identity_required",
                "Profile maintenance requires profile_id and profile_version.",
            )
        )
    if not allowlist or not allowlist_unique:
        issues.append(
            _issue(
                "profile_update_exact_artifact_allowlist_required",
                "artifact_allowlist must be a non-empty unique list of exact artifact paths.",
            )
        )
    if allowlist and (
        len(allowlist) != 2
        or sum(path.lower().endswith(".designer.cs") for path in allowlist) != 1
        or sum(path.lower().endswith(".cs") and not path.lower().endswith(".designer.cs") for path in allowlist) != 1
    ):
        issues.append(
            _issue(
                "profile_update_csharp_pair_ambiguous",
                "The exact allowlist must contain one code-behind .cs artifact and one .Designer.cs artifact.",
                artifact_count=len(allowlist),
            )
        )
    for path in allowlist:
        try:
            stat = Path(path).stat()
        except OSError as exc:
            issues.append(
                _issue(
                    "profile_update_artifact_unreadable",
                    "Every allowlisted artifact must exist as a current regular file before content read.",
                    path=path,
                    detail=str(exc),
                )
            )
            continue
        if not Path(path).is_file():
            issues.append(
                _issue(
                    "profile_update_artifact_not_regular_file",
                    "Every allowlisted artifact must be a regular file.",
                    path=path,
                )
            )
        elif stat.st_size > PROFILE_MAINTENANCE_ARTIFACT_MAX_BYTES:
            issues.append(
                _issue(
                    "profile_update_artifact_size_limit_exceeded",
                    "An allowlisted artifact exceeds the bounded maintenance read limit.",
                    path=path,
                    size_bytes=stat.st_size,
                    maximum_bytes=PROFILE_MAINTENANCE_ARTIFACT_MAX_BYTES,
                )
            )
    allowlist_set = set(allowlist)
    if set(expected) != allowlist_set or any(not _normalized_sha256(expected.get(path)) for path in allowlist):
        issues.append(
            _issue(
                "profile_update_expected_sha256_required",
                "Every allowlisted artifact requires one exact expected SHA-256 and no extra hash entries.",
            )
        )

    provenance_valid = set(provenance) == allowlist_set
    provenance_reviewers: set[str] = set()
    provenance_capturers: set[str] = set()
    if provenance_valid:
        for path in allowlist:
            item = provenance.get(path)
            if not isinstance(item, Mapping):
                provenance_valid = False
                break
            source_system = str(item.get("source_system") or "").strip()
            capture_id = str(item.get("capture_id") or "").strip()
            captured_by = str(item.get("captured_by") or "").strip()
            reviewer = str(item.get("independent_reviewer") or "").strip()
            if not source_system or not capture_id or not captured_by or not reviewer or captured_by == reviewer:
                provenance_valid = False
                break
            provenance_reviewers.add(reviewer)
            provenance_capturers.add(captured_by)
    if not provenance_valid:
        issues.append(
            _issue(
                "profile_update_independent_provenance_required",
                "Every allowlisted artifact requires source_system, capture_id, captured_by, and a different independent_reviewer.",
            )
        )

    custody_valid = set(custody) == allowlist_set
    custodians: set[str] = set()
    if custody_valid:
        for path in allowlist:
            item = custody.get(path)
            if not isinstance(item, Mapping):
                custody_valid = False
                break
            custodian = str(item.get("custodian") or "").strip()
            receipt_id = str(item.get("receipt_id") or "").strip()
            acquired_at = str(item.get("acquired_at") or "").strip()
            if (
                not custodian
                or not receipt_id
                or not acquired_at
                or custodian in provenance_reviewers
                or custodian in provenance_capturers
            ):
                custody_valid = False
                break
            custodians.add(custodian)
    if not custody_valid:
        issues.append(
            _issue(
                "profile_update_independent_custody_required",
                "Every allowlisted artifact requires an independently held custodian, receipt_id, and acquired_at value.",
            )
        )

    uniqueness_valid = isinstance(uniqueness_decision, Mapping)
    if uniqueness_valid:
        decision_paths, decision_unique = _normalize_allowlist(
            uniqueness_decision.get("artifact_paths")
        )
        uniqueness_valid = bool(
            uniqueness_decision.get("status") == "unique"
            and uniqueness_decision.get("copied_artifact_id") is False
            and uniqueness_decision.get("ambiguous") is False
            and str(uniqueness_decision.get("reviewed_by") or "").strip()
            and str(uniqueness_decision.get("reviewed_by") or "").strip()
            not in provenance_reviewers | provenance_capturers | custodians
            and decision_unique
            and set(decision_paths) == allowlist_set
        )
    if not uniqueness_valid:
        issues.append(
            _issue(
                "profile_update_uniqueness_decision_required",
                "A unique, non-ambiguous, non-copied decision bound to the exact allowlist is required.",
            )
        )

    return issues, {
        "artifact_allowlist": allowlist,
        "expected_sha256": {
            path: f"sha256:{_normalized_sha256(expected.get(path))}"
            for path in allowlist
            if _normalized_sha256(expected.get(path))
        },
        "pre_read_checks_passed": not issues,
    }


def _extract_style(source_text: str, designer_text: str) -> Dict[str, Any]:
    combined = source_text + "\n" + designer_text
    return {
        "method_names": sorted(
            set(
                re.findall(
                    r"\b(?:private|protected|public|internal)\s+(?:override\s+)?"
                    r"(?:void|DataSet|bool|string|int)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
                    source_text,
                )
            )
        ),
        "grid_controls": sorted(set(re.findall(r"\b(grd[A-Za-z0-9_]*)\b", combined))),
        "grid_views": sorted(set(re.findall(r"\b(gvw[A-Za-z0-9_]*)\b", combined))),
        "grid_columns": sorted(
            set(re.findall(r"\b(col(?:List|Detail|[A-Za-z0-9]+)_[A-Z0-9_]+)\b", designer_text))
        ),
        "binding_fields": sorted(set(re.findall(r'\.BindingField\s*=\s*"([^"]+)"', designer_text))),
        "repository_spin_controls": sorted(set(re.findall(r"\b(rpsSpin[A-Za-z0-9_]*)\b", designer_text))),
    }


def build_profile_update_candidate(
    procedure_name: str,
    *,
    profile_id: str,
    profile_version: str,
    explicit_user_authorization: bool = False,
    artifact_allowlist: Sequence[str] | None = None,
    expected_sha256: Mapping[str, str] | None = None,
    independent_provenance: Mapping[str, Mapping[str, Any]] | None = None,
    custody_records: Mapping[str, Mapping[str, Any]] | None = None,
    uniqueness_decision: Mapping[str, Any] | None = None,
) -> HarnessResult:
    """Build a candidate only after exact pre-read authorization and custody checks."""
    issues, pre_read = _validate_pre_read_contract(
        profile_id=profile_id,
        profile_version=profile_version,
        explicit_user_authorization=explicit_user_authorization,
        artifact_allowlist=artifact_allowlist,
        expected_sha256=expected_sha256,
        independent_provenance=independent_provenance,
        custody_records=custody_records,
        uniqueness_decision=uniqueness_decision,
    )
    allowlist = list(pre_read["artifact_allowlist"])
    artifact_receipts: list[Dict[str, Any]] = []
    texts: Dict[str, str] = {}

    if not issues:
        for path in allowlist:
            try:
                actual, size, raw = _read_current_artifact(path)
            except ValueError as exc:
                issues.append(_issue("profile_update_artifact_read_failed", str(exc), path=path))
                continue
            expected = _normalized_sha256(pre_read["expected_sha256"].get(path))
            if actual != expected:
                issues.append(
                    _issue(
                        "profile_update_artifact_sha256_mismatch",
                        "An allowlisted artifact does not match its expected SHA-256.",
                        path=path,
                        expected_sha256=f"sha256:{expected}",
                        actual_sha256=f"sha256:{actual}",
                    )
                )
                continue
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                issues.append(_issue("profile_update_artifact_decode_failed", str(exc), path=path))
                continue
            texts[path] = text
            artifact_receipts.append(
                {
                    "path": str(Path(path).resolve()),
                    "sha256": f"sha256:{actual}",
                    "size_bytes": size,
                    "content_read": True,
                }
            )

    artifact_id_records: list[Dict[str, str]] = []
    if not issues:
        for path in allowlist:
            text = texts[path]
            artifact_ids = [match.group("value").strip() for match in _ARTIFACT_ID_HEADER_PATTERN.finditer(text)]
            if not artifact_ids:
                issues.append(
                    _issue(
                        "profile_update_artifact_id_missing",
                        "Each candidate artifact requires exactly one ARTIFACT-ID header.",
                        path=path,
                    )
                )
                continue
            if len(artifact_ids) != 1:
                issues.append(
                    _issue(
                        "profile_update_artifact_id_ambiguous",
                        "The ARTIFACT-ID header must be unique within each file.",
                        path=path,
                    )
                )
                continue
            artifact_id_records.append(
                {"path": path, "artifact_id": artifact_ids[0]}
            )
        artifact_ids = [item["artifact_id"].lower() for item in artifact_id_records]
        if len(artifact_ids) != len(set(artifact_ids)):
            issues.append(
                _issue(
                    "profile_update_copied_artifact_id_rejected",
                    "Candidate artifacts must not reuse an ARTIFACT-ID header.",
                )
            )

    candidate: Dict[str, Any] = {}
    if not issues:
        source_path = next(path for path in allowlist if not path.lower().endswith(".designer.cs"))
        designer_path = next(path for path in allowlist if path.lower().endswith(".designer.cs"))
        source_text = texts[source_path]
        designer_text = texts[designer_path]
        source_classes = re.findall(
            r"\bpartial\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\b",
            source_text,
            flags=re.IGNORECASE,
        )
        designer_classes = re.findall(
            r"\bpartial\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\b",
            designer_text,
            flags=re.IGNORECASE,
        )
        source_file_identity = Path(source_path).name[:-3]
        designer_file_identity = Path(designer_path).name[: -len(".Designer.cs")]
        procedure_key = _normalize_procedure_program_key(procedure_name)
        expected_method = (
            "CallSaveProcedure"
            if str(procedure_name or "").strip().upper().rstrip("]").endswith("_SAVE")
            else "CallSelectProcedure"
        )
        pair_valid = bool(
            len(source_classes) == 1
            and len(designer_classes) == 1
            and source_classes[0].casefold() == designer_classes[0].casefold()
            and source_file_identity.casefold() == designer_file_identity.casefold()
            and _class_program_key(source_classes[0]) == procedure_key
            and re.search(r"\bInitializeComponent\s*\(", designer_text)
            and not re.search(
                r"\b(?:private|protected|public|internal)\s+void\s+InitializeComponent\s*\(",
                source_text,
            )
            and re.search(rf"\b{re.escape(expected_method)}\s*\(", source_text)
        )
        if not pair_valid:
            issues.append(
                _issue(
                    "profile_update_program_pair_mismatch",
                    "The exact pair must share one partial class/file identity and the procedure program key with canonical ownership.",
                    procedure_program_key=procedure_key,
                    source_classes=source_classes,
                    designer_classes=designer_classes,
                    expected_method=expected_method,
                )
            )
        else:
            candidate = {
                "profile_id": str(profile_id),
                "version": str(profile_version),
                "sanitized": False,
                "candidate_source": "exact_allowlisted_artifacts",
                "procedure_name": str(procedure_name or ""),
                "procedure_program_key": procedure_key,
                "partial_class": source_classes[0],
                "extracted_style": _extract_style(source_text, designer_text),
            }

    success = not issues
    metadata = {
        "harness": "pb-to-csharp-profile-maintenance",
        "operation": "explicit_profile_maintenance",
        "status": "candidate_ready" if success else "blocked",
        "write_status": "candidate_only",
        "profile_id": str(profile_id or ""),
        "profile_version": str(profile_version or ""),
        "pre_read_contract": pre_read,
        "artifact_receipts": artifact_receipts,
        "artifact_id_records": artifact_id_records,
        "candidate_profile": candidate,
        "issues": issues,
        "runtime_generation_eligible": False,
        "token_optimizer_status": "passthrough",
    }
    return HarnessResult(
        success=success,
        stdout=json.dumps(
            {"status": metadata["status"], "operation": metadata["operation"]},
            ensure_ascii=False,
            sort_keys=True,
        ),
        stderr="" if success else "Explicit profile maintenance failed closed.",
        exit_code=0 if success else 1,
        metadata=metadata,
    )
