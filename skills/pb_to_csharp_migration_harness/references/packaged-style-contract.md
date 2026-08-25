# Packaged PB-To-C# Style Contract

This is the sole style profile used during normal generation. It is sanitized, generalized, and self-contained so C#, Designer, and SQL Server procedure drafts can be produced offline.

Behavior authority follows a scoped lattice. Exact current target and user-supplied PB, DataWindow, screenshot, description, and target-project artifacts govern behavior first. An explicitly named comparator may govern only the exact requested properties or behavior within an exact path/SHA-256-bound scope. The packaged contract remains the sole default generated style family. Normal generation never uses identity/name, root, similar-program, history, sibling-project, database, or export-inventory discovery as authority.

The companion `packaged-style-contract.json` exposes the same decisions in a machine-readable form. User-supplied source defines behavior and behavior-significant identifiers; this contract defines all generated style, naming, and fallback behavior.

## Contract Selection

Record these selections before generation:

| Decision | Allowed values |
| --- | --- |
| Screen family | `browse`, `master-detail`, `detail-entry`, `popup` |
| Command/event handler family | `command`, `event` |
| Control provider | `target-wrapper`, `konelib`, `devexpress`, `winforms` |
| Procedure family | `select`, `save`, `select-save` |
| Evidence mode | `described-behavior`, `pasted-source`, `mixed-input`, `contract-only` |

Use one value per decision and keep it stable across a generated screen. Target/PB source cannot override the packaged style family. The sole query/save pair is `CallSelectProcedure` and `CallSaveProcedure`; no alternative migration call method is permitted.

## Source Authority

Apply authority in this order:

1. The exact current target and user-supplied artifacts govern behavior, captions, control roles, binding, events, dependency/API availability, project ownership, and database mapping.
2. A comparator explicitly named by the user governs only the exact requested properties or behavior listed in a comparator scope bound to the comparator's readable path and calculated SHA-256. It supplies structural roles, not a blanket copy source.
3. This packaged profile is the sole default style family for generated naming, methods, layout, and SQL shape.
4. Autonomous identity/name, source-root, similar-program, history, sibling-project, database, or export discovery is never authority and cannot fill a gap, choose a comparator, or broaden comparator scope.

Map every comparator role to a current-target role and adapt target semantics. Reject copied class, control, field, event, procedure, project, or dependency identifiers that are stale or lack an exact target mapping. Do not invent UX, business fields, controls, or helpers when behavior evidence is absent; record the gap.

Maintain a cumulative directive ledger. Mid-work corrections append; only explicit conflicts supersede the affected directive, and non-conflicting requirements remain active. An analysis-only directive performs zero writes. Drafts, partial generations, and successful corrections are not completion while an active directive or gate remains unresolved.

## PBL Parity Evidence

PBL source parity is allowed only when the runtime receives all of these correlated receipts:

- an absolute PBL path, its SHA-256, PB runtime name, and runtime version;
- an absolute object-list receipt path and SHA-256 whose PBL path/hash and runtime/version equal the selected PBL contract;
- unique absolute exported artifacts with SHA-256 values, including at least one `.sru` or `.srw` and at least one `.srd`;
- a `linked_datawindow_graph` with `status=complete`, nodes that match every exported path/hash, and edges that bind exported source objects to every exported `.srd`.

Missing or uncorrelated receipts force `proposal-only` or `bounded-source-draft`. Pre-exported or pasted source may support a bounded draft but does not independently prove PBL parity. None of these artifacts is style evidence.

Current exports explicitly supplied at intake are bounded behavior evidence and bypass acquisition, but do not prove PBL parity by themselves. Otherwise, direct extraction uses one deterministic bounded acquisition/fallback ladder: an explicitly configured acquisition provider, then one explicitly selected runtime capability, then only current exports subsequently supplied at exact paths and verified by read-back SHA-256. Never discover tools, versions, or export roots and never retry an implicit version. The selected runtime rung follows `orca-runtime-contract.md`: capability probing executes no process, exactly one configured runtime version is selected, only the spawned child environment changes, and exact exit code plus artifact receipts are preserved. If no configured provider is usable and no current exports exist, record unresolved/block and never infer PB behavior or parity.

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
| Query method | `CallSelectProcedure` |
| Save method | `CallSaveProcedure` |
| Focus handler | `gvw<Role>_FocusedRowChanged` |
| Text editor | `txt<Field>` |
| Lookup/button editor | `btn<Field>` |
| Combo/lookup editor | `cbo<Field>` |
| Numeric editor | `Spin<Field>` |
| Date editor | `ymd<Field>` |
| Boolean editor | `Chk<Field>` |
| Memo editor | `memo<Field>` |
| Label | `lbl<Field>` |
| Panel/group | `pn<Role>`, `grp<Role>` |
| Grid/view | `grd<Role>`, `gvw<Role>` |
| Grid column | `col<Role>_<FIELD>` |
| Numeric repository editor | `rpsSpin<Field>` |
| Other repository editor | Exact instance name from `expected_control_contracts`; no unsourced fallback name |
| Procedure | `[dbo].[usp_<Feature>_<Operation>]` |
| Procedure parameter | `@<CALLER_VALUE>` |
| Procedure local | `@Local<DerivedValue>` |

Preserve behavior-significant source identifiers when the requested operation requires preservation, including namespace/class identity, fields, result aliases, and procedure identity. Generated controls and migration methods always use this grammar. A conflicting supplied or target-source control/method name is reported as noncanonical; it does not override the packaged profile. Use PascalCase for C# symbols and uppercase snake case for SQL parameters and result fields unless an explicit preservation operation requires exact existing casing.

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

### Event-Surface Parity

- Bind the complete authoritative PB event inventory to generated C# handler signatures and Designer subscriptions.
- Preserve positive and negative authority: missing, invented, duplicate, unsupported, or stale-comparator events and subscriptions block parity.
- Event hookups belong in serializer-legal Designer output when they are static. Runtime subscriptions require exact dynamic behavior evidence and cannot compensate for a missing Designer subscription.

## Runtime C# Structural Validation

The machine-readable contract exposes these rules under `rules.csharp.required_patterns`. Every pattern is required for a complete generated C# screen candidate; the validator reports each matched or missing rule identifier.

| Rule identifier | Required generalized evidence |
| --- | --- |
| `mapped_form_declaration` | A partial class whose generated name ends in `Form` and whose declared base is a form or form-base family. |
| `designer_initialization` | A call to `InitializeComponent(...)`, proving that the screen participates in the Designer initialization path. |
| `migration_call_path` | One canonical query/save path: `CallSelectProcedure` or `CallSaveProcedure`. |
| `ui_binding_or_result_mapping` | An explicit `DataSource`, `BindingField`, or `FieldName` assignment connecting generated code to a UI or result field. |

These are structural gates, not project identity. The patterns contain only generalized C# grammar, the command/event handler families, and the fixed query/save methods. They must not encode a private identity, workstation, project, program, database, table, procedure instance, source path, or artifact fingerprint.

An empty string fails all four rules. An arbitrary class such as `public class UnmappedWidget {}` also fails because it has no form mapping, Designer initialization, migration call path, or UI/result binding evidence. A candidate does not pass merely because it compiles or contains a class declaration.

The structural gate complements the forbidden-pattern scan. A passing verifier record includes the packaged contract identifier and version, the consumed `csharp.required_patterns` rule group, every matched rule identifier, and no missing-rule issue. When the runtime cannot consume the exact packaged contract identity, validation remains blocked rather than falling back to local examples.

## Control Provider Fallback

Provider selection depends only on user-supplied dependency evidence:

1. `target-wrapper`: supplied project-owned wrappers and APIs.
2. `konelib`: KoneLib wrappers when KoneLib is declared.
3. `devexpress`: DevExpress editors, grids, views, tabs, and layout controls when DevExpress is declared.
4. `winforms`: standard WinForms controls when no richer provider is declared.

For KoneLib, map logical controls to the corresponding `u_*` wrapper family and keep its binding/reset APIs. Lookup, search, and detail roles use the evidence-backed wrapper or repository and exact `BindingField`; a text editor is not a substitute. For DevExpress, use the existing referenced API generation, not the newest online API. For WinForms, replace `BindingField` with an explicit binding map when the control has no such property.

Use wrapper/API availability only from explicitly supplied target artifacts or an explicit dependency declaration. Do not walk the project or inspect unrelated roots during normal generation. Never add packages. When dependency evidence is missing, select WinForms and record the lower-fidelity fallback.

## Exact Target Base And Designer Pair

- The current target artifact supplies the exact class identity and direct `expected_base_type`. Accept `Form`/`UserControl` only when the source declaration proves that direct base.
- For a custom project base, bind a readable source or trusted binary artifact with its SHA-256 and prove the complete type chain to `System.Windows.Forms.Form` or `System.Windows.Forms.UserControl`. A project name, namespace, similar screen, or caller declaration is not type evidence.
- Code-behind and `.Designer.cs` are one exact file/class pair: matching file identity, matching partial class, distinct role paths, and one ordinary class-member `InitializeComponent` owned by `.Designer.cs`. The current edited Designer cannot be its own preservation baseline.
- Preserve the target project's actual wrapper/base defaults and inheritance. Do not replace a custom base with a framework base, introduce a new custom base, or copy a comparator's inheritance without exact target evidence.

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

### Executable Control Contracts

Pass `expected_control_contracts` to `verify_migration_generated_csharp_style` for every generated-control verification. Each entry requires `instance_name` and `expected_type`; the type may be fully qualified or short. The inventory is fail-closed: every selected-form Designer member constructed in the sole ordinary class-member `InitializeComponent` requires exactly one entry, including custom target wrappers and components. Local functions and lookalike methods do not count as `InitializeComponent`. Optional `BindingField` and `properties` entries are exact Designer assignments, and every observed binding must be declared. Omitting the argument is a blocked contract gap. Pass an explicit empty list only when `no_control_contract_evidence` contains a non-empty evidence-backed `reason` and registry-bound `evidence_refs` proving that the generated files intentionally contain no mapped controls.

Bind verification with the target code-behind path and SHA-256 arguments and, when a separate Designer input is supplied, its target path and SHA-256 arguments. The verifier reads each path, matches the digest, decodes UTF-8, and requires exact text equality. Code-behind and Designer role paths must be distinct. Every supplied `evidence_refs` and `property_evidence` value must be a unique evidence ID resolved through the structured `evidence_registry`, even when no protected default consumes it; `property_evidence` may name only a property declared in the same contract entry.

KoneLib defaults are executable guards. A KoneLib `u_*` input must not explicitly set `Properties.AutoHeight = true`; `u_Label` keeps horizontal `Far` and vertical `Center` alignment; and generated views must not assign a custom `Appearance.EvenRow.BackColor`. An override requires both the matching exact value in `expected_control_contracts.properties` and explicit source/user provenance in that entry's `property_evidence` or `evidence_refs`. A repeated property value without provenance is rejected.

Preserve wrapper defaults and existing `Size`, `Location`, `Margin`, `MaximumSize`, `Visible`, and horizontal/vertical label alignment unless an exact contract value and registry-bound source or user evidence authorize a change. For an existing target, bind the baseline path and SHA-256 arguments to a separately captured pre-edit Designer artifact. The current target Designer path cannot serve as its own baseline. `EnableAppearanceEvenRow` may be enabled without inventing an even-row color.

## Designer Ownership Boundary

`.Designer.cs` is the default owner of static UI structure. Put control and component fields, construction, layout, names, `TabIndex`, binding fields, grid columns, repositories, `Appearance`, `Options`, collection registration, and other static design properties in the Designer partial class. This boundary applies to WinForms, declared wrapper controls, and DevExpress-style controls.

Code-behind owns runtime behavior: command logic, event-handler implementations, validation, procedure calls, result/data binding, and state changes that must occur while the screen is running. A static setting may move to code-behind only when supplied source or an explicit behavior contract proves it is dynamic; record the runtime reason and a targeted test. Without that evidence, the exception is blocked.

Designer output must remain legal for the WinForms/DevExpress serializer: fields and components are declared in the partial class, one ordinary class-member `InitializeComponent` owns construction and static setup, initialization pairs are balanced, parent containment and collections are registered, and event subscriptions reference existing members and handlers. Runtime static UI construction, reflection, post-load repair, or control/grid factories cannot satisfy or compensate for an illegal or incomplete Designer partial class.

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
- Do not whitelist tables, prefixes, domains, or field names. Source evidence supplies one key-value field, one or more sequence fields, and their exact order.
- Apply every authoritative Layout Load default, not only the commonly visible `OptionsView` subset.
- Numeric fields use a spin/numeric repository editor assigned through `ColumnEdit`.
- Numeric classification follows authoritative SQL/result shape. Use `RepositoryItemSpinEdit`; GridColumn `DisplayFormat` is not a replacement.
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
- C# passes raw search/date values through established target wrappers, including date text APIs such as `YYYYMMDD` when evidenced. SQL owns wildcard, default, and date derivation when target style evidence assigns that ownership there.
- Reuse target-project clear, query, and save helpers before generic assignments such as setting a grid `DataSource` to `null`; do not introduce DTO/helper abstractions for simple caller values.
- Do not add literal defaults, normalization blocks, or helper parameters without supplied evidence.
- SELECT result fields exactly match C# bindings and `FieldName` values.
- Composite display expressions preserve authoritative component order. The packaged direct style is `BASE + '-' + FORMAT(SEQUENCE, '##0')`, with `+ '-' + FORMAT(...)` repeated for each additional numeric sequence. Do not introduce `CASE`, `ISNULL`, `CONCAT`, casts, or other null/type rewrites without source evidence. `FORMAT` produces character output; the builder therefore requires character base-key and numeric sequence-key type evidence and never replaces the raw typed result fields.
- SAVE branches document accepted row states, XML shape, write order, transaction boundary, and returned status/result sets.
- Assign every business validation and error outcome to one owner. When exact source evidence assigns a duplicate check, business predicate, `RAISERROR`/`THROW`, message, or failure result to the SAVE procedure, C# may validate transport/UI prerequisites and invoke/forward/display the returned outcome but must not duplicate that business rule or message.

## Project And Dependency Ownership

Before any build or completion claim, bind the exact target `.csproj`, its readable current hash, declared project/package/assembly dependencies, generated-file owning project, and inclusion mode. Explicit-include projects require the exact generated `Compile Include`; implicit SDK projects require evaluated-project evidence that the exact generated files are included. A standalone compile or file existence cannot substitute for project inclusion. Missing dependency ownership, unresolved references, or absent inclusion blocks build and completion evidence.

## Stored Procedure Shapes

### Metadata And Signature

```sql
-- =============================================
-- DESCRIPTION: <purpose>
-- =============================================
CREATE OR ALTER PROCEDURE [dbo].[usp_<Feature>_<Operation>]
      @ACTION         VARCHAR(20) = NULL
    , @FILTER_TEXT    NVARCHAR(100) = NULL
AS
BEGIN
    SET NOCOUNT ON;
```

`DESCRIPTION` is required and must be concrete. `AUTHOR` and `CREATE DATE` are optional lines placed above `DESCRIPTION` only when authoritative supplied source contains their exact values. Unresolved placeholders, inferred identity values, and invented dates block output.

Operation boundaries:

- `new_generation`: signature parameters come only from actual C# caller evidence or a direct ordered caller contract; supplied SQL types must match exactly.
- `pb_srd_generation`: the new-generation rule applies and explicit PB/DataWindow SQL evidence is additionally required.
- `existing_sp_cleanup`: formatting-only equivalence allows whitespace and keyword/identifier case changes. Procedure identity, comment payloads and their relative executable-token positions, statements, operators, literals, terminators, and the ordered typed signature including defaults, `OUTPUT`, and `READONLY` must remain exact. An unchanged ordinary SSMS Object preamble is supported. A requested semantic change is a separate operation.
- `approved_inferred_draft`: requires a traceable approval artifact and approved parameter list, remains pending, and cannot be released as complete.

A complete PB event inventory is negative authority as well as positive authority. When `kind=pb_event_inventory`, `complete_event_inventory=true`, and `save_event_present=false`, the candidate must not introduce a `_SAVE`/`_SELECT_SAVE` procedure or any `INSERT`, `UPDATE`, `DELETE`, or `MERGE`. Such output is an invented SAVE flow and remains blocked even if its formatting is valid.

Pasted SQL declares one role: `existing_procedure`, `pb_query`, or `body_fragment`. A summary or object name without a readable, SHA-256-matched source artifact is not body or signature authority. Every executable candidate statement and structural control event consumes one matching event in a unified hierarchical stream. IF/ELSE, WHILE body scope, generic nested BEGIN/END, BEGIN TRY/END TRY, BEGIN CATCH/END CATCH, and transaction-control statements preserve scope and deterministic order. Duplicate execution requires duplicate source occurrences, and unclassified residual executable/control tokens remain traceable semantic units. A contained fragment cannot authorize an additional scope, branch, transaction, DML, JOIN, predicate, declaration, assignment, or error/control statement. Only the first root-level `SET NOCOUNT ON` in a real procedure envelope before every non-wrapper event is generated wrapper ordinal `0`. Every transaction-following, duplicate, later, nested, branch-path, or fragment-level occurrence is an ordinary traced event. One independently bound source artifact or one complete SHA-bound branch/composite artifact must cover the whole non-wrapper stream. Independent authorities are never pooled. A complete composite binds exact target, complete `trace_sql`, canonical `trace_sha256`, and ordered lineage equal to all correlated source hashes. The hash is SHA-256 over UTF-8 compact sorted-key JSON with schema `kh.pb.nonwrapper-trace.v2` and ordered non-wrapper executable and structural `trace_keys`. TRY/CATCH omission, loop-body extraction, scope movement, branch/statement swaps, source-source and branch-source splicing, partial/unknown/duplicate/reordered lineage, wrong hashes, arm swaps, nested-arm swaps, per-arm reordering, unrelated source SQL, and generated-candidate reuse after case/comment/terminator-only disguise are rejected.

A C# caller artifact must use a strict one-part or two-part identity for the exact candidate `target_procedure`; empty or extra qualifiers fail before normalization. A caller JSON/manifest, label, object name, or caller-supplied hash is not proof. The parser masks comments and non-interpolated string/character payloads, conservatively exposes interpolated payloads for invocation counting, validates globally balanced active-code delimiters, then tokenizes direct, conditional-access, parenthesized, and null-forgiving receivers across whitespace/comments. Every active `dbClient` invocation counts, including unsupported methods; exactly one total is allowed and it must be a case-sensitive supported SP method. The artifact requires a complete containing `class`/`struct`/`record` and one complete ordinary method with a plausible built-in, qualified, generic, nullable, array, tuple, or task-like return type. Reserved control keywords and ambiguous unsupported type syntax fail closed. Constructors, static constructors, destructors, operators/conversions, accessors, bare fragments, top-level/local functions, lambdas, delegates, anonymous contexts, type-level initializers, and nested calls are rejected. The parser structurally splits top-level arguments: the first is the direct SP string and every later argument is a direct supported `new DbParameter` constructor. Parameter values are limited to scalar literals, identifiers, member access, indexers, method calls using the same restricted argument grammar, simple casts/grouping/unary values, and `??`. Lambdas, delegates, anonymous functions, `new`, arrays, collection/object initializers, collection expressions, assignments, general binary/logical expressions, and ternary conditionals do not count. Literal preprocessor conditions are evaluated; caller evidence in an unknown-symbol conditional is rejected without artifact-bound symbol evidence. It proves ordered direct `DbParameter` names only. SQL types, defaults, `OUTPUT`, and `READONLY` require a direct trusted contract or a separately readable, SHA-256-recomputed external-caller input whose identity, target, and typed order are independently bound; the file itself never proves those claims.

The metadata parser accepts the normal SSMS `USE`/`GO`, Object block comment, `SET ANSI_NULLS`/`GO`, and `SET QUOTED_IDENTIFIER`/`GO` preamble. SQL delivery additionally requires the actual final-response binder receipt for the exact fenced candidate and correlated provider selection. The PB bridge first runs the formatting verifier and passes its non-empty structured history into the binder. The history and binding verification IDs plus original/candidate hashes must correlate, and the release's nested binding must equal the exposed binding.

### Select Family

- Use explicit action branches only when the caller matrix defines them.
- Prefer direct joins, derived tables, and aggregate subqueries.
- Use stable per-scope aliases: outer main `A`, related same-role `A1`, next roles `B`, `C`; derived-table main `T`, then `T1`, `TA1`.
- Use leading commas for parameters and selected columns.
- Preserve supplied predicates, literals, calculations, comments, and result order.
- Do not claim a complete query when table/column relationships are inferred.

### Save Family

- Parse the supplied payload using the target-compatible XML or structured-row method.
- Build `field_contracts` before SQL. Every field is classified exactly once as `editable_payload`, `technical_key`, `pb_fixed`, `db_default`, `server_derived`, or `unused`. Recompute each evidence SHA-256 from readable artifact bytes or inline source text; never authorize a locator plus an unverified hash. An editable control's initial value remains editable payload and cannot establish a fixed SQL literal.
- Require an authoritative `type_contract` for every serialized editable/technical field. The staging table and each `OPENXML WITH` schema preserve the authoritative family and capacity. Normalize decimal/numeric synonyms and harmless case/spacing; block precision/scale loss, string narrowing, and incompatible families. A one-argument `DataTable.Columns.Add` proves `System.String`; explicit `typeof(...)` proves another type.
- Bind the exact C# payload table, ordered serialized fields, row-state field and Added/Modified/Deleted mapping through `csharp_payload_contract`. Verify the exact C# source assigns every serialized field on the row actually added to that table. Require source-derived RHS evidence and reject `DBNull.Value`, null/default, unrelated constants, and non-code decoys.
- Declare INSERT and UPDATE as ordered field-to-expression projections. Compare INSERT columns to SELECT/VALUES expressions and UPDATE fields to assignment expressions. Do not reduce them to sets. Normalize identifier brackets only outside literals. A PB-fixed value must be one direct SQL literal and its own target expression; functions, identifiers, parameters, compound expressions, subqueries, comments, and unrelated literals do not count.
- Omit `db_default` and `unused` from C#, OPENXML, INSERT, and UPDATE. Omit `pb_fixed` and `server_derived` from C#/OPENXML. Do not populate omitted/editable fields with empty/zero values or `ISNULL`/`NULLIF` coercion.
- Required editable values use a field-specific pre-target-DML `IF EXISTS` / `BEGIN` / `RAISERROR` / `RETURN` guard. Text marked `nonblank` may use `ISNULL(A.FIELD, '') = ''` or explicit null/blank predicates; numeric/date fields use null checks. `ISNULL`/`NULLIF` is blocked only when it silently rewrites a DML projection.
- Prepare the declared XML handle exactly once, use it for OPENXML, and emit one unconditional `SP_XML_REMOVEDOCUMENT` as the final executable statement on the successful path after the last target DML. Cleanup under `IF`/`ELSE`/`WHILE`, later success-path execution, CATCH cleanup, and `SET @HANDLE = NULL` fail; exceptional-path session parser-memory retention remains a nonblocking residual risk.
- Run `verify_pb_migration_save_field_contract` with the exact C# source and pass both through the SP and orchestration gates. INSERT/SELECT line grouping is delegated to the official SQL final-response verifier. A standalone SP-contract pass is never release authorization.
- Stage rows in a table variable, `#temp` table, or another temporary structure only when exact readable source evidence authorizes that exact construct in the exact candidate scope.
- Do not generate synthetic identity allocation or sequencing such as a new `IDENTITY`, sequence consumption, or `ROW_NUMBER` unless exact source evidence authorizes the exact construct. Generic SAVE style, schema shape, or comparator code is not authority.
- Validate before opening the transaction where possible.
- Use an explicit transaction for writes and the supplied error/logging contract.
- Prefer separate `UPDATE` and `INSERT` statements when no upsert primitive is supplied.
- Preserve logical-delete behavior only when supplied evidence defines it.

## Forbidden Generation Patterns

- Private or environment-derived identifiers, paths, identity values, hashes, snapshot counts, or source fingerprints.
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
- New table variables, `#temp` tables, synthetic identity allocation, or sequencing constructs without exact construct-level source authority. `existing_sp_cleanup` preserves existing constructs and behavior rather than deleting or rewriting them.
- Dependency upgrades, invented custom-control flags, or API calls from a different library generation.
- Runtime static UI/control/grid factories or post-load repair used to compensate for serializer-illegal Designer output.
- Stale comparator identifiers outside an exact current-target role mapping.
- C# duplication of business validation or error behavior assigned by authoritative evidence to the SAVE procedure.

## Evidence Requirements

After every generated C# or Designer change, execute `verify_migration_generated_csharp_style` or `orchestrate_pb_migration_validation` with complete `expected_control_contracts`, exact target paths/digests, a structured registry for every evidence reference, and a separately captured baseline path/digest when an existing Designer is being preserved. Reading this skill, reading a smoke test, or running only package smoke checks is not generated-file validation.

The analysis-to-implementation handoff is schema `kh.pb-migration-handoff.v1` JSON or schema-equivalent Markdown tables. It requires non-empty artifact rows (`artifact_id`, readable `path`, `sha256`), event rows (`pb_event`, `csharp_method`, artifact IDs), field rows (`dw_field`, `control`, `binding_field`, `grid_column`, `result_field`, artifact IDs), SP rows (`procedure`, `caller`, `branch`, `result`, caller/procedure artifact IDs), explicit non-empty `confirmed`/`inferred`/`blocked` inventories, a non-empty unresolved inventory, and manual-test rows (`workflow`, `expected`, artifact IDs where evidence exists). Every referenced ID must resolve to an artifact whose bytes were read back and whose SHA-256 matches. Keyword prose, caller labels, unbound paths, and empty required inventories fail; the implementer must not rediscover evidence from hidden chat context.

```json
{
  "schema_version": "kh.pb-migration-handoff.v1",
  "artifacts": [{"path": "<artifact-path>", "sha256": "sha256:<digest>"}],
  "event_mappings": [{"pb_event": "<event>", "csharp_method": "<method>"}],
  "field_mappings": [{"dw_field": "<field>", "control": "<control>", "binding_field": "<binding>", "grid_column": "<column>", "result_field": "<result>"}],
  "sp_mappings": [{"procedure": "<procedure>", "caller": "<caller>", "branch": "<branch>", "result": "<result>"}],
  "evidence_status": {"confirmed": ["<fact>"], "inferred": ["<fact>"], "blocked": ["<fact>"]},
  "unresolved": ["<gap>"],
  "manual_tests": [{"workflow": "<workflow>", "expected": "<expected-result>"}]
}
```

Core validation runs in the exact order `load-profile`, `validate-csharp`, `validate-sp`, and `final-sql-binding`. Core success without a completion claim is only `draft_validated`. Before build, require an exact target project/dependency/inclusion receipt. Completion always requires independent `project-inclusion`, `project-build`, and `manual-workflow` receipts. It additionally requires `designer-layout-load` when Designer source exists, and `database-equivalence` or `deployment` when either is claimed. A receipt passes only with status `passed`, `verified`, or `succeeded`, no nonzero exit code, and at least one observable evidence key such as receipt ID, path, command, SHA-256, `verified=true`, or scenarios. No receipt may override an active directive, analysis-only zero-write boundary, unresolved event/Designer/SQL ownership gap, or missing PBL acquisition evidence.

A generated artifact is release-ready only when its evidence record includes:

- contract identifier and version;
- selected families and fallback reasons;
- user directive and approved scope;
- cumulative directive ledger, analysis-only write status, and unresolved completion gates;
- authority-lattice result and any path/SHA-bound comparator scope plus target-adaptation/stale-identifier scan;
- supplied-source inventory without private package fingerprints;
- event-to-method map;
- field-to-control/grid/result map;
- caller-parameter and local-variable matrices;
- Designer and repository property plan;
- event-surface parity and Designer serializer-legality result;
- SP result/write/transaction/error contract;
- structured `kh.pb-migration-handoff.v1` receipt;
- SQL verifier-history/binding correlation;
- project-inclusion, build, applicable Designer, manual, and claimed DB/deployment receipts;
- exact target `.csproj`, dependency ownership, evaluated file inclusion, and pre-build gate receipt;
- selected configured acquisition-provider/runtime/current-export ladder rung or explicit no-tool/no-export unresolved result;
- forbidden-pattern scan;
- syntax/build/verifier/manual-test results;
- blocked assumptions and unsupported parity claims;
- `token_optimizer_status=passthrough` for source text.

Normal generation records evidence about the current request only. It never mutates this packaged contract.
