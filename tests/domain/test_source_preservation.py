import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.csharp.checks import check_csharp
from src.csharp.designer import check_designer
from src.csharp.source_preservation import remap_members
from src.csharp.flow_review import check_project_flow

ROOT = Path(__file__).resolve().parents[2]


def changes(result):
    return [i for i in result.issues if i.code == 'designer_existing_properties_changed']


class SourcePreservationTests(unittest.TestCase):
    def test_retained_properties_include_non_grid_defaults_and_removed_assignments(self):
        before = 'private InputBox txt; this.txt.Properties.AutoHeight = false; this.txt.Size = new Size(173, 21); this.txt.Properties.ReadOnly = false;'
        after = 'private InputBox txt; this.txt.Properties.AutoHeight = true; this.txt.Size = new Size(200, 25);'
        result = check_designer(after, original=before, preserve_existing=True)
        self.assertEqual(1, len(changes(result)))
        self.assertEqual({'Properties.AutoHeight', 'Properties.ReadOnly', 'Size'}, set(changes(result)[0].details['properties']))
        self.assertEqual(3, result.metadata['designer_preservation']['property_deltas'])

    def test_new_assignment_on_retained_control_is_reviewed(self):
        result = check_designer('private InputBox txt; this.txt.Enabled = false;', original='private InputBox txt;', preserve_existing=True)
        self.assertEqual(['Enabled'], changes(result)[0].details['properties'])

    def test_preserved_existing_formats_are_not_replaced_by_new_control_defaults(self):
        original = 'this.col = new GridColumn(); this.col.DisplayFormat.FormatString = "N2"; this.col.AppearanceCell.Options.UseTextOptions = true;'
        result = check_designer(original, original=original, preserve_existing=True)
        self.assertFalse(changes(result))
        self.assertNotIn('standard_numeric_format_preference', {i.code for i in result.issues})

    def test_explicit_member_mapping_preserves_names_and_repository_references(self):
        before = 'private InputBox oldInput; private RepositoryItemSpinEdit oldRps; this.oldInput.Name = "oldInput"; this.oldInput.ColumnEdit = this.oldRps; this.oldInput.Text = "oldInput";'
        after = 'private InputBox newInput; private RepositoryItemSpinEdit newRps; this.newInput.Name = "newInput"; this.newInput.ColumnEdit = this.newRps; this.newInput.Text = "oldInput";'
        result = check_designer(after, original=before, preserve_existing=True, member_renames={'oldInput': 'newInput', 'oldRps': 'newRps'})
        self.assertFalse(changes(result))
        self.assertEqual(2, result.metadata['designer_preservation']['matched_members'])

    def test_resource_key_mapping_does_not_rewrite_text_or_binding_literals(self):
        source = 'this.old.Name = "old"; this.old.Image = resources.GetObject("old.Image"); this.old.Text = "old"; this.old.BindingField = "old"; // old'
        result = remap_members(source, {'old': 'current'})
        self.assertIn('this.current.Name = "current"', result)
        self.assertIn('GetObject("current.Image")', result)
        self.assertIn('this.current.Text = "old"', result)
        self.assertIn('this.current.BindingField = "old"', result)
        self.assertTrue(result.endswith('// old'))

    def test_removed_and_new_controls_are_reported_outside_retained_property_proof(self):
        before = 'private InputBox keep; private InputBox removed; this.keep.Enabled = true;'
        after = 'private InputBox keep; private InputBox added; this.keep.Enabled = true;'
        result = check_designer(after, original=before, preserve_existing=True)
        self.assertFalse(changes(result))
        self.assertEqual(['removed'], result.metadata['designer_preservation']['unmatched_original_members'])
        self.assertEqual(['added'], result.metadata['designer_preservation']['new_members'])

    def test_unmatched_baseline_and_missing_baseline_are_incomplete(self):
        source = 'private InputBox current;'
        for original in [None, 'private InputBox previous;']:
            with self.subTest(original=original):
                self.assertEqual('incomplete', check_designer(source, original=original, preserve_existing=True).status)

    def test_mapping_rejects_unknown_members_and_collisions(self):
        for mapping in [{'absent': 'c'}, {'a': 'b'}, {'a': 'c', 'b': 'c'}]:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                check_designer('private InputBox c;', original='private InputBox a; private InputBox b;', member_renames=mapping)

    def test_bound_exception_does_not_hide_other_changes_or_explicit_preservation_error(self):
        before = 'this.txt.BindingField = "DOC"; this.txt.Enabled = true;'
        after = 'this.txt.BindingField = "ORDER"; this.txt.Enabled = false;'
        result = check_designer(after, original=before, preserve_existing=True, allowed_property_changes=['txt.BindingField'])
        self.assertEqual(['Enabled'], changes(result)[0].details['properties'])
        explicit = check_designer(after, original=before, preserve_existing=True, preserved_properties=['txt.BindingField'], allowed_property_changes=['txt.BindingField'])
        self.assertEqual('failed', explicit.status)

    def test_form_properties_and_control_types_are_compared(self):
        result = check_designer('private OtherBox txt; this.ClientSize = new Size(200, 100);',
                                original='private InputBox txt; this.ClientSize = new Size(100, 100);', preserve_existing=True)
        found = {i.details['member']: i.details['properties'] for i in changes(result)}
        self.assertEqual(['type'], found['txt'])
        self.assertEqual(['ClientSize'], found['form'])

    def test_csharp_entrypoint_forwards_preservation_and_separate_baselines(self):
        result = check_csharp('class X {}', original='class X {}', designer='this.current.Size = new Size(2, 3);',
                              original_designer='this.previous.Size = new Size(1, 3);', preserve_existing=True,
                              member_renames={'previous': 'current'})
        self.assertEqual({'csharp': True, 'designer': True}, result.metadata['comparison_baselines'])
        self.assertEqual(1, result.metadata['designer_preservation']['property_deltas'])
        self.assertEqual('needs_review', result.metadata['review_status'])
        self.assertEqual({'csharp': False, 'designer': False}, check_csharp('class X {}').metadata['comparison_baselines'])


class StatePolicyTests(unittest.TestCase):
    def codes(self, after, before=''):
        return {i.code for i in check_project_flow(after, original=before)}

    def test_new_boolean_changes_attachment_mode_and_button_availability(self):
        source = 'class Screen { bool pending = false; void Attach() { pop.m_Editmode = mode == DEFAULT || pending ? DEFAULT : EDIT; btnDelete.Enabled = !pending; } }'
        self.assertIn('ui_state_policy_review', self.codes(source))
        issue = next(i for i in check_project_flow(source, original='') if i.code == 'ui_state_policy_review')
        self.assertEqual('Screen.pending', issue.details['method'])

    def test_original_state_policy_is_preserved_but_extension_to_another_action_is_reviewed(self):
        before = 'class Screen { bool pending; void Delete() { if (pending) { return; } } void Attach() { pop.ShowDialog(); } }'
        after = before.replace('pop.ShowDialog();', 'pop.ReadOnly = pending; pop.ShowDialog();')
        self.assertNotIn('ui_state_policy_review', self.codes(before, before))
        self.assertIn('ui_state_policy_review', self.codes(after, before))

    def test_explicitly_requested_state_remains_a_review_not_a_ban(self):
        source = 'class Screen { bool pending; void Changed(bool value) { pending = value; btnDelete.Enabled = !pending; } }'
        result = check_csharp(source, original='class Screen {}')
        self.assertTrue(result.success)
        self.assertEqual('needs_review', result.metadata['review_status'])

    def test_local_bool_constant_and_non_ui_calculation_are_not_screen_policies(self):
        cases = [
            'class Screen { void Run() { bool pending = false; btn.Enabled = !pending; } }',
            'class Screen { const bool pending = false; void Run() { btn.Enabled = !pending; } }',
            'class Screen { bool valid; int Count() { return valid ? 1 : 0; } }',
            'class Screen { bool pending; void Run(bool pending) { btn.Enabled = pending; } }',
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertNotIn('ui_state_policy_review', self.codes(case))

    def test_qualified_field_remains_visible_when_local_name_is_shadowed(self):
        source = 'class Screen { bool pending; void Run(bool pending) { btn.Enabled = this.pending; } }'
        self.assertIn('ui_state_policy_review', self.codes(source))

    def test_protection_api_and_guarded_updates_are_policy_uses(self):
        for operation in ['devFnc.Usr_ControlsProtect(panel, pending);', 'if (!pending) { txtKey.Text = value; }', 'if (pending) { e.Cancel = true; }']:
            with self.subTest(operation=operation):
                self.assertIn('ui_state_policy_review', self.codes('class Screen { bool pending; void Run() { ' + operation + ' } }'))


class BaselineCliTests(unittest.TestCase):
    def run_check(self, *args):
        result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), *map(str, args)], capture_output=True, text=True, encoding='utf-8')
        return result.returncode, json.loads(result.stdout)

    def test_same_file_is_not_accepted_as_its_own_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.cs'
            path.write_text('class Screen {}', encoding='utf-8')
            for args in [('csharp', path, '--original', path), ('designer', path, '--original', path), ('sql', path, path),
                         ('csharp', path, '--designer', path, '--designer-original', path)]:
                with self.subTest(args=args):
                    status, data = self.run_check(*args)
                    self.assertEqual(1, status)
                    self.assertIn('same file', data['issues'][0]['message'])

    def test_hard_link_cannot_be_used_as_a_separate_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            original, alias = Path(folder)/'before.sql', Path(folder)/'alias.sql'
            original.write_text('SELECT 1', encoding='utf-8')
            try:
                os.link(original, alias)
            except OSError as error:
                self.skipTest(str(error))
            self.assertEqual(1, self.run_check('sql', original, alias)[0])

    def test_separate_equal_snapshots_and_single_file_inspection_are_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            before, after = Path(folder)/'before.sql', Path(folder)/'after.sql'
            for path in (before, after):
                path.write_text('SELECT 1', encoding='utf-8')
            status, compared = self.run_check('sql', before, after)
            self.assertEqual(0, status)
            self.assertEqual({'sql': True}, compared['comparison_baselines'])
            status, inspected = self.run_check('sql', after)
            self.assertEqual(0, status)
            self.assertEqual({'sql': False}, inspected['comparison_baselines'])

    def test_cli_exposes_name_aware_preservation_without_mutating_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            before, after = Path(folder)/'before.cs', Path(folder)/'after.cs'
            before.write_text('this.old.Name = "old"; this.old.Size = new Size(1, 2);', encoding='utf-8')
            after.write_text('this.current.Name = "current"; this.current.Size = new Size(1, 2);', encoding='utf-8')
            snapshots = [p.read_bytes() for p in (before, after)]
            status, data = self.run_check('designer', after, '--original', before, '--preserve-existing', '--member-rename', 'old=current')
            self.assertEqual(0, status)
            self.assertEqual(0, data['designer_preservation']['property_deltas'])
            self.assertEqual(snapshots, [p.read_bytes() for p in (before, after)])


if __name__ == '__main__':
    unittest.main()
