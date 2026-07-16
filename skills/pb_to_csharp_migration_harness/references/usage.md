# PB To C# Migration Harness Usage

Use this harness to plan, generate, or review offline migration output for PowerBuilder behavior, DataWindow fields, C# WinForms/DevExpress/KoneLib screens, Designer code, and SQL Server SELECT/SAVE procedures.

## Runtime Boundary

Normal generation uses `packaged-style-contract.md` and `packaged-style-contract.json` as its only style profile. It may use source text or screenshots supplied directly by the user as behavior evidence. It does not discover style from the machine or refresh the packaged profile.

The maintenance-only `profile-update-workflow.md` never runs during normal generation. Invoke it only for an explicit packaged-profile update request.

Do not use this harness as the SQL formatter. Compose with host-local `sql-formatting`, then use the SQL style verifier when proof is required.

## When to use

Use this harness when a request needs an offline PB-to-C# plan, C#/Designer generation, DataWindow mapping, or SELECT/SAVE procedure drafting and review. Use the packaged contract for output shape, and use only behavior evidence supplied in the current request.

## Inputs to collect

- Exact user directive, requested outputs, target files, and excluded work.
- Behavior description or directly supplied PB/C#/Designer/DataWindow/SQL text.
- Supplied dependency declaration: target wrappers, KoneLib, DevExpress, or WinForms only.
- Screen family: browse, master-detail, detail-entry, or popup.
- Field order, captions, editor hints, validation, and row-state behavior.
- Caller values and parameter order.
- SELECT result fields or SAVE write/payload contract.
- Error, transaction, logging, and popup-return expectations.
- Evidence limitations and explicitly approved inferred-draft boundaries.

Mark PB, C#, Designer, and SQL source as `token_optimizer_status=passthrough`.

## Execution pattern

1. Run KH intake and apply its immediate gates.
2. Record one evidence mode: `described-behavior`, `pasted-source`, `mixed-input`, or `contract-only`.
3. Run `build_pb_to_csharp_migration_plan` when available, or produce its objective/mode/evidence/blocker fields manually.
4. Read `packaged-style-contract.md` and select the screen, method, control-provider, and procedure families.
5. Preserve user-supplied identifiers. For missing identifiers, use only the contract's placeholder grammars.
6. Build these mappings before code:
   - action/event to C# method;
   - field to editor, `BindingField`, grid column, and result field;
   - evidence-backed composite business key to raw result fields, display result field, and visible/hidden grid fields;
   - caller source to SP parameter;
   - derived value to SP local variable;
   - row state to payload and SAVE branch.
7. For supplied SRD/DataWindow fields, apply `datawindow-layout-mapping.md` without claiming unsupported visual parity.
8. Generate C# and Designer output in the selected family. Use one query path and one save path.
   - Write control construction and static design properties to `.Designer.cs` by default.
   - Keep code-behind limited to runtime behavior, event handlers, data binding, and evidence-backed dynamic state changes.
9. Generate a complete SP only from a supplied result/write contract or explicit inferred-draft approval.
10. Run migration C#/SP verifiers when available and compose SQL formatting through `sql-formatting-bridge.md`.
11. Complete `migration-output-checklist.md` and report blocked assumptions.

## C# Generation

- Preserve supplied namespace, class, base class, method, event, and instance names.
- Otherwise apply `<Feature><Mode>Form`, command/event handlers, and field/role control grammars from the packaged contract.
- Keep caller parameter declarations adjacent to the procedure call.
- Keep browse, focused-row detail, validation, binding, serialization, and post-save refresh steps visible.
- Do not add context DTOs, generic value accessors, broad normalization helpers, or parallel call paths.
- Do not shape SQL wildcards or derive helper dates in C#.

## Provider Selection

Use only declared dependency evidence:

1. Supplied target wrapper.
2. KoneLib.
3. DevExpress.
4. WinForms.

Do not inspect local references during normal generation. Do not add or upgrade packages. When no dependency is declared, use WinForms and record the fallback.

## Designer And DataWindow Mapping

- Preserve supplied control types, properties, bounds, containment, collection calls, `BindingField`, `FieldName`, and `TabIndex`.
- Use stable label/editor rows and columns for contract-only detail forms.
- Declare grid columns explicitly and register them with `Columns.AddRange`.
- Treat DataWindow-generated View XML as the authoritative design-time `Layout -> Load` baseline. An explicit grid contract requires both XML that passes `verify_devexpress_grid_xml_contract` and matching post-load-equivalent View, `OptionsView`, and column state in `.Designer.cs`.
- Preserve `column=(` occurrence order for XML and one-based `VisibleIndex`; visual coordinate sorting is only for form-control placement.
- Preserve converter `FieldName` and XML `Name`, including `#` and `$`. Keep `xml_column_name` separate from a valid explicit `csharp_name`; block C# generation when no safe mapping exists.
- Report local verification as static only with `actual_live_layout_load_observed=false`; caller-authored dictionaries and hashes do not prove a DevExpress Designer load.
- Preserve C# role names (`grdList`/`gvwList`, `grdDetail`/`gvwDetail`, or an explicit table/purpose suffix); XML `gridView1` is not a C# naming source.
- Keep `FieldName` identical to the documented result field.
- When an ordered base key plus sequence keys is established, retain every raw key result field and bind the visible grid column to the supplied display alias or packaged `<BASE>S` default. Generate the packaged `BASE + '-' + FORMAT(SEQUENCE, '##0')` expression in component order without adding unrelated null/type rewrites.
- Treat field names as data, not routing rules. The planner receives one key-value field and an ordered sequence-field list; it must not branch on field names, prefixes, tables, or business domains.
- Register repository editors before assigning `ColumnEdit`.
- Use numeric, lookup, button, and boolean repositories according to the packaged contract.
- Record unsupported DataWindow layout, computed, dropdown, protection, and update semantics as blocked or deferred.

## Designer ownership

- `.Designer.cs` owns static control/component fields, construction, parent containment, collection registration, names, layout, `TabIndex`, binding fields, explicit grid columns, repositories, `ColumnEdit`, `Appearance`, `Options`, and other design-time assignments by default.
- Code-behind owns behavior, event-handler implementations, validation, procedure calls, runtime data binding, and state transitions that occur while the form is running.
- Treat a static property assignment in code-behind as a failure unless supplied source or an explicit behavior contract proves it is dynamic.
- For an approved dynamic exception, record the source evidence, runtime reason, changed property, triggering state, and targeted verification.
- Scan both generated files separately and report file ownership evidence; a combined snippet is not enough to prove the boundary.
- Within each independent container, verify that located input controls follow row-major top-to-bottom/left-to-right order and have present, unique, contiguous increasing `TabIndex` values; labels and non-input controls are excluded. Validate different containers independently; each container may restart its sequence.

## Stored Procedure Generation

- Build the caller-parameter matrix first. No generated SP parameter may exist outside it unless a separate external caller is documented.
- Use local `DECLARE` variables for derived and calculation values.
- Keep raw search/date inputs at the caller boundary; SQL owns wildcard and date derivation.
- Preserve supplied branch values, predicates, literals, comments, result order, writes, and transaction behavior.
- Mark schema-dependent relationships and semantic equivalence as unproven offline.
- Do not invent a complete body from only control names, parameter names, or expected columns.

## Evidence to produce

- Contract identifier/version and selected style families.
- User directive and approved scope.
- Confirmed/inferred/blocked/proposal-only ledger.
- Event/method, field/control/grid/result, caller-parameter, and local-variable maps.
- Designer/grid/repository plan.
- Designer ownership inventory, code-behind static UI scan, and any approved dynamic-state exceptions.
- SP result/write/transaction/error plan.
- Forbidden-pattern scan and verifier results.
- Manual tests and residual risk.
- Cross-agent handoff with no hidden chat dependency.

## Failure handling

- Missing behavior evidence: generate a contract-level plan or request the exact missing behavior; do not discover local source.
- Missing dependency evidence: use WinForms fallback and mark provider confidence lower.
- Missing layout evidence: generate a stable layout plan, not a fidelity claim.
- Missing result/write contract: block the complete SP or label it as an explicitly approved inferred draft.
- SQL formatter unavailable: preserve SQL text and report formatting verification blocked.
- Verifier unavailable: perform the packaged checklist and state that deterministic verification did not run.
- Static UI found in code-behind: block completion and move it to `.Designer.cs`, unless the evidence ledger proves and tests a runtime state change.

## Quality bar

A valid run is self-contained and offline. It records the packaged contract version, selected families, behavior evidence, mappings, caller/SP boundary, Designer/grid rules, file ownership scan, forbidden-pattern result, and unsupported claims. Static UI configuration is in `.Designer.cs` by default; code-behind contains only runtime behavior, events, data binding, and justified dynamic state. The generated output must not depend on private examples, local discovery, or hidden prior context.

## Runtime binding

- Execution level: `python-module`
- Implementation targets:
  - `src.skills.pb_to_csharp_migration.build_pb_to_csharp_migration_plan`
  - `src.skills.pb_to_csharp_migration.build_composite_business_key_display_plan`
  - `src.skills.pb_to_csharp_migration.verify_composite_business_key_display_contract`
  - `src.skills.pb_to_csharp_migration.load_packaged_migration_profile`
  - `src.skills.pb_to_csharp_migration.verify_migration_generated_csharp_style`
  - `src.skills.pb_to_csharp_migration.verify_devexpress_grid_xml_contract`
  - `src.skills.pb_to_csharp_migration.verify_pb_migration_sp_generation_contract`
- Actual runtime path: from the repository root, run `python -m skills.pb_to_csharp_migration_harness.scripts.demo --output-dir <tmp>` for the packaged offline scenario, or call the listed Python targets with the exact packaged contract identity during a real migration.
- Completion rule: withhold completion when structural validation, source evidence, caller/SP mapping, or offline verification remains blocked.
