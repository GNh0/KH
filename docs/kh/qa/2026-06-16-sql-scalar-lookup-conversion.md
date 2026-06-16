# SQL Scalar Lookup Conversion QA - 2026-06-16

## Scope

This note records the SQL formatting rule update for scalar lookup functions.
The concrete regression was a worker preserving `DBO.F_BA011T_FIND_SUBNM(...)`
even though the host-local `sql-formatting` contract defines it as a verified
`BA011T` lookup.

No real project SQL, real table data, or PBL fragments are included here.

## Decision

- Unknown scalar functions stay unchanged unless the function body, DB/MCP
  metadata, project source, or a verified style contract proves an equivalent
  lookup join.
- `DBO.F_BA011T_FIND_SUBNM(MAINCD, SUBCD, USEYN)` is treated as a verified
  `BA011T` lookup contract when the host-local `sql-formatting` skill is
  available.
- Verified `BA011T` scalar lookups should be converted to `LEFT OUTER JOIN
  BA011T` unless a concrete safety exception is recorded.
- PB host variables such as `:ls_frdt` are source contract text and must be
  preserved, not uppercased.

## MCP Check

The `mssql_C_KONE110` query tool was available, but the active database
connection was not open in this session:

```text
Query failed: No active database connection. Use connect_database first.
```

That means general scalar functions cannot be converted from DB evidence in
this session. The BA011T conversion remains allowed because the host-local
style contract carries the verified lookup mapping.

## Regression Fixes

- Strengthened the host-local `sql-formatting` rule so verified lookup
  scalar-function-to-join conversion is an explicit exception to generic
  formatting-only restrictions.
- Updated KH `sql-formatting-style-harness` docs to distinguish verified
  lookup conversion from unknown scalar functions.
- Added a negative test for retained `DBO.F_BA011T_FIND_SUBNM`.
- Fixed verifier false positives for:
  - lowercase PB host variables
  - inline `JOIN ... ON ... AND ...` conditions
  - spacing-only changes around comparison operators inside contract lines
  - spacing-only changes inside commented SQL predicates

## Subagent Check

A fresh worker was instructed to read the updated host-local `sql-formatting`
skill and format an anonymized SQL sample. The worker converted:

```sql
DBO.F_BA011T_FIND_SUBNM('CD001', A.STATUS_CD, 'Y')
```

to:

```sql
LEFT OUTER JOIN BA011T C
             ON C.MAINCD = 'CD001'
             AND A.STATUS_CD = C.SUBCD
             AND C.USEYN = 'Y'
```

and projected:

```sql
ISNULL(C.SUBNM, '') AS STATUS_NM
```

## Verification

Commands run from the KH repository:

```powershell
python -B -m unittest tests.test_sql_formatting_style_harness tests.test_plugin_packaging tests.test_plugin_composition_policy tests.test_kh_front_door
python -B -m src.skills.uaf_skill_catalog --check
python -B skills\sql_formatting_style_harness\scripts\smoke_check.py
python -B skills\sql_formatting_style_harness\scripts\demo.py --output-dir "$env:TEMP\kh-sql-formatting-demo-2.9.77"
```

Results:

- `71` unittest cases passed.
- Skill catalog check passed: `41` valid, `0` invalid.
- SQL formatting harness smoke check passed.
- SQL formatting harness demo passed with success and blocked HarnessResult
  artifacts.
- The anonymized scalar-to-join sample passed verifier with
  `mechanical_checks.status=passed`, no preservation issues, and no style
  issues.

## Remaining Boundary

The harness still does not prove DB semantic equivalence. For schema-dependent
or performance-critical conversions, use DB-backed evidence such as function
body review, execution-plan comparison, result-set comparison, or
`STATISTICS IO/TIME`.
