import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    ) -> Dict[str, Any]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        normalized_tasks = {
            "pending": [],
            "in_progress": [],
            "completed": [],
            "blocked": [],
        }
        normalized_tasks.update(tasks or {})

        project_markdown = {}
        if project_markdown_enabled():
            project_markdown = write_goal_markdown_artifacts(
                str(self.project_root),
                goal,
                active_task=active_task,
                next_recommended_action=next_recommended_action,
            )

        state = {
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
            "project_markdown": project_markdown,
            "goal": json.loads(json.dumps(goal)),
            "updated_at": _utc_now(),
        }
        self.current_goal_path.write_text(
            json.dumps(state, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return state

    def load_current_goal(self) -> Dict[str, Any]:
        if not self.current_goal_path.exists():
            return {}
        return json.loads(self.current_goal_path.read_text(encoding="utf-8"))

    def append_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "event_type": event_type,
            "timestamp": _utc_now(),
            "payload": json.loads(json.dumps(payload)),
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True))
            handle.write("\n")
        return event

    def read_events(self) -> List[Dict[str, Any]]:
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
        events = self.read_events()
        kept = events[-max_events:] if max_events else []
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("w", encoding="utf-8") as handle:
            for event in kept:
                handle.write(json.dumps(event, sort_keys=True))
                handle.write("\n")
        return {"before": len(events), "after": len(kept), "deleted": len(events) - len(kept)}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
