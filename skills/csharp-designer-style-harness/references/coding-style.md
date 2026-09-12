# User's C# coding style

Apply this when creating or editing WinForms/DevExpress/KoneLib screens. These rules incorporate recurring patterns from seven screens registered in the current solution of the user-specified BA/SA/MA projects. Do not use BACKUP or copied projects outside the solution as the baseline.

## Priority of requirements

Apply current user instructions and already agreed C# rules first. Do not treat different expressions in reference source as new exceptions: the user explicitly said those differences are likely oversights. Recurring source patterns supplement coding choices that have not yet been specified.

The actual target's bindings, SPs, row states, transactions, and inherited APIs are separate behavior contracts to preserve. Do not change call semantics to match style. Unfinished methods, commented-out save code, unused using directives, and old copied code are not coding rules to imitate. Do not extend these screen patterns to other C# architectures such as MAUI/PDA or asynchronous services.

A current request to preserve the original and edit only part of it is more specific than general preferences for new code. Within that scope, do not conventionally reorganize original properties or branches. Distinguish necessary naming/brace changes from new business conditions. Replacing existing if/else with a ternary or introducing a separate bool state to restrict editing, attachments, or button actions is not merely a style change.

## Syntax and naming

- Put method/control-statement braces on separate lines and indent by 4 spaces. Use body braces for `if`, `else`, `for`, `foreach`, `while`, and `do`, even for a one-line return/assignment. Preserve `else if` chains. Missing braces in reference examples do not weaken this rule.
- Prefer explicit types such as DataTable/DataRow/DataSet and string/int/decimal/bool. Do not batch-convert `var` or clean up an entire existing file. Write properties with `get { ... }` blocks, not expression bodies.
- Follow existing `str...`, `dt...`, `dr...`, `ds...`, and `grd/gvw/col/rps/txt/btn` names. Follow the current file's prefixes/casing for numeric and state variables. Do not impose a sample business name or one prefix as a global naming rule.
- Preserve early returns, explicit assignments, and existing switch branches. Check parsing success and compare the resulting value in separate if statements. Inline TryParse/ternary expressions in references do not override this agreement; this does not prohibit every ternary expression.

```csharp
DataTable dtList
{
    get
    {
        return grdList.DataSource as DataTable;
    }
}

private void AddItem(DataRow drItem)
{
    if (drItem == null)
    {
        return;
    }

    DataRow drNew = dtList.NewRow();
    drNew["ITEMCD"] = drItem["ITEMCD"];
    dtList.Rows.Add(drNew);
}
```

The example shows expression style only. For an actual screen, check target-table initialization, duplicate criteria, required fields, and row states.

## Screen structure and events

Apply [user-control rules](user-controls.md) first for control selection, default initialization, and naming. Prefer available user controls without limiting them to one library. Use ymd and the actual field name for date inputs.

Follow the existing FrmDevBase screen structure: SelectType enum → state fields/DataTable properties → constructor → screen-command events → query/save and focus/popup helpers. Align enum members and multiline DB arguments with leading commas on subsequent lines, as in current source. Do not reorder all existing members for a local edit.

Keep static control declarations, creation, layout, and properties in Designer. Follow the actual screen's constructor pattern of subscribing named handlers after `InitializeComponent()`. Do not arbitrarily convert Load/SearchCommand/NewCommand/EditCommand/SaveCommand/DeleteCommand/ClearCommand or grid/button/Repository events to lambdas or move them into Designer. Do not duplicate subscriptions already made in Designer or another initialization path. Honor actual dynamic subscription/unsubscription requirements according to the event's lifetime.

Keep queries/saves in existing `CallSelectProcedure`/`CallSaveProcedure` methods and connect screen-command events to that flow. Reuse existing helpers with actual roles, such as `fnFocusedRowChanged`, `SetEditMode`, and `PopUpItems`. Do not create a new helper or generic layer for every short code fragment.

## Database and row handling

For multiline calls, put one DbParameter per line with leading commas, matching existing indentation.

```csharp
DataSet ds = dbClient.GetDataSetFromSP("sp_SAMPLE_SELECT"
                                  , new DbParameter("@WORKTYPE", _selectType.ToString())
                                  , new DbParameter("@KEYCODE", strKeycode)
                                   );
```

Determine actual procedure names, parameter names/order/types, WORKTYPE, and result tables from the target contract. Do not copy example names into product code. `ExecSP`/`ExecSPTrn` and `m_Editmode.ToString()`/`GetEditModeWorkType()` may differ semantically; do not standardize them merely for appearance.

Prefer direct DataTable/DataRow handling and `NewRow` → field assignment → `Rows.Add`. Saves must follow actual TableName, DataRowState, and `DataUtil.DataTableToXml` contracts. Follow [data and event contracts](data-flow.md) for focused versus checked rows and button Tag/FieldName branches.

Inspect and reuse actual implementations of existing helpers such as `dtMasterToDataTable`. If a helper already clones the schema, do not conventionally copy an extra `Clone()` from a reference screen. Apply the [necessity criteria](../../work-execution/references/preferences.md) to LINQ, intermediate tables, and builds: use them only when implementation would be difficult without them or an alternative has an extreme performance disadvantage, not just to shorten code.

Use the actual framework's ShowMessage family and exception-display helpers for query/save exceptions and user messages. Do not invent corrections to helper names/signatures or add try/catch to every event. Check null/false returns together with caller handling. Do not copy a reference method that returns true with an empty DB call as a completed save flow.

Prioritize the [user-corrected HTML defaults](grid-layout.md) for grid properties. Do not adopt a reference Designer's cell alignment, masks, DisplayFormat, OptionsBehavior, or missing editing properties as new defaults.

## Numeric display formats

Where numeric formatting is needed, prefer custom formats over standard N formats such as N0/N2. This rule selects format strings; it does not justify adding DisplayFormat, FormatType, or EditMask to a grid column or Repository.

| Display requirement | Preferred example | When an existing requirement suppresses zero |
| --- | --- | --- |
| Thousands separator, no decimals | #,##0 | #,### |
| Thousands separator, up to 2 decimal places | #,##0.## | #,###.## |

These are format-selection examples, not a rule to change decimal precision in existing initialization. Check user-control constructors and base classes, plus initialization helpers called by shared forms, Repository iteration, and application conditions. If the actual path already handles numeric display, do not duplicate assignments in screen Designer.

If the user explicitly requests the same display on a target without shared initialization, apply the verified settings. For example, if the original path uses Numeric and `"{0:#,###,###,##0.####}"` and the user specifies that value, use exactly that format. Do not shorten it to `#,##0.##` or copy unrelated button, mask, or alignment properties alongside it. Apply the specific request to that target; do not make it a new default for other screens.

For summaries, put formats such as {0:#,##0} or {0:#,##0.##} in the existing SummaryItem.DisplayFormat or GridColumnSummaryItem format argument. Preserve suffixes such as the Korean “건” in “{0:N0} 건”, alignment, SummaryType, FieldName, and aggregation calculations. Do not extend a summary-format request to ordinary cell/Repository DisplayFormat settings. Apply the same notation preference to actual numeric ToString, string.Format, and interpolated strings, without creating new interpolation expressions/helpers just for formatting.

#,##0 displays zero; #,### can suppress its digit position. Decimal ## specifies a maximum number of places, so do not assume it displays like N2's fixed two places. Use #,##0.00 when exactly two decimals are required. Do not arbitrarily change culture, numeric types, rounding, or negative/zero display, or convert numeric data to strings to match appearance. Assess an actual API requirement for an N format alongside current user instructions; convenience alone does not justify an exception.

Syntax references: [Microsoft custom numeric formats](https://learn.microsoft.com/en-us/dotnet/standard/base-types/custom-numeric-format-strings) and [DevExpress summary formats](https://docs.devexpress.com/WindowsForms/DevExpress.XtraGrid.GridSummaryItem.DisplayFormat).
