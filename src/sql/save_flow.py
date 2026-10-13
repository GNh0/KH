"""Review XML re-encoding inside loops before static procedure dispatch."""
from collections import Counter
from dataclasses import dataclass

from src.common.results import Issue
from .lexer import _SqlToken, _scan_sql_tokens


_STATEMENTS = frozenset({
    'BEGIN', 'END', 'IF', 'ELSE', 'SELECT', 'SET', 'INSERT', 'UPDATE', 'DELETE',
    'EXEC', 'EXECUTE', 'FETCH', 'OPEN', 'CLOSE', 'DEALLOCATE', 'DECLARE', 'WHILE',
    'PRINT', 'RETURN', 'THROW', 'RAISERROR', 'BREAK', 'CONTINUE', 'WAITFOR',
})
_XML_HELPERS = frozenset({
    'SP_XML_LOG_SAVE', 'SP_XML_PREPAREDOCUMENT', 'SP_XML_REMOVEDOCUMENT',
    'SP_EXECUTESQL',
})


@dataclass(frozen=True)
class _Dispatch:
    identity: str
    offset: int
    callee: str
    variables: tuple[str, ...]
    loop_kind: str


def _block_ends(tokens: list[_SqlToken]) -> dict[int, int]:
    stack: list[int] = []
    ends: dict[int, int] = {}
    for index, token in enumerate(tokens):
        if token.kind == 'batch_separator':
            stack.clear()
        elif token.kind == 'word' and token.normalized == 'CASE':
            stack.append(index)
        elif token.kind == 'word' and token.normalized == 'BEGIN':
            following = tokens[index + 1].normalized if index + 1 < len(tokens) else ''
            if following not in {'TRAN', 'TRANSACTION', 'DISTRIBUTED', 'DIALOG', 'CONVERSATION'}:
                stack.append(index)
        elif token.kind == 'word' and token.normalized == 'END':
            following = tokens[index + 1].normalized if index + 1 < len(tokens) else ''
            if following != 'CONVERSATION' and stack:
                ends[stack.pop()] = index
    return ends


def _while_blocks(tokens: list[_SqlToken]) -> list[tuple[int, int, int]]:
    ends = _block_ends(tokens)
    blocks = []
    for index, token in enumerate(tokens):
        if token.kind != 'word' or token.normalized != 'WHILE':
            continue
        for cursor in range(index + 1, len(tokens)):
            current = tokens[cursor]
            if current.kind == 'batch_separator' or (current.text == ';' and current.depth <= token.depth):
                break
            if current.depth != token.depth or current.kind != 'word':
                continue
            if current.normalized == 'BEGIN':
                if cursor in ends:
                    blocks.append((index, cursor, ends[cursor]))
                break
            if current.normalized in _STATEMENTS:
                break
    return blocks


def _statement_end(tokens: list[_SqlToken], start: int, limit: int, depth: int) -> int:
    for index in range(start, limit):
        token = tokens[index]
        if token.kind == 'batch_separator' or (token.text == ';' and token.depth <= depth):
            return index
        if token.kind == 'word' and token.depth <= depth and token.normalized in _STATEMENTS:
            return index
    return limit


def _xml_variables(tokens: list[_SqlToken], start: int, limit: int) -> set[str]:
    variables: set[str] = set()
    for index in range(start, limit - 2):
        token, variable = tokens[index:index + 2]
        if (token.kind != 'word' or token.normalized not in {'SELECT', 'SET'}
                or variable.kind != 'word' or not variable.text.startswith('@')
                or variable.text.startswith('@@') or tokens[index + 2].text != '='):
            continue
        end = _statement_end(tokens, index + 3, limit, token.depth)
        encoded = any(tokens[part].kind == 'word' and tokens[part].normalized == 'FOR'
                      and tokens[part + 1].kind == 'word' and tokens[part + 1].normalized == 'XML'
                      for part in range(index + 3, end - 1))
        if encoded:
            variables.add(variable.normalized)
        else:
            variables.discard(variable.normalized)
    return variables


def _dispatches(source: str) -> list[_Dispatch]:
    tokens = [token for token in _scan_sql_tokens(source)[0]
              if token.kind not in {'line_comment', 'block_comment'}]
    loops = _while_blocks(tokens)
    found = []
    for index, token in enumerate(tokens):
        if token.kind != 'word' or token.normalized not in {'EXEC', 'EXECUTE'}:
            continue
        containing = [loop for loop in loops if loop[1] < index < loop[2]]
        if not containing:
            continue
        first, begin, end = min(containing, key=lambda loop: loop[2] - loop[1])
        batch_start = max((part + 1 for part in range(first)
                           if tokens[part].kind == 'batch_separator'), default=0)
        if not any(part.kind == 'word' and part.normalized == 'OPENXML'
                   for part in tokens[batch_start:first]):
            continue
        cursor = index + 1
        if (cursor + 1 < end and tokens[cursor].text.startswith('@')
                and tokens[cursor + 1].text == '='):
            cursor += 2
        parts: list[_SqlToken] = []
        while cursor < end:
            part = tokens[cursor]
            if part.kind not in {'word', 'bracket_identifier', 'quoted_identifier'} or part.text.startswith('@'):
                break
            parts.append(part)
            cursor += 1
            if cursor >= end or tokens[cursor].text != '.':
                break
            while cursor < end and tokens[cursor].text == '.':
                cursor += 1
        if not parts:
            continue  # Dynamic EXEC is not a resolved callee.
        basename = parts[-1].normalized.strip('[]"')
        if basename in _XML_HELPERS:
            continue
        variables = _xml_variables(tokens, begin + 1, index)
        arguments_end = _statement_end(tokens, cursor, end, token.depth)
        passed = sorted({part.normalized for position, part in enumerate(tokens[cursor:arguments_end], cursor)
                         if part.normalized in variables
                         and (position + 1 >= arguments_end or tokens[position + 1].text != '=')})
        if not passed:
            continue
        callee = '.'.join(part.text for part in parts)
        identity = repr([part.normalized for part in tokens[first:end + 1]]) + ':' + str(index - first)
        loop_kind = 'cursor' if any(part.normalized == '@@FETCH_STATUS' for part in tokens[first:begin]) else 'while'
        found.append(_Dispatch(identity, token.start, callee, tuple(passed), loop_kind))
    return found


def review_xml_dispatch(candidate: str, original: str | None = None) -> list[Issue]:
    previous = Counter(item.identity for item in _dispatches(original or ''))
    issues = []
    for item in _dispatches(candidate):
        if previous[item.identity]:
            previous[item.identity] -= 1
            continue
        issues.append(Issue('xml_reencode_dispatch_review', 'warning',
            'XML is parsed, re-encoded inside a loop, then passed to another procedure. Compare the batch/direct DML path and the callee input cardinality, keys, side effects, validation and transaction/error ownership. Retain this dispatch only for a verified need or approved project contract; loops, XML and EXEC are not individually prohibited.',
            line=candidate.count('\n', 0, item.offset) + 1,
            details={'callee': item.callee, 'xml_variables': list(item.variables), 'loop_kind': item.loop_kind}))
    return issues
