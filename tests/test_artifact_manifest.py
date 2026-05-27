import json
import tempfile
import unittest
from pathlib import Path

from src.orchestration.artifacts import ArtifactStore
from src.orchestration.domain_profiles import DomainProfileBuilder, work_design_from_profile


class ArtifactStoreTests(unittest.TestCase):
    def test_store_saves_work_design_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = DomainProfileBuilder.build(
                objective="Design a launch plan",
                domain_hint="marketing",
                artifact_types=["channel-plan"],
            )
            design = work_design_from_profile(profile, deliverables=["launch memo"])
            store = ArtifactStore(tmp)

            result = store.save_work_design(
                workflow_id="workflow_demo",
                work_design=design,
                source_design_doc="# Source design",
            )

            manifest_path = Path(result["store"]["manifest_path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifact_path = Path(result["manifest"]["design_artifacts"][0]["path"])

            self.assertTrue(artifact_path.exists())
            self.assertEqual(manifest["workflow_id"], "workflow_demo")
            self.assertIn("work design saved", result["evidence"])
            self.assertIn("artifact manifest saved", result["evidence"])
            self.assertIn("required design artifacts saved", result["evidence"])

    def test_store_saves_additional_design_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp)

            result = store.save_design_artifacts(
                workflow_id="workflow_demo",
                domain="generic",
                artifact_specs=[
                    {
                        "artifact_id": "risk_matrix",
                        "kind": "risk-matrix",
                        "title": "Risk Matrix",
                        "content": "# Risks\n",
                        "owner_role": "risk-policy-reviewer",
                        "required_for": ["review"],
                    }
                ],
            )

            self.assertEqual(result["manifest"]["design_artifacts"][0]["artifact_id"], "risk_matrix")
            self.assertTrue(Path(result["manifest"]["design_artifacts"][0]["path"]).exists())

    def test_store_rejects_unsafe_artifact_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(tmp)

            with self.assertRaises(ValueError):
                store.save_design_artifacts(
                    workflow_id="workflow_demo",
                    domain="generic",
                    artifact_specs=[
                        {
                            "artifact_id": "../outside",
                            "kind": "bad",
                            "title": "Bad",
                            "content": "bad",
                        }
                    ],
                )


if __name__ == "__main__":
    unittest.main()
