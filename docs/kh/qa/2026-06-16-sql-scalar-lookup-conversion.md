# SQL Scalar Lookup Conversion QA - 2026-06-16

## Scope

This note defines the generic evidence boundary for converting a scalar lookup
function to a join. It is not a default instruction to rewrite a particular
function, table, schema, or application query.

Formatting-only work must retain scalar functions. A conversion is a separate
`operation="refactor"` request and remains blocked unless the structured
evidence and parsed SQL boundary both pass.

## Evidence-Bound Conditions

A conversion candidate must provide all of the following:

- an authoritative function definition reference and content hash;
- classification as a pure deterministic lookup, with no calculation,
  aggregation, dynamic SQL, security filtering, or side effects;
- the exact lookup source identity, including every supplied database and
  schema qualifier;
- complete parameter-to-column mappings, fixed filters, and return column;
- reviewed null behavior, zero-or-one cardinality, and unmatched-row behavior;
- a `LEFT OUTER JOIN` that preserves the outer row when the lookup misses;
- original and formatted SQL hashes correlated to any external comparison
  artifact.

Missing or conflicting evidence blocks the conversion. Free text such as
"this looks like a lookup" is not evidence.

## Neutral Example

Original expression:

```sql
SELECT DBO.F_LOOKUP_DESCRIPTION(A.STATUS_CODE) AS STATUS_NAME
FROM DBO.ORDER_HEADER A;
```

The evidence may declare:

```text
function.name = DBO.F_LOOKUP_DESCRIPTION
analysis.classification = pure_deterministic_lookup
analysis.source_table = DBO.CODE_LOOKUP
analysis.key_mappings = @STATUS_CODE -> B.CODE = A.STATUS_CODE
analysis.filters = B.DOMAIN_CODE = 'ORDER_STATUS'; B.ACTIVE_YN = 'Y'
analysis.return_expression = DESCRIPTION
analysis.null_behavior = returns_null_when_no_match
analysis.cardinality = zero_or_one
analysis.unmatched_row_behavior = preserve_outer_row_with_null
```

With the authoritative function definition and correlation artifacts present,
the bounded SQL shape is:

```sql
SELECT B.DESCRIPTION AS STATUS_NAME
FROM DBO.ORDER_HEADER A
        LEFT OUTER JOIN DBO.CODE_LOOKUP B
                     ON B.CODE = A.STATUS_CODE
                     AND B.DOMAIN_CODE = 'ORDER_STATUS'
                     AND B.ACTIVE_YN = 'Y';
```

Schema qualification is evidence. If the evidence declares
`DBO.CODE_LOOKUP`, an unqualified `CODE_LOOKUP` source does not prove the same
identity and the harness must block the refactor.

## Fail-Closed Limits

The parsed boundary permits only one scalar-call replacement and one matching
`LEFT OUTER JOIN` in the same SQL scope. It blocks conversions that introduce
unrelated literal, predicate, arithmetic, statement-count, query-count, join,
or source changes. Ambiguous, computed, aggregate, multi-row, stateful,
permission-sensitive, or unavailable function definitions remain unchanged.

## Trust Boundary

The Python harness can verify evidence shape, hashes, exact parsed source
identity, and the bounded SQL rewrite. It does not authenticate database
execution and does not prove semantic or performance equivalence.

Caller-supplied external comparison metadata is provenance-correlated only.
Unless a separately trusted system authenticates the execution and artifact,
the comparison is claimed and unverified. No cryptographic assurance is
inferred from caller-supplied identifiers or hashes.

## Regression Verification

Run from the KH repository:

```powershell
python -m unittest tests.test_sql_formatting_style_harness -q
```

The hardening target remains `91` passing tests. A green result proves the
deterministic harness gates covered by those tests; it does not prove live
database behavior.
