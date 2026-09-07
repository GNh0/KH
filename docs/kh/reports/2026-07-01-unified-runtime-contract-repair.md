# 2026-07-01 Unified Runtime Contract Repair

## Objective

Align KH UAF with the user's current contract:

- KH must behave as an installed plugin runtime, not as a manual `$CODEX_HOME/skills` copy.
- Non-trivial work starts through `kh-uaf:always-on-front-door`.
- SKILL.md reads and selected follow-up skills are not execution evidence.
- Token Optimizer is an always-on decision gate for non-trivial KH turns.
- Memory remains project/chat/subagent-lineage scoped by default; host-global Codex memory is a separate explicit promotion target.
- Host-local specialists such as `sql-formatting` must not be hidden by KH.
- Brainstorming, role orchestration, GoalState, workflow usability, and verification gates must leave audit evidence.

## Applied KH Gates

- `always-on-front-door`: ran first against the current installed cache and target repo.
- `goal-state-harness`: active host GoalState is tracking this repair.
- `workflow-usability-harness`: token provider/status, memory policy, and resume/report evidence were recorded.
- `host-agent-orchestration`: delegated a bounded routing regression patch to a worker subagent and preserved its result.
- `parallel-orchestration-harness`: used read-only/worker side-agent strategy with main-controller integration.
- `memory-state-harness`: wrote a scoped Codex memory update note only after explicit user request.
- `token-optimizer`: gate checked before broad work; exact review/test output was kept or summarized only when safe.

## Subagent Evidence

Worker `Dirac` handled the focused routing patch:

- read-only Korean KH audit prompt no longer escalates to large-work preflight.
- named DML SQL style prompt now routes to host-local `sql-formatting` and immediate `sql-formatting-style-harness`.
- worker tests passed for request classifier, front-door, SQL formatting style, and exact regression cases.

Reviewer `Poincare` checked the integrated patch:

- confirmed read-only audit overclassification, SQL specialist routing, Token Optimizer lifecycle split, scoped memory boundary, and stricter session audit evidence.
- kept one release condition: installed Codex cache must be upgraded from `2.9.95` to source `2.9.96` before claiming blind runtime adoption.

Reviewer `Hubble` found two release blockers that were fixed in this report cycle:

- provider meta-review prompts such as `Review whether SQL-formatting is not hidden by KH routing.` no longer invoke the SQL formatter and no longer escalate to large-work preflight.
- English DML formatting prompts such as `Format this SQL and align the INSERT, UPDATE, DELETE blocks to our style.` now route to `sql-formatting` with immediate `sql-formatting-style-harness`.
- `plugin_install_audit` now separates benign descriptor/source-ref explanatory notes from actionable findings.

## Code Changes

- `src/orchestration/request_classifier.py`
  - expanded large-work bundle coverage.
  - added Korean read-only audit/no-edit/source vocabulary.
  - added SQL terms for domain detection.
  - added strong software product override that requires implementation intent.
  - added medium SQL formatting style routing before generic software-heavy detection.
  - added provider/routing meta-review routing so provider names in review prompts are not treated as invocation.
- `src/orchestration/plugin_composition.py`
  - added named DML SQL style detection for prompts that mention INSERT/UPDATE/DELETE SQL without a full SQL block.
  - made SQL meta-review context suppress explicit provider invocation.
- `src/orchestration/kh_front_door.py`
  - added `token_optimizer_lifecycle` summary so gate checks are separated from actual optimization.
- `src/orchestration/plugin_install_audit.py`
  - separated descriptor/source-ref explanatory notes from actionable findings.
- `src/orchestration/runtime_memory.py`
  - tightened scoped memory behavior and provider policy evidence.
- `src/orchestration/session_skill_audit.py`
  - tightened skill application evidence, GoalState evidence, token optimizer lifecycle evidence, SQL verifier checks, and orchestration status auditing.
- `src/orchestration/skill_application.py`
  - expanded default large-work skill status coverage and changed Token Optimizer bundle status to considered unless actual optimization evidence exists.
- `src/skills/uaf_skill_validator.py`
  - added a packaged skill contract check for `## KH Entry Contract`.
- `README.md`, `README.ko.md`, `SKILL.md`, `docs/README.md`
  - clarified current product surface, historical docs boundary, plugin/cache behavior, and audited-not-assumed host compliance.
- `.codex-plugin/plugin.json`, `plugin.json`
  - bumped version to `2.9.96` and kept manifest versions synchronized.

## Regression Samples

Validated with real front-door samples:

- Read-only KH session audit:
  - `medium / software / skill_read`
  - no `blocked_until_large_work_preflight`
  - immediate next skill: `workflow-usability-harness`
- SQL-formatting meta-review:
  - `medium / software / skill_read`
  - controller: `kh`
  - no `sql-formatting-style-harness`
- English DML SQL formatting:
  - `medium / software / skill_read`
  - controller: `sql-formatting`
  - immediate next skill: `sql-formatting-style-harness`
- Inventory dashboard direction-only request:
  - `medium / operations / skill_read`
  - `blocked_until_brainstorming_handoff`
  - immediate next skill: `brainstorming-harness`
- SQL style request mentioning INSERT, UPDATE, DELETE:
  - `medium / software / skill_read`
  - plugin route controller: `sql-formatting`
  - immediate next skill: `sql-formatting-style-harness`
- SaaS CRM MVP with auth/API/tests/i18n:
  - `heavy / software / role_dag`
  - `blocked_until_large_work_preflight`
  - immediate next skills: GoalState, workflow usability, host-agent orchestration, parallel orchestration.

## Verification

Passed:

- `python -B -m unittest tests.test_request_classifier tests.test_plugin_composition_policy tests.test_kh_front_door tests.test_kh_front_door_always_on tests.test_sql_formatting_style_harness`
- `python -B -m unittest tests.test_plugin_composition_policy tests.test_request_classifier tests.test_kh_front_door tests.test_plugin_install_audit`
- `python -B -m unittest tests.test_runtime_memory tests.test_session_skill_audit tests.test_token_optimizer_gate_integration tests.test_command_output_runtime tests.test_workflow_usability_layer tests.test_large_work_orchestration_bundle tests.test_uaf_skill_validator`
- `python -B -m src.skills.uaf_skill_catalog --check`
- `python -B -m src.skills.uaf_skill_quality --summary`
- `python -B -m src.skills.uaf_skill_audit --summary`
- `python -m json.tool .codex-plugin/plugin.json`
- `python -m json.tool plugin.json`
- `git diff --check`

Attention:

- `python -B -m src.orchestration.plugin_install_audit --summary` correctly reports installed cache `2.9.95` behind source `2.9.96`. Upgrade KH UAF in Codex and start a fresh session after this branch is pushed.

## Token Optimizer Status

Status for this repair: gate checked.

- Front-door prompt payloads were small, so status was `considered_not_needed`.
- Long command outputs were not pasted raw into final context; outputs were scoped or summarized.
- Review and test evidence was quality-sensitive, so it was preserved instead of lossy compression.
- Actual provider billing token counts were not available from Codex APIs in this run; KH recorded local payload before/after telemetry and explicit not-used reasons.

## Remaining Risk

- Installed sessions that started before `2.9.96` will still use old cache paths until the marketplace is upgraded and a new session loads the new skill list.
- Subagents can inherit plugin skills, but nested subagent creation may be unavailable in the host. KH must record `nested_subagents_available=false` instead of pretending nested orchestration ran.
- Automatic quality scores are release gates, not proof of real host adoption. Blind session logs remain the highest-value validation.
