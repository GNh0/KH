# SAVE examples

These fragments use fictional input contracts. Do not copy their types, lengths, states, key allocation or transaction choices into a target without checking its complete SAVE flow.

## Parsed rows and NEW

Do not copy each XML row field into scalar variables before INSERT SELECT. Parse the required rows once and consume them as rows.

This example receives contacts for one COMPANY_ID/CUSTOMER_ID. CONTACT_ID is already assigned by the approved key-allocation path and is unique within that customer. The caller sends NEW/MOD/DEL. The example's VARCHAR fields and lengths are fictional. The owning error path must release an allocated XML handle that is still live and preserve the original failure. Clear the handle after successful removal so a later INSERT failure cannot cause a second removal. The success-path fragment below does not replace that error/transaction flow.

```sql
DECLARE @DOC_ID INT

DECLARE @TMP_CONTACT TABLE
(
      CHANGE_STATE VARCHAR(3)
    , CONTACT_ID VARCHAR(20)
    , CONTACT_NAME VARCHAR(80)
    , EMAIL VARCHAR(100)
    , PHONE VARCHAR(30)
)

EXEC SP_XML_PREPAREDOCUMENT @DOC_ID OUTPUT, @XML_DATA

INSERT INTO @TMP_CONTACT
(
       CHANGE_STATE , CONTACT_ID , CONTACT_NAME , EMAIL , PHONE
)
SELECT CHANGE_STATE , CONTACT_ID , CONTACT_NAME , EMAIL , PHONE
FROM OPENXML(@DOC_ID, '/ROOT/CONTACT', 1)
WITH
(
      CHANGE_STATE VARCHAR(3)
    , CONTACT_ID VARCHAR(20)
    , CONTACT_NAME VARCHAR(80)
    , EMAIL VARCHAR(100)
    , PHONE VARCHAR(30)
)

EXEC SP_XML_REMOVEDOCUMENT @DOC_ID
SET @DOC_ID = NULL

INSERT INTO CONTACTS
(
       COMPANY_ID  , CUSTOMER_ID  , CONTACT_ID   , CONTACT_NAME
     , EMAIL       , PHONE        , CREATED_AT   , CREATED_BY
)
SELECT @COMPANY_ID , @CUSTOMER_ID , A.CONTACT_ID , A.CONTACT_NAME
     , A.EMAIL     , A.PHONE      , GETDATE()    , @USER_ID
FROM @TMP_CONTACT A
WHERE A.CHANGE_STATE = 'NEW'
```

Do not use the XML row index as a persisted key merely because it is available. If the target generates new keys, follow its actual numbering scope, deterministic ordering and concurrency contract. A necessary numbering variable or staging UPDATE recording the generated key remains valid.

## MOD and DEL

Do not normalize the input table or introduce a scalar-field copying phase merely to prepare these writes. Use parsed row values directly in their owning UPDATE/DELETE.

This continues the same single-customer contact contract. CONTACTS has the key COMPANY_ID/CUSTOMER_ID/CONTACT_ID.

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

Apply needed value expressions at the write when that preserves the actual contract. Do not turn this preference into a ban on required input/key preparation.

## Multiple-master-delete

Do not collapse several selected document keys into one scalar assignment, and do not confuse deleting detail rows with deleting entire documents. Keep all selected full keys as a set.

Here @TMP_DOCUMENT already contains COMPANY_ID/DOCUMENT_NO/CHANGE_STATE for multiple selected masters. Required deletion preconditions run in the actual owning SAVE flow. Within that transaction, delete related details before their selected headers.

```sql
DELETE A
FROM DOCUMENT_DETAIL A
        INNER JOIN @TMP_DOCUMENT B
                ON A.COMPANY_ID = B.COMPANY_ID
                AND A.DOCUMENT_NO = B.DOCUMENT_NO
WHERE A.COMPANY_ID = @COMPANY_ID
  AND B.CHANGE_STATE = 'DEL'

DELETE A
FROM DOCUMENT_HEADER A
        INNER JOIN @TMP_DOCUMENT B
                ON A.COMPANY_ID = B.COMPANY_ID
                AND A.DOCUMENT_NO = B.DOCUMENT_NO
WHERE A.COMPANY_ID = @COMPANY_ID
  AND B.CHANGE_STATE = 'DEL'
```

Check two selected masters, an unselected master and the same document number in another company. Do not remove required related writes or target-specific deletion restrictions to imitate this short fragment.
