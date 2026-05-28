import os
from src.skills.base import agent_skill

# 워크스페이스 외부 경로 접근을 차단하기 위한 루트 디렉토리 설정
WORKSPACE_ROOT = os.path.abspath(os.getcwd())

def _is_safe_path(filepath: str) -> bool:
    """요청된 경로가 허용된 워크스페이스 내부에 있는지 검증합니다."""
    abs_path = os.path.abspath(filepath)
    try:
        return os.path.commonpath([WORKSPACE_ROOT, abs_path]) == WORKSPACE_ROOT
    except ValueError:
        return False

@agent_skill(name="read_file", description="주어진 경로의 파일 내용을 읽어옵니다.")
def read_file(filepath: str) -> str:
    if not _is_safe_path(filepath):
        return f"Security Error: 워크스페이스({WORKSPACE_ROOT}) 외부의 파일 접근은 차단되었습니다."
    if not os.path.exists(filepath):
        return f"Error: {filepath} 파일이 존재하지 않습니다."
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

@agent_skill(name="write_file", description="주어진 경로에 텍스트를 파일로 저장합니다.")
def write_file(filepath: str, content: str) -> str:
    if not _is_safe_path(filepath):
        return f"Security Error: 워크스페이스({WORKSPACE_ROOT}) 외부의 파일 접근은 차단되었습니다."
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return f"Success: {filepath} 작성 완료."
