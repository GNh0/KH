import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def frontmatter(path: str) -> str:
    return read_text(path).split("---", 2)[1].lower()


class LightweightSkillDiscoveryContractTests(unittest.TestCase):
    def test_manifests_define_direct_or_single_domain_default(self):
        paths = [
            ".codex-plugin/plugin.json",
            ".agents/plugins/kh-uaf/plugin.json",
            "plugin.json",
        ]
        manifests = [json.loads(read_text(path)) for path in paths]

        self.assertEqual({manifest["version"] for manifest in manifests}, {"2.9.146"})
        for manifest in manifests:
            description = manifest["description"].lower()
            self.assertIn("ordinary clear requests run directly", description)
            self.assertIn("load only the matching domain skill", description)
            self.assertIn("load only on concrete triggers", description)
            self.assertIn("stay silent unless blocked or requested", description)

    def test_front_door_is_explicit_only_and_not_an_ordinary_specialist(self):
        fm = frontmatter("skills/always_on_front_door/SKILL.md")
        metadata = read_text("skills/always_on_front_door/agents/openai.yaml").lower()
        root_manifest = json.loads(read_text("plugin.json"))
        entry = next(skill for skill in root_manifest["skills"] if skill["name"] == "always-on-front-door")

        self.assertIn("explicitly requests kh routing evidence", fm)
        self.assertIn("do not invoke for ordinary clear work", fm)
        self.assertNotIn("starting any new user request", fm)
        self.assertIn("allow_implicit_invocation: false", metadata)
        self.assertIn("never select it as an ordinary specialist", entry["description"].lower())

    def test_token_optimizer_requires_a_reducible_payload_or_explicit_request(self):
        fm = frontmatter("skills/token_optimizer/SKILL.md")
        combined = "\n".join(
            [
                read_text("skills/token_optimizer/SKILL.md"),
                read_text("skills/token_optimizer/references/usage.md"),
                read_text("skills/token_optimizer/examples/minimal-workflow.md"),
            ]
        ).lower()

        self.assertIn("large reducible", fm)
        self.assertIn("explicitly requests token optimization or telemetry", fm)
        self.assertIn("do not invoke for short ordinary work", fm)
        self.assertNotIn("every kh-routed turn", combined)
        self.assertNotIn("must run even if the request is light/direct", combined)
        self.assertIn("do not narrate the decision unless requested or blocked", combined)

    def test_configured_mcp_use_does_not_select_credential_safety(self):
        fm = frontmatter("skills/credential_safety_harness/SKILL.md")
        combined = "\n".join(
            [
                read_text("skills/credential_safety_harness/SKILL.md"),
                read_text("skills/credential_safety_harness/references/usage.md"),
                read_text("skills/credential_safety_harness/examples/minimal-workflow.md"),
            ]
        ).lower()

        self.assertIn("actual credentials", fm)
        self.assertIn("do not invoke merely because an already-configured mcp", fm)
        self.assertIn("connection status and sql execution", combined)
        self.assertIn("do not load or report this harness merely", combined)

    def test_domain_and_workflow_skills_do_not_require_front_door_preflight(self):
        forbidden = (
            "always-on-front-door has already run",
            "start every non-trivial turn through `always-on-front-door`",
            "start non-trivial work through `always-on-front-door`",
            "apply `always-on-front-door` to every new",
        )
        conflicts = []
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            if path.parent.name == "always_on_front_door":
                continue
            text = path.read_text(encoding="utf-8").lower()
            for phrase in forbidden:
                if phrase in text:
                    conflicts.append(f"{path.parent.name}:{phrase}")
        self.assertEqual([], conflicts)

    def test_supporting_docs_do_not_restore_mandatory_routing_or_token_preflight(self):
        forbidden = (
            "run kh front-door intake before opening",
            "otherwise run the front-door python module before project reads",
            "source text has `token_optimizer_status=passthrough`",
            "mark pb, c#, designer, and sql source as `token_optimizer_status=passthrough`",
            "omits `kh_front_door_evidence`, `workspace_strategy`, `token_optimizer_status`",
        )
        conflicts = []
        for path in sorted((ROOT / "skills").glob("**/*.md")):
            text = path.read_text(encoding="utf-8").lower()
            for phrase in forbidden:
                if phrase in text:
                    conflicts.append(f"{path.relative_to(ROOT)}:{phrase}")
        self.assertEqual([], conflicts)

    def test_primary_domain_skills_remain_directly_discoverable(self):
        expectations = {
            "skills/sql_formatting/SKILL.md": "sql or t-sql is generated",
            "skills/csharp_designer_style_harness/SKILL.md": "generating, modifying, or reviewing",
            "skills/pb_to_csharp_migration_harness/SKILL.md": "powerbuilder-to-c#",
            "skills/brainstorming_harness/SKILL.md": "starting an underspecified",
        }
        for path, phrase in expectations.items():
            with self.subTest(path=path):
                self.assertIn(phrase, frontmatter(path))

    def test_meta_routers_are_not_ordinary_request_triggers(self):
        paths = (
            "skills/automatic_intake_harness/SKILL.md",
            "skills/request_complexity_router/SKILL.md",
            "skills/plugin_composition_policy/SKILL.md",
        )
        for path in paths:
            with self.subTest(path=path):
                fm = frontmatter(path)
                self.assertTrue(
                    "do not invoke for ordinary clear requests" in fm
                    or "do not invoke for an ordinary clear request" in fm
                    or "do not invoke for a clear direct or single-provider request" in fm,
                    fm,
                )


if __name__ == "__main__":
    unittest.main()
