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
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

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

1. Load a supplied project/user policy source with `load_command_policy`, or use packaged defaults when no policy is supplied.
2. Call `src.skills.command_policy.load_command_policy` and verify the returned integrity digest before trusting it.
3. Call `src.skills.command_policy.classify_command` to classify the command as read, write, network, destructive, credential-bearing, or unknown.
4. Call `src.skills.command_policy.evaluate_command_hook_policy` to apply rewrite rules, guard verdicts, integrity status, and audit records in one decision.
5. Rewrite only when the host-supplied rule is intended to be semantically equivalent and the decision records `rewrite.applied_rules`; this harness records and audits the rewrite, but the host owns semantic-equivalence approval for custom rules.
6. On parse errors, unknown protocol input, or hook failure, passthrough with an audit note instead of blocking unrelated execution.

## Audit fields

- original command
- rewritten command if any
- permission verdict
- matched policy source
- integrity status
- exit code
- fallback reason

## External Benchmark Recipe

Use this harness like a command firewall:

1. Call `classify_command` to identify read, write, destructive, network, credential, or unknown behavior.
2. Load the supplied/default policy with `load_command_policy`; record the policy hash.
3. Call `evaluate_command_hook_policy` before rewriting or executing.
4. If rewriting is allowed, record original command, redacted command, rewritten command, decision, and reason.
5. Treat policy ambiguity as `ask` or `deny`, never as silent allow.

Pressure scenario: if a command contains a token or deletes outside the workspace, the audit record must redact the secret and block or ask before execution.

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

- `src.skills.command_policy.classify_command`
- `src.skills.command_policy.evaluate_guard_policy`
- `src.skills.command_policy.evaluate_command_hook_policy`
- `src.skills.command_policy.load_command_policy`
- `src.skills.command_policy.build_command_audit_record`
- `src.skills.command_policy.redact_command`
- `src.platforms.dispatcher_factory`
- `tests.test_command_policy_runtime`
