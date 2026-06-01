import builtins
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


_REAL_IMPORT = builtins.__import__


def _block_httpx_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "httpx" or name.startswith("httpx."):
        raise ModuleNotFoundError("No module named 'httpx'")
    return _REAL_IMPORT(name, globals, locals, fromlist, level)


class OptionalDependencyTests(unittest.TestCase):
    def test_workflow_import_and_no_webhook_dispatch_do_not_require_httpx(self):
        original_module = sys.modules.pop("src.tasks.workflows", None)
        original_url = os.environ.pop("AG_WEBHOOK_URL", None)

        try:
            with patch("builtins.__import__", side_effect=_block_httpx_import):
                workflows = importlib.import_module("src.tasks.workflows")

                with tempfile.TemporaryDirectory() as tmp:
                    project_dir = Path(tmp) / "demo"
                    project_dir.mkdir()
                    result = workflows.dispatch_project_workflow(
                        project_dir=str(project_dir),
                        file_list=["main.py"],
                        design_doc="# design",
                        platform_mode="local",
                        metadata={},
                    )
        finally:
            sys.modules.pop("src.tasks.workflows", None)
            if original_module is not None:
                sys.modules["src.tasks.workflows"] = original_module
            if original_url is not None:
                os.environ["AG_WEBHOOK_URL"] = original_url

        self.assertTrue(result.success)
        self.assertEqual(result.task_results[0].metadata["webhook_report"]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
