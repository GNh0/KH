import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.context.store import Store, session_key
from src.context.transcript import capture, user_text
from src.runtime.hooks import CYCLE, ROOT, handle
from src.runtime.hooks import file_paths, line_hashes, update_files, restore


class HooksContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = patch.dict(os.environ, {'PLUGIN_DATA': str(self.root / 'data'), 'KH_HOOKS_MODE': 'enforce'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.log = self.root / 'native.jsonl'
        self.log.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': 's1'}}) + '\n')
        self.base = {'cwd': str(self.project), 'session_id': 's1', 'transcript_path': str(self.log)}

    def event(self, name, **values):
        return handle({**self.base, 'hook_event_name': name, **values}, 'codex')

    def append_user(self, text):
        with self.log.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'type': 'event_msg', 'payload': {'type': 'user_message', 'message': text}}, ensure_ascii=False) + '\n')

    def prerequisites(self):
        body = '\n'.join((ROOT / 'skills' / relative).read_text(encoding='utf-8-sig')
                         for relative in (CYCLE, 'sql-formatting/SKILL.md'))
        return self.event('PostToolUse', tool_name='Bash', tool_input={'command': 'read skills'}, tool_response={'output': body})

    def edit_event(self, name):
        return self.event(name, tool_name='apply_patch', tool_input={'command': '*** Begin Patch\n*** Add File: example.sql\n+SELECT 1\n*** End Patch'}, tool_response={'output': 'Success'})

    def test_plain_chat_does_not_create_storage_or_emit_context(self):
        for name in ('SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'Stop', 'SessionEnd'):
            self.assertEqual({}, self.event(name, prompt='안녕', tool_name='Bash', tool_input={'command': 'Get-Date'}, tool_response='today'))
        self.assertFalse((self.root / 'data').exists())

    def test_retry_never_substitutes_for_read_and_truncated_read_is_insufficient(self):
        for _ in range(3):
            denied = self.edit_event('PreToolUse')
            self.assertEqual('deny', denied['hookSpecificOutput']['permissionDecision'])
        self.event('PostToolUse', tool_name='Bash', tool_response='sql-formatting/SKILL.md opened [truncated]')
        self.assertEqual('deny', self.edit_event('PreToolUse')['hookSpecificOutput']['permissionDecision'])
        self.prerequisites()
        self.assertEqual({}, self.edit_event('PreToolUse'))

    def test_read_before_first_write_is_retained(self):
        self.prerequisites()
        self.assertEqual({}, self.edit_event('PreToolUse'))

    def test_changed_file_requires_actual_returned_body_and_later_edit_invalidates_it(self):
        self.prerequisites()
        self.edit_event('PreToolUse')
        path = self.project / 'example.sql'
        path.write_text('SELECT 1\n', encoding='utf-8')
        response = self.edit_event('PostToolUse')
        self.assertIn('partial', response['hookSpecificOutput']['additionalContext'])
        self.assertEqual('block', self.event('Stop')['decision'])
        # No unbounded automatic continuation even if the host forgets its active flag.
        self.assertNotIn('decision', self.event('Stop'))
        self.event('PostToolUse', tool_name='Bash', tool_response={'output': 'SELECT 1\n'})
        self.assertEqual({}, self.event('Stop'))
        path.write_text('SELECT 2\n', encoding='utf-8')
        self.assertEqual('block', self.event('Stop')['decision'])
        self.event('Interrupt')
        self.assertEqual({}, self.event('Stop'))

    def test_other_session_does_not_inherit_prerequisites_or_checkpoint(self):
        self.prerequisites()
        other = {**self.base, 'session_id': 's2', 'hook_event_name': 'PreToolUse',
                 'tool_name': 'Write', 'tool_input': {'file_path': str(self.project / 'other.sql')}}
        self.assertEqual('deny', handle(other, 'codex')['hookSpecificOutput']['permissionDecision'])
        output = handle({**other, 'hook_event_name': 'SessionStart'}, 'codex')
        self.assertEqual({}, output)

    def test_compaction_restart_latest_correction_and_original_recall(self):
        self.append_user('기본 폭을 유지하고 저장 처리 고쳐줘')
        self.append_user('앞의 저장 작업은 취소하고 조회만 수정해')
        output = self.event('PreCompact')
        self.assertIn('preserved', output['systemMessage'])
        restored = self.event('PostCompact')['hookSpecificOutput']['additionalContext']
        self.assertLess(restored.index('조회만'), restored.index('기본 폭'))
        self.assertIn('byte_offset', restored)
        self.assertEqual({}, self.event('SessionStart', source='compact'))
        # A fresh host process reloads the exact same session from disk.
        native = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/kh_hook.py'), '--host', 'codex'],
                                input=json.dumps({**self.base, 'hook_event_name': 'SessionStart', 'source': 'resume'}),
                                text=True, encoding='utf-8', capture_output=True, check=True, timeout=10)
        self.assertIn('조회만', json.loads(native.stdout)['hookSpecificOutput']['additionalContext'])
        self.assertFalse(native.stderr)

    def test_only_user_evidence_is_copied_and_secrets_are_redacted(self):
        self.append_user('password=fictional-private 기본 정렬 유지')
        with self.log.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'type': 'response_item', 'payload': {'type': 'reasoning', 'text': 'hidden-reasoning-marker'}}) + '\n')
        self.event('PreCompact')
        output = self.event('PostCompact')
        serialized = json.dumps(output, ensure_ascii=False)
        self.assertNotIn('fictional-private', serialized)
        self.assertNotIn('hidden-reasoning-marker', serialized)
        self.assertIn('[REDACTED]', serialized)

    def test_claude_compaction_reinjects_via_session_start_only(self):
        self.log.write_text(json.dumps({'type': 'user', 'sessionId': 's1', 'message': {'content': [{'type': 'text', 'text': '라벨 높이 유지'}]}}) + '\n')
        handle({**self.base, 'hook_event_name': 'PreCompact'}, 'claude')
        self.assertEqual({}, handle({**self.base, 'hook_event_name': 'PostCompact'}, 'claude'))
        output = handle({**self.base, 'hook_event_name': 'SessionStart', 'source': 'compact'}, 'claude')
        self.assertIn('라벨 높이', output['hookSpecificOutput']['additionalContext'])

    def test_unknown_format_and_incomplete_tail_do_not_claim_complete_capture(self):
        self.log.write_text('{not valid json}\n{"unfinished":', encoding='utf-8')
        state = {'users': []}
        capture(state, self.base, 'codex')
        self.assertEqual(1, state['malformed_records'])
        self.assertGreater(state['backlog_bytes'], 0)
        self.assertEqual([], state['users'])

    def test_durable_project_memory_is_explicit_capacity_bounded_and_isolated(self):
        store = Store(self.root / 'memory', str(self.project))
        with store.connect(create=True) as connection:
            store.remember(connection, 'label', '라벨은 실제 기본 정렬을 따른다')
            self.assertEqual(1, len(store.memories(connection, '기본 정렬')))
            with self.assertRaises(ValueError):
                store.remember(connection, 'oversize', 'x' * 4001)
            self.assertEqual(1, len(store.memories(connection)))
            key = session_key(self.base, 'codex')
            self.assertEqual([], store.load(connection, key)['users'])
        other = Store(self.root / 'memory', str(self.root / 'other-project'))
        with other.connect() as connection:
            self.assertIsNone(connection)

    def test_malformed_hook_input_has_one_json_diagnostic_and_exits(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/kh_hook.py'), '--host', 'codex'],
                                input='{bad', text=True, capture_output=True, check=True, timeout=10)
        self.assertIn('unverified', json.loads(result.stdout)['systemMessage'])
        self.assertFalse(result.stderr)

    def test_advisory_and_off_modes_do_not_deny(self):
        with patch.dict(os.environ, {'KH_HOOKS_MODE': 'advisory'}):
            self.assertNotIn('permissionDecision', self.edit_event('PreToolUse').get('hookSpecificOutput', {}))
        with patch.dict(os.environ, {'KH_HOOKS_MODE': 'off'}):
            self.assertEqual({}, self.edit_event('PreToolUse'))

    def test_real_tool_input_shapes_and_shell_destinations(self):
        expected = self.project / 'example.sql'
        raw = {**self.base, 'tool_name': 'apply_patch', 'tool_input': '*** Add File: example.sql\n+SELECT 1'}
        self.assertEqual([expected], file_paths(raw))
        shell = {**self.base, 'tool_name': 'exec_command', 'tool_input': {'cmd': "Set-Content -LiteralPath 'example.sql' -Value 'SELECT 1'"}}
        self.assertEqual([expected], file_paths(shell))
        shell['tool_input']['cmd'] = "Get-Content 'example.sql' | Set-Content 'notes.txt'"
        self.assertEqual([], file_paths(shell))

    def test_numbered_and_segmented_reads_and_version_change(self):
        for relative in (CYCLE, 'sql-formatting/SKILL.md'):
            body = (ROOT / 'skills' / relative).read_text(encoding='utf-8-sig')
            lines = body.splitlines()
            for start, end in ((0, len(lines)//2), (len(lines)//2, len(lines))):
                returned = '\n'.join(f'{i+1}: {lines[i]}' for i in range(start, end))
                self.event('PostToolUse', tool_name='Read', tool_response=returned)
        self.assertEqual({}, self.edit_event('PreToolUse'))
        # Change the expected prerequisite in a separate fixture, preserving the production tree.
        fake = self.root / 'plugin'
        for relative in (CYCLE, *(domain + '/SKILL.md' for domain in ('sql-formatting', 'csharp-designer-style-harness', 'pb-to-csharp-migration-harness'))):
            destination = fake / 'skills' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text((ROOT / 'skills' / relative).read_text(encoding='utf-8-sig') + '\nNEW REQUIRED TEXT\n', encoding='utf-8')
        with patch('src.runtime.hooks.ROOT', fake):
            self.assertEqual('deny', self.edit_event('PreToolUse')['hookSpecificOutput']['permissionDecision'])

    def test_pause_survives_status_and_long_stop_request(self):
        self.prerequisites()
        self.edit_event('PreToolUse')
        (self.project / 'example.sql').write_text('SELECT 1\n')
        self.edit_event('PostToolUse')
        self.event('Interrupt')
        self.event('UserPromptSubmit', prompt='status?')
        self.assertEqual({}, self.event('Stop'))
        self.assertEqual('deny', self.edit_event('PreToolUse')['hookSpecificOutput']['permissionDecision'])
        self.event('UserPromptSubmit', prompt='일단 작업 멈춰줘. 지금은 아무것도 하지 마.')
        self.assertEqual({}, self.event('Stop'))

    def test_stop_cancel_button_requests_and_advisory_pause(self):
        self.prerequisites()
        for prompt in ('Cancel 버튼의 Click 이벤트를 구현해줘.', 'Stop 버튼을 추가해줘.', 'Save 버튼을 추가해줘.'):
            self.event('UserPromptSubmit', prompt=prompt)
            self.assertEqual({}, self.edit_event('PreToolUse'))
        self.event('Interrupt')
        with patch.dict(os.environ, {'KH_HOOKS_MODE': 'advisory'}):
            output = self.edit_event('PreToolUse')
            self.assertNotIn('permissionDecision', output['hookSpecificOutput'])

    def test_one_line_at_a_time_can_complete_prerequisite_reads(self):
        for relative in (CYCLE, 'sql-formatting/SKILL.md'):
            for line in (ROOT / 'skills' / relative).read_text(encoding='utf-8-sig').splitlines():
                if line.strip():
                    self.event('PostToolUse', tool_name='Read', tool_response=line)
        self.assertEqual({}, self.edit_event('PreToolUse'))

    def test_large_existing_file_only_requires_changed_range_with_context(self):
        self.prerequisites()
        path = self.project / 'example.sql'
        lines = [f'-- unrelated source line {i}' for i in range(120)]
        lines[60] = 'SELECT 1'
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.edit_event('PreToolUse')
        lines[60] = 'SELECT 2'
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.edit_event('PostToolUse')
        self.assertEqual('block', self.event('Stop')['decision'])
        # Return the actual changed unit/context in two chunks, with line numbers.
        for start, end in ((58, 61), (61, 63)):
            self.event('PostToolUse', tool_name='Read', tool_response='\n'.join(f'{i+1}: {lines[i]}' for i in range(start, end)))
        self.assertEqual({}, self.event('Stop'))
        # Deletion requires fresh adjacent-context observation, even if it was read previously.
        self.edit_event('PreToolUse')
        del lines[60]
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.edit_event('PostToolUse')
        self.assertEqual('block', self.event('Stop')['decision'])

    def test_unknown_change_range_is_reported_without_forcing_full_file_read(self):
        self.prerequisites()
        (self.project / 'example.sql').write_text('SELECT 1\n')
        response = self.edit_event('PostToolUse')
        self.assertIn('unverified change range', response['hookSpecificOutput']['additionalContext'])
        self.assertEqual({}, self.event('Stop'))

    def test_replaced_longer_log_is_never_imported_and_damage_is_reported(self):
        self.append_user('first')
        self.event('PreCompact')
        self.log.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': 'foreign'}}) + '\n' +
                            json.dumps({'type': 'event_msg', 'payload': {'type': 'user_message', 'message': 'FOREIGN' * 30}}) + '\n')
        self.assertIn('incomplete', self.event('PreCompact')['systemMessage'])
        restored = self.event('PostCompact')['hookSpecificOutput']['additionalContext']
        self.assertNotIn('FOREIGN', restored)
        fresh = self.root / 'damage.jsonl'
        fresh.write_text('{not valid json}\n')
        output = handle({**self.base, 'transcript_path': str(fresh), 'hook_event_name': 'PreCompact'}, 'codex')
        self.assertIn('incomplete', output['systemMessage'])

    def test_checkpoint_memory_cli_cold_restore_and_full_original_retrieval(self):
        self.append_user('초기 중요 지시: 컨트롤 기본 폭 축소 금지')
        checkpoint = self.root / 'checkpoint.md'
        checkpoint.write_text('목표: 조회 수정.\n' + '현재 파일과 검사 한계 유지. ' * 200 + '\n끝의 중요 제약: 빌드 금지', encoding='utf-8')
        common = [sys.executable, '-B', str(ROOT / 'scripts/kh_context.py'), '--cwd', str(self.project),
                  '--session', 's1', '--transcript', str(self.log)]
        def cli(*args):
            result = subprocess.run([*common, *args], capture_output=True, text=True, encoding='utf-8', check=True, timeout=10)
            self.assertFalse(result.stderr)
            return json.loads(result.stdout)
        self.assertEqual('saved', cli('checkpoint', '--file', str(checkpoint))['status'])
        fact = self.root / 'fact.md'
        fact.write_text('사용자가 요청한 프로젝트 선호: 라벨 기본 정렬 유지', encoding='utf-8')
        cli('remember', 'label-style', '--file', str(fact))
        self.append_user('수정 작업 취소. 지금은 검토 결과만 전달해')
        self.event('PreCompact')
        restored = self.event('PostCompact')['hookSpecificOutput']['additionalContext']
        self.assertIn('newer user records=1', restored)
        self.assertIn('preview_truncated=True', restored)
        self.assertIn('수정 작업 취소', restored)
        self.assertIn('라벨 기본 정렬', restored)
        self.assertIn('끝의 중요 제약: 빌드 금지', cli('recall')['checkpoint']['text'])
        self.assertEqual(1, cli('search', '기본 폭')['user_matches'])
        self.assertIn('폭 축소 금지', cli('get', '1')['record']['text'])
        self.log.unlink()
        # Archive survives the source transcript disappearing, with its provenance retained.
        self.assertIn('폭 축소 금지', cli('get', '1')['record']['text'])
        cli('forget', 'label-style')
        self.assertEqual('not_found', cli('memory-get', 'label-style')['status'])

    def test_bundled_windows_and_claude_commands_execute_utf8_json(self):
        event = {**self.base, 'hook_event_name': 'PreToolUse', 'tool_name': 'Write',
                 'tool_input': {'file_path': str(self.project / '한글 example.sql')}}
        for host, name in (('codex', 'codex-hooks.json'), ('claude', 'hooks.json')):
            handler = json.loads((ROOT / 'hooks' / name).read_text())['hooks']['PreToolUse'][0]['hooks'][0]
            if host == 'codex':
                if os.name != 'nt':
                    continue
                args = ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', handler['commandWindows']]
            else:
                args = [handler['command'], *(arg.replace('${CLAUDE_PLUGIN_ROOT}', str(ROOT)) for arg in handler['args'])]
            result = subprocess.run(args, input=json.dumps(event, ensure_ascii=False).encode('utf-8'),
                                    capture_output=True, timeout=15, env={**os.environ, 'PLUGIN_ROOT': str(ROOT)},
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.assertEqual(0, result.returncode, result.stderr.decode('utf-8', errors='replace'))
            output = json.loads(result.stdout.decode('utf-8'))
            self.assertEqual('deny', output['hookSpecificOutput']['permissionDecision'])

    def test_reordered_lines_cannot_be_verified_with_old_body(self):
        path = self.project / 'Sample.cs'
        old = 'class Sample\n{\n    int Run()\n    {\n        int value = 0;\n        value = 2;\n        value = 3;\n        return value;\n    }\n}\n'
        current = old.replace('value = 2;\n        value = 3;', 'value = 3;\n        value = 2;')
        path.write_text(current, encoding='utf-8')
        state = {'files': {}}
        update_files(state, [path], before={str(path): line_hashes(old)})
        update_files(state, [path], old)
        self.assertIsNone(state['files'][str(path)]['readback'])
        update_files(state, [path], current)
        self.assertEqual(state['files'][str(path)]['sha256'], state['files'][str(path)]['readback'])
        self.assertEqual([], state['files'][str(path)]['pending_spans'])

    def test_full_read_completion_is_preserved_when_a_different_method_changes(self):
        path = self.project / 'Sample.cs'
        old = 'class Sample\n{\n    int First()\n    {\n        return 10;\n    }\n\n    // independent method\n\n    int Second()\n    {\n        return 20;\n    }\n}\n'
        first = old.replace('return 10;', 'return 11;')
        path.write_text(first, encoding='utf-8')
        state = {'files': {}}
        update_files(state, [path], before={str(path): line_hashes(old)})
        update_files(state, [path], first)
        second = first.replace('return 20;', 'return 21;')
        path.write_text(second, encoding='utf-8')
        update_files(state, [path], before={str(path): line_hashes(first)})
        lines = second.splitlines()
        position = next(i for i, line in enumerate(lines) if 'return 21;' in line)
        update_files(state, [path], '\n'.join(lines[position-2:position+3]))
        item = state['files'][str(path)]
        self.assertEqual(item['sha256'], item['readback'])
        self.assertEqual([], item['pending_spans'])

    def test_numbered_current_ranges_allow_overlap_reordering_and_intervening_output(self):
        path = self.project / 'example.sql'
        old = '\n'.join(f'-- unchanged {i}' for i in range(10)) + '\n'
        lines = old.splitlines()
        lines[5] = '-- modified current line'
        current = '\n'.join(lines) + '\n'
        path.write_text(current, encoding='utf-8')
        for ranges in (((3, 6), (5, 8)), ((6, 8), (3, 6)), ((3, 6), None, (6, 8))):
            state = {'files': {}}
            update_files(state, [path], before={str(path): line_hashes(old)})
            for selected in ranges:
                returned = 'unrelated other-file output' if selected is None else '\n'.join(
                    f'{i+1}: {lines[i]}' for i in range(*selected))
                update_files(state, [path], returned)
            item = state['files'][str(path)]
            self.assertEqual([], item['pending_spans'])
            self.assertEqual(item['sha256'], item['readback'])

    def test_real_repeated_user_records_are_not_collapsed_as_event_mirrors(self):
        self.append_user('이 기본 정렬을 유지해')
        self.append_user('이 기본 정렬을 유지해')
        state = {'users': []}
        capture(state, self.base, 'codex')
        self.assertEqual(2, len(state['users']))
        self.assertNotEqual(state['users'][0]['source']['byte_offset'], state['users'][1]['source']['byte_offset'])

    def test_desktop_response_items_and_multipart_requests_are_collected(self):
        user = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user', 'content': [
            {'type': 'input_text', 'text': '<environment_context>host data</environment_context>'},
            {'type': 'input_text', 'text': '업그레이드 테스트해줘. 기본 폭 유지.'},
            {'type': 'input_image', 'image_url': 'ignored'}]}}
        self.log.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': 's1'}}) + '\n' +
                            json.dumps(user, ensure_ascii=False) + '\n', encoding='utf-8')
        state = {'users': []}
        capture(state, self.base, 'codex')
        self.assertEqual(1, len(state['users']))
        self.assertEqual('업그레이드 테스트해줘. 기본 폭 유지.', state['users'][0]['text'])
        self.assertEqual('response_item', state['users'][0]['source']['kind'])
        user['payload']['role'] = 'assistant'
        self.assertIsNone(user_text(user, 'codex'))

    def test_dual_transcript_mirrors_are_one_record_but_real_repetitions_remain(self):
        response = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                    'content': [{'type': 'input_text', 'text': '기본 속성을 유지해'}]}}
        event = {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': '기본 속성을 유지해'}}
        for pair in ((response, event), (event, response)):
            self.log.write_text('\n'.join(json.dumps(record, ensure_ascii=False) for record in pair) + '\n', encoding='utf-8')
            state = {'users': []}
            capture(state, self.base, 'codex')
            self.assertEqual(1, len(state['users']))
            self.assertEqual(1, len(state['users'][0]['source_aliases']))
            with self.log.open('a', encoding='utf-8') as stream:
                stream.write('\n'.join(json.dumps(record, ensure_ascii=False) for record in pair) + '\n')
            capture(state, self.base, 'codex')
            self.assertEqual(2, len(state['users']))

    def test_response_mirror_across_capture_boundary_and_existing_archive_migration(self):
        response = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                    'content': [{'type': 'input_text', 'text': '유지해'}]}}
        event = {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': '유지해'}}
        self.log.write_text(json.dumps(response, ensure_ascii=False) + '\n', encoding='utf-8')
        state = {'users': []}
        capture(state, self.base, 'codex')
        original_id = state['users'][0]['seq']
        with self.log.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        capture(state, self.base, 'codex')
        self.assertEqual(1, len(state['users']))
        self.assertEqual(original_id, state['users'][0]['seq'])
        # Version 1 had consumed all bytes but kept only the event representation.
        legacy = {'users': [{**state['users'][0], 'seq': 42, 'source': state['users'][0]['source_aliases'][0]}],
                  'cursor': self.log.stat().st_size}
        legacy['users'][0].pop('source_aliases', None)
        capture(legacy, self.base, 'codex')
        self.assertEqual(1, len(legacy['users']))
        self.assertEqual(42, legacy['users'][0]['seq'])
        self.assertEqual(2, legacy['adapter_version'])

    def test_upgrade_backfills_previously_consumed_desktop_users_without_touching_controls(self):
        response = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                    'content': [{'type': 'input_text', 'text': '이전 저장 작업 취소'}]}}
        self.log.write_text(json.dumps(response, ensure_ascii=False) + '\n', encoding='utf-8')
        state = {'users': [], 'cursor': self.log.stat().st_size,
                 'checkpoint': {'text': 'preserved checkpoint', 'user_seq': 0}, 'paused': True}
        capture(state, self.base, 'codex')
        self.assertEqual('이전 저장 작업 취소', state['users'][0]['text'])
        self.assertTrue(state['paused'])
        self.assertEqual('preserved checkpoint', state['checkpoint']['text'])
        capture(state, self.base, 'codex')
        self.assertEqual(1, len(state['users']))

    def test_assistant_boundary_and_completed_pair_preserve_real_repeated_requests(self):
        response = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                    'content': [{'type': 'input_text', 'text': '기본값 유지'}]}}
        event = {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': '기본값 유지'}}
        assistant = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant',
                     'content': [{'type': 'output_text', 'text': '완료'}]}}
        for records in ((response, assistant, event), (response, event, event)):
            self.log.write_text('\n'.join(json.dumps(record, ensure_ascii=False) for record in records) + '\n', encoding='utf-8')
            state = {'users': []}
            capture(state, self.base, 'codex')
            self.assertEqual(2, len(state['users']))

    def test_backfill_keeps_original_archive_id_across_scan_boundaries(self):
        response = {'type': 'response_item', 'payload': {'type': 'message', 'role': 'user',
                    'content': [{'type': 'input_text', 'text': '보존'}]}}
        event = {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': '보존'}}
        raw1 = (json.dumps(response, ensure_ascii=False) + '\n').encode('utf-8')
        raw2 = (json.dumps(event, ensure_ascii=False) + '\n').encode('utf-8')
        self.log.write_bytes(raw1 + raw2)
        state = {'users': [{'seq': 42, 'text': '보존', 'sha256': hashlib.sha256('보존'.encode()).hexdigest(),
                           'truncated': False, 'source': {'path': str(self.log), 'byte_offset': len(raw1),
                                                         'sha256': hashlib.sha256(raw2).hexdigest()}}],
                 'cursor': len(raw1) + len(raw2)}
        with patch('src.context.transcript.SCAN_LIMIT', len(raw1)):
            capture(state, self.base, 'codex')
        self.assertGreater(state['backlog_bytes'], 0)
        capture(state, self.base, 'codex')
        self.assertEqual([42], [item['seq'] for item in state['users']])
        self.assertEqual(1, len(state['users'][0]['source_aliases']))

    def test_valid_unknown_format_is_reported_instead_of_success_with_zero_users(self):
        self.log.write_text(json.dumps({'type': 'future-user-format', 'body': 'must not silently pass'}) + '\n')
        state = {'users': []}
        capture(state, self.base, 'codex')
        self.assertIn('unverified', state['capture_warning'])
        output = self.event('PreCompact')
        self.assertIn('incomplete', output['systemMessage'])
        self.assertIn('Capture incomplete', self.event('PostCompact')['hookSpecificOutput']['additionalContext'])

    def test_latest_cancellation_survives_when_transcript_capture_has_backlog(self):
        self.prerequisites()
        for i in range(20):
            self.append_user(f'older record {i}')
        with patch('src.context.transcript.SCAN_LIMIT', 200):
            self.event('UserPromptSubmit', prompt='이전 작업 취소. 다음 요청까지 멈춰')
            self.event('UserPromptSubmit', prompt='현재 상태만 알려줘.')
            self.event('PreCompact')
        restored = self.event('PostCompact')['hookSpecificOutput']['additionalContext']
        self.assertIn('이전 작업 취소', restored)
        self.assertIn('Capture incomplete', restored)
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/kh_context.py'), '--cwd', str(self.project),
                                 '--session', 's1', '--transcript', str(self.log), 'recall'],
                                capture_output=True, check=True, timeout=10)
        self.assertIn('이전 작업 취소', result.stdout.decode('utf-8'))

    def test_restore_budget_preserves_incomplete_diagnostic_and_recall_guidance(self):
        users = [{'seq': i, 'sha256': str(i), 'text': '장문 사용자 지시 ' * 150, 'truncated': False,
                  'source': {'path': 'x' * 800, 'byte_offset': i}} for i in range(4)]
        state = {'users': users, 'checkpoint': {'text': '중요한 조건 ' * 1500, 'user_seq': 0},
                 'latest_prompt': {'text': '최신 요청 ' * 200, 'truncated': False},
                 'backlog_bytes': 12345, 'capture_warning': 'incomplete fixture'}
        text = restore(state, [], Store(self.root / 'data', str(self.project)))
        self.assertLessEqual(len(text), 6500)
        self.assertIn('Capture incomplete: 12345', text)
        self.assertIn('recall/search/get/get-prompt', text)
        self.assertIn(str(ROOT / 'scripts/kh_context.py'), text)
        self.assertIn('preview shortened', text)


if __name__ == '__main__':
    unittest.main()
