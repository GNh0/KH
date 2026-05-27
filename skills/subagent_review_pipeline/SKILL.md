---
name: subagent-review-pipeline
description: Use when coordinating implementer, spec-reviewer, and code-quality-reviewer roles for independent UAF subtasks.
---

# Subagent Review Pipeline

This is a personal UAF subagent coordination harness. It defines review roles and status handling without depending on external subagent plugins.

## Reference basis

- Personal subagent workflow: fresh subagent per task, two-stage review, implementer status handling, and final review before branch finishing.

## Roles

- `implementer`: performs one bounded task, runs relevant checks, and reports changed files plus status.
- `spec-reviewer`: compares the result to the assigned task and user constraints.
- `code-quality-reviewer`: reviews maintainability, integration risk, tests, and security after spec compliance passes.
- `controller`: owns sequencing, shared context, retries, and final reporting.

Upstream governance and downstream release roles come from `orchestration-role-graph`: `ceo`, `advisor`, `product-strategist`, `system-architect`, `implementation-planner`, `qa-verifier`, `security-reviewer`, and `release-manager`.

## Status contract

- `DONE`: proceed to spec review.
- `DONE_WITH_CONCERNS`: inspect concerns before review; resolve correctness or scope concerns first.
- `NEEDS_CONTEXT`: add missing context and retry the task.
- `BLOCKED`: diagnose whether the blocker is context, model capability, task size, or a flawed plan.

## Workflow

1. Split the plan into independent, bounded tasks.
2. Dispatch one implementer per task with only the needed context.
3. Run spec review first; send any gap back to implementation.
4. Run quality review only after spec compliance passes.
5. Preserve every reviewer finding in the aggregated result.
6. Run final review across the combined implementation before finishing.

## UAF implementation targets

- `src.tasks.workflows`
- `src.orchestration.roles`
- `src.orchestration.agent_loop`
- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.skills.uaf_skill_catalog`
