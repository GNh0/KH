# worktree-isolation-harness Usage Reference

## When to use

Use when a Git-backed UAF implementation needs an isolated workspace, host worktree, project-local .worktrees task folder, or explicit in-place exception.

This harness should be considered before edits in repositories, especially when the task involves TDD, multiple files, generated code, parallel workers, subagents, user work protection, branch finishing, or uncertain scope. It is not required for pure read-only analysis.

## Inputs to collect

- Whether the target directory is a Git repository and the current branch/upstream.
- Current dirty state, untracked files, and user-owned unrelated changes.
- Host worktree capability and project-local `.worktrees/` policy.
- Task size, expected files, generated artifacts, subagent plan, and concurrency needs.
- User instruction about in-place editing or branch/worktree preferences.
- Cleanup policy for created workspaces.
- Execution level: `hybrid-harness`.
- Implementation targets:
  - `src.orchestration.development_progress.WORKSPACE_STRATEGIES`
  - `skills/worktree_isolation_harness/SKILL.md`
  - `skills/parallel_orchestration_harness/SKILL.md`
  - `skills/development_lifecycle_harness/SKILL.md`

## Execution pattern

1. Check repository state before editing.
2. Decide whether isolation is required. Strong triggers include multi-file implementation, TDD, parallel work, large refactors, generated code, migration work, and user dirty state.
3. Prefer a host-provided worktree when available; otherwise use `.worktrees/<task>` or an isolated branch.
4. Keep current checkout only for docs-only edits, single-file small patches, read-only work, or explicit in-place instruction.
5. Record `workspace_strategy`, path or branch, base SHA, dirty-state handling, and cleanup policy.
6. For subagents, ensure each write-capable worker has an isolated workspace or a documented non-overlap proof.
7. Carry the strategy into progress state, branch finishing, and final report.

## Evidence to produce

- Workspace strategy decision and rationale.
- Worktree path, host workspace id, branch name, base SHA, or in-place exception.
- Dirty-state handling and unrelated-change protection.
- Parallel/subagent isolation evidence when applicable.
- Cleanup or keep-alive rationale.

## Failure handling

- If worktree creation fails, fall back to an isolated branch or block with the Git error.
- If Git metadata is permission-blocked, do not edit in-place until the risk is understood.
- If existing dirty changes are unrelated, keep them out of staging and report them.
- If the user explicitly requests current checkout editing, record that override.

## Quality bar

A valid workspace decision should let another agent know exactly where edits occurred, why that location was safe, what user changes were protected, and what cleanup remains.

## Runtime binding

- Execution level: hybrid-harness
- Implementation targets:
  - `src.orchestration.development_progress.WORKSPACE_STRATEGIES`
  - `skills/worktree_isolation_harness/SKILL.md`
  - `skills/parallel_orchestration_harness/SKILL.md`
  - `skills/development_lifecycle_harness/SKILL.md`
- Application path: choose project-local worktree, host worktree, task folder, or explicit in-place exception before edits or subagent dispatch.
- Completion rule: do not report workspace isolation as applied until workspace strategy, safe root, in-place exception if any, and cleanup/handoff status are recorded.
