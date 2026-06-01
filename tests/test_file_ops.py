import os
import tempfile
import unittest

from src.skills import file_ops


class FileOpsSkillTests(unittest.TestCase):
    def test_safe_path_rejects_prefix_sibling_workspace(self):
        original_root = file_ops.WORKSPACE_ROOT
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = os.path.join(temp_dir, "workspace")
            sibling = os.path.join(temp_dir, "workspace_evil", "leak.txt")
            os.makedirs(workspace)
            os.makedirs(os.path.dirname(sibling))
            file_ops.WORKSPACE_ROOT = os.path.abspath(workspace)
            try:
                self.assertFalse(file_ops._is_safe_path(sibling))
            finally:
                file_ops.WORKSPACE_ROOT = original_root


if __name__ == "__main__":
    unittest.main()
