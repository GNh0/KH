---
name: development-lifecycle-harness
description: Use when running UAF development work through design, isolated workspace setup, planning, TDD implementation, review, verification, and branch finishing.
---

# Development Lifecycle Harness

This is a personal UAF development workflow. It packages the useful Plan -> Work -> Review loop with TDD, verification, and branch finishing without requiring any external workflow plugin at runtime. When the work produces a reusable lesson, hand off to `workflow-skill-distiller` for the Compound step.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- For task-by-task implementation runs, write progress to `.kh/development/<run-id>/state/progress.json`; the runtime helper is `src.orchestration.development_progress`.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Reference basis

- Personal skillbook workflow: brainstorming, isolated workspaces, writing plans, subagent-driven development, executing plans, test-driven development, requesting code review, receiving code review, and finishing a development branch.

## Workspace Strategy Policy

- Default to an isolated workspace before implementation in a Git-backed project.
- Prefer a host-provided worktree when Codex, Antigravity-style, Claude Code, or another host exposes one; otherwise use project-local `.worktrees/<task-or-branch>` or an isolated branch.
- Treat TDD implementation, multi-file edits, large changes, parallel implementers, and user-work protection as strong triggers for `project-local-worktree` or `host-worktree`.
- In-place edits are allowed only for documentation-only changes, a single-file small patch, or explicit user instruction.
- Final status must include `workspace_strategy`: `current-checkout`, `project-local-worktree`, `host-worktree`, or `isolated-branch` plus path, branch, host workspace, or in-place rationale.

## Context Budget Policy

- For large or long-running implementation, design, review, QA, or resume work, run `token-optimizer` as a context budget gate before broad reads, long commands, or subagent handoffs.
- Use `command-output-harness` plus `token-optimizer` for repeated test, lint, build, traceback, or install logs so exit codes and actionable failures are preserved without flooding context.
- Final status must include `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked`, plus savings, passthrough reason, blocked reason, or skip rationale.

## Large Work Orchestration Bundle Policy

- For large project, SaaS, app, multi-file implementation, role-DAG, or long-running work, create `large_work_orchestration_bundle` evidence before implementation.
- The bundle must contain `skill_statuses` for `request-complexity-router`, `host-agent-orchestration`, `goal-state-harness`, `development-lifecycle-harness`, `token-optimizer`, `memory-state-harness`, `parallel-orchestration-harness`, `subagent-review-pipeline`, `role-execution-audit-harness`, `compound-engineering-harness`, and `workflow-skill-distiller`.
- Each `skill_statuses` entry must be one of `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`, with a short evidence note or rationale.
- Each entry must include `application_mode`: `runtime`, `procedural`, `considered`, or `blocked`. Use `runtime` only when a Python module, adapter, role DAG, command, or harness output actually ran. Use `procedural` when the skill was applied as host policy. Use `considered` when a lightweight decision was made. Use `blocked` when required capability, context, permission, or evidence is missing.
- Use the minimal evidence template when runtime evidence would be disproportionate: `skill`, `status`, `application_mode`, `evidence_note`, `evidence_keys`, and optional `blocked_reason`. This does not require AdapterRequest, role results, or wave metadata unless those runtime paths are actually claimed.
- Do not run every bundle member heavily by default. `memory-state-harness`, `parallel-orchestration-harness`, `subagent-review-pipeline`, `role-execution-audit-harness`, `compound-engineering-harness`, and `workflow-skill-distiller` may be `considered_not_needed` when the run lacks durable memory, independent workers, claimed role DAG execution, or reusable learning.
- `memory-state-harness` should normally produce memory candidates only unless the user explicitly approves durable promotion and scope.
- The bundle must preserve `parallel_strategy_decision`, `memory_candidates`, `workspace_strategy`, `token_optimizer_status`, and `compound_handoff` or a no-learning rationale.

## Skill Transition Policy

- Treat bundle member skills as connected handoffs, not as a passive checklist.
- After review and before final completion, validate `skill_transition_handoff` through `src.orchestration.skill_transitions`.
- `memory_candidates` require `memory-state-harness` to be applied, blocked, or explicitly resolved.
- Applied `subagent-review-pipeline` requires `role-execution-audit-harness` to inspect the role/reviewer outputs or report a blocker.
- A parallel execution decision requires `parallel-orchestration-harness` evidence.
- Post-review work must close `compound-engineering-harness` with reusable learning, a scoped next skill, or an explicit `no_reusable_learning_rationale`.
- Compound `next_skills` such as `workflow-skill-distiller`, `memory-state-harness`, `scenario-evaluation-harness`, or `context-state-harness` must be followed or listed as required next work; do not leave them as invisible chat-only advice.

## Workflow

1. Clarify the intended outcome and constraints before changing behavior.
2. Choose and record `workspace_strategy` before editing; for implementation in a Git-backed project, prefer isolated workspace unless an in-place exception applies.
3. Create or refresh `GoalState` before implementation by using `goal-state-harness` for objective, success criteria, required evidence, and blocked-state handling.
4. For large work, create or update `large_work_orchestration_bundle.skill_statuses` before editing.
5. Decide `token_optimizer_status` for large or long-running work and route long logs or subagent transcripts through `token-optimizer` when needed.
6. Write a short implementation plan for multi-step work with exact files, tests, and verification commands.
7. For task-plan work, create `.kh/development/<run-id>/state/progress.json` and update it as each task moves through RED, GREEN, spec review, code-quality review, fix, re-review, commit, and next task.
8. For behavior changes, add or update a failing test before production edits.
9. Implement the smallest change that satisfies the test and the user requirement.
10. Review for scope drift, missing requirements, and risky integration points.
11. Run fresh verification before claiming completion or committing.
12. Update the goal ledger with evidence, missing evidence, next action, and visible KH Markdown artifacts.
13. Validate `skill_transition_handoff` for large work so required follow-up skills cannot be silently omitted.
14. Finish with an explicit integration action: keep changes local, commit, push, or open a PR.
15. If the review exposed a reusable pattern, bug class, or repeatable workflow, capture it through `workflow-skill-distiller`, `context-state-harness`, or a scenario regression.

## Gate checks

- No broad refactor unless the plan requires it.
- No completion claim without fresh verification output.
- No implementation in the current checkout unless the task matches an in-place exception or the user explicitly requested it.
- No concurrent file-editing workers in one mutable checkout without a non-overlap proof.
- No branch finishing until the working tree diff matches the requested scope.

## External Benchmark Recipe

Use this harness like a Superpowers-style execution guard, not just as lifecycle advice:

1. Write a three-line plan: target files, first failing check, final verification command.
2. Create a snapshot or record why no snapshot is needed before editing shared files.
3. Run the narrow check before implementation and record RED, skipped-with-reason, or not-applicable.
4. Implement, then run the narrow check and the broader verification suite.
5. Finish with one integration state: local only, committed, pushed, or PR-ready.

Pressure scenario: if the agent says "small change, no test needed", it must produce a smoke check, manual evidence, or an explicit no-test rationale before editing. If it cannot, the lifecycle gate is blocked.

## Required outputs

- Implementation plan for multi-step work, including files, tests, and verification commands.
- `large_work_orchestration_bundle` with `skill_statuses` for large work; valid statuses are `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`.
- `workspace_strategy` with path, branch, host workspace, or in-place rationale.
- `token_optimizer_status` with token savings, passthrough reason, blocked reason, or `considered_not_needed` rationale for large or long-running workflows.
- GoalState summary with objective, success criteria, required evidence, current evidence, missing evidence, and goal ledger paths.
- Development progress state at `.kh/development/<run-id>/state/progress.json` for multi-task implementation runs, with task IDs, active task, RED/GREEN status, spec/code-quality review status, commit SHA, and next task.
- `skill_transition_handoff` for large-work progress and final reports, with required next skills or `skill_transition_policy_passed`.
- Failing-first test or smoke evidence for behavior changes when practical.
- Review findings or an explicit no-findings review note.
- Fresh verification output and final integration status: local only, committed, pushed, or PR-ready.
- Stable final report fields: `task_status`, `review_status`, `commit_sha`, `next_task`, `workspace_strategy`, `token_optimizer_status`, and `skill_statuses`.
- Compound note, distilled skill candidate, scenario regression, or explicit no-reusable-learning rationale when the work produced a repeatable lesson.

## Common mistakes

- Do not skip design or planning because the task looks small when it changes shared behavior.
- Do not write production behavior before the failing check for bug fixes or new behavior.
- Do not mix unrelated refactors into the branch-finishing diff.
- Do not claim completion from stale test output or a previous run.

## UAF implementation targets

- `src.orchestration.agent_loop`
- `src.core.snapshot_manager`
- `src.harness.evaluator`
- `src.tasks.workflows`
- `src.skills.uaf_skill_catalog`
- `src.orchestration.development_progress`
