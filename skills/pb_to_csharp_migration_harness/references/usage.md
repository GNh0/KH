# PB To C# Migration Harness Usage

Use this harness to plan, generate, or review offline migration output for PowerBuilder behavior, DataWindow fields, C# WinForms/DevExpress/KoneLib screens, Designer code, and SQL Server SELECT/SAVE procedures.

## Runtime Boundary

Normal generation uses `packaged-style-contract.md` and `packaged-style-contract.json` as its sole default style profile. Behavior authority follows a scoped lattice: exact current target and user-supplied artifacts first; an explicitly named comparator only for the exact requested properties or behavior and exact path/SHA-256-bound scope; packaged profile for default generated style. Identity/name, root, similar-program, and history discovery is never authority and cannot fill gaps or select a comparator.

The maintenance-only `profile-update-workflow.md` never runs during normal generation. Invoke it only for an explicit packaged-profile update request.

Do not use this harness as the SQL formatter. Compose with host-local `sql-formatting`, then use the SQL style verifier when proof is required.

## When to use

Use this harness when a request needs an offline PB-to-C# plan, C#/Designer generation, DataWindow mapping, or SELECT/SAVE procedure drafting and review. Use the packaged contract for output shape, and use only behavior evidence supplied in the current request.

## Inputs to collect

- Exact user directive, requested outputs, target files, and excluded work.
- Cumulative directive ledger, including mid-work corrections, explicit conflicts/supersession, analysis-only zero-write status, and unresolved completion gates.
- Behavior description or directly supplied PB/C#/Designer/DataWindow/SQL text.
- Supplied dependency declaration: target wrappers, KoneLib, DevExpress, or WinForms only.
- Screen family: browse, master-detail, detail-entry, or popup.
- Field order, captions, editor hints, validation, and row-state behavior.
- Caller values and parameter order.
- SELECT result fields or SAVE write/payload contract.
- Error, transaction, logging, and popup-return expectations.
- Optional `designer_ui_contract` mapping for exact direct base inheritance, SHA-bound custom-base type-chain proof, numeric repositories, PB/result/control/grid lineage, label/editor layout, year-only editors, SRD captions, ownership, and tab-order validation.
- Evidence limitations and explicitly approved inferred-draft boundaries.
- SP operation: `new_generation`, `pb_srd_generation`, `existing_sp_cleanup`, or `approved_inferred_draft`.
- For pasted SQL, an explicit evidence role: `existing_procedure`, `pb_query`, or `body_fragment`.
- For a PBL source-parity claim: absolute PBL path/hash, PB runtime/version, correlated object-list receipt, unique exported `.sru`/`.srw` plus `.srd` path/hash receipts, and a complete linked-DataWindow graph.
- For an explicitly named comparator: exact path/SHA-256, allowed property/behavior scope, comparator-role to target-role map, and stale-identifier rejection inventory.
- Exact target `.csproj`, dependency declarations, generated-file ownership/inclusion mode, and evaluated inclusion evidence before build.

Keep PB, C#, Designer, and SQL source exact and uncompressed. Record `token_optimizer_status=passthrough` only when `token-optimizer` was actually selected for the surrounding large payload; otherwise omit token fields.

## Execution pattern

1. Record one evidence mode: `described-behavior`, `pasted-source`, `mixed-input`, or `contract-only`. Preserve every non-conflicting correction in the cumulative directive ledger. An analysis-only request performs zero writes. Withhold completion until every active directive and required gate is satisfied.
2. Treat current exports explicitly supplied at intake as bounded behavior evidence without claiming acquisition parity. Otherwise, when direct PBL extraction is requested, execute the deterministic bounded acquisition ladder: an explicitly configured acquisition provider, then one explicitly selected runtime capability under `orca-runtime-contract.md`, then only current exports subsequently supplied at exact paths and verified by read-back hashes. Do not discover tools, versions, or export roots and do not retry implicit versions. Record each attempted rung, probe/command, child environment where applicable, exact exit code, and artifact receipts. If no configured provider is usable and no current exports exist, return unresolved/block; do not infer behavior.
4. Run `build_pb_to_csharp_migration_plan` when available, or produce its objective/mode/evidence/blocker fields manually.
5. Apply the authority lattice, then read `packaged-style-contract.md` and select the screen, event, control-provider, and procedure families. Use only `CallSelectProcedure` for query and `CallSaveProcedure` for save. A named comparator is bounded to its authorized properties/behavior and must be structurally mapped to target roles rather than copied.
6. Preserve behavior-significant source identifiers when the operation requires preservation. Generated control and migration-method names must use `Spin<Field>`, `ymd<Field>`, `pn<Role>`, `grd<Role>`, `gvw<Role>`, `col<Role>_<FIELD>`, and `rpsSpin<Field>`; conflicting target names do not override this family.
7. Build these mappings before code:
   - action/event to C# method;
   - field to editor, `BindingField`, grid column, and result field;
   - evidence-backed composite business key to raw result fields, display result field, and visible/hidden grid fields;
   - caller source to SP parameter;
   - derived value to SP local variable;
   - row state to payload and SAVE branch;
   - complete PB event inventory to C# handlers and Designer subscriptions;
   - business validation/error outcome to its single C# or SAVE-procedure owner.
8. For supplied SRD/DataWindow fields, apply `datawindow-layout-mapping.md` without claiming unsupported visual parity.
9. Generate C# and Designer output in the selected family. Bind the exact current class to the supplied direct base type; bind a custom base to a readable SHA-256-matched source/binary type-chain artifact. Keep code-behind and `.Designer.cs` as one exact partial-class/file pair, with `InitializeComponent` owned by the Designer. Use one query path and one save path.
   - Write control construction and static design properties to `.Designer.cs` by default.
   - Keep code-behind limited to runtime behavior, event handlers, data binding, and evidence-backed dynamic state changes.
   - Emit serializer-legal Designer structure and block runtime static UI/factory compensation for missing fields, construction, containment, collections, initialization pairs, properties, or subscriptions.
10. For an existing-SP cleanup, compare the ordered typed candidate signature exactly with the original, including defaults, `OUTPUT`, and `READONLY`. For new generation, accept parameters only from actual C# caller evidence or a direct ordered caller contract; enforce SQL types whenever that contract supplies them. A caller JSON/manifest or caller-supplied hash is not proof; any external caller input must be read back, SHA-256 recomputed, and independently bound to the exact candidate `target_procedure`.
11. Generate a complete SP only from authoritative SQL/body evidence. An approved inferred draft remains pending and must not be reported as release-ready.
   - If a complete PB event inventory states `save_event_present=false`, block every generated `_SAVE`/`_SELECT_SAVE` target and every `INSERT`/`UPDATE`/`DELETE`/`MERGE` statement.
12. Run migration C#/SP verifiers and compose SQL formatting through `sql-formatting-bridge.md`. Keep semantic SQL generation separate from presentation formatting. The formatting verifier history must be non-empty and correlated to the exact final-response binding by verification ID and original/candidate hashes.
   - When `designer_ui_contract` is supplied, the C# verifier runs the standalone Designer UI aggregate after its existing Designer/tab-order parsing. It uses the verifier's actual source/Designer views, authoritative `result_fields`, and public baseline path/SHA inputs; those values cannot be overridden inside the mapping.
   - The complete standalone result is returned as `metadata.designer_ui_contract`, including its issue list and an `input_contract` receipt for result fields and baseline binding. Its issues are appended without replacing or suppressing existing verifier issues.
13. Produce a structured `kh.pb-migration-handoff.v1` JSON object or schema-equivalent Markdown tables. Keyword prose is not a valid handoff.
14. Before build, verify the exact target `.csproj`, declared dependencies, generated-file ownership, and explicit `Compile Include` or evaluated implicit SDK inclusion. Missing inclusion or dependency ownership blocks build/completion evidence.
15. Complete `migration-output-checklist.md`. Treat core validation as draft validation; require independent project-inclusion/dependency, build, applicable Designer layout-load, and manual-workflow evidence before claiming completion, plus DB/deployment evidence when those claims are made. A partial generation or successful correction is not completion.

## C# Generation

- Preserve supplied namespace/class and behavior identifiers when required by the operation. Do not use supplied method/control names to select style.
- Apply the packaged canonical command/event, query/save, and field/role naming grammars. A noncanonical generated name is blocked rather than adopted from target source.
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

Use only explicit dependency evidence from the current request artifacts. Do not inspect project roots or local references during normal generation. Do not add or upgrade packages. When no dependency is declared, use WinForms and record the fallback.

## PBL Parity Receipts

Do not equate available exported text with complete PBL source parity. A parity claim requires:

- an absolute PBL path and SHA-256 plus PB runtime and version;
- an acquisition receipt identifying the configured provider/runtime or current-export rung; a runtime rung follows `orca-runtime-contract.md` and includes zero-execution probe result where applicable, one explicit selected version, child-only environment evidence, and exact list/export exit code;
- an absolute object-list receipt path/hash that repeats the exact PBL path/hash and runtime/version;
- unique absolute exported artifact receipts with hashes, including a window/user-object source and a DataWindow source;
- a complete linked-DataWindow graph whose nodes reproduce every exported path/hash and whose edges cover every exported DataWindow.

Without all receipts, use `proposal-only` or `bounded-source-draft`. The artifacts may still drive bounded behavior analysis, but never style selection.

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
- Compare the complete authoritative PB event surface with generated C# handler signatures and Designer subscriptions. Missing, invented, duplicate, or stale-comparator event bindings fail.
- Verify Designer serializer legality directly. Runtime static control creation, factories, reflection, or post-load subscriptions cannot repair missing Designer members, construction, containment, collection registration, `BeginInit`/`EndInit`, or event hookup.

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
- A documented external caller is never proof from a caller JSON/manifest or label alone. It is usable only when the exact artifact is readable, its SHA-256 is recomputed, caller identity and strict `target_procedure` match the artifact, and the ordered typed parameter contract is independently bound to the candidate SP. Malformed identities such as an empty or third qualifier fail closed rather than collapsing during normalization.
- Do not accept caller-like fields attached to `pasted_sql`, `described_behavior`, or another unrelated evidence kind.
- In `existing_sp_cleanup`, allow only whitespace and case formatting. Preserve procedure identity, comment payloads and their relative executable-token positions, statements, operators, literals, terminators, the exact original signature, CTEs, temporary tables, and normalization. Keep the ordinary SSMS Object preamble in its original relative order. Route any requested semantic change through a separate operation.
- In new generation, reject every `#temp` table, table variable, synthetic identity allocation, or sequencing construct unless exact readable source evidence authorizes that exact construct in the exact candidate scope. Generic style, schema shape, or comparator code is insufficient. Existing cleanup preserves these constructs unchanged.
- Map business validation and error ownership before generation. When source evidence assigns a duplicate check, business predicate, `RAISERROR`/`THROW`, message, or failure result to the SAVE procedure, C# may validate transport/UI prerequisites and forward/display the SAVE outcome but must not repeat that predicate or message.
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
- Require `sql_verifier_history` to contain the actual formatting-verifier result. Its verification ID and original/candidate hashes must match `sql_verifier_history_correlation` and the binding receipt.

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
- Standalone Designer UI receipt from `metadata.designer_ui_contract` when the optional mapping is supplied.
- Manual tests and residual risk.
- Structured `kh.pb-migration-handoff.v1` with non-empty artifact, event, field, SP, confirmed/inferred/blocked, unresolved, and manual-test inventories and no hidden chat dependency.
- Project-inclusion, build, applicable Designer layout-load, manual-workflow, and any claimed DB/deployment receipts.
- Exact target project/dependency/inclusion receipt produced before build.
- Scoped authority lattice, comparator adaptation/stale-identifier scan, event-surface parity, and Designer serializer-legality receipts.
- Selected configured acquisition-provider/runtime/current-export ladder rung or explicit no-tool/no-export unresolved result.

## Failure handling

- Missing behavior evidence: generate a contract-level plan or request the exact missing behavior; do not discover local source.
- Missing dependency evidence: use WinForms fallback and mark provider confidence lower.
- Missing layout evidence: generate a stable layout plan, not a fidelity claim.
- Missing authenticated result/write/body contract: block the complete SP or label it as an explicitly approved pending inferred draft.
- SQL formatter unavailable: preserve SQL text and report formatting verification blocked.
- Verifier unavailable: perform the packaged checklist and state that deterministic verification did not run.
- Static UI found in code-behind: block completion and move it to `.Designer.cs`, unless the evidence ledger proves and tests a runtime state change.
- Missing structured handoff: block cross-agent implementation; do not substitute narrative keyword coverage.
- Missing completion receipt: keep the result at `draft_validated` or blocked according to the requested claim.
- Analysis-only directive: perform zero writes and return findings only.
- Missing configured acquisition capability and missing current exports: record unresolved behavior and block parity-dependent generation.
- Missing target `.csproj` inclusion or dependency ownership: block build and completion before compilation is treated as evidence.

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
