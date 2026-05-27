import os
import tempfile
import unittest

from src.core.snapshot_manager import SnapshotManager


class SnapshotManagerTests(unittest.TestCase):
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
            with open(file_path, "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "old")

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
