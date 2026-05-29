---
name: review-gate-harness
description: Use when a UAF workflow needs structured pre-landing review gates, actionable findings, or reviewer status normalization.
---

# Review Gate Harness

This is a UAF-native review harness for structured review workflow patterns. It must not call or require an external review runtime at execution time.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Pattern basis

- Review workflow: pre-landing review, completeness checks, severity-ranked findings, auto-fix separation, and final readiness dashboards.
- UAF: `WorkflowDispatchResult.gate_results`, role graph review stages, and adapter result metadata.

## Workflow

1. Read the design document, changed files, task results, and verification evidence.
2. Check spec compliance before code quality.
3. Require normalized implementation evidence; a successful task status alone is not enough to pass review.
4. Report findings with `src.orchestration.gate_evaluators.build_review_finding` so severity, file path, line when available, reason, and suggested fix are normalized.
5. Separate findings that can be auto-fixed from findings that require user or owner approval.
6. Fail `security-reviewer` when security findings are present so `release-manager` blocks release and preserves the upstream finding text.
7. Produce a gate result for `spec-reviewer`, `code-quality-reviewer`, and `release-manager`.
8. Preserve partial failures instead of collapsing them into a single text log.

## External Benchmark Recipe

Use this harness like a code-review protocol:

1. Start with spec compliance: user request, design output, changed files, and evidence.
2. Normalize every finding with severity, owner role, file/path when available, reason, and suggested fix.
3. Run quality review only after required spec gaps are resolved or explicitly waived.
4. Run security/release gates last and preserve upstream findings in blocked release output.
5. Return "no findings" only after naming the evidence reviewed.

Pressure scenario: if a task result is `success` but contains no changed files, test output, or manual evidence, review remains blocked for missing evidence.

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
- `src.orchestration.gate_evaluators.build_review_finding`
- `src.orchestration.gate_evaluators.normalize_review_findings`
- `src.orchestration.gate_evaluators.evaluate_spec_review_gate`
- `src.orchestration.gate_evaluators.evaluate_code_quality_gate`
- `src.orchestration.gate_evaluators.evaluate_release_gate`
- `src.orchestration.evidence_producers`
- `src.contracts.WorkflowDispatchResult`
- `src.contracts.WorkflowTaskResult`
- `src.platforms.dispatcher_factory`
- `tests.test_gate_evaluators`
