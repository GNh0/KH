import json
import tempfile
import unittest
from pathlib import Path

from src.contracts import GoalState
from src.orchestration.artifacts import ArtifactStore
from src.orchestration.domain_profiles import DomainProfileBuilder, work_design_from_profile
from src.orchestration.goal_ledger import GoalLedger
from src.orchestration.handoff import ResumeHandoff


class ResumeHandoffTests(unittest.TestCase):
    def test_handoff_snapshot_is_built_from_goal_ledger_and_artifact_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = DomainProfileBuilder.build(
                objective="Improve a support workflow",
                domain_hint="operations",
                artifact_types=["workflow-map"],
            )
            design = work_design_from_profile(profile, deliverables=["workflow improvement memo"])
            ArtifactStore(tmp).save_work_design(
                workflow_id="workflow_demo",
                work_design=design,
                source_design_doc="# Source Design",
            )
            goal = GoalState(
                objective="Improve a support workflow",
                status="blocked",
                success_criteria=["review evidence is available"],
                evidence_required=["design_doc", "review passed"],
                evidence=["design_doc"],
                blocked_reason="missing required evidence: review passed",
                metadata={
                    "missing_evidence": ["review passed"],
                    "memory_context": {"record_count": 0, "records": []},
                    "git_state": {"branch": "feature/demo", "dirty": True},
                    "decisions": ["Use local runtime storage"],
                    "remaining_work": ["Collect review evidence"],
                },
            )
            GoalLedger(tmp).save_current_goal(
                goal.to_dict(),
                next_recommended_action="collect missing evidence: review passed",
            )

            result = ResumeHandoff(tmp).save()

            json_path = Path(result["paths"]["json_path"])
            markdown_path = Path(result["paths"]["markdown_path"])
            json_exists = json_path.exists()
            markdown_exists = markdown_path.exists()
            snapshot = result["snapshot"]
            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertTrue(json_exists)
        self.assertTrue(markdown_exists)
        self.assertEqual(snapshot["objective"], "Improve a support workflow")
        self.assertEqual(snapshot["status"], "blocked")
        self.assertEqual(snapshot["workflow_id"], "workflow_demo")
        self.assertEqual(snapshot["success_criteria"], ["review evidence is available"])
        self.assertEqual(snapshot["missing_evidence"], ["review passed"])
        self.assertEqual(snapshot["git_state"]["branch"], "feature/demo")
        self.assertEqual(snapshot["decisions"], ["Use local runtime storage"])
        self.assertEqual(snapshot["remaining_work"], ["Collect review evidence"])
        self.assertEqual(persisted["next_recommended_action"], "collect missing evidence: review passed")
        self.assertEqual(persisted["success_criteria"], ["review evidence is available"])
        self.assertIn("# UAF Resume Handoff", markdown)
        self.assertIn("No prior chat context is required", markdown)
        self.assertIn("## Success Criteria", markdown)
        self.assertIn("review evidence is available", markdown)
        self.assertIn("review passed", markdown)
        self.assertIn("Use local runtime storage", markdown)
        self.assertIn("Collect review evidence", markdown)

    def test_handoff_snapshot_handles_missing_state_as_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = ResumeHandoff(tmp).build_snapshot()

        self.assertEqual(snapshot.status, "unavailable")
        self.assertEqual(snapshot.objective, "")
        self.assertIn("current_goal.json not found", snapshot.next_recommended_action)


if __name__ == "__main__":
    unittest.main()
