import unittest
import subprocess
import sys

from src.skills.uaf_skill_audit import (
    PROJECT_ROOT,
    _test_evidence_for_target,
    audit_packaged_skills,
    extract_implementation_targets,
)


class UafSkillAuditTests(unittest.TestCase):
    def test_extract_implementation_targets_reads_backticked_refs(self):
        content = """
# Demo

## UAF implementation targets

- `src.skills.uaf_skill_catalog`
- `skills/<skill-name>/SKILL.md`

## Common mistakes
"""

        self.assertEqual(
            extract_implementation_targets(content),
            ["src.skills.uaf_skill_catalog", "skills/<skill-name>/SKILL.md"],
        )

    def test_audit_reports_every_packaged_skill(self):
        report = audit_packaged_skills()
        expected_count = report["total_skills"]

        self.assertGreaterEqual(expected_count, 40)
        self.assertEqual(report["total_skills"], expected_count)
        self.assertEqual(len(report["skills"]), expected_count)
        self.assertEqual(sum(report["execution_levels"].values()), expected_count)

    def test_audit_resolves_all_non_template_targets(self):
        report = audit_packaged_skills()
        unresolved = [
            (skill["name"], target["ref"], target["status"])
            for skill in report["skills"]
            for target in skill["targets"]
            if target["status"] not in {"resolved", "template"}
        ]

        self.assertEqual(unresolved, [])

    def test_executable_skills_have_test_evidence(self):
        report = audit_packaged_skills()
        missing = [
            skill["name"]
            for skill in report["skills"]
            if skill["execution_level"] in {"python-module", "hybrid-harness"}
            and not skill["has_test_evidence"]
        ]

        self.assertEqual(missing, [])

    def test_skill_md_stem_does_not_count_as_test_evidence(self):
        target = {
            "ref": "skills/example_harness/SKILL.md",
            "status": "resolved",
            "path": str(PROJECT_ROOT / "skills" / "example_harness" / "SKILL.md"),
        }
        test_index = {
            "tests/test_example.py": "This test mentions SKILL.md and skill folders generically.",
            "tests/test_fixture_only.py": "fixture = 'skills/example_harness/SKILL.md'",
            "tests/test_real_path.py": "self.assertIn('skills/example_harness/SKILL.md', resolved_paths)",
        }

        evidence = _test_evidence_for_target(target["ref"], target, test_index)

        self.assertEqual(evidence, ["tests/test_real_path.py"])

    def test_audit_success_requires_no_unresolved_targets_or_missing_executable_evidence(self):
        report = audit_packaged_skills()

        self.assertTrue(report["success"], report)

    def test_module_help_does_not_run_full_audit(self):
        completed = subprocess.run(
            [sys.executable, "-m", "src.skills.uaf_skill_audit", "--help"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--summary", completed.stdout)
        self.assertNotIn('"skills"', completed.stdout)

    def test_missing_skill_filter_fails_clearly(self):
        completed = subprocess.run(
            [sys.executable, "-m", "src.skills.uaf_skill_audit", "--skill", "does-not-exist", "--summary"],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("skill not found", completed.stdout)


if __name__ == "__main__":
    unittest.main()
