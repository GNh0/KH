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
3. Require normalized implementation evidence; a successful task status alone is not enough to pass review.
4. Report findings with severity, file path, line when available, reason, and suggested fix.
5. Separate findings that can be auto-fixed from findings that require user or owner approval.
6. Produce a gate result for `spec-reviewer`, `code-quality-reviewer`, and `release-manager`.
7. Preserve partial failures instead of collapsing them into a single text log.

## Required outputs

- `status`: `passed`, `failed`, or `blocked`.
- `findings`: list of structured review findings.
- `evidence`: tests, commands, files, or manual inspection used by the review.
- `evidence_records`: passed records grant evidence through `record.evidence`; `metadata.evidence_key` is trace metadata and does not satisfy a goal by itself.
- `next_action`: `fix`, `ask`, `verify`, or `release`.

## Common mistakes

- Do not pass review from `WorkflowTaskResult.status == success` alone.
- Do not treat `metadata.evidence_key` as satisfying goal evidence without a passed record.
- Do not hide partial failures by returning one generic review message.
- Do not run code-quality review before spec compliance gaps are resolved.

## UAF implementation targets

- `src.orchestration.roles`
- `src.orchestration.gate_evaluators`
- `src.orchestration.evidence_producers`
- `src.contracts.WorkflowDispatchResult`
- `src.contracts.WorkflowTaskResult`
- `src.platforms.dispatcher_factory`
- `tests`
