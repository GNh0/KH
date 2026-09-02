"""Dependency-free static validators for generated PB-to-C# Designer UI code.

The validators in this module deliberately inspect text instead of loading
WinForms or DevExpress.  A successful result proves the requested static
contract only; it does not prove that a live Designer can load the form.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple
from fnmatch import fnmatchcase
import json
import os
import re
import xml.etree.ElementTree as ET


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_CONTROL_DECLARATION = re.compile(
    rf"^\s*(?:private|protected|internal|public)\s+"
    rf"(?P<type>[A-Za-z_][A-Za-z0-9_.<>]*)\s+(?P<name>{_IDENTIFIER})\s*;",
    re.MULTILINE,
)
_CONTROL_INITIALIZER = re.compile(
    rf"^\s*this\.(?P<name>{_IDENTIFIER})\s*=\s*new\s+"
    rf"(?P<type>[A-Za-z_][A-Za-z0-9_.<>]*)\s*\(",
    re.MULTILINE,
)
_ASSIGNMENT = re.compile(
    rf"^\s*this\.(?P<name>{_IDENTIFIER})\."
    rf"(?P<property>{_IDENTIFIER}(?:\.{_IDENTIFIER})*)\s*=\s*(?P<value>.*?);\s*$",
    re.MULTILINE,
)
_CODE_BEHIND_INITIALIZER = re.compile(
    rf"(?<![.\w])(?P<qualified>this\.)?(?P<name>{_IDENTIFIER})\s*=\s*new\s+"
    rf"(?P<type>[A-Za-z_][A-Za-z0-9_.<>]*)\s*\("
)
_CODE_BEHIND_ASSIGNMENT = re.compile(
    rf"(?<![.\w])(?P<qualified>this\.)?(?P<name>{_IDENTIFIER})\."
    rf"(?P<property>{_IDENTIFIER}(?:\.{_IDENTIFIER})*)\s*=\s*(?P<value>.*?);"
)
_CODE_BEHIND_COLLECTION = re.compile(
    rf"(?<![.\w])(?P<qualified>this\.)?(?P<name>{_IDENTIFIER})\."
    rf"(?P<collection>Controls|Columns|RepositoryItems)\."
    rf"(?P<method>Add|AddRange|SetChildIndex)\s*\("
)
_CODE_BEHIND_EVENT = re.compile(
    rf"(?<![.\w])(?P<qualified>this\.)?(?P<name>{_IDENTIFIER})\."
    rf"(?P<event>{_IDENTIFIER})\s*\+="
)
_FORM_COLLECTION = re.compile(r"(?<![.\w])this\.Controls\.(?:Add|SetChildIndex)\s*\(")
_FORM_EVENT = re.compile(rf"(?<![.\w])this\.(?P<event>{_IDENTIFIER})\s*\+=")
_FORM_ASSIGNMENT = re.compile(
    rf"^\s*this\.(?P<property>{_IDENTIFIER}(?:\.{_IDENTIFIER})*)\s*=\s*(?P<value>.*?);\s*$",
    re.MULTILINE,
)
_CONTROLS_ADD = re.compile(
    rf"^\s*this(?:\.(?P<parent>{_IDENTIFIER}))?\.Controls\.Add\(\s*"
    rf"this\.(?P<child>{_IDENTIFIER})"
    rf"(?:\s*,\s*(?P<column>-?\d+)\s*,\s*(?P<row>-?\d+))?\s*\)\s*;",
    re.MULTILINE,
)
_SET_CHILD_INDEX = re.compile(
    rf"^\s*this(?:\.(?P<parent>{_IDENTIFIER}))?\.Controls\.SetChildIndex\(\s*"
    rf"this\.(?P<child>{_IDENTIFIER})\s*,\s*(?P<index>-?\d+)\s*\)\s*;",
    re.MULTILINE,
)
_POINT = re.compile(
    r"new\s+(?:System\.Drawing\.)?Point\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)"
)
_SIZE = re.compile(
    r"new\s+(?:System\.Drawing\.)?Size\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)"
)
_CSHARP_STRING = re.compile(r'^@?"(?:""|\\.|[^"\\])*"$')
_CLASS_DECLARATION = re.compile(
    rf"\b(?:(?:public|internal|protected|private|abstract|sealed|static|partial)\s+)*"
    rf"class\s+(?P<name>{_IDENTIFIER})\s*:\s*(?P<bases>[^{{\r\n]+)",
    re.MULTILINE,
)

_INPUT_TYPE_TOKENS = (
    "textedit",
    "spinedit",
    "dateedit",
    "lookupedit",
    "buttonedit",
    "checkedit",
    "memoedit",
    "radiogroup",
    "textbox",
    "combobox",
    "datetimepicker",
    "numericupdown",
    "checkbox",
    "radiobutton",
)
_NON_INPUT_TYPE_TOKENS = (
    "label",
    "grid",
    "column",
    "repository",
    "panel",
    "groupcontrol",
    "tablelayoutpanel",
    "tabpage",
    "container",
    "button",  # ButtonEdit is accepted before this exclusion is evaluated.
)
_INPUT_NAME = re.compile(
    r"^(?:txt|Spin|ymd|cbo|btn|Chk|memo|rad)[A-Z0-9_]", re.IGNORECASE
)
_STATIC_PROPERTY_PREFIXES = (
    "Name",
    "Location",
    "Size",
    "ClientSize",
    "MinimumSize",
    "MaximumSize",
    "Margin",
    "Padding",
    "Dock",
    "Anchor",
    "TabIndex",
    "TabStop",
    "Text",
    "Caption",
    "BindingField",
    "FieldName",
    "ColumnEdit",
    "DisplayFormat",
    "EditFormat",
    "Appearance",
    "Options",
    "Properties",
)


@dataclass(frozen=True)
class DesignerContractResult:
    """Harness-shaped validation result with no project-local dependency."""

    success: bool
    issues: Tuple[Dict[str, Any], ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        return 0 if self.success else 1

    @property
    def stdout(self) -> str:
        return json.dumps(
            {"status": "passed" if self.success else "blocked", "issue_count": len(self.issues)},
            ensure_ascii=False,
            sort_keys=True,
        )

    @property
    def stderr(self) -> str:
        return "" if self.success else "PB Designer UI contract validation failed."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "issues": [dict(issue) for issue in self.issues],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ControlRecord:
    name: str
    type_name: str = ""
    parent: str = "<form>"
    location: Tuple[int, int] | None = None
    size: Tuple[int, int] | None = None
    tab_index: int | None = None
    table_position: Tuple[int, int] | None = None
    add_order: int | None = None
    child_index: int | None = None
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DesignerModel:
    controls: Dict[str, ControlRecord]
    form_properties: Dict[str, str]
    controls_add: Tuple[Dict[str, Any], ...]
    set_child_index: Tuple[Dict[str, Any], ...]
    assignments: Tuple[Dict[str, str], ...]
    source: str = field(repr=False, default="")


def _issue(code: str, message: str, **details: Any) -> Dict[str, Any]:
    return {"code": code, "severity": "error", "message": message, **details}


def _result(issues: Iterable[Dict[str, Any]], **metadata: Any) -> DesignerContractResult:
    normalized = tuple(dict(issue) for issue in issues)
    payload = {
        "status": "passed" if not normalized else "blocked",
        "issues": [dict(issue) for issue in normalized],
        "verification_scope": "static_designer_source",
        "actual_live_designer_load_observed": False,
        **metadata,
    }
    return DesignerContractResult(success=not normalized, issues=normalized, metadata=payload)


def _strip_csharp_comments(source: str) -> str:
    """Remove comments while preserving strings, newlines, and source offsets."""

    text = str(source or "")
    output: List[str] = []
    index = 0
    state = "code"
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                output.extend("  ")
                index += 2
                state = "line_comment"
                continue
            if char == "/" and nxt == "*":
                output.extend("  ")
                index += 2
                state = "block_comment"
                continue
            if char == '@' and nxt == '"':
                output.extend('@"')
                index += 2
                state = "verbatim_string"
                continue
            if char == '"':
                output.append(char)
                index += 1
                state = "string"
                continue
            if char == "'":
                output.append(char)
                index += 1
                state = "character"
                continue
            output.append(char)
            index += 1
            continue
        if state == "line_comment":
            if char in "\r\n":
                output.append(char)
                state = "code"
            else:
                output.append(" ")
            index += 1
            continue
        if state == "block_comment":
            if char == "*" and nxt == "/":
                output.extend("  ")
                index += 2
                state = "code"
            else:
                output.append(char if char in "\r\n" else " ")
                index += 1
            continue
        if state == "string":
            output.append(char)
            index += 1
            if char == "\\" and index < len(text):
                output.append(text[index])
                index += 1
            elif char == '"':
                state = "code"
            continue
        if state == "verbatim_string":
            output.append(char)
            index += 1
            if char == '"' and index < len(text) and text[index] == '"':
                output.append('"')
                index += 1
            elif char == '"':
                state = "code"
            continue
        output.append(char)
        index += 1
        if char == "\\" and index < len(text):
            output.append(text[index])
            index += 1
        elif char == "'":
            state = "code"
    return "".join(output)


def _mask_csharp_noncode(source: str) -> str:
    """Mask comments and literals while retaining offsets and line breaks."""

    text = str(source or "")
    output = list(text)
    index = 0
    state = "code"
    raw_quote_count = 0
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                output[index] = output[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if char == "/" and nxt == "*":
                output[index] = output[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            raw_match = re.match(r"\$*\"{3,}", text[index:])
            if raw_match:
                token = raw_match.group(0)
                raw_quote_count = len(token) - len(token.lstrip("$"))
                raw_quote_count = len(token) - raw_quote_count
                for offset in range(len(token)):
                    output[index + offset] = " "
                index += len(token)
                state = "raw_string"
                continue
            prefix_match = re.match(r"(?:\$@|@\$|\$|@)?\"", text[index:])
            if prefix_match:
                token = prefix_match.group(0)
                for offset in range(len(token)):
                    output[index + offset] = " "
                index += len(token)
                state = "verbatim_string" if "@" in token else "string"
                continue
            if char == "'":
                output[index] = " "
                index += 1
                state = "character"
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
        if state == "raw_string":
            closing = '"' * raw_quote_count
            if text.startswith(closing, index):
                for offset in range(raw_quote_count):
                    output[index + offset] = " "
                index += raw_quote_count
                state = "code"
            else:
                if char not in "\r\n":
                    output[index] = " "
                index += 1
            continue
        if state == "verbatim_string":
            if char == '"' and nxt == '"':
                output[index] = output[index + 1] = " "
                index += 2
            else:
                if char not in "\r\n":
                    output[index] = " "
                index += 1
                if char == '"':
                    state = "code"
            continue
        output[index] = " " if char not in "\r\n" else char
        index += 1
        if char == "\\" and index < len(text):
            if text[index] not in "\r\n":
                output[index] = " "
            index += 1
        elif (state == "string" and char == '"') or (state == "character" and char == "'"):
            state = "code"
    return "".join(output)


def _csharp_string_value(value: str) -> str | None:
    raw = str(value or "").strip()
    if not _CSHARP_STRING.fullmatch(raw):
        return None
    if raw.startswith('@"'):
        return raw[2:-1].replace('""', '"')
    body = raw[1:-1]
    escapes = {
        "\\": "\\",
        '"': '"',
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "0": "\0",
    }

    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.startswith("u") and len(token) == 5:
            return chr(int(token[1:], 16))
        return escapes.get(token, token)

    return re.sub(r"\\(u[0-9A-Fa-f]{4}|.)", replace, body)


def _parse_point(value: str) -> Tuple[int, int] | None:
    match = _POINT.search(str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _parse_size(value: str) -> Tuple[int, int] | None:
    match = _SIZE.search(str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _normalized_csharp_value(value: str) -> str:
    """Remove formatting whitespace while retaining literal payload exactly."""

    text = str(value or "")
    output: List[str] = []
    state = "code"
    index = 0
    while index < len(text):
        char = text[index]
        if state == "code":
            if char.isspace():
                index += 1
                continue
            if char == '@' and index + 1 < len(text) and text[index + 1] == '"':
                output.extend('@"')
                index += 2
                state = "verbatim"
                continue
            if char == '"':
                state = "string"
            elif char == "'":
                state = "character"
            output.append(char)
            index += 1
            continue
        output.append(char)
        index += 1
        if state in {"string", "character"} and char == "\\" and index < len(text):
            output.append(text[index])
            index += 1
            continue
        if state == "verbatim" and char == '"' and index < len(text) and text[index] == '"':
            output.append('"')
            index += 1
            continue
        if (state in {"string", "verbatim"} and char == '"') or (
            state == "character" and char == "'"
        ):
            state = "code"
    return "".join(output)


def parse_designer_source(designer_source: str) -> DesignerModel:
    """Parse controls, static assignments, containment, table cells, and z-order."""

    source = _strip_csharp_comments(designer_source)
    type_names: Dict[str, str] = {}
    for match in _CONTROL_DECLARATION.finditer(source):
        type_names[match.group("name")] = match.group("type")
    for match in _CONTROL_INITIALIZER.finditer(source):
        type_name = match.group("type")
        if type_name.split(".")[-1] not in {"Point", "PointF", "Size", "SizeF", "Padding", "Font"}:
            type_names[match.group("name")] = type_name

    property_values: Dict[str, Dict[str, str]] = {}
    assignments: List[Dict[str, str]] = []
    for match in _ASSIGNMENT.finditer(source):
        name = match.group("name")
        property_path = match.group("property")
        value = match.group("value").strip()
        property_values.setdefault(name, {})[property_path] = value
        assignments.append({"name": name, "property": property_path, "value": value})

    form_properties: Dict[str, str] = {}
    for match in _FORM_ASSIGNMENT.finditer(source):
        property_name = match.group("property")
        if "." not in property_name and property_name not in type_names:
            form_properties[property_name] = match.group("value").strip()

    add_calls: List[Dict[str, Any]] = []
    parents: Dict[str, str] = {}
    table_positions: Dict[str, Tuple[int, int]] = {}
    add_order: Dict[str, int] = {}
    for ordinal, match in enumerate(_CONTROLS_ADD.finditer(source)):
        parent = match.group("parent") or "<form>"
        child = match.group("child")
        column = int(match.group("column")) if match.group("column") is not None else None
        row = int(match.group("row")) if match.group("row") is not None else None
        call = {
            "parent": parent,
            "child": child,
            "column": column,
            "row": row,
            "order": ordinal,
        }
        add_calls.append(call)
        parents[child] = parent
        add_order[child] = ordinal
        if column is not None and row is not None:
            table_positions[child] = (column, row)

    child_index_calls: List[Dict[str, Any]] = []
    child_indexes: Dict[str, int] = {}
    for match in _SET_CHILD_INDEX.finditer(source):
        parent = match.group("parent") or "<form>"
        child = match.group("child")
        index = int(match.group("index"))
        child_index_calls.append({"parent": parent, "child": child, "index": index})
        child_indexes[child] = index
        parents.setdefault(child, parent)

    names = set(type_names) | set(property_values) | set(parents)
    controls: Dict[str, ControlRecord] = {}
    for name in sorted(names):
        properties = dict(property_values.get(name, {}))
        controls[name] = ControlRecord(
            name=name,
            type_name=type_names.get(name, ""),
            parent=parents.get(name, "<form>"),
            location=_parse_point(properties.get("Location", "")),
            size=_parse_size(properties.get("Size", "")),
            tab_index=(
                int(properties["TabIndex"])
                if re.fullmatch(r"\d+", properties.get("TabIndex", "").strip())
                else None
            ),
            table_position=table_positions.get(name),
            add_order=add_order.get(name),
            child_index=child_indexes.get(name),
            properties=properties,
        )
    return DesignerModel(
        controls=controls,
        form_properties=form_properties,
        controls_add=tuple(add_calls),
        set_child_index=tuple(child_index_calls),
        assignments=tuple(assignments),
        source=source,
    )


def _canonical_form_base(value: str) -> str:
    normalized = re.sub(r"\s+", "", str(value or "")).removeprefix("global::")
    aliases = {
        "Form": "System.Windows.Forms.Form",
        "System.Windows.Forms.Form": "System.Windows.Forms.Form",
        "UserControl": "System.Windows.Forms.UserControl",
        "System.Windows.Forms.UserControl": "System.Windows.Forms.UserControl",
    }
    if normalized in aliases:
        return aliases[normalized]
    if re.fullmatch(rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})*", normalized):
        return normalized
    return ""


def _matching_brace(source: str, opening_index: int) -> int | None:
    depth = 0
    state = "code"
    index = opening_index
    while index < len(source):
        char = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""
        if state == "code":
            if char == '"':
                state = "string"
            elif char == "'":
                state = "character"
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
        elif state == "string":
            if char == "\\":
                index += 1
            elif char == '"':
                state = "code"
        else:
            if char == "\\":
                index += 1
            elif char == "'":
                state = "code"
        index += 1
    return None


def _enclosing_callable_scope(source: str, position: int) -> Tuple[int, int, str] | None:
    """Return the narrowest method or constructor body containing ``position``."""

    candidates: List[Tuple[int, int, str]] = []
    for opening in (match.start() for match in re.finditer(r"\{", source[:position + 1])):
        prefix = source[max(0, opening - 1200):opening]
        header = re.search(
            rf"(?P<name>{_IDENTIFIER})\s*\((?P<parameters>[^{{}};]*)\)\s*$",
            prefix,
        )
        if not header or header.group("name") in {
            "if", "for", "foreach", "while", "switch", "catch", "using", "lock", "fixed",
        }:
            continue
        closing = _matching_brace(source, opening)
        if closing is not None and opening < position < closing:
            candidates.append((opening, closing, header.group("parameters")))
    return min(candidates, key=lambda item: item[1] - item[0]) if candidates else None


def _unqualified_member_is_shadowed(source: str, name: str, position: int) -> bool:
    """Conservatively recognize parameters and locals that hide a form field."""

    scope = _enclosing_callable_scope(source, position)
    if scope is None:
        return False
    opening, _, parameters = scope
    parameter_pattern = re.compile(
        rf"(?:^|,)\s*(?:(?:this|ref|out|in|params)\s+)*"
        rf"[A-Za-z_][A-Za-z0-9_.<>?\[\],]*\s+{re.escape(name)}\b"
    )
    if parameter_pattern.search(parameters):
        return True
    body_prefix = source[opening + 1:position]
    local_pattern = re.compile(
        rf"(?<![.\w])(?:var|[A-Za-z_][A-Za-z0-9_.<>?\[\],]*)\s+"
        rf"{re.escape(name)}\b\s*(?==|;|,|\))"
    )
    target_blocks = set(_active_lexical_blocks(source, position, opening))
    for match in local_pattern.finditer(body_prefix):
        declaration_position = opening + 1 + match.start()
        declaration_blocks = _active_lexical_blocks(
            source,
            declaration_position,
            opening,
        )
        if declaration_blocks and declaration_blocks[-1] in target_blocks:
            return True
    return False


def _active_lexical_blocks(
    source: str,
    position: int,
    lower_bound: int,
) -> Tuple[int, ...]:
    """Return brace-delimited blocks still open at ``position``."""

    blocks: List[int] = []
    start = max(0, lower_bound)
    stop = min(max(position, start), len(source))
    for index in range(start, stop):
        if source[index] == "{":
            blocks.append(index)
        elif source[index] == "}" and blocks:
            blocks.pop()
    return tuple(blocks)


def _unqualified_initializer_is_local(source: str, position: int) -> bool:
    line_start = max(source.rfind("\n", 0, position), source.rfind("\r", 0, position)) + 1
    prefix = source[line_start:position]
    return bool(
        re.search(
            r"(?:^|\s)(?:var|[A-Za-z_][A-Za-z0-9_.<>?\[\],]*)\s+$",
            prefix,
        )
    )


def _is_static_designer_property(property_name: str) -> bool:
    first = str(property_name or "").split(".", 1)[0]
    for prefix in _STATIC_PROPERTY_PREFIXES:
        if property_name == prefix or property_name.startswith(prefix + "."):
            return True
        if prefix in {"Appearance", "Options"} and first.startswith(prefix):
            return True
    return False


def _source_type_declarations(source: str) -> Dict[str, Dict[str, str]]:
    """Extract the small type/base map needed for source-chain proof."""

    declarations: Dict[str, Dict[str, str]] = {}
    class_matches = list(_CLASS_DECLARATION.finditer(source))
    namespace_ranges: List[Tuple[int, int, str]] = []
    for namespace_match in re.finditer(
        rf"\bnamespace\s+(?P<name>{_IDENTIFIER}(?:\.{_IDENTIFIER})*)\s*\{{", source
    ):
        closing = _matching_brace(source, namespace_match.end() - 1)
        if closing is not None:
            namespace_ranges.append((namespace_match.end(), closing, namespace_match.group("name")))
    file_namespace = re.search(
        rf"\bnamespace\s+(?P<name>{_IDENTIFIER}(?:\.{_IDENTIFIER})*)\s*;", source
    )
    for class_match in class_matches:
        namespace = ""
        for start, end, candidate in namespace_ranges:
            if start <= class_match.start() < end and len(candidate) >= len(namespace):
                namespace = candidate
        if not namespace and file_namespace and class_match.start() > file_namespace.end():
            namespace = file_namespace.group("name")
        qualified_name = f"{namespace}.{class_match.group('name')}" if namespace else class_match.group("name")
        declarations[qualified_name] = {
            "base": class_match.group("bases").split(",", 1)[0].strip(),
            "namespace": namespace,
        }
    return declarations


def _source_type_chain_proven(source: str, expected: str) -> bool:
    declarations = _source_type_declarations(source)
    current = expected
    seen = set()
    while current not in {"System.Windows.Forms.Form", "System.Windows.Forms.UserControl"}:
        if current in seen or current not in declarations:
            return False
        seen.add(current)
        declaration = declarations[current]
        base = _canonical_form_base(declaration["base"])
        if not base:
            return False
        if "." not in base and declaration["namespace"]:
            base = f"{declaration['namespace']}.{base}"
        current = base
    return True


def _artifact_sha256(path: Path, expected_sha256: str, issues: List[Dict[str, Any]]) -> str:
    if not path.is_absolute():
        issues.append(_issue("form_base_artifact_path_not_absolute", "Base-type evidence requires an absolute artifact path.", path=str(path)))
        return ""
    if not path.is_file():
        issues.append(_issue("form_base_artifact_file_missing", "The exact base-type evidence artifact does not exist.", path=str(path)))
        return ""
    actual_sha = sha256(path.read_bytes()).hexdigest()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(expected_sha256 or "")):
        issues.append(_issue("form_base_artifact_sha256_invalid", "A complete SHA-256 digest is required for base-type evidence."))
        return ""
    if actual_sha != str(expected_sha256).lower():
        issues.append(
            _issue(
                "form_base_artifact_sha256_mismatch",
                "Current base-type evidence bytes do not match the bound SHA-256.",
                expected=str(expected_sha256).lower(),
                actual=actual_sha,
            )
        )
        return ""
    return actual_sha


_RUNTIME_TYPE_CHAIN_PRODUCER_KINDS = {
    "host_tool",
    "runtime_tool",
    "host_runtime_tool",
}


def _normalized_receipt_sha(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text[7:] if text.startswith("sha256:") else text


def _canonical_type_chain_output(types: Sequence[str]) -> bytes:
    return json.dumps(
        {"types": list(types)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _validate_binary_type_chain_runtime_receipt(
    receipt: Mapping[str, Any] | None,
    *,
    binary_path: Path,
    binary_sha256: str,
    normalized_types: Sequence[str],
    issues: List[Dict[str, Any]],
) -> bool:
    """Accept only a separately supplied host/runtime execution receipt.

    ``verified_type_chain`` is caller evidence and therefore cannot authenticate
    itself.  The host supplies this receipt through a separate argument after a
    real tool invocation; all artifact and output bindings are checked again.
    """

    if not isinstance(receipt, Mapping):
        issues.append(
            _issue(
                "form_binary_runtime_receipt_required",
                "A binary type chain requires a separately supplied host/runtime receipt; caller JSON alone is not proof.",
            )
        )
        return False

    receipt_id = str(receipt.get("receipt_id") or "").strip()
    host_id = str(receipt.get("host_id") or "").strip()
    runtime_id = str(receipt.get("runtime_id") or "").strip()
    producer_kind = str(receipt.get("producer_kind") or "").strip().lower()
    tool_call_id = str(receipt.get("tool_call_id") or "").strip()
    tool_result_id = str(receipt.get("tool_result_id") or receipt.get("result_id") or "").strip()
    timestamp = str(receipt.get("timestamp") or receipt.get("observed_at") or "").strip()
    exit_status = receipt.get("exit_status", receipt.get("exit_code"))
    receipt_path = str(receipt.get("binary_path") or receipt.get("artifact_path") or "").strip()
    receipt_sha = _normalized_receipt_sha(
        receipt.get("binary_sha256") or receipt.get("artifact_sha256")
    )
    output_types = receipt.get("type_chain_output")
    output_sha = _normalized_receipt_sha(
        receipt.get("type_chain_output_sha256") or receipt.get("output_sha256")
    )

    valid = True
    identifiers = {
        "receipt_id": receipt_id,
        "host_id": host_id,
        "runtime_id": runtime_id,
        "tool_call_id": tool_call_id,
        "tool_result_id": tool_result_id,
    }
    for name, value in identifiers.items():
        if not value:
            issues.append(_issue("form_binary_runtime_receipt_field_missing", f"Runtime receipt requires {name}."))
            valid = False
    if len({value for value in (receipt_id, tool_call_id, tool_result_id) if value}) != 3:
        issues.append(_issue("form_binary_runtime_receipt_ids_not_unique", "Receipt, tool call, and tool result IDs must be distinct."))
        valid = False
    if producer_kind not in _RUNTIME_TYPE_CHAIN_PRODUCER_KINDS:
        issues.append(_issue("form_binary_runtime_producer_kind_invalid", "Runtime type-chain producer kind is not allowlisted.", producer_kind=producer_kind))
        valid = False
    if not receipt_path or not Path(receipt_path).is_absolute() or Path(receipt_path).resolve() != binary_path.resolve():
        issues.append(_issue("form_binary_runtime_binary_path_mismatch", "Runtime receipt must bind the exact binary path."))
        valid = False
    if not re.fullmatch(r"[0-9a-f]{64}", receipt_sha) or receipt_sha != binary_sha256.lower():
        issues.append(_issue("form_binary_runtime_binary_sha256_mismatch", "Runtime receipt must bind the exact binary byte SHA-256."))
        valid = False
    if not isinstance(output_types, (list, tuple)) or [str(item) for item in output_types] != list(normalized_types):
        issues.append(_issue("form_binary_runtime_type_chain_output_mismatch", "Runtime receipt must contain the exact normalized type-chain output."))
        valid = False
    expected_output_sha = sha256(_canonical_type_chain_output(normalized_types)).hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", output_sha) or output_sha != expected_output_sha:
        issues.append(_issue("form_binary_runtime_type_chain_output_sha256_mismatch", "Runtime receipt must bind the exact type-chain output SHA-256."))
        valid = False
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed_timestamp.tzinfo is None:
            raise ValueError("timezone required")
        parsed_timestamp.astimezone(timezone.utc)
    except (TypeError, ValueError):
        issues.append(_issue("form_binary_runtime_timestamp_invalid", "Runtime receipt timestamp must be timezone-aware ISO-8601."))
        valid = False
    if isinstance(exit_status, bool) or not isinstance(exit_status, int) or exit_status != 0:
        issues.append(_issue("form_binary_runtime_exit_status_invalid", "Runtime type-chain verification must have integer exit_status=0."))
        valid = False
    return valid


def _package_version_ambiguous(evidence: Mapping[str, Any]) -> bool:
    package = evidence.get("package")
    if not isinstance(package, Mapping):
        return False
    source = str(package.get("source") or "").strip().lower()
    if source not in {"central", "imported", "central-package", "imported-package"}:
        return False
    versions = package.get("versions")
    if versions is None:
        versions = [package.get("version")] if package.get("version") is not None else []
    if isinstance(versions, str):
        versions = [versions]
    unique_versions = {str(version).strip() for version in versions if str(version).strip()}
    return bool(package.get("ambiguous")) or len(unique_versions) > 1


def _base_type_provenance(
    expected: str,
    evidence: Mapping[str, Any] | None,
    issues: List[Dict[str, Any]],
    runtime_receipt: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    provenance: Dict[str, Any] = {
        "kind": "framework" if expected in {"System.Windows.Forms.Form", "System.Windows.Forms.UserControl"} else "",
        "type_proof_method": "direct_framework_base" if expected in {"System.Windows.Forms.Form", "System.Windows.Forms.UserControl"} else "",
        "type_proven": expected in {"System.Windows.Forms.Form", "System.Windows.Forms.UserControl"},
        "binary_type_proven_by_name": False,
    }
    if provenance["type_proven"]:
        return provenance
    if not isinstance(evidence, Mapping):
        issues.append(_issue("form_base_provenance_missing", "A custom project base requires source or trusted binary type-chain evidence."))
        return provenance
    package_version_ambiguous = _package_version_ambiguous(evidence)
    if package_version_ambiguous:
        issues.append(_issue("form_base_package_version_ambiguous", "Imported or central package evidence has multiple possible versions."))
    artifact = evidence.get("artifact")
    if not isinstance(artifact, Mapping):
        issues.append(_issue("form_base_provenance_missing", "A custom project base requires an exact source or binary artifact."))
        return provenance
    kind = str(artifact.get("kind") or "").strip().lower()
    path = Path(str(artifact.get("path") or ""))
    actual_sha = _artifact_sha256(path, str(artifact.get("sha256") or ""), issues)
    provenance.update({"kind": kind, "artifact_path": str(path), "artifact_sha256": actual_sha})
    if not actual_sha:
        return provenance
    if kind == "source":
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            issues.append(_issue("form_base_source_decode_failed", "The exact source artifact is not valid UTF-8.", error=str(exc)))
            return provenance
        if not package_version_ambiguous and _source_type_chain_proven(_strip_csharp_comments(source), expected):
            provenance.update({"type_proof_method": "parsed_source_type_chain", "type_proven": True})
        else:
            issues.append(_issue("form_source_type_chain_unproven", "The exact source artifact does not prove the custom base reaches Form or UserControl."))
    elif kind == "binary":
        chain = evidence.get("verified_type_chain")
        types = chain.get("types") if isinstance(chain, Mapping) else None
        normalized_types = [_canonical_form_base(item) for item in types] if isinstance(types, (list, tuple)) else []
        runtime_ok = _validate_binary_type_chain_runtime_receipt(
            runtime_receipt,
            binary_path=path,
            binary_sha256=actual_sha,
            normalized_types=normalized_types,
            issues=issues,
        )
        chain_ok = (
            isinstance(chain, Mapping)
            and len(normalized_types) >= 2
            and all(normalized_types)
            and normalized_types[0] == expected
            and normalized_types[-1] in {"System.Windows.Forms.Form", "System.Windows.Forms.UserControl"}
        )
        if runtime_ok and chain_ok and not package_version_ambiguous:
            provenance.update({"type_proof_method": "runtime_binary_type_chain", "type_proven": True})
        else:
            issues.append(_issue("form_binary_type_chain_unproven", "Binary evidence must contain a runtime-correlated, SHA-bound type chain to Form or UserControl."))
    else:
        issues.append(_issue("form_base_artifact_kind_invalid", "Base-type evidence artifact kind must be source or binary.", kind=kind))
    return provenance


def validate_exact_form_inheritance_contract(
    form_source: str,
    *,
    class_name: str,
    expected_base_type: str,
    base_type_evidence: Mapping[str, Any] | None = None,
    runtime_receipt: Mapping[str, Any] | None = None,
) -> DesignerContractResult:
    """Require direct framework inheritance or a proven custom project base."""

    issues: List[Dict[str, Any]] = []
    expected = _canonical_form_base(expected_base_type)
    if not expected:
        issues.append(
            _issue(
                "form_expected_base_invalid",
                "expected_base_type must be exactly Form or UserControl.",
                expected_base_type=expected_base_type,
            )
        )
    source = _strip_csharp_comments(form_source)
    matches = [match for match in _CLASS_DECLARATION.finditer(source) if match.group("name") == class_name]
    if len(matches) != 1:
        issues.append(
            _issue(
                "form_class_declaration_not_unique",
                "The target Form/UserControl class declaration must appear exactly once.",
                class_name=class_name,
                declaration_count=len(matches),
            )
        )
        actual_raw = ""
        actual = ""
    else:
        actual_raw = matches[0].group("bases").split(",", 1)[0].strip()
        actual = _canonical_form_base(actual_raw)
        if expected and actual != expected:
            issues.append(
                _issue(
                    "form_inheritance_not_exact",
                    "The target class must inherit directly from the contracted Form/UserControl base.",
                    class_name=class_name,
                    expected=expected,
                    actual=actual_raw,
                )
            )
    return _result(
        issues,
        contract="exact_form_usercontrol_inheritance",
        class_name=class_name,
        expected_base_type=expected,
        actual_base_type=actual,
        base_type_provenance=_base_type_provenance(
            expected, base_type_evidence, issues, runtime_receipt=runtime_receipt
        ),
    )


def _field_contract(item: Any) -> Dict[str, str]:
    if isinstance(item, str):
        return {"field_name": item}
    if isinstance(item, Mapping):
        return {str(key): str(value) for key, value in item.items() if value is not None}
    raise TypeError("Field contracts must be strings or mappings.")


def _field_name(item: Mapping[str, str]) -> str:
    return str(item.get("field_name") or item.get("field") or item.get("name") or "").strip()


def validate_numeric_repository_contract(
    designer_source: str,
    numeric_fields: Iterable[Any],
) -> DesignerContractResult:
    """Require one exact ``rpsSpin<Field>`` repository per numeric field."""

    model = parse_designer_source(designer_source)
    issues: List[Dict[str, Any]] = []
    normalized: List[Dict[str, str]] = []
    repository_users: Dict[str, List[str]] = {}
    assignments = {(item["name"], item["property"]): item["value"] for item in model.assignments}

    for raw in numeric_fields:
        contract = _field_contract(raw)
        field_name = _field_name(contract)
        if not field_name:
            issues.append(_issue("numeric_field_name_missing", "Every numeric field contract requires field_name."))
            continue
        column_name = str(contract.get("column_name") or "").strip()
        if not column_name:
            candidates = [
                item["name"]
                for item in model.assignments
                if item["property"] == "FieldName" and _csharp_string_value(item["value"]) == field_name
            ]
            if len(candidates) != 1:
                issues.append(
                    _issue(
                        "numeric_field_column_binding_not_unique",
                        "A numeric field must bind to exactly one GridColumn FieldName.",
                        field_name=field_name,
                        candidates=sorted(candidates),
                    )
                )
                continue
            column_name = candidates[0]
        expected_repository = str(contract.get("repository_name") or f"rpsSpin{field_name}")
        canonical_repository = f"rpsSpin{field_name}"
        if expected_repository != canonical_repository:
            issues.append(
                _issue(
                    "numeric_repository_contract_not_canonical",
                    "Numeric repository contracts cannot replace rpsSpin<Field> with a generic alias.",
                    field_name=field_name,
                    expected=canonical_repository,
                    supplied=expected_repository,
                )
            )
            expected_repository = canonical_repository

        display_paths = [
            item["property"]
            for item in model.assignments
            if item["name"] == column_name and item["property"].startswith("DisplayFormat.")
        ]
        if display_paths:
            issues.append(
                _issue(
                    "numeric_gridcolumn_displayformat_forbidden",
                    "Numeric GridColumn DisplayFormat is forbidden; formatting belongs to rpsSpin<Field>.",
                    field_name=field_name,
                    column=column_name,
                    properties=sorted(display_paths),
                )
            )

        column_edit = assignments.get((column_name, "ColumnEdit"), "")
        match = re.fullmatch(rf"this\.({_IDENTIFIER})", column_edit.strip())
        actual_repository = match.group(1) if match else ""
        if not actual_repository:
            issues.append(
                _issue(
                    "numeric_spin_repository_missing",
                    "Numeric GridColumns require ColumnEdit = this.rpsSpin<Field>.",
                    field_name=field_name,
                    column=column_name,
                    expected_repository=expected_repository,
                )
            )
        else:
            repository_users.setdefault(actual_repository, []).append(field_name)
            if actual_repository != expected_repository:
                issues.append(
                    _issue(
                        "numeric_repository_not_field_specific",
                        "Each numeric field requires its own exact rpsSpin<Field> repository.",
                        field_name=field_name,
                        column=column_name,
                        expected=expected_repository,
                        actual=actual_repository,
                    )
                )

        repository = model.controls.get(expected_repository)
        if repository is None or repository.type_name.split(".")[-1] != "RepositoryItemSpinEdit":
            issues.append(
                _issue(
                    "numeric_spin_repository_not_declared",
                    "The field-specific repository must be declared and initialized as RepositoryItemSpinEdit.",
                    field_name=field_name,
                    repository=expected_repository,
                )
            )
        registration = re.search(
            rf"this\.{_IDENTIFIER}\.RepositoryItems\.AddRange\s*\([\s\S]*?"
            rf"this\.{re.escape(expected_repository)}[\s\S]*?\)\s*;",
            model.source,
        )
        edit_offset = model.source.find(f"this.{column_name}.ColumnEdit")
        if registration is None:
            issues.append(
                _issue(
                    "numeric_spin_repository_not_registered",
                    "The field-specific repository must be registered in GridControl.RepositoryItems.",
                    field_name=field_name,
                    repository=expected_repository,
                )
            )
        elif edit_offset >= 0 and registration.start() > edit_offset:
            issues.append(
                _issue(
                    "numeric_spin_repository_registration_order_invalid",
                    "RepositoryItems registration must precede the GridColumn ColumnEdit assignment.",
                    field_name=field_name,
                    repository=expected_repository,
                )
            )
        normalized.append(
            {
                "field_name": field_name,
                "column_name": column_name,
                "repository_name": expected_repository,
                "actual_repository_name": actual_repository,
            }
        )

    for repository, fields in sorted(repository_users.items()):
        if len(fields) > 1:
            issues.append(
                _issue(
                    "numeric_repository_shared",
                    "A RepositoryItemSpinEdit cannot be shared by multiple numeric fields.",
                    repository=repository,
                    fields=sorted(fields),
                )
            )
    return _result(issues, contract="numeric_repositories", fields=normalized)


def _pair_contract(item: Any) -> Dict[str, str]:
    if isinstance(item, Mapping):
        return {str(key): str(value) for key, value in item.items() if value is not None}
    if isinstance(item, Sequence) and not isinstance(item, (str, bytes)):
        values = [str(value) for value in item]
        if len(values) == 2:
            return {"label_name": values[0], "editor_name": values[1]}
        if len(values) == 3:
            return {"field_name": values[0], "label_name": values[1], "editor_name": values[2]}
    raise TypeError("Label/editor pairs must be mappings or two/three-item sequences.")


def _container_size(model: DesignerModel, parent: str) -> Tuple[int, int] | None:
    if parent == "<form>":
        return _parse_size(model.form_properties.get("ClientSize", "")) or _parse_size(
            model.form_properties.get("Size", "")
        )
    control = model.controls.get(parent)
    if control is None:
        return None
    return control.size or _parse_size(control.properties.get("ClientSize", ""))


def _rectangle(control: ControlRecord) -> Tuple[int, int, int, int] | None:
    if control.location is None or control.size is None:
        return None
    x, y = control.location
    width, height = control.size
    return x, y, x + width, y + height


def _rectangles_overlap(first: Tuple[int, int, int, int], second: Tuple[int, int, int, int]) -> bool:
    return min(first[2], second[2]) > max(first[0], second[0]) and min(
        first[3], second[3]
    ) > max(first[1], second[1])


def validate_label_editor_layout_contract(
    designer_source: str,
    label_editor_pairs: Iterable[Any],
    *,
    alignment_tolerance: int = 2,
) -> DesignerContractResult:
    """Validate pair containment, geometry, alignment, clipping, and overlap."""

    model = parse_designer_source(designer_source)
    issues: List[Dict[str, Any]] = []
    normalized: List[Dict[str, Any]] = []
    involved: Dict[str, ControlRecord] = {}
    for raw in label_editor_pairs:
        contract = _pair_contract(raw)
        field_name = _field_name(contract)
        label_name = str(contract.get("label_name") or contract.get("label") or "").strip()
        editor_name = str(contract.get("editor_name") or contract.get("editor") or "").strip()
        expected_parent = str(
            contract.get("container") or contract.get("parent") or contract.get("expected_container") or ""
        ).strip()
        label = model.controls.get(label_name)
        editor = model.controls.get(editor_name)
        if label is None or editor is None:
            issues.append(
                _issue(
                    "label_editor_control_missing",
                    "Every label/editor mapping must resolve both Designer controls.",
                    field_name=field_name,
                    label=label_name,
                    editor=editor_name,
                    missing=[name for name, value in ((label_name, label), (editor_name, editor)) if value is None],
                )
            )
            continue
        involved[label.name] = label
        involved[editor.name] = editor
        if label.parent != editor.parent:
            issues.append(
                _issue(
                    "label_editor_container_mismatch",
                    "A label and its editor must be added to the same container.",
                    field_name=field_name,
                    label_parent=label.parent,
                    editor_parent=editor.parent,
                )
            )
        if expected_parent and (label.parent != expected_parent or editor.parent != expected_parent):
            issues.append(
                _issue(
                    "label_editor_wrong_container",
                    "The label/editor pair is not in its contracted container.",
                    field_name=field_name,
                    expected=expected_parent,
                    label_parent=label.parent,
                    editor_parent=editor.parent,
                )
            )
        label_rect = _rectangle(label)
        editor_rect = _rectangle(editor)
        table_pair = label.table_position is not None or editor.table_position is not None
        if table_pair:
            if label.table_position is None or editor.table_position is None:
                issues.append(
                    _issue(
                        "label_editor_table_position_incomplete",
                        "Both controls in a TableLayoutPanel pair require explicit column and row arguments.",
                        field_name=field_name,
                    )
                )
            elif label.table_position[1] != editor.table_position[1]:
                issues.append(
                    _issue(
                        "label_editor_row_misaligned",
                        "TableLayoutPanel label/editor pairs must occupy the same row.",
                        field_name=field_name,
                        label_position=label.table_position,
                        editor_position=editor.table_position,
                    )
                )
            elif label.table_position[0] >= editor.table_position[0]:
                issues.append(
                    _issue(
                        "label_editor_horizontal_order_invalid",
                        "A label must occupy a table column to the left of its editor.",
                        field_name=field_name,
                        label_position=label.table_position,
                        editor_position=editor.table_position,
                    )
                )
        else:
            if label_rect is None or editor_rect is None:
                issues.append(
                    _issue(
                        "label_editor_geometry_missing",
                        "Non-table label/editor controls require Designer Location and Size.",
                        field_name=field_name,
                        label=label_name,
                        editor=editor_name,
                    )
                )
            else:
                label_center = (label_rect[1] + label_rect[3]) / 2.0
                editor_center = (editor_rect[1] + editor_rect[3]) / 2.0
                if abs(label_center - editor_center) > alignment_tolerance:
                    issues.append(
                        _issue(
                            "label_editor_vertical_alignment_invalid",
                            "Label and editor vertical centers must align within tolerance.",
                            field_name=field_name,
                            tolerance=alignment_tolerance,
                            label_center=label_center,
                            editor_center=editor_center,
                        )
                    )
                if label_rect[2] > editor_rect[0]:
                    issues.append(
                        _issue(
                            "label_editor_horizontal_order_or_overlap_invalid",
                            "A label must end at or before the editor starts.",
                            field_name=field_name,
                            label_bounds=label_rect,
                            editor_bounds=editor_rect,
                        )
                    )
        normalized.append(
            {
                "field_name": field_name,
                "label_name": label_name,
                "editor_name": editor_name,
                "container": expected_parent or label.parent,
            }
        )

    rectangles_by_parent: Dict[str, List[Tuple[str, Tuple[int, int, int, int]]]] = {}
    table_cells: Dict[Tuple[str, int, int], List[str]] = {}
    for name, control in involved.items():
        rect = _rectangle(control)
        if rect is not None:
            rectangles_by_parent.setdefault(control.parent, []).append((name, rect))
            bounds = _container_size(model, control.parent)
            if bounds is None:
                issues.append(
                    _issue(
                        "container_bounds_missing",
                        "Container Size or form ClientSize is required to prove clipping and bounds.",
                        container=control.parent,
                        control=name,
                    )
                )
            elif rect[0] < 0 or rect[1] < 0 or rect[2] > bounds[0] or rect[3] > bounds[1]:
                issues.append(
                    _issue(
                        "control_out_of_container_bounds",
                        "A label/editor control is clipped or outside its container.",
                        container=control.parent,
                        control=name,
                        control_bounds=rect,
                        container_size=bounds,
                    )
                )
        if control.table_position is not None:
            column, row = control.table_position
            table_cells.setdefault((control.parent, column, row), []).append(name)

    for parent, members in sorted(rectangles_by_parent.items()):
        for index, (first_name, first_rect) in enumerate(members):
            for second_name, second_rect in members[index + 1 :]:
                if _rectangles_overlap(first_rect, second_rect):
                    issues.append(
                        _issue(
                            "controls_overlap",
                            "Mapped label/editor controls must not overlap.",
                            container=parent,
                            controls=[first_name, second_name],
                        )
                    )
    for (parent, column, row), names in sorted(table_cells.items()):
        if len(names) > 1:
            issues.append(
                _issue(
                    "tablelayout_cell_overlap",
                    "Mapped controls cannot share the same TableLayoutPanel cell.",
                    container=parent,
                    column=column,
                    row=row,
                    controls=sorted(names),
                )
            )
    return _result(issues, contract="label_editor_layout", pairs=normalized)


def _normalize_wrapper_proofs(proven_wrappers: Iterable[Any]) -> Tuple[set[str], set[str]]:
    type_names: set[str] = set()
    control_names: set[str] = set()
    for item in proven_wrappers:
        if isinstance(item, str):
            type_names.add(item)
            continue
        if not isinstance(item, Mapping):
            raise TypeError("Proven wrappers must be type strings or mappings.")
        proof = item.get("proof") or item.get("evidence") or item.get("evidence_ref")
        if item.get("proven") is not True and not str(proof or "").strip():
            continue
        type_name = str(item.get("type_name") or item.get("type") or "").strip()
        control_name = str(item.get("control_name") or item.get("control") or "").strip()
        if type_name:
            type_names.add(type_name)
        if control_name:
            control_names.add(control_name)
    return type_names, control_names


def _is_year_format(value: str) -> bool:
    decoded = _csharp_string_value(value)
    return decoded is not None and decoded.strip().lower() in {"yyyy", "0000"}


def validate_year_only_dateedit_contract(
    designer_source: str,
    year_fields: Iterable[Any],
    *,
    proven_wrappers: Iterable[Any] = (),
) -> DesignerContractResult:
    """Require canonical ``ymd<Field>`` year-only DateEdit behavior."""

    model = parse_designer_source(designer_source)
    issues: List[Dict[str, Any]] = []
    normalized: List[Dict[str, Any]] = []
    proven_types, proven_controls = _normalize_wrapper_proofs(proven_wrappers)
    for raw in year_fields:
        contract = _field_contract(raw)
        field_name = _field_name(contract)
        if not field_name:
            issues.append(_issue("year_field_name_missing", "Every year-only field requires field_name."))
            continue
        control_name = str(contract.get("control_name") or f"ymd{field_name}")
        canonical_name = f"ymd{field_name}"
        if control_name != canonical_name:
            issues.append(
                _issue(
                    "year_dateedit_name_not_canonical",
                    "Year-only DateEdit names must use ymd<Field>.",
                    field_name=field_name,
                    expected=canonical_name,
                    actual=control_name,
                )
            )
        control = model.controls.get(control_name)
        if control is None:
            issues.append(
                _issue(
                    "year_dateedit_missing",
                    "The year-only control is missing from Designer declarations/initialization.",
                    field_name=field_name,
                    control=control_name,
                )
            )
            continue
        type_tail = control.type_name.split(".")[-1]
        if "DateEdit" not in type_tail and control.type_name not in proven_types and control_name not in proven_controls:
            issues.append(
                _issue(
                    "year_control_not_dateedit",
                    "A year-only ymd<Field> control must be DateEdit or an explicitly proven wrapper.",
                    field_name=field_name,
                    control=control_name,
                    type_name=control.type_name,
                )
            )
            continue
        wrapper_proven = control.type_name in proven_types or control_name in proven_controls
        evidence = {key: value for key, value in control.properties.items() if key.startswith("Properties.")}
        if not wrapper_proven:
            mask_ok = any(
                key in {"Properties.Mask.EditMask", "Properties.EditMask"} and _is_year_format(value)
                for key, value in evidence.items()
            )
            display_ok = any(
                (
                    key in {"Properties.DisplayFormat.FormatString", "Properties.EditFormat.FormatString"}
                    and _is_year_format(value)
                )
                or (key == "Properties.Mask.UseMaskAsDisplayFormat" and value.strip().lower() == "true")
                for key, value in evidence.items()
            )
            year_view_properties = [
                key
                for key, value in evidence.items()
                if "view" in key.lower() and "year" in value.lower()
            ]
            view_ok = bool(year_view_properties)
            selection_ok = any(
                (
                    "selection" in key.lower()
                    or key.lower().endswith("vistacalendarviewstyle")
                )
                and "year" in value.lower()
                for key, value in evidence.items()
            )
            missing = [
                name
                for name, passed in (
                    ("year_mask", mask_ok),
                    ("year_view", view_ok),
                    ("year_display", display_ok),
                    ("year_selection", selection_ok),
                )
                if not passed
            ]
            if missing:
                issues.append(
                    _issue(
                        "year_dateedit_static_contract_incomplete",
                        "Unproven DateEdit controls require year mask, view, display, and selection properties in Designer.",
                        field_name=field_name,
                        control=control_name,
                        missing=missing,
                    )
                )
        normalized.append(
            {
                "field_name": field_name,
                "control_name": control_name,
                "type_name": control.type_name,
                "wrapper_proven": wrapper_proven,
            }
        )
    return _result(issues, contract="year_only_dateedit", fields=normalized)


def _scan_pb_components(text: str, component_name: str) -> List[str]:
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(component_name)}\s*\(", re.IGNORECASE)
    components: List[str] = []
    for match in pattern.finditer(text):
        start = match.end() - 1
        depth = 0
        quoted = False
        index = start
        while index < len(text):
            char = text[index]
            if quoted:
                if char == "~" and index + 1 < len(text):
                    index += 2
                    continue
                if char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    components.append(text[start + 1 : index])
                    break
            index += 1
    return components


_PB_ATTRIBUTE = re.compile(
    r"(?<![A-Za-z0-9_.#])(?P<key>[A-Za-z_][A-Za-z0-9_.#]*)\s*=\s*"
    r"(?:\"(?P<quoted>(?:~.|[^\"])*)\"|(?P<bare>[^\s)]+))",
    re.IGNORECASE,
)


def _pb_attributes(component: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for match in _PB_ATTRIBUTE.finditer(component):
        raw = match.group("quoted") if match.group("quoted") is not None else match.group("bare")
        values[match.group("key").lower()] = str(raw).replace('~"', '"').replace("~~", "~")
    return values


def _pb_int(attributes: Mapping[str, str], key: str) -> int | None:
    raw = str(attributes.get(key, "")).strip().strip('"')
    return int(raw) if re.fullmatch(r"-?\d+", raw) else None


def parse_srd_caption_map(srd_text: str) -> Dict[str, Dict[str, Any]]:
    """Return SRD visual fields and text controls without trusting caller captions."""

    columns: Dict[str, Dict[str, Any]] = {}
    texts: Dict[str, Dict[str, Any]] = {}
    for component in _scan_pb_components(str(srd_text or ""), "column"):
        attrs = _pb_attributes(component)
        name = attrs.get("name", "")
        if not name:
            continue
        item = {**attrs, "x": _pb_int(attrs, "x"), "y": _pb_int(attrs, "y"), "width": _pb_int(attrs, "width"), "height": _pb_int(attrs, "height")}
        columns.setdefault(name.casefold(), item)
    for component in _scan_pb_components(str(srd_text or ""), "text"):
        attrs = _pb_attributes(component)
        name = attrs.get("name", "")
        if not name:
            continue
        item = {**attrs, "x": _pb_int(attrs, "x"), "y": _pb_int(attrs, "y"), "width": _pb_int(attrs, "width"), "height": _pb_int(attrs, "height")}
        texts.setdefault(name.casefold(), item)
    return {"columns": columns, "texts": texts}


def _derive_srd_caption(
    parsed: Mapping[str, Dict[str, Dict[str, Any]]],
    field_name: str,
    text_name: str,
) -> Tuple[str, str]:
    columns = parsed["columns"]
    texts = parsed["texts"]
    field = columns.get(field_name.casefold())
    if field is None:
        raise ValueError("srd_field_not_found")
    if text_name:
        text = texts.get(text_name.casefold())
        if text is None:
            raise ValueError("srd_text_not_found")
        return str(text.get("text", "")), str(text.get("name", text_name))

    conventional_names = (f"t_{field_name}".casefold(), f"{field_name}_t".casefold())
    conventional = [texts[name] for name in conventional_names if name in texts]
    if len(conventional) == 1:
        item = conventional[0]
        return str(item.get("text", "")), str(item.get("name", ""))

    if None in (field.get("x"), field.get("y"), field.get("width"), field.get("height")):
        raise ValueError("srd_caption_mapping_ambiguous")
    fx = int(field["x"])
    fy = int(field["y"])
    fw = int(field["width"])
    fh = int(field["height"])
    scored: List[Tuple[int, str, Dict[str, Any]]] = []
    for name, item in texts.items():
        if None in (item.get("x"), item.get("y"), item.get("width"), item.get("height")):
            continue
        tx = int(item["x"])
        ty = int(item["y"])
        tw = int(item["width"])
        th = int(item["height"])
        vertical_overlap = min(fy + fh, ty + th) - max(fy, ty)
        horizontal_overlap = min(fx + fw, tx + tw) - max(fx, tx)
        if vertical_overlap > 0 and tx + tw <= fx:
            score = fx - (tx + tw)
        elif horizontal_overlap > 0:
            score = abs((fx * 2 + fw) - (tx * 2 + tw)) + abs(fy - ty)
        else:
            continue
        scored.append((score, name, item))
    scored.sort(key=lambda value: (value[0], value[1]))
    if not scored or (len(scored) > 1 and scored[0][0] == scored[1][0]):
        raise ValueError("srd_caption_mapping_ambiguous")
    item = scored[0][2]
    return str(item.get("text", "")), str(item.get("name", scored[0][1]))


def validate_srd_caption_contract(
    designer_source: str,
    *,
    srd_path: str | os.PathLike[str],
    srd_sha256: str,
    field_mappings: Iterable[Mapping[str, Any]],
    maximum_bytes: int = 2_000_000,
) -> DesignerContractResult:
    """Re-read a bound SRD and re-derive every Designer caption from its bytes."""

    issues: List[Dict[str, Any]] = []
    path = Path(srd_path).expanduser()
    resolved_path = ""
    actual_sha = ""
    srd_text = ""
    if not path.is_absolute():
        issues.append(_issue("srd_path_not_absolute", "Caption provenance requires an exact absolute SRD path.", path=str(path)))
    elif path.suffix.lower() != ".srd":
        issues.append(_issue("srd_path_not_srd", "Caption provenance must bind an .srd file.", path=str(path)))
    elif not path.is_file():
        issues.append(_issue("srd_file_missing", "The bound SRD file does not exist.", path=str(path)))
    else:
        resolved = path.resolve(strict=True)
        resolved_path = str(resolved)
        size = resolved.stat().st_size
        if size > maximum_bytes:
            issues.append(
                _issue(
                    "srd_file_too_large",
                    "The SRD exceeds the bounded static-validator input limit.",
                    path=resolved_path,
                    size_bytes=size,
                    maximum_bytes=maximum_bytes,
                )
            )
        else:
            raw = resolved.read_bytes()
            actual_sha = sha256(raw).hexdigest()
            if not re.fullmatch(r"[0-9a-fA-F]{64}", str(srd_sha256 or "")):
                issues.append(_issue("srd_sha256_invalid", "A complete SHA-256 digest is required."))
            elif actual_sha.lower() != str(srd_sha256).lower():
                issues.append(
                    _issue(
                        "srd_sha256_mismatch",
                        "The current SRD bytes do not match the bound SHA-256.",
                        path=resolved_path,
                        expected=str(srd_sha256).lower(),
                        actual=actual_sha,
                    )
                )
            try:
                srd_text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                try:
                    srd_text = raw.decode("cp949")
                except UnicodeDecodeError as exc:
                    issues.append(_issue("srd_decode_failed", "The SRD is neither UTF-8 nor CP949.", error=str(exc)))

    model = parse_designer_source(designer_source)
    parsed = parse_srd_caption_map(srd_text) if srd_text and not any(issue["code"] == "srd_sha256_mismatch" for issue in issues) else {"columns": {}, "texts": {}}
    verified: List[Dict[str, str]] = []
    seen_fields: set[str] = set()
    for raw_mapping in field_mappings:
        mapping = {str(key): value for key, value in dict(raw_mapping).items()}
        field_name = str(mapping.get("field_name") or mapping.get("field") or "").strip()
        srd_field = str(mapping.get("srd_field_name") or field_name).strip()
        srd_text_name = str(mapping.get("srd_text_name") or mapping.get("text_name") or "").strip()
        member = str(mapping.get("designer_member") or mapping.get("member") or mapping.get("label_name") or mapping.get("column_name") or "").strip()
        property_name = str(mapping.get("property") or ("Caption" if member.startswith("col") else "Text")).strip()
        if not field_name or not member:
            issues.append(
                _issue(
                    "caption_field_mapping_incomplete",
                    "Each caption mapping requires field_name and designer_member.",
                    mapping=mapping,
                )
            )
            continue
        key = field_name.casefold()
        if key in seen_fields:
            issues.append(_issue("caption_field_mapping_duplicate", "Each field may be mapped once.", field_name=field_name))
            continue
        seen_fields.add(key)
        if not parsed["columns"]:
            continue
        try:
            expected_caption, matched_text_name = _derive_srd_caption(parsed, srd_field, srd_text_name)
        except ValueError as exc:
            issues.append(
                _issue(
                    str(exc),
                    "The SRD field-to-caption relationship could not be proven exactly.",
                    field_name=field_name,
                    srd_field_name=srd_field,
                    srd_text_name=srd_text_name,
                )
            )
            continue
        control = model.controls.get(member)
        actual_raw = control.properties.get(property_name, "") if control else ""
        actual_caption = _csharp_string_value(actual_raw)
        if control is None or actual_caption is None:
            issues.append(
                _issue(
                    "designer_caption_assignment_missing",
                    "The mapped Designer member requires a direct static caption assignment.",
                    field_name=field_name,
                    member=member,
                    property=property_name,
                )
            )
        elif actual_caption != expected_caption:
            issues.append(
                _issue(
                    "designer_caption_not_rederived_from_srd",
                    "Designer caption differs from the caption re-derived from the bound SRD bytes.",
                    field_name=field_name,
                    member=member,
                    expected=expected_caption,
                    actual=actual_caption,
                )
            )
        verified.append(
            {
                "field_name": field_name,
                "srd_field_name": srd_field,
                "srd_text_name": matched_text_name,
                "designer_member": member,
                "property": property_name,
                "caption": expected_caption,
            }
        )
    return _result(
        issues,
        contract="srd_caption_provenance",
        srd_path=resolved_path or str(path),
        srd_sha256=actual_sha,
        field_mappings=verified,
    )


def _read_exact_text_artifact(
    path_value: str | os.PathLike[str],
    expected_sha256: str,
    *,
    required_suffix: str,
    maximum_bytes: int,
    artifact_kind: str,
) -> Tuple[str, str, str, List[Dict[str, Any]]]:
    issues: List[Dict[str, Any]] = []
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        return "", "", "", [
            _issue(f"{artifact_kind}_path_not_absolute", "Artifact binding requires an exact absolute path.", path=str(path))
        ]
    if path.suffix.lower() != required_suffix.lower():
        return "", "", "", [
            _issue(
                f"{artifact_kind}_suffix_invalid",
                f"The bound artifact must use {required_suffix}.",
                path=str(path),
            )
        ]
    if not path.is_file():
        return "", "", "", [
            _issue(f"{artifact_kind}_file_missing", "The bound artifact does not exist.", path=str(path))
        ]
    resolved = path.resolve(strict=True)
    size = resolved.stat().st_size
    if size > maximum_bytes:
        return str(resolved), "", "", [
            _issue(
                f"{artifact_kind}_file_too_large",
                "The bound artifact exceeds the static-validator byte limit.",
                path=str(resolved),
                size_bytes=size,
                maximum_bytes=maximum_bytes,
            )
        ]
    raw = resolved.read_bytes()
    digest = sha256(raw).hexdigest()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(expected_sha256 or "")):
        issues.append(_issue(f"{artifact_kind}_sha256_invalid", "A complete SHA-256 digest is required."))
    elif digest != str(expected_sha256).lower():
        issues.append(
            _issue(
                f"{artifact_kind}_sha256_mismatch",
                "Current artifact bytes do not match the bound SHA-256.",
                path=str(resolved),
                expected=str(expected_sha256).lower(),
                actual=digest,
            )
        )
    text = ""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("cp949")
        except UnicodeDecodeError as exc:
            issues.append(_issue(f"{artifact_kind}_decode_failed", "Artifact decoding failed.", error=str(exc)))
    return str(resolved), digest, text, issues


def _contract_bool(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"1", "true", "yes"}


def validate_pb_field_lineage_contract(
    designer_source: str,
    *,
    srd_path: str | os.PathLike[str],
    srd_sha256: str,
    result_fields: Iterable[str],
    field_lineages: Iterable[Mapping[str, Any]],
    maximum_srd_bytes: int = 2_000_000,
) -> DesignerContractResult:
    """Bind each PB field through result, editor, GridColumn, and repository."""

    bound_path, actual_sha, srd_text, issues = _read_exact_text_artifact(
        srd_path,
        srd_sha256,
        required_suffix=".srd",
        maximum_bytes=maximum_srd_bytes,
        artifact_kind="lineage_srd",
    )
    parsed = parse_srd_caption_map(srd_text) if srd_text and not issues else {"columns": {}, "texts": {}}
    model = parse_designer_source(designer_source)
    results = {str(field) for field in result_fields}
    verified: List[Dict[str, Any]] = []
    numeric_contracts: List[Dict[str, str]] = []
    seen_fields: set[str] = set()

    for raw in field_lineages:
        mapping = dict(raw)
        field_name = str(mapping.get("field_name") or mapping.get("field") or "").strip()
        pb_field = str(mapping.get("pb_field_name") or mapping.get("pb_field") or "").strip()
        result_field = str(mapping.get("result_field_name") or mapping.get("result_field") or "").strip()
        binding_control = str(mapping.get("binding_control_name") or mapping.get("binding_control") or "").strip()
        grid_column = str(mapping.get("grid_column_name") or mapping.get("grid_column") or "").strip()
        required = {
            "field_name": field_name,
            "pb_field_name": pb_field,
            "result_field_name": result_field,
            "binding_control_name": binding_control,
            "grid_column_name": grid_column,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            issues.append(
                _issue(
                    "field_lineage_mapping_incomplete",
                    "Each lineage requires PB, result, BindingField control, and GridColumn identities.",
                    missing=missing,
                    mapping=mapping,
                )
            )
            continue
        field_key = field_name.casefold()
        if field_key in seen_fields:
            issues.append(_issue("field_lineage_duplicate", "Each logical field may have one lineage.", field_name=field_name))
            continue
        seen_fields.add(field_key)

        if parsed["columns"] and pb_field.casefold() not in parsed["columns"]:
            issues.append(
                _issue(
                    "field_lineage_pb_field_missing",
                    "The exact PB field does not exist in the SHA-bound SRD.",
                    field_name=field_name,
                    pb_field_name=pb_field,
                )
            )
        if result_field not in results:
            issues.append(
                _issue(
                    "field_lineage_result_field_missing",
                    "The mapped result field is absent from authoritative result_fields.",
                    field_name=field_name,
                    result_field_name=result_field,
                )
            )
        binding = model.controls.get(binding_control)
        actual_binding = _csharp_string_value(binding.properties.get("BindingField", "")) if binding else None
        if actual_binding != result_field:
            issues.append(
                _issue(
                    "field_lineage_bindingfield_mismatch",
                    "Editor BindingField must equal the mapped result field exactly.",
                    field_name=field_name,
                    control=binding_control,
                    expected=result_field,
                    actual=actual_binding,
                )
            )
        column = model.controls.get(grid_column)
        actual_grid_field = _csharp_string_value(column.properties.get("FieldName", "")) if column else None
        if actual_grid_field != result_field:
            issues.append(
                _issue(
                    "field_lineage_grid_fieldname_mismatch",
                    "GridColumn FieldName must equal the mapped result field exactly.",
                    field_name=field_name,
                    column=grid_column,
                    expected=result_field,
                    actual=actual_grid_field,
                )
            )

        numeric = _contract_bool(mapping.get("numeric"))
        repository_name = str(mapping.get("repository_name") or "").strip()
        if numeric or repository_name:
            expected_repository = f"rpsSpin{result_field}"
            if repository_name and repository_name != expected_repository:
                issues.append(
                    _issue(
                        "field_lineage_repository_name_mismatch",
                        "Numeric lineage repository must use exact rpsSpin<ResultField> naming.",
                        field_name=field_name,
                        expected=expected_repository,
                        actual=repository_name,
                    )
                )
            numeric_contracts.append(
                {
                    "field_name": result_field,
                    "column_name": grid_column,
                    "repository_name": expected_repository,
                }
            )
            repository_name = expected_repository
        verified.append(
            {
                "field_name": field_name,
                "pb_field_name": pb_field,
                "result_field_name": result_field,
                "binding_control_name": binding_control,
                "grid_column_name": grid_column,
                "repository_name": repository_name,
            }
        )

    if numeric_contracts:
        numeric_result = validate_numeric_repository_contract(designer_source, numeric_contracts)
        issues.extend(dict(issue) for issue in numeric_result.issues)
    return _result(
        issues,
        contract="pb_binding_result_grid_repository_lineage",
        srd_path=bound_path or str(srd_path),
        srd_sha256=actual_sha,
        result_fields=sorted(results),
        field_lineages=verified,
    )


def _is_input_control(control: ControlRecord) -> bool:
    lowered = control.type_name.lower()
    if any(token in lowered for token in _NON_INPUT_TYPE_TOKENS if token != "button"):
        return False
    if any(token in lowered for token in _INPUT_TYPE_TOKENS):
        return True
    if "button" in lowered:
        return False
    return bool(_INPUT_NAME.match(control.name))


def validate_designer_tab_order_contract(
    designer_source: str,
    *,
    input_names: Iterable[str] | None = None,
) -> DesignerContractResult:
    """Enforce row-major TabIndex order independently inside each container."""

    model = parse_designer_source(designer_source)
    issues: List[Dict[str, Any]] = []
    selected_names = set(input_names) if input_names is not None else None
    for call in model.set_child_index:
        child = model.controls.get(str(call["child"]))
        if child is not None and child.parent != call["parent"]:
            issues.append(
                _issue(
                    "setchildindex_container_mismatch",
                    "SetChildIndex must target the same container that owns the control.",
                    child=call["child"],
                    controls_add_parent=child.parent,
                    setchildindex_parent=call["parent"],
                )
            )
    for parent in sorted({call["parent"] for call in model.set_child_index}):
        indexes = [int(call["index"]) for call in model.set_child_index if call["parent"] == parent]
        if len(indexes) != len(set(indexes)):
            issues.append(
                _issue(
                    "setchildindex_duplicate_index",
                    "SetChildIndex values must be unique within a container.",
                    container=parent,
                    indexes=indexes,
                )
            )

    inputs = [
        control
        for control in model.controls.values()
        if _is_input_control(control) and (selected_names is None or control.name in selected_names)
    ]
    groups: Dict[str, List[ControlRecord]] = {}
    for control in inputs:
        groups.setdefault(control.parent, []).append(control)
    contracts: List[Dict[str, Any]] = []
    for parent, members in sorted(groups.items()):
        def spatial_key(control: ControlRecord) -> Tuple[int, int, str]:
            if control.table_position is not None:
                column, row = control.table_position
                return row, column, control.name
            if control.location is not None:
                x, y = control.location
                return y, x, control.name
            return 2**31 - 1, 2**31 - 1, control.name

        ordered = sorted(members, key=spatial_key)
        missing_position = [item.name for item in ordered if item.table_position is None and item.location is None]
        if missing_position:
            issues.append(
                _issue(
                    "input_spatial_position_missing",
                    "Input controls require Location or TableLayoutPanel column/row placement.",
                    container=parent,
                    controls=missing_position,
                )
            )
        missing_tab = [item.name for item in ordered if item.tab_index is None]
        if missing_tab:
            issues.append(
                _issue(
                    "input_tabindex_missing",
                    "Every input requires an explicit Designer-owned TabIndex.",
                    container=parent,
                    controls=missing_tab,
                )
            )
        indexes = [item.tab_index for item in ordered]
        if not missing_tab:
            integer_indexes = [int(value) for value in indexes if value is not None]
            if len(integer_indexes) != len(set(integer_indexes)):
                issues.append(
                    _issue(
                        "input_tabindex_duplicate",
                        "Input TabIndex values must be unique within each container.",
                        container=parent,
                        indexes=integer_indexes,
                    )
                )
            expected = list(range(min(integer_indexes), min(integer_indexes) + len(integer_indexes)))
            if integer_indexes != expected:
                issues.append(
                    _issue(
                        "input_tabindex_spatial_order_invalid",
                        "TabIndex must be contiguous in left-to-right, top-to-bottom order within each container.",
                        container=parent,
                        spatial_order=[item.name for item in ordered],
                        expected=expected,
                        actual=integer_indexes,
                    )
                )
        contracts.append(
            {
                "container": parent,
                "spatial_order": [item.name for item in ordered],
                "tab_indexes": indexes,
                "table_positions": [item.table_position for item in ordered],
            }
        )
    return _result(
        issues,
        contract="designer_containment_and_tab_order",
        containers=contracts,
        controls_add=[dict(item) for item in model.controls_add],
        set_child_index=[dict(item) for item in model.set_child_index],
    )


def validate_static_designer_ownership_contract(
    designer_source: str,
    code_behind_source: str,
    *,
    dynamic_property_allowlist: Iterable[str] = (),
) -> DesignerContractResult:
    """Reject design-time construction/layout/property assignments in code-behind."""

    model = parse_designer_source(designer_source)
    source = _mask_csharp_noncode(code_behind_source)
    allowlist = {str(item).strip() for item in dynamic_property_allowlist}
    issues: List[Dict[str, Any]] = []
    control_names = set(model.controls)
    for match in _CODE_BEHIND_INITIALIZER.finditer(source):
        name = match.group("name")
        if name in control_names and (
            match.group("qualified")
            or (
                not _unqualified_initializer_is_local(source, match.start())
                and not _unqualified_member_is_shadowed(source, name, match.start())
            )
        ):
            issues.append(
                _issue(
                    "static_control_construction_in_code_behind",
                    "Control construction is Designer-owned.",
                    control=name,
                )
            )
    for match in _CODE_BEHIND_ASSIGNMENT.finditer(source):
        name = match.group("name")
        property_name = match.group("property")
        identity = f"{name}.{property_name}"
        if (
            name not in control_names
            or identity in allowlist
            or (
                not match.group("qualified")
                and _unqualified_member_is_shadowed(source, name, match.start())
            )
        ):
            continue
        if property_name == "DataSource" or property_name.startswith("DataSource."):
            continue
        if _is_static_designer_property(property_name):
            issues.append(
                _issue(
                    "static_designer_property_in_code_behind",
                    "Static UI properties belong in the companion Designer source.",
                    control=name,
                    property=property_name,
                    value=code_behind_source[match.start("value"):match.end("value")].strip(),
                )
            )
    collection_matches = []
    for match in _CODE_BEHIND_COLLECTION.finditer(source):
        name = match.group("name")
        if name not in control_names:
            continue
        if not match.group("qualified") and _unqualified_member_is_shadowed(source, name, match.start()):
            continue
        collection_matches.append(match)
    if collection_matches or _FORM_COLLECTION.search(source):
        issues.append(
            _issue(
                "static_collection_wiring_in_code_behind",
                "Parent containment, z-order, columns, and repositories are Designer-owned.",
            )
        )
    event_matches = []
    for match in _CODE_BEHIND_EVENT.finditer(source):
        name = match.group("name")
        if name not in control_names:
            continue
        if not match.group("qualified") and _unqualified_member_is_shadowed(source, name, match.start()):
            continue
        event_matches.append(match)
    if event_matches or _FORM_EVENT.search(source):
        issues.append(
            _issue(
                "static_event_wiring_in_code_behind",
                "Events on Designer-owned controls and forms belong in the companion Designer source.",
            )
        )
    return _result(issues, contract="static_designer_ownership", allowlist=sorted(allowlist))


def validate_exact_baseline_property_preservation_contract(
    current_designer_source: str,
    *,
    baseline_designer_path: str | os.PathLike[str],
    baseline_designer_sha256: str,
    maximum_baseline_bytes: int = 2_000_000,
) -> DesignerContractResult:
    """Re-read a SHA-bound Designer baseline and preserve every static value."""

    bound_path, actual_sha, baseline_source, issues = _read_exact_text_artifact(
        baseline_designer_path,
        baseline_designer_sha256,
        required_suffix=".cs",
        maximum_bytes=maximum_baseline_bytes,
        artifact_kind="baseline_designer",
    )
    if bound_path and not bound_path.lower().endswith(".designer.cs"):
        issues.append(
            _issue(
                "baseline_designer_filename_invalid",
                "The exact baseline must be a .Designer.cs artifact.",
                path=bound_path,
            )
        )
    current = parse_designer_source(current_designer_source)
    baseline = parse_designer_source(baseline_source) if baseline_source and not issues else None
    preserved: List[Dict[str, str]] = []
    if baseline is not None:
        for name, baseline_control in sorted(baseline.controls.items()):
            current_control = current.controls.get(name)
            if current_control is None:
                issues.append(
                    _issue(
                        "baseline_control_removed",
                        "A control present in the exact Designer baseline was removed.",
                        control=name,
                    )
                )
                continue
            structural_checks = {
                "type_name": (baseline_control.type_name, current_control.type_name),
                "parent": (baseline_control.parent, current_control.parent),
                "table_position": (baseline_control.table_position, current_control.table_position),
                "child_index": (baseline_control.child_index, current_control.child_index),
            }
            for property_name, (expected, actual) in structural_checks.items():
                if expected != actual:
                    issues.append(
                        _issue(
                            "baseline_control_structure_changed",
                            "Control type, containment, table cell, and z-order must match the exact baseline.",
                            control=name,
                            property=property_name,
                            expected=expected,
                            actual=actual,
                        )
                    )
            for property_name, expected_value in sorted(baseline_control.properties.items()):
                actual_value = current_control.properties.get(property_name)
                if actual_value is None:
                    issues.append(
                        _issue(
                            "baseline_designer_property_removed",
                            "A static property assignment from the exact baseline was removed.",
                            control=name,
                            property=property_name,
                            expected=expected_value,
                        )
                    )
                elif _normalized_csharp_value(actual_value) != _normalized_csharp_value(expected_value):
                    issues.append(
                        _issue(
                            "baseline_designer_property_changed",
                            "A static Designer property differs from the exact SHA-bound baseline.",
                            control=name,
                            property=property_name,
                            expected=expected_value,
                            actual=actual_value,
                        )
                    )
                else:
                    preserved.append({"control": name, "property": property_name})
        for property_name, expected_value in sorted(baseline.form_properties.items()):
            actual_value = current.form_properties.get(property_name)
            if actual_value is None:
                issues.append(
                    _issue(
                        "baseline_form_property_removed",
                        "A form-level static property from the exact baseline was removed.",
                        property=property_name,
                        expected=expected_value,
                    )
                )
            elif _normalized_csharp_value(actual_value) != _normalized_csharp_value(expected_value):
                issues.append(
                    _issue(
                        "baseline_form_property_changed",
                        "A form-level static property differs from the exact SHA-bound baseline.",
                        property=property_name,
                        expected=expected_value,
                        actual=actual_value,
                    )
                )
            else:
                preserved.append({"control": "<form>", "property": property_name})
    return _result(
        issues,
        contract="exact_baseline_property_preservation",
        baseline_designer_path=bound_path or str(baseline_designer_path),
        baseline_designer_sha256=actual_sha,
        preserved_properties=preserved,
    )


def validate_pb_designer_ui_contract(
    designer_source: str,
    *,
    form_source: str = "",
    form_class_name: str = "",
    expected_base_type: str = "",
    base_type_evidence: Mapping[str, Any] | None = None,
    runtime_receipt: Mapping[str, Any] | None = None,
    numeric_fields: Iterable[Any] = (),
    field_lineages: Iterable[Mapping[str, Any]] = (),
    result_fields: Iterable[str] = (),
    label_editor_pairs: Iterable[Any] = (),
    year_fields: Iterable[Any] = (),
    proven_year_wrappers: Iterable[Any] = (),
    srd_path: str | os.PathLike[str] | None = None,
    srd_sha256: str = "",
    caption_field_mappings: Iterable[Mapping[str, Any]] = (),
    code_behind_source: str = "",
    input_names: Iterable[str] | None = None,
    dynamic_property_allowlist: Iterable[str] = (),
    baseline_designer_path: str | os.PathLike[str] | None = None,
    baseline_designer_sha256: str = "",
) -> DesignerContractResult:
    """Run every requested PB Designer UI contract as one static gate."""

    numeric_fields = tuple(numeric_fields)
    field_lineages = tuple(field_lineages)
    result_fields = tuple(result_fields)
    label_editor_pairs = tuple(label_editor_pairs)
    year_fields = tuple(year_fields)
    proven_year_wrappers = tuple(proven_year_wrappers)
    caption_field_mappings = tuple(caption_field_mappings)
    results = [
        validate_numeric_repository_contract(designer_source, numeric_fields),
        validate_label_editor_layout_contract(designer_source, label_editor_pairs),
        validate_year_only_dateedit_contract(
            designer_source, year_fields, proven_wrappers=proven_year_wrappers
        ),
        validate_designer_tab_order_contract(designer_source, input_names=input_names),
    ]
    if form_source or form_class_name or expected_base_type:
        results.append(
            validate_exact_form_inheritance_contract(
                form_source,
                class_name=form_class_name,
                expected_base_type=expected_base_type,
                base_type_evidence=base_type_evidence,
                runtime_receipt=runtime_receipt,
            )
        )
    if field_lineages:
        if srd_path is None:
            results.append(
                _result(
                    [_issue("lineage_srd_path_missing", "Field lineage requires an exact SHA-bound SRD path.")],
                    contract="pb_binding_result_grid_repository_lineage",
                )
            )
        else:
            results.append(
                validate_pb_field_lineage_contract(
                    designer_source,
                    srd_path=srd_path,
                    srd_sha256=srd_sha256,
                    result_fields=result_fields,
                    field_lineages=field_lineages,
                )
            )
    if caption_field_mappings or srd_path is not None or srd_sha256:
        if srd_path is None:
            results.append(
                _result(
                    [_issue("srd_path_missing", "Caption mappings require an exact bound SRD path.")],
                    contract="srd_caption_provenance",
                )
            )
        else:
            results.append(
                validate_srd_caption_contract(
                    designer_source,
                    srd_path=srd_path,
                    srd_sha256=srd_sha256,
                    field_mappings=caption_field_mappings,
                )
            )
    if code_behind_source.strip():
        results.append(
            validate_static_designer_ownership_contract(
                designer_source,
                code_behind_source,
                dynamic_property_allowlist=dynamic_property_allowlist,
            )
        )
    if baseline_designer_path is not None or baseline_designer_sha256:
        if baseline_designer_path is None:
            results.append(
                _result(
                    [_issue("baseline_designer_path_missing", "Baseline preservation requires an exact Designer path.")],
                    contract="exact_baseline_property_preservation",
                )
            )
        else:
            results.append(
                validate_exact_baseline_property_preservation_contract(
                    designer_source,
                    baseline_designer_path=baseline_designer_path,
                    baseline_designer_sha256=baseline_designer_sha256,
                )
            )
    issues = [dict(issue) for result in results for issue in result.issues]
    return _result(
        issues,
        contract="pb_designer_ui_contract",
        validators=[result.metadata.get("contract", "") for result in results],
        validator_results=[result.to_dict() for result in results],
        static_properties_owner="Designer",
    )


# Explicit aliases keep granular callers readable without creating alternate behavior.
validate_numeric_grid_repositories = validate_numeric_repository_contract
validate_label_editor_pairs = validate_label_editor_layout_contract
validate_year_only_date_edits = validate_year_only_dateedit_contract
validate_caption_provenance = validate_srd_caption_contract
validate_tab_order = validate_designer_tab_order_contract
validate_static_designer_ownership = validate_static_designer_ownership_contract
validate_form_usercontrol_inheritance = validate_exact_form_inheritance_contract
validate_field_lineage = validate_pb_field_lineage_contract
validate_baseline_property_preservation = validate_exact_baseline_property_preservation_contract


__all__ = [
    "ControlRecord",
    "DesignerContractResult",
    "DesignerModel",
    "parse_designer_source",
    "parse_srd_caption_map",
    "validate_baseline_property_preservation",
    "validate_caption_provenance",
    "validate_designer_tab_order_contract",
    "validate_exact_baseline_property_preservation_contract",
    "validate_exact_form_inheritance_contract",
    "validate_field_lineage",
    "validate_form_usercontrol_inheritance",
    "validate_label_editor_layout_contract",
    "validate_label_editor_pairs",
    "validate_numeric_grid_repositories",
    "validate_numeric_repository_contract",
    "validate_pb_designer_ui_contract",
    "validate_pb_field_lineage_contract",
    "validate_srd_caption_contract",
    "validate_static_designer_ownership",
    "validate_static_designer_ownership_contract",
    "validate_tab_order",
    "validate_year_only_date_edits",
    "validate_year_only_dateedit_contract",
]
