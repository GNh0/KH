import unittest

from src.orchestration.evidence_producers import collect_metadata_evidence
from src.orchestration.gate_evaluators import (
    build_gate_results,
    evaluate_code_quality_gate,
    evaluate_qa_gate,
    evaluate_spec_review_gate,
)


class GateEvaluatorTests(unittest.TestCase):
    def test_spec_review_evaluator_reports_failed_implementer_tasks(self):
        gate = evaluate_spec_review_gate([
            {"role": "implementer", "status": "failed", "file_name": "main.py"},
        ])

        self.assertEqual(gate["role"], "spec-reviewer")
        self.assertEqual(gate["status"], "failed")
        self.assertEqual(gate["findings"], ["main.py failed"])
        self.assertEqual(gate["evidence_records"][0]["source"], "review")
        self.assertEqual(gate["evidence_records"][0]["status"], "failed")

    def test_passed_gate_chain_emits_evidence_records(self):
        gates = build_gate_results([
            {
                "role": "implementer",
                "status": "success",
                "file_name": "main.py",
                "metadata": {"evidence": ["task runner completed", "target file generated:main.py"]},
            },
        ])

        self.assertEqual([gate["role"] for gate in gates], [
            "spec-reviewer",
            "code-quality-reviewer",
            "qa-verifier",
            "security-reviewer",
            "release-manager",
        ])
        self.assertEqual({gate["status"] for gate in gates}, {"passed"})
        self.assertEqual(
            [
                collect_metadata_evidence(gate)[0]
                for gate in gates
            ],
            [
                "spec review passed",
                "code quality review passed",
                "qa gate passed",
                "security review passed",
                "release gate passed",
            ],
        )

    def test_spec_review_requires_task_evidence_not_status_only(self):
        gate = evaluate_spec_review_gate([
            {"role": "implementer", "status": "success", "file_name": "main.py"},
        ])

        self.assertEqual(gate["status"], "failed")
        self.assertIn("missing implementation evidence", gate["message"])
        self.assertEqual(gate["evidence_records"][0]["status"], "failed")

    def test_code_quality_gate_blocks_reported_quality_findings(self):
        gate = evaluate_code_quality_gate(
            spec_gate={"role": "spec-reviewer", "status": "passed"},
            task_results=[
                {
                    "role": "implementer",
                    "status": "success",
                    "file_name": "main.py",
                    "metadata": {"quality_findings": ["missing boundary test"]},
                }
            ],
        )

        self.assertEqual(gate["status"], "failed")
        self.assertEqual(gate["findings"], ["main.py: missing boundary test"])

    def test_qa_gate_blocks_missing_goal_evidence(self):
        gate = evaluate_qa_gate(
            quality_gate={"role": "code-quality-reviewer", "status": "passed"},
            goal={
                "status": "blocked",
                "blocked_reason": "missing required evidence: tests",
                "metadata": {"missing_evidence": ["tests"]},
            },
        )

        self.assertEqual(gate["status"], "blocked")
        self.assertEqual(gate["missing_evidence"], ["tests"])
        self.assertEqual(gate["evidence_records"][0]["source"], "qa")
        self.assertEqual(gate["evidence_records"][0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
