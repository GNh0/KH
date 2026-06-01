import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

EXTERNAL_BENCHMARK_TARGETS = [
    "adapter_contract_harness",
    "architect_pipeline",
    "brainstorming_harness",
    "artifact_render_qa_harness",
    "command_hook_policy_harness",
    "command_output_harness",
    "compound_engineering_harness",
    "context_state_harness",
    "deliverable_template_quality_harness",
    "development_lifecycle_harness",
    "domain_orchestration_harness",
    "goal_state_harness",
    "guard_policy_harness",
    "harness_evaluator",
    "health_check_harness",
    "host_agent_orchestration",
    "memory_state_harness",
    "orchestration_role_graph",
    "parallel_orchestration_harness",
    "qa_gate_harness",
    "quality_gates_harness",
    "review_gate_harness",
    "request_complexity_router",
    "scenario_evaluation_harness",
    "role_execution_audit_harness",
    "skill_catalog",
    "snapshot_state_harness",
    "subagent_review_pipeline",
    "token_optimizer",
    "traceability_matrix_harness",
    "workflow_skill_distiller",
]


class ExternalQualityBenchmarkTests(unittest.TestCase):
    def test_all_packaged_skills_have_pressure_recipes(self):
        for skill_dir in EXTERNAL_BENCHMARK_TARGETS:
            with self.subTest(skill=skill_dir):
                skill_path = REPO_ROOT / "skills" / skill_dir / "SKILL.md"
                text = skill_path.read_text(encoding="utf-8")

                self.assertIn("## External Benchmark Recipe", text)
                self.assertIn("Pressure scenario:", text)
                self.assertIn("## Required outputs", text)
                self.assertIn("## Common mistakes", text)

    def test_external_benchmark_audit_records_8_5_minimum(self):
        audit_path = REPO_ROOT / "docs" / "skillbook" / "audits" / "2026-05-29-external-benchmark-8-5.md"
        text = audit_path.read_text(encoding="utf-8")

        self.assertIn("Minimum external score: 8.5", text)
        self.assertIn("Low-score skills below 8.5: none", text)
        for skill_dir in EXTERNAL_BENCHMARK_TARGETS:
            skill_name = skill_dir.replace("_", "-")
            self.assertIn(skill_name, text)


if __name__ == "__main__":
    unittest.main()
