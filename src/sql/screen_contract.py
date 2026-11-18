"""SQL evidence used by the screen/procedure contract comparison."""
from dataclasses import dataclass
from bisect import bisect_right
import re

from src.pb.sql import procedure_parameters
from .change_review import _statement_end
from .dispatch import _guard
from .lexer import _SqlToken, _identifier_value, _scan_sql_tokens
from .procedure_authorship import procedure_headers


def literal(token: _SqlToken) -> str | None:
    if token.kind in {'string', 'unicode_string'}:
        return token.text[token.text.index("'") + 1:-1].replace("''", "'")
    return None


@dataclass
class Projection:
    line: int
    fields: list[str]
    complete: bool


@dataclass
class Branch:
    parameter: str
    values: list[str]
    line: int
    results: list[Projection] | None


def _field(tokens: list[_SqlToken]) -> str:
    if len(tokens) >= 3 and tokens[-2].normalized == 'AS':
        return _identifier_value(tokens[-1])
    if len(tokens) >= 3 and tokens[1].text == '=':
        return _identifier_value(tokens[0])
    if tokens and all((_identifier_value(t) and not t.text.startswith('@')) if i % 2 == 0
                      else t.text == '.' for i, t in enumerate(tokens)) and len(tokens) % 2 == 1:
        return _identifier_value(tokens[-1])
    return ''


def projections(tokens: list[_SqlToken], source: str) -> list[Projection] | None:
    """Only determine result order in a flat, read-only arm with explicit SELECTs."""
    outer = [t for t in tokens if not t.depth]
    if any(t.normalized in {'IF', 'ELSE', 'WHILE', 'EXEC', 'EXECUTE', 'GOTO', 'RETURN',
                            'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'INTO', 'OUTPUT',
                            'TRY', 'CATCH', 'FOR', 'FETCH'} for t in outer):
        return None
    found = []
    for i, token in enumerate(outer):
        if token.normalized != 'SELECT':
            continue
        if i and outer[i-1].normalized in {'UNION', 'EXCEPT', 'INTERSECT'} or (
                i >= 2 and [t.normalized for t in outer[i-2:i]] == ['UNION', 'ALL']):
            continue
        cursor = i + 1
        if cursor < len(outer) and outer[cursor].normalized in {'ALL', 'DISTINCT'}:
            cursor += 1
        if cursor + 1 < len(outer) and outer[cursor].text.startswith('@') and outer[cursor + 1].text == '=':
            continue
        parts: list[list[_SqlToken]] = [[]]
        case = 0
        for item in outer[cursor:]:
            if not case and item.normalized in {'FROM', 'WHERE', 'UNION', 'EXCEPT', 'INTERSECT',
                                                'ORDER', 'SELECT', ';', 'END', 'GROUP', 'OPTION'}:
                break
            if item.normalized == 'CASE':
                case += 1
            elif item.normalized == 'END':
                case -= 1
            if item.text == ',':
                parts.append([])
            else:
                parts[-1].append(item)
        names = [_field(part) for part in parts]
        found.append(Projection(source.count('\n', 0, token.start) + 1,
                                [name for name in names if name], all(names)))
    return found


@dataclass
class Procedure:
    name: str
    path: str
    parameters: dict[str, bool]
    branches: list[Branch]
    uncertain_guards: set[str]
    xml: dict[str, list[tuple[str, int]]]
    unknown_xml: list[int]
    unguarded_results: list[Projection] | None
    outside_results: bool


def read_procedure(source: str, path: str) -> Procedure:
    headers = procedure_headers(source)
    if len(headers) != 1 or not headers[0].body_observed:
        raise ValueError(f'{path}: supply one complete stored procedure definition')
    header = headers[0]
    tokens, errors = _scan_sql_tokens(source)
    if errors:
        raise ValueError(f'{path}: SQL lexical errors prevent contract comparison')
    end = sum(map(len, source.splitlines(keepends=True)[:header.unit_end]))
    body = [t for t in tokens if header.body_start <= t.start < end and
            t.kind not in {'line_comment', 'block_comment'}]
    parameters = procedure_parameters(source)
    branches: list[Branch] = []
    spans = []
    unknown_guards: set[str] = set()
    xml: dict[str, list[tuple[str, int]]] = {}
    unknown_xml = []
    handles: dict[str, str] = {}
    newlines = [m.start() for m in re.finditer('\n', source)]
    for i, token in enumerate(body):
        word = token.normalized
        line = bisect_right(newlines, token.start) + 1
        if word == 'IF':
            guard = _guard(body, i, allow_statement=True)
            if guard:
                start, observed = guard
                param = observed.signature[0].upper()
                values = [value[value.index("'")+1:-1].replace("''", "'") for kind, value
                          in observed.signature[2] if kind in {'string', 'unicode_string'}]
                if param in parameters and values:
                    finish = _statement_end(body, start)
                    branches.append(Branch(param, values, line, projections(body[start:finish], source)))
                    spans.append((start, finish))
                    continue
            for part in body[i + 1:]:
                if part.normalized in {'BEGIN', 'SELECT', 'IF', 'RETURN', 'SET', 'END'}:
                    break
                if part.normalized in parameters:
                    unknown_guards.add(part.normalized)
        if word == 'ELSE' and i + 1 < len(body) and body[i + 1].normalized != 'IF':
            # Only a fallback on the same recognized guard can accept additional modes.
            for j, (_, finish) in enumerate(spans):
                if finish == i:
                    unknown_guards.add(branches[j].parameter)
        if word in {'BEGIN', 'END', 'ELSE', 'IF', 'GOTO'}:
            handles.clear()
        if word == 'SP_XML_PREPAREDOCUMENT' and i + 4 < len(body):
            handle, output, comma, arg = body[i + 1:i + 5]
            handles.pop(handle.normalized, None)
            if output.normalized in {'OUT', 'OUTPUT'} and comma.text == ',' and arg.normalized in parameters:
                handles[handle.normalized] = arg.normalized
        elif word == 'SP_XML_REMOVEDOCUMENT' and i + 1 < len(body):
            handles.pop(body[i + 1].normalized, None)
        elif word in handles and i + 1 < len(body) and body[i + 1].text == '=':
            handles.pop(word)
        elif word == 'OPENXML':
            args = body[i + 1:i + 6]
            if len(args) >= 5 and args[0].text == '(' and args[2].text == ',' and args[4].text in {',', ')'}:
                parameter = handles.get(args[1].normalized)
                xpath = literal(args[3])
                if parameter and xpath and re.fullmatch(r'/[\w.-]+/[\w.-]+', xpath):
                    xml.setdefault(parameter, []).append((xpath, line))
                    continue
            unknown_xml.append(line)
    outside = any(t.normalized in {'SELECT', 'EXEC', 'EXECUTE', 'OUTPUT'} and t.depth == 0 and
                  not any(a <= i < b for a, b in spans) for i, t in enumerate(body))
    return Procedure(header.name, path, parameters, branches, unknown_guards, xml, unknown_xml,
                     projections(body, source), outside)
