---
name: sql-formatting
description: Generate, edit, or format SQL/T-SQL using the scoped KH layout while preserving query behavior and explicit alias-preservation requests.
---

# SQL formatting

For project code generation/edits, complete the required [source-style cycle](../work-execution/references/source-style-cycle.md): read actual comparison-project SQL before writing, then re-read and audit the final SQL after all edits.

Apply the [user's SQL style](references/style.md) when generating, editing, or cleaning up SQL. For derived FROM/JOIN sources, align closing and opening parentheses, place inner clauses one space to the right, and align derived JOIN ON/AND with the parentheses. For ordinary table JOINs, align ON/AND with the I in JOIN. This user's general “정리” (cleanup) includes alias normalization by business role. Preserve original aliases for “별칭 그대로” (keep aliases) or “정렬만” (format only). Do not infer roles solely from table names/MAINCD.

Align actual text columns with spaces, including within lists; equal tab counts do not establish alignment. For grouped INSERT/SELECT mappings, use shared column starts that fit both target names and source expressions, and preserve their matching row groups. Check the final token positions, not the number of indentation characters.

For cleanup of supplied SQL alone, deliver the completed SQL directly. Do not rewrite SQL or connect to a database for simple comparison or explanation questions. Preserve semantics, JOIN types/order, conditions, literals, Korean text, existing comments, and output columns/types. SQL generation and database execution are separate request scopes.

Read [checker usage](references/checks.md) only when semantic comparison of a cleanup or checks of complex nested JOINs would help. For changes that could alter semantics, such as replacing a function with a JOIN, check actual definitions, NULL behavior, duplicates, row counts, and performance. The checker does not replace database execution.

For generated or migrated procedures, read the actual caller and complete approved procedures with the same operation/responsibility before writing. Use the user's named comparison project, otherwise an approved comparable other project; previously generated or rejected code is not the style baseline. Apply their recurring writing style under the current agreed rules, while deriving schema/APIs and behavior from the actual target. Read [target save contracts](references/save-contracts.md) for operation/result-set ownership, key parsing, actual schema dimensions, XML, related writes and transaction/error ownership. Before completion, compare the actual changed bodies with those selected examples and resolve unsupported departures; a source-read log, formatting pass or successful DB sample alone does not establish style compliance.

Keep temporary query files and verification output outside the source project; follow [workspace files](../work-execution/references/workspace-files.md) when creating them.

Do not habitually add unnecessary CTEs, intermediate tables, or WHERE/SELECT subqueries. Apply [preferences and exceptions](../work-execution/references/preferences.md) without mechanically substituting JOINs that change semantics. Return the requested complete SQL or exact replacement block.

Before final handover, complete the shared [rule audit](../rule-audit/SKILL.md) for this task's applicable rules.
