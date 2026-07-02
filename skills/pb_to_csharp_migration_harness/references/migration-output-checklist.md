# Migration Output Checklist

Use this checklist before handoff or completion.

## Required sections

- Objective and target operator.
- Migration mode and evidence strength.
- PB source trace summary.
- DataWindow field/layout mapping.
- Target Designer extraction summary when `.Designer.cs` or pasted Designer exists: control types, parent/child containment, `BindingField`, project flags, `Properties.*`, bounds, captions, `TabIndex`, grid/view links, collection calls, and explicit absent GridColumn evidence.
- Detail form label/editor layout, source field names, target control names, `BindingField` assignments, and left-to-right/top-to-bottom `TabIndex` assignments when the migrated screen has input controls.
- Control naming evidence for generated controls: `txt`, `btn`, `cbo`, `Spin`, `ymd`, `Chk`, `memo`, `lbl`, `pn`, `grp`, `grd/gvw`, `treeList`, and `tab` prefixes, with target-project existing names taking precedence.
- Grid column generation evidence: explicit `GridColumn` declarations, `Columns.AddRange`, `FieldName`, `Caption`, `Name`, `VisibleIndex`, and `RepositoryItemSpinEdit` `ColumnEdit` evidence for numeric columns, or a blocked reason. Do not accept default `AddGridColumn`/`Columns.AddField` helper output unless local target evidence proves that style.
- Target C# implementation plan.
- Target C# control fallback map.
- SELECT/SAVE SP plan.
- SP generation evidence: source SQL/PB/DB evidence or approved inferred-draft marker, `@WORKTYPE` branch contract, CTE/#temp/MERGE/NOT EXISTS scan, and SQL formatting verifier status.
- SQL formatting/verifier status.
- Traceability from PB behavior to C# method and SP branch.
- Verification plan.
- Blocked items and missing evidence.

## Completion criteria

- No claim of full PB parity without exported or pasted source evidence.
- No claim of DB semantic equivalence without DB-backed check.
- No claim of layout fidelity without visual/layout source.
- No claim of correct Designer style without property extraction or explicit fallback assumptions.
- No generated runtime grid-column helper when the target style requires Designer `GridColumn` members and `col*_<FIELD>` names.
- No completed SELECT/SAVE SP claim from only C# parameters or grid columns. Use blocked contract or clearly labeled inferred draft when PB/DataWindow SQL, verified existing SP definition evidence, pasted SQL, or DB evidence is absent.
- Detail form controls are aligned as readable label/editor pairs instead of blindly copying PB coordinates unless exact visual parity was explicitly requested.
- No generated user-facing files outside the exact requested target path.
- No hidden use of global memory as a substitute for current artifacts.
- Token optimizer status is recorded.
- SQL formatter and verifier roles are separated.
- Project-specific controls are not hard-coded from a sample project. The selected control provider is target-project/custom, DevExpress, or WinForms with a reason.
- Remaining assumptions are visible.

## User-facing output

For normal work, return the deliverable or migration plan in the user's language. Keep internal KH evidence out of the final answer unless the user asks for a skill/harness audit.

- Do not add source-unbacked `SELECT TOP 0/SELECT TOP (0) CAST/CONVERT/TRY_CONVERT(...)` schema-only fallback blocks to generated migration procedures; return from known branches or report a blocked contract instead.
