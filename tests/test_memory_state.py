import tempfile
import unittest
from pathlib import Path

from src.orchestration.memory_state import MemoryScopeResolver


class MemoryScopeResolverTests(unittest.TestCase):
    def test_project_scope_uses_project_local_memory_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()

            scope = MemoryScopeResolver.project_scope(str(project_dir))
            storage_path = MemoryScopeResolver.storage_path(scope)

            self.assertEqual(scope.kind, "project")
            self.assertEqual(scope.project_id, "demo")
            self.assertEqual(scope.status, "active")
            self.assertEqual(storage_path, project_dir / ".uaf" / "memory")

    def test_conversation_scope_uses_thread_namespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = MemoryScopeResolver.conversation_scope(
                thread_id="thread-1",
                conversation_memory_root=tmp,
                status="archived",
            )

            self.assertEqual(scope.kind, "conversation")
            self.assertEqual(scope.thread_id, "thread-1")
            self.assertEqual(scope.status, "archived")
            self.assertEqual(
                MemoryScopeResolver.storage_path(scope),
                Path(tmp) / "conversations" / "thread-1",
            )

    def test_from_adapter_metadata_prefers_project_scope_when_project_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()

            scope = MemoryScopeResolver.from_adapter_metadata(
                project_dir=str(project_dir),
                metadata={"app_context": {"thread_id": "thread-1"}},
                conversation_memory_root=Path(tmp) / "codex-memory",
            )

            self.assertEqual(scope.kind, "project")
            self.assertEqual(scope.thread_id, "thread-1")
            self.assertEqual(MemoryScopeResolver.storage_path(scope), project_dir / ".uaf" / "memory")

    def test_from_adapter_metadata_uses_conversation_scope_without_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = MemoryScopeResolver.from_adapter_metadata(
                project_dir="",
                metadata={"app_context": {"thread_id": "thread-1"}},
                conversation_memory_root=tmp,
            )

            self.assertEqual(scope.kind, "conversation")
            self.assertEqual(MemoryScopeResolver.storage_path(scope), Path(tmp) / "conversations" / "thread-1")


if __name__ == "__main__":
    unittest.main()
