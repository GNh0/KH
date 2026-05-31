from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.contracts import MemoryRecord, MemoryScope
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryStore


MEMORY_PROVIDERS = {"local", "external", "hybrid", "passthrough"}


def resolve_memory_provider(metadata: Dict[str, Any] | None) -> Dict[str, Any]:
    """Resolve memory provider policy without requiring any optional provider package."""
    metadata = metadata or {}
    requested = str(metadata.get("memory_provider", "local") or "local").strip().lower()
    if requested not in MEMORY_PROVIDERS:
        return {
            "provider": "local",
            "requested_provider": requested,
            "status": "fallback",
            "fallback_provider": "local",
            "rationale": "Unknown memory provider; using local KH MemoryStore.",
            "evidence": ["memory_provider", "provider:local", "status:fallback"],
        }
    if requested == "passthrough":
        return {
            "provider": "passthrough",
            "requested_provider": requested,
            "status": "selected",
            "fallback_provider": "",
            "rationale": "Memory reads/writes intentionally disabled for this workflow.",
            "evidence": ["memory_provider", "provider:passthrough", "status:selected"],
        }
    external_available = bool(metadata.get("external_memory_available", False))
    strict = bool(metadata.get("memory_provider_strict", False))
    if requested == "external" and not external_available:
        if strict:
            return {
                "provider": "external",
                "requested_provider": requested,
                "status": "blocked",
                "fallback_provider": "",
                "rationale": "External memory provider requested in strict mode but unavailable.",
                "evidence": ["memory_provider", "provider:external", "status:blocked"],
            }
        return {
            "provider": "local",
            "requested_provider": requested,
            "status": "fallback",
            "fallback_provider": "local",
            "rationale": "External memory provider unavailable; using local KH MemoryStore.",
            "evidence": ["memory_provider", "provider:local", "status:fallback"],
        }
    if requested == "hybrid" and not external_available:
        return {
            "provider": "local",
            "requested_provider": requested,
            "status": "fallback",
            "fallback_provider": "local",
            "rationale": "Hybrid memory requested, external provider unavailable; using local KH MemoryStore.",
            "evidence": ["memory_provider", "provider:local", "status:fallback"],
        }
    return {
        "provider": requested,
        "requested_provider": requested,
        "status": "selected",
        "fallback_provider": "",
        "rationale": "Use the selected KH-compatible memory provider policy.",
        "evidence": ["memory_provider", f"provider:{requested}", "status:selected"],
    }


def build_active_memory_preflight(
    project_dir: str,
    metadata: Dict[str, Any] | None,
    objective: str = "",
) -> Dict[str, Any]:
    """Run KH's OpenClaw-style active recall before implementation or response work."""
    metadata = metadata or {}
    provider = resolve_memory_provider(metadata)
    if provider["status"] == "blocked":
        return {
            "status": "blocked",
            "provider": provider,
            "evidence": ["memory-state-harness", "active_memory_preflight"],
        }
    if provider["provider"] == "passthrough" or metadata.get("active_memory_preflight") is False:
        return {
            "status": "skipped_with_rationale",
            "provider": provider,
            "rationale": "active memory preflight disabled by provider or metadata.",
            "evidence": ["memory-state-harness"],
        }

    scope = _memory_scope(project_dir, metadata)
    store = MemoryStore(str(MemoryScopeResolver.storage_path(scope)), scope)
    query = _memory_query(metadata, objective)
    max_items = int(metadata.get("memory_max_items", metadata.get("session_context_max_items", 10)))
    max_chars = int(metadata.get("memory_prompt_max_chars", 8_000))
    memory_context = store.build_context(limit=max_items)
    memory_recall = store.search_records(query=query, limit=max_items)
    prompt_snapshot = store.write_prompt_memory_snapshot(
        query=query,
        max_records=max_items,
        max_chars=max_chars,
    )
    event = store.append_event(
        "active_memory_preflight",
        {
            "query": query,
            "record_count": memory_context.get("record_count", 0),
            "recall_count": len(memory_recall.get("records", [])),
            "prompt_snapshot": prompt_snapshot.get("paths", {}),
        },
    )
    return {
        "status": "applied",
        "provider": provider,
        "memory_scope": scope.to_dict(),
        "memory_context": memory_context,
        "memory_recall": memory_recall,
        "prompt_memory": {
            "paths": prompt_snapshot.get("paths", {}),
            "record_count": prompt_snapshot.get("record_count", 0),
            "truncated": prompt_snapshot.get("truncated", False),
            "snapshot_strategy": prompt_snapshot.get("snapshot_strategy", ""),
        },
        "event": event,
        "evidence": [
            "memory-state-harness",
            "active_memory_preflight",
            "memory_recall",
            "bounded_prompt_memory",
        ],
    }


def write_pre_compaction_memory_flush(
    project_dir: str,
    metadata: Dict[str, Any] | None,
    notes: str,
    objective: str = "",
) -> Dict[str, Any]:
    """Persist important notes before host context compaction can erase them."""
    metadata = metadata or {}
    notes = str(notes or "").strip()
    provider = resolve_memory_provider(metadata)
    if not notes:
        return {
            "status": "considered_not_needed",
            "provider": provider,
            "recorded_count": 0,
            "evidence": ["memory-state-harness", "pre_compaction_memory_flush"],
        }
    if provider["status"] == "blocked":
        return {
            "status": "blocked",
            "provider": provider,
            "recorded_count": 0,
            "evidence": ["memory-state-harness", "pre_compaction_memory_flush"],
        }
    if provider["provider"] == "passthrough":
        return {
            "status": "skipped_with_rationale",
            "provider": provider,
            "recorded_count": 0,
            "rationale": "memory provider passthrough selected",
            "evidence": ["memory-state-harness", "pre_compaction_memory_flush"],
        }

    scope = _memory_scope(project_dir, metadata)
    store = MemoryStore(str(MemoryScopeResolver.storage_path(scope)), scope)
    record = MemoryRecord(
        record_id=_stable_memory_id("compaction", scope.namespace, objective, notes),
        kind="compaction-flush",
        content=notes,
        scope=scope.kind,
        source=str(metadata.get("memory_flush_source", "pre_compaction_memory_flush")),
        confidence=str(metadata.get("memory_flush_confidence", "medium")),
        metadata={
            "objective": objective,
            "promotion": "durable_record" if metadata.get("memory_flush_promote") else "candidate",
            "provider": provider,
        },
    )
    try:
        if metadata.get("memory_flush_promote"):
            saved = store.save_record(record).to_dict()
            promotion = "durable_record"
            status = "record_saved"
        else:
            saved = store.append_candidate(record)
            promotion = "candidate"
            status = "candidate_recorded" if saved.get("candidate_status") != "duplicate" else "duplicate_skipped"
    except ValueError as exc:
        return {
            "status": "blocked",
            "provider": provider,
            "memory_scope": scope.to_dict(),
            "blocked": {"error_type": type(exc).__name__, "message": str(exc)},
            "recorded_count": 0,
            "evidence": ["memory-state-harness", "pre_compaction_memory_flush"],
        }

    prompt_snapshot = store.write_prompt_memory_snapshot(
        query=objective or notes[:200],
        max_records=int(metadata.get("memory_max_items", 10)),
        max_chars=int(metadata.get("memory_prompt_max_chars", 8_000)),
    )
    event = store.append_event(
        "pre_compaction_memory_flush",
        {
            "record_id": record.record_id,
            "promotion": promotion,
            "status": status,
            "prompt_snapshot": prompt_snapshot.get("paths", {}),
        },
        record_id=record.record_id,
    )
    return {
        "status": status,
        "provider": provider,
        "memory_scope": scope.to_dict(),
        "record": saved,
        "recorded_count": 1 if status != "duplicate_skipped" else 0,
        "promotion": promotion,
        "prompt_memory": {
            "paths": prompt_snapshot.get("paths", {}),
            "truncated": prompt_snapshot.get("truncated", False),
        },
        "event": event,
        "evidence": [
            "memory-state-harness",
            "pre_compaction_memory_flush",
            "bounded_prompt_memory",
        ],
    }


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


def _memory_query(metadata: Dict[str, Any], objective: str) -> str:
    return " ".join(
        str(part)
        for part in [
            objective,
            metadata.get("objective", ""),
            metadata.get("request", ""),
            metadata.get("prompt", ""),
            metadata.get("active_task", ""),
            metadata.get("next_task", ""),
        ]
        if part
    ).strip()


def _stable_memory_id(*parts: str) -> str:
    digest = hashlib.sha256("\n".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:16]
    return f"memory-{digest}"
