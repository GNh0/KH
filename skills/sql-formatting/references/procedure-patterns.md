# Illustrative SELECT/SAVE patterns

These fictional examples express structures observed in the user's approved comparison procedures. They contain no application procedure bodies or real business identifiers. Table/column names, messages and state values are illustrative, not target contracts. Read the complete relevant comparison procedure and actual caller/schema before implementing; do not treat these excerpts as deployable procedures or copy unrelated reference details.

## SELECT: join an aggregate at the linked key

In this fictional schema, ORDER_HEADER has one row per COMPANY_ID/ORDER_NO and ORDER_DETAIL has multiple lines per header. Aggregate detail rows before joining so they cannot multiply the header. Lookup-only data likewise uses LEFT OUTER JOIN when a missing descriptive row must not remove the main row. Use INNER JOIN when the requested inclusion rule requires a match.

```sql
SELECT A.COMPANY_ID
     , A.ORDER_NO
     , A1.AMOUNT
     , A1.NET_AMOUNT
FROM ORDER_HEADER A
        LEFT OUTER JOIN (
                         SELECT T.COMPANY_ID
                              , T.ORDER_NO
                              , SUM(T.AMOUNT) AS AMOUNT
                              , SUM(T.NET_AMOUNT) AS NET_AMOUNT
                         FROM ORDER_DETAIL T
                         WHERE T.COMPANY_ID = @COMPANY_ID
                         GROUP BY T.COMPANY_ID, T.ORDER_NO
                        ) A1
                        ON A.COMPANY_ID = A1.COMPANY_ID
                        AND A.ORDER_NO = A1.ORDER_NO
WHERE A.COMPANY_ID = @COMPANY_ID
  AND A.ORDER_DATE BETWEEN @FROM_DATE AND @TO_DATE
```

Read lookup values from joined rows and totals from grouped joined rows. Do not put a SELECT inside each output expression or WHERE predicate, or fetch those row values into scalars first. Preserve the target's actual missing-row/NULL behavior; a blanket fallback is not implied.

## SAVE: keep XML rows as rows through the write

Assume XML was parsed into @TMP_CONTACT for one specified customer. CONTACTS has the key COMPANY_ID/CUSTOMER_ID/CONTACT_ID. Input rows join the persisted table directly, with the applicable change state on each write. Multiple submitted rows remain a set.

```sql
UPDATE A
SET CONTACT_NAME = B.CONTACT_NAME
  , EMAIL = B.EMAIL
  , PHONE = B.PHONE
  , MODIFIED_AT = GETDATE()
  , MODIFIED_BY = @USER_ID
FROM CONTACTS A
        INNER JOIN @TMP_CONTACT B
                ON A.CONTACT_ID = B.CONTACT_ID
WHERE A.COMPANY_ID = @COMPANY_ID
  AND A.CUSTOMER_ID = @CUSTOMER_ID
  AND B.CHANGE_STATE = 'MOD'

DELETE A
FROM CONTACTS A
        INNER JOIN @TMP_CONTACT B
                ON A.CONTACT_ID = B.CONTACT_ID
WHERE A.COMPANY_ID = @COMPANY_ID
  AND A.CUSTOMER_ID = @CUSTOMER_ID
  AND B.CHANGE_STATE = 'DEL'
```

For a NEW path, use the actual target's INSERT SELECT from parsed rows with matching grouped target/value lists. Derive its keys, state strings, related writes and transaction/error ownership from the complete approved SAVE flow; the fictional contact example does not supply those contracts.

## Validation: IF EXISTS owns the check; JOIN supplies related rows

Here PRODUCT_MASTER has a unique PRODUCT_CODE. An IF EXISTS check is valid control flow; it differs from nesting a query inside a SELECT list or WHERE predicate.

```sql
IF EXISTS (
           SELECT 1
           FROM @TMP_DETAIL A
                   LEFT OUTER JOIN PRODUCT_MASTER B
                                ON A.PRODUCT_CODE = B.PRODUCT_CODE
           WHERE B.PRODUCT_CODE IS NULL
             AND A.CHANGE_STATE <> 'DEL'
          )
BEGIN
    RAISERROR('An input product is not registered.', 16, 9)
    RETURN;
END
```

For quantity validation, join the input rows to quantities aggregated at the full linked key, then compare those values inside the owning IF EXISTS. Derive the target's units, EDIT exclusion and duplicate-input handling before writing that comparison.

## Necessary variables and staging updates have a responsibility

A number allocator's output or a single-document result can require a variable. Recording a newly generated key in input rows can require a staging UPDATE. These responsibilities differ from copying every available input field into variables or normalizing input quantities/units merely to simplify a following write. Decide from the actual data flow, not a variable count or a blanket ban on staging UPDATEs.

Before applying a draft and after the final edit, compare its lookup, aggregation, XML write and validation responsibilities with the matching examples and complete references. Inspect the actual body being applied, including user-rejected existing code that a narrow diff would hide. A final edit reopens the affected comparison and audit.
