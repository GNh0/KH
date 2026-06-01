# Always-On Front Door Regression Audit

Date: 2026-06-01
Branch: codex-runtime

## Problem

Fresh Codex sessions had KH UAF skills available but still performed ordinary work without entering KH front-door intake. This made `automatic-intake-harness` too easy to miss unless the user explicitly named KH or a harness.

The key failing session was:

- `019e8178-ac99-7800-a024-0969f49b6285`

Session audit result before this change:

- `observed_skills: 0`
- `runtime_applied_skills: 0`
- `required_skills: 13`
- `required_missing_evidence: 13`
- `issue_count: 15`

The session contained KH UAF skills in the host skill list, but plugin `defaultPrompt` was not present in the live session payload. Therefore manifest prompt text cannot be treated as a reliable always-on execution mechanism.

## Root Cause

The installed plugin exposed many KH skills, but the host still had to choose one based on skill metadata. `automatic-intake-harness` described the right behavior, but it competed with more concrete skills such as image/browser/document/code workflows. In blind ordinary requests, the model could pick the concrete output skill first and never run KH front-door.

## Change

Added `always-on-front-door` as a host-visible bootstrap skill:

- Its description explicitly says to use it first for every non-trivial Codex, Antigravity-style, Claude Code, or local agent request.
- It runs the same executable KH intake path: `src.orchestration.kh_front_door`.
- It keeps `runtime_applied_skills` and `selected_not_executed_skills` honest.
- It records a blocked/direct rationale when front-door cannot run or is not needed.

Runtime and audit wiring were updated:

- `src.orchestration.kh_front_door.FRONT_DOOR_SKILLS`
- `src.orchestration.session_skill_audit`
- `src.skills.uaf_skill_catalog`
- `src.skills.uaf_skill_quality`
- `src.skills.demo_scenarios`
- `src.orchestration.interactive_side_evaluator`
- plugin manifests and README surfaces

## Acceptance Criteria

- Catalog includes 40 packaged skills/harnesses.
- `always-on-front-door` resolves its implementation targets.
- Front-door summary includes `always-on-front-door` in `runtime_applied_skills`.
- Session audit flags non-trivial work that starts without front-door as a P1 `always-on-front-door` miss.
- Blind post-upgrade subagent sessions are tested with ordinary prompts that do not mention KH, UAF, skill, harness, or front-door.

## Local Verification

- `python -B -m src.skills.uaf_skill_catalog --check`: passed, `40 valid / 0 invalid`.
- `python -B skills\always_on_front_door\scripts\smoke_check.py`: passed, including a packaged test reference for the slim runtime branch.
- `python -B skills\always_on_front_door\scripts\demo.py --output-dir <external temp>`: passed, with success and stale-cache blocked cases.
- `python -B -m src.orchestration.kh_front_door --prompt "간단한 웹 대시보드 하나 만들고 검증까지 해줘" --project <target> --host codex --summary`: passed, `runtime_applied_skills` included `always-on-front-door`, `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog`.
- `python -B -m src.orchestration.session_skill_audit <019e8178...jsonl> --summary`: failed the historical session as expected and now reports `always-on-front-door` as required/missing.
- `python -B -m src.orchestration.plugin_install_audit --summary --repo <repo>`: `attention_required` until Codex upgrades from installed `2.9.29` to source `2.9.30`.
- `python -B -m src.skills.uaf_skill_quality --summary`: still fails overall on `codex-runtime` because this slim branch does not package full test files and several pre-existing core skills score below the strict 9.0 gate; `always-on-front-door` is no longer in `low_quality_skills` after support-file and packaged-test-reference hardening.

## Residual Risk

This patch improves host-visible skill selection, but it cannot force the Codex host to load or obey a skill. If a blind fresh session still ignores `always-on-front-door`, the remaining fix needs a Codex host-level always-on hook or marketplace/runtime prompt injection behavior, not another README claim.
