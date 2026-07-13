import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.orchestration.plugin_install_audit import audit_kh_plugin_install


class PluginInstallAuditTests(unittest.TestCase):
    def _repo(self, root: Path, version: str = "2.9.99") -> Path:
        repo = root / "repo"
        (repo / ".agents" / "plugins").mkdir(parents=True)
        (repo / ".codex-plugin").mkdir(parents=True)
        (repo / "plugin.json").write_text(json.dumps({"version": version}), encoding="utf-8")
        (repo / ".codex-plugin" / "plugin.json").write_text(json.dumps({"version": version}), encoding="utf-8")
        (repo / ".agents" / "plugins" / "marketplace.json").write_text(
            json.dumps(
                {
                    "plugins": [
                        {
                            "name": "kh-uaf",
                            "source": {"url": "https://github.com/GNh0/KH.git", "ref": "codex-runtime"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return repo

    def _configure_codex(self, root: Path) -> Path:
        codex = root / "codex"
        codex.mkdir()
        (codex / "config.toml").write_text(
            "[marketplaces.kh-uaf-marketplace]\n"
            "source = 'https://github.com/GNh0/KH.git'\n"
            "ref = 'main'\n"
            "sparse_paths = ['.agents/plugins']\n"
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

    def test_same_version_with_divergent_entrypoint_content_is_attention_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex = self._configure_codex(root)
            repo = self._repo(root)
            self._write_skill(repo, 1)
            (repo / "plugin.json").write_text(
                json.dumps({"version": "2.9.99", "entrypoint": "cli.py"}),
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
                json.dumps({"version": "2.9.99", "entrypoint": "cli.py"}),
                encoding="utf-8",
            )
            (repo / "cli.py").write_text("print('same')\n", encoding="utf-8")
            self._install_cache(codex, repo)

            audit = audit_kh_plugin_install(codex_home=codex, repository_root=repo)

        self.assertEqual(audit.status, "ok")
        self.assertEqual(audit.release_identity["status"], "ok")
        self.assertTrue(audit.release_identity["content_hashes_match"])
        self.assertTrue(audit.release_identity["catalog_names_match"])

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
