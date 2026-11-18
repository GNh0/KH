"""Preserve observed role/source boundaries; not a host execution evaluation."""
import hashlib
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

from src.maintenance.agents import export_agents
from src.runtime.source_evidence import select_references, observe_references, reference_problem, observed_comparisons, observed_control_sources
from src.runtime.workflows import register
from src.pb.source import parse_pb_export
from src.pb.sql import check_sp_call
from src.csharp.designer import check_designer
from src.context.transcript import capture
from src.sql.procedure_authorship import review_procedure_headers


ROOT = Path(__file__).resolve().parents[2]


class AgentLinkageTests(unittest.TestCase):
    def read_reference(self, state, path):
        observe_references(state, path.read_text(encoding='utf-8'),
                           {'cwd': str(path.parent), 'tool_name': 'Read',
                            'tool_input': {'file_path': str(path)}, 'tool_response': {'exit_code': 0}})

    def test_actual_role_export_is_parseable_and_preserves_customization(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'agents'
            result = export_agents(ROOT, output)
            self.assertEqual(result, export_agents(ROOT, output))
            self.assertEqual('unverified', result['host_discovery'])
            self.assertEqual('unverified', result['invocation'])
            for name in result['agents']:
                value = tomllib.loads((output / (name + '.toml')).read_text(encoding='utf-8'))
                self.assertEqual(name, value['name'])
                self.assertNotIn('model', value)  # User/session model choices remain inherited.
                self.assertIn(ROOT.as_posix(), value['developer_instructions'])
            target = output / 'kh-rule-auditor.toml'
            target.write_text(target.read_text(encoding='utf-8') + '\n# User customization\n', encoding='utf-8')
            before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()}
            with self.assertRaisesRegex(ValueError, 'customized'):
                export_agents(ROOT, output)
            self.assertEqual(before, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()})

    def test_pb_source_and_output_style_have_separate_responsibilities(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            target, source, style = (base / name for name in ('Target.cs', 'Source.sru', 'Style.cs'))
            source.write_text('global function integer days();\nreturn 14\nend function\n', encoding='utf-8')
            style.write_text('class Style { int Days() { return 7; } }', encoding='utf-8')
            state = {'application_epoch': 'current'}
            applied = register(state, epoch='current', work=['pb-migrate', 'csharp-code'], targets=[str(target)], cwd=folder)
            select_references(state, applied, [str(style)], folder)
            self.read_reference(state, style)
            self.assertIn('pb-migrate', reference_problem(state, target))
            select_references(state, applied, [str(source)], folder)
            self.assertIn('pb-migrate', reference_problem(state, target))
            self.read_reference(state, source)
            self.assertEqual('', reference_problem(state, target))

    def test_query_and_print_references_remain_bound_to_their_own_responsibilities(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            target, query, report = (base / name for name in ('Target.cs', 'Query.cs', 'Print.cs'))
            query.write_text('class Query { int Search() { return 1; } }', encoding='utf-8')
            report.write_text('class Print { void Preview() {} }', encoding='utf-8')
            state = {'application_epoch': 'current'}
            for work, reference in [('csharp-data', query), ('csharp-report', report)]:
                applied = register(state, epoch='current', work=[work], targets=[str(target)], cwd=folder)
                select_references(state, applied, [str(reference)], folder, work=[work])
                self.read_reference(state, reference)
            self.assertEqual('', reference_problem(state, target))
            bodies, dependencies, problems = observed_comparisons(state, target)
            self.assertEqual([], problems)
            self.assertIn('Search()', bodies['csharp:csharp-data'])
            self.assertIn('Preview()', bodies['csharp:csharp-report'])
            self.assertEqual({query.resolve(), report.resolve()}, {Path(item['path']).resolve() for item in dependencies})

    def test_select_only_and_truncated_procedures_do_not_establish_save_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            target, reference = Path(folder) / 'Target.sql', Path(folder) / 'Reference.sql'
            state = {'application_epoch': 'current', 'sql_authorship': {'author': 'Writer', 'reference_author': 'Writer'}}
            header = '-- AUTHOR: Writer\n-- CREATE DATE: 2026-11-18\n-- DESCRIPTION: Example processing\nCREATE PROC dbo.Example AS\n'
            for body, accepted in [('BEGIN SELECT 1; END', False), ('BEGIN UPDATE EXAMPLE_ROWS SET VALUE = 1;', False),
                                   ('BEGIN UPDATE EXAMPLE_ROWS SET VALUE = 1; END', True)]:
                reference.write_text(header + body, encoding='utf-8')
                applied = register(state, epoch='current', work=['sql-save'], targets=[str(target)], cwd=folder)
                select_references(state, applied, [str(reference)], folder, work=['sql-save'])
                self.read_reference(state, reference)
                self.assertEqual(accepted, not bool(reference_problem(state, target)), body)

    def test_pb_typed_dataobject_and_optional_parameter_as_syntax(self):
        source = 'global type w_sample from window\nend type\ntype dw_rows from datawindow within w_sample\nstring dataobject = "d_rows"\nend type\n'
        self.assertEqual(['d_rows'], parse_pb_export(source).dataobjects)
        sql = 'CREATE PROC dbo.P @ITEM AS INT, @SITE /* type */ AS INT AS SELECT @ITEM, @SITE;'
        self.assertTrue(check_sp_call('new DbParameter("ITEM", 1); new DbParameter("SITE", 2);', sql).success)
        self.assertFalse(check_sp_call('new DbParameter("ITEM", 1);', sql).success)

    def test_final_width_setters_enforce_the_same_constructor_floor(self):
        before = ('partial class Screen { private u_TextEdit txtItem; void InitializeComponent() { '
                  'this.txtItem = new u_TextEdit(); this.txtItem.Size = new System.Drawing.Size(150, 25); } }')
        defaults = 'public class u_TextEdit : DevExpress.XtraEditors.TextEdit { public u_TextEdit() { base.Size = new System.Drawing.Size(150, 25); } }'
        for setter, shrinks in [('Width = 60', True), ('Bounds = new System.Drawing.Rectangle(0, 0, 60, 25)', True),
                                 ('Width = 160', False), ('Size = new System.Drawing.Size(160, 25)', False)]:
            candidate = before.replace('; } }', '; this.txtItem.' + setter + '; } }')
            result = check_designer(candidate, original=before, control_sources=[defaults], style_reference=before)
            self.assertEqual(shrinks, any(issue.code == 'user_control_size_shrink' for issue in result.issues), setter)

    def test_native_child_transcript_preserves_its_parent_scope_without_importing_another_child(self):
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / 'child.jsonl'
            event = {'cwd': folder, 'session_id': 'parent', 'agent_id': 'child', 'transcript_path': str(log)}
            for meta, accepted in [({'id': 'child', 'session_id': 'parent', 'parent_thread_id': 'parent'}, True),
                                   ({'id': 'other', 'session_id': 'parent', 'parent_thread_id': 'parent'}, False),
                                   ({'id': 'parent'}, False)]:
                records = [{'type': 'session_meta', 'payload': meta},
                           {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': 'Keep current requested scope.'}}]
                log.write_text(''.join(json.dumps(record) + '\n' for record in records), encoding='utf-8')
                state = {'users': [], 'files': {}, 'skills_seen': []}
                capture(state, event, 'codex')
                self.assertEqual(accepted, bool(state['users']))
                self.assertEqual(not accepted, bool(state.get('capture_warning')))

    def test_constructor_source_is_not_a_layout_and_observed_defaults_are_forwarded(self):
        with tempfile.TemporaryDirectory() as folder:
            target, controls, layout = (Path(folder) / name for name in ('Target.Designer.cs', 'Controls.cs', 'Layout.cs'))
            controls.write_text('class u_Input : DevExpress.XtraEditors.TextEdit { public u_Input() { this.Size = new System.Drawing.Size(150, 25); this.Appearance.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Far; } }', encoding='utf-8')
            layout.write_text('partial class Reference { private u_Input txtItem; void InitializeComponent() { this.txtItem = new u_Input(); this.txtItem.Size = new System.Drawing.Size(150, 25); } }', encoding='utf-8')
            state = {'application_epoch': 'current'}
            applied = register(state, epoch='current', work=['csharp-control'], targets=[str(target)], cwd=folder)
            select_references(state, applied, [str(controls)], folder)
            self.read_reference(state, controls)
            self.assertIn('csharp-designer', reference_problem(state, target))
            select_references(state, applied, [str(layout)], folder)
            self.read_reference(state, layout)
            self.assertEqual('', reference_problem(state, target))
            bodies, dependencies, problems = observed_control_sources(state, target)
            self.assertEqual([], problems)
            self.assertEqual([controls.read_text(encoding='utf-8')], bodies)
            self.assertEqual([controls.resolve()], [Path(item['path']).resolve() for item in dependencies])
            compared, _dependencies, problems = observed_comparisons(state, target)
            self.assertEqual([], problems)
            self.assertIn('InitializeComponent', compared['designer'])  # Source role, not filename suffix.

    def test_unchanged_adjacent_sp_is_preserved_but_changed_or_new_sp_requires_its_header(self):
        active = ('-- =============================================\n-- AUTHOR: Writer\n-- CREATE DATE: 2026-11-18\n'
                  '-- DESCRIPTION: Example \uC870\uD68C\n-- =============================================\nCREATE PROC dbo.Active AS SELECT 1;\n')
        original = active + 'GO\nCREATE PROC dbo.Legacy AS SELECT 3;\n'
        candidate = original.replace('SELECT 1;', 'SELECT 2;')
        self.assertEqual([], review_procedure_headers(candidate, original, author='Writer', changed_only=True))
        changed = review_procedure_headers(candidate.replace('SELECT 3;', 'SELECT 4;'), original, author='Writer', changed_only=True)
        self.assertTrue(any(issue.code == 'procedure_header_required' and issue.details['procedure'].upper() == 'DBO.LEGACY' for issue in changed))
        added = review_procedure_headers(candidate + 'GO\nCREATE PROC dbo.NewOne AS SELECT 5;\n', original, author='Writer', changed_only=True)
        self.assertTrue(any(issue.code == 'procedure_header_required' and issue.details['procedure'].upper() == 'DBO.NEWONE' for issue in added))
        legacy = 'CREATE PROC dbo.Legacy AS SELECT 3;\n'
        self.assertTrue(any(issue.code == 'procedure_header_required' for issue in review_procedure_headers(legacy, legacy, author='Writer')))

    def test_separate_definitions_and_new_unread_ranges_do_not_become_style_peers_or_false_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            target, input_file, label_file, layout = (base / name for name in ('Target.Designer.cs', 'Input.cs', 'Label.cs', 'Layout.cs'))
            source = 'class u_Input : DevExpress.XtraEditors.TextEdit\n{\n public u_Input()\n {\n  this.Size = new System.Drawing.Size(150, 25);\n }\n}\n'
            input_file.write_text(source, encoding='utf-8')
            label_file.write_text(source.replace('u_Input', 'u_Label').replace('TextEdit', 'LabelControl'), encoding='utf-8')
            layout.write_text('partial class Ref { private u_Input txtItem; void InitializeComponent() { this.txtItem = new u_Input(); this.txtItem.Size = new System.Drawing.Size(150, 25); } }', encoding='utf-8')
            state = {'application_epoch': 'current'}
            applied = register(state, epoch='current', work=['csharp-control'], targets=[str(target)], cwd=folder)
            select_references(state, applied, [str(input_file), str(label_file), str(layout)], folder)
            for path in (input_file, label_file, layout):
                self.read_reference(state, path)
            _bodies, _deps, problems = observed_comparisons(state, target)
            self.assertEqual([], problems)

            bodies, _deps, problems = observed_control_sources(state, target)
            self.assertEqual(2, len(bodies))
            self.assertEqual([], problems)
            input_file.write_text(source.replace('(150,', '(165,'), encoding='utf-8')
            _bodies, _deps, problems = observed_control_sources(state, target)
            self.assertTrue(problems)  # Removing stale input must not erase its obligation.
            select_references(state, applied, [str(input_file)], folder)
            self.read_reference(state, input_file)
            # A distinct complete unit of the same SHA still needs its own post-selection read.
            combined = base / 'Combined.cs'
            combined.write_text(input_file.read_text(encoding='utf-8') + label_file.read_text(encoding='utf-8'), encoding='utf-8')
            select_references(state, applied, [str(combined)], folder)
            self.read_reference(state, combined)
            select_references(state, applied, [str(combined) + '#L1-L7'], folder)
            _bodies, _deps, problems = observed_control_sources(state, target)
            self.assertTrue(problems)
            self.read_reference(state, combined)
            _bodies, _deps, problems = observed_control_sources(state, target)
            self.assertEqual([], problems)

    def test_inherited_business_and_form_methods_remain_code_style_references(self):
        with tempfile.TemporaryDirectory() as folder:
            target, reference = Path(folder) / 'Target.cs', Path(folder) / 'Reference.cs'
            for inheritance in ('', ' : BasePolicy', ' : System.Windows.Forms.Form'):
                reference.write_text('class BasePolicy {}\nclass Reference' + inheritance + ' { public bool Ready() { return true; } }', encoding='utf-8')
                state = {'application_epoch': 'current'}
                applied = register(state, epoch='current', work=['pb-migrate', 'csharp-code'], targets=[str(target)], cwd=folder)
                select_references(state, applied, [str(reference)], folder)
                self.read_reference(state, reference)
                bodies, _deps, problems = observed_comparisons(state, target)
                self.assertEqual([], problems)
                self.assertIn('Ready()', bodies['csharp'])
                controls, _deps, problems = observed_control_sources(state, target)
                self.assertEqual([], controls)
                self.assertEqual([], problems)
