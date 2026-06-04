---
name: parallel-orchestration-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when a task needs bounded parallel worker execution, fan-out/fan-in orchestration, task aggregation, or multi-file agent dispatch.
---

# Parallel Orchestration Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is the portable UAF replacement for host and personal skillbook parallel dispatch patterns. It should work from the repository alone and must not require any external host or skill installation. Parallelism applies to both role DAG waves and file/task worker fan-out.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Workflow

1. Split the project goal into role responsibilities and independent work items.
2. Decide isolation before dispatch: use project-local `.worktrees/<task-or-branch>` or a separate branch/workspace when parallel workers may edit files.
3. For concurrent write workers, `project-local-worktree` is the default safe strategy.
4. Build a role dependency DAG from the default or supplied role profiles.
5. Run all dependency-ready role tasks in the same wave concurrently.
6. Enqueue file/task work with a bounded worker count.
7. Dispatch each item through an adapter contract.
8. Collect all `WorkflowTaskResult` or `AdapterResult` values before reporting completion.
9. Preserve partial failures and blocked roles as structured results instead of hiding them in logs.

## Required metadata

- `role_orchestration.execution_model = dag-asyncio-role-waves`
- `role_orchestration.parallel_wave_count`
- `role_orchestration_stages[].waves[]`
- `role_task_results[]`
- per-result `metadata.execution_model = parallel-role-stage`
- `isolation.workspace_strategy` when workers edit files: `same-worktree-readonly`, `isolated-branch`, `project-local-worktree`, or `external-workspace`
- `isolation.worktree_root = .worktrees` when project-local worktrees are used
- final report `workspace_strategy`: `current-checkout`, `project-local-worktree`, `host-worktree`, or `isolated-branch`

## Large Work Bundle Reporting

When this skill is part of `large_work_orchestration_bundle`, record `skill_statuses["parallel-orchestration-harness"]` as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`. Always leave `parallel_strategy_decision`: parallel, sequential with rationale, read-only side agents, or blocked by shared-state risk.

When this skill was selected and user-approved implementation is about to start, `parallel_strategy_decision` is mandatory before the first write. It may be `parallel`, `sequential`, `read-only-side-agents`, or `blocked`, but it must name the reason. Silent single-agent implementation is an audit failure, even when the final work succeeds.

## External Benchmark Recipe

Use this harness only when work is actually independent:

1. Identify independent role or file tasks and shared-state conflicts before dispatch.
2. Choose the isolation strategy. For concurrent edits, prefer project-local `.worktrees/<task>` or an equivalent isolated workspace.
3. Run dependency-ready role waves with `asyncio.create_task(...)`.
4. Run file/task work through a bounded queue and worker count.
5. Fan in every result before completion.
6. Preserve partial failures and blocked records in the aggregate.

Pressure scenario: if multiple workers edit the same checkout without an isolation plan, the result may be useful work but must not be reported as safe parallel orchestration.

## Required outputs

- Bounded worker count and queue size for file/task fan-out.
- Isolation strategy and worktree/branch/workspace paths when workers can write files.
- Role DAG wave summary showing which roles ran concurrently.
- Aggregated task results with success, failure, and blocked states preserved.
- Evidence that all queued work was drained before completion was reported.

## Common mistakes

- Do not call sequential loops parallel because the code could support parallelism.
- Do not start implementation after this skill was selected without `parallel_strategy_decision`.
- Do not let one failed worker disappear from the final aggregate result.
- Do not spawn unbounded workers from user-provided file counts.
- Do not run concurrent file edits in one mutable checkout unless the tasks are proven non-overlapping.
- Do not report completion before fan-in has collected every role and worker result.

## UAF implementation targets

- `src.orchestration.role_orchestrator`
- `src.orchestration.agent_loop`
- `src.tasks.workflows`
- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.contracts.WorkflowTaskResult`
