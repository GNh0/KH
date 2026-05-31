import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

from src.orchestration.development_progress import read_development_progress
from src.orchestration.interruption_state import (
    latest_interruption_checkpoint_path,
    read_latest_interruption_checkpoint,
)
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryStore
from src.orchestration.runtime_memory import build_explicit_cross_scope_memory_import


def build_session_start_context(
    project_root: str | Path,
    thread_id: str = "",
    memory_root: str | Path | None = None,
    max_items: int = 10,
    objective: str = "",
    explicit_memory_imports: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    root = Path(project_root).resolve()
    latest_progress_path = _latest_path(root / ".kh" / "development", "progress.json")
    latest_progress = {}
    if latest_progress_path:
        latest_progress = read_development_progress(latest_progress_path).to_dict()

    compound_capture = _read_latest_json(root / ".kh" / "development", "compound_capture.json")
    compound_handoff = _read_latest_json(root / ".kh" / "development", "compound_handoff.json")
    interruption_path = latest_interruption_checkpoint_path(root)
    interruption_checkpoint = read_latest_interruption_checkpoint(root) if interruption_path else {}
    kh_docs = _latest_docs(root / "docs" / "kh", max_items=max_items)
    memory_candidates = _memory_candidates(root, thread_id=thread_id, memory_root=memory_root, max_items=max_items)
    memory_context = _memory_context(root, thread_id=thread_id, memory_root=memory_root, max_items=max_items)
    memory_recall = _memory_recall(
        root,
        thread_id=thread_id,
        memory_root=memory_root,
        query=objective or _context_query(latest_progress, interruption_checkpoint, compound_handoff),
        max_items=max_items,
    )
    memory_imports = _explicit_memory_imports(
        root,
        thread_id=thread_id,
        memory_root=memory_root,
        imports=explicit_memory_imports or [],
        objective=objective,
        max_items=max_items,
    )

    recommended_reads = []
    for path in [interruption_path, latest_progress_path]:
        if path:
            recommended_reads.append(str(path))
    recommended_reads.extend(item["path"] for item in kh_docs[: max_items // 2 or 1])
    recommended_reads.extend(
        item.get("metadata", {}).get("source_path", "")
        for item in memory_candidates
        if item.get("metadata", {}).get("source_path")
    )
    recommended_reads.extend(
        item.get("metadata", {}).get("source_path", "")
        for item in memory_context.get("records", [])
        if item.get("metadata", {}).get("source_path")
    )

    return {
        "project_root": str(root),
        "thread_id": thread_id,
        "latest_progress_path": str(latest_progress_path) if latest_progress_path else "",
        "latest_progress": latest_progress,
        "compound_capture": compound_capture,
        "compound_handoff": compound_handoff,
        "interruption_checkpoint_path": str(interruption_path) if interruption_path else "",
        "interruption_checkpoint": interruption_checkpoint,
        "docs_kh": kh_docs,
        "memory_context": memory_context,
        "memory_recall": memory_recall,
        "memory_imports": memory_imports,
        "memory_candidates": memory_candidates,
        "recommended_reads": _dedupe([item for item in recommended_reads if item])[:max_items],
        "evidence": [
            "session_start_context",
            ".kh",
            "docs/kh",
            "memory_records",
            "memory_recall",
            "memory_candidates",
            *(("explicit_cross_scope_memory_import",) if memory_imports else ()),
            *(("interruption_checkpoint",) if interruption_checkpoint else ()),
        ],
    }


def render_session_start_context(context: Dict[str, Any]) -> str:
    progress = context.get("latest_progress", {})
    handoff = context.get("compound_handoff", {})
    interruption = context.get("interruption_checkpoint", {})
    lines = [
        "KH Session Start Context",
        f"Project: {context.get('project_root', '')}",
    ]
    if interruption:
        lines.append(
            f"Interrupted: {interruption.get('run_id', '')} reason={interruption.get('reason', '')}"
        )
        if interruption.get("next_action"):
            lines.append(f"Resume next action: {interruption.get('next_action')}")
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
    lines.append("Memory Records")
    for item in context.get("memory_context", {}).get("records", []) or [{"content": "none"}]:
        lines.append(f"- {item.get('content', '')}")
    lines.append("")
    lines.append("Memory Recall")
    for item in context.get("memory_recall", {}).get("records", []) or [{"content": "none"}]:
        score = item.get("score")
        suffix = f" (score={score})" if score is not None else ""
        lines.append(f"- {item.get('content', '')}{suffix}")
    lines.append("")
    lines.append("Explicit Memory Imports")
    for item in context.get("memory_imports", []) or [{"status": "none"}]:
        source = item.get("source_scope", {})
        lines.append(
            f"- {item.get('status', '')}: {item.get('application_status', '')}"
            f" source={source.get('namespace', '')}"
        )
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


def _memory_context(
    project_root: Path,
    thread_id: str,
    memory_root: str | Path | None,
    max_items: int,
) -> Dict[str, Any]:
    scope = MemoryScopeResolver.project_scope(str(project_root), thread_id=thread_id or None)
    root = Path(memory_root).resolve() if memory_root else Path(MemoryScopeResolver.storage_path(scope))
    if memory_root:
        scope = replace(scope, root_path=str(root))
    return MemoryStore(str(root), scope).build_context(limit=max_items)


def _memory_recall(
    project_root: Path,
    thread_id: str,
    memory_root: str | Path | None,
    query: str,
    max_items: int,
) -> Dict[str, Any]:
    scope = MemoryScopeResolver.project_scope(str(project_root), thread_id=thread_id or None)
    root = Path(memory_root).resolve() if memory_root else Path(MemoryScopeResolver.storage_path(scope))
    if memory_root:
        scope = replace(scope, root_path=str(root))
    return MemoryStore(str(root), scope).search_records(query=query, limit=max_items)


def _explicit_memory_imports(
    project_root: Path,
    thread_id: str,
    memory_root: str | Path | None,
    imports: List[Dict[str, Any]],
    objective: str,
    max_items: int,
) -> List[Dict[str, Any]]:
    results = []
    for item in imports:
        metadata = dict(item.get("metadata", {}))
        metadata.setdefault("cross_scope_memory_import", True)
        metadata.setdefault("memory_import_max_items", max_items)
        if memory_root:
            metadata.setdefault("memory_root", str(Path(memory_root).resolve()))
        if thread_id:
            metadata.setdefault("thread_id", thread_id)
        result = build_explicit_cross_scope_memory_import(
            str(project_root),
            metadata,
            source_scope=item.get("source_scope"),
            query=item.get("query", objective),
        )
        results.append(result)
    return results


def _context_query(
    progress: Dict[str, Any],
    interruption: Dict[str, Any],
    handoff: Dict[str, Any],
) -> str:
    parts = [
        progress.get("objective", ""),
        progress.get("active_task", ""),
        progress.get("next_task", ""),
        interruption.get("objective", ""),
        interruption.get("next_action", ""),
        handoff.get("summary", ""),
    ]
    return " ".join(str(part) for part in parts if part)


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    output = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output
