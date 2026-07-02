import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from src.orchestration.kh_front_door import build_kh_front_door
from src.orchestration.request_classifier import classify_request
from src.skills.pb_to_csharp_migration import (
    MigrationInputState,
    build_detail_form_layout_plan,
    build_csharp_control_name,
    build_csharp_grid_column_name,
    build_datawindow_grid_layout,
    build_datawindow_gridview_designer_defaults,
    build_pb_to_csharp_migration_plan,
    classify_migration_mode,
    extract_datawindow_column_specs,
    extract_datawindow_columns,
    generate_devexpress_grid_xml,
    resolve_csharp_grid_control_names,
    resolve_csharp_grid_column_prefix,
    resolve_csharp_control_stack,
)
from src.skills.uaf_skill_catalog import read_packaged_skill


class PbToCSharpMigrationHarnessTests(unittest.TestCase):
    def test_packaged_skill_is_readable_and_standalone(self):
        content = read_packaged_skill("pb-to-csharp-migration-harness")

        self.assertIn("Packaged source: uaf_skill_folder", content)
        self.assertIn("External runtime dependency: false", content)
        self.assertIn("src.skills.pb_to_csharp_migration", content)
        self.assertIn("DataWindowToXml", content)

    def test_migration_mode_does_not_require_local_tools(self):
        mode = classify_migration_mode(MigrationInputState())

        self.assertEqual(mode["mode"], "standalone")
        self.assertFalse(mode["runtime_lookup_required"])
        self.assertIn("bundled references", mode["fallback_policy"])

    def test_described_behavior_mode_when_pb_source_is_absent(self):
        mode = classify_migration_mode(
            MigrationInputState(
                has_behavior_description=True,
                notes=["User described the old PB lookup and save behavior."],
            )
        )

        self.assertEqual(mode["mode"], "described-behavior")
        self.assertFalse(mode["runtime_lookup_required"])
        self.assertTrue(any("user-described PB behavior" in item for item in mode["weak_evidence"]))

    def test_full_reference_mode_uses_available_evidence(self):
        mode = classify_migration_mode(
            {
                "has_exported_pb_sources": True,
                "has_target_csharp_samples": True,
                "has_sp_style_reference": True,
                "has_live_db_access": True,
            }
        )

        self.assertEqual(mode["mode"], "full-reference")
        self.assertGreaterEqual(mode["confidence"], 0.9)
        self.assertIn("exported .sru/.srw/.srd source", mode["strong_evidence"])

    def test_plan_returns_harness_result_with_passthrough_token_policy(self):
        result = build_pb_to_csharp_migration_plan(
            "Migrate PB DataWindow search/save screen into target C# and SP style.",
            {
                "has_pasted_source": True,
                "has_sp_style_reference": True,
                "available_controls": {
                    "target_project_controls": {"grid": "Acme.Controls.u_GridControl"},
                    "has_devexpress": True,
                },
            },
        )
        payload = json.loads(result.stdout)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(payload["harness"], "pb-to-csharp-migration-harness")
        self.assertEqual(payload["token_optimizer_status"], "passthrough")
        self.assertIn("DataWindow", " ".join(payload["steps"]))
        self.assertIn("confirmed vs inferred behavior map", payload["deliverables"])
        self.assertIn("target-project control fallback map", payload["deliverables"])
        self.assertEqual(payload["control_stack"]["selection"]["grid"]["provider"], "target-project")
        self.assertEqual(payload["control_stack"]["selection"]["grid"]["type"], "Acme.Controls.u_GridControl")

    def test_plan_records_described_behavior_as_inferred_rebuild(self):
        result = build_pb_to_csharp_migration_plan(
            "Rebuild a described PB inventory screen in a new C# project.",
            {"has_behavior_description": True, "has_sp_style_reference": True},
        )
        payload = json.loads(result.stdout)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(payload["mode"]["mode"], "described-behavior")
        self.assertIn("inferred behavior", " ".join(payload["steps"]))
        self.assertIn("confirmed vs inferred behavior map", payload["deliverables"])

    def test_control_stack_prefers_target_project_controls(self):
        result = resolve_csharp_control_stack(
            {
                "project_name": "AnyProject",
                "control_types": [
                    "Company.Ui.u_GridControl",
                    "Company.Ui.u_TextEdit",
                    "Company.Ui.u_Label",
                ],
                "has_devexpress": True,
            }
        )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["selection"]["grid"]["provider"], "target-project")
        self.assertEqual(result["selection"]["grid"]["type"], "Company.Ui.u_GridControl")
        self.assertEqual(result["selection"]["text"]["provider"], "target-project")
        self.assertEqual(result["selection"]["group"]["provider"], "devexpress")

    def test_control_stack_falls_back_to_devexpress_then_winforms(self):
        devexpress = resolve_csharp_control_stack({"has_devexpress": True})
        winforms = resolve_csharp_control_stack({})

        self.assertEqual(devexpress["selection"]["grid"]["provider"], "devexpress")
        self.assertEqual(devexpress["selection"]["grid"]["type"], "DevExpress.XtraGrid.GridControl")
        self.assertEqual(winforms["selection"]["grid"]["provider"], "winforms")
        self.assertEqual(winforms["selection"]["grid"]["type"], "System.Windows.Forms.DataGridView")

    def test_konelib_is_treated_as_target_project_inventory_not_global_baseline(self):
        result = resolve_csharp_control_stack({"has_konelib": True, "has_devexpress": True})

        self.assertEqual(result["selection"]["grid"]["provider"], "target-project")
        self.assertEqual(result["selection"]["grid"]["type"], "KoneLib.Controls.u_GridControl")
        self.assertEqual(result["selection"]["date"]["type"], "KoneLib.Controls.u_DateEdit")
        self.assertEqual(result["selection"]["spin"]["type"], "KoneLib.Controls.u_SpinEdit")
        self.assertEqual(result["selection"]["button"]["type"], "KoneLib.Controls.u_ButtonEdit")
        self.assertEqual(result["selection"]["combo"]["type"], "KoneLib.Controls.u_ComboBox")
        self.assertEqual(result["selection"]["memo"]["type"], "KoneLib.Controls.u_MemoEdit")
        self.assertEqual(result["selection"]["check"]["type"], "KoneLib.Controls.u_CheckEdit")
        self.assertEqual(result["selection"]["tree"]["type"], "KoneLib.Controls.u_TreeList")

    def test_detail_form_layout_places_label_editor_pairs_with_binding_fields(self):
        result = build_detail_form_layout_plan(
            [
                {"name": "ORDNUM", "caption": "수주번호", "editor_type": "text"},
                {"name": "QTY", "caption": "수주수량", "editor_type": "number", "logical_name": "Qty"},
                {"name": "ORDDT", "caption": "수주일자", "editor_type": "date"},
                {"name": "CUSTCD", "caption": "고객코드", "editor_type": "button"},
                {"name": "REMARK", "caption": "REMARK", "editor_type": "memo"},
                {"name": "USEYN", "caption": "USEYN", "editor_type": "check"},
            ],
            columns=3,
            section_caption="기본 상세정보",
        )
        payload = json.loads(result.stdout)
        fields = payload["fields"]

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(payload["columns"], 3)
        self.assertIn("do not copy PB pixel coordinates blindly", payload["layout_rule"])
        self.assertIn("BindingField", payload["binding_rule"])
        self.assertEqual(fields[0]["caption"], "수주번호")
        self.assertEqual(fields[0]["field_name"], "ORDNUM")
        self.assertEqual(fields[0]["csharp_label_name"], "lblORDNUM")
        self.assertEqual(fields[0]["csharp_editor_name"], "txtORDNUM")
        self.assertEqual(fields[0]["binding_code"], 'this.txtORDNUM.BindingField = "ORDNUM";')
        self.assertEqual(fields[1]["editor_type"], "SpinEdit")
        self.assertEqual(fields[1]["csharp_editor_name"], "SpinQTY")
        self.assertEqual(fields[1]["binding_code"], 'this.SpinQTY.BindingField = "QTY";')
        self.assertEqual(fields[2]["editor_type"], "DateEdit")
        self.assertEqual(fields[2]["csharp_editor_name"], "ymdORDDT")
        self.assertEqual(fields[2]["binding_code"], 'this.ymdORDDT.BindingField = "ORDDT";')
        self.assertEqual(fields[3]["editor_type"], "ButtonEdit")
        self.assertEqual(fields[3]["csharp_editor_name"], "btnCUSTCD")
        self.assertEqual(fields[4]["editor_type"], "MemoEdit")
        self.assertEqual(fields[4]["csharp_editor_name"], "memoREMARK")
        self.assertEqual(fields[5]["editor_type"], "CheckEdit")
        self.assertEqual(fields[5]["csharp_editor_name"], "ChkUSEYN")
        self.assertEqual(fields[0]["tab_index"], 0)
        self.assertEqual(fields[0]["tab_index_code"], "this.txtORDNUM.TabIndex = 0;")
        self.assertEqual(fields[5]["tab_index"], 5)
        self.assertEqual(fields[5]["tab_index_code"], "this.ChkUSEYN.TabIndex = 5;")
        self.assertEqual(fields[0]["row"], 0)
        self.assertEqual(fields[0]["column"], 0)
        self.assertEqual(fields[3]["row"], 1)
        self.assertEqual(fields[3]["column"], 0)
        self.assertEqual(fields[0]["label_bounds"]["y"], fields[1]["label_bounds"]["y"])
        self.assertLess(fields[0]["editor_bounds"]["x"], fields[1]["label_bounds"]["x"])

    def test_control_name_fallbacks_match_observed_csharp_prefixes(self):
        self.assertEqual(build_csharp_control_name("TextEdit", field_name="ITEMNM"), "txtITEMNM")
        self.assertEqual(build_csharp_control_name("ButtonEdit", field_name="CUSTCD"), "btnCUSTCD")
        self.assertEqual(build_csharp_control_name("LookUpEdit", field_name="ITEMACNT"), "cboITEMACNT")
        self.assertEqual(build_csharp_control_name("ComboBoxEdit", field_name="ITEMACNT"), "cboITEMACNT")
        self.assertEqual(build_csharp_control_name("SpinEdit", field_name="QTY"), "SpinQTY")
        self.assertEqual(build_csharp_control_name("DateEdit", field_name="ORDDT"), "ymdORDDT")
        self.assertEqual(build_csharp_control_name("MemoEdit", field_name="REMARK"), "memoREMARK")
        self.assertEqual(build_csharp_control_name("CheckEdit", field_name="USEYN"), "ChkUSEYN")
        self.assertEqual(build_csharp_control_name("PanelControl", logical_name="Detail"), "pnDetail")
        self.assertEqual(build_csharp_control_name("GroupControl", logical_name="Search"), "grpSearch")
        self.assertEqual(build_csharp_control_name("GridControl", logical_name="List"), "grdList")
        self.assertEqual(build_csharp_control_name("GridView", logical_name="List"), "gvwList")
        self.assertEqual(build_csharp_control_name("TreeList", logical_name="BOM"), "treeListBOM")
        self.assertEqual(build_csharp_control_name("TabControl", logical_name="List"), "tabList")

    def test_extracts_datawindow_columns_and_generates_devexpress_xml(self):
        source = """
datawindow(units=0)
table(column=(type=char(20) dbname="sa110t.ordnum" name=ordnum)
column=(type=char(30) dbname="sa110t.itemcd" name=itemcd))
"""
        columns = extract_datawindow_columns(source)
        xml_text = generate_devexpress_grid_xml(columns)
        root = ET.fromstring(xml_text)

        self.assertEqual(columns, ["ORDNUM", "ITEMCD"])
        self.assertEqual(root.tag, "XtraSerializer")
        self.assertIn("<property name=\"FieldName\">ORDNUM</property>", xml_text)
        self.assertIn("<property name=\"Name\">colList_ITEMCD</property>", xml_text)
        expected_grid_defaults = [
            "BestFitMaxRowCount",
            "PreviewLineCount",
            "HorzScrollStep",
            "FocusRectStyle",
            "ScrollStyle",
            "PreviewIndent",
            "GroupPanelText",
            "PreviewFieldName",
            "VertScrollTipFieldName",
            "LevelIndent",
            "GroupFooterShowMode",
            "NewItemRowText",
            "SynchronizeClones",
            "BorderStyle",
            "ViewCaption",
            "DetailHeight",
            "DetailTabHeaderLocation",
            "ActiveFilterEnabled",
        ]
        for property_name in expected_grid_defaults:
            self.assertIn(f"<property name=\"{property_name}\"", xml_text)
        self.assertIn("<property name=\"VisibleIndex\">1</property>", xml_text)
        self.assertIn("<property name=\"VisibleIndex\">2</property>", xml_text)
        self.assertIn("<property name=\"ShowViewCaption\">false</property>", xml_text)
        self.assertIn("<property name=\"EnableAppearanceEvenRow\">true</property>", xml_text)
        self.assertIn("<property name=\"ShowGroupPanel\">false</property>", xml_text)
        self.assertIn("<property name=\"ColumnAutoWidth\">false</property>", xml_text)
        self.assertIn("<property name=\"ShowFooter\">true</property>", xml_text)
        self.assertIn("<property name=\"ShowAutoFilterRow\">true</property>", xml_text)

    def test_extracts_visual_order_csharp_names_and_matched_captions(self):
        source = """
datawindow(units=0)
table(column=(type=char(10) updatewhereclause=no name=as_itemnm dbname="as_itemnm" )
 column=(type=char(10) updatewhereclause=no name=as_itemcd dbname="as_itemcd" )
 )
column(band=detail id=2 x="178" y="12" height="60" width="699" name=as_itemcd )
column(band=detail id=1 x="1056" y="12" height="60" width="686" name=as_itemnm )
text(band=detail text="코드" x="18" y="12" height="60" width="133" name=t_1 )
text(band=detail text="품명" x="901" y="12" height="60" width="133" name=as_item_t )
"""
        specs = extract_datawindow_column_specs(source)
        xml_text = generate_devexpress_grid_xml(specs)

        self.assertEqual([spec.field_name for spec in specs], ["AS_ITEMCD", "AS_ITEMNM"])
        self.assertEqual([spec.caption for spec in specs], ["코드", "품명"])
        self.assertEqual([spec.csharp_name for spec in specs], ["colList_AS_ITEMCD", "colList_AS_ITEMNM"])
        self.assertIn("<property name=\"Caption\">코드</property>", xml_text)
        self.assertIn("<property name=\"Caption\">품명</property>", xml_text)
        self.assertIn("<property name=\"Name\">colList_AS_ITEMCD</property>", xml_text)

    def test_matches_header_band_captions_to_detail_columns(self):
        source = """
datawindow(units=0)
header(height=80)
detail(height=70)
table(column=(type=char(10) name=itemcd dbname="itemcd" )
 column=(type=char(10) name=itemnm dbname="itemnm" ))
text(band=header text="품목코드" x="100" y="8" height="40" width="220" name=t_itemcd )
text(band=header text="품목명" x="340" y="8" height="40" width="260" name=t_itemnm )
column(band=detail x="100" y="12" height="50" width="220" name=itemcd )
column(band=detail x="340" y="12" height="50" width="260" name=itemnm )
"""
        specs = extract_datawindow_column_specs(source)

        self.assertEqual([spec.field_name for spec in specs], ["ITEMCD", "ITEMNM"])
        self.assertEqual([spec.caption for spec in specs], ["품목코드", "품목명"])

    def test_resolves_csharp_grid_column_prefix_variants(self):
        self.assertEqual(resolve_csharp_grid_column_prefix("list"), "colList_")
        self.assertEqual(resolve_csharp_grid_column_prefix("detail"), "colDetail_")
        self.assertEqual(resolve_csharp_grid_column_prefix("table", table_name="SA110T"), "colSA110T_")
        self.assertEqual(resolve_csharp_grid_column_prefix("purpose", purpose_name="POR"), "colPOR_")
        self.assertEqual(resolve_csharp_grid_column_prefix("table", purpose_name="BOM"), "colBOM_")
        self.assertEqual(resolve_csharp_grid_column_prefix("colCustom_"), "colCustom_")
        self.assertEqual(build_csharp_grid_column_name("itemcd", prefix="colDetail_"), "colDetail_ITEMCD")

    def test_resolves_csharp_grid_control_name_variants(self):
        self.assertEqual(
            resolve_csharp_grid_control_names("list"),
            {"grid_control_name": "grdList", "grid_view_name": "gvwList"},
        )
        self.assertEqual(
            resolve_csharp_grid_control_names("detail"),
            {"grid_control_name": "grdDetail", "grid_view_name": "gvwDetail"},
        )
        self.assertEqual(
            resolve_csharp_grid_control_names("table", table_name="SA110T"),
            {"grid_control_name": "grdSA110T", "grid_view_name": "gvwSA110T"},
        )
        self.assertEqual(
            resolve_csharp_grid_control_names("purpose", purpose_name="POR"),
            {"grid_control_name": "grdPOR", "grid_view_name": "gvwPOR"},
        )
        self.assertEqual(
            resolve_csharp_grid_control_names("table", purpose_name="BOM"),
            {"grid_control_name": "grdBOM", "grid_view_name": "gvwBOM"},
        )

    def test_datawindow_layout_metadata_records_column_prefix_and_captions(self):
        source = """
datawindow(units=0)
column(band=detail x="100" y="10" height="50" width="200" name=itemcd )
text(band=detail text="품목코드" x="10" y="10" height="50" width="80" name=t_itemcd )
"""
        result = build_datawindow_grid_layout(source, input_format="table", table_name="BA030T")

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["csharp_column_prefix"], "colBA030T_")
        self.assertEqual(
            result.metadata["csharp_grid_names"],
            {"grid_control_name": "grdBA030T", "grid_view_name": "gvwBA030T"},
        )
        self.assertEqual(result.metadata["column_specs"][0]["csharp_name"], "colBA030T_ITEMCD")
        self.assertEqual(result.metadata["column_specs"][0]["caption"], "품목코드")
        self.assertIn("<property name=\"Name\">gvwBA030T</property>", result.stdout)
        self.assertIn("<property name=\"Name\">colBA030T_ITEMCD</property>", result.stdout)
        self.assertIn("<property name=\"Caption\">품목코드</property>", result.stdout)

    def test_datawindow_layout_uses_purpose_name_when_table_name_is_ambiguous(self):
        source = """
datawindow(units=0)
column(band=detail x="100" y="10" height="50" width="200" name=porseq )
text(band=detail text="발주순번" x="10" y="10" height="50" width="80" name=t_porseq )
"""
        result = build_datawindow_grid_layout(source, input_format="purpose", purpose_name="POR")

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["csharp_column_prefix"], "colPOR_")
        self.assertEqual(
            result.metadata["csharp_grid_names"],
            {"grid_control_name": "grdPOR", "grid_view_name": "gvwPOR"},
        )
        self.assertEqual(result.metadata["column_specs"][0]["csharp_name"], "colPOR_PORSEQ")
        self.assertEqual(result.metadata["column_specs"][0]["caption"], "발주순번")
        self.assertIn("<property name=\"Name\">gvwPOR</property>", result.stdout)
        self.assertIn("<property name=\"Name\">colPOR_PORSEQ</property>", result.stdout)
        self.assertIn("<property name=\"Caption\">발주순번</property>", result.stdout)

    def test_raw_converter_name_default_is_distinct_from_target_csharp_layout_name(self):
        xml_text = generate_devexpress_grid_xml(["ITEMCD"])
        layout = build_datawindow_grid_layout("column(band=detail x=\"1\" y=\"1\" width=\"10\" height=\"10\" name=itemcd )")

        self.assertIn("<property name=\"Name\">gridView1</property>", xml_text)
        self.assertEqual(layout.metadata["csharp_grid_names"]["grid_view_name"], "gvwList")
        self.assertIn("<property name=\"Name\">gvwList</property>", layout.stdout)

    def test_gridview_designer_defaults_match_datawindow_to_xml_options_view(self):
        assignments = build_datawindow_gridview_designer_defaults("gvwList")

        self.assertIn("this.gvwList.OptionsView.ShowViewCaption = false;", assignments)
        self.assertIn("this.gvwList.OptionsView.EnableAppearanceEvenRow = true;", assignments)
        self.assertIn("this.gvwList.OptionsView.ShowGroupPanel = false;", assignments)
        self.assertIn("this.gvwList.OptionsView.ColumnAutoWidth = false;", assignments)
        self.assertIn("this.gvwList.OptionsView.ShowFooter = true;", assignments)
        self.assertIn("this.gvwList.OptionsView.ShowAutoFilterRow = true;", assignments)

    def test_datawindow_layout_blocks_when_no_columns_exist(self):
        result = build_datawindow_grid_layout("datawindow(units=0)")

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.metadata["blocked_reason"], "missing_datawindow_columns")

    def test_front_door_routes_pb_to_csharp_migration_to_harness(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = build_kh_front_door(
                "Migrate this PowerBuilder PBL/DataWindow flow into a C# WinForms and SQL Server SELECT/SAVE SP style.",
                project=Path(temp_dir),
                host="codex",
            )
        summary = result.to_summary_dict()

        self.assertIn("pb-to-csharp-migration-harness", summary["recommended_skills"])
        self.assertIn("pb-to-csharp-migration-harness", summary["immediate_next_skills"])
        self.assertEqual(summary["classification"]["domain"], "software")

    def test_front_door_does_not_route_non_pb_complex_extraction_to_pb_harness(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = build_kh_front_door(
                "Analyze this stored procedure report image and list SELECT bound column names for a C# grid.",
                project=Path(temp_dir),
                host="codex",
            )
        summary = result.to_summary_dict()

        self.assertNotIn("pb-to-csharp-migration-harness", summary["recommended_skills"])
        self.assertNotIn("pb-to-csharp-migration-harness", summary["immediate_next_skills"])


if __name__ == "__main__":
    unittest.main()
