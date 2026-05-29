---
name: development-lifecycle-harness
description: Use when running UAF development work through design, isolated workspace setup, planning, TDD implementation, review, verification, and branch finishing.
---

# Development Lifecycle Harness

This is a personal UAF development workflow. It packages the useful Plan -> Work -> Review loop with TDD, verification, and branch finishing without requiring any external workflow plugin at runtime. When the work produces a reusable lesson, hand off to `workflow-skill-distiller` for the Compound step.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
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

## Workflow

1. Clarify the intended outcome and constraints before changing behavior.
2. Choose and record `workspace_strategy` before editing; for implementation in a Git-backed project, prefer isolated workspace unless an in-place exception applies.
3. Create or refresh `GoalState` before implementation by using `goal-state-harness` for objective, success criteria, required evidence, and blocked-state handling.
4. Write a short implementation plan for multi-step work with exact files, tests, and verification commands.
5. For behavior changes, add or update a failing test before production edits.
6. Implement the smallest change that satisfies the test and the user requirement.
7. Review for scope drift, missing requirements, and risky integration points.
8. Run fresh verification before claiming completion or committing.
9. Update the goal ledger with evidence, missing evidence, next action, and visible KH Markdown artifacts.
10. Finish with an explicit integration action: keep changes local, commit, push, or open a PR.
11. If the review exposed a reusable pattern, bug class, or repeatable workflow, capture it through `workflow-skill-distiller`, `context-state-harness`, or a scenario regression.

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
- `workspace_strategy` with path, branch, host workspace, or in-place rationale.
- GoalState summary with objective, success criteria, required evidence, current evidence, missing evidence, and goal ledger paths.
- Failing-first test or smoke evidence for behavior changes when practical.
- Review findings or an explicit no-findings review note.
- Fresh verification output and final integration status: local only, committed, pushed, or PR-ready.
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
