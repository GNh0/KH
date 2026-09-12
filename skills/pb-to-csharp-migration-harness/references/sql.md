# C# and SELECT/SAVE

Map PB retrieve/update paths to C# parameters/XML and SP result tables, numbering, NEW/MOD/DEL, and validation locations. Complete both SELECT and SAVE when both are requested. Do not delete original validation or replace it with bulk overwrites in C#.

Compare parameter names/required parameters for one selected call against the actual SP definition with the command below. Supply that call fragment, not the entire screen.

```powershell
python <plugin-root>/scripts/kh_check.py sp-call <absolute-selected-call.cs> <absolute-procedure.sql>
```

Leave computed parameter names unverified. A pass covers name/required-parameter comparison only; separately check OUTPUT/INPUTOUTPUT direction, return-value retrieval, XML contents, and actual API defaults.

Use [SQL style](../../sql-formatting/references/style.md) for SQL generation/cleanup. Style comparison alone does not establish data behavior. For actual DB-change requests, verify the exact server/database/target and resulting state. Do not automatically register DB-only SQL files as C# project items.

In `scripts/extract_sql.py` output, `datawindow_retrieve` is a query extracted from a DW quoted value, `embedded_sql` is a PowerScript SQL statement, and `string_candidate` is a string fragment whose assembly must be checked. `complete` means extraction boundaries were identified, not that SQL is valid or executed successfully. Locate originals through line, offset, and source_name. Retain dynamic `DataObject` assignments as `unresolved_dataobjects` without guessing names.
