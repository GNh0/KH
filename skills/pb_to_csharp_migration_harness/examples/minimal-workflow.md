# PB To C# Migration Minimal Workflow

## Scenario

A user describes a browse-and-edit PowerBuilder screen, supplies a field list and caller parameters, and asks for offline C#, Designer, and SELECT/SAVE procedure drafts.

## Runtime contract

- `execution_level=python-module`
- `implementation_targets=src.skills.pb_to_csharp_migration.build_pb_to_csharp_migration_plan,src.skills.pb_to_csharp_migration.load_packaged_migration_profile,src.skills.pb_to_csharp_migration.verify_migration_generated_csharp_style,src.skills.pb_to_csharp_migration.verify_pb_migration_sp_generation_contract`
- `working_directory=repository root`
- `actual_runtime_path=python -m skills.pb_to_csharp_migration_harness.scripts.demo --output-dir <tmp>`
- `verification=python scripts/smoke_check.py` plus the focused demo and quality tests.

## Expected steps

1. Record `described-behavior`, `pasted-source`, `mixed-input`, or `contract-only` evidence mode and preserve any analysis-only zero-write directive.
2. Load `packaged-style-contract.md` and `packaged-style-contract.json`. Do not perform unapproved identity/name or style discovery, source-control metadata lookup, arbitrary-root traversal, sibling-project scanning, or database scanning.
3. If direct PBL access is requested, read `orca-runtime-contract.md`, select exactly one configured runtime/provider version, run the zero-execution probe where applicable, and either launch one child-scoped list/export command or use the documented fallback. Record the child `PATH` scope, exact exit code, and artifact receipts.
4. Select one screen family, event family, control provider, and procedure family. Use the canonical `Spin`/`ymd`/`pn`/`grd`/`gvw`/`col`/`rpsSpin` naming family, `CallSelectProcedure` for query, and `CallSaveProcedure` for save.
6. Record the provider order: supplied target wrapper, KoneLib, DevExpress, then WinForms. Selection depends only on dependencies declared in the request.
7. Bind the current target class to its exact direct base. For a custom base, record a readable SHA-256-bound source/binary type-chain artifact proving the chain reaches `Form` or `UserControl`; pair code-behind with the matching `.Designer.cs` partial class and keep `InitializeComponent` in the Designer.
8. Build action/event, field/control/grid/result, caller-parameter, local-variable, and SAVE row-state mappings. Compare the complete PB event inventory with C# handlers and Designer subscriptions, including absent/unsupported events.
9. Apply `datawindow-layout-mapping.md` when supplied DataWindow fields are available.
10. Generate C# with one select path and one save path.
11. Generate Designer members, controls, explicit grid columns, `Columns.AddRange`, and repository wiring.
   - Put construction, names, layout, `TabIndex`, binding fields, columns, repositories, `Appearance`, `Options`, and static design properties in `.Designer.cs`.
   - Keep code-behind to runtime behavior, event handlers, result binding, and evidence-backed dynamic state changes.
12. Generate a release-ready procedure only from verified, readable-path (or host-resolved URI), SHA-256-bound PB/DataWindow SQL, existing-SP, or pasted-SQL body evidence plus an authoritative caller contract. A caller JSON/manifest or caller-supplied hash is not proof. Require same-procedure or meaningful shared-fragment correlation. Bind statements plus IF/ELSE, WHILE, nested BEGIN/END, TRY/CATCH, and transaction events to one unified hierarchical trace. Only the first root-level pre-body `SET NOCOUNT ON` is wrapper ordinal `0`; all other occurrences require authority. Require one source artifact or one complete branch/composite artifact to cover the entire non-wrapper trace. A composite binds exact target, v2 canonical full-trace hash, and every correlated source hash in evidence order. Do not splice events or move them between scopes. If a complete PB event inventory proves no SAVE event, block every SAVE procedure and DML candidate.
13. An explicitly approved inferred draft remains `pending` and non-release-ready. It may be handed off as a proposal with blockers, but it must not satisfy completion until authoritative body and caller artifacts are supplied.
14. Run migration C#/SP verifiers, then compose semantic SQL generation and presentation formatting through `sql-formatting-bridge.md`. Supply the exact final response, provider paths, correlated provider-selection evidence, and the actual non-empty formatting-verifier history. Require matching verification IDs and original/candidate hashes.
15. Produce a structured `kh.pb-migration-handoff.v1` JSON object or schema-equivalent Markdown tables.
16. Finish with `migration-output-checklist.md`. Core validation is draft validation; completion additionally requires independent project inclusion/dependency, project build, applicable Designer layout-load, and manual-workflow receipts, plus DB/deployment receipts when claimed.

The maintenance-only `profile-update-workflow.md` never runs in this scenario.

## Expected evidence

- Packaged contract identifier and version.
- Selected style families and fallback reasons.
- Exact user scope and confirmed/inferred/blocked/proposal-only ledger.
- Event-to-method mapping.
- Field-to-editor/`BindingField`/grid/result mapping.
- Caller-parameter matrix with no extra SP parameters.
- Derived values represented as SP locals.
- Designer property, grid-column, and repository plan.
- Per-file ownership inventory proving static UI is in `.Designer.cs` and code-behind has no unapproved static design assignments.
- SELECT result and SAVE payload/write/transaction/error contracts.
- Forbidden-pattern and verifier results.
- Manual test plan and residual blockers.
- Runtime evidence naming the execution level, implementation targets called, packaged contract identity, and verification commands.
- For a PBL parity claim, correlated PBL/object-list/export/linked-DataWindow receipts; otherwise an explicit bounded or proposal-only claim scope.
- For direct PBL access, a zero-execution probe receipt and one selected-version child-operation receipt following `orca-runtime-contract.md`, including the exact exit code and produced artifact paths/hashes.
- Structured handoff inventories and independent completion receipts.

## Failure cases

- Searches local projects or systems to learn style during normal generation.
- Mixes KoneLib, DevExpress, and WinForms without a declared fallback reason.
- Invents private-looking identifiers instead of preserving supplied names or using placeholders.
- Adds context DTOs, generic value helpers, parallel call paths, or runtime grid factories.
- Adds C# wildcard/date shaping or SP helper parameters absent from the caller matrix.
- Presents a complete procedure without full per-statement source coverage and target-bound caller evidence, or presents an approved inferred draft as complete.
- Accepts a missing/unreadable source path, a mismatched SHA-256, or the generated candidate itself as source evidence.
- Treats `OUTPUT`/`READONLY` inside a default string literal as a parameter option; accepts C#-claimed SQL metadata absent from the artifact; counts a nested `DbParameter`; accepts a `DbParameter` value containing a lambda, delegate, `new` array/collection/object initializer, collection expression, assignment, binary/logical expression, or ternary; accepts a constructor/static constructor/destructor/operator/conversion/accessor, reserved-keyword return type, bare caller fragment, top-level/local function, lambda/delegate/initializer; ignores another active or unsupported `dbClient` call hidden by interpolation, conditional access, parentheses, null-forgiving syntax, comments, or whitespace; accepts caller evidence from an unknown-symbol preprocessor branch; or accepts a globally unbalanced artifact, incomplete call, wrong-case receiver, malformed procedure identity, another SP, or missing/mismatched external identity.
- Omits or inserts TRY/CATCH, moves a WHILE body to root, removes nested BEGIN/END scope, treats transaction-following `SET NOCOUNT ON` as a generated wrapper, or supplies composite `trace_sql` that omits structural events.
- Accepts a flat or cross-artifact pool of matching SQL statements after splicing source-source or branch-source arms, swapping a sibling statement with a nested branch opening, swapping `then`/`else` arms, nested arms, or same-arm statement order, or accepts a partial authority that omits events needed to prove the complete trace.
- Changes identity, comment payload or relative code position, statements, literals, or terminators during `existing_sp_cleanup` and calls it formatting-only.
- Claims PB parity, UI fidelity, or database equivalence from offline generation.
- Claims PBL source parity without PBL path/hash, runtime/version, object-list receipt, exported object/DataWindow hashes, and a complete linked graph.
- Uses target/PB source as style evidence or accepts noncanonical generated naming.
- Uses prose keywords instead of the structured handoff, or treats core validation as project completion.
- Accepts empty C# or an arbitrary class that lacks a form, initialization, migration method, and UI binding shape required by the packaged contract.
- Creates controls, sets static layout/name/`TabIndex`/binding properties, registers fixed columns or repositories, or assigns static `Appearance`/`Options` in code-behind without dynamic-state evidence.

## Done criteria

- Output is generated offline from the packaged contract and current request evidence.
- No maintenance discovery workflow ran.
- C#, Designer, and SP boundaries are internally consistent.
- All unsupported semantics and verification gaps are visible.
- Every completed SP claim names independently captured source artifacts and matching SHA-256 values, has complete per-statement and per-branch traceability, and binds caller evidence to the exact strict target procedure; inferred drafts remain pending.
- The exact final SQL response is bound to the verified original/candidate/provider receipt before delivery.
- The structured handoff passes `verify_pb_migration_analysis_document`.
- Completion is claimed only when every applicable independent completion receipt passes.
- The packaged required C# structural patterns accept the synthetic mapped form and reject empty or unrelated class text.
- The synthetic Designer file owns static UI configuration; the synthetic code-behind owns only behavior, events, runtime data binding, and approved dynamic state.
- Misplaced static UI examples are rejected unless their evidence ledger records a runtime reason and targeted verification.
- Smoke, demo-schema, and quality-audit verification pass from the repository root using the documented module command.
