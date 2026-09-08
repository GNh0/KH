"""Scoped KH grid preferences and explicit column editing contracts.

Compare deltas when a baseline exists. A style warning is not authorization to
rewrite an existing screen, and explicit target exceptions need no receipt.
"""
from collections.abc import Iterable, Mapping
import re

from src.common.grid_defaults import DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS
from src.common.results import Issue
from .designer_model import DesignerModel, _normalized_csharp_value
from .control_names import known_control_kind


EDIT_PROPERTIES = ('OptionsColumn.AllowEdit', 'OptionsColumn.ReadOnly')
_EDIT_MODES = {
    'read_only': {'OptionsColumn.AllowEdit': 'false', 'OptionsColumn.ReadOnly': 'true'},
    'action': {'OptionsColumn.ReadOnly': 'true'},
    'editable': {},
}
_HEADER_DEFAULTS = {
    'AppearanceHeader.Options.UseFont': 'true',
    'AppearanceHeader.Options.UseTextOptions': 'true',
    'AppearanceHeader.TextOptions.HAlignment': 'Center',
    'AppearanceHeader.TextOptions.VAlignment': 'Center',
}
_GRID_VIEWS = {'GridView', 'BandedGridView', 'AdvBandedGridView', 'CardView', 'LayoutView'}


def column_edit_properties(mode: str) -> dict[str, str]:
    if not isinstance(mode, str) or mode not in _EDIT_MODES:
        raise ValueError('Column edit mode must be read_only, action, or editable.')
    return dict(_EDIT_MODES[mode])


def check_grid_style(model: DesignerModel, *, original: DesignerModel | None = None,
                     column_edit_modes: Mapping[str, str] | None = None,
                     allowed_property_changes: Iterable[str] = (),
                     check_required_defaults: bool = True) -> list[Issue]:
    issues: list[Issue] = []
    allowed = set(allowed_property_changes)
    modes = dict(column_edit_modes or {})
    for name, mode in modes.items():
        column_edit_properties(mode)
        if name not in model.controls:
            issues.append(Issue('column_edit_target_missing', 'error',
                                'The requested column edit mode has no supplied member.', details={'column': name}))
        elif model.controls[name].type_name and model.controls[name].type_name.split('.')[-1] != 'GridColumn':
            issues.append(Issue('column_edit_target_invalid', 'error',
                                'The requested edit contract requires a GridColumn member.', details={'column': name}))
    before_controls = original.controls if original else {}
    for name in sorted(set(model.controls) | set(before_controls)):
        control = model.controls.get(name)
        before = before_controls.get(name)
        props = control.properties if control else {}
        old = before.properties if before else {}
        declared_type = ((control.type_name if control else '') or (before.type_name if before else '')).removeprefix('global::')
        type_name = known_control_kind(declared_type)

        def changed(prop: str) -> bool:
            if f'{name}.{prop}' in allowed:
                return False
            if original is None:
                return True
            left, right = old.get(prop), props.get(prop)
            return ((left is None) != (right is None) or
                    (left is not None and right is not None and
                     _normalized_csharp_value(left) != _normalized_csharp_value(right)))

        def warn(code: str, message: str, prop: str) -> None:
            issues.append(Issue(code, 'warning', message,
                                details={'property': f'{name}.{prop}', 'before': old.get(prop), 'after': props.get(prop)}))

        # Include removals: preserving OptionsBehavior does not mean resetting it.
        if type_name in _GRID_VIEWS or not type_name:
            for prop in sorted(set(props) | set(old)):
                if prop.startswith('OptionsBehavior.') and changed(prop):
                    warn('grid_options_behavior_change',
                         'Preserve existing view behavior. Add/change/remove this option only for a specific requested or required behavior; column editing is a separate policy.', prop)
        if type_name in _GRID_VIEWS | {'GridControl'}:
            for prop, value in props.items():
                if not prop.startswith('Options') or prop.startswith('OptionsBehavior.') or not changed(prop):
                    continue
                expected = DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS.get(prop.removeprefix('OptionsView.')) if prop.startswith('OptionsView.') else None
                if expected is None:
                    warn('grid_option_outside_baseline', 'This option is outside the supplied HTML layout defaults; verify the specific behavior requiring it.', prop)
                elif value.strip() != expected:
                    warn('grid_layout_default_changed', 'This option differs from the supplied HTML layout default; retain a verified target requirement.', prop)

        # DateEdit masks and report formatting are separate scopes.
        is_column = type_name == 'GridColumn' or (not type_name and (name in modes or any(p.startswith(('AppearanceCell.', 'OptionsColumn.')) for p in props)))
        is_editor = type_name.startswith('RepositoryItem') or type_name in {'SpinEdit', 'DateEdit', 'TextEdit', 'ButtonEdit', 'LookUpEdit', 'GridLookUpEdit'}
        if is_column or is_editor:
            for prop in props:
                if re.search(r'(^|\.)DisplayFormat(?:\.|$)', prop) and changed(prop):
                    warn('display_format_preference', 'Omit default DisplayFormat settings, including FormatType and FormatString. Use the actual editor/data contract; a specific required format is an exception.', prop)
        if type_name in {'SpinEdit', 'RepositoryItemSpinEdit'}:
            for prop in props:
                if prop.endswith('Mask.EditMask') and changed(prop):
                    warn('spin_edit_mask_preference', 'Do not add an EditMask simply because the editor is numeric. Preserve existing settings and use an explicit mask only when the actual input behavior requires it.', prop)
        if not is_column or control is None:
            continue
        for prop in props:
            if prop.startswith('Options') and prop not in EDIT_PROPERTIES and changed(prop):
                warn('grid_option_outside_baseline', 'This column option is outside the supplied HTML defaults; verify the specific behavior requiring it.', prop)
            if (prop.startswith('AppearanceCell.TextOptions.') or prop == 'AppearanceCell.Options.UseTextOptions') and changed(prop):
                warn('cell_text_options_preference', 'Leave cell TextOptions unspecified by default; header centering does not imply cell alignment.', prop)
        if check_required_defaults:
            required = {**_HEADER_DEFAULTS, 'AppearanceCell.Options.UseFont': 'true'}
            for prop, expected in required.items():
                value = props.get(prop, '').strip()
                # Explicit enum qualification is harmless; the required member is Center.
                actual = value.split('.')[-1] if expected == 'Center' else value
                missing_new = prop not in props and (original is None or before is None)
                if actual != expected and (missing_new or changed(prop)) and f'{name}.{prop}' not in allowed:
                    warn('header_appearance_default' if prop.startswith('AppearanceHeader.') else 'cell_use_font_default',
                         'Use the supplied HTML appearance defaults for new columns; preserve verified existing appearance.', prop)
        actual_edit = {p: props[p].strip() for p in EDIT_PROPERTIES if p in props}
        if name in modes:
            expected_edit = column_edit_properties(modes[name])
            if actual_edit != expected_edit:
                issues.append(Issue('column_edit_mode_mismatch', 'error', 'Column edit properties do not match the explicitly requested mode.',
                                    details={'column': name, 'mode': modes[name], 'expected': expected_edit, 'actual': actual_edit}))
        elif any(changed(p) for p in EDIT_PROPERTIES if p in props or p in old):
            if actual_edit.get('OptionsColumn.AllowEdit') == 'false' and actual_edit.get('OptionsColumn.ReadOnly') != 'true':
                warn('column_read_only_pair', 'A normal noneditable column uses AllowEdit=false and ReadOnly=true together.', 'OptionsColumn.ReadOnly')
            for prop, default in [('OptionsColumn.AllowEdit', 'true'), ('OptionsColumn.ReadOnly', 'false')]:
                if actual_edit.get(prop) == default and changed(prop):
                    warn('column_edit_default_assignment', 'For an editable column, omit both edit properties instead of assigning their default values.', prop)
            repository = props.get('ColumnEdit', '').removeprefix('this.').strip()
            editor = model.controls.get(repository)
            if editor and editor.type_name.split('.')[-1] == 'RepositoryItemButtonEdit' and actual_edit.get('OptionsColumn.AllowEdit') == 'false':
                warn('button_column_edit_review', 'If the repository action must remain available, set only ReadOnly=true and omit AllowEdit. Confirm the intended column mode.', 'OptionsColumn.AllowEdit')
    return issues
