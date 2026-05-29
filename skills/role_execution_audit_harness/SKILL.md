---
name: role-execution-audit-harness
description: Use when UAF role DAG execution must prove roles actually ran, produced artifacts, and included parallel waves.
---

# Role Execution Audit Harness

This harness audits role orchestration evidence after DAG execution. It answers whether roles such as CEO, advisor, architect, controller, reviewers, QA, security, and release actually produced role task results and artifacts.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Workflow

1. Inspect `WorkflowDispatchResult.metadata["role_orchestration"]` and `role_task_results`.
2. Require `execution_model = dag-asyncio-role-waves`, successful summary state, execution waves, and at least one parallel wave for the default role graph.
3. Verify required roles from the default role graph have successful task results, including `product-strategist`; require `implementer` when implementation work was requested or implementer task results are present.
4. Verify each required role records `metadata.role_artifacts` when project context is available; implementer task results may satisfy this with explicit completion evidence.
5. Attach audit findings to metadata and goal evidence rather than creating user-facing audit documents.

## Required outputs

- `role_execution_audit.status`: `passed` or `failed`.
- `role_execution_audit.findings`: missing role, failed role, or missing artifact findings.
- Evidence key `role execution audited` when the audit passes.

## Common mistakes

- Do not infer role execution from a static role graph; inspect runtime role task results.
- Do not count a role as complete when it has no role artifact in project-backed runs.
- Do not call the DAG parallel when no parallel wave was recorded.
- Do not create user-facing role audit documents unless the user asks for them.

## UAF implementation targets

- `src.orchestration.quality_harnesses.audit_role_execution`
- `src.orchestration.role_orchestrator.RoleOrchestrator`
- `src.tasks.workflows.dispatch_project_workflow`
- `tests.test_quality_harnesses`
- `tests.test_workflows`
