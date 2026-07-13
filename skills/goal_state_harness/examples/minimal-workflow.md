# Goal State Harness Minimal Workflow Example

## Scenario

A host agent receives a task where this trigger is relevant: Use when a UAF workflow needs objective tracking, completion criteria, blocked-state reporting, or evidence-based goal closure.

The agent must decide whether `goal-state-harness` applies, run or apply it according to its execution level, and leave auditable evidence.

## Expected steps

1. Load `SKILL.md` and confirm the trigger applies.
2. Read `references/usage.md` before doing the work.
3. Collect the user objective, workspace boundary, expected outputs, and evidence requirements.
4. Start the KH channel with the exact objective and criteria: `python -m src.orchestration.goal_runtime start --project "<project>" --thread-id "<thread>" --task-id "<task>" --objective "Ship the scoped change" --success-criterion "focused tests pass" --evidence-required "focused tests passed"`.
5. Validate the returned GoalRuntime receipt from a later CLI process and retain the state scope. The local integrity boundary is durable, single-use when consumed, and still labels external authenticity unverified.
6. Save the real command result as JSON with `command`, `command_id`, integer `exit_code`, `stdout`, and `stderr`, then run `capture-evidence --evidence-type test --evidence-key "focused tests passed" --command-result-file "<result.json>"`. For artifact evidence, use `--artifact "<path>"`. Unsigned caller `--envelope-json` cannot pretend to be observed.
7. Run `evaluate`, then `close` only when every criterion mapping and evidence requirement is satisfied by observed envelopes.
8. Run `python skills/goal_state_harness/scripts/demo.py --output-dir <tmp>` to execute the real success path plus asserted-evidence and single-blocker rejection cases.
9. Run `python scripts/smoke_check.py` when validating the packaged skill folder itself.

## Expected evidence

- `skill`: `goal-state-harness`.
- `execution_level`: `python-module`.
- `support_reference_read`: `references/usage.md`.
- `implementation_targets`:
  - `src.contracts.GoalState`
  - `src.orchestration.goal_evidence`
  - `src.orchestration.goal_ledger`
  - `src.orchestration.handoff`
  - `src.orchestration.agent_loop`
  - `src.platforms.dispatcher_factory`
  - `src.tasks.workflows`
  - `src.contracts.WorkflowDispatchResult`
- `actual_runtime_path`: the concrete module, workflow, policy gate, or procedural step used in this run.
- `goal_channels`: routing, KH GoalLedger, and host Goal statuses reported independently.
- `runtime_receipt`: durable local-runtime integrity plus validated project/thread/task/objective/goal/lineage/state/hash correlation for KH execution; external authenticity remains unverified.
- `host_goal_receipt`: structured host tool correlation when the host channel actually ran.
- `evidence_envelopes`: typed asserted/observed records; only valid observed records satisfy criteria.
- `verification`: command output, test result, artifact path, or explicit blocked reason.

## Failure cases

- The agent claims the skill was executed but only read `SKILL.md`.
- The agent marks a nonexistent or cross-scope Goal path as executed.
- The agent closes complete from arbitrary text or closes blocked from a lone reason.
- The agent overwrites an active Goal or mutates a terminal Goal.
- The agent treats host authorization as a host tool receipt.
- The agent reports parallel, role, state, or gate behavior without runtime-path evidence.
- The agent creates user-facing artifacts in hidden state folders or hidden state in the user output folder.
- The agent omits failed worker, gate, policy, or verification results from the final aggregate.

## Done criteria

- The trigger match is explicit.
- Required inputs and boundaries are recorded.
- The execution level is stated accurately.
- Evidence proves what actually ran or was applied.
- Missing or blocked work is represented as structured evidence, not hidden in prose.
