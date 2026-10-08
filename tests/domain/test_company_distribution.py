import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from src.csharp.checks import check_csharp
from src.csharp.designer import check_designer
from src.sql.checks import check_sql

ROOT = Path(__file__).resolve().parents[2]
STYLE_PATH = ROOT / 'company/plugins/company-dev/scripts/company_style.py'
SPEC = importlib.util.spec_from_file_location('company_style', STYLE_PATH)
assert SPEC is not None and SPEC.loader is not None
STYLE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STYLE)


class CompanyStyleTests(unittest.TestCase):
    def test_initialization_preserves_employee_edits_on_update(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / 'employee'
            first = STYLE.initialize(directory)
            self.assertEqual(4, len(first['created']))
            personal = directory / 'csharp.md'
            personal.write_text('Prefer expression-bodied members and N0 formats.', encoding='utf-8')
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            second = STYLE.initialize(directory)
            self.assertEqual([], second['created'])
            self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})

    def test_topic_read_is_scoped_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / 'absent'
            self.assertFalse(STYLE.read_style(directory, 'sql')['exists'])
            self.assertFalse(directory.exists())
            directory.mkdir()
            (directory / 'sql.md').write_text('Lowercase SQL keywords.', encoding='utf-8')
            (directory / 'csharp.md').write_bytes(b'\xff\xfeinvalid UTF-8')
            result = STYLE.read_style(directory, 'sql')
            self.assertEqual('Lowercase SQL keywords.', result['text'])
            self.assertFalse(result['automatic_style_enforcement'])

    def test_absolute_environment_directory_and_codex_home_are_respected(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'COMPANY_DEV_STYLE_HOME': folder, 'CODEX_HOME': 'ignored'}, clear=True):
                self.assertEqual(Path(folder).resolve(), STYLE.style_directory())
            with patch.dict(os.environ, {'CODEX_HOME': folder}, clear=True):
                self.assertEqual(Path(folder).resolve() / 'company-dev-style', STYLE.style_directory())
            with self.assertRaises(ValueError):
                STYLE.style_directory('relative-source-folder')
            with self.assertRaises(ValueError):
                STYLE.style_directory(str(STYLE_PATH.parents[1] / 'personal'))

    def test_topic_cannot_traverse_to_another_file(self):
        with self.assertRaises(ValueError):
            STYLE.read_style(Path(tempfile.gettempdir()), '../secret')


class CompanyCheckTests(unittest.TestCase):
    def test_employee_csharp_preferences_do_not_trigger_kh_rules(self):
        source = 'class Screen { private string Show(int x) => x.ToString("N0"); void Run() { if (ok) return; var data = rows.AsEnumerable().Where(x => x > 0).ToList(); } }'
        kh = check_csharp(source)
        neutral = check_csharp(source, check_style=False)
        codes = {i.code for i in kh.issues}
        self.assertIn('control_body_braces', codes)
        self.assertIn('linq_preference', codes)
        self.assertIn('expression_body_preference', codes)
        self.assertIn('numeric_format_preference', codes)
        self.assertFalse({'control_body_braces', 'linq_preference', 'expression_body_preference', 'numeric_format_preference'} & {i.code for i in neutral.issues})
        self.assertFalse(neutral.metadata['project_style_verified'])

    def test_neutral_designer_keeps_source_integrity_findings(self):
        source = 'private DevExpress.XtraEditors.DateEdit dateStart; private DevExpress.XtraGrid.Columns.GridColumn colQty; void InitializeComponent() { this.dateStart = new DevExpress.XtraEditors.DateEdit(); this.dateStart.Name = "differentName"; this.colQty = new DevExpress.XtraGrid.Columns.GridColumn(); this.colQty.ColumnEdit = this.missingRepository; this.colQty.DisplayFormat.FormatString = "N0"; }'
        result = check_designer(source, check_style=False)
        codes = {i.code for i in result.issues}
        self.assertIn('control_name_mismatch', codes)
        self.assertIn('repository_not_declared', codes)
        self.assertFalse({'header_appearance_default', 'cell_use_font_default', 'control_name_preference', 'numeric_format_preference'} & codes)

    def test_actual_user_control_override_is_reviewed_without_universal_size_ban(self):
        control = 'class MyLookup : DevExpress.XtraEditors.LookUpEdit { public MyLookup() { this.Size = new System.Drawing.Size(150, 24); } }'
        source = 'private MyLookup lookup; void InitializeComponent() { this.lookup = new MyLookup(); this.lookup.Size = new System.Drawing.Size(100, 24); }'
        neutral = check_designer(source, control_sources=[control], check_style=False)
        self.assertIn('user_control_default_override', {i.code for i in neutral.issues})
        self.assertNotIn('user_control_size_shrink', {i.code for i in neutral.issues})
        self.assertIn('user_control_size_shrink', {i.code for i in check_designer(source, control_sources=[control]).issues})

    def test_explicit_column_contract_is_still_checked(self):
        source = 'private DevExpress.XtraGrid.Columns.GridColumn quantity; void InitializeComponent() { this.quantity = new DevExpress.XtraGrid.Columns.GridColumn(); this.quantity.OptionsColumn.AllowEdit = false; }'
        result = check_designer(source, column_edit_modes={'quantity': 'read_only'}, check_style=False)
        self.assertIn('column_edit_mode_mismatch', {i.code for i in result.issues})

    def test_sql_neutral_mode_keeps_changed_query_failure(self):
        source = 'SELECT A.ID FROM Items A WHERE A.QTY > 0'
        candidate = 'SELECT A.ID FROM Items A WHERE A.QTY >= 0'
        result = check_sql(candidate, original=source, check_style=False, check_preferences=False)
        self.assertEqual('failed', result.status)
        temporary = check_sql('SELECT 1 AS value INTO #stage', check_style=False, check_preferences=False)
        self.assertNotIn('intermediate_table_preference', {i.code for i in temporary.issues})
        self.assertIn('intermediate_table_preference', {i.code for i in check_sql('SELECT 1 AS value INTO #stage').issues})

    def test_project_cli_cannot_use_kh_formatter(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'query.sql'
            source.write_text('SELECT 1', encoding='utf-8')
            before = source.read_bytes()
            output = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/kh_check.py'),
                                     'sql', str(source), '--style-policy', 'project', '--normalize-layout'],
                                    cwd=folder, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(1, output.returncode)
            self.assertEqual('input_error', json.loads(output.stdout)['issues'][0]['code'])
            self.assertEqual(before, source.read_bytes())


class CompanyBundleTests(unittest.TestCase):
    def test_zip_is_local_and_excludes_private_and_untracked_material(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'company.zip'
            build = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/build_company_bundle.py'), '--output', str(archive)],
                                   cwd=folder, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            with zipfile.ZipFile(archive) as bundle:
                names = bundle.namelist()
                marketplace = json.loads(bundle.read('.agents/plugins/marketplace.json'))
                self.assertEqual('local', marketplace['plugins'][0]['source']['source'])
                self.assertEqual('./plugins/company-dev', marketplace['plugins'][0]['source']['path'])
                self.assertEqual(9, len([n for n in names if n.endswith('/SKILL.md')]))
                exporter_root = 'plugins/company-dev/skills/pb-to-csharp-migration-harness/scripts/'
                for name in ('export_pbl.py', 'pbl-exporter/Export-PBL.ps1',
                             'pbl-exporter/PblExporter.exe', 'pbl-exporter/bundle.json'):
                    self.assertIn(exporter_root + name, names)
                self.assertFalse(any('kh-maintenance' in n or '.git/' in n or 'temp_output' in n or '__pycache__' in n or 'docs/kh' in n for n in names))
                self.assertTrue(all(b'GNh0' not in bundle.read(n) and b'KONEIT' not in bundle.read(n) for n in names))
                bundle.extractall(Path(folder) / 'installed-source')
            plugin = Path(folder) / 'installed-source/plugins/company-dev'
            sample = Path(folder) / 'sample.cs'
            sample.write_text('class Screen { string Show(int n) => n.ToString("N0"); }', encoding='utf-8')
            runtime = subprocess.run([sys.executable, '-B', str(plugin / 'scripts/company_check.py'), 'csharp', str(sample)],
                                     cwd=folder, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, runtime.returncode, runtime.stdout + runtime.stderr)
            result = json.loads(runtime.stdout)
            self.assertEqual('project', result['style_policy'])
            self.assertNotIn('expression_body_preference', {i['code'] for i in result['issues']})
            launcher = plugin / 'skills/pb-to-csharp-migration-harness/scripts/export_pbl.py'
            extraction = subprocess.run([sys.executable, '-B', str(launcher), 'probe', '--pbl', str(Path(folder) / 'missing.pbl')],
                                         cwd=folder, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, extraction.returncode, extraction.stdout + extraction.stderr)
            capability = json.loads(extraction.stdout)
            self.assertEqual('pbl_not_found', capability['reason_code'])
            self.assertTrue(Path(capability['tool_script']).resolve().is_relative_to(plugin.resolve()))
