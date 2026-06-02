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

This is not only a brainstorming prompt weakness. In this host mode, the subagent receives base/system skills but not KH personal marketplace plugin skills, so the KH plugin cannot self-trigger inside that subagent. KH needs an additional Codex global bootstrap skill under `$CODEX_HOME/skills` for subagent blind routing, or the host must start a fresh parent thread that actually injects the KH marketplace skills.

Follow-up fix for `2.9.39`:

- Add `scripts/install_codex_global_bootstrap.py`.
- The installer writes `$CODEX_HOME/skills/kh-uaf-front-door/SKILL.md`.
- The global skill locates the latest installed `kh-uaf@kh-uaf-marketplace` cache and delegates to `skills/always_on_front_door/scripts/front_door.py`.
- This keeps the full KH logic in the plugin cache while making Codex subagent skill discovery see a trigger-focused bootstrap skill.

## 2026-06-02 Global Bootstrap Subagent Result

Session:

```text
C:\Users\KONEIT\.codex\sessions\2026\06\02\rollout-2026-06-02T10-02-35-019e85da-946d-7611-82c2-a1118b4b60f9.jsonl
```

Prompt:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\BlindProductRequest_20260602_E 폴더에 운영지원 제품 개발해줘.
```

Positive evidence:

- The subagent saw `kh-uaf-front-door` in the available skill list.
- The subagent also saw packaged `kh-uaf:always-on-front-door` after the latest plugin install.
- The subagent ran the installed cache wrapper `skills/always_on_front_door/scripts/front_door.py`.
- Front-door returned `front_door_status: ok`, `complexity: medium`, `domain: product`.
- The subagent read `brainstorming-harness`, presented options, and stopped for approval.
- `C:\Users\KONEIT\Desktop\Jang\SKillsTest\BlindProductRequest_20260602_E` was not created.

Remaining failure:

- The first tool batch still read `MEMORY.md` and checked the target folder before front-door runtime.
- `session_skill_audit` correctly flagged P1 `always-on-front-door` `missing_front_door`.

Follow-up adjustment:

- Strengthen the global skill frontmatter description and immediate action text so the model sees, before opening SKILL.md, that the skill must be read alone and the next standalone tool call must be front-door before any memory or target-folder work.

## 2026-06-02 Global Bootstrap Retest

Session:

```text
C:\Users\KONEIT\.codex\sessions\2026\06\02\rollout-2026-06-02T10-05-29-019e85dd-3d1d-7f13-9662-619b07a4eb0d.jsonl
```

Prompt:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\BlindProductRequest_20260602_F 폴더에 운영지원 제품 개발해줘.
```

Passing evidence:

- First tool call: read `$CODEX_HOME/skills/kh-uaf-front-door/SKILL.md`.
- Second standalone tool call: run installed `skills/always_on_front_door/scripts/front_door.py`.
- No `MEMORY.md` lookup, target folder check, sibling scan, or implementation happened before front-door runtime.
- Front-door returned `front_door_status: ok`, `complexity: medium`, `domain: product`, and selected `brainstorming-harness`.
- The subagent read installed `brainstorming_harness/SKILL.md` only after front-door.
- The subagent presented three product directions and stopped for user approval.
- `C:\Users\KONEIT\Desktop\Jang\SKillsTest\BlindProductRequest_20260602_F` was not created.
- `session_skill_audit` reported runtime-applied front-door skills: `always-on-front-door`, `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog`; it did not report P1 `always-on-front-door` `missing_front_door`.

Residual notes:

- The subagent still searched memory after front-door and after reading `brainstorming-harness`. That is no longer an entry-order failure, but independent target folders should avoid sibling/prior context unless explicitly requested. Future tightening can make brainstorming-harness treat prior memory as opt-in for independent target creation.
- The session audit still reports unrelated missing evidence for large-work/development deliverable harnesses because the subagent intentionally stopped before implementation. Those are not blockers for the blind front-door + brainstorming gate objective.
