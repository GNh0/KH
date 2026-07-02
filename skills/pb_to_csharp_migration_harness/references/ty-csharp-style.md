# TY C# Style

Use this reference before drafting or reviewing TY/C_KONE110 C# migration code.

## Core style

- Preserve the existing class, namespace, control names, event handler names, and method names unless the user asks for refactoring.
- Reuse existing screen flow. Do not create a parallel helper method if `CallViewQuery`, `CallProc`, or another current method already owns the same stored-procedure path.
- Prefer small, same-shape patches over broad redesign.
- Treat the active checkout and active screen binding as source of truth. Duplicate TY trees are common; verify the target tree before applying style.

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

PB behavior is a source, not a reason to ignore TY conventions. If PB uses a pattern that conflicts with current TY infrastructure, preserve PB business behavior through TY-style methods rather than copying PB structure literally.
