"""Check explicit Designer structure; live Designer compatibility stays separate."""
import re
from collections import defaultdict
from typing import Iterable, Mapping, Sequence
from src.common.results import CheckResult, Issue
from .lexer import _scan_csharp
from .syntax import _method_declarations
from .designer_model import DesignerModel, parse_designer_source, _normalized_csharp_value
from .grid_style import check_grid_style, check_numeric_column_editors
from .numeric_format import check_numeric_formats
from .control_defaults import read_control_defaults, check_control_defaults, with_control_base_types
from .control_names import known_control_kind
from .source_preservation import compare_existing_properties, remap_members, validate_designer_renames


_EDITOR_BUTTON_CALL = re.compile(
    r'\bthis\.(?P<name>\w+)\.(?P<path>(?:Properties\.)?(?:CalendarTimeProperties\.)?Buttons)'
    r'\.(?:Add|AddRange)\s*\('
)


def _editor_button_paths(source: str) -> dict[str, set[str]]:
    code, _ = _scan_csharp(source)
    paths: dict[str, set[str]] = defaultdict(set)
    for match in _EDITOR_BUTTON_CALL.finditer(code):
        paths[match['name']].add(match['path'])
    return paths


def _check_reference_editor_defaults(model: DesignerModel, reference: DesignerModel,
                                     retained_controls: set[str]) -> list[Issue]:
    """Review button and label setup visible in an actual comparison screen."""
    reference_paths = _editor_button_paths(reference.source)
    candidate_paths = _editor_button_paths(model.source)
    expected: dict[str, set[str]] = defaultdict(set)
    label_text_options = False
    for name, control in reference.controls.items():
        kind = known_control_kind(control.type_name)
        if kind in {'LookUpEdit', 'DateEdit', 'SpinEdit', 'RepositoryItemLookUpEdit', 'RepositoryItemDateEdit', 'RepositoryItemSpinEdit'}:
            expected[kind].update(reference_paths.get(name, set()))
        elif kind == 'LabelControl' and control.properties.get('Appearance.Options.UseTextOptions', '').strip() == 'true':
            label_text_options = True
    issues: list[Issue] = []
    for name, control in model.controls.items():
        kind = known_control_kind(control.type_name)
        if name in retained_controls:
            continue
        if kind in expected:
            missing = sorted(expected[kind] - candidate_paths.get(name, set()))
            if missing:
                issues.append(Issue('editor_button_initialization_review', 'warning',
                                    'The comparison screen initializes editor buttons, but this new control does not. Verify the actual constructor/shared initialization and required collection items; a button hidden at runtime may still need its Designer initializer.',
                                    details={'control': name, 'type': control.type_name, 'missing_button_paths': missing}))
        elif kind == 'LabelControl' and label_text_options and \
                control.properties.get('Appearance.Options.UseTextOptions', '').strip() != 'true':
            issues.append(Issue('label_text_options_review', 'warning',
                                'Comparison-screen labels enable Appearance.Options.UseTextOptions, but this new label does not. Verify effective alignment through the current control constructor and rendered screen.',
                                details={'control': name, 'type': control.type_name}))
    return issues


def check_designer(designer: str, *, code_behind: str = "", original: str | None = None,
                   style_reference: str | None = None,
                   preserved_properties: Iterable[str] = (), expected_tab_order: Iterable[str] = (),
                   inherited_handlers: Iterable[str] = (), column_edit_modes: Mapping[str, str] | None = None,
                   allowed_property_changes: Iterable[str] = (), control_sources: Sequence[str] = (),
                   numeric_columns: Iterable[str] = (), preserve_existing: bool = False,
                   member_renames: Mapping[str, str] | None = None) -> CheckResult:
    result = CheckResult(checked=["explicit Designer members and assignments", "event handler references"],
                         not_checked=["Visual Studio Designer load", "rendered layout", "control-library version compatibility"])
    result.metadata['comparison_baselines'] = {'designer': original is not None}
    if style_reference is not None:
        result.metadata['comparison_baselines']['style_reference'] = True
    renames = member_renames or {}
    if renames:
        if original is None:
            raise ValueError('member renames require the original Designer')
        validate_designer_renames(parse_designer_source(original), renames)
        original = remap_members(original, renames)
        result.metadata['member_renames'] = dict(renames)
    model = parse_designer_source(designer)
    result.issues.extend(check_numeric_formats(designer, original=original))
    result.checked.append('literal numeric format choices at recognized C# format sites')
    result.not_checked.append('numeric-format overload types, dynamic formats, custom formatters and runtime culture/rounding')
    baseline = parse_designer_source(original) if original is not None else None
    defaults = read_control_defaults(control_sources)
    if baseline is not None:
        before_buttons = _editor_button_paths(baseline.source)
        after_buttons = _editor_button_paths(model.source)
        for name, paths in before_buttons.items():
            if (name in model.controls and name in baseline.controls and
                    model.controls[name].type_name == baseline.controls[name].type_name):
                missing = sorted(paths - after_buttons.get(name, set()))
                if missing:
                    result.issues.append(Issue('editor_button_initialization_removed', 'warning',
                        'An existing editor button initialization path was removed. Verify the requested scope, actual constructor and shared initialization before removing it; a runtime-hidden button may still be required.',
                        details={'control': name, 'removed_button_paths': missing}))
        result.checked.append('removed button-initializer paths on retained editor members')
    if style_reference is not None:
        reference = parse_designer_source(style_reference)
        retained_controls = {name for name, control in model.controls.items()
                             if baseline is not None and name in baseline.controls and
                             baseline.controls[name].type_name == control.type_name}
        result.issues.extend(_check_reference_editor_defaults(with_control_base_types(model, defaults),
            with_control_base_types(reference, defaults), retained_controls))
        result.checked.append('new lookup/date/spin control and Repository button initialization plus label text options against the supplied comparison screen')
        result.not_checked.append('runtime button visibility, label alignment and indirect control/base initialization')
    elif any(known_control_kind(control.type_name) in {'LookUpEdit', 'DateEdit', 'SpinEdit', 'RepositoryItemLookUpEdit', 'RepositoryItemDateEdit', 'RepositoryItemSpinEdit', 'LabelControl'}
             for control in with_control_base_types(model, defaults).controls.values()):
        result.not_checked.append('lookup/date/spin button and label text-option comparison; no same-project comparison Designer supplied')
    allowed_property_changes = tuple(allowed_property_changes)
    numeric_columns = tuple(numeric_columns)
    if allowed_property_changes:
        result.metadata['style_exemptions'] = sorted(set(allowed_property_changes))
        result.not_checked.append('default-style checks for supplied exempt properties; exemptions do not establish user authorization or necessity')
    result.issues.extend(check_numeric_column_editors(with_control_base_types(model, defaults), numeric_columns))
    if numeric_columns:
        result.checked.append('Spin repository bindings for supplied numeric column members')
    result.not_checked.append('numeric column type inference and runtime ColumnEdit/column recreation')
    result.issues.extend(check_control_defaults(model, original=baseline, defaults=defaults,
                                                allowed_property_changes=allowed_property_changes))
    result.checked.append('date control naming and added input formatting')
    if control_sources:
        result.checked.append('supplied user-control types and direct parameterless-constructor assignments')
        result.not_checked.append('user-control helpers, unsupplied partial/base initialization, conditions, runtime defaults and actual project availability')
    else:
        result.not_checked.append('available user-control selection and constructor-default overrides; no control sources supplied')
    result.issues.extend(check_grid_style(with_control_base_types(model, defaults),
                                         original=with_control_base_types(baseline, defaults) if baseline else None,
                                         column_edit_modes=column_edit_modes,
                                         allowed_property_changes=allowed_property_changes))
    result.checked.append('KH HTML grid defaults and explicit column edit modes; property deltas when baseline supplied')
    masked, _ = _scan_csharp(designer)
    preserved_properties = tuple(preserved_properties)
    inherited_handlers = set(inherited_handlers)
    if (preserved_properties or preserve_existing) and original is None:
        result.incomplete = True
        result.issues.append(Issue('preservation_baseline_missing', 'warning', 'Supply the original Designer to verify requested property preservation.'))
    if preserve_existing and baseline is not None:
        preserved = compare_existing_properties(model, baseline, allowed_property_changes)
        result.issues.extend(preserved.issues)
        result.checked.extend(preserved.checked)
        result.not_checked.extend(preserved.not_checked)
        result.incomplete |= preserved.incomplete
        result.metadata.update(preserved.metadata)
    for match in re.finditer(r"\bthis\.(\w+)\s*=\s*(?:this\.)?(Create\w*|Build\w*)\s*\(", masked):
        result.issues.append(Issue("designer_factory_assignment", "warning",
                                  "Check Designer support for this factory assignment; static controls normally use explicit initialization.",
                                  line=masked.count("\n", 0, match.start()) + 1, details={"member": match[1]}))
    for handler in re.findall(r"\+=\s*(?:new\s+[\w.<>]+\s*\(\s*)?(?:this\.)?(\w+)\s*(?:\)|;)", masked):
        if handler not in inherited_handlers and not _method_declarations(code_behind + "\n" + designer, handler):
            result.issues.append(Issue("handler_definition_not_found", "warning", "The subscribed handler was not found in the supplied partial files; check inherited/other partial declarations.", details={"handler": handler}))
    declarations = {name for name, control in model.controls.items() if control.type_name}
    registered = set()
    for match in re.finditer(r'\.RepositoryItems\.Add(?:Range)?\s*\((.*?)\)\s*;', masked, re.S):
        registered.update(re.findall(r'\bthis\.(\w+)', match[1]))
    for name, control in model.controls.items():
        repository = control.properties.get("ColumnEdit", "").removeprefix("this.").strip()
        if repository and repository not in declarations:
            result.issues.append(Issue("repository_not_declared", "warning", "ColumnEdit references a repository not present in this supplied Designer.", details={"column": name, "repository": repository}))
        elif repository and repository not in registered:
            result.issues.append(Issue('repository_registration_unconfirmed', 'warning', 'ColumnEdit repository registration was not found; inspect inherited/dynamic registration if applicable.', details={'column': name, 'repository': repository}))
    if baseline is not None:
        requested = set(preserved_properties)
        for key in requested:
            member, separator, prop = key.partition(".")
            if not separator:
                raise ValueError("preserved properties must be member.property paths")
            before = baseline.controls.get(member)
            after = model.controls.get(member)
            old = before.properties.get(prop) if before else None
            new = after.properties.get(prop) if after else None
            if old is None:
                result.incomplete = True
                result.issues.append(Issue("baseline_property_missing", "warning", "The requested original property was not found; preservation cannot be established.", details={"property": key}))
            elif new is None or _normalized_csharp_value(old) != _normalized_csharp_value(new):
                result.issues.append(Issue("user_property_changed", "error", "An explicitly preserved Designer property changed.", details={"property": key, "before": old, "after": new}))
    order = list(expected_tab_order)
    if order:
        result.checked.append("specified input tab order")
        grouped = defaultdict(list)
        for name in order:
            control = model.controls.get(name)
            if control is None or control.tab_index is None:
                result.issues.append(Issue("tab_order_unknown", "warning", "A requested input has no explicit TabIndex in the supplied Designer.", details={"control": name}))
                result.incomplete = True
            else:
                grouped[control.parent].append(control)
        for parent, controls in grouped.items():
            indexes = [c.tab_index for c in controls]
            if indexes != sorted(indexes) or len(indexes) != len(set(indexes)):
                result.issues.append(Issue("tab_order_mismatch", "error", "TabIndex does not follow the specified input order within its container.", details={"parent": parent, "controls": [c.name for c in controls]}))
        if len(grouped) > 1:
            result.not_checked.append("tab traversal order between separate containers")
    result.metadata["controls"] = sorted(model.controls)
    result.metadata['review_status'] = 'needs_review' if any(i.severity != 'info' for i in result.issues) else 'static_checks_only'
    result.metadata['project_style_verified'] = False
    return result
