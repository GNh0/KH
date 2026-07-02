# PowerBuilder Source Analysis

Use this reference to trace exported PB source before producing C# or SP work.

## Trace order

1. Identify the entry object in `.sru` or `.srw`.
2. Search for window/object inheritance and embedded controls.
3. Search for `dataobject =`, `Retrieve`, `Update`, `SetTransObject`, `Modify`, `Open`, `OpenWithParm`, `CloseWithReturn`, and user events.
4. Follow every linked DataWindow `.srd`.
5. In SRD, inspect `retrieve=`, `table(...)`, `column(...)`, update table, arguments, and computed fields.
6. Check popup windows and copy/save dialogs. The object that opens the popup may not contain the real insert/update logic.
7. Compare PB write behavior against the target stored procedure by table and column, not by table names alone.

## What to extract

- Program/screen object name and parent type.
- Window/userobject flow and popup calls.
- DataWindow names and their retrieve/update role.
- SQL fragments, host variables, argument order, and transaction behavior.
- Insert/update/delete tables and column mappings.
- Special flags, defaults, status fields, hidden values, and post-save updates.
- Result sets returned to UI and expected bindings.

## PB-to-SP parity checklist

For copy or save flows, compare:

- tables touched by PB and SP;
- target columns and source expressions;
- default values and hard-coded flags;
- transaction boundary;
- validation and duplicate checks;
- update-after-insert logic;
- missing child/detail tables;
- standalone SELECT statements left before INSERT blocks;
- result sets returned unintentionally from a save procedure.

## DataWindow caveats

DataWindow source can provide field and SQL metadata, but it does not automatically define the final TY UI. Grid layout, report layout, and detail form behavior must be mapped through the target C# control conventions. Do not invent layout geometry from column names alone.

## Fallback mode

When exported source is unavailable, produce a bounded analysis plan and list what cannot be proven. If only a pasted SRD exists, perform DataWindow mapping. If only C#/SP exists, perform target-side review. If only a screenshot exists, treat visual behavior as a request for clarification or design, not source proof.
