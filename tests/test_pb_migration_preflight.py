import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.skills.pb_migration_preflight import (
    ISSUE_GM31_BUILD_FAILED,
    ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID,
    ISSUE_GM31_BUILD_RECEIPT_INVALID,
    ISSUE_GM31_DEPENDENCY_NOT_IN_PROJECT,
    ISSUE_GM31_DEPENDENCY_OWNER_MISMATCH,
    ISSUE_GM31_EVIDENCE_ORDER_INVALID,
    ISSUE_GM31_EXPLICIT_COMPILE_MISSING,
    ISSUE_GM31_DEPENDENCY_INVALID,
    ISSUE_GM31_DEPENDENCY_SET_MISMATCH,
    ISSUE_GM31_DEPENDENCY_VERSION_DRIFT,
    ISSUE_GM31_RECEIPT_DUPLICATE,
    ISSUE_GM31_INCLUSION_INVALID,
    ISSUE_GM31_PROJECT_READBACK_INVALID,
    ISSUE_GM31_SDK_DEFAULT_UNAVAILABLE,
    ISSUE_GM31_TARGET_PROJECT_MISMATCH,
    ISSUE_GM32_ACQUISITION_UNRESOLVED,
    ISSUE_GM32_DISCOVERY_INPUT_FORBIDDEN,
    ISSUE_GM32_EXPORT_NOT_CURRENT,
    ISSUE_GM32_EXPORT_BINDING_MISMATCH,
    ISSUE_GM32_EXECUTION_CORRELATION_INVALID,
    ISSUE_GM32_RECEIPT_DUPLICATE,
    ISSUE_GM32_TOOL_CAPABILITY_INVALID,
    ISSUE_GM32_TOOL_IDENTITY_INVALID,
    ISSUE_GM32_REQUESTED_PBL_INVALID,
    ISSUE_GM32_REQUESTED_OBJECT_SET_INVALID,
    plan_gm32_acquisition,
    verify_gm31_project_build_contract,
)


class PbMigrationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name).resolve()
        self.project = self.root / "Target.Private.csproj"
        self.generated = self.root / "Generated" / "PrivateForm.cs"
        self.pbl = self.root / "source" / "Private.pbl"
        self.build_output = self.root / "receipts" / "build-output.txt"
        self.generated.parent.mkdir()
        self.generated.write_text("partial class PrivateForm {}\n", encoding="utf-8")
        self.pbl.parent.mkdir()
        self.pbl.write_bytes(b"private-pbl-bytes")
        self.build_output.parent.mkdir()
        self.build_output.write_text("Build succeeded\n", encoding="utf-8")
        self._write_sdk_project()

    def tearDown(self):
        self.temporary_directory.cleanup()

    @staticmethod
    def _sha(path):
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    def _write_sdk_project(self, extra_property=""):
        self.project.write_text(
            "<Project Sdk=\"Microsoft.NET.Sdk\">"
            f"<PropertyGroup>{extra_property}</PropertyGroup>"
            "<ItemGroup><PackageReference Include=\"Stable.Dependency\" Version=\"1.0.0\" /></ItemGroup>"
            "</Project>",
            encoding="utf-8",
        )

    def _write_explicit_project(self, include="Generated\\PrivateForm.cs"):
        self.project.write_text(
            "<Project><ItemGroup>"
            "<Reference Include=\"Stable.Dependency\" />"
            f"<Compile Include=\"{include}\" />"
            "</ItemGroup></Project>",
            encoding="utf-8",
        )

    def _gm31(self, *, mode="sdk_default_compile", dependency_kind="package", completion_requested=True, dependency_receipts=None):
        project_hash = self._sha(self.project)
        dependency = {
            "kind": dependency_kind,
            "include": "Stable.Dependency",
            "version": "1.0.0" if dependency_kind == "package" else "",
            "owner_project_path": str(self.project),
            "sequence": 2,
        }
        generated = {
            "path": str(self.generated),
            "sha256": self._sha(self.generated),
            "owner_project_path": str(self.project),
            "inclusion_mode": mode,
            "sequence": 3,
        }
        if mode == "explicit_compile_include":
            generated["compile_include"] = "Generated\\PrivateForm.cs"
        return {
            "expected_project_path": self.project,
            "target_project_receipt": {
                "path": str(self.project),
                "sha256": project_hash,
                "sequence": 1,
            },
            "dependency_receipts": [dependency] if dependency_receipts is None else dependency_receipts,
            "generated_file_receipts": [generated],
            "project_readback_receipt": {
                "path": str(self.project),
                "sha256": project_hash,
                "sequence": 4,
            },
            "build_invocation_receipt": {
                "call_id": "build-call-1",
                "timestamp": "2026-08-24T10:00:00+09:00",
                "producer": "test-command-runner",
                "project_path": str(self.project),
                "command": ["dotnet", "build", str(self.project)],
                "sequence": 5,
            },
            "build_output_receipt": {
                "call_id": "build-call-1",
                "timestamp": "2026-08-24T10:00:01+09:00",
                "result_id": "result-1",
                "exit_code": 0,
                "output_receipt": {"path": str(self.build_output), "sha256": self._sha(self.build_output)},
                "sequence": 6,
            },
            "completion_receipt": {
                "call_id": "build-call-1",
                "timestamp": "2026-08-24T10:00:02+09:00",
                "sequence": 7,
            },
            "completion_requested": completion_requested,
        }

    def _write_artifact(self, relative, content=b"receipt"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def _requested_objects(self):
        return [
            {"object_name": "PrivateWindow", "object_type": "srw"},
            {"object_name": "PrivateData", "object_type": "srd"},
            {"object_name": "PrivateUser", "object_type": "sru"},
        ]

    def _provenance(self, call_id):
        return {
            "producer": "pb-migration-preflight-host",
            "kind": "runtime_invoked_tool_receipt",
            "runtime_invoked": True,
            "receipt_id": f"host-{call_id}",
            "call_id": call_id,
            "capabilities": ["pb_export", "pb_export_parse", "pb_export_readback"],
        }

    def _command_semantics(self, call_id):
        return {
            "operation": "export_pb_objects",
            "pbl_path": str(self.pbl),
            "pbl_sha256": self._sha(self.pbl),
            "requested_objects": self._requested_objects(),
        }

    @staticmethod
    def _pb_export_content(name, object_type):
        body = "datawindow\n" if object_type == "srd" else "global type {} from {}\n".format(name, "window" if object_type == "srw" else "userobject")
        return f"$PBExportHeader${name}.{object_type}\n{body}$PBExportEnd$\n".encode("utf-8")

    @staticmethod
    def _pe_fixture():
        payload = bytearray(128)
        payload[:2] = b"MZ"
        payload[0x3C:0x40] = (64).to_bytes(4, "little")
        payload[64:68] = b"PE\0\0"
        return bytes(payload)

    def _runtime_output(self, relative, call_id, exports):
        payload = {
            "receipt_type": "pb_export_runtime_receipt",
            "runtime_invoked": True,
            "call_id": call_id,
            "pbl_path": str(self.pbl),
            "pbl_sha256": self._sha(self.pbl),
            "requested_objects": self._requested_objects(),
            "verifier_provenance": self._provenance(call_id),
            "command": ["pb-export-host", str(self.pbl), *[item for obj in self._requested_objects() for item in (obj["object_name"], obj["object_type"]) ]],
            "command_semantics": self._command_semantics(call_id),
            "exported_objects": [
                {
                    "path": item["path"],
                    "sha256": item["readback_sha256"],
                    "object_name": item["object_name"],
                    "object_type": item["object_type"],
                }
                for item in exports
            ],
        }
        return self._write_artifact(relative, json.dumps(payload, sort_keys=True).encode("utf-8"))

    def _pblscripter(self, *, usable=True):
        call_id = "pbl-call-1"
        path = self._write_artifact(
            "tools/PrivateExport.ps1",
            ("Export-PBL -PblPath '{}' -Objects PrivateWindow.srw PrivateData.srd PrivateUser.sru\n".format(self.pbl)).encode("utf-8"),
        )
        exports = self._exports(call_id=call_id)
        output = self._runtime_output("receipts/pblscripter-output.json", call_id, exports)
        return {
            "kind": "script",
            "tool_id": "pblscripter",
            "tool_version": "7.0",
            "receipt_id": "pblscripter-receipt-1",
            "capabilities": ["pbl_export"],
            "path": str(path),
            "sha256": self._sha(path),
            "usable": usable,
            "call_id": call_id,
            "timestamp": "2026-08-24T10:00:00+09:00",
            "result_id": "pbl-result-1",
            "exit_code": 0,
            "source_pbl_path": str(self.pbl),
            "source_pbl_sha256": self._sha(self.pbl),
            "requested_objects": self._requested_objects(),
            "verifier_provenance": self._provenance(call_id),
            "command": ["powershell", "-File", str(path), str(self.pbl), "PrivateWindow", "srw", "PrivateData", "srd", "PrivateUser", "sru"],
            "command_semantics": self._command_semantics(call_id),
            "exported_objects": exports,
            "output_receipt": {
                "path": str(output),
                "sha256": self._sha(output),
                "call_id": call_id,
            },
        }

    def _orca(self):
        call_id = "orca-call-1"
        orca = self._write_artifact("runtime/PBORC.DLL", self._pe_fixture())
        runtime = self._write_artifact("runtime/PBVM.DLL", self._pe_fixture())
        exports = self._exports(call_id=call_id)
        output = self._runtime_output("receipts/orca-output.json", call_id, exports)
        return {
            "selected_version": "one-explicit-version",
            "tool_id": "orca",
            "tool_version": "one-explicit-version",
            "receipt_id": "orca-receipt-1",
            "kind": "runtime",
            "capabilities": ["pbl_export"],
            "call_id": call_id,
            "timestamp": "2026-08-24T10:00:00+09:00",
            "result_id": "orca-result-1",
            "exit_code": 0,
            "source_pbl_path": str(self.pbl),
            "source_pbl_sha256": self._sha(self.pbl),
            "requested_objects": self._requested_objects(),
            "verifier_provenance": self._provenance(call_id),
            "command": ["orca-host", str(self.pbl), "PrivateWindow", "srw", "PrivateData", "srd", "PrivateUser", "sru"],
            "command_semantics": self._command_semantics(call_id),
            "exported_objects": exports,
            "output_receipt": {
                "path": str(output),
                "sha256": self._sha(output),
                "call_id": call_id,
            },
            "orca_library": {"path": str(orca), "sha256": self._sha(orca)},
            "runtime_libraries": [
                {"path": str(runtime), "sha256": self._sha(runtime)}
            ],
        }

    def _exports(self, *, current=True, batch="batch-1", call_id="export-call-1"):
        source_hash = self._sha(self.pbl)
        receipts = []
        for name in ("objects/PrivateWindow.srw", "objects/PrivateData.srd", "objects/PrivateUser.sru"):
            object_path = Path(name)
            object_name = object_path.stem
            object_type = object_path.suffix.lstrip(".")
            path = self._write_artifact(name, self._pb_export_content(object_name, object_type))
            receipts.append(
                {
                    "path": str(path),
                    "readback_sha256": self._sha(path),
                    "authority": "current_export" if current else "historical_export",
                    "current": current,
                    "export_batch_id": batch,
                    "exported_from_sha256": source_hash,
                    "source_pbl_path": str(self.pbl),
                    "object_name": object_name,
                    "object_type": object_type,
                    "call_id": call_id,
                    "timestamp": "2026-08-24T10:00:00+09:00",
                    "verifier_provenance": self._provenance(call_id),
                    "command": ["pb-export-host", str(self.pbl), "PrivateWindow", "srw", "PrivateData", "srd", "PrivateUser", "sru"],
                    "command_semantics": self._command_semantics(call_id),
                }
            )
        return receipts

    def _gm32_scope(self):
        return {
            "requested_pbl": {"path": str(self.pbl), "sha256": self._sha(self.pbl)},
            "requested_objects": [
                *self._requested_objects(),
            ],
        }

    def test_gm31_accepts_exact_sdk_default_inclusion_and_ordered_receipts(self):
        result = verify_gm31_project_build_contract(**self._gm31())

        self.assertTrue(result.success, result.to_dict())
        self.assertTrue(result.metadata["completion_authorized"])
        self.assertFalse(result.metadata["build_executed_by_module"])

    def test_gm31_accepts_explicit_compile_include(self):
        self._write_explicit_project()

        result = verify_gm31_project_build_contract(
            **self._gm31(mode="explicit_compile_include", dependency_kind="assembly")
        )

        self.assertTrue(result.success, result.to_dict())

    def test_gm31_rejects_a_different_target_project_receipt(self):
        arguments = self._gm31()
        arguments["target_project_receipt"]["path"] = str(self.root / "Other.csproj")

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_TARGET_PROJECT_MISMATCH, result.issue_codes)

    def test_gm31_rejects_dependency_owned_by_another_project(self):
        arguments = self._gm31()
        arguments["dependency_receipts"][0]["owner_project_path"] = str(self.root / "Other.csproj")

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_DEPENDENCY_OWNER_MISMATCH, result.issue_codes)

    def test_gm31_rejects_dependency_not_present_in_project_readback(self):
        arguments = self._gm31()
        arguments["dependency_receipts"][0]["include"] = "Missing.Dependency"

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_DEPENDENCY_NOT_IN_PROJECT, result.issue_codes)

    def test_gm31_rejects_missing_explicit_compile_include(self):
        self._write_explicit_project(include="Generated\\Different.cs")

        result = verify_gm31_project_build_contract(
            **self._gm31(mode="explicit_compile_include", dependency_kind="assembly")
        )

        self.assertIn(ISSUE_GM31_EXPLICIT_COMPILE_MISSING, result.issue_codes)

    def test_gm31_rejects_sdk_default_when_default_compile_items_are_disabled(self):
        self._write_sdk_project("<EnableDefaultCompileItems>false</EnableDefaultCompileItems>")

        result = verify_gm31_project_build_contract(**self._gm31())

        self.assertIn(ISSUE_GM31_SDK_DEFAULT_UNAVAILABLE, result.issue_codes)

    def test_gm31_rejects_sdk_default_when_all_default_items_are_disabled(self):
        self._write_sdk_project("<EnableDefaultItems>false</EnableDefaultItems>")

        result = verify_gm31_project_build_contract(**self._gm31())

        self.assertIn(ISSUE_GM31_SDK_DEFAULT_UNAVAILABLE, result.issue_codes)

    def test_gm31_uses_last_evaluated_imported_property_value(self):
        imported = self._write_artifact(
            "Directory.Build.props",
            b"<Project><PropertyGroup><EnableDefaultItems>false</EnableDefaultItems></PropertyGroup></Project>",
        )
        self.project.write_text(
            f'<Project Sdk="Microsoft.NET.Sdk"><Import Project="{imported}" />'
            "<PropertyGroup><EnableDefaultItems>true</EnableDefaultItems></PropertyGroup>"
            "<ItemGroup><PackageReference Include=\"Stable.Dependency\" Version=\"1.0.0\" /></ItemGroup></Project>",
            encoding="utf-8",
        )

        result = verify_gm31_project_build_contract(**self._gm31())

        self.assertTrue(result.success, result.to_dict())

    def test_gm31_later_import_can_disable_defaults_after_project_property(self):
        imported = self._write_artifact(
            "Directory.Build.targets",
            b"<Project><PropertyGroup><EnableDefaultCompileItems>false</EnableDefaultCompileItems></PropertyGroup></Project>",
        )
        self.project.write_text(
            f'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><EnableDefaultCompileItems>true</EnableDefaultCompileItems></PropertyGroup>'
            f'<Import Project="{imported}" /><ItemGroup><PackageReference Include="Stable.Dependency" Version="1.0.0" /></ItemGroup></Project>',
            encoding="utf-8",
        )

        result = verify_gm31_project_build_contract(**self._gm31())

        self.assertIn(ISSUE_GM31_SDK_DEFAULT_UNAVAILABLE, result.issue_codes)

    def test_gm31_rejects_project_readback_hash_drift(self):
        arguments = self._gm31()
        arguments["project_readback_receipt"]["sha256"] = "sha256:" + "0" * 64

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_PROJECT_READBACK_INVALID, result.issue_codes)

    def test_gm31_build_cannot_precede_dependency_and_inclusion_evidence(self):
        arguments = self._gm31()
        arguments["build_invocation_receipt"]["sequence"] = 2

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_EVIDENCE_ORDER_INVALID, result.issue_codes)
        self.assertFalse(result.metadata["completion_authorized"])

    def test_gm31_output_must_follow_and_correlate_to_invocation(self):
        arguments = self._gm31()
        arguments["build_output_receipt"].update(sequence=5, call_id="other")

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_EVIDENCE_ORDER_INVALID, result.issue_codes)
        self.assertIn(ISSUE_GM31_BUILD_RECEIPT_INVALID, result.issue_codes)

    def test_gm31_failed_build_blocks_completion(self):
        arguments = self._gm31()
        arguments["build_output_receipt"]["exit_code"] = 1

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_BUILD_FAILED, result.issue_codes)
        self.assertFalse(result.metadata["completion_authorized"])

    def test_gm31_requires_dependency_and_generated_file_evidence(self):
        arguments = self._gm31()
        arguments["dependency_receipts"] = []
        arguments["generated_file_receipts"] = []

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_DEPENDENCY_SET_MISMATCH, result.issue_codes)
        self.assertIn(ISSUE_GM31_INCLUSION_INVALID, result.issue_codes)

    def test_gm32_prefers_usable_explicit_pblscripter(self):
        result = plan_gm32_acquisition(
            pblscripter=self._pblscripter(),
            orca_runtime=self._orca(),
            exported_objects=self._exports(),
            **self._gm32_scope(),
        )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual("pblscripter", result.metadata["selected_method"])
        self.assertEqual(0, result.metadata["executed_process_count"])

    def test_gm32_falls_from_unusable_pblscripter_to_one_selected_orca(self):
        result = plan_gm32_acquisition(
            pblscripter=self._pblscripter(usable=False),
            orca_runtime=self._orca(),
            **self._gm32_scope(),
        )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual("orca", result.metadata["selected_method"])
        self.assertEqual([], result.metadata["versions_tried"])
        self.assertFalse(result.metadata["orca_executed"])

    def test_gm32_uses_current_exports_only_after_tool_rungs_are_absent(self):
        result = plan_gm32_acquisition(exported_objects=self._exports(), **self._gm32_scope())

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual("current_exports", result.metadata["selected_method"])
        for receipt in result.metadata["selected_receipts"]:
            self.assertEqual(receipt["requested_sha256"], receipt["readback_sha256"])

    def test_gm32_never_treats_stale_exports_as_current(self):
        result = plan_gm32_acquisition(exported_objects=self._exports(current=False), **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertEqual("unresolved", result.metadata["selected_method"])
        self.assertFalse(result.metadata["stale_exports_accepted"])
        self.assertIn(ISSUE_GM32_EXPORT_NOT_CURRENT, result.issue_codes)
        self.assertIn(ISSUE_GM32_ACQUISITION_UNRESOLVED, result.issue_codes)

    def test_gm32_hash_drift_makes_exports_unusable(self):
        exports = self._exports()
        exports[0]["readback_sha256"] = "sha256:" + "0" * 64

        result = plan_gm32_acquisition(exported_objects=exports, **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertIn(ISSUE_GM32_ACQUISITION_UNRESOLVED, result.issue_codes)

    def test_gm32_mixed_export_batches_are_not_current_as_one_receipt_set(self):
        exports = self._exports()
        exports[1]["export_batch_id"] = "another-batch"

        result = plan_gm32_acquisition(exported_objects=exports, **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertIn(ISSUE_GM32_ACQUISITION_UNRESOLVED, result.issue_codes)

    def test_gm32_blocks_when_no_explicit_rung_is_usable(self):
        result = plan_gm32_acquisition()

        self.assertFalse(result.success)
        self.assertEqual("block", result.metadata["planned_action"])
        self.assertIn(ISSUE_GM32_ACQUISITION_UNRESOLVED, result.issue_codes)

    def test_gm32_rejects_multi_version_and_root_discovery_metadata(self):
        orca = self._orca()
        orca["versions"] = ["one", "two"]
        orca["search_root"] = str(self.root)

        result = plan_gm32_acquisition(orca_runtime=orca, **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertEqual(2, result.issue_codes.count(ISSUE_GM32_DISCOVERY_INPUT_FORBIDDEN))
        self.assertFalse(result.metadata["root_scan_performed"])

    def test_gm31_allows_a_genuinely_dependency_free_sdk_project(self):
        self._write_sdk_project()
        self.project.write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup /></Project>', encoding="utf-8")

        result = verify_gm31_project_build_contract(**self._gm31(dependency_receipts=[]))

        self.assertTrue(result.success, result.to_dict())
        self.assertTrue(result.metadata["dependency_free_project_allowed"])

    def test_gm31_rejects_duplicate_dependencies_before_mapping(self):
        dependency = self._gm31()["dependency_receipts"][0]
        arguments = self._gm31(dependency_receipts=[dependency, {**dependency, "sequence": 8}])

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_RECEIPT_DUPLICATE, result.issue_codes)

    def test_gm31_rejects_dependency_version_drift(self):
        arguments = self._gm31()
        arguments["dependency_receipts"][0]["version"] = "9.9.9"

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_DEPENDENCY_VERSION_DRIFT, result.issue_codes)

    def test_gm31_exit_zero_without_timestamp_and_output_artifact_is_not_evidence(self):
        arguments = self._gm31()
        arguments["build_invocation_receipt"].pop("timestamp")
        arguments["build_output_receipt"].pop("output_receipt")

        result = verify_gm31_project_build_contract(**arguments)

        self.assertIn(ISSUE_GM31_BUILD_EXECUTION_CORRELATION_INVALID, result.issue_codes)
        self.assertIn(ISSUE_GM31_BUILD_RECEIPT_INVALID, result.issue_codes)

    def test_gm32_readable_script_status_verified_and_exit_zero_are_not_evidence(self):
        path = self._write_artifact("tools/arbitrary.ps1", b"Write-Output forged")
        result = plan_gm32_acquisition(
            pblscripter={
                "kind": "script",
                "path": str(path),
                "sha256": self._sha(path),
                "usable": True,
                "verified": True,
                "exit_code": 0,
            },
            **self._gm32_scope(),
        )

        self.assertFalse(result.success)
        self.assertIn(ISSUE_GM32_TOOL_IDENTITY_INVALID, result.issue_codes)
        self.assertIn(ISSUE_GM32_TOOL_CAPABILITY_INVALID, result.issue_codes)
        self.assertIn(ISSUE_GM32_EXECUTION_CORRELATION_INVALID, result.issue_codes)

    def test_gm32_rejects_structurally_invalid_export_bytes_with_self_consistent_receipts(self):
        exports = self._exports()
        exports[0]["path"] = str(self._write_artifact("objects/PrivateWindow.srw", b"arbitrary ORCA output bytes"))
        exports[0]["readback_sha256"] = self._sha(Path(exports[0]["path"]))

        result = plan_gm32_acquisition(exported_objects=exports, **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertIn("gm32_export_structure_invalid", result.issue_codes)

    def test_gm32_rejects_arbitrary_orca_runtime_bytes_even_with_matching_ids(self):
        orca = self._orca()
        library_path = Path(orca["orca_library"]["path"])
        library_path.write_bytes(b"arbitrary ORCA DLL bytes")
        orca["orca_library"]["sha256"] = self._sha(library_path)

        result = plan_gm32_acquisition(orca_runtime=orca, **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertIn("gm32_orca_runtime_unusable", result.issue_codes)

    def test_gm32_rejects_arbitrary_runtime_output_bytes_even_with_matching_ids(self):
        orca = self._orca()
        output_path = Path(orca["output_receipt"]["path"])
        output_path.write_bytes(b"arbitrary export output bytes")
        orca["output_receipt"]["sha256"] = self._sha(output_path)

        result = plan_gm32_acquisition(orca_runtime=orca, **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertIn("gm32_verifier_provenance_invalid", result.issue_codes)

    def test_gm32_rejects_arbitrary_script_bytes_even_with_matching_ids(self):
        tool = self._pblscripter()
        script_path = Path(tool["path"])
        script_path.write_bytes(b"arbitrary script bytes")
        tool["sha256"] = self._sha(script_path)

        result = plan_gm32_acquisition(pblscripter=tool, **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertIn("gm32_tool_identity_invalid", result.issue_codes)

    def test_gm32_rejects_self_consistent_tool_ids_without_runtime_provenance(self):
        tool = self._pblscripter()
        tool.pop("verifier_provenance")
        tool.pop("command_semantics")

        result = plan_gm32_acquisition(pblscripter=tool, **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertIn("gm32_verifier_provenance_invalid", result.issue_codes)
        self.assertIn("gm32_command_semantics_invalid", result.issue_codes)

    def test_gm32_rejects_selected_tool_pbl_and_object_scope_drift(self):
        other_pbl = self._write_artifact("source/Other.pbl", b"other")
        tool = self._pblscripter()
        tool["source_pbl_path"] = str(other_pbl)
        tool["source_pbl_sha256"] = self._sha(other_pbl)
        scope = self._gm32_scope()
        scope["requested_objects"] = [{"object_name": "PrivateWindow", "object_type": "srw"}]

        result = plan_gm32_acquisition(pblscripter=tool, **scope)

        self.assertFalse(result.success)
        self.assertIn(ISSUE_GM32_EXPORT_BINDING_MISMATCH, result.issue_codes)

    def test_gm32_rejects_duplicate_export_receipts_before_object_mapping(self):
        exports = self._exports()
        exports.append({**exports[0], "sequence": 99})

        result = plan_gm32_acquisition(exported_objects=exports, **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertIn(ISSUE_GM32_RECEIPT_DUPLICATE, result.issue_codes)

    def test_gm32_rejects_selected_orca_version_or_capability_drift(self):
        orca = self._orca()
        orca["tool_version"] = "different-version"
        orca["capabilities"] = []

        result = plan_gm32_acquisition(orca_runtime=orca, **self._gm32_scope())

        self.assertFalse(result.success)
        self.assertIn(ISSUE_GM32_TOOL_CAPABILITY_INVALID, result.issue_codes)
        self.assertIn("gm32_orca_selection_invalid", result.issue_codes)

    def test_contract_is_private_name_agnostic(self):
        first = plan_gm32_acquisition(pblscripter=self._pblscripter(), **self._gm32_scope())
        other_path = self._write_artifact(
            "tools/UnrelatedName.ps1",
            ("Export-PBL -PblPath '{}' -Objects PrivateWindow.srw PrivateData.srd PrivateUser.sru\n".format(self.pbl)).encode("utf-8"),
        )
        second_tool = self._pblscripter()
        second_tool["path"] = str(other_path)
        second_tool["sha256"] = self._sha(other_path)
        second = plan_gm32_acquisition(
            pblscripter=second_tool,
            **self._gm32_scope(),
        )

        self.assertEqual(first.success, second.success)
        self.assertEqual(first.metadata["selected_method"], second.metadata["selected_method"])
        self.assertEqual(first.metadata["planned_action"], second.metadata["planned_action"])

    def test_module_and_tests_parse_and_module_has_no_execution_or_scan_api(self):
        project = Path(__file__).resolve().parents[1]
        module_path = project / "src" / "skills" / "pb_migration_preflight.py"
        test_path = project / "tests" / "test_pb_migration_preflight.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))

        imports = set()
        attributes = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Attribute):
                attributes.add(node.attr)
        self.assertTrue(imports.isdisjoint({"glob", "os", "subprocess"}))
        self.assertTrue(attributes.isdisjoint({"glob", "rglob", "walk", "run", "Popen"}))


if __name__ == "__main__":
    unittest.main()
