---
name: workflow-usability-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when KH needs visible progress panels, progress-to-Compound handoff, token provider selection, role command entrypoints, or session-start context restore.
---

# Workflow Usability Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is a personal UAF usability harness. It turns the internal KH lifecycle into host-readable control surfaces so large work does not depend on the agent remembering hidden policy after context compression.

When `workflow_usability_auto` is present in AgentLoop, app bridge, or workflow metadata, the UAF runtime applies this harness automatically after dispatch. The host still controls whether to display the panel, but the metadata and project artifacts are produced without a separate manual helper call.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands triggers, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Reference basis

- KH lifecycle evidence, external role-stack command ergonomics, Superpowers-style visible progress, optional RTK-style command context optimization, and Compound learning loops.

## When To Use

Use this harness when:

- `.kh/development/<run-id>/state/progress.json` should produce a visible Compound handoff instead of ending as a private status file.
- A large or long-running workflow needs `token_optimizer_provider` recorded as `kh`, `rtk`, or `hybrid`, plus a separate `token_optimizer_status` such as `used`, `considered_not_needed`, `passthrough`, or `blocked`.
- A user asks for role-driven commands such as brainstorm, spec, work, QA, ship, learn, or resume without needing to know every underlying KH skill name.
- A task-plan run should show a compact progress panel with task status, review status, token optimizer status, commit SHA, and next task.
- Codex, Antigravity-style Agent Manager, CLI shells, or future hosts need a stable `host_panel.<host>.json` contract for their native progress surfaces.
- A new session must recover context from `.kh`, `docs/kh`, and memory candidates before relying on chat context.
- A finished or interrupted Codex session must be checked for false completion, hidden verification failures, token-gate omissions, reviewer timeouts, subagent cleanup, secret exposure, and git integration.
- A stopped or paused goal must prove that the user stop request overrode any later `goal_context` continuation.
- A postmortem must distinguish skill inspection from skill application; reading a skill file is not runtime usage unless there is harness output, module execution, token-savings metadata, or explicit passthrough evidence.
- Optional platform-specific app-server verification needs a reproducible launch plan with an explicit approved runtime entrypoint, normalized environment, redirected logs, and a separate health check. This is a narrow verification subpath, not a reason to choose Windows, Streamlit, or any web stack.

Do not use this harness to skip planning, review, QA, or Compound. It exposes those steps; it does not replace them.

## Core Flow

1. At the start of a new or resumed session, call `src.orchestration.session_start_context.build_session_start_context` and read the recommended KH state/docs/memory candidate paths.
2. Run `src.orchestration.runtime_memory.build_active_memory_preflight` so scoped recall and bounded `MEMORY.md`/`USER.md` prompt snapshots are ready before implementation.
3. During task-plan implementation, keep `src.orchestration.development_progress` current and render `src.orchestration.progress_panel.render_progress_panel` after meaningful state changes.
4. For host-native progress UI, call `src.orchestration.progress_panel.write_host_progress_panel` so `.kh/development/<run-id>/state/host_panel.<host>.json` mirrors the same run state for Codex, Antigravity-style Agent Manager, generic CLI shells, or future hosts.
5. Before broad reads, subagent packets, or long commands, resolve `token_optimizer_provider` through `src.orchestration.token_optimizer_provider.resolve_token_optimizer_provider`.
6. When workflow task results contain long command output or subagent transcripts, route them through `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results` so runtime evidence includes preserved failure context, token savings, and RTK-style command-family statistics.
7. Before expected host context compaction, call `src.orchestration.runtime_memory.write_pre_compaction_memory_flush` so decisions, blockers, next tasks, and verification state survive compression.
8. When Compound or workflow usability produces memory candidates, call `src.orchestration.runtime_memory.record_workflow_memory_candidates` so they are persisted as scoped candidates without durable promotion.
9. When a user asks for role help, resolve `/kh:*` command entrypoints through `src.orchestration.role_commands.resolve_role_command` instead of inventing one-off role prompts.
10. After Plan, Work, and Review, call `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts` so progress becomes `CompoundCapture`, `compound_handoff`, memory candidates, skill candidates, scenario candidates, and a Markdown handoff.
11. When reviewing a real Codex session log, call `src.orchestration.session_postmortem.analyze_codex_session_jsonl` and block final-health claims if `completion_guard`, `verification_claim_guard`, `scope_completion_delta`, or `user_stop_guard` is blocked.
12. When a user stop is honored, call `src.orchestration.interruption_state.write_interruption_checkpoint` so `.kh` state and scoped durable memory both preserve what was done, what remains, and where to resume.
13. For full-catalog skill usage review, call `src.orchestration.session_skill_audit.analyze_session_skills` or the module CLI so every KH packaged skill is classified as required, applied, inspected, mentioned, or missing.
14. For local dev-server checks, first identify the approved runtime and entrypoint. When the selected runtime is Streamlit on Windows, build a launch and health-check plan through `src.orchestration.windows_dev_server.build_streamlit_launch_plan` with an explicit `app_path` instead of retrying ad hoc `Start-Process` variants.
15. Route any next skills from the Compound handoff into `workflow-skill-distiller`, `memory-state-harness`, `scenario-evaluation-harness`, or `context-state-harness`.

## Provider Policy

`token_optimizer_provider` is a policy choice, not a hard dependency:

- `kh`: use KH's Python token optimizer.
- `rtk`: use RTK-style command output optimization only when available; fall back to KH unless strict mode is requested.
- `hybrid`: use RTK for high-noise command output when available and KH otherwise.
`passthrough` is not a provider. It is a token optimizer status/decision that preserves exact source-of-truth text without compression.

Quality-sensitive content such as requirements, security notes, review findings, and contract prose must prefer passthrough over lossy compression.

## Role Commands

The default KH role command front doors are:

- `/kh:brainstorm`
- `/kh:spec`
- `/kh:ceo-review`
- `/kh:eng-review`
- `/kh:work`
- `/kh:qa`
- `/kh:ship`
- `/kh:learn`
- `/kh:resume`

Each command resolves to a small set of roles, KH skills, and expected outputs. The command is only a routing shortcut; evidence still comes from the underlying skills and harnesses.

## Required outputs

- `session_start_context` when resuming or starting work in an existing project.
- Visible progress panel for long task-plan runs.
- Host progress panel JSON at `.kh/development/<run-id>/state/host_panel.<host>.json` when native host surfaces may display progress.
- `token_optimizer_provider` decision with provider, provider-selection status, strategy, fallback, and quality rationale, plus separate `token_optimizer_status` for used/considered/passthrough/blocked outcomes.
- Runtime `token_optimization` summary with status, status reason, not-used reason for skipped/passthrough/blocked decisions, token usage savings, preserved command/subagent evidence, and RTK-style command-family statistics when task outputs cross the threshold.
- Runtime `memory_state` summary with scoped candidate recording paths and promotion mode.
- Runtime `active_memory_preflight` summary with scoped recall and bounded prompt snapshot paths.
- Runtime `pre_compaction_memory_flush` summary when compression could otherwise erase decisions or next actions.
- `session_skill_audit` when inspecting a prior session against all KH packaged skills.
- Resolved KH role command entrypoint when a role command is used.
- `session_postmortem` with `completion_guard`, `verification_claim_guard`, `scope_completion_delta`, `user_stop_guard`, token gate, review status, subagent summary, secret scan, and git integration when inspecting a prior session.
- `interruption_checkpoint` with `.kh` paths and scoped durable `resume-checkpoint` memory record when a user-requested stop interrupts work.
- `windows_dev_server_launch_plan` when Windows local app-server verification needs a stable runner.
- `compound_capture`, `compound_handoff`, memory candidates, skill candidates, scenario candidates, and Markdown handoff when a progress run reaches review completion.
- Next-skill routing or an explicit blocked/no-learning rationale.

## Common mistakes

- Do not leave completed `progress.json` unconnected to Compound.
- Do not treat RTK as required; it is optional provider policy.
- Do not compress source-of-truth text just to claim token savings.
- Do not show a progress panel that omits review status, token optimizer status, commit SHA, or next task.
- Do not assume Codex or Antigravity native panels are Superpowers-owned; KH should expose host-readable progress state and let the host render it.
- Do not start a resumed session from chat memory alone when `.kh`, `docs/kh`, or memory candidates exist.
- Do not treat a scaffold, first slice, or pushed branch as final completion while the user goal remains active.
- Do not let automatic `goal_context` continuation resume work after a user asked to stop, pause, cancel, or equivalent; block the active goal with `blocked_reason=user_requested_stop` when host policy allows it, otherwise keep the interruption checkpoint as the controlling stop state and wait for a fresh non-`goal_context` user resume request.
- Do not replace failed Browser/Playwright QA with a narrower HTTP check unless the final report explicitly states the failed verification route and residual risk.
- Do not mark token optimizer as `used` from skill-file reads, default prompts, or status mentions alone.

## UAF implementation targets

- `src.orchestration.progress_compound_bridge`
- `src.orchestration.workflow_usability_runtime.apply_workflow_usability_runtime`
- `src.orchestration.progress_compound_bridge.write_progress_compound_artifacts`
- `src.orchestration.token_optimizer_provider.resolve_token_optimizer_provider`
- `src.orchestration.runtime_token_optimizer.optimize_workflow_task_results`
- `src.orchestration.runtime_memory.record_workflow_memory_candidates`
- `src.orchestration.role_commands.resolve_role_command`
- `src.orchestration.progress_panel.render_progress_panel`
- `src.orchestration.progress_panel.build_host_progress_panel`
- `src.orchestration.progress_panel.write_host_progress_panel`
- `src.orchestration.session_start_context.build_session_start_context`
- `src.orchestration.session_postmortem.analyze_codex_session_jsonl`
- `src.orchestration.interruption_state.write_interruption_checkpoint`
- `src.orchestration.session_skill_audit.analyze_session_skills`
- `src.orchestration.windows_dev_server.build_streamlit_launch_plan`
- `tests.test_workflow_usability_layer`
