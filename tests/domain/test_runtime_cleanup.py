import contextlib
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from src.runtime.windows_job import _Win32, run_owned


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / 'scripts/kh_runtime.py'
TREE = '''import json, os, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
pending = Path(sys.argv[1]).with_suffix('.pending')
pending.write_text(json.dumps({'root': os.getpid(), 'child': child.pid}), encoding='utf-8')
pending.replace(sys.argv[1])
while not Path(sys.argv[2]).exists():
    time.sleep(0.02)
sys.exit(int(sys.argv[3]))
'''
NODE_TREE = '''const fs = require('node:fs');
const child = require('node:child_process').spawn(process.execPath, ['-e', 'setInterval(()=>{},1000)'], {stdio:'ignore'});
const [pids, release, exitCode] = process.argv.slice(1);
fs.writeFileSync(pids+'.pending', JSON.stringify({root:process.pid, child:child.pid}));
fs.renameSync(pids+'.pending', pids);
setInterval(()=>{if(fs.existsSync(release))process.exit(Number(exitCode));},20);
'''


class RuntimeInputTests(unittest.TestCase):
    def test_invalid_inputs_are_rejected_before_a_process_starts(self):
        for arguments in ([], [''], ['python', 'bad\0argument']):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                run_owned(arguments)
        for timeout in (0, -1, True, math.nan, math.inf):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                run_owned([sys.executable], timeout=timeout)
        with self.assertRaises(ValueError):
            run_owned([sys.executable], cwd='relative-directory')

    def test_missing_executable_does_not_start_a_shell(self):
        with self.assertRaises(FileNotFoundError):
            run_owned(['kh-nonexistent-executable-735193'], timeout=1)


@unittest.skipUnless(os.name == 'nt', 'Windows Job Objects')
class WindowsRuntimeTests(unittest.TestCase):
    @contextlib.contextmanager
    def tree(self, *, timeout=None, exit_code=0, node=False):
        with tempfile.TemporaryDirectory(prefix='kh-owned-tree-test-') as directory:
            folder = Path(directory)
            pids, release = folder / 'pids.json', folder / 'release'
            command = [sys.executable, '-X', 'utf8', '-B', str(LAUNCHER)]
            if timeout is not None:
                command.extend(['--timeout', str(timeout)])
            child_command = [str(shutil.which('node')), '-e', NODE_TREE] if node else [sys.executable, '-X', 'utf8', '-c', TREE]
            command.extend(['--', *child_command, str(pids), str(release), str(exit_code)])
            wrapper = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, encoding='utf-8')
            native = _Win32()
            native.api.OpenProcess.restype = wintypes.HANDLE
            native.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            handles = []
            try:
                deadline = time.monotonic() + 8
                while not pids.exists() and wrapper.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(pids.exists(), 'Disposable tree did not start: ' + str(wrapper.poll()))
                for pid in json.loads(pids.read_text(encoding='utf-8')).values():
                    handle = native.api.OpenProcess(0x101001, False, pid)
                    self.assertTrue(handle)
                    handles.append(handle)
                yield wrapper, release, native, handles
            finally:
                if wrapper.poll() is None:
                    wrapper.kill()
                wrapper.communicate(timeout=8)
                # Handles were captured while this fixture's tree was live; no name/PID sweep.
                for handle in handles:
                    if native.api.WaitForSingleObject(handle, 3000) != 0:
                        native.api.TerminateProcess(handle, 199)
                        native.api.WaitForSingleObject(handle, 3000)
                    native.close(handle)

    def result(self, wrapper):
        stdout, stderr = wrapper.communicate(timeout=10)
        records = [line.partition('=')[2] for line in stderr.splitlines() if line.startswith('KH_RUNTIME_RESULT=')]
        self.assertEqual(1, len(records), stdout + stderr)
        return json.loads(records[0])

    def assert_tree_stopped(self, native, handles):
        for handle in handles:
            self.assertEqual(0, native.api.WaitForSingleObject(handle, 3000))

    def test_success_closes_a_child_left_behind_by_the_root(self):
        with self.tree() as (wrapper, release, native, handles):
            release.touch()
            result = self.result(wrapper)
            self.assertEqual(0, wrapper.returncode)
            self.assertTrue(result['cleanup_verified'])
            self.assertEqual(0, result['remaining_processes'])
            self.assertGreater(result['peak_job_memory_bytes'], 0)
            self.assert_tree_stopped(native, handles)

    def test_failure_preserves_exit_code_and_closes_descendants(self):
        with self.tree(exit_code=7) as (wrapper, release, native, handles):
            release.touch()
            result = self.result(wrapper)
            self.assertEqual(7, wrapper.returncode)
            self.assertEqual(7, result['exit_code'])
            self.assertTrue(result['cleanup_verified'])
            self.assert_tree_stopped(native, handles)

    @unittest.skipUnless(shutil.which('node'), 'Node.js not installed')
    def test_real_node_child_is_closed_after_root_exit(self):
        with self.tree(node=True) as (wrapper, release, native, handles):
            release.touch()
            result = self.result(wrapper)
            self.assertEqual(0, wrapper.returncode)
            self.assertTrue(result['cleanup_verified'])
            self.assert_tree_stopped(native, handles)

    def test_timeout_closes_the_root_and_its_child(self):
        with self.tree(timeout=3) as (wrapper, release, native, handles):
            result = self.result(wrapper)
            self.assertEqual(124, wrapper.returncode)
            self.assertEqual('timeout', result['reason'])
            self.assertTrue(result['cleanup_verified'])
            self.assert_tree_stopped(native, handles)

    def test_abrupt_supervisor_death_still_closes_the_entire_job(self):
        with self.tree() as (wrapper, release, native, handles):
            wrapper.kill()
            wrapper.communicate(timeout=8)
            self.assert_tree_stopped(native, handles)

    def test_an_unrelated_running_process_is_preserved(self):
        other = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            result = run_owned([sys.executable, '-c', 'pass'], timeout=5)
            self.assertTrue(result.cleanup_verified)
            self.assertIsNone(other.poll())
        finally:
            other.terminate()
            other.wait(timeout=5)

    def test_unicode_space_and_quote_arguments_and_cwd_are_preserved(self):
        with tempfile.TemporaryDirectory(prefix='kh-owned-args-') as directory:
            target = Path(directory) / '공백 결과.json'
            values = ['', 'space value', 'quote"value', '한글', 'ampersand&value']
            script = 'import json,os,sys; from pathlib import Path; Path(sys.argv[1]).write_text(json.dumps([os.getcwd(),sys.argv[2:]]),encoding="utf-8")'
            result = run_owned([sys.executable, '-X', 'utf8', '-c', script, str(target), *values], cwd=directory, timeout=5)
            self.assertTrue(result.cleanup_verified)
            actual = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(Path(directory).resolve(), Path(actual[0]).resolve())
            self.assertEqual(values, actual[1])

    def test_assignment_failure_never_runs_the_suspended_command(self):
        with tempfile.TemporaryDirectory(prefix='kh-owned-assign-') as directory:
            marker = Path(directory) / 'should-not-exist'
            native = _Win32()
            with patch('src.runtime.windows_job._Win32', return_value=native), patch.object(native.api, 'AssignProcessToJobObject', return_value=0):
                with self.assertRaises(OSError):
                    run_owned([sys.executable, '-c', 'from pathlib import Path; import sys; Path(sys.argv[1]).touch()', str(marker)], timeout=5)
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
