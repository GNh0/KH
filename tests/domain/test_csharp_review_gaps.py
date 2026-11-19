"""Duplicate subscriptions, removed edit commits and missing original Designer members."""
import unittest

from src.csharp.checks import check_csharp
from src.csharp.designer import check_designer
from src.csharp.subscriptions import subscription_counts

DESIGNER = '''partial class T100 {
    private void InitializeComponent() {
        this.txtName = new DevExpress.XtraEditors.TextEdit();
        this.btnSave = new DevExpress.XtraEditors.SimpleButton();
        this.txtName.Name = "txtName";
        this.btnSave.Name = "btnSave";
        this.btnSave.Click += new System.EventHandler(this.btnSave_Click);
        this.Controls.Add(this.btnSave);
        this.Controls.Add(this.txtName);
    }
    private DevExpress.XtraEditors.TextEdit txtName;
    private DevExpress.XtraEditors.SimpleButton btnSave;
}
'''
CODE = '''partial class T100 : FrmDevBase {
    public T100() {
        InitializeComponent();
        this.SaveCommand += T100_SaveCommand;
    }
    void T100_SaveCommand(object sender, EventArgs e) {
        gvwList.PostEditor();
        Save();
    }
    void btnSave_Click(object sender, EventArgs e) { Save(); }
    void Save() { }
}
'''


def codes(result):
    return [issue.code for issue in result.issues]


class DuplicateSubscriptionTests(unittest.TestCase):
    def test_counts_forms_and_ignores_comments_lambdas_and_unsubscription(self):
        counts = subscription_counts('''
            a.Click += h; this.a.Click += new EventHandler(this.h);
            Load += h2; // Load += h2;
            string s = "Load += h2;";
            b.Click += (s, e) => h(); b.Click += (s, e) => h();
            c.Click -= h3; c.Click += h3;
        ''')
        self.assertEqual(2, counts[('a', 'Click', 'h')])
        self.assertEqual(1, counts[('this', 'Load', 'h2')])
        self.assertEqual(1, counts[('c', 'Click', 'h3')])
        self.assertFalse([key for key in counts if key[0] == 'b'])

    def test_repeated_constructor_subscription(self):
        twice = CODE.replace('this.SaveCommand += T100_SaveCommand;', 'this.SaveCommand += T100_SaveCommand;\n        SaveCommand += T100_SaveCommand;')
        found = [i for i in check_csharp(twice, original=CODE, designer=DESIGNER, original_designer=DESIGNER).issues
                 if i.code == 'duplicate_event_subscription']
        self.assertEqual([('this', 'SaveCommand', 'T100_SaveCommand', 2)],
                         [(i.details['receiver'], i.details['event'], i.details['handler'], i.details['subscriptions']) for i in found])

    def test_designer_subscription_repeated_in_code_behind(self):
        doubled = CODE.replace('InitializeComponent();', 'InitializeComponent();\n        btnSave.Click += btnSave_Click;')
        self.assertIn('duplicate_event_subscription', codes(check_csharp(doubled, original=CODE, designer=DESIGNER, original_designer=DESIGNER)))
        # A Designer edit that repeats an existing code-behind subscription.
        wired = CODE.replace('InitializeComponent();', 'InitializeComponent();\n        btnSave.Click += btnSave_Click;')
        unwired = DESIGNER.replace('        this.btnSave.Click += new System.EventHandler(this.btnSave_Click);\n', '')
        self.assertIn('duplicate_event_subscription', codes(check_designer(DESIGNER, code_behind=wired, original=unwired)))
        self.assertNotIn('duplicate_event_subscription', codes(check_designer(unwired, code_behind=wired, original=unwired)))

    def test_existing_duplicate_and_single_subscription_are_not_reported(self):
        doubled = CODE.replace('InitializeComponent();', 'InitializeComponent();\n        btnSave.Click += btnSave_Click;')
        self.assertNotIn('duplicate_event_subscription', codes(check_csharp(doubled.replace('Save();\n    }', 'Save(); }'), original=doubled, designer=DESIGNER, original_designer=DESIGNER)))
        self.assertNotIn('duplicate_event_subscription', codes(check_csharp(CODE, original=CODE, designer=DESIGNER, original_designer=DESIGNER)))


class EditCommitRemovalTests(unittest.TestCase):
    def test_removed_post_editor_is_reviewed(self):
        removed = CODE.replace('        gvwList.PostEditor();\n', '')
        found = [i for i in check_csharp(removed, original=CODE).issues if i.code == 'edit_commit_call_removed']
        self.assertEqual(['PostEditor'], [i.details['call'] for i in found])

    def test_comment_only_or_unchanged_is_not_removal(self):
        self.assertNotIn('edit_commit_call_removed', codes(check_csharp(CODE.replace('Save();\n    }', 'Save(); // x\n    }'), original=CODE)))
        commented = CODE.replace('        gvwList.PostEditor();\n', '        // gvwList.PostEditor();\n        gvwList.PostEditor();\n')
        self.assertNotIn('edit_commit_call_removed', codes(check_csharp(commented, original=CODE)))

    def test_explicitly_allowed_removal(self):
        removed = CODE.replace('        gvwList.PostEditor();\n', '')
        self.assertNotIn('edit_commit_call_removed', codes(check_csharp(removed, original=CODE, allowed_changes={'removed_calls': ['PostEditor']})))


class MissingOriginalMemberTests(unittest.TestCase):
    def test_undeclared_rename_and_removal_are_reported(self):
        renamed = DESIGNER.replace('txtName', 'txtCustName')
        found = [i for i in check_designer(renamed, code_behind=CODE, original=DESIGNER, preserve_existing=True).issues
                 if i.code == 'designer_original_member_missing']
        self.assertEqual([('txtName', ['txtCustName'])], [(i.details['member'], i.details['possible_renames']) for i in found])

    def test_declared_rename_is_compared_not_reported_missing(self):
        renamed = DESIGNER.replace('txtName', 'txtCustName')
        result = check_designer(renamed, code_behind=CODE, original=DESIGNER, preserve_existing=True,
                                member_renames={'txtName': 'txtCustName'})
        self.assertNotIn('designer_original_member_missing', codes(result))

    def test_unchanged_designer_has_no_missing_member(self):
        self.assertNotIn('designer_original_member_missing',
                         codes(check_designer(DESIGNER, code_behind=CODE, original=DESIGNER, preserve_existing=True)))


if __name__ == '__main__':
    unittest.main()
