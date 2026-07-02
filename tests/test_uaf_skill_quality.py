import subprocess
import sys
import unittest
from pathlib import Path

from src.skills.uaf_skill_quality import audit_skill_packaging_quality


class UafSkillQualityTests(unittest.TestCase):
    def test_repository_skills_have_science_style_support_files(self):
        report = audit_skill_packaging_quality(run_smoke_scripts=True)

        self.assertEqual(report["total_skills"], 42)
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

    def test_every_skill_has_minimum_runtime_quality_score(self):
        report = audit_skill_packaging_quality(run_smoke_scripts=True)
        low_quality = [
            {
                "name": skill["name"],
                "score": skill["quality_score"],
                "rating": skill["quality_rating"],
                "gaps": skill["quality_gaps"],
            }
            for skill in report["skills"]
            if skill["quality_score"] < 8.0
        ]

        self.assertEqual(low_quality, [])

    def test_core_runtime_harnesses_score_at_least_nine(self):
        report = audit_skill_packaging_quality(run_smoke_scripts=True)
        low_core = [
            {
                "name": skill["name"],
                "score": skill["quality_score"],
                "rating": skill["quality_rating"],
                "gaps": skill["quality_gaps"],
            }
            for skill in report["skills"]
            if skill["name"] in report["core_production_skills"]
            if skill["quality_score"] < 9.0
        ]

        self.assertEqual(low_core, [])

    def test_quality_cli_help_does_not_run_full_audit(self):
        completed = subprocess.run(
            [sys.executable, "-m", "src.skills.uaf_skill_quality", "--help"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0)
        self.assertIn("usage:", completed.stdout.lower())
        self.assertNotIn('"skills": [', completed.stdout)


if __name__ == "__main__":
    unittest.main()
