"""Retained sql syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple
from .lexer import (
    _SqlToken,
    _base_source,
    _identifier_value,
    _is_identifier_token,
    _matching_parenthesis_token,
    _next_code_token,
    _normalize_source,
)


_CLAUSE_WORDS = {
    "APPLY",
    "CROSS",
    "EXCEPT",
    "FULL",
    "GROUP",
    "HASH",
    "HAVING",
    "INNER",
    "INTERSECT",
    "JOIN",
    "LEFT",
    "LOOP",
    "MERGE",
    "ON",
    "OPTION",
    "ORDER",
    "OUTER",
    "REMOTE",
    "RIGHT",
    "UNION",
    "WHERE",
    "WHEN",
    "WITH",
}


_FROM_SOURCE_LIST_BOUNDARIES = {
    "EXCEPT",
    "FOR",
    "GROUP",
    "HAVING",
    "INTERSECT",
    "OPTION",
    "ORDER",
    "OUTPUT",
    "SET",
    "UNION",
    "VALUES",
    "WHEN",
    "WHERE",
}


@dataclass(frozen=True)
class _SourceDeclaration:
    scope_id: str
    source: str
    base_source: str
    effective_alias: str
    source_start: int
    source_name_end: int
    source_end: int
    alias_start: int | None
    alias_end: int | None
    order: int


@dataclass(frozen=True)
class _SqlScope:
    scope_id: str
    start: int
    end: int
    depth: int
    declarations: Tuple[_SourceDeclaration, ...]


@dataclass(frozen=True)
class _AliasChange:
    scope_id: str
    source: str
    original_alias: str
    formatted_alias: str
    original: _SourceDeclaration
    formatted: _SourceDeclaration


def _build_sql_scopes(tokens: Sequence[_SqlToken]) -> List[_SqlScope]:
    code_indices = [
        item.index
        for item in tokens
        if item.kind not in {"line_comment", "block_comment"}
        and item.normalized in {"SELECT", "UPDATE", "DELETE", "MERGE"}
        and _is_sql_scope_start(tokens, item.index)
    ]
    scopes: List[_SqlScope] = []
    for ordinal, start in enumerate(code_indices, start=1):
        depth = tokens[start].depth
        end = len(tokens)
        for cursor in range(start + 1, len(tokens)):
            token = tokens[cursor]
            if token.depth < depth:
                end = cursor
                break
            if token.depth == depth and token.normalized == ";":
                end = cursor + 1
                break
            if token.depth == depth and cursor in code_indices:
                end = cursor
                break
        scope_id = f"scope_{ordinal}"
        declarations = _parse_scope_declarations(tokens, scope_id, start, end, depth)
        scopes.append(
            _SqlScope(
                scope_id=scope_id,
                start=start,
                end=end,
                depth=depth,
                declarations=tuple(declarations),
            )
        )
    return scopes


def _is_sql_scope_start(tokens: Sequence[_SqlToken], index: int) -> bool:
    keyword = tokens[index].normalized
    if keyword == "SELECT":
        return True
    if keyword == "MERGE":
        next_token = _next_code_token(tokens, index + 1, len(tokens))
        return next_token is None or tokens[next_token].normalized != "JOIN"
    if keyword not in {"UPDATE", "DELETE"}:
        return False

    depth = tokens[index].depth
    cursor = index - 1
    while cursor >= 0:
        token = tokens[cursor]
        if token.kind in {"line_comment", "block_comment"}:
            cursor -= 1
            continue
        if token.depth < depth or (token.depth == depth and token.normalized == ";"):
            break
        if token.depth == depth and token.normalized == "MERGE":
            return False
        cursor -= 1
    return True


def _parse_scope_declarations(
    tokens: Sequence[_SqlToken],
    scope_id: str,
    start: int,
    end: int,
    depth: int,
) -> List[_SourceDeclaration]:
    declarations: List[_SourceDeclaration] = []
    statement_kind = tokens[start].normalized
    cursor = start if statement_kind == "MERGE" else start + 1
    from_source_list_active = False
    while cursor < end:
        token = tokens[cursor]
        if token.kind in {"line_comment", "block_comment"}:
            cursor += 1
            continue
        if token.depth == depth:
            if token.normalized == "FROM":
                from_source_list_active = True
            elif token.normalized in _FROM_SOURCE_LIST_BOUNDARIES:
                from_source_list_active = False
        source_markers = {"FROM", "JOIN", "APPLY"}
        if statement_kind == "MERGE":
            source_markers.add("USING")
        is_merge_target = statement_kind == "MERGE" and cursor == start
        is_comma_source = (
            token.depth == depth
            and token.text == ","
            and from_source_list_active
        )
        if token.depth != depth or (
            not is_merge_target
            and token.normalized not in source_markers
            and not is_comma_source
        ):
            cursor += 1
            continue
        value_index = _next_code_token(tokens, cursor + 1, end)
        if value_index is None:
            break
        if (
            statement_kind == "DELETE"
            and token.normalized == "FROM"
            and cursor == _next_after_top_modifier(tokens, start + 1, end)
            and _has_later_scope_keyword(tokens, value_index + 1, end, depth, "FROM")
        ):
            cursor = value_index + 1
            continue
        if is_merge_target:
            value_index = _next_after_top_modifier(tokens, cursor + 1, end)
            if value_index is None:
                break
        if is_merge_target and tokens[value_index].normalized == "INTO":
            value_index = _next_code_token(tokens, value_index + 1, end)
            if value_index is None:
                break
        if tokens[value_index].text == "(":
            close = _matching_parenthesis_token(tokens, value_index, end)
            if close is None:
                cursor += 1
                continue
            source = "(DERIVED)"
            source_start = value_index
            source_name_end = close
            source_end = close
            alias_probe = _next_code_token(tokens, close + 1, end)
        else:
            source_start = value_index
            source_end = value_index
            parts = [tokens[value_index].normalized]
            probe = value_index + 1
            while probe + 1 < end:
                dot = _next_code_token(tokens, probe, end)
                if dot is None or tokens[dot].text != ".":
                    break
                name = _next_code_token(tokens, dot + 1, end)
                if name is None or not _is_identifier_token(tokens[name]):
                    break
                parts.extend([".", tokens[name].normalized])
                source_end = name
                probe = name + 1
            source = "".join(parts)
            source_name_end = source_end
            alias_probe = _next_code_token(tokens, source_end + 1, end)
            if alias_probe is not None and tokens[alias_probe].text == "(":
                close = _matching_parenthesis_token(tokens, alias_probe, end)
                if close is None:
                    cursor += 1
                    continue
                source_end = close
                alias_probe = _next_code_token(tokens, close + 1, end)

        alias_start: int | None = None
        alias_end: int | None = None
        alias = _base_source(source)
        if alias_probe is not None and tokens[alias_probe].normalized == "AS":
            alias_value = _next_code_token(tokens, alias_probe + 1, end)
            if alias_value is not None and _is_identifier_token(tokens[alias_value]):
                alias_start, alias_end = alias_probe, alias_value
                alias = _identifier_value(tokens[alias_value])
        elif (
            alias_probe is not None
            and _is_identifier_token(tokens[alias_probe])
            and tokens[alias_probe].normalized not in _CLAUSE_WORDS
        ):
            alias_start = alias_end = alias_probe
            alias = _identifier_value(tokens[alias_probe])

        declarations.append(
            _SourceDeclaration(
                scope_id=scope_id,
                source=_normalize_source(source),
                base_source=_base_source(source),
                effective_alias=alias.upper(),
                source_start=source_start,
                source_name_end=source_name_end,
                source_end=source_end,
                alias_start=alias_start,
                alias_end=alias_end,
                order=len(declarations) + 1,
            )
        )
        declaration_end = alias_end if alias_end is not None else source_end
        cursor = max(cursor + 1, declaration_end + 1)
    return declarations


def _has_later_scope_keyword(
    tokens: Sequence[_SqlToken],
    start: int,
    end: int,
    depth: int,
    keyword: str,
) -> bool:
    return any(
        token.kind not in {"line_comment", "block_comment"}
        and token.depth == depth
        and token.normalized == keyword
        for token in tokens[start:end]
    )


def _next_after_top_modifier(
    tokens: Sequence[_SqlToken],
    start: int,
    end: int,
) -> int | None:
    value = _next_code_token(tokens, start, end)
    if value is None or tokens[value].normalized != "TOP":
        return value
    amount = _next_code_token(tokens, value + 1, end)
    if amount is None:
        return None
    if tokens[amount].text == "(":
        close = _matching_parenthesis_token(tokens, amount, end)
        if close is None:
            return None
        value = _next_code_token(tokens, close + 1, end)
    else:
        value = _next_code_token(tokens, amount + 1, end)
    if value is not None and tokens[value].normalized == "PERCENT":
        value = _next_code_token(tokens, value + 1, end)
    return value


def _find_alias_changes(
    original_scopes: Sequence[_SqlScope],
    formatted_scopes: Sequence[_SqlScope],
) -> List[_AliasChange]:
    changes: List[_AliasChange] = []
    for original_scope, formatted_scope in zip(original_scopes, formatted_scopes):
        for original_decl, formatted_decl in zip(
            original_scope.declarations,
            formatted_scope.declarations,
        ):
            if original_decl.source != formatted_decl.source:
                continue
            if original_decl.effective_alias == formatted_decl.effective_alias:
                continue
            changes.append(
                _AliasChange(
                    scope_id=formatted_scope.scope_id,
                    source=formatted_decl.source,
                    original_alias=original_decl.effective_alias,
                    formatted_alias=formatted_decl.effective_alias,
                    original=original_decl,
                    formatted=formatted_decl,
                )
            )
    return changes


def _is_bound_alias_reference(
    tokens: Sequence[_SqlToken],
    index: int,
    scope: _SqlScope,
    alias: str,
    scopes: Sequence[_SqlScope] | None = None,
) -> bool:
    if _identifier_value(tokens[index]) != alias:
        return False
    binding_scope = (
        _binding_scope_for_alias(scopes, index, alias)
        if scopes is not None
        else scope
    )
    if binding_scope is None or binding_scope.scope_id != scope.scope_id:
        return False
    if sum(item.effective_alias == alias for item in binding_scope.declarations) != 1:
        return False
    if _is_dml_target_alias(tokens, index, binding_scope):
        return True
    dot = _next_code_token(tokens, index + 1, scope.end)
    if dot is None or tokens[dot].text != ".":
        return False
    member = _next_code_token(tokens, dot + 1, scope.end)
    if member is None or not (_is_identifier_token(tokens[member]) or tokens[member].text == "*"):
        return False
    following = _next_code_token(tokens, member + 1, scope.end)
    return following is None or tokens[following].text != "."


def _is_dml_target_alias(
    tokens: Sequence[_SqlToken],
    index: int,
    scope: _SqlScope,
) -> bool:
    statement_kind = tokens[scope.start].normalized
    if statement_kind not in {"UPDATE", "DELETE"}:
        return False
    target = _next_after_top_modifier(tokens, scope.start + 1, scope.end)
    if target is None:
        return False
    if statement_kind == "DELETE" and tokens[target].normalized == "FROM":
        target = _next_code_token(tokens, target + 1, scope.end)
        if target is None:
            return False
    return index == target


def _binding_scope_for_alias(
    scopes: Sequence[_SqlScope],
    token_index: int,
    alias: str,
) -> _SqlScope | None:
    containing = sorted(
        (scope for scope in scopes if scope.start <= token_index < scope.end),
        key=lambda scope: (scope.depth, scope.start, -scope.end),
        reverse=True,
    )
    for candidate in containing:
        matches = [
            declaration
            for declaration in candidate.declarations
            if declaration.effective_alias == alias
        ]
        if matches:
            return candidate if len(matches) == 1 else None
    return None
