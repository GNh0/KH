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

## UAF implementation targets

- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.platforms.dispatcher_factory`
