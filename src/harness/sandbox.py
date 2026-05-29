import ast
import contextlib
import io
import multiprocessing
import os
import queue
import shutil
import tempfile
import time
import traceback

from src.contracts import HarnessResult


_ALLOWED_WORKSPACES: list[str] = []


def set_allowed_workspace(path: str):
    """Replace the allowed workspace list with one project root."""
    global _ALLOWED_WORKSPACES
    _ALLOWED_WORKSPACES = [os.path.abspath(path)]
    print(f"[Sandbox] Workspace registered: {_ALLOWED_WORKSPACES[0]}")


def add_allowed_workspace(path: str):
    """Allow an additional workspace root."""
    abs_path = os.path.abspath(path)
    if abs_path not in _ALLOWED_WORKSPACES:
        _ALLOWED_WORKSPACES.append(abs_path)
        print(f"[Sandbox] Additional workspace registered: {abs_path}")


def get_allowed_workspaces() -> list[str]:
    return list(_ALLOWED_WORKSPACES)


def _assert_within_workspace(path: str):
    if not _ALLOWED_WORKSPACES:
        raise PermissionError("[Sandbox] No workspace registered. Call set_allowed_workspace() first.")

    abs_path = os.path.abspath(path)
    for allowed in _ALLOWED_WORKSPACES:
        allowed_path = os.path.abspath(allowed)
        try:
            if os.path.commonpath([abs_path, allowed_path]) == allowed_path:
                return
        except ValueError:
            continue

    raise PermissionError(
        f"[Sandbox] Path escapes allowed workspace.\n"
        f"  allowed={_ALLOWED_WORKSPACES}\n"
        f"  requested={abs_path}"
    )


def _normalize_code(code: str) -> str:
    """Remove UTF-8 BOM markers that can appear when Windows tools write snippets."""
    return code.replace("\ufeff", "")


def _is_safe_code(code: str) -> bool:
    dangerous_names = {
        "os",
        "subprocess",
        "shutil",
        "sys",
        "pty",
        "__import__",
        "eval",
        "exec",
        "open",
        "getattr",
        "setattr",
        "globals",
        "locals",
        "vars",
        "__builtins__",
        "__traceback__",
        "__class__",
        "__subclasses__",
        "__mro__",
        "__bases__",
        "__globals__",
        "__code__",
        "__closure__",
        "tb_frame",
        "f_globals",
        "f_back",
        "gi_frame",
        "cr_frame",
    }
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in dangerous_names:
            return False
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") in dangerous_names:
            return False
        if isinstance(node, ast.Attribute) and (
            node.attr in dangerous_names
            or (node.attr.startswith("__") and node.attr.endswith("__"))
        ):
            return False

    return True


def _run_isolated_process(code: str, result_queue):
    stdout = io.StringIO()
    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "Exception": Exception,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "print": print,
        "range": range,
        "RuntimeError": RuntimeError,
        "set": set,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "ValueError": ValueError,
    }

    try:
        compiled = compile(code, "<sandbox>", "exec")
        env = {"__builtins__": safe_builtins}
        with contextlib.redirect_stdout(stdout):
            exec(compiled, env, env)
        result_queue.put({
            "success": True,
            "stdout": stdout.getvalue(),
            "stderr": "",
            "exit_code": 0,
        })
    except BaseException as exc:
        result_queue.put({
            "success": False,
            "stdout": stdout.getvalue(),
            "stderr": "".join(traceback.format_exception_only(type(exc), exc)).strip(),
            "exit_code": 1,
        })


class CodeSandbox:
    """Small Python execution harness with AST filtering and timeout isolation."""

    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    def write_file(self, path: str, content: str):
        _assert_within_workspace(path)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def cleanup_workspace_temps(self, extensions: list = None):
        if not _ALLOWED_WORKSPACES:
            return

        extensions = extensions or [".tmp", ".bak", ".log", ".pyc"]
        removed = []

        for workspace in _ALLOWED_WORKSPACES:
            if not os.path.isdir(workspace):
                continue
            for root, dirs, files in os.walk(workspace):
                dirs[:] = [directory for directory in dirs if directory != ".snapshots"]
                for file_name in files:
                    if not any(file_name.endswith(extension) for extension in extensions):
                        continue
                    full_path = os.path.join(root, file_name)
                    try:
                        os.remove(full_path)
                        removed.append(full_path)
                    except OSError:
                        pass

        if removed:
            print(f"[Sandbox] Removed {len(removed)} temporary files.")
        else:
            print("[Sandbox] No temporary files to remove.")

    def run_python_code(self, code: str) -> dict:
        return self.run_python_code_result(code).to_dict()

    def run_python_code_result(self, code: str) -> HarnessResult:
        start_time = time.time()
        code = _normalize_code(code)

        if os.environ.get("AG_NO_SANDBOX") == "1":
            print("[Sandbox] Security sandbox is disabled.")
            return HarnessResult(
                success=True,
                stdout="Sandbox bypassed.",
                exit_code=0,
                execution_time=0.0,
                metadata={"sandbox": "disabled"},
            )

        if not _is_safe_code(code):
            return HarnessResult(
                success=False,
                stderr="Security Error: blocked unsafe syntax or API usage.",
                exit_code=-1,
                execution_time=0.0,
            )

        sandbox_dir = tempfile.mkdtemp(prefix="ag_sandbox_")
        result_queue = multiprocessing.Queue()
        try:
            process = multiprocessing.Process(target=_run_isolated_process, args=(code, result_queue))
            process.start()
            process.join(self.timeout)

            if process.is_alive():
                process.terminate()
                process.join()
                return HarnessResult(
                    success=False,
                    stderr=f"TimeoutError: execution exceeded {self.timeout} seconds.",
                    exit_code=124,
                    execution_time=time.time() - start_time,
                )

            try:
                result = HarnessResult.from_dict(result_queue.get_nowait())
            except queue.Empty:
                result = HarnessResult(
                    success=process.exitcode == 0,
                    stderr="" if process.exitcode == 0 else "Runtime Error occurred.",
                    exit_code=process.exitcode,
                )
            return HarnessResult(
                success=result.success,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                execution_time=time.time() - start_time,
                metadata=result.metadata,
            )
        finally:
            result_queue.close()
            shutil.rmtree(sandbox_dir, ignore_errors=True)
