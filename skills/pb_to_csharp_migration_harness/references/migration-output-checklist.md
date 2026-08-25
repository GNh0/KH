# Migration Output Checklist

Use this checklist before handoff or completion.

## Scope And Profile

- Exact user directive and approved outputs are recorded.
- Excluded and proposal-only changes are visible.
- Evidence mode is recorded.
- `packaged-style-contract.md` is the only normal-generation style profile.
- No unapproved external style discovery, private identity lookup, source-control metadata lookup, arbitrary-root traversal, sibling-project scan, or database style scan ran.
- PB and target artifacts were used only for behavior, fields, captions, events, dependency availability, and DB mapping; they did not override style.
- Contract identifier/version, selected screen, command/event handler family, provider, canonical query/save methods, and procedure family are recorded.
- Exact current target class, direct base type, and paired code-behind/`.Designer.cs` identity are recorded. A custom base has a readable SHA-256-bound source/binary type-chain proof to `Form` or `UserControl`.
- The maintenance-only profile-update workflow did not run.
- Source text has `token_optimizer_status=passthrough`.

## Analysis And Mapping

- Confirmed, inferred, blocked, and proposal-only facts are separate.
- PB/SRU/SRD/DataWindow and target-project evidence governs behavior, captions, control roles, binding, events, and DB mapping; no UX, business field, control, or helper is invented.
- Event/action to C# method mapping is complete.
- The complete PB event inventory matches C# handler signatures and Designer subscriptions, including explicit absent/unsupported events.
- Field to editor/`BindingField`/grid/result mapping is complete.
- Caller value to SP parameter mapping is complete and ordered.
- Derived values are listed as SP locals, not caller parameters.
- SAVE row states, payload shape, write order, transaction, error, and logging behavior are documented.
- The handoff uses schema `kh.pb-migration-handoff.v1` JSON or schema-equivalent Markdown tables with non-empty artifact, event, field, SP, confirmed/inferred/blocked, unresolved, and manual-test inventories.
- Every artifact row has a unique `artifact_id`, readable path, and read-back SHA-256; every event, field, and SP row references resolving artifact IDs; every event row maps PB event to C# method; every field row has control/`BindingField`/grid/result; every SP row has procedure/caller/branch/result; every manual test has workflow/expected and evidence IDs where applicable.
- PBL parity is claimed only with absolute PBL path/hash, runtime/version, correlated object-list receipt, unique exported window/user-object and DataWindow path/hash receipts, and a complete hash-correlated linked-DataWindow graph.
- Any direct PBL capability/list/export path follows `orca-runtime-contract.md`: the probe launches no process, one explicit version is selected, failure uses the documented fallback without implicit version retry, conversion mutates only the child `PATH`, and the exact exit code plus artifact receipts are recorded.

## C# And Designer

- Behavior-significant source identifiers are preserved where the operation requires it; supplied target names are not treated as style authority.
- Generated names use canonical `Spin<Field>`, `ymd<Field>`, `pn<Role>`, `grd<Role>`, `gvw<Role>`, `col<Role>_<FIELD>`, and `rpsSpin<Field>`.
- The screen uses one event family. The sole query method is `CallSelectProcedure` and the sole save method is `CallSaveProcedure`.
- Exactly one canonical query path and one canonical save path are used.
- Provider fallback follows target wrapper, KoneLib, DevExpress, then WinForms from declared evidence.
- Existing target wrapper/base defaults and inheritance are preserved; no comparator or framework base was substituted.
- Existing wrapper defaults, `Size`, `Location`, `Margin`, `MaximumSize`, `Visible`, and horizontal/vertical label alignment match a separately captured pre-edit Designer baseline unless an exact contract value plus registry-bound source/user evidence authorizes change.
- Lookup, search, and detail roles use the evidence-backed wrapper/repository and exact `BindingField`; no text-control substitution remains.
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
- Numeric fields follow SQL/result shape and use `RepositoryItemSpinEdit`, not GridColumn `DisplayFormat` alone.
- `EnableAppearanceEvenRow` may be enabled, but no source-unbacked even-row color is assigned.

## Stored Procedures

- The selected operation is recorded as `new_generation`, `pb_srd_generation`, `existing_sp_cleanup`, or `approved_inferred_draft`.
- When a complete PB event inventory proves `save_event_present=false`, no `_SAVE`/`_SELECT_SAVE` procedure and no `INSERT`/`UPDATE`/`DELETE`/`MERGE` exists in the candidate.
- Complete release-ready output has independently captured, readable, SHA-256-matched result/write/body evidence; schema summaries and candidate-as-source evidence do not qualify. An approved inferred draft remains pending.
- Every executable statement and structural control event consumes one canonical event. IF/ELSE, WHILE body paths, generic nested BEGIN/END, TRY/CATCH openings and closings, and transaction-control statements preserve scope and order. Only the first root-level pre-body `SET NOCOUNT ON` in a procedure envelope is wrapper ordinal `0`; transaction-following, duplicate, later, nested, branch-path, and fragment-level forms require authority and a positive ordinal. One single independently bound source artifact or one complete SHA-bound branch/composite artifact covers the entire non-wrapper stream. A composite has exact candidate `target_procedure`, complete `trace_sql`, v2 canonical `trace_sha256`, and ordered lineage equal to every correlated source SHA-256. Structural omission/reordering/scope movement, condition-only artifacts, partial/unknown/duplicate/reordered lineage, wrong hashes, trace mismatch, cross-artifact splicing, flat fingerprint pools, branch/statement swaps, arm swaps, nested-arm swaps, and per-arm reordering are rejected.
- `DESCRIPTION` is concrete. `AUTHOR` and `CREATE DATE` are absent unless exact authoritative source evidence supplies them. No metadata placeholder remains.
- Every SP parameter exists in the caller matrix or has a documented external caller.
- C# caller evidence names a strict one-part or two-part candidate `target_procedure`, and the bound artifact is globally delimiter-balanced and contains one complete `class`/`struct`/`record`, one complete ordinary method with a plausible built-in/qualified/generic/nullable/array/tuple/task-like return type, and exactly one active `dbClient` invocation. Invocation counting includes direct, conditional-access, parenthesized, null-forgiving, whitespace/comment-separated, and interpolated-string payload forms; unsupported methods also count, so a hidden second call fails. Reserved control keywords and ambiguous unsupported return-type syntax fail closed. The sole call is a complete semicolon-terminated, case-sensitive supported SP method used as a direct method-body expression or `return`. Constructors/static constructors, destructors, operators/conversions, accessors, bare fragments, top-level/local functions, lambdas, delegates, anonymous contexts, initializers, and nested expressions are rejected. Its first top-level argument is the direct SP string; every remaining top-level argument is a direct supported `new DbParameter` constructor whose value is a restricted scalar literal/identifier/member/indexer/method/cast/grouping/unary/`??` expression. Literal preprocessor conditions are evaluated; unknown-symbol regions containing caller evidence fail closed without symbol evidence. It does not claim SQL types, defaults, `OUTPUT`, or `READONLY`.
- External caller evidence is verified and includes matching evidence/artifact caller identity and strict `target_procedure`, a readable artifact path (or host-resolved URI), SHA-256, and ordered SQL types. Empty or extra identity qualifiers fail closed.
- A caller JSON/manifest, caller label, object name, or caller-supplied hash is not accepted as proof; any external caller input is read back, SHA-256-recomputed, and independently bound before use.
- Pasted SQL has an explicit `existing_procedure`, `pb_query`, or `body_fragment` role and resolves to a readable, SHA-256-matched artifact, not only a summary, inline claim, or unresolved URI.
- Existing-SP cleanup changes only whitespace/case and preserves procedure identity, every comment payload at its relative executable-token position, statements, operators, literals, terminators, and the complete ordered typed original signature, defaults, `OUTPUT`, and `READONLY`.
- Parameter defaults are parsed with SQL string awareness; `OUTPUT`/`READONLY` inside literals are not options.
- Normal SSMS `USE`/`GO`, Object comment, ANSI settings, and `GO` preamble are accepted before the metadata header.
- Internal calculations and derived dates are local variables.
- Raw search/date values cross the caller boundary through established wrappers such as evidenced `YYYYMMDD` APIs; SP-owned defaults, date derivation, and wildcards remain in the SP.
- Existing target-project clear/query/save helpers are used before generic assignments such as `DataSource = null`; no unnecessary DTO/helper abstraction is added.
- Supplied predicates, literals, comments, calculations, result order, and write behavior are preserved.
- Formatting verification and semantic-equivalence claims are separate.
- SQL generation/semantic verification and presentation formatting are separate stages with correlated receipts.
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
- After every generated C# or Designer change, `verify_migration_generated_csharp_style` or `orchestrate_pb_migration_validation` is executed against exact target paths/digests with complete `expected_control_contracts`, and its status is recorded.
- `expected_control_contracts` accounts for every selected-form member constructed in the sole class-member `InitializeComponent`, including custom wrappers/components. It is never silently omitted. An explicit empty list is accepted only with `no_control_contract_evidence.reason` and non-empty registry-bound `no_control_contract_evidence.evidence_refs`.
- Every supplied contract-level or property-level evidence ID resolves through the structured `evidence_registry`; unused, malformed, duplicate, free-form, and undeclared-property references are blocked.
- Existing Designer preservation binds a separately captured pre-edit `baseline_designer_path` and SHA-256. Source and Designer target paths are distinct, and the current Designer target is not reused as its own baseline.
- Any protected KoneLib-default override has matching exact `properties` plus source/user provenance in `property_evidence` or `evidence_refs`; a repeated property value alone is not override authority.
- Skill/reference reads and smoke checks are not counted as generated-file verifier execution.
- Per-file Designer ownership scan and any dynamic-state exception evidence are recorded.
- SP generation verifier status is recorded when SQL is generated.
- SQL formatter/verifier status is recorded separately.
- Emitted SQL has an actual final-response binding receipt with exact original/candidate/final hashes and correlated provider-selection evidence.
- The SQL verifier history is non-empty and its verification ID plus original/candidate hashes correlate with the final binding; the release's nested binding equals the exposed binding.
- Core stage order is exactly profile load, C# validation, SP validation, then final SQL binding.
- Project inclusion, project build, and manual workflow each have an independent passing receipt with observable evidence and no nonzero exit code.
- The exact target project, dependency declarations, generated-file owner, and explicit/implicit inclusion mode are bound before the build receipt.
- Designer layout-load has an independent passing receipt whenever Designer source exists.
- Database equivalence and deployment each have independent passing receipts when claimed; otherwise those claims remain absent.
- Build/syntax/manual checks and exact commands are recorded.
- Unsupported PB parity, UI fidelity, and DB equivalence claims remain blocked.
- Residual risks and next required evidence are explicit.

## User-Facing Output

Return the artifact or migration plan in the user's language. Keep internal KH routing details out of the final response unless an audit is requested.
