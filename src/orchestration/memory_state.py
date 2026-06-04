import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.contracts import MemoryScope
from src.orchestration.runtime_paths import conversation_runtime_root, project_memory_dir


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


def _agent_lineage_segments(agent_lineage: Iterable[str] | str | None = None) -> List[str]:
    if not agent_lineage:
        return []
    if isinstance(agent_lineage, str):
        raw_items = re.split(r"[>/\\|,]+", agent_lineage)
    else:
        raw_items = [str(item) for item in agent_lineage]
    segments: List[str] = []
    for item in raw_items:
        segment = _safe_segment(item)
        if segment and segment != "default":
            segments.append(segment)
    return segments


def _metadata_agent_lineage(metadata: Dict[str, Any]) -> List[str]:
    metadata = metadata or {}
    app_context = metadata.get("app_context", {}) or {}
    explicit = metadata.get("agent_lineage") or app_context.get("agent_lineage")
    lineage = _agent_lineage_segments(explicit)

    parent = (
        metadata.get("parent_subagent_id")
        or app_context.get("parent_subagent_id")
        or metadata.get("parent_agent_id")
        or app_context.get("parent_agent_id")
    )
    current = (
        metadata.get("subagent_id")
        or app_context.get("subagent_id")
        or metadata.get("agent_id")
        or app_context.get("agent_id")
    )
    for item in [parent, current]:
        segment = _safe_segment(str(item or ""))
        if segment and segment != "default" and segment not in lineage:
            lineage.append(segment)
    return lineage


def _scope_level(base_kind: str, thread_id: Optional[str], agent_lineage: List[str]) -> str:
    if agent_lineage:
        return f"{base_kind}_chat_subagent" if thread_id else f"{base_kind}_subagent"
    if thread_id:
        return f"{base_kind}_chat"
    return base_kind


class MemoryScopeResolver:
    @staticmethod
    def project_scope(
        project_dir: str,
        status: str = "active",
        thread_id: Optional[str] = None,
        project_id: str = "",
        agent_lineage: Iterable[str] | str | None = None,
    ) -> MemoryScope:
        project_root = Path(project_dir).resolve()
        display_id = project_id or project_root.name or "project"
        lineage = _agent_lineage_segments(agent_lineage)
        memory_root = project_memory_dir(str(project_root), thread_id=thread_id)
        if lineage:
            memory_root = memory_root / "agents" / Path(*lineage)
        namespace = _project_namespace(project_root)
        if thread_id:
            namespace = f"{namespace}:chat:{_safe_segment(thread_id)}"
        if lineage:
            namespace = f"{namespace}:agent:{'/'.join(lineage)}"
        return MemoryScope(
            kind="project",
            namespace=namespace,
            project_id=display_id,
            thread_id=thread_id,
            root_path=str(memory_root),
            status=normalize_memory_status(status),
            metadata={
                "workspace_root": str(project_root),
                "scope_level": _scope_level("project", thread_id, lineage),
                "agent_lineage": lineage,
                "lineage_depth": len(lineage),
            },
        )

    @staticmethod
    def conversation_scope(
        thread_id: str,
        conversation_memory_root: str,
        status: str = "active",
        agent_lineage: Iterable[str] | str | None = None,
    ) -> MemoryScope:
        if not thread_id:
            raise ValueError("conversation memory requires a thread_id")
        safe_thread_id = _safe_segment(thread_id)
        lineage = _agent_lineage_segments(agent_lineage)
        conversation_root = conversation_runtime_root(thread_id, conversation_memory_root)
        memory_root = conversation_root / ".uaf" / "memory"
        if lineage:
            memory_root = memory_root / "agents" / Path(*lineage)
        namespace = f"conversation:{safe_thread_id}"
        if lineage:
            namespace = f"{namespace}:agent:{'/'.join(lineage)}"
        return MemoryScope(
            kind="conversation",
            namespace=namespace,
            thread_id=thread_id,
            root_path=str(memory_root),
            status=normalize_memory_status(status),
            metadata={
                "conversation_memory_root": str(conversation_root),
                "scope_level": _scope_level("conversation", thread_id, lineage),
                "agent_lineage": lineage,
                "lineage_depth": len(lineage),
            },
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
        agent_lineage = _metadata_agent_lineage(metadata)

        if project_dir:
            return MemoryScopeResolver.project_scope(
                project_dir=project_dir,
                status=status,
                thread_id=thread_id,
                project_id=metadata.get("project_id", ""),
                agent_lineage=agent_lineage,
            )

        root = conversation_memory_root or metadata.get("conversation_memory_root", "")
        return MemoryScopeResolver.conversation_scope(
            thread_id=thread_id,
            conversation_memory_root=root,
            status=status,
            agent_lineage=agent_lineage,
        )

    @staticmethod
    def storage_path(scope: MemoryScope) -> Path:
        if not scope.root_path:
            raise ValueError("memory scope has no root_path")
        return Path(scope.root_path)

    @staticmethod
    def parent_scope(scope: MemoryScope) -> Optional[MemoryScope]:
        """Resolve the immediate parent memory scope.

        Memory hierarchy is project -> chat -> subagent lineage. Sibling
        subagents do not share directly; promotion or read-only sharing must go
        through the nearest parent scope.
        """
        lineage = _agent_lineage_segments(scope.metadata.get("agent_lineage", []))
        if scope.kind == "project":
            workspace_root = str(scope.metadata.get("workspace_root", "")).strip()
            if not workspace_root:
                return None
            if lineage:
                return MemoryScopeResolver.project_scope(
                    workspace_root,
                    status=scope.status,
                    thread_id=scope.thread_id,
                    project_id=scope.project_id,
                    agent_lineage=lineage[:-1],
                )
            if scope.thread_id:
                return MemoryScopeResolver.project_scope(
                    workspace_root,
                    status=scope.status,
                    project_id=scope.project_id,
                )
            return None

        if scope.kind == "conversation":
            conversation_root = str(scope.metadata.get("conversation_memory_root", "")).strip()
            if not scope.thread_id or not conversation_root:
                return None
            if lineage:
                return MemoryScopeResolver.conversation_scope(
                    scope.thread_id,
                    conversation_root,
                    status=scope.status,
                    agent_lineage=lineage[:-1],
                )
            return None
        return None
