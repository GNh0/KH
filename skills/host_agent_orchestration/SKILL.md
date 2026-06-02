---
name: host-agent-orchestration
description: Use when kh-uaf:always-on-front-door has already run and selected this skill; use it when designing portable UAF host agent loops, subagent delegation, tool permissions, hooks, or observability across Codex, Antigravity-style, Claude Code, or local runtimes.
---

# Host Agent Orchestration

## KH Entry Contract

- Start every non-trivial turn through `always-on-front-door` unless this skill is that bootstrap step or the current turn was classified as light/direct.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing requests as KH-routed even when KH names are omitted.
- Use this skill only when front-door routing, an explicit user request, or a required follow-up gate selects it.
- Report this skill as `applied` only after its implementation target, gate, artifact, command-output handling, or explicit passthrough/blocked rationale produces evidence.
- Reading this SKILL.md, listing the catalog, or seeing the skill in `selected_not_executed_skills` is not execution evidence.

This is a personal UAF host orchestration harness. It packages reusable agent, subagent, permission, hook, persistence, structured output, and observability patterns without requiring any installed vendor SDK, Gemini plugin directory, or local user configuration at runtime.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo and verify contract-shaped JSON plus any demo artifacts.

## Reference basis

- Host orchestration patterns: agent profiles, conversation records, connections, subagents, MCP tools, tool permissions, safety policies, hooks, error recovery, persistence, structured output, and observability.
- Antigravity-style SDK concepts are design inputs only. Package the reusable behavior here as UAF contracts and personal orchestration rules.

## Workflow

1. Model each worker as an agent profile with explicit role, allowed tools, input contract, and output contract.
2. Route user work through a conversation record that preserves task intent, constraints, artifacts, and structured results.
3. Delegate only independent subtasks to subagents; keep shared-state edits behind the main controller.
4. If the current host is itself a subagent or worker, record whether nested subagents are available before implementation. If not available or not useful, record `subagent_strategy=single-controller` with a host-limited, sequential, tiny-task, or shared-state rationale.
5. Resolve tool access before dispatch with a deny/ask/allow/default policy.
6. Attach lifecycle hooks for pre-dispatch validation, post-dispatch normalization, error recovery, and audit logging.
7. Emit observability metadata for model/runtime choice, token budget, elapsed time, tool calls, and failure category.

Use the default UAF role graph for orchestration: `ceo`, `advisor`, `product-strategist`, `system-architect`, `implementation-planner`, `controller`, `implementer`, `spec-reviewer`, `code-quality-reviewer`, `qa-verifier`, `security-reviewer`, and `release-manager`.

## Large Work Bundle Reporting

When this skill is part of `large_work_orchestration_bundle`, record `skill_statuses["host-agent-orchestration"]` as `applied`, `considered_not_needed`, `skipped_with_rationale`, or `blocked`. Include the host runtime, adapter path, missing capability, or no-subagent rationale as evidence.

For subagent sessions, no-subagent rationale is mandatory before implementation. Do not leave it implicit. Record `host_runtime`, `nested_subagents_available`, `subagent_strategy`, and `strategy_rationale`.

## External Benchmark Recipe

Use this harness when host differences could otherwise be hidden behind vague "agent ran" claims:

1. Normalize the host request into `AdapterRequest(project_dir, files, design_doc, platform_mode, metadata)`.
2. Put role graph, tool policy, goal id, memory scope, evidence requirements, and budget in `metadata`.
3. Dispatch through the selected adapter or mark `status="blocked"` with the missing host capability.
4. Store host-specific fields inside `AdapterResult.metadata`; keep top-level status/message portable.
5. Report the controller aggregate with every subagent result, partial failure, and blocked reason.

Pressure scenario: if Codex, Antigravity-style, Claude Code, or local runner lacks a tool, do not silently fall back to another host. Return a blocked result that names the missing tool, affected role, and recovery path.

## Required outputs

- `AdapterRequest` containing `project_dir`, `files`, `design_doc`, `platform_mode`, and metadata for role graph, goal, memory, evidence, tools, budget, and safety policy.
- `AdapterResult` containing top-level `status`, `message`, `workflow_id`, and `metadata`; artifact paths, evidence, task results, and blocked/failure reasons belong inside `metadata`.
- `subagent_strategy` and nested-subagent availability when the current worker is already a host subagent.
- A controller-level summary that includes every subagent result, including partial failures.

## Failure handling

- Missing credentials, tools, or model IDs should produce a structured blocked result, not an implicit fallback.
- Tool permission denial should be visible in result metadata.
- Hook failures should be reported, but they must not hide the original agent result.

## Common mistakes

- Do not assume Codex, Antigravity-style hosts, Claude Code, and local runners share the same tool APIs.
- Do not let host-specific permissions bypass UAF guard and evidence policy.
- Do not claim subagent delegation happened unless adapter metadata or role task results prove it.
- Do not store host-only state in the project output surface.

## UAF implementation targets

- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.orchestration.roles`
- `src.platforms.dispatcher_factory`
- `src.orchestration.agent_loop`
- `src.skills.uaf_skill_catalog`
