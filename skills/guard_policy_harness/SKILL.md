---
name: guard-policy-harness
description: Use when a UAF workflow needs destructive-command warnings, directory edit boundaries, or combined safety gate policy.
---

# Guard Policy Harness

This is a UAF-native safety harness for careful execution, edit boundary, guard, and unlock workflow patterns. It defines guard policy without installing shell hooks.

## Pattern basis

- Guard workflow: destructive command warnings, directory edit locks, full guard mode, and explicit override behavior.
- UAF: sandbox workspace boundaries, command hook policy, adapter metadata, and security review roles.

## Workflow

1. Classify proposed actions as read, write, network, destructive, credential-bearing, or unknown.
2. Apply permission precedence: deny, ask, allow, default.
3. Enforce optional edit boundaries before generated code or adapter writes files.
4. Require explicit approval for destructive actions such as recursive delete, force push, database drop, or secret exposure.
5. Record guard decisions in workflow metadata for later review.
6. Provide an unlock path that removes temporary boundaries with an audit note.

## Required outputs

- `verdict`: `allow`, `ask`, or `deny`.
- `matched_policy`: policy source and reason.
- `scope`: allowed path roots or command family.
- `audit`: decision timestamp, actor, and override status.

## UAF implementation targets

- `src.harness.sandbox`
- `src.platforms.dispatcher_factory`
- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `skills/command_hook_policy_harness/SKILL.md`
