# SQL Formatting Bridge

This harness composes with host-local `sql-formatting` and `sql-formatting-style-harness`.

## Responsibilities

- `pb-to-csharp-migration-harness`: caller/SP contract, result/write shape, migration rules, and completion evidence.
- `sql-formatting`: presentation-only SQL formatting.
- `sql-formatting-style-harness`: deterministic preservation and style evidence.

## Normal Generation

1. Preserve supplied SQL as source-text passthrough.
2. Generate SQL only from the packaged style contract and current request evidence.
3. Apply the host-local formatter when SQL formatting is requested or required.
4. Run the formatting verifier against the exact original/final pair when proof is required.
5. Keep `semantic_checks.status=not_proven` unless the user supplies independently validated execution evidence.

Normal generation does not query a database or inspect local SQL source. Database/source discovery belongs only to the maintenance-only profile-update workflow, which never runs during normal generation.

## Boundaries

- Formatting must not alter parameters, predicates, joins, calculations, literals, comments, result order, or write behavior.
- Scalar-function conversion and schema-dependent rewrites require a separate explicit semantic-refactor request and authoritative evidence.
- Do not introduce CTEs, temporary tables, `MERGE`, `NOT EXISTS`, or tuning rewrites by default.
- Do not report database equivalence from lexer, formatter, or static migration checks.

SQL text remains uncompressed. Noisy verifier output may be summarized only when the procedure identifier, branch, issue code, line, failing statement, and exit code remain available.
