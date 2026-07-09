# Minimal Workflow

## Scenario

A user asks: "Create the approved project-appropriate deliverable in this folder and verify it."

The user did not mention KH, UAF, plugins, skills, harnesses, routing, or orchestration.

## Expected steps

1. Run the automatic intake command against the target folder.
2. Confirm the request is implementation work rather than a direct answer.
3. Record the selected development, goal, verification, and review-related skills as selected for follow-up.
4. Only mark the intake components as runtime-applied at this stage.
5. Continue with implementation and verification, recording real evidence for each follow-up skill that actually runs.

## Expected evidence

- `front_door_status = ok`
- `runtime_applied_skills` includes `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog`.
- `selected_not_executed_skills` includes implementation and verification follow-ups until they produce their own evidence.
- The final report distinguishes applied, selected, skipped, blocked, and residual-risk states.
- `execution_level = python-module`
- `actual_runtime_path = src.orchestration.kh_front_door.build_kh_front_door`

## Implementation targets

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.plugin_composition.compose_plugin_route`
- `src.skills.uaf_skill_catalog.collect_packaged_skills`
- `skills/automatic_intake_harness/SKILL.md`

## Failure cases

- The agent begins editing files before intake.
- The agent reports every selected skill as applied.
- A long log summary is routed as full implementation instead of command-output/token optimization work.
- A simple definition is made heavy without project or risk evidence.

## Done criteria

The user can give an ordinary task, the host runs intake automatically, and the audit can prove that skill usage was not fabricated.

## Runtime binding

- execution_level: python-module
- implementation_targets:
  - `src.orchestration.kh_front_door.build_kh_front_door`
  - `src.orchestration.request_classifier.classify_request`
  - `src.orchestration.plugin_composition.compose_plugin_route`
- actual_runtime_path: `src.orchestration.kh_front_door.build_kh_front_door`
- verification evidence: run `scripts/smoke_check.py`, `scripts/demo.py --output-dir <tmp>`, and the front-door/classifier unittest cases before claiming intake behavior is complete.
