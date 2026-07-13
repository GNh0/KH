import json
import tempfile
import unittest
from pathlib import Path

from src.benchmarks.kh_bench_verified import load_verified_tasks
from src.benchmarks.practical_quality_gate import (
    _installed_cache_front_door_smoke_message,
    _release_content_hash,
    _release_identity_message,
    build_practical_quality_report,
)


def ok_install_audit():
    return {
        "status": "ok",
        "expected_source_version": "2.9.99",
        "installed_caches": [
            {"root": "C:/cache/kh-uaf/2.9.99", "plugin_version": "2.9.99"}
        ],
    }


def ok_cache_smoke():
    return {
        "status": "ok",
        "front_door_status": "ok",
        "skill_source": {"source_type": "codex-plugin-cache", "version": "2.9.99"},
        "release_identity": {
            "status": "ok",
            "content_hashes_match": True,
            "catalogs_valid": True,
            "catalog_names_match": True,
        },
    }


class PracticalQualityGateTests(unittest.TestCase):
    def test_static_ten_does_not_make_release_ready_without_practical_bench(self):
        static_report = {
            "success": True,
            "lowest_quality_score": 10.0,
            "low_quality_skills": [],
            "total_skills": 31,
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

        report = build_practical_quality_report(
            static_report,
            bench_report,
            plugin_install_audit_report=ok_install_audit(),
            installed_cache_front_door_report=ok_cache_smoke(),
        )

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

    def test_release_ready_requires_installed_cache_runtime_evidence(self):
        static_report = {
            "success": True,
            "lowest_quality_score": 10.0,
            "low_quality_skills": [],
            "total_skills": 31,
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

        self.assertFalse(report["release_ready"])
        blocking = {finding["name"] for finding in report["blocking_findings"]}
        self.assertIn("Codex plugin install audit", blocking)
        self.assertIn("installed-cache front-door smoke", blocking)

    def test_all_practical_checks_pass_for_release_ready_report(self):
        static_report = {
            "success": True,
            "lowest_quality_score": 10.0,
            "low_quality_skills": [],
            "total_skills": 31,
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

        report = build_practical_quality_report(
            static_report,
            bench_report,
            plugin_install_audit_report=ok_install_audit(),
            installed_cache_front_door_report=ok_cache_smoke(),
        )

        self.assertTrue(report["release_ready"])
        self.assertEqual(report["blocking_findings"], [])
        self.assertGreaterEqual(report["practical_confidence_score"], 9.0)

    def test_same_version_with_different_release_content_is_not_release_ready(self):
        static_report = {
            "success": True,
            "lowest_quality_score": 10.0,
            "low_quality_skills": [],
            "total_skills": 43,
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
        cache_smoke = ok_cache_smoke()
        cache_smoke["release_identity"] = {
            "status": "content_mismatch",
            "content_hashes_match": False,
            "catalogs_valid": True,
            "catalog_names_match": True,
        }

        report = build_practical_quality_report(
            static_report,
            bench_report,
            plugin_install_audit_report=ok_install_audit(),
            installed_cache_front_door_report=cache_smoke,
        )

        self.assertFalse(report["release_ready"])
        self.assertIn(
            "release content identity",
            {finding["name"] for finding in report["blocking_findings"]},
        )

    def test_release_content_hash_includes_manifest_declared_executable_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".codex-plugin").mkdir()
            (root / "bin").mkdir()
            (root / "plugin.json").write_text(
                json.dumps(
                    {
                        "entrypoint": "cli.py",
                        "runtime": {"executable": "bin/runtime.py"},
                    }
                ),
                encoding="utf-8",
            )
            (root / ".codex-plugin" / "plugin.json").write_text(
                json.dumps({"name": "kh-uaf"}),
                encoding="utf-8",
            )
            (root / "cli.py").write_text("print('cli-v1')\n", encoding="utf-8")
            (root / "bin" / "runtime.py").write_text(
                "print('runtime-v1')\n",
                encoding="utf-8",
            )

            baseline_hash, baseline_count = _release_content_hash(root)
            (root / "cli.py").write_text("print('cli-v2')\n", encoding="utf-8")
            cli_hash, cli_count = _release_content_hash(root)
            (root / "cli.py").write_text("print('cli-v1')\n", encoding="utf-8")
            (root / "bin" / "runtime.py").write_text(
                "print('runtime-v2')\n",
                encoding="utf-8",
            )
            runtime_hash, runtime_count = _release_content_hash(root)

            self.assertNotEqual(baseline_hash, cli_hash)
            self.assertNotEqual(baseline_hash, runtime_hash)
            self.assertEqual(baseline_count, 4)
            self.assertEqual(cli_count, baseline_count)
            self.assertEqual(runtime_count, baseline_count)

    def test_release_identity_hash_match_does_not_claim_authenticity(self):
        message = _release_identity_message(
            {
                "status": "ok",
                "content_hashes_match": True,
                "catalogs_valid": True,
                "catalog_names_match": True,
            }
        )

        self.assertIn("authenticity=unverified", message)
        self.assertNotIn("authenticity verified", message.lower())

    def test_benchmark_uses_estimated_payload_telemetry_name(self):
        task = next(
            item
            for item in load_verified_tasks()
            if item["instance_id"] == "khbench-context-optimization-001"
        )
        fields = {validator.get("field", "") for validator in task["fail_to_pass"]}

        self.assertIn("metadata.token_usage.estimated_payload_tokens_saved", fields)
        self.assertNotIn("metadata.token_usage.actual_tokens_saved", fields)

    def test_installed_cache_smoke_message_explains_version_mismatch(self):
        message = _installed_cache_front_door_smoke_message(
            {
                "status": "ok",
                "front_door_status": "ok",
                "skill_source": {
                    "source_type": "codex-plugin-cache",
                    "version": "2.9.93",
                },
            },
            {"expected_source_version": "2.9.94"},
        )

        self.assertIn("version mismatch", message)
        self.assertIn("installed=2.9.93", message)
        self.assertIn("expected=2.9.94", message)


if __name__ == "__main__":
    unittest.main()
