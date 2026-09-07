import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CliTests(unittest.TestCase):
    def test_bom_crlf_input_from_an_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original, candidate = root/'original.sql', root/'candidate.sql'
            original.write_bytes('\ufeffSELECT A.ID\r\nFROM ORDERS A\r\nWHERE A.NOTE = N\'한글\';\r\n'.encode('utf-8'))
            candidate.write_text("SELECT A.ID\nFROM ORDERS A\nWHERE A.NOTE = N'한글';\n", encoding='utf-8')
            before = original.read_bytes()
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'sql', str(original), str(candidate)], cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual('passed', json.loads(result.stdout)['status'])
            self.assertEqual(before, original.read_bytes())
            self.assertEqual({'original.sql', 'candidate.sql'}, {p.name for p in root.iterdir()})

    def test_changed_sql_returns_failure_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original, candidate = root/'original.sql', root/'candidate.sql'
            original.write_text('SELECT 1')
            candidate.write_text('SELECT 2')
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/kh_check.py'), 'sql', str(original), str(candidate)], cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(1, result.returncode)
            self.assertIn('sql_meaning_tokens_changed', [i['code'] for i in json.loads(result.stdout)['issues']])

    def test_empty_sql_is_incomplete(self):
        from src.sql.checks import check_sql
        self.assertEqual('incomplete', check_sql('-- comment only').status)


if __name__ == '__main__':
    unittest.main()
