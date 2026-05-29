---
name: scenario-evaluation-harness
description: Use when validating KH UAF against repeated SIDE-style human usage scenarios for request routing, evidence collection, gate decisions, and resume handoff behavior.
---
# Scenario Evaluation Harness

This skill runs a deterministic scenario matrix that behaves like small SIDE groups: human-style users, domain experts, evidence/gate reviewers, and resume reviewers. It converts repeated chatbot usage patterns into traceable regression data instead of relying on one-off manual impressions.

Source label: Scenario evaluation harness.

## Support files

- Read `references/usage.md` before adding scenario categories, changing signal thresholds, or interpreting report output.
- Use `examples/minimal-workflow.md` as the compact acceptance scenario for classification, evidence, gate, and resume signals.
- Run `python scripts/smoke_check.py` from this skill folder to verify support files and implementation targets.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable scenario evaluation mini-demo.

## Instructions

1. Start with `src.orchestration.scenario_evaluator.default_scenarios()` so every run covers the same baseline matrix.
2. Treat each scenario as a simulated SIDE observation, not as an external LLM conversation.
3. Classify the prompt with `classify_request`, compare expected complexity, domain, execution depth, evidence, and required harnesses.
4. For scenarios with gate expectations, feed required evidence through `evaluate_goal_evidence` and record complete or blocked status.
5. For resume scenarios, require `resume_handoff` evidence when context says the next session must continue without prior chat.
6. Write `scenario_trace.jsonl` when investigating a regression so each scenario has a durable record.
7. Convert unexpected failures into tests before changing classifier, evidence, gate, or resume code.
8. Keep the matrix broad and small enough to run quickly. Prefer high-signal prompts over large keyword dictionaries.

## External Benchmark Recipe

Use this skill as a Superpowers-style repeated evaluation loop:

1. Run the baseline matrix with `python -m src.orchestration.scenario_evaluator --summary`.
2. Confirm the summary has at least four SIDE groups, seven domains, and classification/evidence/gate/resume signal categories.
3. If `unexpected_failures` is non-empty, inspect the trace before modifying routing or gate code.
4. Add one regression scenario for each real user pattern that produced a useful failure.
5. Keep expected blocked cases as passing data when the system blocks for the correct evidence reason.

Pressure scenario: a user asks a context-dependent follow-up such as "Do the same thing for the other file" after context compression. The harness must classify it as ambiguous without active artifact context, and a resume scenario must require `resume_handoff` evidence before claiming continuity is safe.

## Required outputs

- A summary containing total scenarios, pass/fail counts, SIDE count, domain count, and signal categories.
- JSONL trace records with `scenario_id`, expected values, actual classification, findings, and signals.
- Stable failure categories for classification, evidence, gate, and resume issues.
- Regression tests for any unexpected failure that is fixed.

## Common mistakes

- Do not treat expected blocked evidence scenarios as failed tests.
- Do not inflate the matrix with hundreds of near-duplicate keywords.
- Do not let a passing classifier hide missing gate or resume evidence.
- Do not claim real LLM quality from this harness; it validates deterministic UAF contracts and routing boundaries.

## UAF implementation targets

- `src.orchestration.scenario_evaluator.default_scenarios`
- `src.orchestration.scenario_evaluator.evaluate_scenarios`
- `src.orchestration.scenario_evaluator.build_scenario_report`
- `src.skills.demo_scenarios.run_skill_demo`
- `tests.test_scenario_evaluator`
- `tests.test_uaf_skill_catalog`
