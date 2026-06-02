import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path("scripts") / "install_codex_global_bootstrap.py"


def load_module():
    spec = importlib.util.spec_from_file_location("install_codex_global_bootstrap", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CodexGlobalBootstrapTests(unittest.TestCase):
    def test_rendered_skill_is_trigger_focused_and_delegates_to_front_door(self):
        module = load_module()
        content = module.render_skill()

        self.assertIn("description: Use when any non-trivial Codex request", content)
        self.assertIn("read this skill alone", content)
        self.assertIn("next standalone tool call", content)
        self.assertIn("front_door.py", content)
        self.assertIn("selected_not_executed_skills", content)
        self.assertIn("stop for user approval", content)
        self.assertIn("Do not parallelize this SKILL.md read", content)
        self.assertIn("Do not read `MEMORY.md` before front-door", content)
        self.assertIn("Do not inspect the target folder or sibling folders before front-door", content)

    def test_install_writes_global_skill_when_cache_wrapper_exists(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp)
            wrapper = (
                codex_home
                / "plugins"
                / "cache"
                / "kh-uaf-marketplace"
                / "kh-uaf"
                / "2.9.38"
                / "skills"
                / "always_on_front_door"
                / "scripts"
                / "front_door.py"
            )
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("# wrapper\n", encoding="utf-8")

            target = module.install(codex_home)
            self.assertEqual(target, codex_home / "skills" / "kh-uaf-front-door" / "SKILL.md")
            self.assertTrue(target.is_file())

            status = module.check(codex_home)
            self.assertTrue(status["installed"])
            self.assertTrue(status["has_front_door_text"])
            self.assertTrue(status["has_brainstorming_stop"])
            self.assertTrue(str(status["latest_cache"]).endswith("2.9.38"))

    def test_install_blocks_when_plugin_cache_is_missing(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                module.install(Path(tmp))


if __name__ == "__main__":
    unittest.main()
