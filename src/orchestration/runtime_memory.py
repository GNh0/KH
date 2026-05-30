from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.contracts import MemoryRecord, MemoryScope
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryStore


def record_workflow_memory_candidates(
    project_dir: str,
    metadata: Dict[str, Any] | None,
    candidates: Iterable[MemoryRecord],
) -> Dict[str, Any]:
    """Persist workflow memory candidates without promoting them to durable records."""
    metadata = metadata or {}
    candidates = list(candidates or [])
    if not candidates:
        return {
            "status": "considered_not_needed",
            "candidate_count": 0,
            "recorded_count": 0,
            "skipped_count": 0,
            "blocked_count": 0,
            "evidence": [],
        }
    if metadata.get("memory_candidates_auto") is False:
        return {
            "status": "skipped_with_rationale",
            "candidate_count": len(candidates),
            "recorded_count": 0,
            "skipped_count": len(candidates),
            "blocked_count": 0,
            "rationale": "memory candidate recording disabled by metadata.memory_candidates_auto=false",
            "evidence": ["memory_candidates"],
        }

    scope = _memory_scope(project_dir, metadata)
    store = MemoryStore(str(MemoryScopeResolver.storage_path(scope)), scope)
    existing_ids = {
        str(item.get("record_id", ""))
        for item in store.read_candidates()
        if item.get("record_id")
    }
    recorded: List[Dict[str, Any]] = []
    skipped: List[str] = []
    blocked: List[Dict[str, str]] = []

    for candidate in candidates:
        record = _candidate_record(candidate, scope)
        if record.record_id in existing_ids:
            skipped.append(record.record_id)
            continue
        try:
            recorded.append(store.append_candidate(record))
            existing_ids.add(record.record_id)
        except ValueError as exc:
            blocked.append({"record_id": record.record_id, "error_type": type(exc).__name__, "message": str(exc)})

    status = "candidates_recorded" if recorded else "already_recorded"
    if blocked and not recorded:
        status = "blocked"
    return {
        "status": status,
        "memory_scope": scope.to_dict(),
        "store": store.describe_paths(),
        "candidate_count": len(candidates),
        "recorded_count": len(recorded),
        "skipped_count": len(skipped),
        "blocked_count": len(blocked),
        "recorded_ids": [item.get("record_id", "") for item in recorded],
        "skipped_ids": skipped,
        "blocked": blocked,
        "promotion": "candidates_only",
        "evidence": ["memory-state-harness", "memory_candidates_recorded"] if recorded else ["memory-state-harness"],
    }


def _memory_scope(project_dir: str, metadata: Dict[str, Any]) -> MemoryScope:
    scope_data = metadata.get("memory_scope")
    if isinstance(scope_data, dict):
        scope = MemoryScope.from_dict(scope_data)
    else:
        scope = MemoryScopeResolver.from_adapter_metadata(
            project_dir=project_dir,
            metadata=metadata,
            conversation_memory_root=metadata.get("conversation_memory_root", ""),
        )
    memory_root = str(metadata.get("memory_root", "")).strip()
    if memory_root:
        return replace(scope, root_path=str(Path(memory_root).resolve()))
    return scope


def _candidate_record(candidate: MemoryRecord, scope: MemoryScope) -> MemoryRecord:
    return MemoryRecord(
        record_id=candidate.record_id,
        kind=candidate.kind,
        content=candidate.content,
        scope=scope.kind,
        source=candidate.source or "workflow_usability_runtime",
        confidence=candidate.confidence,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
        metadata={**dict(candidate.metadata), "candidate_scope": candidate.scope},
    )
