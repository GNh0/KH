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
- Does XML serialization actually include the intended rows?
- Did unchanged focused rows get `SetModified()` when needed?
- Does the result shape match current bindings?
- Are popup, lookup, attachment, and child-grid paths preserved?
- Are user-specified object names and business keys unchanged?

## Migration boundary

PB behavior is a source, not a reason to ignore target-project conventions. If PB uses a pattern that conflicts with current target infrastructure, preserve PB business behavior through the target project's methods rather than copying PB structure literally.
