import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.orchestration.kh_front_door import build_kh_front_door
from src.skills.sql_formatting_provider import (
    inspect_host_sql_formatting_provider,
    inspect_packaged_sql_formatting_provider,
)


class SqlFormattingProviderTests(unittest.TestCase):
    COMPATIBLE_HOST_SKILL = """---
name: sql-formatting
description: Format SQL/T-SQL while preserving query behavior and semantics.
---

# SQL Formatting

Do not change query behavior. Preserve table names, predicates, expressions, and results.
Convert a scalar lookup to a JOIN only when its implementation and relational equivalence are verified.
Run the packaged `sql-formatting-style-harness` deterministic verifier and accept output only when it passes.

## Examples

For example, `DBO.F_SAMPLE_NAME(...)` and `SAMPLE_LOOKUP_TABLE` may illustrate input shape only.
They are not general conversion mandates.
"""

    CURRENT_HOST_LOCAL_SHAPE = """---
name: sql-formatting
description: Preserve SQL logic and allow verified lookup scalar-function-to-join conversions.
---

# SQL Formatting

Do not change query behavior.
Unknown scalar functions must stay scalar functions unless their contract proves an equivalent lookup join.

## BA011T Name Lookup

`DBO.F_BA011T_FIND_SUBNM(MAINCD, SUBCD, USEYN)` has a verified lookup contract in this skill.
When SQL contains this function, replace it with a `LEFT OUTER JOIN BA011T` lookup.
Join `BA011T` with `MAINCD`, `SUBCD`, and `USEYN`, then select `SUBNM`.
"""

    def write_host_skill(self, root, content):
        skill_path = Path(root) / "skills" / "sql-formatting" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text(content, encoding="utf-8")
        return skill_path

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
            self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)

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
            self.write_host_skill(
                tmp,
                self.COMPATIBLE_HOST_SKILL.replace(
                    "Format SQL/T-SQL while preserving query behavior and semantics.",
                    "Format SQL/T-SQL and may change query behavior.",
                ),
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
        self.assertEqual(
            controller["metadata"]["verification_provider"],
            "sql-formatting-style-harness",
        )
        self.assertEqual(
            controller["metadata"]["alias_plan_requirement"],
            "complete_per_changed_scope_when_aliases_change",
        )

    def test_host_provider_rejects_current_host_local_concrete_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_path = self.write_host_skill(tmp, self.CURRENT_HOST_LOCAL_SHAPE)

            inspection = inspect_host_sql_formatting_provider(skill_path)

        self.assertFalse(inspection.compatible)
        self.assertEqual(inspection.compatibility, "divergent")
        self.assertIn("concrete_schema_object_mandate", inspection.issues)
        self.assertIn("missing_packaged_verifier_requirement", inspection.issues)

    def test_host_provider_rejects_concrete_mandates_without_known_object_names(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "Convert a scalar lookup to a JOIN only when its implementation and relational equivalence are verified.",
            (
                "`CORP.F_ZZ901_NAME(CODE)` is the standard lookup. "
                "Always replace it with `LEFT OUTER JOIN ZZ901T` and return `ZZ901T.NAME`."
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("concrete_schema_object_mandate", inspection.issues)

    def test_host_provider_rejects_concrete_table_mandate_without_function(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "Convert a scalar lookup to a JOIN only when its implementation and relational equivalence are verified.",
            "Always use `ACME_CODE_MAP` to resolve code names.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("concrete_schema_object_mandate", inspection.issues)

    def test_host_provider_rejects_unlabeled_fenced_concrete_template(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "## Examples\n\nFor example, `DBO.F_SAMPLE_NAME(...)` and `SAMPLE_LOOKUP_TABLE` may illustrate input shape only.\nThey are not general conversion mandates.\n",
            "## Output Template\n\n```sql\nSELECT A.NAME\nFROM ZZ902T A\n```\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("concrete_schema_object_mandate", inspection.issues)

    def test_host_provider_rejects_unbounded_scalar_to_join_conversion(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "Convert a scalar lookup to a JOIN only when its implementation and relational equivalence are verified.",
            "Replace scalar UDF calls with LEFT JOINs for performance.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("unbounded_scalar_to_join_conversion", inspection.issues)

    def test_host_provider_rejects_missing_packaged_verifier_requirement(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "Run the packaged `sql-formatting-style-harness` deterministic verifier and accept output only when it passes.\n",
            "",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("missing_packaged_verifier_requirement", inspection.issues)

    def test_host_provider_rejects_missing_behavior_preservation_boundary(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "description: Format SQL/T-SQL while preserving query behavior and semantics.",
            "description: Format SQL/T-SQL for readability.",
        ).replace(
            "Do not change query behavior. Preserve table names, predicates, expressions, and results.",
            "Keep table names, predicates, and expressions readable.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("missing_behavior_preservation_boundary", inspection.issues)

    def test_host_provider_rejects_optional_or_negated_preservation_policies(self):
        policies = {
            "optional": "The formatter may preserve query behavior when convenient.",
            "negated": "The formatter must not preserve query behavior.",
        }
        for label, policy in policies.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                content = self.COMPATIBLE_HOST_SKILL.replace(
                    "description: Format SQL/T-SQL while preserving query behavior and semantics.",
                    "description: Format SQL/T-SQL for readability.",
                ).replace(
                    "Do not change query behavior. Preserve table names, predicates, expressions, and results.",
                    policy,
                )
                inspection = inspect_host_sql_formatting_provider(
                    self.write_host_skill(tmp, content)
                )

            self.assertFalse(inspection.compatible)
            self.assertIn("missing_behavior_preservation_boundary", inspection.issues)

    def test_host_provider_rejects_optional_or_negated_verifier_policies(self):
        policies = {
            "optional": (
                "The packaged `sql-formatting-style-harness` deterministic verifier "
                "may run when convenient."
            ),
            "negated": (
                "The packaged `sql-formatting-style-harness` deterministic verifier "
                "must not run before output is accepted."
            ),
            "prohibited": (
                "Do not invoke the packaged `sql-formatting-style-harness` "
                "deterministic verifier."
            ),
        }
        for label, policy in policies.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                content = self.COMPATIBLE_HOST_SKILL.replace(
                    "Run the packaged `sql-formatting-style-harness` deterministic verifier and accept output only when it passes.",
                    policy,
                )
                inspection = inspect_host_sql_formatting_provider(
                    self.write_host_skill(tmp, content)
                )

            self.assertFalse(inspection.compatible)
            self.assertIn("missing_packaged_verifier_requirement", inspection.issues)

    def test_host_provider_rejects_required_and_weak_preservation_clauses(self):
        content = (
            self.COMPATIBLE_HOST_SKILL
            + "\n## Weak Preservation Override\n\n"
            + "The formatter should preserve query behavior where practical.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertEqual(inspection.compatibility, "divergent")
        self.assertIn("contradictory_behavior_preservation_policy", inspection.issues)

    def test_host_provider_rejects_required_and_weak_verifier_clauses(self):
        content = (
            self.COMPATIBLE_HOST_SKILL
            + "\n## Weak Verifier Override\n\n"
            + "The packaged `sql-formatting-style-harness` deterministic verifier "
            + "should run where practical.\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertEqual(inspection.compatibility, "divergent")
        self.assertIn("contradictory_packaged_verifier_policy", inspection.issues)

    def test_host_provider_rejects_overt_behavior_change_permission(self):
        content = self.COMPATIBLE_HOST_SKILL.replace(
            "Do not change query behavior.",
            "Query behavior changes are allowed when the output is faster.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, content)
            )

        self.assertFalse(inspection.compatible)
        self.assertIn("behavior_change_allowed", inspection.issues)

    def test_host_provider_allows_labeled_examples_and_generic_verified_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            inspection = inspect_host_sql_formatting_provider(
                self.write_host_skill(tmp, self.COMPATIBLE_HOST_SKILL)
            )

        self.assertTrue(inspection.compatible)
        self.assertEqual(inspection.compatibility, "compatible")
        self.assertEqual(inspection.issues, [])

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
