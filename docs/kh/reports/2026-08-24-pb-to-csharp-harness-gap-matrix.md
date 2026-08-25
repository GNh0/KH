# PB-to-C# Harness Gap Matrix

- Date: 2026-08-24
- Repository: `GNh0/KH`
- Source thread: `019f58fd`
- Decision: **Historical NO-GO; final 2.9.144 independent review found no P0/P1/P2**
- Release refresh: current source for `2.9.144`; historical findings and red results below remain attributed to their original runs
- Status vocabulary: `IMPLEMENTED-NOT-FINAL`, `DOCUMENTED-NOT-RUNTIME-VERIFIED`, `OPEN-P0`, `OPEN-P1`, `OPEN-P2`, `UNVERIFIED`

## Recurring-contract coverage audit

The generated recurring-contract catalog was merged from the bounded session
scan into the real `Desktop\Jang\KH` checkout. The complete contract text and
source/test locations are in
`docs/kh/reports/2026-08-24-pb-to-csharp-recurring-contracts.md`.

Coverage was rechecked against the current target source and tests. `Enforced`
requires executable target code plus a matching current test. A partial guard or
neighboring test is `Weak`; no dedicated executable verifier/test pair is
`Missing`. These are static coverage labels, not executed-test or runtime claims.

| ID | Contract | Bounded session evidence | Current coverage | Audit basis |
|---|---|---|---|---|
| INV-01 | Exact bounded PB acquisition | `E1/L10`, `E3/L265`, `E91/L6494` | **Weak** | Strategy and preflight tests exist; complete export/read-back parity is not enforced. |
| INV-02 | Source-grounded analysis and handoff | `E458/L28105`, `E907/L56375`, `E1246/L81620` | **Weak** | Handoff/document checks exist; all PB behavior claims are not artifact-bound. |
| INV-03 | UserControl/Designer baseline inheritance | `E555/L33070`, `E794/L45979`, `E837/L49532` | **Enforced** | Baseline, inherited defaults, layout, visibility, alignment, AutoHeight, and TabIndex code/tests exist. |
| INV-04 | DataWindow/XML/Designer grid integrity | `E52/L3800`, `E56/L4075`, `E940/L58043` | **Enforced** | XML, occurrence order, result fields, columns, and repositories are executable/tested. |
| INV-05 | PB event and command parity | `E261/L17650`, `E412/L25455`, `E1305/L86030` | **Weak** | Event inventory checks exist; complete event graph and side-effect parity are not proven. |
| INV-06 | Target C# query/save/error/clear flow | `E68/L4728`, `E270/L17943`, `E938/L57912`, `E1269/L83028` | **Weak** | Several anti-patterns are blocked; exact target helper/wrapper sequence is not proven. |
| INV-07 | Project inclusion and dependency/version lock | `E228/L16514`, `E704/L41465`, `E1103/L71244` | **Weak** | Project facts/build ordering are tested; real target build evidence is absent. |
| INV-08 | SQL formatting and role-aware aliases | `E398/L24767`, `E399/L24779`, `E519/L31349`, `E946/L59241` | **Enforced** | Formatter and SQL tests cover token, alias, JOIN, projection, GROUP, and ORDER preservation. |
| INV-09 | Composite business-key display | `E243/L16985`, `E337/L21464`, `E1007/L64089`, `E1208/L79899` | **Enforced** | Raw identity and all ordered sequence components are verified/tested. |
| INV-10 | Caller parameters versus SP locals | `E266/L17809`, `E309/L19797`, `E1106/L71437`, `E1307/L86066` | **Enforced** | Caller identity, ordered parameters, locals, and exact SP binding are tested. |
| INV-11 | SAVE SP owns business validation | `E48/L3655`, `E166/L12508`, `E1051/L67756`, `E1126/L73824` | **Weak** | Required guards/ownership checks exist; complete rule-to-SAVE coverage is not proven. |
| INV-12 | Minimal typed ordered XML SAVE | `E570/L33755`, `E1057/L68113`, `E1127/L73850` | **Enforced** | Field ownership, typed payload, row states, ordered DML, and cleanup are tested. |
| INV-13 | Evidence-backed completion | `E907/L56375`, `E913/L56777`, `E1246/L81620` | **Enforced** | Independent completion stages and claim boundaries have executable tests. |
| INV-14 | PB migration routing | `E91/L6494`, `E940/L58043` | **Enforced** | Positive migration and negative adjacent-inspection routing are tested. |
| CON-01 | New control layout/binding/naming/TabIndex | `E22/L1978`, `E240/L16930`, `E612/L36564`, `E837/L49532` | **Weak** | Supplied contracts are validated; PB/comparator derivation is incomplete. |
| CON-02 | Event timing and edit state | `E271/L17985`, `E277/L18157`, `E660/L39320`, `E822/L47458` | **Enforced** | The current artifact-bound event-state verifier and integration regressions compare ordering, commands, state mutations, side effects, and timing and reject forged bindings. |
| CON-03 | SELECT branches and result-set shape | `E28/L2401`, `E68/L4728`, `E69/L4820` | **Weak** | Helper-family checks exist; authoritative PB retrieve/result comparison is absent. |
| CON-04 | Client/server defaults and derived values | `E67/L4660`, `E570/L33755`, `E1307/L86066`, `E1308/L86075` | **Enforced** | Caller/SP ownership boundaries and tests cover the supplied contract. |
| CON-05 | Row states and write sequence | `E539/L32160`, `E664/L39397`, `E1057/L68113` | **Enforced** | Row-state, XML table, payload, DML order, and cleanup checks are tested. |
| CON-06 | Stored-procedure metadata header | `E537/L32068`, `E1298/L85334`, `E1304/L85961` | **Enforced** | Target-bound metadata and author/date evidence rules are executable/tested. |
| CON-07 | Transaction/error/return/logging topology | `E960/L60437`, `E962/L60566` | **Weak** | Structural trace is tested; project-specific API/logging/return behavior is incomplete. |
| CON-08 | SQL semantic projection/GROUP/ORDER/row numbering | `E420/L26000`, `E1088/L70230`, `E1297/L84992` | **Enforced** | Source-bound statement topology and formatting tests exist; DB equivalence is separate. |
| CON-09 | Performance and tuning evidence | `E602/L36049`, `E691/L40856`, `E713/L42001`, `E716/L42036` | **Enforced** | The current claim-gated verifier and regressions require correlated before/after plans, logical reads, runtime samples, SQL hashes, and result equivalence. |
| CON-10 | Dynamic UI exceptions | `E148/L10611`, `E1150/L76161`, `E1309/L86127` | **Enforced** | Static ownership and evidence-backed dynamic exceptions are tested. |
| PRO-01 | Fabricated source behavior | `E153/L10696`, `E458/L28105`, `E1246/L81620` | **Weak** | Artifact/SQL authority is strong; general PB analysis remains partly structural. |
| PRO-02 | Runtime recreation of static Designer state | `E52/L3800`, `E54/L3897`, `E1150/L76161` | **Enforced** | Code-behind static UI/grid/repository construction is executable-rejected/tested. |
| PRO-03 | Arbitrary C# validation/defaults/parameters/helpers | `E148/L10611`, `E206/L15439`, `E266/L17809`, `E270/L17943`, `E1308/L86075` | **Weak** | Enumerated patterns are blocked; semantic invention is not fully decidable. |
| PRO-04 | Extra hidden/ignored fields and controls | `E570/L33755`, `E1106/L71437`, `E1107/L71493`, `E1208/L79899` | **Weak** | Save/grid fields are checked; whole-screen unused-field analysis is incomplete. |
| PRO-05 | Direct grid nulling/manual clearing | `E376/L23505`, `E938/L57912`, `E1269/L83028` | **Weak** | Direct reset is blocked; exact target clear-helper binding is not proven. |
| PRO-06 | Unrequested SQL structures/rewrites | `E34/L2488`, `E497/L30071`, `E1284/L84184` | **Enforced** | Generation rejects unsupported constructs and cleanup preserves authenticated source. |
| PRO-07 | Redundant XML cleanup | `E958/L60036`, `E965/L60711`, `E971/L61170`, `E972/L61180` | **Enforced** | Handle count, final cleanup, no marker/catch cleanup, and ordering are tested. |
| PRO-08 | Copied generic names/conventions | `E520/L31370`, `E521/L31390`, `E940/L58043`, `E1305/L86030` | **Weak** | Canonical names/aliases are checked; exact event/method semantics remain partial. |
| PRO-09 | Unsupported parity/completion/performance claims | `E907/L56375`, `E913/L56777`, `E923/L57086`, `E1246/L81620` | **Weak** | Structured receipts are gated; no general final-prose claim checker exists. |

Count: `18 Enforced`, `15 Weak`, `0 Missing` (`33` total). The existing GM-01
through GM-32 taxonomy below is preserved as the prior generalized gap model;
this recurring-contract audit is the current source/test coverage classification.

Current remediation is static and bounded: `pb_event_state_contract` and
`pb_performance_equivalence_contract` close the two former source/test gaps, and
the generic `csharp-designer-style-harness` now verifies exact hash-bound C# and
Designer pairs without requiring PB migration intent. It does not require a
`Form` class suffix, and stored-procedure names remain target/source-bound rather
than universally requiring a `USP_...` pattern.

External verification remains pending for real ORCA/PBL export and readback,
DevExpress Designer load, exact target `.csproj` inclusion/build/dependencies,
live DB equivalence and deployment, the actual UI workflow, non-HMAC host
authenticity, Roslyn-grade semantic proof, and measured performance of the real
3.99 GB session.

## Historical Contract Gap Matrix

The statuses in this section preserve the original adversarial-review snapshot;
they do not override the current `18/15/0` source/test classification above.

| ID | Generalized contract | Previous failure or bypass | Current status | Current evidence | Missing proof / release gate |
|---|---|---|---|---|---|
| GM-01 | Normal generation uses one packaged style profile only | Author tags, matching programs, roots, or history selected unrelated style | IMPLEMENTED-NOT-FINAL | Runtime changes report zero normal discovery and profile ID/version/hash propagation | Remove or isolate every legacy discovery API; prove zero search calls in end-to-end run |
| GM-02 | Behavior evidence cannot override style | Target C#/PB source changed naming and method families | IMPLEMENTED-NOT-FINAL | Mixed method/event families and noncanonical typed controls are rejected | Adversarial target source must not alter canonical output |
| GM-03 | Profile maintenance is a separate privileged lane | Root-only input and copied metadata produced a profile candidate | OPEN-P1 | Authorization, allowlist, SHA, provenance/custody inputs were added | Correlate partial classes, program key, artifacts, and uniqueness; reject unrelated pairs |
| GM-04 | PBL/export evidence must exist and match current bytes | Absolute path plus syntactically valid SHA was enough | OPEN-P0 | Runtime/version/object-list/hash fields exist | `exists`, bounded readback, calculated SHA, exporter receipt, requested-object correlation |
| GM-05 | Handoff rows are bound to source artifacts | Keyword prose and arbitrary structured rows passed | OPEN-P1 | `kh.pb-migration-handoff.v1` and required rows were added | Read back every referenced artifact; correlate events, fields, SP branches, and hashes |
| GM-06 | No PB SAVE/DML evidence means no generated SAVE/DML | Report/query screens gained invented SAVE code | IMPLEMENTED-NOT-FINAL | No-SAVE/no-DML validation was added | Unseen report, query, and read-only DataWindow scenarios must pass independently |
| GM-07 | Static UI belongs to Designer/layout artifacts | Code-behind contained controls, columns, bindings, and appearance | OPEN-P1 | Normal code-behind checks reject static UI | Derive role from actual companion file/path/content; reject caller-controlled `source_role` bypass |
| GM-08 | Grid binding is one end-to-end chain | Alias, table column, `FieldName`, repository, caption, and layout drifted separately | IMPLEMENTED-NOT-FINAL | Missing metadata and Spin repository checks were strengthened | Run real Designer/layout round-trip and negative mismatches for every chain element |
| GM-09 | Canonical naming is deterministic | `spn/dt/pnl/repSpin` and `Spin/ymd/pn/rpsSpin` conflicted | IMPLEMENTED-NOT-FINAL | Canonical docs/code now report `Spin`, `ymd`, `pn`, `rpsSpin` | Red smoke and any legacy names must be eliminated or compatibility-scoped |
| GM-10 | Query/save/event method family has a grounded selection | Alternative methods passed if not mixed | OPEN-P1 | Mixed families are rejected | Define one default; require explicit profile evidence for any alternative |
| GM-11 | SP input, local, XML, and output ownership is unique | C# duplicated date/default logic and SQL exposed internal variables as parameters | IMPLEMENTED-NOT-FINAL | Ownership rules were strengthened | Field-level matrix and generated SP/C# pair review on unseen programs |
| GM-12 | SQL release binds exact final SQL to verifier history | Declared formatter/verifier receipts passed without history in session audit | OPEN-P0 | PB verifier checks history correlation | Session audit must require the same invocation ID, input/output hash, verifier result, and release hash |
| GM-13 | Draft success and final completion are different contracts | Offline validator success became completion | OPEN-P0 | PB runtime added separate project/build/Designer/DB/manual stages | Align session audit with PB verifier; reject legacy completion-shaped receipts |
| GM-14 | Completion receipts require trusted provenance | `status=passed`, `verified=true` forged all stages | OPEN-P0 | Missing receipts block completion | Bind receipts to actual tool calls, target paths, current hashes, timestamps, and stage-specific outputs |
| GM-15 | Build evidence identifies exact project and output | Command name and exit code 0 were accepted | OPEN-P0 | Build stage exists | Require correlated invocation, exact project, output artifact/hash, and current-source identity |
| GM-16 | Manual QA evidence comes from an actual UI tool session | Tool name containing `browser` plus JSON passed | OPEN-P0 | Manual stage exists | Require host/tool provenance, target identity, actions, observed assertions, screenshots or equivalent artifacts |
| GM-17 | Duplicate call IDs invalidate provenance | Last call silently overwrote the first | OPEN-P1 | Bypass reproduced | Reject duplicate IDs before receipt binding |
| GM-18 | Migration routing requires intent and target linkage | PB and C# words anywhere caused heavy migration classification | OPEN-P1 | Overclassification reproduced | Require migration action plus linked PB/C# artifact or explicit migration target |
| GM-19 | Completion-claim audit supports the user's language | Korean completion prose was not detected | OPEN-P2 | Blind spot reproduced | Locale-aware semantic claim detection with low false-positive tests |
| GM-20 | Large session audit parses once with bounded memory | 3.97 GB session was repeatedly read and copied | OPEN-P0 | Helper measured at 30 full payload reads per audit | Streaming parser, one event index, bounded fields, reuse across checks, peak-memory benchmark |
| GM-21 | Artifact readers enforce limits before loading | Target source/layout/SAVE/profile files were read fully before limit checks | OPEN-P1 | No persistent leak in 500-call micro-check | File-size preflight, streaming/hash reads, explicit caps, oversize regression |
| GM-22 | Skill documentation and runtime have one contract | Docs aligned while legacy implementation labels failed privacy smoke | OPEN-P1 | JSON parse and canonical naming checks passed | Green skill smoke; no contradictory legacy labels or private/session residue |
| GM-23 | Project inclusion is independent evidence | Generated files existed but were absent from the project | IMPLEMENTED-NOT-FINAL | Project-inclusion stage was added | Real project file readback and clean build from that project |
| GM-24 | DB equivalence/deployment and manual UI are claim-specific | File generation was reported as a working migration | IMPLEMENTED-NOT-FINAL | Separate stages were added | Real DB/result equivalence, deployment, and manual workflow evidence where claimed |
| GM-25 | Behavior authority follows a scoped lattice | Target source, a named comparator, author/root discovery, and packaged style were treated as interchangeable authority | DOCUMENTED-NOT-RUNTIME-VERIFIED | The three-report integration defines current target/user-supplied artifacts first for behavior, hash-bounded comparator authority only for requested properties/behavior, packaged-only default style, and zero discovery authority | Runtime authority resolver and adversarial precedence tests |
| GM-26 | Mid-work corrections accumulate and analysis-only means zero writes | Later corrections silently displaced non-conflicting directives, analysis requests mutated files, or partial work was called complete | DOCUMENTED-NOT-RUNTIME-VERIFIED | Directive-ledger, zero-write analysis-only, and no-premature-completion rules are now explicit | Runtime write gate, accumulated-directive receipt, and interrupted/corrected-work regressions |
| GM-27 | PB event surface and Designer serializer legality are parity gates | Candidate C# omitted or invented events, or compensated for invalid Designer output with runtime static UI/factories | DOCUMENTED-NOT-RUNTIME-VERIFIED | Event inventory/subscription mapping and serializer-legal Designer ownership are now required; runtime compensation is forbidden | Structural verifier coverage plus real Designer load and event-surface regressions |
| GM-28 | Generated SQL cannot invent staging, identity, or sequencing constructs | New `#temp`, table variables, identity allocation, or sequencing logic appeared from generic SAVE patterns | DOCUMENTED-NOT-RUNTIME-VERIFIED | Exact source authority is required for each exact construct; `existing_sp_cleanup` preserves existing behavior | SQL parser/verifier rules and positive/negative construct-level regressions |
| GM-29 | Comparator reuse is structural and target-adapted | Comparator class, control, field, procedure, and event identifiers were copied stale into a different target | DOCUMENTED-NOT-RUNTIME-VERIFIED | Comparator role mapping must adapt target semantics and reject unmapped stale identifiers | Hash-bound comparator-map verifier and stale-identifier regression corpus |
| GM-30 | SAVE SP owns business validation/errors when source assigns it | C# duplicated server validation and message ownership | DOCUMENTED-NOT-RUNTIME-VERIFIED | Ownership mapping now requires C# to invoke/forward the SAVE outcome without duplicating SP-owned business rules | Paired C#/SAVE ownership verifier and unseen validation/error regressions |
| GM-31 | Project/dependency ownership and `.csproj` inclusion precede build | Generated files were built or reported complete without proving target project ownership, dependencies, or inclusion | DOCUMENTED-NOT-RUNTIME-VERIFIED | Exact target project, dependency source, and inclusion mode are mandatory pre-build evidence | Evaluated project readback, dependency resolution, inclusion, output hash, and clean-build receipts |
| GM-32 | PBL acquisition follows a deterministic PblScripter/ORCA/export ladder | Missing tools or stale exports were replaced by inferred PB behavior | DOCUMENTED-NOT-RUNTIME-VERIFIED | Explicit bounded PblScripter, then selected-version ORCA, then current read-back exports are the only rungs; absent tools plus no current exports is unresolved/blocking | Runtime ladder implementation, no-discovery checks, and rung/failure regressions |

The current integration implements GM-25 through GM-32 in the three approved English contract documents only. Runtime enforcement, verifier code, regression execution, and environment-specific proof remain open; these rows therefore do not change the NO-GO decision.

## Regression Scenario Matrix

| Scenario ID | Covers | Input pressure | Expected invariant | Current disposition |
|---|---|---|---|---|
| PBREG-001 | GM-01, GM-02 | Repository contains many author tags and similarly named programs | Normal run performs zero style discovery and uses packaged profile hash | UNVERIFIED end-to-end |
| PBREG-002 | GM-03 | Copied/missing/ambiguous authorship and unrelated partial classes | Profile candidate rejected before runtime eligibility | OPEN-P1 |
| PBREG-003 | GM-03 | Profile update omits authorization, allowlist, expected SHA, or provenance | Reject before candidate content read | Reported implemented; needs independent rerun |
| PBREG-004 | GM-06 | Report/query PB object has no save semantics | No SAVE event, SP, DML, or XML save payload | Reported implemented; needs unseen case |
| PBREG-005 | GM-07 | Runtime methods and static UI placed together but labeled Designer | Reject file split regardless of caller label | OPEN-P1 |
| PBREG-006 | GM-08 | One mismatched SELECT alias, `FieldName`, repository, caption, or layout column | Reject entire binding chain with exact mismatch | Partially covered; layout round-trip missing |
| PBREG-007 | GM-11 | Same value appears as C# parameter, SQL local, and XML field without source evidence | Reject multiple ownership | UNVERIFIED on unseen pair |
| PBREG-008 | GM-12 | SQL receipt has matching labels but no verifier history | Reject release binding | OPEN-P0 in session audit |
| PBREG-009 | GM-04 | Nonexistent PBL/export paths with matching fake SHA strings | Reject parity before graph claims | OPEN-P0 |
| PBREG-010 | GM-14, GM-15, GM-16 | Every stage supplies only `status=passed`, `verified=true` | Completion remains false | OPEN-P0 |
| PBREG-011 | GM-05 | Handoff references nonexistent or stale artifacts | Reject stale rows and identify the artifact | OPEN-P1 |
| PBREG-012 | GM-23 | Generated files are not included in the target project | Draft may pass; completion fails | Stage exists; real project unverified |
| PBREG-013 | GM-13, GM-24 | Build passes but Designer, DB, deployment, or manual stage is absent | Only the unsupported claim is blocked; no completion | Contract mismatch remains OPEN-P0 |
| PBREG-014 | GM-17 | Two different tool calls reuse one `call_id` | Reject provenance stream | OPEN-P1 |
| PBREG-015 | GM-18 | Prompt compares PB and C# but edits an unrelated C# typo | Do not require PB migration outputs | OPEN-P1 |
| PBREG-016 | GM-19 | Korean prose claims verification, build, and manual QA | Mark claims `claimed_unverified` | OPEN-P2 |
| PBREG-017 | GM-20, GM-21 | 3.97 GB / 86,127-line session plus large artifacts | One bounded parse; no repeated whole-file reads | OPEN-P0 |
| PBREG-018 | GM-09, GM-22 | Canonical docs coexist with legacy evidence labels | Skill smoke passes and runtime/docs agree | Currently red |
| PBREG-019 | GM-25 | Current target conflicts with a named comparator outside the comparator's requested, SHA-bound property scope | Current target wins for behavior; comparator contributes only the authorized mapping; packaged profile remains default style | Contract documented; runtime regression not run |
| PBREG-020 | GM-26 | Two non-conflicting corrections arrive mid-work, followed by an analysis-only review | Both corrections remain active, review performs zero writes, and completion remains false while any directive/gate is unresolved | Contract documented; runtime regression not run |
| PBREG-021 | GM-27 | PB event inventory and Designer subscriptions differ, while code-behind creates static controls through a factory | Reject event-surface mismatch and runtime compensation; require serializer-legal Designer structure | Contract documented; runtime/Designer regression not run |
| PBREG-022 | GM-28 | New SAVE SQL introduces a table variable, `#temp`, `IDENTITY`, or `ROW_NUMBER` without exact source coverage; cleanup input already contains one | Reject every invented construct; preserve the existing construct unchanged in `existing_sp_cleanup` | Contract documented; SQL verifier regression not run |
| PBREG-023 | GM-29 | A hash-bound comparator role maps to the target but copied comparator identifiers remain in C# or Designer output | Adapt the structure to target semantics and reject every stale unmapped identifier | Contract documented; structural regression not run |
| PBREG-024 | GM-30 | SAVE SP owns a duplicate check and error message while C# repeats both | Reject the C# duplication and retain one SP-owned validation/error path | Contract documented; paired-source regression not run |
| PBREG-025 | GM-31 | Generated `.cs` files exist and compile in isolation but are absent from the exact target `.csproj` or require undeclared dependencies | Block build/completion before compilation evidence is accepted | Contract documented; real-project regression not run |
| PBREG-026 | GM-32 | PblScripter and the selected ORCA runtime are absent and no current hash-bound exports exist | Return unresolved/block with no inferred event, DataWindow, or SAVE behavior | Contract documented; acquisition-ladder regression not run |

## Historical Verification Ledger

| Evidence item | Reported result | Authority | Release interpretation |
|---|---:|---|---|
| PB migration harness after implementation | `290/290` | Implementer report | Useful intermediate evidence only |
| Profile maintenance tests after implementation | `6/6` | Implementer report | Useful intermediate evidence only |
| PB/profile combined after adversarial changes/review | `295/296` | Independent reviewer | Red; supersedes earlier green for release judgment |
| Session audit full module | `301/302` | Independent reviewer | Red |
| PB-focused session audit subset | `38/38` | Independent reviewer | Narrow pass only |
| Focused forged-evidence defenses | `12/12` | Independent reviewer | Does not cover newly found bypasses |
| Earlier skill smoke | Failed on legacy evidence label | Documentation reviewer | Historical red result |
| AST parsing of modified Python files | Passed | Implementer/reviewer | Syntax evidence only |
| Real PBL export and parity | Not run | None | Missing |
| Real C# project inclusion/build | Not run | None | Missing |
| DevExpress Designer/layout load | Not run | None | Missing |
| DB equivalence/deployment | Not run | None | Missing |
| Manual UI workflow | Not run | None | Missing |
| Installed-plugin blind scenario | Not run | None | Missing |
| Stable real-corpus benchmark | Natural exit 0 in 139.576642s on 4,009,987,266 bytes; peak RSS 80.582031 MiB; source open/pass/original passes 1/1/1; valid 161,096-byte summary; zero residue | Independent real-corpus run | Accepted release evidence; <=69s stretch missed by 70.576642s and remains non-blocking |
| Final release review and aggregate | No P0/P1/P2; exact four-module aggregate 399/399 in 60.344s | Independent review and exact aggregate | Green functional release evidence |
| GM-25 through GM-32 three-report contract integration | Documentation updated; runtime regressions not run | Current scoped documentation task | Contract integration only; not green-test or runtime-enforcement evidence |
| Current three-report Markdown/reference check | Passed for the three reports, eight GM rows, and eight aligned regression rows per report | Current bounded local check | Structural documentation evidence only |
| Current packaged skill smoke | Passed; 36/36 implementation targets resolved, 13/13 privacy files checked, 0 issues | Current `python -B skills/pb_to_csharp_migration_harness/scripts/smoke_check.py` run | Green packaged skill contract evidence |

## Evidence Boundary Rules

1. Assistant prose, JSON authored by the caller, or a `verified=true` field is a claim, not evidence.
2. Hash strings prove nothing until the current artifact is read and the hash is calculated by a trusted tool invocation.
3. A command name and exit code do not identify the project, source state, output artifact, or assertions.
4. Formatter, SQL verifier, build, Designer, DB, deployment, and manual UI receipts are separate and cannot expand one another's scope.
5. Draft validation may authorize further work; it cannot authorize a completion claim.
6. Missing environmental evidence must be reported as `unverified`, not silently converted to a pass or a generic failure.
7. Earlier green test counts do not override later adversarial failures.
8. Exact current target and user-supplied artifacts govern behavior; comparator authority is limited to its explicitly requested, SHA-bound scope, and discovery output is never authority.
9. Analysis-only work has a zero-write contract, and non-conflicting corrections remain cumulative until explicitly superseded.
10. Project inclusion, dependency ownership, event-surface parity, and Designer serializer legality are prerequisites rather than build-time or runtime compensations.
11. Existing-procedure cleanup preserves constructs and behavior; new generation needs exact source authority for staging, identity, sequencing, validation, and error ownership.
12. Missing PBL tools and missing current exports produce an unresolved/blocking result, never inferred parity.

## Files Reported as Changed

The following inventory comes from completed worker reports. It is not reconciled with Git because Git access was intentionally excluded from this reporting task.

The current integration is separately limited to the three report files named by the user. No runtime, test, JSON contract, checklist, ORCA reference, manifest, or project file is claimed changed by this integration.

### Runtime and tests

- `src/skills/pb_to_csharp_migration.py`
- `src/skills/pb_to_csharp_profile_maintenance.py`
- `src/orchestration/session_skill_audit.py`
- `tests/test_pb_to_csharp_migration_harness.py`
- `tests/test_pb_to_csharp_profile_maintenance.py`
- `tests/test_session_skill_audit.py`

### Skill contract documentation

- `skills/pb_to_csharp_migration_harness/SKILL.md`
- `skills/pb_to_csharp_migration_harness/references/usage.md`
- `skills/pb_to_csharp_migration_harness/references/packaged-style-contract.md`
- `skills/pb_to_csharp_migration_harness/references/packaged-style-contract.json`
- `skills/pb_to_csharp_migration_harness/references/profile-update-workflow.md`
- `skills/pb_to_csharp_migration_harness/references/datawindow-layout-mapping.md`
- `skills/pb_to_csharp_migration_harness/references/sql-formatting-bridge.md`
- `skills/pb_to_csharp_migration_harness/references/migration-output-checklist.md`
- `skills/pb_to_csharp_migration_harness/examples/minimal-workflow.md`

### Audit reports

- `docs/kh/reports/2026-08-24-thread-019f58fd-pb-to-csharp-postmortem.md`
- `docs/kh/reports/2026-08-24-pb-to-csharp-harness-gap-matrix.md`
- `docs/kh/reports/2026-08-24-pb-to-csharp-recurring-contracts.md`

## Full Environment Certification Exit Criteria

The following historical list governs full environment-backed PB migration
certification, not the 2.9.144 package source release. External items gate only
the claims they support. The real-session timing item is retained as a deferred
performance stretch under the current release policy.

1. Every `OPEN-P0` row has a code-level fix and an adversarial regression that fails before and passes after.
2. PB/profile, session audit, skill smoke, and repository-wide relevant suites are green in one current run.
3. PBL/export, handoff, C#/Designer, SQL, build, DB, and manual claims are all bound to current artifacts and trusted invocations.
4. The stable 4,009,987,266-byte source completes within the deferred <=69-second stretch target.
5. A separate worker consumes the handoff and completes an unseen PB-to-C# scenario without style discovery or invented behavior.
6. Installed-plugin testing confirms automatic routing without explicit skill naming and without unrelated PB/C# overclassification.
7. GM-25 through GM-32 have code-level enforcement and adversarial regressions, not documentation-only statements.
8. Event-surface parity and Designer serializer legality are verified against current source and a real Designer load without code-behind static UI compensation.
9. Exact target `.csproj` inclusion and dependency ownership are proven before the exact project build receipt is accepted.
10. The PblScripter/ORCA/export ladder returns a deterministic unresolved/blocking result when neither tools nor current exports are available.

Current status: **the package source is functionally release-ready at 399/399
with no P0/P1/P2 finding. The stable 4,009,987,266-byte source completed
naturally in 139.576642 seconds at 80.582031 MiB peak RSS with one original
source pass, a valid 161,096-byte summary, and zero residue. The <=69-second
stretch remains unmet by 70.576642 seconds and non-blocking. Environment-specific
PB, Designer, build, DB, and UI claims remain unverified until their own
receipts exist**.
