---
name: bugfix-harness
description: "Use when the task is to fix a specific bug, error, or failing test with minimal overhead and immediate test verification."
---

# Bugfix Harness

This is a lightweight UAF harness optimized for bug-fixing tasks. It uses a single implementer with an optional reviewer, runs targeted test verification, and reports pass/fail without full orchestration overhead.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## When to use

- Fixing a specific error message or exception
- Making a failing test pass
- Patching a known regression
- Correcting a configuration or dependency issue
- Any task framed as "fix X" or "resolve error Y"

## Workflow

1. Receive the bug description: error message, stack trace, failing test, or issue report.
2. Identify the target file(s) and the root cause location.
3. Apply the fix using a single implementer pass.
4. Run the relevant test or verification command to confirm the fix.
5. Optionally run a single-pass code review if requested.
6. Return result with fix summary, files changed, and test outcome.

## Required outputs

- `status`: `passed`, `failed`, or `blocked`.
- `bug_description`: the original error or issue being fixed.
- `root_cause`: identified cause of the bug.
- `files_changed`: list of modified file paths.
- `fix_summary`: one-paragraph description of the fix.
- `test_result`: pass/fail outcome of the verification test.
- `test_command`: the command used for verification (if any).

## Common mistakes

- Do not apply a fix without running verification; a fix that is not tested is not confirmed.
- Do not use full DAG orchestration for a simple one-file bug fix.
- Do not ignore the original error message when identifying root cause.
- Do not modify unrelated files as part of a targeted bug fix.
- Do not report success if the verification test still fails after the fix.

## Escalation path

If the bug requires changes across multiple subsystems or architectural decisions:
1. Report `status: blocked` with `reason: complexity_escalation`.
2. Recommend switching to full orchestration or quick-task-harness with review.
3. Preserve the root cause analysis already completed.

## UAF implementation targets

- `src.tasks.runners.LocalTaskRunner`
- `src.tasks.runners.WorkflowTaskInput`
- `src.tasks.checks.CommandCheckRunner`
- `src.tasks.checks.CommandCheckInput`
- `src.contracts.WorkflowTaskResult`
- `src.orchestration.gate_evaluators.evaluate_code_quality_gate`
- `tests.test_task_runners`
- `tests.test_check_runners`
