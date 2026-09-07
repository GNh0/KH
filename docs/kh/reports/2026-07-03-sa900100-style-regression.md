# SA900100 Style Regression Report

## Objective

Block PB-to-C# migration output that still looks generated after author-tagged style verification.

## Trigger

`SA900100.cs` still contained unsupported generated patterns after the previous migration pass:

- `CallSelectProcedure(SelectType.LIST, btnCUSTCD.Text + "%", "%")`
- `if (ymdGIJUN.EditValue == null) ymdGIJUN.SetToDay(0)` in search/procedure paths
- `new DateTime(DateTime.Now.Year, DateTime.Now.Month, 1).AddDays(-1)` and `new DateTime(ymdGIJUN.DateTime.Year - 1, 12, 31)` boundary blocks
- direct `grd*.DataSource = null` resets in a KoneLib-style screen
- C# date parameter shaping such as `@YYYY`, `@MM`, `@BASYYYY`, or `@LASTDT` from `DateTime.Now` / `ymd*.DateTime`
- generated helper naming such as `CallDetailQuery()` for focused-row detail loading

## Root Cause

`verify_migration_generated_csharp_style` only blocked signature defaults, `?? "%"`, null wrappers, DTO/context helpers, and grid/runtime helper patterns. It did not inspect `CallSelectProcedure(...)` call-site wildcard arguments, DateEdit null defaulting, generated DateTime boundary blocks, direct grid null resets, C#-side split date parameters, or generated focused-row helper names.

## Changes

- Added verifier issues:
  - `generated_callselect_inline_wildcard_argument_detected`
  - `generated_dateedit_settoday_null_default_detected`
  - `generated_dateedit_year_or_now_parameter_shaping_detected`
  - `generated_month_end_datetime_block_detected`
  - `generated_year_end_datetime_block_detected`
  - `generated_year_end_string_boundary_detected`
  - `generated_direct_grid_datasource_null_reset_detected`
  - `generated_call_detail_query_helper_detected`
- Added regression coverage for the exact SA900100 leftover pattern.
- Updated PB-to-C# harness references so future agents do not treat these patterns as acceptable C_KONE110/KH style.
- Bumped plugin manifests to `2.9.115`.

## Target Repair

The local target `SA900100.cs` was repaired separately in the user project:

- `LIST` no longer passes inline wildcard arguments.
- `DETAIL` no longer appends `%` at the call site.
- DateEdit null defaulting was removed from the procedure path.
- The explicit `new DateTime(..., 1).AddDays(-1)` / `new DateTime(..., 12, 31)` generated block was removed.
- C# now passes `@GIJUNDT` from `ymdGIJUN.YYYYMMDD()` and does not pass generated `@YYYY`, `@MM`, `@BASYYYY`, or `@LASTDT` parameters.
- Empty list/detail grid resets use `devFnc.InitControl(grd*)` instead of `grd*.DataSource = null`.
- The stored procedure owns wildcard/default/date-boundary shaping from `@GIJUNDT`; the C# screen only passes raw control values.
- The list-focused detail refresh helper was renamed from generated `CallDetailQuery()` to the house-style `fnFocusedRowChanged()`.

## Verification

- `python -B -m unittest tests.test_pb_to_csharp_migration_harness`
- `verify_migration_generated_csharp_style` against repaired `SA900100.cs`
- Forbidden-pattern scan against repaired `SA900100.cs`
- DB parameter/body check for `SP_SA900100_SELECT`

## Remaining Risk

The verifier prevents the known generated patterns, but C# style remains evidence-driven. New C_KONE110/PB migration patterns should still be checked against the author-tagged SP-to-C# baseline and the active target source, not inferred from the generated repair target.
