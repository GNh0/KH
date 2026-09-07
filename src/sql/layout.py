"""Retained sql syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple
from .lexer import (
    SqlFormattingIssue,
    _SqlToken,
    _analyze_sql_integrity,
    _canonical_token_value,
    _has_errors,
    _lowercase_sql_tokens,
    _masked_sql,
    _matching_parenthesis_token,
    _next_code_token,
    _previous_code_token,
    _scan_sql_tokens,
    _sql_line_indent,
    _sql_line_number,
)
from .scopes import (
    _SourceDeclaration,
    _build_sql_scopes,
)


_INSERT_SELECT_LAYOUT_CONTRACT = {
    "wide_mapping_min_items": 8,
    "horizontal_expression_max_length": 72,
    "vertical_fallback_min_expression_length": 73,
    "max_short_singleton_lines": 1,
    "measurement": "canonical_non_comment_token_text_length",
}


_QUERY_LIST_LAYOUT_CONTRACT = {
    "preferred_line_width": 100,
    "hard_line_width": 120,
    "simple_item_max_length": 60,
    "split_boundary": "top_level_commas_only",
    "packing": "short_simple_inline_then_greedy_compact_rows",
    "complex_item_markers": [
        "CASE",
        "subquery",
        "OVER",
        "comments",
        "nested_parenthesis_depth_above_one",
        "item_length_above_60",
    ],
    "window_order_by": "excluded_by_query_depth",
}


_JOIN_LAYOUT_CONTRACT = {
    "join_indent_from_from": 8,
    "join_prefix_and_token": "single_line",
    "outer_keyword": "generation requires explicit OUTER for LEFT/RIGHT/FULL; formatting and refactor preserve the source token stream",
    "predicate_alignment": "ON and line-leading same-join continuation AND/OR align to the I column of JOIN",
    "indentation_basis": "current_query_scope_from_column",
    "ordinary_table_joins": "enforced",
    "derived_table_joins": "same_relative_contract_as_ordinary_joins",
    "derived_inner_clause_indent_from_join": 4,
    "derived_closing_alias_alignment": "outer_join_clause_start",
    "join_hints": ["LOOP", "HASH", "MERGE", "REMOTE"],
    "predicate_context": "ordered_group_subquery_case_between_stack",
    "predicate_exclusions": [
        "inline_AND_OR",
        "BETWEEN_AND",
        "CASE_internal_AND_OR",
        "nested_subquery_AND_OR",
    ],
}


_JOIN_PREFIX_WORDS = {
    "CROSS",
    "FULL",
    "HASH",
    "INNER",
    "LEFT",
    "LOOP",
    "MERGE",
    "OUTER",
    "REMOTE",
    "RIGHT",
}


_JOIN_PREDICATE_BOUNDARIES = {
    "APPLY",
    "EXCEPT",
    "FROM",
    "GROUP",
    "HAVING",
    "INTERSECT",
    "JOIN",
    "ORDER",
    "UNION",
    "WHERE",
}


def normalize_sql_join_layout(sql: str) -> str:
    """Normalize IF EXISTS and line-leading JOIN predicate indentation."""
    if not isinstance(sql, str):
        raise TypeError("sql must be a string")
    sql = _normalize_if_exists_layout(sql)
    tokens, integrity_issues = _analyze_sql_integrity(sql, check_kind="join_layout")
    if _has_errors(integrity_issues):
        raise ValueError("SQL integrity must pass before JOIN layout can be normalized")

    directives: Dict[int, int] = {}
    for scope in _build_sql_scopes(tokens):
        if len(scope.declarations) < 2:
            continue
        from_index = _source_marker_before(
            tokens,
            scope.declarations[0].source_start,
            scope.start,
            scope.depth,
            {"FROM"},
        )
        if from_index is None:
            continue
        _, from_column, _ = _token_line_position(sql, tokens[from_index])
        expected_clause_column = from_column + int(
            _JOIN_LAYOUT_CONTRACT["join_indent_from_from"]
        )
        for declaration in scope.declarations[1:]:
            join_index = _source_marker_before(
                tokens,
                declaration.source_start,
                scope.start,
                scope.depth,
                {"JOIN"},
            )
            if join_index is None:
                continue
            clause_start = _join_clause_start(sql, tokens, join_index)
            clause_line, clause_column, clause_line_leading = _token_line_position(
                sql,
                tokens[clause_start],
            )
            join_line, join_column, _ = _token_line_position(sql, tokens[join_index])
            if clause_line != join_line:
                raise ValueError("JOIN type/hint prefixes must be on the JOIN line")
            if clause_line_leading:
                directives[clause_line] = expected_clause_column
            expected_predicate_column = (
                expected_clause_column + (join_column - clause_column) + 2
            )
            for predicate_index in _same_join_predicate_indexes(
                sql,
                tokens,
                join_index,
                scope.end,
                scope.depth,
            ):
                line, _, line_leading = _token_line_position(sql, tokens[predicate_index])
                if line_leading:
                    directives[line] = expected_predicate_column

    _propagate_exists_layout_directives(sql, tokens, directives)
    if directives:
        lines = sql.splitlines(keepends=True)
        for line_number, indent in directives.items():
            index = line_number - 1
            lines[index] = re.sub(r"^[ \t]*", " " * indent, lines[index], count=1)
        sql = "".join(lines)
    return sql


def _propagate_exists_layout_directives(
    sql: str,
    tokens: Sequence[_SqlToken],
    directives: Dict[int, int],
) -> None:
    """Keep nested EXISTS blocks aligned when JOIN normalization shifts their predicate line."""
    if not directives:
        return
    lines = sql.splitlines()
    for pair in _exists_subquery_pairs(tokens):
        open_index = pair["open"]
        close_index = pair["close"]
        first_index = pair["first"]
        open_line, open_column, _ = _token_line_position(sql, tokens[open_index])
        target_indent = directives.get(open_line)
        if target_indent is None or open_line > len(lines):
            continue
        current_indent = len(lines[open_line - 1]) - len(
            lines[open_line - 1].lstrip(" \t")
        )
        shifted_open_column = open_column + target_indent - current_indent
        close_line, _, _ = _token_line_position(sql, tokens[close_index])
        if pair["if"] < 0 and open_line == close_line:
            continue

        first_line, _, first_line_leading = _token_line_position(
            sql,
            tokens[first_index],
        )
        if first_line_leading:
            directives[first_line] = shifted_open_column + 1
        for index in _if_exists_inner_clause_indexes(tokens, pair):
            line, _, line_leading = _token_line_position(sql, tokens[index])
            if line_leading:
                directives[line] = shifted_open_column + 1

        _, _, close_line_leading = _token_line_position(sql, tokens[close_index])
        if close_line_leading:
            directives[close_line] = shifted_open_column


def _normalize_if_exists_layout(sql: str) -> str:
    tokens, integrity_issues = _analyze_sql_integrity(
        sql,
        check_kind="if_exists_layout",
    )
    if _has_errors(integrity_issues):
        raise ValueError("SQL integrity must pass before IF EXISTS layout can be normalized")

    edits: Dict[Tuple[int, int], str] = {}
    for pair in _exists_subquery_pairs(tokens):
        open_index = pair["open"]
        close_index = pair["close"]
        first_index = pair["first"]
        if_index = pair["if"]
        open_line, open_column, _ = _token_line_position(sql, tokens[open_index])
        close_line, _, _ = _token_line_position(sql, tokens[close_index])
        if if_index < 0 and open_line == close_line:
            continue
        inner_column = open_column + 1
        first_line, _, _ = _token_line_position(sql, tokens[first_index])
        if first_line != open_line + 1:
            _queue_whitespace_line_break(
                sql,
                tokens[open_index],
                tokens[first_index],
                inner_column,
                edits,
            )

        for index in _if_exists_inner_clause_indexes(tokens, pair):
            if index == first_index:
                continue
            previous = _previous_code_token(tokens, index - 1, open_index + 1)
            if previous is None:
                continue
            previous_line, _, _ = _token_line_position(sql, tokens[previous])
            clause_line, _, _ = _token_line_position(sql, tokens[index])
            if clause_line == previous_line:
                _queue_whitespace_line_break(
                    sql,
                    tokens[previous],
                    tokens[index],
                    inner_column,
                    edits,
                )

        previous = _previous_code_token(tokens, close_index - 1, open_index + 1)
        if previous is not None:
            previous_line, _, _ = _token_line_position(sql, tokens[previous])
            close_line, _, _ = _token_line_position(sql, tokens[close_index])
            if close_line == previous_line:
                _queue_whitespace_line_break(
                    sql,
                    tokens[previous],
                    tokens[close_index],
                    open_column,
                    edits,
                )

        begin_index = _next_code_token(tokens, close_index + 1, len(tokens))
        if (
            if_index >= 0
            and begin_index is not None
            and tokens[begin_index].normalized == "BEGIN"
        ):
            close_line, _, _ = _token_line_position(sql, tokens[close_index])
            begin_line, _, _ = _token_line_position(sql, tokens[begin_index])
            _, if_column, _ = _token_line_position(sql, tokens[if_index])
            if begin_line != close_line + 1:
                _queue_whitespace_line_break(
                    sql,
                    tokens[close_index],
                    tokens[begin_index],
                    if_column,
                    edits,
                )

    if edits:
        sql = _apply_text_edits(sql, edits)
        tokens, integrity_issues = _analyze_sql_integrity(
            sql,
            check_kind="if_exists_layout",
        )
        if _has_errors(integrity_issues):
            raise ValueError("IF EXISTS layout normalization damaged SQL integrity")

    directives: Dict[int, int] = {}
    lines = sql.splitlines()
    for pair in _exists_subquery_pairs(tokens):
        open_index = pair["open"]
        close_index = pair["close"]
        first_index = pair["first"]
        if_index = pair["if"]
        open_line, open_column, _ = _token_line_position(sql, tokens[open_index])
        close_line, _, _ = _token_line_position(sql, tokens[close_index])
        if if_index < 0 and open_line == close_line:
            continue
        target_indent = directives.get(open_line)
        if target_indent is not None and open_line <= len(lines):
            current_indent = len(lines[open_line - 1]) - len(
                lines[open_line - 1].lstrip(" \t")
            )
            open_column += target_indent - current_indent
        inner_column = open_column + 1

        first_line, _, first_line_leading = _token_line_position(
            sql,
            tokens[first_index],
        )
        if first_line == open_line + 1 and first_line_leading:
            directives[first_line] = inner_column

        close_line, _, close_line_leading = _token_line_position(
            sql,
            tokens[close_index],
        )
        if close_line_leading:
            directives[close_line] = open_column

        for index in _if_exists_inner_clause_indexes(tokens, pair):
            line, _, line_leading = _token_line_position(sql, tokens[index])
            if line_leading:
                directives[line] = inner_column

        begin_index = _next_code_token(tokens, close_index + 1, len(tokens))
        if (
            if_index >= 0
            and begin_index is not None
            and tokens[begin_index].normalized == "BEGIN"
        ):
            begin_line, _, begin_line_leading = _token_line_position(
                sql,
                tokens[begin_index],
            )
            _, if_column, _ = _token_line_position(sql, tokens[if_index])
            if begin_line == close_line + 1 and begin_line_leading:
                directives[begin_line] = if_column

    if not directives:
        return sql
    lines = sql.splitlines(keepends=True)
    for line_number, indent in directives.items():
        index = line_number - 1
        lines[index] = re.sub(r"^[ \t]*", " " * indent, lines[index], count=1)
    return "".join(lines)


def _queue_whitespace_line_break(
    sql: str,
    left: _SqlToken,
    right: _SqlToken,
    indent: int,
    edits: Dict[Tuple[int, int], str],
) -> None:
    separator = sql[left.end : right.start]
    if separator.strip():
        return
    edits[(left.end, right.start)] = "\n" + (" " * indent)


def _apply_text_edits(sql: str, edits: Mapping[Tuple[int, int], str]) -> str:
    result = sql
    for (start, end), replacement in sorted(
        edits.items(),
        key=lambda item: (item[0][0], item[0][1]),
        reverse=True,
    ):
        result = result[:start] + replacement + result[end:]
    return result


def _style_lint(
    original: str,
    formatted: str,
    original_tokens: Sequence[_SqlToken],
    formatted_tokens: Sequence[_SqlToken],
    *,
    operation: str,
) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    issues.extend(_check_tab_indentation(formatted))
    lowercase = _lowercase_sql_tokens(formatted_tokens)
    if lowercase:
        issues.append(
            SqlFormattingIssue(
                code="identifiers_not_uppercase",
                severity="error",
                message="SQL identifiers and keywords outside literals/comments must be uppercase.",
                evidence=lowercase[:10],
                check_kind="style",
            )
        )
    issues.extend(_check_alias_style(formatted_tokens))
    issues.extend(_check_procedure_parameter_layout(formatted))
    issues.extend(_check_select_leading_commas(formatted))
    issues.extend(_check_insert_select_layout(formatted))
    issues.extend(
        _check_join_layout(
            formatted,
            formatted_tokens,
            operation=operation,
        )
    )
    issues.extend(_check_if_exists_layout(formatted, formatted_tokens))
    issues.extend(_check_query_list_layout(formatted, formatted_tokens))
    if operation != "formatting":
        issues.extend(_check_case_parentheses(formatted, formatted_tokens))
    return issues


def _check_if_exists_layout(
    sql: str,
    tokens: Sequence[_SqlToken],
) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    for pair in _exists_subquery_pairs(tokens):
        if_index = pair["if"]
        open_index = pair["open"]
        close_index = pair["close"]
        first_index = pair["first"]
        open_line, open_column, _ = _token_line_position(sql, tokens[open_index])
        close_line, close_column, close_line_leading = _token_line_position(
            sql,
            tokens[close_index],
        )
        if if_index < 0 and open_line == close_line:
            continue
        if not close_line_leading or close_column != open_column:
            issues.append(
                SqlFormattingIssue(
                    code="if_exists_parenthesis_alignment_invalid",
                    severity="error",
                    message="EXISTS opening and closing parentheses must occupy the same column.",
                    evidence=[
                        f"line {open_line}:open column={open_column}, "
                        f"line {close_line}:close column={close_column}"
                    ],
                    check_kind="style",
                )
            )

        first_line, first_column, first_line_leading = _token_line_position(
            sql,
            tokens[first_index],
        )
        expected_inner_column = open_column + 1
        if (
            first_line != open_line + 1
            or not first_line_leading
            or first_column != expected_inner_column
        ):
            issues.append(
                SqlFormattingIssue(
                    code="if_exists_inner_start_alignment_invalid",
                    severity="error",
                    message="The first EXISTS SQL token must start on the next line one column right of the opening parenthesis.",
                    evidence=[
                        f"line {first_line}:{tokens[first_index].normalized} "
                        f"column={first_column}, expected line={open_line + 1}, "
                        f"column={expected_inner_column}"
                    ],
                    check_kind="style",
                )
            )

        clause_conflicts: List[str] = []
        for index in _if_exists_inner_clause_indexes(tokens, pair):
            line, column, line_leading = _token_line_position(sql, tokens[index])
            if line_leading and column == expected_inner_column:
                continue
            clause_conflicts.append(
                f"line {line}:{tokens[index].normalized} column={column}, "
                f"expected={expected_inner_column}"
            )
        if clause_conflicts:
            issues.append(
                SqlFormattingIssue(
                    code="if_exists_inner_clause_alignment_invalid",
                    severity="error",
                    message="Top-level EXISTS query clauses must align to the inner SQL start column.",
                    evidence=clause_conflicts[:16],
                    check_kind="style",
                )
            )

        begin_index = _next_code_token(tokens, close_index + 1, len(tokens))
        if (
            if_index >= 0
            and begin_index is not None
            and tokens[begin_index].normalized == "BEGIN"
        ):
            begin_line, begin_column, begin_line_leading = _token_line_position(
                sql,
                tokens[begin_index],
            )
            _, if_column, _ = _token_line_position(sql, tokens[if_index])
            if (
                begin_line != close_line + 1
                or not begin_line_leading
                or begin_column != if_column
            ):
                issues.append(
                    SqlFormattingIssue(
                        code="if_exists_begin_alignment_invalid",
                        severity="error",
                        message="BEGIN after IF EXISTS must start on the next line at the IF block column.",
                        evidence=[
                            f"line {begin_line}:BEGIN column={begin_column}, "
                            f"expected line={close_line + 1}, column={if_column}"
                        ],
                        check_kind="style",
                    )
                )
    return issues


def _check_tab_indentation(formatted_sql: str) -> List[SqlFormattingIssue]:
    conflicts = [
        f"line {line_number}: tab used in leading indentation"
        for line_number, line in enumerate(formatted_sql.splitlines(), start=1)
        if "\t" in line[: len(line) - len(line.lstrip(" \t"))]
    ]
    if not conflicts:
        return []
    return [
        SqlFormattingIssue(
            code="tab_indentation_not_allowed",
            severity="error",
            message="SQL layout indentation must use spaces; leading tabs are not accepted.",
            evidence=conflicts[:16],
            check_kind="style",
        )
    ]


def _check_join_layout(
    formatted_sql: str,
    formatted_tokens: Sequence[_SqlToken],
    *,
    operation: str,
) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    for scope in _build_sql_scopes(formatted_tokens):
        if len(scope.declarations) < 2:
            continue
        from_index = _source_marker_before(
            formatted_tokens,
            scope.declarations[0].source_start,
            scope.start,
            scope.depth,
            {"FROM"},
        )
        if from_index is None:
            continue
        _, from_column, _ = _token_line_position(
            formatted_sql,
            formatted_tokens[from_index],
        )
        for declaration in scope.declarations[1:]:
            join_index = _source_marker_before(
                formatted_tokens,
                declaration.source_start,
                scope.start,
                scope.depth,
                {"JOIN"},
            )
            if join_index is None:
                continue
            clause_start = _join_clause_start(
                formatted_sql,
                formatted_tokens,
                join_index,
            )
            line, clause_column, clause_line_leading = _token_line_position(
                formatted_sql,
                formatted_tokens[clause_start],
            )
            expected_join_column = from_column + int(
                _JOIN_LAYOUT_CONTRACT["join_indent_from_from"]
            )
            clause_line_numbers = {
                _token_line_position(formatted_sql, formatted_tokens[index])[0]
                for index in range(clause_start, join_index + 1)
                if formatted_tokens[index].kind not in {"line_comment", "block_comment"}
            }
            if len(clause_line_numbers) != 1:
                issues.append(
                    SqlFormattingIssue(
                        code="join_clause_split_across_lines",
                        severity="error",
                        message="JOIN type/hint prefixes and the JOIN token must stay on one line.",
                        evidence=[f"{scope.scope_id}:lines={sorted(clause_line_numbers)}"],
                        check_kind="style",
                    )
                )
            if not clause_line_leading or clause_column != expected_join_column:
                issues.append(
                    SqlFormattingIssue(
                        code="join_indentation_not_relative",
                        severity="error",
                        message="JOIN indentation must be relative to the current query scope's FROM column, including derived-table sources.",
                        evidence=[
                            f"{scope.scope_id}:line {line}:JOIN indent={clause_column}, "
                            f"expected={expected_join_column}, FROM indent={from_column}"
                        ],
                        check_kind="style",
                    )
                )

            _, join_column, _ = _token_line_position(
                formatted_sql,
                formatted_tokens[join_index],
            )
            expected_predicate_column = join_column + 2
            predicate_indexes = _same_join_predicate_indexes(
                formatted_sql,
                formatted_tokens,
                join_index,
                scope.end,
                scope.depth,
            )
            clause_words = {
                formatted_tokens[index].normalized
                for index in range(clause_start, join_index + 1)
                if formatted_tokens[index].kind not in {"line_comment", "block_comment"}
            }
            directional_outer = {"LEFT", "RIGHT", "FULL"} & clause_words
            if (
                operation == "generation"
                and directional_outer
                and "OUTER" not in clause_words
            ):
                issues.append(
                    SqlFormattingIssue(
                        code="outer_join_keyword_required",
                        severity="error",
                        message="LEFT, RIGHT, and FULL joins require the explicit OUTER keyword.",
                        evidence=[
                            f"{scope.scope_id}:line {line}:"
                            f"join_type={sorted(directional_outer)[0]}"
                        ],
                        check_kind="style",
                    )
                )
            if not predicate_indexes and "CROSS" not in clause_words:
                issues.append(
                    SqlFormattingIssue(
                        code="join_predicate_missing",
                        severity="error",
                        message="Every non-CROSS JOIN requires an ON predicate.",
                        evidence=[f"{scope.scope_id}:line {line}:JOIN has no ON predicate"],
                        check_kind="style",
                    )
                )
            on_index = next(
                (
                    index
                    for index in predicate_indexes
                    if formatted_tokens[index].normalized == "ON"
                ),
                None,
            )
            if on_index is not None and not _join_on_has_expression(
                formatted_tokens,
                on_index,
                scope.end,
                scope.depth,
            ):
                issues.append(
                    SqlFormattingIssue(
                        code="join_predicate_expression_missing",
                        severity="error",
                        message="JOIN ON must be followed by a predicate expression.",
                        evidence=[f"{scope.scope_id}:line {line}:ON has no expression"],
                        check_kind="style",
                    )
                )
            predicate_conflicts = []
            for predicate_index in predicate_indexes:
                predicate = formatted_tokens[predicate_index]
                predicate_line, predicate_column, line_leading = _token_line_position(
                    formatted_sql,
                    predicate,
                )
                if line_leading and predicate_column == expected_predicate_column:
                    continue
                predicate_conflicts.append(
                    f"{scope.scope_id}:line {predicate_line}:{predicate.normalized} "
                    f"column={predicate_column}, expected={expected_predicate_column}"
                )
            if predicate_conflicts:
                issues.append(
                    SqlFormattingIssue(
                        code="join_predicate_alignment_invalid",
                        severity="error",
                        message="ON and same-join AND/OR keywords must align to the I column of JOIN.",
                        evidence=predicate_conflicts[:16],
                        check_kind="style",
                    )
                )
            if declaration.source == "(DERIVED)":
                issues.extend(
                    _check_derived_source_block_layout(
                        formatted_sql,
                        formatted_tokens,
                        declaration,
                        scope.scope_id,
                        expected_join_column,
                    )
                )
    return issues


def _check_derived_source_block_layout(
    sql: str,
    tokens: Sequence[_SqlToken],
    declaration: _SourceDeclaration,
    scope_id: str,
    join_clause_column: int,
) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    close_index = declaration.source_name_end
    close_line, close_column, close_line_leading = _token_line_position(
        sql,
        tokens[close_index],
    )
    if not close_line_leading or close_column != join_clause_column:
        issues.append(
            SqlFormattingIssue(
                code="derived_join_closing_alias_indentation_invalid",
                severity="error",
                message="A derived-table closing parenthesis and alias must align with the outer JOIN clause start.",
                evidence=[
                    f"{scope_id}:line {close_line}:close indent={close_column}, expected={join_clause_column}"
                ],
                check_kind="style",
            )
        )

    if declaration.alias_start is not None:
        alias_line, _, _ = _token_line_position(
            sql,
            tokens[declaration.alias_start],
        )
        if alias_line != close_line:
            issues.append(
                SqlFormattingIssue(
                    code="derived_join_alias_detached",
                    severity="error",
                    message="A derived-table alias must remain on the same line as its closing parenthesis.",
                    evidence=[
                        f"{scope_id}:close line={close_line}, alias line={alias_line}"
                    ],
                    check_kind="style",
                )
            )

    inner_depth = tokens[declaration.source_start].depth + 1
    expected_inner_column = join_clause_column + int(
        _JOIN_LAYOUT_CONTRACT["derived_inner_clause_indent_from_join"]
    )
    clause_keywords = {"SELECT", "FROM", "WHERE", "GROUP", "HAVING", "ORDER", "UNION", "EXCEPT", "INTERSECT"}
    conflicts: List[str] = []
    for index in range(declaration.source_start + 1, close_index):
        token = tokens[index]
        if token.depth != inner_depth or token.normalized not in clause_keywords:
            continue
        line, column, line_leading = _token_line_position(sql, token)
        if line_leading and column == expected_inner_column:
            continue
        conflicts.append(
            f"{scope_id}:line {line}:{token.normalized} column={column}, expected={expected_inner_column}"
        )
    if conflicts:
        issues.append(
            SqlFormattingIssue(
                code="derived_query_clause_indentation_invalid",
                severity="error",
                message="Top-level clauses inside a derived table must align four columns inside the outer JOIN clause.",
                evidence=conflicts[:16],
                check_kind="style",
            )
        )
    return issues


def _source_marker_before(
    tokens: Sequence[_SqlToken],
    start: int,
    lower_bound: int,
    depth: int,
    markers: set[str],
) -> int | None:
    for index in range(start - 1, lower_bound - 1, -1):
        token = tokens[index]
        if token.depth == depth and token.normalized in markers:
            return index
    return None


def _join_clause_start(
    sql: str,
    tokens: Sequence[_SqlToken],
    join_index: int,
) -> int:
    start = join_index
    join_token = tokens[join_index]
    while start > 0:
        candidate = tokens[start - 1]
        if (
            candidate.depth != join_token.depth
            or candidate.normalized not in _JOIN_PREFIX_WORDS
        ):
            break
        start -= 1
    return start


def _same_join_predicate_indexes(
    sql: str,
    tokens: Sequence[_SqlToken],
    join_index: int,
    scope_end: int,
    depth: int,
) -> List[int]:
    predicate_indexes: List[int] = []
    on_seen = False
    contexts: List[str] = []
    for index in range(join_index + 1, scope_end):
        token = tokens[index]
        if token.kind in {"line_comment", "block_comment"}:
            continue
        if token.depth < depth:
            break
        if _is_join_predicate_boundary(tokens, index, scope_end, depth):
            break
        if not on_seen:
            if token.depth == depth and token.normalized == "ON":
                predicate_indexes.append(index)
                on_seen = True
            continue
        if token.text == "(":
            contexts.append("group")
            continue
        if token.text == ")":
            parenthesis_index = next(
                (
                    position
                    for position in range(len(contexts) - 1, -1, -1)
                    if contexts[position] in {"group", "subquery"}
                ),
                None,
            )
            if parenthesis_index is not None:
                del contexts[parenthesis_index:]
            continue
        if token.normalized == "SELECT" and token.depth > depth:
            parenthesis_index = next(
                (
                    position
                    for position in range(len(contexts) - 1, -1, -1)
                    if contexts[position] in {"group", "subquery"}
                ),
                None,
            )
            if parenthesis_index is not None:
                contexts[parenthesis_index] = "subquery"
            continue
        if "subquery" in contexts:
            continue
        if token.normalized == "CASE":
            contexts.append("case")
            continue
        if token.normalized == "END":
            case_index = next(
                (
                    position
                    for position in range(len(contexts) - 1, -1, -1)
                    if contexts[position] == "case"
                ),
                None,
            )
            if case_index is not None:
                del contexts[case_index]
            continue
        if token.normalized == "BETWEEN":
            contexts.append("between")
            continue
        if token.normalized not in {"AND", "OR"}:
            continue
        last_case = max(
            (position for position, context in enumerate(contexts) if context == "case"),
            default=-1,
        )
        last_between = max(
            (
                position
                for position, context in enumerate(contexts)
                if context == "between"
            ),
            default=-1,
        )
        if token.normalized == "AND" and last_between > last_case:
            del contexts[last_between]
            continue
        if last_case >= 0:
            continue
        _, _, line_leading = _token_line_position(sql, token)
        if line_leading:
            predicate_indexes.append(index)
    return predicate_indexes


def _join_on_has_expression(
    tokens: Sequence[_SqlToken],
    on_index: int,
    scope_end: int,
    depth: int,
) -> bool:
    invalid_leading_tokens = {
        ";",
        ",",
        ")",
        "=",
        "<",
        ">",
        "<=",
        ">=",
        "<>",
        "!=",
    }
    for index in range(on_index + 1, min(scope_end, len(tokens))):
        token = tokens[index]
        if token.kind in {"line_comment", "block_comment"}:
            continue
        if token.depth < depth:
            return False
        if _is_join_predicate_boundary(tokens, index, scope_end, depth):
            return False
        if token.text == "(":
            continue
        if token.text in invalid_leading_tokens or token.normalized in {"AND", "OR"}:
            return False
        return True
    return False


def _is_join_predicate_boundary(
    tokens: Sequence[_SqlToken],
    index: int,
    scope_end: int,
    depth: int,
) -> bool:
    token = tokens[index]
    if token.depth != depth:
        return False
    if token.normalized in _JOIN_PREDICATE_BOUNDARIES or token.text == ";":
        return True
    if token.normalized not in {"CROSS", "OUTER"}:
        return False
    next_index = _next_code_token(tokens, index + 1, min(scope_end, len(tokens)))
    return (
        next_index is not None
        and tokens[next_index].depth == depth
        and tokens[next_index].normalized == "APPLY"
    )


def _token_line_position(sql: str, token: _SqlToken) -> Tuple[int, int, bool]:
    line_start = sql.rfind("\n", 0, token.start) + 1
    prefix = sql[line_start:token.start]
    return sql.count("\n", 0, token.start) + 1, len(prefix), not prefix.strip()


def _check_alias_style(tokens: Sequence[_SqlToken]) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    scopes = _build_sql_scopes(tokens)
    invalid = []
    for scope in scopes:
        for declaration in scope.declarations:
            if declaration.alias_start is None:
                continue
            alias = declaration.effective_alias
            if scope.depth == 0 and re.fullmatch(r"T\d*|T[A-Z]\d+", alias):
                invalid.append(alias)
            elif scope.depth == 0 and not re.fullmatch(r"[A-SU-Z]\d*", alias):
                invalid.append(alias)
    if invalid:
        code = (
            "outer_query_uses_derived_table_internal_alias"
            if any(re.fullmatch(r"T\d*|T[A-Z]\d+", item) for item in invalid)
            else "ad_hoc_outer_alias"
        )
        issues.append(
            SqlFormattingIssue(
                code=code,
                severity="error",
                message=(
                    "Outer aliases must use A for the sole main source and sequential B, C, D... "
                    "support families; use T families inside derived scopes. Apply the current user's "
                    "explicit alias-preservation request before this style preference."
                ),
                evidence=invalid[:8],
                check_kind="style",
            )
        )
    return issues


def _exists_subquery_pairs(tokens: Sequence[_SqlToken]) -> List[Dict[str, int]]:
    pairs: List[Dict[str, int]] = []
    for exists_index, token in enumerate(tokens):
        if token.kind in {"line_comment", "block_comment"} or token.normalized != "EXISTS":
            continue
        previous = _previous_code_token(tokens, exists_index - 1, 0)
        if previous is None or tokens[previous].text == ".":
            continue
        anchor = _exists_predicate_anchor(tokens, exists_index)
        if anchor is None:
            continue
        if_index = anchor if tokens[anchor].normalized == "IF" else -1
        open_index = _next_code_token(tokens, exists_index + 1, len(tokens))
        if open_index is None or tokens[open_index].text != "(":
            continue
        close_index = _matching_parenthesis_token(tokens, open_index, len(tokens))
        if close_index is None:
            continue
        first_index = _next_code_token(tokens, open_index + 1, close_index)
        if first_index is None or tokens[first_index].normalized != "SELECT":
            continue
        pairs.append(
            {
                "if": if_index,
                "exists": exists_index,
                "open": open_index,
                "close": close_index,
                "first": first_index,
            }
        )
    return pairs


def _exists_predicate_anchor(
    tokens: Sequence[_SqlToken],
    exists_index: int,
) -> int | None:
    """Return the IF/WHERE/HAVING/ON clause that owns an EXISTS predicate."""
    cursor = _previous_code_token(tokens, exists_index - 1, 0)
    if cursor is None:
        return None
    if tokens[cursor].normalized == "NOT":
        cursor = _previous_code_token(tokens, cursor - 1, 0)
        if cursor is None:
            return None

    exists_depth = tokens[exists_index].depth
    predicate_clauses = {"IF", "WHERE", "HAVING", "ON"}
    expression_boundaries = {
        "CASE",
        "ELSE",
        "FROM",
        "SELECT",
        "SET",
        "THEN",
        "WHEN",
    }
    while cursor is not None:
        token = tokens[cursor]
        if token.normalized in predicate_clauses and token.depth <= exists_depth:
            return cursor
        if (
            token.depth <= exists_depth
            and (
                token.normalized in expression_boundaries
                or token.text in {",", ";"}
            )
        ):
            return None
        cursor = _previous_code_token(tokens, cursor - 1, 0)
    return None


def _if_exists_inner_clause_indexes(
    tokens: Sequence[_SqlToken],
    pair: Mapping[str, int],
) -> List[int]:
    open_index = pair["open"]
    close_index = pair["close"]
    inner_depth = tokens[open_index].depth + 1
    clause_words = {
        "SELECT",
        "FROM",
        "WHERE",
        "GROUP",
        "HAVING",
        "ORDER",
        "UNION",
        "INTERSECT",
        "EXCEPT",
    }
    return [
        index
        for index in range(open_index + 1, close_index)
        if tokens[index].kind not in {"line_comment", "block_comment"}
        and tokens[index].depth == inner_depth
        and tokens[index].normalized in clause_words
    ]


def _check_procedure_parameter_layout(sql: str) -> List[SqlFormattingIssue]:
    masked = _masked_sql(sql)
    if not re.search(r"\bCREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\b", masked, flags=re.IGNORECASE):
        return []
    lines = masked.splitlines()
    issues: List[SqlFormattingIssue] = []
    proc_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.search(r"\bCREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\b", line, flags=re.IGNORECASE)
        ),
        -1,
    )
    if proc_index < 0:
        return []
    if "@" in lines[proc_index]:
        issues.append(
            SqlFormattingIssue(
                code="procedure_first_parameter_same_line",
                severity="error",
                message="First stored procedure parameter must follow the procedure-name line.",
                evidence=[sql.splitlines()[proc_index].strip()],
                check_kind="style",
            )
        )
    parameter_lines = []
    for line in lines[proc_index + 1 :]:
        if re.match(r"^\s*AS\b", line, flags=re.IGNORECASE):
            break
        if re.search(r"@\w+", line):
            parameter_lines.append(line)
    for index, line in enumerate(parameter_lines):
        stripped = line.lstrip()
        if index == 0 and stripped.startswith(","):
            issues.append(
                SqlFormattingIssue(
                    code="procedure_first_parameter_leading_comma",
                    severity="error",
                    message="The first procedure parameter must not have a leading comma.",
                    evidence=[line],
                    check_kind="style",
                )
            )
        elif index > 0 and not stripped.startswith(","):
            issues.append(
                SqlFormattingIssue(
                    code="procedure_parameter_missing_leading_comma",
                    severity="error",
                    message="Procedure parameters after the first must have leading commas.",
                    evidence=[line],
                    check_kind="style",
                )
            )
    return issues


def _check_select_leading_commas(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    lines = _masked_sql(sql).splitlines()
    raw_lines = sql.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not re.match(r"^\s*SELECT\b", line, flags=re.IGNORECASE):
            index += 1
            continue
        select_indent = len(line) - len(line.lstrip(" "))
        column_seen = bool(re.search(r"\bSELECT\s+\S+", line, flags=re.IGNORECASE))
        index += 1
        while index < len(lines):
            candidate = lines[index]
            stripped = candidate.strip()
            if not stripped:
                index += 1
                continue
            if re.match(
                r"^(INTO|FROM|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|UNION|END|ELSE)\b",
                stripped,
                flags=re.IGNORECASE,
            ):
                break
            if column_seen and _looks_like_select_continuation_line(candidate):
                index += 1
                continue
            current_indent = len(candidate) - len(candidate.lstrip(" "))
            if current_indent >= select_indent and column_seen and not candidate.lstrip().startswith(","):
                issues.append(
                    SqlFormattingIssue(
                        code="select_column_missing_leading_comma",
                        severity="error",
                        message="SELECT columns after the first must use leading commas.",
                        evidence=[raw_lines[index] if index < len(raw_lines) else candidate],
                        check_kind="style",
                    )
                )
                break
            column_seen = True
            index += 1
    return issues


def _looks_like_select_continuation_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith(","):
        return False
    if re.match(
        r"^(AND|OR|WHEN|ELSE|END|INTO|FROM|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|UNION)\b",
        stripped,
        flags=re.IGNORECASE,
    ):
        return False
    if stripped.startswith(("+", "-", "*", "/", ")", ".")):
        return True
    if re.match(r"^(PARTITION\s+BY|ORDER\s+BY)\b", stripped, flags=re.IGNORECASE):
        return True
    return stripped == ")"


def _check_insert_select_layout(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    for block in _extract_insert_column_blocks(sql):
        lines = _meaningful_insert_lines(block)
        if len(lines) < 8:
            continue
        single_lines = [line for line in lines if _looks_like_single_insert_column_line(line)]
        if len(single_lines) >= max(8, int(len(lines) * 0.8)):
            issues.append(
                SqlFormattingIssue(
                    code="insert_select_single_column_per_line",
                    severity="error",
                    message="Wide INSERT ... SELECT mappings must retain grouped horizontal layout.",
                    evidence=single_lines[:6],
                    check_kind="style",
                )
            )
    issues.extend(_check_insert_select_value_layout(sql))
    return issues


def _check_insert_select_value_layout(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    for statement in _extract_insert_select_statements(sql):
        target_block = statement["target_block"]
        if len(_split_top_level_commas(target_block)) < _INSERT_SELECT_LAYOUT_CONTRACT[
            "wide_mapping_min_items"
        ]:
            continue
        target_lines = _meaningful_insert_lines(target_block)
        if _target_columns_are_vertical(target_lines):
            continue
        expressions = _select_expression_layout(statement["select_block"])
        if len(expressions) < _INSERT_SELECT_LAYOUT_CONTRACT["wide_mapping_min_items"]:
            continue
        starts_per_line: Dict[int, int] = {}
        for expression in expressions:
            line = int(expression["start_line"])
            starts_per_line[line] = starts_per_line.get(line, 0) + 1
        short_singletons = [
            expression
            for expression in expressions
            if int(expression["canonical_length"])
            <= _INSERT_SELECT_LAYOUT_CONTRACT["horizontal_expression_max_length"]
            and starts_per_line[int(expression["start_line"])] == 1
        ]
        if len(short_singletons) > _INSERT_SELECT_LAYOUT_CONTRACT["max_short_singleton_lines"]:
            evidence = [
                (
                    f"line={int(item['start_line']) + 1}; "
                    f"canonical_length={item['canonical_length']}; "
                    f"expression={item['text']}"
                )
                for item in short_singletons[:6]
            ]
            issues.append(
                SqlFormattingIssue(
                    code="insert_select_short_expressions_verticalized",
                    severity="error",
                    message=(
                        "Short INSERT ... SELECT mappings must remain horizontally grouped; "
                        "only expressions above the declared length threshold may use vertical fallback."
                    ),
                    evidence=evidence,
                    check_kind="style",
                )
            )
            issues.append(
                SqlFormattingIssue(
                    code="insert_select_value_list_verticalized",
                    severity="error",
                    message="Wide SELECT value lists must retain grouped horizontal mapping rows.",
                    evidence=evidence,
                    check_kind="style",
                )
            )
    return issues


def _select_expression_layout(select_block: str) -> List[Dict[str, Any]]:
    tokens, _ = _scan_sql_tokens(select_block)
    select_token = next(
        (
            token
            for token in tokens
            if token.kind not in {"line_comment", "block_comment"}
            and token.depth == 0
            and token.normalized == "SELECT"
        ),
        None,
    )
    if select_token is None:
        return []
    projection = select_block[select_token.end :]
    result: List[Dict[str, Any]] = []
    for text, start, _ in _split_top_level_comma_spans(projection):
        expression_tokens, _ = _scan_sql_tokens(text)
        canonical = [
            _canonical_token_value(token)
            for token in expression_tokens
            if token.kind not in {"line_comment", "block_comment"}
        ]
        result.append(
            {
                "text": " ".join(text.split()),
                "start_line": projection.count("\n", 0, start),
                "canonical_length": len(" ".join(canonical)),
            }
        )
    return result


def _split_top_level_comma_spans(value: str) -> List[Tuple[str, int, int]]:
    tokens, _ = _scan_sql_tokens(value)
    result: List[Tuple[str, int, int]] = []
    start = 0
    for token in tokens:
        if token.text != "," or token.depth != 0:
            continue
        _append_sql_span(result, value, start, token.start)
        start = token.end
    _append_sql_span(result, value, start, len(value))
    return result


def _append_sql_span(
    result: List[Tuple[str, int, int]],
    value: str,
    start: int,
    end: int,
) -> None:
    raw = value[start:end]
    leading = len(raw) - len(raw.lstrip())
    trailing = len(raw.rstrip())
    if trailing <= leading:
        return
    actual_start = start + leading
    actual_end = start + trailing
    result.append((value[actual_start:actual_end], actual_start, actual_end))


def _extract_insert_column_blocks(sql: str) -> List[str]:
    return [item["target_block"] for item in _extract_insert_select_statements(sql)]


def _extract_insert_select_statements(sql: str) -> List[Dict[str, str]]:
    masked = _masked_sql(sql)
    statements = []
    for match in re.finditer(r"\bINSERT\s+INTO\b", masked, flags=re.IGNORECASE):
        statement_end = _find_statement_end(masked, match.start())
        open_index = masked.find("(", match.end(), statement_end)
        if open_index < 0:
            continue
        close_index = _find_matching_parenthesis(masked, open_index)
        if close_index < 0 or close_index >= statement_end:
            continue
        source_starts = {
            keyword: _find_first_top_level_keyword(
                masked,
                close_index + 1,
                statement_end,
                {keyword},
            )
            for keyword in {"SELECT", "VALUES", "EXEC", "EXECUTE", "DEFAULT"}
        }
        source_candidates = [
            (position, keyword)
            for keyword, position in source_starts.items()
            if position >= 0
        ]
        if not source_candidates:
            continue
        select_start, source_kind = min(source_candidates)
        if source_kind != "SELECT":
            continue
        next_statement = _find_next_top_level_statement_start(
            masked,
            select_start + len("SELECT"),
            statement_end,
        )
        if next_statement >= 0:
            statement_end = next_statement
        projection_end = _find_first_top_level_keyword(
            masked,
            select_start + len("SELECT"),
            statement_end,
            {"FROM", "UNION", "EXCEPT", "INTERSECT", "ORDER", "OPTION", "FOR"},
        )
        if projection_end < 0:
            projection_end = statement_end
        statements.append(
            {
                "target_block": sql[open_index + 1 : close_index],
                "select_block": sql[select_start:projection_end],
            }
        )
    return statements


def _find_statement_end(sql: str, start: int) -> int:
    tokens, _ = _scan_sql_tokens(sql[start:])
    for token in tokens:
        if token.depth == 0 and (token.text == ";" or token.kind == "batch_separator"):
            return start + token.start
    return len(sql)


def _find_next_top_level_statement_start(sql: str, start: int, end: int) -> int:
    statement_starters = {
        "ALTER",
        "BACKUP",
        "BEGIN",
        "COMMIT",
        "CREATE",
        "DBCC",
        "DECLARE",
        "DELETE",
        "DENY",
        "DROP",
        "EXEC",
        "EXECUTE",
        "GRANT",
        "IF",
        "INSERT",
        "MERGE",
        "PRINT",
        "RAISERROR",
        "RESTORE",
        "RETURN",
        "REVOKE",
        "ROLLBACK",
        "SELECT",
        "SET",
        "THROW",
        "TRUNCATE",
        "UPDATE",
        "USE",
        "WHILE",
        "WITH",
    }
    tokens, _ = _scan_sql_tokens(sql[start:end])
    code_tokens = [
        token for token in tokens if token.kind not in {"line_comment", "block_comment"}
    ]
    for index, token in enumerate(code_tokens):
        if token.depth != 0 or token.normalized not in statement_starters:
            continue
        absolute_start = start + token.start
        line_start = sql.rfind("\n", 0, absolute_start) + 1
        if sql[line_start:absolute_start].strip():
            continue
        previous = code_tokens[index - 1].normalized if index else ""
        previous_previous = code_tokens[index - 2].normalized if index > 1 else ""
        if token.normalized == "SELECT" and (
            previous in {"UNION", "EXCEPT", "INTERSECT"}
            or (
                previous == "ALL"
                and previous_previous in {"UNION", "EXCEPT", "INTERSECT"}
            )
        ):
            continue
        return absolute_start
    return -1


def _find_first_top_level_keyword(
    sql: str,
    start: int,
    end: int,
    keywords: set[str],
) -> int:
    tokens, _ = _scan_sql_tokens(sql[start:end])
    for token in tokens:
        if token.depth == 0 and token.normalized in keywords:
            return start + token.start
    return -1


def _meaningful_insert_lines(block: str) -> List[str]:
    return [
        line.strip().rstrip(",")
        for line in block.splitlines()
        if line.strip() and line.strip() not in {"(", ")"}
    ]


def _target_columns_are_vertical(lines: Sequence[str]) -> bool:
    values = [line for line in lines if _looks_like_single_insert_column_line(line)]
    return len(values) >= max(8, int(len(lines) * 0.8))


def _looks_like_single_insert_column_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith(","):
        stripped = stripped[1:].strip()
    return bool(
        re.fullmatch(
            r"(?:\[[A-Z_][A-Z0-9_@$#]*\]|[A-Z_][A-Z0-9_@$#]*)(?:\s+AS\s+\w+)?",
            stripped,
            flags=re.IGNORECASE,
        )
    )


def _split_top_level_commas(value: str) -> List[str]:
    tokens, _ = _scan_sql_tokens(value)
    items = []
    start = 0
    for token in tokens:
        if token.text == "," and token.depth == 0:
            item = value[start:token.start].strip()
            if item:
                items.append(item)
            start = token.end
    tail = value[start:].strip()
    if tail:
        items.append(tail)
    return items


def _find_matching_parenthesis(sql: str, open_index: int) -> int:
    tokens, _ = _scan_sql_tokens(sql[open_index:])
    for token in tokens:
        if token.text == ")" and token.depth == 0:
            return open_index + token.start
    return -1


def _check_query_list_layout(
    sql: str,
    tokens: Sequence[_SqlToken],
) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    preferred = _QUERY_LIST_LAYOUT_CONTRACT["preferred_line_width"]
    hard = _QUERY_LIST_LAYOUT_CONTRACT["hard_line_width"]
    for clause in _query_list_clauses(tokens):
        items = clause["items"]
        if not items:
            continue
        clause_token = tokens[clause["keyword_index"]]
        clause_line = _sql_line_number(sql, clause_token.start)
        item_text = [_compact_query_list_item(item) for item in items]
        indent = _sql_line_indent(sql, clause_token.start)
        compact_width = indent + len(clause["name"]) + 1 + len(", ".join(item_text))
        item_lines = {
            _sql_line_number(sql, token.start)
            for item in items
            for token in item
        }
        is_inline = item_lines == {clause_line}
        all_simple = all(
            _query_list_item_is_simple(sql, item, clause["depth"])
            for item in items
        )
        evidence = [
            f"clause={clause['name']}",
            f"line={clause_line}",
            f"query_depth={clause['depth']}",
            f"item_count={len(items)}",
            f"compact_width={compact_width}",
            f"preferred_width={preferred}",
            f"hard_width={hard}",
        ]
        if all_simple and compact_width <= preferred and not is_inline:
            issues.append(
                SqlFormattingIssue(
                    code="query_list_unnecessary_verticalization",
                    severity="error",
                    message=(
                        "Short simple GROUP BY/ORDER BY lists that fit the preferred width "
                        "must remain inline."
                    ),
                    evidence=evidence,
                    check_kind="style",
                )
            )
        item_start_lines = [
            _sql_line_number(sql, next(token.start for token in item if token.text.strip()))
            for item in items
        ]
        physical_lines = sql.splitlines()
        underpacked_boundaries: List[str] = []
        for index in range(len(items) - 1):
            current_line = item_start_lines[index]
            next_line = item_start_lines[index + 1]
            if current_line == next_line or current_line > len(physical_lines):
                continue
            current_item_end_line = max(
                _sql_line_number(sql, token.start)
                for token in items[index]
                if token.text.strip()
            )
            if current_item_end_line != current_line:
                continue
            current_width = len(physical_lines[current_line - 1].expandtabs(4).rstrip())
            packed_width = current_width + 2 + len(item_text[index + 1])
            if packed_width <= preferred:
                underpacked_boundaries.append(
                    f"items={index + 1}/{index + 2}:lines={current_line}/{next_line}:"
                    f"packed_width={packed_width}"
                )
        if (
            all_simple
            and compact_width > preferred
            and underpacked_boundaries
        ):
            issues.append(
                SqlFormattingIssue(
                    code="query_list_not_compact",
                    severity="error",
                    message=(
                        "Long simple GROUP BY/ORDER BY lists must pack adjacent items into "
                        "compact continuation rows when they fit."
                    ),
                    evidence=[*evidence, *underpacked_boundaries],
                    check_kind="style",
                )
            )
        if is_inline and compact_width > preferred:
            issues.append(
                SqlFormattingIssue(
                    code="query_list_overlong_inline",
                    severity="error",
                    message=(
                        "GROUP BY/ORDER BY lists wider than the preferred width must wrap "
                        "at top-level commas; items remain atomic."
                    ),
                    evidence=[*evidence, f"hard_ceiling_exceeded={compact_width > hard}"],
                    check_kind="style",
                )
            )
        if all_simple and not is_inline:
            clause_end_line = max(item_start_lines, default=clause_line)
            overlong_lines = [
                line_number
                for line_number in range(clause_line, clause_end_line + 1)
                if line_number <= len(physical_lines)
                and len(physical_lines[line_number - 1].expandtabs(4)) > hard
            ]
            if overlong_lines:
                issues.append(
                    SqlFormattingIssue(
                        code="query_list_hard_width_exceeded",
                        severity="error",
                        message=(
                            "Wrapped simple GROUP BY/ORDER BY rows must stay within the hard width."
                        ),
                        evidence=[*evidence, f"lines={overlong_lines}"],
                        check_kind="style",
                    )
                )
            trailing_break_commas = []
            for comma_index, next_item in zip(clause["comma_indices"], items[1:]):
                next_token = next(
                    (token for token in next_item if token.kind not in {"line_comment", "block_comment"}),
                    None,
                )
                if next_token is None:
                    continue
                comma_line = _sql_line_number(sql, tokens[comma_index].start)
                next_line = _sql_line_number(sql, next_token.start)
                if comma_line != next_line:
                    trailing_break_commas.append(comma_line)
            if trailing_break_commas:
                issues.append(
                    SqlFormattingIssue(
                        code="query_list_continuation_comma_style",
                        severity="error",
                        message=(
                            "Wrapped GROUP BY/ORDER BY continuation rows must use leading commas."
                        ),
                        evidence=[*evidence, f"trailing_break_comma_lines={trailing_break_commas}"],
                        check_kind="style",
                    )
                )
    return issues


def _query_list_clauses(tokens: Sequence[_SqlToken]) -> List[Dict[str, Any]]:
    clauses: List[Dict[str, Any]] = []
    for scope in _build_sql_scopes(tokens):
        if tokens[scope.start].normalized != "SELECT":
            continue
        cursor = scope.start + 1
        while cursor < scope.end:
            token = tokens[cursor]
            if token.depth != scope.depth or token.normalized not in {"GROUP", "ORDER"}:
                cursor += 1
                continue
            by_index = _next_code_token_at_depth(tokens, cursor + 1, scope.end, scope.depth)
            if by_index is None or tokens[by_index].normalized != "BY":
                cursor += 1
                continue
            end = _query_list_clause_end(
                tokens,
                by_index + 1,
                scope.end,
                scope.depth,
                token.normalized,
            )
            clauses.append(
                {
                    "name": f"{token.normalized} BY",
                    "keyword_index": cursor,
                    "depth": scope.depth,
                    "items": _query_list_items(tokens, by_index + 1, end, scope.depth),
                    "comma_indices": [
                        index
                        for index in range(by_index + 1, end)
                        if tokens[index].text == "," and tokens[index].depth == scope.depth
                    ],
                }
            )
            cursor = max(end, by_index + 1)
    return clauses


def _next_code_token_at_depth(
    tokens: Sequence[_SqlToken],
    start: int,
    end: int,
    depth: int,
) -> int | None:
    for index in range(start, min(end, len(tokens))):
        token = tokens[index]
        if token.kind in {"line_comment", "block_comment"}:
            continue
        if token.depth == depth:
            return index
    return None


def _query_list_clause_end(
    tokens: Sequence[_SqlToken],
    start: int,
    end: int,
    depth: int,
    clause_keyword: str,
) -> int:
    stop_words = {
        "GROUP": {"HAVING", "ORDER", "OPTION", "UNION", "EXCEPT", "INTERSECT", "FOR"},
        "ORDER": {"OFFSET", "FETCH", "OPTION", "UNION", "EXCEPT", "INTERSECT", "FOR"},
    }[clause_keyword]
    for index in range(start, min(end, len(tokens))):
        token = tokens[index]
        if token.depth == depth and (token.normalized in stop_words or token.text == ";"):
            return index
    return min(end, len(tokens))


def _query_list_items(
    tokens: Sequence[_SqlToken],
    start: int,
    end: int,
    depth: int,
) -> List[List[_SqlToken]]:
    items: List[List[_SqlToken]] = []
    item_start = start
    for index in range(start, end):
        if tokens[index].text == "," and tokens[index].depth == depth:
            _append_query_list_item(items, tokens[item_start:index])
            item_start = index + 1
    _append_query_list_item(items, tokens[item_start:end])
    return items


def _append_query_list_item(
    items: List[List[_SqlToken]],
    candidate: Sequence[_SqlToken],
) -> None:
    item = list(candidate)
    if any(token.kind not in {"line_comment", "block_comment"} for token in item):
        items.append(item)


def _query_list_item_is_simple(
    sql: str,
    item: Sequence[_SqlToken],
    clause_depth: int,
) -> bool:
    if any(token.kind in {"line_comment", "block_comment"} for token in item):
        return False
    if any(token.normalized in {"CASE", "SELECT", "OVER"} for token in item):
        return False
    if max((token.depth for token in item), default=clause_depth) > clause_depth + 1:
        return False
    if len(_compact_query_list_item(item)) > _QUERY_LIST_LAYOUT_CONTRACT["simple_item_max_length"]:
        return False
    return len({_sql_line_number(sql, token.start) for token in item}) == 1


def _compact_query_list_item(item: Sequence[_SqlToken]) -> str:
    result = ""
    previous = ""
    for token in item:
        if token.kind in {"line_comment", "block_comment"}:
            text = " ".join(token.text.split())
        else:
            text = token.text
        if not result:
            result = text
        elif text in {".", ",", ")", ";"} or previous in {"(", "."}:
            result += text
        elif text == "(":
            result += text
        else:
            result += " " + text
        previous = text
    return result


def _check_case_parentheses(sql: str, tokens: Sequence[_SqlToken]) -> List[SqlFormattingIssue]:
    issues = []
    masked_lines = _masked_sql(sql).splitlines()
    for line in masked_lines:
        if re.search(r"\bCASE\b", line, flags=re.IGNORECASE) and not re.search(
            r"\(\s*CASE\b",
            line,
            flags=re.IGNORECASE,
        ):
            issues.append(
                SqlFormattingIssue(
                    code="case_not_parenthesized",
                    severity="error",
                    message="CASE expressions must be wrapped as (CASE ... END).",
                    evidence=[line.strip()],
                    check_kind="style",
                )
            )
    return issues
