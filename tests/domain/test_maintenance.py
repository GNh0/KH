import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from src.artifacts.checks import check_artifact
from src.maintenance.package_check import check_package
from src.maintenance.pb_profiles import write_profile, read_profile
from src.maintenance.session_report import inspect_sessions


class MaintenanceTests(unittest.TestCase):
    def test_ooxml_structure_does_not_claim_rendering(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'document.docx'
            with zipfile.ZipFile(path, 'w') as archive:
                for name, root_name in {'[Content_Types].xml': 'Types', '_rels/.rels': 'Relationships', 'word/document.xml': 'document'}.items():
                    archive.writestr(name, '<' + root_name + ' />')
            result = check_artifact(path)
            self.assertTrue(result.success)
            self.assertTrue(any('rendered' in x for x in result.not_checked))

    def test_broken_ooxml_is_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'book.xlsx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('[Content_Types].xml', '<broken>')
            self.assertFalse(check_artifact(path).success)

    def test_csv_korean_and_uneven_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'data.csv'
            path.write_text('이름,수량\n품목,3\n누락\n', encoding='utf-8-sig')
            result = check_artifact(path)
            self.assertTrue(result.success)
            self.assertEqual([1, 2], result.metadata['column_counts'])
            self.assertEqual('warning', result.issues[0].severity)

    def test_invalid_json_and_empty_file_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'data.json'
            path.write_text('{x: 1}')
            self.assertFalse(check_artifact(path).success)
            path.write_bytes(b'')
            self.assertFalse(check_artifact(path).success)

    def test_profile_does_not_search_authors_or_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'scope.json'
            profile = {'name': 'screen', 'scope': {'project': 'selected.csproj'}, 'defaults': {'row_access': 'focused'}}
            write_profile(profile, path)
            self.assertEqual(profile, read_profile(path))
            with self.assertRaises(FileExistsError):
                write_profile(profile, path)

    def test_session_mirrors_are_distinct_from_repeated_user_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'session.jsonl'
            event = {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': 'SQL 정리만 해줘'}}
            response = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'SQL 정리만 해줘'}]}}
            records = [{'type': 'session_meta', 'payload': {'id': 'fictional-session'}}, event, response, event, response]
            path.write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in records), encoding='utf-8')
            report = inspect_sessions([path])
            self.assertEqual(2, len(report['user_candidates']))
            self.assertEqual(2, report['files'][0]['counts']['adjacent_user_mirrors'])
            self.assertGreater(report['user_candidates'][0]['byte_offset'], 0)

    def test_tool_return_is_not_an_agent_completion_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'session.jsonl'
            records = [
                {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'spawn_agent', 'call_id': 'c1'}},
                {'type': 'response_item', 'payload': {'type': 'function_call_output', 'call_id': 'c1', 'output': 'password=private-value'}},
                {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'wait_agent', 'call_id': 'c2'}}]
            path.write_text('\n'.join(json.dumps(x) for x in records))
            report = inspect_sessions([path])
            self.assertEqual(['tool_return_recorded', 'call_without_observed_return'], [x['observed_state'] for x in report['tool_calls']])
            self.assertNotIn('private-value', json.dumps(report))

    def test_session_excerpts_mask_secret_and_do_not_auto_infer_preference(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'session.jsonl'
            path.write_text(json.dumps({'type': 'event_msg', 'payload': {'type': 'user_message', 'message': 'password=very-private SQL'}}))
            report = inspect_sessions([path], pattern='SQL')
            self.assertNotIn('very-private', json.dumps(report))
            self.assertNotIn('preferences', report)

    def test_package_detects_broken_reference_and_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'.codex-plugin').mkdir()
            (root/'.codex-plugin/plugin.json').write_text(json.dumps({'name': 'sample', 'skills': './skills/'}))
            (root/'skills/sample').mkdir(parents=True)
            (root/'skills/sample/SKILL.md').write_text('---\nname: sample\ndescription: Sample use\n---\n[missing](references/no.md)')
            (root/'src').mkdir()
            (root/'src/check.py').write_text('from src.missing import check\n')
            result = check_package(root)
            self.assertEqual({'skill_link_broken', 'internal_import_missing'}, {i.code for i in result.issues})


if __name__ == '__main__':
    unittest.main()
