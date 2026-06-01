import os
import sys
import unittest
import tempfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from src.contracts import AdapterRequest, AdapterResult, WorkflowTaskResult
from src.platforms.antigravity_native import AntigravityNativeDispatchResult
from src.platforms.dispatcher_factory import AntigravityDispatcher, DispatcherFactory, LocalDispatcher


class StaticAntigravityNativeAdapter:
    name = "static-native"

    def __init__(self, result):
        self.result = result
        self.requests = []

    def dispatch(self, request):
        self.requests.append(request)
        return self.result


class DispatcherFactoryTests(unittest.TestCase):
    def tearDown(self):
        DispatcherFactory.reset_registry_for_tests()

    def test_custom_dispatcher_can_be_registered(self):
        class CustomDispatcher:
            pass

        dispatcher = CustomDispatcher()
        DispatcherFactory.register_dispatcher("custom-host", lambda: dispatcher)

        self.assertIs(DispatcherFactory.get_dispatcher("custom-host"), dispatcher)

    def test_default_dispatchers_are_registered(self):
        self.assertIsInstance(DispatcherFactory.get_dispatcher("local"), LocalDispatcher)
        self.assertIsInstance(DispatcherFactory.get_dispatcher("antigravity"), AntigravityDispatcher)


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

    def test_execute_request_preserves_goal_metadata(self):
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
            metadata={
                "goal": {
                    "objective": "build api",
                    "status": "active",
                }
            },
        )

        with redirect_stdout(StringIO()):
            result = AntigravityDispatcher().execute_request(request)

        self.assertEqual(result.metadata["goal"]["objective"], "build api")
        self.assertEqual(result.metadata["goal"]["status"], "active")

    def test_execute_request_preserves_memory_and_evidence_metadata_when_pending(self):
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
            metadata={
                "memory_context": {"records": [{"record_id": "decision-1"}]},
                "evidence": ["input evidence"],
            },
        )

        with redirect_stdout(StringIO()):
            result = AntigravityDispatcher().execute_request(request)

        self.assertEqual(result.metadata["memory_context"]["records"][0]["record_id"], "decision-1")
        self.assertEqual(result.metadata["evidence"], ["input evidence"])
        self.assertEqual(result.metadata["request_metadata"]["memory_context"]["records"][0]["record_id"], "decision-1")

    def test_execute_request_uses_native_adapter_success(self):
        native_result = AntigravityNativeDispatchResult(
            status="success",
            message="native completed",
            task_results=[
                WorkflowTaskResult(
                    task_id="main_py",
                    file_name="main.py",
                    role="implementer",
                    status="success",
                    message="generated natively",
                    metadata={
                        "evidence": [
                            "native dispatch completed",
                            "code generated",
                        ],
                    },
                )
            ],
            metadata={"host": "antigravity"},
        )
        adapter = StaticAntigravityNativeAdapter(native_result)
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
            metadata={
                "goal": {
                    "objective": "build api",
                    "status": "active",
                    "evidence_required": [
                        "design_doc",
                        "target_files",
                        "native dispatch completed",
                        "code generated",
                    ],
                    "evidence": [],
                }
            },
        )

        with redirect_stdout(StringIO()):
            result = AntigravityDispatcher(native_adapter=adapter).execute_request(request)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.message, "native completed")
        self.assertEqual(result.metadata["native_dispatch"]["adapter"], "static-native")
        self.assertEqual(result.metadata["goal"]["status"], "complete")
        self.assertEqual({gate["status"] for gate in result.metadata["gate_results"]}, {"passed"})
        self.assertEqual(adapter.requests[0], request)

    def test_execute_request_uses_native_adapter_blocked_result(self):
        native_result = AntigravityNativeDispatchResult(
            status="blocked",
            message="needs host permission",
            task_results=[
                WorkflowTaskResult(
                    task_id="main_py",
                    file_name="main.py",
                    role="implementer",
                    status="blocked",
                    message="needs host permission",
                    metadata={"evidence": []},
                )
            ],
        )
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
            metadata={
                "goal": {
                    "objective": "build api",
                    "status": "active",
                    "evidence_required": ["native dispatch completed"],
                    "evidence": [],
                }
            },
        )

        with redirect_stdout(StringIO()):
            result = AntigravityDispatcher(
                native_adapter=StaticAntigravityNativeAdapter(native_result)
            ).execute_request(request)

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.metadata["goal"]["status"], "blocked")
        self.assertEqual(result.metadata["task_results"][0]["status"], "blocked")
        self.assertEqual(result.metadata["gate_results"][0]["status"], "failed")

    def test_execute_request_uses_native_sidecar_from_metadata(self):
        script = (
            "import json, sys; "
            "request=json.load(sys.stdin); "
            "print(json.dumps({"
            "'status':'success',"
            "'message':'sidecar completed',"
            "'task_results':[{'task_id':'main_py','file_name':request['files'][0],'role':'implementer','status':'success','message':'generated','metadata':{'evidence':['native dispatch completed','code generated']}}],"
            "'metadata':{'host':'fake-antigravity'}"
            "}))"
        )
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
            metadata={
                "antigravity_native_sidecar": {
                    "command": [sys.executable, "-c", script],
                },
                "goal": {
                    "objective": "build api",
                    "status": "active",
                    "evidence_required": [
                        "design_doc",
                        "target_files",
                        "native dispatch completed",
                        "code generated",
                    ],
                    "evidence": [],
                },
            },
        )

        with redirect_stdout(StringIO()):
            result = AntigravityDispatcher().execute_request(request)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.message, "sidecar completed")
        self.assertEqual(result.metadata["native_dispatch"]["adapter"], "antigravity-native-sidecar")
        self.assertEqual(result.metadata["native_dispatch"]["metadata"]["host"], "fake-antigravity")


class LocalDispatcherTests(unittest.TestCase):
    def test_execute_request_exposes_evaluated_goal_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            request = AdapterRequest(
                project_dir=str(project_dir),
                files=[],
                design_doc="# design",
                platform_mode="local",
                metadata={
                    "goal": {
                        "objective": "build api",
                        "status": "active",
                        "evidence_required": ["design_doc", "workflow dispatch completed"],
                        "evidence": [],
                    }
                },
            )

            with redirect_stdout(StringIO()):
                result = LocalDispatcher().execute_request(request)

            self.assertEqual(result.status, "success")
            self.assertEqual(result.metadata["goal"]["status"], "complete")
            self.assertEqual(result.metadata["workflow"]["metadata"]["goal"]["status"], "complete")
            self.assertIn("goal_ledger", result.metadata)
            self.assertIn("resume_handoff", result.metadata)
            self.assertTrue(Path(result.metadata["goal_ledger"]["current_goal_path"]).exists())
            self.assertTrue(Path(result.metadata["resume_handoff"]["paths"]["json_path"]).exists())

    def test_execute_request_exposes_runner_metadata_for_file_tasks(self):
        original_url = os.environ.pop("AG_WEBHOOK_URL", None)
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            request = AdapterRequest(
                project_dir=str(project_dir),
                files=["main.py"],
                design_doc="# design",
                platform_mode="local",
                metadata={
                    "goal": {
                        "objective": "build api",
                        "status": "active",
                        "evidence_required": [
                            "design_doc",
                            "target_files",
                            "workflow dispatch completed",
                            "task runner completed",
                        ],
                        "evidence": [],
                    }
                },
            )

            with redirect_stdout(StringIO()):
                try:
                    result = LocalDispatcher().execute_request(request)
                finally:
                    if original_url is not None:
                        os.environ["AG_WEBHOOK_URL"] = original_url

        self.assertEqual(result.status, "success")
        self.assertEqual(result.metadata["task_results"][0]["metadata"]["runner"], "local")
        self.assertEqual(result.metadata["task_results"][0]["metadata"]["webhook_report"]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
