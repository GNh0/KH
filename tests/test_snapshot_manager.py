import os
import tempfile
import unittest

from src.core.snapshot_manager import SnapshotManager


class SnapshotManagerTests(unittest.TestCase):
    def test_default_snapshot_storage_does_not_create_project_metadata_folder(self):
        original_runtime_root = os.environ.get("UAF_RUNTIME_ROOT")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                project_dir = os.path.join(temp_dir, "app")
                runtime_root = os.path.join(temp_dir, "runtime")
                os.makedirs(project_dir)
                os.environ["UAF_RUNTIME_ROOT"] = runtime_root

                manager = SnapshotManager(project_dir)
                version_id = manager.commit("app.py", "old", "before change")

                self.assertFalse(os.path.exists(os.path.join(project_dir, ".snapshots")))
                self.assertTrue(os.path.exists(os.path.join(runtime_root, "projects")))
                self.assertTrue(os.path.exists(os.path.join(manager.snapshot_dir, version_id)))
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

    def test_commit_and_rollback_round_trip_file_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SnapshotManager(temp_dir)
            file_path = os.path.join(temp_dir, "app.py")
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write("old")

            version_id = manager.commit("app.py", "old", "before change")
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write("new")

            self.assertTrue(manager.rollback(version_id))
            summary = manager.rollback_result(version_id)
            self.assertEqual(summary["status"], "restored")
            self.assertEqual(summary["restored_files"], ["app.py"])
            with open(file_path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "old")

    def test_commit_many_creates_single_work_snapshot_bundle(self):
        original_runtime_root = os.environ.get("UAF_RUNTIME_ROOT")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                project_dir = os.path.join(temp_dir, "app")
                runtime_root = os.path.join(temp_dir, "runtime")
                os.makedirs(project_dir)
                os.environ["UAF_RUNTIME_ROOT"] = runtime_root
                with open(os.path.join(project_dir, "app.js"), "w", encoding="utf-8") as handle:
                    handle.write("old app")
                with open(os.path.join(project_dir, "index.html"), "w", encoding="utf-8") as handle:
                    handle.write("old html")
                manager = SnapshotManager(project_dir)

                version_id = manager.commit_many(
                    ["app.js", "index.html", "created_later.txt"],
                    "before dashboard work",
                )
                with open(os.path.join(project_dir, "app.js"), "w", encoding="utf-8") as handle:
                    handle.write("new app")
                with open(os.path.join(project_dir, "index.html"), "w", encoding="utf-8") as handle:
                    handle.write("new html")
                with open(os.path.join(project_dir, "created_later.txt"), "w", encoding="utf-8") as handle:
                    handle.write("new file")

                summary = manager.rollback_result(version_id)
                self.assertEqual(summary["status"], "restored")
                self.assertEqual(sorted(summary["restored_files"]), ["app.js", "index.html"])
                self.assertEqual(summary["removed_files"], ["created_later.txt"])
                self.assertEqual(summary["failed_files"], [])

                snapshot_files = [
                    name
                    for name in os.listdir(manager.snapshot_dir)
                    if name.endswith(".gz")
                ]
                self.assertEqual(snapshot_files, [version_id])
                with open(os.path.join(project_dir, "app.js"), "r", encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), "old app")
                with open(os.path.join(project_dir, "index.html"), "r", encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), "old html")
                self.assertFalse(os.path.exists(os.path.join(project_dir, "created_later.txt")))
        finally:
            if original_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = original_runtime_root

    def test_prune_keeps_latest_snapshot_and_log_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SnapshotManager(temp_dir)
            first = manager.commit("app.py", "v1", "first")
            second = manager.commit("app.py", "v2", "second")
            third = manager.commit("app.py", "v3", "third")

            summary = manager.prune(max_snapshots=1)

            self.assertEqual(summary["kept"], [third])
            self.assertEqual(summary["deleted"], [first, second])
            self.assertFalse(os.path.exists(os.path.join(manager.snapshot_dir, first)))
            self.assertFalse(os.path.exists(os.path.join(manager.snapshot_dir, second)))
            self.assertTrue(os.path.exists(os.path.join(manager.snapshot_dir, third)))
            self.assertEqual([entry["version_id"] for entry in manager._read_logs()], [third])

    def test_rejects_prefix_sibling_workspace_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = os.path.join(temp_dir, "app")
            sibling_dir = os.path.join(temp_dir, "app_evil")
            os.makedirs(base_dir)
            os.makedirs(sibling_dir)
            manager = SnapshotManager(base_dir)

            with self.assertRaises(PermissionError):
                manager.commit("../app_evil/escape.py", "bad", "escape")

    def test_rejects_snapshot_metadata_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = SnapshotManager(temp_dir)

            with self.assertRaises(PermissionError):
                manager.commit(".snapshots/commit_log.json", "bad", "metadata")


if __name__ == "__main__":
    unittest.main()
