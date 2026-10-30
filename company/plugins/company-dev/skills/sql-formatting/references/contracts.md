# SQL source and procedure contracts

Read the actual caller, target schema and complete approved procedures for the affected operations, including SELECT-only reports. Inspect XML generation only when that contract uses XML. Compare SELECT with relevant SELECT bodies and SAVE with relevant SAVE bodies by responsibility, not just names. Apply selected style while taking input types, lengths, defaults, output names and keys from the actual target.

Keep each operation's ordered result sets in its coherent dispatch block. A mode already established by an enclosing branch does not need rechecking just to return another table. Preserve distinct business conditions and genuinely shared validation/preprocessing; inspect the complete mode/result-set path against its caller rather than classifying every separate IF as wrong.

Preserve batch keys as a set through XML parsing and updates/deletes. Distinguish a display key from raw key components, persisted sequence numbers from XML row order, and single-header data from multiple selected masters. Trace Added/Modified/Deleted states and the actual caller mode strings to procedure branches.

Trace the requested operation through the actual caller and relevant complete procedure bodies. Compare what the existing path already handles with the concrete gap the change must resolve. Select the simplest sufficient implementation that follows the selected style and preserves input cardinality, full keys, related writes, validation and transaction/error ownership. An available API or familiar technique alone does not establish a need for added code. Justify necessary differences from actual behavior, API constraints or measured performance; classify neither necessity nor correctness from a technique's name or shape.

Check persisted numbering within the full target key scope and real transaction/concurrency path. Quantity checks must account for the current document's prior contribution and duplicate linked keys in the submitted batch. Inspect actual units, NULLs, precision and rounding. Do not invent validation solely to make an unfamiliar source look safer.

Change output columns, Designer bindings and affected XML fields together when the request requires it. A renamed binding is not automatically a renamed procedure parameter. Preserve Unicode and meaningful comments. Keep typed placeholders only when the required UNION/result schema needs them.

Inspect actual result types and caller bindings before adding a conversion. Display formatting alone does not require changing a SQL type. Preserve precision, scale and NULLs; derive required empty-schema placeholder types from the actual result contract. A verified data/API requirement can justify a conversion.

For function/JOIN/APPLY rewrites, inspect definitions, duplicates, NULL behavior and actual query plans/results. Compare timing using the same inputs and row counts. Static token comparison cannot verify schema compatibility, performance, numbering or database deployment.
