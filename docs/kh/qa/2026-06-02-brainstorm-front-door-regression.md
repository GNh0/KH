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

After installing or upgrading to `2.9.37`, run a fresh blind subagent test with a plain prompt that does not mention KH or brainstorming:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\BrainstormEntryOnly_20260602_A folder needs an operations support product built.
```

Passing requires front-door before target-folder inspection, `brainstorming-harness` selection, and a visible brainstorming question/options/handoff path before implementation.
