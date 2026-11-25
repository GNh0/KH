import copy
import tempfile
import unittest
from pathlib import Path
from src.pb.source import parse_pb_export
from src.pb.checks import check_pb_export
from src.pb.events import check_event_mapping, compare_state_graphs
from src.pb.datawindow import extract_datawindow_column_specs, generate_devexpress_grid_xml, verify_devexpress_grid_xml_contract, build_csharp_grid_column_designer_plan
from src.pb.layout import build_detail_form_layout_plan
from src.pb.keys import build_composite_business_key_display_plan, verify_composite_business_key_display_contract
from src.pb.sql import procedure_parameters, check_sp_call, review_save_delta
from src.pb.equivalence import compare_observations
from src.pb.designer import check_field_lineage
from src.pb.preflight import inspect_project
from src.pb.planning import build_migration_plan


PB = '''global type w_orders from w_base
end type
event open;
this.dw_1.retrieve(gs_company)
end event
event ue_save;
IF this.dw_1.accepttext() <> 1 THEN RETURN
end event
type dw_1 from datawindow within w_orders
dataobject = "d_orders"
end type
'''
DW = '''release 7;
datawindow(units=0)
table(column=(type=char(20) name=itemcd dbname="stock.itemcd")
 column=(type=decimal(2) name=qty dbname="stock.qty"))
text(band=header name=itemcd_t text="품목" x="5" y="2" width="100" height="16")
column(band=detail name=itemcd x="5" y="20" width="100" height="16")
column(band=detail name=qty x="110" y="20" width="80" height="16")
'''


class PBTests(unittest.TestCase):
    def test_export_inventory_tracks_parent_event_and_linked_datawindow(self):
        parsed = parse_pb_export(PB)
        self.assertEqual('w_base', parsed.objects[0]['parent'])
        self.assertEqual(['open', 'ue_save'], [x['name'] for x in parsed.events])
        self.assertEqual(['d_orders'], parsed.dataobjects)
        self.assertIn('gs_company', parsed.events[0]['body'])
        self.assertTrue(any('linked DataWindow' in item for item in check_pb_export(PB).not_checked))

    def test_comments_and_prototypes_do_not_create_executable_events(self):
        text = 'event ue_fake();\n// event ue_comment;\n/* event ue_other;\nend event */\n' + PB
        self.assertEqual(['open', 'ue_save'], [x['name'] for x in parse_pb_export(text).events])

    def test_unknown_text_is_incomplete_not_full_pbl_analysis(self):
        self.assertEqual('incomplete', check_pb_export('supplied behavior only').status)
        self.assertEqual('failed', check_pb_export('').status)

    def test_event_mapping_reports_omitted_save(self):
        cs = 'class Screen { private void FormOpen() { } }'
        result = check_event_mapping(PB, cs, [{'pb_event': 'open', 'csharp_handler': 'FormOpen'}])
        self.assertIn('pb_event_omitted', [i.code for i in result.issues])
        result = check_event_mapping(PB, cs, [{'pb_event': 'open', 'csharp_handler': 'FormOpen'}], excluded_events=['ue_save'])
        self.assertTrue(result.success)

    def test_comment_only_handler_does_not_cover_event(self):
        result = check_event_mapping(PB, '// private void FormOpen() {}', [{'pb_event': 'open', 'csharp_handler': 'FormOpen'}], excluded_events=['ue_save'])
        self.assertIn('mapped_handler_missing', [x.code for x in result.issues])

    def test_lifecycle_and_same_named_control_events_are_not_collapsed(self):
        source = 'on w_test.create\nthis.cb_1 = create cb_1\nend on\nevent cb_1::clicked;\ncall_one()\nend event\nevent cb_2::clicked;\ncall_two()\nend event'
        self.assertEqual(3, len(parse_pb_export(source).events))
        result = check_event_mapping(source, 'class Form { void Click() {} }', [{'pb_event':'cb_1::clicked','csharp_handler':'Click'}], excluded_events=['w_test::create'])
        self.assertIn('cb_2::clicked', [i.details.get('event') for i in result.issues if i.code=='pb_event_omitted'])

    def test_designer_extraction_shares_literal_and_property_parsing(self):
        from src.pb.layout import extract_csharp_designer_control_specs
        text = 'string example = """\nthis.fake = new Button();\n""";\nthis.colA = new GridColumn();\nthis.colA.FieldName = @"주문번호";\nthis.colA.Visible = false;'
        result = extract_csharp_designer_control_specs(text)
        self.assertTrue(result.success)
        controls = {x['name']: x for x in result.metadata['controls']}
        self.assertNotIn('fake', controls)
        self.assertEqual('주문번호', controls['colA']['field_name'])
        self.assertIs(False, controls['colA']['properties']['Visible'])

    def test_graph_effect_order_is_preserved(self):
        left = {'nodes': ['dirty', 'saved'], 'edges': [{'from': 'dirty', 'to': 'saved', 'effects': ['validate', 'save', 'reload']}]}
        right = copy.deepcopy(left)
        right['edges'][0]['effects'] = ['save', 'validate', 'reload']
        self.assertFalse(compare_state_graphs(left, right).success)

    def test_datawindow_column_order_caption_type_and_xml(self):
        specs = extract_datawindow_column_specs(DW)
        self.assertEqual(['ITEMCD', 'QTY'], [s.field_name for s in specs])
        self.assertEqual('품목', specs[0].caption)
        self.assertEqual('decimal(2)', specs[1].data_type)
        xml = generate_devexpress_grid_xml(specs)
        result = verify_devexpress_grid_xml_contract(xml, expected_columns=specs)
        self.assertTrue(result.success, result.metadata)
        broken = xml.replace('>QTY<', '>MISSING<')
        self.assertFalse(verify_devexpress_grid_xml_contract(broken, expected_columns=specs).success)

    def test_explicit_target_grid_names_override_defaults(self):
        result = build_csharp_grid_column_designer_plan([{'field_name': 'QTY', 'data_type': 'decimal(2)', 'csharp_name': 'colQuantity'}], grid_view_name='gvwOrders', result_fields=['QTY'])
        self.assertTrue(result.success, result.metadata)
        code = result.stdout
        self.assertIn('colQuantity', code)
        self.assertIn('gvwOrders', code)
        self.assertIn('RepositoryItemSpinEdit', code)
        self.assertIn('RepositoryItems.AddRange', code)

    def test_duplicate_grid_members_are_errors(self):
        result = build_csharp_grid_column_designer_plan([{'field_name': 'A', 'csharp_name': 'colSame'}, {'field_name': 'B', 'csharp_name': 'colSame'}])
        self.assertFalse(result.success)

    def test_current_designer_properties_override_new_template_values(self):
        result = build_csharp_grid_column_designer_plan(['QTY'], column_properties={'QTY': {'Visible': 'false', 'AppearanceCell.Font': 'new System.Drawing.Font("Malgun Gothic", 10F)'}})
        self.assertTrue(result.success)
        self.assertIn('this.colList_QTY.Visible = false;', result.stdout)
        self.assertNotIn('this.colList_QTY.Visible = true;', result.stdout)
        self.assertIn('Font("Malgun Gothic", 10F)', result.stdout)

    def test_detail_explicit_member_and_binding_are_used_without_receipt(self):
        result = build_detail_form_layout_plan([{'field_name': 'ITEMCD', 'csharp_editor_name': 'txtPart', 'csharp_label_name': 'lblPart', 'editor_type': 'TextEdit'}], binding_map={'ITEMCD': {'binding_property': 'BindingField'}}, result_fields=['ITEMCD'])
        self.assertTrue(result.success, result.metadata)
        field = result.metadata['fields'][0]
        self.assertEqual('txtPart', field['csharp_editor_name'])
        self.assertEqual('lblPart', field['csharp_label_name'])
        self.assertIn('BindingField', field['binding_code'])

    def test_composite_key_retains_any_number_of_raw_fields(self):
        spec = {'base_field': 'TICKET', 'sequence_fields': ['REV', 'LINE', 'PART'], 'display_field': 'DISPLAYKEY', 'base_type_family': 'character', 'sequence_type_family': 'integer'}
        result = build_composite_business_key_display_plan(spec)
        self.assertTrue(result.success, result.metadata)
        plan = result.metadata['plan']
        self.assertEqual(['TICKET', 'REV', 'LINE', 'PART'], plan['raw_result_fields'])
        self.assertEqual(3, plan['display_expression'].count('CONVERT('))
        self.assertNotIn('FORMAT(', plan['display_expression'])
        observation = {'result_fields': ['DISPLAYKEY'], 'display_alias': 'DISPLAYKEY'}
        self.assertFalse(verify_composite_business_key_display_contract(spec, observation).success)

    def test_numeric_format_is_not_blindly_changed_to_integer_conversion(self):
        result = build_composite_business_key_display_plan({'base_field': 'KEY', 'sequence_fields': ['SEQ'], 'base_type_family': 'character', 'sequence_type_family': 'numeric', 'sequence_format': '000'})
        self.assertIn("FORMAT(SEQ, '000')", result.metadata['plan']['display_expression'])
        self.assertFalse(build_composite_business_key_display_plan({'base_field': 'KEY', 'sequence_fields': ['SEQ']}).success)

    def test_sp_parameter_literals_and_optional_defaults(self):
        sql = "CREATE PROCEDURE dbo.sp_Save @KEY INT, @NOTE NVARCHAR(20) = N'AS @NO', @MODE CHAR(1) = 'A' AS SELECT @KEY"
        self.assertEqual({'@KEY': False, '@NOTE': True, '@MODE': True}, procedure_parameters(sql))
        self.assertTrue(check_sp_call('new DbParameter("KEY", value)', sql).success)
        self.assertFalse(check_sp_call('new DbParameter("OTHER", value)', sql).success)
        self.assertFalse(check_sp_call('// new DbParameter("KEY", value)', sql).success)

    def test_save_full_replace_requires_review(self):
        result = review_save_delta('DELETE FROM DETAIL WHERE DOC = @DOC; INSERT INTO DETAIL (DOC, QTY) SELECT DOC, QTY FROM @XML;')
        self.assertTrue(result.issues)
        self.assertEqual('warning', result.issues[0].severity)

    def test_measurements_preserve_duplicates_order_context_and_nulls(self):
        baseline = {'parameters': {'P': 1}, 'database': 'test', 'schema': ['ID', 'VALUE'], 'ordered': False, 'rows': [[1, None], [1, None]], 'elapsed_ms': [10, 12, 11]}
        candidate = copy.deepcopy(baseline)
        candidate['elapsed_ms'] = [5, 6, 5]
        result = compare_observations(baseline, candidate)
        self.assertTrue(result.success)
        self.assertAlmostEqual(2.2, result.metadata['observed_speed_ratio'])
        candidate['rows'].pop()
        self.assertFalse(compare_observations(baseline, candidate).success)
        candidate = copy.deepcopy(baseline)
        candidate['parameters'] = {'P': 2}
        self.assertFalse(compare_observations(baseline, candidate).success)

    def test_field_lineage_decodes_verbatim_names_and_reports_dynamic_fields(self):
        cs = 'this.colA.FieldName = @"ID";\nthis.colB.FieldName = GetField();'
        result = check_field_lineage(['ID'], ['ID'], cs)
        self.assertEqual('incomplete', result.status)
        self.assertNotIn('designer_field_not_returned', [i.code for i in result.issues])

    def test_project_sdk_excluded_source_is_not_claimed_included(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'Screen.cs'; source.write_text('class Screen {}')
            project = root/'App.csproj'
            project.write_text('<Project Sdk="Microsoft.NET.Sdk"><ItemGroup><Compile Remove="Screen.cs" /></ItemGroup></Project>')
            self.assertEqual('incomplete', inspect_project(project, [source]).status)
            project.write_text('<Project Sdk="Microsoft.NET.Sdk" />')
            self.assertTrue(inspect_project(project, [source]).success)

    def test_sql_only_plan_does_not_create_a_screen(self):
        plan = build_migration_plan(PB, scope='sql')
        self.assertFalse(plan['implementation_performed'])
        self.assertFalse(any('Designer' in str(item) for item in plan['work']))


if __name__ == '__main__':
    unittest.main()
