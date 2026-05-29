import os
import json
import importlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.skills.uaf_skill_catalog import (
    _validated_execution_levels,
    collect_packaged_skills,
    read_packaged_skill,
)


CORE_SKILLS = {
    "adapter-contract-harness",
    "artifact-render-qa-harness",
    "architect-pipeline",
    "command-hook-policy-harness",
    "development-lifecycle-harness",
    "deliverable-template-quality-harness",
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
    "role-execution-audit-harness",
    "quality-gates-harness",
    "qa-gate-harness",
    "review-gate-harness",
    "request-complexity-router",
    "command-output-harness",
    "skill-catalog",
    "snapshot-state-harness",
    "subagent-review-pipeline",
    "traceability-matrix-harness",
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

    def test_catalog_declares_harness_execution_levels(self):
        result = collect_packaged_skills()
        allowed = {"python-module", "hybrid-harness", "procedure-policy"}
        levels = {skill["execution_level"] for skill in result["skills"]}

        self.assertTrue(levels.issubset(allowed))
        self.assertIn("python-module", levels)
        self.assertIn("procedure-policy", levels)
        self.assertIn("execution_levels", result)
        self.assertEqual(sum(result["execution_levels"].values()), len(CORE_SKILLS))

        skill_catalog = next(skill for skill in result["skills"] if skill["name"] == "skill-catalog")
        command_policy = next(skill for skill in result["skills"] if skill["name"] == "command-hook-policy-harness")
        self.assertEqual(skill_catalog["execution_level"], "python-module")
        self.assertEqual(command_policy["execution_level"], "python-module")

    def test_catalog_has_execution_level_for_every_packaged_skill(self):
        result = collect_packaged_skills()
        levels = _validated_execution_levels()
        names = {skill["name"] for skill in result["skills"]}

        self.assertEqual(set(levels).intersection(names), names)

    def test_packaged_skill_targets_resolve_to_repo_code(self):
        for skill_dir in sorted(Path("skills").iterdir(), key=lambda path: path.name):
            if not skill_dir.is_dir():
                continue
            content = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            target_section = content.split("## UAF implementation targets", 1)[1]
            target_section = target_section.split("\n## ", 1)[0]
            code_refs = re.findall(r"`([^`]+)`", target_section)

            with self.subTest(skill=skill_dir.name):
                self.assertTrue(code_refs, f"{skill_dir} has no code references")
                for ref in code_refs:
                    if "<" in ref or ">" in ref:
                        continue
                    if ref.startswith(("src.", "tests.")):
                        self.assert_importable_ref(ref)
                    elif ref.startswith("skills/"):
                        self.assertTrue(Path(ref).exists(), ref)

    def assert_importable_ref(self, ref: str) -> None:
        parts = ref.split(".")
        last_error = None
        for index in range(len(parts), 0, -1):
            module_name = ".".join(parts[:index])
            try:
                module = importlib.import_module(module_name)
            except ModuleNotFoundError as exc:
                if exc.name != module_name:
                    raise
                last_error = exc
                continue

            current = module
            for attr in parts[index:]:
                self.assertTrue(hasattr(current, attr), f"{ref} missing attribute {attr}")
                current = getattr(current, attr)
            return

        self.fail(f"{ref} could not be imported: {last_error}")

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
            "request-complexity-router": "Request complexity",
        }

        for skill_name, source_label in expected_sources.items():
            with self.subTest(skill_name=skill_name):
                content = read_packaged_skill(skill_name)

                self.assertIn("Packaged source: uaf_skill_folder", content)
                self.assertIn("External runtime dependency: false", content)
                self.assertIn("UAF implementation targets", content)
                self.assertIn(source_label, content)
                self.assertNotIn(r"C:\Users\KONEIT\.gemini", content)

    def test_quality_improvement_harnesses_are_packaged(self):
        expected_targets = {
            "deliverable-template-quality-harness": "evaluate_deliverable_quality",
            "artifact-render-qa-harness": "evaluate_deliverable_quality",
            "traceability-matrix-harness": "build_traceability_matrix_rows",
            "role-execution-audit-harness": "audit_role_execution",
        }

        for skill_name, target in expected_targets.items():
            with self.subTest(skill_name=skill_name):
                content = read_packaged_skill(skill_name)

                self.assertIn("Packaged source: uaf_skill_folder", content)
                self.assertIn("External runtime dependency: false", content)
                self.assertIn("UAF implementation targets", content)
                self.assertIn("src.orchestration.quality_harnesses", content)
                self.assertIn(target, content)

    def test_skills_folder_makes_new_harness_easy_to_add(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = os.path.join(temp_dir, "custom_harness")
            os.makedirs(skill_dir)
            with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as handle:
                handle.write(
                    "---\n"
                    "name: custom-harness\n"
                    "description: Use when testing custom portable harness loading.\n"
                    "---\n"
                    "# Custom Harness\n"
                    "\n"
                    "## Workflow\n"
                    "\n"
                    "1. Load the custom harness.\n"
                    "\n"
                    "## UAF implementation targets\n"
                    "- src.skills.uaf_skill_catalog\n"
                )

            result = collect_packaged_skills(skills_dir=temp_dir)

            self.assertTrue(result["packaged_skill_folder_available"])
            self.assertEqual(result["total_skills_found"], 1)
            self.assertEqual(result["skills"][0]["name"], "custom-harness")
            self.assertEqual(result["skills"][0]["relative_path"], "custom_harness/SKILL.md")
            self.assertNotIn("path", result["skills"][0])


if __name__ == "__main__":
    unittest.main()
