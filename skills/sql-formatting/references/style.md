# KH SQL 스타일

현재 SQL의 의미와 명시적 요구가 먼저다. 일반 정리는 별칭 정규화를 포함하고 “별칭 그대로/정렬만”은 유지한다. 생성·정리·최적화·비교·실행을 구분한다.

- 주 조회 대상 A, 다음 업무 역할 B/C/D, 같은 역할군 안의 여러 테이블 B1/B2처럼 쓴다. 파생 쿼리 내부는 T 계열로 스코프를 구분한다. 서로 다른 물리 테이블도 같은 업무 역할군일 수 있다. BA011T 또는 MAINCD만으로 E/F나 E1/E2를 고정하지 않는다.
- 키워드·식별자는 대상의 승인된 대문자 스타일을 따른다. 문자열·한글·주석은 바꾸지 않는다. 테이블 별칭 AS와 출력 컬럼 AS를 구분한다.
- SELECT/UPDATE SET/SP 파라미터는 해당 예시의 선행 쉼표를 따른다. SP 파라미터 기본값은 승인 템플릿과 실제 호출 계약에서 가져온다.
- 일반 테이블 JOIN의 ON/같은 JOIN의 AND는 JOIN 끝 IN의 I 위치에 맞춘다. 파생 테이블 JOIN은 여는 ( 위치에 닫는 )와 ON/AND를 수직으로 맞춘다. FROM/JOIN의 괄호 안 SELECT·FROM·WHERE·GROUP BY 등은 여는 (보다 한 칸 오른쪽에 맞춘다. 중첩 블록은 각각의 여는 (를 기준으로 한다. LEFT OUTER JOIN을 임의 축약하지 않는다.
- EXISTS 괄호는 수직으로 맞추고 내부 SQL은 다음 줄에서 여는 괄호보다 한 칸 오른쪽으로 시작한다. 짧은 GROUP BY/ORDER BY는 한 줄로 유지하고 CASE 괄호를 해당 예시대로 쓴다.
- INSERT 열과 SELECT/VALUES 값은 같은 가로 묶음·순서·탭 위치·줄바꿈으로 대응한다. UPDATE SET은 세로 목록이다. 줄을 맞췄다는 이유로 열/값 대응의 의미 검사를 생략하지 않는다.
- JOIN 종류/순서·필터·출력 필드·리터럴·기존 주석을 보존한다. 기존 로직을 주석 처리하라는 요청에서는 삭제하지 않는다.

기본 배치 예:

```sql
SELECT A.ITEMCD
     , B.ITEMNM
FROM MA210T A
        LEFT OUTER JOIN BA030T B
                     ON A.ITEMCD = B.ITEMCD
WHERE A.ORGDIV = @ORGDIV
```

일반 테이블 JOIN과 파생 테이블 JOIN의 기준점을 구분한다. 파생 JOIN은 여는 `(`, 닫는 `)`, 그 JOIN의 줄 시작 `ON`·`AND`·`OR`를 같은 열에 둔다. 닫는 괄호를 LEFT/INNER 등 JOIN 시작 위치로 당기지 않는다. 별칭은 닫는 괄호와 같은 줄에 둔다.

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

이 예시는 FROM 0칸, JOIN 8칸, 여는/닫는 괄호와 ON/AND 24칸, 내부 절 25칸이다. 숫자를 전역 들여쓰기 값으로 쓰지 않는다. 실제 여는 괄호 위치가 기준이다. 같은 JOIN의 조건을 잇는 AND/OR에 적용하며 BETWEEN의 AND, CASE 내부 조건, 하위 쿼리 조건은 소속 절의 배치를 유지한다.

FROM의 첫 파생 쿼리와 UNION ALL이 있는 중첩도 같은 괄호 기준을 따른다. SELECT 목록의 선행 쉼표와 WHERE 조건은 해당 내부 절에 대한 상대 위치를 유지한다. 예를 들어 FROM이 4칸이면 바깥 괄호 9칸/내부 절 10칸, 그 내부 FROM의 괄호 15칸/내부 절 16칸이다.

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

최종 SQL은 실제 여는 괄호와 내부 절·연속 행·닫는 괄호·JOIN 조건을 함께 대조한다. `--normalize-layout`은 지원하는 FROM/JOIN 파생 쿼리와 JOIN/EXISTS 배치를 정리하며 전체 SQL 포매터는 아니다. 주석이 끼어 있는 절 분리 등 남은 진단은 최종 텍스트에서 직접 확인한다.

불필요한 WHERE/SELECT 서브쿼리·NOT EXISTS보다 JOIN을 우선하되 NULL·중복·카디널리티가 달라지는 치환은 하지 않는다. 함수→JOIN은 실제 함수 정의와 실행 의미를 먼저 확인한다. GET_CHGRAT 같은 기존 환율 함수와 원본 업무 상수는 보존하고 예시 환율을 새로 하드코딩하지 않는다.

UPDATE만 요청하면 요청한 UPDATE FROM/CROSS APPLY 형태를 완성해 준다. 실제 DB 변경 요청인 경우 정확한 연결·DB·키·트랜잭션·사후 값과 제외 행을 확인한다. 전달한 SQL을 실행한 것처럼 보고하지 않는다.

여러 결과를 반환하는 조회에서 헤더·그리드·차트의 기간·필터·JOIN 키·NULL 처리·집계 단위를 대조한다. UNION 분기와 합계/비율 계산도 실제 비교 대상과 같은 조건인지 확인한다. 중복 SQL이 길어진다는 이유만으로 임시 테이블을 도입하지 않으며, 기존 [필요성 기준](../../work-execution/references/preferences.md)을 따른다.
