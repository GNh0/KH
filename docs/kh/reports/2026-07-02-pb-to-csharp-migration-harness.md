# PB-to-C# Migration Harness Release Evidence

Date: 2026-07-02
Branch: `codex-runtime`
Version: `2.9.113`

## Purpose

Add a packaged KH UAF harness for PowerBuilder/PBL/SRU/SRW/SRD/DataWindow/GWERP to target-project C# WinForms/DevExpress and SQL Server SELECT/SAVE stored procedure migration.

The harness must work without local host assets. It uses bundled references when `PblScripter`, GWERP sources, target C# samples, `DataWindowToXml.html`, live DB access, or MCP access are absent.

## Evidence Sources

- Prior GWERP/PB memory: PBL export, PB7 runtime PATH, SRU/SRW/SRD trace order, `sale_001.pbl`, `saord_001.sru`, `w_copy.srw`, `maot_001.pbl`, and `maot_003.sru`.
- Prior target-project C# samples: `CallViewQuery`, `CallProc`, `SelectType`, `DataTableToXml`, `SetModified`, DevExpress binding, and SQL style constraints. TY/C_KONE110 is treated as sample evidence only when that is the named target project.
- Attached `DataWindowToXml.html`: narrow SRD `column=(...) name=...` to DevExpress GridView XML behavior.
- Host-local `sql-formatting` skill contract: formatting style is delegated to that formatter and verified by KH, not replaced by this harness.

## Implemented Runtime Surface

- New skill folder: `skills/pb_to_csharp_migration_harness/`
- New Python module: `src.skills.pb_to_csharp_migration`
- New runnable demo: `skills/pb_to_csharp_migration_harness/scripts/demo.py`
- New smoke check: `skills/pb_to_csharp_migration_harness/scripts/smoke_check.py`
- New tests: `tests/test_pb_to_csharp_migration_harness.py`
- Catalog, quality gate, demo scenario, front-door routing, plugin manifests, and README files updated.

## 2.9.105 Follow-up Refinement

After installing and rechecking 2.9.104, the route correctly selected `pb-to-csharp-migration-harness` for "PB source absent but old behavior is described" prompts. The remaining gap was internal evidence precision: the runtime collapsed that case into `standalone`.

2.9.105 adds a separate `described-behavior` migration mode:

- `standalone`: no source and no reliable behavior description.
- `described-behavior`: no PB source, but the user described the old PB screen/workflow; rebuild as inferred requirements and mark source parity as unverified.
- `pasted-source`: pasted SRU/SRW/SRD/C#/SQL exists and is authoritative.
- `partial-reference`: some exported PB, converter, C# sample, SP text, or DB evidence exists.
- `full-reference`: exported PB source, C# samples, packaged style references, and optional DB verification exist.

The plan output now includes `confirmed vs inferred behavior map` so C# and SP work generated from user-described behavior does not look like verified PB source parity.

2.9.105 also fixes the control baseline problem:

- Target-project/custom controls are selected first.
- DevExpress controls are fallback level 1.
- WinForms basic controls are fallback level 2.
- KoneLib/TY controls are not global defaults; they are selected only when the current target project exposes them or the user explicitly asks for them.
- Runtime evidence now includes a `control_stack` / control fallback map.

## Subagent Review

Veteran PB/DataWindow analyst identified reusable GWERP/PBL export and DataWindow mapping behavior.

Veteran C#/SP reviewer identified the target-project save/select contracts and SQL formatting boundaries.

Veteran skill/harness reviewer initially blocked release on two issues:

- DataWindow parsing matched `name=` inside `dbname=`.
- PB migration harness was included in the shared complex extraction bundle and could over-route unrelated non-PB requests.

Both blockers were fixed:

- `DATAWINDOW_NAME_PATTERN` now avoids matching `dbname=`.
- `pb-to-csharp-migration-harness` is added only by the PB migration-specific route through `extra_harnesses`.
- Tests now cover `dbname` before `name` and a non-PB stored-procedure/report-image/bound-column prompt that must not route to the PB harness.
- Tests now cover `described-behavior` mode and require the migration plan to expose `confirmed vs inferred behavior map`.
- Tests now cover target-project/custom control selection, DevExpress fallback, WinForms fallback, and KoneLib-as-target-inventory rather than KoneLib-as-global-baseline.

## C_KONE110_codex Sandbox Check

Created a non-integrated sandbox under:

`C:\Users\KONEIT\Desktop\Source\TY\C_KONE110_codex\Programs\99.System\Konesystem.PBMigrationSandbox_20260702`

The sandbox does not modify the solution or existing project files. It proves the harness can inspect a target project, detect that `KoneLib.Controls.u_GridControl`, `u_TextEdit`, `u_Label`, `u_GroupControl`, `u_Panel`, and `u_TabControl` are available in that target checkout, and select them as `target-project` controls. If those files were absent, the same runtime policy would fall back to DevExpress and then WinForms basics.

Generated sandbox files:

- `PBMIG000.cs`
- `PBMIG000.Designer.cs`
- `control_fallback.json`
- `migration_plan.json`
- `srd_layouts.json`
- `Artifacts/d_asqc_205_print3_1.grid.xml`
- `Artifacts/d_partgb_1.grid.xml`
- `Artifacts/d_quality_507_c2.grid.xml`
- `Sql/sp_PBMIG000_SELECT.sql`
- `Sql/sp_PBMIG000_SAVE.sql`

Observed SRD mapping:

- `d_asqc_205_print3_1.srd`: `ASNUM`
- `d_partgb_1.srd`: `PARTGB`, `PARTCD`, `PARTNM`
- `d_quality_507_c2.srd`: `A`

QA/QC review found no release-blocking failures after the focused runtime, catalog, demo, and manifest checks.

## Verification

Passed:

- `python -B skills\pb_to_csharp_migration_harness\scripts\smoke_check.py`
- `python -B -m unittest tests.test_pb_to_csharp_migration_harness`
- `python -B -m unittest tests.test_request_classifier tests.test_kh_front_door tests.test_pb_to_csharp_migration_harness`
- `python -B -m src.skills.uaf_skill_catalog --check`
- `python -B -m src.skills.uaf_skill_quality`
- `python -B -m unittest tests.test_skill_demos tests.test_uaf_skill_catalog tests.test_uaf_skill_quality`
- `python -B -m unittest tests.test_request_classifier`
- `python -B -m unittest tests.test_kh_front_door`
- `python -B -m json.tool plugin.json`
- `python -B -m json.tool .codex-plugin\plugin.json`
- `python -B -m json.tool .agents\plugins\kh-uaf\plugin.json`

Observed quality gate:

- `total_skills`: 42
- `min_score`: 9.3
- `low_quality`: []

## 2.9.107 DataWindow Grid Naming And Caption Refinement

2.9.107 tightens the DataWindow-to-C# grid contract after a live migration review found that the initial scaffold still left important Designer conventions implicit.

Added runtime behavior:

- visual `column(...)` entries are preferred over `table(column=...)` declaration order when layout coordinates exist;
- PB `text(...)` captions are matched to DataWindow columns by position, including the common `header` caption + `detail` column layout;
- generated column names follow the target C# conventions: `colList_<COLUMN>`, `colDetail_<COLUMN>`, `col<TABLE>_<COLUMN>`, or `col<PURPOSE>_<COLUMN>`;
- generated grid/view names follow the paired conventions: `grdList/gvwList`, `grdDetail/gvwDetail`, `grd<TABLE>/gvw<TABLE>`, or `grd<PURPOSE>/gvw<PURPOSE>`;
- business-purpose suffixes such as `POR`, `BOM`, `ITEM`, and `REQ` are supported when table naming is ambiguous;
- raw DataWindowToXml XML generation still defaults to `gridView1`, while KH target-layout generation passes the resolved C# view name such as `gvwList`.

Applied verification on `d_ba_item3_get.srd`:

- field order: `AS_ITEMCD`, `AS_ITEMNM`;
- matched captions: `코드`, `품명`;
- C# grid names: `grdList`, `gvwList`;
- C# column names: `colList_AS_ITEMCD`, `colList_AS_ITEMNM`;
- DataWindowToXml OptionsView defaults preserved, including `ShowGroupPanel=false`.

Generated sample project verification:

- `C:\Users\KONEIT\Desktop\Source\TY\C_KONE110_codex\Programs\99.System\KoneSystem.SYS\PBMigrationAgentTest_20260702_115825\PBMIG_D_BA_ITEM3_GET.Designer.cs`
- `C:\Users\KONEIT\Desktop\Source\TY\C_KONE110_codex\Programs\99.System\KoneSystem.SYS\PBMigrationAgentTest_20260702_115825\layout\PBMIG_D_BA_ITEM3_GET_datawindow.xml`
- `C:\Users\KONEIT\Desktop\Source\TY\C_KONE110_codex\Programs\99.System\KoneSystem.SYS\PBMigrationAgentTest_20260702_115825\evidence\verification.json`

The sample project builds successfully. Remaining compiler warnings are pre-existing warnings in `CR100130.cs`, `CR100140.cs`, `SystemUserSearch.cs`, and `SystemCustList.cs`, not PBMIG compile failures.

Final 2.9.107 regression evidence:

- `python -m unittest tests.test_pb_to_csharp_migration_harness tests.test_plugin_packaging tests.test_uaf_skill_audit tests.test_session_skill_audit tests.test_superpowers_replacement_layer`: 164 tests passed.
- `python -m unittest tests.test_interactive_side_evaluator tests.test_pb_to_csharp_migration_harness tests.test_plugin_packaging tests.test_uaf_skill_audit tests.test_session_skill_audit tests.test_superpowers_replacement_layer`: 172 tests passed.
- `python -m src.orchestration.interactive_side_evaluator --summary --skills`: 42/42 packaged skills covered, `unexpected_failures=[]`.
- `python -m src.skills.uaf_skill_catalog --check`: 42 valid skills, 0 invalid.
- `python skills\pb_to_csharp_migration_harness\scripts\smoke_check.py`: all implementation targets resolved.
- `python skills\pb_to_csharp_migration_harness\scripts\demo.py --output-dir <tmp>`: success and blocked demo cases produced valid contract-shaped evidence.
- `python -m unittest discover -s tests -p "test_*.py" -v`: 813 tests passed.
- `MSBuild.exe ...\Konesystem.SYS.csproj /t:Build /p:Configuration=Debug /nologo /v:minimal`: build passed.

The full regression initially exposed a SIDE catalog coverage gap: `pb-to-csharp-migration-harness` was present in the package catalog but absent from `default_skill_side_turns()`. The evaluator now includes a PowerBuilder/DataWindow/C# migration SIDE case so all packaged skills are covered by the default SIDE transcript check.

Subagent review evidence:

- veteran skill/harness code review: PASS, no blocking findings after header/detail caption matching and raw-vs-target GridView naming were fixed.
- veteran QA/QC review: PASS, Designer/XML/evidence JSON match captions, `colList_*`, `grdList/gvwList`, DataWindowToXml defaults, and the integrated sample `sandbox` path.

## Token Optimizer Handling

## 2.9.108 Detail Form Layout And Binding Refinement

2.9.108 adds a detail-entry form layout contract for PB-to-C# migration work.

Added runtime behavior:

- `build_detail_form_layout_plan` produces SA100100-style aligned label/editor pairs in fixed rows and columns;
- PB or source order and captions are preserved, but PB pixel coordinates are not copied blindly unless exact visual parity is requested;
- generated detail editors include `field_name`, target-style control name, bounds, and `BindingField = "<FIELD>"` assignment evidence;
- target project control names still override generated fallback names;
- packaged fallback names follow observed target style such as `txtITEMNM`, `btnITEMCD`, `cboITEMACNT`, `SpinQTY`, `ymdORDDT`, `ChkUSEYN`, and `memoREMARK`.

This refinement addresses detail controls such as LabelControl, TextEdit, SpinEdit, ButtonEdit, DateEdit, LookUpEdit, CheckEdit, and MemoEdit. It keeps grid migration separate from detail-entry panel migration.

## 2.9.109 Detail Control Naming And Tab Order Refinement

2.9.109 tightens the detail-control and container naming contract after a full target-project naming audit.

Observed target-project evidence from `C:\Users\KONEIT\Desktop\Source\TY\C_KONE110_codex\Programs`:

- `DateEdit`: standard screen prefix is `ymd`, for example `ymdORDDT`, `ymdFRDT`, and `ymdTODT`;
- `Panel/u_Panel`: common container prefixes are `pn` and legacy `pan`, with packaged fallback set to `pn`, for example `pnMaster`, `pnDetail`, and `pnGridList`;
- screen input fallbacks: `txtFIELD`, `btnFIELD`, `cboFIELD`, `SpinFIELD`, `ymdFIELD`, `ChkFIELD`, and `memoFIELD`;
- repository-item editors stay separate: `rpsbtn*`, `rpscbo*`, `rpsSpin*`, and `rpsChk*` are not normal detail-panel input names;
- containers use `lbl`, `pn`, `grp`, `grd/gvw`, `treeList`, and `tab` fallback prefixes while preserving existing target names first.

Runtime changes:

- `build_csharp_control_name` now centralizes fallback control-name generation;
- `build_detail_form_layout_plan` now emits `tab_index` and `tab_index_code` in left-to-right, top-to-bottom input order;
- control-stack fallback detection now covers DateEdit, SpinEdit, ButtonEdit, combo/lookup, MemoEdit, CheckEdit, and TreeList in addition to grid/text/label/group/panel/tab.

## 2.9.110 Designer Property, Grid Column, And SP Evidence Refinement

2.9.110 fixes a follow-up issue found during the `SA900100` migration review: the harness had naming and TabIndex rules, but it did not yet preserve real C# Designer property evidence or block grid/SP generation patterns that looked valid syntactically but did not match the target style.

Added runtime behavior:

- `extract_csharp_designer_control_specs` extracts target Designer controls, types, parent/child containment, `BindingField`, `FieldName`, caption/text, `TabIndex`, `Location`, `Size`, `Properties.*`, custom flags such as `_isAllowBlank`, collection `AddRange` calls, `MainView`, `ViewCollection`, and GridView/GridControl links.
- C# string extraction preserves Korean text without mojibake.
- `build_csharp_grid_column_designer_plan` emits explicit Designer-style `GridColumn` declarations, `Columns.AddRange`, `FieldName`, `Caption`, `Name`, `Visible`, and `VisibleIndex` assignments with `colList_*`, `colDetail_*`, `col<TABLE>_*`, or `col<PURPOSE>_*` names.
- `verify_migration_generated_csharp_style` blocks default runtime grid helper patterns: `AddGridColumn(...)`, `view.Columns.AddField(...)`, and `column.Name = view.Name + "_" + fieldName`.
- `verify_pb_migration_sp_generation_contract` blocks completed migration SP claims when no PB/DataWindow SQL, verified existing SP definition evidence, pasted SQL, DB schema evidence, or explicit user-approved inferred-draft marker exists. It also blocks missing `@WORKTYPE` and default CTE/#temp/MERGE/NOT EXISTS introductions.

Regression evidence:

- `python -B -m unittest tests.test_pb_to_csharp_migration_harness`: 28 tests passed.
- New regression cases cover target Designer property extraction, Korean string preservation, runtime grid helper blocking, explicit Designer GridColumn generation, missing SP text blocking, and unbacked generated SP blocking.

Subagent review evidence:

- veteran C#/DevExpress review identified missing Designer property extraction and flagged runtime `AddGridColumn`/`Columns.AddField`/`view.Name + "_" + fieldName` as style violations.
- veteran SQL/SP review identified that a C# SP call signature is not enough evidence for a completed `sp_SA900100_SELECT` body and recommended explicit SP generation evidence gates.

For PB/C#/SQL source text, token optimizer status should normally be `passthrough` because source code, business literals, Korean text, and SQL contracts are source-of-truth content. Command output may still be filtered by `command-output-harness` when it is noisy and facts can be preserved.

## Remaining Risk

The harness is a migration planning and verification scaffold. It does not prove semantic parity without actual PB source, target C# files, SP definitions, or DB-backed verification. When local artifacts are absent, it must label output as standalone or fallback mode and avoid claiming full migration parity.


## 2026-07-02 Follow-up: Numeric Grid Columns And SP Fallbacks

- User feedback showed generated SA900100 numeric grid columns still used GridColumn `DisplayFormat` instead of repository Spin controls. The harness now treats AMT/QTY/UNP/WGT GridColumns as requiring `RepositoryItemSpinEdit` via `ColumnEdit` and blocks GridColumn `DisplayFormat`-only output.
- `build_csharp_grid_column_designer_plan` now emits Spin repository declarations, registration, initialization, and ColumnEdit mappings for numeric generated columns.
- `verify_pb_migration_sp_generation_contract` now rejects unstructured `source_evidence=True`; complete SP output needs structured evidence such as `pb_srd_sql`, verified `existing_sp` definition evidence, `pasted_sql`, `db_schema`, or an approved inferred draft marker.
- The same verifier now rejects source-unbacked `SELECT TOP 0/SELECT TOP (0) CAST/CONVERT/TRY_CONVERT(...)` schema-only fallback blocks and `;WITH` CTE introductions by default.
- Regression coverage now includes runtime `new GridColumn` + `Columns.Add`, numeric DisplayFormat-only output, Spin ColumnEdit success, structured SP evidence, `;WITH`, and schema-only fallback blocks.

## 2.9.111 Follow-up: Author-Tagged C_KONE110 Baseline And SA900100 Repair

User feedback clarified that "analyze every program" means no omission from the source dataset used to define the style baseline, not simply checking a few representative examples.

Evidence added:

- `author-tagged-style-baseline.md` records 61 `C_KONE110` procedures whose definitions contain `KH`, `근호`, or `장근호` and normalizes them into 40 program keys.
- 39 program keys were mapped to C# source-bearing programs under `C_KONE110_1`; `SA116T` is recorded as SP-only/unmapped local evidence.
- The baseline records that author-tagged C# samples use direct procedure-call/local-variable flow and do not use generated `RetrieveContext`, `GetEditValue`, or `GetColumnText` helpers.
- The SP baseline records 0/61 occurrences of `SET @WORKTYPE = ISNULL(...)` and 0/61 occurrences of `@WORKTYPE VARCHAR(20) = ''`.

Runtime gates added:

- `verify_migration_generated_csharp_style` now blocks generated internal DTO/context classes, generic value/column helper methods, and `txt*NM` fields generated as `u_DateEdit`.
- Follow-up QA broadened helper detection so `GetEditValue(...)` and `GetColumnText(...)` are blocked regardless of access modifier, `static`, or return type. `SetVisibleIndex(...)` helper generation is also blocked.
- `verify_pb_migration_sp_generation_contract` now blocks generated empty-string `@WORKTYPE` defaults, wildcard parameter defaults, business selector literal defaults, and generated CASE/ISNULL parameter normalization blocks.
- `ty-csharp-style.md`, `kh-sp-style.md`, `usage.md`, and `SKILL.md` all point C_KONE110/KH-style work back to the full author-tagged baseline instead of a few examples.

SA900100 applied fixes:

- `SA900100.cs` no longer contains `RetrieveContext`, `GetEditValue`, `GetColumnText`, or `SetVisibleIndex` helper flow.
- `CallSelectProcedure` now builds retrieve parameters directly near the stored-procedure call.
- `txtCUSTNM` is `u_TextEdit`, not `u_DateEdit`.
- `PRNTITEMNM` runtime caption is restored to `부문` / `제품명`.
- `verify_migration_generated_csharp_style` on `SA900100.cs` + `SA900100.Designer.cs`: `issue_count=0`.

DB applied fixes:

- Live MCP DB object: `C_KONE110.dbo.SP_SA900100_SELECT`.
- Definition was altered to `CREATE PROCEDURE [dbo].[sp_SA900100_SELECT]` text with all listed parameters defaulting to `NULL`.
- Removed generated `SET @WORKTYPE = ISNULL(...)` and generated CASE/ISNULL parameter normalization block.
- Added `SET ARITHABORT ON;`.
- Post-change DB checks: bad `@WORKTYPE=''` default 0, bad wildcard/default selector defaults 0, bad normalization block 0, `SET ARITHABORT ON` 1.
- No-data execution checks passed for both `LIST` and `DETAIL` branches.

Verification evidence:

- `python -B skills\pb_to_csharp_migration_harness\scripts\smoke_check.py`: passed.
- `python -B -m unittest tests.test_pb_to_csharp_migration_harness`: 39 tests passed.
- `python -B -m src.skills.uaf_skill_catalog --check`: 42 valid skills, 0 invalid.

## 2.9.112 Follow-up: Stored Procedure Metadata Header Contract

User feedback clarified that C_KONE110/KH-style stored procedures must keep the standard metadata comment block immediately above `CREATE/ALTER PROCEDURE`, even when the author value itself follows target evidence.

Required shape:

```sql
-- =============================================
-- AUTHOR:      <author>
-- CREATE DATE: <yyyy-mm-dd>
-- DESCRIPTION: <description>
-- =============================================
ALTER PROCEDURE [DBO].[SP_SAMPLE_SELECT]
```

Runtime gate added:

- `verify_pb_migration_sp_generation_contract` now blocks generated procedure output without that metadata block via `missing_sp_metadata_header`.
- `kh-sp-style.md`, `author-tagged-style-baseline.md`, `usage.md`, and `SKILL.md` now state that the header belongs directly above `CREATE/ALTER PROCEDURE`.

DB applied fix:

- Live MCP DB object `C_KONE110.dbo.SP_SA900100_SELECT` was updated so the module definition begins with the standard metadata header above the stored procedure declaration.

## 2.9.113 Follow-up: Program-Specific DESCRIPTION And SA900100 C# Style Guard

User feedback clarified two remaining gaps:

- The SP metadata `DESCRIPTION` must match the target program/screen. Reusing another program's description such as `총괄조회 조회` on unrelated procedures is blocked.
- The C# style gate still allowed generated helper wrappers and runtime month-column layout patterns that did not match the author-tagged C_KONE110/KH baseline.

Runtime gates added:

- `verify_pb_migration_sp_generation_contract` now captures the metadata `DESCRIPTION`, extracts the target procedure name, rejects placeholder/sample descriptions, and blocks mismatch against structured source evidence such as `program_description`, `screen_name`, `program_name`, or `description`.
- `verify_migration_generated_csharp_style` now blocks generated `SetDefaultSearchValues`, `ApplyListColumnLayout`, `GetBasisYear`, `GetCustomerLike`, `ValidateSearch`, runtime monthly `VisibleIndex` loops, `PopCustFrm` `DialogResult.Yes || DialogResult.OK` broadening without evidence, and mojibake Korean literals.
- `ty-csharp-style.md`, `author-tagged-style-baseline.md`, and `SKILL.md` now document these rejected generated patterns.

SA900100 local applied fix:

- Target file: `C:\Users\KONEIT\Desktop\Source\TY\C_KONE110_1\Programs\20.영업(SA)\Konesystem.SA02\SA900100.cs`.
- Removed generated helper wrappers and mojibake validation messages.
- Reworked search/default/popup/detail flow into the existing C_KONE110 screen shape: direct `Load`, `SearchCommand`, `ClearCommand`, `CallSelectProcedure`, `FocusedRowChanged`, and explicit column visibility adjustment.
- Kept Designer-level grid columns and monthly amount order; no runtime monthly `VisibleIndex` loop remains.
- `PopCustFrm` now accepts the existing popup contract `DialogResult.OK` only.

Verification evidence:

- `python -B -m unittest tests.test_pb_to_csharp_migration_harness`: 40 tests passed.
- `verify_migration_generated_csharp_style` on `SA900100.cs` + `SA900100.Designer.cs`: `issue_count=0`.
- `rg` scan for rejected helper/mojibake patterns in `SA900100.cs` + `SA900100.Designer.cs`: no matches.
- Visual Studio MSBuild 2022 command on `Konesystem.SA02.csproj` with `Configuration=Debug`, `Platform=AnyCPU`: succeeded and produced `Konesystem.SA02.dll`; existing platform warnings remain unrelated.
- `dotnet build --no-restore` was also tried, but .NET SDK build failed before target compilation on existing non-string resource handling in `KoneLib.DevBase`. VS MSBuild is the valid verification path for this legacy project.
