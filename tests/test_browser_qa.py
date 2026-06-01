import sys
import unittest

from src.tasks.browser_qa import (
    BrowserQACheckInput,
    BrowserQACheckResult,
    BrowserQACheckRunner,
    BrowserQASidecarAdapter,
)


class StaticBrowserQAAdapter:
    name = "static-browser"

    def __init__(self, result):
        self.result = result
        self.checks = []

    def run(self, check):
        self.checks.append(check)
        return self.result


class BrowserQACheckRunnerTests(unittest.TestCase):
    def test_browser_qa_runner_emits_passed_evidence(self):
        adapter = StaticBrowserQAAdapter(
            BrowserQACheckResult(
                status="passed",
                message="page loaded",
                checks=["homepage"],
                artifacts={"screenshot": "artifacts/home.png"},
            )
        )
        check = BrowserQACheckInput(
            target="http://localhost:3000",
            evidence_key="browser qa passed",
            scenario="homepage loads",
        )

        result = BrowserQACheckRunner(adapter=adapter).run(check)

        self.assertEqual(result.source, "qa")
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.evidence, ["browser qa passed"])
        self.assertEqual(result.metadata["adapter"], "static-browser")
        self.assertEqual(result.metadata["target"], "http://localhost:3000")
        self.assertEqual(result.metadata["artifacts"]["screenshot"], "artifacts/home.png")
        self.assertEqual(adapter.checks[0], check)

    def test_browser_qa_runner_does_not_emit_evidence_on_failure(self):
        adapter = StaticBrowserQAAdapter(
            BrowserQACheckResult(
                status="failed",
                message="button missing",
                checks=["homepage"],
                findings=["missing submit button"],
            )
        )
        check = BrowserQACheckInput(
            target="http://localhost:3000",
            evidence_key="browser qa passed",
            scenario="homepage loads",
        )

        result = BrowserQACheckRunner(adapter=adapter).run(check)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.evidence, [])
        self.assertEqual(result.metadata["findings"], ["missing submit button"])

    def test_browser_qa_runner_blocks_when_no_adapter_is_configured(self):
        check = BrowserQACheckInput(
            target="http://localhost:3000",
            evidence_key="browser qa passed",
            scenario="homepage loads",
        )

        result = BrowserQACheckRunner().run(check)

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.evidence, [])
        self.assertEqual(result.metadata["adapter"], "")
        self.assertEqual(result.metadata["error_type"], "BrowserQAAdapterNotConfigured")

    def test_sidecar_adapter_converts_json_stdout_to_qa_result(self):
        script = (
            "import json, sys; "
            "check=json.load(sys.stdin); "
            "print(json.dumps({"
            "'status':'passed',"
            "'message':'ok',"
            "'checks':[check['scenario']],"
            "'artifacts':{'target':check['target']},"
            "'metadata':{'sidecar':'fake'}"
            "}))"
        )
        adapter = BrowserQASidecarAdapter(command=[sys.executable, "-c", script])
        check = BrowserQACheckInput(
            target="http://localhost:3000",
            evidence_key="browser qa passed",
            scenario="homepage loads",
        )

        result = BrowserQACheckRunner(adapter=adapter).run(check)

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.evidence, ["browser qa passed"])
        self.assertEqual(result.metadata["adapter"], "browser-qa-sidecar")
        self.assertEqual(result.metadata["artifacts"]["target"], "http://localhost:3000")
        self.assertEqual(result.metadata["sidecar"], "fake")
        self.assertEqual(result.metadata["sidecar_exit_code"], 0)

    def test_sidecar_adapter_reports_invalid_json_as_failed_result(self):
        adapter = BrowserQASidecarAdapter(
            command=[sys.executable, "-c", "print('not-json')"]
        )
        check = BrowserQACheckInput(
            target="http://localhost:3000",
            evidence_key="browser qa passed",
            scenario="homepage loads",
        )

        result = BrowserQACheckRunner(adapter=adapter).run(check)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.evidence, [])
        self.assertEqual(result.metadata["error_type"], "JSONDecodeError")


if __name__ == "__main__":
    unittest.main()
