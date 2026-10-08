# SQL source and procedure contracts

Read the actual caller, XML generator, target schema and approved project procedure before changing a SELECT/SAVE contract. Match input types, lengths, defaults, output names and target keys. Do not infer these from a similar program number or another company's schema.

Preserve batch keys as a set through XML parsing and updates/deletes. Distinguish a display key from raw key components, persisted sequence numbers from XML row order, and single-header data from multiple selected masters. Trace Added/Modified/Deleted states and the actual caller mode strings to procedure branches.

Check persisted numbering within the full target key scope and real transaction/concurrency path. Quantity checks must account for the current document's prior contribution and duplicate linked keys in the submitted batch. Inspect actual units, NULLs, precision and rounding. Do not invent validation solely to make an unfamiliar source look safer.

Change output columns, Designer bindings and affected XML fields together when the request requires it. A renamed binding is not automatically a renamed procedure parameter. Preserve Unicode and meaningful comments. Keep typed placeholders only when the required UNION/result schema needs them.

Inspect actual result types and caller bindings before adding a conversion. Display formatting alone does not require changing a SQL type. Preserve precision, scale and NULLs; derive required empty-schema placeholder types from the actual result contract. A verified data/API requirement can justify a conversion.

For function/JOIN/APPLY rewrites, inspect definitions, duplicates, NULL behavior and actual query plans/results. Compare timing using the same inputs and row counts. Static token comparison cannot verify schema compatibility, performance, numbering or database deployment.
