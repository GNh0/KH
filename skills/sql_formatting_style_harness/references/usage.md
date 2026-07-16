# SQL Formatting Style Harness Usage

This file defines the runtime procedure for contract version `2.0`. Style rules are in `style-contract.md`.

## When to use

Use this harness after routing selects SQL formatting or a separately requested scalar-function refactor. It verifies the exact original/formatted SQL pair; it does not infer database semantics or replace the selected style contract.

## Inputs to collect

Capture:

- exact original and formatted SQL;
- `operation`: `formatting` or `refactor`;
- selected style-contract path and SHA-256;
- explicit user constraints;
- a complete alias plan only when aliases change;
- `scalar_function_refactor` only for a separately requested conversion.

Pass a `Path` or UTF-8 `bytes` when encoding evidence matters. The verifier decodes strictly and records the raw SHA-256. A Python `str` has no source-encoding provenance and is reported as `encoding_unverified`.

## Execution pattern

Execution level: `python-module`.

Implementation targets:

- `src.skills.sql_formatting_style.verify_sql_formatting_style`
- `src.skills.sql_formatting_style.resolve_style_contract_source`

### Contract Selection

Use the first readable source:

1. explicit caller-provided contract;
2. `$CODEX_HOME/skills/sql-formatting/SKILL.md`;
3. packaged `style-contract.md`.

Do not merge contracts. Record the exact selected path and hash.

### Formatting Call

```python
from pathlib import Path
from src.skills.sql_formatting_style import verify_sql_formatting_style

result = verify_sql_formatting_style(
    Path("original.sql"),
    Path("formatted.sql"),
    operation="formatting",
)
```

Formatting compares the complete ordered lexer token stream. It ignores only whitespace, safe case normalization, and substitutions approved by a complete alias plan. Comments, strings, quoted identifiers, operators, literals, statement order, projections, predicates, assignments, values, control flow, and statement families remain visible to the comparison.

### Alias Plan

Reviewer/LLM judgment establishes roles. Python checks only completeness and consistency.

```json
{
  "scopes": [
    {
      "scope_id": "scope_1",
      "basis_references": [
        {
          "kind": "reviewer_approved_business_role",
          "source": "review://SQL-42/order-and-customer-roles",
          "reviewer_approved": true,
          "role_names": ["order", "customer"]
        }
      ],
      "roles": [
        {
          "name": "order",
          "kind": "main",
          "members": [
            {
              "source": "ORDER_HEADER",
              "original_alias": "ORDER_HEADER",
              "alias": "A"
            }
          ]
        },
        {
          "name": "customer",
          "kind": "support",
          "members": [
            {
              "source": "CUSTOMER",
              "original_alias": "CUSTOMER",
              "alias": "B"
            }
          ]
        }
      ]
    }
  ]
}
```

The plan must exactly cover every declaration in every changed scope. Each changed scope has exactly one first `main` role with exactly one source, and that source is `A`; numbered main aliases such as `A1` and `A2` are invalid in every parsed scope even when aliases are unchanged. Subsequent distinct semantic/business-role families advance through `B`, `C`, `D`, and so on. A singleton non-main family uses the bare letter, while siblings in the same non-main family use suffixes from the first member (`B1`, `B2`), after which the next distinct family is `C`.

Each changed scope's `basis_references` is a non-empty array of objects with the required evidence fields shown above: `kind="reviewer_approved_business_role"`, a controlled reviewer artifact URI `source` using `review`, `spec`, `ticket`, or `design`, literal `reviewer_approved=true`, and non-empty unique `role_names`. Across the objects, `role_names` must exactly cover the names in `roles`; missing and extra names block. For API compatibility, one compact string shape is also accepted: `review://<review-id>/<declared-role-names>-roles`. Its `review` scheme declares reviewer approval and its final path must contain every declared role name plus `role` or `roles`. No other string shape is accepted. Table identity, repeated table identity (including the literal probe `repeated table identity only`), and source order do not qualify. Python validates this declaration and coverage but cannot authenticate the reviewer or infer the business semantics.

The plan cannot use an all-support or multi-source main plan, omit aliases, mix scopes, skip role letters, or start a multi-member non-main family unnumbered. Scope-aware binding covers nested/correlated `SELECT`, `UPDATE ... FROM`, joined `DELETE`, and `MERGE`; shadowed inner references do not belong to an outer rename. If aliases do not change and no numbered main-family declaration is present, the state is `not_needed` and a plan is not normative.

### Scalar-Function Refactor

Before proposing a join, inspect the actual function definition from DB/MCP/project source when available. Retain the function and block when the source is unavailable or when behavior is calculated, aggregated, security-filtered, dynamic, ambiguous, or not deterministic.

Structured evidence shape:

```json
{
  "decision": "convert",
  "function": {
    "name": "DBO.F_LOOKUP_NAME",
    "definition_source_kind": "database",
    "definition_source_ref": "db://ERP/DBO.F_LOOKUP_NAME",
    "definition_sha256": "<64 hex>"
  },
  "analysis": {
    "classification": "pure_deterministic_lookup",
    "source_table": "DBO.CODE_LOOKUP",
    "key_mappings": [
      {
        "parameter": "@CODE",
        "source_column": "CODE",
        "call_argument": "A.CODE",
        "join_expression": "B.CODE = A.CODE"
      }
    ],
    "filters": [],
    "return_expression": "CODE_NAME",
    "null_behavior": "returns_null_when_no_match",
    "cardinality": "zero_or_one",
    "unmatched_row_behavior": "preserve_outer_row_with_null",
    "preferred_reason": "Set-based access was reviewed for this query shape.",
    "disqualifiers": []
  },
  "artifacts": [
    {
      "kind": "function_definition",
      "artifact_id": "db-artifact-17",
      "sha256": "<64 hex>"
    }
  ]
}
```

This can establish `evidence_status=complete`; it cannot prove equivalence. Free-text reasons never count as semantic proof.

A host-trusted artifact correlated to the exact SQL pair can establish `external_correlation=provenance_correlated`. It does not upgrade `semantic_status`, which remains `not_proven`:

```json
{
  "trusted_external_verification": {
    "provider": "approved-db-comparison-runner",
    "artifact_id": "comparison-2026-07-10-01",
    "artifact_sha256": "<64 hex>",
    "kind": "db_result_comparison",
    "status": "matched",
    "original_sha256": "<verifier original_sha256>",
    "formatted_sha256": "<verifier formatted_sha256>"
  }
}
```

Python validates field completeness and hash correlation. Trust, function analysis, database authority, semantic equivalence, and preference remain external responsibilities. Because this mapping is caller-supplied, matching hashes can produce `status=mechanically_valid` but cannot authenticate execution. The resulting refactor must report `release_readiness.status=pending`, `success=false`, and a non-zero exit code.

No field nested inside `scalar_function_refactor` can self-authenticate. Only a runtime execution receipt independently validated by a trusted runtime and bound to the exact SQL hashes may establish `execution_authentication=authenticated`; semantic execution must also establish `semantic_checks.status=proven`. Until both conditions hold, refactor release readiness fails pending closed.

The release-ready path is available only through the Python API. Pass a host-owned `runtime_receipt_authenticator(payload: bytes, signature: str) -> bool`; do not construct this callback from caller evidence. The receipt retains the correlation fields above and additionally requires `receipt_id`, `database_identity`, `executed_at`, positive integer `comparison_count`, `function_definition_sha256`, `equivalence_contract_sha256`, and `signature`.

The signed `payload` is UTF-8 canonical JSON of `trusted_external_verification` with `signature` removed, keys sorted, `ensure_ascii=False`, and separators `(',', ':')`. The equivalence-contract SHA-256 uses the same JSON encoding over:

```json
{
  "version": "1",
  "function": {
    "name": "<function.name>",
    "definition_sha256": "<function.definition_sha256>"
  },
  "analysis": "<the complete structured analysis object>"
}
```

The harness first validates SQL correlation, authoritative definition artifacts, mechanical call-to-join boundaries, and both definition/contract bindings. It then invokes the external authenticator. Only an exact `True` result produces `status=verified`, `semantic_status=proven`, `execution_authentication=authenticated`, and release readiness `ready`. Missing callbacks remain pending; missing, mismatched, rejected, or tampered receipts fail closed.

### INSERT/SELECT Layout

For eight or more target/value mappings, the verifier measures each source expression as canonical non-comment token text joined with one space. Expressions up to 72 characters must remain horizontally grouped by physical start line; at most one short singleton is allowed as a group remainder. Expressions of 73 characters or more have a declared vertical fallback and may start on their own lines. The emitted `style_lint.insert_select_layout_contract` records these thresholds and the measurement name.

### JOIN and Query-List Layout

Preserve existing `JOIN` indentation. No absolute indentation or `JOIN`-to-`ON` delta is a universal verifier rule, and generated deep indentation is not source authority. When authoring SQL without a source layout, one query indentation level below `FROM` is a fallback; align `ON` and continuation `AND` terms within that join block.

For query-level `GROUP BY` and `ORDER BY`, the verifier splits only at commas whose token depth matches the clause. It keeps function/subquery commas, comments, `ASC`/`DESC`, and `COLLATE` within the item. Simple lists whose compact rendering fits the 100-column preferred width must remain inline; inline lists wider than 100 are rejected and must wrap compactly without exceeding the 120-column hard ceiling. Complex items remain atomic. Nested query clauses are evaluated in their own scope, while window and ordered-aggregate `ORDER BY` are excluded by their deeper token depth.

### Session Audit Binding

The session audit accepts verifier evidence only when a real verifier call is correlated to structured output and the exact final SQL. The output must include valid SQL/style hashes, a verification id, passed mechanical checks, and the actual `alias_role_plan_validation` mapping. Accepted alias states are `not_needed` and `verified`.

Legacy `alias_checks`, flat `alias_status`, assistant marker text, copied examples, or unbound output are rejected. `required` and `conflict` alias states block output. The final SQL must be exactly extractable and its UTF-8 SHA-256 must equal `formatted_sha256`.

### CLI

```powershell
python -m src.skills.sql_formatting_style `
  --original <original.sql> `
  --formatted <formatted.sql> `
  --style-contract <selected-contract> `
  --operation formatting
```

Actual verifier execution is mandatory. Preserve `token_optimizer_status=passthrough`; do not compress SQL or evidence to manufacture token savings.

## Evidence to produce

- exact original/formatted SHA-256 values and the selected style-contract hash;
- `input_integrity`, `formatting_preservation`, `style_lint`, and `alias_role_plan_validation` states;
- scalar-refactor evidence status, `external_correlation`, `execution_authentication`, and `semantic_status` when refactoring was separately requested;
- `release_readiness`, top-level `success`, and exit code, distinguishing formatting completion from refactor release readiness;
- the verifier call/output binding for the exact final SQL;
- demo and smoke-script exit codes when validating the packaged harness.

`external_correlation=provenance_correlated` is provenance evidence only. The verifier must continue to emit `semantic_status=not_proven`, `semantic_checks.status=not_proven`, `execution_authentication=not_authenticated`, and `release_readiness.status=pending`; `HarnessResult.success` must be false and the exit code non-zero.

## Failure handling

Block output when source or formatter integrity fails, the complete token stream changes outside an approved alias plan/refactor boundary, or aliases lack complete per-scope evidence. A mechanically valid requested refactor remains pending when semantic proof or authenticated execution is missing. Retain the original scalar call when source evidence is missing or disqualifying behavior exists. Never turn a correlated artifact into a semantic-equivalence or completion claim.

## Quality bar

Formatting verification passes only when the actual Python verifier ran against the exact SQL pair, all deterministic gates passed, and every alias change is bound to a complete plan. Scalar refactor release readiness additionally requires proven semantic execution and authenticated runtime evidence. Documentation reads, free text, matching names, and correlated hashes alone are not semantic database proof or completed verification.
