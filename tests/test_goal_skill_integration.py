import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class GoalSkillIntegrationTests(unittest.TestCase):
    def test_plugin_prompt_connects_goal_state_to_heavy_work(self):
        plugin = json.loads(read_text(".codex-plugin/plugin.json"))
        prompts = "\n".join(plugin["interface"]["defaultPrompt"])

        self.assertIn("For heavy, multi-step, or evidence-gated work", prompts)
        self.assertIn("create or update KH GoalState before execution", prompts)
        self.assertIn("Keep the goal ledger updated", prompts)

    def test_lifecycle_and_router_activate_goal_state_for_implementation(self):
        lifecycle = read_text("skills/development_lifecycle_harness/SKILL.md")
        router = read_text("skills/request_complexity_router/SKILL.md")
        goal = read_text("skills/goal_state_harness/SKILL.md")

        self.assertIn("Create or refresh `GoalState` before implementation", lifecycle)
        self.assertIn("goal-state-harness", lifecycle)
        self.assertIn("Heavy implementation routes should include `goal-state-harness`", router)
        self.assertIn("request-complexity-router", goal)
        self.assertIn("development-lifecycle-harness", goal)


if __name__ == "__main__":
    unittest.main()
