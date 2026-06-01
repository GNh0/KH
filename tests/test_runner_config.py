import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from src.core import runner


class RunnerConfigTests(unittest.TestCase):
    def test_orchestrate_mode_passes_platform_mode_to_agent_loop(self):
        argv = [
            "runner.py",
            "--mode",
            "orchestrate",
            "--project_dir",
            "C:/work/demo",
            "--reqs",
            "build api",
            "--framework",
            "fastapi",
            "--platform_mode",
            "antigravity",
        ]

        with patch.object(sys, "argv", argv), \
                patch.object(runner, "LLMRouter", return_value=object()), \
                patch.object(runner, "AgentLoop") as agent_loop_cls, \
                redirect_stdout(StringIO()):
            runner.main()

        agent_loop_cls.assert_called_once()
        self.assertEqual(agent_loop_cls.call_args.kwargs["platform_mode"], "antigravity")
        agent_loop_cls.return_value.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
