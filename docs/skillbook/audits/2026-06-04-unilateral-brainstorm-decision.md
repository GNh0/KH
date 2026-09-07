# 2026-06-04 Unilateral Brainstorm Decision Audit

## Trigger

Blind subagent retest `019e90d8-6f92-7d42-a559-9238ad9e4179` used installed KH UAF `2.9.54` and received an ordinary request without KH/UAF/skill wording:

`C:\Users\KONEIT\Desktop\Jang\SKillsTest\RetestAutoRoute_20260604_G folder: build an inventory inbound/outbound dashboard.`

The subagent correctly avoided writing files before approval, but the visible brainstorm still made too many decisions on behalf of the user.

## Failure Evidence

The first response said, in effect:

- It would create the missing folder and proceed.
- It would choose the location-stock operating model.
- It would use HTML + CSS + JavaScript.

`python -B -m src.orchestration.session_skill_audit <session-log> --summary`

Now flags:

- `brainstorming-harness`: `shallow_visible_brainstorming`
- `brainstorming-harness`: `unilateral_brainstorm_decision`

The second finding catches phrases equivalent to `2번으로 가겠습니다`, `기준으로 만들겠습니다`, `새로 만들어서 진행`, and approval questions that include an unapproved implementation stack.

## Fix

KH UAF now treats a recommendation as advisory, not an agent-owned final decision. Before user approval:

- The agent should say "my recommendation is option 2 because..."
- The agent must keep alternatives and open questions visible.
- The agent must ask the user to choose or approve.
- The agent must not say "I will go with option 2", "2번으로 가겠습니다", or "기준으로 만들겠습니다".
- The agent must not lock a stack such as HTML/CSS/JavaScript, React, WinForms, or database storage unless the user asked for stack selection or already approved the domain model.

The audit now emits `unilateral_brainstorm_decision` when these patterns appear in the visible brainstorm response.

