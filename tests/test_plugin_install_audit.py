import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from src.orchestration.plugin_install_audit import audit_kh_plugin_install, main


class PluginInstallAuditTests(unittest.TestCase):
    def _repo(
        self,
        root: Path,
        version: str = "2.9.99",
        *,
        source_url: str = "https://github.com/GNh0/KH.git",
        source_ref: str = "codex-runtime",
    ) -> Path:
        repo = root / "repo"
        (repo / ".agents" / "plugins" / "kh-uaf").mkdir(parents=True)
        (repo / ".codex-plugin").mkdir(parents=True)
        manifest = json.dumps({"name": "kh-uaf", "version": version})
        (repo / "plugin.json").write_text(manifest, encoding="utf-8")
        (repo / ".codex-plugin" / "plugin.json").write_text(manifest, encoding="utf-8")
        (repo / ".agents" / "plugins" / "kh-uaf" / "plugin.json").write_text(
            manifest,
            encoding="utf-8",
        )
        (repo / ".agents" / "plugins" / "marketplace.json").write_text(
            json.dumps(
                {
                    "plugins": [
                        {
                            "name": "kh-uaf",
                            "source": {"url": source_url, "ref": source_ref},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return repo

    def _configure_codex(
        self,
        root: Path,
        *,
        source_url: str = "https://github.com/GNh0/KH.git",
        ref: str = "main",
        sparse_paths: tuple[str, ...] = (".agents/plugins",),
    ) -> Path:
        codex = root / "codex"
        codex.mkdir()
        sparse_paths_toml = ", ".join(repr(path) for path in sparse_paths)
        (codex / "config.toml").write_text(
            "[marketplaces.kh-uaf-marketplace]\n"
            f"source = '{source_url}'\n"
            f"ref = '{ref}'\n"
            f"sparse_paths = [{sparse_paths_toml}]\n"
            "last_revision = 'abc'\n",
            encoding="utf-8",
        )
        return codex

    def _write_skill(self, release_root: Path, index: int) -> None:
        name = f"audit-skill-{index:02d}"
        skill_dir = release_root / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            f"name: {name}\n"
            "description: Use when install audit tests need a packaged release fixture.\n"
            "---\n\n"
            f"# {name}\n\n"
            "## KH Entry Contract\n\nApplied by the install audit fixture.\n\n"
            "## Workflow\n\n1. Validate release identity.\n\n"
            "## Required outputs\n\n- Identity evidence.\n\n"
            "## Common mistakes\n\n- Do not skip content comparison.\n\n"
            "## UAF implementation targets\n\n- `tests.test_plugin_install_audit`\n",
            encoding="utf-8",
        )

    def _install_cache(self, codex: Path, repo: Path, version: str = "2.9.99") -> Path:
        cache = codex / "plugins" / "cache" / "kh-uaf-marketplace" / "kh-uaf" / version
        cache.parent.mkdir(parents=True)
        shutil.copytree(repo, cache)
        return cache

    def test_invalid_config_toml_is_attention_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex"
            codex.mkdir()
            (codex / "config.toml").write_text("[marketplaces.kh-uaf-marketplace\nref = 'main'\n", encoding="utf-8")
            repo = self._repo(root)

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "attention_required")
        self.assertEqual(audit.marketplace_config.parse_status, "invalid")
        self.assertTrue(any("not valid TOML" in finding for finding in audit.findings))

    def test_config_replacement_character_is_attention_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex"
            codex.mkdir()
            damaged = chr(0xFFFD)
            (codex / "config.toml").write_text(
                "[marketplaces.kh-uaf-marketplace]\n"
                "source = 'https://github.com/GNh0/KH.git'\n"
                "ref = 'main'\n"
                f"last_revision = 'abc{damaged}'\n",
                encoding="utf-8",
            )
            repo = self._repo(root)

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "attention_required")
        self.assertIn("unicode_replacement_character", audit.marketplace_config.encoding_warnings)
        self.assertTrue(any("encoding damage" in finding for finding in audit.findings))

    def test_main_marketplace_ref_with_codex_runtime_plugin_source_is_not_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = root / "codex"
            codex.mkdir()
            (codex / "config.toml").write_text(
                "[marketplaces.kh-uaf-marketplace]\nsource = 'https://github.com/GNh0/KH.git'\nref = 'main'\nsparse_paths = ['.agents/plugins']\nlast_revision = 'abc'\n",
                encoding="utf-8",
            )
            repo = self._repo(root)

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.marketplace_config.parse_status, "ok")
        self.assertEqual(audit.marketplace_config.ref, "main")
        self.assertEqual(audit.marketplace_plugin_source.source_ref, "codex-runtime")
        self.assertFalse(any("descriptor layer" in finding for finding in audit.findings))
        self.assertTrue(any("descriptor layer" in note for note in audit.notes))

    def test_marketplace_ref_must_track_main_wrapper_not_codex_runtime_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = self._configure_codex(root, ref="codex-runtime")
            repo = self._repo(root)
            self._write_skill(repo, 1)
            self._install_cache(codex, repo)

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "attention_required")
        self.assertTrue(
            any(
                "supported marketplace wrapper ref is main" in finding.lower()
                and "direct codex-runtime marketplace installs are not supported"
                in finding.lower()
                for finding in audit.findings
            )
        )

    def test_plugin_source_ref_topology_finding_is_attention_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = self._configure_codex(root)
            repo = self._repo(root, source_ref="main")
            self._write_skill(repo, 1)
            self._install_cache(codex, repo)

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "attention_required")
        self.assertTrue(any("expected codex-runtime" in finding for finding in audit.findings))

    def test_marketplace_and_plugin_sources_must_identify_the_same_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = self._configure_codex(
                root,
                source_url="https://git.example.test/team/kh-wrapper.git",
            )
            repo = self._repo(
                root,
                source_url="https://mirror.example.test/team/kh-runtime.git",
            )
            self._write_skill(repo, 1)
            self._install_cache(codex, repo)

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "attention_required")
        self.assertTrue(any("repository sources differ" in finding for finding in audit.findings))

    def test_supported_topology_accepts_any_consistent_repository_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_url = "https://git.example.test/team/kh.git"
            codex = self._configure_codex(root, source_url=source_url)
            repo = self._repo(root, source_url=source_url.removesuffix(".git") + "/")
            self._write_skill(repo, 1)
            self._install_cache(codex, repo)

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "ok")
        self.assertFalse(audit.findings)
        self.assertTrue(any("descriptor layer" in note for note in audit.notes))

    def test_strict_cli_fails_when_plugin_source_ref_topology_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = self._configure_codex(root)
            repo = self._repo(root, source_ref="main")
            self._write_skill(repo, 1)
            self._install_cache(codex, repo)
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--codex-home",
                        str(codex),
                        "--repo",
                        str(repo),
                        "--summary",
                        "--strict",
                    ]
                )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["status"], "attention_required")
        self.assertTrue(any("expected codex-runtime" in finding for finding in payload["findings"]))

    def test_same_version_with_divergent_entrypoint_content_is_attention_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = self._configure_codex(root)
            repo = self._repo(root)
            self._write_skill(repo, 1)
            (repo / "plugin.json").write_text(
                json.dumps(
                    {"name": "kh-uaf", "version": "2.9.99", "entrypoint": "cli.py"}
                ),
                encoding="utf-8",
            )
            (repo / "cli.py").write_text("print('source')\n", encoding="utf-8")
            cache = self._install_cache(codex, repo)
            (cache / "cli.py").write_text("print('cache')\n", encoding="utf-8")

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.latest_installed_version, audit.expected_source_version)
        self.assertEqual(audit.status, "attention_required")
        self.assertFalse(audit.release_identity["content_hashes_match"])
        self.assertTrue(audit.release_identity["catalog_names_match"])

    def test_matching_release_content_and_catalog_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = self._configure_codex(root)
            repo = self._repo(root)
            self._write_skill(repo, 1)
            (repo / "plugin.json").write_text(
                json.dumps(
                    {"name": "kh-uaf", "version": "2.9.99", "entrypoint": "cli.py"}
                ),
                encoding="utf-8",
            )
            (repo / "cli.py").write_text("print('same')\n", encoding="utf-8")
            self._install_cache(codex, repo)

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "ok")
        self.assertEqual(audit.release_identity["status"], "ok")
        self.assertTrue(audit.release_identity["content_hashes_match"])
        self.assertTrue(audit.release_identity["catalog_names_match"])
        self.assertTrue(audit.release_identity["manifest_identity_valid"])

    def test_matching_content_with_internal_manifest_name_mismatch_is_attention_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = self._configure_codex(root)
            repo = self._repo(root)
            self._write_skill(repo, 1)
            (repo / ".agents" / "plugins" / "kh-uaf" / "plugin.json").write_text(
                json.dumps({"name": "kh-uaf-drift", "version": "2.9.99"}),
                encoding="utf-8",
            )
            self._install_cache(codex, repo)

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "attention_required")
        self.assertTrue(audit.release_identity["content_hashes_match"])
        self.assertTrue(audit.release_identity["catalog_names_match"])
        self.assertFalse(audit.release_identity["manifest_identity_valid"])
        self.assertEqual(
            audit.release_identity["source_manifest_identity"]["status"],
            "mismatch",
        )
        self.assertEqual(
            audit.release_identity["cache_manifest_identity"]["status"],
            "mismatch",
        )

    def test_matching_content_without_agent_release_manifest_is_attention_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = self._configure_codex(root)
            repo = self._repo(root)
            self._write_skill(repo, 1)
            missing_manifest = repo / ".agents" / "plugins" / "kh-uaf" / "plugin.json"
            missing_manifest.unlink()
            cache = self._install_cache(codex, repo)
            cache_missing_manifest = cache / ".agents" / "plugins" / "kh-uaf" / "plugin.json"

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "attention_required")
        self.assertTrue(audit.release_identity["content_hashes_match"])
        self.assertFalse(audit.release_identity["required_release_manifests_present"])
        self.assertEqual(
            audit.release_identity["source_missing_required_manifest_paths"],
            [str(missing_manifest.resolve())],
        )
        self.assertEqual(
            audit.release_identity["cache_missing_required_manifest_paths"],
            [str(cache_missing_manifest.resolve())],
        )

    def test_pre_upgrade_source_44_vs_cache_43_is_reported_truthfully(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = self._configure_codex(root)
            repo = self._repo(root)
            for index in range(1, 45):
                self._write_skill(repo, index)
            cache = self._install_cache(codex, repo)
            shutil.rmtree(cache / "skills" / "audit-skill-44")

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "attention_required")
        self.assertEqual(audit.release_identity["source_skill_count"], 44)
        self.assertEqual(audit.release_identity["cache_skill_count"], 43)
        self.assertFalse(audit.release_identity["catalog_names_match"])
        self.assertTrue(any("source skills 44, cache skills 43" in finding for finding in audit.findings))


if __name__ == "__main__":
    unittest.main()
