---
name: sql-formatting
description: Generate, edit, or format SQL/T-SQL using the scoped KH layout while preserving query behavior and explicit alias-preservation requests.
---

# SQL formatting

Apply the [user's SQL style](references/style.md) when generating, editing, or cleaning up SQL. For derived FROM/JOIN sources, align closing and opening parentheses, place inner clauses one space to the right, and align derived JOIN ON/AND with the parentheses. For ordinary table JOINs, align ON/AND with the I in JOIN. This user's general “정리” (cleanup) includes alias normalization by business role. Preserve original aliases for “별칭 그대로” (keep aliases) or “정렬만” (format only). Do not infer roles solely from table names/MAINCD.

For cleanup of supplied SQL alone, deliver the completed SQL directly. Do not rewrite SQL or connect to a database for simple comparison or explanation questions. Preserve semantics, JOIN types/order, conditions, literals, Korean text, existing comments, and output columns. SQL generation and database execution are separate request scopes.

Read [checker usage](references/checks.md) only when semantic comparison of a cleanup or checks of complex nested JOINs would help. For changes that could alter semantics, such as replacing a function with a JOIN, check actual definitions, NULL behavior, duplicates, row counts, and performance. The checker does not replace database execution.

Do not habitually add unnecessary CTEs, intermediate tables, or WHERE/SELECT subqueries. Apply [preferences and exceptions](../work-execution/references/preferences.md) without mechanically substituting JOINs that change semantics. Return the requested complete SQL or exact replacement block.
