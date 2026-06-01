# Always-On Front Door Regression Audit

Date: 2026-06-01
Branches: main, codex-runtime

## Problem

Fresh Codex sessions had KH UAF skills available but still performed ordinary work without entering KH front-door intake. This made `automatic-intake-harness` too easy to miss unless the user explicitly named KH or a harness.

The key failing sessions were:

- `019e8178-ac99-7800-a024-0969f49b6285`
- `019e813d-c26b-7d82-82df-d6f052c83dc7`

Both sessions contained KH UAF skills in the host skill list, but they produced no front-door runtime evidence.

## Root Cause

The installed plugin exposed many KH skills, but the host still had to choose one based on skill metadata. `automatic-intake-harness` described the right behavior, but it competed with more concrete skills such as browser, document, code, or app workflows. In blind ordinary requests, the model could pick the concrete output skill first and never run KH front-door.

Manifest `defaultPrompt` is useful but cannot be treated as reliable runtime evidence. Some historical sessions showed KH skills in the available list while no plugin default prompt text was present in the live payload.

## Change

Added `always-on-front-door` as a host-visible bootstrap skill:

- Its description explicitly says to use it first for every non-trivial Codex, Antigravity-style, Claude Code, or local agent request.
- It runs the same executable KH intake path: `src.orchestration.kh_front_door`.
- It keeps `runtime_applied_skills` and `selected_not_executed_skills` honest.
- It records a blocked/direct rationale when front-door cannot run or is not needed.

Runtime and audit wiring were updated:

- `src.orchestration.kh_front_door.FRONT_DOOR_SKILLS`
- `src.orchestration.session_skill_audit`
- `src.orchestration.request_classifier`
- `src.skills.uaf_skill_catalog`
- `src.skills.uaf_skill_quality`
- `src.skills.demo_scenarios`
- `src.orchestration.interactive_side_evaluator`
- plugin manifests and README surfaces

Follow-up hardening after a live 2.9.30 blind subagent run:

- `session_skill_audit` treats `kh_front_door` JSON output from an installed Codex plugin cache path as runtime evidence instead of passive SKILL.md/cache text.
- `session_skill_audit` separates skills in `runtime_applied_skills` from skills in `selected_not_executed_skills`, so selected follow-up harnesses are not inflated into runtime execution.
- `request_classifier` no longer treats the Korean word `실행` by itself as a destructive action.
- UI requests such as filter-button behavior with residual-risk notes stay software work instead of security high-risk.

## Acceptance Criteria

- Catalog includes 40 packaged skills/harnesses.
- `always-on-front-door` resolves its implementation targets.
- Front-door summary includes `always-on-front-door` in `runtime_applied_skills`.
- Session audit flags non-trivial work that starts without front-door as a P1 `always-on-front-door` miss.
- Blind post-upgrade subagent sessions are tested with ordinary prompts that do not mention KH, UAF, skill, harness, or front-door.
- Front-door runtime output from `kh-uaf/2.9.30` cache paths is accepted as active runtime evidence.
- Selected follow-up harnesses are reported as selected or skipped, not as runtime applied.

## Local Verification

- `python -B -m src.skills.uaf_skill_catalog --check`: passed, `40 valid / 0 invalid`.
- `python -B skills\always_on_front_door\scripts\smoke_check.py`: passed, including a packaged test reference for the slim runtime branch.
- `python -B skills\always_on_front_door\scripts\demo.py --output-dir <external temp>`: passed, with success and stale-cache blocked cases.
- `python -B -m src.orchestration.kh_front_door --prompt "<ordinary dashboard request>" --project <target> --host codex --summary`: passed, `runtime_applied_skills` included `always-on-front-door`, `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog`.
- `python -B -m src.orchestration.session_skill_audit <019e8178...jsonl> --summary`: failed the historical session as expected and now reports `always-on-front-door` as required/missing.
- `python -B -m src.orchestration.plugin_install_audit --summary --repo <repo>` after user upgrade: `ok`, installed cache `2.9.30`, expected source version `2.9.30`.
- `python -B -m unittest discover -s tests`: passed, `488 tests`.
- `python -B -m src.skills.uaf_skill_quality --summary`: passed, `40 valid`, `lowest_quality_score: 9.3`, `low_quality_skills: []`.
- `python -B -m src.benchmarks.kh_bench_verified --summary`: passed, `8/8`.
- `python -B -m src.benchmarks.practical_quality_gate --summary`: passed, `release_ready: true`, `practical_confidence_score: 10.0`.

## 2.9.32 Structure Rework

The first implementation still left KH too dependent on a model voluntarily remembering long skill text. The 2.9.32 rework makes the entry loop more Superpowers-like:

- The Codex plugin `defaultPrompt` was rewritten around a short `KH ENTRY LOOP` instead of a long feature inventory.
- All 40 packaged `SKILL.md` files now contain a common `## KH Entry Contract`.
- The shared contract says every non-trivial turn starts through `always-on-front-door`, `kh_active_directive=active` carries across later work-bearing turns, selected skills are not execution evidence, and a skill is `applied` only after concrete runtime/gate/artifact/passthrough/blocked evidence.
- `session_skill_audit` now detects a prior "actively use KH skills/harnesses" instruction and flags later ordinary work that skips front-door as `trigger_kind: kh_active_directive`.
- Tests lock this down through `test_all_packaged_skills_share_kh_entry_contract` and the new `kh_active_directive` session-audit cases.

Verification after this rework:

- `python -B -m unittest discover -s tests`: passed, `488 tests`.
- `python -B -m src.skills.uaf_skill_catalog --check`: passed, `40 valid / 0 invalid`.
- `python -B -m src.skills.uaf_skill_quality --summary`: passed, `lowest_quality_score: 9.3`, `low_quality_skills: []`.
- `python -B -m src.benchmarks.kh_bench_verified --summary`: passed, `8/8`.
- `python -B -m src.benchmarks.practical_quality_gate --summary`: passed, `release_ready: true`.
- `git diff --check`: passed.

## Blind Subagent Verification

Blind prompt sent to subagent `019e81b8-e19c-7b01-add2-ee6957be73c9` did not mention KH, UAF, skill, harness, or front-door. It only asked for a small static KPI dashboard under `C:\Users\KONEIT\Desktop\Jang\SKillsTest\BlindAutoRoute_20260601_A`.

Evidence:

- Active session skill list used installed cache paths under `kh-uaf/2.9.30`.
- The subagent inspected `always-on-front-door` and `automatic-intake-harness` without being told to do so.
- The subagent ran `python -m src.orchestration.kh_front_door ...` from `C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.30`.
- The front-door output reported `front_door_status: ok`.
- Runtime-applied front-door skills were `always-on-front-door`, `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog`.
- Generated deliverable files were created only in the requested target folder.
- Local verification report passed static file checks, no external dependencies, KPI data/cards/table checks, and filter-button simulation.

Post-fix session audit of that same blind run:

- `runtime_applied_skill_names` includes `always-on-front-door`, `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog`.
- `selected_not_executed_skills` are no longer counted as runtime applied.
- The remaining audit findings are about follow-up harnesses not fully executed, not about missing front-door intake.

## Residual Risk

This patch proves the upgraded 2.9.30 plugin can be selected automatically in a blind subagent session. It still cannot force the Codex host to load or obey a skill in every possible future session. If a fresh session has no KH UAF skills in its available skill list, the remaining fix is host/plugin loading. If it loads KH but skips all front-door evidence again, `session_skill_audit` should now flag that as a P1 `always-on-front-door` miss.

## 2.9.33 Carryover Regression

Post-upgrade subagent session `019e8202-72ca-7232-a46f-783a45bf1a7f` used an ordinary dashboard request without naming KH. The session ran `kh_front_door` from installed cache `kh-uaf/2.9.32` before work exploration and `session_skill_audit` reported runtime-applied skills: `always-on-front-door`, `automatic-intake-harness`, `goal-state-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog`. This proved the blind case was improved.

Post-upgrade carryover subagent session `019e8202-975a-7e70-a274-dc92f5bda645` first received "use KH skills/harnesses actively" and then an ordinary dashboard request. It still ran `Test-Path` and a `MEMORY.md` search before `kh_front_door`, so `session_skill_audit` correctly reported P1 `missing_front_door`. That is a real failure, not a false pass.

Fixes added in 2.9.33:

- `session_skill_audit` now recognizes real Korean active-use wording such as "KH 스킬/하네스를 적극적으로 써서 작업해줘" as `kh_active_directive`.
- Codex `defaultPrompt` now explicitly says `Test-Path`, `Get-ChildItem`, `rg`, file reads, MEMORY.md searches, and browser/document/image/plugin actions are work exploration and must happen after front-door intake.
- `always-on-front-door` usage docs now call out target-folder checks and memory lookup as forbidden pre-intake work for non-trivial requests.

Verification target after installing 2.9.33: repeat the carryover subagent scenario and require zero `missing_front_door` issues for the second turn.

## 2.9.34 Order-Evidence Regression

Post-upgrade subagent sessions `019e821c-4557-7f11-abc1-3d964542013f` and `019e821c-4710-7d51-8385-94cc75cebe61` showed a stricter failure:

- Both sessions announced `always-on-front-door`.
- Both sessions read/inspected KH skill guidance.
- Both sessions still executed target-folder `Test-Path` / `Get-ChildItem` before the actual `python -m src.orchestration.kh_front_door ... --summary` command.

That means the previous audit accepted SKILL.md reads or front-door mentions too broadly as order evidence. The correct standard is stricter: for non-trivial work, the first standalone work-bearing tool call must be `kh_front_door`, or the session must record an explicit light/direct or blocked rationale. Target-folder checks must not run before that command, even in the same parallel tool batch.

Fixes added in 2.9.34:

- `session_skill_audit` now uses strict order evidence for `missing_front_door`: only the `src.orchestration.kh_front_door` command or real front-door runtime JSON output can satisfy the entry order gate.
- Skill catalog reads, SKILL.md output, assistant messages that mention `always-on-front-door`, and `kh-uaf` metadata no longer satisfy the order gate.
- Unit coverage now fails a session that lists the skill catalog or reads `always-on-front-door` docs, then starts `Get-ChildItem`.
- The plugin prompt and `always-on-front-door` docs now explicitly forbid parallelizing `Test-Path`, `Get-ChildItem`, `rg`, file reads, or MEMORY.md searches in the same pre-intake batch.

Verification target after installing 2.9.34: repeat the blind and carryover subagent scenarios and require the first non-trivial tool call after the user request to be `python -m src.orchestration.kh_front_door ... --summary`, with target-folder checks only after that command.
