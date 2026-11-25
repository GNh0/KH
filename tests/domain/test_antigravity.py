import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4

from src.runtime.antigravity import ROOT, handle


class AntigravityHooks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'project'
        self.project.mkdir()
        self.storage = Path(self.temp.name) / 'state'
        self.file = self.project / 'Query.sql'
        self.file.write_text("SELECT 'unfinished", encoding='utf-8')
        self.event = {'conversationId': str(uuid4()), 'workspacePaths': [str(self.project)],
                      'lastUserInput': '/sql-formatting edit Query.sql'}

    def run_event(self, name, **extra):
        return handle(name, {**self.event, **extra}, storage=self.storage)

    def tool(self, name, args, **extra):
        return self.run_event('PostToolUse', toolCall={'name': name, 'args': args}, **extra)

    def select(self):
        return self.tool('view_file', {'AbsolutePath': str(ROOT / 'skills/sql-formatting/SKILL.md'), 'IsSkillFile': True})

    def test_native_skill_open_and_successful_save_are_needed_for_bare_name(self):
        self.tool('view_file', {'IsSkillFile': True, 'AbsolutePath': str(self.project / 'foreign/sql-formatting/SKILL.md')})
        self.tool('write_to_file', {'TargetFile': str(self.file)})
        self.assertEqual({}, self.run_event('PreInvocation'))
        self.assertFalse(self.storage.exists())
        self.select()
        self.tool('write_to_file', {'TargetFile': str(self.file)}, error='write rejected')
        self.assertEqual({}, self.run_event('PreInvocation', invocationNum=1))
        self.tool('replace_file_content', {'TargetFile': str(self.file), 'ReplacementContent': 'SELECT 1'})
        first = self.run_event('PreInvocation', invocationNum=2)
        self.assertIn('ephemeralMessage', first['injectSteps'][0])
        self.assertIn('unclosed_string_literal', str(first))
        self.assertEqual({}, self.run_event('PreInvocation', invocationNum=3))
        self.assertEqual({}, self.run_event('Stop', fullyIdle=True, terminationReason='model_stop'))
        self.tool('write_to_file', {'TargetFile': str(self.file)})
        self.assertEqual({}, self.run_event('PreInvocation'))

    def test_errors_background_commands_and_other_workspaces_are_never_new_turns(self):
        self.event['lastUserInput'] = '$kh-uaf:sql-formatting edit Query.sql'
        self.tool('run_command', {'CommandLine': 'touch Query.sql', 'Cwd': str(self.project)})
        self.tool('write_to_file', {'TargetFile': str(self.project.parent / 'other.sql')})
        self.assertFalse(self.storage.exists())
        self.tool('multi_replace_file_content', {'TargetFile': str(self.file)})
        self.assertEqual({}, self.run_event('Stop', fullyIdle=False, terminationReason='model_stop'))
        self.assertEqual({}, self.run_event('PreInvocation', conversationId=str(uuid4())))
        stop = self.run_event('Stop', fullyIdle=True, terminationReason='model_stop')
        self.assertEqual('continue', stop['decision'])
        self.assertEqual({}, self.run_event('Stop', fullyIdle=True, terminationReason='model_stop'))
        self.tool('write_to_file', {'TargetFile': str(self.file)})
        self.assertEqual({}, self.run_event('Stop', fullyIdle=True, terminationReason='error'))
        self.assertEqual({}, self.run_event('PreInvocation'))

    def test_unselected_skill_document_reads_and_unrelated_tools_do_nothing(self):
        self.event['lastUserInput'] = 'Explain the /sql-formatting reference'
        self.select()
        self.tool('write_to_file', {'TargetFile': str(self.file)})
        self.assertEqual({}, self.run_event('PreInvocation'))
        self.assertFalse(self.storage.exists())

    def test_selected_domain_does_not_select_siblings_or_review_only_work(self):
        self.event['lastUserInput'] = '$kh-uaf:sql-formatting edit Query.sql'
        sibling = self.project / 'Second.sql'
        sibling.write_text("SELECT 'bad", encoding='utf-8')
        self.tool('write_to_file', {'TargetFile': str(sibling)})
        self.event['lastUserInput'] = '$kh-uaf:sql-formatting review Query.sql'
        self.tool('write_to_file', {'TargetFile': str(self.file)})
        self.assertFalse(self.storage.exists())
        self.assertEqual({}, self.run_event('PreInvocation'))

    def test_original_comparison_requires_matching_step_and_saved_body(self):
        self.event['lastUserInput'] = '$kh-uaf:sql-formatting --target Query.sql'
        self.file.write_text("SELECT ISNULL(A.QTY, 0) AS QTY FROM ORDERS A", encoding='utf-8')
        args = {'TargetFile': str(self.file), 'ReplacementChunks': [
            {'TargetContent': 'FROM ORDERS A', 'ReplacementContent': 'FROM ORDERS A WHERE A.KEYNO = 3'}]}
        call = {'name': 'multi_replace_file_content', 'args': args}
        self.assertEqual({'decision': 'allow'}, self.run_event('PreToolUse', toolCall=call, stepIdx=9))
        self.file.write_text(self.file.read_text(encoding='utf-8') + ' WHERE A.KEYNO = 3', encoding='utf-8')
        self.tool(call['name'], args, stepIdx=9)
        self.assertIn('previous_file', str(self.run_event('PreInvocation')))
        self.run_event('PreToolUse', toolCall=call, stepIdx=10)
        self.file.write_text("SELECT 'unfinished", encoding='utf-8')
        self.tool(call['name'], args, stepIdx=10)
        self.assertIn('standalone', str(self.run_event('PreInvocation')))

    def test_changed_user_input_retires_an_unreported_previous_save(self):
        self.select()
        self.tool('replace_file_content', {'TargetFile': str(self.file)})
        self.assertEqual({}, self.run_event('PreInvocation', lastUserInput='ordinary request'))
        self.assertEqual({}, self.run_event('PreInvocation'))

    def test_clean_saved_file_does_not_force_continuation(self):
        self.event['lastUserInput'] = '$kh-uaf:sql-formatting edit Query.sql'
        self.file.write_text('SELECT 1', encoding='utf-8')
        self.tool('write_to_file', {'TargetFile': str(self.file)})
        self.assertEqual({}, self.run_event('Stop', fullyIdle=True, terminationReason='model_stop'))
        self.assertEqual({}, self.run_event('PreInvocation'))

    def _save_sql(self, body, step):
        args = {'TargetFile': str(self.file), 'CodeContent': body}
        self.run_event('PreToolUse', toolCall={'name': 'write_to_file', 'args': args}, stepIdx=step)
        self.file.write_text(body, encoding='utf-8')
        self.tool('write_to_file', args, stepIdx=step)

    def test_intermediate_save_warning_survives_later_whitespace(self):
        self.event['lastUserInput'] = '$kh-uaf:sql-formatting edit Query.sql'
        self.file.write_text('SELECT A.QTY FROM ORDERS A', encoding='utf-8')
        changed = 'SELECT ISNULL(A.QTY, 0) FROM ORDERS A'
        self._save_sql(changed, 1)
        originals = list(self.storage.rglob('*.source'))
        self.assertEqual(1, len(originals))
        self._save_sql(changed + '\n', 2)
        result = self.run_event('Stop', fullyIdle=True, terminationReason='model_stop')
        self.assertIn('value_fallback_review', result.get('reason', ''))
        self.assertFalse(originals[0].exists())
        self.assertEqual({}, self.run_event('PreInvocation'))

    def test_fixed_warning_drops_even_with_legacy_fallback_in_final_file(self):
        self.event['lastUserInput'] = '$kh-uaf:sql-formatting edit Query.sql'
        original = 'SELECT ISNULL(A.PRICE, 0), A.QTY FROM ORDERS A'
        self.file.write_text(original, encoding='utf-8')
        self._save_sql(original.replace('A.QTY', 'ISNULL(A.QTY, 0)'), 1)
        self._save_sql(original + '\n', 2)
        report = self.run_event('PreInvocation')['injectSteps'][0]['ephemeralMessage']
        self.assertNotIn('value_fallback_review', report)
        self.assertIn('previous_file', report)
        self.assertFalse(list(self.storage.rglob('*.source')))

    def test_failed_or_cancelled_write_releases_only_this_scope_original(self):
        self.event['lastUserInput'] = '$kh-uaf:sql-formatting edit Query.sql'
        call = {'name': 'write_to_file', 'args': {'TargetFile': str(self.file), 'CodeContent': 'SELECT 1'}}
        self.run_event('PreToolUse', toolCall=call, stepIdx=1)
        self.assertTrue(list(self.storage.rglob('*.source')))
        self.run_event('PostToolUse', toolCall=call, stepIdx=1, error='write failed')
        self.assertFalse(list(self.storage.rglob('*.source')))
        self.run_event('PreToolUse', toolCall=call, stepIdx=2)
        self.run_event('Stop', fullyIdle=True, terminationReason='error')
        self.assertFalse(list(self.storage.rglob('*.source')))

    def test_packaged_google_schema_and_launcher_exchange(self):
        manifest = json.loads((ROOT / '.antigravity-plugin/plugin.json').read_text(encoding='utf-8'))
        self.assertEqual('kh-uaf', manifest['name'])
        group = json.loads((ROOT / 'hooks.json').read_text(encoding='utf-8'))['kh-saved-source']
        self.assertEqual({'PreInvocation', 'PreToolUse', 'PostToolUse', 'Stop'}, set(group))
        for event, entries in group.items():
            handler = entries[0]
            if event in {'PreToolUse', 'PostToolUse'}:
                self.assertRegex('replace_file_content', handler['matcher'])
                self.assertIsNone(re.fullmatch(handler['matcher'], 'foreign_write_to_file'))
                handler = handler['hooks'][0]
            self.assertEqual('command', handler['type'])
            command = shlex.split(handler['command'])
            self.assertEqual(['python', '-B', 'scripts/kh_antigravity.py', event], command)
            result = subprocess.run([sys.executable, *command[1:]], cwd=ROOT,
                                    input=json.dumps({**self.event, 'lastUserInput': 'ordinary request'}),
                                    text=True, capture_output=True, timeout=handler['timeout'],
                                    env={**os.environ, 'PLUGIN_DATA': str(self.storage)})
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({'decision': 'allow'} if event == 'PreToolUse' else {}, json.loads(result.stdout))
        self.assertFalse(self.storage.exists())
