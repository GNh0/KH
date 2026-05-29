import tempfile
import unittest
from pathlib import Path

from src.core.architect import run_architect_pipeline


class ArchitectPipelineTests(unittest.TestCase):
    def test_run_architect_pipeline_returns_design_exports_and_quality(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_architect_pipeline(
                project_dir=tmp,
                requirements="Build an operations dashboard with review evidence.",
                framework="generic",
                libraries=[],
                metadata={
                    "workflow_id": "architect-test",
                    "domain_hint": "software-development",
                    "target_files": ["src/app.py"],
                },
            )

        self.assertTrue(Path(result["design_doc_path"]).name, "design_doc.md")
        self.assertIn("Build an operations dashboard", result["design_doc"])
        self.assertEqual(result["work_design"]["domain"], "software-development")
        self.assertIn("deliverables", result["deliverable_exports"])
        self.assertIn(result["quality"]["status"], {"passed", "failed"})
        self.assertIn("work design saved", result["evidence"])


if __name__ == "__main__":
    unittest.main()
