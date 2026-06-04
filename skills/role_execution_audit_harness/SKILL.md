---
name: role-execution-audit-harness
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when UAF role DAG execution must prove roles actually ran, produced artifacts, and included parallel waves.
---

# Role Execution Audit Harness

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This harness audits role orchestration evidence after DAG execution. It answers whether roles such as CEO, advisor, architect, controller, reviewers, QA, security, and release actually produced role task results and artifacts.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Workflow

1. Inspect `WorkflowDispatchResult.metadata["role_orchestration"]` and `role_task_results`.
2. Require `execution_model = dag-asyncio-role-waves`, successful summary state, execution waves, and at least one parallel wave for the default role graph.
3. Verify required roles from the default role graph have successful task results, including `product-strategist`; require `implementer` when implementation work was requested or implementer task results are present.
4. Verify each required role records `metadata.role_artifacts` when project context is available; implementer task results may satisfy this with explicit completion evidence.
5. Attach audit findings to metadata and goal evidence rather than creating user-facing audit documents.

## Large Work Bundle Reporting

When this skill is part of `large_work_orchestration_bundle`, record `skill_statuses["role-execution-audit-harness"]` as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`. Use `considered_not_needed` only when no role DAG or subagent wave was claimed; if role execution is claimed, the audit must inspect runtime role results.

When implementation work starts after this skill was selected, record `role_execution_audit.status` before completion. If no role DAG or subagent wave is useful, the status may be `skipped` or `blocked`, but it must say why. A static role list, SKILL.md read, or front-door selected list is not runtime role execution evidence.

## External Benchmark Recipe

Use this harness after any claimed role-DAG run:

1. Read `role_orchestration`, `role_orchestration_stages`, and `role_task_results` from workflow metadata.
2. Check execution model, wave count, parallel waves, required role coverage, and role artifacts.
3. Require `product-strategist` and all default governance/review/release roles.
4. Require `implementer` when implementation work exists.
5. Emit failed findings for static-only role graphs or missing runtime artifacts.

Pressure scenario: if a report lists roles but `role_task_results` is empty, role execution audit fails even when the static role graph is complete.

## Required outputs

- `role_execution_audit.status`: `passed`, `failed`, `skipped`, or `blocked`.
- `role_execution_audit.findings`: missing role, failed role, or missing artifact findings.
- Evidence key `role execution audited` when the audit passes.

## Common mistakes

- Do not infer role execution from a static role graph; inspect runtime role task results.
- Do not count a role as complete when it has no role artifact in project-backed runs.
- Do not call the DAG parallel when no parallel wave was recorded.
- Do not finish implementation after this skill was selected without role execution audit evidence or an explicit skipped/blocked rationale.
- Do not create user-facing role audit documents unless the user asks for them.

## UAF implementation targets

- `src.orchestration.quality_harnesses.audit_role_execution`
- `src.orchestration.role_orchestrator.RoleOrchestrator`
- `src.tasks.workflows.dispatch_project_workflow`
- `tests.test_quality_harnesses`
- `tests.test_workflows`
