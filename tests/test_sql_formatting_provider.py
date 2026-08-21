import hashlib
import inspect
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.orchestration.kh_front_door import build_kh_front_door
from src.contracts import HarnessResult
from src.skills.sql_formatting_provider import (
    SQL_PROVIDER_RECEIPT_CLAIM_KIND,
    SQL_PROVIDER_SELECTION_RECEIPT_CLAIM_KIND,
    SqlFinalResponseBindingError,
    SqlFormattingProviderPathError,
    _provider_path_key,
    _sql_provider_runtime_boundary,
    _sql_provider_selection_runtime_boundary,
    attach_sql_formatting_cli_runtime_receipt,
    attach_sql_provider_selection_runtime_receipt,
    bind_verified_sql_final_response,
    evaluate_sql_formatting_repair_gate,
    guard_and_bind_verified_sql_final_response,
    guard_authoritative_sql_formatting_provider_path,
    inspect_host_sql_formatting_provider,
    inspect_packaged_sql_formatting_provider,
    load_sql_formatting_cli_artifacts,
    packaged_sql_formatting_provider,
    sql_provider_selection_sha256,
    validate_sql_formatting_cli_runtime_receipt,
    validate_sql_provider_selection_runtime_receipt,
)
from src.skills.sql_formatting_style import verify_sql_formatting_style


class SqlFormattingProviderTests(unittest.TestCase):
    COMPATIBLE_HOST_SKILL = """---
name: sql-formatting
description: Format SQL/T-SQL while preserving query behavior and semantics.
---

# SQL Formatting

Do not change query behavior. Preserve table names, predicates, expressions, and results.
Convert a scalar lookup to a JOIN only when its implementation and relational equivalence are verified.
Run the packaged `sql-formatting-style-harness` deterministic verifier and accept output only when it passes.

## Examples

For example, `DBO.F_SAMPLE_NAME(...)` and `SAMPLE_LOOKUP_TABLE` may illustrate input shape only.
They are not general conversion mandates.
"""

    CURRENT_HOST_LOCAL_SHAPE = """---
name: sql-formatting
description: Preserve SQL logic and allow verified lookup scalar-function-to-join conversions.
---

# SQL Formatting

Do not change query behavior.
Unknown scalar functions must stay scalar functions unless their contract proves an equivalent lookup join.

## BA011T Name Lookup

`DBO.F_BA011T_FIND_SUBNM(MAINCD, SUBCD, USEYN)` has a verified lookup contract in this skill.
When SQL contains this function, replace it with a `LEFT OUTER JOIN BA011T` lookup.
Join `BA011T` with `MAINCD`, `SUBCD`, and `USEYN`, then select `SUBNM`.
"""

    @staticmethod
    def verifier_result(success):
        return {
            "success": success,
            "exit_code": 0 if success else 1,
            "metadata": {
                "release_readiness": {"status": "ready" if success else "blocked"},
                "issues": [] if success else [{"code": "join_layout_invalid"}],
            },
        }

    def test_repair_gate_allows_one_evidence_directed_repair(self):
        first = evaluate_sql_formatting_repair_gate([self.verifier_result(False)])
        repaired = evaluate_sql_formatting_repair_gate(
            [self.verifier_result(False), self.verifier_result(True)],
            repair_issue_codes=["join_layout_invalid"],
        )

        self.assertEqual(first.status, "repair_allowed")
        self.assertTrue(first.repair_allowed)
        self.assertFalse(first.sql_delivery_allowed)
        self.assertEqual(repaired.status, "ready")
        self.assertFalse(repaired.repair_allowed)
        self.assertTrue(repaired.sql_delivery_allowed)

    def test_repair_gate_blocks_after_failed_repair_and_never_releases_later_sql(self):
        failed_repair = evaluate_sql_formatting_repair_gate(
            [self.verifier_result(False), self.verifier_result(False)],
            repair_issue_codes=["join_layout_invalid"],
        )
        late_success = evaluate_sql_formatting_repair_gate(
            [
                self.verifier_result(False),
                self.verifier_result(False),
                self.verifier_result(True),
            ],
            repair_issue_codes=["join_layout_invalid"],
        )

        for decision in (failed_repair, late_success):
            self.assertEqual(decision.status, "blocked")
            self.assertEqual(
                decision.blocked_reason,
                "sql_formatting_repair_limit_exhausted",
            )
            self.assertFalse(decision.repair_allowed)
            self.assertFalse(decision.sql_delivery_allowed)

    def test_repair_gate_blocks_second_attempt_without_issue_evidence(self):
        first = self.verifier_result(False)
        second = self.verifier_result(True)
        first["metadata"]["issues"] = []
        second["metadata"]["issues"] = []
        decision = evaluate_sql_formatting_repair_gate(
            [first, second]
        )

        self.assertEqual(decision.status, "blocked")
        self.assertEqual(
            decision.blocked_reason,
            "sql_formatting_repair_evidence_required",
        )
        self.assertFalse(decision.sql_delivery_allowed)

    def test_public_release_rejects_missing_nonready_and_late_repair_history(self):
        original = "SELECT ORDER_ID FROM ORDER_HEADER;"
        candidate = "SELECT ORDER_ID\nFROM ORDER_HEADER;"
        response = f"```sql\n{candidate}\n```"
        ready = verify_sql_formatting_style(original, candidate).to_dict()
        blocked = verify_sql_formatting_style(
            original,
            candidate.replace("ORDER_ID", "CUSTOMER_ID"),
        ).to_dict()
        with tempfile.TemporaryDirectory() as tmp:
            provider_path = self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)
            selection = self.provider_selection(provider_path)
            common = {
                "provider_path": provider_path,
                "selected_active_provider_path": provider_path,
                "provider_selection": selection,
            }
            cases = {
                "missing": (None, "sql_formatting_repair_history_required"),
                "nonready": (
                    [blocked],
                    "sql_formatting_repair_decision_not_ready",
                ),
                "second_failed": (
                    [blocked, blocked],
                    "sql_formatting_repair_limit_exhausted",
                ),
                "late_success": (
                    [blocked, blocked, ready],
                    "sql_formatting_repair_limit_exhausted",
                ),
            }
            for label, (history, expected) in cases.items():
                with self.subTest(label=label):
                    with self.assertRaises(SqlFinalResponseBindingError) as raised:
                        guard_and_bind_verified_sql_final_response(
                            original,
                            candidate,
                            response,
                            verifier_history=history,
                            **common,
                        )
                    self.assertEqual(raised.exception.code, expected)

            release = guard_and_bind_verified_sql_final_response(
                original,
                candidate,
                response,
                verifier_history=[ready],
                **common,
            )
            self.assertEqual(release.status, "passed")

    def write_host_skill(self, root, content):
        skill_path = Path(root) / "skills" / "sql-formatting" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text(content, encoding="utf-8")
        return skill_path

    @staticmethod
    def valid_cli_release(root):
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        verification_id = "9" * 64
        paths = {
            "original_file": str(root / "original.sql"),
            "candidate_file": str(root / "candidate.sql"),
            "response_file": str(root / "response.md"),
            "provider_selection_file": str(root / "provider-selection.json"),
            "provider_path": str(root / "skills" / "sql_formatting" / "SKILL.md"),
            "selected_active_provider_path": str(
                root / "skills" / "sql_formatting" / "SKILL.md"
            ),
        }
        original_text = "SELECT 1;"
        candidate_text = "SELECT 1;"
        response_text = f"```sql\n{candidate_text}\n```"
        provider_selection = attach_sql_provider_selection_runtime_receipt(
            {
                "schema_version": 1,
                "host": "local",
                "project": str(root),
                "provider_id": "sql-formatting",
                "provider_path": paths["provider_path"],
                "selected_active_provider_path": paths[
                    "selected_active_provider_path"
                ],
                "provider_source": "host-local-skill",
                "compatibility": "compatible",
                "selection_status": "selected",
                "front_door_status": "ok",
                "plugin_route": {
                    "route": "single",
                    "controller": {
                        "provider_id": "sql-formatting",
                        "capability": "sql_formatting",
                        "metadata": {
                            "path": paths["provider_path"],
                            "source": "host-local-skill",
                            "compatibility": "compatible",
                        },
                    },
                },
                "execution_gate": {
                    "can_execute": True,
                    "status": "execution_allowed_after_selected_skill_setup",
                    "reason": "SQL formatting provider selected.",
                },
            }
        )
        artifact_text = {
            "original_file": original_text,
            "candidate_file": candidate_text,
            "response_file": response_text,
            "provider_selection_file": json.dumps(
                provider_selection,
                separators=(",", ":"),
                sort_keys=True,
            ),
        }
        for key, text in artifact_text.items():
            Path(paths[key]).parent.mkdir(parents=True, exist_ok=True)
            Path(paths[key]).write_text(text, encoding="utf-8", newline="")
        Path(paths["provider_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(paths["provider_path"]).write_text("provider fixture", encoding="utf-8")
        hashes = {
            "original_text_sha256": hashlib.sha256(
                original_text.encode("utf-8")
            ).hexdigest(),
            "candidate_text_sha256": hashlib.sha256(
                candidate_text.encode("utf-8")
            ).hexdigest(),
            "response_text_sha256": hashlib.sha256(
                response_text.encode("utf-8")
            ).hexdigest(),
            "provider_selection_sha256": sql_provider_selection_sha256(
                provider_selection
            ),
            **{
                f"{key}_sha256": hashlib.sha256(Path(paths[key]).read_bytes()).hexdigest()
                for key in artifact_text
            },
        }
        return {
            "status": "passed",
            "provider_path_guard": {
                "status": "accepted",
                "authority": "selected-active-provider",
                "provider_path": paths["provider_path"],
                "selected_active_provider_path": paths[
                    "selected_active_provider_path"
                ],
                "current_packaged_fallback_path": str(
                    (
                        Path(__file__).resolve().parents[1]
                        / "skills"
                        / "sql_formatting"
                        / "SKILL.md"
                    ).resolve()
                ),
                "provider_id": "sql-formatting",
                "provider_source": "host-local-skill",
                "provider_selection_sha256": hashes["provider_selection_sha256"],
            },
            "binding": {
                "status": "bound",
                "original_sha256": hashes["original_text_sha256"],
                "formatted_sha256": hashes["candidate_text_sha256"],
                "final_response_sha256": hashes["response_text_sha256"],
                "verification_id": verification_id,
                "sql_fence_count": 1,
            },
            "verification": {
                "success": True,
                "exit_code": 0,
                "stdout": '{"status":"passed"}',
                "stderr": "",
                "execution_time": 0.0,
                "metadata": {
                    "harness": "sql-formatting-style-harness",
                    "operation": "formatting",
                    "token_optimizer_status": "passthrough",
                    "not_used_reason": "Exact SQL evidence requires passthrough.",
                    "original_sha256": hashes["original_text_sha256"],
                    "formatted_sha256": hashes["candidate_text_sha256"],
                    "verification_id": verification_id,
                    "release_readiness": {"status": "ready"},
                },
            },
            "cli_inputs": {
                "module": "src.skills.sql_formatting_provider",
                "exit_status": 0,
                "arguments": {
                    **paths,
                    "session_id": "provider-api-session",
                    "invocation_nonce": "provider-api-nonce-0001",
                },
                "resolved_paths": dict(paths),
                "hashes": hashes,
            },
        }

    def test_cli_runtime_receipt_issuer_requires_complete_successful_input_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = {
                "argument": ("arguments", "original_file", "cli_input_argument_original_file_missing"),
                "resolved_path": (
                    "resolved_paths",
                    "original_file",
                    "cli_input_resolved_path_original_file_missing",
                ),
                "canonical_hash": (
                    "hashes",
                    "original_text_sha256",
                    "cli_input_hash_original_text_sha256_missing_or_invalid",
                ),
                "raw_hash": (
                    "hashes",
                    "original_file_sha256",
                    "cli_input_hash_original_file_sha256_missing_or_invalid",
                ),
            }
            for label, (category, field, expected) in cases.items():
                with self.subTest(label=label):
                    release = self.valid_cli_release(tmp)
                    release["cli_inputs"][category].pop(field)
                    with self.assertRaises(SqlFinalResponseBindingError) as raised:
                        attach_sql_formatting_cli_runtime_receipt(
                            release,
                            session_id="provider-api-session",
                            invocation_nonce="provider-api-nonce-0001",
                        )
                    self.assertEqual(raised.exception.code, expected)

    def test_cli_runtime_receipt_issuer_rejects_malformed_hash_and_path_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            malformed = self.valid_cli_release(tmp)
            malformed["cli_inputs"]["hashes"]["candidate_file_sha256"] = "not-a-sha"
            with self.assertRaises(SqlFinalResponseBindingError) as bad_hash:
                attach_sql_formatting_cli_runtime_receipt(
                    malformed,
                    session_id="provider-api-session",
                    invocation_nonce="provider-api-nonce-0001",
                )

            mismatched = self.valid_cli_release(tmp)
            mismatched["cli_inputs"]["resolved_paths"]["candidate_file"] = str(
                Path(tmp).resolve() / "other.sql"
            )
            with self.assertRaises(SqlFinalResponseBindingError) as bad_path:
                attach_sql_formatting_cli_runtime_receipt(
                    mismatched,
                    session_id="provider-api-session",
                    invocation_nonce="provider-api-nonce-0001",
                )

        self.assertEqual(
            bad_hash.exception.code,
            "cli_input_hash_candidate_file_sha256_missing_or_invalid",
        )
        self.assertEqual(
            bad_path.exception.code,
            "cli_input_path_candidate_file_mismatch",
        )

    def test_cli_runtime_receipt_validator_reports_schema_errors_with_valid_hmac(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = {
                "argument": ("arguments", "original_file", None, "cli_input_argument_original_file_missing"),
                "resolved_path": (
                    "resolved_paths",
                    "original_file",
                    None,
                    "cli_input_resolved_path_original_file_missing",
                ),
                "canonical_hash": (
                    "hashes",
                    "original_text_sha256",
                    None,
                    "cli_input_hash_original_text_sha256_missing_or_invalid",
                ),
                "raw_hash": (
                    "hashes",
                    "original_file_sha256",
                    None,
                    "cli_input_hash_original_file_sha256_missing_or_invalid",
                ),
                "malformed_hash": (
                    "hashes",
                    "response_file_sha256",
                    "bad",
                    "cli_input_hash_response_file_sha256_missing_or_invalid",
                ),
                "path_mismatch": (
                    "resolved_paths",
                    "response_file",
                    str(Path(tmp).resolve() / "other.md"),
                    "cli_input_path_response_file_mismatch",
                ),
            }
            for label, (category, field, replacement, expected) in cases.items():
                with self.subTest(label=label):
                    release = self.valid_cli_release(tmp)
                    if replacement is None:
                        release["cli_inputs"][category].pop(field)
                    else:
                        release["cli_inputs"][category][field] = replacement
                    with patch(
                        "src.skills.sql_formatting_provider.validate_sql_final_response_release_schema",
                        return_value=[],
                    ):
                        signed = attach_sql_formatting_cli_runtime_receipt(
                            release,
                            session_id="provider-api-session",
                            invocation_nonce="provider-api-nonce-0001",
                        )
                    errors = validate_sql_formatting_cli_runtime_receipt(
                        signed,
                        expected_session_id="provider-api-session",
                        expected_invocation_nonce="provider-api-nonce-0001",
                        expected_provider_selection_sha256=signed["cli_inputs"]["hashes"]["provider_selection_sha256"],
                    )
                    self.assertIn(expected, errors)
                    self.assertFalse(
                        any("producer_claim" in error for error in errors),
                        errors,
                    )

    def test_cli_runtime_receipt_public_api_accepts_complete_successful_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            signed = attach_sql_formatting_cli_runtime_receipt(
                self.valid_cli_release(tmp),
                session_id="provider-api-session",
                invocation_nonce="provider-api-nonce-0001",
            )
            self.assertEqual(
                validate_sql_formatting_cli_runtime_receipt(
                    signed,
                    expected_session_id="provider-api-session",
                    expected_invocation_nonce="provider-api-nonce-0001",
                    expected_provider_selection_sha256=signed["cli_inputs"]["hashes"]["provider_selection_sha256"],
                ),
                [],
            )

    def test_cli_runtime_receipt_rejects_exact_schema_extras_and_split_provider_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = {
                "cli_inputs": (
                    ("cli_inputs", "unexpected"),
                    True,
                    "cli_input_unexpected_unexpected",
                ),
                "arguments": (
                    ("cli_inputs", "arguments", "unexpected"),
                    "value",
                    "cli_input_argument_unexpected_unexpected",
                ),
                "resolved_paths": (
                    ("cli_inputs", "resolved_paths", "unexpected"),
                    "value",
                    "cli_input_resolved_path_unexpected_unexpected",
                ),
                "hashes": (
                    ("cli_inputs", "hashes", "unexpected"),
                    "a" * 64,
                    "cli_input_hash_unexpected_unexpected",
                ),
            }
            for label, (path, replacement, expected) in cases.items():
                with self.subTest(label=label):
                    release = self.valid_cli_release(tmp)
                    target = release
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = replacement
                    with self.assertRaises(SqlFinalResponseBindingError) as raised:
                        attach_sql_formatting_cli_runtime_receipt(
                            release,
                            session_id="provider-api-session",
                            invocation_nonce="provider-api-nonce-0001",
                        )
                    self.assertEqual(raised.exception.code, expected)

            split = self.valid_cli_release(tmp)
            selected = str(Path(tmp).resolve() / "other" / "SKILL.md")
            split["cli_inputs"]["arguments"]["selected_active_provider_path"] = selected
            split["cli_inputs"]["resolved_paths"]["selected_active_provider_path"] = selected
            split["provider_path_guard"]["selected_active_provider_path"] = selected
            with self.assertRaises(SqlFinalResponseBindingError) as raised:
                attach_sql_formatting_cli_runtime_receipt(
                    split,
                    session_id="provider-api-session",
                    invocation_nonce="provider-api-nonce-0001",
                )
            self.assertEqual(raised.exception.code, "cli_input_provider_paths_mismatch")

    def test_cli_runtime_receipt_reopens_artifacts_before_signing_and_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale_before_signing = self.valid_cli_release(tmp)
            Path(
                stale_before_signing["cli_inputs"]["resolved_paths"]["original_file"]
            ).write_bytes(b"\xef\xbb\xbfSELECT 1;")
            with self.assertRaises(SqlFinalResponseBindingError) as raised:
                attach_sql_formatting_cli_runtime_receipt(
                    stale_before_signing,
                    session_id="provider-api-session",
                    invocation_nonce="provider-api-nonce-0001",
                )
            self.assertEqual(
                raised.exception.code,
                "cli_input_original_file_raw_hash_mismatch",
            )

        with tempfile.TemporaryDirectory() as tmp:
            release = self.valid_cli_release(tmp)
            signed = attach_sql_formatting_cli_runtime_receipt(
                release,
                session_id="provider-api-session",
                invocation_nonce="provider-api-nonce-0001",
            )
            Path(signed["cli_inputs"]["resolved_paths"]["candidate_file"]).write_text(
                "SELECT 2;",
                encoding="utf-8",
            )
            errors = validate_sql_formatting_cli_runtime_receipt(
                signed,
                expected_session_id="provider-api-session",
                expected_invocation_nonce="provider-api-nonce-0001",
                expected_provider_selection_sha256=signed["cli_inputs"]["hashes"]["provider_selection_sha256"],
            )
            self.assertIn("cli_input_candidate_file_raw_hash_mismatch", errors)
            self.assertIn("cli_input_candidate_file_hash_mismatch", errors)

    def test_provider_selection_file_rejects_duplicate_json_keys_recursively(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = self.valid_cli_release(tmp)
            paths = release["cli_inputs"]["resolved_paths"]
            duplicate_payloads = {
                "provider_id": '{"provider_id":"sql-formatting","provider_id":"other"}',
                "nested": '{"provider_id":"sql-formatting","nested":{"status":"ok","status":"blocked"}}',
            }
            for label, payload in duplicate_payloads.items():
                with self.subTest(label=label):
                    Path(paths["provider_selection_file"]).write_text(
                        payload,
                        encoding="utf-8",
                    )
                    with self.assertRaises(Exception) as raised:
                        load_sql_formatting_cli_artifacts(
                            original_file=paths["original_file"],
                            candidate_file=paths["candidate_file"],
                            response_file=paths["response_file"],
                            provider_selection_file=paths["provider_selection_file"],
                        )
                    self.assertEqual(
                        getattr(raised.exception, "code", ""),
                        "provider_selection_file_read_failed",
                    )

    def test_cli_runtime_receipt_issuer_rejects_full_release_schema_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = {
                "status_false": (
                    ("status",),
                    False,
                    "final_response_release_status_not_string",
                ),
                "status_blocked": (
                    ("status",),
                    "blocked",
                    "final_response_release_status_not_passed",
                ),
                "missing_binding": (
                    ("binding",),
                    None,
                    "final_response_release_binding_missing",
                ),
                "missing_guard": (
                    ("provider_path_guard",),
                    None,
                    "final_response_release_provider_path_guard_missing",
                ),
                "missing_verification": (
                    ("verification",),
                    None,
                    "final_response_release_verification_missing",
                ),
                "binding_verification_id_bool": (
                    ("binding", "verification_id"),
                    True,
                    "final_response_binding_verification_id_not_string",
                ),
                "fence_bool": (
                    ("binding", "sql_fence_count"),
                    True,
                    "final_response_binding_sql_fence_count_not_integer",
                ),
                "binding_extra_coercible": (
                    ("binding", "legacy_fence_count"),
                    1,
                    "final_response_binding_legacy_fence_count_unexpected",
                ),
                "guard_authority": (
                    ("provider_path_guard", "authority"),
                    "caller-selected",
                    "provider_path_guard_authority_mismatch",
                ),
                "guard_path": (
                    ("provider_path_guard", "provider_path"),
                    str(Path(tmp).resolve() / "other" / "SKILL.md"),
                    "provider_path_guard_provider_path_mismatch",
                ),
                "verification_id_bool": (
                    ("verification", "metadata", "verification_id"),
                    True,
                    "final_response_verification_verification_id_not_string",
                ),
            }
            for label, (path, replacement, expected) in cases.items():
                with self.subTest(label=label):
                    release = self.valid_cli_release(tmp)
                    target = release
                    for key in path[:-1]:
                        target = target[key]
                    if replacement is None:
                        target.pop(path[-1])
                    else:
                        target[path[-1]] = replacement
                    with self.assertRaises(SqlFinalResponseBindingError) as raised:
                        attach_sql_formatting_cli_runtime_receipt(
                            release,
                            session_id="provider-api-session",
                            invocation_nonce="provider-api-nonce-0001",
                        )
                    self.assertEqual(raised.exception.code, expected)

    def test_cli_runtime_receipt_validator_rejects_full_release_schema_with_valid_hmac(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = {
                "status_false": (
                    ("status",),
                    False,
                    "final_response_release_status_not_string",
                ),
                "status_blocked": (
                    ("status",),
                    "blocked",
                    "final_response_release_status_not_passed",
                ),
                "missing_binding": (
                    ("binding",),
                    None,
                    "final_response_release_binding_missing",
                ),
                "missing_guard": (
                    ("provider_path_guard",),
                    None,
                    "final_response_release_provider_path_guard_missing",
                ),
                "missing_verification": (
                    ("verification",),
                    None,
                    "final_response_release_verification_missing",
                ),
                "binding_verification_id_bool": (
                    ("binding", "verification_id"),
                    True,
                    "final_response_binding_verification_id_not_string",
                ),
                "fence_bool": (
                    ("binding", "sql_fence_count"),
                    True,
                    "final_response_binding_sql_fence_count_not_integer",
                ),
                "binding_extra_coercible": (
                    ("binding", "legacy_fence_count"),
                    1,
                    "final_response_binding_legacy_fence_count_unexpected",
                ),
                "guard_authority": (
                    ("provider_path_guard", "authority"),
                    "caller-selected",
                    "provider_path_guard_authority_mismatch",
                ),
                "guard_path": (
                    ("provider_path_guard", "provider_path"),
                    str(Path(tmp).resolve() / "other" / "SKILL.md"),
                    "provider_path_guard_provider_path_mismatch",
                ),
                "verification_id_bool": (
                    ("verification", "metadata", "verification_id"),
                    True,
                    "final_response_verification_verification_id_not_string",
                ),
            }
            for label, (path, replacement, expected) in cases.items():
                with self.subTest(label=label):
                    release = self.valid_cli_release(tmp)
                    target = release
                    for key in path[:-1]:
                        target = target[key]
                    if replacement is None:
                        target.pop(path[-1])
                    else:
                        target[path[-1]] = replacement
                    with patch(
                        "src.skills.sql_formatting_provider.validate_sql_final_response_release_schema",
                        return_value=[],
                        create=True,
                    ):
                        signed = attach_sql_formatting_cli_runtime_receipt(
                            release,
                            session_id="provider-api-session",
                            invocation_nonce="provider-api-nonce-0001",
                        )
                    errors = validate_sql_formatting_cli_runtime_receipt(
                        signed,
                        expected_session_id="provider-api-session",
                        expected_invocation_nonce="provider-api-nonce-0001",
                        expected_provider_selection_sha256=signed["cli_inputs"]["hashes"]["provider_selection_sha256"],
                    )
                    self.assertIn(expected, errors)
                    self.assertNotIn("runtime_producer_claim_mismatch", errors)

    def test_cli_runtime_receipt_validator_rejects_verified_external_authenticity(self):
        with tempfile.TemporaryDirectory() as tmp:
            signed = attach_sql_formatting_cli_runtime_receipt(
                self.valid_cli_release(tmp),
                session_id="provider-api-session",
                invocation_nonce="provider-api-nonce-0001",
            )
        signed["runtime_receipt"]["external_authenticity"] = "verified"
        boundary = _sql_provider_runtime_boundary()
        signed["runtime_receipt"]["producer_claim"] = boundary._claim_digest(
            signed["runtime_receipt"]
        )

        errors = validate_sql_formatting_cli_runtime_receipt(
            signed,
            expected_session_id="provider-api-session",
            expected_invocation_nonce="provider-api-nonce-0001",
            expected_provider_selection_sha256=signed["cli_inputs"]["hashes"]["provider_selection_sha256"],
        )

        self.assertIn(
            "sql_provider_runtime_receipt_external_authenticity_mismatch",
            errors,
        )
        self.assertNotIn("runtime_producer_claim_mismatch", errors)

    def test_cli_runtime_receipt_issuer_rejects_type_confused_scalars(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = {
                "exit_false": ("exit_status", None, False, "cli_input_exit_status_not_integer"),
                "exit_float": ("exit_status", None, 0.0, "cli_input_exit_status_not_integer"),
                "exit_string": ("exit_status", None, "0", "cli_input_exit_status_not_integer"),
                "numeric_hash": (
                    "hashes",
                    "original_text_sha256",
                    1,
                    "cli_input_hash_original_text_sha256_not_string",
                ),
                "numeric_path": (
                    "arguments",
                    "original_file",
                    7,
                    "cli_input_argument_original_file_not_string",
                ),
                "numeric_session": (
                    "arguments",
                    "session_id",
                    9,
                    "cli_input_argument_session_id_not_string",
                ),
                "numeric_nonce": (
                    "arguments",
                    "invocation_nonce",
                    11,
                    "cli_input_argument_invocation_nonce_not_string",
                ),
                "list_module": ("module", None, [], "cli_input_module_not_string"),
                "object_resolved_path": (
                    "resolved_paths",
                    "candidate_file",
                    {},
                    "cli_input_resolved_path_candidate_file_not_string",
                ),
                "null_hash": (
                    "hashes",
                    "response_text_sha256",
                    None,
                    "cli_input_hash_response_text_sha256_not_string",
                ),
            }
            for label, (category, field, replacement, expected) in cases.items():
                with self.subTest(label=label):
                    release = self.valid_cli_release(tmp)
                    if field is None:
                        release["cli_inputs"][category] = replacement
                    else:
                        release["cli_inputs"][category][field] = replacement
                    with self.assertRaises(SqlFinalResponseBindingError) as raised:
                        attach_sql_formatting_cli_runtime_receipt(
                            release,
                            session_id="provider-api-session",
                            invocation_nonce="provider-api-nonce-0001",
                        )
                    self.assertEqual(raised.exception.code, expected)

            with self.assertRaises(SqlFinalResponseBindingError) as numeric_scope:
                attach_sql_formatting_cli_runtime_receipt(
                    self.valid_cli_release(tmp),
                    session_id=13,
                    invocation_nonce="provider-api-nonce-0001",
                )
            with self.assertRaises(SqlFinalResponseBindingError) as numeric_nonce:
                attach_sql_formatting_cli_runtime_receipt(
                    self.valid_cli_release(tmp),
                    session_id="provider-api-session",
                    invocation_nonce=17,
                )
        self.assertEqual(numeric_scope.exception.code, "session_scope_not_string")
        self.assertEqual(numeric_nonce.exception.code, "invocation_nonce_not_string")

    def test_cli_runtime_receipt_validator_rejects_type_confusion_with_valid_hmac(self):
        with tempfile.TemporaryDirectory() as tmp:
            cli_cases = {
                "exit_false": ("exit_status", None, False, "cli_input_exit_status_not_integer"),
                "exit_float": ("exit_status", None, 0.0, "cli_input_exit_status_not_integer"),
                "exit_string": ("exit_status", None, "0", "cli_input_exit_status_not_integer"),
                "numeric_hash": (
                    "hashes",
                    "candidate_file_sha256",
                    123,
                    "cli_input_hash_candidate_file_sha256_not_string",
                ),
                "numeric_path": (
                    "resolved_paths",
                    "response_file",
                    456,
                    "cli_input_resolved_path_response_file_not_string",
                ),
                "list_argument": (
                    "arguments",
                    "provider_path",
                    [],
                    "cli_input_argument_provider_path_not_string",
                ),
                "object_module": ("module", None, {}, "cli_input_module_not_string"),
                "null_nonce": (
                    "arguments",
                    "invocation_nonce",
                    None,
                    "cli_input_argument_invocation_nonce_not_string",
                ),
            }
            for label, (category, field, replacement, expected) in cli_cases.items():
                with self.subTest(label=label):
                    release = self.valid_cli_release(tmp)
                    if field is None:
                        release["cli_inputs"][category] = replacement
                    else:
                        release["cli_inputs"][category][field] = replacement
                    with patch(
                        "src.skills.sql_formatting_provider._successful_sql_cli_input_errors",
                        return_value=[],
                    ):
                        signed = attach_sql_formatting_cli_runtime_receipt(
                            release,
                            session_id="provider-api-session",
                            invocation_nonce="provider-api-nonce-0001",
                        )
                    errors = validate_sql_formatting_cli_runtime_receipt(
                        signed,
                        expected_session_id="provider-api-session",
                        expected_invocation_nonce="provider-api-nonce-0001",
                        expected_provider_selection_sha256=signed["cli_inputs"]["hashes"]["provider_selection_sha256"],
                    )
                    self.assertIn(expected, errors)
                    self.assertNotIn("runtime_producer_claim_mismatch", errors)

            valid = attach_sql_formatting_cli_runtime_receipt(
                self.valid_cli_release(tmp),
                session_id="provider-api-session",
                invocation_nonce="provider-api-nonce-0001",
            )
            for field, replacement in {"schema_version": True, "exit_code": False}.items():
                with self.subTest(runtime_field=field):
                    payload = {
                        key: value
                        for key, value in valid["runtime_receipt"].items()
                        if key
                        not in {
                            "producer_boundary",
                            "authority",
                            "external_authenticity",
                            "receipt_id",
                            "producer_claim",
                        }
                    }
                    payload[field] = replacement
                    malformed = dict(valid)
                    malformed["runtime_receipt"] = _sql_provider_runtime_boundary().issue_claim(
                        payload,
                        claim_kind=SQL_PROVIDER_RECEIPT_CLAIM_KIND,
                        claim_id_field="receipt_id",
                        claim_id_prefix="sql-provider",
                    )
                    errors = validate_sql_formatting_cli_runtime_receipt(
                        malformed,
                        expected_session_id="provider-api-session",
                        expected_invocation_nonce="provider-api-nonce-0001",
                        expected_provider_selection_sha256=malformed["cli_inputs"]["hashes"]["provider_selection_sha256"],
                    )
                    self.assertIn(
                        f"sql_provider_runtime_receipt_{field}_mismatch",
                        errors,
                    )
                    self.assertNotIn("runtime_producer_claim_mismatch", errors)

    @staticmethod
    def provider_selection(path, *, source="host-local-skill"):
        resolved_path = str(Path(path).expanduser().resolve())
        return attach_sql_provider_selection_runtime_receipt({
            "schema_version": 1,
            "host": "local",
            "project": str(Path.cwd().resolve()),
            "provider_id": "sql-formatting",
            "provider_path": resolved_path,
            "selected_active_provider_path": resolved_path,
            "provider_source": source,
            "compatibility": "compatible",
            "selection_status": "selected",
            "front_door_status": "ok",
            "plugin_route": {
                "route": "single",
                "controller": {
                    "provider_id": "sql-formatting",
                    "capability": "sql_formatting",
                    "metadata": {
                        "path": resolved_path,
                        "source": source,
                        "compatibility": "compatible",
                    },
                },
            },
            "execution_gate": {
                "can_execute": True,
                "status": "execution_allowed_after_selected_skill_setup",
                "reason": "SQL formatting provider selected after required skill setup.",
            },
        })

    def test_provider_selection_requires_local_runtime_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected_path = self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)
            signed = self.provider_selection(selected_path)
            unsigned = dict(signed)
            unsigned.pop("provider_selection_receipt")

            with self.assertRaises(SqlFormattingProviderPathError) as missing:
                guard_authoritative_sql_formatting_provider_path(
                    selected_path,
                    selected_active_provider_path=selected_path,
                    provider_selection=unsigned,
                )

            tampered = json.loads(json.dumps(signed))
            tampered["plugin_route"]["controller"]["metadata"]["path"] = str(
                selected_path.parent / "copied" / "SKILL.md"
            )
            with self.assertRaises(SqlFormattingProviderPathError) as changed:
                guard_authoritative_sql_formatting_provider_path(
                    selected_path,
                    selected_active_provider_path=selected_path,
                    provider_selection=tampered,
                )

        self.assertEqual(missing.exception.code, "provider_selection_provenance_invalid")
        self.assertEqual(changed.exception.code, "provider_selection_provenance_invalid")

    def test_provider_selection_external_host_authenticity_boundary_is_explicit(self):
        selection = self.provider_selection(r"C:\active\sql-formatting\SKILL.md")
        receipt = selection["provider_selection_receipt"]

        self.assertEqual(receipt["authority"], "local_runtime_integrity")
        self.assertEqual(receipt["external_authenticity"], "unverified")
        self.assertEqual(validate_sql_provider_selection_runtime_receipt(selection), [])
        self.assertIn(
            "provider_selection_external_host_authenticity_unverified",
            validate_sql_provider_selection_runtime_receipt(
                selection,
                require_external_host_authenticity=True,
            ),
        )
        self.assertEqual(
            validate_sql_provider_selection_runtime_receipt(
                selection,
                require_external_host_authenticity=True,
                external_host_authenticator=lambda _receipt: True,
            ),
            [],
        )

    def test_provider_selection_issuer_rejects_schema_and_blocked_gate_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)
            signed = self.provider_selection(path)
            base = dict(signed)
            base.pop("provider_selection_receipt", None)
            cases = {
                "schema_bool": (
                    lambda value: value.__setitem__("schema_version", True),
                    "provider_selection_schema_version_not_integer",
                ),
                "host_numeric": (
                    lambda value: value.__setitem__("host", 7),
                    "provider_selection_host_not_string",
                ),
                "project_list": (
                    lambda value: value.__setitem__("project", []),
                    "provider_selection_project_not_string",
                ),
                "provider_id_object": (
                    lambda value: value.__setitem__("provider_id", {}),
                    "provider_selection_provider_id_not_string",
                ),
                "provider_path_numeric": (
                    lambda value: value.__setitem__("provider_path", 11),
                    "provider_selection_provider_path_not_string",
                ),
                "selected_path_null": (
                    lambda value: value.__setitem__("selected_active_provider_path", None),
                    "provider_selection_selected_active_provider_path_not_string",
                ),
                "source_list": (
                    lambda value: value.__setitem__("provider_source", []),
                    "provider_selection_provider_source_not_string",
                ),
                "compatibility_bool": (
                    lambda value: value.__setitem__("compatibility", False),
                    "provider_selection_compatibility_not_string",
                ),
                "selection_blocked": (
                    lambda value: value.__setitem__("selection_status", "blocked"),
                    "provider_selection_status_not_allowed",
                ),
                "can_execute_false": (
                    lambda value: value["execution_gate"].__setitem__("can_execute", False),
                    "provider_selection_execution_blocked",
                ),
                "gate_status_numeric": (
                    lambda value: value["execution_gate"].__setitem__("status", 0),
                    "provider_selection_execution_gate_status_not_string",
                ),
                "gate_reason_null": (
                    lambda value: value["execution_gate"].__setitem__("reason", None),
                    "provider_selection_execution_gate_reason_not_string",
                ),
            }
            for label, (mutate, expected) in cases.items():
                with self.subTest(label=label):
                    selection = json.loads(json.dumps(base))
                    mutate(selection)
                    with self.assertRaises(SqlFormattingProviderPathError) as raised:
                        attach_sql_provider_selection_runtime_receipt(selection)
                    self.assertEqual(raised.exception.code, expected)

    def test_provider_selection_validator_rejects_valid_hmac_schema_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)
            base = self.provider_selection(path)
            base.pop("provider_selection_receipt", None)
            cases = {
                "schema_bool": (
                    lambda value: value.__setitem__("schema_version", True),
                    "provider_selection_schema_version_not_integer",
                ),
                "numeric_path": (
                    lambda value: value.__setitem__("provider_path", 3),
                    "provider_selection_provider_path_not_string",
                ),
                "blocked_gate": (
                    lambda value: value["execution_gate"].__setitem__("can_execute", False),
                    "provider_selection_execution_blocked",
                ),
                "object_reason": (
                    lambda value: value["execution_gate"].__setitem__("reason", {}),
                    "provider_selection_execution_gate_reason_not_string",
                ),
            }
            for label, (mutate, expected) in cases.items():
                with self.subTest(label=label):
                    selection = json.loads(json.dumps(base))
                    mutate(selection)
                    with patch(
                        "src.skills.sql_formatting_provider._sql_provider_selection_schema_errors",
                        return_value=[],
                    ):
                        signed = attach_sql_provider_selection_runtime_receipt(selection)
                    errors = validate_sql_provider_selection_runtime_receipt(signed)
                    self.assertIn(expected, errors)
                    self.assertNotIn("runtime_producer_claim_mismatch", errors)

    def test_provider_selection_runtime_identity_rejects_recomputed_wrong_hmac_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)
            valid = self.provider_selection(path)
            cases = {
                "schema_bool": ("schema_version", True, "provider_selection_runtime_receipt_schema_version_mismatch"),
                "receipt_id": (
                    "provider_selection_receipt_id",
                    "wrong-id",
                    "provider_selection_runtime_receipt_id_invalid",
                ),
                "authority": (
                    "authority",
                    "other",
                    "provider_selection_runtime_receipt_authority_mismatch",
                ),
                "external": (
                    "external_authenticity",
                    "verified",
                    "provider_selection_runtime_receipt_external_authenticity_mismatch",
                ),
            }
            for label, (field, replacement, expected) in cases.items():
                with self.subTest(label=label):
                    malformed = json.loads(json.dumps(valid))
                    malformed["provider_selection_receipt"][field] = replacement
                    boundary = _sql_provider_selection_runtime_boundary()
                    malformed["provider_selection_receipt"]["producer_claim"] = boundary._claim_digest(
                        malformed["provider_selection_receipt"]
                    )
                    errors = validate_sql_provider_selection_runtime_receipt(malformed)
                    self.assertIn(expected, errors)
                    self.assertNotIn("runtime_producer_claim_mismatch", errors)

            boundary_cases = {
                "kind": ("other", "provider_selection_runtime_receipt_producer_boundary_kind_mismatch"),
                "name": (7, "provider_selection_runtime_receipt_producer_boundary_producer_name_mismatch"),
                "claim": ([], "provider_selection_runtime_receipt_producer_boundary_claim_kind_mismatch"),
                "boundary": ({}, "provider_selection_runtime_receipt_producer_boundary_boundary_id_mismatch"),
            }
            key_map = {
                "kind": "kind",
                "name": "producer_name",
                "claim": "claim_kind",
                "boundary": "boundary_id",
            }
            for label, (replacement, expected) in boundary_cases.items():
                with self.subTest(boundary_field=label):
                    malformed = json.loads(json.dumps(valid))
                    malformed["provider_selection_receipt"]["producer_boundary"][
                        key_map[label]
                    ] = replacement
                    boundary = _sql_provider_selection_runtime_boundary()
                    malformed["provider_selection_receipt"]["producer_claim"] = boundary._claim_digest(
                        malformed["provider_selection_receipt"]
                    )
                    errors = validate_sql_provider_selection_runtime_receipt(malformed)
                    self.assertIn(expected, errors)

    def test_cli_runtime_identity_rejects_recomputed_wrong_hmac_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            valid = attach_sql_formatting_cli_runtime_receipt(
                self.valid_cli_release(tmp),
                session_id="provider-api-session",
                invocation_nonce="provider-api-nonce-0001",
            )
            cases = {
                "schema_bool": ("schema_version", True, "sql_provider_runtime_receipt_schema_version_mismatch"),
                "receipt_id": ("receipt_id", "wrong-id", "sql_provider_runtime_receipt_id_invalid"),
                "authority": ("authority", "other", "sql_provider_runtime_receipt_authority_mismatch"),
                "external": (
                    "external_authenticity",
                    "verified",
                    "sql_provider_runtime_receipt_external_authenticity_mismatch",
                ),
            }
            for label, (field, replacement, expected) in cases.items():
                with self.subTest(label=label):
                    malformed = json.loads(json.dumps(valid))
                    malformed["runtime_receipt"][field] = replacement
                    boundary = _sql_provider_runtime_boundary()
                    malformed["runtime_receipt"]["producer_claim"] = boundary._claim_digest(
                        malformed["runtime_receipt"]
                    )
                    errors = validate_sql_formatting_cli_runtime_receipt(
                        malformed,
                        expected_session_id="provider-api-session",
                        expected_invocation_nonce="provider-api-nonce-0001",
                        expected_provider_selection_sha256=malformed["cli_inputs"]["hashes"]["provider_selection_sha256"],
                    )
                    self.assertIn(expected, errors)
                    self.assertNotIn("runtime_producer_claim_mismatch", errors)

            boundary_cases = {
                "kind": (
                    "kind",
                    "other",
                    "sql_provider_runtime_receipt_producer_boundary_kind_mismatch",
                ),
                "name": (
                    "producer_name",
                    False,
                    "sql_provider_runtime_receipt_producer_boundary_producer_name_mismatch",
                ),
                "claim": (
                    "claim_kind",
                    [],
                    "sql_provider_runtime_receipt_producer_boundary_claim_kind_mismatch",
                ),
                "boundary": (
                    "boundary_id",
                    {},
                    "sql_provider_runtime_receipt_producer_boundary_boundary_id_mismatch",
                ),
            }
            for label, (field, replacement, expected) in boundary_cases.items():
                with self.subTest(cli_boundary_field=label):
                    malformed = json.loads(json.dumps(valid))
                    malformed["runtime_receipt"]["producer_boundary"][field] = replacement
                    boundary = _sql_provider_runtime_boundary()
                    malformed["runtime_receipt"]["producer_claim"] = boundary._claim_digest(
                        malformed["runtime_receipt"]
                    )
                    errors = validate_sql_formatting_cli_runtime_receipt(
                        malformed,
                        expected_session_id="provider-api-session",
                        expected_invocation_nonce="provider-api-nonce-0001",
                        expected_provider_selection_sha256=malformed["cli_inputs"]["hashes"]["provider_selection_sha256"],
                    )
                    self.assertIn(expected, errors)

    def test_provider_cli_accepts_front_door_receipt_and_rejects_self_authored_json(self):
        repo_root = Path(__file__).resolve().parents[1]
        provider_path = repo_root / "skills" / "sql_formatting" / "SKILL.md"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime_root = root / "uaf-runtime"
            env = os.environ.copy()
            env["UAF_RUNTIME_ROOT"] = str(runtime_root)
            original_path = root / "original.sql"
            candidate_path = root / "candidate.sql"
            response_path = root / "response.md"
            selection_path = root / "provider-selection.json"
            history_path = root / "verifier-history.json"
            original_path.write_text("SELECT ORDER_ID FROM ORDER_HEADER;", encoding="utf-8")
            candidate = "SELECT ORDER_ID\nFROM ORDER_HEADER;"
            candidate_path.write_text(candidate, encoding="utf-8")
            response_path.write_text(f"```sql\n{candidate}\n```", encoding="utf-8")
            history_path.write_text(
                json.dumps(
                    [
                        verify_sql_formatting_style(
                            original_path.read_text(encoding="utf-8"),
                            candidate,
                        ).to_dict()
                    ]
                ),
                encoding="utf-8",
            )
            front_door = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.orchestration.kh_front_door",
                    "--prompt",
                    "Format this SQL: SELECT ORDER_ID FROM ORDER_HEADER",
                    "--project",
                    str(repo_root),
                    "--host",
                    "local",
                    "--summary",
                ],
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                env=env,
            )
            self.assertEqual(front_door.returncode, 0, front_door.stderr)
            signed_selection = json.loads(front_door.stdout)
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(runtime_root)}):
                selection_validation = validate_sql_provider_selection_runtime_receipt(
                    signed_selection
                )
            selection_path.write_text(json.dumps(signed_selection), encoding="utf-8")
            command = [
                sys.executable,
                "-m",
                "src.skills.sql_formatting_provider",
                "--original-file",
                str(original_path),
                "--candidate-file",
                str(candidate_path),
                "--response-file",
                str(response_path),
                "--provider-path",
                str(provider_path),
                "--selected-active-provider-path",
                str(provider_path),
                "--provider-selection-file",
                str(selection_path),
                "--verifier-history-file",
                str(history_path),
                "--session-id",
                "provider-cli-test",
                "--invocation-nonce",
                "provider-cli-test-0001",
            ]
            missing_history_command = list(command)
            history_index = missing_history_command.index("--verifier-history-file")
            del missing_history_command[history_index : history_index + 2]
            missing_history = subprocess.run(
                missing_history_command,
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                env=env,
            )
            self.assertEqual(missing_history.returncode, 1)
            self.assertEqual(
                json.loads(missing_history.stdout)["error_code"],
                "sql_formatting_repair_history_required",
            )
            accepted = subprocess.run(
                command,
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                env=env,
            )
            accepted_receipt = json.loads(accepted.stdout)
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(runtime_root)}):
                accepted_validation = validate_sql_formatting_cli_runtime_receipt(
                    accepted_receipt,
                    expected_session_id="provider-cli-test",
                    expected_invocation_nonce="provider-cli-test-0001",
                    expected_provider_selection_sha256=sql_provider_selection_sha256(
                        signed_selection
                    ),
                )
            raw_hashes = accepted_receipt["cli_inputs"]["hashes"]
            expected_raw_hashes = {
                "original_file_sha256": hashlib.sha256(
                    original_path.read_bytes()
                ).hexdigest(),
                "candidate_file_sha256": hashlib.sha256(
                    candidate_path.read_bytes()
                ).hexdigest(),
                "response_file_sha256": hashlib.sha256(
                    response_path.read_bytes()
                ).hexdigest(),
                "provider_selection_file_sha256": hashlib.sha256(
                    selection_path.read_bytes()
                ).hexdigest(),
            }
            unsigned = dict(signed_selection)
            unsigned.pop("provider_selection_receipt", None)
            selection_path.write_text(json.dumps(unsigned), encoding="utf-8")
            rejected = subprocess.run(
                command[:-1] + ["provider-cli-test-0002"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                env=env,
            )
            selection_runtime_exists = (
                runtime_root / "runtime-receipts" / "sql-provider-selection"
            ).is_dir()
            binding_runtime_exists = (
                runtime_root / "runtime-receipts" / "sql-formatting-provider"
            ).is_dir()

        self.assertEqual(accepted.returncode, 0, accepted.stderr or accepted.stdout)
        self.assertEqual(selection_validation, [])
        self.assertEqual(accepted_validation, [])
        self.assertEqual(rejected.returncode, 1)
        self.assertEqual(
            {key: raw_hashes.get(key) for key in expected_raw_hashes},
            expected_raw_hashes,
        )
        self.assertEqual(
            json.loads(rejected.stdout)["error_code"],
            "provider_selection_provenance_invalid",
        )
        self.assertTrue(selection_runtime_exists)
        self.assertTrue(binding_runtime_exists)

    def test_provider_inspection_blocks_missing_and_corrupt_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills_root = Path(tmp) / "skills"
            skills_root.mkdir()

            missing = inspect_packaged_sql_formatting_provider(skills_root)
            self.assertEqual(missing.status, "missing")
            self.assertFalse(missing.compatible)

            provider_root = skills_root / "sql_formatting"
            provider_root.mkdir()
            (provider_root / "SKILL.md").write_text("not frontmatter", encoding="utf-8")

            corrupt = inspect_packaged_sql_formatting_provider(skills_root)
            self.assertEqual(corrupt.status, "corrupt")
            self.assertFalse(corrupt.compatible)

    def test_front_door_prefers_compatible_host_local_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)

            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                payload = build_kh_front_door(
                    "Format this T-SQL query and preserve logic.",
                    project=Path.cwd(),
                    host="codex",
                ).to_dict()

        controller = payload["plugin_route"]["controller"]
        self.assertEqual(controller["provider_id"], "sql-formatting")
        self.assertEqual(controller["metadata"]["source"], "host-local-skill")
        self.assertEqual(controller["metadata"]["availability"], "available")
        self.assertEqual(controller["metadata"]["compatibility"], "compatible")
        self.assertEqual(
            payload["immediate_next_skills"],
            ["sql-formatting", "sql-formatting-style-harness"],
        )

    def test_front_door_uses_packaged_provider_then_verifier_when_codex_home_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                payload = build_kh_front_door(
                    "Format this T-SQL query and preserve logic.",
                    project=Path.cwd(),
                    host="codex",
                ).to_dict()

        controller = payload["plugin_route"]["controller"]
        self.assertEqual(controller["provider_id"], "sql-formatting")
        self.assertEqual(controller["metadata"]["source"], "packaged-kh-skill")
        self.assertEqual(controller["metadata"]["availability"], "available")
        self.assertEqual(controller["metadata"]["compatibility"], "compatible")
        self.assertEqual(
            payload["immediate_next_skills"],
            ["sql-formatting", "sql-formatting-style-harness"],
        )
        self.assertIn("sql-formatting", payload["recommended_skills"])
        self.assertIn("sql-formatting-style-harness", payload["recommended_skills"])

        metadata = controller["metadata"]
        self.assertTrue(metadata["final_response_binding_required"])
        self.assertEqual(
            metadata["final_response_binding_helper"],
            "src.skills.sql_formatting_provider.guard_and_bind_verified_sql_final_response",
        )
        self.assertEqual(
            metadata["authoritative_provider_path_guard"],
            "src.skills.sql_formatting_provider.guard_authoritative_sql_formatting_provider_path",
        )
        sql_actions = "\n".join(payload["required_next_actions"])
        self.assertIn("exact recorded path", sql_actions)
        self.assertIn("Every SQL correction invalidates", sql_actions)
        self.assertIn("formatted_sha256", sql_actions)

    def test_front_door_falls_back_from_divergent_host_local_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_host_skill(
                tmp,
                self.COMPATIBLE_HOST_SKILL.replace(
                    "Format SQL/T-SQL while preserving query behavior and semantics.",
                    "Format SQL/T-SQL and may change query behavior.",
                ),
            )

            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                payload = build_kh_front_door(
                    "Format this T-SQL query and preserve logic.",
                    project=Path.cwd(),
                    host="codex",
                ).to_dict()

        controller = payload["plugin_route"]["controller"]
        self.assertEqual(controller["provider_id"], "sql-formatting")
        self.assertEqual(controller["metadata"]["source"], "packaged-kh-skill")
        self.assertEqual(
            payload["immediate_next_skills"],
            ["sql-formatting", "sql-formatting-style-harness"],
        )
        evidence = {
            item["source"]: item
            for item in payload["plugin_route"]["provider_evidence"]
            if item["provider_id"] == "sql-formatting"
        }
        self.assertTrue(evidence["host-local-skill"]["available"])
        self.assertFalse(evidence["host-local-skill"]["compatible"])
        self.assertEqual(evidence["host-local-skill"]["compatibility"], "divergent")
        self.assertFalse(evidence["host-local-skill"]["selected"])
        self.assertTrue(evidence["packaged-kh-skill"]["available"])
        self.assertTrue(evidence["packaged-kh-skill"]["compatible"])
        self.assertTrue(evidence["packaged-kh-skill"]["selected"])
        self.assertEqual(
            controller["metadata"]["verification_provider"],
            "sql-formatting-style-harness",
        )
        self.assertEqual(
            controller["metadata"]["alias_plan_requirement"],
            "complete_for_all_multi_source_scopes_and_alias_changed_single_source_scopes",
        )

    def test_host_provider_rejects_current_host_local_concrete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = self.write_host_skill(tmp, self.CURRENT_HOST_LOCAL_SHAPE)

            inspection = inspect_host_sql_formatting_provider(skill_path)

        self.assertFalse(inspection.compatible)
        self.assertEqual(inspection.compatibility, "divergent")
        self.assertIn("concrete_schema_object_mandate", inspection.issues)
        self.assertIn("missing_packaged_verifier_requirement", inspection.issues)

    def test_host_provider_rejects_concrete_mandates_without_known_object_names(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "Convert a scalar lookup to a JOIN only when its implementation and relational equivalence are verified.",
            (
                "`CORP.F_ZZ901_NAME(CODE)` is the standard lookup. "
                "Always replace it with `LEFT OUTER JOIN ZZ901T` and return `ZZ901T.NAME`."
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("concrete_schema_object_mandate", inspection.issues)

    def test_host_provider_rejects_concrete_table_mandate_without_function(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "Convert a scalar lookup to a JOIN only when its implementation and relational equivalence are verified.",
            "Always use `ACME_CODE_MAP` to resolve code names.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("concrete_schema_object_mandate", inspection.issues)

    def test_host_provider_rejects_unlabeled_fenced_concrete_template(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "## Examples\n\nFor example, `DBO.F_SAMPLE_NAME(...)` and `SAMPLE_LOOKUP_TABLE` may illustrate input shape only.\nThey are not general conversion mandates.\n",
            "## Output Template\n\n```sql\nSELECT A.NAME\nFROM ZZ902T A\n```\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("concrete_schema_object_mandate", inspection.issues)

    def test_host_provider_rejects_unbounded_scalar_to_join_conversion(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "Convert a scalar lookup to a JOIN only when its implementation and relational equivalence are verified.",
            "Replace scalar UDF calls with LEFT JOINs for performance.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("unbounded_scalar_to_join_conversion", inspection.issues)

    def test_host_provider_rejects_missing_packaged_verifier_requirement(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "Run the packaged `sql-formatting-style-harness` deterministic verifier and accept output only when it passes.\n",
            "",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("missing_packaged_verifier_requirement", inspection.issues)

    def test_host_provider_rejects_missing_behavior_preservation_boundary(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "description: Format SQL/T-SQL while preserving query behavior and semantics.",
            "description: Format SQL/T-SQL for readability.",
        ).replace(
            "Do not change query behavior. Preserve table names, predicates, expressions, and results.",
            "Keep table names, predicates, and expressions readable.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("missing_behavior_preservation_boundary", inspection.issues)

    def test_host_provider_rejects_optional_or_negated_preservation_policies(self):
        policies = {
            "optional": "The formatter may preserve query behavior when convenient.",
            "negated": "The formatter must not preserve query behavior.",
        }
        for label, policy in policies.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                content = self.COMPATIBLE_HOST_SKILL.replace(
                    "description: Format SQL/T-SQL while preserving query behavior and semantics.",
                    "description: Format SQL/T-SQL for readability.",
                ).replace(
                    "Do not change query behavior. Preserve table names, predicates, expressions, and results.",
                    policy,
                )
                inspection = inspect_host_sql_formatting_provider(
                    self.write_host_skill(tmp, content)
                )

            self.assertFalse(inspection.compatible)
            self.assertIn("missing_behavior_preservation_boundary", inspection.issues)

    def test_host_provider_rejects_optional_or_negated_verifier_policies(self):
        policies = {
            "optional": (
                "The packaged `sql-formatting-style-harness` deterministic verifier "
                "may run when convenient."
            ),
            "negated": (
                "The packaged `sql-formatting-style-harness` deterministic verifier "
                "must not run before output is accepted."
            ),
            "prohibited": (
                "Do not invoke the packaged `sql-formatting-style-harness` "
                "deterministic verifier."
            ),
        }
        for label, policy in policies.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                content = self.COMPATIBLE_HOST_SKILL.replace(
                    "Run the packaged `sql-formatting-style-harness` deterministic verifier and accept output only when it passes.",
                    policy,
                )
                inspection = inspect_host_sql_formatting_provider(
                    self.write_host_skill(tmp, content)
                )

            self.assertFalse(inspection.compatible)
            self.assertIn("missing_packaged_verifier_requirement", inspection.issues)

    def test_host_provider_rejects_required_and_weak_preservation_clauses(self):
        content = (
            self.COMPATIBLE_HOST_SKILL
            + "\n## Weak Preservation Override\n\n"
            + "The formatter should preserve query behavior where practical.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertEqual(inspection.compatibility, "divergent")
        self.assertIn("contradictory_behavior_preservation_policy", inspection.issues)

    def test_host_provider_rejects_required_and_weak_verifier_clauses(self):
        content = (
            self.COMPATIBLE_HOST_SKILL
            + "\n## Weak Verifier Override\n\n"
            + "The packaged `sql-formatting-style-harness` deterministic verifier "
            + "should run where practical.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertEqual(inspection.compatibility, "divergent")
        self.assertIn("contradictory_packaged_verifier_policy", inspection.issues)

    def test_host_provider_rejects_overt_behavior_change_permission(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "Do not change query behavior.",
            "Query behavior changes are allowed when the output is faster.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("behavior_change_allowed", inspection.issues)

    def test_host_provider_allows_labeled_examples_and_generic_verified_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)
            )

        self.assertTrue(inspection.compatible)
        self.assertEqual(inspection.compatibility, "compatible")
        self.assertEqual(inspection.issues, [])

    def test_front_door_blocks_when_no_compatible_provider_exists(self):
        unavailable_provider = {
            "provider_id": "sql-formatting",
            "display_name": "KH Packaged SQL Formatting",
            "aliases": ["sql formatting", "sql-formatting"],
            "capabilities": ["sql_formatting"],
            "status": "corrupt",
            "metadata": {
                "source": "packaged-kh-skill",
                "compatibility": "corrupt",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"CODEX_HOME": tmp}), patch(
                "src.orchestration.kh_front_door.packaged_sql_formatting_provider",
                return_value=unavailable_provider,
            ):
                payload = build_kh_front_door(
                    "Format this T-SQL query and preserve logic.",
                    project=Path.cwd(),
                    host="codex",
                ).to_dict()

        selected_roles = [payload["plugin_route"]["controller"], *payload["plugin_route"]["assistants"]]
        self.assertFalse(any(role.get("capability") == "sql_formatting" for role in selected_roles))
        self.assertEqual(payload["plugin_route"]["route"], "blocked")
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_sql_formatting_provider")
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertIn("sql_formatting", payload["plugin_route"]["unavailable_capabilities"])
        self.assertFalse(
            any("Apply selected provider `sql-formatting`" in action for action in payload["required_next_actions"])
        )

    def test_final_response_binding_accepts_exact_verified_candidate(self):
        candidate = (
            "CREATE OR ALTER PROC DBO.UP_SAMPLE\n"
            "AS\n"
            "BEGIN\n"
            "    -- Preserve this Comment exactly.\n"
            "    SELECT WORKTYPE\n"
            "    FROM DBO.SAMPLE;\n"
            "END"
        )
        formatted_sha256 = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        expected_verification = verify_sql_formatting_style(candidate, candidate)
        self.assertTrue(expected_verification.success, expected_verification.to_dict())
        draft = f"```sql\n{candidate}\n```\n\nVerification passed."

        binding = bind_verified_sql_final_response(
            candidate,
            candidate,
            draft,
        )

        self.assertEqual(binding.status, "bound")
        self.assertEqual(binding.formatted_sql, candidate)
        self.assertEqual(binding.formatted_sha256, formatted_sha256)
        self.assertRegex(binding.verification_id, r"^[0-9a-f]{64}$")
        self.assertNotEqual(binding.verification_id, "")
        self.assertEqual(binding.final_response, draft)
        self.assertEqual(binding.sql_fence_count, 1)

    def test_final_response_binding_preserves_candidate_trailing_newline(self):
        candidate = "SELECT 1;\r\n"
        draft = f"```sql\r\n{candidate}\r\n```"

        binding = bind_verified_sql_final_response(
            candidate,
            candidate,
            draft,
        )

        self.assertEqual(binding.formatted_sql, candidate)

    def test_final_response_binding_invokes_verifier_with_explicit_kwargs(self):
        original = "select 1;"
        candidate = "SELECT 1;"
        formatted_sha256 = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        verifier_result = HarnessResult(
            success=True,
            exit_code=0,
            metadata={
                "original_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
                "formatted_sha256": formatted_sha256,
                "release_readiness": {"status": "ready"},
                "verification_id": "fresh-verification-id",
            },
        )
        style_contract_path = Path("style-contract.md")
        alias_role_plan = [{"scope_id": "scope_1"}]
        scalar_function_refactor = {"status": "not-requested"}
        authenticator = lambda payload, signature: True

        with patch(
            "src.skills.sql_formatting_provider.verify_sql_formatting_style",
            return_value=verifier_result,
        ) as verifier:
            binding = bind_verified_sql_final_response(
                original,
                candidate,
                f"```sql\n{candidate}\n```",
                style_contract_path=style_contract_path,
                cte_temp_table_reason="approved-reason",
                alias_role_plan=alias_role_plan,
                scalar_function_refactor=scalar_function_refactor,
                runtime_receipt_authenticator=authenticator,
                operation="formatting",
            )

        verifier.assert_called_once_with(
            original,
            candidate,
            style_contract_path=style_contract_path,
            cte_temp_table_reason="approved-reason",
            alias_role_plan=alias_role_plan,
            scalar_function_refactor=scalar_function_refactor,
            runtime_receipt_authenticator=authenticator,
            operation="formatting",
        )
        self.assertEqual(binding.verification_id, "fresh-verification-id")
        self.assertEqual(
            binding.original_sha256,
            hashlib.sha256(original.encode("utf-8")).hexdigest(),
        )

    def test_final_response_binding_rejects_generation_operation_bypass(self):
        original = "SELECT 1;"
        changed = "SELECT 2;"

        with self.assertRaises(SqlFinalResponseBindingError) as raised:
            bind_verified_sql_final_response(
                original,
                changed,
                f"```sql\n{changed}\n```",
                operation="generation",
            )

        self.assertEqual(raised.exception.code, "unsupported_final_binding_operation")

    def test_final_response_binding_has_no_caller_receipt_parameter(self):
        parameters = inspect.signature(bind_verified_sql_final_response).parameters
        self.assertEqual(
            list(parameters)[:3],
            ["original_sql", "verified_candidate", "draft_final_response"],
        )
        self.assertNotIn("verifier_result", parameters)

        candidate = "SELECT 1;"
        receipt_shapes = (
            {"success": True, "exit_code": 0, "metadata": {}},
            HarnessResult(success=True),
        )
        for receipt in receipt_shapes:
            with self.subTest(receipt_type=type(receipt).__name__), self.assertRaises(
                SqlFinalResponseBindingError
            ) as raised:
                bind_verified_sql_final_response(
                    candidate,
                    receipt,
                    f"```sql\n{candidate}\n```",
                )

            self.assertEqual(raised.exception.code, "invalid_verified_candidate")

    def test_final_response_binding_rejects_non_ready_fresh_verification(self):
        candidate = "SELECT 2;"

        with self.assertRaises(SqlFinalResponseBindingError) as raised:
            bind_verified_sql_final_response(
                "SELECT 1;",
                candidate,
                f"```sql\n{candidate}\n```",
            )

        self.assertEqual(raised.exception.code, "verifier_not_ready")

    def test_final_response_binding_rejects_stale_fresh_verification_metadata(self):
        candidate = "SELECT 1;"
        stale_result = HarnessResult(
            success=True,
            exit_code=0,
            metadata={
                "original_sha256": hashlib.sha256(candidate.encode("utf-8")).hexdigest(),
                "formatted_sha256": hashlib.sha256(b"SELECT 2;").hexdigest(),
                "release_readiness": {"status": "ready"},
                "verification_id": "stale-verification-id",
            },
        )

        with patch(
            "src.skills.sql_formatting_provider.verify_sql_formatting_style",
            return_value=stale_result,
        ), self.assertRaises(SqlFinalResponseBindingError) as raised:
            bind_verified_sql_final_response(
                candidate,
                candidate,
                f"```sql\n{candidate}\n```",
            )

        self.assertEqual(raised.exception.code, "stale_verification_result")

    def test_final_response_binding_rejects_missing_or_multiple_fences(self):
        candidate = "SELECT 1;"
        drafts = {
            "missing": candidate,
            "multiple_sql": (
                f"```sql\n{candidate}\n```\n\n```sql\n{candidate}\n```"
            ),
            "extra_non_sql": (
                f"```sql\n{candidate}\n```\n\n```text\nreceipt\n```"
            ),
        }

        for label, draft in drafts.items():
            with self.subTest(label=label), self.assertRaises(
                SqlFinalResponseBindingError
            ) as raised:
                bind_verified_sql_final_response(
                    candidate,
                    candidate,
                    draft,
                )

            self.assertIn(
                raised.exception.code,
                {"missing_sql_fence", "multiple_fenced_blocks"},
            )

    def test_final_response_binding_rejects_explanation_first(self):
        candidate = "SELECT 1;"

        with self.assertRaises(SqlFinalResponseBindingError) as raised:
            bind_verified_sql_final_response(
                candidate,
                candidate,
                f"Here is the formatted SQL.\n\n```sql\n{candidate}\n```",
            )

        self.assertEqual(raised.exception.code, "sql_fence_not_first")

    def test_final_response_binding_rejects_partial_or_retyped_sql(self):
        candidate = (
            "CREATE PROC DBO.UP_SAMPLE\n"
            "AS\n"
            "BEGIN\n"
            "    -- Keep Case\n"
            "    SELECT WORKTYPE FROM DBO.SAMPLE;\n"
            "END"
        )
        mutations = {
            "partial": "SELECT WORKTYPE FROM DBO.SAMPLE;",
            "comment": candidate.replace("-- Keep Case", "-- keep case"),
            "keyword_case": candidate.replace("SELECT", "select"),
            "whitespace": candidate.replace("    SELECT", "  SELECT"),
        }

        for label, sql in mutations.items():
            with self.subTest(label=label), self.assertRaises(
                SqlFinalResponseBindingError
            ) as raised:
                bind_verified_sql_final_response(
                    candidate,
                    candidate,
                    f"```sql\n{sql}\n```",
                )

            self.assertEqual(raised.exception.code, "final_sql_candidate_mismatch")

    def test_final_response_binding_fails_closed_for_a_different_complete_sql_fence(self):
        candidate = (
            "SELECT A.EVENT_ID\n"
            "FROM USAGE_LOG A\n"
            "WHERE A.ACTIVE = 'Y';"
        )
        unverified_alternative = (
            "SELECT L.EVENT_ID\n"
            "FROM USAGE_LOG L\n"
            "WHERE L.ACTIVE = 'Y';"
        )

        with self.assertRaises(SqlFinalResponseBindingError) as raised:
            bind_verified_sql_final_response(
                candidate,
                candidate,
                f"```sql\n{unverified_alternative}\n```",
            )

        self.assertEqual(raised.exception.code, "final_sql_candidate_mismatch")

    def test_final_response_binding_accepts_up_to_three_leading_fence_spaces(self):
        candidate = "SELECT 1;"

        for space_count in range(4):
            indent = " " * space_count
            with self.subTest(space_count=space_count):
                binding = bind_verified_sql_final_response(
                    candidate,
                    candidate,
                    f"{indent}```sql\n{candidate}\n{indent}```",
                )

            self.assertEqual(binding.formatted_sql, candidate)

    def test_final_response_binding_rejects_tab_or_four_space_pseudo_fences(self):
        candidate = "SELECT 1;"

        for indent in ("\t", "    "):
            with self.subTest(indent=repr(indent)), self.assertRaises(
                SqlFinalResponseBindingError
            ) as raised:
                bind_verified_sql_final_response(
                    candidate,
                    candidate,
                    f"{indent}```sql\n{candidate}\n{indent}```",
                )

            self.assertEqual(raised.exception.code, "missing_sql_fence")

    def test_provider_path_guard_accepts_only_selected_or_current_packaged_path(self):
        packaged_path = Path(
            packaged_sql_formatting_provider()["metadata"]["path"]
        )
        with tempfile.TemporaryDirectory() as tmp:
            selected_path = self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)

            with patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                selected = guard_authoritative_sql_formatting_provider_path(
                    selected_path,
                    selected_active_provider_path=selected_path,
                    provider_selection=self.provider_selection(selected_path),
                )
                with self.assertRaises(SqlFormattingProviderPathError) as raised:
                    guard_authoritative_sql_formatting_provider_path(
                        packaged_path,
                        selected_active_provider_path=selected_path,
                        provider_selection=self.provider_selection(selected_path),
                    )
            fallback = guard_authoritative_sql_formatting_provider_path(
                packaged_path,
                selected_active_provider_path=packaged_path,
                provider_selection=self.provider_selection(
                    packaged_path,
                    source="packaged-kh-skill",
                ),
            )

        self.assertEqual(selected.status, "accepted")
        self.assertEqual(selected.authority, "selected-active-provider")
        self.assertEqual(raised.exception.code, "provider_selection_path_mismatch")
        self.assertEqual(fallback.status, "accepted")
        self.assertEqual(fallback.authority, "current-packaged-fallback")

    def test_provider_path_guard_rejects_disabled_backup_staging_and_stale_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active_path = self.write_host_skill(root / "active", self.COMPATIBLE_HOST_SKILL)
            rejected_paths = {
                "disabled_provider_path": root / "disabled-skills" / "sql-formatting" / "SKILL.md",
                "backup_provider_path": root / "backups" / "sql-formatting" / "SKILL.md",
                "staging_provider_path": root / "staging" / "sql-formatting" / "SKILL.md",
                "older_cache_provider_path": (
                    root
                    / "plugins"
                    / "cache"
                    / "kh-uaf"
                    / "2.9.100"
                    / "skills"
                    / "sql_formatting"
                    / "SKILL.md"
                ),
            }
            for path in rejected_paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(self.COMPATIBLE_HOST_SKILL, encoding="utf-8")

            for expected_code, path in rejected_paths.items():
                with self.subTest(path=path), self.assertRaises(
                    SqlFormattingProviderPathError
                ) as raised:
                    guard_authoritative_sql_formatting_provider_path(
                        path,
                        selected_active_provider_path=active_path,
                        provider_selection=self.provider_selection(active_path),
                    )

                self.assertEqual(raised.exception.code, expected_code)

    def test_provider_path_guard_rejects_self_declared_selected_provider_from_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected_path = self.write_host_skill(
                Path(tmp) / "plugins" / "cache" / "host" / "2.0.0",
                self.COMPATIBLE_HOST_SKILL,
            )

            with self.assertRaises(SqlFormattingProviderPathError) as raised:
                guard_authoritative_sql_formatting_provider_path(
                    selected_path,
                    selected_active_provider_path=selected_path,
                    provider_selection=self.provider_selection(selected_path),
                )

        self.assertEqual(raised.exception.code, "older_cache_provider_path")

    def test_provider_path_guard_rejects_compatible_clone_without_front_door_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone_path = self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)

            with self.assertRaises(SqlFormattingProviderPathError) as raised:
                guard_authoritative_sql_formatting_provider_path(
                    clone_path,
                    selected_active_provider_path=clone_path,
                    provider_selection={},
                )

        self.assertEqual(raised.exception.code, "provider_selection_missing")

    def test_provider_path_guard_rejects_selected_arbitrary_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            readme_path = Path(tmp) / "README.md"
            readme_path.write_text("# SQL formatting notes\n", encoding="utf-8")

            with self.assertRaises(SqlFormattingProviderPathError) as raised:
                guard_authoritative_sql_formatting_provider_path(
                    readme_path,
                    selected_active_provider_path=readme_path,
                    provider_selection=self.provider_selection(readme_path),
                )

        self.assertEqual(raised.exception.code, "selected_provider_not_compatible")

    def test_provider_path_guard_rejects_selected_incompatible_skill(self):
        incompatible_skill = """---
name: sql-formatting
description: Format SQL.
---

# SQL Formatting

Rewrite queries freely and return the result without verification.
"""
        with tempfile.TemporaryDirectory() as tmp:
            selected_path = self.write_host_skill(tmp, incompatible_skill)

            with patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                with self.assertRaises(SqlFormattingProviderPathError) as raised:
                    guard_authoritative_sql_formatting_provider_path(
                        selected_path,
                        selected_active_provider_path=selected_path,
                        provider_selection=self.provider_selection(selected_path),
                    )

        self.assertEqual(raised.exception.code, "selected_provider_not_compatible")

    def test_provider_path_guard_canonicalizes_realpath_and_windows_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected_path = self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)
            relative_equivalent = (
                selected_path.parent / ".." / "sql-formatting" / "SKILL.md"
            )

            with patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                realpath_result = guard_authoritative_sql_formatting_provider_path(
                    relative_equivalent,
                    selected_active_provider_path=selected_path,
                    provider_selection=self.provider_selection(selected_path),
                )
                with patch(
                    "src.skills.sql_formatting_provider.os.path.normcase",
                    side_effect=lambda value: value.casefold(),
                ):
                    normcase_result = guard_authoritative_sql_formatting_provider_path(
                        selected_path,
                        selected_active_provider_path=str(selected_path).swapcase(),
                        provider_selection=self.provider_selection(selected_path),
                    )

        self.assertEqual(realpath_result.authority, "selected-active-provider")
        self.assertEqual(normcase_result.authority, "selected-active-provider")

    def test_provider_path_key_normalizes_windows_device_prefixes(self):
        with patch(
            "src.skills.sql_formatting_provider.os.path.abspath",
            side_effect=lambda value: value,
        ), patch(
            "src.skills.sql_formatting_provider.os.path.realpath",
            side_effect=lambda value: value,
        ), patch(
            "src.skills.sql_formatting_provider.os.path.normcase",
            side_effect=lambda value: value.casefold(),
        ):
            drive_key = _provider_path_key(Path(r"\\?\C:\Temp\Skill.md"))
            unc_key = _provider_path_key(
                Path(r"\\?\UNC\Server\Share\Skill.md")
            )

        self.assertEqual(drive_key, r"c:\temp\skill.md")
        self.assertEqual(unc_key, r"\\server\share\skill.md")

    @unittest.skipUnless(os.name == "nt", "Windows device path behavior")
    def test_provider_path_guard_accepts_device_prefixed_selected_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            selected_path = self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)
            device_path = Path("\\\\?\\" + str(selected_path))

            with patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                result = guard_authoritative_sql_formatting_provider_path(
                    device_path,
                    selected_active_provider_path=selected_path,
                    provider_selection=self.provider_selection(selected_path),
                )

        self.assertEqual(result.authority, "selected-active-provider")

    def test_provider_path_guard_rejects_arbitrary_discovered_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active_path = self.write_host_skill(root / "active", self.COMPATIBLE_HOST_SKILL)
            discovered_copy = self.write_host_skill(
                root / "discovered-copy",
                self.COMPATIBLE_HOST_SKILL,
            )

            with self.assertRaises(SqlFormattingProviderPathError) as raised:
                guard_authoritative_sql_formatting_provider_path(
                    discovered_copy,
                    selected_active_provider_path=active_path,
                    provider_selection=self.provider_selection(active_path),
                )

        self.assertEqual(raised.exception.code, "provider_selection_path_mismatch")

    def test_provider_path_guard_ignores_codex_home_for_packaged_authority(self):
        packaged_path = Path(
            packaged_sql_formatting_provider()["metadata"]["path"]
        )
        with tempfile.TemporaryDirectory() as tmp:
            self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)
            with patch.dict(os.environ, {"CODEX_HOME": tmp}, clear=False):
                result = guard_authoritative_sql_formatting_provider_path(
                    packaged_path,
                    selected_active_provider_path=packaged_path,
                    provider_selection=self.provider_selection(
                        packaged_path,
                        source="packaged-kh-skill",
                    ),
                )

        self.assertEqual(result.authority, "current-packaged-fallback")
        self.assertEqual(Path(result.provider_path), packaged_path.resolve())


if __name__ == "__main__":
    unittest.main()
