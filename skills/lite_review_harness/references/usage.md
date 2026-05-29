# Lite Review Harness Usage Reference

This reference expands the portable operating contract for `lite-review-harness`. Read it when the task is real work, when deciding whether this skill applies, or when a review needs evidence beyond the concise `SKILL.md`.

## When to use

Use when a lightweight single-pass code review is needed without full role DAG, multi-gate pipeline, or security/release gates.

Context summary: This harness provides fast code quality feedback with minimal overhead. It runs one reviewer pass, produces structured findings, and does not make release or security decisions.

Do not use this skill only because it is available. Use it when the current task needs the behavior named by the trigger, and state whether the skill was actually executed, applied procedurally, or only considered.

Quality rule: review findings must be specific, actionable, and tied to actual code locations. Generic "looks good" responses are not acceptable without naming what was examined.

## Inputs to collect

- Changed files: diff, file list, or PR reference.
- Review focus: what to look for (bugs, style, performance, correctness).
- Context: what the change is supposed to accomplish.
- Execution level: `python-module`.
- Implementation targets:
  - `src.orchestration.gate_evaluators.evaluate_code_quality_gate`
  - `src.orchestration.gate_evaluators.build_review_finding`
  - `src.orchestration.gate_evaluators.normalize_review_findings`
  - `src.contracts.WorkflowTaskResult`
  - `src.contracts.WorkflowDispatchResult`
  - `tests.test_gate_evaluators`

## Execution pattern

1. Read `SKILL.md` first and confirm the trigger applies to the current task.
2. Read this reference before performing non-trivial work with `lite-review-harness`.
3. Collect the changed files and review context.
4. Run `evaluate_code_quality_gate` on the changed files.
5. Format findings using `build_review_finding` and `normalize_review_findings`.
6. Assess whether any findings are critical enough to recommend full review escalation.
7. Return result with findings, files reviewed, and summary.

## Evidence to produce

- `skill`: `lite-review-harness`.
- `execution_level`: `python-module`.
- `files_reviewed`: list of examined files.
- `finding_count`: total number of findings.
- `critical_count`: number of critical/high-severity findings.
- `escalation_recommended`: boolean.
- `review_duration_ms`: time taken for the review pass.

## Failure handling

- If no files are provided for review, return `status: blocked` requesting the diff or file list.
- If file content cannot be read (permissions, missing files), return `status: blocked` with the error.
- If the review identifies potential security issues, recommend escalation to full review-gate-harness.
- Never report "passed" without having examined at least one file's content.

## Quality bar

- Every finding must include: severity (low/medium/high/critical), file path, line number when available, reason, and suggested fix.
- "No findings" result must name the files that were examined and state what was checked.
- Review must cover correctness, not just style.
- Critical findings must trigger an escalation recommendation.
- Review should complete in under 5 seconds for typical small changes (1-5 files).
