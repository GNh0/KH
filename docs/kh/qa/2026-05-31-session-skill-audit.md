# KH Session Skill Audit - 2026-05-31

Scope: three Codex session logs were audited against all 33 packaged KH skills with `src.orchestration.session_skill_audit`.

Sessions:

- `019e797d-6935-7432-bca5-aa98a35d3494`
- `019e78ec-62bd-7ae3-a7ba-539c4b4d61bf`
- `019e6948-1937-7aa0-ac33-e6c99a694e03`

Command:

```powershell
python -m src.orchestration.session_skill_audit --summary C:\Users\User\.codex\sessions\2026\05\31\rollout-2026-05-31T00-25-27-019e797d-6935-7432-bca5-aa98a35d3494.jsonl C:\Users\User\.codex\sessions\2026\05\30\rollout-2026-05-30T21-47-03-019e78ec-62bd-7ae3-a7ba-539c4b4d61bf.jsonl C:\Users\User\.codex\sessions\2026\05\27\rollout-2026-05-27T20-53-13-019e6948-1937-7aa0-ac33-e6c99a694e03.jsonl
```

## Result

- Full catalog size: 33 skills.
- Sessions audited: 3.
- Required skill evidence gaps: 0 after catalog-level observation classification.
- Guard-level issues: 8.

Issues by skill:

- `goal-state-harness`: 3 active-goal completion guard blocks. The sessions emitted completion while the goal was still active.
- `token-optimizer`: 2 token gate blocks. Large sessions crossed token thresholds without runtime token optimization or explicit passthrough evidence.
- `review-gate-harness`: 2 review incomplete blocks. Reviewers timed out or were closed while still running.
- `host-agent-orchestration`: 1 subagent accounting block. Spawned subagents outnumbered closed/accounted subagents.

## Improvements Added

- `src.orchestration.session_skill_audit` audits session logs against every packaged KH skill and separates required, applied, inspected, mentioned, and missing evidence.
- Postmortem guard failures are now promoted into skill audit issues, so "skill was mentioned" cannot hide blocked token/review/goal/subagent gates.
- `src.orchestration.runtime_token_optimizer` records runtime token optimization for `WorkflowTaskResult` command output and subagent transcripts.
- `src.orchestration.runtime_memory` records scoped memory candidates without promoting them to durable memory.
- Workflow usability runtime now attaches `token_optimization` and `memory_state` evidence.

## Operational Rule

For large sessions, run both:

```powershell
python -m src.orchestration.session_postmortem <session.jsonl>
python -m src.orchestration.session_skill_audit --summary <session.jsonl>
```

The first catches guard failures. The second maps those failures back to the KH skills that should own the fix.
