"""Explicit project lessons (compound rules): storage limits, domain routing and every delivery path."""
import json
from pathlib import Path
import unittest
from uuid import uuid4

from src.context.store import Store, compound_preview, work_domains
from src.runtime import antigravity
from src.runtime.hooks import ROOT
from tests.domain import test_hook_applications as _applications

LESSON = ['--domain', 'sql', '--anti-pattern', 'INNER JOIN BA030T for display-only item names',
          '--rule', 'Use LEFT OUTER JOIN BA030T when only ITEMNM/SPEC are displayed',
          '--evidence', 'User correction on sp_SAMPLE100_SELECT LIST branch; verified missing-item rows return']


class CompoundStoreTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.store = Store(Path(scratch.name), scratch.name)

    def test_requires_domain_evidence_and_limits(self):
        with self.store.connect(create=True) as connection:
            with self.assertRaises(ValueError):
                self.store.compound(connection, 'a', 'web', 'x', 'y', 'z')
            with self.assertRaises(ValueError):
                self.store.compound(connection, 'a', 'sql', 'x', 'y', '  ')
            with self.assertRaises(ValueError):
                self.store.compound(connection, 'a', 'sql', 'x' * 1001, 'y', 'z')
            for index in range(9):
                self.store.compound(connection, f'k{index}', 'sql', 'a' * 1000, 'r' * 1000, 'e' * 600)
            with self.assertRaises(ValueError):  # no silent eviction
                self.store.compound(connection, 'overflow', 'sql', 'a' * 1000, 'r' * 1000, 'e' * 600)
            self.store.compound(connection, 'k0', 'sql', 'short', 'short', 'short')  # replacing frees its own space

    def test_domain_filter_query_and_bounded_preview(self):
        with self.store.connect(create=True) as connection:
            self.store.compound(connection, 'sql-a', 'sql', 'anti', 'rule', 'ev')
            self.store.compound(connection, 'cs-a', 'csharp', 'anti', 'PostEditor before save', 'ev')
            self.store.compound(connection, 'gen', 'general', 'anti', 'rule', 'ev')
            self.assertEqual({'sql-a', 'gen'}, {e['id'] for e in self.store.compounds(connection, {'sql', 'general'})})
            self.assertEqual(['cs-a'], [e['id'] for e in self.store.compounds(connection, query='posteditor')])
            preview = compound_preview([{'id': str(i), 'domain': 'sql', 'anti_pattern': 'x' * 500, 'rule': 'y'}
                                        for i in range(9)], limit=6, width=100)
            self.assertEqual((9, 6, True), (preview['entry_count'], len(preview['preview']), preview['more_entries']))
            self.assertTrue(preview['preview'][0]['preview_truncated'])
            self.assertNotIn('evidence', preview['preview'][0])

    def test_work_domains(self):
        self.assertEqual({'sql', 'csharp'}, work_domains(['sql-save', 'csharp-grid', 'other']))


class CompoundLifecycleTests(unittest.TestCase):
    setUp = _applications.ApplicationTests.setUp
    event = _applications.ApplicationTests.event
    read = _applications.ApplicationTests.read
    state = _applications.ApplicationTests.state
    command = _applications.ApplicationTests.command
    apply = _applications.ApplicationTests.apply
    write = _applications.ApplicationTests.write
    load_required = _applications.ApplicationTests.load_required

    def test_cli_roundtrip_redacts_and_forgets(self):
        code, saved = self.command(['compound', 'ba030t-left-join', *LESSON[:-1], LESSON[-1] + ' password=hunter2'])
        self.assertEqual((0, 'saved'), (code, saved['status']))
        self.assertNotIn('hunter2', json.dumps(saved, ensure_ascii=False))
        _, listed = self.command(['compound-list', '--domain', 'csharp'])
        self.assertEqual(0, listed['entry_count'])
        _, full = self.command(['compound-get', 'ba030t-left-join'])
        self.assertIn('LEFT OUTER JOIN', full['compound_rules'][0]['rule'])
        _, found = self.command(['search', 'BA030T'])
        self.assertEqual(1, found['compound_rules']['entry_count'])
        _, recalled = self.command(['recall'])
        self.assertEqual('ba030t-left-join', recalled['compound_rules']['preview'][0]['id'])
        _, removed = self.command(['compound-forget', 'ba030t-left-join'])
        self.assertEqual('removed', removed['status'])
        _, missing = self.command(['compound-get', 'ba030t-left-join'])
        self.assertEqual('not_found', missing['status'])

    def test_apply_restore_and_saved_file_notice_are_domain_scoped(self):
        self.command(['compound', 'ba030t-left-join', *LESSON])
        self.command(['compound', 'cs-post-editor', '--domain', 'csharp', '--anti-pattern', 'save without PostEditor',
                      '--rule', 'call PostEditor first', '--evidence', 'lost last cell in T100'])
        target = self.project / 'Format.sql'
        target.write_text('SELECT A.QTY FROM INPUT_ROWS A;', encoding='utf-8')
        self.read('sql-formatting/SKILL.md')
        result = self.apply(['sql-format'], [target])
        self.assertEqual(['ba030t-left-join'], [e['id'] for e in result['compound_rules']['preview']])
        self.load_required(result)
        self.write(target)
        target.write_text('SELECT A.QTY FROM INPUT_ROWS A WHERE A.QTY > 0;', encoding='utf-8')
        notice = self.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(target)},
                            tool_response=target.read_text(encoding='utf-8'))
        text = json.dumps(notice, ensure_ascii=False)
        self.assertIn('ba030t-left-join', text)
        self.assertNotIn('cs-post-editor', text)
        self.assertNotIn('LEFT OUTER JOIN BA030T when', text)  # ids only, no repeated rule bodies
        self.event('PreCompact')
        restored = json.dumps(self.event('SessionStart', source='compact'), ensure_ascii=False)
        self.assertIn('project lessons', restored)
        self.assertIn('ba030t-left-join', restored)

    def test_antigravity_notice_names_lessons_without_creating_a_store(self):
        workspace = self.project
        storage = self.root / 'data/context-v1'
        common = {'conversationId': str(uuid4()), 'workspacePaths': [str(workspace)],
                  'lastUserInput': '$kh-uaf:sql-formatting --target Q.sql'}
        target = workspace / 'Q.sql'
        target.write_text('SELECT A.QTY FROM T A\n', encoding='utf-8')
        args = {'TargetFile': str(target), 'CodeContent': 'SELECT ISNULL(A.QTY, 0) AS QTY FROM T A\n'}

        def run():
            antigravity.handle('PreToolUse', {**common, 'stepIdx': 1, 'toolCall': {'name': 'write_to_file', 'args': args}}, storage=storage)
            target.write_text(args['CodeContent'], encoding='utf-8')
            antigravity.handle('PostToolUse', {**common, 'stepIdx': 1, 'error': '', 'toolCall': {'name': 'write_to_file', 'args': args}}, storage=storage)
            return json.dumps(antigravity.handle('PreInvocation', {**common, 'stepIdx': 2}, storage=storage), ensure_ascii=False)

        self.assertNotIn('project lessons', run())
        self.assertFalse(Store(storage, str(workspace)).path.exists())
        self.command(['compound', 'ba030t-left-join', *LESSON])
        target.write_text('SELECT A.QTY FROM T A\n', encoding='utf-8')
        self.assertIn('ba030t-left-join', run())


if __name__ == '__main__':
    unittest.main()
