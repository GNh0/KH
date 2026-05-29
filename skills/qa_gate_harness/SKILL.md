---
name: qa-gate-harness
description: Use when a UAF workflow needs QA checks, regression evidence, manual test mapping, or browser/app verification results.
---

# QA Gate Harness

This is a UAF-native QA harness for regression and verification workflow patterns. It describes portable QA gates without requiring bundled browser tooling.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Pattern basis

- QA workflow: lead review, reproduce-fix-verify loops, regression test creation, and report-only QA mode.
- UAF: sandbox evaluator, workflow gate results, and future platform adapters.

## Workflow

1. Map each user requirement and acceptance criterion to a QA check.
2. Prefer automated checks when a deterministic test can prove the behavior.
3. Record manual checks explicitly with `src.orchestration.gate_evaluators.build_qa_check` when automation is not available.
4. For each bug, capture reproduction steps, expected behavior, actual behavior, and severity.
5. Call `src.orchestration.gate_evaluators.evaluate_qa_checks` to aggregate passed, failed, and blocked checks.
6. Treat an empty QA check list as blocked; the role-DAG path must pass explicit check records or a scoped `QA-SKIP` record with scope, notes, and evidence before `qa-verifier` can pass.
7. Require fresh verification evidence after a fix or rollback.
8. Support report-only mode where findings are returned without modifying files.

## External Benchmark Recipe

Use this harness as an acceptance-check map:

1. Convert every acceptance criterion into one QA check with owner, scope, and evidence source.
2. For automated checks, record command, exit code, and relevant output.
3. For manual checks, record steps, observed result, expected result, and reviewer.
4. Use scoped `QA-SKIP` only when QA is not applicable; include scope, notes, and evidence.
5. Fail the gate when a required check is missing, failed, blocked, or unsupported by evidence.

Pressure scenario: if browser QA was expected but no browser/app adapter ran, the QA result is blocked, not passed.

## Required outputs

- `status`: `passed`, `failed`, or `blocked`.
- `checks`: requirement-to-evidence mapping.
- `bugs`: structured reproduction reports.
- `regression_tests`: tests added or recommended.

## Common mistakes

- Do not count planned QA as completed QA.
- Do not emit passed evidence when the browser/QA adapter is missing or failed.
- Do not treat a smoke test as full regression coverage unless the workflow explicitly scopes it that way.
- Do not omit manual verification notes when no deterministic test can cover the risk.

## UAF implementation targets

- `src.harness.evaluator`
- `src.harness.sandbox`
- `src.orchestration.gate_evaluators.build_qa_check`
- `src.orchestration.gate_evaluators.evaluate_qa_checks`
- `src.orchestration.role_orchestrator.GateRoleRunner`
- `src.orchestration.roles`
- `src.contracts.WorkflowDispatchResult`
- `tests.test_gate_evaluators`
