import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Optional

from src.contracts import MemoryScope


MEMORY_STATUSES = {"active", "archived", "deleted"}


def normalize_memory_status(status: str = "active") -> str:
    normalized = (status or "active").strip().lower()
    if normalized not in MEMORY_STATUSES:
        raise ValueError(f"unsupported memory status: {status}")
    return normalized


def _safe_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip())
    return segment.strip(".-") or "default"


def _project_namespace(project_root: Path) -> str:
    digest = hashlib.sha256(str(project_root).lower().encode("utf-8")).hexdigest()[:12]
    return f"project:{digest}"


class MemoryScopeResolver:
    @staticmethod
    def project_scope(
        project_dir: str,
        status: str = "active",
        thread_id: Optional[str] = None,
        project_id: str = "",
    ) -> MemoryScope:
        project_root = Path(project_dir).resolve()
        display_id = project_id or project_root.name or "project"
        memory_root = project_root / ".uaf" / "memory"
        return MemoryScope(
            kind="project",
            namespace=_project_namespace(project_root),
            project_id=display_id,
            thread_id=thread_id,
            root_path=str(memory_root),
            status=normalize_memory_status(status),
            metadata={"workspace_root": str(project_root)},
        )

    @staticmethod
    def conversation_scope(
        thread_id: str,
        conversation_memory_root: str,
        status: str = "active",
    ) -> MemoryScope:
        if not thread_id:
            raise ValueError("conversation memory requires a thread_id")
        root = Path(conversation_memory_root).resolve()
        safe_thread_id = _safe_segment(thread_id)
        memory_root = root / "conversations" / safe_thread_id
        return MemoryScope(
            kind="conversation",
            namespace=f"conversation:{safe_thread_id}",
            thread_id=thread_id,
            root_path=str(memory_root),
            status=normalize_memory_status(status),
            metadata={"conversation_memory_root": str(root)},
        )

    @staticmethod
    def from_adapter_metadata(
        project_dir: str,
        metadata: Dict[str, Any],
        conversation_memory_root: str = "",
    ) -> MemoryScope:
        metadata = metadata or {}
        app_context = metadata.get("app_context", {}) or {}
        thread_id = metadata.get("thread_id") or app_context.get("thread_id")
        status = metadata.get("memory_status", "active")

        if project_dir:
            return MemoryScopeResolver.project_scope(
                project_dir=project_dir,
                status=status,
                thread_id=thread_id,
                project_id=metadata.get("project_id", ""),
            )

        root = conversation_memory_root or metadata.get("conversation_memory_root", "")
        if not root:
            raise ValueError("conversation memory requires conversation_memory_root when project_dir is empty")
        return MemoryScopeResolver.conversation_scope(
            thread_id=thread_id,
            conversation_memory_root=root,
            status=status,
        )

    @staticmethod
    def storage_path(scope: MemoryScope) -> Path:
        if not scope.root_path:
            raise ValueError("memory scope has no root_path")
        return Path(scope.root_path)
