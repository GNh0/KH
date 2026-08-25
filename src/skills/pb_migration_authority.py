"""Bounded authority rules for PB-to-C# migration inputs and comparators."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

from src.contracts import HarnessResult


CONTRACT_SCHEMA_VERSION = "pb-migration-authority/v1"
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
MAX_ALLOWLIST_ENTRIES = 128
MAX_IDENTIFIER_ENTRIES = 1024
_SHA256_PATTERN = re.compile(r"^(?:sha256:)?[0-9a-fA-F]{64}$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_$#]*$")
_FORBIDDEN_METADATA_KEYS = {
    "author",
    "authors",
    "root",
    "roots",
    "history",
    "discovery",
    "discover",
    "search_root",
    "source_root",
    "repository_root",
    "similar_program",
    "similar_programs",
    "similar-program",
    "similar-programs",
}
_BROAD_SCOPE_VALUES = {"*", "all", "any", "everything", "style", "styles", "global"}
_INVENTORY_KINDS = (
    "classes",
    "types",
    "controls",
    "fields",
    "properties",
    "procedures",
    "methods",
    "events",
    "sql",
    "layout",
    "declared",
)
_COMMON_DECLARATION_IDENTIFIERS = {
    "begininit",
    "dispose",
    "endinit",
    "equals",
    "finalize",
    "form",
    "gethashcode",
    "gettype",
    "initializecomponent",
    "memberwiseclone",
    "onactivated",
    "onclosing",
    "onclosed",
    "onformclosed",
    "onformclosing",
    "onload",
    "onshown",
    "referenceequals",
    "resumelayout",
    "suspendlayout",
    "tostring",
    "wndproc",
}
_CONTROL_TYPE_SUFFIXES = (
    "button",
    "checkbox",
    "checkedlistbox",
    "column",
    "combobox",
    "control",
    "dateedit",
    "edit",
    "grid",
    "gridcontrol",
    "gridview",
    "label",
    "layoutcontrol",
    "listbox",
    "lookupedit",
    "panel",
    "repositoryitem",
    "spinedit",
    "textbox",
    "textedit",
    "treeview",
)
_CSHARP_KEYWORDS = {
    "abstract",
    "add",
    "alias",
    "as",
    "ascending",
    "async",
    "await",
    "base",
    "bool",
    "break",
    "by",
    "byte",
    "case",
    "catch",
    "char",
    "checked",
    "class",
    "const",
    "continue",
    "decimal",
    "default",
    "delegate",
    "descending",
    "do",
    "double",
    "dynamic",
    "else",
    "enum",
    "equals",
    "event",
    "explicit",
    "extern",
    "false",
    "file",
    "finally",
    "fixed",
    "float",
    "for",
    "foreach",
    "from",
    "get",
    "global",
    "goto",
    "group",
    "if",
    "implicit",
    "in",
    "init",
    "int",
    "interface",
    "internal",
    "into",
    "is",
    "join",
    "let",
    "lock",
    "long",
    "managed",
    "nameof",
    "namespace",
    "new",
    "not",
    "notnull",
    "null",
    "object",
    "on",
    "operator",
    "orderby",
    "out",
    "override",
    "params",
    "partial",
    "private",
    "protected",
    "public",
    "readonly",
    "record",
    "ref",
    "remove",
    "required",
    "return",
    "sbyte",
    "sealed",
    "select",
    "set",
    "short",
    "sizeof",
    "stackalloc",
    "static",
    "string",
    "struct",
    "switch",
    "this",
    "throw",
    "true",
    "try",
    "typeof",
    "uint",
    "ulong",
    "unchecked",
    "unmanaged",
    "unsafe",
    "ushort",
    "using",
    "value",
    "var",
    "virtual",
    "void",
    "volatile",
    "when",
    "where",
    "while",
    "with",
    "yield",
}
_FRAMEWORK_COMMON_IDENTIFIERS = {
    "argumentexception",
    "argumentnullexception",
    "button",
    "canceleventargs",
    "component",
    "containercontrol",
    "control",
    "eventargs",
    "eventhandler",
    "exception",
    "form",
    "icomponent",
    "icontainer",
    "idisposable",
    "label",
    "panel",
    "task",
    "array",
    "bool",
    "byte",
    "collection",
    "datetime",
    "dataset",
    "datatable",
    "decimal",
    "double",
    "guid",
    "int16",
    "int32",
    "int64",
    "list",
    "object",
    "single",
    "string",
    "timespan",
    "uint16",
    "uint32",
    "uint64",
    "void",
}
_SQL_KEYWORDS = {
    "begin",
    "end",
    "from",
    "join",
    "null",
    "select",
    "table",
    "where",
}
_SQL_COMMON_IDENTIFIERS = _SQL_KEYWORDS | {
    "all",
    "and",
    "as",
    "asc",
    "avg",
    "case",
    "count",
    "delete",
    "desc",
    "distinct",
    "else",
    "exists",
    "false",
    "group",
    "having",
    "if",
    "in",
    "insert",
    "is",
    "like",
    "max",
    "min",
    "not",
    "or",
    "order",
    "select",
    "sum",
    "then",
    "top",
    "union",
    "update",
    "values",
    "when",
}
_LAYOUT_IDENTIFIER_ATTRIBUTES = {
    "bindingfield",
    "column",
    "control",
    "event",
    "field",
    "fieldname",
    "handler",
    "id",
    "identifier",
    "layoutname",
    "member",
    "name",
    "property",
    "repository",
    "type",
}


def _normalized_sha256(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("sha256:"):
        text = text[7:]
    return text


def _issue(code: str, field: str, message: str, **details: Any) -> Dict[str, Any]:
    return {
        "code": code,
        "severity": "error",
        "field": field,
        "message": message,
        **details,
    }


def _forbidden_metadata_issues(value: Any, field: str = "contract") -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key).strip().lower()
            key_field = f"{field}.{key}"
            if key_text in _FORBIDDEN_METADATA_KEYS:
                issues.append(
                    _issue(
                        "discovery_metadata_forbidden",
                        key_field,
                        "Author, root, history, discovery, and similar-program metadata is forbidden.",
                    )
                )
            issues.extend(_forbidden_metadata_issues(nested, key_field))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, nested in enumerate(value):
            issues.extend(_forbidden_metadata_issues(nested, f"{field}[{index}]"))
    return issues


def _decode_artifact_text(content: bytes) -> str:
    encodings = ["utf-8-sig", "cp949"]
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings.insert(0, "utf-16")
    for encoding in encodings:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1")


def _read_receipt(
    receipt: Mapping[str, Any],
    *,
    field: str,
    allowed_authorities: set[str],
) -> tuple[Dict[str, Any], List[Dict[str, Any]], str]:
    issues: List[Dict[str, Any]] = []
    role = str(receipt.get("role") or "").strip()
    authority = str(receipt.get("authority") or "").strip()
    path_text = str(receipt.get("path") or "").strip()
    requested_sha = _normalized_sha256(receipt.get("sha256"))
    identifiers = receipt.get("identifiers", [])
    language = str(receipt.get("language") or "").strip().lower()

    if not role:
        issues.append(_issue("artifact_role_required", f"{field}.role", "Artifact role is required."))
    if authority not in allowed_authorities:
        issues.append(
            _issue(
                "artifact_authority_invalid",
                f"{field}.authority",
                "Artifact authority is not valid for this receipt.",
            )
        )
    if not path_text or not os.path.isabs(path_text):
        issues.append(
            _issue(
                "artifact_path_not_absolute",
                f"{field}.path",
                "Artifact receipts require an absolute path.",
            )
        )
    if not _SHA256_PATTERN.fullmatch(str(receipt.get("sha256") or "").strip()):
        issues.append(
            _issue(
                "artifact_sha256_invalid",
                f"{field}.sha256",
                "Artifact receipts require a complete SHA-256 value.",
            )
        )
    if not isinstance(identifiers, Sequence) or isinstance(identifiers, (str, bytes, bytearray)):
        issues.append(
            _issue(
                "artifact_identifiers_invalid",
                f"{field}.identifiers",
                "Artifact identifiers must be a list of identifiers.",
            )
        )
        identifiers = []
    elif len(identifiers) > MAX_IDENTIFIER_ENTRIES:
        issues.append(
            _issue(
                "artifact_identifiers_limit_exceeded",
                f"{field}.identifiers",
                "Artifact identifier metadata exceeds the bounded entry limit.",
                maximum=MAX_IDENTIFIER_ENTRIES,
            )
        )

    normalized_identifiers: List[str] = []
    for index, identifier in enumerate(identifiers):
        if index >= MAX_IDENTIFIER_ENTRIES:
            break
        name = str(identifier or "").strip()
        if not _IDENTIFIER_PATTERN.fullmatch(name):
            issues.append(
                _issue(
                    "artifact_identifier_invalid",
                    f"{field}.identifiers[{index}]",
                    "Artifact identifiers must use identifier syntax.",
                )
            )
        elif name in normalized_identifiers:
            issues.append(
                _issue(
                    "artifact_identifier_duplicate",
                    f"{field}.identifiers[{index}]",
                    "Artifact identifier metadata must not contain duplicates.",
                    identifier=name,
                )
            )
        else:
            normalized_identifiers.append(name)

    resolved_path = ""
    computed_sha = ""
    exact_text = ""
    size = 0
    if path_text and os.path.isabs(path_text):
        path = Path(path_text)
        try:
            before = path.stat()
            if not path.is_file():
                raise OSError("not a regular file")
            if before.st_size > MAX_ARTIFACT_BYTES:
                issues.append(
                    _issue(
                        "artifact_size_limit_exceeded",
                        f"{field}.path",
                        "Artifact exceeds the bounded receipt size limit.",
                    )
                )
            else:
                digest = hashlib.sha256()
                content = bytearray()
                total = 0
                with path.open("rb") as stream:
                    while True:
                        chunk = stream.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_ARTIFACT_BYTES:
                            raise OSError("artifact grew beyond the size limit")
                        digest.update(chunk)
                        content.extend(chunk)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    issues.append(
                        _issue(
                            "artifact_changed_during_read",
                            f"{field}.path",
                            "Artifact changed while its SHA-256 was recomputed.",
                        )
                    )
                else:
                    resolved_path = str(path.resolve())
                    computed_sha = digest.hexdigest()
                    size = total
                    if requested_sha and requested_sha != computed_sha:
                        issues.append(
                            _issue(
                                "artifact_sha256_mismatch",
                                f"{field}.sha256",
                                "Requested and recomputed SHA-256 values differ.",
                                role=role,
                            )
                        )
                    elif requested_sha and _SHA256_PATTERN.fullmatch(
                        str(receipt.get("sha256") or "").strip()
                    ):
                        exact_text = _decode_artifact_text(bytes(content))
        except OSError as exc:
            if str(exc) == "artifact grew beyond the size limit":
                issues.append(
                    _issue(
                        "artifact_size_limit_exceeded",
                        f"{field}.path",
                        "Artifact exceeded the bounded receipt size limit while being read.",
                        role=role,
                    )
                )
            else:
                issues.append(
                    _issue(
                        "artifact_unreadable",
                        f"{field}.path",
                        "Artifact path is not a readable regular file.",
                        role=role,
                    )
                )

    sha256_verified = bool(
        requested_sha
        and computed_sha
        and requested_sha == computed_sha
        and _SHA256_PATTERN.fullmatch(str(receipt.get("sha256") or "").strip())
    )

    return (
        {
            "role": role,
            "authority": authority,
            "path": resolved_path or path_text,
            "requested_sha256": f"sha256:{requested_sha}" if requested_sha else "",
            "computed_sha256": f"sha256:{computed_sha}" if computed_sha else "",
            "sha256_verified": sha256_verified,
            "size": size,
            "language": language or Path(path_text).suffix.lstrip(".").lower() or "csharp",
            "identifiers": normalized_identifiers,
        },
        issues,
        exact_text,
    )


def _explicit_allowlist(value: Any, field: str) -> tuple[List[str], List[Dict[str, Any]]]:
    issues: List[Dict[str, Any]] = []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return [], [_issue("comparator_scope_invalid", field, "Comparator scope must be an explicit list.")]
    if len(value) > MAX_ALLOWLIST_ENTRIES:
        issues.append(
            _issue(
                "comparator_scope_broad",
                field,
                "Comparator scope exceeds the bounded allowlist limit.",
            )
        )
    names: List[str] = []
    for index, item in enumerate(value):
        if index >= MAX_ALLOWLIST_ENTRIES:
            break
        name = str(item or "").strip()
        broad = name.lower() in _BROAD_SCOPE_VALUES or any(char in name for char in "*?[]{}")
        if not name or broad or len(name) > 256:
            issues.append(
                _issue(
                    "comparator_scope_broad",
                    f"{field}[{index}]",
                    "Comparator scope entries must be explicit bounded names.",
                )
            )
        elif name in names:
            issues.append(
                _issue(
                    "comparator_scope_duplicate",
                    f"{field}[{index}]",
                    "Comparator scope entries must be unique.",
                    name=name,
                )
            )
        else:
            names.append(name)
    return names, issues


def _mask_csharp(text: str) -> str:
    pattern = re.compile(
        r"//[^\r\n]*|/\*.*?\*/|\$?@\"(?:\"\"|[^\"])*\"|\$?\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'",
        re.DOTALL,
    )
    return pattern.sub(lambda match: " " * len(match.group(0)), text)


def _mask_sql(text: str) -> str:
    pattern = re.compile(r"--[^\r\n]*|/\*.*?\*/|'(?:''|[^'])*'", re.DOTALL)
    return pattern.sub(lambda match: " " * len(match.group(0)), text)


def _mask_layout(text: str) -> str:
    masked = re.sub(r"<!--.*?-->", lambda match: " " * len(match.group(0)), text, flags=re.DOTALL)

    def mask_attribute(match: re.Match[str]) -> str:
        name = match.group("name")
        value = match.group("value")
        if name.lower() in _LAYOUT_IDENTIFIER_ATTRIBUTES:
            return f'{name}="{value}"'
        return f'{name}="{" " * len(value)}"'

    return re.sub(
        r'(?P<name>[A-Za-z_][A-Za-z0-9_.:-]*)\s*=\s*"(?P<value>(?:""|[^"])*)"',
        mask_attribute,
        masked,
    )


def _identifier_is_authoritative(name: str) -> bool:
    lowered = name.lower()
    return bool(
        _IDENTIFIER_PATTERN.fullmatch(name)
        and lowered not in _CSHARP_KEYWORDS
        and lowered not in _FRAMEWORK_COMMON_IDENTIFIERS
        and lowered not in _COMMON_DECLARATION_IDENTIFIERS
    )


def _extract_csharp_identifier_inventory(text: str) -> Dict[str, set[str]]:
    """Extract class/type and class-member names without method-local names."""
    masked = _mask_csharp(text)
    inventory = {kind: set() for kind in _INVENTORY_KINDS}
    modifiers = (
        r"(?:public|private|protected|internal|static|readonly|volatile|const|"
        r"virtual|override|abstract|sealed|partial|async|unsafe|extern|new|"
        r"required|ref|out|in)\s+"
    )
    identifier = r"[A-Za-z_][A-Za-z0-9_$#]*"

    def add(kind: str, name: str) -> None:
        if _identifier_is_authoritative(name):
            inventory[kind].add(name)
            inventory["declared"].add(name)

    for match in re.finditer(
        rf"\b(?:class|struct|interface|enum|record)\s+({identifier})", masked
    ):
        add("classes", match.group(1))
        add("types", match.group(1))

    def brace_depths(source: str) -> List[int]:
        depths = [0] * (len(source) + 1)
        depth = 0
        for index, char in enumerate(source):
            depths[index] = depth
            if char == "{":
                depth += 1
            elif char == "}":
                depth = max(0, depth - 1)
        depths[len(source)] = depth
        return depths

    depths = brace_depths(masked)
    class_bodies: List[tuple[int, int, int]] = []
    for class_match in re.finditer(
        rf"\b(?:class|struct|interface|enum|record)\s+{identifier}[^{{;]*\{{", masked
    ):
        opening = masked.find("{", class_match.start(), class_match.end())
        if opening < 0:
            continue
        body_depth = depths[opening] + 1
        depth = body_depth
        closing = len(masked)
        for index in range(opening + 1, len(masked)):
            if masked[index] == "{":
                depth += 1
            elif masked[index] == "}":
                depth -= 1
                if depth == body_depth - 1:
                    closing = index
                    break
        class_bodies.append((opening + 1, closing, body_depth))

    for body_start, body_end, body_depth in class_bodies:
        body = masked[body_start:body_end]
        offset = body_start

        for match in re.finditer(
            rf"\bevent\s+(?:{identifier}(?:\.{identifier})?\s+)?({identifier})", body
        ):
            if depths[offset + match.start()] == body_depth:
                add("events", match.group(1))

        property_pattern = re.compile(
            rf"(?:^|[;}}])\s*(?:{modifiers})*"
            rf"(?P<type>{identifier}(?:\.{identifier})?(?:\s*<[^{{}};()]*>)?(?:\[\])?)\s+"
            rf"(?P<name>{identifier})\s*\{{(?=[^{{}}]*(?:\bget\b|\bset\b|\binit\b))",
            flags=re.MULTILINE,
        )
        for match in property_pattern.finditer(body):
            if depths[offset + match.start("name")] == body_depth:
                add("properties", match.group("name"))
                type_name = match.group("type").split("<", 1)[0].rsplit(".", 1)[-1]
                if _identifier_is_authoritative(type_name):
                    add("types", type_name)

        member_pattern = re.compile(
            rf"(?:^|[;}}])\s*(?:{modifiers})*"
            rf"(?P<type>{identifier}(?:\.{identifier})?(?:\s*<[^{{}};()]*>)?(?:\[\])?)\s+"
            rf"(?P<name>{identifier})\s*(?==|;|,)",
            flags=re.MULTILINE,
        )
        for match in member_pattern.finditer(body):
            if depths[offset + match.start("name")] != body_depth:
                continue
            add("fields", match.group("name"))
            type_name = match.group("type").split("<", 1)[0].rsplit(".", 1)[-1]
            if any(type_name.lower().endswith(suffix) for suffix in _CONTROL_TYPE_SUFFIXES):
                add("controls", match.group("name"))
            if type_name not in _FRAMEWORK_COMMON_IDENTIFIERS and _identifier_is_authoritative(type_name):
                add("types", type_name)

        method_prefix = (
            rf"(?:^|[;}}])\s*(?:{modifiers})*"
            rf"(?:{identifier}(?:\.{identifier})?(?:\s*<[^{{}};()]*>)?(?:\[\])?\s+)+"
        )
        method_pattern = re.compile(
            rf"{method_prefix}(?P<name>{identifier})\s*(?:<[^{{}};()]*>)?\s*\(",
            flags=re.MULTILINE,
        )
        for match in method_pattern.finditer(body):
            if depths[offset + match.start("name")] == body_depth:
                add("methods", match.group("name"))
                add("procedures", match.group("name"))

    return inventory


def _extract_sql_identifier_inventory(text: str) -> Dict[str, set[str]]:
    masked = _mask_sql(text)
    inventory = {kind: set() for kind in _INVENTORY_KINDS}
    for token in re.findall(r"(?<![A-Za-z0-9_$#])([A-Za-z_][A-Za-z0-9_$#]*)", masked):
        if token.lower() not in _SQL_COMMON_IDENTIFIERS and _identifier_is_authoritative(token):
            inventory["sql"].add(token)
            inventory["declared"].add(token)
    return inventory


def _extract_layout_identifier_inventory(text: str) -> Dict[str, set[str]]:
    masked = _mask_layout(text)
    inventory = {kind: set() for kind in _INVENTORY_KINDS}
    for match in re.finditer(
        r'(?P<name>[A-Za-z_][A-Za-z0-9_.:-]*)\s*=\s*"(?P<value>(?:""|[^"])*)"',
        masked,
    ):
        if match.group("name").lower() not in _LAYOUT_IDENTIFIER_ATTRIBUTES:
            continue
        for token in re.findall(r"[A-Za-z_][A-Za-z0-9_$#]*", match.group("value")):
            if _identifier_is_authoritative(token):
                inventory["layout"].add(token)
                inventory["declared"].add(token)
    for tag in re.findall(r"<\s*/?\s*([A-Za-z_][A-Za-z0-9_.:-]*)", masked):
        if _identifier_is_authoritative(tag):
            inventory["layout"].add(tag)
            inventory["declared"].add(tag)
    return inventory


def _extract_identifier_inventory(text: str, language: str = "csharp") -> List[str]:
    normalized_language = str(language or "csharp").strip().lower()
    if "sql" in normalized_language:
        inventory = _extract_sql_identifier_inventory(text)
    elif "layout" in normalized_language or "xml" in normalized_language or "srd" in normalized_language:
        inventory = _extract_layout_identifier_inventory(text)
    else:
        inventory = _extract_csharp_identifier_inventory(text)
    return sorted(inventory["declared"])


def _identifier_inventory_by_kind(text: str, language: str = "csharp") -> Dict[str, List[str]]:
    normalized_language = str(language or "csharp").strip().lower()
    if "sql" in normalized_language:
        inventory = _extract_sql_identifier_inventory(text)
    elif "layout" in normalized_language or "xml" in normalized_language or "srd" in normalized_language:
        inventory = _extract_layout_identifier_inventory(text)
    else:
        inventory = _extract_csharp_identifier_inventory(text)
    return {kind: sorted(inventory[kind]) for kind in _INVENTORY_KINDS if inventory[kind]}


def _generated_text_entries(generated_texts: Mapping[str, Any]) -> List[tuple[str, str, str]]:
    entries: List[tuple[str, str, str]] = []
    for role in sorted(generated_texts):
        value = generated_texts[role]
        if isinstance(value, Mapping):
            text = str(value.get("text") or "")
            language = str(value.get("language") or role).strip().lower()
        else:
            text = str(value or "")
            language = role.lower()
        entries.append((str(role), language, text))
    return entries


def _contains_identifier(text: str, identifier: str, *, ignore_case: bool) -> bool:
    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_$#]){re.escape(identifier)}(?![A-Za-z0-9_$#])",
        flags,
    )
    return pattern.search(text) is not None


def validate_pb_migration_authority_contract(
    *,
    target_receipts: Sequence[Mapping[str, Any]],
    comparator: Mapping[str, Any] | None = None,
    authority_requests: Sequence[Mapping[str, Any]] = (),
    generated_texts: Mapping[str, Any] | None = None,
    packaged_profile_id: str = "packaged-pb-style-contract",
) -> HarnessResult:
    """Validate exact artifact authority and resolve only bounded comparator requests.

    Target receipts use ``authority`` values ``current_target`` or ``user_supplied``.
    A comparator contains ``receipt``, one exact ``role_mapping``, an ``allowlist``
    with ``properties``/``behaviors``, ``identifier_map``, and optional
    ``retained_identifiers``. No source-tree discovery is performed.
    """

    issues = _forbidden_metadata_issues(
        {
            "target_receipts": target_receipts,
            "comparator": comparator or {},
            "authority_requests": authority_requests,
        }
    )
    receipts: List[Dict[str, Any]] = []
    roles: Dict[str, Dict[str, Any]] = {}
    for index, raw_receipt in enumerate(target_receipts):
        if not isinstance(raw_receipt, Mapping):
            issues.append(
                _issue(
                    "artifact_receipt_invalid",
                    f"target_receipts[{index}]",
                    "Target artifact receipt must be an object.",
                )
            )
            continue
        receipt, receipt_issues, exact_text = _read_receipt(
            raw_receipt,
            field=f"target_receipts[{index}]",
            allowed_authorities={"current_target", "user_supplied"},
        )
        issues.extend(receipt_issues)
        if receipt["sha256_verified"]:
            receipt["identifiers"] = _extract_identifier_inventory(exact_text, receipt.get("language", "csharp"))
            receipt["identifier_inventory_by_kind"] = _identifier_inventory_by_kind(
                exact_text, receipt.get("language", "csharp")
            )
        receipt["identifier_inventory"] = list(receipt["identifiers"])
        role = receipt["role"]
        if role in roles:
            issues.append(
                _issue(
                    "target_role_duplicate",
                    f"target_receipts[{index}].role",
                    "Each target role must have exactly one authority receipt.",
                    role=role,
                )
            )
        elif role:
            roles[role] = receipt
        receipts.append(receipt)
    target_identifier_inventory = sorted(
        {
            identifier
            for receipt in receipts
            for identifier in receipt.get("identifiers", [])
        }
    )

    comparator_metadata: Dict[str, Any] = {"status": "not_supplied"}
    comparator_role = ""
    mapped_target_role = ""
    properties: List[str] = []
    behaviors: List[str] = []
    source_identifiers: List[str] = []
    identifier_map: Dict[str, str] = {}
    retained_identifiers: List[str] = []

    if comparator is not None:
        comparator_metadata = {"status": "accepted"}
        receipt_value = comparator.get("receipt")
        if not isinstance(receipt_value, Mapping):
            issues.append(
                _issue(
                    "comparator_receipt_required",
                    "comparator.receipt",
                    "Comparator requires one exact artifact receipt.",
                )
            )
            comparator_receipt = {}
        else:
            comparator_receipt, receipt_issues, exact_text = _read_receipt(
                receipt_value,
                field="comparator.receipt",
                allowed_authorities={"named_comparator"},
            )
            issues.extend(receipt_issues)
            if comparator_receipt["sha256_verified"]:
                comparator_receipt["identifiers"] = _extract_identifier_inventory(
                    exact_text, comparator_receipt.get("language", "csharp")
                )
                comparator_receipt["identifier_inventory_by_kind"] = _identifier_inventory_by_kind(
                    exact_text, comparator_receipt.get("language", "csharp")
                )
        comparator_role = comparator_receipt.get("role", "")
        source_identifiers = list(comparator_receipt.get("identifiers", []))
        comparator_metadata["receipt"] = comparator_receipt
        comparator_metadata["identifier_inventory"] = list(source_identifiers)
        comparator_metadata["identifier_inventory_by_kind"] = dict(
            comparator_receipt.get("identifier_inventory_by_kind", {})
        )

        role_mapping = comparator.get("role_mapping")
        if not isinstance(role_mapping, Mapping) or len(role_mapping) != 1:
            issues.append(
                _issue(
                    "comparator_role_mapping_invalid",
                    "comparator.role_mapping",
                    "Comparator requires one explicit source-role to target-role mapping.",
                )
            )
        elif comparator_role:
            mapped_target_role = str(role_mapping.get(comparator_role) or "").strip()
            if not mapped_target_role:
                issues.append(
                    _issue(
                        "comparator_role_unmapped",
                        "comparator.role_mapping",
                        "Comparator receipt role is not explicitly mapped.",
                        role=comparator_role,
                    )
                )
            elif mapped_target_role not in roles:
                issues.append(
                    _issue(
                        "comparator_target_role_unknown",
                        "comparator.role_mapping",
                        "Comparator role maps to no target artifact receipt.",
                        role=mapped_target_role,
                    )
                )

        allowlist = comparator.get("allowlist")
        if not isinstance(allowlist, Mapping) or set(allowlist) - {"properties", "behaviors"}:
            issues.append(
                _issue(
                    "comparator_scope_broad",
                    "comparator.allowlist",
                    "Comparator may allow only explicit properties and behaviors.",
                )
            )
        else:
            properties, scope_issues = _explicit_allowlist(
                allowlist.get("properties", []), "comparator.allowlist.properties"
            )
            issues.extend(scope_issues)
            behaviors, scope_issues = _explicit_allowlist(
                allowlist.get("behaviors", []), "comparator.allowlist.behaviors"
            )
            issues.extend(scope_issues)
            if not properties and not behaviors:
                issues.append(
                    _issue(
                        "comparator_scope_vacuous",
                        "comparator.allowlist",
                        "Comparator scope must name at least one property or behavior.",
                    )
                )

        raw_map = comparator.get("identifier_map", {})
        raw_retained = comparator.get("retained_identifiers", [])
        if not isinstance(raw_map, Mapping):
            issues.append(
                _issue(
                    "comparator_identifier_map_invalid",
                    "comparator.identifier_map",
                    "Comparator identifier mapping must be an object.",
                )
            )
            raw_map = {}
        if not isinstance(raw_retained, Sequence) or isinstance(
            raw_retained, (str, bytes, bytearray)
        ):
            issues.append(
                _issue(
                    "comparator_retained_identifiers_invalid",
                    "comparator.retained_identifiers",
                    "Retained identifiers must be an explicit list.",
                )
            )
            raw_retained = []
        identifier_map = {
            str(source).strip(): str(target).strip() for source, target in raw_map.items()
        }
        retained_identifiers = [str(item).strip() for item in raw_retained]
        target_identifiers = {
            identifier for receipt in receipts for identifier in receipt.get("identifiers", [])
        }
        for source in source_identifiers:
            mapped = identifier_map.get(source, "")
            retained = source in retained_identifiers
            if bool(mapped) == retained:
                issues.append(
                    _issue(
                        "comparator_identifier_authority_invalid",
                        f"comparator.identifiers.{source}",
                        "Each comparator identifier must be mapped or intentionally retained, exclusively.",
                        identifier=source,
                    )
                )
            elif mapped and mapped not in target_identifiers:
                issues.append(
                    _issue(
                        "comparator_identifier_target_unknown",
                        f"comparator.identifier_map.{source}",
                        "Mapped comparator identifier is not declared by a target receipt.",
                        identifier=source,
                    )
                )
        for source in identifier_map:
            if source not in source_identifiers:
                issues.append(
                    _issue(
                        "comparator_identifier_source_unknown",
                        f"comparator.identifier_map.{source}",
                        "Identifier mapping source is not declared by the comparator receipt.",
                        identifier=source,
                    )
                )
        for source in retained_identifiers:
            if source not in source_identifiers:
                issues.append(
                    _issue(
                        "comparator_identifier_source_unknown",
                        f"comparator.retained_identifiers.{source}",
                        "Retained identifier is not declared by the comparator source.",
                        identifier=source,
                    )
                )

        comparator_metadata.update(
            {
                "role_mapping": {comparator_role: mapped_target_role} if comparator_role else {},
                "allowlist": {"properties": properties, "behaviors": behaviors},
                "identifier_map": dict(sorted(identifier_map.items())),
                "retained_identifiers": sorted(set(retained_identifiers)),
            }
        )

    resolutions: List[Dict[str, Any]] = []
    for index, request in enumerate(authority_requests):
        if not isinstance(request, Mapping):
            issues.append(
                _issue(
                    "authority_request_invalid",
                    f"authority_requests[{index}]",
                    "Authority request must be an object.",
                )
            )
            continue
        category = str(request.get("category") or "").strip().lower()
        name = str(request.get("name") or "").strip()
        target_role = str(request.get("target_role") or "").strip()
        if category not in {"style", "property", "behavior"} or not name:
            issues.append(
                _issue(
                    "authority_request_invalid",
                    f"authority_requests[{index}]",
                    "Authority requests require style, property, or behavior plus an explicit name.",
                )
            )
            continue
        if target_role and target_role not in roles:
            issues.append(
                _issue(
                    "authority_target_role_unknown",
                    f"authority_requests[{index}].target_role",
                    "Authority request names no target receipt role.",
                    role=target_role,
                )
            )
        comparator_allowed = bool(
            comparator is not None
            and target_role == mapped_target_role
            and (
                (category == "property" and name in properties)
                or (category == "behavior" and name in behaviors)
            )
        )
        if comparator_allowed:
            authority = "named_comparator"
            source_role = comparator_role
        elif category == "style":
            authority = "packaged_profile"
            source_role = packaged_profile_id
        else:
            authority = roles.get(target_role, {}).get("authority", "current_target")
            source_role = target_role
        resolutions.append(
            {
                "category": category,
                "name": name,
                "target_role": target_role,
                "authority": authority,
                "source_role": source_role,
            }
        )

    for role, language, text in _generated_text_entries(generated_texts or {}):
        if "sql" in language:
            masked = _mask_sql(text)
            ignore_case = True
        elif "layout" in language or "xml" in language or "srd" in language:
            masked = _mask_layout(text)
            ignore_case = False
        else:
            masked = _mask_csharp(text)
            ignore_case = False
        for source in source_identifiers:
            if source in retained_identifiers:
                continue
            if _contains_identifier(masked, source, ignore_case=ignore_case):
                issues.append(
                    _issue(
                        "stale_comparator_identifier",
                        f"generated_texts.{role}",
                        "Generated text contains a comparator identifier that was not intentionally retained.",
                        identifier=source,
                        role=role,
                    )
                )

    issues.sort(key=lambda item: (item["code"], item["field"], str(item.get("identifier", ""))))
    if comparator is not None and issues:
        comparator_metadata["status"] = "blocked"
    status = "passed" if not issues else "blocked"
    metadata = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "harness": "pb-migration-authority",
        "operation": "validate_pb_migration_authority_contract",
        "status": status,
        "style_authority": {
            "authority": "packaged_profile",
            "profile_id": packaged_profile_id,
        },
        "target_receipts": receipts,
        "target_identifier_inventory": target_identifier_inventory,
        "comparator": comparator_metadata,
        "authority_resolutions": resolutions,
        "issues": issues,
        "issue_codes": sorted({item["code"] for item in issues}),
        "discovery_performed": False,
        "external_sources_consulted": [],
        "token_optimizer_status": "passthrough",
    }
    return HarnessResult(
        success=not issues,
        stdout=json.dumps(
            {"status": status, "issue_codes": metadata["issue_codes"]},
            sort_keys=True,
        ),
        stderr="" if not issues else "PB migration authority contract validation failed.",
        exit_code=0 if not issues else 1,
        metadata=metadata,
    )


verify_pb_migration_authority_contract = validate_pb_migration_authority_contract


__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "validate_pb_migration_authority_contract",
    "verify_pb_migration_authority_contract",
]
