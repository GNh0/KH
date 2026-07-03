# PB To C# Migration Harness Usage

Use this harness for requests involving PB, PBL, PBD, ORCA, PblScripter, SRU, SRW, SRD, DataWindow, DataWindowToXml, GWERP, C# migration, project-specific controls, DevExpress grid/layout migration, WinForms fallback screens, or SELECT/SAVE stored-procedure migration.

Use it even when the local toolchain is absent. The packaged references are the fallback baseline. Local PBL exports, source trees, converter HTML, C# examples, and live DB access increase confidence but are not required just to start the workflow.

Do not use this harness as the SQL formatter. SQL formatting belongs to the host-local `sql-formatting` skill; this harness composes with it and verifies migration-specific constraints.

## When to use

Use this harness when the user asks to analyze, plan, migrate, review, or implement PowerBuilder screens, PBL/PBD exports, SRU/SRW/SRD/DataWindow assets, DataWindowToXml-compatible layouts, target C# WinForms/DevExpress screens, project-specific control mapping, or SQL Server SELECT/SAVE stored procedures as part of a PB-to-C# migration flow.

Do not use it for generic SQL formatting alone, generic C# cleanup with no PB migration context, or claims of project-specific style without current target evidence or packaged reference evidence.

## Inputs to collect

- Objective: screen, program, report, save flow, query, popup, or DataWindow being migrated.
- Available source evidence: PBL, exported `.sru`, `.srw`, `.srd`, `.srm`, pasted PB text, screenshots, existing C# screen, verified existing SP definition evidence, feature spec, or DB access.
- PBL export provider: PblScripter/wrapper, direct ORCA, pre-exported files, pasted source, described behavior, or bundled baseline.
- PB version/runtime evidence: PB 7.0, PB 12.5, unknown, matching ORCA/runtime path, or blocked runtime/license state.
- Migration mode: `standalone`, `described-behavior`, `pasted-source`, `partial-reference`, or `full-reference`.
- PB flow: object name, parent window/user object, event path, `OpenWithParm`, `Retrieve`, `Update`, DataWindow `dataobject`, and linked SQL.
- DataWindow fields: column names, update table, retrieve arguments, display labels, computed fields, DDDW/dropdown dependencies, edit masks, protection, tab order, and layout constraints.
- Target C# context: project, namespace, form base class, existing controls, custom control libraries, DevExpress references, Designer snippets, and existing method names.
- SP context: SELECT/SAVE procedure name, `@WORKTYPE` branches, XML/table variable usage, transaction/error/logging rules, and host-local SQL formatting expectation.
- Evidence limits: missing tool, missing source, ORCA failure, license failure, stale path, no live DB, or formatting-only boundary.
- Execution level: `hybrid-harness`.
- Implementation targets:
  - `src.skills.pb_to_csharp_migration.MigrationInputState`
  - `src.skills.pb_to_csharp_migration.build_pbl_export_strategy`
  - `src.skills.pb_to_csharp_migration.classify_migration_mode`
  - `src.skills.pb_to_csharp_migration.build_pb_to_csharp_migration_plan`
  - `src.skills.pb_to_csharp_migration.extract_datawindow_column_specs`
  - `src.skills.pb_to_csharp_migration.extract_csharp_designer_control_specs`
  - `src.skills.pb_to_csharp_migration.build_csharp_grid_column_designer_plan`
  - `src.skills.pb_to_csharp_migration.build_detail_form_layout_plan`
  - `src.skills.pb_to_csharp_migration.resolve_csharp_control_stack`
  - `src.skills.pb_to_csharp_migration.verify_migration_generated_csharp_style`
  - `src.skills.pb_to_csharp_migration.verify_pb_migration_sp_generation_contract`

## Execution pattern

1. Read `SKILL.md` and this usage reference first.
2. Run or emulate `build_pb_to_csharp_migration_plan(objective, state)` so the run has a concrete `HarnessResult` and migration mode.
3. Select only the reference files needed for the current slice:
   - PBL export and ORCA problems: `pbl-export-process.md`.
   - PB event/source tracing: `powerbuilder-source-analysis.md`.
   - DataWindow grid/layout: `datawindow-layout-mapping.md`.
   - Target C# implementation style: `ty-csharp-style.md` as a packaged sample/baseline, overridden by current target-project evidence.
   - Stored procedure drafting/review: `kh-sp-style.md`.
   - C_KONE110/KH/Geunho/Jang-Geunho style: `author-tagged-style-baseline.md`, which contains the analyzed `author-tagged SP -> program key -> matching C# screen source` dataset and generated-pattern violations found from that baseline.
   - C_KONE110/KH per-program profile: `author-tagged-program-style-profiles.json`, which stores the portable 37-program C#/Designer profile. Use it to choose method names, SP calls, DbParameter order, grid/view names, BindingField samples, repository controls, hashes, and fallback evidence without re-reading the original source tree.
   - SQL formatter/verifier composition: `sql-formatting-bridge.md`.
   - Completion/handoff: `migration-output-checklist.md`.
4. If a PBL/tool/source exists, inspect the real artifact first and keep exports outside the PB source tree. If not, use `described-behavior` when the user explained the old screen/workflow, or `standalone` when even that behavior is not known. State which claims cannot be proven.
5. Choose the PBL export provider through `build_pbl_export_strategy` or the same policy manually:
   - PblScripter or equivalent wrapper first.
   - Direct ORCA when the wrapper is missing.
   - Pre-exported `.sru/.srw/.srd/.srm` when export tooling is absent.
   - Pasted source.
   - Described behavior.
   - Bundled reference baseline.
6. For direct ORCA and PblScripter, use the same evidence sequence: list PBL objects, export the named object, then export linked DataWindows. The difference is only the caller/wrapper. Match the runtime to the PBL lineage: PB 7.0 with PB 7.0 ORCA/runtime, PB 12.5 with PB 12.5 ORCA/runtime. If the version is unknown, list/probe only and mark full source parity blocked until confirmed.
7. For DataWindow column conversion, call `extract_datawindow_column_specs`, `resolve_csharp_grid_column_prefix`, `resolve_csharp_grid_control_names`, and `generate_devexpress_grid_xml` or follow the same rule manually. This reproduces the packaged DataWindowToXml-compatible behavior, including visual column order, matched PB captions, C# column names like `colList_<COLUMN>`, `colDetail_<COLUMN>`, `col<TABLE>_<COLUMN>`, or `col<PURPOSE>_<COLUMN>`, grid names like `grdList/gvwList`, `grdDetail/gvwDetail`, `grd<TABLE>/gvw<TABLE>`, or `grd<PURPOSE>/gvw<PURPOSE>`, and the attached converter's GridView defaults. When table naming is ambiguous, use the business purpose suffix such as `POR`, `BOM`, `ITEM`, or `REQ`. When generating C# Designer code, call or mirror `build_datawindow_gridview_designer_defaults` so `ShowGroupPanel=false`, `EnableAppearanceEvenRow=true`, `ColumnAutoWidth=false`, `ShowFooter=true`, and `ShowAutoFilterRow=true` are not lost.
8. If target C# Designer code is available, call `extract_csharp_designer_control_specs` before drafting or reviewing generated C#. Preserve target evidence for control type, parent/child containment, `BindingField`, `_isAllowBlank`, `_isPKValue`, `EnterMoveNextControl`, `EditValue`, `Properties.*`, `Location`, `Size`, `Dock`, `Margin`, `MinimumSize`, `MaximumSize`, `Text`, `Caption`, `TabIndex`, `MainView`, `ViewCollection`, `GridControl`, and collection `AddRange` calls. If a Designer has no explicit GridColumn declarations, record `grid_columns=[]` instead of inventing hidden evidence.
9. For detail-entry screens, call `build_detail_form_layout_plan` or follow the same rule manually. Arrange LabelControl plus TextEdit, SpinEdit, ButtonEdit, DateEdit, LookUpEdit, CheckEdit, RadioGroup, or MemoEdit pairs in clean SA100100-style rows and columns. Keep source order and captions, but do not copy PB coordinates blindly. Prefer existing target-project control names when known; otherwise use target-style names such as `txtITEMNM`, `btnITEMCD`, `cboITEMACNT`, `SpinQTY`, `ymdORDDT`, `ChkUSEYN`, or `memoREMARK`. Every editor must record the source field name, `BindingField = "<FIELD>"`, and left-to-right/top-to-bottom `TabIndex` assignment.
10. For grid column C# output, call `build_csharp_grid_column_designer_plan` and then `verify_migration_generated_csharp_style`. Generated columns should be explicit `GridColumn` members with `Columns.AddRange` and names such as `colList_CUSTNM` or `colDetail_ORDNUM`; numeric AMT/QTY/UNP/WGT columns must use a `RepositoryItemSpinEdit` assigned through `ColumnEdit`, not `GridColumn.DisplayFormat` as the primary formatting path. Do not generate default `AddGridColumn`, `Columns.AddField`, `view.Name + "_" + fieldName`, or numeric `DisplayFormat`-only helpers unless the current target screen already proves that as its local style.
11. For C# work, resolve the control stack first: target-project/custom controls -> DevExpress controls -> WinForms basic controls. Preserve the current screen flow rather than adding a separate parallel helper. Reuse existing `CallViewQuery` and `CallProc` paths whenever they already match the target procedure. Use the target project's existing DevExpress/KoneLib references and API surface. Do not add, upgrade, or retarget DevExpress packages from current online/latest examples unless the user explicitly asks for a library upgrade.
12. For C_KONE110/KH-style C# work, consult `author-tagged-style-baseline.md` before generating or reviewing code. Use same-program matched C# evidence first, and do not use generic same-project code as the style source when matched evidence exists. Do not generate internal DTO/context flows such as `RetrieveContext`, generic `GetEditValue`/`GetColumnText` helpers, runtime grid-column helpers, `DBNull.Value ?` row wrappers, `_selectType == SelectType.DETAIL ?` routing, `?? "%"` wildcard coalescing, `btn*.EditValue == null ? string.Empty`, `Convert.ToString(rad*.EditValue)` locals, or `txt*NM` date edits unless current target evidence proves that exact local pattern. Also consult `author-tagged-program-style-profiles.json`; aggregate counts are only a gate, while the per-program profile is the generation guide. If the active program is excluded or unmapped, record the fallback program key and why it is valid.
13. For SQL work, keep original SQL uncompressed, apply host-local `sql-formatting`, and run `sql-formatting-style-harness` verification when proof is required. For generated migration SELECT/SAVE procedures, call `verify_pb_migration_sp_generation_contract` first; full SP output needs PB/DataWindow SQL, verified existing SP definition evidence, pasted SQL, DB schema, or an explicit user-approved inferred-draft marker. For C_KONE110/KH-style SP generation, include the standard `AUTHOR` / `CREATE DATE` / `DESCRIPTION` metadata comment block immediately above `CREATE/ALTER PROCEDURE`, and do not add generated literal parameter defaults or up-front `SET @PARAM = ISNULL/CASE` normalization blocks without verified target SP evidence.
14. Mark token optimizer as `passthrough` for PB/C#/SQL source text. Use optimization only for noisy command output or subagent transcripts where required facts are preserved.
15. Before completion, produce the migration checklist and name blocked evidence. Do not claim PB parity, DB semantic equivalence, UI layout fidelity, or completed SP semantics without the matching evidence.

## Evidence to produce

- `HarnessResult` from `build_pb_to_csharp_migration_plan` or `build_datawindow_grid_layout`.
- `mode`: `standalone`, `described-behavior`, `pasted-source`, `partial-reference`, or `full-reference`.
- `pbl_export_strategy`: provider, provider priority, PB version, version policy, operations, blocked conditions, runtime lookup requirement, and source-parity confidence.
- `strong_evidence` and `weak_evidence` explaining what was actually available.
- Confirmed vs inferred behavior map when no PB source exists but user-described workflow is available.
- PB trace summary: object names, source files, event flow, DataWindows, retrieve/update/save paths, and gaps.
- DataWindow mapping: extracted columns, matched captions, generated C# column/grid names, generated grid XML shape, unsupported visual/layout features, and fallback status.
- Detail form layout: label/editor rows and columns, source field names, selected editor types, control names, `BindingField` assignment snippets, and left-to-right/top-to-bottom `TabIndex` snippets.
- Target Designer extraction: actual control types, properties, containment, bounds, grid/view links, collection calls, and explicit missing-grid-column evidence when columns were absent from Designer.
- Grid column Designer plan: explicit `GridColumn` declarations, `Columns.AddRange`, `FieldName`, `Caption`, `Name`, `VisibleIndex`, `RepositoryItemSpinEdit` `ColumnEdit` mappings for numeric columns, and any style violations blocked by `verify_migration_generated_csharp_style`.
- Target C# control fallback map: selected provider for each logical control, target-project/custom matches, DevExpress fallback, WinForms fallback, and reason.
- Target C# plan: target class, existing method path, controls, XML serialization rule, and result-binding expectations.
- Author-tagged style baseline summary when applicable: 62 SPs, 41 program keys, 37 primary C# files, 37 Designer files, current generated target exclusions, SP-only/non-screen exceptions, C# frequency checks, Designer frequency checks, and zero-hit generated patterns blocked.
- Author-tagged per-program profile summary when applicable: profile file version, matched program key, source/designer hashes, base class, command/select/focused-row method names, SP calls, DbParameter names, grids/views, BindingField samples, repository controls, and fallback program key for excluded targets.
- SP plan: SELECT/SAVE procedures, XML/table variable shape, transaction boundary, logging, duplicate checks, and formatting verification.
- SP generation contract: source evidence or inferred-draft marker, `@WORKTYPE` branch contract, forbidden CTE/#temp/MERGE/NOT EXISTS scan, and the separate SQL formatting verifier result.
- SQL verifier status and semantic limits.
- `token_optimizer_status` with `passthrough` reason for source-of-truth text or before/after stats when noisy output was compressed.
- `actual_runtime_path`: module, script, verifier, or procedural path that produced the evidence.

## Failure handling

- Missing PblScripter: use direct ORCA when available. If neither wrapper nor ORCA is available, continue with pre-exported source, pasted-source, described-behavior, or standalone mode; ask for exported source only if correctness depends on PB event flow.
- Unknown PB version with ORCA/PblScripter: treat the provider as available for list/probe only. Do not claim full source parity until PB version and matching runtime are confirmed.
- ORCA runtime failure: distinguish missing runtime path, bad library, incompatible PBL version, and license/SySAM failure. Do not claim the PBL is invalid until that is known.
- Binary-only evidence: treat strings as weak evidence; they can reveal names or SQL fragments, not full event or save semantics.
- Missing DataWindowToXml: use the packaged DataWindow column-to-grid rules or ask for SRD text.
- Missing target C# samples: use `ty-csharp-style.md` as a generic packaged baseline and mark style confidence lower. Do not claim the target project uses TY/KoneLib unless current artifacts prove it.
- Missing target dependency references: do not infer the latest DevExpress API. Use bundled profile patterns only where the target references are unknown, and mark dependency/version confidence lower.
- Missing target Designer properties: do not guess project-specific flags or grid column declarations. Generate a fallback plan and label the missing properties as assumptions.
- Missing live DB: do not claim schema, scalar-function equivalence, execution plan, or semantic parity.
- SQL formatter unavailable: keep SQL untouched except for explicitly requested minimal cleanup and state that formatting proof is blocked.
- Existing SP evidence unavailable: do not present full generated SELECT/SAVE bodies as complete unless the user explicitly accepts an inferred draft.
- Target project is not C_KONE110/KH: do not apply the author-tagged C_KONE110/KH profile as a hard requirement. Use it only as a named sample/fallback with lower confidence.

## Quality bar

A valid PB-to-C# migration harness run must prove the selected export/provider path, the PB version/runtime confidence, the actual source evidence level, the target C# control/style basis, the SQL formatting verifier boundary, and the blocked assumptions. It must not claim PB parity, UI layout fidelity, C# style fidelity, or completed SELECT/SAVE semantics unless the matching source, Designer, SP, or DB evidence is present.
