import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.skills.uaf_skill_catalog import collect_packaged_skills


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

        self.assertIn(payload["blocked_or_failure_case"]["status"], {"blocked", "failed"})
        self.assertIn("contract_type", payload["blocked_or_failure_case"])
        self.assertTrue(
            payload["blocked_or_failure_case"].get("blocked_reason")
            or payload["blocked_or_failure_case"].get("error_code")
        )
        self.assertIn("expected_behavior", payload["blocked_or_failure_case"])
        self.assertIn("remediation", payload["blocked_or_failure_case"])
        self.assertTrue(payload["blocked_or_failure_case"]["non_destructive"])

        self.assertTrue(payload["contracts"], "demo must name at least one UAF contract")
        for contract in payload["contracts"]:
            self.assertIn("name", contract)
            self.assertIn("module", contract)
            self.assertTrue(contract["fields_checked"], contract)
            self.assertTrue(contract["roundtrip_checked"], contract)
            self.assertIn(contract["source"], {"dataclass", "gate-result", "policy-result", "artifact-validator"})

        self.assertIn(payload["host_metadata"]["selected_host"], {"local", "codex", "antigravity-style", "claude-code"})
        self.assertGreaterEqual(len(payload["host_metadata"]["host_differences"]), 3)
        self.assertEqual(Path(payload["host_metadata"]["output_dir"]), output_dir)
        self.assertIn("python_version", payload["host_metadata"])
        self.assertIn("platform", payload["host_metadata"])
        self.assertFalse(payload["host_metadata"]["external_runtime_dependency"])

        self.assertTrue(payload["verification"]["runnable"])
        self.assertEqual(payload["verification"]["exit_code"], 0)
        self.assertTrue(payload["verification"]["stdout_json_only"])
        self.assertTrue(payload["verification"]["contract_roundtrip"])
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


if __name__ == "__main__":
    unittest.main()
