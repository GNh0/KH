# KH SQL 스타일

현재 SQL의 의미와 명시적 요구가 먼저다. 일반 정리는 별칭 정규화를 포함하고 “별칭 그대로/정렬만”은 유지한다. 생성·정리·최적화·비교·실행을 구분한다.

- 주 조회 대상 A, 다음 업무 역할 B/C/D, 같은 역할군 안의 여러 테이블 B1/B2처럼 쓴다. 파생 쿼리 내부는 T 계열로 스코프를 구분한다. 서로 다른 물리 테이블도 같은 업무 역할군일 수 있다. BA011T 또는 MAINCD만으로 E/F나 E1/E2를 고정하지 않는다.
- 키워드·식별자는 대상의 승인된 대문자 스타일을 따른다. 문자열·한글·주석은 바꾸지 않는다. 테이블 별칭 AS와 출력 컬럼 AS를 구분한다.
- SELECT/UPDATE SET/SP 파라미터는 해당 예시의 선행 쉼표를 따른다. SP 파라미터 기본값은 승인 템플릿과 실제 호출 계약에서 가져온다.
- JOIN을 FROM보다 들여쓰고 ON/같은 JOIN의 AND를 JOIN 끝 IN의 I 위치에 맞춘다. 파생 블록은 닫는 괄호, 별칭, 그 아래 ON 위치를 실제 예시대로 맞춘다. LEFT OUTER JOIN을 임의 축약하지 않는다.
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

ON과 같은 JOIN의 AND는 JOIN 끝 IN의 I 위치에 맞춘다. 파생 JOIN 예:

```sql
SELECT A.ORDNUM
     , B.LASTDT
FROM SA100T A
        LEFT OUTER JOIN (
            SELECT T.ORDNUM
                 , MAX(T.RECDT) AS LASTDT
            FROM SA210T T
            GROUP BY T.ORDNUM
        ) B
                     ON A.ORDNUM = B.ORDNUM
```

이 예시에서는 내부 SQL 12칸, 닫는 괄호 8칸, ON 21칸이다. 상대 위치를 설명하는 예시이며 업무 테이블이나 키 이름을 고정하지 않는다. 최종 SQL은 주변 실제 프로시저의 배치와 대조한다. `--normalize-layout`은 지원하는 JOIN/EXISTS 배치만 정리하며 전체 SQL 포매터가 아니다. 남은 진단은 최종 텍스트에서 직접 확인한다.

불필요한 WHERE/SELECT 서브쿼리·NOT EXISTS보다 JOIN을 우선하되 NULL·중복·카디널리티가 달라지는 치환은 하지 않는다. 함수→JOIN은 실제 함수 정의와 실행 의미를 먼저 확인한다. GET_CHGRAT 같은 기존 환율 함수와 원본 업무 상수는 보존하고 예시 환율을 새로 하드코딩하지 않는다.

UPDATE만 요청하면 요청한 UPDATE FROM/CROSS APPLY 형태를 완성해 준다. 실제 DB 변경 요청인 경우 정확한 연결·DB·키·트랜잭션·사후 값과 제외 행을 확인한다. 전달한 SQL을 실행한 것처럼 보고하지 않는다.
