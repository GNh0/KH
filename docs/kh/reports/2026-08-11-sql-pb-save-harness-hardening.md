# SQL/PB SAVE Harness Hardening Release Evidence

Date: 2026-08-11
Branch: `codex-runtime`
Version: `2.9.141`

## Evidence Scope

- Live session `019f58fd` was used only to identify concrete failure boundaries. The resulting checks are generalized harness contracts, not session- or project-specific exceptions.
- SQL coverage is limited to formatting structure and preservation. PB SAVE coverage is limited to evidence-backed migration/SP generation contracts.
- Project-specific `ExecSP` selection, transaction policy, and SQL Server error 266 handling are explicitly excluded.

## Hardened Contracts

### SQL JOIN/APPLY

- `ON` and top-level continuation `AND`/`OR` tokens align to the `I` column of their own `JOIN` token (`JOIN` index + 2), including multiple JOINs with comments between predicates.
- Nested `CASE`, `BETWEEN`, and subquery boolean tokens retain their original scope and are not promoted to JOIN predicates.
- `CROSS APPLY` and `OUTER APPLY` terminate the preceding JOIN predicate boundary; they cannot satisfy a missing `ON` expression or allow a JOIN predicate to resume afterward.

### Front Door

- The exact Korean regression prompt `SP_PR300510_SAVE 관련내용을 PB TO C# 하네스에 분석해서 넣어줘.` routes to `pb-to-csharp-migration-harness` and remains structurally blocked by the strict execution gate before task execution.

### PB SAVE

- SAVE procedure generation preserves ownership by one complete, bound authority; statements or branches cannot be assembled across unrelated artifacts.
- Sibling and branch execution order, wrapper placement, nested control scope, and transaction boundaries must match the bound evidence.
- Caller parameter names and order must come from an exact matched caller. SQL type, default, `OUTPUT`, and `READONLY` metadata require independently trusted typed evidence.
- Procedure identity, artifact path, digest, caller identity, and evidence lineage must bind to the exact target procedure; mismatched, partial, duplicate, or unknown lineage fails closed.
- Comments and non-interpolated string/character literals cannot create false calls. Interpolated payloads remain conservatively visible, and literal preprocessor branches are evaluated without treating unknown branches as proof.
- Candidate payloads must be complete executable evidence, not fragments or textual lookalikes. XML/save cleanup must preserve source-backed payload shape and may not introduce unproved mappings, DML, wrappers, or normalization.
- Generated XML SAVE procedures call `SP_XML_REMOVEDOCUMENT` exactly once and unconditionally as the final executable statement of the successful `TRY` path. They do not generate a CATCH-path `IF @DOC_ID IS NOT NULL` cleanup guard or a `SET @DOC_ID = NULL` marker.
- An exception before the normal-path cleanup can retain session-scoped parser memory. This is reported as a nonblocking residual risk rather than changing the user's established procedure style.

## Review And Verification

- Adversarial review ran through repeated find-fix-retest cycles. Final review reported no P0, P1, or P2 findings.
- SQL harness: 178 tests passed.
- PB migration harness: 274 tests passed.
- Front-door regression: 264 tests passed.
- Packaging: 21 tests passed.
- Catalog: 44 checks passed.
- Compile regression: 723 tests passed.
- JSON validation: 4 files passed.
- Demos: 10 demos and 58 scenarios passed.

## Practical Gate And Residual Risk

- The practical gate returned exit code 1 only because the installed plugin cache was `2.9.139` while the source under test was `2.9.141`; this is a cache/source version mismatch, not a reported test failure.
- Residual limitation: no live SQL Server integration or target C# application integration was executed for this release evidence.
