import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.orchestration.git_workspace_gate import (
    authorize_git_action,
    authorize_git_argv,
    inspect_git_workspace,
)


class GitWorkspaceGateTests(unittest.TestCase):
    @staticmethod
    def _make_common_git_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "HEAD").write_text("ref: refs/heads/main\n", encoding="ascii")
        (path / "objects").mkdir()
        (path / "refs").mkdir()

    def test_non_git_directory_blocks_all_repository_actions_without_process(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("subprocess.run") as run:
                probe = inspect_git_workspace(temp_dir)
                status = authorize_git_action(temp_dir, "status")
                commit = authorize_git_action(
                    temp_dir,
                    "commit",
                    mutation_authorized=True,
                )
                push = authorize_git_action(
                    temp_dir,
                    "push",
                    mutation_authorized=True,
                )

            run.assert_not_called()
            self.assertEqual(probe.status, "not_git_backed")
            self.assertFalse(probe.git_process_allowed)
            self.assertFalse(status["allowed"])
            self.assertFalse(commit["allowed"])
            self.assertFalse(push["allowed"])

    def test_git_directory_allows_read_only_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_common_git_dir(root / ".git")
            nested = root / "src" / "feature"
            nested.mkdir(parents=True)

            probe = inspect_git_workspace(nested)
            status = authorize_git_action(nested, "status")

            self.assertTrue(probe.is_git_backed)
            self.assertEqual(probe.marker_kind, "directory")
            self.assertTrue(status["allowed"])

    def test_valid_worktree_file_allows_read_only_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            common_dir = root / "metadata"
            self._make_common_git_dir(common_dir)
            git_dir = common_dir / "worktrees" / "task"
            git_dir.mkdir(parents=True)
            (git_dir / "HEAD").write_text("ref: refs/heads/task\n", encoding="ascii")
            (git_dir / "commondir").write_text("../..\n", encoding="ascii")
            worktree = root / "task"
            worktree.mkdir()
            (worktree / ".git").write_text(
                "gitdir: ../metadata/worktrees/task\n",
                encoding="utf-8",
            )

            probe = inspect_git_workspace(worktree)

            self.assertTrue(probe.is_git_backed)
            self.assertEqual(probe.marker_kind, "worktree-file")
            self.assertEqual(Path(probe.git_dir), git_dir.resolve())

    def test_invalid_worktree_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").write_text("not-a-gitdir-pointer\n", encoding="utf-8")

            probe = inspect_git_workspace(root)

            self.assertEqual(probe.status, "invalid_git_marker")
            self.assertFalse(probe.git_process_allowed)

    def test_mutating_actions_require_explicit_authorization(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_common_git_dir(root / ".git")

            denied = authorize_git_action(root, "push")
            allowed = authorize_git_action(root, "push", mutation_authorized=True)

            self.assertFalse(denied["allowed"])
            self.assertEqual(denied["action_kind"], "mutation")
            self.assertTrue(allowed["allowed"])

    def test_unknown_or_composed_action_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._make_common_git_dir(root / ".git")

            self.assertFalse(authorize_git_action(root, "status;push")["allowed"])
            self.assertFalse(authorize_git_action(root, "unknown")["allowed"])

    def test_empty_git_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".git").mkdir()

            probe = inspect_git_workspace(root)

            self.assertEqual(probe.status, "invalid_git_marker")
            self.assertFalse(probe.git_process_allowed)

    def test_malformed_head_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            git_dir = root / ".git"
            self._make_common_git_dir(git_dir)
            (git_dir / "HEAD").write_text("not-a-ref-or-object-id\n", encoding="ascii")

            probe = inspect_git_workspace(root)

            self.assertEqual(probe.status, "invalid_git_marker")
            self.assertFalse(probe.git_process_allowed)

    def test_worktree_pointer_to_plain_directory_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fake_target = root / "plain-directory"
            fake_target.mkdir()
            worktree = root / "task"
            worktree.mkdir()
            (worktree / ".git").write_text(
                "gitdir: ../plain-directory\n",
                encoding="utf-8",
            )

            probe = inspect_git_workspace(worktree)

            self.assertEqual(probe.status, "invalid_git_marker")
            self.assertFalse(probe.git_process_allowed)

    def test_bootstrap_action_requires_explicit_authorization_without_repository(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            pending = authorize_git_action(temp_dir, "init")
            allowed = authorize_git_action(
                temp_dir,
                "init",
                mutation_authorized=True,
            )

            self.assertEqual(pending["verdict"], "ask")
            self.assertTrue(pending["requires_confirmation"])
            self.assertTrue(allowed["allowed"])

    def test_structured_argv_uses_dash_c_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            repo.mkdir()
            self._make_common_git_dir(repo / ".git")
            plain = root / "plain"
            plain.mkdir()

            blocked = authorize_git_argv(
                repo,
                ["git", "-C", str(plain), "status"],
            )
            allowed = authorize_git_argv(
                plain,
                ["git.exe", "-C", str(repo), "status"],
            )

            self.assertFalse(blocked["allowed"])
            self.assertTrue(allowed["allowed"])
            self.assertEqual(blocked["effective_project"], str(plain.resolve()))

    def test_structured_shell_wrapper_with_git_is_denied(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            decision = authorize_git_argv(
                temp_dir,
                ["powershell", "-NoProfile", "-Command", "git status"],
            )

            self.assertFalse(decision["allowed"])
            self.assertEqual(decision["target_source"], "wrapped_git_command")

    def test_cli_reports_blocked_without_running_git(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            command = [
                sys.executable,
                "-m",
                "src.orchestration.git_workspace_gate",
                "--project",
                temp_dir,
                "--action",
                "status",
            ]
            result = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 3)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["allowed"])
            self.assertEqual(payload["probe"]["status"], "not_git_backed")

    def test_lifecycle_instructions_require_filesystem_first_gate(self):
        root = Path(__file__).resolve().parents[1]
        required_skills = [
            "branch_finishing_harness",
            "command_hook_policy_harness",
            "context_state_harness",
            "development_lifecycle_harness",
            "verification_before_completion_harness",
            "worktree_isolation_harness",
        ]
        for skill_name in required_skills:
            skill = (root / "skills" / skill_name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("git_workspace_gate", skill)

        codex_manifest = (root / ".codex-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
        self.assertIn("filesystem-only workspace gate", codex_manifest)
        self.assertIn("Non-Git targets run no Git/GitHub commands or retries", codex_manifest)

        front_door = (root / "skills" / "always_on_front_door" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("git_workspace_gate", front_door)
        self.assertIn("Do not launch `git.exe`", front_door)


if __name__ == "__main__":
    unittest.main()
