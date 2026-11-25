"""Added backup-procedure calls and redundant numeric conversions, with false-positive traps."""
import unittest

from src.sql.checks import check_sql

BASE = """SELECT A.DOCNUM
     , A.PRICE
FROM TB_HEADER A
"""


def codes(candidate: str, original: str = BASE) -> list[str]:
    return [issue.code for issue in check_sql(candidate, original=original).issues]


class BackupProcedureTests(unittest.TestCase):
    def test_new_bak_call_is_an_error(self):
        result = check_sql(original=BASE, candidate='EXEC dbo.sp_ORDER_SAVE_BAK @ORGDIV = @ORGDIV\n' + BASE)
        found = [i for i in result.issues if i.code == 'backup_procedure_call']
        self.assertEqual(['error'], [i.severity for i in found])
        self.assertEqual('dbo.sp_ORDER_SAVE_BAK', found[0].details['procedure'])

    def test_return_status_bracketed_and_dated_backups(self):
        self.assertIn('backup_procedure_call', codes('EXEC @RET = [dbo].[sp_X_BAK]\n' + BASE))
        self.assertIn('backup_procedure_call', codes('EXECUTE sp_X_BAK_20261118\n' + BASE))
        self.assertIn('backup_procedure_call', codes('EXEC sp_X_BAK2\n' + BASE))

    def test_not_a_backup_call(self):
        for text in ("PRINT 'EXEC sp_X_BAK'\n", '-- EXEC sp_X_BAK\n', 'EXEC sp_BAKERY_LIST\n',
                     'EXEC sp_X_BAKE\n', "EXEC ('sp_X_BAK')\n", 'SELECT * FROM TB_ORDER_BAK\n'):
            self.assertNotIn('backup_procedure_call', codes(text + BASE), text)

    def test_existing_call_is_not_reported_again(self):
        original = 'EXEC dbo.sp_X_BAK\n' + BASE
        self.assertNotIn('backup_procedure_call', codes(original.replace('A.PRICE', 'A.PRICE2'), original))


class RedundantConversionTests(unittest.TestCase):
    def test_direct_nesting_is_reviewed(self):
        for wrapped in ('CONVERT(NUMERIC(18, 4), CONVERT(NUMERIC(18,4), A.PRICE))',
                        'CAST(CAST(A.PRICE AS DECIMAL(18, 4)) AS NUMERIC(18, 4))',
                        'CONVERT(NUMERIC(18, 4), CAST(A.PRICE AS NUMERIC(18, 4)))'):
            self.assertIn('redundant_numeric_convert_review', codes(BASE.replace('A.PRICE', wrapped + ' AS PRICE')), wrapped)

    def test_type_change_or_arithmetic_is_not_redundant(self):
        for wrapped in ('CONVERT(NUMERIC(18, 2), CONVERT(NUMERIC(18, 4), A.PRICE))',
                        'CONVERT(NUMERIC(18, 4), CONVERT(NUMERIC(18, 4), A.PRICE) * A.QTY)',
                        'CONVERT(NUMERIC(18, 4), SUM(CONVERT(NUMERIC(18, 4), A.PRICE)))',
                        'CONVERT(NUMERIC(18, 4), CONVERT(VARCHAR(20), A.PRICE))',
                        'CONVERT(NUMERIC(18, 4), A.PRICE)'):
            self.assertNotIn('redundant_numeric_convert_review', codes(BASE.replace('A.PRICE', wrapped + ' AS PRICE')), wrapped)


if __name__ == '__main__':
    unittest.main()
