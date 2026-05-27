import os
import tempfile
import unittest

from src.skills.antigravity_bridge import collect_reference_skills, read_reference_skill


class AntigravityReferenceTests(unittest.TestCase):
    def test_collect_reference_skills_uses_packaged_uaf_skill_folders(self):
        result = collect_reference_skills()

        self.assertFalse(result["external_runtime_dependency"])
        self.assertTrue(result["packaged_skill_folder_available"])
        self.assertGreaterEqual(result["total_skills_found"], 4)
        self.assertIn("design_references_considered", result["references_considered"])

        names = {skill["name"] for skill in result["skills"]}
        self.assertIn("antigravity-bridge", names)
        self.assertIn("harness-evaluator", names)
        self.assertIn("parallel-orchestration-harness", names)

        for skill in result["skills"]:
            self.assertEqual(skill["source"], "uaf_skill_folder")
            self.assertTrue(skill["packaged"])
            self.assertNotIn("path", skill)

    def test_read_reference_skill_returns_packaged_skill_without_external_files(self):
        content = read_reference_skill("parallel-orchestration-harness")

        self.assertIn("Packaged source: uaf_skill_folder", content)
        self.assertIn("UAF implementation targets", content)
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

            result = collect_reference_skills(skills_dir=temp_dir)

            self.assertTrue(result["packaged_skill_folder_available"])
            self.assertEqual(result["total_skills_found"], 1)
            self.assertEqual(result["skills"][0]["name"], "custom-harness")
            self.assertEqual(result["skills"][0]["relative_path"], "custom_harness/SKILL.md")
            self.assertNotIn("path", result["skills"][0])


if __name__ == "__main__":
    unittest.main()
