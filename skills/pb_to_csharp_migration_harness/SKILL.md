---
name: pb-to-csharp-migration-harness
description: Use when migrating, analyzing, planning, reviewing, or implementing PowerBuilder, PBL, SRU, SRW, SRD, DataWindow, GWERP, or TY/C_KONE110 workflows into C# WinForms/DevExpress screens and SQL Server SELECT/SAVE stored procedures.
---

# PB To C# Migration Harness

## KH Entry Contract

- Start through `always-on-front-door` for non-trivial migration work before source exploration, memory lookup, target-folder inspection, DB access, file writes, or subagent dispatch.
- Use this harness after intake when the request involves PowerBuilder source, PBL export, DataWindow layout, TY/C_KONE110 C# style, SELECT/SAVE stored procedure drafting, or PB-to-C# migration review.
- Treat local PB tools, GWERP source trees, TY samples, converter HTML, and live DB access as optional evidence, not runtime dependencies.
- Use bundled references as the portable baseline when local evidence is absent.
- Use host-local `sql-formatting` as the SQL formatter when SQL is formatted or generated; this harness owns migration flow and verification expectations.
- Treat PB source, SQL, C# code, Korean literals, comments, and business rules as source-of-truth passthrough content. Do not token-compress them.
- Report this skill as applied only when the migration plan module, DataWindow layout module, reference-guided procedure, smoke script, demo, or explicit passthrough/blocked rationale produced evidence.

## Support files

- Read `references/usage.md` before applying this skill to real migration work; it expands trigger boundaries, modes, workflow, evidence, and failure handling.
- Read `references/pbl-export-process.md` when PBL/PblScripter/ORCA/export behavior matters.
- Read `references/powerbuilder-source-analysis.md` when tracing SRU/SRW/SRD event flow, DataWindow SQL, save logic, or PB-vs-SP parity.
- Read `references/datawindow-layout-mapping.md` when converting DataWindow columns or layout into DevExpress/WinForms structure.
- Read `references/ty-csharp-style.md` before drafting or reviewing TY/C_KONE110 C# screen logic.
- Read `references/kh-sp-style.md` before drafting or reviewing SELECT/SAVE stored procedures.
- Read `references/sql-formatting-bridge.md` when SQL formatting, scalar function conversion, or verifier composition is involved.
- Read `references/migration-output-checklist.md` before claiming completion or handoff.
- Use `examples/minimal-workflow.md` as the compact success/blocked scenario.
- Run `python scripts/smoke_check.py` to verify support-file wiring and implementation target resolution.
- Run `python scripts/demo.py --output-dir <tmp>` to execute the runnable success/blocked mini-demo.

## Workflow

1. Confirm the migration mode:
   - `standalone`: no local PB/TY/DB/converter artifacts available; use bundled references and ask for missing source only when it changes correctness.
   - `pasted-source`: the user pasted SRU/SRW/SRD/C#/SQL; treat pasted text as authoritative.
   - `partial-reference`: some exported PB, converter, C# samples, SP text, or DB access exists.
   - `full-reference`: exported PB source, TY/C# samples, SP style reference, and optional DB verification are available.
2. Build a `pb-to-csharp` migration plan with `src.skills.pb_to_csharp_migration.build_pb_to_csharp_migration_plan`.
3. If PB assets exist, export or inspect safely:
   - list PBL objects first;
   - export named objects into an external output directory;
   - trace `.sru` entrypoints, `.srw` window logic, and linked `.srd` DataWindows;
   - never write exports into the source PBL tree.
4. If only bundled references are available, use the packaged PB export and analysis rules to produce a bounded plan, not a false claim of source parity.
5. Map DataWindow fields/layout:
   - use `src.skills.pb_to_csharp_migration.extract_datawindow_columns` and `generate_devexpress_grid_xml` for DataWindowToXml-compatible grid columns;
   - treat that mapping as grid-column scaffolding, not full PB coordinate or control migration.
6. Draft TY/C_KONE110 C# flow from the style reference:
   - preserve existing `CallViewQuery`, `CallProc`, `SelectType`, `DataUtil.DataTableToXml`, `SetModified`, `grd*`, `gvw*`, `tree*`, and current event paths;
   - do not invent parallel helper methods when the current class already has the correct stored-procedure call path.
7. Draft SELECT/SAVE SP work from the fixed packaged KH SP style:
   - preserve procedure names, parameters, Korean literals, comments, and result contracts;
   - avoid new CTEs, `#` temporary tables, `MERGE`, and `NOT EXISTS` by default;
   - use host-local `sql-formatting` for formatting and `sql-formatting-style-harness` for verification.
8. Separate formatting-only work from semantic rewrites. Require DB/MCP/source evidence for schema-dependent joins, scalar-function conversion, result parity, transaction behavior, or performance claims.
9. Produce the migration checklist, traceability, blockers, and verification plan before implementation or completion claims.

## Required outputs

- `HarnessResult` from `build_pb_to_csharp_migration_plan` or `build_datawindow_grid_layout`, or a documented procedural handoff when source access is absent.
- Migration mode and evidence strength: `standalone`, `pasted-source`, `partial-reference`, or `full-reference`.
- PB source trace summary: PBL/object, `.sru`, `.srw`, linked `.srd`, event/retrieve/update/save paths, and missing evidence.
- DataWindow mapping summary: field names, DevExpress grid column names, unsupported layout semantics, and converter fallback status.
- TY C# plan: screen path, event flow, select/save method path, XML serialization rule, and binding/result-contract expectations.
- SP plan: SELECT/SAVE procedure names, `@WORKTYPE` branches, XML/table variable plan, transaction/error/logging plan, and formatting verifier status.
- SQL formatter composition: host-local `sql-formatting` applied or explicitly unavailable, plus KH verifier result when applicable.
- Token optimizer status: `passthrough` for source-of-truth SQL/C#/PB text, or `used` only for safe noisy command output/transcripts.
- Completion checklist with blocked items and next evidence required.

## Common mistakes

- Do not require local PblScripter, GWERP source trees, TY source trees, `DataWindowToXml.html`, or live `C_KONE110` DB access for the skill to start.
- Do not claim full PB behavior parity from binary strings or file names alone.
- Do not treat DataWindowToXml-style output as a full visual layout migration; it is a column-to-grid XML helper.
- Do not search the DB for KH-authored procedures on every run; use the fixed packaged SP style unless the user explicitly asks to refresh it.
- Do not add CTEs, `#` temporary tables, `MERGE`, `NOT EXISTS`, helper `@FIND...` variables, or scalar-function join rewrites by default.
- Do not format SQL without preserving uppercase identifiers, Korean literals, comments, aliases, predicates, calculations, and row-shape contracts.
- Do not add a separate C# helper when the existing screen already has the correct `CallProc` or `CallViewQuery` path.
- Do not claim the harness ran because references were read; record module output, converter output, verifier output, or an explicit blocked/passthrough rationale.

## UAF implementation targets

- `src.skills.pb_to_csharp_migration.MigrationInputState`
- `src.skills.pb_to_csharp_migration.classify_migration_mode`
- `src.skills.pb_to_csharp_migration.build_pb_to_csharp_migration_plan`
- `src.skills.pb_to_csharp_migration.extract_datawindow_columns`
- `src.skills.pb_to_csharp_migration.generate_devexpress_grid_xml`
- `src.skills.pb_to_csharp_migration.build_datawindow_grid_layout`
- `src.skills.sql_formatting_style.verify_sql_formatting_style`
- `src.skills.sql_formatting_style.extract_powerbuilder_sql_fragments`
- `src.contracts.HarnessResult`
- `tests.test_pb_to_csharp_migration_harness`
- `skills/pb_to_csharp_migration_harness/SKILL.md`
