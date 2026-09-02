import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.contracts import HarnessResult
from src.orchestration import artifact_style_gate as artifact_gate
from src.orchestration.artifact_style_gate import (
    ARTIFACT_STYLE_PRODUCER,
    cancel_csharp_artifact_operation_retry,
    execute_csharp_artifact_operation,
    execute_artifact_style_precompletion,
    issue_csharp_generation_prewrite_receipt,
    issue_csharp_modification_preedit_receipt,
    retry_csharp_artifact_operation,
    sweep_csharp_artifact_retry_registry,
    validate_artifact_style_gate_snapshot,
)
from src.orchestration.goal_evidence import RuntimeProducerBoundary
from src.skills import pb_to_csharp_migration as migration
from src.skills.sql_formatting_provider import (
    attach_sql_provider_selection_runtime_receipt,
)
from src.skills.sql_formatting_style import bind_sql_alias_role_plan


ROOT = Path(__file__).resolve().parents[1]
SQL_PROVIDER_PATH = ROOT / "skills" / "sql_formatting" / "SKILL.md"


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _passed_result(original: str, candidate: str, verification_id: str) -> HarnessResult:
    return HarnessResult(
        success=True,
        exit_code=0,
        metadata={
            "status": "passed",
            "operation": "formatting",
            "verification_id": verification_id,
            "original_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
            "formatted_sha256": hashlib.sha256(candidate.encode("utf-8")).hexdigest(),
        },
    )


def _provider_selection() -> dict:
    resolved = str(SQL_PROVIDER_PATH.resolve())
    return attach_sql_provider_selection_runtime_receipt(
        {
            "schema_version": 1,
            "front_door_status": "ok",
            "host": "runtime-integration-test",
            "project": str(ROOT),
            "provider_id": "sql-formatting",
            "provider_path": resolved,
            "selected_active_provider_path": resolved,
            "provider_source": "packaged-kh-skill",
            "compatibility": "compatible",
            "selection_status": "selected",
            "plugin_route": {
                "route": "single",
                "controller": {
                    "provider_id": "sql-formatting",
                    "capability": "sql_formatting",
                    "metadata": {
                        "path": resolved,
                        "source": "packaged-kh-skill",
                        "compatibility": "compatible",
                    },
                },
                "assistants": [],
            },
            "execution_gate": {
                "can_execute": True,
                "status": "execution_allowed_after_selected_skill_setup",
                "reason": "Focused integration test selected the packaged provider.",
            },
        }
    )


def _candidate_alias_plan(sql: str) -> dict:
    return bind_sql_alias_role_plan(
        sql,
        {
            "scopes": [
                {
                    "scope_id": "scope_1",
                    "basis_references": [
                        {
                            "kind": "reviewer_approved_business_role",
                            "source": "review://PB-RUNTIME/main-and-detail-roles",
                            "reviewer_approved": True,
                            "role_names": ["main", "detail"],
                        }
                    ],
                    "roles": [
                        {
                            "name": "main",
                            "kind": "main",
                            "members": [
                                {
                                    "source": "ORDER_HEADER",
                                    "original_alias": "A",
                                    "alias": "A",
                                }
                            ],
                        },
                        {
                            "name": "detail",
                            "kind": "support",
                            "members": [
                                {
                                    "source": "CUSTOMER",
                                    "original_alias": "B",
                                    "alias": "B",
                                }
                            ],
                        },
                    ],
                }
            ]
        },
    )


_RETRY_SOURCE = """public partial class RetryForm : FrmDevBase
{
    public RetryForm() { InitializeComponent(); }
}
"""
_RETRY_DESIGNER = """public partial class RetryForm : FrmDevBase
{
    private System.Windows.Forms.Button btnSave;
    private void InitializeComponent()
    {
        this.btnSave = new System.Windows.Forms.Button();
        this.btnSave.Name = \"btnSave\";
        this.btnSave.TabIndex = 0;
    }
}
"""
_RETRY_DELETED_DESIGNER = """public partial class RetryForm : FrmDevBase
{
    private void InitializeComponent() { }
}
"""


def _start_failed_modification(root: Path, pair_id: str) -> dict:
    source = root / f"{pair_id}.cs"
    designer = root / f"{pair_id}.Designer.cs"
    source.write_text(_RETRY_SOURCE, encoding="utf-8", newline="")
    designer.write_text(_RETRY_DESIGNER, encoding="utf-8", newline="")

    def writer(paths: dict[str, Path]) -> None:
        paths["winforms_designer"].write_text(
            _RETRY_DELETED_DESIGNER,
            encoding="utf-8",
            newline="",
        )

    return execute_csharp_artifact_operation(
        project_root=root,
        pair_id=pair_id,
        operation="modification",
        codebehind_path=source,
        designer_path=designer,
        write_artifacts=writer,
    )


class CSharpSqlRuntimeIntegrationTests(unittest.TestCase):
    def test_pb_csharp_verifier_forwards_original_and_edit_evidence(self):
        original = "private void SaveCommand() { CallSaveProcedure(); }"
        candidate = (
            "private void SaveCommand() { gvwList.PostEditor(); "
            "CallSaveProcedure(); }"
        )
        evidence = {"authority": "user", "reason": "explicit requested change"}
        blocked = HarnessResult(
            success=False,
            exit_code=1,
            metadata={
                "status": "blocked",
                "issues": [
                    {
                        "code": "invented_edit_commit_call",
                        "severity": "error",
                    }
                ],
            },
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            original_path = Path(temp_dir) / "Sample.cs"
            original_path.write_text(original, encoding="utf-8")
            original_sha256 = hashlib.sha256(original_path.read_bytes()).hexdigest()
            with mock.patch(
                "src.skills.csharp_designer_style.verify_csharp_edit_contract",
                return_value=blocked,
            ) as edit_guard:
                result = migration.verify_migration_generated_csharp_style(
                    candidate,
                    source_operation="modification",
                    original_source_text=original,
                    original_source_path=original_path,
                    original_source_sha256=original_sha256,
                    source_modification_evidence=evidence,
                )

        edit_guard.assert_called_once_with(
            original,
            candidate,
            evidence=evidence,
            designer_source="",
        )
        self.assertFalse(result.success)
        self.assertEqual(
            "blocked",
            result.metadata["source_modification_contract"]["status"],
        )
        self.assertIn(
            "invented_edit_commit_call",
            {item["code"] for item in result.metadata["issues"]},
        )

    def test_pb_csharp_verifier_requires_original_for_modification_but_not_generation(self):
        source = "private void SaveCommand() { CallSaveProcedure(); }"

        modified = migration.verify_migration_generated_csharp_style(
            source,
            source_operation="modification",
        )
        generated = migration.verify_migration_generated_csharp_style(
            source,
            source_operation="generation",
        )

        modified_contract = modified.metadata["source_modification_contract"]
        generated_contract = generated.metadata["source_modification_contract"]
        self.assertEqual("blocked", modified_contract["status"])
        self.assertIn(
            "csharp_modification_original_required",
            {item["code"] for item in modified_contract["issues"]},
        )
        self.assertEqual("pending", generated_contract["status"])
        self.assertEqual(
            "trusted_generation_receipt_required",
            generated_contract["reason"],
        )

    def test_pb_csharp_verifier_rejects_ambiguous_source_operation(self):
        result = migration.verify_migration_generated_csharp_style(
            "private void SaveCommand() { CallSaveProcedure(); }",
            source_operation="write",
        )

        self.assertFalse(result.success)
        self.assertEqual("invalid", result.metadata["source_operation"])
        self.assertIn(
            "csharp_source_operation_invalid",
            {item["code"] for item in result.metadata["issues"]},
        )

    def test_artifact_gate_runs_csharp_edit_guard_only_with_bound_original(self):
        original_text = """public partial class DemoForm : FrmDevBase
{
    private void SaveCommand() { CallSaveProcedure(); }
}
"""
        candidate_text = """public partial class DemoForm : FrmDevBase
{
    private void SaveCommand()
    {
        gvwList.PostEditor();
        CallSaveProcedure();
    }
}
"""
        designer_text = """public partial class DemoForm : FrmDevBase
{
    private void InitializeComponent() { }
}
"""
        blocked = HarnessResult(
            success=False,
            exit_code=1,
            metadata={
                "status": "blocked",
                "issues": [
                    {
                        "code": "invented_edit_commit_call",
                        "severity": "error",
                    }
                ],
            },
        )
        pair_passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        edit_evidence = {
            "authority": "target_source",
            "reason": "bound pre-edit source",
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            snapshot_directory = root / ".artifact-preedit"
            snapshot_directory.mkdir()
            source.write_text(original_text, encoding="utf-8", newline="")
            designer.write_text(designer_text, encoding="utf-8", newline="")
            source_receipt = issue_csharp_modification_preedit_receipt(
                project_root=root,
                artifact_path=source,
                artifact_role="winforms_codebehind",
                pair_id="demo",
                snapshot_directory=snapshot_directory,
            )
            designer_receipt = issue_csharp_modification_preedit_receipt(
                project_root=root,
                artifact_path=designer,
                artifact_role="winforms_designer",
                pair_id="demo",
                snapshot_directory=snapshot_directory,
            )
            source.write_text(candidate_text, encoding="utf-8", newline="")
            context = {
                "project": str(root.resolve()),
                "changed_artifacts": [
                    {
                        "path": str(source.resolve()),
                        "artifact_role": "winforms_codebehind",
                        "pair_id": "demo",
                        "operation": "modified",
                        "modification_preedit_receipt": source_receipt,
                        "edit_evidence": edit_evidence,
                    },
                    {
                        "path": str(designer.resolve()),
                        "artifact_role": "winforms_designer",
                        "pair_id": "demo",
                        "operation": "modified",
                        "modification_preedit_receipt": designer_receipt,
                    },
                ],
                "completion": True,
            }
            with (
                mock.patch(
                    "src.skills.csharp_designer_style.verify_csharp_edit_contract",
                    return_value=blocked,
                ) as edit_guard,
                mock.patch(
                    "src.skills.csharp_designer_style_contract.verify_csharp_designer_style",
                    return_value=pair_passed,
                ) as pair_guard,
            ):
                gate = execute_artifact_style_precompletion(
                    context,
                    producer_boundary=RuntimeProducerBoundary(
                        ARTIFACT_STYLE_PRODUCER
                    ),
                )

        self.assertEqual(2, edit_guard.call_count)
        self.assertEqual((original_text, candidate_text), edit_guard.call_args.args)
        self.assertEqual(edit_evidence, edit_guard.call_args.kwargs["evidence"])
        self.assertEqual(
            designer_text,
            edit_guard.call_args.kwargs["designer_source"],
        )
        pair_guard.assert_not_called()
        self.assertFalse(gate["style_passed"])
        self.assertTrue(
            any(
                item.startswith("csharp_verifier_blocked:")
                for item in gate["executor_errors"]
            ),
            gate,
        )

    def test_artifact_gate_skips_edit_guard_for_generation_artifact(self):
        source_text = """public partial class DemoForm : FrmDevBase
{
    private void SaveCommand() { CallSaveProcedure(); }
}
"""
        designer_text = """public partial class DemoForm : FrmDevBase
{
    private void InitializeComponent() { }
}
"""
        passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            source_receipt = issue_csharp_generation_prewrite_receipt(
                project_root=root,
                artifact_path=source,
                artifact_role="winforms_codebehind",
                pair_id="demo",
            )
            designer_receipt = issue_csharp_generation_prewrite_receipt(
                project_root=root,
                artifact_path=designer,
                artifact_role="winforms_designer",
                pair_id="demo",
            )
            source.write_text(source_text, encoding="utf-8", newline="")
            designer.write_text(designer_text, encoding="utf-8", newline="")
            context = {
                "project": str(root.resolve()),
                "generated_artifacts": [
                    {
                        "path": str(source.resolve()),
                        "artifact_role": "winforms_codebehind",
                        "pair_id": "demo",
                        "operation": "added",
                        "generation_prewrite_receipt": source_receipt,
                    },
                    {
                        "path": str(designer.resolve()),
                        "artifact_role": "winforms_designer",
                        "pair_id": "demo",
                        "operation": "added",
                        "generation_prewrite_receipt": designer_receipt,
                    },
                ],
                "completion": True,
            }
            with (
                mock.patch(
                    "src.skills.csharp_designer_style.verify_csharp_edit_contract"
                ) as edit_guard,
                mock.patch(
                    "src.skills.csharp_designer_style_contract.verify_csharp_designer_style",
                    return_value=passed,
                ),
            ):
                gate = execute_artifact_style_precompletion(
                    context,
                    producer_boundary=RuntimeProducerBoundary(
                        ARTIFACT_STYLE_PRODUCER
                    ),
                )

        edit_guard.assert_not_called()
        self.assertTrue(gate["style_passed"], gate)
        self.assertEqual(
            {source_receipt["receipt_id"], designer_receipt["receipt_id"]},
            {
                item["generation_prewrite_receipt_id"]
                for item in gate["changed_artifacts"]
            },
        )
        self.assertEqual(
            {source_receipt["receipt_id"], designer_receipt["receipt_id"]},
            {
                item["generation_prewrite_receipt_id"]
                for item in gate["style_receipts"]
            },
        )

    def test_public_generation_operation_issues_prewrite_before_writer(self):
        passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"

            def writer(paths: dict[str, Path]) -> dict:
                self.assertFalse(paths["winforms_codebehind"].exists())
                self.assertFalse(paths["winforms_designer"].exists())
                paths["winforms_codebehind"].write_text(
                    "public partial class DemoForm : FrmDevBase { }",
                    encoding="utf-8",
                    newline="",
                )
                paths["winforms_designer"].write_text(
                    "public partial class DemoForm : FrmDevBase "
                    "{ private void InitializeComponent() { } }",
                    encoding="utf-8",
                    newline="",
                )
                return {"status": "written"}

            with (
                mock.patch(
                    "src.orchestration.artifact_style_gate."
                    "issue_csharp_generation_prewrite_receipt",
                    wraps=issue_csharp_generation_prewrite_receipt,
                ) as issuer,
                mock.patch(
                    "src.skills.csharp_designer_style_contract."
                    "verify_csharp_designer_style",
                    return_value=passed,
                ),
            ):
                gate = execute_csharp_artifact_operation(
                    project_root=root,
                    pair_id="demo",
                    operation="generation",
                    codebehind_path=source,
                    designer_path=designer,
                    write_artifacts=writer,
                )

        self.assertEqual(2, issuer.call_count)
        self.assertTrue(gate["style_passed"], gate)
        self.assertEqual(
            "consumed_after_style_pass",
            gate["operation_receipt_lifecycle"],
        )
        self.assertEqual(
            "execute_csharp_artifact_operation>prewrite_or_preedit_receipt>"
            "write_artifacts>execute_artifact_style_precompletion",
            gate["artifact_operation"]["public_call_path"],
        )
        self.assertNotIn("retry_context", gate)

    def test_failed_generation_can_be_corrected_before_receipt_is_consumed(self):
        passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        blocked = HarnessResult(
            success=False,
            exit_code=1,
            metadata={
                "status": "blocked",
                "issues": [{"code": "candidate_broken"}],
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"

            def writer(paths: dict[str, Path]) -> None:
                paths["winforms_codebehind"].write_text(
                    "BROKEN",
                    encoding="utf-8",
                    newline="",
                )
                paths["winforms_designer"].write_text(
                    "BROKEN",
                    encoding="utf-8",
                    newline="",
                )

            def verify_pair(codebehind: dict, _designer: dict) -> HarnessResult:
                return (
                    blocked
                    if Path(codebehind["path"]).read_text(encoding="utf-8")
                    == "BROKEN"
                    else passed
                )

            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                side_effect=verify_pair,
            ):
                first = execute_csharp_artifact_operation(
                    project_root=root,
                    pair_id="demo",
                    operation="generation",
                    codebehind_path=source,
                    designer_path=designer,
                    write_artifacts=writer,
                )
                def correction(paths: dict[str, Path]) -> None:
                    paths["winforms_codebehind"].write_text(
                        "public partial class DemoForm : FrmDevBase { }",
                        encoding="utf-8",
                        newline="",
                    )
                    paths["winforms_designer"].write_text(
                        "public partial class DemoForm : FrmDevBase "
                        "{ private void InitializeComponent() { } }",
                        encoding="utf-8",
                        newline="",
                    )

                corrected = retry_csharp_artifact_operation(
                    retry_receipt=first["retry_receipt"],
                    write_artifacts=correction,
                )
                replay = retry_csharp_artifact_operation(
                    retry_receipt=first["retry_receipt"],
                    write_artifacts=correction,
                )

        self.assertFalse(first["style_passed"], first)
        self.assertEqual(
            "retained_for_retry",
            first["operation_receipt_lifecycle"],
        )
        self.assertTrue(corrected["style_passed"], corrected)
        self.assertEqual(
            "consumed_after_style_pass",
            corrected["operation_receipt_lifecycle"],
        )
        self.assertFalse(replay["style_passed"], replay)
        self.assertTrue(
            any("replayed_receipt" in item for item in replay["executor_errors"]),
            replay,
        )

    def test_public_modification_blocks_deleted_designer_control_and_property(self):
        source_text = """public partial class DemoForm : FrmDevBase
{
    public DemoForm() { InitializeComponent(); }
}
"""
        designer_text = """public partial class DemoForm : FrmDevBase
{
    private System.Windows.Forms.Button btnSave;
    private void InitializeComponent()
    {
        this.btnSave = new System.Windows.Forms.Button();
        this.btnSave.Name = \"btnSave\";
        this.btnSave.TabIndex = 0;
    }
}
"""
        deleted_designer = """public partial class DemoForm : FrmDevBase
{
    private void InitializeComponent() { }
}
"""
        pair_passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            source.write_text(source_text, encoding="utf-8", newline="")
            designer.write_text(designer_text, encoding="utf-8", newline="")

            def writer(paths: dict[str, Path]) -> None:
                paths["winforms_designer"].write_text(
                    deleted_designer,
                    encoding="utf-8",
                    newline="",
                )

            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                return_value=pair_passed,
            ):
                gate = execute_csharp_artifact_operation(
                    project_root=root,
                    pair_id="demo",
                    operation="modification",
                    codebehind_path=source,
                    designer_path=designer,
                    write_artifacts=writer,
                )
                validation = validate_artifact_style_gate_snapshot(gate)
                retry_receipt = gate["retry_receipt"]
                snapshot_paths = [
                    Path(path) for path in retry_receipt["snapshot_paths"]
                ]
                self.assertEqual(2, len(snapshot_paths))
                self.assertTrue(all(path.is_file() for path in snapshot_paths))

                def still_invalid(paths: dict[str, Path]) -> None:
                    paths["winforms_designer"].write_text(
                        deleted_designer,
                        encoding="utf-8",
                        newline="",
                    )

                failed_retry = retry_csharp_artifact_operation(
                    retry_receipt=retry_receipt,
                    write_artifacts=still_invalid,
                )
                self.assertTrue(all(path.is_file() for path in snapshot_paths))

                def correction(paths: dict[str, Path]) -> None:
                    paths["winforms_designer"].write_text(
                        designer_text,
                        encoding="utf-8",
                        newline="",
                    )

                corrected = retry_csharp_artifact_operation(
                    retry_receipt=retry_receipt,
                    write_artifacts=correction,
                )
                replay = retry_csharp_artifact_operation(
                    retry_receipt=retry_receipt,
                    write_artifacts=correction,
                )
                snapshots_removed = all(
                    not path.exists() for path in snapshot_paths
                )

        self.assertFalse(gate["style_passed"], gate)
        self.assertEqual(
            "retained_for_retry",
            gate["operation_receipt_lifecycle"],
        )
        self.assertTrue(
            any(
                "csharp_verifier_issue:designer_control_removed:" in item
                for item in gate["executor_errors"]
            ),
            gate,
        )
        self.assertTrue(
            any(
                "csharp_verifier_issue:designer_property_removed:" in item
                for item in gate["executor_errors"]
            ),
            gate,
        )
        self.assertTrue(validation["valid"], validation)
        self.assertNotIn("retry_context", gate)
        self.assertFalse(failed_retry["style_passed"], failed_retry)
        self.assertEqual(
            "retained_for_retry",
            failed_retry["operation_receipt_lifecycle"],
        )
        self.assertTrue(corrected["style_passed"], corrected)
        self.assertTrue(snapshots_removed)
        self.assertFalse(replay["style_passed"], replay)
        self.assertIn("replayed_receipt", replay["executor_errors"])

    def test_public_modification_binds_both_originals_and_survives_cleanup(self):
        source_text = """public partial class DemoForm : FrmDevBase
{
    public DemoForm() { InitializeComponent(); }
}
"""
        designer_text = """public partial class DemoForm : FrmDevBase
{
    private System.Windows.Forms.Button btnSave;
    private void InitializeComponent()
    {
        this.btnSave = new System.Windows.Forms.Button();
        this.btnSave.Name = \"btnSave\";
        this.btnSave.TabIndex = 0;
    }
}
"""
        pair_passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            source.write_text(source_text, encoding="utf-8", newline="")
            designer.write_text(designer_text, encoding="utf-8", newline="")

            def writer(paths: dict[str, Path]) -> None:
                paths["winforms_codebehind"].write_text(
                    source_text + "// requested source edit\n",
                    encoding="utf-8",
                    newline="",
                )

            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                return_value=pair_passed,
            ):
                gate = execute_csharp_artifact_operation(
                    project_root=root,
                    pair_id="demo",
                    operation="modification",
                    codebehind_path=source,
                    designer_path=designer,
                    write_artifacts=writer,
                )
                validation = validate_artifact_style_gate_snapshot(gate)

        self.assertTrue(gate["style_passed"], gate)
        self.assertEqual(
            "consumed_after_style_pass",
            gate["operation_receipt_lifecycle"],
        )
        self.assertEqual(
            2,
            len(
                {
                    item["modification_preedit_receipt_id"]
                    for item in gate["changed_artifacts"]
                }
            ),
        )
        self.assertTrue(validation["valid"], validation)

    def test_failed_modification_cancellation_cleans_snapshot_and_state(self):
        pair_passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                return_value=pair_passed,
            ):
                gate = _start_failed_modification(root, "cancel")
            retry_receipt = gate["retry_receipt"]
            snapshot_paths = [
                Path(path) for path in retry_receipt["snapshot_paths"]
            ]
            self.assertTrue(all(path.is_file() for path in snapshot_paths))
            cancelled = cancel_csharp_artifact_operation_retry(
                retry_receipt=retry_receipt
            )
            replay = retry_csharp_artifact_operation(
                retry_receipt=retry_receipt,
                write_artifacts=lambda _paths: None,
            )

        self.assertTrue(cancelled["cancelled"], cancelled)
        self.assertTrue(all(not path.exists() for path in snapshot_paths))
        self.assertIn("replayed_receipt", replay["executor_errors"])

    def test_retry_registry_evicts_oldest_and_remains_bounded(self):
        pair_passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            artifact_gate,
            "_CSHARP_RETRY_LIMIT",
            1,
        ):
            root = Path(tmp)
            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                return_value=pair_passed,
            ):
                first = _start_failed_modification(root, "first")
                first_paths = [
                    Path(path) for path in first["retry_receipt"]["snapshot_paths"]
                ]
                second = _start_failed_modification(root, "second")
            second_paths = [
                Path(path) for path in second["retry_receipt"]["snapshot_paths"]
            ]
            registry = sweep_csharp_artifact_retry_registry()
            evicted_replay = retry_csharp_artifact_operation(
                retry_receipt=first["retry_receipt"],
                write_artifacts=lambda _paths: None,
            )
            cancelled = cancel_csharp_artifact_operation_retry(
                retry_receipt=second["retry_receipt"]
            )
            final_registry = sweep_csharp_artifact_retry_registry()

        self.assertTrue(all(not path.exists() for path in first_paths))
        self.assertTrue(all(not path.exists() for path in second_paths))
        self.assertEqual(1, registry["active_count"], registry)
        self.assertIn("replayed_receipt", evicted_replay["executor_errors"])
        self.assertTrue(cancelled["cancelled"], cancelled)
        self.assertEqual(0, final_registry["active_count"], final_registry)

    def test_retry_registry_expiry_cleans_snapshot_and_blocks_replay(self):
        pair_passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            artifact_gate,
            "_CSHARP_RETRY_TTL_SECONDS",
            0,
        ):
            root = Path(tmp)
            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                return_value=pair_passed,
            ):
                gate = _start_failed_modification(root, "expired")
            snapshot_paths = [
                Path(path) for path in gate["retry_receipt"]["snapshot_paths"]
            ]
            expired = sweep_csharp_artifact_retry_registry()
            replay = retry_csharp_artifact_operation(
                retry_receipt=gate["retry_receipt"],
                write_artifacts=lambda _paths: None,
            )

        self.assertEqual(1, expired["expired_count"], expired)
        self.assertTrue(all(not path.exists() for path in snapshot_paths))
        self.assertIn("replayed_receipt", replay["executor_errors"])

    def test_process_restart_invalidates_retry_and_cleans_only_authenticated_snapshot(self):
        pair_passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            arbitrary = root / ".kh-artifact-preedit-user-folder"
            arbitrary.mkdir()
            arbitrary_file = arbitrary / "user.txt"
            arbitrary_file.write_text("preserve", encoding="utf-8")
            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                return_value=pair_passed,
            ):
                gate = _start_failed_modification(root, "restart")
            retry_receipt = gate["retry_receipt"]
            retry_id = retry_receipt["retry_id"]
            snapshot_paths = [
                Path(path) for path in retry_receipt["snapshot_paths"]
            ]
            snapshot_directory = snapshot_paths[0].parent
            state = artifact_gate._CSHARP_RETRY_STATES[retry_id]
            persistence_path = Path(state["persistence_path"])
            marker_path = snapshot_directory / ".kh-retry-snapshot.json"
            self.assertTrue(persistence_path.is_file())
            self.assertTrue(marker_path.is_file())

            artifact_gate._CSHARP_RETRY_STATES.clear()
            artifact_gate._CSHARP_RETRY_PERSISTING.clear()
            artifact_gate._HOST_REGISTRIES.clear()
            artifact_gate._HOST_REGISTRY_ORDER.clear()

            swept = sweep_csharp_artifact_retry_registry()
            replay = retry_csharp_artifact_operation(
                retry_receipt=retry_receipt,
                write_artifacts=lambda _paths: None,
            )
            arbitrary_preserved = (
                arbitrary.is_dir()
                and arbitrary_file.read_text(encoding="utf-8") == "preserve"
            )

        self.assertEqual(
            1,
            swept["restart_cleanup"]["cleaned_count"],
            swept,
        )
        self.assertFalse(snapshot_directory.exists())
        self.assertFalse(persistence_path.exists())
        self.assertTrue(arbitrary_preserved)
        self.assertIn("replayed_receipt", replay["executor_errors"])

    def test_designer_modification_requires_its_own_hash_bound_preedit_receipt(self):
        source_text = "public partial class DemoForm : FrmDevBase { }"
        designer_text = (
            "public partial class DemoForm : FrmDevBase "
            "{ private void InitializeComponent() { } }"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            snapshot_directory = root / ".artifact-preedit"
            snapshot_directory.mkdir()
            source.write_text(source_text, encoding="utf-8", newline="")
            designer.write_text(designer_text, encoding="utf-8", newline="")
            source_receipt = issue_csharp_modification_preedit_receipt(
                project_root=root,
                artifact_path=source,
                artifact_role="winforms_codebehind",
                pair_id="demo",
                snapshot_directory=snapshot_directory,
            )
            gate = execute_artifact_style_precompletion(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": [
                        {
                            "path": str(source.resolve()),
                            "artifact_role": "winforms_codebehind",
                            "pair_id": "demo",
                            "operation": "modification",
                            "modification_preedit_receipt": source_receipt,
                        },
                        {
                            "path": str(designer.resolve()),
                            "artifact_role": "winforms_designer",
                            "pair_id": "demo",
                            "operation": "modification",
                        },
                    ],
                    "completion": True,
                }
            )

        self.assertFalse(gate["style_passed"], gate)
        self.assertIn(
            f"original_artifact_receipt_required:{designer.resolve()}",
            gate["artifact_errors"],
        )

    def test_designer_modification_rejects_tampered_preedit_snapshot(self):
        text = "public partial class DemoForm : FrmDevBase { }"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            snapshot_directory = root / ".artifact-preedit"
            snapshot_directory.mkdir()
            source.write_text(text, encoding="utf-8", newline="")
            designer.write_text(text, encoding="utf-8", newline="")
            source_receipt = issue_csharp_modification_preedit_receipt(
                project_root=root,
                artifact_path=source,
                artifact_role="winforms_codebehind",
                pair_id="demo",
                snapshot_directory=snapshot_directory,
            )
            designer_receipt = issue_csharp_modification_preedit_receipt(
                project_root=root,
                artifact_path=designer,
                artifact_role="winforms_designer",
                pair_id="demo",
                snapshot_directory=snapshot_directory,
            )
            Path(designer_receipt["snapshot_path"]).write_text(
                "tampered",
                encoding="utf-8",
                newline="",
            )
            gate = execute_artifact_style_precompletion(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": [
                        {
                            "path": str(source.resolve()),
                            "artifact_role": "winforms_codebehind",
                            "pair_id": "demo",
                            "operation": "modification",
                            "modification_preedit_receipt": source_receipt,
                        },
                        {
                            "path": str(designer.resolve()),
                            "artifact_role": "winforms_designer",
                            "pair_id": "demo",
                            "operation": "modification",
                            "modification_preedit_receipt": designer_receipt,
                        },
                    ],
                    "completion": True,
                }
            )

        self.assertFalse(gate["style_passed"], gate)
        self.assertTrue(
            any(
                "modification_preedit_snapshot_bytes_mismatch" in item
                for item in gate["artifact_errors"]
            ),
            gate,
        )

    def test_artifact_gate_blocks_candidate_as_its_own_modification_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            source.write_text("public partial class DemoForm { }", encoding="utf-8")
            designer.write_text("public partial class DemoForm { }", encoding="utf-8")
            gate = execute_artifact_style_precompletion(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": [
                        {
                            "path": str(source.resolve()),
                            "artifact_role": "winforms_codebehind",
                            "pair_id": "demo",
                            "operation": "modified",
                            "original_path": str(source.resolve()),
                            "original_sha256": _sha(source),
                        },
                        {
                            "path": str(designer.resolve()),
                            "artifact_role": "winforms_designer",
                            "pair_id": "demo",
                            "operation": "modified",
                        },
                    ],
                    "completion": True,
                },
                producer_boundary=RuntimeProducerBoundary(ARTIFACT_STYLE_PRODUCER),
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(
            any(
                item.startswith("original_artifact_receipt_required:")
                for item in gate["artifact_errors"]
            ),
            gate,
        )

    def test_artifact_gate_blocks_hard_link_as_modification_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            original = root / "DemoForm.before.cs"
            designer = root / "DemoForm.Designer.cs"
            source.write_text("public partial class DemoForm { }", encoding="utf-8")
            os.link(source, original)
            designer.write_text("public partial class DemoForm { }", encoding="utf-8")
            gate = execute_artifact_style_precompletion(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": [
                        {
                            "path": str(source.resolve()),
                            "artifact_role": "winforms_codebehind",
                            "pair_id": "demo",
                            "operation": "modified",
                            "original_path": str(original.resolve()),
                            "original_sha256": _sha(original),
                        },
                        {
                            "path": str(designer.resolve()),
                            "artifact_role": "winforms_designer",
                            "pair_id": "demo",
                            "operation": "modified",
                        },
                    ],
                    "completion": True,
                },
                producer_boundary=RuntimeProducerBoundary(ARTIFACT_STYLE_PRODUCER),
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(
            any(
                item.startswith("original_artifact_receipt_required:")
                for item in gate["artifact_errors"]
            ),
            gate,
        )

    def test_artifact_gate_blocks_existing_file_disguised_as_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            source.write_text("public partial class DemoForm { }", encoding="utf-8")
            designer.write_text("public partial class DemoForm { }", encoding="utf-8")
            gate = execute_artifact_style_precompletion(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": [
                        {
                            "path": str(source.resolve()),
                            "artifact_role": "winforms_codebehind",
                            "pair_id": "demo",
                            "operation": "generated",
                        },
                        {
                            "path": str(designer.resolve()),
                            "artifact_role": "winforms_designer",
                            "pair_id": "demo",
                            "operation": "generated",
                        },
                    ],
                    "completion": True,
                },
                producer_boundary=RuntimeProducerBoundary(ARTIFACT_STYLE_PRODUCER),
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(
            any(
                item.startswith("csharp_generation_prewrite_receipt_required:")
                for item in gate["artifact_errors"]
            ),
            gate,
        )

    def test_artifact_gate_rejects_self_declared_generation_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            source.write_text("public partial class DemoForm { }", encoding="utf-8")
            designer.write_text("public partial class DemoForm { }", encoding="utf-8")
            gate = execute_artifact_style_precompletion(
                {
                    "project": str(root.resolve()),
                    "generated_artifacts": [
                        {
                            "path": str(source.resolve()),
                            "artifact_role": "winforms_codebehind",
                            "pair_id": "demo",
                            "operation": "generated",
                            "operation_metadata": {
                                "pre_write_path_state": "absent",
                                "created_in_current_operation": False,
                            },
                        },
                        {
                            "path": str(designer.resolve()),
                            "artifact_role": "winforms_designer",
                            "pair_id": "demo",
                            "operation": "generated",
                        },
                    ],
                    "completion": True,
                },
                producer_boundary=RuntimeProducerBoundary(ARTIFACT_STYLE_PRODUCER),
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(
            any(
                item.startswith("csharp_generation_prewrite_receipt_required:")
                for item in gate["artifact_errors"]
            ),
            gate,
        )

    def test_artifact_gate_rejects_forged_generation_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            source.write_text("public partial class DemoForm { }", encoding="utf-8")
            designer.write_text("public partial class DemoForm { }", encoding="utf-8")
            forged = {
                "status": "passed",
                "path_state": "absent",
                "artifact_path": str(source.resolve()),
                "artifact_role": "winforms_codebehind",
                "pair_id": "demo",
                "producer_claim": "hmac-sha256:" + "a" * 64,
            }
            gate = execute_artifact_style_precompletion(
                {
                    "project": str(root.resolve()),
                    "generated_artifacts": [
                        {
                            "path": str(source.resolve()),
                            "artifact_role": "winforms_codebehind",
                            "pair_id": "demo",
                            "operation": "generated",
                            "generation_prewrite_receipt": forged,
                        },
                        {
                            "path": str(designer.resolve()),
                            "artifact_role": "winforms_designer",
                            "pair_id": "demo",
                            "operation": "generated",
                            "generation_prewrite_receipt": forged,
                        },
                    ],
                    "completion": True,
                },
                producer_boundary=RuntimeProducerBoundary(ARTIFACT_STYLE_PRODUCER),
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(
            any(
                item.startswith("csharp_generation_prewrite_receipt_invalid:")
                for item in gate["artifact_errors"]
            ),
            gate,
        )

    def test_artifact_gate_rejects_tampered_and_replayed_generation_receipts(self):
        source_text = "public partial class DemoForm : FrmDevBase { }"
        designer_text = """public partial class DemoForm : FrmDevBase
{
    private void InitializeComponent() { }
}
"""
        passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            source_receipt = issue_csharp_generation_prewrite_receipt(
                project_root=root,
                artifact_path=source,
                artifact_role="winforms_codebehind",
                pair_id="demo",
            )
            designer_receipt = issue_csharp_generation_prewrite_receipt(
                project_root=root,
                artifact_path=designer,
                artifact_role="winforms_designer",
                pair_id="demo",
            )
            source.write_text(source_text, encoding="utf-8", newline="")
            designer.write_text(designer_text, encoding="utf-8", newline="")
            context = {
                "project": str(root.resolve()),
                "generated_artifacts": [
                    {
                        "path": str(source.resolve()),
                        "artifact_role": "winforms_codebehind",
                        "pair_id": "demo",
                        "operation": "generated",
                        "generation_prewrite_receipt": source_receipt,
                    },
                    {
                        "path": str(designer.resolve()),
                        "artifact_role": "winforms_designer",
                        "pair_id": "demo",
                        "operation": "generated",
                        "generation_prewrite_receipt": designer_receipt,
                    },
                ],
                "completion": True,
            }
            with mock.patch(
                "src.skills.csharp_designer_style_contract.verify_csharp_designer_style",
                return_value=passed,
            ):
                tampered_results = []
                for key, value in (
                    ("pair_id", "other"),
                    ("artifact_path", str(root / "OtherForm.cs")),
                    ("absent_artifact_sha256", "sha256:" + "b" * 64),
                    ("created_in_current_operation", True),
                ):
                    tampered_context = copy.deepcopy(context)
                    tampered_context["generated_artifacts"][0][
                        "generation_prewrite_receipt"
                    ][key] = value
                    tampered_results.append(
                        execute_artifact_style_precompletion(tampered_context)
                    )
                first = execute_artifact_style_precompletion(context)
                replay = execute_artifact_style_precompletion(context)

        self.assertTrue(
            all(not item["style_passed"] for item in tampered_results),
            tampered_results,
        )
        self.assertTrue(first["style_passed"], first)
        self.assertFalse(replay["style_passed"])
        self.assertTrue(
            any("replayed_receipt" in item for item in replay["artifact_errors"]),
            replay,
        )

    def test_artifact_gate_blocks_modification_without_original_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            source.write_text("public partial class DemoForm { }", encoding="utf-8")
            designer.write_text("public partial class DemoForm { }", encoding="utf-8")
            gate = execute_artifact_style_precompletion(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": [
                        {
                            "path": str(source.resolve()),
                            "artifact_role": "winforms_codebehind",
                            "pair_id": "demo",
                            "operation": "modified",
                        },
                        {
                            "path": str(designer.resolve()),
                            "artifact_role": "winforms_designer",
                            "pair_id": "demo",
                            "operation": "modified",
                        },
                    ],
                    "completion": True,
                },
                producer_boundary=RuntimeProducerBoundary(ARTIFACT_STYLE_PRODUCER),
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(
            any(
                item.startswith("original_artifact_receipt_required:")
                for item in gate["artifact_errors"]
            ),
            gate,
        )

    def test_artifact_gate_rejects_ambiguous_codebehind_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            source.write_text("public partial class DemoForm { }", encoding="utf-8")
            designer.write_text("public partial class DemoForm { }", encoding="utf-8")
            gate = execute_artifact_style_precompletion(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": [
                        {
                            "path": str(source.resolve()),
                            "artifact_role": "winforms_codebehind",
                            "pair_id": "demo",
                            "operation": "write",
                        },
                        {
                            "path": str(designer.resolve()),
                            "artifact_role": "winforms_designer",
                            "pair_id": "demo",
                            "operation": "modified",
                        },
                    ],
                    "completion": True,
                },
                producer_boundary=RuntimeProducerBoundary(ARTIFACT_STYLE_PRODUCER),
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(
            any(
                item.startswith("csharp_source_operation_invalid:")
                for item in gate["artifact_errors"]
            ),
            gate,
        )

    def test_pb_sql_binder_blocks_not_in_and_full_replace_during_generation(self):
        candidates = {
            "where_subquery_introduced": (
                "SELECT A.ITEMCD FROM ITEM_MASTER A "
                "WHERE A.ITEMCD NOT IN (SELECT B.ITEMCD FROM BLOCKED_ITEM B);"
            ),
            "full_delete_reinsert_without_evidence": (
                "DELETE FROM DETAIL_TABLE WHERE MASTER_ID = @MASTER_ID;\n"
                "INSERT INTO DETAIL_TABLE (MASTER_ID) SELECT @MASTER_ID;"
            ),
        }
        for expected_code, candidate in candidates.items():
            with self.subTest(expected_code=expected_code):
                success, receipt = migration._execute_pb_sql_final_response_binding(
                    candidate,
                    candidate,
                    candidate,
                    sql_provider_path="provider.py",
                    selected_active_sql_provider_path="provider.py",
                    sql_provider_selection={},
                    sql_formatting_verifier_kwargs={"operation": "generation"},
                    required_operation="generation",
                )
                serialized = json.dumps(receipt, ensure_ascii=False)
                self.assertFalse(success)
                self.assertEqual("sql_generation_policy_blocked", receipt["code"])
                self.assertIn(expected_code, serialized)

    def test_pb_sql_binder_runs_generation_then_existing_formatting_binding(self):
        original = ""
        candidate = "SELECT 1 AS VALUE;"
        verification_id = "formatting-verification"
        generation = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed", "operation": "generation"},
        )
        formatting = _passed_result(original, candidate, verification_id)
        release = mock.Mock()
        release.to_receipt_dict.return_value = {
            "status": "passed",
            "binding": {
                "status": "bound",
                "verification_id": verification_id,
            },
        }
        where_contract = {"kind": "source_artifact"}
        save_contract = {"mode": "delta"}
        with (
            mock.patch(
                "src.skills.sql_formatting_provider.verify_sql_formatting_style",
                side_effect=[generation, formatting],
            ) as verifier,
            mock.patch(
                "src.skills.sql_formatting_provider.guard_and_bind_verified_sql_final_response",
                return_value=release,
            ) as final_binding,
        ):
            success, receipt = migration._execute_pb_sql_final_response_binding(
                original,
                candidate,
                candidate,
                sql_provider_path="provider.py",
                selected_active_sql_provider_path="provider.py",
                sql_provider_selection={},
                sql_formatting_verifier_kwargs={
                    "operation": "generation",
                    "where_subquery_source_contract": where_contract,
                    "save_row_state_contract": save_contract,
                },
                required_operation="generation",
            )

        self.assertTrue(success, receipt)
        self.assertEqual(2, verifier.call_count)
        self.assertEqual("", verifier.call_args_list[0].args[0])
        self.assertEqual("generation", verifier.call_args_list[0].kwargs["operation"])
        self.assertIs(
            where_contract,
            verifier.call_args_list[0].kwargs["where_subquery_source_contract"],
        )
        self.assertIs(
            save_contract,
            verifier.call_args_list[0].kwargs["save_row_state_contract"],
        )
        self.assertEqual("formatting", verifier.call_args_list[1].kwargs["operation"])
        final_binding.assert_called_once()
        self.assertTrue(receipt["generation_policy"]["success"])
        self.assertEqual("correlated", receipt["verifier_history_correlation"]["status"])

    def test_pb_sql_binder_accepts_real_candidate_bound_multi_source_alias_plan(self):
        candidate = (
            "SELECT A.ORDER_NO\n"
            "     , B.CUSTOMER_NAME\n"
            "FROM ORDER_HEADER A\n"
            "        LEFT OUTER JOIN CUSTOMER B\n"
            "                     ON A.CUSTOMER_ID = B.CUSTOMER_ID;\n"
        )
        plan = _candidate_alias_plan(candidate)

        success, receipt = migration._execute_pb_sql_final_response_binding(
            candidate,
            candidate,
            f"```sql\n{candidate}\n```",
            sql_provider_path=SQL_PROVIDER_PATH,
            selected_active_sql_provider_path=SQL_PROVIDER_PATH,
            sql_provider_selection=_provider_selection(),
            alias_role_plan=plan,
            sql_formatting_verifier_kwargs={"operation": "generation"},
            required_operation="generation",
        )

        self.assertTrue(success, receipt)
        self.assertEqual("passed", receipt["status"])
        generation = receipt["generation_policy"]["metadata"]
        self.assertEqual(
            "candidate_sql",
            generation["alias_role_plan_validation"]["validation_baseline"]["kind"],
        )

    def test_pb_sql_binder_rejects_forged_and_accepts_bound_full_replace_contract(self):
        candidate = (
            "DELETE FROM DETAIL_TABLE\n"
            "WHERE MASTER_ID = @MASTER_ID;\n\n"
            "INSERT INTO DETAIL_TABLE (MASTER_ID)\n"
            "SELECT @MASTER_ID;\n"
        )
        formatted_sha256 = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        forged = {
            "mode": "full_replace",
            "authority": "user",
            "reason": "caller-controlled assertion",
            "formatted_sha256": formatted_sha256,
        }
        forged_success, forged_receipt = (
            migration._execute_pb_sql_final_response_binding(
                candidate,
                candidate,
                f"```sql\n{candidate}\n```",
                sql_provider_path=SQL_PROVIDER_PATH,
                selected_active_sql_provider_path=SQL_PROVIDER_PATH,
                sql_provider_selection=_provider_selection(),
                sql_formatting_verifier_kwargs={
                    "operation": "generation",
                    "save_row_state_contract": forged,
                },
                required_operation="generation",
            )
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "target-save-source.sql"
            path.write_text(candidate, encoding="utf-8", newline="")
            bound = {
                "mode": "full_replace",
                "authority": "target_source",
                "reason": "exact target-source behavior",
                "formatted_sha256": formatted_sha256,
                "artifact_path": str(path.resolve()),
                "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            bound_success, bound_receipt = (
                migration._execute_pb_sql_final_response_binding(
                    candidate,
                    candidate,
                    f"```sql\n{candidate}\n```",
                    sql_provider_path=SQL_PROVIDER_PATH,
                    selected_active_sql_provider_path=SQL_PROVIDER_PATH,
                    sql_provider_selection=_provider_selection(),
                    sql_formatting_verifier_kwargs={
                        "operation": "generation",
                        "save_row_state_contract": bound,
                    },
                    required_operation="generation",
                )
            )

        self.assertFalse(forged_success)
        self.assertEqual("sql_generation_policy_blocked", forged_receipt["code"])
        self.assertTrue(bound_success, bound_receipt)
        policy = bound_receipt["generation_policy"]["metadata"]["style_lint"][
            "save_row_state_policy"
        ]
        self.assertEqual("verified_source_preservation", policy["status"])

    def test_csharp_edit_module_is_packaged_by_the_skill_contract(self):
        root = Path(__file__).resolve().parents[1]
        module = root / "src/skills/csharp_designer_style.py"
        skill = root / "skills/csharp_designer_style_harness/SKILL.md"
        self.assertTrue(module.is_file())
        self.assertIn(
            "src.skills.csharp_designer_style.verify_csharp_edit_contract",
            skill.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
