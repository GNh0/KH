---
name: credential-safety-harness
description: Use when a task will read, create, update, transmit, validate, or expose actual credentials, API keys, tokens, connection strings, secret-bearing environment variables, or commands that may reveal them. Do not invoke merely because an already-configured MCP, database, API, or connector is used.
---

# Credential Safety Harness

## KH Entry Contract

- This skill is not a generic MCP, database, API, plugin, or subagent preflight.
- Select it only when the task accesses or changes secret material/configuration, verifies credential presence, accepts hidden credential input, or proposes a command that could expose a secret.
- Calling an already-configured MCP/database/API/connector through its normal tool interface is not credential handling and must not load this skill.
- If this skill appears only in `selected_not_executed_skills`, report it as selected but not run until credential safety evidence exists.
- Report this skill as `applied` only after a safe presence plan, command classification, validation result, explicit passthrough, or blocked rationale exists.
- Reading this `SKILL.md`, listing the skill, or saying "credential safety applies" is not execution evidence.
- Keep internal credential-safety status out of ordinary user-facing narration. Explain only a block, required outside-chat setup, or explicitly requested audit.

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

These outputs remain internal unless the user must resolve a blocked credential step or explicitly requested an audit.

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
- Do not load or report this harness merely because a configured MCP or database connection was used successfully.

## UAF implementation targets

- `src.skills.credential_safety.CredentialSafetyPlan`
- `src.skills.credential_safety.build_credential_safety_plan`
- `src.skills.credential_safety.classify_credential_command`
- `src.skills.credential_safety.validate_credential_safety_plan`
- `tests.test_credential_safety_harness`
