---
name: credential-safety-harness
description: Use when kh-uaf:always-on-front-door has already run and a UAF workflow, helper script, API call, MCP server, plugin, or subagent needs credentials, API keys, tokens, connection strings, or secret-bearing environment variables; verify presence without reading or printing secret values and block secret exposure commands.
---

# Credential Safety Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, another selected KH skill, or a helper script requires credentials or secret-bearing settings.
- If this skill appears only in `selected_not_executed_skills`, report it as selected but not run until credential safety evidence exists.
- Report this skill as `applied` only after a safe presence plan, command classification, validation result, explicit passthrough, or blocked rationale exists.
- Reading this `SKILL.md`, listing the skill, or saying "credential safety applies" is not execution evidence.

This harness imports the useful Science Skills credential pattern into KH without depending on Antigravity or local science folders. It checks only whether a credential exists. It must never print, read, summarize, store in chat, pass as a CLI argument, or expose a secret value to the agent context.

## Support files

- Read `references/usage.md` before applying this skill to real work; it defines trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` to verify the success and blocked cases.
- Run `python scripts/smoke_check.py` from this skill folder to verify support-file wiring and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo.

## Workflow

1. Identify the exact credential name and why it is needed.
2. Build a safe plan with `src.skills.credential_safety.build_credential_safety_plan`.
3. Validate the plan with `src.skills.credential_safety.validate_credential_safety_plan`.
4. For any proposed command touching `.env`, environment variables, tokens, API keys, or connection strings, classify it with `src.skills.credential_safety.classify_credential_command`.
5. Allow only presence checks and hidden-input setup commands. Block commands that print or read secret values.
6. If the credential is missing, ask the user to add it outside chat using the generated hidden-input command. Do not ask the user to paste a key into chat.
7. Record `credential_safety_status` as `passed`, `blocked`, `passthrough`, or `considered_not_needed`.

## Required outputs

- `credential_safety_status`.
- Credential name, secret scope, and environment file path without the secret value.
- Safe check command or explicit reason no credential access is needed.
- Validation result and command classification.
- Blocked reason when a command might expose secret values.

## Common mistakes

- Do not run `cat ~/.env`, `type .env`, `Get-Content .env`, `echo $TOKEN`, `echo $env:TOKEN`, or `printenv TOKEN`.
- Do not ask the user to paste API keys or passwords into chat.
- Do not pass secret values as command-line arguments.
- Do not store secret values in KH memory, GoalState, progress panels, artifacts, or subagent packets.
- Do not claim a credential exists unless the presence check succeeded or the user confirms it externally.

## UAF implementation targets

- `src.skills.credential_safety.CredentialSafetyPlan`
- `src.skills.credential_safety.build_credential_safety_plan`
- `src.skills.credential_safety.classify_credential_command`
- `src.skills.credential_safety.validate_credential_safety_plan`
- `tests.test_credential_safety_harness`
