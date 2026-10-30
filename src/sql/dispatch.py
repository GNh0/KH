"""Review repeated, unchanged scalar-mode guards inside an enclosing branch.

This is a narrow source review, not a T-SQL control-flow or business parser.
"""
from collections import Counter
from dataclasses import dataclass

from src.common.results import Issue
from .lexer import _SqlToken, _scan_sql_tokens


_Signature = tuple[str, str, tuple[tuple[str, str], ...]]
_NON_BLOCK_BEGIN = {'TRAN', 'TRANSACTION', 'DISTRIBUTED', 'DIALOG', 'CONVERSATION'}


@dataclass(frozen=True)
class _Guard:
    signature: _Signature
    offset: int


@dataclass
class _Frame:
    kind: str
    guard: _Guard | None = None
    mutated: bool = False


def _guard(tokens: list[_SqlToken], index: int) -> tuple[int, _Guard] | None:
    cursor = index + 1
    wrappers = 0
    while cursor < len(tokens) and tokens[cursor].text == '(':
        wrappers += 1
        cursor += 1
    if cursor + 2 >= len(tokens):
        return None
    parameter = tokens[cursor]
    if parameter.kind != 'word' or not parameter.text.startswith('@') or parameter.text.startswith('@@'):
        return None
    operator = tokens[cursor + 1].normalized
    cursor += 2
    values: list[tuple[str, str]] = []
    if operator == 'IN':
        if tokens[cursor].text != '(':
            return None
        cursor += 1
        while cursor < len(tokens):
            value = tokens[cursor]
            if value.kind not in {'string', 'unicode_string', 'number'}:
                return None
            values.append((value.kind, value.normalized))
            cursor += 1
            if cursor >= len(tokens):
                return None
            if tokens[cursor].text == ')':
                cursor += 1
                break
            if tokens[cursor].text != ',':
                return None
            cursor += 1
        else:
            return None
    elif operator == '=' and tokens[cursor].kind in {'string', 'unicode_string', 'number'}:
        values.append((tokens[cursor].kind, tokens[cursor].normalized))
        cursor += 1
    else:
        return None
    for _ in range(wrappers):
        if cursor >= len(tokens) or tokens[cursor].text != ')':
            return None
        cursor += 1
    if cursor >= len(tokens) or tokens[cursor].normalized != 'BEGIN':
        return None
    if cursor + 1 < len(tokens) and tokens[cursor + 1].normalized in _NON_BLOCK_BEGIN:
        return None
    return cursor, _Guard((parameter.text, operator, tuple(values)), tokens[index].start)


def _assignment(tokens: list[_SqlToken], index: int) -> bool:
    if index + 1 >= len(tokens):
        return False
    following = tokens[index + 1].text
    return (following in {'=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^='} or
            (following in {'+', '-', '*', '/', '%', '&', '|', '^'} and
             index + 2 < len(tokens) and tokens[index + 2].text == '='))


def _repetitions(source: str) -> list[tuple[_Signature, int, int]]:
    tokens = [token for token in _scan_sql_tokens(source)[0]
              if token.kind not in {'line_comment', 'block_comment'}]
    if any(token.kind == 'word' and token.normalized == 'GOTO' for token in tokens):
        return []  # A jump can enter a block without testing its lexical guard.
    frames: list[_Frame] = []
    pending: dict[int, _Guard] = {}
    projection: dict[int, bool] = {}
    found: list[tuple[_Signature, int, int]] = []

    def changed(parameter: str | None = None) -> None:
        for frame in frames:
            if frame.guard and (parameter is None or frame.guard.signature[0].casefold() == parameter.casefold()):
                frame.mutated = True

    for index, token in enumerate(tokens):
        if token.kind == 'batch_separator':
            frames.clear()
            pending.clear()
            projection.clear()
            continue
        if token.text == ';':
            projection.clear()
        if token.kind != 'word':
            continue
        word = token.normalized
        if word == 'IF':
            parsed = _guard(tokens, index)
            if parsed:
                pending[parsed[0]] = parsed[1]
            projection.clear()
        elif word == 'BEGIN':
            if index + 1 < len(tokens) and tokens[index + 1].normalized in _NON_BLOCK_BEGIN:
                continue
            current = pending.pop(index, None)
            if current:
                parent = next((frame.guard for frame in reversed(frames)
                               if frame.guard and not frame.mutated and
                               frame.guard.signature == current.signature), None)
                if parent:
                    found.append((current.signature, current.offset, parent.offset))
            frames.append(_Frame('block', current))
            projection.clear()
        elif word == 'CASE':
            frames.append(_Frame('case'))
        elif word == 'END':
            if index + 1 < len(tokens) and tokens[index + 1].normalized == 'CONVERSATION':
                continue
            if frames:
                ended = frames.pop()
                if ended.kind == 'block':
                    projection.clear()
        elif word in {'EXEC', 'EXECUTE', 'FETCH', 'RECEIVE', 'WHILE'}:
            changed()  # External assignment or loop re-entry is not evaluated.
            projection.clear()
        elif word in {'SET', 'DECLARE'}:
            if index + 1 < len(tokens) and tokens[index + 1].text.startswith('@'):
                changed(tokens[index + 1].text)
            projection.clear()
        elif word == 'SELECT':
            projection[token.depth] = True
        elif word in {'FROM', 'WHERE', 'ON', 'GROUP', 'ORDER', 'HAVING', 'UNION', 'EXCEPT', 'INTERSECT'}:
            projection[token.depth] = False
        elif (token.text.startswith('@') and projection.get(token.depth, False) and
              not any(frame.kind == 'case' for frame in frames) and _assignment(tokens, index)):
            changed(token.text)
    return found


def review_dispatch(candidate: str, original: str | None = None) -> list[Issue]:
    previous = Counter(signature for signature, _, _ in _repetitions(original or ''))
    issues = []
    for signature, offset, outer_offset in _repetitions(candidate):
        if previous[signature]:
            previous[signature] -= 1
            continue
        issues.append(Issue('repeated_enclosing_mode_guard', 'warning',
            'This scalar-mode predicate repeats an enclosing branch condition without an observed mode assignment. '
            'Review the operation boundary and ordered result sets; keep additional results in their owning branch. '
            'This does not ban other nested conditions or authorize an automatic rewrite.',
            line=candidate.count('\n', 0, offset) + 1,
            details={'parameter': signature[0], 'outer_line': candidate.count('\n', 0, outer_offset) + 1}))
    return issues
