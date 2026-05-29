# Quick Task Harness Usage Reference

This reference expands the portable operating contract for `quick-task-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when a task is simple enough for a single implementer without full DAG role orchestration, multi-gate review, or persistent state.

Context summary: This harness provides a zero-overhead execution path for bounded single-purpose tasks. It bypasses GoalState, MemoryStore, SnapshotManager, and RoleOrchestrator to deliver results with minimal latency and token cost.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

Quality rule: quick execution must not sacrifice correctness. If the task requires design review or multi-role coordination, escalate to full orchestration rather than producing incomplete output.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace and write boundaries.
- Whether review is requested (optional single-pass review gate).
- Complexity assessment: single-file change, bounded function, or configuration task.
- Execution level: `python-module`.
- Implementation targets:
  - `src.tasks.runners.LocalTaskRunner`
  - `src.tasks.runners.WorkflowTaskInput`
  - `src.contracts.WorkflowTaskResult`
  - `src.contracts.WorkflowDispatchResult`
  - `src.orchestration.gate_evaluators.evaluate_code_quality_gate`
  - `tests.test_task_runners`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `quick-task-harness`.
3. Assess task complexity: count expected files, roles, and gates needed.
4. If complexity is low (1-3 files, single role, 0-1 gates), proceed in quick mode.
5. Initialize only `LocalTaskRunner` with a direct `WorkflowTaskInput`.
6. Execute the implementer task without DAG scheduling.
7. If review was requested, run a single `evaluate_code_quality_gate` pass.
8. Return `WorkflowDispatchResult` with minimal metadata.
9. If complexity exceeds quick-mode bounds, return `blocked` with escalation recommendation.

## Evidence to produce

- `skill`: `quick-task-harness`.
- `execution_level`: `python-module`.
- `mode`: `quick`.
- `files_changed`: list of paths created or modified.
- `review_requested`: boolean.
- `review_result`: gate result if review was run.
- `escalated`: boolean indicating whether full mode was recommended.
- `duration_ms`: execution time in milliseconds.

## Failure handling

- If the implementer task raises an exception, capture it and return `status: failed` with the error message.
- If workspace write fails due to permissions, return `status: blocked` with the path and error.
- If complexity assessment determines the task is too complex, return `status: blocked` with `reason: complexity_escalation`.
- Never silently drop errors; all failures must appear in the result metadata.

## Quality bar

- Quick tasks must still produce syntactically valid output (parseable code, valid JSON/YAML).
- Changed files must be written to the correct workspace paths.
- If review is requested and fails, the result must include findings, not just a `failed` flag.
- Token usage should be under 20% of what full orchestration would consume for the same task.
