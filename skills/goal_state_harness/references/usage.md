# Goal State Harness Usage Reference

This reference expands the portable operating contract for `goal-state-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when a UAF workflow needs objective tracking, completion criteria, blocked-state reporting, or evidence-based goal closure.

Context summary: This is the UAF-native goal contract for workflow completion. It gives agent runs a stable objective and evidence vocabulary so "done" means more than successful task dispatch.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

## Inputs to collect

- User objective, success criteria, and any explicit completion conditions.
- Target workspace, write boundaries, and whether user-facing deliverables are expected.
- Activation source: request router, development lifecycle, role DAG, QA/release gate, resume handoff, or explicit user request.
- Required role, gate, state, artifact, or command evidence for this harness.
- Existing artifacts or state files that must be preserved rather than overwritten.
- Execution level: `python-module`.
- Implementation targets:
  - `src.contracts.GoalState`
  - `src.orchestration.goal_evidence`
  - `src.orchestration.goal_ledger`
  - `src.orchestration.handoff`
  - `src.orchestration.agent_loop`
  - `src.platforms.dispatcher_factory`
  - `src.tasks.workflows`
  - `src.contracts.WorkflowDispatchResult`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `goal-state-harness`.
3. For the default KH backend, run `python -m src.orchestration.goal_runtime start --project "<project>" --objective "<objective>" --success-criterion "<criterion>" --evidence-required "<evidence key>"`. Preserve structured `goal_spec` input rather than substituting a generic objective.
4. Use `status`, `capture-evidence`, `update`, `evaluate`, and `close` through separate invocations of that same module path. `capture-evidence --artifact` hashes an existing file. `capture-evidence --command-result-file` parses a JSON object containing `command`, `command_id`, integer `exit_code`, `stdout`, and `stderr`, then derives status and hashes the captured output. Raw `--envelope-json` input does not become observed merely because a caller labels it so.
5. Call or inspect the listed Python implementation targets, then record the exact module/function path and test evidence used.
6. Preserve intermediate decisions in typed `command`, `test`, `artifact`, `review`, or `tool_receipt` envelopes. Mark each envelope `asserted` or `observed`; only observed scope-matched envelopes satisfy criteria.
7. When project artifacts are explicitly enabled, write visible `.kh/goal/.../content/*.md`, `.kh/goal/.../state/`, and `docs/kh/handoffs/*.md` summaries in addition to runtime JSON.
8. Run `python scripts/smoke_check.py` when validating this packaged skill in the repository.
9. Report the difference between capability available in the repository and behavior actually executed in the current run.

## Backend selection

Automatic KH judgment selects `goal_backend=kh_ledger`. The KH module never executes a host Goal. Select `host_goal` only when the host tool is available and its structured receipt is correlated to the current thread/task and objective hash. Select `hybrid` only when both independently validated receipts exist. Report `unavailable` when neither path can execute.

## Receipt validation

- KH receipt: require a valid durable local-runtime HMAC plus an existing parseable state path inside the expected project/chat runtime root, matching objective, project/thread/task/goal/lineage scope, every mirrored state field, state status, goal content hash, file content hash, operation, result id, and timestamp. Validate everything before recording single-use consumption so an invalid attempt cannot burn a corrected receipt.
- Host receipt: require host, `create_goal` or `update_goal`, tool call id, result id/status, goal id, thread/task ids, objective hash, timestamp, and output hash.
- Receipt validation establishes cross-process durable local-runtime integrity and correlation, replacing the previous same-process runtime claim limitation. The local key is not an external attestation, so external authenticity remains unverified.

## Lifecycle rules

- Starting an unrelated Goal while another is active fails unless an explicit `archive_current` replacement policy archives it first.
- Complete, blocked, and archived Goals are immutable.
- Every success criterion must map to declared evidence keys, and each mapped key must have valid observed evidence before complete.
- Blocked requires repeated distinct observations carrying `repeated_observation_v1` and the same blocker code. A lone blocked reason is rejected.

## Evidence to produce

- Skill name and execution level used for the run.
- Concrete input summary and target workspace or artifact paths.
- Activation source and linked skill, such as `request-complexity-router` or `development-lifecycle-harness`.
- Implementation targets touched, imported, called, resolved by smoke check, or explicitly not needed.
- Output files, gate results, state records, or role results created by the skill.
- Goal channel evidence: routing requirement, validated KH GoalRuntime receipt, validated host Goal receipt, or both without conflation.
- Verification command or review evidence, including failures and blocked states.

## Failure handling

- If a required implementation target is missing, stop using this skill as executed evidence and report the missing target.
- If the workflow can only be applied procedurally, say so explicitly and record the policy or decision evidence.
- If parallel, role, gate, or state behavior is claimed, prove the actual runtime path instead of citing only repository support.
- If generated artifacts are incomplete, withhold completion until valid observed artifact evidence exists.
- If state integrity, scope, or receipt correlation fails, keep Goal activation pending and report the validation error; never downgrade it to executed.

## Quality bar

A valid use of `goal-state-harness` must leave enough evidence for another agent to answer: why this skill applied, what ran or was applied, what changed, and what still needs attention.
