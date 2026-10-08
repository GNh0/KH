import unittest

from src.sql.checks import check_sql
from src.sql.compare import compare_sql
from src.sql.layout import normalize_sql_join_layout


BEFORE = '''    INSERT INTO TARGET
    (
        ID , VERY_LONG_FIELD , C , D
       , E , F , G , H
    )
    SELECT @ID , @A , @COLUMN , @D
         , @E , @F , @G , @H
    FROM SOURCE A
'''

EXPECTED = '''    INSERT INTO TARGET
    (
           ID  , VERY_LONG_FIELD , C       , D
         , E   , F               , G       , H
    )
    SELECT @ID , @A              , @COLUMN , @D
         , @E  , @F              , @G      , @H
    FROM SOURCE A
'''


def alignment_codes(sql):
    return {issue.code for issue in check_sql(sql).issues
            if issue.code.startswith('insert_select_') or issue.code == 'tab_indentation_not_allowed'}


class SqlTextColumnTests(unittest.TestCase):
    def assert_preserved(self, before, after):
        self.assertTrue(compare_sql(before, after, preserve_aliases=True).success)
        self.assertEqual(after, normalize_sql_join_layout(after))

    def test_short_and_long_items_use_shared_actual_columns(self):
        self.assertIn('insert_select_column_alignment_invalid', alignment_codes(BEFORE))
        after = normalize_sql_join_layout(BEFORE)
        self.assertEqual(EXPECTED, after)
        self.assertNotIn('insert_select_column_alignment_invalid', alignment_codes(after))
        self.assert_preserved(BEFORE, after)

    def test_equal_internal_tab_counts_do_not_establish_alignment(self):
        before = BEFORE.replace(' , ', '\t,\t')
        self.assertIn('tab_indentation_not_allowed', alignment_codes(before))
        self.assertIn('insert_select_column_alignment_invalid', alignment_codes(before))
        after = normalize_sql_join_layout(before)
        self.assertNotIn('\t', after)
        self.assertNotIn('insert_select_column_alignment_invalid', alignment_codes(after))
        self.assert_preserved(before, after)

    def test_already_aligned_roomier_columns_are_preserved(self):
        before = '''    INSERT INTO TARGET
    (
           ID       , VERY_LONG_FIELD      , C           , D
         , E        , F                    , G           , H
    )
    SELECT @ID      , @A                   , @COLUMN     , @D
         , @E       , @F                   , @G          , @H
    FROM SOURCE A
'''
        self.assertNotIn('insert_select_column_alignment_invalid', alignment_codes(before))
        self.assertEqual(before, normalize_sql_join_layout(before))

    def test_layout_tabs_expand_without_touching_literals_comments_or_identifiers(self):
        before = 'SELECT\tN\'한\t글\', [I\tD], "N\tM" FROM ITEMS A -- 설명\t유지\n/*\n\t내용\n*/\n'
        after = normalize_sql_join_layout(before)
        self.assertTrue(after.startswith('SELECT  N'))
        for content in ("N'한\t글'", '[I\tD]', '"N\tM"', '-- 설명\t유지', '/*\n\t내용\n*/'):
            self.assertIn(content, after)
        self.assertNotIn('tab_indentation_not_allowed', alignment_codes(after))
        self.assert_preserved(before, after)

    def test_nested_joins_use_token_columns_after_tab_expansion(self):
        before = '''\tSELECT A.ID
\tFROM\t(
\t\tSELECT T.ID
\t\tFROM ITEMS T
\t\tLEFT OUTER\tJOIN PARTS TA1
\t\tON T.ID = TA1.ID
\t) A
'''
        after = normalize_sql_join_layout(before)
        self.assertNotIn('\t', after)
        lines = after.splitlines()
        self.assertEqual(lines[1].index('('), lines[-1].index(')'))
        join = next(line for line in lines if 'JOIN PARTS' in line)
        predicate = next(line for line in lines if line.lstrip().startswith('ON '))
        self.assertEqual(join.index('JOIN') + 2, predicate.index('ON'))
        self.assert_preserved(before, after)

    def test_wide_literal_padding_uses_text_width_and_preserves_value(self):
        before = BEFORE.replace('@ID', "N'한글'")
        after = normalize_sql_join_layout(before)
        self.assertIn('ID      , VERY_LONG_FIELD', after)
        self.assertIn("SELECT N'한글' , @A", after)
        self.assertNotIn('insert_select_column_alignment_invalid', alignment_codes(after))
        self.assert_preserved(before, after)

    def test_row_group_mismatch_remains_explicitly_unverified(self):
        before = BEFORE.replace('SELECT @ID , @A , @COLUMN , @D\n         , @E',
                                'SELECT @ID , @A , @COLUMN\n         , @D , @E')
        result = check_sql(before)
        self.assertIn('insert_select_alignment_unverified', {issue.code for issue in result.issues})
        self.assertTrue(any('unsupported horizontal' in item for item in result.not_checked))
        self.assertEqual(before, normalize_sql_join_layout(before))

    def test_multiline_expressions_are_preserved_and_unverified(self):
        before = BEFORE.replace('@COLUMN', 'COALESCE(\n                @C, @DEFAULT)')
        self.assertIn('insert_select_alignment_unverified', alignment_codes(before))
        self.assertEqual(before, normalize_sql_join_layout(before))

    def test_comments_in_both_mapping_lists_are_preserved_and_unverified(self):
        before = BEFORE.replace('VERY_LONG_FIELD', 'VERY_LONG_FIELD /* 컬럼\t유지 */').replace('@COLUMN', '@COLUMN /* 값\t유지 */')
        self.assertIn('insert_select_alignment_unverified', alignment_codes(before))
        self.assertNotIn('tab_indentation_not_allowed', alignment_codes(before))
        self.assertEqual(before, normalize_sql_join_layout(before))

    def test_select_modifiers_do_not_become_first_mapped_values(self):
        for modifier in ('DISTINCT ', 'TOP (10) ', 'ALL '):
            with self.subTest(modifier=modifier):
                before = BEFORE.replace('SELECT @ID', 'SELECT ' + modifier + '@ID')
                self.assertIn('insert_select_alignment_unverified', alignment_codes(before))
                self.assertEqual(before, normalize_sql_join_layout(before))

    def test_multiple_statements_and_crlf_preserve_tokens_and_line_endings(self):
        before = (BEFORE + ';\n' + BEFORE.replace('TARGET', 'OTHER_TARGET')).replace('\n', '\r\n')
        after = normalize_sql_join_layout(before)
        self.assertEqual(2, after.count('ID  , VERY_LONG_FIELD'))
        self.assertNotIn('\n', after.replace('\r\n', ''))
        self.assertNotIn('insert_select_column_alignment_invalid', alignment_codes(after))
        self.assert_preserved(before, after)

    def test_ordinary_sql_tabs_are_reviewed_even_without_insert(self):
        self.assertIn('tab_indentation_not_allowed', alignment_codes('SELECT A.ID\t, A.QTY FROM ITEMS A'))
        self.assertNotIn('tab_indentation_not_allowed', alignment_codes("SELECT '\t' FROM ITEMS A --\tcomment"))

    def test_unicode_literal_sql_text_does_not_create_an_insert_mapping(self):
        before = "SELECT N'INSERT INTO FAKE (A, B, C, D, E, F, G, H)\nSELECT\t1, 2, 3, 4, 5, 6, 7, 8';"
        self.assertEqual(before, normalize_sql_join_layout(before))
        self.assertFalse(any(code.startswith('insert_select_') for code in alignment_codes(before)))

    def test_reported_qc165t_groups_share_columns_despite_different_name_lengths(self):
        target_rows = (
            ('ORGDIV', 'PRODDATE', 'ITEMCD', 'LOTNUM', 'PRODMAC'),
            ('PROCD', 'SEQ', 'CHKCODE', 'CHKNAME', 'CHKDESC'),
            ('REFVALUE', 'REFUPVALUE', 'REFLOWVALUE', 'CHKMETHOD'),
            ('IPVAL1', 'IPVAL2', 'IPVAL3', 'IQVAL'),
            ('MPVAL1', 'MPVAL2', 'MPVAL3', 'MQVAL'),
            ('FPVAL1', 'FPVAL2', 'FPVAL3', 'FQVAL'),
            ('REGDT', 'REGEMPNO', 'REGIP'),
        )
        value_rows = (
            ('@ORGDIV', '@PRODDATE', '@ITEMCD', '@LOTNUM', '@PRODMAC'),
            ('@PROCD', 'A.SEQ', 'A.CHKCODE', 'A.CHKNAME', 'A.CHKDESC'),
            ('A.REFVALUE', 'A.REFUPVALUE', 'A.REFLOWVALUE', 'A.CHKMETHOD'),
            ('B.IPVAL1', 'B.IPVAL2', 'B.IPVAL3', 'B.IQVAL'),
            ('B.MPVAL1', 'B.MPVAL2', 'B.MPVAL3', 'B.MQVAL'),
            ('B.FPVAL1', 'B.FPVAL2', 'B.FPVAL3', 'B.FQVAL'),
            ('GETDATE()', '@USERID', '@USERIP'),
        )
        target_lines = [('    ' if n == 0 else '   , ') + '\t,\t'.join(row) for n, row in enumerate(target_rows)]
        value_lines = [('SELECT ' if n == 0 else '     , ') + '\t,\t'.join(row) for n, row in enumerate(value_rows)]
        before = 'INSERT INTO QC165T\n(\n' + '\n'.join(target_lines) + '\n)\n' + '\n'.join(value_lines) + '\nFROM QC155T A\n'
        after = normalize_sql_join_layout(before)
        lines = after.splitlines()
        target_positions = [tuple(line.index(field) for field in row) for line, row in zip(lines[2:9], target_rows)]
        value_positions = [tuple(line.index(field) for field in row) for line, row in zip(lines[10:17], value_rows)]
        self.assertEqual(target_positions, value_positions)
        for n in range(5):
            self.assertEqual(1, len({positions[n] for positions in target_positions if n < len(positions)}))
        self.assertNotIn('\t', after)
        self.assertNotIn('insert_select_column_alignment_invalid', alignment_codes(after))
        self.assert_preserved(before, after)

    def test_short_inline_values_and_unsupported_values_clause_are_not_reformatted(self):
        for before in ('INSERT INTO TARGET (A, B) SELECT 1, 2;',
                       'INSERT INTO TARGET (A, B, C, D, E, F, G, H) VALUES (1, 2, 3, 4, 5, 6, 7, 8);'):
            with self.subTest(before=before):
                self.assertEqual(before, normalize_sql_join_layout(before))
                self.assertNotIn('insert_select_column_alignment_invalid', alignment_codes(before))


if __name__ == '__main__':
    unittest.main()
