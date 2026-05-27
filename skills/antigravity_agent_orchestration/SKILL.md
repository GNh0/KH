---
name: antigravity-agent-orchestration
description: Use when designing portable UAF agent loops, subagent delegation, tool permissions, hooks, or observability from Antigravity-style agent patterns.
---

# Antigravity Agent Orchestration

This is a UAF-native harness derived from Google Antigravity SDK concepts. It must not import or require an installed Antigravity SDK, Gemini plugin directory, or local user configuration at runtime.

## Reference basis

- Google Antigravity SDK: agent, conversation, connection, subagents, MCP tools, tool permissions, safety policies, hooks, error recovery, persistence, structured output, and observability.
- Local Antigravity skills are design inputs only. Package the reusable behavior here as UAF contracts and orchestration rules.

## Workflow

1. Model each worker as an agent profile with explicit role, allowed tools, input contract, and output contract.
2. Route user work through a conversation record that preserves task intent, constraints, artifacts, and structured results.
3. Delegate only independent subtasks to subagents; keep shared-state edits behind the main controller.
4. Resolve tool access before dispatch with a deny/ask/allow/default policy.
5. Attach lifecycle hooks for pre-dispatch validation, post-dispatch normalization, error recovery, and audit logging.
6. Emit observability metadata for model/runtime choice, token budget, elapsed time, tool calls, and failure category.

## Required outputs

- `AdapterRequest` containing agent role, task text, allowed tools, budget, and safety policy.
- `AdapterResult` containing status, normalized output, artifact paths, and metadata.
- A controller-level summary that includes every subagent result, including partial failures.

## Failure handling

- Missing credentials, tools, or model IDs should produce a structured blocked result, not an implicit fallback.
- Tool permission denial should be visible in result metadata.
- Hook failures should be reported, but they must not hide the original agent result.

## UAF implementation targets

- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.platforms.dispatcher_factory`
- `src.orchestration.agent_loop`
- `src.skills.uaf_skill_catalog`
