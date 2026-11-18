"""Procedure header structure and explicitly selected authors, not style approval."""
from dataclasses import dataclass
from datetime import datetime
import re
from typing import TypedDict
import unicodedata

from src.common.results import Issue
from .delta import _dml_statement_end, _identifier_path_at
from .lexer import _base_source, _scan_sql_tokens, _identifier_value, _is_identifier_token, _next_code_token, _SqlToken
from .scopes import _next_after_top_modifier, _parse_scope_declarations


@dataclass(frozen=True)
class ProcedureHeader:
    name: str
    line: int
    fields: dict[str, str]
    framed: bool
    parts: tuple[str, ...]
    unit_start: int
    unit_end: int
    body_observed: bool
    declaration: str
    body_start: int


def author_key(value: str) -> str:
    return unicodedata.normalize('NFC', value.strip()).casefold()


class AuthorSelection(TypedDict):
    author: str
    reference_author: str | list[str]


def selected_authors(author: str | None, reference_author: str | list[str] | None) -> AuthorSelection:
    references = reference_author if isinstance(reference_author, list) else [reference_author]
    if not references or any(not isinstance(value, str) or not value.strip() or len(value) > 160 or
                             any(char in value for char in '\r\n\x00{}') for value in (author, *references)):
        raise ValueError('Supply the name for the SP header and the name(s) to search for in existing SP headers.')
    names = list(dict.fromkeys(str(value).strip() for value in references))
    # Keep single-name CLI output and previously stored selections compatible.
    return {'author': str(author).strip(), 'reference_author': names[0] if len(names) == 1 else names}


def _complete_blocks(tokens: list[_SqlToken]) -> bool:
    """Reject observed truncation; this is not a complete T-SQL parser."""
    stack = []
    for index, token in enumerate(tokens):
        if token.kind != 'word':
            continue
        word = token.normalized
        following = tokens[index + 1].normalized if index + 1 < len(tokens) else ''
        if word == 'CASE':
            stack.append('CASE')
        elif word == 'BEGIN' and following not in {'TRAN', 'TRANSACTION', 'DISTRIBUTED', 'DIALOG', 'CONVERSATION'}:
            stack.append('BEGIN')
        elif word == 'END' and following != 'CONVERSATION':
            if not stack:
                return False
            stack.pop()
    return not stack


def procedure_headers(source: str) -> list[ProcedureHeader]:
    scanned = _scan_sql_tokens(source)[0]
    positions = {token.start: index for index, token in enumerate(scanned)}
    tokens = [t for t in scanned if t.kind not in {'line_comment', 'block_comment'}]
    result = []
    for index, token in enumerate(tokens):
        if token.kind != 'word' or token.normalized not in {'CREATE', 'ALTER'}:
            continue
        if token.normalized == 'ALTER' and index >= 2 and [t.normalized for t in tokens[index - 2:index]] == ['CREATE', 'OR']:
            continue
        cursor = index + 1
        declaration = token.normalized
        if [t.normalized for t in tokens[cursor:cursor + 2]] == ['OR', 'ALTER']:
            declaration = 'CREATE OR ALTER'
            cursor += 2
        if cursor >= len(tokens) or tokens[cursor].normalized not in {'PROC', 'PROCEDURE'}:
            continue
        cursor += 1
        names = []
        while cursor < len(tokens) and _is_identifier_token(tokens[cursor]):
            names.append(_identifier_value(tokens[cursor]))
            cursor += 1
            if cursor >= len(tokens) or tokens[cursor].text != '.':
                break
            cursor += 1
        if not names:
            continue
        comments = []
        comment_offsets = []
        following = token.start
        for comment in reversed(scanned[:positions[token.start]]):
            if comment.kind != 'line_comment' or source[comment.end:following].strip():
                break
            line_start = max(source.rfind('\n', 0, comment.start), source.rfind('\r', 0, comment.start)) + 1
            if source[line_start:comment.start].strip():
                break  # GO/other statement trailing comments do not introduce this SP.
            comments.append(comment.text.strip())
            comment_offsets.append(comment.start)
            following = comment.start
        comments.reverse()
        comment_offsets.reverse()
        separators = [i for i, line in enumerate(comments) if re.fullmatch(r'--\s*={3,}', line)]
        framed = len(separators) >= 2 and separators[-1] == len(comments) - 1
        body = comments[separators[-2] + 1:separators[-1]] if framed else comments
        fields = {}
        search_fields = [line for line in body if re.match(
            r'--\s*(?:REFERENCE[\s_-]*AUTHORS?|(?:참조|참고)\s*작성자)\s*:', line, re.I)]
        if search_fields:
            fields['REFERENCE AUTHOR'] = '\n'.join(search_fields)
        for key in ('AUTHOR', 'CREATE DATE', 'DESCRIPTION'):
            matches = [match[1].strip() for line in body if
                       (match := re.fullmatch(r'--\s*' + key + r'\s*:\s*(.*?)\s*', line, re.I))]
            if len(matches) == 1 and matches[0] and not any(char in matches[0] for char in '{}'):
                fields[key] = matches[0]
        start = comment_offsets[separators[-2]] if framed else comment_offsets[0] if comment_offsets else token.start
        end = next((t.start for t in scanned[positions[token.start] + 1:] if t.kind == 'batch_separator'), len(source))
        body_tokens = []
        body_start = end
        for body_index in range(cursor, len(tokens)):
            value = tokens[body_index]
            if value.start >= end:
                break
            previous = tokens[body_index - 1] if body_index else None
            if value.kind == 'word' and value.normalized == 'AS' and not value.depth and not (
                    previous and (previous.text.startswith('@') or previous.normalized == 'EXECUTE')):
                body_start = value.end
                body_tokens = [t for t in tokens[body_index + 1:] if t.start < end and t.text != ';']
                break
        body_observed = bool(body_tokens and _complete_blocks(body_tokens) and
            (len(body_tokens) > 1 or body_tokens[0].normalized not in {
                'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'EXEC', 'EXECUTE',
                'DECLARE', 'SET', 'IF', 'WHILE', 'WITH', 'PRINT', 'EXTERNAL', 'AS'}) and
            any(t.kind == 'word' and t.normalized not in {'BEGIN', 'END', 'TRY', 'CATCH'} for t in body_tokens))
        end_lines = source[:end].splitlines()
        while end_lines and not end_lines[-1].strip():
            end_lines.pop()
        result.append(ProcedureHeader('.'.join(names), source.count('\n', 0, token.start) + 1, fields, framed,
                                      tuple(part.casefold() for part in names), source.count('\n', 0, start) + 1, len(end_lines), body_observed, declaration, body_start))
    return result


def _returns_rows(tokens: list[_SqlToken]) -> bool:
    """Recognize an outer result SELECT, excluding input rows for writes and local assignments."""
    outer = [token for token in tokens if token.depth == 0 and token.kind not in {'line_comment', 'block_comment'}]
    insert_source = False
    for index, token in enumerate(outer):
        word = token.normalized
        if word == 'INSERT':
            insert_source = True
        elif word in {';', 'VALUES', 'EXEC', 'EXECUTE', 'DEFAULT'}:
            insert_source = False
        elif word == 'SELECT':
            feeds_insert = insert_source
            insert_source = False
            if feeds_insert or index and outer[index - 1].normalized in {'FOR', 'UNION', 'ALL', 'INTERSECT', 'EXCEPT'}:
                continue
            first = _next_code_token(tokens, token.index + 1, len(tokens))
            if first is None:
                continue
            if tokens[first].normalized in {'ALL', 'DISTINCT'}:
                first += 1
            first = _next_after_top_modifier(tokens, first, len(tokens))
            if first is None:
                continue
            operator = _next_code_token(tokens, first + 1, len(tokens))
            if tokens[first].text.startswith('@') and operator is not None and tokens[operator].text in {
                    '=', '+=', '-=', '*=', '/=', '%=', '&', '|', '^'}:
                if tokens[operator].text not in {'&', '|', '^'} or (operator + 1 < len(tokens) and tokens[operator + 1].text == '='):
                    continue
            for pos in range(index + 1, len(outer)):
                term = outer[pos].normalized
                if term == 'INTO':
                    break
                if term in {'FROM', ';', 'SELECT', 'RETURN', 'SET', 'INSERT', 'UPDATE', 'DELETE'}:
                    return True
            else:
                return True
    return False


def _writes_table(tokens: list[_SqlToken]) -> bool:
    for token in tokens:
        kind = token.normalized
        if token.depth or kind not in {'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'TRUNCATE'}:
            continue
        end = _dml_statement_end(tokens, token.index)
        pos = _next_after_top_modifier(tokens, token.index + 1, end)
        if pos is not None and tokens[pos].normalized in {'INTO', 'FROM', 'TABLE'}:
            pos = _next_code_token(tokens, pos + 1, end)
        if pos is None:
            continue
        name, _last = _identifier_path_at(tokens, pos, end)
        if kind in {'UPDATE', 'DELETE'} and name:
            sources = _parse_scope_declarations(tokens, 'sp_write', token.index, end, token.depth)
            name = next((s.source for s in sources if s.effective_alias == name), name)
        if name and not _base_source(name).strip('[]"').startswith(('@', '#')):
            return True
    return False


def procedure_responsibilities(source: str, *, start: int, end: int) -> set[str]:
    """Observe statement kinds in complete selected SPs, not business ownership.

    A SELECT-only example cannot demonstrate SAVE. Calls and dynamic bodies
    require their actual callee evidence instead of assuming a SAVE by name.
    """
    responsibilities = {'sql-format'}
    for header in procedure_headers(source):
        if not header.body_observed or not start <= header.unit_start <= header.unit_end <= end:
            continue
        body = ''.join(source.splitlines(keepends=True)[:header.unit_end])[header.body_start:]
        tokens, errors = _scan_sql_tokens(body)
        if errors:
            continue
        if _returns_rows(tokens):
            responsibilities.add('sql-select')
        if _writes_table(tokens):
            responsibilities.add('sql-save')
    return responsibilities


def creation_date_status(value: str) -> str:
    patterns = [(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', '%Y'),
                (r'\d{2}[-./]\d{1,2}[-./]\d{1,2}', '%y'),
                (r'\d{8}', '%Y%m%d'), (r'\d{6}', '%y%m%d')]
    for shape, pattern in patterns:
        if not re.fullmatch(shape, value):
            continue
        date = value
        if pattern in {'%Y', '%y'}:
            date = value.replace('/', '-').replace('.', '-')
            pattern += '-%m-%d'
        try:
            datetime.strptime(date, pattern)
            return 'valid'
        except ValueError:
            return 'invalid'
    return 'unverified'


def review_procedure_headers(candidate: str, original: str | None = None, *, author: str | None = None,
                             changed_only: bool = False) -> list[Issue]:
    prior = {header.parts: header for header in procedure_headers(original or '')}
    issues = []
    headers = procedure_headers(candidate)
    if not headers:
        return [Issue('procedure_definition_required', 'error',
            'This selected SP artifact has no supported CREATE/ALTER PROCEDURE definition to audit. A plain query or unsupported dynamic wrapper does not establish a complete SP/header; use the actual artifact responsibility.')]
    for header in headers:
        old = prior.get(header.parts)
        if changed_only and old and '\n'.join(candidate.splitlines()[header.unit_start - 1:header.unit_end]) == '\n'.join(
                (original or '').splitlines()[old.unit_start - 1:old.unit_end]):
            continue  # Unchanged adjacent procedures do not belong to this edit.
        fields = header.fields
        if 'REFERENCE AUTHOR' in fields and (not old or old.fields.get('REFERENCE AUTHOR') != fields['REFERENCE AUTHOR']):
            issues.append(Issue('procedure_reference_author_in_header', 'error',
                'Keep the comparison search names in the task context. Only the procedure author belongs in its attribution.',
                line=header.line, details={'procedure': header.name}))
        if not header.body_observed:
            issues.append(Issue('procedure_body_unverified', 'error',
                'A procedure name or AS token alone is not a complete SP body. Supply the full supported definition; this observation is not full T-SQL grammar validation.',
                line=header.line, details={'procedure': header.name}))
        missing = [key for key in ('AUTHOR', 'CREATE DATE', 'DESCRIPTION') if key not in fields]
        if not header.framed or missing:
            issues.append(Issue('procedure_header_required', 'error',
                'SP work requires a framed AUTHOR / CREATE DATE / DESCRIPTION header. Ask for the actual author and reference author; recover the first creation date instead of inventing it.',
                line=header.line, details={'procedure': header.name, 'missing': missing}))
        if 'CREATE DATE' in fields and (date_status := creation_date_status(fields['CREATE DATE'])) != 'valid':
            issues.append(Issue('procedure_creation_date_' + date_status, 'error' if date_status == 'invalid' else 'warning',
                'Use a real first-creation date in the project date style, not the current modification date or a placeholder.',
                line=header.line, details={'procedure': header.name}))
        if 'DESCRIPTION' in fields and (not re.fullmatch(r'.+\s*(?:처리|조회)', fields['DESCRIPTION']) or
                re.search(r'처리\s*OR\s*조회$', fields['DESCRIPTION'], re.I)):
            issues.append(Issue('procedure_description_required', 'error',
                'Describe the actual program followed by 처리 or 조회; the checker cannot determine the program title or business purpose.',
                line=header.line, details={'procedure': header.name}))
        possible_old = [record for parts, record in prior.items()
                        if parts[-1] == header.parts[-1] and (len(parts) == 1 or len(header.parts) == 1)] if old is None else []
        if old:
            for key in ('AUTHOR', 'CREATE DATE'):
                if key in old.fields and fields.get(key) != old.fields[key]:
                    issues.append(Issue('procedure_original_attribution_changed', 'warning',
                        'Preserve the original author and first-creation date when modifying an existing SP. An attribution correction requires explicit source-backed user direction.',
                        line=header.line, details={'procedure': header.name, 'field': key}))
        elif header.declaration != 'CREATE' or possible_old:
            issues.append(Issue('procedure_original_attribution_unverified', 'warning',
                'An ALTER/export or CREATE OR ALTER without an exact original definition does not establish a new SP. Verify the actual existing object, author and first date; schema qualification is not assumed and the current worker must not replace original attribution by default.',
                line=header.line, details={'procedure': header.name, 'declaration': header.declaration}))
        elif author and 'AUTHOR' in fields and author_key(fields['AUTHOR']) != author_key(author):
            issues.append(Issue('procedure_author_mismatch', 'error',
                'This new SP header does not name the user-selected author.',
                line=header.line, details={'procedure': header.name}))
    return issues
