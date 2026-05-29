---
name: development-lifecycle-harness
description: Use when running UAF development work through design, isolated workspace setup, planning, TDD implementation, review, verification, and branch finishing.
---

# Development Lifecycle Harness

This is a personal UAF development workflow. It packages the useful planning, TDD, review, and branch-finishing methodology without requiring any external workflow plugin at runtime.

## Reference basis

- Personal skillbook workflow: brainstorming, isolated workspaces, writing plans, subagent-driven development, executing plans, test-driven development, requesting code review, receiving code review, and finishing a development branch.

## Workflow

1. Clarify the intended outcome and constraints before changing behavior.
2. Create or select an isolated workspace when the task can disturb unrelated work.
3. Write a short implementation plan for multi-step work with exact files, tests, and verification commands.
4. For behavior changes, add or update a failing test before production edits.
5. Implement the smallest change that satisfies the test and the user requirement.
6. Review for scope drift, missing requirements, and risky integration points.
7. Run fresh verification before claiming completion or committing.
8. Finish with an explicit integration action: keep changes local, commit, push, or open a PR.

## Gate checks

- No broad refactor unless the plan requires it.
- No completion claim without fresh verification output.
- No branch finishing until the working tree diff matches the requested scope.

## Required outputs

- Implementation plan for multi-step work, including files, tests, and verification commands.
- Failing-first test or smoke evidence for behavior changes when practical.
- Review findings or an explicit no-findings review note.
- Fresh verification output and final integration status: local only, committed, pushed, or PR-ready.

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
