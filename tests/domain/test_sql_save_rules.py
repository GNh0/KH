"""Fixed SAVE rules: locking hints, WORKTYPE branch structure and count/sequence variables."""
import unittest
from pathlib import Path

from src.sql.checks import check_sql
from src.runtime.hooks import inspect

FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'sql'
RULES = {'locking_hint', 'save_mode_early_exit', 'save_multiple_commit', 'count_variable',
         'rowcount_count_variable', 'scalar_sequence_base', 'staging_sequence_update', 'intermediate_table',
         'unused_variable', 'single_use_variable', 'row_by_row_loop', 'duplicated_mode_code'}


def findings(candidate: str, original: str | None = None, **options) -> list[tuple[str, str]]:
    review = original is not None and options.pop('review', True)
    result = check_sql(candidate, original=original, check_style=False, review_sp_changes=review,
                       compare_original=not review, **options)
    return [(issue.code, issue.severity) for issue in result.issues if issue.code in RULES]


def codes(candidate: str, original: str | None = None, **options) -> set[str]:
    return {code for code, _ in findings(candidate, original, **options)}


class LockingHintTests(unittest.TestCase):
    SOURCE = 'SELECT 1 FROM MA100T A WITH (UPDLOCK, HOLDLOCK) WHERE A.ORGDIV = @ORGDIV'

    def test_present_added_and_retained_hints_are_errors(self):
        self.assertEqual([('locking_hint', 'error')] * 2, findings(self.SOURCE))
        plain = self.SOURCE.replace(' WITH (UPDLOCK, HOLDLOCK)', '')
        self.assertEqual([('locking_hint', 'error')] * 2, findings(self.SOURCE, plain))
        retained = check_sql(self.SOURCE + ' AND 1 = 1', original=self.SOURCE, review_sp_changes=True, compare_original=False)
        self.assertEqual({'retained'}, {i.details['origin'] for i in retained.issues if i.code == 'locking_hint'})
        self.assertFalse(retained.success)

    def test_explicit_request_formatting_and_project_policy(self):
        self.assertEqual([('locking_hint', 'info')] * 2, findings(self.SOURCE, allow_locking_hints=True))
        self.assertEqual([('locking_hint', 'info')] * 2, findings(self.SOURCE, self.SOURCE, review=False))
        self.assertEqual([], findings(self.SOURCE, self.SOURCE, check_preferences=False))
        plain = self.SOURCE.replace(' WITH (UPDLOCK, HOLDLOCK)', '')
        self.assertEqual([('locking_hint', 'warning')] * 2, findings(self.SOURCE, plain, check_preferences=False))

    def test_other_hints_literals_and_comments_are_not_locking_hints(self):
        for text in ("SELECT 'WITH (UPDLOCK, HOLDLOCK)' FROM T A /* WITH (UPDLOCK) */",
                     'SELECT 1 FROM T A WITH (NOLOCK)', 'SELECT 1 FROM T A -- WITH (HOLDLOCK)\n'):
            self.assertEqual(set(), codes(text), text)
        self.assertEqual({'locking_hint'}, codes('SELECT 1 FROM T A WITH (ROWLOCK, XLOCK)'))


BRANCHED = """IF ISNULL(@WORKTYPE, '') NOT IN ('NEW', 'EDIT', 'DELETE')
BEGIN
    RAISERROR('X', 16, 1);
    RETURN;
END
BEGIN TRANSACTION
IF @WORKTYPE = 'DELETE'
BEGIN
    DELETE A FROM DOC A WHERE A.ID = @ID
END
ELSE IF @WORKTYPE IN ('NEW', 'EDIT')
BEGIN
    IF @WORKTYPE = 'NEW'
    BEGIN
        INSERT INTO DOC (ID) SELECT @ID
    END
    UPDATE A SET A.QTY = 1 FROM DOC A WHERE A.ID = @ID
END
COMMIT TRANSACTION
"""

EARLY_EXIT = """IF ISNULL(@WORKTYPE, '') NOT IN ('NEW', 'EDIT', 'DELETE')
BEGIN
    RAISERROR('X', 16, 1);
    RETURN;
END
BEGIN TRANSACTION
IF @WORKTYPE = 'DELETE'
BEGIN
    DELETE A FROM DOC A WHERE A.ID = @ID
    COMMIT TRANSACTION
    RETURN;
END
IF @WORKTYPE = 'NEW'
BEGIN
    INSERT INTO DOC (ID) SELECT @ID
END
UPDATE A SET A.QTY = 1 FROM DOC A WHERE A.ID = @ID
COMMIT TRANSACTION
"""


class ModeBranchTests(unittest.TestCase):
    def test_early_exit_and_second_commit(self):
        self.assertEqual({'save_mode_early_exit', 'save_multiple_commit'}, codes(EARLY_EXIT))
        self.assertEqual(set(), codes(BRANCHED))

    def test_validation_return_and_final_block_are_not_early_exits(self):
        validation = """IF @WORKTYPE = 'EDIT'
BEGIN
    IF NOT EXISTS (SELECT 1 FROM DOC A WHERE A.ID = @ID)
    BEGIN
        RAISERROR('X', 16, 1);
        RETURN;
    END
END
IF @WORKTYPE = 'X'
BEGIN
    RAISERROR('unsupported', 16, 1);
    RETURN;
END
UPDATE A SET A.QTY = 1 FROM DOC A
"""
        self.assertEqual(set(), codes(validation))
        last = "IF @WORKTYPE = 'DELETE'\nBEGIN\n    DELETE A FROM DOC A\n    RETURN;\nEND\n"
        self.assertEqual(set(), codes('BEGIN\n' + last + 'END'))
        self.assertEqual(set(), codes("BEGIN TRAN\nCOMMIT\nGO\nBEGIN TRAN\nCOMMIT\n"))

    def test_moving_the_rest_into_else_if_is_not_a_changed_operation(self):
        def procedure(body):
            return 'CREATE PROC dbo.P @WORKTYPE VARCHAR(20), @ID INT AS\nBEGIN\n' + body + 'END\n'
        result = check_sql(procedure(BRANCHED), original=procedure(EARLY_EXIT), check_style=False,
                           review_sp_changes=True, compare_original=False)
        self.assertEqual([], [i.details for i in result.issues if i.code == 'sp_operation_change_review'])
        # Without a closed mode list the code after the RETURN may serve another mode.
        open_modes = EARLY_EXIT.split('BEGIN TRANSACTION', 1)[1]
        moved = check_sql(procedure(BRANCHED.split('BEGIN TRANSACTION', 1)[1]), original=procedure(open_modes),
                          check_style=False, review_sp_changes=True, compare_original=False)
        self.assertTrue(any(i.code == 'sp_operation_change_review' for i in moved.issues))


class CountAndSequenceVariableTests(unittest.TestCase):
    def test_count_variables_and_rowcount_checks(self):
        source = """SELECT @DELCOUNT = COUNT(CASE WHEN A.GBN = 'DEL' THEN 1 END) FROM @TMP A
DELETE A FROM DOC A INNER JOIN @TMP B ON A.ID = B.ID WHERE B.GBN = 'DEL'
IF @@ROWCOUNT <> @DELCOUNT
BEGIN
    RAISERROR('X', 16, 1);
END
SET @CNT = (SELECT COUNT(*) FROM DOC A)
IF @CNT > 0 RETURN
"""
        self.assertEqual([('count_variable', 'error'), ('rowcount_count_variable', 'error'), ('count_variable', 'error')],
                         findings(source))

    def test_unused_or_output_counts_and_rowcount_capture_are_not_reported(self):
        for text in ('SELECT @TOTAL = COUNT(*) FROM DOC A\nSELECT @TOTAL AS TOTAL',
                     'SET @ROWS = @@ROWCOUNT', 'SELECT @ROWS = @@ROWCOUNT',
                     "IF (SELECT COUNT(*) FROM @TMP) <> 1 RETURN", 'IF @@ROWCOUNT = 0 RETURN'):
            self.assertEqual(set(), codes(text), text)

    def test_scalar_max_sequence_base(self):
        source = """SELECT @LASTSEQ = ISNULL(MAX(A.SEQ), 0) FROM DETAIL A WHERE A.DOCNO = @DOCNO
UPDATE A SET A.SEQ = @LASTSEQ + B.RN FROM @TMP A INNER JOIN (SELECT T.ID, ROW_NUMBER() OVER (ORDER BY T.ID) AS RN FROM @TMP T) B ON A.ID = B.ID
"""
        self.assertEqual({'scalar_sequence_base', 'staging_sequence_update'}, codes(source))
        self.assertEqual({'scalar_sequence_base'}, codes(
            'SET @BASE = (SELECT MAX(A.SEQ) FROM DETAIL A)\nINSERT INTO DETAIL (SEQ) SELECT @BASE + ROW_NUMBER() OVER (ORDER BY T.ID) FROM @TMP T'))

    def test_single_value_numbering_and_derived_max_are_valid(self):
        for text in ("SELECT @SEQ = ISNULL(MAX(A.SEQ), 0) + 1 FROM DETAIL A\nINSERT INTO DETAIL (SEQ) VALUES (@SEQ)",
                     "SET @PURNUM = @PURDT + '-' + CONVERT(VARCHAR(10), @NEWSEQ)",
                     "SELECT @ORGLOTNUM = MIN(A.LOTNUM) FROM @TMP A",
                     """INSERT INTO DETAIL (DOCNO, SEQ)
SELECT @DOCNO, ISNULL(C.SEQ, 0) + ROW_NUMBER() OVER (ORDER BY A.ID)
FROM @TMP A
        LEFT OUTER JOIN (SELECT T.DOCNO, MAX(T.SEQ) AS SEQ FROM DETAIL T GROUP BY T.DOCNO) C
                     ON C.DOCNO = @DOCNO"""):
            self.assertEqual(set(), codes(text), text)
        numbered = check_sql('SELECT ISNULL(C.SEQ, 0) + ROW_NUMBER() OVER (ORDER BY A.ID) AS SEQ FROM @TMP A',
                             original='SELECT 1 AS SEQ FROM @TMP A', review_sp_changes=True, compare_original=False)
        self.assertNotIn('value_fallback_review', {i.code for i in numbered.issues})


class StagingTests(unittest.TestCase):
    def test_intermediate_results_and_staged_numbering(self):
        allocation = """INSERT INTO @TMPISSUE (SEQ, QTY)
SELECT A.SEQ, B.QTY FROM @TMPMA110T A INNER JOIN STOCK B ON A.ITEMCD = B.ITEMCD
SELECT A.ID INTO #ROWS FROM DOC A
"""
        self.assertEqual([('intermediate_table', 'error')] * 2, findings(allocation))
        numbering = """UPDATE A SET A.SEQ = B.RN
FROM @TMPDETAIL A INNER JOIN (SELECT T.ID, ROW_NUMBER() OVER (ORDER BY T.ID) AS RN FROM @TMPDETAIL T) B ON A.ID = B.ID
"""
        self.assertEqual({'staging_sequence_update'}, codes(numbering))
        self.assertEqual({'staging_sequence_update'}, codes('UPDATE @TMP SET SEQ = (SELECT MAX(T.SEQ) FROM DETAIL T)'))

    def test_xml_staging_exec_values_and_real_table_updates_are_valid(self):
        for text in ("INSERT INTO @TMP (ID) SELECT A.ID FROM OPENXML (@DOC_ID, '/ROOT/T', 1) WITH (ID INT) A",
                     'INSERT INTO @TMP (ID) EXEC dbo.LISTROWS', 'INSERT INTO @TMP (ID) VALUES (1)',
                     'INSERT INTO DETAIL (ID) SELECT A.ID FROM @TMP A',
                     'UPDATE A SET A.SEQ = B.RN FROM DETAIL A INNER JOIN (SELECT T.ID, ROW_NUMBER() OVER (ORDER BY T.ID) AS RN FROM DETAIL T) B ON A.ID = B.ID',
                     'UPDATE A SET A.PREVITEMCD = B.ITEMCD FROM @TMP A INNER JOIN ITEMS B ON A.ITEMCD = B.ITEMCD'):
            self.assertEqual(set(), codes(text), text)


class MinimalVariableTests(unittest.TestCase):
    def test_unused_and_single_use_variables(self):
        source = """DECLARE @DOC_ID INT
      , @UNUSED INT
      , @WRITEONLY VARCHAR(8)
      , @CUSTCD VARCHAR(20)
      , @TODAY VARCHAR(8) = CONVERT(VARCHAR(8), GETDATE(), 112)
SET @WRITEONLY = '20261119'
SELECT @CUSTCD = A.CUSTCD FROM @TMPMA100T A
UPDATE A SET A.CUSTCD = @CUSTCD, A.MODDT = @TODAY FROM MA100T A
"""
        self.assertEqual([('unused_variable', '@DOC_ID'), ('unused_variable', '@UNUSED'), ('unused_variable', '@WRITEONLY'),
                          ('single_use_variable', '@CUSTCD'), ('single_use_variable', '@TODAY')],
                         [(i.code, i.details['variable']) for i in check_sql(source, check_style=False).issues
                          if i.code in {'unused_variable', 'single_use_variable'}])

    def test_variables_that_tsql_needs(self):
        source = """DECLARE @DOC_ID INT
      , @STARTTRANCOUNT INT = @@TRANCOUNT
      , @PURNUM VARCHAR(20)
      , @PURDT VARCHAR(8)
      , @NEWSEQ INT
      , @IGNORED INT
      , @MSG VARCHAR(200)
EXEC SP_XML_PREPAREDOCUMENT @DOC_ID OUTPUT, @XML
SELECT @PURDT = A.PURDT FROM @TMPMA100T A
EXEC SP_SYSTEM_BA100T_KEYCODE @ORGDIV, 'MA100T', @PURDT, @NEWSEQ OUTPUT
EXEC SP_OTHER @OUTPUT = @IGNORED OUTPUT
SET @PURNUM = @PURDT + '-' + CONVERT(VARCHAR(10), @NEWSEQ)
SET @MSG = 'X' + @PURNUM
RAISERROR(@MSG, 16, 1)
INSERT INTO MA100T (PURNUM) SELECT @PURNUM
IF @STARTTRANCOUNT = 0 BEGIN TRANSACTION
EXEC SP_XML_REMOVEDOCUMENT @DOC_ID
"""
        self.assertEqual(set(), codes(source) & {'unused_variable', 'single_use_variable'})


class RowLoopAndDuplicationTests(unittest.TestCase):
    LOOP = """WHILE EXISTS (SELECT 1 FROM @KEYS)
BEGIN
    SELECT TOP 1 @SEQ = A.SEQ FROM @KEYS A ORDER BY A.SEQ
    WHILE @QTY > 0
    BEGIN
        SELECT TOP (1) @RECDT = A.RECDT, @STOCK = A.QTY FROM STOCK A ORDER BY A.RECDT
        SET @ISSUE = (CASE WHEN @QTY > @STOCK THEN @STOCK ELSE @QTY END)
        INSERT INTO STOCK_ISSUE (RECDT, QTY) SELECT @RECDT, @ISSUE
        SET @QTY = @QTY - @ISSUE
    END
    DELETE A FROM @KEYS A WHERE A.SEQ = @SEQ
END
"""

    def test_nested_row_by_row_write_loop(self):
        found = [i for i in check_sql(self.LOOP, check_style=False).issues if i.code == 'row_by_row_loop']
        self.assertEqual(1, len(found))
        self.assertEqual((1, 2), (found[0].details['nested_loops'], found[0].details['top_1_assignments']))
        cursor = """DECLARE C CURSOR FOR SELECT A.ID, A.QTY, A.LOT FROM @TMP A
OPEN C
FETCH NEXT FROM C INTO @ID, @QTY, @LOT
WHILE @@FETCH_STATUS = 0
BEGIN
    INSERT INTO ISSUE (ID, QTY, LOT) SELECT @ID, @QTY, @LOT
    FETCH NEXT FROM C INTO @ID, @QTY, @LOT
END
"""
        self.assertIn('row_by_row_loop', codes(cursor))

    def test_loops_that_are_not_row_by_row_writes(self):
        for text in ("WHILE @RETRY < 3\nBEGIN\n    SET @RETRY = @RETRY + 1\nEND",
                     "WHILE 1 = 1\nBEGIN\n    DELETE TOP (1000) A FROM LOGS A WHERE A.DT < @DT\n    IF @@ROWCOUNT = 0 BREAK\nEND",
                     "WHILE EXISTS (SELECT 1 FROM @T)\nBEGIN\n    SELECT TOP 1 @ID = A.ID FROM @T A\n    DELETE A FROM @T A WHERE A.ID = @ID\nEND"):
            self.assertNotIn('row_by_row_loop', codes(text), text)

    def test_shared_steps_copied_into_mode_branches(self):
        shared = ("    INSERT INTO DETAIL (A, B, C, D) SELECT T.A, T.B, T.C, T.D FROM @TMP T "
                  "INNER JOIN ITEMS I ON T.A = I.A WHERE T.GBN = 'NEW'\n") * 8
        copied = ("IF @WORKTYPE = 'NEW'\nBEGIN\n" + shared + "END\nELSE IF @WORKTYPE = 'EDIT'\nBEGIN\n"
                  "    UPDATE A SET A.X = 1 FROM DOC A\n" + shared + "END\n")
        self.assertIn('duplicated_mode_code', codes(copied))
        similar = copied.replace(shared, shared[:len(shared) // 4], 1)
        self.assertNotIn('duplicated_mode_code', codes(similar))
        nested = "IF @WORKTYPE IN ('NEW', 'EDIT')\nBEGIN\n    IF @WORKTYPE = 'NEW'\n    BEGIN\n" + shared + "    END\nEND\n"
        self.assertNotIn('duplicated_mode_code', codes(nested))

    def test_output_into_a_table_variable_is_an_intermediate_table(self):
        source = "UPDATE A SET A.QTY = 1, A.MODIP = @USERIP OUTPUT INSERTED.SEQ INTO @KEYS (SEQ) FROM DETAIL A"
        self.assertEqual([('intermediate_table', 'error')], findings(source))
        self.assertEqual(set(), codes("EXEC SP_KEYCODE @ORGDIV, 'T', @DT, @NEWSEQ OUTPUT\nINSERT INTO T (S) SELECT @NEWSEQ"))


class SaveProcedureRegressionTests(unittest.TestCase):
    """2026-11-19 C_KONE120 sp_MA100500_SAVE. With 3.6.4 a worker kept four UPDLOCK/HOLDLOCK
    hints, @TMPISSUE and the staged PURSEQ2 numbering from the original. The worker fixture is
    the unprompted kh-sql-worker result after these rules ("수정해봐라", no corrections)."""

    original = (FIXTURES / 'sp_MA100500_SAVE_original.sql').read_text(encoding='utf-8')
    # The Codex-altered DB definition at 15:40:25 ("@변수때문에 개 거지같이 만들어졌음"): 18 scalar
    # variables, @TMPPURSEQ2 + OUTPUT INTO, a nested WHILE with SELECT TOP 1 fetching that inserts
    # SA210T row by row, and the same ~150 lines in the NEW and EDIT branches.
    db_1540 = (FIXTURES / 'sp_MA100500_SAVE_db_1540.sql').read_text(encoding='utf-8')
    worker = (FIXTURES / 'sp_MA100500_SAVE_worker.sql').read_text(encoding='utf-8')

    def test_original_reports_all_three_rules(self):
        found = check_sql(self.original, check_style=False)
        counts = {code: sum(i.code == code for i in found.issues) for code in RULES}
        self.assertEqual({'locking_hint': 8, 'save_mode_early_exit': 1, 'save_multiple_commit': 1, 'count_variable': 3,
                          'rowcount_count_variable': 3, 'scalar_sequence_base': 1, 'staging_sequence_update': 1,
                          'intermediate_table': 1, 'unused_variable': 0, 'single_use_variable': 0,
                          'row_by_row_loop': 0, 'duplicated_mode_code': 0}, counts)
        self.assertFalse(found.success)

    def test_keeping_the_original_hints_in_a_logic_change_fails(self):
        kept = self.original.replace('@@ROWCOUNT <> @DELCOUNT', '@@ROWCOUNT <> @DELCOUNT AND 1 = 1')
        result = check_sql(kept, original=self.original, review_sp_changes=True, compare_original=False)
        self.assertEqual({'retained'}, {i.details['origin'] for i in result.issues if i.code == 'locking_hint'})
        self.assertFalse(result.success)
        saved = inspect(Path('sp_MA100500_SAVE.sql'), kept, original=self.original, require_procedure_header=True)
        self.assertIn('locking_hint', saved['errors'])

    def test_unprompted_worker_result_passes_the_rules(self):
        result = check_sql(self.worker, original=self.original, review_sp_changes=True, compare_original=False,
                           require_procedure_header=True)
        self.assertEqual([], [(i.code, i.line) for i in result.issues if i.code in RULES or i.severity == 'error'])
        self.assertEqual([], [i.details for i in result.issues if i.code == 'sp_operation_change_review'])
        alone = check_sql(self.worker)
        self.assertEqual([], [(i.code, i.line) for i in alone.issues if i.code in RULES])

    def test_row_by_row_database_version_is_reported(self):
        found = check_sql(self.db_1540, check_style=False)
        counts = {code: sum(i.code == code for i in found.issues) for code in RULES}
        self.assertEqual(2, counts['row_by_row_loop'])
        self.assertEqual(1, counts['duplicated_mode_code'])
        self.assertEqual(3, counts['intermediate_table'])
        self.assertFalse(found.success)
        loop = next(i for i in found.issues if i.code == 'row_by_row_loop')
        self.assertGreaterEqual(len(loop.details['loop_variables']), 8)
        self.assertEqual([], [i.code for i in check_sql(self.worker).issues if i.code in RULES])

    def test_remaining_variables_are_the_necessary_ones(self):
        # 2026-11-19 "@변수도 최소화": the worker keeps @DOC_ID, @STARTTRANCOUNT, @PURNUM, @PURDT,
        # @NEWSEQ and @OUTSEQ (XML handle, transaction capture, generated number, EXEC arguments/OUTPUT).
        for source in (self.original, self.worker):
            self.assertEqual([], [i.details for i in check_sql(source).issues
                                  if i.code in {'unused_variable', 'single_use_variable'}])
        extra = self.worker.replace('          , @OUTSEQ', '          , @CUSTCD         VARCHAR(20)\n          , @OUTSEQ', 1)
        self.assertIn('unused_variable', {i.code for i in check_sql(extra).issues})


if __name__ == '__main__':
    unittest.main()
