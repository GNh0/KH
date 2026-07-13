import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from src.skills.demo_scenarios import DEMO_SKILL_PROFILES, _scenario_for
from src.skills.uaf_skill_catalog import collect_packaged_skills
from src.skills.uaf_skill_quality import _validate_demo_payload


REPO_ROOT = Path(__file__).resolve().parents[1]


class SkillDemoTests(unittest.TestCase):
    def test_demo_prompts_do_not_teach_static_web_defaults(self):
        forbidden = [
            "Create a small static task tracker",
            "Make a small static dashboard",
            "Create a small static dashboard",
        ]
        paths = [
            REPO_ROOT / "src" / "skills" / "demo_scenarios.py",
            REPO_ROOT / "skills" / "automatic_intake_harness" / "examples" / "minimal-workflow.md",
            REPO_ROOT / "skills" / "always_on_front_door" / "examples" / "minimal-workflow.md",
        ]

        for path in paths:
            content = path.read_text(encoding="utf-8")
            for phrase in forbidden:
                with self.subTest(path=str(path), phrase=phrase):
                    self.assertNotIn(phrase, content)

    def test_every_packaged_skill_has_runnable_demo(self):
        catalog = collect_packaged_skills()
        skills = catalog["skills"]
        self.assertGreaterEqual(len(skills), 27)
        self.assertEqual(
            {skill["name"] for skill in skills},
            set(DEMO_SKILL_PROFILES),
            "every packaged skill must have a skill-specific demo profile",
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            for skill in skills:
                with self.subTest(skill=skill["name"]):
                    skill_dir = REPO_ROOT / "skills" / skill["relative_path"].replace("/SKILL.md", "")
                    demo_path = skill_dir / "scripts" / "demo.py"
                    self.assertTrue(demo_path.exists(), f"missing demo script for {skill['name']}")
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(demo_path),
                            "--output-dir",
                            str(output_root / skill["name"]),
                        ],
                        cwd=REPO_ROOT,
                        capture_output=True,
                        encoding="utf-8",
                        text=True,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(completed.stderr.strip(), "")
                    payload = json.loads(completed.stdout)
                    self._assert_demo_payload(skill["name"], payload, output_root / skill["name"])

    def test_demos_are_runnable_from_skill_directory(self):
        catalog = collect_packaged_skills()
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            for skill in catalog["skills"]:
                with self.subTest(skill=skill["name"]):
                    skill_dir = REPO_ROOT / "skills" / skill["relative_path"].replace("/SKILL.md", "")
                    demo_path = skill_dir / "scripts" / "demo.py"
                    self.assertTrue(demo_path.exists(), f"missing demo script for {skill['name']}")
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(demo_path),
                            "--output-dir",
                            str(output_root / "skill-cwd" / skill["name"]),
                        ],
                        cwd=skill_dir,
                        capture_output=True,
                        encoding="utf-8",
                        text=True,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(completed.stderr.strip(), "")
                    payload = json.loads(completed.stdout)
                    self._assert_demo_payload(skill["name"], payload, output_root / "skill-cwd" / skill["name"])

    def test_goal_demo_declares_runtime_artifacts_and_executes_evidence_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "goal-state-harness"
            demo_path = REPO_ROOT / "skills" / "goal_state_harness" / "scripts" / "demo.py"
            completed = subprocess.run(
                [sys.executable, str(demo_path), "--output-dir", str(output_dir)],
                cwd=REPO_ROOT,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self._assert_demo_payload("goal-state-harness", payload, output_dir)
            runtime_demo = payload["runtime_demo"]
            for case in ["success", "blocked"]:
                evidence = runtime_demo[case]["command_evidence"]
                self.assertTrue(evidence["executed"])
                self.assertTrue(evidence["command"])
                self.assertRegex(evidence["output_hash"], r"^sha256:[0-9a-f]{64}$")

            declared_paths = {Path(item["path"]).resolve() for item in payload["artifacts"]}
            generated_paths = {path.resolve() for path in output_dir.rglob("*") if path.is_file()}
            self.assertEqual(generated_paths, declared_paths)

    def test_sql_provider_demo_runs_source_candidate_verifier_pipeline_truthfully(self):
        collect_packaged_skills()
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "sql-formatting"
            demo_path = REPO_ROOT / "skills" / "sql_formatting" / "scripts" / "demo.py"
            completed = subprocess.run(
                [sys.executable, str(demo_path), "--output-dir", str(output_dir)],
                cwd=REPO_ROOT,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self._assert_demo_payload("sql-formatting", payload, output_dir)

            pipeline = payload["provider_pipeline"]
            self.assertEqual(pipeline["generation"]["execution_actor"], "host-llm")
            self.assertFalse(pipeline["generation"]["host_llm_executed"])
            self.assertFalse(pipeline["generation"]["headless_python_formatter"])
            self.assertEqual(
                pipeline["generation"]["candidate_provenance"],
                "bundled-static-demo-fixture",
            )
            self.assertEqual(
                pipeline["verification"]["actor"],
                "src.skills.sql_formatting_style.verify_sql_formatting_style",
            )
            self.assertTrue(pipeline["verification"]["success"])

    def test_sql_style_demo_separates_formatting_success_from_refactor_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "sql-formatting-style-harness"
            demo_path = (
                REPO_ROOT
                / "skills"
                / "sql_formatting_style_harness"
                / "scripts"
                / "demo.py"
            )
            completed = subprocess.run(
                [sys.executable, str(demo_path), "--output-dir", str(output_dir)],
                cwd=REPO_ROOT,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            formatting = json.loads(
                (output_dir / "formatting_success.json").read_text(encoding="utf-8")
            )
            pending = json.loads(
                (
                    output_dir
                    / "refactor_provenance_correlated_not_proven.json"
                ).read_text(encoding="utf-8")
            )

            self.assertTrue(formatting["success"])
            self.assertEqual(formatting["exit_code"], 0)
            self.assertEqual(formatting["metadata"]["release_readiness"]["status"], "ready")
            self.assertFalse(pending["success"])
            self.assertEqual(pending["exit_code"], 1)
            self.assertEqual(json.loads(pending["stdout"])["status"], "pending")
            self.assertEqual(pending["metadata"]["mechanical_checks"]["status"], "passed")
            self.assertEqual(pending["metadata"]["semantic_checks"]["status"], "not_proven")
            self.assertEqual(pending["metadata"]["release_readiness"]["status"], "pending")
            refactor = pending["metadata"]["semantic_refactor_evidence"][
                "scalar_function_refactor"
            ]
            self.assertEqual(refactor["status"], "mechanically_valid")
            self.assertEqual(refactor["execution_authentication"], "not_authenticated")

    def _assert_demo_payload(self, skill_name, payload, output_dir):
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["skill"], skill_name)
        self.assertRegex(payload["scenario_id"], r"^demo-[a-z0-9-]+$")
        self.assertIn(payload["execution_level"], {"python-module", "hybrid-harness", "procedure-policy"})
        self.assertTrue(payload["generated_at"].endswith("Z"))

        for key in [
            "success_case",
            "blocked_or_failure_case",
            "contracts",
            "demo_specificity",
            "host_metadata",
            "artifacts",
            "verification",
        ]:
            self.assertIn(key, payload)

        self.assertEqual(payload["success_case"]["status"], "passed")
        self.assertIn("contract_type", payload["success_case"])
        self.assertTrue(payload["success_case"]["evidence"])
        self.assertIn("expected_behavior", payload["success_case"])
        self.assertIn("side_effects", payload["success_case"])
        self.assertEqual(payload["success_case"]["skill_demo_context"]["skill"], skill_name)
        self.assertEqual(payload["success_case"]["skill_demo_context"]["scenario_id"], payload["scenario_id"])
        if skill_name in {"token-optimizer", "command-output-harness"}:
            success_payload = payload["success_case"]["payload"]
            token_usage = success_payload["metadata"]["token_usage"]
            self.assertEqual(token_usage["strategy"], "command-output")
            self.assertEqual(token_usage["where_saved"]["strategy"], "command-output")
            self.assertGreater(
                token_usage["estimated_payload_tokens_before"],
                token_usage["estimated_payload_tokens_after"],
            )
            self.assertGreater(token_usage["estimated_payload_tokens_saved"], 0)
            self.assertGreater(token_usage["estimated_payload_token_savings_ratio"], 0.5)
            self.assertFalse(token_usage["billing_tokens_available"])
            self.assertFalse(token_usage["billing_counterfactual_available"])
            accounting = success_payload["runtime_token_accounting"]
            self.assertFalse(accounting["billing_tokens_available"])
            self.assertFalse(accounting["billing_counterfactual_available"])
            self.assertTrue(accounting["billing_tokens_unavailable_reason"])
            self.assertEqual(accounting["estimated_payload_scope"], "optimizer_local_estimated_payload")
            self.assertTrue(accounting["must_not_report_as_billable_usage"])
            self.assertTrue(success_payload["preserved_required_facts"])
            for fact in [
                "tests/test_invoice.py::test_total_rounding FAILED",
                "AssertionError",
                "119999 == 120000",
                "exit code: 1",
            ]:
                self.assertIn(fact, success_payload["stdout"])
        if skill_name == "compound-engineering-harness":
            success_payload = payload["success_case"]["payload"]
            for next_skill in [
                "workflow-skill-distiller",
                "memory-state-harness",
                "scenario-evaluation-harness",
            ]:
                self.assertIn(next_skill, success_payload["next_skills"])
            self.assertTrue(success_payload["learnings"])
            self.assertTrue(success_payload["regression_checks"])

        self.assertIn(payload["blocked_or_failure_case"]["status"], {"blocked", "failed"})
        self.assertIn("contract_type", payload["blocked_or_failure_case"])
        self.assertTrue(
            payload["blocked_or_failure_case"].get("blocked_reason")
            or payload["blocked_or_failure_case"].get("error_code")
        )
        self.assertIn("expected_behavior", payload["blocked_or_failure_case"])
        self.assertIn("remediation", payload["blocked_or_failure_case"])
        self.assertTrue(payload["blocked_or_failure_case"]["non_destructive"])
        self.assertEqual(payload["blocked_or_failure_case"]["skill_demo_context"]["skill"], skill_name)
        self.assertEqual(payload["blocked_or_failure_case"]["skill_demo_context"]["scenario_id"], payload["scenario_id"])
        self.assertNotEqual(payload["success_case"].get("payload"), payload["blocked_or_failure_case"].get("payload"))

        self.assertTrue(payload["contracts"], "demo must name at least one UAF contract")
        for contract in payload["contracts"]:
            self.assertIn("name", contract)
            self.assertIn("module", contract)
            self.assertTrue(contract["fields_checked"], contract)
            self.assertIn(contract["source"], {"dataclass", "gate-result", "policy-result", "artifact-validator"})
            if contract["source"] == "dataclass":
                self.assertTrue(contract["roundtrip_checked"], contract)
                self.assertEqual(contract["roundtrip_kind"], "dataclass_from_dict")
            else:
                self.assertFalse(contract["roundtrip_checked"], contract)
                self.assertTrue(contract["schema_validation_checked"], contract)
                self.assertEqual(contract["roundtrip_kind"], "mapping_schema_presence")

        specificity = payload["demo_specificity"]
        self.assertEqual(specificity["skill"], skill_name)
        self.assertEqual(specificity["scenario_id"], payload["scenario_id"])
        self.assertTrue(specificity["scenario_function"].endswith("_scenario"))
        self.assertTrue(specificity["success_context_bound"])
        self.assertTrue(specificity["blocked_context_bound"])
        self.assertTrue(specificity["success_and_blocked_are_distinct"])
        self.assertTrue(specificity["artifact_namespace_bound"])
        self.assertEqual(specificity["profile"]["skill"], skill_name)
        self.assertTrue(specificity["profile"]["capability_proven"])
        self.assertTrue(specificity["profile"]["failure_mode_proven"])
        self.assertTrue(specificity["profile"]["semantic_probe"])
        expected_capability, expected_failure, expected_probe = DEMO_SKILL_PROFILES[skill_name]
        self.assertEqual(specificity["profile"]["capability_proven"], expected_capability)
        self.assertEqual(specificity["profile"]["failure_mode_proven"], expected_failure)
        self.assertEqual(specificity["profile"]["semantic_probe"], expected_probe)
        self.assertEqual(payload["success_case"]["capability_proven"], expected_capability)
        self.assertEqual(payload["success_case"]["semantic_probe"], expected_probe)
        self.assertEqual(payload["blocked_or_failure_case"]["failure_mode_proven"], expected_failure)
        self.assertEqual(payload["blocked_or_failure_case"]["semantic_probe"], expected_probe)
        self.assertIn(expected_capability, "\n".join(payload["success_case"]["evidence"]))
        self.assertIn(expected_probe, "\n".join(payload["success_case"]["evidence"]))
        self.assertIn(expected_failure, "\n".join(payload["blocked_or_failure_case"]["evidence"]))
        self.assertIn(expected_probe, "\n".join(payload["blocked_or_failure_case"]["evidence"]))
        self.assertTrue(specificity["declared_implementation_targets"])
        self.assertTrue(specificity["resolved_implementation_targets"])
        self.assertEqual(specificity["skill_specific_probe"]["skill"], skill_name)
        self.assertTrue(specificity["skill_specific_probe"]["primary_target"])
        self.assertIn(
            specificity["skill_specific_probe"]["primary_target_status"],
            {"resolved", "template", "packaged_test_reference"},
        )
        self.assertEqual(
            specificity["skill_specific_probe"]["proof_kind"],
            "implementation-target-resolution-plus-contract-demo",
        )
        self.assertEqual(
            specificity["skill_specific_probe"]["semantic_probe"],
            specificity["profile"]["semantic_probe"],
        )
        self.assertTrue(specificity["skill_specific_probe"]["contract_modules"])
        self.assertIn(skill_name, specificity["unique_markers"])
        self.assertIn(payload["scenario_id"], specificity["unique_markers"])
        self.assertIn(specificity["profile"]["semantic_probe"], specificity["unique_markers"])

        self.assertIn(payload["host_metadata"]["selected_host"], {"local", "codex", "antigravity-style", "claude-code"})
        self.assertTrue(payload["host_metadata"]["host_mode_evidence"]["dispatch"])
        self.assertTrue(payload["host_metadata"]["host_mode_evidence"]["state"])
        self.assertTrue(payload["host_metadata"]["host_mode_evidence"]["panel"])
        self.assertEqual(payload["host_metadata"]["host_claim_scope"], "simulated_metadata_only")
        self.assertFalse(payload["host_metadata"]["behavioral_host_execution"])
        self.assertTrue(payload["host_metadata"]["behavioral_host_execution_reason"])
        self.assertEqual(payload["host_metadata"]["verified_host_artifacts"], [])
        self.assertGreaterEqual(len(payload["host_metadata"]["host_differences"]), 3)
        self.assertEqual(Path(payload["host_metadata"]["output_dir"]), output_dir)
        self.assertIn("python_version", payload["host_metadata"])
        self.assertIn("platform", payload["host_metadata"])
        self.assertFalse(payload["host_metadata"]["external_runtime_dependency"])

        self.assertTrue(payload["verification"]["runnable"])
        self.assertEqual(payload["verification"]["exit_code"], 0)
        self.assertTrue(payload["verification"]["stdout_json_only"])
        self.assertTrue(payload["verification"]["contract_roundtrip"])
        self.assertEqual(
            payload["verification"]["contract_validation_mode"],
            "dataclass_roundtrip_or_mapping_schema",
        )
        self.assertTrue(payload["verification"]["artifacts_within_output_dir"])
        self.assertTrue(payload["verification"]["artifacts_validated"])
        self.assertIn("runtime_observation", payload["verification"])
        self.assertEqual(payload["verification"]["runtime_observation"]["source"], "outer subprocess quality gate")

        self.assertTrue(payload["artifacts"], "demo must write at least one verifiable artifact")
        for artifact in payload["artifacts"]:
            artifact_path = Path(artifact["path"])
            self.assertTrue(artifact_path.exists(), artifact)
            self.assertTrue(artifact_path.is_relative_to(output_dir), artifact)
            self.assertTrue(artifact.get("validated"), artifact)
            self.assertTrue(artifact.get("checksum"), artifact)
            self.assertIn("validation_evidence", artifact)

        declared_paths = {Path(artifact["path"]).resolve() for artifact in payload["artifacts"]}
        generated_paths = {path.resolve() for path in output_dir.rglob("*") if path.is_file()}
        self.assertEqual(generated_paths, declared_paths)

    def test_unknown_skill_cannot_fall_back_to_generic_gate_demo(self):
        with self.assertRaises(ValueError):
            _scenario_for("new-unmapped-skill")

    def test_demo_host_modes_are_parameterized(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            evidence_by_host = {}
            for host in ["local", "codex", "antigravity-style", "claude-code"]:
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "src.skills.demo_scenarios",
                        "--skill",
                        "workflow-usability-harness",
                        "--host",
                        host,
                        "--output-dir",
                        str(output_root / host),
                    ],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    encoding="utf-8",
                    text=True,
                )

                self.assertEqual(completed.returncode, 0, completed.stderr)
                payload = json.loads(completed.stdout)
                self.assertEqual(payload["host_metadata"]["selected_host"], host)
                evidence_by_host[host] = payload["host_metadata"]["host_mode_evidence"]

            self.assertEqual(len({item["dispatch"] for item in evidence_by_host.values()}), 4)
            self.assertEqual(len({item["state"] for item in evidence_by_host.values()}), 4)

    def test_demo_validation_rejects_self_minted_profile_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "workflow-usability-harness"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.skills.demo_scenarios",
                    "--skill",
                    "workflow-usability-harness",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            payload["demo_specificity"]["profile"]["capability_proven"] = "NONSENSE CAPABILITY"
            payload["demo_specificity"]["profile"]["failure_mode_proven"] = "NONSENSE FAILURE"
            payload["demo_specificity"]["profile"]["semantic_probe"] = "NONSENSE PROBE"
            payload["success_case"]["capability_proven"] = "NONSENSE CAPABILITY"
            payload["success_case"]["semantic_probe"] = "NONSENSE PROBE"
            payload["blocked_or_failure_case"]["failure_mode_proven"] = "NONSENSE FAILURE"
            payload["blocked_or_failure_case"]["semantic_probe"] = "NONSENSE PROBE"

            errors = _validate_demo_payload("workflow-usability-harness", payload, output_dir)

            self.assertTrue(errors)
            self.assertTrue(any("semantic" in error or "capability" in error for error in errors), errors)

    def test_token_demo_validation_rejects_fake_host_billing_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "token-optimizer"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.skills.demo_scenarios",
                    "--skill",
                    "token-optimizer",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                encoding="utf-8",
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            token_usage = payload["success_case"]["payload"]["metadata"]["token_usage"]
            token_usage["host_actual_tokens_available"] = True
            token_usage["host_actual_tokens_used"] = 123456
            token_usage["host_actual_token_source"] = "fake-provider-billing"
            token_usage["billing_tokens_available"] = True

            errors = _validate_demo_payload("token-optimizer", payload, output_dir)

            self.assertTrue(any("host_actual" in error or "billing" in error for error in errors), errors)

    def test_token_and_command_demos_fail_nonzero_when_required_contract_fields_are_missing(self):
        malformed = {
            "success_case": {
                "payload": {
                    "metadata": {
                        "token_usage": {
                            "estimated_payload_tokens_before": 10,
                        }
                    }
                }
            }
        }
        for skill_dir_name in ["token_optimizer", "command_output_harness"]:
            with self.subTest(skill=skill_dir_name), tempfile.TemporaryDirectory() as tmp:
                demo_path = REPO_ROOT / "skills" / skill_dir_name / "scripts" / "demo.py"
                spec = importlib.util.spec_from_file_location(f"demo_{skill_dir_name}", demo_path)
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                stderr = io.StringIO()
                stdout = io.StringIO()
                with mock.patch("src.skills.demo_scenarios.run_skill_demo", return_value=malformed):
                    with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
                        exit_code = module.main(module.SKILL_NAME, ["--output-dir", tmp])

                self.assertNotEqual(exit_code, 0)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn("estimated_payload_tokens_after", stderr.getvalue())
                self.assertIn("demo_specificity", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
