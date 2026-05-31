# KH Memory Benchmark Comparison

Date: 2026-05-31

## Compared Systems

- KH UAF `memory-state-harness`
- OpenClaw active memory and memory wiki concepts
- Hermes Agent persistent memory and session search concepts

## Findings

KH is stronger on scope isolation. Memory is resolved as project, project/chat, conversation, or explicit global, and projectless chat memory is not mixed with project memory. This matches the user's requirement that KH, New Project 2, New Project 3, and ordinary chats keep separate durable memory.

OpenClaw is stronger on active recall. Its active memory runs a bounded recall pass before the main reply for eligible persistent sessions, and its memory docs describe semantic search, keyword search, hybrid search, compaction-time memory flush, and optional background consolidation.

Hermes is stronger on prompt-budgeted always-available memory. It keeps bounded `MEMORY.md` and `USER.md` stores, injects a frozen memory snapshot at session start, uses session search for detailed past conversations, and supports external providers for deeper memory.

KH should not copy global always-on personal memory by default. For UAF work, project/chat scope and evidence quality are more important than broad personalization. The useful benchmark ideas are objective recall, compaction/resume save points, dedupe, capacity guardrails, and unsafe-memory rejection.

## Implemented KH Alignment

- `MemoryStore.search_records(...)` provides local keyword-ranked recall without external embeddings.
- `session_start_context` now returns `memory_recall` in addition to latest memory records and memory candidates.
- `workflow_usability_runtime` passes the current objective into session-start recall.
- Memory writes reject secret-like content, prompt-injection text, invisible control characters, oversized entries, and duplicates.
- Duplicate record/candidate skips are recorded as memory lifecycle events.

## Remaining Candidates

- Optional embedding-backed recall provider behind the same `MemoryStore`/`MemoryScope` contract.
- Capacity compaction for high-value memory records when the store grows beyond a configurable token budget.
- Pre-compaction memory flush hook when a host exposes an explicit compaction event.
- Human-review promotion workflow from candidates into durable records.
