import ast
import unittest
from pathlib import Path

from src.skills.pb_migration_directives import (
    ACTION_MUTATION,
    ACTION_READ,
    ACTION_REPORT,
    ACTION_SUBAGENT_IMPLEMENTATION,
    ACTION_WRITE,
    ISSUE_ACTIVE_CONFLICT,
    ISSUE_ACTIVE_UNRESOLVED,
    ISSUE_ANALYSIS_ONLY_MUTATION,
    ISSUE_ANALYSIS_ONLY_SUBAGENT_IMPLEMENTATION,
    ISSUE_ANALYSIS_ONLY_WRITE,
    ISSUE_DUPLICATE_DIRECTIVE_ID,
    ISSUE_PREMATURE_COMPLETION,
    ISSUE_UNDECLARED_SUPERSESSION_CONFLICT,
    ISSUE_UNKNOWN_SUPERSESSION,
    MODE_ANALYSIS_ONLY,
    AppendOnlyDirectiveLedger,
    Directive,
    ObservedAction,
    evaluate_pb_migration_directives,
)


class CumulativeDirectiveTests(unittest.TestCase):
    def test_additions_keep_all_nonconflicting_requirements_active(self):
        ledger = AppendOnlyDirectiveLedger()
        ledger.append(Directive("source", "Use exported PB source."))
        ledger.append(Directive("layout", "Preserve the measured layout."))

        receipt = ledger.evaluate(satisfied_ids=("layout", "source"))

        self.assertTrue(receipt.completion_authorized, receipt.to_dict())
        self.assertEqual(
            [item["directive_id"] for item in receipt.metadata["active"]],
            ["source", "layout"],
        )
        self.assertEqual(receipt.metadata["superseded"], [])
        self.assertEqual(receipt.metadata["conflict"], [])
        self.assertEqual(receipt.metadata["unresolved"], [])

    def test_correction_supersedes_only_explicit_conflict(self):
        directives = [
            Directive("source", "Use exported PB source."),
            Directive("layout-v1", "Use layout version one."),
            Directive(
                "layout-v2",
                "Use layout version two.",
                conflicts_with=("layout-v1",),
                supersedes=("layout-v1",),
            ),
        ]

        receipt = evaluate_pb_migration_directives(
            directives,
            satisfied_ids=("source", "layout-v2"),
        )

        self.assertTrue(receipt.completion_authorized, receipt.to_dict())
        self.assertEqual(
            [item["directive_id"] for item in receipt.metadata["active"]],
            ["source", "layout-v2"],
        )
        self.assertEqual(
            receipt.metadata["superseded"],
            [
                {
                    "directive_id": "layout-v1",
                    "directive_sequence": 1,
                    "superseded_by": "layout-v2",
                    "superseded_by_sequence": 2,
                }
            ],
        )
        self.assertEqual(receipt.metadata["conflict"][0]["status"], "superseded")

    def test_explicit_conflict_without_supersession_remains_active(self):
        receipt = evaluate_pb_migration_directives(
            [
                Directive("layout-v1", "Use layout version one."),
                Directive(
                    "layout-v2",
                    "Use layout version two.",
                    conflicts_with=("layout-v1",),
                ),
            ],
            satisfied_ids=("layout-v1", "layout-v2"),
        )

        self.assertFalse(receipt.completion_authorized)
        self.assertIn(ISSUE_ACTIVE_CONFLICT, receipt.issue_codes)
        self.assertEqual(receipt.metadata["conflict"][0]["status"], "active")
        self.assertEqual(
            [item["directive_id"] for item in receipt.metadata["active"]],
            ["layout-v1", "layout-v2"],
        )

    def test_supersession_requires_an_explicit_conflict_edge(self):
        receipt = evaluate_pb_migration_directives(
            [
                Directive("old", "Old requirement."),
                Directive("new", "New requirement.", supersedes=("old",)),
            ],
            satisfied_ids=("old", "new"),
        )

        self.assertFalse(receipt.completion_authorized)
        self.assertIn(
            ISSUE_UNDECLARED_SUPERSESSION_CONFLICT,
            receipt.issue_codes,
        )
        self.assertEqual(
            [item["directive_id"] for item in receipt.metadata["active"]],
            ["old", "new"],
        )

    def test_duplicate_ids_fail_closed_without_rewriting_the_log(self):
        ledger = AppendOnlyDirectiveLedger(
            [
                Directive("same", "First requirement."),
                Directive("same", "Second requirement."),
            ]
        )

        receipt = ledger.evaluate(satisfied_ids=("same",))

        self.assertFalse(receipt.completion_authorized)
        self.assertIn(ISSUE_DUPLICATE_DIRECTIVE_ID, receipt.issue_codes)
        self.assertEqual(len(ledger.directives), 2)
        self.assertIsInstance(ledger.directives, tuple)
        self.assertFalse(hasattr(ledger, "remove"))
        self.assertFalse(hasattr(ledger, "replace"))

    def test_unknown_supersession_fails_closed(self):
        receipt = evaluate_pb_migration_directives(
            [
                Directive(
                    "correction",
                    "Correct the prior requirement.",
                    conflicts_with=("missing",),
                    supersedes=("missing",),
                )
            ],
            satisfied_ids=("correction",),
        )

        self.assertFalse(receipt.completion_authorized)
        self.assertIn(ISSUE_UNKNOWN_SUPERSESSION, receipt.issue_codes)
        self.assertEqual(receipt.metadata["conflict"][0]["status"], "unknown")

    def test_unresolved_active_directive_blocks_premature_completion(self):
        receipt = evaluate_pb_migration_directives(
            [Directive("save", "Implement the SAVE flow contract.")],
            completion_requested=True,
        )

        self.assertFalse(receipt.completion_authorized)
        self.assertIn(ISSUE_ACTIVE_UNRESOLVED, receipt.issue_codes)
        self.assertIn(ISSUE_PREMATURE_COMPLETION, receipt.issue_codes)
        self.assertEqual(receipt.metadata["unresolved"][0]["directive_id"], "save")
        self.assertFalse(receipt.metadata["completion_authorized"])


class WriteIntentTests(unittest.TestCase):
    def test_analysis_only_allows_reads_and_reports_with_zero_writes(self):
        receipt = evaluate_pb_migration_directives(
            [Directive("audit", "Report current behavior.")],
            satisfied_ids=("audit",),
            write_intent=MODE_ANALYSIS_ONLY,
            observed_actions=(
                ObservedAction("read-source", ACTION_READ),
                ObservedAction("report-findings", ACTION_REPORT),
            ),
        )

        intent = receipt.metadata["write_intent"]
        self.assertTrue(receipt.completion_authorized, receipt.to_dict())
        self.assertFalse(intent["writes_permitted"])
        self.assertEqual(intent["observed_write_count"], 0)
        self.assertEqual(intent["observed_mutation_count"], 0)
        self.assertEqual(intent["observed_subagent_implementation_count"], 0)
        self.assertEqual(intent["violations"], [])

    def test_analysis_only_observed_writes_mutations_and_subagents_fail(self):
        receipt = evaluate_pb_migration_directives(
            [Directive("audit", "Report current behavior.")],
            satisfied_ids=("audit",),
            write_intent=MODE_ANALYSIS_ONLY,
            observed_actions=(
                ObservedAction("write-file", ACTION_WRITE),
                ObservedAction("mutate-db", ACTION_MUTATION),
                ObservedAction(
                    "delegate-implementation",
                    ACTION_SUBAGENT_IMPLEMENTATION,
                ),
            ),
        )

        self.assertFalse(receipt.completion_authorized)
        self.assertIn(ISSUE_ANALYSIS_ONLY_WRITE, receipt.issue_codes)
        self.assertIn(ISSUE_ANALYSIS_ONLY_MUTATION, receipt.issue_codes)
        self.assertIn(
            ISSUE_ANALYSIS_ONLY_SUBAGENT_IMPLEMENTATION,
            receipt.issue_codes,
        )
        self.assertEqual(len(receipt.metadata["write_intent"]["violations"]), 3)


class DeterminismAndIsolationTests(unittest.TestCase):
    def test_receipt_metadata_is_stable_and_mixed_language_text_is_opaque(self):
        text = (
            "\ud55c\uad6d\uc5b4 requirement / "
            "\u65e5\u672c\u8a9e correction / "
            "requisito en Espa\u00f1ol / \u0645\u062a\u0637\u0644\u0628"
        )
        directives = [Directive("mixed", text)]

        first = evaluate_pb_migration_directives(
            directives,
            satisfied_ids=("mixed",),
        )
        second = evaluate_pb_migration_directives(
            directives,
            satisfied_ids=("mixed",),
        )

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.metadata["active"][0]["text"], text)
        self.assertEqual(
            first.metadata["receipt_sha256"],
            second.metadata["receipt_sha256"],
        )
        self.assertNotIn("language", first.metadata)
        self.assertNotIn("memory", first.metadata)

    def test_module_ast_has_no_io_process_network_or_memory_dependency(self):
        module_path = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "skills"
            / "pb_migration_directives.py"
        )
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imports = set()
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.add(node.func.id)

        self.assertTrue(
            imports.isdisjoint(
                {
                    "asyncio",
                    "multiprocessing",
                    "os",
                    "pathlib",
                    "socket",
                    "subprocess",
                    "tempfile",
                    "threading",
                    "urllib",
                }
            ),
            imports,
        )
        self.assertNotIn("open", calls)


if __name__ == "__main__":
    unittest.main()
