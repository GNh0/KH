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

## 2.9.87 Follow-up: Global Memory Scope Audit

Trigger: session `019f121a-087c-7c93-b2df-816a521789ea` appeared to reuse old `MaxWidth` context despite KH memory isolation rules. Independent review did not prove `MaxWidth` came from global memory; the strongest evidence was same-session/source-backed `PR300400` and `PR300500` `MaxWidth` reads plus user-provided `MaxWidth` snippets. The real audit bug was that global `MEMORY.md` reads and final memory citations were not flagged.

Changes:

- Split "session id/log lookup" from "global Codex memory import approval".
- Session ids now authorize reading the named session log only; they do not authorize `%CODEX_HOME%/memories/MEMORY.md` lookup or citation.
- Added `global_memory_citation_without_scope_approval` so final/user-facing `MEMORY.md` citations are flagged even when no direct tool-read sample is available.
- Removed broad approval markers from scoped import evidence: `memory_scope_decision`, `global_memory_candidate`, and passive SKILL.md/front-door text no longer suppress global-memory issues.
- Only explicit approved evidence such as `memory_import_approved`, `parent_memory_access_approved`, or approved/applied `explicit_cross_scope_memory_import` suppresses global-memory warnings.
- Excluded developer/system citation-format examples from the citation detector.
- Global-memory approval is now evaluated in event order. A later approval request does not retroactively authorize an earlier `MEMORY.md` read or citation.
- Boolean approval fields must be truthy. `memory_import_approved=false`, `parent_memory_access_approved=false`, or explanatory mentions of those field names do not authorize global memory.
- Passive tool outputs such as SKILL.md examples containing `<oai-mem-citation>` are not treated as final/user-facing global-memory citations.
- `task_complete.last_agent_message` is treated as user-facing completion output, so a final completion message containing an unapproved `MEMORY.md` citation is flagged.

Regression coverage:

- `test_explicit_session_id_does_not_approve_global_memory_lookup`
- `test_explicit_session_id_allows_session_log_lookup_not_memory_index`
- `test_memory_scope_decision_does_not_approve_global_memory_lookup`
- `test_global_memory_citation_requires_explicit_scope_request`
- `test_developer_memory_citation_example_is_not_global_memory_leak`
- `test_structured_memory_citation_requires_explicit_scope_request`
- `test_explicit_memory_md_request_allows_global_memory_citation`
- `test_false_memory_import_approval_does_not_approve_global_memory_lookup`
- `test_plain_approval_marker_explanation_does_not_approve_global_memory_lookup`
- `test_later_global_memory_request_does_not_retroactively_approve_prior_lookup`
- `test_prior_global_memory_request_allows_later_lookup`
- `test_passive_tool_output_memory_citation_example_is_not_global_memory_leak`
- `test_task_complete_memory_citation_requires_explicit_scope_request`

Subagent review evidence:

- Noether found the root cause: session-id/log wording was treated as global-memory approval and suppressed both `MEMORY.md` read samples and citation samples.
- Laplace found `MaxWidth` itself was not proven to be memory-derived, but the session repeatedly read/cited global memory while front-door policy said global memory was not allowed without explicit approval.
- Bohr found four follow-up gaps: false approval fields were accepted, later global-memory approval retroactively suppressed earlier violations, passive tool-output citation examples could be misclassified, and `task_complete.last_agent_message` was not treated as user-facing citation output. All four are now covered by regression tests.

Verification:

- Targeted memory-scope regression tests passed.
- Actual session `019f121a-087c-7c93-b2df-816a521789ea` now reports:
  - `global_memory_citation_without_scope_approval` P1
  - `cross_chat_memory_leak` P1
- `python -B -m unittest tests.test_session_skill_audit tests.test_kh_front_door_always_on tests.test_kh_front_door tests.test_runtime_memory`
  - 158 tests passed.
- `python -B -m unittest tests.test_session_skill_audit`
  - 108 tests passed.
- `python -B -m unittest tests.test_kh_front_door_always_on tests.test_kh_front_door tests.test_runtime_memory tests.test_session_postmortem_guards tests.test_token_optimizer_gate_integration tests.test_skill_transitions`
  - 99 tests passed.
- `python -B -m unittest discover -s tests -q`
  - 736 tests passed.
- No-write compile check for `src/orchestration/session_skill_audit.py` and `tests/test_session_skill_audit.py`
  - Passed.

Operational step:

- Bumped plugin manifests to `2.9.87`.
- After push, upgrade KH UAF in Codex so the installed cache moves to `2.9.87`, then re-run the memory-scope/session audit scenario in a fresh session.

Remaining risk:

- Host-level memory injection can still appear in the model prompt before KH code runs. KH cannot prevent host injection, but the session audit now catches unsupported global-memory use/citation after the fact.
- A session may still use a memory-derived idea without citation or explicit tool read. That cannot be proven deterministically; reviewers should treat unexplained old-context behavior as a qualitative finding and add targeted scenarios when reproducible.
