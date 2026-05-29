# Parallel Orchestration Harness Usage Reference

This reference expands the portable operating contract for `parallel-orchestration-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when a task needs bounded parallel worker execution, fan-out/fan-in orchestration, task aggregation, or multi-file agent dispatch.

Context summary: This is the portable UAF replacement for host and personal skillbook parallel dispatch patterns. It should work from the repository alone and must not require any external host or skill installation. Parallelism applies to both role DAG waves and file/task worker fan-out.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Isolation strategy for parallel edits: same checkout only for read-only or proven non-overlapping writes; otherwise use `.worktrees/<task>`, an isolated branch, or an external workspace.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `python-module`.
- Implementation targets:
  - `src.orchestration.role_orchestrator`
  - `src.orchestration.agent_loop`
  - `src.tasks.workflows`
  - `src.contracts.AdapterRequest`
  - `src.contracts.AdapterResult`
  - `src.contracts.WorkflowTaskResult`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `parallel-orchestration-harness`.
3. Record the isolation decision before dispatch. For concurrent edits, prefer project-local `.worktrees/<task-or-branch>` unless the host provides an equivalent isolated workspace.
4. Call or inspect the listed Python implementation targets, then record the exact module/function path and test evidence used.
5. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
6. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
7. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- Isolation evidence: worktree root, branch/workspace names, or explicit same-checkout read-only/non-overlap rationale.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If concurrent workers can edit files and no isolation strategy exists, block safe parallel orchestration or downgrade to sequential execution.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.

## Quality bar

A valid use of `parallel-orchestration-harness` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
