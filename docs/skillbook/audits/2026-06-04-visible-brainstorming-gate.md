# 2026-06-04 Visible Brainstorming Gate Audit

## Trigger

Blind subagent retest `019e9089-86c7-7230-af78-43f86fb59a4f` received an ordinary request without KH/UAF/skill wording:

`C:\Users\KONEIT\Desktop\Jang\SKillsTest\RetestAutoRoute_20260604_E folder: build an inventory inbound/outbound dashboard.`

The subagent did not implement immediately, but its first brainstorming response was still too shallow. It only reported the missing target folder, listed three inventory models, gave basic fields, and asked for approval.

## Audit Result

`python -B -m src.orchestration.session_skill_audit <session-log> --summary`

Flagged:

- `brainstorming-harness`: `shallow_visible_brainstorming`
- Missing markers: `success_constraints`, `operating_options_tradeoffs`, `required_records_data`, `open_questions`
- `verification-before-completion-harness`: failed verification was not reflected in the final response

## Fix

KH UAF now adds a visible first-response gate for vague or new app, dashboard, operations, manufacturing, document, drawing/design, analysis, investment, product, or workflow requests.

The first visible brainstorming response must include:

1. Objective/operator
2. Workflow boundary
3. Success criteria/constraints/non-goals
4. Operating model options and tradeoffs
5. Required records/data/artifact shape
6. Open questions
7. Recommendation
8. Approval question

A response that only states the target folder is missing and lists options is explicitly failed. The rule is present in both `skills/brainstorming_harness/SKILL.md` and the Codex plugin `defaultPrompt` so installed marketplace sessions and subagents can see it without a manual `$CODEX_HOME/skills` bootstrap copy.

## Verification

Passed:

- `python -B -m unittest tests.test_brainstorming_harness tests.test_superpowers_benchmark_alignment tests.test_session_skill_audit`
- `python -B -m unittest discover -s tests`
- `python -B -m src.skills.uaf_skill_catalog --check`
- `python -B -m src.skills.uaf_skill_quality --summary`

Result:

- Full regression: 530 tests OK
- Skill catalog: 40 valid / 0 invalid
- Skill quality: lowest score 9.3, no low-quality skills

