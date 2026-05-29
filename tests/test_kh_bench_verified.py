import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.benchmarks.kh_bench_verified import (
    BENCHMARK_NAME,
    evaluate_validator,
    load_verified_tasks,
    run_kh_bench_verified,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class KHBenchVerifiedTests(unittest.TestCase):
    def test_task_catalog_uses_swe_bench_style_schema(self):
        tasks = load_verified_tasks()

        self.assertGreaterEqual(len(tasks), 6)
        instance_ids = [task["instance_id"] for task in tasks]
        self.assertEqual(len(instance_ids), len(set(instance_ids)))

        categories = {task["category"] for task in tasks}
        self.assertTrue(
            {
                "coding-workflow",
                "domain-deliverables",
                "role-orchestration",
                "state-snapshot",
                "context-optimization",
                "goal-memory",
            }.issubset(categories)
        )

        for task in tasks:
            with self.subTest(task=task["instance_id"]):
                self.assertEqual(task["schema_version"], "1.0")
                self.assertTrue(task["instance_id"].startswith("khbench-"))
                self.assertTrue(task["problem_statement"])
                self.assertTrue(task["skills"])
                self.assertTrue(task["candidate_profile"])
                self.assertNotIn("scenario", task)
                self.assertTrue(task["base_workspace"])
                self.assertTrue(task["pre_validation"])
                self.assertTrue(task["expected_artifacts"])
                self.assertTrue(task["fail_to_pass"])
                self.assertTrue(task["pass_to_pass"])
                self.assertTrue(task["human_verified"])
                self.assertIn(task["difficulty"], {"smoke", "standard", "hard"})
                self_attested_types = {
                    "custom_flag",
                    "custom_equals",
                    "custom_at_least",
                    "custom_contains_all",
                    "workflow_success",
                    "role_audit_passed",
                    "deliverable_formats",
                    "artifact_type_exists",
                    "snapshot_bundle_restored",
                    "single_snapshot_bundle",
                    "memory_record_count",
                    "handoff_status",
                }
                for validator in task["pre_validation"]:
                    self.assertIn("type", validator)
                    self.assertIn("name", validator)
                    self.assertEqual(validator["expect"], "fail")
                    self.assertNotIn(validator["type"], self_attested_types)
                for validator in task["fail_to_pass"] + task["pass_to_pass"]:
                    self.assertIn("type", validator)
                    self.assertIn("name", validator)
                    self.assertNotIn(validator["type"], self_attested_types)

    def test_benchmark_executes_tasks_and_reports_verified_pass_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_kh_bench_verified(output_root=Path(tmp))

            self.assertEqual(report["schema_version"], "1.0")
            self.assertEqual(report["benchmark"], BENCHMARK_NAME)
            self.assertEqual(report["score_schema_version"], "kh-bench-score/v1")
            self.assertTrue(report["run_id"].startswith("khbench-run-"))
            self.assertGreaterEqual(report["task_count"], 6)
            self.assertEqual(report["resolved_count"], report["task_count"])
            self.assertEqual(report["resolved_rate"], 1.0)
            self.assertEqual(report["unresolved"], [])
            self.assertEqual(report["summary"]["invalid"], 0)
            self.assertEqual(report["summary"]["infra_error"], 0)
            self.assertTrue(report["generated_at"].endswith("Z"))

            json.dumps(report, ensure_ascii=False)
            for result in report["results"]:
                with self.subTest(task=result["instance_id"]):
                    self.assertTrue(result["resolved"], result)
                    self.assertEqual(result["pre_validation"]["passed"], result["pre_validation"]["total"])
                    self.assertEqual(result["fail_to_pass"]["passed"], result["fail_to_pass"]["total"])
                    self.assertEqual(result["pass_to_pass"]["passed"], result["pass_to_pass"]["total"])
                    self.assertGreater(result["pre_validation"]["total"], 0)
                    self.assertGreater(result["fail_to_pass"]["total"], 0)
                    self.assertGreater(result["pass_to_pass"]["total"], 0)
                    self.assertTrue(result["evidence"])
                    self.assertTrue(result["runtime_contract"])
                    self.assertIn(result["status"], {"passed"})
                    self.assertIn(result["category"], report["categories"])
                    self.assertTrue(Path(result["workspace"]).exists())
                    self.assertTrue(Path(result["runtime_root"]).exists())
                    for artifact in result["artifacts"]:
                        artifact_path = Path(artifact["path"]).resolve()
                        self.assertTrue(artifact_path.exists(), artifact)
                        valid_roots = [
                            Path(result["workspace"]).resolve(),
                            Path(result["runtime_root"]).resolve(),
                        ]
                    self.assertTrue(
                        any(
                            os.path.commonpath([str(root), str(artifact_path)]) == str(root)
                            for root in valid_roots
                        ),
                        artifact,
                    )

    def test_benchmark_is_hermetic_when_project_local_state_env_is_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env["UAF_PROJECT_LOCAL_STATE"] = "1"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.benchmarks.kh_bench_verified",
                    "--output-dir",
                    tmp,
                    "--summary",
                ],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=180,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.splitlines()[-1])
        self.assertEqual(payload["summary"]["passed"], payload["summary"]["total"])
        self.assertEqual(payload["unresolved"], [])

    def test_candidate_runner_receives_sealed_task_view(self):
        class InspectingRunner:
            name = "inspecting-runner"

            def __init__(self):
                self.received = None

            def run(self, task, workspace, runtime_root):
                self.received = task
                return {
                    "artifacts": [],
                    "workflow": {},
                    "evidence": [],
                    "runtime_contract": {},
                }

        runner = InspectingRunner()
        with tempfile.TemporaryDirectory() as tmp:
            report = run_kh_bench_verified(
                output_root=Path(tmp),
                task_ids=["khbench-context-optimization-001"],
                candidate_runner=runner,
            )

        self.assertEqual(report["summary"]["passed"], 0)
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertEqual(report["unresolved"], ["khbench-context-optimization-001"])
        self.assertIsNotNone(runner.received)
        for hidden_key in [
            "pre_validation",
            "fail_to_pass",
            "pass_to_pass",
            "expected_artifacts",
            "candidate_profile",
        ]:
            self.assertNotIn(hidden_key, runner.received)
        self.assertIn("problem_statement", runner.received)
        self.assertIn("skills", runner.received)

    def test_score_contract_records_failing_and_infra_candidates(self):
        class NoopRunner:
            name = "noop-runner"

            def run(self, task, workspace, runtime_root):
                return {"artifacts": [], "workflow": {}, "evidence": [], "runtime_contract": {}}

        class ExplodingRunner:
            name = "exploding-runner"

            def run(self, task, workspace, runtime_root):
                raise RuntimeError("candidate exploded")

        with tempfile.TemporaryDirectory() as tmp:
            failed_report = run_kh_bench_verified(
                output_root=Path(tmp) / "failed",
                task_ids=["khbench-context-optimization-001"],
                candidate_runner=NoopRunner(),
            )
            infra_report = run_kh_bench_verified(
                output_root=Path(tmp) / "infra",
                task_ids=["khbench-context-optimization-001"],
                candidate_runner=ExplodingRunner(),
            )

        self.assertEqual(failed_report["summary"]["passed"], 0)
        self.assertEqual(failed_report["summary"]["failed"], 1)
        self.assertEqual(failed_report["results"][0]["status"], "failed")
        self.assertEqual(failed_report["results"][0]["score"], 0.0)
        self.assertEqual(failed_report["unresolved"], ["khbench-context-optimization-001"])

        self.assertEqual(infra_report["summary"]["passed"], 0)
        self.assertEqual(infra_report["summary"]["infra_error"], 1)
        self.assertEqual(infra_report["results"][0]["status"], "infra_error")
        self.assertEqual(infra_report["results"][0]["score"], 0.0)
        self.assertIn("candidate exploded", infra_report["results"][0]["failure_reason"])

    def test_validator_failures_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = evaluate_validator(
                {
                    "name": "missing artifact blocks resolution",
                    "type": "file_exists",
                    "path": "docs/required-output.docx",
                },
                {
                    "workspace": workspace,
                    "artifacts": [],
                    "workflow": {},
                    "custom": {},
                },
            )

        self.assertFalse(result["passed"])
        self.assertIn("missing", result["message"].lower())
        self.assertIn("required-output.docx", result["message"])


if __name__ == "__main__":
    unittest.main()
