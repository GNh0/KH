import json
import unittest
from pathlib import Path


class PluginPackagingTests(unittest.TestCase):
    def test_codex_plugin_manifest_exposes_repo_skills(self):
        manifest_path = Path(".codex-plugin") / "plugin.json"

        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "kh-uaf")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertTrue(Path("skills").is_dir())
        self.assertNotIn("apps", manifest)
        self.assertNotIn("mcpServers", manifest)

        interface = manifest["interface"]
        self.assertEqual(interface["displayName"], "KH UAF")
        self.assertIn("Skill", " ".join(interface["capabilities"]))
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
        self.assertEqual(entry["source"]["ref"], "main")
        self.assertEqual(entry["policy"]["installation"], "AVAILABLE")
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Productivity")

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
        self.assertIn("python -m src.skills.uaf_skill_catalog --check", content)
        self.assertIn("skills/", content)

    def test_root_manifest_can_act_as_antigravity_global_plugin_marker(self):
        manifest = json.loads(Path("plugin.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "kh-uaf")
        self.assertTrue(Path("skills").is_dir())
        self.assertTrue((Path("skills") / "goal_state_harness" / "SKILL.md").is_file())

    def test_readme_documents_codex_and_antigravity_install_paths(self):
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("README.ko.md", content)
        self.assertIn("## Codex Plugin Install", content)
        self.assertIn(".codex-plugin/plugin.json", content)
        self.assertIn(".agents/plugins/marketplace.json", content)
        self.assertIn("## Antigravity Plugin Install", content)
        self.assertIn("~/.gemini/config/plugins/kh-uaf", content)
        self.assertIn(".agents/plugins/kh-uaf", content)

    def test_korean_readme_links_back_to_english_readme(self):
        content = Path("README.ko.md").read_text(encoding="utf-8")

        self.assertIn("[English](README.md)", content)
        self.assertIn("## Codex 플러그인 설치", content)
        self.assertIn("## Antigravity 플러그인 설치", content)


if __name__ == "__main__":
    unittest.main()
