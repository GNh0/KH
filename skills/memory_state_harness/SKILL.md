---
name: memory-state-harness
description: Use when a UAF workflow needs scoped persistent memory, memory candidates, project/conversation namespace isolation, or archive/delete cleanup policy.
---

# Memory State Harness

This is the UAF-native persistent memory harness. It keeps long-lived project or conversation knowledge separate from short-lived goal state and context compression.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Reference basis

- UAF `MemoryScope`, `MemoryRecord`, and `MemoryEvent` contracts.
- Hermes/OpenClaw-style persistent memory concepts, adapted as host-neutral scoped memory.
- Codex desktop thread registry behavior: active and archived threads can be detected from the host registry when available; deleted threads are inferred by absence or explicit host events.

## Workflow

1. Resolve memory scope before dispatch:
   - project workspace present: use project-scoped runtime `.uaf/memory/`.
   - project workspace plus host thread id: use project/chat-scoped runtime `.uaf/memory/`.
   - projectless chat: use `conversations/<thread_id>/.uaf/memory/`.
   - global memory: require explicit user promotion.
2. Load scoped memory context and attach it to `AdapterRequest.metadata["memory_context"]`.
3. Preserve memory context inside `GoalState.metadata["memory_context"]` so the goal ledger can resume with the same long-term context.
4. Save verified project decisions as `MemoryRecord(kind="decision")`.
5. Save uncertain lessons as candidates first, not committed memory.
6. When workflow usability or Compound produces `memory_candidates`, call `src.orchestration.runtime_memory.record_workflow_memory_candidates` so the scoped candidate store can be read by the next session.
7. When the user explicitly stops an active workflow, save a durable scoped `MemoryRecord(kind="resume-checkpoint")` through `src.orchestration.interruption_state.write_interruption_checkpoint`; this is operational resume state, not global personal memory.
8. Append memory lifecycle events to `memory_events.jsonl`.
9. Keep active and archived conversation memories.
10. Delete or quarantine conversation memories only when the host reports deletion or the thread disappears from the host registry.
11. Never store secrets, API keys, private keys, credentials, or one-off transient prompts.

## Runtime storage rule

Do not create `.uaf/` in the target project root by default. Use `%LOCALAPPDATA%/KH-UAF/` or `UAF_RUNTIME_ROOT` for project/chat-scoped memory. `UAF_PROJECT_LOCAL_STATE=1` is the explicit opt-in for project-local runtime files.

## Large Work Bundle Reporting

When this skill is part of `large_work_orchestration_bundle`, record `skill_statuses["memory-state-harness"]` as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`. Large work should at least decide whether scoped `memory_candidates` are needed; do not promote candidates to durable memory without the required scope and approval.

## External Benchmark Recipe

Use this harness only for durable, scoped facts:

1. Resolve scope before reading memory: project, project/chat, conversation, or explicit global.
2. Load only bounded records relevant to the current objective.
3. Save verified decisions as records and uncertain observations as candidates.
4. Record event type, source, scope, and retention action in `memory_events.jsonl`.
5. Revalidate memory-derived facts when they can drift.

Pressure scenario: if a fact came from an older conversation and the source may have changed, report it as memory-derived and require fresh verification before using it as completion evidence.

## Required outputs

- `memory_scope`: project, conversation, or global scope with namespace and status.
- `memory_context`: bounded records loaded for the current workflow.
- `memory_store`: JSON/JSONL paths for records, candidates, events, and scope state.
- `memory_candidates`: pending records requiring later promotion.
- `resume_checkpoint`: durable scoped memory record pointing to the latest interruption checkpoint when a user stop must survive context compression.
- `memory_state`: candidate recording status with recorded, skipped, blocked, and promotion mode.
- `cleanup_summary`: active, archived, quarantined, and deleted conversation memory results.

## Common mistakes

- Do not mix project memory and conversation memory in one namespace.
- Do not persist secrets, credentials, or raw private outputs as durable memory.
- Do not rely on compressed chat context after a stop; load the scoped `resume-checkpoint` and its `.kh` interruption file first.
- Do not delete memory for archived conversations without checking the thread registry when available.
- Do not treat memory-derived facts as current truth without revalidation when they can drift.

## UAF implementation targets

- `src.contracts.MemoryScope`
- `src.contracts.MemoryRecord`
- `src.contracts.MemoryEvent`
- `src.orchestration.memory_state`
- `src.orchestration.memory_store`
- `src.orchestration.runtime_memory`
- `src.orchestration.interruption_state`
- `src.platforms.codex_thread_registry`
- `src.tasks.workflows`
