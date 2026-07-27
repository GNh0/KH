# SQL and PB Release Hardening Checkpoint

Finalized: 2026-07-27

## Objective

Harden KH UAF SQL formatting and PB-to-C# migration contracts so final SQL, source lineage, caller evidence, and session receipts fail closed when required evidence is missing, stale, malformed, or inconsistent.

## Release State

- Worktree: `C:\Users\KONEIT\Desktop\Jang\KH\.worktrees\sol-sql-harness-redesign`
- Source branch: `codex-runtime-sol-audit`
- Integration target: `origin/codex-runtime`
- Base commit: `0f1872981d3c3f8760993b7712b0922238b8d646`
- Release version: `2.9.136`
- Token Optimizer: `passthrough` for SQL, C#, session, and receipt evidence; only command-output presentation was compacted.

## SQL Hardening

- The provider path, provider-selection receipt, CLI inputs, raw file hashes, verifier result, final binding, and final release are correlated through one strict schema.
- Final release status is `passed`; its nested binding status is `bound`.
- Exact scalar types are required. Boolean or string values cannot satisfy integer exit codes, fence counts, IDs, or hashes.
- Text shell output accepts only canonical `Exit code: 0`.
- Session evidence requires an executed `const r = await tools.shell_command(...); text(r);` result flow rather than a command-shaped source fragment.
- Extra schema keys, duplicate JSON keys, split provider paths, stale raw hashes, malformed exits, and repeated receipt IDs are rejected.
- A later SQL request or correction invalidates earlier verification evidence and requires a new provider and binder run.

## PB-to-C# Hardening

- Existing-procedure cleanup preserves exact target procedure identity and complete executable structure.
- Canonical trace v2 records procedure-root, nested block, IF/ELSE, WHILE, TRY/CATCH, and transaction scope/order.
- Composite authority requires exact target procedure, full canonical trace SQL/hash, and complete ordered source lineage. Subset, stale, duplicate, reordered, or incomplete authority is rejected.
- Only the first root-level procedure-envelope `SET NOCOUNT ON` may be treated as wrapper ordinal zero.
- Active `dbClient` calls are counted across whitespace, comments, conditional access, parentheses, null-forgiving syntax, verbatim identifiers, and executable interpolation expressions.
- Caller evidence must be one complete ordinary C# method with a plausible legal return type. Constructors, operators, accessors, local functions, fragments, `var`, and invalid `void` compositions are rejected.
- PB evidence stores both `sql_final_response_release.status == "passed"` and `sql_final_response_binding.status == "bound"` without conflating the two contracts.

## Independent Review Findings Closed

Independent reviewers found and the implementation closed:

- incomplete SQL release schemas and scalar coercion;
- command text that looked executed but was not tied to returned shell output;
- duplicate-key and replayable receipt evidence;
- incomplete PB control-flow traces and subset source authority;
- hidden second `dbClient` calls;
- constructors, fragments, and malformed return types treated as ordinary methods;
- PB/SQL integration status collision between `passed` and `bound`.

No P0 was reported. All bounded P1 findings above were converted into regressions and fixed. Review was intentionally stopped after these concrete contract findings rather than expanded indefinitely.

## Final Verification

- PB/SQL/session/front-door integration: `700/700` passed.
- Entire repository test suite: `1,519/1,519` passed.
- Packaged skill catalog: `44/44` valid, zero issues.
- Wiring quality gate: `44/44` valid, lowest score `10.0`, zero wiring gaps. This is packaging evidence, not a substitute for behavioral review.
- PB, SQL provider, SQL style, and front-door smoke checks: all exited `0` with `success: true`.
- PB, SQL provider, SQL style, and front-door runnable demos: all exited `0`; success and blocked paths produced validated artifacts.
- No-write Python compile: 9 affected modules passed; packaged PB JSON contract parsed.
- `git diff --check`: passed after LF normalization.

## Residual Limits

- The PB C# and T-SQL analyzers are conservative lexical/static verifiers, not Roslyn or a live SQL Server execution engine. Unsupported constructs fail closed.
- Local HMAC receipts prove local integrity and correlation only. They do not prove external Codex host authenticity; `external_authenticity` remains `unverified`.
- Live DevExpress behavior and database semantics still require project-specific build, UI, and DB validation when those runtimes are available.
