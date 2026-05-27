import os
import unittest

from src.orchestration.roles import build_default_role_metadata
from src.tasks.workflows import _project_id, _safe_worker_count, dispatch_project_workflow


class WorkflowDispatchTests(unittest.TestCase):
    def test_safe_worker_count_never_returns_zero_for_queued_files(self):
        original_workers = os.environ.get("AG_MAX_WORKERS")
        os.environ["AG_MAX_WORKERS"] = "0"

        try:
            self.assertEqual(_safe_worker_count(file_count=3, cpu_count=8), 1)
        finally:
            if original_workers is None:
                os.environ.pop("AG_MAX_WORKERS", None)
            else:
                os.environ["AG_MAX_WORKERS"] = original_workers

    def test_safe_worker_count_handles_invalid_env_value(self):
        original_workers = os.environ.get("AG_MAX_WORKERS")
        os.environ["AG_MAX_WORKERS"] = "not-an-int"

        try:
            self.assertEqual(_safe_worker_count(file_count=3, cpu_count=8), 3)
        finally:
            if original_workers is None:
                os.environ.pop("AG_MAX_WORKERS", None)
            else:
                os.environ["AG_MAX_WORKERS"] = original_workers

    def test_project_id_ignores_trailing_path_separator(self):
        self.assertEqual(_project_id("C:/work/demo/"), "demo")

    def test_webhook_failure_returns_failed_workflow_result(self):
        original_url = os.environ.get("AG_WEBHOOK_URL")
        os.environ["AG_WEBHOOK_URL"] = "http://127.0.0.1:9/api/webhook/subagent-result"

        try:
            result = dispatch_project_workflow(
                project_dir="C:/work/demo",
                file_list=["main.py"],
                design_doc="# design",
                platform_mode="local",
                metadata=build_default_role_metadata(),
            )
        finally:
            if original_url is None:
                os.environ.pop("AG_WEBHOOK_URL", None)
            else:
                os.environ["AG_WEBHOOK_URL"] = original_url

        self.assertEqual(result.workflow_id, "workflow_demo")
        self.assertFalse(result.success)
        self.assertEqual(len(result.task_results), 1)
        self.assertEqual(result.task_results[0].status, "failed")
        self.assertEqual(result.task_results[0].role, "implementer")
        self.assertIn("spec-reviewer", [gate["role"] for gate in result.gate_results])
        self.assertIn("failed", {gate["status"] for gate in result.gate_results})


if __name__ == "__main__":
    unittest.main()
