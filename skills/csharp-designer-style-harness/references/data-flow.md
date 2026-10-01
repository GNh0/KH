# Actual data and event flow

For a full-screen request, identify the permitted operations first, then trace Load/initControl → Search → detail → protection → the requested commands → requery/focus restoration. Also connect actual permissions such as BA060T and CustomButton/SimpleButton/U_BUTTON behavior. Do not add add/copy/delete/navigation merely because the base toolbar supports them, or reimplement the full lifecycle for a local edit.

Follow current SearchCommand/NewCommand/DeleteCommand and m_Editmode flow. Do not duplicate initialization or confirmation messages. Distinguish focus via GetFocusedDataRow()/FocusedRowHandle from checked selection via the actual selection collection. Do not confuse screen sort order with selection return order.

Read the actual target command bodies before copying a flow. Compare Save with Save and Search with Search, including their helper/base calls. If the reference Save only calls CallSaveProcedure, reports success and dispatches Search, do not also insert AcceptChanges, control protection or a mode reset that Search already owns. Conversely, preserve a Save reset required by the target's tab/detail flow. AcceptChanges and DataEditMode.DEFAULT are not globally banned: their timing and row-state effects must follow the actual XML/save contract. A foreign screen can supply business behavior without supplying this target's event structure.

At completion, compare implemented and wired commands with the latest request, and compare the changed event bodies with the selected project source. Resolve differences in the real call path rather than treating a build, familiar method name, skill read or static pass as evidence of compliance. For an automated comparison, use the optional C# reference and explicit command scope in [checks](checks.md).

## Connecting functionality to an existing screen

First read the user's current screen and queries. The migration source defines business behavior; the current project defines control APIs, event structure, and DB call patterns. Do not copy an event body verbatim merely because its name matches if header/detail population timing or state differs. Use actual call paths to determine whether the source's separate queries, rebinding, or validation are needed in the target.

| Task | Current contract to inspect first | Implementation rule |
| --- | --- | --- |
| Enter new mode | Existing DataTable schema and InitControl's actual scope | Use current initialization. Do not conventionally add an empty DETAIL query. Distinguish targets without a schema that actually need the query. |
| Enter edit mode | Whether focus/detail events already bind the header and rows | Preserve values and switch mode/tabs. Query only needed data, such as item lists. Do not prohibit requerying when the current contract requires it. |
| Remove detail rows | Actual GridView API, row states, and selection scope | Prefer an existing API such as DeleteSelectedRows when removing editable detail rows. Build GetSelectedRows/GetDataRow/Delete loops only for required per-row additional behavior. |
| Delete persisted master documents | Selected master keys, CallSaveProcedure's DELETE branch, and XML row-state selection | Follow the current master-XML deletion pattern. Do not substitute a detail-row deletion API or reduce multiple selected documents to the focused row. |
| Add detail | Where keys, business site, parent number, and sequence are set: SP parameters or XML | Assign only fields required in actual detail XML. Do not duplicate server numbering with DataRowVersion/Math.Max. |
| Save/delete all | Current CallSaveProcedure calls, confirmation/success messages, and row states on failure | Follow current branches. Do not invent required-value, zero-value, or count restrictions or separate confirmation steps. Preserve existing required validation and error handling. |
| Initialize dates | The user control's actual methods and current screen usage | Use an available API such as SetToDay(int) if it matches the requirement. Do not assume another date control has that method. |

Do not wrap item-addition DataRow handling, query binding, or focus handling in new wrappers such as CreateSelectedRowsTable/BindSelectProcedure. If the project writes this directly in existing events/save methods, keep that approach. Helpers with an actual reuse requirement and an established target structure remain permitted; these method names are not themselves prohibited.

Do not introduce a screen-state bool absent from the original to impose new restrictions on editing, deletion, attachments, or button Enabled/ReadOnly. A status value in query results, or a plausible reason to block changes in a state, does not justify a new business rule. Implement that state and branching only when the current request or actual existing contract requires them. This does not globally prohibit variable names, bools, or ternaries. After style feedback, check field declarations, initialization, query assignments, and every usage together, not just the cited line.

After style feedback, also recheck validation, initialization, requerying, and wrappers added in the same change. When asked to remove your changes, revert only your changes while preserving current user edits, and do not reintroduce rejected implementations in a new version. A pre-task copy establishes change provenance; it does not override later user corrections.

Retain named event handlers and existing CallSelectProcedure/CallSaveProcedure boundaries per the [user's coding style](coding-style.md). Check actual semantics of ExecSP/ExecSPTrn and GetEditModeWorkType/original mode strings; do not standardize them for style alone. First inspect whether the existing master-to-table helper handles cloning/row states, and do not add unnecessary Clone calls or intermediate tables.

Align NEW/MOD/DEL and Added/Modified/Deleted with the actual XML generator and SELECT/SAVE branches. Do not invent delete-all/reinsert behavior, modification of every row, or batch atomicity. Do not duplicate in C# validation assigned to SAVE. Compare parameters, XML fields, numbering, fixed values, and result tables.

## Save modes, selection and binding

For the current FrmDevBase save pattern, derive `@WORKTYPE` from the actual edit-mode API, such as `m_Editmode.ToString()` and any established casing conversion. Read that API and the SP branches together; do not replace it with a literal `"NEW"`/`"MOD"` just because the screen currently has one button. A genuinely fixed special operation remains valid when required by the target contract. Keep SELECT enum values separate from SAVE edit modes.

For persisted master deletion, inspect how the target marks selected Unchanged rows Modified and either imports those rows into the established XML table or serializes the appropriate master table. This prescribed Clone/ImportRow use can be necessary even though intermediate tables are generally disfavored. Verify selected-row scope, TableName, row states, and the SP's set-based key JOINs; a scalar header variable cannot represent several selected documents. Do not impose one variant on every screen.

Use the existing DataRowState/XML selection to choose changed rows. Do not add repeated `Equals(..., DataRowVersion.Original)` checks for every field, redundant `GetChanges`, `CloseEdit`, `PostEditor`, or `UpdateCurrentRow` without inspecting the actual save/editor path. Reading a deleted row's Original key is a separate valid requirement. Keep failed-save state and pending edits intact.

Bind lookup/popup display names and persisted codes according to the actual target. If the user specifies a visible USERNM control and a hidden USERID input, initialize and populate both and pass the hidden input's EditValue to the query. Do not invent a state field or store that ID in Tag. A requested FieldName/BindingField rename does not by itself require renaming an SP parameter: inspect and change each affected caller/result binding within scope.

In FocusedRowChanged, apply the existing edit-mode row-movement guard before a negative/filter-row early return when that return could bypass protection. Preserve tab/input/detail data during requery according to the current request. Use the target's `Usr_ControlsProtect` or equivalent protection path for edit-state colors and availability; do not simulate it with arbitrary Designer colors.

When creating or changing SAVE procedures, also apply the [SQL save contracts](../../sql-formatting/references/save-contracts.md). A full screen migration needs the target's actual caller/XML/SP chain; compilation and a similarly named foreign procedure do not establish that chain.

## Preserving original integrations as comments

A request to comment out an original integration, such as Amaranth (아마란스) or electronic tax invoices, means retaining its actual body while disabling execution. Do not replace complete methods or related SQL branches with explanations, empty method lists, or TODOs. Do not activate JOINs, validation, or filters already commented out in the original during migration. Replacing related columns with empty strings, 0, or CAST is also a behavior change; do not do it arbitrarily. Compare the original body with retained candidate content, and separately compare active calls/bindings.

Resolve table/API differences from actual target schemas and implementations. Do not turn a comment-preservation request into a requirement to execute the entire original, or invent business restrictions/return values to pass a build. Static style checks alone do not establish string/comment preservation or runtime behavior.

Prefer existing for/DataTable.Select/NewRow/Rows.Add patterns. In the relevant upload case, add valid rows directly to the target, skip invalid rows, and report their errors together. Do not use that case to decide atomicity for other uploads. Inspect actual Excel sheets, cell types, headers, keys, and dates.

For TY user lookups, distinguish query RTRUSER from input/edit USER within the requested scope. Follow the specified existing C# style, including get blocks and separate parsing/comparison if statements. Reuse shared functionality when duplication needs removal, after reading the actual helper contract.
