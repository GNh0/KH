import os
import ast
import builtins
import tempfile
import shutil
import multiprocessing
import time


# ─────────────────────────────────────────────────────────────────────────────
# 전역 허용 폴더 레지스트리
# CLI 또는 AgentLoop이 시작할 때 set_allowed_workspace()로 등록하면
# 이후 모든 파일 생성/쓰기 요청이 이 경로들 안에서만 허용됩니다.
# ─────────────────────────────────────────────────────────────────────────────
_ALLOWED_WORKSPACES: list[str] = []

def set_allowed_workspace(path: str):
    """
    [V2.5] 파일 생성이 허용되는 기본 작업 폴더를 등록합니다.
    호출 시 기존 목록을 초기화하고 새 경로만 허용합니다.
    AgentLoop 또는 cli.py 초기화 시 반드시 호출하세요.
    """
    global _ALLOWED_WORKSPACES
    _ALLOWED_WORKSPACES = [os.path.abspath(path)]
    print(f"[Sandbox] 작업 폴더 등록됨: {_ALLOWED_WORKSPACES[0]}")

def add_allowed_workspace(path: str):
    """
    [V2.5] 추가로 허용할 폴더를 등록합니다.
    사용자가 프로젝트 폴더 외에도 특정 폴더를 사용해야 할 때 호출하세요.
    예) add_allowed_workspace("C:/shared_assets")
    """
    abs_path = os.path.abspath(path)
    if abs_path not in _ALLOWED_WORKSPACES:
        _ALLOWED_WORKSPACES.append(abs_path)
        print(f"[Sandbox] 추가 허용 폴더 등록됨: {abs_path}")

def get_allowed_workspaces() -> list[str]:
    """[V2.5] 현재 등록된 전체 허용 폴더 목록을 반환합니다."""
    return list(_ALLOWED_WORKSPACES)

def _assert_within_workspace(path: str):
    """
    [V2.5] 지정된 경로가 허용된 작업 폴더 중 하나에라도 속하는지 강제 검증합니다.
    모든 허용 폴더를 뺗어나면 즉시 PermissionError를 발생시킵니다.
    """
    if not _ALLOWED_WORKSPACES:
        raise PermissionError(
            "[Sandbox] 작업 폴더가 등록되지 않았습니다. "
            "set_allowed_workspace()를 먼저 호출하세요."
        )
    abs_path = os.path.abspath(path)
    for allowed in _ALLOWED_WORKSPACES:
        if abs_path.startswith(allowed):
            return  # 허용된 폴더 안에 있음
    raise PermissionError(
        f"[Sandbox] 작업 폴더 이탈 감지!\n"
        f"  허용된 경로: {_ALLOWED_WORKSPACES}\n"
        f"  요청 경로: {abs_path}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# AST 기반 코드 정적 분석
# ─────────────────────────────────────────────────────────────────────────────
def _is_safe_code(code: str) -> bool:
    """AST 파싱을 통해 위험한 함수/모듈 사용을 차단합니다. (V2.5 강화판)"""
    dangerous_names = {
        'os', 'subprocess', 'shutil', 'sys', 'pty',
        '__import__', 'eval', 'exec', 'open',
        'getattr', 'setattr', '__traceback__',
        'tb_frame', 'f_globals', 'f_back'
    }
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in dangerous_names:
                return False
            if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                return False
            if isinstance(node, ast.Call) and getattr(node.func, 'id', '') in dangerous_names:
                return False
            if isinstance(node, ast.Attribute) and node.attr in dangerous_names:
                return False

        # 문자열 꼼수 방어
        for danger in dangerous_names:
            if danger in code:
                return False

        return True
    except SyntaxError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 격리 프로세스 실행 타겟
# ─────────────────────────────────────────────────────────────────────────────
def _run_isolated_process(code: str):
    """격리된 자식 프로세스에서 실제로 코드를 실행하는 타겟 함수"""
    try:
        wrapper = f"""
import builtins

# 호스트 환경으로의 탈출을 막기 위한 내장 함수 박탈
for _b in ['__import__', 'eval', 'exec', 'open', 'getattr', 'setattr']:
    if hasattr(builtins, _b):
        delattr(builtins, _b)

try:
    {code}
except Exception:
    pass
"""
        safe_globals = {"__builtins__": {}}
        exec(wrapper, safe_globals)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# 메인 샌드박스 클래스
# ─────────────────────────────────────────────────────────────────────────────
class CodeSandbox:
    """
    [V2.5] 가상 환경 및 권한 격리 기반 샌드박스 (Windows 완벽 호환)

    주요 보안 레이어:
    1. AST 정적 분석으로 위험 키워드 사전 차단
    2. multiprocessing 기반 타임아웃 강제 킬 (Windows 지원)
    3. 작업 폴더 범위 강제 적용 (프로젝트 디렉토리 이탈 불가)
    4. try...finally 가비지 컬렉션으로 임시 폴더 누수 원천 차단
    """
    def __init__(self, timeout: int = 5):
        self.timeout = timeout

    def write_file(self, path: str, content: str):
        """
        [V2.5] 파일 쓰기 전 작업 폴더 검증을 강제합니다.
        허용된 작업 폴더 밖에는 단 1바이트도 쓸 수 없습니다.
        """
        _assert_within_workspace(path)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def cleanup_workspace_temps(self, extensions: list = None):
        """
        [V2.5] 작업 폴더 내에 남은 임시 파일들을 자동으로 정리합니다.
        extensions: 삭제할 확장자 목록 (기본값: .tmp, .bak, .log, .pyc)
        """
        if _ALLOWED_WORKSPACE is None:
            return

        if extensions is None:
            extensions = [".tmp", ".bak", ".log", ".pyc"]

        removed = []
        for root, dirs, files in os.walk(_ALLOWED_WORKSPACE):
            # .snapshots 보호 구역은 절대 건드리지 않음
            dirs[:] = [d for d in dirs if d != ".snapshots"]
            for fname in files:
                if any(fname.endswith(ext) for ext in extensions):
                    full_path = os.path.join(root, fname)
                    try:
                        os.remove(full_path)
                        removed.append(full_path)
                    except Exception:
                        pass

        if removed:
            print(f"🧹 [Sandbox] 임시 파일 {len(removed)}개 정리 완료:")
            for p in removed:
                print(f"   - {p}")
        else:
            print("🧹 [Sandbox] 정리할 임시 파일 없음.")

    def run_python_code(self, code: str) -> dict:
        start_time = time.time()

        # [V2.4] CLI 디버그용 No-Sandbox 우회
        if os.environ.get("AG_NO_SANDBOX") == "1":
            print("⚠️ [Sandbox] 보안 샌드박스가 비활성화되어 있습니다.")
            return {
                "success": True,
                "stdout": "Sandbox bypassed.",
                "stderr": "",
                "exit_code": 0,
                "execution_time": 0.0
            }

        # 1. 1차 정적 보안 검증 (AST)
        if not _is_safe_code(code):
            return {
                "success": False,
                "stdout": "",
                "stderr": "Security Error: AST 검열에 의해 위험한 시스템 제어 모듈/함수 사용이 차단되었습니다.",
                "exit_code": -1,
                "execution_time": 0.0
            }

        # 2. V2.3 타임아웃 강제 킬 및 가비지 컬렉터 적용
        sandbox_dir = tempfile.mkdtemp(prefix="ag_sandbox_")
        try:
            p = multiprocessing.Process(target=_run_isolated_process, args=(code,))
            p.start()
            p.join(self.timeout)

            if p.is_alive():
                p.terminate()
                p.join()
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"TimeoutError: 실행 시간이 {self.timeout}초를 초과하여 강제 종료되었습니다.",
                    "exit_code": 124,
                    "execution_time": time.time() - start_time
                }

            success = (p.exitcode == 0)
            return {
                "success": success,
                "stdout": "Execution completed.",
                "stderr": "" if success else "Runtime Error occurred.",
                "exit_code": p.exitcode,
                "execution_time": time.time() - start_time
            }
        finally:
            # try 블록이 어떻게 끝나든 임시 폴더는 무조건 삭제 (가비지 컬렉션 보장)
            shutil.rmtree(sandbox_dir, ignore_errors=True)
