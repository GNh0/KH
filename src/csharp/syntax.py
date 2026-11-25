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


def static_ui_sites(text: str, known_members: set[str]) -> list[tuple[str, str, str, int, str, int]]:
    """Direct fixed-value setup only; conditional/event semantics stay manual."""
    from .source import _method_declaration_matches
    from .control_style import direct_statement_spans
    from .lexer import balanced_close
    code, _ = _scan_csharp(text)
    bodies = []
    for method in _method_declaration_matches(code):
        if method['body'] != '{':
            continue
        start = method.end() - 1
        end = balanced_close(code, start, '{', '}')
        if end >= 0:
            bodies.append((start + 1, end, method['name']))
    for name in re.findall(r'\bclass\s+(\w+)', code):
        for constructor in re.finditer(r'\b' + re.escape(name) + r'\s*\([^()]*\)\s*\{', code):
            end = balanced_close(code, constructor.end() - 1, '{', '}')
            if end >= 0:
                bodies.append((constructor.end(), end, name))
    if not bodies and not re.search(r'\b(?:class|struct|record)\b', code):
        bodies = [(0, len(text), '<snippet>')]
    sites = []
    for start, end, owner in bodies:
        for left, right in direct_statement_spans(text[start:end]):
            statement = text[start + left:start + right]
            match = re.fullmatch(r'\s*(?P<this>this\.)?(?P<member>\w+)\.(?P<property>[\w.]+)\s*=\s*(?P<value>.+?)\s*;\s*', statement, re.S)
            if not match or match['member'] not in known_members:
                continue
            value = match['value']
            literal = string_literal_value(value) is not None or value.strip() in {'true', 'false'}
            construction = re.fullmatch(r'new\s+(?:System\.Drawing\.)?(?:Font|Point|Size|Rectangle)\s*\((.*)\)', value, re.S)
            if construction:
                _, tokens = _scan_csharp(construction[1])
                literal = all(kind in {'number', 'string', 'symbol'} or
                              kind == 'identifier' and token in {'System', 'Drawing', 'FontStyle', 'GraphicsUnit', 'Regular', 'Bold', 'Italic', 'Underline', 'Point', 'Pixel', 'F', 'f', 'D', 'd', 'M', 'm', 'U', 'u', 'L', 'l'}
                              for kind, token, _, _ in tokens)
            if literal:
                sites.append((match['member'], match['property'], value,
                              text.count('\n', 0, start + left) + 1, owner, start + left))
    return sites
