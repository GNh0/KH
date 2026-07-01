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

Source manifests are bumped to `2.9.101`. Installed Codex marketplace cache remains
`2.9.100` until the user upgrades the marketplace entry after this branch is pushed.
`python -B -m src.orchestration.plugin_install_audit --summary` therefore reports
`attention_required`, and `python -B -m src.benchmarks.practical_quality_gate --summary`
reports `release_ready=false` only because installed cache 2.9.100 is behind source
2.9.101. KH-Bench itself passed 8/8 inside that gate.
