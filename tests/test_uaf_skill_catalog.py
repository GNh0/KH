import os
import tempfile
import unittest

from src.skills.uaf_skill_catalog import collect_packaged_skills, read_packaged_skill


CORE_SKILLS = {
    "adapter-contract-harness",
    "antigravity-agent-orchestration",
    "architect-pipeline",
    "command-hook-policy-harness",
    "development-lifecycle-harness",
    "harness-evaluator",
    "parallel-orchestration-harness",
    "quality-gates-harness",
    "rtk-command-output-harness",
    "skill-catalog",
    "subagent-review-pipeline",
    "token-optimizer",
    "workflow-skill-distiller",
}

REMOVED_EXAMPLE_SKILLS = {
    "android-cli-harness",
    "browser-devtools-harness",
    "firebase-project-harness",
    "license-policy-gate",
    "modern-web-quality-harness",
    "science-api-wrapper-harness",
    "antigravity-bridge",
}


class UafSkillCatalogTests(unittest.TestCase):
    def test_catalog_contains_only_core_uaf_skill_folders(self):
        result = collect_packaged_skills()

        self.assertFalse(result["external_runtime_dependency"])
        self.assertTrue(result["packaged_skill_folder_available"])
        self.assertEqual(result["total_skills_found"], len(CORE_SKILLS))

        names = {skill["name"] for skill in result["skills"]}
        self.assertEqual(names, CORE_SKILLS)
        self.assertTrue(names.isdisjoint(REMOVED_EXAMPLE_SKILLS))

        for skill in result["skills"]:
            self.assertEqual(skill["source"], "uaf_skill_folder")
            self.assertTrue(skill["packaged"])
            self.assertNotIn("path", skill)

    def test_read_packaged_skill_returns_skill_folder_content(self):
        content = read_packaged_skill("parallel-orchestration-harness")

        self.assertIn("Packaged source: uaf_skill_folder", content)
        self.assertIn("UAF implementation targets", content)
        self.assertNotIn(r"C:\Users\KONEIT\.gemini", content)

    def test_reference_derived_harnesses_are_uaf_native(self):
        expected_sources = {
            "antigravity-agent-orchestration": "Google Antigravity SDK",
            "development-lifecycle-harness": "Superpowers",
            "subagent-review-pipeline": "Superpowers",
            "quality-gates-harness": "Superpowers",
            "rtk-command-output-harness": "RTK",
            "command-hook-policy-harness": "RTK",
        }

        for skill_name, source_label in expected_sources.items():
            with self.subTest(skill_name=skill_name):
                content = read_packaged_skill(skill_name)

                self.assertIn("Packaged source: uaf_skill_folder", content)
                self.assertIn("External runtime dependency: false", content)
                self.assertIn("UAF implementation targets", content)
                self.assertIn(source_label, content)
                self.assertNotIn(r"C:\Users\KONEIT\.gemini", content)

    def test_skills_folder_makes_new_harness_easy_to_add(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = os.path.join(temp_dir, "custom_harness")
            os.makedirs(skill_dir)
            with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as handle:
                handle.write(
                    "---\n"
                    "name: custom-harness\n"
                    "description: Custom portable harness.\n"
                    "---\n"
                    "# Custom Harness\n"
                    "\n"
                    "## UAF implementation targets\n"
                    "- src.skills.custom_harness\n"
                )

            result = collect_packaged_skills(skills_dir=temp_dir)

            self.assertTrue(result["packaged_skill_folder_available"])
            self.assertEqual(result["total_skills_found"], 1)
            self.assertEqual(result["skills"][0]["name"], "custom-harness")
            self.assertEqual(result["skills"][0]["relative_path"], "custom_harness/SKILL.md")
            self.assertNotIn("path", result["skills"][0])


if __name__ == "__main__":
    unittest.main()
