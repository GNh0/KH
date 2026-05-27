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


if __name__ == "__main__":
    unittest.main()
