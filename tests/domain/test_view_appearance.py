import unittest

from src.csharp.checks import check_csharp
from src.csharp.designer import check_designer
from src.csharp.view_appearance import check_view_appearance
from src.csharp.control_defaults import read_control_defaults


def findings(result):
    return [item for item in result.issues if item.code == 'view_appearance_change_review']


class ViewAppearanceTests(unittest.TestCase):
    def test_designer_view_scope_is_separate_from_column_header_and_cell(self):
        source = '''this.gvwList = new DevExpress.XtraGrid.Views.Grid.GridView();
this.gvwList.Appearance.HeaderPanel.Options.UseFont = true;
this.gvwList.Appearance.HeaderPanel.TextOptions.HAlignment = HorzAlignment.Center;
this.colList_QTY = new GridColumn();
this.colList_QTY.AppearanceCell.Options.UseFont = true;
this.colList_QTY.AppearanceHeader.TextOptions.HAlignment = HorzAlignment.Center;'''
        result = check_designer(source)
        self.assertEqual({'gvwList.Appearance.HeaderPanel.Options.UseFont',
                          'gvwList.Appearance.HeaderPanel.TextOptions.HAlignment'},
                         {item.details['property'] for item in findings(result)})
        self.assertTrue(result.success)  # Findings request review, not a ban.

    def test_add_change_remove_and_unchanged_existing_defaults(self):
        plain = 'private GridView view;'
        setting = plain + ' this.view.Appearance.FocusedRow.Options.UseFont = true;'
        for before, after in [(plain, setting), (setting, plain),
                              (setting, setting.replace('true', 'false'))]:
            with self.subTest(before=before, after=after):
                self.assertEqual(1, len(findings(check_designer(after, original=before))))
        result = check_designer(setting, original=setting)
        self.assertFalse(findings(result))
        self.assertEqual(1, result.metadata['view_appearance']['unchanged_properties'])

    def test_standalone_review_does_not_claim_agent_added_existing_values(self):
        source = 'private GridView view; this.view.Appearance.Row.Font = fontRegular;'
        result = check_designer(source)
        self.assertFalse(findings(result)[0].details['original_available'])
        self.assertEqual([], findings(result)[0].details['before'])

    def test_bare_code_behind_field_uses_actual_designer_type(self):
        result = check_csharp('gvwList.Appearance.Row.Font = fontRegular;', original='',
                              designer='private KoneLib.Controls.u_GridView gvwList;')
        self.assertEqual(['gvwList.Appearance.Row.Font'],
                         [item.details['property'] for item in findings(result)])
        self.assertEqual(1, result.metadata['view_appearance']['recognized_assignments'])
        self.assertEqual(0, result.metadata['view_appearance_designer']['recognized_assignments'])

    def test_shared_helper_parameter_and_typed_cast_local(self):
        source = '''private static void Init(GridView view) {
    view.Appearance.GroupRow.Options.UseFont = true;
}
private void OnFocused(object sender) {
    GridView view = (GridView)sender;
    view.Appearance.FocusedRow.Font = fontRegular;
}'''
        result = check_csharp(source, original='')
        self.assertEqual(2, len(findings(result)))
        self.assertTrue(all('method:' in item.details['scope'] for item in findings(result)))

    def test_explicit_foreach_and_pattern_receivers(self):
        source = '''void Init() {
    foreach (GridView view in grid.Views) {
        view.Appearance.SelectedRow.Options.UseFont = false;
    }
    if (item is GridView gvw) {
        gvw.Appearance.ViewCaption.Font = fontRegular;
    }
}'''
        self.assertEqual(2, len(findings(check_csharp(source, original=''))))

    def test_same_local_name_on_non_view_in_another_method_is_not_a_grid(self):
        source = '''void Init(GridView view) {
    view.Appearance.HeaderPanel.Options.UseFont = true;
}
void Other(TreeList view) {
    view.Appearance.HeaderPanel.Options.UseFont = true;
}'''
        result = check_csharp(source, original='')
        self.assertEqual(1, len(findings(result)))
        self.assertIn('method:Init(', findings(result)[0].details['scope'])

    def test_shadowing_respects_explicit_this_and_nested_scope(self):
        source = '''class Screen {
    private GridView view;
    void Init() {
        { TreeList view = tree; view.Appearance.HeaderPanel.Options.UseFont = true; }
        this.view.Appearance.HeaderPanel.Options.UseFont = true;
        view.Appearance.FocusedRow.Options.UseFont = false;
    }
}'''
        result = check_csharp(source, original='')
        self.assertEqual(2, len(findings(result)))
        self.assertFalse(result.metadata['view_appearance']['unresolved_receivers'])

    def test_var_new_is_visible_but_unresolved_alias_is_not_inferred(self):
        source = '''void Init() {
    var view = new GridView();
    view.Appearance.Row.Font = fontRegular;
    var alias = view;
    alias.Appearance.Row.Font = otherFont;
}'''
        result = check_csharp(source, original='')
        self.assertEqual(1, len(findings(result)))
        self.assertTrue(any(item.endswith(':alias') for item in result.metadata['view_appearance']['unresolved_receivers']))

    def test_control_constructor_self_is_checked_without_a_standalone_view_file(self):
        source = '''namespace Widgets {
class WorkView : DevExpress.XtraGrid.Views.Grid.GridView {
    public WorkView() {
        Appearance.Row.Font = fontRegular;
        this.Appearance.HeaderPanel.Options.UseFont = true;
        base.Appearance.FocusedRow.Options.UseFont = true;
    }
}
class WorkGrid : DevExpress.XtraGrid.GridControl {
    public WorkGrid() { this.Appearance.BackColor = Color.White; }
}
}'''
        result = check_csharp(source, original='')
        self.assertEqual(3, len(findings(result)))
        self.assertTrue(all(item.details['property'].startswith('this.Appearance.') for item in findings(result)))

    def test_supplied_custom_view_chain_and_unknown_similar_name(self):
        library = '''namespace Widgets {
class BaseView : DevExpress.XtraGrid.Views.Grid.GridView {}
class WorkView : BaseView {}
}'''
        result = check_designer('this.view = new Widgets.WorkView(); this.view.Appearance.Row.Font = fontRegular;',
                                control_sources=[library])
        self.assertEqual(1, len(findings(result)))
        self.assertFalse(findings(check_designer('this.view = new Other.WorkView(); this.view.Appearance.Row.Font = fontRegular;',
                                                 control_sources=[library])))
        self.assertFalse(findings(check_designer('this.u_GridView = new UnknownWidget(); this.u_GridView.Appearance.Row.Font = fontRegular;')))

    def test_custom_self_base_chain_uses_supplied_source(self):
        library = 'namespace Widgets { class BaseView : GridView {} }'
        result = check_view_appearance('class WorkView : Widgets.BaseView { void Init() { Appearance.Row.Font = f; } }',
                                       original='', defaults=read_control_defaults([library]))
        self.assertEqual(1, len(findings(result)))

    def test_intermediate_assignment_change_cannot_hide_behind_same_last_value(self):
        before = '''private GridView view;
this.view.Appearance.Row.Font = first;
this.view.Appearance.Row.Font = last;'''
        after = before.replace('= first', '= changed')
        result = check_designer(after, original=before)
        self.assertEqual(1, len(findings(result)))
        self.assertEqual(['first', 'last'], findings(result)[0].details['before'])
        self.assertEqual(['changed', 'last'], findings(result)[0].details['after'])

    def test_comment_literal_and_formatting_changes_are_not_new_assignments(self):
        before = '''private GridView view;
this.view.Appearance.Row.Font = new Font("Tahoma", 9F);'''
        after = before.replace('this.view.Appearance.Row.Font', 'this . view . Appearance . Row . Font')
        after += '''
// this.view.Appearance.FocusedRow.Options.UseFont = true;
string sample = """this.view.Appearance.HeaderPanel.Font = other;""";'''
        self.assertFalse(findings(check_designer(after, original=before)))

    def test_exact_property_exception_keeps_other_properties_under_review(self):
        source = '''private GridView view;
this.view.Appearance.Row.Font = fontRegular;
this.view.Appearance.FocusedRow.Options.UseFont = false;'''
        result = check_designer(source, allowed_property_changes=iter(['view.Appearance.Row.Font']))
        self.assertEqual(['view.Appearance.FocusedRow.Options.UseFont'],
                         [item.details['property'] for item in findings(result)])
        self.assertEqual(['view.Appearance.Row.Font'], result.metadata['style_exemptions'])

    def test_neutral_company_mode_retains_source_behavior_review(self):
        source = 'private GridView view; this.view.Appearance.HeaderPanel.TextOptions.HAlignment = HorzAlignment.Center;'
        self.assertEqual(1, len(findings(check_designer(source, check_style=False))))
        self.assertEqual(1, len(findings(check_csharp(source, original='', check_style=False))))

    def test_member_rename_does_not_invent_an_appearance_change(self):
        before = 'private GridView oldView; this.oldView.Appearance.Row.Font = fontRegular;'
        after = before.replace('oldView', 'newView')
        source = 'this.newView.Appearance.Row.Font = fontRegular;'
        result = check_csharp(source, original=source.replace('newView', 'oldView'),
                              designer=after, original_designer=before, member_renames={'oldView': 'newView'})
        self.assertFalse(findings(result))

    def test_removed_code_behind_setting_uses_actual_original_type(self):
        result = check_csharp('', original='view.Appearance.Row.Font = fontRegular;',
                              designer='', original_designer='private GridView view;')
        self.assertEqual(1, len(findings(result)))
        self.assertEqual([], findings(result)[0].details['after'])
        non_grid = check_csharp('', original='view.Appearance.HeaderPanel.Options.UseFont = true;',
                                designer='', original_designer='private TreeList view;')
        self.assertFalse(findings(non_grid))

    def test_missing_type_is_reported_as_unresolved_not_a_guessed_grid(self):
        result = check_csharp('view.Appearance.Row.Font = fontRegular;', original='')
        self.assertFalse(findings(result))
        self.assertTrue(result.metadata['view_appearance']['unresolved_receivers'])
        self.assertIn('unresolved appearance receivers listed in view_appearance', result.not_checked)

    def test_incompatible_parameter_shadows_designer_field(self):
        result = check_csharp('void Init(TreeList view) { view.Appearance.HeaderPanel.Font = fontRegular; }',
                              original='', designer='private GridView view;')
        self.assertFalse(findings(result))

    def test_expression_helper_parameters_keep_their_own_type_and_scope(self):
        source = '''void Init(GridView view) => view.Appearance.Row.Font = fontRegular;
void Other(TreeList view) => view.Appearance.HeaderPanel.Font = fontRegular;'''
        result = check_csharp(source, original='')
        self.assertEqual(1, len(findings(result)))
        self.assertIn('method:Init(', findings(result)[0].details['scope'])

    def test_lambda_parameter_type_is_not_guessed_from_same_named_grid_field(self):
        source = '''void Init() {
    items.ForEach(view => view.Appearance.HeaderPanel.Font = f);
    action = (TreeList view) => { view.Appearance.HeaderPanel.Font = f; };
    other = (GridView grid) => { grid.Appearance.Row.Font = f; };
}'''
        result = check_csharp(source, original='', designer='private GridView view;')
        self.assertEqual(1, len(findings(result)))
        self.assertTrue(any(item.endswith(':view') for item in result.metadata['view_appearance']['unresolved_receivers']))

    def test_indirect_receiver_with_spaces_does_not_become_self_appearance(self):
        source = '''class WorkView : GridView {
    void Init() { items[0] . Appearance.Row.Font = f; }
}'''
        result = check_csharp(source, original='')
        self.assertFalse(findings(result))
        self.assertTrue(result.metadata['view_appearance']['unresolved_receivers'])


if __name__ == '__main__':
    unittest.main()
