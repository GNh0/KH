# Target procedure and save contracts

Use this for generating, migrating or correcting SELECT/SAVE procedures. Ordinary formatting of supplied SQL preserves its existing behavior and does not trigger a schema redesign.

Read the current caller, XML generator, target table keys/types and complete approved same-project procedures for the affected operations. Compare SELECT with relevant SELECT bodies and SAVE with relevant SAVE bodies; choose by actual responsibility, not just a similar name or shared query data. Apply their recurring structure and syntax within the current agreed style while adapting the actual target contract. Keep the original business behavior within the latest requested scope. Retain requested commented integrations as their full original bodies rather than activating them, replacing them with placeholder values, or reducing them to explanatory comments.

## Save boundary and reuse

Trace the requested operation through the actual caller and relevant complete procedure bodies. Compare what the existing path already handles with the concrete gap the change must resolve. Select the simplest sufficient implementation that follows the agreed style and preserves input cardinality, full keys, related writes, validation and transaction/error ownership. An available API or familiar technique alone does not establish a need for added code. Justify necessary differences from actual behavior, API constraints or measured performance; classify neither necessity nor correctness from a technique's name or shape. Resolve material omissions from truncated output.

## Modes and multiple rows

Match actual edit-mode strings and XML Added/Modified/Deleted states to SP branches. A target that sends EDIT must not be implemented only as MOD. Preserve the established `sp_XML_LOG_SAVE` integration when the target pattern/request requires it.

Separate removal of detail rows from deletion of persisted master documents. Multiple selected master keys must remain a set through XML parsing and UPDATE/DELETE JOINs. Do not replace those keys with one scalar `@PURNUM`-like assignment. A scalar header value can still be appropriate in an actual single-document NEW/EDIT branch.

For other selected-row actions, including saving print status, trace the comparable caller's XML/state selection and save boundary before designing the signature. Preserve its set-based keys and applicable MOD branch; per-record printed pages alone do not establish per-record SP calls.

A SAVE XML requirement does not itself change SELECT transport. Keep the existing scalar/key lookup when that is the actual query contract; introduce SELECT XML only for a query-specific requirement or verified dependency.

Assign persisted sequence numbers within the real target key scope. XML row order/SEQ is not automatically the persisted detail key. When appending to an existing parent, verify its current maximum plus deterministic ROW_NUMBER/order and the actual transaction/concurrency path; test multiple new rows and another append to that same parent. Do not add UPDLOCK/HOLDLOCK routinely to compensate for an untraced numbering path. Use hints when the current requirement or verified concurrency behavior actually needs them.

For upstream quantity checks, use the full linked key and the correct unit. On EDIT, exclude the current document's old contribution from already-processed totals before comparing proposed values. Inspect Added/Modified/Deleted together and aggregate duplicate linked keys in the proposed batch. Preserve restrictions already required by the source; do not invent new zero/count/required-value rules or duplicate SP-owned validation in C#.

## Parameters, outputs and dates

Use the approved parameter template: in this user's current screen procedures WORKTYPE and ORGDIV are required, while ordinary optional parameters generally default to NULL. Apply actual target types/lengths instead of copied literal defaults. Match CUSTCD/CUSTNM to the real master schema. Preserve Unicode when meaningful, including XML and actual password/encrypted-value contracts; do not batch-convert every NVARCHAR to VARCHAR.

Trace actual column/result types and caller bindings before adding conversions. A display-format change alone does not require a different SQL numeric type; preserve actual precision, scale and NULL behavior unless a verified data/API requirement needs the conversion. For required empty-schema or UNION placeholders, derive the type from that real result contract.

Keep FieldName/output-column names distinct from SP parameter names. A request to bind PURNUM does not necessarily rename KEYCODE parameters. Change SELECT output, C# binding and relevant XML/SAVE fields together where required by the request.

Remove excluded source-only output columns and their Designer references. Do not keep them alive as `CAST('' AS VARCHAR(...))` or typed NULL fields merely to make a copied screen compile. A typed placeholder can be valid for a required UNION/result schema; verify that specific need. Return persisted judgment/status codes directly unless a defined fallback is required. Do not synthesize a code from quantities merely to display a plausible default.

Distinguish application/request dates from result/inspection dates. Trace which screen writes each field before reusing REGDT or a mutable result date. Copy date filtering/conversion only when it matches the target field type and approved procedure pattern. Preserve requested remarks, modification audit fields and INSERT column/value correspondence.

If the request assigns a save timestamp to GETDATE(), generate it in the SP. Do not add a timestamp input/OUTPUT solely to patch the grid when the caller's established success path requeries. Keep outputs that the actual caller needs.

At completion compare the actual caller, XML shape, SP signature/branches, target keys, related writes, error/transaction path and returned fields with the requested operation and approved structure. The optional checker reviews lexical/layout patterns, new locking hints and typed empty output aliases; it does not prove implementation necessity, schema compatibility, correct numbering, concurrency, business validation or actual DB deployment.
