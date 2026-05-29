import unittest

from src.benchmarks.kh_bench_verified import load_verified_tasks
from src.benchmarks.practical_quality_gate import build_practical_quality_report


class PracticalQualityGateTests(unittest.TestCase):
    def test_static_ten_does_not_make_release_ready_without_practical_bench(self):
        static_report = {
            "success": True,
            "lowest_quality_score": 10.0,
            "low_quality_skills": [],
            "total_skills": 27,
        }
        bench_report = {
            "benchmark": "KH-Bench Verified",
            "summary": {
                "total": 8,
                "passed": 7,
                "failed": 1,
                "invalid": 0,
                "infra_error": 0,
                "pass_rate": 0.875,
            },
            "unresolved": ["khbench-side-regression-markdown-001"],
        }

        report = build_practical_quality_report(static_report, bench_report)

        self.assertFalse(report["release_ready"])
        self.assertEqual(report["primary_signal"], "kh_bench_verified")
        self.assertEqual(report["static_quality_role"], "advisory_structure_gate")
        self.assertIn("khbench-side-regression-markdown-001", report["blocking_findings"][0]["message"])

    def test_release_ready_requires_side_regression_tasks_in_benchmark_catalog(self):
        tasks = load_verified_tasks()
        side_tasks = [task for task in tasks if task["category"] == "side-regression"]
        task_ids = {task["instance_id"] for task in side_tasks}

        self.assertGreaterEqual(len(side_tasks), 2)
        self.assertIn("khbench-side-regression-markdown-001", task_ids)
        self.assertIn("khbench-side-regression-product-spec-001", task_ids)
        for task in side_tasks:
            with self.subTest(task=task["instance_id"]):
                self.assertEqual(task["difficulty"], "hard")
                self.assertTrue(task["human_verified"])
                self.assertIn("SIDE", task["problem_statement"])
                self.assertTrue(task["fail_to_pass"])
                self.assertTrue(task["pass_to_pass"])

    def test_all_practical_checks_pass_for_release_ready_report(self):
        static_report = {
            "success": True,
            "lowest_quality_score": 10.0,
            "low_quality_skills": [],
            "total_skills": 27,
        }
        bench_report = {
            "benchmark": "KH-Bench Verified",
            "summary": {
                "total": 8,
                "passed": 8,
                "failed": 0,
                "invalid": 0,
                "infra_error": 0,
                "pass_rate": 1.0,
            },
            "unresolved": [],
        }

        report = build_practical_quality_report(static_report, bench_report)

        self.assertTrue(report["release_ready"])
        self.assertEqual(report["blocking_findings"], [])
        self.assertGreaterEqual(report["practical_confidence_score"], 9.0)


if __name__ == "__main__":
    unittest.main()
