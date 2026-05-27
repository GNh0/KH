import unittest

from src.orchestration.agent_loop import AgentLoop


class AgentLoopParsingTests(unittest.TestCase):
    def test_parse_target_files_requires_json_array_of_strings(self):
        self.assertEqual(
            AgentLoop.parse_target_files('["main.py", "src/app.py"]'),
            ["main.py", "src/app.py"],
        )

        with self.assertRaises(ValueError):
            AgentLoop.parse_target_files("Error connecting to LLM API: down")

        with self.assertRaises(ValueError):
            AgentLoop.parse_target_files('{"file": "main.py"}')


if __name__ == "__main__":
    unittest.main()
