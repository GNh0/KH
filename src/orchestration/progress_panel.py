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


def _marker(status: str) -> str:
    return {
        "complete": "[x]",
        "in_progress": "[>]",
        "review": "[?]",
        "fixing": "[!]",
        "blocked": "[BLOCKED]",
        "pending": "[ ]",
    }.get(status, "[ ]")
