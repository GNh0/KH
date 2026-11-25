# KH-Bench Verified SIDE Review

Date: 2026-05-29

## Review Input

An independent SIDE review flagged the first KH-Bench implementation as a useful integration smoke suite, but not yet a SWE-bench-style practical benchmark.

Main findings:

- The initial task runner was self-solving through benchmark-owned scenario functions.
- Pre-fail/post-pass existed mechanically, but several pre-fail checks were absent custom flags rather than failing workspace conditions.
- Several validators trusted `context.custom` metadata emitted by the runner under test.
- Artifact checks did not consistently bind validators to concrete files.
- The score contract existed, but was not strongly guarded by tests.

## Changes Applied

- Added an explicit `KHBaselineCandidateRunner` so the built-in runner is treated as the candidate being evaluated.
- Replaced task `scenario` entries with `candidate_profile`; tests assert `scenario` is not part of the public task schema.
- Removed self-attested validator types from packaged tasks and production validator logic.
- Reworked task validators to read concrete workspace files, runtime artifacts, and report JSON.
- Added task-scoped `UAF_RUNTIME_ROOT` so benchmark state stays inside the clean run root.
- Added tests that reject self-attested validator types in task definitions.
- Added artifact scope checks so returned artifacts must exist under the task workspace or task runtime root.

## Second-Pass Fixes

A second SIDE review found three remaining gaps. These were also addressed:

- `UAF_PROJECT_LOCAL_STATE` is now forced to `0` during each task and restored afterward, so ambient host settings cannot break runtime isolation.
- External candidate runners now receive a sealed public task view. The view excludes validators, expected artifacts, and `candidate_profile`.
- Negative score-contract tests now cover a failing candidate and an infra-error candidate, including unresolved task IDs and zero score handling.

## Current Limit

This benchmark now scores KH UAF baseline execution against fixed practical tasks and provides a sealed task view for alternate candidate runners. It is still not a public SWE-bench replacement because it does not execute arbitrary GitHub issue patches in containerized third-party repositories. The next external-comparison step is to add a real CLI/agent candidate adapter that receives only the public task prompt and workspace, then compare its pass rate with the KH baseline runner.
