import unittest

from src.contracts import MemoryEvent, MemoryRecord, MemoryScope


class MemoryContractTests(unittest.TestCase):
    def test_memory_scope_round_trips_as_dict(self):
        scope = MemoryScope(
            kind="project",
            namespace="project:demo",
            project_id="demo",
            root_path="C:/work/demo/.uaf/memory",
            status="active",
            metadata={"workspace_root": "C:/work/demo"},
        )

        self.assertEqual(MemoryScope.from_dict(scope.to_dict()), scope)

    def test_memory_record_round_trips_as_dict(self):
        record = MemoryRecord(
            record_id="decision-1",
            kind="decision",
            content="UAF core stays Python-first; TypeScript is sidecar-first.",
            scope="project",
            source="user-approved",
            confidence="high",
            metadata={"project_id": "demo"},
        )

        restored = MemoryRecord.from_dict(record.to_dict())

        self.assertEqual(restored, record)

    def test_memory_event_round_trips_as_dict(self):
        event = MemoryEvent(
            event_type="memory_saved",
            record_id="decision-1",
            scope="project",
            payload={"kind": "decision"},
        )

        self.assertEqual(MemoryEvent.from_dict(event.to_dict()), event)


if __name__ == "__main__":
    unittest.main()
