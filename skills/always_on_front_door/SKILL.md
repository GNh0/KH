---
name: always-on-front-door
description: Use when any non-trivial Codex, Antigravity-style, Claude Code, or local agent request should run this plugin's KH front-door FIRST and ALONE before MEMORY.md lookup, memory quick pass, target/sibling folder inspection, project file reads, other skills/plugins, browser, image, document, code, shell, subagent, review, QA, or verification work, even when the user does not name KH, UAF, a skill, or a harness.
---

# Always On Front Door

## Immediate Action

Run the front-door command as the next standalone tool call. Do not spend a reasoning/planning pass here, do not read other skill files, and do not run target, memory, source, browser, document, QA, verification, or subagent tools before or alongside this command.

Target bootstrap latency: under 10 seconds from reading this file to starting the command. If the command path is missing or stale, resolve the latest installed `kh-uaf` cache path or repo skill folder once, then run the command. If it still cannot run, report blocked with the missing path.

### Windows UTF-8 Template

Use this exact shape for Korean, Japanese, Chinese, or any non-ASCII prompt:

```powershell
$promptPath = Join-Path $env:TEMP "kh-front-door-prompt.txt"
Set-Content -LiteralPath $promptPath -Value @'
<exact user request>
'@ -Encoding UTF8
python "<this skill folder>\scripts\front_door.py" --prompt-file $promptPath --project "<cwd or target project>" --host codex --summary
```

For short ASCII-only prompts, `--prompt "<user request>"` is accepted. If running from the KH repository root, `python -m src.orchestration.kh_front_door ...` is also valid.

Only after the command returns should selected follow-up skills be read or applied.

## KH Entry Contract

- Use this bootstrap for work-bearing requests: project files, code changes, generated assets/documents, long logs, review, QA, verification, subagents, persistence, branch work, or risky commands.
- If an earlier message in the same conversation or project asked to actively/default-use KH/UAF skills or harnesses, keep `kh_active_directive=active` for later work-bearing turns until explicit opt-out.
- Count this skill as `applied` only when the runtime front-door command ran or a concrete blocked/direct rationale was recorded.
- A SKILL.md read, plugin listing, marketplace metadata, or `selected_not_executed_skills` entry is not execution evidence.
- `immediate_next_skills` must produce same-turn applied/skipped/blocked evidence before source exploration, implementation, verification, or final claims; session audit treats SKILL.md-only handling as `immediate_next_skill_not_applied`.

## Workflow

1. Decide only whether the request is direct/light or work-bearing.
2. For work-bearing requests, run the front-door command immediately.
3. Treat `runtime_applied_skills` as executed and `selected_not_executed_skills` as selected follow-up only.
4. Execute `immediate_next_skills` first, in order. Do not treat the full `recommended_skills` or `selected_not_executed_skills` list as the next execution plan.
5. If `execution_gate.can_execute=false`, stop before global memory lookup, source reads, file writes, scaffolding, deliverable generation, browser QA, verification, or subagent dispatch. First apply, skip with rationale, or block `immediate_next_skills`.
6. If the gate is `blocked_until_large_work_preflight`, do only the allowed setup evidence: GoalState, orchestration bundle, workspace/domain boundary, token decision, host/subagent strategy, parallel strategy, role-audit decision, command-output plan, deliverable/render quality plan, guard/rollback policy, and verification plan.
7. After intake, route specialist providers by capability. KH intake must not hide host-local skills such as `sql-formatting` when they match the request.

## Required outputs

- `front_door_status`, request classification, plugin route, and `execution_gate`.
- `runtime_applied_skills`, `selected_not_executed_skills`, `immediate_next_skills`, and `skill_status_summary`.
- `kh_active_directive` when persistent KH use was requested.
- Blocked/direct rationale when the runtime command cannot run.

## User-Facing Reporting

- Keep raw KH routing evidence in tool output, runtime metadata, handoff files, or audit reports.
- Do not append raw KH status lines to ordinary final answers unless the user asks how KH was used.
- If a progress update is needed, keep it short and then return to the user's task.

## Common mistakes

- Do not read MEMORY.md, source files, target folders, parent/sibling folders, other SKILL.md files, or support references before the front-door command.
- Do not parallelize the front-door command with pre-intake reads.
- Do not use `--prompt "<non-ASCII text>"` on Windows; use `--prompt-file`.
- Do not ignore stale cache path failures; resolve the latest cache or repo skills path before claiming KH use.
- Do not run broad uncapped searches after intake. Narrow `rg`/file reads and use command-output filtering before hundreds of raw lines enter context.
- Do not treat a user saying "develop/make/create" as implementation approval when front-door selected brainstorming.
- Do not treat selected follow-up skills as exclusive; specialist plugins may still be routed after intake.
- Do not skip `immediate_next_skills` and jump directly to source exploration, implementation, verification, or final claims.
- Do not treat a support-file read as immediate skill application, even when the support file contains runtime marker names.

## UAF implementation targets

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.plugin_composition.compose_plugin_route`
- `src.skills.uaf_skill_catalog.collect_packaged_skills`
- `skills/always_on_front_door/SKILL.md`
- `skills/automatic_intake_harness/SKILL.md`
- `src.orchestration.session_skill_audit.analyze_session_skills`
- `tests.test_kh_front_door_always_on`
- `tests.test_session_skill_audit`

## Support files

- Use `scripts/front_door.py` as the skill-local front-door wrapper when the host starts outside the KH repository root.
- Read `references/usage.md` only before changing host trigger wording.
- Use `examples/minimal-workflow.md` for blind-request acceptance scenarios.
- Run `python scripts/smoke_check.py` from this skill folder for support-file and target checks.
- Run `python scripts/demo.py --output-dir <tmp>` to verify the front-door demo path.
