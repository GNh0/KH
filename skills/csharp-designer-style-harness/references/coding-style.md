# User's C# coding style

Use a working source from the designated comparison project, or an approved comparable project. Read the relevant complete bodies. Use the current target for APIs, inherited behavior and data contracts.

## Priority of requirements

- Apply current instructions and agreed C# rules first. Source examples fill unspecified choices. An inconsistent sample cannot override an explicit rule.
- Respect the requested edit boundary. Preserve original properties, branching, transactions and bindings outside it. Adding state or changing permissions is a behavior change.
- Use these conventions for the applicable WinForms/DevExpress architecture. Check the actual architecture for other targets.

## Syntax and naming

- Use four spaces, separate-line braces and braced bodies for if/else and loops, including one-line returns. Preserve else-if chains.
- Prefer explicit DataTable, DataRow, DataSet and primitive types. Use get blocks. Keep existing code outside scope.
- Follow local variable prefixes and casing, including str/dt/dr/ds and control names. Preserve early returns, explicit assignments and switch branches.
- Check TryParse success and compare the parsed value in separate if statements. Preserve established if/else handling.
- Use interpolation for composed display text. Preserve SQL/XML/key construction semantics. Uppercase application action Tags and matching switch cases. Preserve external identifiers.

```csharp
DataTable dtList
{
    get
    {
        return grdList.DataSource as DataTable;
    }
}
```

## Screen structure and events

- Apply [user-control selection and naming](user-controls.md). Date inputs use ymd plus the field name.
- In FrmDevBase follow the target's order of enum, state/data properties, constructor, commands and query/save helpers. Align subsequent multiline arguments and enum members with leading commas.
- Keep static control layout in Designer. Where the screen subscribes after InitializeComponent, use named handlers there. Inspect subscriptions in both files and handle dynamic lifetimes. Check Repository ButtonClick and grid RowCellClick for duplicate popups.
- Keep commands linked to the established query/save methods. Resolve names, arguments, return, failure, cancellation, reset, protection and requery in the actual caller. Reuse a shared handler or helper when the project and task need it.

## Database and row handling

- Use one DbParameter per line with leading commas and actual argument order. Preserve ExecSP/ExecSPTrn, edit-mode semantics, XML TableName, row states and result order.
- Prefer direct DataTable and DataRow operations. Inspect helpers before cloning schemas or building intermediate tables. Apply the user's [necessity criteria](../../work-execution/references/preferences.md) to LINQ, intermediate tables and builds.
- Trace checked and focused rows, actual event branches, exception handling and ShowMessage APIs. See [data flow](data-flow.md). Preserve explicit [grid HTML defaults](grid-layout.md).

```csharp
DataRow drNew = dtList.NewRow();
drNew["ITEMCD"] = drItem["ITEMCD"];
dtList.Rows.Add(drNew);
```

## Numeric display formats

| Requirement | Format | Suppress zero when requested |
| --- | --- | --- |
| Thousands, no decimals | `#,##0` | `#,###` |
| Up to two decimals | `#,##0.##` | `#,###.##` |
| Exactly two decimals | `#,##0.00` | Verify the requested zero display |

- Prefer custom formats over N0/N2 where a format is required. Preserve a user-specified format exactly. Check constructors, base classes and shared Repository initialization before adding a screen setting.
- Apply summary formats in SummaryItem.DisplayFormat or GridColumnSummaryItem. Preserve suffixes, alignment, SummaryType and FieldName. Match the same notation in existing ToString, string.Format and interpolation.
- Retain existing precision, rounding, culture, negative/zero display and data type. Change cell display, edit masks or Repository settings only where that property is required.

See [Microsoft numeric formats](https://learn.microsoft.com/en-us/dotnet/standard/base-types/custom-numeric-format-strings) and [DevExpress summary formats](https://docs.devexpress.com/WindowsForms/DevExpress.XtraGrid.GridSummaryItem.DisplayFormat).
