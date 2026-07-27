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
- Within each independent container, located input controls follow row-major top-to-bottom/left-to-right order and have present, unique, contiguous increasing `TabIndex` values; labels and non-input controls are excluded. Different containers are validated independently and may restart their sequence.
- Static control construction, layout, naming, binding fields, grid/repository wiring, `Appearance`, `Options`, and design properties are in `.Designer.cs` by default.
- Code-behind contains runtime behavior, event-handler implementations, validation, procedure calls, result binding, and evidence-backed dynamic state only.
- Every static UI assignment in code-behind has explicit source evidence, a runtime reason, and a targeted verification result; otherwise completion is blocked.
- Grid columns are explicit and registered with `Columns.AddRange`.
- DataWindow-generated View XML has passed value-level serializer/View/OptionsView/column verification.
- Every explicit grid contract has both verified Layout-Load-ready XML and matching post-load-equivalent C# Designer defaults; neither artifact nor hand-written assignments pass alone.
- `actual_live_layout_load_observed=false` is recorded unless an external DevExpress host supplied independently trustworthy evidence; caller dictionaries and hashes are not accepted.
- XML and `VisibleIndex` order follows raw PB `column=(` occurrence order, never visual y/x order.
- XML `FieldName`/`Name` preserve `#` and `$`; any distinct C# member identifier is an explicit valid `csharp_name` mapping.
- XML and C# Designer `VisibleIndex` values are one-based and match source/`Columns.AddRange` order exactly.
- GridControl/GridView names and wiring match list, detail, or explicit table/purpose role conventions; XML `gridView1` was not copied.
- `FieldName` matches the SP result field.
- Evidence-backed composite business keys retain every raw key result field, emit the dedicated display alias, preserve component order, bind the visible grid `FieldName` to the display field, and hide raw identity columns unless source/UI evidence requires visibility.
- A supplied display alias/caption is preserved; otherwise the established ordered business-key components use the packaged `<BASE>S` default. The display expression uses direct `+ '-' + FORMAT(..., '##0')` composition without unrequested `CASE`, `ISNULL`, `CONCAT`, casts, or null/type rewrites.
- Repository editors are registered before `ColumnEdit` assignment.
- Numeric fields use numeric editor behavior, not formatting alone.

## Stored Procedures

- The selected operation is recorded as `new_generation`, `pb_srd_generation`, `existing_sp_cleanup`, or `approved_inferred_draft`.
- Complete release-ready output has independently captured, readable, SHA-256-matched result/write/body evidence; schema summaries and candidate-as-source evidence do not qualify. An approved inferred draft remains pending.
- Every executable statement and structural control event consumes one canonical event. IF/ELSE, WHILE body paths, generic nested BEGIN/END, TRY/CATCH openings and closings, and transaction-control statements preserve scope and order. Only the first root-level pre-body `SET NOCOUNT ON` in a procedure envelope is wrapper ordinal `0`; transaction-following, duplicate, later, nested, branch-path, and fragment-level forms require authority and a positive ordinal. One single independently bound source artifact or one complete SHA-bound branch/composite artifact covers the entire non-wrapper stream. A composite has exact candidate `target_procedure`, complete `trace_sql`, v2 canonical `trace_sha256`, and ordered lineage equal to every correlated source SHA-256. Structural omission/reordering/scope movement, condition-only artifacts, partial/unknown/duplicate/reordered lineage, wrong hashes, trace mismatch, cross-artifact splicing, flat fingerprint pools, branch/statement swaps, arm swaps, nested-arm swaps, and per-arm reordering are rejected.
- `DESCRIPTION` is concrete. `AUTHOR` and `CREATE DATE` are absent unless exact authoritative source evidence supplies them. No metadata placeholder remains.
- Every SP parameter exists in the caller matrix or has a documented external caller.
- C# caller evidence names a strict one-part or two-part candidate `target_procedure`, and the bound artifact is globally delimiter-balanced and contains one complete `class`/`struct`/`record`, one complete ordinary method with a plausible built-in/qualified/generic/nullable/array/tuple/task-like return type, and exactly one active `dbClient` invocation. Invocation counting includes direct, conditional-access, parenthesized, null-forgiving, whitespace/comment-separated, and interpolated-string payload forms; unsupported methods also count, so a hidden second call fails. Reserved control keywords and ambiguous unsupported return-type syntax fail closed. The sole call is a complete semicolon-terminated, case-sensitive supported SP method used as a direct method-body expression or `return`. Constructors/static constructors, destructors, operators/conversions, accessors, bare fragments, top-level/local functions, lambdas, delegates, anonymous contexts, initializers, and nested expressions are rejected. Its first top-level argument is the direct SP string; every remaining top-level argument is a direct supported `new DbParameter` constructor whose value is a restricted scalar literal/identifier/member/indexer/method/cast/grouping/unary/`??` expression. Literal preprocessor conditions are evaluated; unknown-symbol regions containing caller evidence fail closed without symbol evidence. It does not claim SQL types, defaults, `OUTPUT`, or `READONLY`.
- External caller evidence is verified and includes matching evidence/artifact caller identity and strict `target_procedure`, a readable artifact path (or host-resolved URI), SHA-256, and ordered SQL types. Empty or extra identity qualifiers fail closed.
- Pasted SQL has an explicit `existing_procedure`, `pb_query`, or `body_fragment` role and resolves to a readable, SHA-256-matched artifact, not only a summary, inline claim, or unresolved URI.
- Existing-SP cleanup changes only whitespace/case and preserves procedure identity, every comment payload at its relative executable-token position, statements, operators, literals, terminators, and the complete ordered typed original signature, defaults, `OUTPUT`, and `READONLY`.
- Parameter defaults are parsed with SQL string awareness; `OUTPUT`/`READONLY` inside literals are not options.
- Normal SSMS `USE`/`GO`, Object comment, ANSI settings, and `GO` preamble are accepted before the metadata header.
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
- Emitted SQL has an actual final-response binding receipt with exact original/candidate/final hashes and correlated provider-selection evidence.
- Build/syntax/manual checks and exact commands are recorded.
- Unsupported PB parity, UI fidelity, and DB equivalence claims remain blocked.
- Residual risks and next required evidence are explicit.

## User-Facing Output

Return the artifact or migration plan in the user's language. Keep internal KH routing details out of the final response unless an audit is requested.
