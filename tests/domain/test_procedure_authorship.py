"""Authorship setup supplements SQL-FORMATTING without selecting arbitrary people."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.context.store import Store, session_key
from src.runtime.guidance import document
from src.runtime.hooks import ROOT, handle
from src.sql.checks import check_sql
from src.sql.procedure_authorship import procedure_headers, procedure_responsibilities, review_procedure_headers


def procedure(author='테스트 작성자', name='dbo.Sample_SELECT', action='CREATE PROCEDURE', date='26.11.18'):
    return f'''-- =============================================
-- AUTHOR:      {author}
-- CREATE DATE: {date}
-- DESCRIPTION: 예시 프로그램 조회
-- =============================================
{action} {name}
AS
BEGIN
    SELECT A.VALUE
    FROM SAMPLE_ROWS A
END
'''


class HeaderTests(unittest.TestCase):
    def test_search_metadata_and_internal_selects_are_not_output(self):
        baseline = procedure()
        for label in ('REFERENCE AUTHOR', 'REFERENCE AUTHORS', '참고 작성자', '참조 작성자'):
            candidate = baseline.replace('-- CREATE DATE:', f'-- {label}: Example\n-- CREATE DATE:')
            self.assertIn('procedure_reference_author_in_header', [i.code for i in review_procedure_headers(candidate)])
            self.assertNotIn('procedure_reference_author_in_header', [i.code for i in review_procedure_headers(candidate, candidate)])
            revised = candidate.replace(f'{label}: Example', f'{label}: Someone else')
            self.assertIn('procedure_reference_author_in_header', [i.code for i in review_procedure_headers(revised, candidate)])
        for statement, returns in (
                ('INSERT @stage (id) SELECT id FROM INPUT; UPDATE A SET X=1;', False),
                ('SELECT @id = id FROM INPUT;', False),
                ('SELECT @qty += qty FROM INPUT;', False),
                ('DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT id FROM INPUT;', False),
                ('SELECT id INTO #staged FROM INPUT;', False),
                ('SELECT CASE WHEN @id = 1 THEN 1 END AS x INTO #tmp FROM INPUT;', False),
                ('SELECT CASE WHEN @id = 1 THEN 1 END AS x FROM INPUT;', True),
                ('IF EXISTS (SELECT 1 FROM INPUT) RETURN;', False),
                ('INSERT @stage SELECT id FROM INPUT; SELECT @id AS id;', True)):
            sql = '-- AUTHOR: Example\nCREATE PROC dbo.P AS ' + statement
            self.assertEqual(returns, 'sql-select' in procedure_responsibilities(sql, start=1, end=2), statement)
        for name in ('@stage', '#stage', 'dbo.FinalRows'):
            sql = '-- AUTHOR: Example\nCREATE PROC dbo.P AS INSERT INTO ' + name + ' SELECT id FROM INPUT;'
            self.assertEqual(name == 'dbo.FinalRows', 'sql-save' in procedure_responsibilities(sql, start=1, end=2))

    def test_header_fields_and_all_supported_declarations(self):
        for action in ('CREATE PROCEDURE', 'ALTER PROC', 'CREATE OR ALTER PROCEDURE'):
            source = procedure(action=action)
            self.assertEqual(1, len(procedure_headers(source)))
            self.assertFalse([i for i in review_procedure_headers(source, author='테스트 작성자') if i.severity == 'error'])
        for source in ('CREATE PROCEDURE dbo.Bad AS SELECT 1;', procedure(author='{작성자명}'),
                       procedure(date='26.02.30'), procedure().replace('예시 프로그램 조회', '조회'),
                       procedure().replace('예시 프로그램 조회', '예시 프로그램 처리OR조회')):
            self.assertTrue(review_procedure_headers(source))

    def test_comments_and_literals_cannot_borrow_a_header_for_a_real_declaration(self):
        source = procedure() + "\nPRINT 'AUTHOR: Other';\nCREATE PROC dbo.NoHeader AS SELECT 1;"
        self.assertEqual(['procedure_header_required'], [i.code for i in review_procedure_headers(source)])
        self.assertEqual([], procedure_headers("PRINT 'CREATE PROC fake AS SELECT 1'; -- CREATE PROCEDURE fake\n"))
        self.assertEqual('procedure_definition_required', review_procedure_headers('SELECT 1;')[0].code)
        false_header = '/*\n' + procedure().split('CREATE PROCEDURE')[0].rstrip().removesuffix('-- =============================================') + '-- */\n-- =============================================\nCREATE PROC dbo.Fake AS SELECT 1;'
        self.assertIn('procedure_header_required', [i.code for i in review_procedure_headers(false_header)])

    def test_new_author_and_existing_attribution_are_distinct(self):
        old = procedure(author='원작성자', date='24.02.29')
        self.assertEqual([], review_procedure_headers(old, old, author='현재 작업자'))
        self.assertIn('procedure_author_mismatch', [i.code for i in review_procedure_headers(old, author='현재 작업자')])
        edited = old.replace('24.02.29', '26.11.18')
        findings = review_procedure_headers(edited, old)
        self.assertEqual(['procedure_original_attribution_changed'], [i.code for i in findings])
        self.assertEqual('warning', findings[0].severity)
        for action in ('ALTER PROCEDURE', 'CREATE OR ALTER PROCEDURE'):
            exported = old.replace('CREATE PROCEDURE', action)
            self.assertNotIn('procedure_author_mismatch', [i.code for i in review_procedure_headers(exported, author='현재 작업자')])
            self.assertIn('procedure_original_attribution_unverified', [i.code for i in review_procedure_headers(exported, author='현재 작업자')])
        unqualified = old.replace('dbo.Sample_SELECT', 'Sample_SELECT')
        qualified = old.replace('dbo.Sample_SELECT', 'OPS.Sample_SELECT')
        self.assertNotIn('procedure_author_mismatch', [i.code for i in review_procedure_headers(qualified, unqualified, author='현재 작업자')])

    def test_authorship_does_not_replace_sql_style_or_value_rules(self):
        source = procedure().replace('SELECT A.VALUE', 'SELECT ISNULL(A.VALUE, 0)')
        result = check_sql(source, require_procedure_header=True, procedure_author='테스트 작성자')
        self.assertIn('value_fallback_review', [i.code for i in result.issues])
        old = 'CREATE PROC dbo.Legacy AS SELECT 1;'
        formatting = check_sql(old, original=old)
        self.assertNotIn('procedure_header_required', [i.code for i in formatting.issues])

    def test_legacy_author_dates_and_structured_object_names(self):
        legacy = '-- AUTHOR: 원작성자\n-- CREATE DATE: 2018-04-03\nCREATE PROC dbo.Sample_SELECT AS SELECT 1;'
        replacement = procedure(author='새작성자')
        self.assertEqual(2, len([i for i in review_procedure_headers(replacement, legacy)
                                 if i.code == 'procedure_original_attribution_changed']))
        self.assertFalse(review_procedure_headers(procedure(date='2025/03/04')))
        self.assertIn('procedure_creation_date_invalid', [i.code for i in review_procedure_headers(procedure(date='202613'))])
        self.assertIn('procedure_creation_date_unverified', [i.code for i in review_procedure_headers(procedure(date='2025년 3월 4일'))])
        old = procedure(name='[OPS.ARCHIVE].[Read]')
        new = procedure(author='다른작성자', name='[OPS].[ARCHIVE.Read]')
        self.assertIn('procedure_author_mismatch', [i.code for i in review_procedure_headers(new, old, author='테스트 작성자')])
        for body in ('COMMIT;', 'CHECKPOINT;', 'RETURN;', 'EXTERNAL NAME [ASSY].[CLASS].[READ];'):
            source = procedure().split('\nAS\n', 1)[0] + '\nAS ' + body
            self.assertTrue(procedure_headers(source)[0].body_observed)
        inline = 'CREATE PROC dbo.Prior AS SELECT 1;\nGO -- AUTHOR: 참조 작성자\nCREATE PROC dbo.Next AS SELECT 2;'
        self.assertNotIn('AUTHOR', procedure_headers(inline)[1].fields)
        proper = inline.replace('GO -- AUTHOR', 'GO\n-- AUTHOR')
        self.assertEqual('참조 작성자', procedure_headers(proper)[1].fields['AUTHOR'])


class AuthorshipLifecycleTests(unittest.TestCase):
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
        self.scope = {'cwd': str(self.project), 'session_id': 'author-test', 'transcript_path': str(self.log)}
        self.target = self.project / 'Target.sql'
        self.reference = self.project / 'Reference.sql'
        self.reference.write_text(procedure(author='참조 작성자'), encoding='utf-8')
        self.store = Store(self.root / 'data/context-v1', str(self.project))
        self.key = session_key(self.scope, 'codex')
        self.read_guidance('sql-formatting/SKILL.md')

    def event(self, name, **values):
        return handle({**self.scope, 'hook_event_name': name, **values}, 'codex')

    def state(self):
        with self.store.connect() as connection:
            return self.store.load(connection, self.key)

    def read_guidance(self, relative):
        path, body, _start, _end = document(ROOT, relative)
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(path)}, tool_response=body)

    def apply(self, extra=(), *, work='sql-select', target=None, reference=None):
        args = [sys.executable, '-B', str(ROOT / 'scripts/kh_context.py'), '--cwd', str(self.project),
                '--session', self.scope['session_id'], '--transcript', str(self.log), '--host', 'codex',
                '--data-root', str(self.root / 'data/context-v1'), '--epoch', self.state()['application_epoch'],
                'apply', '--work', work, '--target', str(target or self.target), '--reference', str(reference or self.reference), *extra]
        process = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', timeout=20)
        self.assertEqual(0, process.returncode, process.stderr + process.stdout)
        result = json.loads(process.stdout)
        for relative in result['files'][0]['required']:
            self.read_guidance(relative)
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(self.reference)}, tool_response=self.reference.read_text(encoding='utf-8'))
        return result

    def write(self):
        return self.event('PreToolUse', tool_name='Write', tool_input={'file_path': str(self.target)})

    def test_missing_names_wrong_reference_and_reuse(self):
        self.apply()
        self.assertIn('ask the user', self.write()['hookSpecificOutput']['permissionDecisionReason'])
        self.apply(('--author', '현재 작성자', '--reference-author', '다른 사람'))
        self.assertEqual('deny', self.write()['hookSpecificOutput']['permissionDecision'])
        self.apply(('--author', '현재 작성자', '--reference-author', '참조 작성자'))
        self.assertEqual({}, self.write())
        result = self.apply()
        self.assertEqual({'author': '현재 작성자', 'reference_author': '참조 작성자'}, result['sql_authorship'])
        self.assertEqual({}, self.write())

    def test_multiple_search_names_match_existing_sps_independently_of_target_author(self):
        args = ('--author', 'Target Writer', '--reference-author', 'First Writer', '--reference-author', 'Second Writer')
        for name in ('First Writer', 'Second Writer', 'Target Writer', 'First Writer,Second Writer'):
            with self.subTest(name=name):
                self.reference.write_text(procedure(author=name), encoding='utf-8')
                self.apply(args)
                if name in ('First Writer', 'Second Writer'):
                    self.assertEqual({}, self.write())
                else:
                    self.assertEqual('deny', self.write()['hookSpecificOutput']['permissionDecision'])
        self.reference.write_text(procedure(author='Second Writer'), encoding='utf-8')
        self.apply()
        self.assertEqual({}, self.write())
        self.target.write_text(procedure(author='Second Writer'), encoding='utf-8')
        self.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(self.target)})
        self.assertIn('procedure_author_mismatch', self.state()['files'][str(self.target)]['check']['errors'])

    def test_require_every_selected_sp_read_and_release_superseded_selection(self):
        second = self.project / 'OtherReference.sql'
        second.write_text(procedure(author='Other'), encoding='utf-8')
        names = ('--author', 'Target', '--reference-author', '참조 작성자', '--reference-author', 'Other')
        self.apply((*names, '--reference', str(second)))
        self.assertEqual('deny', self.write()['hookSpecificOutput']['permissionDecision'])
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(second)}, tool_response=second.read_text(encoding='utf-8'))
        self.assertEqual({}, self.write())
        second.unlink()
        self.assertEqual('deny', self.write()['hookSpecificOutput']['permissionDecision'])
        self.apply(('--author', 'Target', '--reference-author', '참조 작성자'))
        self.assertEqual({}, self.write())

    def test_correct_author_does_not_certify_a_missing_generated_header(self):
        self.apply(('--author', '현재 작성자', '--reference-author', '참조 작성자'))
        self.assertEqual({}, self.write())
        self.target.write_text('CREATE PROCEDURE dbo.New_SELECT AS SELECT 1;', encoding='utf-8')
        self.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(self.target)})
        self.assertIn('procedure_header_required', self.state()['files'][str(self.target)]['check']['errors'])
        self.assertEqual('block', self.event('Stop')['decision'])

    def test_regular_query_and_other_chat_have_no_author_setup(self):
        self.apply(work='sql-query')
        self.assertEqual({}, self.write())
        other = {**self.scope, 'session_id': 'other-chat', 'hook_event_name': 'PreToolUse',
                 'tool_name': 'Write', 'tool_input': {'file_path': str(self.target)}}
        self.assertEqual({}, handle(other, 'codex'))
        self.assertNotIn('sql_authorship', self.state())

    def test_a_new_file_author_does_not_reassign_an_already_owned_sp(self):
        self.apply(('--author', '현재 작성자', '--reference-author', '참조 작성자'))
        self.apply(('--author', '두번째 작성자', '--reference-author', '참조 작성자'), target=self.project / 'Other.sql')
        self.assertEqual({}, self.write())
        self.target.write_text(procedure(author='현재 작성자'), encoding='utf-8')
        self.event('PostToolUse', tool_name='Write', tool_input={'file_path': str(self.target)})
        self.assertNotIn('procedure_author_mismatch', self.state()['files'][str(self.target)]['check']['errors'])

    def test_complete_authored_body_is_required_but_legacy_header_shape_is_separate(self):
        names = ('--author', '현재 작성자', '--reference-author', '참조 작성자')
        self.apply(names, reference=str(self.reference) + '#L6-L6')
        self.assertEqual('deny', self.write()['hookSpecificOutput']['permissionDecision'])
        self.apply(names)
        self.assertEqual({}, self.write())
        self.reference.write_text('-- AUTHOR: 참조 작성자\nCREATE PROC dbo.Reference AS SELECT 1;', encoding='utf-8')
        self.apply(names)
        self.assertEqual({}, self.write())
        self.reference.write_text('-- AUTHOR: 참조 작성자\nCREATE PROC dbo.Reference AS', encoding='utf-8')
        self.apply(names)
        self.assertEqual('deny', self.write()['hookSpecificOutput']['permissionDecision'])


if __name__ == '__main__':
    unittest.main()
