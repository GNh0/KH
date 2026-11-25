"""Review direct view appearance deltas without prescribing property values.

Declared receivers and supplied inheritance establish scope. These lexical
observations do not evaluate appearance precedence or authorize a reset.
"""
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import re

from src.common.results import CheckResult, Issue
from .control_defaults import ControlDefaults, control_base_type, read_control_defaults
from .control_names import known_control_kind
from .designer_model import _assignment_end, _normalized_csharp_value
from .lexer import _scan_csharp
from .source import _method_declaration_matches, _split_top_level


_IDENT = r'[A-Za-z_]\w*'
_TYPE = rf'(?:global::)?{_IDENT}(?:\.{_IDENT})*'
_CLASS = re.compile(rf'\bclass\s+(?P<name>{_IDENT})\s*(?::\s*(?P<base>{_TYPE})[^{{}}]*)?\s*\{{')
_DECLARATION = re.compile(rf'(?<![\w.])(?P<type>{_TYPE}\??)\s+(?P<name>{_IDENT})\s*(?=[=;,)]|\bin\b)')
_INITIALIZER = re.compile(rf'\bthis\s*\.\s*(?P<name>{_IDENT})\s*=\s*new\s+(?P<type>{_TYPE})\s*\(')
_WRITE = re.compile(rf'(?<![\w.])(?P<path>(?:{_IDENT}\s*\.\s*)*Appearance'
                    rf'(?:\s*\.\s*{_IDENT})*)\s*=(?!=)')
_LAMBDA = re.compile(rf'(?:\((?P<parameters>[^()]*)\)|(?P<single>{_IDENT}))\s*=>\s*')
_VIEWS = {'GridView', 'BandedGridView', 'AdvBandedGridView', 'CardView', 'LayoutView'}
_NON_TYPES = {'return', 'throw', 'new', 'case', 'is', 'as', 'in', 'out', 'ref', 'await', 'yield'}


@dataclass
class _Scope:
    start: int
    end: int
    parent: int | None
    label: str = ''
    kind: str = ''
    base_type: str = ''


@dataclass(frozen=True)
class _Declaration:
    type_name: str
    start: int
    parameter: bool = False


@dataclass(frozen=True)
class _Assignment:
    scope: str
    member: str
    property: str
    value: str
    line: int


def _scopes(code: str) -> tuple[list[_Scope], dict[int, int]]:
    scopes = [_Scope(-1, len(code), None, '<source>')]
    openings: dict[int, int] = {}
    stack = [0]
    for offset, char in enumerate(code):
        if char == '{':
            openings[offset] = len(scopes)
            scopes.append(_Scope(offset, len(code), stack[-1]))
            stack.append(len(scopes) - 1)
        elif char == '}' and len(stack) > 1:
            scopes[stack.pop()].end = offset
    for match in _CLASS.finditer(code):
        index = openings.get(match.end() - 1)
        if index is not None:
            scopes[index].label = 'class:' + match['name']
            scopes[index].kind = 'class'
            scopes[index].base_type = match['base'] or ''
    return scopes, openings


def _scope_at(scopes: Sequence[_Scope], offset: int) -> int:
    return min((n for n, scope in enumerate(scopes) if scope.start < offset <= scope.end),
               key=lambda n: scopes[n].end - scopes[n].start, default=0)


def _chain(scopes: Sequence[_Scope], index: int) -> list[int]:
    result = []
    cursor: int | None = index
    while cursor is not None:
        result.append(cursor)
        cursor = scopes[cursor].parent
    return result


def _expression_end(code: str, start: int) -> int | None:
    stack: list[str] = []
    pairs = {')': '(', ']': '[', '}': '{'}
    for offset in range(start, len(code)):
        char = code[offset]
        if char in '([{':
            stack.append(char)
        elif char in pairs:
            if not stack:
                return offset
            if stack.pop() != pairs[char]:
                return None
        elif char in ',;' and not stack:
            return offset
    return None


def _assignments(source: str, control_types: Mapping[str, str],
                 defaults: Sequence[ControlDefaults]) -> tuple[list[_Assignment], list[str]]:
    code, _ = _scan_csharp(source)
    scopes, openings = _scopes(code)
    parameter_ranges: list[tuple[int, int, int]] = []
    method_arrows: set[int] = set()
    for match in _method_declaration_matches(code):
        opening = match.end() - 1
        index = openings.get(opening) if match['body'] == '{' else None
        if match['body'] == '=>':
            method_arrows.add(match.end() - 2)
            end = _assignment_end(code, match.end())
            if end is not None:
                index = len(scopes)
                scopes.append(_Scope(opening, end, _scope_at(scopes, match.start())))
        if index is None:
            continue
        scopes[index].label = 'method:' + match['name'] + '(' + _normalized_csharp_value(match['parameters']) + ')'
        scopes[index].kind = 'method'
        parameter_ranges.append((match.start('parameters'), match.end('parameters'), index))
    declarations: dict[tuple[int, str], list[_Declaration]] = defaultdict(list)
    for match in _LAMBDA.finditer(code):
        arrow = code.find('=>', match.start(), match.end())
        if arrow in method_arrows:
            continue
        opening = match.end()
        index = openings.get(opening)
        if index is None:
            end = _expression_end(code, opening)
            if end is None:
                continue
            index = len(scopes)
            scopes.append(_Scope(opening - 1, end, _scope_at(scopes, match.start())))
        parameters = match['parameters'] if match['parameters'] is not None else match['single']
        scopes[index].label = 'lambda:(' + _normalized_csharp_value(parameters) + ')'
        scopes[index].kind = 'lambda'
        left = match.start('parameters') if match['parameters'] is not None else match.start('single')
        parameter_ranges.append((left, left + len(parameters), index))
        # Untyped lambda parameters shadow fields. Their types cannot be
        # inferred from the field or from a familiar parameter name.
        for parameter in _split_top_level(parameters):
            if re.fullmatch(_IDENT, parameter.strip()):
                declarations[index, parameter.strip()].append(_Declaration('var', left, True))
    for match in _DECLARATION.finditer(code):
        declared_type = match['type'].removesuffix('?')
        if declared_type in _NON_TYPES:
            continue
        parameter_scope = next((index for left, right, index in parameter_ranges if left <= match.start() < right), None)
        index = parameter_scope if parameter_scope is not None else _scope_at(scopes, match.start())
        if declared_type == 'var':
            created = re.match(rf'=\s*new\s+({_TYPE})\s*\(', code[match.end():])
            constructed_type = created.group(1) if created else None
            if constructed_type is not None:
                declared_type = constructed_type
        declarations[index, match['name']].append(_Declaration(declared_type, match.start(), parameter_scope is not None))
    for match in _INITIALIZER.finditer(code):
        parents = _chain(scopes, _scope_at(scopes, match.start()))
        index = next((n for n in parents if scopes[n].kind == 'class'), 0)
        key = (index, match['name'])
        if key not in declarations:
            declarations[key].append(_Declaration(match['type'], match.start()))
    # Local definitions are used only for their explicit inheritance, not as
    # proof that constructor values are effective at runtime.
    combined = {item.type_name: item for item in defaults}
    combined.update({item.type_name: item for item in read_control_defaults((source,))})
    bases = tuple(combined.values())
    class_count = sum(scope.kind == 'class' for scope in scopes)
    observed: list[_Assignment] = []
    unresolved: list[str] = []
    for match in _WRITE.finditer(code):
        parts = re.split(r'\s*\.\s*', match['path'])
        if code[:match.start()].rstrip().endswith('.'):
            unresolved.append('<indirect>:' + '.'.join(parts))
            continue
        appearance = parts.index('Appearance')
        receiver = parts[:appearance]
        parents = _chain(scopes, _scope_at(scopes, match.start()))
        owner = next((n for n in parents if scopes[n].kind == 'class'), 0)
        scope_name = '/'.join(scopes[n].label for n in reversed(parents) if scopes[n].label)
        member = 'this' if receiver in ([], ['this'], ['base']) else receiver[-1]
        type_name: str | None = None
        if receiver in ([], ['this'], ['base']):
            type_name = scopes[owner].base_type or None
        elif len(receiver) == 1 or (len(receiver) == 2 and receiver[0] == 'this'):
            search = [owner] if len(receiver) == 2 else parents
            for index in search:
                records = [item for item in declarations.get((index, member), ())
                           if item.start <= match.start() or item.parameter or scopes[index].kind == 'class']
                if records:
                    types = {item.type_name for item in records}
                    type_name = next(iter(types)) if len(types) == 1 else None
                    break
            else:
                # A supplied Designer belongs to the target partial class;
                # do not apply its fields to several unrelated classes.
                type_name = control_types.get(member) if class_count <= 1 else None
        if type_name is None or type_name == 'var':
            unresolved.append(scope_name + ':' + '.'.join(receiver or ['this']))
            continue
        kind = known_control_kind(control_base_type(type_name, bases))
        if kind not in _VIEWS:
            continue
        end = _expression_end(code, match.end())
        if end is None:
            unresolved.append(scope_name + ':' + '.'.join(parts))
            continue
        observed.append(_Assignment(scope_name, member, '.'.join(parts[appearance:]),
                                    source[match.end():end].strip(), source.count('\n', 0, match.start()) + 1))
    return observed, sorted(set(unresolved))


def check_view_appearance(candidate: str, *, original: str | None = None,
                          control_types: Mapping[str, str] | None = None,
                          original_control_types: Mapping[str, str] | None = None,
                          defaults: Sequence[ControlDefaults] = (),
                          allowed_property_changes: Iterable[str] = ()) -> CheckResult:
    current, unresolved = _assignments(candidate, control_types or {}, defaults)
    previous, old_unresolved = (_assignments(original, original_control_types or {}, defaults)
                                if original is not None else ([], []))
    before: dict[tuple[str, str, str], list[_Assignment]] = defaultdict(list)
    after: dict[tuple[str, str, str], list[_Assignment]] = defaultdict(list)
    for item in previous:
        before[item.scope, item.member, item.property].append(item)
    for item in current:
        after[item.scope, item.member, item.property].append(item)
    result = CheckResult(checked=['direct appearance assignment deltas on declared grid view receivers'],
        not_checked=['view appearance necessity, effective inheritance/precedence, runtime layout, branch execution, inferred lambda/alias types, appearance-object setters, collection/method calls and full C# semantics'])
    allowed = set(allowed_property_changes)
    unchanged = 0
    excluded: set[str] = set()
    for key in sorted(set(before) | set(after)):
        old, new = before[key], after[key]
        property_path = key[1] + '.' + key[2]
        if property_path in allowed:
            excluded.add(property_path)
            continue
        if original is not None and ([_normalized_csharp_value(item.value) for item in old] ==
                                     [_normalized_csharp_value(item.value) for item in new]):
            unchanged += 1
            continue
        result.issues.append(Issue('view_appearance_change_review', 'warning',
            'A view-wide Appearance assignment was added, changed or removed. Compare the specific request with the actual control/base/shared initialization and layout loading. Column appearance does not require this override; preserve verified existing or required behavior rather than applying a global reset.',
            line=(new or old)[0].line, details={'property': property_path, 'scope': key[0],
                'before': [item.value for item in old], 'after': [item.value for item in new],
                'original_available': original is not None}))
    result.metadata['view_appearance'] = {'recognized_assignments': len(current),
        'unchanged_properties': unchanged, 'excluded_properties': sorted(excluded),
        'unresolved_receivers': unresolved, 'original_unresolved_receivers': old_unresolved}
    if unresolved or old_unresolved:
        result.not_checked.append('unresolved appearance receivers listed in view_appearance')
    return result
