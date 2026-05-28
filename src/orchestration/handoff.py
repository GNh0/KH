import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.contracts import HandoffSnapshot
from src.orchestration.artifacts import ArtifactStore
from src.orchestration.goal_ledger import GoalLedger
from src.orchestration.runtime_paths import project_state_dir


class ResumeHandoff:
    def __init__(self, project_dir: str, thread_id: str = ""):
        self.project_root = Path(project_dir).resolve()
        self.thread_id = thread_id
        self.state_dir = project_state_dir(str(self.project_root), thread_id=thread_id)
        self.json_path = self.state_dir / "resume_handoff.json"
        self.markdown_path = self.state_dir / "resume_handoff.md"

    def resolve_project_path(self, path: str) -> Path:
        raw_path = Path(path)
        candidate = raw_path if raw_path.is_absolute() else self.project_root / raw_path
        resolved = candidate.resolve()
        try:
            common_root = os.path.commonpath([str(self.project_root), str(resolved)])
        except ValueError as exc:
            raise ValueError(f"path escapes project root: {path}") from exc
        if common_root != str(self.project_root):
            raise ValueError(f"path escapes project root: {path}")
        return resolved

    def describe_paths(self) -> Dict[str, str]:
        return {
            "json_path": str(self.json_path),
            "markdown_path": str(self.markdown_path),
        }

    def build_snapshot(self) -> HandoffSnapshot:
        ledger = GoalLedger(str(self.project_root), thread_id=self.thread_id)
        state = ledger.load_current_goal()
        if not state:
            return HandoffSnapshot(
                project_dir=str(self.project_root),
                status="unavailable",
                next_recommended_action="current_goal.json not found; start a new UAF goal or run workflow dispatch first",
                generated_at=_utc_now(),
                metadata={
                    "source": "resume_handoff",
                    "paths": self.describe_paths(),
                },
            )

        goal = dict(state.get("goal", {}))
        goal_metadata = dict(goal.get("metadata", {}))
        manifest = _artifact_manifest_from_state(str(self.project_root), goal_metadata, self.thread_id)
        missing_evidence = _missing_evidence(state, goal_metadata)
        workflow_id = manifest.get("workflow_id", "")

        return HandoffSnapshot(
            project_dir=str(self.project_root),
            workflow_id=workflow_id,
            objective=state.get("objective", goal.get("objective", "")),
            status=state.get("status", goal.get("status", "unknown")),
            next_recommended_action=state.get("next_recommended_action", ""),
            success_criteria=list(state.get("success_criteria", goal.get("success_criteria", []))),
            evidence_required=list(state.get("evidence_required", goal.get("evidence_required", []))),
            evidence=list(state.get("evidence", goal.get("evidence", []))),
            missing_evidence=missing_evidence,
            artifact_manifest=manifest,
            memory_context=dict(goal_metadata.get("memory_context", {})),
            goal=goal,
            generated_at=_utc_now(),
            metadata={
                "source": "resume_handoff",
                "schema_version": 1,
                "paths": self.describe_paths(),
                "goal_state_path": str(ledger.current_goal_path),
                "artifact_manifest_path": str(ArtifactStore(str(self.project_root), thread_id=self.thread_id).manifest_path),
            },
        )

    def save(self) -> Dict[str, Any]:
        snapshot = self.build_snapshot()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.json_path.write_text(
            json.dumps(snapshot.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self.markdown_path.write_text(
            render_handoff_markdown(snapshot),
            encoding="utf-8",
        )
        return {
            "snapshot": snapshot.to_dict(),
            "paths": self.describe_paths(),
        }


def render_handoff_markdown(snapshot: HandoffSnapshot) -> str:
    return "\n".join([
        "# UAF Resume Handoff",
        "",
        "No prior chat context is required. Use this file plus the JSON snapshot to resume the workflow.",
        "",
        f"- Objective: {snapshot.objective or 'not available'}",
        f"- Status: {snapshot.status}",
        f"- Workflow ID: {snapshot.workflow_id or 'not available'}",
        f"- Next action: {snapshot.next_recommended_action or 'inspect current goal'}",
        "",
        "## Success Criteria",
        _bullet_list(snapshot.success_criteria),
        "",
        "## Missing Evidence",
        _bullet_list(snapshot.missing_evidence),
        "",
        "## Evidence Required",
        _bullet_list(snapshot.evidence_required),
        "",
        "## Evidence Collected",
        _bullet_list(snapshot.evidence),
        "",
        "## Design Artifacts",
        _artifact_list(snapshot.artifact_manifest),
        "",
        "## Memory Context",
        f"- Record count: {snapshot.memory_context.get('record_count', 0)}",
        "",
        "## Runtime Paths",
        f"- Resume JSON: {snapshot.metadata.get('paths', {}).get('json_path', '')}",
        f"- Current goal: {snapshot.metadata.get('goal_state_path', '')}",
        f"- Artifact manifest: {snapshot.metadata.get('artifact_manifest_path', '')}",
        "",
    ])


def _artifact_manifest_from_state(project_dir: str, goal_metadata: Dict[str, Any], thread_id: str = "") -> Dict[str, Any]:
    manifest = ArtifactStore(project_dir, thread_id=thread_id).load_manifest().to_dict()
    if manifest.get("workflow_id"):
        return manifest
    return dict(goal_metadata.get("artifact_manifest", {}))


def _missing_evidence(state: Dict[str, Any], goal_metadata: Dict[str, Any]) -> List[str]:
    missing = goal_metadata.get("missing_evidence", [])
    if missing:
        return list(missing)
    evidence = {str(item) for item in state.get("evidence", [])}
    return [
        item
        for item in state.get("evidence_required", [])
        if str(item) not in evidence
    ]


def _artifact_list(manifest: Dict[str, Any]) -> str:
    artifacts = manifest.get("design_artifacts", []) if manifest else []
    if not artifacts:
        return "- none"
    lines = []
    for artifact in artifacts:
        lines.append(
            f"- {artifact.get('artifact_id', '')}: {artifact.get('kind', '')} ({artifact.get('status', '')})"
        )
    return "\n".join(lines)


def _bullet_list(items: List[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
