import os
import tempfile
import unittest
from pathlib import Path

from src.orchestration.memory_state import MemoryScopeResolver


class MemoryScopeResolverTests(unittest.TestCase):
    def test_project_scope_uses_external_runtime_memory_directory_by_default(self):
        original_runtime_root = os.environ.get("UAF_RUNTIME_ROOT")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                project_dir = Path(tmp) / "demo"
                runtime_root = Path(tmp) / "runtime"
                project_dir.mkdir()
                os.environ["UAF_RUNTIME_ROOT"] = str(runtime_root)

                scope = MemoryScopeResolver.project_scope(str(project_dir))
                storage_path = MemoryScopeResolver.storage_path(scope)

                self.assertEqual(scope.kind, "project")
                self.assertEqual(scope.project_id, "demo")
                self.assertEqual(scope.status, "active")
                self.assertTrue(str(storage_path).startswith(str(runtime_root)))
                self.assertEqual(storage_path.name, "memory")
                self.assertEqual(storage_path.parent.name, ".uaf")
                self.assertFalse((project_dir / ".uaf").exists())
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

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
                Path(tmp) / "conversations" / "thread-1" / ".uaf" / "memory",
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
            self.assertEqual(MemoryScopeResolver.storage_path(scope).name, "memory")
            self.assertIn("chats", MemoryScopeResolver.storage_path(scope).parts)
            self.assertIn("thread-1", MemoryScopeResolver.storage_path(scope).parts)
            self.assertFalse((project_dir / ".uaf").exists())

    def test_from_adapter_metadata_uses_conversation_scope_without_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            scope = MemoryScopeResolver.from_adapter_metadata(
                project_dir="",
                metadata={"app_context": {"thread_id": "thread-1"}},
                conversation_memory_root=tmp,
            )

            self.assertEqual(scope.kind, "conversation")
            self.assertEqual(
                MemoryScopeResolver.storage_path(scope),
                Path(tmp) / "conversations" / "thread-1" / ".uaf" / "memory",
            )


if __name__ == "__main__":
    unittest.main()
