---
name: goal-state-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when a UAF workflow needs objective tracking, completion criteria, blocked-state reporting, or evidence-based goal closure.
---

# Goal State Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after a validated KH GoalRuntime receipt or a correlated host-native Goal tool receipt proves that the selected runtime channel executed.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is the UAF-native goal contract for workflow completion. It gives agent runs a stable objective and evidence vocabulary so "done" means more than successful task dispatch.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Goal runtime CLI

Use the repository module, not a skill-file read, to execute the KH backend:

```powershell
python -m src.orchestration.goal_runtime start --project "<project>" --objective "<objective>" --success-criterion "<criterion>" --evidence-required "<evidence key>"
python -m src.orchestration.goal_runtime status --project "<project>"
python -m src.orchestration.goal_runtime capture-evidence --project "<project>" --evidence-type test --evidence-key "<evidence key>" --command-result-file "<result.json>"
python -m src.orchestration.goal_runtime capture-evidence --project "<project>" --evidence-type artifact --evidence-key "<evidence key>" --artifact "<artifact path>"
python -m src.orchestration.goal_runtime add-evidence --project "<project>" --envelope-json "<typed observed evidence JSON>"
python -m src.orchestration.goal_runtime update --project "<project>" --progress-note "<note>"
python -m src.orchestration.goal_runtime evaluate --project "<project>"
python -m src.orchestration.goal_runtime close --project "<project>"
```

Every GoalRuntime result includes a structured `runtime_receipt`. This cross-process local boundary replaces the previous same-process runtime claim limitation. The runtime signs receipts with a key stored under the scoped local runtime state and records consumption under the same locked boundary, so a receipt can be validated once by a later CLI process. Validation covers the objective, complete scope, mirrored state fields, state path and hashes, status, operation, result id, and timestamp before consumption. This proves durable local-runtime integrity and correlation only; external authenticity remains unverified. A path string, status string, authorization boolean, or `SKILL.md` read is not execution evidence.

## Backend policy

- `kh_ledger`: automatic KH judgment and the default. The internal CLI persists through `GoalLedger` under the UAF runtime root.
- `host_goal`: only the host can execute this channel. It requires a structured `create_goal`/`update_goal` receipt correlated to the current thread/task and objective hash, including tool call id, result id/status, timestamp, goal id, and output hash.
- `hybrid`: use both only when the KH ledger is available and the host Goal path is authorized and evidenced.
- `unavailable`: neither backend can be used; activation remains unavailable rather than being reported as applied.

Routing that says a Goal is required, KH GoalLedger execution, and host-native Goal tool execution are three distinct states. Do not represent one as another.

## Evidence envelope contract

Completion evidence uses typed envelopes: `command`, `test`, `artifact`, `review`, or `tool_receipt`. Each envelope records `asserted` or `observed`, producer, project/thread/task/goal/lineage/objective scope, timezone-aware observation time, status, and the type-specific locator, command/result identifiers, exit code/result status, and output/content hash. Use `capture-evidence` when the CLI must observe an artifact or command-result source. Raw caller JSON is not upgraded to observed evidence unless it already carries a valid scoped local-runtime integrity claim. Local integrity is durable across CLI processes; external authenticity remains unverified.

## Reference basis

- UAF `GoalState`: objective, status, success criteria, evidence requirements, collected evidence, progress notes, and blocked reason.
- UAF role graph: QA and release roles use evaluated goal evidence before reporting completion.
- Codex-style goal tracking: active, complete, and blocked states should be explicit and auditable.
- `request-complexity-router`: heavy implementation, persistent deliverables, and high-impact decisions should activate this harness.
- `development-lifecycle-harness`: implementation runs should create or refresh GoalState before editing and update it after verification.

## Workflow

1. Preserve the user's concrete objective, success criteria, and criterion-to-evidence mapping. Run `python -m src.orchestration.goal_runtime start ...` for KH state, or invoke the host-native Goal tool separately and retain its receipt.
2. Store the serialized goal at `AdapterRequest.metadata["goal"]`.
3. Preserve the goal through adapter results and workflow dispatch results.
4. Capture typed evidence from an artifact file or a command-result JSON file with `capture-evidence`. Command-result JSON must contain `command`, `command_id`, integer `exit_code`, `stdout`, and `stderr`. Plain strings and unsigned caller envelopes remain asserted or invalid and cannot close a strict runtime Goal.
5. Persist resumable goal state to the project/chat-scoped runtime `.uaf/state/current_goal.json`.
6. Append goal lifecycle events to the runtime `.uaf/state/goal_events.jsonl`.
7. Write runtime `.uaf/state/resume_handoff.json` and `.uaf/state/resume_handoff.md` after the evaluated goal is saved.
8. Write human-readable KH summaries under `.kh/goal/<run-id>/content/`, run-local state under `.kh/goal/<run-id>/state/`, and shareable summaries under `docs/kh/handoffs/` when project artifacts are enabled.
9. Add richer evidence as checks, reviews, QA, or release gates run.
10. Use `GoalState.metadata.evidence_aliases` when host-specific tools emit equivalent evidence keys with different names.
11. If the user says stop, pause, cancel, abort, or uses an equivalent stop instruction in their language, stop new work immediately, write an interruption checkpoint and scoped resume memory record, and record `metadata.user_stop_requested=true` before any automatic goal continuation can resume it.
12. For a user stop, mark the active goal `blocked` with `blocked_reason=user_requested_stop` only when the host goal tool allows blocking for stop/pause/cancel. If host policy disallows using `blocked` as pause state, do not call `update_goal`; keep the interruption checkpoint as the controlling state and ignore later automated `goal_context` until a fresh non-`goal_context` user message explicitly asks to resume.
13. Mark a goal `complete` only when every success criterion maps to valid observed evidence and every required evidence key is satisfied.
14. Mark a goal `blocked` only after the configured blocker policy sees repeated, distinct, observed, scope-matched blocker receipts. A lone reason string cannot close a Goal.
15. Reject unrelated active-Goal replacement unless an explicit replacement policy archives the current Goal first. Reject all updates, evidence additions, and close attempts after a Goal is terminal.
16. Before a final answer or host `task_complete`, validate the terminal KH or host receipt rather than trusting a path or status string.
17. If terminal receipt evidence is unavailable, do not claim completion. Preserve the active state and next required action.

## Required outputs

- `objective`: the user-facing workflow goal.
- `goal_activation`: separate routing, KH GoalLedger, and host Goal channel states plus the preserved `goal_spec`.
- `status`: `active`, `complete`, or `blocked`.
- `success_criteria`: concrete criteria for completion.
- `evidence_required`: evidence categories required before completion.
- `evidence`: observed evidence keys plus typed envelopes under metadata; asserted evidence remains visibly separate.
- `blocked_reason`: specific blocker when status is `blocked`.
- `metadata.user_stop_requested`: true when a user stop/pause/cancel request interrupted the active goal.
- `interruption_checkpoint`: `.kh/development/<run-id>/state/interruption.json` and `.kh/development/<run-id>/content/interruption.md` when the user stopped a run.
- `scoped_memory_resume_record`: project/chat-scoped durable memory record pointing to the interruption checkpoint.
- `metadata.missing_evidence`: normalized evidence keys that prevented completion.
- `metadata.evidence_alias_matches`: required evidence keys satisfied by an accepted alias.
- `goal_ledger`: paths to the project/chat-scoped current goal and event log.
- `terminal_goal_state_evidence`: a validated GoalRuntime or host-tool receipt, not merely a file path or status field.
- `resume_handoff`: paths and snapshot for continuing from runtime state without prior chat context.
- `project_markdown`: visible project-local paths for `.kh/goal/.../content/`, `.kh/goal/.../state/`, and `docs/kh/handoffs/` when written.

## Runtime storage rule

By default, do not create `.uaf/` in the target project root. Store runtime state under the UAF runtime root, normally `%LOCALAPPDATA%/KH-UAF/projects/<project-key>/.uaf/`, or under `projects/<project-key>/chats/<thread-id>/.uaf/` when a host thread id is available. `UAF_RUNTIME_ROOT` may override the base directory. `UAF_PROJECT_LOCAL_STATE=1` is the explicit opt-in for project-local `.uaf/`.

## External Benchmark Recipe

Use this harness as the final authority for completion:

1. Create or update GoalRuntime state with the exact objective, success criteria, criterion mappings, and required evidence.
2. Add only typed observed envelopes from checks, artifacts, reviews, commands, or tool receipts.
3. Persist the current Goal, events, scope identity, and content hash in the runtime state store.
4. Before completion, validate scope and structure, then compute missing mapped evidence and accepted aliases.
5. Keep the Goal active when evidence is merely missing. Close blocked only after repeated policy-qualified blocker observations.

Pressure scenario: if task dispatch succeeded but QA evidence is missing, the Goal remains active; it is not complete or blocked without blocker-policy evidence.

## Common mistakes

- Do not mark a goal complete from task success, arbitrary text, or a forged `passed` field; every criterion needs valid observed evidence.
- Do not treat `selected_not_executed_skills`, SKILL.md reads, marketplace metadata, or successful task dispatch as terminal GoalState evidence.
- Do not conflate routing, `kh_ledger`, and host `create_goal`; each channel has a distinct status and receipt.
- Do not accept nonexistent, malformed, cross-project, cross-chat, lineage-mismatched, objective-mismatched, or hash-mismatched Goal state paths.
- Do not overwrite an unrelated active Goal or mutate a complete, blocked, or archived Goal.
- Do not close blocked from a single string; require repeated policy-qualified observations.
- Do not emit a final answer or `task_complete` for goal-required work while GoalState is absent or only selected for later.
- Do not use `metadata.evidence_key` as passed evidence unless a producer emitted a real evidence record.
- Do not keep retrying a blocked workflow without updating `blocked_reason` and missing evidence.
- Do not continue implementation after the user asks to stop or pause, even if the host goal remains active or a later automated `goal_context` appears.
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
