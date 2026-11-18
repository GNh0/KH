"""Counterexamples for source observation and changed artifact responsibilities."""
from pathlib import Path
import tempfile
import unittest

from src.runtime.source_evidence import control_work, observe_references, reference_problem, select_references, read_paths, observed_comparisons
from src.runtime.workflows import register
from src.runtime.hooks import inspect


class SourceEvidenceTests(unittest.TestCase):
    def test_indexed_and_method_control_operations_are_observed_without_dto_name_guessing(self):
        peer = 'private DevExpress.XtraEditors.ButtonEdit button; private DevExpress.XtraGrid.Views.Grid.GridView view; private System.Windows.Forms.Panel panel;'
        for statement, kind in [('this.button.Properties.Buttons[0].Enabled = false;', 'csharp-control'),
                                ('this.view.TileTemplate[0].Appearance.Normal.Font = fontUser;', 'csharp-grid'),
                                ('this.panel.Controls.Add(this.button);', 'csharp-control'),
                                ('this.view.BestFitColumns();', 'csharp-grid')]:
            self.assertIn(kind, control_work('', statement, peer), statement)
        self.assertEqual(set(), control_work('', 'dto.Buttons[0].Enabled = false; helper.ApplyGridControlFont(dto, font);'))
        for statement in ('return this.view.GetFocusedDataRow();', 'return this.view.ToString();', 'return GetDataTable(this.view);'):
            self.assertEqual(set(), control_work('', statement, peer), statement)

    def test_blank_boundaries_and_standard_powershell_reads_preserve_provenance(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'Reference.cs'
            target = Path(folder) / 'Screen.cs'
            body = '\nclass Reference\n\n{\n int Read() { return 1; }\n\n}\n\n'
            source.write_text(body, encoding='utf-8')
            for command in (f"Get-Content -Encoding UTF8 -LiteralPath '{source}'", f"Get-Content -Raw '{source}'", f"(Get-Content '{source}')[0..50]", f"Get-Content -TotalCount 50 -Path '{source}'"):
                state = {'application_epoch': 'current'}
                applied = register(state, epoch='current', work=['csharp-code'], targets=[str(target)], cwd=folder)
                select_references(state, applied, [str(source)], folder)
                event = {'cwd': folder, 'tool_name': 'exec_command', 'tool_input': {'cmd': command}}
                self.assertEqual([source.resolve()], read_paths(event))
                observe_references(state, '\n'.join(body.splitlines()[:4]).strip(), event)
                self.assertTrue(reference_problem(state, target))
                observe_references(state, '\n'.join(body.splitlines()[4:]).strip(), event)
                self.assertEqual('', reference_problem(state, target))
                bodies, _dependencies, problems = observed_comparisons(state, target)
                self.assertIn('class Reference', bodies['csharp'])
                self.assertEqual([], problems)

    def test_framework_creation_and_actual_receiver_changes_expand_control_work(self):
        before = 'class Screen { void Run() { } }'
        after = 'class Screen { void Run() { DevExpress.XtraEditors.TextEdit edit = new DevExpress.XtraEditors.TextEdit(); edit.Enabled = false; } }'
        self.assertEqual({'csharp-control'}, control_work(before, after))
        peer = 'private DevExpress.XtraEditors.TextEdit edit;'
        self.assertEqual({'csharp-control'}, control_work('this.edit.Enabled = true;', 'this.edit.Enabled = false;', peer))
        self.assertEqual({'csharp-control'}, control_work('edit.Enabled = true;', 'edit.Enabled = false;', peer))
        self.assertEqual({'csharp-control'}, control_work('this.edit.Enabled = false;', '', peer))
        self.assertEqual({'csharp-grid'}, control_work('', 'var grid = new DevExpress.XtraGrid.GridControl();'))

    def test_overlapping_and_out_of_order_source_reads_only_credit_returned_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'Reference.cs'
            target = Path(folder) / 'Candidate.cs'
            lines = ['class Reference', '{', ' int Read;', ' int Write;', '}']
            source.write_text('\n'.join(lines), encoding='utf-8')
            for first, second in ((lines[:3], lines[2:]), (lines[3:], lines[:3])):
                state = {'application_epoch': 'current'}
                applied = register(state, epoch='current', work=['csharp-code'], targets=[str(target)], cwd=folder)
                select_references(state, applied, [str(source)], folder)
                event = {'cwd': folder, 'tool_name': 'Read', 'tool_input': {'file_path': str(source)}}
                observe_references(state, '\n'.join(first), event)
                observe_references(state, '\n'.join(first), event)
                self.assertTrue(reference_problem(state, target))
                observe_references(state, '\n'.join(second), event)
                self.assertEqual('', reference_problem(state, target))
            lines = ['first', 'same', 'middle', 'same', 'last']
            source.write_text('\n'.join(lines), encoding='utf-8')
            state = {'application_epoch': 'current'}
            applied = register(state, epoch='current', work=['csharp-code'], targets=[str(target)], cwd=folder)
            select_references(state, applied, [str(source) + '#L4-L4'], folder)
            observe_references(state, 'same', event)
            self.assertTrue(reference_problem(state, target))
            observe_references(state, '4: same', event)
            self.assertEqual('', reference_problem(state, target))

    def test_control_and_grid_layouts_reach_both_saved_file_entry_points(self):
        layout = 'this.lbl = new DevExpress.XtraEditors.LabelControl();\nthis.lbl.Size = new Size(110, 39);'
        grid = 'this.view = new DevExpress.XtraGrid.Views.Grid.GridView();\nthis.view.OptionsSelection.MultiSelect = true;'
        with tempfile.TemporaryDirectory() as folder:
            for target_name in ('Screen.cs', 'Screen.Designer.cs'):
                target = Path(folder) / target_name
                state = {'application_epoch': 'current'}
                work = ['csharp-control', 'csharp-grid']
                applied = register(state, epoch='current', work=work, targets=[str(target)], cwd=folder)
                for role, body in zip(work, (layout, grid)):
                    reference = Path(folder) / (role + '.Designer.cs')
                    reference.write_text(body, encoding='utf-8')
                    select_references(state, applied, [str(reference)], folder, work=[role])
                    observe_references(state, body, {'cwd': folder, 'tool_name': 'Read', 'tool_input': {'file_path': str(reference)}})
                self.assertEqual('', reference_problem(state, target))
                comparisons, _, problems = observed_comparisons(state, target)
                self.assertEqual([], problems)
                design = layout + '\n' + grid
                def check(body):
                    code, peer = ('class Screen {}', body) if target_name == 'Screen.cs' else (body, 'class Screen {}')
                    return inspect(target, code, original='', peer=peer, original_peer='', style_comparisons=comparisons)
                good = check(design)
                self.assertTrue(good['comparison_baselines']['style_reference'])
                self.assertNotIn('grid_option_outside_baseline', good['warnings'])
                wrong = check(design.replace('110, 39', '110, 29').replace('MultiSelect = true', 'MultiSelect = false'))
                self.assertIn('label_height_mismatch', wrong['errors'])
                self.assertIn('grid_option_outside_baseline', wrong['warnings'])

    def test_literals_comments_dtos_and_unchanged_controls_do_not_expand_work(self):
        source = 'class Screen { void Run() { DevExpress.XtraEditors.TextEdit edit = new DevExpress.XtraEditors.TextEdit(); } int Read() { return 1; } }'
        self.assertEqual(set(), control_work(source, source.replace('return 1', 'return 2')))
        self.assertEqual(set(), control_work('', 'var dto = new Payload(); dto.Enabled = false; // new DevExpress.XtraEditors.TextEdit()\n string text = "new DevExpress.XtraEditors.TextEdit()";'))
        self.assertEqual(set(), control_work('', 'var timer = new System.Windows.Forms.Timer(); var settings = new DevExpress.XtraEditors.SomeOptions();'))
        self.assertEqual(set(), control_work('void Run(Payload edit) { edit.Enabled = true; }', 'void Run(Payload edit) { edit.Enabled = false; }', 'private DevExpress.XtraEditors.TextEdit edit;'))

    def test_explicit_alias_and_global_framework_types_remain_observable(self):
        self.assertEqual({'csharp-control'}, control_work('', 'using E = DevExpress.XtraEditors; class Screen { void Run() { var edit = new E.TextEdit(); } }'))
        self.assertEqual({'csharp-control'}, control_work('', 'var edit = new global::DevExpress.XtraEditors.TextEdit();'))

    def test_comparison_registration_does_not_certify_read_and_changes_invalidate_it(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            target = directory / 'Screen.cs'
            source = directory / 'Reference.cs'
            source.write_text('class Reference\n{\n    int Read() { return 1; }\n}\n', encoding='utf-8')
            state = {'application_epoch': 'current'}
            applied = register(state, epoch='current', work=['csharp-code'], targets=[str(target)], cwd=folder)
            select_references(state, applied, [str(source) + '#L2-L4'], folder)
            event = {'cwd': folder, 'tool_name': 'Read', 'tool_input': {'file_path': str(source)}}
            self.assertTrue(reference_problem(state, target))
            observe_references(state, source.read_text(), {**event, 'tool_input': {'file_path': str(target)}})
            self.assertTrue(reference_problem(state, target))
            observe_references(state, '2: {\n3:     int Read() { return 1; }\n', event)
            self.assertTrue(reference_problem(state, target))
            observe_references(state, 'tool metadata\n4: }\n', event)
            self.assertEqual('', reference_problem(state, target))
            source.write_text(source.read_text().replace('return 1', 'return 2'), encoding='utf-8')
            observe_references(state, source.read_text(), event)
            self.assertTrue(reference_problem(state, target))
            select_references(state, applied, [str(source) + '#L2-L4'], folder)
            self.assertTrue(reference_problem(state, target))
            observe_references(state, source.read_text(), event)
            self.assertEqual('', reference_problem(state, target))
            register(state, epoch='current', work=['csharp-code'], targets=[str(source)], cwd=folder)
            self.assertTrue(reference_problem(state, target))

    def test_owned_outputs_cannot_be_their_own_comparison(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'Screen.cs'
            source.write_text('class Screen { }', encoding='utf-8')
            state = {'application_epoch': 'current'}
            applied = register(state, epoch='current', work=['csharp-code'], targets=[str(source)], cwd=folder)
            with self.assertRaises(ValueError):
                select_references(state, applied, [str(source)], folder)
