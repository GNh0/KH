import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


class KHProjectMarkdownStore:
    """Write human-readable KH markdown artifacts inside the target project."""

    def __init__(self, project_dir: str):
        self.project_root = Path(project_dir).resolve()

    def write_markdown(
        self,
        kind: str,
        title: str,
        body: str,
        slug: str = "",
        run_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        docs_copy: bool = True,
        local_root: str = ".kh",
        docs_root: str = "docs/kh",
    ) -> Dict[str, str]:
        safe_kind = _safe_segment(kind)
        safe_run_id = _safe_segment(run_id or _run_id())
        safe_slug = f"{_safe_segment(slug or title or safe_kind)}.md"
        document = render_markdown_document(
            title=title,
            body=body,
            metadata={
                "kind": safe_kind,
                "run_id": safe_run_id,
                **dict(metadata or {}),
            },
        )

        content_dir = self._project_path(local_root) / safe_kind / safe_run_id / "content"
        content_path = content_dir / safe_slug
        self._assert_in_project(content_path)
        content_dir.mkdir(parents=True, exist_ok=True)
        content_path.write_text(document, encoding="utf-8")

        docs_path = Path("")
        if docs_copy:
            docs_dir = self._project_path(docs_root) / safe_kind
            docs_path = docs_dir / safe_slug
            self._assert_in_project(docs_path)
            docs_dir.mkdir(parents=True, exist_ok=True)
            docs_path.write_text(document, encoding="utf-8")

        return {
            "kind": safe_kind,
            "run_id": safe_run_id,
            "content_path": str(content_path),
            "docs_path": str(docs_path) if docs_copy else "",
            "workspace_strategy": "project-local-markdown",
        }

    def _project_path(self, path: str) -> Path:
        candidate = (self.project_root / path).resolve()
        self._assert_in_project(candidate)
        return candidate

    def _assert_in_project(self, path: Path) -> None:
        try:
            common_root = os.path.commonpath([str(self.project_root), str(path.resolve())])
        except ValueError as exc:
            raise ValueError(f"path escapes project root: {path}") from exc
        if common_root != str(self.project_root):
            raise ValueError(f"path escapes project root: {path}")


def project_markdown_enabled() -> bool:
    configured = os.environ.get("UAF_PROJECT_MARKDOWN", "").strip().lower()
    if configured in FALSE_VALUES:
        return False
    if configured in TRUE_VALUES:
        return True
    return True


def render_markdown_document(title: str, body: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    metadata = {
        "title": title,
        "generated_at": _utc_now(),
        **dict(metadata or {}),
    }
    frontmatter = ["---"]
    for key, value in sorted(metadata.items()):
        frontmatter.append(f"{_safe_key(key)}: {_frontmatter_value(value)}")
    frontmatter.append("---")
    return "\n".join([
        *frontmatter,
        "",
        f"# {title}",
        "",
        body.strip(),
        "",
    ])


def render_goal_markdown(
    goal: Dict[str, Any],
    active_task: str = "",
    next_recommended_action: str = "",
) -> str:
    return "\n".join([
        f"- Objective: {goal.get('objective', '') or 'not specified'}",
        f"- Status: {goal.get('status', 'active')}",
        f"- Active task: {active_task or 'none'}",
        f"- Next action: {next_recommended_action or 'inspect goal state'}",
        f"- Blocked reason: {goal.get('blocked_reason', '') or 'none'}",
        "",
        "## Success Criteria",
        _bullet_list(goal.get("success_criteria", [])),
        "",
        "## Evidence Required",
        _bullet_list(goal.get("evidence_required", [])),
        "",
        "## Evidence Collected",
        _bullet_list(goal.get("evidence", [])),
    ])


def write_goal_markdown_artifacts(
    project_dir: str,
    goal: Dict[str, Any],
    active_task: str = "",
    next_recommended_action: str = "",
    run_id: str = "",
) -> Dict[str, str]:
    title = _goal_title(goal)
    return KHProjectMarkdownStore(project_dir).write_markdown(
        kind="goal",
        title=title,
        body=render_goal_markdown(
            goal,
            active_task=active_task,
            next_recommended_action=next_recommended_action,
        ),
        slug="current-goal",
        run_id=run_id or "current",
        metadata={
            "skill": "goal-state-harness",
            "status": goal.get("status", "active"),
        },
    )


def _goal_title(goal: Dict[str, Any]) -> str:
    objective = str(goal.get("objective", "") or "Current Goal").strip()
    return f"KH Goal - {objective[:80]}"


def _bullet_list(items: Any) -> str:
    values = [str(item) for item in list(items or [])]
    if not values:
        return "- none"
    return "\n".join(f"- {item}" for item in values)


def _frontmatter_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = str(value).replace("\n", " ").strip()
    if not text:
        return '""'
    if re.search(r"[:#{}\[\],&*?!|>'\"%@`]", text):
        return json.dumps(text, ensure_ascii=False)
    return text


def _safe_key(value: str) -> str:
    key = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())
    return key.strip("_") or "metadata"


def _safe_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip().lower())
    return segment.strip(".-") or "artifact"


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
