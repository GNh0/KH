# Minimal Workflow

## Scenario

User says:

```text
Create the approved project-appropriate deliverables in this folder and verify them.
```

The user did not name KH, UAF, skills, or harnesses.

The same bootstrap applies to short requests such as `1+1?`, `Translate hello`, or `Format this SQL: SELECT ...`.

## Expected steps

1. Recognize this as work-bearing because it edits project files and needs verification.
2. Run front-door intake before reading source files, doing a memory quick pass, checking the target folder, or writing output:

```bash
python "<this skill folder>/scripts/front_door.py" --prompt-file "<utf8 prompt file>" --project "<cwd>" --host codex --summary --strict-execution-gate
```

3. Record the returned classification and plugin route.
4. Treat `always-on-front-door`, `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog` as runtime-applied only if the command ran.
5. Keep implementation, QA, review, and completion skills as selected-not-executed until their own evidence exists.
6. Continue with the implementation plan and fresh verification.

For short/direct work, use `--micro-summary` as the normal machine bootstrap. The runtime may return a micro packet with `cls.x=direct`, `g.ok=true`, and no `next` list. Answer directly at that point without opening another skill. For SQL formatting, the ordered next skills must be `sql-formatting` followed by `sql-formatting-style-harness`.

A bounded confirmation may reuse the current receipt only while this same task remains unfinished and unchanged. After completion, for a new task, or when the user adds work, run front-door again.

## Expected evidence

- `front_door_status: ok`
- `runtime_applied_skills` contains front-door runtime skills
- `selected_not_executed_skills` is not empty for follow-up skills
- verification output includes command, exit code, and result
- `actual_runtime_path`: `src.orchestration.kh_front_door.build_kh_front_door` or `scripts/front_door.py`
- `execution_level`: `python-module`
- `implementation_targets`: `src.orchestration.kh_front_door.build_kh_front_door`, `src.orchestration.request_classifier.classify_request`, `src.orchestration.plugin_composition.compose_plugin_route`, `src.skills.uaf_skill_catalog.collect_packaged_skills`, `src.orchestration.session_skill_audit.analyze_session_skills`, `skills/always_on_front_door/SKILL.md`, `skills/automatic_intake_harness/SKILL.md`, `tests.test_kh_front_door_always_on`, `tests.test_session_skill_audit`

## Failure cases

- The assistant starts with `ls`, source reads, memory quick pass, image generation, browser testing, or file writes before intake.
- The assistant reads this `SKILL.md` and searches `MEMORY.md` in the same first parallel batch before the front-door command.
- The host decides a request is trivial and answers, translates, rewrites, looks up, calculates, or reads the SQL provider before running front-door.
- The manifest is treated as proof that the host auto-selected KH; compliance was not audited from runtime evidence.
- The assistant reads `SKILL.md` but never runs front-door intake.
- The assistant claims all selected skills were used.
- The assistant suppresses a failed verification command in the final report.

## Done criteria

The task is done when the requested artifact is created, fresh verification is reported, and the session audit shows front-door runtime evidence.

A direct response is allowed only when valid runtime output for the current request reports a direct classification and execution authorization.
