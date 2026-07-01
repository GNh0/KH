# KH UAF Subagent Cache Retest - 2026-07-01

## Scope

This pass retested the installed Codex marketplace cache after `2.9.99` was
installed, using read-only subagents for blind routing, token optimization, and
SQL/plugin-composition behavior.

## Subagent Findings

- Blind routing passed for vague dashboard direction requests: the installed
  front door stopped before implementation and selected brainstorming.
- Short sentence rewrite and concept prompts stayed `light/direct_answer`.
- Token Optimizer was visible as a front-door gate and reported
  `considered_not_needed` with `not_used_reason` when no payload was optimized.
- SQL formatting prompts routed to the host-local `sql-formatting` skill, with
  KH `sql-formatting-style-harness` acting only as verifier.
- Subagents found three follow-up issues:
  - blocked front-door JSON advertised strict exit code `3`, while one subagent
    observed process exit `1`;
  - pytest-like logs with single-colon file-line markers needed stronger
    preservation;
  - SQL style harness documentation used stale CLI flag names.

## Main-Controller Follow-Up

- Reproduced installed-cache strict front-door exit locally with PowerShell
  `$LASTEXITCODE=3`; no source patch was required for exit-code behavior.
- Hardened Token Optimizer file-line preservation for
  `path/file.ext:line` markers across common source file extensions.
- Added regression coverage for noisy pytest output containing
  `tests/test_billing.py:42`.
- Updated SQL style harness instructions to use actual CLI flags:
  `--original` and `--formatted`.
- Bumped source package manifests to `2.9.100` so the next marketplace upgrade
  creates an unambiguous cache refresh target.

## Verification

- `python -B -m unittest tests.test_command_output_runtime tests.test_sql_formatting_style_harness -q`
  passed: `76` tests.

## Remaining Release Step

Commit and push this follow-up, then upgrade KH UAF in Codex again and verify
the installed cache advances to `2.9.100`.
