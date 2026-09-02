---
name: request-complexity-router
description: Use when the user explicitly requests an execution-depth or complexity audit, or a governed workflow has genuine unresolved ambiguity or risk. Do not invoke for an ordinary clear request.
---
# Request Complexity Router

## KH Entry Contract

- Select this skill only for an explicit complexity audit or a genuine unresolved execution-depth decision inside governed work.
- Do not select it merely because KH is active, a tool or file is needed, or another domain skill clearly matches.
- A governed workflow may call it when the lightest safe execution depth is materially uncertain.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This skill is a governed complexity-analysis module, not a prerequisite for ordinary requests.

Source label: Request complexity routing.

## Support files

- Read `references/usage.md` when adding routing rules, reviewing borderline cases, or deciding whether a task should escalate.
- Use `examples/minimal-workflow.md` as the compact acceptance scenario for light, medium, heavy, high-risk, and ambiguous requests.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable routing mini-demo.

## Instructions

1. Classify first, then execute only the lightest sufficient path.
2. Treat the classifier as advisory routing, not as a substitute for judgment.
3. Use `direct_answer` for clear concept questions.
4. Use `skill_read` or a narrow Python module for bounded summaries, comparisons, and analysis.
5. Escalate to GoalState, role DAG, and review/QA gates for implementation, deliverables, persistent state, or high-impact decisions.
6. For ambiguous prompts, ask a short clarification instead of starting a full workflow.
7. Select `token-optimizer` only when a large reducible payload or explicit telemetry request crosses its own trigger; ordinary and contract-sensitive work does not need a no-op token record.
8. Workspace strategy is a cross-cutting output for implementation routes. Prefer `host-worktree`, `project-local-worktree`, or `isolated-branch` for Git-backed implementation unless the task is documentation-only, a single-file small patch, or explicitly in-place.
9. Heavy implementation routes should include `goal-state-harness` so completion criteria, evidence requirements, and blocked states survive context compaction.
10. For heavy implementation routes or threshold-crossing contexts, final status must include `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked`. Do not make a light request heavy just because this gate is considered.
11. For large project, SaaS, app, multi-file implementation, role-DAG, or long-running work, require `large_work_orchestration_bundle` evidence with `skill_statuses`.
12. `large_work_orchestration_bundle.skill_statuses` must cover `request-complexity-router`, `host-agent-orchestration`, `goal-state-harness`, `development-lifecycle-harness`, `token-optimizer`, `memory-state-harness`, `parallel-orchestration-harness`, `subagent-review-pipeline`, `role-execution-audit-harness`, `compound-engineering-harness`, and `workflow-skill-distiller` as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`.
13. Bundle entries must include `application_mode`: `runtime`, `procedural`, `considered`, or `blocked`. The router should not imply runtime execution unless runtime evidence exists.
14. For large-work progress and final reports, require `skill_transition_handoff` evidence so bundle members that became necessary are not left as passive listed skills.
15. Do not create a large-work bundle for light or medium requests; keep them cheap unless context budget thresholds require only token optimization evidence.
16. Do not grow this into a large keyword dictionary. Prefer intent order: conceptual questions stay light, concrete build/review/design work becomes heavy, and destructive or regulated advice overrides to high-risk.
17. Do not choose a development stack, file template, static web shape, document format, drawing format, or generated artifact layout until the user objective, operating context, output type, and any required brainstorming/design approval are known.

## External Benchmark Recipe

Use this skill as a Superpowers-style intake rule:

1. Start with the cheapest route that could satisfy the user.
2. Escalate only on concrete triggers: implementation, persisted deliverables, external commands, long-running state, money, law, health, credentials, security, destructive operations, or explicit review/QA needs.
3. Keep ambiguous prompts in clarification mode until the domain or target artifact is known.
4. Keep token optimization as cross-cutting infrastructure, not as a full workflow.
5. For large work, require the large-work bundle so host, goal, lifecycle, token, memory, parallel, subagent, audit, compound, and distiller decisions are visible.
6. Record the routing reason so later review can spot over-orchestration or under-escalation.

Pressure scenario: a user asks "Is Samsung okay?" without context. The host must not guess investment, phone purchase, hiring, or brand reputation and must not start a role DAG. It should ask a short clarification, then reclassify when the domain is known.

## Required outputs

- A classification with `complexity`, `domain`, `recommended_execution`, and confidence.
- Any required harnesses and evidence keys when the task escalates.
- For implementation routes, a `workspace_strategy` recommendation: `current-checkout`, `project-local-worktree`, `host-worktree`, or `isolated-branch`.
- For heavy implementation routes, include `goal-state-harness` in `required_harnesses`.
- For threshold-crossing contexts, include `token_optimization` in `evidence_required` and report `token_optimizer_status` without changing the request depth by itself.
- For large work, include `large_work_orchestration_bundle`, `skill_statuses`, `parallel_strategy_decision`, `memory_candidates`, `compound_handoff`, and `skill_transition_handoff` in `evidence_required`.
- A minimal evidence template for bundle status: `skill`, `status`, `application_mode`, `evidence_note`, `evidence_keys`, and optional `blocked_reason`; do not require AdapterRequest, role results, or wave metadata unless runtime execution is claimed.
- A clarification path when context is insufficient.
- A short reason for the chosen depth.

## Common mistakes

- Do not run role DAGs for definitions, simple explanations, or short conceptual questions.
- Do not answer high-risk investment, legal, medical, security, or destructive requests as if they were ordinary summaries.
- Do not encode every possible weird prompt. Use `ambiguous -> clarify` when confidence is low.
- Do not treat `token-optimizer` as a heavy workflow; it is a cross-cutting utility.

## UAF implementation targets

- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.request_classifier.RequestClassification`
- `src.skills.demo_scenarios.run_skill_demo`
- `tests.test_request_classifier`
- `tests.test_uaf_skill_catalog`
