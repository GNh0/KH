import unittest
import tempfile

from src.orchestration.agent_loop import AgentLoop


class FakeLLMRouter:
    pass


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

    def test_build_goal_metadata_creates_active_goal_from_requirement(self):
        metadata = AgentLoop.build_goal_metadata("build api")

        self.assertEqual(metadata["goal"]["objective"], "build api")
        self.assertEqual(metadata["goal"]["status"], "active")
        self.assertIn("workflow dispatch completed", metadata["goal"]["evidence_required"])

    def test_build_dispatch_metadata_attaches_llm_router_for_local_mode(self):
        llm = FakeLLMRouter()
        with tempfile.TemporaryDirectory() as tmp:
            loop = AgentLoop(llm, tmp, platform_mode="local")
            metadata = loop.build_dispatch_metadata("build api")

        self.assertIs(metadata["llm_router"], llm)
        self.assertEqual(metadata["goal"]["objective"], "build api")
        self.assertTrue(metadata["workflow_usability_auto"])
        self.assertEqual(metadata["token_optimizer_provider"], "kh")
        self.assertEqual(metadata["token_optimizer_status"], "considered_not_needed")

    def test_build_dispatch_metadata_omits_llm_router_for_host_modes(self):
        llm = FakeLLMRouter()
        with tempfile.TemporaryDirectory() as tmp:
            loop = AgentLoop(llm, tmp, platform_mode="antigravity")
            metadata = loop.build_dispatch_metadata("build api")

        self.assertNotIn("llm_router", metadata)
        self.assertTrue(metadata["workflow_usability_auto"])


if __name__ == "__main__":
    unittest.main()
