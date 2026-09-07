"""Retained sql syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple
from .lexer import (
    _SqlToken,
    _base_source,
    _identifier_value,
    _is_identifier_token,
    _matching_parenthesis_token,
    _next_code_token,
    _scan_sql_tokens,
)
from .scopes import (
    _is_sql_scope_start,
    _next_after_top_modifier,
    _parse_scope_declarations,
)


def _full_replace_records(sql: str) -> List[Dict[str, str]]:
    tokens, _ = _scan_sql_tokens(sql)
    inserts = _insert_target_tables(tokens)
    records: List[Dict[str, str]] = []
    for start, token in enumerate(tokens):
        if token.normalized != "DELETE" or not _is_sql_scope_start(tokens, start):
            continue
        end = _dml_statement_end(tokens, start)
        table = _delete_target_table(tokens, start, end)
        if not table:
            continue
        matching_inserts = [
            record
            for record in inserts
            if record["position"] > start
            and record["table"] == table
            and not _simple_if_else_mutually_exclusive(
                tokens,
                start,
                int(record["position"]),
            )
        ]
        if not matching_inserts:
            continue
        delete_states = _explicit_row_state_values(tokens, start, end)
        delta_delete = bool(delete_states) and delete_states <= _DELETE_ROW_STATE_VALUES
        offending_inserts = (
            matching_inserts
            if not delta_delete
            else [
                record
                for record in matching_inserts
                if bool(record["has_select"])
                and not _valid_insert_delta_states(set(record["row_state_values"]))
            ]
        )
        delete_signature = _sql_token_slice_signature(tokens, start, end)
        for insert in offending_inserts:
            records.append(
                {
                    "table": table,
                    "shape_sha256": _sha256_text(
                        delete_signature
                        + "\x1e"
                        + _sql_token_slice_signature(
                            tokens,
                            int(insert["position"]),
                            int(insert["end"]),
                        )
                    ),
                }
            )
    unique: Dict[Tuple[str, str], Dict[str, str]] = {}
    for record in records:
        unique[(record["table"], record["shape_sha256"])] = record
    return list(unique.values())


def _sql_token_slice_signature(
    tokens: Sequence[_SqlToken],
    start: int,
    end: int,
) -> str:
    return "\x1f".join(
        token.normalized
        for token in tokens[start:end]
        if token.kind not in {"line_comment", "block_comment"}
    )


def _insert_target_tables(tokens: Sequence[_SqlToken]) -> List[Dict[str, Any]]:
    targets: List[Dict[str, Any]] = []
    for position, token in enumerate(tokens):
        if token.normalized != "INSERT":
            continue
        into = _next_code_token(tokens, position + 1, len(tokens))
        if into is None or tokens[into].normalized != "INTO":
            continue
        source = _next_code_token(tokens, into + 1, len(tokens))
        if source is None:
            continue
        table, _ = _identifier_path_at(tokens, source, len(tokens))
        if table:
            end = _insert_statement_end(tokens, position)
            targets.append(
                {
                    "position": position,
                    "end": end,
                    "table": _normalize_table_name(table),
                    "has_select": any(
                        item.depth == token.depth and item.normalized == "SELECT"
                        for item in tokens[position + 1 : end]
                    ),
                    "row_state_values": sorted(
                        _explicit_row_state_values(tokens, position, end)
                    ),
                }
            )
    return targets


def _insert_statement_end(tokens: Sequence[_SqlToken], start: int) -> int:
    depth = tokens[start].depth
    for position in range(start + 1, len(tokens)):
        token = tokens[position]
        if token.kind in {"line_comment", "block_comment"}:
            continue
        if token.depth < depth:
            return position
        if token.depth != depth:
            continue
        if token.normalized == ";":
            return position
        if token.normalized in {"INSERT", "UPDATE", "DELETE", "MERGE"}:
            return position
    return len(tokens)


def _dml_statement_end(tokens: Sequence[_SqlToken], start: int) -> int:
    depth = tokens[start].depth
    for position in range(start + 1, len(tokens)):
        token = tokens[position]
        if token.kind in {"line_comment", "block_comment"}:
            continue
        if token.depth < depth:
            return position
        if token.depth != depth:
            continue
        if token.normalized == ";":
            return position
        if token.normalized in {"SELECT", "INSERT", "UPDATE", "DELETE", "MERGE"}:
            return position
    return len(tokens)


def _delete_target_table(
    tokens: Sequence[_SqlToken],
    start: int,
    end: int,
) -> str:
    target = _next_after_top_modifier(tokens, start + 1, end)
    if target is None:
        return ""

    declarations = _parse_scope_declarations(
        tokens,
        "full_replace_delete",
        start,
        end,
        tokens[start].depth,
    )
    if tokens[target].normalized == "FROM":
        return _normalize_table_name(declarations[0].source) if declarations else ""

    target_name, _ = _identifier_path_at(tokens, target, end)
    normalized_target = _normalize_table_name(target_name)
    target_base = _base_source(normalized_target)
    matches = [
        declaration
        for declaration in declarations
        if declaration.effective_alias == target_base
        or declaration.source == normalized_target
    ]
    if len(matches) != 1:
        return ""
    return _normalize_table_name(matches[0].source)


def _identifier_path_at(
    tokens: Sequence[_SqlToken],
    start: int,
    end: int,
) -> Tuple[str, int]:
    if start >= end or not _is_identifier_token(tokens[start]):
        return "", start
    parts = [_identifier_value(tokens[start])]
    last = start
    while True:
        dot = _next_code_token(tokens, last + 1, end)
        if dot is None or tokens[dot].text != ".":
            break
        name = _next_code_token(tokens, dot + 1, end)
        if name is None or not _is_identifier_token(tokens[name]):
            break
        parts.append(_identifier_value(tokens[name]))
        last = name
    return ".".join(parts), last


_ROW_STATE_COLUMNS = {"GBN", "ROW_STATE", "ROWSTATE", "ROW_STATUS", "ROWSTATUS", "STATE"}


_DELETE_ROW_STATE_VALUES = {"D", "DEL", "DELETED"}


_INSERT_ROW_STATE_VALUES = {"I", "N", "ADD", "ADDED", "INSERTED", "NEW"}


def _explicit_row_state_values(
    tokens: Sequence[_SqlToken],
    start: int,
    end: int,
) -> set[str]:
    matched: set[str] = set()
    for position in range(start + 1, end):
        if _identifier_value(tokens[position]) not in _ROW_STATE_COLUMNS:
            continue
        operator = _next_code_token(tokens, position + 1, end)
        if operator is None:
            continue
        if tokens[operator].text == "=":
            value = _next_code_token(tokens, operator + 1, end)
            if value is not None:
                row_state = _sql_string_value(tokens[value])
                if row_state:
                    matched.add(row_state)
        if tokens[operator].normalized == "IN":
            opening = _next_code_token(tokens, operator + 1, end)
            if opening is None or tokens[opening].text != "(":
                continue
            closing = _matching_parenthesis_token(tokens, opening, end)
            if closing is None:
                continue
            matched.update(
                _sql_string_value(token)
                for token in tokens[opening + 1 : closing]
                if token.kind in {"string", "unicode_string"}
            )
    matched.discard("")
    return matched


def _valid_insert_delta_states(values: set[str]) -> bool:
    return bool(values) and values <= _INSERT_ROW_STATE_VALUES


def _simple_if_else_mutually_exclusive(
    tokens: Sequence[_SqlToken],
    delete_start: int,
    insert_start: int,
) -> bool:
    depth = tokens[delete_start].depth
    else_positions = [
        position
        for position in range(delete_start + 1, insert_start)
        if tokens[position].depth == depth and tokens[position].normalized == "ELSE"
    ]
    for else_position in else_positions:
        if_positions = [
            position
            for position in range(0, delete_start)
            if tokens[position].depth == depth and tokens[position].normalized == "IF"
        ]
        if not if_positions:
            continue
        if_position = if_positions[-1]
        if any(
            tokens[position].depth == depth and tokens[position].normalized == "ELSE"
            for position in range(if_position + 1, delete_start)
        ):
            continue
        first_branch_dml = [
            position
            for position in range(if_position + 1, else_position)
            if tokens[position].depth == depth
            and tokens[position].normalized in {"DELETE", "INSERT", "MERGE", "UPDATE"}
        ]
        second_branch_dml = [
            position
            for position in range(else_position + 1, insert_start)
            if tokens[position].depth == depth
            and tokens[position].normalized in {"DELETE", "INSERT", "MERGE", "UPDATE"}
        ]
        if first_branch_dml == [delete_start] and not second_branch_dml:
            return True
    return False


def _sql_string_value(token: _SqlToken) -> str:
    if token.kind == "unicode_string":
        return token.text[2:-1].replace("''", "'").upper()
    if token.kind == "string":
        return token.text[1:-1].replace("''", "'").upper()
    return ""


def _normalize_table_name(value: str) -> str:
    normalized = value.replace("[", "").replace("]", "").upper()
    parts = normalized.split(".")
    if len(parts) == 2 and parts[0] == "DBO":
        return parts[1]
    return normalized


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
