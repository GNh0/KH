import unittest

from src.csharp.checks import check_csharp
from src.csharp.command_flow import check_command_flow


REFERENCE = '''class ProjectScreen {
    void Project_SearchCommand(object sender, SearchCommandEventArgs e) {
        m_Editmode = DataEditMode.DEFAULT;
        devFnc.Usr_ControlsProtect(grdList, true);
        CallSelectProcedure(SelectType.LIST);
    }
    void Project_SaveCommand(object sender, SaveCommandEventArgs e) {
        if (CallSaveProcedure()) {
            ShowMessage("Saved");
            CallCommand(BizCommand.Search);
        }
    }
    void Project_NewCommand(object sender, NewCommandEventArgs e) {
        m_Editmode = DataEditMode.NEW;
    }
}'''


def screen(save_body, extra=''):
    return 'class Screen { void Save(object sender, SaveCommandEventArgs e) { ' + save_body + ' } ' + extra + ' }'


class CommandFlowTests(unittest.TestCase):
    def test_repeated_temporary_save_result_and_early_reset_in_wired_button(self):
        candidate = '''class Screen {
            void Init() { btnREQ.Click += BtnREQ_Click; }
            void BtnREQ_Click(object sender, EventArgs e) {
                m_Editmode = DataEditMode.NEW;
                bool isSaved = CallSaveProcedure();
                m_Editmode = DataEditMode.DEFAULT;
                if (isSaved) { ShowMessage("Saved"); CallCommand(BizCommand.Search); }
            }
        }'''
        result = check_command_flow(candidate, style_reference=REFERENCE, allowed_commands=['search'])
        self.assertEqual({'default_edit_mode', 'save_result_temporary'},
                         {issue.details['operation'] for issue in result.issues})
        self.assertEqual(['BtnREQ_Click'], result.metadata['command_flow']['save_action_handlers'])
        self.assertTrue(all(issue.severity == 'warning' for issue in result.issues))

    def test_project_pattern_in_button_requires_no_extra_save_toolbar(self):
        candidate = '''class Screen {
            void Init() { btnREQ.Click += BtnREQ_Click; }
            void BtnREQ_Click(object sender, EventArgs e) {
                m_Editmode = DataEditMode.NEW;
                if (CallSaveProcedure()) { ShowMessage("Saved"); CallCommand(BizCommand.Search); }
            }
        }'''
        self.assertEqual([], check_command_flow(candidate, style_reference=REFERENCE,
                                               allowed_commands=['search']).issues)

    def test_designer_wiring_also_establishes_save_action_and_unchanged_is_preserved(self):
        candidate = '''void OnRequest(object sender, EventArgs e) {
            bool saved = CallSaveProcedure();
            m_Editmode = DataEditMode.DEFAULT;
            if (saved) { CallCommand(BizCommand.Search); }
        }'''
        designer = 'this.btnREQ.Click += this.OnRequest;'
        result = check_csharp(candidate, designer=designer, style_reference_csharp=REFERENCE)
        found = [issue for issue in result.issues if issue.code == 'command_phase_drift_review']
        self.assertEqual({'default_edit_mode', 'save_result_temporary'},
                         {issue.details['operation'] for issue in found})
        unchanged = check_command_flow(candidate, original=candidate, designer=designer,
                                       original_designer=designer, style_reference=REFERENCE)
        self.assertFalse(unchanged.issues)

    def test_boolean_reused_for_another_purpose_is_not_single_use_style_drift(self):
        candidate = screen('bool saved = CallSaveProcedure(); LogResult(saved); '
                           'if (saved) { CallCommand(BizCommand.Search); }')
        self.assertEqual([], check_command_flow(candidate, style_reference=REFERENCE).issues)
        reference = screen('bool saved = CallSaveProcedure(); if (saved) { CallCommand(BizCommand.Search); }')
        self.assertEqual([], check_command_flow(reference, style_reference=reference).issues)

    def test_delete_uses_its_own_complete_project_phase(self):
        reference = '''void Project_DeleteCommand(object s, DeleteCommandEventArgs e) {
            m_Editmode = DataEditMode.DELETE;
            if (CallSaveProcedure()) { CallCommand(BizCommand.Search); }
        }'''
        candidate = reference.replace('if (CallSaveProcedure())',
            'bool result = CallSaveProcedure(); m_Editmode = DataEditMode.DEFAULT; if (result)')
        result = check_command_flow(candidate, style_reference=reference)
        self.assertEqual({'default_edit_mode', 'save_result_temporary'},
                         {issue.details['operation'] for issue in result.issues})

    def test_unwired_helper_and_other_objects_save_do_not_become_button_actions(self):
        helper = 'void Helper() { bool saved = CallSaveProcedure(); if (saved) { Reset(); } }'
        other = '''void Init() { btn.Click += OnClick; }
            void OnClick(object s, EventArgs e) { bool saved = other.CallSaveProcedure();
            m_Editmode = DataEditMode.DEFAULT; if (saved) { Reset(); } }'''
        for candidate in (helper, other):
            with self.subTest(candidate=candidate):
                self.assertFalse(check_command_flow(candidate, style_reference=REFERENCE).issues)

    def test_uncalled_local_and_literals_do_not_invent_temporary_result(self):
        candidate = screen('string text = "bool saved = CallSaveProcedure(); if (saved) {}"; '
            'void Local() { bool saved = CallSaveProcedure(); if (saved) { Reset(); } } '
            'if (CallSaveProcedure()) { CallCommand(BizCommand.Search); }')
        self.assertEqual([], check_command_flow(candidate, style_reference=REFERENCE).issues)

    def test_repeated_failure_is_detected_against_project_phases(self):
        candidate = screen('if (CallSaveProcedure()) { dt.AcceptChanges(); '
            'devFnc.Usr_ControlsProtect(grdList, true); m_Editmode = DataEditMode.DEFAULT; '
            'CallCommand(BizCommand.Search); }')
        result = check_command_flow(candidate, style_reference=REFERENCE)
        issues = [issue for issue in result.issues if issue.code == 'command_phase_drift_review']
        self.assertEqual({'AcceptChanges', 'control_protection', 'default_edit_mode'},
                         {issue.details['operation'] for issue in issues})
        resets = [issue for issue in issues if issue.details['operation'] != 'AcceptChanges']
        self.assertTrue(all(issue.details['reference_other_phases'] == ['search'] for issue in resets))
        self.assertEqual(['save'], result.metadata['command_flow']['compared_commands'])

    def test_project_save_pattern_is_preserved(self):
        result = check_command_flow(screen('if (CallSaveProcedure()) { ShowMessage("Saved"); '
            'CallCommand(BizCommand.Search); }'), style_reference=REFERENCE)
        self.assertEqual([], result.issues)

    def test_legitimate_save_reset_is_not_globally_prohibited(self):
        reference = screen('if (CallSaveProcedure()) { m_Editmode = DataEditMode.DEFAULT; '
            'devFnc.Usr_ControlsProtect(grdList, true); dt.AcceptChanges(); tab.SelectedPage = pageList; }')
        candidate = reference.replace('pageList', 'pageDetail')
        result = check_command_flow(candidate, style_reference=reference)
        self.assertEqual([], result.issues)

    def test_accept_changes_outside_save_is_not_banned(self):
        candidate = screen('CallCommand(BizCommand.Search);',
            'bool CallSaveProcedure() { xmlTable.AcceptChanges(); return true; }')
        self.assertEqual([], check_command_flow(candidate, style_reference=REFERENCE).issues)

    def test_modify_only_scope_rejects_added_commands(self):
        candidate = screen('CallCommand(BizCommand.Search);',
            'void Init() { this.NewCommand += OnNew; DeleteCommand += OnDelete; other.NewCommand += Other; }')
        result = check_command_flow(candidate, allowed_commands=['search', 'edit', 'save', 'clear'])
        self.assertEqual('failed', result.status)
        self.assertEqual({'new', 'delete'}, {issue.details['command'] for issue in result.issues})
        self.assertEqual(2, len(result.issues))

    def test_unwired_nonempty_handler_is_reviewed_but_empty_handler_is_not(self):
        candidate = screen('', 'void OnNew(object s, NewCommandEventArgs e) { OpenMenuProgram("A", "B", "C"); } '
            'void OnDelete(object s, DeleteCommandEventArgs e) { /* no operation */ }')
        result = check_command_flow(candidate, allowed_commands=['save'])
        self.assertEqual(['screen_command_body_out_of_scope'], [issue.code for issue in result.issues])
        self.assertEqual('new', result.issues[0].details['command'])

    def test_comments_strings_and_uncalled_local_functions_are_not_operations(self):
        candidate = screen('string sample = "dt.AcceptChanges(); NewCommand += OnNew;"; '
            '// m_Editmode = DataEditMode.DEFAULT;\n'
            'void Deferred() { dt.AcceptChanges(); devFnc.Usr_ControlsProtect(grdList, true); } '
            'CallCommand(BizCommand.Search);', '/* this.DeleteCommand += OnDelete; */')
        result = check_command_flow(candidate, style_reference=REFERENCE, allowed_commands=['save'])
        self.assertEqual([], result.issues)

    def test_new_navigation_is_compared_with_new_not_another_phase(self):
        candidate = 'void Screen_NewCommand(object s, NewCommandEventArgs e) { OpenMenuProgram("A", "B", "C"); }'
        result = check_command_flow(candidate, style_reference=REFERENCE)
        self.assertEqual('program_navigation', result.issues[0].details['operation'])
        self.assertEqual('new', result.issues[0].details['command'])

    def test_missing_refresh_requires_review_not_automatic_failure(self):
        result = check_command_flow(screen('if (CallSaveProcedure()) { tab.SelectedPage = pageList; }'),
                                    style_reference=REFERENCE)
        self.assertEqual(['save_refresh_drift_review'], [issue.code for issue in result.issues])
        self.assertEqual('passed', result.status)

    def test_unchanged_local_body_is_skipped_but_scope_still_applies(self):
        candidate = screen('dt.AcceptChanges();', 'void Init() { this.NewCommand += OnNew; }')
        result = check_command_flow(candidate, original=candidate, style_reference=REFERENCE, allowed_commands=['save'])
        self.assertEqual(['screen_command_out_of_scope'], [issue.code for issue in result.issues])
        standalone = check_command_flow(candidate, style_reference=REFERENCE)
        self.assertIn('command_phase_drift_review', [issue.code for issue in standalone.issues])

    def test_missing_ambiguous_and_unsupported_references_remain_unverified(self):
        candidate = screen('dt.AcceptChanges();')
        for reference in ('class Empty {}', REFERENCE + REFERENCE,
                          'void OnSave(object s, SaveCommandEventArgs e) => CallCommand(BizCommand.Search);'):
            result = check_command_flow(candidate, style_reference=reference)
            self.assertEqual([], result.metadata['command_flow']['compared_commands'])
            self.assertTrue(any('matching command bodies' in item for item in result.not_checked))
        missing = check_csharp(candidate)
        self.assertFalse(missing.metadata['comparison_baselines'].get('command_style_reference', False))
        self.assertFalse(missing.metadata['project_style_verified'])
        self.assertTrue(any('no same-project C#' in item for item in missing.not_checked))

    def test_invalid_operation_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            check_command_flow('class Screen {}', allowed_commands=['export'])

    def test_print_handler_and_subscription_use_explicit_scope(self):
        candidate = 'class Screen { void Init() { this.PrintCommand += OnPrint; } '
        candidate += 'void OnPrint(object s, PrintCommandEventArgs e) { PrintPages(); } }'
        self.assertEqual([], check_command_flow(candidate, allowed_commands=['print']).issues)
        result = check_command_flow(candidate, allowed_commands=['search'])
        self.assertEqual(['screen_command_out_of_scope'], [issue.code for issue in result.issues])
        self.assertEqual('print', result.issues[0].details['command'])

    def test_report_property_name_alone_does_not_create_a_style_finding(self):
        reference = 'void Screen_PrintCommand(object s, PrintCommandEventArgs e) { '
        reference += 'using (Report rpt = new Report(data)) { rpt.Print(); } }'
        candidate = reference.replace('rpt.Print();',
            'rpt.Bands[BandKind.Detail].PageBreak = PageBreak.BeforeBandExceptFirstEntry; rpt.Print();')
        result = check_command_flow(candidate, style_reference=reference)
        self.assertEqual([], result.issues)
        self.assertEqual([], result.metadata['command_flow']['compared_commands'])
        self.assertTrue(any('report behavior' in item for item in result.not_checked))
