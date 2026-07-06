# SQL Formatting Bridge

This harness composes with the host-local `sql-formatting` skill.

## Division of responsibility

- `sql-formatting`: formats, cleans, and standardizes SQL/T-SQL.
- `sql-formatting-style-harness`: verifies preservation and style evidence.
- `pb-to-csharp-migration-harness`: decides migration flow, PB evidence, C# style, SP target shape, and completion checklist.

## Required behavior

1. Preserve original SQL as source-of-truth passthrough text.
2. Apply the host-local formatter when formatting or generating SQL is required.
3. Run `verify_sql_formatting_style(original, formatted)` when proof is required.
4. Treat `semantic_checks.status=not_proven` as a real limitation when DB behavior matters.
5. Use DB-backed checks for scalar-function conversion, target schema differences, performance claims, or result equivalence.

## Token optimizer policy

SQL/stored procedure text is contract-sensitive. Do not summarize or minify it. Token optimizer may summarize noisy command output from SQL verification only if it preserves procedure name, branch, error code, line number, failing statement, and exit code.

## Default recommendation policy

Do not recommend CTE, `#` temporary table, `MERGE`, `NOT EXISTS`, nested `WHERE` subqueries inside `IF EXISTS` guards, scalar-function-to-join conversion, or performance tuning just because the SQL looks cleaner that way. Those are exceptions requiring a concrete reason or user request.
