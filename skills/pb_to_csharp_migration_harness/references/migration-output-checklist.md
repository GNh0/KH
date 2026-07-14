# Migration Output Checklist

Use this checklist before handoff or completion.

## Scope And Profile

- Exact user directive and approved outputs are recorded.
- Excluded and proposal-only changes are visible.
- Evidence mode is recorded.
- `packaged-style-contract.md` is the only normal-generation style profile.
- Contract identifier/version and selected screen, method, provider, and procedure families are recorded.
- The maintenance-only profile-update workflow did not run.
- Source text has `token_optimizer_status=passthrough`.

## Analysis And Mapping

- Confirmed, inferred, blocked, and proposal-only facts are separate.
- Event/action to C# method mapping is complete.
- Field to editor/`BindingField`/grid/result mapping is complete.
- Caller value to SP parameter mapping is complete and ordered.
- Derived values are listed as SP locals, not caller parameters.
- SAVE row states, payload shape, write order, transaction, error, and logging behavior are documented.
- A separate developer can implement without hidden chat context.

## C# And Designer

- Supplied identifiers and APIs are preserved.
- Missing identifiers use only packaged naming grammars.
- One query path and one save path are used.
- Provider fallback follows target wrapper, KoneLib, DevExpress, then WinForms from declared evidence.
- No dependency was added, upgraded, or retargeted.
- Designer members, initialization, containment, collections, bounds/layout, and `TabIndex` are explicit.
- Static control construction, layout, naming, binding fields, grid/repository wiring, `Appearance`, `Options`, and design properties are in `.Designer.cs` by default.
- Code-behind contains runtime behavior, event-handler implementations, validation, procedure calls, result binding, and evidence-backed dynamic state only.
- Every static UI assignment in code-behind has explicit source evidence, a runtime reason, and a targeted verification result; otherwise completion is blocked.
- Grid columns are explicit and registered with `Columns.AddRange`.
- `FieldName` matches the SP result field.
- Repository editors are registered before `ColumnEdit` assignment.
- Numeric fields use numeric editor behavior, not formatting alone.

## Stored Procedures

- Complete output has supplied result/write evidence or explicit inferred-draft approval.
- Metadata placeholders are resolved from the request or remain visibly unresolved.
- Every SP parameter exists in the caller matrix or has a documented external caller.
- Internal calculations and derived dates are local variables.
- Raw search/date values cross the caller boundary.
- Supplied predicates, literals, comments, calculations, result order, and write behavior are preserved.
- Formatting verification and semantic-equivalence claims are separate.
- Offline generation does not claim database parity.

## Forbidden Pattern Gate

- No private packaged paths, identities, database names, concrete source identifiers, hashes, snapshot counts, or fingerprints.
- No normal-generation style discovery or profile refresh.
- No invented context DTOs, broad value helpers, or parallel call paths.
- No inline C# wildcard shaping or hidden query-path date defaults.
- No SP parameters outside the caller matrix.
- No runtime fixed-column factories or loops.
- No unapproved Designer-owned static UI setup in code-behind.
- No source-unbacked empty result schema or completed SP claim.
- No unapproved dependency upgrade or semantic SQL rewrite.

## Verification

- Migration analysis verifier status is recorded when available.
- C# style verifier status is recorded when C# is generated.
- Per-file Designer ownership scan and any dynamic-state exception evidence are recorded.
- SP generation verifier status is recorded when SQL is generated.
- SQL formatter/verifier status is recorded separately.
- Build/syntax/manual checks and exact commands are recorded.
- Unsupported PB parity, UI fidelity, and DB equivalence claims remain blocked.
- Residual risks and next required evidence are explicit.

## User-Facing Output

Return the artifact or migration plan in the user's language. Keep internal KH routing details out of the final response unless an audit is requested.
