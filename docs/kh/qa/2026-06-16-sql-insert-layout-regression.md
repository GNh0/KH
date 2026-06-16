# SQL INSERT Layout Regression - 2026-06-16

## Problem

A PBL SQL before/after run formatted a wide `INSERT INTO ... SELECT` mapping as
one target column per line. That does not match the user's established stored
procedure style, where wide business-table mappings are grouped horizontally so
target columns and source expressions can be compared by eye.

The bad shape appeared in the generated artifact:

```text
pbl-sql-before-after-20260616-v2/sql/02_insert_after.sql
```

The source was a real PBL `INSERT ... SELECT` mapping, not an anonymized sample.

## Expected Style

For wide ERP insert mappings such as `SA110T`, `SA130T`, and similar copy/save
flows:

- Keep `INSERT INTO <TABLE>` and `(` split for readability.
- Group target columns horizontally, usually three or four per row.
- Group the `SELECT` expressions in matching horizontal rows.
- If one mapping is long because of `CASE WHEN`, `ROW_NUMBER() OVER (...)`,
  long `ISNULL(...)`, arithmetic, concatenation, or a similar expression, wrap
  that mapping onto continuation lines while keeping the neighboring mappings
  horizontally grouped.
- Preserve commented-out columns and matching commented-out source expressions.
- Do not convert a wide mapping to one-column-per-line unless the user explicitly
  asks for that shape.

## Changes

- Updated host-local `sql-formatting` instructions with an explicit
  `INSERT INTO ... SELECT Layout` section.
- Added KH verifier style issue `insert_select_single_column_per_line`.
- Added regression tests:
  - one-column-per-line wide insert is blocked
  - grouped horizontal wide insert is accepted
  - grouped insert with a wrapped long `ROW_NUMBER()` expression is accepted
- Updated SQL formatting harness docs and minimal workflow failure cases.
- Bumped plugin manifests to `2.9.78`.

## Verification

Commands run from the KH repository:

```powershell
python -B -m unittest tests.test_sql_formatting_style_harness
python -B -m unittest tests.test_plugin_packaging tests.test_plugin_composition_policy tests.test_kh_front_door
python -B -m src.skills.uaf_skill_catalog --check
python -B -m src.skills.sql_formatting_style --original <v2 02_insert_before.sql> --formatted <v2 02_insert_after.sql>
```

Results:

- SQL formatting harness tests: `21` passed.
- Packaging/composition/front-door tests: `52` passed.
- Skill catalog check: `41` valid, `0` invalid.
- The previously bad `02_insert_after.sql` now fails verification with
  `insert_select_single_column_per_line`.

## Boundary

This verifier checks formatting shape and mechanical preservation. It does not
prove database semantics or execution-plan equivalence.
