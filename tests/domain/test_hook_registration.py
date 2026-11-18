"""Named applications enforce prerequisites; mentions do not claim other files."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.context.store import Store, session_key
from src.runtime.hooks import ROOT, handle
from tests.domain.hook_application_fixture import apply_files


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        self.log = self.root / 'transcript.jsonl'
        self.log.write_text('', encoding='utf-8')
        env = patch.dict(os.environ, {'PLUGIN_DATA': str(self.root / 'data'), 'KH_HOOKS_MODE': 'enforce'})
        env.start()
        self.addCleanup(env.stop)
        self.host = 'codex'
        self.scope = {'cwd': str(self.project), 'session_id': 'registration-test', 'transcript_path': str(self.log)}
        self.store = Store(self.root / 'data/context-v1', str(self.project))

    def event(self, name, **values):
        return handle({**self.scope, 'hook_event_name': name, **values}, self.host)

    def state(self):
        with self.store.connect() as connection:
            return self.store.load(connection, session_key(self.scope, self.host))

    def write(self, path):
        return self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(path), 'content': 'SELECT 1;'})

    def test_mentions_review_and_explicit_refusal_do_not_claim_unregistered_files(self):
        for turn, prompt in enumerate(('$sql-formatting change this query',
                                      'Do not use $sql-formatting for this file.',
                                      'Explain $sql-formatting; this sample is outside KH.')):
            self.event('UserPromptSubmit', prompt=prompt, turn_id=str(turn))
            target = self.project / 'New.sql'
            for _ in range(3):
                self.assertNotIn('permissionDecision', self.write(target).get('hookSpecificOutput', {}))
            state = self.state()
            self.assertFalse(target.exists())
            self.assertEqual({}, state['applications'])
            self.assertEqual({}, state['files'])
            self.assertNotIn(str(target), state.get('before', {}))
            self.assertEqual({}, self.event('Stop'))

    def test_apply_satisfies_registration_but_not_missing_prerequisites(self):
        self.event('UserPromptSubmit', prompt='$sql-formatting update this query', turn_id='one')
        target = self.project / 'New.sql'
        self.assertNotIn('permissionDecision', self.write(target).get('hookSpecificOutput', {}))
        apply_files(self.scope, self.host, ['sql-query'], [target], deliver=False)
        reason = self.write(target)['hookSpecificOutput']['permissionDecisionReason']
        self.assertIn('prerequisites', reason)
        apply_files(self.scope, self.host, ['sql-query'], [target])
        self.assertEqual({}, self.write(target))
        # A mixed call must identify uncovered work without claiming ownership of it.
        other = self.project / 'Forgotten.sql'
        response = self.event('PreToolUse', tool_name='apply_patch', tool_input={
            'patch': f'*** Begin Patch\n*** Add File: {target}\n+SELECT 1;\n*** Add File: {other}\n+SELECT 2;\n*** End Patch'})
        self.assertNotIn('permissionDecision', response['hookSpecificOutput'])
        self.assertIn(str(other), response['hookSpecificOutput']['additionalContext'])
        self.assertIn('No KH compliance result', response['hookSpecificOutput']['additionalContext'])

    def test_document_read_and_other_application_do_not_claim_unregistered_files(self):
        path = ROOT / 'skills/sql-formatting/SKILL.md'
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(path)}, tool_response=path.read_text(encoding='utf-8'))
        apply_files(self.scope, self.host, ['sql-query'], [self.project / 'Owned.sql'])
        response = self.write(self.project / 'Unrelated.sql')
        self.assertNotIn('permissionDecision', response.get('hookSpecificOutput', {}))
        self.assertEqual({}, self.state()['files'])

    def test_advisory_and_off_do_not_deny_registration_omission(self):
        self.event('UserPromptSubmit', prompt='$sql-formatting task', turn_id='one')
        target = self.project / 'New.sql'
        with patch.dict(os.environ, {'KH_HOOKS_MODE': 'advisory'}):
            response = self.write(target)
            self.assertNotIn('permissionDecision', response.get('hookSpecificOutput', {}))
        with patch.dict(os.environ, {'KH_HOOKS_MODE': 'off'}):
            self.assertEqual({}, self.write(target))

    def test_blocked_stop_preserves_owned_repair_without_claiming_another_file(self):
        self.event('UserPromptSubmit', prompt='$sql-formatting task', turn_id='one')
        target = self.project / 'Owned.sql'
        target.write_text('SELECT A.QTY FROM INPUT_ROWS A;', encoding='utf-8')
        apply_files(self.scope, self.host, ['sql-query'], [target])
        edit = {'tool_name': 'Write', 'tool_input': {'file_path': str(target),
                'content': 'SELECT ISNULL(A.QTY, 0) FROM INPUT_ROWS A;'}}
        self.event('PreToolUse', **edit)
        target.write_text(edit['tool_input']['content'], encoding='utf-8')
        self.event('PostToolUse', **edit)
        self.assertEqual('block', self.event('Stop')['decision'])
        response = self.write(self.project / 'Repair.sql')
        self.assertNotIn('permissionDecision', response.get('hookSpecificOutput', {}))
        self.assertIn(str(target), self.state()['files'])

    def test_claude_selection_does_not_identify_development_destinations(self):
        self.host = 'claude'
        self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'kh-skills:csharp-designer-style-harness'})
        self.assertNotIn('permissionDecision', self.write(self.project / 'Screen.cs').get('hookSpecificOutput', {}))
        self.assertEqual({}, self.write(self.project / 'Other.sql'))

    def test_claude_pending_mismatched_or_failed_invocation_does_not_arm(self):
        self.host = 'claude'
        target = self.project / 'Other.sql'
        self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting', command_source='plugin',
                   expansion_type='slash_command', prompt_id='pending')
        response = self.write(target)
        self.assertNotIn('permissionDecision', response.get('hookSpecificOutput', {}))
        self.event('UserPromptSubmit', prompt='unrelated', prompt_id='different')
        self.event('PostToolUse', tool_name='Skill', tool_input={'skill': 'kh-skills:sql-formatting'}, tool_response={'is_error': True})
        self.assertEqual({}, self.write(target))

    def test_claude_matching_first_turn_expansion_still_needs_a_named_application(self):
        self.host = 'claude'
        self.event('UserPromptExpansion', command_name='kh-skills:sql-formatting', command_source='plugin',
                   expansion_type='slash_command', prompt_id='first')
        self.event('UserPromptSubmit', prompt='/kh-skills:sql-formatting task', prompt_id='first')
        target = self.project / 'New.sql'
        self.assertNotIn('permissionDecision', self.write(target).get('hookSpecificOutput', {}))
        apply_files(self.scope, self.host, ['sql-query'], [target], deliver=False)
        self.assertEqual('deny', self.write(target)['hookSpecificOutput']['permissionDecision'])


if __name__ == '__main__':
    unittest.main()
