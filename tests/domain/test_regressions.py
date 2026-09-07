"""Counterexamples found in the 3.0.0 practical evaluation and nearby boundaries."""
import copy
import unittest

from src.csharp.checks import check_csharp
from src.csharp.designer import check_designer
from src.csharp.designer_model import parse_designer_source
from src.pb.equivalence import compare_observations
from src.pb.source import parse_pb_export
from src.pb.sql import check_sp_call
from src.sql.pb_extract import extract_powerbuilder_sql_fragments


class EvaluationRegressions(unittest.TestCase):
    def test_local_where_method_is_not_linq(self):
        source = 'class Filter { void Where() { } void Run() { this.Where(); Where(); } }'
        self.assertNotIn('linq_preference', [i.code for i in check_csharp(source).issues])

    def test_local_where_does_not_hide_an_explicit_linq_call(self):
        source = 'class Filter { void Where() { } void Run() { Enumerable.Where(rows, x => true); } }'
        self.assertIn('linq_preference', [i.code for i in check_csharp(source).issues])

    def test_transaction_wrapper_name_does_not_prove_a_transaction_loss(self):
        source = '''class Screen {
void Save() { using (var tx = db.BeginTransaction()) { ExecuteWithTransaction("p", tx); tx.Commit(); } }
void ExecuteWithTransaction(string procedure, object transaction) { Execute(procedure, transaction); }
void Execute(string procedure, object transaction) { db.Run(procedure, transaction); }
}'''
        candidate = source.replace('ExecuteWithTransaction("p", tx)', 'Execute("p", tx)')
        result = check_csharp(candidate, original=source)
        self.assertTrue(result.success, result.to_dict())
        self.assertIn('transaction_call_change_review', [i.code for i in result.issues])

    def test_transaction_named_call_removal_remains_visible_for_review(self):
        result = check_csharp('void Save() { db.Execute("p"); }',
                              original='void Save() { db.ExecuteWithTransaction("p"); }')
        self.assertIn('transaction_call_change_review', [i.code for i in result.issues])
        self.assertTrue(any('transaction' in s.lower() for s in result.not_checked))

    def test_inline_designer_properties_are_compared(self):
        source = ('partial class Screen { private Button btn; void InitializeComponent() { '
                  'this.btn = new Button(); this.btn.Visible = false; '
                  'this.btn.Text = "보류"; this.btn.TabIndex = 0; } }')
        result = check_designer(source.replace('Visible = false', 'Visible = true'),
                                original=source, preserved_properties=['btn.Visible'])
        self.assertEqual('failed', result.status)
        self.assertIn('user_property_changed', [i.code for i in result.issues])
        model = parse_designer_source(source)
        self.assertEqual('"보류"', model.controls['btn'].properties['Text'])
        self.assertEqual(0, model.controls['btn'].tab_index)

    def test_semicolons_and_code_inside_literals_do_not_split_assignments(self):
        source = ('this.btn.Text = @"hello; this.fake.Visible = false;"; '
                  'this.btn.Size = new System.Drawing.Size(\n 80, 24); '
                  'this.Controls.Add(this.btn); this.Controls.SetChildIndex(this.btn, 0);')
        model = parse_designer_source(source)
        self.assertNotIn('fake', model.controls)
        self.assertEqual((80, 24), model.controls['btn'].size)
        self.assertEqual(1, len(model.controls_add))
        self.assertEqual(0, model.controls['btn'].child_index)

    def test_equivalent_literal_values_preserve_requested_text(self):
        for left, right in [
            ('"보류"', '@"보류"'),
            ('"\\u0041\\x42\\U0001F600"', '"AB😀"'),
            ('"\\uD83D\\uDE00"', '"😀"'),
            ('"a\\\\b\\\"c"', '@"a\\b""c"'),
            ('"보류"', '"""보류"""'),
            ('"a\\nb"', '"""\n    a\n    b\n    """'),
        ]:
            with self.subTest(left=left, right=right):
                result = check_designer('this.btn.Text = ' + right + ';',
                    original='this.btn.Text = ' + left + ';', preserved_properties=['btn.Text'])
                self.assertTrue(result.success, result.to_dict())

    def test_different_literal_runtime_values_are_not_normalized_together(self):
        for left, right in [('"a\\nb"', '@"a\\nb"'), ('"a b"', '"ab"'),
                            ('"a"', '$"{a}"')]:
            with self.subTest(left=left, right=right):
                self.assertFalse(check_designer('this.btn.Text = ' + right + ';',
                    original='this.btn.Text = ' + left + ';', preserved_properties=['btn.Text']).success)

    def test_globally_and_alias_qualified_parameter_constructors(self):
        for type_name in ['global::Company.Data.DbParameter', 'Data::DbParameter',
                          'global::System.Data.SqlClient.SqlParameter']:
            with self.subTest(type_name=type_name):
                result = check_sp_call('new ' + type_name + '("\\u004BEY", 1)',
                                       'CREATE PROC dbo.Save @KEY int AS SELECT @KEY;')
                self.assertTrue(result.success, result.to_dict())

    def test_parameter_expression_prefix_is_not_a_constant_name(self):
        result = check_sp_call('new DbParameter("KEY" + suffix, 1)',
                              'CREATE PROC dbo.Save @KEY int AS SELECT @KEY;')
        self.assertFalse(result.success)
        self.assertEqual('incomplete', result.status)
        self.assertNotIn('@KEY', result.metadata.get('passed_parameters', []))

    def test_pb_qualified_literal_dataobject_binding(self):
        source = ('event open;\ndw_list.DataObject = "d_dispatch"\n'
                  '// dw_list.DataObject = "d_comment"\n'
                  'ls_example = ~"ignored~"\nend event')
        self.assertEqual(['d_dispatch'], parse_pb_export(source).dataobjects)

    def test_pb_dataobject_lookalike_inside_string_is_not_a_binding(self):
        source = "ls_example = 'dw_list.DataObject = ~" + '"d_fake~"' + "'\n"
        self.assertEqual([], parse_pb_export(source).dataobjects)

    def test_pb_dataobject_comparison_is_not_a_binding(self):
        parsed = parse_pb_export('IF dw_list.DataObject = "d_other" THEN\ndw_list.DataObject = ls_name\nEND IF')
        self.assertEqual([], parsed.dataobjects)
        self.assertEqual(1, len(parsed.unresolved_dataobjects))

    def test_sql_looking_value_inside_sql_is_not_a_second_query(self):
        fragments = extract_powerbuilder_sql_fragments("SELECT 'SELECT * FROM sample' INTO :text FROM orders;")
        self.assertEqual(1, len(fragments))

    def test_two_queries_on_one_line_have_distinct_provenance(self):
        fragments = extract_powerbuilder_sql_fragments('SELECT id FROM orders; SELECT id FROM archive;')
        self.assertEqual(2, len(fragments))
        self.assertEqual(2, len({item['fragment_id'] for item in fragments}))

    def test_datawindow_retrieve_value_is_sql_without_dw_tail(self):
        source = ('table(column=(type=char(10) name=id)\n'
                  ' retrieve="SELECT id FROM orders WHERE note = ~\'한글~\'"\n'
                  ' arguments=(("as_id", string)))\ncolumn(name=id x="4")')
        fragments = extract_powerbuilder_sql_fragments(source, source_name='d_orders.srd')
        self.assertEqual(1, len(fragments))
        self.assertEqual("SELECT id FROM orders WHERE note = '한글'", fragments[0]['sql_text'])
        self.assertEqual('datawindow_retrieve', fragments[0]['extraction_kind'])
        self.assertTrue(fragments[0]['complete'])
        self.assertEqual((2, 2), (fragments[0]['start_line'], fragments[0]['end_line']))

    def test_pb_embedded_sql_excludes_comments_and_preserves_string_semicolons(self):
        source = ('// SELECT fake FROM phantom;\n'
                  "SELECT id INTO :ll_id FROM orders WHERE note = ';' USING SQLCA;\n"
                  'MessageBox("SELECT", "button")')
        fragments = extract_powerbuilder_sql_fragments(source)
        self.assertEqual(1, len(fragments))
        self.assertTrue(fragments[0]['complete'])
        self.assertTrue(fragments[0]['sql_text'].endswith('USING SQLCA;'))

    def test_pb_unterminated_query_is_not_reported_as_complete(self):
        fragments = extract_powerbuilder_sql_fragments('SELECT id\nFROM orders\nWHERE id = :id',
                                                        max_lines_per_fragment=2)
        self.assertEqual(1, len(fragments))
        self.assertIs(False, fragments[0]['complete'])


class MeasurementBoundaryRegressions(unittest.TestCase):
    def setUp(self):
        self.baseline = {'parameters': {'P': 1}, 'database': 'fixture',
                         'schema': ['ID', 'VALUE'], 'ordered': False,
                         'rows': [[1, None], [1, None], [2, 'x']], 'elapsed_ms': [5, 6, 7]}

    def test_bool_and_int_parameter_contexts_are_distinct(self):
        candidate = copy.deepcopy(self.baseline)
        candidate['parameters'] = {'P': True}
        result = compare_observations(self.baseline, candidate)
        self.assertIn('measurement_context_differs', [i.code for i in result.issues])
        self.assertEqual('failed', result.status)

    def test_nested_bool_and_number_contexts_are_distinct(self):
        self.baseline['parameters'] = {'P': [{'values': [1]}]}
        candidate = copy.deepcopy(self.baseline)
        candidate['parameters']['P'][0]['values'][0] = True
        self.assertEqual('failed', compare_observations(self.baseline, candidate).status)

    def test_malformed_external_values_return_structured_results(self):
        invalid = [('ordered', 1), ('parameters', [1]), ('database', None),
                   ('schema', 'ID'), ('rows', None), ('rows', [[object()]]),
                   ('parameters', {1: 'invalid key'}), ('rows', [[float('nan')]])]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                candidate = copy.deepcopy(self.baseline)
                candidate[field] = value
                result = compare_observations(self.baseline, candidate)
                self.assertEqual('incomplete', result.status, result.to_dict())
                result.to_json()

    def test_non_object_observation_is_structured(self):
        result = compare_observations([], self.baseline)
        self.assertEqual('incomplete', result.status)

    def test_cycles_and_extreme_timing_inputs_do_not_crash(self):
        cycle = []
        cycle.append(cycle)
        candidate = copy.deepcopy(self.baseline)
        candidate['rows'] = cycle
        self.assertEqual('incomplete', compare_observations(self.baseline, candidate).status)
        candidate = copy.deepcopy(self.baseline)
        candidate['elapsed_ms'] = [10 ** 400]
        self.assertEqual('incomplete', compare_observations(self.baseline, candidate).status)

    def test_bool_timing_is_not_a_numeric_sample(self):
        candidate = copy.deepcopy(self.baseline)
        candidate['elapsed_ms'] = [True]
        result = compare_observations(self.baseline, candidate)
        self.assertEqual('incomplete', result.status)
        self.assertNotIn('observed_speed_ratio', result.metadata)

    def test_duplicate_rows_and_required_order_remain_significant(self):
        candidate = copy.deepcopy(self.baseline)
        candidate['rows'].reverse()
        self.assertTrue(compare_observations(self.baseline, candidate).success)
        self.baseline['ordered'] = candidate['ordered'] = True
        self.assertFalse(compare_observations(self.baseline, candidate).success)
        candidate = copy.deepcopy(self.baseline)
        candidate['rows'].pop(0)
        self.assertFalse(compare_observations(self.baseline, candidate).success)


if __name__ == '__main__':
    unittest.main()
