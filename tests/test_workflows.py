import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from src.orchestration.roles import build_default_role_metadata
from src.contracts import MemoryRecord
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryStore
from src.tasks.browser_qa import BrowserQACheckResult
from src.tasks.workflows import _project_id, _safe_worker_count, dispatch_project_workflow


class StaticBrowserQAAdapter:
    name = "static-browser"

    def __init__(self, result):
        self.result = result
        self.checks = []

    def run(self, check):
        self.checks.append(check)
        return self.result


class FakeLLMRouter:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return self.response


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

    def test_webhook_failure_is_recorded_without_overriding_runner_result(self):
        original_url = os.environ.get("AG_WEBHOOK_URL")
        os.environ["AG_WEBHOOK_URL"] = "http://127.0.0.1:9/api/webhook/subagent-result"
        metadata = build_default_role_metadata()
        metadata["goal"] = {
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

        try:
            with tempfile.TemporaryDirectory() as tmp:
                project_dir = Path(tmp) / "demo"
                project_dir.mkdir()
                result = dispatch_project_workflow(
                    project_dir=str(project_dir),
                    file_list=["main.py"],
                    design_doc="# design",
                    platform_mode="local",
                    metadata=metadata,
                )
        finally:
            if original_url is None:
                os.environ.pop("AG_WEBHOOK_URL", None)
            else:
                os.environ["AG_WEBHOOK_URL"] = original_url

        self.assertEqual(result.workflow_id, "workflow_demo")
        self.assertTrue(result.success)
        self.assertEqual(len(result.task_results), 1)
        self.assertEqual(result.task_results[0].status, "success")
        self.assertEqual(result.task_results[0].role, "implementer")
        self.assertEqual(result.task_results[0].metadata["runner"], "local")
        self.assertEqual(result.task_results[0].metadata["webhook_report"]["status"], "failed")
        self.assertEqual(result.metadata["goal"]["objective"], "build api")
        self.assertEqual(result.metadata["goal"]["status"], "complete")
        self.assertIn("task runner completed", result.metadata["goal"]["evidence"])
        self.assertIn("spec-reviewer", [gate["role"] for gate in result.gate_results])
        self.assertEqual({gate["status"] for gate in result.gate_results}, {"passed"})

    def test_webhook_report_is_skipped_when_url_is_not_configured(self):
        original_url = os.environ.pop("AG_WEBHOOK_URL", None)
        metadata = build_default_role_metadata()
        metadata["goal"] = {
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

        try:
            with tempfile.TemporaryDirectory() as tmp:
                project_dir = Path(tmp) / "demo"
                project_dir.mkdir()
                result = dispatch_project_workflow(
                    project_dir=str(project_dir),
                    file_list=["main.py"],
                    design_doc="# design",
                    platform_mode="local",
                    metadata=metadata,
                )
        finally:
            if original_url is not None:
                os.environ["AG_WEBHOOK_URL"] = original_url

        self.assertTrue(result.success)
        self.assertEqual(result.task_results[0].metadata["webhook_report"]["status"], "skipped")
        self.assertEqual(
            result.task_results[0].metadata["webhook_report"]["reason"],
            "AG_WEBHOOK_URL not configured",
        )

    def test_workflow_collects_generated_code_evidence(self):
        original_url = os.environ.pop("AG_WEBHOOK_URL", None)
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": [
                "design_doc",
                "target_files",
                "workflow dispatch completed",
                "task runner completed",
                "code generated",
            ],
            "evidence": [],
        }

        try:
            with tempfile.TemporaryDirectory() as tmp:
                project_dir = Path(tmp) / "demo"
                project_dir.mkdir()
                result = dispatch_project_workflow(
                    project_dir=str(project_dir),
                    file_list=["main.py"],
                    design_doc="# design",
                    platform_mode="local",
                    metadata=metadata,
                )
                generated_content = (project_dir / "main.py").read_text(encoding="utf-8")
        finally:
            if original_url is not None:
                os.environ["AG_WEBHOOK_URL"] = original_url

        self.assertTrue(result.success)
        self.assertIn("code generated", result.metadata["goal"]["evidence"])
        self.assertIn("Generated by UAF LocalTaskRunner", generated_content)
        self.assertTrue(result.task_results[0].metadata["artifact_exists"])

    def test_workflow_uses_llm_router_for_local_generation_when_provided(self):
        original_url = os.environ.pop("AG_WEBHOOK_URL", None)
        llm = FakeLLMRouter("```python\nprint('from workflow llm')\n```")
        metadata = build_default_role_metadata()
        metadata["llm_router"] = llm
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": [
                "design_doc",
                "target_files",
                "workflow dispatch completed",
                "code generated",
            ],
            "evidence": [],
        }

        try:
            with tempfile.TemporaryDirectory() as tmp:
                project_dir = Path(tmp) / "demo"
                project_dir.mkdir()
                result = dispatch_project_workflow(
                    project_dir=str(project_dir),
                    file_list=["main.py"],
                    design_doc="# design",
                    platform_mode="local",
                    metadata=metadata,
                )
                generated_content = (project_dir / "main.py").read_text(encoding="utf-8")
        finally:
            if original_url is not None:
                os.environ["AG_WEBHOOK_URL"] = original_url

        self.assertTrue(result.success)
        self.assertEqual(result.task_results[0].metadata["generation_adapter"], "llm-local")
        self.assertEqual(generated_content, "print('from workflow llm')\n")
        self.assertIn("main.py", llm.calls[0][1])

    def test_workflow_runs_command_checks_into_goal_evidence(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "workflow dispatch completed"],
            "evidence": [],
        }
        metadata["command_checks"] = [
            {
                "command": [sys.executable, "-c", "print('ok')"],
                "evidence_key": "unit tests passed",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["command_check_results"][0]["status"], "passed")
        self.assertIn("unit tests passed", result.metadata["goal"]["evidence"])
        self.assertIn("unit tests passed", result.metadata["goal"]["evidence_required"])

    def test_workflow_expands_command_check_presets(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "workflow dispatch completed"],
            "evidence": [],
        }
        metadata["command_check_presets"] = ["python-compile"]

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["command_check_results"][0]["status"], "passed")
        self.assertIn("python compile passed", result.metadata["goal"]["evidence"])
        self.assertIn("python compile passed", result.metadata["goal"]["evidence_required"])

    def test_workflow_runs_browser_qa_checks_into_goal_evidence(self):
        adapter = StaticBrowserQAAdapter(
            BrowserQACheckResult(
                status="passed",
                message="page loaded",
                checks=["homepage"],
                artifacts={"screenshot": "artifacts/home.png"},
            )
        )
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "workflow dispatch completed"],
            "evidence": [],
        }
        metadata["browser_qa_adapter"] = adapter
        metadata["browser_qa_checks"] = [
            {
                "target": "http://localhost:3000",
                "scenario": "homepage loads",
                "evidence_key": "browser qa passed",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["browser_qa_results"][0]["status"], "passed")
        self.assertEqual(result.metadata["browser_qa_results"][0]["metadata"]["adapter"], "static-browser")
        self.assertEqual(adapter.checks[0].target, "http://localhost:3000")
        self.assertIn("browser qa passed", result.metadata["goal"]["evidence"])
        self.assertIn("browser qa passed", result.metadata["goal"]["evidence_required"])

    def test_missing_browser_qa_adapter_blocks_goal_and_release(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "workflow dispatch completed"],
            "evidence": [],
        }
        metadata["browser_qa_checks"] = [
            {
                "target": "http://localhost:3000",
                "scenario": "homepage loads",
                "evidence_key": "browser qa passed",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )

        statuses = {gate["role"]: gate["status"] for gate in result.gate_results}
        self.assertFalse(result.success)
        self.assertEqual(result.metadata["browser_qa_results"][0]["status"], "blocked")
        self.assertEqual(
            result.metadata["browser_qa_results"][0]["metadata"]["error_type"],
            "BrowserQAAdapterNotConfigured",
        )
        self.assertEqual(result.metadata["goal"]["status"], "blocked")
        self.assertEqual(result.metadata["goal"]["metadata"]["missing_evidence"], ["browser qa passed"])
        self.assertEqual(statuses["qa-verifier"], "blocked")
        self.assertEqual(statuses["release-manager"], "blocked")

    def test_failed_command_check_blocks_goal_and_release(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "workflow dispatch completed"],
            "evidence": [],
        }
        metadata["command_checks"] = [
            {
                "command": [sys.executable, "-c", "import sys; sys.exit(2)"],
                "evidence_key": "unit tests passed",
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )

        statuses = {gate["role"]: gate["status"] for gate in result.gate_results}
        self.assertFalse(result.success)
        self.assertEqual(result.metadata["command_check_results"][0]["status"], "failed")
        self.assertEqual(result.metadata["goal"]["status"], "blocked")
        self.assertEqual(result.metadata["goal"]["metadata"]["missing_evidence"], ["unit tests passed"])
        self.assertEqual(statuses["qa-verifier"], "blocked")
        self.assertEqual(statuses["release-manager"], "blocked")

    def test_failed_command_check_without_evidence_key_blocks_goal_and_ledger(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "workflow dispatch completed"],
            "evidence": [],
        }
        metadata["command_checks"] = [
            {
                "command": [sys.executable, "-c", "import sys; sys.exit(2)"],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )
            ledger_state = json.loads(
                Path(result.metadata["goal_ledger"]["current_goal_path"]).read_text(encoding="utf-8")
            )
            ledger_events = [
                json.loads(line)
                for line in Path(result.metadata["goal_ledger"]["events_path"]).read_text(encoding="utf-8").splitlines()
            ]

        self.assertFalse(result.success)
        self.assertEqual(result.metadata["command_check_results"][0]["status"], "failed")
        self.assertEqual(result.metadata["goal"]["status"], "blocked")
        self.assertEqual(result.metadata["goal"]["blocked_reason"], "workflow dispatch failed")
        self.assertEqual(result.metadata["goal"]["metadata"]["missing_evidence"], [])
        self.assertEqual(ledger_state["status"], "blocked")
        self.assertEqual(ledger_events[-1]["event_type"], "goal_blocked")

    def test_unknown_command_preset_blocks_goal_even_without_required_evidence(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "workflow dispatch completed"],
            "evidence": [],
        }
        metadata["command_check_presets"] = ["missing-preset"]

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )

        self.assertFalse(result.success)
        self.assertEqual(result.metadata["command_check_results"][0]["status"], "failed")
        self.assertEqual(
            result.metadata["command_check_results"][0]["metadata"]["error_type"],
            "ValueError",
        )
        self.assertEqual(result.metadata["goal"]["status"], "blocked")
        self.assertEqual(result.metadata["goal"]["blocked_reason"], "workflow dispatch failed")

    def test_workflow_records_post_gate_evidence_in_final_goal(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "workflow dispatch completed"],
            "evidence": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["goal"]["status"], "complete")
        self.assertIn("spec review passed", result.metadata["gate_evidence"])
        self.assertIn("qa gate passed", result.metadata["gate_evidence"])
        self.assertIn("release gate passed", result.metadata["gate_evidence"])
        self.assertIn("release gate passed", result.metadata["goal"]["evidence"])

    def test_post_gate_evidence_does_not_unblock_missing_required_evidence(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "release gate passed"],
            "evidence": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )

        self.assertFalse(result.success)
        self.assertEqual(result.metadata["goal"]["status"], "blocked")
        self.assertEqual(result.metadata["goal"]["metadata"]["missing_evidence"], ["release gate passed"])
        self.assertIn("security review passed", result.metadata["goal"]["evidence"])
        self.assertNotIn("release gate passed", result.metadata["goal"]["evidence"])

    def test_runner_failure_blocks_workflow_before_goal_completion(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["task runner completed"],
            "evidence": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=["../outside.py"],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )

        self.assertFalse(result.success)
        self.assertEqual(result.task_results[0].status, "failed")
        self.assertEqual(result.task_results[0].metadata["error_type"], "ValueError")
        self.assertEqual(result.metadata["goal"]["status"], "blocked")
        self.assertEqual(result.metadata["goal"]["blocked_reason"], "workflow dispatch failed")

    def test_workflow_marks_goal_complete_when_required_evidence_is_collected(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "workflow dispatch completed"],
            "evidence": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )
            ledger_path = Path(result.metadata["goal_ledger"]["current_goal_path"])
            events_path = Path(result.metadata["goal_ledger"]["events_path"])
            ledger_state = json.loads(ledger_path.read_text(encoding="utf-8"))
            ledger_events = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["goal"]["status"], "complete")
        self.assertEqual(ledger_state["status"], "complete")
        self.assertEqual(ledger_events[-1]["event_type"], "goal_completed")
        self.assertIn("design_doc", result.metadata["goal"]["evidence"])
        self.assertIn("workflow dispatch completed", result.metadata["goal"]["evidence"])
        self.assertIn("release gate passed", result.metadata["goal"]["evidence"])
        self.assertEqual({gate["status"] for gate in result.gate_results}, {"passed"})

    def test_workflow_runtime_state_is_external_by_default(self):
        original_runtime_root = os.environ.get("UAF_RUNTIME_ROOT")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                project_dir = Path(tmp) / "demo"
                runtime_root = Path(tmp) / "runtime"
                project_dir.mkdir()
                os.environ["UAF_RUNTIME_ROOT"] = str(runtime_root)
                metadata = build_default_role_metadata()
                metadata["goal"] = {
                    "objective": "build api",
                    "status": "active",
                    "evidence_required": ["design_doc", "workflow dispatch completed"],
                    "evidence": [],
                }

                result = dispatch_project_workflow(
                    project_dir=str(project_dir),
                    file_list=[],
                    design_doc="# design",
                    platform_mode="local",
                    metadata=metadata,
                )

                self.assertTrue(result.success)
                self.assertFalse((project_dir / ".uaf").exists())
                self.assertFalse((project_dir / ".snapshots").exists())
                self.assertTrue(
                    str(result.metadata["goal_ledger"]["current_goal_path"]).startswith(str(runtime_root))
                )
                self.assertTrue(
                    str(result.metadata["resume_handoff"]["paths"]["json_path"]).startswith(str(runtime_root))
                )
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

    def test_workflow_exports_domain_neutral_deliverables_to_project_docs(self):
        original_runtime_root = os.environ.get("UAF_RUNTIME_ROOT")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                project_dir = Path(tmp) / "demo"
                runtime_root = Path(tmp) / "runtime"
                project_dir.mkdir()
                os.environ["UAF_RUNTIME_ROOT"] = str(runtime_root)
                metadata = build_default_role_metadata()
                metadata["domain_hint"] = "operations"
                metadata["goal"] = {
                    "objective": "coordinate exception review",
                    "status": "active",
                    "evidence_required": [
                        "design_doc",
                        "workflow dispatch completed",
                        "requirements brief exported",
                        "orchestration design exported",
                        "manual exported",
                    ],
                    "evidence": [],
                }
                metadata["manual_revision"] = "Rev. 1.1"
                metadata["manual_revision_note"] = "Workflow acceptance update."

                result = dispatch_project_workflow(
                    project_dir=str(project_dir),
                    file_list=["exception-report"],
                    design_doc="# Exception Review\nCoordinate a cross-team review.",
                    platform_mode="local",
                    metadata=metadata,
                )
                deliverables = result.metadata["deliverable_exports"]["deliverables"]
                exported_paths = {Path(item["path"]).name: Path(item["path"]) for item in deliverables}
                ledger_state = json.loads(
                    Path(result.metadata["goal_ledger"]["current_goal_path"]).read_text(encoding="utf-8")
                )

                self.assertTrue(result.success)
                self.assertFalse((project_dir / ".uaf").exists())
                self.assertFalse((project_dir / ".snapshots").exists())
                self.assertTrue((project_dir / "docs" / "요구정의서.docx").exists())
                self.assertTrue((project_dir / "docs" / "오케스트레이션_설계서.docx").exists())
                self.assertTrue((project_dir / "docs" / "역할별_작업분해표.xlsx").exists())
                self.assertTrue((project_dir / "docs" / "사용_매뉴얼.docx").exists())
                self.assertTrue(zipfile.is_zipfile(exported_paths["오케스트레이션_설계서.docx"]))
                with zipfile.ZipFile(exported_paths["사용_매뉴얼.docx"]) as package:
                    manual_xml = package.read("word/document.xml").decode("utf-8")
                self.assertIn("requirements brief exported", result.metadata["goal"]["evidence"])
                self.assertIn("orchestration design exported", result.metadata["goal"]["evidence"])
                self.assertIn("manual exported", result.metadata["goal"]["evidence"])
                self.assertIn("리비전 버전 관리", manual_xml)
                self.assertIn("Rev. 1.1", manual_xml)
                self.assertEqual(
                    result.metadata["role_orchestration"]["execution_model"],
                    "dag-asyncio-role-waves",
                )
                self.assertGreaterEqual(result.metadata["role_orchestration"]["wave_count"], 2)
                self.assertGreaterEqual(result.metadata["role_orchestration"]["parallel_wave_count"], 2)
                self.assertTrue(result.metadata["role_task_results"])
                self.assertTrue(
                    all(
                        item["metadata"]["execution_model"] == "parallel-role-stage"
                        for item in result.metadata["role_task_results"]
                    )
                )
                role_names = {item["role"] for item in result.metadata["role_task_results"]}
                self.assertTrue({
                    "system-architect",
                    "implementation-planner",
                    "spec-reviewer",
                    "qa-verifier",
                    "security-reviewer",
                    "release-manager",
                }.issubset(role_names))
                architect = next(
                    item for item in result.metadata["role_task_results"]
                    if item["role"] == "system-architect"
                )
                self.assertIn("오케스트레이션_설계서.docx", architect["metadata"]["required_deliverables"])
                architect_artifact = Path(architect["metadata"]["role_artifacts"][0]["path"])
                self.assertTrue(str(architect_artifact).startswith(str(runtime_root)))
                self.assertTrue(architect_artifact.exists())
                self.assertIn("system-architect", architect_artifact.read_text(encoding="utf-8"))
                self.assertIn("system architect role task completed", result.metadata["goal"]["evidence"])
                self.assertIn(
                    "deliverable_exports",
                    ledger_state["goal"]["metadata"],
                )
                self.assertIn(
                    "role_orchestration",
                    ledger_state["goal"]["metadata"],
                )
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

    def test_workflow_loads_memory_context_into_metadata_and_goal_ledger(self):
        metadata = build_default_role_metadata()
        metadata["enable_memory"] = True
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "workflow dispatch completed"],
            "evidence": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            scope = MemoryScopeResolver.project_scope(str(project_dir))
            store = MemoryStore(MemoryScopeResolver.storage_path(scope), scope)
            store.save_record(
                MemoryRecord(
                    record_id="decision-1",
                    kind="decision",
                    content="Use Python core and TypeScript sidecars.",
                    scope=scope.kind,
                    source="user-approved",
                    confidence="high",
                )
            )

            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )
            ledger_state = json.loads(
                Path(result.metadata["goal_ledger"]["current_goal_path"]).read_text(encoding="utf-8")
            )

        self.assertTrue(result.success)
        self.assertEqual(result.metadata["memory_context"]["records"][0]["record_id"], "decision-1")
        self.assertEqual(
            result.metadata["goal"]["metadata"]["memory_context"]["records"][0]["content"],
            "Use Python core and TypeScript sidecars.",
        )
        self.assertEqual(
            ledger_state["goal"]["metadata"]["memory_context"]["records"][0]["record_id"],
            "decision-1",
        )

    def test_workflow_saves_work_design_artifacts_into_manifest_and_goal_evidence(self):
        metadata = build_default_role_metadata()
        metadata["domain_profile"] = {
            "domain_name": "operations",
            "objective": "Improve a support workflow",
            "subdomains": ["triage", "handoff"],
            "required_design_artifact_types": ["workflow-map"],
        }
        metadata["design_artifacts"] = [
            {
                "artifact_id": "workflow_map",
                "kind": "workflow-map",
                "title": "Workflow Map",
                "content": "# Workflow Map\n",
                "owner_role": "domain-designer",
                "required_for": ["review", "qa"],
            }
        ]
        metadata["goal"] = {
            "objective": "Improve a support workflow",
            "status": "active",
            "evidence_required": [
                "design_doc",
                "workflow dispatch completed",
                "work design saved",
                "artifact manifest saved",
                "required design artifacts saved",
            ],
            "evidence": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# Source design",
                platform_mode="local",
                metadata=metadata,
            )
            manifest_path = Path(result.metadata["artifact_store"]["manifest_path"])
            manifest_exists = manifest_path.exists()
            ledger_state = json.loads(
                Path(result.metadata["goal_ledger"]["current_goal_path"]).read_text(encoding="utf-8")
            )

        self.assertTrue(result.success)
        self.assertTrue(manifest_exists)
        self.assertEqual(result.metadata["domain_profile"]["domain_name"], "operations")
        self.assertEqual(result.metadata["work_design"]["domain"], "operations")
        self.assertEqual(len(result.metadata["artifact_manifest"]["design_artifacts"]), 2)
        self.assertIn("work design saved", result.metadata["goal"]["evidence"])
        self.assertIn("artifact manifest saved", result.metadata["goal"]["evidence"])
        self.assertIn("required design artifacts saved", result.metadata["goal"]["evidence"])
        self.assertEqual(
            ledger_state["goal"]["metadata"]["artifact_manifest"]["workflow_id"],
            result.workflow_id,
        )

    def test_workflow_writes_resume_handoff_for_next_session(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "Resume a blocked workflow",
            "status": "active",
            "success_criteria": ["review evidence is available"],
            "evidence_required": [
                "design_doc",
                "workflow dispatch completed",
                "review passed",
            ],
            "evidence": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# Resume Design",
                platform_mode="local",
                metadata=metadata,
            )
            handoff = result.metadata["resume_handoff"]
            json_path = Path(handoff["paths"]["json_path"])
            markdown_path = Path(handoff["paths"]["markdown_path"])
            json_exists = json_path.exists()
            markdown_exists = markdown_path.exists()
            persisted = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertFalse(result.success)
        self.assertTrue(json_exists)
        self.assertTrue(markdown_exists)
        self.assertEqual(handoff["snapshot"]["status"], "blocked")
        self.assertEqual(handoff["snapshot"]["success_criteria"], ["review evidence is available"])
        self.assertEqual(handoff["snapshot"]["missing_evidence"], ["review passed"])
        self.assertEqual(persisted["success_criteria"], ["review evidence is available"])
        self.assertIn("review passed", persisted["missing_evidence"])
        self.assertEqual(handoff["snapshot"]["workflow_id"], result.workflow_id)

    def test_workflow_blocks_goal_and_release_when_required_evidence_is_missing(self):
        metadata = build_default_role_metadata()
        metadata["goal"] = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc", "qa report"],
            "evidence": [],
        }

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            result = dispatch_project_workflow(
                project_dir=str(project_dir),
                file_list=[],
                design_doc="# design",
                platform_mode="local",
                metadata=metadata,
            )
            ledger_state = json.loads(
                Path(result.metadata["goal_ledger"]["current_goal_path"]).read_text(encoding="utf-8")
            )

        statuses = {gate["role"]: gate["status"] for gate in result.gate_results}
        self.assertFalse(result.success)
        self.assertEqual(result.metadata["goal"]["status"], "blocked")
        self.assertEqual(ledger_state["status"], "blocked")
        self.assertEqual(result.metadata["goal"]["metadata"]["missing_evidence"], ["qa report"])
        self.assertEqual(statuses["qa-verifier"], "blocked")
        self.assertEqual(statuses["release-manager"], "blocked")


if __name__ == "__main__":
    unittest.main()
