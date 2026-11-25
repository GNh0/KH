"""Retained csharp syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations
from .lexer import _scan_csharp

import hashlib
import json
import re
from collections import Counter
from typing import Any, Dict, List, Mapping, Sequence




_FOR_ROWS_PATTERN = re.compile(
    r"\bfor\s*\((?P<header>[^;]*;[^;]*\b(?P<table>[A-Za-z_]\w*)\.Rows\.Count[^;]*;[^)]*)\)",
    re.MULTILINE,
)




def _mask_comments_and_literals(source: str) -> str:
    return _scan_csharp(source)[0]


def _call_count(source: str, name: str) -> int:
    return len(re.findall(rf"\b{re.escape(name)}\s*\(", source))


_METHOD_DECLARATION_PATTERN = re.compile(
    r"(?P<modifiers>(?:(?:public|private|protected|internal|static|virtual|sealed|override|async|partial|extern|abstract|new|unsafe)\s+)*)"
    r"(?P<return>[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*|\s*<[^;{}()]+>|\s*\[\s*\]|\s*\?)*)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*(?P<generic><[^;{}()]+>)?\s*"
    r"\((?P<parameters>[^()]*)\)\s*(?:where\s+[^{}=>]+\s*)?(?P<body>\{|=>)",
    re.MULTILINE,
)


_TYPE_BODY_PATTERN = re.compile(
    r"\b(?:class|struct|interface|record(?:\s+(?:class|struct))?)\s+"
    r"[A-Za-z_]\w*(?:\s*<[^;{}]+>)?[^;{}]*\{",
    re.MULTILINE,
)


_NON_METHOD_RETURN_TOKENS = {
    "await",
    "case",
    "do",
    "else",
    "for",
    "foreach",
    "if",
    "lock",
    "new",
    "return",
    "switch",
    "throw",
    "using",
    "while",
    "yield",
}


_GENERATED_OR_LIFECYCLE_METHODS = {
    "Dispose",
    "InitializeComponent",
    "OnClosing",
    "OnClosed",
    "OnFormClosing",
    "OnFormClosed",
    "OnHandleCreated",
    "OnHandleDestroyed",
    "OnLoad",
    "OnShown",
}


_INVOCATION_PATTERN = re.compile(
    r"(?:(?P<receiver>\b[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*)\s*\.\s*)?"
    r"(?P<name>[A-Za-z_]\w*)\s*(?:<[^;{}()]+>)?\s*\("
)


_INVOCATION_KEYWORDS = {
    "catch",
    "checked",
    "default",
    "fixed",
    "for",
    "foreach",
    "if",
    "lock",
    "nameof",
    "sizeof",
    "switch",
    "typeof",
    "unchecked",
    "using",
    "while",
}


def _target_local_method_inventory(
    source: str,
    *,
    wired_event_handlers: set[str] | None = None,
) -> List[Dict[str, str]]:
    inventory: List[Dict[str, str]] = []
    wired_handlers = wired_event_handlers or set()
    matches = list(_method_declaration_matches(source))
    type_body_openings = {
        match.end() - 1 for match in _TYPE_BODY_PATTERN.finditer(source)
    }
    active_braces: List[int] = []
    cursor = 0
    for match in matches:
        while cursor < match.start():
            if source[cursor] == "{":
                active_braces.append(cursor)
            elif source[cursor] == "}" and active_braces:
                active_braces.pop()
            cursor += 1

        # Full source files must expose methods directly under a type body.
        # Standalone method snippets remain supported when no type is present.
        if type_body_openings:
            if not active_braces or active_braces[-1] not in type_body_openings:
                continue
        elif active_braces:
            continue

        modifiers = set((match.group("modifiers") or "").split())
        name = match.group("name")
        parameters = match.group("parameters")
        if modifiers & {"override", "partial", "extern", "abstract"}:
            continue
        if name in _GENERATED_OR_LIFECYCLE_METHODS:
            continue
        if _looks_like_event_handler(
            name,
            match.group("return"),
            parameters,
            wired_handlers,
        ):
            continue
        generic = match.group("generic") or ""
        generic_arity = generic.count(",") + 1 if generic else 0
        parameter_types = _parameter_type_signature(parameters)
        inventory.append(
            {
                "name": name,
                "signature": f"{name}`{generic_arity}({','.join(parameter_types)})",
            }
        )
    return inventory


def _method_declaration_matches(source: str):
    """Yield method-shaped declarations while excluding statement expressions."""

    for match in _METHOD_DECLARATION_PATTERN.finditer(source):
        return_type = re.sub(r"\s+", "", match.group("return")).lower()
        if return_type in _NON_METHOD_RETURN_TOKENS:
            continue
        yield match


def _looks_like_event_handler(
    name: str,
    return_type: str,
    parameters: str,
    wired_event_handlers: set[str],
) -> bool:
    if re.sub(r"\s+", "", return_type) != "void":
        return False
    if name in wired_event_handlers:
        return True
    parameter_types = _parameter_type_signature(parameters)
    if len(parameter_types) != 2:
        return False
    sender_type = re.sub(r"^(?:ref|in|out)\s+", "", parameter_types[0]).rstrip("?")
    event_type = re.sub(r"^(?:ref|in|out)\s+", "", parameter_types[1]).rstrip("?")
    return sender_type == "object" and bool(
        re.search(
            r"(?:^|\.)(?:EventArgs|[A-Za-z_]\w+EventArgs)$",
            event_type,
        )
    )


_DESIGNER_EVENT_WIRING_PATTERN = re.compile(
    r"\b[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)+\s*\+=\s*"
    r"(?:new\s+[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*(?:\s*<[^;()]+>)?\s*\(\s*)?"
    r"(?:this\s*\.\s*)?(?P<handler>[A-Za-z_]\w*)\s*\)?\s*;",
    re.MULTILINE,
)


def _designer_wired_event_handlers(designer_source: str | None) -> set[str]:
    if not designer_source:
        return set()
    masked = _mask_comments_and_literals(str(designer_source))
    return {
        match.group("handler")
        for match in _DESIGNER_EVENT_WIRING_PATTERN.finditer(masked)
    }


def _parameter_type_signature(parameters: str) -> List[str]:
    result: List[str] = []
    for parameter in _split_top_level(parameters):
        value = re.sub(r"^\s*(?:\[[^\]]+\]\s*)+", "", parameter).strip()
        value = _strip_top_level_default(value)
        value = re.sub(r"\s+[A-Za-z_]\w*\s*$", "", value).strip()
        value = re.sub(r"\s+", " ", value)
        value = re.sub(r"\s*([<>,\[\]?.])\s*", r"\1", value)
        if value:
            result.append(value)
    return result


def _split_top_level(value: str) -> List[str]:
    parts: List[str] = []
    start = 0
    depths = {"<": 0, "(": 0, "[": 0, "{": 0}
    closing = {">": "<", ")": "(", "]": "[", "}": "{"}
    for index, char in enumerate(value):
        if char in depths:
            depths[char] += 1
        elif char in closing and depths[closing[char]] > 0:
            depths[closing[char]] -= 1
        elif char == "," and not any(depths.values()):
            parts.append(value[start:index])
            start = index + 1
    parts.append(value[start:])
    return [part for part in parts if part.strip()]


def _strip_top_level_default(value: str) -> str:
    depths = {"<": 0, "(": 0, "[": 0, "{": 0}
    closing = {">": "<", ")": "(", "]": "[", "}": "{"}
    for index, char in enumerate(value):
        if char in depths:
            depths[char] += 1
        elif char in closing and depths[closing[char]] > 0:
            depths[closing[char]] -= 1
        elif char == "=" and not any(depths.values()):
            return value[:index].strip()
    return value


def _transaction_invocation_drift_issues(
    original: str,
    candidate: str,
) -> List[Dict[str, Any]]:
    original_calls = _invocation_inventory(original)
    candidate_calls = _invocation_inventory(candidate)
    original_exact = Counter(item["identity"] for item in original_calls)
    candidate_exact = Counter(item["identity"] for item in candidate_calls)
    original_non_transaction = Counter(
        item["family"] for item in original_calls if not item["transaction_capable"]
    )
    candidate_non_transaction = Counter(
        item["family"] for item in candidate_calls if not item["transaction_capable"]
    )
    issues: List[Dict[str, Any]] = []
    for call in original_calls:
        if not call["transaction_capable"]:
            continue
        identity = call["identity"]
        if candidate_exact[identity] >= original_exact[identity]:
            continue
        family = call["family"]
        introduced_plain = candidate_non_transaction[family] - original_non_transaction[family]
        if introduced_plain <= 0:
            continue
        issues.append(
            {"code": "transaction_call_change_review", "severity": "warning",
             "message": "A transaction-named save call changed to another call in its name family. Inspect actual transaction arguments, wrapper bodies and API behavior; names alone do not prove transaction loss.",
             "original_invocation": identity, "invocation_family": family,
             "introduced_plain_name_count": introduced_plain}
        )
    return issues


def _invocation_inventory(source: str) -> List[Dict[str, Any]]:
    declarations = {
        match.start("name")
        for match in _method_declaration_matches(source)
    }
    inventory: List[Dict[str, Any]] = []
    for match in _INVOCATION_PATTERN.finditer(source):
        if match.start("name") in declarations:
            continue
        name = match.group("name")
        if name.lower() in _INVOCATION_KEYWORDS:
            continue
        family, transaction_capable = _save_invocation_family(name)
        if not family:
            continue
        receiver = re.sub(r"\s+", "", match.group("receiver") or "").lower()
        inventory.append(
            {
                "name": name,
                "receiver": receiver,
                "family": family,
                "transaction_capable": transaction_capable,
                "identity": f"{receiver}.{name.lower()}",
            }
        )
    return inventory


def _save_invocation_family(name: str) -> tuple[str, bool]:
    lowered = name.lower()
    transaction_pattern = re.compile(
        r"(?:with)?(?:transaction|trans|tran|trn)(?:async)?$",
        re.IGNORECASE,
    )
    match = transaction_pattern.search(name)
    transaction_capable = match is not None
    base = name[: match.start()] if match is not None else name
    canonical = re.sub(r"[^a-z0-9]", "", base.lower())
    if not re.search(r"(?:exec|execute|save|storedprocedure|procedure|sp)", canonical):
        return "", transaction_capable
    return canonical, transaction_capable


def _row_rewrite_loops(source: str) -> List[Dict[str, Any]]:
    masked = _mask_comments_and_literals(source)
    loops: List[Dict[str, Any]] = []
    for marker in re.finditer(r"\bforeach\b", masked):
        opening = marker.end()
        while opening < len(masked) and masked[opening].isspace():
            opening += 1
        if opening >= len(masked) or masked[opening] != "(":
            continue
        closing = _matching_delimiter(masked, opening, "(", ")")
        if closing is None:
            continue
        header = masked[opening + 1 : closing]
        in_match = re.search(r"\bin\b", header)
        if in_match is None:
            continue
        declaration = header[: in_match.start()]
        row_match = re.search(r"([A-Za-z_]\w*)\s*$", declaration)
        table_name = _whole_table_source(header[in_match.end() :])
        if row_match is None or not table_name:
            continue
        body_start, body_end = _statement_or_block_span(masked, closing + 1)
        body_code = masked[body_start:body_end]
        body_source = source[body_start:body_end]
        columns = _assigned_indexer_columns(
            body_code,
            body_source,
            rf"\b{re.escape(row_match.group(1))}",
        )
        if columns:
            loops.append(_loop_record(table_name, columns, body_code))
    for match in _FOR_ROWS_PATTERN.finditer(masked):
        body_start, body_end = _statement_or_block_span(masked, match.end())
        body_code = masked[body_start:body_end]
        body_source = source[body_start:body_end]
        table_name = match.group("table")
        columns = _assigned_indexer_columns(
            body_code,
            body_source,
            rf"\b{re.escape(table_name)}\.Rows\s*\[[^\]]+\]",
        )
        if columns:
            loops.append(_loop_record(table_name, columns, body_code))
    return loops


def _whole_table_source(value: str) -> str:
    compact = re.sub(r"\s+", "", value)
    suffixes = (
        r"\.Rows\.Cast<[^>]+>\(\)$",
        r"\.Select\(\)$",
        r"\.Rows$",
    )
    for suffix in suffixes:
        match = re.search(suffix, compact)
        if match is None:
            continue
        table = compact[: match.start()]
        if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*(?:\[[^\]]*\])?)*", table):
            return table
    return ""


def _matching_delimiter(
    source: str,
    opening: int,
    open_char: str,
    close_char: str,
) -> int | None:
    depth = 0
    for position in range(opening, len(source)):
        if source[position] == open_char:
            depth += 1
        elif source[position] == close_char:
            depth -= 1
            if depth == 0:
                return position
    return None


def _statement_or_block_span(source: str, start: int) -> tuple[int, int]:
    position = start
    while position < len(source) and source[position].isspace():
        position += 1
    if position >= len(source):
        return len(source), len(source)
    if source[position] != "{":
        end = source.find(";", position)
        return (position, len(source)) if end < 0 else (position, end + 1)
    closing = _matching_delimiter(source, position, "{", "}")
    return (position, len(source)) if closing is None else (position, closing + 1)


def _assigned_indexer_columns(
    masked_body: str,
    original_body: str,
    receiver_pattern: str,
) -> List[str]:
    pattern = re.compile(
        receiver_pattern
        + r"\s*\[(?P<literal>[ \t]+)\]\s*(?:=(?!=|>)|[+\-*/%&|^]=)",
        re.MULTILINE,
    )
    columns: List[str] = []
    for match in pattern.finditer(masked_body):
        start, end = match.span("literal")
        value = _csharp_string_value(original_body[start:end].strip())
        if value:
            columns.append(value)
    return columns


def _csharp_string_value(value: str) -> str:
    if value.startswith('@"') and value.endswith('"'):
        return value[2:-1].replace('""', '"')
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    return ""


def _loop_record(table: str, columns: Sequence[str], body: str) -> Dict[str, Any]:
    normalized_columns = sorted({str(column).upper() for column in columns})
    return {
        "table": table,
        "columns": normalized_columns,
        "fingerprint": _sha256(
            json.dumps(
                {"table": table, "columns": normalized_columns, "body": " ".join(body.split())},
                sort_keys=True,
                separators=(",", ":"),
            )
        ),
    }


def _issue(code: str, message: str, **evidence: Any) -> Dict[str, Any]:
    return {"code": code, "severity": "error", "message": message, "evidence": evidence}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
