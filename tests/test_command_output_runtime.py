import unittest
import subprocess
import sys
import tempfile
from pathlib import Path

from src.skills.token_optimizer import (
    aggregate_token_usage_stats,
    compare_token_usage,
    minify_code,
    optimize_context_content,
    summarize_command_output,
    summarize_agent_transcript,
    truncate_logs,
)


class CommandOutputRuntimeTests(unittest.TestCase):
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

    def test_aggregate_token_usage_stats_summarizes_multiple_records(self):
        records = [
            compare_token_usage("a " * 200, "a " * 20, strategy="command-output", label="log"),
            compare_token_usage("def run():\n    return 1\n" * 30, "def run():\n return 1\n", strategy="minify-code", label="code"),
        ]

        summary = aggregate_token_usage_stats(records)

        self.assertEqual(summary["case_count"], 2)
        self.assertGreater(summary["without_token_optimizer"], summary["with_token_optimizer"])
        self.assertGreater(summary["estimated_tokens_saved"], 0)
        self.assertIn("command-output", summary["by_strategy"])
        self.assertIn("minify-code", summary["by_strategy"])

    def test_agent_transcript_summary_preserves_lifecycle_quality_evidence(self):
        transcript = _agent_lifecycle_transcript()

        result = summarize_agent_transcript(transcript, max_lines=24, label="pipepilot-task-loop")

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["strategy"], "agent-transcript")
        self.assertGreater(result.metadata["token_usage"]["estimated_tokens_saved"], 0)
        self.assertGreater(result.metadata["token_usage"]["token_savings_ratio"], 0.7)
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
