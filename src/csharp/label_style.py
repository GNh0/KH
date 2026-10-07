"""Compare label presentation and single-line heights with scoped source evidence."""
from collections.abc import Iterable, Sequence

from src.common.results import CheckResult, Issue
from .control_defaults import ControlDefaults, _same_type, with_control_base_types
from .control_names import known_control_kind
from .control_values import HEIGHT_PROPERTIES, LABEL_PROPERTIES, label_constructor_value, label_value_key
from .designer_model import DesignerModel, _normalized_csharp_value


_INPUT_KINDS = frozenset({'TextEdit', 'DateEdit', 'SpinEdit', 'LookUpEdit', 'GridLookUpEdit',
                          'ButtonEdit', 'TimeEdit', 'TextBox'})
_DIMENSIONS = frozenset({'Size', 'Height', 'Bounds'})


def _constructor_values(control: ControlDefaults, defaults: Sequence[ControlDefaults],
                        seen: frozenset[str] = frozenset()) -> dict[str, str]:
    if control.type_name in seen:
        return {}
    parents = [d for d in defaults if _same_type(control.base_type, d.type_name)]
    values = _constructor_values(parents[0], defaults, seen | {control.type_name}) if len(parents) == 1 else {}
    for prop, raw in control.properties.items():
        value = label_constructor_value(prop, raw)
        previous = values.get(prop)
        previous_key = label_value_key(prop, previous) if previous is not None else None
        if value != raw and previous is not None:
            # The self-property fallback preserves a known non-Default value
            # from a supplied base constructor, including specialized labels.
            value = (value if previous_key and previous_key[0] == 'enum' and previous_key[-1] == 'Default'
                     else previous if previous_key and previous_key[0] == 'enum' else raw)
        values.pop(prop, None)
        values[prop] = value
    for prop in control.unresolved_properties:
        values.pop(prop, None)
    return values


def _property_value(properties: dict[str, str], prop: str) -> str | None:
    if prop == 'Height':
        return next((value for key, value in reversed(list(properties.items())) if key in _DIMENSIONS), None)
    return properties.get(prop)


def _key(prop: str, value: str | None) -> tuple | None:
    if value is None:
        return None
    if prop == 'Height' and '(' in value:
        return label_value_key('Bounds' if 'Rectangle' in value else 'Size', value)
    return label_value_key(prop, value)


def check_label_style(model: DesignerModel, *, original: DesignerModel | None = None,
                      reference: DesignerModel | None = None, defaults: Sequence[ControlDefaults] = (),
                      allowed_property_changes: Iterable[str] = (), explicit_only: bool = False) -> CheckResult:
    result = CheckResult(not_checked=['effective control rendering, inherited runtime helpers and DPI/font scaling'])
    allowed = set(allowed_property_changes)
    typed = with_control_base_types(model, defaults)
    typed_reference = with_control_base_types(reference, defaults) if reference else None
    inspected: list[str] = []
    for name, control in model.controls.items():
        kind = known_control_kind(typed.controls[name].type_name)
        is_label = kind == 'LabelControl'
        if not is_label and kind not in _INPUT_KINDS:
            continue
        if kind == 'TextBox' and control.properties.get('Multiline', '').strip() == 'true':
            continue
        properties = (LABEL_PROPERTIES if is_label else HEIGHT_PROPERTIES) - {'Size', 'Bounds'}
        before = original.controls.get(name) if original else None
        old = before.properties if before else {}
        new = before is None or not _same_type(control.type_name, before.type_name)
        changed = {p for p in properties if new or
                   _normalized_csharp_value(_property_value(control.properties, p) or '') !=
                   _normalized_csharp_value(_property_value(old, p) or '')}
        if explicit_only:
            changed = {p for p in changed if _property_value(control.properties, p) is not None}
        if not changed:
            continue
        matching = [d for d in defaults if _same_type(control.type_name, d.type_name)]
        constructor = _constructor_values(matching[0], defaults) if len(matching) == 1 else {}
        comparisons = [c for c in reference.controls.values() if _same_type(control.type_name, c.type_name)] if reference else []
        # Use another single-line input/label only when no same-type reference
        # exists and its visible heights agree. Conflicting roles stay unverified.
        similar = [c for n, c in reference.controls.items()
                   if typed_reference and known_control_kind(typed_reference.controls[n].type_name) in _INPUT_KINDS | {'LabelControl'}
                   and c.properties.get('Multiline', '').strip() != 'true'] if reference else []
        if not constructor and not comparisons and not similar:
            result.not_checked.append('presentation defaults for ' + name + '; supply the actual control source and approved screen controls')
            continue
        inspected.append(name)
        for prop in sorted(changed):
            if f'{name}.{prop}' in allowed:
                continue
            if prop == 'Height':
                writes = {p for p in _DIMENSIONS if p in control.properties and
                          (new or _normalized_csharp_value(control.properties[p]) != _normalized_csharp_value(old.get(p, '')))}
                if writes and all(f'{name}.{p}' in allowed for p in writes):
                    continue
            actual = _property_value(control.properties, prop)
            inherited = _property_value(constructor, prop)
            refs = (comparisons or similar) if prop in HEIGHT_PROPERTIES else comparisons
            values = [_property_value(c.properties, prop) for c in refs]
            present = [v for v in values if v is not None]
            # Control-owned font/alignment win over copied screen overrides.
            # Actual screen heights win over unscaled constructor dimensions.
            use_reference = bool(present) and (prop in HEIGHT_PROPERTIES or inherited is None)
            expected = present[0] if use_reference else inherited
            source = 'comparison controls' if use_reference else 'control constructor'
            if use_reference and len({_key(prop, v) or ('expression', _normalized_csharp_value(v)) for v in present}) > 1:
                if actual is not None:
                    result.incomplete = True
                    result.issues.append(Issue('control_height_reference_ambiguous' if prop in HEIGHT_PROPERTIES else 'label_reference_ambiguous', 'warning',
                        'The supplied comparison controls disagree. Select the approved similar controls for this layout role; do not choose an arbitrary value.',
                        details={'property': f'{name}.{prop}', 'reference_values': sorted(set(present))}))
                continue
            effective = actual if actual is not None else inherited
            if expected is None:
                if actual is not None:
                    result.incomplete = True
                    result.issues.append(Issue('label_property_unverified' if is_label else 'control_height_unverified', 'warning',
                        'This setting has no established default in the supplied evidence. Verify the current requirement and actual initialization.',
                        details={'property': f'{name}.{prop}', 'value': actual}))
                continue
            if effective is None:
                result.incomplete = True
                result.issues.append(Issue('label_property_unverified' if is_label else 'control_height_unverified', 'warning',
                    'The comparison initializes this setting, but no candidate or supplied constructor value establishes it.',
                    details={'property': f'{name}.{prop}', 'expected': expected, 'source': source}))
                continue
            if _normalized_csharp_value(effective) == _normalized_csharp_value(expected):
                continue
            actual_key, expected_key = _key(prop, effective), _key(prop, expected)
            if actual_key is not None and actual_key == expected_key:
                continue
            if actual_key is None or expected_key is None or (prop in HEIGHT_PROPERTIES and not use_reference):
                result.incomplete = True
                result.issues.append(Issue('control_height_unverified' if prop in HEIGHT_PROPERTIES else 'label_value_unverified', 'warning',
                    'Verify the effective value against the actual screen. Constructor dimensions alone do not establish its serialized/scaled height; unsupported expressions are not proved violations.',
                    details={'property': f'{name}.{prop}', 'expected': expected, 'actual': effective, 'source': source}))
                continue
            category = ('height' if prop in HEIGHT_PROPERTIES else 'font' if 'Font' in prop else
                        'alignment' if 'TextOptions' in prop else 'sizing')
            result.issues.append(Issue(('label_' if is_label else 'control_') + category + '_mismatch', 'error',
                'The setting differs from the supplied project contract. Match the actual screen height and preserve label initialization, including H/V alignment. Text length alone does not justify this change.',
                details={'property': f'{name}.{prop}', 'expected': expected, 'actual': effective, 'source': source}))
    if inspected:
        result.checked.append('scoped label font/alignment and label/input heights against supplied initialization and actual comparison controls')
        if reference is None:
            result.not_checked.append('height matching to actual screen controls; no comparison Designer supplied')
    result.metadata['label_style'] = {'inspected_members': inspected, 'reference_supplied': reference is not None,
                                      'control_source_supplied': bool(defaults)}
    return result
