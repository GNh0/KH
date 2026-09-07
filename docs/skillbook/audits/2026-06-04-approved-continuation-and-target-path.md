# 2026-06-04 Approved Continuation And Target Path Audit

## Trigger

Blind subagent retest `019e90a2-6b6a-7f20-b6f6-f6ba38f1937e` used installed KH UAF `2.9.53` and received an ordinary request without KH/UAF/skill wording:

`C:\Users\KONEIT\Desktop\Jang\SKillsTest\RetestAutoRoute_20260604_F folder: build an inventory inbound/outbound dashboard.`

The first brainstorming response passed the visible brainstorm audit. After the user approved the recommended basic stock ledger model, the implementation phase still failed multiple KH behavior gates.

## Failure Evidence

`python -B -m src.orchestration.session_skill_audit <session-log> --summary`

Flagged:

- `guard-policy-harness`: `target_path_substitution`
- `brainstorming-harness`: `brainstorming_execution_gate_bypassed`
- `memory-state-harness`: `cross_chat_memory_leak`
- `host-agent-orchestration` and `subagent-review-pipeline`: missing subagent strategy
- `verification-before-completion-harness`: failed verification was not reflected correctly
- `token-optimizer`: required after cumulative token growth but not applied or passed through

The subagent created `RetestAutoRoute_20260604_F/...` under the workspace first, then copied files into the requested absolute target path. The final target folder existed, but the staging pattern is still a guard failure because user-facing files were generated outside the exact requested target before approval for exact-path writes.

The subagent also read global Codex memory and static-web skill memory after the brainstorming gate, using old static dashboard preferences as implementation context. That violates KH memory scope isolation for a fresh blind target.

## Fix

KH UAF now adds stricter host-visible rules:

- Approved brainstorm continuation requires current-run `approval_frame`, `BrainstormSession`, `decision_log`, and `brainstorm_handoff` before implementation.
- User approval of a recommendation does not authorize global Codex memory lookup, memory skill notes, sibling folders, or previous run folders.
- Absolute target folders require direct exact-path writes or a permission-needed stop.
- Same-name relative folders, staging folders, temporary generated projects, and copy-back flows are explicitly forbidden.
- Relative staging followed by `Copy-Item`, `Move-Item`, or equivalent remains a guard failure.

## Verification

The fix is covered by documentation and prompt regression tests before publishing the next plugin version.

