import hashlib
import tempfile
import unittest
from pathlib import Path

from src.skills.pb_migration_authority import (
    validate_pb_migration_authority_contract,
)
from src.skills.pb_migration_directives import (
    ACTION_WRITE,
    ISSUE_ANALYSIS_ONLY_WRITE,
    MODE_ANALYSIS_ONLY,
    Directive,
    ObservedAction,
    evaluate_pb_migration_directives,
)
from src.skills.pb_sql_generation_policy import (
    ISSUE_NEW_ROW_NUMBER_SEQUENCING,
    ISSUE_NEW_TABLE_VARIABLE,
    ISSUE_NEW_TEMP_TABLE,
    build_source_equivalence_evidence,
    evaluate_pb_sql_generation_policy,
)
from tests.test_pb_to_csharp_migration_harness import (
    orchestrate_pb_migration_validation,
    pasted_sql_evidence,
    patch_runtime_profile_path,
    sp_metadata_header,
    target_artifact_kwargs,
    valid_csharp_contract_sources,
    write_packaged_profile,
)


class PbGovernanceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.target = self._write(
            "Target.cs", "class TargetForm { void SaveTarget() {} }\n"
        )
        self.comparator = self._write(
            "Comparator.cs", "class LegacyForm { void SaveLegacy() {} }\n"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path.resolve()

    @staticmethod
    def _sha(path):
        return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def _target_receipt(self):
        return {
            "role": "code",
            "authority": "current_target",
            "path": str(self.target),
            "sha256": self._sha(self.target),
            "identifiers": ["TargetForm", "SaveTarget"],
        }

    def _comparator_contract(self):
        return {
            "receipt": {
                "role": "reference_code",
                "authority": "named_comparator",
                "path": str(self.comparator),
                "sha256": self._sha(self.comparator),
                "identifiers": ["LegacyForm", "SaveLegacy"],
            },
            "role_mapping": {"reference_code": "code"},
            "allowlist": {"properties": [], "behaviors": ["SaveFlow"]},
            "identifier_map": {
                "LegacyForm": "TargetForm",
                "SaveLegacy": "SaveTarget",
            },
            "retained_identifiers": [],
        }

    def _orchestration_inputs(self):
        sql = sp_metadata_header("Governance integration") + """
CREATE PROCEDURE DBO.SP_GENERALIZED_SELECT
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        csharp, designer = valid_csharp_contract_sources()
        profile_path, profile_hash = write_packaged_profile(self.root)
        targets = target_artifact_kwargs(
            csharp, designer, prefix="pb-governance-integration"
        )
        kwargs = {
            "csharp_source_text": csharp,
            "designer_source_text": designer,
            "original_sql_text": sql,
            "formatted_sql_text": sql,
            "source_evidence": [
                pasted_sql_evidence(
                    "SELECT @WORKTYPE AS WORKTYPE;",
                    evidence_role="body_fragment",
                )
            ],
            "profile_id": "pb-csharp-offline-generalized",
            "profile_version": "1.0",
            "profile_hash": profile_hash,
            "program_key": "InventoryBrowse",
            "result_fields": ["ENTITY_ID"],
            **targets,
        }
        return profile_path, kwargs, targets

    @staticmethod
    def _governance_inputs(targets):
        return {
            "authority_contract": {
                "target_receipts": [
                    {
                        "role": "code",
                        "authority": "current_target",
                        "path": targets["target_source_path"],
                        "sha256": targets["target_source_sha256"],
                        "identifiers": ["InventoryBrowseForm"],
                    },
                    {
                        "role": "designer",
                        "authority": "current_target",
                        "path": targets["target_designer_path"],
                        "sha256": targets["target_designer_sha256"],
                        "identifiers": ["InventoryBrowseForm"],
                    },
                ]
            },
            "directive_ledger": {
                "directives": [
                    {
                        "directive_id": "preserve-source",
                        "text": "Preserve the verified PB and SQL source contract.",
                    }
                ],
                "satisfied_ids": ["preserve-source"],
            },
        }

    def test_authority_passes_then_fails_on_target_hash_drift(self):
        receipt = self._target_receipt()
        passed = validate_pb_migration_authority_contract(
            target_receipts=[receipt]
        )
        self.assertTrue(passed.success, passed.metadata["issues"])

        self.target.write_text("class Changed {}\n", encoding="utf-8")
        failed = validate_pb_migration_authority_contract(
            target_receipts=[receipt]
        )
        self.assertFalse(failed.success)
        self.assertIn("artifact_sha256_mismatch", failed.metadata["issue_codes"])

    def test_named_comparator_is_scoped_to_allowlisted_behavior(self):
        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()],
            comparator=self._comparator_contract(),
            authority_requests=[
                {"category": "behavior", "name": "SaveFlow", "target_role": "code"},
                {"category": "behavior", "name": "DeleteFlow", "target_role": "code"},
            ],
        )
        self.assertTrue(result.success, result.metadata["issues"])
        resolutions = result.metadata["authority_resolutions"]
        self.assertEqual("named_comparator", resolutions[0]["authority"])
        self.assertEqual("current_target", resolutions[1]["authority"])

    def test_discovery_metadata_is_rejected_without_discovery(self):
        comparator = self._comparator_contract()
        comparator["history"] = ["do not inspect"]
        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()], comparator=comparator
        )
        self.assertFalse(result.success)
        self.assertIn("discovery_metadata_forbidden", result.metadata["issue_codes"])
        self.assertFalse(result.metadata["discovery_performed"])
        self.assertEqual([], result.metadata["external_sources_consulted"])

    def test_directives_accumulate_without_erasing_prior_requirements(self):
        receipt = evaluate_pb_migration_directives(
            [
                Directive("source", "Use exported PB source."),
                Directive("layout", "Preserve measured layout."),
            ],
            satisfied_ids=("source", "layout"),
            completion_requested=True,
        )
        self.assertTrue(receipt.completion_authorized, receipt.to_dict())
        self.assertEqual(
            ["source", "layout"],
            [item["directive_id"] for item in receipt.metadata["active"]],
        )
        self.assertEqual([], receipt.metadata["superseded"])

    def test_analysis_only_write_is_blocked(self):
        receipt = evaluate_pb_migration_directives(
            [Directive("audit", "Inspect and report only.")],
            satisfied_ids=("audit",),
            write_intent=MODE_ANALYSIS_ONLY,
            observed_actions=(ObservedAction("write-source", ACTION_WRITE),),
        )
        self.assertFalse(receipt.completion_authorized)
        self.assertIn(ISSUE_ANALYSIS_ONLY_WRITE, receipt.issue_codes)
        self.assertEqual(1, receipt.metadata["write_intent"]["observed_write_count"])

    def test_completion_claim_reports_missing_governance_and_project_inclusion(self):
        profile_path, kwargs, _ = self._orchestration_inputs()
        with patch_runtime_profile_path(profile_path):
            result = orchestrate_pb_migration_validation(
                completion_claims={"completion": True}, **kwargs
            )

        self.assertFalse(result.success)
        contract = result.metadata["validation_contract"]
        self.assertEqual("authority-contract", contract["failure_boundary"])
        self.assertIn(
            "pb_migration_authority_receipt_required",
            contract["governance"]["issue_codes"],
        )
        self.assertIn(
            "pb_migration_directive_receipt_required",
            contract["governance"]["issue_codes"],
        )
        stages = {stage["name"]: stage for stage in contract["completion_stages"]}
        self.assertEqual("blocked", stages["project-inclusion"]["status"])
        self.assertTrue(stages["project-inclusion"]["issues"])

    def test_stale_comparator_identifiers_are_rejected_in_generated_outputs(self):
        result = validate_pb_migration_authority_contract(
            target_receipts=[self._target_receipt()],
            comparator=self._comparator_contract(),
            generated_texts={
                "csharp": "class TargetForm { LegacyForm stale; }",
                "designer": "partial class TargetForm { SaveLegacy(); }",
                "sql": "SELECT LegacyForm FROM T",
            },
        )
        self.assertFalse(result.success)
        stale_roles = {
            issue["role"]
            for issue in result.metadata["issues"]
            if issue["code"] == "stale_comparator_identifier"
        }
        self.assertEqual({"csharp", "designer", "sql"}, stale_roles)

    def test_exact_source_authorizes_temp_table_table_variable_and_row_number(self):
        cases = [
            ("CREATE TABLE #GeneratedRows (ID INT);", ISSUE_NEW_TEMP_TABLE),
            ("DECLARE @GeneratedRows TABLE (ID INT);", ISSUE_NEW_TABLE_VARIABLE),
            (
                "SELECT ROW_NUMBER() OVER (ORDER BY R.ID) AS SEQ FROM RealRows R;",
                ISSUE_NEW_ROW_NUMBER_SEQUENCING,
            ),
        ]
        for sql, issue_code in cases:
            with self.subTest(issue_code=issue_code):
                baseline = evaluate_pb_sql_generation_policy(sql, source_sql=sql)
                self.assertFalse(baseline.allowed)
                self.assertIn(issue_code, baseline.issue_codes)
                fingerprint = baseline.metadata["constructs"][0][
                    "construct_fingerprint"
                ]
                evidence = build_source_equivalence_evidence(
                    sql,
                    sql,
                    equivalent=True,
                    authorized_construct_fingerprints=[fingerprint],
                )
                authorized = evaluate_pb_sql_generation_policy(
                    sql, source_sql=sql, evidence=evidence
                )
                self.assertTrue(authorized.allowed, authorized.to_dict())
                self.assertEqual(
                    1,
                    authorized.metadata["construct_counts"]["evidence_authorized"],
                )

    def test_orchestration_metadata_preserves_all_governance_receipts(self):
        profile_path, kwargs, targets = self._orchestration_inputs()
        with patch_runtime_profile_path(profile_path):
            result = orchestrate_pb_migration_validation(
                **self._governance_inputs(targets), **kwargs
            )

        self.assertTrue(result.success, result.to_dict())
        contract = result.metadata["validation_contract"]
        governance = contract["governance"]
        self.assertEqual("passed", governance["status"])
        self.assertTrue(governance["authority_supplied"])
        self.assertTrue(governance["directive_ledger_supplied"])
        self.assertEqual(
            governance, result.metadata["evidence"]["governance"]
        )
        self.assertEqual(
            "pb-migration-authority",
            governance["authority_receipt"]["harness"],
        )
        self.assertEqual(
            "preserve-source",
            governance["directive_receipt"]["active"][0]["directive_id"],
        )
        self.assertEqual(
            "pb_sql_generation_subquery_policy",
            result.metadata["evidence"]["sp"]["pb_sql_generation_policy"]["policy_id"],
        )


if __name__ == "__main__":
    unittest.main()
