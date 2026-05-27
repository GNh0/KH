---
name: goal-state-harness
description: Use when a UAF workflow needs objective tracking, completion criteria, blocked-state reporting, or evidence-based goal closure.
---

# Goal State Harness

This is the UAF-native goal contract for workflow completion. It gives agent runs a stable objective and evidence vocabulary so "done" means more than successful task dispatch.

## Reference basis

- UAF `GoalState`: objective, status, success criteria, evidence requirements, collected evidence, progress notes, and blocked reason.
- UAF role graph: QA and release roles use evaluated goal evidence before reporting completion.
- Codex-style goal tracking: active, complete, and blocked states should be explicit and auditable.

## Workflow

1. Create a `GoalState` when a workflow starts.
2. Store the serialized goal at `AdapterRequest.metadata["goal"]`.
3. Preserve the goal through adapter results and workflow dispatch results.
4. Add deterministic workflow evidence such as `design_doc`, `target_files`, and `workflow dispatch completed`.
5. Persist resumable goal state to `.uaf/state/current_goal.json`.
6. Append goal lifecycle events to `.uaf/state/goal_events.jsonl`.
7. Add richer evidence as checks, reviews, QA, or release gates run.
8. Use `GoalState.metadata.evidence_aliases` when host-specific tools emit equivalent evidence keys with different names.
9. Mark a goal `complete` only when success criteria and required evidence are satisfied.
10. Mark a goal `blocked` when the workflow cannot make meaningful progress without missing evidence, context, credentials, tools, or external state.

## Required outputs

- `objective`: the user-facing workflow goal.
- `status`: `active`, `complete`, or `blocked`.
- `success_criteria`: concrete criteria for completion.
- `evidence_required`: evidence categories required before completion.
- `evidence`: checks or artifacts collected so far.
- `blocked_reason`: specific blocker when status is `blocked`.
- `metadata.missing_evidence`: normalized evidence keys that prevented completion.
- `metadata.evidence_alias_matches`: required evidence keys satisfied by an accepted alias.
- `goal_ledger`: paths to the project-local current goal and event log.

## UAF implementation targets

- `src.contracts.GoalState`
- `src.orchestration.goal_evidence`
- `src.orchestration.goal_ledger`
- `src.orchestration.agent_loop`
- `src.platforms.dispatcher_factory`
- `src.tasks.workflows`
- `src.contracts.WorkflowDispatchResult`
