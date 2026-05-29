# Scenario Evaluation Harness Usage

## When to use

Use `scenario-evaluation-harness` when KH UAF needs evidence that its skills and harnesses behave well across repeated, realistic chatbot usage patterns. The harness is useful after classifier changes, evidence producer changes, gate evaluator changes, resume/handoff changes, or new domain orchestration work. It is also useful when a review asks whether simple requests are staying light while important work still escalates to GoalState, role DAG, and evidence gates.

Do not use it as a replacement for end-to-end host adapter testing. It is a deterministic contract harness. It catches routing, evidence, gate, and resume regressions before heavier Codex, Antigravity-style, browser, or LLM-backed runs are worth the cost.

## Inputs to collect

Collect the user pattern, expected complexity, expected domain, expected execution depth, required evidence, required harnesses, and whether a gate or resume decision should be evaluated. For a real regression, also collect the prior actual result, why it was wrong, and the smallest prompt that reproduces it. When the scenario depends on state, provide explicit context such as `domain`, `has_active_artifact`, or `requires_resume`; do not rely on hidden chat history.

The default matrix already contains four SIDE groups:

- `human-user`: ambiguous follow-ups, short concept questions, common summaries, and everyday rewrites.
- `domain-expert`: software, investment, product design, security, legal, and medical boundary cases.
- `evidence-gate`: source, token, PR audit, and blocked-evidence cases.
- `resume`: scenarios that should survive context compression and fresh-session continuation.

## Execution pattern

Run the aggregate summary:

```bash
python -m src.orchestration.scenario_evaluator --summary
```

Write a durable trace and Markdown report:

```bash
python -m src.orchestration.scenario_evaluator --summary --trace-jsonl scenario_trace.jsonl --report-md scenario_report.md
```

For each scenario, the harness classifies the prompt with `src.orchestration.request_classifier.classify_request`, checks expected fields, optionally evaluates goal evidence through `src.orchestration.goal_evidence.evaluate_goal_evidence`, and emits signals. A scenario passes when the actual behavior matches the expected route and any expected blocked gate blocks for the correct missing evidence.

## Evidence to produce

Preserve these evidence items when using this skill in a real review:

- command used to run the harness
- JSON summary with scenario counts, pass/fail counts, domain count, SIDE count, and signal categories
- `scenario_trace.jsonl` when investigating regressions
- list of unexpected failures and their categories
- follow-up code/test/docs changes made from those failures
- final verification command after fixes

The most useful signal categories are `classification`, `evidence`, `gate`, and `resume`. They are intentionally stable so reports can be compared across runs.

## Failure handling

If `unexpected_failures` is non-empty, do not tune the expected values to make the run green unless the expectation was genuinely wrong. First decide whether the failure is an under-escalation, over-escalation, domain error, missing evidence, gate mismatch, or resume gap. Fix the smallest responsible component and keep the scenario as a regression test.

If the matrix grows too large or slow, remove duplicate prompts rather than weakening the assertions. The harness should stay lightweight enough to run before heavier integration checks.

## Quality bar

A useful run covers at least four SIDE groups, seven domains, and all four signal categories. It should produce enough meaningful signals to show where routing, evidence, gate, and resume behavior are being exercised. A release-quality run has no unexpected failures, a durable trace for investigations, and tests that lock in any newly fixed boundary.
