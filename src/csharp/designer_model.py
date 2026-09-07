"""Retained csharp syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple
import re
import json

from .lexer import _scan_csharp, _mask_range, string_literal_value


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"


_CONTROL_DECLARATION = re.compile(
    rf"\b(?:private|protected|internal|public)\s+"
    rf"(?P<type>[A-Za-z_][A-Za-z0-9_.<>]*)\s+(?P<name>{_IDENTIFIER})\s*;",
    re.MULTILINE,
)


_CONTROL_INITIALIZER = re.compile(
    rf"\bthis\.(?P<name>{_IDENTIFIER})\s*=\s*new\s+"
    rf"(?P<type>[A-Za-z_][A-Za-z0-9_.<>]*)\s*\(",
    re.MULTILINE,
)


_ASSIGNMENT = re.compile(rf"\bthis\.(?P<path>{_IDENTIFIER}(?:\.{_IDENTIFIER})*)\s*=(?!=)")


_CONTROLS_ADD = re.compile(
    rf"\bthis(?:\.(?P<parent>{_IDENTIFIER}))?\.Controls\.Add\(\s*"
    rf"this\.(?P<child>{_IDENTIFIER})"
    rf"(?:\s*,\s*(?P<column>-?\d+)\s*,\s*(?P<row>-?\d+))?\s*\)\s*;",
    re.MULTILINE,
)


_SET_CHILD_INDEX = re.compile(
    rf"\bthis(?:\.(?P<parent>{_IDENTIFIER}))?\.Controls\.SetChildIndex\(\s*"
    rf"this\.(?P<child>{_IDENTIFIER})\s*,\s*(?P<index>-?\d+)\s*\)\s*;",
    re.MULTILINE,
)


_POINT = re.compile(
    r"new\s+(?:System\.Drawing\.)?Point\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)"
)


_SIZE = re.compile(
    r"new\s+(?:System\.Drawing\.)?Size\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)"
)


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
    return string_literal_value(value)


def _parse_point(value: str) -> Tuple[int, int] | None:
    match = _POINT.search(str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _parse_size(value: str) -> Tuple[int, int] | None:
    match = _SIZE.search(str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def _normalized_csharp_value(value: str) -> str:
    """Compare constant string values; otherwise preserve token boundaries and payload."""
    constant = string_literal_value(value)
    if constant is not None:
        return 'string:' + json.dumps(constant, ensure_ascii=True)
    _, tokens = _scan_csharp(value)
    # Token boundaries matter: `a + +b` must not become `a++b`.
    return 'tokens:' + json.dumps([(kind, value[start:end]) for kind, _, start, end in tokens], ensure_ascii=True)


def _assignment_end(code: str, start: int) -> int | None:
    """Locate a statement terminator outside literal text and nested expressions."""
    stack: list[str] = []
    pairs = {')': '(', ']': '[', '}': '{'}
    for index in range(start, len(code)):
        char = code[index]
        if char in '([{':
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return None
        elif char == ';' and not stack:
            return index
    return None


def parse_designer_source(designer_source: str) -> DesignerModel:
    """Parse controls, static assignments, containment, table cells, and z-order."""

    source = _strip_csharp_comments(designer_source)
    code, tokens = _scan_csharp(designer_source)
    chars = list(code)
    for kind, _, start, end in tokens:
        if kind in {'string', 'interpolated_string'}:
            _mask_range(chars, designer_source, start, end)
    code = ''.join(chars)
    type_names: Dict[str, str] = {}
    for match in _CONTROL_DECLARATION.finditer(code):
        type_names[match.group("name")] = match.group("type")
    for match in _CONTROL_INITIALIZER.finditer(code):
        type_name = match.group("type")
        if type_name.split(".")[-1] not in {"Point", "PointF", "Size", "SizeF", "Padding", "Font"}:
            type_names[match.group("name")] = type_name

    property_values: Dict[str, Dict[str, str]] = {}
    form_properties: Dict[str, str] = {}
    assignments: List[Dict[str, Any]] = []
    for match in _ASSIGNMENT.finditer(code):
        end = _assignment_end(code, match.end())
        if end is None:
            continue
        parts = match['path'].split('.')
        value = source[match.end():end].strip()
        if len(parts) == 1:
            if parts[0] not in type_names:
                form_properties[parts[0]] = value
            continue
        name, property_path = parts[0], '.'.join(parts[1:])
        property_values.setdefault(name, {})[property_path] = value
        assignments.append({"name": name, "property": property_path, "value": value,
                            "line": source.count('\n', 0, match.start()) + 1})

    add_calls: List[Dict[str, Any]] = []
    parents: Dict[str, str] = {}
    table_positions: Dict[str, Tuple[int, int]] = {}
    add_order: Dict[str, int] = {}
    for ordinal, match in enumerate(_CONTROLS_ADD.finditer(code)):
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
    for match in _SET_CHILD_INDEX.finditer(code):
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
