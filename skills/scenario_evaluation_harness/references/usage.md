# Scenario Evaluation Harness Usage

## When to use

Use `scenario-evaluation-harness` when KH UAF needs evidence that its skills and harnesses behave well across repeated, realistic chatbot usage patterns. The harness is useful after classifier changes, evidence producer changes, gate evaluator changes, resume/handoff changes, or new domain orchestration work. It is also useful when a review asks whether simple requests are staying light while important work still escalates to GoalState, role DAG, and evidence gates.

Do not use it as a replacement for end-to-end host adapter testing. It is a deterministic contract harness. It catches routing, evidence, gate, and resume regressions before heavier Codex, Antigravity-style, browser, or LLM-backed runs are worth the cost.

## Inputs to collect

Collect the user pattern, expected complexity, expected domain, expected execution depth, required evidence, required harnesses, and whether a gate or resume decision should be evaluated. For a real regression, also collect the prior actual result, why it was wrong, and the smallest prompt that reproduces it. When the scenario depends on state, provide explicit context such as `domain`, `has_active_artifact`, or `requires_resume`; do not rely on hidden chat history.

The default matrix contains four SIDE groups:

- `human-user`: ambiguous follow-ups, short concept questions, common summaries, and everyday rewrites.
- `domain-expert`: software, investment, product design, security, legal, and medical boundary cases.
- `evidence-gate`: source, token, PR audit, and blocked-evidence cases.
- `resume`: scenarios that should survive context compression and fresh-session continuation.

The stress matrix adds repeated multi-turn probes for data/file workflows, creative and marketing, travel/local/current data, Korean life-admin, education/language/document work, health/fitness/cooking/lifestyle, career/workplace, civic/government forms, DevOps/cloud/security, and everyday social/safety prompts.

The interactive SIDE matrix is separate. It models KH-assistant turns and checks that every packaged skill/harness appears in a multi-turn transcript with:

- exact `selected_skill` from the packaged catalog
- expected route, such as `skill_call`, `workflow_harness`, or `procedure_policy`
- evidence keys that prove why the skill/harness applied
- assistant-policy markers showing the response was not just generic advice
- token usage statistics when `token-optimizer` is selected

## Execution pattern

Run the aggregate summary:

```bash
python -m src.orchestration.scenario_evaluator --summary
```

Run the broader stress corpus:

```bash
python -m src.orchestration.scenario_evaluator --summary --stress
```

Write a durable trace and Markdown report:

```bash
python -m src.orchestration.scenario_evaluator --summary --stress --trace-jsonl scenario_trace.jsonl --report-md scenario_report.md
```

Run all packaged KH skill/harness SIDE transcript checks:

```bash
python -m src.orchestration.interactive_side_evaluator --summary --skills
```

Run broader live-style SIDE transcript stress checks:

```bash
python -m src.orchestration.interactive_side_evaluator --summary --skills --stress
```

For each scenario, the harness classifies the prompt with `src.orchestration.request_classifier.classify_request`, checks expected fields, optionally evaluates goal evidence through `src.orchestration.goal_evidence.evaluate_goal_evidence`, and emits signals. A scenario passes when the actual behavior matches the expected route and any expected blocked gate blocks for the correct missing evidence.

For all-skill SIDE transcript checks, run `src.orchestration.interactive_side_evaluator.default_skill_side_turns()` through `evaluate_skill_side_turns()` and `build_skill_side_report()`. A transcript fails if a SIDE assistant invents a skill name, omits the evidence trace, uses the wrong execution level, or cannot show token savings for token optimization.

Use `stress_skill_side_turns()` when evaluating whether the transcript fixture has enough shape to be useful. Its summary includes conversation length, route counts, execution-level counts, multi-skill turn count, selected skill counts, and aggregate token usage. Do not describe this as statistically meaningful user telemetry; it is deterministic regression data.

## Evidence to produce

Preserve these evidence items when using this skill in a real review:

- command used to run the harness
- JSON summary with scenario counts, pass/fail counts, domain count, SIDE count, and signal categories
- `scenario_trace.jsonl` when investigating regressions
- list of unexpected failures and their categories
- follow-up code/test/docs changes made from those failures
- final verification command after fixes
- interactive SIDE report summary when validating all packaged skills/harnesses
- token usage before/after statistics for `token-optimizer`

The most useful deterministic signal categories are `classification`, `evidence`, `gate`, and `resume`. Interactive SIDE reports add `catalog`, `assistant_policy`, and `token_usage`.

## Failure handling

If `unexpected_failures` is non-empty, do not tune the expected values to make the run green unless the expectation was genuinely wrong. First decide whether the failure is an under-escalation, over-escalation, domain error, missing evidence, gate mismatch, or resume gap. Fix the smallest responsible component and keep the scenario as a regression test.

If the matrix grows too large or slow, remove duplicate prompts rather than weakening the assertions. The harness should stay lightweight enough to run before heavier integration checks.

## Quality bar

A useful baseline run covers at least four SIDE groups, seven domains, and all four signal categories. A useful stress run covers at least 190 scenarios, at least eight SIDE groups, at least 25 domains, and more than 360 meaningful signals. A useful interactive SIDE smoke covers every packaged skill/harness, has no invented skill names, and reports token usage savings where optimization is expected. A useful interactive SIDE stress run covers at least 70 turns, 14 conversations, a 10-turn conversation, three multi-skill overlap cases, and five token-usage comparison cases. A release-quality run has no unexpected failures, a durable trace for investigations, and tests that lock in any newly fixed boundary.
