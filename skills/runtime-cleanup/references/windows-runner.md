# Owned Windows command trees

Use this for disposable task commands whose descendants must not outlive the command. Python 3.11+ and Windows 8+ are required. No extra package, process inventory service, PID registry or administrator-only installer is needed. Normal sandbox and approval rules still apply.

```powershell
python -B <plugin-root>/scripts/kh_runtime.py --cwd C:/Task --timeout 120 -- node.exe C:/Task/probe.mjs
```

Supply the actual interpreter executable and argument list. The helper does not infer shell syntax or quote a batch script as an executable; invoke the real interpreter when needed. It inherits standard input/output/error and environment, launches a hidden command, and preserves the root exit code. Omit `--timeout` when the task needs an explicitly supervised longer lifetime; stop through the owning terminal session. Do not use this disposable-command lifetime for a user application or service intended to remain after the command exits.

The new process starts suspended, enters a fresh Windows Job Object, then resumes. The job has kill-on-close and no breakaway flags. Normal exit, timeout, error, interruption or supervisor death closes the owned tree, including children left behind by an exited root. Job assignment failure stops the suspended process instead of running without containment. Processes created through external brokers/services are outside this guarantee.

The helper writes one `KH_RUNTIME_RESULT=` JSON record to stderr. `cleanup_verified=true` and `remaining_processes=0` mean the job's active process count reached zero. `active_before_cleanup` is the job's reported active count before termination, not an exact count of processes killed. CPU seconds and peak job memory describe this owned job, not system-wide usage or freed memory. Exit codes are the root's code, 124 for timeout, 130 for interruption, and 125 for a helper failure or unverified cleanup.

Existing processes cannot be adopted by PID or name. This runner does not close application-managed MCP/REPL servers, enforce cleanup for commands launched outside it, or replace the host's session lifecycle. For REPL state, use the reset/disposal capability actually exposed by that host after releasing task-owned handles.

Basis: [Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [assigning a suspended process](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject), and [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw).
