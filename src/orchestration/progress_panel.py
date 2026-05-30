import json
from pathlib import Path
from typing import Any, Dict, List

from src.orchestration.development_progress import (
    DevelopmentRunProgress,
    derive_review_status,
    derive_task_status,
    final_report_fields,
)


def build_progress_panel(progress: DevelopmentRunProgress) -> Dict[str, Any]:
    fields = final_report_fields(progress)
    counts = {
        "complete": 0,
        "in_progress": 0,
        "review": 0,
        "fixing": 0,
        "blocked": 0,
        "pending": 0,
    }
    rows: List[Dict[str, Any]] = []
    for task in progress.tasks:
        status = task.status if task.status in counts else "pending"
        counts[status] += 1
        rows.append(
            {
                "task_id": task.task_id,
                "title": task.title,
                "status": task.status,
                "marker": _marker(task.status),
                "red_status": task.red_status,
                "green_status": task.green_status,
                "spec_review_status": task.spec_review_status,
                "code_quality_review_status": task.code_quality_review_status,
                "commit_sha": task.commit_sha,
                "next_action": task.next_action,
            }
        )

    return {
        "objective": progress.objective,
        "run_id": progress.run_id,
        "workspace_strategy": progress.workspace_strategy,
        "workspace_path": progress.workspace_path,
        "task_status": progress.task_status or derive_task_status(progress.tasks),
        "review_status": progress.review_status or derive_review_status(progress.tasks),
        "token_optimizer_status": progress.token_optimizer_status,
        "commit_sha": fields["commit_sha"],
        "next_task": fields["next_task"],
        "active_task": progress.active_task,
        "counts": counts,
        "rows": rows,
    }


def render_progress_panel(progress: DevelopmentRunProgress) -> str:
    panel = build_progress_panel(progress)
    lines = [
        "KH Progress",
        f"Run: {panel['run_id']}",
        f"Objective: {panel['objective']}",
        f"Workspace: {panel['workspace_strategy']} {panel['workspace_path']}".rstrip(),
        (
            f"Status: {panel['task_status']} | Review: {panel['review_status']} | "
            f"Token: {panel['token_optimizer_status'] or 'not-recorded'}"
        ),
        (
            "Tasks: "
            f"{panel['counts']['complete']} complete, "
            f"{panel['counts']['in_progress'] + panel['counts']['review'] + panel['counts']['fixing']} active, "
            f"{panel['counts']['blocked']} blocked, "
            f"{panel['counts']['pending']} pending"
        ),
    ]
    if panel["commit_sha"]:
        lines.append(f"Latest commit: {panel['commit_sha']}")
    if panel["next_task"]:
        lines.append(f"Next: {panel['next_task']}")
    lines.append("")
    for row in panel["rows"]:
        commit = f", commit={row['commit_sha']}" if row["commit_sha"] else ""
        lines.append(
            f"{row['marker']} {row['task_id']} - {row['title']} "
            f"(RED={row['red_status']}, GREEN={row['green_status']}, "
            f"spec={row['spec_review_status']}, quality={row['code_quality_review_status']}{commit})"
        )
        if row["next_action"]:
            lines.append(f"    next_action: {row['next_action']}")
    return "\n".join(lines).rstrip() + "\n"


def build_host_progress_panel(progress: DevelopmentRunProgress, host: str = "generic") -> Dict[str, Any]:
    """Build a host-readable panel contract for Codex, Antigravity, CLI, or another shell."""
    normalized_host = _normalized_host(host)
    panel = build_progress_panel(progress)
    sections = [
        _progress_section(panel),
        _environment_section(progress, panel),
        _subagent_section(progress),
        _task_section(panel),
        _evidence_section(progress),
    ]
    return {
        "schema": "kh.uaf.host_progress_panel.v1",
        "host": normalized_host,
        "title": "KH Progress",
        "summary": {
            "objective": panel["objective"],
            "run_id": panel["run_id"],
            "task_status": panel["task_status"],
            "review_status": panel["review_status"],
            "workspace_strategy": panel["workspace_strategy"],
            "token_optimizer_status": panel["token_optimizer_status"] or "not-recorded",
            "commit_sha": panel["commit_sha"],
            "active_task": panel["active_task"],
            "next_task": panel["next_task"],
            "counts": panel["counts"],
        },
        "host_binding": {
            "preferred_surface": _preferred_surface(normalized_host),
            "refresh": "on_progress_state_change",
            "subagent_source": "progress.tasks[].metadata.agent|role",
            "worktree_source": "progress.workspace_strategy",
        },
        "capabilities": {
            "subagent_panel": normalized_host in {"antigravity", "codex"},
            "worktree_aware": bool(panel["workspace_strategy"]),
            "review_status": True,
            "token_status": True,
            "commit_status": True,
            "next_task": True,
        },
        "state_files": {
            "progress_json": _state_file(progress.run_id, "progress.json"),
            "host_panel_json": _state_file(progress.run_id, f"host_panel.{normalized_host}.json"),
        },
        "sections": sections,
    }


def write_host_progress_panel(
    project_root: str | Path,
    progress: DevelopmentRunProgress,
    host: str = "generic",
) -> Path:
    normalized_host = _normalized_host(host)
    path = Path(project_root) / ".kh" / "development" / progress.run_id / "state" / f"host_panel.{normalized_host}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_host_progress_panel(progress, host=normalized_host), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _marker(status: str) -> str:
    return {
        "complete": "[x]",
        "in_progress": "[>]",
        "review": "[?]",
        "fixing": "[!]",
        "blocked": "[BLOCKED]",
        "pending": "[ ]",
    }.get(status, "[ ]")


def _normalized_host(host: str) -> str:
    value = str(host or "generic").strip().lower().replace("_", "-")
    aliases = {
        "ag": "antigravity",
        "google-antigravity": "antigravity",
        "codex-app": "codex",
        "cli": "generic",
        "terminal": "generic",
    }
    return aliases.get(value, value or "generic")


def _preferred_surface(host: str) -> str:
    return {
        "antigravity": "antigravity-agent-manager",
        "codex": "codex-task-panel",
        "claude-code": "agent-worktree-panel",
    }.get(host, "json-status-panel")


def _state_file(run_id: str, file_name: str) -> str:
    return f".kh/development/{run_id}/state/{file_name}"


def _progress_section(panel: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": "progress",
        "title": "Progress",
        "items": [
            {"label": "Task Status", "value": panel["task_status"]},
            {"label": "Review Status", "value": panel["review_status"]},
            {"label": "Token Optimizer", "value": panel["token_optimizer_status"] or "not-recorded"},
            {"label": "Active Task", "value": panel["active_task"]},
            {"label": "Next Task", "value": panel["next_task"]},
            {"label": "Latest Commit", "value": panel["commit_sha"]},
        ],
    }


def _environment_section(progress: DevelopmentRunProgress, panel: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": "environment",
        "title": "Environment",
        "items": [
            {"label": "Workspace Strategy", "value": panel["workspace_strategy"]},
            {"label": "Workspace Path", "value": panel["workspace_path"]},
            {"label": "Branch", "value": progress.branch},
        ],
    }


def _subagent_section(progress: DevelopmentRunProgress) -> Dict[str, Any]:
    return {
        "id": "subagents",
        "title": "Subagents",
        "rows": [
            {
                "id": task.task_id,
                "name": _task_agent_name(task),
                "role": _task_agent_role(task),
                "status": task.status,
                "workspace": progress.workspace_path,
                "artifacts": list(task.changed_files),
                "next_action": task.next_action,
            }
            for task in progress.tasks
        ],
    }


def _task_section(panel: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": "tasks",
        "title": "Tasks",
        "rows": [
            {
                "id": row["task_id"],
                "title": row["title"],
                "status": row["status"],
                "marker": row["marker"],
                "commit_sha": row["commit_sha"],
                "next_action": row["next_action"],
                "detail": {
                    "red_status": row["red_status"],
                    "green_status": row["green_status"],
                    "spec_review_status": row["spec_review_status"],
                    "code_quality_review_status": row["code_quality_review_status"],
                },
            }
            for row in panel["rows"]
        ],
    }


def _evidence_section(progress: DevelopmentRunProgress) -> Dict[str, Any]:
    return {
        "id": "evidence",
        "title": "Evidence",
        "items": [
            {"label": "Artifact", "value": artifact}
            for artifact in progress.artifacts
        ],
        "skill_statuses": dict(progress.skill_statuses),
    }


def _task_agent_name(task: Any) -> str:
    metadata = task.metadata or {}
    return str(
        metadata.get("agent_name")
        or metadata.get("subagent")
        or metadata.get("role")
        or f"{task.task_id}-worker"
    )


def _task_agent_role(task: Any) -> str:
    metadata = task.metadata or {}
    return str(metadata.get("agent_role") or metadata.get("role") or "worker")
