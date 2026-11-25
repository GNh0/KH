"""Owned native invocation, failure and cancellation boundaries."""
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

from src.context.store import Store, session_key
from src.runtime.hooks import CYCLE, ROOT, handle
from src.runtime.check_context import SourceBaselines
from tests.domain.hook_application_fixture import apply_files
from src.runtime.workflows import required_paths
from src.runtime.guidance import document


class NativeHookTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        self.log = self.root / 'native.jsonl'
        self.log.write_text('', encoding='utf-8')
        self.env = patch.dict(os.environ, {'PLUGIN_DATA': str(self.root / 'data'), 'KH_HOOKS_MODE': 'enforce'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.scope = {'cwd': str(self.project), 'session_id': 'native-test', 'transcript_path': str(self.log)}
        self.store = Store(self.root / 'data/context-v1', str(self.project))
        self.key = session_key(self.scope, 'claude')

    def event(self, name, **values):
        return handle({**self.scope, 'hook_event_name': name, **values}, 'claude')

    def state(self):
        with self.store.connect() as connection:
            return self.store.load(connection, self.key)

    def cycle(self):
        for relative in sorted(required_paths({'work': ['sql-query']}, self.project / 'Save.sql') - {'sql-formatting/SKILL.md'}):
            _path, body, _start, _end = document(ROOT, relative)
            self.event('PostToolUse', tool_name='Read', tool_response=body)

    def apply_sql(self, path=None, *, deliver=False, work=None):
        return apply_files(self.scope, 'claude', work or ['sql-query'],
                           [path or self.project / 'Save.sql'], deliver=deliver)

    def test_native_delivery_is_available_and_apply_owns_only_its_target(self):
        self.event('PostToolUse', tool_name='Skill',
                   tool_input={'skill': 'kh-skills:sql-formatting', 'args': 'private-argument-sentinel'},
                   tool_response={'success': True})
        sql = self.project / 'Save.sql'
        edit = {'tool_name': 'Write', 'tool_input': {'file_path': str(sql)}}
        self.assertEqual([], self.state()['kh_used_skills'])
        self.apply_sql()
        self.assertEqual(['sql-formatting'], self.state()['kh_used_skills'])
        self.assertNotIn('private-argument-sentinel', json.dumps(self.state()))
        self.assertEqual('deny', self.event('PreToolUse', **edit)['hookSpecificOutput']['permissionDecision'])
        self.cycle()
        self.assertEqual({}, self.event('PreToolUse', **edit))
        self.assertEqual({}, self.event('PreToolUse', tool_name='Write',
                                        tool_input={'file_path': str(self.project / 'Other.cs')}))

    def test_direct_command_expansion_needs_owned_plugin_provenance(self):
        for command, source, expansion in [('sql-formatting', 'plugin', 'slash_command'),
                                            ('other:sql-formatting', 'plugin', 'slash_command'),
                                            ('kh-skills:sql-formatting', 'project', 'slash_command'),
                                            ('kh-skills:sql-formatting', 'plugin', 'mcp_prompt')]:
            self.assertEqual({}, self.event('UserPromptExpansion', command_name=command,
                                            command_source=source, expansion_type=expansion))
            self.assertFalse(self.store.path.exists())
        self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting',
                   command_source='plugin', expansion_type='slash_command')
        self.assertEqual([], self.state()['kh_used_skills'])
        self.cycle()
        self.apply_sql()
        self.assertEqual({}, self.event('PreToolUse', tool_name='Write',
                                        tool_input={'file_path': str(self.project / 'Save.sql')}))

    def test_failed_or_unrelated_native_skill_does_not_activate_checks(self):
        for skill, response in [('kh-skills:sql-formatting', {'is_error': True}),
                                ('other:sql-formatting', {}), ('kh-skills:context-handoff', {}),
                                ('kh-skills:sql-formatting arguments', {})]:
            self.event('PostToolUse', tool_name='Skill', tool_input={'skill': skill}, tool_response=response)
            self.assertFalse(self.store.path.exists())

    def test_first_submit_rejects_unrelated_expansion_without_prior_stop(self):
        for label, expansion_id, submitted_id, submitted in [
                ('different_ids', 'a', 'b', '/kh-skills:sql-formatting'),
                ('missing_submit_id', 'a', None, '/kh-skills:sql-formatting'),
                ('missing_expansion_id', None, 'b', '/kh-skills:sql-formatting'),
                ('different_text', None, None, 'unrelated request')]:
            with self.subTest(label=label):
                self.scope['session_id'] = label
                self.key = session_key(self.scope, 'claude')
                self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting', command_source='plugin',
                           expansion_type='slash_command', prompt='/kh-skills:sql-formatting', prompt_id=expansion_id)
                self.event('UserPromptSubmit', prompt=submitted, prompt_id=submitted_id)
                self.assertEqual([], self.state()['kh_used_skills'])
                self.assertEqual({}, self.event('PreToolUse', tool_name='Write',
                                                tool_input={'file_path': str(self.project / 'Other.sql')}))
                self.assertEqual({}, self.state().get('before', {}))

    def test_first_submit_accepts_matching_id_or_exact_no_id_prompt(self):
        for prompt_id in ('same-id', None):
            with self.subTest(prompt_id=prompt_id):
                self.scope['session_id'] = 'matching-' + str(prompt_id)
                self.key = session_key(self.scope, 'claude')
                prompt = '/kh-skills:sql-formatting task'
                self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting', command_source='plugin',
                           expansion_type='slash_command', prompt=prompt, prompt_id=prompt_id)
                self.event('UserPromptSubmit', prompt=prompt, prompt_id=prompt_id)
                self.assertIn('sql-formatting/SKILL.md', self.state()['skills_seen'])
                self.apply_sql()
                self.assertEqual(['sql-formatting'], self.state()['kh_used_skills'])
                result = self.event('PreToolUse', tool_name='Write',
                                    tool_input={'file_path': str(self.project / 'Save.sql')})
                self.assertEqual('deny', result['hookSpecificOutput']['permissionDecision'])
                self.assertNotIn('sql-formatting/SKILL.md', result['hookSpecificOutput']['permissionDecisionReason'].replace('\\', '/'))

    def test_mismatched_expansion_preserves_independent_skill_or_body_delivery(self):
        for delivery in ('native', 'body'):
            with self.subTest(delivery=delivery):
                self.scope['session_id'] = 'prior-' + delivery
                self.key = session_key(self.scope, 'claude')
                if delivery == 'native':
                    self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'kh-skills:sql-formatting'})
                else:
                    self.event('PostToolUse', tool_name='Read', tool_response=(ROOT / 'skills/sql-formatting/SKILL.md').read_text(encoding='utf-8'))
                self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting', command_source='plugin',
                           expansion_type='slash_command', prompt_id='a')
                self.event('UserPromptSubmit', prompt='steering', prompt_id='b')
                self.assertIn('sql-formatting/SKILL.md', self.state()['skills_seen'])
                self.assertEqual([], self.state()['kh_used_skills'])

    def test_repeated_pending_expansion_does_not_turn_old_pending_into_delivery(self):
        for prompt_id in ('a', 'b', 'c'):
            self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting', command_source='plugin',
                       expansion_type='slash_command', prompt_id=prompt_id)
        self.event('UserPromptSubmit', prompt='unrelated', prompt_id='different')
        self.assertEqual([], self.state()['kh_used_skills'])
        self.assertEqual({}, self.state()['native_skill_reads'])

    def check_unmatched_output_domain(self, pending):
        self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'kh-skills:sql-formatting'})
        self.cycle()
        self.event('UserPromptSubmit', prompt='SQL-only task', prompt_id='sql')
        self.event('UserPromptExpansion', command_name='kh-skills:' + pending,
                   command_source='plugin', expansion_type='slash_command', prompt_id='pending-csharp')
        sql = self.project / 'Save.sql'
        sql.write_text('SELECT A.QTY FROM INPUT_ROWS A;', encoding='utf-8')
        self.apply_sql(sql)
        edit = {'tool_name': 'Write', 'tool_input': {'file_path': str(sql)}}
        self.assertEqual({}, self.event('PreToolUse', **edit))
        self.event('PostToolUse', **edit, tool_response=sql.read_text(encoding='utf-8'))
        self.assertTrue(self.state()['native_skill_reads'][pending]['pending_submission'])
        self.event('UserPromptSubmit', prompt='SQL-only correction', prompt_id='different')
        self.assertEqual(['sql-formatting'], self.state()['kh_used_skills'])
        cs = self.project / 'Ordinary.cs'
        cs_edit = {'tool_name': 'Write', 'tool_input': {'file_path': str(cs)}}
        self.assertEqual({}, self.event('PreToolUse', **cs_edit))
        cs.write_text('class Ordinary { }', encoding='utf-8')
        self.assertEqual({}, self.event('PostToolUse', **cs_edit))
        self.assertNotIn(str(cs), self.state().get('before', {}))
        self.assertNotIn(str(cs), self.state()['files'])

    def test_sql_action_does_not_settle_an_unmatched_csharp_expansion(self):
        self.check_unmatched_output_domain('csharp-designer-style-harness')

    def test_sql_action_does_not_settle_an_unmatched_pb_expansion(self):
        self.check_unmatched_output_domain('pb-to-csharp-migration-harness')

    def test_pb_sql_output_keeps_its_needed_audit_after_cancel(self):
        self.event('UserPromptExpansion', command_name='kh-skills:pb-to-csharp-migration-harness',
                   command_source='plugin', expansion_type='slash_command', prompt_id='pending-pb')
        self.event('PostToolUse', tool_name='Read', tool_response=(ROOT / 'skills/sql-formatting/SKILL.md').read_text(encoding='utf-8'))
        self.cycle()
        sql = self.project / 'Output.sql'
        before = 'SELECT A.QTY FROM INPUT_ROWS A;'
        sql.write_text(before, encoding='utf-8')
        self.apply_sql(sql, deliver=True, work=['pb-migrate', 'sql-query'])
        edit = {'tool_name': 'Write', 'tool_input': {'file_path': str(sql)}}
        self.assertEqual({}, self.event('PreToolUse', **edit))
        sql.write_text(before.replace('A.QTY', 'ISNULL(A.QTY, 0)'), encoding='utf-8')
        self.event('UserPromptSubmit', prompt='stop', prompt_id='different')
        self.assertEqual(['sql-formatting'], self.state()['kh_used_skills'])
        self.assertEqual({}, self.event('Stop'))
        self.resume()
        self.assertEqual('block', self.event('Stop')['decision'])
        self.assertEqual(before, SourceBaselines(self.store.path.parent / 'checks' / self.key, self.state()).original(sql))

    def test_denied_action_keeps_correlation_separate_from_applied_intent(self):
        self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting',
                   command_source='plugin', expansion_type='slash_command', prompt_id='pending')
        edit = {'tool_name': 'Write', 'tool_input': {'file_path': str(self.project / 'Save.sql')}}
        self.event('PostToolUse', tool_name='Read', tool_response='unrelated non-guidance output')
        self.apply_sql()
        self.assertEqual('deny', self.event('PreToolUse', **edit)['hookSpecificOutput']['permissionDecision'])
        self.assertTrue(self.state()['native_skill_reads']['sql-formatting']['pending_submission'])
        self.event('UserPromptSubmit', prompt='unrelated task', prompt_id='different')
        self.assertNotIn('sql-formatting', self.state()['native_skill_reads'])
        self.assertEqual(['sql-formatting'], self.state()['kh_used_skills'])
        self.assertEqual('deny', self.event('PreToolUse', **edit)['hookSpecificOutput']['permissionDecision'])

    def test_used_expansion_keeps_its_audit_after_cancel_and_resume(self):
        sql = self.project / 'Save.sql'
        before = 'SELECT A.QTY FROM INPUT_ROWS A;'
        sql.write_text(before, encoding='utf-8')
        edit = {'tool_name': 'Write', 'tool_input': {'file_path': str(sql)}}
        self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting', command_source='plugin',
                   expansion_type='slash_command', prompt_id='a')
        self.cycle()
        self.apply_sql(sql)
        self.assertEqual({}, self.event('PreToolUse', **edit))
        sql.write_text(before.replace('A.QTY', 'ISNULL(A.QTY, 0)'), encoding='utf-8')
        self.event('UserPromptSubmit', prompt='stop', prompt_id='b')
        self.assertEqual({}, self.event('Stop'))
        self.resume()
        self.assertEqual('block', self.event('Stop')['decision'])
        self.assertEqual(before, SourceBaselines(self.store.path.parent / 'checks' / self.key, self.state()).original(sql))

    def test_expansion_before_submit_is_bound_to_its_prompt_not_the_previous_task(self):
        self.event('UserPromptSubmit', prompt='previous', prompt_id='previous')
        self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'kh-skills:sql-formatting'})
        self.event('Stop')
        self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting',
                   command_source='plugin', expansion_type='slash_command', prompt_id='current')
        self.event('UserPromptSubmit', prompt='/kh-skills:sql-formatting', prompt_id='current')
        self.assertIn('sql-formatting/SKILL.md', self.state()['skills_seen'])
        self.assertEqual([], self.state()['kh_used_skills'])
        self.assertEqual({}, self.state()['read_coverage'])
        self.cycle()
        self.apply_sql()
        self.assertEqual({}, self.event('PreToolUse', tool_name='Write',
                                        tool_input={'file_path': str(self.project / 'Save.sql')}))
        self.event('Stop')
        self.event('UserPromptSubmit', prompt='unrelated', prompt_id='later')
        self.assertEqual([], self.state()['kh_used_skills'])
        self.assertEqual({}, self.state()['native_skill_reads'])

    def prepare_write(self, tool='Write'):
        self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'kh-skills:sql-formatting'})
        self.cycle()
        sql = self.project / 'Save.sql'
        before = 'SELECT A.QTY FROM INPUT_ROWS A;'
        sql.write_text(before, encoding='utf-8')
        self.apply_sql(sql)
        data = {'file_path': str(sql)} if tool == 'Write' else {'command': "Set-Content -LiteralPath '" + str(sql) + "' -Value 'partial'"}
        edit = {'tool_name': tool, 'tool_input': data}
        self.assertEqual({}, self.event('PreToolUse', **edit))
        return sql, before, edit

    def test_no_id_expansion_matches_exact_prompt_once_without_retaining_arguments(self):
        self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'kh-skills:sql-formatting'})
        self.event('Stop')
        prompt = '/kh-skills:sql-formatting private-argument-sentinel'
        self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting',
                   command_source='plugin', expansion_type='slash_command', prompt=prompt)
        self.assertNotIn('private-argument-sentinel', json.dumps(self.state()))
        self.event('UserPromptSubmit', prompt=prompt)
        self.assertIn('sql-formatting/SKILL.md', self.state()['skills_seen'])
        self.assertEqual([], self.state()['kh_used_skills'])
        self.event('Stop')
        self.event('UserPromptSubmit', prompt=prompt)
        self.assertEqual([], self.state()['kh_used_skills'])

    def test_no_id_expansion_never_carries_to_a_different_prompt_or_mismatched_id(self):
        prompt = '/kh-skills:sql-formatting'
        self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'kh-skills:sql-formatting'})
        for expansion_id, submit_id, submitted in [(None, None, 'unrelated'), ('a', 'b', prompt),
                                                   ('a', None, prompt), (None, 'b', prompt)]:
            self.event('Stop')
            self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting',
                       command_source='plugin', expansion_type='slash_command', prompt=prompt,
                       prompt_id=expansion_id)
            self.event('UserPromptSubmit', prompt=submitted, prompt_id=submit_id)
            self.assertEqual([], self.state()['kh_used_skills'])

    def test_expansion_after_submit_cannot_activate_the_next_identical_task(self):
        prompt = '/kh-skills:sql-formatting'
        self.event('UserPromptSubmit', prompt=prompt)
        self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting',
                   command_source='plugin', expansion_type='slash_command', prompt=prompt)
        self.event('Stop')
        self.event('UserPromptSubmit', prompt=prompt)
        self.assertEqual([], self.state()['kh_used_skills'])

    def test_failed_powershell_partial_write_is_still_reviewed(self):
        sql, before, edit = self.prepare_write('PowerShell')
        sql.write_text(before.replace('A.QTY', 'ISNULL(A.QTY, 0)'), encoding='utf-8')
        response = self.event('PostToolUseFailure', **edit, error='private-error-sentinel')
        self.assertIn('partial changes', response['hookSpecificOutput']['additionalContext'])
        self.assertIn('value_fallback_review', self.state()['files'][str(sql)]['check']['warnings'])
        self.assertNotIn('private-error-sentinel', json.dumps(self.state()))
        self.assertEqual('block', self.event('Stop')['decision'])

    def test_unchanged_failure_does_not_create_a_saved_file_audit(self):
        _sql, _before, edit = self.prepare_write()
        self.event('PostToolUseFailure', **edit, error='failed before writing')
        self.assertEqual({}, self.state()['files'])
        self.assertEqual({}, self.event('Stop'))
        self.assertFalse((self.store.path.parent / 'checks' / self.key).exists())

    def test_interrupted_failure_preserves_originals_without_new_audit(self):
        sql, before, edit = self.prepare_write()
        sql.write_text('SELECT 2;', encoding='utf-8')
        with patch('src.runtime.hooks.snapshot') as read:
            self.assertEqual({}, self.event('PostToolUseFailure', **edit, is_interrupt=True))
            self.assertEqual({}, self.event('Stop'))
            read.assert_not_called()
        state = self.state()
        self.assertTrue(state['paused'])
        self.assertEqual(before, SourceBaselines(self.store.path.parent / 'checks' / self.key, state).original(sql))

    def resume(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/kh_context.py'),
                                 '--cwd', str(self.project), '--session', self.scope['session_id'],
                                 '--transcript', str(self.log), '--host', 'claude', 'resume'],
                                capture_output=True, check=True, timeout=10)
        self.assertEqual('resumed', json.loads(result.stdout)['status'])

    def test_cancel_resume_recovers_partial_write_and_keeps_original_through_repair(self):
        sql, before, edit = self.prepare_write()
        candidate = before.replace('A.QTY', 'ISNULL(A.QTY, 0)')
        sql.write_text(candidate, encoding='utf-8')
        self.event('PostToolUseFailure', **edit, is_interrupt=True)
        with patch('src.runtime.hooks.snapshot') as read:
            self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(sql)}, tool_response=candidate)
            self.event('PreCompact')
            self.event('Stop')
            read.assert_not_called()
        self.resume()
        self.assertEqual('block', self.event('Stop')['decision'])
        self.assertIn('value_fallback_review', self.state()['files'][str(sql)]['check']['warnings'])
        original = SourceBaselines(self.store.path.parent / 'checks' / self.key, self.state()).original(sql)
        self.assertEqual(before, original)
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(sql)}, tool_response=candidate)
        self.assertIn('cannot verify', self.event('Stop', stop_hook_active=True)['systemMessage'])
        self.event('PreToolUse', **edit)
        sql.write_text(before, encoding='utf-8')
        self.event('PostToolUse', **edit)
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(sql)}, tool_response=before)
        self.assertEqual({}, self.event('Stop'))
        self.assertEqual('checks_complete', self.state()['last_file_checks_outcome'])
        self.assertFalse(self.state()['semantic_audit_verified'])
        self.assertFalse((self.store.path.parent / 'checks' / self.key).exists())

    def test_unchanged_cancel_resume_creates_no_saved_file_audit(self):
        _sql, _before, edit = self.prepare_write()
        self.event('PostToolUseFailure', **edit, is_interrupt=True)
        self.resume()
        self.assertEqual({}, self.event('Stop'))
        self.assertEqual({}, self.state()['last_file_checks'])
        self.assertFalse((self.store.path.parent / 'checks' / self.key).exists())

    def test_compaction_restores_pause_without_any_archived_user_or_checkpoint(self):
        _sql, _before, edit = self.prepare_write()
        self.event('PostToolUseFailure', **edit, is_interrupt=True)
        self.event('PreCompact')
        restored = self.event('SessionStart', source='compact')['hookSpecificOutput']['additionalContext']
        self.assertIn('Task remains paused', restored)
        self.assertIn('recall/search/get/get-prompt', restored)
        self.assertEqual([], self.state()['users'])
        self.assertEqual({}, self.event('Stop'))

    def test_completion_of_one_write_preserves_another_outstanding_write(self):
        first, _before, edit = self.prepare_write()
        second = self.project / 'Other.sql'
        self.apply_sql(second)
        second.write_text('SELECT A.QTY FROM OTHER_ROWS A;', encoding='utf-8')
        other_edit = {'tool_name': 'Write', 'tool_input': {'file_path': str(second)}}
        self.event('PreToolUse', **other_edit)
        self.event('PostToolUse', **edit, tool_response=first.read_text(encoding='utf-8'))
        self.assertIn(str(second), self.state()['before'])
        second.write_text('SELECT ISNULL(A.QTY, 0) FROM OTHER_ROWS A;', encoding='utf-8')
        self.assertEqual('block', self.event('Stop')['decision'])
        self.assertIn('value_fallback_review', self.state()['files'][str(second)]['check']['warnings'])

    def test_same_file_failure_cannot_retire_another_interrupted_write(self):
        sql, before, edit = self.prepare_write()
        self.event('PreToolUse', **edit, tool_use_id='write-B')
        self.event('PostToolUseFailure', **edit, tool_use_id='write-A', error='unchanged')
        self.assertIn(str(sql), self.state()['before'])
        self.assertEqual({}, self.state()['files'])
        sql.write_text(before.replace('A.QTY', 'ISNULL(A.QTY, 0)'), encoding='utf-8')
        self.event('PostToolUseFailure', **edit, tool_use_id='write-B', is_interrupt=True)
        self.resume()
        self.assertEqual('block', self.event('Stop')['decision'])
        self.assertIn('value_fallback_review', self.state()['files'][str(sql)]['check']['warnings'])
        self.assertEqual(before, SourceBaselines(self.store.path.parent / 'checks' / self.key, self.state()).original(sql))

    def test_retained_intent_does_not_reopen_previously_read_unaffected_lines(self):
        sql, _before, edit = self.prepare_write()
        original = '\n'.join('SELECT ' + str(i) + ';' for i in range(20))
        # Use a new epoch with a complete original for the separated change ranges.
        self.event('Stop')
        sql.write_text(original, encoding='utf-8')
        self.event('PreToolUse', **edit)
        first = original.replace('SELECT 1;', 'SELECT 101;')
        sql.write_text(first, encoding='utf-8')
        self.event('PostToolUse', **edit, tool_response=first)
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(sql)}, tool_response=first)
        self.event('PreToolUse', **edit)
        second = first.replace('SELECT 18;', 'SELECT 118;')
        sql.write_text(second, encoding='utf-8')
        self.event('PostToolUse', **edit)
        spans = self.state()['files'][str(sql)]['pending_spans']
        self.assertTrue(spans)
        self.assertTrue(all(span['start'] >= 16 for span in spans), spans)

    def test_missing_completion_with_empty_file_deletion_is_not_ignored(self):
        sql, _before, edit = self.prepare_write()
        self.event('PostToolUseFailure', **edit, error='unchanged')
        sql.write_text('', encoding='utf-8')
        self.event('PreToolUse', **edit)
        sql.unlink()
        self.assertEqual({}, self.event('Stop'))
        self.assertEqual('deleted', self.state()['last_file_checks'][str(sql)]['sha256'])

    def test_session_end_retires_pending_intent_before_an_unrelated_task(self):
        self.prepare_write()
        self.event('SessionEnd')
        with patch('src.runtime.hooks.snapshot') as read:
            self.event('UserPromptSubmit', prompt='unrelated', prompt_id='new')
            self.event('Stop')
            read.assert_not_called()
        self.assertEqual('previous_turn_unverified', self.state()['last_file_checks_outcome'])
        self.assertEqual({}, self.state()['before'])
        self.assertEqual([], self.state()['kh_used_skills'])
        self.assertFalse((self.store.path.parent / 'checks' / self.key).exists())

    def test_legacy_line_only_intent_recognizes_empty_file_deletion(self):
        sql, _before, edit = self.prepare_write()
        self.event('PostToolUseFailure', **edit, error='unchanged')
        sql.write_text('', encoding='utf-8')
        # Begin a separate original epoch so the legacy snapshot really is an empty file.
        self.event('Stop')
        self.event('PreToolUse', **edit)
        with self.store.connect() as connection:
            state = self.store.load(connection, self.key)
            state.pop('before_sha256')
            self.store.save(connection, self.key, state)
        sql.unlink()
        self.assertEqual({}, self.event('Stop'))
        self.assertEqual('deleted', self.state()['last_file_checks'][str(sql)]['sha256'])
