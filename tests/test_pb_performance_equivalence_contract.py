import ast
import hashlib
from pathlib import Path
import tempfile
import unittest

from src.skills.pb_performance_equivalence_contract import (
    ISSUE_CONTEXT_MISMATCH,
    ISSUE_RECEIPT_CALL_DUPLICATE,
    ISSUE_RECEIPT_DUPLICATE,
    ISSUE_RESULT_VALUE_MISMATCH,
    ISSUE_SQL_HASH_MISMATCH,
    validate_pb_performance_equivalence_contract,
)


class PbPerformanceEquivalenceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.before_sql = self._write("before.sql", "SELECT value FROM sample WHERE id = @id")
        self.after_sql = self._write("after.sql", "SELECT value FROM sample WHERE id = @id ORDER BY id")

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, name, value):
        path = self.root / name
        path.write_text(value, encoding="utf-8", newline="")
        return path

    def _sha(self, path):
        return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def _receipt(self, side, path, *, call_id=None, receipt_id=None, database="DB_A", value_hash=None):
        digest = "sha256:" + "1" * 64
        return {
            "receipt_id": receipt_id or "receipt-" + side,
            "call_id": call_id or "call-" + side,
            "tool_name": "sql-profiler",
            "side": side,
            "observed_at": "2026-08-24T12:00:00+09:00",
            "exit_code": 0,
            "errors": [],
            "database": database,
            "environment": "staging",
            "parameters": {"id": 7},
            "sql_path": str(path),
            "sql_sha256": self._sha(path),
            "execution_plan_sha256": digest,
            "logical_reads": 12 if side == "before" else 8,
            "runtime_samples_ms": [10.0, 11.0, 9.0],
            "result": {
                "schema_sha256": digest,
                "row_count": 1,
                "value_sha256": value_hash or digest,
            },
        }

    def test_no_claim_is_not_requested_even_with_passed_json(self):
        result = validate_pb_performance_equivalence_contract(
            claim="static SQL formatting cleanup",
            execution_receipts=[{"status": "passed", "verified": True}],
        )
        self.assertTrue(result.success)
        self.assertEqual(result.metadata["status"], "not_requested")

    def test_performance_claim_requires_real_receipts_not_forged_status_json(self):
        result = validate_pb_performance_equivalence_contract(
            claim="performance tuning equivalence",
            execution_receipts=[{"status": "passed", "verified": True}],
        )
        self.assertFalse(result.success)
        self.assertEqual(result.exit_code, 1)

    def test_valid_correlated_before_after_receipts_pass(self):
        result = validate_pb_performance_equivalence_contract(
            claim="performance equivalence",
            execution_receipts=[
                self._receipt("before", self.before_sql),
                self._receipt("after", self.after_sql),
            ],
        )
        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["status"], "passed")

    def test_duplicate_receipt_and_call_ids_are_rejected(self):
        before = self._receipt("before", self.before_sql, receipt_id="same", call_id="same-call")
        after = self._receipt("after", self.after_sql, receipt_id="same", call_id="same-call")
        result = validate_pb_performance_equivalence_contract(claim="tuning", execution_receipts=[before, after])
        codes = [item["code"] for item in result.metadata["issues"]]
        self.assertIn(ISSUE_RECEIPT_DUPLICATE, codes)
        self.assertIn(ISSUE_RECEIPT_CALL_DUPLICATE, codes)

    def test_context_and_result_value_mismatch_are_rejected(self):
        before = self._receipt("before", self.before_sql)
        after = self._receipt("after", self.after_sql, database="DB_B", value_hash="sha256:" + "2" * 64)
        result = validate_pb_performance_equivalence_contract(claim="equivalence", execution_receipts=[before, after])
        codes = [item["code"] for item in result.metadata["issues"]]
        self.assertIn(ISSUE_CONTEXT_MISMATCH, codes)
        self.assertIn(ISSUE_RESULT_VALUE_MISMATCH, codes)

    def test_sql_hash_is_bound_to_actual_sql_bytes(self):
        before = self._receipt("before", self.before_sql)
        self.before_sql.write_text("SELECT forged FROM sample", encoding="utf-8", newline="")
        after = self._receipt("after", self.after_sql)
        result = validate_pb_performance_equivalence_contract(claim="performance", execution_receipts=[before, after])
        self.assertIn(ISSUE_SQL_HASH_MISMATCH, [item["code"] for item in result.metadata["issues"]])

    def test_alias_receipt_argument_and_boolean_claim_work(self):
        result = validate_pb_performance_equivalence_contract(
            performance_claimed=True,
            tool_receipts=[self._receipt("before", self.before_sql), self._receipt("after", self.after_sql)],
        )
        self.assertTrue(result.success, result.to_dict())

    def test_ast_parse(self):
        module = Path(__file__).resolve().parents[1] / "src/skills/pb_performance_equivalence_contract.py"
        ast.parse(module.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
