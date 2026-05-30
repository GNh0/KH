import unittest
from contextlib import redirect_stdout
from io import StringIO

from src.core.app_bridge import create_app_request, dispatch_app_request


class AppBridgeTests(unittest.TestCase):
    def test_create_app_request_attaches_windows_app_context_and_role_graph(self):
        request = create_app_request(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
            app_host="codex",
            thread_id="thread-1",
        )

        self.assertEqual(request.platform_mode, "antigravity")
        self.assertEqual(request.metadata["app_context"]["host"], "codex")
        self.assertEqual(request.metadata["app_context"]["thread_id"], "thread-1")
        self.assertTrue(request.metadata["workflow_usability_auto"])
        self.assertEqual(request.metadata["token_optimizer_provider"], "kh")
        self.assertEqual(request.metadata["workspace_strategy"], "host-worktree")
        self.assertIn("ceo", request.metadata["orchestration_roles"])

    def test_dispatch_app_request_returns_serializable_adapter_result(self):
        request = create_app_request(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
            app_host="antigravity",
        )

        with redirect_stdout(StringIO()):
            result = dispatch_app_request(request)

        self.assertEqual(result["status"], "pending")
        self.assertIn("orchestration_roles", result["metadata"])
        self.assertIn("role_graph", result["metadata"])
        self.assertTrue(result["metadata"]["workflow_usability"]["enabled"])
        self.assertEqual(result["metadata"]["workflow_usability"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
