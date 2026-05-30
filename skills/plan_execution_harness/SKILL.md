---
name: plan-execution-harness
description: Use when a written UAF task plan must be executed task by task with progress state, RED/GREEN checks, reviews, commits, and next-task handoff.
---

# Plan Execution Harness

This is the KH-native plan execution workflow. It turns a written plan into a controlled task loop with progress state, evidence, review checkpoints, branch finishing, and resumable next-task handoff.

It replaces external executing-plans style workflows with KH `progress.json`, GoalState, token decisions, review gates, and Compound handoff.

## Support files

- Read `references/usage.md` before applying this skill to real task-plan execution.
- Use `examples/minimal-workflow.md` as a compact scenario for task-by-task implementation.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the packaged KH skill demo path.

## Workflow

1. Confirm the written plan, task list, owned files, forbidden files, verification commands, and acceptance criteria.
2. Initialize or load `.kh/development/<run-id>/state/progress.json`.
3. Select workspace strategy through `worktree-isolation-harness`.
4. For each task, record status transitions: pending, in_progress, RED, GREEN, review, fixing, re_review, committed, blocked, or complete.
5. Apply TDD and quality gates for behavior changes.
6. Dispatch subagents only when the task has independent scope, bounded packets, and isolation evidence.
7. Run spec review before code-quality review; preserve findings and fixes.
8. Commit task-sized changes when branch finishing policy allows.
9. Update `next_task`, token optimizer status, review status, and goal evidence after each meaningful transition.
10. After review completion, route to Compound, memory candidates, scenario regression, or no-learning rationale.

## Required outputs

- `plan_execution_status`: `active`, `blocked`, `complete`, or `partial`.
- Progress state path and latest task status.
- Task packets or single-controller rationale.
- RED/GREEN evidence or no-test rationale per behavior-changing task.
- Spec review, code-quality review, fix, and re-review status.
- Commit SHA per committed task when applicable.
- `next_task`, missing evidence, and resume handoff.

## Common mistakes

- Do not execute a multi-task plan only from chat without progress state.
- Do not skip review checkpoints because tests pass.
- Do not dispatch subagents without bounded packets and workspace isolation.
- Do not mark the full plan complete when only one milestone or scaffold is done.
- Do not leave Compound or memory candidates as chat-only suggestions.

## UAF implementation targets

- `src.orchestration.development_progress.DevelopmentTaskProgress`
- `src.orchestration.progress_panel.render_progress_panel`
- `src.orchestration.skill_transitions.validate_skill_transitions`
- `skills/plan_execution_harness/SKILL.md`
