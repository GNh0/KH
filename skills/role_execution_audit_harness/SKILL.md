---
name: role-execution-audit-harness
description: Use when UAF role DAG execution must prove roles actually ran, produced artifacts, and included parallel waves.
---

# Role Execution Audit Harness

This harness audits role orchestration evidence after DAG execution. It answers whether roles such as CEO, advisor, architect, controller, reviewers, QA, security, and release actually produced role task results and artifacts.

## Workflow

1. Inspect `WorkflowDispatchResult.metadata["role_orchestration"]` and `role_task_results`.
2. Require `execution_model = dag-asyncio-role-waves`, successful summary state, execution waves, and at least one parallel wave for the default role graph.
3. Verify required roles have successful task results.
4. Verify each required role records `metadata.role_artifacts` when project context is available.
5. Attach audit findings to metadata and goal evidence rather than creating user-facing audit documents.

## Required outputs

- `role_execution_audit.status`: `passed` or `failed`.
- `role_execution_audit.findings`: missing role, failed role, or missing artifact findings.
- Evidence key `role execution audited` when the audit passes.

## UAF implementation targets

- `src.orchestration.quality_harnesses.audit_role_execution`
- `src.orchestration.role_orchestrator.RoleOrchestrator`
- `src.tasks.workflows.dispatch_project_workflow`
- `tests.test_quality_harnesses`
- `tests.test_workflows`
