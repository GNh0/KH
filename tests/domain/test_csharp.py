import unittest
from src.csharp.lexer import _scan_csharp
from src.csharp.checks import check_csharp, verify_csharp_edit_contract
from src.csharp.designer import check_designer


class CSharpTests(unittest.TestCase):
    def test_comments_and_literals_do_not_trigger_code_findings(self):
        text = 'string x = "a.Clone()"; // a.AsEnumerable()\nvar y = @"b.ImportRow()";'
        self.assertFalse(any(i.code.endswith('preference') for i in check_csharp(text).issues))

    def test_interpolation_expression_is_code(self):
        code, _ = _scan_csharp('var s = $"text {items.AsEnumerable()}";')
        self.assertIn('items.AsEnumerable()', code)
        self.assertTrue(any(i.code == 'linq_preference' for i in check_csharp('var s = $"text {items.AsEnumerable()}";').issues))

    def test_linq_is_warning_not_global_failure(self):
        result = check_csharp('var values = rows.AsEnumerable();')
        self.assertTrue(result.success)
        self.assertEqual(result.issues[0].severity, 'warning')

    def test_existing_linq_is_not_newly_flagged(self):
        source = 'var values = rows.AsEnumerable();'
        self.assertFalse(any(i.code == 'linq_preference' for i in check_csharp(source, original=source).issues))

    def test_explicit_user_property_preservation(self):
        before = 'private Button btn;\nthis.btn.Visible = false;\nthis.btn.Font = new Font("기본", 9);'
        after = before.replace('false', 'true')
        result = check_designer(after, original=before, preserved_properties=['btn.Visible'])
        self.assertFalse(result.success)
        self.assertEqual(result.issues[0].code, 'user_property_changed')

    def test_missing_baseline_is_not_assumed_preserved(self):
        result = check_designer('', original='', preserved_properties=['btn.Visible'])
        self.assertEqual(result.status, 'incomplete')

    def test_requested_tab_order(self):
        source = 'private TextBox txtCode;\nprivate TextBox txtName;\nthis.txtCode.TabIndex = 2;\nthis.txtName.TabIndex = 1;'
        self.assertFalse(check_designer(source, expected_tab_order=['txtCode', 'txtName']).success)

    def test_no_universal_control_size(self):
        source = 'private TextBox txtCode;\nthis.txtCode.Size = new Size(157, 31);'
        self.assertTrue(check_designer(source).success)
        self.assertEqual(check_designer(source).issues, [])

    def test_real_subscribed_handler_is_found(self):
        designer = 'this.btn.Click += new System.EventHandler(this.Btn_Click);'
        source = 'private void Btn_Click(object sender, EventArgs e) { }'
        self.assertFalse(check_designer(designer, code_behind=source).issues)

    def test_current_user_explanation_does_not_need_receipt(self):
        result = verify_csharp_edit_contract('private void Save() { }', 'private void Save() { grid.PostEditor(); }', evidence={'allowed_new_calls': ['PostEditor']})
        self.assertFalse(any(i['code'] == 'new_edit_commit_call' for i in result.metadata['issues']))


if __name__ == '__main__':
    unittest.main()
class DesignerEdgeTests(unittest.TestCase):
    def test_new_code_behind_font_assignment_is_reviewed(self):
        before = 'class Form { void Load() {\n} }'
        after = 'class Form { void Load() {\nthis.btn.Font = new System.Drawing.Font("Arial", 10F);\n} }'
        self.assertIn('static_ui_in_code_behind_review', [i.code for i in check_csharp(after, original=before).issues])

    def test_preservation_without_original_is_incomplete(self):
        self.assertEqual('incomplete', check_designer('this.btn.Visible = false;', preserved_properties=['btn.Visible']).status)

    def test_multiline_literal_does_not_invent_designer_controls(self):
        from src.csharp.designer_model import parse_designer_source
        text = 'string example = """\nthis.fake = new Button();\nthis.fake.Visible = false;\n""";'
        self.assertNotIn('fake', parse_designer_source(text).controls)

    def test_missing_repository_registration_is_visible(self):
        text = 'this.colQ = new GridColumn();\nthis.rpsQ = new RepositoryItemSpinEdit();\nthis.colQ.ColumnEdit = this.rpsQ;'
        result = check_designer(text)
        self.assertIn('repository_registration_unconfirmed', [i.code for i in result.issues])
        result = check_designer(text + '\nthis.grd.RepositoryItems.AddRange(new RepositoryItem[] { this.rpsQ });')
        self.assertNotIn('repository_registration_unconfirmed', [i.code for i in result.issues])
