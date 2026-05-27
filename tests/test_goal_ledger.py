import json
import tempfile
import unittest
from pathlib import Path

from src.orchestration.goal_ledger import GoalLedger


class GoalLedgerTests(unittest.TestCase):
    def test_save_and_load_current_goal_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = GoalLedger(tmp)
            goal = {
                "objective": "build api",
                "status": "active",
                "evidence_required": ["tests"],
                "evidence": [],
            }

            state = ledger.save_current_goal(
                goal,
                active_task="dispatch workflow",
                tasks={"pending": ["main.py"], "in_progress": [], "completed": [], "blocked": []},
                next_recommended_action="run workflow dispatch",
            )

            self.assertTrue(Path(ledger.current_goal_path).exists())
            loaded = ledger.load_current_goal()
            self.assertEqual(loaded, state)
            self.assertEqual(loaded["objective"], "build api")
            self.assertEqual(loaded["status"], "active")
            self.assertEqual(loaded["tasks"]["pending"], ["main.py"])
            self.assertEqual(loaded["goal"], goal)

    def test_append_event_writes_ordered_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = GoalLedger(tmp)

            first = ledger.append_event("goal_created", {"objective": "build api"})
            second = ledger.append_event("evidence_added", {"evidence": "tests"})
            events = ledger.read_events()

            self.assertEqual([event["event_type"] for event in events], ["goal_created", "evidence_added"])
            self.assertEqual(events[0]["payload"], {"objective": "build api"})
            self.assertEqual(events[1]["payload"], {"evidence": "tests"})
            self.assertEqual(events[0], first)
            self.assertEqual(events[1], second)

            lines = Path(ledger.events_path).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["event_type"], "goal_created")

    def test_resolve_project_path_rejects_paths_outside_project_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = GoalLedger(tmp)
            safe_path = ledger.resolve_project_path(".uaf/state/current_goal.json")

            self.assertTrue(str(safe_path).startswith(str(Path(tmp).resolve())))
            with self.assertRaises(ValueError):
                ledger.resolve_project_path("../outside.json")
            with self.assertRaises(ValueError):
                ledger.resolve_project_path(str(Path(tmp).resolve().parent / "outside.json"))


if __name__ == "__main__":
    unittest.main()
