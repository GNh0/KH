---
name: orchestration-role-graph
description: Use when inspecting or extending the default UAF orchestration roles such as CEO, advisor, architect, controller, implementer, reviewers, QA, security, and release.
---

# Orchestration Role Graph

This is the UAF-native role contract for multi-agent orchestration. It makes leadership, advisory, design, implementation, review, verification, and release responsibilities explicit and executable instead of leaving them as prompt-only assumptions.

## Required default roles

- `ceo`: owns business intent, priority, success criteria, and tradeoff approval.
- `advisor`: challenges assumptions and records cross-domain risks.
- `product-strategist`: translates intent into feature scope and acceptance criteria.
- `system-architect`: creates technical architecture, file boundaries, and constraints.
- `implementation-planner`: breaks design into bounded tasks and verification steps.
- `controller`: coordinates role execution, retries, aggregation, and final reporting.
- `implementer`: executes one bounded task and reports exact changes and checks.
- `spec-reviewer`: verifies implementation against user constraints and acceptance criteria.
- `code-quality-reviewer`: reviews maintainability, integration risk, tests, and local pattern fit.
- `qa-verifier`: maps completion claims to fresh verification evidence.
- `security-reviewer`: reviews permissions, file writes, commands, secrets, and sandbox boundaries.
- `release-manager`: packages final status, integration decision, and residual risks.

## Stage order

1. `executive`
2. `advisory`
3. `architecture`
4. `planning`
5. `implementation`
6. `review`
7. `release`

## Runtime contract

- `src.orchestration.roles.default_role_profiles()` is the source of truth.
- `build_default_role_metadata()` serializes the graph into `AdapterRequest.metadata`.
- `src.orchestration.role_orchestrator.RoleOrchestrator` executes selected roles as a dependency DAG.
- Ready roles in the same wave must be launched concurrently with `asyncio.create_task(...)`.
- Blocked roles must produce structured `WorkflowTaskResult` records instead of disappearing from the run.
- Project-backed roles must write runtime role-stage artifacts under `.uaf/artifacts/roles/`, outside the target project root unless `UAF_PROJECT_LOCAL_STATE=1` is explicit.
- Workflow metadata must include `role_orchestration`, `role_orchestration_stages`, and `role_task_results`; each role task should expose `metadata.role_artifacts` when a role-stage artifact was written.
- `AgentLoop` appends a role graph brief to the design content before dispatch.
- Local and Antigravity dispatchers preserve role metadata in `AdapterResult.metadata`.
- File workers execute as bounded parallel `implementer` tasks.
- Review, QA, security, and release roles run as role tasks and also emit gate-compatible metadata.

## Default parallel waves

- `ceo` starts the role DAG.
- `advisor` and `product-strategist` can run in the same wave after `ceo`.
- `system-architect`, `implementation-planner`, and `controller` run after their dependencies are satisfied.
- File-level `implementer` work fans out through the bounded worker queue.
- `qa-verifier` and `security-reviewer` can run in the same wave after code quality review.
- `release-manager` runs after QA and security are complete or records a blocked result when they are not.

## Required outputs

- Default role metadata with role ids, stages, responsibilities, dependencies, and execution flags.
- Runtime `role_orchestration` summary with execution model, waves, parallel wave count, and status.
- `role_task_results` for every required role, including blocked results instead of silent omissions.
- `metadata.role_artifacts` for role-stage artifacts when project context is available.

## Common mistakes

- Do not list roles in documentation without preserving them in runtime metadata.
- Do not call the run parallel unless role waves or worker fan-out actually executed.
- Do not let reviewer, QA, security, or release roles disappear when an upstream role blocks.
- Do not make `implementer` the only meaningful role in a role-based orchestration run.

## UAF implementation targets

- `src.orchestration.roles`
- `src.orchestration.role_orchestrator`
- `src.orchestration.agent_loop`
- `src.platforms.dispatcher_factory`
- `src.tasks.workflows`
- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
