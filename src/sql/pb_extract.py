"""Extract quoted DW queries and bounded PowerScript SQL with explicit provenance."""
from bisect import bisect_right
from pathlib import Path
import re
from typing import Any

from src.pb.lexer import scan_pb

POWERBUILDER_SQL_KEYWORD_PATTERN = re.compile(r'\b(SELECT|UPDATE|DELETE|INSERT|MERGE)\b', re.I)


def extract_powerbuilder_sql_fragments(
    source_text: str, *, source_name: str = '', max_lines_per_fragment: int = 80,
    token_optimizer_selected: bool = False,
) -> list[dict[str, Any]]:
    """`complete` describes an extracted boundary, never SQL validity or dynamic assembly."""
    if type(max_lines_per_fragment) is not int or max_lines_per_fragment < 1:
        raise ValueError('max_lines_per_fragment must be a positive integer')
    code, literals = scan_pb(source_text)
    comments_masked = scan_pb(source_text, mask_literals=False)[0]
    starts = [0] + [m.end() for m in re.finditer('\n', source_text)]
    fragments: list[dict[str, Any]] = []

    def add(start: int, end: int, sql: str, keyword: str, kind: str, complete: bool) -> None:
        first = bisect_right(starts, start)
        item: dict[str, Any] = {
            'fragment_id': f'{Path(source_name).name or "powerbuilder"}:{first}:{start}:{keyword}',
            'source_name': source_name, 'keyword': keyword,
            'start_line': first, 'end_line': bisect_right(starts, max(start, end - 1)),
            'start_offset': start, 'end_offset': end,
            'sql_text': sql, 'extraction_kind': kind, 'complete': complete,
        }
        if token_optimizer_selected:
            item.update(token_optimizer_status='passthrough',
                        token_optimizer_status_reason='SQL source text was not compressed.')
        fragments.append(item)

    for literal in literals:
        sql = literal.value.strip()
        keyword = POWERBUILDER_SQL_KEYWORD_PATTERN.match(sql)
        if keyword is None or not sql[keyword.end():].strip():
            continue
        retrieve = re.search(r'\bretrieve\s*=\s*$', code[:literal.start], re.I)
        complete = bool(retrieve and literal.complete and not code[literal.end:].lstrip(' \t').startswith(('+', '&')))
        add(literal.start, literal.end, sql, keyword[1].upper(),
            'datawindow_retrieve' if retrieve else 'string_candidate', complete)

    consumed = 0
    for match in POWERBUILDER_SQL_KEYWORD_PATTERN.finditer(code):
        if match.start() < consumed:
            continue
        if match.start() and code[match.start() - 1] == '.':
            continue
        if match[1].upper() != 'SELECT' and code[match.end():].lstrip().startswith('('):
            continue
        line = bisect_right(starts, match.start()) - 1
        limit_line = line + max_lines_per_fragment
        limit = starts[limit_line] if limit_line < len(starts) else len(code)
        semicolon = code.find(';', match.end(), limit)
        end = semicolon + 1 if semicolon >= 0 else limit
        add(match.start(), end, comments_masked[match.start():end].strip(), match[1].upper(),
            'embedded_sql', semicolon >= 0)
        consumed = end
    embedded = [(item['start_offset'], item['end_offset']) for item in fragments if item['extraction_kind'] == 'embedded_sql']
    fragments = [item for item in fragments if item['extraction_kind'] != 'string_candidate'
                 or not any(start <= item['start_offset'] < end for start, end in embedded)]
    return sorted(fragments, key=lambda item: item['start_offset'])
