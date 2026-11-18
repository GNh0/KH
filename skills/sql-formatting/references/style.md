# SQL 서식

## SQL layout

- A는 주 대상, B/C/D는 후속 업무 역할, B1/B2는 같은 역할의 여러 테이블, 파생 쿼리 내부는 T 계열을 쓴다. 테이블명·MAINCD만으로 E/F를 정하지 않는다. “정렬만/별칭 그대로”는 원래 별칭을 보존한다.
- 승인된 대문자·선행 쉼표 표기를 따른다. SELECT 목록, UPDATE SET, SP 인자 순서와 기본값을 맞춘다. 별칭 AS와 출력 열 AS를 구별한다.
- 일반 JOIN의 ON과 그 조건의 AND는 JOIN의 I 열에 맞춘다. 파생 FROM/JOIN은 여는 괄호와 닫는 괄호를 맞추고 안쪽 절은 한 칸 더 들인다. 파생 JOIN의 ON·AND·OR는 여는 괄호 열에 둔다. 중첩·UNION은 각 괄호를 기준으로 한다.
- EXISTS 괄호는 같은 열, 내부 SQL은 다음 줄에서 한 칸 더 들인다. 짧은 GROUP BY·ORDER BY는 한 줄, CASE 괄호는 해당 작성 예시와 맞춘다. BETWEEN의 AND는 해당 식 안에 둔다.
- INSERT 열과 SELECT/VALUES 값은 순서·줄 그룹·실제 시작 열을 대응시킨다. 두 목록에서 가장 긴 표현에 맞춰 공백으로 정렬한다. UPDATE SET은 세로 목록으로 쓴다.
- JOIN 종류·순서·조건, 출력 타입·필드, 리터럴·한글·기존 주석을 보존한다. 주석 처리 요청은 원문을 남긴다. 필요한 JOIN·IF EXISTS·업무 함수와 상수는 실제 의미를 지킨다.
- JOIN으로 변경할 때는 전체 키·NULL·중복·집계 단위, 함수 원본·실행 의미를 확인한다. 다중 결과는 각 결과의 기간·필터·집계 키·UNION·비율을 맞춘다.
- 요청이 UPDATE 하나면 해당 UPDATE FROM/CROSS APPLY를 완성한다. DB 변경은 지정한 연결·DB·키, 트랜잭션과 변경/제외 행을 확인한다. 중간 테이블은 [필요성 기준](../../work-execution/references/preferences.md)을 따른다.

## JOIN 예시

```sql
SELECT A.ITEMCD
     , B.ITEMNM
FROM MA210T A
        LEFT OUTER JOIN BA030T B
                     ON A.ITEMCD = B.ITEMCD
WHERE A.ORGDIV = @ORGDIV
```

```sql
SELECT A.ORDERNO
     , B.QTY
FROM ORDERS A
        LEFT OUTER JOIN (
                         SELECT T.ORDERNO
                              , SUM(T.QTY) AS QTY
                         FROM WORK_LOG T
                         GROUP BY T.ORDERNO
                        ) B
                        ON A.ORDERNO = B.ORDERNO
                        AND A.QTY = B.QTY
```

파생 JOIN의 닫는 괄호, ON, AND는 여는 괄호와 같은 열이다. 실제 괄호 위치가 기준이다.

## 중첩·UNION 예시

```sql
    SELECT A.PERIOD
         , A.QTY
    FROM (
          SELECT T.PERIOD
               , SUM(T.QTY) AS QTY
          FROM (
                SELECT T.PERIOD, T.QTY
                FROM HISTORY T

                UNION ALL

                SELECT T.PERIOD, T.QTY
                FROM ORDERS T
               ) T
          GROUP BY T.PERIOD
         ) A
    ORDER BY A.PERIOD
```

## INSERT 열 대응 예시

```sql
    INSERT INTO TARGET
    (
           ID  , VERY_LONG_FIELD , C       , D
         , E   , F               , G       , H
    )
    SELECT @ID , @A              , @COLUMN , @D
         , @E  , @F              , @G      , @H
    FROM SOURCE A
```

기존의 넉넉한 열 간격은 유지한다. 여러 줄 표현·주석이 있으면 최종 문자열에서 열/값의 의미와 시작 열을 직접 확인한다.
