import hashlib
import json
import re
import sys
from pathlib import Path


SKILL_NAME = "pb-to-csharp-migration-harness"
CONTRACT_ID = "pb-csharp-offline-generalized"


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
            grdBrowse.DataSource = result;
        }
    }
}
"""


def _designer_demo() -> str:
    return """using System.Drawing;
using System.Windows.Forms;

namespace SyntheticMigration
{
    partial class CatalogBrowseForm
    {
        private TextBox txtFilterText;
        private DataGridView grdBrowse;
        private DataGridViewTextBoxColumn colBrowse_ENTITY_ID;

        private void InitializeComponent()
        {
            this.txtFilterText = new TextBox();
            this.grdBrowse = new DataGridView();
            this.colBrowse_ENTITY_ID = new DataGridViewTextBoxColumn();

            this.txtFilterText.Name = "txtFilterText";
            this.txtFilterText.Location = new Point(16, 16);
            this.txtFilterText.Size = new Size(180, 24);
            this.txtFilterText.TabIndex = 0;
            this.colBrowse_ENTITY_ID.Name = "colBrowse_ENTITY_ID";
            this.colBrowse_ENTITY_ID.DataPropertyName = "ENTITY_ID";
            this.grdBrowse.Columns.AddRange(this.colBrowse_ENTITY_ID);
        }
    }
}
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
this.txtFilterText = new TextBox();
this.txtFilterText.Name = "txtFilterText";
this.grdBrowse.Columns.AddRange(this.colBrowse_ENTITY_ID);
this.colBrowse_ENTITY_ID.ColumnEdit = this.repEntity;
this.gvwBrowse.OptionsView.ShowGroupPanel = false;
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
        load_packaged_migration_profile,
        verify_migration_generated_csharp_style,
        verify_pb_migration_sp_generation_contract,
    )

    contract = _load_contract()
    csharp = _csharp_demo()
    designer = _designer_demo()
    sql = _sql_demo()
    mapped = _validate_csharp_structure(contract, csharp)
    empty = _validate_csharp_structure(contract, "")
    unrelated = _validate_csharp_structure(contract, "public class UnmappedWidget {}")
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
    )
    runtime_unrelated = verify_migration_generated_csharp_style(
        "public class UnmappedWidget {}",
        profile_evidence=profile,
        form_class="CatalogBrowseForm",
        source_role="code-behind",
    )
    runtime_misplaced = verify_migration_generated_csharp_style(
        csharp.replace(
            "InitializeComponent();",
            'InitializeComponent(); this.txtFilterText.Name = "txtFilterText";',
        ),
        profile_evidence=profile,
        form_class="CatalogBrowseForm",
        source_role="code-behind",
    )
    sp_contract = verify_pb_migration_sp_generation_contract(
        sql,
        source_evidence=[
            {
                "kind": "pasted_sql",
                "summary": "Synthetic offline catalog SELECT source",
                "program_description": "Browse synthetic catalog rows",
                "caller_parameters": ["@WORKTYPE", "@FILTER_TEXT"],
            }
        ],
        profile_evidence=profile,
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
    ):
        raise RuntimeError("packaged runtime C# validation did not enforce the generalized contract")

    csharp_path = output_dir / "CatalogBrowseForm.cs"
    designer_path = output_dir / "CatalogBrowseForm.Designer.cs"
    sql_path = output_dir / "SP_CATALOG_SELECT.sql"
    evidence_path = output_dir / "offline_generation_evidence.json"
    csharp_path.write_text(csharp, encoding="utf-8")
    designer_path.write_text(designer, encoding="utf-8")
    sql_path.write_text(sql, encoding="utf-8")

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
        "selected_families": {
            "screen": "browse",
            "method": "event",
            "provider": "winforms",
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
            "sp_generation_contract": "passed" if sp_contract.success else "blocked",
            "sp_issue_codes": [
                item["code"] for item in sp_contract.metadata.get("issues", [])
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
            sql_path,
            "synthetic-select-procedure",
            output_dir,
            [
                "UTF-8 readable",
                "synthetic procedure identifiers only",
                "SP generation contract verified",
            ],
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
                "provider": "winforms",
                "profile_source": "packaged-only",
                "designer_default_owner": ".Designer.cs",
            },
        },
        success_evidence=[
            "PB to C# migration plan produced from packaged-only synthetic evidence",
            "pb-csharp-probe matched all generalized required C# structural patterns",
            "empty source and unrelated class text were rejected",
            "Designer ownership scan kept static UI out of code-behind",
            "misplaced static UI fixture was correctly rejected",
            "demo SQL passed verify_pb_migration_sp_generation_contract",
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
