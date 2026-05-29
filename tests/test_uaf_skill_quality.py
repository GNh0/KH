import subprocess
import sys
import unittest
from pathlib import Path

from src.skills.uaf_skill_quality import audit_skill_packaging_quality


class UafSkillQualityTests(unittest.TestCase):
    def test_repository_skills_have_science_style_support_files(self):
        report = audit_skill_packaging_quality(run_smoke_scripts=True)

        self.assertEqual(report["total_skills"], 27)
        self.assertTrue(report["success"], report)
        self.assertTrue(report["smoke_scripts_executed"])
        self.assertTrue(
            all(skill["smoke_execution"]["success"] for skill in report["skills"]),
            report,
        )

    def test_support_files_are_wired_from_skill_md(self):
        report = audit_skill_packaging_quality()
        missing = [
            (skill["name"], issue["code"], issue["path"])
            for skill in report["skills"]
            for issue in skill["issues"]
            if issue["code"] in {
                "missing_support_file",
                "support_file_not_referenced",
            }
        ]

        self.assertEqual(missing, [])

    def test_skill_smoke_scripts_are_parseable(self):
        report = audit_skill_packaging_quality()
        syntax_issues = [
            (skill["name"], issue["message"])
            for skill in report["skills"]
            for issue in skill["issues"]
            if issue["code"] == "smoke_script_syntax_error"
        ]

        self.assertEqual(syntax_issues, [])

    def test_packaged_skill_smoke_scripts_run(self):
        for script_path in sorted(Path("skills").glob("*/scripts/smoke_check.py")):
            with self.subTest(script=str(script_path)):
                completed = subprocess.run(
                    [sys.executable, str(script_path.resolve())],
                    cwd=script_path.parents[1],
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
