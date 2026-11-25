"""Review repeated, unchanged scalar-mode guards inside an enclosing branch.

This is a narrow source review, not a T-SQL control-flow or business parser.
"""
from collections import Counter
from dataclasses import dataclass, field

from src.common.results import Issue
from .lexer import _SqlToken, _scan_sql_tokens


_Signature = tuple[str, str, tuple[tuple[str, str], ...]]
_NON_BLOCK_BEGIN = {'TRAN', 'TRANSACTION', 'DISTRIBUTED', 'DIALOG', 'CONVERSATION'}


@dataclass(frozen=True)
class _Guard:
    signature: _Signature
    offset: int
    transaction_phase: str = ''


@dataclass
class _Frame:
    kind: str
    guard: _Guard | None = None
    mutated: bool = False
    siblings: dict[_Signature, _Guard] = field(default_factory=dict)


def _guard(tokens: list[_SqlToken], index: int, *, allow_statement: bool = False) -> tuple[int, _Guard] | None:
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
    if cursor >= len(tokens):
        return None
    next_word = tokens[cursor].normalized
    if next_word != 'BEGIN' and not (allow_statement and next_word in {
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'EXEC', 'EXECUTE',
            'SET', 'RETURN', 'THROW', 'PRINT', 'WITH', 'IF'}):
        return None
    if next_word == 'BEGIN' and cursor + 1 < len(tokens) and tokens[cursor + 1].normalized in _NON_BLOCK_BEGIN:
        return None
    phase = ''
    if next_word == 'BEGIN' and cursor + 3 < len(tokens):
        action, unit = (part.normalized for part in tokens[cursor + 1:cursor + 3])
        if action in {'BEGIN', 'COMMIT', 'ROLLBACK'} and unit in {'TRAN', 'TRANSACTION'}:
            after = cursor + 3
            if tokens[after].text == ';':
                after += 1
            if after < len(tokens) and tokens[after].normalized == 'END':
                phase = action
    return cursor, _Guard((parameter.text, operator, tuple(values)), tokens[index].start, phase)


def _assignment(tokens: list[_SqlToken], index: int) -> bool:
    if index + 1 >= len(tokens):
        return False
    following = tokens[index + 1].text
    return (following in {'=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^='} or
            (following in {'+', '-', '*', '/', '%', '&', '|', '^'} and
             index + 2 < len(tokens) and tokens[index + 2].text == '='))


def _repetitions(source: str) -> list[tuple[_Signature, int, int, str]]:
    tokens = [token for token in _scan_sql_tokens(source)[0]
              if token.kind not in {'line_comment', 'block_comment'}]
    if any(token.kind == 'word' and token.normalized == 'GOTO' for token in tokens):
        return []  # A jump can enter a block without testing its lexical guard.
    frames: list[_Frame] = [_Frame('root')]
    pending: dict[int, _Guard] = {}
    projection: dict[int, bool] = {}
    found: list[tuple[_Signature, int, int, str]] = []

    def changed(parameter: str | None = None) -> None:
        for frame in frames:
            frame.siblings = {key: guard for key, guard in frame.siblings.items()
                              if parameter is not None and key[0].casefold() != parameter.casefold()}
            if frame.guard and (parameter is None or frame.guard.signature[0].casefold() == parameter.casefold()):
                frame.mutated = True

    for index, token in enumerate(tokens):
        if token.kind == 'batch_separator':
            frames = [_Frame('root')]
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
                    found.append((current.signature, current.offset, parent.offset, 'enclosing'))
                sibling = frames[-1].siblings.get(current.signature)
                if sibling and not (sibling.transaction_phase == 'BEGIN' and
                                    current.transaction_phase in {'COMMIT', 'ROLLBACK'}):
                    found.append((current.signature, current.offset, sibling.offset, 'sibling'))
            frames.append(_Frame('block', current))
            projection.clear()
        elif word == 'CASE':
            frames.append(_Frame('case'))
        elif word == 'END':
            if index + 1 < len(tokens) and tokens[index + 1].normalized == 'CONVERSATION':
                continue
            if len(frames) > 1:
                ended = frames.pop()
                if ended.kind == 'block':
                    projection.clear()
                    if ended.guard and not ended.mutated:
                        frames[-1].siblings[ended.guard.signature] = ended.guard
        elif word in {'EXEC', 'EXECUTE'}:
            if index + 2 < len(tokens) and tokens[index + 1].text.startswith('@') and tokens[index + 2].text == '=':
                changed(tokens[index + 1].text)  # Stored-procedure return status.
            for cursor in range(index + 1, len(tokens) - 1):
                argument = tokens[cursor]
                if argument.text == ';' or argument.kind == 'batch_separator' or argument.normalized in {'IF', 'BEGIN', 'END', 'SELECT', 'SET', 'EXEC', 'EXECUTE', 'RETURN'}:
                    break
                if argument.text.startswith('@') and tokens[cursor + 1].normalized in {'OUT', 'OUTPUT'}:
                    changed(argument.text)  # Actual argument, not the formal name.
            projection.clear()
        elif word in {'FETCH', 'RECEIVE', 'WHILE'}:
            changed()  # External assignment or loop re-entry is not evaluated.
            projection.clear()
        elif word in {'SET', 'DECLARE'}:
            if index + 1 < len(tokens) and tokens[index + 1].text.startswith('@'):
                changed(tokens[index + 1].text)
            projection.clear()
            # UPDATE SET lists may assign a variable after any column item.
            projection[token.depth] = word == 'SET'
        elif word == 'SELECT':
            projection[token.depth] = True
        elif word in {'FROM', 'WHERE', 'ON', 'GROUP', 'ORDER', 'HAVING', 'UNION', 'EXCEPT', 'INTERSECT'}:
            projection[token.depth] = False
        elif (token.text.startswith('@') and projection.get(token.depth, False) and
              not any(frame.kind == 'case' for frame in frames) and _assignment(tokens, index)):
            changed(token.text)
    return found


def review_dispatch(candidate: str, original: str | None = None) -> list[Issue]:
    previous = Counter((signature, kind) for signature, _, _, kind in _repetitions(original or ''))
    issues = []
    for signature, offset, outer_offset, kind in _repetitions(candidate):
        if previous[signature, kind]:
            previous[signature, kind] -= 1
            continue
        issues.append(Issue('repeated_' + kind + '_mode_guard', 'warning',
            'This scalar-mode predicate repeats an ' + ('enclosing branch condition' if kind == 'enclosing' else 'earlier sibling phase') + ' without an observed mode assignment. '
            'Review the operation boundary and ordered result sets; keep additional results in their owning branch. '
            'This does not ban other nested conditions or authorize an automatic rewrite.',
            line=candidate.count('\n', 0, offset) + 1,
            details={'parameter': signature[0], 'outer_line': candidate.count('\n', 0, outer_offset) + 1, 'relationship': kind}))
    return issues
