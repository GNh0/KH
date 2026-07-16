import hashlib
import json
import runpy
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from src.orchestration.kh_front_door import build_kh_front_door
from src.orchestration.request_classifier import classify_request
from src.skills import pb_to_csharp_migration as pb_migration
from src.skills.pb_to_csharp_migration import (
    CompositeBusinessKeyDisplayObservation,
    CompositeBusinessKeyDisplaySpec,
    MigrationInputState,
    build_author_tagged_style_profile_update,
    build_migration_profile_update,
    build_offline_pb_to_csharp_runtime_generation,
    build_pbl_export_strategy,
    build_csharp_grid_column_designer_plan,
    build_detail_form_layout_plan,
    build_csharp_control_name,
    build_csharp_grid_column_name,
    build_composite_business_key_display_plan,
    build_datawindow_grid_layout,
    build_datawindow_gridview_designer_defaults,
    build_pb_to_csharp_migration_plan,
    classify_migration_mode,
    extract_datawindow_column_specs,
    extract_datawindow_columns,
    extract_csharp_designer_control_specs,
    generate_devexpress_grid_xml,
    verify_devexpress_grid_xml_contract,
    verify_composite_business_key_display_contract,
    get_author_tagged_csharp_style_baseline,
    load_packaged_migration_profile,
    normalize_author_tagged_program_key,
    orchestrate_pb_migration_validation,
    resolve_author_tagged_style_evidence,
    verify_migration_generated_csharp_style as _verify_migration_generated_csharp_style,
    verify_pb_migration_analysis_document,
    verify_pb_migration_sp_generation_contract as _verify_pb_migration_sp_generation_contract,
    verify_pb_migration_sp_with_sql_formatting as _verify_pb_migration_sp_with_sql_formatting,
    resolve_csharp_grid_control_names,
    resolve_csharp_grid_column_prefix,
    resolve_csharp_control_stack,
)
from src.skills.uaf_skill_catalog import read_packaged_skill


def sp_metadata_header(description="Synthetic procedure contract"):
    return f"""-- =============================================
-- AUTHOR:      <maintainer>
-- CREATE DATE: 2026-06-15
-- DESCRIPTION: {description}
-- =============================================
"""


def packaged_profile_payload(
    *,
    profile_id="pb-csharp-offline-generalized",
    version="1.0",
    csharp_required_patterns=None,
    csharp_forbidden_patterns=None,
    sql_allowed_procedure_patterns=None,
    sql_forbidden_patterns=None,
):
    source = Path("skills/pb_to_csharp_migration_harness/references/packaged-style-contract.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["contract_id"] = profile_id
    payload["contract_version"] = version
    csharp_rules = payload["rules"]["csharp"]
    sql_rules = payload["rules"]["sql"]
    if csharp_required_patterns is not None:
        csharp_rules["required_patterns"] = csharp_required_patterns
    if csharp_forbidden_patterns is not None:
        csharp_rules["forbidden_patterns"] = csharp_forbidden_patterns
    if sql_allowed_procedure_patterns is not None:
        sql_rules["allowed_procedure_patterns"] = sql_allowed_procedure_patterns
    if sql_forbidden_patterns is not None:
        sql_rules["forbidden_patterns"] = sql_forbidden_patterns
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return payload, "sha256:" + hashlib.sha256(raw).hexdigest()


def write_packaged_profile(directory, **kwargs):
    payload, _ = packaged_profile_payload(**kwargs)
    path = Path(directory) / "packaged-style-contract.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    profile_hash = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return path, profile_hash


def loaded_test_profile(**kwargs):
    with tempfile.TemporaryDirectory() as temp_dir:
        profile_path, profile_hash = write_packaged_profile(temp_dir, **kwargs)
        with patch_runtime_profile_path(profile_path):
            return load_packaged_migration_profile(
                kwargs.get("profile_id", "pb-csharp-offline-generalized"),
                kwargs.get("version", "1.0"),
                profile_hash,
            )


def loaded_sp_test_profile():
    return loaded_test_profile(
        csharp_required_patterns=[],
        sql_allowed_procedure_patterns=[r"^SP_[A-Z0-9_]+_(?:SELECT|SAVE)$"],
    )


def valid_csharp_contract_sources(form_class="InventoryBrowseForm", field_name="ENTITY_ID"):
    code_behind = f'''
    public partial class {form_class} : System.Windows.Forms.Form
    {{
        public {form_class}()
        {{
            InitializeComponent();
        }}

        protected void SearchCommand()
        {{
            CallSelectProcedure();
        }}

        private void CallSelectProcedure()
        {{
            this.grdList.DataSource = result;
        }}
    }}
    '''
    designer = f'''
    partial class {form_class}
    {{
        private System.Windows.Forms.DataGridView grdList;
        private System.Windows.Forms.DataGridViewTextBoxColumn colList_{field_name};

        private void InitializeComponent()
        {{
            this.grdList = new System.Windows.Forms.DataGridView();
            this.colList_{field_name} = new System.Windows.Forms.DataGridViewTextBoxColumn();
            this.colList_{field_name}.Name = "colList_{field_name}";
            this.colList_{field_name}.DataPropertyName = "{field_name}";
            this.grdList.Columns.AddRange(this.colList_{field_name});
        }}
    }}
    '''
    return code_behind, designer


def non_code_csharp_contract_sources():
    comment_only = r'''
    // public partial class InventoryBrowseForm : Form
    // InitializeComponent(); CallSelectProcedure(); this.grdList.DataSource = result;
    /*
    partial class InventoryBrowseForm
    {
        private System.Windows.Forms.DataGridView grdList;
        private void InitializeComponent()
        {
            this.grdList = new System.Windows.Forms.DataGridView();
            this.grdList.BindingField = "ENTITY_ID";
        }
    }
    */
    '''
    string_literal_only = r'''
    var regular = "public partial class InventoryBrowseForm : Form { InitializeComponent(); CallSelectProcedure(); this.grdList.DataSource = result; }";
    var escaped = "partial class InventoryBrowseForm { CallProc(\"fake\"); FieldName = value; }";
    var verbatim = @"partial class InventoryBrowseForm { InitializeComponent(); CallViewQuery(); BindingField = ""ENTITY_ID""; }";
    var interpolated = $"partial class InventoryBrowseForm {{ CallSaveProcedure(); DataSource = {value}; }}";
    var interpolatedVerbatim = $@"partial class InventoryBrowseForm {{ InitializeComponent(); FieldName = ""{value}""; }}";
    var alternateInterpolatedVerbatim = @$"partial class InventoryBrowseForm {{ CallProc(); BindingField = ""{value}""; }}";
    char slash = '/';
    char quote = '\'';
    '''
    return comment_only, string_literal_only


def write_generalized_packaged_contract(directory, mutate=None):
    source = Path("skills/pb_to_csharp_migration_harness/references/packaged-style-contract.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if mutate is not None:
        mutate(payload)
    path = Path(directory) / "packaged-style-contract.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    profile_hash = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return path, payload, profile_hash


def valid_devexpress_grid_designer(
    form_class="RecordsBrowseForm",
    *,
    columns=None,
    input_format="list",
    table_name="",
    purpose_name="",
):
    columns = columns or [{"field_name": "PRICE", "caption": "Price", "data_type": "decimal(18, 2)"}]
    plan = build_csharp_grid_column_designer_plan(
        columns,
        input_format=input_format,
        table_name=table_name,
        purpose_name=purpose_name,
        result_fields=[item["field_name"] for item in columns],
    )
    if not plan.success:
        raise AssertionError(plan.to_dict())
    return plan, f"partial class {form_class}\n{{\n{plan.stdout}\n}}"


def observed_layout_load_evidence(path, *, grid_name="grdList", view_name="gvwList"):
    artifact_path = Path(path).resolve()
    xml_text = artifact_path.read_text(encoding="utf-8")
    return {
        "kind": "devexpress_designer_layout_load",
        "status": "observed",
        "artifact_path": str(artifact_path),
        "artifact_sha256": "sha256:" + hashlib.sha256(xml_text.encode("utf-8")).hexdigest(),
        "grid_control_name": grid_name,
        "grid_view_name": view_name,
    }


def handwritten_grid_xml(field_name, prefix, *, view_name="gridView1"):
    return f'''<XtraSerializer version="1.0" application="View">
  <property name="#LayoutVersion" />
  <property name="BestFitMaxRowCount">-1</property>
  <property name="PreviewLineCount">-1</property>
  <property name="HorzScrollStep">3</property>
  <property name="FocusRectStyle">CellFocus</property>
  <property name="ScrollStyle">LiveVertScroll, LiveHorzScroll</property>
  <property name="PreviewIndent">-1</property>
  <property name="GroupPanelText" />
  <property name="PreviewFieldName" />
  <property name="VertScrollTipFieldName" />
  <property name="LevelIndent">-1</property>
  <property name="GroupFooterShowMode">VisibleIfExpanded</property>
  <property name="NewItemRowText" />
  <property name="SynchronizeClones">true</property>
  <property name="BorderStyle">Default</property>
  <property name="ViewCaption" />
  <property name="DetailHeight">350</property>
  <property name="Name">{view_name}</property>
  <property name="DetailTabHeaderLocation">Top</property>
  <property name="ActiveFilterEnabled">true</property>
  <property name="Columns" iskey="true" value="1">
    <property name="Item1" isnull="true" iskey="true">
      <property name="AppearanceHeader" isnull="true" iskey="true">
        <property name="Options" isnull="true" iskey="true">
          <property name="UseTextOptions">true</property>
          <property name="UseFont">true</property>
        </property>
        <property name="TextOptions" isnull="true" iskey="true">
          <property name="HAlignment">Center</property>
          <property name="VAlignment">Center</property>
        </property>
        <property name="Font">Tahoma, 9pt</property>
      </property>
      <property name="AppearanceCell" isnull="true" iskey="true">
        <property name="Options" isnull="true" iskey="true">
          <property name="UseFont">true</property>
        </property>
        <property name="Font">Tahoma, 9pt</property>
      </property>
      <property name="Visible">true</property>
      <property name="VisibleIndex">1</property>
      <property name="FieldName">{field_name}</property>
      <property name="Name">{prefix}{field_name}</property>
      <property name="Caption">{field_name}</property>
      <property name="ColumnEditName" />
    </property>
  </property>
  <property name="OptionsView" isnull="true" iskey="true">
    <property name="ShowViewCaption">false</property>
    <property name="EnableAppearanceEvenRow">true</property>
    <property name="ShowGroupPanel">false</property>
    <property name="ColumnAutoWidth">false</property>
    <property name="ShowFooter">true</property>
    <property name="ShowAutoFilterRow">true</property>
  </property>
</XtraSerializer>'''


def patch_runtime_profile_path(path):
    return mock.patch.object(pb_migration, "PACKAGED_MIGRATION_PROFILE_PATH", Path(path))


def verify_migration_generated_csharp_style(*args, **kwargs):
    source = str(args[0] if args else kwargs.pop("source_text", ""))
    requested_program = str(kwargs.get("program_key") or "TestBrowse")
    expected_form = requested_program if requested_program.lower().endswith("form") else requested_program + "Form"
    source = (
        f"public partial class {expected_form} : System.Windows.Forms.Form {{\n"
        f"public {expected_form}() {{ InitializeComponent(); }}\n"
        "protected void SearchCommand() { CallSelectProcedure(); }\n"
        "private void CallSelectProcedure() { this.grdList.DataSource = result; }\n"
        f"{source}\n}}"
    )
    args = (source, *args[1:]) if args else (source,)
    kwargs.setdefault("program_key", requested_program)
    kwargs.setdefault(
        "profile_evidence",
        loaded_test_profile(csharp_required_patterns=[]),
    )
    return _verify_migration_generated_csharp_style(*args, **kwargs)


def verify_pb_migration_sp_generation_contract(*args, **kwargs):
    kwargs.setdefault("profile_evidence", loaded_sp_test_profile())
    return _verify_pb_migration_sp_generation_contract(*args, **kwargs)


def verify_pb_migration_sp_with_sql_formatting(*args, **kwargs):
    kwargs.setdefault("profile_evidence", loaded_sp_test_profile())
    return _verify_pb_migration_sp_with_sql_formatting(*args, **kwargs)


class PbToCSharpMigrationHarnessTests(unittest.TestCase):
    def _composite_display_spec(self, **overrides):
        values = {
            "base_field": "KEYVALUE",
            "sequence_fields": ["SEQUENCE1"],
            "evidence_kind": "user-supplied-contract",
            "evidence_refs": ["ordered key-value plus sequence components"],
            "display_field": "KEYVALUES",
            "display_caption": "Composite key",
            "base_type_family": "character",
            "sequence_type_family": "numeric",
            "sequence_format": "##0",
        }
        values.update(overrides)
        return CompositeBusinessKeyDisplaySpec(**values)

    def test_composite_display_key_retains_key_and_sequence_fields(self):
        spec = self._composite_display_spec()
        plan = build_composite_business_key_display_plan(spec)
        observation = CompositeBusinessKeyDisplayObservation(
            result_fields=["KEYVALUE", "SEQUENCE1", "KEYVALUES"],
            display_expression="KEYVALUE + '-' + FORMAT(SEQUENCE1, '##0')",
            display_alias="KEYVALUES",
            component_order=["KEYVALUE", "SEQUENCE1"],
            visible_grid_field="KEYVALUES",
            hidden_raw_fields=["KEYVALUE", "SEQUENCE1"],
            grid_caption="Composite key",
        )

        verified = verify_composite_business_key_display_contract(spec, observation)

        self.assertTrue(plan.success, plan.to_dict())
        self.assertEqual(["KEYVALUE", "SEQUENCE1"], plan.metadata["plan"]["raw_result_fields"])
        self.assertEqual("KEYVALUES", plan.metadata["plan"]["visible_grid_field"])
        self.assertEqual(
            "KEYVALUE + '-' + FORMAT(SEQUENCE1, '##0')",
            plan.metadata["plan"]["display_expression"],
        )
        self.assertTrue(verified.success, verified.to_dict())

    def test_composite_display_key_includes_all_sequences_in_declared_order(self):
        spec = self._composite_display_spec(sequence_fields=["SEQUENCE1", "SEQUENCE2"])
        plan = build_composite_business_key_display_plan(spec)
        verified = verify_composite_business_key_display_contract(
            spec,
            {
                "result_fields": ["KEYVALUE", "SEQUENCE1", "SEQUENCE2", "KEYVALUES"],
                "display_expression": (
                    "KEYVALUE + '-' + FORMAT(SEQUENCE1, '##0') "
                    "+ '-' + FORMAT(SEQUENCE2, '##0')"
                ),
                "display_alias": "KEYVALUES",
                "component_order": ["KEYVALUE", "SEQUENCE1", "SEQUENCE2"],
                "visible_grid_field": "KEYVALUES",
                "hidden_raw_fields": ["KEYVALUE", "SEQUENCE1", "SEQUENCE2"],
                "grid_caption": "Composite key",
            },
        )

        self.assertTrue(plan.success, plan.to_dict())
        self.assertEqual(
            "KEYVALUE + '-' + FORMAT(SEQUENCE1, '##0') "
            "+ '-' + FORMAT(SEQUENCE2, '##0')",
            plan.metadata["plan"]["display_expression"],
        )
        self.assertTrue(verified.success, verified.to_dict())

    def test_composite_display_key_is_name_agnostic(self):
        for case_index in range(1, 13):
            base_field = f"KEY_{case_index}"
            sequence_fields = [
                f"SEQUENCE_{case_index}_{position}"
                for position in range(1, (case_index % 3) + 2)
            ]
            display_field = f"DISPLAY_{case_index}"
            expression = base_field + "".join(
                f" + '-' + FORMAT({field_name}, '##0')"
                for field_name in sequence_fields
            )
            with self.subTest(base_field=base_field, sequence_fields=sequence_fields):
                spec = self._composite_display_spec(
                    base_field=base_field,
                    sequence_fields=sequence_fields,
                    display_field=display_field,
                )
                plan = build_composite_business_key_display_plan(spec)
                raw_fields = [base_field, *sequence_fields]
                verified = verify_composite_business_key_display_contract(
                    spec,
                    {
                        "result_fields": [*raw_fields, display_field],
                        "display_expression": expression,
                        "display_alias": display_field,
                        "component_order": raw_fields,
                        "visible_grid_field": display_field,
                        "hidden_raw_fields": raw_fields,
                        "grid_caption": "Composite key",
                    },
                )

                self.assertTrue(plan.success, plan.to_dict())
                self.assertEqual(raw_fields, plan.metadata["plan"]["raw_result_fields"])
                self.assertEqual(expression, plan.metadata["plan"]["display_expression"])
                self.assertTrue(verified.success, verified.to_dict())

    def test_composite_display_key_requires_authoritative_evidence_and_derives_default_alias(self):
        missing_evidence = build_composite_business_key_display_plan(
            self._composite_display_spec(evidence_kind="", evidence_refs=[])
        )
        missing_alias = build_composite_business_key_display_plan(
            self._composite_display_spec(display_field="")
        )
        approved_default = build_composite_business_key_display_plan(
            self._composite_display_spec(display_field="")
        )

        self.assertFalse(missing_evidence.success)
        self.assertIn(
            "composite_display_key_evidence_required",
            {item["code"] for item in missing_evidence.metadata["issues"]},
        )
        self.assertTrue(missing_alias.success, missing_alias.to_dict())
        self.assertEqual("KEYVALUES", missing_alias.metadata["plan"]["display_result_field"])
        self.assertTrue(approved_default.success, approved_default.to_dict())
        self.assertEqual("KEYVALUES", approved_default.metadata["plan"]["display_result_field"])

    def test_composite_display_key_verifier_rejects_missing_raw_alias_and_wrong_order(self):
        spec = self._composite_display_spec(sequence_fields=["SEQUENCE1", "SEQUENCE2"])
        common = {
            "result_fields": ["KEYVALUE", "SEQUENCE2", "WRONG_ALIAS"],
            "display_expression": (
                "KEYVALUE + '-' + FORMAT(SEQUENCE1, '##0') "
                "+ '-' + FORMAT(SEQUENCE2, '##0')"
            ),
            "display_alias": "WRONG_ALIAS",
            "component_order": ["KEYVALUE", "SEQUENCE2", "SEQUENCE1"],
            "visible_grid_field": "WRONG_ALIAS",
            "hidden_raw_fields": ["KEYVALUE", "SEQUENCE1", "SEQUENCE2"],
            "grid_caption": "Composite key",
        }

        result = verify_composite_business_key_display_contract(spec, common)
        issue_codes = {item["code"] for item in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("composite_display_key_raw_result_field_missing", issue_codes)
        self.assertIn("composite_display_key_display_result_field_missing", issue_codes)
        self.assertIn("composite_display_key_alias_mismatch", issue_codes)
        self.assertIn("composite_display_key_component_order_mismatch", issue_codes)
        self.assertIn("composite_display_key_grid_field_mismatch", issue_codes)

    def test_runtime_loader_rejects_legacy_profile_catalog_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            legacy_path = Path(temp_dir) / "legacy-profile-catalog.json"
            legacy_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profiles": [
                            {
                                "profile_id": "legacy-profile",
                                "version": "1.0",
                                "sanitized": True,
                                "rules": {"csharp": {}, "sql": {}},
                            }
                        ],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            profile_hash = "sha256:" + hashlib.sha256(legacy_path.read_bytes()).hexdigest()
            with patch_runtime_profile_path(legacy_path):
                loaded = load_packaged_migration_profile(
                    "legacy-profile",
                    "1.0",
                    profile_hash,
                )

        self.assertFalse(loaded.success)
        self.assertIn(
            "packaged_profile_contract_invalid",
            {issue["code"] for issue in loaded.metadata["issues"]},
        )

    def test_plan_fails_closed_when_generalized_contract_is_missing_or_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / "missing-packaged-style-contract.json"
            invalid_path, _, _ = write_generalized_packaged_contract(
                temp_dir,
                mutate=lambda payload: payload.pop("naming_grammar"),
            )
            with patch_runtime_profile_path(missing_path):
                missing = build_pb_to_csharp_migration_plan("Migrate a browse form.")
            with patch_runtime_profile_path(invalid_path):
                invalid = build_pb_to_csharp_migration_plan("Migrate a browse form.")

        self.assertFalse(missing.success)
        self.assertFalse(invalid.success)
        self.assertEqual("blocked", missing.metadata["packaged_style_resolution"]["status"])
        self.assertEqual("blocked", invalid.metadata["packaged_style_resolution"]["status"])

    def test_csharp_validator_requires_structure_and_requested_form_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, payload, profile_hash = write_generalized_packaged_contract(temp_dir)
            with patch_runtime_profile_path(profile_path):
                loaded = load_packaged_migration_profile(
                    payload["contract_id"],
                    payload["contract_version"],
                    profile_hash,
                )

        empty = _verify_migration_generated_csharp_style(
            "",
            profile_evidence=loaded,
            program_key="InventoryBrowse",
        )
        arbitrary = _verify_migration_generated_csharp_style(
            "public class UnrelatedBrowseForm { protected void SearchCommand() {} }",
            profile_evidence=loaded,
            program_key="InventoryBrowse",
        )
        search_command_only = _verify_migration_generated_csharp_style(
            "public partial class InventoryBrowseForm { protected void SearchCommand() {} }",
            profile_evidence=loaded,
            program_key="InventoryBrowse",
        )
        code_behind, designer = valid_csharp_contract_sources()
        mapped = _verify_migration_generated_csharp_style(
            code_behind,
            designer_source_text=designer,
            profile_evidence=loaded,
            program_key="InventoryBrowse",
            result_fields=["ENTITY_ID"],
        )
        result_mismatch = _verify_migration_generated_csharp_style(
            code_behind,
            designer_source_text=designer.replace("DataPropertyName", "FieldName"),
            profile_evidence=loaded,
            program_key="InventoryBrowse",
            result_fields=["OTHER_ID"],
        )

        self.assertFalse(empty.success)
        self.assertIn("generated_csharp_empty", {issue["code"] for issue in empty.metadata["issues"]})
        self.assertFalse(arbitrary.success)
        self.assertIn(
            "generated_csharp_form_contract_mismatch",
            {issue["code"] for issue in arbitrary.metadata["issues"]},
        )
        self.assertFalse(search_command_only.success)
        self.assertEqual(
            {"mapped_form_declaration", "designer_initialization", "migration_call_path", "ui_binding_or_result_mapping"},
            set(search_command_only.metadata["profile_consumption"]["required_pattern_ids"]),
        )
        self.assertEqual(
            {"mapped_form_declaration", "designer_initialization", "migration_call_path", "ui_binding_or_result_mapping"},
            set(mapped.metadata["profile_consumption"]["matched_required_pattern_ids"]),
        )
        self.assertTrue(mapped.success, mapped.to_dict())
        self.assertTrue(mapped.metadata["program_form_contract"]["mapped"])
        self.assertEqual("passed", mapped.metadata["result_field_contract"]["status"])
        self.assertFalse(result_mismatch.success)
        self.assertIn(
            "csharp_result_field_mapping_mismatch",
            {issue["code"] for issue in result_mismatch.metadata["issues"]},
        )
        self.assertIn(
            "csharp.required_patterns",
            mapped.metadata["profile_consumption"]["applied_rule_groups"],
        )

    def test_csharp_validator_ignores_comment_and_literal_only_structural_evidence(self):
        profile = loaded_test_profile()
        comment_only, string_literal_only = non_code_csharp_contract_sources()
        comment_result = _verify_migration_generated_csharp_style(
            comment_only,
            designer_source_text=comment_only,
            profile_evidence=profile,
            program_key="InventoryBrowse",
            result_fields=["ENTITY_ID"],
        )
        literal_result = _verify_migration_generated_csharp_style(
            string_literal_only,
            designer_source_text=string_literal_only,
            profile_evidence=profile,
            program_key="InventoryBrowse",
            result_fields=["ENTITY_ID"],
        )
        code_behind, designer = valid_csharp_contract_sources()
        escaped_field = designer.replace(
            'DataPropertyName = "ENTITY_ID"',
            r'DataPropertyName = "\u0045NTITY_ID"',
        )
        verbatim_field = designer.replace(
            'DataPropertyName = "ENTITY_ID"',
            'DataPropertyName = @"ENTITY_ID"',
        )
        escaped_result = _verify_migration_generated_csharp_style(
            code_behind,
            designer_source_text=escaped_field,
            profile_evidence=profile,
            program_key="InventoryBrowse",
            result_fields=["ENTITY_ID"],
        )
        verbatim_result = _verify_migration_generated_csharp_style(
            code_behind,
            designer_source_text=verbatim_field,
            profile_evidence=profile,
            program_key="InventoryBrowse",
            result_fields=["ENTITY_ID"],
        )

        self.assertFalse(comment_result.success)
        self.assertFalse(literal_result.success)
        for result in (comment_result, literal_result):
            self.assertEqual(
                [],
                result.metadata["profile_consumption"]["matched_required_pattern_ids"],
            )
            self.assertFalse(result.metadata["program_form_contract"]["mapped"])
            self.assertEqual([], result.metadata["result_field_contract"]["mappings"])
        self.assertTrue(escaped_result.success, escaped_result.to_dict())
        self.assertTrue(verbatim_result.success, verbatim_result.to_dict())
        self.assertEqual(
            "ENTITY_ID",
            escaped_result.metadata["result_field_contract"]["mappings"][0]["field_name"],
        )
        self.assertEqual(
            "ENTITY_ID",
            verbatim_result.metadata["result_field_contract"]["mappings"][0]["field_name"],
        )

    def test_csharp_validator_masks_if_false_and_raw_string_contract_evidence(self):
        profile = loaded_test_profile()
        fake = r'''
        public class Noise {}
        #if false
        public partial class InventoryBrowseForm : System.Windows.Forms.Form
        {
            public InventoryBrowseForm() { InitializeComponent(); }
            private void CallSelectProcedure() { this.grdList.DataSource = result; }
        }
        #endif
        var raw = """public partial class InventoryBrowseForm : Form { InitializeComponent(); CallProc(); FieldName = "ENTITY_ID"; }""";
        var interpolatedRaw = $$"""partial class InventoryBrowseForm { CallSaveProcedure(); DataSource = {{value}}; }""";
        '''
        result = _verify_migration_generated_csharp_style(
            fake,
            profile_evidence=profile,
            program_key="InventoryBrowse",
            result_fields=["ENTITY_ID"],
        )
        self.assertFalse(result.success, result.to_dict())
        self.assertEqual([], result.metadata["profile_consumption"]["matched_required_pattern_ids"])
        self.assertFalse(result.metadata["program_form_contract"]["mapped"])

    def test_result_field_mapping_requires_direct_resolvable_literal(self):
        code_behind, designer = valid_csharp_contract_sources()
        dynamic_designer = designer.replace(
            'this.colList_ENTITY_ID.DataPropertyName = "ENTITY_ID";',
            "this.colList_ENTITY_ID.DataPropertyName = ResolveFieldName();",
        )
        result = _verify_migration_generated_csharp_style(
            code_behind,
            designer_source_text=dynamic_designer,
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="InventoryBrowse",
            result_fields=["ENTITY_ID"],
        )
        self.assertFalse(result.success, result.to_dict())
        self.assertIn(
            "csharp_result_field_mapping_unresolved",
            {item["code"] for item in result.metadata["issues"]},
        )

    def test_csharp_validator_blocks_designer_owned_ui_in_code_behind_without_dynamic_evidence(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, payload, profile_hash = write_generalized_packaged_contract(
                temp_dir,
                mutate=lambda contract: contract["rules"]["csharp"].update(required_patterns=[]),
            )
            with patch_runtime_profile_path(profile_path):
                loaded = load_packaged_migration_profile(
                    payload["contract_id"],
                    payload["contract_version"],
                    profile_hash,
                )

        generated = r'''
        public partial class InventoryBrowseForm
        {
            private System.Windows.Forms.TextBox txtCode;
            protected void SearchCommand()
            {
                this.txtCode = new System.Windows.Forms.TextBox();
                this.txtCode.Location = new System.Drawing.Point(10, 10);
                this.txtCode.Name = "txtCode";
                this.txtCode.TabIndex = 0;
                this.txtCode.BindingField = "CODE";
            }
        }
        '''
        blocked = _verify_migration_generated_csharp_style(
            generated,
            profile_evidence=loaded,
            program_key="InventoryBrowse",
        )
        allowed = _verify_migration_generated_csharp_style(
            generated,
            profile_evidence=loaded,
            program_key="InventoryBrowse",
            runtime_dynamic_ui_evidence={
                "kind": "runtime_dynamic_ui",
                "approved": True,
                "reason": "The control is created from runtime metadata after the form is loaded.",
                "members": ["txtCode"],
            },
        )

        self.assertFalse(blocked.success)
        self.assertIn(
            "designer_owned_ui_in_code_behind",
            {issue["code"] for issue in blocked.metadata["issues"]},
        )
        self.assertEqual(
            {"binding", "construction", "declaration", "layout", "name", "tab_index"},
            set(blocked.metadata["designer_owned_ui_contract"]["detected_categories"]),
        )
        self.assertFalse(allowed.success)
        self.assertFalse(
            allowed.metadata["designer_owned_ui_contract"]["runtime_dynamic_evidence_accepted"]
        )

        prose_only = _verify_migration_generated_csharp_style(
            '''
            public partial class InventoryBrowseForm
            {
                protected void SearchCommand()
                {
                    this.txtCode.Enabled = false;
                }
            }
            ''',
            profile_evidence=loaded,
            program_key="InventoryBrowse",
            runtime_dynamic_ui_evidence={
                "kind": "runtime_dynamic_ui",
                "approved": True,
                "reason": "The source disables editing after a completed workflow transition.",
                "source_evidence": {"kind": "event", "name": "workflow-completed"},
                "verification": "The transition test verifies that the editor becomes disabled.",
                "transitions": [{"member": "txtCode", "property": "Enabled"}],
            },
        )
        runtime_state = _verify_migration_generated_csharp_style(
            '''
            public partial class InventoryBrowseForm
            {
                protected void SearchCommand()
                {
                    this.txtCode.Enabled = false;
                }
            }
            ''',
            profile_evidence=loaded,
            program_key="InventoryBrowse",
            runtime_dynamic_ui_evidence={
                "kind": "runtime_dynamic_ui",
                "approved": True,
                "reason": "The source disables editing after a completed workflow transition.",
                "source_evidence": {"kind": "event", "name": "workflow-completed"},
                "verification": {
                    "kind": "test",
                    "status": "passed",
                    "observed": True,
                    "test": "InventoryBrowseRuntimeStateTests.editor_is_disabled_after_completion",
                },
                "transitions": [{"member": "txtCode", "property": "Enabled"}],
            },
        )
        self.assertFalse(prose_only.success)
        self.assertFalse(
            prose_only.metadata["designer_owned_ui_contract"]["runtime_dynamic_evidence_accepted"]
        )
        self.assertTrue(runtime_state.success, runtime_state.to_dict())
        self.assertTrue(
            runtime_state.metadata["designer_owned_ui_contract"]["runtime_dynamic_evidence_accepted"]
        )

    def test_csharp_validator_covers_grid_repository_and_designer_property_families(self):
        profile = loaded_test_profile()
        generated = r'''
        public partial class InventoryBrowseForm
        {
            protected void SearchCommand()
            {
                this.colRuntime_VALUE = new DevExpress.XtraGrid.Columns.GridColumn();
                this.repRuntime = new DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit();
                this.gvwRuntime.Columns.AddRange(new[] { this.colRuntime_VALUE });
                this.colRuntime_VALUE.AppearanceHeader.Options.UseFont = true;
                this.gvwRuntime.OptionsView.ShowGroupPanel = false;
                this.colRuntime_VALUE.DisplayFormat.FormatString = "text";
                this.colRuntime_VALUE.ColumnEdit = this.repRuntime;
                this.pnlRuntime.Location = new System.Drawing.Point(1, 1);
                this.pnlRuntime.Name = "pnlRuntime";
                this.pnlRuntime.TabIndex = 1;
                this.pnlRuntime.BindingField = "VALUE";
            }
        }
        '''
        blocked = _verify_migration_generated_csharp_style(
            generated,
            profile_evidence=profile,
            program_key="InventoryBrowse",
        )
        allowed = _verify_migration_generated_csharp_style(
            generated,
            profile_evidence=profile,
            program_key="InventoryBrowse",
            runtime_dynamic_ui_evidence={
                "kind": "runtime_dynamic_ui",
                "approved": True,
                "reason": "The grid and panel are materialized from a runtime metadata schema.",
                "source_evidence": {"kind": "schema", "name": "runtime-grid"},
                "verification": {
                    "kind": "test",
                    "status": "passed",
                    "observed": True,
                    "test": "RuntimeGridSchemaTests.materializes_supported_properties",
                },
                "transitions": [
                    {"member": "gvwRuntime", "property": "OptionsView.ShowGroupPanel"},
                ],
            },
        )

        self.assertFalse(blocked.success)
        self.assertTrue(
            {
                "appearance",
                "binding",
                "collection",
                "construction",
                "display_format",
                "layout",
                "name",
                "options",
                "repository",
                "tab_index",
            }.issubset(set(blocked.metadata["designer_owned_ui_contract"]["detected_categories"]))
        )
        self.assertFalse(allowed.success)
        self.assertTrue(
            allowed.metadata["designer_owned_ui_contract"]["runtime_dynamic_evidence_accepted"]
        )

    def test_csharp_validator_rejects_code_behind_only_static_ui_and_accepts_designer_split(self):
        profile = loaded_test_profile(csharp_required_patterns=[])
        code_behind_only = r'''
        public partial class RecordsBrowseForm
        {
            private DevExpress.XtraGrid.GridControl grdBrowse;
            private DevExpress.XtraGrid.Views.Grid.GridView gvwBrowse;
            private DevExpress.XtraGrid.Columns.GridColumn colList_ENTITY_VALUE;
            private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit repNumeric;

            protected void SearchCommand()
            {
                this.grdBrowse = new DevExpress.XtraGrid.GridControl();
                this.gvwBrowse = new DevExpress.XtraGrid.Views.Grid.GridView();
                this.colList_ENTITY_VALUE = new DevExpress.XtraGrid.Columns.GridColumn();
                this.repNumeric = new DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit();
                this.grdBrowse.MainView = this.gvwBrowse;
                this.grdBrowse.ViewCollection.AddRange(new[] { this.gvwBrowse });
                this.gvwBrowse.Columns.AddRange(new[] { this.colList_ENTITY_VALUE });
                this.colList_ENTITY_VALUE.Name = "colList_ENTITY_VALUE";
                this.colList_ENTITY_VALUE.FieldName = "ENTITY_VALUE";
                this.colList_ENTITY_VALUE.VisibleIndex = 0;
                this.colList_ENTITY_VALUE.AppearanceHeader.Options.UseTextOptions = true;
                this.colList_ENTITY_VALUE.AppearanceCell.Options.UseTextOptions = true;
                this.colList_ENTITY_VALUE.ColumnEdit = this.repNumeric;
                this.grdBrowse.Location = new System.Drawing.Point(8, 8);
                this.grdBrowse.Size = new System.Drawing.Size(320, 180);
                this.grdBrowse.Name = "grdBrowse";
                this.grdBrowse.TabIndex = 0;
                this.Controls.Add(this.grdBrowse);
            }
        }
        '''
        code_behind = r'''
        public partial class RecordsBrowseForm
        {
            protected void SearchCommand()
            {
                this.grdBrowse.DataSource = result;
            }

            private void grdBrowse_DoubleClick(object sender, System.EventArgs e)
            {
                OpenSelectedRecord();
            }
        }
        '''
        designer = r'''
        partial class RecordsBrowseForm
        {
            private DevExpress.XtraGrid.GridControl grdBrowse;
            private DevExpress.XtraGrid.Views.Grid.GridView gvwBrowse;
            private DevExpress.XtraGrid.Columns.GridColumn colList_ENTITY_VALUE;
            private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit repNumeric;

            private void InitializeComponent()
            {
                this.grdBrowse = new DevExpress.XtraGrid.GridControl();
                this.gvwBrowse = new DevExpress.XtraGrid.Views.Grid.GridView();
                this.colList_ENTITY_VALUE = new DevExpress.XtraGrid.Columns.GridColumn();
                this.repNumeric = new DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit();
                this.grdBrowse.MainView = this.gvwBrowse;
                this.grdBrowse.ViewCollection.AddRange(new[] { this.gvwBrowse });
                this.gvwBrowse.Columns.AddRange(new[] { this.colList_ENTITY_VALUE });
                this.colList_ENTITY_VALUE.Name = "colList_ENTITY_VALUE";
                this.colList_ENTITY_VALUE.FieldName = "ENTITY_VALUE";
                this.colList_ENTITY_VALUE.VisibleIndex = 0;
                this.colList_ENTITY_VALUE.AppearanceHeader.Options.UseTextOptions = true;
                this.colList_ENTITY_VALUE.AppearanceCell.Options.UseTextOptions = true;
                this.colList_ENTITY_VALUE.ColumnEdit = this.repNumeric;
                this.grdBrowse.Location = new System.Drawing.Point(8, 8);
                this.grdBrowse.Size = new System.Drawing.Size(320, 180);
                this.grdBrowse.Name = "grdBrowse";
                this.grdBrowse.TabIndex = 0;
                this.Controls.Add(this.grdBrowse);
            }
        }
        '''
        _, designer = valid_devexpress_grid_designer(
            "RecordsBrowseForm",
            columns=[{"field_name": "ENTITY_VALUE", "caption": "Entity value", "data_type": "string"}],
        )

        blocked = _verify_migration_generated_csharp_style(
            code_behind_only,
            profile_evidence=profile,
            program_key="RecordsBrowse",
        )
        split = _verify_migration_generated_csharp_style(
            code_behind,
            designer_source_text=designer,
            profile_evidence=profile,
            program_key="RecordsBrowse",
        )

        self.assertFalse(blocked.success)
        self.assertIn(
            "designer_owned_ui_in_code_behind",
            {issue["code"] for issue in blocked.metadata["issues"]},
        )
        self.assertIn(
            "declaration",
            blocked.metadata["designer_owned_ui_contract"]["detected_categories"],
        )
        self.assertTrue(split.success, split.to_dict())
        self.assertTrue(split.metadata["designer_owned_ui_contract"]["split_contract_validated"])
        self.assertGreater(
            split.metadata["designer_owned_ui_contract"]["designer_static_finding_count"],
            0,
        )

    def test_normal_plan_does_not_consult_legacy_private_style_constants(self):
        with (
            mock.patch.object(pb_migration, "AUTHOR_TAGGED_CSHARP_STYLE_BASELINE", None),
            mock.patch.object(pb_migration, "AUTHOR_TAGGED_PROGRAM_CSHARP_MAPPINGS", None),
            mock.patch.object(pb_migration, "_discover_author_tagged_csharp_paths") as discover,
            mock.patch.object(pb_migration, "build_migration_profile_update") as profile_update,
        ):
            result = build_pb_to_csharp_migration_plan(
                "Plan a generalized inventory browse form.",
                {"program_key": "InventoryBrowse"},
            )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual("loaded", result.metadata["packaged_style_resolution"]["status"])
        discover.assert_not_called()
        profile_update.assert_not_called()

    def test_packaged_profile_load_requires_exact_sanitized_identity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                loaded = load_packaged_migration_profile(
                    "pb-csharp-offline-generalized",
                    "1.0",
                    profile_hash,
                )
                wrong_version = load_packaged_migration_profile(
                    "pb-csharp-offline-generalized",
                    "2.0.0",
                    profile_hash,
                )
                wrong_hash = load_packaged_migration_profile(
                    "pb-csharp-offline-generalized",
                    "1.0",
                    "sha256:" + "0" * 64,
                )

        self.assertTrue(loaded.success, loaded.to_dict())
        self.assertEqual("loaded", loaded.metadata["status"])
        self.assertTrue(loaded.metadata["profile_consumption"]["sanitized"])
        self.assertEqual(profile_hash, loaded.metadata["profile_consumption"]["profile_hash"])
        self.assertFalse(wrong_version.success)
        self.assertIn("packaged_profile_version_mismatch", {issue["code"] for issue in wrong_version.metadata["issues"]})
        self.assertFalse(wrong_hash.success)
        self.assertIn("packaged_profile_hash_mismatch", {issue["code"] for issue in wrong_hash.metadata["issues"]})

    def test_runtime_generation_uses_only_packaged_profile_and_never_walks_csharp_roots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with (
                patch_runtime_profile_path(profile_path),
                mock.patch.object(pb_migration.os, "walk") as walk,
                mock.patch.object(pb_migration, "_discover_author_tagged_csharp_paths") as discover,
                mock.patch.object(pb_migration, "build_author_tagged_style_profile_update") as profile_update,
                mock.patch.object(pb_migration, "build_migration_profile_update") as generic_profile_update,
            ):
                result = build_offline_pb_to_csharp_runtime_generation(
                    "Generate generalized C# and SQL.",
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    csharp_root=r"C:\private\source",
                )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual("offline_packaged_profile", result.metadata["runtime_mode"])
        self.assertEqual([], result.metadata["external_sources_consulted"])
        self.assertFalse(result.metadata["capabilities_invoked"]["db"])
        self.assertFalse(result.metadata["capabilities_invoked"]["pbl"])
        self.assertFalse(result.metadata["capabilities_invoked"]["orca"])
        self.assertFalse(result.metadata["capabilities_invoked"]["pblscripter"])
        walk.assert_not_called()
        discover.assert_not_called()
        profile_update.assert_not_called()
        generic_profile_update.assert_not_called()

    def test_live_csharp_relearning_is_explicit_profile_update_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "GENERALIZED.cs").write_text(
                "public class GENERALIZED : GeneralizedScreenBase { private void SearchCommand() {} }",
                encoding="utf-8",
            )
            (root / "GENERALIZED.Designer.cs").write_text(
                'this.txtCODE.BindingField = "CODE";',
                encoding="utf-8",
            )

            runtime = resolve_author_tagged_style_evidence(
                "SP_GENERALIZED_SELECT",
                csharp_root=str(root),
            )
            updated = build_migration_profile_update(
                "SP_GENERALIZED_SELECT",
                csharp_root=str(root),
                profile_id="generalized-pb-csharp",
                profile_version="1.1.0",
            )

        self.assertFalse(runtime.success)
        self.assertEqual("explicit_profile_update_required", runtime.metadata["status"])
        self.assertTrue(updated.success, updated.to_dict())
        self.assertEqual("explicit_profile_update", updated.metadata["operation"])
        self.assertEqual("candidate_only", updated.metadata["write_status"])

    def test_csharp_validator_requires_and_applies_loaded_profile(self):
        without_profile = _verify_migration_generated_csharp_style(
            "public class Screen : GeneralizedScreenBase {}"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                loaded = load_packaged_migration_profile("pb-csharp-offline-generalized", "1.0", profile_hash)
            alien = verify_migration_generated_csharp_style(
                "public class Screen : GeneralizedScreenBase { AlienConvention bridge; }",
                profile_evidence=loaded,
                program_key="GENERALIZED",
                primary_style_evidence_paths=[
                    r"packaged\style\GENERALIZED.cs",
                    r"packaged\style\GENERALIZED.Designer.cs",
                ],
                require_author_tagged_evidence=True,
            )
            matched = verify_migration_generated_csharp_style(
                "public class Screen : GeneralizedScreenBase {}",
                profile_evidence=loaded,
            )

        self.assertFalse(without_profile.success)
        self.assertIn("packaged_profile_consumption_required", {issue["code"] for issue in without_profile.metadata["issues"]})
        self.assertFalse(alien.success)
        self.assertIn("profile_forbidden_csharp_pattern", {issue["code"] for issue in alien.metadata["issues"]})
        self.assertTrue(matched.success, matched.to_dict())
        self.assertTrue(matched.metadata["profile_consumption"]["consumed"])
        self.assertIn("csharp.required_patterns", matched.metadata["profile_consumption"]["applied_rule_groups"])

    def test_sp_validator_requires_profile_and_rejects_unmapped_or_temporary_table_sql(self):
        mapped_sql = sp_metadata_header("Generalized screen") + """
CREATE PROCEDURE DBO.SP_GENERALIZED_SELECT
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        unmapped_sql = mapped_sql.replace("SP_GENERALIZED_SELECT", "LEGACY_GENERALIZED_SELECT")
        temp_sql = mapped_sql.replace(
            "SELECT @WORKTYPE AS WORKTYPE;",
            "SELECT @WORKTYPE AS WORKTYPE INTO #TEMP;",
        )
        evidence = [
            {
                "kind": "pasted_sql",
                "path": "packaged/style/generalized.sql",
                "summary": "Generalized source SQL",
            }
        ]

        without_profile = _verify_pb_migration_sp_generation_contract(mapped_sql, source_evidence=evidence)
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                loaded = load_packaged_migration_profile("pb-csharp-offline-generalized", "1.0", profile_hash)
            unmapped = verify_pb_migration_sp_generation_contract(
                unmapped_sql,
                source_evidence=evidence,
                profile_evidence=loaded,
            )
            temporary = verify_pb_migration_sp_generation_contract(
                temp_sql,
                source_evidence=evidence,
                profile_evidence=loaded,
            )

        self.assertFalse(without_profile.success)
        self.assertIn("packaged_profile_consumption_required", {issue["code"] for issue in without_profile.metadata["issues"]})
        self.assertFalse(unmapped.success)
        self.assertIn("profile_unmapped_sp_output", {issue["code"] for issue in unmapped.metadata["issues"]})
        self.assertFalse(temporary.success)
        temporary_codes = {issue["code"] for issue in temporary.metadata["issues"]}
        self.assertIn("profile_forbidden_sql_pattern", temporary_codes)
        self.assertIn("temp_table_in_generated_sp", temporary_codes)
        self.assertTrue(temporary.metadata["profile_consumption"]["consumed"])

    def test_sp_validator_derives_procedure_identity_after_comment_stripping(self):
        sql = """-- =============================================
-- AUTHOR:      CREATE PROCEDURE DBO.SP_ALLOWED_SELECT
-- CREATE DATE: 2026-06-15
-- DESCRIPTION: ALTER PROCEDURE DBO.SP_ALLOWED_SELECT
-- =============================================
ALTER PROCEDURE DBO.SP_DISALLOWED_QUERY
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        profile = loaded_test_profile(
            csharp_required_patterns=[],
            sql_allowed_procedure_patterns=[r"^SP_ALLOWED_SELECT$"],
        )
        result = _verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[{"kind": "pasted_sql", "summary": "Disallowed procedure source SQL"}],
            profile_evidence=profile,
        )

        self.assertEqual("SP_DISALLOWED_QUERY", pb_migration._extract_sp_procedure_name(sql))
        self.assertFalse(result.success)
        issue = next(
            item for item in result.metadata["issues"] if item["code"] == "profile_unmapped_sp_output"
        )
        self.assertEqual("SP_DISALLOWED_QUERY", issue["procedure_name"])

    def test_orchestrated_validation_is_ordered_and_fails_closed_on_profile_mismatch(self):
        sql = sp_metadata_header("Generalized screen") + """
CREATE PROCEDURE DBO.SP_GENERALIZED_SELECT
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        evidence = [{"kind": "pasted_sql", "summary": "Generalized source SQL"}]
        csharp, designer = valid_csharp_contract_sources()
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                passed = orchestrate_pb_migration_validation(
                    csharp_source_text=csharp,
                    designer_source_text=designer,
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=evidence,
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                )
                mismatched = orchestrate_pb_migration_validation(
                    csharp_source_text=csharp,
                    designer_source_text=designer,
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=evidence,
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash="sha256:" + "0" * 64,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                )

        self.assertTrue(passed.success, passed.to_dict())
        self.assertEqual(
            ["load-profile", "validate-csharp", "validate-sp", "formatting-evidence"],
            passed.metadata["validation_contract"]["completed_stage_order"],
        )
        self.assertTrue(passed.metadata["validation_contract"]["completion_allowed"])
        self.assertFalse(passed.metadata["validation_contract"]["database_execution_attempted"])
        self.assertFalse(mismatched.success)
        self.assertEqual(["load-profile"], mismatched.metadata["validation_contract"]["completed_stage_order"])
        self.assertFalse(mismatched.metadata["validation_contract"]["profile_identity_match"])

    def test_orchestrated_validation_rejects_non_code_csharp_evidence_and_accepts_real_code(self):
        sql = sp_metadata_header("Generalized screen") + """
CREATE PROCEDURE DBO.SP_GENERALIZED_SELECT
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        evidence = [{"kind": "pasted_sql", "summary": "Generalized source SQL"}]
        comment_only, string_literal_only = non_code_csharp_contract_sources()
        code_behind, designer = valid_csharp_contract_sources()
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                comment_result = orchestrate_pb_migration_validation(
                    csharp_source_text=comment_only,
                    designer_source_text=comment_only,
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=evidence,
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                )
                literal_result = orchestrate_pb_migration_validation(
                    csharp_source_text=string_literal_only,
                    designer_source_text=string_literal_only,
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=evidence,
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                )
                real_result = orchestrate_pb_migration_validation(
                    csharp_source_text=code_behind,
                    designer_source_text=designer,
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=evidence,
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                )

        for result in (comment_result, literal_result):
            self.assertFalse(result.success)
            self.assertEqual(
                ["load-profile", "validate-csharp"],
                result.metadata["validation_contract"]["completed_stage_order"],
            )
            self.assertEqual(
                [],
                result.metadata["evidence"]["csharp"]["profile_consumption"][
                    "matched_required_pattern_ids"
                ],
            )
        self.assertTrue(real_result.success, real_result.to_dict())

    def test_orchestration_propagates_expected_grid_contract_and_missing_designer_fails(self):
        code_behind, _ = valid_csharp_contract_sources()
        sql = sp_metadata_header("Grid propagation") + '''
CREATE PROCEDURE DBO.USP_GRID_SELECT
AS
BEGIN
    SELECT 1 AS ENTITY_ID;
END
'''
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                result = orchestrate_pb_migration_validation(
                    csharp_source_text=code_behind,
                    designer_source_text="",
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=[{"kind": "pasted_sql", "summary": "Grid source"}],
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                    expected_grid_role="list",
                    expected_grid_columns=[{"field_name": "ENTITY_ID", "data_type": "string"}],
                )
        self.assertFalse(result.success, result.to_dict())
        self.assertEqual(
            ["load-profile", "validate-csharp"],
            result.metadata["validation_contract"]["completed_stage_order"],
        )
        self.assertIn(
            "expected_grid_designer_missing",
            {item["code"] for item in result.metadata["evidence"]["csharp"]["issues"]},
        )

    def test_orchestration_propagates_multiple_master_detail_grid_contracts(self):
        list_columns = [{"field_name": "MASTER_ID", "caption": "Master", "data_type": "string"}]
        detail_columns = [{"field_name": "DETAIL_ID", "caption": "Detail", "data_type": "string"}]
        list_plan = build_csharp_grid_column_designer_plan(list_columns, result_fields=["MASTER_ID"])
        detail_plan = build_csharp_grid_column_designer_plan(
            detail_columns, input_format="detail", result_fields=["DETAIL_ID"]
        )
        designer = f"partial class RecordsBrowseForm {{\n{list_plan.stdout}\n{detail_plan.stdout}\n}}"
        code_behind = "public partial class RecordsBrowseForm : System.Windows.Forms.Form { public RecordsBrowseForm() { InitializeComponent(); } private void CallSelectProcedure() { this.grdList.DataSource = result; } }"
        sql = sp_metadata_header("Master detail grid propagation") + """
CREATE PROCEDURE DBO.SP_GENERALIZED_SELECT
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS MASTER_ID;
    END
END
"""
        contracts = [
            {"id": "master", "role": "list", "columns": list_columns, "artifact_text": generate_devexpress_grid_xml(list_columns)},
            {"id": "detail", "role": "detail", "columns": detail_columns, "artifact_text": generate_devexpress_grid_xml(detail_columns, prefix="colDetail_")},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                passed = orchestrate_pb_migration_validation(
                    csharp_source_text=code_behind,
                    designer_source_text=designer,
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=[{"kind": "pasted_sql", "summary": "Master detail source"}],
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="RecordsBrowse",
                    result_fields=["MASTER_ID", "DETAIL_ID"],
                    expected_grid_contracts=contracts,
                )
                blocked = orchestrate_pb_migration_validation(
                    csharp_source_text=code_behind,
                    designer_source_text=designer.replace(
                        "this.colDetail_DETAIL_ID.VisibleIndex = 1;",
                        "this.colDetail_DETAIL_ID.VisibleIndex = 0;",
                        1,
                    ),
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=[{"kind": "pasted_sql", "summary": "Master detail source"}],
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="RecordsBrowse",
                    result_fields=["MASTER_ID", "DETAIL_ID"],
                    expected_grid_contracts=contracts,
                )
        self.assertTrue(passed.success, passed.to_dict())
        self.assertFalse(blocked.success, blocked.to_dict())
        self.assertEqual(
            ["load-profile", "validate-csharp"],
            blocked.metadata["validation_contract"]["completed_stage_order"],
        )

    def test_orchestrated_validation_rejects_commented_allowed_sp_identity(self):
        sql = """-- =============================================
-- AUTHOR:      CREATE PROCEDURE DBO.SP_ALLOWED_SELECT
-- CREATE DATE: 2026-06-15
-- DESCRIPTION: ALTER PROCEDURE DBO.SP_ALLOWED_SELECT
-- =============================================
ALTER PROCEDURE DBO.SP_DISALLOWED_QUERY
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        csharp, designer = valid_csharp_contract_sources()
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(
                temp_dir,
                sql_allowed_procedure_patterns=[r"^SP_ALLOWED_SELECT$"],
            )
            with patch_runtime_profile_path(profile_path):
                result = orchestrate_pb_migration_validation(
                    csharp_source_text=csharp,
                    designer_source_text=designer,
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=[{"kind": "pasted_sql", "summary": "Disallowed procedure source SQL"}],
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                )

        self.assertFalse(result.success)
        self.assertEqual(
            ["load-profile", "validate-csharp", "validate-sp"],
            result.metadata["validation_contract"]["completed_stage_order"],
        )
        issue = next(
            item
            for item in result.metadata["evidence"]["sp"]["issues"]
            if item["code"] == "profile_unmapped_sp_output"
        )
        self.assertEqual("SP_DISALLOWED_QUERY", issue["procedure_name"])

    def test_orchestrated_validation_blocks_profile_forbidden_temp_before_formatting_or_db(self):
        sql = sp_metadata_header("Generalized screen") + """
CREATE PROCEDURE DBO.SP_GENERALIZED_SELECT
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE INTO #TEMP;
END
"""
        csharp, designer = valid_csharp_contract_sources()
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with (
                patch_runtime_profile_path(profile_path),
                mock.patch("src.skills.sql_formatting_style.verify_sql_formatting_style") as formatting,
            ):
                result = orchestrate_pb_migration_validation(
                    csharp_source_text=csharp,
                    designer_source_text=designer,
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=[{"kind": "pasted_sql", "summary": "Generalized source SQL"}],
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                )

        self.assertFalse(result.success)
        self.assertEqual(
            ["load-profile", "validate-csharp", "validate-sp"],
            result.metadata["validation_contract"]["completed_stage_order"],
        )
        self.assertFalse(result.metadata["validation_contract"]["database_execution_attempted"])
        formatting.assert_not_called()

    def test_orchestrated_validation_requires_and_validates_designer_companion(self):
        sql = sp_metadata_header("Generalized screen") + """
CREATE PROCEDURE DBO.SP_GENERALIZED_SELECT
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        csharp, designer = valid_csharp_contract_sources()
        mismatched_designer = designer.replace("InventoryBrowseForm", "OtherBrowseForm")
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                missing = orchestrate_pb_migration_validation(
                    csharp_source_text=csharp,
                    designer_source_text="",
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=[{"kind": "pasted_sql", "summary": "Generalized source SQL"}],
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                )
                mismatched = orchestrate_pb_migration_validation(
                    csharp_source_text=csharp,
                    designer_source_text=mismatched_designer,
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=[{"kind": "pasted_sql", "summary": "Generalized source SQL"}],
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                )

        self.assertFalse(missing.success)
        self.assertEqual(
            ["load-profile", "validate-csharp"],
            missing.metadata["validation_contract"]["completed_stage_order"],
        )
        self.assertIn(
            "designer_companion_required",
            {issue["code"] for issue in missing.metadata["evidence"]["csharp"]["issues"]},
        )
        self.assertFalse(mismatched.success)
        self.assertIn(
            "designer_companion_class_mismatch",
            {issue["code"] for issue in mismatched.metadata["evidence"]["csharp"]["issues"]},
        )

    def test_packaged_skill_is_readable_and_standalone(self):
        content = read_packaged_skill("pb-to-csharp-migration-harness")

        self.assertIn("Packaged source: uaf_skill_folder", content)
        self.assertIn("External runtime dependency: false", content)
        self.assertIn("src.skills.pb_to_csharp_migration", content)
        self.assertIn("Normal generation is offline", content)

    def test_demo_sql_is_verified_by_sp_contract_with_distinct_evidence(self):
        script_path = Path("skills/pb_to_csharp_migration_harness/scripts/demo.py")
        demo_module = runpy.run_path(str(script_path))
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            payload = demo_module["_sanitized_offline_scenario"](
                "pb-to-csharp-migration-harness",
                output_dir,
                Path.cwd(),
            )
            evidence = json.loads((output_dir / "offline_generation_evidence.json").read_text(encoding="utf-8"))
            sql_artifact = next(
                item for item in payload["artifacts"] if item["kind"] == "synthetic-select-procedure"
            )
            sql_text = Path(sql_artifact["path"]).read_text(encoding="utf-8")

        self.assertEqual("passed", evidence["runtime_validation"]["sp_generation_contract"])
        self.assertEqual([], evidence["runtime_validation"]["sp_issue_codes"])
        self.assertIn("@WORKTYPE", sql_text)
        self.assertRegex(sql_text, r"-- CREATE DATE: \d{4}-\d{2}-\d{2}")
        self.assertIn("SP generation contract verified", sql_artifact["validation_evidence"])
        self.assertIn("UTF-8 readable", sql_artifact["validation_evidence"])

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

    def test_declared_wrapper_family_is_target_project_inventory_not_global_baseline(self):
        wrapper_types = {
            "grid": "Target.Ui.u_GridControl",
            "date": "Target.Ui.u_DateEdit",
            "spin": "Target.Ui.u_SpinEdit",
            "button": "Target.Ui.u_ButtonEdit",
            "combo": "Target.Ui.u_ComboBox",
            "memo": "Target.Ui.u_MemoEdit",
            "check": "Target.Ui.u_CheckEdit",
            "tree": "Target.Ui.u_TreeList",
        }
        result = resolve_csharp_control_stack(
            {
                "target_project_controls": wrapper_types,
                "has_devexpress": True,
            }
        )

        self.assertEqual(result["selection"]["grid"]["provider"], "target-project")
        for logical_name, type_name in wrapper_types.items():
            with self.subTest(logical_name=logical_name):
                self.assertEqual(result["selection"][logical_name]["type"], type_name)

    def test_detail_form_layout_places_label_editor_pairs_with_binding_fields(self):
        result = build_detail_form_layout_plan(
            [
                {"name": "RECORD_ID", "caption": "수주번호", "editor_type": "text"},
                {"name": "QTY", "caption": "수주수량", "editor_type": "number", "logical_name": "Qty"},
                {"name": "EVENT_DATE", "caption": "수주일자", "editor_type": "date"},
                {"name": "ENTITY_CODE", "caption": "고객코드", "editor_type": "button"},
                {"name": "NOTES", "caption": "NOTES", "editor_type": "memo"},
                {"name": "ENABLED_YN", "caption": "ENABLED_YN", "editor_type": "check"},
            ],
            columns=3,
            section_caption="기본 상세정보",
            provider_contract={"provider": "konelib", "supports_binding_field": True},
            result_fields=["RECORD_ID", "QTY", "EVENT_DATE", "ENTITY_CODE", "NOTES", "ENABLED_YN"],
        )
        payload = json.loads(result.stdout)
        fields = payload["fields"]

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(payload["columns"], 3)
        self.assertIn("do not copy PB pixel coordinates blindly", payload["layout_rule"])
        self.assertIn("BindingField", payload["binding_rule"])
        self.assertEqual(fields[0]["caption"], "수주번호")
        self.assertEqual(fields[0]["field_name"], "RECORD_ID")
        self.assertEqual(fields[0]["csharp_label_name"], "lblRECORD_ID")
        self.assertEqual(fields[0]["csharp_editor_name"], "txtRECORD_ID")
        self.assertEqual(fields[0]["binding_code"], 'this.txtRECORD_ID.BindingField = "RECORD_ID";')
        self.assertEqual(fields[1]["editor_type"], "SpinEdit")
        self.assertEqual(fields[1]["csharp_editor_name"], "SpinQTY")
        self.assertEqual(fields[1]["binding_code"], 'this.SpinQTY.BindingField = "QTY";')
        self.assertEqual(fields[2]["editor_type"], "DateEdit")
        self.assertEqual(fields[2]["csharp_editor_name"], "ymdEVENT_DATE")
        self.assertEqual(fields[2]["binding_code"], 'this.ymdEVENT_DATE.BindingField = "EVENT_DATE";')
        self.assertEqual(fields[3]["editor_type"], "ButtonEdit")
        self.assertEqual(fields[3]["csharp_editor_name"], "btnENTITY_CODE")
        self.assertEqual(fields[4]["editor_type"], "MemoEdit")
        self.assertEqual(fields[4]["csharp_editor_name"], "memoNOTES")
        self.assertEqual(fields[5]["editor_type"], "CheckEdit")
        self.assertEqual(fields[5]["csharp_editor_name"], "ChkENABLED_YN")
        self.assertEqual(fields[0]["tab_index"], 0)
        self.assertEqual(fields[0]["tab_index_code"], "this.txtRECORD_ID.TabIndex = 0;")
        self.assertEqual(fields[5]["tab_index"], 5)
        self.assertEqual(fields[5]["tab_index_code"], "this.ChkENABLED_YN.TabIndex = 5;")
        self.assertEqual(fields[0]["row"], 0)
        self.assertEqual(fields[0]["column"], 0)
        self.assertEqual(fields[3]["row"], 1)
        self.assertEqual(fields[3]["column"], 0)
        self.assertEqual(fields[0]["label_bounds"]["y"], fields[1]["label_bounds"]["y"])
        self.assertLess(fields[0]["editor_bounds"]["x"], fields[1]["label_bounds"]["x"])

    def test_detail_form_layout_uses_provider_binding_contract_and_rejects_result_mismatch(self):
        winforms = build_detail_form_layout_plan(
            [{"name": "RECORD_ID", "editor_type": "text"}],
            provider_contract={"provider": "winforms", "supports_binding_field": False},
            result_fields=["RECORD_ID"],
        )
        explicit_wrapper = build_detail_form_layout_plan(
            [{"name": "RECORD_ID", "editor_type": "text"}],
            provider_contract={"provider": "winforms", "supports_binding_field": False},
            binding_map={
                "RECORD_ID": {
                    "result_field": "RECORD_ID",
                    "binding_property": "BindingField",
                    "evidence": {"kind": "supplied_binding_map", "observed": True},
                }
            },
            result_fields=["RECORD_ID"],
        )
        mismatch = build_detail_form_layout_plan(
            [{"name": "RECORD_ID", "editor_type": "text"}],
            provider_contract={"provider": "konelib", "supports_binding_field": True},
            result_fields=["OTHER_FIELD"],
        )

        winforms_field = winforms.metadata["fields"][0]
        self.assertTrue(winforms.success, winforms.to_dict())
        self.assertEqual("DataBindings", winforms_field["binding_property"])
        self.assertIn(".DataBindings.Add", winforms_field["binding_code"])
        self.assertNotIn(".BindingField", winforms_field["binding_code"])
        self.assertTrue(explicit_wrapper.success, explicit_wrapper.to_dict())
        self.assertEqual("BindingField", explicit_wrapper.metadata["fields"][0]["binding_property"])
        self.assertFalse(mismatch.success)
        self.assertIn(
            "binding_result_field_mismatch",
            {issue["code"] for issue in mismatch.metadata["issues"]},
        )

    def test_control_name_fallbacks_match_observed_csharp_prefixes(self):
        self.assertEqual(build_csharp_control_name("TextEdit", field_name="RECORD_NAME"), "txtRECORD_NAME")
        self.assertEqual(build_csharp_control_name("ButtonEdit", field_name="ENTITY_CODE"), "btnENTITY_CODE")
        self.assertEqual(build_csharp_control_name("LookUpEdit", field_name="RECORD_CATEGORY"), "cboRECORD_CATEGORY")
        self.assertEqual(build_csharp_control_name("ComboBoxEdit", field_name="RECORD_CATEGORY"), "cboRECORD_CATEGORY")
        self.assertEqual(build_csharp_control_name("SpinEdit", field_name="QTY"), "SpinQTY")
        self.assertEqual(build_csharp_control_name("DateEdit", field_name="EVENT_DATE"), "ymdEVENT_DATE")
        self.assertEqual(build_csharp_control_name("MemoEdit", field_name="NOTES"), "memoNOTES")
        self.assertEqual(build_csharp_control_name("CheckEdit", field_name="ENABLED_YN"), "ChkENABLED_YN")
        self.assertEqual(build_csharp_control_name("PanelControl", logical_name="Detail"), "pnDetail")
        self.assertEqual(build_csharp_control_name("GroupControl", logical_name="Search"), "grpSearch")
        self.assertEqual(build_csharp_control_name("GridControl", logical_name="List"), "grdList")
        self.assertEqual(build_csharp_control_name("GridView", logical_name="List"), "gvwList")
        self.assertEqual(build_csharp_control_name("TreeList", logical_name="TREE"), "treeListTREE")
        self.assertEqual(build_csharp_control_name("TabControl", logical_name="List"), "tabList")

    def test_extracts_datawindow_columns_and_generates_devexpress_xml(self):
        source = """
datawindow(units=0)
table(column=(type=char(20) dbname="zx900t.record_id" name=record_id)
column=(type=char(30) dbname="zx900t.record_code" name=record_code))
"""
        columns = extract_datawindow_columns(source)
        xml_text = generate_devexpress_grid_xml(columns)
        root = ET.fromstring(xml_text)

        self.assertEqual(columns, ["RECORD_ID", "RECORD_CODE"])
        self.assertEqual(root.tag, "XtraSerializer")
        self.assertIn("<property name=\"FieldName\">RECORD_ID</property>", xml_text)
        self.assertIn("<property name=\"Name\">colList_RECORD_CODE</property>", xml_text)
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

        verified = verify_devexpress_grid_xml_contract(
            xml_text,
            expected_columns=[
                {"field_name": "RECORD_ID", "caption": "RECORD_ID"},
                {"field_name": "RECORD_CODE", "caption": "RECORD_CODE"},
            ],
        )
        self.assertTrue(verified.success, verified.to_dict())
        self.assertEqual(verified.metadata["serializer_version"], "1.0")
        self.assertEqual(verified.metadata["serializer_application"], "View")
        self.assertEqual(verified.metadata["columns"][0]["field_name"], "RECORD_ID")
        self.assertEqual(verified.metadata["columns"][1]["name"], "colList_RECORD_CODE")
        self.assertFalse(verified.metadata["actual_live_layout_load_observed"])

    def test_generated_grid_xml_matches_canonical_authoritative_fixture_exactly(self):
        expected = handwritten_grid_xml("ENTITY_ID", "colList_").replace(
            '    <property name="ShowAutoFilterRow">',
            '\t<property name="ShowAutoFilterRow">',
        )
        self.assertEqual(generate_devexpress_grid_xml(["ENTITY_ID"]), expected)

    def test_special_field_names_round_trip_xml_and_require_explicit_csharp_mapping(self):
        columns = [
            {
                "field_name": "RATE#",
                "xml_column_name": "colSpecial_RATE#",
                "csharp_name": "colSpecial_RATE_NUMBER",
                "data_type": "string",
            },
            {
                "field_name": "COST$",
                "xml_column_name": "colSpecial_COST$",
                "csharp_name": "colSpecial_COST_DOLLAR",
                "data_type": "decimal(18, 2)",
            },
        ]
        xml_text = generate_devexpress_grid_xml(columns, prefix="colSpecial_")
        verified = verify_devexpress_grid_xml_contract(
            xml_text,
            expected_columns=columns,
            expected_column_prefix="colSpecial_",
        )
        plan = build_csharp_grid_column_designer_plan(
            columns,
            prefix="colSpecial_",
            input_format="purpose",
            purpose_name="Special",
            result_fields=["RATE#", "COST$"],
        )
        blocked = build_csharp_grid_column_designer_plan(
            ["RATE#", "COST$"],
            prefix="colSpecial_",
            input_format="purpose",
            purpose_name="Special",
            result_fields=["RATE#", "COST$"],
        )
        designer = f"partial class SpecialBrowseForm {{\n{plan.stdout}\n}}"
        style = _verify_migration_generated_csharp_style(
            "public partial class SpecialBrowseForm : System.Windows.Forms.Form { public SpecialBrowseForm() { InitializeComponent(); } private void CallSelectProcedure() { this.grdSPECIAL.DataSource = result; } }",
            designer_source_text=designer,
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="SpecialBrowse",
            expected_grid_role="purpose",
            expected_grid_suffix="SPECIAL",
            expected_grid_prefix="colSpecial_",
            expected_grid_columns=columns,
            result_fields=["RATE#", "COST$"],
            layout_load_artifact_text=xml_text,
        )

        self.assertIn('<property name="FieldName">RATE#</property>', xml_text)
        self.assertIn('<property name="Name">colSpecial_COST$</property>', xml_text)
        self.assertTrue(verified.success, verified.to_dict())
        self.assertTrue(plan.success, plan.to_dict())
        self.assertTrue(style.success, style.to_dict())
        self.assertIn("colSpecial_RATE_NUMBER", plan.stdout)
        self.assertFalse(blocked.success, blocked.to_dict())
        self.assertIn(
            "grid_column_csharp_name_mapping_required",
            {item["code"] for item in blocked.metadata["issues"]},
        )

    def test_grid_xml_verifier_rejects_wrong_serializer_view_options_and_column_values(self):
        columns = [{"field_name": "PRICE", "caption": "Unit price", "data_type": "decimal(18, 2)"}]
        valid_xml = generate_devexpress_grid_xml(columns)
        mutations = {
            "serializer": valid_xml.replace('version="1.0"', 'version="2.0"', 1),
            "view": valid_xml.replace(
                '<property name="BestFitMaxRowCount">-1</property>',
                '<property name="BestFitMaxRowCount">0</property>',
                1,
            ),
            "options": valid_xml.replace(
                '<property name="ShowFooter">true</property>',
                '<property name="ShowFooter">false</property>',
                1,
            ),
            "appearance": valid_xml.replace(
                '<property name="Font">Tahoma, 9pt</property>',
                '<property name="Font">Arial, 9pt</property>',
                1,
            ),
            "field": valid_xml.replace(
                '<property name="FieldName">PRICE</property>',
                '<property name="FieldName">price</property>',
                1,
            ),
            "caption": valid_xml.replace(
                '<property name="Caption">PRICE</property>',
                '<property name="Caption">Unit price</property>',
                1,
            ),
            "column_edit_name": valid_xml.replace(
                '<property name="ColumnEditName" />',
                '<property name="ColumnEditName">repSpin</property>',
                1,
            ),
        }
        for case, xml_text in mutations.items():
            with self.subTest(case=case):
                result = verify_devexpress_grid_xml_contract(xml_text, expected_columns=columns)
                self.assertFalse(result.success, result.to_dict())
                self.assertGreater(len(result.metadata["issues"]), 0)

    def test_handwritten_grid_xml_accepts_list_detail_table_and_purpose_roles(self):
        cases = [
            ("list", "", "", "colList_", "ENTITY_ID"),
            ("detail", "", "", "colDetail_", "LINE_ID"),
            ("table", "ORDER", "", "colORDER_", "ORDER_ID"),
            ("purpose", "", "LEDGER", "colLEDGER_", "ENTRY_ID"),
        ]
        for role, table_name, purpose_name, prefix, field_name in cases:
            with self.subTest(role=role):
                result = verify_devexpress_grid_xml_contract(
                    handwritten_grid_xml(field_name, prefix),
                    expected_columns=[{"field_name": field_name, "data_type": "string"}],
                    input_format=role,
                    table_name=table_name,
                    purpose_name=purpose_name,
                )
                self.assertTrue(result.success, result.to_dict())

    def test_grid_xml_security_hierarchy_and_duplicate_checks_fail_closed(self):
        valid_xml = handwritten_grid_xml("ENTITY_ID", "colList_")
        mutations = {
            "dtd": '<!DOCTYPE XtraSerializer [<!ENTITY x "boom">]>' + valid_xml,
            "entity": '<!ENTITY x "boom">' + valid_xml,
            "duplicate": valid_xml.replace(
                '<property name="BestFitMaxRowCount">-1</property>',
                '<property name="BestFitMaxRowCount">-1</property>\n  <property name="BestFitMaxRowCount">-1</property>',
                1,
            ),
            "unexpected": valid_xml.replace(
                '<property name="#LayoutVersion" />',
                '<property name="#LayoutVersion" />\n  <property name="Unexpected">x</property>',
                1,
            ),
            "deep": valid_xml.replace(
                '<property name="#LayoutVersion" />',
                '<property name="#LayoutVersion">' + '<property name="X">' * 9 + '</property>' * 9 + '</property>',
                1,
            ),
        }
        for case, xml_text in mutations.items():
            with self.subTest(case=case):
                result = verify_devexpress_grid_xml_contract(
                    xml_text,
                    expected_columns=[{"field_name": "ENTITY_ID", "data_type": "string"}],
                )
                self.assertFalse(result.success, result.to_dict())
        oversized = verify_devexpress_grid_xml_contract(" " * (1024 * 1024 + 1))
        self.assertFalse(oversized.success, oversized.to_dict())
        self.assertIn("grid_xml_size_limit_exceeded", {item["code"] for item in oversized.metadata["issues"]})

    def test_grid_xml_rejects_wrong_view_name_column_name_and_visible_index(self):
        valid_xml = handwritten_grid_xml("ENTITY_ID", "colList_")
        mutations = [
            valid_xml.replace(">gridView1</property>", ">gvwList</property>", 1),
            valid_xml.replace(">colList_ENTITY_ID</property>", ">colWrong_ENTITY_ID</property>", 1),
            valid_xml.replace('<property name="VisibleIndex">1</property>', '<property name="VisibleIndex">0</property>', 1),
        ]
        for xml_text in mutations:
            result = verify_devexpress_grid_xml_contract(
                xml_text,
                expected_columns=[{"field_name": "ENTITY_ID", "data_type": "string"}],
            )
            self.assertFalse(result.success, result.to_dict())
        csharp_mapping_is_separate = verify_devexpress_grid_xml_contract(
            valid_xml,
            expected_columns=[
                {"field_name": "ENTITY_ID", "csharp_name": "colWrong_ENTITY_ID", "data_type": "string"}
            ],
        )
        self.assertTrue(csharp_mapping_is_separate.success, csharp_mapping_is_separate.to_dict())

    def test_packaged_contract_records_exact_layout_load_values(self):
        payload = json.loads(
            Path("skills/pb_to_csharp_migration_harness/references/packaged-style-contract.json").read_text(encoding="utf-8")
        )
        layout = payload["grid_layout_load_contract"]
        self.assertEqual(layout["serializer"], {"version": "1.0", "application": "View"})
        self.assertEqual(layout["xml_view_defaults"]["ScrollStyle"], "LiveVertScroll, LiveHorzScroll")
        self.assertEqual(layout["xml_view_defaults"]["DetailHeight"], "350")
        self.assertEqual(layout["xml_options_view_defaults"]["ShowAutoFilterRow"], "true")
        self.assertEqual(layout["xml_column_defaults"]["AppearanceHeader.Font"], "Tahoma, 9pt")
        self.assertEqual(layout["xml_column_defaults"]["ColumnEditName"], "")
        self.assertTrue(layout["csharp_designer_result"]["xml_view_name_is_not_csharp_name"])

    def test_extracts_pb_occurrence_order_with_csharp_names_and_matched_captions(self):
        source = """
datawindow(units=0)
table(column=(type=char(10) updatewhereclause=no name=as_record_name dbname="as_record_name" )
 column=(type=char(10) updatewhereclause=no name=as_record_code dbname="as_record_code" )
 )
column(band=detail id=2 x="178" y="12" height="60" width="699" name=as_record_code )
column(band=detail id=1 x="1056" y="12" height="60" width="686" name=as_record_name )
text(band=detail text="코드" x="18" y="12" height="60" width="133" name=t_1 )
text(band=detail text="품명" x="901" y="12" height="60" width="133" name=as_item_t )
"""
        specs = extract_datawindow_column_specs(source)
        xml_text = generate_devexpress_grid_xml(specs)
        designer_plan = build_csharp_grid_column_designer_plan(
            specs,
            result_fields=[spec.field_name for spec in specs],
        )

        self.assertEqual([spec.field_name for spec in specs], ["AS_RECORD_NAME", "AS_RECORD_CODE"])
        self.assertEqual([spec.caption for spec in specs], ["품명", "코드"])
        self.assertEqual([spec.csharp_name for spec in specs], ["colList_AS_RECORD_NAME", "colList_AS_RECORD_CODE"])
        self.assertLess(xml_text.index("AS_RECORD_NAME"), xml_text.index("AS_RECORD_CODE"))
        self.assertIn("<property name=\"Caption\">AS_RECORD_CODE</property>", xml_text)
        self.assertIn("<property name=\"Caption\">AS_RECORD_NAME</property>", xml_text)
        self.assertIn("<property name=\"Name\">colList_AS_RECORD_CODE</property>", xml_text)
        self.assertIn('this.colList_AS_RECORD_CODE.Caption = "코드";', designer_plan.stdout)
        self.assertIn('this.colList_AS_RECORD_NAME.Caption = "품명";', designer_plan.stdout)

    def test_matches_header_band_captions_to_detail_columns(self):
        source = """
datawindow(units=0)
header(height=80)
detail(height=70)
table(column=(type=char(10) name=record_code dbname="record_code" )
 column=(type=char(10) name=record_name dbname="record_name" ))
text(band=header text="품목코드" x="100" y="8" height="40" width="220" name=t_record_code )
text(band=header text="품목명" x="340" y="8" height="40" width="260" name=t_record_name )
column(band=detail x="100" y="12" height="50" width="220" name=record_code )
column(band=detail x="340" y="12" height="50" width="260" name=record_name )
"""
        specs = extract_datawindow_column_specs(source)

        self.assertEqual([spec.field_name for spec in specs], ["RECORD_CODE", "RECORD_NAME"])
        self.assertEqual([spec.caption for spec in specs], ["품목코드", "품목명"])

    def test_resolves_csharp_grid_column_prefix_variants(self):
        self.assertEqual(resolve_csharp_grid_column_prefix("list"), "colList_")
        self.assertEqual(resolve_csharp_grid_column_prefix("detail"), "colDetail_")
        self.assertEqual(resolve_csharp_grid_column_prefix("table", table_name="ZX900T"), "colZX900T_")
        self.assertEqual(resolve_csharp_grid_column_prefix("purpose", purpose_name="BROWSE"), "colBROWSE_")
        self.assertEqual(resolve_csharp_grid_column_prefix("table", purpose_name="TREE"), "colTREE_")
        self.assertEqual(resolve_csharp_grid_column_prefix("colCustom_"), "colCustom_")
        self.assertEqual(resolve_csharp_grid_column_prefix("table"), "colTable_")
        self.assertEqual(resolve_csharp_grid_column_prefix("purpose"), "colPurpose_")
        self.assertEqual(build_csharp_grid_column_name("record_code", prefix="colDetail_"), "colDetail_RECORD_CODE")

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
            resolve_csharp_grid_control_names("table", table_name="ZX900T"),
            {"grid_control_name": "grdZX900T", "grid_view_name": "gvwZX900T"},
        )
        self.assertEqual(
            resolve_csharp_grid_control_names("purpose", purpose_name="BROWSE"),
            {"grid_control_name": "grdBROWSE", "grid_view_name": "gvwBROWSE"},
        )
        self.assertEqual(
            resolve_csharp_grid_control_names("table", purpose_name="TREE"),
            {"grid_control_name": "grdTREE", "grid_view_name": "gvwTREE"},
        )
        self.assertEqual(
            resolve_csharp_grid_control_names("table"),
            {"grid_control_name": "grdTable", "grid_view_name": "gvwTable"},
        )
        self.assertEqual(
            resolve_csharp_grid_control_names("purpose"),
            {"grid_control_name": "grdPurpose", "grid_view_name": "gvwPurpose"},
        )

    def test_datawindow_layout_metadata_records_column_prefix_and_captions(self):
        source = """
datawindow(units=0)
column(band=detail x="100" y="10" height="50" width="200" name=record_code )
text(band=detail text="품목코드" x="10" y="10" height="50" width="80" name=t_record_code )
"""
        result = build_datawindow_grid_layout(source, input_format="table", table_name="ZX901T")

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["csharp_column_prefix"], "colZX901T_")
        self.assertEqual(
            result.metadata["csharp_grid_names"],
            {"grid_control_name": "grdZX901T", "grid_view_name": "gvwZX901T"},
        )
        self.assertEqual(result.metadata["column_specs"][0]["csharp_name"], "colZX901T_RECORD_CODE")
        self.assertEqual(result.metadata["column_specs"][0]["caption"], "품목코드")
        self.assertIn("<property name=\"Name\">gridView1</property>", result.stdout)
        self.assertIn("<property name=\"Name\">colZX901T_RECORD_CODE</property>", result.stdout)
        self.assertIn("<property name=\"Caption\">RECORD_CODE</property>", result.stdout)

    def test_datawindow_layout_uses_purpose_name_when_table_name_is_ambiguous(self):
        source = """
datawindow(units=0)
column(band=detail x="100" y="10" height="50" width="200" name=sequence_id )
text(band=detail text="Sequence" x="10" y="10" height="50" width="80" name=t_sequence_id )
"""
        result = build_datawindow_grid_layout(source, input_format="purpose", purpose_name="BROWSE")

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["csharp_column_prefix"], "colBROWSE_")
        self.assertEqual(
            result.metadata["csharp_grid_names"],
            {"grid_control_name": "grdBROWSE", "grid_view_name": "gvwBROWSE"},
        )
        self.assertEqual(result.metadata["column_specs"][0]["csharp_name"], "colBROWSE_SEQUENCE_ID")
        self.assertEqual(result.metadata["column_specs"][0]["caption"], "Sequence")
        self.assertIn("<property name=\"Name\">gridView1</property>", result.stdout)
        self.assertIn("<property name=\"Name\">colBROWSE_SEQUENCE_ID</property>", result.stdout)
        self.assertIn("<property name=\"Caption\">SEQUENCE_ID</property>", result.stdout)

    def test_raw_converter_name_default_is_distinct_from_target_csharp_layout_name(self):
        xml_text = generate_devexpress_grid_xml(["RECORD_CODE"])
        layout = build_datawindow_grid_layout("column(band=detail x=\"1\" y=\"1\" width=\"10\" height=\"10\" name=record_code )")
        legacy_named = build_datawindow_grid_layout(
            "column(band=detail x=\"1\" y=\"1\" width=\"10\" height=\"10\" name=record_code )",
            grid_view_name="legacySerializedView",
        )

        self.assertIn("<property name=\"Name\">gridView1</property>", xml_text)
        self.assertEqual(layout.metadata["csharp_grid_names"]["grid_view_name"], "gvwList")
        self.assertEqual(layout.metadata["serialized_grid_view_name"], "gridView1")
        self.assertIn("<property name=\"Name\">gridView1</property>", layout.stdout)
        self.assertIn("<property name=\"Name\">legacySerializedView</property>", legacy_named.stdout)
        self.assertEqual(legacy_named.metadata["csharp_grid_names"]["grid_view_name"], "gvwList")
        self.assertTrue(legacy_named.metadata["legacy_grid_view_name_alias_used"])

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
            this.radMODE_CODE = new KoneLib.Controls.u_RadioButton();
            this.txtInputValue = new KoneLib.Controls.u_TextEdit();
            this.btnENTITY_CODE = new KoneLib.Controls.u_ButtonEdit();
            this.lblInputValue = new DevExpress.XtraEditors.LabelControl();
            this.grdList = new KoneLib.Controls.u_GridControl();
            this.gvwList = new DevExpress.XtraGrid.Views.Grid.GridView();
            this.colList_AMTTOT = new DevExpress.XtraGrid.Columns.GridColumn();
            this.Controls.Add(this.grpSearch);
            this.grpSearch.Controls.Add(this.radMODE_CODE);
            this.grpSearch.Controls.Add(this.txtInputValue);
            this.grpSearch.Controls.Add(this.btnENTITY_CODE);
            this.radMODE_CODE._isAllowBlank = true;
            this.radMODE_CODE._isPKValue = false;
            this.radMODE_CODE.BindingField = "MODE_CODE";
            this.radMODE_CODE.EditValue = "T";
            this.radMODE_CODE.EnterMoveNextControl = true;
            this.radMODE_CODE.Location = new System.Drawing.Point(733, 31);
            this.radMODE_CODE.Properties.Items.AddRange(new DevExpress.XtraEditors.Controls.RadioGroupItem[] {
            new DevExpress.XtraEditors.Controls.RadioGroupItem("T", "전체"),
            new DevExpress.XtraEditors.Controls.RadioGroupItem("A", "출고")});
            this.radMODE_CODE.Size = new System.Drawing.Size(260, 23);
            this.radMODE_CODE.TabIndex = 7;
            this.txtInputValue._isAllowBlank = false;
            this.txtInputValue.BindingField = "INPUT_VALUE";
            this.txtInputValue.MaximumSize = new System.Drawing.Size(65535, 23);
            this.txtInputValue.MinimumSize = new System.Drawing.Size(0, 23);
            this.txtInputValue.Properties.AutoHeight = false;
            this.txtInputValue.Properties.Mask.EditMask = "0000";
            this.txtInputValue.Properties.Mask.MaskType = DevExpress.XtraEditors.Mask.MaskType.Simple;
            this.btnENTITY_CODE.BindingField = "ENTITY_CODE";
            this.btnENTITY_CODE.Properties.Buttons.AddRange(new DevExpress.XtraEditors.Controls.EditorButton[] {
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
            private KoneLib.Controls.u_RadioButton radMODE_CODE;
            private KoneLib.Controls.u_TextEdit txtInputValue;
            private KoneLib.Controls.u_ButtonEdit btnENTITY_CODE;
            private DevExpress.XtraEditors.LabelControl lblInputValue;
            private KoneLib.Controls.u_GridControl grdList;
            private DevExpress.XtraGrid.Views.Grid.GridView gvwList;
            private DevExpress.XtraGrid.Columns.GridColumn colList_AMTTOT;
        '''

        result = extract_csharp_designer_control_specs(designer_source)
        payload = json.loads(result.stdout)
        controls = {item["name"]: item for item in payload["controls"]}

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(controls["radMODE_CODE"]["type_name"], "KoneLib.Controls.u_RadioButton")
        self.assertEqual(controls["radMODE_CODE"]["binding_field"], "MODE_CODE")
        self.assertEqual(controls["radMODE_CODE"]["properties"]["_isAllowBlank"], True)
        self.assertEqual(controls["radMODE_CODE"]["properties"]["_isPKValue"], False)
        self.assertEqual(controls["radMODE_CODE"]["properties"]["EditValue"], "T")
        self.assertEqual(controls["radMODE_CODE"]["properties"]["EnterMoveNextControl"], True)
        self.assertEqual(controls["radMODE_CODE"]["location"], {"x": 733, "y": 31})
        self.assertEqual(controls["radMODE_CODE"]["size"], {"width": 260, "height": 23})
        self.assertEqual(controls["radMODE_CODE"]["tab_index"], 7)
        self.assertIn("Properties.Items.AddRange", controls["radMODE_CODE"]["collection_calls"])
        self.assertEqual(controls["txtInputValue"]["binding_field"], "INPUT_VALUE")
        self.assertEqual(controls["txtInputValue"]["properties"]["Properties.AutoHeight"], False)
        self.assertEqual(controls["txtInputValue"]["properties"]["Properties.Mask.EditMask"], "0000")
        self.assertEqual(controls["txtInputValue"]["properties"]["MaximumSize"], {"width": 65535, "height": 23})
        self.assertIn("Properties.Buttons.AddRange", controls["btnENTITY_CODE"]["collection_calls"])
        self.assertEqual(controls["btnENTITY_CODE"]["parent_name"], "grpSearch")
        self.assertEqual(controls["grpSearch"]["parent_name"], "this")
        self.assertEqual(controls["grpSearch"]["children"], ["radMODE_CODE", "txtInputValue", "btnENTITY_CODE"])
        self.assertEqual(payload["grid_columns_present"], True)
        self.assertEqual(payload["grid_column_count"], 1)
        self.assertEqual(payload["grid_columns"][0]["name"], "colList_AMTTOT")
        self.assertEqual(controls["lblInputValue"]["caption"], "")
        self.assertEqual(controls["grdList"]["properties"]["MainView"], "this.gvwList")
        self.assertIn("ViewCollection.AddRange", controls["grdList"]["collection_calls"])
        self.assertEqual(controls["gvwList"]["properties"]["GridControl"], "this.grdList")

    def test_csharp_designer_string_values_preserve_korean_text(self):
        result = extract_csharp_designer_control_specs(
            '''
            this.lblInputValue = new DevExpress.XtraEditors.LabelControl();
            this.lblInputValue.Text = "기준년도";
            this.lblInputValue.Name = "lblInputValue";
            '''
        )
        controls = {item["name"]: item for item in json.loads(result.stdout)["controls"]}

        self.assertEqual(controls["lblInputValue"]["caption"], "기준년도")
        self.assertEqual(controls["lblInputValue"]["properties"]["Text"], "기준년도")

    def test_generated_csharp_style_blocks_runtime_columns_add_even_with_designer_members(self):
        generated = '''
        private DevExpress.XtraGrid.Columns.GridColumn colList_DISPLAY_NAME;
        this.colList_DISPLAY_NAME = new DevExpress.XtraGrid.Columns.GridColumn();
        this.gvwList.Columns.AddRange(new DevExpress.XtraGrid.Columns.GridColumn[] {
        this.colList_DISPLAY_NAME});
        DevExpress.XtraGrid.Columns.GridColumn runtimeColumn = new DevExpress.XtraGrid.Columns.GridColumn();
        runtimeColumn.FieldName = "RECORD_CODE";
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
        columns = [{"field_name": "AMTTOT", "caption": "Amount", "data_type": "decimal(18, 2)"}]
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
        _, generated = valid_devexpress_grid_designer(
            columns=columns,
        )

        result = _verify_migration_generated_csharp_style(
            generated,
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            source_role="designer",
            form_class="RecordsBrowseForm",
            expected_grid_role="list",
            expected_grid_columns=columns,
            layout_load_artifact_text=generate_devexpress_grid_xml(columns),
        )

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
            AddGridColumn(gvwList, "DISPLAY_NAME", "고객", 160, true, false);
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

    def test_generated_csharp_style_blocks_zx123456_followup_generated_helpers(self):
        generated = '''
        private void ZX123456_Load(object sender, EventArgs e)
        {
            SetDefaultSearchValues();
            ApplyListColumnLayout();
        }

        private bool ValidateSearch()
        {
            ShowMessageError("\u6e72\uacd7");
            return true;
        }

        private string GetDerivedYear()
        {
            return ymdInput.Text.Trim();
        }

        private string GetEntityCodeLike()
        {
            return btnENTITY_CODE.Text.Trim() + "%";
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

        private void BtnENTITY_CODE_ButtonClick(object sender, DevExpress.XtraEditors.Controls.ButtonPressedEventArgs e)
        {
            EntityLookupDialog pop = new EntityLookupDialog();
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

    def test_legacy_baseline_api_returns_a_detached_generalized_recipe_without_corpus_metrics(self):
        baseline = get_author_tagged_csharp_style_baseline()
        second = get_author_tagged_csharp_style_baseline()

        self.assertIsInstance(baseline, dict)
        self.assertEqual("packaged_sanitized_profile", baseline["source"])
        self.assertIn("positive_generation_recipe", baseline)
        for removed_metric in (
            "sp_count",
            "normalized_program_key_count",
            "primary_csharp_baseline_files_analyzed",
            "designer_files_analyzed",
            "primary_csharp_pattern_counts",
            "designer_pattern_counts",
            "zero_hit_generated_patterns",
        ):
            with self.subTest(removed_metric=removed_metric):
                self.assertNotIn(removed_metric, baseline)
        baseline["mutated_by_test"] = True
        self.assertNotIn("mutated_by_test", second)

    def test_author_tagged_program_style_profiles_are_packaged(self):
        profile_path = Path("skills/pb_to_csharp_migration_harness/references/packaged-style-contract.json")
        payload = json.loads(profile_path.read_text(encoding="utf-8"))

        profile_hash = "sha256:" + hashlib.sha256(profile_path.read_bytes()).hexdigest()
        loaded = load_packaged_migration_profile(
            payload["contract_id"],
            payload["contract_version"],
            profile_hash,
        )

        self.assertEqual("packaged-only", payload["normal_generation"]["profile_source"])
        self.assertFalse(payload["normal_generation"]["external_discovery_allowed"])
        self.assertTrue(loaded.success, loaded.to_dict())
        self.assertEqual(profile_hash, loaded.metadata["profile_consumption"]["profile_hash"])

    def test_author_tagged_style_evidence_resolves_sp_to_program_key(self):
        self.assertEqual("GENERALIZED", normalize_author_tagged_program_key("DBO.SP_GENERALIZED_SELECT"))
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                resolved = resolve_author_tagged_style_evidence(
                    "SP_GENERALIZED_SELECT",
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                )

        self.assertTrue(resolved.success, resolved.to_dict())
        self.assertEqual("GENERALIZED", resolved.metadata["program_key"])
        self.assertEqual([], resolved.metadata["primary_style_evidence_paths"])
        self.assertFalse(resolved.metadata["path_evidence_accepted"])

    def test_runtime_style_resolution_does_not_discover_same_program_files_under_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = resolve_author_tagged_style_evidence(
                "SP_GENERALIZED_SELECT",
                csharp_root=temp_dir,
            )

        self.assertFalse(resolved.success)
        self.assertEqual("explicit_profile_update_required", resolved.metadata["status"])

    def test_author_tagged_style_evidence_blocks_stale_root_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = resolve_author_tagged_style_evidence("SP_GENERALIZED_SELECT", csharp_root=temp_dir)

        self.assertFalse(resolved.success)
        self.assertEqual("explicit_profile_update_required", resolved.metadata["status"])

    def test_author_tagged_style_evidence_uses_bundled_program_profile_without_live_root(self):
        missing_identity = resolve_author_tagged_style_evidence("SP_GENERALIZED_SELECT")

        self.assertFalse(missing_identity.success)
        self.assertEqual("blocked", missing_identity.metadata["status"])
        self.assertIn(
            "packaged_profile_identity_required",
            {issue["code"] for issue in missing_identity.metadata["issues"]},
        )

    def test_build_plan_dict_state_preserves_generalized_profile_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                result = build_pb_to_csharp_migration_plan(
                    "Migrate a generalized screen with the packaged style.",
                    {
                        "target_style": "generalized",
                        "procedure_name": "SP_GENERALIZED_SELECT",
                        "has_sp_style_reference": True,
                        "profile_id": "pb-csharp-offline-generalized",
                        "profile_version": "1.0",
                        "profile_hash": profile_hash,
                    },
                )

        self.assertTrue(result.success, result.to_dict())
        resolution = result.metadata["packaged_style_resolution"]
        self.assertEqual("GENERALIZED", resolution["program_key"])
        self.assertEqual("loaded", resolution["status"])
        self.assertTrue(resolution["profile_consumption"]["profile_hash_verified"])

    def test_migration_analysis_document_quality_blocks_short_log_level_summary(self):
        shallow = """
        # PB migration notes

        ## Objective
        Migrate ZX234567 to C#.

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
        # ZX234567 PB-to-C# migration analysis

        ## 1. Objective and target operator
        Objective: migrate the PowerBuilder production detail workflow into a C# WinForms screen.
        Target operator: production planner who selects rows, chooses detail items, and saves the result.

        ## 2. PB source evidence
        Source evidence: prod_003.pbl, synthetic_source_a.sru, linked SRW popup, and SRD DataWindow objects.
        The PB source trace records clicked event behavior, Retrieve arguments, DataWindow fields, and source gaps.

        ```powerscript
        // PB clicked event source evidence from synthetic_source_a.sru
        dw_main.AcceptText()
        if dw_main.GetRow() <= 0 then return
        ```

        ## 3. User workflow
        User workflow: select a production order row, click detail, open popup, choose item, confirm save,
        refresh list, and verify the result in the grid.

        ## 4. C# implementation scope
        Target C# scope: WinForms form, DevExpress grid, Designer GridColumn members, BindingField assignments,
        popup result handling, DbParameter-based CallProc or CallViewQuery path, and refresh binding.

        ```csharp
        // target C# evidence
        dbClient.GetDataSetFromSP("sp_ZX234567_SELECT", new DbParameter("@WORKTYPE", "LIST"));
        ```

        ## 5. Event and call flow
        Event/call flow: button click handler -> selected row validation -> duplicate detail validation
        -> popup call -> save confirmation -> SP SAVE call -> grid refresh.

        ## 6. DB and SP mapping
        DB/SP mapping: SELECT branch returns target row data, SAVE branch performs INSERT into SYNTHETIC_TARGET and UPDATE SYNTHETIC_SOURCE.
        @WORKTYPE distinguishes LIST, DETAIL, and SAVE semantics. No source-unbacked schema-only fallback is allowed.

        ```sql
        INSERT INTO SYNTHETIC_TARGET (SCOPE_CODE, RECORD_ID, RECORD_SEQUENCE)
        SELECT A.SCOPE_CODE, A.RECORD_ID, A.RECORD_SEQUENCE
          FROM SYNTHETIC_SOURCE A
         WHERE A.SCOPE_CODE = @SCOPE_CODE;
        ```

        ## 7. Transaction and error handling
        transaction boundary: INSERT and UPDATE run in one transaction; rollback on validation failure.
        RAISERROR message is used for duplicate or completed-process conflicts.

        ```sql
        IF EXISTS (SELECT 1 FROM SYNTHETIC_TARGET WHERE SCOPE_CODE = @SCOPE_CODE)
            RAISERROR('Already processed.', 16, 1);
        ```

        ## 8. Implementation order
        Implementation order: preserve existing button, comment old incompatible code, add popup call,
        add save SP branch, update Designer grid columns, then verify build and manual flow.

        ## 9. Constraints and business rules
        Required business rules: preserve RECORD_ID + RECORD_SEQUENCE key, do not save with RECORD_ID alone,
        do not invent C# wildcard shaping, and keep source Korean literals unchanged.

        ## 10. Manual test scenarios
        Verification plan: normal save, popup cancel, duplicate detail row, completed process conflict,
        grid refresh, SP rollback check, and C# build check.

        ```text
        manual test case: choose one valid row, select popup item, save, verify SYNTHETIC_TARGET insert and SYNTHETIC_SOURCE update.
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
        | C# screen | ZX234567.cs | add button handler and CallProc path | build succeeds |
        | Designer | ZX234567.Designer.cs | add explicit GridColumn members | BindingField and Caption match |
        | SQL procedure | sp_ZX234567_SAVE procedure | add SAVE @WORKTYPE branch | SP contract passes review |

        ### User directive and approved scope
        User directive: migrate the confirmed PB detail workflow and preserve the current target style.
        Approved scope: C# handler, Designer columns, and SAVE branch only. Out-of-scope findings such as
        unrelated SQL cleanup, library upgrades, or inferred UI convenience logic are proposal-only and do not
        implement without explicit approval.

        ### PB event to C# event mapping
        | PB event | C# method / handler | validation | output |
        | --- | --- | --- | --- |
        | clicked | btnOpenDetail_Click handler | selected row and duplicate check | popup save call |

        ### DataWindow field mapping
        | DataWindow | PB column / field | C# control / GridColumn | BindingField | Caption |
        | --- | --- | --- | --- | --- |
        | dw_main | RECORD_ID | colList_RECORD_ID GridColumn | RECORD_ID | Order No |
        | dw_main | RECORD_CODE | btnRECORD_CODE control | RECORD_CODE | Item |

        ### Control layout and binding plan
        | control | type | BindingField | TabIndex | note |
        | --- | --- | --- | --- | --- |
        | lblRECORD_CODE | LabelControl |  | 0 | item label |
        | btnRECORD_CODE | ButtonEdit | RECORD_CODE | 1 | target control |
        | gvwList | GridView |  | 10 | list view |

        ### SP contract matrix
        | SP contract | @WORKTYPE | parameter | result column | DML |
        | --- | --- | --- | --- | --- |
        | sp_ZX234567_SAVE | SAVE | @SCOPE_CODE, @XML | RECORD_ID, RECORD_SEQUENCE | INSERT SYNTHETIC_TARGET / UPDATE SYNTHETIC_SOURCE |

        ### Style profile contract
        Packaged style profile: use program key ZX234567. If unmapped, use fallback program ZX345678
        with source hash and Designer hash evidence before applying style patterns.

        ### Implementation task list
        1. implementation task: update ZX234567.cs handler; acceptance: selected row validation is preserved.
        2. implementation task: update ZX234567.Designer.cs grid columns; done criteria: explicit AddRange columns exist.
        3. implementation task: update SQL SAVE branch; acceptance: transaction and RAISERROR behavior match.

        ### Verification contract
        manual test: save one valid row. expected UI: grid refresh shows the saved row.
        expected DB: SYNTHETIC_TARGET insert and SYNTHETIC_SOURCE update exist. build and rollback checks must pass.

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

    def test_migration_analysis_document_quality_blocks_missing_user_scope_contract(self):
        document = """
        # ZX234567 PB-to-C# migration analysis

        Objective: migrate the PowerBuilder production detail workflow for the target operator.
        PB source evidence: synthetic_source_a.sru, synthetic_source_a.srw, DataWindow dw_main, PBL and SRD export.
        User workflow: button click, selected row validation, popup, save, grid refresh.
        Target C# implementation scope: WinForms, DevExpress GridColumn members, BindingField assignments,
        DbParameter-based CallProc, CallViewQuery, Designer.cs changes, and procedure work.
        Event and call flow: PB event mapping to C# handler with click validation and popup result handling.
        DB/SP mapping: SELECT, SAVE, INSERT, UPDATE, DELETE, @WORKTYPE, transaction, RAISERROR.
        Implementation order: analyze PB, update C#, update Designer, update SP, run verification.
        Constraints and business rules: preserve RECORD_ID and RECORD_SEQUENCE, Korean literals, comments, and row contracts.
        Manual test scenarios: build verification, manual UI verification, rollback verification, expected DB result.
        LLM implementation handoff: analysis agent passes this handoff to developer agent with no hidden context.

        ```csharp
        dbClient.GetDataSetFromSP("sp_ZX234567_SELECT", new DbParameter("@WORKTYPE", "LIST"));
        ```

        ```sql
        INSERT INTO SYNTHETIC_TARGET (SCOPE_CODE, RECORD_ID, RECORD_SEQUENCE)
        SELECT A.SCOPE_CODE, A.RECORD_ID, A.RECORD_SEQUENCE
          FROM SYNTHETIC_SOURCE A
         WHERE A.SCOPE_CODE = @SCOPE_CODE;
        ```

        ## Cross-agent development specification
        Analysis agent and developer agent must use this development handoff.
        target file plan: ZX234567.cs, ZX234567.Designer.cs, sp_ZX234567_SAVE procedure.
        PB event to C# method mapping: clicked event -> btnSave_Click handler.
        DataWindow field mapping: DataWindow column RECORD_ID -> GridColumn colList_RECORD_ID, BindingField RECORD_ID, Caption.
        control layout binding plan: control, TabIndex, BindingField, LabelControl, GridView.
        SP contract matrix: @WORKTYPE, parameter, result column, DML, procedure contract.
        style profile contract: packaged style program key ZX234567, fallback program, source hash.
        implementation task list: implementation task, task list, done criteria, acceptance.
        verification contract: manual test, expected UI, expected DB, build, rollback.
        confirmed: PB clicked event. inferred: popup caption. blocked: missing DB schema.
        """

        result = verify_pb_migration_analysis_document(document)

        self.assertFalse(result.success)
        self.assertFalse(result.metadata["development_spec_coverage"]["user_directive_scope_contract"])
        self.assertIn(
            "user_directive_scope_contract",
            {
                issue.get("spec_item")
                for issue in result.metadata["issues"]
                if issue["code"] == "migration_analysis_development_spec_missing"
            },
        )

    def test_migration_analysis_document_quality_blocks_thin_user_scope_keyword(self):
        document = """
        # ZX234567 PB-to-C# migration analysis

        Objective: migrate the PowerBuilder production detail workflow for the target operator.
        PB source evidence: synthetic_source_a.sru, synthetic_source_a.srw, DataWindow dw_main, PBL and SRD export.
        User workflow: button click, selected row validation, popup, save, grid refresh.
        Target C# implementation scope: WinForms, DevExpress GridColumn members, BindingField assignments,
        DbParameter-based CallProc, CallViewQuery, Designer.cs changes, and procedure work.
        Event and call flow: PB event mapping to C# handler with click validation and popup result handling.
        DB/SP mapping: SELECT, SAVE, INSERT, UPDATE, DELETE, @WORKTYPE, transaction, RAISERROR.
        Implementation order: analyze PB, update C#, update Designer, update SP, run verification.
        Constraints and business rules: preserve RECORD_ID and RECORD_SEQUENCE, Korean literals, comments, and row contracts.
        Manual test scenarios: build verification, manual UI verification, rollback verification, expected DB result.
        LLM implementation handoff: analysis agent passes this handoff to developer agent with no hidden context.

        ```csharp
        dbClient.GetDataSetFromSP("sp_ZX234567_SELECT", new DbParameter("@WORKTYPE", "LIST"));
        ```

        ```sql
        INSERT INTO SYNTHETIC_TARGET (SCOPE_CODE, RECORD_ID, RECORD_SEQUENCE)
        SELECT A.SCOPE_CODE, A.RECORD_ID, A.RECORD_SEQUENCE
          FROM SYNTHETIC_SOURCE A
         WHERE A.SCOPE_CODE = @SCOPE_CODE;
        ```

        ## Cross-agent development specification
        Analysis agent and developer agent must use this development handoff.
        target file plan: ZX234567.cs, ZX234567.Designer.cs, sp_ZX234567_SAVE procedure.
        approved scope: approved scope exists.
        PB event to C# method mapping: clicked event -> btnSave_Click handler.
        DataWindow field mapping: DataWindow column RECORD_ID -> GridColumn colList_RECORD_ID, BindingField RECORD_ID, Caption.
        control layout binding plan: control, TabIndex, BindingField, LabelControl, GridView.
        SP contract matrix: @WORKTYPE, parameter, result column, DML, procedure contract.
        style profile contract: packaged style program key ZX234567, fallback program, source hash.
        implementation task list: implementation task, task list, done criteria, acceptance.
        verification contract: manual test, expected UI, expected DB, build, rollback.
        confirmed: PB clicked event. inferred: popup caption. blocked: missing DB schema.
        """

        result = verify_pb_migration_analysis_document(document)

        self.assertFalse(result.success)
        details = result.metadata["development_spec_detail_coverage"]["user_directive_scope_contract"]
        self.assertTrue(details["approved_scope_boundary"])
        self.assertFalse(details["user_instruction_authority"])
        self.assertFalse(details["proposal_only_boundary"])

    def test_generated_csharp_style_requires_author_tagged_evidence_when_enabled(self):
        missing = _verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("SP_REFERENCE_SCREEN_SELECT");',
            program_key="ReferenceScreen",
            require_author_tagged_evidence=True,
        )
        self.assertFalse(missing.success)
        self.assertIn("author_tagged_style_evidence_required", {issue["code"] for issue in missing.metadata["issues"]})

        present = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("SP_REFERENCE_SCREEN_SELECT", new DbParameter("@WORKTYPE", "LIST"));',
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="ReferenceScreen",
            primary_style_evidence_paths=[
                r"packaged\style\ReferenceScreen.cs",
                r"packaged\style\ReferenceScreen.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )
        self.assertTrue(present.success, present.to_dict())
        self.assertEqual("REFERENCESCREEN", present.metadata["expected_style_program_key"])
        self.assertIn("author_tagged_generation_recipe", present.metadata)

    def test_generated_csharp_style_blocks_wrong_author_tagged_evidence_path(self):
        result = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("SP_REFERENCE_SCREEN_SELECT", new DbParameter("@WORKTYPE", "LIST"));',
            program_key="ReferenceScreen",
            primary_style_evidence_paths=[
                r"packaged\other\UNRELATED_SCREEN.cs",
                r"packaged\other\UNRELATED_SCREEN.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )

        self.assertFalse(result.success)
        self.assertIn("author_tagged_style_evidence_path_mismatch", {issue["code"] for issue in result.metadata["issues"]})

    def test_generated_csharp_style_rejects_same_filename_without_module_tail(self):
        result = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("SP_REFERENCE_SCREEN_SELECT", new DbParameter("@WORKTYPE", "LIST"));',
            program_key="ReferenceScreen",
            primary_style_evidence_paths=[
                r"C:\tmp\ReferenceScreen.cs",
                r"C:\tmp\ReferenceScreen.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )

        self.assertFalse(result.success)
        self.assertIn("author_tagged_style_evidence_path_mismatch", {issue["code"] for issue in result.metadata["issues"]})

    def test_generated_csharp_style_requires_fallback_for_excluded_author_target(self):
        missing_fallback = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("SP_MIGRATION_TARGET_SELECT", new DbParameter("@WORKTYPE", "LIST"));',
            program_key="MigrationTarget",
            primary_style_evidence_paths=[
                r"packaged\style\ReferenceScreen.cs",
                r"packaged\style\ReferenceScreen.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )
        self.assertFalse(missing_fallback.success)
        self.assertIn("author_tagged_fallback_program_key_required", {issue["code"] for issue in missing_fallback.metadata["issues"]})

        with_fallback = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("SP_MIGRATION_TARGET_SELECT", new DbParameter("@WORKTYPE", "LIST"));',
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="MigrationTarget",
            fallback_program_key="ReferenceScreen",
            primary_style_evidence_paths=[
                r"packaged\style\ReferenceScreen.cs",
                r"packaged\style\ReferenceScreen.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )
        self.assertTrue(with_fallback.success, with_fallback.to_dict())

    def test_generated_csharp_style_blocks_bare_sp_call_under_author_tagged_mode(self):
        result = verify_migration_generated_csharp_style(
            'return dbClient.GetDataSetFromSP("SP_REFERENCE_SCREEN_SELECT");',
            program_key="ReferenceScreen",
            primary_style_evidence_paths=[
                r"packaged\style\ReferenceScreen.cs",
                r"packaged\style\ReferenceScreen.Designer.cs",
            ],
            require_author_tagged_evidence=True,
        )

        self.assertFalse(result.success)
        self.assertIn("author_tagged_sp_call_missing_explicit_dbparameters", {issue["code"] for issue in result.metadata["issues"]})

    def test_generated_csharp_style_blocks_bare_exec_sp_calls_under_author_tagged_mode(self):
        result = verify_migration_generated_csharp_style(
            'dbClient.ExecSP("SP_REFERENCE_SCREEN_SAVE");',
            program_key="ReferenceScreen",
            primary_style_evidence_paths=[
                r"packaged\style\ReferenceScreen.cs",
                r"packaged\style\ReferenceScreen.Designer.cs",
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
            string entityCode = dr["ENTITY_CODE"] == DBNull.Value ? string.Empty : dr["ENTITY_CODE"].ToString().Trim();
            string record_code = dr["PARENT_RECORD_CODE"] == DBNull.Value ? string.Empty : dr["PARENT_RECORD_CODE"].ToString().Trim();
            record_code = string.IsNullOrEmpty(record_code) ? "%" : record_code + "%";
            DataSet ds = CallSelectProcedure(SelectType.DETAIL, entityCode, record_code);
        }

        private DataSet CallSelectProcedure(SelectType _selectType, string _entityCode = null, string _record_code = null)
        {
            string modeCode = Convert.ToString(radMODE_CODE.EditValue);
            string optionCode = Convert.ToString(radOptionCode.EditValue);
            string entityCode = btnENTITY_CODE.EditValue == null ? string.Empty : btnENTITY_CODE.EditValue.ToString().Trim();
            string record_code = _selectType == SelectType.DETAIL ? (_record_code ?? "%") : "%";
            return dbClient.GetDataSetFromSP("sp_ZX123456_SELECT");
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

    def test_generated_csharp_style_blocks_zx123456_leftover_generated_patterns(self):
        generated = '''
        private void ZX123456_SearchCommand(object sender, SearchCommandEventArgs e)
        {
            if (ymdInput.EditValue == null)
                ymdInput.SetToDay(0);

            DataSet ds = CallSelectProcedure(SelectType.LIST, btnENTITY_CODE.Text + "%", "%");
        }

        private void CallDetailQuery()
        {
            DataRow dr = gvwList.GetFocusedDataRow();
            DataSet ds = CallSelectProcedure(SelectType.DETAIL, dr["ENTITY_CODE"].ToString(), dr["PARENT_RECORD_CODE"].ToString() + "%");
        }

        private DataSet CallSelectProcedure(SelectType _selectType, string _entityCode, string _record_code)
        {
            DateTime boundaryDate = new DateTime(DateTime.Now.Year, DateTime.Now.Month, 1).AddDays(-1);
            if (ymdInput.DateTime.Year != boundaryDate.Year)
                boundaryDate = new DateTime(ymdInput.DateTime.Year - 1, 12, 31);

            return dbClient.GetDataSetFromSP("sp_ZX123456_SELECT");
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

            DataSet ds = CallSelectProcedure(SelectType.DETAIL, dr["ENTITY_CODE"].ToString(), dr["PARENT_RECORD_CODE"].ToString());
            grdDetail.DataSource = ds.Tables[0];
        }
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertNotIn("generated_call_detail_query_helper_detected", issue_codes)

    def test_generated_csharp_style_blocks_csharp_sp_parameter_shaping(self):
        generated = '''
        private DataSet CallSelectProcedure(SelectType _selectType, string _entityCode, string _record_code)
        {
            DateTime inputDate = DateTime.Now.AddDays(1 - DateTime.Now.Day).AddDays(-1);
            string entityCode = _entityCode;
            string record_code = _record_code;
            string boundaryDate = inputDate.ToString("yyyyMMdd");

            if (ymdInput.DateTime.Year != inputDate.Year)
                boundaryDate = (ymdInput.DateTime.Year - 1).ToString("0000") + "1231";

            if (_selectType == SelectType.LIST)
            {
                entityCode = btnENTITY_CODE.Text;
                if (string.IsNullOrEmpty(entityCode))
                    entityCode = "%";
                else
                    entityCode = entityCode + "%";

                record_code = "%";
            }
            else if (_selectType == SelectType.DETAIL)
            {
                record_code = record_code + "%";
            }

            return dbClient.GetDataSetFromSP("sp_ZX123456_SELECT");
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
        return dbClient.GetDataSetFromSP("sp_ZX123456_SELECT"
                , new DbParameter("@WORKTYPE", _selectType.ToString())
                , new DbParameter("@SCOPE_CODE", userInfo.ScopeCode)
                , new DbParameter("@ENTITY_CODE", _entityCode)
                , new DbParameter("@DERIVED_YEAR", ymdInput.DateTime.Year.ToString())
                , new DbParameter("@DERIVED_MONTH", DateTime.Now.Month.ToString("00"))
                , new DbParameter("@BASE_YEAR", DateTime.Now.Year.ToString())
                , new DbParameter("@MODE_CODE", radMODE_CODE.EditValue)
                , new DbParameter("@OPTION_CODE", radOptionCode.EditValue)
                , new DbParameter("@RECORD_CODE", _record_code)
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
            public string ENTITY_CODE { get; set; }
        }

        private DataSet CallSelectProcedure(SelectType _selectType, string _entityCode = "", string _record_code = "%")
        {
            DataRow dr = gvwList.GetFocusedDataRow();
            string entityCode = Convert.IsDBNull(dr["ENTITY_CODE"]) ? string.Empty : dr["ENTITY_CODE"].ToString();
            string record_code = dr.IsNull("RECORD_CODE") ? string.Empty : dr["RECORD_CODE"].ToString();
            object qty = gvwList.GetFocusedRowCellValue("QTY") == DBNull.Value ? 0 : gvwList.GetFocusedRowCellValue("QTY");
            if (dr["RECORD_ID"] is DBNull)
                return null;
            return dbClient.GetDataSetFromSP("sp_ZX123456_SELECT");
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
        private KoneLib.Controls.u_DateEdit txtDISPLAY_NAME;
        this.txtDISPLAY_NAME = new KoneLib.Controls.u_DateEdit();
        '''

        result = verify_migration_generated_csharp_style(generated)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("text_name_field_generated_as_dateedit", issue_codes)

    def test_grid_column_designer_plan_uses_explicit_target_column_names(self):
        result = build_csharp_grid_column_designer_plan(
            [
                {"field_name": "DISPLAY_NAME", "caption": "고객", "width": 160},
                {"field_name": "AMTTOT", "caption": "합계", "width": 120},
                {"field_name": "PRICE", "caption": "단가", "width": 100},
            ],
            input_format="list",
            result_fields=["DISPLAY_NAME", "AMTTOT", "PRICE"],
        )

        self.assertTrue(result.success, result.to_dict())
        self.assertIn("private DevExpress.XtraGrid.Columns.GridColumn colList_DISPLAY_NAME;", result.stdout)
        self.assertIn("private DevExpress.XtraGrid.GridControl grdList;", result.stdout)
        self.assertIn("private DevExpress.XtraGrid.Views.Grid.GridView gvwList;", result.stdout)
        self.assertIn("this.grdList.MainView = this.gvwList;", result.stdout)
        self.assertIn("this.grdList.ViewCollection.AddRange", result.stdout)
        self.assertIn("this.gvwList.GridControl = this.grdList;", result.stdout)
        self.assertIn("this.gvwList.Columns.AddRange", result.stdout)
        self.assertIn('this.colList_DISPLAY_NAME.FieldName = "DISPLAY_NAME";', result.stdout)
        self.assertIn('this.colList_DISPLAY_NAME.Name = "colList_DISPLAY_NAME";', result.stdout)
        self.assertIn("private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit rpsSpinAmt;", result.stdout)
        self.assertIn("this.grdList.RepositoryItems.AddRange", result.stdout)
        self.assertIn("this.colList_AMTTOT.ColumnEdit = this.rpsSpinAmt;", result.stdout)
        self.assertIn("this.colList_PRICE.ColumnEdit = this.rpsSpinAmt;", result.stdout)
        self.assertIn("this.gvwList.BestFitMaxRowCount = -1;", result.stdout)
        self.assertIn("this.gvwList.FocusRectStyle = DevExpress.XtraGrid.Views.Grid.DrawFocusRectStyle.CellFocus;", result.stdout)
        self.assertIn("this.gvwList.OptionsView.ShowAutoFilterRow = true;", result.stdout)
        self.assertIn("this.colList_PRICE.AppearanceHeader.Options.UseTextOptions = true;", result.stdout)
        self.assertIn('this.colList_PRICE.AppearanceHeader.Font = new System.Drawing.Font("Tahoma", 9F);', result.stdout)
        self.assertIn("this.colList_PRICE.AppearanceCell.Options.UseFont = true;", result.stdout)
        self.assertNotIn(".DisplayFormat.FormatString", result.stdout)
        self.assertNotIn("ColumnEditName", result.stdout)
        self.assertLess(
            result.stdout.index("this.grdList.RepositoryItems.AddRange"),
            result.stdout.index("this.colList_PRICE.ColumnEdit = this.rpsSpinAmt;"),
        )
        self.assertNotIn("AddGridColumn", result.stdout)
        self.assertNotIn("Columns.AddField", result.stdout)

    def test_grid_column_designer_plan_prefers_data_type_over_field_name_tokens(self):
        result = build_csharp_grid_column_designer_plan(
            [
                {"field_name": "TOTAL_TEXT", "data_type": "string"},
                {"field_name": "QUANTITY", "data_type": "decimal(18, 3)"},
            ],
            input_format="list",
            result_fields=["TOTAL_TEXT", "QUANTITY"],
        )

        repositories = result.metadata["numeric_repository_by_column"]
        self.assertTrue(result.success, result.to_dict())
        self.assertNotIn("colList_TOTAL_TEXT", repositories)
        self.assertIn("colList_QUANTITY", repositories)
        self.assertNotIn("this.colList_TOTAL_TEXT.ColumnEdit", result.stdout)
        self.assertIn("this.colList_QUANTITY.ColumnEdit", result.stdout)
        self.assertEqual("string", result.metadata["columns"][0]["data_type"])
        self.assertEqual("decimal(18, 3)", result.metadata["columns"][1]["data_type"])

    def test_grid_column_designer_plan_fails_fieldname_result_field_mismatch(self):
        result = build_csharp_grid_column_designer_plan(
            [{"field_name": "ENTITY_ID", "data_type": "string"}],
            result_fields=["OTHER_ID"],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "grid_field_result_mismatch",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_grid_column_designer_plan_uses_one_based_indices_and_rejects_name_override(self):
        valid = build_csharp_grid_column_designer_plan(
            [
                {"field_name": "FIRST_ID", "data_type": "string"},
                {"field_name": "SECOND_ID", "data_type": "string"},
            ],
            result_fields=["FIRST_ID", "SECOND_ID"],
        )
        invalid = build_csharp_grid_column_designer_plan(
            [{"field_name": "PRICE", "csharp_name": "colWrong_PRICE", "data_type": "decimal"}],
            result_fields=["PRICE"],
        )
        self.assertTrue(valid.success, valid.to_dict())
        self.assertIn("this.colList_FIRST_ID.VisibleIndex = 1;", valid.stdout)
        self.assertIn("this.colList_SECOND_ID.VisibleIndex = 2;", valid.stdout)
        self.assertFalse(invalid.success, invalid.to_dict())
        self.assertIn("grid_column_csharp_prefix_mismatch", {item["code"] for item in invalid.metadata["issues"]})

    def test_explicit_grid_expectations_require_real_designer_not_comments_strings_raw_or_if_false(self):
        code_behind = '''
        public partial class RecordsBrowseForm : System.Windows.Forms.Form
        {
            public RecordsBrowseForm() { InitializeComponent(); }
            protected void SearchCommand() { CallSelectProcedure(); }
            private void CallSelectProcedure() { this.grdList.DataSource = result; }
        }
        '''
        fake_designer = r'''
        // private DevExpress.XtraGrid.GridControl grdList;
        /* private DevExpress.XtraGrid.Views.Grid.GridView gvwList; */
        var regular = "private DevExpress.XtraGrid.Columns.GridColumn colList_ENTITY_ID;";
        var verbatim = @"this.grdList.MainView = this.gvwList;";
        var interpolated = $"this.gvwList.Columns.AddRange({value});";
        var raw = """this.gvwList.GridControl = this.grdList;""";
        #if false
        private DevExpress.XtraGrid.GridControl grdList;
        private DevExpress.XtraGrid.Views.Grid.GridView gvwList;
        #endif
        '''
        for designer in ("", fake_designer):
            result = _verify_migration_generated_csharp_style(
                code_behind,
                designer_source_text=designer,
                profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
                program_key="RecordsBrowse",
                expected_grid_role="list",
                expected_grid_columns=[{"field_name": "ENTITY_ID", "data_type": "string"}],
                result_fields=["ENTITY_ID"],
            )
            self.assertFalse(result.success, result.to_dict())
            self.assertIn("expected_grid_designer_missing", {item["code"] for item in result.metadata["issues"]})

    def test_explicit_grid_contract_requires_xml_even_with_complete_designer(self):
        columns = [{"field_name": "ENTITY_ID", "caption": "Entity", "data_type": "string"}]
        _, designer = valid_devexpress_grid_designer(columns=columns)
        result = _verify_migration_generated_csharp_style(
            "public partial class RecordsBrowseForm : System.Windows.Forms.Form { public RecordsBrowseForm() { InitializeComponent(); } private void CallSelectProcedure() { this.grdList.DataSource = result; } }",
            designer_source_text=designer,
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="RecordsBrowse",
            expected_grid_role="list",
            expected_grid_columns=columns,
            result_fields=["ENTITY_ID"],
        )
        self.assertFalse(result.success, result.to_dict())
        self.assertIn("layout_load_artifact_required", {item["code"] for item in result.metadata["issues"]})

    def test_unknown_preprocessor_branches_cannot_hide_static_ui_or_supply_grid_evidence(self):
        columns = [{"field_name": "ENTITY_ID", "caption": "Entity", "data_type": "string"}]
        _, designer = valid_devexpress_grid_designer(columns=columns)
        code_behind = '''
        public partial class RecordsBrowseForm : System.Windows.Forms.Form
        {
            public RecordsBrowseForm() { InitializeComponent(); }
            private void CallSelectProcedure() { this.grdList.DataSource = result; }
            #if DEBUG
            private void ConfigureDebugUi() { this.txtFilter = new DevExpress.XtraEditors.TextEdit(); }
            #endif
        }
        '''
        static_ui = _verify_migration_generated_csharp_style(
            code_behind,
            designer_source_text=designer,
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="RecordsBrowse",
        )
        zero_branch_static_ui = _verify_migration_generated_csharp_style(
            code_behind.replace("#if DEBUG", "#if 0"),
            designer_source_text=designer,
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="RecordsBrowse",
        )
        conditional_grid = _verify_migration_generated_csharp_style(
            code_behind.replace("#if DEBUG", "#if false"),
            designer_source_text="#if DEBUG\n" + designer + "\n#endif",
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="RecordsBrowse",
            expected_grid_role="list",
            expected_grid_columns=columns,
            result_fields=["ENTITY_ID"],
            layout_load_artifact_text=generate_devexpress_grid_xml(columns),
        )
        self.assertIn("designer_owned_ui_in_code_behind", {item["code"] for item in static_ui.metadata["issues"]})
        self.assertIn("designer_owned_ui_in_code_behind", {item["code"] for item in zero_branch_static_ui.metadata["issues"]})
        self.assertIn("construction", static_ui.metadata["designer_owned_ui_contract"]["detected_categories"])
        self.assertFalse(conditional_grid.success, conditional_grid.to_dict())
        self.assertIn(
            "grid_designer_unknown_conditional_compilation",
            {item["code"] for item in conditional_grid.metadata["issues"]},
        )

    def test_designer_accepts_normal_tahoma_font_variants_and_rejects_extra_scroll_flags(self):
        columns = [{"field_name": "ENTITY_ID", "caption": "Entity", "data_type": "string"}]
        _, designer = valid_devexpress_grid_designer(columns=columns)
        font_variant = designer.replace(
            'new System.Drawing.Font("Tahoma", 9F)',
            'new System.Drawing.Font("Tahoma", 9.0F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point)',
        )
        extra_scroll = font_variant.replace(
            "DevExpress.XtraGrid.Views.Grid.ScrollStyleFlags.LiveHorzScroll;",
            "DevExpress.XtraGrid.Views.Grid.ScrollStyleFlags.LiveHorzScroll | DevExpress.XtraGrid.Views.Grid.ScrollStyleFlags.None;",
            1,
        )
        duplicate_scroll = font_variant.replace(
            "DevExpress.XtraGrid.Views.Grid.ScrollStyleFlags.LiveHorzScroll;",
            "DevExpress.XtraGrid.Views.Grid.ScrollStyleFlags.LiveHorzScroll | DevExpress.XtraGrid.Views.Grid.ScrollStyleFlags.LiveHorzScroll;",
            1,
        )
        kwargs = {
            "profile_evidence": loaded_test_profile(csharp_required_patterns=[]),
            "program_key": "RecordsBrowse",
            "expected_grid_role": "list",
            "expected_grid_columns": columns,
            "result_fields": ["ENTITY_ID"],
            "layout_load_artifact_text": generate_devexpress_grid_xml(columns),
        }
        code_behind = "public partial class RecordsBrowseForm : System.Windows.Forms.Form { public RecordsBrowseForm() { InitializeComponent(); } private void CallSelectProcedure() { this.grdList.DataSource = result; } }"
        accepted = _verify_migration_generated_csharp_style(code_behind, designer_source_text=font_variant, **kwargs)
        rejected = _verify_migration_generated_csharp_style(code_behind, designer_source_text=extra_scroll, **kwargs)
        duplicate_rejected = _verify_migration_generated_csharp_style(code_behind, designer_source_text=duplicate_scroll, **kwargs)
        self.assertTrue(accepted.success, accepted.to_dict())
        self.assertFalse(rejected.success, rejected.to_dict())
        self.assertFalse(duplicate_rejected.success, duplicate_rejected.to_dict())
        self.assertIn("authoritative_gridview_default_mismatch", {item["code"] for item in rejected.metadata["issues"]})

    def test_csharp_tahoma_nine_font_accepts_only_equivalent_regular_point_overloads(self):
        accepted = [
            'new Font("Tahoma", 9F)',
            'new System.Drawing.Font("Tahoma", 9)',
            'new Font("Tahoma", 9.0f, FontStyle.Regular)',
            'new Font("Tahoma", 9.00F, GraphicsUnit.Point)',
            'new Font("Tahoma", 9F, FontStyle.Regular, GraphicsUnit.Point)',
            'new System.Drawing.Font("Tahoma", 9F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 1)',
            'new Font("Tahoma", 9F, FontStyle.Regular, GraphicsUnit.Point, (byte)1, false)',
        ]
        for value in accepted:
            with self.subTest(value=value):
                self.assertTrue(pb_migration._csharp_tahoma_nine_font(value))

    def test_csharp_tahoma_nine_font_rejects_non_regular_styles_units_and_flags(self):
        rejected = [
            'new Font("Tahoma", 9F, FontStyle.Bold)',
            'new Font("Tahoma", 9F, FontStyle.Italic)',
            'new Font("Tahoma", 9F, FontStyle.Underline)',
            'new Font("Tahoma", 9F, FontStyle.Strikeout)',
            'new Font("Tahoma", 9F, FontStyle.Regular | FontStyle.Bold)',
            'new Font("Tahoma", 9F, FontStyle.Bold | FontStyle.Italic)',
            'new Font("Tahoma", 9F, GraphicsUnit.Pixel)',
            'new Font("Tahoma", 9F, GraphicsUnit.Display)',
            'new Font("Tahoma", 9F, GraphicsUnit.Document)',
            'new Font("Tahoma", 9F, GraphicsUnit.Inch)',
            'new Font("Tahoma", 9F, GraphicsUnit.Millimeter)',
            'new Font("Tahoma", 9F, GraphicsUnit.World)',
            'new Font("Tahoma", 9F, FontStyle.Regular, GraphicsUnit.Point, 0)',
            'new Font("Tahoma", 9F, FontStyle.Regular, GraphicsUnit.Point, 2)',
            'new Font("Tahoma", 9F, FontStyle.Regular, GraphicsUnit.Point, 1, true)',
            'new Font("Ta homa", 9F)',
            'new Font("Tahoma", 9.1F)',
            'new Font("Tahoma", 9D)',
        ]
        for value in rejected:
            with self.subTest(value=value):
                self.assertFalse(pb_migration._csharp_tahoma_nine_font(value))

    def test_master_detail_contracts_validate_targets_independently_and_together(self):
        list_columns = [{"field_name": "MASTER_ID", "caption": "Master", "data_type": "string"}]
        detail_columns = [{"field_name": "DETAIL_ID", "caption": "Detail", "data_type": "string"}]
        list_plan = build_csharp_grid_column_designer_plan(list_columns, input_format="list", result_fields=["MASTER_ID"])
        detail_plan = build_csharp_grid_column_designer_plan(detail_columns, input_format="detail", result_fields=["DETAIL_ID"])
        designer = f"partial class RecordsBrowseForm {{\n{list_plan.stdout}\n{detail_plan.stdout}\n}}"
        code_behind = "public partial class RecordsBrowseForm : System.Windows.Forms.Form { public RecordsBrowseForm() { InitializeComponent(); } private void CallSelectProcedure() { this.grdList.DataSource = result; } }"
        common = {
            "designer_source_text": designer,
            "profile_evidence": loaded_test_profile(csharp_required_patterns=[]),
            "program_key": "RecordsBrowse",
            "result_fields": ["MASTER_ID", "DETAIL_ID"],
        }
        targeted = _verify_migration_generated_csharp_style(
            code_behind,
            expected_grid_role="list",
            expected_grid_columns=list_columns,
            layout_load_artifact_text=generate_devexpress_grid_xml(list_columns),
            **common,
        )
        contracts = [
            {"id": "master", "role": "list", "columns": list_columns, "artifact_text": generate_devexpress_grid_xml(list_columns)},
            {"id": "detail", "role": "detail", "columns": detail_columns, "artifact_text": generate_devexpress_grid_xml(detail_columns, prefix="colDetail_")},
        ]
        together = _verify_migration_generated_csharp_style(
            code_behind,
            expected_grid_contracts=contracts,
            **common,
        )
        bad_detail = _verify_migration_generated_csharp_style(
            code_behind,
            designer_source_text=designer.replace("this.colDetail_DETAIL_ID.VisibleIndex = 1;", "this.colDetail_DETAIL_ID.VisibleIndex = 0;", 1),
            profile_evidence=common["profile_evidence"],
            program_key="RecordsBrowse",
            result_fields=common["result_fields"],
            expected_grid_contracts=contracts,
        )
        self.assertTrue(targeted.success, targeted.to_dict())
        self.assertTrue(together.success, together.to_dict())
        self.assertFalse(bad_detail.success, bad_detail.to_dict())
        detail_issues = [item for item in bad_detail.metadata["issues"] if item.get("grid_contract_id") == "detail"]
        self.assertTrue(detail_issues, bad_detail.to_dict())

    def test_designer_visible_index_is_required_one_based_and_ordered(self):
        columns = [
            {"field_name": "FIRST_ID", "caption": "First", "data_type": "string"},
            {"field_name": "SECOND_ID", "caption": "Second", "data_type": "string"},
        ]
        _, designer = valid_devexpress_grid_designer(columns=columns)
        code_behind = '''
        public partial class RecordsBrowseForm : System.Windows.Forms.Form
        {
            public RecordsBrowseForm() { InitializeComponent(); }
            protected void SearchCommand() { CallSelectProcedure(); }
            private void CallSelectProcedure() { this.grdList.DataSource = result; }
        }
        '''
        mutations = {
            "missing": designer.replace("this.colList_FIRST_ID.VisibleIndex = 1;", "", 1),
            "zero_based": designer.replace("this.colList_FIRST_ID.VisibleIndex = 1;", "this.colList_FIRST_ID.VisibleIndex = 0;", 1),
            "reordered_indices": designer.replace("this.colList_FIRST_ID.VisibleIndex = 1;", "this.colList_FIRST_ID.VisibleIndex = 2;", 1).replace("this.colList_SECOND_ID.VisibleIndex = 2;", "this.colList_SECOND_ID.VisibleIndex = 1;", 1),
            "reordered_addrange": designer.replace(
                "    this.colList_FIRST_ID,\n    this.colList_SECOND_ID",
                "    this.colList_SECOND_ID,\n    this.colList_FIRST_ID",
                1,
            ),
        }
        for case, candidate in mutations.items():
            with self.subTest(case=case):
                result = _verify_migration_generated_csharp_style(
                    code_behind,
                    designer_source_text=candidate,
                    profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
                    program_key="RecordsBrowse",
                    expected_grid_role="list",
                    expected_grid_columns=columns,
                    result_fields=["FIRST_ID", "SECOND_ID"],
                )
                self.assertFalse(result.success, result.to_dict())

    def test_numeric_designer_verification_uses_declared_type_not_field_tokens(self):
        columns = [
            {"field_name": "TOTAL_TEXT", "caption": "Total text", "data_type": "string"},
            {"field_name": "QUANTITY", "caption": "Quantity", "data_type": "decimal(18, 3)"},
        ]
        _, designer = valid_devexpress_grid_designer(columns=columns)
        code_behind = '''
        public partial class RecordsBrowseForm : System.Windows.Forms.Form
        {
            public RecordsBrowseForm() { InitializeComponent(); }
            protected void SearchCommand() { CallSelectProcedure(); }
            private void CallSelectProcedure() { this.grdList.DataSource = result; }
        }
        '''
        missing_spin = designer.replace("this.colList_QUANTITY.ColumnEdit = this.rpsSpinAmt;", "", 1)
        display_only = designer.replace(
            "this.colList_QUANTITY.ColumnEdit = this.rpsSpinAmt;",
            'this.colList_QUANTITY.DisplayFormat.FormatString = "#,##0.000";',
            1,
        )
        for candidate in (missing_spin, display_only):
            result = _verify_migration_generated_csharp_style(
                code_behind,
                designer_source_text=candidate,
                profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
                program_key="RecordsBrowse",
                expected_grid_role="list",
                expected_grid_columns=columns,
                result_fields=["TOTAL_TEXT", "QUANTITY"],
            )
            self.assertFalse(result.success, result.to_dict())
            numeric_issues = [item for item in result.metadata["issues"] if item["code"].startswith("numeric_grid")]
            self.assertTrue(any("QUANTITY" in item.get("column", item.get("message", "")) for item in numeric_issues))
            self.assertFalse(any("TOTAL_TEXT" in item.get("column", item.get("message", "")) for item in numeric_issues))

    def test_paired_designer_accepts_valid_list_detail_and_table_purpose_roles(self):
        cases = [
            ("list", "", "", "List", "ENTITY_ID"),
            ("detail", "", "", "Detail", "LINE_ID"),
            ("table", "ORDER", "", "ORDER", "ORDER_ID"),
            ("purpose", "", "LEDGER", "LEDGER", "ENTRY_ID"),
        ]
        for role, table_name, purpose_name, suffix, field_name in cases:
            with self.subTest(role=role):
                columns = [{"field_name": field_name, "caption": f"{field_name} caption", "data_type": "string"}]
                plan, designer = valid_devexpress_grid_designer(
                    columns=columns,
                    input_format=role,
                    table_name=table_name,
                    purpose_name=purpose_name,
                )
                code_behind = f'''
                public partial class RecordsBrowseForm : System.Windows.Forms.Form
                {{
                    public RecordsBrowseForm() {{ InitializeComponent(); }}
                    protected void SearchCommand() {{ CallSelectProcedure(); }}
                    private void CallSelectProcedure() {{ this.grd{suffix}.DataSource = result; }}
                }}
                '''
                result = _verify_migration_generated_csharp_style(
                    code_behind,
                    designer_source_text=designer,
                    profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
                    program_key="RecordsBrowse",
                    expected_grid_role=role,
                    expected_grid_suffix=suffix if role in {"table", "purpose"} else "",
                    expected_grid_columns=columns,
                    result_fields=[field_name],
                    layout_load_artifact_text=generate_devexpress_grid_xml(
                        columns,
                        prefix=plan.metadata["csharp_column_prefix"],
                    ),
                )
                self.assertTrue(plan.success, plan.to_dict())
                self.assertTrue(result.success, result.to_dict())
                self.assertEqual(result.metadata["grid_designer_contract"]["grid_control_name"], f"grd{suffix}")
                self.assertEqual(result.metadata["grid_designer_contract"]["grid_view_name"], f"gvw{suffix}")

    def test_paired_designer_rejects_wrong_names_numeric_displayformat_appearance_and_wiring(self):
        columns = [{"field_name": "PRICE", "caption": "Unit price", "data_type": "decimal(18, 2)"}]
        _, valid_designer = valid_devexpress_grid_designer(columns=columns)
        code_behind = '''
        public partial class RecordsBrowseForm : System.Windows.Forms.Form
        {
            public RecordsBrowseForm() { InitializeComponent(); }
            protected void SearchCommand() { CallSelectProcedure(); }
            private void CallSelectProcedure() { this.grdList.DataSource = result; }
        }
        '''
        mutations = {
            "wrong_names": valid_designer.replace("grdList", "grdWrong").replace("gvwList", "gvwWrong").replace("colList_PRICE", "colArbitrary_PRICE"),
            "displayformat_only": valid_designer.replace(
                "this.colList_PRICE.ColumnEdit = this.rpsSpinAmt;",
                'this.colList_PRICE.DisplayFormat.FormatString = "{0:#,##0.00}";',
            ),
            "missing_appearance": valid_designer.replace(
                "this.colList_PRICE.AppearanceHeader.Options.UseFont = true;",
                "",
                1,
            ),
            "wrong_wiring": valid_designer.replace(
                "this.grdList.MainView = this.gvwList;",
                "this.grdList.MainView = this.gvwWrong;",
                1,
            ),
            "wrong_viewcollection": valid_designer.replace(
                "    this.gvwList\n});\nthis.gvwList.GridControl",
                "    this.gvwWrong\n});\nthis.gvwList.GridControl",
                1,
            ),
        }
        expected_codes = {
            "wrong_names": {
                "grid_designer_member_or_initializer_missing",
                "grid_column_member_or_initializer_missing",
            },
            "displayformat_only": {"numeric_grid_column_missing_spin_repository", "numeric_grid_column_displayformat_detected"},
            "missing_appearance": {"authoritative_grid_column_default_missing"},
            "wrong_wiring": {"grid_designer_wiring_identity_mismatch"},
            "wrong_viewcollection": {"grid_designer_wiring_identity_mismatch"},
        }
        for case, designer in mutations.items():
            with self.subTest(case=case):
                result = _verify_migration_generated_csharp_style(
                    code_behind,
                    designer_source_text=designer,
                    profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
                    program_key="RecordsBrowse",
                    expected_grid_role="list",
                    expected_grid_columns=columns,
                    result_fields=["PRICE"],
                )
                issue_codes = {item["code"] for item in result.metadata["issues"]}
                self.assertFalse(result.success, result.to_dict())
                self.assertTrue(expected_codes[case].intersection(issue_codes), issue_codes)

    def test_paired_designer_missing_each_authoritative_loaded_default_fails(self):
        columns = [{"field_name": "PRICE", "caption": "Unit price", "data_type": "decimal(18, 2)"}]
        plan, valid_designer = valid_devexpress_grid_designer(columns=columns)
        code_behind = '''
        public partial class RecordsBrowseForm : System.Windows.Forms.Form
        {
            public RecordsBrowseForm() { InitializeComponent(); }
            protected void SearchCommand() { CallSelectProcedure(); }
            private void CallSelectProcedure() { this.grdList.DataSource = result; }
        }
        '''
        authoritative_lines = list(plan.metadata["view_defaults"]) + [
            "this.colList_PRICE.AppearanceHeader.Options.UseTextOptions = true;",
            "this.colList_PRICE.AppearanceHeader.Options.UseFont = true;",
            "this.colList_PRICE.AppearanceHeader.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Center;",
            "this.colList_PRICE.AppearanceHeader.TextOptions.VAlignment = DevExpress.Utils.VertAlignment.Center;",
            'this.colList_PRICE.AppearanceHeader.Font = new System.Drawing.Font("Tahoma", 9F);',
            "this.colList_PRICE.AppearanceCell.Options.UseFont = true;",
            'this.colList_PRICE.AppearanceCell.Font = new System.Drawing.Font("Tahoma", 9F);',
            "this.colList_PRICE.Visible = true;",
        ]
        for line in authoritative_lines:
            with self.subTest(line=line):
                result = _verify_migration_generated_csharp_style(
                    code_behind,
                    designer_source_text=valid_designer.replace(line, "", 1),
                    profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
                    program_key="RecordsBrowse",
                    expected_grid_role="list",
                    expected_grid_columns=columns,
                    result_fields=["PRICE"],
                )
                self.assertFalse(result.success, result.to_dict())
                self.assertTrue(
                    {"authoritative_gridview_default_missing", "authoritative_optionsview_default_missing", "authoritative_grid_column_default_missing"}.intersection(
                        {item["code"] for item in result.metadata["issues"]}
                    )
                )

    def test_layout_artifact_and_self_attested_load_cannot_replace_designer_defaults(self):
        columns = [{"field_name": "PRICE", "caption": "Unit price", "data_type": "decimal(18, 2)"}]
        plan, designer = valid_devexpress_grid_designer(columns=columns)
        for line in plan.metadata["view_defaults"]:
            designer = designer.replace(line, "", 1)
        for property_path in (
            "AppearanceHeader.Options.UseTextOptions",
            "AppearanceHeader.Options.UseFont",
            "AppearanceHeader.TextOptions.HAlignment",
            "AppearanceHeader.TextOptions.VAlignment",
            "AppearanceHeader.Font",
            "AppearanceCell.Options.UseFont",
            "AppearanceCell.Font",
        ):
            designer = "\n".join(line for line in designer.splitlines() if f"colList_PRICE.{property_path}" not in line)
        code_behind = '''
        public partial class RecordsBrowseForm : System.Windows.Forms.Form
        {
            public RecordsBrowseForm() { InitializeComponent(); }
            protected void SearchCommand() { CallSelectProcedure(); }
            private void CallSelectProcedure() { this.grdList.DataSource = result; }
        }
        '''
        with tempfile.TemporaryDirectory() as temp_dir:
            artifact_path = Path(temp_dir) / "grid-layout.xml"
            artifact_path.write_text(generate_devexpress_grid_xml(columns), encoding="utf-8")
            artifact_only = _verify_migration_generated_csharp_style(
                code_behind,
                designer_source_text=designer,
                profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
                program_key="RecordsBrowse",
                expected_grid_role="list",
                expected_grid_columns=columns,
                result_fields=["PRICE"],
                layout_load_artifact_path=str(artifact_path),
            )
            result = _verify_migration_generated_csharp_style(
                code_behind,
                designer_source_text=designer,
                profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
                program_key="RecordsBrowse",
                expected_grid_role="list",
                expected_grid_columns=columns,
                result_fields=["PRICE"],
                layout_load_artifact_path=str(artifact_path),
                layout_load_evidence=observed_layout_load_evidence(artifact_path),
            )
        self.assertFalse(artifact_only.success, artifact_only.to_dict())
        self.assertFalse(result.success, result.to_dict())
        self.assertTrue(result.metadata["grid_designer_contract"]["layout_load_artifact_verified"])
        self.assertFalse(result.metadata["grid_designer_contract"]["layout_load_evidence_verified"])
        self.assertEqual(
            result.metadata["grid_designer_contract"]["layout_load_evidence_status"],
            "caller_assertion_ignored",
        )
        self.assertFalse(result.metadata["grid_designer_contract"]["actual_live_layout_load_observed"])

    def test_paired_designer_rejects_reversed_input_tabindex_but_ignores_label(self):
        columns = [{"field_name": "ENTITY_ID", "caption": "Entity", "data_type": "string"}]
        _, designer = valid_devexpress_grid_designer(columns=columns)
        designer += '''
        private DevExpress.XtraEditors.TextEdit txtLEFT;
        private DevExpress.XtraEditors.TextEdit txtRIGHT;
        private DevExpress.XtraEditors.LabelControl lblIGNORED;
        this.txtLEFT = new DevExpress.XtraEditors.TextEdit();
        this.txtRIGHT = new DevExpress.XtraEditors.TextEdit();
        this.lblIGNORED = new DevExpress.XtraEditors.LabelControl();
        this.txtLEFT.Location = new System.Drawing.Point(10, 10);
        this.txtRIGHT.Location = new System.Drawing.Point(110, 10);
        this.lblIGNORED.Location = new System.Drawing.Point(5, 5);
        this.txtLEFT.TabIndex = 2;
        this.txtRIGHT.TabIndex = 1;
        this.lblIGNORED.TabIndex = 99;
        '''
        code_behind = '''
        public partial class RecordsBrowseForm : System.Windows.Forms.Form
        {
            public RecordsBrowseForm() { InitializeComponent(); }
            protected void SearchCommand() { CallSelectProcedure(); }
            private void CallSelectProcedure() { this.grdList.DataSource = result; }
        }
        '''
        result = _verify_migration_generated_csharp_style(
            code_behind,
            designer_source_text=designer,
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="RecordsBrowse",
            expected_grid_role="list",
            expected_grid_columns=columns,
            result_fields=["ENTITY_ID"],
        )
        issue_codes = {item["code"] for item in result.metadata["issues"]}
        self.assertFalse(result.success, result.to_dict())
        self.assertIn("input_tabindex_spatial_order_mismatch", issue_codes)
        self.assertNotIn("lblIGNORED", [item["name"] for item in result.metadata["input_tab_order_contract"]["inputs"]])

    def test_tabindex_requires_presence_and_contiguity_per_container_only(self):
        columns = [{"field_name": "ENTITY_ID", "caption": "Entity", "data_type": "string"}]
        _, base_designer = valid_devexpress_grid_designer(columns=columns)
        code_behind = '''
        public partial class RecordsBrowseForm : System.Windows.Forms.Form
        {
            public RecordsBrowseForm() { InitializeComponent(); }
            protected void SearchCommand() { CallSelectProcedure(); }
            private void CallSelectProcedure() { this.grdList.DataSource = result; }
        }
        '''

        def verify(extra):
            return _verify_migration_generated_csharp_style(
                code_behind,
                designer_source_text=base_designer + extra,
                profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
                program_key="RecordsBrowse",
                expected_grid_role="list",
                expected_grid_columns=columns,
                result_fields=["ENTITY_ID"],
                layout_load_artifact_text=generate_devexpress_grid_xml(columns),
            )

        missing = verify('''
        private DevExpress.XtraEditors.TextEdit txtONLY;
        this.txtONLY = new DevExpress.XtraEditors.TextEdit();
        this.txtONLY.Location = new System.Drawing.Point(10, 10);
        ''')
        noncontiguous = verify('''
        private DevExpress.XtraEditors.TextEdit txtLEFT;
        private DevExpress.XtraEditors.TextEdit txtRIGHT;
        this.txtLEFT = new DevExpress.XtraEditors.TextEdit();
        this.txtRIGHT = new DevExpress.XtraEditors.TextEdit();
        this.txtLEFT.Location = new System.Drawing.Point(10, 10);
        this.txtRIGHT.Location = new System.Drawing.Point(110, 10);
        this.txtLEFT.TabIndex = 10;
        this.txtRIGHT.TabIndex = 999;
        ''')
        separate = verify('''
        private DevExpress.XtraEditors.GroupControl grpLEFT;
        private DevExpress.XtraEditors.GroupControl grpRIGHT;
        private DevExpress.XtraEditors.TextEdit txtLEFT;
        private DevExpress.XtraEditors.TextEdit txtRIGHT;
        this.grpLEFT = new DevExpress.XtraEditors.GroupControl();
        this.grpRIGHT = new DevExpress.XtraEditors.GroupControl();
        this.txtLEFT = new DevExpress.XtraEditors.TextEdit();
        this.txtRIGHT = new DevExpress.XtraEditors.TextEdit();
        this.grpLEFT.Controls.Add(this.txtLEFT);
        this.grpRIGHT.Controls.Add(this.txtRIGHT);
        this.txtLEFT.Location = new System.Drawing.Point(110, 100);
        this.txtRIGHT.Location = new System.Drawing.Point(10, 10);
        this.txtLEFT.TabIndex = 5;
        this.txtRIGHT.TabIndex = 99;
        ''')
        self.assertIn("input_tabindex_missing_with_layout", {item["code"] for item in missing.metadata["issues"]})
        self.assertIn("input_tabindex_not_container_contiguous", {item["code"] for item in noncontiguous.metadata["issues"]})
        self.assertTrue(separate.success, separate.to_dict())
        self.assertFalse(separate.metadata["input_tab_order_contract"]["unrelated_containers_compared"])

    def test_sp_generation_contract_blocks_missing_sql_or_unbacked_full_sp(self):
        missing = verify_pb_migration_sp_generation_contract("")
        self.assertFalse(missing.success)
        self.assertIn("missing_sql_text", {issue["code"] for issue in missing.metadata["issues"]})

        unbacked = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DISPLAY_NAME
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
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DISPLAY_NAME
    END
END
""",
            source_evidence=True,
        )
        self.assertFalse(bool_flag.success)
        self.assertIn("unstructured_source_evidence_flag", {issue["code"] for issue in bool_flag.metadata["issues"]})

        no_header = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DISPLAY_NAME
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
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DISPLAY_NAME
    END
END
""",
            source_evidence={"kind": "pb_srd_sql", "path": "d_saoth_070_a_1.srd", "summary": "retrieve SQL"},
        )
        self.assertTrue(allowed.success, allowed.metadata["issues"])

        fake_existing_sp = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DISPLAY_NAME
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
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DISPLAY_NAME
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
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DISPLAY_NAME
    END
END
""",
            source_evidence={"kind": "existing_sp", "object": "sp_ZX123456_SELECT", "verified": True},
        )
        self.assertFalse(object_only_verified_sp.success)
        self.assertIn(
            "missing_pb_or_db_source_evidence_for_sp_generation",
            {issue["code"] for issue in object_only_verified_sp.metadata["issues"]},
        )

        excerpt_only_existing_sp = verify_pb_migration_sp_generation_contract(
            sp_metadata_header()
            + """
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DISPLAY_NAME
    END
END
""",
            source_evidence={
                "kind": "existing_sp",
                "object": "sp_ZX123456_SELECT",
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
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT 1 AS DISPLAY_NAME
    END
END
""",
            source_evidence={
                "kind": "existing_sp",
                "object": "sp_ZX123456_SELECT",
                "verified": True,
                "definition_hash": "954465F0F0D81341EF6527FC33A7B4CE916E4A86DAE4810E86A1301242609376",
            },
        )
        self.assertTrue(verified_existing_sp.success, verified_existing_sp.metadata["issues"])

        cte = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
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

        for label, predicate in [
            (
                "IN",
                """
              WHERE A.RECORD_ID IN (
                                  SELECT T.RECORD_ID
                                  FROM @TMP T
                                 )
""",
            ),
            (
                "EXISTS",
                """
              WHERE EXISTS (
                            SELECT 1
                            FROM @TMP T
                            WHERE T.RECORD_ID = A.RECORD_ID
                           )
""",
            ),
            (
                "SCALAR",
                """
              WHERE A.RECORD_SEQUENCE = (
                                SELECT MAX(T.RECORD_SEQUENCE)
                                FROM @TMP T
                               )
""",
            ),
        ]:
            with self.subTest(if_exists_where_subquery=label):
                if_exists_where_subquery = verify_pb_migration_sp_generation_contract(
                    sp_metadata_header()
                    + f"""
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SAVE]
      @WORKTYPE    VARCHAR(20) = NULL
    , @SCOPE_CODE      VARCHAR(2)  = NULL
AS
BEGIN
    IF EXISTS (
              SELECT 1
              FROM SYNTHETIC_RECORDS A
{predicate.rstrip()}
              )
    BEGIN
        RAISERROR('Already processed.', 16, 1);
        RETURN;
    END
END
""",
                    source_evidence={"kind": "pb_srd_sql", "path": "synthetic_detail.srd"},
                )
                self.assertFalse(if_exists_where_subquery.success)
                self.assertIn(
                    "if_exists_where_subquery_in_generated_sp",
                    {issue["code"] for issue in if_exists_where_subquery.metadata["issues"]},
                )

        if_exists_simple_where = verify_pb_migration_sp_generation_contract(
            sp_metadata_header()
            + """
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SAVE]
      @WORKTYPE    VARCHAR(20) = NULL
    , @SCOPE_CODE      VARCHAR(2)  = NULL
AS
BEGIN
    IF EXISTS (
              SELECT 1
              FROM SYNTHETIC_RECORDS A
              WHERE A.RECORD_ID = @SCOPE_CODE
              )
    BEGIN
        RAISERROR('Already processed.', 16, 1);
        RETURN;
    END
END
""",
            source_evidence={"kind": "pb_srd_sql", "path": "synthetic_detail.srd"},
        )
        self.assertNotIn(
            "if_exists_where_subquery_in_generated_sp",
            {issue["code"] for issue in if_exists_simple_where.metadata["issues"]},
        )

        schema_fallback = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT TOP 0
           CAST('' AS VARCHAR(20)) AS RECORD_ID
         , CAST(0 AS DECIMAL(18, 4)) AS QTY;
END
""",
            source_evidence={"kind": "pb_srd_sql", "path": "synthetic_detail.srd"},
        )
        self.assertFalse(schema_fallback.success)
        self.assertIn(
            "schema_only_select_top_0_fallback_in_generated_sp",
            {issue["code"] for issue in schema_fallback.metadata["issues"]},
        )

        schema_fallback_convert = verify_pb_migration_sp_generation_contract(
            """
CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT TOP (0)
           CONVERT(VARCHAR(20), '') AS RECORD_ID
         , TRY_CONVERT(DECIMAL(18, 4), 0) AS QTY;
END
""",
            source_evidence={"kind": "pb_srd_sql", "path": "synthetic_detail.srd"},
        )
        self.assertFalse(schema_fallback_convert.success)
        self.assertIn(
            "schema_only_select_top_0_fallback_in_generated_sp",
            {issue["code"] for issue in schema_fallback_convert.metadata["issues"]},
        )

    def test_sp_generation_contract_blocks_generated_parameter_defaults_and_normalization(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20) = ''
    , @SCOPE_CODE   VARCHAR(2)  = ''
    , @ENTITY_CODE   VARCHAR(20) = '%'
    , @MODE_CODE    VARCHAR(1)  = 'T'
    , @OPTION_CODE       VARCHAR(1)  = '1'
    , @RECORD_CODE   VARCHAR(30) = '%'
AS
BEGIN
    SET NOCOUNT ON;

    SET @WORKTYPE = ISNULL(@WORKTYPE, '');
    SET @ENTITY_CODE = (CASE WHEN ISNULL(@ENTITY_CODE, '') = '' THEN '%' ELSE @ENTITY_CODE END);
    SELECT @RECORD_CODE = COALESCE(@RECORD_CODE, '%');
    SET @MODE_CODE = NULLIF(@MODE_CODE, '');
    IF ISNULL(@OPTION_CODE, '') = ''
        SET @OPTION_CODE = '1';
    SET @ENTITY_CODE = LTRIM(RTRIM(@ENTITY_CODE));

    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT A.DISPLAY_NAME
        FROM ZX902T A;
    END
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "existing_sp", "object": "sp_ZX123456_SELECT", "verified": True},
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
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @SCOPE_CODE   VARCHAR(2)
    , @INPUT_DATE  VARCHAR(8)
    , @DERIVED_YEAR     VARCHAR(4)
    , @DERIVED_MONTH       VARCHAR(2)
    , @BASE_YEAR  VARCHAR(4)
    , @BOUNDARY_DATE   VARCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;

    IF ISNULL(@INPUT_DATE, '') <> ''
    BEGIN
        SET @DERIVED_YEAR = LEFT(@INPUT_DATE, 4);
        SET @DERIVED_MONTH = SUBSTRING(@INPUT_DATE, 5, 2);
    END;

    IF ISNULL(@DERIVED_YEAR, '') = ''
        SET @DERIVED_YEAR = CONVERT(VARCHAR(4), YEAR(GETDATE()));

    IF ISNULL(@DERIVED_MONTH, '') = ''
        SET @DERIVED_MONTH = RIGHT('0' + CONVERT(VARCHAR(2), MONTH(GETDATE())), 2);

    IF ISNULL(@BASE_YEAR, '') = ''
        SET @BASE_YEAR = CONVERT(VARCHAR(4), YEAR(GETDATE()));

    IF ISNULL(@BOUNDARY_DATE, '') = ''
    BEGIN
        SET @BOUNDARY_DATE = CONVERT(VARCHAR(8), DATEADD(DAY, -DAY(GETDATE()), GETDATE()), 112);

        IF @DERIVED_YEAR <> LEFT(@BOUNDARY_DATE, 4)
            SET @BOUNDARY_DATE = CONVERT(VARCHAR(4), CONVERT(INT, @DERIVED_YEAR) - 1) + '1231';
    END;

    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT A.DISPLAY_NAME
        FROM ZX902T A;
    END
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "pb_srd_sql", "path": "d_zx123456.srd", "summary": "retrieve SQL"},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("derived_date_helper_parameter_detected", issue_codes)
        self.assertIn("if_isnull_date_derivation_block_detected", issue_codes)
        self.assertIn("generated_if_wrapped_date_set_block_detected", issue_codes)

    def test_sp_generation_contract_allows_local_declared_date_helpers_without_if_defaults(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @SCOPE_CODE   VARCHAR(2)
    , @INPUT_DATE  VARCHAR(8)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @DERIVED_YEAR    VARCHAR(4)
          , @DERIVED_MONTH      VARCHAR(2)
          , @BASE_YEAR VARCHAR(4)
          , @BOUNDARY_DATE  VARCHAR(8);

    SET @DERIVED_YEAR = LEFT(@INPUT_DATE, 4);
    SET @DERIVED_MONTH = SUBSTRING(@INPUT_DATE, 5, 2);
    SET @BASE_YEAR = CONVERT(VARCHAR(4), YEAR(GETDATE()));
    SET @BOUNDARY_DATE = CONVERT(VARCHAR(8), DATEADD(DAY, -DAY(GETDATE()), GETDATE()), 112);

    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT A.DISPLAY_NAME
        FROM ZX902T A;
    END
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "pb_srd_sql", "path": "d_zx123456.srd", "summary": "retrieve SQL"},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertNotIn("derived_date_helper_parameter_detected", issue_codes)
        self.assertNotIn("if_isnull_date_derivation_block_detected", issue_codes)
        self.assertNotIn("generated_if_wrapped_date_set_block_detected", issue_codes)

    def test_sp_generation_contract_blocks_alter_procedure_derived_helper_parameters(self):
        generated = sp_metadata_header() + """
ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @SCOPE_CODE   VARCHAR(2)
    , @INPUT_DATE  VARCHAR(8)
    , @DERIVED_YEAR     VARCHAR(4)
AS
BEGIN
    SELECT A.DISPLAY_NAME
    FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "pb_srd_sql", "path": "d_zx123456.srd", "summary": "retrieve SQL"},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("derived_date_helper_parameter_detected", issue_codes)

    def test_sp_generation_contract_blocks_parenthesized_date_isnull_defaults(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @SCOPE_CODE   VARCHAR(2)
    , @INPUT_DATE  VARCHAR(8)
AS
BEGIN
    DECLARE @DERIVED_YEAR VARCHAR(4);

    IF (ISNULL(@INPUT_DATE, '') = '')
        SET @DERIVED_YEAR = CONVERT(VARCHAR(4), YEAR(GETDATE()));

    SELECT A.DISPLAY_NAME
    FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "pb_srd_sql", "path": "d_zx123456.srd", "summary": "retrieve SQL"},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("if_isnull_date_derivation_block_detected", issue_codes)
        self.assertIn("generated_if_wrapped_date_set_block_detected", issue_codes)

    def test_sp_generation_contract_blocks_direct_if_wrapped_date_set(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @SCOPE_CODE   VARCHAR(2)
    , @INPUT_DATE  VARCHAR(8)
AS
BEGIN
    DECLARE @DERIVED_YEAR VARCHAR(4);

    IF @INPUT_DATE <> ''
        SET @DERIVED_YEAR = CONVERT(VARCHAR(4), @INPUT_DATE);

    SELECT A.DISPLAY_NAME
    FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence={"kind": "pb_srd_sql", "path": "d_zx123456.srd", "summary": "retrieve SQL"},
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("generated_if_wrapped_date_set_block_detected", issue_codes)

    def test_sp_generation_contract_blocks_non_caller_helper_parameters_when_csharp_params_known(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @SCOPE_CODE   VARCHAR(2)
    , @INPUT_DATE  VARCHAR(8)
    , @ROWCNT   INT
AS
BEGIN
    SELECT A.DISPLAY_NAME
    FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence=[
                {"kind": "pb_srd_sql", "path": "d_zx123456.srd", "summary": "retrieve SQL"},
                {
                    "kind": "csharp_call",
                    "path": "ZX123456.cs",
                    "db_parameters": ["@WORKTYPE", "@SCOPE_CODE", "@INPUT_DATE"],
                },
            ],
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("non_caller_procedure_parameter_detected", issue_codes)

    def test_sp_generation_contract_blocks_non_caller_parameters_with_broader_sql_types(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @SCOPE_CODE   VARCHAR(2)
    , @INPUT_DATE  VARCHAR(8)
    , @ROWNUM   INTEGER
    , @ROWGUID  UNIQUEIDENTIFIER
    , @FILEBIN  VARBINARY(MAX)
    , @RUNTIME  DATETIME2
AS
BEGIN
    SELECT A.DISPLAY_NAME
    FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence=[
                {"kind": "pb_srd_sql", "path": "d_zx123456.srd", "summary": "retrieve SQL"},
                {
                    "kind": "csharp_call",
                    "path": "ZX123456.cs",
                    "db_parameters": ["@WORKTYPE", "@SCOPE_CODE", "@INPUT_DATE"],
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
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @SCOPE_CODE   VARCHAR(2)
    , @INPUT_DATE  VARCHAR(8)
AS
BEGIN
    DECLARE @ROWCNT INT;

    SET @ROWCNT = 0;

    SELECT A.DISPLAY_NAME
    FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence=[
                {"kind": "pb_srd_sql", "path": "d_zx123456.srd", "summary": "retrieve SQL"},
                {
                    "kind": "csharp_call",
                    "path": "ZX123456.cs",
                    "db_parameters": ["@WORKTYPE", "@SCOPE_CODE", "@INPUT_DATE"],
                },
            ],
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertNotIn("non_caller_procedure_parameter_detected", issue_codes)

    def test_composed_sp_and_sql_formatting_verifier_requires_both_gates(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE    VARCHAR(20) = NULL
    , @SCOPE_CODE      VARCHAR(2)  = NULL
AS
BEGIN
    SELECT A.RECORD_ID
    FROM SYNTHETIC_RECORDS A
    WHERE A.SCOPE_CODE = @SCOPE_CODE;
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
