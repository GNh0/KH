# SELECT examples

Use fictional tables only as structural examples. Do not add these business rules to a target unless its caller and approved source require them.

## Lookup and eligibility

Do not use INNER JOIN merely to fetch descriptive data when the main row must survive a missing description. Conversely, do not replace a required eligibility JOIN with LEFT OUTER JOIN and display a plausible default.

This fictional request lists only approved orders, including orders whose customer description is missing. ORDER_HEADER and ORDER_APPROVAL each have at most one row per COMPANY_ID/ORDER_NO; CUSTOMER_MASTER is unique by COMPANY_ID/CUSTOMER_ID. Approval belongs to the order role (A1), while customer data is another role (B).

```sql
SELECT A.ORDER_NO
     , B.CUSTOMER_NAME
     , A1.APPROVED_AT
FROM ORDER_HEADER A
        INNER JOIN ORDER_APPROVAL A1
                ON A.COMPANY_ID = A1.COMPANY_ID
                AND A.ORDER_NO = A1.ORDER_NO
                AND A1.APPROVAL_STATE = 'APPROVED'
        LEFT OUTER JOIN CUSTOMER_MASTER B
                     ON A.COMPANY_ID = B.COMPANY_ID
                     AND A.CUSTOMER_ID = B.CUSTOMER_ID
WHERE A.COMPANY_ID = @COMPANY_ID
  AND A.ORDER_DATE BETWEEN @FROM_DATE AND @TO_DATE
```

Check both cases: a missing customer keeps an approved order; a missing approval excludes it. If approval has multiple matching rows in the actual target, resolve that actual row grain before using this shape.

## Grouped detail JOIN

Do not let matching detail rows multiply a header result, or fetch a total with a SELECT inside the output list. Aggregate to the header key before joining.

ORDER_HEADER has one row per COMPANY_ID/ORDER_NO and ORDER_DETAIL has multiple lines per header. The example preserves NULL totals when no detail exists; only add a zero fallback if the real result contract requires it.

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

## Exclusion JOIN

Do not introduce WHERE NOT EXISTS/NOT IN for a new exclusion when the approved JOIN form meets the contract. Join the processing key and keep only unmatched rows.

In this fictional request, DOCUMENT_HEADER and POSTED_DOCUMENT use COMPANY_ID/DOCUMENT_NO as their non-null key. This example selects documents with no posting.

```sql
SELECT A.DOCUMENT_NO
     , A.DOCUMENT_DATE
FROM DOCUMENT_HEADER A
        LEFT OUTER JOIN POSTED_DOCUMENT A1
                     ON A.COMPANY_ID = A1.COMPANY_ID
                     AND A.DOCUMENT_NO = A1.DOCUMENT_NO
WHERE A.COMPANY_ID = @COMPANY_ID
  AND A1.DOCUMENT_NO IS NULL
```

Do not use a nullable descriptive field as the absence test. Preserve a genuinely required existing exclusion when changing its shape would alter NULL behavior, full-key matching or results.

## One branch with multiple results

Do not repeat the same mode condition just to return another table, or merge different modes with conditional OR predicates merely to share SQL. Keep each mode's ordered results in its owning branch.

Here the caller expects LIST to return one table, and DETAIL to return header then detail. That order is part of this fictional caller contract.

```sql
IF @WORKTYPE = 'LIST'
BEGIN
    SELECT A.ORDER_NO
         , A.ORDER_DATE
    FROM ORDER_HEADER A
    WHERE A.COMPANY_ID = @COMPANY_ID
      AND A.ORDER_DATE BETWEEN @FROM_DATE AND @TO_DATE
END
ELSE IF @WORKTYPE = 'DETAIL'
BEGIN
    SELECT A.ORDER_NO
         , A.ORDER_DATE
    FROM ORDER_HEADER A
    WHERE A.COMPANY_ID = @COMPANY_ID
      AND A.ORDER_NO = @ORDER_NO

    SELECT A.ORDER_NO
         , A.LINE_NO
         , A.PRODUCT_CODE
         , A.QTY
    FROM ORDER_DETAIL A
    WHERE A.COMPANY_ID = @COMPANY_ID
      AND A.ORDER_NO = @ORDER_NO
    ORDER BY A.LINE_NO
END
```

Do not copy this result count/order to another caller. Preserve separate shared phases when they have a real responsibility.
