# 2026-06-02 Brainstorm Front-Door Regression

## Problem

Blind subagent usage showed that a plain request such as:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\BrainstormEntryOnly_20260601_B folder needs an operations support product built.
```

ran KH front-door only after an initial cwd import failure, then classified the request as `ambiguous/software` with route `clarify`. The result did not select `brainstorming-harness`, did not build a `BrainstormSession`, and did not produce `brainstorm_handoff` evidence.

That was not acceptable for KH's always-on behavior. A user should not need to explicitly name KH, UAF, brainstorming, a skill, or a harness for early product/project discovery.

## Fix

- Added product-discovery routing in `src.orchestration.request_classifier`.
- Vague product/service/app/tool/platform creation requests now select `brainstorming-harness` before implementation.
- Specific implementation requests with details such as HTML, API, KPI, verification, tests, screen, drawing, or export formats remain on implementation/design routes.
- Compliance/security/privacy/devops/high-risk requests are excluded from the brainstorming shortcut.
- Added `skills/always_on_front_door/scripts/front_door.py` so front-door can run from target folders and subagent workspaces without `ModuleNotFoundError: No module named 'src'`.
- Updated always-on front-door skill docs, usage reference, examples, plugin default prompt, and session audit detection to recognize the wrapper path.
- Bumped plugin manifests to `2.9.37`.

## Evidence

Classifier check:

```text
python -B -m src.orchestration.request_classifier "C:\work\BrainstormEntryOnly folder needs an operations support product built."
```

Expected result:

- `complexity: medium`
- `domain: product`
- `recommended_execution: skill_read`
- `recommended_skills` includes `brainstorming-harness`
- `required_harnesses` includes `brainstorming-harness`
- `evidence_required` includes `brainstorm_handoff`

Front-door check:

```text
python -B -m src.orchestration.kh_front_door --prompt "C:\work\BrainstormEntryOnly folder needs an operations support product built." --project "C:\work\BrainstormEntryOnly" --host codex --summary
```

Expected result:

- `front_door_status: ok`
- `plugin_route.controller: kh`
- `selected_not_executed_skills` includes `brainstorming-harness`
- `required_next_actions` tells the host to apply `brainstorming-harness` before implementation.
- `runtime_applied_skills` remains limited to front-door runtime skills and does not falsely claim brainstorming execution.

Wrapper check from a non-repo cwd:

```text
python -B C:\Users\KONEIT\Desktop\Jang\KH\skills\always_on_front_door\scripts\front_door.py --prompt "C:\work\BrainstormEntryOnly folder needs an operations support product built." --project "C:\work\BrainstormEntryOnly" --host codex --summary
```

Expected result: same front-door summary without import failure.

## Regression Tests

- `tests.test_request_classifier.RequestClassifierTests.test_vague_product_development_routes_to_brainstorming`
- `tests.test_request_classifier.RequestClassifierTests.test_specific_verified_html_tool_does_not_route_to_brainstorming`
- `tests.test_kh_front_door.KhFrontDoorTests.test_vague_product_development_selects_brainstorming_without_kh_terms`
- `tests.test_kh_front_door.KhFrontDoorTests.test_skill_local_front_door_wrapper_runs_outside_repo_root`
- `tests.test_session_skill_audit.SessionSkillAuditTests.test_skill_local_front_door_wrapper_counts_as_front_door_evidence`

## Remaining Verification Target

After installing or upgrading to `2.9.38`, run a fresh blind subagent test with a plain prompt that does not mention KH or brainstorming:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\BrainstormEntryOnly_20260602_A folder needs an operations support product built.
```

Passing requires front-door before target-folder inspection, `brainstorming-harness` selection, and a visible brainstorming question/options/handoff path before implementation.

## 2026-06-02 Blind Subagent Result

Session:

```text
C:\Users\KONEIT\.codex\sessions\2026\06\02\rollout-2026-06-02T09-21-36-019e85b5-0fa5-7793-a9e2-47d1b761050d.jsonl
```

Prompt:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\BrainstormEntryOnly_20260602_C 폴더에 운영지원 제품 개발해줘.
```

Positive evidence:

- The session eventually ran `kh_front_door`.
- Front-door classified the request as `medium/product`.
- The agent read `brainstorming-harness`.
- The run wrote `.kh/brainstorm/20260602_C/state/session.json`.
- The run wrote `docs/kh/handoffs/brainstorm_handoff.md`.

Failures:

- The agent read `always_on_front_door/SKILL.md` and ran `Get-ChildItem` on the target folder before front-door runtime. Reading SKILL.md is not runtime evidence.
- `session_skill_audit` previously accepted `always_on_front_door` too broadly as order evidence after the wrapper change. That made the early folder read look cleaner than it was.
- The agent treated the vague product request as approval to implement and created an app in the same turn. That bypassed the intended brainstorming approval checkpoint.
- The agent read prior memory about `SKillsTest` after front-door and used it to shape the run. For independent target folders, prior/sibling context should not seed the new brainstorm unless the user asks for reuse.

Fixes after this result:

- `session_skill_audit` now counts `front_door.py` and `src.orchestration.kh_front_door` as front-door order evidence, but does not count `always_on_front_door/SKILL.md` reads.
- `kh_front_door.required_next_actions` now says `brainstorming-harness` must stop before implementation/scaffolding/product code until the user approves the direction in a later message.
- `brainstorming-harness` SKILL, usage reference, and minimal workflow now explicitly mark immediate implementation after vague product discovery as a failure.
- Plugin default prompt now states that vague product/app/service requests are not implementation approval.

Next install target: `2.9.38`.
