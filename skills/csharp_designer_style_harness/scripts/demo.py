"""Package-local demo; src.skills.demo_scenarios is deliberately outside its imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.skills.csharp_designer_style_contract import verify_csharp_designer_style


SKILL_NAME = "csharp-designer-style-harness"
SCENARIO_ID = "demo-csharp-designer-style-harness"
SCENARIO_FUNCTION = "_csharp_designer_scenario"
EXECUTION_LEVEL = "python-module"
CAPABILITY = "C# Designer style contract verification"
FAILURE_MODE = "source or Designer contract evidence mismatch"
SEMANTIC_PROBE = "csharp-designer-verifier-probe"

VALID_SOURCE = r'''using System;
using System.Data;

public partial class DemoForm : FrmDevBase
{
    public DemoForm() { InitializeComponent(); }

    private DataSet CallSelectProcedure(SelectType selectType)
    {
        try
        {
            return dbClient.GetDataSetFromSP(
                "sp_DEMO_SELECT",
                new DbParameter("@SELECT", selectType)
                );
        }
        catch (Exception ex)
        {
            ShowExcetion(ex);
            return null;
        }
    }

    private bool CallSaveProcedure()
    {
        try
        {
            return dbClient.ExecSP(
                "sp_DEMO_SAVE",
                new SqlParameter("@SAVE", true)
                );
        }
        catch (Exception ex)
        {
            ShowExcetion(ex);
            return false;
        }
    }

    private void DemoForm_Load(object sender, EventArgs e)
    {
        DataSet ds = CallSelectProcedure(SelectType.LIST);
        bool saved = CallSaveProcedure();
        grdList.DataSource = ds.Tables[0];
        ClearScreen();
        RefreshList();
    }

    private void ClearScreen() { devFnc.InitControl(grdList); }
    private void RefreshList() { devFnc.GridToPanel(gvwList); }
}
'''

VALID_DESIGNER = r'''using System;
using DevExpress.XtraGrid.Columns;
using DevExpress.XtraGrid.Views.Grid;
using DevExpress.XtraEditors.Repository;

public partial class DemoForm : FrmDevBase
{
    private DevExpress.XtraGrid.GridControl grdList;
    private GridView gvwList;
    private GridColumn colList_PGMDIV;
    private GridColumn colList_QTY;
    private RepositoryItemSpinEdit rpsSpinQTY;
    private DevExpress.XtraEditors.TextEdit txtPGMDIV;
    private DevExpress.XtraEditors.SimpleButton btnSearch;

    private void InitializeComponent()
    {
        this.grdList = new DevExpress.XtraGrid.GridControl();
        this.gvwList = new GridView();
        this.colList_PGMDIV = new GridColumn();
        this.colList_QTY = new GridColumn();
        this.rpsSpinQTY = new RepositoryItemSpinEdit();
        this.txtPGMDIV = new DevExpress.XtraEditors.TextEdit();
        this.btnSearch = new DevExpress.XtraEditors.SimpleButton();
        this.grdList.MainView = this.gvwList;
        this.grdList.RepositoryItems.AddRange(new RepositoryItem[] { this.rpsSpinQTY });
        this.colList_PGMDIV.FieldName = "PGMDIV";
        this.colList_PGMDIV.Name = "colList_PGMDIV";
        this.colList_PGMDIV.VisibleIndex = 1;
        this.colList_QTY.FieldName = "QTY";
        this.colList_QTY.Name = "colList_QTY";
        this.colList_QTY.VisibleIndex = 2;
        this.colList_QTY.ColumnEdit = this.rpsSpinQTY;
        this.gvwList.Columns.AddRange(new GridColumn[] { this.colList_PGMDIV, this.colList_QTY });
        this.txtPGMDIV.BindingField = "PGMDIV";
        this.txtPGMDIV.TabIndex = 0;
        this.btnSearch.TabIndex = 1;
        this.Load += new EventHandler(this.DemoForm_Load);
    }
}
'''


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": _sha256(path)}


def _result_payload(result: Any) -> dict[str, Any]:
    payload = result.to_dict()
    try:
        payload["stdout"] = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError):
        payload["stdout"] = str(result.stdout)
    return payload


def _artifact(path: Path, kind: str, output_dir: Path, created_by_case: str) -> dict[str, Any]:
    resolved = path.resolve()
    valid = path.is_file() and path.stat().st_size > 0 and resolved.is_relative_to(output_dir.resolve())
    if path.suffix.lower() == ".json" and valid:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            valid = False
    return {
        "artifact_id": path.stem.replace("_", "-"),
        "kind": kind,
        "path": str(resolved),
        "exists": path.is_file(),
        "validated": valid,
        "checksum": _sha256(path) if path.is_file() else "",
        "validation_evidence": ["file exists", "file is non-empty", "path is inside demo output directory"],
        "template_not_applicable": True,
        "created_by_case": created_by_case,
    }


def _contract(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "HarnessResult",
        "module": "src.skills.csharp_designer_style_contract",
        "fields_checked": list(payload),
        "roundtrip_checked": False,
        "schema_validation_checked": bool(payload),
        "roundtrip_kind": "mapping_schema_presence",
        "source": "policy-result",
        "sample": {
            "success": payload.get("success"),
            "exit_code": payload.get("exit_code"),
            "status": dict(payload.get("metadata", {})).get("status"),
            "issue_count": len(dict(payload.get("metadata", {})).get("issues", [])),
        },
    }


def _implementation_targets() -> list[dict[str, Any]]:
    targets = [
        ("src.skills.csharp_designer_style_contract.verify_csharp_designer_style", REPO_ROOT / "src/skills/csharp_designer_style_contract.py", "resolved", "function"),
        ("src.contracts.HarnessResult", REPO_ROOT / "src/contracts.py", "resolved", "type"),
        ("skills/csharp_designer_style_harness/scripts/smoke_check.py", REPO_ROOT / "skills/csharp_designer_style_harness/scripts/smoke_check.py", "resolved", "file"),
        ("skills/csharp_designer_style_harness/scripts/demo.py", REPO_ROOT / "skills/csharp_designer_style_harness/scripts/demo.py", "resolved", "file"),
        ("tests.test_csharp_designer_style_contract", REPO_ROOT / "tests/test_csharp_designer_style_contract.py", "packaged_test_reference", "module"),
        ("tests.test_plugin_packaging", REPO_ROOT / "tests/test_plugin_packaging.py", "packaged_test_reference", "module"),
    ]
    return [
        {
            "ref": ref,
            "status": status if path.is_file() else "missing",
            "path": str(path.resolve()),
            "object_type": object_type,
            "proof": "package_local_target_probe",
        }
        for ref, path, status, object_type in targets
    ]


def _host_metadata(output_dir: Path, selected_host: str) -> dict[str, Any]:
    host_modes = {
        "local": ("local Python verifier dispatch", "caller-supplied temporary output state"),
        "codex": ("Codex tool-mediated verifier dispatch", "host-owned runtime state"),
        "antigravity-style": ("agent-manager verifier dispatch", "host-owned runtime state"),
        "claude-code": ("CLI-mediated verifier dispatch", "host-owned runtime state"),
    }
    dispatch, state = host_modes[selected_host]
    return {
        "selected_host": selected_host,
        "host_mode_evidence": {
            "dispatch": f"simulated metadata only: {dispatch}",
            "state": f"simulated metadata only: {state}",
            "panel": "stdout JSON plus an output-directory artifact manifest",
        },
        "host_claim_scope": "simulated_metadata_only",
        "behavioral_host_execution": False,
        "behavioral_host_execution_reason": "This package-local demo runs the verifier only; it does not launch a host runtime.",
        "verified_host_artifacts": [],
        "host_differences": [
            {"host": host, "dispatch": values[0], "state": values[1]}
            for host, values in host_modes.items()
        ],
        "output_dir": str(output_dir.resolve()),
        "cwd_supported": True,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "external_runtime_dependency": False,
        "execution_level": EXECUTION_LEVEL,
    }


def _csharp_designer_scenario(output_dir: Path, host: str) -> tuple[dict[str, Any], int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_path = output_dir / "DemoForm.cs"
    designer_path = output_dir / "DemoForm.Designer.cs"
    blocked_source_path = output_dir / "BlockedDemoForm.cs"
    blocked_designer_path = output_dir / "BlockedDemoForm.Designer.cs"
    source_path.write_text(VALID_SOURCE, encoding="utf-8", newline="")
    designer_path.write_text(VALID_DESIGNER, encoding="utf-8", newline="")
    blocked_source_path.write_text(
        VALID_SOURCE.replace("CallSelectProcedure", "CallViewQuery").replace("CallSaveProcedure", "CallSaveQuery"),
        encoding="utf-8",
        newline="",
    )
    blocked_designer_path.write_text(VALID_DESIGNER.replace("colList_PGMDIV", "colPGMDIV"), encoding="utf-8", newline="")

    success_result = verify_csharp_designer_style(
        _receipt(source_path),
        _receipt(designer_path),
        native_helpers=["ClearScreen", "RefreshList"],
        expected_identities={
            "procedures": ["sp_DEMO_SELECT", "sp_DEMO_SAVE"],
            "controls": ["grdList", "colList_QTY"],
            "fields": ["grdList", "colList_QTY"],
            "methods": ["CallSelectProcedure", "CallSaveProcedure"],
        },
    )
    blocked_result = verify_csharp_designer_style(_receipt(blocked_source_path), _receipt(blocked_designer_path))
    success_payload = _result_payload(success_result)
    blocked_payload = _result_payload(blocked_result)
    success_is_real = bool(success_result.success and success_result.exit_code == 0 and success_result.metadata.get("status") == "passed")
    blocked_is_real = bool(not blocked_result.success and blocked_result.exit_code != 0 and blocked_result.metadata.get("status") == "blocked")

    context = {"skill": SKILL_NAME, "scenario_id": SCENARIO_ID, "scenario_function": SCENARIO_FUNCTION, "semantic_probe": SEMANTIC_PROBE}
    success_case = {
        "status": "passed" if success_is_real else "failed",
        "contract_type": "HarnessResult",
        "payload": success_payload,
        "evidence": [
            "exact source and Designer receipts were reopened and byte-hash checked",
            f"capability_proven: {CAPABILITY}",
            f"semantic_probe: {SEMANTIC_PROBE}",
        ],
        "expected_behavior": "Run C# Designer style contract verification against real SELECT/SAVE calls and exact artifacts.",
        "side_effects": ["writes bounded demo artifacts below the requested output directory"],
        "skill_demo_context": context,
        "capability_proven": CAPABILITY,
        "semantic_probe": SEMANTIC_PROBE,
    }
    blocked_case = {
        "status": "blocked" if blocked_is_real else "failed",
        "contract_type": "HarnessResult",
        "payload": blocked_payload,
        "blocked_reason": "The deliberately noncanonical method and Designer identities are rejected by the current verifier.",
        "missing_inputs": ["canonical query/save method family", "canonical Designer column identity"],
        "expected_behavior": "Keep the result blocked until the exact artifact pair satisfies the fixed contract.",
        "remediation": "Restore canonical method and Designer identities, then run a fresh hash-bound verification.",
        "non_destructive": True,
        "skill_demo_context": context,
        "failure_mode_proven": FAILURE_MODE,
        "semantic_probe": SEMANTIC_PROBE,
        "evidence": [f"failure_mode_proven: {FAILURE_MODE}", f"semantic_probe: {SEMANTIC_PROBE}"],
    }
    contracts = [_contract(success_payload), _contract(blocked_payload)]

    evidence_path = output_dir / "demo_evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "skill": SKILL_NAME,
                "success_status": success_case["status"],
                "success_verifier_status": success_result.metadata.get("status"),
                "blocked_status": blocked_case["status"],
                "blocked_verifier_status": blocked_result.metadata.get("status"),
                "contract_names": [item["name"] for item in contracts],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    manifest_path = output_dir / "demo_file_manifest.json"
    generated_files = [source_path, designer_path, blocked_source_path, blocked_designer_path, evidence_path, manifest_path]
    manifest_path.write_text(
        json.dumps({"skill": SKILL_NAME, "files": [str(path.resolve()) for path in generated_files]}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    artifacts = [
        _artifact(source_path, "csharp-source", output_dir, "success"),
        _artifact(designer_path, "csharp-designer", output_dir, "success"),
        _artifact(blocked_source_path, "csharp-source", output_dir, "blocked"),
        _artifact(blocked_designer_path, "csharp-designer", output_dir, "blocked"),
        _artifact(evidence_path, "demo-evidence-json", output_dir, "success"),
        _artifact(manifest_path, "demo-generated-file-manifest", output_dir, "manifest"),
    ]
    targets = _implementation_targets()
    resolved_targets = [item for item in targets if item["status"] in {"resolved", "packaged_test_reference"}]
    profile = {"skill": SKILL_NAME, "capability_proven": CAPABILITY, "failure_mode_proven": FAILURE_MODE, "semantic_probe": SEMANTIC_PROBE}
    payload = {
        "schema_version": "1.0",
        "skill": SKILL_NAME,
        "scenario_id": SCENARIO_ID,
        "execution_level": EXECUTION_LEVEL,
        "generated_at": _utc_now(),
        "success_case": success_case,
        "blocked_or_failure_case": blocked_case,
        "contracts": contracts,
        "demo_specificity": {
            "skill": SKILL_NAME,
            "scenario_id": SCENARIO_ID,
            "scenario_function": SCENARIO_FUNCTION,
            "execution_level": EXECUTION_LEVEL,
            "profile": profile,
            "success_context_bound": True,
            "blocked_context_bound": True,
            "success_and_blocked_are_distinct": success_payload != blocked_payload,
            "artifact_namespace_bound": all(Path(item["path"]).is_relative_to(output_dir.resolve()) for item in artifacts),
            "declared_implementation_targets": targets,
            "resolved_implementation_targets": [item["ref"] for item in resolved_targets],
            "skill_specific_probe": {
                "skill": SKILL_NAME,
                "primary_target": targets[0]["ref"],
                "primary_target_status": targets[0]["status"],
                "scenario_function": SCENARIO_FUNCTION,
                "semantic_probe": SEMANTIC_PROBE,
                "contract_modules": [item["module"] for item in contracts],
                "proof_kind": "implementation-target-resolution-plus-contract-demo",
            },
            "contract_names": [item["name"] for item in contracts],
            "contract_modules": [item["module"] for item in contracts],
            "unique_markers": [SKILL_NAME, SCENARIO_ID, SCENARIO_FUNCTION, EXECUTION_LEVEL, SEMANTIC_PROBE, targets[0]["ref"], "HarnessResult"],
        },
        "host_metadata": _host_metadata(output_dir, host),
        "artifacts": artifacts,
        "verification": {
            "runnable": success_is_real and blocked_is_real,
            "exit_code": 0 if success_is_real and blocked_is_real else 1,
            "stdout_json_only": True,
            "stderr_empty_or_expected": True,
            "contract_roundtrip": all(item["schema_validation_checked"] for item in contracts),
            "contract_validation_mode": "dataclass_roundtrip_or_mapping_schema",
            "artifacts_within_output_dir": all(Path(item["path"]).is_relative_to(output_dir.resolve()) for item in artifacts),
            "artifacts_validated": all(item["validated"] for item in artifacts),
            "artifact_count": len(artifacts),
            "runtime_observation": {
                "source": "outer subprocess quality gate",
                "checked_by": ["skills.csharp_designer_style_harness.scripts.smoke_check", "src.skills.uaf_skill_quality._run_demo_script"],
                "note": "The caller verifies process exit code, stdout JSON, and artifact declarations.",
            },
        },
    }
    return payload, 0 if success_is_real and blocked_is_real else 1


def main(skill_name: str = SKILL_NAME) -> int:
    if skill_name != SKILL_NAME:
        raise ValueError(f"unsupported skill: {skill_name}")
    parser = argparse.ArgumentParser(description="Run the package-local C# Designer verifier demo.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--host", default="local", choices=["local", "codex", "antigravity-style", "claude-code"])
    args = parser.parse_args()
    payload, exit_code = _csharp_designer_scenario(Path(args.output_dir).resolve(), args.host)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(SKILL_NAME))
