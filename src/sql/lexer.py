"""Retained sql syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class SqlFormattingIssue:
    code: str
    severity: str
    message: str
    evidence: List[str] = field(default_factory=list)
    check_kind: str = "mechanical"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "evidence": list(self.evidence),
            "check_kind": self.check_kind,
        }


@dataclass(frozen=True)
class _SqlToken:
    index: int
    kind: str
    text: str
    start: int
    end: int
    depth: int

    @property
    def normalized(self) -> str:
        if self.kind in {"string", "line_comment", "block_comment"}:
            return self.text
        if self.kind == "unicode_string":
            return "N" + self.text[1:]
        if self.kind == "batch_separator":
            return "<GO_BATCH>"
        if self.kind == "bracket_identifier":
            return "[" + self.text[1:-1].replace("]]", "]").upper() + "]"
        if self.kind == "quoted_identifier":
            return '"' + self.text[1:-1].replace('""', '"').upper() + '"'
        if self.kind == "word":
            return self.text.upper()
        return self.text


def _scan_sql_tokens(sql: str) -> Tuple[List[_SqlToken], List[Tuple[str, str, str]]]:
    tokens: List[_SqlToken] = []
    issues: List[Tuple[str, str, str]] = []
    index = 0
    depth = 0
    open_parentheses: List[int] = []

    def emit(kind: str, text: str, start: int, end: int, token_depth: int | None = None) -> None:
        tokens.append(
            _SqlToken(
                index=len(tokens),
                kind=kind,
                text=text,
                start=start,
                end=end,
                depth=depth if token_depth is None else token_depth,
            )
        )

    while index < len(sql):
        char = sql[index]
        pair = sql[index : index + 2]
        if char.isspace():
            index += 1
            continue
        if pair == "--":
            start = index
            newline = sql.find("\n", index + 2)
            index = len(sql) if newline < 0 else newline
            emit("line_comment", sql[start:index], start, index)
            continue
        if pair == "/*":
            start = index
            nesting = 1
            index += 2
            while index < len(sql) and nesting:
                current = sql[index : index + 2]
                if current == "/*":
                    nesting += 1
                    index += 2
                elif current == "*/":
                    nesting -= 1
                    index += 2
                else:
                    index += 1
            emit("block_comment", sql[start:index], start, index)
            if nesting:
                issues.append(
                    (
                        "unclosed_block_comment",
                        "SQL contains a block comment without a closing */ marker.",
                        f"offset={start}",
                    )
                )
            continue
        if char in "Nn" and index + 1 < len(sql) and sql[index + 1] == "'":
            start = index
            index += 2
            closed = False
            while index < len(sql):
                if sql[index] == "'":
                    if index + 1 < len(sql) and sql[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    closed = True
                    break
                index += 1
            emit("unicode_string", sql[start:index], start, index)
            if not closed:
                issues.append(
                    (
                        "unclosed_string_literal",
                        "SQL contains a string literal without a closing quote.",
                        f"offset={start}",
                    )
                )
            continue
        if char == "'":
            start = index
            index += 1
            closed = False
            while index < len(sql):
                if sql[index] == "'":
                    if index + 1 < len(sql) and sql[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    closed = True
                    break
                index += 1
            emit("string", sql[start:index], start, index)
            if not closed:
                issues.append(
                    (
                        "unclosed_string_literal",
                        "SQL contains a string literal without a closing quote.",
                        f"offset={start}",
                    )
                )
            continue
        if char == "[":
            start = index
            index += 1
            closed = False
            while index < len(sql):
                if sql[index] == "]":
                    if index + 1 < len(sql) and sql[index + 1] == "]":
                        index += 2
                        continue
                    index += 1
                    closed = True
                    break
                index += 1
            emit("bracket_identifier", sql[start:index], start, index)
            if not closed:
                issues.append(
                    (
                        "unclosed_bracket_identifier",
                        "SQL contains a bracketed identifier without a closing ].",
                        f"offset={start}",
                    )
                )
            continue
        if char == '"':
            start = index
            index += 1
            closed = False
            while index < len(sql):
                if sql[index] == '"':
                    if index + 1 < len(sql) and sql[index + 1] == '"':
                        index += 2
                        continue
                    index += 1
                    closed = True
                    break
                index += 1
            emit("quoted_identifier", sql[start:index], start, index)
            if not closed:
                issues.append(
                    (
                        "unclosed_quoted_identifier",
                        "SQL contains a quoted identifier without a closing quote.",
                        f"offset={start}",
                    )
                )
            continue
        if char == "(":
            emit("symbol", char, index, index + 1)
            open_parentheses.append(index)
            depth += 1
            index += 1
            continue
        if char == ")":
            if open_parentheses:
                open_parentheses.pop()
                depth -= 1
                emit("symbol", char, index, index + 1, depth)
            else:
                emit("symbol", char, index, index + 1, 0)
                issues.append(
                    (
                        "unbalanced_parentheses",
                        "SQL contains an unmatched closing parenthesis.",
                        f"offset={index}",
                    )
                )
            index += 1
            continue
        if char.isalpha() or char in "_@#$" or ord(char) > 127:
            start = index
            index += 1
            while index < len(sql) and (
                sql[index].isalnum() or sql[index] in "_@#$" or ord(sql[index]) > 127
            ):
                index += 1
            text = sql[start:index]
            line_start = sql.rfind("\n", 0, start) + 1
            line_end = sql.find("\n", index)
            if line_end < 0:
                line_end = len(sql)
            line = sql[line_start:line_end]
            kind = (
                "batch_separator"
                if text.upper() == "GO"
                and re.fullmatch(r"\s*GO(?:\s+\d+)?(?:\s*--[^\r\n]*)?\s*", line, re.IGNORECASE)
                else "word"
            )
            emit(kind, text, start, index)
            continue
        if char.isdigit():
            start = index
            index += 1
            while index < len(sql) and (sql[index].isalnum() or sql[index] in "._"):
                index += 1
            emit("number", sql[start:index], start, index)
            continue
        if pair in {"<=", ">=", "<>", "!=", "!<", "!>", "+=", "-=", "*=", "/=", "%=", "::"}:
            emit("symbol", pair, index, index + 2)
            index += 2
            continue
        emit("symbol", char, index, index + 1)
        index += 1

    if open_parentheses:
        issues.append(
            (
                "unbalanced_parentheses",
                "SQL contains one or more unclosed opening parentheses.",
                "offsets=" + ",".join(str(value) for value in open_parentheses[:8]),
            )
        )
    return tokens, issues


def _analyze_sql_integrity(
    sql: str,
    *,
    check_kind: str,
) -> Tuple[List[_SqlToken], List[SqlFormattingIssue]]:
    tokens, records = _scan_sql_tokens(sql)
    issues = []
    for code, message, evidence in records:
        output_code = (
            "unterminated_string_literal"
            if check_kind == "formatter_output_integrity" and code == "unclosed_string_literal"
            else code
        )
        issues.append(
            SqlFormattingIssue(
                code=output_code,
                severity="error",
                message=message,
                evidence=[evidence],
                check_kind=check_kind,
            )
        )
    if not records:
        code_tokens = [item for item in tokens if item.kind not in {"line_comment", "block_comment"}]
        for position, token in enumerate(code_tokens):
            if token.normalized != "SELECT":
                continue
            for cursor in range(position + 1, len(code_tokens)):
                candidate = code_tokens[cursor]
                if candidate.depth < token.depth:
                    break
                if candidate.depth == token.depth and candidate.normalized in {";", "UNION", "EXCEPT", "INTERSECT", "END"}:
                    break
                if candidate.depth == token.depth and candidate.normalized == "FROM":
                    previous = code_tokens[cursor - 1] if cursor > position + 1 else None
                    if previous and previous.text == ",":
                        issues.append(
                            SqlFormattingIssue(
                                code="dangling_select_comma",
                                severity="error",
                                message="SELECT projection has a dangling comma before FROM.",
                                evidence=[f"offset={previous.start}"],
                                check_kind=check_kind,
                            )
                        )
                    break
    return tokens, issues


def _previous_code_token(
    tokens: Sequence[_SqlToken],
    start: int,
    lower_bound: int,
) -> int | None:
    for index in range(start, lower_bound - 1, -1):
        if tokens[index].kind not in {"line_comment", "block_comment"}:
            return index
    return None


def _canonical_token_value(token: _SqlToken) -> str:
    if token.kind == "line_comment":
        return "LINE_COMMENT:" + token.text
    if token.kind == "block_comment":
        return "BLOCK_COMMENT:" + token.text
    if token.kind == "string":
        return "STRING:" + token.text
    if token.kind == "unicode_string":
        return "UNICODE_STRING:N" + token.text[1:]
    if token.kind == "bracket_identifier":
        return "BRACKET_IDENTIFIER:" + token.text
    if token.kind == "quoted_identifier":
        return "QUOTED_IDENTIFIER:" + token.text
    return token.normalized


def _next_code_token(tokens: Sequence[_SqlToken], start: int, end: int) -> int | None:
    for index in range(start, min(end, len(tokens))):
        if tokens[index].kind not in {"line_comment", "block_comment"}:
            return index
    return None


def _matching_parenthesis_token(
    tokens: Sequence[_SqlToken],
    open_index: int,
    end: int,
) -> int | None:
    target_depth = tokens[open_index].depth
    for index in range(open_index + 1, min(end, len(tokens))):
        if tokens[index].text == ")" and tokens[index].depth == target_depth:
            return index
    return None


def _is_identifier_token(token: _SqlToken) -> bool:
    return token.kind in {"word", "bracket_identifier", "quoted_identifier"}


def _identifier_value(token: _SqlToken) -> str:
    if not _is_identifier_token(token):
        return ""
    if token.kind == "bracket_identifier":
        return token.text[1:-1].replace("]]", "]").upper()
    if token.kind == "quoted_identifier":
        return token.text[1:-1].replace('""', '"').upper()
    return token.text.upper()


def _normalize_source(value: str) -> str:
    return value.replace("[", "").replace("]", "").replace('"', "").strip().upper()


def _base_source(value: str) -> str:
    return _normalize_source(value).rsplit(".", 1)[-1]


def _lowercase_sql_tokens(tokens: Sequence[_SqlToken]) -> List[str]:
    values = []
    for index, token in enumerate(tokens):
        if token.kind != "word" or not any("a" <= char <= "z" for char in token.text):
            continue
        previous = tokens[index - 1] if index else None
        if previous and previous.text == ":":
            continue
        if token.text.startswith("@@"):
            continue
        values.append(token.text)
    return sorted(set(values))


def _masked_sql(sql: str) -> str:
    tokens, _ = _scan_sql_tokens(sql)
    chars = list(sql)
    for token in tokens:
        if token.kind not in {"string", "line_comment", "block_comment"}:
            continue
        for index in range(token.start, token.end):
            if chars[index] not in "\r\n":
                chars[index] = " "
    return "".join(chars)


def _sql_line_number(sql: str, offset: int) -> int:
    return sql.count("\n", 0, offset) + 1


def _sql_line_indent(sql: str, offset: int) -> int:
    line_start = sql.rfind("\n", 0, offset) + 1
    prefix = sql[line_start:offset]
    return len(prefix) - len(prefix.lstrip(" \t"))


def _has_errors(issues: Iterable[SqlFormattingIssue]) -> bool:
    return any(item.severity == "error" for item in issues)
