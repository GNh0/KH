import ast
import hashlib
import tempfile
import unittest
from pathlib import Path

from src.skills.pb_migration_authority import validate_pb_migration_authority_contract


class PbMigrationAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.target = self._write("Target.cs", "class TargetForm { void SaveTarget() {} }\n")
        self.comparator = self._write(
            "Comparator.cs", "class LegacyForm { void SaveLegacy() {} }\n"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path.resolve()

    @staticmethod
    def _sha(path: Path) -> str:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    def _target_receipt(self):
        return {
            "role": "code",
            "authority": "current_target",
            "path": str(self.target),
            "sha256": self._sha(self.target),
            "identifiers": ["TargetForm", "SaveTarget"],
        }

    def _comparator_contract(self, **overrides):
        contract = {
            "receipt": {
                "role": "reference_code",
                "authority": "named_comparator",
                "path": str(self.comparator),
                "sha256": self._sha(self.comparator),
                "identifiers": ["LegacyForm", "SaveLegacy"],
            },
            "role_mapping": {"reference_code": "code"},
            "allowlist": {
                "properties": ["TabIndex"],
                "behaviors": ["SaveFlow"],
            },
            "identifier_map": {
                "LegacyForm": "TargetForm",
                "SaveLegacy": "SaveTarget",
            },
            "retained_identifiers": [],
        }
        contract.update(overrides)
        return contract

    def _comparator_from_source(self, source, **overrides):
        self.comparator.write_text(source, encoding="utf-8")
        contract = self._comparator_contract()
        contract["receipt"]["sha256"] = self._sha(self.comparator)
        contract["receipt"]["identifiers"] = []
        contract.update(overrides)
        return contract

    def test_current_target_beats_out_of_scope_comparator(self):
        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()],
            comparator=self._comparator_contract(),
            authority_requests=[
                {"category": "behavior", "name": "DeleteFlow", "target_role": "code"}
            ],
        )

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual(
            "current_target", result.metadata["authority_resolutions"][0]["authority"]
        )
        self.assertEqual(
            "packaged_profile", result.metadata["style_authority"]["authority"]
        )

    def test_in_scope_comparator_governs_only_the_named_behavior(self):
        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()],
            comparator=self._comparator_contract(),
            authority_requests=[
                {"category": "behavior", "name": "SaveFlow", "target_role": "code"},
                {"category": "style", "name": "DefaultStyle", "target_role": "code"},
            ],
        )

        self.assertTrue(result.success, result.metadata["issues"])
        resolutions = result.metadata["authority_resolutions"]
        self.assertEqual("named_comparator", resolutions[0]["authority"])
        self.assertEqual("reference_code", resolutions[0]["source_role"])
        self.assertEqual("packaged_profile", resolutions[1]["authority"])

    def test_hash_drift_blocks_exact_receipt(self):
        receipt = self._target_receipt()
        self.target.write_text("class Changed {}\n", encoding="utf-8")

        result = validate_pb_migration_authority_contract(target_receipts=[receipt])

        self.assertFalse(result.success)
        self.assertIn("artifact_sha256_mismatch", result.metadata["issue_codes"])
        self.assertEqual(1, result.exit_code)

    def test_broad_style_override_is_rejected(self):
        comparator = self._comparator_contract(
            allowlist={"properties": ["*"], "behaviors": [], "style": ["all"]}
        )

        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )

        self.assertFalse(result.success)
        self.assertIn("comparator_scope_broad", result.metadata["issue_codes"])

    def test_discovery_metadata_is_rejected_without_using_private_values(self):
        comparator = self._comparator_contract()
        comparator["history"] = ["private value is not inspected"]
        comparator["similar_programs"] = ["unrelated"]
        comparator["receipt"]["root"] = str(self.root)

        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )

        self.assertFalse(result.success)
        codes = [issue["code"] for issue in result.metadata["issues"]]
        self.assertEqual(3, codes.count("discovery_metadata_forbidden"))
        self.assertFalse(result.metadata["discovery_performed"])
        self.assertEqual([], result.metadata["external_sources_consulted"])

    def test_stale_identifier_in_generated_artifacts_is_rejected(self):
        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()],
            comparator=self._comparator_contract(),
            generated_texts={
                "csharp": "class TargetForm { LegacyForm field; }",
                "designer": "partial class TargetForm { SaveLegacy(); }",
                "sql": "SELECT LegacyForm FROM T",
                "layout": '<control name="LegacyForm" />',
            },
        )

        self.assertFalse(result.success)
        stale = [
            issue
            for issue in result.metadata["issues"]
            if issue["code"] == "stale_comparator_identifier"
        ]
        self.assertEqual({"csharp", "designer", "sql", "layout"}, {i["role"] for i in stale})

    def test_mapped_identifiers_pass_in_generated_texts(self):
        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()],
            comparator=self._comparator_contract(),
            generated_texts={
                "csharp": "class TargetForm { void Run() { SaveTarget(); } }",
                "designer": "partial class TargetForm { }",
                "sql": "SELECT SaveTarget FROM T",
                "layout": '<control name="TargetForm" />',
            },
        )

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual([], result.metadata["issue_codes"])

    def test_comments_and_string_literals_do_not_trigger_false_positives(self):
        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()],
            comparator=self._comparator_contract(),
            generated_texts={
                "csharp": {
                    "language": "csharp",
                    "text": '// LegacyForm\nvar text = "SaveLegacy"; /* LegacyForm */',
                },
                "designer": {
                    "language": "csharp",
                    "text": '@"LegacyForm" + $"SaveLegacy";',
                },
                "sql": {
                    "language": "sql",
                    "text": "-- LegacyForm\nSELECT 'SaveLegacy' /* LegacyForm */",
                },
                "layout": {
                    "language": "layout",
                    "text": '<!-- LegacyForm and SaveLegacy -->',
                },
            },
        )

        self.assertTrue(result.success, result.metadata["issues"])

    def test_unmapped_comparator_identifier_fails_even_without_generated_text(self):
        comparator = self._comparator_contract(
            identifier_map={"LegacyForm": "TargetForm"}
        )

        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )

        self.assertFalse(result.success)
        self.assertIn(
            "comparator_identifier_authority_invalid", result.metadata["issue_codes"]
        )

    def test_empty_identifier_metadata_cannot_hide_stale_comparator_form(self):
        comparator = self._comparator_from_source(
            "public partial class StaleComparatorForm : Form { }\n",
            identifier_map={},
            retained_identifiers=[],
        )

        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )

        self.assertFalse(result.success)
        unmapped = {
            issue.get("identifier")
            for issue in result.metadata["issues"]
            if issue["code"] == "comparator_identifier_authority_invalid"
        }
        self.assertIn("StaleComparatorForm", unmapped)

    def test_exact_comparator_inventory_masks_comments_and_string_literals(self):
        comparator = self._comparator_from_source(
            '''
// class StaleComparatorForm { }
class LegacyForm
{
    /* void StaleComparatorEvent() { } */
    private string note = "StaleComparatorField";
    void SaveLegacy() { }
}
''',
            identifier_map={
                "LegacyForm": "TargetForm",
                "SaveLegacy": "SaveTarget",
            },
            retained_identifiers=["note"],
        )

        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )

        self.assertTrue(result.success, result.metadata["issues"])
        inventory = result.metadata["comparator"]["identifier_inventory"]
        self.assertNotIn("StaleComparatorForm", inventory)
        self.assertNotIn("StaleComparatorEvent", inventory)
        self.assertNotIn("StaleComparatorField", inventory)

    def test_field_and_property_inventory_rejects_stale_names_until_mapped(self):
        comparator = self._comparator_from_source(
            '''
class LegacyForm
{
    private string OldField;
    public string OldProp { get; set; }
    private void SaveLegacy() { var localOnly = OldField; }
}
''',
            identifier_map={
                "LegacyForm": "TargetForm",
                "SaveLegacy": "SaveTarget",
            },
        )

        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )

        self.assertFalse(result.success)
        invalid = {
            issue["identifier"]
            for issue in result.metadata["issues"]
            if issue["code"] == "comparator_identifier_authority_invalid"
        }
        self.assertEqual({"OldField", "OldProp"}, invalid)

        comparator["identifier_map"].update(
            {"OldField": "TargetForm", "OldProp": "SaveTarget"}
        )
        mapped = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )
        self.assertTrue(mapped.success, mapped.metadata["issues"])

    def test_sql_and_layout_identifier_inventory_masks_comments_and_literals(self):
        sql = self._write(
            "Comparator.sql",
            "-- OldComment\nSELECT OldField FROM OldTable WHERE OldField = 'OldLiteral';\n",
        )
        layout = self._write(
            "Comparator.xml",
            '<!-- OldComment --><control name="OldControl" caption="OldLiteral" property="OldProp" />',
        )
        comparator = self._comparator_contract()
        comparator["receipt"] = {
            "role": "reference_code",
            "authority": "named_comparator",
            "path": str(sql),
            "sha256": self._sha(sql),
            "language": "sql",
            "identifiers": [],
        }
        comparator["identifier_map"] = {
            "OldField": "TargetForm",
            "OldTable": "SaveTarget",
        }
        comparator["retained_identifiers"] = []
        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )
        self.assertTrue(result.success, result.metadata["issues"])
        self.assertIn("OldField", result.metadata["comparator"]["identifier_inventory"])
        self.assertIn("OldTable", result.metadata["comparator"]["identifier_inventory"])
        self.assertNotIn("OldComment", result.metadata["comparator"]["identifier_inventory"])
        self.assertNotIn("OldLiteral", result.metadata["comparator"]["identifier_inventory"])

        layout_receipt = dict(comparator["receipt"])
        layout_receipt.update({"path": str(layout), "sha256": self._sha(layout), "language": "layout"})
        comparator["receipt"] = layout_receipt
        comparator["identifier_map"] = {"OldControl": "TargetForm", "OldProp": "SaveTarget"}
        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )
        self.assertTrue(result.success, result.metadata["issues"])
        self.assertIn("OldControl", result.metadata["comparator"]["identifier_inventory"])
        self.assertIn("OldProp", result.metadata["comparator"]["identifier_inventory"])
        self.assertNotIn("OldLiteral", result.metadata["comparator"]["identifier_inventory"])

    def test_extracted_identifiers_can_map_to_exact_target_inventory(self):
        target_receipt = self._target_receipt()
        target_receipt["identifiers"] = []
        comparator = self._comparator_from_source(
            "class LegacyForm { void SaveLegacy() { } }\n",
            identifier_map={
                "LegacyForm": "TargetForm",
                "SaveLegacy": "SaveTarget",
            },
        )

        result = validate_pb_migration_authority_contract(
            target_receipts=[target_receipt], comparator=comparator
        )

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual(
            ["LegacyForm", "SaveLegacy"],
            result.metadata["comparator"]["identifier_inventory"],
        )
        self.assertEqual(
            ["SaveTarget", "TargetForm"], result.metadata["target_identifier_inventory"]
        )

    def test_common_language_and_framework_identifiers_are_not_authority_names(self):
        comparator = self._comparator_from_source(
            '''
public partial class LegacyForm : Form
{
    private Button btnLegacy;
    public event EventHandler Saved;

    private void InitializeComponent()
    {
        this.btnLegacy = new Button();
    }

    private void SaveLegacy(object sender, EventArgs e) { }
}
''',
            identifier_map={
                "LegacyForm": "TargetForm",
                "SaveLegacy": "SaveTarget",
            },
            retained_identifiers=["btnLegacy", "Saved"],
        )

        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )

        self.assertTrue(result.success, result.metadata["issues"])
        inventory = result.metadata["comparator"]["identifier_inventory"]
        for common in (
            "class",
            "partial",
            "Form",
            "Button",
            "EventHandler",
            "EventArgs",
            "InitializeComponent",
        ):
            self.assertNotIn(common, inventory)

    def test_vacuous_comparator_scope_is_rejected(self):
        comparator = self._comparator_contract(
            allowlist={"properties": [], "behaviors": []}
        )

        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )

        self.assertFalse(result.success)
        self.assertIn("comparator_scope_vacuous", result.metadata["issue_codes"])

    def test_comparator_hash_drift_blocks_extracted_identifier_inventory(self):
        comparator = self._comparator_from_source(
            "class StaleComparatorForm { }\n",
            identifier_map={},
            retained_identifiers=[],
        )
        self.comparator.write_text("class ChangedComparatorForm { }\n", encoding="utf-8")

        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )

        self.assertFalse(result.success)
        self.assertIn("artifact_sha256_mismatch", result.metadata["issue_codes"])

    def test_module_and_test_sources_parse_as_ast(self):
        project = Path(__file__).resolve().parents[1]
        for relative in (
            "src/skills/pb_migration_authority.py",
            "tests/test_pb_migration_authority.py",
        ):
            ast.parse((project / relative).read_text(encoding="utf-8"), filename=relative)


if __name__ == "__main__":
    unittest.main()
