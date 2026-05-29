---
name: parallel-orchestration-harness
description: Use when a task needs bounded parallel worker execution, fan-out/fan-in orchestration, task aggregation, or multi-file agent dispatch.
---

# Parallel Orchestration Harness

This is the portable UAF replacement for host and personal skillbook parallel dispatch patterns. It should work from the repository alone and must not require any external host or skill installation. Parallelism applies to both role DAG waves and file/task worker fan-out.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Workflow

1. Split the project goal into role responsibilities and independent work items.
2. Build a role dependency DAG from the default or supplied role profiles.
3. Run all dependency-ready role tasks in the same wave concurrently.
4. Enqueue file/task work with a bounded worker count.
5. Dispatch each item through an adapter contract.
6. Collect all `WorkflowTaskResult` or `AdapterResult` values before reporting completion.
7. Preserve partial failures and blocked roles as structured results instead of hiding them in logs.

## Required metadata

- `role_orchestration.execution_model = dag-asyncio-role-waves`
- `role_orchestration.parallel_wave_count`
- `role_orchestration_stages[].waves[]`
- `role_task_results[]`
- per-result `metadata.execution_model = parallel-role-stage`

## External Benchmark Recipe

Use this harness only when work is actually independent:

1. Identify independent role or file tasks and shared-state conflicts before dispatch.
2. Run dependency-ready role waves with `asyncio.create_task(...)`.
3. Run file/task work through a bounded queue and worker count.
4. Fan in every result before completion.
5. Preserve partial failures and blocked records in the aggregate.

Pressure scenario: if the implementation loops over tasks sequentially, the result may be valid work but must not be reported as parallel orchestration.

## Required outputs

- Bounded worker count and queue size for file/task fan-out.
- Role DAG wave summary showing which roles ran concurrently.
- Aggregated task results with success, failure, and blocked states preserved.
- Evidence that all queued work was drained before completion was reported.

## Common mistakes

- Do not call sequential loops parallel because the code could support parallelism.
- Do not let one failed worker disappear from the final aggregate result.
- Do not spawn unbounded workers from user-provided file counts.
- Do not report completion before fan-in has collected every role and worker result.

## UAF implementation targets

- `src.orchestration.role_orchestrator`
- `src.orchestration.agent_loop`
- `src.tasks.workflows`
- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.contracts.WorkflowTaskResult`
