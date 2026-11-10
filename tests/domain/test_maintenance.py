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

    def test_ui_context_wrappers_are_not_human_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'session.jsonl'
            messages = ['<external_codex_apps_open_page>{"page_id":null}</external_codex_apps_open_page>',
                        '<recommended_plugins>plugin list</recommended_plugins>',
                        '<external_codex_apps_open_page>{"page_id":null}</external_codex_apps_open_page>\nFix the selected source',
                        'Fix the source']
            path.write_text('\n'.join(json.dumps({'type': 'event_msg', 'payload': {'type': 'user_message', 'message': text}})
                                      for text in messages), encoding='utf-8')
            report = inspect_sessions([path])
            self.assertEqual(2, len(report['user_candidates']))
            self.assertEqual(2, report['files'][0]['counts']['environment_or_automatic_records'])

    def test_tool_evidence_locations_retrieve_real_return_records(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'session.jsonl'
            records = [
                {'type': 'session_meta', 'payload': {'id': 'fictional-session'}},
                {'timestamp': '2026-11-10T01:00:00Z', 'type': 'response_item',
                 'payload': {'type': 'function_call', 'name': 'exec', 'call_id': 'read',
                             'arguments': 'Get-Content source.cs # password=private-value'}},
                {'timestamp': '2026-11-10T01:00:01Z', 'type': 'response_item',
                 'payload': {'type': 'function_call_output', 'call_id': 'read', 'output': 'first result'}},
                {'timestamp': '2026-11-10T01:00:02Z', 'type': 'response_item',
                 'payload': {'type': 'function_call_output', 'call_id': 'read', 'output': 'remaining result'}},
                {'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'apply_patch',
                                                     'call_id': 'write', 'input': 'change source.cs'}}]
            path.write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in records), encoding='utf-8')
            default = inspect_sessions([path])
            self.assertNotIn('argument_excerpt', default['tool_calls'][0])
            report = inspect_sessions([path], tool_excerpt_chars=100)
            read, write = report['tool_calls']
            self.assertNotIn('private-value', json.dumps(report))
            self.assertEqual('2026-11-10T01:00:00Z', read['timestamp'])
            self.assertEqual(2, len(read['result_locations']))
            with path.open('rb') as stream:
                for location in read['result_locations']:
                    stream.seek(location['byte_offset'])
                    returned = json.loads(stream.readline())
                    self.assertEqual('read', returned['payload']['call_id'])
                    self.assertEqual(records[location['line']-1], returned)
            self.assertEqual('change source.cs', write['argument_excerpt'])
            self.assertEqual([], write['result_locations'])
            self.assertEqual('call_without_observed_return', write['observed_state'])

    def test_tool_excerpt_is_bounded_and_invalid_limits_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'session.jsonl'
            path.write_text(json.dumps({'type': 'response_item', 'payload': {
                'type': 'function_call', 'name': 'exec', 'call_id': 'c1',
                'arguments': {'command': 'read a long fictional source path'}}}), encoding='utf-8')
            call = inspect_sessions([path], tool_excerpt_chars=8)['tool_calls'][0]
            self.assertEqual(8, len(call['argument_excerpt']))
            self.assertTrue(call['argument_truncated'])
            for limit in (-1, 2001):
                with self.assertRaises(ValueError):
                    inspect_sessions([path], tool_excerpt_chars=limit)

    def test_tool_previews_mask_structured_and_quoted_secret_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'session.jsonl'
            for argument in ({'password': 'fictional-secret-123'},
                             json.dumps({'api_key': 'fictional-secret-123'}),
                             json.dumps({'env': {'client_secret': 'fictional-secret-123'}}),
                             json.dumps({'access_token': 'fictional-secret-123"suffix'}),
                             "{'password': 'fictional-secret-123'}"):
                with self.subTest(argument=argument):
                    path.write_text(json.dumps({'type': 'response_item', 'payload': {
                        'type': 'function_call', 'name': 'exec', 'call_id': 'c1',
                        'arguments': argument}}), encoding='utf-8')
                    report = inspect_sessions([path], tool_excerpt_chars=1000)
                    serialized = json.dumps(report)
                    self.assertNotIn('fictional-secret-123', serialized)
                    self.assertNotIn('suffix', serialized)
                    self.assertIn('[REDACTED]', serialized)

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

    def test_package_checks_agent_names_and_local_references(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.codex-plugin').mkdir()
            (root / '.codex-plugin/plugin.json').write_text(json.dumps({'name': 'sample'}))
            (root / 'skills/sample').mkdir(parents=True)
            (root / 'skills/sample/SKILL.md').write_text('---\nname: sample\ndescription: Sample\n---\nRun the sample.')
            (root / 'agents').mkdir()
            agent = root / 'agents/worker.md'
            agent.write_text('---\nname: worker\ndescription: Work\n---\nRead [source](../skills/sample/SKILL.md).')
            result = check_package(root)
            self.assertEqual([], result.issues)
            self.assertEqual(['worker'], result.metadata['agent_names'])

            agent.write_text('---\nname: reviewer\ndescription: Review\n---\nRead [missing](../missing.md).')
            result = check_package(root)
            self.assertEqual({'agent_metadata_invalid', 'agent_link_broken'}, {i.code for i in result.issues})

            (root / '.claude-plugin').mkdir()
            manifest = root / '.claude-plugin/plugin.json'
            manifest.write_text(json.dumps({'agents': './agents/'}))
            result = check_package(root)
            self.assertEqual({'agent_path_invalid'}, {i.code for i in result.issues})

            agent.write_text('---\nname: worker\ndescription: Work\n---\nRead [source](../skills/sample/SKILL.md).')
            manifest.write_text(json.dumps({'agents': ['./agents/worker.md']}))
            result = check_package(root)
            self.assertEqual([], result.issues)
            self.assertEqual(['worker'], result.metadata['agent_names'])


if __name__ == '__main__':
    unittest.main()
