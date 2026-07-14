# DataWindow Layout Mapping

Use this reference with directly supplied SRD text, a user-provided field list, or a described DataWindow contract. Normal generation does not search for DataWindow files.

## Column Extraction

- Preserve supplied field names and source order.
- When visual column positions are present in supplied text, order by vertical then horizontal position.
- Match a nearby supplied text label to its field when the relationship is unambiguous.
- Otherwise use the field name as the caption and record the fallback.
- Keep computed fields distinct from stored fields.
- Record retrieve arguments, updateability, edit masks, dropdowns, protection, and validation only when supplied.

## Grid Mapping

Use the selected control provider from the packaged style contract.

- Grid/view names: `grd<Role>` and `gvw<Role>`.
- Column names: `col<Role>_<FIELD>`.
- `FieldName`: exact supplied result field.
- `Caption`: supplied caption or documented fallback.
- `VisibleIndex`: supplied visual order.
- Explicit Designer members and `Columns.AddRange` are required.
- Numeric, lookup, button, and boolean fields use the matching repository convention.
- Repository initialization and registration precede `ColumnEdit` assignment.

For DevExpress-compatible output, default to a hidden group panel, visible auto-filter row, visible footer, disabled auto-width, even-row appearance, and centered headers when the API supports them. For KoneLib, keep the corresponding wrapper behavior. For WinForms, express unsupported repository behavior through cell/editor configuration and record the substitution.

## Detail Mapping

Arrange label/editor pairs in stable rows and columns:

1. Preserve supplied field order.
2. Select editor kind from supplied metadata; otherwise use text.
3. Name the control from the packaged grammar.
4. Set `BindingField` when supported or record an explicit binding map.
5. Assign `TabIndex` left-to-right, top-to-bottom.
6. Keep required/read-only/null/edit-mask behavior only when supplied.

Do not copy PB coordinates blindly. Exact geometry requires supplied visual evidence and explicit fidelity scope.

## Unsupported Claims

A field mapping alone does not prove:

- band/header/detail/footer geometry;
- computed-expression behavior;
- dropdown data sources;
- edit masks, protection, or conditional formatting;
- retrieve SQL or update metadata;
- nested layouts, reports, or print fidelity;
- target custom-control flags.

List missing semantics as blocked or deferred. Do not infer them from a field name.

## Evidence

Record field, caption source, order source, editor/repository choice, generated control and column names, binding/result field, unsupported semantics, selected provider, and fallback reason.
