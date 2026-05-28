---
name: memory-state-harness
description: Use when a UAF workflow needs scoped persistent memory, memory candidates, project/conversation namespace isolation, or archive/delete cleanup policy.
---

# Memory State Harness

This is the UAF-native persistent memory harness. It keeps long-lived project or conversation knowledge separate from short-lived goal state and context compression.

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
6. Append memory lifecycle events to `memory_events.jsonl`.
7. Keep active and archived conversation memories.
8. Delete or quarantine conversation memories only when the host reports deletion or the thread disappears from the host registry.
9. Never store secrets, API keys, private keys, credentials, or one-off transient prompts.

## Runtime storage rule

Do not create `.uaf/` in the target project root by default. Use `%LOCALAPPDATA%/KH-UAF/` or `UAF_RUNTIME_ROOT` for project/chat-scoped memory. `UAF_PROJECT_LOCAL_STATE=1` is the explicit opt-in for project-local runtime files.

## Required outputs

- `memory_scope`: project, conversation, or global scope with namespace and status.
- `memory_context`: bounded records loaded for the current workflow.
- `memory_store`: JSON/JSONL paths for records, candidates, events, and scope state.
- `memory_candidates`: pending records requiring later promotion.
- `cleanup_summary`: active, archived, quarantined, and deleted conversation memory results.

## UAF implementation targets

- `src.contracts.MemoryScope`
- `src.contracts.MemoryRecord`
- `src.contracts.MemoryEvent`
- `src.orchestration.memory_state`
- `src.orchestration.memory_store`
- `src.platforms.codex_thread_registry`
- `src.tasks.workflows`
