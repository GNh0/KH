"""Retained csharp syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

import re




def _mask_range(chars: list[str], text: str, start: int, end: int) -> None:
    for index in range(start, min(end, len(chars))):
        if text[index] not in "\r\n":
            chars[index] = " "


def _find_interpolation_close(
    text: str,
    start: int,
    limit: int,
    *,
    brace_count: int,
) -> int:
    """Find the first balanced interpolation close outside nested literals."""

    opening = "{" * brace_count
    closing = "}" * brace_count
    depth = 1
    index = start
    while index < limit:
        if text.startswith("//", index):
            newline = text.find("\n", index + 2, limit)
            index = limit if newline < 0 else newline + 1
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2, limit)
            index = limit if end < 0 else end + 2
            continue
        nested = _consume_csharp_literal(text, index)
        if nested is not None:
            index = nested[0]
            continue
        if text.startswith(opening, index):
            depth += 1
            index += brace_count
            continue
        if text.startswith(closing, index):
            depth -= 1
            if depth == 0:
                return index
            index += brace_count
            continue
        index += 1
    return limit


def _consume_csharp_literal(
    text: str,
    start: int,
) -> tuple[int, str, list[tuple[int, int]], bool] | None:
    """Return literal end/value and executable interpolation expression ranges."""

    length = len(text)
    index = start
    dollar_count = 0
    verbatim = False
    while index < length and text[index] in {"$", "@"}:
        if text[index] == "$":
            dollar_count += 1
        else:
            if verbatim:
                return None
            verbatim = True
        index += 1
    if index >= length or text[index] not in {'"', "'"}:
        return None
    quote = text[index]
    if quote == "'" and (dollar_count or verbatim):
        return None
    quote_start = index
    quote_count = 1
    while quote == '"' and index + quote_count < length and text[index + quote_count] == quote:
        quote_count += 1
    raw = quote == '"' and quote_count >= 3
    content_start = quote_start + (quote_count if raw else 1)
    delimiter = quote * (quote_count if raw else 1)
    index = content_start
    expressions: list[tuple[int, int]] = []
    literal_parts: list[str] = []
    literal_start = content_start
    brace_count = max(1, dollar_count) if raw else 1
    while index < length:
        if raw and text.startswith(delimiter, index):
            literal_parts.append(text[literal_start:index])
            return index + len(delimiter), "".join(literal_parts), expressions, bool(dollar_count)
        if not raw and verbatim and quote == '"' and text[index] == '"':
            if index + 1 < length and text[index + 1] == '"':
                index += 2
                continue
            literal_parts.append(text[literal_start:index])
            return index + 1, "".join(literal_parts), expressions, bool(dollar_count)
        if not raw and not verbatim and text[index] == "\\":
            index = min(index + 2, length)
            continue
        if not raw and not verbatim and text[index] == quote:
            literal_parts.append(text[literal_start:index])
            return index + 1, "".join(literal_parts), expressions, bool(dollar_count)
        opening = "{" * brace_count
        if dollar_count and text.startswith(opening, index):
            if not raw and text.startswith("{{", index):
                index += 2
                continue
            expression_start = index + brace_count
            expression_end = _find_interpolation_close(
                text,
                expression_start,
                length,
                brace_count=brace_count,
            )
            literal_parts.append(text[literal_start:index])
            expressions.append((expression_start, expression_end))
            index = min(length, expression_end + brace_count)
            literal_start = index
            continue
        if not raw and dollar_count and text.startswith("}}", index):
            index += 2
            continue
        index += 1
    literal_parts.append(text[literal_start:])
    return length, "".join(literal_parts), expressions, bool(dollar_count)


def _scan_csharp(text: str) -> tuple[str, list[tuple[str, str, int, int]]]:
    """Lex comments and literals without allowing their contents to act as code."""

    chars = list(text)
    tokens: list[tuple[str, str, int, int]] = []
    index = 0
    length = len(text)
    while index < length:
        if text.startswith("//", index):
            end = index + 2
            while end < length and text[end] not in "\r\n":
                end += 1
            _mask_range(chars, text, index, end)
            index = end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = length if end < 0 else end + 2
            _mask_range(chars, text, index, end)
            index = end
            continue
        literal = _consume_csharp_literal(text, index)
        if literal is not None:
            end, value, expressions, interpolated = literal
            tokens.append(("interpolated_string" if interpolated else "string", value, index, end))
            _mask_range(chars, text, index, end)
            for expression_start, expression_end in expressions:
                nested_code, nested_tokens = _scan_csharp(text[expression_start:expression_end])
                chars[expression_start:expression_end] = list(nested_code)
                tokens.extend(
                    (kind, value, start + expression_start, finish + expression_start)
                    for kind, value, start, finish in nested_tokens
                )
            index = end
            continue
        if text[index].isalpha() or text[index] == "_":
            end = index + 1
            while end < length and (text[end].isalnum() or text[end] == "_"):
                end += 1
            tokens.append(("identifier", text[index:end], index, end))
            index = end
            continue
        if not text[index].isspace():
            operators = ('??=', '<<=', '>>=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=',
                         '=>', '?.', '??', '==', '!=', '<=', '>=', '::', '++', '--', '&&', '||', '<<', '>>')
            operator = next((candidate for candidate in operators if text.startswith(candidate, index)), text[index])
            tokens.append(("symbol", operator, index, index + len(operator)))
            index += len(operator)
            continue
        index += 1
    tokens.sort(key=lambda item: (item[2], item[3]))
    return "".join(chars), tokens


def mask_comments(text: str) -> str:
    """Use the same literal boundaries while retaining values for Designer parsing."""
    code, tokens = _scan_csharp(text)
    chars = list(code)
    for kind, _, start, end in tokens:
        if kind in {"string", "interpolated_string"}:
            chars[start:end] = text[start:end]
    return ''.join(chars)


def string_literal_value(source: str) -> str | None:
    """Decode one constant string; expressions, interpolation and invalid escapes stay unresolved."""
    text = source.strip()
    if text.startswith('@"'):
        if not re.fullmatch(r'@"(?:""|[^"])*"', text):
            return None
        value = text[2:-1].replace('""', '"')
    elif text.startswith('"""'):
        count = len(text) - len(text.lstrip('"'))
        delimiter = '"' * count
        if len(text) < count * 2 or not text.endswith(delimiter):
            return None
        body = text[count:-count]
        if delimiter in body:
            return None
        if '\n' not in body and '\r' not in body:
            value = body
        else:
            opening = re.match(r'[^\S\r\n]*(?:\r\n|\n|\r)', body)
            closing = re.search(r'(?:\r\n|\n|\r)([^\S\r\n]*)$', body)
            if opening is None or closing is None or opening.end() > closing.start():
                return None
            indent = closing[1]
            lines = body[opening.end():closing.start()].splitlines(keepends=True)
            stripped: list[str] = []
            for line in lines:
                if line.startswith(indent):
                    stripped.append(line[len(indent):])
                elif not line.strip() and indent.startswith(line.rstrip('\r\n')):
                    stripped.append(line[len(line.rstrip('\r\n')):])
                else:
                    return None
            value = ''.join(stripped)
    else:
        if not re.fullmatch(r'"(?:[^"\\\r\n]|\\.)*"', text):
            return None
        body = text[1:-1]
        escapes = {'0': '\0', 'a': '\a', 'b': '\b', 'f': '\f', 'n': '\n',
                   'r': '\r', 't': '\t', 'v': '\v', '\\': '\\', '"': '"', "'": "'"}
        pieces: list[str] = []
        index = 0
        while index < len(body):
            if body[index] != '\\':
                pieces.append(body[index])
                index += 1
                continue
            token = body[index + 1]
            if token in escapes:
                pieces.append(escapes[token])
                index += 2
                continue
            pattern = {'u': r'[0-9a-fA-F]{4}', 'U': r'[0-9a-fA-F]{8}', 'x': r'[0-9a-fA-F]{1,4}'}.get(token)
            match = re.match(pattern, body[index + 2:]) if pattern else None
            if match is None or int(match[0], 16) > 0x10FFFF:
                return None
            pieces.append(chr(int(match[0], 16)))
            index += 2 + len(match[0])
        value = ''.join(pieces)
    # .NET strings use UTF-16: a surrogate pair and its scalar spelling are equal.
    return value.encode('utf-16-le', errors='surrogatepass').decode('utf-16-le', errors='surrogatepass')


def mask_code(text: str) -> str:
    return _scan_csharp(text)[0]


def balanced_close(code: str, opening: int, open_char: str = "(", close_char: str = ")") -> int:
    depth = 0
    for index in range(opening, len(code)):
        if code[index] == open_char:
            depth += 1
        elif code[index] == close_char:
            depth -= 1
            if depth == 0:
                return index
    return -1
