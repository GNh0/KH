# PB To C# Migration Harness Usage

Use this reference when a PowerBuilder/GWERP workflow must be migrated, reviewed, or planned as target-project C# WinForms/DevExpress screens and SQL Server SELECT/SAVE stored procedures. TY/C_KONE110 is one supported reference project, not a universal baseline.

## When to use

Use this harness for requests involving PB, PBL, PBD, ORCA, PblScripter, SRU, SRW, SRD, DataWindow, DataWindowToXml, GWERP, C# migration, project-specific controls, DevExpress grid/layout migration, WinForms fallback screens, or SELECT/SAVE stored-procedure migration.

Use it even when the local toolchain is absent. The packaged references are the fallback baseline. Local PBL exports, source trees, converter HTML, C# examples, and live DB access increase confidence but are not required just to start the workflow.

Do not use this harness as the SQL formatter. SQL formatting belongs to the host-local `sql-formatting` skill; this harness decides migration flow and verifies that PB/C#/SP work follows the migration contract.

## Inputs to collect

- Objective: screen, program, report, save flow, query, popup, or DataWindow being migrated.
- Available source evidence: PBL, exported `.sru`, `.srw`, `.srd`, pasted PB text, screenshots, existing C# screen, verified existing SP definition evidence, feature spec, or DB access.
- Migration mode: `standalone`, `described-behavior`, `pasted-source`, `partial-reference`, or `full-reference`.
- PB flow: object name, parent window/user object, event path, `OpenWithParm`, `Retrieve`, `Update`, DataWindow `dataobject`, and linked SQL.
- DataWindow fields: column names, update table, retrieve arguments, display labels, computed fields, DDDW/dropdown dependencies, edit masks, protection, tab order, and layout constraints.
- C# target: project name, namespace/module, form class, available custom controls, DevExpress availability, WinForms fallback availability, control names, `SelectType`, `CallViewQuery`, `CallProc`, `DataUtil.DataTableToXml`, `SetModified`, and current binding/result contract.
- SP target: `sp_<PROGRAM>_SELECT`, `sp_<PROGRAM>_SAVE`, `@WORKTYPE`, XML input shape, transaction/logging/error pattern, and formatting verifier needs.
- Evidence limits: missing tool, missing source, ORCA failure, license failure, stale path, no live DB, or formatting-only boundary.

## Execution pattern

1. Read `SKILL.md` and this usage reference first.
2. Run or emulate `build_pb_to_csharp_migration_plan(objective, state)` so the run has a concrete `HarnessResult` and migration mode.
3. Select only the reference files needed for the current slice:
   - PBL export and ORCA problems: `pbl-export-process.md`.
   - PB event/source tracing: `powerbuilder-source-analysis.md`.
   - DataWindow grid/layout: `datawindow-layout-mapping.md`.
   - Target C# implementation style: `ty-csharp-style.md` as a packaged sample/baseline, overridden by current target-project evidence.
   - Stored procedure drafting/review: `kh-sp-style.md`.
   - C_KONE110/KH/근호/장근호 style: `author-tagged-style-baseline.md`, which lists the complete author-tagged SP/program dataset and generated-pattern violations found from that baseline.
   - SQL formatter/verifier composition: `sql-formatting-bridge.md`.
   - Completion/handoff: `migration-output-checklist.md`.
4. If a PBL/tool/source exists, inspect the real artifact first and keep exports outside the PB source tree. If not, use `described-behavior` when the user explained the old screen/workflow, or `standalone` when even that behavior is not known. State which claims cannot be proven.
5. For DataWindow column conversion, call `extract_datawindow_column_specs`, `resolve_csharp_grid_column_prefix`, `resolve_csharp_grid_control_names`, and `generate_devexpress_grid_xml` or follow the same rule manually. This reproduces the packaged DataWindowToXml-compatible behavior, including visual column order, matched PB captions, C# column names like `colList_<COLUMN>`, `colDetail_<COLUMN>`, `col<TABLE>_<COLUMN>`, or `col<PURPOSE>_<COLUMN>`, grid names like `grdList/gvwList`, `grdDetail/gvwDetail`, `grd<TABLE>/gvw<TABLE>`, or `grd<PURPOSE>/gvw<PURPOSE>`, and the attached converter's GridView defaults. When table naming is ambiguous, use the business purpose suffix such as `POR`, `BOM`, `ITEM`, or `REQ`. When generating C# Designer code, call or mirror `build_datawindow_gridview_designer_defaults` so `ShowGroupPanel=false`, `EnableAppearanceEvenRow=true`, `ColumnAutoWidth=false`, `ShowFooter=true`, and `ShowAutoFilterRow=true` are not lost.
6. If target C# Designer code is available, call `extract_csharp_designer_control_specs` before drafting or reviewing generated C#. Preserve target evidence for control type, parent/child containment, `BindingField`, `_isAllowBlank`, `_isPKValue`, `EnterMoveNextControl`, `EditValue`, `Properties.*`, `Location`, `Size`, `Dock`, `Margin`, `MinimumSize`, `MaximumSize`, `Text`, `Caption`, `TabIndex`, `MainView`, `ViewCollection`, `GridControl`, and collection `AddRange` calls. If a Designer has no explicit GridColumn declarations, record `grid_columns=[]` instead of inventing hidden evidence.
7. For detail-entry screens, call `build_detail_form_layout_plan` or follow the same rule manually. Arrange LabelControl plus TextEdit, SpinEdit, ButtonEdit, DateEdit, LookUpEdit, CheckEdit, RadioGroup, or MemoEdit pairs in clean SA100100-style rows and columns. Keep source order and captions, but do not copy PB coordinates blindly. Prefer existing target-project control names when known; otherwise use target-style names such as `txtITEMNM`, `btnITEMCD`, `cboITEMACNT`, `SpinQTY`, `ymdORDDT`, `ChkUSEYN`, or `memoREMARK`. Every editor must record the source field name, `BindingField = "<FIELD>"`, and left-to-right/top-to-bottom `TabIndex` assignment.
8. For grid column C# output, call `build_csharp_grid_column_designer_plan` and then `verify_migration_generated_csharp_style`. Generated columns should be explicit `GridColumn` members with `Columns.AddRange` and names such as `colList_CUSTNM` or `colDetail_ORDNUM`; numeric AMT/QTY/UNP/WGT columns must use a `RepositoryItemSpinEdit` assigned through `ColumnEdit`, not `GridColumn.DisplayFormat` as the primary formatting path. Do not generate default `AddGridColumn`, `Columns.AddField`, `view.Name + "_" + fieldName`, or numeric `DisplayFormat`-only helpers unless the current target screen already proves that as its local style.
9. For C# work, resolve the control stack first: target-project/custom controls -> DevExpress controls -> WinForms basic controls. Preserve the current screen flow rather than adding a separate parallel helper. Reuse existing `CallViewQuery` and `CallProc` paths whenever they already match the target procedure.
10. For C_KONE110/KH-style C# work, consult `author-tagged-style-baseline.md` before generating or reviewing code. Do not generate internal DTO/context flows such as `RetrieveContext`, generic `GetEditValue`/`GetColumnText` helpers, runtime grid-column helpers, or `txt*NM` date edits unless current target evidence proves that exact local pattern.
11. For SQL work, keep original SQL uncompressed, apply host-local `sql-formatting`, and run `sql-formatting-style-harness` verification when proof is required. For generated migration SELECT/SAVE procedures, call `verify_pb_migration_sp_generation_contract` first; full SP output needs PB/DataWindow SQL, verified existing SP definition evidence, pasted SQL, DB schema, or an explicit user-approved inferred-draft marker. For C_KONE110/KH-style SP generation, include the standard `AUTHOR` / `CREATE DATE` / `DESCRIPTION` metadata comment block immediately above `CREATE/ALTER PROCEDURE`, and do not add generated literal parameter defaults or up-front `SET @PARAM = ISNULL/CASE` normalization blocks without verified target SP evidence.
12. Mark token optimizer as `passthrough` for PB/C#/SQL source text. Use optimization only for noisy command output or subagent transcripts where required facts are preserved.
13. Before completion, produce the migration checklist and name blocked evidence. Do not claim PB parity, DB semantic equivalence, UI layout fidelity, or completed SP semantics without the matching evidence.

## Evidence to produce

- `HarnessResult` from `build_pb_to_csharp_migration_plan` or `build_datawindow_grid_layout`.
- `mode`: `standalone`, `described-behavior`, `pasted-source`, `partial-reference`, or `full-reference`.
- `strong_evidence` and `weak_evidence` explaining what was actually available.
- Confirmed vs inferred behavior map when no PB source exists but user-described workflow is available.
- PB trace summary: object names, source files, event flow, DataWindows, retrieve/update/save paths, and gaps.
- DataWindow mapping: extracted columns, matched captions, generated C# column/grid names, generated grid XML shape, unsupported visual/layout features, and fallback status.
- Detail form layout: label/editor rows and columns, source field names, selected editor types, control names, `BindingField` assignment snippets, and left-to-right/top-to-bottom `TabIndex` snippets.
- Target Designer extraction: actual control types, properties, containment, bounds, grid/view links, collection calls, and explicit missing-grid-column evidence when columns were absent from Designer.
- Grid column Designer plan: explicit `GridColumn` declarations, `Columns.AddRange`, `FieldName`, `Caption`, `Name`, `VisibleIndex`, `RepositoryItemSpinEdit` `ColumnEdit` mappings for numeric columns, and any style violations blocked by `verify_migration_generated_csharp_style`.
- Target C# control fallback map: selected provider for each logical control, target-project/custom matches, DevExpress fallback, WinForms fallback, and reason.
- Target C# plan: target class, existing method path, controls, XML serialization rule, and result-binding expectations.
- Author-tagged style baseline summary when applicable: 61 SPs, 40 program keys, mapped C# evidence, SP-only/unmapped exceptions, C# frequency checks, and SP frequency checks.
- SP plan: SELECT/SAVE procedures, XML/table variable shape, transaction boundary, logging, duplicate checks, and formatting verification.
- SP generation contract: source evidence or inferred-draft marker, `@WORKTYPE` branch contract, forbidden CTE/#temp/MERGE/NOT EXISTS scan, and the separate SQL formatting verifier result.
- SQL verifier status and semantic limits.
- `token_optimizer_status` with `passthrough` reason for source-of-truth text or before/after stats when noisy output was compressed.
- `actual_runtime_path`: module, script, verifier, or procedural path that produced the evidence.

## Failure handling

- Missing PblScripter: continue in standalone, described-behavior, pasted-source, or partial-reference mode; ask for exported source only if correctness depends on PB event flow.
- ORCA runtime failure: distinguish missing runtime path, bad library, and license/SySAM failure. Do not claim the PBL is invalid until that is known.
- Binary-only evidence: treat strings as weak evidence; they can reveal names or SQL fragments, not full event or save semantics.
- Missing DataWindowToXml: use the packaged DataWindow column-to-grid rules or ask for SRD text.
- Missing target C# samples: use `ty-csharp-style.md` as a generic packaged baseline and mark style confidence lower. Do not claim the target project uses TY/KoneLib unless current artifacts prove it.
- Missing target Designer properties: do not guess project-specific flags or grid column declarations. Generate a fallback plan and label the missing properties as assumptions.
- Missing live DB: do not claim schema, scalar-function equivalence, execution plan, or semantic parity.
- Missing PB/DataWindow SQL or verified existing SP body: do not present a full generated SP as complete. Return a blocked SP contract or a clearly labeled inferred draft only when the user approves that mode.
- Formatting-only request: do not perform performance tuning or scalar-function rewrites unless the user asks and evidence exists.

## Quality bar

A valid run lets another agent answer what PB behavior was traced, what was only inferred, how DataWindow fields map to target C# controls, which target method path should be reused, what SELECT/SAVE SP contract is expected, what SQL formatting verifier said, what remains blocked, and whether local evidence was present or absent.

It must work from bundled references alone. Local host paths are examples, not requirements. The harness should degrade honestly instead of pretending it inspected unavailable PB, C#, HTML, or DB artifacts.
