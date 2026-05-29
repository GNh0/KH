# Bugfix Harness Usage Reference

This reference expands the portable operating contract for `bugfix-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when the task is to fix a specific bug, error, or failing test with minimal overhead and immediate test verification.

Context summary: This harness provides a focused fix-verify cycle for known bugs. It combines a single implementer pass with immediate test execution to confirm the fix, without multi-role orchestration or persistent state.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

Quality rule: a bug fix is not complete until verification passes. The fix must address the root cause, not just suppress symptoms.

## Inputs to collect

- Bug description: error message, stack trace, failing test name, or issue report.
- Target file(s) where the bug manifests.
- Verification method: test command, manual check, or expected behavior description.
- Whether code review is requested after the fix.
- Execution level: `python-module`.
- Implementation targets:
  - `src.tasks.runners.LocalTaskRunner`
  - `src.tasks.runners.WorkflowTaskInput`
  - `src.tasks.checks.CommandCheckRunner`
  - `src.tasks.checks.CommandCheckInput`
  - `src.contracts.WorkflowTaskResult`
  - `src.orchestration.gate_evaluators.evaluate_code_quality_gate`
  - `tests.test_task_runners`
  - `tests.test_check_runners`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `bugfix-harness`.
3. Parse the bug description to identify the root cause location.
4. Initialize `LocalTaskRunner` with a fix-oriented `WorkflowTaskInput`.
5. Apply the fix in the identified file(s).
6. Build a `CommandCheckInput` with the relevant test or verification command.
7. Run `CommandCheckRunner` to verify the fix.
8. If review was requested, run `evaluate_code_quality_gate` on the changed files.
9. Return result with bug description, root cause, fix summary, and test outcome.

## Evidence to produce

- `skill`: `bugfix-harness`.
- `execution_level`: `python-module`.
- `bug_description`: original error or issue.
- `root_cause`: identified cause.
- `files_changed`: modified paths.
- `test_command`: verification command used.
- `test_exit_code`: 0 for pass, non-zero for fail.
- `test_output_summary`: key lines from test output.
- `review_result`: gate result if review was run.

## Failure handling

- If root cause cannot be identified, return `status: blocked` with the analysis so far.
- If the fix is applied but verification still fails, return `status: failed` with the test output.
- If the verification command itself errors (not a test failure), return `status: blocked` with the command error.
- If the fix requires changes in multiple subsystems, return `status: blocked` with escalation recommendation.

## Quality bar

- The verification test must pass after the fix is applied.
- The fix must be minimal: only change what is necessary to resolve the bug.
- No unrelated files should be modified.
- The root cause must be documented in the result metadata.
- If review is requested and findings are produced, they must be actionable.
