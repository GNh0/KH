"""Shared C# method, parameter and explicit property observations."""

import re

from .lexer import _scan_csharp, _strip_comments



def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1

def _method_declarations(text: str, name: str) -> list[re.Match[str]]:
    code = _strip_comments(text)
    modifiers = r"(?:public|private|protected|internal|static|async|virtual|override|sealed|new|unsafe|extern|partial|abstract)"
    return list(
        re.finditer(
            rf"(?m)(?:^|(?<=[;{{}}]))\s*(?:(?:{modifiers})\s+)*(?!(?:return|throw|new|if|while|for|switch)\b)[A-Za-z_][A-Za-z0-9_.,<>\[\]?]*\s+@?{re.escape(name)}\s*\(",
            code,
        )
    )

def _parameter_constructor_calls(text: str) -> list[tuple[str, str, int]]:
    """Return real DbParameter/SqlParameter constructor call sites."""

    _, tokens = _scan_csharp(text)
    calls: list[tuple[str, str, int]] = []
    for index, token in enumerate(tokens):
        if token[0] != "identifier" or token[1] != "new":
            continue
        cursor = index + 1
        type_name = ""
        while cursor < len(tokens) and tokens[cursor][0] == "identifier":
            type_name = tokens[cursor][1]
            cursor += 1
            if cursor < len(tokens) and tokens[cursor][1] == ".":
                cursor += 1
                continue
            break
        if type_name not in {"DbParameter", "SqlParameter"}:
            continue
        if cursor + 1 >= len(tokens) or tokens[cursor][1] != "(" or tokens[cursor + 1][0] != "string":
            continue
        calls.append((type_name, tokens[cursor + 1][1], token[2]))
    return calls

def _property_assignments(text: str) -> dict:
    from .designer_model import parse_designer_source
    values = {}
    for item in parse_designer_source(text).assignments:
        values.setdefault(item['name'], {})[item['property']] = (item['value'], item['line'])
    return values
