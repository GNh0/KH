---
name: adapter-contract-harness
description: Use when adding or normalizing dispatch adapters for Codex, Antigravity-style agents, Claude Code, local workers, or other agent runtimes.
---

# Adapter Contract Harness

This is a UAF-native harness. It does not call an installed external agent skill. Use external systems only as design references, then implement the portable behavior through UAF contracts.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Workflow

1. Represent incoming work with `AdapterRequest`.
2. Dispatch through a platform adapter that owns runtime-specific behavior.
3. Return `AdapterResult` with a stable `status`, `message`, optional `workflow_id`, and `metadata`.
4. Keep adapter-specific details outside orchestration code.

## External Benchmark Recipe

Use this harness before adding any new runtime adapter:

1. Map host input to `AdapterRequest` without adding host-only top-level fields.
2. Map host output to `AdapterResult(status, message, workflow_id, metadata)`.
3. Put artifacts, evidence, memory context, blocked reason, and raw host ids inside metadata.
4. Run a pending/blocked path and a success path; both must preserve request metadata.
5. Add a smoke or unit test proving the adapter can be called without the target host installed.

Pressure scenario: if the host returns a native job id but no final artifact, the adapter result is `pending` with resumable metadata, not `success`.

## Required outputs

- `AdapterRequest`: `project_dir`, `files`, `design_doc`, `platform_mode`, and metadata containing goal, memory, role, evidence, and safety context.
- `AdapterResult`: stable status, message, workflow id, metadata, evidence, and blocked/failure reason when applicable.
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
