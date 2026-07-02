# Target C# Style

Use this reference before drafting or reviewing target-project C# migration code. TY/C_KONE110 examples are packaged sample evidence only; the active target project's real controls, base forms, method paths, and naming conventions override this baseline.

## Core style

- Preserve the existing class, namespace, control names, event handler names, and method names unless the user asks for refactoring.
- Reuse existing screen flow. Do not create a parallel helper method if `CallViewQuery`, `CallProc`, or another current method already owns the same stored-procedure path.
- Prefer small, same-shape patches over broad redesign.
- Treat the active checkout and active screen binding as source of truth. Duplicate project trees are common; verify the target tree before applying style.

## Control fallback order

Resolve controls before drafting code:

1. Target-project/custom controls already present in the target checkout, such as project-owned `u_GridControl`, `u_TextEdit`, `u_Label`, base forms, or equivalent wrappers.
2. DevExpress controls such as `GridControl`, `GridView`, `TextEdit`, `LabelControl`, `GroupControl`, `PanelControl`, and `XtraTabControl` when the target project has DevExpress but no matching custom wrapper.
3. WinForms basic controls such as `DataGridView`, `TextBox`, `Label`, `GroupBox`, `Panel`, and `TabControl` when neither target-project wrappers nor DevExpress are available.

Record the selected provider and reason. Do not hard-code KoneLib or any project-specific wrapper unless it exists in the target project or was explicitly selected by the user.

## Detail form layout style

- For detail panels like SA100100, arrange labels and input editors as clean label/editor pairs in fixed rows and columns. The goal is readable alignment, not a pixel-for-pixel copy of PB coordinates.
- Use the target project's existing control names when a matching screen or migrated control exists.
- When an existing `.Designer.cs` or pasted Designer snippet is available, extract its properties first and treat them as target-style evidence: `BindingField`, `_isAllowBlank`, `_isPKValue`, `EnterMoveNextControl`, `EditValue`, `Properties.*`, `Location`, `Size`, `Dock`, `Margin`, `MinimumSize`, `MaximumSize`, `Text`, `Caption`, and `TabIndex`.
- When generating fallback names, use field-based names seen in the target style: `txtFIELD` for text, `btnFIELD` for button/search editors, `cboFIELD` for combo/lookup editors, `SpinFIELD` for SpinEdit, `ymdFIELD` for DateEdit, `ChkFIELD` for CheckEdit, and `memoFIELD` for MemoEdit.
- RepositoryItem editors are separate from screen input controls. Grid repository names commonly use `rpsbtn*`, `rpscbo*`, `rpsSpin*`, or `rpsChk*`; do not use those prefixes for ordinary detail-panel input controls unless the target screen already does.
- Use `pn<Area>` for panel containers, `grp<Area>` for groups, `grd<Area>/gvw<Area>` for grids/views, `treeList<Area>` for new TreeList fallbacks, and `tab<Area>` for tabs. Existing target names still win, including legacy `pan*`, `tree*`, `Tab`, or numbered designer names.
- Set each editor's `BindingField` to the source field name and `TabIndex` in left-to-right, top-to-bottom input order, for example `this.txtITEMNM.BindingField = "ITEMNM";`, `this.SpinQTY.BindingField = "QTY";`, and `this.ymdORDDT.TabIndex = 2;`.
- Keep labels tied to captions from PB/DataWindow or user-provided Korean labels, but use field-based control names rather than deriving names from Korean caption text.

## Grid naming style

- Main/list grid controls usually use `grdList` and `gvwList`.
- Detail/child grid controls usually use `grdDetail` and `gvwDetail`.
- Table-bound grids may use the source table suffix, such as `grdSA110T` and `gvwSA110T`.
- If table naming is ambiguous, grids may use a business-purpose suffix such as `grdPOR/gvwPOR`, `grdBOM/gvwBOM`, `grdITEM/gvwITEM`, or `grdREQ/gvwREQ`.
- Grid columns should follow the same target style: `colList_<COLUMN>`, `colDetail_<COLUMN>`, `col<TABLE>_<COLUMN>`, or `col<PURPOSE>_<COLUMN>`.
- Preserve uppercase field names in `FieldName`; use matched Korean PB/DataWindow captions when available, otherwise fall back to the uppercase field name.
- Prefer explicit Designer `GridColumn` members and `Columns.AddRange` over generated runtime helpers. Treat `AddGridColumn(...)`, `view.Columns.AddField(...)`, and `column.Name = view.Name + "_" + fieldName` as style violations unless the current target screen already uses that exact local pattern.
- If the current Designer has grids but no explicit columns, record that as evidence instead of inventing columns from the Designer. Columns may still be generated from PB/DataWindow/SP evidence, but the evidence source must be named.

## Select flow

Typical select flow:

- `CallViewQuery(SelectType.<TYPE>, ...)`;
- pass `@WORKTYPE = _selectType.ToString()` or equivalent current pattern;
- call the target `sp_<PROGRAM>_SELECT`;
- bind datasets to existing GridControl, TreeList, or controls;
- preserve expected column names such as `ID` and `ParentID` when TreeList binding depends on them.

## Save flow

Typical save flow:

- collect current or changed rows from the existing grid/table;
- call `SetModified()` on an unchanged row when it must be serialized as a modified XML row;
- use `DataUtil.DataTableToXml(..., DataRowState.Modified)` or the existing screen's matching helper;
- call `CallProc("<WORKTYPE>")` or the existing save method;
- pass XML and parameters to `sp_<PROGRAM>_SAVE`;
- preserve existing `@WORKTYPE`, `@USERID`, `@USERIP`, date/time, and key parameter conventions.

## Review checks

- Does the migrated C# reuse the existing method path?
- Did a copied PB behavior introduce duplicate helper methods?
- Did generated grid code avoid ad hoc runtime column helpers and preserve `col*_<FIELD>` names?
- Did Designer-derived controls preserve `BindingField`, project-specific flags, properties, bounds, and `TabIndex`?
- Does XML serialization actually include the intended rows?
- Did unchanged focused rows get `SetModified()` when needed?
- Does the result shape match current bindings?
- Are popup, lookup, attachment, and child-grid paths preserved?
- Are user-specified object names and business keys unchanged?

## Migration boundary

PB behavior is a source, not a reason to ignore target-project conventions. If PB uses a pattern that conflicts with current target infrastructure, preserve PB business behavior through the target project's methods rather than copying PB structure literally.
