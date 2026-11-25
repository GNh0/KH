"""Source event coverage and explicit graph comparisons; no ownership ledger."""
import json
from typing import Mapping, Sequence
from src.common.results import CheckResult, Issue
from src.csharp.syntax import _method_declarations
from .source import parse_pb_export


def check_event_mapping(pb_source: str, csharp_source: str, mappings: Sequence[Mapping], *, excluded_events: Sequence[str] = ()) -> CheckResult:
    inventory = parse_pb_export(pb_source).events
    names = {(e['object'] + '::' if e.get('object') else '') + e['name'] for e in inventory}
    names = {name.casefold() for name in names}
    def resolve(value):
        value = str(value).casefold()
        if value in names:
            return value
        matches = [name for name in names if name.split('::')[-1] == value]
        return matches[0] if len(matches) == 1 else value
    excluded = {resolve(name) for name in excluded_events}
    result = CheckResult(checked=['supplied PB executable event inventory', 'mapped C# handler definitions'],
                         not_checked=['event subscription behavior', 'complete state transitions', 'SAVE execution'])
    if not names:
        result.incomplete = True
        result.issues.append(Issue('event_inventory_missing', 'warning', 'No executable event body was found in the supplied PB source.'))
    seen = set()
    for mapping in mappings:
        event = resolve(mapping.get('pb_event', ''))
        handler = str(mapping.get('csharp_handler', ''))
        if event not in names:
            result.issues.append(Issue('mapped_pb_event_missing', 'error', 'A mapping names no event in the supplied PB source.', details={'event': event}))
        if not handler or not _method_declarations(csharp_source, handler):
            result.issues.append(Issue('mapped_handler_missing', 'error', 'The mapped C# handler definition is absent.', details={'handler': handler}))
        seen.add(event)
    for event in sorted(names - seen - excluded):
        result.issues.append(Issue('pb_event_omitted', 'error', 'An original PB event has no target mapping or scoped exclusion.', details={'event': event}))
    result.metadata.update(source_events=sorted(names), mapped_events=sorted(seen), excluded_events=sorted(excluded))
    if excluded:
        result.not_checked.append('excluded event behavior: ' + ', '.join(sorted(excluded)))
    return result


def compare_state_graphs(original: Mapping, candidate: Mapping) -> CheckResult:
    """Compare supplied graphs; callers must separately establish their source origin."""
    result = CheckResult(checked=['supplied event/state graph nodes, edges and ordered effects'],
                         not_checked=['graph extraction correctness', 'runtime transitions'])
    for kind in ('nodes', 'edges'):
        before, after = original.get(kind), candidate.get(kind)
        if not isinstance(before, list) or not isinstance(after, list):
            result.incomplete = True
            result.issues.append(Issue('graph_input_missing', 'warning', 'Both graphs must supply node and edge arrays.'))
            continue
        def canonical(values):
            return [json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':')) for v in values]
        left, right = canonical(before), canonical(after)
        if len(left) != len(set(left)) or len(right) != len(set(right)):
            result.issues.append(Issue('duplicate_graph_record', 'error', 'Duplicate graph records obscure coverage.', details={'kind': kind}))
        if sorted(left) != sorted(right):
            result.issues.append(Issue('state_graph_changed', 'error', 'The supplied graph has missing, invented, or changed transitions/effects.', details={'kind': kind}))
    return result
