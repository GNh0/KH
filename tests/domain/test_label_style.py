import unittest

from src.csharp.checks import check_csharp
from src.csharp.designer import check_designer


# The actual project's initialization shape: conditional self-property defaults,
# an unscaled 23px constructor and 25px controls in an approved screen.
LABEL = '''namespace Widgets {
    public class LabelBox : DevExpress.XtraEditors.LabelControl {
        public LabelBox() {
            base.Appearance.Font = new System.Drawing.Font("Pretendard GOV Variable", 10);
            base.Appearance.Options.UseFont = true;
            base.Appearance.TextOptions.HAlignment = base.Appearance.TextOptions.HAlignment == DevExpress.Utils.HorzAlignment.Default ? DevExpress.Utils.HorzAlignment.Far : base.Appearance.TextOptions.HAlignment;
            base.Appearance.TextOptions.VAlignment = base.Appearance.TextOptions.VAlignment == DevExpress.Utils.VertAlignment.Default ? DevExpress.Utils.VertAlignment.Center : base.Appearance.TextOptions.VAlignment;
            base.AutoSizeMode = LabelAutoSizeMode.None;
            base.MinimumSize = new Size(0, 23);
            base.MaximumSize = new Size(65535, 23);
            base.Size = new Size(100, 23);
        }
    }
}'''
DATE = '''namespace Widgets { public class DateBox : DevExpress.XtraEditors.DateEdit {
    public DateBox() { base.Size = new Size(100, 23); }
} }'''
SCREEN = '''this.lblName = new Widgets.LabelBox();
    this.lblName.Appearance.Font = new System.Drawing.Font("Pretendard GOV Variable", 10F);
    this.lblName.Appearance.Options.UseFont = true;
    this.lblName.Appearance.Options.UseTextOptions = true;
    this.lblName.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Far;
    this.lblName.Appearance.TextOptions.VAlignment = DevExpress.Utils.VertAlignment.Center;
    this.lblName.AutoSizeMode = DevExpress.XtraEditors.LabelAutoSizeMode.None;
    this.lblName.MinimumSize = new System.Drawing.Size(0, 25);
    this.lblName.MaximumSize = new System.Drawing.Size(74897, 25);
    this.lblName.Size = new System.Drawing.Size(113, 25);'''
REFERENCE = SCREEN.replace('lblName', 'lblReference')


def review(source=SCREEN, **kwargs):
    return check_designer(source, control_sources=[LABEL], style_reference=REFERENCE, **kwargs)


class LabelStyleTests(unittest.TestCase):
    def test_actual_default_fallback_and_approved_scaled_height_are_accepted(self):
        result = review()
        self.assertEqual('passed', result.status)
        self.assertFalse([i for i in result.issues if i.severity != 'info'])
        self.assertEqual(['lblName'], result.metadata['label_style']['inspected_members'])

    def test_horizontal_and_vertical_default_overrides_are_errors(self):
        for original, replacement, prop in (
            ('HorzAlignment.Far', 'HorzAlignment.Near', 'HAlignment'),
            ('VertAlignment.Center', 'VertAlignment.Top', 'VAlignment'),
        ):
            with self.subTest(prop=prop):
                result = review(SCREEN.replace(original, replacement))
                finding = next(i for i in result.issues if i.code == 'label_alignment_mismatch')
                self.assertEqual('error', finding.severity)
                self.assertTrue(finding.details['property'].endswith(prop))
                self.assertEqual('failed', result.status)

    def test_alignment_fallback_is_checked_without_a_screen_reference(self):
        source = 'this.lblName = new Widgets.LabelBox(); this.lblName.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Near;'
        result = check_designer(source, control_sources=[LABEL])
        self.assertIn('label_alignment_mismatch', {i.code for i in result.issues})
        self.assertEqual('failed', result.status)

    def test_inherited_default_alignment_does_not_need_redundant_assignments(self):
        source = SCREEN.replace('this.lblName.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Far;', '')
        source = source.replace('this.lblName.Appearance.TextOptions.VAlignment = DevExpress.Utils.VertAlignment.Center;', '')
        self.assertEqual('passed', review(source).status)

    def test_inherited_use_text_options_is_not_a_missing_initializer(self):
        library = LABEL.replace('base.Appearance.Options.UseFont = true;',
                                'base.Appearance.Options.UseFont = true; base.Appearance.Options.UseTextOptions = true;')
        source = SCREEN.replace('this.lblName.Appearance.Options.UseTextOptions = true;', '')
        result = check_designer(source, style_reference=REFERENCE, control_sources=[library])
        self.assertEqual('passed', result.status)
        self.assertNotIn('label_text_options_review', {i.code for i in result.issues})

    def test_fallback_preserves_a_known_non_default_supplied_base_value(self):
        parent = '''namespace Widgets { public class BaseLabel : DevExpress.XtraEditors.LabelControl {
            public BaseLabel() { base.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Near; }
        } }'''
        child = LABEL.replace(': DevExpress.XtraEditors.LabelControl', ': Widgets.BaseLabel')
        source = SCREEN.replace('HorzAlignment.Far', 'HorzAlignment.Near')
        result = check_designer(source, style_reference=source.replace('lblName', 'lblReference'), control_sources=[parent, child])
        self.assertEqual('passed', result.status)

    def test_a_copied_bad_reference_does_not_override_control_alignment(self):
        bad = SCREEN.replace('HorzAlignment.Far', 'HorzAlignment.Near')
        result = check_designer(bad, style_reference=bad.replace('lblName', 'lblReference'), control_sources=[LABEL])
        self.assertIn('label_alignment_mismatch', {i.code for i in result.issues})

    def test_other_control_defaults_are_used_instead_of_global_far_center(self):
        library = LABEL.replace('HorzAlignment.Far', 'HorzAlignment.Center').replace('VertAlignment.Center', 'VertAlignment.Bottom')
        source = SCREEN.replace('HorzAlignment.Far', 'HorzAlignment.Center').replace('VertAlignment.Center', 'VertAlignment.Bottom')
        result = check_designer(source, style_reference=REFERENCE, control_sources=[library])
        self.assertEqual('passed', result.status)

    def test_a_needed_alignment_exception_does_not_force_the_default_back(self):
        source = SCREEN.replace('HorzAlignment.Far', 'HorzAlignment.Center')
        result = review(source, allowed_property_changes=['lblName.Appearance.TextOptions.HAlignment'])
        self.assertEqual('passed', result.status)

    def test_font_changes_are_errors_but_10_and_10f_are_equivalent(self):
        self.assertEqual('passed', review().status)
        for old, new in [('10F', '9F'), ('Pretendard GOV Variable', 'Tahoma')]:
            with self.subTest(new=new):
                self.assertIn('label_font_mismatch', {i.code for i in review(SCREEN.replace(old, new)).issues})

    def test_actual_screen_height_controls_both_shrink_and_arbitrary_expansion(self):
        for height in (22, 23, 28):
            with self.subTest(height=height):
                result = review(SCREEN.replace('Size(113, 25)', f'Size(113, {height})'))
                height_findings = [i for i in result.issues if i.code == 'label_height_mismatch']
                self.assertEqual(1, len(height_findings))
                self.assertEqual('lblName.Height', height_findings[0].details['property'])
                self.assertEqual('failed', result.status)

    def test_width_expansion_preserves_font_alignment_and_height(self):
        self.assertEqual('passed', review(SCREEN.replace('Size(113, 25)', 'Size(190, 25)')).status)

    def test_height_constraints_must_follow_the_comparison_screen(self):
        for target in ('Size(0, 25)', 'Size(74897, 25)'):
            with self.subTest(target=target):
                result = review(SCREEN.replace(target, target.replace('25', '23')))
                self.assertIn('label_height_mismatch', {i.code for i in result.issues})

    def test_constructor_height_alone_does_not_force_23_on_a_scaled_screen(self):
        result = check_designer(SCREEN, control_sources=[LABEL])
        self.assertNotIn('label_height_mismatch', {i.code for i in result.issues})
        self.assertIn('control_height_unverified', {i.code for i in result.issues})
        self.assertEqual('incomplete', result.status)

    def test_conflicting_reference_heights_need_a_relevant_comparison(self):
        ref = REFERENCE + REFERENCE.replace('lblReference', 'lblAnother').replace('25)', '30)')
        result = check_designer(SCREEN, style_reference=ref, control_sources=[LABEL])
        self.assertIn('control_height_reference_ambiguous', {i.code for i in result.issues})
        self.assertEqual('incomplete', result.status)
        self.assertNotIn('label_height_mismatch', {i.code for i in result.issues})

    def test_unrelated_conditional_or_helper_defaults_remain_unverified(self):
        library = LABEL.replace('base.Appearance.TextOptions.HAlignment == DevExpress.Utils.HorzAlignment.Default ? DevExpress.Utils.HorzAlignment.Far : base.Appearance.TextOptions.HAlignment',
                                'localized ? DevExpress.Utils.HorzAlignment.Far : DevExpress.Utils.HorzAlignment.Near')
        result = check_designer(SCREEN, style_reference=REFERENCE, control_sources=[library])
        self.assertIn('label_value_unverified', {i.code for i in result.issues})
        self.assertEqual('incomplete', result.status)
        result = review(SCREEN.replace('new System.Drawing.Font("Pretendard GOV Variable", 10F)', 'GetLabelFont()'))
        self.assertIn('label_value_unverified', {i.code for i in result.issues})

    def test_unchanged_existing_exceptions_are_not_rewritten(self):
        old = SCREEN.replace('HorzAlignment.Far', 'HorzAlignment.Near').replace('Size(113, 25)', 'Size(113, 28)')
        result = review(old, original=old)
        self.assertFalse([i for i in result.issues if i.code.startswith('label_')])
        changed = old.replace('VertAlignment.Center', 'VertAlignment.Top')
        findings = [i for i in review(changed, original=old).issues if i.code == 'label_alignment_mismatch']
        self.assertEqual(1, len(findings))
        self.assertTrue(findings[0].details['property'].endswith('VAlignment'))

    def test_a_current_requested_size_exception_is_scoped_to_that_property(self):
        changed = SCREEN.replace('Size(113, 25)', 'Size(113, 28)')
        self.assertEqual('passed', review(changed, allowed_property_changes=['lblName.Size']).status)
        changed = changed.replace('HorzAlignment.Far', 'HorzAlignment.Near')
        self.assertIn('label_alignment_mismatch', {i.code for i in review(changed, allowed_property_changes=['lblName.Size']).issues})

    def test_single_line_inputs_match_actual_screen_height_too(self):
        ref = 'this.ymdReference = new Widgets.DateBox(); this.ymdReference.Size = new Size(100, 25);'
        source = 'this.ymdDate = new Widgets.DateBox(); this.ymdDate.Size = new Size(100, 23);'
        result = check_designer(source, style_reference=ref, control_sources=[DATE])
        self.assertIn('control_height_mismatch', {i.code for i in result.issues})
        self.assertEqual('passed', check_designer(source.replace('100, 23', '100, 25'), style_reference=ref, control_sources=[DATE]).status)

    def test_a_similar_input_can_supply_height_when_no_same_type_label_exists(self):
        source = 'this.lblName = new DevExpress.XtraEditors.LabelControl(); this.lblName.Size = new Size(100, 23);'
        ref = 'this.txtReference = new DevExpress.XtraEditors.TextEdit(); this.txtReference.Size = new Size(150, 25);'
        result = check_designer(source, style_reference=ref)
        self.assertIn('label_height_mismatch', {i.code for i in result.issues})
        self.assertEqual('passed', check_designer(source.replace('100, 23', '100, 25'), style_reference=ref).status)

    def test_code_behind_overrides_use_designer_types_without_false_missing_sizes(self):
        source = 'class Screen { void Update() { this.lblName.Text = "Name"; } }'
        result = check_csharp(source, designer=SCREEN, style_reference_designer=REFERENCE, control_sources=[LABEL])
        self.assertEqual('passed', result.status)
        self.assertEqual(['lblName'], result.metadata['label_style_designer']['inspected_members'])
        changed = source.replace('this.lblName.Text = "Name";', 'this.lblName.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Near;')
        self.assertIn('label_alignment_mismatch', {i.code for i in check_csharp(changed, designer=SCREEN, style_reference_designer=REFERENCE, control_sources=[LABEL]).issues})

    def test_last_height_assignment_wins_even_if_size_is_assigned_twice(self):
        source = SCREEN + 'this.lblName.Height = 22; this.lblName.Size = new Size(113, 25);'
        self.assertEqual('passed', review(source).status)
        self.assertIn('label_height_mismatch', {i.code for i in review(source + 'this.lblName.Height = 23;').issues})

    def test_bounds_height_is_checked_without_duplicate_size_errors(self):
        source = SCREEN.replace('this.lblName.Size = new System.Drawing.Size(113, 25);', 'this.lblName.Bounds = new System.Drawing.Rectangle(0, 0, 113, 23);')
        findings = [i for i in review(source).issues if i.code == 'label_height_mismatch']
        self.assertEqual(1, len(findings))

    def test_company_project_mode_keeps_personal_defaults_customizable(self):
        bad = SCREEN.replace('HorzAlignment.Far', 'HorzAlignment.Near').replace('Size(113, 25)', 'Size(113, 28)')
        result = check_designer(bad, style_reference=REFERENCE, control_sources=[LABEL], check_style=False)
        self.assertFalse([i for i in result.issues if i.code.startswith('label_') or i.code == 'control_height_mismatch'])


if __name__ == '__main__':
    unittest.main()
