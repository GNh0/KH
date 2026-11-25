"""Compare provided measurements without claiming to have run them."""
from collections import Counter
import json
import math
from statistics import median
from typing import TypeAlias, TypeGuard, cast
from src.common.results import CheckResult, Issue

JSONValue: TypeAlias = str | int | float | bool | None | list['JSONValue'] | dict[str, 'JSONValue']


def _is_json(value: object, *, depth: int = 0) -> TypeGuard[JSONValue]:
    """Validate actual external values, including cycles/deep nesting and finite numbers."""
    if depth > 100:
        return False
    if value is None or type(value) in {str, bool, int}:
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_is_json(item, depth=depth + 1) for item in cast(list[object], value))
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json(item, depth=depth + 1)
                   for key, item in cast(dict[object, object], value).items())
    return False


def _json_key(value: JSONValue) -> str:
    # JSON distinguishes booleans, integers and floating-point representations;
    # Python container equality alone considers True == 1.
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':'))


def _validated_observation(value: object, side: str, result: CheckResult) -> dict[str, JSONValue] | None:
    if not _is_json(value) or not isinstance(value, dict):
        result.incomplete = True
        result.issues.append(Issue('measurement_input_invalid', 'warning',
            'An observation must be a JSON object with string keys, finite values and nesting at most 100.',
            details={'side': side}))
        return None
    try:
        _json_key(value)
    except (ValueError, OverflowError):
        result.incomplete = True
        result.issues.append(Issue('measurement_input_invalid', 'warning',
            'The observation cannot be serialized as finite JSON.', details={'side': side}))
        return None
    valid = True
    for field, expected in [('parameters', dict), ('database', str), ('schema', list), ('ordered', bool), ('rows', list)]:
        if field not in value:
            code = 'result_rows_missing' if field == 'rows' else 'measurement_context_missing'
        elif type(value[field]) is not expected or (field == 'database' and not value[field]):
            code = 'measurement_field_invalid'
        else:
            continue
        valid = False
        result.incomplete = True
        result.issues.append(Issue(code, 'warning', 'Measurement fields require the documented JSON types.',
                                   details={'side': side, 'field': field, 'expected': expected.__name__}))
    return value if valid else None


def _timing_median(value: JSONValue) -> float | None:
    if not isinstance(value, list) or not value:
        return None
    samples: list[float] = []
    for sample in value:
        if isinstance(sample, bool) or not isinstance(sample, (int, float)):
            return None
        try:
            number = float(sample)
        except OverflowError:
            return None
        if not math.isfinite(number) or number < 0:
            return None
        samples.append(number)
    observed = median(samples)
    return observed if math.isfinite(observed) else None


def compare_observations(original: object, candidate: object) -> CheckResult:
    result = CheckResult(checked=['provided measurement context, result schema/rows and timings'],
                         not_checked=['measurement execution and origin', 'database execution plans'])
    left = _validated_observation(original, 'original', result)
    right = _validated_observation(candidate, 'candidate', result)
    if left is None or right is None:
        result.not_checked.append('context/result equivalence: malformed or missing input')
        return result
    for key in ('parameters', 'database', 'schema', 'ordered'):
        if _json_key(left[key]) != _json_key(right[key]):
            result.issues.append(Issue('measurement_context_differs', 'error', 'Measurements use different contexts.', details={'field': key}))
    left_rows, right_rows = left['rows'], right['rows']
    assert isinstance(left_rows, list) and isinstance(right_rows, list)  # established by field validation
    encoded_left, encoded_right = [_json_key(row) for row in left_rows], [_json_key(row) for row in right_rows]
    same = encoded_left == encoded_right if left['ordered'] else Counter(encoded_left) == Counter(encoded_right)
    if not same:
        result.issues.append(Issue('result_rows_differ', 'error', 'Result values, duplicates or required row order changed.'))
    left_ms, right_ms = _timing_median(left.get('elapsed_ms')), _timing_median(right.get('elapsed_ms'))
    if left_ms is not None and right_ms is not None:
        result.metadata['median_elapsed_ms'] = {'original': left_ms, 'candidate': right_ms}
        if right_ms > 0:
            ratio = left_ms / right_ms
            if math.isfinite(ratio):
                result.metadata['observed_speed_ratio'] = ratio
            else:
                result.incomplete = True
                result.not_checked.append('performance ratio: exceeds finite numeric range')
    else:
        result.incomplete = True
        result.not_checked.append('performance: valid runtime samples were not supplied')
    for key in ('query_count', 'logical_reads'):
        if key in left and key in right:
            left_count, right_count = left[key], right[key]
            if type(left_count) is int and type(right_count) is int and left_count >= 0 and right_count >= 0:
                result.metadata[key] = {'original': left_count, 'candidate': right_count}
            else:
                result.incomplete = True
                result.not_checked.append(key + ': requires nonnegative integer counters')
    return result
