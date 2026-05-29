---
name: adapter-contract-harness
description: Use when adding or normalizing dispatch adapters for Codex, Antigravity-style agents, Claude Code, local workers, or other agent runtimes.
---

# Adapter Contract Harness

This is a UAF-native harness. It does not call an installed external agent skill. Use external systems only as design references, then implement the portable behavior through UAF contracts.

## Workflow

1. Represent incoming work with `AdapterRequest`.
2. Dispatch through a platform adapter that owns runtime-specific behavior.
3. Return `AdapterResult` with a stable `status`, `output`, and `metadata`.
4. Keep adapter-specific details outside orchestration code.

## Required outputs

- `AdapterRequest`: normalized prompt, files, project root, platform mode, goal, role metadata, and safety metadata.
- `AdapterResult`: stable status, output text, metadata, evidence, and blocked/failure reason when applicable.
- Adapter registration entry when a new runtime is added to `DispatcherFactory`.
- Contract tests that prove serialization, blocked results, and metadata preservation.

## Common mistakes

- Do not let platform-specific payloads leak into orchestration logic; normalize them at the adapter boundary.
- Do not treat missing tool credentials as success; return a blocked result with a concrete reason.
- Do not drop goal, memory, role, or evidence metadata during dispatch.
- Do not create a new adapter shape when `AdapterRequest` and `AdapterResult` already cover the case.

## UAF implementation targets

- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.platforms.dispatcher_factory`
