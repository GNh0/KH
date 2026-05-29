import os
import tempfile
import unittest

from src.contracts import HarnessResult
from src.harness.evaluator import Evaluator
from src.harness.sandbox import CodeSandbox, set_allowed_workspace


class SandboxTests(unittest.TestCase):
    def test_evaluator_allows_safe_functions_and_harmless_output_text(self):
        result = Evaluator(timeout=2).evaluate_code(
            "def add(a, b):\n    return a + b",
            "assert add(2, 3) == 5\nprint('eval ok')",
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["stderr"], "")
        self.assertIn("eval ok", result["stdout"])

    def test_evaluator_allows_utf8_sig_fragments_from_windows_files(self):
        result = Evaluator(timeout=2).evaluate_code(
            "\ufeffdef add(a, b):\n    return a + b",
            "\ufeffassert add(2, 3) == 5\nprint('windows utf8 ok')",
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["stderr"], "")
        self.assertIn("windows utf8 ok", result["stdout"])

    def test_run_python_code_blocks_dangerous_builtin_calls(self):
        result = CodeSandbox(timeout=2).run_python_code("eval('1 + 1')")

        self.assertFalse(result["success"])
        self.assertEqual(result["exit_code"], -1)
        self.assertIn("Security Error", result["stderr"])

    def test_run_python_code_reports_runtime_errors(self):
        result = CodeSandbox(timeout=2).run_python_code("raise ValueError('boom')")

        self.assertFalse(result["success"])
        self.assertNotEqual(result["exit_code"], 0)
        self.assertIn("ValueError", result["stderr"])
        self.assertIn("boom", result["stderr"])

    def test_run_python_code_result_returns_contract_object(self):
        result = CodeSandbox(timeout=2).run_python_code_result("print('ok')")

        self.assertIsInstance(result, HarnessResult)
        self.assertTrue(result.success)
        self.assertEqual(result.stdout, "ok\n")

    def test_cleanup_workspace_temps_removes_tmp_files(self):
        with tempfile.TemporaryDirectory() as workspace:
            temp_path = os.path.join(workspace, "generated.tmp")
            with open(temp_path, "w", encoding="utf-8") as handle:
                handle.write("temporary")

            set_allowed_workspace(workspace)
            CodeSandbox().cleanup_workspace_temps()

            self.assertFalse(os.path.exists(temp_path))

    def test_write_file_rejects_prefix_sibling_workspace(self):
        with tempfile.TemporaryDirectory() as parent:
            allowed = os.path.join(parent, "app")
            sibling = os.path.join(parent, "app_evil", "escape.txt")
            os.makedirs(allowed)

            set_allowed_workspace(allowed)

            with self.assertRaises(PermissionError):
                CodeSandbox().write_file(sibling, "nope")


if __name__ == "__main__":
    unittest.main()
