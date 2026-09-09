import unittest

from src.sql.checks import check_sql
from src.sql.compare import compare_sql
from src.sql.layout import normalize_sql_join_layout


JOIN_BEFORE = """    SELECT A.ID
    FROM ORDERS A
            LEFT OUTER JOIN (
                SELECT T.ID
                     , SUM(T.QTY) AS QTY
                FROM WORK_LOG T
                GROUP BY T.ID
            ) B
                             ON A.ID = B.ID
                            AND A.QTY = B.QTY
"""
JOIN_EXPECTED = """    SELECT A.ID
    FROM ORDERS A
            LEFT OUTER JOIN (
                             SELECT T.ID
                                  , SUM(T.QTY) AS QTY
                             FROM WORK_LOG T
                             GROUP BY T.ID
                            ) B
                            ON A.ID = B.ID
                            AND A.QTY = B.QTY
"""

NESTED_BEFORE = """    SELECT A.PERIOD
    FROM (
        SELECT T.PERIOD
             , SUM(T.QTY) AS QTY
        FROM (
            SELECT T.PERIOD
                 , T.QTY
            FROM HISTORY T
                    LEFT OUTER JOIN ITEMS TA1
                                 ON T.ITEMCD = TA1.ITEMCD
            WHERE T.QTY <> 0
                AND T.ACTIVE = 'Y'
            GROUP BY T.PERIOD, T.QTY

            UNION ALL

            SELECT T.PERIOD
                 , T.QTY
            FROM ORDERS T
                    LEFT OUTER JOIN ITEMS TA1
                                 ON T.ITEMCD = TA1.ITEMCD
            WHERE T.QTY <> 0
                AND T.ACTIVE = 'Y'
            GROUP BY T.PERIOD, T.QTY
        ) T
        GROUP BY T.PERIOD
    ) A
    ORDER BY A.PERIOD
"""
NESTED_EXPECTED = """    SELECT A.PERIOD
    FROM (
          SELECT T.PERIOD
               , SUM(T.QTY) AS QTY
          FROM (
                SELECT T.PERIOD
                     , T.QTY
                FROM HISTORY T
                        LEFT OUTER JOIN ITEMS TA1
                                     ON T.ITEMCD = TA1.ITEMCD
                WHERE T.QTY <> 0
                    AND T.ACTIVE = 'Y'
                GROUP BY T.PERIOD, T.QTY

                UNION ALL

                SELECT T.PERIOD
                     , T.QTY
                FROM ORDERS T
                        LEFT OUTER JOIN ITEMS TA1
                                     ON T.ITEMCD = TA1.ITEMCD
                WHERE T.QTY <> 0
                    AND T.ACTIVE = 'Y'
                GROUP BY T.PERIOD, T.QTY
               ) T
          GROUP BY T.PERIOD
         ) A
    ORDER BY A.PERIOD
"""


class DerivedQueryLayoutTests(unittest.TestCase):
    def assert_preserved_and_stable(self, before, after):
        self.assertTrue(compare_sql(before, after, preserve_aliases=True).success)
        self.assertEqual(after, normalize_sql_join_layout(after))

    def test_derived_join_parentheses_and_predicates_share_the_open_column(self):
        after = normalize_sql_join_layout(JOIN_BEFORE)
        self.assertEqual(JOIN_EXPECTED, after)
        self.assert_preserved_and_stable(JOIN_BEFORE, after)
        self.assertEqual([], check_sql(after, original=JOIN_BEFORE, preserve_aliases=True).issues)

    def test_nested_from_union_branches_and_continuations_follow_each_open(self):
        after = normalize_sql_join_layout(NESTED_BEFORE)
        self.assertEqual(NESTED_EXPECTED, after)
        self.assert_preserved_and_stable(NESTED_BEFORE, after)
        self.assertEqual([], check_sql(after, original=NESTED_BEFORE, preserve_aliases=True).issues)

    def test_checker_flags_the_old_derived_join_contract(self):
        codes = {i.code for i in check_sql(JOIN_BEFORE, original=JOIN_BEFORE).issues}
        self.assertTrue({
            'derived_join_closing_alias_indentation_invalid',
            'derived_query_clause_indentation_invalid',
            'join_predicate_alignment_invalid',
        } <= codes)

    def test_checker_includes_first_from_source_without_an_outer_join(self):
        codes = {i.code for i in check_sql(NESTED_BEFORE, original=NESTED_BEFORE).issues}
        self.assertIn('derived_join_closing_alias_indentation_invalid', codes)
        self.assertIn('derived_query_clause_indentation_invalid', codes)

    def test_each_clause_moves_its_own_continuations(self):
        before = NESTED_BEFORE.replace('        GROUP BY T.PERIOD', '  GROUP BY T.PERIOD')
        after = normalize_sql_join_layout(before)
        self.assertEqual(NESTED_EXPECTED, after)
        self.assert_preserved_and_stable(before, after)

    def test_nested_exists_derived_from_and_joins_remain_stable(self):
        before = """SELECT A.ID
FROM ORDERS A
LEFT OUTER JOIN (
SELECT T.ID FROM ITEMS T
) B
ON A.ID = B.ID
AND EXISTS (
SELECT 1
FROM (
SELECT T.ID
FROM ITEMS T
LEFT OUTER JOIN STOCK T1
ON T.ID = T1.ID
) X
LEFT OUTER JOIN STOCK Y
ON X.ID = Y.ID
WHERE X.ID = A.ID
)
"""
        after = normalize_sql_join_layout(before)
        self.assert_preserved_and_stable(before, after)
        bad = [i for i in check_sql(after, original=before, preserve_aliases=True).issues
               if 'indentation' in i.code or 'alignment' in i.code]
        self.assertEqual([], bad)

    def test_comments_and_multiline_literals_are_not_reindented_internally(self):
        before = """SELECT A.ID
FROM (
SELECT T.ID
     , N'한글 (
  SELECT value
 )' AS NOTE
/* 설명 (
   FROM unchanged
 ) */
FROM ITEMS T
WHERE T.CODE = 'ON AND )'
) A
"""
        after = normalize_sql_join_layout(before)
        self.assertIn("N'한글 (\n  SELECT value\n )'", after)
        self.assertIn("/* 설명 (\n   FROM unchanged\n ) */", after)
        self.assert_preserved_and_stable(before, after)

    def test_derived_join_between_case_and_or_ownership(self):
        before = JOIN_BEFORE.replace(
            '                            AND A.QTY = B.QTY',
            """AND B.QTY BETWEEN 1
      AND 10
OR (CASE WHEN A.QTY = 1
    AND B.QTY = 2 THEN 1 ELSE 0 END) = 1
AND A.QTY = B.QTY""")
        after = normalize_sql_join_layout(before)
        self.assertIn('                            AND B.QTY BETWEEN 1\n      AND 10', after)
        self.assertIn('                            OR (CASE', after)
        self.assertIn('    AND B.QTY = 2 THEN', after)
        self.assertIn('                            AND A.QTY = B.QTY', after)
        self.assert_preserved_and_stable(before, after)

    def test_inline_derived_clauses_split_only_at_whitespace_boundaries(self):
        before = "SELECT A.ID\nFROM (SELECT T.ID FROM ITEMS T WHERE T.ID > 0) A\n"
        expected = "SELECT A.ID\nFROM (\n      SELECT T.ID\n      FROM ITEMS T\n      WHERE T.ID > 0\n     ) A\n"
        after = normalize_sql_join_layout(before)
        self.assertEqual(expected, after)
        self.assert_preserved_and_stable(before, after)

    def test_ordinary_join_uses_join_i_column(self):
        before = "SELECT A.ID\nFROM ORDERS A\nLEFT OUTER JOIN ITEMS B\nON A.ID = B.ID\nAND B.QTY > 0\n"
        after = normalize_sql_join_layout(before)
        self.assertIn('        LEFT OUTER JOIN ITEMS B\n                     ON', after)
        self.assertIn('\n                     AND', after)
        self.assert_preserved_and_stable(before, after)

    def test_apply_and_function_parentheses_do_not_inherit_prior_join(self):
        before = """SELECT A.ID
FROM ORDERS A
        LEFT OUTER JOIN ITEMS B
                     ON A.ID = B.ID
        OUTER APPLY (SELECT CONVERT(INT, A.QTY) AS QTY) C
"""
        self.assertEqual(before, normalize_sql_join_layout(before))
        codes = {i.code for i in check_sql(before, original=before).issues}
        self.assertNotIn('derived_join_closing_alias_indentation_invalid', codes)
        self.assertNotIn('join_predicate_alignment_invalid', codes)

    def test_unterminated_sql_is_not_rewritten(self):
        with self.assertRaises(ValueError):
            normalize_sql_join_layout("SELECT A.ID FROM (SELECT 'broken) A")


if __name__ == '__main__':
    unittest.main()
