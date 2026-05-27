---
name: qa-gate-harness
description: Use when a UAF workflow needs QA checks, regression evidence, manual test mapping, or browser/app verification results.
---

# QA Gate Harness

This is a UAF-native QA harness derived from gstack QA workflow patterns. It describes portable QA gates without requiring gstack browser tooling.

## Reference basis

- gstack: QA lead workflow, reproduce-fix-verify loops, regression test creation, and report-only QA mode.
- UAF: sandbox evaluator, workflow gate results, and future platform adapters.

## Workflow

1. Map each user requirement and acceptance criterion to a QA check.
2. Prefer automated checks when a deterministic test can prove the behavior.
3. Record manual checks explicitly when automation is not available.
4. For each bug, capture reproduction steps, expected behavior, actual behavior, and severity.
5. Require fresh verification evidence after a fix or rollback.
6. Support report-only mode where findings are returned without modifying files.

## Required outputs

- `status`: `passed`, `failed`, or `blocked`.
- `checks`: requirement-to-evidence mapping.
- `bugs`: structured reproduction reports.
- `regression_tests`: tests added or recommended.

## UAF implementation targets

- `src.harness.evaluator`
- `src.harness.sandbox`
- `src.orchestration.roles`
- `src.contracts.WorkflowDispatchResult`
- `tests`
