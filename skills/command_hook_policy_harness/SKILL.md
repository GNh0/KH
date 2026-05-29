---
name: command-hook-policy-harness
description: Use when defining UAF command rewrite hooks, trust checks, permission precedence, integrity verification, or non-blocking hook behavior.
---

# Command Hook Policy Harness

This is a personal UAF hook and permission harness for command rewrite, trust, and safety policy. It must not install or require external hooks by default.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Reference basis

- Command hook patterns: agent command hooks, permission precedence, integrity verification, audit/trust checks, and fail-safe command passthrough.
- Host SDK patterns: lifecycle hooks, tool permissions, and safety policy routing.

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

## Required outputs

- Command classification: read, write, network, destructive, credential-bearing, or unknown.
- Permission verdict with matched policy source and precedence level.
- Rewrite decision with original command, rewritten command, or passthrough reason.
- Audit record that preserves integrity status and command exit semantics.

## Common mistakes

- Do not rewrite a command unless the replacement is semantically equivalent and auditable.
- Do not block unrelated execution because a hook parser failed; passthrough with an audit note.
- Do not allow destructive commands through default policy without explicit approval.
- Do not hide credential-like content in audit logs; redact while preserving the reason.

## UAF implementation targets

- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.platforms.dispatcher_factory`
- `src.orchestration.agent_loop`
- `src.skills.uaf_skill_catalog`
