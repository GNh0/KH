import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.orchestration.kh_front_door import build_kh_front_door
from src.orchestration.plugin_composition import compose_plugin_route
from src.orchestration.request_classifier import classify_request
from src.orchestration.session_skill_audit import analyze_session_skills
from src.skills.uaf_skill_catalog import collect_packaged_skills


class AlwaysOnFrontDoorTests(unittest.TestCase):
    def write_session(self, events):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "session.jsonl"
        lines = [
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {"id": "always-on-front-door-test", "cwd": str(Path(tmp.name))},
                }
            )
        ]
        lines.extend(json.dumps(event) for event in events)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_always_on_front_door_runs_for_ordinary_work_without_kh_terms(self):
        request = "Build a small HTML dashboard in this folder and verify it."
        classification = classify_request(request, {"host": "codex"})
        route = compose_plugin_route(
            request,
            providers=[
                {
                    "provider_id": "kh",
                    "capabilities": ["workflow_control", "memory_goal_resume", "domain_orchestration"],
                }
            ],
            context={"host": "codex"},
        )
        catalog = collect_packaged_skills()
        result = build_kh_front_door(request, project=Path.cwd(), host="codex")
        summary = result.to_summary_dict()

        self.assertEqual(classification.complexity, "heavy")
        self.assertEqual(route.controller.provider_id, "kh")
        self.assertIn("always-on-front-door", {skill["name"] for skill in catalog["skills"]})
        self.assertEqual(summary["front_door_status"], "ok")
        self.assertEqual(
            summary["runtime_applied_skills"],
            [
                "always-on-front-door",
                "automatic-intake-harness",
                "plugin-composition-policy",
                "request-complexity-router",
                "skill-catalog",
                "token-optimizer",
            ],
        )
        self.assertEqual(summary["skill_status_summary"]["token-optimizer"]["status"], "applied")
        self.assertIn("estimated_payload_tokens_before", summary["token_optimizer_decision"])
        self.assertIn("verification-before-completion-harness", summary["selected_not_executed_skills"])

    def test_new_korean_web_product_request_blocks_until_brainstorming(self):
        request = (
            r"C:\Users\KONEIT\Desktop\Jang\asdfasdf "
            "\uc774 \uacbd\ub85c\uc5d0 \uc77c\uc815,\ud68c\uc758\ub85d\uc744 "
            "\uc815\ub9ac\ud558\ub294 \uc6f9 \ud648\ud398\uc774\uc9c0\ub97c "
            "\ud558\ub098 \ub9cc\ub4e4\uace0\uc2f6\ub124 pdf\ub97c \uc62c\ub9ac\uba74 "
            "pdf\uc758 \ub0b4\uc6a9\uc774 \uadf8\ub300\ub85c \uc800\uc7a5\ub418\uace0 \ud558\ub294"
        )

        classification = classify_request(request, {"host": "codex"})
        result = build_kh_front_door(
            request,
            project=r"C:\Users\KONEIT\Desktop\Jang\asdfasdf",
            host="codex",
        )
        summary = result.to_summary_dict()

        self.assertEqual(classification.recommended_execution, "skill_read")
        self.assertIn("brainstorming-harness", classification.required_harnesses)
        self.assertFalse(summary["execution_gate"]["can_execute"])
        self.assertEqual(summary["execution_gate"]["status"], "blocked_until_brainstorming_handoff")
        self.assertIn("MEMORY.md_lookup", summary["execution_gate"]["blocked_actions"])
        self.assertIn("brainstorming-harness", summary["immediate_next_skills"])
        self.assertNotIn("brainstorming-harness", summary["selected_not_executed_skills"])

    def test_new_korean_web_product_request_without_pdf_still_brainstorms(self):
        request = (
            r"C:\Users\KONEIT\Desktop\Jang\asdfasdf "
            "\uacbd\ub85c\uc5d0 \uc77c\uc815,\ud68c\uc758\ub85d\uc744 "
            "\uc815\ub9ac\ud558\ub294 \uc6f9 \ud648\ud398\uc774\uc9c0\ub97c "
            "\ud558\ub098 \ub9cc\ub4e4\uace0\uc2f6\ub124"
        )

        classification = classify_request(request, {"host": "codex"})
        result = build_kh_front_door(
            request,
            project=r"C:\Users\KONEIT\Desktop\Jang\asdfasdf",
            host="codex",
        )
        summary = result.to_summary_dict()

        self.assertIn("brainstorming-harness", classification.required_harnesses)
        self.assertFalse(summary["execution_gate"]["can_execute"])

    def test_garbled_path_pdf_project_request_does_not_open_execution_gate(self):
        request = (
            r"C:\Users\KONEIT\Desktop\Jang\asdfasdf "
            "?? ??? ??? ??? ??? pdf?? ?? pdf??? ??? ???"
        )

        classification = classify_request(request, {"host": "codex"})
        result = build_kh_front_door(
            request,
            project=r"C:\Users\KONEIT\Desktop\Jang\asdfasdf",
            host="codex",
        )
        summary = result.to_summary_dict()

        self.assertIn("brainstorming-harness", classification.required_harnesses)
        self.assertFalse(summary["execution_gate"]["can_execute"])
        self.assertIn("global_codex_MEMORY.md", summary["execution_gate"]["blocked_actions"])

    def test_contextual_kh_audit_repair_followup_opens_large_work_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "docs" / "kh").mkdir(parents=True)
            request = (
                "\uc774\uc81c \uadf8\ub7fc \uadf8 \uae30\uc900\uc73c\ub85c "
                "\ub2e4\uc2dc \uc2f9\ub2e4 \ubcf4\uc644\ud558\uc790??"
            )

            result = build_kh_front_door(request, project=project, host="codex")

        summary = result.to_summary_dict()
        self.assertEqual(summary["classification"]["complexity"], "heavy")
        self.assertEqual(summary["classification"]["recommended_execution"], "role_dag")
        self.assertEqual(summary["plugin_route"]["controller"], "kh")
        self.assertEqual(summary["execution_gate"]["status"], "blocked_until_large_work_preflight")
        self.assertIn("goal-state-harness", summary["immediate_next_skills"])
        self.assertIn("workflow-usability-harness", summary["immediate_next_skills"])

    def test_contextual_kh_audit_repair_followup_uses_request_context_without_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = (
                "\uc774\uc81c \uadf8\ub7fc \uadf8 \uae30\uc900\uc73c\ub85c "
                "\ub2e4\uc2dc \uc2f9\ub2e4 \ubcf4\uc644\ud558\uc790??"
            )
            result = build_kh_front_door(
                request,
                project=tmp,
                host="codex",
                request_context={
                    "domain": "software",
                    "has_active_artifact": True,
                    "requires_resume": True,
                    "prior_context_kind": "session_audit",
                },
            )

        summary = result.to_summary_dict()
        self.assertEqual(summary["classification"]["complexity"], "heavy")
        self.assertEqual(summary["execution_gate"]["status"], "blocked_until_large_work_preflight")

    def test_front_door_cli_accepts_context_json_for_session_audit_followup(self):
        with tempfile.TemporaryDirectory() as tmp:
            prompt_file = Path(tmp) / "prompt.txt"
            prompt_file.write_text(
                "\uc774\uc81c \uadf8\ub7fc \uadf8 \uae30\uc900\uc73c\ub85c "
                "\ub2e4\uc2dc \uc2f9\ub2e4 \ubcf4\uc644\ud558\uc790??",
                encoding="utf-8",
            )
            context = json.dumps(
                {
                    "domain": "software",
                    "has_active_artifact": True,
                    "requires_resume": True,
                    "prior_context_kind": "session_audit",
                }
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.orchestration.kh_front_door",
                    "--prompt-file",
                    str(prompt_file),
                    "--project",
                    tmp,
                    "--host",
                    "codex",
                    "--context-json",
                    context,
                    "--summary",
                ],
                capture_output=True,
                encoding="utf-8",
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["classification"]["complexity"], "heavy")
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_large_work_preflight")

    def test_kh_project_marker_does_not_turn_security_fix_into_audit_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "docs" / "kh").mkdir(parents=True)
            result = build_kh_front_door(
                "Fix the SQL injection vulnerability and add regression tests.",
                project=project,
                host="codex",
            )

        classification = result.classification
        self.assertEqual(classification["domain"], "security")
        self.assertIn("security_review", classification["evidence_required"])
        self.assertNotIn("contextual_audit_repair_request", classification["reasons"])

    def test_kh_active_directive_does_not_turn_react_routing_bug_into_audit_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_kh_front_door(
                "Fix the React routing bug in this app.",
                project=tmp,
                host="codex",
                request_context={"kh_active_directive": "active"},
            )

        classification = result.classification
        self.assertEqual(classification["domain"], "software")
        self.assertNotIn("contextual_audit_repair_request", classification["reasons"])

    def test_session_audit_flags_front_door_miss_as_always_on_failure(self):
        path = self.write_session(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": "Build a small HTML dashboard in this folder and verify it.",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "shell_command",
                        "arguments": "Get-ChildItem -Recurse -Filter *.html",
                    },
                },
            ]
        )

        audit = analyze_session_skills(path)

        self.assertIn("always-on-front-door", audit.coverage["required_missing_skill_names"])
        self.assertTrue(
            any(
                issue["skill"] == "always-on-front-door"
                and issue["status"] == "missing_front_door"
                and issue["severity"] == "P1"
                for issue in audit.issues
            )
        )

    def test_skill_documentation_targets_are_traceable(self):
        repo_root = Path(__file__).resolve().parents[1]
        always_on = repo_root / "skills/always_on_front_door/SKILL.md"
        automatic_intake = repo_root / "skills/automatic_intake_harness/SKILL.md"

        self.assertTrue(always_on.exists())
        self.assertTrue(automatic_intake.exists())
        self.assertIn("src.orchestration.kh_front_door.build_kh_front_door", always_on.read_text(encoding="utf-8"))
        self.assertIn("tests.test_kh_front_door_always_on", always_on.read_text(encoding="utf-8"))

    def test_windows_powershell_51_template_writes_bom_safe_prompt_and_context_json(self):
        repo_root = Path(__file__).resolve().parents[1]
        skill_text = (repo_root / "skills/always_on_front_door/SKILL.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("UTF8Encoding($false)", skill_text)
        self.assertIn("ConvertTo-Json -Depth 10", skill_text)
        self.assertIn("--context-file $contextPath", skill_text)


if __name__ == "__main__":
    unittest.main()
