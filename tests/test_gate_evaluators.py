import unittest

from src.orchestration.evidence_producers import collect_metadata_evidence
from src.orchestration.gate_evaluators import (
    build_qa_check,
    build_review_finding,
    build_gate_results,
    evaluate_code_quality_gate,
    evaluate_qa_checks,
    evaluate_qa_gate,
    evaluate_release_gate,
    evaluate_security_gate,
    evaluate_spec_review_gate,
    normalize_review_findings,
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

    def test_normalized_review_findings_keep_severity_location_and_action(self):
        finding = build_review_finding(
            severity="high",
            message="missing destructive command approval",
            file_path="src/skills/command_policy.py",
            line=42,
            suggested_fix="require ask verdict",
            needs_approval=True,
        )

        normalized = normalize_review_findings([finding, "README.md: unclear install path"])

        self.assertEqual(normalized[0]["severity"], "high")
        self.assertEqual(normalized[0]["file_path"], "src/skills/command_policy.py")
        self.assertEqual(normalized[0]["line"], 42)
        self.assertEqual(normalized[0]["next_action"], "ask")
        self.assertEqual(normalized[1]["severity"], "medium")
        self.assertEqual(normalized[1]["message"], "README.md: unclear install path")

    def test_code_quality_gate_includes_structured_findings(self):
        gate = evaluate_code_quality_gate(
            spec_gate={"role": "spec-reviewer", "status": "passed"},
            task_results=[
                {
                    "role": "implementer",
                    "status": "success",
                    "file_name": "src/app.py",
                    "metadata": {
                        "quality_findings": [
                            build_review_finding(
                                severity="medium",
                                message="missing regression test",
                                file_path="tests/test_app.py",
                            )
                        ]
                    },
                }
            ],
        )

        self.assertEqual(gate["status"], "failed")
        self.assertEqual(gate["structured_findings"][0]["file_path"], "tests/test_app.py")
        self.assertEqual(gate["structured_findings"][0]["next_action"], "fix")

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

    def test_evaluate_qa_checks_fails_failed_or_blocked_checks(self):
        gate = evaluate_qa_checks(
            quality_gate={"role": "code-quality-reviewer", "status": "passed"},
            checks=[
                build_qa_check(
                    requirement_id="REQ-1",
                    check_type="automated",
                    description="unit tests",
                    status="passed",
                    evidence=["python -m unittest tests.test_demo"],
                ),
                build_qa_check(
                    requirement_id="REQ-2",
                    check_type="manual",
                    description="browser render verification",
                    status="blocked",
                    evidence=[],
                    notes="browser adapter unavailable",
                ),
            ],
        )

        self.assertEqual(gate["status"], "blocked")
        self.assertEqual(gate["checks"][1]["requirement_id"], "REQ-2")
        self.assertTrue(any("REQ-2 blocked" in finding for finding in gate["findings"]))

    def test_evaluate_qa_checks_blocks_empty_check_sets_by_default(self):
        gate = evaluate_qa_checks(
            quality_gate={"role": "code-quality-reviewer", "status": "passed"},
            checks=[],
        )

        self.assertEqual(gate["status"], "blocked")
        self.assertIn("no QA checks were supplied", gate["findings"])

    def test_bare_skipped_qa_check_is_blocked(self):
        gate = evaluate_qa_checks(
            quality_gate={"role": "code-quality-reviewer", "status": "passed"},
            checks=[
                build_qa_check(
                    requirement_id="QA-SKIP",
                    check_type="approved-skip",
                    description="not applicable",
                    status="skipped",
                )
            ],
        )

        self.assertEqual(gate["status"], "blocked")
        self.assertTrue(any("skip" in finding.lower() for finding in gate["findings"]))

    def test_security_findings_block_security_and_release_gates(self):
        security_gate = evaluate_security_gate(
            quality_gate={"role": "code-quality-reviewer", "status": "passed"},
            task_results=[
                {
                    "role": "implementer",
                    "status": "success",
                    "file_name": "src/app.py",
                    "metadata": {"security_findings": ["secret written to logs"]},
                }
            ],
        )
        release_gate = evaluate_release_gate(
            qa_gate={"role": "qa-verifier", "status": "passed", "findings": []},
            security_gate=security_gate,
        )

        self.assertEqual(security_gate["status"], "failed")
        self.assertEqual(release_gate["status"], "blocked")
        self.assertIn("secret written to logs", release_gate["findings"])


if __name__ == "__main__":
    unittest.main()
