import unittest

from src.csharp.checks import check_csharp
from src.csharp.designer import check_designer
from src.csharp.numeric_format import check_numeric_formats


class NumericFormatTests(unittest.TestCase):
    def formats(self, source, **kwargs):
        return [issue.details['format'] for issue in check_numeric_formats(source, **kwargs)]

    def test_summary_property_is_a_format_site_but_not_a_cell_override(self):
        original = 'this.colList_QTY = new GridColumn();'
        source = original + 'this.colList_QTY.SummaryItem.DisplayFormat = "{0:N0}";'
        result = check_designer(source, original=original)
        codes = {issue.code for issue in result.issues}
        self.assertIn('numeric_format_preference', codes)
        self.assertNotIn('display_format_preference', codes)
        custom = check_designer(source.replace('{0:N0}', '{0:#,##0}'), original=original)
        self.assertEqual([], custom.issues)

    def test_summary_constructors_preserve_field_names_labels_and_alignment_scope(self):
        source = '''
new DevExpress.XtraGrid.GridColumnSummaryItem(SummaryItemType.Sum, "N0", "합계 {0,12:N2} 원");
new GridGroupSummaryItem(SummaryItemType.Sum, "QTY", column, "{0:N0}");
'''
        self.assertEqual(['N2', 'N0'], self.formats(source))

    def test_standard_formats_in_properties_and_to_string_are_reviewed(self):
        source = '''
rep.DisplayFormat.FormatString = "N0";
rep.Mask.EditMask = "n2";
string result = amount.ToString("N4", CultureInfo.InvariantCulture);
'''
        self.assertEqual(['N0', 'n2', 'N4'], self.formats(source))
        self.assertEqual('#,##0.####', check_numeric_formats(source)[2].details['custom_format_candidate'])

    def test_requested_custom_variants_and_fixed_decimal_contract_are_accepted(self):
        for value in ['#,###', '#,##0', '#,###.##', '#,##0.##', '#,##0.00', "#,##0.##;(#,##0.##);'-'"]:
            with self.subTest(value=value):
                self.assertEqual([], self.formats('amount.ToString("' + value + '");'))
                self.assertEqual([], self.formats('col.SummaryItem.DisplayFormat = "{0:' + value + '}";'))

    def test_custom_numeric_spelling_does_not_authorize_repository_display_format(self):
        source = 'this.rep = new RepositoryItemSpinEdit(); this.rep.DisplayFormat.FormatString = "#,##0";'
        result = check_designer(source)
        self.assertIn('display_format_preference', {i.code for i in result.issues})
        self.assertNotIn('numeric_format_preference', {i.code for i in result.issues})
        nested = 'this.date = new DateEdit(); this.date.Properties.CalendarTimeProperties.DisplayFormat.FormatString = "t";'
        self.assertIn('display_format_preference', {i.code for i in check_designer(nested).issues})

    def test_display_property_exception_does_not_silence_the_numeric_choice(self):
        source = 'this.rep = new RepositoryItemSpinEdit(); this.rep.DisplayFormat.FormatString = "N2";'
        result = check_designer(source, allowed_property_changes=['rep.DisplayFormat.FormatString'])
        self.assertIn('numeric_format_preference', {i.code for i in result.issues})
        self.assertEqual(['rep.DisplayFormat.FormatString'], result.metadata['style_exemptions'])

    def test_explicit_common_format_request_can_scope_repository_property_exceptions(self):
        original = 'this.rep = new RepositoryItemSpinEdit();'
        source = original + '''
this.rep.DisplayFormat.FormatType = DevExpress.Utils.FormatType.Numeric;
this.rep.DisplayFormat.FormatString = "{0:#,###,###,##0.####}";
'''
        self.assertIn('display_format_preference', {i.code for i in check_designer(source, original=original).issues})
        properties = ['rep.DisplayFormat.FormatType', 'rep.DisplayFormat.FormatString']
        result = check_designer(source, original=original, allowed_property_changes=properties)
        self.assertEqual([], result.issues)
        self.assertEqual(set(properties), set(result.metadata['style_exemptions']))

    def test_comments_unrelated_strings_codes_and_other_numeric_families_are_not_formats(self):
        source = '''
// amount.ToString("N0");
/* col.SummaryItem.DisplayFormat = "{0:N2}"; */
string code = "N0";
label.Text = "{0:N2}";
new GridColumnSummaryItem(SummaryItemType.Sum, "N0", "{0:#,##0}");
amount.ToString("C2");
amount.ToString("'N0'");
'''
        self.assertEqual([], self.formats(source))

    def test_composite_escaped_braces_are_literal_but_triple_braces_wrap_a_real_item(self):
        self.assertEqual([], self.formats('string.Format("{{0:N0}}", qty);'))
        self.assertEqual(['N0'], self.formats('string.Format("{{{0:N0}}}", qty);'))

    def test_format_data_arguments_are_not_interpreted_as_the_format(self):
        self.assertEqual([], self.formats('string.Format("{0}", "{0:N2}");'))
        self.assertEqual([], self.formats('string.Format(formatVariable, "{0:N2}");'))
        self.assertEqual(['N2'], self.formats('string.Format(CultureInfo.InvariantCulture, "{0:N2}", qty);'))
        self.assertEqual(['N0'], self.formats('System.String.Format(new System.Globalization.CultureInfo("en-US"), "{0:N0}", qty);'))

    def test_interpolation_formats_include_nested_calls_without_literal_false_positives(self):
        source = 'string result = $"QTY {qty:N0}; {(enabled ? a : b),12:N2}; {qty.ToString("N3")}";'
        self.assertCountEqual(['N0', 'N2', 'N3'], self.formats(source))
        self.assertEqual([], self.formats('string result = $"{{qty:N0}} {text ?? "x:N2"}";'))

    def test_raw_interpolation_uses_actual_brace_count(self):
        source = 'string text = $$"""literal {0:N0}, value {{qty:N2}}""";'
        self.assertEqual(['N2'], self.formats(source))

    def test_regular_verbatim_raw_and_escaped_constant_formats(self):
        source = r'''
col.SummaryItem.DisplayFormat = @"{0:N0}";
rep.DisplayFormat.FormatString = """N2""";
amount.ToString("\u004E1");
'''
        self.assertEqual(['N0', 'N2', 'N1'], self.formats(source))

    def test_dynamic_format_fragments_are_not_treated_as_complete_specifiers(self):
        source = 'rep.DisplayFormat.FormatString = "N" + digits; amount.ToString("N2" + suffix); string.Format("{0:N0}" + suffix, qty);'
        self.assertEqual([], self.formats(source))

    def test_existing_occurrences_are_preserved_but_additions_and_new_members_are_reviewed(self):
        before = 'amount.ToString("N0");'
        self.assertEqual([], self.formats('\n' + before, original=before))
        self.assertEqual(['N0'], self.formats(before + before, original=before))
        self.assertEqual(['N0'], self.formats('other.ToString("N0");', original=before))

    def test_unresolved_default_precision_and_large_precision_have_no_invented_suggestion(self):
        for value in ['N', 'N999999999']:
            issue = check_numeric_formats('amount.ToString("' + value + '");')[0]
            self.assertIsNone(issue.details['custom_format_candidate'])

    def test_csharp_and_designer_entrypoints_both_review_numeric_formats(self):
        source = 'this.colList_QTY = new GridColumn(); this.colList_QTY.SummaryItem.DisplayFormat = "{0:N2}";'
        for result in [check_csharp(source), check_designer(source)]:
            self.assertIn('numeric_format_preference', {i.code for i in result.issues})
            self.assertTrue(any('dynamic formats' in item for item in result.not_checked))


if __name__ == '__main__':
    unittest.main()
