import json
import tempfile
import unittest
from pathlib import Path

from src.orchestration.brainstorming import (
    BrainstormDecision,
    BrainstormOption,
    BrainstormSession,
    write_brainstorm_markdown_artifacts,
)
from src.orchestration.goal_ledger import GoalLedger
from src.orchestration.project_markdown import (
    KH_DOC_TYPES,
    KHProjectMarkdownStore,
    write_goal_markdown_artifacts,
)


class ProjectMarkdownArtifactTests(unittest.TestCase):
    def test_store_writes_local_content_and_docs_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = KHProjectMarkdownStore(tmp).write_markdown(
                kind="brainstorm",
                title="SaaS Directions",
                body="## Options\n- CRM pipeline",
                slug="saas-directions",
                run_id="run-001",
                metadata={"skill": "brainstorming-harness"},
            )

            content_path = Path(result["content_path"])
            docs_path = Path(result["docs_path"])

            self.assertEqual(content_path.relative_to(tmp), Path(".kh/brainstorm/run-001/content/saas-directions.md"))
            self.assertEqual(docs_path.relative_to(tmp), Path("docs/kh/handoffs/saas-directions.md"))
            self.assertIn("skill: brainstorming-harness", content_path.read_text(encoding="utf-8"))
            self.assertIn("# SaaS Directions", docs_path.read_text(encoding="utf-8"))

    def test_store_writes_superpowers_style_content_state_and_docs_taxonomy(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = KHProjectMarkdownStore(tmp)
            result = store.write_markdown(
                kind="brainstorm",
                title="SaaS Directions",
                body="## Options\n- CRM pipeline",
                slug="saas-directions",
                run_id="run-001",
                doc_type="handoffs",
                metadata={"skill": "brainstorming-harness"},
            )
            state_result = store.write_state(
                kind="brainstorm",
                run_id="run-001",
                name="session",
                payload={"status": "approved", "selected": "Pipeline CRM"},
            )

            content_path = Path(result["content_path"])
            state_path = Path(state_result["state_path"])
            docs_path = Path(result["docs_path"])

            self.assertEqual(content_path.relative_to(tmp), Path(".kh/brainstorm/run-001/content/saas-directions.md"))
            self.assertEqual(state_path.relative_to(tmp), Path(".kh/brainstorm/run-001/state/session.json"))
            self.assertEqual(docs_path.relative_to(tmp), Path("docs/kh/handoffs/saas-directions.md"))
            self.assertEqual(result["content_dir"], str(content_path.parent))
            self.assertEqual(result["state_dir"], str(state_path.parent))
            self.assertEqual(result["doc_type"], "handoffs")
            self.assertIn("selected", state_path.read_text(encoding="utf-8"))

    def test_known_document_types_cover_core_kh_outputs(self):
        self.assertEqual(
            KH_DOC_TYPES,
            ("specs", "plans", "decisions", "qa", "handoffs"),
        )

    def test_store_rejects_escape_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = KHProjectMarkdownStore(tmp)

            with self.assertRaises(ValueError):
                store.write_markdown(
                    kind="goal",
                    title="Bad",
                    body="bad",
                    local_root="../outside",
                )

    def test_brainstorm_session_exports_markdown_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = BrainstormSession(
                objective="Pick a CRM SaaS direction",
                target_user="Small B2B sales teams",
                problem="Lead follow-up is inconsistent",
                options=[
                    BrainstormOption(
                        name="Pipeline CRM",
                        tradeoffs=["fastest MVP"],
                        recommended=True,
                        rationale="Core workflow first",
                    )
                ],
                decisions=[
                    BrainstormDecision(
                        key="mvp",
                        value="Pipeline CRM",
                        rationale="Best validates SaaS basics",
                    )
                ],
                constraints=["No external API for first demo"],
            )

            result = write_brainstorm_markdown_artifacts(tmp, session, run_id="brainstorm-001")

            content = Path(result["content_path"]).read_text(encoding="utf-8")
            state = Path(result["state_path"]).read_text(encoding="utf-8")
            self.assertIn("brainstorming-harness", content)
            self.assertIn("Pipeline CRM", content)
            self.assertIn("Best validates SaaS basics", content)
            self.assertEqual(Path(result["docs_path"]).parent.relative_to(tmp), Path("docs/kh/handoffs"))
            self.assertIn("architect-pipeline", state)

    def test_goal_ledger_writes_project_markdown_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = GoalLedger(tmp)
            state = ledger.save_current_goal(
                {
                    "objective": "Build login",
                    "status": "active",
                    "success_criteria": ["login tests pass"],
                    "evidence_required": ["tdd_red_green"],
                    "evidence": [],
                },
                active_task="write failing test",
                next_recommended_action="run RED check",
            )

            project_markdown = state["project_markdown"]
            goal_doc = Path(project_markdown["docs_path"])
            current_goal = json.loads(Path(ledger.current_goal_path).read_text(encoding="utf-8"))

            self.assertTrue(goal_doc.exists())
            self.assertIn("Build login", goal_doc.read_text(encoding="utf-8"))
            self.assertIn("write failing test", goal_doc.read_text(encoding="utf-8"))
            self.assertEqual(current_goal["project_markdown"], project_markdown)

    def test_goal_markdown_can_be_written_directly(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = write_goal_markdown_artifacts(
                tmp,
                {
                    "objective": "Ship feature",
                    "status": "blocked",
                    "blocked_reason": "missing QA",
                    "evidence_required": ["qa gate passed"],
                    "evidence": ["design_doc"],
                },
                active_task="QA",
                next_recommended_action="run QA gate",
                run_id="goal-001",
            )

            content = Path(result["content_path"]).read_text(encoding="utf-8")
            state = Path(result["state_path"]).read_text(encoding="utf-8")
            self.assertIn("Status: blocked", content)
            self.assertIn("missing QA", content)
            self.assertIn("qa gate passed", content)
            self.assertIn("Ship feature", state)

    def test_readme_and_plugin_describe_kh_project_artifact_layout(self):
        repo_root = Path(__file__).resolve().parents[1]
        readme = (repo_root / "README.md").read_text(encoding="utf-8")
        plugin = (repo_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")

        for text in (readme, plugin):
            self.assertIn(".kh/<skill>/<run-id>/content/", text)
            self.assertIn(".kh/<skill>/<run-id>/state/", text)
            self.assertIn("docs/kh/specs", text)
            self.assertIn("docs/kh/plans", text)
            self.assertIn("docs/kh/qa", text)
            self.assertIn("docs/kh/handoffs", text)


if __name__ == "__main__":
    unittest.main()
