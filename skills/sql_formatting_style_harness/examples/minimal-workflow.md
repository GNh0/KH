# SQL Formatting Style Harness Minimal Workflow Example

## Scenario

An agent formats a stored procedure and claims it followed the host-local `sql-formatting` skill. KH must verify that the claim is supported by preservation and style evidence.

## Expected steps

1. Read the host-local `sql-formatting` skill.
2. Format the SQL using that style.
3. Keep original and formatted SQL as exact passthrough text.
4. Run `verify_sql_formatting_style(original, formatted)`.
5. If the result is blocked, fix formatting or restore changed contract text before completion.

## Expected evidence

- `skill`: `sql-formatting-style-harness`.
- `execution_level`: `python-module`.
- `actual_runtime_path`: `src.skills.sql_formatting_style.verify_sql_formatting_style`.
- `style_contract_source`: host-local path/hash when available.
- `token_optimizer_status`: `passthrough`.
- `semantic_checks.status`: `not_proven` unless DB-backed checks were separately run.

## Failure cases

- A Korean literal changes.
- A comment is removed or uncommented.
- A predicate or JOIN condition changes.
- A new `ELSE` is added.
- The agent claims semantic equivalence without DB-backed evidence.

## Done criteria

- Mechanical preservation checks pass.
- Style checks pass.
- DB/semantic limits are explicitly reported.
- The host-local `sql-formatting` skill remains the formatter; KH only verifies evidence.
