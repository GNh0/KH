# Quick Task Harness Minimal Workflow Example

## Scenario

A host agent receives a task where this trigger is relevant: Use when a task is simple enough for a single implementer without full DAG role orchestration, multi-gate review, or persistent state.

The agent must decide whether `quick-task-harness` applies, run or apply it according to its execution level, and leave auditable evidence.

## Expected steps

1. Load `SKILL.md` and confirm the trigger applies (task is simple, bounded, single-purpose).
2. Read `references/usage.md` before doing the work.
3. Assess complexity: count files, roles, and gates needed. Determine quick mode is appropriate.
4. Initialize `LocalTaskRunner` directly without GoalState, MemoryStore, or RoleOrchestrator.
5. Build `WorkflowTaskInput` with the user prompt and workspace path.
6. Execute the single implementer task.
7. Optionally run `evaluate_code_quality_gate` if review was requested.
8. Return `WorkflowDispatchResult` with files_changed, summary, and status.
9. Run `python scripts/smoke_check.py` when validating the packaged skill folder itself.

## Expected evidence

- `skill`: `quick-task-harness`.
- `execution_level`: `python-module`.
- `support_reference_read`: `references/usage.md`.
- `implementation_targets`:
  - `src.tasks.runners.LocalTaskRunner`
  - `src.tasks.runners.WorkflowTaskInput`
  - `src.contracts.WorkflowTaskResult`
  - `src.contracts.WorkflowDispatchResult`
  - `src.orchestration.gate_evaluators.evaluate_code_quality_gate`
  - `tests.test_task_runners`
- `actual_runtime_path`: the concrete module, workflow, policy gate, or procedural step used in this run.
- `verification`: command output, test result, artifact path, or explicit blocked reason.

## Failure cases

- The agent claims the skill was executed but initialized full DAG orchestration anyway.
- The agent reports quick-mode execution but spent tokens on GoalState, Memory, or Snapshot.
- The agent does not escalate when the task clearly exceeds single-implementer complexity.
- The agent omits error details when the implementer task fails.
- The agent skips review when it was explicitly requested by the user.

## Done criteria

- Task completed with a single implementer pass (no DAG scheduling).
- Result includes `files_changed`, `summary`, and `status`.
- Token usage and execution time are measurably lower than full orchestration.
- If escalation was needed, result clearly indicates `blocked` with reason.
