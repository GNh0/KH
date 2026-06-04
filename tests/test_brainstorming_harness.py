import unittest
from pathlib import Path

from src.orchestration.brainstorming import (
    BrainstormDecision,
    BrainstormOption,
    BrainstormSession,
    build_architect_handoff,
    validate_brainstorm_session,
)


class BrainstormingHarnessTests(unittest.TestCase):
    def test_valid_session_builds_architect_handoff(self):
        session = BrainstormSession(
            objective="Build a small B2B CRM SaaS MVP.",
            target_user="Small B2B sales teams",
            problem="Deals and follow-ups are scattered across spreadsheets.",
            options=[
                BrainstormOption(
                    name="Pipeline-first CRM",
                    tradeoffs=["fastest MVP", "reporting can come later"],
                    recommended=True,
                ),
                BrainstormOption(
                    name="Reporting-first CRM",
                    tradeoffs=["useful dashboards", "needs more data model upfront"],
                ),
            ],
            decisions=[
                BrainstormDecision(key="product_name", value="PipePilot"),
                BrainstormDecision(key="mvp_focus", value="deal pipeline"),
            ],
            open_questions=["Which auth provider should be used?"],
            constraints=["Private GitHub repo", "TypeScript full-stack MVP"],
            next_skill="architect-pipeline",
        )

        validation = validate_brainstorm_session(session)
        handoff = build_architect_handoff(session)

        self.assertTrue(validation["valid"], validation)
        self.assertEqual(handoff["next_skill"], "architect-pipeline")
        self.assertEqual(handoff["objective"], session.objective)
        self.assertIn("PipePilot", handoff["decisions"]["product_name"])
        self.assertIn("brainstorm_handoff", handoff["evidence"])
        self.assertIn("decision_log", handoff["evidence"])

    def test_validation_blocks_missing_recommendation_or_decisions(self):
        session = BrainstormSession(
            objective="Build something",
            target_user="",
            problem="",
            options=[BrainstormOption(name="Option A", tradeoffs=[])],
            decisions=[],
        )

        validation = validate_brainstorm_session(session)

        self.assertFalse(validation["valid"])
        self.assertIn("target_user", validation["missing"])
        self.assertIn("problem", validation["missing"])
        self.assertIn("recommended_option", validation["missing"])
        self.assertIn("decisions", validation["missing"])

    def test_skill_docs_require_domain_first_compact_brainstorming(self):
        repo_root = Path(__file__).resolve().parents[1]
        skill = (repo_root / "skills" / "brainstorming_harness" / "SKILL.md").read_text(encoding="utf-8")
        usage = (
            repo_root / "skills" / "brainstorming_harness" / "references" / "usage.md"
        ).read_text(encoding="utf-8")
        combined = skill + "\n" + usage

        self.assertIn("Domain-First Compact Brainstorm", skill)
        self.assertIn("Visible First Response Gate", skill)
        self.assertIn("Approved Continuation Gate", skill)
        self.assertIn("Success criteria/constraints/non-goals", skill)
        self.assertIn("Open questions", skill)
        self.assertIn("approval_frame", combined)
        self.assertIn("brainstorm_handoff", combined)
        self.assertIn("global Codex memory", combined)
        self.assertIn("inventory inbound/outbound", combined)
        self.assertIn("operating model", combined)
        self.assertIn("required records", combined)
        self.assertIn("HTML", combined)
        self.assertIn("React", combined)
        self.assertIn("WinForms", combined)


if __name__ == "__main__":
    unittest.main()
