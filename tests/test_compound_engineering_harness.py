import unittest

from src.orchestration.compound import (
    CompoundCapture,
    CompoundLearning,
    CompoundMemoryCandidate,
    build_compound_handoff,
    validate_compound_capture,
)


class CompoundEngineeringHarnessTests(unittest.TestCase):
    def test_valid_capture_builds_system_update_handoff(self):
        capture = CompoundCapture(
            objective="Improve SaaS project discovery.",
            completed_work=["Added brainstorming handoff and SIDE regression coverage."],
            review_findings=["Superpowers was selected before KH for unclear SaaS work."],
            learnings=[
                CompoundLearning(
                    title="Use KH brainstorming as the front door",
                    trigger="New product, SaaS, feature, or unclear design request",
                    reusable_insight="Start with one-question-at-a-time discovery and hand off to architect-pipeline.",
                    evidence=["brainstorm_handoff", "SIDE skill activation"],
                    tags=["brainstorming", "front-door", "compound"],
                )
            ],
            system_updates=[
                "Update plugin default prompt to prefer KH brainstorming for SaaS discovery.",
                "Add SIDE regression for compound capture after review.",
            ],
            regression_checks=[
                "python -m unittest tests.test_superpowers_benchmark_alignment",
            ],
            memory_candidates=[
                CompoundMemoryCandidate(
                    scope="project",
                    content="For SaaS discovery in this project, start with KH brainstorming-harness before architecture.",
                    evidence=["brainstorm_handoff", "plugin prompt update"],
                    confidence=0.86,
                )
            ],
            next_skills=["workflow-skill-distiller", "scenario-evaluation-harness", "memory-state-harness"],
            source_references=["Superpowers", "external role-stack benchmark", "external compound engineering"],
        )

        validation = validate_compound_capture(capture)
        handoff = build_compound_handoff(capture)

        self.assertTrue(validation["valid"], validation)
        self.assertEqual(handoff["status"], "ready_for_system_update")
        self.assertIn("compound_capture", handoff["evidence"])
        self.assertIn("learning_candidates", handoff["evidence"])
        self.assertIn("system_update_plan", handoff["evidence"])
        self.assertIn("regression_check_plan", handoff["evidence"])
        self.assertIn("memory_candidates", handoff["evidence"])
        self.assertIn("workflow-skill-distiller", handoff["next_skills"])
        self.assertIn("memory-state-harness", handoff["next_skills"])

    def test_memory_candidate_rejects_global_scope_without_explicit_promotion(self):
        capture = CompoundCapture(
            objective="Capture a project preference.",
            completed_work=["Observed repeated SaaS discovery pattern."],
            review_findings=["Pattern should be remembered for this project only."],
            learnings=[
                CompoundLearning(
                    title="Project discovery starts with brainstorming",
                    trigger="SaaS project kickoff",
                    reusable_insight="Use KH brainstorming before architecture.",
                    evidence=["review finding"],
                )
            ],
            system_updates=["Attach memory candidate to handoff."],
            regression_checks=["python -m unittest tests.test_compound_engineering_harness"],
            memory_candidates=[
                CompoundMemoryCandidate(
                    scope="global",
                    content="Always use this project preference everywhere.",
                    evidence=["review finding"],
                    confidence=0.7,
                )
            ],
        )

        validation = validate_compound_capture(capture)

        self.assertFalse(validation["valid"])
        self.assertIn("explicit_global_memory_promotion", validation["missing"])

    def test_validation_requires_learning_or_explicit_no_learning_rationale(self):
        capture = CompoundCapture(
            objective="Ship a small typo fix.",
            completed_work=["Fixed one typo."],
            review_findings=["No review findings."],
        )

        validation = validate_compound_capture(capture)
        handoff = build_compound_handoff(capture)

        self.assertFalse(validation["valid"])
        self.assertIn("learning_or_no_learning_rationale", validation["missing"])
        self.assertEqual(handoff["status"], "blocked")

    def test_no_reusable_learning_still_produces_a_compound_record(self):
        capture = CompoundCapture(
            objective="Fix one README typo.",
            completed_work=["Corrected spelling."],
            review_findings=["No issues."],
            no_reusable_learning_rationale="One-off typo; no repeatable pattern or regression value.",
        )

        validation = validate_compound_capture(capture)
        handoff = build_compound_handoff(capture)

        self.assertTrue(validation["valid"], validation)
        self.assertIn("no_reusable_learning_rationale", handoff["evidence"])
        self.assertEqual(handoff["status"], "ready_for_system_update")


if __name__ == "__main__":
    unittest.main()
