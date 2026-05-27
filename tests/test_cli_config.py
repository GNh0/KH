import argparse
import tempfile
import unittest

import cli


class CliConfigTests(unittest.TestCase):
    def test_build_llm_router_uses_explicit_cli_options(self):
        args = argparse.Namespace(
            provider="openai",
            model="gpt-5-mini",
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
        )

        router = cli.build_llm_router(args)

        self.assertEqual(router.provider, "openai")
        self.assertEqual(router.model, "gpt-5-mini")
        self.assertEqual(router.base_url, "https://api.openai.com/v1")
        self.assertEqual(router.api_key, "sk-test")

    def test_build_agent_loop_uses_explicit_platform_mode(self):
        router = argparse.Namespace()

        with tempfile.TemporaryDirectory() as temp_dir:
            loop = cli.build_agent_loop(
                router=router,
                project=temp_dir,
                platform_mode="antigravity",
            )

        self.assertEqual(loop.platform_mode, "antigravity")


if __name__ == "__main__":
    unittest.main()
