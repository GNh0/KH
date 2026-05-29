import unittest

from src.skills.uaf_skill_audit import audit_packaged_skills, extract_implementation_targets


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

        self.assertEqual(report["total_skills"], 27)
        self.assertEqual(len(report["skills"]), 27)
        self.assertEqual(sum(report["execution_levels"].values()), 27)

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

    def test_audit_success_requires_no_unresolved_targets_or_missing_executable_evidence(self):
        report = audit_packaged_skills()

        self.assertTrue(report["success"], report)


if __name__ == "__main__":
    unittest.main()
