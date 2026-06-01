import unittest

from src.orchestration.goal_evidence import (
    collect_workflow_goal_evidence,
    evaluate_goal_evidence,
)


class GoalEvidenceTests(unittest.TestCase):
    def test_collect_workflow_goal_evidence_records_deterministic_workflow_facts(self):
        evidence = collect_workflow_goal_evidence(
            design_doc="# design",
            file_list=["main.py"],
            workflow_completed=True,
        )

        self.assertEqual(
            evidence,
            ["design_doc", "target_files", "workflow dispatch completed"],
        )

    def test_evaluate_goal_evidence_marks_complete_when_required_evidence_is_present(self):
        goal = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "tests"],
            "evidence": [" tests "],
        }

        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=["DESIGN_DOC"],
            workflow_success=True,
        )

        self.assertEqual(evaluated["status"], "complete")
        self.assertEqual(evaluated["blocked_reason"], "")
        self.assertEqual(evaluated["evidence"], ["tests", "design_doc"])
        self.assertEqual(evaluated["metadata"]["missing_evidence"], [])

    def test_evaluate_goal_evidence_accepts_default_evidence_aliases(self):
        goal = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design doc", "unit tests passed"],
            "evidence": ["tests passed"],
        }

        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=["design_doc"],
            workflow_success=True,
        )

        self.assertEqual(evaluated["status"], "complete")
        self.assertEqual(evaluated["metadata"]["missing_evidence"], [])
        self.assertEqual(
            evaluated["metadata"]["evidence_alias_matches"],
            {
                "design doc": "design_doc",
                "unit tests passed": "tests passed",
            },
        )

    def test_evaluate_goal_evidence_accepts_metadata_evidence_aliases(self):
        goal = {
            "objective": "release api",
            "status": "active",
            "evidence_required": ["release approved"],
            "evidence": ["release gate passed"],
            "metadata": {
                "evidence_aliases": {
                    "release approved": ["release gate passed"],
                },
            },
        }

        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=[],
            workflow_success=True,
        )

        self.assertEqual(evaluated["status"], "complete")
        self.assertEqual(
            evaluated["metadata"]["evidence_alias_matches"],
            {"release approved": "release gate passed"},
        )

    def test_evaluate_goal_evidence_blocks_when_required_evidence_is_missing(self):
        goal = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "qa report"],
            "evidence": [],
        }

        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=["design_doc"],
            workflow_success=True,
        )

        self.assertEqual(evaluated["status"], "blocked")
        self.assertEqual(evaluated["blocked_reason"], "missing required evidence: qa report")
        self.assertEqual(evaluated["metadata"]["missing_evidence"], ["qa report"])

    def test_evaluate_goal_evidence_blocks_when_workflow_failed(self):
        goal = {
            "objective": "build api",
            "status": "active",
            "evidence_required": [],
            "evidence": [],
        }

        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=["workflow dispatch completed"],
            workflow_success=False,
        )

        self.assertEqual(evaluated["status"], "blocked")
        self.assertEqual(evaluated["blocked_reason"], "workflow dispatch failed")


if __name__ == "__main__":
    unittest.main()
