# UAF Persistent Goal Ledger Design

## Goal

Add a project-local persistent goal ledger so UAF can resume workflow intent, task status, required evidence, collected evidence, and next action after context compaction, process restart, or a new agent session.

## Scope

This phase adds the storage layer and local workflow wiring:

- `src/orchestration/goal_ledger.py`
- `.uaf/state/current_goal.json`
- `.uaf/state/goal_events.jsonl`
- workflow dispatch writes the initial and evaluated goal states when goal metadata is present
- `.uaf/` is ignored by git

This phase does not implement a CLI command for inspecting the ledger and does not change Antigravity native dispatch behavior.

## State Files

`current_goal.json` is the compact state snapshot agents should read first:

- `schema_version`
- `objective`
- `status`
- `active_task`
- `tasks.pending`
- `tasks.in_progress`
- `tasks.completed`
- `tasks.blocked`
- `evidence_required`
- `evidence`
- `blocked_reason`
- `next_recommended_action`
- `goal`
- `updated_at`

`goal_events.jsonl` is append-only audit history. Each line has:

- `event_type`
- `timestamp`
- `payload`

Supported event types in this phase:

- `goal_created`
- `goal_updated`
- `goal_completed`
- `goal_blocked`
- `evidence_added`

## Safety

Ledger writes must stay inside the project root. Any path helper should reject `..` traversal or absolute paths outside the project. Runtime ledger files live under `.uaf/`, and `.uaf/` should not be committed.

## Workflow Integration

When `dispatch_project_workflow()` receives `metadata["goal"]`:

1. Create or update `.uaf/state/current_goal.json` before worker execution.
2. Append `goal_created` when no current goal exists, otherwise `goal_updated`.
3. After goal evidence evaluation, update `current_goal.json`.
4. Append `goal_completed` or `goal_blocked` based on evaluated status.
5. Include ledger paths in `WorkflowDispatchResult.metadata["goal_ledger"]`.

## Tests

Tests should prove:

- `GoalLedger` saves and loads `current_goal.json`.
- `GoalLedger` appends JSONL events in order.
- `GoalLedger` rejects project path traversal.
- workflow dispatch writes evaluated goal state to `.uaf/state/current_goal.json`.
- workflow dispatch returns ledger metadata paths.
