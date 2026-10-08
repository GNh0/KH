import unittest

from src.csharp.checks import check_csharp
from src.csharp.save_contract import check_save_contract, check_select_contract


XML_SAVE = '''bool CallSaveProcedure() {
    DataTable dt = grdList.DataSource as DataTable;
    foreach (DataRow dr in dt.Select("CHK = 'Y'")) {
        if (dr.RowState == DataRowState.Unchanged) { dr.SetModified(); }
    }
    dt.TableName = "ROWS";
    string xml = DataUtil.DataTableToXml(dt, DataRowState.Modified);
    dbClient.ExecSPTrn("sp_SAVE", new DbParameter("@XML", xml));
    return true;
}'''
BATCH = '''class Screen {
    void Screen_PrintCommand(object s, PrintCommandEventArgs e) {
        PrintSelectedPages();
        if (CallSaveProcedure()) { CallCommand(BizCommand.Search); }
    }
''' + XML_SAVE + '\n}'
ROWWISE = '''class Screen {
    void Screen_PrintCommand(object s, PrintCommandEventArgs e) {
        foreach (DataRow dr in drSelected) {
            using (Report rpt = new Report(GetPrintData(dr))) { rpt.Print(); }
            if (CallSaveProcedure(dr) == false) { return; }
        }
    }
    bool CallSaveProcedure(DataRow dr) {
        DbParameter stamp = new DbParameter("@PRINTDATE", DBNull.Value,
                                             DbType.Date, ParameterDirection.Output);
        dbClient.ExecSPTrn("sp_SAVE", new DbParameter("@IDX", dr["IDX"]), stamp);
        dr["PRINTDATE"] = stamp.Value;
        return true;
    }
}'''
SCALAR_SELECT = '''DataSet CallSelectProcedure(SelectType type, int? idx = null) {
    return db.GetDataSetFromSP("sp_SELECT", new DbParameter("@IDX", idx));
}'''
XML_SELECT = '''DataSet CallSelectProcedure(SelectType type) {
    string xml = null;
    if (type == SelectType.PRINT) {
        DataTable dt = grdList.DataSource as DataTable;
        dt.TableName = "ROWS";
        xml = DataUtil.DataTableToXml(dt, DataRowState.Unchanged | DataRowState.Modified);
    }
    return db.GetDataSetFromSP("sp_SELECT", new DbParameter("@XML", xml));
}'''


def codes(result):
    return {issue.code for issue in result.issues}


class SaveContractTests(unittest.TestCase):
    def test_reported_scalar_output_rowwise_failure_is_detected(self):
        result = check_save_contract(ROWWISE, style_reference=BATCH)
        self.assertEqual({'save_xml_contract_drift_review', 'save_output_contract_drift_review',
                          'rowwise_save_contract_drift_review'}, codes(result))
        loop = next(issue for issue in result.issues if issue.code == 'rowwise_save_contract_drift_review')
        self.assertIn('CallSaveProcedure(dr)', ROWWISE.splitlines()[loop.line - 1])
        self.assertEqual(1, result.metadata['save_contract_comparison']['candidate_loop_save_calls'])

    def test_selected_states_then_one_xml_save_is_preserved(self):
        result = check_save_contract(BATCH, style_reference=BATCH)
        self.assertEqual([], result.issues)
        self.assertTrue(result.metadata['save_contract_comparison']['compared'])
        self.assertTrue(result.metadata['save_contract_comparison']['reference_xml'])

    def test_check_csharp_exposes_review_not_project_verification(self):
        result = check_csharp(ROWWISE, style_reference_csharp=BATCH, screen_commands=['print'])
        self.assertIn('save_xml_contract_drift_review', codes(result))
        self.assertEqual('needs_review', result.metadata['review_status'])
        self.assertFalse(result.metadata['project_style_verified'])
        self.assertEqual('passed', result.status)

    def test_existing_rowwise_and_output_contract_is_not_globally_banned(self):
        reference = ROWWISE.replace('return true;',
            'string xml = DataUtil.DataTableToXml(dt, DataRowState.Modified); return true;')
        candidate = reference.replace('GetPrintData(dr)', 'GetOtherPrintData(dr)')
        self.assertEqual([], check_save_contract(candidate, style_reference=reference).issues)

    def test_scalar_reference_does_not_require_xml_or_batch_saves(self):
        self.assertEqual([], check_save_contract(ROWWISE, style_reference=ROWWISE).issues)

    def test_output_addition_requires_review_even_with_xml(self):
        candidate = BATCH.replace('return true;',
            'var key = new DbParameter("@KEY", 0, DbType.Int32, ParameterDirection.InputOutput); return true;')
        self.assertEqual({'save_output_contract_drift_review'},
                         codes(check_save_contract(candidate, style_reference=BATCH)))

    def test_unchanged_source_is_skipped_but_new_helper_transport_is_reviewed(self):
        self.assertEqual([], check_save_contract(ROWWISE, original=ROWWISE, style_reference=BATCH).issues)
        candidate = BATCH.replace('DataUtil.DataTableToXml(dt, DataRowState.Modified)', 'GetXmlIndirectly(dt)')
        self.assertEqual({'save_xml_contract_drift_review'},
                         codes(check_save_contract(candidate, original=BATCH, style_reference=BATCH)))

    def test_new_loop_is_detected_even_when_save_helper_is_unchanged(self):
        candidate = BATCH.replace('PrintSelectedPages();',
            'foreach (DataRow dr in rows) { CallSaveProcedure(); } PrintSelectedPages();')
        self.assertEqual({'rowwise_save_contract_drift_review'},
                         codes(check_save_contract(candidate, original=BATCH, style_reference=BATCH)))

    def test_comments_strings_and_uncalled_local_functions_are_excluded(self):
        candidate = BATCH.replace('PrintSelectedPages();', '''
            string sample = "foreach (var row in rows) { CallSaveProcedure(); }";
            // while (true) { CallSaveProcedure(); }
            void Deferred() { foreach (var row in rows) { CallSaveProcedure(); } }
            PrintSelectedPages();''').replace('return true;',
            '/* ParameterDirection.Output */ return true;')
        self.assertEqual([], check_save_contract(candidate, style_reference=BATCH).issues)

    def test_foreign_receiver_is_not_a_local_save_call(self):
        candidate = BATCH.replace('PrintSelectedPages();',
            'foreach (var row in rows) { other.CallSaveProcedure(row); } PrintSelectedPages();')
        self.assertEqual([], check_save_contract(candidate, style_reference=BATCH).issues)

    def test_nested_unbraced_and_loop_condition_calls_are_detected_once(self):
        loops = ('foreach (var row in rows) if (ok) this.CallSaveProcedure();',
                 'for (int i = 0; i < rows.Count; i++) { while (ok) { base.CallSaveProcedure(); } }',
                 'while (CallSaveProcedure()) { Next(); }',
                 'do { CallSaveProcedure(); } while (ok);')
        for loop in loops:
            with self.subTest(loop=loop):
                candidate = BATCH.replace('PrintSelectedPages();', loop)
                result = check_save_contract(candidate, style_reference=BATCH)
                self.assertEqual(['rowwise_save_contract_drift_review'], [issue.code for issue in result.issues])

    def test_save_outside_loop_is_not_mistaken_for_rowwise(self):
        candidate = BATCH.replace('PrintSelectedPages();',
            'foreach (var row in rows) { PrintOne(row); }')
        self.assertEqual([], check_save_contract(candidate, style_reference=BATCH).issues)

    def test_missing_ambiguous_expression_bodied_sources_remain_unverified(self):
        for reference in (None, 'class Empty {}', BATCH + BATCH,
                          'class Screen { bool CallSaveProcedure() => SaveXml(); }'):
            with self.subTest(reference=reference):
                result = check_save_contract(ROWWISE, style_reference=reference)
                self.assertEqual([], result.issues)
                self.assertFalse(result.metadata['save_contract_comparison']['compared'])
                self.assertTrue(any('save transport comparison' in item for item in result.not_checked))
        result = check_save_contract('class Empty {}', style_reference=BATCH)
        self.assertFalse(result.metadata['save_contract_comparison']['compared'])


class SelectContractTests(unittest.TestCase):
    def test_save_xml_does_not_authorize_select_xml(self):
        reference = 'class Screen {' + SCALAR_SELECT + XML_SAVE + '}'
        candidate = 'class Screen {' + XML_SELECT + XML_SAVE + '}'
        result = check_csharp(candidate, style_reference_csharp=reference)
        self.assertIn('select_xml_contract_drift_review', codes(result))
        self.assertNotIn('save_xml_contract_drift_review', codes(result))
        self.assertTrue(result.metadata['select_contract_comparison']['compared'])
        self.assertTrue(result.metadata['save_contract_comparison']['compared'])

    def test_scalar_select_and_batch_xml_save_are_independent(self):
        source = 'class Screen {' + SCALAR_SELECT + XML_SAVE + '}'
        self.assertEqual([], check_select_contract(source, style_reference=source).issues)

    def test_existing_xml_query_is_not_globally_prohibited(self):
        candidate = XML_SELECT.replace('"sp_SELECT"', '"sp_OTHER_SELECT"')
        self.assertEqual([], check_select_contract(candidate, style_reference=XML_SELECT).issues)

    def test_unchanged_query_is_skipped_only_in_differential_review(self):
        result = check_select_contract(XML_SELECT, original=XML_SELECT, style_reference=SCALAR_SELECT)
        self.assertEqual([], result.issues)
        self.assertTrue(result.metadata['select_contract_comparison']['unchanged_body_skipped'])
        self.assertEqual({'select_xml_contract_drift_review'},
                         codes(check_select_contract(XML_SELECT, style_reference=SCALAR_SELECT)))

    def test_comments_strings_and_uncalled_locals_do_not_add_serialization(self):
        candidate = SCALAR_SELECT.replace('return db.', '''
            string sample = "DataUtil.DataTableToXml(dt, DataRowState.Modified)";
            // DataUtil.DataTableToXml(dt, DataRowState.Modified);
            void Deferred() { DataUtil.DataTableToXml(dt, DataRowState.Modified); }
            return db.''')
        self.assertEqual([], check_select_contract(candidate, style_reference=SCALAR_SELECT).issues)

    def test_missing_ambiguous_or_expression_bodied_query_stays_unverified(self):
        for reference in (None, XML_SAVE, SCALAR_SELECT + SCALAR_SELECT,
                          'DataSet CallSelectProcedure() => Query();'):
            with self.subTest(reference=reference):
                result = check_select_contract(XML_SELECT, style_reference=reference)
                self.assertEqual([], result.issues)
                self.assertFalse(result.metadata['select_contract_comparison']['compared'])

    def test_query_comparison_does_not_require_a_save_body(self):
        result = check_select_contract(XML_SELECT, style_reference=SCALAR_SELECT)
        self.assertEqual({'select_xml_contract_drift_review'}, codes(result))


if __name__ == '__main__':
    unittest.main()
