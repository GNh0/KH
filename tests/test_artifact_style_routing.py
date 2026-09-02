import copy
import hashlib
import io
import json
import os
import struct
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from src.contracts import HarnessResult
from src.orchestration.artifact_style_gate import (
    ARTIFACT_STYLE_PRODUCER,
    ARTIFACT_STYLE_RECEIPT_KIND,
    CSHARP_STYLE_SKILL,
    HostCallResultRegistry,
    SQL_FORMATTING_SKILL,
    SQL_STYLE_SKILL,
    analyze_artifact_style_context,
    execute_artifact_style_precompletion,
    issue_csharp_modification_preedit_receipt,
    issue_visual_qa_receipt,
    validate_artifact_style_gate_snapshot,
)
from src.orchestration.goal_evidence import RuntimeProducerBoundary
from src.orchestration.kh_front_door import (
    build_kh_front_door,
    main as kh_front_door_main,
)
from src.orchestration.request_classifier import classify_request
from src.orchestration.skill_application import (
    build_large_work_orchestration_bundle,
    validate_large_work_orchestration_bundle,
)
from src.orchestration.skill_transitions import validate_skill_transitions


VALID_SOURCE = """
using System;

public partial class DemoForm : FrmDevBase
{
    public DemoForm()
    {
        InitializeComponent();
    }
}
"""

VALID_DESIGNER = """
using System;

public partial class DemoForm : FrmDevBase
{
    private void InitializeComponent()
    {
        this.Load += new EventHandler(this.DemoForm_Load);
    }
}
"""


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _boundary() -> RuntimeProducerBoundary:
    return RuntimeProducerBoundary(ARTIFACT_STYLE_PRODUCER)


def _write_sql(root: Path, name: str = "sp_DEMO_SELECT.sql") -> Path:
    path = root / name
    path.write_text(
        "SELECT A.ITEMCD\n"
        "FROM SA100T A\n"
        "WHERE A.ORGDIV = @ORGDIV;\n",
        encoding="utf-8",
        newline="",
    )
    return path


def _identity_sql_formatter(request: dict) -> dict:
    path = Path(request["candidate_path"])
    history = [{
        "engine": "test-host-override",
        "operation": "formatting",
        "input_sha256": request["candidate_sha256"],
        "formatted_sha256": _sha(path),
        "changed": False,
    }]
    return {
        "status": "passed",
        "provider_id": request["provider_id"],
        "artifact_path": str(path),
        "input_sha256": request["candidate_sha256"],
        "formatted_sha256": _sha(path),
        "formatter_history": history,
        "formatter_history_sha256": _json_sha(history),
    }


def _whitespace_sql_formatter(request: dict) -> dict:
    path = Path(request["candidate_path"])
    path.write_text(
        request["candidate_text"].rstrip() + "\n\n",
        encoding="utf-8",
        newline="",
    )
    history = [{
        "engine": "test-host-override",
        "operation": "formatting",
        "input_sha256": request["candidate_sha256"],
        "formatted_sha256": _sha(path),
        "changed": True,
    }]
    return {
        "status": "passed",
        "provider_id": request["provider_id"],
        "artifact_path": str(path),
        "input_sha256": request["candidate_sha256"],
        "formatted_sha256": _sha(path),
        "formatter_history": history,
        "formatter_history_sha256": _json_sha(history),
    }


def _json_sha(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _minimal_png_bytes() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind)
        crc = zlib.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + chunk(b"IEND", b"")
    )


def _visual_qa_runner(request: dict) -> dict:
    return {
        "status": "passed",
        "provider": request["provider"],
        "artifact_path": request["artifact_path"],
        "artifact_sha256": request["artifact_sha256"],
    }


def _sql_context(
    root: Path,
    path: Path,
    *,
    supplied_hash: str = "",
    completion: bool = True,
) -> dict:
    row = {
        "path": str(path.resolve()),
        "artifact_role": "sql_candidate",
        "operation": "modified",
    }
    if supplied_hash:
        row["sha256"] = supplied_hash
    return {
        "project": str(root.resolve()),
        "changed_artifacts": [row],
        "completion": completion,
    }


def _write_pair(root: Path) -> tuple[Path, Path]:
    source = root / "DemoForm.cs"
    designer = root / "DemoForm.Designer.cs"
    source.write_text(VALID_SOURCE, encoding="utf-8", newline="")
    designer.write_text(VALID_DESIGNER, encoding="utf-8", newline="")
    return source, designer


def _csharp_context(
    root: Path,
    source: Path,
    designer: Path,
    *,
    visual_completion: bool = False,
) -> dict:
    snapshot_directory = root / ".artifact-preedit"
    snapshot_directory.mkdir(exist_ok=True)
    source_receipt = issue_csharp_modification_preedit_receipt(
        project_root=root,
        artifact_path=source,
        artifact_role="winforms_codebehind",
        pair_id="demo-form",
        snapshot_directory=snapshot_directory,
    )
    designer_receipt = issue_csharp_modification_preedit_receipt(
        project_root=root,
        artifact_path=designer,
        artifact_role="winforms_designer",
        pair_id="demo-form",
        snapshot_directory=snapshot_directory,
    )
    return {
        "project": str(root.resolve()),
        "changed_artifacts": [
            {
                "path": str(source.resolve()),
                "artifact_role": "winforms_codebehind",
                "pair_id": "demo-form",
                "operation": "modified",
                "modification_preedit_receipt": source_receipt,
            },
            {
                "path": str(designer.resolve()),
                "artifact_role": "winforms_designer",
                "pair_id": "demo-form",
                "operation": "modified",
                "modification_preedit_receipt": designer_receipt,
            },
        ],
        "completion": True,
        "visual_completion": visual_completion,
    }


def _style_overrides(gate: dict) -> dict:
    overrides = {
        "verification-before-completion-harness": {
            "status": "applied",
            "application_mode": "runtime",
            "evidence_note": "Fresh verification completed.",
            "evidence_keys": ["fresh_verification", "verification_command"],
            "metadata": {
                "command_output": {
                    "command": "python -m unittest",
                    "exit_code": 0,
                }
            },
        }
    }
    for skill in gate.get("required_skills", []):
        overrides[skill] = {
            "status": "applied",
            "application_mode": "runtime",
            "evidence_note": "Authenticated artifact verifier receipt.",
            "evidence_keys": [
                "authenticated_artifact_style_snapshot",
                "current_byte_sha256_receipts",
            ],
        }
    return overrides


class ArtifactStyleRoutingTests(unittest.TestCase):
    def test_ordinary_appkey_crud_does_not_select_designer_style(self):
        result = classify_request(
            "Implement ordinary APPKey CRUD in a generic C# service."
        )

        self.assertNotIn(CSHARP_STYLE_SKILL, result.required_harnesses)
        self.assertNotIn(CSHARP_STYLE_SKILL, result.recommended_skills)

    def test_vague_winforms_grid_change_selects_designer_style(self):
        result = classify_request("Modify this WinForms grid screen.")

        self.assertIn(CSHARP_STYLE_SKILL, result.required_harnesses)
        self.assertIn(CSHARP_STYLE_SKILL, result.recommended_skills)

    def test_generic_service_cs_artifact_without_verified_role_stays_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = root / "AppKeyService.cs"
            service.write_text(
                "public class AppKeyService {}",
                encoding="utf-8",
            )
            gate = analyze_artifact_style_context(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": [
                        {
                            "path": str(service.resolve()),
                            "kind": "csharp",
                            "operation": "modified",
                        }
                    ],
                    "completion": True,
                },
                producer_boundary=_boundary(),
            )

        self.assertFalse(gate["csharp_required"])
        self.assertNotIn(CSHARP_STYLE_SKILL, gate["required_skills"])

    def test_nonexistent_file_and_fake_hash_status_never_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing.sql"
            fake = {
                "gate": SQL_STYLE_SKILL,
                "path": str(missing.resolve()),
                "artifact_path": str(missing.resolve()),
                "sha256": "sha256:" + "a" * 64,
                "artifact_sha256": "sha256:" + "a" * 64,
                "artifact_role": "sql_candidate",
                "status": "passed",
            }
            gate = analyze_artifact_style_context(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": [fake],
                    "style_receipts": [fake],
                    "completion": True,
                    "style_passed": True,
                    "exact_receipts": True,
                },
                producer_boundary=_boundary(),
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(gate["completion_blocked"])
        self.assertTrue(
            any(
                item.startswith("artifact_path_not_file:")
                for item in gate["artifact_errors"]
            )
        )

    def test_relative_parent_and_outside_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            outside = _write_sql(Path(other), "outside.sql")
            rows = [
                {
                    "path": "relative.sql",
                    "artifact_role": "sql_candidate",
                    "operation": "modified",
                },
                {
                    "path": str(root / "sub" / ".." / "escape.sql"),
                    "artifact_role": "sql_candidate",
                    "operation": "modified",
                },
                {
                    "path": str(outside.resolve()),
                    "artifact_role": "sql_candidate",
                    "operation": "modified",
                },
            ]
            gate = analyze_artifact_style_context(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": rows,
                    "completion": True,
                },
                producer_boundary=_boundary(),
            )

        errors = "\n".join(gate["artifact_errors"])
        self.assertIn("artifact_path_relative", errors)
        self.assertIn("artifact_path_parent_traversal", errors)
        self.assertIn("artifact_path_outside_project", errors)
        self.assertFalse(gate["style_passed"])

    def test_empty_db_mapping_does_not_imply_sql_deployment(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = analyze_artifact_style_context(
                {
                    "project": str(Path(tmp).resolve()),
                    "db_deployment": {},
                    "completion": False,
                },
                producer_boundary=_boundary(),
            )

        self.assertFalse(gate["db_deployment_evidence"])
        self.assertFalse(gate["sql_required"])

    def test_nested_caller_receipts_cannot_bypass_runtime_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            digest = _sha(sql_path)
            fake_receipt = {
                "gate": SQL_STYLE_SKILL,
                "artifact_path": str(sql_path.resolve()),
                "artifact_sha256": digest,
                "artifact_role": "sql_candidate",
                "status": "passed",
                "result_id": "caller-result",
            }
            gate = analyze_artifact_style_context(
                {
                    **_sql_context(root, sql_path),
                    "runtime_context": {
                        "style_receipts": [
                            fake_receipt,
                            {
                                **fake_receipt,
                                "gate": SQL_FORMATTING_SKILL,
                            },
                        ],
                        "style_passed": True,
                        "exact_receipts": True,
                    },
                },
                producer_boundary=_boundary(),
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(gate["receipt_errors"])

    def test_same_path_stale_then_new_rows_block_regardless_of_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            current = {
                "path": str(sql_path.resolve()),
                "artifact_role": "sql_candidate",
                "sha256": _sha(sql_path),
                "operation": "modified",
            }
            stale = {
                **current,
                "sha256": "sha256:" + "b" * 64,
                "sequence": 1,
            }
            for rows in ([stale, current], [current, stale]):
                with self.subTest(order=[row["sha256"] for row in rows]):
                    gate = analyze_artifact_style_context(
                        {
                            "project": str(root.resolve()),
                            "changed_artifacts": rows,
                            "completion": True,
                        },
                        producer_boundary=_boundary(),
                    )
                    self.assertFalse(gate["style_passed"])
                    self.assertTrue(
                        any(
                            item.startswith(
                                "duplicate_or_replayed_artifact_path:"
                            )
                            for item in gate["artifact_errors"]
                        )
                    )

    @unittest.skipUnless(os.name == "nt", "Windows path identity test")
    def test_windows_case_alias_of_same_path_is_a_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            row = {
                "path": str(sql_path.resolve()),
                "artifact_role": "sql_candidate",
                "operation": "modified",
            }
            gate = analyze_artifact_style_context(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": [
                        row,
                        {**row, "path": row["path"].swapcase()},
                    ],
                    "completion": True,
                },
                producer_boundary=_boundary(),
            )

        self.assertTrue(
            any(
                item.startswith("duplicate_or_replayed_artifact_path:")
                for item in gate["artifact_errors"]
            )
        )

    def test_post_write_executor_runs_sql_provider_and_style_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            boundary = _boundary()
            formatter = mock.Mock(side_effect=_identity_sql_formatter)
            gate = execute_artifact_style_precompletion(
                _sql_context(root, sql_path, supplied_hash=_sha(sql_path)),
                producer_boundary=boundary,
                sql_formatter_runner=formatter,
            )
            validation = validate_artifact_style_gate_snapshot(
                gate,
                producer_boundary=boundary,
            )

        formatter.assert_called_once()
        self.assertEqual(gate["executor_status"], "passed", gate)
        self.assertTrue(gate["style_passed"], gate)
        self.assertEqual(
            {item["gate"] for item in gate["style_receipts"]},
            {SQL_FORMATTING_SKILL, SQL_STYLE_SKILL},
        )
        self.assertTrue(validation["valid"], validation)

    def test_sql_formatter_changed_output_binds_input_and_current_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            original_hash = _sha(sql_path)
            gate = execute_artifact_style_precompletion(
                _sql_context(root, sql_path, supplied_hash=original_hash),
                producer_boundary=_boundary(),
                sql_formatter_runner=_whitespace_sql_formatter,
            )

        formatting = next(
            item
            for item in gate["style_receipts"]
            if item["gate"] == SQL_FORMATTING_SKILL
        )
        self.assertNotEqual(original_hash, formatting["artifact_sha256"])
        self.assertEqual(
            formatting["execution_input_artifact_sha256"],
            original_hash,
        )
        self.assertEqual(
            formatting["formatted_output_sha256"],
            formatting["artifact_sha256"],
        )
        self.assertTrue(gate["style_passed"], gate)

    def test_sql_provider_availability_without_execution_remains_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            gate = execute_artifact_style_precompletion(
                _sql_context(root, sql_path),
                producer_boundary=_boundary(),
            )

        self.assertEqual(gate["executor_status"], "blocked")
        self.assertFalse(gate["style_passed"])
        self.assertEqual(gate["style_receipts"], [])
        self.assertTrue(
            any(
                item.startswith("sql_formatter_runner_unavailable:")
                for item in gate["executor_errors"]
            )
        )

    def test_identical_files_receive_unique_monotonic_execution_receipts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _write_sql(root, "first.sql")
            second = root / "second.sql"
            second.write_bytes(first.read_bytes())
            context = {
                "project": str(root.resolve()),
                "changed_artifacts": [
                    {
                        "path": str(path.resolve()),
                        "artifact_role": "sql_candidate",
                        "operation": "modified",
                    }
                    for path in (first, second)
                ],
                "completion": True,
            }
            gate = execute_artifact_style_precompletion(
                context,
                producer_boundary=_boundary(),
                sql_formatter_runner=_identity_sql_formatter,
            )

        receipts = gate["style_receipts"]
        self.assertEqual(len(receipts), 4, gate)
        self.assertEqual(len({item["call_id"] for item in receipts}), 4)
        self.assertEqual(len({item["result_id"] for item in receipts}), 4)
        sequences = [item["sequence"] for item in receipts]
        self.assertEqual(sequences, sorted(sequences))
        self.assertEqual(len(set(sequences)), 4)
        self.assertTrue(
            all(item["producer_identity"] for item in receipts)
        )
        self.assertTrue(gate["style_passed"], gate)

    def test_reused_execution_ids_across_identical_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _write_sql(root, "first.sql")
            second = root / "second.sql"
            second.write_bytes(first.read_bytes())
            boundary = _boundary()
            context = {
                "project": str(root.resolve()),
                "changed_artifacts": [
                    {
                        "path": str(path.resolve()),
                        "artifact_role": "sql_candidate",
                        "operation": "modified",
                    }
                    for path in (first, second)
                ],
                "completion": True,
            }
            gate = execute_artifact_style_precompletion(
                context,
                producer_boundary=boundary,
                sql_formatter_runner=_identity_sql_formatter,
            )
            receipts = copy.deepcopy(gate["style_receipts"])
            source = receipts[0]
            target = receipts[2]
            for key in (
                "call_id",
                "result_id",
                "sequence",
                "producer_identity",
                "tool_name",
                "execution_output_sha256",
                "execution_call_receipt",
                "execution_result_receipt",
            ):
                target[key] = copy.deepcopy(source[key])
            unsigned = {
                key: value
                for key, value in target.items()
                if key
                not in {
                    "producer_boundary",
                    "authority",
                    "external_authenticity",
                    "receipt_id",
                    "producer_claim",
                }
            }
            receipts[2] = boundary.issue_claim(
                unsigned,
                claim_kind=ARTIFACT_STYLE_RECEIPT_KIND,
                claim_id_field="receipt_id",
                claim_id_prefix="artifact-style",
            )
            checked = analyze_artifact_style_context(
                {
                    "project": str(root.resolve()),
                    "changed_artifacts": gate["changed_artifacts"],
                    "style_receipts": receipts,
                    "completion": True,
                },
                producer_boundary=boundary,
            )

        self.assertFalse(checked["style_passed"])
        self.assertIn(
            "artifact_style_execution_duplicate_or_replay",
            checked["receipt_errors"],
        )

    def test_post_write_executor_invokes_csharp_verifier_on_exact_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root)
            boundary = _boundary()
            result = HarnessResult(
                success=True,
                exit_code=0,
                metadata={"status": "passed"},
            )
            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                return_value=result,
            ) as verifier:
                gate = execute_artifact_style_precompletion(
                    _csharp_context(root, source, designer),
                    producer_boundary=boundary,
                )

            self.assertEqual(verifier.call_count, 2)
            for verifier_call in verifier.call_args_list:
                called_source, called_designer = verifier_call.args
                self.assertEqual(
                    called_source["path"],
                    str(source.resolve()),
                )
                self.assertEqual(
                    called_designer["path"],
                    str(designer.resolve()),
                )
            self.assertEqual(len(gate["style_receipts"]), 2)
            self.assertTrue(gate["style_passed"], gate)

    def test_verifier_not_run_remains_blocked_and_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            context = _sql_context(root, sql_path)
            gate = analyze_artifact_style_context(
                context,
                producer_boundary=_boundary(),
            )
            result = classify_request(
                "Finish the current work.",
                context,
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(gate["completion_blocked"])
        self.assertIn(SQL_STYLE_SKILL, result.recommended_skills)
        self.assertTrue(
            result.intent["artifact_style_gate"]["completion_blocked"]
        )

    def test_duplicate_signed_receipt_row_invalidates_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            boundary = _boundary()
            gate = execute_artifact_style_precompletion(
                _sql_context(root, sql_path),
                producer_boundary=boundary,
                sql_formatter_runner=_identity_sql_formatter,
            )
            gate["style_receipts"].append(
                copy.deepcopy(gate["style_receipts"][0])
            )
            validation = validate_artifact_style_gate_snapshot(
                gate,
                producer_boundary=boundary,
            )

        self.assertFalse(validation["valid"])
        self.assertIn(
            "artifact_style_receipt_duplicate_or_replay",
            validation["errors"],
        )

    def test_current_file_change_invalidates_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            boundary = _boundary()
            gate = execute_artifact_style_precompletion(
                _sql_context(root, sql_path),
                producer_boundary=boundary,
                sql_formatter_runner=_identity_sql_formatter,
            )
            sql_path.write_text(
                sql_path.read_text(encoding="utf-8") + "-- changed\n",
                encoding="utf-8",
            )
            validation = validate_artifact_style_gate_snapshot(
                gate,
                producer_boundary=boundary,
            )

        self.assertFalse(validation["valid"])
        self.assertIn(
            "artifact_style_snapshot_revalidation_failed",
            validation["errors"],
        )

    def test_visual_completion_blocks_without_authenticated_visual_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root)
            gate = analyze_artifact_style_context(
                _csharp_context(
                    root,
                    source,
                    designer,
                    visual_completion=True,
                ),
                producer_boundary=_boundary(),
            )

        self.assertTrue(gate["visual_required"])
        self.assertFalse(gate["visual_passed"])
        self.assertFalse(gate["style_passed"])
        self.assertTrue(gate["completion_blocked"])

    def test_real_visual_receipt_binds_current_artifact_and_tool_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root)
            screenshot = root / "DemoForm.png"
            screenshot.write_bytes(_minimal_png_bytes())
            boundary = _boundary()
            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                return_value=HarnessResult(
                    success=True,
                    exit_code=0,
                    metadata={"status": "passed"},
                ),
            ):
                runtime_gate = execute_artifact_style_precompletion(
                    _csharp_context(root, source, designer),
                )
            receipt = issue_visual_qa_receipt(
                project_root=root,
                visual_artifact_path=screenshot,
                qa_provider="designer",
                runtime_registry_id=runtime_gate["host_registry_id"],
                qa_runner=_visual_qa_runner,
            )
            context = _csharp_context(
                root,
                source,
                designer,
                visual_completion=True,
            )
            context["visual_qa_receipts"] = [receipt]
            gate = analyze_artifact_style_context(
                context,
                producer_boundary=boundary,
            )

        self.assertTrue(gate["visual_passed"])
        self.assertTrue(gate["visual_qa_receipts"][0]["call_id"])
        self.assertTrue(gate["visual_qa_receipts"][0]["result_id"])

    def test_visual_arbitrary_ids_and_malformed_bytes_do_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root)
            screenshot = root / "DemoForm.png"
            screenshot.write_bytes(b"not-a-png")
            boundary = _boundary()
            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                return_value=HarnessResult(
                    success=True,
                    exit_code=0,
                    metadata={"status": "passed"},
                ),
            ):
                runtime_gate = execute_artifact_style_precompletion(
                    _csharp_context(root, source, designer),
                )
            receipt = issue_visual_qa_receipt(
                project_root=root,
                visual_artifact_path=screenshot,
                qa_provider="designer",
                runtime_registry_id=runtime_gate["host_registry_id"],
                qa_runner=_visual_qa_runner,
            )
            receipt["call_id"] = "caller-picked-call"
            receipt["result_id"] = "caller-picked-result"
            context = _csharp_context(
                root,
                source,
                designer,
                visual_completion=True,
            )
            context["visual_qa_receipts"] = [receipt]
            gate = analyze_artifact_style_context(
                context,
                producer_boundary=boundary,
            )

        self.assertFalse(gate["visual_passed"])
        self.assertFalse(gate["style_passed"])
        self.assertIn(
            "visual_receipt_structure_qa_failed",
            gate["visual_receipt_errors"],
        )

    def test_caller_computed_bundle_booleans_cannot_bypass_snapshot(self):
        fake_gate = {
            "required_skills": [CSHARP_STYLE_SKILL],
            "changed_artifacts": [
                {
                    "path": "never-read.cs",
                    "sha256": "sha256:" + "f" * 64,
                }
            ],
            "exact_receipts": True,
            "style_passed": True,
            "completion_claimed": True,
        }
        bundle = build_large_work_orchestration_bundle(
            objective="Complete generated C#.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            overrides={
                CSHARP_STYLE_SKILL: {
                    "status": "applied",
                    "application_mode": "runtime",
                    "evidence_note": "caller claim",
                }
            },
            metadata={"artifact_style_gate": fake_gate},
        )
        bundle_validation = validate_large_work_orchestration_bundle(
            bundle
        )
        transition_validation = validate_skill_transitions(
            bundle,
            phase="final",
        )

        self.assertFalse(bundle_validation["valid"])
        self.assertIn(
            "artifact_style_gate.authenticated_runtime_snapshot",
            bundle_validation["missing"],
        )
        self.assertIn(
            "artifact_style_gate_requires_authenticated_runtime_snapshot",
            {
                issue["rule"]
                for issue in transition_validation["issues"]
            },
        )

    def test_valid_snapshot_is_recomputed_by_bundle_and_transition(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            boundary = _boundary()
            gate = execute_artifact_style_precompletion(
                _sql_context(root, sql_path),
                producer_boundary=boundary,
                sql_formatter_runner=_identity_sql_formatter,
            )
            bundle = build_large_work_orchestration_bundle(
                objective="Complete generated SQL.",
                workspace_strategy="project-local-worktree",
                token_optimizer_status="used",
                compound_handoff={
                    "status": "no_reusable_learning",
                    "no_reusable_learning_rationale": "covered",
                },
                overrides=_style_overrides(gate),
                metadata={"artifact_style_gate": gate},
            )
            bundle_validation = validate_large_work_orchestration_bundle(
                bundle,
                artifact_style_producer_boundary=boundary,
            )
            transition_validation = validate_skill_transitions(
                bundle,
                phase="final",
                artifact_style_producer_boundary=boundary,
            )

        self.assertNotIn(
            "artifact_style_gate.authenticated_runtime_snapshot",
            bundle_validation["missing"],
        )
        self.assertFalse(
            any(
                issue["rule"].startswith("artifact_style_gate_")
                for issue in transition_validation["issues"]
            ),
            transition_validation,
        )

    def test_historical_or_synthetic_task_ids_never_create_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            gate = analyze_artifact_style_context(
                {
                    **_sql_context(root, sql_path),
                    "prior_task_id": "synthetic-prior-task",
                    "corrective_task_id": "synthetic-corrective-task",
                    "style_passed": True,
                    "exact_receipts": True,
                },
                producer_boundary=_boundary(),
            )

        self.assertFalse(gate["style_passed"])
        self.assertTrue(gate["completion_blocked"])

    def test_frontdoor_executes_selected_sql_provider_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            formatter = mock.Mock(side_effect=_identity_sql_formatter)
            result = build_kh_front_door(
                "Format and finish this SQL candidate.",
                project=root,
                host="codex",
                request_context=_sql_context(root, sql_path),
                provider_runners={"sql-formatting": formatter},
            )
            gate = result.classification["intent"]["artifact_style_gate"]

        formatter.assert_called_once()
        self.assertTrue(gate["style_passed"], gate)
        self.assertFalse(gate["completion_blocked"], gate)

    def test_product_cli_reaches_csharp_prewrite_write_validate_consume_boundary(self):
        passed = HarnessResult(
            success=True,
            exit_code=0,
            metadata={"status": "passed"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DemoForm.cs"
            designer = root / "DemoForm.Designer.cs"
            operation_file = root / "artifact-operation.json"
            operation_file.write_text(
                json.dumps(
                    {
                        "action": "execute",
                        "project_root": str(root.resolve()),
                        "pair_id": "demo-form",
                        "operation": "generation",
                        "codebehind_path": str(source.resolve()),
                        "designer_path": str(designer.resolve()),
                        "artifact_contents": {
                            "winforms_codebehind": VALID_SOURCE,
                            "winforms_designer": VALID_DESIGNER,
                        },
                    }
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            argv = [
                "kh_front_door.py",
                "--artifact-operation-file",
                str(operation_file),
            ]
            with (
                mock.patch("sys.argv", argv),
                mock.patch(
                    "src.skills.csharp_designer_style_contract."
                    "verify_csharp_designer_style",
                    return_value=passed,
                ),
                redirect_stdout(stdout),
            ):
                exit_code = kh_front_door_main()
            payload = json.loads(stdout.getvalue())
            source_output = source.read_text(encoding="utf-8")
            designer_output = designer.read_text(encoding="utf-8")

        self.assertEqual(0, exit_code, payload)
        self.assertTrue(payload["style_passed"], payload)
        self.assertEqual(VALID_SOURCE, source_output)
        self.assertEqual(VALID_DESIGNER, designer_output)
        self.assertEqual(
            "execute_kh_artifact_write_operation>"
            "execute_csharp_artifact_operation>prewrite_or_preedit_receipt>"
            "write_artifacts>execute_artifact_style_precompletion",
            payload["artifact_operation"]["public_call_path"],
        )
        self.assertEqual(
            "consumed_after_style_pass",
            payload["operation_receipt_lifecycle"],
        )

    def test_frontdoor_completion_fails_closed_when_csharp_write_boundary_bypassed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root)
            result = build_kh_front_door(
                "Complete the generated C# screen.",
                project=root,
                host="codex",
                request_context={
                    "project": str(root.resolve()),
                    "generated_artifacts": [
                        {
                            "path": str(source.resolve()),
                            "artifact_role": "winforms_codebehind",
                            "pair_id": "demo-form",
                            "operation": "generation",
                        },
                        {
                            "path": str(designer.resolve()),
                            "artifact_role": "winforms_designer",
                            "pair_id": "demo-form",
                            "operation": "generation",
                        },
                    ],
                    "completion": True,
                },
            )
            gate = result.classification["intent"]["artifact_style_gate"]

        self.assertFalse(gate["style_passed"], gate)
        self.assertTrue(gate["completion_blocked"], gate)
        self.assertTrue(
            any(
                item.startswith("csharp_generation_prewrite_receipt_required:")
                for item in gate["executor_errors"]
            ),
            gate,
        )

    def test_production_cli_executes_default_packaged_sql_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            context_file = root / "context.json"
            context_file.write_text(
                json.dumps(_sql_context(root, sql_path)),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            argv = [
                "kh_front_door.py",
                "--prompt",
                "Format and finish this SQL candidate.",
                "--project",
                str(root),
                "--host",
                "codex",
                "--context-file",
                str(context_file),
            ]
            with mock.patch("sys.argv", argv), redirect_stdout(stdout):
                exit_code = kh_front_door_main()
            payload = json.loads(stdout.getvalue())
            gate = payload["classification"]["intent"]["artifact_style_gate"]

        formatting = next(
            item
            for item in gate["style_receipts"]
            if item["gate"] == SQL_FORMATTING_SKILL
        )
        self.assertEqual(exit_code, 0)
        self.assertTrue(gate["style_passed"], gate)
        self.assertTrue(gate["host_registry_id"].startswith("host-registry-"))
        self.assertEqual(
            formatting["host_registry_id"],
            gate["host_registry_id"],
        )
        self.assertEqual(
            formatting["execution_call_receipt"]["host_registry_id"],
            gate["host_registry_id"],
        )
        self.assertEqual(
            formatting["execution_result_receipt"]["host_registry_id"],
            gate["host_registry_id"],
        )
        self.assertEqual(
            formatting["formatter_history"][-1]["engine"],
            "src.skills.sql_formatting_style.normalize_sql_join_layout",
        )
        self.assertTrue(formatting["execution_output_sha256"])
        self.assertTrue(formatting["formatted_output_sha256"])
        self.assertTrue(formatting["verifier_history"])

    def test_boundary_only_visual_registry_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "screen.png"
            screenshot.write_bytes(_minimal_png_bytes())
            external_registry = HostCallResultRegistry(_boundary())

            with self.assertRaisesRegex(ValueError, "executor-owned"):
                issue_visual_qa_receipt(
                    project_root=root,
                    visual_artifact_path=screenshot,
                    qa_provider="designer",
                    host_registry=external_registry,
                    qa_runner=_visual_qa_runner,
                )

    def test_receipts_require_registered_host_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sql_path = _write_sql(root)
            gate = execute_artifact_style_precompletion(
                _sql_context(root, sql_path),
                sql_formatter_runner=_identity_sql_formatter,
            )
            receipts = copy.deepcopy(gate["style_receipts"])
            for receipt in receipts:
                receipt["host_registry_id"] = "host-registry-not-registered"
            checked = analyze_artifact_style_context(
                {
                    **_sql_context(root, sql_path),
                    "style_receipts": receipts,
                }
            )

        self.assertFalse(checked["style_passed"])
        self.assertIn(
            "artifact_host_registry_lookup_required",
            checked["receipt_errors"],
        )

    def test_style_visual_sequence_collision_is_rejected_globally(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root)
            screenshot = root / "DemoForm.png"
            screenshot.write_bytes(_minimal_png_bytes())
            with mock.patch(
                "src.skills.csharp_designer_style_contract."
                "verify_csharp_designer_style",
                return_value=HarnessResult(
                    success=True,
                    exit_code=0,
                    metadata={"status": "passed"},
                ),
            ):
                runtime_gate = execute_artifact_style_precompletion(
                    _csharp_context(root, source, designer),
                )
            visual = issue_visual_qa_receipt(
                project_root=root,
                visual_artifact_path=screenshot,
                qa_provider="designer",
                runtime_registry_id=runtime_gate["host_registry_id"],
                qa_runner=_visual_qa_runner,
            )
            visual["sequence"] = runtime_gate["style_receipts"][0]["sequence"]
            context = _csharp_context(
                root,
                source,
                designer,
                visual_completion=True,
            )
            context["style_receipts"] = runtime_gate["style_receipts"]
            context["visual_qa_receipts"] = [visual]
            checked = analyze_artifact_style_context(context)

        self.assertFalse(checked["style_passed"])
        self.assertIn(
            "artifact_execution_sequence_not_monotonic",
            checked["visual_receipt_errors"],
        )


if __name__ == "__main__":
    unittest.main()
