import unittest

from src.sql.checks import check_sql


READ_BATCH = "INSERT INTO @Rows SELECT ID FROM OPENXML(@doc, '/ROOT/Rows', 1) WITH (ID INT);\n"
LOOP = '''WHILE @@FETCH_STATUS = 0
BEGIN
    SELECT @payload = (SELECT A.ID FROM @Rows A WHERE A.ID = @id FOR XML RAW('Rows'), ROOT('ROOT'));
    EXEC dbo.SaveRow @data = @payload;
    FETCH NEXT FROM RowCursor INTO @id;
END'''


def inspect(source, original=None):
    return check_sql(source, original=original, check_style=False, check_preferences=False)


def dispatches(result):
    return [issue for issue in result.issues if issue.code == 'xml_reencode_dispatch_review']


class SqlSaveFlowTests(unittest.TestCase):
    def test_batch_reencoded_for_cursor_dispatch_requires_review(self):
        result = inspect(READ_BATCH + LOOP)
        found = dispatches(result)
        self.assertEqual(1, len(found))
        self.assertEqual('warning', found[0].severity)
        self.assertEqual({'callee': 'dbo.SaveRow', 'xml_variables': ['@PAYLOAD'], 'loop_kind': 'cursor'}, found[0].details)
        self.assertEqual(5, found[0].line)
        self.assertEqual('needs_review', result.metadata['review_status'])
        self.assertTrue(result.success)
        self.assertTrue(any('callee implementation' in item for item in result.not_checked))

    def test_plain_counter_loop_and_set_assignment_are_also_reviewed(self):
        source = (READ_BATCH + LOOP).replace('@@FETCH_STATUS = 0', '@id < @count').replace('SELECT @payload =', 'SET @payload =')
        self.assertEqual('while', dispatches(inspect(source))[0].details['loop_kind'])

    def test_batch_update_delete_and_one_batch_call_do_not_require_rowwise_review(self):
        for source in (
            READ_BATCH + 'UPDATE A SET A.QTY = B.QTY FROM Target A JOIN @Rows B ON A.ID = B.ID;',
            READ_BATCH + 'DELETE A FROM Target A JOIN @Rows B ON A.ID = B.ID;',
            READ_BATCH + 'SELECT @payload = (SELECT ID FROM @Rows FOR XML RAW); EXEC dbo.SaveBatch @data = @payload;',
        ):
            with self.subTest(source=source):
                self.assertEqual([], dispatches(inspect(source)))

    def test_components_alone_do_not_prohibit_loop_xml_or_exec(self):
        for source in (
            LOOP,
            READ_BATCH + LOOP.replace('EXEC dbo.SaveRow @data = @payload;', 'SELECT @payload;'),
            READ_BATCH + LOOP.replace('SELECT @payload = (SELECT A.ID FROM @Rows A WHERE A.ID = @id FOR XML RAW(\'Rows\'), ROOT(\'ROOT\'));', 'SET @payload = @input;'),
        ):
            with self.subTest(source=source):
                self.assertEqual([], dispatches(inspect(source)))

    def test_comments_strings_and_quoted_keywords_are_not_executable_shape(self):
        source = "SELECT 'OPENXML(@doc)' AS [OPENXML]; /* " + READ_BATCH + " */\n" + LOOP
        self.assertEqual([], dispatches(inspect(source)))
        source = READ_BATCH + "WHILE @id > 0 BEGIN SELECT 'SELECT @payload = FOR XML; EXEC dbo.SaveRow @payload'; END"
        self.assertEqual([], dispatches(inspect(source)))

    def test_original_loop_is_preserved_even_when_surrounding_sql_changes(self):
        source = READ_BATCH + LOOP
        self.assertEqual([], dispatches(inspect('SET NOCOUNT ON;\n' + source, original=source)))
        self.assertEqual([], dispatches(inspect(source.replace('    ', '        '), original=source)))

    def test_new_dispatch_in_changed_loop_is_reviewed(self):
        source = READ_BATCH + LOOP
        original = source.replace('EXEC dbo.SaveRow @data = @payload;', 'SELECT @payload;')
        self.assertEqual(1, len(dispatches(inspect(source, original=original))))

    def test_named_parameter_is_not_the_xml_argument(self):
        source = (READ_BATCH + LOOP).replace('@data = @payload', '@payload = @different')
        self.assertEqual([], dispatches(inspect(source)))

    def test_latest_direct_assignment_replaces_encoded_value(self):
        source = (READ_BATCH + LOOP).replace('EXEC dbo.SaveRow', 'SET @payload = NULL; EXEC dbo.SaveRow')
        self.assertEqual([], dispatches(inspect(source)))

    def test_xml_document_helpers_and_dynamic_calls_are_not_static_business_dispatch(self):
        for call in (
            'EXEC SP_XML_PREPAREDOCUMENT @doc OUTPUT, @payload;',
            'EXEC dbo.SP_XML_LOG_SAVE @@PROCID, @mode, @user, @payload;',
            'EXEC sys.sp_executesql @sql, N\'@payload xml\', @payload = @payload;',
            'EXEC(@sql);',
            'EXEC @procedure @data = @payload;',
        ):
            with self.subTest(call=call):
                source = (READ_BATCH + LOOP).replace('EXEC dbo.SaveRow @data = @payload;', call)
                self.assertEqual([], dispatches(inspect(source)))

    def test_static_qualified_names_and_return_variables_are_supported(self):
        for call, callee in (
            ('EXEC @result = [dbo].[WriteRows] @data = @payload;', '[dbo].[WriteRows]'),
            ('EXECUTE OtherDb..WriteRows @payload;', 'OtherDb.WriteRows'),
            ('exec dbo.WriteRows @data = @PAYLOAD;', 'dbo.WriteRows'),
        ):
            with self.subTest(call=call):
                source = (READ_BATCH + LOOP).replace('EXEC dbo.SaveRow @data = @payload;', call)
                self.assertEqual(callee, dispatches(inspect(source))[0].details['callee'])

    def test_nested_loop_case_and_try_blocks_preserve_the_actual_loop_boundary(self):
        inner = LOOP.replace('SELECT A.ID', "SELECT CASE WHEN A.ID = 1 THEN 'A' ELSE 'B' END AS ID")
        source = READ_BATCH + 'WHILE @outer < 2 BEGIN BEGIN TRY ' + inner + ' END TRY BEGIN CATCH THROW; END CATCH END'
        found = dispatches(inspect(source))
        self.assertEqual(1, len(found))
        self.assertEqual('cursor', found[0].details['loop_kind'])

    def test_begin_transaction_is_not_a_begin_end_block(self):
        source = READ_BATCH + LOOP.replace('SELECT @payload', 'BEGIN TRANSACTION; SELECT @payload').replace('FETCH NEXT', 'COMMIT TRANSACTION; FETCH NEXT')
        self.assertEqual(1, len(dispatches(inspect(source))))

    def test_a_different_batch_does_not_supply_the_input_parser(self):
        self.assertEqual([], dispatches(inspect(READ_BATCH + 'GO\n' + LOOP)))

    def test_single_statement_loop_and_nodes_input_remain_unverified(self):
        source = READ_BATCH + 'SELECT @payload = (SELECT ID FOR XML RAW); WHILE @id > 0 EXEC dbo.SaveRow @payload;'
        self.assertEqual([], dispatches(inspect(source)))
        source = 'SELECT A.ID FROM @input.nodes(\'/ROOT/Rows\') A(ID);\n' + LOOP
        self.assertEqual([], dispatches(inspect(source)))

    def test_multiple_reencoded_xml_arguments_form_one_dispatch(self):
        source = (READ_BATCH + LOOP).replace('EXEC dbo.SaveRow @data = @payload;',
            "SET @other = (SELECT ID FROM @Rows FOR XML RAW); EXEC dbo.SaveRow @data = @payload, @other = @other;")
        found = dispatches(inspect(source))
        self.assertEqual(1, len(found))
        self.assertEqual(['@OTHER', '@PAYLOAD'], found[0].details['xml_variables'])


if __name__ == '__main__':
    unittest.main()
