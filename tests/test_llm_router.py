import unittest
from unittest.mock import patch

import requests

from src.orchestration.llm_router import LLMRouter, LLMRouterError


class LLMRouterTests(unittest.TestCase):
    def tearDown(self):
        LLMRouter.reset_provider_registry_for_tests()

    def test_custom_llm_provider_can_be_registered(self):
        class EchoProvider:
            def __init__(self, router):
                self.router = router

            def chat(self, system_prompt, user_prompt):
                return f"{self.router.model}:{system_prompt}:{user_prompt}"

        LLMRouter.register_provider("echo", lambda router: EchoProvider(router))
        router = LLMRouter(provider="echo", model="custom-model")

        self.assertEqual(router.chat("system", "user"), "custom-model:system:user")

    def test_openai_compatible_connection_errors_raise(self):
        router = LLMRouter(provider="local", base_url="http://127.0.0.1:9/v1")

        with patch("src.orchestration.llm_router.requests.post", side_effect=requests.ConnectionError("down")):
            with self.assertRaises(LLMRouterError):
                router.chat("system", "user")

    def test_offline_provider_returns_deterministic_target_files(self):
        router = LLMRouter(provider="offline")

        response = router.chat(
            "You output only JSON arrays.",
            "Return only a JSON array of source file paths.",
        )

        self.assertEqual(response, "[\"README.md\", \"src/app.py\"]")

    def test_offline_provider_returns_deterministic_file_content(self):
        router = LLMRouter(provider="offline")

        response = router.chat(
            "Return only file content.",
            "Target file: src/app.py\nRole: implementer\n",
        )

        self.assertIn("def main", response)
        self.assertIn("KH UAF", response)

    def test_offline_provider_prioritizes_target_file_over_embedded_csv_context(self):
        router = LLMRouter(provider="offline")

        response = router.chat(
            "Return only file content.",
            "Target file: src/app.py\n\nDesign document:\n## 기능정의서\n```csv\nID,대분류,기능명,상세설명\n```",
        )

        self.assertIn("def main", response)
        self.assertNotIn("ID,대분류", response)


if __name__ == "__main__":
    unittest.main()
