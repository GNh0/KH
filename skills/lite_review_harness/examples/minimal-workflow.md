# Lite Review Harness Minimal Workflow Example

## Scenario

A host agent receives a task where this trigger is relevant: Use when a lightweight single-pass code review is needed without full role DAG, multi-gate pipeline, or security/release gates.

The agent must decide whether `lite-review-harness` applies, run or apply it according to its execution level, and leave auditable evidence.

## Expected steps

1. Load `SKILL.md` and confirm the trigger applies (lightweight review needed, no security/release gates).
2. Read `references/usage.md` before doing the work.
3. Collect the changed files or diff to review.
4. Run `evaluate_code_quality_gate` on the changed files.
5. Format findings with `build_review_finding`.
6. Normalize findings with `normalize_review_findings`.
7. Determine if escalation to full review is needed.
8. Return result with findings, files_reviewed, summary, and escalation_recommended.
9. Run `python scripts/smoke_check.py` when validating the packaged skill folder itself.

## Expected evidence

- `skill`: `lite-review-harness`.
- `execution_level`: `python-module`.
- `support_reference_read`: `references/usage.md`.
- `implementation_targets`:
  - `src.orchestration.gate_evaluators.evaluate_code_quality_gate`
  - `src.orchestration.gate_evaluators.build_review_finding`
  - `src.orchestration.gate_evaluators.normalize_review_findings`
  - `src.contracts.WorkflowTaskResult`
  - `src.contracts.WorkflowDispatchResult`
  - `tests.test_gate_evaluators`
- `actual_runtime_path`: the concrete module, workflow, policy gate, or procedural step used in this run.
- `verification`: command output, test result, artifact path, or explicit blocked reason.

## Failure cases

- The agent claims review was performed but did not read any file content.
- The agent reports "passed" without naming what files were examined.
- The agent produces findings without severity or file paths.
- The agent runs full DAG orchestration for a simple review.
- The agent makes release or security decisions from a lite review.

## Done criteria

- All changed files were examined in one review pass.
- Findings are structured with severity, path, reason, and suggestion.
- Summary accurately reflects the review outcome.
- No orchestration state (GoalState, Memory, Snapshot) was created.
- Escalation is recommended if critical issues were found.
