# Large Work Orchestration Bundle Audit

Date: 2026-05-30
Trigger session: `019e7484-627b-7f81-9b10-ba2f58b6e53b`

## Why

A real SaaS planning and implementation session showed that KH could expose many relevant skills while still letting an agent apply them as isolated checklists. The agent used development, quality, and QA flow, but it did not use `token-optimizer` early, did not record memory candidate decisions, did not explicitly evaluate parallel orchestration, and did not produce a compound or distillation handoff until challenged.

The problem was not a missing individual skill. The missing piece was a large-work decision bundle that forces relevant harnesses to be applied or explicitly accounted for without making simple prompts heavy.

## Contract

For large project, SaaS, app, multi-file implementation, role-DAG, or long-running work, KH now requires `large_work_orchestration_bundle` evidence before implementation.

The bundle contains `skill_statuses` for:

- `request-complexity-router`
- `host-agent-orchestration`
- `goal-state-harness`
- `development-lifecycle-harness`
- `token-optimizer`
- `memory-state-harness`
- `parallel-orchestration-harness`
- `subagent-review-pipeline`
- `role-execution-audit-harness`
- `compound-engineering-harness`
- `workflow-skill-distiller`

Allowed status values:

- `applied`
- `considered_not_needed`
- `skipped_with_rationale`
- `blocked`

This is an accounting contract, not a command to run every harness heavily. For example, `parallel-orchestration-harness` can be `considered_not_needed` for sequential dependent work, and `workflow-skill-distiller` can be `considered_not_needed` when no repeated workflow or reusable lesson exists.

## Evidence Keys

Large work should carry these evidence keys:

- `large_work_orchestration_bundle`
- `skill_statuses`
- `workspace_strategy`
- `parallel_strategy_decision`
- `token_optimizer_status`
- `memory_candidates`
- `compound_handoff`

## Regression Coverage

Added `tests/test_large_work_orchestration_bundle.py` to verify:

- Codex plugin prompt requires bundle status reporting.
- `development-lifecycle-harness` and `request-complexity-router` document the bundle.
- Heavy SaaS/app implementation routes include bundle skills, required harnesses, and evidence.
- Light conceptual questions do not become heavy merely because the bundle exists.
- Bundle member skills cross-reference `large_work_orchestration_bundle` and `skill_statuses`.

## Expected Behavior

For a prompt such as "Build a SaaS CRM MVP with auth, dashboard, API, tests, and i18n", KH should classify it as heavy role-DAG work, create GoalState, choose an isolated workspace, apply token optimization as a context gate, decide whether memory candidates are needed, decide whether parallel/subagent work is appropriate, and leave compound/distillation handoff evidence at the end.

For a prompt such as "What is PER?", KH should stay light and answer directly. Token optimization can still be considered when context thresholds are crossed, but the large-work bundle should not be created for the conceptual question itself.
