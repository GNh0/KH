"""Counterexamples for source observation and changed artifact responsibilities."""
from pathlib import Path
import tempfile
import unittest

from src.runtime.source_evidence import control_work, observe_references, reference_problem, select_references
from src.runtime.workflows import register


class SourceEvidenceTests(unittest.TestCase):
    def test_framework_creation_and_actual_receiver_changes_expand_control_work(self):
        before = 'class Screen { void Run() { } }'
        after = 'class Screen { void Run() { DevExpress.XtraEditors.TextEdit edit = new DevExpress.XtraEditors.TextEdit(); edit.Enabled = false; } }'
        self.assertEqual({'csharp-control'}, control_work(before, after))
        peer = 'private DevExpress.XtraEditors.TextEdit edit;'
        self.assertEqual({'csharp-control'}, control_work('this.edit.Enabled = true;', 'this.edit.Enabled = false;', peer))
        self.assertEqual({'csharp-control'}, control_work('edit.Enabled = true;', 'edit.Enabled = false;', peer))
        self.assertEqual({'csharp-control'}, control_work('this.edit.Enabled = false;', '', peer))
        self.assertEqual({'csharp-grid'}, control_work('', 'var grid = new DevExpress.XtraGrid.GridControl();'))

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
