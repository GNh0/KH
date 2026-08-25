"""Bounded GM-31 delivery and GM-32 PB acquisition preflight contracts.

Only caller-supplied paths are read. The module does not discover tools,
search roots, invoke builds, or execute PblScripter/ORCA.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime
from typing import Any, Mapping, Sequence
import xml.etree.ElementTree as ET


GM31_CONTRACT_ID = "GM-31"
GM32_CONTRACT_ID = "GM-32"
SCHEMA_VERSION = "pb-migration-preflight/v2"
MAX_RECEIPT_FILE_BYTES = 32 * 1024 * 1024
MAX_DEPENDENCIES = 64
MAX_GENERATED_FILES = 64
MAX_RUNTIME_LIBRARIES = 16
MAX_EXPORTED_OBJECTS = 128

ISSUE_GM31_TARGET_PROJECT_INVALID = "gm31_target_project_invalid"
ISSUE_GM31_TARGET_PROJECT_MISMATCH = "gm31_target_project_mismatch"
ISSUE_GM31_PROJECT_HASH_MISMATCH = "gm31_project_hash_mismatch"
ISSUE_GM31_PROJECT_READBACK_INVALID = "gm31_project_readback_invalid"
ISSUE_GM31_DEPENDENCY_INVALID = "gm31_dependency_invalid"
ISSUE_GM31_DEPENDENCY_OWNER_MISMATCH = "gm31_dependency_owner_mismatch"
ISSUE_GM31_DEPENDENCY_NOT_IN_PROJECT = "gm31_dependency_not_in_project"
ISSUE_GM31_INCLUSION_INVALID = "gm31_generated_inclusion_invalid"
ISSUE_GM31_INCLUSION_OWNER_MISMATCH = "gm31_inclusion_owner_mismatch"
ISSUE_GM31_EXPLICIT_COMPILE_MISSING = "gm31_explicit_compile_include_missing"
ISSUE_GM31_SDK_DEFAULT_UNAVAILABLE = "gm31_sdk_default_compile_unavailable"
ISSUE_GM31_EVIDENCE_ORDER_INVALID = "gm31_evidence_order_invalid"
ISSUE_GM31_BUILD_RECEIPT_INVALID = "gm31_build_receipt_invalid"
ISSUE_GM31_BUILD_FAILED = "gm31_build_failed"
ISSUE_GM31_COMPLETION_PREMATURE = "gm31_completion_premature"
ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID = "gm31_build_execution_correlation_invalid"
ISSUE_GM31_RECEIPT_DUPLICATE = "gm31_receipt_duplicate"
ISSUE_GM31_DEPENDENCY_VERSION_DRIFT = "gm31_dependency_version_drift"
ISSUE_GM31_DEPENDENCY_SET_MISMATCH = "gm31_dependency_set_mismatch"

ISSUE_GM32_DISCOVERY_INPUT_FORBIDDEN = "gm32_discovery_input_forbidden"
ISSUE_GM32_PBLSCRIPTER_UNUSABLE = "gm32_pblscripter_unusable"
ISSUE_GM32_ORCA_SELECTION_INVALID = "gm32_orca_selection_invalid"
ISSUE_GM32_ORCA_RUNTIME_UNUSABLE = "gm32_orca_runtime_unusable"
ISSUE_GM32_EXPORT_RECEIPT_INVALID = "gm32_export_receipt_invalid"
ISSUE_GM32_EXPORT_NOT_CURRENT = "gm32_export_not_current"
ISSUE_GM32_ACQUISITION_UNRESOLVED = "gm32_acquisition_unresolved"
ISSUE_GM32_TOOL_IDENTITY_INVALID = "gm32_tool_identity_invalid"
ISSUE_GM32_TOOL_CAPABILITY_INVALID = "gm32_tool_capability_invalid"
ISSUE_GM32_EXECUTION_CORRELATION_INVALID = "gm32_execution_correlation_invalid"
ISSUE_GM32_REQUESTED_PBL_INVALID = "gm32_requested_pbl_invalid"
ISSUE_GM32_REQUESTED_OBJECT_SET_INVALID = "gm32_requested_object_set_invalid"
ISSUE_GM32_EXPORT_BINDING_MISMATCH = "gm32_export_request_binding_mismatch"
ISSUE_GM32_RECEIPT_DUPLICATE = "gm32_receipt_duplicate"
ISSUE_GM32_OUTPUT_HASH_INVALID = "gm32_output_object_hash_invalid"
ISSUE_GM32_VERIFIER_PROVENANCE_INVALID = "gm32_verifier_provenance_invalid"
ISSUE_GM32_COMMAND_SEMANTICS_INVALID = "gm32_command_semantics_invalid"
ISSUE_GM32_EXPORT_STRUCTURE_INVALID = "gm32_export_structure_invalid"

_SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-fA-F]{64}$")
_FORBIDDEN_DISCOVERY_KEYS = {
    "candidate",
    "candidates",
    "discover",
    "discovery",
    "glob",
    "history",
    "repository_root",
    "root",
    "roots",
    "scan",
    "search_root",
    "source_root",
    "versions",
}
_ALLOWED_GM32_PRODUCERS = {"pb-migration-preflight-host"}
_ALLOWED_GM32_PROVENANCE_KINDS = {"runtime_invoked_tool_receipt"}
_REQUIRED_GM32_CAPABILITIES = {
    "pb_export",
    "pb_export_parse",
    "pb_export_readback",
}


@dataclass(frozen=True)
class PreflightResult:
    """Deterministic result shared by the standalone contracts."""

    success: bool
    issues: tuple[Mapping[str, Any], ...]
    metadata: Mapping[str, Any]

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(str(issue["code"]) for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "issue_codes": list(self.issue_codes),
            "issues": [dict(issue) for issue in self.issues],
            "metadata": dict(self.metadata),
        }


def _issue(code: str, field: str, message: str, **details: Any) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "error",
        "field": field,
        "message": message,
        **details,
    }


def _finish(
    issues: list[dict[str, Any]], metadata: dict[str, Any]
) -> PreflightResult:
    issues.sort(
        key=lambda item: (
            str(item["code"]),
            str(item["field"]),
            json.dumps(item, sort_keys=True, default=str),
        )
    )
    metadata["status"] = "passed" if not issues else "blocked"
    metadata["issue_codes"] = sorted({str(item["code"]) for item in issues})
    return PreflightResult(not issues, tuple(issues), metadata)


def _normalized_hash(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text[7:] if text.startswith("sha256:") else text


def _read_exact_file(
    receipt: Mapping[str, Any],
    *,
    field: str,
    issue_code: str,
    hash_field: str = "sha256",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    path_text = str(receipt.get("path") or "").strip()
    requested_hash = _normalized_hash(receipt.get(hash_field))
    computed_hash = ""
    size = 0
    resolved_path = path_text

    if not path_text or not Path(path_text).is_absolute():
        issues.append(_issue(issue_code, f"{field}.path", "An explicit absolute file path is required."))
    if not _SHA256_RE.fullmatch(str(receipt.get(hash_field) or "").strip()):
        issues.append(_issue(issue_code, f"{field}.{hash_field}", "A complete SHA-256 receipt is required."))

    if path_text and Path(path_text).is_absolute():
        path = Path(path_text)
        try:
            before = path.stat()
            if not path.is_file() or before.st_size > MAX_RECEIPT_FILE_BYTES:
                raise OSError("not a bounded regular file")
            payload = path.read_bytes()
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise OSError("file changed during readback")
            size = len(payload)
            computed_hash = hashlib.sha256(payload).hexdigest()
            resolved_path = str(path.resolve())
            if requested_hash and requested_hash != computed_hash:
                issues.append(_issue(issue_code, f"{field}.{hash_field}", "Receipt and readback SHA-256 values differ."))
        except OSError:
            issues.append(_issue(issue_code, f"{field}.path", "The explicit file is not readable within the bounded receipt limit."))

    return (
        {
            "path": resolved_path,
            "requested_sha256": f"sha256:{requested_hash}" if requested_hash else "",
            "readback_sha256": f"sha256:{computed_hash}" if computed_hash else "",
            "size": size,
        },
        issues,
    )


def _sequence(
    receipt: Mapping[str, Any], field: str, issue_code: str, issues: list[dict[str, Any]]
) -> int | None:
    value = receipt.get("sequence")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        issues.append(_issue(issue_code, f"{field}.sequence", "Receipt sequence must be a non-negative integer."))
        return None
    return value


def _timestamp(
    receipt: Mapping[str, Any], field: str, issue_code: str, issues: list[dict[str, Any]]
) -> str:
    value = str(receipt.get("timestamp") or receipt.get("completed_at") or "").strip()
    if not value:
        issues.append(_issue(issue_code, f"{field}.timestamp", "A timezone-aware execution timestamp is required."))
        return ""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None:
        issues.append(_issue(issue_code, f"{field}.timestamp", "Execution timestamps must be ISO-8601 values with a timezone."))
        return ""
    return value


def _timestamp_value(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _call_id(
    receipt: Mapping[str, Any], field: str, issue_code: str, issues: list[dict[str, Any]]
) -> str:
    value = str(receipt.get("call_id") or "").strip()
    if not value:
        issues.append(_issue(issue_code, f"{field}.call_id", "A host-issued execution call_id is required."))
    return value


def _duplicate_receipt_issues(
    receipts: Sequence[Mapping[str, Any]], field: str, issue_code: str, keys: Sequence[str]
) -> list[dict[str, Any]]:
    indexes: dict[tuple[str, ...], list[int]] = {}
    for index, receipt in enumerate(receipts):
        identity = tuple(str(receipt.get(key) or "").strip().casefold() for key in keys)
        if any(identity):
            indexes.setdefault(identity, []).append(index)
    return [
        _issue(issue_code, field, "Duplicate receipts are rejected before semantic mapping.", receipt_indexes=positions)
        for positions in indexes.values()
        if len(positions) > 1
    ]


def _same_path(left: Any, right: Any) -> bool:
    try:
        return Path(str(left)).resolve() == Path(str(right)).resolve()
    except (OSError, ValueError):
        return False


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _normalized_include(value: Any) -> str:
    return str(value or "").strip().replace("/", "\\").strip("\\").casefold()


def _project_model(path: Path) -> tuple[ET.Element | None, str | None]:
    try:
        return ET.fromstring(path.read_bytes()), None
    except (OSError, ET.ParseError) as exc:
        return None, type(exc).__name__


def _project_has_item(
    root: ET.Element, tag: str, include: str, *, project_path: Path | None = None
) -> bool:
    expected = _normalized_include(include)
    for element in _evaluated_project_elements(root, project_path):
        for candidate in element.iter():
            if (
                _xml_local_name(candidate.tag) == tag
                and _normalized_include(candidate.attrib.get("Include")) == expected
            ):
                return True
    return False


def _project_dependencies(root: ET.Element) -> dict[tuple[str, str], str]:
    tags = {
        "ProjectReference": "project",
        "PackageReference": "package",
        "Reference": "assembly",
    }
    declared: dict[tuple[str, str], str] = {}
    for element in root.iter():
        kind = tags.get(_xml_local_name(element.tag))
        include = str(element.attrib.get("Include") or "").strip()
        if not kind or not include:
            continue
        version = str(
            element.attrib.get("Version")
            or element.attrib.get("VersionOverride")
            or ""
        ).strip()
        for child in element:
            if _xml_local_name(child.tag) in {"Version", "VersionOverride"} and (child.text or "").strip():
                version = (child.text or "").strip()
        declared[(kind, include.casefold())] = version
    return declared


def _msbuild_condition_applies(condition: Any, properties: Mapping[str, str]) -> bool:
    text = str(condition or "").strip()
    if not text:
        return True

    def expand(value: str) -> str:
        return re.sub(
            r"\$\(([^)]+)\)",
            lambda match: properties.get(match.group(1), ""),
            value,
        ).strip()

    text = expand(text)
    for operator in (" or ", " and "):
        parts = re.split(re.escape(operator), text, flags=re.IGNORECASE)
        if len(parts) > 1:
            values = [_msbuild_condition_applies(part, properties) for part in parts]
            return any(values) if operator.strip() == "or" else all(values)
    match = re.fullmatch(r"['\"]?(.*?)['\"]?\s*(==|!=)\s*['\"]?(.*?)['\"]?", text)
    if match:
        left, comparison, right = (item.strip().strip("'\"") for item in match.groups())
        equal = left.casefold() == right.casefold()
        return equal if comparison == "==" else not equal
    return text.casefold() not in {"false", "0"}


def _import_path(project_path: Path | None, project_value: Any, properties: Mapping[str, str]) -> Path | None:
    value = str(project_value or "").strip()
    if not value or any(char in value for char in "*?[]"):
        return None
    value = re.sub(
        r"\$\(([^)]+)\)",
        lambda match: properties.get(match.group(1), ""),
        value,
    )
    path = Path(value)
    if not path.is_absolute() and project_path is not None:
        path = project_path.parent / path
    return path.resolve()


def _evaluated_project_elements(
    root: ET.Element,
    project_path: Path | None = None,
    *,
    _current_path: Path | None = None,
    _seen: set[Path] | None = None,
    _properties: dict[str, str] | None = None,
) -> list[ET.Element]:
    """Flatten explicit MSBuild imports in evaluation order without discovery."""
    seen = _seen if _seen is not None else set()
    properties = _properties if _properties is not None else {}
    current_path = _current_path or project_path
    elements: list[ET.Element] = []
    for child in list(root):
        name = _xml_local_name(child.tag)
        if name == "Import":
            if not _msbuild_condition_applies(child.attrib.get("Condition"), properties):
                continue
            imported_path = _import_path(current_path, child.attrib.get("Project"), properties)
            if imported_path is None or imported_path in seen:
                continue
            try:
                imported_root = ET.fromstring(imported_path.read_bytes())
            except (OSError, ET.ParseError):
                continue
            seen.add(imported_path)
            elements.extend(
                _evaluated_project_elements(
                    imported_root,
                    project_path,
                    _current_path=imported_path,
                    _seen=seen,
                    _properties=properties,
                )
            )
            continue
        if name == "PropertyGroup" and _msbuild_condition_applies(child.attrib.get("Condition"), properties):
            for property_element in list(child):
                if _msbuild_condition_applies(property_element.attrib.get("Condition"), properties):
                    value = (property_element.text or "").strip()
                    value = re.sub(
                        r"\$\(([^)]+)\)",
                        lambda match: properties.get(match.group(1), ""),
                        value,
                    )
                    properties[_xml_local_name(property_element.tag)] = value
        elements.append(child)
    return elements


def _sdk_default_includes(
    root: ET.Element, relative_path: str, *, project_path: Path | None = None
) -> bool:
    sdk_style = bool(root.attrib.get("Sdk")) or any(
        _xml_local_name(element.tag) == "Sdk" for element in root.iter()
    )
    if not sdk_style:
        return False
    properties: dict[str, str] = {}
    elements = _evaluated_project_elements(root, project_path, _properties=properties)
    default_items = properties.get("EnableDefaultItems", "true")
    default_compile_items = properties.get("EnableDefaultCompileItems")
    default_enabled = default_items.casefold() != "false" and (
        default_compile_items is None or default_compile_items.casefold() != "false"
    )
    expected = _normalized_include(relative_path)
    for element in elements:
        for candidate in element.iter():
            if _xml_local_name(candidate.tag) == "Compile" and _normalized_include(candidate.attrib.get("Remove")) == expected:
                default_enabled = False
    return default_enabled


def verify_gm31_project_build_contract(
    *,
    expected_project_path: str | Path,
    target_project_receipt: Mapping[str, Any],
    dependency_receipts: Sequence[Mapping[str, Any]],
    generated_file_receipts: Sequence[Mapping[str, Any]],
    project_readback_receipt: Mapping[str, Any],
    build_invocation_receipt: Mapping[str, Any],
    build_output_receipt: Mapping[str, Any],
    completion_receipt: Mapping[str, Any] | None = None,
    completion_requested: bool = False,
) -> PreflightResult:
    """Verify exact GM-31 project ownership, inclusion, and receipt ordering."""

    issues: list[dict[str, Any]] = []
    expected_path = Path(expected_project_path)
    expected_text = str(expected_path.resolve()) if expected_path.is_absolute() else str(expected_path)
    if not expected_path.is_absolute() or expected_path.suffix.casefold() != ".csproj":
        issues.append(_issue(ISSUE_GM31_TARGET_PROJECT_INVALID, "expected_project_path", "The target must be one explicit absolute .csproj path."))

    project_file, file_issues = _read_exact_file(
        target_project_receipt,
        field="target_project_receipt",
        issue_code=ISSUE_GM31_TARGET_PROJECT_INVALID,
    )
    issues.extend(file_issues)
    project_sequence = _sequence(target_project_receipt, "target_project_receipt", ISSUE_GM31_TARGET_PROJECT_INVALID, issues)
    if not _same_path(target_project_receipt.get("path"), expected_path):
        issues.append(_issue(ISSUE_GM31_TARGET_PROJECT_MISMATCH, "target_project_receipt.path", "The receipt does not name the exact selected target project."))

    root, project_error = _project_model(expected_path) if expected_path.is_absolute() else (None, "invalid_path")
    if project_error:
        issues.append(_issue(ISSUE_GM31_TARGET_PROJECT_INVALID, "target_project_receipt.path", "The selected project could not be read back as XML.", error=project_error))

    dependency_values = (
        list(dependency_receipts)
        if isinstance(dependency_receipts, Sequence)
        and not isinstance(dependency_receipts, (str, bytes, bytearray))
        else []
    )
    if len(dependency_values) > MAX_DEPENDENCIES:
        issues.append(_issue(ISSUE_GM31_DEPENDENCY_INVALID, "dependency_receipts", "Dependency receipts exceed the bounded maximum."))
    prerequisite_sequences: list[int] = [project_sequence] if project_sequence is not None else []
    dependency_metadata: list[dict[str, Any]] = []
    tags = {
        "project": "ProjectReference",
        "package": "PackageReference",
        "assembly": "Reference",
    }
    issues.extend(
        _duplicate_receipt_issues(
            dependency_values[:MAX_DEPENDENCIES],
            "dependency_receipts",
            ISSUE_GM31_RECEIPT_DUPLICATE,
            ("kind", "include"),
        )
    )
    declared_dependencies = _project_dependencies(root) if root is not None else {}
    supplied_dependencies: set[tuple[str, str]] = set()
    for index, receipt in enumerate(dependency_values[:MAX_DEPENDENCIES]):
        field = f"dependency_receipts[{index}]"
        if not isinstance(receipt, Mapping):
            issues.append(_issue(ISSUE_GM31_DEPENDENCY_INVALID, field, "Dependency receipt must be an object."))
            continue
        sequence = _sequence(receipt, field, ISSUE_GM31_DEPENDENCY_INVALID, issues)
        if sequence is not None:
            prerequisite_sequences.append(sequence)
        kind = str(receipt.get("kind") or "").strip().lower()
        include = str(receipt.get("include") or "").strip()
        version = str(receipt.get("version") or "").strip()
        owner = receipt.get("owner_project_path")
        if kind not in tags or not include:
            issues.append(_issue(ISSUE_GM31_DEPENDENCY_INVALID, field, "Dependency kind and exact Include value are required."))
        if not _same_path(owner, expected_path):
            issues.append(_issue(ISSUE_GM31_DEPENDENCY_OWNER_MISMATCH, f"{field}.owner_project_path", "Dependency ownership does not match the selected target project."))
        dependency_key = (kind, include.casefold())
        if kind in tags and include:
            supplied_dependencies.add(dependency_key)
        if root is not None and kind in tags and include and dependency_key not in declared_dependencies:
            issues.append(_issue(ISSUE_GM31_DEPENDENCY_NOT_IN_PROJECT, f"{field}.include", "The dependency was not found in the selected project readback.", kind=kind))
        declared_version = declared_dependencies.get(dependency_key)
        if declared_version is not None and declared_version != version:
            issues.append(_issue(ISSUE_GM31_DEPENDENCY_VERSION_DRIFT, f"{field}.version", "Dependency version does not match the selected project declaration.", declared_version=declared_version, supplied_version=version))
        dependency_artifact: dict[str, Any] = {}
        if receipt.get("path") or receipt.get("sha256"):
            dependency_artifact, dependency_artifact_issues = _read_exact_file(receipt, field=field, issue_code=ISSUE_GM31_DEPENDENCY_INVALID)
            issues.extend(dependency_artifact_issues)
        dependency_metadata.append({"kind": kind, "include": include, "version": version, "owner_project_path": str(owner or ""), "sequence": sequence, "artifact": dependency_artifact})
    if root is not None and supplied_dependencies != set(declared_dependencies):
        issues.append(_issue(ISSUE_GM31_DEPENDENCY_SET_MISMATCH, "dependency_receipts", "Dependency receipts must equal the exact dependency declarations in the selected project; an empty set is valid only for a genuinely dependency-free project."))

    generated_values = (
        list(generated_file_receipts)
        if isinstance(generated_file_receipts, Sequence)
        and not isinstance(generated_file_receipts, (str, bytes, bytearray))
        else []
    )
    if not generated_values or len(generated_values) > MAX_GENERATED_FILES:
        issues.append(_issue(ISSUE_GM31_INCLUSION_INVALID, "generated_file_receipts", "Generated-file receipts exceed the bounded maximum."))
    issues.extend(
        _duplicate_receipt_issues(
            generated_values[:MAX_GENERATED_FILES],
            "generated_file_receipts",
            ISSUE_GM31_RECEIPT_DUPLICATE,
            ("path",),
        )
    )
    inclusion_metadata: list[dict[str, Any]] = []
    for index, receipt in enumerate(generated_values[:MAX_GENERATED_FILES]):
        field = f"generated_file_receipts[{index}]"
        if not isinstance(receipt, Mapping):
            issues.append(_issue(ISSUE_GM31_INCLUSION_INVALID, field, "Generated-file receipt must be an object."))
            continue
        generated_file, generated_issues = _read_exact_file(receipt, field=field, issue_code=ISSUE_GM31_INCLUSION_INVALID)
        issues.extend(generated_issues)
        sequence = _sequence(receipt, field, ISSUE_GM31_INCLUSION_INVALID, issues)
        if sequence is not None:
            prerequisite_sequences.append(sequence)
        if not _same_path(receipt.get("owner_project_path"), expected_path):
            issues.append(_issue(ISSUE_GM31_INCLUSION_OWNER_MISMATCH, f"{field}.owner_project_path", "Generated-file ownership does not match the selected target project."))
        mode = str(receipt.get("inclusion_mode") or "").strip().lower()
        generated_path = Path(str(receipt.get("path") or ""))
        try:
            relative = str(generated_path.resolve().relative_to(expected_path.resolve().parent))
        except (OSError, ValueError):
            relative = ""
            issues.append(_issue(ISSUE_GM31_INCLUSION_INVALID, f"{field}.path", "Generated files must be inside the selected project directory."))
        if mode == "explicit_compile_include":
            compile_include = str(receipt.get("compile_include") or relative).strip()
            if root is not None and (
                not compile_include
                or not _project_has_item(root, "Compile", compile_include, project_path=expected_path)
            ):
                issues.append(_issue(ISSUE_GM31_EXPLICIT_COMPILE_MISSING, f"{field}.compile_include", "The exact explicit Compile Include was not found in project readback."))
        elif mode == "sdk_default_compile":
            if root is not None and (
                not relative
                or not _sdk_default_includes(root, relative, project_path=expected_path)
            ):
                issues.append(_issue(ISSUE_GM31_SDK_DEFAULT_UNAVAILABLE, f"{field}.inclusion_mode", "SDK default compile inclusion is not active for this file."))
        else:
            issues.append(_issue(ISSUE_GM31_INCLUSION_INVALID, f"{field}.inclusion_mode", "Inclusion mode must be explicit_compile_include or sdk_default_compile."))
        inclusion_metadata.append({**generated_file, "owner_project_path": str(receipt.get("owner_project_path") or ""), "inclusion_mode": mode, "relative_path": relative, "sequence": sequence})

    readback_file, readback_issues = _read_exact_file(project_readback_receipt, field="project_readback_receipt", issue_code=ISSUE_GM31_PROJECT_READBACK_INVALID)
    issues.extend(readback_issues)
    readback_sequence = _sequence(project_readback_receipt, "project_readback_receipt", ISSUE_GM31_PROJECT_READBACK_INVALID, issues)
    if not _same_path(project_readback_receipt.get("path"), expected_path):
        issues.append(_issue(ISSUE_GM31_PROJECT_READBACK_INVALID, "project_readback_receipt.path", "Project readback must name the exact target project."))
    if project_file["readback_sha256"] and readback_file["readback_sha256"] and project_file["readback_sha256"] != readback_file["readback_sha256"]:
        issues.append(_issue(ISSUE_GM31_PROJECT_HASH_MISMATCH, "project_readback_receipt.sha256", "Target project and project readback hashes differ."))
    if readback_sequence is not None:
        if prerequisite_sequences and readback_sequence <= max(prerequisite_sequences):
            issues.append(_issue(ISSUE_GM31_EVIDENCE_ORDER_INVALID, "project_readback_receipt.sequence", "Project readback must follow project, dependency, and inclusion evidence."))
        prerequisite_sequences.append(readback_sequence)

    invocation_sequence = _sequence(build_invocation_receipt, "build_invocation_receipt", ISSUE_GM31_BUILD_RECEIPT_INVALID, issues)
    invocation_call_id = _call_id(build_invocation_receipt, "build_invocation_receipt", ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID, issues)
    invocation_timestamp = _timestamp(build_invocation_receipt, "build_invocation_receipt", ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID, issues)
    command = build_invocation_receipt.get("command")
    producer = str(build_invocation_receipt.get("producer") or "").strip()
    if not producer or not isinstance(command, Sequence) or isinstance(command, (str, bytes)) or not command:
        issues.append(_issue(ISSUE_GM31_BUILD_RECEIPT_INVALID, "build_invocation_receipt", "Build invocation requires a producer and argument-vector receipt."))
    if not _same_path(build_invocation_receipt.get("project_path"), expected_path):
        issues.append(_issue(ISSUE_GM31_BUILD_RECEIPT_INVALID, "build_invocation_receipt.project_path", "Build invocation must target the exact selected project."))
    if invocation_sequence is not None and prerequisite_sequences and invocation_sequence <= max(prerequisite_sequences):
        issues.append(_issue(ISSUE_GM31_EVIDENCE_ORDER_INVALID, "build_invocation_receipt.sequence", "Build invocation cannot precede project, dependency, inclusion, and readback evidence."))

    output_sequence = _sequence(build_output_receipt, "build_output_receipt", ISSUE_GM31_BUILD_RECEIPT_INVALID, issues)
    output_call_id = _call_id(build_output_receipt, "build_output_receipt", ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID, issues)
    output_timestamp = _timestamp(build_output_receipt, "build_output_receipt", ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID, issues)
    result_id = str(build_output_receipt.get("result_id") or build_output_receipt.get("command_result_id") or "").strip()
    exit_code = build_output_receipt.get("exit_code")
    output_artifact_receipt = build_output_receipt.get("output_receipt")
    if not isinstance(output_artifact_receipt, Mapping):
        output_path = str(build_output_receipt.get("output_path") or "").strip()
        output_hash = build_output_receipt.get("output_sha256")
        output_artifact_receipt = {"path": output_path, "sha256": output_hash}
    output_artifact, output_artifact_issues = _read_exact_file(
        output_artifact_receipt,
        field="build_output_receipt.output_receipt",
        issue_code=ISSUE_GM31_BUILD_RECEIPT_INVALID,
    )
    issues.extend(output_artifact_issues)
    if output_call_id != invocation_call_id or not result_id or isinstance(exit_code, bool) or not isinstance(exit_code, int):
        issues.append(_issue(ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID, "build_output_receipt", "Build output requires one correlated call_id, a result_id, and a typed exit code; caller status or exit0 alone is not evidence."))
        issues.append(_issue(ISSUE_GM31_BUILD_RECEIPT_INVALID, "build_output_receipt", "Build output receipt correlation is invalid."))
    invocation_time = _timestamp_value(invocation_timestamp)
    output_time = _timestamp_value(output_timestamp)
    if invocation_time and output_time and output_time < invocation_time:
        issues.append(_issue(ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID, "build_output_receipt.timestamp", "Build output timestamp cannot precede invocation timestamp."))
    if invocation_sequence is not None and output_sequence is not None and output_sequence <= invocation_sequence:
        issues.append(_issue(ISSUE_GM31_EVIDENCE_ORDER_INVALID, "build_output_receipt.sequence", "Build output must follow its invocation."))
    if isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0:
        issues.append(_issue(ISSUE_GM31_BUILD_FAILED, "build_output_receipt.exit_code", "A failed build cannot authorize completion.", exit_code=exit_code))

    completion_sequence: int | None = None
    if completion_requested:
        if completion_receipt is None:
            issues.append(_issue(ISSUE_GM31_COMPLETION_PREMATURE, "completion_receipt", "Completion requires an explicit receipt after successful build output."))
        else:
            completion_sequence = _sequence(completion_receipt, "completion_receipt", ISSUE_GM31_COMPLETION_PREMATURE, issues)
            if completion_sequence is not None and output_sequence is not None and completion_sequence <= output_sequence:
                issues.append(_issue(ISSUE_GM31_COMPLETION_PREMATURE, "completion_receipt.sequence", "Completion cannot precede build output receipt."))
            completion_call_id = _call_id(completion_receipt, "completion_receipt", ISSUE_GM31_COMPLETION_PREMATURE, issues)
            _timestamp(completion_receipt, "completion_receipt", ISSUE_GM31_COMPLETION_PREMATURE, issues)
            if completion_call_id != invocation_call_id:
                issues.append(_issue(ISSUE_GM31_COMPLETION_PREMATURE, "completion_receipt.invocation_id", "Completion must correlate to the verified build invocation."))

    completion_authorized = completion_requested and not issues
    return _finish(
        issues,
        {
            "schema_version": SCHEMA_VERSION,
            "contract_id": GM31_CONTRACT_ID,
            "operation": "verify_project_build_receipts",
            "expected_project_path": expected_text,
            "target_project": project_file,
            "dependencies": dependency_metadata,
            "generated_files": inclusion_metadata,
            "project_readback": readback_file,
            "receipt_order": {
                "project": project_sequence,
                "dependencies": [item["sequence"] for item in dependency_metadata],
                "inclusions": [item["sequence"] for item in inclusion_metadata],
                "project_readback": readback_sequence,
                "build_invocation": invocation_sequence,
                "build_output": output_sequence,
                "completion": completion_sequence,
            },
            "build": {"call_id": invocation_call_id, "result_id": result_id, "exit_code": exit_code, "output": output_artifact},
            "completion_requested": completion_requested,
            "completion_authorized": completion_authorized,
            "build_executed_by_module": False,
            "execution_correlated_build_receipt": not any(item["code"] == ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID for item in issues),
            "dependency_free_project_allowed": not declared_dependencies and not supplied_dependencies,
            "discovery_performed": False,
        },
    )


def _forbidden_discovery_issues(value: Any, field: str = "inputs") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key).strip().lower()
            nested_field = f"{field}.{key}"
            if key_text in _FORBIDDEN_DISCOVERY_KEYS:
                issues.append(_issue(ISSUE_GM32_DISCOVERY_INPUT_FORBIDDEN, nested_field, "Root scans, candidate lists, history, and multi-version discovery are forbidden."))
            issues.extend(_forbidden_discovery_issues(nested, nested_field))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, nested in enumerate(value):
            issues.extend(_forbidden_discovery_issues(nested, f"{field}[{index}]"))
    return issues


def _capabilities(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return {str(key).strip().casefold() for key, enabled in value.items() if enabled is True}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return {str(item).strip().casefold() for item in value if str(item).strip()}
    return set()


def _object_keys(value: Any) -> set[tuple[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return set()
    return {
        (
            str(item.get("object_name") or item.get("name") or "").strip().casefold(),
            str(item.get("object_type") or item.get("type") or "").strip().casefold().lstrip("."),
        )
        for item in value
        if isinstance(item, Mapping)
    }


def _gm32_provenance_issues(
    receipt: Mapping[str, Any],
    *,
    field: str,
    call_id: str,
    requested_pbl: Mapping[str, Any] | None = None,
    requested_objects: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    provenance = receipt.get("verifier_provenance")
    if not isinstance(provenance, Mapping):
        issues.append(_issue(ISSUE_GM32_VERIFIER_PROVENANCE_INVALID, field, "A runtime-invoked host/tool verifier provenance receipt is required."))
        provenance = {}
    producer = str(provenance.get("producer") or provenance.get("producer_name") or "").strip().casefold()
    kind = str(provenance.get("kind") or provenance.get("receipt_kind") or "").strip().casefold()
    capabilities = _capabilities(provenance.get("capabilities") or provenance.get("capability"))
    provenance_call_id = str(provenance.get("call_id") or "").strip()
    receipt_id = str(provenance.get("receipt_id") or provenance.get("host_receipt_id") or "").strip()
    if producer not in _ALLOWED_GM32_PRODUCERS:
        issues.append(_issue(ISSUE_GM32_VERIFIER_PROVENANCE_INVALID, f"{field}.verifier_provenance.producer", "Verifier provenance producer is not an allowed PB migration host."))
    if kind not in _ALLOWED_GM32_PROVENANCE_KINDS or provenance.get("runtime_invoked") is not True:
        issues.append(_issue(ISSUE_GM32_VERIFIER_PROVENANCE_INVALID, f"{field}.verifier_provenance.kind", "Verifier provenance must identify a runtime-invoked host/tool receipt."))
    if not receipt_id or provenance_call_id != call_id:
        issues.append(_issue(ISSUE_GM32_EXECUTION_CORRELATION_INVALID, f"{field}.verifier_provenance.call_id", "Verifier provenance must carry a host receipt id and the exact tool call_id."))
    if not _REQUIRED_GM32_CAPABILITIES.issubset(capabilities):
        issues.append(_issue(ISSUE_GM32_TOOL_CAPABILITY_INVALID, f"{field}.verifier_provenance.capabilities", "Verifier provenance must advertise PB export, parse, and read-back capabilities."))

    semantic = receipt.get("command_semantics") or receipt.get("script_semantics")
    if not isinstance(semantic, Mapping):
        issues.append(_issue(ISSUE_GM32_COMMAND_SEMANTICS_INVALID, f"{field}.command_semantics", "A structured command or script semantic receipt is required."))
        return issues
    operation = str(semantic.get("operation") or "").strip().casefold()
    actual_path = str(semantic.get("pbl_path") or semantic.get("source_pbl_path") or "").strip()
    actual_hash = _normalized_hash(semantic.get("pbl_sha256") or semantic.get("source_pbl_sha256"))
    expected_path = str(requested_pbl.get("path") or "") if isinstance(requested_pbl, Mapping) else ""
    expected_hash = _normalized_hash(requested_pbl.get("sha256")) if isinstance(requested_pbl, Mapping) else ""
    expected_keys = _object_keys(requested_objects)
    actual_keys = _object_keys(semantic.get("requested_objects"))
    if operation not in {"export_pb_objects", "export_pbl_objects"}:
        issues.append(_issue(ISSUE_GM32_COMMAND_SEMANTICS_INVALID, f"{field}.command_semantics.operation", "The runtime command must identify PB object export."))
    if expected_path and (not _same_path(actual_path, expected_path) or actual_hash != expected_hash):
        issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, f"{field}.command_semantics.pbl_path", "Command semantics must bind to the exact requested PBL path and byte hash."))
    if expected_keys and actual_keys != expected_keys:
        issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, f"{field}.command_semantics.requested_objects", "Command semantics must bind to the exact requested PB object set."))
    command = receipt.get("command")
    if not isinstance(command, Sequence) or isinstance(command, (str, bytes, bytearray)) or not command:
        issues.append(_issue(ISSUE_GM32_COMMAND_SEMANTICS_INVALID, f"{field}.command", "The runtime invocation must include a non-empty argument vector."))
    else:
        command_text = " ".join(str(item) for item in command).casefold()
        if expected_path and str(expected_path).casefold() not in command_text:
            issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, f"{field}.command", "The runtime command must contain the exact requested PBL path."))
        for object_name, object_type in expected_keys:
            if object_name not in command_text or object_type not in command_text:
                issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, f"{field}.command", "The runtime command must contain every requested PB object name and type."))
                break
    return issues


def _pb_export_structure_issues(
    path: Any, *, object_name: str, object_type: str, field: str
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        payload = Path(str(path)).read_bytes()
    except OSError:
        payload = b""
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header = lines[0] if lines else ""
    if not re.fullmatch(r"\$PBExportHeader\$[^\r\n]+", header) or "$PBExportEnd$" not in lines:
        issues.append(_issue(ISSUE_GM32_EXPORT_STRUCTURE_INVALID, field, "Exported PB content must contain a PBExportHeader and PBExportEnd marker."))
        return issues
    header_name = header.split("$", 2)[-1]
    if Path(header_name).stem.casefold() != object_name.casefold() or Path(header_name).suffix.casefold() != f".{object_type.casefold().lstrip('.')}":
        issues.append(_issue(ISSUE_GM32_EXPORT_STRUCTURE_INVALID, f"{field}.header", "PB export header must identify the exact requested object and type."))
    body = text.casefold()
    if object_type.casefold() == "srd" and "datawindow" not in body:
        issues.append(_issue(ISSUE_GM32_EXPORT_STRUCTURE_INVALID, field, "SRD content must contain a DataWindow export body."))
    if object_type.casefold() in {"srw", "sru"} and "global type" not in body:
        issues.append(_issue(ISSUE_GM32_EXPORT_STRUCTURE_INVALID, field, "SRW/SRU content must contain a global type export body."))
    return issues


def _pe_image_issues(path: Any, field: str) -> list[dict[str, Any]]:
    try:
        payload = Path(str(path)).read_bytes()
    except OSError:
        payload = b""
    if len(payload) < 64 or payload[:2] != b"MZ":
        return [_issue(ISSUE_GM32_ORCA_RUNTIME_UNUSABLE, field, "The selected runtime library is not a readable PE image.")]
    pe_offset = int.from_bytes(payload[0x3C:0x40], "little")
    if pe_offset < 0x40 or pe_offset + 4 > len(payload) or payload[pe_offset:pe_offset + 4] != b"PE\0\0":
        return [_issue(ISSUE_GM32_ORCA_RUNTIME_UNUSABLE, field, "The selected runtime library has no valid PE signature.")]
    return []


def _tool_execution_evidence(
    receipt: Mapping[str, Any], field: str, issue_code: str
) -> tuple[str, str, dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    call_id = _call_id(receipt, field, issue_code, issues)
    timestamp = _timestamp(receipt, field, issue_code, issues)
    output_receipt = receipt.get("output_receipt")
    if not isinstance(output_receipt, Mapping):
        output_receipt = {
            "path": receipt.get("output_path"),
            "sha256": receipt.get("output_sha256"),
        }
    output, output_issues = _read_exact_file(
        output_receipt,
        field=f"{field}.output_receipt",
        issue_code=issue_code,
    )
    issues.extend(output_issues)
    output_call_id = str(output_receipt.get("call_id") or receipt.get("output_call_id") or call_id).strip()
    result_id = str(receipt.get("result_id") or output_receipt.get("result_id") or "").strip()
    exit_code = receipt.get("exit_code", output_receipt.get("exit_code"))
    if output_call_id != call_id or not result_id or isinstance(exit_code, bool) or not isinstance(exit_code, int) or exit_code != 0:
        issues.append(_issue(issue_code, f"{field}.output_receipt", "Tool selection requires a correlated call_id, result_id, zero exit code, and a byte-hash-verified output receipt; status/verified alone is not evidence."))
    return call_id, timestamp, {"output": output, "result_id": result_id, "exit_code": exit_code}, issues


def _runtime_output_manifest_issues(
    receipt: Mapping[str, Any],
    *,
    field: str,
    output: Mapping[str, Any],
    requested_pbl: Mapping[str, Any] | None,
    requested_objects: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        payload = json.loads(Path(str(output.get("path") or "")).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    if not isinstance(payload, Mapping) or payload.get("receipt_type") != "pb_export_runtime_receipt":
        return [_issue(ISSUE_GM32_VERIFIER_PROVENANCE_INVALID, f"{field}.output_receipt", "Tool output must be a structured PB export runtime receipt, not arbitrary output bytes.")]
    if payload.get("runtime_invoked") is not True:
        issues.append(_issue(ISSUE_GM32_VERIFIER_PROVENANCE_INVALID, f"{field}.output_receipt.runtime_invoked", "Tool output must record runtime invocation."))
    call_id = str(receipt.get("call_id") or "").strip()
    if str(payload.get("call_id") or "").strip() != call_id:
        issues.append(_issue(ISSUE_GM32_EXECUTION_CORRELATION_INVALID, f"{field}.output_receipt.call_id", "Tool output receipt must correlate to the selected host call_id."))
    expected_path = str(requested_pbl.get("path") or "") if isinstance(requested_pbl, Mapping) else ""
    expected_hash = _normalized_hash(requested_pbl.get("sha256")) if isinstance(requested_pbl, Mapping) else ""
    if expected_path and (not _same_path(payload.get("pbl_path"), expected_path) or _normalized_hash(payload.get("pbl_sha256")) != expected_hash):
        issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, f"{field}.output_receipt.pbl_path", "Tool output receipt must bind to the exact requested PBL path and byte hash."))
    if _object_keys(payload.get("requested_objects")) != _object_keys(requested_objects):
        issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, f"{field}.output_receipt.requested_objects", "Tool output receipt must bind to the exact requested PB object set."))
    manifest = payload.get("exported_objects")
    if not isinstance(manifest, Sequence) or isinstance(manifest, (str, bytes, bytearray)) or not manifest:
        issues.append(_issue(ISSUE_GM32_EXPORT_RECEIPT_INVALID, f"{field}.output_receipt.exported_objects", "Tool output receipt must list every exported object and its exact hash."))
    else:
        expected_manifest = receipt.get("exported_objects")
        def manifest_key(item: Any) -> tuple[str, str, str]:
            if not isinstance(item, Mapping):
                return ("", "", "")
            return (
                str(item.get("path") or "").casefold(),
                _normalized_hash(item.get("sha256") or item.get("readback_sha256")),
                f"{str(item.get('object_name') or '').casefold()}:{str(item.get('object_type') or '').casefold().lstrip('.')}",
            )
        if not isinstance(expected_manifest, Sequence) or isinstance(expected_manifest, (str, bytes, bytearray)) or {
            manifest_key(item) for item in manifest
        } != {manifest_key(item) for item in expected_manifest}:
            issues.append(_issue(ISSUE_GM32_OUTPUT_HASH_INVALID, f"{field}.output_receipt.exported_objects", "Tool output manifest must match every selected export path, object identity, and exact SHA-256."))
    issues.extend(
        _gm32_provenance_issues(
            payload,
            field=f"{field}.output_receipt",
            call_id=str(receipt.get("call_id") or "").strip(),
            requested_pbl=requested_pbl,
            requested_objects=requested_objects,
        )
    )
    return issues


def _usable_tool(
    receipt: Mapping[str, Any],
    *,
    requested_pbl: Mapping[str, Any] | None = None,
    requested_objects: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    artifact, issues = _read_exact_file(receipt, field="pblscripter", issue_code=ISSUE_GM32_PBLSCRIPTER_UNUSABLE)
    tool_id = str(receipt.get("tool_id") or "").strip().casefold()
    tool_version = str(receipt.get("tool_version") or "").strip()
    receipt_id = str(receipt.get("receipt_id") or "").strip()
    kind = str(receipt.get("tool_kind") or receipt.get("kind") or "").strip().lower()
    suffix = Path(str(receipt.get("path") or "")).suffix.casefold()
    capabilities = _capabilities(receipt.get("capabilities"))
    if tool_id not in {"pblscripter", "export-pbl"} or not tool_version or not receipt_id:
        issues.append(_issue(ISSUE_GM32_TOOL_IDENTITY_INVALID, "pblscripter", "The selected tool needs an explicit supported tool id, version, and receipt id."))
    if kind not in {"executable", "script"} or (kind == "executable" and suffix != ".exe") or (kind == "script" and suffix != ".ps1"):
        issues.append(_issue(ISSUE_GM32_PBLSCRIPTER_UNUSABLE, "pblscripter.kind", "The selected PblScripter kind must match the supplied artifact type."))
    if not capabilities.intersection({"pbl_export", "export_pbl", "export"}):
        issues.append(_issue(ISSUE_GM32_TOOL_CAPABILITY_INVALID, "pblscripter.capabilities", "The selected tool must explicitly advertise PBL export capability."))
    if receipt.get("usable") is False:
        issues.append(_issue(ISSUE_GM32_PBLSCRIPTER_UNUSABLE, "pblscripter.usable", "The supplied tool is explicitly unusable."))
    call_id, timestamp, execution, execution_issues = _tool_execution_evidence(
        receipt, "pblscripter", ISSUE_GM32_EXECUTION_CORRELATION_INVALID
    )
    issues.extend(execution_issues)
    issues.extend(
        _gm32_provenance_issues(
            receipt,
            field="pblscripter",
            call_id=call_id,
            requested_pbl=requested_pbl,
            requested_objects=requested_objects,
        )
    )
    if kind == "script":
        try:
            script_text = Path(str(receipt.get("path") or "")).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            script_text = ""
        script_text_casefold = script_text.casefold()
        semantic_text = " ".join(
            [
                str(requested_pbl.get("path") or "") if isinstance(requested_pbl, Mapping) else "",
                *(
                    token
                    for item in (requested_objects or ())
                    if isinstance(item, Mapping)
                    for token in (
                        str(item.get("object_name") or item.get("name") or ""),
                        str(item.get("object_type") or item.get("type") or "").lstrip("."),
                    )
                ),
            ]
        ).casefold()
        if "export" not in script_text_casefold or "pbl" not in script_text_casefold or any(
            token and token not in script_text_casefold for token in semantic_text.split()
        ):
            issues.append(_issue(ISSUE_GM32_TOOL_IDENTITY_INVALID, "pblscripter.path", "The PblScripter script must contain the bound export operation, exact PBL path, and requested object names."))
    exported_values = receipt.get("exported_objects")
    if not isinstance(exported_values, Sequence) or isinstance(exported_values, (str, bytes, bytearray)):
        issues.append(_issue(ISSUE_GM32_EXPORT_RECEIPT_INVALID, "pblscripter.exported_objects", "A selected tool must provide structured read-back receipts for every exported PB object."))
    else:
        _, export_issues = _usable_exports(
            exported_values,
            requested_pbl=requested_pbl,
            requested_objects=requested_objects,
        )
        issues.extend(export_issues)
    issues.extend(
        _runtime_output_manifest_issues(
            receipt,
            field="pblscripter",
            output=execution["output"],
            requested_pbl=requested_pbl,
            requested_objects=requested_objects,
        )
    )
    artifact.update({"tool_id": tool_id, "tool_version": tool_version, "receipt_id": receipt_id, "kind": kind, "capabilities": sorted(capabilities), "call_id": call_id, "timestamp": timestamp, **execution})
    return artifact, issues


def _usable_orca(
    receipt: Mapping[str, Any],
    *,
    requested_pbl: Mapping[str, Any] | None = None,
    requested_objects: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    version = str(receipt.get("selected_version") or "").strip()
    tool_id = str(receipt.get("tool_id") or "").strip().casefold()
    tool_version = str(receipt.get("tool_version") or "").strip()
    receipt_id = str(receipt.get("receipt_id") or "").strip()
    kind = str(receipt.get("tool_kind") or receipt.get("kind") or "runtime").strip().lower()
    capabilities = _capabilities(receipt.get("capabilities"))
    if tool_id not in {"orca", "powerbuilder-orca"} or not tool_version or not receipt_id:
        issues.append(_issue(ISSUE_GM32_TOOL_IDENTITY_INVALID, "orca_runtime", "The selected ORCA runtime needs an explicit supported tool id, version, and receipt id."))
    if not version or any(char in version for char in ",;|*") or version != tool_version:
        issues.append(_issue(ISSUE_GM32_ORCA_SELECTION_INVALID, "orca_runtime.selected_version", "Exactly one explicit ORCA runtime version is required."))
    if kind not in {"runtime", "library", "orca"}:
        issues.append(_issue(ISSUE_GM32_ORCA_RUNTIME_UNUSABLE, "orca_runtime.kind", "The selected ORCA kind must identify a runtime artifact."))
    if not capabilities.intersection({"pbl_export", "export_pbl", "export", "orca_export"}):
        issues.append(_issue(ISSUE_GM32_TOOL_CAPABILITY_INVALID, "orca_runtime.capabilities", "The selected ORCA runtime must explicitly advertise PBL export capability."))
    call_id, timestamp, execution, execution_issues = _tool_execution_evidence(
        receipt, "orca_runtime", ISSUE_GM32_EXECUTION_CORRELATION_INVALID
    )
    issues.extend(execution_issues)
    issues.extend(
        _gm32_provenance_issues(
            receipt,
            field="orca_runtime",
            call_id=call_id,
            requested_pbl=requested_pbl,
            requested_objects=requested_objects,
        )
    )
    library_receipt = receipt.get("orca_library")
    if not isinstance(library_receipt, Mapping):
        issues.append(_issue(ISSUE_GM32_ORCA_RUNTIME_UNUSABLE, "orca_runtime.orca_library", "One explicit ORCA library receipt is required."))
        library = {}
    else:
        library, library_issues = _read_exact_file(library_receipt, field="orca_runtime.orca_library", issue_code=ISSUE_GM32_ORCA_RUNTIME_UNUSABLE)
        issues.extend(library_issues)
        issues.extend(_pe_image_issues(library_receipt.get("path"), "orca_runtime.orca_library"))
    runtime_values = receipt.get("runtime_libraries", ())
    runtime_libraries: list[dict[str, Any]] = []
    if not isinstance(runtime_values, Sequence) or isinstance(runtime_values, (str, bytes)) or not runtime_values or len(runtime_values) > MAX_RUNTIME_LIBRARIES:
        issues.append(_issue(ISSUE_GM32_ORCA_RUNTIME_UNUSABLE, "orca_runtime.runtime_libraries", "A bounded explicit runtime-library list is required."))
        runtime_values = ()
    for index, item in enumerate(runtime_values):
        if not isinstance(item, Mapping):
            issues.append(_issue(ISSUE_GM32_ORCA_RUNTIME_UNUSABLE, f"orca_runtime.runtime_libraries[{index}]", "Runtime library receipt must be an object."))
            continue
        artifact, artifact_issues = _read_exact_file(item, field=f"orca_runtime.runtime_libraries[{index}]", issue_code=ISSUE_GM32_ORCA_RUNTIME_UNUSABLE)
        runtime_libraries.append(artifact)
        issues.extend(artifact_issues)
        issues.extend(_pe_image_issues(item.get("path"), f"orca_runtime.runtime_libraries[{index}]"))
    exported_values = receipt.get("exported_objects")
    if not isinstance(exported_values, Sequence) or isinstance(exported_values, (str, bytes, bytearray)):
        issues.append(_issue(ISSUE_GM32_EXPORT_RECEIPT_INVALID, "orca_runtime.exported_objects", "A selected runtime must provide structured read-back receipts for every exported PB object."))
    else:
        _, export_issues = _usable_exports(
            exported_values,
            requested_pbl=requested_pbl,
            requested_objects=requested_objects,
        )
        issues.extend(export_issues)
    issues.extend(
        _runtime_output_manifest_issues(
            receipt,
            field="orca_runtime",
            output=execution["output"],
            requested_pbl=requested_pbl,
            requested_objects=requested_objects,
        )
    )
    return {"selected_version": version, "tool_id": tool_id, "tool_version": tool_version, "receipt_id": receipt_id, "kind": kind, "capabilities": sorted(capabilities), "call_id": call_id, "timestamp": timestamp, **execution, "orca_library": library, "runtime_libraries": runtime_libraries}, issues


def _requested_scope(
    requested_pbl: Mapping[str, Any] | None,
    requested_objects: Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], set[tuple[str, str]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    pbl_metadata: dict[str, Any] = {}
    if not isinstance(requested_pbl, Mapping):
        issues.append(_issue(ISSUE_GM32_REQUESTED_PBL_INVALID, "requested_pbl", "One exact requested PBL path and SHA-256 receipt is required."))
    else:
        pbl_metadata, pbl_issues = _read_exact_file(requested_pbl, field="requested_pbl", issue_code=ISSUE_GM32_REQUESTED_PBL_INVALID)
        issues.extend(pbl_issues)
        if Path(str(requested_pbl.get("path") or "")).suffix.casefold() != ".pbl":
            issues.append(_issue(ISSUE_GM32_REQUESTED_PBL_INVALID, "requested_pbl.path", "The requested source must be an explicit .pbl file."))
    object_values = (
        list(requested_objects)
        if isinstance(requested_objects, Sequence)
        and not isinstance(requested_objects, (str, bytes, bytearray))
        else []
    )
    if not object_values or len(object_values) > MAX_EXPORTED_OBJECTS:
        issues.append(_issue(ISSUE_GM32_REQUESTED_OBJECT_SET_INVALID, "requested_objects", "A bounded non-empty requested PB object set is required."))
    object_metadata: list[dict[str, Any]] = []
    object_keys: set[tuple[str, str]] = set()
    for index, item in enumerate(object_values[:MAX_EXPORTED_OBJECTS]):
        field = f"requested_objects[{index}]"
        if not isinstance(item, Mapping):
            issues.append(_issue(ISSUE_GM32_REQUESTED_OBJECT_SET_INVALID, field, "Requested PB objects must be objects with name and type."))
            continue
        name = str(item.get("object_name") or item.get("name") or "").strip()
        object_type = str(item.get("object_type") or item.get("type") or "").strip().casefold().lstrip(".")
        object_path = str(item.get("path") or item.get("object_path") or "").strip()
        key = (name.casefold(), object_type)
        if not name or not object_type or key in object_keys:
            issues.append(_issue(ISSUE_GM32_REQUESTED_OBJECT_SET_INVALID, field, "Requested PB object names and types must be non-empty and unique."))
            continue
        if object_path and not Path(object_path).is_absolute():
            issues.append(_issue(ISSUE_GM32_REQUESTED_OBJECT_SET_INVALID, f"{field}.path", "Requested object paths must be absolute when supplied."))
        object_keys.add(key)
        object_metadata.append({"object_name": name, "object_type": object_type, "path": object_path})
    return pbl_metadata, object_metadata, object_keys, issues


def _usable_exports(
    receipts: Sequence[Mapping[str, Any]],
    *,
    requested_pbl: Mapping[str, Any] | None,
    requested_objects: Sequence[Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    if not receipts or len(receipts) > MAX_EXPORTED_OBJECTS:
        issues.append(_issue(ISSUE_GM32_EXPORT_RECEIPT_INVALID, "exported_objects", "A non-empty bounded exported-object list is required."))
        return artifacts, issues
    pbl_metadata, object_metadata, requested_keys, scope_issues = _requested_scope(requested_pbl, requested_objects)
    issues.extend(scope_issues)
    expected_pbl_path = str(pbl_metadata.get("path") or "")
    expected_pbl_hash = _normalized_hash(pbl_metadata.get("readback_sha256"))
    issues.extend(_duplicate_receipt_issues(receipts, "exported_objects", ISSUE_GM32_RECEIPT_DUPLICATE, ("path",)))
    issues.extend(_duplicate_receipt_issues(receipts, "exported_objects", ISSUE_GM32_RECEIPT_DUPLICATE, ("object_name", "object_type")))
    batch_ids: set[str] = set()
    source_hashes: set[str] = set()
    call_ids: set[str] = set()
    export_keys: set[tuple[str, str]] = set()
    for index, receipt in enumerate(receipts):
        field = f"exported_objects[{index}]"
        if not isinstance(receipt, Mapping):
            issues.append(_issue(ISSUE_GM32_EXPORT_RECEIPT_INVALID, field, "Export receipt must be an object."))
            continue
        artifact, artifact_issues = _read_exact_file(receipt, field=field, issue_code=ISSUE_GM32_EXPORT_RECEIPT_INVALID, hash_field="readback_sha256")
        issues.extend(artifact_issues)
        if not artifact["readback_sha256"] or artifact["requested_sha256"] != artifact["readback_sha256"]:
            issues.append(_issue(ISSUE_GM32_OUTPUT_HASH_INVALID, f"{field}.readback_sha256", "The exported object output must match the current bytes at its exact path."))
        suffix = Path(str(receipt.get("path") or "")).suffix.casefold()
        authority = str(receipt.get("authority") or "").strip()
        batch_id = str(receipt.get("export_batch_id") or "").strip()
        source_hash = _normalized_hash(receipt.get("exported_from_sha256"))
        source_path = str(receipt.get("source_pbl_path") or receipt.get("pbl_path") or "").strip()
        object_name = str(receipt.get("object_name") or "").strip()
        object_type = str(receipt.get("object_type") or "").strip().casefold().lstrip(".")
        call_id = str(receipt.get("call_id") or "").strip()
        timestamp = _timestamp(receipt, field, ISSUE_GM32_EXECUTION_CORRELATION_INVALID, issues)
        if suffix not in {".srd", ".srw", ".sru"}:
            issues.append(_issue(ISSUE_GM32_EXPORT_RECEIPT_INVALID, f"{field}.path", "Only explicit SRD, SRW, and SRU object artifacts are accepted."))
        if authority != "current_export" or receipt.get("current") is not True or not batch_id or not _SHA256_RE.fullmatch(str(receipt.get("exported_from_sha256") or "").strip()):
            issues.append(_issue(ISSUE_GM32_EXPORT_NOT_CURRENT, field, "Export receipts require current_export authority, current=true, one batch id, and source SHA-256."))
        if not call_id:
            issues.append(_issue(ISSUE_GM32_EXECUTION_CORRELATION_INVALID, f"{field}.call_id", "Each export must carry a host-issued execution call_id."))
        else:
            call_ids.add(call_id)
            issues.extend(
                _gm32_provenance_issues(
                    receipt,
                    field=field,
                    call_id=call_id,
                    requested_pbl=requested_pbl,
                    requested_objects=requested_objects,
                )
            )
        if expected_pbl_path and not _same_path(source_path, expected_pbl_path):
            issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, f"{field}.source_pbl_path", "Current exports must bind to the exact requested PBL path."))
        if expected_pbl_hash and source_hash != expected_pbl_hash:
            issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, f"{field}.exported_from_sha256", "Current exports must bind to the exact requested PBL byte hash."))
        key = (object_name.casefold(), object_type)
        export_keys.add(key)
        if key not in requested_keys:
            issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, field, "Current exports must identify an object in the exact requested object set."))
        requested_item = next((item for item in object_metadata if (item["object_name"].casefold(), item["object_type"]) == key), None)
        if requested_item and requested_item.get("path") and not _same_path(receipt.get("path"), requested_item["path"]):
            issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, f"{field}.path", "The exported object path does not match the exact requested object path."))
        issues.extend(
            _pb_export_structure_issues(
                receipt.get("path"),
                object_name=object_name,
                object_type=object_type,
                field=field,
            )
        )
        if batch_id:
            batch_ids.add(batch_id)
        if source_hash:
            source_hashes.add(source_hash)
        artifacts.append({**artifact, "authority": authority, "current": receipt.get("current") is True, "export_batch_id": batch_id, "exported_from_sha256": f"sha256:{source_hash}" if source_hash else "", "source_pbl_path": source_path, "object_name": object_name, "object_type": object_type, "call_id": call_id, "timestamp": timestamp})
    if len(batch_ids) != 1 or len(source_hashes) != 1 or len(call_ids) != 1:
        issues.append(_issue(ISSUE_GM32_EXPORT_NOT_CURRENT, "exported_objects", "All current exports must share one explicit batch, source hash, and execution call_id."))
    if export_keys != requested_keys:
        issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, "exported_objects", "The current export receipt set must equal the requested PB object set."))
    return artifacts, issues


def _tool_scope_issues(
    receipt: Mapping[str, Any],
    *,
    requested_pbl: Mapping[str, Any],
    requested_objects: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    expected_path = str(requested_pbl.get("path") or "")
    expected_hash = _normalized_hash(requested_pbl.get("sha256"))
    actual_path = str(receipt.get("source_pbl_path") or receipt.get("pbl_path") or "").strip()
    actual_hash = _normalized_hash(receipt.get("source_pbl_sha256") or receipt.get("pbl_sha256"))
    if not _same_path(actual_path, expected_path) or actual_hash != expected_hash:
        issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, "selected_tool.requested_pbl", "The selected tool execution must bind to the exact requested PBL path and byte hash."))
    expected_keys = {
        (str(item.get("object_name") or item.get("name") or "").strip().casefold(), str(item.get("object_type") or item.get("type") or "").strip().casefold().lstrip("."))
        for item in requested_objects
        if isinstance(item, Mapping)
    }
    actual_values = receipt.get("requested_objects")
    actual_keys = {
        (str(item.get("object_name") or item.get("name") or "").strip().casefold(), str(item.get("object_type") or item.get("type") or "").strip().casefold().lstrip("."))
        for item in actual_values
        if isinstance(item, Mapping)
    } if isinstance(actual_values, Sequence) and not isinstance(actual_values, (str, bytes, bytearray)) else set()
    if actual_keys != expected_keys:
        issues.append(_issue(ISSUE_GM32_EXPORT_BINDING_MISMATCH, "selected_tool.requested_objects", "The selected tool execution must bind to the exact requested PB object set."))
    return issues


def plan_gm32_acquisition(
    *,
    pblscripter: Mapping[str, Any] | None = None,
    orca_runtime: Mapping[str, Any] | None = None,
    exported_objects: Sequence[Mapping[str, Any]] = (),
    requested_pbl: Mapping[str, Any] | None = None,
    requested_objects: Sequence[Mapping[str, Any]] | None = None,
) -> PreflightResult:
    """Select the first usable explicit GM-32 acquisition rung without execution."""

    inputs = {
        "pblscripter": pblscripter or {},
        "orca_runtime": orca_runtime or {},
        "exported_objects": exported_objects,
        "requested_pbl": requested_pbl or {},
        "requested_objects": requested_objects or (),
    }
    blocking_issues = _forbidden_discovery_issues(inputs)
    requested_pbl_metadata, requested_object_metadata, _, scope_issues = _requested_scope(requested_pbl, requested_objects)
    if pblscripter is not None or orca_runtime is not None or exported_objects:
        blocking_issues.extend(scope_issues)
    attempts: list[dict[str, Any]] = []
    failed_attempt_issues: list[dict[str, Any]] = []
    selected_method = ""
    selected_receipts: Any = None
    export_probe: tuple[list[dict[str, Any]], list[dict[str, Any]]] | None = None
    if exported_objects:
        export_probe = _usable_exports(
            exported_objects,
            requested_pbl=requested_pbl,
            requested_objects=requested_objects,
        )
        duplicate_codes = {ISSUE_GM32_RECEIPT_DUPLICATE}
        blocking_issues.extend(item for item in export_probe[1] if item["code"] in duplicate_codes)

    if pblscripter is not None:
        tool, tool_issues = _usable_tool(
            pblscripter,
            requested_pbl=requested_pbl,
            requested_objects=requested_object_metadata,
        )
        attempts.append({"method": "pblscripter", "usable": not tool_issues, "issue_codes": sorted({item["code"] for item in tool_issues})})
        failed_attempt_issues.extend(tool_issues)
        if not tool_issues:
            selected_method = "pblscripter"
            selected_receipts = tool
            if isinstance(requested_pbl, Mapping):
                blocking_issues.extend(_tool_scope_issues(pblscripter, requested_pbl=requested_pbl, requested_objects=requested_object_metadata))

    if not selected_method and orca_runtime is not None:
        orca, orca_issues = _usable_orca(
            orca_runtime,
            requested_pbl=requested_pbl,
            requested_objects=requested_object_metadata,
        )
        attempts.append({"method": "orca", "usable": not orca_issues, "issue_codes": sorted({item["code"] for item in orca_issues})})
        failed_attempt_issues.extend(orca_issues)
        if not orca_issues:
            selected_method = "orca"
            selected_receipts = orca
            if isinstance(requested_pbl, Mapping):
                blocking_issues.extend(_tool_scope_issues(orca_runtime, requested_pbl=requested_pbl, requested_objects=requested_object_metadata))

    if not selected_method and exported_objects:
        exports, export_issues = export_probe or ([], [_issue(ISSUE_GM32_EXPORT_RECEIPT_INVALID, "exported_objects", "Export receipts were not evaluated.")])
        attempts.append({"method": "current_exports", "usable": not export_issues, "issue_codes": sorted({item["code"] for item in export_issues})})
        failed_attempt_issues.extend(export_issues)
        if not export_issues:
            selected_method = "current_exports"
            selected_receipts = exports

    if not selected_method:
        blocking_issues.extend(failed_attempt_issues)
        blocking_issues.append(_issue(ISSUE_GM32_ACQUISITION_UNRESOLVED, "acquisition", "No usable explicit PblScripter, selected ORCA runtime, or current export receipt was supplied."))

    return _finish(
        blocking_issues,
        {
            "schema_version": SCHEMA_VERSION,
            "contract_id": GM32_CONTRACT_ID,
            "operation": "plan_explicit_acquisition",
            "ladder": ["pblscripter", "orca", "current_exports", "unresolved"],
            "attempts": attempts,
            "selected_method": selected_method or "unresolved",
            "selected_receipts": selected_receipts,
            "planned_action": {
                "pblscripter": "invoke_supplied_pblscripter_once",
                "orca": "invoke_selected_orca_version_once",
                "current_exports": "read_current_exported_objects",
            }.get(selected_method, "block"),
            "explicit_inputs_only": True,
            "root_scan_performed": False,
            "versions_tried": [],
            "behavior_inferred": False,
            "stale_exports_accepted": False,
            "executed_process_count": 0,
            "orca_executed": False,
            "request_scope": {"requested_pbl": requested_pbl_metadata, "requested_objects": requested_object_metadata},
            "execution_correlated_selection": bool(selected_method and not any(item["code"] in {ISSUE_GM32_EXECUTION_CORRELATION_INVALID, ISSUE_GM32_EXPORT_BINDING_MISMATCH} for item in blocking_issues)),
        },
    )


verify_gm31_preflight = verify_gm31_project_build_contract
plan_gm32_preflight = plan_gm32_acquisition


__all__ = [
    "GM31_CONTRACT_ID",
    "GM32_CONTRACT_ID",
    "SCHEMA_VERSION",
    "PreflightResult",
    "ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID",
    "ISSUE_GM31_DEPENDENCY_SET_MISMATCH",
    "ISSUE_GM31_DEPENDENCY_VERSION_DRIFT",
    "ISSUE_GM31_RECEIPT_DUPLICATE",
    "ISSUE_GM32_EXPORT_BINDING_MISMATCH",
    "ISSUE_GM32_EXECUTION_CORRELATION_INVALID",
    "ISSUE_GM32_OUTPUT_HASH_INVALID",
    "ISSUE_GM32_RECEIPT_DUPLICATE",
    "ISSUE_GM32_REQUESTED_OBJECT_SET_INVALID",
    "ISSUE_GM32_REQUESTED_PBL_INVALID",
    "ISSUE_GM32_TOOL_CAPABILITY_INVALID",
    "ISSUE_GM32_TOOL_IDENTITY_INVALID",
    "ISSUE_GM32_VERIFIER_PROVENANCE_INVALID",
    "ISSUE_GM32_COMMAND_SEMANTICS_INVALID",
    "ISSUE_GM32_EXPORT_STRUCTURE_INVALID",
    "verify_gm31_project_build_contract",
    "verify_gm31_preflight",
    "plan_gm32_acquisition",
    "plan_gm32_preflight",
]
