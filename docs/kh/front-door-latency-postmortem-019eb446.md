# Front-Door Latency Postmortem: `019eb446-e275-7880-b69f-84774dec5add`

Date: 2026-06-11

## Summary

Session `019eb446-e275-7880-b69f-84774dec5add` showed user-visible latency before KH UAF did useful work. The front-door runtime itself was not the slow component. The slow path came from host behavior around the front-door skill and command output handling.

## Findings

- The assistant read `always_on_front_door/SKILL.md` near the start of the session, then delayed for about 324 seconds before running the front-door command.
- The front-door command execution was fast once started, around sub-second runtime in the captured session.
- A broad source search later produced a timeout dump with `Total output lines: 1050`, after which the next agent action was delayed by about 322 seconds.
- The request classifier also had a drift risk: KH UAF diagnosis prompts containing Korean diagnostic wording could be routed as `medical` instead of `software`.

## Fixes

- `always_on_front_door/SKILL.md` was shortened into an execution-oriented command card.
- Plugin default prompts now require the front-door wrapper to start immediately after the command card, targeting under 10 seconds from skill read to intake command.
- `session_skill_audit` now reports `front_door_bootstrap_delay` when the assistant reads the front-door skill but waits too long before invoking the runtime.
- `session_skill_audit` now reports `large_output_reasoning_delay` when oversized raw command output is followed by a long reasoning stall.
- `request_classifier` now treats KH UAF/front-door/plugin-cache diagnosis prompts as software/runtime work before generic diagnostic domain matching.

## Regression Evidence

- `python -B -m unittest tests.test_session_skill_audit tests.test_request_classifier`
  - Result: 109 tests passed.
- `python -B -m src.skills.uaf_skill_catalog --check`
  - Result: 40 valid skills, 0 invalid skills.
- `python -B -m src.skills.uaf_skill_quality`
  - Result: quality gate passed, 40 valid skills, lowest score 9.3.
- Actual session audit for `019eb446-e275-7880-b69f-84774dec5add` detects:
  - `front_door_bootstrap_delay`
  - `large_output_reasoning_delay`
- Repo front-door classification for a KH UAF diagnosis prompt routes to `software`, not `medical`.

## Operational Notes

- This fix cannot force an already-running Codex session to reload a newer plugin cache. Users must upgrade KH UAF and open a fresh session before judging blind automatic intake against the new version.
- Marketplace wrapper `main` is version-bumped separately; the marketplace descriptor still points the plugin source at `codex-runtime`.
