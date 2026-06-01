---
name: automatic-intake-harness
description: Use when non-trivial Codex, Antigravity-style, Claude Code, or local agent work involves project files, code changes, deliverables, reviews, long logs, verification, subagents, persistence, or high-risk actions, even if the user did not name KH, UAF, a skill, or a harness.
---

# Automatic Intake Harness

This is the always-on KH intake skill. It prevents useful KH behavior from depending on the user knowing internal skill or harness names.

## Support files

- Read `references/usage.md` before changing trigger boundaries or host prompt wording.
- Use `examples/minimal-workflow.md` as a compact acceptance scenario for blind user requests.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to verify that ordinary requests route without internal names.

## Workflow

1. Before source exploration, edits, deliverable generation, review, verification, subagent dispatch, or long-log summarization, classify the user request through `src.orchestration.kh_front_door`.
2. Do not require the user to say KH, UAF, skill, harness, plugin, front door, router, or catalog.
3. Keep simple direct questions cheap: use direct answer when classification is light and no project artifact, command output, safety, persistence, or verification evidence is needed.
4. For project-file work, code changes, substantial docs, long logs, review, QA, security, branch finishing, or stateful workflows, record the selected skills before acting.
5. Treat the intake command itself as runtime evidence for `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog`.
6. Treat every other selected skill as `selected_not_executed` until its implementation target, gate, artifact, or explicit passthrough evidence actually runs.
7. If the installed host points to a stale KH cache path, stop and resolve the current repo-local `skills/` folder or latest installed cache before claiming skill use.
8. After the work, report what was actually applied, what was only selected for next steps, and any residual risk.

## Required outputs

- Front-door classification with complexity, domain, recommended execution, and confidence.
- Selected skill list produced without requiring internal names in the user request.
- `runtime_applied_skills` limited to the intake components that actually ran.
- `selected_not_executed_skills` for follow-up skills that were chosen but not executed yet.
- `skill_status_summary` with status, application mode, evidence note, and blocked reason when applicable.
- Stale or missing host skill path warnings when cache paths are invalid.

## Common mistakes

- Do not wait for the user to enumerate skill names before routing a non-trivial task.
- Do not run the full role DAG for simple definitions, one-line explanations, or tiny edits.
- Do not claim a selected skill was executed just because its name appears in routing output.
- Do not let plugin default prompt text replace runtime evidence.
- Do not hide a stale cache path by falling back silently.

## UAF implementation targets

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.plugin_composition.compose_plugin_route`
- `src.skills.uaf_skill_catalog.collect_packaged_skills`
- `skills/automatic_intake_harness/SKILL.md`
