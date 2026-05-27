---
name: review-gate-harness
description: Use when a UAF workflow needs structured pre-landing review gates, actionable findings, or reviewer status normalization.
---

# Review Gate Harness

This is a UAF-native review harness for structured review workflow patterns. It must not call or require an external review runtime at execution time.

## Pattern basis

- Review workflow: pre-landing review, completeness checks, severity-ranked findings, auto-fix separation, and final readiness dashboards.
- UAF: `WorkflowDispatchResult.gate_results`, role graph review stages, and adapter result metadata.

## Workflow

1. Read the design document, changed files, task results, and verification evidence.
2. Check spec compliance before code quality.
3. Report findings with severity, file path, line when available, reason, and suggested fix.
4. Separate findings that can be auto-fixed from findings that require user or owner approval.
5. Produce a gate result for `spec-reviewer`, `code-quality-reviewer`, and `release-manager`.
6. Preserve partial failures instead of collapsing them into a single text log.

## Required outputs

- `status`: `passed`, `failed`, or `blocked`.
- `findings`: list of structured review findings.
- `evidence`: tests, commands, files, or manual inspection used by the review.
- `next_action`: `fix`, `ask`, `verify`, or `release`.

## UAF implementation targets

- `src.orchestration.roles`
- `src.contracts.WorkflowDispatchResult`
- `src.contracts.WorkflowTaskResult`
- `src.platforms.dispatcher_factory`
- `tests`
