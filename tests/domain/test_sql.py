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

    def test_new_locking_hints_are_reviewed_without_becoming_errors(self):
        source = 'SELECT MAX(A.SEQ) FROM TARGET A WITH (UPDLOCK, HOLDLOCK)'
        result = check_sql(source, check_style=False)
        self.assertTrue(result.success)
        self.assertEqual({'UPDLOCK', 'HOLDLOCK'}, {i.details['hint'] for i in result.issues if i.code == 'locking_hint_review'})
        self.assertNotIn('locking_hint_review', {i.code for i in check_sql(source, original=source).issues})

    def test_literal_or_commented_hints_are_not_executable_hints(self):
        source = "SELECT 'WITH (UPDLOCK, HOLDLOCK)' FROM TARGET A /* WITH (UPDLOCK) */"
        self.assertNotIn('locking_hint_review', {i.code for i in check_sql(source, check_style=False).issues})

    def test_typed_empty_result_placeholders_are_reviewed_without_a_blanket_cast_rule(self):
        source = "SELECT CAST('' AS VARCHAR(30)) AS OLD_FIELD, CAST(NULL AS DATE) AS OLD_DATE FROM TARGET A"
        result = check_sql(source, check_style=False)
        self.assertEqual(2, sum(i.code == 'synthetic_result_field_review' for i in result.issues))
        self.assertTrue(result.success)
        self.assertNotIn('synthetic_result_field_review', {i.code for i in check_sql(source, original=source, check_style=False).issues})
        for source in ["SELECT CAST(A.QTY AS DECIMAL(18, 4)) FROM TARGET A", "SELECT CAST('20260101' AS DATE)", "SELECT 'CAST(NULL AS DATE)'", "SELECT CAST(NULL AS DATE)"]:
            self.assertNotIn('synthetic_result_field_review', {i.code for i in check_sql(source, check_style=False).issues})


class WhereSubqueryReviewTests(unittest.TestCase):
    def findings(self, source, **kwargs):
        return [issue for issue in check_sql(source, check_style=False, **kwargs).issues
                if issue.code == 'subquery_preference']

    def test_where_exists_inside_save_validation_is_reviewed(self):
        source = '''IF EXISTS (
            SELECT 1 FROM PLANS A
            WHERE A.QTY > 0 AND EXISTS (
                SELECT 1 FROM CHANGED T WHERE T.ID = A.ID
            )
        ) BEGIN RAISERROR('invalid', 16, 1); RETURN; END'''
        found = self.findings(source)
        self.assertEqual(1, len(found))
        self.assertEqual({'EXISTS': 1}, found[0].details['added_where_subqueries'])
        self.assertEqual('warning', found[0].severity)

    def test_direct_save_validation_is_not_a_where_subquery(self):
        for prefix in ['IF', 'IF @MODE = 1 AND NOT', 'WHILE NOT']:
            with self.subTest(prefix=prefix):
                self.assertEqual([], self.findings(prefix +
                    " EXISTS (SELECT 1 FROM PLANS A WHERE A.QTY > 0) BEGIN RETURN; END"))

    def test_positive_negative_in_and_parenthesized_predicates(self):
        source = '''SELECT A.ID FROM ITEMS A WHERE (
            EXISTS (SELECT 1 FROM PARTS T WHERE T.ID = A.ID)
            OR NOT EXISTS (SELECT 1 FROM STOCK T WHERE T.ID = A.ID)
        ) AND A.ID IN (SELECT T.ID FROM ORDERS T)'''
        self.assertEqual({'EXISTS': 2, 'IN': 1},
            self.findings(source)[0].details['added_where_subqueries'])

    def test_prior_where_does_not_leak_into_later_if_or_join(self):
        source = '''SELECT A.ID FROM ITEMS A WHERE A.ID = 1
        IF @MODE = 1 AND EXISTS (SELECT 1 FROM PLANS T WHERE T.QTY > 0) RETURN
        SELECT A.ID FROM ITEMS A INNER JOIN PARTS B
            ON A.ID = B.ID AND EXISTS (SELECT 1 FROM STOCK T WHERE T.ID = B.ID)'''
        self.assertEqual([], self.findings(source))

    def test_inner_where_is_reviewed_inside_derived_source(self):
        source = '''SELECT A.ID FROM (
            SELECT T.ID FROM ITEMS T WHERE T.ID IN (SELECT T1.ID FROM PARTS T1)
        ) A'''
        self.assertEqual({'IN': 1}, self.findings(source)[0].details['added_where_subqueries'])

    def test_literals_comments_identifier_names_and_value_lists_are_not_queries(self):
        source = '''SELECT 'WHERE EXISTS (SELECT 1)', [WHERE], "EXISTS" FROM ITEMS A
        WHERE A.ID IN (1, 2) -- AND EXISTS (SELECT 1)
        AND A.VALUE = 'IN (SELECT 1)' /* WHERE NOT EXISTS (SELECT 1) */'''
        self.assertEqual([], self.findings(source))

    def test_existing_counts_and_company_preferences_are_preserved(self):
        source = 'SELECT A.ID FROM ITEMS A WHERE EXISTS (SELECT 1 FROM PARTS T WHERE T.ID = A.ID)'
        self.assertEqual([], self.findings(source, original=source))
        self.assertEqual([], self.findings(source, check_preferences=False))
        before = source.replace('WHERE EXISTS', 'WHERE NOT EXISTS')
        self.assertEqual([], self.findings(source, original=before))


class CteReviewTests(unittest.TestCase):
    def findings(self, source, **kwargs):
        return [issue for issue in check_sql(source, check_style=False, **kwargs).issues
                if issue.code == 'cte_preference']

    def test_cte_in_procedure_branch_is_reported_at_its_declaration(self):
        source = '''IF @WORKTYPE = 'LIST'
BEGIN
    ;WITH QTY AS (
        SELECT A.ID, SUM(A.QTY) AS QTY FROM RESULTS A GROUP BY A.ID
    )
    SELECT A.ID, A.QTY FROM QTY A;
END'''
        issue, = self.findings(source)
        self.assertEqual(('warning', 3, 'QTY'), (issue.severity, issue.line, issue.details['cte']))

    def test_added_declaration_in_existing_cte_list_is_reviewed(self):
        original = 'WITH PLAN AS (SELECT A.ID FROM PLANS A) SELECT A.ID FROM PLAN A;'
        candidate = '''WITH [Plan] AS (SELECT A.ID FROM PLANS A),
              [Ready] (ID) AS (SELECT A.ID FROM [Plan] A)
        SELECT A.ID FROM [Ready] A;'''
        self.assertEqual(['[Ready]'], [issue.details['cte'] for issue in self.findings(candidate, original=original)])
        self.assertEqual([], self.findings(candidate, check_preferences=False))

    def test_table_hints_and_protected_text_are_not_ctes(self):
        source = '''SELECT 'WITH S AS (SELECT 1)', [WITH] FROM ITEMS A WITH (NOLOCK)
        /* WITH S AS (SELECT 1) */
        FOR XML PATH('item');'''
        self.assertEqual([], self.findings(source))


class ExpressionSubqueryReviewTests(unittest.TestCase):
    def findings(self, source, **kwargs):
        return [issue for issue in check_sql(source, check_style=False, **kwargs).issues
                if issue.code == 'subquery_preference']

    def test_select_output_and_variable_assignment_queries_have_locations(self):
        source = '''SELECT A.ID
     , (SELECT T.NAME FROM ITEMS T WHERE T.ID = A.ID) AS NAME
FROM ORDERS A;
SELECT @ITEM = (
    SELECT T.ITEM FROM MACHINES T WHERE T.ID = @ID
);'''
        self.assertEqual([('SELECT', 2), ('SELECT', 5)],
                         [(i.details['clause'], i.line) for i in self.findings(source)])

    def test_scalar_where_and_case_expressions_are_reviewed(self):
        source = '''SELECT CASE WHEN A.ACTIVE = 1 THEN 0
                   ELSE (SELECT MAX(T.QTY) FROM RESULTS T) END AS QTY
FROM ITEMS A
WHERE (A.QTY > ISNULL((SELECT SUM(T.QTY) FROM PLANS T), 0))
  AND A.ID = ANY (SELECT T.ID FROM RESULTS T);'''
        self.assertEqual(['SELECT', 'WHERE', 'WHERE'],
                         [i.details['clause'] for i in self.findings(source)])

    def test_nested_queries_keep_their_own_clause(self):
        source = '''SELECT A.ID FROM (
    SELECT T.ID, (SELECT T1.NAME FROM NAMES T1 WHERE T1.ID = T.ID) AS NAME
    FROM ITEMS T
) A WHERE A.QTY > (SELECT MAX(T.QTY) FROM PLANS T);'''
        self.assertEqual(['SELECT', 'WHERE'], [i.details['clause'] for i in self.findings(source)])

    def test_join_sources_save_validations_and_protected_text_are_not_flagged(self):
        source = '''IF EXISTS (SELECT 1 FROM @TMP A JOIN ITEMS B ON A.ID = B.ID)
BEGIN
    SELECT A.ID, 'SELECT (SELECT 1)', [SELECT], "WHERE"
    FROM (SELECT T.ID FROM ITEMS T) A
    OUTER APPLY (SELECT MAX(T.QTY) AS QTY FROM PLANS T WHERE T.ID = A.ID) B
    LEFT JOIN RESULTS C ON C.ID = A.ID AND C.QTY = (SELECT MAX(T.QTY) FROM PLANS T)
    WHERE A.ID IN (1, 2); -- (SELECT 1)
END'''
        self.assertEqual([], self.findings(source))

    def test_existing_expressions_and_disabled_preferences_are_preserved(self):
        before = 'SELECT A.ID, (SELECT T.NAME FROM ITEMS T WHERE T.ID = A.ID) AS NAME FROM ORDERS A;'
        self.assertEqual([], self.findings(before, original=before))
        self.assertEqual([], self.findings(before, check_preferences=False))
        changed = before.replace('T.NAME', 'T.CODE')
        self.assertEqual(1, len(self.findings(changed, original=before)))

    def test_nested_select_has_its_own_leading_comma_check(self):
        good = '''SELECT A.ID
     , (SELECT T.CODE
             , T.NAME
        FROM ITEMS T
        WHERE T.ID = A.ID) AS ITEM
FROM ORDERS A;'''
        codes = lambda text: [i.code for i in check_sql(text, check_preferences=False).issues]
        self.assertNotIn('select_column_missing_leading_comma', codes(good))
        bad_inner = good.replace('             , T.NAME', '               T.NAME')
        self.assertIn('select_column_missing_leading_comma', codes(bad_inner))
        bad_outer = good.replace('FROM ORDERS A;', '       A.QTY\nFROM ORDERS A;')
        self.assertIn('select_column_missing_leading_comma', codes(bad_outer))

    def test_leading_comma_review_preserves_line_ending_support(self):
        for ending in ['\n', '\r\n', '\r']:
            with self.subTest(ending=repr(ending)):
                source = ending.join(['SELECT A.ID', '       A.NAME', 'FROM ITEMS A;'])
                self.assertIn('select_column_missing_leading_comma',
                              [i.code for i in check_sql(source).issues])

    def test_review_locations_match_each_supported_line_ending(self):
        for ending in ['\n', '\r\n', '\r']:
            with self.subTest(ending=repr(ending)):
                source = ending.join(['SELECT A.ID',
                    '     , (SELECT T.NAME FROM ITEMS T) AS NAME FROM ORDERS A;',
                    'WITH TOTAL AS (SELECT SUM(T.QTY) AS QTY FROM RESULTS T)',
                    'SELECT A.QTY FROM TOTAL A;'])
                result = check_sql(source, check_style=False)
                self.assertEqual([('subquery_preference', 2), ('cte_preference', 3)],
                    sorted([(i.code, i.line) for i in result.issues
                            if i.code in {'subquery_preference', 'cte_preference'}], key=lambda item: item[1] or 0))


if __name__ == '__main__':
    unittest.main()
