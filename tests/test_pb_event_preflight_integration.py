import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from src.contracts import HarnessResult
from src.skills import pb_to_csharp_migration as migration


DESIGNER = """partial class AnyForm
{
    private System.Windows.Forms.Button commandControl;
    private void InitializeComponent()
    {
        this.commandControl = new System.Windows.Forms.Button();
        this.commandControl.Name = "commandControl";
        this.commandControl.Click += this.HandleCommand;
        this.Controls.Add(this.commandControl);
    }
    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
    }
}
"""

CSHARP = """partial class AnyForm
{
    public AnyForm() { InitializeComponent(); }
    private void HandleCommand(object sender, EventArgs e)
    {
        ExecuteSave();
    }
}
"""

SAVE_SP = """CREATE PROCEDURE dbo.SaveAny @VALUE INT AS
BEGIN
    IF EXISTS (SELECT 1 FROM AnyTable WHERE ValueColumn = @VALUE)
    BEGIN
        RAISERROR(N'Duplicate value', 16, 1);
        RETURN;
    END
END
"""


class PbEventPreflightIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name).resolve()
        self.paths = {
            "pb": self._write("source.sru", "event clicked;\r\nend event\r\n"),
            "designer": self._write("AnyForm.Designer.cs", DESIGNER),
            "csharp": self._write("AnyForm.cs", CSHARP),
            "save_sp": self._write("SaveAny.sql", SAVE_SP),
        }
        self.project = self.root / "Target.Private.csproj"
        self.generated = self.root / "Generated" / "PrivateForm.cs"
        self.build_output = self.root / "bin" / "Target.Private.dll"
        self.pbl = self.root / "private.pbl"
        self.pbl.write_text(
            "PB Library: Private\nObjects: PrivateWindow.srw, PrivateData.srd\n",
            encoding="utf-8",
            newline="",
        )
        self.export_paths = {
            "PrivateWindow.srw": self._write(
                "objects/PrivateWindow.srw",
                "$PBExportHeader$PrivateWindow.srw\n"
                "global type PrivateWindow from window\n"
                "end type\n"
                "$PBExportEnd$\n",
            ),
            "PrivateData.srd": self._write(
                "objects/PrivateData.srd",
                "$PBExportHeader$PrivateData.srd\n"
                "datawindow(table(column=(name=VALUE dbname=\"VALUE\")))\n"
                "$PBExportEnd$\n",
            ),
        }
        self.generated.parent.mkdir()
        self.generated.write_text("partial class PrivateForm {}\n", encoding="utf-8")
        self.build_output.parent.mkdir()
        self.build_output.write_bytes(b"current build output")
        self.project.write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><ItemGroup>'
            '<PackageReference Include="Stable.Dependency" Version="1.0.0" />'
            "</ItemGroup></Project>",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _write(self, relative, source):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8", newline="")
        return path

    @staticmethod
    def _sha(path):
        return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def _artifact(self, role):
        path = self.paths[role]
        return {
            "path": str(path),
            "sha256": self._sha(path),
            "source": path.read_text(encoding="utf-8"),
        }

    def _event_contract(self):
        pb_binding = {
            "source_path": str(self.paths["pb"]),
            "source_sha256": self._sha(self.paths["pb"]),
        }
        csharp_binding = {
            "source_path": str(self.paths["csharp"]),
            "source_sha256": self._sha(self.paths["csharp"]),
        }
        designer_binding = {
            "source_path": str(self.paths["designer"]),
            "source_sha256": self._sha(self.paths["designer"]),
        }
        return {
            "pb_event_inventory": [
                {
                    "event_id": "evt-1",
                    "object": "command",
                    "event": "clicked",
                    "confirmed": True,
                    **pb_binding,
                }
            ],
            "event_mappings": [
                {
                    "pb_event_id": "evt-1",
                    "handler": "HandleCommand",
                    "subscription_id": "sub-1",
                    "csharp_event": "Click",
                }
            ],
            "csharp_event_handlers": [{"handler": "HandleCommand", **csharp_binding}],
            "csharp_event_subscriptions": [
                {
                    "subscription_id": "sub-1",
                    "owner": "designer",
                    "event": "Click",
                    "handler": "HandleCommand",
                    **designer_binding,
                }
            ],
            "designer_artifact": self._artifact("designer"),
            "csharp_artifact": self._artifact("csharp"),
            "save_sp_artifact": self._artifact("save_sp"),
            "ownership_ledger": [
                {
                    "rule_id": "duplicate-value",
                    "owner": "save_sp",
                    "artifacts": {
                        "csharp": {
                            "path": str(self.paths["csharp"]),
                            "sha256": self._sha(self.paths["csharp"]),
                        },
                        "save_sp": {
                            "path": str(self.paths["save_sp"]),
                            "sha256": self._sha(self.paths["save_sp"]),
                        },
                    },
                    "save_sp": {
                        "predicate": "EXISTS (SELECT 1 FROM AnyTable WHERE ValueColumn = @VALUE)",
                        "message": "Duplicate value",
                        "guard": "RETURN",
                    },
                    "csharp": {
                        "predicate": "HasDuplicate(value)",
                        "message": "Duplicate value",
                        "guard": "return",
                    },
                }
            ],
        }

    def _replace_event_artifact(self, role, source):
        self.paths[role].write_text(source, encoding="utf-8", newline="")

    def _event_integration(self, contract):
        return migration._evaluate_pb_event_preflight_integrations(
            event_save_contract={"inputs": contract},
            migration_preflight_contract=None,
            completion_claims={},
            completion_requested=False,
        )

    def _requested_objects(self):
        return [
            {
                "object_name": "PrivateWindow",
                "object_type": "srw",
                "path": str(self.export_paths["PrivateWindow.srw"]),
            },
            {
                "object_name": "PrivateData",
                "object_type": "srd",
                "path": str(self.export_paths["PrivateData.srd"]),
            },
        ]

    def _export_manifest(self):
        return [
            {
                "path": str(path),
                "object_name": name.rsplit(".", 1)[0],
                "object_type": name.rsplit(".", 1)[1],
                "sha256": self._sha(path),
                "readback_sha256": self._sha(path),
            }
            for name, path in self.export_paths.items()
        ]

    def _gm32_provenance(self, call_id, receipt_id):
        return {
            "producer": "pb-migration-preflight-host",
            "kind": "runtime_invoked_tool_receipt",
            "runtime_invoked": True,
            "call_id": call_id,
            "receipt_id": receipt_id,
            "capabilities": ["pb_export", "pb_export_parse", "pb_export_readback"],
        }

    def _command_semantics(self):
        return {
            "operation": "export_pb_objects",
            "pbl_path": str(self.pbl),
            "pbl_sha256": self._sha(self.pbl),
            "requested_objects": self._requested_objects(),
        }

    def _gm32_command(self):
        return [
            "export-pb-objects",
            str(self.pbl),
            "PrivateWindow",
            "srw",
            "PrivateData",
            "srd",
        ]

    def _event_state_contract(self, forged=False):
        graph = {
            "nodes": [
                {
                    "id": "load",
                    "order": 10,
                    "commands": ["load"],
                    "preconditions": ["ready"],
                    "state_mutations": ["loaded=true"],
                    "calls": ["CallSelectProcedure"],
                    "side_effects": ["grid_refresh"],
                    "timing": {"stage": "before_call"},
                },
                {
                    "id": "save",
                    "order": 20,
                    "commands": ["save"],
                    "preconditions": ["valid"],
                    "state_mutations": ["saved=true"],
                    "calls": ["CallSaveProcedure"],
                    "side_effects": ["message"],
                    "timing": {"stage": "after_call"},
                },
            ],
            "edges": [
                {
                    "id": "load-to-save",
                    "source": "load",
                    "target": "save",
                    "timing": "immediate",
                }
            ],
        }
        artifacts = {}
        for role in ("pb", "csharp"):
            path = self.root / f"{role}-event-state.json"
            raw = json.dumps(
                graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            path.write_bytes(raw)
            artifact_hash = self._sha(path)
            artifacts[role] = {
                "path": str(path),
                "sha256": artifact_hash,
                "graph_sha256": artifact_hash,
            }
        if forged:
            artifacts["csharp"]["sha256"] = "sha256:" + "0" * 64
        return {
            "pb_graph": graph,
            "csharp_graph": graph,
            "pb_artifact": artifacts["pb"],
            "csharp_artifact": artifacts["csharp"],
        }

    def _performance_contract(self):
        before_path = self._write("performance/before.sql", "SELECT 1\n")
        after_path = self._write("performance/after.sql", "SELECT 1\n")
        digest = "sha256:" + "1" * 64

        def receipt(side, path):
            return {
                "receipt_id": f"receipt-{side}",
                "call_id": f"call-{side}",
                "tool_name": "synthetic-sql-profiler",
                "side": side,
                "observed_at": "2026-08-24T12:00:00+09:00",
                "exit_code": 0,
                "errors": [],
                "database": "SyntheticDb",
                "environment": "test",
                "parameters": {"id": 1},
                "sql_path": str(path),
                "sql_sha256": self._sha(path),
                "execution_plan_sha256": digest,
                "logical_reads": 10 if side == "before" else 8,
                "runtime_samples_ms": [10.0, 11.0],
                "result": {
                    "schema_sha256": digest,
                    "row_count": 1,
                    "value_sha256": digest,
                },
            }

        return {
            "claim": "performance equivalence",
            "execution_receipts": [
                receipt("before", before_path),
                receipt("after", after_path),
            ],
        }

    def test_claim_gated_contracts_pass_with_bound_evidence(self):
        result = migration._evaluate_pb_event_preflight_integrations(
            event_save_contract=None,
            migration_preflight_contract=None,
            completion_claims={
                "event_state_parity": True,
                "performance_equivalence": True,
            },
            completion_requested=False,
            event_state_contract=self._event_state_contract(),
            performance_equivalence_contract=self._performance_contract(),
        )

        self.assertTrue(result["validation_allowed"], result)
        self.assertEqual("passed", result["event_state"]["status"])
        self.assertEqual("passed", result["performance_equivalence"]["status"])

    def test_forged_event_state_artifact_is_blocked_when_claimed(self):
        result = migration._evaluate_pb_event_preflight_integrations(
            event_save_contract=None,
            migration_preflight_contract=None,
            completion_claims={"timing_parity": True},
            completion_requested=False,
            event_state_contract=self._event_state_contract(forged=True),
        )

        self.assertFalse(result["validation_allowed"])
        self.assertIn(
            "pb_event_state_artifact_sha256_mismatch",
            result["issue_codes"],
        )

    def test_claimed_event_state_requires_graph_input(self):
        result = migration._evaluate_pb_event_preflight_integrations(
            event_save_contract=None,
            migration_preflight_contract=None,
            completion_claims={"event_state_parity": True},
            completion_requested=True,
        )

        self.assertFalse(result["completion_authorized"])
        self.assertIn("pb_event_state_contract_required", result["issue_codes"])

    def test_unclaimed_optional_contracts_are_not_requested(self):
        result = migration._evaluate_pb_event_preflight_integrations(
            event_save_contract=None,
            migration_preflight_contract=None,
            completion_claims={},
            completion_requested=False,
            event_state_contract=self._event_state_contract(forged=True),
            performance_equivalence_contract={
                "execution_receipts": [{"status": "passed", "verified": True}]
            },
        )

        self.assertTrue(result["validation_allowed"])
        self.assertEqual("not_requested", result["event_state"]["status"])
        self.assertEqual(
            "not_requested", result["performance_equivalence"]["status"]
        )

    def test_claimed_performance_requires_execution_evidence(self):
        result = migration._evaluate_pb_event_preflight_integrations(
            event_save_contract=None,
            migration_preflight_contract=None,
            completion_claims={"tuning": True},
            completion_requested=True,
        )

        self.assertFalse(result["completion_authorized"])
        self.assertIn(
            "pb_performance_execution_receipts_missing",
            result["issue_codes"],
        )

    def _gm31_contract(self):
        project_hash = self._sha(self.project)
        return {
            "expected_project_path": self.project,
            "target_project_receipt": {
                "path": str(self.project),
                "sha256": project_hash,
                "sequence": 1,
            },
            "dependency_receipts": [
                {
                    "kind": "package",
                    "include": "Stable.Dependency",
                    "version": "1.0.0",
                    "owner_project_path": str(self.project),
                    "sequence": 2,
                }
            ],
            "generated_file_receipts": [
                {
                    "path": str(self.generated),
                    "sha256": self._sha(self.generated),
                    "owner_project_path": str(self.project),
                    "inclusion_mode": "sdk_default_compile",
                    "sequence": 3,
                }
            ],
            "project_readback_receipt": {
                "path": str(self.project),
                "sha256": project_hash,
                "sequence": 4,
            },
            "build_invocation_receipt": {
                "call_id": "build-call-1",
                "execution_id": "execution-1",
                "timestamp": "2026-08-24T00:00:00+09:00",
                "executed": True,
                "producer": "test-command-runner",
                "project_path": str(self.project),
                "command": ["dotnet", "build", str(self.project)],
                "sequence": 5,
            },
            "build_output_receipt": {
                "call_id": "build-call-1",
                "execution_id": "execution-1",
                "timestamp": "2026-08-24T00:00:01+09:00",
                "executed": True,
                "producer": "test-command-runner",
                "result_id": "result-1",
                "exit_code": 0,
                "output_receipt": {
                    "path": str(self.build_output),
                    "sha256": self._sha(self.build_output),
                },
                "sequence": 6,
            },
            "completion_receipt": {
                "call_id": "build-call-1",
                "timestamp": "2026-08-24T00:00:02+09:00",
                "sequence": 7,
            },
            "completion_requested": True,
        }

    def _pblscripter(self, usable=True):
        command = self._gm32_command()
        path = self._write(
            "tools/PrivateExport.ps1",
            "# export PB objects\n"
            + " ".join(command)
            + "\n",
        )
        call_id = "pblscripter-call-1"
        output_payload = {
            "receipt_type": "pb_export_runtime_receipt",
            "runtime_invoked": True,
            "call_id": call_id,
            "pbl_path": str(self.pbl),
            "pbl_sha256": self._sha(self.pbl),
            "requested_objects": self._requested_objects(),
            "exported_objects": self._exports(),
            "verifier_provenance": self._gm32_provenance(
                call_id, "pblscripter-output-host-receipt-1"
            ),
            "command_semantics": self._command_semantics(),
            "command": command,
        }
        output = self._write(
            "tools/pblscripter-output.json",
            json.dumps(output_payload, ensure_ascii=False, sort_keys=True),
        )
        return {
            "kind": "script",
            "tool_id": "pblscripter",
            "tool_version": "2026.1",
            "receipt_id": "pblscripter-receipt-1",
            "verified": True,
            "path": str(path),
            "sha256": self._sha(path),
            "usable": usable,
            "capabilities": ["pbl_export"],
            "call_id": "pblscripter-call-1",
            "timestamp": "2026-08-24T00:00:00+09:00",
            "result_id": "pblscripter-result-1",
            "exit_code": 0,
            "output_receipt": {
                "path": str(output),
                "sha256": self._sha(output),
                "call_id": call_id,
            },
            "verifier_provenance": self._gm32_provenance(
                call_id, "pblscripter-host-receipt-1"
            ),
            "command_semantics": self._command_semantics(),
            "command": command,
            "exported_objects": self._exports(),
            "source_pbl_path": str(self.pbl),
            "source_pbl_sha256": self._sha(self.pbl),
            "requested_objects": self._requested_objects(),
        }

    def _orca(self):
        pe_image = bytearray(128)
        pe_image[:2] = b"MZ"
        pe_image[0x3C:0x40] = (0x40).to_bytes(4, "little")
        pe_image[0x40:0x44] = b"PE\0\0"
        orca = self.root / "runtime" / "PBORC.DLL"
        runtime = self.root / "runtime" / "PBVM.DLL"
        orca.parent.mkdir(parents=True, exist_ok=True)
        orca.write_bytes(bytes(pe_image))
        runtime.write_bytes(bytes(pe_image))
        command = self._gm32_command()
        call_id = "orca-call-1"
        output_payload = {
            "receipt_type": "pb_export_runtime_receipt",
            "runtime_invoked": True,
            "call_id": call_id,
            "pbl_path": str(self.pbl),
            "pbl_sha256": self._sha(self.pbl),
            "requested_objects": self._requested_objects(),
            "exported_objects": self._export_manifest(),
            "verifier_provenance": self._gm32_provenance(
                call_id, "orca-output-host-receipt-1"
            ),
            "command_semantics": self._command_semantics(),
            "command": command,
        }
        output = self._write(
            "runtime/orca-output.json",
            json.dumps(output_payload, ensure_ascii=False, sort_keys=True),
        )
        return {
            "selected_version": "one-explicit-version",
            "tool_id": "orca",
            "tool_version": "one-explicit-version",
            "receipt_id": "orca-receipt-1",
            "verified": True,
            "kind": "runtime",
            "capabilities": ["pbl_export"],
            "call_id": "orca-call-1",
            "timestamp": "2026-08-24T00:00:00+09:00",
            "result_id": "orca-result-1",
            "exit_code": 0,
            "output_receipt": {
                "path": str(output),
                "sha256": self._sha(output),
                "call_id": call_id,
            },
            "usable": True,
            "orca_library": {"path": str(orca), "sha256": self._sha(orca)},
            "runtime_libraries": [
                {"path": str(runtime), "sha256": self._sha(runtime)}
            ],
            "verifier_provenance": self._gm32_provenance(
                call_id, "orca-host-receipt-1"
            ),
            "command_semantics": self._command_semantics(),
            "command": command,
            "exported_objects": self._exports(),
            "source_pbl_path": str(self.pbl),
            "source_pbl_sha256": self._sha(self.pbl),
            "requested_objects": self._requested_objects(),
        }

    def _exports(self):
        receipts = []
        call_id = "export-call-1"
        for name, path in self.export_paths.items():
            object_name, object_type = name.rsplit(".", 1)
            receipts.append(
                {
                    "path": str(path),
                    "readback_sha256": self._sha(path),
                    "sha256": self._sha(path),
                    "authority": "current_export",
                    "current": True,
                    "export_batch_id": "batch-1",
                    "exported_from_sha256": self._sha(self.pbl),
                    "source_pbl_path": str(self.pbl),
                    "object_name": object_name,
                    "object_type": object_type,
                    "call_id": call_id,
                    "timestamp": "2026-08-24T00:00:00+09:00",
                    "verifier_provenance": self._gm32_provenance(
                        call_id, "export-host-receipt-1"
                    ),
                    "command_semantics": self._command_semantics(),
                    "command": self._gm32_command(),
                }
            )
        return receipts

    def _acquisition_scope(self):
        return {
            "requested_pbl": {
                "path": str(self.pbl),
                "sha256": self._sha(self.pbl),
            },
            "requested_objects": [
                *self._requested_objects(),
            ],
        }

    def test_event_parity_pass_and_fail_are_merged(self):
        passed = self._event_integration(self._event_contract())
        missing = self._event_contract()
        missing["event_mappings"] = []
        blocked = self._event_integration(missing)

        self.assertTrue(passed["validation_allowed"])
        self.assertEqual("passed", passed["event_save"]["status"])
        self.assertTrue(passed["event_save"]["validator_executed"])
        self.assertFalse(blocked["validation_allowed"])
        self.assertIn("pb_event_mapping_missing", blocked["issue_codes"])

    def test_invented_handler_is_merged(self):
        source = CSHARP.replace(
            "\n}\n",
            "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n",
        )
        self._replace_event_artifact("csharp", source)
        contract = self._event_contract()
        contract["csharp_event_handlers"].append(
            {
                "handler": "ExtraHandler",
                "source_path": str(self.paths["csharp"]),
                "source_sha256": self._sha(self.paths["csharp"]),
            }
        )

        result = self._event_integration(contract)

        self.assertIn("csharp_event_handler_invented", result["issue_codes"])

    def test_code_behind_static_ui_is_merged(self):
        self._replace_event_artifact(
            "csharp",
            CSHARP.replace(
                "ExecuteSave();",
                "this.commandControl = new System.Windows.Forms.Button();\n        ExecuteSave();",
            ),
        )

        result = self._event_integration(self._event_contract())

        self.assertIn("static_ui_owned_by_code_behind", result["issue_codes"])

    def test_save_validation_duplication_is_merged(self):
        self._replace_event_artifact(
            "csharp",
            CSHARP.replace(
                "ExecuteSave();",
                "if (HasDuplicate(value)) return;\n        ExecuteSave();",
            ),
        )

        result = self._event_integration(self._event_contract())

        self.assertIn(
            "save_sp_owned_validation_duplicated_in_csharp",
            result["issue_codes"],
        )

    def test_project_inclusion_and_build_ordering_are_merged(self):
        passed = migration._evaluate_pb_event_preflight_integrations(
            event_save_contract=None,
            migration_preflight_contract={"project_build": self._gm31_contract()},
            completion_claims={},
            completion_requested=False,
        )
        out_of_order = self._gm31_contract()
        out_of_order["build_invocation_receipt"]["sequence"] = 2
        blocked = migration._evaluate_pb_event_preflight_integrations(
            event_save_contract=None,
            migration_preflight_contract={"project_build": out_of_order},
            completion_claims={},
            completion_requested=False,
        )

        self.assertTrue(passed["validation_allowed"])
        self.assertEqual(
            "sdk_default_compile",
            passed["migration_preflight"]["project_build"]["metadata"]
            ["generated_files"][0]["inclusion_mode"],
        )
        self.assertIn("gm31_evidence_order_invalid", blocked["issue_codes"])

    def test_dependency_free_sdk_project_is_allowed_with_correlated_build(self):
        self.project.write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup /></Project>',
            encoding="utf-8",
        )
        contract = self._gm31_contract()
        contract["dependency_receipts"] = []

        result = migration._evaluate_pb_event_preflight_integrations(
            event_save_contract=None,
            migration_preflight_contract={"project_build": contract},
            completion_claims={},
            completion_requested=False,
        )

        project = result["migration_preflight"]["project_build"]
        self.assertTrue(project["success"], project)
        self.assertTrue(project["validator_executed"])
        self.assertTrue(project["metadata"]["dependency_free_project_allowed"])
        self.assertTrue(project["metadata"]["execution_correlated_build_receipt"])

    def test_project_build_without_execution_correlation_is_blocked(self):
        contract = self._gm31_contract()
        contract["build_output_receipt"].pop("result_id")

        result = migration._evaluate_pb_event_preflight_integrations(
            event_save_contract=None,
            migration_preflight_contract={"project_build": contract},
            completion_claims={},
            completion_requested=False,
        )

        self.assertIn(
            "gm31_build_execution_correlation_invalid",
            result["issue_codes"],
        )

    def test_export_strategy_uses_explicit_pblscripter_rung(self):
        strategy = migration.build_pbl_export_strategy(
            {
                **self._acquisition_scope(),
                "pblscripter": self._pblscripter(),
                "orca_runtime": self._orca(),
            }
        )

        self.assertEqual("pblscripter", strategy["provider"])
        self.assertEqual(
            "pblscripter", strategy["acquisition_preflight"]["metadata"]["selected_method"]
        )
        self.assertTrue(strategy["acquisition_preflight"]["metadata"]["explicit_inputs_only"])
        self.assertEqual(0, strategy["acquisition_preflight"]["metadata"]["executed_process_count"])

    def test_export_strategy_uses_one_explicit_orca_rung(self):
        strategy = migration.build_pbl_export_strategy(
            {
                **self._acquisition_scope(),
                "pblscripter": self._pblscripter(usable=False),
                "orca_runtime": self._orca(),
            }
        )

        acquisition = strategy["acquisition_preflight"]
        self.assertEqual("orca", strategy["provider"])
        self.assertTrue(acquisition["metadata"]["explicit_inputs_only"])
        self.assertEqual("orca", acquisition["metadata"]["selected_method"])
        self.assertEqual([], acquisition["metadata"]["versions_tried"])
        self.assertFalse(acquisition["metadata"]["orca_executed"])

    def test_export_strategy_falls_back_to_current_exports(self):
        strategy = migration.build_pbl_export_strategy(
            {
                **self._acquisition_scope(),
                "exported_objects": [
                    {
                        **receipt,
                        "exported_from_sha256": self._sha(self.pbl),
                    }
                    for receipt in self._exports()
                ],
            }
        )

        self.assertEqual("pre_exported_source", strategy["provider"])
        self.assertEqual(
            "current_exports", strategy["acquisition_preflight"]["metadata"]["selected_method"]
        )
        self.assertTrue(strategy["acquisition_preflight"]["metadata"]["explicit_inputs_only"])

    def test_export_strategy_blocks_when_explicit_ladder_has_no_rung(self):
        strategy = migration.build_pbl_export_strategy(
            {"acquisition_preflight": self._acquisition_scope()}
        )

        self.assertEqual("blocked", strategy["status"])
        self.assertEqual("unresolved", strategy["provider"])
        self.assertIn(
            "gm32_acquisition_unresolved",
            strategy["acquisition_preflight"]["issue_codes"],
        )

    def test_arbitrary_readable_script_without_tool_identity_is_blocked(self):
        tool = self._pblscripter()
        for key in ("tool_id", "tool_version", "receipt_id", "verified"):
            tool.pop(key)

        strategy = migration.build_pbl_export_strategy(
            {**self._acquisition_scope(), "pblscripter": tool}
        )

        self.assertEqual("blocked", strategy["status"])
        self.assertIn(
            "gm32_pblscripter_identity_invalid",
            strategy["acquisition_preflight"]["issue_codes"],
        )

    def test_orchestration_metadata_and_completion_gate(self):
        profile_identity = {
            "profile_id": "profile",
            "profile_version": "1",
            "profile_hash": "sha256:" + "c" * 64,
        }
        loaded = HarnessResult(
            success=True,
            metadata={"status": "loaded", "profile_consumption": profile_identity},
        )
        validated = HarnessResult(
            success=True,
            metadata={
                "profile_consumption": {**profile_identity, "consumed": True},
                "target_artifact_binding": {},
                "program_form_contract": {"expected_form_class": "AnyForm"},
                "program_key": "ANY",
            },
        )
        binding = {"status": "bound"}
        release = {
            "status": "passed",
            "binding": binding,
            "verifier_history": [],
            "verifier_history_correlation": {
                "status": "correlated",
                "binding_verification_id": "verify-1",
                "history_verification_id": "verify-1",
            },
        }

        def completion_receipt(name, _evidence, required, **_kwargs):
            return {
                "name": name,
                "required_for_claim": required,
                "status": "passed" if required else "not_claimed",
                "receipt_id": "receipt-" + name,
                "run_id": "run-1",
                "correlation_id": "correlation-1",
                "target_path": str(self.project),
                "issues": [],
            }

        common = {
            "csharp_source_text": CSHARP,
            "designer_source_text": DESIGNER,
            "original_sql_text": SAVE_SP,
            "formatted_sql_text": SAVE_SP,
            "profile_id": profile_identity["profile_id"],
            "profile_version": profile_identity["profile_version"],
            "profile_hash": profile_identity["profile_hash"],
            "program_key": "ANY",
            "completion_claims": {
                "completion": True,
                "requires_event_save_contract": True,
            },
            "event_save_contract": {"inputs": self._event_contract()},
        }
        governance = {
            "status": "passed",
            "authority_supplied": True,
            "directive_ledger_supplied": True,
            "validation_allowed": True,
            "completion_authorized": True,
            "issues": [],
            "issue_codes": [],
        }
        with (
            mock.patch.object(migration, "load_packaged_migration_profile", return_value=loaded),
            mock.patch.object(migration, "verify_migration_generated_csharp_style", return_value=validated),
            mock.patch.object(migration, "verify_pb_migration_sp_generation_contract", return_value=validated),
            mock.patch.object(migration, "_execute_pb_sql_final_response_binding", return_value=(True, {})),
            mock.patch.object(migration, "_pb_sql_release_evidence_views", return_value=(True, binding, release)),
            mock.patch.object(migration, "_evaluate_pb_migration_orchestration_contracts", return_value=governance),
            mock.patch.object(migration, "_validate_completion_receipt", side_effect=completion_receipt),
        ):
            passed = migration.orchestrate_pb_migration_validation(**common)
            missing = migration.orchestrate_pb_migration_validation(
                **{**common, "event_save_contract": None}
            )

        integration = passed.metadata["evidence"]["pb_contract_integrations"]
        self.assertTrue(passed.success, passed.metadata)
        self.assertTrue(integration["completion_authorized"])
        self.assertEqual("passed", integration["event_save"]["status"])
        self.assertFalse(missing.success)
        self.assertIn(
            "pb_event_save_contract_required",
            missing.metadata["evidence"]["pb_contract_integrations"]["issue_codes"],
        )


if __name__ == "__main__":
    unittest.main()
