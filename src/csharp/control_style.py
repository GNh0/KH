"""Lexical review of new unbraced control bodies, without rewriting source.

This recognizes local statement boundaries, not C# semantics or active
preprocessor branches. Incomplete/unrecognized bodies are left unresolved.
"""
from collections import Counter
from dataclasses import dataclass
import re

from src.common.results import Issue
from .lexer import _scan_csharp


_CONDITIONAL = {'if', 'for', 'foreach', 'while'}
_PAREN_BODY = _CONDITIONAL | {'switch', 'using', 'lock', 'fixed'}


@dataclass(frozen=True)
class _Body:
    keyword: str
    line: int
    fingerprint: tuple[tuple[str, str], ...]


class _Statements:
    def __init__(self, source: str):
        self.source = source
        code, tokens = _scan_csharp(source)
        directives = [match.span() for match in re.finditer(r'(?m)^[ \t]*#[^\r\n]*', code)]
        self.tokens = [token for token in tokens
                       if not any(start <= token[2] < end for start, end in directives)]
        self.pairs: dict[int, int] = {}
        stack: list[tuple[str, int]] = []
        closes = {')': '(', ']': '[', '}': '{'}
        for index, (kind, value, _, _) in enumerate(self.tokens):
            if kind != 'symbol':
                continue
            if value in {'(', '[', '{'}:
                stack.append((value, index))
            elif value in closes:
                if stack and stack[-1][0] == closes[value]:
                    _, opening = stack.pop()
                    self.pairs[opening] = index
                else:
                    stack.clear()

    def symbol(self, index: int, value: str) -> bool:
        return 0 <= index < len(self.tokens) and self.tokens[index][:2] == ('symbol', value)

    def keyword(self, index: int) -> str:
        if not 0 <= index < len(self.tokens) or self.tokens[index][0] != 'identifier':
            return ''
        if index and self.tokens[index - 1][:2] in {
            ('symbol', '@'), ('symbol', '.'), ('symbol', '?.'), ('symbol', '::')
        }:
            return ''
        return self.tokens[index][1]

    def after_condition(self, index: int) -> int | None:
        closing = self.pairs.get(index + 1) if self.symbol(index + 1, '(') else None
        return closing + 1 if closing is not None else None

    def end(self, start: int, depth: int = 0) -> int | None:
        """Return the first token after one complete supported statement."""
        if start >= len(self.tokens) or depth >= 128:
            return None
        if self.symbol(start, '{'):
            closing = self.pairs.get(start)
            return closing + 1 if closing is not None else None
        keyword = self.keyword(start)
        if keyword == 'await' and self.keyword(start + 1) in {'foreach', 'using'}:
            return self.end(start + 1, depth + 1)
        if keyword in _PAREN_BODY:
            body = self.after_condition(start)
            end = self.end(body, depth + 1) if body is not None else None
            if keyword == 'if' and end is not None and self.keyword(end) == 'else':
                end = self.end(end + 1, depth + 1)
            return end
        if keyword == 'do':
            tail = self.end(start + 1, depth + 1)
            end = self.after_condition(tail) if tail is not None and self.keyword(tail) == 'while' else None
            return end + 1 if end is not None and self.symbol(end, ';') else None
        if keyword in {'checked', 'unchecked', 'unsafe'} and self.symbol(start + 1, '{'):
            return self.end(start + 1, depth + 1)
        if keyword == 'try':
            end = self.end(start + 1, depth + 1)
            while end is not None and self.keyword(end) in {'catch', 'finally'}:
                body = self.after_condition(end) if self.symbol(end + 1, '(') else end + 1
                if body is not None and self.keyword(body) == 'when':
                    body = self.after_condition(body)
                end = self.end(body, depth + 1) if body is not None else None
            return end
        index = start
        while index < len(self.tokens):
            if self.symbol(index, ';'):
                return index + 1
            if any(self.symbol(index, close) for close in (')', ']', '}')):
                return None
            if any(self.symbol(index, opening) for opening in ('(', '[', '{')):
                closing = self.pairs.get(index)
                if closing is None:
                    return None
                index = closing + 1
            else:
                index += 1
        return None

    def unbraced(self) -> list[_Body]:
        tails: set[int] = set()
        for index in range(len(self.tokens)):
            if self.keyword(index) == 'do':
                end = self.end(index + 1)
                if end is not None and self.keyword(end) == 'while':
                    tails.add(end)
        found: list[_Body] = []
        for index, (_, _, start, _) in enumerate(self.tokens):
            keyword = self.keyword(index)
            if keyword not in _CONDITIONAL | {'else', 'do'} or index in tails:
                continue
            body = self.after_condition(index) if keyword in _CONDITIONAL else index + 1
            if body is None or self.symbol(body, '{') or (keyword == 'else' and self.keyword(body) == 'if'):
                continue
            end = self.end(body)
            if end is None:
                continue
            fingerprint = tuple((kind, self.source[left:right])
                                for kind, _, left, right in self.tokens[index:end])
            found.append(_Body(keyword, self.source.count('\n', 0, start) + 1, fingerprint))
        return found


def check_control_braces(candidate: str, *, original: str | None = None) -> list[Issue]:
    previous = Counter(body.fingerprint for body in _Statements(original or '').unbraced())
    issues: list[Issue] = []
    for body in _Statements(candidate).unbraced():
        if previous[body.fingerprint]:
            previous[body.fingerprint] -= 1
            continue
        issues.append(Issue('control_body_braces', 'warning',
                            'Use braces for this control body, including a single return or assignment. Unbraced reference examples do not override the agreed style.',
                            line=body.line, details={'keyword': body.keyword}))
    return issues


def direct_statement_spans(source: str) -> list[tuple[int, int]]:
    """Complete outer statements only; nested conditional writes stay nested."""
    statements = _Statements(source)
    found: list[tuple[int, int]] = []
    index = 0
    while index < len(statements.tokens):
        end = statements.end(index)
        if end is None or end <= index:
            break
        found.append((statements.tokens[index][2], statements.tokens[end - 1][3]))
        index = end
    return found
