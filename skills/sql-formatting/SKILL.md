---
name: sql-formatting
description: Create, change, format or review SQL/T-SQL query and procedure artifacts using the user's style.
---

# SQL formatting

Execute in the current agent by default. Use the [KH delegation flow](../work-execution/references/delegation.md) only when a bounded specialist task or independent review benefits from a separate agent. An assigned SQL worker completes its scope and returns evidence without further delegation.

For project-file work, use the [scoped application](../work-execution/references/application.md) for the actual `sql-format`, `sql-query`, `sql-select` and/or `sql-save` responsibility and named files. Read the returned required references, then complete the shared [source-style cycle](../work-execution/references/source-style-cycle.md). Document inspection or query explanation alone does not apply code-writing checks.

Do not add or change a value fallback unless the user explicitly requested that substitution. Preserve the actual supplied/stored value; NULLs, blanks, missing legacy data or defensive coding do not authorize replacing it with another field, master/default value, zero or a literal. A request to initialize an input default does not authorize replacing submitted values during SAVE or later SELECT. Changing ISNULL to COALESCE, CASE or another form does not change this rule; preserve unchanged existing handling outside the requested correction.

## Procedure work: SELECT and SAVE

At the first actual SP task, ask whose name belongs in the target AUTHOR header and whose existing SPs to find for style. Reuse explicit answers. Search existing AUTHOR headers for each requested name, read relevant SELECT/SAVE bodies before drafting, and identify the procedures used. Only the target author belongs in the new header. Apply [SP authorship and reference selection](references/procedure-authorship.md) alongside SQL-FORMATTING.

Before creating or changing procedure logic, including SELECT-only/report procedures, read the actual caller, complete approved same-responsibility procedures and the relevant [SELECT/SAVE procedure contracts](references/procedure-contracts.md). Select the changed responsibilities in the [illustrative-pattern index](references/procedure-patterns.md) and read those examples; do not load the whole example collection. Verify the selected structure against the complete procedures. Derive schema, types, keys and behavior from the actual target. When the request adds a caller or operation, cover the added responsibility before drafting it.

Keep one operation's ordered result sets in its owning dispatch block. Do not put additional SELECTs behind a second check of the mode predicate already established by that branch, or append a duplicate mode branch just to return another table. Preserve genuinely different business conditions and required shared phases.

Before changing the target file or executing changed procedure SQL, including rollback tests, compare the exact draft with the selected procedures and each requested rule, including existing code the user explicitly asked to correct. Run the [standalone SQL check](references/checks.md) when available and resolve relevant findings against that draft; preservation success or no errors does not clear `needs_review`. For filters and state changes, establish both qualifying and excluded cases. After the final edit, verify the caller's mode/result-table order and exercise both cases where execution is authorized. Recheck the applied body when deploying.

## Layout and preservation

Apply the [user's SQL style](references/style.md) when generating, editing, or cleaning up SQL. For derived FROM/JOIN sources, align closing and opening parentheses, place inner clauses one space to the right, and align derived JOIN ON/AND with the parentheses. For ordinary table JOINs, align ON/AND with the I in JOIN. This user's general “정리” (cleanup) includes alias normalization by business role. Preserve original aliases for “별칭 그대로” (keep aliases) or “정렬만” (format only). Do not infer roles solely from table names/MAINCD.

Align actual text columns with spaces, including within lists; equal tab counts do not establish alignment. For grouped INSERT/SELECT mappings, use shared column starts that fit both target names and source expressions, and preserve their matching row groups. Check the final token positions, not the number of indentation characters.

For cleanup of supplied SQL alone, deliver the completed SQL directly. Do not rewrite SQL or connect to a database for simple comparison or explanation questions. Preserve semantics, JOIN types/order, conditions, literals, Korean text, existing comments, and output columns/types. SQL generation and database execution are separate request scopes.

For other SQL work, use the [checker](references/checks.md) when it adds evidence. For changes that could alter semantics, such as replacing a function with a JOIN, check actual definitions, NULL behavior, duplicates, row counts, and performance. The checker does not replace database execution.

Keep temporary query files and verification output outside the source project; follow [workspace files](../work-execution/references/workspace-files.md) when creating them.

Use the approved JOIN-based form for lookups, aggregation and inclusion/exclusion in both SELECT and SAVE. Keep query sources in FROM/JOIN rather than adding SELECT/WHERE subqueries or copying row values into scalar variables for convenience. Preserve required IF EXISTS validations and necessary key/output variables. Apply [preferences and exceptions](../work-execution/references/preferences.md) when an actual requirement makes the preferred form unsuitable; verify full keys, NULLs and row cardinality before rewriting. Return the requested complete SQL or exact replacement block.
