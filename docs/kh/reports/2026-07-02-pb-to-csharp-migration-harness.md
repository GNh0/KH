# PB-to-C# Migration Harness Release Evidence

Date: 2026-07-02
Branch: `codex-runtime`
Version: `2.9.109`

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

For PB/C#/SQL source text, token optimizer status should normally be `passthrough` because source code, business literals, Korean text, and SQL contracts are source-of-truth content. Command output may still be filtered by `command-output-harness` when it is noisy and facts can be preserved.

## Remaining Risk

The harness is a migration planning and verification scaffold. It does not prove semantic parity without actual PB source, target C# files, SP definitions, or DB-backed verification. When local artifacts are absent, it must label output as standalone or fallback mode and avoid claiming full migration parity.
