# PB-to-C# Recurring Contracts

Date: 2026-08-24
Session: `019f58fd`
Scope: user corrections repeated at least twice in the bounded session scan
Release status: refreshed from current source for `2.9.144`; historical session findings remain evidence of the audited run

## Reference model

The source session is identified by the short thread label `019f58fd`; the
private rollout path is intentionally omitted.

`E<n>/L<n>` means the nth direct human `event_msg.user_message` record and its
1-based physical JSONL line. Each reference is bounded to one JSONL record. The
scanner used a fixed byte ceiling of `3,975,375,930` and did not load the file as
a whole.

An invariant applies unless the user explicitly overrides it. A conditional
contract must be resolved from the named PB object, DataWindow, current C# target,
stored procedure, project, or user-supplied comparator. A prohibited pattern is
default-deny unless exact source evidence or an explicit user instruction permits
it. Example business identifiers in the session are evidence instances, not
universal table or column rules.

## Invariant contracts

### INV-01 Exact and bounded PB acquisition

Acquire the exact named library and object. Prefer already exported PB text when
it is current; otherwise list/probe with the matching PB runtime and use
PblScripter, then direct ORCA when appropriate. Export the named object first,
then only referenced DataWindows, to an external evidence directory while
preserving encoding. Do not substitute a similar PBL, backup, or sibling object.
Evidence: `E1/L10`, `E3/L265`, `E91/L6494`.

### INV-02 Source-grounded analysis and implementation handoff

The PB analysis must identify object relationships, event flow, retrieve/update
behavior, hidden or defaulted fields, DataWindow mappings, caller/SP boundaries,
and unresolved evidence. The handoff must distinguish confirmed behavior from
inference and must be sufficient for a separate implementer without hidden chat
context. Missing source must be reported, never filled with an imagined function,
query, save path, or field. Evidence: `E458/L28105`, `E907/L56375`,
`E1246/L81620`.

### INV-03 Exact UserControl and Designer baseline inheritance

When an existing target `UserControl` or pre-edit Designer supplies type,
container, size, location, margin, visibility, alignment, AutoHeight, or other
defaults, preserve those exact values. A change requires an exact property-level
contract and source or user evidence. The current edited Designer cannot serve as
its own baseline. Evidence: `E555/L33070`, `E794/L45979`, `E837/L49532`.

### INV-04 DataWindow to XML to Designer grid integrity

Derive grid columns from the authoritative DataWindow/result contract, preserve
raw occurrence order, produce verifier-compatible View XML, and bind the loaded
state to explicit Designer columns. Grid/control names, `FieldName`, captions,
`VisibleIndex`, repositories, `ColumnEdit`, formats, and result fields must agree
across PB, XML, Designer, C#, and SELECT output. Evidence: `E52/L3800`,
`E56/L4075`, `E940/L58043`.

### INV-05 PB event and command parity

Produce an explicit PB-event-to-C#-method map and preserve required command/event
wiring. Standard screen commands remain wired when the target family uses them,
even if a handler is intentionally empty. Names must follow the actual target
program and local method family, not generic copied names. Evidence:
`E261/L17650`, `E412/L25455`, `E1305/L86030`.

### INV-06 Target C# query, save, error, and clear flow

Use the target screen's established query/save method family, adjacent
`DbParameter` style, error wrapper, focused-row helper, master-to-table helper,
and container-level clear helper. Keep one coherent query path and one coherent
save path; do not create a second helper for the same operation. Evidence:
`E68/L4728`, `E270/L17943`, `E938/L57912`, `E1269/L83028`.

### INV-07 Target project inclusion and dependency/version lock

Every added C#, Designer, resource, or report artifact must be included by the
exact target project in its native project-file style. Reuse the target project's
existing wrapper, KoneLib, DevExpress, framework, and assembly versions; do not
upgrade, retarget, or assume the latest version. Evidence: `E228/L16514`,
`E704/L41465`, `E1103/L71244`.

### INV-08 SQL formatting preservation and role-aware aliases

Formatting must preserve tokens, literals, comments, projection order, predicates,
grouping, and ordering. Alias roles are source-bound: the main source uses the
main alias, repeated role families use ordered sibling aliases, and table aliases
do not gain `AS` when the target style omits it. Each JOIN's `ON` and line-leading
continuation `AND`/`OR` align to that JOIN's contract. Evidence: `E398/L24767`,
`E399/L24779`, `E519/L31349`, `E946/L59241`.

### INV-09 Complete composite business-key display

When source evidence defines a visible business identifier as a base key plus
ordered sequence components, retain every raw key field for identity and emit a
separate display field containing all components in source order. Do not omit the
last sequence or create raw fields merely to hide them at runtime. Evidence:
`E243/L16985`, `E337/L21464`, `E1007/L64089`, `E1208/L79899`.

### INV-10 Caller parameters versus procedure locals

The exact caller matrix bounds the procedure signature and parameter order.
Values supplied by the caller are parameters; helper dates, counters, normalized
values, and calculations used only inside the procedure are local declarations.
No non-caller parameter, invented selector, literal business default, or automatic
normalization block is allowed without exact source evidence. Evidence:
`E266/L17809`, `E309/L19797`, `E1106/L71437`, `E1307/L86066`.

### INV-11 SAVE procedure owns authoritative business validation

Required-field, eligibility, chronology, duplicate, and row-specific business
validation belongs in the designated SAVE procedure when that is the established
application contract. Validation must occur before target DML and return an
actionable error. C# may retain only source-proven UI interaction checks.
Evidence: `E48/L3655`, `E166/L12508`, `E1051/L67756`, `E1126/L73824`.

### INV-12 Minimal, typed, ordered XML SAVE contract

Classify each field as editable payload, technical key, fixed, defaulted,
server-derived, or unused. Serialize only the exact source-owned payload with the
correct row states and types. Keep INSERT/UPDATE projections ordered and correlated
to the C# payload; derive fixed, identity, user, organization, and key values on
the server when the source assigns ownership there. Evidence: `E570/L33755`,
`E1057/L68113`, `E1127/L73850`.

### INV-13 Evidence-backed completion

Completion requires the exact target artifacts, source/caller/SP bindings,
structural verifier results, project/build evidence where applicable, and an
explicit runtime/manual/DB status. Static generation or a harness read must not be
reported as PB parity, UI fidelity, live DB equivalence, or completed behavior.
Evidence: `E907/L56375`, `E913/L56777`, `E1246/L81620`.

### INV-14 PB migration routing

Requests whose operative scope is PB/PBL/DataWindow to C#/Designer/SELECT/SAVE
migration must route to the PB-to-C# migration harness. A non-migration SQL or
report inspection must not be routed there solely because C# or a grid is
mentioned. Evidence: `E91/L6494`, `E940/L58043`.

## Conditional and source-dependent contracts

### CON-01 New control layout, binding, naming, and TabIndex

For controls not present in a baseline, derive containment, wrapper type,
`BindingField`, label pairing, bounds, editor role, and TabIndex from the exact
PB layout and named target comparator. Validate input order per container; never
turn one observed size, field name, or TabIndex sequence into a universal value.
Evidence: `E22/L1978`, `E240/L16930`, `E612/L36564`, `E837/L49532`.

### CON-02 Event timing and edit-state behavior

Whether behavior runs on Load, Search, edit mode, Save, a tab change, button click,
or `CellValueChanged` is determined by PB behavior and the target command model.
Immediate persistence must not replace staged edit-and-save behavior unless the
source proves it. Evidence: `E271/L17985`, `E277/L18157`, `E660/L39320`,
`E822/L47458`.

### CON-03 SELECT branches and result-set shape

The number and meaning of `SelectType` branches, result tables, list/detail panel
mapping, and focused-row refresh parameters come from the exact PB/C# comparator.
Do not add a separate detail-list branch or query helper when the target uses one
list/detail path, and do not collapse genuinely distinct source operations.
Evidence: `E28/L2401`, `E68/L4728`, `E69/L4820`.

### CON-04 Client/server ownership of defaults and derived values

Decide where defaults, status values, dates, users, keys, wildcards, and calculated
values are produced from the source contract. Prefer raw target-wrapper values at
the caller boundary and server derivation when the target SP owns it; retain a
client-side assignment only when PB/C# behavior proves it. Evidence: `E67/L4660`,
`E570/L33755`, `E1307/L86066`, `E1308/L86075`.

### CON-05 Row-state mapping and write sequence

Added, Modified, Deleted, and selected-row behavior, XML table names, master/detail
payload count, and DML order are operation-specific. Preserve the exact source
mapping and do not serialize all states or all rows by convenience. Evidence:
`E539/L32160`, `E664/L39397`, `E1057/L68113`.

### CON-06 Stored-procedure metadata header

Preserve the exact target header when authoritative source supplies it. A concrete
description must match the target program/purpose. Author and create date are
included only when exact source or user evidence supplies them; they must not be
invented, dropped during cleanup, or copied from another program. Evidence:
`E537/L32068`, `E1298/L85334`, `E1304/L85961`.

### CON-07 Transaction, error, return, and logging topology

Use the exact target write API and source-backed transaction/error/logging shape.
Preserve TRY/CATCH, transaction boundaries, return/output behavior, and error
propagation as one ordered topology. A test wrapper's rollback behavior is not a
universal production-SP rule. Evidence: `E960/L60437`, `E962/L60566`.

### CON-08 SQL semantic projection, GROUP, ORDER, and row numbering

Formatting is invariant, but selected fields, joins, GROUP keys, final ordering,
window ordering, and row-number purpose are semantic and must follow the exact PB
query/result contract. Do not use a display sort as a row-number key or rewrite a
function as joins solely because another query did. Evidence: `E420/L26000`,
`E1088/L70230`, `E1297/L84992`.

### CON-09 Performance and tuning

Choose direct joins, derived tables, TVFs, correlated lookups, optimizer hints,
or recompilation only after preserving result equivalence and measuring the exact
workload with execution plans, logical reads, and runtime. A structural preference
or intuition is not performance evidence. Evidence: `E602/L36049`, `E691/L40856`,
`E713/L42001`, `E716/L42036`.

### CON-10 Dynamic UI exceptions

Static UI belongs to the Designer by default. A runtime property assignment is
allowed only when a source-backed state transition requires it and evidence names
the control, property, trigger, reason, and targeted test. Prefer a supported
Designer/DevExpress format rule over a row event when the behavior is equivalent.
Evidence: `E148/L10611`, `E1150/L76161`, `E1309/L86127`.

## Prohibited patterns

### PRO-01 Fabricated source behavior

Do not invent PB queries, functions, save operations, fields, validations, or
business behavior when the named artifact is missing or says otherwise. Mark the
item blocked or inferred. Evidence: `E153/L10696`, `E458/L28105`,
`E1246/L81620`.

### PRO-02 Runtime recreation of static Designer state

Do not build fixed grid columns, repositories, visibility/order loops, editor
assignments, static layout, or control factories in code-behind when Designer owns
them. Evidence: `E52/L3800`, `E54/L3897`, `E1150/L76161`.

### PRO-03 Arbitrary C# validation, defaults, parameters, and parallel helpers

Do not add source-unproven C# business validation, date/default shaping, wildcard
logic, extra query/save parameters, or duplicate query/save helpers. Evidence:
`E148/L10611`, `E206/L15439`, `E266/L17809`, `E270/L17943`, `E1308/L86075`.

### PRO-04 Extra fields, controls, or parameters that are later hidden or ignored

Do not create dummy UI controls for fixed/server fields, serialize unused columns,
request filters the operation does not use, or add result columns only to hide them
at runtime. Omit them from the relevant contract at the source. Evidence:
`E570/L33755`, `E1106/L71437`, `E1107/L71493`, `E1208/L79899`.

### PRO-05 Direct grid nulling and manual child-by-child clearing

Do not set grid `DataSource` to null or clear every child individually when the
target project has a container-aware clear helper. Evidence: `E376/L23505`,
`E938/L57912`, `E1269/L83028`.

### PRO-06 Unrequested intermediate SQL structures or broad rewrites

Do not introduce temporary/intermediate tables, CTEs, MERGE, NOT EXISTS, or broad
query rewrites by default. Use them only when exact source or explicit approved
semantic/performance evidence requires them. Evidence: `E34/L2488`,
`E497/L30071`, `E1284/L84184`.

### PRO-07 Redundant or speculative XML cleanup

Do not append a null marker after XML-handle removal, duplicate cleanup in CATCH,
guard normal cleanup with a nullable-handle test, or silently return before required
payload cleanup/DML. For generated XML SAVE flow, use the one source-backed final
normal-path cleanup contract. Evidence: `E958/L60036`, `E965/L60711`,
`E971/L61170`, `E972/L61180`.

### PRO-08 Copied generic naming or unrelated project conventions

Do not import generic event names, wrong-project methods, unrelated grid/worktype
names, or ad hoc SQL alias families. Preserve the supplied target identifiers and
role relationships. Evidence: `E520/L31370`, `E521/L31390`, `E940/L58043`,
`E1305/L86030`.

### PRO-09 Unsupported parity, completion, or performance claims

Do not claim the screen is complete, PB-equivalent, live-DB verified, or faster
from generated files, static tests, a code review, or a complex-looking rewrite.
State the exact unverified boundary and required runtime evidence. Evidence:
`E907/L56375`, `E913/L56777`, `E923/L57086`, `E1246/L81620`.

## Current target coverage audit

The real target checkout was inspected at the `GNh0/KH` repository root.
`Enforced` requires both executable target code and a matching current test. A
partial guard, a prose requirement, or a test that checks only a neighboring
property is `Weak`. `Missing` means no dedicated executable verifier and test
pair was found for the contract. These labels describe static source/test
coverage; no test execution or runtime/DB claim is implied.

| ID | Status | Current executable evidence | Current test evidence | Basis |
|---|---|---|---|---|
| INV-01 | Weak | `src/skills/pb_to_csharp_migration.py:2821-2940` | `tests/test_pb_to_csharp_migration_harness.py:2619-2935`; `tests/test_pb_migration_preflight.py:337-510` | Provider planning and tool identity are tested, but no complete PBL/export executor and read-back receipt gate proves acquisition. |
| INV-02 | Weak | `src/skills/pb_to_csharp_migration.py:4823-5425` | `tests/test_pb_to_csharp_migration_harness.py:5139-5359,11104-11116` | Handoff rows and document shape are checked, but all PB behavior claims are not artifact-bound. |
| INV-03 | Enforced | `src/skills/pb_to_csharp_migration.py:3361-3803,6388-7147,8900-9714` | `tests/test_pb_to_csharp_migration_harness.py:4003-4154`; `tests/test_pb_designer_ui_contract.py:464-540`; `tests/test_pb_designer_ui_contract_integration.py:221-230` | Separate baseline/hash, UserControl surface, inherited defaults, layout, visibility, alignment, AutoHeight, and TabIndex checks have negative tests. |
| INV-04 | Enforced | `src/skills/pb_to_csharp_migration.py:5460-6138,9233-9714` | `tests/test_pb_to_csharp_migration_harness.py:3112-3332,5719-5809,6018-6135` | DataWindow order, XML serializer values, Designer columns, result fields, and repositories are executable and tested. |
| INV-05 | Weak | `src/skills/pb_to_csharp_migration.py:18009-18198` | `tests/test_pb_event_save_contract.py:189-210`; `tests/test_pb_event_preflight_integration.py:286-327` | Event inventory and merge checks exist, but complete PB event graph, C# subscriptions, command timing, and side effects are not fully compared. |
| INV-06 | Weak | `src/skills/pb_to_csharp_migration.py:4560-4675,9714-9878` | `tests/test_pb_to_csharp_migration_harness.py:5421-5493,5602-5677` | Several duplicate-helper, shaping, and direct-reset patterns are blocked, but exact target wrapper and clear/refresh sequence are not proven. |
| INV-07 | Weak | `src/skills/pb_to_csharp_migration.py:3048-3361,17908-17972` | `tests/test_pb_migration_preflight.py:252-332,345-389`; `tests/test_pb_to_csharp_migration_harness.py:11995-12264` | Project/dependency facts and build ordering are modeled and tested, but no real target build receipt is bound here. |
| INV-08 | Enforced | `src/skills/sql_formatting_style.py:236-477,987-1055,3253-3448,4144-4252,4724-4860` | `tests/test_sql_formatting_style_harness.py:58-263,457-505,4656-5261` | Token, alias-role, JOIN-relative predicate, projection, GROUP, and ORDER preservation have executable tests. |
| INV-09 | Enforced | `src/skills/pb_to_csharp_migration.py:3966-4304` | `tests/test_pb_to_csharp_migration_harness.py:1194-1304` | Raw identity fields, all ordered sequence components, and display alias order are verified. |
| INV-10 | Enforced | `src/skills/pb_to_csharp_migration.py:10885-11134,13606-13735,15519-16759` | `tests/test_pb_to_csharp_migration_harness.py:7795-8179,9746-10532` | Caller identity, ordered direct parameters, local helper separation, and exact procedure binding are fail-closed and tested. |
| INV-11 | Weak | `src/skills/pb_to_csharp_migration.py:14981-15519,18009-18198` | `tests/test_pb_event_save_contract.py:325-352`; `tests/test_pb_to_csharp_migration_harness.py:6391-6414` | Required guards and duplicate-validation ownership checks exist, but no general proof covers every business rule and designated SAVE branch. |
| INV-12 | Enforced | `src/skills/pb_to_csharp_migration.py:13859-14981` | `tests/test_pb_to_csharp_migration_harness.py:6414-7375` | Typed field ownership, exact payload, row state, ordered DML, and one-final cleanup are executable and tested. |
| INV-13 | Enforced | `src/skills/pb_to_csharp_migration.py:17395-18274` | `tests/test_pb_to_csharp_migration_harness.py:11436-11666` | Independent completion stages and claim boundaries are executable and tested, while runtime/DB status remains explicitly unclaimed. |
| INV-14 | Enforced | `src/orchestration/request_classifier.py:2549-2555,2720-2753,3324` | `tests/test_pb_to_csharp_migration_harness.py:11743-11756`; `tests/test_kh_front_door.py:2180-2180` | Positive migration and negative adjacent inspection routing have executable coverage. |
| CON-01 | Weak | `src/skills/pb_to_csharp_migration.py:4304-4483,6388-9714` | `tests/test_pb_to_csharp_migration_harness.py:3715-4210,6289-6328` | Supplied layout/control contracts are validated, but PB/comparator evidence does not derive every new-control semantic. |
| CON-02 | Enforced | `src/skills/pb_event_state_contract.py:1-320`; `src/skills/pb_to_csharp_migration.py:18152-18420` | `tests/test_pb_event_preflight_integration.py:253-405` | Artifact-bound PB/C# graphs now compare event order, commands, preconditions, state mutations, calls, side effects, and timing; forged hashes and missing claimed graphs are rejected. |
| CON-03 | Weak | `src/skills/pb_to_csharp_migration.py:4560-4675,9714-9878` | `tests/test_pb_to_csharp_migration_harness.py:5421-5493` | Helper-family anti-patterns are blocked, but authoritative PB retrieve/result-set branch comparison is absent. |
| CON-04 | Enforced | `src/skills/pb_to_csharp_migration.py:14522-14680,15519-16759` | `tests/test_pb_to_csharp_migration_harness.py:5602-5707,7795-8179,6414-6785` | Client/server ownership, defaults, locals, fixed fields, and derived values have executable boundary checks and tests. |
| CON-05 | Enforced | `src/skills/pb_to_csharp_migration.py:14680-14981` | `tests/test_pb_to_csharp_migration_harness.py:7001-7034,7222-7337` | Row states, XML table/payload mapping, DML order, and cleanup topology are tested. |
| CON-06 | Enforced | `src/skills/pb_to_csharp_migration.py:15519-16759` | `tests/test_pb_to_csharp_migration_harness.py:8086-8111,10763-10791` | Target-bound metadata and source-backed author/date rules have executable tests. |
| CON-07 | Weak | `src/skills/pb_to_csharp_migration.py:11361-12105,15519-17299` | `tests/test_pb_to_csharp_migration_harness.py:9168-9746,8220-8290` | Structural trace and cleanup are tested, but project-specific API, SQL error, logging, and return behavior are not fully integrated. |
| CON-08 | Enforced | `src/skills/pb_to_csharp_migration.py:11361-12105,15519-17299` | `tests/test_pb_to_csharp_migration_harness.py:9168-9257`; `tests/test_sql_formatting_style_harness.py:4656-5261` | Source-bound statement topology and formatting preservation have executable tests; DB result equivalence remains separate. |
| CON-09 | Enforced | `src/skills/pb_performance_equivalence_contract.py:1-280`; `src/skills/pb_to_csharp_migration.py:18328-18420` | `tests/test_pb_performance_equivalence_contract.py:60-118`; `tests/test_pb_event_preflight_integration.py:308-419` | Claimed performance/equivalence now requires distinct correlated before/after receipts with bound SQL bytes, plans, logical reads, runtime samples, and equal result schema/rows/values. |
| CON-10 | Enforced | `src/skills/pb_to_csharp_migration.py:6636-6723,7008-7147` | `tests/test_pb_to_csharp_migration_harness.py:1575-1756,4294-4388` | Static UI ownership and evidence-backed dynamic exceptions are executable and tested. |
| PRO-01 | Weak | `src/skills/pb_to_csharp_migration.py:4823-5425,12159-12956` | `tests/test_pb_to_csharp_migration_harness.py:5139-5359,8338-8495` | Artifact and SQL authority checks are strong, but general PB analysis statements remain partly content/structure based. |
| PRO-02 | Enforced | `src/skills/pb_to_csharp_migration.py:6723-7008,7206-7800` | `tests/test_pb_to_csharp_migration_harness.py:1575-1756,4755-4901`; `tests/test_pb_event_save_contract.py:287-319` | Static controls, grids, repositories, layout, and serializer ownership are rejected in code-behind with tests. |
| PRO-03 | Weak | `src/skills/pb_to_csharp_migration.py:7800-7890,12217-12749,15519-16759` | `tests/test_pb_to_csharp_migration_harness.py:5421-5707,7795-8179` | Enumerated anti-patterns are blocked, but semantic invention and every duplicate helper cannot be detected. |
| PRO-04 | Weak | `src/skills/pb_to_csharp_migration.py:12217-12749,6931-6990` | `tests/test_pb_to_csharp_migration_harness.py:5531-5531,6260-6785` | Save/grid fields are checked, but whole-screen unused/hidden field analysis is incomplete. |
| PRO-05 | Weak | `src/skills/pb_to_csharp_migration.py:7800-7890` | `tests/test_pb_to_csharp_migration_harness.py:5662-5677` | Direct grid nulling is blocked, but exact target clear-helper binding and all manual clearing variants are not proven. |
| PRO-06 | Enforced | `src/skills/pb_to_csharp_migration.py:15519-16759` | `tests/test_pb_to_csharp_migration_harness.py:2036-2083,8220-8290,12589-12620` | New unsupported SQL constructs are rejected and authenticated existing-SP cleanup preserves source constructs. |
| PRO-07 | Enforced | `src/skills/pb_to_csharp_migration.py:14808-14981` | `tests/test_pb_to_csharp_migration_harness.py:7051-7337` | Handle count, final normal cleanup, no marker, no catch cleanup, and DML ordering are tested. |
| PRO-08 | Weak | `src/skills/pb_to_csharp_migration.py:9714-9878` | `tests/test_pb_to_csharp_migration_harness.py:10977-11084,2850-2850` | Canonical naming and SQL alias roles are checked, but exact event/method semantics and wrong-project identifiers remain partial. |
| PRO-09 | Weak | `src/skills/pb_to_csharp_migration.py:17667-18274` | `tests/test_pb_to_csharp_migration_harness.py:11436-11666` | Structured completion receipts are gated, but no general final-prose checker proves all parity/performance claims. |

## Count and interpretation

- `18 Enforced`
- `15 Weak`
- `0 Missing`
- Total: `33` recurring contracts

The count is based on the real target source/tests above, not on generated
coverage labels. It is static coverage only: the two former `Missing` contracts
are now executable and tested, but their tests do not prove a real migrated
application or production environment.

External verification remains pending for real ORCA/PBL export and readback,
DevExpress Designer load, exact target `.csproj` inclusion/build/dependencies,
live DB equivalence and deployment, the actual UI workflow, non-HMAC host
authenticity, and Roslyn-grade semantic proof. The stable 4,009,987,266-byte
source completed naturally with exit code 0 in 139.576642 seconds at
80.582031 MiB peak RSS. Source open/pass/original passes were 1/1/1, the valid
summary was 161,096 bytes, and temporary residue was zero. The <=69-second
stretch remains unmet by 70.576642 seconds and non-blocking. None of those
boundaries is implied by `18 Enforced`.
