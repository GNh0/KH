import unittest

from src.orchestration.skill_application import build_large_work_orchestration_bundle
from src.orchestration.skill_transitions import validate_skill_transitions


class SkillTransitionTests(unittest.TestCase):
    def test_post_review_requires_compound_closure(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Build a SaaS MVP.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
        )

        validation = validate_skill_transitions(bundle, phase="post_review")

        self.assertFalse(validation["valid"])
        self.assertIn("compound-engineering-harness", validation["required_next_skills"])
        self.assertEqual(validation["issues"][0]["rule"], "compound_handoff_must_close")

    def test_no_reusable_learning_closes_compound_transition(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Small verified fix.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            compound_handoff={
                "status": "no_reusable_learning",
                "no_reusable_learning_rationale": "One-off typo fix; no reusable workflow change.",
                "next_skills": [],
            },
        )

        validation = validate_skill_transitions(bundle, phase="final")

        self.assertTrue(validation["valid"], validation)
        self.assertIn("skill_transition_policy_passed", validation["evidence"])

    def test_memory_candidates_force_memory_state_harness(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Capture project learning.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            memory_candidates=[
                {
                    "scope": "project",
                    "content": "Use progress state for large task-plan runs.",
                    "evidence": ["review_summary"],
                }
            ],
            compound_handoff={
                "status": "ready_for_system_update",
                "next_skills": ["memory-state-harness"],
            },
        )

        validation = validate_skill_transitions(bundle, phase="final")

        self.assertFalse(validation["valid"])
        self.assertIn("memory-state-harness", validation["required_next_skills"])
        self.assertEqual(validation["issues"][0]["rule"], "memory_candidates_require_memory_state")

    def test_subagent_review_forces_role_audit_decision(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Run subagent implementation and reviews.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            overrides={
                "subagent-review-pipeline": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "Implementer, spec reviewer, and code-quality reviewer were dispatched.",
                    "evidence_keys": ["review_status"],
                }
            },
            compound_handoff={
                "status": "no_reusable_learning",
                "no_reusable_learning_rationale": "No reusable lesson after review.",
            },
        )

        validation = validate_skill_transitions(bundle, phase="final")

        self.assertFalse(validation["valid"])
        self.assertIn("role-execution-audit-harness", validation["required_next_skills"])
        self.assertEqual(validation["issues"][0]["rule"], "subagent_review_requires_role_audit_decision")

    def test_subagent_review_requires_token_optimizer_decision_not_auto_compression(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Run short review-only subagent.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="considered_not_needed",
            overrides={
                "subagent-review-pipeline": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "A short review-only subagent was used after dispatch decision.",
                    "evidence_keys": ["review_status", "subagent_strategy"],
                },
                "token-optimizer": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "Token gate was checked; transcript was short and exact.",
                    "evidence_keys": ["token_optimizer_status"],
                },
                "role-execution-audit-harness": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "Reviewer output was inspected.",
                    "evidence_keys": ["role_execution_audit"],
                },
            },
            compound_handoff={
                "status": "no_reusable_learning",
                "no_reusable_learning_rationale": "No reusable lesson after short review.",
            },
        )

        validation = validate_skill_transitions(bundle, phase="final")

        self.assertTrue(validation["valid"], validation)
        self.assertIn("skill_transition_policy_passed", validation["evidence"])

    def test_compound_next_skill_cannot_leave_followup_considered_not_needed(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Distill repeated workflow.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            compound_handoff={
                "status": "ready_for_system_update",
                "next_skills": ["workflow-skill-distiller", "scenario-evaluation-harness"],
            },
        )

        validation = validate_skill_transitions(bundle, phase="final")

        self.assertFalse(validation["valid"])
        self.assertIn("scenario-evaluation-harness", validation["required_next_skills"])
        self.assertIn("workflow-skill-distiller", validation["required_next_skills"])
        issue_rules = {issue["rule"] for issue in validation["issues"]}
        self.assertEqual(issue_rules, {"compound_next_skill_requires_followup_status"})

    def test_applied_handoffs_pass_when_required_followups_are_marked(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Run reviewed subagent workflow and capture learning.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            memory_candidates=[
                {
                    "scope": "project",
                    "content": "Keep task progress in .kh/development state.",
                    "evidence": ["compound_capture"],
                }
            ],
            compound_handoff={
                "status": "ready_for_system_update",
                "next_skills": ["workflow-skill-distiller", "memory-state-harness"],
            },
            overrides={
                "subagent-review-pipeline": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "Subagent review pipeline ran for the task plan.",
                    "evidence_keys": ["review_status"],
                },
                "role-execution-audit-harness": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "Role results were inspected before release.",
                    "evidence_keys": ["role_execution_audit"],
                },
                "memory-state-harness": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "Project-scoped memory candidates were captured.",
                    "evidence_keys": ["memory_candidates_recorded"],
                    "metadata": {"record_ids": ["memory-001"]},
                },
                "workflow-skill-distiller": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "Repeated workflow was routed for distillation.",
                    "evidence_keys": ["workflow_skill_distiller_applied"],
                    "metadata": {"artifact_path": ".kh/compound/skill-distillation.md"},
                },
            },
        )

        validation = validate_skill_transitions(bundle, phase="final")

        self.assertTrue(validation["valid"], validation)
        self.assertEqual(validation["required_next_skills"], [])

    def test_self_attested_allowed_evidence_key_does_not_satisfy_compound_followup(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Run reviewed workflow and capture learning.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            compound_handoff={
                "status": "ready_for_system_update",
                "next_skills": ["workflow-skill-distiller"],
            },
            overrides={
                "workflow-skill-distiller": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "Generic metadata says distillation was applied.",
                    "evidence_keys": ["workflow_skill_distiller_applied"],
                },
            },
        )

        validation = validate_skill_transitions(bundle, phase="final")

        self.assertFalse(validation["valid"])
        self.assertIn("workflow-skill-distiller", validation["required_next_skills"])
        self.assertEqual(validation["issues"][0]["rule"], "compound_next_skill_requires_followup_evidence")


if __name__ == "__main__":
    unittest.main()
