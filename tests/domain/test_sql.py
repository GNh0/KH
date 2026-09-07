import unittest
from src.sql.aliases import describe_sources, rename_aliases
from src.sql.compare import compare_sql
from src.sql.checks import check_sql
from src.sql.layout import normalize_sql_join_layout


class SqlPreservationTests(unittest.TestCase):
    def test_alias_references_rename_with_source(self):
        before = "SELECT X.ID, Y.NM FROM ORDERS X LEFT OUTER JOIN ITEMS Y ON X.ID = Y.ID WHERE X.ACTIVE = 'Y'"
        scope = describe_sources(before)[0]['scope_id']
        after = rename_aliases(before, {scope: {'X': 'A', 'Y': 'B'}})
        self.assertIn('ON A.ID = B.ID', after)
        self.assertTrue(compare_sql(before, after).success)
        self.assertFalse(compare_sql(before, after, preserve_aliases=True).success)

    def test_correlated_scope_references(self):
        before = "SELECT X.ID FROM ORDERS X WHERE EXISTS (SELECT 1 FROM ITEMS T WHERE T.ID = X.ID)"
        scopes = describe_sources(before)
        after = rename_aliases(before, {scopes[0]['scope_id']: {'X': 'A'}})
        self.assertIn('T.ID = A.ID', after)
        self.assertIn('FROM ITEMS T', after)
        self.assertTrue(compare_sql(before, after).success)

    def test_shadowed_alias_is_not_renamed(self):
        before = "SELECT X.ID FROM ORDERS X WHERE EXISTS (SELECT 1 FROM ITEMS X WHERE X.ID = 2)"
        scope = describe_sources(before)[0]['scope_id']
        after = rename_aliases(before, {scope: {'X': 'A'}})
        self.assertIn('FROM ITEMS X WHERE X.ID = 2', after)

    def test_role_family_does_not_depend_on_physical_table(self):
        before = "SELECT X.ID, Y.NM, Z.NM FROM ORDERS X JOIN ITEMS Y ON X.ID=Y.ID JOIN CUSTOMERS Z ON X.CUST=Z.ID"
        scope = describe_sources(before)[0]['scope_id']
        after = rename_aliases(before, {scope: {'X': 'A', 'Y': 'B1', 'Z': 'B2'}})
        self.assertTrue(compare_sql(before, after).success)

    def test_source_alias_as_is_optional_but_column_alias_is_preserved(self):
        self.assertTrue(compare_sql('SELECT A.ID AS IDENT FROM ITEMS AS A', 'SELECT A.ID AS IDENT FROM ITEMS A', preserve_aliases=True).success)
        self.assertFalse(compare_sql('SELECT A.ID AS IDENT FROM ITEMS A', 'SELECT A.ID AS NAME FROM ITEMS A').success)

    def test_missing_reference_rename_fails(self):
        self.assertFalse(compare_sql('SELECT X.ID FROM ITEMS X', 'SELECT X.ID FROM ITEMS A').success)

    def test_dml_alias_targets(self):
        before = 'UPDATE X SET X.QTY=1 FROM ITEMS X WHERE X.ID=2'
        scope = describe_sources(before)[0]['scope_id']
        after = rename_aliases(before, {scope: {'X': 'A'}})
        self.assertTrue(after.startswith('UPDATE A SET A.QTY'))
        self.assertTrue(compare_sql(before, after).success)

    def test_alias_collision_is_rejected(self):
        before = 'SELECT X.ID FROM ITEMS X JOIN ITEMS Y ON X.ID=Y.ID'
        scope = describe_sources(before)[0]['scope_id']
        with self.assertRaises(ValueError):
            rename_aliases(before, {scope: {'X': 'Y'}})

    def test_literals_comments_and_join_kind_are_preserved(self):
        before = "SELECT N'한글', 'JOIN X' /* 설명 */ FROM ITEMS A LEFT OUTER JOIN ITEMS B ON A.ID=B.ID"
        for candidate in [before.replace('한글', '수정'), before.replace('설명', '삭제'), before.replace('LEFT OUTER', 'INNER')]:
            with self.subTest(candidate=candidate):
                self.assertFalse(compare_sql(before, candidate).success)

    def test_join_and_exists_layout_changes_whitespace_only(self):
        before = 'SELECT A.ID\nFROM ITEMS A\nLEFT OUTER JOIN PARTS B\nON A.ID=B.ID\nAND B.ID BETWEEN 1 AND 10\nWHERE EXISTS (\nSELECT 1 FROM STOCK T\nWHERE T.ID=A.ID\n)'
        after = normalize_sql_join_layout(before)
        self.assertTrue(compare_sql(before, after).success)
        self.assertEqual(after, normalize_sql_join_layout(after))

    def test_preserve_alias_mode_does_not_warn_about_alias_names(self):
        result = check_sql('SELECT TT.ID FROM ITEMS TT', original='SELECT TT.ID FROM ITEMS TT', preserve_aliases=True)
        self.assertFalse(any('alias' in i.code for i in result.issues))

    def test_prefers_direct_flow_without_global_temp_table_failure(self):
        result = check_sql('DECLARE @TMP TABLE (ID INT); INSERT INTO @TMP (ID) VALUES (1)')
        self.assertTrue(result.success)
        self.assertTrue(any(i.code == 'intermediate_table_preference' and i.severity == 'warning' for i in result.issues))

    def test_invalid_lexical_input_does_not_pass(self):
        self.assertFalse(check_sql("SELECT 'unterminated").success)

    def test_insert_value_order_cannot_pass_as_formatting(self):
        self.assertFalse(compare_sql('INSERT INTO T(A,B) SELECT 1,2', 'INSERT INTO T(A,B) SELECT 2,1').success)

    def test_declared_delta_differs_from_whole_replace(self):
        bad = "DELETE A FROM TARGET A JOIN @TMP B ON A.ID=B.ID; INSERT INTO TARGET(ID) SELECT ID FROM @TMP"
        good = "DELETE A FROM TARGET A JOIN @TMP B ON A.ID=B.ID WHERE B.GBN='DEL'; INSERT INTO TARGET(ID) SELECT ID FROM @TMP WHERE GBN='NEW'"
        self.assertTrue(any(i.code == 'review_full_replace' for i in check_sql(bad, check_delta=True).issues))
        self.assertFalse(any(i.code == 'review_full_replace' for i in check_sql(good, check_delta=True).issues))


if __name__ == '__main__':
    unittest.main()
