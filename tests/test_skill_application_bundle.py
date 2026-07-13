import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.orchestration.goal_runtime import GoalRuntime
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
        self.assertEqual(
            serialized["skill_statuses"]["goal-state-harness"]["status"],
            "pending_immediate_execution",
        )

    def test_goal_harness_becomes_applied_only_with_runtime_or_backend_evidence(self):
        missing_evidence = build_large_work_orchestration_bundle(
            objective="Build a Goal runtime.",
            workspace_strategy="host-worktree",
            token_optimizer_status="considered_not_needed",
            overrides={
                "goal-state-harness": {
                    "status": "applied",
                    "application_mode": "procedural",
                    "evidence_note": "Read the goal skill documentation.",
                    "evidence_keys": ["SKILL.md"],
                }
            },
        )
        invalid = validate_large_work_orchestration_bundle(missing_evidence)
        self.assertFalse(invalid["valid"])
        self.assertIn("goal-state-harness.execution_evidence", invalid["missing"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            with patch.dict(os.environ, {"UAF_RUNTIME_ROOT": str(root / "runtime")}, clear=False):
                runtime = GoalRuntime(
                    str(project), thread_id="thread-a", task_id="task-a"
                )
                started = runtime.start(
                    objective="Build a Goal runtime.",
                    success_criteria=["runtime starts"],
                    evidence_required=["runtime start observed"],
                )
                valid_runtime = build_large_work_orchestration_bundle(
                    objective="Build a Goal runtime.",
                    workspace_strategy="host-worktree",
                    token_optimizer_status="considered_not_needed",
                    overrides={
                        "goal-state-harness": {
                            "status": "applied",
                            "application_mode": "runtime",
                            "evidence_note": "KH Goal runtime persisted current_goal.json.",
                            "evidence_keys": ["goal_runtime", "goal_ledger"],
                            "metadata": {
                                "goal_runtime_receipt": started["runtime_receipt"],
                            },
                        }
                    },
                    metadata={
                        "project": str(project),
                        "thread_id": "thread-a",
                        "task_id": "task-a",
                    },
                )
                valid = validate_large_work_orchestration_bundle(
                    valid_runtime,
                    goal_runtime_producer_boundary=runtime.receipt_producer,
                )

        self.assertTrue(valid["valid"], valid)

    def test_goal_harness_rejects_forged_valid_boolean_and_unvalidated_receipt_shape(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Build a Goal runtime.",
            workspace_strategy="host-worktree",
            token_optimizer_status="passthrough",
            overrides={
                "goal-state-harness": {
                    "status": "applied",
                    "application_mode": "runtime",
                    "evidence_note": "Claimed runtime execution without a correlated receipt.",
                    "evidence_keys": ["goal_runtime", "goal_ledger"],
                    "metadata": {
                        "validated": True,
                        "goal_runtime_receipt": {
                            "state_path": "C:/does/not/exist/current_goal.json",
                            "status": "active",
                        },
                    },
                }
            },
            metadata={"project": str(REPO_ROOT), "thread_id": "thread-a"},
        )
        validation = validate_large_work_orchestration_bundle(
            bundle,
            goal_runtime_producer_boundary={"validated": True},
        )

        self.assertFalse(validation["valid"])
        self.assertIn("goal-state-harness.validated_runtime_receipt", validation["missing"])

    def test_parallel_and_role_skills_reject_runtime_applied_claims_without_validated_artifacts(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Run a bounded role DAG.",
            workspace_strategy="host-worktree",
            token_optimizer_status="passthrough",
            overrides={
                "parallel-orchestration-harness": {
                    "status": "applied",
                    "application_mode": "runtime",
                    "evidence_note": "Claimed a parallel wave without runtime artifacts.",
                    "evidence_keys": ["parallel_wave_count"],
                    "metadata": {"validated": True, "parallel_wave_count": 1},
                },
                "role-execution-audit-harness": {
                    "status": "applied",
                    "application_mode": "runtime",
                    "evidence_note": "Claimed role execution without role artifacts.",
                    "evidence_keys": ["role_execution_audit"],
                    "metadata": {"validated": True, "status": "passed"},
                },
            },
        )

        validation = validate_large_work_orchestration_bundle(bundle)

        self.assertFalse(validation["valid"])
        self.assertIn(
            "parallel-orchestration-harness.validated_wave_artifacts",
            validation["missing"],
        )
        self.assertIn(
            "role-execution-audit-harness.validated_role_artifacts",
            validation["missing"],
        )

    def test_parallel_and_role_skills_accept_audited_parallel_wave_and_role_artifacts(self):
        results = [
            {
                "role": "ceo",
                "status": "success",
                "metadata": {"role_artifacts": [{"path": "runtime/ceo.md"}]},
            },
            {
                "role": "advisor",
                "status": "success",
                "metadata": {"role_artifacts": [{"path": "runtime/advisor.md"}]},
            },
        ]
        role_orchestration = {
            "summary": {
                "execution_model": "dag-asyncio-role-waves",
                "success": True,
                "wave_count": 1,
                "parallel_wave_count": 1,
                "runtime_overlap_wave_count": 1,
            },
            "stages": [
                {
                    "waves": [
                        {
                            "parallel": True,
                            "runtime_overlap": True,
                            "roles": ["ceo", "advisor"],
                            "results": results,
                        }
                    ]
                }
            ],
            "results": results,
        }
        execution_metadata = {
            "role_orchestration": role_orchestration,
            "required_roles": ["ceo", "advisor"],
        }
        bundle = build_large_work_orchestration_bundle(
            objective="Run a bounded role DAG.",
            workspace_strategy="host-worktree",
            token_optimizer_status="passthrough",
            overrides={
                "parallel-orchestration-harness": {
                    "status": "applied",
                    "application_mode": "runtime",
                    "evidence_note": "A bounded parallel role wave produced artifacts.",
                    "evidence_keys": ["parallel_wave", "role_artifacts"],
                    "metadata": execution_metadata,
                },
                "role-execution-audit-harness": {
                    "status": "applied",
                    "application_mode": "runtime",
                    "evidence_note": "Role execution audit passed against runtime artifacts.",
                    "evidence_keys": ["role_execution_audit", "role_artifacts"],
                    "metadata": execution_metadata,
                },
            },
        )

        validation = validate_large_work_orchestration_bundle(bundle)

        self.assertTrue(validation["valid"], validation)

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

    def test_validation_rejects_skill_status_as_token_optimizer_usage_status(self):
        bundle = build_large_work_orchestration_bundle(
            objective="Build a SaaS CRM MVP.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="pending_immediate_execution",
            token_optimizer_status_reason="This is a skill gate status, not a token usage status.",
        )

        validation = validate_large_work_orchestration_bundle(bundle)

        self.assertFalse(validation["valid"])
        self.assertIn("token_optimizer_status", validation["missing"])

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
