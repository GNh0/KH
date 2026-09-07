# KH UAF Routing Regression Fix - 2026-06-30

## Scope

This note records the evidence for the 2.9.89 routing regression fix on the
`codex-runtime` branch.

The fix targets two user-visible failures observed in blind subagent sessions:

1. A new dashboard direction request entered `brainstorming-harness`, but the
   agent inspected the target folder before the first visible brainstorm.
2. A direct SQL formatting request read the host-local `sql-formatting` skill,
   but emitted SQL without KH SQL style verifier evidence.

## Changes

- `kh_front_door.py` now lists target folder existence checks, target folder
  inspection, target write preflight, `Test-Path`, `Get-ChildItem`, `rg`,
  `Get-Content`, and source reads as blocked actions for
  `blocked_until_brainstorming_handoff`.
- `brainstorming-harness` instructions now forbid inspecting even the explicit
  target folder before the first visible brainstorm.
- `session_skill_audit.py` now reports
  `target_folder_inspection_before_brainstorm_handoff` when a session violates
  that gate.
- Direct SQL formatting no longer creates a false `missing_front_door` issue
  for host-local specialist work, but it still requires
  `sql-formatting-style-harness` evidence.
- Failed SQL verifier output no longer counts as successful verifier evidence.
  Emitting SQL after a failed verifier is reported as
  `sql_formatting_style_verifier_failed_before_output`.
- Synthetic `<environment_context>` messages are ignored as user-trigger text
  for front-door-missing audits.

## Subagent Review

Three independent subagents reviewed the patch:

- Veteran skill/harness developer: pass, with recommendation to add a
  post-front-door target-inspection audit.
- QA/QC reviewer: partial pass, P1 gap found for failed SQL verifier evidence.
- Veteran LLM power user: 7/10, must-fix gap found for exact target folder read
  before brainstorm handoff.

Both must-fix gaps were patched and covered by tests.

## Verification

Commands run from `C:\Users\KONEIT\Desktop\Jang\KH`:

```powershell
python -B -m unittest tests.test_session_skill_audit tests.test_kh_front_door tests.test_sql_formatting_style_harness
python -B -m src.skills.uaf_skill_catalog --check
python -B -m unittest tests.test_plugin_packaging tests.test_superpowers_benchmark_alignment tests.test_uaf_skill_catalog tests.test_plugin_composition_policy tests.test_workflow_usability_layer tests.test_skill_demos
python -B -m unittest discover -s tests
git diff --check
```

Results:

- Focused routing and SQL tests: 190 tests OK.
- Packaged skill catalog: 41 valid, 0 invalid.
- Packaging/skillbook/workflow tests: 68 tests OK.
- Full unittest discovery: 740 tests OK.
- `git diff --check`: no whitespace errors; Git reported expected LF-to-CRLF
  working-tree warnings only.

## Real Session Evidence

Re-audited failed session:

- `019f166f-ac89-7bc1-af92-f2067113ce6d`
- Now reports `target_folder_inspection_before_brainstorm_handoff` for
  `Get-ChildItem` on the target folder before brainstorm handoff.

Re-audited SQL session:

- `019f1670-1e33-7562-8881-881975cdc267`
- No longer reports false `always-on-front-door/missing_front_door` caused by
  `<environment_context>`.
- Still reports missing SQL style verifier evidence, which is the intended
  failure.

## Token Optimizer Status

The patch did not change token optimizer behavior. For these focused audits the
runtime status was `considered_not_needed` because the commands and reviewed
outputs were bounded. Session audit still reports the runtime token decision
and reason.

## Remaining Risk

This fix improves runtime instructions and postmortem accountability. It cannot
force a host model to obey the gate if the host ignores plugin instructions, but
the violation is now explicit in front-door output and detectable in session
audit.
