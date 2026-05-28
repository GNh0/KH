import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class CodexThreadState:
    thread_id: str
    status: str
    archived_at: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "thread_id": self.thread_id,
            "status": self.status,
            "archived_at": self.archived_at,
        }


class CodexThreadRegistry:
    def __init__(self, db_path: str = ""):
        self.db_path = Path(db_path).resolve() if db_path else Path.home() / ".codex" / "state_5.sqlite"

    def available(self) -> bool:
        if not self.db_path.exists():
            return False
        try:
            with closing(sqlite3.connect(self.db_path)) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("pragma table_info(threads)")
                }
            return {"id", "archived"}.issubset(columns)
        except sqlite3.Error:
            return False

    def describe(self) -> Dict[str, object]:
        if not self.available():
            return {
                "status": "unavailable",
                "db_path": str(self.db_path),
                "delete_detection": "requires host event or absence from thread registry",
            }
        states = self.list_thread_states()
        return {
            "status": "available",
            "db_path": str(self.db_path),
            "thread_count": len(states),
            "active_thread_count": len([state for state in states if state.status == "active"]),
            "archived_thread_count": len([state for state in states if state.status == "archived"]),
            "archive_detection": "threads.archived",
            "delete_detection": "absence from threads registry",
        }

    def list_thread_states(self) -> List[CodexThreadState]:
        if not self.available():
            return []
        with closing(sqlite3.connect(self.db_path)) as connection:
            rows = connection.execute(
                "select id, archived, archived_at from threads order by id"
            ).fetchall()
        return [
            CodexThreadState(
                thread_id=row[0],
                status="archived" if int(row[1] or 0) else "active",
                archived_at=row[2],
            )
            for row in rows
        ]

    def live_thread_ids(self) -> List[str]:
        return [
            state.thread_id
            for state in self.list_thread_states()
            if state.status == "active"
        ]

    def archived_thread_ids(self) -> List[str]:
        return [
            state.thread_id
            for state in self.list_thread_states()
            if state.status == "archived"
        ]

    def cleanup_conversation_memories(self, conversation_memory_root: str, quarantine: bool = True) -> Dict[str, List[str]]:
        from src.orchestration.memory_store import MemoryCleanupPolicy

        return MemoryCleanupPolicy(conversation_memory_root).cleanup_conversation_memories(
            live_thread_ids=self.live_thread_ids(),
            archived_thread_ids=self.archived_thread_ids(),
            quarantine=quarantine,
        )
