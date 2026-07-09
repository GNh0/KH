# worktree-isolation-harness Minimal Workflow Example

## Scenario

The user asks for a multi-file SaaS feature in a Git repository. The current checkout has unrelated local edits.

## Expected steps

1. Inspect branch, status, and whether the task is write-capable.
2. Detect that multi-file implementation and dirty state require isolation.
3. Create or select a host worktree or `.worktrees/<task>` branch.
4. Record base SHA, worktree path, branch, and cleanup policy.
5. Run implementation in that workspace.
6. Report `workspace_strategy` in final status and branch finishing evidence.

## Expected evidence

- `actual_runtime_path`: `skills/worktree_isolation_harness/SKILL.md`
- `execution_level`: `hybrid-harness`
- Implementation targets:
  - `src.orchestration.development_progress.WORKSPACE_STRATEGIES`
  - `skills/worktree_isolation_harness/SKILL.md`
  - `skills/parallel_orchestration_harness/SKILL.md`
- `workspace_strategy`: `project-local-worktree`
- `worktree_root`: `.worktrees`
- `dirty_state_handling`: unrelated checkout changes protected
- `cleanup_policy`: remove after merge/push or keep for follow-up

## Failure cases

- The agent edits current checkout despite unrelated dirty files.
- Two subagents write to the same mutable checkout without non-overlap proof.
- Worktree creation fails and the agent silently continues in-place.
- Final status omits where the work happened.

## Done criteria

- Workspace strategy is recorded before edits.
- In-place exceptions are explicit.
- Subagent and branch finishing stages can reuse the strategy evidence.
- Catalog validation and the skill smoke check pass.

## Runtime binding

- execution_level: hybrid-harness
- implementation_targets:
  - `src.orchestration.development_progress.WORKSPACE_STRATEGIES`
  - `skills/worktree_isolation_harness/SKILL.md`
  - `skills/parallel_orchestration_harness/SKILL.md`
  - `skills/development_lifecycle_harness/SKILL.md`
- actual_runtime_path: `src.orchestration.development_progress.WORKSPACE_STRATEGIES`
- verification evidence: run `scripts/smoke_check.py`, `scripts/demo.py --output-dir <tmp>`, git status/root checks, and the workflow tests that use the selected workspace strategy.
