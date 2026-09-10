import unittest

from src.csharp.checks import check_csharp
from src.csharp.flow_review import check_project_flow


DATE_SOURCE = '''namespace Local.Controls {
public class WorkDate : DateEdit {
    public void SetToDay(int day) { base.DateTime = DateTime.Now.AddDays(day); }
}}'''


def screen(name, body, args='object sender, EventArgs e'):
    return 'class Screen { private void ' + name + '(' + args + ') { ' + body + ' } }'


class FlowReviewTests(unittest.TestCase):
    def codes(self, text, **kwargs):
        return {i.code for i in check_project_flow(text, **kwargs)}

    def test_new_and_edit_queries_are_visible(self):
        for name in ['Screen_NewCommand', 'Screen_EditCommand']:
            with self.subTest(name=name):
                before = screen(name, 'mode = EDIT;')
                after = screen(name, 'mode = EDIT; grid.DataSource = CallSelectProcedure(SelectType.DETAIL, key).Tables[0];')
                self.assertIn('entry_query_review', self.codes(after, original=before))

    def test_event_argument_type_is_supported_without_name_convention(self):
        source = screen('EnterEdit', 'CallSelectProcedure(SelectType.DETAIL);', 'object sender, EditCommandEventArgs e')
        self.assertIn('entry_query_review', self.codes(source, original=''))

    def test_original_queries_and_formatting_only_changes_are_preserved(self):
        before = screen('Screen_EditCommand', 'CallSelectProcedure(SelectType.DETAIL, key);')
        after = screen('Screen_EditCommand', 'CallSelectProcedure( /* existing behavior */ SelectType.DETAIL, key );')
        self.assertNotIn('entry_query_review', self.codes(after, original=before))

    def test_query_moved_to_another_event_is_not_hidden_by_global_counts(self):
        before = screen('Screen_SearchCommand', 'CallSelectProcedure(SelectType.DETAIL, key);')
        after = screen('Screen_EditCommand', 'CallSelectProcedure(SelectType.DETAIL, key);')
        self.assertIn('entry_query_review', self.codes(after, original=before))

    def test_schema_query_can_be_reviewed_without_becoming_a_ban(self):
        source = screen('Screen_NewCommand', 'grid.DataSource = CallSelectProcedure(SelectType.DETAIL, string.Empty).Tables[0];')
        result = check_csharp(source, original=screen('Screen_NewCommand', ''))
        self.assertTrue(result.success)
        self.assertEqual('needs_review', result.metadata['review_status'])
        self.assertFalse(result.metadata['project_style_verified'])

    def test_search_queries_and_item_queries_in_the_existing_tab_event_are_not_entry_changes(self):
        for name in ['Screen_SearchCommand', 'Tab_SelectedPageChanged']:
            self.assertNotIn('entry_query_review', self.codes(screen(name, 'CallSelectProcedure(SelectType.ITEM);'), original=''))

    def test_save_guard_is_reviewed_and_existing_guard_is_preserved(self):
        source = screen('Screen_SaveCommand', 'if (row.IsNull("QTY")) { ShowMessageWaring("수량 확인"); return; }')
        self.assertIn('save_gate_review', self.codes(source, original=screen('Screen_SaveCommand', '')))
        self.assertNotIn('save_gate_review', self.codes(source, original=source))

    def test_save_procedure_validation_is_reviewed(self):
        source = 'class Screen { private bool CallSaveProcedure() { if (count == 0) { ShowMessage("품목 없음"); return false; } return true; } }'
        self.assertIn('save_gate_review', self.codes(source, original=''))

    def test_success_notification_and_non_save_guards_are_not_save_gates(self):
        source = screen('Screen_SaveCommand', 'if (CallSaveProcedure()) { ShowMessage("완료"); }')
        source += screen('Screen_SearchCommand', 'if (value == null) { ShowMessage("선택"); return; }')
        self.assertNotIn('save_gate_review', self.codes(source, original=''))

    def test_manual_selected_row_deletion_is_reviewed(self):
        source = screen('Remove_Click', 'int[] rows = view.GetSelectedRows(); for (int i = rows.Length - 1; i >= 0; i--) { DataRow row = view.GetDataRow(rows[i]); if (row != null) { row.Delete(); } }')
        self.assertIn('manual_selected_row_delete', self.codes(source, original=screen('Remove_Click', '')))
        self.assertNotIn('manual_selected_row_delete', self.codes(screen('Remove_Click', 'view.DeleteSelectedRows();'), original=''))

    def test_unrelated_row_loop_is_not_classified_as_selected_grid_deletion(self):
        source = screen('Cleanup', 'foreach (DataRow row in table.Rows) { row.Delete(); }')
        self.assertNotIn('manual_selected_row_delete', self.codes(source, original=''))

    def test_client_sequence_calculation_is_reviewed_without_column_name_assumptions(self):
        source = screen('Add_Click', 'foreach (DataRow row in table.Rows) { DataRowVersion version = DataRowVersion.Original; count = Math.Max(count, Convert.ToInt32(row["SEQ", version])); }')
        self.assertIn('client_sequence_review', self.codes(source, original=screen('Add_Click', '')))
        self.assertNotIn('client_sequence_review', self.codes(screen('Resize', 'width = Math.Max(0, width);'), original=''))

    def test_context_and_header_copies_to_new_rows_are_reviewed(self):
        source = screen('Add_Click', 'DataRow row = table.NewRow(); row["TENANT"] = userInfo.Orgdiv; row["DOC"] = txtKey.Text; row["ITEM"] = selected["ITEM"]; table.Rows.Add(row);')
        issues = check_project_flow(source, original=screen('Add_Click', ''))
        self.assertEqual(2, sum(i.code == 'row_header_propagation_review' for i in issues))

    def test_existing_row_update_is_not_new_detail_field_propagation(self):
        source = screen('Edit_Click', 'DataRow row = view.GetFocusedDataRow(); row["KEY"] = txtKey.Text;')
        self.assertNotIn('row_header_propagation_review', self.codes(source, original=''))

    def test_source_proven_date_helper_is_preferred(self):
        source = screen('Screen_NewCommand', 'date.EditValue = DateTime.Today;')
        kwargs = {'control_types': {'date': 'Local.Controls.WorkDate'}, 'control_sources': [DATE_SOURCE]}
        self.assertIn('date_helper_review', self.codes(source, original='', **kwargs))
        self.assertNotIn('date_helper_review', self.codes(source, original=source, **kwargs))
        self.assertNotIn('date_helper_review', self.codes(screen('Screen_NewCommand', 'date.SetToDay(0);'), original='', **kwargs))

    def test_date_helper_is_not_invented_for_unsupplied_or_standard_controls(self):
        source = screen('Screen_NewCommand', 'date.EditValue = DateTime.Today;')
        self.assertNotIn('date_helper_review', self.codes(source, original='', control_types={'date': 'DateEdit'}))
        self.assertNotIn('date_helper_review', self.codes(source, original='', control_types={'date': 'Other.Date'}, control_sources=[DATE_SOURCE]))

    def test_existing_member_date_api_is_sufficient_evidence(self):
        before = screen('Screen_NewCommand', 'date.SetToDay(0);')
        after = screen('Screen_NewCommand', 'date.EditValue = DateTime.Today;')
        self.assertIn('date_helper_review', self.codes(after, original=before))

    def test_date_helper_inheritance_and_nested_type_boundaries(self):
        source = screen('Screen_NewCommand', 'date.EditValue = DateTime.Today;')
        derived = 'namespace Local.Controls { public class DerivedDate : WorkDate { } }'
        self.assertIn('date_helper_review', self.codes(source, original='', control_types={'date': 'Local.Controls.DerivedDate'}, control_sources=[DATE_SOURCE, derived]))
        nested = 'class OtherDate : DateEdit { class Inner { public void SetToDay(int d) { } } }'
        self.assertNotIn('date_helper_review', self.codes(source, original='', control_types={'date': 'OtherDate'}, control_sources=[nested]))

    def test_new_data_wrapper_is_reviewed_but_filling_an_existing_method_is_not(self):
        source = 'class Screen { private DataTable SelectedRows(GridView view) { DataTable selected = table.Clone(); foreach (int row in view.GetSelectedRows()) { selected.ImportRow(view.GetDataRow(row)); } return selected; } }'
        self.assertIn('new_ui_data_helper', self.codes(source, original='class Screen { }'))
        before = 'class Screen { private DataTable SelectedRows(GridView view) { return null; } }'
        self.assertNotIn('new_ui_data_helper', self.codes(source, original=before))
        self.assertNotIn('new_ui_data_helper', self.codes(source))

    def test_direct_event_implementation_and_unrelated_helper_are_not_data_wrappers(self):
        self.assertNotIn('new_ui_data_helper', self.codes(screen('Load_Click', 'grid.DataSource = CallSelectProcedure(SelectType.LIST);'), original=''))
        self.assertNotIn('new_ui_data_helper', self.codes('class X { private int Add(int a, int b) { return a + b; } }', original='class X {}'))

    def test_strings_comments_and_local_function_declarations_do_not_invent_entry_queries(self):
        source = screen('Screen_EditCommand', 'string sample = "CallSelectProcedure(SelectType.DETAIL)"; /* CallSelectProcedure(SelectType.DETAIL); */')
        self.assertNotIn('entry_query_review', self.codes(source, original=''))
        source = 'class X { void Outer() { void Fake_EditCommand() { CallSelectProcedure(SelectType.DETAIL); } } }'
        self.assertNotIn('entry_query_review', self.codes(source, original=''))

    def test_passed_static_checks_never_claim_full_project_style_verification(self):
        result = check_csharp(screen('Screen_EditCommand', 'mode = EDIT; Tab.SelectedTabPage = Page2;'))
        self.assertEqual('passed', result.status)
        self.assertEqual('static_checks_only', result.metadata['review_status'])
        self.assertFalse(result.metadata['project_style_verified'])

    def test_control_source_is_used_through_csharp_entrypoint(self):
        source = screen('Screen_NewCommand', 'date.EditValue = DateTime.Today;')
        designer = 'private Local.Controls.WorkDate date;'
        result = check_csharp(source, original='', designer=designer, control_sources=[DATE_SOURCE])
        self.assertIn('date_helper_review', {i.code for i in result.issues})


if __name__ == '__main__':
    unittest.main()
