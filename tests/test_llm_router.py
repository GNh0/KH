import unittest
from unittest.mock import patch

import requests

from src.orchestration.llm_router import LLMRouter, LLMRouterError


class LLMRouterTests(unittest.TestCase):
    def test_openai_compatible_connection_errors_raise(self):
        router = LLMRouter(provider="local", base_url="http://127.0.0.1:9/v1")

        with patch("src.orchestration.llm_router.requests.post", side_effect=requests.ConnectionError("down")):
            with self.assertRaises(LLMRouterError):
                router.chat("system", "user")


if __name__ == "__main__":
    unittest.main()
