import json
import tempfile
import unittest
from pathlib import Path

from src.contracts import MemoryRecord, WorkflowTaskResult
from src.orchestration.development_progress import (
    DevelopmentRunProgress,
    DevelopmentTaskProgress,
    read_development_progress,
    validate_development_progress,
    write_development_progress,
)
from src.orchestration.memory_state import MemoryScopeResolver
from src.orchestration.memory_store import MemoryStore
from src.orchestration.progress_compound_bridge import (
    build_progress_compound_artifacts,
    write_progress_compound_artifacts,
)
from src.orchestration.progress_panel import build_progress_panel, render_progress_panel
from src.orchestration.role_commands import (
    build_role_command_menu,
    list_role_command_entrypoints,
    resolve_role_command,
)
from src.orchestration.session_start_context import (
    build_session_start_context,
    render_session_start_context,
)
from src.orchestration.token_optimizer_provider import (
    resolve_token_optimizer_provider,
    validate_token_optimizer_provider,
)
from src.orchestration.workflow_usability_runtime import (
    apply_workflow_usability_runtime,
    build_workflow_usability_preflight,
    workflow_usability_enabled,
)


class WorkflowUsabilityLayerTests(unittest.TestCase):
    def sample_progress(self) -> DevelopmentRunProgress:
        return DevelopmentRunProgress(
            run_id="run-usability",
            objective="Build a visible KH task workflow.",
            workspace_strategy="project-local-worktree",
            workspace_path=".worktrees/run-usability",
            token_optimizer_status="used",
            tasks=[
                DevelopmentTaskProgress(
                    task_id="task-1",
                    title="Add workflow bridge",
                    status="complete",
                    red_status="failed_expected",
                    green_status="passed",
                    spec_review_status="passed",
                    code_quality_review_status="passed",
                    commit_sha="abc1234",
                    changed_files=["src/orchestration/progress_compound_bridge.py"],
                    metadata={
                        "learning_candidates": [
                            {
                                "title": "Progress state should feed Compound",
                                "trigger": "A progress run completes after review",
                                "reusable_insight": "Convert progress.json into CompoundCapture and visible next skills.",
                                "evidence": ["progress.json", "review passed"],
                                "target_update": "skill",
                            }
                        ],
                        "memory_candidates": [
                            {
                                "scope": "project",
                                "content": "For KH task runs, inspect progress.json before relying on chat context.",
                                "evidence": ["progress.json"],
                                "confidence": 0.9,
                            }
                        ],
                    },
                )
            ],
            metadata={
                "system_updates": ["Expose progress-to-compound bridge in KH usability docs."],
                "regression_checks": ["python -m unittest tests.test_workflow_usability_layer"],
            },
        )

    def test_progress_json_builds_compound_memory_skill_and_scenario_candidates(self):
        artifacts = build_progress_compound_artifacts(self.sample_progress())

        self.assertEqual(artifacts.handoff["status"], "ready_for_system_update")
        self.assertIn("compound_capture", artifacts.evidence)
        self.assertIn("memory_candidates", artifacts.evidence)
        self.assertIn("skill_candidates", artifacts.evidence)
        self.assertIn("scenario_candidates", artifacts.evidence)
        self.assertIn("workflow-skill-distiller", artifacts.capture.next_skills)
        self.assertIn("scenario-evaluation-harness", artifacts.capture.next_skills)
        self.assertIn("memory-state-harness", artifacts.capture.next_skills)
        self.assertEqual(artifacts.memory_candidates[0].confidence, "high")

    def test_progress_compound_artifacts_write_state_and_docs_handoff(self):
        progress = self.sample_progress()
        with tempfile.TemporaryDirectory() as tmp:
            result = write_progress_compound_artifacts(tmp, progress)

            for key in [
                "compound_capture",
                "compound_handoff",
                "compound_candidates",
                "compound_markdown",
            ]:
                self.assertTrue(Path(result.paths[key]).is_file(), key)

            handoff = json.loads(Path(result.paths["compound_handoff"]).read_text(encoding="utf-8"))
            self.assertEqual(handoff["status"], "ready_for_system_update")
            self.assertIn("compound_artifacts_written", result.evidence)

    def test_token_optimizer_provider_policy_supports_kh_rtk_hybrid_and_passthrough(self):
        self.assertTrue(validate_token_optimizer_provider("kh")["valid"])
        self.assertFalse(validate_token_optimizer_provider("unknown")["valid"])

        kh = resolve_token_optimizer_provider("kh", command="python -m unittest")
        self.assertEqual(kh.provider, "kh")
        self.assertEqual(kh.status, "selected")

        rtk_fallback = resolve_token_optimizer_provider("rtk", command="pytest", rtk_available=False)
        self.assertEqual(rtk_fallback.provider, "kh")
        self.assertEqual(rtk_fallback.status, "fallback")

        rtk_blocked = resolve_token_optimizer_provider(
            "rtk",
            command="pytest",
            rtk_available=False,
            strict=True,
        )
        self.assertEqual(rtk_blocked.status, "blocked")

        hybrid = resolve_token_optimizer_provider("hybrid", command="npm test", rtk_available=True)
        self.assertEqual(hybrid.provider, "rtk")

        passthrough = resolve_token_optimizer_provider("hybrid", content_kind="contract-sensitive")
        self.assertEqual(passthrough.provider, "passthrough")
        self.assertIn("token_optimizer_provider", passthrough.evidence)

    def test_role_commands_are_simple_front_doors_to_kh_skills(self):
        commands = list_role_command_entrypoints()
        names = {entry["name"] for entry in commands}
        self.assertIn("/kh:brainstorm", names)
        self.assertIn("/kh:work", names)
        self.assertIn("/kh:learn", names)

        review = resolve_role_command("eng-review")
        self.assertIn("subagent-review-pipeline", review.skills)
        self.assertIn("code-quality-reviewer", review.roles)

        menu = build_role_command_menu()
        self.assertIn("KH Role Commands", menu)
        self.assertIn("/kh:resume", menu)

    def test_progress_panel_renders_visible_task_state(self):
        progress = self.sample_progress()
        panel = build_progress_panel(progress)
        rendered = render_progress_panel(progress)

        self.assertEqual(panel["counts"]["complete"], 1)
        self.assertEqual(panel["task_status"], "complete")
        self.assertIn("KH Progress", rendered)
        self.assertIn("[x] task-1", rendered)
        self.assertIn("Token: used", rendered)

    def test_session_start_context_reads_kh_docs_progress_compound_and_memory_candidates(self):
        progress = self.sample_progress()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_development_progress(root, progress)
            compound = write_progress_compound_artifacts(root, progress)
            docs_dir = root / "docs" / "kh" / "handoffs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            (docs_dir / "manual.md").write_text("# Manual Handoff\n\nRead this.", encoding="utf-8")

            scope = MemoryScopeResolver.project_scope(str(root))
            memory_dir = root / ".memory"
            store = MemoryStore(str(memory_dir), scope)
            store.append_candidate(
                MemoryRecord(
                    record_id="candidate-1",
                    kind="project-note",
                    content="Read KH progress and Compound before continuing.",
                    scope="project",
                    source="test",
                    metadata={"source_path": compound.paths["compound_handoff"]},
                )
            )

            context = build_session_start_context(root, memory_root=memory_dir)
            rendered = render_session_start_context(context)

            self.assertEqual(context["latest_progress"]["run_id"], "run-usability")
            self.assertEqual(context["compound_handoff"]["status"], "ready_for_system_update")
            self.assertTrue(context["docs_kh"])
            self.assertEqual(context["memory_candidates"][0]["content"], "Read KH progress and Compound before continuing.")
            self.assertIn("KH Session Start Context", rendered)
            self.assertIn("Memory Candidates", rendered)

    def test_plugin_surface_exposes_workflow_usability_controls(self):
        root = Path(__file__).resolve().parents[1]
        codex_manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        root_manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        prompt = "\n".join(codex_manifest["interface"]["defaultPrompt"])
        root_skill_names = {skill["name"] for skill in root_manifest["skills"]}

        for capability in [
            "Progress Compound Bridge",
            "Workflow Usability Runtime",
            "Session Postmortem",
            "Completion Guard",
            "Verification Claim Guard",
            "Windows Dev Server Runner",
            "Token Provider Policy",
            "Role Commands",
            "Progress Panel",
            "Session Restore",
        ]:
            self.assertIn(capability, codex_manifest["interface"]["capabilities"])

        for expected in [
            "workflow-usability-harness",
            "workflow-usability-runtime",
            "progress-compound-bridge",
            "token-optimizer-provider",
            "role-command-entrypoints",
            "progress-panel",
            "session-start-context",
            "session-postmortem",
            "windows-dev-server-runner",
        ]:
            self.assertIn(expected, root_skill_names)

        self.assertIn("token_optimizer_provider", prompt)
        self.assertIn("workflow_usability_auto", prompt)
        self.assertIn("session_postmortem", prompt)
        self.assertIn("scope_completion_delta", prompt)
        self.assertIn("skill inspection", prompt)
        self.assertIn("windows-dev-server-runner", prompt)
        self.assertIn("/kh:work", prompt)
        self.assertIn("progress.json", prompt)
        self.assertIn(".kh", prompt)

    def test_runtime_usability_hooks_generate_visible_workflow_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata = {
                "workflow_usability_auto": True,
                "token_optimizer_provider": "kh",
                "token_optimizer_status": "considered_not_needed",
                "workspace_strategy": "project-local-worktree",
                "goal": {"objective": "Build a workflow."},
            }
            preflight = build_workflow_usability_preflight(tmp, metadata)
            result = apply_workflow_usability_runtime(
                project_dir=tmp,
                workflow_id="workflow-demo",
                file_list=["main.py"],
                task_results=[
                    WorkflowTaskResult(
                        task_id="task-main",
                        file_name="main.py",
                        role="implementer",
                        status="success",
                        message="done",
                        metadata={"evidence": ["task runner completed"]},
                    )
                ],
                gate_results=[
                    {"role": "spec-reviewer", "status": "passed"},
                    {"role": "code-quality-reviewer", "status": "passed"},
                ],
                metadata=metadata,
                final_goal={"objective": "Build a workflow.", "status": "complete"},
                workflow_success=True,
                preflight=preflight,
            )

            self.assertTrue(workflow_usability_enabled(metadata))
            self.assertEqual(result.status, "complete")
            self.assertTrue(Path(result.progress_path).exists())
            self.assertIn("KH Progress", result.progress_panel)
            self.assertEqual(result.token_optimizer_provider["provider"], "kh")
            self.assertTrue(Path(result.compound["paths"]["compound_handoff"]).exists())
            progress = read_development_progress(result.progress_path)
            self.assertTrue(validate_development_progress(progress)["valid"])
            self.assertIn("development_progress_valid", result.evidence)


if __name__ == "__main__":
    unittest.main()
