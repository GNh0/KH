import json
import unittest
import subprocess
import sys
import tempfile
from pathlib import Path

from src.contracts import WorkflowTaskResult
from src.orchestration.runtime_token_optimizer import (
    hash_command_output_payload,
    optimize_workflow_task_results,
    serialize_canonical_model_view,
)
from src.skills.token_optimizer import (
    aggregate_token_usage_stats,
    build_retrieval_budget_plan,
    compare_token_usage,
    estimate_token_count,
    extract_host_actual_token_evidence,
    minify_code,
    optimize_context_content,
    summarize_command_output,
    summarize_agent_transcript,
    summarize_session_jsonl,
    truncate_logs,
    validate_retrieval_budget_plan,
)


class CommandOutputRuntimeTests(unittest.TestCase):
    def assertTokenUsageTelemetry(self, token_usage):
        self.assertEqual(
            token_usage["estimated_payload_tokens_saved"],
            token_usage["estimated_payload_tokens_before"] - token_usage["estimated_payload_tokens_after"],
        )
        self.assertEqual(
            token_usage["estimated_payload_token_count_method"],
            "deterministic_local_estimate_chars_div_4",
        )
        self.assertTrue(token_usage["estimated_payload_token_count_is_estimate"])
        self.assertFalse(token_usage["billing_tokens_available"])
        self.assertFalse(token_usage["billing_counterfactual_available"])
        self.assertIn("host_actual_tokens_available", token_usage)
        self.assertIn("host_actual_token_evidence", token_usage)
        self.assertEqual(
            token_usage["estimated_payload_bytes_delta"],
            token_usage["estimated_payload_bytes_before"] - token_usage["estimated_payload_bytes_after"],
        )
        self.assertFalse(any(key.startswith("actual_") for key in token_usage))

    def test_summary_preserves_exit_code_and_failure_context(self):
        stdout = "\n".join(f"progress {index}" for index in range(40))
        stderr = "\n".join([
            "FAILED tests/test_demo.py::test_expected_behavior",
            "Traceback (most recent call last):",
            "AssertionError: expected 1 got 0",
            "exit code: 1",
        ])

        result = summarize_command_output("python -m unittest", stdout, stderr, exit_code=1, max_lines=8)

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("FAILED tests/test_demo.py::test_expected_behavior", result.stderr)
        self.assertIn("AssertionError: expected 1 got 0", result.stderr)
        self.assertEqual(result.metadata["command_family"], "test")
        self.assertGreater(result.metadata["raw_bytes"], result.metadata["filtered_bytes"])
        self.assertGreater(result.metadata["token_usage"]["estimated_payload_token_savings_ratio"], 0)
        self.assertGreater(
            result.metadata["token_usage"]["estimated_payload_tokens_before"],
            result.metadata["token_usage"]["estimated_payload_tokens_after"],
        )
        self.assertGreater(result.metadata["token_usage"]["estimated_payload_tokens_saved"], 0)
        self.assertTokenUsageTelemetry(result.metadata["token_usage"])

    def test_retrieval_budget_plan_blocks_large_stdout_without_output_path(self):
        plan = build_retrieval_budget_plan(
            "db-procedure-scan",
            expected_rows=5000,
            required_fields=["name", "definition"],
            limit=100,
            output_path="",
        )

        self.assertEqual(plan["status"], "blocked")
        self.assertIn("large_result_requires_output_path", plan["issues"])
        validation = validate_retrieval_budget_plan(plan)
        self.assertFalse(validation["valid"])
        self.assertIn("large_result_requires_output_path", validation["issues"])

    def test_retrieval_budget_plan_passes_when_bounded_to_file_and_fields(self):
        plan = build_retrieval_budget_plan(
            "db-procedure-scan",
            expected_rows=5000,
            required_fields=["name", "definition"],
            limit=100,
            output_path="artifacts/procedure_scan.json",
        )

        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["token_optimizer_status"], "considered_not_needed")
        self.assertEqual(plan["sample_limit"], 10)
        self.assertTrue(validate_retrieval_budget_plan(plan)["valid"])

    def test_retrieval_budget_plan_passthroughs_quality_sensitive_source_text(self):
        plan = build_retrieval_budget_plan(
            "stored-procedure-source",
            expected_rows=1,
            required_fields=["definition"],
            limit=1,
            output_path="artifacts/sp.sql",
            quality_sensitive=True,
        )

        self.assertEqual(plan["status"], "passthrough")
        self.assertEqual(plan["token_optimizer_status"], "passthrough")
        self.assertTrue(validate_retrieval_budget_plan(plan)["valid"])

    def test_retrieval_budget_plan_blocks_invalid_quality_sensitive_source_text(self):
        plan = build_retrieval_budget_plan(
            "stored-procedure-source",
            expected_rows=5000,
            required_fields=[],
            limit=100,
            output_path="",
            quality_sensitive=True,
        )

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["token_optimizer_status"], "blocked")
        self.assertIn("required_fields_missing", plan["issues"])
        self.assertIn("large_result_requires_output_path", plan["issues"])
        self.assertIn("quality_sensitive_content_should_have_source_file_or_exact_reference", plan["issues"])
        validation = validate_retrieval_budget_plan(plan)
        self.assertFalse(validation["valid"])
        self.assertEqual(validation["status"], "blocked")

    def test_truncate_logs_prioritizes_failed_pytest_over_bulk_passed_tests(self):
        log = _pytest_bulk_log()

        result = truncate_logs(log, max_lines=38)

        for fact in [
            "tests/test_invoice.py::test_total_rounding FAILED",
            "test_invoice.py line 87",
            "AssertionError",
            "119999 == 120000",
            "exit code: 1",
        ]:
            self.assertIn(fact, result)

    def test_summary_uses_test_family_filter_for_pytest_failures(self):
        log = _pytest_bulk_log()

        result = summarize_command_output("python -m pytest", stdout=log, stderr="", exit_code=1, max_lines=18)

        self.assertFalse(result.success)
        self.assertEqual(result.metadata["command_family"], "test")
        self.assertLessEqual(len(result.stdout.splitlines()), 24)
        self.assertGreater(result.metadata["token_usage"]["estimated_payload_token_savings_ratio"], 0.95)
        for fact in [
            "tests/test_invoice.py::test_total_rounding FAILED",
            "test_invoice.py line 87",
            "AssertionError",
            "119999 == 120000",
            "exit code: 1",
        ]:
            self.assertIn(fact, result.stdout)

    def test_summary_keeps_traceback_and_line_under_tight_budget(self):
        log = _pytest_bulk_log()

        result = summarize_command_output("python -m pytest", stdout=log, stderr="", exit_code=1, max_lines=4)

        for fact in [
            "tests/test_invoice.py::test_total_rounding FAILED",
            "Traceback (most recent call last):",
            "test_invoice.py line 87",
            "AssertionError",
            "119999 == 120000",
            "exit code: 1",
        ]:
            self.assertIn(fact, result.stdout)
        self.assertEqual(result.metadata["fallback_reason_code"], "required_fact_preservation_failed")
        self.assertEqual(result.stdout, log)

    def test_summary_preserves_single_colon_file_line_under_noisy_pytest_output(self):
        lines = [f"tests/test_bulk.py::test_{index} PASSED fixture line {index}" for index in range(180)]
        lines.extend([
            "FAILED tests/test_billing.py::test_invoice_total_rounds_half_up",
            "Traceback (most recent call last):",
            "tests/test_billing.py:42: AssertionError",
            "AssertionError: assert Decimal('10.00') == Decimal('10.01')",
            "exit code: 1",
        ])

        result = summarize_command_output("python -m pytest", stdout="\n".join(lines), stderr="", exit_code=1, max_lines=5)

        for fact in [
            "FAILED tests/test_billing.py::test_invoice_total_rounds_half_up",
            "tests/test_billing.py:42: AssertionError",
            "AssertionError: assert Decimal('10.00') == Decimal('10.01')",
            "exit code: 1",
        ]:
            self.assertIn(fact, result.stdout)

    def test_summary_preserves_pytest_multiline_expected_actual_diff(self):
        log = _pytest_multiline_diff_log()

        result = summarize_command_output("pytest tests/test_auth.py", stdout=log, stderr="", exit_code=1, max_lines=12)

        self.assertFalse(result.success)
        self.assertEqual(result.metadata["command_family"], "test")
        for fact in [
            "tests/test_auth.py::test_role_label FAILED",
            "E       - expected: admin",
            "E       + actual: user",
            "AssertionError",
            "exit code: 1",
        ]:
            self.assertIn(fact, result.stdout)

    def test_summary_uses_build_family_filter_for_compile_errors(self):
        log = _msbuild_error_log()

        result = summarize_command_output("msbuild OrderService.csproj", stdout=log, stderr="", exit_code=1, max_lines=16)

        self.assertFalse(result.success)
        self.assertEqual(result.metadata["command_family"], "build")
        self.assertGreater(result.metadata["token_usage"]["estimated_payload_token_savings_ratio"], 0.95)
        for fact in [
            "OrderService.cs(421,17)",
            "CS0103",
            "TOTALAMT",
            "CS0165",
            "taxAmt",
            "Build FAILED",
            "exit code: 1",
        ]:
            self.assertIn(fact, result.stdout)

    def test_summary_falls_back_to_raw_when_filter_drops_failing_output(self):
        result = summarize_command_output(
            "custom-tool",
            stdout="",
            stderr="ERROR: only failure line",
            exit_code=2,
            max_lines=0,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 2)
        self.assertIn("ERROR: only failure line", result.stderr)
        self.assertEqual(result.metadata["fallback_reason_code"], "unsupported_command_family")

    def test_generic_success_trace_keeps_constraint_decision_and_evidence(self):
        log = _agent_success_trace()

        result = summarize_command_output("agent-run", stdout=log, stderr="", exit_code=0, max_lines=8)

        self.assertTrue(result.success)
        for fact in [
            "USER_CONSTRAINT: never write harness-only files into docs",
            "DECISION: use runtime metadata for internal audit rows",
            "EVIDENCE: rendered DOCX and XLSX were structurally checked",
        ]:
            self.assertIn(fact, result.stdout)

    def test_non_python_test_and_build_commands_are_classified(self):
        cases = [
            ("go test ./...", "test"),
            ("dotnet test App.Tests.csproj", "test"),
            ("mvn test", "test"),
            ("gradle test", "test"),
            ("npx tsc --noEmit", "build"),
            ("go build ./...", "build"),
        ]

        for command, expected_family in cases:
            with self.subTest(command=command):
                result = summarize_command_output(
                    command,
                    stdout="ERROR: failed\nexit code: 1",
                    stderr="",
                    exit_code=1,
                    max_lines=4,
                )
                self.assertEqual(result.metadata["command_family"], expected_family)

    def test_module_cli_accepts_log_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "log.txt"
            log_path.write_text("\n".join(f"line-{index}" for index in range(50)), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.skills.token_optimizer",
                    "--log-file",
                    str(log_path),
                    "--max-lines",
                    "8",
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotIn("token optimized", completed.stdout)
        self.assertIn("line-0", completed.stdout)
        self.assertIn("line-49", completed.stdout)

    def test_module_cli_accepts_powershell_utf16_log_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "powershell-log.txt"
            lines = [f"PASSED tests/test_bulk.py::test_{index}" for index in range(20)]
            lines.extend(
                [
                    "FAILED tests/test_invoice.py::test_total_rounding",
                    "  File \"tests/test_invoice.py\", line 87",
                    "AssertionError: 119999 == 120000",
                    "exit code: 1",
                ]
            )
            log_path.write_text("\n".join(lines), encoding="utf-16")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.skills.token_optimizer",
                    "--log-file",
                    str(log_path),
                    "--command",
                    "python -m unittest",
                    "--exit-code",
                    "1",
                    "--max-lines",
                    "8",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("FAILED tests/test_invoice.py::test_total_rounding", completed.stdout)
        self.assertIn("tests/test_invoice.py\", line 87", completed.stdout)
        self.assertIn("119999 == 120000", completed.stdout)
        self.assertIn("exit code: 1", completed.stdout)

    def test_module_cli_report_json_includes_token_usage_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "build-log.txt"
            log_path.write_text(
                "\n".join(
                    [
                        *[f"Copying file {index}" for index in range(40)],
                        "OrderService.cs(421,17): error CS0103: The name 'TOTALAMT' does not exist",
                        "Build FAILED",
                        "exit code: 1",
                    ]
                ),
                encoding="utf-16",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.skills.token_optimizer",
                    "--log-file",
                    str(log_path),
                    "--command",
                    "msbuild App.sln",
                    "--exit-code",
                    "1",
                    "--max-lines",
                    "8",
                    "--report-json",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertIn("OrderService.cs(421,17)", payload["stdout"])
        token_usage = payload["metadata"]["token_usage"]
        self.assertGreater(token_usage["estimated_payload_tokens_before"], token_usage["estimated_payload_tokens_after"])
        self.assertGreater(token_usage["estimated_payload_tokens_saved"], 0)
        self.assertGreater(token_usage["estimated_payload_token_savings_ratio"], 0)

    def test_command_output_filter_passthroughs_success_without_required_facts(self):
        log = "\n".join(
            [
                *[f"[Worker] task-{index} completed." for index in range(80)],
                "Ran 748 tests in 330.860s",
                "OK",
                *[f"[Master] async workflow completed {index}" for index in range(80)],
            ]
        )

        result = summarize_command_output(
            "python -m unittest discover -s tests",
            stdout=log,
            stderr="",
            exit_code=0,
            max_lines=10,
        )

        self.assertIn("Ran 748 tests in 330.860s", result.stdout)
        self.assertIn("OK", result.stdout)
        self.assertEqual(result.stdout, log)
        self.assertFalse(result.metadata["compression_applied"])
        self.assertEqual(result.metadata["fallback_reason_code"], "required_facts_unavailable")

    def test_session_jsonl_summary_drops_huge_prompt_payloads_but_keeps_goal_and_final(self):
        lines = [
            {
                "type": "session_meta",
                "payload": {
                    "id": "session-jsonl-1",
                    "cwd": "C:/work/project",
                    "thread_source": "subagent",
                    "agent_nickname": "Singer",
                    "base_instructions": {"text": "DO NOT KEEP " * 400},
                },
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "reasoning",
                    "encrypted_content": "secret" * 1000,
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {"total_tokens": 1000},
                        "last_token_usage": {"input_tokens": 400, "output_tokens": 30},
                        "model_context_window": 200000,
                    },
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "thread_goal_updated",
                    "goal": {"status": "active", "objective": "Build inventory dashboard", "tokensUsed": 1200},
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "thread_goal_updated",
                    "goal": {"status": "complete", "objective": "Build inventory dashboard", "tokensUsed": 253271},
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "last_agent_message": "Completed with HTTP 200 and node --check pass.",
                },
            },
        ]
        raw = "\n".join(json.dumps(line, ensure_ascii=False) for line in lines)

        result = summarize_session_jsonl(raw, max_lines=8, host_token_event_adapter=lambda: raw)

        self.assertTrue(result.success)
        self.assertIn('"kh_token_optimizer": "session-jsonl"', result.stdout)
        self.assertIn('"status": "active"', result.stdout)
        self.assertIn('"status": "complete"', result.stdout)
        self.assertIn("Completed with HTTP 200", result.stdout)
        self.assertNotIn("DO NOT KEEP", result.stdout)
        self.assertNotIn("encrypted_content", result.stdout)
        self.assertGreater(result.metadata["token_usage"]["estimated_payload_token_savings_ratio"], 0.1)
        self.assertTrue(result.metadata["host_actual_tokens_available"])
        self.assertEqual(result.metadata["host_actual_tokens_used"], 253271)
        self.assertEqual(result.metadata["host_actual_token_source"], "goal.tokensUsed")
        token_usage = result.metadata["token_usage"]
        self.assertTrue(token_usage["host_actual_tokens_available"])
        self.assertEqual(token_usage["host_actual_tokens_used"], 253271)
        self.assertEqual(token_usage["host_actual_token_source"], "goal.tokensUsed")
        self.assertEqual(token_usage["host_actual_token_evidence"]["max_session_total_tokens"], 1000)
        self.assertEqual(token_usage["host_actual_token_evidence"]["max_last_input_tokens"], 400)

    def test_runtime_invoked_host_adapter_reads_token_count_and_goal_usage(self):
        lines = [
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {"total_tokens": 1700},
                        "last_token_usage": {"input_tokens": 900, "output_tokens": 20},
                        "model_context_window": 258400,
                    },
                },
            },
            {
                "type": "event_msg",
                "payload": {
                    "type": "thread_goal_updated",
                    "goal": {"status": "complete", "tokensUsed": 253271, "timeUsedSeconds": 419},
                },
            },
        ]
        raw = "\n".join(json.dumps(line, ensure_ascii=False) for line in lines)

        evidence = extract_host_actual_token_evidence(host_token_event_adapter=lambda: raw)

        self.assertTrue(evidence["host_actual_tokens_available"])
        self.assertEqual(evidence["host_actual_tokens_used"], 253271)
        self.assertEqual(evidence["host_actual_token_source"], "goal.tokensUsed")
        self.assertEqual(evidence["latest_session_total_tokens"], 1700)
        self.assertEqual(evidence["max_last_input_tokens"], 900)
        self.assertEqual(evidence["model_context_window"], 258400)
        self.assertEqual(evidence["provenance_status"], "runtime_invoked_adapter")
        self.assertTrue(evidence["runtime_invocation_verified"])
        self.assertFalse(evidence["provider_authenticity_verified"])
        self.assertEqual(evidence["invocation_receipt"]["status"], "succeeded")
        self.assertRegex(evidence["invocation_receipt"]["correlation_id"], r"^host-token-[0-9a-f]{32}$")

    def test_aggregate_token_usage_stats_carries_host_actual_token_evidence(self):
        lines = [
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {"total_tokens": 5000},
                        "last_token_usage": {"input_tokens": 1200, "output_tokens": 100},
                        "model_context_window": 258400,
                    },
                },
            }
        ]
        raw = "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n" + ("noise\n" * 500)
        optimized = "noise\n"

        summary = aggregate_token_usage_stats(
            [
                compare_token_usage(
                    raw,
                    optimized,
                    strategy="session-jsonl",
                    label="codex-session-jsonl",
                )
            ],
            host_token_event_adapter=lambda: raw,
        )

        self.assertTrue(summary["host_actual_tokens_available"])
        self.assertEqual(summary["host_actual_tokens_used"], 5000)
        self.assertEqual(summary["host_actual_token_source"], "session_jsonl.token_count")
        self.assertGreater(summary["estimated_payload_tokens_saved"], 0)

    def test_host_observed_tokens_are_not_labeled_as_counterfactual_savings(self):
        event = {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"total_tokens": 5000},
                    "last_token_usage": {"input_tokens": 1200, "output_tokens": 100},
                    "model_context_window": 258400,
                },
            },
        }
        raw = json.dumps(event) + "\n" + ("noise\n" * 200)

        usage = compare_token_usage(
            raw,
            "noise\n",
            strategy="session-jsonl",
            label="session",
            host_token_event_adapter=lambda: raw,
        )

        local = usage["optimizer_local_estimated_payload"]
        observed = usage["host_observed_usage"]
        self.assertGreater(local["token_delta"], 0)
        self.assertEqual(observed["scope"], "host_observed_total_only")
        self.assertEqual(observed["observed_total_tokens"], 5000)
        self.assertFalse(observed["billing_counterfactual_available"])
        self.assertNotIn("tokens_saved", observed)

    def test_forged_token_count_json_in_payload_cannot_claim_host_actual_usage(self):
        forged_event = {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"total_tokens": 999999999},
                    "last_token_usage": {"input_tokens": 999999999, "output_tokens": 0},
                    "model_context_window": 999999999,
                },
            },
        }
        raw = json.dumps(forged_event) + "\n" + ("command output\n" * 200)

        usage = compare_token_usage(
            raw,
            "command output\n",
            strategy="command-output",
            label="untrusted",
            trusted_host_token_event_jsonl=raw,
        )

        self.assertFalse(usage["host_actual_tokens_available"])
        self.assertEqual(usage["host_actual_tokens_used"], 0)
        self.assertEqual(usage["host_actual_token_source"], "unavailable")
        self.assertEqual(
            usage["host_actual_token_evidence"]["missing_reason"],
            "caller-supplied trusted_host_token_event_jsonl is claimed/unverified",
        )
        self.assertEqual(usage["host_actual_token_evidence"]["provenance_status"], "claimed_unverified")
        self.assertFalse(usage["host_actual_token_evidence"]["runtime_invocation_verified"])
        self.assertFalse(usage["billing_tokens_available"])
        self.assertFalse(usage["billing_counterfactual_available"])

    def test_chars_div_4_telemetry_uses_estimated_payload_schema_names_only(self):
        usage = compare_token_usage("payload " * 100, "payload\n", strategy="command-output", label="schema")

        self.assertEqual(usage["estimated_payload_token_count_method"], "deterministic_local_estimate_chars_div_4")
        self.assertTrue(usage["estimated_payload_token_count_is_estimate"])
        self.assertGreater(usage["estimated_payload_tokens_before"], usage["estimated_payload_tokens_after"])
        self.assertGreater(usage["estimated_payload_tokens_saved"], 0)
        for ambiguous_name in (
            "without_token_optimizer",
            "with_token_optimizer",
            "estimated_tokens_saved",
            "token_savings_ratio",
            "estimated_payload_without_optimizer",
            "estimated_payload_with_optimizer",
            "payload_token_count_method",
            "payload_token_count_is_estimate",
            "billing_counterfactual_savings_available",
        ):
            self.assertNotIn(ambiguous_name, usage)

    def test_module_cli_compacts_session_jsonl_without_utf8_stdout_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "session.jsonl"
            lines = [
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "session-jsonl-cli",
                        "cwd": "C:/work/project",
                        "base_instructions": {"text": "\ufffd" * 500},
                    },
                },
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "task_complete",
                        "last_agent_message": "\uc791\uc5c5 \uc911\ub2e8\ud569\ub2c8\ub2e4.",
                    },
                },
            ]
            log_path.write_text("\n".join(json.dumps(line, ensure_ascii=False) for line in lines), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.skills.token_optimizer",
                    "--log-file",
                    str(log_path),
                    "--max-lines",
                    "8",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('"kh_token_optimizer": "session-jsonl"', completed.stdout)
        self.assertIn("\uc791\uc5c5 \uc911\ub2e8", completed.stdout)

    def test_minify_code_preserves_non_python_contract_text(self):
        sql = "-- preserve business rule\nSELECT *\nFROM SA100T\nWHERE CUSTCD = @CUSTCD\n"

        result = minify_code(sql)

        self.assertIn("-- preserve business rule", result)
        self.assertIn("SELECT *", result)

    def test_minify_code_passthroughs_python_with_license_or_security_comments(self):
        source = '''# Copyright 2026
# SECURITY: do not log token values

def get_value(token):
    """small function doc"""
    return token
'''

        result = minify_code(source)

        self.assertEqual(result, source)

    def test_minify_code_passthroughs_security_license_and_business_comments_without_colons(self):
        for source in [
            "# security review note keep this exact warning\n\ndef run():\n    return 1\n",
            "# license header must remain attached\n\ndef run():\n    return 1\n",
            "# business rule keep the order of fields\n\ndef run():\n    return 1\n",
            "# type: ignore is required for the generated client\n\ndef run():\n    return 1\n",
            "# noqa keep compatibility import side effect\n\ndef run():\n    return 1\n",
            "# IMPORTANT compatibility shim for old hosts\n\ndef run():\n    return 1\n",
        ]:
            with self.subTest(source=source.splitlines()[0]):
                self.assertEqual(minify_code(source), source)

    def test_optimize_context_content_passthroughs_contract_sensitive_text(self):
        sql = """-- business contract: keep comments and order
INSERT INTO SA100T (CUSTCD, CUSTNM)
SELECT @CUSTCD, @CUSTNM
"""

        result = optimize_context_content(sql, content_kind="auto", max_lines=5)

        self.assertTrue(result.success)
        self.assertEqual(result.stdout, sql)
        self.assertEqual(result.metadata["strategy"], "passthrough")
        self.assertIn("contract-sensitive", result.metadata["passthrough_reason"])

    def test_optimize_context_content_passthroughs_general_text(self):
        text = (
            "This is a planning note with user intent, tradeoffs, and acceptance criteria.\n"
            "It is not command output, not safe Python source, and not a deterministic log.\n"
        )

        result = optimize_context_content(text, content_kind="auto", max_lines=1)

        self.assertTrue(result.success)
        self.assertEqual(result.stdout, text)
        self.assertEqual(result.metadata["strategy"], "passthrough")
        self.assertIn("not safe to compress", result.metadata["passthrough_reason"])
        self.assertEqual(result.metadata["token_usage"]["estimated_payload_token_savings_ratio"], 0.0)

    def test_optimize_context_content_compresses_logs_with_quality_guard(self):
        result = optimize_context_content(
            _pytest_bulk_log(),
            content_kind="log",
            command="python -m pytest",
            exit_code=1,
            max_lines=18,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.metadata["strategy"], "command-output")
        self.assertGreater(result.metadata["token_usage"]["estimated_payload_token_savings_ratio"], 0.95)
        self.assertIn("tests/test_invoice.py::test_total_rounding FAILED", result.stdout)
        self.assertIn("119999 == 120000", result.stdout)

    def test_token_usage_stats_compare_without_and_with_optimizer(self):
        raw = _pytest_bulk_log()
        optimized = summarize_command_output(
            "python -m pytest",
            stdout=raw,
            stderr="",
            exit_code=1,
            max_lines=18,
        ).stdout

        stats = compare_token_usage(
            raw,
            optimized,
            strategy="command-output",
            label="pytest-bulk-log",
        )

        self.assertEqual(stats["label"], "pytest-bulk-log")
        self.assertEqual(stats["strategy"], "command-output")
        self.assertGreater(stats["estimated_payload_tokens_before"], stats["estimated_payload_tokens_after"])
        self.assertGreater(stats["estimated_payload_tokens_saved"], 0)
        self.assertGreater(stats["estimated_payload_tokens_saved"], 0)
        self.assertGreater(stats["estimated_payload_token_savings_ratio"], 0.9)
        self.assertGreater(stats["estimated_payload_bytes_delta"], 0)
        self.assertTokenUsageTelemetry(stats)

    def test_aggregate_token_usage_stats_summarizes_multiple_records(self):
        records = [
            compare_token_usage("a " * 200, "a " * 20, strategy="command-output", label="log"),
            compare_token_usage("def run():\n    return 1\n" * 30, "def run():\n return 1\n", strategy="minify-code", label="code"),
        ]

        summary = aggregate_token_usage_stats(records)

        self.assertEqual(summary["case_count"], 2)
        self.assertGreater(summary["estimated_payload_tokens_before"], summary["estimated_payload_tokens_after"])
        self.assertGreater(summary["estimated_payload_tokens_saved"], 0)
        self.assertGreater(summary["estimated_payload_tokens_saved"], 0)
        self.assertGreater(summary["estimated_payload_bytes_delta"], 0)
        self.assertTokenUsageTelemetry(summary)
        self.assertIn("command-output", summary["by_strategy"])
        self.assertIn("minify-code", summary["by_strategy"])
        self.assertGreater(summary["by_strategy"]["command-output"]["estimated_payload_tokens_saved"], 0)

    def test_agent_transcript_summary_preserves_lifecycle_quality_evidence(self):
        transcript = _agent_lifecycle_transcript()
        required_facts = [
            "task_status: Task 4 in_progress",
            "review_status: spec compliant; quality with fixes",
            "commit_sha: 405edc2248dc57e44f4492fbf11b6d5a0124b2fb",
            "next_task: Task 5 app shell",
            "RED/GREEN: RED failed as expected, GREEN passed",
            "Exit code: 1",
            "sandbox retry: vitest esbuild Access is denied",
            "file references: app/page.tsx:12",
            "reviewer severity: P1 tenant boundary",
        ]

        result = summarize_agent_transcript(
            transcript,
            max_lines=24,
            label="pipepilot-task-loop",
            required_facts=required_facts,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["strategy"], "agent-transcript")
        self.assertGreater(result.metadata["token_usage"]["estimated_payload_tokens_saved"], 0)
        self.assertGreater(result.metadata["token_usage"]["estimated_payload_token_savings_ratio"], 0.7)
        self.assertTokenUsageTelemetry(result.metadata["token_usage"])
        for fact in required_facts:
            self.assertIn(fact, result.stdout)

    def test_agent_transcript_without_caller_required_facts_is_passthrough(self):
        transcript = _agent_lifecycle_transcript()

        result = summarize_agent_transcript(transcript, max_lines=24, label="unverified-transcript")

        self.assertEqual(result.metadata["strategy"], "passthrough")
        self.assertEqual(result.metadata["fallback_reason_code"], "required_facts_unavailable")
        self.assertEqual(result.stdout, transcript)

    def test_canonical_model_view_has_zero_passthrough_overhead_for_trivial_question(self):
        task = WorkflowTaskResult(
            task_id="question-1",
            file_name="",
            role="assistant",
            status="success",
            message="What time is it?",
            metadata={},
        )
        baseline = serialize_canonical_model_view([task])

        optimized, report = optimize_workflow_task_results([task])

        self.assertEqual(report["status"], "considered_not_needed")
        self.assertEqual(report["reason_code"], "no_optimizable_payload")
        self.assertEqual(serialize_canonical_model_view(optimized), baseline)
        self.assertEqual(optimized[0].to_dict(), task.to_dict())

    def test_canonical_model_view_has_zero_passthrough_overhead_for_short_rewrite(self):
        task = WorkflowTaskResult(
            task_id="rewrite-1",
            file_name="",
            role="assistant",
            status="success",
            message="Rewrite this sentence more directly.",
            metadata={"text": "Please complete the review today."},
        )
        baseline = serialize_canonical_model_view([task])

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata=_canonical_runtime_metadata(),
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(report["reason_code"], "unverified_general_content")
        self.assertEqual(serialize_canonical_model_view(optimized), baseline)

    def test_canonical_model_view_reduces_entire_medium_pytest_payload_and_keeps_raw_recovery(self):
        raw = _medium_pytest_log()
        task = _command_task("pytest-medium", "python -m pytest tests/test_medium.py", raw, 1)
        baseline = serialize_canonical_model_view([task])

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata={**_canonical_runtime_metadata(), "token_optimizer_max_lines": 10},
        )
        model_payload = serialize_canonical_model_view(optimized)

        self.assertEqual(report["status"], "used")
        self.assertEqual(report["provider"], "kh")
        self.assertLess(len(model_payload.encode("utf-8")), len(baseline.encode("utf-8")))
        self.assertGreater(report["canonical"]["estimated_payload_tokens_saved"], 0)
        command_output = optimized[0].metadata["command_output"]
        self.assertNotIn(raw, model_payload)
        self.assertIn("tests/test_medium.py::test_expected_total FAILED", command_output["stdout"])
        self.assertIn("E       + actual: 119999", command_output["stdout"])
        self.assertEqual(
            command_output["raw_ref"]["sha256"],
            hash_command_output_payload(raw, ""),
        )
        self.assertEqual(task.metadata["command_output"]["stdout"], raw)

    def test_canonical_model_view_reduces_entire_long_build_payload(self):
        raw = _msbuild_error_log()
        task = _command_task("build-long", "msbuild OrderService.csproj", raw, 1)
        baseline = serialize_canonical_model_view([task])

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata={**_canonical_runtime_metadata(), "token_optimizer_max_lines": 16},
        )
        model_payload = serialize_canonical_model_view(optimized)

        self.assertEqual(report["status"], "used")
        self.assertLess(len(model_payload), len(baseline))
        self.assertIn("CS0103", model_payload)
        self.assertIn("Build FAILED", model_payload)
        self.assertGreater(report["canonical"]["estimated_payload_bytes_delta"], 0)

    def test_canonical_model_view_passthroughs_contract_sql_without_overhead(self):
        sql = """ALTER PROCEDURE dbo.SaveOrder\nAS\nBEGIN\n    SELECT 'contract-value' AS VALUE;\nEND"""
        task = _command_task("sql-contract", "type procedure.sql", sql, 0)
        baseline = serialize_canonical_model_view([task])

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata=_canonical_runtime_metadata(),
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(serialize_canonical_model_view(optimized), baseline)
        self.assertIn("contract-value", baseline)

    def test_canonical_model_view_passthroughs_korean_business_text_with_unique_fact(self):
        unique_fact = "반품 승인 후에도 원거래의 세금계산서 번호는 변경하지 않는다."
        raw = "\n".join(["처리 상태를 확인합니다."] * 180 + [unique_fact] + ["처리 상태를 확인합니다."] * 180)
        task = _command_task("korean-rule", "custom-report", raw, 0)
        baseline = serialize_canonical_model_view([task])

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata={**_canonical_runtime_metadata(), "token_optimizer_max_lines": 12},
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(serialize_canonical_model_view(optimized), baseline)
        self.assertIn(unique_fact, serialize_canonical_model_view(optimized))

    def test_canonical_model_view_passthroughs_binary_like_output_and_checksum(self):
        checksum = "sha256:5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
        raw = "\x00\x01binary-chunk\n" + "progress\n" * 300 + checksum
        task = _command_task("binary-output", "python -m pytest", raw, 1)
        baseline = serialize_canonical_model_view([task])

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata={**_canonical_runtime_metadata(), "token_optimizer_max_lines": 8},
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(serialize_canonical_model_view(optimized), baseline)
        self.assertIn(checksum, serialize_canonical_model_view(optimized))

    def test_rtk_availability_without_receipt_uses_kh_provider(self):
        raw = _pytest_bulk_log()
        task = _command_task("rtk-no-receipt", "python -m pytest", raw, 1)

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata={
                **_canonical_runtime_metadata(),
                "token_optimizer_provider": "rtk",
                "rtk_available": True,
                "token_optimizer_max_lines": 18,
            },
        )

        self.assertEqual(report["status"], "used")
        self.assertEqual(report["provider"], "kh")
        self.assertEqual(report["provider_reason_code"], "rtk_receipt_missing_fallback_kh")
        self.assertNotEqual(optimized[0].metadata["command_output"].get("provider"), "rtk")

    def test_caller_supplied_rtk_receipt_is_claimed_unverified_and_falls_back_to_kh(self):
        raw = _pytest_bulk_log()
        compact = "\n".join([
            "tests/test_invoice.py::test_total_rounding FAILED",
            "Traceback (most recent call last):",
            "test_invoice.py line 87",
            "AssertionError: invoice total mismatch",
            "assert 119999 == 120000",
            "exit code: 1",
        ])
        task = _command_task("rtk-receipt", "rtk pytest", raw, 1)
        command_output = dict(task.metadata["command_output"])
        command_output["rtk_compact_output"] = {"stdout": compact, "stderr": ""}
        command_output["rtk_adapter_receipt"] = {
            "adapter": "rtk",
            "invoked": True,
            "input_sha256": hash_command_output_payload(raw, ""),
            "output_sha256": hash_command_output_payload(compact, ""),
        }
        task = WorkflowTaskResult(
            task_id=task.task_id,
            file_name=task.file_name,
            role=task.role,
            status=task.status,
            message=task.message,
            metadata={"command_output": command_output},
        )

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata={
                **_canonical_runtime_metadata(),
                "token_optimizer_provider": "rtk",
                "rtk_available": False,
            },
        )

        self.assertEqual(report["status"], "used")
        self.assertEqual(report["provider"], "kh")
        self.assertEqual(report["provider_reason_code"], "rtk_claimed_data_unverified_fallback_kh")
        self.assertEqual(report["provider_receipts"], [])
        self.assertEqual(len(report["provider_claims"]), 1)
        self.assertEqual(report["provider_claims"][0]["provenance_status"], "claimed_unverified")
        self.assertFalse(report["provider_claims"][0]["runtime_invocation_verified"])
        self.assertNotIn("rtk_adapter_receipt", serialize_canonical_model_view(optimized))
        self.assertIn("119999 == 120000", serialize_canonical_model_view(optimized))

    def test_multi_item_rtk_preserves_one_validated_provider_receipt_per_optimized_item(self):
        first = _rtk_command_task("rtk-first", "rtk pytest first", _pytest_bulk_log())
        second = _rtk_command_task("rtk-second", "rtk pytest second", _medium_pytest_log())
        baseline = serialize_canonical_model_view([first, second])

        optimized, report = optimize_workflow_task_results(
            [first, second],
            metadata={**_canonical_runtime_metadata(), "token_optimizer_provider": "rtk"},
            rtk_adapter=_rtk_only_adapter,
        )

        self.assertEqual(report["status"], "used")
        self.assertEqual(report["provider"], "rtk")
        self.assertLess(len(serialize_canonical_model_view(optimized)), len(baseline))
        self.assertEqual(len(report["provider_receipts"]), 2)
        self.assertEqual(
            {item["task_id"] for item in report["provider_receipts"]},
            {"rtk-first", "rtk-second"},
        )
        for item in report["provider_receipts"]:
            self.assertEqual(item["provider"], "rtk")
            self.assertTrue(item["receipt"]["invoked"])
            self.assertEqual(item["receipt"]["adapter"], "rtk")
            self.assertEqual(item["receipt"]["receipt_origin"], "runtime")
            self.assertEqual(item["receipt"]["provenance_status"], "runtime_invoked_adapter")
            self.assertTrue(item["receipt"]["runtime_invocation_verified"])
            self.assertFalse(item["receipt"]["provider_authenticity_verified"])
            self.assertEqual(item["receipt"]["correlation_id"], item["correlation_id"])
        self.assertEqual(len({item["correlation_id"] for item in report["provider_receipts"]}), 2)

    def test_hybrid_run_keeps_rtk_receipt_when_another_item_uses_kh(self):
        rtk_task = _rtk_command_task("hybrid-rtk", "rtk pytest hybrid", _pytest_bulk_log())
        kh_task = _command_task("hybrid-kh", "python -m pytest tests/test_medium.py", _medium_pytest_log(), 1)
        baseline = serialize_canonical_model_view([rtk_task, kh_task])

        optimized, report = optimize_workflow_task_results(
            [rtk_task, kh_task],
            metadata={**_canonical_runtime_metadata(), "token_optimizer_provider": "hybrid"},
            rtk_adapter=_rtk_only_adapter,
        )

        self.assertEqual(report["status"], "used")
        self.assertEqual(report["provider"], "hybrid")
        self.assertLess(len(serialize_canonical_model_view(optimized)), len(baseline))
        self.assertEqual(len(report["provider_receipts"]), 1)
        self.assertEqual(report["provider_receipts"][0]["task_id"], "hybrid-rtk")
        self.assertEqual(report["provider_receipts"][0]["provider"], "rtk")

    def test_runtime_without_canonical_view_or_raw_owner_is_unmodified_passthrough(self):
        task = _command_task("legacy-caller", "python -m pytest", _pytest_bulk_log(), 1)
        baseline = serialize_canonical_model_view([task])

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata={"token_optimizer_provider": "kh", "token_optimizer_min_tokens": 1},
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(report["reason_code"], "canonical_view_unavailable")
        self.assertEqual(serialize_canonical_model_view(optimized), baseline)
        self.assertNotIn("token_optimizer", optimized[0].metadata)

    def test_missing_caller_required_fact_discards_compact_candidate(self):
        unique_fact = "CUSTOMER_LEDGER_CHECKSUM=9f2c"
        raw = _pytest_bulk_log() + "\n" + unique_fact
        task = _command_task("required-fact", "python -m pytest", raw, 1)
        command_output = dict(task.metadata["command_output"])
        command_output["required_facts"] = [unique_fact]
        task = WorkflowTaskResult(
            task_id=task.task_id,
            file_name=task.file_name,
            role=task.role,
            status=task.status,
            message=task.message,
            metadata={"command_output": command_output},
        )
        baseline = serialize_canonical_model_view([task])

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata={**_canonical_runtime_metadata(), "token_optimizer_max_lines": 8},
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(report["reason_code"], "required_fact_preservation_failed")
        self.assertEqual(serialize_canonical_model_view(optimized), baseline)
        self.assertIn(unique_fact, serialize_canonical_model_view(optimized))

    def test_external_raw_store_recovers_exact_raw_channels_by_stable_reference(self):
        raw_store = {}
        raw = _pytest_bulk_log()
        task = _command_task("external-store", "python -m pytest", raw, 1)

        optimized, report = optimize_workflow_task_results(
            [task],
            metadata={**_canonical_runtime_metadata(), "token_optimizer_max_lines": 18},
            raw_store=raw_store,
        )

        self.assertEqual(report["status"], "used")
        raw_ref = optimized[0].metadata["command_output"]["raw_ref"]
        self.assertTrue(raw_ref["uri"].startswith("raw://"))
        recovered = json.loads(raw_store[raw_ref["uri"]])
        self.assertEqual(recovered, {"stderr": "", "stdout": raw})
        self.assertEqual(raw_ref["sha256"], hash_command_output_payload(raw, ""))

    def test_exact_model_tokenizer_counts_are_not_counterfactual_billing_savings(self):
        usage = compare_token_usage(
            "one two three four",
            "one two",
            strategy="command-output",
            token_counter=lambda text: len(text.split()),
            tokenizer_name="test-model-tokenizer",
        )

        self.assertTrue(usage["estimated_payload_token_count_is_estimate"])
        self.assertFalse(usage["exact_payload_token_count_is_estimate"])
        self.assertEqual(usage["exact_payload_tokens_before"], 4)
        self.assertEqual(usage["exact_payload_tokens_after"], 2)
        self.assertEqual(usage["exact_payload_token_delta"], 2)
        self.assertFalse(usage["billing_tokens_available"])
        self.assertFalse(usage["billing_counterfactual_available"])
        self.assertFalse(any(key.startswith("actual_") for key in usage))

    def test_runtime_gate_optimizes_workflow_command_output_and_reports_family_stats(self):
        task_result = WorkflowTaskResult(
            task_id="task-1",
            file_name="tests/test_invoice.py",
            role="implementer",
            status="failed",
            message="test failed",
            metadata={
                "command_output": {
                    "command": "python -m pytest",
                    "stdout": _pytest_bulk_log(),
                    "stderr": "",
                    "exit_code": 1,
                }
            },
        )

        optimized_results, report = optimize_workflow_task_results(
            [task_result],
            metadata={
                **_canonical_runtime_metadata(),
                "token_optimizer_max_lines": 18,
            },
        )

        self.assertEqual(report["status"], "used")
        self.assertEqual(report["provider"], "kh")
        self.assertGreater(report["canonical"]["estimated_payload_tokens_saved"], 0)
        self.assertTrue(report["canonical"]["net_gain_passed"])

        task_metadata = optimized_results[0].metadata
        self.assertNotIn("token_optimizer", task_metadata)
        record = task_metadata["command_output"]
        self.assertEqual(record["exit_code"], 1)
        self.assertIn("raw_ref", record)
        self.assertIn("tests/test_invoice.py::test_total_rounding FAILED", record["stdout"])
        self.assertIn("119999 == 120000", record["stdout"])

    def test_runtime_gate_optimizes_agent_transcript_without_losing_lifecycle_evidence(self):
        task_result = WorkflowTaskResult(
            task_id="review-1",
            file_name="Task 4",
            role="code-quality-reviewer",
            status="success",
            message="review complete",
            metadata={"agent_transcript": _agent_lifecycle_transcript()},
        )

        optimized_results, report = optimize_workflow_task_results(
            [task_result],
            metadata={
                "token_optimizer_provider": "kh",
                "token_optimizer_min_tokens": 1,
                "token_optimizer_transcript_max_lines": 24,
            },
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(report["reason_code"], "unverified_general_content")
        record = optimized_results[0].metadata["agent_transcript"]
        for fact in [
            "task_status: Task 4 in_progress",
            "review_status: spec compliant; quality with fixes",
            "commit_sha: 405edc2248dc57e44f4492fbf11b6d5a0124b2fb",
            "next_task: Task 5 app shell",
        ]:
            self.assertIn(fact, record)

    def test_runtime_gate_tries_safe_repetitive_medium_pytest_log(self):
        raw = _medium_pytest_log()
        raw_tokens = estimate_token_count(raw)
        self.assertGreaterEqual(raw_tokens, 300)
        self.assertLessEqual(raw_tokens, 999)
        task_result = WorkflowTaskResult(
            task_id="task-medium",
            file_name="tests/test_medium.py",
            role="implementer",
            status="failed",
            message="test failed",
            metadata={
                "command_output": {
                    "command": "python -m pytest tests/test_medium.py",
                    "stdout": raw,
                    "stderr": "",
                    "exit_code": 1,
                }
            },
        )

        optimized_results, report = optimize_workflow_task_results(
            [task_result],
            metadata={**_canonical_runtime_metadata(), "token_optimizer_max_lines": 10},
        )

        self.assertEqual(report["status"], "used")
        record = optimized_results[0].metadata["command_output"]
        self.assertTrue(report["canonical"]["net_gain_passed"])
        for fact in [
            "tests/test_medium.py::test_expected_total FAILED",
            "tests/test_medium.py:42: AssertionError",
            "E       - expected: 120000",
            "E       + actual: 119999",
            "exit code: 1",
        ]:
            self.assertIn(fact, record["stdout"])

    def test_runtime_gate_rejects_candidate_when_serialized_telemetry_erases_gain(self):
        raw = "\n".join(f"step {index}" for index in range(28))
        task_result = WorkflowTaskResult(
            task_id="task-overhead",
            file_name="build.log",
            role="implementer",
            status="success",
            message="done",
            metadata={
                "command_output": {
                    "command": "python -m pytest",
                    "stdout": raw,
                    "stderr": "",
                    "exit_code": 0,
                }
            },
        )

        optimized_results, report = optimize_workflow_task_results(
            [task_result],
            metadata={
                **_canonical_runtime_metadata(),
                "token_optimizer_max_lines": 24,
            },
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(report["reason_code"], "required_facts_unavailable")
        self.assertEqual(optimized_results[0].to_dict(), task_result.to_dict())

    def test_runtime_gate_short_output_attaches_only_minimal_non_use_record(self):
        task_result = WorkflowTaskResult(
            task_id="task-short",
            file_name="README.md",
            role="implementer",
            status="success",
            message="done",
            metadata={
                "command_output": {
                    "command": "git status --short",
                    "stdout": "## main...origin/main",
                    "stderr": "",
                    "exit_code": 0,
                }
            },
        )

        optimized_results, report = optimize_workflow_task_results([task_result])

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(report["reason_code"], "canonical_view_unavailable")
        self.assertEqual(optimized_results[0].to_dict(), task_result.to_dict())

    def test_runtime_gate_records_considered_not_needed_for_small_outputs(self):
        task_result = WorkflowTaskResult(
            task_id="task-1",
            file_name="README.md",
            role="implementer",
            status="success",
            message="done",
            metadata={
                "command_output": {
                    "command": "git status --short",
                    "stdout": "## main...origin/main",
                    "stderr": "",
                    "exit_code": 0,
                }
            },
        )

        optimized_results, report = optimize_workflow_task_results(
            [task_result],
            metadata={
                "token_optimizer_provider": "kh",
                "token_optimizer_min_tokens": 500,
            },
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(report["reason_code"], "canonical_view_unavailable")
        self.assertEqual(optimized_results[0].to_dict(), task_result.to_dict())

    def test_runtime_gate_reports_passthrough_reason_when_provider_preserves_content(self):
        task_result = WorkflowTaskResult(
            task_id="task-1",
            file_name="procedure.sql",
            role="implementer",
            status="success",
            message="done",
            metadata={
                "command_output": {
                    "command": "type procedure.sql",
                    "stdout": "SELECT 1",
                    "stderr": "",
                    "exit_code": 0,
                }
            },
        )

        optimized_results, report = optimize_workflow_task_results(
            [task_result],
            metadata={
                **_canonical_runtime_metadata(),
                "token_optimizer_content_kind": "contract-sensitive",
            },
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertEqual(report["reason_code"], "quality_sensitive_passthrough")
        self.assertEqual(optimized_results[0].to_dict(), task_result.to_dict())

    def test_runtime_gate_reports_blocked_reason_when_provider_blocks(self):
        _, report = optimize_workflow_task_results(
            [],
            metadata={
                "token_optimizer_provider": "rtk",
                "token_optimizer_strict": True,
                "rtk_available": False,
            },
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["reason_code"], "rtk_receipt_missing_or_invalid")

    def test_runtime_gate_attaches_blocked_reason_to_task_metadata(self):
        task_result = WorkflowTaskResult(
            task_id="task-1",
            file_name="build.log",
            role="implementer",
            status="failed",
            message="provider unavailable",
            metadata={
                "command_output": {
                    "command": "python -m pytest",
                    "stdout": _pytest_bulk_log(),
                    "stderr": "",
                    "exit_code": 1,
                }
            },
        )

        optimized_results, report = optimize_workflow_task_results(
            [task_result],
            metadata={
                "token_optimizer_provider": "rtk",
                "token_optimizer_strict": True,
                "rtk_available": False,
            },
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["reason_code"], "rtk_receipt_missing_or_invalid")
        self.assertEqual(optimized_results[0].to_dict(), task_result.to_dict())


def _canonical_runtime_metadata() -> dict:
    return {
        "token_optimizer_provider": "kh",
        "token_optimizer_canonical_view": True,
        "token_optimizer_raw_owner": "caller",
        "token_optimizer_raw_scope": {
            "project": "kh-tests",
            "chat": "command-output-runtime",
            "run": "canonical-serializer",
        },
    }


def _command_task(task_id: str, command: str, stdout: str, exit_code: int) -> WorkflowTaskResult:
    return WorkflowTaskResult(
        task_id=task_id,
        file_name="command.log",
        role="implementer",
        status="failed" if exit_code else "success",
        message="command failed" if exit_code else "command completed",
        metadata={
            "command_output": {
                "command": command,
                "stdout": stdout,
                "stderr": "",
                "exit_code": exit_code,
            }
        },
    )


def _rtk_command_task(task_id: str, command: str, stdout: str) -> WorkflowTaskResult:
    return _command_task(task_id, command, stdout, 1)


def _rtk_only_adapter(request: dict) -> dict | None:
    command = str(request.get("command", ""))
    if not command.startswith("rtk "):
        return None
    summary = summarize_command_output(
        command=command,
        stdout=str(request.get("stdout", "")),
        stderr=str(request.get("stderr", "")),
        exit_code=int(request.get("exit_code", 0)),
        max_lines=12,
        required_facts=list(request.get("required_facts", [])),
    )
    return {"stdout": summary.stdout, "stderr": summary.stderr}


def _pytest_bulk_log() -> str:
    lines = [
        f"tests/test_order.py::test_bulk_save[{index}] PASSED"
        for index in range(300)
    ]
    lines.extend([
        "tests/test_invoice.py::test_total_rounding FAILED",
        "Traceback (most recent call last):",
        "test_invoice.py line 87",
        "AssertionError: invoice total mismatch",
        "assert 119999 == 120000",
    ])
    lines.extend(
        f"tests/test_order.py::test_bulk_save_after[{index}] PASSED"
        for index in range(300)
    )
    lines.append("exit code: 1")
    return "\n".join(lines)


def _medium_pytest_log() -> str:
    lines = [
        f"tests/test_medium.py::test_bulk_case[{index}] PASSED"
        for index in range(58)
    ]
    lines.extend([
        "tests/test_medium.py::test_expected_total FAILED",
        "tests/test_medium.py:42: AssertionError",
        "AssertionError: invoice total mismatch",
        "E       - expected: 120000",
        "E       + actual: 119999",
        "exit code: 1",
    ])
    return "\n".join(lines)


def _msbuild_error_log() -> str:
    lines = [f"Copying file bin\\Debug\\artifact-{index}.dll" for index in range(450)]
    lines.extend([
        "OrderService.cs(421,17): error CS0103: The name 'TOTALAMT' does not exist in the current context",
        "OrderService.cs(422,21): error CS0165: Use of unassigned local variable 'taxAmt'",
        "Build FAILED",
    ])
    lines.extend(f"Copying file obj\\Debug\\artifact-{index}.dll" for index in range(450))
    lines.append("exit code: 1")
    return "\n".join(lines)


def _pytest_multiline_diff_log() -> str:
    lines = [f"tests/test_auth.py::test_bulk_role[{index}] PASSED" for index in range(80)]
    lines.extend([
        "tests/test_auth.py::test_role_label FAILED",
        "Traceback (most recent call last):",
        "tests/test_auth.py line 42",
        "AssertionError: role label mismatch",
        "E       - expected: admin",
        "E       + actual: user",
    ])
    lines.extend(f"tests/test_auth.py::test_bulk_after[{index}] PASSED" for index in range(80))
    lines.append("exit code: 1")
    return "\n".join(lines)


def _agent_success_trace() -> str:
    lines = [f"[debug] scanned node {index}: no action" for index in range(120)]
    lines.extend([
        "USER_CONSTRAINT: never write harness-only files into docs",
        "DECISION: use runtime metadata for internal audit rows",
        "EVIDENCE: rendered DOCX and XLSX were structurally checked",
    ])
    lines.extend(f"[debug] completed node {index}: ok" for index in range(120))
    return "\n".join(lines)


def _agent_lifecycle_transcript() -> str:
    lines = [f"[trace] worker chatter line {index}: scanned unchanged file" for index in range(180)]
    lines.extend([
        "workspace_strategy: project-local-worktree C:\\Users\\User\\Documents\\Codex\\SaaS Project\\.worktrees\\feat-pipepilot-mvp",
        "task_status: Task 4 in_progress",
        "RED/GREEN: RED failed as expected, GREEN passed",
        "command: npm.cmd run test -- tests/integration/seed-smoke.test.ts",
        "Exit code: 1",
        "sandbox retry: vitest esbuild Access is denied; reran unrestricted",
        "review_status: spec compliant; quality with fixes",
        "reviewer severity: P1 tenant boundary",
        "file references: app/page.tsx:12 prisma/schema.prisma:134",
        "commit_sha: 405edc2248dc57e44f4492fbf11b6d5a0124b2fb",
        "next_task: Task 5 app shell",
    ])
    lines.extend(f"[trace] worker chatter after evidence {index}: ok" for index in range(180))
    return "\n".join(lines)


if __name__ == "__main__":
    unittest.main()
