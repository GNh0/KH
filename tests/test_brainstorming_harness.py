import unittest

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


if __name__ == "__main__":
    unittest.main()
