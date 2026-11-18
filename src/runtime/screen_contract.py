"""Compare a changed, explicitly applied screen and its explicitly applied SP definitions at Stop."""
from collections import Counter
from pathlib import Path

from src.common.results import Issue
from src.csharp.lexer import mask_code, mask_comments, string_literal_value
from src.csharp.screen_calls import TRANSPORT, calls_in, methods
from src.csharp.screen_contract import check_screen_contract
from src.sql.procedure_authorship import procedure_headers
from .check_context import SourceBaselines, source_text


def _targets(source: str) -> set[str]:
    source = mask_comments(source)
    return {name.replace('[', '').replace(']', '').upper()
            for method in methods(source, mask_code(source)) for call in calls_in(method, TRANSPORT)
            if call.args and (name := string_literal_value(call.args[0]))}


def _identity(issue: Issue) -> tuple:
    keys = ('procedure', 'method', 'parameter', 'mode', 'grid', 'member', 'field', 'result_index',
            'table_names', 'paths')
    return issue.code, tuple((key, str(issue.details[key])) for key in keys if key in issue.details)


def _message(issue: Issue) -> str:
    return (f'{issue.path or issue.details.get("method", "")}:{issue.line or issue.details.get("call_line", "")} '
            f'{issue.code} {dict(_identity(issue)[1])}')


def _lost_call_targets(previous: list[dict], current: list[dict]) -> list[str]:
    """Compare resolved and unresolved calls within the same method and transport, independently of line changes."""
    def counts(records):
        bound = Counter()
        unknown = Counter()
        for call in records:
            site = (call['method'], call['transport'])
            if call.get('definition'):
                bound[site] += 1
            else:
                unknown[(*site, call.get('target_expression', ''))] += 1
        return bound, unknown

    old_bound, old_unknown = counts(previous)
    new_bound, new_unknown = counts(current)
    return [f'{method}.{transport}({target})' for method, transport, target in (new_unknown - old_unknown)
            if new_bound[method, transport] < old_bound[method, transport]]


def applied_screen_contracts(state: dict, baselines: SourceBaselines) -> list[dict]:
    applied = {Path(a['target']) for a in state.get('applications', {}).values() if a.get('target')}
    tracked = {Path(name) for name in state.get('files', {})}
    callers = sorted(p for p in applied if p.suffix.lower() == '.cs' and not p.name.lower().endswith('.designer.cs'))
    sql = sorted(p for p in applied if p.suffix.lower() == '.sql')
    if not callers or not sql or not (applied & tracked):
        return []
    cached = {}
    def read(path: Path) -> str:
        if path not in cached:
            cached[path] = source_text(path) if path.is_file() else ''
        return cached[path]

    def original(path: Path) -> str | None:
        return baselines.original(path) if path in tracked else read(path)

    def procedure_name(source: str) -> str:
        headers = procedure_headers(source)
        return headers[0].name.upper() if len(headers) == 1 else ''

    names = {}
    previous_names = {}
    for path in sql:
        names[path] = procedure_name(read(path))
        previous_names[path] = procedure_name(original(path) or '') if path in tracked else names[path]
    reports = []
    for caller in callers:
        if not caller.is_file():
            continue
        selected = _targets(read(caller))
        previous_calls = _targets(original(caller) or '') if caller in tracked else selected
        def matched(name: str, calls: set[str]) -> bool:
            return bool(name) and (name in calls or name.rsplit('.', 1)[-1] in calls)
        definitions = [p for p in sql if matched(names[p], selected) or matched(previous_names[p], previous_calls)]
        designer = next((p for p in applied if p.parent == caller.parent and
                         p.name.casefold() == (caller.stem + '.Designer.cs').casefold() and p.is_file()), None)
        group = [caller, *definitions] + ([designer] if designer else [])
        if not definitions or not tracked.intersection(group):
            continue
        before = {p: original(p) for p in group}
        if all(before[p] == read(p) for p in group):
            continue
        options = dict(caller_path=str(caller), designer_path=str(designer or 'designer'))
        current = check_screen_contract(read(caller), read(designer) if designer else None,
                    {str(p): read(p) for p in definitions}, **options)
        # Missing evidence is recorded and never promoted to a new confirmed violation.
        previous = check_screen_contract(before[caller] or '', before.get(designer) if designer else None,
                    {str(p): before[p] or '' for p in definitions}, **options)
        prior = Counter(_identity(i) for i in previous.issues if i.severity == 'error')
        complete_baseline = all(before[p] is not None for p in group)
        errors, existing = [], []
        for issue in current.issues:
            if issue.severity != 'error':
                continue
            key = _identity(issue)
            if prior[key] or not complete_baseline:
                existing.append(_message(issue))
                prior[key] -= bool(prior[key])
            else:
                errors.append(_message(issue))
        unresolved = {i.code for i in current.issues if i.severity == 'warning'}
        lost = _lost_call_targets(previous.metadata['calls'], current.metadata['calls'])
        if lost:
            unresolved.add('previous_screen_contract_no_longer_resolves')
        for p in definitions:
            if matched(previous_names[p], previous_calls) and not matched(names[p], selected):
                if (matched(previous_names[p], selected) and (not p.exists() or names[p]) and
                        not any(matched(name, {previous_names[p]}) for name in names.values())):
                    errors.append(f'{p}: The caller still uses {previous_names[p]} but its registered definition was removed or renamed.')
        reports.append(dict(caller=str(caller), definitions=[str(p) for p in definitions], designer=str(designer) if designer else None,
            status='failed' if errors else 'incomplete' if unresolved and current.status == 'passed' else current.status,
            new_errors=errors, existing_or_unattributed=existing, lost_call_targets=lost, unresolved=sorted(unresolved)))
    return reports
