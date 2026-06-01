import sys
import tempfile
import unittest
from pathlib import Path

from src.tasks.browser_qa import BrowserQACheckResult
from src.tasks.workflow_checks import WorkflowCheckStage, goal_with_check_requirements


class StaticBrowserQAAdapter:
    name = "static-browser"

    def __init__(self, result):
        self.result = result

    def run(self, check):
        return self.result


class WorkflowCheckStageTests(unittest.TestCase):
    def test_required_evidence_combines_command_specs_presets_and_browser_qa(self):
        metadata = {
            "command_checks": [
                {
                    "command": [sys.executable, "-c", "print('ok')"],
                    "evidence_key": "unit tests passed",
                }
            ],
            "command_check_presets": ["python-compile"],
            "browser_qa_checks": [
                {
                    "target": "http://localhost:3000",
                    "scenario": "homepage loads",
                    "evidence_key": "browser qa passed",
                }
            ],
        }

        self.assertEqual(
            WorkflowCheckStage().required_evidence(metadata),
            ["unit tests passed", "python compile passed", "browser qa passed"],
        )

    def test_goal_with_check_requirements_preserves_existing_goal_fields(self):
        goal = {
            "objective": "build api",
            "status": "active",
            "evidence_required": ["design_doc"],
            "evidence": [],
        }
        metadata = {
            "command_check_presets": ["python-compile"],
            "browser_qa_checks": [
                {
                    "target": "http://localhost:3000",
                    "evidence_key": "browser qa passed",
                }
            ],
        }

        updated = goal_with_check_requirements(goal, metadata)

        self.assertEqual(updated["objective"], "build api")
        self.assertEqual(
            updated["evidence_required"],
            ["design_doc", "python compile passed", "browser qa passed"],
        )

    def test_stage_runs_command_and_browser_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            metadata = {
                "command_checks": [
                    {
                        "command": [sys.executable, "-c", "print('ok')"],
                        "evidence_key": "unit tests passed",
                    }
                ],
                "browser_qa_adapter": StaticBrowserQAAdapter(
                    BrowserQACheckResult(
                        status="passed",
                        checks=["homepage"],
                        artifacts={"screenshot": "home.png"},
                    )
                ),
                "browser_qa_checks": [
                    {
                        "target": "http://localhost:3000",
                        "scenario": "homepage loads",
                        "evidence_key": "browser qa passed",
                    }
                ],
            }

            result = WorkflowCheckStage().run(str(project_dir), metadata)

        self.assertTrue(result.success)
        self.assertEqual(result.command_results[0]["status"], "passed")
        self.assertEqual(result.browser_qa_results[0]["status"], "passed")
        self.assertEqual(result.evidence, ["unit tests passed", "browser qa passed"])
        self.assertEqual(
            result.to_metadata(),
            {
                "command_check_results": result.command_results,
                "browser_qa_results": result.browser_qa_results,
            },
        )

    def test_stage_builds_browser_qa_sidecar_adapter_from_metadata(self):
        script = (
            "import json, sys; "
            "check=json.load(sys.stdin); "
            "print(json.dumps({"
            "'status':'passed',"
            "'checks':[check['scenario']],"
            "'metadata':{'source':'sidecar'}"
            "}))"
        )
        metadata = {
            "browser_qa_sidecar": {
                "command": [sys.executable, "-c", script],
            },
            "browser_qa_checks": [
                {
                    "target": "http://localhost:3000",
                    "scenario": "homepage loads",
                    "evidence_key": "browser qa passed",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            result = WorkflowCheckStage().run(tmp, metadata)

        self.assertTrue(result.success)
        self.assertEqual(result.browser_qa_results[0]["metadata"]["adapter"], "browser-qa-sidecar")
        self.assertEqual(result.browser_qa_results[0]["metadata"]["source"], "sidecar")
        self.assertEqual(result.evidence, ["browser qa passed"])

    def test_unknown_command_preset_returns_failed_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = WorkflowCheckStage().run(
                tmp,
                {"command_check_presets": ["missing-preset"]},
            )

        self.assertFalse(result.success)
        self.assertEqual(result.command_results[0]["status"], "failed")
        self.assertEqual(result.command_results[0]["metadata"]["error_type"], "ValueError")


if __name__ == "__main__":
    unittest.main()
