import tempfile
import unittest
from pathlib import Path

from src.core.architect import SystemArchitect
from src.skills.license_checker import check_license
from src.skills.pattern_analyzer import analyze_design_pattern
from src.skills.token_optimizer import minify_code, truncate_logs


class FakeLLMRouter:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        self.calls.append((system_prompt, user_prompt))
        return self.response


class BuiltinSkillRuntimeTests(unittest.TestCase):
    def test_system_architect_writes_design_doc_and_functional_spec_csv(self):
        llm = FakeLLMRouter(
            "```csv\n"
            "ID,Category,Feature,Description\n"
            "F-001,Work,Dashboard,Display work status\n"
            "```"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            result_path = SystemArchitect(str(path), llm).draft_architecture(
                requirements="Work status dashboard",
                framework="winforms",
                libraries=[],
            )

            design_doc = Path(result_path)
            functional_spec = path / "functional_spec.csv"

            self.assertTrue(design_doc.exists())
            self.assertTrue(functional_spec.exists())
            self.assertIn("System Architecture", design_doc.read_text(encoding="utf-8"))
            self.assertIn("F-001", functional_spec.read_text(encoding="utf-8-sig"))
            self.assertTrue(llm.calls)

    def test_design_pattern_skill_selects_winforms_mvp_for_large_work(self):
        result = analyze_design_pattern(
            framework="winforms",
            project_scale="large",
            maintainability_priority="high",
        )

        self.assertIn("MVP", result)
        self.assertIn("maintainability", result)

    def test_license_checker_rejects_unsafe_package_names(self):
        result = check_license("../secret", registry="pypi")

        self.assertIn("Security Error", result)

    def test_license_checker_supports_non_network_mock_registry_path(self):
        result = check_license("demo_package", registry="internal")

        self.assertIn("MIT License", result)
        self.assertIn("demo_package", result)

    def test_minify_code_removes_docstrings_but_preserves_logic(self):
        source = '''
"""module docs"""

def add_one(value):
    """function docs"""
    # comment
    return value + 1
'''

        result = minify_code(source)

        self.assertNotIn("module docs", result)
        self.assertNotIn("function docs", result)
        self.assertIn("return value + 1", result)

    def test_truncate_logs_keeps_head_and_tail(self):
        log = "\n".join(f"line-{index}" for index in range(20))

        result = truncate_logs(log, max_lines=6)

        self.assertIn("line-0", result)
        self.assertIn("line-19", result)
        self.assertIn("token optimized", result)
        self.assertNotIn("line-10\nline-11", result)

    def test_truncate_logs_preserves_failure_context_from_middle(self):
        lines = [f"setup-line-{index}" for index in range(80)]
        lines.extend(
            [
                "FAILED tests/test_token_optimizer.py::test_keeps_context",
                "Traceback (most recent call last):",
                "  File \"src/skills/token_optimizer.py\", line 44, in truncate_logs",
                "ValueError: important middle failure",
                "exit code: 1",
            ]
        )
        lines.extend(f"tail-line-{index}" for index in range(80))
        log = "\n".join(lines)

        result = truncate_logs(log, max_lines=20)

        self.assertIn("FAILED tests/test_token_optimizer.py::test_keeps_context", result)
        self.assertIn("ValueError: important middle failure", result)
        self.assertIn("exit code: 1", result)
        self.assertIn("token optimized", result)
        self.assertLessEqual(len(result.splitlines()), 32)


if __name__ == "__main__":
    unittest.main()
