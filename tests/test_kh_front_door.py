import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.orchestration.kh_front_door import _source_identity_for_root, build_kh_front_door


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

    def test_front_door_discovers_explicit_host_local_sql_formatting_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "sql-formatting"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: sql-formatting\n"
                "description: Use when formatting, cleaning, standardizing, or refactoring SQL/T-SQL.\n"
                "---\n"
                "# SQL Formatting\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                result = build_kh_front_door(
                    "Use sql-formatting to clean this query.",
                    project=Path.cwd(),
                    host="codex",
                )
        payload = result.to_dict()
        summary = result.to_summary_dict()

        self.assertEqual(summary["front_door_status"], "ok")
        self.assertEqual(summary["plugin_route"]["route"], "single")
        self.assertEqual(summary["plugin_route"]["controller"], "sql-formatting")
        self.assertEqual(payload["plugin_route"]["controller"]["capability"], "sql_formatting")
        provider_ids = {
            provider["provider_id"]
            for provider in payload["plugin_route"]["available_providers_snapshot"]
        }
        self.assertIn("kh", provider_ids)
        self.assertIn("sql-formatting", provider_ids)
        self.assertIn("explicit_user_request:sql-formatting", payload["plugin_route"]["reasons"])
        self.assertTrue(
            any("Apply selected provider `sql-formatting`" in action for action in payload["required_next_actions"])
        )

    def test_front_door_routes_light_sql_formatting_intent_to_host_local_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "sql-formatting"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: sql-formatting\n"
                "description: Use when formatting, cleaning, standardizing, or refactoring SQL/T-SQL.\n"
                "---\n"
                "# SQL Formatting\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                result = build_kh_front_door(
                    "Format this T-SQL query and preserve logic.",
                    project=Path.cwd(),
                    host="codex",
                )
        summary = result.to_summary_dict()

        self.assertEqual(summary["classification"]["complexity"], "light")
        self.assertEqual(summary["plugin_route"]["route"], "single")
        self.assertEqual(summary["plugin_route"]["controller"], "sql-formatting")
        self.assertTrue(
            any("Apply selected provider `sql-formatting`" in action for action in result.to_dict()["required_next_actions"])
        )

    def test_front_door_routes_actionable_pasted_sql_to_host_local_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "sql-formatting"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: sql-formatting\n"
                "description: Use when formatting, cleaning, standardizing, or refactoring SQL/T-SQL.\n"
                "---\n"
                "# SQL Formatting\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                result = build_kh_front_door(
                    "SELECT *\n"
                    "FROM BA011T\n"
                    "WHERE MAINCD = 'DZ010'\n\n"
                    "SELECT *\n"
                    "FROM BA011T\n"
                    "WHERE MAINCD = 'DZ011'\n\n"
                    "\uc774\ubbf8\uc9c0\ucc98\ub7fc \ub300\ubd84\ub958 \uc911\ubd84\ub958\ud574\uc11c "
                    "\uc21c\uc11c\ub85c \uc870\ud68c\ub418\ub3c4\ub85d \ud558\uace0\uc2f6\uac70\ub4e0?",
                    project=Path.cwd(),
                    host="codex",
                )
        payload = result.to_dict()
        summary = result.to_summary_dict()

        self.assertEqual(summary["plugin_route"]["route"], "single")
        self.assertEqual(summary["plugin_route"]["controller"], "sql-formatting")
        self.assertEqual(payload["plugin_route"]["controller"]["capability"], "sql_formatting")
        self.assertIn("specialist_trigger:sql-formatting:sql_formatting", payload["plugin_route"]["reasons"])
        self.assertIn("sql-formatting-style-harness", payload["recommended_skills"])
        self.assertTrue(
            any("Apply selected provider `sql-formatting`" in action for action in payload["required_next_actions"])
        )

    def test_front_door_does_not_route_provider_when_name_is_review_example(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "sql-formatting"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: sql-formatting\n"
                "description: Use when formatting, cleaning, standardizing, or refactoring SQL/T-SQL.\n"
                "---\n"
                "# SQL Formatting\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                result = build_kh_front_door(
                    "Review whether KH hides other skills such as `sql-formatting` etc.; "
                    "this is only a risk example, not a provider to apply, and not a request to format SQL.",
                    project=Path(tmp),
                    host="codex",
                )
        payload = result.to_dict()

        self.assertNotEqual(payload["plugin_route"]["controller"]["provider_id"], "sql-formatting")
        self.assertNotIn("explicit_user_request:sql-formatting", payload["plugin_route"]["reasons"])
        self.assertNotIn(
            "sql-formatting",
            {assistant["provider_id"] for assistant in payload["plugin_route"]["assistants"]},
        )
        self.assertNotIn("sql-formatting-style-harness", payload["recommended_skills"])
        self.assertFalse(
            any("Apply selected provider `sql-formatting`" in action for action in payload["required_next_actions"])
        )

    def test_heavy_non_kh_provider_route_still_requires_preflight_immediate_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "sql-formatting"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: sql-formatting\n"
                "description: Use when formatting, cleaning, standardizing, or refactoring SQL/T-SQL.\n"
                "---\n"
                "# SQL Formatting\n",
                encoding="utf-8",
            )
            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                result = build_kh_front_door(
                    "Use sql-formatting to refactor every SQL file in this project, "
                    "run verification, and prepare commit evidence.",
                    project=Path(tmp),
                    host="codex",
                )
        payload = result.to_dict()

        self.assertEqual(payload["plugin_route"]["controller"]["provider_id"], "sql-formatting")
        self.assertEqual(
            payload["execution_gate"]["status"],
            "blocked_until_large_work_preflight",
        )
        self.assertEqual(
            payload["immediate_next_skills"],
            [
                "goal-state-harness",
                "workflow-usability-harness",
                "token-optimizer",
                "host-agent-orchestration",
            ],
        )
        self.assertTrue(
            payload["required_next_actions"][0].startswith("NEXT SKILL EXECUTION")
        )

    def test_ambiguous_visual_query_order_blocks_execution_until_clarified(self):
        result = build_kh_front_door(
            "\uc774\ubbf8\uc9c0\ucc98\ub7fc \uc21c\uc11c\ub85c \uc870\ud68c\ub418\ub3c4\ub85d \ud558\uace0\uc2f6\uac70\ub4e0?",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["classification"]["complexity"], "ambiguous")
        self.assertEqual(payload["classification"]["recommended_execution"], "clarify")
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_clarification")
        self.assertIn("user_clarification", payload["execution_gate"]["required_before_execution"])

    def test_ambiguous_visual_query_order_with_active_artifact_blocks_execution(self):
        result = build_kh_front_door(
            "\uc774\ubbf8\uc9c0\ucc98\ub7fc \uc21c\uc11c\ub85c \uc870\ud68c\ub418\ub3c4\ub85d \ud558\uace0\uc2f6\uac70\ub4e0?",
            project=Path.cwd(),
            host="codex",
            request_context={"has_active_artifact": True},
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["classification"]["complexity"], "ambiguous")
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_clarification")

    def test_front_door_warns_but_recovers_from_stale_host_cache_paths(self):
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

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(
            payload["stale_or_missing_skill_paths"][0]["status"],
            "stale_kh_cache_path",
        )
        self.assertTrue(
            any("stale KH cache" in warning for warning in payload["warnings"])
        )
        self.assertTrue(
            any("Resolved KH skills from" in warning for warning in payload["warnings"])
        )

    def test_cache_root_is_reported_as_codex_plugin_cache(self):
        root = Path(
            r"C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.69"
        )

        source_type, version, reason = _source_identity_for_root(root)

        self.assertEqual(source_type, "codex-plugin-cache")
        self.assertEqual(version, "2.9.69")
        self.assertEqual(reason, "installed Codex plugin cache")

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
            "pending_immediate_execution",
        )
        self.assertEqual(
            payload["skill_statuses"]["goal-state-harness"]["application_mode"],
            "immediate_gate",
        )
        self.assertEqual(
            payload["skill_statuses"]["token-optimizer"]["status"],
            "pending_immediate_execution",
        )
        self.assertEqual(
            payload["large_work_orchestration_bundle"]["token_optimizer_status"],
            "blocked",
        )
        self.assertIn(
            "immediate next gate",
            payload["large_work_orchestration_bundle"]["token_optimizer_status_reason"],
        )
        self.assertTrue(payload["large_work_bundle_validation"]["valid"])
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(
            payload["execution_gate"]["status"],
            "blocked_until_large_work_preflight",
        )
        self.assertEqual(
            payload["immediate_next_skills"],
            [
                "goal-state-harness",
                "workflow-usability-harness",
                "token-optimizer",
                "host-agent-orchestration",
            ],
        )
        self.assertTrue(
            payload["required_next_actions"][0].startswith("NEXT SKILL EXECUTION")
        )
        for required in [
            "large_work_orchestration_bundle",
            "workspace_strategy",
            "token_optimizer_status",
            "subagent_strategy_with_rationale",
            "parallel_strategy_decision_with_rationale",
            "role_execution_audit.status_or_pre_role_skip",
            "guard_policy_or_rollback_strategy",
            "verification_plan",
        ]:
            self.assertIn(required, payload["execution_gate"]["required_before_execution"])
        for blocked in ["implementation", "file_writes", "db_writes", "completion_claim"]:
            self.assertIn(blocked, payload["execution_gate"]["blocked_actions"])
        self.assertTrue(
            any("HARD PRE-FLIGHT STOP" in action for action in payload["required_next_actions"])
        )

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
        self.assertIn("immediate_next_skills", payload)
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

    def test_cli_prompt_file_preserves_korean_request_for_brainstorming_gate(self):
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            prompt_file = Path(tmp) / "prompt.txt"
            prompt_file.write_text(
                (
                    r"C:\Users\KONEIT\Desktop\Jang\asdfasdf "
                    "\uacbd\ub85c\uc5d0 \uc77c\uc815,\ud68c\uc758\ub85d\uc744 "
                    "\uc815\ub9ac\ud558\ub294 \uc6f9 \ud648\ud398\uc774\uc9c0\ub97c "
                    "\ud558\ub098 \ub9cc\ub4e4\uace0\uc2f6\ub124"
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "src.orchestration.kh_front_door",
                    "--prompt-file",
                    str(prompt_file),
                    "--project",
                    r"C:\Users\KONEIT\Desktop\Jang\asdfasdf",
                    "--host",
                    "codex",
                    "--summary",
                ],
                cwd=repo_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        payload = json.loads(completed.stdout)

        self.assertIn("brainstorming-harness", payload["recommended_skills"])
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertIn("MEMORY.md_lookup", payload["execution_gate"]["blocked_actions"])

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
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(
            payload["execution_gate"]["status"],
            "blocked_until_large_work_preflight",
        )
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
        self.assertEqual(payload["immediate_next_skills"], ["brainstorming-harness"])
        self.assertNotIn("brainstorming-harness", payload["selected_not_executed_skills"])
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_brainstorming_handoff")
        self.assertIn("implementation", payload["execution_gate"]["blocked_actions"])
        self.assertIn("target_folder_inspection", payload["execution_gate"]["blocked_actions"])
        self.assertIn("target_folder_existence_check", payload["execution_gate"]["blocked_actions"])
        self.assertEqual(
            payload["skill_status_summary"]["brainstorming-harness"]["status"],
            "pending_immediate_execution",
        )
        self.assertTrue(
            any("Apply `brainstorming-harness`" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("do not implement" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("domain-first" in action and "operating model" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("required records/data" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("option choice is direction approval only" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("lock implementation scope" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("I will set the implementation scope as follows" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("separately asks to implement" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("target folder existence checks" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("Test-Path" in action and "Get-ChildItem" in action for action in payload["required_next_actions"])
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
        self.assertIn("brainstorming-harness", payload["immediate_next_skills"])
        self.assertNotIn("brainstorming-harness", payload["selected_not_executed_skills"])
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertIn("MEMORY.md_lookup", payload["execution_gate"]["blocked_actions"])
        self.assertIn("target_folder_inspection", payload["execution_gate"]["blocked_actions"])
        self.assertTrue(
            any("do not implement" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("target folder existence checks" in action for action in payload["required_next_actions"])
        )

    def test_brainstorm_followup_without_handoff_keeps_execution_closed(self):
        result = build_kh_front_door(
            "\uc0ac\uc6a9\uc790\uac00 \uc7ac\uace0 \uc785\ucd9c\uace0 \uad00\ub9ac "
            "\ub300\uc2dc\ubcf4\ub4dc 1\ubc88 \uae30\ubcf8 \uc7a5\ubd80\ud615 MVP "
            "\ubc29\ud5a5\uc744 \uc2b9\uc778\ud568. \ub300\uc0c1 \uacbd\ub85c "
            "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260604_C "
            "\uc5d0 \uad6c\ud604 \uc9c4\ud589.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["domain"], "operations")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("brainstorming-harness", payload["recommended_skills"])
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_brainstorming_handoff")
        self.assertIn("brainstorming-harness", payload["immediate_next_skills"])
        self.assertTrue(
            any("brainstorming-harness" in action for action in payload["required_next_actions"])
        )

    def test_brainstorm_handoff_approved_without_execution_approval_stays_closed(self):
        result = build_kh_front_door(
            "\uc0ac\uc6a9\uc790\uac00 \uc7ac\uace0 \uc785\ucd9c\uace0 \uad00\ub9ac "
            "\ub300\uc2dc\ubcf4\ub4dc 1\ubc88 \uae30\ubcf8 \uc7a5\ubd80\ud615 MVP "
            "\ubc29\ud5a5\uc744 \uc2b9\uc778\ud568. \ub300\uc0c1 \uacbd\ub85c "
            "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260604_C "
            "\uc5d0 \uad6c\ud604 \uc9c4\ud589.",
            project=Path.cwd(),
            host="codex",
            request_context={"brainstorm_handoff_approved": True},
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("brainstorming-harness", payload["recommended_skills"])
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_brainstorming_handoff")

    def test_reviewed_brainstorm_followup_opens_execution_gate(self):
        result = build_kh_front_door(
            "\uc0ac\uc6a9\uc790\uac00 \uc7ac\uace0 \uc785\ucd9c\uace0 \uad00\ub9ac "
            "\ub300\uc2dc\ubcf4\ub4dc 1\ubc88 \uae30\ubcf8 \uc7a5\ubd80\ud615 MVP "
            "\ubc29\ud5a5\uc744 \uc2b9\uc778\ud568. \ub300\uc0c1 \uacbd\ub85c "
            "C:\\Users\\KONEIT\\Desktop\\Jang\\SKillsTest\\RetestAutoRoute_20260604_C "
            "\uc5d0 \uad6c\ud604 \uc9c4\ud589.",
            project=Path.cwd(),
            host="codex",
            request_context={
                "has_brainstorm_handoff": True,
                "design_review_approved": True,
                "separate_implementation_approval": True,
            },
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["classification"]["complexity"], "heavy")
        self.assertEqual(payload["classification"]["domain"], "operations")
        self.assertEqual(payload["classification"]["recommended_execution"], "role_dag")
        self.assertNotIn("brainstorming-harness", payload["recommended_skills"])
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_large_work_preflight")
        self.assertIn("goal-state-harness", payload["immediate_next_skills"])

    def test_front_door_emits_machine_readable_memory_policy(self):
        result = build_kh_front_door(
            "Implement this workflow and keep scoped memory evidence.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["memory_policy"]["scope"], "project_chat")
        self.assertFalse(payload["memory_policy"]["global_codex_memory_allowed"])
        self.assertFalse(payload["memory_policy"]["host_memory_lookup_before_front_door_allowed"])
        self.assertTrue(payload["memory_policy"]["cross_scope_import_requires_explicit_user_approval"])

    def test_memory_state_request_requires_project_chat_scope_and_global_candidate_policy(self):
        result = build_kh_front_door(
            "영구메모리는 시스템메모리가 아니라 프로젝트/채팅/서브에이전트 스코프로 관리하고 "
            "중요한 것만 host global Codex memory 후보로 분리해줘.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_dict()
        summary = result.to_summary_dict()

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("memory-state-harness", payload["recommended_skills"])
        self.assertIn("memory-state-harness", summary["immediate_next_skills"])
        self.assertNotIn("memory-state-harness", summary["selected_not_executed_skills"])
        self.assertIn("memory_scope_decision", payload["classification"]["evidence_required"])
        self.assertIn("global_memory_candidate_policy", payload["classification"]["evidence_required"])
        self.assertTrue(
            any("project/chat-scoped prompt snapshots" in action for action in payload["required_next_actions"])
        )
        self.assertTrue(
            any("global_memory_candidate" in action for action in payload["required_next_actions"])
        )

    def test_memory_parallel_orchestration_routes_to_heavy_role_dag(self):
        result = build_kh_front_door(
            "프로젝트/채팅/중첩 서브에이전트 메모리와 병렬 오케스트레이션 역할 DAG가 "
            "실제로 동작하는지 구현하고 검증해줘.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["classification"]["complexity"], "heavy")
        self.assertEqual(payload["classification"]["recommended_execution"], "role_dag")
        self.assertIn("memory-state-harness", payload["recommended_skills"])
        self.assertIn("parallel-orchestration-harness", payload["recommended_skills"])
        self.assertIn("role-execution-audit-harness", payload["recommended_skills"])
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_large_work_preflight")
        self.assertTrue(
            any("Create or update GoalState" in action for action in payload["required_next_actions"])
        )

    def test_option_choice_without_execution_keeps_brainstorm_gate_closed(self):
        result = build_kh_front_door(
            "1\ubc88 \ub2e8\uc21c \uc7ac\uace0 \uc6d0\uc7a5\ud615\uc73c\ub85c \uc9c4\ud589\ud574\uc918.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["front_door_status"], "ok")
        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("brainstorming-harness", payload["recommended_skills"])
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_brainstorming_handoff")
        self.assertIn("design_review_approval", payload["execution_gate"]["required_before_execution"])
        self.assertIn("separate_implementation_approval", payload["execution_gate"]["required_before_execution"])
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
        self.assertIn("brainstorming-harness", payload["immediate_next_skills"])
        self.assertNotIn("brainstorming-harness", payload["selected_not_executed_skills"])
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
        self.assertIn("command-output-harness", payload["immediate_next_skills"])
        self.assertNotIn("command-output-harness", payload["selected_not_executed_skills"])
        self.assertEqual(
            payload["skill_status_summary"]["command-output-harness"]["status"],
            "pending_immediate_execution",
        )
        self.assertEqual(
            payload["skill_status_summary"]["command-output-harness"]["application_mode"],
            "immediate_gate",
        )

    def test_readonly_update_condition_question_does_not_trigger_large_preflight(self):
        result = build_kh_front_door(
            "\ud639\uc2dc \uc800\uac70 \uc218\uc815\ud560\ub54c \uccb4\ud06c\ub85c\uc9c1\uc774 "
            "\uc788\uc744\uae4c?? \uc5b4\ub5a4\uc0c1\ud669\uc5d0\uc120 \uc218\uc815\uc744 "
            "\ubabb\ud55c\ub2e4\ub358\uc9c0",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_dict()

        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("source_summary", payload["classification"]["evidence_required"])
        self.assertIn("readonly_source_condition_question", payload["classification"]["reasons"])
        self.assertTrue(payload["execution_gate"]["can_execute"])
        self.assertNotEqual(
            payload["execution_gate"]["status"],
            "blocked_until_large_work_preflight",
        )
        self.assertNotIn("goal-state-harness", payload["immediate_next_skills"])

    def test_list_double_click_update_condition_question_does_not_trigger_large_preflight(self):
        result = build_kh_front_door(
            "LIST \ub354\ube14\ud074\ub9ad\ud560\ub54c \uc218\uc815 \ubabb\ud558\ub294 \uc870\uac74\uc774 \uc788\uc5b4?",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_dict()

        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("source_summary", payload["classification"]["evidence_required"])
        self.assertIn("readonly_source_condition_question", payload["classification"]["reasons"])
        self.assertTrue(payload["execution_gate"]["can_execute"])
        self.assertNotEqual(
            payload["execution_gate"]["status"],
            "blocked_until_large_work_preflight",
        )

    def test_mixed_read_and_add_condition_command_triggers_large_preflight(self):
        result = build_kh_front_door(
            "\uc218\uc815 \ubabb\ud558\ub294 \uc870\uac74\uc774 \uc788\ub294\uc9c0 "
            "\ud655\uc778\ud558\uace0 \uc5c6\uc73c\uba74 \ucd94\uac00\ud574\uc918",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_dict()

        self.assertEqual(payload["classification"]["complexity"], "heavy")
        self.assertEqual(payload["classification"]["recommended_execution"], "role_dag")
        self.assertEqual(
            payload["execution_gate"]["status"],
            "blocked_until_large_work_preflight",
        )
        self.assertIn("goal-state-harness", payload["immediate_next_skills"])

    def test_single_condition_mutation_command_triggers_large_preflight(self):
        cases = [
            "\uccb4\ud06c\ub85c\uc9c1 \uc218\uc815\ud574\uc918",
            "\uccb4\ud06c\ub85c\uc9c1 \ucd94\uac00\ud574\uc918",
        ]

        for prompt in cases:
            with self.subTest(prompt=prompt):
                result = build_kh_front_door(prompt, project=Path.cwd(), host="codex")
                payload = result.to_dict()

                self.assertEqual(payload["classification"]["complexity"], "heavy")
                self.assertEqual(payload["classification"]["recommended_execution"], "role_dag")
                self.assertIn("source_condition_mutation_command", payload["classification"]["reasons"])
                self.assertEqual(
                    payload["execution_gate"]["status"],
                    "blocked_until_large_work_preflight",
                )
                self.assertIn("goal-state-harness", payload["immediate_next_skills"])

    def test_localized_selector_patch_does_not_trigger_large_preflight(self):
        result = build_kh_front_door(
            "standalone_resource.html \ud55c \uc904, .leave-list selector \ucd94\uac00",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_dict()

        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("localized_patch_continuation", payload["classification"]["reasons"])
        self.assertTrue(payload["execution_gate"]["can_execute"])
        self.assertNotEqual(
            payload["execution_gate"]["status"],
            "blocked_until_large_work_preflight",
        )
        self.assertNotIn("goal-state-harness", payload["immediate_next_skills"])

    def test_context_supplied_localized_patch_does_not_trigger_large_preflight(self):
        result = build_kh_front_door(
            "\uadf8\ub7fc \ucd94\uac00\ud574\uc918\ubd10",
            project=Path.cwd(),
            host="codex",
            request_context={
                "domain": "software",
                "has_active_artifact": True,
                "localized_patch_context": True,
                "target_selector": ".leave-list",
                "current_file": "standalone_resource.html",
            },
        )
        payload = result.to_dict()

        self.assertEqual(payload["classification"]["complexity"], "medium")
        self.assertEqual(payload["classification"]["recommended_execution"], "skill_read")
        self.assertIn("localized_patch_continuation", payload["classification"]["reasons"])
        self.assertTrue(payload["execution_gate"]["can_execute"])
        self.assertNotEqual(
            payload["execution_gate"]["status"],
            "blocked_until_large_work_preflight",
        )
        self.assertNotIn("goal-state-harness", payload["immediate_next_skills"])

    def test_subagent_packets_require_worker_workspace_decision_for_autonomy_tests(self):
        repo_root = Path(__file__).resolve().parents[1]
        packets = (repo_root / "skills" / "subagent_review_pipeline" / "references" / "standard-task-packets.md").read_text(
            encoding="utf-8"
        )
        skill = (repo_root / "skills" / "subagent_review_pipeline" / "SKILL.md").read_text(encoding="utf-8")
        combined = f"{packets}\n{skill}"

        for expected in [
            "`workspace_assignment`: `preassigned`",
            "`worker_decides`",
            "`workspace=not_preassigned`",
            "`target_repo`",
            "`worker_workspace_decision_required`",
            "Do not preassign worktree paths when the packet purpose is to test KH harness autonomy.",
            "worker-side worktree isolation decision",
            "`workspace_decision_source`",
            "`worktree_isolation_evidence`",
        ]:
            self.assertIn(expected, combined)

    def test_subagent_packets_use_adaptive_final_user_language_policy(self):
        repo_root = Path(__file__).resolve().parents[1]
        packets = (repo_root / "skills" / "subagent_review_pipeline" / "references" / "standard-task-packets.md").read_text(
            encoding="utf-8"
        )
        skill = (repo_root / "skills" / "subagent_review_pipeline" / "SKILL.md").read_text(encoding="utf-8")
        combined = f"{packets}\n{skill}".lower()

        self.assertIn("requested or apparent language", combined)
        self.assertIn("internal subagent reports may stay in english", combined)
        self.assertNotIn("must be korean", combined)
        self.assertNotIn("final report must be korean", combined)

    def test_pbl_sql_image_binding_request_requires_large_work_preflight(self):
        result = build_kh_front_door(
            "Use C:\\PblScripter with quality_470 / quality_004.pbl, trace the print button SQL, "
            "replace actual data in the report image with bound column names, and give me the image.",
            project=Path.cwd(),
            host="codex",
        )
        payload = result.to_summary_dict()

        self.assertEqual(payload["classification"]["complexity"], "heavy")
        self.assertEqual(payload["classification"]["recommended_execution"], "role_dag")
        self.assertIn("command-output-harness", payload["recommended_skills"])
        self.assertIn("artifact-render-qa-harness", payload["recommended_skills"])
        self.assertIn("deliverable-template-quality-harness", payload["recommended_skills"])
        self.assertIn("traceability-matrix-harness", payload["recommended_skills"])
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertEqual(
            payload["execution_gate"]["status"],
            "blocked_until_large_work_preflight",
        )
        self.assertIn(
            "command_output_filter_plan",
            payload["execution_gate"]["required_before_execution"],
        )
        self.assertIn(
            "deliverable_render_quality_plan",
            payload["execution_gate"]["required_before_execution"],
        )
        self.assertIn(
            "record_command_output_filter_plan",
            payload["execution_gate"]["allowed_setup_actions"],
        )
        self.assertIn(
            "record_deliverable_render_quality_plan",
            payload["execution_gate"]["allowed_setup_actions"],
        )


if __name__ == "__main__":
    unittest.main()
