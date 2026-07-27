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

1. Run KH intake and record `token_optimizer_status=passthrough` for supplied source text.
2. Record `described-behavior`, `pasted-source`, `mixed-input`, or `contract-only` evidence mode.
3. Load `packaged-style-contract.md` and `packaged-style-contract.json`. Do not discover a local style profile.
4. Select one screen family, method family, control provider, and procedure family.
5. Record the provider order: supplied target wrapper, KoneLib, DevExpress, then WinForms. Selection depends only on dependencies declared in the request.
6. Build action/event, field/control/grid/result, caller-parameter, local-variable, and SAVE row-state mappings.
7. Apply `datawindow-layout-mapping.md` when supplied DataWindow fields are available.
8. Generate C# with one select path and one save path.
9. Generate Designer members, controls, explicit grid columns, `Columns.AddRange`, and repository wiring.
   - Put construction, names, layout, `TabIndex`, binding fields, columns, repositories, `Appearance`, `Options`, and static design properties in `.Designer.cs`.
   - Keep code-behind to runtime behavior, event handlers, result binding, and evidence-backed dynamic state changes.
10. Generate a release-ready procedure only from verified, readable-path (or host-resolved URI), SHA-256-bound PB/DataWindow SQL, existing-SP, or pasted-SQL body evidence plus an authoritative caller contract. Require same-procedure or meaningful shared-fragment correlation. Bind statements plus IF/ELSE, WHILE, nested BEGIN/END, TRY/CATCH, and transaction events to one unified hierarchical trace. Only the first root-level pre-body `SET NOCOUNT ON` is wrapper ordinal `0`; all other occurrences require authority. Require one source artifact or one complete branch/composite artifact to cover the entire non-wrapper trace. A composite binds exact target, v2 canonical full-trace hash, and every correlated source hash in evidence order. Do not splice events or move them between scopes.
11. An explicitly approved inferred draft remains `pending` and non-release-ready. It may be handed off as a proposal with blockers, but it must not satisfy completion until authoritative body and caller artifacts are supplied.
12. Run migration C#/SP verifiers, then compose SQL formatting and the actual final-response binder through `sql-formatting-bridge.md`. Supply the exact final response, authoritative and selected-active provider paths, and correlated front-door provider-selection evidence.
13. Finish with `migration-output-checklist.md`.

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
- Accepts empty C# or an arbitrary class that lacks a form, initialization, migration method, and UI binding shape required by the packaged contract.
- Creates controls, sets static layout/name/`TabIndex`/binding properties, registers fixed columns or repositories, or assigns static `Appearance`/`Options` in code-behind without dynamic-state evidence.

## Done criteria

- Output is generated offline from the packaged contract and current request evidence.
- No maintenance discovery workflow ran.
- C#, Designer, and SP boundaries are internally consistent.
- All unsupported semantics and verification gaps are visible.
- Every completed SP claim names independently captured source artifacts and matching SHA-256 values, has complete per-statement and per-branch traceability, and binds caller evidence to the exact strict target procedure; inferred drafts remain pending.
- The exact final SQL response is bound to the verified original/candidate/provider receipt before delivery.
- The packaged required C# structural patterns accept the synthetic mapped form and reject empty or unrelated class text.
- The synthetic Designer file owns static UI configuration; the synthetic code-behind owns only behavior, events, runtime data binding, and approved dynamic state.
- Misplaced static UI examples are rejected unless their evidence ledger records a runtime reason and targeted verification.
- Smoke, demo-schema, and quality-audit verification pass from the repository root using the documented module command.
