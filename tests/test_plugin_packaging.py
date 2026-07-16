import json
import re
import tempfile
import unittest
from pathlib import Path

from skills.pb_to_csharp_migration_harness.scripts.smoke_check import (
    REQUIRED_SUPPORT_FILES,
    SHIPPED_RUNTIME_SOURCE_FILES,
    collect_privacy_scan_paths,
    scan_private_runtime_fingerprints,
)
from src.skills.uaf_skill_catalog import collect_packaged_skills


def _u(value: str) -> str:
    return value


def _version_base(value: str) -> str:
    return value.split("+", 1)[0]


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(map(int, _version_base(value).split(".")))


def _manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _skill_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 4 or lines[0] != "---":
        return {}
    try:
        frontmatter_end = lines.index("---", 1)
    except ValueError:
        return {}

    frontmatter = {}
    for line in lines[1:frontmatter_end]:
        key, separator, value = line.partition(":")
        if separator:
            frontmatter[key.strip()] = value.strip()
    return frontmatter


def _packaged_skill_frontmatter(root: Path = Path(".")) -> dict[str, Path]:
    packaged = {}
    for path in sorted((root / "skills").glob("*/SKILL.md")):
        metadata = _skill_frontmatter(path)
        name = metadata.get("name", "")
        if name:
            packaged[name] = path
    return packaged


def _static_runtime_exposure_gaps(root: Path = Path(".")) -> set[str]:
    packaged_names = set(_packaged_skill_frontmatter(root))
    explicit_runtime_names = {
        skill["name"] for skill in _manifest(root / "plugin.json")["skills"]
    }
    return packaged_names - explicit_runtime_names


class PluginPackagingTests(unittest.TestCase):
    def test_packaged_catalog_is_valid_and_sql_examples_are_generic(self):
        catalog = collect_packaged_skills()
        sql_skill_root = Path("skills") / "sql_formatting_style_harness"
        sql_docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sql_skill_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".md", ".py"}
        )

        self.assertTrue(catalog["validation"]["success"], catalog["validation"]["issues"])
        self.assertEqual(catalog["total_skills_found"], 44)
        self.assertNotIn("BA011T", sql_docs)
        self.assertNotIn("F_BA011T", sql_docs)

    def test_pb_migration_package_uses_only_the_sanitized_offline_contract(self):
        skill = Path("skills") / "pb_to_csharp_migration_harness"
        references = skill / "references"
        contract_path = references / "packaged-style-contract.json"
        contract_doc_path = references / "packaged-style-contract.md"
        update_path = references / "profile-update-workflow.md"

        self.assertTrue(contract_path.is_file())
        self.assertTrue(contract_doc_path.is_file())
        self.assertTrue(update_path.is_file())
        self.assertFalse((references / "author-tagged-style-baseline.md").exists())
        self.assertFalse((references / "author-tagged-program-style-profiles.json").exists())

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["contract_id"], "pb-csharp-offline-generalized")
        self.assertEqual(contract["normal_generation"]["profile_source"], "packaged-only")
        self.assertFalse(contract["normal_generation"]["external_discovery_allowed"])
        self.assertFalse(
            contract["normal_generation"]["profile_update_runs_during_normal_generation"]
        )
        self.assertEqual(
            contract["control_fallback_order"],
            ["target-wrapper", "konelib", "devexpress", "winforms"],
        )

        contract_docs = contract_doc_path.read_text(encoding="utf-8")
        for marker in (
            "Style Families",
            "Naming Grammar",
            "Event And Method Shapes",
            "Control Provider Fallback",
            "Designer Contract",
            "Grid And Repository Contract",
            "Caller And Procedure Contract",
            "Stored Procedure Shapes",
            "Forbidden Generation Patterns",
            "Evidence Requirements",
        ):
            with self.subTest(contract_marker=marker):
                self.assertIn(marker, contract_docs)

        ordinary_runtime_paths = (
            skill / "SKILL.md",
            references / "usage.md",
            contract_doc_path,
            contract_path,
            references / "datawindow-layout-mapping.md",
            references / "sql-formatting-bridge.md",
            references / "migration-output-checklist.md",
            skill / "examples" / "minimal-workflow.md",
        )
        ordinary_runtime_docs = "\n".join(
            path.read_text(encoding="utf-8") for path in ordinary_runtime_paths
        )
        for discovery_term in (
            "PblScripter",
            "ORCA",
            "SYS.OBJECTS",
            "SYS.SQL_MODULES",
            "source_sha256",
            "designer_sha256",
            "snapshot_date",
            "source_root",
        ):
            with self.subTest(discovery_term=discovery_term):
                self.assertNotIn(discovery_term, ordinary_runtime_docs)

        update_docs = update_path.read_text(encoding="utf-8")
        self.assertIn("never runs during normal generation", update_docs)
        for update_marker in ("PblScripter", "ORCA", "database", "scan", "Sanitization Gate"):
            with self.subTest(update_marker=update_marker):
                self.assertIn(update_marker, update_docs)

        packaged_docs = "\n".join(
            path.read_text(encoding="utf-8")
            for path in skill.rglob("*")
            if path.is_file() and path.suffix.lower() in {".md", ".json"}
        )
        private_literals = (
            "C_KONE110",
            "GWERP",
            "Geunho",
            "Jang-Geunho",
            "author-tagged",
            "CUSTCD",
            "ITEMCD",
            "ORGDIV",
        )
        for private_literal in private_literals:
            with self.subTest(private_literal=private_literal):
                self.assertNotIn(private_literal, packaged_docs)

        private_patterns = (
            r"\b[A-Za-z]:\\",
            r"\b[0-9A-Fa-f]{64}\b",
            r"\b[A-Z]{2}\d{6}(?:_[A-Z]+)?\b",
            r"\b[A-Z]{2}\d{3}T\b",
            r"\b(?:SP|sp)_[A-Z]{2}\d{6}[A-Z0-9_]*\b",
        )
        for private_pattern in private_patterns:
            with self.subTest(private_pattern=private_pattern):
                self.assertIsNone(re.search(private_pattern, packaged_docs))

        runtime_path = Path("src") / "skills" / "pb_to_csharp_migration.py"
        runtime_text = runtime_path.read_text(encoding="utf-8")
        runtime_issues = scan_private_runtime_fingerprints(
            runtime_text,
            runtime_path.as_posix(),
        )
        self.assertEqual([], runtime_issues)

        for retained_grammar in (
            "grdList",
            "gvwList",
            "colList",
            "colDetail",
            "Designer.cs",
        ):
            with self.subTest(retained_grammar=retained_grammar):
                self.assertIn(retained_grammar, runtime_text)

        for removed_metric in (
            "primary_csharp_pattern_counts",
            "designer_pattern_counts",
            "primary_csharp_baseline_files_analyzed",
            "designer_files_analyzed",
            "author_tagged_baseline_counts",
        ):
            with self.subTest(removed_metric=removed_metric):
                self.assertNotIn(removed_metric, runtime_text)

    def test_pb_privacy_scan_covers_manifest_all_declared_support_files_and_runtime(self):
        skill_dir = Path("skills") / "pb_to_csharp_migration_harness"
        scan_paths = collect_privacy_scan_paths(skill_dir, Path("."))
        expected_labels = {
            "SKILL.md",
            *REQUIRED_SUPPORT_FILES,
            *SHIPPED_RUNTIME_SOURCE_FILES,
        }

        self.assertEqual(expected_labels, {label for label, _ in scan_paths})
        self.assertEqual(12, len(scan_paths))
        self.assertTrue(all(path.is_file() for _, path in scan_paths))
        for label, path in scan_paths:
            with self.subTest(privacy_path=label):
                self.assertEqual(
                    [],
                    scan_private_runtime_fingerprints(
                        path.read_text(encoding="utf-8"),
                        label,
                    ),
                )

    def test_pb_runtime_privacy_scanner_detects_all_nine_leak_categories_by_default(self):
        leak_samples = {
            "absolute_windows_path": r'SOURCE_ROOT = "R:\\Internal\\Migration\\screen.txt"',
            "legacy_source_corpus_metric": 'STYLE_METRIC = "designer_files_analyzed"',
            "concrete_business_example_identifier": 'BUSINESS_FIELD = "CUSTCD"',
            "private_identity_assignment": 'PROFILE_OWNER = "Morgan Analyst"',
            "private_database_identifier": "USE [FinanceArchive2024];",
            "private_company_namespace": "using LedgerWorks.Internal.Controls;",
            "production_program_identifier": 'PROGRAM_ID = "QZ846205"',
            "production_procedure_identifier": 'PROCEDURE_NAME = "SP_RV731904_SELECT"',
            "production_source_identifier": (
                'SOURCE_FILE = "Programs/MK562817/MK562817.Designer.cs"'
            ),
        }

        for expected_code, sample in leak_samples.items():
            with self.subTest(expected_code=expected_code):
                issue_codes = {
                    issue["code"]
                    for issue in scan_private_runtime_fingerprints(sample)
                }
                self.assertIn(expected_code, issue_codes)

        combined_issue_codes = {
            issue["code"]
            for issue in scan_private_runtime_fingerprints("\n".join(leak_samples.values()))
        }
        self.assertEqual(set(leak_samples), combined_issue_codes)

        for database_reference in (
            "SELECT * FROM [FinanceArchive2024].[dbo].[LedgerEntry];",
            "SELECT * FROM FinanceArchive2024.dbo.LedgerEntry;",
            'DATABASE_NAME = "FinanceArchive2024"',
        ):
            with self.subTest(database_reference=database_reference):
                self.assertIn(
                    "private_database_identifier",
                    {
                        issue["code"]
                        for issue in scan_private_runtime_fingerprints(database_reference)
                    },
                )

        self.assertIn(
            "private_company_namespace",
            {
                issue["code"]
                for issue in scan_private_runtime_fingerprints(
                    "namespace LedgerWorks.Migration"
                )
            },
        )

    def test_pb_runtime_privacy_scanner_allows_documented_generic_placeholders(self):
        generic_synthetic_runtime = '''
USE [<Database>];
SELECT * FROM [<Database>].[dbo].[<Object>];
using System.Data;
using Microsoft.Extensions.DependencyInjection;
namespace SyntheticMigration
SYNTHETIC_PROGRAM = "<ProgramId>"
SYNTHETIC_PROCEDURE = "[dbo].[usp_<Feature>_<Operation>]"
SYNTHETIC_SOURCE = "examples/programs/<ProgramId>.Designer.cs"
SYNTHETIC_FORM = "CatalogBrowseForm"
SYNTHETIC_FIELDS = ("ENTITY_CODE", "INPUT_DATE", "DERIVED_YEAR", "BOUNDARY_DATE")
SYNTHETIC_UI = ("grdList", "gvwList", "colList_ENTITY_CODE", "colDetail_ENTITY_CODE", "Designer.cs")
'''
        self.assertEqual(
            [],
            scan_private_runtime_fingerprints(generic_synthetic_runtime),
        )

    def test_pb_privacy_scanner_source_has_no_private_detection_literals(self):
        scanner_path = (
            Path("skills")
            / "pb_to_csharp_migration_harness"
            / "scripts"
            / "smoke_check.py"
        )
        scanner_text = scanner_path.read_text(encoding="utf-8")
        self.assertEqual(
            [],
            scan_private_runtime_fingerprints(
                scanner_text,
                scanner_path.as_posix(),
            ),
        )

    def test_sql_provider_artifact_layout_and_release_version_are_synchronized(self):
        root_manifest = _manifest(Path("plugin.json"))
        codex_manifest = _manifest(Path(".codex-plugin") / "plugin.json")
        agent_manifest = _manifest(Path(".agents") / "plugins" / "kh-uaf" / "plugin.json")
        catalog_names = {skill["name"] for skill in collect_packaged_skills()["skills"]}
        root_skill_names = {skill["name"] for skill in root_manifest["skills"]}

        self.assertIn("sql-formatting", catalog_names)
        self.assertIn("sql-formatting", root_skill_names)
        self.assertEqual(root_manifest["version"], "2.9.135")
        self.assertEqual(codex_manifest["version"], "2.9.135")
        self.assertEqual(agent_manifest["version"], "2.9.135")
        for manifest in [root_manifest, codex_manifest]:
            with self.subTest(manifest=manifest["description"]):
                layout = manifest["artifact_layout"]
                self.assertEqual(layout["run_content"], ".kh/<skill>/<run-id>/content/")
                self.assertEqual(layout["run_state"], ".kh/<skill>/<run-id>/state/")

    def test_codex_plugin_manifest_exposes_repo_skills(self):
        manifest_path = Path(".codex-plugin") / "plugin.json"

        self.assertTrue(manifest_path.is_file())
        manifest = _manifest(manifest_path)
        root_manifest = _manifest(Path("plugin.json"))

        self.assertEqual(manifest["name"], "kh-uaf")
        self.assertEqual(manifest["version"], root_manifest["version"])
        self.assertGreaterEqual(_version_tuple(manifest["version"]), (2, 9, 10))
        self.assertEqual(manifest["skills"], "./skills/")
        codex_skill_root = Path(manifest["skills"])
        self.assertTrue(codex_skill_root.is_dir())
        self.assertEqual(
            set(_packaged_skill_frontmatter()),
            {
                _skill_frontmatter(path).get("name")
                for path in codex_skill_root.glob("*/SKILL.md")
            },
        )
        self.assertNotIn("apps", manifest)
        self.assertNotIn("mcpServers", manifest)

        interface = manifest["interface"]
        self.assertEqual(interface["displayName"], "KH UAF")
        self.assertIn("Skill", " ".join(interface["capabilities"]))
        self.assertIn("KH-Bench Verified", " ".join(interface["capabilities"]))
        self.assertIn("https://github.com/GNh0/KH", manifest["repository"])

    def test_release_manifest_identities_and_versions_match(self):
        root_manifest = _manifest(Path("plugin.json"))
        codex_manifest = _manifest(Path(".codex-plugin") / "plugin.json")
        agent_manifest = _manifest(Path(".agents") / "plugins" / "kh-uaf" / "plugin.json")

        manifests = (root_manifest, codex_manifest, agent_manifest)
        for manifest in manifests:
            with self.subTest(manifest=manifest["description"]):
                self.assertEqual(manifest["name"], root_manifest["name"])
                self.assertTrue(manifest["description"].strip())
                self.assertEqual(manifest["version"], root_manifest["version"])

        self.assertEqual(
            {manifest["description"] for manifest in manifests},
            {root_manifest["description"]},
        )
        self.assertIn("cannot guarantee host auto-selection", root_manifest["description"])

        self.assertGreaterEqual(_version_tuple(root_manifest["version"]), (2, 9, 10))

    def test_default_prompt_is_a_compact_bootstrap_contract(self):
        manifest = _manifest(Path(".codex-plugin") / "plugin.json")
        segments = manifest["interface"]["defaultPrompt"]

        self.assertIsInstance(segments, list)
        self.assertTrue(all(isinstance(segment, str) and segment.strip() for segment in segments))
        self.assertLessEqual(len(segments), 10)

        prompt = "\n".join(segments)
        character_count = len(prompt)
        estimated_tokens = (character_count + 3) // 4

        self.assertLess(character_count, 1800)
        self.assertLess(estimated_tokens, 450)
        self.assertEqual(len(segments), len(set(segments)))

        required_markers = [
            "kh-uaf:always-on-front-door",
            "first and alone",
            "execution_gate",
            "execution_authorization",
            "immediate_next_skills",
            "best available specialist provider",
            "GoalState",
            "current project, chat/task, and subagent lineage",
            "explicit authorization",
            "token_optimizer_status",
            "selected_not_executed_skills",
            "runtime_applied_skills",
            "verification-before-completion-harness",
            "user's current language",
            "selected skill docs",
            "cannot guarantee host auto-selection",
            "Audit compliance",
            "normal machine bootstrap",
            "current unfinished task evidence",
            "task completion",
            "new task",
        ]
        for marker in required_markers:
            with self.subTest(required_marker=marker):
                self.assertIn(marker, prompt)

        detailed_procedure_markers = [
            "BrainstormSession",
            "Visible brainstorming output gate",
            "large_work_orchestration_bundle",
            "pb-to-csharp-migration-harness",
            "sql-formatting-style-harness",
            "windows-dev-server-runner",
            "workflow_usability_auto",
            ".kh/development/<run-id>/state/progress.json",
            "For user-facing deliverables",
        ]
        for marker in detailed_procedure_markers:
            with self.subTest(detailed_procedure_marker=marker):
                self.assertNotIn(marker, prompt)

    def test_front_door_docs_bound_host_selection_and_same_task_reuse(self):
        skill = Path("skills") / "always_on_front_door"
        content = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                skill / "SKILL.md",
                skill / "references" / "usage.md",
                skill / "examples" / "minimal-workflow.md",
            )
        )

        for marker in (
            "cannot guarantee host auto-selection",
            "Audit compliance",
            "normal machine bootstrap",
            "current unfinished task",
            "task completion",
            "new task",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, content)

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

        manifest = _manifest(manifest_path)
        self.assertEqual(manifest["name"], "kh-uaf")
        self.assertNotIn("skills", manifest)

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
        self.assertIn("installed marketplace plugin cache", content)
        self.assertIn("Do not install a separate `$CODEX_HOME/skills` bootstrap copy", content)
        self.assertNotIn("install_codex_global_bootstrap.py", content)
        self.assertNotIn("kh-uaf-front-door", content)
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
        self.assertIn(_u("\uc124\uce58\ub41c marketplace \ud50c\ub7ec\uadf8\uc778 \uce90\uc2dc\ub9cc\uc73c\ub85c \ub3d9\uc791\ud574\uc57c \ud569\ub2c8\ub2e4"), content)
        self.assertNotIn("install_codex_global_bootstrap.py", content)
        self.assertNotIn("kh-uaf-front-door", content)
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

    def test_packaged_skill_frontmatter_matches_catalog_and_static_root_runtime_manifest(self):
        packaged = _packaged_skill_frontmatter()
        catalog_names = {
            skill["name"] for skill in collect_packaged_skills()["skills"]
        }

        self.assertGreaterEqual(len(packaged), 40)
        self.assertEqual(set(packaged), catalog_names)
        self.assertFalse(
            _static_runtime_exposure_gaps(),
            "Root plugin.json uses a static explicit skill schema; add every packaged "
            "frontmatter name before release.",
        )
        for name, path in packaged.items():
            with self.subTest(path=str(path)):
                frontmatter = _skill_frontmatter(path)
                self.assertEqual(frontmatter.get("name"), name)
                self.assertTrue(frontmatter.get("description"))

    def test_new_skill_is_path_discovered_but_fails_static_runtime_release_exposure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_root = root / "skills" / "new_release_harness"
            skill_root.mkdir(parents=True)
            (root / "plugin.json").write_text(
                json.dumps(_manifest(Path("plugin.json"))),
                encoding="utf-8",
            )
            (skill_root / "SKILL.md").write_text(
                "---\n"
                "name: new-release-harness\n"
                "description: Use when testing release exposure.\n"
                "---\n\n"
                "# New Release Harness\n",
                encoding="utf-8",
            )

            codex_path_discovery = set(_packaged_skill_frontmatter(root))
            catalog_names = {
                skill["name"]
                for skill in collect_packaged_skills(str(root / "skills"))["skills"]
            }

            self.assertIn("new-release-harness", codex_path_discovery)
            self.assertIn("new-release-harness", catalog_names)
            self.assertEqual(
                _static_runtime_exposure_gaps(root),
                {"new-release-harness"},
                "Path/catalog discovery must not be mistaken for automatic registration "
                "in the root host's static explicit skill schema.",
            )

if __name__ == "__main__":
    unittest.main()
