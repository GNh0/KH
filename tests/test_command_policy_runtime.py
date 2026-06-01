import unittest

from src.skills.command_policy import (
    build_command_audit_record,
    classify_command,
    evaluate_command_hook_policy,
    evaluate_guard_policy,
    evaluate_write_boundary,
    load_command_policy,
)


class CommandPolicyRuntimeTests(unittest.TestCase):
    def test_read_only_command_is_allowed_by_default(self):
        decision = classify_command("Get-ChildItem -Recurse")

        self.assertEqual(decision["primary_category"], "read")
        self.assertIn("read", decision["categories"])
        self.assertEqual(decision["risk_level"], "low")
        self.assertEqual(decision["verdict"], "allow")
        self.assertFalse(decision["requires_confirmation"])

    def test_destructive_recursive_delete_requires_confirmation(self):
        decision = classify_command("Remove-Item -LiteralPath C:\\work\\tmp -Recurse -Force")

        self.assertIn("destructive", decision["categories"])
        self.assertEqual(decision["risk_level"], "high")
        self.assertEqual(decision["verdict"], "ask")
        self.assertTrue(decision["requires_confirmation"])
        self.assertTrue(any("recursive delete" in reason for reason in decision["reasons"]))

    def test_force_push_is_high_risk(self):
        decision = evaluate_guard_policy("git push --force origin main")

        self.assertIn("destructive", decision["classification"]["categories"])
        self.assertEqual(decision["verdict"], "ask")
        self.assertTrue(decision["requires_confirmation"])
        self.assertIn("git force", " ".join(decision["classification"]["reasons"]))

    def test_approved_high_risk_command_records_override(self):
        decision = evaluate_guard_policy("git reset --hard HEAD~1", approved=True, actor="tester")

        self.assertEqual(decision["verdict"], "allow")
        self.assertTrue(decision["override"])
        self.assertEqual(decision["audit"]["actor"], "tester")
        self.assertEqual(decision["audit"]["original_verdict"], "ask")

    def test_credential_like_values_are_redacted(self):
        decision = classify_command('curl https://example.test -H "Authorization: Bearer abc123"')

        self.assertIn("network", decision["categories"])
        self.assertIn("credential", decision["categories"])
        self.assertNotIn("abc123", decision["redacted_command"])
        self.assertIn("<redacted>", decision["redacted_command"])

    def test_write_boundary_denies_paths_outside_allowed_roots(self):
        decision = evaluate_write_boundary(
            target_path="C:\\Users\\KONEIT\\Desktop\\other\\file.txt",
            allowed_roots=["C:\\Users\\KONEIT\\Desktop\\Jang\\KH"],
        )

        self.assertEqual(decision["verdict"], "deny")
        self.assertFalse(decision["within_boundary"])

    def test_command_hook_policy_loads_policy_and_records_rewrite_decision(self):
        policy = load_command_policy(
            {
                "source": "project-policy",
                "rewrite_rules": [
                    {"pattern": "pytest", "replacement": "python -m pytest"},
                ],
            }
        )

        decision = evaluate_command_hook_policy("pytest tests", policy=policy, actor="tester")

        self.assertEqual(decision["policy"]["source"], "project-policy")
        self.assertEqual(decision["rewrite"]["rewritten_command"], "python -m pytest tests")
        self.assertEqual(decision["audit"]["actor"], "tester")
        self.assertEqual(decision["integrity"]["status"], "verified")

    def test_command_audit_record_redacts_original_and_final_commands(self):
        record = build_command_audit_record(
            command="curl https://example.test -H \"Authorization: Bearer abc123\"",
            final_command="curl https://example.test -H \"Authorization: Bearer abc123\"",
            verdict="ask",
            actor="tester",
            reasons=["credential"],
        )

        self.assertNotIn("abc123", record["original_command"])
        self.assertNotIn("abc123", record["final_command"])
        self.assertEqual(record["final_verdict"], "ask")


if __name__ == "__main__":
    unittest.main()
