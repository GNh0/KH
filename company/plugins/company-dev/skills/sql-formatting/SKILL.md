---
name: sql-formatting
description: Write, edit or format SQL/T-SQL using the current project and employee style while preserving the requested data behavior.
---

# SQL formatting

Read the [selected personal SQL style](../../references/personal-style.md) and relevant approved project SQL. Use those choices for case, aliases and layout; preserve unspecified existing choices.

For project code generation/edits, complete the required [source-style cycle](../work-execution/references/source-style-cycle.md): inspect actual comparison-project SQL before writing, then re-read and audit the final SQL.

For procedure creation or logic changes, including SELECT-only reports, first read [procedure contracts](references/contracts.md), the actual caller and complete approved same-responsibility procedures. Keep an operation's ordered result sets in its owning dispatch block rather than repeating its already-established mode condition for additional tables. Preserve distinct business conditions and required shared phases. Audit the complete mode/result-set path against the caller after all edits.

For column-aligned SQL, compare actual text columns using space padding rather than repeated tab counts. Match grouped INSERT target names and SELECT/VALUES expressions at shared starts that fit both lists, preserving the approved row groups.

For formatting only, preserve JOIN types/order, conditions, aliases unless explicitly changed, literals, comments, output columns and Korean text. Return the complete requested SQL or exact replacement block. SQL generation does not itself authorize database execution.

Optional comparison: `python -B <plugin-root>/scripts/company_check.py sql <absolute-before.sql> <absolute-after.sql> --preserve-aliases`. This compares reported lexical/source items, not DB equivalence. The company checker supplies no universal SQL formatter or personal style score. Follow [workspace files](../work-execution/references/workspace-files.md) for scratch and cleanup.
