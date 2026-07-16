---
name: sql-formatting-style-harness
description: Use when SQL/T-SQL formatting or a separately requested scalar-function refactor needs deterministic preservation, style, alias-plan, and evidence gates.
---

# SQL Formatting Style Harness

## KH Entry Contract

- Start non-trivial work through `always-on-front-door` unless the current turn was classified as light/direct.
- Use this harness only after routing selects SQL formatting or a separately requested scalar-function refactor.
- Provider selection, catalog listing, and `SKILL.md` reads are inspection only.
- Report this harness as applied only when an actual `verify_sql_formatting_style(...)` call is correlated to its structured `HarnessResult` and the exact final SQL hash.
- Require `alias_role_plan_validation`; legacy `alias_checks`, flat `alias_status`, and assistant prose cannot satisfy verifier binding.

## Purpose

Use this harness after selecting the host-local `sql-formatting` contract or the packaged fallback. The reviewer/LLM decides business roles and evaluates source authority. Python produces deterministic evidence only: it lexes SQL, checks integrity, compares the complete token stream, validates a declared alias plan, and validates structured refactor evidence. It does not infer roles or database equivalence.

## Workflow

1. Preserve the exact original. Pass `bytes` or `Path` for strict UTF-8 decoding and a raw hash; plain `str` is reported as `encoding_unverified`.
2. Select one style contract and record its path and SHA-256. Prefer the host-local skill when present; otherwise use `references/style-contract.md` as a standalone fallback.
3. Declare `operation="formatting"` or `operation="refactor"`.
4. For formatting, preserve every token except whitespace, safe case normalization, and substitutions from a complete verified alias plan. Every scalar function remains present.
5. Before changing aliases, create a complete per-scope role plan from concrete source/reviewer evidence.
6. For a scalar-function-to-join request, inspect the actual function definition through DB/MCP/project source when available. Supply `scalar_function_refactor`; never infer behavior from a function or table name.
7. Run `verify_sql_formatting_style(...)` or the module CLI against the exact pair. Skill selection or file reads are not verifier evidence.

## Independent Gates

| Metadata field | Key states | Meaning |
| --- | --- | --- |
| `input_integrity.status` | `valid`, `source_invalid` | Lexer and encoding preflight for the original. |
| `formatting_preservation.status` | `verified`, `changed`, `not_evaluated` | Complete ordered token-stream comparison. |
| `style_lint.status` | `passed`, `blocked` | Presentation-only contract checks. |
| `alias_role_plan_validation.status` | `not_needed`, `required`, `verified`, `conflict` | Complete per-scope alias evidence. |
| `semantic_refactor_evidence.scalar_function_refactor.status` | `not_requested`, `blocked`, `not_proven`, `mechanically_valid`, `verified` | Separate scalar refactor state; only an authenticated `verified` result is release ready. |
| `semantic_checks.status` | `not_proven`, `proven` | `proven` requires an independently authenticated runtime comparison bound to the exact contract. |
| `release_readiness.status` | `ready`, `pending`, `blocked` | Top-level completion gate. Refactors remain pending until semantic execution is proven and authenticated. |

## Alias Plan

- No alias change: state is `not_needed`.
- Alias change without a complete plan: block.
- In every parsed scope, reject declaration aliases `A1`, `A2`, and later numbered `A` aliases even when source and candidate aliases are unchanged. Numbered non-main families such as `B1`/`B2` remain valid.
- Every changed scope requires exactly one first `main` role containing exactly one source; all-support and multi-source main plans block.
- The one main source is `A`. Generated `A1`, `A2`, and later main aliases are invalid.
- Each subsequent distinct business-role family advances sequentially through `B`, `C`, `D`, and so on.
- A singleton non-main family uses its letter without a suffix. Multiple siblings in one non-main family use suffixes from the first member, for example `B1`, `B2`; the next distinct family is `C`.
- Family grouping comes from structured `reviewer_approved_business_role` evidence, not table identity, repetition, or source order alone. Each evidence object must name a controlled reviewer artifact URI using `review`, `spec`, `ticket`, or `design`, set `reviewer_approved=true`, and exactly cover the declared role names. The compatibility form is limited to `review://<review-id>/<declared-role-names>-roles`.
- Every changed scope must be present. Every declaration and changed reference must be covered. Cross-scope members, skipped role letters, missing aliases, and vague/empty basis references block.
- Scope-aware binding applies to nested/correlated queries and to `UPDATE ... FROM`, joined `DELETE`, and `MERGE`; an outer rename never owns a reference shadowed by an inner declaration.

## Scalar Refactor Boundary

Formatting always retains scalar calls. A separate conversion may proceed only when structured evidence identifies an authoritative function definition, proves a pure deterministic lookup, records exact source table/keys/filters/return/null behavior, proves zero-or-one cardinality and unmatched-row behavior, and explains why the join is preferable. Calculation, aggregation, security filtering, dynamic behavior, ambiguity, or unavailable source blocks conversion.

Complete structured evidence remains `not_proven`. A DB/result-comparison artifact correlated to both original and formatted SHA-256 values records `external_correlation=provenance_correlated`; Python validates completeness and correlation only and does not upgrade semantic status. Caller-supplied or otherwise unauthenticated evidence may reach `status=mechanically_valid` with `release_readiness.status=pending`, but it must return `success=false` and a non-zero exit code. Only a runtime execution receipt independently validated outside caller-supplied metadata may set both semantic proof and execution authentication needed for release readiness.

The authenticated path uses the Python API's host-supplied `runtime_receipt_authenticator(payload, signature)` callback. The signed receipt must bind the original/formatted SQL hashes, authoritative function-definition hash, computed equivalence-contract hash, comparison artifact, database identity, execution timestamp, and a positive comparison count. The callback is a host trust boundary and must never be constructed from fields inside `scalar_function_refactor`.

## INSERT Layout Contract

For mappings with eight or more items, canonical non-comment expression text of at most 72 characters remains horizontally grouped. Expressions of 73 or more characters may use vertical fallback. At most one short singleton line is allowed as a row remainder; additional short singleton mappings block. The exact thresholds and measurement name are emitted as `style_lint.insert_select_layout_contract`.

## Query Layout Contract

`JOIN` layout is source-authoritative. The verifier does not require eight spaces before `JOIN` or a fixed offset for `ON`/`AND`; derived-table indentation is preserved rather than inferred from generated output. For new SQL only, one query indentation level below `FROM` is fallback authoring guidance, with same-block `ON`/`AND` terms aligned.

Query-level `GROUP BY` and `ORDER BY` lists use a 100-column preferred width and 120-column hard ceiling. Short simple lists stay inline. Long lists split only at top-level commas and pack compactly across continuation rows; complex items stay atomic. Direction and collation modifiers stay attached. Window `ORDER BY` is excluded by query-depth detection. The exact policy is emitted as `style_lint.query_list_layout_contract`.

## Progressive Disclosure

- Read `references/usage.md` for API/evidence shapes.
- Read `references/style-contract.md` when using the packaged fallback.
- Use `examples/minimal-workflow.md` for acceptance scenarios.
- Run `python scripts/smoke_check.py` for package wiring.
- Run `python scripts/demo.py --output-dir <tmp>` for executable contract cases.
- Use `scripts/powerbuilder_sql_probe.py` only for a bounded approved export; never write into the source tree.

## Completion Rules

- Block on source/output corruption, formatting token changes, style errors, or incomplete alias plans. Keep mechanically valid but unproven refactors pending closed.
- Formatting verification may complete with `semantic_checks.status=not_proven` because no refactor release claim is made.
- Refactor verification may complete only when `semantic_checks.status=proven` and `execution_authentication=authenticated`; correlation alone never completes it.
- Do not use a refactor reason to waive unrelated token changes.
- Do not claim semantic equivalence from deterministic Python checks.
- Do not claim this harness ran until a `HarnessResult` was produced.

## Required outputs

- Correlated verifier call/output evidence, using call IDs when available.
- `success`, `status`, `exit_code`, and a non-empty `verification_id`.
- `release_readiness.status=ready|pending|blocked`; pending refactors must have `success=false` and non-zero `exit_code`.
- Valid `original_sha256`, `formatted_sha256`, and `style_contract_sha256` values.
- `mechanical_checks.status=passed` for an accepted formatting result.
- Structured `alias_role_plan_validation.status=not_needed|verified`; `required` and `conflict` block acceptance.
- Exact final SQL whose UTF-8 SHA-256 equals `formatted_sha256`.
- `token_optimizer_status=passthrough` with the quality-preserving reason.

## Common mistakes

- Do not substitute `alias_checks`, `alias_status`, marker text, or a copied JSON sample for `alias_role_plan_validation`.
- Do not accept verifier output without a preceding correlated verifier call.
- Do not bind a hash to unfenced, multiple, or otherwise non-extractable final SQL.
- Do not infer alias roles from table names, repeated source names, or remembered project policy.
- Do not remove scalar functions during formatting or claim database equivalence from lexer checks.
- Do not treat caller-created comparison metadata, matching hashes, or `external_correlation=provenance_correlated` as an authenticated runtime execution receipt.
- Do not introduce project-specific lookup tables or scalar functions as universal examples or policy.

## UAF implementation targets

- `src.skills.sql_formatting_style.verify_sql_formatting_style`
- `src.skills.sql_formatting_style.resolve_style_contract_source`
- `src.contracts.HarnessResult`
- `skills/sql_formatting_style_harness/SKILL.md`
