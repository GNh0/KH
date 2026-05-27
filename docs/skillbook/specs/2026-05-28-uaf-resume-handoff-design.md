# UAF Resume Handoff Design

## Goal

Make UAF prove that a later Codex, Antigravity, or other host session can resume work from repo-local state without relying on the previous chat context.

## Scope

This work intentionally does not add dashboards, distributed servers, Browser/QA sidecars, or native host SDK dependencies. It strengthens the skill/harness value of UAF: persistent goal state, artifact manifests, memory context, and next actions should be recoverable by a future agent run.

## Design

Add a small `HandoffSnapshot` contract and a `ResumeHandoff` builder. The builder reads:

- `.uaf/state/current_goal.json`
- `.uaf/state/artifact_manifest.json`
- `GoalState.metadata.memory_context` when available

It writes:

- `.uaf/state/resume_handoff.json`
- `.uaf/state/resume_handoff.md`

The JSON output is the host/tool contract. The Markdown output is the human-readable handoff note a future LLM session can inspect. Both are project-local runtime state and should not require a dashboard.

## Resume Semantics

A handoff snapshot must include:

- current objective and status
- workflow id when known
- required and collected evidence
- missing evidence
- next recommended action
- artifact manifest summary
- memory context summary when present
- paths to the generated handoff files

If required evidence is missing, the next session should continue or block based on that evidence, not infer completion from the previous conversation.

## Security Boundary

The handoff must stay inside `.uaf/state/`. It should not store credentials or promote uncertain memory. It may reference local artifact paths because those are project-local runtime files; anything intended for public sharing should be redacted separately.
