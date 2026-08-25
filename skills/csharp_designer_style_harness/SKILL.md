---
name: csharp-designer-style-harness
description: Use when verifying an exact C# WinForms/DevExpress/KoneLib code-behind and .Designer.cs pair against the packaged style contract with hash-bound evidence and no-write analysis.
---

# C# Designer Style Harness

This skill verifies one exact C# code-behind and `.Designer.cs` pair against the packaged C# WinForms/DevExpress/KoneLib contract. It is source-bound, PB-independent, and does not discover style from a project root, sibling tree, source-control history, author metadata, or arbitrary files.

## KH Entry Contract

- Start non-trivial verification through `always-on-front-door` before reading target artifacts, selecting this skill, or running the verifier. This source, tool, artifact, and verification work normally requires governed runtime intake.
- A catalog entry, `selected_not_executed_skills`, a `SKILL.md` read, or a smoke check is inspection only. Report this skill as applied only after `verify_csharp_designer_style` runs against the exact hash-bound source and Designer receipts and returns a structured result.
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

## Inputs

Pass two exact artifact receipts. Each receipt contains an absolute `path` and the expected byte `sha256`, with or without the `sha256:` prefix. Source and Designer paths must be distinct.

Optional expected and target identities may name the exact form, controls, fields, methods, and procedures that must exist. Optional `identity_exceptions` and `type_chain_evidence` inputs are diagnostic-only in standalone mode: each is blocked and included in the verification binding, but neither can authorize a deviation. The public verifier accepts no trusted root, authenticator, caller signature, or private factory. A future host-issued opaque receipt must be validated outside this standalone public API.

## Workflow

1. Run the front door and record the selected provider, execution gate, and exact allowed file boundary before source inspection.
2. Read the exact source and Designer paths supplied for the current task. Recompute byte hashes and decode UTF-8; do not use sibling or backup artifacts as substitutes.
3. Call `verify_csharp_designer_style` with both receipts, the requested operation set, expected/target identities, and any packaged native-helper names. Do not manufacture authority with exception provenance or caller-owned type claims.
4. Inspect the structured `HarnessResult` metadata for artifact hashes, packaged-contract hash, `verification_binding`, verifier id, and issue codes. A successful return is evidence for that exact pair only.
5. For a blocked result, report the issue code and missing evidence. Do not repair source or Designer files inside this skill unless a separate user instruction explicitly authorizes those files.
6. Preserve the exact verifier output and demo/smoke command exit codes as evidence. Do not claim live project build, Designer layout load, PB parity, or database equivalence from this verifier alone.

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

- `src.skills.csharp_designer_style_contract.verify_csharp_designer_style`
- `src.contracts.HarnessResult`
- `skills/csharp_designer_style_harness/scripts/smoke_check.py`
- `skills/csharp_designer_style_harness/scripts/demo.py`
- `tests.test_csharp_designer_style_contract`
- `tests.test_plugin_packaging`
