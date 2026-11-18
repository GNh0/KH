# Actual data and event flow

For full screens, trace Load/initControl → Search → detail → protection → requested commands → requery and focus. Read actual permissions, toolbar and custom-button paths. For a local edit, trace only the affected flow.

## Connecting functionality to an existing screen

| Operation | Establish from the current screen |
| --- | --- |
| New | Reuse existing initialization and DataTable schema. Query empty DETAIL only if needed for that schema. |
| Edit | Preserve bound values and switch to the established edit mode and tab. Fetch only missing data. |
| Remove editable detail | Use the established GridView API. Add per-row processing only for a required effect. |
| Delete persisted documents | Save the selected master keys as the expected XML rowset. A focus call returns one row. |
| Add detail | Use NewRow, field assignment and Rows.Add. Put keys and numbering in their established owner. |
| Save/delete | Keep current confirmations, validation, error messages and pending changes on failure. |
| Initialize dates | Read the actual control API and same-screen usage before choosing a date helper. |
| Change number display | Trace DB expression, DataColumn, editor and report. Preserve numeric type, precision and NULLs unless a verified consumer requires conversion. |

- Keep named handlers and existing query/save boundaries. Read the actual helper including its return value, schema cloning and DataRowState behavior before adding code. See [coding style](coding-style.md).
- Use direct DataTable operations when the project does. Add a helper, state flag, restriction or extra query only for a concrete gap. A status column alone does not grant permission to change button or edit behavior.
- After feedback, inspect declarations, initialization, assignments and uses together. Revert only your changes, preserve later user edits and re-read the final caller and SP.

## Save modes, selection and binding

- Read the caller's actual save operation and the full comparable implementation. Trace mode, checked keys, TableName, row states, XML generation, transaction, result and requery. Inspect ExecSP/ExecSPTrn and the actual edit-mode API.
- Derive WORKTYPE from the established edit-mode API for ordinary saves. Use a fixed mode for an actual dedicated operation. Match the exact strings to the SP.
- Keep selected rows in the established batch. Printed pages per row do not imply separate DB saves. Distinguish checked rows, focused rows and sorted order. Keep SELECT, SAVE and print boundaries independently grounded.
- Use the existing DataRowState/XML change selection. Clone/ImportRow when required for selected master keys. Read deleted Original keys where necessary. Avoid redundant comparison, commit, validation and delete/reinsert steps.
- Requery via the existing success path. If the SP owns GETDATE(), add an output parameter only for a verified caller need.
- Bind visible names and stored codes to their actual controls. For a specified hidden USERID, use its EditValue. Match FieldName, XML and query parameter contracts independently.
- Apply edit-mode movement protection before any early return that bypasses it. Preserve selection and details. Use the screen's protection routine for availability and colors.
- Follow the [SQL workflow](../../sql-formatting/SKILL.md) for SP changes. Compare actual schema, parameter names/types, XML keys and ordered results.

| C# source | Verify in the paired source |
| --- | --- |
| DataRowToPanel / MasterToDataTable | Read the target library overload for BindingField, key handling and hidden/bound controls. |
| DataTableToXml | Follow TableName and selected row states into the actual XML root, row path and OPENXML mapping. |
| BindingCode / BindingorgdivCode | Check the overload's organization argument and the target editor's value/display columns. |
| GetDataSetFromSP / ExecSPTrn | Compare one call's literal parameter names with the actual SP using `kh_check.py sp-call`. Trace the mode, output direction, result order and grid FieldName in the caller. |

## Preserving original integrations as comments

- Keep the original integration body and disable its execution when requested. Preserve already-commented JOINs and filters. Verify actual calls, fields, bindings and schemas separately.
- For uploads, inspect the actual workbook headers, types, dates and keys. Use the target's direct DataTable loop. If requested to save valid rows and collect errors, keep that behavior local to that upload.
- For TY lookup changes, distinguish query RTRUSER from edit USER. Keep established get blocks and separate parsing and comparison conditions.
