---
name: request-complexity-router
description: Use when deciding whether a user request should be answered directly, handled with a lightweight skill/module, or escalated to GoalState, role DAG, evidence gates, or high-risk review.
---
# Request Complexity Router

This skill is the lightweight intake gate for UAF. It prevents over-orchestration by classifying the request before running heavier skills, harnesses, roles, or gates.

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
7. Keep `token-optimizer` available as cross-cutting infrastructure, but only apply compression when content is large, log-like, or expected to exceed the context budget. If `estimated_context_tokens`, broad file reads, expected tool calls, or subagent transcripts cross the threshold, the token gate must be applied even when the user-facing question sounds simple.
8. Workspace strategy is a cross-cutting output for implementation routes. Prefer `host-worktree`, `project-local-worktree`, or `isolated-branch` for Git-backed implementation unless the task is documentation-only, a single-file small patch, or explicitly in-place.
9. Heavy implementation routes should include `goal-state-harness` so completion criteria, evidence requirements, and blocked states survive context compaction.
10. For heavy implementation routes or threshold-crossing contexts, final status must include `token_optimizer_status`: `used`, `considered_not_needed`, `passthrough`, or `blocked`. Do not make a light request heavy just because this gate is considered.
11. Do not grow this into a large keyword dictionary. Prefer intent order: conceptual questions stay light, concrete build/review/design work becomes heavy, and destructive or regulated advice overrides to high-risk.

## External Benchmark Recipe

Use this skill as a Superpowers-style intake rule:

1. Start with the cheapest route that could satisfy the user.
2. Escalate only on concrete triggers: implementation, persisted deliverables, external commands, long-running state, money, law, health, credentials, security, destructive operations, or explicit review/QA needs.
3. Keep ambiguous prompts in clarification mode until the domain or target artifact is known.
4. Keep token optimization as cross-cutting infrastructure, not as a full workflow.
5. Record the routing reason so later review can spot over-orchestration or under-escalation.

Pressure scenario: a user asks "삼성 괜찮아?" without context. The host must not guess investment, phone purchase, hiring, or brand reputation and must not start a role DAG. It should ask a short clarification, then reclassify when the domain is known.

## Required outputs

- A classification with `complexity`, `domain`, `recommended_execution`, and confidence.
- Any required harnesses and evidence keys when the task escalates.
- For implementation routes, a `workspace_strategy` recommendation: `current-checkout`, `project-local-worktree`, `host-worktree`, or `isolated-branch`.
- For heavy implementation routes, include `goal-state-harness` in `required_harnesses`.
- For threshold-crossing contexts, include `token_optimization` in `evidence_required` and report `token_optimizer_status` without changing the request depth by itself.
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
