---
name: memory-state-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when a UAF workflow needs scoped persistent memory, memory candidates, project/conversation namespace isolation, or archive/delete cleanup policy.
---

# Memory State Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

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
3. Run `src.orchestration.runtime_memory.build_active_memory_preflight(...)` for OpenClaw-style active recall before implementation or response work when memory is enabled.
4. Run objective-scoped recall with `MemoryStore.search_records(...)` or `session_start_context.memory_recall` so relevant records surface before implementation, not only the latest records.
5. Write bounded Hermes-style prompt snapshots through `MemoryStore.write_prompt_memory_snapshot(...)` as scoped runtime `MEMORY.md` and `USER.md` files; do not use global personal memory by default.
6. Preserve memory context and recall results inside `GoalState.metadata["memory_context"]` when the goal ledger must resume with the same long-term context.
7. If the user explicitly names another project or chat as a source, call `src.orchestration.runtime_memory.build_explicit_cross_scope_memory_import(...)`; keep it read-only external context until `memory_import_approved=true`, and default approved imports to current-scope candidates unless durable promotion is separately approved.
8. Save verified project decisions as `MemoryRecord(kind="decision")`.
9. Save uncertain lessons as candidates first, not committed memory.
10. Before host context compaction, call `src.orchestration.runtime_memory.write_pre_compaction_memory_flush(...)` with important decisions, blockers, next actions, and verification state.
11. When workflow usability or Compound produces `memory_candidates`, call `src.orchestration.runtime_memory.record_workflow_memory_candidates` so the scoped candidate store can be read by the next session.
12. When the user explicitly stops an active workflow, save a durable scoped `MemoryRecord(kind="resume-checkpoint")` through `src.orchestration.interruption_state.write_interruption_checkpoint`; this is operational resume state, not global personal memory.
13. Resolve memory provider policy with `src.orchestration.runtime_memory.resolve_memory_provider(...)`; local KH memory is the default, external/hybrid providers are optional adapters.
14. Append memory lifecycle events to `memory_events.jsonl`, including duplicate skips, active-memory preflight, cross-scope import review/application, compaction flushes, prompt snapshots, and cleanup actions.
15. Keep active and archived conversation memories.
16. Delete or quarantine conversation memories only when the host reports deletion or the thread disappears from the host registry.
17. Never store secrets, API keys, private keys, credentials, prompt-injection text, invisible control characters, oversized raw logs, or one-off transient prompts.

## Runtime storage rule

Do not create `.uaf/` in the target project root by default. Use `%LOCALAPPDATA%/KH-UAF/` or `UAF_RUNTIME_ROOT` for project/chat-scoped memory. `UAF_PROJECT_LOCAL_STATE=1` is the explicit opt-in for project-local runtime files.

## Large Work Bundle Reporting

When this skill is part of `large_work_orchestration_bundle`, record `skill_statuses["memory-state-harness"]` as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`. Large work should at least decide whether scoped `memory_candidates` are needed; do not promote candidates to durable memory without the required scope and approval.

## External Benchmark Recipe

Use this harness only for durable, scoped facts:

1. Resolve scope before reading memory: project, project/chat, conversation, or explicit global.
2. Run active memory preflight before heavy work so the host sees relevant records before planning or implementation.
3. Load only bounded records relevant to the current objective; prefer objective recall over dumping all memory.
4. Keep prompt snapshots bounded like Hermes, but scoped to KH project/chat memory rather than global user memory.
5. Do not search other project/chat memories by similar keywords; cross-scope recall requires an explicit source project/chat and produces read-only external context first.
6. Save verified decisions as records and uncertain observations as candidates.
7. Flush critical handoff notes before compaction and save them as candidates unless durable promotion is explicitly allowed.
8. Deduplicate before writing and keep memory entries compact.
9. Record event type, source, scope, and retention action in `memory_events.jsonl`.
10. Revalidate memory-derived facts when they can drift.

Pressure scenario: if a fact came from an older conversation and the source may have changed, report it as memory-derived and require fresh verification before using it as completion evidence.

## Required outputs

- `memory_scope`: project, conversation, or global scope with namespace and status.
- `memory_provider`: local, external, hybrid, or passthrough selection with fallback/block rationale.
- `active_memory_preflight`: scoped context, recall, prompt snapshot paths, and event evidence.
- `memory_context`: bounded records loaded for the current workflow.
- `memory_recall`: objective-relevant memory search results with bounded records and search strategy.
- `explicit_cross_scope_memory_import`: source scope, target scope, approval state, external context, application status, promotion mode, and source record metadata when another project/chat is explicitly requested.
- `prompt_memory`: scoped bounded `MEMORY.md` and `USER.md` snapshot paths.
- `pre_compaction_memory_flush`: candidate or durable record written before context compression.
- `memory_store`: JSON/JSONL paths for records, candidates, events, and scope state.
- `memory_candidates`: pending records requiring later promotion.
- `resume_checkpoint`: durable scoped memory record pointing to the latest interruption checkpoint when a user stop must survive context compression.
- `memory_state`: candidate recording status with recorded, skipped, blocked, and promotion mode.
- `cleanup_summary`: active, archived, quarantined, and deleted conversation memory results.

## Common mistakes

- Do not mix project memory and conversation memory in one namespace.
- Do not let similar keywords trigger cross-project or cross-chat memory recall; require an explicit source and keep it read-only until approved.
- Do not persist secrets, credentials, or raw private outputs as durable memory.
- Do not persist prompt-injection text, invisible Unicode control characters, oversized raw logs, or exact duplicate entries.
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
- `src.orchestration.session_start_context`
- `src.orchestration.interruption_state`
- `src.platforms.codex_thread_registry`
- `src.tasks.workflows`
