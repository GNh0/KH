# Workflow Usability Harness Usage

## When to use

Use this skill whenever KH has enough moving parts that the user or next session should not have to reconstruct the workflow from chat. The common trigger is a task-plan run with `.kh/development/<run-id>/state/progress.json`, but the same harness applies to long reviews, subagent packets, QA loops, token-budget decisions, session resume work, and postmortems over Codex session JSONL logs.

In AgentLoop, app bridge, and workflow dispatch paths, set `workflow_usability_auto=true` to make the runtime apply this harness automatically. The automatic path writes the same evidence as a manual helper call: session-start context, token provider policy, runtime token optimization evidence, progress panel, progress state, Compound handoff, and candidates.

This harness is also the KH-native place to absorb useful external workflow ergonomics: visible progress panels, short role command entrypoints, token provider policy, and a final Compound handoff. It should be used as a light control surface. It must not force every request through heavy role DAG execution.

## Inputs to collect

- Project root.
- Current or latest run id.
- Current `DevelopmentRunProgress` or path to `.kh/development/<run-id>/state/progress.json`.
- Task status, review status, commit SHA, active task, next task, and `token_optimizer_status`.
- Expected command volume, broad file reads, subagent transcript size, and quality-sensitive content markers.
- Optional `token_optimizer_provider`: `kh`, `rtk`, or `hybrid`. Use `token_optimizer_status=passthrough` when exact source-of-truth content must not be compressed.
- Optional role command such as `/kh:work`, `/kh:qa`, or `/kh:learn`.
- Existing `.kh` state, `docs/kh` handoffs, and scoped memory candidate store.
- Optional Codex rollout JSONL path when reviewing a finished or interrupted session.
- Any user stop/pause/cancel message and the goal status immediately after it.
- Current progress, changed files, remaining work, and scoped memory root for durable interruption resume records.

## Execution pattern

1. Build a session-start context before deep work in an existing checkout:
   `src.orchestration.session_start_context.build_session_start_context(project_root)`.
   Runtime auto mode performs this before dispatch when `workflow_usability_auto=true`.
2. If the context recommends progress, handoff, or memory files, inspect those before relying on chat recall.
3. Resolve the token optimizer provider before reading or producing large content:
   `src.orchestration.token_optimizer_provider.resolve_token_optimizer_provider(...)`.
4. Use `kh` by default. Use `hybrid` when RTK-style command optimization may be available. For exact evidence, keep the provider as `kh`, `rtk`, or `hybrid` and record `token_optimizer_status=passthrough`.
5. When task results include command output or subagent transcripts, call:
   `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results(...)`.
   Runtime auto mode performs this during `apply_workflow_usability_runtime(...)`.
6. When Compound/workflow usability produces memory candidates, call:
   `src.orchestration.runtime_memory.record_workflow_memory_candidates(...)`.
   This records candidates for scoped review and does not promote durable memory automatically.
7. Resolve a role command only when the user or workflow asks for one:
   `src.orchestration.role_commands.resolve_role_command("/kh:work")`.
8. Keep `progress.json` current while tasks move through RED, GREEN, review, fix, re-review, commit, and next task.
9. Render a visible panel with `src.orchestration.progress_panel.render_progress_panel(progress)` after meaningful task transitions.
10. After Plan, Work, and Review, convert progress to Compound artifacts with:
   `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts(project_root, progress)`.
11. Treat generated memory records as candidates unless the user explicitly approves durable memory promotion and scope.
12. Route next skills from the handoff instead of leaving them as chat-only advice.
13. When reviewing a real session, call `src.orchestration.session_postmortem.analyze_codex_session_jsonl(...)` and inspect `completion_guard`, `verification_claim_guard`, `scope_completion_delta`, `user_stop_guard`, `token_gate`, `subagent_summary`, `secret_findings`, and `git_integration`.
14. When honoring a user stop, call `src.orchestration.interruption_state.write_interruption_checkpoint(...)` to save `.kh/development/<run-id>/state/interruption.json`, `.kh/development/<run-id>/content/interruption.md`, and a scoped durable `resume-checkpoint` memory record.
15. For full skill usage review, call `src.orchestration.session_skill_audit.analyze_session_skills(...)` or `python -m src.orchestration.session_skill_audit --summary <jsonl>`.
16. Treat skill-file reads and default-prompt mentions as inspection only. Token optimizer usage requires runtime evidence such as `src.skills.token_optimizer`, command-output summarization, token-savings metadata, or explicit passthrough evidence.
17. For local dev-server checks, identify the approved runtime and entrypoint first. When the selected runtime is Streamlit on Windows, use `src.orchestration.windows_dev_server.build_streamlit_launch_plan(..., app_path=\"<approved entrypoint>\")` to avoid repeated hidden-process failures caused by Path/PATH environment quirks without assuming a dashboard layout.

## Evidence to produce

- `session_start_context` with recommended reads.
- `progress_panel` text or equivalent structured panel payload.
- `token_optimizer_provider` decision with provider-selection status and rationale, plus separate `token_optimizer_status`.
- `token_optimization` summary with workflow status, aggregate savings, preserved command/subagent records, and RTK-style `by_command_family` savings when command output was optimized.
- `memory_state` candidate recording summary with scoped store paths and promotion mode.
- `role_command_entrypoint` when used.
- `compound_capture.json`.
- `compound_handoff.json`.
- `compound_candidates.json` containing memory, skill, and scenario candidates.
- `docs/kh/handoffs/<run-id>-compound.md`.
- `required_next_skills` or explicit blocked/no-learning rationale.
- `session_postmortem` when inspecting prior Codex logs, including active-goal completion, verification-claim, scope-delta, and user-stop guard status.
- `interruption_checkpoint` plus scoped durable memory record when a user-requested stop must survive context compression.
- `session_skill_audit` when inspecting a session against all packaged KH skills.
- `token_optimizer_evidence` separating runtime calls, skill doc reads, explicit usage records, and status mentions.
- `windows_dev_server_launch_plan` when a local Windows app server must stay running for QA.

## Failure handling

- If `progress.json` is missing, report the missing path and fall back to `context-state-harness` or `goal-state-harness`.
- If progress exists but is incomplete, render the panel and mark Compound as not ready.
- If a requested RTK provider is unavailable, fall back to KH unless strict mode was requested; strict mode returns a blocked decision.
- If content is quality-sensitive, choose passthrough and record why compression would lower answer quality.
- If a role command is unknown, fail closed with the known `/kh:*` menu.
- If memory candidates contain secret-like content, do not persist them; use memory-state safety checks.
- If a user goal is still active and the session emitted completion language for a scaffold, first slice, or partial milestone, mark `completion_guard=blocked`, record `scope_completion_delta`, and continue the missing objective markers.
- If the user asked to stop, pause, cancel, or gave an equivalent stop instruction, user intent overrides later `goal_context` auto-continuation. Stop new work, write an interruption checkpoint plus scoped resume memory record, mark the active goal blocked with `blocked_reason=user_requested_stop` when host policy allows it, and record `user_stop_guard=passed`. If the host keeps the goal active because blocked is not valid pause state, the interruption checkpoint becomes the controlling state and automated `goal_context` must be ignored until a fresh non-`goal_context` user resume request. If work continued afterward, mark `user_stop_guard=blocked`.
- If a promised verification path fails or is unavailable, such as Browser/Playwright QA, mark `verification_claim_guard=blocked` unless the final report explicitly names the failed verification and residual risk.
- If token optimizer was only inspected, keep `token_optimizer_status=blocked` when the token gate requires optimization and require runtime evidence or passthrough before final completion.

## Quality bar

A good run is easy for a new session to resume. The next agent should see the latest progress, next task, review state, token decision, Compound handoff, memory candidates, and required next skills without reading the full chat. A good token policy should save context only when it preserves evidence. A good role command should route to existing KH skills instead of creating a new undocumented process.

The harness passes when it makes omissions visible. It fails if the agent can still finish a large task without recording token provider status, progress state, next skills, or resume context.

## Runtime binding

- Execution level: hybrid-harness
- Implementation targets:
  - `src.orchestration.workflow_usability_runtime.apply_workflow_usability_runtime`
  - `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts`
  - `src.orchestration.token_optimizer_provider.resolve_token_optimizer_provider`
  - `src.orchestration.runtime_memory.record_workflow_memory_candidates`
- Application path: apply the usability layer during large workflow startup, progress updates, token decisions, Compound handoff, and resume-context creation.
- Completion rule: do not report this harness as applied until progress state, token provider status, required next skills, and resume/Compound evidence are recorded or blocked.
