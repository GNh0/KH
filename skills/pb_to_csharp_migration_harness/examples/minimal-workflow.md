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
10. Generate a complete procedure only when the request supplies the result/write contract or explicitly approves an inferred draft.
11. Run migration C#/SP verifiers when available, then compose SQL formatting through `sql-formatting-bridge.md`.
12. Finish with `migration-output-checklist.md`.

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
- Presents a complete procedure without result/write evidence or approved inferred-draft scope.
- Claims PB parity, UI fidelity, or database equivalence from offline generation.
- Accepts empty C# or an arbitrary class that lacks a form, initialization, migration method, and UI binding shape required by the packaged contract.
- Creates controls, sets static layout/name/`TabIndex`/binding properties, registers fixed columns or repositories, or assigns static `Appearance`/`Options` in code-behind without dynamic-state evidence.

## Done criteria

- Output is generated offline from the packaged contract and current request evidence.
- No maintenance discovery workflow ran.
- C#, Designer, and SP boundaries are internally consistent.
- All unsupported semantics and verification gaps are visible.
- The packaged required C# structural patterns accept the synthetic mapped form and reject empty or unrelated class text.
- The synthetic Designer file owns static UI configuration; the synthetic code-behind owns only behavior, events, runtime data binding, and approved dynamic state.
- Misplaced static UI examples are rejected unless their evidence ledger records a runtime reason and targeted verification.
- Smoke, demo-schema, and quality-audit verification pass from the repository root using the documented module command.
