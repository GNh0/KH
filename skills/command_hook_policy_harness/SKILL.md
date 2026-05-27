---
name: command-hook-policy-harness
description: Use when defining UAF command rewrite hooks, trust checks, permission precedence, integrity verification, or non-blocking hook behavior.
---

# Command Hook Policy Harness

This is a UAF-native hook and permission harness derived from RTK hook architecture and Antigravity prompt-level command guidance. It must not install or require external hooks by default.

## Reference basis

- RTK: agent command hooks, permission precedence, integrity verification, audit/trust checks, and fail-safe command passthrough.
- Google Antigravity SDK: lifecycle hooks, tool permissions, and safety policy routing.

## Permission precedence

Apply permission rules in this order:

1. `deny`
2. `ask`
3. `allow`
4. `default`

The default should be conservative for destructive actions and non-blocking for read-only observation commands.

## Hook workflow

1. Load project-local policy, then user policy, then packaged defaults.
2. Verify hook or policy integrity before trusting it.
3. Classify the command as read, write, network, destructive, credential-bearing, or unknown.
4. Apply the permission verdict and record the reason.
5. Rewrite only when the rewritten command is semantically equivalent.
6. On parse errors, unknown protocol input, or hook failure, passthrough with an audit note instead of blocking unrelated execution.

## Audit fields

- original command
- rewritten command if any
- permission verdict
- matched policy source
- integrity status
- exit code
- fallback reason

## UAF implementation targets

- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.platforms.dispatcher_factory`
- `src.orchestration.agent_loop`
- `src.skills.uaf_skill_catalog`
