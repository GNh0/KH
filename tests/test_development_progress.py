import tempfile
import unittest
from pathlib import Path

from src.orchestration.development_progress import (
    DevelopmentRunProgress,
    DevelopmentTaskProgress,
    build_development_progress,
    development_progress_path,
    final_report_fields,
    read_development_progress,
    validate_development_progress,
    write_development_progress,
)


class DevelopmentProgressTests(unittest.TestCase):
    def test_progress_json_uses_project_local_kh_development_state_path(self):
        progress = build_development_progress(
            run_id="run-001",
            objective="Build PipePilot MVP.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            token_optimizer_status_reason="Token optimizer used; runtime telemetry is available.",
            task_items=[
                {
                    "task_id": "task-1",
                    "title": "Scaffold baseline",
                    "status": "complete",
                    "red_status": "not_applicable",
                    "green_status": "passed",
                    "spec_review_status": "passed",
                    "code_quality_review_status": "passed",
                    "commit_sha": "abc1234",
                }
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = write_development_progress(tmp, progress)
            loaded = read_development_progress(path)

            self.assertEqual(
                path,
                Path(tmp) / ".kh" / "development" / "run-001" / "state" / "progress.json",
            )
            self.assertEqual(development_progress_path(tmp, "run-001"), path)
            self.assertEqual(loaded.to_dict(), progress.to_dict())

    def test_complete_task_requires_red_green_review_and_commit_evidence(self):
        progress = DevelopmentRunProgress(
            run_id="run-002",
            objective="Build a CRM task.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            token_optimizer_status_reason="Token optimizer used; runtime telemetry is available.",
            tasks=[
                DevelopmentTaskProgress(
                    task_id="task-1",
                    title="Add validation",
                    status="complete",
                    green_status="passed",
                    spec_review_status="passed",
                    code_quality_review_status="passed",
                )
            ],
        )

        validation = validate_development_progress(progress)

        self.assertFalse(validation["valid"])
        self.assertIn("tasks.task-1.red_status", validation["missing"])
        self.assertIn("tasks.task-1.commit_sha", validation["missing"])

    def test_final_report_fields_are_stable_and_derive_next_task(self):
        progress = DevelopmentRunProgress(
            run_id="run-003",
            objective="Build PipePilot MVP.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            token_optimizer_status_reason="Token optimizer used; runtime telemetry is available.",
            skill_statuses={"development-lifecycle-harness": {"status": "applied"}},
            tasks=[
                DevelopmentTaskProgress(
                    task_id="task-1",
                    title="Done task",
                    status="complete",
                    red_status="failed_expected",
                    green_status="passed",
                    spec_review_status="passed",
                    code_quality_review_status="passed",
                    commit_sha="abc1234",
                ),
                DevelopmentTaskProgress(
                    task_id="task-2",
                    title="Next task",
                    status="in_progress",
                    red_status="failed_expected",
                ),
            ],
        )

        validation = validate_development_progress(progress)
        fields = final_report_fields(progress)

        self.assertTrue(validation["valid"], validation)
        self.assertEqual(fields["task_status"], "in_progress")
        self.assertEqual(fields["review_status"], "passed")
        self.assertEqual(fields["commit_sha"], "abc1234")
        self.assertEqual(fields["next_task"], "task-2")
        self.assertEqual(fields["workspace_strategy"], "project-local-worktree")
        self.assertEqual(fields["token_optimizer_status"], "used")
        self.assertEqual(fields["token_optimizer_status_reason"], "Token optimizer used; runtime telemetry is available.")
        self.assertIn("skill_statuses", fields)

    def test_reviewer_with_fixes_requires_fix_and_re_review(self):
        progress = DevelopmentRunProgress(
            run_id="run-004",
            objective="Close a review finding.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="used",
            token_optimizer_status_reason="Token optimizer used; runtime telemetry is available.",
            tasks=[
                DevelopmentTaskProgress(
                    task_id="task-1",
                    title="Fix review finding",
                    status="fixing",
                    red_status="failed_expected",
                    green_status="passed",
                    spec_review_status="passed",
                    code_quality_review_status="with_fixes",
                )
            ],
        )

        validation = validate_development_progress(progress)

        self.assertFalse(validation["valid"])
        self.assertIn("tasks.task-1.fix_status", validation["missing"])
        self.assertIn("tasks.task-1.re_review_status", validation["missing"])

    def test_token_optimizer_status_is_required_for_progress_state(self):
        progress = DevelopmentRunProgress(
            run_id="run-005",
            objective="Track a large task-plan run.",
            workspace_strategy="project-local-worktree",
            tasks=[
                DevelopmentTaskProgress(
                    task_id="task-1",
                    title="Start task",
                    status="in_progress",
                )
            ],
        )

        validation = validate_development_progress(progress)

        self.assertFalse(validation["valid"])
        self.assertIn("token_optimizer_status", validation["missing"])

    def test_token_optimizer_status_reason_is_required_for_progress_state(self):
        progress = DevelopmentRunProgress(
            run_id="run-006",
            objective="Track a token decision.",
            workspace_strategy="project-local-worktree",
            token_optimizer_status="considered_not_needed",
            tasks=[
                DevelopmentTaskProgress(
                    task_id="task-1",
                    title="Start task",
                    status="in_progress",
                )
            ],
        )

        validation = validate_development_progress(progress)

        self.assertFalse(validation["valid"])
        self.assertIn("token_optimizer_status_reason", validation["missing"])


if __name__ == "__main__":
    unittest.main()
