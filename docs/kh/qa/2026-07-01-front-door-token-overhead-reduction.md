# KH Front-Door Token Overhead Reduction

Date: 2026-07-01

## Problem

Installed KH UAF 2.9.100 reduced command/log payloads, but the front-door `--summary`
output itself became a token overhead source. Short requests generated multi-kilobyte
JSON because compact routing still emitted verbose skill status notes, execution
authorization text, required action paragraphs, and full token optimizer telemetry.

## Installed Cache Baseline

Measured against installed cache `2.9.100`:

| Scenario | Summary bytes | Estimated tokens | Notes |
|---|---:|---:|---|
| Light question | 9,130 | 2,283 | direct route |
| Current token-overhead question | 9,615 | 2,404 | direct route |
| SQL formatting route | 10,957 | 2,739 | sql-formatting controller |
| Heavy workflow route | 24,427 | 6,107 | KH role DAG |

The skill arrays were not the dominant cost. The largest fields were
`token_optimizer_decision`, `token_optimizer_gate`, `token_optimizer_lifecycle`,
`skill_status_summary`, `execution_authorization`, and `required_next_actions`.

## Fix

- Kept legacy detailed summary under `--verbose-summary`.
- Changed CLI `--summary` to emit compact one-line JSON.
- Added `to_compact_summary_dict()` for CLI intake output.
- Removed repeated token optimizer telemetry from compact output.
- Reduced `skill_status_summary` to aggregate counts in compact output.
- Suppressed generic `required_next_actions` for light/direct requests.
- Kept full details available through non-summary output and `--verbose-summary`.

## Local Source Result

Measured against local 2.9.101 source after the patch:

| Scenario | Summary bytes | Estimated tokens | Reduction |
|---|---:|---:|---:|
| Light question | 2,649 | 662 | 71.0% |
| Current token-overhead question | 2,673 | 668 | 72.2% |
| SQL formatting route | 3,701 | 925 | 66.2% |
| Heavy workflow route | 6,739 | 1,685 | 72.4% |

## Ultra-Compact Follow-Up

Measured against local 2.9.102 source after reducing `--summary` to a routing
signal rather than an evidence report:

| Scenario | Prompt tokens | 2.9.100 summary tokens | 2.9.101 compact tokens | 2.9.102 ultra-compact tokens | Delta vs 2.9.101 |
|---|---:|---:|---:|---:|---:|
| Light question | 3 | 2,297 | 663 | 106 | -84.0% |
| Current token-overhead question | 9 | 2,418 | 669 | 106 | -84.2% |
| Short rewrite | 14 | 2,630 | 663 | 174 | -73.8% |
| SQL formatting | 19 | 2,753 | 926 | 179 | -80.7% |
| Inventory dashboard direction | 24 | 3,739 | 1,310 | 174 | -86.7% |
| Heavy implementation request | 26 | 6,121 | 1,685 | 205 | -87.8% |

The ultra-compact payload keeps only classification, plugin route, execution gate,
immediate next skill names when required, short next-action codes, skill source
version, and token optimizer status. Token optimizer savings fields are emitted
only when optimization was actually used. Full skill lists, long gate reasons,
status summaries, and detailed token telemetry remain available through
`--verbose-summary` and full JSON output.

Reviewer QA also measured an English inline rewrite prompt at 106-107 estimated
tokens because that exact request is now classified as `light/direct_answer`.
The table's short-rewrite row uses the Korean rewrite prompt above, which still
routes through the medium lightweight skill gate and therefore costs more.
Medium rows include `execution_authorization.status=blocked_by_pending_immediate_skill_gate`
so hosts cannot mistake `execution_gate.can_execute=true` for permission to skip
immediate selected skills.

`tests.test_kh_front_door` now includes an ultra-compact token budget regression
test so representative light, SQL, and heavy-preflight summaries fail if they
creep back toward verbose output size.

## Regression Found During Subagent QA

The installed 2.9.100 cache also over-routed this short request:

`Rewrite this sentence: The report is ready for review.`

It was classified as `medium/general/skill_read` with a pending
`workflow-usability-harness`. The local fix classifies short inline rewrite and
rephrase requests as `light/general/direct_answer`.

## Verification

- `python -B -m unittest tests.test_kh_front_door tests.test_kh_front_door_always_on -q`
  passed: 55 tests.
- Targeted request-classifier checks passed for short inline rewrite/rephrase cases.
- `python -B -m unittest tests.test_request_classifier tests.test_plugin_composition_policy tests.test_kh_front_door tests.test_kh_front_door_always_on tests.test_sql_formatting_style_harness -q`
  passed: 213 tests.
- `python -B -m unittest discover -s tests -p "test_*.py" -q`
  passed: 786 tests.
- `python -B -m src.skills.uaf_skill_catalog --check`
  passed: 41 valid / 0 invalid.
- `python -B -m src.skills.uaf_skill_quality --summary`
  passed: 41 valid / 0 invalid, lowest quality score 9.3.
- Subagent read-only QA confirmed local 2.9.101 source keeps short rewrite/rephrase
  requests on `light/general/direct_answer`, keeps vague dashboard requests blocked
  for brainstorming, keeps SQL formatting routed to `sql-formatting`, and preserves
  strict exit code 3 for blocked compact summaries.

## Remaining Deployment State

Source manifests are bumped to `2.9.102`. Installed Codex marketplace cache remains
behind until the user upgrades the marketplace entry after this branch is pushed.
`python -B -m src.orchestration.plugin_install_audit --summary` may therefore report
`attention_required` until the installed cache catches up.

## 2.9.103 Opt-In Micro Summary

Reviewer pass before this patch agreed not to compress default `--summary` further:
those fields are still needed for audit and debugging. Instead, `--micro-summary`
is added as an opt-in machine-only packet for hard token budgets.

Measured against local 2.9.103 source:

| Scenario | 2.9.102 ultra-compact tokens | 2.9.103 micro-summary tokens | Reduction |
|---|---:|---:|---:|
| Light question | 108 | 51 | 52.8% |
| SQL formatting route | 181 | 75 | 58.6% |
| Heavy implementation preflight | 207 | 86 | 58.5% |

Micro schema is versioned with `m=kh_fd_micro` and `v=1`. Its short keys map to
the default summary as follows: `s` -> `front_door_status`, `cls.c` ->
classification complexity, `cls.x` -> recommended execution, `r` -> plugin
route, `g` -> execution gate, `auth` -> execution authorization, `next` ->
immediate next skills, `act` -> required next action codes, `t` -> token
optimizer status/reason, and `src` -> skill source type/version.
Missing `auth` means no stop or pending immediate-skill gate. Missing `next` or
`act` means there are no immediate next skills or required action codes to carry
in the micro packet.

Default `--summary` remains the recommended interactive host output. The micro
packet is for host-to-host routing where the consumer already knows the schema.
Regression tests now enforce both default summary budgets and micro-summary
budgets. Repo-local source identity also reads `.codex-plugin/plugin.json` so
the summary reports the source manifest version instead of a blank version.
