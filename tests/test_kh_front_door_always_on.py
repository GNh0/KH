import json
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
            ],
        )
        self.assertIn("verification-before-completion-harness", summary["selected_not_executed_skills"])

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


if __name__ == "__main__":
    unittest.main()
