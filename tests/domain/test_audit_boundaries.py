"""Independent audit counterexamples and their valid controls."""
import unittest

from src.csharp.control_style import check_control_braces
from src.csharp.lexer import _scan_csharp, string_literal_value
from src.pb.checks import check_pb_export
from src.pb.datawindow import build_datawindow_grid_layout, extract_datawindow_column_specs
from src.sql.aliases import rename_aliases
from src.sql.compare import compare_sql
from src.sql.checks import check_sql, verify_sql_formatting_style


class AliasQualificationTests(unittest.TestCase):
    def test_changed_multipart_qualifiers_do_not_pass_as_alias_renames(self):
        for source, candidate in (
            ('SELECT dbo.T.ID FROM dbo.T;', 'SELECT dbo.A.ID FROM dbo.T A;'),
            ('SELECT [dbo].[T].[ID] FROM [dbo].[T];', 'SELECT [dbo].[A].[ID] FROM [dbo].[T] A;'),
            ('SELECT db.dbo.T.ID FROM db.dbo.T;', 'SELECT db.dbo.A.ID FROM db.dbo.T A;'),
        ):
            with self.subTest(source=source):
                self.assertFalse(compare_sql(source, candidate).success)

    def test_alias_helper_does_not_return_an_unbound_qualified_reference(self):
        for source in (
            'SELECT dbo.T.ID FROM dbo.T;',
            'SELECT [dbo].[T].[ID] FROM [dbo].[T];',
            'SELECT dbo /* schema */ . T.ID FROM dbo.T;',
        ):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    rename_aliases(source, {'scope_1': {'T': 'A'}})

    def test_unchanged_multipart_reference_does_not_prove_new_alias_binding(self):
        result = compare_sql('SELECT dbo.T.ID FROM dbo.T;', 'SELECT dbo.T.ID FROM dbo.T A;')
        self.assertFalse(result.success)
        self.assertEqual('incomplete', result.status)

    def test_new_explicit_alias_is_not_just_optional_as_spelling(self):
        source = 'SELECT dbo.T.ID FROM dbo.T;'
        candidate = 'SELECT dbo.T.ID FROM dbo.T AS T;'
        self.assertEqual('incomplete', compare_sql(source, candidate).status)
        self.assertFalse(check_sql(candidate, original=source, check_style=False, check_preferences=False).success)
        self.assertFalse(verify_sql_formatting_style(source, candidate, check_style=False).success)
        self.assertTrue(compare_sql('SELECT T.ID FROM dbo.T;', 'SELECT T.ID FROM dbo.T AS T;').success)
        self.assertTrue(compare_sql('SELECT T.ID FROM dbo.T AS T;', 'SELECT T.ID FROM dbo.T T;').success)

    def test_supported_alias_renames_and_unchanged_qualifiers_still_pass(self):
        for source in ('SELECT T.ID FROM dbo.T;', 'SELECT X.ID FROM dbo.T X;'):
            old = 'X' if ' X;' in source else 'T'
            with self.subTest(source=source):
                result = rename_aliases(source, {'scope_1': {old: 'A'}})
                self.assertIn('SELECT A.ID', result)
                self.assertTrue(compare_sql(source, result).success)
        source = 'SELECT dbo.T.ID FROM dbo.T;'
        self.assertTrue(compare_sql(source, source.replace('SELECT ', 'SELECT\n    ')).success)
        self.assertTrue(compare_sql('SELECT X.ID FROM dbo.T AS X;', 'SELECT X.ID FROM dbo.T X;').success)

    def test_source_name_parts_matching_aliases_do_not_block_supported_renames(self):
        for source, old, new in (
            ('SELECT A.ID FROM db.A.Items A;', 'A', 'B'),
            ('SELECT X.ID FROM db.A.Items X;', 'X', 'A'),
            ('SELECT A.ID FROM [db].[A].[Items] A;', 'A', 'B'),
        ):
            with self.subTest(source=source, new=new):
                candidate = rename_aliases(source, {'scope_1': {old: new}})
                self.assertTrue(compare_sql(source, candidate).success)
                self.assertIn('SELECT ' + new + '.ID', candidate)


class DataWindowLiteralBoundaryTests(unittest.TestCase):
    def test_window_script_strings_are_not_datawindow_columns(self):
        source = ('global type w_test from window\nend type\nevent open;\n'
                  'MessageBox("help", "column=(type=long name=fake)")\nend event\n')
        self.assertEqual([], check_pb_export(source).metadata['source']['columns'])
        self.assertEqual([], extract_datawindow_column_specs(source))

    def test_retrieve_literals_and_comments_do_not_generate_extra_columns(self):
        for protected in (
            'retrieve="SELECT \'column=(type=long name=fake)\' AS message"',
            'retrieve="SELECT ~"column=(type=long name=fake)~" AS message"',
            '// column=(type=long name=fake)',
            '/* column=(type=long name=fake) */',
        ):
            source = 'table(column=(type=char(100) name=message dbname="message")\n' + protected + '\n)'
            with self.subTest(protected=protected):
                self.assertEqual(['MESSAGE'], [x.field_name for x in extract_datawindow_column_specs(source)])
                result = build_datawindow_grid_layout(source)
                self.assertTrue(result.success)
                self.assertEqual(1, result.metadata['column_count'])

    def test_column_properties_do_not_leak_from_quoted_values_or_later_blocks(self):
        source = ('table(column=(type=char(100) dbname="name=fake" name="message")\n'
                  ' column=(type=decimal(18, 4) name=qty dbname="qty"))\n'
                  'text(band=header name=qty_t text="수량" x="110" y="2" width="80" height="16")\n'
                  'column(band=detail name=qty x="110" y="20" width="80" height="16")')
        specs = extract_datawindow_column_specs(source)
        self.assertEqual(['MESSAGE', 'QTY'], [x.field_name for x in specs])
        self.assertEqual('decimal(18, 4)', specs[1].data_type)
        self.assertEqual('수량', specs[1].caption)

    def test_multiline_literal_cannot_supply_visual_control_properties(self):
        source = ('table(column=(type=long name=id)\nretrieve="SELECT 1\n'
                  'column(name=id x=999 y=999 width=999 height=999)\n'
                  'text(name=id_t text=FAKE x=1 y=1)\n")\n'
                  'column(band=detail name=id x=5 y=20 width=100 height=16)')
        spec, = extract_datawindow_column_specs(source)
        self.assertEqual((5, 20, 100, 16), (spec.x, spec.y, spec.width, spec.height))
        self.assertEqual('ID', spec.caption)


class CSharpLiteralBoundaryTests(unittest.TestCase):
    def test_quote_leading_verbatim_literals_leave_following_code_visible(self):
        for literal, value in (('@"""hello"', '"hello'), ('@""""', '"')):
            with self.subTest(literal=literal):
                source = 'class C { void M() { var text = ' + literal + '; if (ready) Run(); } }'
                code, tokens = _scan_csharp(source)
                self.assertIn('if (ready) Run();', code)
                strings = [token for token in tokens if token[0] == 'string']
                self.assertEqual(1, len(strings))
                self.assertEqual(literal, source[strings[0][2]:strings[0][3]])
                self.assertEqual(value, string_literal_value(literal))
                self.assertEqual(1, len(check_control_braces(source)))

    def test_regular_raw_and_interpolated_literals_keep_their_code_boundaries(self):
        for literal in ('"hello"', '@"hello"', '"""hello"""', '$@"""hello {value}"', '@$"""hello {value}"'):
            with self.subTest(literal=literal):
                source = 'class C { void M() { var text = ' + literal + '; if (ready) Run(); } }'
                code, _ = _scan_csharp(source)
                self.assertIn('if (ready) Run();', code)
                self.assertEqual(1, len(check_control_braces(source)))

    def test_code_looking_verbatim_payload_remains_non_executable(self):
        source = 'class C { void M() { var text = @"""if (ready) Run();"; } }'
        code, _ = _scan_csharp(source)
        self.assertNotIn('if (ready)', code)
        self.assertFalse(check_control_braces(source))


if __name__ == '__main__':
    unittest.main()
