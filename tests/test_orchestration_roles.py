import json
import unittest

from src.orchestration.roles import (
    build_role_gate_results,
    build_default_role_metadata,
    default_role_graph,
    default_role_profiles,
)


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
            {"role": "implementer", "status": "success", "file_name": "main.py"},
        ])

        self.assertEqual({gate["status"] for gate in gates}, {"passed"})
        self.assertEqual(gates[0]["role"], "spec-reviewer")
        self.assertEqual(gates[-1]["role"], "release-manager")

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


if __name__ == "__main__":
    unittest.main()
