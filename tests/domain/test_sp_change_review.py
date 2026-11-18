import unittest
from pathlib import Path

from src.runtime.hooks import inspect
from src.sql.checks import check_sql


def procedure(body):
    return '-- =============================================\n-- AUTHOR: Writer\n-- CREATE DATE: 2026-01-01\n-- DESCRIPTION: 검사 조회\n-- =============================================\nCREATE PROC dbo.Example @mode varchar(10), @m varchar(10) AS\nBEGIN\n' + body + '\nEND'


class SpChangeReviewTests(unittest.TestCase):
    def test_one_statement_modes_and_guarded_calls(self):
        original = procedure('EXEC dbo.RecordUse;')
        changed = procedure("IF @mode = 'READ' SELECT 1; ELSE IF @mode IN ('EDIT') EXEC dbo.RecordUse;")
        result = check_sql(changed, original=original, compare_original=False, review_sp_changes=True)
        changes = [item.details for item in result.issues if item.code == 'sp_operation_change_review']
        self.assertEqual(["@MODE = 'READ'", "@MODE = 'EDIT'", 'DBO.RECORDUSE'], [c['name'] for c in changes])
        self.assertEqual(["@MODE IN ('EDIT')"], changes[-1]['guards'])

    def test_requested_scope_is_not_inferred_from_a_working_draft(self):
        original = procedure("EXEC dbo.RecordUse; IF @mode = 'ADD' BEGIN INSERT dbo.LogRows VALUES (1); END")
        changed = procedure("IF @mode = 'ADD' BEGIN EXEC dbo.RecordUse; INSERT dbo.LogRows VALUES (1); END\n"
                            "ELSE IF @mode = 'EDIT' BEGIN UPDATE A SET Qty = 3 FROM dbo.StockRows A; END")
        result = check_sql(changed, original=original, compare_original=False, review_sp_changes=True)
        self.assertTrue(result.incomplete)
        events = [(item.details['operation'], item.details['name'], item.line) for item in result.issues
                  if item.code == 'sp_operation_change_review']
        self.assertEqual([('call', 'DBO.RECORDUSE', 8), ('branch', "@MODE = 'EDIT'", 9),
                          ('write', 'UPDATE DBO.STOCKROWS', 9)], events)
        saved = inspect(Path('Example.sql'), changed, original=original, require_procedure_header=True)
        self.assertTrue(saved['incomplete'])
        self.assertIn('DBO.RECORDUSE', ' '.join(saved['sp_changes']))
        self.assertNotIn('sp_changes', inspect(Path('ordinary.sql'), changed, original=original))

    def test_compare_numeric_output_against_the_same_aliased_expression(self):
        original = procedure('SELECT SUM(A.Qty) AS Qty FROM dbo.Rows A;')
        for wrapper in ('CONVERT(NUMERIC(18,4), SUM(A.Qty))', 'CAST(SUM(A.Qty) AS DECIMAL(18,4))'):
            changed = original.replace('SUM(A.Qty)', wrapper)
            review = check_sql(changed, original=original, compare_original=False, review_sp_changes=True)
            findings = [item for item in review.issues if item.code == 'sp_output_type_change_review']
            self.assertEqual(['QTY'], [item.details['column'] for item in findings])
            self.assertTrue(review.incomplete)
            same = check_sql(changed, original=changed, compare_original=False, review_sp_changes=True)
            self.assertFalse(same.incomplete)
        unrelated = procedure("SELECT 'CONVERT(NUMERIC(18,4), SUM(A.Qty))' AS Example;")
        self.assertFalse(check_sql(unrelated, original=original, compare_original=False, review_sp_changes=True).incomplete)

    def test_unbraced_operation_boundaries_with_and_without_semicolons(self):
        for statement in ('UPDATE dbo.A SET Qty=2', 'DELETE FROM dbo.A', 'INSERT dbo.A SELECT 1 UNION ALL SELECT 2',
                          'SELECT 1 AS X INTO dbo.T'):
            original = procedure("IF @m='EDIT' SELECT 1\n" + statement)
            changed = procedure("IF @m='EDIT' BEGIN SELECT 1\n" + statement + " END")
            events = check_sql(changed, original=original, compare_original=False, review_sp_changes=True).issues
            self.assertTrue(any(e.code == 'sp_operation_change_review' and e.details['operation'] == 'write' for e in events), statement)
        original = procedure("IF @m='X' SELECT 1; EXEC dbo.LogUse;")
        result = check_sql(original.replace('; EXEC', '; ELSE EXEC'), original=original, compare_original=False, review_sp_changes=True)
        self.assertTrue(any(i.details and i.details.get('guards') == ["ELSE (@M IN ('X'))"] for i in result.issues))

    def test_other_branch_and_shortened_source_cannot_clear_a_changed_contract(self):
        query = 'SELECT SUM(A.N) AS Qty FROM A;'
        cast = query.replace('SUM(A.N)', 'CAST(SUM(A.N) AS DECIMAL(18,4))')
        original = procedure(f"IF @m = 'R' BEGIN {query} END ELSE BEGIN {cast} EXEC dbo.LogUse; END")
        candidate = procedure(f"IF @m = 'R' BEGIN {cast} END ELSE BEGIN {cast} END EXEC dbo.LogUse; SELECT 1 AS X INTO dbo.NewTable;")
        changed = check_sql(candidate, original=original, compare_original=False, review_sp_changes=True)
        self.assertEqual(1, sum(item.code == 'sp_output_type_change_review' for item in changed.issues))
        self.assertEqual({'DBO.LOGUSE', 'SELECT INTO DBO.NEWTABLE'}, {item.details['name'] for item in changed.issues
                         if item.code == 'sp_operation_change_review'})
        truncated = 'CREATE PROC dbo.Example AS'
        self.assertTrue(check_sql(procedure(query), original=truncated, compare_original=False, review_sp_changes=True).incomplete)
