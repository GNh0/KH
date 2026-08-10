import hashlib
import json
import re
import sys
from pathlib import Path


SKILL_NAME = "pb-to-csharp-migration-harness"
CONTRACT_ID = "pb-csharp-offline-generalized"


def _write_utf8_artifact(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8", newline="")
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _complete_csharp_caller_artifact(method_body: str) -> str:
    return f"""public sealed class CallerEvidence
{{
    private object Execute()
    {{
{method_body}
    }}
}}
"""


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src").is_dir() and (parent / "skills").is_dir():
            return parent
    raise RuntimeError("repository root not found")


def _load_contract() -> dict:
    contract_path = Path(__file__).resolve().parents[1] / "references" / "packaged-style-contract.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    normal_generation = payload.get("normal_generation", {})
    if payload.get("contract_id") != CONTRACT_ID:
        raise RuntimeError("packaged style contract is missing or incompatible")
    if normal_generation.get("profile_source") != "packaged-only":
        raise RuntimeError("demo requires the packaged-only normal-generation profile")
    if normal_generation.get("external_discovery_allowed") is not False:
        raise RuntimeError("normal-generation discovery must be disabled")
    if normal_generation.get("profile_update_runs_during_normal_generation") is not False:
        raise RuntimeError("profile-update workflow must be disabled during normal generation")
    return payload


def _csharp_demo() -> str:
    return """using System;
using System.Data;
using System.Windows.Forms;

namespace SyntheticMigration
{
    public partial class CatalogBrowseForm : Form
    {
        public CatalogBrowseForm()
        {
            InitializeComponent();
        }

        private void btnSearch_Click(object sender, EventArgs e)
        {
            CallSelectProcedure();
        }

        private void CallSelectProcedure()
        {
            DataTable result = new DataTable();
            grdList.DataSource = result;
        }
    }
}
"""


def _designer_demo(plan) -> str:
    metadata = plan.metadata
    body_sections = [
        metadata["initializers"],
        metadata["add_range"],
        metadata["grid_wiring"],
        metadata["view_defaults"],
        metadata["repository_registration"],
        metadata["repository_assignments"],
        metadata["assignments"],
    ]
    declarations = "\n        ".join(metadata["declarations"])
    statements = "\n\n".join(
        "\n".join(f"            {line}" for line in section)
        for section in body_sections
        if section
    )
    return f"""namespace SyntheticMigration
{{
    partial class CatalogBrowseForm
    {{
        {declarations}

        private void InitializeComponent()
        {{
{statements}
        }}
    }}
}}
"""


def _sql_demo() -> str:
    return """-- =============================================
-- AUTHOR:      KH demo
-- CREATE DATE: 2026-01-01
-- DESCRIPTION: Browse synthetic catalog rows
-- =============================================
CREATE OR ALTER PROCEDURE [dbo].[SP_CATALOG_SELECT]
      @WORKTYPE       VARCHAR(20) = NULL
    , @FILTER_TEXT    NVARCHAR(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT A.ENTITY_ID
             , A.DISPLAY_NAME
        FROM [dbo].[ENTITY_RECORD] A
        WHERE A.DISPLAY_NAME LIKE ISNULL(@FILTER_TEXT, N'') + N'%';
    END;
END;
"""


def _validate_csharp_structure(contract: dict, source: str) -> dict:
    required = contract["rules"]["csharp"]["required_patterns"]
    matched = []
    missing = []
    for item in required:
        if re.search(item["pattern"], source, flags=re.IGNORECASE | re.MULTILINE):
            matched.append(item["id"])
        else:
            missing.append(item["id"])
    return {
        "status": "passed" if not missing else "failed",
        "success": not missing,
        "matched_pattern_ids": matched,
        "missing_pattern_ids": missing,
        "rule_group": "csharp.required_patterns",
    }


def _validate_designer_ownership(contract: dict, code_behind: str) -> dict:
    patterns = contract["designer_ownership"]["code_behind_static_ui_patterns"]
    misplaced_fixture = """
this.txtFilterText = new DevExpress.XtraEditors.TextEdit();
this.txtFilterText.Name = "txtFilterText";
this.gvwList.Columns.AddRange(this.colList_ENTITY_ID);
this.colList_ENTITY_ID.ColumnEdit = this.repEntity;
this.gvwList.OptionsView.ShowGroupPanel = false;
"""
    code_behind_matches = [
        item["id"]
        for item in patterns
        if re.search(item["pattern"], code_behind, flags=re.IGNORECASE | re.MULTILINE)
    ]
    rejected_fixture_matches = [
        item["id"]
        for item in patterns
        if re.search(item["pattern"], misplaced_fixture, flags=re.IGNORECASE | re.MULTILINE)
    ]
    expected_ids = [item["id"] for item in patterns]
    success = not code_behind_matches and rejected_fixture_matches == expected_ids
    return {
        "status": "passed" if success else "failed",
        "success": success,
        "default_owner": contract["designer_ownership"]["default_owner"],
        "code_behind_matches": code_behind_matches,
        "misplaced_fixture_matches": rejected_fixture_matches,
        "expected_pattern_ids": expected_ids,
    }


def _sanitized_offline_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> dict:
    from src.contracts import HarnessResult
    from src.skills import demo_scenarios
    from src.skills.pb_to_csharp_migration import (
        CompositeBusinessKeyDisplayObservation,
        CompositeBusinessKeyDisplaySpec,
        _canonical_nonwrapper_trace_sha256,
        build_composite_business_key_display_plan,
        build_csharp_grid_column_designer_plan,
        generate_devexpress_grid_xml,
        load_packaged_migration_profile,
        verify_composite_business_key_display_contract,
        verify_devexpress_grid_xml_contract,
        verify_migration_generated_csharp_style,
        verify_pb_migration_sp_generation_contract,
        verify_pb_migration_sp_with_sql_formatting,
    )
    from src.skills.sql_formatting_provider import (
        attach_sql_provider_selection_runtime_receipt,
    )

    contract = _load_contract()
    csharp = _csharp_demo()
    sql = _sql_demo()
    grid_columns = [
        {"field_name": "ENTITY_ID", "caption": "Entity", "data_type": "string"},
        {"field_name": "QUANTITY", "caption": "Quantity", "data_type": "decimal(18, 3)"},
    ]
    grid_plan = build_csharp_grid_column_designer_plan(
        grid_columns,
        input_format="list",
        result_fields=[item["field_name"] for item in grid_columns],
    )
    if not grid_plan.success:
        raise RuntimeError("synthetic DevExpress Designer generation failed")
    composite_display_plans = []
    for scenario_index, sequence_count in enumerate((1, 2, 4), start=1):
        base_field = f"KEYFIELD_{scenario_index}"
        sequence_fields = [
            f"SEQUENCEFIELD_{scenario_index}_{position}"
            for position in range(1, sequence_count + 1)
        ]
        display_field = f"DISPLAYFIELD_{scenario_index}"
        display_expression = base_field + "".join(
            f" + '-' + FORMAT({field_name}, '##0')"
            for field_name in sequence_fields
        )
        raw_fields = [base_field, *sequence_fields]
        composite_spec = CompositeBusinessKeyDisplaySpec(
            base_field=base_field,
            sequence_fields=sequence_fields,
            evidence_kind="user-supplied-contract",
            evidence_refs=["synthetic ordered key-value plus sequence contract"],
            display_field=display_field,
            display_caption="Composite key",
        )
        composite_plan = build_composite_business_key_display_plan(composite_spec)
        composite_contract = verify_composite_business_key_display_contract(
            composite_spec,
            CompositeBusinessKeyDisplayObservation(
                result_fields=[*raw_fields, display_field],
                display_expression=display_expression,
                display_alias=display_field,
                component_order=raw_fields,
                visible_grid_field=display_field,
                hidden_raw_fields=raw_fields,
                grid_caption="Composite key",
            ),
        )
        if not composite_plan.success or not composite_contract.success:
            raise RuntimeError("composite business-key display contract failed")
        composite_display_plans.append(composite_plan.metadata["plan"])
    designer = _designer_demo(grid_plan)
    grid_xml = generate_devexpress_grid_xml(grid_columns)
    csharp_path = output_dir / "CatalogBrowseForm.cs"
    designer_path = output_dir / "CatalogBrowseForm.Designer.cs"
    baseline_designer_path = output_dir / "CatalogBrowseForm.baseline.Designer.cs"
    unrelated_csharp_path = output_dir / "UnmappedWidget.cs"
    misplaced_csharp_path = output_dir / "CatalogBrowseForm.misplaced.cs"
    sql_path = output_dir / "SP_CATALOG_SELECT.sql"
    grid_xml_path = output_dir / "CatalogBrowseGrid.xml"
    evidence_path = output_dir / "offline_generation_evidence.json"
    unrelated_csharp = "public class UnmappedWidget {}"
    misplaced_csharp = csharp.replace(
        "InitializeComponent();",
        'InitializeComponent(); this.txtFilterText.Name = "txtFilterText";',
    )
    csharp_sha256 = _write_utf8_artifact(csharp_path, csharp)
    designer_sha256 = _write_utf8_artifact(designer_path, designer)
    baseline_designer_sha256 = _write_utf8_artifact(baseline_designer_path, designer)
    unrelated_csharp_sha256 = _write_utf8_artifact(
        unrelated_csharp_path,
        unrelated_csharp,
    )
    misplaced_csharp_sha256 = _write_utf8_artifact(
        misplaced_csharp_path,
        misplaced_csharp,
    )
    _write_utf8_artifact(grid_xml_path, grid_xml)
    evidence_registry = {
        "demo:generated-source": {
            "evidence_id": "demo:generated-source",
            "kind": "source",
            "locator": "artifact://demo/CatalogBrowseForm.cs",
            "sha256": csharp_sha256,
        },
        "demo:generated-designer": {
            "evidence_id": "demo:generated-designer",
            "kind": "source",
            "locator": "artifact://demo/CatalogBrowseForm.Designer.cs",
            "sha256": designer_sha256,
        },
        "demo:baseline-designer": {
            "evidence_id": "demo:baseline-designer",
            "kind": "source",
            "locator": "artifact://demo/CatalogBrowseForm.baseline.Designer.cs",
            "sha256": baseline_designer_sha256,
        },
        "demo:no-generated-controls": {
            "evidence_id": "demo:no-generated-controls",
            "kind": "user",
            "locator": "user://demo/no-generated-controls",
        },
    }
    control_contracts = [
        {
            "instance_name": "grdList",
            "expected_type": "DevExpress.XtraGrid.GridControl",
            "evidence_refs": ["demo:generated-designer"],
        },
        {
            "instance_name": "gvwList",
            "expected_type": "DevExpress.XtraGrid.Views.Grid.GridView",
            "evidence_refs": ["demo:generated-designer"],
        },
        {
            "instance_name": "colList_ENTITY_ID",
            "expected_type": "DevExpress.XtraGrid.Columns.GridColumn",
            "bindings": {"FieldName": "ENTITY_ID"},
            "evidence_refs": ["demo:generated-designer"],
        },
        {
            "instance_name": "colList_QUANTITY",
            "expected_type": "DevExpress.XtraGrid.Columns.GridColumn",
            "bindings": {"FieldName": "QUANTITY"},
            "evidence_refs": ["demo:generated-designer"],
        },
        {
            "instance_name": "rpsSpinAmt",
            "expected_type": (
                "DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit"
            ),
            "evidence_refs": ["demo:generated-designer"],
        },
    ]
    mapped = _validate_csharp_structure(contract, csharp)
    empty = _validate_csharp_structure(contract, "")
    unrelated = _validate_csharp_structure(contract, unrelated_csharp)
    ownership = _validate_designer_ownership(contract, csharp)
    if not mapped["success"] or empty["success"] or unrelated["success"] or not ownership["success"]:
        raise RuntimeError("packaged C# structural rules do not distinguish mapped output")

    contract_path = Path(__file__).resolve().parents[1] / "references" / "packaged-style-contract.json"
    profile_hash = "sha256:" + hashlib.sha256(contract_path.read_bytes()).hexdigest()
    profile = load_packaged_migration_profile(
        contract["contract_id"],
        contract["contract_version"],
        profile_hash,
    )
    runtime_mapped = verify_migration_generated_csharp_style(
        csharp,
        designer_source_text=designer,
        profile_evidence=profile,
        form_class="CatalogBrowseForm",
        source_role="code-behind",
        result_fields=[item["field_name"] for item in grid_columns],
        expected_control_contracts=control_contracts,
        evidence_registry=evidence_registry,
        target_source_path=str(csharp_path),
        target_source_sha256=csharp_sha256,
        target_designer_path=str(designer_path),
        target_designer_sha256=designer_sha256,
        baseline_designer_path=str(baseline_designer_path),
        baseline_designer_sha256=baseline_designer_sha256,
        expected_grid_role="list",
        expected_grid_suffix="List",
        expected_grid_columns=grid_columns,
        layout_load_artifact_path=str(grid_xml_path),
    )
    runtime_unrelated = verify_migration_generated_csharp_style(
        unrelated_csharp,
        profile_evidence=profile,
        form_class="CatalogBrowseForm",
        source_role="code-behind",
        expected_control_contracts=[],
        no_control_contract_evidence={
            "reason": "The unrelated negative fixture intentionally has no generated controls.",
            "evidence_refs": ["demo:no-generated-controls"],
        },
        evidence_registry=evidence_registry,
        target_source_path=str(unrelated_csharp_path),
        target_source_sha256=unrelated_csharp_sha256,
    )
    runtime_misplaced = verify_migration_generated_csharp_style(
        misplaced_csharp,
        designer_source_text=designer,
        profile_evidence=profile,
        form_class="CatalogBrowseForm",
        source_role="code-behind",
        result_fields=[item["field_name"] for item in grid_columns],
        expected_control_contracts=control_contracts,
        evidence_registry=evidence_registry,
        target_source_path=str(misplaced_csharp_path),
        target_source_sha256=misplaced_csharp_sha256,
        target_designer_path=str(designer_path),
        target_designer_sha256=designer_sha256,
        baseline_designer_path=str(baseline_designer_path),
        baseline_designer_sha256=baseline_designer_sha256,
    )
    caller_body = (
        'return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"\n'
        '    , new DbParameter("@WORKTYPE", workType)\n'
        '    , new DbParameter("@FILTER_TEXT", filterText)\n'
        ');'
    )
    caller_artifact = _complete_csharp_caller_artifact(caller_body)
    source_sql = """-- =============================================
-- AUTHOR:      KH demo
-- CREATE DATE: 2026-01-01
-- DESCRIPTION: Browse synthetic catalog rows
-- =============================================
CREATE OR ALTER PROCEDURE [dbo].[SP_CATALOG_SELECT]
      @FILTER_TEXT    NVARCHAR(100) = NULL
AS
BEGIN
    SELECT A.ENTITY_ID
         , A.DISPLAY_NAME
    FROM [dbo].[ENTITY_RECORD] A
    WHERE A.DISPLAY_NAME LIKE ISNULL(@FILTER_TEXT, N'') + N'%';
END;
"""
    source_artifact_path = output_dir / "catalog-pb-source-fragment.sql"
    caller_artifact_path = output_dir / "catalog-csharp-caller.txt"
    branch_contract_path = output_dir / "catalog-branch-contract.json"
    source_artifact_path.write_text(source_sql, encoding="utf-8")
    caller_artifact_path.write_text(caller_artifact, encoding="utf-8")
    branch_sql = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT A.ENTITY_ID
         , A.DISPLAY_NAME
    FROM [dbo].[ENTITY_RECORD] A
    WHERE A.DISPLAY_NAME LIKE ISNULL(@FILTER_TEXT, N'') + N'%';
END;"""
    branch_contract_text = json.dumps(
        {
            "target_procedure": "SP_CATALOG_SELECT",
            "branch_sql": branch_sql,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    branch_contract_path.write_text(branch_contract_text, encoding="utf-8")
    sql_provider_path = output_dir / "host-skills" / "sql-formatting" / "SKILL.md"
    sql_provider_path.parent.mkdir(parents=True, exist_ok=True)
    sql_provider_path.write_text(
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
    sql_provider_path = sql_provider_path.resolve()
    provider_selection = attach_sql_provider_selection_runtime_receipt({
        "schema_version": 1,
        "front_door_status": "ok",
        "host": "local-demo",
        "project": str(output_dir.resolve()),
        "provider_id": "sql-formatting",
        "provider_path": str(sql_provider_path),
        "selected_active_provider_path": str(sql_provider_path),
        "provider_source": "host-local-skill",
        "compatibility": "compatible",
        "selection_status": "selected",
        "plugin_route": {
            "route": "single",
            "controller": {
                "provider_id": "sql-formatting",
                "capability": "sql_formatting",
                "metadata": {
                    "path": str(sql_provider_path),
                    "source": "host-local-skill",
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
    body_evidence = {
        "kind": "pasted_sql",
        "verified": True,
        "evidence_role": "existing_procedure",
        "definition_path": str(source_artifact_path),
        "summary": "Synthetic offline PB catalog SELECT fragment",
        "definition_text": source_sql,
        "sha256": hashlib.sha256(source_sql.encode("utf-8")).hexdigest(),
        "program_description": "Browse synthetic catalog rows",
    }
    caller_evidence = {
        "kind": "csharp_call",
        "verified": True,
        "path": str(caller_artifact_path),
        "definition_text": caller_artifact,
        "sha256": hashlib.sha256(caller_artifact.encode("utf-8")).hexdigest(),
        "db_parameters": ["@WORKTYPE", "@FILTER_TEXT"],
        "target_procedure": "SP_CATALOG_SELECT",
    }
    branch_evidence = {
        "kind": "branch_contract",
        "verified": True,
        "target_procedure": "SP_CATALOG_SELECT",
        "path": str(branch_contract_path),
        "artifact_text": branch_contract_text,
        "sha256": hashlib.sha256(branch_contract_text.encode("utf-8")).hexdigest(),
        "branch_sql": branch_sql,
    }
    sp_contract = verify_pb_migration_sp_with_sql_formatting(
        sql,
        sql,
        source_evidence=[body_evidence, caller_evidence, branch_evidence],
        profile_evidence=profile,
        draft_final_response=f"```sql\n{sql}\n```",
        sql_provider_path=sql_provider_path,
        selected_active_sql_provider_path=sql_provider_path,
        sql_provider_selection=provider_selection,
    )
    unsupported_body_sql = sql.replace(
        "    WHERE A.DISPLAY_NAME LIKE ISNULL(@FILTER_TEXT, N'') + N'%';",
        """    WHERE A.DISPLAY_NAME LIKE ISNULL(@FILTER_TEXT, N'') + N'%';

    DELETE FROM [dbo].[ENTITY_RECORD];""",
    )
    unsupported_body_result = verify_pb_migration_sp_generation_contract(
        unsupported_body_sql,
        source_evidence=[body_evidence, caller_evidence, branch_evidence],
        profile_evidence=profile,
    )
    unbound_branch_result = verify_pb_migration_sp_generation_contract(
        sql,
        source_evidence=[body_evidence, caller_evidence],
        profile_evidence=profile,
    )

    branch_position_source_sql = """IF @WORKTYPE = 'LIST'
    BEGIN
        SELECT @FILTER_TEXT AS DISPLAY_NAME;
    END
    ELSE
    BEGIN
        DELETE FROM [dbo].[ENTITY_RECORD]
        WHERE DISPLAY_NAME = @FILTER_TEXT;
    END;
"""
    branch_position_valid_sql = """-- =============================================
-- DESCRIPTION: Generated branch-position candidate
-- =============================================
CREATE OR ALTER PROCEDURE [dbo].[SP_CATALOG_SELECT]
      @WORKTYPE       VARCHAR(20) = NULL
    , @FILTER_TEXT    NVARCHAR(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;

""" + branch_position_source_sql + """END;
"""
    branch_position_candidate_sql = branch_position_valid_sql.replace(
        "        SELECT @FILTER_TEXT AS DISPLAY_NAME;",
        "        __BRANCH_SWAP__",
    ).replace(
        "        DELETE FROM [dbo].[ENTITY_RECORD]\n"
        "        WHERE DISPLAY_NAME = @FILTER_TEXT;",
        "        SELECT @FILTER_TEXT AS DISPLAY_NAME;",
    ).replace(
        "        __BRANCH_SWAP__",
        "        DELETE FROM [dbo].[ENTITY_RECORD]\n"
        "        WHERE DISPLAY_NAME = @FILTER_TEXT;",
    )
    branch_position_source_path = output_dir / "catalog-branch-position-source.sql"
    branch_position_source_path.write_text(branch_position_source_sql, encoding="utf-8")
    branch_position_evidence = {
        "kind": "pasted_sql",
        "verified": True,
        "evidence_role": "body_fragment",
        "definition_path": str(branch_position_source_path),
        "definition_text": branch_position_source_sql,
        "sha256": hashlib.sha256(branch_position_source_sql.encode("utf-8")).hexdigest(),
    }
    branch_position_valid_result = verify_pb_migration_sp_generation_contract(
        branch_position_valid_sql,
        source_evidence=[branch_position_evidence, caller_evidence],
        profile_evidence=profile,
    )
    branch_position_swap_result = verify_pb_migration_sp_generation_contract(
        branch_position_candidate_sql,
        source_evidence=[branch_position_evidence, caller_evidence],
        profile_evidence=profile,
    )

    sibling_order_source_sql = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @FILTER_TEXT AS DISPLAY_NAME;

    IF @WORKTYPE = 'DELETE'
    BEGIN
        DELETE FROM [dbo].[ENTITY_RECORD]
        WHERE DISPLAY_NAME = @FILTER_TEXT;
    END;
END;
"""
    sibling_order_moved_sql = sibling_order_source_sql.replace(
        "    SELECT @FILTER_TEXT AS DISPLAY_NAME;\n\n"
        "    IF @WORKTYPE = 'DELETE'",
        "    IF @WORKTYPE = 'DELETE'",
    ).replace(
        "        WHERE DISPLAY_NAME = @FILTER_TEXT;\n"
        "    END;\nEND;",
        "        WHERE DISPLAY_NAME = @FILTER_TEXT;\n"
        "    END;\n\n"
        "    SELECT @FILTER_TEXT AS DISPLAY_NAME;\nEND;",
    )
    sibling_candidate_template = """-- =============================================
-- DESCRIPTION: Generated sibling-order candidate
-- =============================================
CREATE OR ALTER PROCEDURE [dbo].[SP_CATALOG_SELECT]
      @WORKTYPE       VARCHAR(20) = NULL
    , @FILTER_TEXT    NVARCHAR(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;

{body}END;
"""
    sibling_valid_sql = sibling_candidate_template.format(body=sibling_order_source_sql)
    sibling_moved_sql = sibling_candidate_template.format(body=sibling_order_moved_sql)
    sibling_source_path = output_dir / "catalog-sibling-order-source.sql"
    sibling_contract_path = output_dir / "catalog-sibling-order-contract.json"
    sibling_source_path.write_text(sibling_order_source_sql, encoding="utf-8")
    sibling_contract_text = json.dumps(
        {
            "target_procedure": "SP_CATALOG_SELECT",
            "branch_sql": sibling_order_source_sql,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    sibling_contract_path.write_text(sibling_contract_text, encoding="utf-8")
    sibling_source_evidence = {
        "kind": "pasted_sql",
        "verified": True,
        "evidence_role": "body_fragment",
        "definition_path": str(sibling_source_path),
        "definition_text": sibling_order_source_sql,
        "sha256": hashlib.sha256(sibling_order_source_sql.encode("utf-8")).hexdigest(),
    }
    sibling_branch_evidence = {
        "kind": "branch_contract",
        "verified": True,
        "target_procedure": "SP_CATALOG_SELECT",
        "path": str(sibling_contract_path),
        "artifact_text": sibling_contract_text,
        "sha256": hashlib.sha256(sibling_contract_text.encode("utf-8")).hexdigest(),
        "branch_sql": sibling_order_source_sql,
    }
    sibling_evidence = [
        sibling_source_evidence,
        caller_evidence,
        sibling_branch_evidence,
    ]
    sibling_order_valid_result = verify_pb_migration_sp_generation_contract(
        sibling_valid_sql,
        source_evidence=sibling_evidence,
        profile_evidence=profile,
    )
    sibling_order_swap_result = verify_pb_migration_sp_generation_contract(
        sibling_moved_sql,
        source_evidence=sibling_evidence,
        profile_evidence=profile,
    )

    splice_candidate_branch = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @FILTER_TEXT AS DISPLAY_NAME;
END
ELSE
BEGIN
    DELETE FROM [dbo].[ENTITY_RECORD]
    WHERE DISPLAY_NAME = @FILTER_TEXT;
END;
"""
    splice_source_a = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @FILTER_TEXT AS DISPLAY_NAME;
END;
"""
    splice_source_b = """IF @WORKTYPE = 'LIST'
BEGIN
    UPDATE [dbo].[ENTITY_RECORD]
    SET DISPLAY_NAME = N'OTHER'
    WHERE DISPLAY_NAME = @FILTER_TEXT;
END
ELSE
BEGIN
    DELETE FROM [dbo].[ENTITY_RECORD]
    WHERE DISPLAY_NAME = @FILTER_TEXT;
END;
"""
    splice_candidate_sql = sibling_candidate_template.format(body=splice_candidate_branch)
    splice_source_evidence = []
    for suffix, source_text in (("a", splice_source_a), ("b", splice_source_b)):
        source_path = output_dir / f"catalog-splice-source-{suffix}.sql"
        source_path.write_text(source_text, encoding="utf-8")
        splice_source_evidence.append(
            {
                "kind": "pb_srd_sql",
                "verified": True,
                "definition_path": str(source_path),
                "definition_text": source_text,
                "sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            }
        )
    splice_branch_contract_path = output_dir / "catalog-splice-branch-contract.json"
    splice_branch_contract_text = json.dumps(
        {
            "target_procedure": "SP_CATALOG_SELECT",
            "branch_sql": splice_source_b,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    splice_branch_contract_path.write_text(splice_branch_contract_text, encoding="utf-8")
    splice_branch_evidence = {
        "kind": "branch_contract",
        "verified": True,
        "target_procedure": "SP_CATALOG_SELECT",
        "path": str(splice_branch_contract_path),
        "artifact_text": splice_branch_contract_text,
        "sha256": hashlib.sha256(splice_branch_contract_text.encode("utf-8")).hexdigest(),
        "branch_sql": splice_source_b,
    }
    source_source_splice_result = verify_pb_migration_sp_generation_contract(
        splice_candidate_sql,
        source_evidence=[*splice_source_evidence, caller_evidence],
        profile_evidence=profile,
    )
    branch_source_splice_result = verify_pb_migration_sp_generation_contract(
        splice_candidate_sql,
        source_evidence=[splice_source_evidence[0], caller_evidence, splice_branch_evidence],
        profile_evidence=profile,
    )

    nested_nocount_sql = sql.replace(
        "        SELECT A.ENTITY_ID",
        "        SET NOCOUNT ON;\n\n        SELECT A.ENTITY_ID",
    )
    nested_nocount_result = verify_pb_migration_sp_generation_contract(
        nested_nocount_sql,
        source_evidence=[body_evidence, caller_evidence, branch_evidence],
        profile_evidence=profile,
    )

    structural_candidate_template = """-- =============================================
-- DESCRIPTION: Structural trace demo
-- =============================================
CREATE OR ALTER PROCEDURE [DBO].[SP_CATALOG_SELECT]
      @WORKTYPE   VARCHAR(20)
    , @FILTER_TEXT NVARCHAR(100)
AS
BEGIN
{body}
END;
"""
    structure_select = "SELECT @FILTER_TEXT AS DISPLAY_NAME;"
    structure_try = """BEGIN TRY
    SELECT @FILTER_TEXT AS DISPLAY_NAME;
END TRY
BEGIN CATCH
END CATCH;"""
    structure_loop = """WHILE @WORKTYPE = 'LIST'
BEGIN
    SELECT @FILTER_TEXT AS DISPLAY_NAME;
END;"""
    structure_nested = """BEGIN
    BEGIN
        SELECT @FILTER_TEXT AS DISPLAY_NAME;
    END;
END;"""
    structure_adjacent = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @FILTER_TEXT AS DISPLAY_NAME;
END
ELSE
BEGIN
    WHILE @WORKTYPE = 'SAVE'
    BEGIN
        BEGIN TRANSACTION;
        UPDATE [DBO].[ENTITY_RECORD] SET DISPLAY_NAME = @FILTER_TEXT;
        COMMIT TRANSACTION;
    END;
END;"""
    structure_adjacent_moved = """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @FILTER_TEXT AS DISPLAY_NAME;
END
ELSE
BEGIN
    WHILE @WORKTYPE = 'SAVE'
    BEGIN
    END;
    BEGIN TRANSACTION;
    UPDATE [DBO].[ENTITY_RECORD] SET DISPLAY_NAME = @FILTER_TEXT;
    COMMIT TRANSACTION;
END;"""
    structural_cases = {
        "try_catch_added": (structure_select, structure_try),
        "try_catch_omitted": (structure_try, structure_select),
        "while_body_moved_to_root": (
            structure_loop,
            """WHILE @WORKTYPE = 'LIST'
BEGIN
END;
SELECT @FILTER_TEXT AS DISPLAY_NAME;""",
        ),
        "nested_begin_omitted": (structure_nested, structure_select),
        "transaction_before_nocount": (
            structure_select,
            """BEGIN TRANSACTION;
SET NOCOUNT ON;
SELECT @FILTER_TEXT AS DISPLAY_NAME;""",
        ),
        "else_loop_transaction_moved": (
            structure_adjacent,
            structure_adjacent_moved,
        ),
        "control_arm_braces_removed": (
            """IF @WORKTYPE = 'LIST'
BEGIN
    SELECT @FILTER_TEXT AS DISPLAY_NAME;
END
ELSE
BEGIN
    UPDATE [DBO].[ENTITY_RECORD] SET DISPLAY_NAME = @FILTER_TEXT;
END;""",
            """IF @WORKTYPE = 'LIST'
    SELECT @FILTER_TEXT AS DISPLAY_NAME;
ELSE
    UPDATE [DBO].[ENTITY_RECORD] SET DISPLAY_NAME = @FILTER_TEXT;""",
        ),
        "exhaustive_source_subset": (
            """SELECT @FILTER_TEXT AS DISPLAY_NAME;
UPDATE [DBO].[ENTITY_RECORD] SET DISPLAY_NAME = @FILTER_TEXT;""",
            structure_select,
        ),
    }
    structural_negative_results = {}
    structural_source_evidence = {}
    for case_name, (source_text, candidate_body) in structural_cases.items():
        source_path = output_dir / f"catalog-{case_name.replace('_', '-')}-source.sql"
        source_path.write_text(source_text, encoding="utf-8")
        evidence_item = {
            "kind": "pb_srd_sql",
            "verified": True,
            "definition_path": str(source_path),
            "definition_text": source_text,
            "sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        }
        structural_source_evidence[case_name] = evidence_item
        structural_negative_results[case_name] = (
            verify_pb_migration_sp_generation_contract(
                structural_candidate_template.format(body=candidate_body),
                source_evidence=[evidence_item, caller_evidence],
                profile_evidence=profile,
            )
        )

    complete_root_source = structural_candidate_template.format(
        body=structure_select
    ).replace("CREATE OR ALTER PROCEDURE", "ALTER PROCEDURE", 1)
    complete_root_candidate = structural_candidate_template.format(
        body=structure_select
    ).replace("AS\nBEGIN\n", "AS\n", 1).rsplit("\nEND;", 1)[0] + "\n"
    complete_root_source_path = output_dir / "catalog-complete-root-source.sql"
    complete_root_source_path.write_text(complete_root_source, encoding="utf-8")
    complete_root_evidence = {
        "kind": "existing_sp",
        "verified": True,
        "object": "SP_CATALOG_SELECT",
        "definition_path": str(complete_root_source_path),
        "definition_text": complete_root_source,
        "sha256": hashlib.sha256(
            complete_root_source.encode("utf-8")
        ).hexdigest(),
    }
    structural_negative_results["procedure_root_braces_removed"] = (
        verify_pb_migration_sp_generation_contract(
            complete_root_candidate,
            source_evidence=[complete_root_evidence, caller_evidence],
            profile_evidence=profile,
        )
    )

    splice_lineage = [item["sha256"] for item in splice_source_evidence]
    splice_trace_sha256 = _canonical_nonwrapper_trace_sha256(splice_candidate_sql)
    composite_negative_results = {}
    for case_name, trace_sha256, source_lineage in (
        ("wrong_composite_trace_hash", "f" * 64, splice_lineage),
        ("partial_composite_lineage", splice_trace_sha256, splice_lineage[:1]),
    ):
        composite_payload = {
            "target_procedure": "SP_CATALOG_SELECT",
            "trace_sql": splice_candidate_sql,
            "trace_sha256": trace_sha256,
            "source_lineage": source_lineage,
        }
        composite_text = json.dumps(
            composite_payload,
            ensure_ascii=False,
            sort_keys=True,
        )
        composite_path = output_dir / f"catalog-{case_name.replace('_', '-')}.json"
        composite_path.write_text(composite_text, encoding="utf-8")
        composite_evidence = {
            "kind": "composite_contract",
            "verified": True,
            "target_procedure": "SP_CATALOG_SELECT",
            "path": str(composite_path),
            "artifact_text": composite_text,
            "sha256": hashlib.sha256(composite_text.encode("utf-8")).hexdigest(),
            "trace_sql": splice_candidate_sql,
            "trace_sha256": trace_sha256,
            "source_lineage": source_lineage,
        }
        composite_negative_results[case_name] = (
            verify_pb_migration_sp_generation_contract(
                splice_candidate_sql,
                source_evidence=[
                    *splice_source_evidence,
                    caller_evidence,
                    composite_evidence,
                ],
                profile_evidence=profile,
            )
        )

    omitted_try_source = structural_source_evidence["try_catch_omitted"]
    omitted_try_trace_sql = structural_candidate_template.format(
        body=structure_select
    )
    omitted_try_payload = {
        "target_procedure": "SP_CATALOG_SELECT",
        "trace_sql": omitted_try_trace_sql,
        "trace_sha256": _canonical_nonwrapper_trace_sha256(
            omitted_try_trace_sql
        ),
        "source_lineage": [omitted_try_source["sha256"]],
    }
    omitted_try_text = json.dumps(
        omitted_try_payload,
        ensure_ascii=False,
        sort_keys=True,
    )
    omitted_try_path = output_dir / "catalog-composite-omits-try-catch.json"
    omitted_try_path.write_text(omitted_try_text, encoding="utf-8")
    composite_negative_results["composite_omits_try_catch"] = (
        verify_pb_migration_sp_generation_contract(
            structural_candidate_template.format(body=structure_try),
            source_evidence=[
                omitted_try_source,
                caller_evidence,
                {
                    "kind": "composite_contract",
                    "verified": True,
                    "target_procedure": "SP_CATALOG_SELECT",
                    "path": str(omitted_try_path),
                    "artifact_text": omitted_try_text,
                    "sha256": hashlib.sha256(
                        omitted_try_text.encode("utf-8")
                    ).hexdigest(),
                    **omitted_try_payload,
                },
            ],
            profile_evidence=profile,
        )
    )

    exhaustive_source = structural_source_evidence["exhaustive_source_subset"]
    exhaustive_candidate = structural_candidate_template.format(
        body=structure_select
    )
    exhaustive_payload = {
        "target_procedure": "SP_CATALOG_SELECT",
        "trace_sql": exhaustive_candidate,
        "trace_sha256": _canonical_nonwrapper_trace_sha256(
            exhaustive_candidate
        ),
        "source_lineage": [exhaustive_source["sha256"]],
    }
    exhaustive_text = json.dumps(
        exhaustive_payload,
        ensure_ascii=False,
        sort_keys=True,
    )
    exhaustive_path = output_dir / "catalog-composite-source-subset.json"
    exhaustive_path.write_text(exhaustive_text, encoding="utf-8")
    composite_negative_results["composite_source_subset"] = (
        verify_pb_migration_sp_generation_contract(
            exhaustive_candidate,
            source_evidence=[
                exhaustive_source,
                caller_evidence,
                {
                    "kind": "composite_contract",
                    "verified": True,
                    "target_procedure": "SP_CATALOG_SELECT",
                    "path": str(exhaustive_path),
                    "artifact_text": exhaustive_text,
                    "sha256": hashlib.sha256(
                        exhaustive_text.encode("utf-8")
                    ).hexdigest(),
                    **exhaustive_payload,
                },
            ],
            profile_evidence=profile,
        )
    )

    raw_parameter_artifact = _complete_csharp_caller_artifact(
        '''return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
    , """new DbParameter("@WORKTYPE", workType), new DbParameter("@FILTER_TEXT", filterText)"""
);'''
    )
    raw_parameter_path = output_dir / "catalog-raw-string-parameter-forgery.cs"
    raw_parameter_path.write_text(raw_parameter_artifact, encoding="utf-8")
    raw_parameter_evidence = dict(caller_evidence)
    raw_parameter_evidence.update(
        {
            "path": str(raw_parameter_path),
            "definition_text": raw_parameter_artifact,
            "sha256": hashlib.sha256(raw_parameter_artifact.encode("utf-8")).hexdigest(),
        }
    )
    raw_parameter_result = verify_pb_migration_sp_generation_contract(
        sql,
        source_evidence=[body_evidence, raw_parameter_evidence, branch_evidence],
        profile_evidence=profile,
    )

    csharp_parser_negative_results = {}
    csharp_parser_fixtures = {
        "nested_lambda_parameter": '''return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
    , new Func<DbParameter>(() => new DbParameter("@WORKTYPE", workType))
    , new DbParameter("@FILTER_TEXT", filterText)
);''',
        "direct_value_lambda": '''return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
    , new DbParameter("@WORKTYPE", () => workType)
    , new DbParameter("@FILTER_TEXT", filterText)
);''',
        "direct_value_array": '''return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
    , new DbParameter("@WORKTYPE", new[] { workType })
    , new DbParameter("@FILTER_TEXT", filterText)
);''',
        "direct_value_object_initializer": '''return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
    , new DbParameter("@WORKTYPE", new Holder { Value = workType })
    , new DbParameter("@FILTER_TEXT", filterText)
);''',
        "direct_value_conditional": '''return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
    , new DbParameter("@WORKTYPE", enabled ? workType : fallback)
    , new DbParameter("@FILTER_TEXT", filterText)
);''',
        "expression_lambda_call_context": '''Func<DataSet> load = () => dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
    , new DbParameter("@WORKTYPE", workType)
    , new DbParameter("@FILTER_TEXT", filterText)
);''',
        "local_function_call_context": '''private DataSet LoadRows()
{
    DataSet LocalLoad()
    {
        return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
            , new DbParameter("@WORKTYPE", workType)
            , new DbParameter("@FILTER_TEXT", filterText)
        );
    }

    return LocalLoad();
}''',
        "mixed_correct_and_wrong_calls": caller_body + '''
dbClient.ExecSP("SP_OTHER_SAVE"
    , new DbParameter("@WORKTYPE", workType)
    , new DbParameter("@FILTER_TEXT", filterText)
);''',
        "whitespace_second_unsupported_call": caller_body + '''
dbClient /* count this call too */
    . ExecuteOther();''',
        "interpolated_second_call": '''string audit = $"{dbClient.ExecuteOther()}";
''' + caller_body,
        "conditional_second_call": '''dbClient /* conditional */ ? . ExecuteOther();
''' + caller_body,
        "parenthesized_null_forgiving_second_call": '''((dbClient /* receiver */ !)) . ExecuteOther();
''' + caller_body,
        "unknown_preprocessor_symbol": '''#if FEATURE_X
return dbClient.GetDataSetFromSP("SP_OTHER_SELECT"
    , new DbParameter("@WORKTYPE", workType)
    , new DbParameter("@FILTER_TEXT", filterText)
);
#else
return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
    , new DbParameter("@WORKTYPE", workType)
    , new DbParameter("@FILTER_TEXT", filterText)
);
#endif''',
        "globally_unbalanced_artifact": caller_body + "\nif (enabled) {",
        "top_level_local_function": '''private DataSet LocalLoad()
{
    return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
        , new DbParameter("@WORKTYPE", workType)
        , new DbParameter("@FILTER_TEXT", filterText)
    );
}''',
        "constructor_context": '''public sealed class CallerEvidence
{
    public CallerEvidence()
    {
        dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
            , new DbParameter("@WORKTYPE", workType)
            , new DbParameter("@FILTER_TEXT", filterText)
        );
    }
}''',
        "keyword_return_type": '''public sealed class CallerEvidence
{
    private return Execute()
    {
        return dbClient.GetDataSetFromSP("SP_CATALOG_SELECT"
            , new DbParameter("@WORKTYPE", workType)
            , new DbParameter("@FILTER_TEXT", filterText)
        );
    }
}''',
    }
    prewrapped_or_incomplete_caller_artifacts = {
        "top_level_local_function",
        "constructor_context",
        "keyword_return_type",
    }
    for case_name, artifact_text in csharp_parser_fixtures.items():
        if case_name not in prewrapped_or_incomplete_caller_artifacts:
            artifact_text = _complete_csharp_caller_artifact(artifact_text)
        artifact_path = output_dir / f"catalog-{case_name.replace('_', '-')}.cs"
        artifact_path.write_text(artifact_text, encoding="utf-8")
        evidence_item = dict(caller_evidence)
        evidence_item.update(
            {
                "path": str(artifact_path),
                "definition_text": artifact_text,
                "sha256": hashlib.sha256(artifact_text.encode("utf-8")).hexdigest(),
            }
        )
        csharp_parser_negative_results[case_name] = (
            verify_pb_migration_sp_generation_contract(
                sql,
                source_evidence=[body_evidence, evidence_item, branch_evidence],
                profile_evidence=profile,
            )
        )

    wrong_caller_artifact = caller_artifact.replace(
        "SP_CATALOG_SELECT",
        "SP_OTHER_SELECT",
    )
    wrong_caller_path = output_dir / "catalog-wrong-csharp-caller.txt"
    wrong_caller_path.write_text(wrong_caller_artifact, encoding="utf-8")
    wrong_caller_evidence = dict(caller_evidence)
    wrong_caller_evidence.update(
        {
            "path": str(wrong_caller_path),
            "definition_text": wrong_caller_artifact,
            "sha256": hashlib.sha256(wrong_caller_artifact.encode("utf-8")).hexdigest(),
        }
    )
    wrong_caller_result = verify_pb_migration_sp_generation_contract(
        sql,
        source_evidence=[body_evidence, wrong_caller_evidence, branch_evidence],
        profile_evidence=profile,
    )

    external_contract = [
        {"name": "@WORKTYPE", "type_spec": "VARCHAR(20)"},
        {
            "name": "@FILTER_TEXT",
            "type_spec": "NVARCHAR(100)",
            "default_present": True,
            "default": "NULL",
        },
    ]
    external_negative_results = {}
    for case_name, artifact_target in (
        ("missing", None),
        ("wrong", "SP_OTHER_SELECT"),
        ("malformed", "DBO..SP_CATALOG_SELECT"),
    ):
        payload = {
            "caller_id": f"demo-external-{case_name}",
            "parameter_contract": external_contract,
        }
        if artifact_target is not None:
            payload["target_procedure"] = artifact_target
        artifact_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        artifact_path = output_dir / f"catalog-external-{case_name}-target.json"
        artifact_path.write_text(artifact_text, encoding="utf-8")
        evidence_item = {
            "kind": "external_caller",
            "verified": True,
            "caller_id": payload["caller_id"],
            "target_procedure": artifact_target,
            "path": str(artifact_path),
            "artifact_text": artifact_text,
            "sha256": hashlib.sha256(artifact_text.encode("utf-8")).hexdigest(),
            "parameter_contract": external_contract,
        }
        external_negative_results[case_name] = verify_pb_migration_sp_generation_contract(
            sql,
            source_evidence=[body_evidence, evidence_item, branch_evidence],
            profile_evidence=profile,
        )

    cleanup_original = """-- =============================================
-- DESCRIPTION: Existing synthetic cleanup
-- =============================================
ALTER PROCEDURE [DBO].[SP_CATALOG_CLEANUP]
      @WORKTYPE VARCHAR(20)
AS
BEGIN
    -- Keep this comment adjacent to the read.
    SELECT @WORKTYPE AS WORKTYPE;
END;
"""
    cleanup_relocated = cleanup_original.replace(
        "    -- Keep this comment adjacent to the read.\n    SELECT @WORKTYPE AS WORKTYPE;",
        "    SELECT @WORKTYPE AS WORKTYPE;\n    -- Keep this comment adjacent to the read.",
    )
    cleanup_source_path = output_dir / "existing-comment-binding.sql"
    cleanup_source_path.write_text(cleanup_original, encoding="utf-8")
    cleanup_evidence = {
        "kind": "existing_sp",
        "verified": True,
        "object": "SP_CATALOG_CLEANUP",
        "definition_path": str(cleanup_source_path),
        "definition_text": cleanup_original,
        "sha256": hashlib.sha256(cleanup_original.encode("utf-8")).hexdigest(),
    }
    relocated_comment_result = verify_pb_migration_sp_generation_contract(
        cleanup_relocated,
        operation="existing_sp_cleanup",
        original_sp_text=cleanup_original,
        source_evidence=cleanup_evidence,
    )

    negative_issue_codes = {
        "unsupported_body": {
            item["code"] for item in unsupported_body_result.metadata.get("issues", [])
        },
        "unbound_branch": {
            item["code"] for item in unbound_branch_result.metadata.get("issues", [])
        },
        "branch_position_swap": {
            item["code"]
            for item in branch_position_swap_result.metadata.get("issues", [])
        },
        "sibling_statement_branch_order_swap": {
            item["code"]
            for item in sibling_order_swap_result.metadata.get("issues", [])
        },
        "source_source_branch_splice": {
            item["code"]
            for item in source_source_splice_result.metadata.get("issues", [])
        },
        "branch_source_branch_splice": {
            item["code"]
            for item in branch_source_splice_result.metadata.get("issues", [])
        },
        "nested_set_nocount": {
            item["code"] for item in nested_nocount_result.metadata.get("issues", [])
        },
        **{
            case_name: {
                item["code"] for item in result.metadata.get("issues", [])
            }
            for case_name, result in structural_negative_results.items()
        },
        **{
            case_name: {
                item["code"] for item in result.metadata.get("issues", [])
            }
            for case_name, result in composite_negative_results.items()
        },
        "raw_string_parameter": {
            item["code"] for item in raw_parameter_result.metadata.get("issues", [])
        },
        **{
            case_name: {
                item["code"] for item in result.metadata.get("issues", [])
            }
            for case_name, result in csharp_parser_negative_results.items()
        },
        "wrong_csharp_target": {
            item["code"] for item in wrong_caller_result.metadata.get("issues", [])
        },
        "missing_external_target": {
            item["code"]
            for item in external_negative_results["missing"].metadata.get("issues", [])
        },
        "wrong_external_target": {
            item["code"]
            for item in external_negative_results["wrong"].metadata.get("issues", [])
        },
        "malformed_external_target": {
            item["code"]
            for item in external_negative_results["malformed"].metadata.get("issues", [])
        },
        "relocated_business_comment": {
            item["code"] for item in relocated_comment_result.metadata.get("issues", [])
        },
    }
    expected_negative_codes = {
        "unsupported_body": "candidate_body_statement_not_covered_by_source",
        "unbound_branch": "candidate_body_statement_not_covered_by_source",
        "branch_position_swap": "body_fragment_not_present_in_candidate",
        "sibling_statement_branch_order_swap": "body_fragment_not_present_in_candidate",
        "source_source_branch_splice": "candidate_body_not_covered_by_single_authority",
        "branch_source_branch_splice": "candidate_body_not_covered_by_single_authority",
        "nested_set_nocount": "candidate_body_not_covered_by_single_authority",
        **{
            case_name: "candidate_body_not_covered_by_single_authority"
            for case_name in structural_negative_results
        },
        "wrong_composite_trace_hash": "composite_contract_trace_sha256_mismatch",
        "partial_composite_lineage": "composite_contract_source_lineage_mismatch",
        "composite_omits_try_catch": "composite_contract_candidate_trace_mismatch",
        "composite_source_subset": "composite_contract_source_trace_mismatch",
        "raw_string_parameter": "csharp_caller_target_procedure_mismatch",
        **{
            case_name: "csharp_caller_target_procedure_mismatch"
            for case_name in csharp_parser_negative_results
        },
        "wrong_csharp_target": "csharp_caller_target_procedure_mismatch",
        "missing_external_target": "external_caller_target_procedure_missing",
        "wrong_external_target": "external_caller_target_procedure_mismatch",
        "malformed_external_target": "external_caller_target_procedure_invalid",
        "relocated_business_comment": "existing_sp_comment_binding_changed",
    }
    if any(
        expected_code not in negative_issue_codes[case_name]
        for case_name, expected_code in expected_negative_codes.items()
    ):
        raise RuntimeError(
            "PB SP negative traceability/target cases were not rejected: "
            + json.dumps(
                {key: sorted(value) for key, value in negative_issue_codes.items()},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    grid_xml_contract = verify_devexpress_grid_xml_contract(
        grid_xml,
        expected_columns=grid_columns,
    )
    split_validated = runtime_mapped.metadata.get("designer_owned_ui_contract", {}).get(
        "split_contract_validated"
    )
    if (
        not profile.success
        or not runtime_mapped.success
        or not split_validated
        or runtime_unrelated.success
        or runtime_misplaced.success
        or not sp_contract.success
        or not branch_position_valid_result.success
        or not sibling_order_valid_result.success
        or not grid_plan.success
        or not grid_xml_contract.success
    ):
        raise RuntimeError(
            "packaged runtime validation did not enforce the generalized contract: "
            + json.dumps(
                {
                    "profile": profile.success,
                    "runtime_mapped": runtime_mapped.to_dict(),
                    "split_validated": split_validated,
                    "runtime_unrelated_rejected": not runtime_unrelated.success,
                    "runtime_misplaced_rejected": not runtime_misplaced.success,
                    "sp_contract": sp_contract.to_dict(),
                    "source_backed_branch_contract": branch_position_valid_result.to_dict(),
                    "grid_plan": grid_plan.to_dict(),
                    "grid_xml_contract": grid_xml_contract.to_dict(),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )

    _write_utf8_artifact(sql_path, sql)

    evidence = {
        "schema_version": "1.0",
        "skill": skill_name,
        "status": "passed",
        "execution_level": "python-module",
        "contract_id": contract["contract_id"],
        "contract_version": contract["contract_version"],
        "profile_source": contract["normal_generation"]["profile_source"],
        "profile_update_ran": False,
        "external_discovery_ran": False,
        "token_optimizer_status": "passthrough",
        "verification_scope": "static_xml_and_post_load_equivalent_designer_state",
        "actual_live_layout_load_observed": False,
        "selected_families": {
            "screen": "browse",
            "method": "event",
            "provider": "devexpress",
            "procedure": "select",
        },
        "caller_parameter_matrix": [
            {"parameter": "@WORKTYPE", "caller_source": "selected branch"},
            {"parameter": "@FILTER_TEXT", "caller_source": "txtFilterText.Text"},
        ],
        "csharp_structural_validation": mapped,
        "designer_ownership_validation": ownership,
        "runtime_validation": {
            "mapped_designer_split": "passed",
            "designer_static_finding_count": runtime_mapped.metadata[
                "designer_owned_ui_contract"
            ]["designer_static_finding_count"],
            "unrelated_class": "rejected",
            "misplaced_static_ui": "rejected",
            "unrelated_issue_codes": [
                item["code"] for item in runtime_unrelated.metadata.get("issues", [])
            ],
            "misplaced_issue_codes": [
                item["code"] for item in runtime_misplaced.metadata.get("issues", [])
            ],
            "target_artifact_binding": runtime_mapped.metadata[
                "target_artifact_binding"
            ],
            "control_contracts": runtime_mapped.metadata["control_contracts"],
            "control_evidence_registry": runtime_mapped.metadata[
                "control_evidence_registry"
            ],
            "baseline_designer_preservation": runtime_mapped.metadata[
                "baseline_designer_preservation"
            ],
            "sp_generation_contract": "passed" if sp_contract.success else "blocked",
            "branch_contract": {
                "status": "verified",
                "target_procedure": "DBO.SP_CATALOG_SELECT",
                "artifact_path": str(branch_contract_path),
                "sha256": branch_evidence["sha256"],
                "branch_sql": branch_evidence["branch_sql"],
            },
            "sp_issue_codes": [
                item["code"]
                for item in sp_contract.metadata.get("sp_generation_contract", {}).get(
                    "issues", []
                )
            ],
            "sp_negative_traceability_and_target_cases": {
                key: sorted(value) for key, value in negative_issue_codes.items()
            },
            "sql_final_response_binding": sp_contract.metadata.get(
                "sql_final_response_binding", {}
            ),
            "sql_final_response_release": sp_contract.metadata.get(
                "sql_final_response_release", {}
            ),
            "sql_provider_fixture": {
                "source": "host-local-skill",
                "path": str(sql_provider_path),
                "purpose": "offline demo fixture for authoritative provider-path binding",
            },
            "grid_xml_contract": "passed" if grid_xml_contract.success else "blocked",
            "composite_business_key_display": {
                "status": "passed",
                "contract": "key-value plus ordered sequence fields",
                "name_specific_routing": False,
                "scenarios": composite_display_plans,
            },
            "grid_designer_contract": runtime_mapped.metadata["grid_designer_contract"]["status"],
            "layout_load_artifact_verified": runtime_mapped.metadata["grid_designer_contract"]["layout_load_artifact_verified"],
            "actual_live_layout_load_observed": runtime_mapped.metadata["grid_designer_contract"]["actual_live_layout_load_observed"],
            "grid_xml_issue_codes": [
                item["code"] for item in grid_xml_contract.metadata.get("issues", [])
            ],
        },
        "negative_structural_cases": {
            "empty_source": empty,
            "unrelated_class": unrelated,
        },
        "semantic_equivalence": "not_proven",
    }
    evidence_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    success_result = HarnessResult(
        success=True,
        stdout=json.dumps(mapped, sort_keys=True),
        stderr="",
        exit_code=0,
        metadata={
            "status": "passed",
            "contract_id": contract["contract_id"],
            "profile_source": "packaged-only",
            "external_discovery_ran": False,
            "token_optimizer_status": "passthrough",
            "designer_default_owner": ".Designer.cs",
            "verification_scope": "static_xml_and_post_load_equivalent_designer_state",
            "actual_live_layout_load_observed": False,
        },
    )
    blocked_result = HarnessResult(
        success=False,
        stdout=json.dumps(unrelated, sort_keys=True),
        stderr="Missing DataWindow columns and required mapped C# structural evidence.",
        exit_code=1,
        metadata={
            "status": "failed",
            "missing_inputs": ["DataWindow columns", "mapped form structure"],
            "misplaced_static_ui_pattern_ids": ownership["misplaced_fixture_matches"],
            "designer_default_owner": ".Designer.cs",
            "non_destructive": True,
        },
    )
    contracts = [
        demo_scenarios._dataclass_contract(success_result),
        demo_scenarios._dataclass_contract(blocked_result),
        demo_scenarios._mapping_contract(
            "PackagedStyleContract",
            "src.skills.pb_to_csharp_migration",
            {
                "contract_id": contract["contract_id"],
                "contract_version": contract["contract_version"],
                "required_csharp_pattern_ids": [
                    item["id"] for item in contract["rules"]["csharp"]["required_patterns"]
                ],
                "designer_default_owner": contract["designer_ownership"]["default_owner"],
                "code_behind_static_ui_pattern_ids": [
                    item["id"]
                    for item in contract["designer_ownership"]["code_behind_static_ui_patterns"]
                ],
            },
            "policy-result",
        ),
    ]
    artifacts = [
        demo_scenarios._artifact_record_from_file(
            csharp_path,
            "synthetic-csharp-screen",
            output_dir,
            ["UTF-8 readable", "all required C# structural rules matched"],
            created_by_case="success",
        ),
        demo_scenarios._artifact_record_from_file(
            designer_path,
            "synthetic-csharp-designer",
            output_dir,
            ["UTF-8 readable", "static UI configuration is Designer-owned"],
            created_by_case="success",
        ),
        demo_scenarios._artifact_record_from_file(
            baseline_designer_path,
            "synthetic-csharp-designer-baseline",
            output_dir,
            [
                "UTF-8 readable",
                "separately captured pre-verification Designer baseline",
            ],
            created_by_case="success",
        ),
        demo_scenarios._artifact_record_from_file(
            sql_path,
            "synthetic-select-procedure",
            output_dir,
            [
                "UTF-8 readable",
                "synthetic procedure identifiers only",
                "SP generation contract and final SQL response binding verified",
            ],
            created_by_case="success",
        ),
        demo_scenarios._artifact_record_from_file(
            grid_xml_path,
            "synthetic-devexpress-grid-layout",
            output_dir,
            ["XML readable", "serializer and Layout Load values verified"],
            created_by_case="success",
        ),
        demo_scenarios._artifact_record_from_file(
            evidence_path,
            "offline-generation-evidence",
            output_dir,
            ["JSON readable", "packaged-only profile recorded", "negative structural cases correctly rejected"],
            created_by_case="success",
        ),
    ]
    return demo_scenarios._scenario_result(
        success_contract="HarnessResult",
        success_payload={
            "validation": success_result.to_dict(),
            "migration_plan": {
                "mode": "contract-only",
                "screen": "browse",
                "provider": "devexpress",
                "profile_source": "packaged-only",
                "designer_default_owner": ".Designer.cs",
                "verification_scope": "static_xml_and_post_load_equivalent_designer_state",
                "actual_live_layout_load_observed": False,
            },
        },
        success_evidence=[
            "PB to C# migration plan produced from packaged-only synthetic evidence",
            "pb-csharp-probe matched all generalized required C# structural patterns",
            "empty source and unrelated class text were rejected",
            "Designer ownership scan kept static UI out of code-behind",
            "misplaced static UI fixture was correctly rejected",
            "exact distinct C# source Designer and baseline artifacts were SHA-256 bound",
            "complete control inventory and structured evidence registry passed",
            "demo SQL passed the PB SP contract and actual final-response binder",
            "generated View XML and matching DevExpress Designer source passed static contract verification",
            "actual live DevExpress Layout Load was not observed",
            "no external discovery or profile update ran",
        ],
        success_behavior=(
            "Produce a PB to C# migration plan and synthetic C#/Designer/SQL artifacts from the "
            "packaged-only offline contract, then prove mapped C# structure and Designer ownership "
            "without private examples."
        ),
        success_side_effects=["writes only sanitized synthetic artifacts under the demo output directory"],
        blocked_contract="HarnessResult",
        blocked_payload=blocked_result.to_dict(),
        blocked_reason="missing DataWindow columns and mapped C# structural evidence",
        missing_inputs=["DataWindow columns", "mapped form declaration and UI binding evidence"],
        contracts=contracts,
        artifacts=artifacts,
    )


if __name__ == "__main__":
    sys.path.insert(0, str(_repo_root()))
    from src.skills import demo_scenarios
    from src.skills.demo_scenarios import main

    demo_scenarios._pb_to_csharp_migration_scenario = _sanitized_offline_scenario
    raise SystemExit(main(SKILL_NAME))
