---
name: pb-to-csharp-migration-harness
description: Use when planning, generating, or reviewing offline PowerBuilder-to-C# WinForms/DevExpress/KoneLib screens, Designer code, DataWindow mappings, and SQL Server SELECT/SAVE procedures.
---

# PB To C# Migration Harness

## KH Entry Contract

- Start non-trivial work through `always-on-front-door` and honor its execution gate.
- Mark PB, C#, Designer, and SQL source text as `token_optimizer_status=passthrough`; never summarize contract-sensitive source.
- Normal generation is offline and reads `references/packaged-style-contract.md` plus `references/packaged-style-contract.json` as its only style profile.
- User-pasted source, current code supplied in the request, screenshots, and explicit behavior descriptions may define behavior, identifiers, and scope. They do not replace the packaged style profile.
- Normal generation never discovers or refreshes style from a database, binary library, export tool, local source tree, or sibling project.
- Discovery and refresh belong only to `references/profile-update-workflow.md`. That maintenance workflow never runs during normal generation and requires an explicit profile-update request.
- A reference read alone is not execution evidence. Produce a migration plan, mapping, generated artifact, verifier result, or an explicit blocked rationale.

## Runtime References

- Read `references/usage.md` for the offline generation sequence and evidence model.
- Read `references/packaged-style-contract.md` before generating or reviewing C#, Designer, grid, repository, or stored-procedure output.
- Read `references/packaged-style-contract.json` when a structured style profile is needed.
- Read `references/datawindow-layout-mapping.md` for DataWindow field-to-control and field-to-grid mapping.
- Read `references/sql-formatting-bridge.md` when SQL formatting or verifier composition is involved.
- Read `references/migration-output-checklist.md` before completion or handoff.
- Use `examples/minimal-workflow.md` for the runnable offline scenario.
- Run `python scripts/smoke_check.py` to verify package wiring, contract shape, and privacy gates.
- From the repository root, run `python -m skills.pb_to_csharp_migration_harness.scripts.demo --output-dir <tmp>` to exercise the packaged demo implemented in `scripts/demo.py`.

`references/profile-update-workflow.md` is maintenance-only. Do not read or execute it during normal generation unless the user explicitly asks to refresh the packaged profile.

## Workflow

1. Record the exact user directive, approved files, requested output, and exclusions.
2. Classify available behavior evidence:
   - `described-behavior`: the user describes the screen or workflow;
   - `pasted-source`: PB, C#, Designer, SRD, or SQL text is supplied directly;
   - `mixed-input`: described behavior plus supplied source or visual evidence;
   - `contract-only`: only the requested behavior and packaged style contract are available.
3. Build a migration plan with `build_pb_to_csharp_migration_plan` when the runtime module is available. Otherwise produce the same fields procedurally.
4. Keep `confirmed`, `inferred`, `blocked`, and `proposal-only` facts separate. Never turn an inferred improvement into an approved edit.
5. Load the packaged style contract. Select one C# style family, one control provider, one event/method family, and one SP family. Do not mix alternatives without evidence.
6. Map behavior before code:
   - PB event or described action to C# event/method;
   - source field to editor, `BindingField`, grid column, and result column;
   - caller value to stored-procedure parameter;
   - save row state to XML/table-row handling and transaction behavior.
7. Generate C# and Designer output using the contract's naming grammar, event shapes, provider order, property rules, grid conventions, and forbidden-pattern list.
8. Generate SELECT/SAVE procedure output only when the result shape and write behavior are supplied or explicitly accepted as an inferred draft.
9. Verify generated C# with `verify_migration_generated_csharp_style` and generated SQL with `verify_pb_migration_sp_generation_contract` when those runtime functions are available. Run the SQL formatter/verifier separately.
10. Finish with the migration checklist, evidence ledger, blocked assumptions, and manual test plan.

## Offline Style Rules

### C# and Events

- Preserve supplied class, namespace, event, and method names. Otherwise use the synthetic grammars in the packaged contract.
- Use one screen family: browse/list, master-detail, detail-entry, or popup.
- Use command handlers for search, save, clear, and delete only when the selected family supports them.
- Keep select and save calls in one established path. Do not invent a parallel query or save helper.
- Keep list retrieval, focused-row detail retrieval, validation, binding, and save serialization explicit.
- Pass raw editor values to the caller boundary. Do not hide wildcard shaping, date derivation, or silent defaults in C#.

### Control Provider Order

Resolve each logical control from declared dependency evidence in this order:

1. Supplied target-project wrapper type.
2. KoneLib family when KoneLib is explicitly declared.
3. DevExpress family when DevExpress is explicitly declared.
4. WinForms family when neither library is declared.

Do not inspect a local project to choose a provider during normal generation. Do not add, upgrade, or retarget UI packages.

### Designer and Controls

- Put control/component fields, construction, static layout, names, `TabIndex`, binding fields, grid columns, repositories, `Appearance`, `Options`, and other design-time properties in `.Designer.cs` by default.
- Keep code-behind limited to runtime behavior, event-handler implementations, validation, procedure calls, data binding, and evidence-backed dynamic state changes.
- A static assignment in code-behind is blocked unless supplied source or an explicit behavior contract proves the setting changes at runtime and targeted verification covers it.
- Emit explicit members, initialization, parent containment, and collection registration.
- Preserve supplied `BindingField`, `TabIndex`, bounds, docking, captions, editor properties, and grid/view links.
- Within each independent container, located input controls follow row-major top-to-bottom/left-to-right order, and their `TabIndex` values must be present, unique, and contiguous increasing; labels and non-input controls are excluded. Validate different containers independently; each container may restart its sequence.
- Treat generated View XML as the authoritative `Layout -> Load` baseline. An explicit grid contract requires both valid Layout-Load-ready XML and matching post-load-equivalent C# Designer state. Local dictionaries and file hashes never prove a live Designer load; record `actual_live_layout_load_observed=false` unless a genuinely external DevExpress host supplies stronger evidence.
- Preserve target grid names (`grdList`/`gvwList`, `grdDetail`/`gvwDetail`, or explicit table/purpose suffixes); never copy XML `gridView1` into C# naming.
- Use explicit grid columns registered through `Columns.AddRange`.
- Use repository editors for numeric, lookup, button, and boolean grid columns; register repositories before assigning `ColumnEdit`.
- Keep `FieldName` and result-column names identical.

### Caller and Stored Procedures

- The procedure signature is bounded by the caller-parameter matrix. Every procedure parameter must have a caller source or an explicitly documented external caller.
- Values used only inside the procedure are local variables declared and assigned in the procedure.
- Pass raw date/search inputs; derive helper dates and wildcard predicates inside the procedure.
- Preserve supplied result-column names, branch values, literals, comments, calculations, and row-state behavior.
- A complete SELECT/SAVE body requires supplied PB/DataWindow SQL, supplied current procedure text, schema/contract evidence in the request, or an explicit inferred-draft approval.
- Keep formatting verification separate from semantic equivalence. Offline generation cannot prove database behavior.

## Required outputs

- KH routing result and `token_optimizer_status=passthrough` for source text.
- User directive, approved scope, and output file/procedure plan.
- Input evidence mode and a `confirmed`/`inferred`/`blocked`/`proposal-only` ledger.
- Packaged contract identifier, version, selected C# family, selected provider, selected method family, and selected SP family.
- Event-to-method map and field/control/`BindingField`/grid/result map.
- Caller-parameter matrix and local-variable list.
- Designer property and grid/repository plan.
- `.Designer.cs` versus code-behind ownership inventory, misplaced-static scan, and approved dynamic-state exception evidence.
- SP branch, result-shape, transaction, error, and logging plan.
- Forbidden-pattern scan result.
- C#, Designer, SQL, build, and manual verification status, with unsupported claims left blocked.
- Cross-agent handoff that is complete without hidden chat context.

## Forbidden Patterns

- Private paths, author identities, database names, program identifiers, procedure identifiers, schema object identifiers, control instance names, hashes, source snapshots, or fingerprints in packaged references.
- Local discovery or profile refresh during normal generation.
- Invented request/context DTOs or generic value helpers for simple screen flows.
- Runtime grid-column factories when explicit Designer columns are required.
- Static control creation, layout, naming, `TabIndex`, binding fields, fixed grid/repository wiring, `Appearance`, `Options`, or design properties in code-behind without runtime-state evidence.
- Numeric `DisplayFormat` without the selected repository editor behavior.
- Inline C# wildcard shaping, hidden date defaults, or derived date parameters.
- Procedure parameters absent from the caller matrix.
- Source-unbacked schema-only result sets or completed procedure claims.
- Unrequested CTEs, temporary tables, `MERGE`, scalar-function rewrites, package upgrades, or broad architecture changes.
- Claims of PB parity, UI fidelity, or database equivalence without matching evidence.

## Common mistakes

- Treating a migration request as permission to refresh the packaged profile.
- Selecting a control provider from undeclared local dependencies.
- Mixing command/event or query/save method families in one generated screen.
- Using field names as proof of validation, layout, lookup, or write semantics.
- Emitting a complete procedure from only a control list or caller signature.
- Duplicating Designer-owned static UI setup in constructors, load handlers, or query methods.
- Reporting static formatting or syntax checks as database semantic proof.
- Omitting the caller-parameter matrix or allowing procedure-local values into the signature.
- Claiming the harness ran when only its references were read.

## UAF implementation targets

- `src.skills.pb_to_csharp_migration.MigrationInputState`
- `src.skills.pb_to_csharp_migration.build_pb_to_csharp_migration_plan`
- `src.skills.pb_to_csharp_migration.extract_datawindow_column_specs`
- `src.skills.pb_to_csharp_migration.extract_csharp_designer_control_specs`
- `src.skills.pb_to_csharp_migration.build_csharp_grid_column_designer_plan`
- `src.skills.pb_to_csharp_migration.generate_devexpress_grid_xml`
- `src.skills.pb_to_csharp_migration.verify_devexpress_grid_xml_contract`
- `src.skills.pb_to_csharp_migration.build_detail_form_layout_plan`
- `src.skills.pb_to_csharp_migration.resolve_csharp_control_stack`
- `src.skills.pb_to_csharp_migration.verify_migration_generated_csharp_style`
- `src.skills.pb_to_csharp_migration.verify_pb_migration_analysis_document`
- `src.skills.pb_to_csharp_migration.verify_pb_migration_sp_generation_contract`
- `src.skills.pb_to_csharp_migration.verify_pb_migration_sp_with_sql_formatting`
- `src.skills.sql_formatting_style.verify_sql_formatting_style`
- `src.contracts.HarnessResult`
- `skills/pb_to_csharp_migration_harness/SKILL.md`
