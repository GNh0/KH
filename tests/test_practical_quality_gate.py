import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.benchmarks.kh_bench_verified import load_verified_tasks
from src.benchmarks.practical_quality_gate import (
    CANONICAL_RELEASE_HASH_ALGORITHM,
    RAW_RELEASE_HASH_ALGORITHM,
    _build_release_identity_report,
    _installed_cache_front_door_smoke_message,
    _release_content_hash,
    _release_content_hash_details,
    _release_identity_ok,
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
            "required_release_manifests_present": True,
            "manifest_identity_valid": True,
        },
    }


class PracticalQualityGateTests(unittest.TestCase):
    def _write_release_fixture(self, root: Path) -> None:
        (root / ".codex-plugin").mkdir(parents=True)
        (root / ".agents" / "plugins" / "kh-uaf").mkdir(parents=True)
        (root / "src").mkdir()
        skill_dir = root / "skills" / "release-identity-fixture"
        skill_dir.mkdir(parents=True)
        manifest = json.dumps({"name": "kh-uaf", "version": "2.9.130"})
        (root / "plugin.json").write_text(manifest, encoding="utf-8", newline="\n")
        (root / ".codex-plugin" / "plugin.json").write_text(
            manifest,
            encoding="utf-8",
            newline="\n",
        )
        (root / ".agents" / "plugins" / "kh-uaf" / "plugin.json").write_text(
            manifest,
            encoding="utf-8",
            newline="\n",
        )
        (root / "src" / "runtime.py").write_text(
            "FIRST = 1\nSECOND = 2\n",
            encoding="utf-8",
            newline="\n",
        )
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: release-identity-fixture\n"
            "description: Use when release identity tests need a valid skill catalog.\n"
            "---\n\n"
            "# Release Identity Fixture\n\n"
            "## KH Entry Contract\n\nApplied by the release identity fixture.\n\n"
            "## Workflow\n\n1. Compare canonical release content.\n\n"
            "## Required outputs\n\n- Identity evidence.\n\n"
            "## Common mistakes\n\n- Do not skip content comparison.\n\n"
            "## UAF implementation targets\n\n- `tests.test_practical_quality_gate`\n",
            encoding="utf-8",
            newline="\n",
        )

    def _write_manifest_identity(
        self,
        root: Path,
        relative_path: Path,
        *,
        name: str = "kh-uaf",
        version: str = "2.9.130",
    ) -> None:
        (root / relative_path).write_text(
            json.dumps({"name": name, "version": version}),
            encoding="utf-8",
            newline="\n",
        )

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

    def test_release_identity_accepts_utf8_text_eol_only_differences(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            (source / "src" / "legacy.py").write_bytes(b"FIRST = 1\nSECOND = 2\n")
            shutil.copytree(source, cache)
            (cache / "src" / "runtime.py").write_bytes(b"FIRST = 1\r\nSECOND = 2\r\n")
            (cache / "src" / "legacy.py").write_bytes(b"FIRST = 1\rSECOND = 2\r")

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "ok")
        self.assertTrue(identity["content_hashes_match"])
        self.assertFalse(identity["raw_content_hashes_match"])
        self.assertEqual(identity["content_hash_algorithm"], CANONICAL_RELEASE_HASH_ALGORITHM)

    def test_release_identity_rejects_source_internal_manifest_name_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            mismatched_path = Path(".agents") / "plugins" / "kh-uaf" / "plugin.json"
            self._write_manifest_identity(
                source,
                mismatched_path,
                name="kh-uaf-source-drift",
            )

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertFalse(identity["manifest_identity_valid"])
        self.assertEqual(identity["source_manifest_identity"]["status"], "mismatch")
        self.assertEqual(identity["cache_manifest_identity"]["status"], "ok")
        mismatch = identity["source_manifest_identity"]["mismatched_values"]
        self.assertEqual([item["field"] for item in mismatch], ["name"])
        self.assertEqual(
            {item["value"] for item in mismatch[0]["values"]},
            {"kh-uaf", "kh-uaf-source-drift"},
        )
        self.assertFalse(_release_identity_ok(identity))

    def test_release_identity_rejects_cache_internal_manifest_version_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            mismatched_path = Path(".codex-plugin") / "plugin.json"
            self._write_manifest_identity(
                cache,
                mismatched_path,
                version="2.9.131",
            )

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertFalse(identity["manifest_identity_valid"])
        self.assertEqual(identity["source_manifest_identity"]["status"], "ok")
        self.assertEqual(identity["cache_manifest_identity"]["status"], "mismatch")
        mismatch = identity["cache_manifest_identity"]["mismatched_values"]
        self.assertEqual([item["field"] for item in mismatch], ["version"])
        self.assertEqual(
            {item["value"] for item in mismatch[0]["values"]},
            {"2.9.130", "2.9.131"},
        )

    def test_release_identity_rejects_source_cache_manifest_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            for relative_path in (
                Path("plugin.json"),
                Path(".codex-plugin") / "plugin.json",
                Path(".agents") / "plugins" / "kh-uaf" / "plugin.json",
            ):
                self._write_manifest_identity(cache, relative_path, version="2.9.131")

            identity = _build_release_identity_report(source, cache)

        self.assertFalse(identity["manifest_identity_valid"])
        self.assertEqual(identity["source_manifest_identity"]["status"], "ok")
        self.assertEqual(identity["cache_manifest_identity"]["status"], "ok")
        self.assertEqual(
            identity["source_cache_manifest_identity_mismatches"],
            [
                {
                    "field": "version",
                    "source_value": "2.9.130",
                    "cache_value": "2.9.131",
                }
            ],
        )

    def test_release_identity_rejects_invalid_manifest_json_with_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            invalid_path = source / ".codex-plugin" / "plugin.json"
            invalid_path.write_text("{not-json", encoding="utf-8", newline="\n")

            identity = _build_release_identity_report(source, cache)

        self.assertFalse(identity["manifest_identity_valid"])
        self.assertEqual(identity["source_manifest_identity"]["status"], "invalid")
        self.assertEqual(identity["cache_manifest_identity"]["status"], "ok")
        self.assertEqual(
            identity["source_manifest_identity"]["invalid_manifests"][0]["path"],
            str(invalid_path.resolve()),
        )
        self.assertEqual(
            identity["source_manifest_identity"]["invalid_manifests"][0]["reason"],
            "invalid_json",
        )
        self.assertEqual(identity["source_manifest_identity"]["missing_values"], [])
        self.assertEqual(identity["source_manifest_identity"]["mismatched_values"], [])

    def test_release_identity_rejects_missing_manifest_identity_value_with_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            missing_value_path = source / "plugin.json"
            missing_value_path.write_text(
                json.dumps({"version": "2.9.130"}),
                encoding="utf-8",
                newline="\n",
            )

            identity = _build_release_identity_report(source, cache)

        self.assertFalse(identity["manifest_identity_valid"])
        self.assertEqual(identity["source_manifest_identity"]["status"], "invalid")
        self.assertEqual(
            identity["source_manifest_identity"]["missing_values"],
            [{"path": str(missing_value_path.resolve()), "field": "name"}],
        )
        self.assertEqual(identity["source_manifest_identity"]["invalid_manifests"], [])

    def test_release_identity_rejects_matching_hashes_with_internal_manifest_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            self._write_manifest_identity(
                source,
                Path(".agents") / "plugins" / "kh-uaf" / "plugin.json",
                name="kh-uaf-drift",
            )
            shutil.copytree(source, cache)

            identity = _build_release_identity_report(source, cache)

        self.assertTrue(identity["content_hashes_match"])
        self.assertTrue(identity["catalogs_valid"])
        self.assertTrue(identity["catalog_names_match"])
        self.assertFalse(identity["manifest_identity_valid"])
        self.assertFalse(_release_identity_ok(identity))

    def test_release_identity_accepts_valid_consistent_manifest_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)

            identity = _build_release_identity_report(source, cache)

        expected_identity = {"name": "kh-uaf", "version": "2.9.130"}
        self.assertEqual(identity["status"], "ok")
        self.assertTrue(identity["manifest_identity_valid"])
        self.assertEqual(identity["source_manifest_identity"]["status"], "ok")
        self.assertEqual(identity["cache_manifest_identity"]["status"], "ok")
        self.assertEqual(identity["source_manifest_identity"]["identity"], expected_identity)
        self.assertEqual(identity["cache_manifest_identity"]["identity"], expected_identity)
        self.assertEqual(identity["source_cache_manifest_identity_mismatches"], [])
        self.assertTrue(_release_identity_ok(identity))

    def test_release_identity_rejects_consistent_noncanonical_manifest_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            for relative_path in (
                Path("plugin.json"),
                Path(".codex-plugin") / "plugin.json",
                Path(".agents") / "plugins" / "kh-uaf" / "plugin.json",
            ):
                self._write_manifest_identity(source, relative_path, name="kh-uaf-copy")
            shutil.copytree(source, cache)

            identity = _build_release_identity_report(source, cache)

        self.assertTrue(identity["content_hashes_match"])
        self.assertFalse(identity["manifest_identity_valid"])
        self.assertEqual(identity["source_manifest_identity"]["status"], "invalid")
        self.assertEqual(identity["cache_manifest_identity"]["status"], "invalid")
        for manifest_identity in (
            identity["source_manifest_identity"],
            identity["cache_manifest_identity"],
        ):
            self.assertEqual(
                {issue["reason"] for issue in manifest_identity["invalid_values"]},
                {"noncanonical_plugin_name"},
            )
            self.assertEqual(
                {issue["expected"] for issue in manifest_identity["invalid_values"]},
                {"kh-uaf"},
            )

    def test_release_identity_rejects_consistent_malformed_release_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            for relative_path in (
                Path("plugin.json"),
                Path(".codex-plugin") / "plugin.json",
                Path(".agents") / "plugins" / "kh-uaf" / "plugin.json",
            ):
                self._write_manifest_identity(source, relative_path, version="release-2.9.130")
            shutil.copytree(source, cache)

            identity = _build_release_identity_report(source, cache)

        self.assertTrue(identity["content_hashes_match"])
        self.assertFalse(identity["manifest_identity_valid"])
        self.assertEqual(identity["source_manifest_identity"]["status"], "invalid")
        self.assertEqual(identity["cache_manifest_identity"]["status"], "invalid")
        for manifest_identity in (
            identity["source_manifest_identity"],
            identity["cache_manifest_identity"],
        ):
            self.assertEqual(
                {issue["reason"] for issue in manifest_identity["invalid_values"]},
                {"invalid_release_version"},
            )
            self.assertEqual(
                {issue["expected_format"] for issue in manifest_identity["invalid_values"]},
                {"MAJOR.MINOR.PATCH"},
            )

    def test_release_identity_canonicalizes_allowed_markdown_eol_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            (source / "skills" / "release-identity-fixture" / "usage.md").write_bytes(
                b"# Usage\n\nFirst\nSecond\n"
            )
            shutil.copytree(source, cache)
            (cache / "skills" / "release-identity-fixture" / "usage.md").write_bytes(
                b"# Usage\r\n\r\nFirst\r\nSecond\r\n"
            )

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "ok")
        self.assertTrue(identity["content_hashes_match"])
        self.assertFalse(identity["raw_content_hashes_match"])

    def test_release_identity_rejects_semantic_utf8_text_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            (cache / "src" / "runtime.py").write_text(
                "FIRST = 1\nSECOND = 3\n",
                encoding="utf-8",
                newline="\n",
            )

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertFalse(identity["content_hashes_match"])
        self.assertFalse(identity["raw_content_hashes_match"])

    def test_release_identity_rejects_agent_manifest_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            agent_manifest = cache / ".agents" / "plugins" / "kh-uaf" / "plugin.json"
            agent_manifest.write_text(
                json.dumps({"name": "kh-uaf", "version": "2.9.130", "drift": True}),
                encoding="utf-8",
                newline="\n",
            )

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertFalse(identity["content_hashes_match"])
        self.assertFalse(identity["raw_content_hashes_match"])

    def test_release_identity_rejects_missing_source_manifest_with_path_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            missing_path = source / ".agents" / "plugins" / "kh-uaf" / "plugin.json"
            missing_path.unlink()

            identity = _build_release_identity_report(source, cache)
            message = _release_identity_message(identity)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertFalse(identity["required_release_manifests_present"])
        self.assertEqual(
            identity["source_missing_required_manifest_paths"],
            [str(missing_path.resolve())],
        )
        self.assertEqual(identity["cache_missing_required_manifest_paths"], [])
        self.assertIn(str(missing_path.resolve()), message)

    def test_release_identity_rejects_missing_cache_manifest_with_path_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            missing_path = cache / ".codex-plugin" / "plugin.json"
            missing_path.unlink()

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertFalse(identity["required_release_manifests_present"])
        self.assertEqual(identity["source_missing_required_manifest_paths"], [])
        self.assertEqual(
            identity["cache_missing_required_manifest_paths"],
            [str(missing_path.resolve())],
        )

    def test_release_identity_rejects_manifest_missing_from_both_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            relative_path = Path("plugin.json")
            source_missing_path = source / relative_path
            cache_missing_path = cache / relative_path
            source_missing_path.unlink()
            cache_missing_path.unlink()

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertTrue(identity["content_hashes_match"])
        self.assertTrue(identity["raw_content_hashes_match"])
        self.assertFalse(identity["required_release_manifests_present"])
        self.assertEqual(
            identity["missing_required_manifest_paths"],
            [str(source_missing_path.resolve()), str(cache_missing_path.resolve())],
        )

    def test_release_hash_length_prefix_blocks_delimiter_collision(self):
        def legacy_frame(entries: list[tuple[str, bytes]]) -> bytes:
            framed = bytearray()
            for path, content in entries:
                framed.extend(path.encode("utf-8"))
                framed.extend(b"\0")
                framed.extend(content)
                framed.extend(b"\0")
            return bytes(framed)

        one_file = [("src/a.bin", b"x\0src/b.bin\0y")]
        two_files = [("src/a.bin", b"x"), ("src/b.bin", b"y")]
        self.assertEqual(legacy_frame(one_file), legacy_frame(two_files))
        self.assertEqual(
            hashlib.sha256(legacy_frame(one_file)).digest(),
            hashlib.sha256(legacy_frame(two_files)).digest(),
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            one_file_root = root / "one-file"
            two_file_root = root / "two-files"
            self._write_release_fixture(one_file_root)
            self._write_release_fixture(two_file_root)
            (one_file_root / "src" / "a.bin").write_bytes(one_file[0][1])
            (two_file_root / "src" / "a.bin").write_bytes(two_files[0][1])
            (two_file_root / "src" / "b.bin").write_bytes(two_files[1][1])

            one_file_hashes = _release_content_hash_details(one_file_root)
            two_file_hashes = _release_content_hash_details(two_file_root)

        self.assertNotEqual(
            one_file_hashes["canonical_sha256"],
            two_file_hashes["canonical_sha256"],
        )
        self.assertNotEqual(one_file_hashes["raw_sha256"], two_file_hashes["raw_sha256"])
        self.assertNotEqual(one_file_hashes["file_count"], two_file_hashes["file_count"])
        self.assertEqual(
            CANONICAL_RELEASE_HASH_ALGORITHM,
            "sha256-length-prefixed-path-and-canonical-content-v3",
        )
        self.assertEqual(
            RAW_RELEASE_HASH_ALGORITHM,
            "sha256-length-prefixed-path-and-raw-content-v2",
        )

    def test_release_identity_rejects_binary_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            (source / "src" / "payload.bin").write_bytes(b"\x00\x01\r\n")
            shutil.copytree(source, cache)
            (cache / "src" / "payload.bin").write_bytes(b"\x00\x01\n")

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertFalse(identity["content_hashes_match"])
        self.assertFalse(identity["raw_content_hashes_match"])
        self.assertEqual(identity["source_binary_file_count"], 1)
        self.assertEqual(identity["cache_binary_file_count"], 1)

    def test_release_identity_rejects_printable_unknown_extension_eol_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            (source / "src" / "protocol.bin").write_bytes(b"FRAME 1\r\nFRAME 2\r\n")
            shutil.copytree(source, cache)
            (cache / "src" / "protocol.bin").write_bytes(b"FRAME 1\nFRAME 2\n")

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertFalse(identity["content_hashes_match"])
        self.assertFalse(identity["raw_content_hashes_match"])
        self.assertEqual(identity["source_binary_file_count"], 1)
        self.assertEqual(identity["cache_binary_file_count"], 1)

    def test_release_identity_keeps_non_utf8_content_byte_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            (source / "src" / "legacy.dat").write_bytes(b"\xff\r\n")
            shutil.copytree(source, cache)
            (cache / "src" / "legacy.dat").write_bytes(b"\xff\n")

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertFalse(identity["content_hashes_match"])
        self.assertEqual(identity["source_binary_file_count"], 1)
        self.assertEqual(identity["cache_binary_file_count"], 1)

    def test_release_identity_rejects_missing_or_extra_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            cache = root / "cache"
            self._write_release_fixture(source)
            shutil.copytree(source, cache)
            (source / "src" / "source-only.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
                newline="\n",
            )

            identity = _build_release_identity_report(source, cache)

        self.assertEqual(identity["status"], "content_mismatch")
        self.assertFalse(identity["content_hashes_match"])
        self.assertNotEqual(identity["source_file_count"], identity["cache_file_count"])

    def test_release_identity_hash_match_does_not_claim_authenticity(self):
        message = _release_identity_message(
            {
                "status": "ok",
                "content_hashes_match": True,
                "catalogs_valid": True,
                "catalog_names_match": True,
                "required_release_manifests_present": True,
                "manifest_identity_valid": True,
            }
        )

        self.assertIn("authenticity=unverified", message)
        self.assertNotIn("authenticity verified", message.lower())

    def test_release_identity_requires_explicit_manifest_presence_evidence(self):
        identity = {
            "status": "ok",
            "content_hashes_match": True,
            "catalogs_valid": True,
            "catalog_names_match": True,
        }

        self.assertFalse(_release_identity_ok(identity))

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
