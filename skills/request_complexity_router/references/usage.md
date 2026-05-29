# Request Complexity Router Usage Reference

This reference expands the portable operating contract for `request-complexity-router`. Read it when a task could be over-orchestrated, when a request is ambiguous, when a high-risk domain may require evidence, or when adding new routing rules.

## When to use

Use when deciding whether a user request should be answered directly, handled with a lightweight skill/module, or escalated to GoalState, role DAG, evidence gates, or high-risk review.

Context summary: this skill is an intake router. It should be cheap: no file scan, no network call, no role execution, no automatic GoalState creation. It defines the decision boundary for light, medium, heavy, high-risk, and ambiguous requests so UAF can stay fast for simple work and rigorous for risky work.

Do not use this skill only because it is available. Use it when the host needs an explicit routing decision or when a prompt might otherwise trigger too much machinery.

Keep the router principle-based. Keyword rules are only guardrails for obvious domain, action, and risk signals; they should not become an exhaustive prompt taxonomy.

## Inputs to collect

- User request text and any already-visible artifact or project context.
- Whether the user asks for explanation, summary, comparison, implementation, deliverables, recommendation, or risky action.
- Whether the domain is investment, legal, medical, security, software, product design, operations, or general.
- Whether the request has external impact: money, health, law, credentials, destructive commands, file edits, long-running work, or published deliverables.
- Whether the prompt is ambiguous enough to require a clarification before choosing an execution depth.
- Execution level: `python-module`.
- Implementation targets:
  - `src.orchestration.request_classifier.classify_request`
  - `src.orchestration.request_classifier.RequestClassification`
  - `src.skills.demo_scenarios.run_skill_demo`
  - `tests.test_request_classifier`
  - `tests.test_uaf_skill_catalog`

## Execution pattern

1. Read `SKILL.md` and identify the cheapest plausible route.
2. If a deterministic decision is useful, call `classify_request(text, context=None)`.
3. If the result is `light`, answer directly and avoid role DAG, GoalState, and gates.
4. If the result is `medium`, use only the needed skill, source check, or small Python module; gather narrow evidence such as `source_summary` or `comparison_basis`.
5. If the result is `heavy`, create objective/evidence state and use the relevant domain, quality, review, and QA harnesses.
6. For software implementation or bugfix work, include TDD evidence such as `tdd_red_green` and `test_evidence`; review, QC, and QA are quality gates, not substitutes for TDD.
7. If the result is `high_risk`, require explicit scope, evidence, risk disclosure, scenario analysis, and review gates before presenting a decision.
8. If the result is `ambiguous`, ask for the missing domain or artifact context instead of guessing.
9. Keep `token-optimizer` as cross-cutting infrastructure; only compress when the content is long, log-like, or token-expensive.

## Evidence to produce

- Skill name and execution level used for the run.
- Classification JSON or concise equivalent: `complexity`, `domain`, `recommended_execution`, `required_harnesses`, `evidence_required`, and confidence.
- Trigger reason: conceptual, summary/comparison, implementation/design, high-risk, or ambiguous.
- If escalated, the actual runtime path and required harnesses.
- If not escalated, a note that the request stayed light or medium intentionally.

## Failure handling

- If the classifier returns `ambiguous`, do not continue into a full workflow until the missing context is supplied.
- If a high-risk request was initially treated as medium, reclassify and add missing evidence requirements.
- If a light request triggered heavy orchestration, record an over-orchestration warning and downgrade future handling.
- If a keyword rule causes repeated over-escalation, prefer an intent-order fix over adding more exception keywords.
- If keyword rules conflict with user-provided context, prefer the explicit context and record that override.
- If the classifier cannot import, treat the skill as procedural guidance and do not claim Python-module evidence.

## Quality bar

A valid use of `request-complexity-router` must make UAF cheaper for simple work and stricter for high-impact work. Another agent should be able to answer why the request did or did not trigger GoalState, role DAG, QA, review, or high-risk evidence.
