"""Exercise the real scoped helper and hooks against isolated source files."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.context.store import Store, session_key
from src.runtime.hooks import CYCLE, ROOT, handle
from src.runtime.check_context import SourceBaselines
from src.runtime.guidance import document


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        self.log = self.root / 'transcript.jsonl'
        self.log.write_text('', encoding='utf-8')
        environment = patch.dict(os.environ, {'PLUGIN_DATA': str(self.root / 'data'), 'KH_HOOKS_MODE': 'enforce'})
        environment.start()
        self.addCleanup(environment.stop)
        self.host = 'codex'
        self.scope = {'cwd': str(self.project), 'session_id': 'application-test', 'transcript_path': str(self.log)}
        self.store = Store(self.root / 'data/context-v1', str(self.project))

    def event(self, name, **values):
        return handle({**self.scope, 'hook_event_name': name, **values}, self.host)

    def read(self, relative):
        path, body, _start, _end = document(ROOT, relative)
        return self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(path)}, tool_response=body)

    def state(self):
        with self.store.connect() as connection:
            return self.store.load(connection, session_key(self.scope, self.host))

    def command(self, command, *, scope=None, epoch=None):
        data = self.scope if scope is None else scope
        args = [sys.executable, '-B', str(ROOT / 'scripts/kh_context.py'), '--cwd', data['cwd'],
                '--session', data['session_id'], '--transcript', data['transcript_path'], '--host', self.host,
                '--data-root', str(self.root / 'data/context-v1')]
        if epoch is not None:
            args.extend(['--epoch', epoch])
        if data.get('agent_id'):
            args.extend(['--agent-id', data['agent_id']])
        result = subprocess.run([*args, *command], capture_output=True, text=True, encoding='utf-8',
                                timeout=20, cwd=self.project)
        return result.returncode, json.loads(result.stdout)

    def apply(self, work, targets):
        args = ['apply']
        if set(work) & {'sql-select', 'sql-save'}:
            args.extend(['--author', 'Fixture Writer', '--reference-author', 'Fixture Writer'])
        for kind in work:
            args.extend(['--work', kind])
        for path in targets:
            args.extend(['--target', str(path)])
        references = []
        suffixes = {path.suffix for path in targets} | ({'.sru'} if 'pb-migrate' in work else set())
        for suffix in suffixes:
            layout = suffix == '.cs' and any(path.name.casefold().endswith('.designer.cs') for path in targets)
            reference = self.project / ('Reference.Designer.cs' if layout else 'Reference' + suffix)
            body = 'class Reference { public int Read() { return 1; } }\n' if suffix == '.cs' else 'SELECT A.VALUE FROM REFERENCE_ROWS A;\n' if suffix == '.sql' else 'global type reference from window\nend type\n'
            if layout:
                body = 'partial class Reference { private DevExpress.XtraEditors.TextEdit txtItem; void InitializeComponent() { this.txtItem = new DevExpress.XtraEditors.TextEdit(); this.txtItem.Size = new System.Drawing.Size(150, 25); } }\n'
            if suffix == '.sql':
                body = '-- =============================================\n-- AUTHOR: Fixture Writer\n-- CREATE DATE: 2026-11-18\n-- DESCRIPTION: Fixture query 조회\n-- =============================================\nCREATE PROCEDURE dbo.Reference_SELECT AS\n' + body
                if 'sql-save' in work:
                    body += 'UPDATE REFERENCE_ROWS SET VALUE = 1;\n'
            reference.write_text(body, encoding='utf-8')
            args.extend(['--reference', str(reference)])
            references.append(reference)
        status, result = self.command(args, epoch=self.state()['application_epoch'])
        self.assertEqual(0, status, result)
        self.assertEqual('applied', result['status'])
        for reference in references:
            self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(reference)}, tool_response=reference.read_text(encoding='utf-8'))
        return result

    def write(self, path):
        return self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(path)})

    def assert_unchecked(self, response):
        self.assertNotIn('permissionDecision', response.get('hookSpecificOutput', {}))
        self.assertTrue(not response or 'outside registered KH coverage' in response['hookSpecificOutput']['additionalContext'])

    def load_required(self, result, *, omit=()):
        for relative in sorted({p for item in result['files'] for p in item['required']}):
            if relative not in omit and relative.partition('#')[0] not in omit:
                self.read(relative)

    def test_review_reads_and_explicit_selection_do_not_apply_development(self):
        self.event('UserPromptSubmit', prompt='Review the KH skill documents as data.', turn_id='review')
        for domain in ('sql-formatting', 'csharp-designer-style-harness', 'pb-to-csharp-migration-harness'):
            self.read(domain + '/SKILL.md')
        self.assertEqual([], self.state()['kh_used_skills'])
        with patch('src.runtime.hooks.snapshot') as snapshot, patch('src.runtime.hooks.inspect') as inspect:
            for suffix in ('.sql', '.cs', '.srw'):
                path = self.project / ('Unrelated' + suffix)
                self.assert_unchecked(self.write(path))
                path.write_text('unrelated text', encoding='utf-8')
                self.assertEqual({}, self.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(path)}))
            self.assertEqual({}, self.event('Stop'))
            snapshot.assert_not_called()
            inspect.assert_not_called()
        self.event('UserPromptSubmit', prompt='$sql-formatting inspect its instructions', turn_id='explicit-review')
        self.assertEqual(['sql-formatting'], self.state()['requested_skills'])
        self.assertEqual([], self.state()['kh_used_skills'])
        self.assert_unchecked(self.write(self.project / 'Other.sql'))

    def test_child_stop_uses_observed_child_scope_and_preserves_parent(self):
        self.scope['agent_id'] = 'child-with-owned-sql'
        self.read('sql-formatting/SKILL.md')
        target = self.project / 'Child.sql'
        target.write_text('SELECT 1;', encoding='utf-8')
        self.load_required(self.apply(['sql-format'], [target]))
        self.assertEqual({}, self.write(target))
        target.write_text('SELECT 2;', encoding='utf-8')
        self.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(target)}, tool_response='saved')
        parent_log = self.root / 'parent.jsonl'
        parent_log.write_text('', encoding='utf-8')
        stopped = self.event('SubagentStop', transcript_path=str(parent_log), agent_transcript_path=str(self.log))
        self.assertEqual('block', stopped['decision'])
        parent = {key: value for key, value in self.scope.items() if key != 'agent_id'}
        parent['transcript_path'] = str(parent_log)
        self.assertEqual({}, handle({**parent, 'hook_event_name': 'Stop'}, self.host))
        self.assertEqual({}, handle({**parent, 'agent_id': 'another-child', 'hook_event_name': 'SubagentStop'}, self.host))

    def test_designer_minimum_references_cannot_be_omitted_by_code_kind(self):
        hint = self.read('csharp-designer-style-harness/SKILL.md')
        arguments = json.loads(hint['hookSpecificOutput']['additionalContext'].split('Scope arguments: ', 1)[1])
        self.assertEqual(self.root / 'data/context-v1', Path(arguments['data-root']))
        self.assertEqual(self.state()['application_epoch'], arguments['epoch'])
        target = self.project / 'Screen.Designer.cs'
        result = self.apply(['csharp-code'], [target])
        critical = {'csharp-designer-style-harness/references/coding-style.md',
                    'csharp-designer-style-harness/references/designer.md',
                    'csharp-designer-style-harness/references/user-controls.md'}
        self.assertTrue(critical <= {relative.partition('#')[0] for relative in result['files'][0]['missing']})
        self.read(CYCLE)
        for relative in sorted(critical):
            denied = self.write(target)['hookSpecificOutput']
            self.assertEqual('deny', denied['permissionDecision'])
            self.assertIn(str(ROOT / 'skills' / relative), denied['permissionDecisionReason'])
            self.read(relative)
        self.assertEqual({}, self.write(target))
        self.assert_unchecked(self.write(self.project / 'Unregistered.Designer.cs'))

    def test_select_contracts_are_required_without_unrelated_save_examples(self):
        self.read('sql-formatting/SKILL.md')
        target = self.project / 'Select.sql'
        result = self.apply(['sql-select'], [target])
        missing = set(result['files'][0]['missing'])
        for name in ('style.md', 'procedure-contracts.md', 'procedure-patterns.md', 'select-patterns.md'):
            self.assertIn('sql-formatting/references/' + name, {relative.partition('#')[0] for relative in missing})
        self.assertNotIn('sql-formatting/references/save-patterns.md', result['files'][0]['required'])
        self.load_required(result, omit={'sql-formatting/references/procedure-contracts.md'})
        self.assertIn('procedure-contracts.md', self.write(target)['hookSpecificOutput']['permissionDecisionReason'])
        self.read('sql-formatting/references/procedure-contracts.md')
        self.assertEqual({}, self.write(target))

    def test_control_changes_in_code_behind_have_their_own_required_route(self):
        self.read('csharp-designer-style-harness/SKILL.md')
        target = self.project / 'Screen.cs'
        result = self.apply(['csharp-control'], [target])
        self.load_required(result, omit={'csharp-designer-style-harness/references/user-controls.md'})
        self.assertIn('user-controls.md', self.write(target)['hookSpecificOutput']['permissionDecisionReason'])
        self.read('csharp-designer-style-harness/references/user-controls.md')
        self.assertEqual({}, self.write(target))
        self.assertNotIn('csharp-designer-style-harness/references/reports.md', result['files'][0]['required'])

    def test_pb_outputs_require_their_actual_routes_and_stay_file_scoped(self):
        self.read('pb-to-csharp-migration-harness/SKILL.md')
        cs, sql = self.project / 'Output.cs', self.project / 'Output.sql'
        result = self.apply(['pb-migrate', 'csharp-control', 'sql-select'], [cs, sql])
        cs_item = next(item for item in result['files'] if item['target'].endswith('.cs'))
        sql_item = next(item for item in result['files'] if item['target'].endswith('.sql'))
        self.assertIn('pb-to-csharp-migration-harness/references/datawindow.md', cs_item['required'])
        self.assertIn('csharp-designer-style-harness/references/user-controls.md', {relative.partition('#')[0] for relative in cs_item['required']})
        self.assertNotIn('sql-formatting/references/procedure-contracts.md', cs_item['required'])
        self.assertIn('pb-to-csharp-migration-harness/references/sql.md', sql_item['required'])
        self.assertIn('sql-formatting/references/procedure-contracts.md', {relative.partition('#')[0] for relative in sql_item['required']})
        self.assertNotIn('csharp-designer-style-harness/references/coding-style.md', sql_item['required'])
        self.assertEqual({}, self.write(self.project / 'Unregistered.sql'))
        self.load_required({'files': [cs_item]})
        self.assertEqual({}, self.write(cs))
        self.assertEqual('deny', self.write(sql)['hookSpecificOutput']['permissionDecision'])
        self.load_required({'files': [sql_item]})
        self.assertEqual({}, self.write(sql))

    def test_existing_reads_are_reused_and_new_responsibility_keeps_original(self):
        target = self.project / 'Save.sql'
        original = 'SELECT A.QTY FROM INPUT_ROWS A;'
        target.write_text(original, encoding='utf-8')
        self.read('sql-formatting/SKILL.md')
        self.read('sql-formatting/references/procedure-contracts.md')
        first = self.apply(['sql-select'], [target])
        self.assertNotIn('sql-formatting/references/procedure-contracts.md', first['files'][0]['missing'])
        self.load_required(first)
        target.write_text(original.replace('A.QTY', 'ISNULL(A.QTY, 0)'), encoding='utf-8')
        second = self.apply(['sql-save'], [target])
        self.assertIn('sql-formatting/references/save-patterns.md', second['files'][0]['missing'])
        key = session_key(self.scope, self.host)
        baselines = SourceBaselines(self.store.path.parent / 'checks' / key, self.state())
        self.assertEqual(original, baselines.original(target))
        self.assertIn('sql-select', second['files'][0]['work'])

    def test_missing_references_are_reported_after_specialized_writer_and_stop(self):
        target = self.project / 'Save.sql'
        original = 'SELECT A.QTY FROM INPUT_ROWS A;'
        target.write_text(original, encoding='utf-8')
        self.read('sql-formatting/SKILL.md')
        self.apply(['sql-select'], [target])
        target.write_text(original.replace('A.QTY', 'ISNULL(A.QTY, 0)'), encoding='utf-8')
        stopped = self.event('Stop')
        self.assertEqual('block', stopped['decision'])
        self.assertIn('procedure-contracts.md', stopped['reason'])
        self.assertIn('value_fallback_review', json.dumps(self.state()['files']))

    def test_pause_epoch_and_other_chat_cannot_be_bypassed_by_apply(self):
        self.read('sql-formatting/SKILL.md')
        epoch = self.state()['application_epoch']
        args = ['apply', '--work', 'sql-select', '--target', str(self.project / 'Save.sql')]
        code, _ = self.command(args, scope={**self.scope, 'session_id': 'different'}, epoch=epoch)
        self.assertEqual(1, code)
        self.event('UserPromptSubmit', prompt='current task correction', turn_id='new')
        code, _ = self.command(args, epoch=epoch)
        self.assertEqual(1, code)
        self.event('UserPromptSubmit', prompt='stop', turn_id='cancel')
        code, result = self.command(args, epoch=self.state()['application_epoch'])
        self.assertEqual(1, code)
        self.assertIn('paused', result['message'])
        self.assertTrue(self.state()['paused'])

    def test_claude_native_delivery_requires_registration_without_auto_applying(self):
        self.host = 'claude'
        self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'kh-skills:sql-formatting'}, tool_response={})
        self.assertEqual([], self.state()['kh_used_skills'])
        target = self.project / 'Save.sql'
        self.assert_unchecked(self.write(target))
        result = self.apply(['sql-save'], [target])
        self.assertNotIn('sql-formatting/SKILL.md', result['files'][0]['missing'])
        self.assertIn(str(ROOT / 'skills/sql-formatting/references/save-patterns.md'),
                      self.write(target)['hookSpecificOutput']['permissionDecisionReason'])

    def test_formatting_scope_does_not_accept_a_behavior_change(self):
        target = self.project / 'Format.sql'
        original = 'SELECT A.QTY FROM INPUT_ROWS A;'
        target.write_text(original, encoding='utf-8')
        self.read('sql-formatting/SKILL.md')
        result = self.apply(['sql-format'], [target])
        self.load_required(result)
        self.assertEqual({}, self.write(target))
        target.write_text('SELECT A.QTY FROM INPUT_ROWS A WHERE A.QTY > 0;', encoding='utf-8')
        self.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(target)}, tool_response=target.read_text(encoding='utf-8'))
        self.assertIn('sql_meaning_tokens_changed', json.dumps(self.state()['files']))
        self.assertEqual('block', self.event('Stop')['decision'])

    def test_selected_comparison_reaches_checker_and_new_ownership_invalidates_cache(self):
        self.read('csharp-designer-style-harness/SKILL.md')
        target = self.project / 'Screen.cs'
        target.write_text('class Screen { int Read() { return 1; } }', encoding='utf-8')
        result = self.apply(['csharp-code'], [target])
        self.load_required(result)
        edit = {'tool_name': 'Write', 'tool_input': {'file_path': str(target),
                'content': 'class Screen { int Read() { return 2; } }'}}
        self.assertEqual({}, self.event('PreToolUse', **edit))
        target.write_text(edit['tool_input']['content'], encoding='utf-8')
        self.event('PostToolUse', **edit)
        check = self.state()['files'][str(target)]['check']
        self.assertTrue(check['comparison_baselines']['command_style_reference'])
        reference = self.project / 'Reference.cs'
        code, _result = self.command(['apply', '--work', 'csharp-code', '--target', str(reference)], epoch=self.state()['application_epoch'])
        self.assertEqual(0, code)
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(target)}, tool_response=target.read_text(encoding='utf-8'))
        check = self.state()['files'][str(target)]['check']
        self.assertFalse(check['comparison_baselines'].get('command_style_reference'))

    def test_plain_method_work_needs_only_its_relevant_coding_sections(self):
        self.read('csharp-designer-style-harness/SKILL.md')
        target = self.project / 'Calculation.cs'
        result = self.apply(['csharp-code'], [target])
        references = result['files'][0]['required']
        self.assertIn('csharp-designer-style-harness/references/coding-style.md#syntax-and-naming', references)
        self.assertFalse(any('numeric-display-formats' in path or 'user-controls' in path or 'reports.md' in path for path in references))
        self.load_required(result, omit={'csharp-designer-style-harness/references/coding-style.md'})
        for reference in references:
            if 'coding-style.md#' in reference:
                path, body, _start, _end = document(ROOT, reference)
                lines = body.splitlines(keepends=True)
                split = max(1, len(lines) // 2)
                self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(path)}, tool_response=''.join(lines[:split]))
                self.assertEqual('deny', self.write(target)['hookSpecificOutput']['permissionDecision'])
                self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(path)}, tool_response=''.join(lines[split:]))
        self.assertEqual({}, self.write(target))

    def test_select_sections_exclude_save_preparation_without_dropping_key_rules(self):
        self.read('sql-formatting/SKILL.md')
        result = self.apply(['sql-select'], [self.project / 'Select.sql'])
        contracts = '\n'.join(document(ROOT, path)[1] for path in result['files'][0]['required'] if 'procedure-contracts.md' in path)
        self.assertIn('For composite keys,', contracts)
        self.assertIn('Give each operation a coherent dispatch branch', contracts)
        self.assertNotIn('When adding an XML action,', contracts)
        self.assertNotIn('Keep XML/selected row values in their rowset', contracts)

    def test_standalone_query_cannot_hide_a_procedure_and_format_cannot_create_source(self):
        self.read('sql-formatting/SKILL.md')
        query = self.project / 'Query.sql'
        result = self.apply(['sql-query'], [query])
        self.assertFalse(any('procedure-contracts' in path for path in result['files'][0]['required']))
        self.load_required(result)
        self.assertEqual({}, self.write(query))
        content = 'CREATE OR ALTER PROCEDURE dbo.Sample AS BEGIN SELECT 1; END'
        denied = self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(query), 'content': content})
        self.assertIn('sql-select/sql-save', denied['hookSpecificOutput']['permissionDecisionReason'])
        query.write_text(content, encoding='utf-8')  # An unsupported writer is caught from the saved body too.
        self.assertEqual('block', self.event('Stop')['decision'])
        self.assertIn('procedure', self.state()['files'][str(query)]['routing_problem'])
        self.event('UserPromptSubmit', prompt='new formatting task', turn_id='later')
        self.read('sql-formatting/SKILL.md')
        code, result = self.command(['apply', '--work', 'sql-format', '--target', str(self.project / 'Missing.sql')], epoch=self.state()['application_epoch'])
        self.assertEqual(1, code)
        self.assertIn('existing file', result['message'])

    def test_file_metadata_is_not_treated_as_sql_declaration_content(self):
        self.read('sql-formatting/SKILL.md')
        target = self.project / 'CREATE PROC.sql'
        result = self.apply(['sql-query'], [target])
        self.load_required(result)
        self.assertEqual({}, self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(target), 'content': 'SELECT 1;'}))
        patch = '*** Begin Patch\n*** Add File: ' + str(target) + '\n+SELECT 1;\n*** End Patch'
        self.assertEqual({}, self.event('PreToolUse', tool_name='apply_patch', tool_input={'command': patch}))

    def test_failed_application_does_not_adopt_a_changed_candidate_as_original(self):
        self.read('sql-formatting/SKILL.md')
        target = self.project / 'Save.sql'
        before = 'SELECT A.QTY FROM INPUT_ROWS A;'
        target.write_text(before, encoding='utf-8')
        key = session_key(self.scope, self.host)
        blocked = self.store.path.parent / 'checks' / key
        blocked.parent.mkdir(parents=True)
        blocked.write_text('owned fixture blocking a directory', encoding='utf-8')
        args = ['apply', '--work', 'sql-select', '--target', str(target)]
        epoch = self.state()['application_epoch']
        code, _ = self.command(args, epoch=epoch)
        self.assertEqual(1, code)
        self.assertTrue(self.state()['application_errors'])
        blocked.unlink()
        target.write_text('SELECT 999;', encoding='utf-8')
        code, _ = self.command(args, epoch=epoch)
        self.assertEqual(1, code)
        self.assertFalse(self.state().get('check_baselines'))
        self.assertEqual('deny', self.write(target)['hookSpecificOutput']['permissionDecision'])
        target.write_text(before, encoding='utf-8')  # Restore the known actual pre-failure source.
        code, result = self.command(args, epoch=epoch)
        self.assertEqual(0, code, result)
        self.assertFalse(self.state()['application_errors'])
        self.assertEqual(before, SourceBaselines(self.store.path.parent / 'checks' / key, self.state()).original(target))

    def test_multifile_patch_classifies_each_sql_destination_separately(self):
        self.read('sql-formatting/SKILL.md')
        query = self.project / 'Query.sql'
        procedure = self.project / 'Procedure.sql'
        result = self.apply(['sql-query'], [query])
        self.load_required(result)
        query_patch = '*** Update File: ' + str(query) + '\n@@\n-SELECT 1;\n+SELECT 2;\n'
        proc_patch = '*** Add File: ' + str(procedure) + '\n+CREATE PROCEDURE dbo.P AS SELECT 1;\n'
        def proposed(body):
            return self.event('PreToolUse', tool_name='apply_patch', tool_input={'command': '*** Begin Patch\n' + body + '*** End Patch'})
        self.assert_unchecked(proposed(query_patch + proc_patch))  # Coverage notice does not apply the other procedure.
        result = self.apply(['sql-select'], [procedure])
        self.load_required(result)
        self.assertEqual({}, proposed(proc_patch + query_patch))  # Registered procedure owns its separate requirements.
        self.assertEqual('deny', proposed(query_patch + '+CREATE PROCEDURE dbo.Bad AS SELECT 1;\n')['hookSpecificOutput']['permissionDecision'])
        renamed = self.project / 'Renamed.sql'
        result = self.apply(['sql-query'], [renamed])
        self.load_required(result)
        self.assertEqual('deny', proposed('*** Update File: ' + str(query) + '\n*** Move to: ' + str(renamed) + '\n@@\n+CREATE PROCEDURE dbo.Bad AS SELECT 1;\n')['hookSpecificOutput']['permissionDecision'])

    def test_companion_change_after_failed_capture_is_not_a_new_original(self):
        self.read('csharp-designer-style-harness/SKILL.md')
        target = self.project / 'Screen.cs'
        peer = self.project / 'Screen.Designer.cs'
        target.write_text('partial class Screen { void Run() { } }', encoding='utf-8')
        original_peer = 'partial class Screen { void InitializeComponent() { } }'
        peer.write_text(original_peer, encoding='utf-8')
        key = session_key(self.scope, self.host)
        blocked = self.store.path.parent / 'checks' / key
        blocked.parent.mkdir(parents=True)
        blocked.write_text('owned capture failure fixture', encoding='utf-8')
        args = ['apply', '--work', 'csharp-code', '--target', str(target)]
        epoch = self.state()['application_epoch']
        self.assertEqual(1, self.command(args, epoch=epoch)[0])
        blocked.unlink()
        peer.write_text(original_peer.replace('InitializeComponent', 'Changed'), encoding='utf-8')
        self.assertEqual(1, self.command(args, epoch=epoch)[0])
        self.assertFalse(self.state().get('check_baselines'))
        peer.write_text(original_peer, encoding='utf-8')
        self.assertEqual(0, self.command(args, epoch=epoch)[0])
        baselines = SourceBaselines(self.store.path.parent / 'checks' / key, self.state())
        self.assertEqual(original_peer, baselines.original(peer))

    def test_legacy_partial_capture_preserves_originals_while_paused(self):
        target = self.project / 'Screen.cs'
        original = 'partial class Screen { void Run() { } }'
        target.write_text(original, encoding='utf-8')
        key = session_key(self.scope, self.host)
        with self.store.connect(create=True) as connection:
            state = self.store.load(connection, key)
            baselines = SourceBaselines(self.store.path.parent / 'checks' / key, state)
            baselines.capture(target)
            state.update(skill_scope_version=1, paused=True, files={}, before={},
                         file_warning='Original companion could not be captured.',
                         kh_used_skills=['csharp-designer-style-harness'])
            self.store.save(connection, key, state)
        target.write_text(original.replace('Run', 'Changed'), encoding='utf-8')
        self.event('SessionStart', source='compact')
        state = self.state()
        self.assertTrue(state['paused'])
        self.assertTrue(state['legacy_originals_pending'])
        self.assertFalse(state['kh_used_skills'])  # A baseline does not identify which peer was the owned write target.
        self.assertFalse(state.get('last_file_checks_outcome'))
        self.assertEqual(original, SourceBaselines(self.store.path.parent / 'checks' / key, state).original(target))

    def test_move_carries_unchanged_procedure_declaration_to_its_new_route(self):
        self.read('sql-formatting/SKILL.md')
        source = self.project / 'ExistingProcedure.sql'
        target = self.project / 'NewQuery.sql'
        source.write_text('CREATE PROCEDURE DBO.P AS\nSELECT 1;', encoding='utf-8')
        self.load_required(self.apply(['sql-query'], [target]))
        patch = '*** Begin Patch\n*** Update File: ' + str(source) + '\n*** Move to: ' + str(target) + '\n@@\n-SELECT 1;\n+SELECT 2;\n*** End Patch'
        denied = self.event('PreToolUse', tool_name='apply_patch', tool_input={'command': patch})
        self.assertIn('sql-select/sql-save', denied['hookSpecificOutput']['permissionDecisionReason'])
        self.load_required(self.apply(['sql-select'], [target]))
        self.assert_unchecked(self.event('PreToolUse', tool_name='apply_patch', tool_input={'command': patch}))

    def test_declared_method_scope_expands_for_actual_control_change(self):
        self.read('csharp-designer-style-harness/SKILL.md')
        target = self.project / 'Screen.cs'
        target.write_text('class Screen { void Run() { } }', encoding='utf-8')
        self.load_required(self.apply(['csharp-code'], [target]))
        content = 'class Screen { void Run() { var edit = new DevExpress.XtraEditors.TextEdit(); edit.Enabled = false; } }'
        decision = self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(target), 'content': content})
        self.assertEqual('deny', decision['hookSpecificOutput']['permissionDecision'])
        self.assertIn('user-controls.md', decision['hookSpecificOutput']['permissionDecisionReason'])
        self.assertIn('csharp-control', next(iter(self.state()['applications'].values()))['work'])
        self.load_required(self.apply(['csharp-control'], [target]))
        self.assertEqual({}, self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(target), 'content': content}))

    def test_no_comparison_cannot_become_a_completed_audit(self):
        self.read('csharp-designer-style-harness/SKILL.md')
        target = self.project / 'Calculation.cs'
        target.write_text('class Calculation { int Read() { return 1; } }', encoding='utf-8')
        code, result = self.command(['apply', '--work', 'csharp-code', '--target', str(target)], epoch=self.state()['application_epoch'])
        self.assertEqual(0, code)
        self.load_required(result)
        self.assertIn('Comparison-source', self.write(target)['hookSpecificOutput']['permissionDecisionReason'])
        content = 'class Calculation { int Read() { return 2; } }'
        target.write_text(content, encoding='utf-8')
        self.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(target)}, tool_response=content)
        self.assertEqual('block', self.event('Stop')['decision'])
        self.assertEqual('requires_repair_or_evidence', self.state()['completion_status'])
        self.assertFalse(self.state()['semantic_audit_verified'])
        self.load_required(self.apply(['csharp-code'], [target]))
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(target)}, tool_response=content)
        self.assertEqual({}, self.event('Stop'))
        self.assertEqual('checks_complete', self.state()['last_file_checks_outcome'])
        self.assertFalse(self.state()['semantic_audit_verified'])

    def test_unregistered_coverage_notice_does_not_inspect_or_activate(self):
        self.read('sql-formatting/SKILL.md')
        target = self.project / 'Other.sql'
        first = self.write(target)
        self.assertIn('outside registered KH coverage', first['hookSpecificOutput']['additionalContext'])
        self.assertEqual({}, self.write(target))
        state = self.state()
        self.assertFalse(state.get('applications'))
        self.assertFalse(state.get('files'))
        self.assertFalse(state.get('before'))
        self.assertFalse(state.get('check_baselines'))

    def test_new_edit_reopens_completion_status_after_clean_stop(self):
        self.read('csharp-designer-style-harness/SKILL.md')
        target = self.project / 'Calculation.cs'
        target.write_text('class Calculation { int Read() { return 1; } }', encoding='utf-8')
        self.load_required(self.apply(['csharp-code'], [target]))
        first = 'class Calculation { int Read() { return 2; } }'
        self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(target), 'content': first})
        target.write_text(first, encoding='utf-8')
        self.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(target)}, tool_response=first)
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(target)}, tool_response=first)
        self.assertEqual({}, self.event('Stop'))
        self.assertEqual('checks_complete_audit_unverified', self.state()['completion_status'])
        second = 'class Calculation { int Read() { if (flag) return 3; return 2; } }'
        self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(target), 'content': second})
        self.assertEqual('in_progress_audit_unverified', self.state()['completion_status'])
        self.assertFalse(self.state().get('kh_scope_closed'))
        target.write_text(second, encoding='utf-8')
        self.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(target)}, tool_response=second)
        self.assertEqual('in_progress_audit_unverified', self.state()['completion_status'])
        self.assertEqual('block', self.event('Stop')['decision'])
        self.assertEqual('requires_repair_or_evidence', self.state()['completion_status'])

    def test_reapply_preserves_observed_comparison_and_new_role_needs_explicit_selection(self):
        self.read('csharp-designer-style-harness/SKILL.md')
        target = self.project / 'Calculation.cs'
        self.load_required(self.apply(['csharp-code'], [target]))
        reference = next(iter(self.state()['applications'].values()))['references'][0]
        read_sha = reference['read_sha256']
        args = ['apply', '--work', 'csharp-code', '--target', str(target)]
        code, result = self.command(args, epoch=self.state()['application_epoch'])
        self.assertEqual(0, code, result)
        self.assertEqual(read_sha, result['files'][0]['comparison_sources'][0]['read_sha256'])
        self.assertFalse(result['files'][0]['comparison_evidence_missing'])
        code, result = self.command(['apply', '--work', 'csharp-control', '--target', str(target)], epoch=self.state()['application_epoch'])
        self.assertEqual(0, code, result)
        self.assertIn('csharp-control', result['files'][0]['comparison_evidence_missing'])
        code, result = self.command(['apply', '--work', 'csharp-control', '--target', str(target),
                                     '--reference', reference['path']], epoch=self.state()['application_epoch'])
        self.assertEqual(0, code, result)
        self.assertEqual(read_sha, result['files'][0]['comparison_sources'][0]['read_sha256'])
        self.assertFalse(result['files'][0]['comparison_evidence_missing'])

    def test_retracted_unsaved_control_proposal_does_not_force_unrelated_references(self):
        self.read('csharp-designer-style-harness/SKILL.md')
        target = self.project / 'Calculation.cs'
        initial = 'class Calculation { int Read() { return 1; } }'
        target.write_text(initial, encoding='utf-8')
        self.load_required(self.apply(['csharp-code'], [target]))
        proposed = 'class Calculation { void Run() { var edit = new DevExpress.XtraEditors.TextEdit(); } }'
        denied = self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(target), 'content': proposed})
        self.assertEqual('deny', denied['hookSpecificOutput']['permissionDecision'])
        self.assertEqual(initial, target.read_text(encoding='utf-8'))
        actual = initial.replace('return 1', 'return 2')
        self.assertEqual({}, self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(target), 'content': actual}))
        item = next(iter(self.state()['applications'].values()))
        self.assertEqual(['csharp-code'], item['work'])
        self.assertEqual([], item['inferred_work'])

    def test_control_file_deletion_uses_existing_body_for_responsibilities(self):
        self.read('csharp-designer-style-harness/SKILL.md')
        target = self.project / 'Screen.cs'
        target.write_text('class Screen { void Run() { var edit = new DevExpress.XtraEditors.TextEdit(); } }', encoding='utf-8')
        self.load_required(self.apply(['csharp-code'], [target]))
        patch = '*** Begin Patch\n*** Delete File: ' + str(target) + '\n*** End Patch'
        result = self.event('PreToolUse', tool_name='apply_patch', tool_input={'command': patch})
        self.assertEqual('deny', result['hookSpecificOutput']['permissionDecision'])
        self.assertIn('user-controls.md', result['hookSpecificOutput']['permissionDecisionReason'])
