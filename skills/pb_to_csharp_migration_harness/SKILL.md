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
4. Keep `confirmed`, `inferred`, `blocked`, and `proposal-only` facts separate. Never turn an inferred improvement into an approved edit. Real PB/SRU/SRD/DataWindow evidence and the actual target project govern behavior, captions, control roles, bindings, events, and database mapping. Do not invent UX, business fields, or helpers.
5. Load the packaged style contract. Select one C# style family, one control provider, one event/method family, and one SP family. Do not mix alternatives without evidence.
6. Map behavior before code:
   - PB event or described action to C# event/method;
   - source field to editor, `BindingField`, grid column, and result column;
   - caller value to stored-procedure parameter;
   - save row state to XML/table-row handling and transaction behavior.
7. Generate C# and Designer output using the contract's naming grammar, event shapes, provider order, property rules, grid conventions, and forbidden-pattern list.
8. Select an explicit SP operation before generation: `new_generation`, `pb_srd_generation`, `existing_sp_cleanup`, or `approved_inferred_draft`. Never apply new-generation prohibitions to a preservation-only cleanup, and never release an inferred draft as complete.
9. Generate SELECT/SAVE procedure output only when the selected operation has authoritative body/signature evidence. Pasted SQL must declare its role as `existing_procedure`, `pb_query`, or `body_fragment`; a prose summary or object name is not SQL authority. For new generation, every executable candidate statement must match a complete statement from independently bound source evidence. A contained fragment cannot authorize extra DML, JOINs, predicates, assignments, declarations, or error/control statements.
10. After every generated C# or Designer change, execute `verify_migration_generated_csharp_style` or `orchestrate_pb_migration_validation` against the exact target paths and SHA-256 digests with complete `expected_control_contracts`. Every selected-form member constructed in the sole class-member `InitializeComponent` requires one entry, including custom target wrappers and components. Omitting the argument is a blocked contract gap. Pass an explicit empty list only when `no_control_contract_evidence` records an evidence-backed reason and registry-bound references. Every supplied `evidence_refs` or `property_evidence` ID must resolve through `evidence_registry`, even when no default guard consumes it. For an existing Designer, also bind a separately captured pre-edit baseline path and digest; the current target file cannot serve as its own baseline. Reading this skill or running only a smoke check is not execution evidence. Verify generated SQL separately with `verify_pb_migration_sp_generation_contract` and the SQL formatter/verifier.
11. Finish with the migration checklist, evidence ledger, blocked assumptions, manual test plan, and an analysis-to-implementation handoff complete enough for another agent to proceed without rediscovery.

## Offline Style Rules

### C# and Events

- Preserve supplied class, namespace, event, and method names. Otherwise use the synthetic grammars in the packaged contract.
- Use one screen family: browse/list, master-detail, detail-entry, or popup.
- Use command handlers for search, save, clear, and delete only when the selected family supports them.
- Keep select and save calls in one established path. Do not invent a parallel query or save helper.
- Keep list retrieval, focused-row detail retrieval, validation, binding, and save serialization explicit.
- Reuse established target-project clear, query, and save helpers before generic assignments or new helpers.
- Pass raw editor values through existing wrappers, including date text APIs such as `YYYYMMDD`, when target evidence uses them. Let the procedure own date/default/wildcard derivation when target style evidence says so; do not add client-side derivation, DTOs, or value helpers.

### Control Provider Order

Resolve each logical control from declared dependency evidence in this order:

1. Supplied target-project wrapper type.
2. KoneLib family when KoneLib is explicitly declared.
3. DevExpress family when DevExpress is explicitly declared.
4. WinForms family when neither library is declared.

When the target project is supplied as migration evidence, its available wrappers and APIs take precedence. Otherwise do not inspect unrelated local projects to choose a provider. Do not add, upgrade, or retarget UI packages.

### Designer and Controls

- Put control/component fields, construction, static layout, names, `TabIndex`, binding fields, grid columns, repositories, `Appearance`, `Options`, and other design-time properties in `.Designer.cs` by default.
- Keep code-behind limited to runtime behavior, event-handler implementations, validation, procedure calls, data binding, and evidence-backed dynamic state changes.
- A static assignment in code-behind is blocked unless supplied source or an explicit behavior contract proves the setting changes at runtime and targeted verification covers it.
- Emit explicit members, initialization, parent containment, and collection registration.
- Preserve wrapper defaults and existing `Size`, `Location`, `Margin`, `MaximumSize`, `Visible`, `BindingField`, `TabIndex`, docking, captions, editor properties, and grid/view links unless an exact contract value plus registry-bound source or user evidence authorizes a change. Preserve horizontal and vertical label alignment defaults. Verify existing values against a separately captured pre-edit Designer baseline.
- Map lookup, search, and detail roles to the evidence-backed wrapper or repository type and exact `BindingField`; never replace a role-specific control with a text editor.
- Within each independent container, located input controls follow row-major top-to-bottom/left-to-right order, and their `TabIndex` values must be present, unique, and contiguous increasing; labels and non-input controls are excluded. Validate different containers independently; each container may restart its sequence.
- Treat generated View XML as the authoritative `Layout -> Load` baseline. An explicit grid contract requires both valid Layout-Load-ready XML and matching post-load-equivalent C# Designer state. Local dictionaries and file hashes never prove a live Designer load; record `actual_live_layout_load_observed=false` unless a genuinely external DevExpress host supplies stronger evidence.
- Preserve target grid names (`grdList`/`gvwList`, `grdDetail`/`gvwDetail`, or explicit table/purpose suffixes); never copy XML `gridView1` into C# naming.
- Use explicit grid columns registered through `Columns.AddRange`.
- Use repository editors for numeric, lookup, button, and boolean grid columns; register repositories before assigning `ColumnEdit`. Numeric result fields use `RepositoryItemSpinEdit` based on SQL/result shape, never GridColumn `DisplayFormat` as a substitute.
- `EnableAppearanceEvenRow` may be enabled, but do not invent an `Appearance.EvenRow.BackColor` value.
- Keep `FieldName` and result-column names identical.
- For an evidence-backed composite business identifier, keep every raw base/sequence key in the SELECT result for identity and logic, and bind the visible grid column to a separate display result field. Hide raw key columns by default unless PB/UI evidence requires them visible.
- Do not infer components from a table name alone. Once PB/DataWindow/result/schema evidence establishes an ordered base key plus sequence keys, preserve a supplied display alias or derive the packaged `<BASE>S` default.
- The contract is field-name agnostic: one key-value field plus one or more ordered sequence fields. Never implement a table, prefix, business-domain, or column-name whitelist.

### Caller and Stored Procedures

- The procedure signature is bounded by the caller-parameter matrix. Every procedure parameter must have a caller source or an explicitly documented external caller.
- Caller evidence is trusted only from an actual `csharp_call`, a direct ordered host caller contract, or a verified external-caller artifact. Procedure identity uses a strict one-part or two-part identifier; empty or extra qualifiers are invalid before normalization. The evidence and bound artifact must identify the exact candidate `target_procedure`. C# verification masks comments, non-interpolated strings, and character payloads, but conservatively exposes interpolated-string payloads to invocation counting. It validates active-code delimiters and tokenizes direct, conditional-access, parenthesized, and null-forgiving `dbClient` receivers while allowing whitespace/comments between tokens. Every active invocation counts, including unsupported methods; exactly one total call may exist and it must be the supported, case-sensitive `GetDataSetFromSP`, `ExecSPTrn`, or `ExecSP` form. The artifact must contain a complete `class`, `struct`, or `record` and one complete ordinary containing method whose return type is a plausible built-in, qualified, generic, nullable, array, tuple, or task-like type. Reserved control keywords and ambiguous unsupported type syntax fail closed. The call must be a direct expression or `return` statement in that method. Constructors, static constructors, destructors, operators/conversions, accessors, bare fragments, top-level/local functions, lambdas, delegates, anonymous contexts, field initializers, and nested calls are rejected. The first top-level argument must be the direct SP string and every remaining top-level argument must be the supported direct `new DbParameter("@NAME", value)` form. Supported values are scalar literals, identifiers, member access, indexers, method calls with the same restricted argument grammar, simple casts/grouping/unary scalar values, and `??` fallback. Lambdas, delegates, anonymous functions, `new` expressions, arrays/collections/object initializers, collection expressions, assignments, general binary/logical expressions, and ternary conditionals do not count. Literal `#if true`/`#if false` is evaluated; caller evidence inside an unknown-symbol conditional is ambiguous and rejected without artifact-bound build symbols. A bound C# call proves ordered names only; it does not prove SQL type, default, `OUTPUT`, or `READONLY`. Rich metadata requires a direct trusted contract or a verified external-caller JSON artifact whose `caller_id`, strict `target_procedure`, readable path, SHA-256, and ordered typed contract all match.
- Parse parameter defaults with SQL string awareness. Text such as `N'A OUTPUT READONLY B'` is a default literal, not a direction option.
- `existing_sp_cleanup` is formatting-only: preserve procedure identity, every comment payload and its relative executable-token position, every statement/operator/literal/terminator, and the complete ordered signature including defaults, `OUTPUT`, and `READONLY`. Only whitespace and keyword/identifier case may differ. The normal SSMS Object preamble remains supported when its content and relative order are unchanged. A semantic change requires a separate explicit operation.
- Values used only inside the procedure are local variables declared and assigned in the procedure.
- Pass raw date/search inputs through established target wrappers; derive helper dates, defaults, and wildcard predicates inside the procedure when target evidence assigns that ownership there.
- Before generating an XML-based SAVE procedure, declare every involved field once in `field_contracts` as `editable_payload`, `technical_key`, `pb_fixed`, `db_default`, `server_derived`, or `unused`. Every evidence entry has a source-grounded kind and a SHA-256 verified against either readable artifact bytes or included inline source text. A locator plus caller-supplied hash is not authority. An editable control's initial value remains `editable_payload`; it is never promoted to `pb_fixed` merely because PB initializes it.
- Every serialized editable or technical field declares an authoritative `type_contract` with `sql_type` and cryptographically bound type evidence. The declared staging-table type and every `OPENXML WITH` type must preserve that type family and capacity. Decimal/numeric synonyms and harmless case/spacing normalize; scale/precision, string length, or family narrowing blocks. `DataTable.Columns.Add("FIELD")` proves `System.String`; an explicit `typeof(...)` proves that declared C# type.
- Declare `csharp_payload_contract` with the exact payload table variable, ordered serialized fields, technical row-state field, Added/Modified/Deleted mapping, and evidence. The exact C# source must construct that field inventory and assign every serialized field on the exact row added to the serialized table. Each editable/technical RHS must be source-derived; `DBNull.Value`, null/default, pure constants, and comment/string decoys fail. A correlated row-state branch mapping is valid source derivation for the row-state field.
- Declare ordered `insert_projection` and `update_projection` field-to-expression pairs. The verifier compares INSERT columns to SELECT/VALUES expressions and UPDATE assignments without reducing them to sets. Expression normalization may remove identifier brackets and external whitespace, but never changes string-literal content. `pb_fixed.fixed_value_sql` must be one direct string/Unicode, numeric/bit, `NULL`, or hex literal and the direct expression for its own target field; functions, identifiers, parameters, compound expressions, and subqueries fail. `db_default` and `unused` fields are omitted from generated DML.
- Required editable inputs use a field-specific `IF EXISTS` / `BEGIN` / `RAISERROR` / `RETURN` guard before the first target-table DML. Text fields marked `nonblank` may use the established `ISNULL(A.FIELD, '') = ''` validation form or explicit null/blank predicates; numeric/date fields use type-appropriate null checks. `ISNULL`/`NULLIF` remains forbidden as a silent DML projection default.
- Declare one `xml_handle_variable`. Prepare it exactly once, use it for every `OPENXML`, then emit exactly one unconditional `SP_XML_REMOVEDOCUMENT` as the final executable statement on the successful path after the last payload consumption and target DML. Cleanup under `IF`/`ELSE`/`WHILE`, a later success-path statement, CATCH cleanup, and `SET @HANDLE = NULL` all fail. An error before normal cleanup retains a documented, nonblocking residual risk of session-scoped parser memory retention.
- Run `verify_pb_migration_save_field_contract` with the exact C# source, then pass the same contract and C# source through SP generation and orchestration. INSERT/SELECT line grouping remains the official SQL verifier's responsibility. A standalone SP-contract pass never authorizes release; only a correlated final SQL binding/release receipt can let orchestration complete.
- Preserve supplied result-column names, branch values, literals, comments, calculations, and row-state behavior.
- Build composite display SQL only from authoritative PB/DataWindow/result/business-key evidence. The packaged `BASE + '-' + FORMAT(SEQUENCE, '##0')` family appends additional sequences in key order. Do not add `CASE`, `ISNULL`, `CONCAT`, casts, or different null handling unless the source contract explicitly requires it.
- A release-ready SELECT/SAVE body requires independently captured PB/DataWindow SQL, current procedure text, or pasted SQL bound to a readable path and matching SHA-256. Every executable statement and relevant structural event is fingerprinted after comment/case/whitespace normalization and consumes one unified ordinal within its hierarchical path. Structural events include IF/ELSE arms, WHILE bodies, nested generic BEGIN/END scopes, BEGIN TRY/END TRY, BEGIN CATCH/END CATCH, and transaction-control statements. Scope movement, omission, insertion, or reordering changes the canonical trace. Only the first root-level `SET NOCOUNT ON` in a real procedure envelope, before every non-wrapper event, is a generated wrapper at ordinal `0`; transaction, TRY/CATCH, loop, branch, or nested scope context prevents wrapper classification. One single independently bound source artifact or one complete SHA-bound branch/composite artifact must cover the candidate's entire non-wrapper stream and topology. Separate source and branch artifacts are supporting evidence only and cannot pool disjoint trace keys. A composite authority must carry exact `target_procedure`, `trace_sql`, `trace_sha256`, and ordered `source_lineage`. `trace_sha256` is SHA-256 over UTF-8 canonical JSON `{"schema_version":"kh.pb.nonwrapper-trace.v2","trace_keys":[...]}` using sorted keys and compact separators; `trace_keys` are every candidate non-wrapper executable or structural trace key in traversal order. The evidence and JSON fields must match, the canonical `trace_sql` hash must equal the candidate hash, and lineage must exactly equal all correlated source authority SHA-256 values in evidence order with no unknown, missing, duplicate, or reordered entry. A flat pool cannot authorize scope movement, TRY/CATCH omission, loop-body extraction, arm swaps, nested-arm swaps, branch/statement swaps, reordering, or cross-artifact `then`/`else` splicing. A smaller source fragment cannot authorize a new scope, branch, transaction, DML, JOIN, predicate, declaration, assignment, or error/control statement. Unrelated SQL is not evidence. Candidate output cannot authenticate itself after case, comments, whitespace, or terminator-only disguise.
- `approved_inferred_draft` requires a traceable approval artifact and approved parameter contract, and remains `pending`/non-release-ready until authoritative body and caller evidence exist.
- The metadata header always contains a concrete `DESCRIPTION` derived from the supplied program/purpose. `AUTHOR` and `CREATE DATE` are optional and may appear only when exact values are present in authoritative source evidence; never invent them or emit placeholders.
- Accept the normal SSMS `USE`/`GO`, Object block comment, `SET ANSI_NULLS`/`GO`, and `SET QUOTED_IDENTIFIER`/`GO` preamble immediately before the metadata header.
- When SQL is emitted, run the actual final-response binder with the exact original, candidate, fenced final response, selected active provider path, and correlated front-door provider-selection evidence. A style check alone does not authorize delivery.
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
- SP operation, source-role ledger, exact original-signature comparison when cleaning an existing procedure, and caller-authority evidence.
- Forbidden-pattern scan result.
- C#, Designer, SQL, build, and manual verification status, with unsupported claims left blocked.
- Cross-agent handoff containing PB behavior, event flow, control-role map, field/`BindingField` map, SP/caller contract, proven-versus-inferred labels, unresolved gaps, and manual tests; it must be complete without hidden chat context or rediscovery.

## Forbidden Patterns

- Private paths, author identities, database names, program identifiers, procedure identifiers, schema object identifiers, control instance names, hashes, source snapshots, or fingerprints in packaged references.
- Local discovery or profile refresh during normal generation.
- Invented request/context DTOs or generic value helpers for simple screen flows.
- Runtime grid-column factories when explicit Designer columns are required.
- Static control creation, layout, naming, `TabIndex`, binding fields, fixed grid/repository wiring, `Appearance`, `Options`, or design properties in code-behind without runtime-state evidence.
- Numeric `DisplayFormat` without the selected repository editor behavior.
- Text-control substitution for evidence-backed lookup, search, or detail roles.
- Inline C# wildcard shaping, hidden date defaults, or derived date parameters.
- Generic clear/query/save assignments when an established target-project helper exists.
- Procedure parameters absent from the caller matrix.
- Source-unbacked schema-only result sets or completed procedure claims.
- Source-unbacked `AUTHOR`/`CREATE DATE`, metadata placeholders, untyped external caller evidence, or release-ready inferred drafts.
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
- Treating a skill read or smoke check as generated-file verifier execution.
- Omitting the caller-parameter matrix or allowing procedure-local values into the signature.
- Claiming the harness ran when only its references were read.

## UAF implementation targets

- `src.skills.pb_to_csharp_migration.CompositeBusinessKeyDisplaySpec`
- `src.skills.pb_to_csharp_migration.CompositeBusinessKeyDisplayObservation`
- `src.skills.pb_to_csharp_migration.build_composite_business_key_display_plan`
- `src.skills.pb_to_csharp_migration.verify_composite_business_key_display_contract`
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
- `src.skills.pb_to_csharp_migration.verify_pb_migration_save_field_contract`
- `src.skills.pb_to_csharp_migration.verify_pb_migration_sp_with_sql_formatting`
- `src.skills.pb_to_csharp_migration.orchestrate_pb_migration_validation`
- `src.skills.sql_formatting_style.verify_sql_formatting_style`
- `src.contracts.HarnessResult`
- `skills/pb_to_csharp_migration_harness/SKILL.md`
