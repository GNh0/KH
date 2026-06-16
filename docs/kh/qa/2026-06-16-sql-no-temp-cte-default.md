# SQL No Temp Table Or CTE Default

## Change

SQL recommendations and formatting verification now treat newly introduced CTEs and `#` temporary tables as non-default patterns.

## Rule

- Prefer direct joins, derived tables, aggregate subqueries, and the existing stored-procedure style.
- Use CTEs only for explicit requests, recursion, or a concrete readability/maintainability reason.
- Use `#` temporary tables only for explicit requests, repeated multi-statement reuse, large intermediate sets that need indexing/statistics, procedural staging, or measured performance evidence.
- If a CTE or `#` temporary table is used, the formatter should state the reason.

## Regression Coverage

- `cte_introduced_without_reason`
- `temp_table_introduced_without_reason`
- existing CTE/temp-table SQL remains allowed when preserved from the original
- CTE column-list syntax is detected
- CTEs at the start of a procedure block are detected
- adding another CTE to SQL that already had a CTE is detected
- `WITH (NOLOCK)` is not treated as a CTE
- CTE/temp-table markers inside literals or comments are ignored
- concrete exception reasons produce warning evidence instead of a blocking error
- vague exception reasons still block
- negated exception reasons such as "not explicit" still block
- negated performance/statistics reasons such as "no measured performance evidence" still block
- `SELECT ... INTO #TEMP` can pass only when a concrete temp-table exception reason is recorded

## Verification

- `python -B -m unittest tests.test_sql_formatting_style_harness`
- `python -B -m unittest tests.test_plugin_packaging tests.test_plugin_composition_policy tests.test_kh_front_door`
- `python -B -m src.skills.uaf_skill_catalog --check`
