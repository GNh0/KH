"""Compare selected command boundaries with a supplied project example."""
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
import re

from src.common.results import CheckResult, Issue
from .flow_review import _methods
from .lexer import _scan_csharp, balanced_close
from .source import _method_declaration_matches


COMMANDS = frozenset({'search', 'new', 'edit', 'save', 'delete', 'clear', 'print'})
_KINDS = r'Search|New|Edit|Save|Delete|Clear|Print'
_WIRING = re.compile(
    rf'(?<![\w.])(?P<receiver>(?:[A-Za-z_]\w*\s*\.\s*)*)'
    rf'(?P<kind>{_KINDS})Command\s*\+=')
_ACTIONS = {
    'AcceptChanges': re.compile(r'\bAcceptChanges\s*\('),
    'default_edit_mode': re.compile(r'\bm_Editmode\s*=\s*(?:[\w]+\s*\.\s*)*DataEditMode\s*\.\s*DEFAULT\b'),
    'control_protection': re.compile(r'\bUsr_ControlsProtect\s*\('),
    'program_navigation': re.compile(r'\bOpenMenuProgram\s*\('),
    'search_command': re.compile(r'\bCallCommand\s*\(\s*(?:[\w]+\s*\.\s*)*BizCommand\s*\.\s*Search\s*\)'),
}
_REVIEW_ACTIONS = {
    'save': ('AcceptChanges', 'default_edit_mode', 'control_protection'),
    'new': ('program_navigation',),
}


@dataclass(frozen=True)
class _Command:
    kind: str
    name: str
    body: str
    fingerprint: tuple[tuple[str, str], ...]
    line: int


def _without_local_functions(body: str) -> str:
    chars = list(body)
    previous_end = -1
    for match in _method_declaration_matches(body):
        if match.start() < previous_end:
            continue
        if match['body'] == '{':
            end = balanced_close(body, match.end() - 1, '{', '}')
        else:
            end = body.find(';', match.end())
        if end < 0:
            continue
        previous_end = end + 1
        chars[match.start():end + 1] = ['\n' if char == '\n' else ' ' for char in body[match.start():end + 1]]
    return ''.join(chars)


def _commands(source: str) -> list[_Command]:
    code, _ = _scan_csharp(source)
    commands = []
    for match, start, end in _methods(code):
        typed = re.search(rf'\b({_KINDS})CommandEventArgs\b', match['parameters'])
        named = re.search(rf'(?:^|_)({_KINDS})Command$', match['name'])
        kind = typed or named
        if kind is None:
            continue
        _, tokens = _scan_csharp(source[match.start():end + 1])
        commands.append(_Command(kind[1].lower(), match['name'],
            _without_local_functions(code[start:end]),
            tuple((token[0], token[1]) for token in tokens),
            source.count('\n', 0, match.start()) + 1))
    return commands


def _counts(command: _Command) -> dict[str, int]:
    return {name: len(pattern.findall(command.body)) for name, pattern in _ACTIONS.items()}


def check_command_flow(candidate: str, *, original: str | None = None,
                       style_reference: str | None = None,
                       allowed_commands: Sequence[str] | None = None) -> CheckResult:
    """Style differences need review; explicit unsupported commands are errors."""
    allowed = set(allowed_commands) if allowed_commands is not None else None
    if allowed is not None and not allowed <= COMMANDS:
        raise ValueError('screen commands must be search, new, edit, save, delete, clear, or print')
    result = CheckResult(not_checked=[
        'command branch feasibility, indirect calls/subscriptions, inherited toolbar availability, expression-bodied handlers, report behavior and XML/SP behavior'])
    if allowed is None and style_reference is None:
        result.not_checked.extend([
            'allowed screen commands; no explicit command scope supplied',
            'project command-phase comparison; no same-project C# style reference supplied'])
        result.metadata['command_flow'] = {'allowed_commands': None, 'style_reference_supplied': False,
            'reference_commands': [], 'compared_commands': []}
        return result
    commands = _commands(candidate)
    code, _ = _scan_csharp(candidate)
    wired = set()
    if allowed is None:
        result.not_checked.append('allowed screen commands; no explicit command scope supplied')
    else:
        result.checked.append('direct screen command subscriptions and recognizable nonempty command handlers against explicit scope')
        for match in _WIRING.finditer(code):
            receiver = re.sub(r'\s+', '', match['receiver'])
            kind = match['kind'].lower()
            if receiver not in {'', 'this.', 'base.'} or kind in allowed:
                continue
            wired.add(kind)
            result.issues.append(Issue('screen_command_out_of_scope', 'error',
                'This screen subscribes to a command outside the explicitly requested operations. Review the subscription and actual toolbar settings.',
                line=candidate.count('\n', 0, match.start()) + 1,
                details={'command': kind, 'allowed_commands': sorted(allowed)}))
        for command in commands:
            if command.kind not in allowed and command.kind not in wired and command.body.strip():
                result.issues.append(Issue('screen_command_body_out_of_scope', 'warning',
                    'A nonempty handler implements an operation outside the explicit screen scope. Trace direct calls and event wiring before retaining it.',
                    line=command.line, details={'command': command.kind, 'method': command.name}))

    references = _commands(style_reference or '')
    grouped = {kind: [command for command in references if command.kind == kind] for kind in COMMANDS}
    compared = set()
    unchanged = Counter((command.kind, command.name, command.fingerprint)
        for command in _commands(original or '') if style_reference is not None)
    if style_reference is None:
        result.not_checked.append('project command-phase comparison; no same-project C# style reference supplied')
    else:
        result.checked.append('recognizable Save/New phase operations against supplied C# command bodies')
        for command in commands:
            if command.kind not in _REVIEW_ACTIONS:
                continue
            key = (command.kind, command.name, command.fingerprint)
            if unchanged[key]:
                unchanged[key] -= 1
                continue
            baseline = grouped[command.kind]
            if len(baseline) != 1:
                result.not_checked.append(f'{command.name} phase comparison; reference contains {len(baseline)} matching command bodies')
                continue
            compared.add(command.kind)
            current, expected = _counts(command), _counts(baseline[0])
            for action in _REVIEW_ACTIONS[command.kind]:
                if current[action] <= expected[action]:
                    continue
                other_phases = sorted({reference.kind for reference in references
                    if reference.kind != command.kind and _counts(reference)[action]})
                result.issues.append(Issue('command_phase_drift_review', 'warning',
                    'This command adds an operation absent from the supplied project command body. Inspect its actual phase, row states and requested behavior; the operation is not globally prohibited.',
                    line=command.line, details={'command': command.kind, 'method': command.name,
                        'operation': action, 'candidate_count': current[action],
                        'reference_count': expected[action], 'reference_other_phases': other_phases}))
            if command.kind == 'save' and expected['search_command'] and not current['search_command']:
                result.issues.append(Issue('save_refresh_drift_review', 'warning',
                    'The reference Save dispatches Search but this Save does not. Trace the target refresh/reset path, including legitimate indirect tab events.',
                    line=command.line, details={'method': command.name}))
    result.metadata['command_flow'] = {'allowed_commands': sorted(allowed) if allowed is not None else None,
        'style_reference_supplied': style_reference is not None,
        'reference_commands': sorted({command.kind for command in references}),
        'compared_commands': sorted(compared)}
    return result
