"""Resolve direct SP transports and local wrapper call sites within their C# method."""
from dataclasses import dataclass
import re

from .flow_review import _methods
from .lexer import balanced_close, mask_code, string_literal_value
from .syntax import parameter_constructor_sites


TRANSPORT = r'GetDataSetFromSP|SaveTrn|SaveNoTrn'
IDENT = r'[A-Za-z_]\w*'


def arguments(source: str, code: str, opening: int, closing: int) -> list[str]:
    """Split original expressions at commas outside strings and nested calls/initializers."""
    starts = [opening + 1]
    depth = 0
    for index in range(opening + 1, closing):
        char = code[index]
        if char in '([{':
            depth += 1
        elif char in ')]}':
            depth -= 1
        elif char == ',' and not depth:
            starts.append(index + 1)
    ends = [x - 1 for x in starts[1:]] + [closing]
    return [source[a:b].strip() for a, b in zip(starts, ends) if source[a:b].strip()]


@dataclass
class Method:
    name: str
    parameters: list[str]
    source: str
    code: str
    offset: int


@dataclass
class Call:
    method: Method
    start: int
    end: int
    name: str
    args: list[str]


def methods(source: str, code: str) -> list[Method]:
    found = []
    for match, start, end in _methods(code):
        params = [part.split('=')[0].strip().split()[-1] for part in match['parameters'].split(',') if part.strip()]
        found.append(Method(match['name'], params, source[start:end], code[start:end], start))
    return found


def calls_in(method: Method, names: str) -> list[Call]:
    found = []
    for m in re.finditer(r'\b(' + names + r')\s*\(', method.code):
        close = balanced_close(method.code, m.end() - 1)
        if close >= 0:
            found.append(Call(method, m.start(), close + 1, m[1],
                              arguments(method.source, method.code, m.end() - 1, close)))
    return found


def assignments(method: Method, variable: str, before: int) -> list[tuple[int, str]]:
    if not re.fullmatch(IDENT, variable):
        return []
    result = []
    for m in re.finditer(r'(?<![\w.])' + re.escape(variable) + r'\s*=(?!=|>)', method.code[:before]):
        end = method.code.find(';', m.end(), before)
        if end >= 0:
            result.append((m.start(), method.source[m.end():end].strip()))
    return result


def actual_parameters(call: Call) -> tuple[list[tuple[str, str]], list[str]]:
    records = []
    unknown = []
    def visit(expr: str, before: int) -> None:
        code = mask_code(expr)
        constructors = parameter_constructor_sites(expr)
        if constructors and constructors[0][2] == 0:
            _, name, _ = constructors[0]
            opening = code.find('(')
            closing = balanced_close(code, opening)
            if name and closing == len(expr) - 1:
                args = arguments(expr, code, opening, closing)
                records.append(('@' + name.lstrip('@').upper(), args[1] if len(args) > 1 else ''))
                return
        array = re.fullmatch(r'new\s*(?:(?:[\w.]+)\s*)?\[\s*\]\s*\{(.*)\}', code, re.S)
        if array:
            for item in arguments(expr, code, array.start(1) - 1, array.end(1)):
                visit(item, before)
            return
        earlier = assignments(call.method, expr, before)
        if len(earlier) == 1:
            offset, value = earlier[0]
            # Subscripts, mutated properties or passing the buffer to another helper
            # break the local declaration proof.
            semi = call.method.code.find(';', offset)
            if not re.search(r'\b' + re.escape(expr) + r'\b', call.method.code[semi + 1:before]):
                visit(value, offset)
                return
        unknown.append(expr)
    for expr in call.args[1:]:
        visit(expr, call.start)
    return records, unknown


def enum_members(code: str) -> dict[str, set[str]]:
    found = {}
    for m in re.finditer(r'\benum\s+(\w+)(?:\s*:\s*\w+)?\s*\{([^{}]*)\}', code):
        members = [v.strip() for v in m[2].split(',') if v.strip()]
        # Explicit values can alias another name when converted by ToString().
        if all(re.fullmatch(IDENT, member) for member in members):
            found[m[1]] = set(members)
    return found


def mode_values(expr: str, enum: dict[str, set[str]]) -> tuple[list[str], bool]:
    val = string_literal_value(expr.strip())
    if val is not None:
        return [val], False
    m = re.fullmatch(r'(\w+)\s*\.\s*(\w+)(?:\s*\.\s*ToString\s*\(\s*\))?', expr.strip())
    if m and m[2] in enum.get(m[1], set()):
        return [m[2]], False
    return [], True


def mode_evidence(call: Call, expr: str, sites: list[Call], enum: dict[str, set[str]]) -> tuple[dict[int, list[str]], set[str], bool]:
    direct, unresolved = mode_values(expr, enum)
    values = set(direct)
    site_values: dict[int, list[str]] = {}
    if not unresolved:
        return {s.method.offset + s.start: direct for s in sites}, values, False
    var = re.fullmatch(r'(\w+)(?:\s*\.\s*ToString\s*\(\s*\))?', expr)
    if not var:
        return site_values, values, True
    earlier = assignments(call.method, var[1], call.start)
    unknown = False
    for _, assignment in earlier:
        observed, dynamic = mode_values(assignment, enum)
        values.update(observed)
        unknown |= dynamic
    if var[1] not in call.method.parameters:
        return site_values, values, unknown or not earlier
    index = call.method.parameters.index(var[1])
    for site in sites:
        observed, dynamic = mode_values(site.args[index] if len(site.args) > index else '', enum)
        values.update(observed)
        unknown |= dynamic
        if not earlier:
            site_values[site.method.offset + site.start] = observed
    return site_values, values, unknown or not sites


def xml_names(call: Call, expr: str) -> tuple[set[str], list[str], bool]:
    """Trace assignments to the actual argument, serializer input and its preceding TableName."""
    sources = assignments(call.method, expr, call.start) if re.fullmatch(IDENT, expr) else [(call.start, expr)]
    names: set[str] = set()
    serializers: list[str] = []
    dynamic = False
    for offset, value in sources:
        if value == 'null':
            continue
        match = re.fullmatch(r'(?:[\w.]+\.)?TableToXml\s*\(\s*(\w+)(?:\s*\.\s*Clone\s*\(\s*\))?\s*(?:,.*)?\)', value, re.S)
        if not match:
            dynamic = True
            continue
        serializers.append(value)
        table = re.escape(match[1])
        literals = []
        for item in re.finditer(r'\b' + table + r'\s*\.\s*TableName\s*=\s*[^;]*;', call.method.code[:offset]):
            val = call.method.source[item.start():item.end()].split('=', 1)[1][:-1].strip()
            literals.append(string_literal_value(val))
        if literals and len(set(literals)) == 1 and literals[-1] is not None:
            names.add(literals[-1])
        else:
            dynamic = True
    return names, serializers, dynamic or not serializers
