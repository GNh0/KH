# Thread 019f58fd PB-to-C# Postmortem

- Date: 2026-08-24
- Repository: `GNh0/KH`
- Audited thread: `019f58fd`
- Scope: PB-to-C# migration routing, analysis handoff, C#/Designer generation, SQL bridge, evidence audit, completion claims, and runtime cost
- Current decision: **NO-GO**
- Release refresh: current packaged source for `2.9.144`; the audited thread remains historical negative evidence

## Executive Summary

The thread repeatedly failed for the same structural reason: the harness treated observed project source as both behavior evidence and style authority. That allowed an agent to rediscover style from ambiguous files, invent missing PB behavior, and then accept self-declared receipts as proof of completion.

At the time of the audit, the patch direction was correct: use one packaged style profile, separate profile maintenance from normal generation, require structured PB handoff, prohibit ungrounded SAVE/DML, and split draft validation from final completion. Independent adversarial review still found spoofable evidence, including nonexistent PBL/export claims, self-declared stage receipts, inconsistent SQL-history correlation, and repeated whole-session reads. Those failures remain valid findings for the audited thread.

Earlier implementation results reported `296/296` targeted PB/profile tests passing. Later independent review observed `295/296` PB/profile and `301/302` session-audit tests passing, plus a red skill smoke check. These are not final integration results. Release readiness remains false.

The original three-report integration recorded those findings as documentation contracts only. Current `2.9.144` source now packages executable event-state, performance-equivalence, project/PBL preflight, and generic C#/Designer verification contracts with matching tests. This raises current static recurring-contract coverage to `18 Enforced / 15 Weak / 0 Missing`; it does not retroactively validate the thread or convert external evidence into a pass.

## Evidence Base

This report uses the bounded findings already produced from the thread and current checkout. It does not copy the raw transcript.

- The raw session was measured at approximately **3.99 GB** and **86,127 JSONL lines**.
- One forensic pass extracted the recurring failure timeline with streaming reads after broad loading was stopped.
- Separate reviewers audited PB/C#/SQL contracts, session evidence provenance, documentation alignment, and adversarial bypasses.
- Current code references in this report are reviewer-observed locations, not a final line-stable release map.
- Git, `.git`, manifests, versions, source, tests, and skill documentation were not modified while producing this report.

## Merged recurring-contract audit

The complete 33-contract catalog and per-contract source/test references are in
`docs/kh/reports/2026-08-24-pb-to-csharp-recurring-contracts.md`. The real target
checkout was inspected before assigning coverage labels. `Enforced` is used only
where executable target code and a matching current test both exist. Partial
guards are `Weak`; no dedicated executable verifier/test pair is `Missing`.
These labels are static coverage, not executed-test or runtime evidence.

The baseline rule is explicit: an existing target `UserControl` and pre-edit
Designer are the authority for inherited type, container, size, location, margin,
visibility, alignment, AutoHeight, and other defaults. A changed Designer cannot
serve as its own baseline. New controls require exact PB/layout/comparator
evidence. This is implemented by the target baseline and Designer validators and
covered by the baseline, wrapper, layout, alignment, AutoHeight, visibility, and
TabIndex tests cited in the recurring report.

| Contract set | Bounded session line/event references | Current target coverage |
|---|---|---|
| INV-01 to INV-04 | `E1/L10`, `E3/L265`, `E91/L6494`, `E458/L28105`, `E907/L56375`, `E1246/L81620`, `E555/L33070`, `E794/L45979`, `E837/L49532`, `E52/L3800`, `E56/L4075`, `E940/L58043` | `2 Enforced`, `2 Weak` |
| INV-05 to INV-08 | `E261/L17650`, `E412/L25455`, `E1305/L86030`, `E68/L4728`, `E270/L17943`, `E938/L57912`, `E1269/L83028`, `E228/L16514`, `E704/L41465`, `E1103/L71244`, `E398/L24767`, `E399/L24779`, `E519/L31349`, `E946/L59241` | `1 Enforced`, `3 Weak` |
| INV-09 to INV-14 | `E243/L16985`, `E337/L21464`, `E1007/L64089`, `E1208/L79899`, `E266/L17809`, `E309/L19797`, `E1106/L71437`, `E1307/L86066`, `E48/L3655`, `E166/L12508`, `E1051/L67756`, `E1126/L73824`, `E570/L33755`, `E1057/L68113`, `E1127/L73850`, `E913/L56777`, `E91/L6494`, `E940/L58043` | `5 Enforced`, `1 Weak` |
| CON-01 to CON-05 | `E22/L1978`, `E240/L16930`, `E612/L36564`, `E837/L49532`, `E271/L17985`, `E277/L18157`, `E660/L39320`, `E822/L47458`, `E28/L2401`, `E68/L4728`, `E69/L4820`, `E67/L4660`, `E570/L33755`, `E1307/L86066`, `E1308/L86075`, `E539/L32160`, `E664/L39397`, `E1057/L68113` | `3 Enforced`, `2 Weak` |
| CON-06 to CON-10 | `E537/L32068`, `E1298/L85334`, `E1304/L85961`, `E960/L60437`, `E962/L60566`, `E420/L26000`, `E1088/L70230`, `E1297/L84992`, `E602/L36049`, `E691/L40856`, `E713/L42001`, `E716/L42036`, `E148/L10611`, `E1150/L76161`, `E1309/L86127` | `4 Enforced`, `1 Weak` |
| PRO-01 to PRO-05 | `E153/L10696`, `E458/L28105`, `E1246/L81620`, `E52/L3800`, `E54/L3897`, `E1150/L76161`, `E148/L10611`, `E206/L15439`, `E266/L17809`, `E270/L17943`, `E1308/L86075`, `E570/L33755`, `E1106/L71437`, `E1107/L71493`, `E1208/L79899`, `E376/L23505`, `E938/L57912`, `E1269/L83028` | `1 Enforced`, `4 Weak` |
| PRO-06 to PRO-09 | `E34/L2488`, `E497/L30071`, `E1284/L84184`, `E958/L60036`, `E965/L60711`, `E971/L61170`, `E972/L61180`, `E520/L31370`, `E521/L31390`, `E940/L58043`, `E1305/L86030`, `E907/L56375`, `E913/L56777`, `E923/L57086`, `E1246/L81620` | `2 Enforced`, `2 Weak` |

Total current recurring-contract coverage: **18 Enforced, 15 Weak, 0 Missing**.
The two upgrades are backed by the packaged event-state and performance-
equivalence verifier/test pairs. This is static source/test coverage and does
not claim that real PB, Designer, project, DB, UI, or large-session work ran.

## Recurring Failure Taxonomy

| ID | Recurring failure | Root cause | User impact |
|---|---|---|---|
| FT-01 | Wrong C# style source selected | Author tags, matching program names, repository roots, or history were searched during normal generation | Output copied an unrelated contributor's patterns and ignored the requested fixed style |
| FT-02 | PB behavior was invented | Missing PB evidence was treated as freedom to infer events, SAVE branches, report behavior, or UI convenience logic | Generated screens and procedures changed behavior rather than migrating it |
| FT-03 | Analysis-to-development handoff was too shallow | Prose and keyword presence were accepted instead of artifact-bound rows for events, fields, SPs, and ownership | A second worker could not reconstruct the first worker's reasoning safely |
| FT-04 | Static UI configuration was placed in code-behind | Designer ownership was advisory and caller-controlled `source_role` could bypass it | DevExpress layout drifted from the expected Designer-managed form |
| FT-05 | Grid and binding chains were incomplete | Field aliases, `DataTable` columns, `FieldName`, repository editors, captions, result sets, and layout columns were validated separately or only when metadata was supplied | Screens compiled but displayed wrong, blank, or uneditable columns |
| FT-06 | Naming and method families drifted | Multiple control prefixes and query/save method families were allowed without a grounded selection rule | Generated code mixed incompatible local conventions |
| FT-07 | SP parameter, local variable, and XML ownership drifted | UI-derived values, procedure-local values, XML payload fields, and output parameters were not assigned one authoritative owner | Procedures gained unnecessary parameters and C# duplicated database logic |
| FT-08 | SQL formatting and alias layout drifted | Formatting verification was not consistently bound to the exact final SQL and verifier history | JOIN `ON`/`AND`, aliases, projection layout, and key-sequence display columns repeatedly violated the contract |
| FT-09 | SAVE/XML transaction flow changed | API names were interpreted without tracing transaction ownership, output propagation, and cleanup semantics | Generated SAVE logic risked duplicate messages, lost outputs, or cleanup/session leaks |
| FT-10 | Project inclusion and environment checks were skipped | File generation was treated as completion | Files could exist outside the project, fail to build, or fail at runtime |
| FT-11 | Completion was claimed from self-authored evidence | `status=passed`, `verified=true`, command names, or assistant prose were accepted without trusted tool correlation | The user received completion claims without build, DB, Designer, or manual proof |
| FT-12 | PB-to-C# routing was over-broad | Mere co-occurrence of PB and C# terms triggered migration requirements | Unrelated C# edits incurred heavy PB preflight and false P0 findings |
| FT-13 | Session audit was slow and memory-heavy | The same JSONL was loaded with `read_text().splitlines()` through repeated helper calls | Large tasks became slow and caused high transient memory use that looked like a leak |

## Failure Progression in the Audited Thread

The recurring sequence was consistent across the thread:

1. A PB screen, DataWindow, report, or stored procedure was named.
2. The agent searched broadly for a stylistic comparator or trusted an ambiguous author marker.
3. Missing behavior was filled with generic WinForms/DevExpress or SQL patterns.
4. Static controls, bindings, event flow, and SP contracts diverged from the PB source.
5. A local or synthetic receipt marked the stage as passed.
6. Build, Designer load, DB equivalence, project inclusion, or manual workflow evidence was absent.
7. A later user review exposed the same mismatch, causing another narrow patch rather than removing the underlying bypass.

This explains why scenario-specific fixes did not hold: the routing, authority, and evidence boundaries were still permissive.

## Old Bypasses Confirmed by Independent Review

| Bypass | Evidence | Consequence |
|---|---|---|
| Author/root/matching-program rediscovery | Legacy public APIs remained in `src/skills/pb_to_csharp_migration.py` during the initial audit | Normal generation could select unrelated source |
| Nonexistent PBL/export receipt | Path and SHA syntax were checked near `pb_to_csharp_migration.py:2031`; parity was granted near `:2145` without file readback | Fake artifacts produced `parity_ready=true` |
| Self-declared completion receipt | Stage evidence near `pb_to_csharp_migration.py:14685` accepted `status=passed` and `verified=true` | All completion stages could be forged |
| Unbound structured handoff | Handoff validation near `pb_to_csharp_migration.py:3280` checked strings but not current artifact contents or hashes | Invented events/fields/SP mappings passed |
| `source_role=designer` bypass | Role branching near `pb_to_csharp_migration.py:4879` and companion checks near `:4906` trusted caller labels | Runtime methods and static UI could coexist in one file |
| SQL receipt without verifier history | Session audit near `session_skill_audit.py:3578` accepted binding/release shape, while PB verifier near `pb_to_csharp_migration.py:14728` required history correlation | Session audit and PB verifier disagreed |
| Synthetic build/manual QA | Command-name and exit-code checks near `session_skill_audit.py:3740`; tool-name substring check near `:3759` | Fabricated stage JSON could satisfy completion |
| Duplicate tool call IDs | `pending[call_id]` replacement near `session_skill_audit.py:6970` | A later call silently replaced the original provenance |
| Keyword-only migration trigger | Co-occurrence logic near `session_skill_audit.py:2894` | Unrelated C# work was classified as PB migration |
| Korean completion-claim blind spot | English-only phrases near `session_skill_audit.py:3867` | Korean false-completion prose was not flagged |

## Required Generalized Contract

The reusable contract must not depend on private names, private paths, or a particular program key.

1. **Style authority:** normal generation uses exactly one packaged, versioned, hashed style profile. Target source can describe behavior and available APIs but cannot override style.
2. **Profile maintenance:** profile updates run only through a separate maintenance workflow with explicit authorization, exact artifact allowlist, expected SHA-256, provenance/custody evidence, class/program-key correlation, and uniqueness review.
3. **PB evidence:** PBL and exported objects must exist, be read back, match the recorded hash, identify the exporter/runtime, and correlate the requested object list to the exported graph.
4. **Handoff:** `kh.pb-migration-handoff.v1` must bind every event, field, control, DataWindow column, SP branch, parameter/local/XML owner, and unresolved decision to current artifact hashes.
5. **No invention:** no PB SAVE/DML evidence means no generated SAVE/DML. Unsupported behavior is reported as unresolved, not inferred.
6. **Designer ownership:** static controls, layout, repository items, grid columns, appearance, captions, field bindings, and `TabIndex` belong to Designer/layout artifacts. Runtime-only changes require explicit behavioral evidence.
7. **Binding integrity:** PB field -> SELECT alias -> result table -> `FieldName` -> editor/repository -> visible caption/layout must be verified as one chain.
8. **SQL bridge:** the exact final SQL hash must correlate to the formatter invocation, verifier history, result, and release receipt. A declared verifier name is not evidence.
9. **Completion gates:** draft validation, project inclusion, compilation, Designer/layout load, DB equivalence/deployment, and manual workflow are independent stages with trusted receipts.
10. **Runtime cost:** session JSONL must be parsed once with bounded streaming/indexing. Large source artifacts must be size-checked before full reads.
11. **Scoped authority lattice:** the exact current target and user-supplied artifacts govern behavior first. An explicitly named comparator is authoritative only for the exact requested properties or behavior and exact SHA-256-bound scope. The packaged profile remains the sole default style family. Author, root, or similar-program discovery is never authority.
12. **Directive accumulation:** non-conflicting mid-work corrections remain cumulative; only an explicit conflict supersedes the affected directive. Analysis-only requests perform zero writes, and no partial milestone may be reported as completion.
13. **Event and Designer parity:** the complete PB event surface, C# handlers, and Designer subscriptions must correlate. Designer output must be serializer-legal; runtime static UI construction or factories cannot compensate for missing or invalid Designer structure.
14. **SQL construct authority:** new generation may not introduce `#temp`, table variables, synthetic identity allocation, or sequencing constructs without exact source evidence authorizing the exact construct. `existing_sp_cleanup` preserves existing constructs and behavior.
15. **Comparator adaptation:** a named comparator supplies only a structural role map within its approved scope. Generated target output must adapt target semantics and reject stale comparator class, control, field, event, and procedure identifiers.
16. **SAVE validation ownership:** when authoritative evidence assigns business validation or error ownership to the SAVE procedure, C# invokes and forwards that outcome without duplicating the rule or message.
17. **Project ownership before build:** the exact target project, dependency declarations, generated-file ownership, and `.csproj` inclusion mode must be proven before build or completion evidence is accepted.
18. **Deterministic PBL acquisition:** use only an explicitly configured PblScripter rung, then the one selected ORCA runtime, then current read-back/hash-bound exports. If the tools are absent or unusable and no current exports exist, the behavior remains unresolved and generation blocks rather than inferring.

## Historical Documentation Integration and Current Packaged Status

The original correction set integrated the authority lattice, cumulative-correction and analysis-only rules, event/Designer parity boundary, SQL construct authority, comparator adaptation, SAVE validation ownership, project/dependency inclusion gate, and deterministic PBL acquisition ladder into the approved English harness documents and aligned report matrices.

At that checkpoint their status was **documented, not runtime-verified**. In current source, the corrections are packaged contracts rather than report-only advice: event-state and performance-equivalence validators are integrated into the migration preflight, project/dependency and PBL acquisition contracts have executable tests, and the PB-independent `csharp-designer-style-harness` verifies exact hash-bound source/Designer pairs. The generic C# contract does not require a `Form` suffix, and stored-procedure naming remains source/target-bound rather than a universal PB `USP_...` rule.

The current packaged contracts still do not establish real ORCA/PBL export and
readback, DevExpress Designer load, exact target `.csproj` inclusion/build and
dependencies, live DB equivalence/deployment, the actual UI workflow, non-HMAC
host authenticity, or Roslyn-grade semantic proof. The stable
4,009,987,266-byte source subsequently completed naturally with exit code 0 in
139.576642 seconds at 80.582031 MiB peak RSS. Source open/pass/original passes
were 1/1/1, the valid summary was 161,096 bytes, and temporary residue was zero.
The <=69-second objective remains unmet by 70.576642 seconds and non-blocking.

## Implementation Status

### Historical implementation state recorded by the audit

- Normal generation author/root discovery was changed toward fail-closed behavior.
- Profile maintenance was split into a separate module with authorization, allowlist, hash, and provenance inputs.
- Packaged profile ID/version/hash propagation was added.
- Mixed method/event families and noncanonical typed-control names were blocked.
- Structured handoff, no-SAVE/no-DML, SQL verifier-history binding, KoneLib fallback, and independent completion stages were added or strengthened.
- Session audit began separating assistant claims from runtime evidence and splitting C#, Designer, SP, SQL, build, DB, and manual outputs.
- Skill documentation was rewritten toward the packaged-profile contract.

### Historical open findings at the time of review

- PBL/export parity does not yet prove artifact existence and current content hash.
- Completion-stage receipts remain self-assertable in the PB verifier.
- Session audit and PB verifier use incompatible completion semantics.
- SQL history is not required consistently by session audit.
- Build and manual QA provenance remains spoofable.
- Handoff rows are not fully correlated to read-back artifacts.
- Caller-controlled Designer role can bypass source separation.
- Maintenance accepts unrelated partial-class pairs under some crafted inputs.
- Alternative method-family selection remains underconstrained.
- Duplicate call IDs, Korean completion claims, and PB/C# keyword overclassification remain open.
- Session parsing still performs repeated full-file reads.
- Earlier skill smoke was red because a legacy evidence label remained in implementation. The current three-report smoke is also red for a different reason: its ordinary-runtime-doc policy rejects the required `PblScripter` and `ORCA` ladder wording in all three edited report documents.
- The scoped authority lattice is documented but has no runtime precedence resolver or adversarial comparator-scope test in this integration.
- Correction accumulation and analysis-only zero-write behavior are documented but not enforced by a current directive/write gate in this integration.
- Event-surface parity, Designer serializer legality, SQL construct authority, comparator stale-identifier rejection, and SAVE validation ownership have no newly executed runtime regressions.
- Exact `.csproj`/dependency pre-build enforcement and the PblScripter/ORCA/export fallback ladder remain runtime and environment integration work.

## Regression Scenario Catalog

| ID | Scenario | Required result |
|---|---|---|
| PBREG-001 | Normal migration with repositories containing author tags and similarly named programs | Zero style-discovery searches; packaged profile only |
| PBREG-002 | Copied, missing, or ambiguous authorship metadata | Reject as profile evidence |
| PBREG-003 | Profile update without authorization, exact allowlist, hash, and provenance | Fail before reading candidate content |
| PBREG-004 | PB report/query with no SAVE behavior | No SAVE SP, DML, or save event generated |
| PBREG-005 | Static DevExpress controls supplied in code-behind or mislabeled as Designer | Reject by file identity/content, not caller role |
| PBREG-006 | PB field and grid column with mismatched alias, `FieldName`, repository, or caption | Reject the entire binding chain |
| PBREG-007 | Procedure value ambiguously duplicated across C# parameter, SQL local, and XML | Require one owner and reject duplication |
| PBREG-008 | SQL formatter receipt without exact final hash and verifier history | Reject release binding |
| PBREG-009 | PBL/export paths do not exist or hashes do not match readback | Reject parity |
| PBREG-010 | Stage receipts contain only `status=passed`, `verified=true` | Reject as untrusted claims |
| PBREG-011 | Structured handoff references nonexistent or stale artifacts | Reject and report exact stale row |
| PBREG-012 | Generated files are absent from the target project | Draft may pass; completion must fail |
| PBREG-013 | Build passes but Designer load, DB, or manual workflow is missing | Completion must fail with stage-specific gaps |
| PBREG-014 | Duplicate tool `call_id` with different calls | Reject provenance stream |
| PBREG-015 | PB and C# are merely compared while an unrelated C# typo is edited | Do not route as migration |
| PBREG-016 | Korean prose claims validation/build/manual completion without receipts | Flag as `claimed_unverified` |
| PBREG-017 | 3.99 GB JSONL session | Single bounded parse; no repeated whole-file copies |
| PBREG-018 | Canonical docs coexist with legacy evidence labels | Skill smoke and runtime/docs agreement are required; any red smoke blocks the affected packaging claim |
| PBREG-019 | Current target conflicts with a named comparator outside the exact requested, SHA-bound property scope | Current target controls behavior; comparator is bounded; packaged profile remains default style; discovery is ignored |
| PBREG-020 | Two cumulative corrections followed by an analysis-only request and an unresolved gate | Preserve both corrections, perform zero writes, and withhold completion |
| PBREG-021 | PB events/Designer subscriptions differ and code-behind creates static controls or columns through a factory | Reject both event-surface mismatch and runtime Designer compensation |
| PBREG-022 | New SQL invents `#temp`, a table variable, identity allocation, or sequencing while cleanup input already contains such a construct | Reject invented generation and preserve existing cleanup behavior exactly |
| PBREG-023 | Comparator structure is applicable but copied identifiers do not belong to the target | Adapt roles to target semantics and reject stale identifiers |
| PBREG-024 | SAVE SP owns duplicate validation/error text and C# repeats it | Reject duplicate C# business validation and keep SAVE ownership singular |
| PBREG-025 | Generated files compile alone but are absent from the exact target `.csproj` or need undeclared dependencies | Reject build/completion evidence before project inclusion and dependency ownership pass |
| PBREG-026 | PblScripter and selected ORCA capability are unavailable and no current exports exist | Return unresolved/block without inferred behavior or parity |

## Test and Evidence Boundary

Current source contains dedicated tests for `pb_event_state_contract`,
`pb_performance_equivalence_contract`, migration preflight integration, and the
PB-independent C#/Designer style contract. The `2.9.144` release pass also
observed `9/9` focused packaging/docs tests green, including the 45-skill
catalog, synchronized manifests, `codex-runtime` marketplace ref, README checks,
generic C#/Designer packaging, and front-door packet version. Those checks are
packaging/static evidence only; the event/performance/runtime suites were not
rerun by this two-report completion.

The following results are useful but **not final release evidence**:

- Implementer report: PB migration harness `290/290`, profile maintenance `6/6`, AST parse passed.
- Later independent report: PB/profile `295/296`; one documentation-alignment expectation failed.
- Later independent report: session audit `301/302`; one severity expectation failed.
- Focused adversarial checks: `12/12`; PB session-audit subset `38/38`.
- Skill smoke: failed because a legacy `author-tagged` evidence label remained in implementation.

For the original checkpoint, the later red results superseded the earlier all-green report. No final full-suite, clean-environment, installed-plugin, or end-to-end migration result was established by that audit.

No green tests were claimed for the original three-report integration. Its Markdown/reference checks and skill smoke remain historical evidence and cannot prove current external execution.

Original bounded verification observed:

- Three-report Markdown/reference check: passed; fenced blocks and table shapes were consistent, required support references existed, and the reports contained the eight aligned GM/regression additions plus the 33-contract catalog.
- Packaged skill smoke: failed with six `discovery_term_in_normal_runtime_doc` issues, one `PblScripter` and one `ORCA` issue in each edited contract document. All 27 listed implementation targets resolved, but the overall smoke status remained failed.
- No unit, integration, Designer, build, DB, deployment, or manual UI regression suite was run or claimed green for this documentation-only integration.

## Token and Memory Impact

- The audited 3.99 GB session is contract-sensitive evidence and should remain passthrough on disk; it should not be loaded wholesale into model context.
- A reviewer measured `_session_payload_events()` being invoked **30 times** for one small audit. The implementation uses `read_text().splitlines()`, causing repeated full reads and large temporary string/list allocations.
- PB artifact paths also include read-before-limit patterns. A 500-call micro-check did not show a persistent leak (about 72 KB retained, 363 KB peak), so the stronger current finding is **transient amplification and repeated reread**, not a proven permanent leak.
- `.git` was not needed for this report and is not identified as the direct cause by this audit.
- Required fix: one bounded streaming parse, indexed event reuse, early size limits, and file references instead of raw transcript duplication.

## Changed Files Reported by Workers

This list is reconstructed from worker reports, not from Git status or diff:

- `src/skills/pb_to_csharp_migration.py`
- `src/skills/pb_to_csharp_profile_maintenance.py`
- `src/orchestration/session_skill_audit.py`
- `tests/test_pb_to_csharp_migration_harness.py`
- `tests/test_pb_to_csharp_profile_maintenance.py`
- `tests/test_session_skill_audit.py`
- `skills/pb_to_csharp_migration_harness/SKILL.md`
- `skills/pb_to_csharp_migration_harness/references/usage.md`
- `skills/pb_to_csharp_migration_harness/references/packaged-style-contract.md`
- `skills/pb_to_csharp_migration_harness/references/packaged-style-contract.json`
- `skills/pb_to_csharp_migration_harness/references/profile-update-workflow.md`
- `skills/pb_to_csharp_migration_harness/references/datawindow-layout-mapping.md`
- `skills/pb_to_csharp_migration_harness/references/sql-formatting-bridge.md`
- `skills/pb_to_csharp_migration_harness/references/migration-output-checklist.md`
- `skills/pb_to_csharp_migration_harness/examples/minimal-workflow.md`
- `docs/kh/reports/2026-08-24-thread-019f58fd-pb-to-csharp-postmortem.md`
- `docs/kh/reports/2026-08-24-pb-to-csharp-harness-gap-matrix.md`
- `docs/kh/reports/2026-08-24-pb-to-csharp-recurring-contracts.md`

## Current External Residuals and Historical Release Requirements

Full environment-backed completion remains blocked pending real ORCA/PBL readback,
DevExpress Designer load, exact target `.csproj`/build/dependency evidence, live
DB equivalence/deployment, actual UI workflow evidence, non-HMAC host
authenticity, and Roslyn-grade semantic proof. The stable real-corpus run
completed naturally in 139.576642 seconds at 80.582031 MiB peak RSS with one
original source pass, a valid 161,096-byte summary, and zero residue. The
<=69-second target was missed by 70.576642 seconds and remains deferred and
non-blocking for the package source release. The following broader list
preserves the original audit's release requirements; it is not a claim that
every listed code-level gap remains absent from current source:

- Current diff/changed-file reconciliation and stale legacy API review.
- Green skill smoke and green PB/profile/session-audit regression suites.
- Real PBL export using an identified runtime, with object-list and hash readback.
- End-to-end analysis handoff consumed by a separate implementation worker.
- Target project inclusion and clean C# build.
- DevExpress Designer/layout load and structural inspection.
- Exact SQL formatter/verifier history bound to final SQL hashes.
- DB result equivalence and deployment evidence where DB claims are made.
- Manual UI workflow evidence for the migrated behavior.
- Completed audit of the 3.99 GB session within the deferred <=69-second target.
- Installed-plugin end-to-end scenario proving the fixed profile is selected without explicit user naming.
- Runtime and adversarial regression enforcement for GM-25 through GM-32, including cumulative directives and analysis-only zero-write behavior.
- Current-source event-surface comparison and real Designer serializer/load evidence with no runtime static UI compensation.
- New-generation SQL construct checks plus cleanup-preservation cases for temporary staging, identity, and sequencing.
- Hash-bound structural comparator adaptation and stale-identifier rejection.
- Paired C#/SAVE verification proving one owner for business validation and errors.
- Exact target dependency and `.csproj` inclusion proof before a correlated project build.
- Deterministic PblScripter/ORCA/export ladder evidence, including the no-tool/no-export unresolved path.

Until the current external residuals are observed, the packaged corrections may
be reported as **implemented and statically covered**, but not externally
verified, migration-complete, or release-ready for a real target workflow.
