import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.contracts import MemoryRecord
from src.orchestration.development_progress import DevelopmentRunProgress, development_progress_path
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryStore


INTERRUPTION_SCHEMA = "kh.uaf.interruption_checkpoint.v1"


@dataclass(frozen=True)
class InterruptionCheckpoint:
    run_id: str
    project_root: str
    objective: str
    reason: str = "user_requested_stop"
    status: str = "interrupted"
    active_task: str = ""
    next_action: str = ""
    progress_path: str = ""
    changed_files: List[str] = field(default_factory=list)
    verification: List[Dict[str, Any]] = field(default_factory=list)
    remaining_work: List[str] = field(default_factory=list)
    goal: Dict[str, Any] = field(default_factory=dict)
    progress: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["schema"] = INTERRUPTION_SCHEMA
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterruptionCheckpoint":
        return cls(
            run_id=str(data.get("run_id", "")),
            project_root=str(data.get("project_root", "")),
            objective=str(data.get("objective", "")),
            reason=str(data.get("reason", "user_requested_stop")),
            status=str(data.get("status", "interrupted")),
            active_task=str(data.get("active_task", "")),
            next_action=str(data.get("next_action", "")),
            progress_path=str(data.get("progress_path", "")),
            changed_files=[str(item) for item in data.get("changed_files", [])],
            verification=[dict(item) for item in data.get("verification", []) if isinstance(item, dict)],
            remaining_work=[str(item) for item in data.get("remaining_work", [])],
            goal=dict(data.get("goal", {})),
            progress=dict(data.get("progress", {})),
            metadata=dict(data.get("metadata", {})),
            created_at=str(data.get("created_at", "")),
        )


def build_interruption_checkpoint(
    project_root: str | Path,
    progress: DevelopmentRunProgress | Dict[str, Any],
    *,
    goal: Dict[str, Any] | None = None,
    reason: str = "user_requested_stop",
    next_action: str = "",
    changed_files: List[str] | None = None,
    verification: List[Dict[str, Any]] | None = None,
    remaining_work: List[str] | None = None,
    metadata: Dict[str, Any] | None = None,
) -> InterruptionCheckpoint:
    progress_dict = progress.to_dict() if isinstance(progress, DevelopmentRunProgress) else dict(progress)
    run_id = str(progress_dict.get("run_id", "") or (metadata or {}).get("run_id", "interrupted-run"))
    active_task = str(progress_dict.get("active_task", ""))
    task = _active_task(progress_dict, active_task)
    merged_changed_files = list(changed_files or [])
    if not merged_changed_files and task:
        merged_changed_files = [str(item) for item in task.get("changed_files", [])]
    merged_verification = list(verification or [])
    if not merged_verification and task:
        merged_verification = [dict(item) for item in task.get("verification", []) if isinstance(item, dict)]
    merged_remaining_work = list(remaining_work or [])
    if not merged_remaining_work:
        merged_remaining_work = _remaining_work(progress_dict)
    resolved_root = Path(project_root).resolve()
    return InterruptionCheckpoint(
        run_id=run_id,
        project_root=str(resolved_root),
        objective=str(progress_dict.get("objective", "")),
        reason=reason or "user_requested_stop",
        status="interrupted",
        active_task=active_task,
        next_action=next_action or str(progress_dict.get("next_task", "")) or (task or {}).get("next_action", ""),
        progress_path=str(development_progress_path(resolved_root, run_id)),
        changed_files=merged_changed_files,
        verification=merged_verification,
        remaining_work=merged_remaining_work,
        goal=_blocked_goal_for_stop(goal or {}, reason=reason or "user_requested_stop"),
        progress=progress_dict,
        metadata={
            "user_stop_requested": True,
            "resume_requires_user_request": True,
            **dict(metadata or {}),
        },
        created_at=_utc_now(),
    )


def write_interruption_checkpoint(
    project_root: str | Path,
    progress: DevelopmentRunProgress | Dict[str, Any],
    *,
    goal: Dict[str, Any] | None = None,
    thread_id: str = "",
    memory_root: str | Path | None = None,
    persist_memory: bool = True,
    reason: str = "user_requested_stop",
    next_action: str = "",
    changed_files: List[str] | None = None,
    verification: List[Dict[str, Any]] | None = None,
    remaining_work: List[str] | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    checkpoint = build_interruption_checkpoint(
        project_root,
        progress,
        goal=goal,
        reason=reason,
        next_action=next_action,
        changed_files=changed_files,
        verification=verification,
        remaining_work=remaining_work,
        metadata=metadata,
    )
    root = Path(project_root).resolve()
    base = root / ".kh" / "development" / checkpoint.run_id
    state_dir = base / "state"
    content_dir = base / "content"
    state_dir.mkdir(parents=True, exist_ok=True)
    content_dir.mkdir(parents=True, exist_ok=True)
    json_path = state_dir / "interruption.json"
    markdown_path = content_dir / "interruption.md"
    json_path.write_text(
        json.dumps(checkpoint.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_interruption_markdown(checkpoint), encoding="utf-8")
    memory_result = _persist_interruption_memory(
        checkpoint,
        thread_id=thread_id,
        memory_root=memory_root,
        source_path=str(json_path),
        enabled=persist_memory,
    )
    return {
        "checkpoint": checkpoint.to_dict(),
        "paths": {
            "interruption_json": str(json_path),
            "interruption_markdown": str(markdown_path),
        },
        "memory": memory_result,
        "evidence": [
            "interruption_checkpoint",
            "user_requested_stop",
            "resume_checkpoint",
            *(["scoped_memory_resume_record"] if memory_result.get("status") == "saved" else []),
        ],
    }


def read_latest_interruption_checkpoint(project_root: str | Path) -> Dict[str, Any]:
    path = latest_interruption_checkpoint_path(project_root)
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"path": str(path), "error": "invalid_json"}


def latest_interruption_checkpoint_path(project_root: str | Path) -> Path | None:
    root = Path(project_root).resolve() / ".kh" / "development"
    if not root.exists():
        return None
    matches = [path for path in root.rglob("interruption.json") if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def render_interruption_markdown(checkpoint: InterruptionCheckpoint) -> str:
    return "\n".join(
        [
            "# KH Interruption Checkpoint",
            "",
            "The user asked to stop. Do not continue the goal automatically; resume only after a new user request.",
            "",
            f"- Run ID: {checkpoint.run_id}",
            f"- Status: {checkpoint.status}",
            f"- Reason: {checkpoint.reason}",
            f"- Objective: {checkpoint.objective or 'not available'}",
            f"- Active task: {checkpoint.active_task or 'none'}",
            f"- Next action: {checkpoint.next_action or 'inspect checkpoint'}",
            f"- Progress JSON: {checkpoint.progress_path}",
            "",
            "## Changed Files",
            _bullet_list(checkpoint.changed_files),
            "",
            "## Remaining Work",
            _bullet_list(checkpoint.remaining_work),
            "",
            "## Verification",
            _verification_list(checkpoint.verification),
            "",
        ]
    )


def _persist_interruption_memory(
    checkpoint: InterruptionCheckpoint,
    *,
    thread_id: str,
    memory_root: str | Path | None,
    source_path: str,
    enabled: bool,
) -> Dict[str, Any]:
    if not enabled:
        return {"status": "skipped", "reason": "persist_memory=false"}
    scope = MemoryScopeResolver.project_scope(checkpoint.project_root, thread_id=thread_id or None)
    root = Path(memory_root).resolve() if memory_root else MemoryScopeResolver.storage_path(scope)
    store = MemoryStore(str(root), scope)
    record = MemoryRecord(
        record_id=f"interruption-{checkpoint.run_id}",
        kind="resume-checkpoint",
        content=(
            f"Resume checkpoint for {checkpoint.run_id}: status={checkpoint.status}, "
            f"reason={checkpoint.reason}, active_task={checkpoint.active_task or 'none'}, "
            f"next_action={checkpoint.next_action or 'inspect checkpoint'}."
        ),
        scope=scope.kind,
        source="interruption_state",
        confidence="high",
        metadata={
            "source_path": source_path,
            "run_id": checkpoint.run_id,
            "project_root": checkpoint.project_root,
            "thread_id": thread_id,
            "resume_requires_user_request": True,
            "user_stop_requested": True,
            "remaining_work": list(checkpoint.remaining_work),
            "changed_files": list(checkpoint.changed_files),
        },
    )
    try:
        saved = store.save_record(record)
    except ValueError as exc:
        return {"status": "blocked", "error_type": type(exc).__name__, "message": str(exc)}
    return {
        "status": "saved",
        "record": saved.to_dict(),
        "store": store.describe_paths(),
    }


def _active_task(progress: Dict[str, Any], active_task: str) -> Dict[str, Any]:
    for task in progress.get("tasks", []) or []:
        if isinstance(task, dict) and active_task and task.get("task_id") == active_task:
            return task
    for task in progress.get("tasks", []) or []:
        if isinstance(task, dict) and task.get("status") in {"in_progress", "review", "fixing", "blocked"}:
            return task
    return {}


def _remaining_work(progress: Dict[str, Any]) -> List[str]:
    output = []
    for task in progress.get("tasks", []) or []:
        if isinstance(task, dict) and task.get("status") != "complete":
            detail = str(task.get("next_action") or task.get("title") or task.get("task_id") or "").strip()
            if detail:
                output.append(detail)
    if not output and progress.get("next_task"):
        output.append(str(progress.get("next_task")))
    return output


def _blocked_goal_for_stop(goal: Dict[str, Any], reason: str) -> Dict[str, Any]:
    if not goal:
        return {
            "status": "blocked",
            "blocked_reason": reason,
            "metadata": {"user_stop_requested": True},
        }
    blocked = dict(goal)
    blocked["status"] = "blocked"
    blocked["blocked_reason"] = reason
    metadata = dict(blocked.get("metadata", {}))
    metadata["user_stop_requested"] = True
    blocked["metadata"] = metadata
    return blocked


def _verification_list(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "- none"
    lines = []
    for item in items:
        command = item.get("command") or item.get("name") or "verification"
        status = item.get("status") or item.get("result") or item.get("exit_code", "")
        lines.append(f"- {command}: {status}")
    return "\n".join(lines)


def _bullet_list(items: List[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


__all__ = [
    "INTERRUPTION_SCHEMA",
    "InterruptionCheckpoint",
    "build_interruption_checkpoint",
    "latest_interruption_checkpoint_path",
    "read_latest_interruption_checkpoint",
    "render_interruption_markdown",
    "write_interruption_checkpoint",
]
