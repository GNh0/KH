---
name: context-state-harness
description: Use when a UAF workflow needs resumable context, decision capture, handoff notes, or state restore across agent runs.
---

# Context State Harness

This is a UAF-native context harness derived from gstack context-save and context-restore patterns. It keeps resumable workflow state project-local and explicit.

## Reference basis

- gstack: save/restore working context, git state, decisions, remaining work, and handoff continuity.
- UAF: snapshot manager, adapter metadata, role graph, and workflow dispatch results.

## Workflow

1. Capture current git branch, dirty files, active workflow id, role graph, and task status.
2. Record decisions, assumptions, blockers, and next actions in structured metadata.
3. Store context artifacts inside a project-local state directory, not in external user skill folders.
4. Restore by reading the newest matching context and validating that the repository state still matches.
5. Treat stale or conflicting context as blocked, not silently authoritative.

## Required outputs

- `context_id`: stable id for the saved context.
- `git_state`: branch, head sha, and dirty file summary.
- `decisions`: explicit decisions and assumptions.
- `remaining_work`: next tasks and verification commands.

## UAF implementation targets

- `src.core.snapshot_manager`
- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.contracts.WorkflowDispatchResult`
- `src.orchestration.agent_loop`
