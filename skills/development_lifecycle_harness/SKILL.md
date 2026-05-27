---
name: development-lifecycle-harness
description: Use when running UAF development work through design, isolated workspace setup, planning, TDD implementation, review, verification, and branch finishing.
---

# Development Lifecycle Harness

This is a UAF-native development workflow derived from Superpowers. It packages the useful methodology without requiring the Superpowers plugin at runtime.

## Reference basis

- Superpowers: brainstorming, isolated worktrees, writing plans, subagent-driven development, executing plans, test-driven development, requesting code review, receiving code review, and finishing a development branch.

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

## UAF implementation targets

- `src.orchestration.agent_loop`
- `src.core.snapshot_manager`
- `src.harness.evaluator`
- `src.tasks.workflows`
- `src.skills.uaf_skill_catalog`
