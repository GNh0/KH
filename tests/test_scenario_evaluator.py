import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.orchestration.scenario_evaluator import (
    build_scenario_report,
    default_scenarios,
    evaluate_scenarios,
    multi_turn_scenarios,
    stress_scenarios,
    write_trace_jsonl,
)


class ScenarioEvaluatorTests(unittest.TestCase):
    def test_default_scenarios_cover_common_sides_and_domains(self):
        scenarios = default_scenarios()

        self.assertGreaterEqual(len(scenarios), 28)
        self.assertGreaterEqual(len({scenario.side for scenario in scenarios}), 4)

        domains = {scenario.expected.domain for scenario in scenarios}
        for domain in [
            "software",
            "investment",
            "product-design",
            "legal",
            "medical",
            "security",
            "general",
        ]:
            self.assertIn(domain, domains)

    def test_report_has_meaningful_signals_without_unexpected_failures(self):
        evaluations = evaluate_scenarios(default_scenarios())
        report = build_scenario_report(evaluations)

        self.assertEqual(report["unexpected_failures"], [])
        self.assertGreaterEqual(report["summary"]["total"], 28)
        self.assertGreaterEqual(report["summary"]["domain_count"], 7)
        self.assertGreaterEqual(report["summary"]["meaningful_signal_count"], 12)

        signal_categories = set(report["summary"]["signal_categories"])
        for category in ["classification", "evidence", "gate", "resume"]:
            self.assertIn(category, signal_categories)

    def test_stress_scenarios_expand_coverage_without_unexpected_failures(self):
        scenarios = stress_scenarios()
        evaluations = evaluate_scenarios(scenarios)
        report = build_scenario_report(evaluations)

        self.assertGreaterEqual(len(scenarios), 190)
        self.assertGreaterEqual(len({scenario.side for scenario in scenarios}), 6)
        self.assertGreaterEqual(report["summary"]["domain_count"], 25)
        self.assertGreaterEqual(report["summary"]["meaningful_signal_count"], 360)
        self.assertEqual(report["unexpected_failures"], [])

    def test_multi_turn_scenarios_cover_varied_conversation_lengths(self):
        scenarios = multi_turn_scenarios()
        evaluations = evaluate_scenarios(scenarios)
        report = build_scenario_report(evaluations)

        conversation_ids = {
            tag.removeprefix("conversation:")
            for scenario in scenarios
            for tag in scenario.tags
            if tag.startswith("conversation:")
        }
        turn_counts = {
            conversation_id: sum(
                f"conversation:{conversation_id}" in scenario.tags for scenario in scenarios
            )
            for conversation_id in conversation_ids
        }

        self.assertGreaterEqual(len(conversation_ids), 15)
        self.assertGreaterEqual(min(turn_counts.values()), 2)
        self.assertGreaterEqual(max(turn_counts.values()), 10)
        self.assertIn("multi-turn", {scenario.side for scenario in scenarios})
        self.assertEqual(report["unexpected_failures"], [])

    def test_resume_context_requires_handoff_evidence_for_heavy_work(self):
        scenario = next(
            item
            for item in default_scenarios()
            if item.scenario_id == "resume-software-session-001"
        )

        evaluation = evaluate_scenarios([scenario])[0]

        self.assertTrue(evaluation.passed, evaluation.findings)
        self.assertIn("resume_handoff", evaluation.actual["evidence_required"])
        self.assertIn("resume", {signal["category"] for signal in evaluation.signals})

    def test_trace_jsonl_writer_outputs_one_record_per_scenario(self):
        evaluations = evaluate_scenarios(default_scenarios()[:3])

        with tempfile.TemporaryDirectory() as temp_dir:
            trace_path = Path(temp_dir) / "scenario_trace.jsonl"
            write_trace_jsonl(evaluations, trace_path)
            lines = trace_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 3)
        payloads = [json.loads(line) for line in lines]
        self.assertTrue(all("scenario_id" in payload for payload in payloads))
        self.assertTrue(all("signals" in payload for payload in payloads))

    def test_module_cli_outputs_summary_json(self):
        completed = subprocess.run(
            [sys.executable, "-m", "src.orchestration.scenario_evaluator", "--summary"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertGreaterEqual(payload["summary"]["total"], 28)
        self.assertEqual(payload["unexpected_failures"], [])

    def test_module_cli_outputs_stress_summary_json(self):
        completed = subprocess.run(
            [sys.executable, "-m", "src.orchestration.scenario_evaluator", "--summary", "--stress"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertGreaterEqual(payload["summary"]["total"], 190)
        self.assertEqual(payload["unexpected_failures"], [])


if __name__ == "__main__":
    unittest.main()
