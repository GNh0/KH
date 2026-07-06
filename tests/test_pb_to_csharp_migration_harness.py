import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from src.orchestration.kh_front_door import build_kh_front_door
from src.orchestration.request_classifier import classify_request
from src.skills.pb_to_csharp_migration import (
    MigrationInputState,
    build_pbl_export_strategy,
    build_csharp_grid_column_designer_plan,
    build_detail_form_layout_plan,
    build_csharp_control_name,
    build_csharp_grid_column_name,
    build_datawindow_grid_layout,
    build_datawindow_gridview_designer_defaults,
    build_pb_to_csharp_migration_plan,
    classify_migration_mode,
    extract_datawindow_column_specs,
    extract_datawindow_columns,
    extract_csharp_designer_control_specs,
    generate_devexpress_grid_xml,
    get_author_tagged_csharp_style_baseline,
    normalize_author_tagged_program_key,
    resolve_author_tagged_style_evidence,
    verify_migration_generated_csharp_style,
    verify_pb_migration_analysis_document,
    verify_pb_migration_sp_generation_contract,
    verify_pb_migration_sp_with_sql_formatting,
    resolve_csharp_grid_control_names,
    resolve_csharp_grid_column_prefix,
    resolve_csharp_control_stack,
)
from src.skills.uaf_skill_catalog import read_packaged_skill


def sp_metadata_header(description="총괄조회 조회"):
    return f"""-- =============================================
-- AUTHOR:      근호
-- CREATE DATE: 2026-06-15
-- DESCRIPTION: {description}
-- =============================================
"""


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

    def test_orca_is_direct_pbl_export_provider_without_pblscripter(self):
        strategy = build_pbl_export_strategy({"has_orca": True, "pb_version": "12.5"})
        mode = classify_migration_mode({"has_orca": True, "pb_version": "12.5"})

        self.assertEqual(strategy["provider"], "orca")
        self.assertEqual(strategy["status"], "available")
        self.assertEqual(strategy["pb_version"], "12.5")
        self.assertIn("PB 12.5 ORCA/runtime", strategy["version_policy"])
        self.assertEqual(mode["mode"], "partial-reference")
        self.assertIn("ORCA available but export not attached yet", mode["weak_evidence"])

    def test_orca_without_pb_version_is_probe_only(self):
        strategy = build_pbl_export_strategy({"has_orca": True})
        mode = classify_migration_mode({"has_orca": True})

        self.assertEqual(strategy["provider"], "orca")
        self.assertEqual(strategy["status"], "available_with_version_probe")
        self.assertEqual(strategy["confidence"], "bounded")
        self.assertTrue(strategy["runtime_lookup_required"])
        self.assertIn("full source parity", strategy["reason"])
        self.assertTrue(mode["runtime_lookup_required"])
        self.assertTrue(mode["pbl_export_strategy"]["runtime_lookup_required"])
        self.assertEqual(mode["pbl_export_strategy"]["status"], "available_with_version_probe")

    def test_pblscripter_without_pb_version_is_probe_only(self):
        strategy = build_pbl_export_strategy({"pbl_export_tool": "Export-PBL.ps1"})
        mode = classify_migration_mode({"pbl_export_tool": "Export-PBL.ps1"})

        self.assertEqual(strategy["provider"], "pblscripter")
        self.assertEqual(strategy["status"], "available_with_version_probe")
        self.assertTrue(strategy["runtime_lookup_required"])
        self.assertTrue(mode["runtime_lookup_required"])

    def test_export_provider_priority_falls_back_to_pasted_source_and_bundled_reference(self):
        pasted = build_pbl_export_strategy({"has_pasted_source": True})
        bundled = build_pbl_export_strategy({})

        self.assertEqual(pasted["provider"], "pasted_source")
        self.assertEqual(pasted["confidence"], "bounded")
        self.assertEqual(bundled["provider"], "bundled_reference")
        self.assertEqual(bundled["confidence"], "low")

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
        self.assertIn("PBL export provider and PB version strategy", payload["deliverables"])
        self.assertIn("target-project control fallback map", payload["deliverables"])
        self.assertEqual(payload["pbl_export_strategy"]["provider"], "pasted_source")
        self.assertEqual(payload["control_stack"]["selection"]["grid"]["provider"], "target-project")
        self.assertEqual(payload["control_stack"]["selection"]["grid"]["type"], "Acme.Controls.u_GridControl")

    def test_plan_records_orca_version_strategy(self):
        result = build_pb_to_csharp_migration_plan(
            "Export PB 7.0 PBL with ORCA and migrate the screen.",
            {"has_orca": True, "pb_version": "7.0", "has_sp_style_reference": True},
        )
        payload = json.loads(result.stdout)

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(payload["pbl_export_strategy"]["provider"], "orca")
        self.assertEqual(payload["pbl_export_strategy"]["pb_version"], "7.0")
        self.assertIn("PB 7.0 ORCA/runtime", payload["pbl_export_strategy"]["version_policy"])
        self.assertIn("PblScripter", payload["pbl_export_strategy"]["provider_priority"][0])
        self.assertIn("wrapper", payload["pbl_export_strategy"]["provider_priority"][0])

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

    def test_extracts_csharp_designer_control_properties_from_target_style(self):
        designer_source = '''
            this.grpSearch = new DevExpress.XtraEditors.GroupControl();
            this.radGUBUN = new KoneLib.Controls.u_RadioButton();
            this.txtGIJUN = new KoneLib.Controls.u_TextEdit();
            this.btnCUSTCD = new KoneLib.Controls.u_ButtonEdit();
            this.lblGijun = new DevExpress.XtraEditors.LabelControl();
            this.grdList = new KoneLib.Controls.u_GridControl();
            this.gvwList = new DevExpress.XtraGrid.Views.Grid.GridView();
            this.colList_AMTTOT = new DevExpress.XtraGrid.Columns.GridColumn();
            this.Controls.Add(this.grpSearch);
            this.grpSearch.Controls.Add(this.radGUBUN);
            this.grpSearch.Controls.Add(this.txtGIJUN);
            this.grpSearch.Controls.Add(this.btnCUSTCD);
            this.radGUBUN._isAllowBlank = true;
            this.radGUBUN._isPKValue = false;
            this.radGUBUN.BindingField = "GUBUN";
            this.radGUBUN.EditValue = "T";
            this.radGUBUN.EnterMoveNextControl = true;
            this.radGUBUN.Location = new System.Drawing.Point(733, 31);
            this.radGUBUN.Properties.Items.AddRange(new DevExpress.XtraEditors.Controls.RadioGroupItem[] {
            new DevExpress.XtraEditors.Controls.RadioGroupItem("T", "전체"),
            new DevExpress.XtraEditors.Controls.RadioGroupItem("A", "출고")});
            this.radGUBUN.Size = new System.Drawing.Size(260, 23);
            this.radGUBUN.TabIndex = 7;
            this.txtGIJUN._isAllowBlank = false;
            this.txtGIJUN.BindingField = "GIJUN";
            this.txtGIJUN.MaximumSize = new System.Drawing.Size(65535, 23);
            this.txtGIJUN.MinimumSize = new System.Drawing.Size(0, 23);
            this.txtGIJUN.Properties.AutoHeight = false;
            this.txtGIJUN.Properties.Mask.EditMask = "0000";
            this.txtGIJUN.Properties.Mask.MaskType = DevExpress.XtraEditors.Mask.MaskType.Simple;
            this.btnCUSTCD.BindingField = "CUSTCD";
            this.btnCUSTCD.Properties.Buttons.AddRange(new DevExpress.XtraEditors.Controls.EditorButton[] {
            new DevExpress.XtraEditors.Controls.EditorButton(DevExpress.XtraEditors.Controls.ButtonPredefines.Search)});
            this.grdList.MainView = this.gvwList;
            this.grdList.ViewCollection.AddRange(new DevExpress.XtraGrid.Views.Base.BaseView[] {
            this.gvwList});
            this.gvwList.Columns.AddRange(new DevExpress.XtraGrid.Columns.GridColumn[] {
            this.colList_AMTTOT});
            this.gvwList.GridControl = this.grdList;
            this.gvwList.Name = "gvwList";
            this.colList_AMTTOT.FieldName = "AMTTOT";
            private DevExpress.XtraEditors.GroupControl grpSearch;
            private KoneLib.Controls.u_RadioButton radGUBUN;
            private KoneLib.Controls.u_TextEdit txtGIJUN;
            private KoneLib.Controls.u_ButtonEdit btnCUSTCD;
            private DevExpress.XtraEditors.LabelControl lblGijun;
            private KoneLib.Controls.u_GridControl grdList;
            private DevExpress.XtraGrid.Views.Grid.GridView gvwList;
            private DevExpress.XtraGrid.Columns.GridColumn colList_AMTTOT;
        '''

        result = extract_csharp_designer_control_specs(designer_source)
        payload = json.loads(result.stdout)
        controls = {item["name"]: item for item in payload["controls"]}

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(controls["radGUBUN"]["type_name"], "KoneLib.Controls.u_RadioButton")
        self.assertEqual(controls["radGUBUN"]["binding_field"], "GUBUN")
        self.assertEqual(controls["radGUBUN"]["properties"]["_isAllowBlank"], True)
        self.assertEqual(controls["radGUBUN"]["properties"]["_isPKValue"], False)
        self.assertEqual(controls["radGUBUN"]["properties"]["EditValue"], "T")
        self.assertEqual(controls["radGUBUN"]["properties"]["EnterMoveNextControl"], True)
        self.assertEqual(controls["radGUBUN"]["location"], {"x": 733, "y": 31})
        self.assertEqual(controls["radGUBUN"]["size"], {"width": 260, "height": 23})
        self.assertEqual(controls["radGUBUN"]["tab_index"], 7)
        self.assertIn("Properties.Items.AddRange", controls["radGUBUN"]["collection_calls"])
        self.assertEqual(controls["txtGIJUN"]["binding_field"], "GIJUN")
        self.assertEqual(controls["txtGIJUN"]["properties"]["Properties.AutoHeight"], False)
        self.assertEqual(controls["txtGIJUN"]["properties"]["Properties.Mask.EditMask"], "0000")
        self.assertEqual(controls["txtGIJUN"]["properties"]["MaximumSize"], {"width": 65535, "height": 23})
        self.assertIn("Properties.Buttons.AddRange", controls["btnCUSTCD"]["collection_calls"])
        self.assertEqual(controls["btnCUSTCD"]["parent_name"], "grpSearch")
        self.assertEqual(controls["grpSearch"]["parent_name"], "this")
        self.assertEqual(controls["grpSearch"]["children"], ["radGUBUN", "txtGIJUN", "btnCUSTCD"])
        self.assertEqual(payload["grid_columns_present"], True)
        self.assertEqual(payload["grid_column_count"], 1)
        self.assertEqual(payload["grid_columns"][0]["name"], "colList_AMTTOT")
        self.assertEqual(controls["lblGijun"]["caption"], "")
        self.assertEqual(controls["grdList"]["properties"]["MainView"], "this.gvwList")
        self.assertIn("ViewCollection.AddRange", controls["grdList"]["collection_calls"])
        self.assertEqual(controls["gvwList"]["properties"]["GridControl"], "this.grdList")

    def test_csharp_designer_string_values_preserve_korean_text(self):
        result = extract_csharp_designer_control_specs(
            '''
            this.lblGijun = new DevExpress.XtraEditors.LabelControl();
            this.lblGijun.Text = "기준년도";
            this.lblGijun.Name = "lblGijun";
            '''
        )
        controls = {item["name"]: item for item in json.loads(result.stdout)["controls"]}

        self.assertEqual(controls["lblGijun"]["caption"], "기준년도")
        self.assertEqual(controls["lblGijun"]["properties"]["Text"], "기준년도")

    def test_generated_csharp_style_blocks_runtime_columns_add_even_with_designer_members(self):
        generated = '''
        private DevExpress.XtraGrid.Columns.GridColumn colList_CUSTNM;
        this.colList_CUSTNM = new DevExpress.XtraGrid.Columns.GridColumn();
        this.gvwList.Columns.AddRange(new DevExpress.XtraGrid.Columns.GridColumn[] {
        this.colList_CUSTNM});
        DevExpress.XtraGrid.Columns.GridColumn runtimeColumn = new DevExpress.XtraGrid.Columns.GridColumn();
        runtimeColumn.FieldName = "ITEMCD";
        this.gvwList.Columns.Add(runtimeColumn);
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("runtime_columns_add_detected", issue_codes)
        self.assertIn("runtime_gridcolumn_constructor_without_designer_contract", issue_codes)

    def test_generated_csharp_style_blocks_runtime_grid_column_construction_and_add(self):
        generated = '''
        private void SetColumns()
        {
            DevExpress.XtraGrid.Columns.GridColumn column = new DevExpress.XtraGrid.Columns.GridColumn();
            column.FieldName = "AMTTOT";
            column.Name = "colList_AMTTOT";
            gvwList.Columns.Add(column);
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("runtime_gridcolumn_constructor_without_designer_contract", issue_codes)
        self.assertIn("runtime_columns_add_detected", issue_codes)

    def test_generated_csharp_style_blocks_price_formatstring_only_without_spin_repository(self):
        generated = '''
        private DevExpress.XtraGrid.Columns.GridColumn colList_PRICE;
        this.colList_PRICE = new DevExpress.XtraGrid.Columns.GridColumn();
        this.gvwList.Columns.AddRange(new DevExpress.XtraGrid.Columns.GridColumn[] {
        this.colList_PRICE});
        this.colList_PRICE.FieldName = "PRICE";
        this.colList_PRICE.Name = "colList_PRICE";
        this.colList_PRICE.DisplayFormat.FormatString = "{0:#,##0.##}";
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("numeric_grid_column_missing_spin_repository", issue_codes)
        self.assertIn("numeric_grid_column_displayformat_detected", issue_codes)

    def test_generated_csharp_style_blocks_numeric_displayformat_without_spin_repository(self):
        generated = '''
        private DevExpress.XtraGrid.Columns.GridColumn colList_AMTTOT;
        this.colList_AMTTOT = new DevExpress.XtraGrid.Columns.GridColumn();
        this.gvwList.Columns.AddRange(new DevExpress.XtraGrid.Columns.GridColumn[] {
        this.colList_AMTTOT});
        this.colList_AMTTOT.FieldName = "AMTTOT";
        this.colList_AMTTOT.Name = "colList_AMTTOT";
        this.colList_AMTTOT.DisplayFormat.FormatString = "{0:#,##0}";
        this.colList_AMTTOT.DisplayFormat.FormatType = DevExpress.Utils.FormatType.Numeric;
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("numeric_grid_column_missing_spin_repository", issue_codes)
        self.assertIn("numeric_grid_column_displayformat_detected", issue_codes)

    def test_generated_csharp_style_accepts_numeric_spin_repository_columnedit(self):
        generated = '''
        private DevExpress.XtraGrid.Columns.GridColumn colList_AMTTOT;
        private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit rpsSpinAmt;
        this.colList_AMTTOT = new DevExpress.XtraGrid.Columns.GridColumn();
        this.rpsSpinAmt = new DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit();
        this.gvwList.Columns.AddRange(new DevExpress.XtraGrid.Columns.GridColumn[] {
        this.colList_AMTTOT});
        this.colList_AMTTOT.FieldName = "AMTTOT";
        this.colList_AMTTOT.Name = "colList_AMTTOT";
        this.colList_AMTTOT.ColumnEdit = this.rpsSpinAmt;
        '''

        result = verify_migration_generated_csharp_style(generated)

        self.assertTrue(result.success, result.metadata["issues"])

    def test_generated_csharp_style_blocks_undeclared_spin_repository_reference(self):
        generated = '''
        private DevExpress.XtraGrid.Columns.GridColumn colList_AMTTOT;
        this.colList_AMTTOT = new DevExpress.XtraGrid.Columns.GridColumn();
        this.gvwList.Columns.AddRange(new DevExpress.XtraGrid.Columns.GridColumn[] {
        this.colList_AMTTOT});
        this.colList_AMTTOT.FieldName = "AMTTOT";
        this.colList_AMTTOT.Name = "colList_AMTTOT";
        this.colList_AMTTOT.ColumnEdit = this.rpsSpinAmt;
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("numeric_grid_spin_repository_not_declared_or_initialized", issue_codes)

    def test_generated_csharp_style_blocks_runtime_grid_column_helpers(self):
        generated = '''
        private void SetGridColumns()
        {
            AddGridColumn(gvwList, "CUSTNM", "고객", 160, true, false);
        }
        private GridColumn AddGridColumn(GridView view, string fieldName, string caption, int width, bool visible, bool numeric)
        {
            GridColumn column = view.Columns.AddField(fieldName);
            column.Name = view.Name + "_" + fieldName;
            return column;
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("runtime_add_grid_column_helper_detected", issue_codes)
        self.assertIn("runtime_columns_addfield_detected", issue_codes)
        self.assertIn("view_name_fieldname_column_name_detected", issue_codes)

    def test_generated_csharp_style_blocks_context_dto_and_generic_value_helpers(self):
        generated = '''
        private sealed class RetrieveContext
        {
            public string YYYY { get; set; }
        }

        private RetrieveContext GetRetrieveContext()
        {
            return new RetrieveContext();
        }

        private string GetEditValue(DevExpress.XtraEditors.BaseEdit edit, string defaultValue)
        {
            return defaultValue;
        }

        private string GetColumnText(System.Data.DataRow row, string columnName)
        {
            return string.Empty;
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_internal_dto_class_detected", issue_codes)
        self.assertIn("generated_context_flow_detected", issue_codes)
        self.assertIn("generated_get_edit_value_helper_detected", issue_codes)
        self.assertIn("generated_get_column_text_helper_detected", issue_codes)

    def test_generated_csharp_style_blocks_helper_variants_and_visible_index_helper(self):
        generated = '''
        private static string GetEditValue(DevExpress.XtraEditors.BaseEdit edit, string defaultValue)
        {
            return defaultValue;
        }

        private object GetColumnText(System.Data.DataRow row, string columnName)
        {
            return string.Empty;
        }

        private void SetVisibleIndex(DevExpress.XtraGrid.Columns.GridColumn column, bool visible, ref int visibleIndex)
        {
            column.Visible = visible;
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_get_edit_value_helper_detected", issue_codes)
        self.assertIn("generated_get_column_text_helper_detected", issue_codes)
        self.assertIn("generated_set_visible_index_helper_detected", issue_codes)

    def test_generated_csharp_style_blocks_sa900100_followup_generated_helpers(self):
        generated = '''
        private void SA900100_Load(object sender, EventArgs e)
        {
            SetDefaultSearchValues();
            ApplyListColumnLayout();
        }

        private bool ValidateSearch()
        {
            ShowMessageError("\u6e72\uacd7");
            return true;
        }

        private string GetBasisYear()
        {
            return ymdGIJUN.Text.Trim();
        }

        private string GetCustomerLike()
        {
            return btnCUSTCD.Text.Trim() + "%";
        }

        private void SetDefaultSearchValues(bool force = false)
        {
        }

        private void ApplyListColumnLayout()
        {
            for (int i = 1; i <= 12; i++)
            {
                gvwList.Columns["AMT" + i.ToString("00")].VisibleIndex = i + 1;
            }
        }

        private void BtnCUSTCD_ButtonClick(object sender, DevExpress.XtraEditors.Controls.ButtonPressedEventArgs e)
        {
            PopCustFrm pop = new PopCustFrm();
            DialogResult di = pop.ShowDialog();
            if (di == DialogResult.Yes || di == DialogResult.OK)
            {
            }
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_default_search_values_helper_detected", issue_codes)
        self.assertIn("generated_list_column_layout_helper_detected", issue_codes)
        self.assertIn("generated_basis_year_helper_detected", issue_codes)
        self.assertIn("generated_customer_like_helper_detected", issue_codes)
        self.assertIn("generated_validate_search_helper_detected", issue_codes)
        self.assertIn("generated_month_column_visibleindex_loop_detected", issue_codes)
        self.assertIn("popcust_dialogresult_yes_or_ok_detected", issue_codes)
        self.assertIn("mojibake_korean_literal_detected", issue_codes)

    def test_author_tagged_csharp_style_baseline_has_real_analysis_counts(self):
        baseline = get_author_tagged_csharp_style_baseline()

        self.assertEqual(62, baseline["sp_count"])
        self.assertEqual(41, baseline["normalized_program_key_count"])
        self.assertEqual(37, baseline["primary_csharp_baseline_files_analyzed"])
        self.assertEqual(37, baseline["designer_files_analyzed"])
        self.assertIn("SA900100", baseline["baseline_exclusions"])
        self.assertEqual(31, baseline["primary_csharp_pattern_counts"]["CallSelectProcedure"]["files"])
        self.assertEqual(27, baseline["primary_csharp_pattern_counts"]["GetFocusedDataRow"]["files"])
        self.assertEqual(35, baseline["designer_pattern_counts"]["u_GridControl"]["files"])
        self.assertEqual(34, baseline["designer_pattern_counts"]["explicit_GridColumn_fields"]["files"])
        self.assertEqual(27, baseline["designer_pattern_counts"]["RepositoryItemSpinEdit"]["files"])
        self.assertEqual(0, baseline["zero_hit_generated_patterns"]["DBNull_ternary_row_value"])
        self.assertEqual(0, baseline["zero_hit_generated_patterns"]["radio_Convert_ToString_local"])
        self.assertEqual(0, baseline["zero_hit_generated_patterns"]["CallSelectProcedure_inline_wildcard_argument"])
        self.assertEqual(0, baseline["zero_hit_generated_patterns"]["CSharp_like_wildcard_shaping"])
        self.assertEqual(0, baseline["zero_hit_generated_patterns"]["DateEdit_null_SetToDay_default"])
        self.assertEqual(0, baseline["zero_hit_generated_patterns"]["DateEdit_year_or_now_parameter_shaping"])
        self.assertEqual(0, baseline["zero_hit_generated_patterns"]["generated_date_boundary_DateTime_block"])
        self.assertEqual(0, baseline["zero_hit_generated_patterns"]["direct_grid_datasource_null_reset"])
        self.assertEqual(0, baseline["zero_hit_generated_patterns"]["CallDetailQuery_generated_method"])
        recipe = baseline["positive_generation_recipe"]
        self.assertIn("same-program primary C# file", recipe["source_priority"])
        self.assertEqual("FrmDevBase", recipe["screen_base"]["normal_screen"])
        self.assertIn("prefer the matched source's CallSelectProcedure or CallViewQuery shape", recipe["select_flow"])
        self.assertIn("use RepositoryItemSpinEdit through ColumnEdit for numeric grid columns instead of DisplayFormat-only output", recipe["designer_flow"])

    def test_author_tagged_program_style_profiles_are_packaged(self):
        profile_path = Path("skills/pb_to_csharp_migration_harness/references/author-tagged-program-style-profiles.json")
        payload = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertEqual(37, payload["program_count"])
        self.assertIn("SA800100", payload["profiles"])
        sa800100 = payload["profiles"]["SA800100"]
        self.assertEqual("FrmDevBase", sa800100["base_class"])
        self.assertIn("CallSelectProcedure", sa800100["select_methods"])
        self.assertIn("sp_SA800100_SELECT", {item["procedure"] for item in sa800100["sp_calls"]})
        self.assertIn("@WORKTYPE", sa800100["db_parameters"])
        self.assertTrue(sa800100["style_flags"]["has_columns_addrange"])

    def test_author_tagged_style_evidence_resolves_sp_to_program_key(self):
        self.assertEqual("SA800100", normalize_author_tagged_program_key("dbo.sp_SA800100_SELECT"))
        self.assertEqual("MA100100_POP", normalize_author_tagged_program_key("[dbo].[sp_MA100100_POP_SELECT]"))

        resolved = resolve_author_tagged_style_evidence("sp_SA800100_SELECT")
        self.assertTrue(resolved.success, resolved.to_dict())
        self.assertEqual("SA800100", resolved.metadata["program_key"])
        self.assertIn("SA800100.cs", resolved.metadata["primary_style_evidence_paths"][0])

        excluded = resolve_author_tagged_style_evidence("SP_SA900100_SELECT")
        self.assertFalse(excluded.success)
        self.assertEqual("excluded", excluded.metadata["status"])
        self.assertIn("repair target", excluded.metadata["exclusion_reason"])

    def test_author_tagged_style_evidence_discovers_same_program_files_under_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            screen_dir = root / "20.영업(SA)" / "Konesystem.SA02"
            screen_dir.mkdir(parents=True)
            (screen_dir / "SA800100.cs").write_text(
                """
                public partial class SA800100 : FrmDevBase
                {
                    protected override void SearchCommand(object sender, EventArgs e) {}
                    private DataSet CallSelectProcedure()
                    {
                        return dbClient.GetDataSetFromSP("sp_SA800100_SELECT"
                            , new DbParameter("@WORKTYPE", "LIST"));
                    }
                }
                """,
                encoding="utf-8",
            )
            (screen_dir / "SA800100.Designer.cs").write_text(
                """
                private DevExpress.XtraGrid.Columns.GridColumn colList_ITEMCD;
                this.gvwList.Columns.AddRange(new DevExpress.XtraGrid.Columns.GridColumn[] {
                    this.colList_ITEMCD});
                this.colList_ITEMCD.BindingField = "ITEMCD";
                this.colList_ITEMCD.AppearanceHeader.Options.UseFont = true;
                this.colList_ITEMCD.AppearanceHeader.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Center;
                this.colList_ITEMCD.AppearanceCell.Options.UseFont = true;
                """,
                encoding="utf-8",
            )

            resolved = resolve_author_tagged_style_evidence("sp_SA800100_SELECT", csharp_root=str(root))

        self.assertTrue(resolved.success, resolved.to_dict())
        self.assertTrue(all(resolved.metadata["path_exists"]))
        self.assertEqual("FrmDevBase", resolved.metadata["style_profile"]["base_class"])
        self.assertIn("SearchCommand", resolved.metadata["style_profile"]["command_handlers"])
        self.assertIn("@WORKTYPE", resolved.metadata["style_profile"]["db_parameters"])

    def test_author_tagged_style_evidence_blocks_stale_root_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = resolve_author_tagged_style_evidence("sp_SA800100_SELECT", csharp_root=temp_dir)

        self.assertFalse(resolved.success)
        self.assertEqual("stale_or_missing", resolved.metadata["status"])
        self.assertGreaterEqual(len(resolved.metadata["missing_style_evidence_paths"]), 1)

    def test_author_tagged_style_evidence_uses_bundled_program_profile_without_live_root(self):
        resolved = resolve_author_tagged_style_evidence("sp_SA800100_SELECT")

        self.assertTrue(resolved.success, resolved.to_dict())
        self.assertEqual("SA800100", resolved.metadata["program_key"])
        profile = resolved.metadata["style_profile"]
        self.assertEqual("FrmDevBase", profile["base_class"])
        self.assertIn("SA800100_SearchCommand", profile["method_names"])
        self.assertIn("@WORKTYPE", profile["db_parameters"])
        self.assertIn(
            {"client_method": "GetDataSetFromSP", "procedure": "sp_SA800100_SELECT"},
            profile["sp_calls"],
        )

    def test_build_plan_dict_state_preserves_author_tagged_fields(self):
        result = build_pb_to_csharp_migration_plan(
            "Migrate SA800100 using C_KONE110 style.",
            {
                "target_style": "C_KONE110",
                "procedure_name": "sp_SA800100_SELECT",
                "has_sp_style_reference": True,
            },
        )

        self.assertTrue(result.success, result.to_dict())
        resolution = result.metadata["author_tagged_style_resolution"]
        self.assertEqual("SA800100", resolution["program_key"])
        self.assertEqual("matched", resolution["status"])
        self.assertEqual("FrmDevBase", resolution["style_profile"]["base_class"])

    def test_migration_analysis_document_quality_blocks_short_log_level_summary(self):
        shallow = """
        # PB migration notes

        ## Objective
        Migrate PR100200 to C#.

        ## Implementation
        Add a button and create a stored procedure.
        """

        result = verify_pb_migration_analysis_document(shallow)

        self.assertFalse(result.success)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}
        self.assertNotIn("migration_analysis_document_too_short", issue_codes)
        self.assertNotIn("migration_analysis_heading_count_too_low", issue_codes)
        self.assertNotIn("migration_analysis_code_evidence_too_low", issue_codes)
        self.assertIn("migration_analysis_evidence_anchor_missing", issue_codes)
        self.assertIn("migration_analysis_readiness_missing", issue_codes)
        self.assertIn("migration_analysis_development_spec_missing", issue_codes)
        self.assertIn(
            "source_evidence",
            {
                issue.get("section")
                for issue in result.metadata["issues"]
                if issue["code"] == "migration_analysis_required_section_missing"
            },
        )

    def test_migration_analysis_document_quality_accepts_minimum_handoff_depth(self):
        document = """
        # PR100200 PB-to-C# migration analysis

        ## 1. Objective and target operator
        Objective: migrate the PowerBuilder production outsourcing workflow into a C# WinForms screen.
        Target operator: production planner who selects rows, chooses outsourcing items, and saves the result.

        ## 2. PB source evidence
        Source evidence: prod_003.pbl, prod_302_a.sru, linked SRW popup, and SRD DataWindow objects.
        The PB source trace records clicked event behavior, Retrieve arguments, DataWindow fields, and source gaps.

        ```powerscript
        // PB clicked event source evidence from prod_302_a.sru
        dw_main.AcceptText()
        if dw_main.GetRow() <= 0 then return
        ```

        ## 3. User workflow
        User workflow: select a production order row, click outsourcing, open popup, choose item, confirm save,
        refresh list, and verify the result in the grid.

        ## 4. C# implementation scope
        Target C# scope: WinForms form, DevExpress grid, Designer GridColumn members, BindingField assignments,
        popup result handling, DbParameter-based CallProc or CallViewQuery path, and refresh binding.

        ```csharp
        // target C# evidence
        dbClient.GetDataSetFromSP("sp_PR100200_SELECT", new DbParameter("@WORKTYPE", "LIST"));
        ```

        ## 5. Event and call flow
        Event/call flow: button click handler -> selected row validation -> duplicate outsourcing validation
        -> popup call -> save confirmation -> SP SAVE call -> grid refresh.

        ## 6. DB and SP mapping
        DB/SP mapping: SELECT branch returns target row data, SAVE branch performs INSERT into SA130T and UPDATE PR110T.
        @WORKTYPE distinguishes LIST, DETAIL, and SAVE semantics. No source-unbacked schema-only fallback is allowed.

        ```sql
        INSERT INTO SA130T (ORGDIV, ORDNUM, ORDSEQ)
        SELECT A.ORGDIV, A.ORDNUM, A.ORDSEQ
          FROM PR110T A
         WHERE A.ORGDIV = @ORGDIV;
        ```

        ## 7. Transaction and error handling
        transaction boundary: INSERT and UPDATE run in one transaction; rollback on validation failure.
        RAISERROR message is used for duplicate or completed-process conflicts.

        ```sql
        IF EXISTS (SELECT 1 FROM SA130T WHERE ORGDIV = @ORGDIV)
            RAISERROR('Already processed.', 16, 1);
        ```

        ## 8. Implementation order
        Implementation order: preserve existing button, comment old incompatible code, add popup call,
        add save SP branch, update Designer grid columns, then verify build and manual flow.

        ## 9. Constraints and business rules
        Required business rules: preserve ORDNUM + ORDSEQ key, do not save with ORDNUM alone,
        do not invent C# wildcard shaping, and keep source Korean literals unchanged.

        ## 10. Manual test scenarios
        Verification plan: normal save, popup cancel, duplicate outsourcing row, completed process conflict,
        grid refresh, SP rollback check, and C# build check.

        ```text
        manual test case: choose one valid row, select popup item, save, verify SA130T insert and PR110T update.
        ```

        ## 11. LLM implementation handoff
        LLM handoff: use this analysis as the migration contract. Implement C# and SP from the mapped PB behavior,
        not from generic screen assumptions. Block if PB source, C# target style, or SP evidence conflicts.

        ## 12. Cross-agent development specification
        Analysis agent output contract: this document is the development handoff for the developer agent.
        Developer agent must not re-infer PB behavior from chat context; use the target file plan and mapping tables.

        ### Target file plan
        | artifact | target file / class / procedure | implementation task | done criteria |
        | --- | --- | --- | --- |
        | C# screen | PR100200.cs | add button handler and CallProc path | build succeeds |
        | Designer | PR100200.Designer.cs | add explicit GridColumn members | BindingField and Caption match |
        | SQL procedure | sp_PR100200_SAVE procedure | add SAVE @WORKTYPE branch | SP contract passes review |

        ### PB event to C# event mapping
        | PB event | C# method / handler | validation | output |
        | --- | --- | --- | --- |
        | clicked | btnOutsourcing_Click handler | selected row and duplicate check | popup save call |

        ### DataWindow field mapping
        | DataWindow | PB column / field | C# control / GridColumn | BindingField | Caption |
        | --- | --- | --- | --- | --- |
        | dw_main | ORDNUM | colList_ORDNUM GridColumn | ORDNUM | Order No |
        | dw_main | ITEMCD | btnITEMCD control | ITEMCD | Item |

        ### Control layout and binding plan
        | control | type | BindingField | TabIndex | note |
        | --- | --- | --- | --- | --- |
        | lblITEMCD | LabelControl |  | 0 | item label |
        | btnITEMCD | ButtonEdit | ITEMCD | 1 | target control |
        | gvwList | GridView |  | 10 | list view |

        ### SP contract matrix
        | SP contract | @WORKTYPE | parameter | result column | DML |
        | --- | --- | --- | --- | --- |
        | sp_PR100200_SAVE | SAVE | @ORGDIV, @XML | ORDNUM, ORDSEQ | INSERT SA130T / UPDATE PR110T |

        ### Style profile contract
        Author-tagged style profile: use program key PR100200. If unmapped, use fallback program PR300100
        with source hash and Designer hash evidence before applying style patterns.

        ### Implementation task list
        1. implementation task: update PR100200.cs handler; acceptance: selected row validation is preserved.
        2. implementation task: update PR100200.Designer.cs grid columns; done criteria: explicit AddRange columns exist.
        3. implementation task: update SQL SAVE branch; acceptance: transaction and RAISERROR behavior match.

        ### Verification contract
        manual test: save one valid row. expected UI: grid refresh shows the saved row.
        expected DB: SA130T insert and PR110T update exist. build and rollback checks must pass.

        ### Confirmed / inferred / blocked split
        confirmed: PB clicked event and DataWindow columns. inferred: popup captions when SRD text is absent.
        blocked: source parity remains blocked if the PBL export or SP schema conflicts with this document.
        """

        result = verify_pb_migration_analysis_document(document)

        self.assertTrue(result.success, result.to_dict())
        self.assertLess(result.metadata["line_count"], 350)
        self.assertTrue(all(result.metadata["section_coverage"].values()))
        self.assertTrue(all(result.metadata["evidence_anchor_coverage"].values()))
        self.assertTrue(all(result.metadata["development_spec_coverage"].values()))
        self.assertTrue(all(result.metadata["readiness"].values()))
        self.assertTrue(result.metadata["cross_agent_contract"]["developer_agent_handoff_ready"])

    def test_generated_csharp_style_requires_author_tagged_evidence_when_enabled(self):
        missing = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("sp_SA900100_SELECT");',
            program_key="SA800100",
            require_author_tagged_evidence=True,
        )
        self.assertFalse(missing.success)
        self.assertIn("author_tagged_style_evidence_required", {issue["code"] for issue in missing.metadata["issues"]})

        present = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("sp_SA800100_SELECT", new DbParameter("@WORKTYPE", "LIST"));',
            program_key="SA800100",
            primary_style_evidence_paths=[
                r"Programs\20.??(SA)\Konesystem.SA02\SA800100.cs",
                r"Programs\20.??(SA)\Konesystem.SA02\SA800100.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )
        self.assertTrue(present.success, present.to_dict())
        self.assertEqual("SA800100", present.metadata["expected_style_program_key"])
        self.assertIn("author_tagged_generation_recipe", present.metadata)

    def test_generated_csharp_style_blocks_wrong_author_tagged_evidence_path(self):
        result = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("sp_SA800100_SELECT", new DbParameter("@WORKTYPE", "LIST"));',
            program_key="SA800100",
            primary_style_evidence_paths=[
                r"Programs\60.??(DE)\Konesystem.DE01\DE000600.cs",
                r"Programs\60.??(DE)\Konesystem.DE01\DE000600.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )

        self.assertFalse(result.success)
        self.assertIn("author_tagged_style_evidence_path_mismatch", {issue["code"] for issue in result.metadata["issues"]})

    def test_generated_csharp_style_rejects_same_filename_without_module_tail(self):
        result = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("sp_SA800100_SELECT", new DbParameter("@WORKTYPE", "LIST"));',
            program_key="SA800100",
            primary_style_evidence_paths=[
                r"C:\tmp\SA800100.cs",
                r"C:\tmp\SA800100.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )

        self.assertFalse(result.success)
        self.assertIn("author_tagged_style_evidence_path_mismatch", {issue["code"] for issue in result.metadata["issues"]})

    def test_generated_csharp_style_requires_fallback_for_excluded_author_target(self):
        missing_fallback = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("SP_SA900100_SELECT", new DbParameter("@WORKTYPE", "LIST"));',
            program_key="SA900100",
            primary_style_evidence_paths=[
                r"Programs\20.??(SA)\Konesystem.SA02\SA800100.cs",
                r"Programs\20.??(SA)\Konesystem.SA02\SA800100.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )
        self.assertFalse(missing_fallback.success)
        self.assertIn("author_tagged_fallback_program_key_required", {issue["code"] for issue in missing_fallback.metadata["issues"]})

        with_fallback = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("SP_SA900100_SELECT", new DbParameter("@WORKTYPE", "LIST"));',
            program_key="SA900100",
            fallback_program_key="SA800100",
            primary_style_evidence_paths=[
                r"Programs\20.??(SA)\Konesystem.SA02\SA800100.cs",
                r"Programs\20.??(SA)\Konesystem.SA02\SA800100.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )
        self.assertTrue(with_fallback.success, with_fallback.to_dict())

    def test_generated_csharp_style_blocks_bare_sp_call_under_author_tagged_mode(self):
        result = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("sp_SA800100_SELECT");',
            program_key="SA800100",
            primary_style_evidence_paths=[
                r"Programs\20.??(SA)\Konesystem.SA02\SA800100.cs",
                r"Programs\20.??(SA)\Konesystem.SA02\SA800100.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )

        self.assertFalse(result.success)
        self.assertIn("author_tagged_sp_call_missing_explicit_dbparameters", {issue["code"] for issue in result.metadata["issues"]})

    def test_generated_csharp_style_blocks_bare_exec_sp_calls_under_author_tagged_mode(self):
        result = verify_migration_generated_csharp_style(
            'dbClient.ExecSP("sp_SA800100_SAVE");',
            program_key="SA800100",
            primary_style_evidence_paths=[
                r"Programs\20.??(SA)\Konesystem.SA02\SA800100.cs",
                r"Programs\20.??(SA)\Konesystem.SA02\SA800100.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )

        self.assertFalse(result.success)
        self.assertIn("author_tagged_sp_call_missing_explicit_dbparameters", {issue["code"] for issue in result.metadata["issues"]})

    def test_generated_csharp_style_blocks_unverified_devexpress_package_or_version(self):
        generated = '''
        <PackageReference Include="DevExpress.Win.Design" Version="26.1.0" />
        dotnet add package DevExpress.Win
        using DevExpress.XtraGrid;
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_devexpress_package_reference_detected", issue_codes)

        version_ref = verify_migration_generated_csharp_style(
            'using DevExpress.XtraGrid, Version=26.1.0; // unverified target reference'
        )
        version_issue_codes = {issue["code"] for issue in version_ref.metadata["issues"]}
        self.assertFalse(version_ref.success)
        self.assertIn("generated_unverified_devexpress_version_reference_detected", version_issue_codes)

    def test_generated_csharp_style_blocks_patterns_absent_from_matched_sources(self):
        generated = '''
        private void CallDetailQuery()
        {
            DataRow dr = gvwList.GetFocusedDataRow();
            string custcd = dr["CUSTCD"] == DBNull.Value ? string.Empty : dr["CUSTCD"].ToString().Trim();
            string itemcd = dr["PRNTITEMCD"] == DBNull.Value ? string.Empty : dr["PRNTITEMCD"].ToString().Trim();
            itemcd = string.IsNullOrEmpty(itemcd) ? "%" : itemcd + "%";
            DataSet ds = CallSelectProcedure(SelectType.DETAIL, custcd, itemcd);
        }

        private DataSet CallSelectProcedure(SelectType _selectType, string _custcd = null, string _itemcd = null)
        {
            string gubun = Convert.ToString(radGUBUN.EditValue);
            string gb = Convert.ToString(radGB.EditValue);
            string custcd = btnCUSTCD.EditValue == null ? string.Empty : btnCUSTCD.EditValue.ToString().Trim();
            string itemcd = _selectType == SelectType.DETAIL ? (_itemcd ?? "%") : "%";
            return dbClient.GetDataSetFromSP("sp_SA900100_SELECT");
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_dbnull_ternary_row_value_detected", issue_codes)
        self.assertIn("generated_call_detail_query_helper_detected", issue_codes)
        self.assertIn("generated_selecttype_detail_ternary_detected", issue_codes)
        self.assertIn("generated_percent_null_coalesce_detected", issue_codes)
        self.assertIn("generated_buttonedit_null_stringempty_ternary_detected", issue_codes)
        self.assertIn("generated_radio_convert_tostring_local_detected", issue_codes)

    def test_generated_csharp_style_blocks_sa900100_leftover_generated_patterns(self):
        generated = '''
        private void SA900100_SearchCommand(object sender, SearchCommandEventArgs e)
        {
            if (ymdGIJUN.EditValue == null)
                ymdGIJUN.SetToDay(0);

            DataSet ds = CallSelectProcedure(SelectType.LIST, btnCUSTCD.Text + "%", "%");
        }

        private void CallDetailQuery()
        {
            DataRow dr = gvwList.GetFocusedDataRow();
            DataSet ds = CallSelectProcedure(SelectType.DETAIL, dr["CUSTCD"].ToString(), dr["PRNTITEMCD"].ToString() + "%");
        }

        private DataSet CallSelectProcedure(SelectType _selectType, string _custcd, string _itemcd)
        {
            DateTime lastdt = new DateTime(DateTime.Now.Year, DateTime.Now.Month, 1).AddDays(-1);
            if (ymdGIJUN.DateTime.Year != lastdt.Year)
                lastdt = new DateTime(ymdGIJUN.DateTime.Year - 1, 12, 31);

            return dbClient.GetDataSetFromSP("sp_SA900100_SELECT");
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_callselect_inline_wildcard_argument_detected", issue_codes)
        self.assertIn("generated_call_detail_query_helper_detected", issue_codes)
        self.assertIn("generated_dateedit_settoday_null_default_detected", issue_codes)
        self.assertIn("generated_month_end_datetime_block_detected", issue_codes)
        self.assertIn("generated_year_end_datetime_block_detected", issue_codes)

    def test_generated_csharp_style_allows_focused_row_changed_style_name(self):
        generated = '''
        private void fnFocusedRowChanged()
        {
            DataRow dr = gvwList.GetFocusedDataRow();
            if (dr == null || gvwList.FocusedRowHandle < 0)
            {
                devFnc.InitControl(grdDetail);
                return;
            }

            DataSet ds = CallSelectProcedure(SelectType.DETAIL, dr["CUSTCD"].ToString(), dr["PRNTITEMCD"].ToString());
            grdDetail.DataSource = ds.Tables[0];
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertNotIn("generated_call_detail_query_helper_detected", issue_codes)

    def test_generated_csharp_style_blocks_csharp_sp_parameter_shaping(self):
        generated = '''
        private DataSet CallSelectProcedure(SelectType _selectType, string _custcd, string _itemcd)
        {
            DateTime basdt = DateTime.Now.AddDays(1 - DateTime.Now.Day).AddDays(-1);
            string custcd = _custcd;
            string itemcd = _itemcd;
            string lastdt = basdt.ToString("yyyyMMdd");

            if (ymdGIJUN.DateTime.Year != basdt.Year)
                lastdt = (ymdGIJUN.DateTime.Year - 1).ToString("0000") + "1231";

            if (_selectType == SelectType.LIST)
            {
                custcd = btnCUSTCD.Text;
                if (string.IsNullOrEmpty(custcd))
                    custcd = "%";
                else
                    custcd = custcd + "%";

                itemcd = "%";
            }
            else if (_selectType == SelectType.DETAIL)
            {
                itemcd = itemcd + "%";
            }

            return dbClient.GetDataSetFromSP("sp_SA900100_SELECT");
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_csharp_like_wildcard_shaping_detected", issue_codes)
        self.assertIn("generated_month_end_datetime_block_detected", issue_codes)
        self.assertIn("generated_year_end_string_boundary_detected", issue_codes)

    def test_generated_csharp_style_blocks_dateedit_split_date_parameters(self):
        generated = '''
        return dbClient.GetDataSetFromSP("sp_SA900100_SELECT"
                , new DbParameter("@WORKTYPE", _selectType.ToString())
                , new DbParameter("@ORGDIV", userInfo.Orgdiv)
                , new DbParameter("@CUSTCD", _custcd)
                , new DbParameter("@YYYY", ymdGIJUN.DateTime.Year.ToString())
                , new DbParameter("@MM", DateTime.Now.Month.ToString("00"))
                , new DbParameter("@BASYYYY", DateTime.Now.Year.ToString())
                , new DbParameter("@GUBUN", radGUBUN.EditValue)
                , new DbParameter("@GB", radGB.EditValue)
                , new DbParameter("@ITEMCD", _itemcd)
                );
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_dateedit_year_or_now_parameter_shaping_detected", issue_codes)

    def test_generated_csharp_style_blocks_direct_grid_datasource_null_reset(self):
        generated = '''
        private void Search()
        {
            grdDetail.DataSource = null;
            grdList.DataSource = null;
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_direct_grid_datasource_null_reset_detected", issue_codes)

    def test_generated_csharp_style_blocks_dbnull_and_helper_variants(self):
        generated = '''
        private class SearchParams
        {
            public string CUSTCD { get; set; }
        }

        private DataSet CallSelectProcedure(SelectType _selectType, string _custcd = "", string _itemcd = "%")
        {
            DataRow dr = gvwList.GetFocusedDataRow();
            string custcd = Convert.IsDBNull(dr["CUSTCD"]) ? string.Empty : dr["CUSTCD"].ToString();
            string itemcd = dr.IsNull("ITEMCD") ? string.Empty : dr["ITEMCD"].ToString();
            object qty = gvwList.GetFocusedRowCellValue("QTY") == DBNull.Value ? 0 : gvwList.GetFocusedRowCellValue("QTY");
            if (dr["ORDNUM"] is DBNull)
                return null;
            return dbClient.GetDataSetFromSP("sp_SA900100_SELECT");
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_private_parameter_helper_class_detected", issue_codes)
        self.assertIn("generated_callselect_string_literal_default_detected", issue_codes)
        self.assertIn("generated_convert_isdbnull_ternary_detected", issue_codes)
        self.assertIn("generated_datarow_isnull_ternary_detected", issue_codes)
        self.assertIn("generated_focused_cell_dbnull_check_detected", issue_codes)
        self.assertIn("generated_is_dbnull_check_detected", issue_codes)

    def test_generated_csharp_style_blocks_name_text_field_as_dateedit(self):
        generated = '''
        private KoneLib.Controls.u_DateEdit txtCUSTNM;
        this.txtCUSTNM = new KoneLib.Controls.u_DateEdit();
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("text_name_field_generated_as_dateedit", issue_codes)

    def test_grid_column_designer_plan_uses_explicit_target_column_names(self):
        result = build_csharp_grid_column_designer_plan(
            [
                {"field_name": "CUSTNM", "caption": "고객", "width": 160},
                {"field_name": "AMTTOT", "caption": "합계", "width": 120},
                {"field_name": "PRICE", "caption": "단가", "width": 100},
            ],
            input_format="list",
        )

        self.assertTrue(result.success, result.to_dict())
        self.assertIn("private DevExpress.XtraGrid.Columns.GridColumn colList_CUSTNM;", result.stdout)
        self.assertIn("this.gvwList.Columns.AddRange", result.stdout)
        self.assertIn('this.colList_CUSTNM.FieldName = "CUSTNM";', result.stdout)
        self.assertIn('this.colList_CUSTNM.Name = "colList_CUSTNM";', result.stdout)
        self.assertIn("private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit rpsSpinAmt;", result.stdout)
        self.assertIn("this.grdList.RepositoryItems.AddRange", result.stdout)
        self.assertIn("this.colList_AMTTOT.ColumnEdit = this.rpsSpinAmt;", result.stdout)
        self.assertIn("this.colList_PRICE.ColumnEdit = this.rpsSpinAmt;", result.stdout)
        self.assertNotIn(".DisplayFormat.FormatString", result.stdout)
        self.assertNotIn("AddGridColumn", result.stdout)
        self.assertNotIn("Columns.AddField", result.stdout)

    def test_sp_generation_contract_blocks_missing_sql_or_unbacked_full_sp(self):
        missing = verify_pb_migration_sp_generation_contract("")
        self.assertFalse(missing.success)
        self.assertIn("missing_sql_text", {issue["code"] for issue in missing.metadata["issues"]})

        unbacked = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS CUSTNM
    END
END
""",
            source_evidence=False,
        )
        issue_codes = {issue["code"] for issue in unbacked.metadata["issues"]}
        self.assertFalse(unbacked.success)
        self.assertIn("missing_pb_or_db_source_evidence_for_sp_generation", issue_codes)

        bool_flag = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS CUSTNM
    END
END
""",
            source_evidence=True,
        )
        self.assertFalse(bool_flag.success)
        self.assertIn("unstructured_source_evidence_flag", {issue["code"] for issue in bool_flag.metadata["issues"]})

        no_header = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS CUSTNM
    END
END
""",
            source_evidence={"kind": "pb_srd_sql", "path": "d_saoth_070_a_1.srd", "summary": "retrieve SQL"},
        )
        self.assertFalse(no_header.success)
        self.assertIn("missing_sp_metadata_header", {issue["code"] for issue in no_header.metadata["issues"]})

        copied_wrong_description = verify_pb_migration_sp_generation_contract(
            sp_metadata_header("총괄조회 조회")
            + """
CREATE OR ALTER PROCEDURE [dbo].[sp_DE000600_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DWGNO
    END
END
""",
            source_evidence={
                "kind": "existing_sp",
                "object": "sp_DE000600_SELECT",
                "verified": True,
                "definition_hash": "18B35CA51C9BBBCC3F6C7EE0481799D5B8922CD58FEC20DCB3C07E673D0120A2",
                "program_description": "설계조회",
            },
        )
        copied_issue_codes = {issue["code"] for issue in copied_wrong_description.metadata["issues"]}
        self.assertFalse(copied_wrong_description.success)
        self.assertIn("sp_metadata_description_mismatch", copied_issue_codes)
        self.assertIn("sp_metadata_description_not_program_specific", copied_issue_codes)

        matched_program_description = verify_pb_migration_sp_generation_contract(
            sp_metadata_header("설계조회 조회")
            + """
CREATE OR ALTER PROCEDURE [dbo].[sp_DE000600_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DWGNO
    END
END
""",
            source_evidence={
                "kind": "existing_sp",
                "object": "sp_DE000600_SELECT",
                "verified": True,
                "definition_hash": "18B35CA51C9BBBCC3F6C7EE0481799D5B8922CD58FEC20DCB3C07E673D0120A2",
                "program_description": "설계조회",
            },
        )
        self.assertTrue(matched_program_description.success, matched_program_description.metadata["issues"])

        allowed = verify_pb_migration_sp_generation_contract(
            sp_metadata_header()
            + """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS CUSTNM
    END
END
""",
            source_evidence={"kind": "pb_srd_sql", "path": "d_saoth_070_a_1.srd", "summary": "retrieve SQL"},
        )
        self.assertTrue(allowed.success, allowed.metadata["issues"])

        fake_existing_sp = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS CUSTNM
    END
END
""",
            source_evidence={"kind": "existing_sp", "object": "sp_FAKE"},
        )
        self.assertFalse(fake_existing_sp.success)
        self.assertIn(
            "missing_pb_or_db_source_evidence_for_sp_generation",
            {issue["code"] for issue in fake_existing_sp.metadata["issues"]},
        )

        fake_existing_sp_summary = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS CUSTNM
    END
END
""",
            source_evidence={"kind": "existing_sp", "object": "sp_FAKE", "summary": "claimed existing procedure"},
        )
        self.assertFalse(fake_existing_sp_summary.success)
        self.assertIn(
            "missing_pb_or_db_source_evidence_for_sp_generation",
            {issue["code"] for issue in fake_existing_sp_summary.metadata["issues"]},
        )

        object_only_verified_sp = verify_pb_migration_sp_generation_contract(
            sp_metadata_header()
            + """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS CUSTNM
    END
END
""",
            source_evidence={"kind": "existing_sp", "object": "sp_SA900100_SELECT", "verified": True},
        )
        self.assertFalse(object_only_verified_sp.success)
        self.assertIn(
            "missing_pb_or_db_source_evidence_for_sp_generation",
            {issue["code"] for issue in object_only_verified_sp.metadata["issues"]},
        )

        excerpt_only_existing_sp = verify_pb_migration_sp_generation_contract(
            sp_metadata_header()
            + """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS CUSTNM
    END
END
""",
            source_evidence={
                "kind": "existing_sp",
                "object": "sp_SA900100_SELECT",
                "verified": True,
                "definition_excerpt": "SELECT 1",
            },
        )
        self.assertFalse(excerpt_only_existing_sp.success)
        self.assertIn(
            "missing_pb_or_db_source_evidence_for_sp_generation",
            {issue["code"] for issue in excerpt_only_existing_sp.metadata["issues"]},
        )

        verified_existing_sp = verify_pb_migration_sp_generation_contract(
            sp_metadata_header()
            + """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS CUSTNM
    END
END
""",
            source_evidence={
                "kind": "existing_sp",
                "object": "sp_SA900100_SELECT",
                "verified": True,
                "definition_hash": "954465F0F0D81341EF6527FC33A7B4CE916E4A86DAE4810E86A1301242609376",
            },
        )
        self.assertTrue(verified_existing_sp.success, verified_existing_sp.metadata["issues"])

        cte = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    ;WITH A AS (SELECT 1 AS X)
    SELECT X FROM A
END
""",
            source_evidence={"kind": "pb_srd_sql", "path": "d_saoth_070_a_1.srd"},
        )
        self.assertFalse(cte.success)
        self.assertIn("cte_in_generated_sp", {issue["code"] for issue in cte.metadata["issues"]})

        schema_fallback = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT TOP 0
           CAST('' AS VARCHAR(20)) AS ORDNUM
         , CAST(0 AS DECIMAL(18, 4)) AS QTY;
END
""",
            source_evidence={"kind": "pb_srd_sql", "path": "d_saoth_070_a_2.srd"},
        )
        self.assertFalse(schema_fallback.success)
        self.assertIn(
            "schema_only_select_top_0_fallback_in_generated_sp",
            {issue["code"] for issue in schema_fallback.metadata["issues"]},
        )

        schema_fallback_convert = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_SA900100_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT TOP (0)
           CONVERT(VARCHAR(20), '') AS ORDNUM
         , TRY_CONVERT(DECIMAL(18, 4), 0) AS QTY;
END
""",
            source_evidence={"kind": "pb_srd_sql", "path": "d_saoth_070_a_2.srd"},
        )
        self.assertFalse(schema_fallback_convert.success)
        self.assertIn(
            "schema_only_select_top_0_fallback_in_generated_sp",
            {issue["code"] for issue in schema_fallback_convert.metadata["issues"]},
        )

    def test_sp_generation_contract_blocks_generated_parameter_defaults_and_normalization(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_SA900100_SELECT]
      @WORKTYPE VARCHAR(20) = ''
    , @ORGDIV   VARCHAR(2)  = ''
    , @CUSTCD   VARCHAR(20) = '%'
    , @GUBUN    VARCHAR(1)  = 'T'
    , @GB       VARCHAR(1)  = '1'
    , @ITEMCD   VARCHAR(30) = '%'
AS
BEGIN
    SET NOCOUNT ON;

    SET @WORKTYPE = ISNULL(@WORKTYPE, '');
    SET @CUSTCD = (CASE WHEN ISNULL(@CUSTCD, '') = '' THEN '%' ELSE @CUSTCD END);
    SELECT @ITEMCD = COALESCE(@ITEMCD, '%');
    SET @GUBUN = NULLIF(@GUBUN, '');
    IF ISNULL(@GB, '') = ''
        SET @GB = '1';
    SET @CUSTCD = LTRIM(RTRIM(@CUSTCD));

    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT A.CUSTNM
        FROM BA020T A;
    END
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "existing_sp", "object": "sp_SA900100_SELECT", "verified": True},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("worktype_empty_string_default_detected", issue_codes)
        self.assertIn("wildcard_filter_parameter_default_detected", issue_codes)
        self.assertIn("business_flag_parameter_default_detected", issue_codes)
        self.assertIn("worktype_isnull_normalization_detected", issue_codes)
        self.assertIn("case_isnull_parameter_normalization_detected", issue_codes)
        self.assertIn("set_isnull_parameter_normalization_detected", issue_codes)
        self.assertIn("set_coalesce_parameter_normalization_detected", issue_codes)
        self.assertIn("set_nullif_parameter_normalization_detected", issue_codes)
        self.assertIn("if_isnull_parameter_normalization_detected", issue_codes)
        self.assertIn("trim_parameter_normalization_detected", issue_codes)

    def test_sp_generation_contract_blocks_derived_date_helper_parameters_and_if_defaults(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_SA900100_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ORGDIV   VARCHAR(2)
    , @GIJUNDT  VARCHAR(8)
    , @YYYY     VARCHAR(4)
    , @MM       VARCHAR(2)
    , @BASYYYY  VARCHAR(4)
    , @LASTDT   VARCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;

    IF ISNULL(@GIJUNDT, '') <> ''
    BEGIN
        SET @YYYY = LEFT(@GIJUNDT, 4);
        SET @MM = SUBSTRING(@GIJUNDT, 5, 2);
    END;

    IF ISNULL(@YYYY, '') = ''
        SET @YYYY = CONVERT(VARCHAR(4), YEAR(GETDATE()));

    IF ISNULL(@MM, '') = ''
        SET @MM = RIGHT('0' + CONVERT(VARCHAR(2), MONTH(GETDATE())), 2);

    IF ISNULL(@BASYYYY, '') = ''
        SET @BASYYYY = CONVERT(VARCHAR(4), YEAR(GETDATE()));

    IF ISNULL(@LASTDT, '') = ''
    BEGIN
        SET @LASTDT = CONVERT(VARCHAR(8), DATEADD(DAY, -DAY(GETDATE()), GETDATE()), 112);

        IF @YYYY <> LEFT(@LASTDT, 4)
            SET @LASTDT = CONVERT(VARCHAR(4), CONVERT(INT, @YYYY) - 1) + '1231';
    END;

    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT A.CUSTNM
        FROM BA020T A;
    END
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "pb_srd_sql", "path": "d_sa900100.srd", "summary": "retrieve SQL"},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("derived_date_helper_parameter_detected", issue_codes)
        self.assertIn("if_isnull_date_derivation_block_detected", issue_codes)
        self.assertIn("generated_if_wrapped_date_set_block_detected", issue_codes)

    def test_sp_generation_contract_allows_local_declared_date_helpers_without_if_defaults(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_SA900100_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ORGDIV   VARCHAR(2)
    , @GIJUNDT  VARCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @YYYY    VARCHAR(4)
          , @MM      VARCHAR(2)
          , @BASYYYY VARCHAR(4)
          , @LASTDT  VARCHAR(8);

    SET @YYYY = LEFT(@GIJUNDT, 4);
    SET @MM = SUBSTRING(@GIJUNDT, 5, 2);
    SET @BASYYYY = CONVERT(VARCHAR(4), YEAR(GETDATE()));
    SET @LASTDT = CONVERT(VARCHAR(8), DATEADD(DAY, -DAY(GETDATE()), GETDATE()), 112);

    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT A.CUSTNM
        FROM BA020T A;
    END
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "pb_srd_sql", "path": "d_sa900100.srd", "summary": "retrieve SQL"},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertNotIn("derived_date_helper_parameter_detected", issue_codes)
        self.assertNotIn("if_isnull_date_derivation_block_detected", issue_codes)
        self.assertNotIn("generated_if_wrapped_date_set_block_detected", issue_codes)

    def test_sp_generation_contract_blocks_alter_procedure_derived_helper_parameters(self):
        generated = sp_metadata_header() + """
ALTER PROCEDURE [DBO].[SP_SA900100_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ORGDIV   VARCHAR(2)
    , @GIJUNDT  VARCHAR(8)
    , @YYYY     VARCHAR(4)
AS
BEGIN
    SELECT A.CUSTNM
    FROM BA020T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "pb_srd_sql", "path": "d_sa900100.srd", "summary": "retrieve SQL"},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("derived_date_helper_parameter_detected", issue_codes)

    def test_sp_generation_contract_blocks_parenthesized_date_isnull_defaults(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_SA900100_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ORGDIV   VARCHAR(2)
    , @GIJUNDT  VARCHAR(8)
AS
BEGIN
    DECLARE @YYYY VARCHAR(4);

    IF (ISNULL(@GIJUNDT, '') = '')
        SET @YYYY = CONVERT(VARCHAR(4), YEAR(GETDATE()));

    SELECT A.CUSTNM
    FROM BA020T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "pb_srd_sql", "path": "d_sa900100.srd", "summary": "retrieve SQL"},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("if_isnull_date_derivation_block_detected", issue_codes)
        self.assertIn("generated_if_wrapped_date_set_block_detected", issue_codes)

    def test_sp_generation_contract_blocks_direct_if_wrapped_date_set(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_SA900100_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ORGDIV   VARCHAR(2)
    , @GIJUNDT  VARCHAR(8)
AS
BEGIN
    DECLARE @YYYY VARCHAR(4);

    IF @GIJUNDT <> ''
        SET @YYYY = CONVERT(VARCHAR(4), @GIJUNDT);

    SELECT A.CUSTNM
    FROM BA020T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "pb_srd_sql", "path": "d_sa900100.srd", "summary": "retrieve SQL"},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_if_wrapped_date_set_block_detected", issue_codes)

    def test_sp_generation_contract_blocks_non_caller_helper_parameters_when_csharp_params_known(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_SA900100_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ORGDIV   VARCHAR(2)
    , @GIJUNDT  VARCHAR(8)
    , @ROWCNT   INT
AS
BEGIN
    SELECT A.CUSTNM
    FROM BA020T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence=[
                {"kind": "pb_srd_sql", "path": "d_sa900100.srd", "summary": "retrieve SQL"},
                {
                    "kind": "csharp_call",
                    "path": "SA900100.cs",
                    "db_parameters": ["@WORKTYPE", "@ORGDIV", "@GIJUNDT"],
                },
            ],
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("non_caller_procedure_parameter_detected", issue_codes)

    def test_sp_generation_contract_blocks_non_caller_parameters_with_broader_sql_types(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_SA900100_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ORGDIV   VARCHAR(2)
    , @GIJUNDT  VARCHAR(8)
    , @ROWNUM   INTEGER
    , @ROWGUID  UNIQUEIDENTIFIER
    , @FILEBIN  VARBINARY(MAX)
    , @RUNTIME  DATETIME2
AS
BEGIN
    SELECT A.CUSTNM
    FROM BA020T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence=[
                {"kind": "pb_srd_sql", "path": "d_sa900100.srd", "summary": "retrieve SQL"},
                {
                    "kind": "csharp_call",
                    "path": "SA900100.cs",
                    "db_parameters": ["@WORKTYPE", "@ORGDIV", "@GIJUNDT"],
                },
            ],
        )
        non_caller_issue = next(
            issue
            for issue in result.metadata["issues"]
            if issue["code"] == "non_caller_procedure_parameter_detected"
        )

        self.assertFalse(result.success)
        self.assertIn("@ROWNUM", non_caller_issue["parameters"])
        self.assertIn("@ROWGUID", non_caller_issue["parameters"])
        self.assertIn("@FILEBIN", non_caller_issue["parameters"])
        self.assertIn("@RUNTIME", non_caller_issue["parameters"])

    def test_sp_generation_contract_allows_parameters_matching_csharp_call_evidence(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_SA900100_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ORGDIV   VARCHAR(2)
    , @GIJUNDT  VARCHAR(8)
AS
BEGIN
    DECLARE @ROWCNT INT;

    SET @ROWCNT = 0;

    SELECT A.CUSTNM
    FROM BA020T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence=[
                {"kind": "pb_srd_sql", "path": "d_sa900100.srd", "summary": "retrieve SQL"},
                {
                    "kind": "csharp_call",
                    "path": "SA900100.cs",
                    "db_parameters": ["@WORKTYPE", "@ORGDIV", "@GIJUNDT"],
                },
            ],
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertNotIn("non_caller_procedure_parameter_detected", issue_codes)

    def test_composed_sp_and_sql_formatting_verifier_requires_both_gates(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_SA900100_SELECT]
      @WORKTYPE    VARCHAR(20) = NULL
    , @ORGDIV      VARCHAR(2)  = NULL
AS
BEGIN
    SELECT A.ORDNUM
    FROM SA100T A
    WHERE A.ORGDIV = @ORGDIV;
END
"""
        result = verify_pb_migration_sp_with_sql_formatting(
            sql,
            sql,
            source_evidence={"kind": "pb_srd_sql", "path": "d_saoth_070_a_1.srd"},
        )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["sp_generation_contract"]["status"], "passed")
        self.assertEqual(result.metadata["sql_formatting_style"]["mechanical_checks"]["status"], "passed")

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
