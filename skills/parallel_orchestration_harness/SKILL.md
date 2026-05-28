---
name: parallel-orchestration-harness
description: Use when a task needs bounded parallel worker execution, fan-out/fan-in orchestration, task aggregation, or multi-file agent dispatch.
---

# Parallel Orchestration Harness

This is the portable UAF replacement for host and personal skillbook parallel dispatch patterns. It should work from the repository alone and must not require any external host or skill installation. Parallelism applies to both role DAG waves and file/task worker fan-out.

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

## UAF implementation targets

- `src.orchestration.role_orchestrator`
- `src.orchestration.agent_loop`
- `src.tasks.workflows`
- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.contracts.WorkflowTaskResult`
