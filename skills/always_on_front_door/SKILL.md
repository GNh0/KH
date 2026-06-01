---
name: always-on-front-door
description: Use when any non-trivial Codex, Antigravity-style, Claude Code, or local agent request should be handled before any other skill, plugin, browser, image, document, code, shell, subagent, review, QA, or verification work, even when the user does not name KH, UAF, a skill, or a harness.
---

# Always On Front Door

This is the host-visible bootstrap skill for KH UAF. Its job is to make automatic intake harder to miss in ordinary sessions where the user asks for real work without naming KH internals.

## Support files

- Read `references/usage.md` before changing host trigger wording.
- Use `examples/minimal-workflow.md` as the blind-request acceptance scenario.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to verify the front-door demo path.

## Workflow

1. Before using any other non-trivial skill or plugin, decide whether the user request is direct/light or work-bearing.
2. Work-bearing means project files, code changes, generated assets/documents, long logs, review, QA, verification, subagents, persistence, branch work, or risky commands.
3. If work-bearing, run KH front-door intake before source reads, shell exploration, image generation, document generation, browser QA, or subagent dispatch:

```bash
python -m src.orchestration.kh_front_door --prompt "<user request>" --project "<cwd or target project>" --host codex --summary
```

4. Treat only the intake command's `runtime_applied_skills` as executed.
5. Treat `selected_not_executed_skills` as selected follow-up work until concrete module, gate, artifact, command-output, or passthrough evidence exists.
6. If the command is unavailable, explicitly record `blocked` with the missing path or import error before continuing.
7. When another plugin is also useful, apply front-door first, then route by capability; do not let image/browser/document/code skills bypass intake.

## Required outputs

- `front_door_status`, request classification, and plugin route.
- `runtime_applied_skills` and `selected_not_executed_skills`.
- `skill_status_summary` with applied, selected, skipped, or blocked status.
- A short note when a request is intentionally direct/light and no KH runtime work is needed.

## Common mistakes

- Do not start with image generation, browser testing, document writing, source exploration, or shell commands for a work-bearing request before front-door intake.
- Do not assume plugin `defaultPrompt` was injected into the live session.
- Do not count a SKILL.md read, plugin listing, or marketplace metadata as runtime application.
- Do not ask the user to name KH skills before applying this bootstrap.

## UAF implementation targets

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.plugin_composition.compose_plugin_route`
- `src.skills.uaf_skill_catalog.collect_packaged_skills`
- `skills/always_on_front_door/SKILL.md`
- `skills/automatic_intake_harness/SKILL.md`
- `tests.test_kh_front_door_always_on`
