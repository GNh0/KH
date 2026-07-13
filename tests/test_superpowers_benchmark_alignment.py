import json
import unittest
from pathlib import Path

from src.orchestration.kh_front_door import build_kh_front_door


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def routed_skills(request: str) -> set[str]:
    summary = build_kh_front_door(
        request,
        project=REPO_ROOT,
        host="codex",
    ).to_summary_dict()
    return set(
        summary["runtime_applied_skills"]
        + summary["immediate_next_skills"]
        + summary["selected_not_executed_skills"]
    )


class SuperpowersBenchmarkAlignmentTests(unittest.TestCase):
    def test_benchmark_note_records_adopt_and_do_not_copy_boundaries(self):
        text = read_text("docs/skillbook/audits/2026-05-30-superpowers-benchmark.md")

        for expected in [
            "Strong front-door triggers",
            "One-question-at-a-time discovery",
            "TDD and verification-before-completion",
            "Subagent review discipline",
            "Compound engineering",
            "Worktree isolation",
            "Role-Stack Benchmark Coverage",
            "Office-hours style discovery before commitment",
            "CEO and advisor plan challenge",
            "Engineering, design, and developer-experience plan reviews",
            "Browser, QA, and release checks",
            "Security officer and safety guardrails",
            "Learn, retro, and project memory",
            "Cross-model or second-opinion review",
            "Continuous checkpoint and restore",
            "Do not require `.superpowers/` paths",
            "Current 2.9.4 Changes",
        ]:
            self.assertIn(expected, text)

    def test_project_local_artifacts_policy_keeps_kh_and_superpowers_paths_separate(self):
        readme = read_text("README.md")
        gitignore = read_text(".gitignore")

        self.assertIn("KH does not require `.superpowers/`", readme)
        self.assertIn("KH-owned runtime state should use `.uaf/`", readme)
        self.assertIn("KH local Markdown notes should use `.kh/`", readme)
        self.assertIn("Git worktrees should live under `.worktrees/`", readme)
        self.assertIn(".kh/", gitignore)
        self.assertIn(".worktrees/", gitignore)

    def test_front_door_brainstorming_is_kh_native_and_trigger_focused(self):
        skill = read_text("skills/brainstorming_harness/SKILL.md")

        self.assertIn("SaaS", skill)
        self.assertIn("Ask one question at a time", skill)
        self.assertIn("brainstorm_handoff", skill)
        self.assertIn("architect-pipeline", skill)
        self.assertIn("Do not copy Superpowers paths", skill)
        self.assertIn("KH handoff targets are UAF skills", skill)
        self.assertIn("stop before implementation", skill.lower())
        self.assertIn("approval before implementation", skill.lower())
        self.assertIn("user approves the direction", skill)

    def test_parallel_and_subagent_harnesses_require_isolation_evidence(self):
        parallel = read_text("skills/parallel_orchestration_harness/SKILL.md")
        subagent = read_text("skills/subagent_review_pipeline/SKILL.md")
        lifecycle = read_text("skills/development_lifecycle_harness/SKILL.md")

        for text in [parallel, subagent, lifecycle]:
            self.assertIn(".worktrees/", text)
            self.assertIn("isolated", text.lower())

        self.assertIn("isolation.workspace_strategy", parallel)
        self.assertIn("same mutable checkout", subagent)
        self.assertIn("No concurrent file-editing workers", lifecycle)

    def test_worktree_first_policy_is_visible_to_hosts(self):
        lifecycle = read_text("skills/development_lifecycle_harness/SKILL.md")
        parallel = read_text("skills/parallel_orchestration_harness/SKILL.md")
        router = read_text("skills/request_complexity_router/SKILL.md")
        selected = routed_skills(
            "Implement a multi-file feature with tests, worktree isolation, parallel workers, review, and verification."
        )

        self.assertIn(
            "Default to an isolated workspace before implementation in a Git-backed project.",
            lifecycle,
        )
        self.assertIn(
            "In-place edits are allowed only for documentation-only changes, a single-file small patch, or explicit user instruction.",
            lifecycle,
        )
        self.assertIn(
            "`workspace_strategy`: `current-checkout`, `project-local-worktree`, `host-worktree`, or `isolated-branch`",
            lifecycle,
        )
        self.assertIn(
            "For concurrent write workers, `project-local-worktree` is the default safe strategy.",
            parallel,
        )
        self.assertIn(
            "Workspace strategy is a cross-cutting output for implementation routes.",
            router,
        )
        self.assertIn("development-lifecycle-harness", selected)
        self.assertIn("worktree-isolation-harness", selected)
        self.assertIn("parallel-orchestration-harness", selected)

    def test_plan_work_review_compound_is_visible_to_plugin_users(self):
        readme = read_text("README.md")
        lifecycle = read_text("skills/development_lifecycle_harness/SKILL.md")
        compound = read_text("skills/compound_engineering_harness/SKILL.md")
        distiller = read_text("skills/workflow_skill_distiller/SKILL.md")
        brainstorming = read_text("skills/brainstorming_harness/SKILL.md")
        vague_request_route = routed_skills("Build a new operations dashboard in this folder.")
        large_work_route = routed_skills(
            "Implement a multi-file feature with tests, use a worktree, parallel workers, review, verify before completion, and finish the branch."
        )

        for stage in ["Plan", "Work", "Review", "Compound"]:
            self.assertIn(stage, readme)

        self.assertIn("Plan -> Work -> Review", lifecycle)
        self.assertIn("explicit Compound step", compound)
        self.assertIn("downstream distillation step", distiller)
        self.assertIn("compound-engineering-harness", distiller)
        for procedure in [
            "Objective/operator",
            "Success criteria/constraints/non-goals",
            "Required records/data/artifact shape",
            "direction question, not an execution question",
            "I will set the implementation scope as follows",
            "3-4 focused user decisions",
            "BrainstormSession",
            "brainstorm_handoff",
        ]:
            self.assertIn(procedure, brainstorming)

        self.assertIn("brainstorming-harness", vague_request_route)
        self.assertIn("compound-engineering-harness", large_work_route)
        self.assertIn("workflow-skill-distiller", large_work_route)

    def test_compound_harness_combines_external_role_stack_and_memory(self):
        skill = read_text("skills/compound_engineering_harness/SKILL.md")

        self.assertIn("role-stack", skill)
        self.assertIn("Superpowers", skill)
        self.assertIn("Compound", skill)
        self.assertIn("memory_candidates", skill)
        self.assertIn("memory-state-harness", skill)
        self.assertIn("regression_check_plan", skill)

    def test_memory_harness_adapts_openclaw_hermes_and_rtk_boundaries(self):
        skill = read_text("skills/memory_state_harness/SKILL.md")
        usage = read_text("skills/memory_state_harness/references/usage.md")
        combined = skill + "\n" + usage

        for expected in [
            "OpenClaw",
            "Hermes",
            "project/chat-scoped",
            "subagent lineage",
            "parent_memory_access",
            "parent_memory_candidates",
            "global_memory_candidate",
            "durable compact memory",
            "working daily/session memory",
            "action-sensitive memory boundaries",
            "frozen at session start",
            "session search",
            "external providers are additive",
            "source/owner authority",
            "safe-to-act",
            "RTK/command-output discipline",
        ]:
            self.assertIn(expected, combined)

    def test_large_project_control_sample_adds_progress_state_and_task_packets(self):
        audit = read_text("docs/skillbook/audits/2026-05-30-superpowers-large-project-control-sample.md")
        lifecycle = read_text("skills/development_lifecycle_harness/SKILL.md")
        subagent = read_text("skills/subagent_review_pipeline/SKILL.md")
        packets = read_text("skills/subagent_review_pipeline/references/standard-task-packets.md")
        usability = read_text("skills/workflow_usability_harness/SKILL.md")
        plugin = json.loads(read_text(".codex-plugin/plugin.json"))
        selected = routed_skills(
            "Implement a large multi-file project with task packets, subagent review, progress state, and verification."
        )

        for text in [audit, lifecycle, subagent, usability]:
            self.assertIn(".kh/development/<run-id>/state/progress.json", text)

        for expected in [
            "Implementer Packet",
            "Spec Reviewer Packet",
            "Code Quality Reviewer Packet",
            "RED -> GREEN",
            "commit_sha",
            "token_optimizer_status",
        ]:
            self.assertIn(expected, packets)

        self.assertIn("development progress state", plugin["description"])
        self.assertIn("Development Progress", plugin["interface"]["capabilities"])
        self.assertIn("workflow-usability-harness", selected)
        self.assertIn("subagent-review-pipeline", selected)

    def test_subagent_dispatch_and_token_optimizer_are_decision_gated(self):
        subagent = read_text("skills/subagent_review_pipeline/SKILL.md")
        packets = read_text("skills/subagent_review_pipeline/references/standard-task-packets.md")
        token = read_text("skills/token_optimizer/SKILL.md")
        readme = read_text("README.md")
        selected = routed_skills(
            "Use subagents for a multi-file implementation and review, with explicit token optimization decisions."
        )
        combined = "\n".join([subagent, packets, token, readme])

        for expected in [
            "subagent_strategy",
            "`dispatch`, `single-controller`, `review-only`, or `blocked`",
            "Dispatch subagents only when",
            "This is a decision gate, not automatic compression",
            "not automatic compression",
            "short or exact reviewer output",
            "considered_not_needed",
            "passthrough",
        ]:
            self.assertIn(expected, combined)

        self.assertIn("subagent-review-pipeline", selected)
        self.assertIn("token-optimizer", selected)

    def test_exact_target_and_memory_guards_are_visible_to_hosts(self):
        guard = read_text("skills/guard_policy_harness/SKILL.md")
        memory = read_text("skills/memory_state_harness/SKILL.md")
        selected = routed_skills(
            "Create generated project files at C:\\target and keep all memory scoped to this project and chat."
        )
        combined = "\n".join([guard, memory])

        for expected in [
            "Exact Target Path Rule",
            "same-name folder",
            "Relative staging followed by copy-back is a guard failure.",
            "The restriction also applies after a brainstorming approval message.",
            "Do not read host global Codex memory after a user approves a brainstorm option",
            "generated user-facing files must be created or updated at that exact resolved path",
            "Do not create a relative same-name project folder",
        ]:
            self.assertIn(expected, combined)

        self.assertIn("memory-state-harness", selected)
        self.assertIn("skill-catalog", selected)

    def test_runtime_prompts_use_stack_neutral_generated_file_language(self):
        guard = read_text("skills/guard_policy_harness/SKILL.md")
        front_door_example = read_text("skills/always_on_front_door/examples/minimal-workflow.md")
        agent_loop = read_text("src/orchestration/agent_loop.py")
        runtime_text = "\n".join([guard, front_door_example, agent_loop])

        for expected in [
            "workspace-root project files, stack-specific generated files, documents, images, drawings, or generated data files",
            "the chosen stack and artifact type",
            "approved project-appropriate deliverables",
        ]:
            self.assertIn(expected, runtime_text)

        for banned in [
            "do not create `index.html`, `styles.css`, `app.js`",
            "workspace-root files such as `index.html`, `styles.css`, `app.js`",
            "Make a small static dashboard",
            "[\"server.py\", \"index.html\", \"style.css\"]",
        ]:
            self.assertNotIn(banned, runtime_text)

    def test_skill_transition_policy_connects_large_work_skills(self):
        readme = read_text("README.md")
        lifecycle = read_text("skills/development_lifecycle_harness/SKILL.md")
        router = read_text("skills/request_complexity_router/SKILL.md")
        compound = read_text("skills/compound_engineering_harness/SKILL.md")
        audit = read_text("docs/skillbook/audits/2026-05-30-skill-transition-policy.md")
        plugin = json.loads(read_text(".codex-plugin/plugin.json"))
        selected = routed_skills(
            "Implement a multi-file feature with tests, use a worktree, parallel workers, review, verify before completion, and finish the branch."
        )
        combined = "\n".join([readme, lifecycle, router, compound, audit])

        for expected in [
            "skill_transition_handoff",
            "memory candidates trigger memory-state-harness",
            "subagent review triggers role-execution-audit-harness",
            "post-review work closes compound-engineering-harness",
            "workflow-skill-distiller",
            "scenario-evaluation-harness",
            "External role-stack",
        ]:
            self.assertIn(expected, combined)

        self.assertIn("Skill Transitions", plugin["interface"]["capabilities"])
        self.assertIn("compound-engineering-harness", selected)
        self.assertIn("workflow-skill-distiller", selected)


if __name__ == "__main__":
    unittest.main()
