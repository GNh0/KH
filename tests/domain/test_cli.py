import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CliTests(unittest.TestCase):
    def test_command_style_and_operation_scope_are_available_without_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            source, reference = Path(folder)/'screen.cs', Path(folder)/'project.cs'
            source.write_text('class Screen { void Init() { this.NewCommand += OnNew; } '
                'void OnSave(object s, SaveCommandEventArgs e) { dt.AcceptChanges(); } }', encoding='utf-8')
            reference.write_text('void OnSave(object s, SaveCommandEventArgs e) { CallCommand(BizCommand.Search); }', encoding='utf-8')
            before = {path: path.read_bytes() for path in (source, reference)}
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'csharp', str(source),
                '--style-reference-csharp', str(reference), '--screen-command', 'search', '--screen-command', 'save'],
                cwd=folder, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(1, result.returncode, result.stderr)
            output = json.loads(result.stdout)
            self.assertTrue(output['comparison_baselines']['command_style_reference'])
            self.assertEqual(['save', 'search'], output['command_flow']['allowed_commands'])
            self.assertLessEqual({'screen_command_out_of_scope', 'command_phase_drift_review', 'save_refresh_drift_review'},
                                 {issue['code'] for issue in output['issues']})
            self.assertTrue(all(path.read_bytes() == content for path, content in before.items()))
            self.assertEqual({'screen.cs', 'project.cs'}, {path.name for path in Path(folder).iterdir()})

    def test_command_style_reference_cannot_be_candidate_itself(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'screen.cs'
            source.write_text('class Screen {}', encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'csharp', str(source),
                '--style-reference-csharp', str(source)], cwd=folder, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(1, result.returncode)
            self.assertEqual('input_error', json.loads(result.stdout)['issues'][0]['code'])

    def test_print_query_and_save_contract_comparison_runs_from_another_directory(self):
        from tests.domain.test_save_contract import BATCH, ROWWISE, SCALAR_SELECT, XML_SELECT
        with tempfile.TemporaryDirectory() as folder:
            source, reference = Path(folder)/'screen.cs', Path(folder)/'project.cs'
            candidate = ROWWISE.replace('class Screen {', 'class Screen {' + XML_SELECT)
            candidate = candidate.replace('rpt.Print();', 'rpt.Detail.PageBreak = PageBreak.BeforeBand; rpt.Print();')
            source.write_text(candidate, encoding='utf-8')
            reference.write_text(BATCH.replace('class Screen {', 'class Screen {' + SCALAR_SELECT), encoding='utf-8')
            before = {path: path.read_bytes() for path in (source, reference)}
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'csharp', str(source),
                '--style-reference-csharp', str(reference), '--screen-command', 'print'],
                cwd=folder, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(['print'], output['command_flow']['allowed_commands'])
            self.assertTrue(output['save_contract_comparison']['compared'])
            self.assertTrue(output['select_contract_comparison']['compared'])
            self.assertLessEqual({'save_xml_contract_drift_review', 'save_output_contract_drift_review',
                                 'rowwise_save_contract_drift_review', 'select_xml_contract_drift_review',
                                 'command_phase_drift_review'},
                                {issue['code'] for issue in output['issues']})
            self.assertEqual('needs_review', output['review_status'])
            self.assertTrue(all(path.read_bytes() == content for path, content in before.items()))
            self.assertEqual({'screen.cs', 'project.cs'}, {path.name for path in Path(folder).iterdir()})

    def test_standalone_csharp_reports_save_and_input_contract_review(self):
        with tempfile.TemporaryDirectory() as folder:
            source, designer = Path(folder)/'screen.cs', Path(folder)/'screen.Designer.cs'
            source.write_text('class Screen { bool CallSaveProcedure() { '
                'gvwList.PostEditor(); db.ExecSPTrn("sp_SAMPLE_SAVE", new DbParameter("@WORKTYPE", "MOD"), '
                'new DbParameter("@USERID", btnUser.Tag)); return true; } }', encoding='utf-8')
            designer.write_text('private KoneLib.Controls.u_ButtonEdit btnUser;', encoding='utf-8')
            before = source.read_bytes()
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'csharp', str(source),
                '--designer', str(designer)], cwd=folder, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual('needs_review', output['review_status'])
            self.assertLessEqual({'save_worktype_literal_review', 'input_tag_binding_review', 'new_edit_commit_call'},
                                 {issue['code'] for issue in output['issues']})
            self.assertFalse(output['project_style_verified'])
            self.assertEqual(before, source.read_bytes())

    def test_bom_crlf_input_from_an_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original, candidate = root/'original.sql', root/'candidate.sql'
            original.write_bytes('\ufeffSELECT A.ID\r\nFROM ORDERS A\r\nWHERE A.NOTE = N\'한글\';\r\n'.encode('utf-8'))
            candidate.write_text("SELECT A.ID\nFROM ORDERS A\nWHERE A.NOTE = N'한글';\n", encoding='utf-8')
            before = original.read_bytes()
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'sql', str(original), str(candidate)], cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual('passed', json.loads(result.stdout)['status'])
            self.assertEqual(before, original.read_bytes())
            self.assertEqual({'original.sql', 'candidate.sql'}, {p.name for p in root.iterdir()})

    def test_changed_sql_returns_failure_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original, candidate = root/'original.sql', root/'candidate.sql'
            original.write_text('SELECT 1')
            candidate.write_text('SELECT 2')
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'sql', str(original), str(candidate)], cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(1, result.returncode)
            self.assertIn('sql_meaning_tokens_changed', [i['code'] for i in json.loads(result.stdout)['issues']])

    def test_empty_sql_is_incomplete(self):
        from src.sql.checks import check_sql
        self.assertEqual('incomplete', check_sql('-- comment only').status)

    def test_designer_property_contract_is_available_from_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original, candidate = root/'before.cs', root/'after.cs'
            original.write_bytes(b'this.label.Text = "ready\\nnext"; this.label.Visible = false;')
            candidate.write_bytes(b'this.label.Text = @"ready\r\nnext"; this.label.Visible = true;')
            command = [sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'designer', str(candidate),
                       '--original', str(original), '--preserve-property', 'label.Text', '--preserve-property', 'label.Visible']
            result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(1, result.returncode, result.stderr)
            issues = json.loads(result.stdout)['issues']
            self.assertEqual(2, sum(item['code'] == 'user_property_changed' for item in issues))

    def test_sp_call_cli_preserves_parameter_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            call, procedure = root/'call.cs', root/'save.sql'
            call.write_text('new global::App.Data.DbParameter("KEY", 1)', encoding='utf-8')
            procedure.write_text('CREATE PROC dbo.Save @KEY int, @MSG nvarchar(10) OUTPUT AS SELECT @KEY', encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'sp-call', str(call), str(procedure)],
                                     cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(1, result.returncode, result.stderr)
            output = json.loads(result.stdout)
            self.assertIn('required_sp_parameter_missing', [item['code'] for item in output['issues']])
            self.assertTrue(any('OUTPUT' in item for item in output['not_checked']))

    def test_column_mode_and_specific_option_exception_are_available(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'screen.cs'
            source.write_text('this.col = new GridColumn(); this.col.OptionsColumn.AllowEdit = false; this.view = new GridView(); this.view.OptionsBehavior.ReadOnly = true;', encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'designer', str(source),
                '--column-mode', 'col=action', '--allow-property-change', 'view.OptionsBehavior.ReadOnly'],
                cwd=folder, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(1, result.returncode, result.stderr)
            codes = {item['code'] for item in json.loads(result.stdout)['issues']}
            self.assertIn('column_edit_mode_mismatch', codes)
            self.assertNotIn('grid_options_behavior_change', codes)

    def test_current_user_control_source_is_available_to_both_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            source, library = Path(folder)/'screen.cs', Path(folder)/'Control.cs'
            source.write_text('this.txtName = new Widgets.InputBox(); this.txtName.Properties.AutoHeight = true;', encoding='utf-8')
            library.write_text('namespace Widgets { public class InputBox : TextEdit { public InputBox() { base.Properties.AutoHeight = false; } } }', encoding='utf-8')
            before = library.read_bytes()
            for command in ('designer', 'csharp'):
                result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), command, str(source),
                    '--control-source', str(library)], cwd=folder, capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn('user_control_default_override', {i['code'] for i in json.loads(result.stdout)['issues']})
            self.assertEqual(before, library.read_bytes())

    def test_style_reference_and_constructor_size_are_available_from_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            screen, reference, library = root/'screen.Designer.cs', root/'reference.Designer.cs', root/'LookupBox.cs'
            screen.write_text('this.cboName = new Widgets.LookupBox(); this.cboName.Size = new Size(110, 25);', encoding='utf-8')
            reference.write_text('this.cboRef = new Widgets.LookupBox(); this.cboRef.Properties.Buttons.AddRange(new EditorButton[] { new EditorButton() });', encoding='utf-8')
            library.write_text('namespace Widgets { public class LookupBox : DevExpress.XtraEditors.LookUpEdit { public LookupBox() { base.Size = new Size(150, 23); } } }', encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'designer', str(screen),
                '--style-reference-designer', str(reference), '--control-source', str(library)],
                cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(1, result.returncode, result.stderr)
            output = json.loads(result.stdout)
            self.assertTrue(output['comparison_baselines']['style_reference'])
            self.assertIn('user_control_size_shrink', {item['code'] for item in output['issues']})
            self.assertIn('editor_button_initialization_review', {item['code'] for item in output['issues']})


    def test_numeric_column_and_exemption_scope_are_reported_by_both_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'screen.cs'
            source.write_text('this.colList_QTY = new GridColumn(); this.rpsSpinQTY = new RepositoryItemSpinEdit(); this.rpsSpinQTY.Mask.EditMask = "N0";', encoding='utf-8')
            original = source.read_bytes()
            for command in ('designer', 'csharp'):
                result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), command, str(source),
                    '--numeric-column', 'colList_QTY', '--allow-property-change', 'rpsSpinQTY.Mask.EditMask'],
                    cwd=folder, capture_output=True, text=True, encoding='utf-8')
                self.assertEqual(0, result.returncode, result.stderr)
                data = json.loads(result.stdout)
                self.assertIn('numeric_column_spin_editor_missing', {i['code'] for i in data['issues']})
                self.assertEqual(['rpsSpinQTY.Mask.EditMask'], data['style_exemptions'])
            self.assertEqual(original, source.read_bytes())


if __name__ == '__main__':
    unittest.main()
