import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Optional


TRUE_VALUES = {"1", "true", "yes", "on"}


def project_local_state_enabled() -> bool:
    return os.environ.get("UAF_PROJECT_LOCAL_STATE", "").strip().lower() in TRUE_VALUES


def runtime_root() -> Path:
    configured = os.environ.get("UAF_RUNTIME_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        candidate = (Path(local_app_data) / "KH-UAF").resolve()
        if _can_write_runtime_root(candidate):
            return candidate

    home_candidate = (Path.home() / ".kh-uaf").resolve()
    if _can_write_runtime_root(home_candidate):
        return home_candidate

    return (Path(tempfile.gettempdir()) / "KH-UAF").resolve()


def project_runtime_root(project_dir: str, thread_id: Optional[str] = None) -> Path:
    project_root = Path(project_dir).resolve()
    if project_local_state_enabled():
        root = project_root
    else:
        root = runtime_root() / "projects" / _project_key(project_root)

    if thread_id:
        return root / "chats" / _safe_segment(thread_id)
    return root


def project_uaf_root(project_dir: str, thread_id: Optional[str] = None) -> Path:
    return project_runtime_root(project_dir, thread_id) / ".uaf"


def project_state_dir(project_dir: str, thread_id: Optional[str] = None) -> Path:
    return project_uaf_root(project_dir, thread_id) / "state"


def project_artifact_design_dir(project_dir: str, thread_id: Optional[str] = None) -> Path:
    return project_uaf_root(project_dir, thread_id) / "artifacts" / "design"


def project_memory_dir(project_dir: str, thread_id: Optional[str] = None) -> Path:
    return project_uaf_root(project_dir, thread_id) / "memory"


def project_snapshot_dir(project_dir: str, thread_id: Optional[str] = None) -> Path:
    return project_runtime_root(project_dir, thread_id) / ".snapshots"


def conversation_runtime_root(thread_id: str, conversation_memory_root: str = "") -> Path:
    if not thread_id:
        raise ValueError("conversation runtime requires a thread_id")
    root = Path(conversation_memory_root).resolve() if conversation_memory_root else runtime_root()
    return root / "conversations" / _safe_segment(thread_id)


def _project_key(project_root: Path) -> str:
    digest = hashlib.sha256(str(project_root).lower().encode("utf-8")).hexdigest()[:12]
    return f"{_safe_segment(project_root.name or 'project')}-{digest}"


def _safe_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip())
    return segment.strip(".-") or "default"


def _can_write_runtime_root(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False
