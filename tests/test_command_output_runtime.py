import json
import unittest
import subprocess
import sys
import tempfile
from pathlib import Path

from src.contracts import WorkflowTaskResult
from src.orchestration.runtime_token_optimizer import optimize_workflow_task_results
from src.skills.token_optimizer import (
    aggregate_token_usage_stats,
    compare_token_usage,
    extract_host_actual_token_evidence,
    minify_code,
    optimize_context_content,
    summarize_command_output,
    summarize_agent_transcript,
    summarize_session_jsonl,
    truncate_logs,
)


class CommandOutputRuntimeTests(unittest.TestCase):
    def assertTokenUsageTelemetry(self, token_usage):
        self.assertEqual(token_usage["actual_usage_scope"], "actual_optimizer_input_output_payload")
        self.assertEqual(token_usage["token_count_method"], "deterministic_local_estimate_chars_div_4")
        self.assertTrue(token_usage["token_count_is_estimate"])
        self.assertFalse(token_usage["billing_tokens_available"])
        self.assertEqual(token_usage["estimated_payload_tokens_saved"], token_usage["estimated_tokens_saved"])
        self.assertEqual(token_usage["payload_token_count_method"], "deterministic_local_estimate_chars_div_4")
        self.assertTrue(token_usage["payload_token_count_is_estimate"])
        self.assertIn("host_actual_tokens_available", token_usage)
        self.assertIn("host_actual_token_evidence", token_usage)
        self.assertEqual(
            token_usage["actual_tokens_saved"],
            token_usage["actual_without_token_optimizer"] - token_usage["actual_with_token_optimizer"],
        )
        self.assertIn("actual_usage", token_usage)
        self.assertEqual(token_usage["actual_usage"]["scope"], "actual_optimizer_input_output_payload")
        self.assertTrue(token_usage["actual_usage"]["token_count_is_estimate"])
        self.assertFalse(token_usage["actual_usage"]["billing_tokens_available"])

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
        self.assertGreater(result.metadata["token_savings_ratio"], 0)
        self.assertGreater(result.metadata["token_usage"]["without_token_optimizer"], result.metadata["token_usage"]["with_token_optimizer"])
        self.assertGreater(result.metadata["token_usage"]["estimated_tokens_saved"], 0)
        self.assertTokenUsageTelemetry(result.metadata["token_usage"])

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
        self.assertGreater(result.metadata["token_savings_ratio"], 0.95)
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
        self.assertIn("required facts", result.metadata["fallback_reason"])

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
        self.assertGreater(result.metadata["token_savings_ratio"], 0.95)
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
        self.assertEqual(result.metadata["fallback_reason"], "filtered output was empty for failing command")

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
        self.assertIn("token optimized", completed.stdout)
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
        self.assertGreater(token_usage["without_token_optimizer"], token_usage["with_token_optimizer"])
        self.assertGreater(token_usage["actual_tokens_saved"], 0)
        self.assertGreater(token_usage["actual_token_savings_ratio"], 0)

    def test_command_output_filter_preserves_success_test_summary(self):
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
        self.assertGreater(result.metadata["token_savings_ratio"], 0.5)

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

        result = summarize_session_jsonl(raw, max_lines=8)

        self.assertTrue(result.success)
        self.assertIn('"kh_token_optimizer": "session-jsonl"', result.stdout)
        self.assertIn('"status": "active"', result.stdout)
        self.assertIn('"status": "complete"', result.stdout)
        self.assertIn("Completed with HTTP 200", result.stdout)
        self.assertNotIn("DO NOT KEEP", result.stdout)
        self.assertNotIn("encrypted_content", result.stdout)
        self.assertGreater(result.metadata["token_savings_ratio"], 0.1)
        self.assertTrue(result.metadata["host_actual_tokens_available"])
        self.assertEqual(result.metadata["host_actual_tokens_used"], 253271)
        self.assertEqual(result.metadata["host_actual_token_source"], "goal.tokensUsed")
        token_usage = result.metadata["token_usage"]
        self.assertTrue(token_usage["host_actual_tokens_available"])
        self.assertEqual(token_usage["host_actual_tokens_used"], 253271)
        self.assertEqual(token_usage["host_actual_token_source"], "goal.tokensUsed")
        self.assertEqual(token_usage["host_actual_token_evidence"]["max_session_total_tokens"], 1000)
        self.assertEqual(token_usage["host_actual_token_evidence"]["max_last_input_tokens"], 400)

    def test_extract_host_actual_token_evidence_reads_token_count_and_goal_usage(self):
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

        evidence = extract_host_actual_token_evidence(raw)

        self.assertTrue(evidence["host_actual_tokens_available"])
        self.assertEqual(evidence["host_actual_tokens_used"], 253271)
        self.assertEqual(evidence["host_actual_token_source"], "goal.tokensUsed")
        self.assertEqual(evidence["latest_session_total_tokens"], 1700)
        self.assertEqual(evidence["max_last_input_tokens"], 900)
        self.assertEqual(evidence["model_context_window"], 258400)

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

        summary = aggregate_token_usage_stats([
            compare_token_usage(raw, optimized, strategy="session-jsonl", label="codex-session-jsonl")
        ])

        self.assertTrue(summary["host_actual_tokens_available"])
        self.assertEqual(summary["host_actual_tokens_used"], 5000)
        self.assertEqual(summary["host_actual_token_source"], "session_jsonl.token_count")
        self.assertGreater(summary["estimated_payload_tokens_saved"], 0)

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
        self.assertEqual(result.metadata["token_savings_ratio"], 0.0)

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
        self.assertGreater(result.metadata["token_savings_ratio"], 0.95)
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
        self.assertGreater(stats["without_token_optimizer"], stats["with_token_optimizer"])
        self.assertGreater(stats["estimated_tokens_saved"], 0)
        self.assertGreater(stats["token_savings_ratio"], 0.9)
        self.assertGreater(stats["actual_tokens_saved"], 0)
        self.assertGreater(stats["actual_token_savings_ratio"], 0.9)
        self.assertGreater(stats["actual_bytes_saved"], 0)
        self.assertTokenUsageTelemetry(stats)

    def test_aggregate_token_usage_stats_summarizes_multiple_records(self):
        records = [
            compare_token_usage("a " * 200, "a " * 20, strategy="command-output", label="log"),
            compare_token_usage("def run():\n    return 1\n" * 30, "def run():\n return 1\n", strategy="minify-code", label="code"),
        ]

        summary = aggregate_token_usage_stats(records)

        self.assertEqual(summary["case_count"], 2)
        self.assertGreater(summary["without_token_optimizer"], summary["with_token_optimizer"])
        self.assertGreater(summary["estimated_tokens_saved"], 0)
        self.assertGreater(summary["actual_tokens_saved"], 0)
        self.assertGreater(summary["actual_bytes_saved"], 0)
        self.assertTokenUsageTelemetry(summary)
        self.assertIn("command-output", summary["by_strategy"])
        self.assertIn("minify-code", summary["by_strategy"])
        self.assertGreater(summary["by_strategy"]["command-output"]["actual_tokens_saved"], 0)

    def test_agent_transcript_summary_preserves_lifecycle_quality_evidence(self):
        transcript = _agent_lifecycle_transcript()

        result = summarize_agent_transcript(transcript, max_lines=24, label="pipepilot-task-loop")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["strategy"], "agent-transcript")
        self.assertGreater(result.metadata["token_usage"]["estimated_tokens_saved"], 0)
        self.assertGreater(result.metadata["token_usage"]["token_savings_ratio"], 0.7)
        self.assertTokenUsageTelemetry(result.metadata["token_usage"])
        for fact in [
            "task_status: Task 4 in_progress",
            "review_status: spec compliant; quality with fixes",
            "commit_sha: 405edc2248dc57e44f4492fbf11b6d5a0124b2fb",
            "next_task: Task 5 app shell",
            "RED/GREEN: RED failed as expected, GREEN passed",
            "Exit code: 1",
            "sandbox retry: vitest esbuild Access is denied",
            "file references: app/page.tsx:12",
            "reviewer severity: P1 tenant boundary",
        ]:
            self.assertIn(fact, result.stdout)

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
                "token_optimizer_provider": "kh",
                "token_optimizer_min_tokens": 1,
                "token_optimizer_max_lines": 18,
            },
        )

        self.assertEqual(report["status"], "used")
        self.assertEqual(report["provider"]["provider"], "kh")
        self.assertGreater(report["summary"]["estimated_tokens_saved"], 0)
        self.assertGreater(report["summary"]["actual_tokens_saved"], 0)
        self.assertTokenUsageTelemetry(report["summary"])
        self.assertIn("test", report["rtk_style_stats"]["by_command_family"])
        self.assertGreater(
            report["rtk_style_stats"]["by_command_family"]["test"]["estimated_tokens_saved"],
            0,
        )
        self.assertGreater(
            report["rtk_style_stats"]["by_command_family"]["test"]["actual_tokens_saved"],
            0,
        )

        task_metadata = optimized_results[0].metadata
        self.assertEqual(task_metadata["token_optimizer"]["status"], "used")
        record = task_metadata["token_optimizer"]["records"][0]
        self.assertEqual(record["kind"], "command-output")
        self.assertEqual(record["exit_code"], 1)
        self.assertEqual(record["command_family"], "test")
        self.assertTokenUsageTelemetry(record["token_usage"])
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

        self.assertEqual(report["status"], "used")
        record = optimized_results[0].metadata["token_optimizer"]["records"][0]
        self.assertEqual(record["kind"], "agent-transcript")
        self.assertGreater(record["token_usage"]["estimated_tokens_saved"], 0)
        self.assertGreater(record["token_usage"]["actual_tokens_saved"], 0)
        self.assertTokenUsageTelemetry(record["token_usage"])
        for fact in [
            "task_status: Task 4 in_progress",
            "review_status: spec compliant; quality with fixes",
            "commit_sha: 405edc2248dc57e44f4492fbf11b6d5a0124b2fb",
            "next_task: Task 5 app shell",
        ]:
            self.assertIn(fact, record["transcript"])

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

        self.assertEqual(report["status"], "considered_not_needed")
        self.assertIn("not used", report["not_used_reason"])
        self.assertIn("500 tokens", report["token_optimizer_status_reason"])
        self.assertEqual(report["summary"]["case_count"], 1)
        self.assertGreater(report["summary"]["without_token_optimizer"], 0)
        self.assertEqual(
            report["summary"]["without_token_optimizer"],
            report["summary"]["with_token_optimizer"],
        )
        self.assertEqual(report["summary"]["estimated_tokens_saved"], 0)
        task_gate = optimized_results[0].metadata["token_optimizer"]
        self.assertEqual(task_gate["status"], "considered_not_needed")
        self.assertIn("not used", task_gate["not_used_reason"])
        self.assertIn("500 tokens", task_gate["token_optimizer_status_reason"])
        self.assertEqual(task_gate["summary"]["case_count"], 1)
        self.assertGreater(task_gate["summary"]["without_token_optimizer"], 0)
        self.assertEqual(
            task_gate["summary"]["without_token_optimizer"],
            task_gate["summary"]["with_token_optimizer"],
        )
        self.assertEqual(task_gate["skipped_small_output_count"], 1)

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
                "token_optimizer_provider": "kh",
                "token_optimizer_content_kind": "contract-sensitive",
            },
        )

        self.assertEqual(report["status"], "passthrough")
        self.assertIn("not used", report["not_used_reason"])
        self.assertIn("passed through unchanged", report["token_optimizer_status_reason"])
        self.assertEqual(report["summary"]["case_count"], 1)
        self.assertGreater(report["summary"]["without_token_optimizer"], 0)
        self.assertEqual(report["summary"]["estimated_tokens_saved"], 0)
        task_gate = optimized_results[0].metadata["token_optimizer"]
        self.assertEqual(task_gate["status"], "passthrough")
        self.assertIn("not used", task_gate["not_used_reason"])
        self.assertIn("passed through unchanged", task_gate["token_optimizer_status_reason"])
        self.assertEqual(task_gate["records_count"], 1)
        self.assertEqual(task_gate["summary"]["case_count"], 1)

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
        self.assertIn("not used", report["not_used_reason"])
        self.assertIn("blocked", report["token_optimizer_status_reason"])

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
        self.assertEqual(report["summary"]["case_count"], 1)
        self.assertGreater(report["summary"]["without_token_optimizer"], 0)
        task_gate = optimized_results[0].metadata["token_optimizer"]
        self.assertEqual(task_gate["status"], "blocked")
        self.assertIn("not used", task_gate["not_used_reason"])
        self.assertIn("blocked", task_gate["token_optimizer_status_reason"])
        self.assertEqual(task_gate["records_count"], 1)
        self.assertEqual(task_gate["summary"]["case_count"], 1)


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
