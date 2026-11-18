"""Source-based positive/negative controls for the reported 3.5.13 gaps."""
import unittest

from src.csharp.checks import check_csharp
from src.csharp.designer import check_designer


LABEL = '''namespace Demo { public class LabelBox : DevExpress.XtraEditors.LabelControl {
 public LabelBox() {
  base.Size = new System.Drawing.Size(100, 25);
  base.Appearance.Font = new System.Drawing.Font("Arial", 10F);
  base.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Far;
  base.Appearance.TextOptions.VAlignment = DevExpress.Utils.VertAlignment.Center;
 }
} }'''


def screen(name='lbl', font=10, width=100, visible='true'):
    return f'''this.{name} = new Demo.LabelBox();
this.{name}.Visible = {visible};
this.{name}.Size = new System.Drawing.Size({width}, 25);
this.{name}.Appearance.Font = new System.Drawing.Font("Arial", {font}F);
this.Controls.Add(this.{name});'''


def codes(result):
    return [i.code for i in result.issues]


class FollowupFindingsTests(unittest.TestCase):
    def test_hidden_presentation_is_excluded_but_negative_coordinates_are_not_authorization(self):
        hidden = screen(width=10, visible='false')
        self.assertNotIn('user_control_size_shrink', codes(check_designer(hidden, control_sources=[LABEL])))
        negative = screen(width=10) + '\nthis.lbl.Location = new System.Drawing.Point(-1000, -1000);'
        self.assertIn('user_control_size_shrink', codes(check_designer(negative, control_sources=[LABEL])))
        ancestor = screen(width=10).replace('this.Controls.Add(this.lbl);', 'this.panel.Controls.Add(this.lbl);')
        ancestor += '\nthis.panel.Visible = false;'
        self.assertNotIn('user_control_size_shrink', codes(check_designer(ancestor, control_sources=[LABEL])))
        conditional = screen(width=10) + '\nif (hidden) { this.lbl.Visible = false; }'
        self.assertIn('user_control_size_shrink', codes(check_designer(conditional, control_sources=[LABEL])))
        conditional_ancestor = ancestor.replace('this.panel.Visible = false;', 'if (hidden) { this.panel.Visible = false; }')
        self.assertIn('user_control_size_shrink', codes(check_designer(conditional_ancestor, control_sources=[LABEL])))
        branching = screen(width=10, visible='false') + '\nif (hidden) { this.lbl.Visible = true; } else { this.lbl.Visible = false; }'
        for source in (branching, branching.replace('\n', ' ')):
            self.assertIn('user_control_size_shrink', codes(check_designer(source, control_sources=[LABEL])))

    def test_font_reference_and_unchanged_peers_do_not_waive_alignment_or_mass_changes(self):
        target = screen(font=12)
        self.assertNotIn('label_font_mismatch', codes(check_designer(target, style_reference=screen('reference', font=12), control_sources=[LABEL])))
        wrong = target + '\nthis.lbl.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Near;'
        self.assertIn('label_alignment_mismatch', codes(check_designer(wrong, style_reference=screen('reference', font=12), control_sources=[LABEL])))
        before = screen('one', font=12) + screen('two', font=10)
        after = before.replace('this.two.Appearance.Font = new System.Drawing.Font("Arial", 10F)', 'this.two.Appearance.Font = new System.Drawing.Font("Arial", 12F)')
        self.assertNotIn('label_font_mismatch', codes(check_designer(after, original=before, control_sources=[LABEL])))
        before = screen('one') + screen('two')
        after = before.replace('10F', '12F')
        self.assertEqual(2, codes(check_designer(after, original=before, control_sources=[LABEL])).count('label_font_mismatch'))

    def test_text_options_enabling_inherited_alignment_and_issue_locations(self):
        source = screen() + '\nthis.lbl.Appearance.Options.UseTextOptions = true;'
        result = check_designer(source, control_sources=[LABEL])
        self.assertFalse([i for i in result.issues if i.code == 'label_property_unverified' and i.details.get('property', '').endswith('UseTextOptions')])
        bad = source + '\nthis.lbl.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Near;'
        issue = next(i for i in check_designer(bad, control_sources=[LABEL]).issues if i.code == 'label_alignment_mismatch')
        self.assertEqual(len(bad.splitlines()), issue.line)
        self.assertEqual('designer', issue.details['source_artifact'])
        explicit_false = LABEL.replace('base.Size =', 'base.Appearance.Options.UseTextOptions = false; base.Size =')
        self.assertTrue([i for i in check_designer(source, control_sources=[explicit_false]).issues
                         if i.details.get('property', '').endswith('UseTextOptions') and i.severity != 'info'])

    def test_selection_options_need_an_agreeing_actual_reference(self):
        source = '''this.view = new DevExpress.XtraGrid.Views.Grid.GridView();
this.view.OptionsSelection.MultiSelect = true;
this.view.OptionsSelection.MultiSelectMode = DevExpress.XtraGrid.Views.Grid.GridMultiSelectMode.CheckBoxRowSelect;
this.view.OptionsSelection.CheckBoxSelectorColumnWidth = 30;
this.view.OptionsSelection.ShowCheckBoxSelectorInColumnHeader = DevExpress.Utils.DefaultBoolean.True;'''
        self.assertEqual(4, codes(check_designer(source)).count('grid_option_outside_baseline'))
        self.assertNotIn('grid_option_outside_baseline', codes(check_designer(source, style_reference=source)))
        changed = source.replace('ColumnWidth = 30', 'ColumnWidth = 50')
        self.assertEqual(1, codes(check_designer(changed, style_reference=source)).count('grid_option_outside_baseline'))

    def test_clone_spelling_alone_is_not_an_intermediate_table_violation(self):
        for source in ('class Image { public Image Clone() { return this; } }',
                       'var copy = image.Clone();',
                       'DataTable selected = table.Clone(); foreach (int row in view.GetSelectedRows()) { selected.ImportRow(view.GetDataRow(row)); }'):
            self.assertNotIn('intermediate_table_preference', codes(check_csharp(source)))

    def test_static_ui_is_consistent_without_baseline_but_dynamic_branches_are_separate(self):
        static = 'class Screen { private DevExpress.XtraEditors.LabelControl lbl; void Load() { this.lbl.Caption = "Fixed"; } }'
        for original in (None, ''):
            self.assertEqual(1, codes(check_csharp(static, original=original)).count('static_ui_in_code_behind_review'))
            dynamic = 'class Screen { private DevExpress.XtraEditors.LabelControl lbl; void Load() { switch (mode) { case "I": this.lbl.Caption = "Input"; break; default: this.lbl.Caption = "Output"; break; } } }'
            self.assertNotIn('static_ui_in_code_behind_review', codes(check_csharp(dynamic, original=original)))
            self.assertNotIn('static_ui_in_code_behind_review', codes(check_csharp('class Screen { void Load() { this.lbl.Caption = GetCaption(); } }', original=original)))
        dto = 'class Screen { private DataSpec config; void Load() { this.config.Caption = "Station"; } }'
        self.assertNotIn('static_ui_in_code_behind_review', codes(check_csharp(dto)))
        column = 'class Screen { private DevExpress.XtraGrid.Columns.GridColumn col; void Load() { this.col.Caption = "Fixed"; this.col.FieldName = "VALUE"; } }'
        self.assertEqual(2, codes(check_csharp(column)).count('static_ui_in_code_behind_review'))


if __name__ == '__main__':
    unittest.main()
