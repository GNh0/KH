import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from src.orchestration.project_markdown import (
    project_markdown_enabled,
    write_goal_markdown_artifacts,
)
from src.orchestration.runtime_paths import project_state_dir


class GoalLedger:
    def __init__(self, project_dir: str, thread_id: str = ""):
        self.project_root = Path(project_dir).resolve()
        self.thread_id = thread_id
        self.state_dir = project_state_dir(str(self.project_root), thread_id=thread_id)
        self.current_goal_path = self.state_dir / "current_goal.json"
        self.events_path = self.state_dir / "goal_events.jsonl"
        self.lock_path = self.state_dir / ".goal_ledger.lock"

    def resolve_project_path(self, path: str) -> Path:
        raw_path = Path(path)
        candidate = raw_path if raw_path.is_absolute() else self.project_root / raw_path
        resolved = candidate.resolve()

        root = str(self.project_root)
        target = str(resolved)
        try:
            common_root = os.path.commonpath([root, target])
        except ValueError as exc:
            raise ValueError(f"path escapes project root: {path}") from exc
        if common_root != root:
            raise ValueError(f"path escapes project root: {path}")
        return resolved

    def describe_paths(self) -> Dict[str, str]:
        return {
            "state_dir": str(self.state_dir),
            "current_goal_path": str(self.current_goal_path),
            "events_path": str(self.events_path),
        }

    def save_current_goal(
        self,
        goal: Dict[str, Any],
        active_task: str = "",
        tasks: Optional[Dict[str, List[str]]] = None,
        next_recommended_action: str = "",
        transition: str = "",
        expected_revision: str | None = None,
    ) -> Dict[str, Any]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with _exclusive_file_lock(self.lock_path):
            existing, actual_revision = self._load_current_goal_unlocked()
            if expected_revision is not None and str(expected_revision) != actual_revision:
                raise ValueError("concurrent goal ledger update conflict")
            if existing.get("goal"):
                _validate_goal_transition(existing["goal"], goal, transition)

            state = self._build_state(
                goal,
                active_task=active_task,
                tasks=tasks,
                next_recommended_action=next_recommended_action,
            )
            payload = json.dumps(state, indent=2, sort_keys=True)
            _atomic_write_text(self.current_goal_path, payload)
            state["_ledger_revision"] = _revision(payload.encode("utf-8"))
            return state

    def replace_current_goal(
        self,
        goal: Dict[str, Any],
        *,
        archived_goal: Dict[str, Any],
        archive_path: Path,
        active_task: str = "",
        tasks: Optional[Dict[str, List[str]]] = None,
        next_recommended_action: str = "",
        expected_revision: str,
    ) -> Dict[str, Any]:
        """Replace current state without exposing an archived-only current Goal."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive_file_lock(self.lock_path):
            existing, actual_revision = self._load_current_goal_unlocked()
            if str(expected_revision) != actual_revision:
                raise ValueError("concurrent goal ledger update conflict")
            if not existing.get("goal"):
                raise ValueError("current goal is required for replacement")
            _validate_goal_transition(existing["goal"], archived_goal, "archive_current")
            _validate_goal_transition(archived_goal, goal, "replace_archived")

            archived_state = self._build_state(
                archived_goal,
                active_task=existing.get("active_task", ""),
                tasks=existing.get("tasks", {}),
                next_recommended_action="replace archived goal",
                project_markdown=existing.get("project_markdown", {}),
            )
            state = self._build_state(
                goal,
                active_task=active_task,
                tasks=tasks,
                next_recommended_action=next_recommended_action,
            )
            archive_payload = json.dumps(archived_state, indent=2, sort_keys=True)
            current_payload = json.dumps(state, indent=2, sort_keys=True)
            _atomic_write_text(archive_path, archive_payload)
            try:
                _atomic_write_text(self.current_goal_path, current_payload)
            except Exception:
                try:
                    archive_path.unlink()
                except OSError:
                    pass
                raise
            state["_ledger_revision"] = _revision(current_payload.encode("utf-8"))
            return state

    def _build_state(
        self,
        goal: Dict[str, Any],
        *,
        active_task: str = "",
        tasks: Optional[Dict[str, List[str]]] = None,
        next_recommended_action: str = "",
        project_markdown: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_tasks = {
            "pending": [],
            "in_progress": [],
            "completed": [],
            "blocked": [],
        }
        normalized_tasks.update(tasks or {})
        markdown = dict(project_markdown or {})
        if project_markdown is None and project_markdown_enabled():
            markdown = write_goal_markdown_artifacts(
                str(self.project_root),
                goal,
                active_task=active_task,
                next_recommended_action=next_recommended_action,
            )
        return {
            "schema_version": 1,
            "objective": goal.get("objective", ""),
            "status": goal.get("status", "active"),
            "active_task": active_task,
            "tasks": normalized_tasks,
            "success_criteria": list(goal.get("success_criteria", [])),
            "evidence_required": list(goal.get("evidence_required", [])),
            "evidence": list(goal.get("evidence", [])),
            "blocked_reason": goal.get("blocked_reason", ""),
            "next_recommended_action": next_recommended_action,
            "project_markdown": markdown,
            "goal": json.loads(json.dumps(goal)),
            "updated_at": _utc_now(),
        }

    def load_current_goal(self) -> Dict[str, Any]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with _exclusive_file_lock(self.lock_path):
            state, revision = self._load_current_goal_unlocked()
        if state:
            state["_ledger_revision"] = revision
        return state

    def _load_current_goal_unlocked(self) -> tuple[Dict[str, Any], str]:
        if not self.current_goal_path.exists():
            return {}, ""
        raw = self.current_goal_path.read_bytes()
        return json.loads(raw.decode("utf-8")), _revision(raw)

    def append_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with _exclusive_file_lock(self.lock_path):
            event = {
                "event_type": event_type,
                "timestamp": _utc_now(),
                "payload": json.loads(json.dumps(payload)),
            }
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        return event

    def read_events(self) -> List[Dict[str, Any]]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with _exclusive_file_lock(self.lock_path):
            return self._read_events_unlocked()

    def _read_events_unlocked(self) -> List[Dict[str, Any]]:
        if not self.events_path.exists():
            return []
        return [
            json.loads(line)
            for line in self.events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def trim_events(self, max_events: int) -> Dict[str, int]:
        if max_events < 0:
            raise ValueError("max_events must be >= 0")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with _exclusive_file_lock(self.lock_path):
            events = self._read_events_unlocked()
            kept = events[-max_events:] if max_events else []
            payload = "".join(f"{json.dumps(event, sort_keys=True)}\n" for event in kept)
            _atomic_write_text(self.events_path, payload)
        return {"before": len(events), "after": len(kept), "deleted": len(events) - len(kept)}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _revision(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _atomic_write_text(path: Path, payload: str) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _exclusive_file_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _validate_goal_transition(
    current: Mapping[str, Any],
    incoming: Mapping[str, Any],
    transition: str,
) -> None:
    current_status = str(current.get("status") or "active")
    incoming_status = str(incoming.get("status") or "active")
    terminal = {"complete", "blocked", "archived"}

    if incoming_status == "archived":
        if transition != "archive_current" or not _same_goal(current, incoming):
            raise ValueError("terminal goal archive requires an explicit same-goal transition")
        metadata = incoming.get("metadata", {}) or {}
        if not metadata.get("archive_reason") or not metadata.get("replacement_objective_hash"):
            raise ValueError("terminal goal archive requires replacement metadata")
        return

    if current_status not in terminal:
        if not _same_goal(current, incoming):
            raise ValueError("active goal replacement requires an explicit archive transition")
        return

    if current_status == "archived" and transition == "replace_archived":
        current_metadata = current.get("metadata", {}) or {}
        incoming_scope = (incoming.get("metadata", {}) or {}).get("scope", {}) or {}
        if _same_goal(current, incoming):
            raise ValueError("archived goal replacement requires a new goal identity")
        if str(current_metadata.get("replacement_objective_hash") or "") != str(
            incoming_scope.get("objective_hash") or ""
        ):
            raise ValueError("archived goal replacement objective does not match")
        return

    raise ValueError("terminal goal is immutable")


def _same_goal(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    first_scope = (first.get("metadata", {}) or {}).get("scope", {}) or {}
    second_scope = (second.get("metadata", {}) or {}).get("scope", {}) or {}
    first_id = str(first_scope.get("goal_id") or "")
    second_id = str(second_scope.get("goal_id") or "")
    if first_id or second_id:
        return bool(first_id) and first_id == second_id
    return str(first.get("objective") or "") == str(second.get("objective") or "")
