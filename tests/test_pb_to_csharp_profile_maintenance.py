from __future__ import annotations

import hashlib
import inspect
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.skills import pb_to_csharp_profile_maintenance as maintenance
from src.skills.pb_to_csharp_profile_maintenance import build_profile_update_candidate


class PbToCSharpProfileMaintenanceTests(unittest.TestCase):
    def _write_pair(
        self,
        root: str,
        *,
        source_name: str = "Screen.cs",
        designer_name: str = "Screen.Designer.cs",
        source_class: str = "ScreenForm",
        designer_class: str = "ScreenForm",
        source_header: str = "// ARTIFACT-ID: screen-code\n",
        designer_header: str = "// ARTIFACT-ID: screen-designer\n",
        method_name: str = "CallSelectProcedure",
    ) -> tuple[list[str], dict[str, str]]:
        source = Path(root) / source_name
        designer = Path(root) / designer_name
        source.write_text(
            source_header
            + f"""public partial class {source_class}
{{
    protected void SearchCommand() {{ {method_name}(); }}
    private void {method_name}() {{ }}
}}
""",
            encoding="utf-8",
        )
        designer.write_text(
            designer_header
            + f"""public partial class {designer_class}
{{
    private KoneLib.Controls.u_TextEdit txtAMT;
    private void InitializeComponent()
    {{
        this.txtAMT = new KoneLib.Controls.u_TextEdit();
        this.txtAMT.BindingField = "AMT";
    }}
}}
""",
            encoding="utf-8",
        )
        paths = [str(source.resolve()), str(designer.resolve())]
        hashes = {
            path: "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in paths
        }
        return paths, hashes

    def _contract(self, paths: list[str], hashes: dict[str, str]) -> dict[str, object]:
        provenance = {
            path: {
                "source_system": "controlled-export",
                "capture_id": f"capture-{index}",
                "captured_by": f"capture-operator-{index}",
                "independent_reviewer": f"provenance-reviewer-{index}",
            }
            for index, path in enumerate(paths)
        }
        custody = {
            path: {
                "custodian": f"custody-operator-{index}",
                "receipt_id": f"receipt-{index}",
                "acquired_at": "2026-08-24T09:00:00+09:00",
            }
            for index, path in enumerate(paths)
        }
        return {
            "procedure_name": "SP_SCREEN_SELECT",
            "profile_id": "maintenance-candidate",
            "profile_version": "1.0",
            "explicit_user_authorization": True,
            "artifact_allowlist": paths,
            "expected_sha256": hashes,
            "independent_provenance": provenance,
            "custody_records": custody,
            "uniqueness_decision": {
                "status": "unique",
                "copied_artifact_id": False,
                "ambiguous": False,
                "reviewed_by": "uniqueness-reviewer",
                "artifact_paths": paths,
            },
        }

    def test_public_candidate_api_has_no_root_discovery_parameter(self):
        parameter_names = inspect.signature(build_profile_update_candidate).parameters
        self.assertNotIn("csharp_" + "root", parameter_names)
        with mock.patch.object(Path, "open") as artifact_open:
            with self.assertRaises(TypeError):
                build_profile_update_candidate(
                    "SP_SCREEN_SELECT",
                    profile_id="maintenance-candidate",
                    profile_version="1.0",
                    **{"csharp_" + "root": r"C:\arbitrary"},
                )
        artifact_open.assert_not_called()

    def test_each_pre_read_authority_contract_is_required_before_content_read(self):
        mutations = {
            "authorization": lambda value: value.update(explicit_user_authorization=False),
            "allowlist": lambda value: value.update(artifact_allowlist=[]),
            "hashes": lambda value: value.update(expected_sha256={}),
            "provenance": lambda value: value.update(independent_provenance={}),
            "custody": lambda value: value.update(custody_records={}),
            "uniqueness": lambda value: value.update(uniqueness_decision={}),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, hashes = self._write_pair(temp_dir)
            for label, mutate in mutations.items():
                with self.subTest(label=label):
                    contract = self._contract(paths, hashes)
                    mutate(contract)
                    with mock.patch.object(Path, "open") as artifact_open:
                        result = build_profile_update_candidate(**contract)
                    self.assertFalse(result.success)
                    self.assertFalse(result.metadata["pre_read_contract"]["pre_read_checks_passed"])
                    artifact_open.assert_not_called()

    def test_provenance_custody_and_uniqueness_reviewers_must_be_independent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, hashes = self._write_pair(temp_dir)
            cases = []

            same_provenance_reviewer = self._contract(paths, hashes)
            for item in same_provenance_reviewer["independent_provenance"].values():
                item["independent_reviewer"] = item["captured_by"]
            cases.append((same_provenance_reviewer, "profile_update_independent_provenance_required"))

            same_custodian = self._contract(paths, hashes)
            for index, item in enumerate(same_custodian["custody_records"].values()):
                item["custodian"] = f"capture-operator-{index}"
            cases.append((same_custodian, "profile_update_independent_custody_required"))

            same_uniqueness_reviewer = self._contract(paths, hashes)
            same_uniqueness_reviewer["uniqueness_decision"]["reviewed_by"] = "custody-operator-0"
            cases.append((same_uniqueness_reviewer, "profile_update_uniqueness_decision_required"))

            for contract, expected_code in cases:
                with self.subTest(expected_code=expected_code), mock.patch.object(
                    Path, "open"
                ) as artifact_open:
                    result = build_profile_update_candidate(**contract)
                    self.assertFalse(result.success)
                    self.assertIn(expected_code, {issue["code"] for issue in result.metadata["issues"]})
                    artifact_open.assert_not_called()

    def test_nonexistent_allowlisted_artifact_is_rejected_before_content_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, hashes = self._write_pair(temp_dir)
            Path(paths[0]).unlink()
            with mock.patch.object(Path, "open") as artifact_open:
                result = build_profile_update_candidate(**self._contract(paths, hashes))

        self.assertFalse(result.success)
        self.assertIn(
            "profile_update_artifact_unreadable",
            {issue["code"] for issue in result.metadata["issues"]},
        )
        artifact_open.assert_not_called()

    def test_expected_sha_mismatch_rejects_candidate_after_current_readback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, hashes = self._write_pair(temp_dir)
            hashes[paths[0]] = "sha256:" + "0" * 64
            result = build_profile_update_candidate(**self._contract(paths, hashes))

        self.assertFalse(result.success)
        self.assertEqual({}, result.metadata["candidate_profile"])
        self.assertIn(
            "profile_update_artifact_sha256_mismatch",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_missing_ambiguous_and_copied_artifact_ids_are_rejected(self):
        cases = {
            "missing": (
                "// no artifact identity\n",
                "// ARTIFACT-ID: screen-designer\n",
                "profile_update_artifact_id_missing",
            ),
            "ambiguous": (
                "// ARTIFACT-ID: screen-code-a\n// ARTIFACT-ID: screen-code-b\n",
                "// ARTIFACT-ID: screen-designer\n",
                "profile_update_artifact_id_ambiguous",
            ),
            "copied": (
                "// ARTIFACT-ID: copied-id\n",
                "// ARTIFACT-ID: copied-id\n",
                "profile_update_copied_artifact_id_rejected",
            ),
        }
        for label, (source_header, designer_header, expected_code) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                paths, hashes = self._write_pair(
                    temp_dir,
                    source_header=source_header,
                    designer_header=designer_header,
                )
                result = build_profile_update_candidate(**self._contract(paths, hashes))
                self.assertFalse(result.success)
                self.assertIn(expected_code, {issue["code"] for issue in result.metadata["issues"]})

    def test_unrelated_partial_class_pair_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, hashes = self._write_pair(
                temp_dir,
                source_class="WrongForm",
                designer_class="OtherForm",
            )
            result = build_profile_update_candidate(**self._contract(paths, hashes))

        self.assertFalse(result.success)
        self.assertIn(
            "profile_update_program_pair_mismatch",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_wrong_procedure_family_method_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, hashes = self._write_pair(temp_dir, method_name="CallSaveProcedure")
            result = build_profile_update_candidate(**self._contract(paths, hashes))

        self.assertFalse(result.success)
        self.assertIn(
            "profile_update_program_pair_mismatch",
            {issue["code"] for issue in result.metadata["issues"]},
        )

    def test_oversized_artifact_is_rejected_before_full_read(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, hashes = self._write_pair(temp_dir)
            oversized = Path(paths[0])
            oversized.write_bytes(
                b"x" * (maintenance.PROFILE_MAINTENANCE_ARTIFACT_MAX_BYTES + 1)
            )
            hashes[paths[0]] = "sha256:" + hashlib.sha256(oversized.read_bytes()).hexdigest()
            with mock.patch.object(Path, "open") as artifact_open:
                result = build_profile_update_candidate(**self._contract(paths, hashes))

        self.assertFalse(result.success)
        self.assertIn(
            "profile_update_artifact_size_limit_exceeded",
            {issue["code"] for issue in result.metadata["issues"]},
        )
        artifact_open.assert_not_called()

    def test_exact_authorized_pair_produces_candidate_but_never_runtime_authority(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            paths, hashes = self._write_pair(temp_dir)
            result = build_profile_update_candidate(**self._contract(paths, hashes))

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual("candidate_ready", result.metadata["status"])
        self.assertEqual(2, len(result.metadata["artifact_receipts"]))
        self.assertEqual(2, len(result.metadata["artifact_id_records"]))
        self.assertFalse(result.metadata["runtime_generation_eligible"])
        candidate = result.metadata["candidate_profile"]
        self.assertEqual("exact_allowlisted_artifacts", candidate["candidate_source"])
        self.assertEqual("SCREEN", candidate["procedure_program_key"])
        self.assertEqual("ScreenForm", candidate["partial_class"])


if __name__ == "__main__":
    unittest.main()
