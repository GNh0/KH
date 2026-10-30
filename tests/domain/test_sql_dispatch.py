import unittest

from src.sql.checks import check_sql


REPEATED = """IF @Mode = 'LIST'
BEGIN
    SELECT 0;
END
ELSE IF @Mode IN ('READ', 'EXPORT')
BEGIN
    SELECT CASE WHEN FLAG = 1 THEN 1 ELSE 0 END AS VALUE FROM ITEMS;
    IF @Mode IN ('READ', 'EXPORT')
    BEGIN
        SELECT CODE FROM CODES;
    END
END"""


def findings(source, original=None):
    return [issue for issue in check_sql(source, original=original, check_style=False,
                                         check_preferences=False).issues
            if issue.code == 'repeated_enclosing_mode_guard']


class SqlDispatchTests(unittest.TestCase):
    def test_same_mode_guard_inside_its_proven_branch_is_reported(self):
        result = findings(REPEATED)
        self.assertEqual(1, len(result))
        self.assertEqual(8, result[0].line)
        self.assertEqual(5, result[0].details['outer_line'])
        self.assertEqual('@Mode', result[0].details['parameter'])

    def test_rule_is_not_tied_to_worktype_name_or_literal_mode_values(self):
        source = "IF (@Action = 'UPDATE') BEGIN SELECT 1; IF (@Action = 'UPDATE') BEGIN SELECT 2; END END"
        self.assertEqual(1, len(findings(source)))

    def test_ordered_result_sets_in_one_branch_need_no_repeated_mode_guard(self):
        source = "IF @Mode IN ('READ','EXPORT') BEGIN SELECT 1; SELECT 2; END"
        self.assertFalse(findings(source))

    def test_distinct_business_conditions_and_sibling_phases_are_not_banned(self):
        for source in (
            "IF @Mode = 'READ' BEGIN IF @Process = '09' BEGIN SELECT 1; END END",
            "IF @Mode = 'READ' BEGIN SELECT 1; END IF @Mode = 'READ' BEGIN SELECT 2; END",
            "IF @Mode = 'READ' BEGIN IF @OtherMode = 'READ' BEGIN SELECT 2; END END",
        ):
            with self.subTest(source=source):
                self.assertFalse(findings(source))

    def test_changed_or_externally_assigned_mode_is_not_assumed_constant(self):
        for mutation in (
            "SET @Mode = 'OTHER';", "SELECT @Mode = VALUE FROM SETTINGS;",
            "SELECT @Other = (SELECT 1), @Mode = 'OTHER';", "SET @Mode += 'X';",
            "SET @mode = 'OTHER';", "SELECT @mode = VALUE FROM SETTINGS;",
            "EXEC dbo.ChangeMode @Mode OUTPUT;", "FETCH NEXT FROM C INTO @Mode;",
        ):
            with self.subTest(mutation=mutation):
                source = "IF @Mode = 'READ' BEGIN " + mutation + " IF @Mode = 'READ' BEGIN SELECT 2; END END"
                self.assertFalse(findings(source))

    def test_reads_and_writes_to_other_variables_do_not_hide_the_duplicate(self):
        for prefix in ("SELECT ID FROM T WHERE @Mode = 'READ';", "SET @Other = 1;", "SELECT @Other = 1;"):
            with self.subTest(prefix=prefix):
                source = "IF @Mode = 'READ' BEGIN " + prefix + " IF @Mode = 'READ' BEGIN SELECT 2; END END"
                self.assertEqual(1, len(findings(source)))

    def test_comments_strings_case_end_and_transactions_keep_block_context(self):
        source = """IF @Mode = 'READ'
BEGIN
    BEGIN TRANSACTION;
    SELECT 'IF @Mode = ''READ'' BEGIN END';
    SELECT CASE WHEN X = 1 THEN CASE WHEN Y = 2 THEN 3 ELSE 4 END ELSE 5 END FROM T;
    -- END IF @Mode = 'READ' BEGIN
    IF @Mode = 'READ' BEGIN SELECT 2; END
    COMMIT;
END"""
        self.assertEqual(1, len(findings(source)))

    def test_different_predicates_and_unknown_expressions_remain_manual_review(self):
        for source in (
            "IF @Mode = 'READ' BEGIN IF @Mode = 'EXPORT' BEGIN SELECT 1; END END",
            "IF EXISTS(SELECT 1 FROM T) BEGIN IF EXISTS(SELECT 1 FROM T) BEGIN SELECT 2; END END",
            "IF @Mode = 'READ' BEGIN IF @Mode = 'READ' AND @Flag = 1 BEGIN SELECT 2; END END",
        ):
            with self.subTest(source=source):
                self.assertFalse(findings(source))

    def test_original_can_limit_local_review_but_standalone_still_finds_it(self):
        self.assertFalse(findings(REPEATED, original=REPEATED))
        self.assertTrue(findings(REPEATED))

    def test_loop_reentry_and_jumps_do_not_prove_the_outer_condition_still_holds(self):
        for source in (
            "IF @Mode = 'READ' BEGIN WHILE @More = 1 BEGIN IF @Mode = 'READ' BEGIN SELECT 1; END SET @Mode = 'OTHER'; END END",
            "GOTO Inside; IF @Mode = 'READ' BEGIN Inside: IF @Mode = 'READ' BEGIN SELECT 1; END END",
        ):
            with self.subTest(source=source):
                self.assertFalse(findings(source))
        checked_each_iteration = "WHILE @More = 1 BEGIN IF @Mode = 'READ' BEGIN IF @Mode = 'READ' BEGIN SELECT 1; END END END"
        self.assertEqual(1, len(findings(checked_each_iteration)))


if __name__ == '__main__':
    unittest.main()
