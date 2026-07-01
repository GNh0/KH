import os

from src.skills.base import agent_skill


WORKSPACE_ROOT = os.path.abspath(os.getcwd())


def _is_safe_path(filepath: str) -> bool:
    """Return true when the path stays inside the current workspace root."""
    abs_path = os.path.abspath(filepath)
    try:
        return os.path.commonpath([WORKSPACE_ROOT, abs_path]) == WORKSPACE_ROOT
    except ValueError:
        return False


@agent_skill(name="read_file", description="Read a UTF-8 text file from the current workspace.")
def read_file(filepath: str) -> str:
    if not _is_safe_path(filepath):
        return f"Security Error: file access outside workspace is blocked ({WORKSPACE_ROOT})"
    if not os.path.exists(filepath):
        return f"Error: file does not exist: {filepath}"
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


@agent_skill(name="write_file", description="Write UTF-8 text to a file inside the current workspace.")
def write_file(filepath: str, content: str) -> str:
    if not _is_safe_path(filepath):
        return f"Security Error: file access outside workspace is blocked ({WORKSPACE_ROOT})"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Success: wrote {filepath}"
