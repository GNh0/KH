"""Run one owned command tree in a Windows kill-on-close Job Object."""
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import math
import os
from pathlib import Path
import shutil
import subprocess
import time


class _Limits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', wintypes.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                ('active_limit', wintypes.DWORD), ('affinity', ctypes.c_size_t),
                ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]


class _Io(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ('reads', 'writes', 'other', 'read_bytes', 'write_bytes', 'other_bytes')]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [('basic', _Limits), ('io', _Io), ('process_memory', ctypes.c_size_t),
                ('job_memory', ctypes.c_size_t), ('peak_process_memory', ctypes.c_size_t),
                ('peak_job_memory', ctypes.c_size_t)]


class _Accounting(ctypes.Structure):
    _fields_ = [('user_time', ctypes.c_longlong), ('kernel_time', ctypes.c_longlong),
                ('period_user_time', ctypes.c_longlong), ('period_kernel_time', ctypes.c_longlong),
                ('faults', wintypes.DWORD), ('total_processes', wintypes.DWORD),
                ('active_processes', wintypes.DWORD), ('terminated_processes', wintypes.DWORD)]


class _Startup(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('reserved', wintypes.LPWSTR), ('desktop', wintypes.LPWSTR),
                ('title', wintypes.LPWSTR), ('x', wintypes.DWORD), ('y', wintypes.DWORD),
                ('width', wintypes.DWORD), ('height', wintypes.DWORD), ('x_chars', wintypes.DWORD),
                ('y_chars', wintypes.DWORD), ('fill', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('show', wintypes.WORD), ('reserved_size', wintypes.WORD),
                ('reserved_bytes', ctypes.POINTER(wintypes.BYTE)), ('stdin', wintypes.HANDLE),
                ('stdout', wintypes.HANDLE), ('stderr', wintypes.HANDLE)]


class _Process(ctypes.Structure):
    _fields_ = [('process', wintypes.HANDLE), ('thread', wintypes.HANDLE),
                ('pid', wintypes.DWORD), ('tid', wintypes.DWORD)]


class _Win32:
    def __init__(self):
        if os.name != 'nt':
            raise OSError('The owned-command helper requires Windows; use native host process sessions elsewhere.')
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': (wintypes.HANDLE, [ctypes.c_void_p, wintypes.LPCWSTR]),
            'SetInformationJobObject': (wintypes.BOOL, [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]),
            'QueryInformationJobObject': (wintypes.BOOL, [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]),
            'AssignProcessToJobObject': (wintypes.BOOL, [wintypes.HANDLE, wintypes.HANDLE]),
            'TerminateJobObject': (wintypes.BOOL, [wintypes.HANDLE, wintypes.UINT]),
            'TerminateProcess': (wintypes.BOOL, [wintypes.HANDLE, wintypes.UINT]),
            'GetCurrentProcess': (wintypes.HANDLE, []),
            'GetStdHandle': (wintypes.HANDLE, [wintypes.DWORD]),
            'DuplicateHandle': (wintypes.BOOL, [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
                                            ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]),
            'CreateProcessW': (wintypes.BOOL, [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                                             ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p,
                                             wintypes.LPCWSTR, ctypes.POINTER(_Startup), ctypes.POINTER(_Process)]),
            'ResumeThread': (wintypes.DWORD, [wintypes.HANDLE]),
            'WaitForSingleObject': (wintypes.DWORD, [wintypes.HANDLE, wintypes.DWORD]),
            'GetExitCodeProcess': (wintypes.BOOL, [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]),
            'CloseHandle': (wintypes.BOOL, [wintypes.HANDLE]),
        }
        for name, (result, arguments) in signatures.items():
            function = getattr(self.api, name)
            function.restype = result
            function.argtypes = arguments

    def require(self, succeeded) -> None:
        if not succeeded:
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self, handle) -> None:
        if handle:
            self.require(self.api.CloseHandle(handle))

    def accounting(self, job) -> _Accounting:
        result = _Accounting()
        self.require(self.api.QueryInformationJobObject(job, 1, ctypes.byref(result), ctypes.sizeof(result), None))
        return result

    def duplicate_stdio(self, identifier: int) -> int:
        source = self.api.GetStdHandle(identifier)
        if not source or source == ctypes.c_void_p(-1).value:
            raise OSError('A standard stream handle is unavailable; invoke from a host terminal session.')
        duplicate = wintypes.HANDLE()
        current = self.api.GetCurrentProcess()
        self.require(self.api.DuplicateHandle(current, source, current, ctypes.byref(duplicate), 0, True, 2))
        if duplicate.value is None:
            raise OSError('Could not duplicate a standard stream handle.')
        return duplicate.value


@dataclass(frozen=True)
class RunResult:
    root_pid: int
    exit_code: int
    reason: str
    cleanup_verified: bool
    remaining_processes: int
    active_before_cleanup: int
    elapsed_seconds: float
    job_cpu_seconds: float
    peak_job_memory_bytes: int


def run_owned(arguments: list[str], *, cwd: str | None = None, timeout: float | None = None) -> RunResult:
    """No existing PID/name is accepted; only the newly created tree is contained."""
    if not arguments or not arguments[0] or any(not isinstance(value, str) or '\0' in value for value in arguments):
        raise ValueError('Supply an executable and valid argument strings.')
    if timeout is not None and (isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0):
        raise ValueError('timeout must be a finite positive number of seconds, or omitted.')
    if cwd is not None and (not Path(cwd).is_absolute() or not Path(cwd).is_dir()):
        raise ValueError('cwd must name an existing absolute directory.')
    executable = shutil.which(arguments[0])
    if executable is None:
        raise FileNotFoundError(arguments[0])
    if Path(executable).suffix.lower() in {'.cmd', '.bat', '.ps1'}:
        raise ValueError('Invoke a script through its explicit interpreter, such as node.exe or pwsh.exe.')
    native = _Win32()
    job = native.api.CreateJobObjectW(None, None)
    native.require(job)
    process = _Process()
    duplicates: list[int] = []
    started = time.monotonic()
    assigned = False
    reason, exit_code = 'exited', 125
    try:
        limits = _ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway flags.
        native.require(native.api.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        for identifier in (-10, -11, -12):
            duplicates.append(native.duplicate_stdio(identifier))
        startup = _Startup()
        startup.cb = ctypes.sizeof(startup)
        startup.flags = 0x101  # STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW.
        startup.show = 0
        startup.stdin, startup.stdout, startup.stderr = duplicates
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline([executable, *arguments[1:]]))
        native.require(native.api.CreateProcessW(executable, command, None, None, True,
                       0x08000004, None, cwd, ctypes.byref(startup), ctypes.byref(process)))
        # Suspend before assigning: the command cannot spawn an uncontained child first.
        native.require(native.api.AssignProcessToJobObject(job, process.process))
        assigned = True
        if native.api.ResumeThread(process.thread) == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        for handle in duplicates:
            native.close(handle)
        duplicates.clear()
        native.close(process.thread)
        process.thread = None
        try:
            while True:
                state = native.api.WaitForSingleObject(process.process, 100)
                if state == 0:
                    result_code = wintypes.DWORD()
                    native.require(native.api.GetExitCodeProcess(process.process, ctypes.byref(result_code)))
                    exit_code = result_code.value
                    break
                if state != 258:
                    raise ctypes.WinError(ctypes.get_last_error())
                if timeout is not None and time.monotonic() - started >= timeout:
                    reason, exit_code = 'timeout', 124
                    break
        except KeyboardInterrupt:
            reason, exit_code = 'interrupted', 130
        before = native.accounting(job)
        if before.active_processes:
            native.require(native.api.TerminateJobObject(job, exit_code))
        deadline = time.monotonic() + 5
        after = native.accounting(job)
        while after.active_processes and time.monotonic() < deadline:
            time.sleep(0.05)
            after = native.accounting(job)
        usage = _ExtendedLimits()
        native.require(native.api.QueryInformationJobObject(job, 9, ctypes.byref(usage), ctypes.sizeof(usage), None))
        return RunResult(process.pid, exit_code, reason, after.active_processes == 0,
                         after.active_processes, before.active_processes, round(time.monotonic() - started, 3),
                         round((after.user_time + after.kernel_time) / 10_000_000, 4), usage.peak_job_memory)
    finally:
        if process.process and not assigned:
            native.api.TerminateProcess(process.process, 125)
            native.api.WaitForSingleObject(process.process, 5000)
        # Closing the sole non-inherited job handle also covers errors and owner death.
        native.close(job)
        for handle in duplicates:
            native.close(handle)
        native.close(process.thread)
        native.close(process.process)
