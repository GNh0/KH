import json
import tempfile
import unittest
from dataclasses import replace
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
from src.orchestration.progress_panel import (
    build_host_progress_panel,
    build_progress_panel,
    render_progress_panel,
    write_host_progress_panel,
)
from src.orchestration.interruption_state import (
    build_interruption_checkpoint,
    write_interruption_checkpoint,
)
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

    def test_host_progress_panel_contract_targets_native_agent_surfaces(self):
        progress = self.sample_progress()

        panel = build_host_progress_panel(progress, host="antigravity")

        self.assertEqual(panel["schema"], "kh.uaf.host_progress_panel.v1")
        self.assertEqual(panel["host"], "antigravity")
        self.assertEqual(panel["host_binding"]["preferred_surface"], "antigravity-agent-manager")
        self.assertTrue(panel["capabilities"]["subagent_panel"])
        self.assertTrue(panel["capabilities"]["worktree_aware"])
        self.assertEqual(panel["summary"]["workspace_strategy"], "project-local-worktree")
        self.assertIn("tasks", {section["id"] for section in panel["sections"]})
        self.assertIn("subagents", {section["id"] for section in panel["sections"]})
        task_rows = next(section["rows"] for section in panel["sections"] if section["id"] == "tasks")
        self.assertEqual(task_rows[0]["status"], "complete")
        self.assertEqual(task_rows[0]["detail"]["spec_review_status"], "passed")
        self.assertEqual(
            panel["state_files"]["host_panel_json"],
            ".kh/development/run-usability/state/host_panel.antigravity.json",
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = write_host_progress_panel(tmp, progress, host="antigravity")
            written = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(path.name, "host_panel.antigravity.json")
            self.assertEqual(written["host"], "antigravity")
            self.assertEqual(written["summary"]["task_status"], "complete")

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
            self.assertEqual(context["memory_context"]["record_count"], 0)
            self.assertEqual(context["memory_recall"]["records"], [])
            self.assertIn("KH Session Start Context", rendered)
            self.assertIn("Memory Records", rendered)
            self.assertIn("Memory Recall", rendered)
            self.assertIn("Memory Candidates", rendered)

    def test_session_start_context_searches_relevant_memory_for_objective(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            memory_dir = root / ".memory"
            scope = MemoryScopeResolver.project_scope(str(root))
            store = MemoryStore(str(memory_dir), scope)
            store.save_record(
                MemoryRecord(
                    record_id="resume-lesson",
                    kind="decision",
                    content="After user stop, load resume checkpoint before implementation.",
                    scope="project",
                    source="test",
                )
            )
            store.save_record(
                MemoryRecord(
                    record_id="unrelated",
                    kind="decision",
                    content="Use green accent for dashboard charts.",
                    scope="project",
                    source="test",
                )
            )

            context = build_session_start_context(
                root,
                memory_root=memory_dir,
                objective="continue implementation from resume checkpoint",
            )
            rendered = render_session_start_context(context)

            self.assertEqual(context["memory_recall"]["search_strategy"], "keyword_ranked")
            self.assertEqual(context["memory_recall"]["records"][0]["record_id"], "resume-lesson")
            self.assertIn("After user stop, load resume checkpoint", rendered)

    def test_session_start_context_imports_explicit_external_memory_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            source = root / "source"
            target_memory = root / "target-memory"
            source_memory = root / "source-memory"
            source_scope = replace(
                MemoryScopeResolver.project_scope(str(source), thread_id="source-thread"),
                root_path=str(source_memory),
            )
            MemoryStore(str(source_memory), source_scope).save_record(
                MemoryRecord(
                    record_id="source-decision",
                    kind="decision",
                    content="Keep imported memory read-only until the user approves applying it.",
                    scope=source_scope.kind,
                    source="source-session",
                )
            )

            context = build_session_start_context(
                target,
                thread_id="target-thread",
                memory_root=target_memory,
                objective="memory import approval",
                explicit_memory_imports=[
                    {
                        "source_scope": source_scope.to_dict(),
                        "query": "imported memory approval",
                        "metadata": {"cross_scope_memory_import": True},
                    }
                ],
            )
            rendered = render_session_start_context(context)

            self.assertEqual(context["memory_context"]["record_count"], 0)
            self.assertEqual(context["memory_imports"][0]["status"], "approval_required")
            self.assertEqual(context["memory_imports"][0]["application_status"], "read_only_external_context")
            self.assertEqual(
                context["memory_imports"][0]["external_context"]["records"][0]["record_id"],
                "source-decision",
            )
            target_scope = replace(
                MemoryScopeResolver.project_scope(str(target), thread_id="target-thread"),
                root_path=str(target_memory),
            )
            self.assertEqual(MemoryStore(str(target_memory), target_scope).read_candidates(), [])
            self.assertIn("Explicit Memory Imports", rendered)

    def test_interruption_checkpoint_writes_resume_memory_and_session_start_prefers_it(self):
        progress = DevelopmentRunProgress(
            run_id="run-stop",
            objective="Finish a long task safely.",
            workspace_strategy="project-local-worktree",
            active_task="task-2",
            next_task="task-2",
            token_optimizer_status="used",
            tasks=[
                DevelopmentTaskProgress(
                    task_id="task-1",
                    title="Done task",
                    status="complete",
                    red_status="failed_expected",
                    green_status="passed",
                    spec_review_status="passed",
                    code_quality_review_status="passed",
                    commit_sha="abc1234",
                ),
                DevelopmentTaskProgress(
                    task_id="task-2",
                    title="Continue stopped work",
                    status="in_progress",
                    changed_files=["src/example.py"],
                    verification=[{"command": "python -m unittest", "status": "failed"}],
                    next_action="resume from failing test",
                ),
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            memory_dir = root / ".memory"

            checkpoint = build_interruption_checkpoint(
                root,
                progress,
                goal={"objective": progress.objective, "status": "active"},
            )
            result = write_interruption_checkpoint(
                root,
                progress,
                goal={"objective": progress.objective, "status": "active"},
                thread_id="thread-1",
                memory_root=memory_dir,
            )
            context = build_session_start_context(root, thread_id="thread-1", memory_root=memory_dir)
            rendered = render_session_start_context(context)

            self.assertEqual(checkpoint.goal["status"], "blocked")
            self.assertTrue(Path(result["paths"]["interruption_json"]).exists())
            self.assertTrue(Path(result["paths"]["interruption_markdown"]).exists())
            self.assertEqual(result["memory"]["status"], "saved")
            self.assertEqual(context["interruption_checkpoint"]["run_id"], "run-stop")
            self.assertEqual(context["memory_context"]["record_count"], 1)
            self.assertIn("Resume checkpoint for run-stop", context["memory_context"]["records"][0]["content"])
            self.assertEqual(context["recommended_reads"][0], result["paths"]["interruption_json"])
            self.assertIn("Interrupted: run-stop reason=user_requested_stop", rendered)
            self.assertIn("Resume checkpoint for run-stop", rendered)

    def test_plugin_surface_exposes_workflow_usability_controls(self):
        root = Path(__file__).resolve().parents[1]
        codex_manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        root_manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        prompt = "\n".join(codex_manifest["interface"]["defaultPrompt"])
        root_skill_names = {skill["name"] for skill in root_manifest["skills"]}

        for capability in [
            "Progress Compound Bridge",
            "Workflow Usability Runtime",
            "Runtime Token Optimization",
            "Runtime Memory Candidates",
            "Active Memory Preflight",
            "Bounded Prompt Memory",
            "Pre-Compaction Memory Flush",
            "Memory Provider Policy",
            "Session Postmortem",
            "Session Skill Audit",
            "Completion Guard",
            "User Stop Guard",
            "Interruption Checkpoints",
            "Verification Claim Guard",
            "Windows Dev Server Runner",
            "Token Provider Policy",
            "Role Commands",
            "Progress Panel",
            "Host Native Progress Panels",
            "Session Restore",
        ]:
            self.assertIn(capability, codex_manifest["interface"]["capabilities"])

        for expected in [
            "workflow-usability-harness",
            "workflow-usability-runtime",
            "runtime-token-optimizer",
            "runtime-memory-candidates",
            "active-memory-preflight",
            "pre-compaction-memory-flush",
            "memory-provider-policy",
            "progress-compound-bridge",
            "token-optimizer-provider",
            "role-command-entrypoints",
            "progress-panel",
            "host-progress-panel",
            "interruption-checkpoint",
            "session-start-context",
            "session-postmortem",
            "session-skill-audit",
            "windows-dev-server-runner",
        ]:
            self.assertIn(expected, root_skill_names)

        self.assertIn("token_optimizer_provider", prompt)
        self.assertIn("workflow_usability_auto", prompt)
        self.assertIn("session_postmortem", prompt)
        self.assertIn("session_skill_audit", prompt)
        self.assertIn("scope_completion_delta", prompt)
        self.assertIn("user_stop_guard", prompt)
        self.assertIn("host goal tool allows blocking", prompt)
        self.assertIn("host policy disallows using blocked as pause/cancel state", prompt)
        self.assertIn("fresh non-goal_context user message", prompt)
        self.assertIn("interruption.json", prompt)
        self.assertIn("resume-checkpoint", prompt)
        self.assertIn("memory_candidates", prompt)
        self.assertIn("skill inspection", prompt)
        self.assertIn("windows-dev-server-runner", prompt)
        self.assertIn("host_panel.<host>.json", prompt)
        self.assertIn("/kh:work", prompt)
        self.assertIn("progress.json", prompt)
        self.assertIn(".kh", prompt)

    def test_runtime_usability_hooks_generate_visible_workflow_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata = {
                "workflow_usability_auto": True,
                "token_optimizer_provider": "kh",
                "token_optimizer_status": "considered_not_needed",
                "token_optimizer_min_tokens": 1,
                "token_optimizer_max_lines": 8,
                "memory_root": str(Path(tmp) / ".memory"),
                "workspace_strategy": "project-local-worktree",
                "host_panel_host": "antigravity",
                "goal": {"objective": "Build a workflow."},
            }
            noisy_output = "\n".join([*(f"progress {index}" for index in range(80)), "ERROR: runtime failed", "exit code: 1"])
            preflight = build_workflow_usability_preflight(tmp, metadata)
            self.assertEqual(preflight["active_memory_preflight"]["status"], "applied")
            self.assertIn("bounded_prompt_memory", preflight["active_memory_preflight"]["evidence"])
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
                        metadata={
                            "evidence": ["task runner completed"],
                            "command_output": {
                                "command": "python -m unittest",
                                "stdout": noisy_output,
                                "stderr": "",
                                "exit_code": 1,
                            },
                        },
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
            self.assertTrue(Path(result.host_progress_panel_path).exists())
            self.assertEqual(result.host_progress_panel["host"], "antigravity")
            self.assertIn("host_progress_panel", result.evidence)
            self.assertEqual(result.token_optimizer_provider["provider"], "kh")
            self.assertEqual(result.token_optimization["status"], "used")
            self.assertGreater(result.token_optimization["summary"]["actual_tokens_saved"], 0)
            self.assertEqual(
                result.token_optimization["summary"]["actual_usage_scope"],
                "actual_optimizer_input_output_payload",
            )
            self.assertTrue(result.token_optimization["summary"]["token_count_is_estimate"])
            self.assertFalse(result.token_optimization["summary"]["billing_tokens_available"])
            self.assertEqual(result.memory_state["status"], "candidates_recorded")
            self.assertEqual(result.memory_state["recorded_count"], 1)
            self.assertIn("runtime_token_optimization", result.evidence)
            self.assertIn("memory_candidates_recorded", result.evidence)
            self.assertTrue(Path(result.memory_state["store"]["candidates_path"]).exists())
            self.assertTrue(Path(result.compound["paths"]["compound_handoff"]).exists())
            progress = read_development_progress(result.progress_path)
            self.assertTrue(validate_development_progress(progress)["valid"])
            self.assertEqual(progress.token_optimizer_status, "used")
            task_optimizer = progress.tasks[0].metadata["workflow_task_result"]["metadata"]["token_optimizer"]
            self.assertEqual(task_optimizer["status"], "used")
            self.assertGreater(task_optimizer["summary"]["actual_tokens_saved"], 0)
            self.assertIn("ERROR: runtime failed", task_optimizer["records"][0]["stdout"])
            self.assertIn("development_progress_valid", result.evidence)


if __name__ == "__main__":
    unittest.main()
