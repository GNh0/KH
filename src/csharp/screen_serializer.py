"""Observe a supplied DataTableToXml implementation's document root and row naming."""
from dataclasses import dataclass
import re

from .lexer import mask_code, mask_comments, string_literal_value
from .screen_calls import IDENT, Method, arguments, calls_in, methods


@dataclass(frozen=True)
class Shape:
    root: str
    fixed_row: str | None  # None denotes the nonempty input DataTable.TableName.
    root_line: int
    row_line: int


def _shape(method: Method, text: str) -> Shape | None:
    elements = calls_in(method, 'CreateElement')
    if len(elements) != 2 or not method.parameters:
        return None
    writes = []
    for element in elements:
        match = re.search(r'(\w+)\s*=\s*(\w+)\s*\.\s*$', method.code[:element.start])
        if not match or len(element.args) != 1:
            return None
        writes.append((match[1], match[2], element.args[0], element.start))
    root, doc, literal_root, root_pos = writes[0]
    row, doc2, row_expr, row_pos = writes[1]
    root_name = string_literal_value(literal_root)
    if doc != doc2 or not root_name:
        return None
    # Keep the XML object, root, row and actual returned writer connected.
    connections = [(doc, root, root_pos, row_pos), (root, row, row_pos, len(method.code))]
    for owner, child, a, b in connections:
        if not re.search(r'\b' + owner + r'\s*\.\s*AppendChild\s*\(\s*' + child + r'\s*\)', method.code[a:b]):
            return None
    returned = re.findall(r'\breturn\s+([^;]+);', method.code)
    if len(returned) != 1:
        return None
    if not re.fullmatch(doc + r'\s*\.\s*(?:OuterXml|InnerXml)', returned[0].strip()):
        writer = re.search(r'\b(\w+)\s*=\s*(?:[\w.]+\.)?XmlWriter\.Create\s*\(\s*(\w+)\s*[,)]', method.code)
        if not writer or not re.search(r'\b' + doc + r'\.WriteTo\(\s*' + writer[1] + r'\s*\)', method.code[writer.end():]):
            return None
        if not re.fullmatch(writer[2] + r'\s*\.\s*ToString\s*\(\s*\)', returned[0].strip()):
            return None
    field = method.parameters[0] + r'\s*\.\s*TableName'
    fixed = string_literal_value(row_expr)
    if fixed is None and not re.fullmatch(field, row_expr):
        # The empty-name fallback does not change a nonempty literal TableName.
        if not re.fullmatch(r'(?:string|String)\.IsNullOrEmpty\(\s*' + field +
                r'\s*\)\s*\?\s*"[^"\\]*"\s*:\s*' + field, row_expr):
            return None
    return Shape(root_name, fixed, text.count('\n', 0, method.offset + root_pos) + 1,
                 text.count('\n', 0, method.offset + row_pos) + 1)


def serializer_shapes(text: str) -> dict[tuple[str, int], Shape]:
    source = mask_comments(text)
    code = mask_code(source)
    owners = re.findall(r'\bclass\s+(\w+)', code)
    if len(owners) != 1:
        return {}
    candidates = [m for m in methods(source, code) if m.name == 'DataTableToXml']
    evidence: dict[tuple[str, int], Shape] = {}
    unique = [m for m in candidates if sum(len(c.parameters) == len(m.parameters) for c in candidates) == 1]
    for m in unique:
        observed = _shape(m, source)
        if observed:
            evidence[owners[0], len(m.parameters)] = observed
    for m in unique:
        calls = calls_in(m, 'DataTableToXml')
        if len(calls) != 1:
            continue
        call = calls[0]
        if (m.code[:call.start].strip() == 'return' and m.code[call.end:].strip() == ';' and
                call.args and m.parameters and call.args[0] == m.parameters[0]):
            observed = evidence.get((owners[0], len(call.args)))
            if observed:
                evidence[owners[0], len(m.parameters)] = observed
    return evidence


def serializer_key(expr: str) -> tuple[str, int] | None:
    code = mask_code(expr)
    match = re.fullmatch(r'(?:[\w.]+\.)?(' + IDENT + r')\s*\.\s*DataTableToXml\s*\((.*)\)', code, re.S)
    if match:
        count = len(arguments(expr, code, match.start(2) - 1, match.end(2)))
        return match[1], count
    return None
