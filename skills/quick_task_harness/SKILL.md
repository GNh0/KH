---
name: quick-task-harness
description: "Use when a task is simple enough for a single implementer without full DAG role orchestration, multi-gate review, or persistent state."
---

# Quick Task Harness

This is a lightweight UAF harness for simple, bounded tasks that do not require the full role DAG, multi-gate review pipeline, or persistent GoalState/Memory/Snapshot infrastructure. It runs a single implementer role, applies only the gates the user explicitly requests, and produces minimal output.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## When to use

- Single-purpose requests: "write a function", "add a config file", "fix this error"
- Tasks with clear completion criteria that one implementer can satisfy
- Situations where full orchestration overhead exceeds the task complexity
- Quick prototyping or exploration tasks

## When NOT to use

- Multi-file architecture changes requiring design review
- Tasks needing security audit or compliance gates
- Long-running projects requiring state persistence or handoff
- Tasks that need multiple specialized roles (architect, QA, security)

## Workflow

1. Receive prompt and workspace path.
2. Classify complexity: if the task fits a single bounded action, proceed in quick mode.
3. Skip GoalState, MemoryStore, SnapshotManager, and RoleOrchestrator initialization.
4. Run a single implementer worker with the prompt directly.
5. Optionally run a single-pass review if `--review` is specified.
6. Return result with minimal metadata: files changed, summary, and success/failure status.

## Required outputs

- `status`: `passed`, `failed`, or `blocked`.
- `files_changed`: list of created or modified file paths.
- `summary`: one-paragraph description of what was done.
- `review`: optional single-pass review finding (only if review gate was requested).

## Common mistakes

- Do not initialize full DAG orchestration for a task that only needs one file change.
- Do not skip this harness and use full orchestration when the user explicitly requests quick mode.
- Do not omit error reporting; even quick tasks must report failure clearly.
- Do not persist GoalState or Memory for ephemeral quick tasks unless explicitly requested.
- Do not escalate to full mode silently; inform the user if the task appears too complex for quick mode.

## Escalation path

If during execution the task is found to require multiple roles, design review, or persistent state:
1. Report `status: blocked` with `reason: complexity_escalation`.
2. Recommend switching to full orchestration mode.
3. Preserve any partial work already completed.

## UAF implementation targets

- `src.tasks.runners.LocalTaskRunner`
- `src.tasks.runners.WorkflowTaskInput`
- `src.contracts.WorkflowTaskResult`
- `src.contracts.WorkflowDispatchResult`
- `src.orchestration.gate_evaluators.evaluate_code_quality_gate`
- `tests.test_task_runners`
