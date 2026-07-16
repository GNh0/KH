# Packaged PB-To-C# Style Contract

This is the only style profile used during normal generation. It is sanitized, generalized, and self-contained so C#, Designer, and SQL Server procedure drafts can be produced offline.

The companion `packaged-style-contract.json` exposes the same decisions in a machine-readable form. User-supplied source defines behavior and identifiers; this contract defines generated shape and fallback behavior.

## Contract Selection

Record these selections before generation:

| Decision | Allowed values |
| --- | --- |
| Screen family | `browse`, `master-detail`, `detail-entry`, `popup` |
| Method family | `command`, `event` |
| Control provider | `target-wrapper`, `konelib`, `devexpress`, `winforms` |
| Procedure family | `select`, `save`, `select-save` |
| Evidence mode | `described-behavior`, `pasted-source`, `mixed-input`, `contract-only` |

Use one value per decision and keep it stable across a generated screen. User-supplied target code may override a packaged default, but a local discovery run may not.

## Style Families

### Browse

- One search area and one result grid.
- Search or button event calls one select method.
- Result table binds directly to the selected grid/view family.
- Clear resets search editors and result binding through the selected provider's supported API.

### Master-Detail

- A master grid retrieves first.
- The focused-row event reads the current master row and calls one detail-select path.
- A missing focused row clears the detail binding and returns.
- Master and detail result contracts remain separate.

### Detail Entry

- Label/editor pairs use stable rows and columns rather than copied PB pixel positions.
- Field order follows supplied DataWindow order or the user-approved mapping.
- Validation occurs before save serialization.
- `BindingField` and `TabIndex` are explicit for every editor that supports them.

### Popup

- Inputs arrive through the supplied constructor/property/parameter contract.
- Selection returns only through the supplied popup result contract.
- Do not broaden result states or invent global mutable state.

## Naming Grammar

Angle-bracket tokens below are placeholders, not concrete project identifiers.

| Element | Grammar |
| --- | --- |
| Form class | `<Feature><Mode>Form` |
| Load handler | `<FormClass>_Load` |
| Command handlers | `SearchCommand`, `SaveCommand`, `ClearCommand`, `DeleteCommand` |
| Query method | `CallSelectProcedure` or `CallViewQuery` |
| Save method | `CallSaveProcedure` or `CallProc` |
| Focus handler | `gvw<Role>_FocusedRowChanged` |
| Text editor | `txt<Field>` |
| Lookup/button editor | `btn<Field>` |
| Combo/lookup editor | `cbo<Field>` |
| Numeric editor | `spn<Field>` |
| Date editor | `dt<Field>` |
| Boolean editor | `chk<Field>` |
| Memo editor | `memo<Field>` |
| Label | `lbl<Field>` |
| Panel/group | `pnl<Role>`, `grp<Role>` |
| Grid/view | `grd<Role>`, `gvw<Role>` |
| Grid column | `col<Role>_<FIELD>` |
| Repository editor | `repButton<Field>`, `repLookup<Field>`, `repSpin<Field>`, `repCheck<Field>` |
| Procedure | `[dbo].[usp_<Feature>_<Operation>]` |
| Procedure parameter | `@<CALLER_VALUE>` |
| Procedure local | `@Local<DerivedValue>` |

Preserve supplied names exactly. Apply this grammar only for missing names. Use PascalCase for C# symbols and uppercase snake case for SQL parameters and result fields unless supplied code establishes another casing contract.

## Event And Method Shapes

### Command Family

Use when the selected form base exposes command overrides.

```csharp
protected override void SearchCommand(object sender, EventArgs e)
{
    base.SearchCommand(sender, e);
    CallSelectProcedure(SelectType.List);
}

protected override void SaveCommand(object sender, EventArgs e)
{
    base.SaveCommand(sender, e);
    CallSaveProcedure();
}
```

### Event Family

Use when no command base is declared.

```csharp
private void btnSearch_Click(object sender, EventArgs e)
{
    CallSelectProcedure(SelectType.List);
}

private void btnSave_Click(object sender, EventArgs e)
{
    CallSaveProcedure();
}
```

### Select Shape

- Keep caller parameters adjacent to the call.
- Use one `SelectType` or equivalent branch selector when list/detail branches exist.
- Bind each returned table to exactly one documented UI role.
- For a focused-row detail call, return immediately when no row is focused.
- Do not create a context DTO or generic editor-value helper for an ordinary call.

### Save Shape

- Validate required fields first.
- Collect inserted, modified, and deleted rows according to the supplied save contract.
- Serialize only the row states expected by the selected procedure branch.
- Use the existing transaction-capable client method when the KoneLib family is selected and declared.
- Refresh or clear only after successful save completion.

## Runtime C# Structural Validation

The machine-readable contract exposes these rules under `rules.csharp.required_patterns`. Every pattern is required for a complete generated C# screen candidate; the validator reports each matched or missing rule identifier.

| Rule identifier | Required generalized evidence |
| --- | --- |
| `mapped_form_declaration` | A partial class whose generated name ends in `Form` and whose declared base is a form or form-base family. |
| `designer_initialization` | A call to `InitializeComponent(...)`, proving that the screen participates in the Designer initialization path. |
| `migration_call_path` | One packaged query/save path: `CallSelectProcedure`, `CallViewQuery`, `CallSaveProcedure`, or `CallProc`. |
| `ui_binding_or_result_mapping` | An explicit `DataSource`, `BindingField`, or `FieldName` assignment connecting generated code to a UI or result field. |

These are structural gates, not project identity. The patterns contain only generalized C# grammar and synthetic method families. They must not encode a person, workstation, project, program, database, table, procedure instance, source path, or artifact fingerprint.

An empty string fails all four rules. An arbitrary class such as `public class UnmappedWidget {}` also fails because it has no form mapping, Designer initialization, migration call path, or UI/result binding evidence. A candidate does not pass merely because it compiles or contains a class declaration.

The structural gate complements the forbidden-pattern scan. A passing verifier record includes the packaged contract identifier and version, the consumed `csharp.required_patterns` rule group, every matched rule identifier, and no missing-rule issue. When the runtime cannot consume the exact packaged contract identity, validation remains blocked rather than falling back to local examples.

## Control Provider Fallback

Provider selection depends only on user-supplied dependency evidence:

1. `target-wrapper`: supplied project-owned wrappers and APIs.
2. `konelib`: KoneLib wrappers when KoneLib is declared.
3. `devexpress`: DevExpress editors, grids, views, tabs, and layout controls when DevExpress is declared.
4. `winforms`: standard WinForms controls when no richer provider is declared.

For KoneLib, map logical controls to the corresponding `u_*` wrapper family and keep its binding/reset APIs. For DevExpress, use the existing referenced API generation, not the newest online API. For WinForms, replace `BindingField` with an explicit binding map when the control has no such property.

Never add packages or inspect a project during normal generation. When dependency evidence is missing, select WinForms and record the lower-fidelity fallback.

## Designer Contract

Emit initialization in dependency order:

1. Fields and component container.
2. Repository editors.
3. Grid columns.
4. Grid view and grid control.
5. Editors and labels.
6. Containers and parent `Controls.Add` calls.
7. `BeginInit`/`EndInit`, `SuspendLayout`/`ResumeLayout`, and final form properties.

For every supplied or generated editor, record:

- type and provider;
- `Name`;
- source field;
- `BindingField` or explicit binding map;
- caption/text;
- `TabIndex`;
- parent container;
- `Location` and `Size`, or dock/anchor constraints;
- relevant `Properties.*`, edit mask, read-only, null, and validation behavior.

Within each independent container, located input controls follow row-major top-to-bottom/left-to-right visual order, and their `TabIndex` values must be present, unique, and contiguous increasing. Labels, grid columns, repositories, and other non-input controls do not participate in this check. Different containers are validated independently and may restart their sequence.

Do not invent project-specific flags. Preserve them only when they are present in supplied source.

## Designer Ownership Boundary

`.Designer.cs` is the default owner of static UI structure. Put control and component fields, construction, layout, names, `TabIndex`, binding fields, grid columns, repositories, `Appearance`, `Options`, collection registration, and other static design properties in the Designer partial class. This boundary applies to WinForms, declared wrapper controls, and DevExpress-style controls.

Code-behind owns runtime behavior: command logic, event-handler implementations, validation, procedure calls, result/data binding, and state changes that must occur while the screen is running. A static setting may move to code-behind only when supplied source or an explicit behavior contract proves it is dynamic; record the runtime reason and a targeted test. Without that evidence, the exception is blocked.

### Synthetic Designer Example

```csharp
partial class CatalogBrowseForm
{
    private TextBox txtFilterText;
    private DataGridView grdBrowse;
    private DataGridViewTextBoxColumn colBrowse_ENTITY_ID;

    private void InitializeComponent()
    {
        this.txtFilterText = new TextBox();
        this.grdBrowse = new DataGridView();
        this.colBrowse_ENTITY_ID = new DataGridViewTextBoxColumn();

        this.txtFilterText.Name = "txtFilterText";
        this.txtFilterText.Location = new Point(16, 16);
        this.txtFilterText.Size = new Size(180, 24);
        this.txtFilterText.TabIndex = 0;

        this.colBrowse_ENTITY_ID.Name = "colBrowse_ENTITY_ID";
        this.colBrowse_ENTITY_ID.DataPropertyName = "ENTITY_ID";
        this.grdBrowse.Columns.AddRange(this.colBrowse_ENTITY_ID);
    }
}
```

The names are synthetic grammar examples. They do not identify a real project, program, table, procedure, or control inventory.

### Synthetic Code-Behind Example

```csharp
private void btnSearch_Click(object sender, EventArgs e)
{
    CallSelectProcedure();
}

private void CallSelectProcedure()
{
    DataTable result = LoadCurrentRows();
    grdBrowse.DataSource = result;
}
```

This code contains behavior, an event path, and runtime result binding. It does not recreate controls or repeat static layout/design assignments.

### Failure Cases

The following code-behind shape is blocked by default:

```csharp
public CatalogBrowseForm()
{
    InitializeComponent();
    this.txtFilterText = new TextBox();
    this.txtFilterText.Name = "txtFilterText";
    this.txtFilterText.TabIndex = 0;
    this.grdBrowse.Columns.AddRange(this.colBrowse_ENTITY_ID);
}
```

It moves control creation, naming, tab order, and fixed grid registration out of `.Designer.cs` without dynamic-state evidence. The verifier or review evidence must report the matched file-scoped rule identifiers and block completion until the assignments return to the Designer file or an approved runtime exception is documented.

## Grid And Repository Contract

- The authoritative workflow is DataWindow -> generated DevExpress View XML -> GridControl Designer `Layout -> Load` -> target C# Designer state. The XML is not merely a separate runtime serialization output; its fixed values define the baseline applied to the actual `GridView` and `GridColumn` components.
- Keep XML representation rules separate from C# naming and repository conventions. XML may serialize `Name=gridView1` and an empty `ColumnEditName`; C# must retain target names and must not emit `ColumnEditName`.
- XML uses `XtraSerializer` version `1.0`, application `View`.
- Required XML View values are `BestFitMaxRowCount=-1`, `PreviewLineCount=-1`, `HorzScrollStep=3`, `FocusRectStyle=CellFocus`, `ScrollStyle=LiveVertScroll, LiveHorzScroll`, `PreviewIndent=-1`, empty `GroupPanelText`, `PreviewFieldName`, `VertScrollTipFieldName`, `NewItemRowText`, and `ViewCaption`, `LevelIndent=-1`, `GroupFooterShowMode=VisibleIfExpanded`, `SynchronizeClones=true`, `BorderStyle=Default`, `DetailHeight=350`, `DetailTabHeaderLocation=Top`, and `ActiveFilterEnabled=true`.
- Required XML `OptionsView` values are `ShowViewCaption=false`, `EnableAppearanceEvenRow=true`, `ShowGroupPanel=false`, `ColumnAutoWidth=false`, `ShowFooter=true`, and `ShowAutoFilterRow=true`.
- Every XML column uses header `UseTextOptions=true`, header `UseFont=true`, horizontal and vertical center alignment, header font `Tahoma, 9pt`, cell `UseFont=true`, cell font `Tahoma, 9pt`, `Visible=true`, and one-based `VisibleIndex` in raw PB `column=(` occurrence order. Visual y/x sorting is not used for grid XML. `FieldName` and XML `Caption` are the uppercase source field exactly as emitted by the HTML. A mapped PB caption is an intentional post-conversion C# Designer override, not source-exact XML emission.
- XML `FieldName` and XML `Name` preserve converter characters including `#` and `$`. `xml_column_name` and `csharp_name` are separate contracts; C# generation requires an explicit valid identifier mapping when the XML name is not a safe C# member.
- An explicit grid contract requires both valid Layout-Load-ready XML and C# Designer source containing equivalent applied View, `OptionsView`, column appearance, and one-based index values. Neither artifact nor hand-written assignments pass alone, and caller-authored observed-load dictionaries or hashes do not replace Designer validation.
- Local verification is static and records `actual_live_layout_load_observed=false`; only a genuinely external DevExpress host can supply stronger evidence.
- Use `grdList`/`gvwList`/`colList_<FIELD>` for list role, `grdDetail`/`gvwDetail`/`colDetail_<FIELD>` for detail role, and `grd<SUFFIX>`/`gvw<SUFFIX>`/`col<SUFFIX>_<FIELD>` for an explicit table or purpose. `colList_` is never the fallback for table or purpose roles.
- Declare and initialize the `GridControl` and `GridView`, set `MainView`, register `ViewCollection`, set `GridControl`, and preserve the target `Name` values explicitly.
- Declare each grid column as a Designer member.
- Register columns with `Columns.AddRange` in visible order.
- Set `Name`, `FieldName`, mapped/post-conversion `Caption`, and one-based `VisibleIndex` explicitly; `Columns.AddRange` order must match the indices.
- Keep `FieldName` identical to the SP result field.
- When authoritative evidence defines a base key plus one or more sequence keys and a dedicated UI display field, SELECT retains all raw key components and additionally emits the display field. The visible Designer/Grid `FieldName` binds to that display alias; raw key columns remain available and are hidden unless supplied PB/UI evidence says otherwise.
- Preserve a supplied display alias and PB caption. If no alias is supplied after the ordered business-key components are established, use the packaged `<BASE>S` default. A table name or similar field names alone are not enough to establish the components.
- Apply every authoritative Layout Load default, not only the commonly visible `OptionsView` subset.
- Numeric fields use a spin/numeric repository editor assigned through `ColumnEdit`.
- Lookup fields use a lookup repository whose value/display members come from supplied evidence.
- Button fields use a button repository and one explicit button event.
- Boolean fields use a check repository when the selected provider supports it.
- Add repositories to the grid control's repository collection before assigning them to columns.
- Do not use runtime column factories, `AddField`, generated `for` loops for fixed columns, or numeric GridColumn `DisplayFormat`. Numeric columns require `RepositoryItemSpinEdit` behavior.

## Caller And Procedure Contract

Build a caller matrix before SQL generation:

| Parameter | C# source | Type/length | Branches | Null/default rule |
| --- | --- | --- | --- | --- |
| `@ACTION` | selected method branch | supplied or inferred draft | all | no invented literal default |
| `@FILTER_TEXT` | search editor | supplied or inferred draft | select | raw value; wildcard owned by SQL |
| `@EFFECTIVE_DATE` | date editor | supplied or inferred draft | select/save | raw date value |
| `@ROWS_XML` | serialized changed rows | XML/text per supplied client | save | required only for save branch |
| `@ACTOR_ID` | caller context | supplied context type | save | never synthesized from package data |

These names are synthetic examples. Generated parameters must use the user's supplied identifiers when available.

Rules:

- Every procedure parameter maps to a caller value or an explicitly documented non-screen caller.
- Keep parameter order synchronized between C# and SQL.
- Internal counters, normalized values, derived dates, and calculation values are local `DECLARE` variables.
- C# passes raw search/date values. SQL owns wildcard and date derivation.
- Do not add literal defaults, normalization blocks, or helper parameters without supplied evidence.
- SELECT result fields exactly match C# bindings and `FieldName` values.
- Composite display expressions preserve authoritative component order. The packaged direct style is `BASE + '-' + FORMAT(SEQUENCE, '##0')`, with `+ '-' + FORMAT(...)` repeated for each additional numeric sequence. Do not introduce `CASE`, `ISNULL`, `CONCAT`, casts, or other null/type rewrites without source evidence. `FORMAT` produces character output; the builder therefore requires character base-key and numeric sequence-key type evidence and never replaces the raw typed result fields.
- SAVE branches document accepted row states, XML shape, write order, transaction boundary, and returned status/result sets.

## Stored Procedure Shapes

### Metadata And Signature

```sql
-- =============================================
-- AUTHOR:      <maintainer>
-- CREATE DATE: <yyyy-mm-dd>
-- DESCRIPTION: <purpose>
-- =============================================
CREATE OR ALTER PROCEDURE [dbo].[usp_<Feature>_<Operation>]
      @ACTION         VARCHAR(20) = NULL
    , @FILTER_TEXT    NVARCHAR(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;
```

Placeholders must be replaced from the request or left visibly unresolved in a draft. Never substitute packaged identities.

### Select Family

- Use explicit action branches only when the caller matrix defines them.
- Prefer direct joins, derived tables, and aggregate subqueries.
- Use stable per-scope aliases: outer main `A`, related same-role `A1`, next roles `B`, `C`; derived-table main `T`, then `T1`, `TA1`.
- Use leading commas for parameters and selected columns.
- Preserve supplied predicates, literals, calculations, comments, and result order.
- Do not claim a complete query when table/column relationships are inferred.

### Save Family

- Parse the supplied payload using the target-compatible XML or structured-row method.
- Stage rows in a table variable when that matches the selected contract.
- Validate before opening the transaction where possible.
- Use an explicit transaction for writes and the supplied error/logging contract.
- Prefer separate `UPDATE` and `INSERT` statements when no upsert primitive is supplied.
- Preserve logical-delete behavior only when supplied evidence defines it.

## Forbidden Generation Patterns

- Private or environment-derived identifiers, paths, people, hashes, snapshot counts, or source fingerprints.
- Style decisions learned by scanning local assets during normal generation.
- Invented context/request classes, broad normalization helpers, or parallel query/save paths.
- Inline wildcard concatenation in C#.
- Silent date initialization in a query/save path.
- Year/month/boundary helper values exposed as procedure parameters.
- Caller parameters missing from the caller matrix.
- Runtime grid-column factories or fixed-column generation loops.
- Numeric formatting without repository/editor behavior.
- Source-unbacked empty result schemas or full procedure claims.
- New CTEs, temporary tables, `MERGE`, `NOT EXISTS`, scalar-function conversion, or tuning rewrites without supplied evidence or explicit approval.
- Dependency upgrades, invented custom-control flags, or API calls from a different library generation.

## Evidence Requirements

A generated artifact is release-ready only when its evidence record includes:

- contract identifier and version;
- selected families and fallback reasons;
- user directive and approved scope;
- supplied-source inventory without private package fingerprints;
- event-to-method map;
- field-to-control/grid/result map;
- caller-parameter and local-variable matrices;
- Designer and repository property plan;
- SP result/write/transaction/error contract;
- forbidden-pattern scan;
- syntax/build/verifier/manual-test results;
- blocked assumptions and unsupported parity claims;
- `token_optimizer_status=passthrough` for source text.

Normal generation records evidence about the current request only. It never mutates this packaged contract.
