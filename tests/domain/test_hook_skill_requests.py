"""Explicit current-user requests arm only their KH domains, without faking delivery."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.context.store import Store, session_key
from src.runtime.hooks import CYCLE, ROOT, handle
from src.runtime.skill_usage import explicit_skill_requests
from tests.domain.hook_application_fixture import apply_files


class ExplicitSkillTests(unittest.TestCase):
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
        self.scope = {'cwd': str(self.project), 'session_id': 'explicit-test', 'transcript_path': str(self.log)}
        self.store = Store(self.root / 'data/context-v1', str(self.project))
        self.key = session_key(self.scope, 'codex')

    def event(self, name, **values):
        return handle({**self.scope, 'hook_event_name': name, **values}, 'codex')

    def state(self):
        with self.store.connect() as connection:
            return self.store.load(connection, self.key)

    def write(self, suffix):
        return self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(self.project / ('Target' + suffix))})

    def test_owned_invocations_default_prompt_and_inline_requests(self):
        for prompt, skills in [
                ('$sql-formatting 이 SQL을 수정해줘', {'sql-formatting'}),
                ('Use $sql-formatting to help with this task.', {'sql-formatting'}),
                ('이 SQL을 $sql-formatting으로 정리해줘.', {'sql-formatting'}),
                ("Don't change behavior; use $sql-formatting.", {'sql-formatting'}),
                ("Please update users' queries with $sql-formatting.", {'sql-formatting'}),
                ("Don't change users' queries and admins' permissions; use $sql-formatting.", {'sql-formatting'}),
                ('> quoted example\n\nUse $sql-formatting.', {'sql-formatting'}),
                ('> quoted example\n# Use $sql-formatting', {'sql-formatting'}),
                ('Fix this screen with $kh-uaf:csharp-designer-style-harness.', {'csharp-designer-style-harness'}),
                ('$kh-uaf:csharp-designer-style-harness\nFix the screen.', {'csharp-designer-style-harness'}),
                ('$sql-formatting, $pb-to-csharp-migration-harness task', {'sql-formatting', 'pb-to-csharp-migration-harness'})]:
            self.assertEqual(skills, explicit_skill_requests({'hook_event_name': 'UserPromptSubmit', 'prompt': prompt}, 'codex', plugin_root=ROOT))

    def test_linked_skill_selection_requires_the_owned_path(self):
        owned = (ROOT / 'skills/sql-formatting/SKILL.md').as_posix()
        for prompt in ('[$sql-formatting](' + owned + ') task', 'task [$sql-formatting](skill://' + owned + ')',
                       '[$sql-formatting](\n' + owned + '\n) task'):
            self.assertEqual({'sql-formatting'}, explicit_skill_requests({'hook_event_name': 'UserPromptSubmit', 'prompt': prompt}, 'codex', plugin_root=ROOT))
        for target in ('C:/other-plugin/skills/sql-formatting/SKILL.md', 'app://sql-formatting', 'plugin://kh-uaf', 'relative/SKILL.md'):
            for prompt in ('[$sql-formatting](' + target + ') task', '[$sql-formatting](\n' + target + '\n) task',
                           '[$sql-formatting][other]\n\n[other]: ' + target,
                           '[$sql-formatting][]\n\n[$sql-formatting]: ' + target):
                self.assertEqual(set(), explicit_skill_requests({'hook_event_name': 'UserPromptSubmit', 'prompt': prompt}, 'codex', plugin_root=ROOT))

    def test_mentions_quotes_examples_other_plugins_and_generic_skills_are_not_invocations(self):
        for prompt in ('sql-formatting', 'Explain sql-formatting', 'Explain `$sql-formatting`', '`$sql-formatting`', '"$sql-formatting task"',
                       '> $sql-formatting task', '```\n$sql-formatting\n```', 'document\n~~~\n$sql-formatting\n~~~',
                       '> The following is an example:\n$sql-formatting changes the SQL\n\nExplain that example.',
                       '```sql\n```not-a-close\n$sql-formatting\n```', "SELECT N'a $sql-formatting example';",
                       '$other:sql-formatting task', '$sql-formatting-extra task', '$code-review task',
                       '<user_instructions>\n$sql-formatting\n</user_instructions>'):
            with self.subTest(prompt=prompt):
                self.event('UserPromptSubmit', prompt=prompt)
                self.assertEqual({}, self.write('.sql'))
                self.assertEqual({}, self.write('.cs'))
                self.assertEqual({}, self.event('Stop'))
        self.assertFalse(self.store.path.exists())

    def test_language_prefixed_literals_do_not_select_a_skill(self):
        for literal in ("r'$sql-formatting'", "b'$sql-formatting'", "rb'example $sql-formatting'", "fr'example $sql-formatting'",
                        "u'$sql-formatting'", "f'$sql-formatting'", "t'$sql-formatting'", "rt'example $sql-formatting'", "N'$sql-formatting'",
                        "r'''it's an example $sql-formatting'''", '"""an "example" $sql-formatting"""'):
            prompt = 'Explain the literal ' + literal + '; do not invoke it.'
            self.event('UserPromptSubmit', prompt=prompt)
            self.assertEqual({}, self.write('.sql'))
            self.assertEqual({}, self.event('Stop'))
        self.assertFalse(self.store.path.exists())

    def test_nested_replacement_literals_preserve_only_the_independent_request(self):
        for literal in ('f"{"$sql-formatting"}"', 't"{"$sql-formatting"}"',
                        'rf"{"$sql-formatting"}"', 'f"{ {"key": "$sql-formatting"} }"',
                        'f"{f"{"$sql-formatting"}"}"', 'f"""{(\n# example $sql-formatting\n"$sql-formatting")}\n"""',
                        'f"{255:#x}"', 't"{255:#x}"', 'f"{\'$sql-formatting\':\'>30}"',
                        r'rf"\{"$sql-formatting"}"', r'rt"\{"$sql-formatting"}"',
                        r'f"\{"$sql-formatting"}"', r't"\{"$sql-formatting"}"',
                        r'rf"\\{"$sql-formatting"}"', r'rt"\\{"$sql-formatting"}"',
                        'f"{items[1:3]}"', 'f"{ {\'key\': \'$sql-formatting\'}[\'key\']!s:>{width}}"',
                        'f"{(value:=\'$sql-formatting\')}"'):
            for suffix, expected in (('; do not invoke it.', set()),
                                     ('; use $kh-uaf:csharp-designer-style-harness for this screen.', {'csharp-designer-style-harness'})):
                prompt = 'Explain the Python example ' + literal + suffix
                self.assertEqual(expected, explicit_skill_requests({'hook_event_name': 'UserPromptSubmit', 'prompt': prompt}, 'codex', plugin_root=ROOT))

    def test_explicit_request_requires_observed_body_and_cycle_before_edit(self):
        self.event('UserPromptSubmit', prompt='$sql-formatting task', turn_id='first')
        self.assertEqual(['sql-formatting'], self.state()['requested_skills'])
        self.assertEqual([], self.state()['kh_used_skills'])
        self.assertEqual({}, self.state().get('native_skill_reads', {}))
        self.assertEqual([], self.state()['skills_seen'])
        self.assertNotIn('permissionDecision', self.write('.sql').get('hookSpecificOutput', {}))
        apply_files(self.scope, 'codex', ['sql-select'], [self.project / 'Target.sql'], deliver=False)
        denied = self.write('.sql')['hookSpecificOutput']
        self.assertEqual('deny', denied['permissionDecision'])
        self.assertIn('sql-formatting', denied['permissionDecisionReason'])
        self.assertIn('source-style-cycle', denied['permissionDecisionReason'])
        self.assertEqual({}, self.write('.cs'))
        self.event('PostToolUse', tool_name='Read', tool_response=(ROOT / 'skills/sql-formatting/SKILL.md').read_text(encoding='utf-8'))
        self.assertEqual('deny', self.write('.sql')['hookSpecificOutput']['permissionDecision'])
        self.event('PostToolUse', tool_name='Read', tool_response=(ROOT / 'skills' / CYCLE).read_text(encoding='utf-8'))
        self.assertEqual('deny', self.write('.sql')['hookSpecificOutput']['permissionDecision'])
        apply_files(self.scope, 'codex', ['sql-select'], [self.project / 'Target.sql'])
        self.assertEqual({}, self.write('.sql'))

    def test_stop_then_unrelated_request_clears_explicit_selection_and_read_coverage(self):
        self.event('UserPromptSubmit', prompt='$sql-formatting task', turn_id='first')
        self.event('PostToolUse', tool_name='Read', tool_response=(ROOT / 'skills/sql-formatting/SKILL.md').read_text(encoding='utf-8'))
        self.event('Stop')
        self.event('UserPromptSubmit', prompt='unrelated SQL work', turn_id='next')
        self.assertEqual([], self.state()['kh_used_skills'])
        self.assertEqual({}, self.state()['read_coverage'])
        self.assertEqual({}, self.write('.sql'))

    def test_same_turn_steering_preserves_selected_scope_and_stop_does_not_resume(self):
        self.event('UserPromptSubmit', prompt='$sql-formatting task', turn_id='same')
        apply_files(self.scope, 'codex', ['sql-select'], [self.project / 'Target.sql'], deliver=False)
        self.event('UserPromptSubmit', prompt='same task correction', turn_id='same')
        self.assertEqual('deny', self.write('.sql')['hookSpecificOutput']['permissionDecision'])
        self.event('UserPromptSubmit', prompt='stop', turn_id='cancel')
        self.event('UserPromptSubmit', prompt='$sql-formatting continue', turn_id='later')
        self.assertTrue(self.state()['paused'])
        self.assertIn('paused', self.write('.sql')['hookSpecificOutput']['permissionDecisionReason'])

    def test_pb_selection_requires_registration_only_for_native_pb_files(self):
        self.event('UserPromptSubmit', prompt='$pb-to-csharp-migration-harness migrate', turn_id='first')
        for suffix in ('.sql', '.cs'):
            self.assertEqual({}, self.write(suffix))
        self.assertNotIn('permissionDecision', self.write('.srw').get('hookSpecificOutput', {}))
        apply_files(self.scope, 'codex', ['pb-edit'], [self.project / 'Target.srw'], deliver=False)
        self.assertEqual('deny', self.write('.srw')['hookSpecificOutput']['permissionDecision'])
        self.assertEqual({}, self.write('.sql'))
        self.assertEqual({}, self.write('.cs'))
        self.assertEqual({}, self.write('.py'))
        self.assertNotIn('migrate', json.dumps(self.state().get('native_skill_reads', {})))
