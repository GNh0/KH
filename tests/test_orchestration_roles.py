import json
import time
import unittest
from dataclasses import dataclass

from src.orchestration.roles import (
    RoleProfile,
    build_role_gate_results,
    build_default_role_metadata,
    default_role_graph,
    default_role_profiles,
)
from src.orchestration.role_orchestrator import RoleOrchestrator
from src.contracts import WorkflowTaskResult


REQUIRED_ROLES = {
    "ceo",
    "advisor",
    "product-strategist",
    "system-architect",
    "implementation-planner",
    "controller",
    "implementer",
    "spec-reviewer",
    "code-quality-reviewer",
    "qa-verifier",
    "security-reviewer",
    "release-manager",
}


@dataclass
class TimedRoleRunner:
    delay_seconds: float = 0.05

    async def run_role(self, profile, context):
        import asyncio

        started_at = time.perf_counter()
        await asyncio.sleep(self.delay_seconds)
        finished_at = time.perf_counter()
        context.setdefault("timings", {})[profile.name] = (started_at, finished_at)
        return WorkflowTaskResult(
            task_id=f"role_{profile.name}",
            file_name=f"role:{profile.name}",
            role=profile.name,
            status="success",
            message=f"{profile.name} completed",
            metadata={
                "started_at": started_at,
                "finished_at": finished_at,
                "execution_model": "parallel-role-stage",
            },
        )


class OrchestrationRoleGraphTests(unittest.TestCase):
    def test_default_role_profiles_include_required_orchestration_roles(self):
        profiles = default_role_profiles()
        names = {profile.name for profile in profiles}

        self.assertEqual(len(names), len(profiles))
        self.assertTrue(REQUIRED_ROLES.issubset(names))

        for profile in profiles:
            self.assertTrue(profile.title)
            self.assertTrue(profile.stage)
            self.assertTrue(profile.purpose)
            self.assertTrue(profile.responsibilities)
            self.assertTrue(profile.outputs)

    def test_default_role_graph_orders_governance_before_delivery_and_release(self):
        graph = default_role_graph()
        stage_order = graph["stage_order"]

        self.assertLess(stage_order.index("executive"), stage_order.index("advisory"))
        self.assertLess(stage_order.index("advisory"), stage_order.index("architecture"))
        self.assertLess(stage_order.index("architecture"), stage_order.index("planning"))
        self.assertLess(stage_order.index("planning"), stage_order.index("implementation"))
        self.assertLess(stage_order.index("implementation"), stage_order.index("review"))
        self.assertLess(stage_order.index("review"), stage_order.index("release"))

        self.assertIn("ceo", graph["stages"]["executive"])
        self.assertIn("advisor", graph["stages"]["advisory"])
        self.assertIn("implementer", graph["stages"]["implementation"])
        self.assertIn("spec-reviewer", graph["stages"]["review"])
        self.assertIn("code-quality-reviewer", graph["stages"]["review"])

    def test_controller_and_review_roles_have_expected_execution_flags(self):
        profiles = {profile.name: profile for profile in default_role_profiles()}

        self.assertFalse(profiles["controller"].fanout_safe)
        self.assertTrue(profiles["implementer"].fanout_safe)
        self.assertFalse(profiles["ceo"].fanout_safe)
        self.assertIn("implementer", profiles["spec-reviewer"].blocks_on)
        self.assertIn("spec-reviewer", profiles["code-quality-reviewer"].blocks_on)

    def test_default_role_metadata_is_adapter_serializable(self):
        metadata = build_default_role_metadata()

        json.dumps(metadata)
        self.assertEqual(metadata["role_count"], len(REQUIRED_ROLES))
        self.assertEqual(metadata["orchestration_roles"][0], "ceo")
        self.assertEqual(metadata["orchestration_roles"][-1], "release-manager")
        self.assertEqual(metadata["role_graph"]["roles"][0]["name"], "ceo")

    def test_role_gate_results_pass_when_implementer_tasks_succeed(self):
        gates = build_role_gate_results([
            {
                "role": "implementer",
                "status": "success",
                "file_name": "main.py",
                "metadata": {"evidence": ["task runner completed", "target file generated:main.py"]},
            },
        ])

        self.assertEqual({gate["status"] for gate in gates}, {"passed"})
        self.assertEqual(gates[0]["role"], "spec-reviewer")
        self.assertEqual(gates[-1]["role"], "release-manager")
        self.assertIn("evidence_records", gates[0])
        self.assertIn("evidence_records", gates[-1])

    def test_role_gate_results_block_downstream_when_implementer_fails(self):
        gates = build_role_gate_results([
            {"role": "implementer", "status": "failed", "file_name": "main.py"},
        ])

        statuses = {gate["role"]: gate["status"] for gate in gates}
        self.assertEqual(statuses["spec-reviewer"], "failed")
        self.assertEqual(statuses["code-quality-reviewer"], "blocked")
        self.assertEqual(statuses["qa-verifier"], "blocked")
        self.assertEqual(statuses["security-reviewer"], "blocked")
        self.assertEqual(statuses["release-manager"], "blocked")

    def test_role_gate_results_block_qa_and_release_when_goal_evidence_is_missing(self):
        gates = build_role_gate_results(
            [
                {
                    "role": "implementer",
                    "status": "success",
                    "file_name": "main.py",
                    "metadata": {"evidence": ["task runner completed", "target file generated:main.py"]},
                }
            ],
            goal={
                "objective": "build api",
                "status": "blocked",
                "blocked_reason": "missing required evidence: tests",
                "metadata": {"missing_evidence": ["tests"]},
            },
        )

        statuses = {gate["role"]: gate["status"] for gate in gates}
        self.assertEqual(statuses["spec-reviewer"], "passed")
        self.assertEqual(statuses["code-quality-reviewer"], "passed")
        self.assertEqual(statuses["qa-verifier"], "blocked")
        self.assertEqual(statuses["security-reviewer"], "passed")
        self.assertEqual(statuses["release-manager"], "blocked")

        qa_gate = next(gate for gate in gates if gate["role"] == "qa-verifier")
        release_gate = next(gate for gate in gates if gate["role"] == "release-manager")
        self.assertEqual(qa_gate["missing_evidence"], ["tests"])
        self.assertEqual(release_gate["missing_evidence"], ["tests"])
        self.assertIn("missing goal evidence", qa_gate["message"])

    def test_role_orchestrator_runs_ready_roles_in_parallel_waves(self):
        profiles = (
            RoleProfile(
                name="root",
                title="Root",
                stage="planning",
                purpose="start",
                responsibilities=("start",),
                inputs=(),
                outputs=("root output",),
            ),
            RoleProfile(
                name="parallel-a",
                title="Parallel A",
                stage="review",
                purpose="branch a",
                responsibilities=("branch",),
                inputs=("root output",),
                outputs=("a",),
                blocks_on=("root",),
            ),
            RoleProfile(
                name="parallel-b",
                title="Parallel B",
                stage="review",
                purpose="branch b",
                responsibilities=("branch",),
                inputs=("root output",),
                outputs=("b",),
                blocks_on=("root",),
            ),
            RoleProfile(
                name="join",
                title="Join",
                stage="release",
                purpose="join",
                responsibilities=("join",),
                inputs=("a", "b"),
                outputs=("done",),
                blocks_on=("parallel-a", "parallel-b"),
            ),
        )
        runner = TimedRoleRunner(delay_seconds=0.08)
        started_at = time.perf_counter()
        result = RoleOrchestrator(profiles, runner=runner).run_sync({})
        elapsed = time.perf_counter() - started_at

        self.assertTrue(result["success"])
        self.assertLess(elapsed, 0.30)
        self.assertEqual(
            [[item["role"] for item in wave["results"]] for wave in result["waves"]],
            [["root"], ["parallel-a", "parallel-b"], ["join"]],
        )
        timing_a = result["context"]["timings"]["parallel-a"]
        timing_b = result["context"]["timings"]["parallel-b"]
        self.assertLess(abs(timing_a[0] - timing_b[0]), 0.04)
        self.assertLess(max(timing_a[1], timing_b[1]) - min(timing_a[0], timing_b[0]), 0.14)


if __name__ == "__main__":
    unittest.main()
