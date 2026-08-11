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
- SP operation: `new_generation`, `pb_srd_generation`, `existing_sp_cleanup`, or `approved_inferred_draft`.
- For pasted SQL, an explicit evidence role: `existing_procedure`, `pb_query`, or `body_fragment`.

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
9. For an existing-SP cleanup, compare the ordered typed candidate signature exactly with the original, including defaults, `OUTPUT`, and `READONLY`. For new generation, accept parameters only from actual C# caller evidence or a direct ordered caller contract; enforce SQL types whenever that caller contract supplies them. Bind caller evidence to the exact candidate `target_procedure` and program key.
10. Generate a complete SP only from authoritative SQL/body evidence. An approved inferred draft remains pending and must not be reported as release-ready.
11. Run migration C#/SP verifiers when available and compose SQL formatting through `sql-formatting-bridge.md`.
12. Complete `migration-output-checklist.md` and report blocked assumptions.

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
- For XML-based SAVE work, build `field_contracts` before SQL. Each field is classified exactly once as `editable_payload`, `technical_key`, `pb_fixed`, `db_default`, `server_derived`, or `unused`. Evidence is authoritative only when SHA-256 is recomputed from readable artifact bytes or supplied inline source text; a locator plus a shaped hash is rejected.
- Give every serialized editable/technical field an authoritative `type_contract`. Verify the declared staging-table type and every `OPENXML WITH` type against its family and capacity. Normalize decimal/numeric synonyms and harmless case/spacing, but reject numeric scale/precision loss, string-length narrowing, and incompatible date/string/numeric families. Treat one-argument `DataTable.Columns.Add("FIELD")` as a proven `System.String`; use explicit `typeof(...)` when another type is required.
- Bind C# and SQL through `csharp_payload_contract`: exact payload table variable, ordered serialized fields, row-state field and mappings, and evidence. Verify every field assignment is on a row added to the serialized table and has a source-derived RHS. Reject `DBNull.Value`, null/default, unrelated constants, and comments/strings that only resemble source use.
- Declare `insert_projection` and `update_projection` as ordered `{field, expression}` pairs. Compare each INSERT field to its SELECT/VALUES expression and each UPDATE field to its assignment expression. Normalize identifier brackets only outside SQL string literals. A PB-fixed value is one direct SQL literal, not a function, identifier, parameter, expression, or subquery.
- Omit `db_default` and `unused` fields from C#, OPENXML, INSERT, and UPDATE. Omit `pb_fixed` and `server_derived` fields from C#/OPENXML; emit them only as authorized direct target expressions. Do not use `ISNULL`, `NULLIF`, empty strings, or zero merely to populate omitted or editable fields.
- Required editable values must fail fast before the first target-table DML with the target `IF` / `BEGIN` / `RAISERROR` / `RETURN` pattern. Required text marked `nonblank` may use `ISNULL(A.FIELD, '') = ''` or explicit null/blank checks; numeric/date inputs use null checks only. The silent-default ban applies to DML projections, not validation predicates.
- Prepare the declared XML handle once, consume it through OPENXML, then call `SP_XML_REMOVEDOCUMENT` exactly once, unconditionally, as the final executable statement on the successful path after the last target DML. Cleanup under `IF`/`ELSE`/`WHILE`, later success-path execution, CATCH cleanup guards, and `SET @HANDLE = NULL` are rejected. Exceptional-path parser-memory retention remains a documented nonblocking residual risk.
- Treat INSERT/SELECT visual grouping as delegated to the official SQL final-response verifier. `verify_pb_migration_sp_generation_contract` is a semantic contract gate only; release requires correlated `sql_final_response_binding.status=bound` and `sql_final_response_release.status=passed` evidence from the composed verifier/orchestrator.
- Treat PB/DataWindow SQL, current SP text, and pasted SQL as final-completion evidence only after the host persists them to a readable artifact and records a matching SHA-256. A host-resolved URI may identify the artifact, but an unresolved URI or inline text alone remains non-authoritative.
- A C# caller artifact proves only the ordered parameter names inside exactly one active executable call that names the exact candidate `target_procedure`. Procedure identity must be a strict one-part or two-part identifier; empty or extra qualifiers are rejected before default-`DBO` normalization. The parser masks comments, non-interpolated strings, and character payloads, conservatively includes interpolated-string payloads in invocation counting, validates balanced active-code `()[]{}` delimiters, and tokenizes direct, `?.`, parenthesized, and null-forgiving `dbClient` receivers even when whitespace/comments separate tokens. Exactly one total invocation is allowed; unsupported methods count toward cardinality and the sole call must be a case-sensitive supported SP method. The artifact requires a complete containing `class`/`struct`/`record` and one complete ordinary method with a plausible built-in, qualified, generic, nullable, array, tuple, or task-like return type. Reserved control keywords and unsupported ambiguous type syntax are rejected. Constructors, static constructors, destructors, operators/conversions, accessors, bare fragments, top-level/local functions, lambdas, delegates, anonymous contexts, type-level initializers, and nested calls are rejected. The parser structurally splits top-level call arguments: argument 1 is the direct SP string and every later argument is a direct top-level `new DbParameter("@NAME", value)` constructor. The value grammar permits literals, identifiers, member chains, indexers, method calls with restricted scalar arguments, simple casts/grouping/unary values, and `??`; it rejects lambdas/delegates/anonymous functions, `new`, arrays, collection/object initializers, collection expressions, assignment, general binary/logical expressions, and ternary conditionals. Literal `#if true`/`#if false` is evaluated; an unknown-symbol conditional containing caller evidence is ambiguous and rejected unless a future artifact-bound symbol contract explicitly supports it. It cannot assert SQL type, default, `OUTPUT`, or `READONLY` metadata that the artifact does not contain.
- A documented external caller is valid only when it is verified and includes caller identity, strict `target_procedure`, a readable artifact path (or host-resolved URI), SHA-256, and an ordered typed parameter contract. The evidence `caller_id` and `target_procedure` must equal the artifact values and the artifact target must equal the candidate SP. Malformed identities such as an empty or third qualifier fail closed rather than collapsing during normalization.
- Do not accept caller-like fields attached to `pasted_sql`, `described_behavior`, or another unrelated evidence kind.
- In `existing_sp_cleanup`, allow only whitespace and case formatting. Preserve procedure identity, comment payloads and their relative executable-token positions, statements, operators, literals, terminators, the exact original signature, CTEs, temporary tables, and normalization. Keep the ordinary SSMS Object preamble in its original relative order. Route any requested semantic change through a separate operation.
- Require every executable new-generation statement and every relevant structural event to consume one matching event in a unified hierarchical stream. IF/ELSE, WHILE body scope, generic nested BEGIN/END, TRY/CATCH openings and closings, and transaction-control statements are canonical events; moving a statement across those scopes changes its path and trace key. Exact duplicate source artifact text is deduplicated, and duplicate candidate execution requires duplicate source occurrences. Trace otherwise unclassified residual executable/control tokens as semantic units instead of ignoring them. Only the first root-level `SET NOCOUNT ON` in a procedure envelope before any non-wrapper event is generated wrapper ordinal `0`; transaction, TRY/CATCH, loop, branch, nested, later, or fragment-level occurrences consume normal ordinals and require authority. Require one single independently bound source artifact or one complete SHA-bound branch/composite artifact to cover the full non-wrapper trace. Never pool disjoint trace-key counts from separate authorities. A `composite_contract` is complete only when evidence and JSON have identical exact target, complete `trace_sql`, `trace_sha256`, and nonempty ordered `source_lineage`. Compute `trace_sha256` as SHA-256 of UTF-8 compact sorted-key JSON `{"schema_version":"kh.pb.nonwrapper-trace.v2","trace_keys":[...]}`, where trace keys are all non-wrapper executable and structural candidate events in traversal order. The trace hash must equal both `trace_sql` and candidate canonical hashes. Lineage must exactly equal every correlated source artifact SHA-256 in evidence order; subsets, unknowns, duplicates, and reordering fail closed. Reject TRY/CATCH omission, scope insertion/removal, loop-body extraction, source-source or branch-source arm splicing, branch/statement sibling swaps, arm swaps, nested-arm swaps, per-arm reordering, partial branch artifacts, unrelated SQL, and candidate self-evidence even when case, comments, whitespace, or terminators differ.
- Parse SQL parameter defaults before interpreting `OUTPUT`/`READONLY`; those words inside string literals remain literal data.
- Use local `DECLARE` variables for derived and calculation values.
- Keep raw search/date inputs at the caller boundary; SQL owns wildcard and date derivation.
- Preserve supplied branch values, predicates, literals, comments, result order, writes, and transaction behavior.
- Mark schema-dependent relationships and semantic equivalence as unproven offline.
- Do not invent a complete body from only control names, parameter names, or expected columns.
- Require a concrete `DESCRIPTION`. Include `AUTHOR` or `CREATE DATE` only when authoritative source evidence provides the exact value.
- Permit the standard SSMS `USE`/`GO`, Object comment, ANSI settings, and `GO` preamble before the metadata header.
- Before delivering emitted SQL, require `verify_pb_migration_sp_with_sql_formatting` or `orchestrate_pb_migration_validation` to return `sql_final_response_binding.status=bound` for the exact nested binding and `sql_final_response_release.status=passed` for the full correlated provider-guard, verifier, and binding envelope. The release's nested `binding` must equal `sql_final_response_binding`; do not conflate release status with binding status.

## Evidence to produce

- Contract identifier/version and selected style families.
- User directive and approved scope.
- Confirmed/inferred/blocked/proposal-only ledger.
- Event/method, field/control/grid/result, caller-parameter, and local-variable maps.
- Designer/grid/repository plan.
- Designer ownership inventory, code-behind static UI scan, and any approved dynamic-state exceptions.
- SP result/write/transaction/error plan.
- Per-statement body traceability showing `branch_path`, `order_kind`, `order_in_path`, and `source_statement`, `branch_contract`, `generated_wrapper`, or `missing` coverage for every executable candidate unit.
- Forbidden-pattern scan and verifier results.
- Manual tests and residual risk.
- Cross-agent handoff with no hidden chat dependency.

## Failure handling

- Missing behavior evidence: generate a contract-level plan or request the exact missing behavior; do not discover local source.
- Missing dependency evidence: use WinForms fallback and mark provider confidence lower.
- Missing layout evidence: generate a stable layout plan, not a fidelity claim.
- Missing authenticated result/write/body contract: block the complete SP or label it as an explicitly approved pending inferred draft.
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
  - `src.skills.pb_to_csharp_migration.verify_pb_migration_save_field_contract`
  - `src.skills.pb_to_csharp_migration.verify_pb_migration_sp_with_sql_formatting`
  - `src.skills.pb_to_csharp_migration.orchestrate_pb_migration_validation`
- Actual runtime path: from the repository root, run `python -m skills.pb_to_csharp_migration_harness.scripts.demo --output-dir <tmp>` for the packaged offline scenario, or call the listed Python targets with the exact packaged contract identity during a real migration.
- Completion rule: withhold completion when structural validation, source evidence, caller/SP mapping, or offline verification remains blocked.
