import unittest

from src.csharp.checks import check_csharp


DESIGNER = '''private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit rpsSpinVALUE;
private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit rpsAddSpinVALUE;'''
BASE = 'class Screen { public Screen() { InitializeComponent(); } }'
HANDLER = '''private void FormatValue(object sender, CustomDisplayTextEventArgs e)
    {
        decimal decValue;
        if (decimal.TryParse(Convert.ToString(e.Value), out decValue))
        {
            e.DisplayText = decValue.ToString("#,##0.##");
        }
    }'''


def screen(handler=HANDLER, wiring='rpsSpinVALUE.CustomDisplayText += FormatValue;'):
    return 'class Screen { public Screen() { InitializeComponent(); ' + wiring + ' } ' + handler + ' }'


def review(source, **kwargs):
    return check_csharp(source, designer=DESIGNER, **kwargs)


def display_findings(result):
    return [issue for issue in result.issues if issue.code == 'editor_display_override_review']


class EditorDisplayTests(unittest.TestCase):
    def test_two_real_repositories_share_one_display_rewrite(self):
        candidate = screen(wiring='rpsSpinVALUE.CustomDisplayText += FormatValue; '
                                  'rpsAddSpinVALUE.CustomDisplayText += FormatValue;')
        result = review(candidate, original=BASE, original_designer=DESIGNER)
        self.assertEqual({'rpsSpinVALUE', 'rpsAddSpinVALUE'},
                         {item.details['member'] for item in display_findings(result)})
        self.assertTrue(result.success)
        self.assertEqual('needs_review', result.metadata['review_status'])

    def test_existing_required_callback_is_preserved(self):
        candidate = screen()
        result = review(candidate, original=candidate, original_designer=DESIGNER)
        self.assertEqual([], display_findings(result))
        self.assertEqual(1, result.metadata['editor_display_callbacks']['unchanged_rewrites'])

    def test_changed_existing_format_is_reviewed(self):
        self.assertEqual(1, len(display_findings(review(screen().replace('#,##0.##', '#,##0.####'),
            original=screen(), original_designer=DESIGNER))))

    def test_local_helper_receiving_event_args_is_traced(self):
        handler = '''private void FormatValue(object sender, CustomDisplayTextEventArgs e) { Rewrite(e); }
        private void Rewrite(CustomDisplayTextEventArgs value) { value.DisplayText = "changed"; }'''
        found = display_findings(review(screen(handler), original=BASE))
        self.assertEqual(1, len(found))
        self.assertEqual(['Rewrite'], found[0].details['writers'])

    def test_changed_helper_return_is_reviewed_without_changing_callback(self):
        handler = '''private void FormatValue(object sender, CustomDisplayTextEventArgs e) { e.DisplayText = GetText(e.Value); }
        private string GetText(object value) => Convert.ToDecimal(value).ToString("#,##0.##");'''
        before = screen(handler)
        after = before.replace('#,##0.##', '#,##0.####')
        self.assertEqual(1, len(display_findings(review(after, original=before))))

    def test_unused_handler_and_local_function_do_not_establish_override(self):
        self.assertEqual([], display_findings(review(screen(wiring=''), original=BASE)))
        handler = '''private void FormatValue(object sender, CustomDisplayTextEventArgs e) {
            void Unused() { e.DisplayText = "changed"; }
            Log(e.Value);
        }'''
        self.assertEqual([], display_findings(review(screen(handler), original=BASE)))

    def test_callback_name_or_connection_alone_is_not_a_finding(self):
        handler = 'private void FormatValue(object sender, CustomDisplayTextEventArgs e) { Log(e.Value); }'
        self.assertEqual([], display_findings(review(screen(handler), original=BASE)))

    def test_button_actions_and_report_formatting_are_separate(self):
        source = screen(wiring='rpsSpinVALUE.ButtonClick += FormatValue;')
        source += 'this.report.TextFormatString = "{0:#,##0.##}";'
        self.assertEqual([], display_findings(review(source, original=BASE)))
        report = screen(wiring='report.CustomDisplayText += FormatValue;')
        result = check_csharp(report, original=BASE, designer='private DevExpress.XtraReports.UI.XRLabel report;')
        self.assertEqual([], display_findings(result))
        self.assertEqual([], result.metadata['editor_display_callbacks']['unresolved_bindings'])

    def test_comments_and_literal_fake_code_do_not_create_callbacks(self):
        source = screen(wiring='') + '\n// rpsSpinVALUE.CustomDisplayText += FormatValue;'
        source += '\nstring code = "rpsSpinVALUE.CustomDisplayText += FormatValue;";'
        self.assertEqual([], display_findings(review(source, original=BASE)))
        handler = '''private void FormatValue(object sender, CustomDisplayTextEventArgs e) {
            string sample = "e.DisplayText = text;";
            // e.DisplayText = "fake";
        }'''
        self.assertEqual([], display_findings(review(screen(handler), original=BASE)))

    def test_inline_lambda_and_typed_editor_properties_are_resolved(self):
        for body in ['{ value.DisplayText = "changed"; }', 'value.DisplayText = "changed"']:
            with self.subTest(body=body):
                source = screen(wiring='rpsSpinVALUE.CustomDisplayText += (sender, value) => ' + body + ';')
                self.assertEqual(1, len(display_findings(review(source, original=BASE))))
        source = screen(wiring='SpinVALUE.Properties.CustomDisplayText += FormatValue;')
        result = check_csharp(source, original=BASE, designer='private KoneLib.Controls.u_SpinEdit SpinVALUE;')
        self.assertEqual(1, len(display_findings(result)))

    def test_designer_subscription_and_explicit_delegate_are_resolved(self):
        candidate = screen(wiring='')
        designer = DESIGNER + '\nthis.rpsSpinVALUE.CustomDisplayText += new CustomDisplayTextEventHandler(this.FormatValue);'
        result = check_csharp(candidate, original=BASE, designer=designer, original_designer=DESIGNER)
        self.assertEqual(1, len(display_findings(result)))
        before = screen()
        result = check_csharp(candidate, original=before, designer=designer, original_designer=DESIGNER)
        self.assertEqual([], display_findings(result))

    def test_unknown_types_and_ambiguous_bodies_remain_unverified(self):
        result = check_csharp(screen(), original=BASE, designer='private Other.u_SpinEdit rpsSpinVALUE;')
        self.assertEqual([], display_findings(result))
        self.assertTrue(result.metadata['editor_display_callbacks']['unresolved_bindings'])
        handler = HANDLER + '\nprivate void FormatValue(object sender, OtherEventArgs e) { e.DisplayText = "other"; }'
        result = review(screen(handler), original=BASE)
        self.assertEqual([], display_findings(result))
        self.assertTrue(result.metadata['editor_display_callbacks']['unresolved_bindings'])

    def test_current_designer_does_not_invent_a_previous_subscription(self):
        candidate = screen(wiring='')
        designer = DESIGNER + '\nthis.rpsSpinVALUE.CustomDisplayText += FormatValue;'
        result = check_csharp(candidate, original=candidate, designer=designer)
        self.assertEqual(1, len(display_findings(result)))
        self.assertEqual(0, result.metadata['editor_display_callbacks']['unchanged_rewrites'])

    def test_supplied_custom_repository_inheritance_is_used(self):
        result = check_csharp(screen(), original=BASE,
            designer='private Widgets.NumericRepository rpsSpinVALUE;',
            control_sources=['namespace Widgets { public class NumericRepository : DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit { } }'])
        self.assertEqual(1, len(display_findings(result)))

    def test_member_rename_preserves_existing_callback(self):
        candidate = screen().replace('rpsSpinVALUE', 'rpsDetailSpinVALUE')
        result = check_csharp(candidate, original=screen(), designer=DESIGNER.replace('rpsSpinVALUE', 'rpsDetailSpinVALUE'),
            original_designer=DESIGNER, member_renames={'rpsSpinVALUE': 'rpsDetailSpinVALUE'})
        self.assertEqual([], display_findings(result))

    def test_neutral_company_mode_keeps_source_behavior_review(self):
        self.assertEqual(1, len(display_findings(review(screen(), original=BASE, check_style=False))))

    def test_recursive_helper_graph_terminates(self):
        handler = '''private void FormatValue(object sender, CustomDisplayTextEventArgs e) { Rewrite(e); }
        private void Rewrite(CustomDisplayTextEventArgs value) { value.DisplayText = "changed"; Again(value); }
        private void Again(CustomDisplayTextEventArgs value) { Rewrite(value); }'''
        self.assertEqual(1, len(display_findings(review(screen(handler), original=BASE))))
