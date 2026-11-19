"""Claude-specific hook behaviour: read-only reviewer, combined denials and cheap reads."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.runtime.hooks import ROOT, handle
from src.runtime.readonly_guard import readonly_violation
from tests.domain.hook_application_fixture import apply_files

AUDITOR = 'kh-skills:kh-rule-auditor'


def shell(command: str, agent: str = AUDITOR) -> dict:
    return {'agent_type': agent, 'agent_id': 'child', 'tool_name': 'Bash', 'tool_input': {'command': command}}


class ReadOnlyReviewerTests(unittest.TestCase):
    def test_review_reads_and_checks_remain_available(self):
        for command in ('git diff release -- src', 'git log --oneline -5 2>&1', 'rg -n "=>" src',
                        "grep -n 'a > b' Screen.cs", 'cat a.sql 2>/dev/null | head', 'Get-Content a.cs 2>$null',
                        'python -B scripts/kh_check.py sql before.sql after.sql'):
            self.assertEqual('', readonly_violation(shell(command)), command)

    def test_file_repository_and_db_writes_are_denied(self):
        for command in ('echo x > Screen.cs', 'sed -i s/a/b/ Save.sql', 'Set-Content -Path a.cs -Value x',
                        'git commit -m fix', 'git checkout -- a.cs', 'cp a.sql b.sql', 'tee out.txt',
                        'python -c "open(\'x.cs\', \'w\').write(1)"', 'python scripts/kh_context.py apply --work sql-save',
                        'sqlcmd -Q "UPDATE T SET A = 1"'):
            self.assertIn('read-only reviewer', readonly_violation(shell(command)), command)
        for tool in ('Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
            self.assertTrue(readonly_violation({'agent_type': AUDITOR, 'tool_name': tool}))

    def test_workers_and_main_thread_are_not_restricted(self):
        self.assertEqual('', readonly_violation(shell('echo x > a.cs', 'kh-skills:kh-sql-worker')))
        self.assertEqual('', readonly_violation({'tool_name': 'Bash', 'tool_input': {'command': 'echo x > a.cs'}}))

    def test_hook_denies_before_touching_the_store_even_in_advisory_mode(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'PLUGIN_DATA': folder, 'KH_HOOKS_MODE': 'advise'}):
            output = handle({**shell('echo x > a.cs'), 'hook_event_name': 'PreToolUse', 'cwd': folder,
                             'session_id': 'review', 'transcript_path': ''}, 'claude')
            self.assertEqual('deny', output['hookSpecificOutput']['permissionDecision'])
            self.assertFalse(any(Path(folder).rglob('*.sqlite*')))


class CombinedDenialTests(unittest.TestCase):
    def test_every_blocking_reason_is_reported_together(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            project = root / 'project'
            project.mkdir()
            log = root / 'transcript.jsonl'
            log.write_text('', encoding='utf-8')
            scope = {'cwd': str(project), 'session_id': 'combined', 'transcript_path': str(log)}
            target = project / 'Save.sql'
            with patch.dict(os.environ, {'PLUGIN_DATA': str(root / 'data'), 'KH_HOOKS_MODE': 'enforce'}):
                handle({**scope, 'hook_event_name': 'UserPromptSubmit', 'prompt': '$sql-formatting update', 'turn_id': '1'}, 'codex')
                apply_files(scope, 'codex', ['sql-query'], [target], deliver=False)
                with patch('src.runtime.hooks.routing_problem', return_value='ROUTE-PROBLEM'):
                    output = handle({**scope, 'hook_event_name': 'PreToolUse', 'tool_name': 'Write',
                                     'tool_input': {'file_path': str(target), 'content': 'SELECT 1;'}}, 'codex')
            reason = output['hookSpecificOutput']['permissionDecisionReason']
            self.assertIn('prerequisites', reason)  # Previously replaced by the later routing reason.
            self.assertIn('ROUTE-PROBLEM', reason)


class ReadToolCostTests(unittest.TestCase):
    def test_reads_do_not_start_the_pre_tool_hook(self):
        # A read has no write destination, so PreToolUse had nothing to decide for it.
        for name, matcher_key in (('hooks.json', 'PreToolUse'), ('codex-hooks.json', 'PreToolUse')):
            matcher = json.loads((ROOT / 'hooks' / name).read_text(encoding='utf-8'))['hooks'][matcher_key][0]['matcher']
            self.assertNotIn('Read', matcher.split('|'), name)
            self.assertNotIn('read_file', matcher.split('|'), name)
            self.assertIn('Write', matcher.split('|'), name)
        post = json.loads((ROOT / 'hooks/hooks.json').read_text(encoding='utf-8'))['hooks']['PostToolUse'][0]['matcher']
        self.assertIn('Read', post.split('|'))  # Read bodies still establish observed guidance.


if __name__ == '__main__':
    unittest.main()
