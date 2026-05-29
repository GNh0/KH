# Bugfix Harness Minimal Workflow Example

## Scenario

A host agent receives a task where this trigger is relevant: Use when the task is to fix a specific bug, error, or failing test with minimal overhead and immediate test verification.

The agent must decide whether `bugfix-harness` applies, run or apply it according to its execution level, and leave auditable evidence.

## Expected steps

1. Load `SKILL.md` and confirm the trigger applies (task is a bug fix with identifiable error).
2. Read `references/usage.md` before doing the work.
3. Parse the bug description to identify root cause and target file(s).
4. Apply the fix using `LocalTaskRunner` with a fix-oriented task input.
5. Build and run a `CommandCheckRunner` verification (e.g., `python -m pytest tests/test_module.py`).
6. Confirm test passes (exit code 0).
7. Optionally run single-pass review if requested.
8. Return result with bug_description, root_cause, files_changed, fix_summary, test_result.
9. Run `python scripts/smoke_check.py` when validating the packaged skill folder itself.

## Expected evidence

- `skill`: `bugfix-harness`.
- `execution_level`: `python-module`.
- `support_reference_read`: `references/usage.md`.
- `implementation_targets`:
  - `src.tasks.runners.LocalTaskRunner`
  - `src.tasks.runners.WorkflowTaskInput`
  - `src.tasks.checks.CommandCheckRunner`
  - `src.tasks.checks.CommandCheckInput`
  - `src.contracts.WorkflowTaskResult`
  - `src.orchestration.gate_evaluators.evaluate_code_quality_gate`
  - `tests.test_task_runners`
  - `tests.test_check_runners`
- `actual_runtime_path`: the concrete module, workflow, policy gate, or procedural step used in this run.
- `verification`: command output, test result, artifact path, or explicit blocked reason.

## Failure cases

- The agent claims the bug is fixed but did not run any verification command.
- The agent modifies unrelated files during the fix.
- The agent reports success but the test still fails.
- The agent uses full DAG orchestration for a single-file bug fix.
- The agent cannot identify root cause but proceeds with a speculative fix without marking it as uncertain.

## Done criteria

- Bug fix applied to the correct file(s).
- Verification test passes (exit code 0).
- Result includes root cause, fix summary, and test evidence.
- No orchestration state (GoalState, Memory, Snapshot) was created for this fix.
