# KH UAF Runtime Routing Hardening Report - 2026-06-29

## Scope

This change hardens KH UAF runtime routing and verification after repeated live-session failures where skills were selected too broadly, not applied, or allowed execution before required gates.

## Changes

- Added an invariant ambiguity gate for visual/order/query prompts without an explicit target layer.
  - Blocks prompts such as image-like ordering/query requests until the user clarifies whether the target is DB ordering, UI display, report layout, or SQL formatting.
  - Keeps inline SQL or explicit `execution_layer=sql` actionable.
- Split brainstorming direction approval from implementation approval.
  - `brainstorm_handoff_approved` no longer counts as separate implementation approval.
  - Execution requires handoff, design review approval, and separate implementation/execution approval.
- Strengthened `BrainstormSession` validation.
  - Requires `intent_frame`, `problem_frame`, `option_frame`, `approval_frame`, `handoff_frame`, and `self_review` metadata.
- Separated token optimizer usage status from skill application status.
  - `token_optimizer_status` is now limited to `used`, `considered_not_needed`, `passthrough`, or `blocked`.
  - Front-door immediate-gate selection maps to `blocked` until real token evidence exists.
- Added machine-readable front-door `memory_policy`.
  - Project/chat scope by default.
  - Global Codex memory lookup/write is disabled unless explicit cross-scope import is approved.
- Made SQL style verification attach to any actual `sql-formatting` provider route.
  - Mention-only risk examples still do not select `sql-formatting` or the KH SQL verifier.
- Extended practical release gate.
  - Requires plugin install audit.
  - Requires installed-cache `always_on_front_door/scripts/front_door.py` smoke evidence.
- Added regression coverage in classifier, front-door, scenario evaluator, skill bundle, practical gate, and brainstorming/demo paths.
- Bumped plugin manifests to `2.9.85`.

## Subagent Review Evidence

- Tesla reviewed installed-cache/runtime split and identified missing release gates around Codex plugin cache smoke.
- Dirac reviewed workflow UX and identified token status conflation, weak brainstorming validation, missing memory policy, and SQL verifier coverage.
- Fermat reviewed the first patch and found two remaining P1 gaps:
  - legacy `brainstorm_handoff_approved` bypassed separate implementation approval.
  - visual/query/order ambiguity was bypassed when `has_active_artifact=true`.
- Nietzsche performed final QA after the follow-up patch and found no blocking issues.

## Verification

Latest source-checkout verification after version bump:

- `python -B -m unittest tests.test_request_classifier tests.test_kh_front_door tests.test_practical_quality_gate tests.test_skill_application_bundle tests.test_sql_formatting_style_harness tests.test_session_skill_audit tests.test_brainstorming_harness tests.test_project_markdown_artifacts tests.test_skill_demos`
  - 268 tests passed.
- `python -B -m src.orchestration.scenario_evaluator --summary --stress`
  - 194/194 scenarios passed.
- `python -B -m src.benchmarks.practical_quality_gate --summary`
  - Passed before version bump with installed cache `2.9.84` and source `2.9.84`.
  - After source version bump to `2.9.85`, install audit correctly reports the local installed cache `2.9.84` as behind until Codex marketplace upgrade is performed.
- Practical gate read-only check:
  - `git diff --binary` hash was identical before and after practical gate execution.

## Remaining Operational Step

After this commit is pushed, upgrade KH UAF in Codex so the installed cache moves from `2.9.84` to `2.9.85`, then open a fresh session before judging blind automatic intake.

## 2.9.86 Follow-up: Subagent Token Evidence Gate

Trigger: live blind subagent tests produced plausible answers, but the test assessment did not fail the run when `token-optimizer` evidence was absent. That was an evaluation gap: response quality and actual skill/harness application must be judged separately.

Changes:

- Treat any spawned subagent as requiring an explicit token optimizer decision for task packets/transcripts.
- Count namespaced subagent tools such as `multi_agent_v1.spawn_agent` and `multi_agent_v1.close_agent`.
- Count subagent tools wrapped inside `multi_tool_use.parallel` via `tool_uses[].recipient_name`.
- Block token optimizer status when subagents ran but no runtime optimizer, passthrough, or explicit `considered_not_needed` decision exists.
- Require an explicit non-empty `not_used_reason` field before accepting `token_optimizer_status=considered_not_needed`; generic `token_optimizer_status_reason`, `rationale`, or provider metadata is not enough.
- Replace raw internal token-gate reason keys in user-facing audit output with readable wording.
- Update token-gate remediation text to include the valid short-content escape hatch: explicit `considered_not_needed` with `not_used_reason`.

Subagent review evidence:

- Galileo found a P1: `considered_not_needed` could pass with only `token_optimizer_status` and `token_optimizer_provider`, without `not_used_reason`.
- Ampere confirmed the missing-token-evidence failure was visible but flagged confusing internal reason text and the same weak `considered_not_needed` acceptance.
- Godel confirmed the focused test went red after the reason text was made human-readable, and requested coverage for missing `not_used_reason`, namespaced close tools, and `multi_tool_use.parallel` wrappers.
- Averroes found a final blocker: `considered_not_needed` still accepted alternate rationale fields without `not_used_reason`. That path is now blocked and covered by regression tests.

Verification:

- `python -m unittest tests.test_session_skill_audit`
  - 95 tests passed.
- `python -m unittest tests.test_token_optimizer_gate_integration tests.test_skill_transitions`
  - 14 tests passed.
- `python -m unittest tests.test_token_optimizer_gate_integration tests.test_workflow_usability_layer`
  - 19 tests passed.
- `python -m unittest discover -s tests -q`
  - 723 tests passed.
- `python -m py_compile src\orchestration\session_postmortem.py src\orchestration\session_skill_audit.py tests\test_session_skill_audit.py`
  - Passed.
- Synthetic audit check:
  - `multi_tool_use.parallel` containing `multi_agent_v1.spawn_agent` and `multi_agent_v1.close_agent` is counted as `spawned=1`, `closed=1`.
  - Missing token decision yields `token_optimizer_status=blocked`.
  - `considered_not_needed` with `token_optimizer_status_reason` but no `not_used_reason` remains blocked.
  - Audit action says to run token optimizer, record runtime evidence, record passthrough, or record explicit `considered_not_needed` with `not_used_reason`.

Operational step:

- Bumped plugin manifests to `2.9.86`.
- After push, upgrade KH UAF in Codex so the installed cache moves to `2.9.86`, then rerun blind subagent tests. A blind subagent response without token optimizer evidence should now fail the session audit instead of being treated as acceptable.
