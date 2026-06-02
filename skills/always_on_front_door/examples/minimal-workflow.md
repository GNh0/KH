# Minimal Workflow

## Scenario

User says:

```text
Make a small static dashboard in this folder and verify it.
```

The user did not name KH, UAF, skills, or harnesses.

## Expected steps

1. Recognize this as work-bearing because it edits project files and needs verification.
2. Run front-door intake before reading source files or writing output:

```bash
python "<this skill folder>/scripts/front_door.py" --prompt "Make a small static dashboard in this folder and verify it." --project "<cwd>" --host codex --summary
```

3. Record the returned classification and plugin route.
4. Treat `always-on-front-door`, `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog` as runtime-applied only if the command ran.
5. Keep implementation, QA, review, and completion skills as selected-not-executed until their own evidence exists.
6. Continue with the implementation plan and fresh verification.

## Expected evidence

- `front_door_status: ok`
- `runtime_applied_skills` contains front-door runtime skills
- `selected_not_executed_skills` is not empty for follow-up skills
- verification output includes command, exit code, and result
- `actual_runtime_path`: `src.orchestration.kh_front_door.build_kh_front_door` or `scripts/front_door.py`
- `execution_level`: `python-module`
- `implementation_targets`: `src.orchestration.kh_front_door.build_kh_front_door`, `src.orchestration.request_classifier.classify_request`, `src.orchestration.plugin_composition.compose_plugin_route`, `src.skills.uaf_skill_catalog.collect_packaged_skills`, `skills/always_on_front_door/SKILL.md`, `skills/automatic_intake_harness/SKILL.md`, `tests.test_kh_front_door_always_on`

## Failure cases

- The assistant starts with `ls`, source reads, image generation, browser testing, or file writes before intake.
- The assistant reads `SKILL.md` but never runs front-door intake.
- The assistant claims all selected skills were used.
- The assistant suppresses a failed verification command in the final report.

## Done criteria

The task is done when the requested artifact is created, fresh verification is reported, and the session audit shows front-door runtime evidence or an explicit blocked/direct rationale.
