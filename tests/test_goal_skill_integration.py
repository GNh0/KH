import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class GoalSkillIntegrationTests(unittest.TestCase):
    def test_plugin_manifest_exposes_goal_state_capability(self):
        plugin = json.loads(read_text(".codex-plugin/plugin.json"))
        root_manifest = json.loads(read_text("plugin.json"))
        root_skill_names = {skill["name"] for skill in root_manifest["skills"]}

        self.assertIn("Goal State", plugin["interface"]["capabilities"])
        self.assertIn("goal-state-harness", root_skill_names)

    def test_lifecycle_and_router_activate_goal_state_for_implementation(self):
        lifecycle = read_text("skills/development_lifecycle_harness/SKILL.md")
        router = read_text("skills/request_complexity_router/SKILL.md")
        goal = read_text("skills/goal_state_harness/SKILL.md")

        self.assertIn("Create or refresh `GoalState` before implementation", lifecycle)
        self.assertIn("goal-state-harness", lifecycle)
        self.assertIn("Heavy implementation routes should include `goal-state-harness`", router)
        self.assertIn("request-complexity-router", goal)
        self.assertIn("development-lifecycle-harness", goal)

    def test_goal_skill_documents_runtime_claim_and_cross_process_revalidation_boundary(self):
        skill = read_text("skills/goal_state_harness/SKILL.md")
        usage = read_text("skills/goal_state_harness/references/usage.md")

        for content in (skill, usage):
            self.assertIn("same-process runtime claim", content)
            self.assertIn("cross-process", content)
            self.assertIn("external authenticity remains unverified", content)


if __name__ == "__main__":
    unittest.main()
