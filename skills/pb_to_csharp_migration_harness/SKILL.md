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
6. Resolve the target C# control stack before drafting code:
   - prefer target-project/custom controls such as a project-owned `u_GridControl` when they exist;
   - fall back to DevExpress controls only when the target project has no matching custom control;
   - fall back to WinForms basic controls when neither target-project controls nor DevExpress are available;
   - record the selected provider and fallback reason in the migration evidence.
7. Draft target C# flow from the style reference:
   - preserve existing method paths such as `CallViewQuery`, `CallProc`, `SelectType`, `DataUtil.DataTableToXml`, `SetModified`, `grd*`, `gvw*`, `tree*`, and current event paths when the target project has them;
   - do not invent parallel helper methods when the current class already has the correct stored-procedure call path.
8. Draft SELECT/SAVE SP work from the fixed packaged KH SP style:
   - preserve procedure names, parameters, Korean literals, comments, and result contracts;
   - avoid new CTEs, `#` temporary tables, `MERGE`, and `NOT EXISTS` by default;
   - use host-local `sql-formatting` for formatting and `sql-formatting-style-harness` for verification.
9. Separate formatting-only work from semantic rewrites. Require DB/MCP/source evidence for schema-dependent joins, scalar-function conversion, result parity, transaction behavior, or performance claims.
10. Produce the migration checklist, traceability, blockers, and verification plan before implementation or completion claims.

## Required outputs

- `HarnessResult` from `build_pb_to_csharp_migration_plan` or `build_datawindow_grid_layout`, or a documented procedural handoff when source access is absent.
- Migration mode and evidence strength: `standalone`, `described-behavior`, `pasted-source`, `partial-reference`, or `full-reference`.
- PB source trace summary: PBL/object, `.sru`, `.srw`, linked `.srd`, event/retrieve/update/save paths, and missing evidence.
- Confirmed vs inferred behavior map when PB source is absent and the user provided only behavior descriptions.
- DataWindow mapping summary: field names, generated grid column names, unsupported layout semantics, and converter fallback status.
- DataWindow naming summary: selected `grd*/gvw*` names, selected `col*_<COLUMN>` prefix, matched captions, and fallback fields when captions were not provable.
- Detail form layout summary: label/editor pair order, bounds, field names, generated or preserved control names, `BindingField` assignments, and `TabIndex` order.
- Target C# control fallback map: target-project/custom controls, DevExpress fallback, WinForms fallback, selected provider, and reason.
- Target C# plan: screen path, event flow, select/save method path, XML serialization rule, and binding/result-contract expectations.
- SP plan: SELECT/SAVE procedure names, `@WORKTYPE` branches, XML/table variable plan, transaction/error/logging plan, and formatting verifier status.
- SQL formatter composition: host-local `sql-formatting` applied or explicitly unavailable, plus KH verifier result when applicable.
- Token optimizer status: `passthrough` for source-of-truth SQL/C#/PB text, or `used` only for safe noisy command output/transcripts.
- Completion checklist with blocked items and next evidence required.

## Common mistakes

- Do not require local PblScripter, GWERP source trees, target C# source trees, `DataWindowToXml.html`, or live DB access for the skill to start.
- Do not claim full PB behavior parity from binary strings or file names alone.
- Do not treat DataWindowToXml-style output as a full visual layout migration; it is a column-to-grid XML helper.
- Do not search the DB for KH-authored procedures on every run; use the fixed packaged SP style unless the user explicitly asks to refresh it.
- Do not treat TY/C_KONE110, KoneLib, or any other project name as the universal C# baseline. They are sample references only when the target project provides them.
- Do not replace a target project's custom controls with DevExpress just because DevExpress is known; target-project controls win first.
- Do not add CTEs, `#` temporary tables, `MERGE`, `NOT EXISTS`, helper `@FIND...` variables, or scalar-function join rewrites by default.
- Do not format SQL without preserving uppercase identifiers, Korean literals, comments, aliases, predicates, calculations, and row-shape contracts.
- Do not add a separate C# helper when the existing screen already has the correct `CallProc` or `CallViewQuery` path.
- Do not claim the harness ran because references were read; record module output, converter output, verifier output, or an explicit blocked/passthrough rationale.

## UAF implementation targets

- `src.skills.pb_to_csharp_migration.MigrationInputState`
- `src.skills.pb_to_csharp_migration.classify_migration_mode`
- `src.skills.pb_to_csharp_migration.build_pb_to_csharp_migration_plan`
- `src.skills.pb_to_csharp_migration.extract_datawindow_column_specs`
- `src.skills.pb_to_csharp_migration.extract_datawindow_columns`
- `src.skills.pb_to_csharp_migration.resolve_csharp_grid_column_prefix`
- `src.skills.pb_to_csharp_migration.resolve_csharp_grid_control_names`
- `src.skills.pb_to_csharp_migration.build_csharp_grid_column_name`
- `src.skills.pb_to_csharp_migration.build_csharp_control_name`
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
