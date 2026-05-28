import tempfile
import unittest
from pathlib import Path

from src.contracts import MemoryRecord
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryCleanupPolicy, MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_memory_store_persists_records_candidates_and_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = MemoryScopeResolver.conversation_scope("thread-1", tmp)
            store = MemoryStore(MemoryScopeResolver.storage_path(scope), scope)
            record = MemoryRecord(
                record_id="decision-1",
                kind="decision",
                content="Use project-local memory before external providers.",
                scope=scope.kind,
                source="user-approved",
                confidence="high",
            )

            store.save_record(record)
            store.append_candidate(
                MemoryRecord(
                    record_id="candidate-1",
                    kind="lesson",
                    content="Promote only verified lessons.",
                    scope=scope.kind,
                    source="workflow",
                    confidence="medium",
                )
            )
            store.append_event("memory_context_loaded", {"records": 1})

            context = store.build_context()

            self.assertEqual(context["scope"]["kind"], "conversation")
            self.assertEqual(context["records"][0]["content"], record.content)
            saved_record = store.load_records()[0]
            self.assertEqual(saved_record.record_id, record.record_id)
            self.assertEqual(saved_record.content, record.content)
            self.assertTrue(saved_record.created_at)
            self.assertEqual(store.read_candidates()[0]["record_id"], "candidate-1")
            self.assertEqual(store.read_events()[-1]["event_type"], "memory_context_loaded")

    def test_memory_store_rejects_secret_like_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = MemoryScopeResolver.project_scope(tmp)
            store = MemoryStore(MemoryScopeResolver.storage_path(scope), scope)

            with self.assertRaises(ValueError):
                store.save_record(
                    MemoryRecord(
                        record_id="secret-1",
                        kind="decision",
                        content="api_key=should-not-be-stored",
                        scope=scope.kind,
                        source="test",
                    )
                )

    def test_trim_events_keeps_latest_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = MemoryScopeResolver.project_scope(tmp)
            store = MemoryStore(MemoryScopeResolver.storage_path(scope), scope)
            store.append_event("one", {"index": 1})
            store.append_event("two", {"index": 2})
            store.append_event("three", {"index": 3})

            summary = store.trim_events(max_events=1)
            events = store.read_events()

            self.assertEqual(summary["before"], 3)
            self.assertEqual(summary["after"], 1)
            self.assertEqual([event["event_type"] for event in events], ["three"])

    def test_cleanup_preserves_archived_threads_and_quarantines_missing_threads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for thread_id in ["thread-active", "thread-archived", "thread-gone"]:
                scope = MemoryScopeResolver.conversation_scope(thread_id, root)
                MemoryStore(MemoryScopeResolver.storage_path(scope), scope).save_record(
                    MemoryRecord(
                        record_id=f"{thread_id}-decision",
                        kind="decision",
                        content=f"{thread_id} memory",
                        scope=scope.kind,
                        source="test",
                    )
                )

            summary = MemoryCleanupPolicy(root).cleanup_conversation_memories(
                live_thread_ids=["thread-active"],
                archived_thread_ids=["thread-archived"],
                quarantine=True,
            )

            self.assertEqual(summary["archived"], ["thread-archived"])
            self.assertEqual(summary["quarantined"], ["thread-gone"])
            self.assertTrue((root / "conversations" / "thread-active").exists())
            self.assertTrue((root / "conversations" / "thread-archived").exists())
            self.assertFalse((root / "conversations" / "thread-gone").exists())
            self.assertTrue((root / "_quarantine" / "thread-gone").exists())


if __name__ == "__main__":
    unittest.main()
