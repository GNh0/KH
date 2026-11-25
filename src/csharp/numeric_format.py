"""Review literal N-format choices at recognizable C# formatting sites."""
from collections import Counter
import re

from src.common.results import Issue
from .lexer import _consume_csharp_literal, _scan_csharp, string_literal_value

_TOKEN = tuple[str, str, int, int]
_PROPERTIES = {'DisplayFormat', 'FormatString', 'EditMask'}
_SUMMARY_TYPES = {'GridColumnSummaryItem', 'GridGroupSummaryItem', 'GridSummaryItem'}
_STRING_FORMAT = {'string.Format', 'String.Format', 'System.String.Format', 'global::System.String.Format'}
_STANDARD = re.compile(r'[nN][0-9]*\Z')
_COMPOSITE = re.compile(r'\{[0-9]+\s*(?:,\s*-?[0-9]+\s*)?:(?P<format>[nN][0-9]*)\}')


def _specifiers(value: str, *, direct: bool) -> list[str]:
    if direct and _STANDARD.fullmatch(value):
        return [value]
    found: list[str] = []
    cursor = 0
    while cursor < len(value):
        if value.startswith('{{', cursor) or value.startswith('}}', cursor):
            cursor += 2
            continue
        match = _COMPOSITE.match(value, cursor)
        if match:
            found.append(match['format'])
            cursor = match.end()
        else:
            cursor += 1
    return found


def _member_before(tokens: list[_TOKEN], end: int) -> str:
    if end < 0 or tokens[end][0] != 'identifier':
        return ''
    parts = [tokens[end][1]]
    cursor = end - 1
    while cursor > 0 and tokens[cursor][1] in {'.', '?.', '::'} and tokens[cursor - 1][0] == 'identifier':
        parts[:0] = [tokens[cursor - 1][1], tokens[cursor][1]]
        cursor -= 2
    return ''.join(parts)


def _format_uses(source: str) -> list[tuple[str, str, int]]:
    _, tokens = _scan_csharp(source)
    uses: list[tuple[str, str, int]] = []
    # Closing token, callee, argument number, opening-token index.
    frames: list[tuple[str, str, int, int]] = []
    for index, (kind, value, start, end) in enumerate(tokens):
        if kind == 'interpolated_string':
            literal = _consume_csharp_literal(source, start)
            if literal is not None:
                for left, right in literal[2]:
                    expression = source[left:right]
                    code, _ = _scan_csharp(expression)
                    match = re.search(r'(?<!:):(?P<format>[nN][0-9]*)\Z', code)
                    if match:
                        context = 'interpolation:' + re.sub(r'\s+', '', code[:match.start()])
                        uses.append((context, match['format'], left + match.start()))
            continue
        if kind == 'string':
            decoded = string_literal_value(source[start:end])
            if decoded is None:
                continue
            # A fragment of a concatenation is not the resolved format string.
            if index + 1 >= len(tokens) or tokens[index + 1][1] not in {';', ',', ')', '}'}:
                continue
            context = ''
            direct = False
            if index >= 2 and tokens[index - 1][1] == '=' and tokens[index - 2][1] in _PROPERTIES:
                context = _member_before(tokens, index - 2)
                direct = True
            elif frames and frames[-1][0] == ')':
                _, member, argument, opening = frames[-1]
                leaf = member.split('.')[-1]
                if leaf == 'ToString' and argument == 0:
                    context, direct = member, True
                elif leaf in _SUMMARY_TYPES:
                    context = member
                elif member in _STRING_FORMAT:
                    provider = ''.join(token[1] for token in tokens[opening + 1:index])
                    known_provider = re.match(r'(?:new)?(?:System\.Globalization\.)?CultureInfo[.(]', provider)
                    if argument == 0 or (argument == 1 and known_provider):
                        context = member
            if context:
                uses.extend((context, specifier, start) for specifier in _specifiers(decoded, direct=direct))
            continue
        if value in {'(', '[', '{'}:
            frames.append(({'(': ')', '[': ']', '{': '}'}[value],
                           _member_before(tokens, index - 1) if value == '(' else '', 0, index))
        elif frames and value == frames[-1][0]:
            frames.pop()
        elif frames and value == ',' and frames[-1][0] == ')':
            closing, member, argument, opening = frames[-1]
            frames[-1] = (closing, member, argument + 1, opening)
    return uses


def check_numeric_formats(source: str, *, original: str | None = None) -> list[Issue]:
    """Warn on new literal format uses, without rewriting data or properties."""
    previous = Counter((context, value) for context, value, _ in _format_uses(original or ''))
    issues: list[Issue] = []
    for context, value, offset in _format_uses(source):
        key = context, value
        if previous[key]:
            previous[key] -= 1
            continue
        # A bounded suggestion avoids allocating a precision-sized string.
        digits = value[1:]
        precision = int(digits) if digits and len(digits) <= 2 else None
        preferred = '#,##0' + ('.' + '#' * precision if precision else '') if precision is not None and precision <= 8 else None
        issues.append(Issue('numeric_format_preference', 'warning',
            'Prefer an explicit custom numeric format. N0 normally uses #,##0; N2 normally uses #,##0.##. Check zero visibility, fixed decimal places, culture and rounding. This does not authorize adding DisplayFormat or EditMask.',
            line=source.count('\n', 0, offset) + 1,
            details={'context': context, 'format': value, 'custom_format_candidate': preferred}))
    return issues
