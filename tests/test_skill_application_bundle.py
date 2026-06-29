import unittest
from pathlib import Path

from src.orchestration.skill_application import (
    BUNDLE_MEMBER_SKILLS,
    build_large_work_orchestration_bundle,
    validate_large_work_orchestration_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class SkillApplicationBundleTests(unittest.TestCase):
    def test_builder_creates_lightweight_status_template_for_large_work(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Build a SaaS CRM MVP.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            overrides={
                "parallel-orchestration-harness": {
                    "status": "considered_not_needed",
                    "application_mode": "procedural",
                    "evidence_note": "Sequential task dependencies; no safe independent write set.",
                },
                "memory-state-harness": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "Captured project-scoped memory candidates only.",
                    "evidence_keys": ["memory_candidates"],
                },
            },
        )

        validation = validate_large_work_orchestration_bundle(bundle)
        serialized = bundle.to_dict()

        self.assertTrue(validation["valid"], validation)
        self.assertEqual(serialized["evidence_key"], "large_work_orchestration_bundle")
        self.assertEqual(serialized["workspace_strategy"], "project-local-worktree")
        self.assertEqual(serialized["token_optimizer_status"], "used")
        self.assertIn("Token optimizer used", serialized["token_optimizer_status_reason"])
        self.assertEqual(set(serialized["skill_statuses"]), set(BUNDLE_MEMBER_SKILLS))
        self.assertEqual(
            serialized["skill_statuses"]["parallel-orchestration-harness"]["status"],
            "considered_not_needed",
        )
        self.assertIn("parallel_strategy_decision", serialized)
        self.assertIn("memory_candidates", serialized)
        self.assertIn("compound_handoff", serialized)

    def test_validation_rejects_missing_rationale_for_skipped_or_considered_skills(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Build a SaaS CRM MVP.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            overrides={
                "workflow-skill-distiller": {
                    "status": "considered_not_needed",
                    "application_mode": "procedural",
                    "evidence_note": "",
                }
            },
        )

        validation = validate_large_work_orchestration_bundle(bundle)

        self.assertFalse(validation["valid"])
        self.assertIn("workflow-skill-distiller.evidence_note", validation["missing"])

    def test_validation_rejects_invalid_status_or_mode(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Build a SaaS CRM MVP.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            overrides={
                "host-agent-orchestration": {
                    "status": "done",
                    "application_mode": "magic",
                    "evidence_note": "Host handled it.",
                }
            },
        )

        validation = validate_large_work_orchestration_bundle(bundle)

        self.assertFalse(validation["valid"])
        self.assertIn("host-agent-orchestration.status", validation["missing"])
        self.assertIn("host-agent-orchestration.application_mode", validation["missing"])

    def test_docs_explain_modes_and_minimal_evidence_template(self):
        lifecycle = read_text("skills/development_lifecycle_harness/SKILL.md")
        router = read_text("skills/request_complexity_router/SKILL.md")
        audit = read_text("docs/skillbook/audits/2026-05-30-large-work-orchestration-bundle.md")
        combined = lifecycle + "\n" + router + "\n" + audit

        for phrase in [
            "application_mode",
            "runtime",
            "procedural",
            "considered",
            "blocked",
            "minimal evidence template",
            "evidence_note",
            "do not require AdapterRequest",
            "memory candidates only",
        ]:
            self.assertIn(phrase, combined)


if __name__ == "__main__":
    unittest.main()
