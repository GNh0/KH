# Validation examples

Do not infer a new business validation from an example. Apply only the checks required by the actual operation, with its full keys, units and transaction behavior.

## Missing related row

Do not remove a valid IF EXISTS check because SELECT/WHERE subqueries are disfavored. IF EXISTS owns the control-flow check; JOIN supplies the related rows.

In this fictional schema PRODUCT_MASTER has a unique, non-null PRODUCT_CODE.

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

## Edited-quantity-proposal

Do not count the current document's persisted contribution twice during EDIT. Do not overlook repeated source keys in the proposed rows or change quantity units to make the comparison easier.

This fictional flow has already validated source receipt existence and units. STOCK_RECEIPT is unique by COMPANY_ID/RECEIPT_NO/RECEIPT_LINE, and each STOCK_ISSUE row consumes that receipt in the same unit. Quantities and document keys, including @DOCUMENT_NO, are non-null in this example. @TMP_PROPOSAL contains the current document's **complete final contribution** after the edit, including retained unchanged rows and excluding deleted rows. Repeated receipt keys in that proposal must be summed. For a target with nullable quantities, establish its actual NULL meaning before comparing; do not silently reinterpret NULL as zero or add an unrequested required-value rule.

```sql
IF EXISTS (
           SELECT 1
           FROM (
                 SELECT T.RECEIPT_NO
                      , T.RECEIPT_LINE
                      , SUM(T.QTY) AS QTY
                 FROM @TMP_PROPOSAL T
                 GROUP BY T.RECEIPT_NO, T.RECEIPT_LINE
                ) A
                   INNER JOIN STOCK_RECEIPT B
                           ON B.COMPANY_ID = @COMPANY_ID
                           AND A.RECEIPT_NO = B.RECEIPT_NO
                           AND A.RECEIPT_LINE = B.RECEIPT_LINE
                   LEFT OUTER JOIN (
                                    SELECT T.COMPANY_ID
                                         , T.RECEIPT_NO
                                         , T.RECEIPT_LINE
                                         , SUM(T.QTY) AS QTY
                                    FROM STOCK_ISSUE T
                                    WHERE T.COMPANY_ID = @COMPANY_ID
                                      AND T.DOCUMENT_NO <> @DOCUMENT_NO
                                    GROUP BY T.COMPANY_ID, T.RECEIPT_NO, T.RECEIPT_LINE
                                   ) C
                                   ON B.COMPANY_ID = C.COMPANY_ID
                                   AND B.RECEIPT_NO = C.RECEIPT_NO
                                   AND B.RECEIPT_LINE = C.RECEIPT_LINE
           WHERE A.QTY + ISNULL(C.QTY, 0) > B.QTY
          )
BEGIN
    RAISERROR('The proposed quantity exceeds the receipt quantity.', 16, 9)
    RETURN;
END
```

Do not apply this whole-document exclusion to a changed-rows-only XML batch: it would also discard the current document's retained persisted rows. Derive that caller's final contribution through its actual full-key/state flow before comparing.

Check equal-to-limit and over-limit proposals, duplicate source keys, retained/deleted rows, the same receipt in another company, and an EDIT with an existing current-document contribution. SQL shape alone does not establish unit or concurrency correctness.
