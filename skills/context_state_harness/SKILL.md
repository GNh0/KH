---
name: context-state-harness
description: Use when a UAF workflow needs resumable context, decision capture, handoff notes, or state restore across agent runs.
---

# Context State Harness

This is a UAF-native context harness for context-save and context-restore patterns. It keeps resumable workflow state project/chat-scoped and explicit without polluting the target project root by default.

## Support files

- Read `references/usage.md` before applying this skill to a real task; it expands the trigger boundary, inputs, execution pattern, evidence, and failure handling.
- Use `examples/minimal-workflow.md` as a compact scenario for checking whether the host followed this skill correctly.
- Run `python scripts/smoke_check.py` from this skill folder to verify the support files are present and wired from `SKILL.md`.

## Pattern basis

- Context workflow: save/restore working context, git state, decisions, remaining work, and handoff continuity.
- UAF: snapshot manager, adapter metadata, role graph, and workflow dispatch results.

## Workflow

1. Capture current git branch, dirty files, active workflow id, role graph, and task status in goal/workflow metadata before saving the handoff.
2. Record decisions, assumptions, blockers, and next actions in structured metadata.
3. Store context artifacts inside the UAF runtime state directory, not in external user skill folders and not in the target project root by default.
4. Write a resume handoff snapshot to runtime `.uaf/state/resume_handoff.json` and a human-readable note to `.uaf/state/resume_handoff.md`.
5. Restore by reading the newest matching context; hosts should validate branch/head/dirty-file state against `git_state` before treating it as authoritative.
6. Treat stale or conflicting context as blocked, not silently authoritative.

## Required outputs

- `context_id`: stable id for the saved context.
- `git_state`: branch, head sha, and dirty file summary.
- `decisions`: explicit decisions and assumptions.
- `remaining_work`: next tasks and verification commands.
- `resume_handoff`: JSON and Markdown paths for a future host session.

## Common mistakes

- Do not store resumable runtime state in the target project root unless project-local state was explicitly requested.
- Do not trust stale context when the git branch, head, or dirty files no longer match.
- Do not omit blocked reasons, remaining work, or verification commands from handoff state.
- Do not persist secrets, credentials, or private tool outputs as memory/context records.

## UAF implementation targets

- `src.core.snapshot_manager`
- `src.contracts.AdapterRequest`
- `src.contracts.AdapterResult`
- `src.contracts.HandoffSnapshot`
- `src.contracts.WorkflowDispatchResult`
- `src.orchestration.handoff`
- `src.orchestration.agent_loop`
