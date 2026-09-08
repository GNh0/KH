import unittest

from src.csharp.checks import check_csharp
from src.csharp.control_defaults import read_control_defaults
from src.csharp.designer import check_designer


LIBRARY = '''
namespace Project.Widgets
{
    public class SearchBox : DevExpress.XtraEditors.TextEdit
    {
        public SearchBox()
        {
            base.Properties.AutoHeight = false;
            base.MinimumSize = new System.Drawing.Size(0, 23);
            base.EnterMoveNextControl = true;
        }
    }
    public class CalendarBox : DevExpress.XtraEditors.DateEdit
    {
        public CalendarBox()
        {
            this.Properties.Mask.MaskType = DevExpress.XtraEditors.Mask.MaskType.DateTimeAdvancingCaret;
        }
    }
}
'''


def codes(source, **kwargs):
    return {issue.code for issue in check_designer(source, **kwargs).issues}


class ControlDefaultsTests(unittest.TestCase):
    def test_available_user_controls_are_not_limited_to_one_library_or_prefix(self):
        source = 'this.txtFind = new DevExpress.XtraEditors.TextEdit();'
        self.assertIn('available_user_control_preference', codes(source, control_sources=[LIBRARY]))
        self.assertNotIn('available_user_control_preference', codes(source))
        self.assertNotIn('available_user_control_preference', codes(source, original=source, control_sources=[LIBRARY]))

    def test_constructor_defaults_are_inherited_and_new_overrides_are_reviewed(self):
        source = 'this.txtFind = new Project.Widgets.SearchBox();'
        self.assertEqual(set(), codes(source, control_sources=[LIBRARY]))
        changed = source + ' this.txtFind.Properties.AutoHeight = true;'
        self.assertIn('user_control_default_override', codes(changed, original=source, control_sources=[LIBRARY]))
        self.assertNotIn('user_control_default_override', codes(changed, original=changed, control_sources=[LIBRARY]))

    def test_default_values_come_from_current_source_instead_of_global_constants(self):
        source = 'this.txtFind = new Project.Widgets.SearchBox(); this.txtFind.Properties.AutoHeight = true;'
        self.assertIn('user_control_default_override', codes(source, control_sources=[LIBRARY]))
        other = LIBRARY.replace('AutoHeight = false', 'AutoHeight = true')
        result = check_designer(source, control_sources=[other])
        self.assertNotIn('user_control_default_override', {i.code for i in result.issues})
        self.assertEqual(['info'], [i.severity for i in result.issues if i.code == 'user_control_default_restatement'])

    def test_specific_required_override_does_not_exempt_other_properties(self):
        source = 'this.txtFind = new Project.Widgets.SearchBox(); this.txtFind.Properties.AutoHeight = true; this.txtFind.EnterMoveNextControl = false;'
        found = check_designer(source, control_sources=[LIBRARY], allowed_property_changes=['txtFind.Properties.AutoHeight'])
        self.assertEqual(['txtFind.EnterMoveNextControl'], [i.details['property'] for i in found.issues if i.code == 'user_control_default_override'])

    def test_code_behind_assignments_cannot_bypass_the_supplied_defaults(self):
        designer = 'private Project.Widgets.SearchBox txtFind;'
        result = check_csharp('this.txtFind.Properties.AutoHeight = true;', original='', designer=designer,
                             original_designer=designer, control_sources=[LIBRARY])
        self.assertIn('user_control_default_override', {i.code for i in result.issues})

    def test_date_naming_and_input_settings_are_reviewed_for_new_controls(self):
        for typename, sources in [('DevExpress.XtraEditors.DateEdit', []), ('Project.Widgets.CalendarBox', [LIBRARY])]:
            with self.subTest(typename=typename):
                source = f'this.deFRDT = new {typename}(); this.deFRDT.Properties.EditFormat.FormatString = "yyyy-MM-dd";'
                self.assertTrue({'date_control_name_preference', 'date_input_option_review'} <= codes(source, control_sources=sources))
                self.assertEqual(set(), codes(source, original=source, control_sources=sources))
                self.assertNotIn('date_control_name_preference', codes(source.replace('deFRDT', 'ymdFRDT'), control_sources=sources))

    def test_date_input_behavior_can_be_requested_without_a_global_mask_ban(self):
        source = 'this.ymdFRDT = new DateEdit(); this.ymdFRDT.Properties.Mask.MaskType = MaskType.DateTimeAdvancingCaret;'
        self.assertIn('date_input_option_review', codes(source))
        self.assertNotIn('date_input_option_review', codes(source, allowed_property_changes=['ymdFRDT.Properties.Mask.MaskType']))

    def test_custom_editor_inheritance_also_uses_display_format_review(self):
        source = 'this.ymdFRDT = new Project.Widgets.CalendarBox(); this.ymdFRDT.Properties.DisplayFormat.FormatString = "d";'
        self.assertIn('display_format_preference', codes(source, control_sources=[LIBRARY]))
        self.assertNotIn('display_format_preference', codes(source, original=source, control_sources=[LIBRARY]))

    def test_custom_view_inheritance_is_resolved_only_from_supplied_sources(self):
        library = 'namespace Widgets { public class WorkView : DevExpress.XtraGrid.Views.Grid.GridView { public WorkView() { } } }'
        source = 'this.view = new Widgets.WorkView(); this.view.OptionsBehavior.Editable = false;'
        self.assertIn('grid_options_behavior_change', codes(source, control_sources=[library]))
        self.assertNotIn('grid_options_behavior_change', codes(source))

    def test_other_qualified_types_and_ambiguous_short_names_are_not_the_same_control(self):
        source = 'this.txtFind = new Other.SearchBox(); this.txtFind.Properties.AutoHeight = true;'
        self.assertNotIn('user_control_default_override', codes(source, control_sources=[LIBRARY]))
        self.assertNotIn('available_user_control_preference', codes('this.txtFind = new Other.TextEdit();', control_sources=[LIBRARY]))
        alternate = LIBRARY.replace('Project.Widgets', 'Other')
        self.assertNotIn('user_control_default_override', codes(source.replace('Other.SearchBox', 'SearchBox'), control_sources=[LIBRARY, alternate]))

    def test_conditional_localized_defaults_and_event_code_are_not_universal_values(self):
        source = '''namespace Widgets { public class Box : TextEdit { public Box() {
            base.Properties.AutoHeight = false;
            if (localized) base.Properties.AutoHeight = true;
            if (localized) { base.Properties.EditFormat.FormatString = "d"; }
            base.Text = "a ; b";
            base.Click += (s, e) => { base.Visible = false; };
        } void Other() { base.Enabled = false; } } }'''
        props = read_control_defaults([source])[0].properties
        self.assertEqual({'Text': '"a ; b"'}, props)

    def test_duplicate_conflicting_control_sources_are_visible(self):
        with self.assertRaises(ValueError):
            read_control_defaults([LIBRARY, LIBRARY.replace('AutoHeight = false', 'AutoHeight = true')])

    def test_partial_unclosed_input_does_not_invent_a_control_default(self):
        self.assertEqual([], read_control_defaults(['public class Box : TextEdit { public Box() {']))

    def test_supplied_base_constructor_defaults_are_inherited_without_forcing_specialized_subclasses(self):
        child = 'namespace Project.Widgets { public class SpecializedBox : Project.Widgets.SearchBox { public SpecializedBox() { } } }'
        source = 'this.txtFind = new Project.Widgets.SpecializedBox(); this.txtFind.EnterMoveNextControl = false;'
        self.assertIn('user_control_default_override', codes(source, control_sources=[LIBRARY, child]))
        self.assertNotIn('available_user_control_preference', codes(source.replace('SpecializedBox', 'SearchBox'), control_sources=[LIBRARY, child]))
        conditional = child.replace('public SpecializedBox() { }', 'public SpecializedBox() { if (mode) base.EnterMoveNextControl = false; }')
        self.assertNotIn('user_control_default_override', codes(source, control_sources=[LIBRARY, conditional]))

    def test_screen_owned_name_position_and_binding_do_not_override_style_defaults(self):
        library = LIBRARY.replace('base.EnterMoveNextControl = true;', 'base.Name = "SearchBox"; base.Location = new Point(0, 0); base.TabIndex = 0; base.BindingField = null;')
        source = 'this.txtFind = new Project.Widgets.SearchBox(); this.txtFind.Name = "txtFind"; this.txtFind.Location = new Point(20, 40); this.txtFind.TabIndex = 2; this.txtFind.BindingField = "ITEMCD";'
        self.assertNotIn('user_control_default_override', codes(source, control_sources=[library]))

    def test_member_and_name_stay_consistent_when_a_date_is_renamed(self):
        source = 'this.ymdFRDT = new DateEdit(); this.ymdFRDT.Name = "deFRDT";'
        self.assertIn('control_name_mismatch', codes(source))
        self.assertNotIn('control_name_mismatch', codes(source, original=source))


if __name__ == '__main__':
    unittest.main()
