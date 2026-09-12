# Actual data and event flow

For a full-screen request, check Load/initControl → Search → detail → protection → add/copy/edit/delete/save/cancel → requery/focus restoration. Also connect actual permissions such as BA060T and CustomButton/SimpleButton/U_BUTTON behavior. Do not require reimplementing the full lifecycle for a local edit.

Follow current SearchCommand/NewCommand/DeleteCommand and m_Editmode flow. Do not duplicate initialization or confirmation messages. Distinguish focus via GetFocusedDataRow()/FocusedRowHandle from checked selection via the actual selection collection. Do not confuse screen sort order with selection return order.

## Connecting functionality to an existing screen

First read the user's current screen and queries. The migration source defines business behavior; the current project defines control APIs, event structure, and DB call patterns. Do not copy an event body verbatim merely because its name matches if header/detail population timing or state differs. Use actual call paths to determine whether the source's separate queries, rebinding, or validation are needed in the target.

| Task | Current contract to inspect first | Implementation rule |
| --- | --- | --- |
| Enter new mode | Existing DataTable schema and InitControl's actual scope | Use current initialization. Do not conventionally add an empty DETAIL query. Distinguish targets without a schema that actually need the query. |
| Enter edit mode | Whether focus/detail events already bind the header and rows | Preserve values and switch mode/tabs. Query only needed data, such as item lists. Do not prohibit requerying when the current contract requires it. |
| Delete selected rows | Actual GridView API, row states, and selection scope | Prefer existing APIs such as DeleteSelectedRows. Build GetSelectedRows/GetDataRow/Delete loops only for required per-row additional behavior. |
| Add detail | Where keys, business site, parent number, and sequence are set: SP parameters or XML | Assign only fields required in actual detail XML. Do not duplicate server numbering with DataRowVersion/Math.Max. |
| Save/delete all | Current CallSaveProcedure calls, confirmation/success messages, and row states on failure | Follow current branches. Do not invent required-value, zero-value, or count restrictions or separate confirmation steps. Preserve existing required validation and error handling. |
| Initialize dates | The user control's actual methods and current screen usage | Use an available API such as SetToDay(int) if it matches the requirement. Do not assume another date control has that method. |

Do not wrap item-addition DataRow handling, query binding, or focus handling in new wrappers such as CreateSelectedRowsTable/BindSelectProcedure. If the project writes this directly in existing events/save methods, keep that approach. Helpers with an actual reuse requirement and an established target structure remain permitted; these method names are not themselves prohibited.

Do not introduce a screen-state bool absent from the original to impose new restrictions on editing, deletion, attachments, or button Enabled/ReadOnly. A status value in query results, or a plausible reason to block changes in a state, does not justify a new business rule. Implement that state and branching only when the current request or actual existing contract requires them. This does not globally prohibit variable names, bools, or ternaries. After style feedback, check field declarations, initialization, query assignments, and every usage together, not just the cited line.

After style feedback, also recheck validation, initialization, requerying, and wrappers added in the same change. When asked to remove your changes, revert only your changes while preserving current user edits, and do not reintroduce rejected implementations in a new version. A pre-task copy establishes change provenance; it does not override later user corrections.

Retain named event handlers and existing CallSelectProcedure/CallSaveProcedure boundaries per the [user's coding style](coding-style.md). Check actual semantics of ExecSP/ExecSPTrn and GetEditModeWorkType/original mode strings; do not standardize them for style alone. First inspect whether the existing master-to-table helper handles cloning/row states, and do not add unnecessary Clone calls or intermediate tables.

Align NEW/MOD/DEL and Added/Modified/Deleted with the actual XML generator and SELECT/SAVE branches. Do not invent delete-all/reinsert behavior, modification of every row, or batch atomicity. Do not duplicate in C# validation assigned to SAVE. Compare parameters, XML fields, numbering, fixed values, and result tables.

## Preserving original integrations as comments

A request to comment out an original integration, such as Amaranth (아마란스) or electronic tax invoices, means retaining its actual body while disabling execution. Do not replace complete methods or related SQL branches with explanations, empty method lists, or TODOs. Do not activate JOINs, validation, or filters already commented out in the original during migration. Replacing related columns with empty strings, 0, or CAST is also a behavior change; do not do it arbitrarily. Compare the original body with retained candidate content, and separately compare active calls/bindings.

Resolve table/API differences from actual target schemas and implementations. Do not turn a comment-preservation request into a requirement to execute the entire original, or invent business restrictions/return values to pass a build. Static style checks alone do not establish string/comment preservation or runtime behavior.

Prefer existing for/DataTable.Select/NewRow/Rows.Add patterns. In the relevant upload case, add valid rows directly to the target, skip invalid rows, and report their errors together. Do not use that case to decide atomicity for other uploads. Inspect actual Excel sheets, cell types, headers, keys, and dates.

For TY user lookups, distinguish query RTRUSER from input/edit USER within the requested scope. Follow the specified existing C# style, including get blocks and separate parsing/comparison if statements. Reuse shared functionality when duplication needs removal, after reading the actual helper contract.
