"""Owned native invocation, failure and cancellation boundaries."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.context.store import Store, session_key
from src.runtime.hooks import CYCLE, ROOT, handle
from src.runtime.check_context import SourceBaselines


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
        self.event('PostToolUse', tool_name='Read',
                   tool_response=(ROOT / 'skills' / CYCLE).read_text(encoding='utf-8-sig'))

    def test_native_skill_delivery_activates_only_its_domain_without_storing_arguments(self):
        self.event('PostToolUse', tool_name='Skill',
                   tool_input={'skill': 'kh-skills:sql-formatting', 'args': 'private-argument-sentinel'},
                   tool_response={'success': True})
        sql = self.project / 'Save.sql'
        edit = {'tool_name': 'Write', 'tool_input': {'file_path': str(sql)}}
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
        self.assertEqual(['sql-formatting'], self.state()['kh_used_skills'])
        self.cycle()
        self.assertEqual({}, self.event('PreToolUse', tool_name='Write',
                                        tool_input={'file_path': str(self.project / 'Save.sql')}))

    def test_failed_or_unrelated_native_skill_does_not_activate_checks(self):
        for skill, response in [('kh-skills:sql-formatting', {'is_error': True}),
                                ('other:sql-formatting', {}), ('kh-skills:context-handoff', {}),
                                ('kh-skills:sql-formatting arguments', {})]:
            self.event('PostToolUse', tool_name='Skill', tool_input={'skill': skill}, tool_response=response)
            self.assertFalse(self.store.path.exists())

    def test_expansion_before_submit_is_bound_to_its_prompt_not_the_previous_task(self):
        self.event('UserPromptSubmit', prompt='previous', prompt_id='previous')
        self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'kh-skills:sql-formatting'})
        self.event('Stop')
        self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting',
                   command_source='plugin', expansion_type='slash_command', prompt_id='current')
        self.event('UserPromptSubmit', prompt='/kh-skills:sql-formatting', prompt_id='current')
        self.assertEqual(['sql-formatting'], self.state()['kh_used_skills'])
        self.assertEqual({}, self.state()['read_coverage'])
        self.cycle()
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
        data = {'file_path': str(sql)} if tool == 'Write' else {'command': "Set-Content -LiteralPath '" + str(sql) + "' -Value 'partial'"}
        edit = {'tool_name': tool, 'tool_input': data}
        self.assertEqual({}, self.event('PreToolUse', **edit))
        return sql, before, edit

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
