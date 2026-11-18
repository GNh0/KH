import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.context.store import Store, session_key
from src.runtime.check_context import SourceBaselines, companion, literal_project_sources
from src.runtime.hooks import CYCLE, ROOT, handle, inspect, update_files
from src.sql.checks import check_sql
from tests.domain.hook_application_fixture import apply_files


CONTROL = '''namespace Widgets {
public class InputBox : TextEdit {
    public InputBox() {
        base.Size = new System.Drawing.Size(150, 24);
        base.Properties.AutoHeight = false;
    }
} }
'''
DESIGNER = '''partial class Screen {
private Widgets.InputBox txtCode;
void InitializeComponent() {
this.txtCode = new Widgets.InputBox();
this.txtCode.Size = new System.Drawing.Size(150, 24);
this.txtCode.Properties.AutoHeight = false;
} }
'''
CODE = 'partial class Screen { void Load() { } }\n'


class HookCheckContextTests(unittest.TestCase):
    def test_companion_preserves_actual_lowercase_designer_identity(self):
        code = self.project / 'Example.cs'
        designer = self.project / 'Example.designer.cs'
        code.write_text('partial class Example {}', encoding='utf-8', newline='')
        designer.write_text('partial class Example { int value; }', encoding='utf-8', newline='')
        state = {}
        baselines = SourceBaselines(self.root / 'snapshots', state)
        baselines.capture(designer)
        inferred = companion(code)
        self.assertEqual(designer.resolve(), inferred)
        self.assertEqual('partial class Example { int value; }', baselines.original(inferred))

    @unittest.skipUnless(os.name == 'nt', 'Legacy aliases refer to the same file only on this filesystem')
    def test_legacy_windows_alias_keeps_the_first_original(self):
        code = self.project / 'Example.cs'
        code.write_text('class Example {}', encoding='utf-8', newline='')
        state = {}
        baselines = SourceBaselines(self.root / 'snapshots', state)
        baselines.capture(code)
        key = next(iter(baselines.records))
        baselines.records[str(code).upper()] = baselines.records.pop(key)
        code.write_text('class Example { int changed; }', encoding='utf-8', newline='')
        baselines.capture(code)
        self.assertEqual('class Example {}', baselines.original(code))
        self.assertEqual(1, len(baselines.records))

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.project = self.root / 'project'
        self.project.mkdir()
        self.env = patch.dict(os.environ, {'PLUGIN_DATA': str(self.root / 'data'), 'KH_HOOKS_MODE': 'enforce'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.log = self.root / 'native.jsonl'
        self.log.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': 's1'}}) + '\n', encoding='utf-8', newline='')
        self.scope = {'cwd': str(self.project), 'session_id': 's1', 'transcript_path': str(self.log)}
        self.store = Store(self.root / 'data/context-v1', str(self.project))
        self.key = session_key(self.scope, 'codex')

    def event(self, name, **values):
        return handle({**self.scope, 'hook_event_name': name, **values}, 'codex')

    def read_skills(self, domain='csharp-designer-style-harness'):
        body = '\n'.join((ROOT / 'skills' / path).read_text(encoding='utf-8-sig')
                         for path in (CYCLE, domain + '/SKILL.md'))
        self.event('PostToolUse', tool_name='exec_command', tool_response={'output': body})
        if domain == 'sql-formatting':
            apply_files(self.scope, 'codex', ['sql-query'], [self.project / 'Save.sql'])
        else:
            apply_files(self.scope, 'codex', ['csharp-code', 'csharp-designer'],
                        [self.project / 'Screen.cs', self.project / 'Screen.Designer.cs'])

    def write_event(self, name, path):
        return self.event(name, tool_name='Write', tool_input={'file_path': str(path)})

    def state(self):
        with self.store.connect() as connection:
            return self.store.load(connection, self.key)

    def fixture(self):
        library = self.root / 'library'
        library.mkdir()
        control = library / 'InputBox.cs'
        control.write_text(CONTROL, encoding='utf-8', newline='')
        (library / 'Widgets.csproj').write_text('<Project><ItemGroup><Compile Include="InputBox.cs" /></ItemGroup></Project>', encoding='utf-8', newline='')
        project = self.project / 'Screen.csproj'
        project.write_text('<Project><ItemGroup><Compile Include="Screen.cs" /><Compile Include="Screen.Designer.cs" /><ProjectReference Include="../library/Widgets.csproj" /></ItemGroup></Project>', encoding='utf-8', newline='')
        code = self.project / 'Screen.cs'
        designer = self.project / 'Screen.Designer.cs'
        code.write_text(CODE, encoding='utf-8', newline='')
        designer.write_text(DESIGNER, encoding='utf-8', newline='')
        return code, designer, control, project

    def test_real_hook_original_companion_and_literal_control_source(self):
        code, designer, control, _project = self.fixture()
        self.read_skills()
        self.assertEqual({}, self.write_event('PreToolUse', designer))
        designer.write_text(DESIGNER.replace('Size(150, 24)', 'Size(110, 24)'), encoding='utf-8', newline='')
        response = self.write_event('PostToolUse', designer)
        item = self.state()['files'][str(designer)]
        self.assertIn('user_control_size_shrink', item['check']['errors'])
        self.assertEqual(str(code), item['check']['automatic_context']['companion'])
        self.assertTrue(item['check']['automatic_context']['original'])
        self.assertEqual([str(control)], item['check']['automatic_context']['control_sources'])
        self.assertIn('user_control_size_shrink', response['hookSpecificOutput']['additionalContext'])
        self.assertFalse(list(self.project.glob('*.source')))
        self.assertNotIn(CONTROL, json.dumps(self.state()))
        self.assertNotIn(DESIGNER, json.dumps(self.state()))

    def test_baseline_is_immutable_across_multiple_edits_and_companion_edits(self):
        code, designer, _control, _project = self.fixture()
        self.read_skills()
        self.write_event('PreToolUse', code)
        code.write_text(CODE + '// first edit\n', encoding='utf-8', newline='')
        self.write_event('PostToolUse', code)
        self.write_event('PreToolUse', designer)
        designer.write_text(DESIGNER + '// second edit\n', encoding='utf-8', newline='')
        self.write_event('PostToolUse', designer)
        state = self.state()
        baselines = SourceBaselines(self.store.path.parent / 'checks' / self.key, state)
        self.assertEqual(CODE, baselines.original(code))
        self.assertEqual(DESIGNER, baselines.original(designer))

    def test_existing_formats_suppressed_but_new_warning_survives_readback_and_repair(self):
        code, _designer, _control, _project = self.fixture()
        before = 'class Screen { string Format(int n) { return n.ToString("N0"); } }\n'
        code.write_text(before, encoding='utf-8', newline='')
        self.read_skills()
        self.write_event('PreToolUse', code)
        after = before.replace('N0', 'N2')
        code.write_text(after, encoding='utf-8', newline='')
        self.write_event('PostToolUse', code)
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(code)}, tool_response=after)
        check = self.state()['files'][str(code)]['check']
        self.assertEqual('review_required', check['status'])
        self.assertIn('numeric_format_preference', check['warnings'])
        self.assertEqual('block', self.event('Stop')['decision'])
        self.assertNotIn('decision', self.event('Stop', stop_hook_active=True))
        self.write_event('PreToolUse', code)
        fixed = after.replace('N2', '#,##0.##')
        code.write_text(fixed, encoding='utf-8', newline='')
        self.write_event('PostToolUse', code)
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(code)}, tool_response=fixed)
        self.assertEqual({}, self.event('Stop'))
        self.assertFalse((self.store.path.parent / 'checks' / self.key).exists())
        self.assertEqual({}, self.state()['check_baselines'])
        self.write_event('PreToolUse', code)
        state = self.state()
        self.assertEqual({}, state['files'])
        self.assertEqual(fixed, SourceBaselines(self.store.path.parent / 'checks' / self.key, state).original(code))

    def test_sql_value_fallback_survives_readback_until_the_unauthorized_addition_is_removed(self):
        sql = self.project / 'Save.sql'
        before = 'SELECT A.LIMIT_VALUE, ISNULL(A.QTY, 0) AS QTY FROM INPUT_ROWS A;'
        sql.write_text(before, encoding='utf-8', newline='')
        self.read_skills('sql-formatting')
        self.write_event('PreToolUse', sql)
        added = before.replace('SELECT A.LIMIT_VALUE', 'SELECT ISNULL(A.LIMIT_VALUE, 0)')
        sql.write_text(added, encoding='utf-8', newline='')
        response = self.write_event('PostToolUse', sql)
        self.assertIn('value_fallback_review', response['hookSpecificOutput']['additionalContext'])
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(sql)}, tool_response=added)
        check = self.state()['files'][str(sql)]['check']
        self.assertEqual('review_required', check['status'])
        self.assertEqual(1, check['warning_counts']['value_fallback_review'])
        self.assertEqual('block', self.event('Stop')['decision'])
        self.write_event('PreToolUse', sql)
        sql.write_text(before, encoding='utf-8', newline='')
        self.write_event('PostToolUse', sql)
        self.event('PostToolUse', tool_name='Read', tool_input={'file_path': str(sql)}, tool_response=before)
        self.assertEqual({}, self.event('Stop'))
        self.assertFalse((self.store.path.parent / 'checks' / self.key).exists())

    def test_new_file_has_empty_original_but_unknown_original_is_not_current_source(self):
        state = {}
        baselines = SourceBaselines(self.root / 'snapshots', state)
        new = self.project / 'New.cs'
        baselines.capture(new)
        new.write_text(CODE, encoding='utf-8', newline='')
        self.assertEqual('', baselines.original(new))
        self.assertIsNone(baselines.original(self.project / 'Unknown.cs'))

    def test_cleanup_preflights_all_files_and_preserves_other_session(self):
        state = {}
        directory = self.root / 'snapshots' / 's1'
        baselines = SourceBaselines(directory, state)
        code = self.project / 'Screen.cs'
        code.write_text(CODE, encoding='utf-8', newline='')
        baselines.capture(code)
        owned = next(directory.glob('*.source'))
        unknown = directory / 'unowned.txt'
        unknown.write_text('preserve', encoding='utf-8', newline='')
        other = directory.parent / 's2'
        other.mkdir()
        (other / 'keep').write_text('needed', encoding='utf-8', newline='')
        with self.assertRaises(ValueError):
            baselines.cleanup()
        self.assertTrue(owned.exists())
        unknown.unlink()
        baselines.cleanup()
        self.assertTrue((other / 'keep').exists())

    def test_tampered_snapshot_is_never_used_or_deleted(self):
        state = {}
        baselines = SourceBaselines(self.root / 'snapshots', state)
        code = self.project / 'Screen.cs'
        code.write_text(CODE, encoding='utf-8', newline='')
        baselines.capture(code)
        target = next(baselines.directory.glob('*.source'))
        target.write_text('changed', encoding='utf-8', newline='')
        with self.assertRaises(ValueError):
            baselines.original(code)
        with self.assertRaises(ValueError):
            baselines.cleanup()
        self.assertTrue(target.exists())

    def test_identical_crlf_sources_share_snapshot_without_normalizing_newlines(self):
        state = {}
        baselines = SourceBaselines(self.root / 'snapshots', state)
        first = self.project / 'First.cs'
        second = self.project / 'Second.cs'
        raw = b'class Example { }\r\n'
        first.write_bytes(raw)
        second.write_bytes(raw)
        baselines.capture(first)
        baselines.capture(second)
        self.assertEqual(raw.decode(), baselines.original(first))
        self.assertEqual(raw.decode(), baselines.original(second))
        self.assertEqual(1, len(list(baselines.directory.glob('*.source'))))
        baselines.cleanup()
        self.assertFalse(baselines.directory.exists())

    def test_context_dependencies_invalidate_unchanged_candidate(self):
        code, designer, control, project = self.fixture()
        state = {}
        update_files(state, [designer])
        self.assertNotIn('user_control_size_shrink', state['files'][str(designer)]['check']['errors'])
        control.write_text(CONTROL.replace('Size(150, 24)', 'Size(180, 24)'), encoding='utf-8', newline='')
        self.assertTrue(update_files(state, [designer]))
        self.assertIn('user_control_size_shrink', state['files'][str(designer)]['check']['errors'])
        code.write_text(CODE + '// peer changed\n', encoding='utf-8', newline='')
        self.assertTrue(update_files(state, [designer]))
        project.write_text('<Project />', encoding='utf-8', newline='')
        self.assertTrue(update_files(state, [designer]))
        self.assertEqual(0, state['files'][str(designer)]['check']['automatic_context']['control_source_count'])

    def test_previously_missing_dependency_appearing_is_rechecked(self):
        _code, designer, control, _project = self.fixture()
        control.unlink()
        state = {}
        update_files(state, [designer])
        self.assertEqual(0, state['files'][str(designer)]['check']['automatic_context']['control_source_count'])
        control.write_text(CONTROL, encoding='utf-8', newline='')
        self.assertTrue(update_files(state, [designer]))
        self.assertEqual(1, state['files'][str(designer)]['check']['automatic_context']['control_source_count'])

    def test_new_project_ambiguity_invalidates_cached_context(self):
        _code, designer, _control, _project = self.fixture()
        state = {}
        update_files(state, [designer])
        self.assertEqual(1, state['files'][str(designer)]['check']['automatic_context']['control_source_count'])
        extra = self.project / 'Other.csproj'
        extra.write_text('<Project />', encoding='utf-8', newline='')
        self.assertTrue(update_files(state, [designer]))
        self.assertEqual(0, state['files'][str(designer)]['check']['automatic_context']['control_source_count'])
        extra.unlink()
        self.assertTrue(update_files(state, [designer]))
        self.assertEqual(1, state['files'][str(designer)]['check']['automatic_context']['control_source_count'])

    def test_invalid_project_and_unmatched_control_can_recover_without_target_edit(self):
        _code, designer, control, project = self.fixture()
        project_body = project.read_text(encoding='utf-8')
        project.write_text('<Project', encoding='utf-8', newline='')
        state = {}
        update_files(state, [designer])
        self.assertEqual(0, state['files'][str(designer)]['check']['automatic_context']['control_source_count'])
        project.write_text(project_body, encoding='utf-8', newline='')
        self.assertTrue(update_files(state, [designer]))
        self.assertEqual(1, state['files'][str(designer)]['check']['automatic_context']['control_source_count'])
        control.write_text(CONTROL.replace('Widgets', 'Other'), encoding='utf-8', newline='')
        self.assertTrue(update_files(state, [designer]))
        self.assertEqual(0, state['files'][str(designer)]['check']['automatic_context']['control_source_count'])
        control.write_text(CONTROL, encoding='utf-8', newline='')
        self.assertTrue(update_files(state, [designer]))
        self.assertEqual(1, state['files'][str(designer)]['check']['automatic_context']['control_source_count'])

    def test_failed_check_is_retried_without_another_source_change(self):
        _code, designer, _control, _project = self.fixture()
        state = {}
        with patch('src.runtime.hooks.inspect', side_effect=ValueError('injected read failure')):
            update_files(state, [designer])
        self.assertIn('error', state['files'][str(designer)])
        self.assertTrue(update_files(state, [designer]))
        self.assertNotIn('error', state['files'][str(designer)])
        self.assertIn('check', state['files'][str(designer)])

    def test_conditional_or_ambiguous_source_is_not_inferred(self):
        code, designer, _control, project = self.fixture()
        project.write_text('<Project><ItemGroup Condition="\'$(Configuration)\' == \'Debug\'"><ProjectReference Include="../library/Widgets.csproj" /></ItemGroup></Project>', encoding='utf-8', newline='')
        sources, meta = literal_project_sources(code, [CODE, DESIGNER])
        self.assertEqual([], sources)
        self.assertTrue(meta['unverified'])
        (self.project / 'Second.csproj').write_text('<Project />', encoding='utf-8', newline='')
        sources, meta = literal_project_sources(designer, [DESIGNER])
        self.assertEqual([], sources)
        self.assertIsNone(meta['project'])

    def test_transformed_compile_membership_is_not_assumed(self):
        code, _designer, _control, _project = self.fixture()
        library = self.root / 'library' / 'Widgets.csproj'
        library.write_text('<Project><ItemGroup><Compile Include="InputBox.cs" /><Compile Remove="InputBox.cs" /></ItemGroup></Project>', encoding='utf-8', newline='')
        sources, meta = literal_project_sources(code, [CODE, DESIGNER])
        self.assertEqual([], sources)
        self.assertTrue(meta['unverified'])

    def test_compaction_and_interruption_retain_unfinished_baselines(self):
        code, _designer, _control, _project = self.fixture()
        self.read_skills()
        self.write_event('PreToolUse', code)
        self.event('PreCompact')
        self.event('Interrupt')
        self.assertEqual({}, self.event('Stop'))
        state = self.state()
        self.assertEqual(CODE, SourceBaselines(self.store.path.parent / 'checks' / self.key, state).original(code))

    def test_sql_edit_context_does_not_freeze_requested_behavior(self):
        self.assertFalse(check_sql('SELECT 2', original='SELECT 1').success)
        edited = inspect(self.project / 'query.sql', 'SELECT 2', original='SELECT 1')
        self.assertEqual([], edited['errors'])
        bad = inspect(self.project / 'query.sql', "SELECT 'unterminated", original='SELECT 1')
        self.assertTrue(bad['errors'])
        style = inspect(self.project / 'query.sql', 'SELECT 1 WHERE EXISTS (SELECT 1)', original='SELECT 1')
        self.assertTrue(style['warnings'])
        new = inspect(self.project / 'new.sql', 'SELECT A.ID FROM FIRST A LEFT JOIN SECOND B ON A.ID = B.ID', original='')
        self.assertIn('outer_join_keyword_required', new['warnings'])

    def test_recall_exposes_omitted_check_results_without_source_snapshots(self):
        code, _designer, _control, _project = self.fixture()
        self.read_skills()
        self.write_event('PreToolUse', code)
        code.write_text(CODE + '// edit\n', encoding='utf-8', newline='')
        self.write_event('PostToolUse', code)
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/kh_context.py'),
                                 '--cwd', str(self.project), '--session', 's1', '--transcript', str(self.log),
                                 '--host', 'codex', 'recall'], capture_output=True, text=True,
                                encoding='utf-8', check=True, timeout=10)
        item = json.loads(result.stdout)['files'][str(code)]
        self.assertTrue(item['check']['automatic_context']['original'])
        self.assertIn('sources', item['check_context'])
        self.assertNotIn(CONTROL, result.stdout)


if __name__ == '__main__':
    unittest.main()
