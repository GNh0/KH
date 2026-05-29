# Request Complexity Router Minimal Workflow Example

## Scenario

A host agent receives a task where this trigger is relevant: Use when deciding whether a user request should be answered directly, handled with a lightweight skill/module, or escalated to GoalState, role DAG, evidence gates, or high-risk review.

The agent must classify the request before choosing a UAF runtime depth. The goal is not to make every prompt expensive; the goal is to avoid both over-orchestration and unsafe under-escalation.

## Expected steps

1. Load `SKILL.md` and confirm that routing is needed.
2. Read `references/usage.md` when the request is borderline, ambiguous, or high-risk.
3. Call `src.orchestration.request_classifier.classify_request` for deterministic routing evidence, or apply the same policy procedurally when code execution is unavailable.
4. For `light`, answer directly and do not start GoalState, role DAG, review, or QA gates.
5. For `medium`, use the narrowest useful skill/module and collect source or comparison evidence only when the answer depends on it.
6. For `heavy`, create objective/evidence state and use role/gate harnesses that match the work.
7. For software implementation, require TDD evidence such as `tdd_red_green` and `test_evidence`; review/QC/QA gates do not replace TDD.
8. For `high_risk`, require scope, evidence, risk disclosure, scenario analysis, and review before making a recommendation.
9. For `ambiguous`, ask a short clarification instead of guessing.

## Expected evidence

- `skill`: `request-complexity-router`.
- `execution_level`: `python-module`.
- `support_reference_read`: `references/usage.md` when the request is not obviously light.
- `classification`: `complexity`, `domain`, `recommended_execution`, `required_harnesses`, `evidence_required`, and confidence.
- `actual_runtime_path`: direct answer, skill read, Python module call, hybrid harness, role DAG, or clarification.
- `verification`: classifier test, smoke check, demo output, or explicit blocked reason.

## Failure cases

- The agent sends a concept question through role DAG and release gates.
- The agent treats stock recommendations, legal advice, medical diagnosis, credentials, or destructive commands as ordinary medium summaries.
- The agent guesses the meaning of "이거 어때?" or "삼성 괜찮아?" without context.
- The agent claims `token-optimizer` ran as a heavy workflow instead of a cross-cutting utility.
- The agent omits `actual_runtime_path`, making it impossible to audit whether the route was light or heavy.

## Done criteria

- Light, medium, heavy, high-risk, and ambiguous examples classify differently.
- Ambiguous prompts produce clarification instead of blind escalation.
- High-risk prompts include evidence and risk requirements.
- The selected runtime depth is the lightest route that can satisfy the request safely.
- No user-facing deliverables or hidden state are created by classification alone.
