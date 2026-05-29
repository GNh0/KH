import os
import tempfile
import unittest

from src.skills.uaf_skill_validator import validate_skill_folders


def write_skill(root: str, folder: str, content: str) -> None:
    skill_dir = os.path.join(root, folder)
    os.makedirs(skill_dir)
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as handle:
        handle.write(content)


VALID_SKILL = """---
name: valid-harness
description: Use when validating a UAF harness.
---

# Valid Harness

## Workflow

1. Do the work.

## UAF implementation targets

- src.skills.valid_harness
"""


class UafSkillValidatorTests(unittest.TestCase):
    def test_repository_packaged_skills_validate_successfully(self):
        report = validate_skill_folders()

        self.assertTrue(report.success, report.to_dict())
        self.assertEqual(report.invalid_skills, 0)

    def test_repository_packaged_skills_have_operational_quality_sections(self):
        report = validate_skill_folders()

        self.assertTrue(report.success, report.to_dict())
        for result in report.results:
            with self.subTest(skill=result.name):
                issue_codes = {issue.code for issue in result.issues}
                self.assertNotIn("missing_required_outputs", issue_codes)
                self.assertNotIn("missing_common_mistakes", issue_codes)
        self.assertGreater(report.valid_skills, 0)

    def test_missing_frontmatter_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_skill(
                temp_dir,
                "broken",
                "# Broken\n\n## UAF implementation targets\n\n- src.skills.broken\n",
            )

            report = validate_skill_folders(skills_dir=temp_dir)

        self.assertFalse(report.success)
        self.assertIn("missing_frontmatter", {issue.code for issue in report.issues})

    def test_description_must_be_trigger_focused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_skill(
                temp_dir,
                "description",
                VALID_SKILL.replace(
                    "description: Use when validating a UAF harness.",
                    "description: Valid UAF harness.",
                ),
            )

            report = validate_skill_folders(skills_dir=temp_dir)

        self.assertFalse(report.success)
        self.assertIn("description_not_trigger_focused", {issue.code for issue in report.issues})

    def test_missing_behavior_section_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_skill(
                temp_dir,
                "behavior",
                VALID_SKILL.replace("## Workflow\n\n1. Do the work.\n\n", ""),
            )

            report = validate_skill_folders(skills_dir=temp_dir)

        self.assertFalse(report.success)
        self.assertIn("missing_behavior_section", {issue.code for issue in report.issues})

    def test_duplicate_skill_names_are_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_skill(temp_dir, "one", VALID_SKILL)
            write_skill(temp_dir, "two", VALID_SKILL)

            report = validate_skill_folders(skills_dir=temp_dir)

        self.assertFalse(report.success)
        self.assertIn("duplicate_name", {issue.code for issue in report.issues})

    def test_missing_uaf_targets_section_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_skill(
                temp_dir,
                "missing_targets",
                "---\n"
                "name: missing-targets\n"
                "description: Missing targets.\n"
                "---\n"
                "\n"
                "# Missing Targets\n",
            )

            report = validate_skill_folders(skills_dir=temp_dir)

        self.assertFalse(report.success)
        self.assertIn("missing_uaf_targets", {issue.code for issue in report.issues})

    def test_unresolved_template_placeholder_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            write_skill(
                temp_dir,
                "placeholder",
                VALID_SKILL.replace("Do the work.", "Run {{COMMAND_REFERENCE}}."),
            )

            report = validate_skill_folders(skills_dir=temp_dir)

        self.assertFalse(report.success)
        self.assertIn("unresolved_placeholder", {issue.code for issue in report.issues})


if __name__ == "__main__":
    unittest.main()
