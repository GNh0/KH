---
name: subagent-review-pipeline
description: Use when coordinating implementer, spec-reviewer, and code-quality-reviewer roles for independent UAF subtasks.
---

# Subagent Review Pipeline

This is a personal UAF subagent coordination harness. It defines review roles and status handling without depending on external subagent plugins.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `references/standard-task-packets.md` for implementer, spec-reviewer, and code-quality-reviewer prompt packet fields.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Reference basis

- Personal subagent workflow: fresh subagent per task, two-stage review, implementer status handling, and final review before branch finishing.

## Roles

- `implementer`: performs one bounded task, runs relevant checks, and reports changed files plus status.
- `spec-reviewer`: compares the result to the assigned task and user constraints.
- `code-quality-reviewer`: reviews maintainability, integration risk, tests, and security after spec compliance passes.
- `controller`: owns sequencing, shared context, retries, and final reporting.

Upstream governance and downstream release roles come from `orchestration-role-graph`: `ceo`, `advisor`, `product-strategist`, `system-architect`, `implementation-planner`, `qa-verifier`, `security-reviewer`, and `release-manager`.

## Status contract

- `success`: proceed to spec review when evidence is present.
- `failed`: return the task to implementation or mark the plan failed.
- `blocked`: diagnose whether the blocker is context, model capability, task size, or a flawed plan.
- Optional reviewer substatus may use `done_with_concerns`, `needs_context`, or `approval_required` inside metadata, but `WorkflowTaskResult.status` remains `success`, `failed`, or `blocked`.

## Workflow

1. Split the plan into independent, bounded tasks.
2. Build a compact task packet per implementer using `references/standard-task-packets.md`: objective, workspace, base SHA, plan section, owned files, forbidden files, checks, expected artifacts, commit message, and report fields.
3. When task packets, command logs, or subagent transcripts are large, apply `token-optimizer` as a quality-first context budget gate; use `passthrough` or `blocked` if compression would reduce review quality.
4. Dispatch one implementer per task with only the needed context.
5. Run spec review first; send any gap back to implementation.
6. Run quality review only after spec compliance passes.
7. Preserve every reviewer finding in the aggregated result.
8. For task-plan development runs, update `.kh/development/<run-id>/state/progress.json` after implementer, spec reviewer, code-quality reviewer, fix, re-review, and commit events.
9. When implementers can edit files concurrently, isolate them with `.worktrees/<task>`, an isolated branch, or a host-provided equivalent workspace.
10. Run final review across the combined implementation before finishing.

## Large Work Bundle Reporting

When this skill is part of `large_work_orchestration_bundle`, record `skill_statuses["subagent-review-pipeline"]` as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`. If subagents are not used, the rationale should say whether the task was too small, sequentially dependent, host-limited, or better handled by the main controller.

## External Benchmark Recipe

Use this harness when an implementation needs independent roles to produce reviewable evidence:

1. Controller creates one task packet per implementer: objective, owned files, forbidden files, checks, and expected artifacts.
2. Implementer returns `WorkflowTaskResult` with changed files, commands run, evidence, and status.
3. Spec reviewer compares the result to the task packet and user constraints before code quality review starts.
4. Code-quality reviewer records structured findings with severity, file/path when available, and required fix.
5. Controller aggregates all statuses and blocks release if any task is failed, blocked, or has unresolved required findings.

Pressure scenario: if an implementer says "done" but did not report changed files or checks, spec review must fail for missing evidence before quality review.

## Required outputs

- Implementer result per bounded task with status, changed files, checks, and evidence.
- Compact task packet per implementer that is self-contained and excludes unrelated session history.
- Standard reviewer packets for `spec-reviewer` and `code-quality-reviewer` when those roles are dispatched.
- `token_optimizer_status` for large task packets, command outputs, or subagent transcripts.
- Development progress state update when a task-plan run is active.
- Isolation evidence when two or more implementers can write files.
- Spec-reviewer result for each implementer output before quality review.
- Code-quality-reviewer result with findings, reviewer severity, file references, line references when available, and suggested fix.
- Controller aggregate that preserves `success`, `failed`, `blocked`, and optional reviewer substatus metadata.

## Common mistakes

- Do not let implementers share hidden state that reviewers cannot inspect.
- Do not dispatch concurrent implementers into the same mutable checkout unless the write set is proven non-overlapping.
- Do not skip spec review because code quality looks good.
- Do not flatten reviewer findings into a vague summary.
- Do not mark blocked tasks as failed implementation without identifying the blocker category.

## UAF implementation targets

- `src.tasks.workflows`
- `src.orchestration.roles`
- `src.orchestration.agent_loop`
- `src.orchestration.role_orchestrator.RoleOrchestrator`
- `src.orchestration.gate_evaluators.normalize_review_findings`
- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.skills.uaf_skill_catalog`
