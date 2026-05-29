# Development Lifecycle Harness Usage Reference

This reference expands the portable operating contract for `development-lifecycle-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when running UAF development work through design, isolated workspace setup, planning, TDD implementation, review, verification, and branch finishing.

Context summary: This is a personal UAF development workflow. It packages the useful planning, TDD, review, and branch-finishing methodology without requiring any external workflow plugin at runtime.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Workspace strategy: `current-checkout`, `project-local-worktree`, `host-worktree`, or `isolated-branch`.
- Default to isolated workspace for implementation in Git-backed projects. Use `current-checkout` only for documentation-only edits, a single-file small patch, or explicit user instruction.
- GoalState inputs: objective, success criteria, required evidence, current evidence, active task, missing evidence, and next recommended action.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `procedure-policy`.
- Implementation targets:
  - `src.orchestration.agent_loop`
  - `src.core.snapshot_manager`
  - `src.harness.evaluator`
  - `src.tasks.workflows`
  - `src.skills.uaf_skill_catalog`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `development-lifecycle-harness`.
3. Apply the written workflow as a host-agent policy, then record the decision, boundary, or gate evidence that proves the policy was actually used.
4. For implementation work, choose `host-worktree`, `project-local-worktree`, or `isolated-branch` before editing unless the task qualifies for `current-checkout`.
5. Create or refresh `GoalState` through `goal-state-harness` before implementation, then update it after checks, review, QA, and release decisions.
6. For parallel or risky edits, record whether work used `.worktrees/`, an isolated branch, or an equivalent host workspace.
7. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
8. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
9. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- `workspace_strategy` and its evidence: current checkout rationale, worktree path, host workspace id, or isolated branch name.
- GoalState and goal ledger evidence: objective, status, success criteria, evidence required, evidence collected, missing evidence, and next recommended action.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.

## Quality bar

A valid use of `development-lifecycle-harness` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
