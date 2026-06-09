---
name: always-on-front-door
description: Use when any non-trivial Codex, Antigravity-style, Claude Code, or local agent request should run this plugin's KH front-door FIRST and ALONE before MEMORY.md lookup, memory quick pass, target/sibling folder inspection, project file reads, other skills/plugins, browser, image, document, code, shell, subagent, review, QA, or verification work, even when the user does not name KH, UAF, a skill, or a harness.
---

# Always On Front Door

## Immediate Action

After reading this file for a work-bearing request, run the front-door command immediately as the next standalone tool call. Do not open QA, verification, browser, document, image, memory, or other KH skill files first. Do not run target-folder checks, parent/sibling directory scans, `MEMORY.md` searches, memory quick passes, project file reads, or parallel tool batches before or alongside the command.

For non-ASCII prompts on Windows, do not pass the user request through a shell `--prompt "<text>"` argument. Write the exact request to a UTF-8 prompt file as part of the front-door bootstrap and call:

```bash
python "<this skill folder>/scripts/front_door.py" --prompt-file "<utf8 prompt file>" --project "<cwd or target project>" --host codex --summary
```

For short ASCII-only prompts, `--prompt "<user request>"` is still accepted.

If you are already running from the KH repository root, `python -m src.orchestration.kh_front_door ...` is also valid. Prefer the skill-local wrapper when the host starts in a target project, temp folder, or subagent workspace.

Only after this command returns should the selected follow-up skills be read or applied.

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- At bootstrap time, select only this skill first; other skills become eligible after `kh_front_door` returns.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is the host-visible bootstrap skill for KH UAF. Its job is to make automatic intake harder to miss in ordinary sessions where the user asks for real work without naming KH internals.

## Workflow

1. Before using any other non-trivial skill or plugin, decide whether the user request is direct/light or work-bearing.
2. Work-bearing means project files, code changes, generated assets/documents, long logs, review, QA, verification, subagents, persistence, branch work, or risky commands.
3. If an earlier message in the same conversation or project asked the assistant to actively, always, or by default use KH/UAF skills or harnesses, keep `kh_active_directive=active` for later work-bearing turns until the user explicitly opts out.
4. If work-bearing, make the first standalone work-bearing tool call the KH front-door intake. Do not run source reads, target-folder checks, parent/sibling folder scans, `Test-Path`, `Get-ChildItem`, `rg`, memory lookup, memory quick pass, image generation, document generation, browser QA, or subagent dispatch before it. Do not parallelize those actions in the same pre-intake batch.

```bash
python "<this skill folder>/scripts/front_door.py" --prompt-file "<utf8 prompt file>" --project "<cwd or target project>" --host codex --summary
```

5. Treat only the intake command's `runtime_applied_skills` as executed.
6. Treat `selected_not_executed_skills` as selected follow-up work until concrete module, gate, artifact, command-output, or passthrough evidence exists.
7. If the command returns `execution_gate.can_execute=false`, stop before any global Codex `MEMORY.md` lookup, `.codex/memories/skills/...` lookup, memory-derived shortcut, parent/sibling folder read, scaffolding, source write, deliverable generation, verification, or browser QA. Satisfy `execution_gate.required_before_execution` first, or record an explicit blocked rationale.
8. If the gate status is `blocked_until_large_work_preflight`, do only the gate's `allowed_setup_actions`: read selected skill docs, create/update GoalState, record `large_work_orchestration_bundle`, `workspace_strategy`, `token_optimizer_status`, host/subagent strategy, `parallel_strategy_decision`, role-audit decision, command-output filter plan, deliverable/render quality plan, guard/rollback policy, and verification plan. Do not run implementation, DB writes, file writes, broad source exploration, subagent dispatch, verification-as-completion, or completion claims until that preflight evidence exists.
9. If the command is unavailable, explicitly record `blocked` with the missing path or import error before continuing.
10. When another plugin or host-local skill is also useful, apply front-door first, then route by capability; do not let image/browser/document/code/SQL-formatting skills bypass intake, and do not let KH intake hide a better specialist provider after intake.

## Required outputs

- `front_door_status`, request classification, and plugin route.
- `execution_gate`, including whether `can_execute` is true or false.
- `kh_active_directive` as active/inactive when the user has asked for persistent KH skill/harness use in the conversation or project.
- `runtime_applied_skills` and `selected_not_executed_skills`.
- `skill_status_summary` with applied, selected, skipped, or blocked status.
- A short note when a request is intentionally direct/light and no KH runtime work is needed.

## User-Facing Reporting

- Keep KH routing evidence in tool output, runtime metadata, handoff files, or audit reports.
- For ordinary user requests, do not append raw KH status lines such as `front_door_status`, `runtime_applied_skills`, `valid=true`, or `missing=[]` to the final answer unless the user asks how KH was used.
- If host policy requires announcing skill use during the turn, keep it to one short progress update, then make the final answer about the user's task.
- When the user explicitly asks for skill/harness evidence, report applied, selected-not-executed, skipped, and blocked states without counting SKILL.md reads as execution.

## Common mistakes

- Do not start with target-folder checks, parent/sibling folder scans, memory search, memory quick pass, image generation, browser testing, document writing, source exploration, or shell commands for a work-bearing request before front-door intake.
- Do not count "I will use always-on-front-door", a SKILL.md read, or a catalog listing as front-door execution. The runtime command or blocked/direct rationale must come first.
- Do not bundle `Test-Path`, `Get-ChildItem`, `rg`, file reads, or MEMORY.md search in the same parallel batch as the first front-door command.
- Do not open `qa_gate_harness`, `verification_before_completion_harness`, browser skills, memory files, or support references before the front-door command.
- Do not inspect previous run folders or sibling test outputs to bootstrap a new requested target. Treat that as cross-scope context leakage unless the user explicitly requested comparison or reuse.
- Do not create a substitute folder in the current workspace when the user named a different target path. If the exact target path is unavailable, outside the sandbox, or needs approval, stop and report the permission/path blocker before generating artifacts.
- Do not create workspace-root product files such as `index.html`, `styles.css`, `app.js`, documents, images, or generated data files while waiting for exact target path permission. Execution approval does not allow staging outside the requested absolute target.
- Do not assume plugin `defaultPrompt` was injected into the live session.
- Do not pass Korean, Japanese, Chinese, or other non-ASCII user requests through a Windows shell `--prompt "<text>"` argument. Use `--prompt-file` or `--prompt-stdin` so the front-door classifier sees the same request the user wrote.
- Do not ignore `execution_gate.can_execute=false` because the user said "develop", "make", or "create"; that wording starts direction discovery when front-door selected brainstorming, not implementation approval.
- Do not ignore `execution_gate.status=blocked_until_large_work_preflight` because the work is urgent or specific. Heavy/role_dag work must record the preflight strategy bundle before broad reads, edits, DB writes, subagent dispatch, verification, or completion claims.
- Do not use `%CODEX_HOME%/memories/MEMORY.md` or `%CODEX_HOME%/memories/skills/...` as current-project evidence under a brainstorming gate. Those are cross-chat/subagent memories unless the user explicitly asks for prior-context reuse.
- Do not count a SKILL.md read, plugin listing, or marketplace metadata as runtime application.
- Do not ask the user to name KH skills before applying this bootstrap.
- Do not forget a prior "actively use KH skills/harnesses" instruction just because the later task wording omits KH names.
- Do not treat KH selected skills as exclusive. After front-door intake, host-local skills such as `sql-formatting` must still be used when their trigger or explicit provider name matches the request.

## UAF implementation targets

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.plugin_composition.compose_plugin_route`
- `src.skills.uaf_skill_catalog.collect_packaged_skills`
- `skills/always_on_front_door/SKILL.md`
- `skills/automatic_intake_harness/SKILL.md`
- `tests.test_kh_front_door_always_on`

## Support files

- Read `references/usage.md` before changing host trigger wording.
- Use `examples/minimal-workflow.md` as the blind-request acceptance scenario.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to verify the front-door demo path.
- Use `python scripts/front_door.py --prompt-file "<utf8 prompt file>" --project "<target>" --host codex --summary` when the current working directory is not the KH repository root and the prompt is not ASCII-only.
