---
name: automatic-intake-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it to classify every new Codex, Antigravity-style, Claude Code, or local-agent request without requiring the user to name KH, UAF, a skill, or a harness, then exit directly or route governed work.
---

# Automatic Intake Harness

## KH Entry Contract

- Start every new request through `always-on-front-door`; an eligible direct/meta turn may use its host-native semantic fast path, while every other turn enters the governed runtime.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report governed runtime application only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this `SKILL.md`, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not governed runtime execution evidence.

This is the always-on KH intake skill. It prevents useful KH behavior from depending on the user knowing internal skill or harness names.

## Support files

- Read `references/usage.md` before changing trigger boundaries or host prompt wording.
- Use `examples/minimal-workflow.md` as a compact acceptance scenario for blind user requests.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to verify that ordinary requests route without internal names.

## Workflow

1. Apply the host-native semantic gate documented by `always-on-front-door` using only the request and already-visible conversation context.
2. Use the no-Python direct exit only for a high-confidence direct/meta, non-specialist, non-stateful turn that needs no read-only tool/source access, mutation, persistence, credentials, high-risk handling, artifact, verification, or governed work.
3. On any failed condition or ambiguity, classify through `src.orchestration.kh_front_door` before source exploration, edits, deliverable generation, review, verification, subagent dispatch, or long-log summarization.
4. Do not require the user to say KH, UAF, skill, harness, plugin, front door, router, or catalog.
5. If the conversation or project already contains an active instruction to actively, always, or by default use KH/UAF skills or harnesses, carry `kh_active_directive=active` into later work-bearing turns until the user explicitly opts out.
6. For a host-native direct exit, record `intake_mode=host_native_semantic_fast_path`, `route=direct`, `governed_runtime_executed=false`, empty `runtime_applied_skills`, and Token Optimizer `considered_not_needed` or `passthrough`; do not read more skill files.
7. For project-file work, code changes, substantial docs, long logs, review, QA, security, branch finishing, or stateful workflows, record the runtime-selected skills before acting.
8. Treat the intake command itself as runtime evidence for `automatic-intake-harness`, `plugin-composition-policy`, and `request-complexity-router`. Count `skill-catalog` as applied only when full catalog discovery actually ran; targeted micro validation is separate evidence.
9. Treat every other selected skill as `selected_not_executed` until its implementation target, gate, artifact, or explicit passthrough evidence actually runs.
10. If the installed host points to a stale KH cache path, stop and resolve the current repo-local `skills/` folder or latest installed cache before claiming skill use.
11. After the work, report what was actually applied, what was only selected for next steps, and any residual risk.

## Required outputs

- Host-native direct decision or governed front-door classification with complexity, domain, recommended execution, and confidence.
- `kh_active_directive` status when a previous user instruction asked for persistent KH skill/harness use.
- Selected skill list produced without requiring internal names in the user request.
- `runtime_applied_skills` limited to the intake components that actually ran.
- `selected_not_executed_skills` for follow-up skills that were chosen but not executed yet.
- `skill_status_summary` with status, application mode, evidence note, and blocked reason when applicable.
- Stale or missing host skill path warnings when cache paths are invalid.

## Common mistakes

- Do not wait for the user to enumerate skill names before routing a new request.
- Do not drop a prior "actively use KH skills/harnesses" instruction on later turns where the user says only "continue", "finish", or describes ordinary work.
- Do not run the full role DAG for simple definitions, one-line explanations, or tiny edits.
- Do not use the host-native path when the request needs any source/tool read, specialist, state, mutation, persistence, credentials, risk review, artifact, or verification.
- Do not claim a selected skill was executed just because its name appears in routing output.
- Do not claim governed runtime execution because this `SKILL.md` was read or a host-native direct decision was made.
- Do not let plugin default prompt text replace runtime evidence.
- Do not hide a stale cache path by falling back silently.

## UAF implementation targets

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.plugin_composition.compose_plugin_route`
- `src.skills.uaf_skill_catalog.collect_packaged_skills`
- `skills/automatic_intake_harness/SKILL.md`
