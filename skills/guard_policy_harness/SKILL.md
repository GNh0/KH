---
name: guard-policy-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when a UAF workflow needs destructive-command warnings, directory edit boundaries, or combined safety gate policy.
---

# Guard Policy Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is a UAF-native safety harness for careful execution, edit boundary, guard, and unlock workflow patterns. It defines guard policy without installing shell hooks.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Pattern basis

- Guard workflow: destructive command warnings, directory edit locks, full guard mode, and explicit override behavior.
- UAF: sandbox workspace boundaries, command hook policy, adapter metadata, and security review roles.

## Workflow

1. Classify proposed actions with `src.skills.command_policy.classify_command`.
2. Apply permission precedence with `src.skills.command_policy.evaluate_guard_policy`: deny, ask, allow, default.
3. Enforce optional edit boundaries with `src.skills.command_policy.evaluate_write_boundary` before generated code or adapter writes files.
4. Require explicit approval for destructive actions such as recursive delete, force push, database drop, or secret exposure.
5. Record guard decisions in workflow metadata for later review.
6. Provide an unlock path that removes temporary boundaries with an audit note.

## Exact Target Path Rule

When the user names an absolute target folder, generated user-facing files must be created or updated at that exact resolved path. A workspace-local same-name folder, staging folder, temporary generated project, or relative substitute is not acceptable even if it is copied back later.

If the exact path is outside the current writable workspace or requires sandbox approval, ask for exact-path write permission before generating product files, or stop with `permission_needed`. Do not use `apply_patch` to create a relative substitute and then `Copy-Item`, `Move-Item`, or equivalent to backfill the requested path. Relative staging followed by copy-back is a guard failure.

## External Benchmark Recipe

Use this harness before any risky command or file write:

1. Resolve the intended workspace root to an absolute path.
2. Classify the command and target path before execution.
3. Run write-boundary checks for every generated or modified path.
4. Return `allow`, `ask`, or `deny` with a reason and matched policy.
5. Store only redacted command text in audit metadata.

Pressure scenario: if a generated path resolves outside the workspace through `..` or symlinks, the guard must deny the write even when the raw string looked relative.

## Required outputs

- `verdict`: `allow`, `ask`, or `deny`.
- `matched_policy`: policy source and reason.
- `scope`: allowed path roots or command family.
- `audit`: decision timestamp, actor, and override status.

## Common mistakes

- Do not rely on string-prefix path checks; resolve real paths before allowing writes.
- Do not treat network, credentials, or destructive commands as normal write actions.
- Do not silently bypass an `ask` or `deny` verdict because a workflow is otherwise ready.
- Do not record raw secrets in guard audit metadata.
- Do not create a relative same-name project folder for an absolute user target, even temporarily.
- Do not treat copying a staged project into the target as satisfying the exact target path rule.

## UAF implementation targets

- `src.skills.command_policy.classify_command`
- `src.skills.command_policy.evaluate_guard_policy`
- `src.skills.command_policy.evaluate_write_boundary`
- `src.harness.sandbox`
- `tests.test_command_policy_runtime`
