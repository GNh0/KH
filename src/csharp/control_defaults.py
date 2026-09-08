"""Review supplied user-control constructors and their use in a screen.

The caller selects control sources from the actual target project. These are
lexical comparisons, not evaluated runtime defaults or dependency discovery.
"""
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
import re

from src.common.results import Issue
from .control_style import direct_statement_spans
from .control_names import control_name_issue, known_control_kind
from .designer_model import DesignerModel, _normalized_csharp_value
from .lexer import _scan_csharp, balanced_close, string_literal_value


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


def with_control_base_types(model: DesignerModel, defaults: Sequence[ControlDefaults]) -> DesignerModel:
    """Resolve only the explicit inheritance chain in the supplied control sources."""
    controls = {}
    for name, control in model.controls.items():
        type_name = control.type_name
        seen: set[str] = set()
        while type_name not in seen:
            seen.add(type_name)
            matching = [item for item in defaults if _same_type(type_name, item.type_name)]
            if len(matching) != 1:
                break
            type_name = matching[0].base_type
        controls[name] = replace(control, type_name=type_name)
    return replace(model, controls=controls)


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


def check_control_defaults(model: DesignerModel, *, original: DesignerModel | None = None,
                          defaults: Sequence[ControlDefaults] = (),
                          allowed_property_changes: Iterable[str] = (),
                          check_declarations: bool = True) -> list[Issue]:
    issues: list[Issue] = []
    allowed = set(allowed_property_changes)
    base_model = with_control_base_types(model, defaults)
    for name, control in model.controls.items():
        before = original.controls.get(name) if original else None
        old = before.properties if before else {}
        new_type = before is None or not _same_type(before.type_name, control.type_name)
        matching = [item for item in defaults if _same_type(control.type_name, item.type_name)]

        def changed(prop: str) -> bool:
            return (f'{name}.{prop}' not in allowed and prop in control.properties and
                    (new_type or prop not in old or _normalized_csharp_value(old[prop]) != _normalized_csharp_value(control.properties[prop])))

        is_date = known_control_kind(base_model.controls[name].type_name) == 'DateEdit'
        if check_declarations and control.type_name and changed('Name'):
            value = string_literal_value(control.properties['Name'])
            if value is not None and value != name:
                issues.append(Issue('control_name_mismatch', 'warning',
                                    'The declared member and its Name differ. Keep naming changes consistent with the actual field and references.',
                                    details={'control': name, 'name_value': value}))
        if check_declarations and new_type and f'{name}.Name' not in allowed:
            naming = control_name_issue(name, base_model.controls[name].type_name)
            if naming:
                issues.append(naming)
        if is_date:
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
            if prop in {'Name', 'Location', 'TabIndex', 'BindingField', 'DataPropertyName'} or not changed(prop):
                continue
            actual = control.properties[prop]
            equal = _normalized_csharp_value(actual) == _normalized_csharp_value(expected)
            issues.append(Issue('user_control_default_restatement' if equal else 'user_control_default_override',
                                'info' if equal else 'warning',
                                'This assignment repeats a supplied constructor default; prefer inheriting it unless Designer serialization requires it.' if equal else
                                'This screen assignment overrides a supplied user-control constructor default. Keep the control initialization unless the requested behavior requires this specific change.',
                                details={'property': f'{name}.{prop}', 'constructor_value': expected, 'screen_value': actual}))
    return issues
