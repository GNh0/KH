import unittest
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from src.skills.workflow_distiller import (
    build_skill_scaffold,
    should_distill_workflow,
)


class WorkflowDistillerRuntimeTests(unittest.TestCase):
    def test_rejects_one_off_workflow_without_reuse_signal(self):
        result = should_distill_workflow(
            trigger="Fix the typo in one local README",
            repeated_count=1,
            reusable_across_projects=False,
            has_clear_failure_modes=False,
        )

        self.assertFalse(result["should_distill"])
        self.assertIn("one-off", " ".join(result["reasons"]))

    def test_accepts_repeated_workflow_with_clear_trigger_and_failure_modes(self):
        result = should_distill_workflow(
            trigger="Use when a SQL save procedure must preserve pasted column order",
            repeated_count=4,
            reusable_across_projects=True,
            has_clear_failure_modes=True,
        )

        self.assertTrue(result["should_distill"])
        self.assertEqual(result["quality_gate"], "candidate")

    def test_build_skill_scaffold_outputs_required_files(self):
        scaffold = build_skill_scaffold(
            name="sql-save-contract",
            trigger="Use when rewriting SQL save procedures while preserving pasted contracts.",
            workflow_steps=[
                "Collect the pasted procedure and save payload.",
                "Preserve column/value order while formatting.",
                "Verify aliases and audit fields before returning.",
            ],
            implementation_targets=["skills/<skill-name>/SKILL.md"],
        )

        self.assertIn("SKILL.md", scaffold)
        self.assertIn("references/usage.md", scaffold)
        self.assertIn("examples/minimal-workflow.md", scaffold)
        self.assertIn("scripts/smoke_check.py", scaffold)
        self.assertIn("description: Use when rewriting SQL", scaffold["SKILL.md"])
        self.assertIn("## Common mistakes", scaffold["SKILL.md"])

    def test_scaffold_accepts_execution_level_and_resolves_python_targets(self):
        scaffold = build_skill_scaffold(
            name="command-policy-helper",
            trigger="Use when classifying shell commands for guard policy.",
            workflow_steps=["Call the classifier."],
            implementation_targets=["src.skills.command_policy.classify_command"],
            execution_level="python-module",
        )

        self.assertIn("Execution level: `python-module`", scaffold["references/usage.md"])
        self.assertIn("importlib", scaffold["scripts/smoke_check.py"])
        self.assertIn("src.skills.command_policy.classify_command", scaffold["SKILL.md"])

    def test_generated_smoke_check_executes_from_generated_skill_folder(self):
        scaffold = build_skill_scaffold(
            name="command-policy-helper",
            trigger="Use when classifying shell commands for guard policy.",
            workflow_steps=["Call the classifier."],
            implementation_targets=[
                "src.skills.command_policy.classify_command",
                "skills/command_hook_policy_harness/SKILL.md",
            ],
            execution_level="python-module",
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "command-policy-helper"
            for relative_path, content in scaffold.items():
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            env = os.environ.copy()
            env["UAF_REPO_ROOT"] = str(Path.cwd())
            completed = subprocess.run(
                [sys.executable, "scripts/smoke_check.py"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("smoke_check ok", completed.stdout)


if __name__ == "__main__":
    unittest.main()
