---
name: lite-review-harness
description: "Use when a lightweight single-pass code review is needed without full role DAG, multi-gate pipeline, or security/release gates."
---

# Lite Review Harness

This is a lightweight UAF review harness that runs a single reviewer pass on changed code. It replaces the full review-gate-harness when only basic code quality feedback is needed without multi-role DAG, security gates, or release gates.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## When to use

- Quick code review of a small change (1-5 files)
- Post-fix review after applying a bugfix
- Reviewing a single PR or diff for basic quality
- When the user explicitly asks for a "quick review" or "light review"
- When full security/release gates are not required

## When NOT to use

- Changes touching security-sensitive code (use full review-gate-harness)
- Pre-release reviews requiring compliance sign-off
- Multi-subsystem changes requiring architecture review
- When the user explicitly requests security review or release gates

## Workflow

1. Receive the diff or list of changed files.
2. Run a single code-quality review pass (no spec-compliance or security passes).
3. Produce findings with severity, file path, and suggested fix.
4. Return review summary without gate blocking or release decisions.
5. If findings are critical, recommend escalating to full review-gate-harness.

## Required outputs

- `status`: `passed` (no critical findings), `findings` (has actionable items), or `blocked`.
- `findings`: list of review findings, each with severity, file, line (when available), reason, and suggestion.
- `files_reviewed`: list of files that were examined.
- `summary`: one-paragraph review assessment.
- `escalation_recommended`: boolean if critical issues suggest full review.

## Common mistakes

- Do not run full DAG orchestration for a lightweight review.
- Do not skip all findings and report "passed" without examining the code.
- Do not produce vague findings without file paths or actionable suggestions.
- Do not block release decisions from a lite review; that requires the full review-gate-harness.
- Do not review files that are not part of the change set.

## UAF implementation targets

- `src.orchestration.gate_evaluators.evaluate_code_quality_gate`
- `src.orchestration.gate_evaluators.build_review_finding`
- `src.orchestration.gate_evaluators.normalize_review_findings`
- `src.contracts.WorkflowTaskResult`
- `src.contracts.WorkflowDispatchResult`
- `tests.test_gate_evaluators`
