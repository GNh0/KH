import hashlib
import json
import re
import runpy
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from src.contracts import HarnessResult
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
    orchestrate_pb_migration_validation as _raw_orchestrate_pb_migration_validation,
    resolve_author_tagged_style_evidence,
    verify_migration_generated_csharp_style as _raw_verify_migration_generated_csharp_style,
    verify_pb_migration_analysis_document,
    verify_pb_migration_save_field_contract,
    verify_pb_migration_sp_generation_contract as _verify_pb_migration_sp_generation_contract,
    verify_pb_migration_sp_with_sql_formatting as _verify_pb_migration_sp_with_sql_formatting,
    resolve_csharp_grid_control_names,
    resolve_csharp_grid_column_prefix,
    resolve_csharp_control_stack,
)
from src.skills.sql_formatting_provider import (
    attach_sql_provider_selection_runtime_receipt,
    sql_provider_selection_sha256,
)
from src.skills.uaf_skill_catalog import read_packaged_skill


REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_PROVIDER_PATH = REPO_ROOT / "skills" / "sql_formatting" / "SKILL.md"


def sql_final_response(sql_text):
    return f"```sql\n{sql_text}\n```"


def sql_provider_selection(provider_path=SQL_PROVIDER_PATH, *, source="packaged-kh-skill"):
    resolved = str(Path(provider_path).resolve())
    return attach_sql_provider_selection_runtime_receipt({
        "schema_version": 1,
        "front_door_status": "ok",
        "host": "pb-test",
        "project": str(REPO_ROOT),
        "provider_id": "sql-formatting",
        "provider_path": resolved,
        "selected_active_provider_path": resolved,
        "provider_source": source,
        "compatibility": "compatible",
        "selection_status": "selected",
        "plugin_route": {
            "route": "single",
            "controller": {
                "provider_id": "sql-formatting",
                "capability": "sql_formatting",
                "metadata": {
                    "path": resolved,
                    "source": source,
                    "compatibility": "compatible",
                },
            },
            "assistants": [],
        },
        "execution_gate": {
            "can_execute": True,
            "status": "execution_allowed_after_selected_skill_setup",
            "reason": "SQL formatting provider selected after required skill setup.",
        },
    })


def sp_metadata_header(description="Synthetic procedure contract"):
    return f"""-- =============================================
-- DESCRIPTION: {description}
-- =============================================
    """


def write_test_artifact(name, text):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    root = Path(tempfile.gettempdir()) / "kh-uaf-pb-migration-tests"
    root.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", name)
    path = root / f"{safe_name}-{digest[:12]}.txt"
    path.write_text(text, encoding="utf-8", newline="")
    return path, digest


def target_artifact_kwargs(source_text, designer_text="", *, prefix="generated"):
    source_path, source_digest = write_test_artifact(f"{prefix}-source.cs", source_text)
    result = {
        "target_source_path": str(source_path),
        "target_source_sha256": f"sha256:{source_digest}",
    }
    if designer_text:
        designer_path, designer_digest = write_test_artifact(
            f"{prefix}-designer.cs",
            designer_text,
        )
        result.update(
            {
                "target_designer_path": str(designer_path),
                "target_designer_sha256": f"sha256:{designer_digest}",
            }
        )
    return result


def test_evidence_registry(*entries):
    default_entries = entries or (
        {
            "evidence_id": "user:no-generated-controls",
            "kind": "user",
            "locator": "user://test/no-generated-controls",
        },
    )
    return {item["evidence_id"]: dict(item) for item in default_entries}


def inferred_test_control_contracts(designer_text):
    declarations = {
        match.group("name"): match.group("type")
        for match in re.finditer(
            r"(?m)^\s*(?:public|protected|internal|private)\s+"
            r"(?P<type>(?:global::)?[A-Za-z_][A-Za-z0-9_.<>]*)\s+"
            r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;",
            designer_text,
        )
        if pb_migration._is_designer_control_type(match.group("type"))
    }
    contracts = []
    lexical_view = pb_migration._lex_csharp_non_code(designer_text)
    mappings, _ = pb_migration._extract_csharp_result_field_mappings(lexical_view)
    mappings_by_control = {}
    for mapping in mappings:
        mappings_by_control.setdefault(mapping["member"], {})[
            mapping["property"]
        ] = mapping["field_name"]
    for name, type_name in sorted(declarations.items()):
        contract = {"instance_name": name, "expected_type": type_name}
        if name in mappings_by_control:
            contract["bindings"] = dict(mappings_by_control[name])
        for property_name in ("BindingField", "FieldName", "DataPropertyName"):
            match = re.search(
                rf'this\.{re.escape(name)}\.{property_name}\s*=\s*"([^"\\]*)"\s*;',
                designer_text,
            )
            if match:
                contract.setdefault("bindings", {})[property_name] = match.group(1)
        contracts.append(contract)
    return contracts


def complete_csharp_caller_artifact(method_body, *, class_name="CallerEvidence"):
    return f'''public sealed class {class_name}
{{
    private object Execute()
    {{
{method_body}
    }}
}}'''


def csharp_call_evidence(
    parameters,
    *,
    artifact_name="ZX123456.cs",
    target_procedure="SP_ZX123456_SELECT",
    **extra,
):
    parameter_lines = "\n".join(
        f'    , new DbParameter("{parameter}", value)' for parameter in parameters
    )
    method_body = (
        f'return dbClient.GetDataSetFromSP("{target_procedure}"\n'
        f'{parameter_lines}\n'
        ');'
    )
    artifact_text = complete_csharp_caller_artifact(method_body)
    path, digest = write_test_artifact(artifact_name, artifact_text)
    return {
        "kind": "csharp_call",
        "verified": True,
        "path": str(path),
        "definition_text": artifact_text,
        "sha256": digest,
        "db_parameters": list(parameters),
        "target_procedure": target_procedure,
        **extra,
    }


def external_caller_evidence(
    parameter_contract,
    *,
    caller_id="batch-a",
    target_procedure="SP_ZX123456_SELECT",
):
    artifact_text = json.dumps(
        {
            "caller_id": caller_id,
            "target_procedure": target_procedure,
            "parameter_contract": parameter_contract,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    path, digest = write_test_artifact(f"external-{caller_id}", artifact_text)
    return {
        "kind": "external_caller",
        "verified": True,
        "caller_id": caller_id,
        "target_procedure": target_procedure,
        "path": str(path),
        "artifact_text": artifact_text,
        "sha256": digest,
        "parameter_contract": parameter_contract,
    }


def branch_contract_evidence(
    branch_sql,
    *,
    target_procedure="SP_ZX123456_SELECT",
    artifact_name="branch-contract",
):
    artifact_text = json.dumps(
        {
            "target_procedure": target_procedure,
            "branch_sql": str(branch_sql),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    path, digest = write_test_artifact(artifact_name, artifact_text)
    return {
        "kind": "branch_contract",
        "verified": True,
        "target_procedure": target_procedure,
        "path": str(path),
        "artifact_text": artifact_text,
        "sha256": digest,
        "branch_sql": str(branch_sql),
    }


def canonical_nonwrapper_trace_sha256(sql_text):
    trace_keys = [
        item["trace_key"]
        for item in pb_migration._sql_hierarchical_trace(sql_text)
        if not item["generated_wrapper"]
    ]
    payload = {
        "schema_version": "kh.pb.nonwrapper-trace.v2",
        "trace_keys": trace_keys,
    }
    canonical_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def composite_contract_evidence(
    trace_sql,
    source_lineage,
    *,
    target_procedure="SP_ZX123456_SELECT",
    artifact_name="composite-contract",
    trace_sha256=None,
):
    trace_sha256 = trace_sha256 or canonical_nonwrapper_trace_sha256(trace_sql)
    artifact_text = json.dumps(
        {
            "target_procedure": target_procedure,
            "trace_sql": str(trace_sql),
            "trace_sha256": trace_sha256,
            "source_lineage": list(source_lineage),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    path, digest = write_test_artifact(artifact_name, artifact_text)
    return {
        "kind": "composite_contract",
        "verified": True,
        "target_procedure": target_procedure,
        "path": str(path),
        "artifact_text": artifact_text,
        "sha256": digest,
        "trace_sql": str(trace_sql),
        "trace_sha256": trace_sha256,
        "source_lineage": list(source_lineage),
    }


def bound_source_evidence(kind, source_text, *, artifact_name="source-1", **extra):
    path, digest = write_test_artifact(artifact_name, source_text)
    return {
        "kind": kind,
        "verified": True,
        "definition_path": str(path),
        "definition_text": source_text,
        "sha256": digest,
        **extra,
    }


def pb_srd_sql_evidence(source_text="SELECT @WORKTYPE AS WORKTYPE;", **extra):
    return bound_source_evidence(
        "pb_srd_sql",
        source_text,
        artifact_name="synthetic-pb-query",
        **extra,
    )


def existing_sp_evidence(source_text, object_name="SP_ZX123456_SELECT", **extra):
    return bound_source_evidence(
        "existing_sp",
        source_text,
        artifact_name=f"existing-{object_name.lower()}",
        object=object_name,
        **extra,
    )


def pasted_sql_evidence(source_text, evidence_role="body_fragment", **extra):
    return bound_source_evidence(
        "pasted_sql",
        source_text,
        artifact_name=f"pasted-{evidence_role}",
        evidence_role=evidence_role,
        **extra,
    )


def approved_alias_role_plan():
    return {
        "scopes": [
            {
                "scope_id": "scope_1",
                "basis_references": [
                    {
                        "kind": "reviewer_approved_business_role",
                        "source": "review://PB-MIGRATION/main-and-detail-roles",
                        "reviewer_approved": True,
                        "role_names": ["main", "detail"],
                    }
                ],
                "roles": [
                    {
                        "name": "main",
                        "kind": "main",
                        "members": [
                            {"source": "SYNTHETIC_RECORDS", "original_alias": "A", "alias": "A"}
                        ],
                    },
                    {
                        "name": "detail",
                        "kind": "support",
                        "members": [
                            {"source": "SYNTHETIC_DETAILS", "original_alias": "B", "alias": "B"}
                        ],
                    },
                ],
            }
        ]
    }


def passed_sql_formatting_result(original_sql="", formatted_sql=""):
    original_sha256 = hashlib.sha256(str(original_sql).encode("utf-8")).hexdigest()
    formatted_sha256 = hashlib.sha256(str(formatted_sql).encode("utf-8")).hexdigest()
    return HarnessResult(
        success=True,
        stdout=json.dumps({"status": "passed"}, sort_keys=True),
        stderr="",
        exit_code=0,
        metadata={
            "mechanical_checks": {"status": "passed"},
            "alias_role_plan_validation": {"status": "verified"},
            "original_sha256": original_sha256,
            "formatted_sha256": formatted_sha256,
            "release_readiness": {"status": "ready"},
            "verification_id": "test-verification-id",
        },
    )


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
    return plan, designer_from_plans(form_class, plan)


def designer_from_plans(form_class, *plans):
    declarations = []
    bodies = []
    for plan in plans:
        declarations.extend(plan.metadata["declarations"])
        declaration_set = set(plan.metadata["declarations"])
        bodies.extend(
            line
            for line in plan.stdout.splitlines()
            if line.strip() not in declaration_set
            and line.strip() != "// GridColumn field declarations"
        )
    return (
        f"partial class {form_class}\n{{\n{chr(10).join(declarations)}\n"
        f"private void InitializeComponent()\n{{\n{chr(10).join(bodies)}\n}}\n}}"
    )


def extend_designer_initialize_component(designer, extra):
    declaration_lines = []
    body_lines = []
    for line in extra.splitlines():
        if re.match(r"\s*(?:public|protected|internal|private)\s+", line):
            declaration_lines.append(line.strip())
        elif line.strip():
            body_lines.append(line.strip())
    method_marker = "private void InitializeComponent()"
    extended = designer.replace(
        method_marker,
        "\n".join(declaration_lines + [method_marker]),
        1,
    )
    closing = extended.rfind("\n}\n}")
    if closing < 0:
        raise AssertionError("Designer fixture does not have an InitializeComponent closing scope.")
    return extended[:closing] + "\n" + "\n".join(body_lines) + extended[closing:]


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


def _prepare_csharp_verifier_kwargs(source, kwargs):
    prepared = dict(kwargs)
    designer = str(prepared.get("designer_source_text") or "")
    for key, value in target_artifact_kwargs(source, designer).items():
        prepared.setdefault(key, value)
    if "expected_control_contracts" not in prepared:
        contracts = inferred_test_control_contracts(
            designer if designer else (source if prepared.get("source_role") == "designer" else "")
        )
        prepared["expected_control_contracts"] = contracts
        if not contracts:
            prepared.setdefault(
                "no_control_contract_evidence",
                {
                    "reason": "The selected test Designer scope contains no generated controls.",
                    "evidence_refs": ["user:no-generated-controls"],
                },
            )
            prepared.setdefault("evidence_registry", test_evidence_registry())
    return prepared


def _verify_migration_generated_csharp_style(*args, **kwargs):
    source = str(args[0] if args else kwargs.pop("source_text", ""))
    prepared = _prepare_csharp_verifier_kwargs(source, kwargs)
    return _raw_verify_migration_generated_csharp_style(source, **prepared)


def _orchestrate_pb_migration_validation(*args, **kwargs):
    prepared = dict(kwargs)
    source = str(prepared.get("csharp_source_text") or "")
    designer = str(prepared.get("designer_source_text") or "")
    for key, value in target_artifact_kwargs(source, designer, prefix="orchestrated").items():
        prepared.setdefault(key, value)
    if "expected_control_contracts" not in prepared:
        contracts = inferred_test_control_contracts(designer)
        prepared["expected_control_contracts"] = contracts
        if not contracts:
            prepared.setdefault(
                "no_control_contract_evidence",
                {
                    "reason": "The selected test Designer scope contains no generated controls.",
                    "evidence_refs": ["user:no-generated-controls"],
                },
            )
            prepared.setdefault("evidence_registry", test_evidence_registry())
    return _raw_orchestrate_pb_migration_validation(*args, **prepared)


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
    formatted_sql = str(args[1] if len(args) > 1 else kwargs.get("formatted_sql_text") or "")
    kwargs.setdefault("draft_final_response", sql_final_response(formatted_sql))
    kwargs.setdefault("sql_provider_path", SQL_PROVIDER_PATH)
    kwargs.setdefault("selected_active_sql_provider_path", SQL_PROVIDER_PATH)
    kwargs.setdefault("sql_provider_selection", sql_provider_selection())
    return _verify_pb_migration_sp_with_sql_formatting(*args, **kwargs)


def orchestrate_pb_migration_validation(*args, **kwargs):
    kwargs.setdefault("caller_parameter_contract", ["@WORKTYPE"])
    formatted_sql = str(kwargs.get("formatted_sql_text") or "")
    kwargs.setdefault("draft_final_response", sql_final_response(formatted_sql))
    kwargs.setdefault("sql_provider_path", SQL_PROVIDER_PATH)
    kwargs.setdefault("selected_active_sql_provider_path", SQL_PROVIDER_PATH)
    kwargs.setdefault("sql_provider_selection", sql_provider_selection())
    return _orchestrate_pb_migration_validation(*args, **kwargs)


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

    def test_runtime_loader_accepts_schema_v2_without_konelib_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, payload, profile_hash = write_generalized_packaged_contract(
                temp_dir,
                mutate=lambda contract: contract.pop("konelib_defaults"),
            )
            with patch_runtime_profile_path(profile_path):
                loaded = load_packaged_migration_profile(
                    payload["contract_id"],
                    payload["contract_version"],
                    profile_hash,
                )

        self.assertTrue(loaded.success, loaded.to_dict())
        self.assertEqual(
            {},
            loaded.metadata["profile_rules"]["csharp"]["designer_contract"][
                "konelib_defaults"
            ],
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
        evidence = [
            pasted_sql_evidence(
                "SELECT @WORKTYPE AS WORKTYPE;",
                evidence_role="body_fragment",
            )
        ]
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
            ["load-profile", "validate-csharp", "validate-sp", "final-sql-binding"],
            passed.metadata["validation_contract"]["completed_stage_order"],
        )
        self.assertTrue(passed.metadata["validation_contract"]["completion_allowed"])
        self.assertFalse(passed.metadata["validation_contract"]["database_execution_attempted"])
        self.assertFalse(mismatched.success)
        self.assertEqual(["load-profile"], mismatched.metadata["validation_contract"]["completed_stage_order"])
        self.assertFalse(mismatched.metadata["validation_contract"]["profile_identity_match"])

    def test_orchestrated_validation_passes_alias_plan_to_sql_formatting_verifier(self):
        sql = sp_metadata_header("Generalized screen") + """
CREATE PROCEDURE DBO.SP_GENERALIZED_SELECT
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        alias_plan = approved_alias_role_plan()
        csharp, designer = valid_csharp_contract_sources()
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with (
                patch_runtime_profile_path(profile_path),
                mock.patch(
                    "src.skills.sql_formatting_provider.verify_sql_formatting_style",
                    return_value=passed_sql_formatting_result(sql, sql),
                ) as formatting,
            ):
                result = orchestrate_pb_migration_validation(
                    csharp_source_text=csharp,
                    designer_source_text=designer,
                    original_sql_text=sql,
                    formatted_sql_text=sql,
                    source_evidence=[
                        pasted_sql_evidence(
                            "SELECT @WORKTYPE AS WORKTYPE;",
                            evidence_role="body_fragment",
                        )
                    ],
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="InventoryBrowse",
                    result_fields=["ENTITY_ID"],
                    alias_role_plan=alias_plan,
                    sql_formatting_verifier_kwargs={"operation": "formatting"},
                )

        self.assertTrue(result.success, result.to_dict())
        formatting.assert_called_once()
        self.assertIs(formatting.call_args.kwargs["alias_role_plan"], alias_plan)
        self.assertEqual(formatting.call_args.kwargs["operation"], "formatting")
        self.assertEqual(formatting.call_args.kwargs["cte_temp_table_reason"], "")

    def test_orchestrated_validation_rejects_non_code_csharp_evidence_and_accepts_real_code(self):
        sql = sp_metadata_header("Generalized screen") + """
CREATE PROCEDURE DBO.SP_GENERALIZED_SELECT
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        evidence = [
            pasted_sql_evidence(
                "SELECT @WORKTYPE AS WORKTYPE;",
                evidence_role="body_fragment",
            )
        ]
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
        designer = designer_from_plans("RecordsBrowseForm", list_plan, detail_plan)
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
                    source_evidence=[
                        pasted_sql_evidence(
                            "SELECT 1 AS MASTER_ID;",
                            evidence_role="body_fragment",
                        ),
                        branch_contract_evidence(
                            "IF @WORKTYPE = 'LIST' BEGIN SELECT 1 AS MASTER_ID; END",
                            target_procedure="SP_GENERALIZED_SELECT",
                        ),
                    ],
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
                    source_evidence=[
                        pasted_sql_evidence(
                            "SELECT 1 AS MASTER_ID;",
                            evidence_role="body_fragment",
                        ),
                        branch_contract_evidence(
                            "IF @WORKTYPE = 'LIST' BEGIN SELECT 1 AS MASTER_ID; END",
                            target_procedure="SP_GENERALIZED_SELECT",
                        ),
                    ],
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

    def test_demo_cli_satisfies_fail_closed_csharp_artifact_contract(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "skills.pb_to_csharp_migration_harness.scripts.demo",
                    "--output-dir",
                    temp_dir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            evidence = json.loads(
                (Path(temp_dir) / "offline_generation_evidence.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(0, completed.returncode, completed.stderr)
        demo_payload = json.loads(completed.stdout)
        self.assertEqual("passed", demo_payload["success_case"]["status"])
        self.assertEqual(0, demo_payload["verification"]["exit_code"])
        runtime = evidence["runtime_validation"]
        self.assertEqual(
            {"source": "passed", "designer": "passed", "baseline_designer": "passed"},
            {
                role: binding["status"]
                for role, binding in runtime["target_artifact_binding"].items()
            },
        )
        self.assertEqual("passed", runtime["control_contracts"]["status"])
        self.assertEqual(5, len(runtime["control_contracts"]["contracts"]))
        self.assertEqual("passed", runtime["control_evidence_registry"]["status"])
        self.assertEqual("passed", runtime["baseline_designer_preservation"]["status"])
        self.assertIn(
            "designer_owned_ui_in_code_behind",
            runtime["misplaced_issue_codes"],
        )

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
        runtime_validation = evidence["runtime_validation"]
        self.assertEqual(
            {"source": "passed", "designer": "passed", "baseline_designer": "passed"},
            {
                role: binding["status"]
                for role, binding in runtime_validation["target_artifact_binding"].items()
            },
        )
        self.assertEqual("passed", runtime_validation["control_contracts"]["status"])
        self.assertEqual(5, len(runtime_validation["control_contracts"]["contracts"]))
        self.assertEqual(
            "passed",
            runtime_validation["control_evidence_registry"]["status"],
        )
        self.assertEqual(
            "passed",
            runtime_validation["baseline_designer_preservation"]["status"],
        )
        self.assertEqual([], evidence["runtime_validation"]["sp_issue_codes"])
        self.assertEqual(
            "bound",
            evidence["runtime_validation"]["sql_final_response_binding"]["status"],
        )
        self.assertEqual(
            "passed",
            evidence["runtime_validation"]["sql_final_response_release"]["status"],
        )
        self.assertEqual(
            evidence["runtime_validation"]["sql_final_response_binding"],
            evidence["runtime_validation"]["sql_final_response_release"]["binding"],
        )
        self.assertEqual(
            hashlib.sha256(sql_text.encode("utf-8")).hexdigest(),
            evidence["runtime_validation"]["sql_final_response_binding"][
                "formatted_sha256"
            ],
        )
        self.assertIn("@WORKTYPE", sql_text)
        self.assertRegex(sql_text, r"-- CREATE DATE: \d{4}-\d{2}-\d{2}")
        self.assertIn(
            "SP generation contract and final SQL response binding verified",
            sql_artifact["validation_evidence"],
        )
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
        designer = designer_from_plans("SpecialBrowseForm", plan)
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

    @staticmethod
    def _control_contract_designer(
        *,
        lookup_type="KoneLib.Controls.u_ButtonEdit",
        binding_field="LOOKUP_CODE",
        auto_height="false",
        horizontal_alignment="Far",
        even_row_back_color="",
    ):
        even_row_assignment = (
            f"this.gvwList.Appearance.EvenRow.BackColor = {even_row_back_color};"
            if even_row_back_color
            else ""
        )
        return f'''
        partial class TestBrowseForm
        {{
            private {lookup_type} btnLookup;
            private KoneLib.Controls.u_Label lblLookup;
            private ExampleView gvwList;

            private void InitializeComponent()
            {{
                this.btnLookup = new {lookup_type}();
                this.lblLookup = new KoneLib.Controls.u_Label();
                this.gvwList = new ExampleView();
                this.btnLookup.BindingField = "{binding_field}";
                this.btnLookup.Properties.AutoHeight = {auto_height};
                this.lblLookup.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.{horizontal_alignment};
                this.lblLookup.Appearance.TextOptions.VAlignment = DevExpress.Utils.VertAlignment.Center;
                {even_row_assignment}
            }}
        }}
        '''

    @staticmethod
    def _expected_control_contracts(*, include_exact_defaults=True):
        lookup = {
            "instance_name": "btnLookup",
            "expected_type": "KoneLib.Controls.u_ButtonEdit",
            "BindingField": "LOOKUP_CODE",
        }
        if include_exact_defaults:
            lookup["properties"] = {"Properties.AutoHeight": False}
        return [
            lookup,
            {"instance_name": "lblLookup", "expected_type": "u_Label"},
            {"instance_name": "gvwList", "expected_type": "ExampleView"},
        ]

    def _raw_control_verification(self, designer, **kwargs):
        source, _ = valid_csharp_contract_sources(form_class="TestBrowseForm")
        call_kwargs = {
            "designer_source_text": designer,
            "profile_evidence": loaded_test_profile(csharp_required_patterns=[]),
            "program_key": "TestBrowse",
            **target_artifact_kwargs(source, designer, prefix="raw-control"),
            **kwargs,
        }
        return _raw_verify_migration_generated_csharp_style(source, **call_kwargs)

    def test_current_profile_blocks_omitted_contract_for_unbound_konelib_control(self):
        designer = self._control_contract_designer().replace(
            'this.btnLookup.BindingField = "LOOKUP_CODE";',
            "",
        )

        result = self._raw_control_verification(designer)

        self.assertFalse(result.success)
        self.assertIn(
            "expected_control_contracts_required",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_explicit_no_control_evidence_cannot_hide_mapped_controls(self):
        result = self._raw_control_verification(
            self._control_contract_designer(),
            expected_control_contracts=[],
            no_control_contract_evidence={
                "reason": "The migration claims no generated controls.",
                "evidence_refs": ["user:no-controls"],
            },
            evidence_registry=test_evidence_registry(
                {
                    "evidence_id": "user:no-controls",
                    "kind": "user",
                    "locator": "user://directive/no-controls",
                }
            ),
        )

        self.assertFalse(result.success)
        self.assertIn(
            "empty_control_contract_conflicts_with_designer_controls",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_nonempty_control_contract_requires_complete_designer_inventory(self):
        designer = self._control_contract_designer().replace(
            "private KoneLib.Controls.u_Label lblLookup;",
            "private KoneLib.Controls.u_Label lblLookup;\n"
            "private KoneLib.Controls.u_TextEdit txtUnverified;",
        ).replace(
            "this.lblLookup = new KoneLib.Controls.u_Label();",
            "this.lblLookup = new KoneLib.Controls.u_Label();\n"
            "this.txtUnverified = new KoneLib.Controls.u_TextEdit();\n"
            'this.txtUnverified.BindingField = "WRONG_CODE";\n'
            "this.txtUnverified.Properties.AutoHeight = false;",
        )

        result = self._raw_control_verification(
            designer,
            expected_control_contracts=self._expected_control_contracts(),
        )

        self.assertFalse(result.success)
        missing = [
            issue
            for issue in result.metadata["issues"]
            if issue["code"] == "control_contract_inventory_incomplete"
        ]
        self.assertEqual(["txtUnverified"], missing[0]["missing_controls"])

    def test_complete_inventory_includes_custom_target_wrapper_without_name_heuristic(self):
        designer = self._control_contract_designer().replace(
            "private ExampleView gvwList;",
            "private ExampleView gvwList;\n"
            "private TargetProject.LegacyLookupWidget legacyLookup;",
        ).replace(
            "this.gvwList = new ExampleView();",
            "this.gvwList = new ExampleView();\n"
            "this.legacyLookup = new TargetProject.LegacyLookupWidget();",
        )

        result = self._raw_control_verification(
            designer,
            expected_control_contracts=self._expected_control_contracts(),
        )

        self.assertFalse(result.success)
        incomplete = [
            issue
            for issue in result.metadata["issues"]
            if issue["code"] == "control_contract_inventory_incomplete"
        ]
        self.assertEqual(["legacyLookup"], incomplete[0]["missing_controls"])

    def test_protected_override_rejects_unbound_evidence_reference(self):
        contracts = self._expected_control_contracts(include_exact_defaults=False)
        contracts[0]["properties"] = {"Properties.AutoHeight": True}
        contracts[0]["evidence_refs"] = ["invented"]

        result = self._raw_control_verification(
            self._control_contract_designer(auto_height="true"),
            expected_control_contracts=contracts,
            evidence_registry={},
        )

        self.assertFalse(result.success)
        self.assertIn(
            "control_contract_evidence_reference_unresolved",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_contract_level_evidence_reference_must_resolve_even_without_properties(self):
        contracts = self._expected_control_contracts()
        contracts[1]["evidence_refs"] = ["invented:label-authority"]

        result = self._raw_control_verification(
            self._control_contract_designer(),
            expected_control_contracts=contracts,
            evidence_registry={},
        )

        self.assertFalse(result.success)
        self.assertIn(
            "control_contract_evidence_reference_unresolved",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_property_evidence_cannot_authorize_an_undeclared_property(self):
        contracts = self._expected_control_contracts()
        contracts[1]["property_evidence"] = {
            "Appearance.TextOptions.HAlignment": ["user:label-authority"]
        }

        result = self._raw_control_verification(
            self._control_contract_designer(),
            expected_control_contracts=contracts,
            evidence_registry=test_evidence_registry(
                {
                    "evidence_id": "user:label-authority",
                    "kind": "user",
                    "locator": "user://directive/label-authority",
                }
            ),
        )

        self.assertFalse(result.success)
        self.assertIn(
            "control_contract_property_evidence_invalid",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_evidence_registry_rejects_non_mapping_entries(self):
        contracts = self._expected_control_contracts()
        contracts[1]["evidence_refs"] = ["user:label-authority"]

        result = self._raw_control_verification(
            self._control_contract_designer(),
            expected_control_contracts=contracts,
            evidence_registry=[
                {
                    "evidence_id": "user:label-authority",
                    "kind": "user",
                    "locator": "user://directive/label-authority",
                },
                "arbitrary-string",
            ],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "control_evidence_registry_entry_invalid",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_no_control_evidence_requires_reason_and_bound_registry_entry(self):
        designer = """
        partial class TestBrowseForm
        {
            private void InitializeComponent() { }
        }
        """
        unbound = self._raw_control_verification(
            designer,
            expected_control_contracts=[],
            no_control_contract_evidence={
                "reason": "No controls are generated.",
                "evidence_refs": ["source:unbound-label"],
            },
            evidence_registry={},
        )
        missing_reason = self._raw_control_verification(
            designer,
            expected_control_contracts=[],
            no_control_contract_evidence={
                "evidence_refs": ["user:no-controls"],
            },
            evidence_registry=test_evidence_registry(
                {
                    "evidence_id": "user:no-controls",
                    "kind": "user",
                    "locator": "user://directive/no-controls",
                }
            ),
        )

        self.assertFalse(unbound.success)
        self.assertFalse(missing_reason.success)
        self.assertIn(
            "no_control_evidence_reference_unresolved",
            {issue["code"] for issue in unbound.metadata["issues"]},
        )
        self.assertIn(
            "no_control_evidence_reason_required",
            {issue["code"] for issue in missing_reason.metadata["issues"]},
        )

    def test_target_artifact_binding_blocks_missing_and_mismatched_files(self):
        source, _ = valid_csharp_contract_sources(form_class="TestBrowseForm")
        designer = self._control_contract_designer()
        profile = loaded_test_profile(csharp_required_patterns=[])
        missing = _raw_verify_migration_generated_csharp_style(
            source,
            designer_source_text=designer,
            profile_evidence=profile,
            program_key="TestBrowse",
            expected_control_contracts=self._expected_control_contracts(),
        )
        artifact_args = target_artifact_kwargs(source, designer, prefix="wrong-sibling")
        wrong_path, wrong_digest = write_test_artifact(
            "wrong-sibling-designer.cs",
            designer.replace("LOOKUP_CODE", "OTHER_CODE"),
        )
        artifact_args["target_designer_path"] = str(wrong_path)
        artifact_args["target_designer_sha256"] = f"sha256:{wrong_digest}"
        mismatched = _raw_verify_migration_generated_csharp_style(
            source,
            designer_source_text=designer,
            profile_evidence=profile,
            program_key="TestBrowse",
            expected_control_contracts=self._expected_control_contracts(),
            **artifact_args,
        )

        self.assertFalse(missing.success)
        self.assertFalse(mismatched.success)
        self.assertIn(
            "target_source_artifact_required",
            {issue["code"] for issue in missing.metadata["issues"]},
        )
        self.assertIn(
            "target_designer_artifact_text_mismatch",
            {issue["code"] for issue in mismatched.metadata["issues"]},
        )

    def test_target_artifact_binding_rejects_source_designer_path_collision(self):
        source, _ = valid_csharp_contract_sources(form_class="TestBrowseForm")
        designer = self._control_contract_designer()
        artifact_args = target_artifact_kwargs(source, designer, prefix="path-collision")
        artifact_args["target_designer_path"] = artifact_args["target_source_path"]
        artifact_args["target_designer_sha256"] = artifact_args["target_source_sha256"]

        result = _raw_verify_migration_generated_csharp_style(
            source,
            designer_source_text=designer,
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="TestBrowse",
            expected_control_contracts=self._expected_control_contracts(),
            **artifact_args,
        )

        self.assertFalse(result.success)
        self.assertIn(
            "target_artifact_role_path_collision",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_designer_control_evidence_must_be_in_initialize_component(self):
        designer = self._control_contract_designer().replace(
            "private void InitializeComponent()",
            "private void ConfigureAtRuntime()",
        ).replace(
            "partial class TestBrowseForm\n        {",
            "partial class TestBrowseForm\n        {\n"
            "            private void InitializeComponent() { }",
        )

        result = self._raw_control_verification(
            designer,
            expected_control_contracts=self._expected_control_contracts(),
        )

        self.assertFalse(result.success)
        self.assertIn(
            "designer_static_evidence_outside_initialize_component",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_local_function_cannot_impersonate_initialize_component(self):
        designer = '''
        partial class TestBrowseForm
        {
            private KoneLib.Controls.u_ButtonEdit btnLookup;
            private KoneLib.Controls.u_Label lblLookup;
            private ExampleView gvwList;

            private void ConfigureAtRuntime()
            {
                void InitializeComponent()
                {
                    this.btnLookup = new KoneLib.Controls.u_ButtonEdit();
                    this.lblLookup = new KoneLib.Controls.u_Label();
                    this.gvwList = new ExampleView();
                    this.btnLookup.BindingField = "LOOKUP_CODE";
                    this.btnLookup.Properties.AutoHeight = false;
                    this.lblLookup.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Far;
                    this.lblLookup.Appearance.TextOptions.VAlignment = DevExpress.Utils.VertAlignment.Center;
                }
            }
        }
        '''

        result = self._raw_control_verification(
            designer,
            expected_control_contracts=self._expected_control_contracts(),
        )

        self.assertFalse(result.success)
        self.assertIn(
            "designer_initialize_component_missing",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_baseline_preservation_blocks_unexplained_existing_property_changes(self):
        baseline = self._control_contract_designer().replace(
            "this.btnLookup.Properties.AutoHeight = false;",
            "this.btnLookup.Properties.AutoHeight = false;\n"
            "this.btnLookup.Size = new System.Drawing.Size(120, 20);\n"
            "this.btnLookup.Visible = true;",
        )
        current = baseline.replace(
            "new System.Drawing.Size(120, 20)",
            "new System.Drawing.Size(180, 20)",
        )
        baseline_path, baseline_digest = write_test_artifact(
            "baseline-designer.cs",
            baseline,
        )

        result = self._raw_control_verification(
            current,
            expected_control_contracts=self._expected_control_contracts(),
            baseline_designer_path=str(baseline_path),
            baseline_designer_sha256=f"sha256:{baseline_digest}",
        )

        self.assertFalse(result.success)
        self.assertIn(
            "baseline_designer_property_changed_without_evidence",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_baseline_preservation_covers_layout_visibility_and_label_alignment(self):
        baseline = self._control_contract_designer().replace(
            "this.btnLookup.Properties.AutoHeight = false;",
            "this.btnLookup.Properties.AutoHeight = false;\n"
            "this.btnLookup.Size = new System.Drawing.Size(120, 20);\n"
            "this.btnLookup.Location = new System.Drawing.Point(10, 12);\n"
            "this.btnLookup.Margin = new System.Windows.Forms.Padding(3);\n"
            "this.btnLookup.MaximumSize = new System.Drawing.Size(65535, 23);\n"
            "this.btnLookup.Visible = true;",
        )
        changes = {
            "Size": (
                "this.btnLookup.Size = new System.Drawing.Size(120, 20);",
                "this.btnLookup.Size = new System.Drawing.Size(180, 20);",
            ),
            "Location": (
                "this.btnLookup.Location = new System.Drawing.Point(10, 12);",
                "this.btnLookup.Location = new System.Drawing.Point(30, 12);",
            ),
            "Margin": (
                "this.btnLookup.Margin = new System.Windows.Forms.Padding(3);",
                "this.btnLookup.Margin = new System.Windows.Forms.Padding(6);",
            ),
            "MaximumSize": (
                "this.btnLookup.MaximumSize = new System.Drawing.Size(65535, 23);",
                "this.btnLookup.MaximumSize = new System.Drawing.Size(500, 23);",
            ),
            "Visible": (
                "this.btnLookup.Visible = true;",
                "this.btnLookup.Visible = false;",
            ),
            "Appearance.TextOptions.HAlignment": (
                "DevExpress.Utils.HorzAlignment.Far",
                "DevExpress.Utils.HorzAlignment.Near",
            ),
            "Appearance.TextOptions.VAlignment": (
                "DevExpress.Utils.VertAlignment.Center",
                "DevExpress.Utils.VertAlignment.Top",
            ),
        }
        baseline_path, baseline_digest = write_test_artifact(
            "baseline-all-preserved-properties.cs",
            baseline,
        )

        for property_path, (before, after) in changes.items():
            with self.subTest(property=property_path):
                result = self._raw_control_verification(
                    baseline.replace(before, after),
                    expected_control_contracts=self._expected_control_contracts(),
                    baseline_designer_path=str(baseline_path),
                    baseline_designer_sha256=f"sha256:{baseline_digest}",
                )
                matching = [
                    issue
                    for issue in result.metadata["issues"]
                    if issue["code"]
                    == "baseline_designer_property_changed_without_evidence"
                    and issue.get("property") == property_path
                ]

                self.assertFalse(result.success)
                self.assertEqual(1, len(matching), result.metadata["issues"])

    def test_baseline_preservation_allows_exact_registry_bound_change(self):
        baseline = self._control_contract_designer().replace(
            "this.btnLookup.Properties.AutoHeight = false;",
            "this.btnLookup.Properties.AutoHeight = false;\n"
            "this.btnLookup.Size = new System.Drawing.Size(120, 20);",
        )
        current = baseline.replace(
            "this.btnLookup.Size = new System.Drawing.Size(120, 20);",
            "this.btnLookup.Size = new System.Drawing.Size(180, 20);",
        )
        contracts = self._expected_control_contracts()
        contracts[0]["properties"]["Size"] = "new System.Drawing.Size(180, 20)"
        contracts[0]["property_evidence"] = {"Size": ["user:resize-approved"]}
        baseline_path, baseline_digest = write_test_artifact(
            "baseline-authorized-size.cs",
            baseline,
        )

        result = self._raw_control_verification(
            current,
            expected_control_contracts=contracts,
            evidence_registry=test_evidence_registry(
                {
                    "evidence_id": "user:resize-approved",
                    "kind": "user",
                    "locator": "user://directive/resize-approved",
                }
            ),
            baseline_designer_path=str(baseline_path),
            baseline_designer_sha256=f"sha256:{baseline_digest}",
        )

        self.assertTrue(result.success, result.metadata["issues"])
        changes = result.metadata["baseline_designer_preservation"]["changes"]
        self.assertEqual([True], [item["authorized"] for item in changes])

    def test_baseline_preservation_rejects_current_designer_as_its_own_baseline(self):
        designer = self._control_contract_designer()
        source, _ = valid_csharp_contract_sources(form_class="TestBrowseForm")
        artifact_args = target_artifact_kwargs(source, designer, prefix="baseline-collision")

        result = _raw_verify_migration_generated_csharp_style(
            source,
            designer_source_text=designer,
            profile_evidence=loaded_test_profile(csharp_required_patterns=[]),
            program_key="TestBrowse",
            expected_control_contracts=self._expected_control_contracts(),
            baseline_designer_path=artifact_args["target_designer_path"],
            baseline_designer_sha256=artifact_args["target_designer_sha256"],
            **artifact_args,
        )

        self.assertFalse(result.success)
        self.assertIn(
            "baseline_designer_target_path_collision",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_baseline_preservation_records_new_controls_as_not_evaluable(self):
        baseline = self._control_contract_designer()
        current = baseline.replace(
            "private ExampleView gvwList;",
            "private ExampleView gvwList;\nprivate KoneLib.Controls.u_TextEdit txtNew;",
        ).replace(
            "this.gvwList = new ExampleView();",
            "this.gvwList = new ExampleView();\n"
            "this.txtNew = new KoneLib.Controls.u_TextEdit();\n"
            "this.txtNew.Properties.AutoHeight = false;",
        )
        contracts = self._expected_control_contracts()
        contracts.append(
            {
                "instance_name": "txtNew",
                "expected_type": "KoneLib.Controls.u_TextEdit",
            }
        )
        baseline_path, baseline_digest = write_test_artifact(
            "baseline-new-control.cs",
            baseline,
        )

        result = self._raw_control_verification(
            current,
            expected_control_contracts=contracts,
            baseline_designer_path=str(baseline_path),
            baseline_designer_sha256=f"sha256:{baseline_digest}",
        )

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual(
            ["txtNew"],
            result.metadata["baseline_designer_preservation"][
                "new_controls_not_evaluable"
            ],
        )

    def test_generated_csharp_style_accepts_expected_control_contracts_and_konelib_defaults(self):
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(),
            expected_control_contracts=self._expected_control_contracts(),
        )

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual("passed", result.metadata["control_contracts"]["status"])
        self.assertEqual("passed", result.metadata["konelib_default_guards"]["status"])
        lookup = result.metadata["control_contracts"]["contracts"][0]
        self.assertEqual("passed", lookup["status"])
        self.assertEqual("LOOKUP_CODE", lookup["expected_binding_field"])
        self.assertEqual("LOOKUP_CODE", lookup["actual_binding_field"])
        self.assertEqual({"Properties.AutoHeight": False}, lookup["expected_properties"])
        self.assertEqual({"Properties.AutoHeight": "false"}, lookup["actual_properties"])
        self.assertEqual([], lookup["consumed_explicit_exceptions"])

    def test_generated_csharp_style_blocks_omitted_required_control_contracts(self):
        result = self._raw_control_verification(self._control_contract_designer())

        self.assertFalse(result.success)
        self.assertIn(
            "expected_control_contracts_required",
            {issue["code"] for issue in result.metadata["issues"]},
        )
        self.assertEqual("omitted", result.metadata["control_contracts"]["input_state"])

    def test_generated_csharp_style_requires_evidence_for_explicit_no_control_contract(self):
        blocked = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(),
            expected_control_contracts=[],
        )
        accepted = verify_migration_generated_csharp_style(
            "",
            designer_source_text="""
            partial class TestBrowseForm
            {
                private void InitializeComponent() { }
            }
            """,
            expected_control_contracts=[],
            no_control_contract_evidence={
                "reason": "The reviewed migration mapping declares no mapped controls.",
                "evidence_refs": ["user:no-mapped-controls"],
            },
            evidence_registry=test_evidence_registry(
                {
                    "evidence_id": "user:no-mapped-controls",
                    "kind": "user",
                    "locator": "user://directive/no-mapped-controls",
                }
            ),
        )

        self.assertFalse(blocked.success)
        self.assertIn(
            "empty_control_contract_requires_no_control_evidence",
            {issue["code"] for issue in blocked.metadata["issues"]},
        )
        self.assertTrue(accepted.success, accepted.metadata["issues"])
        self.assertEqual(
            "proven_no_mapped_controls",
            accepted.metadata["control_contracts"]["status"],
        )

    def test_orchestrated_validation_blocks_generated_designer_without_control_contract_or_rationale(self):
        csharp, _ = valid_csharp_contract_sources(form_class="TestBrowseForm")
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, profile_hash = write_packaged_profile(temp_dir)
            with patch_runtime_profile_path(profile_path):
                artifact_kwargs = target_artifact_kwargs(
                    csharp,
                    self._control_contract_designer(),
                    prefix="orchestrated-omitted",
                )
                result = _raw_orchestrate_pb_migration_validation(
                    csharp_source_text=csharp,
                    designer_source_text=self._control_contract_designer(),
                    original_sql_text="",
                    formatted_sql_text="",
                    profile_id="pb-csharp-offline-generalized",
                    profile_version="1.0",
                    profile_hash=profile_hash,
                    program_key="TestBrowse",
                    **artifact_kwargs,
                )

        self.assertFalse(result.success)
        self.assertEqual(
            ["load-profile", "validate-csharp"],
            result.metadata["validation_contract"]["completed_stage_order"],
        )
        self.assertIn(
            "expected_control_contracts_required",
            {
                issue["code"]
                for issue in result.metadata["evidence"]["csharp"]["issues"]
            },
        )

    def test_generated_csharp_style_blocks_lookup_control_text_type_mismatch(self):
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(
                lookup_type="KoneLib.Controls.u_TextEdit"
            ),
            expected_control_contracts=self._expected_control_contracts(),
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("control_contract_declaration_type_mismatch", issue_codes)
        self.assertIn("control_contract_initializer_type_mismatch", issue_codes)

    def test_generated_csharp_style_blocks_control_binding_field_mismatch(self):
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(binding_field="OTHER_CODE"),
            expected_control_contracts=self._expected_control_contracts(),
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("control_contract_binding_field_mismatch", issue_codes)

    def test_generated_csharp_style_blocks_exact_control_property_mismatch(self):
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(auto_height="true"),
            expected_control_contracts=self._expected_control_contracts(),
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("control_contract_property_mismatch", issue_codes)

    def test_generated_csharp_style_blocks_konelib_input_autoheight_true_override(self):
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(auto_height="true"),
            expected_control_contracts=self._expected_control_contracts(
                include_exact_defaults=False
            ),
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("konelib_input_autoheight_true_override", issue_codes)

    def test_generated_csharp_style_blocks_konelib_label_alignment_override(self):
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(
                horizontal_alignment="Near"
            ),
            expected_control_contracts=self._expected_control_contracts(
                include_exact_defaults=False
            ),
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("konelib_label_alignment_override", issue_codes)

    def test_generated_csharp_style_blocks_even_row_backcolor_override(self):
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(
                even_row_back_color="System.Drawing.Color.AliceBlue"
            ),
            expected_control_contracts=self._expected_control_contracts(
                include_exact_defaults=False
            ),
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("even_row_backcolor_override", issue_codes)

    def test_generated_csharp_style_rejects_self_authorizing_default_overrides(self):
        contracts = self._expected_control_contracts(include_exact_defaults=False)
        contracts[0]["properties"] = {"Properties.AutoHeight": True}
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(auto_height="true"),
            expected_control_contracts=contracts,
        )

        self.assertFalse(result.success)
        self.assertIn(
            "control_contract_override_provenance_missing",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_generated_csharp_style_allows_explicit_exact_default_overrides(self):
        contracts = self._expected_control_contracts(include_exact_defaults=False)
        contracts[0]["properties"] = {"Properties.AutoHeight": True}
        contracts[0]["evidence_refs"] = ["source:pb-auto-height"]
        contracts[1]["properties"] = {
            "Appearance.TextOptions.HAlignment": "DevExpress.Utils.HorzAlignment.Near"
        }
        contracts[1]["property_evidence"] = {
            "Appearance.TextOptions.HAlignment": ["user-approved:label-alignment"]
        }
        contracts[2]["properties"] = {
            "Appearance.EvenRow.BackColor": "System.Drawing.Color.AliceBlue"
        }
        contracts[2]["evidence_refs"] = ["source:designer-even-row-color"]
        registry = test_evidence_registry(
            {
                "evidence_id": "source:pb-auto-height",
                "kind": "source",
                "sha256": "sha256:" + "1" * 64,
            },
            {
                "evidence_id": "user-approved:label-alignment",
                "kind": "user",
                "locator": "user://directive/label-alignment",
            },
            {
                "evidence_id": "source:designer-even-row-color",
                "kind": "source",
                "sha256": "sha256:" + "2" * 64,
            },
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(
                auto_height="true",
                horizontal_alignment="Near",
                even_row_back_color="System.Drawing.Color.AliceBlue",
            ),
            expected_control_contracts=contracts,
            evidence_registry=registry,
        )

        self.assertTrue(result.success, result.metadata["issues"])
        controls = {
            item["control"]: item
            for item in result.metadata["control_contracts"]["contracts"]
        }
        self.assertEqual(
            ["Properties.AutoHeight"],
            [
                item["property"]
                for item in controls["btnLookup"]["consumed_explicit_exceptions"]
            ],
        )
        self.assertEqual(
            ["Appearance.TextOptions.HAlignment"],
            [
                item["property"]
                for item in controls["lblLookup"]["consumed_explicit_exceptions"]
            ],
        )
        self.assertEqual(
            ["Appearance.EvenRow.BackColor"],
            [
                item["property"]
                for item in controls["gvwList"]["consumed_explicit_exceptions"]
            ],
        )
        self.assertEqual(
            ["source:pb-auto-height"],
            controls["btnLookup"]["consumed_explicit_exceptions"][0][
                "provenance"
            ]["references"],
        )

    def test_generated_csharp_style_ignores_unrelated_same_named_controls_after_target_resolution(self):
        target = self._control_contract_designer()
        unrelated = self._control_contract_designer(
            lookup_type="KoneLib.Controls.u_TextEdit",
            binding_field="WRONG_CODE",
            auto_height="true",
        ).replace(
            "TestBrowseForm",
            "UnrelatedBrowseForm",
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=target + unrelated,
            expected_control_contracts=self._expected_control_contracts(),
            form_class="TestBrowseForm",
        )

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual(
            "KoneLib.Controls.u_ButtonEdit",
            result.metadata["control_contracts"]["contracts"][0]["declared_type"],
        )

    def test_generated_csharp_style_merges_partial_target_class_declarations(self):
        designer = self._control_contract_designer()
        designer = designer.replace(
            "private void InitializeComponent()",
            "}\npartial class TestBrowseForm\n{\nprivate void InitializeComponent()",
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=self._expected_control_contracts(),
            form_class="TestBrowseForm",
        )

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual(
            2,
            result.metadata["control_contracts"]["form_scope"][
                "partial_declaration_count"
            ],
        )

    def test_generated_csharp_style_blocks_repeated_guarded_property_assignments(self):
        designer = self._control_contract_designer().replace(
            "this.btnLookup.Properties.AutoHeight = false;",
            "this.btnLookup.Properties.AutoHeight = false;\n"
            "this.btnLookup.Properties.AutoHeight = true;",
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=self._expected_control_contracts(),
        )

        self.assertFalse(result.success)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}
        self.assertIn("control_contract_property_assignment_ambiguous", issue_codes)
        self.assertIn("konelib_guard_assignment_ambiguous", issue_codes)

    def test_generated_csharp_style_blocks_conditional_guarded_property_assignment(self):
        designer = self._control_contract_designer(auto_height="true").replace(
            "this.btnLookup.Properties.AutoHeight = true;",
            "if (allowAutoHeight)\n"
            "{\n"
            "    this.btnLookup.Properties.AutoHeight = true;\n"
            "}",
        )
        contracts = self._expected_control_contracts(include_exact_defaults=False)
        contracts[0]["properties"] = {"Properties.AutoHeight": True}
        contracts[0]["evidence_refs"] = ["source:conditional-auto-height"]
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=contracts,
        )

        self.assertFalse(result.success)
        self.assertIn(
            "konelib_guard_conditional_assignment",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_generated_csharp_style_blocks_nonliteral_guarded_property_assignment(self):
        designer = self._control_contract_designer(auto_height="ResolveAutoHeight()")
        contracts = self._expected_control_contracts(include_exact_defaults=False)
        contracts[0]["properties"] = {"Properties.AutoHeight": "ResolveAutoHeight()"}
        contracts[0]["evidence_refs"] = ["source:dynamic-auto-height"]
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=contracts,
        )

        self.assertFalse(result.success)
        self.assertIn(
            "konelib_guard_nonliteral_assignment",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_legacy_schema_v2_profile_does_not_enable_konelib_default_guards(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_path, payload, profile_hash = write_generalized_packaged_contract(
                temp_dir,
                mutate=lambda contract: contract.pop("konelib_defaults"),
            )
            with patch_runtime_profile_path(profile_path):
                profile = load_packaged_migration_profile(
                    payload["contract_id"],
                    payload["contract_version"],
                    profile_hash,
                )
                csharp, _ = valid_csharp_contract_sources(
                    form_class="TestBrowseForm"
                )
                contracts = self._expected_control_contracts(
                    include_exact_defaults=False
                )
                contracts[0]["properties"] = {"Properties.AutoHeight": True}
                result = _verify_migration_generated_csharp_style(
                    csharp,
                    designer_source_text=self._control_contract_designer(
                        auto_height="true"
                    ),
                    profile_evidence=profile,
                    program_key="TestBrowse",
                    expected_control_contracts=contracts,
                )

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual(
            "not_enabled",
            result.metadata["konelib_default_guards"]["status"],
        )

    def test_generated_csharp_style_blocks_multiline_konelib_autoheight_override(self):
        designer = self._control_contract_designer(
            auto_height="(\n                    true\n                )"
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=self._expected_control_contracts(
                include_exact_defaults=False
            ),
        )

        self.assertFalse(result.success)
        self.assertIn(
            "konelib_input_autoheight_true_override",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_generated_csharp_style_blocks_multiline_konelib_label_override(self):
        designer = self._control_contract_designer().replace(
            "= DevExpress.Utils.HorzAlignment.Far;",
            "= DevExpress.Utils.HorzAlignment.\n                    Near;",
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=self._expected_control_contracts(
                include_exact_defaults=False
            ),
        )

        self.assertFalse(result.success)
        self.assertIn(
            "konelib_label_alignment_override",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_generated_csharp_style_blocks_multiline_even_row_override(self):
        designer = self._control_contract_designer(
            even_row_back_color="System.Drawing.Color.\n                    AliceBlue"
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=self._expected_control_contracts(
                include_exact_defaults=False
            ),
        )

        self.assertFalse(result.success)
        self.assertIn(
            "even_row_backcolor_override",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_generated_csharp_style_blocks_missing_control_declaration(self):
        designer = self._control_contract_designer().replace(
            "private KoneLib.Controls.u_ButtonEdit btnLookup;",
            "",
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=self._expected_control_contracts(),
        )

        self.assertFalse(result.success)
        self.assertIn(
            "control_contract_declaration_missing",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_generated_csharp_style_blocks_missing_control_initializer(self):
        designer = self._control_contract_designer().replace(
            "this.btnLookup = new KoneLib.Controls.u_ButtonEdit();",
            "",
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=self._expected_control_contracts(),
        )

        self.assertFalse(result.success)
        self.assertIn(
            "control_contract_initializer_missing",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_generated_csharp_style_blocks_missing_control_binding(self):
        designer = self._control_contract_designer().replace(
            'this.btnLookup.BindingField = "LOOKUP_CODE";',
            "",
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=self._expected_control_contracts(),
        )

        self.assertFalse(result.success)
        self.assertIn(
            "control_contract_binding_field_missing",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_generated_csharp_style_blocks_missing_control_property(self):
        designer = self._control_contract_designer().replace(
            "this.btnLookup.Properties.AutoHeight = false;",
            "",
        )
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer,
            expected_control_contracts=self._expected_control_contracts(),
        )

        lookup = result.metadata["control_contracts"]["contracts"][0]
        self.assertFalse(result.success)
        self.assertIn(
            "control_contract_property_missing",
            {issue["code"] for issue in result.metadata["issues"]},
        )
        self.assertEqual("blocked", lookup["status"])
        self.assertEqual({"Properties.AutoHeight": None}, lookup["actual_properties"])

    def test_generated_csharp_style_blocks_invalid_control_contract(self):
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(),
            expected_control_contracts=[
                {"instance_name": "invalid-name", "expected_type": "u_ButtonEdit"}
            ],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "control_contract_invalid",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_generated_csharp_style_blocks_duplicate_control_contract(self):
        duplicate = self._expected_control_contracts()[0]
        result = verify_migration_generated_csharp_style(
            "",
            designer_source_text=self._control_contract_designer(),
            expected_control_contracts=[duplicate, dict(duplicate)],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "control_contract_duplicate_instance",
            {issue["code"] for issue in result.metadata["issues"]},
        )

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
        designer = designer_from_plans("RecordsBrowseForm", list_plan, detail_plan)
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
                designer_source_text=extend_designer_initialize_component(
                    base_designer,
                    extra,
                ),
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

    def test_save_field_contract_accepts_source_owned_minimal_projections(self):
        sql = """
DECLARE @DOC INT;
DECLARE @ROWS TABLE
(
      RECORD_ID   VARCHAR(20)
    , ROWSTATE    VARCHAR(1)
    , OUTINSPEC   VARCHAR(1)
);

INSERT INTO @ROWS (RECORD_ID, ROWSTATE, OUTINSPEC)
SELECT RECORD_ID, ROWSTATE, OUTINSPEC
FROM OPENXML(@DOC, '/ROOT/ROW', 2)
WITH
(
      RECORD_ID   VARCHAR(20)
    , ROWSTATE    VARCHAR(1)
    , OUTINSPEC   VARCHAR(1)
);

IF EXISTS (
          SELECT 1
          FROM @ROWS A
          WHERE A.OUTINSPEC IS NULL
             OR A.OUTINSPEC = ''
          )
BEGIN
    RAISERROR('Required value is missing.', 16, 1);
    RETURN;
END

INSERT INTO SYNTHETIC_TARGET
(
      RECORD_ID
    , OUTINSPEC
    , STATUSCD
    , REGDT
)
SELECT A.RECORD_ID
     , A.OUTINSPEC
     , 'A'
     , GETDATE()
FROM @ROWS A;

UPDATE A
SET A.OUTINSPEC = B.OUTINSPEC
  , A.MODDT = GETDATE()
FROM SYNTHETIC_TARGET A
    INNER JOIN @ROWS B
        ON A.RECORD_ID = B.RECORD_ID;
"""
        contract = {
            "target_table": "SYNTHETIC_TARGET",
            "screen_used_fields": ["OUTINSPEC"],
            "payload_fields": ["OUTINSPEC"],
            "technical_fields": ["RECORD_ID", "ROWSTATE"],
            "required_fields": ["OUTINSPEC"],
            "required_nonblank_fields": ["OUTINSPEC"],
            "pb_fixed_values": {"STATUSCD": "'A'"},
            "database_default_fields": ["CREATED_BY"],
            "server_derived_fields": ["REGDT", "MODDT"],
            "nullable_unused_fields": ["REMARK"],
            "insert_fields": ["RECORD_ID", "OUTINSPEC", "STATUSCD", "REGDT"],
            "update_fields": ["OUTINSPEC", "MODDT"],
            "evidence_registry": {"pb:save": {"kind": "pb_behavior"}},
            "evidence_refs": ["pb:save"],
        }

        result = verify_pb_migration_save_field_contract(sql, contract)

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual(
            result.metadata["actual_insert_fields"],
            ["OUTINSPEC", "RECORD_ID", "REGDT", "STATUSCD"],
        )
        self.assertEqual(result.metadata["actual_update_fields"], ["MODDT", "OUTINSPEC"])

    def test_save_field_contract_allows_null_only_guard_for_required_numeric_field(self):
        sql = """
IF EXISTS (
          SELECT 1
          FROM @ROWS A
          WHERE A.QTY IS NULL
          )
BEGIN
    RAISERROR('Required value is missing.', 16, 1);
    RETURN;
END

INSERT INTO SYNTHETIC_TARGET (RECORD_ID, QTY)
SELECT A.RECORD_ID, A.QTY
FROM OPENXML(@DOC, '/ROOT/ROW', 2)
WITH (RECORD_ID VARCHAR(20), QTY DECIMAL(18, 4)) A;
"""
        contract = {
            "target_table": "SYNTHETIC_TARGET",
            "screen_used_fields": ["QTY"],
            "payload_fields": ["QTY"],
            "technical_fields": ["RECORD_ID"],
            "required_fields": ["QTY"],
            "required_nonblank_fields": [],
            "pb_fixed_values": {},
            "database_default_fields": [],
            "server_derived_fields": [],
            "nullable_unused_fields": [],
            "insert_fields": ["RECORD_ID", "QTY"],
            "update_fields": [],
            "evidence_registry": {"pb:save": {"kind": "pb_behavior"}},
            "evidence_refs": ["pb:save"],
        }

        result = verify_pb_migration_save_field_contract(sql, contract)

        self.assertTrue(result.success, result.metadata["issues"])

    def test_save_field_contract_blocks_unused_columns_silent_defaults_and_missing_guard(self):
        sql = """
INSERT INTO SYNTHETIC_TARGET (RECORD_ID, OUTINSPEC, REMARK, STATUSCD)
SELECT A.RECORD_ID, ISNULL(A.OUTINSPEC, 'A'), A.REMARK, 'A'
FROM OPENXML(@DOC, '/ROOT/ROW', 2)
WITH (RECORD_ID VARCHAR(20), OUTINSPEC VARCHAR(1), REMARK VARCHAR(200)) A;
"""
        contract = {
            "target_table": "SYNTHETIC_TARGET",
            "screen_used_fields": ["OUTINSPEC"],
            "payload_fields": ["OUTINSPEC"],
            "technical_fields": ["RECORD_ID"],
            "required_fields": ["OUTINSPEC"],
            "required_nonblank_fields": ["OUTINSPEC"],
            "pb_fixed_values": {"STATUSCD": "'A'"},
            "database_default_fields": [],
            "server_derived_fields": [],
            "nullable_unused_fields": ["REMARK"],
            "insert_fields": ["RECORD_ID", "OUTINSPEC", "STATUSCD"],
            "update_fields": [],
            "evidence_registry": {"pb:save": {"kind": "pb_behavior"}},
            "evidence_refs": ["pb:save"],
        }

        result = verify_pb_migration_save_field_contract(sql, contract)
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("save_xml_field_inventory_mismatch", issue_codes)
        self.assertIn("save_insert_field_inventory_mismatch", issue_codes)
        self.assertIn("save_omitted_field_written", issue_codes)
        self.assertIn("save_nullable_unused_field_serialized", issue_codes)
        self.assertIn("save_field_silent_null_default_detected", issue_codes)
        self.assertIn("save_required_field_fail_fast_guard_missing", issue_codes)

    def test_xml_save_generation_requires_field_contract(self):
        sql = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SAVE]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    INSERT INTO SYNTHETIC_TARGET (RECORD_ID)
    SELECT A.RECORD_ID
    FROM OPENXML(@DOC, '/ROOT/ROW', 2)
    WITH (RECORD_ID VARCHAR(20)) A;
END
"""

        result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=False,
        )

        self.assertFalse(result.success)
        self.assertIn(
            "save_field_contract_missing",
            {issue["code"] for issue in result.metadata["issues"]},
        )
        self.assertEqual(result.metadata["save_field_contract"]["status"], "missing")

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
            source_evidence=[
                pb_srd_sql_evidence(),
                csharp_call_evidence(["@WORKTYPE"]),
            ],
        )
        self.assertFalse(no_header.success)
        self.assertIn("missing_sp_metadata_header", {issue["code"] for issue in no_header.metadata["issues"]})

        existing_de_source = sp_metadata_header("Existing source") + """CREATE OR ALTER PROCEDURE [dbo].[sp_DE000600_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT 1 AS DWGNO;
END
"""
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
            source_evidence=[
                existing_sp_evidence(
                    existing_de_source,
                    "sp_DE000600_SELECT",
                    program_description="설계조회",
                ),
                branch_contract_evidence(
                    "IF @WORKTYPE = 'LIST' BEGIN SELECT 1 AS DWGNO; END",
                    target_procedure="sp_DE000600_SELECT",
                ),
            ],
            caller_parameter_contract=["@WORKTYPE"],
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
            source_evidence=[
                existing_sp_evidence(
                    existing_de_source,
                    "sp_DE000600_SELECT",
                    program_description="설계조회",
                ),
                branch_contract_evidence(
                    "IF @WORKTYPE = 'LIST' BEGIN SELECT 1 AS DWGNO; END",
                    target_procedure="sp_DE000600_SELECT",
                ),
            ],
            caller_parameter_contract=["@WORKTYPE"],
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
            source_evidence=[
                pb_srd_sql_evidence("SELECT 1 AS DISPLAY_NAME"),
                branch_contract_evidence(
                    "IF @WORKTYPE = 'LIST' BEGIN SELECT 1 AS DISPLAY_NAME; END"
                ),
            ],
            caller_parameter_contract=["@WORKTYPE"],
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

        verified_existing_source = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [dbo].[sp_ZX123456_SELECT]
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT 1 AS DISPLAY_NAME;
END
"""
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
            source_evidence=[
                existing_sp_evidence(verified_existing_source),
                branch_contract_evidence(
                    "IF @WORKTYPE = 'LIST' BEGIN SELECT 1 AS DISPLAY_NAME; END"
                ),
            ],
            caller_parameter_contract=["@WORKTYPE"],
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
            source_evidence=pb_srd_sql_evidence(),
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
                    source_evidence=pb_srd_sql_evidence(),
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
            source_evidence=pb_srd_sql_evidence(),
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
            source_evidence=pb_srd_sql_evidence(),
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
            source_evidence=pb_srd_sql_evidence(),
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
            source_evidence=[
                pb_srd_sql_evidence("FROM ZX902T A"),
                csharp_call_evidence(["@WORKTYPE", "@SCOPE_CODE", "@INPUT_DATE"]),
            ],
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
            source_evidence=[
                pb_srd_sql_evidence(
                    """DECLARE @DERIVED_YEAR VARCHAR(4)
      , @DERIVED_MONTH VARCHAR(2)
      , @BASE_YEAR VARCHAR(4)
      , @BOUNDARY_DATE VARCHAR(8);
SET @DERIVED_YEAR = LEFT(@INPUT_DATE, 4);
SET @DERIVED_MONTH = SUBSTRING(@INPUT_DATE, 5, 2);
SET @BASE_YEAR = CONVERT(VARCHAR(4), YEAR(GETDATE()));
SET @BOUNDARY_DATE = CONVERT(VARCHAR(8), DATEADD(DAY, -DAY(GETDATE()), GETDATE()), 112);
SELECT A.DISPLAY_NAME
FROM ZX902T A;""",
                ),
                branch_contract_evidence(
                    """DECLARE @DERIVED_YEAR VARCHAR(4)
      , @DERIVED_MONTH VARCHAR(2)
      , @BASE_YEAR VARCHAR(4)
      , @BOUNDARY_DATE VARCHAR(8);
SET @DERIVED_YEAR = LEFT(@INPUT_DATE, 4);
SET @DERIVED_MONTH = SUBSTRING(@INPUT_DATE, 5, 2);
SET @BASE_YEAR = CONVERT(VARCHAR(4), YEAR(GETDATE()));
SET @BOUNDARY_DATE = CONVERT(VARCHAR(8), DATEADD(DAY, -DAY(GETDATE()), GETDATE()), 112);
IF @WORKTYPE = 'LIST'
BEGIN
    SELECT A.DISPLAY_NAME FROM ZX902T A;
END;"""
                ),
            ],
            caller_parameter_contract=["@WORKTYPE", "@SCOPE_CODE", "@INPUT_DATE"],
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
            source_evidence=pb_srd_sql_evidence(),
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
            source_evidence=pb_srd_sql_evidence(),
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
            source_evidence=pb_srd_sql_evidence(),
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
                pb_srd_sql_evidence(),
                csharp_call_evidence(["@WORKTYPE", "@SCOPE_CODE", "@INPUT_DATE"]),
            ],
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("non_caller_procedure_parameter_detected", issue_codes)

    def test_sp_generation_contract_requires_caller_contract_for_pb_only_generation(self):
        generated = sp_metadata_header() + """
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @SCOPE_CODE VARCHAR(2)
    , @ROWCNT INT
AS
BEGIN
    SELECT A.DISPLAY_NAME
    FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence=pb_srd_sql_evidence(),
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("missing_caller_parameter_contract", issue_codes)

    def test_sp_generation_contract_rejects_placeholder_author_when_present(self):
        generated = """-- =============================================
-- AUTHOR:      <maintainer>
-- DESCRIPTION: Synthetic procedure contract
-- =============================================
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT A.DISPLAY_NAME
    FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            generated,
            source_evidence=[
                pb_srd_sql_evidence(),
                csharp_call_evidence(["@WORKTYPE"]),
            ],
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("sp_metadata_author_placeholder", issue_codes)

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
                pb_srd_sql_evidence(),
                csharp_call_evidence(["@WORKTYPE", "@SCOPE_CODE", "@INPUT_DATE"]),
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
                pb_srd_sql_evidence(
                    """DECLARE @ROWCNT INT;
SET @ROWCNT = 0;
SELECT A.DISPLAY_NAME
FROM ZX902T A;"""
                ),
                csharp_call_evidence(["@WORKTYPE", "@SCOPE_CODE", "@INPUT_DATE"]),
            ],
        )
        issue_codes = {issue["code"] for issue in result.metadata["issues"]}

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertNotIn("non_caller_procedure_parameter_detected", issue_codes)

    def test_sp_generation_contract_rejects_caller_fields_from_untrusted_evidence_kind(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                pb_srd_sql_evidence(),
                {"kind": "untrusted_blob", "caller_parameters": ["@WORKTYPE"]},
            ],
        )
        codes = {item["code"] for item in result.metadata["issues"]}

        self.assertFalse(result.success)
        self.assertIn("untrusted_caller_evidence_kind", codes)
        self.assertIn("missing_caller_parameter_contract", codes)

    def test_pasted_sql_summary_does_not_authorize_generated_signature(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence={"kind": "pasted_sql", "summary": "claimed procedure"},
            caller_parameter_contract=["@WORKTYPE"],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "missing_pb_or_db_source_evidence_for_sp_generation",
            {item["code"] for item in result.metadata["issues"]},
        )

    def test_existing_sp_cleanup_preserves_exact_signature_and_existing_constructs(self):
        original = sp_metadata_header() + """ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20) = ''
    , @FILTER_TEXT VARCHAR(30) = '%' OUTPUT
AS
BEGIN
    CREATE TABLE #KEEP_EXISTING (ID INT);
    ;WITH KEEP_EXISTING AS (SELECT 1 AS ID)
    SELECT ID FROM KEEP_EXISTING;
END
"""
        preserved = verify_pb_migration_sp_generation_contract(
            original,
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=existing_sp_evidence(original),
        )
        changed = verify_pb_migration_sp_generation_contract(
            original.replace("@FILTER_TEXT VARCHAR(30)", "@FILTER_TEXT VARCHAR(40)"),
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=existing_sp_evidence(original),
        )

        self.assertTrue(preserved.success, preserved.metadata["issues"])
        self.assertEqual("existing_sp_definition", preserved.metadata["signature_authority"])
        self.assertFalse(changed.success)
        self.assertIn(
            "existing_sp_signature_changed",
            {item["code"] for item in changed.metadata["issues"]},
        )

    def test_existing_sp_cleanup_requires_authenticated_original_artifact(self):
        original = sp_metadata_header() + """ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @FILTER_TEXT VARCHAR(30)
AS
BEGIN
    SELECT @FILTER_TEXT AS FILTER_TEXT;
END
"""
        direct_only = verify_pb_migration_sp_generation_contract(
            original,
            operation="existing_sp_cleanup",
            original_sp_text=original,
        )
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "SP_ZX123456_SELECT.sql"
            source_path.write_text(original, encoding="utf-8")
            authenticated = verify_pb_migration_sp_generation_contract(
                original,
                operation="existing_sp_cleanup",
                original_sp_text=original,
                source_evidence={
                    "kind": "existing_sp",
                    "verified": True,
                    "object": "SP_ZX123456_SELECT",
                    "definition_path": str(source_path),
                    "sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
                },
            )

        self.assertFalse(direct_only.success)
        self.assertIn(
            "existing_sp_definition_missing",
            {item["code"] for item in direct_only.metadata["issues"]},
        )
        self.assertTrue(authenticated.success, authenticated.metadata["issues"])

        mismatched_direct_argument = verify_pb_migration_sp_generation_contract(
            original,
            operation="existing_sp_cleanup",
            original_sp_text=original.replace("VARCHAR(30)", "VARCHAR(40)"),
            source_evidence=existing_sp_evidence(original),
        )
        self.assertFalse(mismatched_direct_argument.success)
        self.assertIn(
            "original_sp_text_evidence_mismatch",
            {item["code"] for item in mismatched_direct_argument.metadata["issues"]},
        )

    def test_sp_metadata_allows_use_go_without_author_but_rejects_unbacked_author_date(self):
        body = """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        evidence = [
            pb_srd_sql_evidence(),
            csharp_call_evidence(["@WORKTYPE"]),
        ]
        accepted = verify_pb_migration_sp_generation_contract(
            (
                "USE [C_SAMPLE]\nGO\n"
                "SET ANSI_NULLS ON\nGO\n"
                "SET QUOTED_IDENTIFIER ON\nGO\n"
                + sp_metadata_header("Inventory browse screen")
                + body
            ),
            source_evidence=evidence,
        )
        unbacked = verify_pb_migration_sp_generation_contract(
            """-- =============================================
-- AUTHOR:      invented
-- CREATE DATE: 2026-01-01
-- DESCRIPTION: Inventory browse screen
-- =============================================
""" + body,
            source_evidence=evidence,
        )
        codes = {item["code"] for item in unbacked.metadata["issues"]}

        self.assertTrue(accepted.success, accepted.metadata["issues"])
        self.assertFalse(unbacked.success)
        self.assertIn("sp_metadata_author_not_source_backed", codes)
        self.assertIn("sp_metadata_create_date_not_source_backed", codes)

    def test_source_artifact_path_and_hash_are_verified_before_completion(self):
        candidate = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT A.DISPLAY_NAME
    FROM ZX902T A;
END
"""
        source = "SELECT A.DISPLAY_NAME FROM ZX902T A;"
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "d_zx123456.srd"
            source_path.write_text(source, encoding="utf-8")
            accepted = verify_pb_migration_sp_generation_contract(
                candidate,
                source_evidence={
                    "kind": "pb_srd_sql",
                    "verified": True,
                    "path": str(source_path),
                    "sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
                    "candidate_provenance": {
                        "target_procedure": "SP_ZX123456_SELECT",
                        "preserved_fragments": ["FROM ZX902T"],
                    },
                },
                caller_parameter_contract=["@WORKTYPE"],
            )
            mismatched = verify_pb_migration_sp_generation_contract(
                candidate,
                source_evidence={
                    "kind": "pb_srd_sql",
                    "verified": True,
                    "path": str(source_path),
                    "sha256": "0" * 64,
                    "candidate_provenance": {
                        "target_procedure": "SP_ZX123456_SELECT",
                        "preserved_fragments": ["FROM ZX902T"],
                    },
                },
                caller_parameter_contract=["@WORKTYPE"],
            )

        self.assertTrue(accepted.success, accepted.metadata["issues"])
        self.assertFalse(mismatched.success)
        self.assertIn(
            "source_artifact_hash_mismatch",
            {item["code"] for item in mismatched.metadata["issues"]},
        )

    def test_source_artifact_rejects_unreadable_path_and_inline_path_spoofing(self):
        candidate = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT A.DISPLAY_NAME FROM ZX902T A;
END
"""
        fake_text = "SELECT DISPLAY_NAME FROM ZX902T"
        result = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence={
                "kind": "pb_srd_sql",
                "verified": True,
                "path": "does-not-exist.srd",
                "definition_text": fake_text,
                "sha256": hashlib.sha256(fake_text.encode("utf-8")).hexdigest(),
            },
            caller_parameter_contract=["@WORKTYPE"],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "source_artifact_unreadable",
            {item["code"] for item in result.metadata["issues"]},
        )

        uri_only = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence={
                "kind": "pb_srd_sql",
                "verified": True,
                "artifact_uri": "prompt://source-1",
                "definition_text": fake_text,
                "sha256": hashlib.sha256(fake_text.encode("utf-8")).hexdigest(),
            },
            caller_parameter_contract=["@WORKTYPE"],
        )
        self.assertFalse(uri_only.success)
        self.assertIn(
            "source_artifact_uri_unresolved",
            {item["code"] for item in uri_only.metadata["issues"]},
        )

    def test_candidate_cannot_authenticate_itself_as_source_evidence(self):
        candidate = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT A.DISPLAY_NAME FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=pasted_sql_evidence(
                candidate,
                evidence_role="existing_procedure",
            ),
            caller_parameter_contract=["@WORKTYPE"],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "candidate_reused_as_source_evidence",
            {item["code"] for item in result.metadata["issues"]},
        )

        comment_changed = candidate.replace(
            "-- DESCRIPTION:",
            "-- source capture note\n-- DESCRIPTION:",
        ).replace("CREATE OR ALTER", "create or alter").replace("SELECT", "select")
        comment_result = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=pasted_sql_evidence(
                comment_changed,
                evidence_role="existing_procedure",
            ),
            caller_parameter_contract=["@WORKTYPE"],
        )
        self.assertFalse(comment_result.success)
        self.assertIn(
            "candidate_reused_as_source_evidence",
            {item["code"] for item in comment_result.metadata["issues"]},
        )

    def test_body_fragment_must_be_preserved_in_candidate(self):
        candidate = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT A.DISPLAY_NAME FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=pasted_sql_evidence(
                "DELETE FROM ZX902T WHERE RECORD_ID = 1;",
                evidence_role="body_fragment",
            ),
            caller_parameter_contract=["@WORKTYPE"],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "body_fragment_not_present_in_candidate",
            {item["code"] for item in result.metadata["issues"]},
        )

    def test_schema_summary_alone_cannot_authorize_procedure_body(self):
        candidate = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT A.DISPLAY_NAME FROM ZX902T A;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence={"kind": "db_schema", "summary": "ZX902T columns"},
            caller_parameter_contract=["@WORKTYPE"],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "missing_pb_or_db_source_evidence_for_sp_generation",
            {item["code"] for item in result.metadata["issues"]},
        )

    def test_verified_external_caller_requires_artifact_hash_and_typed_ordered_contract(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ROWCOUNT INT OUTPUT
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        pb_evidence = pb_srd_sql_evidence()
        incomplete = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                pb_evidence,
                {
                    "kind": "external_caller",
                    "verified": True,
                    "caller_id": "batch-a",
                    "artifact_uri": "artifact://caller-a",
                    "sha256": "short",
                    "parameter_contract": [
                        {"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"},
                        {"name": "@ROWCOUNT", "type_spec": "INT", "output": True},
                    ],
                },
            ],
        )
        accepted_contract = [
            {"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"},
            {"name": "@ROWCOUNT", "type_spec": "INT", "output": True},
        ]
        accepted = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                pb_evidence,
                external_caller_evidence(accepted_contract),
            ],
        )

        self.assertFalse(incomplete.success)
        self.assertIn(
            "incomplete_external_caller_evidence",
            {item["code"] for item in incomplete.metadata["issues"]},
        )
        self.assertTrue(accepted.success, accepted.metadata["issues"])

    def test_inferred_draft_evidence_cannot_be_released_as_new_generation(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            sql,
            operation="new_generation",
            source_evidence={
                "kind": "approved_inferred_draft",
                "approved": True,
                "approval_artifact": "approval://draft-escape",
                "approved_parameters": ["@WORKTYPE"],
            },
            caller_parameter_contract=["@WORKTYPE"],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "inferred_evidence_operation_mismatch",
            {item["code"] for item in result.metadata["issues"]},
        )

    def test_csharp_caller_requires_readable_hash_bound_artifact(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                pb_srd_sql_evidence(),
                {
                    "kind": "csharp_call",
                    "path": "does-not-exist.cs",
                    "db_parameters": ["@WORKTYPE"],
                    "target_procedure": "SP_ZX123456_SELECT",
                },
            ],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "caller_artifact_unreadable",
            {item["code"] for item in result.metadata["issues"]},
        )

    def test_csharp_caller_rejects_comment_only_parameter_mentions_and_unresolved_uri(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        comment_only = '// new DbParameter("@WORKTYPE", ignored)'
        path, digest = write_test_artifact("comment-only-caller.cs", comment_only)
        comment_result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                pb_srd_sql_evidence(),
                {
                    "kind": "csharp_call",
                    "verified": True,
                    "path": str(path),
                    "sha256": digest,
                    "db_parameters": ["@WORKTYPE"],
                    "target_procedure": "SP_ZX123456_SELECT",
                },
            ],
        )
        uri_result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                pb_srd_sql_evidence(),
                {
                    "kind": "csharp_call",
                    "verified": True,
                    "artifact_uri": "prompt://caller-1",
                    "definition_text": 'new DbParameter("@WORKTYPE", value)',
                    "sha256": hashlib.sha256(
                        'new DbParameter("@WORKTYPE", value)'.encode("utf-8")
                    ).hexdigest(),
                    "db_parameters": ["@WORKTYPE"],
                    "target_procedure": "SP_ZX123456_SELECT",
                },
            ],
        )

        self.assertFalse(comment_result.success)
        self.assertIn(
            "csharp_caller_target_procedure_mismatch",
            {item["code"] for item in comment_result.metadata["issues"]},
        )
        self.assertFalse(uri_result.success)
        self.assertIn(
            "caller_artifact_uri_unresolved",
            {item["code"] for item in uri_result.metadata["issues"]},
        )

    def test_direct_external_contract_without_artifact_provenance_is_rejected(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=pb_srd_sql_evidence(),
            external_caller_contract=[
                {"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"}
            ],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "external_caller_contract_without_provenance",
            {item["code"] for item in result.metadata["issues"]},
        )

    def test_existing_sp_signature_parser_preserves_comment_like_string_defaults(self):
        original = sp_metadata_header() + """ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @FILTER_TEXT NVARCHAR(30) = N'-- AS /* keep */'
AS
BEGIN
    SELECT @FILTER_TEXT AS FILTER_TEXT;
END
"""
        unchanged = verify_pb_migration_sp_generation_contract(
            original,
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=existing_sp_evidence(original),
        )
        changed = verify_pb_migration_sp_generation_contract(
            original.replace("N'-- AS /* keep */'", "N'-- AS /* changed */'"),
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=existing_sp_evidence(original),
        )

        self.assertTrue(unchanged.success, unchanged.metadata["issues"])
        self.assertFalse(changed.success)
        self.assertIn(
            "existing_sp_signature_changed",
            {item["code"] for item in changed.metadata["issues"]},
        )

    def test_external_caller_output_and_readonly_contract_is_enforced(self):
        contract = [
            {"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"},
            {"name": "@ROWCOUNT", "type_spec": "INT", "output": True},
        ]
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ROWCOUNT INT
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                pb_srd_sql_evidence(),
                external_caller_evidence(contract),
            ],
        )

        self.assertFalse(result.success)
        self.assertIn(
            "caller_parameter_output_mismatch",
            {item["code"] for item in result.metadata["issues"]},
        )

    def test_external_caller_manifest_and_readonly_contract_are_enforced(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
    , @ROWS DBO.ROWTYPE
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        readonly_contract = [
            {"name": "@ROWS", "type_spec": "DBO.ROWTYPE", "readonly": True},
        ]
        readonly_result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                pb_srd_sql_evidence(),
                external_caller_evidence(readonly_contract),
            ],
            caller_parameter_contract=["@WORKTYPE"],
        )

        manifest_text = json.dumps(
            {
                "caller_id": "batch-mismatch",
                "parameter_contract": [
                    {"name": "@ROWS", "type_spec": "INT", "readonly": True},
                ],
            },
            sort_keys=True,
        )
        path, digest = write_test_artifact("external-mismatch.json", manifest_text)
        manifest_result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                pb_srd_sql_evidence(),
                {
                    "kind": "external_caller",
                    "verified": True,
                    "caller_id": "batch-mismatch",
                    "path": str(path),
                    "sha256": digest,
                    "parameter_contract": readonly_contract,
                },
            ],
            caller_parameter_contract=["@WORKTYPE"],
        )

        self.assertFalse(readonly_result.success)
        self.assertIn(
            "caller_parameter_readonly_mismatch",
            {item["code"] for item in readonly_result.metadata["issues"]},
        )
        self.assertFalse(manifest_result.success)
        self.assertIn(
            "incomplete_external_caller_evidence",
            {item["code"] for item in manifest_result.metadata["issues"]},
        )

    def test_existing_sp_cleanup_does_not_require_worktype(self):
        original = sp_metadata_header() + """ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @FILTER_TEXT VARCHAR(30)
AS
BEGIN
    SELECT @FILTER_TEXT AS FILTER_TEXT;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            original,
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=existing_sp_evidence(original),
        )

        self.assertTrue(result.success, result.metadata["issues"])

    def test_approved_inferred_draft_never_becomes_release_ready(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        result = verify_pb_migration_sp_generation_contract(
            sql,
            operation="approved_inferred_draft",
            source_evidence={
                "kind": "approved_inferred_draft",
                "approved": True,
                "approval_artifact": "approval://draft-1",
                "approved_parameters": ["@WORKTYPE"],
            },
        )

        self.assertFalse(result.success)
        self.assertEqual("pending", result.metadata["status"])
        self.assertEqual("pending", result.metadata["release_readiness"]["status"])

    def test_existing_sp_cleanup_preserves_identity_comments_and_statements(self):
        original = sp_metadata_header("Existing cleanup") + """ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    -- formatter-sensitive comment
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        formatting_only = sp_metadata_header("Existing cleanup") + """alter procedure [dbo].[sp_zx123456_select]
    @worktype varchar(20)
as
begin
        -- formatter-sensitive comment
        select @worktype as worktype ;
end ;
"""
        evidence = existing_sp_evidence(original)
        accepted = verify_pb_migration_sp_generation_contract(
            formatting_only,
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=evidence,
        )
        renamed = verify_pb_migration_sp_generation_contract(
            formatting_only.replace("sp_zx123456_select", "sp_zx123456_save"),
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=evidence,
        )
        comment_changed = verify_pb_migration_sp_generation_contract(
            formatting_only.replace("formatter-sensitive comment", "changed comment"),
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=evidence,
        )
        statement_changed = verify_pb_migration_sp_generation_contract(
            formatting_only.replace(
                "select @worktype as worktype ;",
                "delete from ZX902T where WORKTYPE = @worktype ;",
            ),
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=evidence,
        )

        self.assertTrue(accepted.success, accepted.metadata["issues"])
        self.assertIn(
            "existing_sp_identity_changed",
            {item["code"] for item in renamed.metadata["issues"]},
        )
        self.assertIn(
            "existing_sp_comments_changed",
            {item["code"] for item in comment_changed.metadata["issues"]},
        )
        self.assertIn(
            "existing_sp_body_or_statement_changed",
            {item["code"] for item in statement_changed.metadata["issues"]},
        )

    def test_existing_sp_business_comments_remain_bound_to_code_position(self):
        original = """USE [SYNTHETIC_DB]
GO
/****** Object: StoredProcedure [dbo].[SP_ZX123456_SELECT] Script Date: 2026-07-27 ******/
SET ANSI_NULLS ON
GO
""" + sp_metadata_header("Existing cleanup") + """ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    -- Keep this rule adjacent to the guarded read.
    SELECT @WORKTYPE AS WORKTYPE;

    -- Delete only the matching work type.
    DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;
END;
"""
        formatting_only = original.replace("ALTER PROCEDURE", "alter procedure").replace(
            "SELECT @WORKTYPE AS WORKTYPE;",
            "select @worktype as worktype ;",
        )
        relocated = formatting_only.replace(
            "    -- Keep this rule adjacent to the guarded read.\n    select @worktype as worktype ;",
            "    select @worktype as worktype ;\n    -- Keep this rule adjacent to the guarded read.",
        )
        evidence = existing_sp_evidence(original)
        accepted = verify_pb_migration_sp_generation_contract(
            formatting_only,
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=evidence,
        )
        moved = verify_pb_migration_sp_generation_contract(
            relocated,
            operation="existing_sp_cleanup",
            original_sp_text=original,
            source_evidence=evidence,
        )

        self.assertTrue(accepted.success, accepted.metadata["issues"])
        self.assertFalse(moved.success)
        self.assertIn(
            "existing_sp_comment_binding_changed",
            {item["code"] for item in moved.metadata["issues"]},
        )

    def test_new_generation_requires_correlated_independent_source_evidence(self):
        candidate = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT A.DISPLAY_NAME FROM ZX902T A;
END;
"""
        unrelated = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=pb_srd_sql_evidence("SELECT B.OTHER_NAME FROM OTHER_TABLE B;"),
            caller_parameter_contract=["@WORKTYPE"],
        )
        disguised_candidate = (
            candidate.replace("CREATE OR ALTER", "create or alter")
            .replace("SELECT", "select")
            .replace("FROM", "from")
            + "\n-- capture-only comment\n;;;"
        )
        self_evidence = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=pasted_sql_evidence(
                disguised_candidate,
                evidence_role="existing_procedure",
            ),
            caller_parameter_contract=["@WORKTYPE"],
        )

        self.assertIn(
            "source_evidence_not_correlated_to_candidate",
            {item["code"] for item in unrelated.metadata["issues"]},
        )
        self.assertIn(
            "candidate_reused_as_source_evidence",
            {item["code"] for item in self_evidence.metadata["issues"]},
        )

    def test_small_source_statement_cannot_authorize_unsupported_candidate_statements_or_clauses(self):
        source = "SELECT @WORKTYPE AS WORKTYPE;"
        base = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        mutations = {
            "DELETE": base.replace(
                "    SELECT @WORKTYPE AS WORKTYPE;",
                "    SELECT @WORKTYPE AS WORKTYPE;\n    DELETE FROM ZX902T;",
            ),
            "DELETE_WITHOUT_TERMINATOR": base.replace(
                "    SELECT @WORKTYPE AS WORKTYPE;",
                "    SELECT @WORKTYPE AS WORKTYPE;\n    DELETE FROM ZX902T",
            ),
            "UPDATE": base.replace(
                "    SELECT @WORKTYPE AS WORKTYPE;",
                "    SELECT @WORKTYPE AS WORKTYPE;\n    UPDATE ZX902T SET DISPLAY_NAME = 'X';",
            ),
            "INSERT": base.replace(
                "    SELECT @WORKTYPE AS WORKTYPE;",
                "    SELECT @WORKTYPE AS WORKTYPE;\n    INSERT INTO ZX902T (DISPLAY_NAME) VALUES ('X');",
            ),
            "JOIN": base.replace(
                "SELECT @WORKTYPE AS WORKTYPE",
                "SELECT A.WORKTYPE FROM ZX902T A INNER JOIN ZX903T B ON A.ID = B.ID",
            ),
            "WHERE": base.replace(
                "SELECT @WORKTYPE AS WORKTYPE",
                "SELECT @WORKTYPE AS WORKTYPE WHERE @WORKTYPE = 'LIST'",
            ),
            "DUPLICATE_STATEMENT": base.replace(
                "    SELECT @WORKTYPE AS WORKTYPE;",
                "    SELECT @WORKTYPE AS WORKTYPE;\n    SELECT @WORKTYPE AS WORKTYPE;",
            ),
            "UNSUPPORTED_WORKTYPE_CONDITION": base.replace(
                "    SELECT @WORKTYPE AS WORKTYPE;",
                """    IF @WORKTYPE = 'LIST' OR 1 = 1
    BEGIN
        SELECT @WORKTYPE AS WORKTYPE;
    END;""",
            ),
        }

        accepted = verify_pb_migration_sp_generation_contract(
            base,
            source_evidence=[
                pb_srd_sql_evidence(source),
                csharp_call_evidence(["@WORKTYPE"]),
            ],
        )
        self.assertTrue(accepted.success, accepted.metadata["issues"])
        for label, candidate in mutations.items():
            with self.subTest(mutation=label):
                result = verify_pb_migration_sp_generation_contract(
                    candidate,
                    source_evidence=[
                        pb_srd_sql_evidence(source),
                        csharp_call_evidence(["@WORKTYPE"]),
                    ],
                )
                self.assertFalse(result.success)
                issue_codes = {item["code"] for item in result.metadata["issues"]}
                if label == "JOIN":
                    self.assertIn("source_evidence_not_correlated_to_candidate", issue_codes)
                else:
                    self.assertIn(
                        "candidate_body_statement_not_covered_by_source",
                        issue_codes,
                    )

    def test_source_covered_dml_is_not_globally_forbidden(self):
        source = """SELECT @WORKTYPE AS WORKTYPE;
DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;
"""
        candidate = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;

    IF @WORKTYPE = 'DELETE'
    BEGIN
        DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;
    END;
END;
"""

        result = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[
                pb_srd_sql_evidence(source),
                csharp_call_evidence(["@WORKTYPE"]),
                branch_contract_evidence(
                    "SELECT @WORKTYPE AS WORKTYPE; "
                    "IF @WORKTYPE = 'DELETE' BEGIN "
                    "DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE; END"
                ),
            ],
        )

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual(
            {"generated_envelope", "branch_contract"},
            {item["coverage"] for item in result.metadata["body_traceability"]},
        )
        self.assertTrue(
            all(
                item["coverage"] == "branch_contract"
                for item in result.metadata["body_traceability"]
                if item["kind"] not in {
                    "PROCEDURE_BEGIN_SCOPE",
                    "PROCEDURE_END_SCOPE",
                }
            )
        )
        self.assertEqual(
            1,
            len(
                {
                    item["authority_id"]
                    for item in result.metadata["body_traceability"]
                    if item["coverage"]
                    not in {"generated_wrapper", "generated_envelope"}
                }
            ),
        )

    def test_worktype_branch_requires_source_or_bound_branch_contract(self):
        source_dml = "DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;"
        candidate = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE <> 'NEVER'
    BEGIN
        DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;
    END;
END;
"""
        caller = csharp_call_evidence(["@WORKTYPE"])
        unbound = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[pb_srd_sql_evidence(source_dml), caller],
        )
        source_backed = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[
                pb_srd_sql_evidence(
                    "IF @WORKTYPE <> 'NEVER'\nBEGIN\n"
                    + source_dml
                    + "\nEND;"
                ),
                caller,
            ],
        )
        contract_backed = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[
                pb_srd_sql_evidence(source_dml),
                caller,
                branch_contract_evidence(
                    "IF @WORKTYPE <> 'NEVER' BEGIN "
                    "DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE; END"
                ),
            ],
        )

        self.assertFalse(unbound.success)
        self.assertIn(
            "candidate_body_statement_not_covered_by_source",
            {item["code"] for item in unbound.metadata["issues"]},
        )
        self.assertTrue(source_backed.success, source_backed.metadata["issues"])
        self.assertTrue(contract_backed.success, contract_backed.metadata["issues"])
        self.assertIn(
            "branch_contract",
            {item["coverage"] for item in contract_backed.metadata["body_traceability"]},
        )

    def test_branch_traceability_binds_arm_nesting_and_statement_order(self):
        source = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
    UPDATE ZX902T SET DISPLAY_NAME = 'LIST' WHERE WORKTYPE = @WORKTYPE;

    IF @WORKTYPE <> 'NEVER'
    BEGIN
        INSERT INTO ZX903T (WORKTYPE) VALUES (@WORKTYPE);
    END
    ELSE
    BEGIN
        DELETE FROM ZX903T WHERE WORKTYPE = @WORKTYPE;
    END;
END
ELSE
BEGIN
    DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;
END;
"""
        candidate_template = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
{body}
END;
"""
        original = candidate_template.format(body=source)
        arm_swapped = candidate_template.format(
            body=source.replace(
                "    SELECT @WORKTYPE AS WORKTYPE;\n"
                "    UPDATE ZX902T SET DISPLAY_NAME = 'LIST' WHERE WORKTYPE = @WORKTYPE;",
                "    DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;",
            ).replace(
                "ELSE\nBEGIN\n    DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;\nEND;",
                "ELSE\nBEGIN\n    SELECT @WORKTYPE AS WORKTYPE;\n"
                "    UPDATE ZX902T SET DISPLAY_NAME = 'LIST' WHERE WORKTYPE = @WORKTYPE;\nEND;",
            )
        )
        same_arm_reordered = candidate_template.format(
            body=source.replace(
                "    SELECT @WORKTYPE AS WORKTYPE;\n"
                "    UPDATE ZX902T SET DISPLAY_NAME = 'LIST' WHERE WORKTYPE = @WORKTYPE;",
                "    UPDATE ZX902T SET DISPLAY_NAME = 'LIST' WHERE WORKTYPE = @WORKTYPE;\n"
                "    SELECT @WORKTYPE AS WORKTYPE;",
            )
        )
        nested_arms_swapped = candidate_template.format(
            body=source.replace(
                "        INSERT INTO ZX903T (WORKTYPE) VALUES (@WORKTYPE);",
                "        __NESTED_BRANCH_TEMP__;",
            ).replace(
                "        DELETE FROM ZX903T WHERE WORKTYPE = @WORKTYPE;",
                "        INSERT INTO ZX903T (WORKTYPE) VALUES (@WORKTYPE);",
            ).replace(
                "        __NESTED_BRANCH_TEMP__;",
                "        DELETE FROM ZX903T WHERE WORKTYPE = @WORKTYPE;",
            )
        )
        evidence = [pb_srd_sql_evidence(source), csharp_call_evidence(["@WORKTYPE"])]

        accepted = verify_pb_migration_sp_generation_contract(
            original,
            source_evidence=evidence,
        )
        self.assertTrue(accepted.success, accepted.metadata["issues"])
        self.assertTrue(
            all(
                item["order_kind"]
                in {"envelope", "wrapper", "branch", "scope", "statement"}
                for item in accepted.metadata["body_traceability"]
            )
        )
        for label, candidate in {
            "arm_swapped": arm_swapped,
            "same_arm_reordered": same_arm_reordered,
            "nested_arms_swapped": nested_arms_swapped,
        }.items():
            with self.subTest(case=label):
                result = verify_pb_migration_sp_generation_contract(
                    candidate,
                    source_evidence=evidence,
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "candidate_body_statement_not_covered_by_source",
                    {item["code"] for item in result.metadata["issues"]},
                )

    def test_branch_traceability_uses_one_total_sibling_execution_order(self):
        branch_sql = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;

    IF @WORKTYPE = 'DELETE'
    BEGIN
        DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;
    END;
END;
"""
        moved_branch_sql = """IF @WORKTYPE = 'LIST'
BEGIN
    IF @WORKTYPE = 'DELETE'
    BEGIN
        DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;
    END;

    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        candidate_template = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;

{body}
END;
"""
        valid_candidate = candidate_template.format(body=branch_sql)
        moved_candidate = candidate_template.format(body=moved_branch_sql)
        caller = csharp_call_evidence(["@WORKTYPE"])
        source_evidence = [pb_srd_sql_evidence(branch_sql), caller]
        contract_evidence = [
            pb_srd_sql_evidence(
                "SELECT @WORKTYPE AS WORKTYPE;\n"
                "DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;"
            ),
            caller,
            branch_contract_evidence(branch_sql),
        ]

        valid_source = verify_pb_migration_sp_generation_contract(
            valid_candidate,
            source_evidence=source_evidence,
        )
        valid_contract = verify_pb_migration_sp_generation_contract(
            valid_candidate,
            source_evidence=contract_evidence,
        )
        moved_source = verify_pb_migration_sp_generation_contract(
            moved_candidate,
            source_evidence=source_evidence,
        )
        moved_contract = verify_pb_migration_sp_generation_contract(
            moved_candidate,
            source_evidence=contract_evidence,
        )

        self.assertTrue(valid_source.success, valid_source.metadata["issues"])
        self.assertTrue(valid_contract.success, valid_contract.metadata["issues"])
        wrapper_events = [
            item
            for item in valid_source.metadata["body_traceability"]
            if item["order_kind"] == "wrapper"
        ]
        self.assertEqual([0], [item["ordinal"] for item in wrapper_events])
        self.assertEqual(
            1,
            next(
                item["ordinal"]
                for item in valid_source.metadata["body_traceability"]
                if item["order_kind"] not in {"envelope", "wrapper"}
            ),
        )
        then_events = [
            (item["kind"], item["order_in_path"])
            for item in valid_source.metadata["body_traceability"]
            if len(item["branch_path"]) == 1
            and item["branch_path"][0]["arm"] == "then"
        ]
        self.assertEqual(
            [("ARM_BEGIN", 1), ("SELECT", 2), ("IF", 3), ("ARM_END", 4)],
            then_events,
        )
        for result in (moved_source, moved_contract):
            self.assertFalse(result.success)
            self.assertIn(
                "candidate_body_statement_not_covered_by_source",
                {item["code"] for item in result.metadata["issues"]},
            )

    def test_set_nocount_wrapper_is_only_the_first_root_event(self):
        template = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
{body}
END;
"""
        caller = csharp_call_evidence(["@WORKTYPE"])
        source_select = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")
        duplicate_candidate = template.format(
            body="""    SET NOCOUNT ON;
    SET NOCOUNT ON;
    SELECT @WORKTYPE AS WORKTYPE;"""
        )
        later_candidate = template.format(
            body="""    SELECT @WORKTYPE AS WORKTYPE;
    SET NOCOUNT ON;"""
        )
        nested_candidate = template.format(
            body="""    IF @WORKTYPE = 'LIST'
    BEGIN
        SET NOCOUNT ON;
        SELECT @WORKTYPE AS WORKTYPE;
    END;"""
        )
        nested_source = """IF @WORKTYPE = 'LIST'
BEGIN
    SET NOCOUNT ON;
    SELECT @WORKTYPE AS WORKTYPE;
END;"""

        duplicate = verify_pb_migration_sp_generation_contract(
            duplicate_candidate,
            source_evidence=[source_select, caller],
        )
        later = verify_pb_migration_sp_generation_contract(
            later_candidate,
            source_evidence=[source_select, caller],
        )
        nested_unbound = verify_pb_migration_sp_generation_contract(
            nested_candidate,
            source_evidence=[
                pb_srd_sql_evidence(
                    "IF @WORKTYPE = 'LIST' BEGIN "
                    "SELECT @WORKTYPE AS WORKTYPE; END;"
                ),
                caller,
            ],
        )
        nested_bound = verify_pb_migration_sp_generation_contract(
            nested_candidate,
            source_evidence=[pb_srd_sql_evidence(nested_source), caller],
        )

        for result in (duplicate, later, nested_unbound):
            self.assertFalse(result.success)
            self.assertIn(
                "candidate_body_not_covered_by_single_authority",
                {item["code"] for item in result.metadata["issues"]},
            )
        self.assertTrue(nested_bound.success, nested_bound.metadata["issues"])
        nested_nocount = next(
            item
            for item in nested_bound.metadata["body_traceability"]
            if item["preview"] == "SET NOCOUNT ON"
        )
        self.assertEqual("source_statement", nested_nocount["coverage"])
        self.assertGreater(nested_nocount["ordinal"], 0)
        self.assertNotEqual("wrapper", nested_nocount["order_kind"])

    def test_body_traceability_rejects_cross_artifact_branch_splicing(self):
        candidate_branch = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
ELSE
BEGIN
    DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;
END;
"""
        candidate = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;

{body}
END;
""".format(body=candidate_branch)
        source_a = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        source_b = """IF @WORKTYPE = 'LIST'
BEGIN
    UPDATE ZX902T SET DISPLAY_NAME = 'OTHER' WHERE WORKTYPE = @WORKTYPE;
END
ELSE
BEGIN
    DELETE FROM ZX902T WHERE WORKTYPE = @WORKTYPE;
END;
"""
        mismatched_branch_contract = branch_contract_evidence(
            source_b,
            artifact_name="splice-mismatched-branch",
        )
        complete_branch_contract = branch_contract_evidence(
            candidate_branch,
            artifact_name="splice-complete-branch",
        )
        composite_support_a = bound_source_evidence(
            "pb_srd_sql",
            candidate_branch,
            artifact_name="splice-composite-support-a",
        )
        complete_composite_contract = composite_contract_evidence(
            candidate,
            [composite_support_a["sha256"]],
            artifact_name="splice-complete-composite",
        )
        lineage = [composite_support_a["sha256"]]
        composite_variants = {
            "wrong_trace_hash": composite_contract_evidence(
                candidate,
                lineage,
                artifact_name="splice-wrong-trace-hash",
                trace_sha256="f" * 64,
            ),
            "partial_lineage": composite_contract_evidence(
                candidate,
                [],
                artifact_name="splice-partial-lineage",
            ),
            "unknown_lineage": composite_contract_evidence(
                candidate,
                ["0" * 64],
                artifact_name="splice-unknown-lineage",
            ),
            "duplicate_lineage": composite_contract_evidence(
                candidate,
                [lineage[0], lineage[0]],
                artifact_name="splice-duplicate-lineage",
            ),
            "wrong_trace_sql": composite_contract_evidence(
                candidate.replace("DELETE FROM", "UPDATE"),
                lineage,
                artifact_name="splice-wrong-trace-sql",
            ),
        }
        unbound_composite_contract = composite_contract_evidence(
            candidate,
            ["0" * 64],
            artifact_name="splice-unbound-composite",
        )
        caller = csharp_call_evidence(["@WORKTYPE"])

        source_source = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[
                bound_source_evidence(
                    "pb_srd_sql", source_a, artifact_name="splice-source-a"
                ),
                bound_source_evidence(
                    "pb_srd_sql", source_b, artifact_name="splice-source-b"
                ),
                caller,
            ],
        )
        branch_source = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[
                bound_source_evidence(
                    "pb_srd_sql",
                    source_a,
                    artifact_name="splice-source-branch-a",
                ),
                caller,
                mismatched_branch_contract,
            ],
        )
        complete_source = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[
                bound_source_evidence(
                    "pb_srd_sql",
                    candidate_branch,
                    artifact_name="splice-complete-source",
                ),
                caller,
            ],
        )
        complete_branch = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[
                bound_source_evidence(
                    "pb_srd_sql",
                    "SELECT @WORKTYPE AS WORKTYPE;",
                    artifact_name="splice-supporting-source",
                ),
                caller,
                complete_branch_contract,
            ],
        )
        complete_composite = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[
                composite_support_a,
                caller,
                complete_composite_contract,
            ],
        )
        unbound_composite = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[
                composite_support_a,
                caller,
                unbound_composite_contract,
            ],
        )
        composite_variant_results = {
            name: verify_pb_migration_sp_generation_contract(
                candidate,
                source_evidence=[
                    composite_support_a,
                    caller,
                    evidence,
                ],
            )
            for name, evidence in composite_variants.items()
        }

        self.assertTrue(complete_source.success, complete_source.metadata["issues"])
        self.assertTrue(complete_branch.success, complete_branch.metadata["issues"])
        self.assertTrue(
            complete_composite.success,
            complete_composite.metadata["issues"],
        )
        self.assertEqual(
            {"composite_contract"},
            {
                item["coverage"]
                for item in complete_composite.metadata["body_traceability"]
                if item["coverage"]
                not in {"generated_wrapper", "generated_envelope"}
            },
        )
        self.assertFalse(unbound_composite.success)
        self.assertIn(
            "composite_contract_source_lineage_mismatch",
            {item["code"] for item in unbound_composite.metadata["issues"]},
        )
        expected_composite_issues = {
            "wrong_trace_hash": "composite_contract_trace_sha256_mismatch",
            "partial_lineage": "composite_contract_source_lineage_invalid",
            "unknown_lineage": "composite_contract_source_lineage_mismatch",
            "duplicate_lineage": "composite_contract_source_lineage_duplicate",
            "wrong_trace_sql": "composite_contract_candidate_trace_mismatch",
        }
        for name, expected_issue in expected_composite_issues.items():
            with self.subTest(composite_case=name):
                result = composite_variant_results[name]
                self.assertFalse(result.success)
                self.assertIn(
                    expected_issue,
                    {item["code"] for item in result.metadata["issues"]},
                )
        for result in (source_source, branch_source):
            self.assertFalse(result.success)
            self.assertIn(
                "candidate_body_not_covered_by_single_authority",
                {item["code"] for item in result.metadata["issues"]},
            )

    def test_structural_trace_preserves_try_loop_scope_and_transaction_boundaries(self):
        caller = csharp_call_evidence(["@WORKTYPE"])

        def procedure(body):
            return sp_metadata_header() + f"""CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
{body}
END;
"""

        select_sql = "SELECT @WORKTYPE AS WORKTYPE;"
        try_sql = """BEGIN TRY
    SELECT @WORKTYPE AS WORKTYPE;
END TRY
BEGIN CATCH
END CATCH;"""
        loop_sql = """WHILE @WORKTYPE = 'LIST'
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;"""
        nested_scope_sql = """BEGIN
    BEGIN
        SELECT @WORKTYPE AS WORKTYPE;
    END;
END;"""
        adjacent_sql = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
ELSE
BEGIN
    WHILE @WORKTYPE = 'SAVE'
    BEGIN
        BEGIN TRANSACTION;
        UPDATE ZX902T SET WORKTYPE = @WORKTYPE;
        COMMIT TRANSACTION;
    END;
END;"""
        adjacent_moved = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
ELSE
BEGIN
    WHILE @WORKTYPE = 'SAVE'
    BEGIN
    END;
    BEGIN TRANSACTION;
    UPDATE ZX902T SET WORKTYPE = @WORKTYPE;
    COMMIT TRANSACTION;
END;"""

        exact_cases = (try_sql, loop_sql, nested_scope_sql, adjacent_sql)
        for index, source_sql in enumerate(exact_cases):
            with self.subTest(exact_structure=index):
                result = verify_pb_migration_sp_generation_contract(
                    procedure(source_sql),
                    source_evidence=[pb_srd_sql_evidence(source_sql), caller],
                )
                self.assertTrue(result.success, result.metadata["issues"])

        unauthorized_variants = {
            "try_catch_added": (select_sql, try_sql),
            "try_catch_omitted": (try_sql, select_sql),
            "while_body_moved_to_root": (
                loop_sql,
                """WHILE @WORKTYPE = 'LIST'
BEGIN
END;
SELECT @WORKTYPE AS WORKTYPE;""",
            ),
            "nested_begin_omitted": (nested_scope_sql, select_sql),
            "transaction_before_nocount": (
                select_sql,
                """BEGIN TRANSACTION;
SET NOCOUNT ON;
SELECT @WORKTYPE AS WORKTYPE;""",
            ),
            "else_loop_transaction_moved": (adjacent_sql, adjacent_moved),
        }
        for label, (source_sql, candidate_body) in unauthorized_variants.items():
            with self.subTest(structural_bypass=label):
                result = verify_pb_migration_sp_generation_contract(
                    procedure(candidate_body),
                    source_evidence=[pb_srd_sql_evidence(source_sql), caller],
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "candidate_body_not_covered_by_single_authority",
                    {item["code"] for item in result.metadata["issues"]},
                )

        transaction_trace = pb_migration._sql_hierarchical_trace(
            procedure("""BEGIN TRANSACTION;
SET NOCOUNT ON;
SELECT @WORKTYPE AS WORKTYPE;""")
        )
        transaction_nocount = [
            item for item in transaction_trace if item["preview"] == "SET NOCOUNT ON"
        ]
        self.assertEqual(len(transaction_nocount), 1)
        self.assertFalse(transaction_nocount[0]["generated_wrapper"])
        self.assertGreater(transaction_nocount[0]["order_in_path"], 0)

        composite_without_try = composite_contract_evidence(
            select_sql,
            [pb_srd_sql_evidence(try_sql)["sha256"]],
            artifact_name="composite-omits-try-catch",
        )
        composite_result = verify_pb_migration_sp_generation_contract(
            procedure(try_sql),
            source_evidence=[pb_srd_sql_evidence(try_sql), caller, composite_without_try],
        )
        self.assertFalse(composite_result.success)
        self.assertIn(
            "composite_contract_candidate_trace_mismatch",
            {item["code"] for item in composite_result.metadata["issues"]},
        )

    def test_csharp_caller_requires_one_complete_executable_exact_case_call(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")

        def evidence_from_text(name, artifact_text):
            artifact_text = complete_csharp_caller_artifact(artifact_text)
            path, digest = write_test_artifact(name, artifact_text)
            return {
                "kind": "csharp_call",
                "verified": True,
                "path": str(path),
                "definition_text": artifact_text,
                "sha256": digest,
                "db_parameters": ["@WORKTYPE"],
                "target_procedure": "SP_ZX123456_SELECT",
            }

        forgeries = {
            "raw_string_parameter": '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , """new DbParameter("@WORKTYPE", value)"""
);''',
            "inactive_preprocessor": '''#if false
return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", value)
);
#endif''',
            "unterminated_call": '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", value)''',
            "wrong_receiver_case": '''return DBCLIENT.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", value)
);''',
        }
        valid = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[body, csharp_call_evidence(["@WORKTYPE"])],
        )
        valid_with_raw_directive_text = '''string documentation = """
#if false
not a preprocessor directive here
#endif
""";
return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", value)
);'''
        valid_with_raw_directive = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                body,
                evidence_from_text("valid-raw-directive", valid_with_raw_directive_text),
            ],
        )
        self.assertTrue(valid.success, valid.metadata["issues"])
        self.assertTrue(
            valid_with_raw_directive.success,
            valid_with_raw_directive.metadata["issues"],
        )
        for label, artifact_text in forgeries.items():
            with self.subTest(forgery=label):
                result = verify_pb_migration_sp_generation_contract(
                    sql,
                    source_evidence=[body, evidence_from_text(label, artifact_text)],
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "csharp_caller_target_procedure_mismatch",
                    {item["code"] for item in result.metadata["issues"]},
                )

    def test_csharp_caller_rejects_nested_arguments_unknown_symbols_and_global_imbalance(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")

        def evidence_from_text(name, artifact_text):
            artifact_text = complete_csharp_caller_artifact(artifact_text)
            path, digest = write_test_artifact(name, artifact_text)
            return {
                "kind": "csharp_call",
                "verified": True,
                "path": str(path),
                "definition_text": artifact_text,
                "sha256": digest,
                "db_parameters": ["@WORKTYPE"],
                "target_procedure": "SP_ZX123456_SELECT",
            }

        invalid_artifacts = {
            "nested_lambda": '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new Func<DbParameter>(() => new DbParameter("@WORKTYPE", value))
);''',
            "nested_array": '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new[] { new DbParameter("@WORKTYPE", value) }
);''',
            "unknown_symbol_else": '''#if FEATURE_X
return null;
#else
return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", value)
);
#endif''',
            "globally_unbalanced": '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", value)
);
if (enabled) {''',
        }
        literal_false_else = '''#if false
return null;
#else
return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", value)
);
#endif'''
        literal_result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                body,
                evidence_from_text("literal-false-else", literal_false_else),
            ],
        )
        self.assertTrue(literal_result.success, literal_result.metadata["issues"])

        for label, artifact_text in invalid_artifacts.items():
            with self.subTest(case=label):
                result = verify_pb_migration_sp_generation_contract(
                    sql,
                    source_evidence=[body, evidence_from_text(label, artifact_text)],
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "csharp_caller_target_procedure_mismatch",
                    {item["code"] for item in result.metadata["issues"]},
                )

    def test_csharp_caller_value_expression_grammar_is_fail_closed(self):
        parameters = [
            "@WORKTYPE",
            "@ORGDIV",
            "@ITEMCD",
            "@SELECTTYPE",
            "@CUSTCD",
            "@OPTION",
            "@GIJUNDT",
        ]
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE  VARCHAR(20)
    , @ORGDIV    VARCHAR(2)
    , @ITEMCD    VARCHAR(30)
    , @SELECTTYPE VARCHAR(20)
    , @CUSTCD    VARCHAR(20)
    , @OPTION    VARCHAR(20)
    , @GIJUNDT   VARCHAR(8)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")

        def evidence_from_text(name, artifact_text, expected_parameters):
            artifact_text = complete_csharp_caller_artifact(artifact_text)
            path, digest = write_test_artifact(name, artifact_text)
            return {
                "kind": "csharp_call",
                "verified": True,
                "path": str(path),
                "definition_text": artifact_text,
                "sha256": digest,
                "db_parameters": list(expected_parameters),
                "target_procedure": "SP_ZX123456_SELECT",
            }

        realistic = '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
    , new DbParameter("@ORGDIV", userInfo.Orgdiv)
    , new DbParameter("@ITEMCD", row["ITEMCD"])
    , new DbParameter("@SELECTTYPE", _selectType.ToString())
    , new DbParameter("@CUSTCD", (string)row["CUSTCD"])
    , new DbParameter("@OPTION", _option ?? string.Empty)
    , new DbParameter("@GIJUNDT", ymdGIJUN.YYYYMMDD())
);'''
        accepted = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                body,
                evidence_from_text("realistic-values", realistic, parameters),
            ],
        )
        self.assertTrue(accepted.success, accepted.metadata["issues"])

        single_parameter_sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        invalid_values = {
            "lambda": "() => value",
            "async_lambda": "async () => value",
            "delegate": "delegate { return value; }",
            "array_creation": "new[] { value }",
            "collection_expression": "[value]",
            "object_initializer": "new Holder { Value = value }",
            "collection_initializer": "new List<string> { value }",
            "conditional": "flag ? left : right",
        }
        for label, value_expression in invalid_values.items():
            artifact_text = (
                'return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"\n'
                f'    , new DbParameter("@WORKTYPE", {value_expression})\n'
                ');'
            )
            with self.subTest(value_expression=label):
                result = verify_pb_migration_sp_generation_contract(
                    single_parameter_sql,
                    source_evidence=[
                        body,
                        evidence_from_text(label, artifact_text, ["@WORKTYPE"]),
                    ],
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "csharp_caller_target_procedure_mismatch",
                    {item["code"] for item in result.metadata["issues"]},
                )

    def test_csharp_caller_requires_one_direct_method_body_call(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")

        def evidence_from_text(name, artifact_text):
            path, digest = write_test_artifact(name, artifact_text)
            return {
                "kind": "csharp_call",
                "verified": True,
                "path": str(path),
                "definition_text": artifact_text,
                "sha256": digest,
                "db_parameters": ["@WORKTYPE"],
                "target_procedure": "SP_ZX123456_SELECT",
            }

        valid_method = complete_csharp_caller_artifact(
            '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);'''
        )
        accepted = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[body, evidence_from_text("direct-method", valid_method)],
        )
        self.assertTrue(accepted.success, accepted.metadata["issues"])

        invalid_contexts = {
            "bare_fragment": '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);''',
            "top_level_local_function": '''private DataSet LocalLoad()
{
    return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
        , new DbParameter("@WORKTYPE", workType)
    );
}''',
            "expression_lambda": '''Func<DataSet> load = () => dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);''',
            "block_lambda": '''Func<DataSet> load = () =>
{
    return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
        , new DbParameter("@WORKTYPE", workType)
    );
};''',
            "anonymous_delegate": '''Func<DataSet> load = delegate
{
    return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
        , new DbParameter("@WORKTYPE", workType)
    );
};''',
            "local_function": '''private DataSet LoadRows()
{
    DataSet LocalLoad()
    {
        return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
            , new DbParameter("@WORKTYPE", workType)
        );
    }

    return LocalLoad();
}''',
            "mixed_correct_and_wrong": '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);
dbClient.ExecSP("SP_OTHER_SAVE"
    , new DbParameter("@WORKTYPE", workType)
);''',
            "whitespace_comment_second_unsupported_call": '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);
dbClient /* count every active receiver call */
    . ExecuteOther();''',
            "constructor": '''public sealed class CallerEvidence
{
    public CallerEvidence()
    {
        dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
            , new DbParameter("@WORKTYPE", workType)
        );
    }
}''',
            "static_constructor": '''public sealed class CallerEvidence
{
    static CallerEvidence()
    {
        dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
            , new DbParameter("@WORKTYPE", workType)
        );
    }
}''',
            "destructor": '''public sealed class CallerEvidence
{
    ~CallerEvidence()
    {
        dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
            , new DbParameter("@WORKTYPE", workType)
        );
    }
}''',
            "operator": '''public sealed class CallerEvidence
{
    public static object operator +(CallerEvidence left, CallerEvidence right)
    {
        return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
            , new DbParameter("@WORKTYPE", workType)
        );
    }
}''',
            "conversion_operator": '''public sealed class CallerEvidence
{
    public static implicit operator object(CallerEvidence value)
    {
        return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
            , new DbParameter("@WORKTYPE", workType)
        );
    }
}''',
            "accessor": '''public sealed class CallerEvidence
{
    public object Value
    {
        get
        {
            return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
                , new DbParameter("@WORKTYPE", workType)
            );
        }
    }
}''',
        }
        for label in {
            "expression_lambda",
            "block_lambda",
            "anonymous_delegate",
            "local_function",
            "mixed_correct_and_wrong",
            "whitespace_comment_second_unsupported_call",
        }:
            invalid_contexts[label] = complete_csharp_caller_artifact(
                invalid_contexts[label]
            )
        for label, artifact_text in invalid_contexts.items():
            with self.subTest(context=label):
                result = verify_pb_migration_sp_generation_contract(
                    sql,
                    source_evidence=[body, evidence_from_text(label, artifact_text)],
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "csharp_caller_target_procedure_mismatch",
                    {item["code"] for item in result.metadata["issues"]},
                )

    def test_csharp_caller_counts_conditional_parenthesized_and_interpolated_invocations(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")

        def evidence_from_text(name, artifact_text):
            path, digest = write_test_artifact(name, artifact_text)
            return {
                "kind": "csharp_call",
                "verified": True,
                "path": str(path),
                "definition_text": artifact_text,
                "sha256": digest,
                "db_parameters": ["@WORKTYPE"],
                "target_procedure": "SP_ZX123456_SELECT",
            }

        positive_calls = {
            "conditional_receiver": '''return dbClient?.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);''',
            "parenthesized_null_forgiving_receiver": '''return ((dbClient!)).GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);''',
            "interpolated_literal_is_not_a_call": '''string label = $"dbClient.ExecuteOther()";
return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);''',
        }
        for label, call_text in positive_calls.items():
            with self.subTest(valid_receiver=label):
                artifact = complete_csharp_caller_artifact(call_text)
                result = verify_pb_migration_sp_generation_contract(
                    sql,
                    source_evidence=[body, evidence_from_text(label, artifact)],
                )
                self.assertTrue(result.success, result.metadata["issues"])

        second_calls = {
            "interpolated_expression": '''string audit = $"{dbClient.ExecuteOther()}";
return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);''',
            "conditional_receiver": '''dbClient /* conditional */ ? . ExecuteOther();
return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);''',
            "parenthesized_null_forgiving_receiver": '''((dbClient /* receiver */ !)) . ExecuteOther();
return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);''',
        }
        for label, method_body in second_calls.items():
            with self.subTest(hidden_second_call=label):
                artifact = complete_csharp_caller_artifact(method_body)
                result = verify_pb_migration_sp_generation_contract(
                    sql,
                    source_evidence=[body, evidence_from_text(label, artifact)],
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "csharp_caller_target_procedure_mismatch",
                    {item["code"] for item in result.metadata["issues"]},
                )

    def test_csharp_caller_requires_plausible_ordinary_method_return_type(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")
        call_return = '''return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);'''

        def artifact(return_type, *, returns=True):
            call = call_return if returns else call_return.replace("return ", "", 1)
            return f'''public sealed class CallerEvidence
{{
    private {return_type} Execute()
    {{
{call}
    }}
}}'''

        def evidence_from_text(name, artifact_text):
            path, digest = write_test_artifact(name, artifact_text)
            return {
                "kind": "csharp_call",
                "verified": True,
                "path": str(path),
                "definition_text": artifact_text,
                "sha256": digest,
                "db_parameters": ["@WORKTYPE"],
                "target_procedure": "SP_ZX123456_SELECT",
            }

        valid_return_types = {
            "void": ("void", False),
            "builtin": ("object", True),
            "qualified": ("System.Data.DataSet", True),
            "generic": ("System.Threading.Tasks.Task<System.Data.DataSet>", True),
            "nullable": ("System.Data.DataSet?", True),
            "array": ("System.Data.DataSet[]", True),
            "tuple": ("(System.Data.DataSet Rows, int Count)", True),
        }
        for label, (return_type, returns) in valid_return_types.items():
            with self.subTest(valid_return_type=label):
                source = artifact(return_type, returns=returns)
                result = verify_pb_migration_sp_generation_contract(
                    sql,
                    source_evidence=[body, evidence_from_text(label, source)],
                )
                self.assertTrue(result.success, result.metadata["issues"])

        for return_type in ("return", "if", "while", "throw", "private"):
            with self.subTest(invalid_return_type=return_type):
                source = artifact(return_type)
                result = verify_pb_migration_sp_generation_contract(
                    sql,
                    source_evidence=[body, evidence_from_text(return_type, source)],
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "csharp_caller_target_procedure_mismatch",
                    {item["code"] for item in result.metadata["issues"]},
                )

    def test_trace_v2_preserves_procedure_and_control_arm_braces(self):
        source = sp_metadata_header() + """ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT @WORKTYPE AS WORKTYPE;
    END
    ELSE
    BEGIN
        UPDATE ZX902T SET WORKTYPE = @WORKTYPE;
    END;
END;
"""
        exact_candidate = source.replace(
            "ALTER PROCEDURE", "CREATE OR ALTER PROCEDURE", 1
        )
        without_procedure_braces = exact_candidate.replace(
            "AS\nBEGIN\n    IF", "AS\n    IF", 1
        ).rsplit("\nEND;", 1)[0] + "\n"
        without_arm_braces = exact_candidate.replace(
            "    BEGIN\n        SELECT @WORKTYPE AS WORKTYPE;\n    END\n    ELSE\n    BEGIN\n        UPDATE ZX902T SET WORKTYPE = @WORKTYPE;\n    END;",
            "        SELECT @WORKTYPE AS WORKTYPE;\n    ELSE\n        UPDATE ZX902T SET WORKTYPE = @WORKTYPE;",
        )
        complete_source = existing_sp_evidence(
            source,
            object_name="SP_ZX123456_SELECT",
        )
        caller = csharp_call_evidence(["@WORKTYPE"])

        exact = verify_pb_migration_sp_generation_contract(
            exact_candidate,
            source_evidence=[complete_source, caller],
        )
        self.assertTrue(exact.success, exact.metadata["issues"])

        for label, candidate in {
            "procedure_braces_removed": without_procedure_braces,
            "control_arm_braces_removed": without_arm_braces,
        }.items():
            with self.subTest(structural_removal=label):
                result = verify_pb_migration_sp_generation_contract(
                    candidate,
                    source_evidence=[complete_source, caller],
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "candidate_body_not_covered_by_single_authority",
                    {item["code"] for item in result.metadata["issues"]},
                )

        generated_wrapper = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        wrapper_result = verify_pb_migration_sp_generation_contract(
            generated_wrapper,
            source_evidence=[
                pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;"),
                caller,
            ],
        )
        self.assertTrue(wrapper_result.success, wrapper_result.metadata["issues"])

    def test_body_authority_requires_exhaustive_full_trace_equality(self):
        complete_body = """SELECT @WORKTYPE AS WORKTYPE;
UPDATE ZX902T SET WORKTYPE = @WORKTYPE;
"""
        candidate = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        source = bound_source_evidence(
            "pb_srd_sql",
            complete_body,
            artifact_name="exhaustive-source-select-update",
        )
        caller = csharp_call_evidence(["@WORKTYPE"])

        source_subset = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[source, caller],
        )
        self.assertFalse(source_subset.success)
        self.assertIn(
            "candidate_body_not_covered_by_single_authority",
            {item["code"] for item in source_subset.metadata["issues"]},
        )

        composite_subset = composite_contract_evidence(
            candidate,
            [source["sha256"]],
            artifact_name="exhaustive-composite-subset",
        )
        composite_result = verify_pb_migration_sp_generation_contract(
            candidate,
            source_evidence=[source, caller, composite_subset],
        )
        self.assertFalse(composite_result.success)
        self.assertIn(
            "composite_contract_source_trace_mismatch",
            {item["code"] for item in composite_result.metadata["issues"]},
        )

    def test_csharp_caller_counts_verbatim_and_nested_literal_interpolation_calls(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")

        def evidence_from_text(name, method_body):
            artifact_text = complete_csharp_caller_artifact(method_body)
            path, digest = write_test_artifact(name, artifact_text)
            return {
                "kind": "csharp_call",
                "verified": True,
                "path": str(path),
                "definition_text": artifact_text,
                "sha256": digest,
                "db_parameters": ["@WORKTYPE"],
                "target_procedure": "SP_ZX123456_SELECT",
            }

        cases = {
            "verbatim_method_identifier": '''dbClient.@ExecuteOther();
return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);''',
            "interpolation_nested_char_literal": '''string audit = $"{Format('}', dbClient.ExecuteOther())}";
return dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", workType)
);''',
        }
        for label, method_body in cases.items():
            with self.subTest(hidden_call=label):
                result = verify_pb_migration_sp_generation_contract(
                    sql,
                    source_evidence=[body, evidence_from_text(label, method_body)],
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "csharp_caller_target_procedure_mismatch",
                    {item["code"] for item in result.metadata["issues"]},
                )

    def test_csharp_caller_rejects_illegal_void_and_var_return_types(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")

        def evidence_from_type(return_type):
            returns = return_type != "void"
            call = ('return ' if returns else '') + '''dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
        , new DbParameter("@WORKTYPE", workType)
    );'''
            artifact_text = f'''public sealed class CallerEvidence
{{
    private {return_type} Execute()
    {{
        {call}
    }}
}}'''
            path, digest = write_test_artifact(
                "invalid-return-" + re.sub(r"[^A-Za-z0-9]+", "-", return_type),
                artifact_text,
            )
            return {
                "kind": "csharp_call",
                "verified": True,
                "path": str(path),
                "definition_text": artifact_text,
                "sha256": digest,
                "db_parameters": ["@WORKTYPE"],
                "target_procedure": "SP_ZX123456_SELECT",
            }

        for return_type in (
            "var",
            "void?",
            "void[]",
            "System.Threading.Tasks.Task<void>",
            "(void Value, int Count)",
        ):
            with self.subTest(invalid_return_type=return_type):
                result = verify_pb_migration_sp_generation_contract(
                    sql,
                    source_evidence=[body, evidence_from_type(return_type)],
                )
                self.assertFalse(result.success)
                self.assertIn(
                    "csharp_caller_target_procedure_mismatch",
                    {item["code"] for item in result.metadata["issues"]},
                )

    def test_malformed_procedure_identity_is_rejected_before_normalization(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")
        malformed_csharp = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                body,
                csharp_call_evidence(
                    ["@WORKTYPE"],
                    target_procedure="DBO..SP_ZX123456_SELECT",
                ),
            ],
        )
        malformed_external = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                body,
                external_caller_evidence(
                    [{"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"}],
                    target_procedure="DBO..SP_ZX123456_SELECT",
                ),
            ],
        )

        self.assertFalse(malformed_csharp.success)
        self.assertIn(
            "csharp_caller_target_procedure_invalid",
            {item["code"] for item in malformed_csharp.metadata["issues"]},
        )
        self.assertFalse(malformed_external.success)
        self.assertIn(
            "external_caller_target_procedure_invalid",
            {item["code"] for item in malformed_external.metadata["issues"]},
        )

    def test_caller_evidence_must_bind_exact_target_procedure(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")
        wrong_csharp = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                body,
                csharp_call_evidence(
                    ["@WORKTYPE"],
                    target_procedure="SP_OTHER_SELECT",
                ),
            ],
        )
        wrong_schema_csharp = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                body,
                csharp_call_evidence(
                    ["@WORKTYPE"],
                    target_procedure="OTHER.SP_ZX123456_SELECT",
                ),
            ],
        )
        declared_target_but_wrong_artifact = csharp_call_evidence(["@WORKTYPE"])
        wrong_artifact_text = declared_target_but_wrong_artifact["definition_text"].replace(
            "SP_ZX123456_SELECT",
            "SP_OTHER_SELECT",
        )
        wrong_artifact_path, wrong_artifact_hash = write_test_artifact(
            "csharp-wrong-target-call",
            wrong_artifact_text,
        )
        declared_target_but_wrong_artifact["definition_text"] = wrong_artifact_text
        declared_target_but_wrong_artifact["path"] = str(wrong_artifact_path)
        declared_target_but_wrong_artifact["sha256"] = wrong_artifact_hash
        wrong_csharp_artifact = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[body, declared_target_but_wrong_artifact],
        )
        raw_string_spoof = csharp_call_evidence(["@WORKTYPE"])
        raw_string_spoof_text = '''string sample = """dbClient.GetDataSetFromSP("SP_ZX123456_SELECT"
    , new DbParameter("@WORKTYPE", value)
);""";
return dbClient.GetDataSetFromSP("SP_OTHER_SELECT"
    , new DbParameter("@WORKTYPE", value)
);'''
        raw_string_spoof_path, raw_string_spoof_hash = write_test_artifact(
            "csharp-raw-string-spoof",
            raw_string_spoof_text,
        )
        raw_string_spoof["definition_text"] = raw_string_spoof_text
        raw_string_spoof["path"] = str(raw_string_spoof_path)
        raw_string_spoof["sha256"] = raw_string_spoof_hash
        raw_string_spoof_result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[body, raw_string_spoof],
        )
        missing_csharp_target = csharp_call_evidence(["@WORKTYPE"])
        missing_csharp_target.pop("target_procedure")
        missing_csharp_result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[body, missing_csharp_target],
        )
        missing_external_declaration = external_caller_evidence(
            [{"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"}],
        )
        missing_external_declaration.pop("target_procedure")
        missing_declaration_result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[body, missing_external_declaration],
        )
        missing_external_artifact = external_caller_evidence(
            [{"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"}],
        )
        missing_payload = json.loads(missing_external_artifact["artifact_text"])
        missing_payload.pop("target_procedure")
        missing_external_artifact["artifact_text"] = json.dumps(
            missing_payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        missing_path, missing_hash = write_test_artifact(
            "external-missing-target",
            missing_external_artifact["artifact_text"],
        )
        missing_external_artifact["path"] = str(missing_path)
        missing_external_artifact["sha256"] = missing_hash
        missing_artifact_result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[body, missing_external_artifact],
        )
        wrong_external = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                body,
                external_caller_evidence(
                    [{"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"}],
                    target_procedure="SP_OTHER_SELECT",
                ),
            ],
        )
        declared_target_but_wrong_external_artifact = external_caller_evidence(
            [{"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"}],
        )
        wrong_external_payload = json.loads(
            declared_target_but_wrong_external_artifact["artifact_text"]
        )
        wrong_external_payload["target_procedure"] = "SP_OTHER_SELECT"
        wrong_external_text = json.dumps(
            wrong_external_payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        wrong_external_path, wrong_external_hash = write_test_artifact(
            "external-wrong-target-artifact",
            wrong_external_text,
        )
        declared_target_but_wrong_external_artifact["artifact_text"] = wrong_external_text
        declared_target_but_wrong_external_artifact["path"] = str(wrong_external_path)
        declared_target_but_wrong_external_artifact["sha256"] = wrong_external_hash
        wrong_external_artifact = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[body, declared_target_but_wrong_external_artifact],
        )

        self.assertIn(
            "csharp_caller_target_procedure_mismatch",
            {item["code"] for item in wrong_csharp.metadata["issues"]},
        )
        self.assertIn(
            "csharp_caller_target_procedure_mismatch",
            {item["code"] for item in wrong_schema_csharp.metadata["issues"]},
        )
        self.assertIn(
            "csharp_caller_target_procedure_mismatch",
            {item["code"] for item in wrong_csharp_artifact.metadata["issues"]},
        )
        self.assertIn(
            "csharp_caller_target_procedure_mismatch",
            {item["code"] for item in raw_string_spoof_result.metadata["issues"]},
        )
        self.assertIn(
            "csharp_caller_target_procedure_missing",
            {item["code"] for item in missing_csharp_result.metadata["issues"]},
        )
        self.assertIn(
            "external_caller_target_procedure_missing",
            {item["code"] for item in missing_declaration_result.metadata["issues"]},
        )
        self.assertIn(
            "external_caller_target_procedure_missing",
            {item["code"] for item in missing_artifact_result.metadata["issues"]},
        )
        self.assertIn(
            "external_caller_target_procedure_mismatch",
            {item["code"] for item in wrong_external.metadata["issues"]},
        )
        self.assertIn(
            "external_caller_target_procedure_mismatch",
            {item["code"] for item in wrong_external_artifact.metadata["issues"]},
        )

    def test_sp_parameter_options_ignore_output_and_readonly_inside_string_defaults(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @FILTER_TEXT NVARCHAR(50) = N'A OUTPUT READONLY B'
    , @ROWS DBO.ROWTYPE READONLY
    , @ROWCOUNT INT OUTPUT
AS
BEGIN
    SELECT @FILTER_TEXT AS FILTER_TEXT;
END;
"""
        contract = pb_migration._extract_sp_parameter_contract(sql)

        self.assertEqual("N'A OUTPUT READONLY B'", contract[0]["default"])
        self.assertFalse(contract[0]["output"])
        self.assertFalse(contract[0]["readonly"])
        self.assertTrue(contract[1]["readonly"])
        self.assertTrue(contract[2]["output"])

    def test_caller_evidence_cannot_claim_unobserved_metadata_or_mismatched_identity(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        body_evidence = pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;")
        csharp_overclaim = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                body_evidence,
                csharp_call_evidence(
                    ["@WORKTYPE"],
                    parameter_contract=[
                        {
                            "name": "@WORKTYPE",
                            "type_spec": "VARCHAR(20)",
                            "default": "NULL",
                            "output": True,
                        }
                    ],
                ),
            ],
        )
        mismatched_external = external_caller_evidence(
            [{"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"}],
            caller_id="artifact-caller",
        )
        mismatched_external["caller_id"] = "declared-caller"
        external_result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[body_evidence, mismatched_external],
        )

        self.assertIn(
            "csharp_caller_parameter_metadata_not_proven_by_artifact",
            {item["code"] for item in csharp_overclaim.metadata["issues"]},
        )
        self.assertIn(
            "external_caller_id_mismatch",
            {item["code"] for item in external_result.metadata["issues"]},
        )

    def test_sp_metadata_header_accepts_normal_ssms_object_preamble(self):
        sql = """USE [C_SAMPLE]
GO
/****** Object: StoredProcedure [dbo].[SP_ZX123456_SELECT] Script Date: 2026-07-23 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
-- =============================================
-- DESCRIPTION: Synthetic procedure contract
-- =============================================
CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        result = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[
                pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;"),
                csharp_call_evidence(["@WORKTYPE"]),
            ],
        )

        self.assertTrue(result.success, result.metadata["issues"])

    def test_pb_sql_emission_uses_actual_provider_guard_and_final_response_binder(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            provider_path = Path(temp_dir) / "skills" / "sql-formatting" / "SKILL.md"
            provider_path.parent.mkdir(parents=True)
            provider_path.write_text(
                """---
name: sql-formatting
description: Format SQL/T-SQL while preserving query behavior and semantics.
---

# SQL Formatting

Do not change query behavior. Preserve table names, predicates, expressions, and results.
Convert a scalar lookup to a JOIN only when its implementation and relational equivalence are verified.
Run the packaged `sql-formatting-style-harness` deterministic verifier and accept output only when it passes.
""",
                encoding="utf-8",
            )
            selection = sql_provider_selection(provider_path, source="host-local-skill")
            passed = _verify_pb_migration_sp_with_sql_formatting(
                sql,
                sql,
                source_evidence=[
                    pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;"),
                    csharp_call_evidence(["@WORKTYPE"]),
                ],
                profile_evidence=loaded_sp_test_profile(),
                draft_final_response=sql_final_response(sql),
                sql_provider_path=provider_path,
                selected_active_sql_provider_path=provider_path,
                sql_provider_selection=selection,
            )
            missing_response = _verify_pb_migration_sp_with_sql_formatting(
                sql,
                sql,
                source_evidence=[
                    pb_srd_sql_evidence("SELECT @WORKTYPE AS WORKTYPE;"),
                    csharp_call_evidence(["@WORKTYPE"]),
                ],
                profile_evidence=loaded_sp_test_profile(),
                draft_final_response="",
                sql_provider_path=provider_path,
                selected_active_sql_provider_path=provider_path,
                sql_provider_selection=selection,
            )

        self.assertTrue(passed.success, passed.to_dict())
        binding = passed.metadata["sql_final_response_binding"]
        release = passed.metadata["sql_final_response_release"]
        self.assertEqual("passed", release["status"])
        self.assertEqual("bound", release["binding"]["status"])
        self.assertEqual("bound", binding["status"])
        self.assertEqual(binding, release["binding"])
        self.assertEqual("accepted", release["provider_path_guard"]["status"])
        self.assertEqual(
            release["provider_path_guard"]["provider_selection_sha256"],
            sql_provider_selection_sha256(selection),
        )
        self.assertEqual(
            release["verification"]["metadata"]["verification_id"],
            binding["verification_id"],
        )
        self.assertEqual(
            hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            binding["formatted_sha256"],
        )
        self.assertFalse(missing_response.success)
        self.assertEqual(
            "sql_final_response_missing",
            missing_response.metadata["sql_final_response_binding"]["code"],
        )

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
            source_evidence=[
                pb_srd_sql_evidence(
                    """SELECT A.RECORD_ID
FROM SYNTHETIC_RECORDS A
WHERE A.SCOPE_CODE = @SCOPE_CODE;"""
                ),
                csharp_call_evidence(["@WORKTYPE", "@SCOPE_CODE"]),
            ],
        )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["sp_generation_contract"]["status"], "passed")
        self.assertEqual(result.metadata["sql_formatting_style"]["status"], "passed")
        self.assertEqual(result.metadata["sql_final_response_binding"]["status"], "bound")
        self.assertEqual(result.metadata["sql_final_response_release"]["status"], "passed")
        self.assertEqual(
            result.metadata["sql_final_response_release"]["binding"]["status"],
            "bound",
        )
        self.assertEqual(
            result.metadata["sql_final_response_binding"],
            result.metadata["sql_final_response_release"]["binding"],
        )

    def test_composed_sp_and_sql_formatting_verifier_passes_alias_plan_kwargs(self):
        sql = sp_metadata_header() + """CREATE OR ALTER PROCEDURE [DBO].[SP_ZX123456_SELECT]
      @WORKTYPE    VARCHAR(20) = NULL
    , @SCOPE_CODE      VARCHAR(2)  = NULL
AS
BEGIN
    SELECT A.RECORD_ID
         , B.DETAIL_STATUS
    FROM SYNTHETIC_RECORDS A
        LEFT OUTER JOIN SYNTHETIC_DETAILS B
                     ON A.RECORD_ID = B.RECORD_ID
    WHERE A.SCOPE_CODE = @SCOPE_CODE;
END
"""
        alias_plan = approved_alias_role_plan()
        with mock.patch(
            "src.skills.sql_formatting_provider.verify_sql_formatting_style",
            return_value=passed_sql_formatting_result(sql, sql),
        ) as formatting:
            result = verify_pb_migration_sp_with_sql_formatting(
                sql,
                sql,
                source_evidence=[
                    pb_srd_sql_evidence(
                        """SELECT A.RECORD_ID
     , B.DETAIL_STATUS
FROM SYNTHETIC_RECORDS A
    LEFT OUTER JOIN SYNTHETIC_DETAILS B
                 ON A.RECORD_ID = B.RECORD_ID
WHERE A.SCOPE_CODE = @SCOPE_CODE;"""
                    ),
                    csharp_call_evidence(["@WORKTYPE", "@SCOPE_CODE"]),
                ],
                alias_role_plan=alias_plan,
                sql_formatting_verifier_kwargs={"operation": "formatting"},
            )

        self.assertTrue(result.success, result.to_dict())
        formatting.assert_called_once()
        self.assertIs(formatting.call_args.kwargs["alias_role_plan"], alias_plan)
        self.assertEqual(formatting.call_args.kwargs["operation"], "formatting")
        self.assertEqual(formatting.call_args.kwargs["cte_temp_table_reason"], "")

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
