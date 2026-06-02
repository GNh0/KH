import json
import unittest
from pathlib import Path


def _u(value: str) -> str:
    return value


class PluginPackagingTests(unittest.TestCase):
    def test_codex_plugin_manifest_exposes_repo_skills(self):
        manifest_path = Path(".codex-plugin") / "plugin.json"

        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        root_manifest = json.loads(Path("plugin.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "kh-uaf")
        self.assertEqual(manifest["version"], root_manifest["version"])
        self.assertGreaterEqual(tuple(map(int, manifest["version"].split("."))), (2, 9, 10))
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertTrue(Path("skills").is_dir())
        self.assertNotIn("apps", manifest)
        self.assertNotIn("mcpServers", manifest)

        interface = manifest["interface"]
        self.assertEqual(interface["displayName"], "KH UAF")
        self.assertIn("Skill", " ".join(interface["capabilities"]))
        self.assertIn("KH-Bench Verified", " ".join(interface["capabilities"]))
        self.assertIn("https://github.com/GNh0/KH", manifest["repository"])

    def test_repo_marketplace_exposes_git_backed_plugin(self):
        marketplace_path = Path(".agents") / "plugins" / "marketplace.json"

        self.assertTrue(marketplace_path.is_file())
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

        self.assertEqual(marketplace["name"], "kh-uaf-marketplace")
        self.assertEqual(marketplace["interface"]["displayName"], "KH UAF")
        self.assertEqual(len(marketplace["plugins"]), 1)

        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], "kh-uaf")
        self.assertEqual(entry["source"]["source"], "url")
        self.assertEqual(entry["source"]["url"], "https://github.com/GNh0/KH.git")
        self.assertEqual(entry["source"]["ref"], "codex-runtime")
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Productivity")

    def test_root_does_not_ship_legacy_sample_project_folders(self):
        self.assertFalse(Path("test_cli_project").exists())
        self.assertFalse(Path("test_project").exists())

        ignore_content = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn("test_cli_project/", ignore_content)
        self.assertIn("test_project/", ignore_content)

    def test_runtime_archive_marks_development_only_paths_export_ignored(self):
        attributes = Path(".gitattributes").read_text(encoding="utf-8")

        self.assertIn("tests/ export-ignore", attributes)
        self.assertIn("docs/ export-ignore", attributes)
        self.assertIn("test_cli_project/ export-ignore", attributes)
        self.assertIn("test_project/ export-ignore", attributes)

    def test_antigravity_workspace_plugin_wrapper_is_available(self):
        plugin_root = Path(".agents") / "plugins" / "kh-uaf"
        manifest_path = plugin_root / "plugin.json"
        skill_path = plugin_root / "skills" / "kh-uaf" / "SKILL.md"

        self.assertTrue(manifest_path.is_file())
        self.assertTrue(skill_path.is_file())

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "kh-uaf")

        content = skill_path.read_text(encoding="utf-8")
        self.assertIn("name: kh-uaf", content)
        self.assertIn("front-door auto routing", content)
        self.assertIn("Users should not need to name every harness", content)
        self.assertIn("src.orchestration.kh_front_door", content)
        self.assertIn("python -m src.skills.uaf_skill_catalog --check", content)
        self.assertIn("skills/", content)

    def test_root_manifest_can_act_as_antigravity_global_plugin_marker(self):
        manifest = json.loads(Path("plugin.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "kh-uaf")
        self.assertTrue(Path("skills").is_dir())
        self.assertTrue((Path("skills") / "goal_state_harness" / "SKILL.md").is_file())
        skill_names = {skill["name"] for skill in manifest["skills"]}
        self.assertIn("kh-front-door", skill_names)

    def test_readme_documents_codex_and_antigravity_install_paths(self):
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("README.ko.md", content)
        self.assertIn("## Codex Plugin Install", content)
        self.assertIn(".codex-plugin/plugin.json", content)
        self.assertIn(".agents/plugins/marketplace.json", content)
        self.assertIn("codex-runtime", content)
        self.assertIn("slim plugin runtime branch", content)
        self.assertIn("## Antigravity Plugin Install", content)
        self.assertIn("~/.gemini/config/plugins/kh-uaf", content)
        self.assertIn(".agents/plugins/kh-uaf", content)
        self.assertIn("Upgrade note", content)
        self.assertIn("Codex subagent note", content)
        self.assertIn("install_codex_global_bootstrap.py", content)
        self.assertIn("kh-uaf-front-door", content)
        self.assertIn(".codex-plugin/plugin.json", content)
        self.assertIn("root `plugin.json`", content)
        self.assertIn("Offline output is smoke-only", content)
        self.assertIn("src.orchestration.kh_front_door", content)

    def test_korean_readme_links_back_to_english_readme(self):
        content = Path("README.ko.md").read_text(encoding="utf-8")

        self.assertIn("[English](README.md)", content)
        self.assertIn(_u("## Codex \ud50c\ub7ec\uadf8\uc778 \uc124\uce58"), content)
        self.assertIn(_u("## Antigravity \ud50c\ub7ec\uadf8\uc778 \uc124\uce58"), content)
        self.assertIn(_u("\uc5c5\uadf8\ub808\uc774\ub4dc \ucc38\uace0"), content)
        self.assertIn(_u("\ubc84\uc804 bump"), content)
        self.assertIn("install_codex_global_bootstrap.py", content)
        self.assertIn("kh-uaf-front-door", content)
        self.assertIn("codex-runtime", content)
        self.assertIn("smoke-only", content)

    def test_korean_readme_is_not_mojibake(self):
        content = Path("README.ko.md").read_text(encoding="utf-8")

        for expected in [
            _u("KH UAF\ub294"),
            _u("\ud3ec\ud568 \ud56d\ubaa9"),
            _u("\ube60\ub978 \uc2dc\uc791"),
            _u("\uae30\ubcf8 \ud750\ub984"),
            _u("\uc0b0\ucd9c\ubb3c"),
            _u("\uac80\uc99d"),
        ]:
            self.assertIn(expected, content)

        mojibake_fragments = [
            "\ufffd",
            "?" + "\ub6ae",
            "?" + "\u317c",
            "?" + "\uacf3",
            "?" + "\uc12e",
            "\u6028" + "\uafbe",
            "\u6fe1" + "\uc492",
            "\uf9cd" + "\u317b",
            "\uc720" + "?",
            "\u5a9b" + "\uc492",
        ]
        for fragment in mojibake_fragments:
            self.assertNotIn(fragment, content)

    def test_all_packaged_skills_share_kh_entry_contract(self):
        skill_files = sorted(Path("skills").glob("*/SKILL.md"))

        self.assertGreaterEqual(len(skill_files), 40)
        for path in skill_files:
            with self.subTest(path=str(path)):
                content = path.read_text(encoding="utf-8")
                self.assertIn("## KH Entry Contract", content)
                self.assertIn("always-on-front-door", content)
                self.assertIn("kh_active_directive=active", content)
                self.assertIn("selected_not_executed_skills", content)
                self.assertIn("is not execution evidence", content)


if __name__ == "__main__":
    unittest.main()
