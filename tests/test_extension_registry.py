import unittest

from src.orchestration.extension_registry import ExtensionRegistry


class ExtensionRegistryTests(unittest.TestCase):
    def test_registry_creates_named_extensions_case_insensitively(self):
        registry = ExtensionRegistry()
        registry.register("dispatcher", "CustomHost", lambda: "created")

        self.assertTrue(registry.has("dispatcher", "customhost"))
        self.assertEqual(registry.create("dispatcher", "CUSTOMHOST"), "created")
        self.assertEqual(registry.names("dispatcher"), ["customhost"])

    def test_registry_rejects_unknown_extensions(self):
        registry = ExtensionRegistry()

        with self.assertRaises(KeyError):
            registry.create("dispatcher", "missing")

    def test_registry_prevents_accidental_overwrite(self):
        registry = ExtensionRegistry()
        registry.register("llm_provider", "echo", lambda: "one")

        with self.assertRaises(ValueError):
            registry.register("llm_provider", "echo", lambda: "two")

        registry.register("llm_provider", "echo", lambda: "two", overwrite=True)
        self.assertEqual(registry.create("llm_provider", "echo"), "two")


if __name__ == "__main__":
    unittest.main()
