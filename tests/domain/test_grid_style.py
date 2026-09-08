import json
from pathlib import Path
import unittest
from xml.etree import ElementTree as ET

from src.csharp.designer import check_designer
from src.csharp.checks import check_csharp
from src.csharp.designer_model import parse_designer_source
from src.pb.datawindow import build_csharp_grid_column_designer_plan, generate_devexpress_grid_xml


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/datawindow_to_xml_defaults.xml'


def column(extra=''):
    return '''this.col = new DevExpress.XtraGrid.Columns.GridColumn();
this.col.AppearanceCell.Options.UseFont = true;
this.col.AppearanceHeader.Options.UseFont = true;
this.col.AppearanceHeader.Options.UseTextOptions = true;
this.col.AppearanceHeader.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Center;
this.col.AppearanceHeader.TextOptions.VAlignment = DevExpress.Utils.VertAlignment.Center;
''' + extra


def issues(source, **kwargs):
    return {item.code for item in check_designer(source, **kwargs).issues}


def xml_shape(element):
    return element.tag, sorted(element.attrib.items()), (element.text or '').strip(), [xml_shape(child) for child in element]


class GridStyleTests(unittest.TestCase):
    def test_xml_matches_output_of_supplied_html(self):
        self.assertEqual(xml_shape(ET.parse(FIXTURE).getroot()),
                         xml_shape(ET.fromstring(generate_devexpress_grid_xml(['ITEMCD', 'QTY']))))

    def test_designer_defaults_match_html_without_adding_edit_locks(self):
        result = build_csharp_grid_column_designer_plan(['ITEMCD', 'QTY'])
        self.assertTrue(result.success, result.metadata)
        model = parse_designer_source(result.stdout)
        view = model.controls['gvwList'].properties
        expected = ET.parse(FIXTURE).getroot()
        options = expected.find("property[@name='OptionsView']")
        self.assertIsNotNone(options)
        for prop in options:
            self.assertEqual(prop.text, view['OptionsView.' + prop.attrib['name']])
        for prop in expected:
            name = prop.attrib['name']
            if name in {'#LayoutVersion', 'Name', 'Columns', 'OptionsView'}:
                continue
            # Compare the independent HTML values with emitted C# assignments.
            value = view[name]
            if value == 'string.Empty':
                value = ''
            elif 'DevExpress.' in value:
                value = ', '.join(part.strip().split('.')[-1] for part in value.split('|'))
            self.assertEqual(prop.text or '', value, name)
        self.assertFalse(any(p.startswith('OptionsBehavior.') for p in view))
        for name in ['colList_ITEMCD', 'colList_QTY']:
            props = model.controls[name].properties
            self.assertNotIn('OptionsColumn.AllowEdit', props)
            self.assertNotIn('OptionsColumn.ReadOnly', props)
            self.assertFalse(any(p.startswith('AppearanceCell.TextOptions.') or p == 'AppearanceCell.Options.UseTextOptions' for p in props))
        self.assertFalse(any('EditMask' in p for control in model.controls.values() for p in control.properties))

    def test_three_column_edit_modes_generate_exact_property_sets(self):
        result = build_csharp_grid_column_designer_plan(['A', 'B', 'C'],
            column_edit_modes={'A': 'read_only', 'colList_B': 'action', 'C': 'editable'})
        self.assertTrue(result.success, result.metadata)
        model = parse_designer_source(result.stdout)
        actual = {name: {p: v for p, v in control.properties.items() if p.startswith('OptionsColumn.')}
                  for name, control in model.controls.items() if name.startswith('colList_')}
        self.assertEqual({'colList_A': {'OptionsColumn.AllowEdit': 'false', 'OptionsColumn.ReadOnly': 'true'},
                          'colList_B': {'OptionsColumn.ReadOnly': 'true'}, 'colList_C': {}}, actual)

    def test_explicit_legacy_readonly_default_adds_both_flags(self):
        code = build_csharp_grid_column_designer_plan(['A'], default_allow_edit=False).stdout
        self.assertIn('OptionsColumn.ReadOnly = true', code)
        self.assertIn('OptionsColumn.AllowEdit = false', code)
        self.assertNotIn('OptionsColumn.', build_csharp_grid_column_designer_plan(['A'], default_allow_edit=True).stdout)

    def test_unknown_or_conflicting_mode_inputs_do_not_silently_pass(self):
        for mapping in [{'MISSING': 'editable'}, {'A': 'invalid'}, {'A': 'action', 'colList_A': 'read_only'}]:
            with self.subTest(mapping=mapping):
                self.assertFalse(build_csharp_grid_column_designer_plan(['A'], column_edit_modes=mapping).success)

    def test_target_override_can_remove_template_property_and_preserve_view_setting(self):
        result = build_csharp_grid_column_designer_plan(['A'],
            column_properties={'A': {'AppearanceCell.Font': None, 'Visible': 'false'}},
            view_properties={'OptionsBehavior.Editable': 'false'})
        self.assertTrue(result.success, result.metadata)
        props = parse_designer_source(result.stdout).controls['colList_A'].properties
        self.assertNotIn('AppearanceCell.Font', props)
        self.assertEqual('false', props['Visible'])
        self.assertIn('OptionsBehavior.Editable = false', result.stdout)

    def test_valid_column_modes_pass_without_style_findings(self):
        for mode, text in [('read_only', 'this.col.OptionsColumn.AllowEdit = false; this.col.OptionsColumn.ReadOnly = true;'),
                           ('action', 'this.col.OptionsColumn.ReadOnly = true;'), ('editable', '')]:
            with self.subTest(mode=mode):
                result = check_designer(column(text).replace('this.col', 'this.colList_ITEMCD'), column_edit_modes={'colList_ITEMCD': mode})
                self.assertEqual([], result.issues)

    def test_explicit_column_mode_mismatch_is_a_contract_error(self):
        for mode, text in [('read_only', 'this.col.OptionsColumn.AllowEdit = false;'),
                           ('action', 'this.col.OptionsColumn.AllowEdit = false; this.col.OptionsColumn.ReadOnly = true;'),
                           ('editable', 'this.col.OptionsColumn.AllowEdit = true; this.col.OptionsColumn.ReadOnly = false;')]:
            with self.subTest(mode=mode):
                result = check_designer(column(text), column_edit_modes={'col': mode})
                self.assertFalse(result.success)
                self.assertIn('column_edit_mode_mismatch', {i.code for i in result.issues})

    def test_mode_requires_an_actual_or_explicit_partial_column(self):
        self.assertFalse(check_designer('this.button = new Button();', column_edit_modes={'button': 'editable'}).success)
        self.assertFalse(check_designer('this.col.Name = "col";', column_edit_modes={'col': 'read_only'}).success)

    def test_default_review_finds_missing_pair_and_redundant_values(self):
        self.assertIn('column_read_only_pair', issues(column('this.col.OptionsColumn.AllowEdit = false;')))
        self.assertIn('column_edit_default_assignment', issues(column('this.col.OptionsColumn.AllowEdit = true;')))
        self.assertIn('column_edit_default_assignment', issues(column('this.col.OptionsColumn.ReadOnly = false;')))
        before = column('this.col.OptionsColumn.AllowEdit = false; this.col.OptionsColumn.ReadOnly = true;')
        self.assertIn('column_read_only_pair', issues(before.replace('this.col.OptionsColumn.ReadOnly = true;', ''), original=before))

    def test_displayformat_type_and_string_are_both_reviewed(self):
        for prop, value in [('FormatType', 'DevExpress.Utils.FormatType.DateTime'), ('FormatString', '"yyyy-MM-dd"')]:
            with self.subTest(prop=prop):
                source = column(f'this.col.DisplayFormat.{prop} = {value};')
                self.assertIn('display_format_preference', issues(source))
                self.assertNotIn('display_format_preference', issues(source, original=source))
        self.assertNotIn('display_format_preference', issues('this.report = new XRLabel(); this.report.DisplayFormat.FormatString = "N0";'))

    def test_code_behind_does_not_bypass_grid_style_review(self):
        source = 'this.rep.Mask.EditMask = "N0"; this.view.OptionsBehavior.ReadOnly = true;'
        designer = 'this.rep = new RepositoryItemSpinEdit(); this.view = new GridView();'
        result = check_csharp(source, original='', designer=designer, original_designer=designer)
        self.assertTrue({'spin_edit_mask_preference', 'grid_options_behavior_change'} <= {i.code for i in result.issues})

    def test_removed_non_grid_member_uses_original_designer_type(self):
        result = check_csharp('class Screen {}', original='this.tree.OptionsBehavior.Editable = false;',
            designer='class Screen {}', original_designer='this.tree = new TreeList();')
        self.assertNotIn('grid_options_behavior_change', {i.code for i in result.issues})

    def test_property_override_may_not_contradict_explicit_column_mode(self):
        result = build_csharp_grid_column_designer_plan(['A'], column_edit_modes={'A': 'action'},
            column_properties={'A': {'OptionsColumn.AllowEdit': 'false'}})
        self.assertFalse(result.success)
        self.assertIn('column_edit_mode_mismatch', {i['code'] for i in result.metadata['issues']})

    def test_cell_and_header_have_separate_rules(self):
        source = column('this.col.AppearanceCell.Options.UseTextOptions = true; this.col.AppearanceCell.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Near;')
        self.assertIn('cell_text_options_preference', issues(source))
        self.assertNotIn('header_appearance_default', issues(source))
        self.assertIn('header_appearance_default', issues(column().replace('VertAlignment.Center', 'VertAlignment.Top')))
        self.assertIn('cell_use_font_default', issues(column().replace('AppearanceCell.Options.UseFont = true', 'AppearanceCell.Options.UseFont = false')))

    def test_spin_mask_review_uses_control_type_not_member_name(self):
        for typename, path in [('RepositoryItemSpinEdit', 'Mask.EditMask'), ('SpinEdit', 'Properties.Mask.EditMask')]:
            with self.subTest(typename=typename):
                self.assertIn('spin_edit_mask_preference', issues(f'this.numeric = new {typename}(); this.numeric.{path} = "N0";'))
        self.assertNotIn('spin_edit_mask_preference', issues('this.spinNamedDate = new DateEdit(); this.spinNamedDate.Properties.Mask.EditMask = "yyyy-MM-dd";'))

    def test_button_action_is_not_disabled_by_allowedit(self):
        source = column('this.repo = new RepositoryItemButtonEdit(); this.col.ColumnEdit = this.repo; this.col.OptionsColumn.AllowEdit = false; this.col.OptionsColumn.ReadOnly = true;')
        self.assertIn('button_column_edit_review', issues(source))
        self.assertNotIn('button_column_edit_review', issues(source, column_edit_modes={'col': 'read_only'}))

    def test_verified_konelib_subclasses_use_the_base_control_policy(self):
        for typename in ['KoneLib.Controls.u_GridView', 'KoneLib.Controls.u_GridControl']:
            with self.subTest(typename=typename):
                source = f'this.view = new {typename}(); this.view.OptionsSelection.MultiSelect = true;'
                self.assertIn('grid_option_outside_baseline', issues(source))
                self.assertNotIn('grid_option_outside_baseline', issues(source, original=source))
        source = 'this.view = new KoneLib.Controls.u_GridView(); this.view.OptionsBehavior.Editable = false;'
        self.assertIn('grid_options_behavior_change', issues(source))
        self.assertNotIn('grid_options_behavior_change', issues(source, original=source))
        result = check_csharp('this.view.OptionsBehavior.Editable = false;', original='',
            designer='private KoneLib.Controls.u_GridView view;',
            original_designer='private KoneLib.Controls.u_GridView view;')
        self.assertIn('grid_options_behavior_change', {i.code for i in result.issues})

    def test_konelib_editor_aliases_do_not_generalize_to_similar_member_names(self):
        spin = 'this.editor = new KoneLib.Controls.u_SpinEdit(); this.editor.Properties.Mask.EditMask = "N0";'
        self.assertIn('spin_edit_mask_preference', issues(spin))
        self.assertNotIn('spin_edit_mask_preference', issues(spin, original=spin))
        date = 'this.editor = new KoneLib.Controls.u_DateEdit(); this.editor.Properties.Mask.EditMask = "yyyy-MM-dd";'
        self.assertNotIn('spin_edit_mask_preference', issues(date))
        self.assertIn('display_format_preference', issues(date + ' this.editor.Properties.DisplayFormat.FormatString = "d";'))
        lookalike = 'this.u_GridView = new UnknownWidget(); this.u_GridView.OptionsBehavior.Editable = false;'
        self.assertNotIn('grid_options_behavior_change', issues(lookalike))
        self.assertNotIn('grid_options_behavior_change', issues(lookalike.replace('UnknownWidget', 'Other.u_GridView')))

    def test_existing_appearance_and_mask_are_preserved_without_style_cleanup(self):
        source = column('this.col.AppearanceCell.TextOptions.HAlignment = HorzAlignment.Far;') + '\nthis.rep = new RepositoryItemSpinEdit(); this.rep.Mask.EditMask = "N0";'
        self.assertEqual(set(), issues(source, original=source))

    def test_optionsbehavior_add_change_remove_are_reviewed_but_unchanged_is_preserved(self):
        plain = 'this.view = new GridView();'
        locked = plain + ' this.view.OptionsBehavior.Editable = false; this.view.OptionsBehavior.ReadOnly = true;'
        for before, after in [(plain, locked), (locked, plain), (locked, locked.replace('Editable = false', 'Editable = true'))]:
            with self.subTest(before=before, after=after):
                self.assertIn('grid_options_behavior_change', issues(after, original=before))
        self.assertNotIn('grid_options_behavior_change', issues(locked, original=locked))

    def test_required_specific_option_can_be_declared_without_global_exemption(self):
        source = 'this.view = new GridView(); this.view.OptionsBehavior.Editable = false; this.view.OptionsBehavior.ReadOnly = true;'
        result = check_designer(source, allowed_property_changes=['view.OptionsBehavior.Editable'])
        found = [i.details['property'] for i in result.issues if i.code == 'grid_options_behavior_change']
        self.assertEqual(['view.OptionsBehavior.ReadOnly'], found)
        self.assertTrue(result.success)

    def test_unrequested_view_option_outside_html_needs_review(self):
        source = 'this.view = new GridView(); this.view.OptionsSelection.MultiSelect = true;'
        self.assertIn('grid_option_outside_baseline', issues(source))
        self.assertNotIn('grid_option_outside_baseline', issues(source, original=source))
        self.assertNotIn('grid_option_outside_baseline', issues(source, allowed_property_changes=['view.OptionsSelection.MultiSelect']))
        self.assertIn('grid_option_outside_baseline', issues(column('this.col.OptionsColumn.AllowFocus = false;')))

    def test_string_comments_and_unrelated_controls_do_not_invent_options(self):
        source = '// this.view.OptionsBehavior.Editable = false;\nstring s = """this.view.OptionsBehavior.ReadOnly = true;""";\nthis.treeListItems = new TreeList(); this.treeListItems.OptionsBehavior.Editable = false;'
        self.assertEqual(set(), issues(source))

    def test_same_numeric_field_in_another_grid_uses_role_before_spin(self):
        existing = ['rpsSpinQTY']
        result = build_csharp_grid_column_designer_plan(['QTY'], input_format='detail', existing_repository_names=existing)
        self.assertTrue(result.success, result.metadata)
        model = parse_designer_source(result.stdout)
        self.assertEqual('this.rpsDetailSpinQTY', model.controls['colDetail_QTY'].properties['ColumnEdit'])
        self.assertIn('rpsDetailSpinQTY', model.controls)
        self.assertNotIn('rpsSpinQTY', model.controls)
        self.assertEqual(['rpsSpinQTY'], existing)
        plain = build_csharp_grid_column_designer_plan(['QTY'])
        self.assertIn('rpsSpinQTY', parse_designer_source(plain.stdout).controls)

    def test_occupied_role_repository_is_reported_without_inventing_numeric_suffixes(self):
        result = build_csharp_grid_column_designer_plan(['QTY'], input_format='detail',
            existing_repository_names=['rpsSpinQTY', 'rpsDetailSpinQTY'])
        self.assertFalse(result.success)
        self.assertIn('repository_name_conflict', {i['code'] for i in result.metadata['issues']})
        self.assertNotIn('rpsDetailSpinQTY2', result.stdout)

    def test_both_skill_profiles_share_the_same_current_grid_policy(self):
        csharp = json.loads((ROOT/'skills/csharp-designer-style-harness/references/default-profile.json').read_text(encoding='utf-8'))
        pb = json.loads((ROOT/'skills/pb-to-csharp-migration-harness/references/default-profile.json').read_text(encoding='utf-8'))
        self.assertEqual(csharp, pb)
        self.assertIn('grid_layout', csharp['defaults'])


if __name__ == '__main__':
    unittest.main()
