import unittest
from contextlib import redirect_stdout
from io import StringIO

from src.contracts import AdapterRequest, AdapterResult
from src.platforms.dispatcher_factory import AntigravityDispatcher


class AntigravityDispatcherTests(unittest.TestCase):
    def test_execute_formats_payload_without_name_error(self):
        with redirect_stdout(StringIO()):
            result = AntigravityDispatcher().execute(
                project_dir="C:/work/demo",
                files=["main.py"],
                design_doc="# design",
                platform_mode="antigravity",
            )

        self.assertEqual(len(result), 1)
        self.assertIn("Pending", result[0])

    def test_execute_request_returns_adapter_result(self):
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
        )

        with redirect_stdout(StringIO()):
            result = AntigravityDispatcher().execute_request(request)

        self.assertIsInstance(result, AdapterResult)
        self.assertEqual(result.status, "pending")
        self.assertEqual(result.workflow_id, "demo")

    def test_execute_request_attaches_default_role_graph_metadata(self):
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
        )

        with redirect_stdout(StringIO()):
            result = AntigravityDispatcher().execute_request(request)

        self.assertIn("ceo", result.metadata["orchestration_roles"])
        self.assertIn("advisor", result.metadata["orchestration_roles"])
        self.assertIn("implementer", result.metadata["orchestration_roles"])
        self.assertEqual(result.metadata["role_graph"]["roles"][0]["name"], "ceo")


if __name__ == "__main__":
    unittest.main()
