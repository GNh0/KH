# SQL Formatting Style Harness Minimal Workflow

Use these scenarios to review contract version `2.0`.

## Scenario

Verify formatting-only SQL preservation, alias-plan enforcement, and separately requested scalar-function refactors without treating deterministic checks or correlated provenance as semantic database proof.

## Expected steps

1. Preserve the original as UTF-8 bytes/path when encoding proof is required.
2. Select and hash one style contract.
3. Declare `formatting` or `refactor`.
4. Execute the verifier; routing or documentation reads are not execution.
5. Bind the correlated result through `alias_role_plan_validation`, never legacy alias marker text.
6. Keep SQL/evidence passthrough.

## Expected evidence

### Case 1: Formatting Success

The source is valid and the formatted SQL changes only whitespace and safe case.

Expected:

- `input_integrity.status=valid`;
- `formatting_preservation.status=verified`;
- `style_lint.status=passed`;
- `alias_role_plan_validation.status=not_needed`;
- `semantic_refactor_evidence.scalar_function_refactor.status=not_requested`;
- `release_readiness.status=ready`, `success=true`, and exit code `0`.

Any scalar call remains in the token stream.

### Case 2: Source Invalid

The original has an unterminated string/comment/bracket or unbalanced parenthesis.

Expected:

- `input_integrity.status=source_invalid`;
- formatting preservation is not evaluated;
- no guessed repair is emitted.

### Case 3: Alias Change Needs a Plan

The formatter replaces raw qualifiers with `A`/`B` without a per-scope plan.

Expected:

- `alias_role_plan_validation.status=required`;
- `alias_role_plan_required` blocks output;
- no role is inferred from repeated source names.

After a reviewer supplies concrete basis references and a complete scope plan, rerun. Python verifies membership, coverage, scope, numbering, and reference substitution only.

### Case 4: Refactor Evidence Complete but Not Proven

A separate request proposes replacing `DBO.F_LOOKUP_NAME(A.CODE)` with a join. The actual function definition has been inspected and the structured bundle is complete, but no trusted result-comparison artifact is correlated to both SQL hashes.

Expected:

- `evidence_status=complete`;
- scalar refactor `status=not_proven`;
- `semantic_checks.status=not_proven`;
- the request remains blocked from an equivalence claim.

Free text such as "looks like a lookup" is incomplete evidence.
A comparison artifact correlated to both SQL hashes may add `external_correlation=provenance_correlated` and produce scalar refactor `status=mechanically_valid`, but it remains unauthenticated caller evidence. Expected completion fields are:

- `semantic_status=not_proven` and `semantic_checks.status=not_proven`;
- `execution_authentication=not_authenticated`;
- `release_readiness.status=pending`;
- `success=false` and a non-zero exit code.

Only a trusted runtime-validated execution receipt bound to the exact SQL pair may authenticate execution; semantic execution must also be proven before refactor release readiness can become ready.

### Case 5: Disqualified Conversion

The function definition is unavailable, ambiguous, calculated, aggregated, security-filtered, dynamic, or can return multiple matches.

Expected:

- retain the scalar function;
- scalar refactor `status=blocked`;
- list the disqualifier or missing fields;
- never infer behavior from the function/table name.

## Failure cases

- invalid source or damaged formatter output;
- token, literal, comment, statement, or control-flow drift;
- alias changes without a complete evidence-backed per-scope plan;
- scalar conversion with incomplete/disqualifying evidence;
- any claim that provenance correlation proves semantic database equivalence.

## Done criteria

The verifier ran against the exact SQL pair, formatting gates passed or blocked with explicit issue codes, aliases are `not_needed` or `verified`, and every requested scalar refactor remains blocked unless its mechanical boundary is valid. Correlated provenance must still report semantic status as `not_proven`.

- `execution_level`: `python-module`
- `implementation_targets`:
  - `src.skills.sql_formatting_style.verify_sql_formatting_style`
  - `src.skills.sql_formatting_style.resolve_style_contract_source`
- Verification evidence: successful smoke/demo exit codes plus the persisted `HarnessResult` metadata for the exact SQL pair.

## Demo

```powershell
python scripts/demo.py --output-dir <tmp>
```

`actual_runtime_path`: `skills/sql_formatting_style_harness/scripts/demo.py` imports and calls `src.skills.sql_formatting_style.verify_sql_formatting_style`, while binding its profile to `src.skills.demo_scenarios`.

The demo writes UTF-8 JSON for formatting success, semantic mutation blocking, source corruption, alias-plan blocking/success, incomplete refactor evidence, and provenance-correlated evidence whose semantic status remains `not_proven`.
