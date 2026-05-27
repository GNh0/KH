import os
import json
import subprocess
import sys
import tempfile
import unittest

from src.skills.uaf_skill_catalog import collect_packaged_skills, read_packaged_skill


CORE_SKILLS = {
    "adapter-contract-harness",
    "architect-pipeline",
    "command-hook-policy-harness",
    "development-lifecycle-harness",
    "context-state-harness",
    "domain-orchestration-harness",
    "goal-state-harness",
    "guard-policy-harness",
    "harness-evaluator",
    "health-check-harness",
    "host-agent-orchestration",
    "memory-state-harness",
    "orchestration-role-graph",
    "parallel-orchestration-harness",
    "quality-gates-harness",
    "qa-gate-harness",
    "review-gate-harness",
    "command-output-harness",
    "skill-catalog",
    "snapshot-state-harness",
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

    def test_catalog_includes_validation_summary(self):
        result = collect_packaged_skills()

        self.assertIn("validation", result)
        self.assertTrue(result["validation"]["success"], result["validation"])
        self.assertEqual(result["validation"]["total_skills"], len(CORE_SKILLS))
        self.assertEqual(result["validation"]["invalid_skills"], 0)

    def test_check_command_outputs_validation_json(self):
        completed = subprocess.run(
            [sys.executable, "-m", "src.skills.uaf_skill_catalog", "--check"],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        data = json.loads(completed.stdout)
        self.assertTrue(data["success"], data)
        self.assertEqual(data["invalid_skills"], 0)

    def test_read_packaged_skill_returns_skill_folder_content(self):
        content = read_packaged_skill("parallel-orchestration-harness")

        self.assertIn("Packaged source: uaf_skill_folder", content)
        self.assertIn("UAF implementation targets", content)
        self.assertNotIn(r"C:\Users\KONEIT\.gemini", content)

    def test_snapshot_state_harness_is_packaged(self):
        content = read_packaged_skill("snapshot-state-harness")

        self.assertIn("Packaged source: uaf_skill_folder", content)
        self.assertIn("src.core.snapshot_manager", content)
        self.assertIn("commit", content)
        self.assertIn("rollback", content)

    def test_reference_derived_harnesses_are_uaf_native(self):
        expected_sources = {
            "development-lifecycle-harness": "Personal skillbook",
            "domain-orchestration-harness": "domain orchestration",
            "host-agent-orchestration": "host orchestration",
            "subagent-review-pipeline": "Personal subagent",
            "quality-gates-harness": "Personal quality",
            "command-output-harness": "command output",
            "command-hook-policy-harness": "Command hook",
            "orchestration-role-graph": "CEO",
            "review-gate-harness": "Review workflow",
            "qa-gate-harness": "QA workflow",
            "context-state-harness": "Context workflow",
            "goal-state-harness": "GoalState",
            "guard-policy-harness": "Guard workflow",
            "health-check-harness": "Health workflow",
            "memory-state-harness": "persistent memory",
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
