---
name: pb-to-csharp-migration-harness
description: Use when migrating, analyzing, planning, reviewing, or implementing PowerBuilder, PBL, SRU, SRW, SRD, DataWindow, GWERP, or project-specific workflows into C# WinForms/DevExpress screens and SQL Server SELECT/SAVE stored procedures.
---

# PB To C# Migration Harness

## KH Entry Contract

- Start through `always-on-front-door` for non-trivial migration work before source exploration, memory lookup, target-folder inspection, DB access, file writes, or subagent dispatch.
- If `kh_active_directive=active` was set by an earlier user instruction, treat later work-bearing migration requests as KH-routed even when KH names are omitted.
- Use this harness after intake when the request involves PowerBuilder source, PBL export, DataWindow layout, target-project C# style, SELECT/SAVE stored procedure drafting, or PB-to-C# migration review.
- Treat local PB tools, GWERP source trees, target C# samples, converter HTML, and live DB access as optional evidence, not runtime dependencies.
- Use bundled references as the portable baseline when local evidence is absent.
- Use host-local `sql-formatting` as the SQL formatter when SQL is formatted or generated; this harness owns migration flow and verification expectations.
- Treat PB source, SQL, C# code, Korean literals, comments, and business rules as source-of-truth passthrough content. Do not token-compress them.
- Report this skill as applied only when the migration plan module, DataWindow layout module, reference-guided procedure, smoke script, demo, or explicit passthrough/blocked rationale produced evidence.
- A SKILL.md read, marketplace listing, or `selected_not_executed_skills` entry is not execution evidence.

## Support files

- Read `references/usage.md` before applying this skill to real migration work; it expands trigger boundaries, modes, workflow, evidence, and failure handling.
- Read `references/pbl-export-process.md` when PBL/PblScripter/ORCA/export behavior matters.
- Read `references/powerbuilder-source-analysis.md` when tracing SRU/SRW/SRD event flow, DataWindow SQL, save logic, or PB-vs-SP parity.
- Read `references/datawindow-layout-mapping.md` when converting DataWindow columns or layout into DevExpress/WinForms structure.
- Read `references/ty-csharp-style.md` before drafting or reviewing target C# screen logic; TY/C_KONE110 is a sample style, not a universal baseline.
- Read `references/kh-sp-style.md` before drafting or reviewing SELECT/SAVE stored procedures.
- Read `references/author-tagged-style-baseline.md` when the target is the user's C_KONE110/KH style or when asked to follow KH/Geunho/Jang-Geunho-authored C#/SP style; this file contains the analyzed `author-tagged SP -> program key -> matching C# screen source` baseline and must not be skipped for generated C# or SP work in that style.
- Read `references/author-tagged-program-style-profiles.json` together with the baseline for C_KONE110/KH-style generation or review. It is the portable per-program profile built from 37 matched primary C# and Designer pairs and includes source hashes, base class, method names, SP calls, DbParameter names, grid/view names, BindingField samples, repository controls, and style flags.
- Read `references/sql-formatting-bridge.md` when SQL formatting, scalar function conversion, or verifier composition is involved.
- Read `references/migration-output-checklist.md` before claiming completion or handoff.
- Use `examples/minimal-workflow.md` as the compact success/blocked scenario.
- Run `python scripts/smoke_check.py` to verify support-file wiring and implementation target resolution.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo.

## Workflow

1. Confirm the migration mode:
   - `standalone`: no local PB/C#/DB/converter artifacts available; use bundled references and ask for missing source only when it changes correctness.
   - `described-behavior`: no PB source is available, but the user described the PB screen/workflow; rebuild from inferred requirements and mark source parity as unverified.
   - `pasted-source`: the user pasted SRU/SRW/SRD/C#/SQL; treat pasted text as authoritative.
   - `partial-reference`: some exported PB, converter, C# samples, SP text, or DB access exists.
   - `full-reference`: exported PB source, target C# samples, SP style reference, and optional DB verification are available.
2. Build a `pb-to-csharp` migration plan with `src.skills.pb_to_csharp_migration.build_pb_to_csharp_migration_plan`.
3. If PB assets exist, export or inspect safely:
   - select the export provider in this order: PblScripter or equivalent wrapper, direct ORCA, pre-exported `.sru/.srw/.srd/.srm`, pasted source, described behavior, bundled baseline;
   - when using ORCA directly, match the PB runtime/ORCA version to the PBL lineage, for example PB 7.0 PBL with PB 7.0 ORCA/runtime and PB 12.5 PBL with PB 12.5 ORCA/runtime;
   - list PBL objects first;
   - export named objects into an external output directory;
   - trace `.sru` entrypoints, `.srw` window logic, and linked `.srd` DataWindows;
   - never write exports into the source PBL tree.
4. If only bundled references are available, use the packaged PB export and analysis rules to produce a bounded plan, not a false claim of source parity.
5. Map DataWindow fields/layout:
   - use `src.skills.pb_to_csharp_migration.extract_datawindow_column_specs`, `resolve_csharp_grid_column_prefix`, `resolve_csharp_grid_control_names`, and `generate_devexpress_grid_xml` for DataWindowToXml-compatible grid columns, matched captions, C# grid names, C# column names, and converter GridView defaults;
   - treat that mapping as grid-column scaffolding, not full PB coordinate or control migration;
   - for detail-entry areas, use `build_detail_form_layout_plan` to create SA100100-style clean label/editor rows and columns; preserve source order and captions, but do not copy PB pixel coordinates blindly;
   - detail controls must carry the source `field_name`, target-project-style control name, `BindingField = "<FIELD>"`, and left-to-right/top-to-bottom `TabIndex` assignment evidence;
   - generated detail and container names must follow target evidence first, then packaged fallbacks: `txt`, `btn`, `cbo`, `Spin`, `ymd`, `Chk`, `memo`, `lbl`, `pn`, `grp`, `grd/gvw`, `treeList`, and `tab`;
   - when emitting C# Designer code, mirror `build_datawindow_gridview_designer_defaults` so the generated GridView keeps the converter's group-panel, filter-row, footer, auto-width, even-row, and view-caption defaults.
   - when target C# Designer code is available, use `extract_csharp_designer_control_specs` to preserve actual control types, `BindingField`, `TabIndex`, bounds, containment, `Properties.*`, and collection calls before generating or reviewing new code;
   - when generating grid columns, use explicit GridColumn members and `Columns.AddRange` with `colList_*`, `colDetail_*`, `col<TABLE>_*`, or `col<PURPOSE>_*` names; block default `AddGridColumn`, `Columns.AddField`, and `view.Name + "_" + fieldName` helper patterns unless the existing target screen already proves that style.
6. Resolve the target C# control stack before drafting code:
   - prefer target-project/custom controls such as a project-owned `u_GridControl` when they exist;
   - fall back to DevExpress controls only when the target project has no matching custom control;
   - when DevExpress is present, use the target project's existing references and API surface; do not add NuGet packages, upgrade assemblies, or generate code from the latest DevExpress version by default;
   - fall back to WinForms basic controls when neither target-project controls nor DevExpress are available;
   - record the selected provider and fallback reason in the migration evidence.
7. Draft target C# flow from the style reference:
   - preserve existing method paths such as `CallViewQuery`, `CallProc`, `SelectType`, `DataUtil.DataTableToXml`, `SetModified`, `grd*`, `gvw*`, `tree*`, and current event paths when the target project has them;
   - do not invent parallel helper methods when the current class already has the correct stored-procedure call path.
   - for C_KONE110/KH-style migration, compare the target against `references/author-tagged-style-baseline.md` and `references/author-tagged-program-style-profiles.json`; use same-program matched C# and Designer evidence first, require a fallback program key for excluded/current repair targets, and block zero-hit generated patterns such as internal DTO/context classes, generic value helpers, invented `CallDetailQuery` detail helpers, `DBNull.Value ?` row wrappers, `_selectType == SelectType.DETAIL ?` routing, `?? "%"` wildcard coalescing, `btn*.EditValue == null ? string.Empty`, and `Convert.ToString(rad*.EditValue)` radio locals.
8. Draft SELECT/SAVE SP work from the fixed packaged KH SP style:
   - preserve procedure names, parameters, Korean literals, comments, and result contracts;
   - include the standard procedure metadata header immediately above `CREATE/ALTER PROCEDURE` with `AUTHOR`, `CREATE DATE`, and `DESCRIPTION`;
   - avoid new CTEs, `#` temporary tables, `MERGE`, and `NOT EXISTS` by default;
   - do not generate empty-string/wildcard/status parameter defaults such as `@WORKTYPE = ''`, `@CUSTCD = '%'`, `@GUBUN = 'T'`, or `@GB = '1'` unless existing verified target SP evidence uses that exact contract;
   - do not add an up-front parameter normalization block such as `SET @WORKTYPE = ISNULL(...)` or `SET @PARAM = (CASE WHEN ISNULL(...) THEN ... END)` unless verified existing SP evidence for that same procedure branch already has it;
   - procedure parameters are only values sent by C# or the caller; helper/calculation values used only inside the SP must be local `DECLARE` variables followed by `SET`, not generated parameters;
   - do not expose derived date helper values such as `@YYYY`, `@MM`, `@BASYYYY`, or `@LASTDT` as generated procedure parameters; accept the raw target-style date input and derive local variables inside the SP when needed;
   - do not wrap date helper `SET` assignments in generated `IF ISNULL(...)` defaulting blocks or direct `IF @GIJUNDT <> '' SET @YYYY = ...` style guards; local derived date variables use `DECLARE` plus `SET` only unless verified existing SP evidence proves another shape;
   - do not present a full generated SELECT/SAVE SP as complete unless structured PB/DataWindow SQL, verified existing SP definition evidence, pasted SQL, DB schema, or an explicit user-approved inferred draft marker is recorded;
   - run `verify_pb_migration_sp_generation_contract` before completion claims for generated migration SP text;
   - use host-local `sql-formatting` for formatting and `sql-formatting-style-harness` for verification.
9. Separate formatting-only work from semantic rewrites. Require DB/MCP/source evidence for schema-dependent joins, scalar-function conversion, result parity, transaction behavior, or performance claims.
10. Produce the migration checklist, traceability, blockers, and verification plan before implementation or completion claims.

## Required outputs

- `HarnessResult` from `build_pb_to_csharp_migration_plan` or `build_datawindow_grid_layout`, or a documented procedural handoff when source access is absent.
- PBL export provider and PB version strategy: PblScripter wrapper, direct ORCA, pre-exported source, pasted source, described behavior, or bundled fallback; include version/runtime confidence for PB 7.0, PB 12.5, or unknown lineage.
- Migration mode and evidence strength: `standalone`, `described-behavior`, `pasted-source`, `partial-reference`, or `full-reference`.
- PB source trace summary: PBL/object, `.sru`, `.srw`, linked `.srd`, event/retrieve/update/save paths, and missing evidence.
- Confirmed vs inferred behavior map when PB source is absent and the user provided only behavior descriptions.
- DataWindow mapping summary: field names, generated grid column names, unsupported layout semantics, and converter fallback status.
- DataWindow naming summary: selected `grd*/gvw*` names, selected `col*_<COLUMN>` prefix, matched captions, and fallback fields when captions were not provable.
- Detail form layout summary: label/editor pair order, bounds, field names, generated or preserved control names, `BindingField` assignments, and `TabIndex` order.
- Target Designer evidence summary: extracted control types, parent/child containment, `BindingField`/`FieldName`, captions, `TabIndex`, bounds, `Properties.*`, collection calls, and whether grid columns were explicitly present or absent.
- Grid column generation summary: explicit GridColumn names and `Columns.AddRange` output, or a blocked reason if the proposed C# uses runtime `AddGridColumn`/`Columns.AddField` helper style without target evidence.
- Target C# control fallback map: target-project/custom controls, DevExpress fallback, WinForms fallback, selected provider, and reason.
- Target C# plan: screen path, event flow, select/save method path, XML serialization rule, and binding/result-contract expectations.
- SP plan: SELECT/SAVE procedure names, `@WORKTYPE` branches, XML/table variable plan, transaction/error/logging plan, and formatting verifier status.
- Author-tagged style baseline summary for C_KONE110/KH-style work: number of SPs/programs checked, mapped C# files, unmatched/exception programs, common style patterns, and generated-pattern violations blocked.
- Author-tagged per-program profile summary for C_KONE110/KH-style work: matched program key, source and Designer hash, base class, command/select/focused-row method names, SP calls, DbParameter names, grid/view names, BindingField samples, repository controls, dependency/version notes, and fallback program key when the active target is excluded.
- SP generation evidence: source evidence or explicit inferred-draft marker, `@WORKTYPE` contract, forbidden CTE/#temp/MERGE/NOT EXISTS scan, and SQL formatter/verifier status.
- SQL formatter composition: host-local `sql-formatting` applied or explicitly unavailable, plus KH verifier result when applicable.
- Token optimizer status: `passthrough` for source-of-truth SQL/C#/PB text, or `used` only for safe noisy command output/transcripts.
- Completion checklist with blocked items and next evidence required.

## Common mistakes

- Do not require local PblScripter, GWERP source trees, target C# source trees, `DataWindowToXml.html`, or live DB access for the skill to start.
- Do not treat missing PblScripter as missing export capability when direct ORCA is available. Direct ORCA is a first-class export provider, but it must use a matching PB runtime/ORCA version.
- Do not open or export an unknown-version PBL as if source evidence is proven. Probe/list first, record the suspected PB version, and block full source parity until the version/runtime is confirmed.
- Do not claim full PB behavior parity from binary strings or file names alone.
- Do not treat DataWindowToXml-style output as a full visual layout migration; it is a column-to-grid XML helper.
- Do not search the DB for KH-authored procedures on every run; use the fixed packaged SP style unless the user explicitly asks to refresh it.
- Do not treat TY/C_KONE110, KoneLib, or any other project name as the universal C# baseline. They are sample references only when the target project provides them.
- Do not add, upgrade, or re-target DevExpress packages or assemblies during migration generation. Existing target project references and controls are the dependency contract.
- Do not replace a target project's custom controls with DevExpress just because DevExpress is known; target-project controls win first.
- Do not add CTEs, `#` temporary tables, `MERGE`, `NOT EXISTS`, helper `@FIND...` variables, or scalar-function join rewrites by default.
- Do not invent completed SELECT/SAVE SP bodies from only a C# call signature. If only parameters and expected grid columns are known, output a blocked SP contract or clearly labeled inferred draft.
- Do not add default parameter values or parameter-normalization `SET` blocks just to make generated SQL defensive. Follow the verified SP contract or keep defaults as `NULL`/required parameters.
- Do not declare SP-internal helper or calculation values as procedure parameters. Parameters are caller/C# inputs; helper values belong in local `DECLARE` variables.
- When the matched C# call has explicit `DbParameter` evidence, generated SP parameters must stay inside that caller parameter set. Extra values belong in local `DECLARE` variables.
- Do not generate `IF ISNULL(@GIJUNDT, ...)`, `IF ISNULL(@YYYY, ...)`, `IF ISNULL(@MM, ...)`, `IF ISNULL(@BASYYYY, ...)`, `IF ISNULL(@LASTDT, ...)`, or direct `IF @GIJUNDT <> '' SET @YYYY = ...` date helper blocks. If date derivation is needed, use local `DECLARE` and `SET` without invented guard branches.
- Do not add source-unbacked `SELECT TOP 0/SELECT TOP (0) CAST/CONVERT/TRY_CONVERT(...)` schema-only fallback blocks to generated migration procedures; return from known branches or report a blocked contract instead.
- Do not generate grid columns through ad hoc runtime helpers when the target style expects Designer-level `GridColumn` members and `col*_<FIELD>` names.
- Do not generate internal request/context DTOs such as `RetrieveContext`, `GetRetrieveContext`, `GetEditValue`, or `GetColumnText` for ordinary screen retrieval code unless the target source already proves that pattern.
- Do not use arbitrary same-project C# files as the style basis when an author-tagged SP can be mapped to a same-program C# source. The bundled baseline is built from 62 author-tagged SPs, 41 program keys, 37 primary C# files, and 37 Designer files.
- Do not ignore `author-tagged-program-style-profiles.json`; aggregate counts alone are not enough for C_KONE110/KH-style generation.
- Do not let current generated repair targets teach the style back to the harness. Treat them as targets to verify, not baseline evidence.
- Do not generate generic search/default/layout wrappers such as `SetDefaultSearchValues`, `ApplyListColumnLayout`, `GetBasisYear`, `GetCustomerLike`, or `ValidateSearch` for ordinary screens unless the active target source already proves that pattern.
- Do not invent `CallDetailQuery` for list-focused detail loading. Use the active target event shape directly or a proven local helper name such as `fnFocusedRowChanged` / `CallViewQuery` when the matched source family uses it.
- Do not inline LIKE wildcard shaping in `CallSelectProcedure(...)` arguments such as `btnCUSTCD.Text + "%"` or `dr["ITEMCD"].ToString() + "%"`.
- Do not shape stored-procedure LIKE parameters in C# with `custcd = custcd + "%"`, `itemcd = itemcd + "%"`, or `itemcd = "%"`. Pass raw control/row values and let the stored procedure own LIKE defaults and wildcard handling.
- Do not add hidden date defaulting inside search/procedure paths such as `if (ymd*.EditValue == null) ymd*.SetToDay(0)`.
- Do not split a `u_DateEdit` value into C# parameters such as `@YYYY = ymd*.DateTime.Year.ToString()`, `@MM = DateTime.Now.Month...`, or `@BASYYYY = DateTime.Now.Year...`. Pass the target-style raw date value with `YYYYMMDD()` and let the stored procedure derive related year/month/base-date parameters.
- Do not generate ad hoc `new DateTime(...)` or string-concatenated month/year boundary values for screen retrieve parameters; let the stored procedure own derived date boundaries unless matched target evidence proves otherwise.
- For KoneLib-style screens, use `devFnc.InitControl(grd*)` for grid resets when matched target evidence shows that pattern. Do not generate direct `grd*.DataSource = null` resets unless active target evidence proves that exact local pattern.
- Do not replace explicit Designer month/amount columns with runtime `for` loops and `VisibleIndex` assignments.
- Do not broaden popup result handling or emit mojibake Korean captions/messages without current source evidence.
- Do not format SQL without preserving uppercase identifiers, Korean literals, comments, aliases, predicates, calculations, and row-shape contracts.
- Do not add a separate C# helper when the existing screen already has the correct `CallProc` or `CallViewQuery` path.
- Do not claim the harness ran because references were read; record module output, converter output, verifier output, or an explicit blocked/passthrough rationale.

## UAF implementation targets

- `src.skills.pb_to_csharp_migration.MigrationInputState`
- `src.skills.pb_to_csharp_migration.build_pbl_export_strategy`
- `src.skills.pb_to_csharp_migration.classify_migration_mode`
- `src.skills.pb_to_csharp_migration.build_pb_to_csharp_migration_plan`
- `src.skills.pb_to_csharp_migration.extract_datawindow_column_specs`
- `src.skills.pb_to_csharp_migration.extract_datawindow_columns`
- `src.skills.pb_to_csharp_migration.resolve_csharp_grid_column_prefix`
- `src.skills.pb_to_csharp_migration.resolve_csharp_grid_control_names`
- `src.skills.pb_to_csharp_migration.build_csharp_grid_column_name`
- `src.skills.pb_to_csharp_migration.build_csharp_control_name`
- `src.skills.pb_to_csharp_migration.extract_csharp_designer_control_specs`
- `src.skills.pb_to_csharp_migration.build_csharp_grid_column_designer_plan`
- `src.skills.pb_to_csharp_migration.get_author_tagged_csharp_style_baseline`
- `src.skills.pb_to_csharp_migration.normalize_author_tagged_program_key`
- `src.skills.pb_to_csharp_migration.resolve_author_tagged_style_evidence`
- `src.skills.pb_to_csharp_migration.verify_migration_generated_csharp_style`
- `src.skills.pb_to_csharp_migration.verify_pb_migration_sp_generation_contract`
- `src.skills.pb_to_csharp_migration.verify_pb_migration_sp_with_sql_formatting`
- `src.skills.pb_to_csharp_migration.generate_devexpress_grid_xml`
- `src.skills.pb_to_csharp_migration.build_datawindow_gridview_designer_defaults`
- `src.skills.pb_to_csharp_migration.build_datawindow_grid_layout`
- `src.skills.pb_to_csharp_migration.build_detail_form_layout_plan`
- `src.skills.pb_to_csharp_migration.resolve_csharp_control_stack`
- `src.skills.sql_formatting_style.verify_sql_formatting_style`
- `src.skills.sql_formatting_style.extract_powerbuilder_sql_fragments`
- `src.contracts.HarnessResult`
- `tests.test_pb_to_csharp_migration_harness`
- `skills/pb_to_csharp_migration_harness/SKILL.md`
