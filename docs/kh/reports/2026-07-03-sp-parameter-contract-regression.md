# SP Parameter Contract Regression Fix

Date: 2026-07-03
Branch: `codex-runtime`
Version: `2.9.118`

## Problem

PB-to-C# migration output could generate stored procedures with helper/calculation values declared as procedure parameters instead of local `DECLARE` variables. The observed failure pattern exposed derived values such as `@YYYY`, `@MM`, `@BASYYYY`, and `@LASTDT` as parameters and wrapped generated date assignments in `IF ISNULL(...)` or direct `IF @GIJUNDT <> '' SET @YYYY = ...` guard blocks.

This violated the KH C#/SP style contract:

- C# caller values are procedure parameters.
- SP-internal helper/calculation values are local variables.
- Internal values use `DECLARE` plus `SET`, not generated procedure parameters.

## Changes

- Generalized `verify_pb_migration_sp_generation_contract` so generated SP signatures can be checked against matched C# caller `DbParameter` evidence.
- Added `non_caller_procedure_parameter_detected` for parameters not sent by the matched C# caller.
- Added date-helper guards for `ALTER PROCEDURE`, parenthesized `IF (ISNULL(...))`, direct `IF @GIJUNDT <> '' SET @YYYY = ...`, and broader SQL parameter types including user-defined type tokens.
- Updated PB-to-C# migration skill instructions, KH SP style reference, usage reference, author-tagged baseline, and migration checklist.
- Added regression tests for blocked generated patterns and allowed local `DECLARE`/`SET` patterns.

## Subagent Review Evidence

Two read-only reviewer passes were used.

- First reviewer found `ALTER PROCEDURE`, parenthesized `IF ISNULL`, and direct `IF @GIJUNDT <> ''` bypass risks.
- Second reviewer confirmed the first fixes and found two remaining bypasses: narrow date assignment matching and narrow SQL type extraction.
- Both bypasses were then patched and covered by tests/probes.

## Verification

- `python -B -m unittest tests.test_pb_to_csharp_migration_harness -q`: 74 tests passed.
- Direct probe `IF @GIJUNDT <> '' SET @YYYY = ...`: blocked by `generated_if_wrapped_date_set_block_detected`.
- Direct probe extra non-caller parameters with `UNIQUEIDENTIFIER`, `DATETIME2`, and user-defined type shape: blocked by `non_caller_procedure_parameter_detected`.
- `python skills\pb_to_csharp_migration_harness\scripts\smoke_check.py`: passed.
- `python -m src.skills.uaf_skill_catalog --check`: 42 valid / 0 invalid.
- `git diff --check`: no whitespace errors.

## Token Optimizer Status

`passthrough`: SQL/SP/C#/harness contract text was source-of-truth content and was not compressed.
