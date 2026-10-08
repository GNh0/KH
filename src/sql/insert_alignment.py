"""Align observable horizontal INSERT/SELECT mappings by text columns."""
from dataclasses import dataclass
from collections.abc import Iterable
import unicodedata

from .lexer import SqlFormattingIssue, _SqlToken, _scan_sql_tokens, _sql_line_number


_PROTECTED = {'string', 'unicode_string', 'line_comment', 'block_comment', 'bracket_identifier', 'quoted_identifier'}


def _text_columns(text: str, start: int = 0) -> int:
    column = start
    for char in text:
        if char == '\t':
            column += 4 - column % 4
        elif char not in '\r\n' and not unicodedata.combining(char):
            column += 2 if unicodedata.east_asian_width(char) in {'W', 'F'} else 1
    return column - start


def _expand_layout_tabs(sql: str) -> str:
    """Expand input whitespace at four-column stops, preserving token content."""
    tokens, _ = _scan_sql_tokens(sql)
    protected = iter(token for token in tokens if token.kind in _PROTECTED)
    current = next(protected, None)
    result: list[str] = []
    column = 0
    for index, char in enumerate(sql):
        while current is not None and index >= current.end:
            current = next(protected, None)
        in_token = current is not None and current.start <= index < current.end
        if char == '\t':
            width = 4 - column % 4
            result.append(char if in_token else ' ' * width)
            column += width
        else:
            result.append(char)
            column = 0 if char == '\n' else column + _text_columns(char)
    return ''.join(result)


@dataclass(frozen=True)
class _Cell:
    start: int
    end: int
    comma: int | None


@dataclass(frozen=True)
class _Mapping:
    targets: tuple[tuple[_Cell, ...], ...]
    values: tuple[tuple[_Cell, ...], ...]
    columns: tuple[int, ...]
    select_end: int


def _position(sql: str, offset: int) -> int:
    return _text_columns(sql[sql.rfind('\n', 0, offset) + 1:offset])


def _cells(sql: str, start: int, end: int, *, select: bool) -> tuple[list[_Cell], int, str]:
    tokens, _ = _scan_sql_tokens(sql[start:end])
    reason = 'comments interrupt the mapping list' if any(token.kind in {'line_comment', 'block_comment'} for token in tokens) else ''
    tokens = [token for token in tokens if token.kind not in {'line_comment', 'block_comment'}]
    select_end = start
    if select:
        if not tokens or tokens[0].normalized != 'SELECT':
            return [], start, 'SELECT projection is not resolved'
        select_end = start + tokens.pop(0).end
        if tokens and tokens[0].normalized in {'TOP', 'DISTINCT', 'ALL'}:
            return [], select_end, 'SELECT modifiers require direct layout review'
    cells: list[_Cell] = []
    group: list[_SqlToken] = []
    comma: int | None = None
    for token in tokens:
        if token.depth == 0 and token.text == ',':
            if not group:
                return [], select_end, 'empty mapping item'
            cells.append(_Cell(start + group[0].start, start + group[-1].end, comma))
            group = []
            comma = start + token.start
        else:
            group.append(token)
    if group:
        cells.append(_Cell(start + group[0].start, start + group[-1].end, comma))
    if any('\n' in sql[cell.start:cell.end] or '\t' in sql[cell.start:cell.end] for cell in cells):
        return cells, select_end, 'multiline or tab-containing expressions require direct layout review'
    return cells, select_end, reason


def _rows(sql: str, cells: list[_Cell]) -> tuple[tuple[_Cell, ...], ...]:
    rows: list[list[_Cell]] = []
    previous_line = -1
    for cell in cells:
        line = _sql_line_number(sql, cell.start)
        if line != previous_line:
            rows.append([])
            previous_line = line
        rows[-1].append(cell)
    return tuple(tuple(row) for row in rows)


def _mapping_records(sql: str, ranges: Iterable[tuple[int, int, int, int]]) -> tuple[list[_Mapping], list[SqlFormattingIssue]]:
    mappings: list[_Mapping] = []
    issues: list[SqlFormattingIssue] = []
    for target_start, target_end, select_start, select_end in ranges:
        targets, _, target_reason = _cells(sql, target_start, target_end, select=False)
        values, prefix_end, value_reason = _cells(sql, select_start, select_end, select=True)
        if max(len(targets), len(values)) < 8:
            continue
        target_rows, value_rows = _rows(sql, targets), _rows(sql, values)
        if len(target_rows) <= 1 and len(value_rows) <= 1 and not (target_reason or value_reason):
            continue
        reason = target_reason or value_reason
        if len(targets) != len(values):
            reason = reason or 'target and source item counts differ'
        if not reason and tuple(map(len, target_rows)) != tuple(map(len, value_rows)):
            reason = 'target and source horizontal row groups differ'
        all_rows = target_rows + value_rows
        if not reason and not any(len(row) > 1 for row in all_rows):
            continue
        if not reason:
            for row in all_rows:
                first = row[0]
                line_start = sql.rfind('\n', 0, first.start) + 1
                if first.comma is not None:
                    prefix = sql[line_start:first.comma]
                    if _sql_line_number(sql, first.comma) != _sql_line_number(sql, first.start) or prefix.strip():
                        reason = 'row-leading commas or list boundaries require direct layout review'
                        break
                elif first is targets[0] and sql[line_start:first.start].strip():
                    reason = 'inline INSERT columns require direct layout review'
                    break
        if reason:
            issues.append(SqlFormattingIssue('insert_select_alignment_unverified', 'warning',
                'Horizontal INSERT/SELECT column alignment was not normalized; inspect the actual mapping.',
                evidence=[f'line {_sql_line_number(sql, select_start)}: {reason}'], check_kind='style'))
            continue
        widths = [max(_text_columns(sql[row[n].start:row[n].end])
                      for row in all_rows if n < len(row))
                  for n in range(max(map(len, all_rows)))]
        columns: list[int] = []
        for n, _ in enumerate(widths):
            minimum = (_position(sql, select_start) + len('SELECT ') if not n
                       else columns[-1] + widths[n - 1] + 3)
            existing = {_position(sql, row[n].start) for row in all_rows if n < len(row)}
            columns.append(max(minimum, next(iter(existing))) if len(existing) == 1 else minimum)
        mappings.append(_Mapping(target_rows, value_rows, tuple(columns), prefix_end))
    return mappings, issues


def normalize_insert_select_alignment(sql: str, ranges: Iterable[tuple[int, int, int, int]]) -> str:
    edits: dict[tuple[int, int], str] = {}
    for mapping in _mapping_records(sql, ranges)[0]:
        for row in mapping.targets + mapping.values:
            for n, cell in enumerate(row):
                column = mapping.columns[n]
                if cell.comma is not None:
                    left = row[n - 1].end if n else sql.rfind('\n', 0, cell.start) + 1
                    prefix_column = (mapping.columns[n - 1] + _text_columns(sql[row[n - 1].start:row[n - 1].end])) if n else 0
                    edits[(left, cell.comma)] = ' ' * (column - 2 - prefix_column)
                    edits[(cell.comma + 1, cell.start)] = ' '
                else:
                    line_start = sql.rfind('\n', 0, cell.start) + 1
                    left = mapping.select_end if sql[line_start:cell.start].strip() else line_start
                    edits[(left, cell.start)] = ' ' * (column - _position(sql, left))
    for (start, end), text in sorted(edits.items(), reverse=True):
        sql = sql[:start] + text + sql[end:]
    return sql


def check_insert_select_alignment(sql: str, ranges: Iterable[tuple[int, int, int, int]]) -> list[SqlFormattingIssue]:
    mappings, issues = _mapping_records(sql, ranges)
    for mapping in mappings:
        evidence: list[str] = []
        for row in mapping.targets + mapping.values:
            for n, cell in enumerate(row):
                actual = _position(sql, cell.start)
                expected = mapping.columns[n]
                if actual != expected or (cell.comma is not None and _position(sql, cell.comma) != expected - 2):
                    evidence.append(f'line {_sql_line_number(sql, cell.start)}: {sql[cell.start:cell.end]} '
                                    f'column={actual + 1}, expected={expected + 1}')
        if evidence:
            issues.append(SqlFormattingIssue('insert_select_column_alignment_invalid', 'warning',
                'Align target columns and SELECT expressions at the same actual text columns, using spaces and widths from both lists.',
                evidence=evidence[:16], check_kind='style'))
    return issues
