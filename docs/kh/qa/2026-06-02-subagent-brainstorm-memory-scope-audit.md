# Subagent Brainstorming and Memory Scope Audit

Date: 2026-06-02

## Trigger

A blind subagent test was launched without naming KH UAF:

```text
C:\Users\KONEIT\Desktop\Jang\SKillsTest\RetestAutoRoute_20260602_K 폴더에서 재고 입출고 관리 대시보드 개발해줘.
```

The expected behavior was automatic KH front-door intake followed by a brainstorming stop, because the request was an underspecified new operations dashboard direction.

## Observed Failure

The subagent did receive KH skill context and ran the front-door wrapper. The front-door selected `brainstorming-harness` as a follow-up skill, but the subagent then read global Codex memory and implemented a static dashboard in the same turn.

Observed session:

```text
019e8781-8e0d-7fc0-883e-ee97bd88ab8a
```

Important evidence from the session audit:

- `always-on-front-door`, `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`, and `skill-catalog` were runtime-applied.
- `brainstorming-harness` was selected but not executed.
- The subagent read `%CODEX_HOME%/memories/MEMORY.md` and `%CODEX_HOME%/memories/skills/static-web-local-verification/SKILL.md`.
- It used the old static-dashboard memory pattern as if it were current approval.
- It created `index.html`, `styles.css`, and `app.js` before `BrainstormSession` validation or `brainstorm_handoff`.

## Root Cause

There were two separate problems:

1. Front-door output selected brainstorming but did not expose a machine-readable hard execution gate.
2. Session audit treated front-door instruction text containing `BrainstormSession` and `brainstorm_handoff` as if it were actual brainstorming evidence, and did not flag global Codex memory reads after a brainstorming gate.

The memory problem is scope-related. KH scoped memory is project/chat scoped. Host global Codex memory is a cross-chat/subagent source and must not override a current front-door gate unless the user explicitly asks for prior-context reuse.

## Fix

Changes made:

- Added `execution_gate` to `kh_front_door` summary and full output.
- Set `execution_gate.can_execute=false` when `brainstorming-harness` is selected.
- Added blocked actions for global Codex memory, cross-chat/subagent memory, memory-derived shortcuts, sibling reads, implementation, deliverable generation, verification, and browser QA.
- Updated `always-on-front-door`, `brainstorming-harness`, `memory-state-harness`, Codex defaultPrompt, and the marketplace wrapper to treat `execution_gate.can_execute=false` as a hard stop.
- Added session audit detection for `brainstorming_execution_gate_bypassed`.
- Added session audit detection for `cross_chat_memory_leak` when global Codex memory is read while the execution gate is closed.
- Normalized JSON-escaped Windows paths so audit catches `C:\\Users\\...\\.codex\\memories\\...` in Codex rollout logs.

## Verification

Commands run:

```bash
python -B -m unittest tests.test_session_skill_audit tests.test_kh_front_door
python -B -m src.orchestration.session_skill_audit --summary "C:\Users\KONEIT\.codex\sessions\2026\06\02\rollout-2026-06-02T17-44-35-019e8781-8e0d-7fc0-883e-ee97bd88ab8a.jsonl"
python -B -m unittest discover -s tests
python -B -m src.skills.uaf_skill_catalog --check
python -B -m src.skills.uaf_skill_quality --summary
```

Results:

- Targeted tests: 47 passed.
- Full tests: 515 passed.
- Skill catalog: 40 valid, 0 invalid.
- Skill quality summary: success true, lowest quality score 9.3, low quality skills empty.
- The old failed subagent session is now flagged with both:
  - `brainstorming_execution_gate_bypassed`
  - `cross_chat_memory_leak`

## Acceptance Rule

For future blind subagent tests, a vague new app/dashboard/product/process/analysis/design request must not implement in the same turn when front-door returns:

```json
{
  "execution_gate": {
    "can_execute": false,
    "status": "blocked_until_brainstorming_handoff"
  }
}
```

The acceptable behavior is a compact brainstorming response in the user's language with 2-3 options, one recommendation, one approval question, and preserved KH handoff evidence.
