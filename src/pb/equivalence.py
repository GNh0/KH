"""Compare provided measurements without claiming to have run them."""
from collections import Counter
import json
import math
from statistics import median
from src.common.results import CheckResult, Issue


def compare_observations(original: dict, candidate: dict) -> CheckResult:
    result = CheckResult(checked=['provided measurement context, result schema/rows and timings'],
                         not_checked=['measurement execution and origin', 'database execution plans'])
    for key in ('parameters', 'database', 'schema', 'ordered'):
        if key not in original or key not in candidate:
            result.incomplete = True
            result.issues.append(Issue('measurement_context_missing', 'warning', 'Both measurements need the same explicit context.', details={'field': key}))
        elif original[key] != candidate[key]:
            result.issues.append(Issue('measurement_context_differs', 'error', 'Measurements use different contexts.', details={'field': key}))
    if 'rows' not in original or 'rows' not in candidate:
        result.incomplete = True
        result.issues.append(Issue('result_rows_missing', 'warning', 'Result equality cannot be established without rows.'))
    else:
        left, right = original['rows'], candidate['rows']
        encode = lambda values: [json.dumps(x, sort_keys=True, ensure_ascii=False) for x in values]
        same = encode(left) == encode(right) if original.get('ordered', False) else Counter(encode(left)) == Counter(encode(right))
        if not same:
            result.issues.append(Issue('result_rows_differ', 'error', 'Result values, duplicates or required row order changed.'))
    timings = []
    for observation in (original, candidate):
        values = observation.get('elapsed_ms')
        if not isinstance(values, list) or not values or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 for x in values):
            result.incomplete = True
            timings.append(None)
        else:
            timings.append(median(values))
    if all(value is not None for value in timings):
        result.metadata['median_elapsed_ms'] = {'original': timings[0], 'candidate': timings[1]}
        if timings[1] > 0:
            result.metadata['observed_speed_ratio'] = timings[0] / timings[1]
    else:
        result.not_checked.append('performance: valid runtime samples were not supplied')
    for key in ('query_count', 'logical_reads'):
        if key in original and key in candidate:
            result.metadata[key] = {'original': original[key], 'candidate': candidate[key]}
    return result
