import tempfile
import unittest
from pathlib import Path
from src.common.files import read_file, verify_unchanged, write_output
from src.common.output import compact_output, redact


class CommonTests(unittest.TestCase):
    def test_changed_user_file_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'source.txt'
            path.write_text('before')
            snapshot = read_file(path)
            path.write_text('user change')
            with self.assertRaises(RuntimeError):
                verify_unchanged(snapshot)
            with self.assertRaises(FileExistsError):
                write_output(path, b'candidate', expected_sha256=snapshot.sha256)
            self.assertEqual(path.read_text(), 'user change')

    def test_new_output_and_explicit_current_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'result.txt'
            write_output(path, b'one')
            current = read_file(path)
            write_output(path, b'two', expected_sha256=current.sha256)
            self.assertEqual(path.read_bytes(), b'two')

    def test_failure_exit_and_stderr_survive_truncation(self):
        result = compact_output('noise\n'*2000, 'fatal: actual failure', 17, limit=300)
        self.assertEqual(result.exit_code, 17)
        self.assertIn('actual failure', result.stderr)
        self.assertIn('truncated', result.stdout)

    def test_secret_assignment_is_masked(self):
        self.assertNotIn('fictional-secret', redact('PWD=fictional-secret; Server=example'))


if __name__ == '__main__':
    unittest.main()
