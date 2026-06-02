import json
import subprocess
import sys
import tempfile
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
        self.assertIn("always-on-front-door", payload["recommended_skills"])
        self.assertIn("automatic-intake-harness", payload["recommended_skills"])
        self.assertIn("plugin-composition-policy", payload["recommended_skills"])
        self.assertIn("request-complexity-router", payload["recommended_skills"])
        self.assertIn("skill-catalog", payload["recommended_skills"])
        self.assertEqual(
            payload["skill_statuses"]["always-on-front-door"]["status"],
            "applied",
        )
        self.assertEqual(
            payload["skill_statuses"]["automatic-intake-harness"]["status"],
            "applied",
        )
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
                "always-on-front-door",
                "automatic-intake-harness",
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

    def test_skill_local_front_door_wrapper_runs_outside_repo_root(self):
        repo_root = Path(__file__).resolve().parents[1]
        wrapper = repo_root / "skills" / "always_on_front_door" / "scripts" / "front_door.py"
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(wrapper),
                    "--prompt",
                    "Build a small HTML todo tool and verify it.",
                    "--project",
                    tmp,
                    "--host",
                    "codex",
                    "--summary",
                ],
                cwd=tmp,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["plugin_route"]["controller"], "kh")
        self.assertIn("always-on-front-door", payload["runtime_applied_skills"])

    def test_ordinary_non_trivial_request_runs_automatic_intake_without_kh_terms(self):
        result = build_kh_front_door(
            "Build a small HTML todo tool and verify it.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["classification"]["complexity"], "heavy")
        self.assertEqual(payload["classification"]["domain"], "software")
        self.assertEqual(payload["plugin_route"]["controller"], "kh")
        self.assertEqual(
            payload["runtime_applied_skills"],
            [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
            ],
        )
        self.assertIn("verification-before-completion-harness", payload["selected_not_executed_skills"])

    def test_vague_product_development_selects_brainstorming_without_kh_terms(self):
        result = build_kh_front_door(
            "C:\\work\\BrainstormEntryOnly "
            "\ud3f4\ub354\uc5d0 \uc6b4\uc601\uc9c0\uc6d0 \uc81c\ud488 \uac1c\ubc1c\ud574\uc918.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["domain"], "product")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertEqual(payload["plugin_route"]["controller"], "kh")
        self.assertIn("brainstorming-harness", payload["recommended_skills"])
        self.assertIn("brainstorming-harness", payload["selected_not_executed_skills"])
        self.assertEqual(
            payload["skill_status_summary"]["brainstorming-harness"]["status"],
            "skipped_with_rationale",
        )
        self.assertTrue(
            any("Apply `brainstorming-harness`" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("do not implement" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("user approves the direction" in action for action in payload["required_next_actions"])
        )

    def test_vague_inventory_dashboard_development_selects_brainstorming(self):
        result = build_kh_front_door(
            "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260602_J "
            "\ud3f4\ub354\uc5d0\uc11c \uc7ac\uace0 \uc785\ucd9c\uace0 \uad00\ub9ac \ub300\uc2dc\ubcf4\ub4dc \uac1c\ubc1c\ud574\uc918.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["domain"], "operations")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("brainstorming-harness", payload["recommended_skills"])
        self.assertIn("brainstorming-harness", payload["selected_not_executed_skills"])
        self.assertTrue(
            any("do not implement" in action for action in payload["required_next_actions"])
        )

    def test_non_software_discovery_selects_brainstorming_without_kh_terms(self):
        result = build_kh_front_door(
            "C:\\work\\ResearchPlan folder needs a customer churn analysis approach planned.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["domain"], "analysis")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("brainstorming-harness", payload["recommended_skills"])
        self.assertIn("brainstorming-harness", payload["selected_not_executed_skills"])
        self.assertTrue(
            any("analysis output" in action for action in payload["required_next_actions"])
        )

    def test_command_output_request_selects_log_harness_before_ambiguity(self):
        result = build_kh_front_door(
            "Summarize this long pytest log and preserve the failing test name, file line, assertion values, and exit code.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("command-output-harness", payload["recommended_skills"])
        self.assertIn("token-optimizer", payload["recommended_skills"])
        self.assertIn("command-output-harness", payload["selected_not_executed_skills"])
        self.assertEqual(
            payload["skill_status_summary"]["command-output-harness"]["status"],
            "skipped_with_rationale",
        )


if __name__ == "__main__":
    unittest.main()
