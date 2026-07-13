import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.orchestration.kh_front_door import build_kh_front_door
from src.skills.sql_formatting_provider import inspect_packaged_sql_formatting_provider


class SqlFormattingProviderTests(unittest.TestCase):
    def test_provider_inspection_blocks_missing_and_corrupt_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills_root = Path(tmp) / "skills"
            skills_root.mkdir()

            missing = inspect_packaged_sql_formatting_provider(skills_root)
            self.assertEqual(missing.status, "missing")
            self.assertFalse(missing.compatible)

            provider_root = skills_root / "sql_formatting"
            provider_root.mkdir()
            (provider_root / "SKILL.md").write_text("not frontmatter", encoding="utf-8")

            corrupt = inspect_packaged_sql_formatting_provider(skills_root)
            self.assertEqual(corrupt.status, "corrupt")
            self.assertFalse(corrupt.compatible)

    def test_front_door_prefers_compatible_host_local_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "sql-formatting"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: sql-formatting\n"
                "description: Use when formatting, cleaning, standardizing, or refactoring SQL/T-SQL.\n"
                "---\n"
                "# SQL Formatting\n",
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                payload = build_kh_front_door(
                    "Format this T-SQL query and preserve logic.",
                    project=Path.cwd(),
                    host="codex",
                ).to_dict()

        controller = payload["plugin_route"]["controller"]
        self.assertEqual(controller["provider_id"], "sql-formatting")
        self.assertEqual(controller["metadata"]["source"], "host-local-skill")
        self.assertEqual(controller["metadata"]["availability"], "available")
        self.assertEqual(controller["metadata"]["compatibility"], "compatible")
        self.assertEqual(
            payload["immediate_next_skills"],
            ["sql-formatting", "sql-formatting-style-harness"],
        )

    def test_front_door_uses_packaged_provider_then_verifier_when_codex_home_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                payload = build_kh_front_door(
                    "Format this T-SQL query and preserve logic.",
                    project=Path.cwd(),
                    host="codex",
                ).to_dict()

        controller = payload["plugin_route"]["controller"]
        self.assertEqual(controller["provider_id"], "sql-formatting")
        self.assertEqual(controller["metadata"]["source"], "packaged-kh-skill")
        self.assertEqual(controller["metadata"]["availability"], "available")
        self.assertEqual(controller["metadata"]["compatibility"], "compatible")
        self.assertEqual(
            payload["immediate_next_skills"],
            ["sql-formatting", "sql-formatting-style-harness"],
        )
        self.assertIn("sql-formatting", payload["recommended_skills"])
        self.assertIn("sql-formatting-style-harness", payload["recommended_skills"])

    def test_front_door_falls_back_from_divergent_host_local_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "sql-formatting"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: sql-formatting\n"
                "description: Use when formatting SQL and may change query behavior.\n"
                "---\n"
                "# Divergent SQL Formatting\n",
                encoding="utf-8",
            )

            with patch.dict("os.environ", {"CODEX_HOME": tmp}):
                payload = build_kh_front_door(
                    "Format this T-SQL query and preserve logic.",
                    project=Path.cwd(),
                    host="codex",
                ).to_dict()

        controller = payload["plugin_route"]["controller"]
        self.assertEqual(controller["provider_id"], "sql-formatting")
        self.assertEqual(controller["metadata"]["source"], "packaged-kh-skill")
        self.assertEqual(
            payload["immediate_next_skills"],
            ["sql-formatting", "sql-formatting-style-harness"],
        )
        evidence = {
            item["source"]: item
            for item in payload["plugin_route"]["provider_evidence"]
            if item["provider_id"] == "sql-formatting"
        }
        self.assertTrue(evidence["host-local-skill"]["available"])
        self.assertFalse(evidence["host-local-skill"]["compatible"])
        self.assertEqual(evidence["host-local-skill"]["compatibility"], "divergent")
        self.assertFalse(evidence["host-local-skill"]["selected"])
        self.assertTrue(evidence["packaged-kh-skill"]["available"])
        self.assertTrue(evidence["packaged-kh-skill"]["compatible"])
        self.assertTrue(evidence["packaged-kh-skill"]["selected"])

    def test_front_door_blocks_when_no_compatible_provider_exists(self):
        unavailable_provider = {
            "provider_id": "sql-formatting",
            "display_name": "KH Packaged SQL Formatting",
            "aliases": ["sql formatting", "sql-formatting"],
            "capabilities": ["sql_formatting"],
            "status": "corrupt",
            "metadata": {
                "source": "packaged-kh-skill",
                "compatibility": "corrupt",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"CODEX_HOME": tmp}), patch(
                "src.orchestration.kh_front_door.packaged_sql_formatting_provider",
                return_value=unavailable_provider,
            ):
                payload = build_kh_front_door(
                    "Format this T-SQL query and preserve logic.",
                    project=Path.cwd(),
                    host="codex",
                ).to_dict()

        selected_roles = [payload["plugin_route"]["controller"], *payload["plugin_route"]["assistants"]]
        self.assertFalse(any(role.get("capability") == "sql_formatting" for role in selected_roles))
        self.assertEqual(payload["plugin_route"]["route"], "blocked")
        self.assertEqual(payload["execution_gate"]["status"], "blocked_until_sql_formatting_provider")
        self.assertFalse(payload["execution_gate"]["can_execute"])
        self.assertIn("sql_formatting", payload["plugin_route"]["unavailable_capabilities"])
        self.assertFalse(
            any("Apply selected provider `sql-formatting`" in action for action in payload["required_next_actions"])
        )


if __name__ == "__main__":
    unittest.main()
