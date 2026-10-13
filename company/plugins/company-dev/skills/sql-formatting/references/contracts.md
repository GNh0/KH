# SQL source and procedure contracts

Read the actual caller, XML generator, target schema and approved project procedure before changing a SELECT/SAVE contract. Match input types, lengths, defaults, output names and target keys. Do not infer these from a similar program number or another company's schema.

Preserve batch keys as a set through XML parsing and updates/deletes. Distinguish a display key from raw key components, persisted sequence numbers from XML row order, and single-header data from multiple selected masters. Trace Added/Modified/Deleted states and the actual caller mode strings to procedure branches.

Choose the persistence boundary from the requested operation and approved procedure structure. Query fields or matching tables do not make another screen's save procedure a reusable service. Read its relevant branches and compare input cardinality, keys, related writes, validation and transaction/error ownership. For batch edits/deletes, prefer compatible direct batch DML; cursors, XML re-encoding and per-row dispatch require a verified need or approved callable contract. Preserve necessary related-table behavior and review restrictions when the caller's scope differs.

The shared checker reviews recognizable OPENXML → loop-local FOR XML variable → static procedure dispatch as `xml_reencode_dispatch_review`. This warning requires source review and does not prohibit required cursor/EXEC/XML use. Unchanged loops are excluded with an original; indirect flows, effective branch values and callee behavior remain unverified.

Check persisted numbering within the full target key scope and real transaction/concurrency path. Quantity checks must account for the current document's prior contribution and duplicate linked keys in the submitted batch. Inspect actual units, NULLs, precision and rounding. Do not invent validation solely to make an unfamiliar source look safer.

Change output columns, Designer bindings and affected XML fields together when the request requires it. A renamed binding is not automatically a renamed procedure parameter. Preserve Unicode and meaningful comments. Keep typed placeholders only when the required UNION/result schema needs them.

Inspect actual result types and caller bindings before adding a conversion. Display formatting alone does not require changing a SQL type. Preserve precision, scale and NULLs; derive required empty-schema placeholder types from the actual result contract. A verified data/API requirement can justify a conversion.

For function/JOIN/APPLY rewrites, inspect definitions, duplicates, NULL behavior and actual query plans/results. Compare timing using the same inputs and row counts. Static token comparison cannot verify schema compatibility, performance, numbering or database deployment.
