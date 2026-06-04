# Orchestration Decision Audit

Date: 2026-06-04
Branch: codex-runtime
Version: 2.9.61

## Problem

Blind SIDE-style implementation tests could pass even when KH selected host/subagent/parallel/role orchestration but the agent silently continued as a single controller. Existing session audit logic mainly enforced subagent strategy after a subagent was already spawned or when the current session was itself a subagent.

## Independent Review Evidence

Explorer agent `Volta` reviewed the current repository without edits and reported that:

- `session_skill_audit.py` required host/subagent/role audit mainly when subagents were spawned or `spawn_agent` appeared.
- `_subagent_strategy_issues` only audited subagent sessions.
- `single-controller` was allowed too broadly by policy text.
- Minimal fix: require explicit orchestration decisions after approved implementation work, even in main/controller sessions.

Capability probe agent `Mendel` checked nested subagent support from inside a subagent session and reported:

- `nested_subagents_available=false`
- no nested agent spawn API was exposed in that subagent tool set
- no nested agent was created

## Changes

- `src/orchestration/session_skill_audit.py`
  - Added implementation-time orchestration decision audit for main and subagent sessions.
  - Flags missing `subagent_strategy`, `parallel_strategy_decision`, and `role_execution_audit.status` after implementation activity.
  - Requires concrete rationale for `single-controller`; a bare strategy token no longer passes.

- `skills/host_agent_orchestration/SKILL.md`
  - Requires host runtime, nested availability when relevant, subagent strategy, and rationale before non-trivial implementation.

- `skills/subagent_review_pipeline/SKILL.md`
  - Narrows `single-controller` to concrete reasons such as tiny scope, sequential dependency, shared-state risk, host-limited tooling, or unavailable nested subagents.

- `skills/parallel_orchestration_harness/SKILL.md`
  - Requires `parallel_strategy_decision` before the first write when selected.

- `skills/role_execution_audit_harness/SKILL.md`
  - Requires `role_execution_audit.status` or explicit skipped/blocked rationale before completion.

- `.codex-plugin/plugin.json`
  - Adds default host prompt guidance that silent single-agent implementation after selected orchestration skills is an audit failure.

## Regression Tests

Added tests in `tests/test_session_skill_audit.py`:

- main implementation with selected orchestration but no decision is flagged
- main single-controller rationale with parallel and role audit status passes
- bare `subagent_strategy=single-controller` without rationale fails

Verification command:

```powershell
python -B -m unittest tests.test_session_skill_audit
```

Result:

```text
Ran 50 tests in 2.722s
OK
```

## Remaining Boundary

In this Codex environment, parent/main sessions can spawn subagents, but spawned subagents currently cannot spawn nested subagents. KH should therefore record `nested_subagents_available=false` and use `single-controller`, `review-only`, or `blocked` with a reason inside subagent sessions rather than pretending nested orchestration happened.
