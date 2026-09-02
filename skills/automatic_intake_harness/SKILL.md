---
name: automatic-intake-harness
description: Use when explicitly testing or auditing deterministic KH intake, or when integrating governed intake into a host agent runtime. Do not invoke for ordinary clear requests.
---

# Automatic Intake Harness

## KH Entry Contract

- Use this skill only for an explicit intake/routing audit or a governed host-runtime integration that requires deterministic classification evidence.
- Ordinary direct and single-domain requests bypass this skill and select their domain skill from visible metadata.
- An active KH directive permits matching domain and process skills; it does not make this intake harness mandatory.
- Report governed runtime application only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this `SKILL.md`, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not governed runtime execution evidence.

This is a deterministic intake audit and host-integration harness. It is not an always-on prerequisite for using KH domain or workflow skills.

## Support files

- Read `references/usage.md` before changing trigger boundaries or host prompt wording.
- Use `examples/minimal-workflow.md` as a compact acceptance scenario for blind user requests.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to verify that ordinary requests route without internal names.

## Workflow

1. Confirm that an explicit audit or governed host-integration trigger exists before reading support files or running Python.
2. Audit the expected direct, single-domain, or governed path from the request and already-visible context.
3. Run `src.orchestration.kh_front_door` only when deterministic classification evidence is the requested or governed output.
4. Do not require the user to say KH, UAF, skill, harness, plugin, front door, router, or catalog.
5. If an active KH directive exists, preserve it as audit context without treating it as proof that this harness executed.
6. For an audited direct or single-domain path, record that the governed runtime did not execute; do not attach no-op Token Optimizer or routing telemetry to the ordinary task.
7. For an audited governed workflow, record only skills actually selected by the concrete risk, state, artifact, or orchestration trigger.
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

- Do not load this harness merely because a new request started or the user omitted internal skill names.
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
