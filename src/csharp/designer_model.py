"""Retained csharp syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple
import re


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
    assignments: Tuple[Dict[str, Any], ...]
    source: str = field(repr=False, default="")


def _strip_csharp_comments(source: str) -> str:
    from .lexer import mask_comments
    return mask_comments(str(source or ""))


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
    from .lexer import _scan_csharp
    code, _ = _scan_csharp(designer_source)
    def code_matches(pattern):
        for match in pattern.finditer(source):
            first = match.start() + len(match[0]) - len(match[0].lstrip())
            if code[first:first+1].strip():
                yield match
    type_names: Dict[str, str] = {}
    for match in code_matches(_CONTROL_DECLARATION):
        type_names[match.group("name")] = match.group("type")
    for match in code_matches(_CONTROL_INITIALIZER):
        type_name = match.group("type")
        if type_name.split(".")[-1] not in {"Point", "PointF", "Size", "SizeF", "Padding", "Font"}:
            type_names[match.group("name")] = type_name

    property_values: Dict[str, Dict[str, str]] = {}
    assignments: List[Dict[str, Any]] = []
    for match in code_matches(_ASSIGNMENT):
        name = match.group("name")
        property_path = match.group("property")
        value = match.group("value").strip()
        property_values.setdefault(name, {})[property_path] = value
        first = match.start() + len(match[0]) - len(match[0].lstrip())
        assignments.append({"name": name, "property": property_path, "value": value,
                            "line": source.count('\n', 0, first) + 1})

    form_properties: Dict[str, str] = {}
    for match in code_matches(_FORM_ASSIGNMENT):
        property_name = match.group("property")
        if "." not in property_name and property_name not in type_names:
            form_properties[property_name] = match.group("value").strip()

    add_calls: List[Dict[str, Any]] = []
    parents: Dict[str, str] = {}
    table_positions: Dict[str, Tuple[int, int]] = {}
    add_order: Dict[str, int] = {}
    for ordinal, match in enumerate(code_matches(_CONTROLS_ADD)):
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
    for match in code_matches(_SET_CHILD_INDEX):
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
