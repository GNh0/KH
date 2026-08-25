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
4. Run the formatting verifier against the exact original/candidate pair and retain its structured result as a non-empty `verifier_history` entry.
5. Run `guard_and_bind_verified_sql_final_response` (or the packaged SQL provider CLI that calls it) against the exact original, candidate, fenced final response, authoritative provider path, selected-active provider path, correlated `provider_selection` evidence, and that verifier history.
6. Require the history/binding verification IDs and original/candidate hashes to match, and require the release's nested binding to equal the exposed binding.
7. Deliver SQL only when the binder receipt hashes the exact final response and reports the authoritative provider plus successful deterministic verification. Reading this bridge or obtaining a style-verifier success alone is not delivery authorization.
8. Keep `semantic_checks.status=not_proven` unless the user supplies independently validated execution evidence.

Normal generation does not query a database or inspect local SQL source to learn style. Live database equivalence or deployment verification, when explicitly requested and authorized, is separate completion evidence. The packaged-profile maintenance API accepts only its exact authorized C# artifact pair and does not use database or SQL discovery.

## Boundaries

- Formatting must not alter parameters, predicates, joins, calculations, literals, comments, result order, or write behavior.
- Scalar-function conversion and schema-dependent rewrites require a separate explicit semantic-refactor request and authoritative evidence.
- Do not introduce CTEs, temporary tables, `MERGE`, `NOT EXISTS`, or tuning rewrites by default.
- Do not report database equivalence from lexer, formatter, or static migration checks.
- Do not reconstruct, summarize, or manually paste a different SQL block after binding. Any final-response change requires a fresh binder receipt.
- Missing or mismatched provider-selection evidence, selected-active path, provider path, final response, verifier hashes, or release readiness blocks delivery.
- Missing, empty, or uncorrelated verifier history blocks delivery.
- An `approved_inferred_draft` remains pending even when SQL formatting and final-response binding succeed; binding proves formatting provenance, not PB/DB semantics.

SQL text remains uncompressed. Noisy verifier output may be summarized only when the procedure identifier, branch, issue code, line, failing statement, and exit code remain available.
