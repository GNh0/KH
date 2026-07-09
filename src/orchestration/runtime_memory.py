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


def build_explicit_cross_scope_memory_import(
    project_dir: str,
    metadata: Dict[str, Any] | None,
    source_scope: MemoryScope | Dict[str, Any] | None = None,
    query: str = "",
) -> Dict[str, Any]:
    """Read another scope only when the user explicitly requested that source.

    Cross-scope recall is intentionally separate from active memory preflight.
    The default result is read-only external context; importing into the current
    scope requires explicit approval and defaults to candidates, not durable
    records.
    """
    metadata = metadata or {}
    provider = resolve_memory_provider(metadata)
    requested = bool(metadata.get("cross_scope_memory_import"))
    if not requested:
        return {
            "status": "skipped_with_rationale",
            "application_status": "not_requested",
            "provider": provider,
            "rationale": "cross-scope memory import requires metadata.cross_scope_memory_import=true",
            "evidence": ["memory-state-harness"],
        }
    if provider["status"] == "blocked":
        return {
            "status": "blocked",
            "application_status": "not_applied",
            "provider": provider,
            "evidence": ["memory-state-harness", "explicit_cross_scope_memory_import"],
        }
    if provider["provider"] == "passthrough":
        return {
            "status": "skipped_with_rationale",
            "application_status": "not_applied",
            "provider": provider,
            "rationale": "memory provider passthrough selected",
            "evidence": ["memory-state-harness", "explicit_cross_scope_memory_import"],
        }

    try:
        resolved_source_scope = _source_memory_scope(source_scope, metadata)
    except ValueError as exc:
        return {
            "status": "blocked",
            "application_status": "not_applied",
            "provider": provider,
            "blocked": {"error_type": type(exc).__name__, "message": str(exc)},
            "evidence": ["memory-state-harness", "explicit_cross_scope_memory_import"],
        }
    if resolved_source_scope.status == "deleted":
        return {
            "status": "blocked",
            "application_status": "not_applied",
            "provider": provider,
            "source_scope": resolved_source_scope.to_dict(),
            "blocked": {"error_type": "DeletedSourceScope", "message": "source memory scope is deleted"},
            "evidence": ["memory-state-harness", "explicit_cross_scope_memory_import"],
        }

    target_scope = _memory_scope(project_dir, metadata)
    target_store = MemoryStore(str(MemoryScopeResolver.storage_path(target_scope)), target_scope)
    source_store = MemoryStore(str(MemoryScopeResolver.storage_path(resolved_source_scope)), resolved_source_scope)
    max_items = int(metadata.get("memory_import_max_items", metadata.get("memory_max_items", 10)))
    search_query = query or _memory_query(metadata, "")
    external_context = source_store.search_records(query=search_query, limit=max_items)
    external_context["source_scope"] = resolved_source_scope.to_dict()
    external_context["target_scope"] = target_scope.to_dict()

    approved = bool(metadata.get("memory_import_approved"))
    should_apply = bool(metadata.get("memory_import_apply"))
    promote = bool(metadata.get("memory_import_promote"))
    if not approved:
        event = target_store.append_event(
            "cross_scope_memory_import_reviewed",
            {
                "approval_status": "approval_required",
                "application_status": "read_only_external_context",
                "source_scope": resolved_source_scope.to_dict(),
                "query": search_query,
                "record_count": len(external_context.get("records", [])),
            },
        )
        return {
            "status": "approval_required",
            "application_status": "read_only_external_context",
            "provider": provider,
            "source_scope": resolved_source_scope.to_dict(),
            "target_scope": target_scope.to_dict(),
            "external_context": external_context,
            "recorded_count": 0,
            "promotion": "external_context_only",
            "approval": {
                "required": True,
                "approved": False,
                "rationale": "Source memory was recalled read-only; current scope was not modified.",
            },
            "event": event,
            "evidence": [
                "memory-state-harness",
                "explicit_cross_scope_memory_import",
                "read_only_external_context",
            ],
        }

    if not should_apply:
        event = target_store.append_event(
            "cross_scope_memory_import_reviewed",
            {
                "approval_status": "approved_read_only",
                "application_status": "read_only_external_context",
                "source_scope": resolved_source_scope.to_dict(),
                "query": search_query,
                "record_count": len(external_context.get("records", [])),
            },
        )
        return {
            "status": "approved_read_only",
            "application_status": "read_only_external_context",
            "provider": provider,
            "source_scope": resolved_source_scope.to_dict(),
            "target_scope": target_scope.to_dict(),
            "external_context": external_context,
            "recorded_count": 0,
            "promotion": "external_context_only",
            "approval": {
                "required": True,
                "approved": True,
                "rationale": "User approved reading the source, but import_apply=false kept it out of current memory.",
            },
            "event": event,
            "evidence": [
                "memory-state-harness",
                "explicit_cross_scope_memory_import",
                "read_only_external_context",
            ],
        }

    imported: List[Dict[str, Any]] = []
    blocked: List[Dict[str, str]] = []
    for source_record in external_context.get("records", []):
        record = _import_record_from_external_context(
            target_scope=target_scope,
            source_scope=resolved_source_scope,
            source_record=source_record,
            query=search_query,
            promotion="durable_record" if promote else "candidate",
        )
        try:
            if promote:
                imported.append(target_store.save_record(record).to_dict())
            else:
                imported.append(target_store.append_candidate(record))
        except ValueError as exc:
            blocked.append(
                {
                    "record_id": record.record_id,
                    "source_record_id": str(source_record.get("record_id", "")),
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    status = "records_imported" if promote and imported else "candidates_recorded" if imported else "no_records"
    if blocked and not imported:
        status = "blocked"
    event = target_store.append_event(
        "cross_scope_memory_import_applied",
        {
            "approval_status": "approved",
            "application_status": "durable_imported" if promote else "candidate_imported",
            "source_scope": resolved_source_scope.to_dict(),
            "query": search_query,
            "recorded_count": len(imported),
            "blocked_count": len(blocked),
            "promotion": "durable_record" if promote else "candidate",
        },
    )
    return {
        "status": status,
        "application_status": "durable_imported" if promote else "candidate_imported",
        "provider": provider,
        "source_scope": resolved_source_scope.to_dict(),
        "target_scope": target_scope.to_dict(),
        "external_context": external_context,
        "recorded": imported,
        "recorded_count": len(imported),
        "blocked": blocked,
        "blocked_count": len(blocked),
        "promotion": "durable_record" if promote else "candidate",
        "approval": {
            "required": True,
            "approved": True,
            "rationale": "Explicit cross-scope import was approved by the caller.",
        },
        "event": event,
        "evidence": [
            "memory-state-harness",
            "explicit_cross_scope_memory_import",
            "memory_import_applied",
        ],
    }


def build_parent_scope_memory_access(
    project_dir: str,
    metadata: Dict[str, Any] | None,
    query: str = "",
) -> Dict[str, Any]:
    """Request read-only access from the immediate parent memory scope.

    Same-level scopes never read each other directly. A nested subagent can
    request its parent scope; access is read-only until the parent/controller
    approves it through metadata.parent_memory_access_approved=true.
    """
    metadata = metadata or {}
    provider = resolve_memory_provider(metadata)
    child_scope = _memory_scope(project_dir, metadata)
    parent_scope = _parent_memory_scope(child_scope, metadata)
    child_store = MemoryStore(str(MemoryScopeResolver.storage_path(child_scope)), child_scope)
    if parent_scope is None:
        return {
            "status": "skipped_with_rationale",
            "application_status": "no_parent_scope",
            "provider": provider,
            "child_scope": child_scope.to_dict(),
            "evidence": ["memory-state-harness", "parent_memory_access"],
        }
    if provider["status"] == "blocked" or provider["provider"] == "passthrough":
        return {
            "status": "blocked" if provider["status"] == "blocked" else "skipped_with_rationale",
            "application_status": "not_applied",
            "provider": provider,
            "child_scope": child_scope.to_dict(),
            "parent_scope": parent_scope.to_dict(),
            "evidence": ["memory-state-harness", "parent_memory_access"],
        }

    search_query = query or _memory_query(metadata, "")
    if not metadata.get("parent_memory_access_approved"):
        event = child_store.append_event(
            "parent_memory_access_requested",
            {
                "child_scope": child_scope.to_dict(),
                "parent_scope": parent_scope.to_dict(),
                "query": search_query,
                "approval_status": "approval_required",
                "sharing_rule": "same-level scopes isolated; parent approval required",
            },
        )
        return {
            "status": "approval_required",
            "application_status": "read_blocked_until_parent_approval",
            "provider": provider,
            "child_scope": child_scope.to_dict(),
            "parent_scope": parent_scope.to_dict(),
            "external_context": {"records": [], "search_strategy": "parent_approval_required"},
            "approval": {"required": True, "approved": False},
            "event": event,
            "evidence": ["memory-state-harness", "parent_memory_access_requested"],
        }

    parent_store = MemoryStore(str(MemoryScopeResolver.storage_path(parent_scope)), parent_scope)
    external_context = parent_store.search_records(
        query=search_query,
        limit=int(metadata.get("parent_memory_max_items", metadata.get("memory_max_items", 10))),
    )
    event = child_store.append_event(
        "parent_memory_access_granted",
        {
            "child_scope": child_scope.to_dict(),
            "parent_scope": parent_scope.to_dict(),
            "query": search_query,
            "record_count": len(external_context.get("records", [])),
            "application_status": "read_only_parent_context",
        },
    )
    return {
        "status": "approved_read_only",
        "application_status": "read_only_parent_context",
        "provider": provider,
        "child_scope": child_scope.to_dict(),
        "parent_scope": parent_scope.to_dict(),
        "external_context": external_context,
        "approval": {"required": True, "approved": True},
        "event": event,
        "evidence": ["memory-state-harness", "parent_memory_access", "read_only_parent_context"],
    }


def submit_parent_memory_candidates(
    project_dir: str,
    metadata: Dict[str, Any] | None,
    candidates: Iterable[MemoryRecord | Dict[str, Any]],
) -> Dict[str, Any]:
    """Submit child-scope memory candidates to the immediate parent scope.

    The default is parent-scope candidates only. Durable parent records require
    metadata.parent_memory_promote_durable=true after approval.
    """
    metadata = metadata or {}
    provider = resolve_memory_provider(metadata)
    child_scope = _memory_scope(project_dir, metadata)
    parent_scope = _parent_memory_scope(child_scope, metadata)
    child_store = MemoryStore(str(MemoryScopeResolver.storage_path(child_scope)), child_scope)
    candidate_records = [_as_memory_record(item) for item in candidates or []]
    if parent_scope is None:
        return {
            "status": "skipped_with_rationale",
            "application_status": "no_parent_scope",
            "provider": provider,
            "child_scope": child_scope.to_dict(),
            "candidate_count": len(candidate_records),
            "recorded_count": 0,
            "evidence": ["memory-state-harness", "parent_memory_candidates"],
        }
    if not candidate_records:
        return {
            "status": "considered_not_needed",
            "application_status": "no_candidates",
            "provider": provider,
            "child_scope": child_scope.to_dict(),
            "parent_scope": parent_scope.to_dict(),
            "candidate_count": 0,
            "recorded_count": 0,
            "evidence": ["memory-state-harness", "parent_memory_candidates"],
        }
    if provider["status"] == "blocked" or provider["provider"] == "passthrough":
        return {
            "status": "blocked" if provider["status"] == "blocked" else "skipped_with_rationale",
            "application_status": "not_applied",
            "provider": provider,
            "child_scope": child_scope.to_dict(),
            "parent_scope": parent_scope.to_dict(),
            "candidate_count": len(candidate_records),
            "recorded_count": 0,
            "evidence": ["memory-state-harness", "parent_memory_candidates"],
        }

    if not metadata.get("parent_memory_candidates_approved"):
        event = child_store.append_event(
            "parent_memory_candidates_requested",
            {
                "child_scope": child_scope.to_dict(),
                "parent_scope": parent_scope.to_dict(),
                "candidate_count": len(candidate_records),
                "approval_status": "approval_required",
                "sharing_rule": "child candidates require parent/controller acceptance",
            },
        )
        return {
            "status": "approval_required",
            "application_status": "not_applied",
            "provider": provider,
            "child_scope": child_scope.to_dict(),
            "parent_scope": parent_scope.to_dict(),
            "candidate_count": len(candidate_records),
            "recorded_count": 0,
            "approval": {"required": True, "approved": False},
            "event": event,
            "evidence": ["memory-state-harness", "parent_memory_candidates_requested"],
        }

    parent_store = MemoryStore(str(MemoryScopeResolver.storage_path(parent_scope)), parent_scope)
    promote_durable = bool(metadata.get("parent_memory_promote_durable"))
    recorded: List[Dict[str, Any]] = []
    blocked: List[Dict[str, str]] = []
    for candidate in candidate_records:
        parent_record = MemoryRecord(
            record_id=_stable_memory_id(
                "parent",
                parent_scope.namespace,
                child_scope.namespace,
                candidate.record_id,
                candidate.content,
            ),
            kind=candidate.kind or "parent-memory-candidate",
            content=candidate.content,
            scope=parent_scope.kind,
            source="parent_memory_candidates",
            confidence=candidate.confidence,
            metadata={
                **dict(candidate.metadata),
                "child_scope": child_scope.to_dict(),
                "parent_scope": parent_scope.to_dict(),
                "origin_record_id": candidate.record_id,
                "origin_scope": candidate.scope,
                "promotion": "durable_record" if promote_durable else "candidate",
            },
        )
        try:
            if promote_durable:
                recorded.append(parent_store.save_record(parent_record).to_dict())
            else:
                recorded.append(parent_store.append_candidate(parent_record))
        except ValueError as exc:
            blocked.append(
                {
                    "record_id": parent_record.record_id,
                    "origin_record_id": candidate.record_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    event = child_store.append_event(
        "parent_memory_candidates_applied",
        {
            "child_scope": child_scope.to_dict(),
            "parent_scope": parent_scope.to_dict(),
            "recorded_count": len(recorded),
            "blocked_count": len(blocked),
            "promotion": "durable_record" if promote_durable else "candidate",
        },
    )
    status = "records_promoted" if promote_durable and recorded else "candidates_recorded" if recorded else "blocked"
    return {
        "status": status,
        "application_status": "parent_records_promoted" if promote_durable else "parent_candidates_recorded",
        "provider": provider,
        "child_scope": child_scope.to_dict(),
        "parent_scope": parent_scope.to_dict(),
        "candidate_count": len(candidate_records),
        "recorded_count": len(recorded),
        "blocked_count": len(blocked),
        "recorded": recorded,
        "blocked": blocked,
        "promotion": "durable_record" if promote_durable else "candidate",
        "approval": {"required": True, "approved": True},
        "event": event,
        "evidence": ["memory-state-harness", "parent_memory_candidates", "parent_scope_acceptance"],
    }


def record_workflow_memory_candidates(
    project_dir: str,
    metadata: Dict[str, Any] | None,
    candidates: Iterable[MemoryRecord],
) -> Dict[str, Any]:
    """Persist workflow memory candidates without promoting them to durable records."""
    metadata = metadata or {}
    provider = resolve_memory_provider(metadata)
    candidates = list(candidates or [])
    if not candidates:
        return {
            "status": "considered_not_needed",
            "provider": provider,
            "candidate_count": 0,
            "recorded_count": 0,
            "skipped_count": 0,
            "blocked_count": 0,
            "evidence": [],
        }
    if provider["status"] == "blocked":
        return {
            "status": "blocked",
            "provider": provider,
            "candidate_count": len(candidates),
            "recorded_count": 0,
            "skipped_count": 0,
            "blocked_count": len(candidates),
            "blocked": [
                {
                    "record_id": _candidate_record_id(candidate),
                    "error_type": "MemoryProviderBlocked",
                    "message": provider["rationale"],
                }
                for candidate in candidates
            ],
            "rationale": provider["rationale"],
            "promotion": "blocked",
            "evidence": ["memory-state-harness", "memory_provider_policy"],
        }
    if provider["provider"] == "passthrough":
        return {
            "status": "skipped_with_rationale",
            "provider": provider,
            "candidate_count": len(candidates),
            "recorded_count": 0,
            "skipped_count": len(candidates),
            "blocked_count": 0,
            "rationale": "memory provider passthrough selected; workflow memory candidates were not written",
            "promotion": "passthrough",
            "evidence": ["memory-state-harness", "memory_provider_policy"],
        }
    if metadata.get("memory_candidates_auto") is False:
        return {
            "status": "skipped_with_rationale",
            "provider": provider,
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
    evidence = ["memory-state-harness"]
    if status in {"candidates_recorded", "already_recorded"}:
        evidence.append("memory_candidates_recorded")
    return {
        "status": status,
        "provider": provider,
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
        "evidence": evidence,
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


def _parent_memory_scope(scope: MemoryScope, metadata: Dict[str, Any]) -> MemoryScope | None:
    parent = MemoryScopeResolver.parent_scope(scope)
    if parent is None:
        return None
    parent_root = str(metadata.get("parent_memory_root", "")).strip()
    if parent_root:
        return replace(parent, root_path=str(Path(parent_root).resolve()))
    lineage_depth = int(scope.metadata.get("lineage_depth") or 0)
    if scope.root_path and lineage_depth > 0:
        root_path = Path(scope.root_path).resolve()
        if lineage_depth == 1:
            return replace(parent, root_path=str(root_path.parents[1]))
        return replace(parent, root_path=str(root_path.parent))
    return parent


def _as_memory_record(item: MemoryRecord | Dict[str, Any]) -> MemoryRecord:
    if isinstance(item, MemoryRecord):
        return item
    if isinstance(item, dict):
        return MemoryRecord.from_dict(item)
    raise TypeError("memory candidate must be MemoryRecord or dict")


def _candidate_record_id(item: MemoryRecord | Dict[str, Any]) -> str:
    if isinstance(item, MemoryRecord):
        return str(item.record_id)
    if isinstance(item, dict):
        return str(item.get("record_id", ""))
    return ""


def _source_memory_scope(
    source_scope: MemoryScope | Dict[str, Any] | None,
    metadata: Dict[str, Any],
) -> MemoryScope:
    if isinstance(source_scope, MemoryScope):
        scope = source_scope
    elif isinstance(source_scope, dict):
        scope = MemoryScope.from_dict(source_scope)
    else:
        source_project_dir = str(metadata.get("memory_import_source_project_dir", "")).strip()
        source_thread_id = metadata.get("memory_import_source_thread_id")
        source_conversation_root = str(
            metadata.get("memory_import_conversation_root", metadata.get("conversation_memory_root", ""))
        )
        if source_project_dir:
            scope = MemoryScopeResolver.project_scope(
                project_dir=source_project_dir,
                thread_id=source_thread_id,
                project_id=str(metadata.get("memory_import_source_project_id", "")),
            )
        elif source_thread_id:
            scope = MemoryScopeResolver.conversation_scope(
                thread_id=str(source_thread_id),
                conversation_memory_root=source_conversation_root,
            )
        else:
            raise ValueError("cross-scope import requires source_scope or memory_import_source_project_dir/thread_id")
    source_root = str(metadata.get("memory_import_source_root", "")).strip()
    if source_root:
        scope = replace(scope, root_path=str(Path(source_root).resolve()))
    if not scope.root_path:
        raise ValueError("cross-scope import source scope requires root_path")
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


def _import_record_from_external_context(
    target_scope: MemoryScope,
    source_scope: MemoryScope,
    source_record: Dict[str, Any],
    query: str,
    promotion: str,
) -> MemoryRecord:
    content = str(source_record.get("content", ""))
    source_record_id = str(source_record.get("record_id", ""))
    return MemoryRecord(
        record_id=_stable_memory_id(
            "import",
            target_scope.namespace,
            source_scope.namespace,
            source_record_id,
            content,
        ),
        kind="memory-import",
        content=content,
        scope=target_scope.kind,
        source="explicit_cross_scope_memory_import",
        confidence=str(source_record.get("confidence", "medium")),
        metadata={
            "source_scope": source_scope.to_dict(),
            "source_record_id": source_record_id,
            "source_kind": source_record.get("kind", ""),
            "source_record_scope": source_record.get("scope", ""),
            "source_record_updated_at": source_record.get("updated_at", ""),
            "query": query,
            "import_status": promotion,
            "source_score": source_record.get("score", 0),
        },
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
