import unittest
import json
from pathlib import Path

from src.orchestration.plugin_composition import compose_plugin_route


class PluginCompositionPolicyTests(unittest.TestCase):
    def test_light_question_ignores_provider_self_forcing(self):
        decision = compose_plugin_route(
            "What is PER?",
            providers=[
                {
                    "provider_id": "aggressive-methodology",
                    "capabilities": ["planning_methodology", "tdd_review"],
                    "self_forcing_rules": ["MUST use this before any question"],
                }
            ],
        )

        self.assertEqual(decision.route, "direct")
        self.assertEqual(decision.controller.provider_id, "none")
        self.assertIn("aggressive-methodology", decision.ignored_self_forcing)
        self.assertEqual(decision.assistants, [])

    def test_heavy_work_composes_controller_and_specialist_assistants(self):
        decision = compose_plugin_route(
            "Build a SaaS dashboard, verify the browser screen, and prepare the PR.",
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": [
                        "workflow_control",
                        "memory_goal_resume",
                        "domain_orchestration",
                        "tdd_review",
                    ],
                },
                {
                    "provider_id": "visual-checker",
                    "capabilities": ["browser_qa", "screenshot"],
                },
                {
                    "provider_id": "repo-service",
                    "capabilities": ["repo_pr_ci"],
                },
            ],
        )

        self.assertEqual(decision.route, "hybrid")
        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertEqual(
            {(assistant.provider_id, assistant.capability) for assistant in decision.assistants},
            {("visual-checker", "browser_qa"), ("repo-service", "repo_pr_ci")},
        )
        self.assertFalse(decision.ask_user)
        self.assertEqual(decision.conflict_policy, "delegated_scope")

    def test_generic_browser_word_routes_as_specialist_not_controller(self):
        decision = compose_plugin_route(
            "Build a SaaS dashboard, verify the browser screen, and prepare the PR.",
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": ["workflow_control", "memory_goal_resume", "tdd_review"],
                },
                {
                    "provider_id": "browser",
                    "capabilities": ["browser_qa"],
                },
                {
                    "provider_id": "repo-service",
                    "capabilities": ["repo_pr_ci"],
                },
            ],
        )

        self.assertEqual(decision.route, "hybrid")
        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertFalse(decision.explicit_user_request)
        self.assertIn(
            ("browser", "browser_qa"),
            {(role.provider_id, role.capability) for role in decision.assistants},
        )

    def test_existing_superpowers_project_can_continue_without_kh_forcing(self):
        decision = compose_plugin_route(
            "Continue the current implementation plan.",
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": ["workflow_control", "memory_goal_resume"],
                },
                {
                    "provider_id": "superpowers",
                    "capabilities": ["planning_methodology", "tdd_review", "worktree"],
                    "self_forcing_rules": ["MUST use for creative work"],
                },
            ],
            context={"project_markers": [".superpowers"]},
        )

        self.assertEqual(decision.controller.provider_id, "superpowers")
        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.ignored_self_forcing, [])
        self.assertIn("project_context:superpowers", decision.reasons)

    def test_future_provider_can_be_controller_when_it_has_matching_capabilities(self):
        decision = compose_plugin_route(
            "Implement the workflow and prove it with tests.",
            providers=[
                {
                    "provider_id": "future-uaf",
                    "capabilities": ["workflow_control", "tdd_review"],
                }
            ],
        )

        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.controller.provider_id, "future-uaf")
        self.assertIn("capability:workflow_control", decision.reasons)

    def test_missing_specialist_provider_records_fallback_without_blocking_controller(self):
        decision = compose_plugin_route(
            "Build a local web app and verify the browser screen.",
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": ["workflow_control", "memory_goal_resume", "tdd_review"],
                }
            ],
        )

        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertEqual(decision.route, "single")
        self.assertEqual(decision.unavailable_capabilities["browser_qa"], "manual_qa_evidence")

    def test_short_specialist_terms_do_not_match_inside_ordinary_words(self):
        decision = compose_plugin_route(
            "Build a project planning helper.",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "repo-service", "capabilities": ["repo_pr_ci"]},
            ],
        )

        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertEqual(decision.assistants, [])

    def test_short_provider_ids_do_not_match_inside_ordinary_words(self):
        for text in ["Prepare a project plan.", "Create a proper design plan."]:
            with self.subTest(text=text):
                decision = compose_plugin_route(
                    text,
                    providers=[
                        {"provider_id": "kh", "capabilities": ["workflow_control"]},
                        {"provider_id": "pr", "capabilities": ["repo_pr_ci"]},
                        {"provider_id": "pro", "capabilities": ["planning_methodology"]},
                    ],
                )

                self.assertEqual(decision.route, "direct")
                self.assertEqual(decision.controller.provider_id, "none")
                self.assertFalse(decision.explicit_user_request)

    def test_explicit_user_provider_request_takes_precedence(self):
        decision = compose_plugin_route(
            "Superpowers로 이어서 해줘",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control"]},
                {"provider_id": "superpowers", "capabilities": ["planning_methodology"]},
            ],
        )

        self.assertEqual(decision.controller.provider_id, "superpowers")
        self.assertIn("explicit_user_request:superpowers", decision.reasons)

    def test_unavailable_explicit_provider_is_reported_before_fallback(self):
        decision = compose_plugin_route(
            "Use Superpowers to build a SaaS app.",
            providers=[
                {"provider_id": "kh", "capabilities": ["workflow_control", "tdd_review"]},
                {
                    "provider_id": "superpowers",
                    "capabilities": ["planning_methodology", "tdd_review"],
                    "status": "unavailable",
                },
            ],
        )

        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertEqual(decision.unavailable_capabilities["provider:superpowers"], "provider_status:unavailable")
        self.assertIn("explicit_provider_unavailable:superpowers", decision.reasons)
        self.assertTrue(decision.explicit_user_request)

    def test_controller_tie_break_is_stable_and_not_reverse_lexical(self):
        decision = compose_plugin_route(
            "Implement the workflow and prove it with tests.",
            providers=[
                {"provider_id": "zeta", "capabilities": ["workflow_control"]},
                {"provider_id": "alpha", "capabilities": ["workflow_control"]},
            ],
        )

        self.assertEqual(decision.controller.provider_id, "alpha")

    def test_plugin_manifest_exposes_composition_as_top_level_policy(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        root_manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        prompts = "\n".join(manifest["interface"]["defaultPrompt"])
        root_skill_names = {skill["name"] for skill in root_manifest["skills"]}

        self.assertEqual(manifest["version"], "2.9.23")
        self.assertIn("Plugin Composition", manifest["interface"]["capabilities"])
        self.assertIn("plugin-composition-policy", root_skill_names)
        self.assertIn("plugin-composition", root_skill_names)
        self.assertIn("Before applying any plugin-specific MUST/ALWAYS rule", prompts)
        self.assertIn("controller plus assistant composition", prompts)


if __name__ == "__main__":
    unittest.main()
