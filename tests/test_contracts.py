import unittest

from src.contracts import AdapterRequest, AdapterResult, HarnessResult, SkillManifest


class HarnessResultContractTests(unittest.TestCase):
    def test_harness_result_round_trips_as_dict(self):
        result = HarnessResult(
            success=False,
            stdout="out",
            stderr="boom",
            exit_code=1,
            execution_time=0.25,
            metadata={"adapter": "codex"},
        )

        restored = HarnessResult.from_dict(result.to_dict())

        self.assertEqual(restored, result)


class SkillManifestContractTests(unittest.TestCase):
    def test_skill_manifest_loads_plugin_shape(self):
        manifest = SkillManifest.from_plugin_json({
            "name": "universal-agent-framework",
            "version": "2.5.0",
            "description": "Universal skill harness",
            "entrypoint": "cli.py",
            "requires": ["fastapi", "requests"],
            "skills": [{"name": "sandbox"}],
        })

        self.assertEqual(manifest.name, "universal-agent-framework")
        self.assertEqual(manifest.version, "2.5.0")
        self.assertEqual(manifest.entrypoint, "cli.py")
        self.assertEqual(manifest.requires, ["fastapi", "requests"])
        self.assertEqual(manifest.capabilities, ["sandbox"])


class AdapterContractTests(unittest.TestCase):
    def test_adapter_request_and_result_are_serializable(self):
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="codex",
            metadata={"thread": "local"},
        )
        result = AdapterResult(
            status="accepted",
            message="queued",
            workflow_id="workflow_demo",
            metadata={"tasks": 1},
        )

        self.assertEqual(AdapterRequest.from_dict(request.to_dict()), request)
        self.assertEqual(AdapterResult.from_dict(result.to_dict()), result)
        self.assertEqual(result.to_legacy_messages(), ["[Accepted] queued (ID: workflow_demo)"])


if __name__ == "__main__":
    unittest.main()
