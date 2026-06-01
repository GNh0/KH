import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.contracts import MemoryRecord
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryStore
from src.platforms.codex_thread_registry import CodexThreadRegistry


class CodexThreadRegistryTests(unittest.TestCase):
    def test_registry_reads_active_and_archived_thread_ids_from_codex_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "state.sqlite"
            connection = sqlite3.connect(db_path)
            connection.execute(
                "create table threads (id text primary key, archived integer not null default 0, archived_at integer)"
            )
            connection.execute("insert into threads (id, archived, archived_at) values ('thread-active', 0, null)")
            connection.execute("insert into threads (id, archived, archived_at) values ('thread-archived', 1, 1770000000)")
            connection.commit()
            connection.close()

            registry = CodexThreadRegistry(db_path)
            states = registry.list_thread_states()

            self.assertTrue(registry.available())
            self.assertEqual(
                {state.thread_id: state.status for state in states},
                {
                    "thread-active": "active",
                    "thread-archived": "archived",
                },
            )
            self.assertEqual(registry.live_thread_ids(), ["thread-active"])
            self.assertEqual(registry.archived_thread_ids(), ["thread-archived"])

    def test_registry_reports_unavailable_when_sqlite_file_is_missing(self):
        registry = CodexThreadRegistry("missing.sqlite")

        self.assertFalse(registry.available())
        self.assertEqual(registry.describe()["status"], "unavailable")

    def test_registry_can_drive_conversation_memory_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "state.sqlite"
            connection = sqlite3.connect(db_path)
            connection.execute(
                "create table threads (id text primary key, archived integer not null default 0, archived_at integer)"
            )
            connection.execute("insert into threads (id, archived, archived_at) values ('thread-active', 0, null)")
            connection.execute("insert into threads (id, archived, archived_at) values ('thread-archived', 1, 1770000000)")
            connection.commit()
            connection.close()

            for thread_id in ["thread-active", "thread-archived", "thread-deleted"]:
                scope = MemoryScopeResolver.conversation_scope(thread_id, root)
                MemoryStore(MemoryScopeResolver.storage_path(scope), scope).save_record(
                    MemoryRecord(
                        record_id=f"{thread_id}-record",
                        kind="decision",
                        content=f"{thread_id} memory",
                        scope=scope.kind,
                        source="test",
                    )
                )

            summary = CodexThreadRegistry(db_path).cleanup_conversation_memories(root)

            self.assertEqual(summary["active"], ["thread-active"])
            self.assertEqual(summary["archived"], ["thread-archived"])
            self.assertEqual(summary["quarantined"], ["thread-deleted"])


if __name__ == "__main__":
    unittest.main()
