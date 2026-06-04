import asyncio
import unittest

from src.contracts import WorkflowTaskResult
from src.orchestration.quality_harnesses import audit_role_execution
from src.orchestration.role_orchestrator import RoleOrchestrator


class SlowEvidenceRunner:
    async def run_role(self, profile, context):
        await asyncio.sleep(0.02)
        return WorkflowTaskResult(
            task_id=f"role_{profile.name}",
            file_name=f"role:{profile.name}",
            role=profile.name,
            status="success",
            message=f"{profile.name} completed by slow evidence runner",
            metadata={
                "execution_model": "parallel-role-stage",
                "role_artifacts": [{"path": f"runtime/{profile.name}.md"}],
                "evidence": [f"{profile.name} role task completed"],
            },
        )


class RoleOrchestratorParallelTests(unittest.TestCase):
    def test_role_orchestrator_runs_dependency_ready_roles_in_parallel_wave(self):
        result = RoleOrchestrator(runner=SlowEvidenceRunner()).run_sync(
            context={},
            selected_roles=["ceo", "advisor", "product-strategist"],
        )
        summary = result["context"]["role_orchestration"]
        role_metadata = {
            "summary": {
                **summary,
                "execution_model": "dag-asyncio-role-waves",
            },
            "results": result["context"]["role_task_results"],
        }
        audit = audit_role_execution(
            role_metadata,
            required_roles=["ceo", "advisor", "product-strategist"],
        )

        self.assertTrue(result["success"], result)
        self.assertEqual(summary["execution_model"], "dag-asyncio-role-waves")
        self.assertGreaterEqual(summary["wave_count"], 2)
        self.assertGreaterEqual(summary["parallel_wave_count"], 1)
        self.assertGreaterEqual(summary["runtime_overlap_wave_count"], 1)
        parallel_waves = [wave for wave in result["waves"] if wave.get("parallel")]
        self.assertTrue(parallel_waves)
        self.assertIn("advisor", parallel_waves[0]["roles"])
        self.assertIn("product-strategist", parallel_waves[0]["roles"])
        self.assertEqual(audit["status"], "passed", audit)
        self.assertIn("role execution audited", audit["evidence"])


if __name__ == "__main__":
    unittest.main()
