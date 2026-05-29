# Orchestration Role Graph Usage Reference

This reference expands the portable operating contract for `orchestration-role-graph`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when inspecting or extending the default UAF orchestration roles such as CEO, advisor, architect, controller, implementer, reviewers, QA, security, and release.

Context summary: This is the UAF-native role contract for multi-agent orchestration. It makes leadership, advisory, design, implementation, review, verification, and release responsibilities explicit and executable instead of leaving them as prompt-only assumptions.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `python-module`.
- Implementation targets:
  - `src.orchestration.roles`
  - `src.orchestration.role_orchestrator`
  - `src.orchestration.agent_loop`
  - `src.platforms.dispatcher_factory`
  - `src.tasks.workflows`
  - `src.contracts.AdapterRequest`
  - `src.contracts.AdapterResult`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `orchestration-role-graph`.
3. Call or inspect the listed Python implementation targets, then record the exact module/function path and test evidence used.
4. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
5. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
6. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.

## Quality bar

A valid use of `orchestration-role-graph` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
