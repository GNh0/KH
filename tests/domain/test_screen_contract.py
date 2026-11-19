"""Regression cases for the joins between caller, XML argument, mode, grid and result."""
import unittest

from src.csharp.screen_contract import check_screen_contract


CALLER = '''
class Form {
    enum Choice { List, Detail }
    DataSet Query(Choice choice) {
        return db.GetDataSetFromSP("dbo.Fetch", new DbParameter("@action", choice.ToString()));
    }
    void Load() {
        var ds = Query(Choice.Detail);
        grid.DataSource = ds.Tables[1];
    }
    void Save() {
        rows.TableName = "Line";
        var xml = Lib.DataTableToXml(rows);
        var key = new DbParameter("@key", input);
        db.ExecSPTrn("Store", new DbParameter("@doc", xml), key);
    }
}
'''
DESIGNER = '''
partial class Form {
    GridControl grid;
    GridView view;
    GridColumn col;
    void InitializeComponent() {
        this.grid = new GridControl();
        this.view = new GridView();
        this.col = new GridColumn();
        this.grid.MainView = this.view;
        this.view.Columns.AddRange(new GridColumn[] {this.col});
        this.col.FieldName = "Target";
    }
}
'''
FETCH = """
CREATE PROC dbo.Fetch @action varchar(9) AS
BEGIN
 IF @action = 'List'
 BEGIN
    SELECT A.Target FROM A
 END
 ELSE IF @action = 'Detail'
 BEGIN
    SELECT A.Other FROM A
    SELECT Target = B.Id FROM B
 END
END
"""
STORE = """
CREATE PROC dbo.Store @key int, @doc xml AS
BEGIN
 EXEC sp_xml_preparedocument @h OUTPUT, @doc
 SELECT A.Id FROM OPENXML(@h, '/ROOT/Line', 1) WITH (Id int) A
END
"""


class ScreenContractTests(unittest.TestCase):
    def check(self, caller=CALLER, designer=DESIGNER, fetch=FETCH, store=STORE):
        return check_screen_contract(caller, designer, {'fetch': fetch, 'store': store})

    def test_matches_actual_result_and_xml_parameter(self):
        result = self.check()
        self.assertEqual([i.code for i in result.issues], ['serializer_root_unverified'])
        self.assertEqual(result.status, 'incomplete')
        grid = result.metadata['grid_bindings'][0]
        self.assertEqual((grid['result_index'], grid['modes'], grid['projection']), (1, {'@ACTION': ['Detail']}, ['TARGET']))
        self.assertEqual(result.metadata['calls'][1]['parameters'], ['@DOC', '@KEY'])

    def test_modes_are_literal_and_grid_field_must_belong_to_this_result(self):
        for changed, issue in [
                (FETCH.replace("'Detail'", "'Other'"), 'sp_mode_missing'),
                (FETCH.replace('Target = B.Id', 'B.Different'), 'grid_result_field_missing')]:
            with self.subTest(issue=issue):
                self.assertIn(issue, [i.code for i in self.check(fetch=changed).issues])
        result = self.check(caller=CALLER.replace('ds.Tables[1]', 'ds.Tables[0]'))
        self.assertIn('grid_result_field_missing', [i.code for i in result.issues])
        result = self.check(caller=CALLER.replace('ds.Tables[1]', 'ds.Tables[2]'))
        self.assertIn('grid_result_index_missing', [i.code for i in result.issues])

    def test_each_transport_uses_only_its_own_arguments(self):
        caller = '''class F { void M() {
            var a = new DbParameter("@first", 1);
            var b = new[] {new DbParameter("@second", 2)};
            db.ExecSPTrn("P", a); db.ExecSPTrn("P", b);
        } }'''
        result = check_screen_contract(caller, '', {'P': 'CREATE PROC P @first int, @second int AS SELECT 1 AS N'})
        missing = [i.details['parameter'] for i in result.issues if i.code == 'required_sp_parameter_missing']
        self.assertEqual(missing, ['@SECOND', '@FIRST'])
        self.assertEqual([c['parameters'] for c in result.metadata['calls']], [['@FIRST'], ['@SECOND']])
        bad = self.check(caller=CALLER.replace('new DbParameter("@doc"', 'new DbParameter("@typo"'))
        codes = [i.code for i in bad.issues]
        self.assertIn('unexpected_sp_parameter', codes)
        self.assertIn('required_sp_parameter_missing', codes)

    def test_missing_targets_and_dynamic_shapes_cannot_pass(self):
        cases = [
            (CALLER.replace('"Store"', 'spName'), FETCH, 'procedure_target_unresolved'),
            (CALLER.replace('new DbParameter("@action", choice.ToString())', 'CreateArgs(choice)'), FETCH, 'call_arguments_unresolved'),
            (CALLER.replace('Query(Choice.Detail)', 'Query(ResolveChoice())'), FETCH, 'mode_value_unresolved'),
            (CALLER.replace('ds.Tables[1]', 'ds.Tables[index]'), FETCH, 'grid_source_unresolved'),
            (CALLER, FETCH.replace('Target = B.Id', 'B.*'), 'grid_projection_unresolved'),
        ]
        for caller, sql, code in cases:
            with self.subTest(code=code):
                result = self.check(caller=caller, fetch=sql)
                self.assertEqual(result.status, 'incomplete')
                self.assertIn(code, [i.code for i in result.issues])

    def test_xml_path_uses_the_handle_for_this_actual_parameter(self):
        wrong = self.check(store=STORE.replace('/ROOT/Line', '/ROOT/Other'))
        self.assertIn('xml_row_name_mismatch', [i.code for i in wrong.issues])
        dynamic = self.check(store=STORE.replace("'/ROOT/Line'", '@xpath'))
        self.assertIn('openxml_path_unresolved', [i.code for i in dynamic.issues])
        self.assertNotIn('xml_row_name_mismatch', [i.code for i in dynamic.issues])
        removed = self.check(store=STORE.replace('SELECT A.Id', 'EXEC sp_xml_removedocument @h; SELECT A.Id'))
        self.assertIn('openxml_path_unresolved', [i.code for i in removed.issues])

    def test_xml_handle_survives_nested_blocks_but_not_their_exit(self):
        # The common SAVE shape prepares once, then reads inside mode/TRY blocks.
        guarded = STORE.replace(" SELECT A.Id", " IF @key > 0\n BEGIN TRY\n  BEGIN TRAN\n  SELECT CASE WHEN 1 = 1 THEN 1 END,\n A.Id").replace(
            "WITH (Id int) A\n", "WITH (Id int) A\n  COMMIT TRAN\n END TRY\n BEGIN CATCH\n  ROLLBACK TRAN\n END CATCH\n")
        self.assertNotIn('openxml_path_unresolved', [i.code for i in self.check(store=guarded).issues])
        wrong = self.check(store=guarded.replace('/ROOT/Line', '/ROOT/Other'))
        self.assertIn('xml_row_name_mismatch', [i.code for i in wrong.issues])
        # A handle prepared only inside an earlier block is not established afterwards.
        scoped = STORE.replace(' EXEC sp_xml_preparedocument @h OUTPUT, @doc\n',
                               ' IF @key > 0\n BEGIN\n  EXEC sp_xml_preparedocument @h OUTPUT, @doc\n END\n')
        self.assertIn('openxml_path_unresolved', [i.code for i in self.check(store=scoped).issues])
        # Removal inside a block also invalidates the enclosing handle.
        removed = STORE.replace(' SELECT A.Id', ' IF @key > 0\n BEGIN\n  EXEC sp_xml_removedocument @h\n END\n SELECT A.Id')
        self.assertIn('openxml_path_unresolved', [i.code for i in self.check(store=removed).issues])

    def test_literals_comments_and_unrelated_helpers_are_not_calls(self):
        caller = CALLER.replace('var ds = Query(Choice.Detail);', '''
            // db.ExecSP("Other", new DbParameter("@junk", 1));
            var s = @"db.ExecSP(""Other"")";
            other.Query(Choice.List);
            var ds = Query(Choice.Detail);''')
        result = self.check(caller=caller)
        self.assertEqual([i.code for i in result.issues], ['serializer_root_unverified'])
        self.assertEqual(result.metadata['calls'][0]['modes']['@ACTION']['observed'], ['Detail'])

    def test_explicit_serializer_verifies_root_and_returned_row(self):
        serializer = '''class Lib {
            static string DataTableToXml(DataTable t) {
                var doc = new XmlDocument(); var root = doc.CreateElement("ROOT");
                doc.AppendChild(root); var row = doc.CreateElement(t.TableName);
                root.AppendChild(row); return doc.OuterXml;
            }
        }'''
        for xpath, code in [('/ROOT/Line', None), ('/OTHER/Line', 'xml_root_mismatch')]:
            result = check_screen_contract(CALLER, DESIGNER, {'s': FETCH, 'w': STORE.replace('/ROOT/Line', xpath)},
                                           serializer=serializer)
            self.assertEqual([i.code for i in result.issues], [code] if code else [])
        unrelated = serializer.replace('return doc.OuterXml;', 'return somethingElse;')
        self.assertIn('serializer_root_unverified', [i.code for i in check_screen_contract(CALLER, DESIGNER,
            {'s': FETCH, 'w': STORE}, serializer=unrelated).issues])

    def test_applied_stop_compares_actual_pair_and_a_repair(self):
        from tests.domain.test_hook_applications import ApplicationTests
        fixture = ApplicationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        cs = fixture.project / 'Form.cs'
        sql = fixture.project / 'Query.sql'
        other = fixture.project / 'Other.sql'
        cs.write_text('class F { void Save() { db.ExecSPTrn("P", new DbParameter("@key", id)); db.ExecSP("Other"); } }', encoding='utf-8')
        baseline = 'CREATE PROC P @key int AS SELECT @key AS VALUE'
        sql.write_text(baseline, encoding='utf-8')
        other.write_text('CREATE PROC Other AS SELECT 1 AS VALUE', encoding='utf-8')
        fixture.read('csharp-designer-style-harness/SKILL.md')
        fixture.read('sql-formatting/SKILL.md')
        fixture.load_required(fixture.apply(['csharp-code'], [cs]))
        fixture.load_required(fixture.apply(['sql-query'], [sql]))
        for text, broken in [(baseline.replace('@key', '@changed'), True), (baseline, False)]:
            fixture.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(sql), 'content': text})
            sql.write_text(text, encoding='utf-8')
            fixture.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(sql)}, tool_response=text)
            fixture.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(sql)}, tool_response=text)
            output = fixture.event('Stop')
            reports = fixture.state().get('last_screen_contract_checks', [])
            if broken:
                self.assertEqual(output.get('decision'), 'block')
                self.assertIn('unexpected_sp_parameter', output['reason'])
                self.assertEqual(reports[0]['definitions'], [str(sql)])
                self.assertIn('procedure_target_unresolved', reports[0]['unresolved'])
            else:
                self.assertFalse([e for r in reports for e in r['new_errors']])
                self.assertNotIn('unexpected_sp_parameter', output.get('reason', ''))

    def test_stale_procedure_is_reviewed_for_its_own_call_and_a_resolved_replacement_is_accepted(self):
        from src.runtime.screen_contract import _lost_call_targets
        def calls(second):
            source = 'class F { void Normal() { db.ExecSP("P"); } void Retry() { db.ExecSP("' + second + '"); } }'
            options = {'P.sql': 'CREATE PROC P AS SELECT 1 AS V', 'Q.sql': 'CREATE PROC Q AS SELECT 1 AS V'}
            return check_screen_contract(source, None, options).metadata['calls']
        self.assertEqual([], _lost_call_targets(calls('P'), calls('Q')))
        self.assertEqual(1, len(_lost_call_targets(calls('P'), calls('Typo'))))
