# Subagent Review Pipeline Usage Reference

This reference expands the portable operating contract for `subagent-review-pipeline`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when coordinating implementer, spec-reviewer, and code-quality-reviewer roles for independent UAF subtasks.

Context summary: This is a personal UAF subagent coordination harness. It defines review roles and status handling without depending on external subagent plugins.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Compact task packet inputs: objective, owned files, forbidden files, checks, expected artifacts, and source context needed for each subtask.
- Token context budget inputs for large task packets, command output, or subagent transcripts.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `hybrid-harness`.
- Implementation targets:
  - `src.tasks.workflows`
  - `src.orchestration.roles`
  - `src.orchestration.agent_loop`
  - `src.orchestration.role_orchestrator.RoleOrchestrator`
  - `src.orchestration.gate_evaluators.normalize_review_findings`
  - `src.contracts.AdapterRequest`
  - `src.contracts.AdapterResult`
  - `src.skills.uaf_skill_catalog`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `subagent-review-pipeline`.
3. Create a compact task packet per implementer and keep it self-contained.
4. Apply `token-optimizer` to large task packets, command logs, or subagent transcripts before fan-out; preserve exact failures and use `passthrough` or `blocked` if compression would reduce answer quality.
5. Dispatch or simulate bounded role tasks, preserve `success`, `failed`, and `blocked` status, and normalize reviewer findings before aggregation.
6. Preserve intermediate decisions in structured evidence rather than relying on terminal logs alone.
7. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
8. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- Compact task packet and `token_optimizer_status` for any large subagent transcripts or command outputs.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until the missing artifact or exception is recorded.

## Quality bar

A valid use of `subagent-review-pipeline` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
