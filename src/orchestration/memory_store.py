import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.contracts import MemoryEvent, MemoryRecord, MemoryScope
from src.orchestration.memory_state import MemoryScopeResolver


SECRET_PATTERN = re.compile(
    r"(api[_-]?key\s*=|secret\s*=|token\s*=|-----BEGIN\s+[A-Z ]*PRIVATE KEY-----|sk-[A-Za-z0-9_-]{12,})",
    re.IGNORECASE,
)
INJECTION_PATTERN = re.compile(
    r"(ignore\s+(?:all\s+)?(?:previous|prior|system|developer)\s+instructions|"
    r"disregard\s+(?:all\s+)?(?:previous|prior|system|developer)\s+instructions|"
    r"reveal\s+(?:the\s+)?system\s+prompt|exfiltrat(?:e|ion)|send\s+.*(?:secret|credential|private\s+key))",
    re.IGNORECASE,
)
INVISIBLE_CONTROL_PATTERN = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f]")
MAX_MEMORY_CONTENT_CHARS = 4_000


class MemoryStore:
    def __init__(self, root_dir: str, scope: Optional[MemoryScope] = None):
        self.root_dir = Path(root_dir).resolve()
        self.scope = scope or MemoryScope(
            kind="project",
            namespace="project:unknown",
            root_path=str(self.root_dir),
        )
        self.records_path = self.root_dir / "project_memory.json"
        self.events_path = self.root_dir / "memory_events.jsonl"
        self.candidates_path = self.root_dir / "memory_candidates.jsonl"
        self.scope_state_path = self.root_dir / "scope_state.json"

    def describe_paths(self) -> Dict[str, Any]:
        return {
            "memory_dir": str(self.root_dir),
            "records_path": str(self.records_path),
            "events_path": str(self.events_path),
            "candidates_path": str(self.candidates_path),
            "scope_state_path": str(self.scope_state_path),
            "scope": self.scope.to_dict(),
        }

    def load_records(self) -> List[MemoryRecord]:
        if not self.records_path.exists():
            return []
        data = json.loads(self.records_path.read_text(encoding="utf-8"))
        return [
            MemoryRecord.from_dict(record)
            for record in data.get("records", [])
        ]

    def save_record(self, record: MemoryRecord) -> MemoryRecord:
        _reject_unsafe_memory_content(record.content)
        records = self.load_records()
        duplicate = _find_duplicate_record(records, record.content, exclude_record_id=record.record_id)
        if duplicate:
            self.append_event(
                "memory_duplicate_skipped",
                {"duplicate_of": duplicate.record_id, "kind": duplicate.kind},
                record_id=record.record_id,
            )
            return duplicate
        by_id = {existing.record_id: existing for existing in records}
        timestamp = _utc_now()
        record_to_save = MemoryRecord(
            record_id=record.record_id,
            kind=record.kind,
            content=record.content,
            scope=record.scope,
            source=record.source,
            confidence=record.confidence,
            created_at=record.created_at or timestamp,
            updated_at=timestamp,
            metadata=dict(record.metadata),
        )
        by_id[record.record_id] = record_to_save
        self._write_records(list(by_id.values()))
        self.append_event(
            "memory_saved",
            {"kind": record.kind, "confidence": record.confidence},
            record_id=record.record_id,
        )
        return record_to_save

    def build_context(self, limit: int = 20) -> Dict[str, Any]:
        records = self.load_records()
        selected_records = records[-limit:] if limit >= 0 else records
        return {
            "scope": self.scope.to_dict(),
            "record_count": len(records),
            "records": [record.to_dict() for record in selected_records],
        }

    def search_records(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Return bounded keyword-ranked memory records without external vector dependencies."""
        terms = _search_terms(query)
        records = self.load_records()
        if not terms:
            selected = records[-limit:] if limit >= 0 else records
            return {
                "scope": self.scope.to_dict(),
                "query": query,
                "record_count": len(records),
                "records": [
                    {**record.to_dict(), "score": 0}
                    for record in selected
                ],
                "search_strategy": "latest",
            }

        scored = []
        for record in records:
            score = _record_score(record, terms)
            if score:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].updated_at or item[1].created_at, item[1].record_id))
        selected_scored = scored[:limit] if limit >= 0 else scored
        return {
            "scope": self.scope.to_dict(),
            "query": query,
            "record_count": len(records),
            "records": [
                {**record.to_dict(), "score": score}
                for score, record in selected_scored
            ],
            "search_strategy": "keyword_ranked",
        }

    def append_candidate(self, record: MemoryRecord) -> Dict[str, Any]:
        _reject_unsafe_memory_content(record.content)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        duplicate_record = _find_duplicate_record(self.load_records(), record.content)
        duplicate_candidate = _find_duplicate_candidate(self.read_candidates(), record.content)
        if duplicate_record or duplicate_candidate:
            duplicate_id = (
                duplicate_record.record_id
                if duplicate_record
                else str(duplicate_candidate.get("record_id", ""))
            )
            self.append_event(
                "memory_candidate_duplicate_skipped",
                {"duplicate_of": duplicate_id, "kind": record.kind},
                record_id=record.record_id,
            )
            candidate = record.to_dict()
            candidate["candidate_status"] = "duplicate"
            candidate["duplicate_of"] = duplicate_id
            return candidate
        candidate = record.to_dict()
        candidate["candidate_status"] = "pending"
        candidate["created_at"] = candidate.get("created_at") or _utc_now()
        with self.candidates_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(candidate, sort_keys=True))
            handle.write("\n")
        self.append_event(
            "memory_candidate_added",
            {"kind": record.kind, "confidence": record.confidence},
            record_id=record.record_id,
        )
        return candidate

    def read_candidates(self) -> List[Dict[str, Any]]:
        return _read_jsonl(self.candidates_path)

    def append_event(self, event_type: str, payload: Dict[str, Any], record_id: str = "") -> Dict[str, Any]:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._write_scope_state()
        event = MemoryEvent(
            event_type=event_type,
            record_id=record_id,
            scope=self.scope.kind,
            payload=json.loads(json.dumps(payload)),
            timestamp=_utc_now(),
            metadata={"namespace": self.scope.namespace},
        )
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True))
            handle.write("\n")
        return event.to_dict()

    def read_events(self) -> List[Dict[str, Any]]:
        return _read_jsonl(self.events_path)

    def trim_events(self, max_events: int) -> Dict[str, int]:
        if max_events < 0:
            raise ValueError("max_events must be >= 0")
        events = self.read_events()
        kept = events[-max_events:] if max_events else []
        self.root_dir.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("w", encoding="utf-8") as handle:
            for event in kept:
                handle.write(json.dumps(event, sort_keys=True))
                handle.write("\n")
        return {"before": len(events), "after": len(kept), "deleted": len(events) - len(kept)}

    def mark_archived(self) -> Dict[str, Any]:
        self.scope = MemoryScope(
            kind=self.scope.kind,
            namespace=self.scope.namespace,
            project_id=self.scope.project_id,
            thread_id=self.scope.thread_id,
            root_path=self.scope.root_path,
            status="archived",
            metadata=dict(self.scope.metadata),
        )
        self._write_scope_state()
        return self.append_event("memory_scope_archived", {"thread_id": self.scope.thread_id})

    def _write_records(self, records: Iterable[MemoryRecord]) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._write_scope_state()
        payload = {
            "schema_version": 1,
            "scope": self.scope.to_dict(),
            "records": [record.to_dict() for record in records],
            "updated_at": _utc_now(),
        }
        self.records_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _write_scope_state(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.scope_state_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "scope": self.scope.to_dict(),
                    "updated_at": _utc_now(),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )


class MemoryCleanupPolicy:
    def __init__(self, conversation_memory_root: str):
        self.root = Path(conversation_memory_root).resolve()
        self.conversations_dir = self.root / "conversations"
        self.quarantine_dir = self.root / "_quarantine"

    def cleanup_conversation_memories(
        self,
        live_thread_ids: Iterable[str],
        archived_thread_ids: Iterable[str],
        quarantine: bool = True,
    ) -> Dict[str, List[str]]:
        live = set(live_thread_ids or [])
        archived = set(archived_thread_ids or [])
        summary = {
            "active": [],
            "archived": [],
            "quarantined": [],
            "deleted": [],
        }
        if not self.conversations_dir.exists():
            return summary

        for memory_dir in sorted(self.conversations_dir.iterdir(), key=lambda path: path.name):
            if not memory_dir.is_dir():
                continue
            thread_id = memory_dir.name
            if thread_id in live:
                summary["active"].append(thread_id)
                continue
            if thread_id in archived:
                scope = MemoryScopeResolver.conversation_scope(thread_id, str(self.root), status="archived")
                MemoryStore(memory_dir, scope).mark_archived()
                summary["archived"].append(thread_id)
                continue

            if quarantine:
                self.quarantine_dir.mkdir(parents=True, exist_ok=True)
                destination = _unique_destination(self.quarantine_dir / thread_id)
                shutil.move(str(memory_dir), str(destination))
                summary["quarantined"].append(thread_id)
            else:
                shutil.rmtree(memory_dir)
                summary["deleted"].append(thread_id)
        return summary


def _unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.name}-{index}")
        if not candidate.exists():
            return candidate
        index += 1


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _reject_secret_like_content(content: str) -> None:
    _reject_unsafe_memory_content(content)


def _reject_unsafe_memory_content(content: str) -> None:
    if len(content or "") > MAX_MEMORY_CONTENT_CHARS:
        raise ValueError("memory content exceeds maximum durable entry size")
    if INVISIBLE_CONTROL_PATTERN.search(content or ""):
        raise ValueError("memory content contains invisible control characters")
    if SECRET_PATTERN.search(content or ""):
        raise ValueError("memory content appears to contain a secret")
    if INJECTION_PATTERN.search(content or ""):
        raise ValueError("memory content appears to contain prompt-injection text")


def _find_duplicate_record(
    records: Iterable[MemoryRecord],
    content: str,
    exclude_record_id: str = "",
) -> Optional[MemoryRecord]:
    normalized = _normalize_memory_content(content)
    if not normalized:
        return None
    for record in records:
        if exclude_record_id and record.record_id == exclude_record_id:
            continue
        if _normalize_memory_content(record.content) == normalized:
            return record
    return None


def _find_duplicate_candidate(candidates: Iterable[Dict[str, Any]], content: str) -> Optional[Dict[str, Any]]:
    normalized = _normalize_memory_content(content)
    if not normalized:
        return None
    for candidate in candidates:
        if _normalize_memory_content(str(candidate.get("content", ""))) == normalized:
            return candidate
    return None


def _normalize_memory_content(content: str) -> str:
    return re.sub(r"\s+", " ", str(content or "").strip()).casefold()


def _search_terms(query: str) -> List[str]:
    return [
        term.casefold()
        for term in re.findall(r"[A-Za-z0-9_.:/-]{2,}", query or "")
    ][:12]


def _record_score(record: MemoryRecord, terms: List[str]) -> int:
    content = record.content.casefold()
    metadata = json.dumps(record.metadata, sort_keys=True).casefold()
    haystack = f"{record.kind} {record.source} {record.confidence} {metadata}".casefold()
    score = 0
    for term in terms:
        if term in content:
            score += 3
        if term in haystack:
            score += 1
    return score


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
