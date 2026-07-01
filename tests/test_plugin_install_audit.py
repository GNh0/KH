import json
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


if __name__ == "__main__":
    unittest.main()
