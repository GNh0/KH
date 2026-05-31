import json
import unittest
from pathlib import Path

from src.orchestration.plugin_composition import compose_plugin_route
from src.orchestration.request_classifier import classify_request
from src.orchestration.role_commands import resolve_role_command
from src.orchestration.skill_application import (
    BUNDLE_MEMBER_SKILLS,
    build_large_work_orchestration_bundle,
    validate_large_work_orchestration_bundle,
)
from src.skills.uaf_skill_catalog import collect_packaged_skills


SUPERPOWERS_REPLACEMENT_SKILLS = {
    "verification-before-completion-harness",
    "systematic-debugging-harness",
    "branch-finishing-harness",
    "worktree-isolation-harness",
    "plan-execution-harness",
}


class SuperpowersReplacementLayerTests(unittest.TestCase):
    def test_replacement_skills_are_packaged_and_external_runtime_free(self):
        catalog = collect_packaged_skills()
        names = {skill["name"] for skill in catalog["skills"]}

        self.assertTrue(SUPERPOWERS_REPLACEMENT_SKILLS.issubset(names))
        for skill in catalog["skills"]:
            if skill["name"] in SUPERPOWERS_REPLACEMENT_SKILLS:
                self.assertFalse(skill["external_runtime_dependency"])
                self.assertEqual(skill["execution_level"], "hybrid-harness")

    def test_large_work_bundle_contains_replacement_layer_decisions(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Build and finish a feature without Superpowers.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="considered_not_needed",
        )
        validation = validate_large_work_orchestration_bundle(bundle)

        self.assertTrue(validation["valid"], validation)
        for skill in SUPERPOWERS_REPLACEMENT_SKILLS:
            self.assertIn(skill, BUNDLE_MEMBER_SKILLS)
            self.assertIn(skill, bundle.skill_statuses)
            self.assertTrue(bundle.skill_statuses[skill].evidence_note)

    def test_role_commands_route_to_replacement_layer(self):
        work = resolve_role_command("/kh:work")
        qa = resolve_role_command("/kh:qa")
        ship = resolve_role_command("/kh:ship")

        self.assertIn("worktree-isolation-harness", work.skills)
        self.assertIn("plan-execution-harness", work.skills)
        self.assertIn("systematic-debugging-harness", work.skills)
        self.assertIn("verification-before-completion-harness", qa.skills)
        self.assertIn("branch-finishing-harness", ship.skills)

    def test_plugin_composition_prefers_kh_when_superpowers_only_self_forces(self):
        decision = compose_plugin_route(
            "Implement this feature with tests, worktree isolation, review, and push it.",
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": [
                        "workflow_control",
                        "tdd_review",
                        "workspace_isolation",
                        "completion_verification",
                        "branch_finishing",
                    ],
                },
                {
                    "provider_id": "superpowers",
                    "capabilities": ["planning_methodology", "tdd_review", "worktree"],
                    "self_forcing_rules": ["MUST use when starting any conversation"],
                },
            ],
        )

        self.assertEqual(decision.controller.provider_id, "kh")
        self.assertIn("superpowers", decision.ignored_self_forcing)

    def test_request_classifier_recommends_replacement_skills_for_large_work(self):
        result = classify_request(
            "Build a multi-file feature with tests, use a worktree, debug failures, verify before completion, commit and push."
        )

        for skill in SUPERPOWERS_REPLACEMENT_SKILLS:
            self.assertIn(skill, result.recommended_skills)

    def test_manifest_exposes_replacement_layer(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        prompts = "\n".join(manifest["interface"]["defaultPrompt"])
        capabilities = set(manifest["interface"]["capabilities"])

        self.assertEqual(manifest["version"], "2.9.25")
        self.assertIn("Superpowers Replacement Layer", capabilities)
        self.assertIn("KH-native replacements for Superpowers-style", prompts)
        self.assertIn("verification-before-completion-harness", prompts)
        self.assertIn("branch-finishing-harness", prompts)


if __name__ == "__main__":
    unittest.main()
