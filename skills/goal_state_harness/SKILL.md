---
name: goal-state-harness
description: Use when a UAF workflow needs objective tracking, completion criteria, blocked-state reporting, or evidence-based goal closure.
---

# Goal State Harness

This is the UAF-native goal contract for workflow completion. It gives agent runs a stable objective and evidence vocabulary so "done" means more than successful task dispatch.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Reference basis

- UAF `GoalState`: objective, status, success criteria, evidence requirements, collected evidence, progress notes, and blocked reason.
- UAF role graph: QA and release roles use evaluated goal evidence before reporting completion.
- Codex-style goal tracking: active, complete, and blocked states should be explicit and auditable.

## Workflow

1. Create a `GoalState` when a workflow starts.
2. Store the serialized goal at `AdapterRequest.metadata["goal"]`.
3. Preserve the goal through adapter results and workflow dispatch results.
4. Add deterministic workflow evidence such as `design_doc`, `target_files`, and `workflow dispatch completed`.
5. Persist resumable goal state to the project/chat-scoped runtime `.uaf/state/current_goal.json`.
6. Append goal lifecycle events to the runtime `.uaf/state/goal_events.jsonl`.
7. Write runtime `.uaf/state/resume_handoff.json` and `.uaf/state/resume_handoff.md` after the evaluated goal is saved.
8. Add richer evidence as checks, reviews, QA, or release gates run.
9. Use `GoalState.metadata.evidence_aliases` when host-specific tools emit equivalent evidence keys with different names.
10. Mark a goal `complete` only when success criteria and required evidence are satisfied.
11. Mark a goal `blocked` when the workflow cannot make meaningful progress without missing evidence, context, credentials, tools, or external state.

## Required outputs

- `objective`: the user-facing workflow goal.
- `status`: `active`, `complete`, or `blocked`.
- `success_criteria`: concrete criteria for completion.
- `evidence_required`: evidence categories required before completion.
- `evidence`: checks or artifacts collected so far.
- `blocked_reason`: specific blocker when status is `blocked`.
- `metadata.missing_evidence`: normalized evidence keys that prevented completion.
- `metadata.evidence_alias_matches`: required evidence keys satisfied by an accepted alias.
- `goal_ledger`: paths to the project/chat-scoped current goal and event log.
- `resume_handoff`: paths and snapshot for continuing from runtime state without prior chat context.

## Runtime storage rule

By default, do not create `.uaf/` in the target project root. Store runtime state under the UAF runtime root, normally `%LOCALAPPDATA%/KH-UAF/projects/<project-key>/.uaf/`, or under `projects/<project-key>/chats/<thread-id>/.uaf/` when a host thread id is available. `UAF_RUNTIME_ROOT` may override the base directory. `UAF_PROJECT_LOCAL_STATE=1` is the explicit opt-in for project-local `.uaf/`.

## External Benchmark Recipe

Use this harness as the final authority for completion:

1. Create or update `GoalState` with objective, success criteria, and required evidence.
2. Add evidence only from passed checks, saved artifacts, gate records, or explicit manual verification.
3. Persist current goal and event records in the runtime state store.
4. Before completion, compute missing evidence and accepted evidence aliases.
5. Mark blocked when evidence, tools, credentials, context, or external state are missing.

Pressure scenario: if task dispatch succeeded but QA evidence is missing, the goal remains active or blocked; it is not complete.

## Common mistakes

- Do not mark a goal complete from task success alone; required evidence must be present.
- Do not use `metadata.evidence_key` as passed evidence unless a producer emitted a real evidence record.
- Do not keep retrying a blocked workflow without updating `blocked_reason` and missing evidence.
- Do not write goal state into the target project root by default.

## UAF implementation targets

- `src.contracts.GoalState`
- `src.orchestration.goal_evidence`
- `src.orchestration.goal_ledger`
- `src.orchestration.handoff`
- `src.orchestration.agent_loop`
- `src.platforms.dispatcher_factory`
- `src.tasks.workflows`
- `src.contracts.WorkflowDispatchResult`
