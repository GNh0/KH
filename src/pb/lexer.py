"""PowerScript comment and quoted-value boundaries for textual export inspection."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class PBLiteral:
    start: int
    end: int
    value: str
    complete: bool


def scan_pb(text: str, *, mask_literals: bool = True) -> tuple[str, list[PBLiteral]]:
    chars = list(text)
    literals: list[PBLiteral] = []
    index = 0
    escapes = {'n': '\n', 'r': '\r', 't': '\t', 'v': '\v', 'f': '\f',
               'b': '\b', '"': '"', "'": "'", '~': '~'}
    while index < len(text):
        start = index
        if text[index] in {'"', "'"}:
            quote = text[index]
            index += 1
            parts: list[str] = []
            valid, closed = True, False
            while index < len(text):
                char = text[index]
                if char == quote:
                    index += 1
                    closed = True
                    break
                if char == '~' and index + 1 < len(text):
                    escape = text[index + 1]
                    if escape in escapes:
                        parts.append(escapes[escape])
                        index += 2
                        continue
                    numeric = re.match(r'~(?:h([0-9a-fA-F]{2})|o([0-7]{3})|([0-9]{3}))', text[index:])
                    if numeric:
                        digits, base = next((s, b) for s, b in zip(numeric.groups(), (16, 8, 10)) if s is not None)
                        number = int(digits, base)
                        if number <= 255:
                            parts.append(chr(number))
                            index += len(numeric[0])
                            continue
                    valid = False
                parts.append(char)
                index += 1
            literals.append(PBLiteral(start, index, ''.join(parts), valid and closed))
            if not mask_literals:
                continue
        elif text.startswith('//', index):
            end = text.find('\n', index)
            index = len(text) if end < 0 else end
        elif text.startswith('/*', index):
            end = text.find('*/', index + 2)
            index = len(text) if end < 0 else end + 2
        else:
            index += 1
            continue
        for cursor in range(start, index):
            if chars[cursor] not in '\r\n':
                chars[cursor] = ' '
    return ''.join(chars), literals
