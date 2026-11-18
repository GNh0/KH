# 조회 예시

## SELECT contract

| 바뀌는 부분 | 작성할 형태 |
| --- | --- |
| 표시명·업무 자격 | 설명이 없어도 남는 행은 LEFT OUTER JOIN. 반드시 있어야 하는 자격 행은 INNER JOIN. 같은 키가 여러 건이면 JOIN 전 반환 단위를 확인한다. |
| 헤더별 상세 합계 | 상세를 전체 헤더 키로 먼저 GROUP BY한 뒤 붙인다. 사용자의 지시 없이 누락 합계를 0으로 대체하지 않는다. |
| 처리된 행 제외 | 처리 테이블에 전체 키로 LEFT OUTER JOIN 후 NULL 불가 키의 IS NULL로 골라낸다. |
| 같은 모드의 여러 결과 | 한 분기에 호출자의 결과표 순서대로 SELECT를 둔다. 공통 처리와 서로 다른 모드의 조건은 원래 범위를 유지한다. |

아래에서 현재 변경하는 항목의 예시를 대조한다. 표·값은 가상이다.

## Lookup and eligibility

승인 건만 조회하되 거래처 설명이 없는 승인 건도 남기는 예다. 회사·주문별 승인은 최대 한 행이다.

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

## Grouped detail JOIN

회사·주문별로 상세 금액을 먼저 합산해 헤더 행 수를 보존한다.

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

게시되지 않은 문서를 조회한다. 처리 키의 문서번호는 NULL 불가다.

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

## One branch with multiple results

이 호출자의 LIST는 1표, DETAIL은 헤더와 상세 2표를 순서대로 소비한다.

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
