import json
import unittest
from pathlib import Path

from src.orchestration.kh_front_door import build_kh_front_door
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
        root_manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        capabilities = set(manifest["interface"]["capabilities"])
        root_skill_names = {skill["name"] for skill in root_manifest["skills"]}

        self.assertEqual(manifest["version"], root_manifest["version"])
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertIn("Superpowers Replacement Layer", capabilities)
        summary = build_kh_front_door(
            "Implement a multi-file feature with tests, worktree isolation, debugging, review, verification, and branch finishing.",
            project=root,
            host="codex",
        ).to_summary_dict()
        routed_skills = set(
            summary["runtime_applied_skills"]
            + summary["immediate_next_skills"]
            + summary["selected_not_executed_skills"]
        )
        procedure_markers = {
            "verification-before-completion-harness": "fresh verification evidence",
            "systematic-debugging-harness": "verify root cause",
            "branch-finishing-harness": "Do not commit unrelated user changes",
            "worktree-isolation-harness": ".worktrees/<task>",
            "plan-execution-harness": "RED/GREEN evidence",
        }
        for skill in SUPERPOWERS_REPLACEMENT_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(skill, root_skill_names)
                self.assertIn(skill, routed_skills)
                skill_doc = (
                    root / "skills" / skill.replace("-", "_") / "SKILL.md"
                ).read_text(encoding="utf-8")
                self.assertIn(procedure_markers[skill], skill_doc)

if __name__ == "__main__":
    unittest.main()
