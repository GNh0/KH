import unittest
from copy import deepcopy
from datetime import datetime, timezone

from src.orchestration.goal_evidence import (
    RuntimeProducerBoundary,
    build_evidence_envelope,
    capture_evidence_envelope,
    collect_workflow_goal_evidence,
    evaluate_goal_evidence,
    sha256_text,
    validate_evidence_envelope,
)


class GoalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.producer_boundary = RuntimeProducerBoundary("goal-evidence-tests")

    def strict_goal(self):
        scope = {
            "project_id": "project-1",
            "thread_id": "thread-1",
            "task_id": "task-1",
            "goal_id": "goal-1",
            "lineage_id": "lineage-1",
            "objective_hash": sha256_text("ship runtime"),
        }
        return {
            "objective": "ship runtime",
            "status": "active",
            "success_criteria": ["focused tests pass"],
            "evidence_required": ["focused tests passed"],
            "evidence": [],
            "metadata": {
                "goal_required": True,
                "evidence_policy": "typed_observed_v1",
                "scope": scope,
                "criterion_evidence_map": {
                    "focused tests pass": ["focused tests passed"],
                },
                "evidence_envelopes": [],
            },
        }

    def observed_test(
        self,
        scope,
        *,
        key="focused tests passed",
        status="passed",
        exit_code=0,
        observed_at="",
        supersedes="",
    ):
        return capture_evidence_envelope(
            producer_boundary=self.producer_boundary,
            evidence_type="test",
            evidence_key=key,
            producer="python-unittest",
            scope=scope,
            observed_at=observed_at or datetime.now(timezone.utc).isoformat(),
            status=status,
            command="python -m unittest tests.test_goal_evidence",
            command_id=f"cmd-{status}",
            exit_code=exit_code,
            captured_output=f"{status}:{exit_code}",
            supersedes=supersedes,
        )

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

    def test_goal_required_work_cannot_complete_from_status_string_only(self):
        goal = {
            "objective": "ship runtime",
            "status": "complete",
            "success_criteria": [],
            "evidence_required": [],
            "evidence": ["complete"],
            "metadata": {"goal_required": True},
        }

        evaluated = evaluate_goal_evidence(goal, workflow_evidence=[], workflow_success=True)

        self.assertEqual(evaluated["status"], "blocked")
        self.assertEqual(
            evaluated["metadata"]["missing_goal_requirements"],
            ["success_criteria", "evidence_required"],
        )
        self.assertIn("missing goal completion requirements", evaluated["blocked_reason"])

    def test_failed_evidence_record_does_not_satisfy_goal_requirement(self):
        goal = {
            "objective": "ship runtime",
            "status": "active",
            "success_criteria": ["focused tests pass"],
            "evidence_required": ["focused tests passed"],
            "evidence": ["focused tests passed"],
            "metadata": {
                "goal_required": True,
                "evidence_records": [
                    {"key": "focused tests passed", "status": "failed"},
                ],
            },
        }

        evaluated = evaluate_goal_evidence(goal, workflow_evidence=[], workflow_success=True)

        self.assertEqual(evaluated["status"], "blocked")
        self.assertEqual(evaluated["metadata"]["missing_evidence"], [])
        self.assertEqual(evaluated["metadata"]["failed_evidence"], ["focused tests passed"])

    def test_typed_envelope_requires_observed_producer_scope_time_hash_and_type_fields(self):
        goal = self.strict_goal()
        scope = goal["metadata"]["scope"]
        valid = self.observed_test(scope)
        checked = validate_evidence_envelope(
            valid,
            expected_scope=scope,
            producer_boundary=self.producer_boundary,
        )
        self.assertTrue(checked["valid"], checked)

        required_fields = [
            "producer",
            "scope",
            "observed_at",
            "output_hash",
            "command_id",
            "exit_code",
        ]
        for field in required_fields:
            with self.subTest(field=field):
                candidate = dict(valid)
                candidate.pop(field)
                invalid = validate_evidence_envelope(
                    candidate,
                    expected_scope=scope,
                    producer_boundary=self.producer_boundary,
                )
                self.assertFalse(invalid["valid"])
                self.assertIn(f"missing_{field}", invalid["errors"])

    def test_caller_constructed_structural_envelope_is_claimed_not_observed(self):
        goal = self.strict_goal()
        fabricated = build_evidence_envelope(
            evidence_type="test",
            evidence_key="focused tests passed",
            observation="observed",
            producer="caller",
            scope=goal["metadata"]["scope"],
            observed_at=datetime.now(timezone.utc).isoformat(),
            status="passed",
            command="python -m unittest tests.test_goal_evidence",
            command_id="caller-command",
            exit_code=0,
            output_hash=sha256_text("fabricated output"),
        )

        checked = validate_evidence_envelope(
            fabricated,
            expected_scope=goal["metadata"]["scope"],
        )
        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=[fabricated],
            workflow_success=True,
        )

        self.assertFalse(checked["valid"])
        self.assertIn("runtime_producer_revalidation_required", checked["errors"])
        self.assertEqual(evaluated["status"], "active")
        self.assertEqual(
            evaluated["metadata"]["missing_evidence"],
            ["focused tests passed"],
        )

    def test_strict_completion_accepts_only_observed_scope_matched_evidence(self):
        goal = self.strict_goal()
        scope = goal["metadata"]["scope"]
        asserted = {
            **self.observed_test(scope),
            "observation": "asserted",
        }
        wrong_scope = self.observed_test({**scope, "thread_id": "other-thread"})

        for evidence, expected_invalid in [
            (["focused tests passed"], "untyped_evidence"),
            ([asserted], "asserted_evidence"),
            ([wrong_scope], "scope_mismatch"),
        ]:
            with self.subTest(expected_invalid=expected_invalid):
                evaluated = evaluate_goal_evidence(
                    goal,
                    workflow_evidence=evidence,
                    workflow_success=True,
                    producer_boundary=self.producer_boundary,
                )
                self.assertEqual(evaluated["status"], "active")
                self.assertEqual(
                    evaluated["metadata"]["missing_evidence"],
                    ["focused tests passed"],
                )
                self.assertIn(expected_invalid, evaluated["metadata"]["invalid_evidence_reasons"])

        completed = evaluate_goal_evidence(
            goal,
            workflow_evidence=[self.observed_test(scope)],
            workflow_success=True,
            producer_boundary=self.producer_boundary,
        )
        self.assertEqual(completed["status"], "complete")
        self.assertEqual(completed["metadata"]["missing_evidence"], [])
        self.assertEqual(completed["metadata"]["observed_evidence"], ["focused tests passed"])

    def test_strict_completion_requires_every_criterion_mapping(self):
        goal = self.strict_goal()
        goal["success_criteria"].append("review passes")
        goal["evidence_required"].append("review passed")
        goal["metadata"]["criterion_evidence_map"] = {
            "focused tests pass": ["focused tests passed"],
        }
        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=[self.observed_test(goal["metadata"]["scope"])],
            workflow_success=True,
            producer_boundary=self.producer_boundary,
        )
        self.assertEqual(evaluated["status"], "active")
        self.assertEqual(evaluated["metadata"]["unmapped_success_criteria"], ["review passes"])

    def test_strict_workflow_failure_boolean_does_not_forge_blocked_terminal_state(self):
        goal = self.strict_goal()
        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=[self.observed_test(goal["metadata"]["scope"])],
            workflow_success=False,
            producer_boundary=self.producer_boundary,
        )
        self.assertEqual(evaluated["status"], "active")
        self.assertEqual(evaluated["blocked_reason"], "")
        self.assertTrue(evaluated["metadata"]["workflow_failure_asserted"])

    def test_strict_goal_without_complete_scope_identity_cannot_close(self):
        goal = self.strict_goal()
        goal["metadata"]["scope"].pop("lineage_id")
        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=[],
            workflow_success=True,
        )
        self.assertEqual(evaluated["status"], "active")
        self.assertIn("scope", evaluated["metadata"]["missing_goal_requirements"])

    def test_later_failed_observation_revokes_earlier_pass(self):
        goal = self.strict_goal()
        scope = goal["metadata"]["scope"]
        passed = self.observed_test(
            scope,
            status="passed",
            exit_code=0,
            observed_at="2026-07-10T01:00:00+00:00",
        )
        failed = self.observed_test(
            scope,
            status="failed",
            exit_code=1,
            observed_at="2026-07-10T01:01:00+00:00",
        )

        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=[passed, failed],
            workflow_success=True,
            producer_boundary=self.producer_boundary,
        )

        self.assertEqual(evaluated["status"], "active")
        self.assertEqual(evaluated["metadata"]["observed_evidence"], [])
        self.assertEqual(evaluated["metadata"]["missing_evidence"], [])
        self.assertEqual(evaluated["metadata"]["failed_evidence"], ["focused tests passed"])

    def test_later_pass_requires_validated_supersession_of_failure(self):
        goal = self.strict_goal()
        scope = goal["metadata"]["scope"]
        failed = self.observed_test(
            scope,
            status="failed",
            exit_code=1,
            observed_at="2026-07-10T01:00:00+00:00",
        )
        passed = self.observed_test(
            scope,
            status="passed",
            exit_code=0,
            observed_at="2026-07-10T01:01:00+00:00",
            supersedes=failed["receipt_id"],
        )

        evaluated = evaluate_goal_evidence(
            goal,
            workflow_evidence=[failed, passed],
            workflow_success=True,
            producer_boundary=self.producer_boundary,
        )

        self.assertEqual(evaluated["status"], "complete")
        self.assertEqual(evaluated["metadata"]["observed_evidence"], ["focused tests passed"])

    def test_public_capture_helper_is_claimed_until_explicit_runtime_boundary_observes_it(self):
        goal = self.strict_goal()
        claimed = capture_evidence_envelope(
            evidence_type="test",
            evidence_key="focused tests passed",
            producer="caller",
            scope=goal["metadata"]["scope"],
            status="passed",
            command="python -m unittest tests.test_goal_evidence",
            command_id="caller-command",
            exit_code=0,
            captured_output="caller supplied output",
        )

        checked = validate_evidence_envelope(
            claimed,
            expected_scope=goal["metadata"]["scope"],
        )

        self.assertFalse(checked["valid"])
        self.assertEqual(claimed["observation"], "asserted")
        self.assertEqual(claimed["authority"], "claimed_unverified")
        self.assertIn("asserted_evidence", checked["errors"])

    def test_persisted_claim_requires_same_runtime_producer_revalidation(self):
        goal = self.strict_goal()
        envelope = self.observed_test(goal["metadata"]["scope"])
        persisted = deepcopy(envelope)

        no_boundary = validate_evidence_envelope(
            persisted,
            expected_scope=goal["metadata"]["scope"],
        )
        wrong_boundary = validate_evidence_envelope(
            persisted,
            expected_scope=goal["metadata"]["scope"],
            producer_boundary=RuntimeProducerBoundary("other-process"),
        )

        self.assertFalse(no_boundary["valid"])
        self.assertIn("runtime_producer_revalidation_required", no_boundary["errors"])
        self.assertFalse(wrong_boundary["valid"])
        self.assertIn("runtime_producer_boundary_mismatch", wrong_boundary["errors"])

    def test_replayed_or_invalid_runtime_claim_fails_closed(self):
        goal = self.strict_goal()
        envelope = self.observed_test(goal["metadata"]["scope"])
        replayed = evaluate_goal_evidence(
            goal,
            workflow_evidence=[envelope, envelope],
            workflow_success=True,
            producer_boundary=self.producer_boundary,
        )
        tampered = deepcopy(envelope)
        tampered["output_hash"] = sha256_text("tampered")
        invalid = evaluate_goal_evidence(
            goal,
            workflow_evidence=[envelope, tampered],
            workflow_success=True,
            producer_boundary=self.producer_boundary,
        )

        self.assertEqual(replayed["status"], "active")
        self.assertIn(
            "replayed_evidence_receipt",
            replayed["metadata"]["invalid_evidence_reasons"],
        )
        self.assertEqual(invalid["status"], "active")
        self.assertIn(
            "runtime_producer_claim_mismatch",
            invalid["metadata"]["invalid_evidence_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
