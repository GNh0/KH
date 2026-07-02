# PB To C# Migration Minimal Workflow

## Scenario

A user asks: "Migrate this PowerBuilder order copy screen into the target C# project and SP style. I may not have PblScripter or the old GWERP source on this machine."

The correct behavior is not to fail because local tools are absent. The harness should start in standalone, described-behavior, or pasted-source mode, use bundled references, and clearly state which claims need real PB or DB evidence.

## Expected steps

1. Run KH intake first and select `pb-to-csharp-migration-harness` for the migration slice.
2. Record `token_optimizer_status=passthrough` for PB/C#/SQL source text.
3. Call `build_pb_to_csharp_migration_plan` with the objective and available evidence state.
4. If SRD text is present, call `build_datawindow_grid_layout` or `extract_datawindow_column_specs` plus `generate_devexpress_grid_xml`.
   The output should preserve visual column order, matched DataWindow captions, C# column names such as `colList_<COLUMN>`, `colDetail_<COLUMN>`, `col<TABLE>_<COLUMN>`, or `col<PURPOSE>_<COLUMN>`, and grid names such as `grdList/gvwList`, `grdDetail/gvwDetail`, `grd<TABLE>/gvw<TABLE>`, or `grd<PURPOSE>/gvw<PURPOSE>`.
   When the table name is awkward or ambiguous, use a business purpose suffix such as `POR`, `BOM`, `ITEM`, or `REQ`.
5. If a target `.Designer.cs` or pasted Designer snippet exists, call `extract_csharp_designer_control_specs` before generating/reviewing code. Preserve actual control types, containment, `BindingField`, project-specific flags, `Properties.*`, bounds, captions, `TabIndex`, grid/view links, and collection calls.
6. If the target screen has detail-entry controls, call `build_detail_form_layout_plan` or follow the same SA100100-style rule manually: aligned label/editor pairs, target-style names such as `txtITEMNM`, `btnITEMCD`, `cboITEMACNT`, `SpinQTY`, `ymdORDDT`, `ChkUSEYN`, or `memoREMARK`, plus `BindingField = "<FIELD>"` and left-to-right/top-to-bottom `TabIndex` evidence.
7. If generating grid columns for C#, call `build_csharp_grid_column_designer_plan` and `verify_migration_generated_csharp_style`. The output should use explicit `GridColumn` members, `Columns.AddRange`, and `col*_<FIELD>` names. Runtime `AddGridColumn`, `Columns.AddField`, and `view.Name + "_" + fieldName` helpers are blocked by default.
8. Read only the needed references:
   - `pbl-export-process.md` for PBL export;
   - `powerbuilder-source-analysis.md` for SRU/SRW/SRD tracing;
   - `datawindow-layout-mapping.md` for grid XML;
   - `ty-csharp-style.md` for target C# flow;
   - `kh-sp-style.md` and `sql-formatting-bridge.md` for SP work.
9. Resolve the control stack: target-project/custom controls first, DevExpress second, WinForms basics third.
10. Draft migration guidance that preserves existing target-project method paths and SP result contracts.
11. For generated SELECT/SAVE SP text, call `verify_pb_migration_sp_generation_contract`. A complete SP requires structured PB/DataWindow SQL, verified existing SP definition evidence, pasted SQL, DB schema evidence, or an explicit user-approved inferred-draft marker, and must not include source-unbacked `SELECT TOP 0/SELECT TOP (0) CAST/CONVERT/TRY_CONVERT(...)` schema-only fallback blocks.
12. Use host-local `sql-formatting` for SQL formatting and KH verifier evidence when required.
13. Finish with `migration-output-checklist.md`.

## Expected evidence

- `actual_runtime_path`: `src.skills.pb_to_csharp_migration.build_pb_to_csharp_migration_plan`.
- `HarnessResult.success=true` for a non-empty objective.
- `mode=standalone`, `described-behavior`, `pasted-source`, `partial-reference`, or `full-reference`.
- Confirmed vs inferred behavior is visible when no PB source exists.
- `DataWindow` conversion evidence when SRD columns are available, including captions, C# column names, selected grid names, and table-or-purpose fallback.
- Target Designer extraction evidence when Designer source is available, including control properties and explicit missing-grid-column evidence when columns are absent.
- Grid column generation evidence with explicit `GridColumn` member names and no blocked runtime helper pattern.
- Detail form layout evidence when input controls are generated, including field names, control names, bounds, `BindingField` assignments, and TabIndex order.
- Target C# control fallback map is visible, including selected provider and fallback reason.
- SP generation evidence includes source evidence or an inferred-draft marker, plus forbidden CTE/#temp/MERGE/NOT EXISTS scan.
- SQL text marked as passthrough, not compressed.
- Missing local PBL/C#/DB artifacts listed as blocked or lower-confidence evidence.

## Failure cases

- Claims full PB behavior parity from a PBL file name only.
- Treats DataWindowToXml-compatible output as full layout migration.
- Ignores the existing target-project `CallProc`/`CallViewQuery` path and invents a separate helper.
- Treats TY/C_KONE110, KoneLib, or another sample project as the universal C# baseline.
- Generates grid columns through `AddGridColumn`, `Columns.AddField`, or `view.Name + "_" + fieldName` without target evidence.
- Presents a full SP body as completed from only a C# call signature or grid column list.
- Adds CTEs, `#` temporary tables, `MERGE`, `NOT EXISTS`, or scalar-function rewrites by default.
- Formats SQL without host-local `sql-formatting` or without verifier evidence when proof is requested.
- Creates files in a staging folder instead of the exact requested target path.

## Done criteria

- The migration plan can run without local PblScripter, GWERP, target C# source, converter HTML, or live DB access.
- Available artifacts are used when present, and absent artifacts are not fabricated.
- C# and SP guidance follows target-project evidence first, then packaged C#/KH style references.
- DataWindow mapping is deterministic for SRD columns, matched captions, and target C# grid/column naming.
- Designer extraction, grid column generation, and SP generation all have explicit evidence or blocked assumptions.
- The final response distinguishes proven facts, packaged-style defaults, and unresolved evidence.
