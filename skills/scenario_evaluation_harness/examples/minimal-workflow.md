# Scenario Evaluation Minimal Workflow

## Scenario

A maintainer has just improved KH UAF request routing and wants to know whether the system still behaves like a practical chatbot assistant. The run should cover simple concept questions, ambiguous follow-ups, investment/legal/medical/security high-risk requests, software implementation, product design, evidence blocking, and resume continuation. The maintainer wants meaningful data, not a broad keyword sweep.

## Expected steps

1. Run `python -m src.orchestration.scenario_evaluator --summary` from the repository root.
2. Run `python -m src.orchestration.scenario_evaluator --summary --stress` when broad coverage matters.
3. Confirm `unexpected_failures` is empty.
4. Confirm the stress summary reports at least 190 scenarios, eight SIDE groups, 25 domains, and more than 360 signals.
5. Confirm the signal categories include `classification`, `evidence`, `gate`, and `resume`.
6. Run `python -m src.orchestration.interactive_side_evaluator --summary --skills` for the interactive SIDE skill transcript checks.
7. Run `python -m src.orchestration.interactive_side_evaluator --summary --skills --stress` before treating transcript coverage as useful stress data.
8. Confirm every packaged KH skill/harness is covered, exact catalog names are used, and `token_usage` reports before/after savings for `token-optimizer`.
9. Confirm the stress transcript summary has at least 70 turns, 14 conversations, a 10-turn conversation, three multi-skill overlap cases, and five token-usage comparison cases.
10. When investigating a change, rerun with `--stress --trace-jsonl scenario_trace.jsonl` and inspect the scenario records.
11. Convert any unexpected failure into a regression scenario or test before editing the classifier or gates.
12. Run the targeted test file after each fix.

The `actual_runtime_path` is `src.orchestration.scenario_evaluator` for deterministic routing scenarios and `src.orchestration.interactive_side_evaluator` for KH-assistant SIDE transcript checks.

## Expected evidence

- JSON summary with total, passed, failed, domain count, SIDE count, and meaningful signal count.
- Scenario trace JSONL when a regression is being debugged.
- A finding category for each unexpected mismatch.
- Gate status evidence for scenarios that intentionally check complete or blocked GoalState behavior.
- Resume signal evidence for scenarios that require `resume_handoff`.
- Interactive SIDE report with catalog, assistant-policy, evidence, and token-usage signals.

## Failure cases

- A concept question such as "What is an API?" escalates to role DAG.
- A context-free follow-up such as "Can you review it?" gets answered directly instead of asking for clarification.
- A high-risk bypass or destructive request is routed as product design or ordinary help.
- A heavy software request does not require TDD/test evidence.
- A resume scenario does not require `resume_handoff`.
- The harness marks an expected missing-evidence block as a failed scenario instead of a passing blocked decision.
- A SIDE transcript uses an invented skill name instead of an exact packaged KH skill.
- `token-optimizer` is claimed without before/after token usage statistics.

## Done criteria

- The scenario matrix runs without unexpected failures.
- The stress matrix has at least 190 scenarios and meaningful signals cover classification, evidence, gate, and resume.
- The interactive SIDE smoke covers every packaged KH skill/harness and includes token usage savings where optimization applies.
- The interactive SIDE stress run has varied conversation lengths, multi-skill overlap cases, route/execution-level statistics, and token usage comparisons.
- New useful failures are preserved as regression tests.
- The final report is short enough to compare across releases and concrete enough to drive the next improvement.

## Runtime binding

- execution_level: python-module
- implementation_targets:
  - `src.orchestration.scenario_evaluator.evaluate_scenarios`
  - `src.orchestration.scenario_evaluator.build_scenario_report`
  - `src.orchestration.interactive_side_evaluator.evaluate_skill_side_turns`
- actual_runtime_path: `src.orchestration.scenario_evaluator.evaluate_scenarios`
- verification evidence: run `scripts/smoke_check.py`, `scripts/demo.py --output-dir <tmp>`, `python -m src.orchestration.scenario_evaluator --summary --stress`, and `python -m src.orchestration.interactive_side_evaluator --summary --skills --stress`.
