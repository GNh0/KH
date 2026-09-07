# SQL Formatting PBL Quality Evaluation - 2026-06-16

## Purpose

This report records whether the host-local `sql-formatting` skill can actually format real PowerBuilder/PBL SQL work well enough for the user's KH/KONE-style workflow.

It intentionally does **not** store real SQL snippets, real business values, real Korean literals, or source data. The earlier raw evaluation output directory was deleted because it may have contained real PBL SQL fragments.

## Data Handling

- Source root checked: `C:\GWERP`
- Export tool checked: `C:\PblScripter\Export-PBL.ps1`
- Raw evaluation output with possible real SQL content: deleted
- Repository fixtures/report samples: anonymized only
- SQL/PB text token handling: passthrough during analysis, not stored raw in this report

Allowed evidence in this file:

- PBL file names and line ranges used as source location metadata
- aggregate counts
- anonymized SQL shapes
- pass/fail summaries
- improvement requirements

Disallowed evidence in this file:

- real SQL fragments copied from PBL exports
- real table names, column names, values, Korean business strings, customer/order/item values
- formatted output containing real source data

## Source-Safe Validation Summary

Three PBL files were copied to an external validation output root before export because the PBL export tool writes near the input PBL. No export/probe output was written to `C:\GWERP`.

| Area | Result |
| --- | --- |
| PBL files sampled | 3 |
| Exported PB objects | 178 total |
| Export failures | 0 |
| Exported files scanned | 175 |
| SQL-looking fragments extracted | 594 |
| SELECT fragments | 399 |
| UPDATE fragments | 154 |
| DELETE fragments | 5 |
| INSERT fragments | 36 |
| Forbidden output guard | Passed |

## Representative Evaluation Cases

The cases below are anonymized reconstructions of the evaluated shapes. They are not copied production SQL.

### Case 1: SELECT With Joins And Commented Conditions

Source metadata:

- Source class: PowerBuilder DataWindow SQL
- Representative source: `maip_001\d_ant_1.srd`
- Line range: 153-187

Anonymized shape:

```sql
SELECT A.COL_A
     , B.COL_B
     , C.COL_C
FROM T_MAIN A
        LEFT OUTER JOIN T_FLOW B
                     ON A.KEY_COL = B.KEY_COL

        LEFT OUTER JOIN T_LOOKUP C
                     ON A.CODE_COL = C.CODE_COL
WHERE A.DATE_COL BETWEEN :HOST_FROM AND :HOST_TO
--AND A.STATUS_COL = '<STATUS_LITERAL>'
```

Result:

- Manual formatting quality: fail / uncertain
- Main issue: alias rewrite is risky for truncated PB fragments where the full business flow is not visible
- Verifier result from raw run: blocked
- Interpretation: `sql-formatting` needs a fragment mode. For incomplete PB fragments, it should preserve existing alias intent unless enough context exists.

### Case 2: SELECT With CASE, Korean Literal, And DataWindow Wrapper

Source metadata:

- Source class: PowerBuilder DataWindow retrieve SQL
- Representative source: `maip_001\d_maip_002_21b.srd`
- Line range: 105-132

Anonymized shape:

```sql
RETRIEVE="
SELECT A.COL_A
     , (CASE WHEN A.FLAG_COL = 'Y' THEN '<KOREAN_LITERAL>' END) AS FLAG_NM
FROM T_MAIN A
WHERE A.DATE_COL = :HOST_DATE
"
```

Result:

- Manual formatting quality: concerns
- Main issue: DataWindow wrapper text such as `retrieve="..."` is outside normal T-SQL formatting rules
- Verifier result from raw run: blocked
- Interpretation: PB wrapper handling should be explicit. The formatter should format only the SQL body and preserve wrapper syntax.

### Case 3: UPDATE With PowerBuilder Host Variable

Source metadata:

- Source class: PowerBuilder script SQL
- Representative source: `maip_001\maip_002_2.sru`
- Line range: 1964-1967

Anonymized shape:

```sql
UPDATE T_MAIN
   SET COL_A = :HOST_VALUE
WHERE KEY_COL = :HOST_KEY ;
```

Expected formatted shape:

```sql
UPDATE T_MAIN
   SET COL_A = :HOST_VALUE
WHERE KEY_COL = :HOST_KEY;
```

Result:

- Manual formatting quality: pass with concern
- Earlier verifier issue: false positive on whitespace before semicolon
- Fix committed: `b8f19e9`
- Current expected verifier result: pass
- Interpretation: `sql-formatting` must preserve PB host variable casing and treat semicolon-adjacent whitespace as formatting-only.

### Case 4: DELETE With PowerBuilder Host Variable

Source metadata:

- Source class: PowerBuilder script SQL
- Representative source: `sale_001\saord_001.sru`
- Line range: 527-530

Anonymized shape:

```sql
DELETE
FROM T_MAIN
WHERE KEY_COL = :HOST_KEY ;
```

Expected formatted shape:

```sql
DELETE
FROM T_MAIN
WHERE KEY_COL = :HOST_KEY;
```

Result:

- Manual formatting quality: pass with concern
- Earlier verifier issue: false positive on whitespace before semicolon
- Fix committed: `b8f19e9`
- Current expected verifier result: pass

### Case 5: INSERT With PowerBuilder Host Variables

Source metadata:

- Source class: PowerBuilder script SQL
- Representative source: `sale_001\saord_001.sru`
- Line range: 891-893

Anonymized shape:

```sql
INSERT INTO T_MAIN (
       COL_A
     , COL_B
)
VALUES (
       :HOST_A
     , :HOST_B
)
```

Result:

- Manual formatting quality: pass with concern
- Main issue: existing `sql-formatting` skill has weak INSERT examples
- Interpretation: add explicit INSERT/UPDATE/DELETE examples so agents do not over-apply SELECT-centric rules.

## Findings

The existing `sql-formatting` skill is useful for complete T-SQL stored procedures, but it is not sufficient by itself for real PowerBuilder/PBL SQL fragments.

Main gaps:

1. PB host variables such as `:HOST_VAR` must be preserved, including casing.
2. DataWindow wrappers such as `retrieve="..."` must be preserved while formatting only the SQL body.
3. Fragment mode is needed for incomplete SQL extracted from PB files.
4. Alias rewriting should be conservative when the full query/business flow is not visible.
5. UPDATE, DELETE, and INSERT examples are needed, not only SELECT/JOIN examples.
6. Comment handling must preserve commented conditions and allow alias/casing-only updates inside comments.
7. Formatting evaluation must not persist real SQL data; use anonymized fixtures only.

## Actions Already Taken

- Deleted raw formatting evaluation output that may have contained real SQL fragments.
- Added verifier fix for semicolon-adjacent whitespace in PB host-variable predicates.
- Added PBL-derived but anonymized/limited regression fixtures for UPDATE/DELETE semicolon spacing.
- Added version parity checks for plugin manifests.
- Released:
  - `codex-runtime`: `b8f19e9 Fix PB semicolon SQL formatting verification`
  - `main`: `e7db3bf Bump KH wrapper to 2.9.76`

## Recommended Next Changes

Update the host-local `sql-formatting` skill with a PowerBuilder/PBL section:

1. Preserve `:hostvar` names exactly unless the user explicitly asks to rename them.
2. Treat DataWindow wrappers as non-SQL containers.
3. Add fragment-mode instructions for partial SQL.
4. Add UPDATE, DELETE, INSERT formatting examples.
5. Clarify when alias rewriting is allowed and when it must be conservative.
6. Require anonymized evaluation artifacts for future tests.

## Review Checklist For User

Use this checklist to decide whether the formatting behavior is correct later:

- Did the formatted SQL preserve all conditions?
- Did it preserve host variables such as `:HOST_VAR`?
- Did it preserve Korean/business literals?
- Did it avoid inventing JOIN relationships?
- Did it avoid adding `ELSE`?
- Did it keep commented conditions commented?
- Did it only change readability, casing, aliases, indentation, and harmless whitespace?
- If the SQL came from PB/DataWindow, did it preserve wrapper syntax?

