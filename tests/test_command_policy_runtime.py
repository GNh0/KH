import unittest
import tempfile
from pathlib import Path

from src.skills.command_policy import (
    build_command_audit_record,
    classify_command,
    evaluate_command_hook_policy,
    evaluate_guard_policy,
    evaluate_write_boundary,
    load_command_policy,
)


class CommandPolicyRuntimeTests(unittest.TestCase):
    @staticmethod
    def _make_git_dir(root: Path) -> None:
        git_dir = root / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="ascii")
        (git_dir / "objects").mkdir()
        (git_dir / "refs").mkdir()

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

    def test_command_hook_denies_git_status_outside_git_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            decision = evaluate_command_hook_policy("git status", cwd=temp_dir)

        self.assertEqual(decision["verdict"], "deny")
        self.assertFalse(decision["requires_confirmation"])
        self.assertEqual(
            decision["git_workspace_gate"]["probe"]["status"],
            "not_git_backed",
        )
        self.assertFalse(decision["git_workspace_gate"]["allowed"])

    def test_command_hook_allows_git_status_in_verified_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_git_dir(root)

            decision = evaluate_command_hook_policy("git status", cwd=str(root))

        self.assertEqual(decision["verdict"], "allow")
        self.assertTrue(decision["git_workspace_gate"]["allowed"])

    def test_command_hook_requires_approval_for_git_push(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_git_dir(root)

            denied = evaluate_command_hook_policy("git push origin main", cwd=str(root))
            allowed = evaluate_command_hook_policy(
                "git push origin main",
                cwd=str(root),
                approved=True,
            )

        self.assertEqual(denied["verdict"], "ask")
        self.assertTrue(denied["requires_confirmation"])
        self.assertTrue(allowed["git_workspace_gate"]["allowed"])
        self.assertTrue(allowed["git_workspace_gate"]["allowed"])

    def test_command_hook_fails_closed_when_git_workspace_path_is_missing(self):
        decision = evaluate_command_hook_policy("git status")

        self.assertEqual(decision["verdict"], "deny")
        self.assertEqual(
            decision["git_workspace_gate"]["probe"]["status"],
            "missing_workspace_path",
        )

    def test_command_hook_checks_every_git_segment(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_git_dir(root)

            decision = evaluate_command_hook_policy(
                "git status; git push origin main",
                cwd=str(root),
            )

        self.assertEqual(decision["verdict"], "ask")
        self.assertEqual(
            decision["git_workspace_gate"]["actions"],
            ["status", "push"],
        )

    def test_command_hook_recognizes_git_dash_c_and_common_shell_wrapper(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dash_c = evaluate_command_hook_policy(
                f'git -C "{temp_dir}" status',
                cwd=temp_dir,
            )
            wrapped = evaluate_command_hook_policy(
                "cmd /c git status",
                cwd=temp_dir,
            )

        self.assertEqual(dash_c["verdict"], "deny")
        self.assertEqual(wrapped["verdict"], "deny")
        self.assertEqual(dash_c["git_workspace_gate"]["action"], "status")
        self.assertEqual(wrapped["git_workspace_gate"]["action"], "status")

    def test_git_dash_c_uses_effective_target_instead_of_cwd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            self._make_git_dir(repo)
            plain = root / "plain"
            plain.mkdir()

            blocked = evaluate_command_hook_policy(
                f'git -C "{plain}" status',
                cwd=str(repo),
            )
            allowed = evaluate_command_hook_policy(
                f'git -C "{repo}" status',
                cwd=str(plain),
            )

        self.assertEqual(blocked["verdict"], "deny")
        self.assertTrue(allowed["git_workspace_gate"]["allowed"])
        self.assertEqual(
            blocked["git_workspace_gate"]["effective_project"],
            str(plain.resolve()),
        )

    def test_shell_directory_change_updates_git_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            self._make_git_dir(repo)
            plain = root / "plain"
            plain.mkdir()

            decision = evaluate_command_hook_policy(
                f'cd "{plain}" && git status',
                cwd=str(repo),
            )

        self.assertEqual(decision["verdict"], "deny")
        self.assertEqual(
            decision["git_workspace_gate"]["probe"]["status"],
            "not_git_backed",
        )

    def test_common_wrappers_and_parenthesized_git_are_gated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            commands = [
                'powershell -NoProfile -Command "git status"',
                'cmd /s /c "git status"',
                "(git status)",
                "call git status",
            ]
            decisions = [
                evaluate_command_hook_policy(command, cwd=temp_dir)
                for command in commands
            ]

        self.assertTrue(all(decision["verdict"] == "deny" for decision in decisions))
        self.assertTrue(
            all(decision["git_workspace_gate"]["action"] == "status" for decision in decisions)
        )

    def test_wrapper_payload_is_recursively_segmented(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            self._make_git_dir(repo)
            plain = root / "plain"
            plain.mkdir()

            changed_dir = evaluate_command_hook_policy(
                f'powershell -Command "cd {plain}; git status"',
                cwd=str(repo),
            )
            quoted_git = evaluate_command_hook_policy(
                "powershell -Command \"& 'git.exe' status\"",
                cwd=str(plain),
            )

        self.assertEqual(changed_dir["verdict"], "deny")
        self.assertEqual(quoted_git["verdict"], "deny")

    def test_quoted_non_git_text_is_not_misclassified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            decision = evaluate_command_hook_policy(
                'python -c "print(\'x; git status\')"',
                cwd=temp_dir,
            )

        self.assertEqual(decision["git_workspace_gate"], {})

    def test_command_hook_fails_closed_for_unparsed_git_global_options(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            recognized = evaluate_command_hook_policy(
                "git --no-pager status",
                cwd=temp_dir,
            )
            unknown = evaluate_command_hook_policy(
                "git --future-option status",
                cwd=temp_dir,
            )

        self.assertEqual(recognized["verdict"], "deny")
        self.assertEqual(recognized["git_workspace_gate"]["action"], "status")
        self.assertEqual(unknown["verdict"], "deny")
        self.assertEqual(unknown["git_workspace_gate"]["action"], "unparsed")

    def test_command_hook_keeps_explicit_git_init_available_for_approval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pending = evaluate_command_hook_policy("git init", cwd=temp_dir)
            allowed = evaluate_command_hook_policy(
                "git init",
                cwd=temp_dir,
                approved=True,
            )

        self.assertEqual(pending["verdict"], "ask")
        self.assertTrue(pending["requires_confirmation"])
        self.assertEqual(allowed["verdict"], "allow")

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
