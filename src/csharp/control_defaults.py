"""Review supplied user-control constructors and their use in a screen.

The caller selects control sources from the actual target project. These are
lexical comparisons, not evaluated runtime defaults or dependency discovery.
"""
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
import re

from src.common.results import Issue
from .control_style import direct_statement_spans
from .control_names import SINGLE_LINE_INPUT_KINDS, control_name_issue, known_control_kind
from .designer_model import ControlRecord, DesignerModel, _normalized_csharp_value, _parse_size, statically_hidden, visible_comparison
from .lexer import _scan_csharp, balanced_close, string_literal_value
from .control_values import LABEL_PROPERTIES, label_value_key


_TYPE = r'[A-Za-z_][A-Za-z0-9_.:]*'
_CLASS = re.compile(rf'\bclass\s+(\w+)\s*:\s*({_TYPE})[^{{}}]*\{{')
_WRITE = re.compile(r'\b(?:this|base)\.([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*=(?!=)')


@dataclass(frozen=True)
class ControlDefaults:
    type_name: str
    base_type: str
    properties: dict[str, str] = field(default_factory=dict)
    unresolved_properties: frozenset[str] = frozenset()


def read_control_defaults(sources: Sequence[str]) -> list[ControlDefaults]:
    """Read direct parameterless-constructor assignments; ignore conditional values."""
    found: dict[str, ControlDefaults] = {}
    for source in sources:
        code, _ = _scan_csharp(source)
        namespaces = list(re.finditer(r'\bnamespace\s+([\w.]+)\s*[;{]', code))
        for declaration in _CLASS.finditer(code):
            name, base = declaration[1], declaration[2].removeprefix('global::')
            enclosing = [match[1] for match in namespaces if match.start() < declaration.start()]
            full_name = (enclosing[-1] + '.' if enclosing else '') + name
            close = balanced_close(code, declaration.end() - 1, '{', '}')
            if close < 0:
                continue
            body_code = code[declaration.end():close]
            constructor = re.search(rf'\b(?:public|protected|internal)\s+{re.escape(name)}\s*\(\s*\)\s*(?::\s*base\s*\([^{{}}]*\)\s*)?\{{', body_code)
            props: dict[str, str] = {}
            unresolved: set[str] = set()
            if constructor:
                opening = declaration.end() + constructor.end() - 1
                closing = balanced_close(code, opening, '{', '}')
                if closing >= 0:
                    body = source[opening + 1:closing]
                    for left, right in direct_statement_spans(body):
                        statement = body[left:right]
                        masked, _ = _scan_csharp(statement)
                        writes = list(_WRITE.finditer(masked))
                        if len(writes) == 1 and not masked[:writes[0].start()].strip():
                            props.pop(writes[0][1], None)
                            props[writes[0][1]] = statement[writes[0].end():].rstrip().removesuffix(';').strip()
                            unresolved.discard(writes[0][1])
                        else:
                            # A later conditional write invalidates an earlier
                            # unconditional value; do not select a culture branch.
                            for write in writes:
                                props.pop(write[1], None)
                                unresolved.add(write[1])
            record = ControlDefaults(full_name, base, props, frozenset(unresolved))
            previous = found.get(full_name)
            if previous is not None and previous != record:
                raise ValueError('Conflicting user-control definitions for ' + full_name)
            found[full_name] = record
    return list(found.values())


def _same_type(left: str, right: str) -> bool:
    left, right = left.removeprefix('global::'), right.removeprefix('global::')
    return left == right or ('.' not in left and left == right.split('.')[-1]) or ('.' not in right and right == left.split('.')[-1])


def control_base_type(type_name: str, defaults: Sequence[ControlDefaults]) -> str:
    """Resolve a unique explicit inheritance chain; do not guess from a name."""
    seen: set[str] = set()
    while type_name not in seen:
        seen.add(type_name)
        matching = [item for item in defaults if _same_type(type_name, item.type_name)]
        if len(matching) != 1:
            break
        type_name = matching[0].base_type
    return type_name


def with_control_base_types(model: DesignerModel, defaults: Sequence[ControlDefaults]) -> DesignerModel:
    """Resolve only the explicit inheritance chain in the supplied control sources."""
    return replace(model, controls={name: replace(control, type_name=control_base_type(control.type_name, defaults))
                                   for name, control in model.controls.items()})


def _inherited_defaults(control: ControlDefaults, defaults: Sequence[ControlDefaults],
                        seen: frozenset[str] = frozenset()) -> dict[str, str]:
    if control.type_name in seen:
        return {}
    parents = [item for item in defaults if _same_type(control.base_type, item.type_name)]
    props = _inherited_defaults(parents[0], defaults, seen | {control.type_name}) if len(parents) == 1 else {}
    props.update(control.properties)
    for name in control.unresolved_properties:
        props.pop(name, None)
    return props


def _effective_size(model: DesignerModel, name: str,
                    initial: tuple[int | None, int | None] = (None, None)) -> tuple[int | None, int | None]:
    """Follow observed literal setters in source order; do not evaluate helpers."""
    width, height = initial
    for assignment in model.assignments:
        if assignment['name'] != name:
            continue
        prop, value = assignment['property'], assignment['value']
        if prop == 'Size':
            dimensions = _parse_size(value)
            width, height = dimensions if dimensions is not None else (None, None)
        elif prop == 'Bounds':
            rectangle = re.fullmatch(r'(?:new\s+)?(?:System\.Drawing\.)?Rectangle\s*\(\s*-?\d+\s*,\s*-?\d+\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', value.strip())
            width, height = (int(rectangle[1]), int(rectangle[2])) if rectangle else (None, None)
        elif prop in {'Width', 'Height'}:
            number = int(value.strip()) if re.fullmatch(r'\d+', value.strip()) else None
            if prop == 'Width':
                width = number
            else:
                height = number
    return width, height


def _presentation_key(prop: str, value: str | None) -> tuple | None:
    if value is None:
        return None
    if prop == 'MaximumSize':
        return _parse_size(value)
    if prop == 'Margin':
        match = re.fullmatch(r'new\s+(?:System\.Windows\.Forms\.)?Padding\s*\(\s*(\d+(?:\s*,\s*\d+){0,3})\s*\)', value)
        if match:
            values = tuple(int(part) for part in match[1].split(','))
            if len(values) == 1:
                return values * 4
            if len(values) == 4:
                return values
        return None
    return label_value_key(prop, value)


def _role_peers(control: ControlRecord, source: DesignerModel) -> list[ControlRecord]:
    peers = [c for c in source.controls.values() if _same_type(c.type_name, control.type_name)
             and c.parent == control.parent and visible_comparison(source, c.name)]
    exact = [c for c in peers if c.name == control.name]
    if exact:
        return exact
    bindings = {p: value for p in ('BindingField', 'DataPropertyName')
                if (value := string_literal_value(control.properties.get(p, ''))) and value.strip()}
    bound = [c for c in peers if any(string_literal_value(c.properties.get(p, '')) == value
                                     for p, value in bindings.items())]
    if bound:
        return bound
    return [c for c in peers if control.add_order is not None and c.add_order is not None and
            ((control.table_position is not None and c.table_position is not None and control.table_position[1] == c.table_position[1]) or
             (control.table_position is None and control.location is not None and c.location is not None and control.location[1] == c.location[1]))]


def check_control_defaults(model: DesignerModel, *, original: DesignerModel | None = None, reference: DesignerModel | None = None,
                          defaults: Sequence[ControlDefaults] = (),
                          allowed_property_changes: Iterable[str] = (),
                          check_declarations: bool = True, check_style: bool = True) -> list[Issue]:
    issues: list[Issue] = []
    allowed = set(allowed_property_changes)
    base_model = with_control_base_types(model, defaults)
    for name, control in model.controls.items():
        before = original.controls.get(name) if original else None
        old = before.properties if before else {}
        new_type = before is None or not _same_type(before.type_name, control.type_name)
        matching = [item for item in defaults if _same_type(control.type_name, item.type_name)]
        comparison_peers = _role_peers(control, reference) if reference and visible_comparison(model, name) else []

        def changed(prop: str) -> bool:
            return (f'{name}.{prop}' not in allowed and prop in control.properties and
                    (new_type or prop not in old or _normalized_csharp_value(old[prop]) != _normalized_csharp_value(control.properties[prop])))

        kind = known_control_kind(base_model.controls[name].type_name)
        is_date = kind == 'DateEdit'
        is_label = kind == 'LabelControl'
        screen_height = kind in SINGLE_LINE_INPUT_KINDS and not (
            kind == 'TextBox' and control.properties.get('Multiline', '').strip() == 'true')
        if check_style and known_control_kind(base_model.controls[name].type_name) in {'SimpleButton', 'Button'} and changed('Tag'):
            value = string_literal_value(control.properties['Tag'])
            if value and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', value) and value != value.upper():
                issues.append(Issue('action_tag_case_preference', 'warning',
                                    'Use the agreed uppercase application action code consistently in this button Tag and its handler. Verify any externally defined case-sensitive value.',
                                    details={'control': name, 'tag': value}))
        if check_declarations and control.type_name and changed('Name'):
            value = string_literal_value(control.properties['Name'])
            if value is not None and value != name:
                issues.append(Issue('control_name_mismatch', 'warning',
                                    'The declared member and its Name differ. Keep naming changes consistent with the actual field and references.',
                                    details={'control': name, 'name_value': value}))
        if check_style and check_declarations and new_type and f'{name}.Name' not in allowed:
            naming = control_name_issue(name, base_model.controls[name].type_name)
            if naming:
                issues.append(naming)
        if check_style and is_date:
            for prop in control.properties:
                if (re.search(r'(^|\.)EditFormat\.', prop) or prop.endswith(('Mask.EditMask', 'Properties.EditMask', 'Mask.MaskType'))) and changed(prop):
                    issues.append(Issue('date_input_option_review', 'warning',
                                        'Preserve the actual date control initialization. Do not add edit formats or masks merely because this is a date; a requested input behavior can require a specific override.',
                                        details={'property': f'{name}.{prop}'}))
        if check_declarations and new_type and not matching:
            preferred = [item.type_name for item in defaults if _same_type(control.type_name, item.base_type)]
            if preferred:
                issues.append(Issue('available_user_control_preference', 'warning',
                                    'The supplied target control sources provide a user control for this base type. Prefer the applicable user control and its initialization; verify a specific reason for the base control.',
                                    details={'control': name, 'type': control.type_name, 'available': preferred}))
        # An unqualified name shared by two supplied namespaces is unresolved.
        if len(matching) != 1:
            continue
        for prop, expected in _inherited_defaults(matching[0], defaults).items():
            if statically_hidden(model, name) and (prop in {'Size', 'Height', 'Bounds', 'MinimumSize', 'MaximumSize', 'Font', 'Margin', 'Padding'} or prop.endswith('.Font')):
                continue  # Binding/behavior/name checks above remain active.
            if prop == 'Size' and check_style:
                default_size = _parse_size(expected)
                if default_size is not None and any(changed(key) for key in ('Size', 'Bounds', 'Width', 'Height')):
                    effective = _effective_size(model, name, default_size)
                    previous = _effective_size(original, name, default_size) if original and not new_type else (None, None)
                    for index, dimension in enumerate(('Width', 'Height')):
                        if index == 1 and (is_label or screen_height):
                            continue  # Height uses the actual peer-screen contract.
                        if any(f'{name}.{key}' in allowed for key in ('Size', 'Bounds', dimension)):
                            continue
                        prior = previous[index]
                        floor = min(default_size[index], prior) if prior is not None else default_size[index]
                        actual_dimension = effective[index]
                        if actual_dimension is None:
                            issues.append(Issue('user_control_size_unresolved', 'warning',
                                'The final control dimension needs expression or helper evaluation before its default-size contract can be verified.',
                                details={'property': f'{name}.{dimension}'}))
                        elif actual_dimension < floor:
                            issues.append(Issue('user_control_size_shrink', 'error',
                                'The final observed control dimension is smaller than its supplied default; preserve the default unless compact sizing was explicitly requested.',
                                details={'property': f'{name}.{dimension}', 'constructor_size': default_size,
                                         'screen_size': effective}))
                continue
            if prop in {'Name', 'Location', 'TabIndex', 'BindingField', 'DataPropertyName', 'EditValue'} or not changed(prop):
                continue
            actual = control.properties[prop]
            equal = _normalized_csharp_value(actual) == _normalized_csharp_value(expected)
            if is_label and check_style and prop in LABEL_PROPERTIES:
                # Label height/font/alignment use the scoped constructor + approved screen comparison.
                continue
            if is_label or prop == 'Font' or prop.endswith('.Font'):
                left, right = label_value_key(prop, actual), label_value_key(prop, expected)
                equal |= left is not None and left == right
            if check_style and screen_height and prop in {'Height', 'Bounds', 'MinimumSize', 'MaximumSize'}:
                # These height contracts are checked with actual screen evidence below.
                continue
            if check_style and comparison_peers and (prop in {'Margin', 'MaximumSize', 'Font'} or prop.endswith('.Font')):
                peer_keys = {_presentation_key(prop, c.properties.get(prop, expected)) for c in comparison_peers}
                actual_key = _presentation_key(prop, actual)
                if actual_key is not None and len(peer_keys) == 1 and None not in peer_keys:
                    if actual_key not in peer_keys:
                        issues.append(Issue('user_control_screen_property_review', 'warning',
                            'The setting differs from the visible same-role control in the supplied screen. Verify the intended override.',
                            details={'property': f'{name}.{prop}', 'screen_value': actual,
                                     'comparison_members': [c.name for c in comparison_peers]}))
                    continue
            issues.append(Issue('user_control_default_restatement' if equal else 'user_control_default_override',
                                'info' if equal else 'warning',
                                'This assignment repeats a supplied constructor default; prefer inheriting it unless Designer serialization requires it.' if equal else
                                'This screen assignment overrides a supplied user-control constructor default. Keep the control initialization unless the requested behavior requires this specific change.',
                                details={'property': f'{name}.{prop}', 'constructor_value': expected, 'screen_value': actual}))
    return issues
