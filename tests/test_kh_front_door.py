import json
import subprocess
import sys
import unittest
from pathlib import Path

from src.orchestration.kh_front_door import build_kh_front_door


class KhFrontDoorTests(unittest.TestCase):
    def test_front_door_resolves_repo_local_skills_and_routes_kh_request(self):
        result = build_kh_front_door(
            "Use the KH plugin for this source analysis.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_dict()

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["skill_source"]["source_type"], "repo-local")
        self.assertGreaterEqual(payload["skill_source"]["skill_count"], 38)
        self.assertEqual(payload["plugin_route"]["controller"]["provider_id"], "kh")
        self.assertIn("plugin-composition-policy", payload["recommended_skills"])
        self.assertIn("request-complexity-router", payload["recommended_skills"])
        self.assertIn("skill-catalog", payload["recommended_skills"])
        self.assertEqual(
            payload["skill_statuses"]["plugin-composition-policy"]["status"],
            "applied",
        )
        self.assertEqual(
            payload["skill_statuses"]["request-complexity-router"]["application_mode"],
            "runtime",
        )

    def test_front_door_flags_stale_host_cache_paths(self):
        old_cache_path = (
            r"C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf"
            r"\2.9.25\skills\parallel_orchestration_harness\SKILL.md"
        )

        result = build_kh_front_door(
            "Use the KH plugin for this source analysis.",
            project=Path.cwd(),
            host="codex",
            host_skill_paths=[old_cache_path],
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["front_door_status"], "blocked")
        self.assertEqual(
            payload["stale_or_missing_skill_paths"][0]["status"],
            "stale_kh_cache_path",
        )
        self.assertTrue(
            any("stale KH cache" in warning for warning in payload["warnings"])
        )

    def test_heavy_route_selects_runtime_skills_without_claiming_they_ran(self):
        result = build_kh_front_door(
            "Use KH to implement this workflow and prove it with tests.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_dict()

        self.assertEqual(payload["classification"]["complexity"], "heavy")
        self.assertIn("goal-state-harness", payload["recommended_skills"])
        self.assertIn("verification-before-completion-harness", payload["recommended_skills"])
        self.assertEqual(
            payload["skill_statuses"]["goal-state-harness"]["status"],
            "skipped_with_rationale",
        )
        self.assertEqual(
            payload["skill_statuses"]["goal-state-harness"]["application_mode"],
            "procedural",
        )
        self.assertEqual(
            payload["skill_statuses"]["token-optimizer"]["status"],
            "skipped_with_rationale",
        )
        self.assertEqual(
            payload["large_work_orchestration_bundle"]["token_optimizer_status"],
            "skipped_with_rationale",
        )
        self.assertTrue(payload["large_work_bundle_validation"]["valid"])

    def test_cli_summary_outputs_machine_readable_front_door_json(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.orchestration.kh_front_door",
                "--prompt",
                "Use the KH plugin for this source analysis.",
                "--project",
                ".",
                "--host",
                "codex",
                "--summary",
            ],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["plugin_route"]["controller"], "kh")
        self.assertIn("skill-catalog", payload["recommended_skills"])
        self.assertEqual(
            payload["runtime_applied_skills"],
            [
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
        )
        self.assertEqual(
            payload["skill_status_summary"]["skill-catalog"]["status"],
            "applied",
        )
        self.assertIn("token-optimizer", payload["selected_not_executed_skills"])


if __name__ == "__main__":
    unittest.main()
