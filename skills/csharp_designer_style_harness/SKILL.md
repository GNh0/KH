---
name: csharp-designer-style-harness
description: Use when generating, modifying, or reviewing C# WinForms/DevExpress/KoneLib code-behind and .Designer.cs while preserving the exact target's helper, save, binding, and Designer patterns.
---

# C# Designer Style Harness

This skill governs generation and modification of one exact C# code-behind and `.Designer.cs` pair, then verifies the candidate against the packaged contract. It is source-bound and does not discover style from sibling trees, history, author metadata, or arbitrary files.

## KH Entry Contract

- Select this skill for C# WinForms/DevExpress/KoneLib generation, modification, or review; do not require the user to name the skill or ask for verification.
- Read the exact target source and Designer pair before editing. A catalog entry, skill read, or smoke check alone is not application evidence.
- Preserve the user's exact target paths, requested operation, exclusions, and no-write boundary. Do not expand the scope into catalog, routing, project, database, or caller changes.
- Keep `confirmed`, `inferred`, `blocked`, and `proposal-only` facts separate. Missing source, Designer, hash, identity, base-type, or event evidence remains blocked; it is never replaced with an invented control, field, helper, query, or style choice.
- Runtime evidence belongs to the current exact artifact pair. A copied demo result, reference read, or prior verification cannot authorize a different pair.

## Runtime Contract

- Execution level: `python-module`.
- Runtime entrypoint: `src.skills.csharp_designer_style_contract.verify_csharp_designer_style`.
- `actual_runtime_path=src.skills.csharp_designer_style_contract.verify_csharp_designer_style` is the execution evidence marker; catalog discovery and support-file reads are not execution.
- The package check is `python -m src.skills.uaf_skill_catalog --check --summary`; a catalog read does not replace verifier execution.
- The callable verifier returns `src.contracts.HarnessResult`, recomputes both artifact hashes, and reports structured issue codes. It never writes files.
- This is a runtime-backed verifier, not a `hybrid-harness`: the host procedure collects receipts and interprets evidence, while the Python module owns deterministic contract checks. The packaged examples and demos document the procedure but do not change the catalog classification.
- Default mode is `analysis_only=True`; use `applicable_operations=("query",)` for an explicitly read-only query surface. The default verifies both query and normal save families.

## Generation And Modification Contract

- Preserve the exact target's helper calls, query/save method family, detail row-state handling, bindings, and Designer ownership unless exact target-source or user evidence authorizes a change.
- Do not introduce `PostEditor`, `UpdateCurrentRow`, whole-table `DataTable` row rewrites, parent-key propagation, inferred composite-key values, or DTOs merely because they seem defensive. An ordinary new helper is a review concern, not a deterministic blocker by itself.
- Added/New, Modified, and Deleted/Del detail states remain delta operations. Do not replace them with full delete/reinsert without exact source or user evidence.
- Run `src.skills.csharp_designer_style.verify_csharp_edit_contract` against the pre-edit and candidate code-behind. Then run the pair verifier when source and Designer are both in scope.

## Inputs

Pass two exact artifact receipts. Each receipt contains an absolute `path` and the expected byte `sha256`, with or without the `sha256:` prefix. Source and Designer paths must be distinct.

Optional expected and target identities may name the exact form, controls, fields, methods, and procedures that must exist. Optional `identity_exceptions` and `type_chain_evidence` inputs are diagnostic-only in standalone mode: each is blocked and included in the verification binding, but neither can authorize a deviation. The public verifier accepts no trusted root, authenticator, caller signature, or private factory. A future host-issued opaque receipt must be validated outside this standalone public API.

## Workflow

1. Read the exact current source and Designer pair; do not substitute a sibling, backup, or remembered program.
2. Record existing helpers, save calls, row-state behavior, bindings, and Designer-owned members.
3. Make the smallest source-grounded change and run `verify_csharp_edit_contract` on original versus candidate.
4. Block new edit-commit calls, whole-table row rewrites, and key propagation unless exact evidence authorizes them. Review ordinary new helpers in context instead of rejecting every new method mechanically.
5. Run `verify_csharp_designer_style` for the final pair when both artifacts are in scope, then run the focused build/syntax check permitted by the task.

## Verification Contract

The fixed contract requires a partial form with explicit base-type evidence and `InitializeComponent`, canonical `CallSelectProcedure(SelectType...)` and `CallSaveProcedure()` families, explicit exception handling, semantic `grd`/`gvw`/`col<Role>_<FIELD>`/`rps...` identities, Designer-owned static controls/columns/repositories/bindings/`TabIndex`/`VisibleIndex`/event subscriptions, and exact binding-to-field relationships.

Code-behind static UI construction, runtime column factories, Designer helper methods, generic generated names, code-behind event subscriptions, DTO/wrapper abstractions, stale expected identities, and noncanonical query/save families are blocked. Project-native helpers such as `devFnc.InitControl`, `DataRowToPanel`, `GridToPanel`, and `dtMasterToDataTable` are accepted as runtime behavior when present; the verifier never invents replacements.

## Support Files

- Read `references/usage.md` for the input receipt, execution sequence, evidence fields, and failure boundary.
- Read `references/style-contract.json` when a structured packaged profile is needed; it is a read-only contract reference.
- Use `examples/minimal-workflow.md` for the bounded success and blocked scenarios.
- Run `scripts/smoke_check.py` for package wiring, implementation-target resolution, AST parsing, and demo invocation.
- Run `scripts/demo.py --output-dir <tmp>` for the runnable success/failure artifact demo. Its files stay below the supplied output directory.

## Required outputs

- A structured `HarnessResult` from `src.skills.csharp_designer_style_contract.verify_csharp_designer_style`.
- Exact source and Designer paths, recomputed byte SHA-256 values, and the packaged contract SHA-256 in verifier metadata.
- `success`, `status`, `exit_code`, a non-empty verification id, and machine-readable issue codes.
- For blocked results, the missing or conflicting evidence and a non-destructive remediation step.
- Smoke JSON and demo JSON/artifact receipts with command exit codes. Demo evidence must distinguish the passing pair from the intentionally failing pair.
- A final statement limited to the verified source/Designer contract; build, live layout, PB, database, and deployment claims require their own evidence.

## Common Mistakes

- Do not treat this `SKILL.md`, catalog metadata, a front-door selection, or a smoke pass as verifier execution.
- Do not pass unhashed strings or reuse a hash from a different path; the verifier must read the exact bytes.
- Do not accept a caller boolean as proof instead of the returned `HarnessResult`.
- Do not expect identity exceptions, type-chain claims, signatures, roots, or callbacks to authorize standalone verification; they fail closed.
- Do not infer control provider, form base type, event parity, stored-procedure method family, or Designer ownership from a sibling program or remembered project convention.
- Do not claim PB migration parity, project compilation, live DevExpress layout load, or database equivalence from this offline verifier.
- Do not turn a blocked issue into a source edit or a passing result by weakening the packaged contract.

## UAF implementation targets

- `src.skills.csharp_designer_style.verify_csharp_edit_contract`
- `src.skills.csharp_designer_style_contract.verify_csharp_designer_style`
- `src.contracts.HarnessResult`
- `skills/csharp_designer_style_harness/scripts/smoke_check.py`
- `skills/csharp_designer_style_harness/scripts/demo.py`
- `tests.test_csharp_designer_style_contract`
- `tests.test_plugin_packaging`
