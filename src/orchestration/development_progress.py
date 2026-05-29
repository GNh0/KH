import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


TASK_STATUS_VALUES = {
    "pending",
    "in_progress",
    "review",
    "fixing",
    "complete",
    "blocked",
}
STEP_STATUS_VALUES = {
    "pending",
    "passed",
    "failed",
    "failed_expected",
    "with_fixes",
    "not_applicable",
    "blocked",
}
WORKSPACE_STRATEGIES = {
    "current-checkout",
    "project-local-worktree",
    "host-worktree",
    "isolated-branch",
}
TOKEN_OPTIMIZER_STATUSES = {
    "used",
    "considered_not_needed",
    "passthrough",
    "blocked",
}


@dataclass(frozen=True)
class DevelopmentTaskProgress:
    task_id: str
    title: str
    status: str = "pending"
    red_status: str = "pending"
    green_status: str = "pending"
    spec_review_status: str = "pending"
    code_quality_review_status: str = "pending"
    fix_status: str = "pending"
    re_review_status: str = "pending"
    commit_sha: str = ""
    changed_files: List[str] = field(default_factory=list)
    verification: List[Dict[str, Any]] = field(default_factory=list)
    next_action: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DevelopmentTaskProgress":
        return cls(
            task_id=str(data.get("task_id", "")),
            title=str(data.get("title", "")),
            status=str(data.get("status", "pending")),
            red_status=str(data.get("red_status", "pending")),
            green_status=str(data.get("green_status", "pending")),
            spec_review_status=str(data.get("spec_review_status", "pending")),
            code_quality_review_status=str(data.get("code_quality_review_status", "pending")),
            fix_status=str(data.get("fix_status", "pending")),
            re_review_status=str(data.get("re_review_status", "pending")),
            commit_sha=str(data.get("commit_sha", "")),
            changed_files=[str(item) for item in data.get("changed_files", [])],
            verification=[dict(item) for item in data.get("verification", []) if isinstance(item, dict)],
            next_action=str(data.get("next_action", "")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class DevelopmentRunProgress:
    run_id: str
    objective: str
    workspace_strategy: str
    tasks: List[DevelopmentTaskProgress] = field(default_factory=list)
    workspace_path: str = ""
    branch: str = ""
    active_task: str = ""
    task_status: str = ""
    review_status: str = ""
    commit_sha: str = ""
    next_task: str = ""
    token_optimizer_status: str = ""
    skill_statuses: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "objective": self.objective,
            "workspace_strategy": self.workspace_strategy,
            "workspace_path": self.workspace_path,
            "branch": self.branch,
            "active_task": self.active_task,
            "task_status": self.task_status or derive_task_status(self.tasks),
            "review_status": self.review_status or derive_review_status(self.tasks),
            "commit_sha": self.commit_sha,
            "next_task": self.next_task,
            "token_optimizer_status": self.token_optimizer_status,
            "skill_statuses": dict(self.skill_statuses),
            "tasks": [task.to_dict() for task in self.tasks],
            "artifacts": list(self.artifacts),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DevelopmentRunProgress":
        return cls(
            run_id=str(data.get("run_id", "")),
            objective=str(data.get("objective", "")),
            workspace_strategy=str(data.get("workspace_strategy", "")),
            workspace_path=str(data.get("workspace_path", "")),
            branch=str(data.get("branch", "")),
            active_task=str(data.get("active_task", "")),
            task_status=str(data.get("task_status", "")),
            review_status=str(data.get("review_status", "")),
            commit_sha=str(data.get("commit_sha", "")),
            next_task=str(data.get("next_task", "")),
            token_optimizer_status=str(data.get("token_optimizer_status", "")),
            skill_statuses=dict(data.get("skill_statuses", {})),
            tasks=[
                DevelopmentTaskProgress.from_dict(item)
                for item in data.get("tasks", [])
                if isinstance(item, dict)
            ],
            artifacts=[str(item) for item in data.get("artifacts", [])],
            metadata=dict(data.get("metadata", {})),
        )


def build_development_progress(
    run_id: str,
    objective: str,
    workspace_strategy: str,
    task_items: List[Dict[str, Any]],
    **kwargs: Any,
) -> DevelopmentRunProgress:
    return DevelopmentRunProgress(
        run_id=run_id,
        objective=objective,
        workspace_strategy=workspace_strategy,
        tasks=[DevelopmentTaskProgress.from_dict(item) for item in task_items],
        **kwargs,
    )


def development_progress_path(project_root: str | Path, run_id: str) -> Path:
    return Path(project_root) / ".kh" / "development" / run_id / "state" / "progress.json"


def write_development_progress(project_root: str | Path, progress: DevelopmentRunProgress) -> Path:
    path = development_progress_path(project_root, progress.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(progress.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def read_development_progress(path: str | Path) -> DevelopmentRunProgress:
    return DevelopmentRunProgress.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def validate_development_progress(progress: DevelopmentRunProgress) -> Dict[str, Any]:
    missing: List[str] = []
    if not progress.run_id.strip():
        missing.append("run_id")
    if not progress.objective.strip():
        missing.append("objective")
    if progress.workspace_strategy not in WORKSPACE_STRATEGIES:
        missing.append("workspace_strategy")
    if not progress.token_optimizer_status.strip():
        missing.append("token_optimizer_status")
    elif progress.token_optimizer_status not in TOKEN_OPTIMIZER_STATUSES:
        missing.append("token_optimizer_status")
    if not progress.tasks:
        missing.append("tasks")

    task_ids = [task.task_id for task in progress.tasks]
    if len(task_ids) != len(set(task_ids)):
        missing.append("tasks.unique_task_id")
    if progress.active_task and progress.active_task not in task_ids:
        missing.append("active_task.known_task_id")
    if progress.next_task and progress.next_task not in task_ids:
        missing.append("next_task.known_task_id")

    for task in progress.tasks:
        missing.extend(_validate_task(task))

    evidence = []
    if not missing:
        evidence = [
            "development_progress",
            "task_status",
            "review_status",
            "workspace_strategy",
            "token_optimizer_status",
            "progress_json",
        ]
    return {
        "valid": not missing,
        "missing": missing,
        "evidence": evidence,
        "summary": final_report_fields(progress) if not missing else {},
    }


def final_report_fields(progress: DevelopmentRunProgress) -> Dict[str, Any]:
    return {
        "task_status": progress.task_status or derive_task_status(progress.tasks),
        "review_status": progress.review_status or derive_review_status(progress.tasks),
        "commit_sha": progress.commit_sha or _latest_task_commit(progress.tasks),
        "next_task": progress.next_task or _next_incomplete_task(progress.tasks),
        "workspace_strategy": progress.workspace_strategy,
        "token_optimizer_status": progress.token_optimizer_status,
        "skill_statuses": dict(progress.skill_statuses),
    }


def derive_task_status(tasks: List[DevelopmentTaskProgress]) -> str:
    if not tasks:
        return "pending"
    statuses = {task.status for task in tasks}
    if "blocked" in statuses:
        return "blocked"
    if all(task.status == "complete" for task in tasks):
        return "complete"
    if statuses & {"in_progress", "review", "fixing"}:
        return "in_progress"
    return "pending"


def derive_review_status(tasks: List[DevelopmentTaskProgress]) -> str:
    if not tasks:
        return "pending"
    if any(
        task.spec_review_status == "blocked" or task.code_quality_review_status == "blocked"
        for task in tasks
    ):
        return "blocked"
    if any(
        task.spec_review_status == "with_fixes" or task.code_quality_review_status == "with_fixes"
        for task in tasks
    ):
        return "with_fixes"
    complete_tasks = [task for task in tasks if task.status == "complete"]
    if complete_tasks and all(
        task.spec_review_status in {"passed", "not_applicable"}
        and task.code_quality_review_status in {"passed", "not_applicable"}
        for task in complete_tasks
    ):
        return "passed"
    return "pending"


def _validate_task(task: DevelopmentTaskProgress) -> List[str]:
    missing: List[str] = []
    prefix = f"tasks.{task.task_id or '<missing>'}"
    if not task.task_id.strip():
        missing.append("tasks.task_id")
    if not task.title.strip():
        missing.append(f"{prefix}.title")
    if task.status not in TASK_STATUS_VALUES:
        missing.append(f"{prefix}.status")
    for field_name in [
        "red_status",
        "green_status",
        "spec_review_status",
        "code_quality_review_status",
        "fix_status",
        "re_review_status",
    ]:
        if getattr(task, field_name) not in STEP_STATUS_VALUES:
            missing.append(f"{prefix}.{field_name}")

    if task.status == "complete":
        if task.red_status == "pending":
            missing.append(f"{prefix}.red_status")
        if task.green_status not in {"passed", "not_applicable"}:
            missing.append(f"{prefix}.green_status")
        if task.spec_review_status not in {"passed", "not_applicable"}:
            missing.append(f"{prefix}.spec_review_status")
        if task.code_quality_review_status not in {"passed", "not_applicable"}:
            missing.append(f"{prefix}.code_quality_review_status")
        if task.code_quality_review_status == "with_fixes" and task.re_review_status != "passed":
            missing.append(f"{prefix}.re_review_status")
        if not task.commit_sha.strip():
            missing.append(f"{prefix}.commit_sha")
    if task.code_quality_review_status == "with_fixes":
        if task.fix_status not in {"passed", "not_applicable"}:
            missing.append(f"{prefix}.fix_status")
        if task.re_review_status != "passed":
            missing.append(f"{prefix}.re_review_status")
    return missing


def _latest_task_commit(tasks: List[DevelopmentTaskProgress]) -> str:
    for task in reversed(tasks):
        if task.commit_sha.strip():
            return task.commit_sha
    return ""


def _next_incomplete_task(tasks: List[DevelopmentTaskProgress]) -> str:
    for task in tasks:
        if task.status != "complete":
            return task.task_id
    return ""
