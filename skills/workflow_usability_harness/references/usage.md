# Workflow Usability Harness Usage

## When to use

Use this skill whenever KH has enough moving parts that the user or next session should not have to reconstruct the workflow from chat. The common trigger is a task-plan run with `.kh/development/<run-id>/state/progress.json`, but the same harness applies to long reviews, subagent packets, QA loops, token-budget decisions, and session resume work.

In AgentLoop, app bridge, and workflow dispatch paths, set `workflow_usability_auto=true` to make the runtime apply this harness automatically. The automatic path writes the same evidence as a manual helper call: session-start context, token provider policy, progress panel, progress state, Compound handoff, and candidates.

This harness is also the KH-native place to absorb useful external workflow ergonomics: visible progress panels, short role command entrypoints, token provider policy, and a final Compound handoff. It should be used as a light control surface. It must not force every request through heavy role DAG execution.

## Inputs to collect

- Project root.
- Current or latest run id.
- Current `DevelopmentRunProgress` or path to `.kh/development/<run-id>/state/progress.json`.
- Task status, review status, commit SHA, active task, next task, and `token_optimizer_status`.
- Expected command volume, broad file reads, subagent transcript size, and quality-sensitive content markers.
- Optional `token_optimizer_provider`: `kh`, `rtk`, `hybrid`, or `passthrough`.
- Optional role command such as `/kh:work`, `/kh:qa`, or `/kh:learn`.
- Existing `.kh` state, `docs/kh` handoffs, and scoped memory candidate store.

## Execution pattern

1. Build a session-start context before deep work in an existing checkout:
   `src.orchestration.session_start_context.build_session_start_context(project_root)`.
   Runtime auto mode performs this before dispatch when `workflow_usability_auto=true`.
2. If the context recommends progress, handoff, or memory files, inspect those before relying on chat recall.
3. Resolve the token optimizer provider before reading or producing large content:
   `src.orchestration.token_optimizer_provider.resolve_token_optimizer_provider(...)`.
4. Use `kh` by default. Use `hybrid` when RTK-style command optimization may be available. Use `passthrough` for exact evidence.
5. Resolve a role command only when the user or workflow asks for one:
   `src.orchestration.role_commands.resolve_role_command("/kh:work")`.
6. Keep `progress.json` current while tasks move through RED, GREEN, review, fix, re-review, commit, and next task.
7. Render a visible panel with `src.orchestration.progress_panel.render_progress_panel(progress)` after meaningful task transitions.
8. After Plan, Work, and Review, convert progress to Compound artifacts with:
   `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts(project_root, progress)`.
9. Treat generated memory records as candidates unless the user explicitly approves durable memory promotion and scope.
10. Route next skills from the handoff instead of leaving them as chat-only advice.

## Evidence to produce

- `session_start_context` with recommended reads.
- `progress_panel` text or equivalent structured panel payload.
- `token_optimizer_provider` decision with status and rationale.
- `role_command_entrypoint` when used.
- `compound_capture.json`.
- `compound_handoff.json`.
- `compound_candidates.json` containing memory, skill, and scenario candidates.
- `docs/kh/handoffs/<run-id>-compound.md`.
- `required_next_skills` or explicit blocked/no-learning rationale.

## Failure handling

- If `progress.json` is missing, report the missing path and fall back to `context-state-harness` or `goal-state-harness`.
- If progress exists but is incomplete, render the panel and mark Compound as not ready.
- If a requested RTK provider is unavailable, fall back to KH unless strict mode was requested; strict mode returns a blocked decision.
- If content is quality-sensitive, choose passthrough and record why compression would lower answer quality.
- If a role command is unknown, fail closed with the known `/kh:*` menu.
- If memory candidates contain secret-like content, do not persist them; use memory-state safety checks.

## Quality bar

A good run is easy for a new session to resume. The next agent should see the latest progress, next task, review state, token decision, Compound handoff, memory candidates, and required next skills without reading the full chat. A good token policy should save context only when it preserves evidence. A good role command should route to existing KH skills instead of creating a new undocumented process.

The harness passes when it makes omissions visible. It fails if the agent can still finish a large task without recording token provider status, progress state, next skills, or resume context.
