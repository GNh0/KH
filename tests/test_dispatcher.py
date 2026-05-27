import unittest
from contextlib import redirect_stdout
from io import StringIO

from src.platforms.dispatcher_factory import AntigravityDispatcher


class AntigravityDispatcherTests(unittest.TestCase):
    def test_execute_formats_payload_without_name_error(self):
        with redirect_stdout(StringIO()):
            result = AntigravityDispatcher().execute(
                project_dir="C:/work/demo",
                files=["main.py"],
                design_doc="# design",
                platform_mode="antigravity",
            )

        self.assertEqual(len(result), 1)
        self.assertIn("Pending", result[0])


if __name__ == "__main__":
    unittest.main()
