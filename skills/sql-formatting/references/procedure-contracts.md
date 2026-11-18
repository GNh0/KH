# SELECT/SAVE procedure contracts

Choose a working procedure written by the selected reference author for each responsibility. Read the complete SELECT or SAVE and its actual caller. Use the target's schema and behavior and the [authorship and header rules](procedure-authorship.md).

## Save boundary and reuse

- Identify the definition used for deployment and any maintained copies. Resolve differences against the actual caller.
- Trace what the existing operation already does. Add only the missing behavior. Preserve validation, row counts, full keys, transaction ownership and error cleanup.
- Keep requested disabled integrations as their complete commented bodies. Retrieve any missing part of the reference before writing.
- Before applying a draft and again after saving, compare its operations with the original. For each new mode, write, call or result type, identify the request or caller that needs it.

### XML preparation and writes

- When adding an XML action, check which documents the caller sends, where the target prepares them and which operations share cleanup. Reuse that boundary.
- Keep XML/selected row values in their rowset through INSERT SELECT, UPDATE FROM or DELETE JOIN. Apply required expressions at the owning write.
- Use scalars for genuinely single-document outputs, number allocation or required API parameters. Update staging when generated keys must be recorded. See [procedure patterns](procedure-patterns.md).

## Modes and multiple rows

- Give each operation a coherent dispatch branch. Match the target's IF/ELSE IF flow and return all of that mode's tables in caller order.
- Use separate branches for different keys, joins or exclusions. Keep shared validation and preprocessing at their existing scope. Verify each caller's path.

### Save row operations

- Match the caller's actual mode strings and Added/Modified/Deleted selection to the SAVE branches. Preserve the required XML log call at its original scope.

### Composite keys

- For composite keys, read the target's parser and a complete same-project usage. Join on the typed components of the full key. Preserve NULL behavior and row count.
- Keep parsing in the established place. Avoid concatenating table columns or introducing scalars to reconstruct available keys.

### Save batches and transitions

- Preserve the set of selected master keys through XML and UPDATE/DELETE. Removing detail rows and deleting persisted documents have different owners.
- Trace print/save selection, state and batch width. Keep SELECT's scalar/key transport when the XML change concerns only SAVE.
- Allocate sequence numbers within the actual parent key and transaction. Verify deterministic ordering, multiple inserts and a second append. Use locking hints only with an established requirement and user authorization where applicable.
- Compare proposed quantities in the correct units by full linked key. On edits, exclude the document's old contribution. Combine duplicate keys and include additions, changes and deletions. Preserve existing validation.
- For eligibility, identify the current row, linked prerequisites and status update separately. Test included and excluded cases and one-to-many joins. Keep sample IDs out of business filters.

## Parameters, outputs and dates

- Follow the target's parameter template. Current screen procedures require WORKTYPE and ORGDIV. Ordinary optional parameters generally default to NULL.
- Trace schema → parameter/XML/staging → result → caller. Preserve actual lengths, Unicode, precision, scale and NULL handling. Check master code/name fields against the real master.
- Return the original calculation type unless the consuming contract needs a conversion. A display format belongs to the display layer. SQL aggregates can widen a numeric result.
- Keep binding names, result fields and SP parameter names distinct. Remove excluded outputs and corresponding Designer bindings together.
- Return persisted and submitted values directly. A **new or changed NULL/blank substitution requires the user's explicit request for that operation**. An editor default applies at initialization. Preserve existing handling outside the edit.
- Use typed empty placeholders only when a real UNION or result schema needs that field. Verify the type against the consuming branch.
- Preserve application, inspection and audit dates separately. Trace the actual writer, date filters, remarks, and INSERT column/value pairs. For a server-owned save time, retain GETDATE() and the caller's established requery.
- Check the saved procedure against its caller, selected reference, signature, XML shape, keys, writes, result order and error path. Verify affected schema, concurrency and deployment separately. See [SQL checks](checks.md).

For example, if the caller already consumes the aggregate below, changing the display to four decimal places gives no reason to narrow the SQL result.

```sql
SELECT SUM(A.AMOUNT) AS AMOUNT
FROM ExampleLine A
```
