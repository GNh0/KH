"""Review observable editor display rewrites, including local helper paths.

A wired callback that writes DisplayText is evidence of a display override,
not evidence that the callback is unnecessary or that its event is prohibited.
"""
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
import re

from src.common.results import CheckResult, Issue
from .command_flow import _without_local_functions
from .control_names import known_control_kind
from .designer_model import _assignment_end, _normalized_csharp_value
from .lexer import _scan_csharp, balanced_close
from .source import _method_declaration_matches, _split_top_level, _strip_top_level_default


_IDENT = r'[A-Za-z_]\w*'
_BINDING = re.compile(rf'(?<![\w.])(?:this\s*\.\s*)?(?P<member>{_IDENT})'
                      rf'\s*\.\s*(?:Properties\s*\.\s*)?CustomDisplayText\s*\+=\s*')
_CALL = re.compile(rf'(?<![\w.])(?:this\s*\.\s*)?(?P<name>{_IDENT})\s*\(')
_EDITORS = {'BaseEdit', 'SpinEdit', 'DateEdit', 'TextEdit', 'ButtonEdit',
            'LookUpEdit', 'GridLookUpEdit', 'ComboBoxEdit', 'CalcEdit', 'MemoEdit', 'CheckEdit'}


@dataclass(frozen=True)
class _Method:
    parameters: tuple[str, ...]
    body: str
    line: int


@dataclass(frozen=True)
class _Rewrite:
    member: str
    handler: str
    fingerprint: tuple[str, ...]
    writers: tuple[str, ...]
    line: int


def _parameter_names(parameters: str) -> tuple[str, ...]:
    names = []
    for parameter in _split_top_level(parameters):
        match = re.search(rf'({_IDENT})\s*$', _strip_top_level_default(parameter))
        if match is None:
            return ()
        names.append(match[1])
    return tuple(names)


def _methods(source: str) -> dict[str, list[_Method]]:
    code, _ = _scan_csharp(source)
    result: dict[str, list[_Method]] = {}
    previous_end = -1
    for match in _method_declaration_matches(code):
        if match.start() < previous_end:
            continue
        start = match.end()
        end = (balanced_close(code, match.end() - 1, '{', '}') if match['body'] == '{'
               else _assignment_end(code, start))
        if end is None or end < 0:
            continue
        previous_end = end + 1
        body = _without_local_functions(source[start:end])
        method = _Method(_parameter_names(match['parameters']), body,
                         source.count('\n', 0, match.start()) + 1)
        result.setdefault(match['name'], []).append(method)
    return result


def _trace(method: _Method, argument: str | None, methods: Mapping[str, list[_Method]],
           seen: set[tuple[str, str | None]] | None = None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    visited = seen if seen is not None else set()
    code, _ = _scan_csharp(method.body)
    fingerprint = [_normalized_csharp_value(method.body)]
    writers: list[str] = []
    if argument is not None and re.search(rf'(?<![\w.]){re.escape(argument)}\s*\.\s*DisplayText\s*=(?!=)', code):
        writers.append('<callback>')
    for call in _CALL.finditer(code):
        targets = methods.get(call['name'], [])
        if len(targets) != 1:
            continue
        end = balanced_close(code, call.end() - 1, '(', ')')
        if end < 0:
            continue
        values = _split_top_level(code[call.end():end])
        target = targets[0]
        if len(values) != len(target.parameters):
            continue
        forwarded = next((target.parameters[n] for n, value in enumerate(values)
                          if argument is not None and value.strip() == argument), None)
        key = (call['name'], forwarded)
        if key in visited:
            continue
        visited.add(key)
        child, child_writers = _trace(target, forwarded, methods, visited)
        fingerprint.extend(child)
        writers.extend(call['name'] if writer == '<callback>' else writer for writer in child_writers)
    return tuple(fingerprint), tuple(sorted(set(writers)))


def _rewrites(source: str, designer: str | None, control_types: Mapping[str, str]) -> tuple[list[_Rewrite], list[str]]:
    methods = _methods(source)
    result: list[_Rewrite] = []
    unresolved: list[str] = []
    for wiring in (source, designer or ''):
        code, _ = _scan_csharp(wiring)
        for binding in _BINDING.finditer(code):
            member = binding['member']
            kind = known_control_kind(control_types.get(member, ''))
            if kind.startswith('XR'):
                continue
            if kind not in _EDITORS and not kind.startswith('RepositoryItem'):
                unresolved.append(member + ': editor type not resolved')
                continue
            start = binding.end()
            named = re.match(rf'(?:new\s+[\w.]+\s*\(\s*)?(?:this\s*\.\s*)?'
                             rf'(?P<handler>{_IDENT})\s*\)?\s*;', code[start:])
            if named:
                handler = named['handler']
                targets = methods.get(handler, [])
                method = targets[0] if len(targets) == 1 else None
            else:
                handler = '<lambda>'
                method = None
                if code[start:start + 1] == '(':
                    end_parameters = balanced_close(code, start, '(', ')')
                    arrow = re.match(r'\s*=>\s*', code[end_parameters + 1:]) if end_parameters >= 0 else None
                    if arrow:
                        body_start = end_parameters + 1 + arrow.end()
                        end_body = (balanced_close(code, body_start, '{', '}') if code[body_start:body_start + 1] == '{'
                                    else _assignment_end(code, body_start))
                        if end_body is not None and end_body >= 0:
                            opening = body_start + 1 if code[body_start:body_start + 1] == '{' else body_start
                            method = _Method(_parameter_names(code[start + 1:end_parameters]),
                                _without_local_functions(wiring[opening:end_body]), wiring.count('\n', 0, start) + 1)
            if method is None or len(method.parameters) != 2:
                unresolved.append(member + ': callback body not uniquely resolved')
                continue
            fingerprint, writers = _trace(method, method.parameters[-1], methods)
            if writers:
                result.append(_Rewrite(member, handler, fingerprint, writers, method.line))
    return result, unresolved


def check_editor_display(candidate: str, *, original: str | None = None,
                         designer: str | None = None, original_designer: str | None = None,
                         control_types: Mapping[str, str], original_control_types: Mapping[str, str]) -> CheckResult:
    current, unresolved = _rewrites(candidate, designer, control_types)
    previous, _ = _rewrites(original or '', original_designer, original_control_types) if original is not None else ([], [])
    old = Counter((item.member, item.fingerprint) for item in previous)
    result = CheckResult(checked=['typed editor display callbacks and recognizable local helper rewrites'],
        not_checked=['display-override necessity, branch execution, aliases, external helpers and full editor default initialization'])
    unchanged = 0
    for item in current:
        key = (item.member, item.fingerprint)
        if old[key]:
            old[key] -= 1
            unchanged += 1
            continue
        result.issues.append(Issue('editor_display_override_review', 'warning',
            'A wired editor callback changes display text directly or through a local helper. Compare its need with the editor/shared initialization and current request; a different route still overrides display behavior. Preserve a verified required customization.',
            line=item.line, details={'member': item.member, 'event': 'CustomDisplayText',
                'handler': item.handler, 'writers': list(item.writers), 'original_available': original is not None}))
    result.metadata['editor_display_callbacks'] = {'resolved_rewrites': len(current),
        'unchanged_rewrites': unchanged, 'unresolved_bindings': sorted(set(unresolved))}
    if unresolved:
        result.not_checked.append('unresolved editor display bindings listed in editor_display_callbacks')
    return result
