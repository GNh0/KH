"""Shared C# method, parameter and explicit property observations."""

import re

from .lexer import _scan_csharp, mask_code, string_literal_value



def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1

def _method_declarations(text: str, name: str) -> list[re.Match[str]]:
    code = mask_code(text)
    modifiers = r"(?:public|private|protected|internal|static|async|virtual|override|sealed|new|unsafe|extern|partial|abstract)"
    return list(
        re.finditer(
            rf"(?m)(?:^|(?<=[;{{}}]))\s*(?:(?:{modifiers})\s+)*(?!(?:return|throw|new|if|while|for|switch)\b)[A-Za-z_][A-Za-z0-9_.,<>\[\]?]*\s+@?{re.escape(name)}\s*\(",
            code,
        )
    )

def parameter_constructor_sites(text: str) -> list[tuple[str, str | None, int]]:
    """Observe typed constructor sites; a dynamic name remains unresolved."""

    _, tokens = _scan_csharp(text)
    calls: list[tuple[str, str | None, int]] = []
    for index, token in enumerate(tokens):
        if token[0] != "identifier" or token[1] != "new":
            continue
        cursor = index + 1
        type_name = ""
        while cursor < len(tokens) and tokens[cursor][0] == "identifier":
            type_name = tokens[cursor][1]
            cursor += 1
            if cursor < len(tokens) and tokens[cursor][1] in {".", "::"}:
                cursor += 1
                continue
            break
        if type_name not in {"DbParameter", "SqlParameter"}:
            continue
        if cursor >= len(tokens) or tokens[cursor][1] != '(':
            continue
        name = None
        if cursor + 2 < len(tokens) and tokens[cursor + 1][0] == 'string' and tokens[cursor + 2][1] in {',', ')'}:
            literal = tokens[cursor + 1]
            name = string_literal_value(text[literal[2]:literal[3]])
        calls.append((type_name, name, token[2]))
    return calls


def linq_candidates(text: str) -> list[int]:
    """Review likely invocations, excluding declarations and known local calls.

    This is lexical evidence, not overload/extension-method resolution.
    """
    code = mask_code(text)
    names = {'AsEnumerable', 'ToLookup', 'GroupBy', 'Where', 'SelectMany', 'ToDictionary'}
    declarations = {name: _method_declarations(text, name) for name in names}
    offsets: list[int] = []
    for match in re.finditer(r'\b(?P<name>' + '|'.join(sorted(names)) + r')\s*\(', code):
        name = match['name']
        local = declarations[name]
        if any(item.start() <= match.start() < item.end() for item in local):
            continue
        receiver = re.search(r'([\w.]+)\s*(?:\.|\?\.)\s*$', code[:match.start()])
        if local and (receiver is None or receiver[1] in {'this', 'base'}):
            continue
        # AsEnumerable and collection operators are candidates only. A local
        # Where() is never sufficient evidence of LINQ by its spelling alone.
        if name == 'Where' and receiver is None:
            continue
        offsets.append(match.start())
    return offsets

def _property_assignments(text: str) -> dict:
    from .designer_model import parse_designer_source
    values = {}
    for item in parse_designer_source(text).assignments:
        values.setdefault(item['name'], {})[item['property']] = (item['value'], item['line'])
    return values
