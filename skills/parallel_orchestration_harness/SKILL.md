---
name: parallel-orchestration-harness
description: Use when a task needs bounded parallel worker execution, fan-out/fan-in orchestration, task aggregation, or multi-file agent dispatch.
---

# Parallel Orchestration Harness

This is the portable UAF replacement for Antigravity/Superpower-style parallel dispatch patterns. It should work from the repository alone and must not require any local Gemini, Antigravity, RTK, or Superpower installation.

## Workflow

1. Split the project goal into independent work items.
2. Enqueue work with a bounded worker count.
3. Dispatch each item through an adapter contract.
4. Collect all `AdapterResult` values before reporting completion.
5. Preserve partial failures as structured results instead of hiding them in logs.

## UAF implementation targets

- `src.orchestration.agent_loop`
- `src.tasks.workflows`
- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
