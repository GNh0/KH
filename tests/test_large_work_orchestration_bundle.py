import json
import unittest
from pathlib import Path

from src.orchestration.request_classifier import classify_request


REPO_ROOT = Path(__file__).resolve().parents[1]


BUNDLE_SKILLS = [
    "request-complexity-router",
    "host-agent-orchestration",
    "domain-orchestration-harness",
    "goal-state-harness",
    "development-lifecycle-harness",
    "worktree-isolation-harness",
    "plan-execution-harness",
    "systematic-debugging-harness",
    "command-output-harness",
    "token-optimizer",
    "memory-state-harness",
    "parallel-orchestration-harness",
    "subagent-review-pipeline",
    "role-execution-audit-harness",
    "quality-gates-harness",
    "review-gate-harness",
    "qa-gate-harness",
    "artifact-render-qa-harness",
    "deliverable-template-quality-harness",
    "traceability-matrix-harness",
    "verification-before-completion-harness",
    "branch-finishing-harness",
    "compound-engineering-harness",
    "workflow-skill-distiller",
]

BUNDLE_STATUS_VALUES = [
    "applied",
    "considered_not_needed",
    "skipped_with_rationale",
    "blocked",
]


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class LargeWorkOrchestrationBundleTests(unittest.TestCase):
    def test_plugin_manifest_exposes_large_work_capability(self):
        plugin = json.loads(read_text(".codex-plugin/plugin.json"))
        root_manifest = json.loads(read_text("plugin.json"))
        root_skill_names = {skill["name"] for skill in root_manifest["skills"]}

        self.assertIn("Large Work Bundle", plugin["interface"]["capabilities"])
        for skill in BUNDLE_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn(skill, root_skill_names)

    def test_lifecycle_requires_bundle_decision_for_large_project_work(self):
        lifecycle = read_text("skills/development_lifecycle_harness/SKILL.md")
        usage = read_text("skills/development_lifecycle_harness/references/usage.md")
        combined = lifecycle + "\n" + usage

        self.assertIn("large_work_orchestration_bundle", combined)
        self.assertIn("skill_statuses", combined)
        for status in BUNDLE_STATUS_VALUES:
            self.assertIn(status, combined)
        for skill in BUNDLE_SKILLS:
            self.assertIn(skill, combined)
        for final_field in ["task_status", "review_status", "commit_sha", "next_task", "workspace_strategy"]:
            self.assertIn(final_field, combined)

    def test_router_escalates_large_project_work_to_bundle_without_over_orchestrating_light_work(self):
        router = read_text("skills/request_complexity_router/SKILL.md")
        router_usage = read_text("skills/request_complexity_router/references/usage.md")
        combined = router + "\n" + router_usage

        self.assertIn("large_work_orchestration_bundle", combined)
        self.assertIn("Do not create a large-work bundle for light or medium requests", combined)

        heavy = classify_request("Build a SaaS CRM MVP with auth, dashboard, API, tests, and i18n.")

        self.assertEqual(heavy.complexity, "heavy")
        self.assertEqual(heavy.recommended_execution, "role_dag")
        for skill in BUNDLE_SKILLS:
            self.assertIn(skill, heavy.recommended_skills)
        for harness in [
            "host-agent-orchestration",
            "domain-orchestration-harness",
            "goal-state-harness",
            "development-lifecycle-harness",
            "quality-gates-harness",
            "review-gate-harness",
            "qa-gate-harness",
        ]:
            self.assertIn(harness, heavy.required_harnesses)
        for evidence in [
            "large_work_orchestration_bundle",
            "skill_statuses",
            "parallel_strategy_decision",
            "memory_candidates",
            "compound_handoff",
        ]:
            self.assertIn(evidence, heavy.evidence_required)

        light = classify_request("What is PER?")

        self.assertEqual(light.complexity, "light")
        self.assertEqual(light.recommended_execution, "direct_answer")
        self.assertEqual(light.required_harnesses, [])
        self.assertNotIn("large_work_orchestration_bundle", light.evidence_required)

    def test_bundle_member_skills_cross_reference_bundle_reporting(self):
        for path in [
            "skills/host_agent_orchestration/SKILL.md",
            "skills/memory_state_harness/SKILL.md",
            "skills/parallel_orchestration_harness/SKILL.md",
            "skills/subagent_review_pipeline/SKILL.md",
            "skills/role_execution_audit_harness/SKILL.md",
            "skills/compound_engineering_harness/SKILL.md",
            "skills/workflow_skill_distiller/SKILL.md",
        ]:
            with self.subTest(path=path):
                content = read_text(path)
                self.assertIn("large_work_orchestration_bundle", content)
                self.assertIn("skill_statuses", content)


if __name__ == "__main__":
    unittest.main()
