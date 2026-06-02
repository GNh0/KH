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

## 2026-06-02 Blind Subagent Result After 2.9.38 Install

Session:

```text
C:\Users\KONEIT\.codex\sessions\2026\06\02\rollout-2026-06-02T09-51-32-019e85d0-79bf-7ba2-bd8c-693a04edaf55.jsonl
```

Prompt:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\BlindProductRequest_20260602_D 폴더에 운영지원 제품 개발해줘.
```

Install evidence before the run:

- `kh-uaf@kh-uaf-marketplace` installed cache version: `2.9.38`.
- `skills/always_on_front_door/scripts/front_door.py` existed under the installed cache.
- `plugin_install_audit` status: `ok`.

Result:

- The subagent still did not run KH front-door.
- `session_skill_audit` reported `runtime_applied_skills: 0`.
- The first work actions were target folder inspection and `MEMORY.md` lookup.
- The subagent read sibling/prior `SKillsTest` outputs and implemented product files immediately.
- It created `index.html`, `src/app.js`, `src/styles.css`, `README.md`, sample data, and a smoke test before any brainstorming approval checkpoint.

Root-cause evidence:

- The subagent session metadata had no KH text in `base_instructions`.
- The subagent JSONL did not contain `KH BOOTSTRAP OVERRIDE`.
- The subagent JSONL did not contain `kh-uaf:always-on-front-door`.
- The subagent did contain a generated `Available skills` section, but KH marketplace skills were absent.

Conclusion:

The 2.9.38 failure was a plugin injection/session freshness problem, not a reason to require a separate user-level skill install. KH must behave like a plugin: install or upgrade the marketplace plugin once, open a fresh session, and let the installed plugin cache expose `kh-uaf:always-on-front-door`.

## 2026-06-02 Plugin-Only Subagent Result After 2.9.39 Install

Session:

```text
C:\Users\KONEIT\.codex\sessions\2026\06\02\rollout-2026-06-02T10-20-11-019e85ea-b271-74d2-abc5-6cfc3a9dfd33.jsonl
```

Prompt:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\BlindProductRequest_20260602_H 폴더에 운영지원 제품 개발해줘.
```

Positive evidence:

- No separate user-level KH skill existed before the run.
- First KH skill read came from the installed plugin cache: `kh-uaf-marketplace\kh-uaf\2.9.39\skills\always_on_front_door\SKILL.md`.
- The subagent ran the installed cache wrapper `skills\always_on_front_door\scripts\front_door.py`.
- Front-door returned `front_door_status: ok`, `complexity: medium`, `domain: product`, `route: kh single`.
- The subagent read `brainstorming-harness`, presented three directions, and stopped for user approval.
- `C:\Users\KONEIT\Desktop\Jang\SKillsTest\BlindProductRequest_20260602_H` was not created.

Remaining failure:

- The first tool batch read `MEMORY.md` in parallel with the always-on skill read before front-door runtime.
- That means plugin-only discovery worked, but the strict "front-door first and alone" rule did not fully hold.
- `session_skill_audit` still reported a P1 `always-on-front-door` issue for that ordering miss.

2.9.40 correction:

- Remove the separate bootstrap installer and its tests from the repository.
- Remove README guidance that asked users to create a user-level skill copy.
- Strengthen `.codex-plugin/plugin.json` and `skills/always_on_front_door/SKILL.md` so plugin-only front-door is the only supported Codex bootstrap path.
- Add a regression test that treats an initial always-on skill read plus `MEMORY.md` search in the same first batch as a front-door miss.

Next install target: `2.9.40`.

Passing requires a fresh subagent whose first work-bearing sequence is: installed plugin cache `kh-uaf:always-on-front-door` read, then front-door wrapper command, then any memory lookup, target-folder check, brainstorming skill read, or implementation decision.

## 2026-06-02 Plugin-Only Subagent Pass After 2.9.40 Install

Session:

```text
C:\Users\KONEIT\.codex\sessions\2026\06\02\rollout-2026-06-02T10-51-37-019e8607-7984-79a0-853a-a9158c1030cb.jsonl
```

Prompt:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\BlindProductRequest_20260602_I 폴더에 운영지원 제품 개발해줘.
```

Install/cache evidence:

- `plugin_install_audit --summary` status: `ok`.
- Expected source version: `2.9.40`.
- Latest installed cache version: `2.9.40`.
- Installed cache versions: `["2.9.40"]`.
- No user-level KH bootstrap existed: `C:\Users\KONEIT\.codex\skills\kh-uaf-front-door\SKILL.md` returned `False`.

Passing order evidence:

- First tool call read the installed plugin cache skill:
  `C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.40\skills\always_on_front_door\SKILL.md`.
- The next work-bearing tool call ran:
  `C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.40\skills\always_on_front_door\scripts\front_door.py`.
- No `MEMORY.md` lookup, target-folder check, sibling scan, or implementation happened before front-door runtime.
- Front-door returned `front_door_status: ok`, `complexity: medium`, `domain: product`, `route: kh single`.
- `recommended_skills` included `brainstorming-harness`.
- The subagent then read `brainstorming-harness` from the same `2.9.40` plugin cache.
- The target folder `C:\Users\KONEIT\Desktop\Jang\SKillsTest\BlindProductRequest_20260602_I` was not created.
- The final answer offered three product directions and stopped for user approval before scaffolding or product code.

Session audit evidence:

- `session_skill_audit --summary` reported runtime-applied skills:
  `always-on-front-door`, `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, `skill-catalog`.
- The audit did not report a P1 `always-on-front-door` `missing_front_door` issue.
- The remaining audit issues are broad large-session/deliverable skill accounting warnings caused by inherited session size and the fact that the subagent intentionally stopped before implementation. They are not failures of the blind plugin-only front-door plus brainstorming gate objective.

Conclusion:

The requested plugin-only behavior is verified for the blind product-development prompt: KH was not named by the user, no global skill copy was present, the subagent used the installed `2.9.40` plugin cache, front-door ran before memory/target inspection, `brainstorming-harness` was selected and read, and implementation was blocked pending product-direction approval.
