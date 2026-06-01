import sys
import tempfile
import unittest
from pathlib import Path

from src.tasks.checks import (
    CommandCheckInput,
    CommandCheckRunner,
    command_check_presets,
)


class CommandCheckRunnerTests(unittest.TestCase):
    def test_command_check_runner_emits_passed_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            check = CommandCheckInput(
                project_dir=str(project_dir),
                command=[sys.executable, "-c", "print('ok')"],
                evidence_key="unit tests passed",
            )

            result = CommandCheckRunner().run(check)

        self.assertEqual(result.source, "command")
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.evidence, ["unit tests passed"])
        self.assertEqual(result.metadata["exit_code"], 0)
        self.assertEqual(result.metadata["stdout"].strip(), "ok")

    def test_command_check_runner_does_not_emit_evidence_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            check = CommandCheckInput(
                project_dir=str(project_dir),
                command=[sys.executable, "-c", "import sys; print('bad'); sys.exit(2)"],
                evidence_key="unit tests passed",
            )

            result = CommandCheckRunner().run(check)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.evidence, [])
        self.assertEqual(result.metadata["exit_code"], 2)
        self.assertEqual(result.metadata["stdout"].strip(), "bad")

    def test_command_check_runner_rejects_missing_project_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_dir = Path(tmp) / "missing"
            check = CommandCheckInput(
                project_dir=str(missing_dir),
                command=[sys.executable, "-c", "print('never')"],
                evidence_key="unit tests passed",
            )

            result = CommandCheckRunner().run(check)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.evidence, [])
        self.assertEqual(result.metadata["error_type"], "ValueError")

    def test_command_check_presets_expand_known_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()

            checks = command_check_presets(
                project_dir=str(project_dir),
                preset_names=["plugin-json", "python-compile"],
            )

        self.assertEqual([check.evidence_key for check in checks], [
            "plugin json valid",
            "python compile passed",
        ])
        self.assertEqual(checks[0].command[:3], [sys.executable, "-m", "json.tool"])
        self.assertEqual(checks[1].command[:3], [sys.executable, "-B", "-c"])

    def test_unknown_command_check_preset_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                command_check_presets(
                    project_dir=tmp,
                    preset_names=["unknown-check"],
                )


if __name__ == "__main__":
    unittest.main()
