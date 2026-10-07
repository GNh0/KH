# PB extraction and comparison

Verify the selected PB version, exact PBL, ORCA DLL, bitness, dependent DLLs, PATH and license. PBL header numbers alone do not identify a usable runtime. `src.pb.orca` can probe/run an available PblScripter; inspect its `--help` and supply actual tool paths. Conversion requires an explicit export output directory. Continue from supplied exports if extraction is unavailable and identify the missing evidence.

Exit zero alone is insufficient: inspect error text and actual newly created nonempty exports. Session-open, bad-library, SySAM/license failures and missing output cannot be reported as completed extraction. Helper builds follow the current task's instructions and concrete necessity.

`python -B <plugin-root>/scripts/company_check.py pb <absolute-export> --encoding cp949` inspects supported export structure. Choose the actual source encoding. `sp-call <absolute-caller.cs> <absolute-procedure.sql>` compares a selected call and actual signature. Neither command executes a PBL or database.

For a migration plan, connect actual screens, events, DataWindows, tables, inputs/outputs, keys, row states and implementation dependencies only to the detail the request needs. Compare query/edit/protection/save/requery and reports using the same inputs.

`src.pb.equivalence.compare_observations` accepts two observation objects: `parameters` (object), `database` (nonempty string), `schema` (ordered array), `ordered` (boolean), and `rows` (array). Duplicate rows are retained, nested types are compared and ordered results require matching row order. Timing uses finite nonnegative samples in `elapsed_ms`; optional `query_count` and `logical_reads` are nonnegative integers. Provenance is supplied evidence, not automatically authenticated execution. Performance claims need comparable context, results and measurements.
