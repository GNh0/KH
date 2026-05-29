# Scenario Evaluation Minimal Workflow

## Scenario

A maintainer has just improved KH UAF request routing and wants to know whether the system still behaves like a practical chatbot assistant. The run should cover simple concept questions, ambiguous follow-ups, investment/legal/medical/security high-risk requests, software implementation, product design, evidence blocking, and resume continuation. The maintainer wants meaningful data, not a broad keyword sweep.

## Expected steps

1. Run `python -m src.orchestration.scenario_evaluator --summary` from the repository root.
2. Confirm `unexpected_failures` is empty.
3. Confirm the summary reports at least four SIDE groups and seven domains.
4. Confirm the signal categories include `classification`, `evidence`, `gate`, and `resume`.
5. When investigating a change, rerun with `--trace-jsonl scenario_trace.jsonl` and inspect the scenario records.
6. Convert any unexpected failure into a regression scenario or test before editing the classifier or gates.
7. Run the targeted test file after each fix.

The `actual_runtime_path` is `src.orchestration.scenario_evaluator`, with `src.orchestration.request_classifier` and `src.orchestration.goal_evidence` as the main runtime dependencies.

## Expected evidence

- JSON summary with total, passed, failed, domain count, SIDE count, and meaningful signal count.
- Scenario trace JSONL when a regression is being debugged.
- A finding category for each unexpected mismatch.
- Gate status evidence for scenarios that intentionally check complete or blocked GoalState behavior.
- Resume signal evidence for scenarios that require `resume_handoff`.

## Failure cases

- A concept question such as "What is an API?" escalates to role DAG.
- A context-free follow-up such as "Can you review it?" gets answered directly instead of asking for clarification.
- A high-risk bypass or destructive request is routed as product design or ordinary help.
- A heavy software request does not require TDD/test evidence.
- A resume scenario does not require `resume_handoff`.
- The harness marks an expected missing-evidence block as a failed scenario instead of a passing blocked decision.

## Done criteria

- The scenario matrix runs without unexpected failures.
- Meaningful signals cover classification, evidence, gate, and resume.
- New useful failures are preserved as regression tests.
- The final report is short enough to compare across releases and concrete enough to drive the next improvement.
