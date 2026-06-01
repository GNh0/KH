# UAF Goal State Design

## Goal

Add a small workflow goal contract to UAF so every orchestration can carry an objective, success criteria, evidence requirements, and terminal status through adapter and workflow metadata.

## Scope

This phase adds only the reusable contract and metadata propagation:

- `GoalState` dataclass in `src.contracts`.
- Goal metadata attached by `AgentLoop` when it dispatches a workflow.
- Goal metadata preserved by local and Antigravity dispatchers.
- Workflow results include the goal metadata they received.
- `goal-state-harness` packaged skill that defines how future gates should use the contract.

This phase does not implement automatic release blocking or natural-language evidence matching. Those gates should be built after the contract is stable.

## Contract

`GoalState` fields:

- `objective`: human-readable workflow objective.
- `status`: `active`, `complete`, or `blocked`.
- `success_criteria`: list of concrete criteria the workflow is trying to satisfy.
- `evidence_required`: list of evidence categories required before completion.
- `evidence`: list of collected evidence items.
- `progress_notes`: list of short status notes.
- `blocked_reason`: reason the goal is blocked.
- `metadata`: adapter-specific or app-specific details.

The contract follows existing UAF dataclass style with `to_dict()` and `from_dict()`.

## Metadata Shape

Adapters should use `metadata["goal"]` to carry a serialized `GoalState`.

`AgentLoop` should create an active goal from the user requirement and attach it beside the existing role graph. `dispatch_project_workflow()` should preserve that goal in `WorkflowDispatchResult.metadata`. Dispatchers should include the same goal metadata in `AdapterResult.metadata`.

## Tests

Tests should prove:

- `GoalState` round-trips through dict serialization.
- `AgentLoop` creates active goal metadata from a requirement.
- Local workflow results preserve goal metadata.
- Antigravity dispatcher preserves goal metadata in pending results.
- `goal-state-harness` appears in the packaged skill catalog and validates successfully.
