import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

from src.orchestration.development_progress import read_development_progress
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryStore


def build_session_start_context(
    project_root: str | Path,
    thread_id: str = "",
    memory_root: str | Path | None = None,
    max_items: int = 10,
) -> Dict[str, Any]:
    root = Path(project_root).resolve()
    latest_progress_path = _latest_path(root / ".kh" / "development", "progress.json")
    latest_progress = {}
    if latest_progress_path:
        latest_progress = read_development_progress(latest_progress_path).to_dict()

    compound_capture = _read_latest_json(root / ".kh" / "development", "compound_capture.json")
    compound_handoff = _read_latest_json(root / ".kh" / "development", "compound_handoff.json")
    kh_docs = _latest_docs(root / "docs" / "kh", max_items=max_items)
    memory_candidates = _memory_candidates(root, thread_id=thread_id, memory_root=memory_root, max_items=max_items)

    recommended_reads = []
    for path in [latest_progress_path]:
        if path:
            recommended_reads.append(str(path))
    recommended_reads.extend(item["path"] for item in kh_docs[: max_items // 2 or 1])
    recommended_reads.extend(
        item.get("metadata", {}).get("source_path", "")
        for item in memory_candidates
        if item.get("metadata", {}).get("source_path")
    )

    return {
        "project_root": str(root),
        "thread_id": thread_id,
        "latest_progress_path": str(latest_progress_path) if latest_progress_path else "",
        "latest_progress": latest_progress,
        "compound_capture": compound_capture,
        "compound_handoff": compound_handoff,
        "docs_kh": kh_docs,
        "memory_candidates": memory_candidates,
        "recommended_reads": _dedupe([item for item in recommended_reads if item])[:max_items],
        "evidence": [
            "session_start_context",
            ".kh",
            "docs/kh",
            "memory_candidates",
        ],
    }


def render_session_start_context(context: Dict[str, Any]) -> str:
    progress = context.get("latest_progress", {})
    handoff = context.get("compound_handoff", {})
    lines = [
        "KH Session Start Context",
        f"Project: {context.get('project_root', '')}",
    ]
    if progress:
        lines.append(f"Latest progress: {progress.get('run_id', '')} status={progress.get('task_status', '')}")
        if progress.get("next_task"):
            lines.append(f"Next task: {progress.get('next_task')}")
    if handoff:
        lines.append(f"Compound: {handoff.get('status', '')}")
        next_skills = handoff.get("next_skills", [])
        if next_skills:
            lines.append(f"Next skills: {', '.join(next_skills)}")
    lines.append("")
    lines.append("Recommended Reads")
    for path in context.get("recommended_reads", []) or ["none"]:
        lines.append(f"- {path}")
    lines.append("")
    lines.append("Memory Candidates")
    for item in context.get("memory_candidates", []) or [{"content": "none"}]:
        lines.append(f"- {item.get('content', '')}")
    return "\n".join(lines).rstrip() + "\n"


def _latest_path(root: Path, filename: str) -> Path | None:
    if not root.exists():
        return None
    matches = [path for path in root.rglob(filename) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _read_latest_json(root: Path, filename: str) -> Dict[str, Any]:
    path = _latest_path(root, filename)
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"path": str(path), "error": "invalid_json"}


def _latest_docs(root: Path, max_items: int) -> List[Dict[str, str]]:
    if not root.exists():
        return []
    docs = [path for path in root.rglob("*.md") if path.is_file()]
    latest = sorted(docs, key=lambda path: path.stat().st_mtime, reverse=True)[:max_items]
    return [{"path": str(path), "title": _first_heading(path)} for path in latest]


def _first_heading(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines()[:40]:
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return path.stem


def _memory_candidates(
    project_root: Path,
    thread_id: str,
    memory_root: str | Path | None,
    max_items: int,
) -> List[Dict[str, Any]]:
    scope = MemoryScopeResolver.project_scope(str(project_root), thread_id=thread_id or None)
    root = Path(memory_root).resolve() if memory_root else Path(MemoryScopeResolver.storage_path(scope))
    if memory_root:
        scope = replace(scope, root_path=str(root))
    candidates = MemoryStore(str(root), scope).read_candidates()
    return candidates[-max_items:] if max_items >= 0 else candidates


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output
