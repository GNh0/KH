# SQL 서식

## SQL layout

- 별칭은 [별칭 역할](#별칭-역할) 순서로 정한다. 파생 쿼리 내부는 T 계열을 쓴다. 테이블명·MAINCD만으로 E/F를 정하지 않는다. “정렬만/별칭 그대로”는 원래 별칭을 보존한다.
- 리터럴·주석 밖의 SQL은 **모두 대문자**로 쓴다. 키워드·함수뿐 아니라 테이블·열·별칭·출력 열 이름(`AS` 뒤)·사용자 함수·프로시저·변수 이름도 포함한다(예: `DBO.F_CODE_NAME`). 출력 열 이름이나 개체 이름의 대소문자가 바뀐다는 이유로 원래 표기를 남기지 않는다. 문자열 리터럴, 주석, `[...]`·`"..."`로 감싼 식별자 안의 표기만 원문을 유지한다. `identifiers_not_uppercase`가 남으면 고친다.
- 선행 쉼표 표기를 따른다. SELECT 목록, UPDATE SET, SP 인자 순서와 기본값을 맞춘다. 별칭 AS와 출력 열 AS를 구별한다.
- 일반 JOIN의 ON과 그 조건의 AND는 JOIN의 I 열에 맞춘다. 파생 FROM/JOIN은 여는 괄호와 닫는 괄호를 맞추고 안쪽 절은 한 칸 더 들인다. 파생 JOIN의 ON·AND·OR는 여는 괄호 열에 둔다. 중첩·UNION은 각 괄호를 기준으로 한다.
- EXISTS 괄호는 같은 열, 내부 SQL은 다음 줄에서 한 칸 더 들인다. 짧은 GROUP BY·ORDER BY는 한 줄, CASE 괄호는 해당 작성 예시와 맞춘다. BETWEEN의 AND는 해당 식 안에 둔다.
- INSERT 열과 SELECT/VALUES 값은 순서·줄 그룹·실제 시작 열을 대응시킨다. 같은 순번의 열과 값은 같은 시작 위치에 두고, 각 칸은 그 칸의 열·값 중 긴 쪽에 맞춰 공백을 둔다. **30자 이상인 긴 값(식·CASE·ROW_NUMBER 등)이 그 줄의 마지막 항목이 아니면, 그 값부터 다음 줄로 넘긴다.** INSERT 열 목록도 같은 위치에서 줄을 넘긴다. 긴 값 하나에 맞추려고 다른 줄의 열을 수십 칸씩 띄우지 않는다([INSERT 열 대응 예시](#insert-열-대응-예시)). UPDATE SET은 세로 목록으로 쓴다.
- JOIN 종류·순서·조건, 출력 타입·필드, 리터럴·한글·기존 주석을 보존한다. 주석 처리 요청은 원문을 남긴다. 필요한 JOIN·IF EXISTS·업무 함수와 상수는 실제 의미를 지킨다.
- JOIN으로 변경할 때는 전체 키·NULL·중복·집계 단위, 함수 원본·실행 의미를 확인한다. 다중 결과는 각 결과의 기간·필터·집계 키·UNION·비율을 맞춘다.
- 요청이 UPDATE 하나면 해당 UPDATE FROM/CROSS APPLY를 완성한다. DB 변경은 지정한 연결·DB·키, 트랜잭션과 변경/제외 행을 확인한다. 중간 테이블은 [필요성 기준](../../work-execution/references/preferences.md)을 따른다.

## 별칭 역할

일반 “정리”에서 별칭을 바꾸기 전에 테이블마다 `별칭 | 테이블 | 업무 역할 | 연결 키`를 먼저 적는다. 별칭은 JOIN 순서나 테이블명 첫 글자가 아니라 이 역할로 정한다.

모든 테이블(FROM·일반 JOIN·파생 JOIN)에 같은 규칙 하나를 적용한다. FROM의 주 대상은 처음 나오므로 항상 **A**다.

- **이미 글자를 받은 테이블과 같은 업무면 그 글자에 번호를 붙인다.** 그 테이블 행의 기준·표준·설정·승인 값을 더하는 보조 테이블, 헤더의 상세, 같은 원천을 조건만 달리 나눈 파생이 해당한다. A의 것이면 A1·A2, B의 것이면 B1·B2, C의 것이면 C1처럼 어느 글자에도 똑같이 적용한다.
- **새 업무면 다음 글자**(B, C, D…)를 처음 나오는 순서대로 쓴다. 앞 테이블의 키로 붙어도 업무가 다르면 새 글자다.
- 같은 업무 테이블이 기준 테이블보다 먼저 나와도 글자는 업무로 정한다. JOIN 순서는 바꾸지 않는다.

| 원래 | 별칭 | 근거 |
| --- | --- | --- |
| `XP110T` 공정계획 | `A` | 주 대상 |
| `XP100T` 표준시간 | `A1` | A의 공정·품목 표준값(같은 업무). `B`가 아니다 |
| `XS100T` 수주 헤더 | `B` | 새 업무 |
| `MS011T` 공정명 코드 | `C` | 새 업무 |
| `XS110T` 수주 상세 | `B1` | B의 상세(같은 업무). 먼저 나온 C와 무관하게 B 계열 |
| `XP210T` 실적 집계(PARTCD <> 'Y') | `D` | 새 업무 |
| `XP210T` 실적 집계(PARTCD = 'Y') | `D1` | D와 같은 원천의 조건별 집계(같은 업무) |
| `SY905T` 도면 파일 | `E` | 새 업무 |

업무가 같은지는 테이블 설명, 실제 연결 키, 사용하는 열로 판단한다. 근거가 부족하면 역할표에 `미확인`과 이유를 적고 사용자에게 확인한다. 인계에는 원래→새 별칭과 역할 근거를 함께 적는다.

```sql
SELECT A.GONUM
     , A1.STDTIME
     , B.HULLNO
     , B1.ITEMNM
     , C.SUBNM3
     , D.PRODQTY
FROM XP110T A
        LEFT OUTER JOIN XP100T A1
                     ON A.ORGDIV = A1.ORGDIV
                     AND A.PROCCD = A1.PROCCD
                     AND A.ITEMCD = A1.ITEMCD
        LEFT OUTER JOIN XS100T B
                     ON A.ORGDIV = B.ORGDIV
                     AND A.ORDNUM = B.ORDNUM
        LEFT OUTER JOIN MS011T C
                     ON A.PROCCD = C.SUBCD
        LEFT OUTER JOIN XS110T B1
                     ON A.ORGDIV = B1.ORGDIV
                     AND A.ORDNUM = B1.ORDNUM
                     AND A.ORDSEQ = B1.ORDSEQ
        LEFT OUTER JOIN (
                         SELECT T.ORDNUM
                              , SUM(T.PRODQTY) AS PRODQTY
                         FROM XP210T T
                         GROUP BY T.ORDNUM
                        ) D
                        ON A.ORDNUM = D.ORDNUM
```

## JOIN 예시

```sql
SELECT A.ITEMCD
     , B.ITEMNM
FROM XM210T A
        LEFT OUTER JOIN MS030T B
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

긴 값은 줄 끝에 둔다. 아래에서 `ISNULL(C.SEQ, 0) + ROW_NUMBER() …`는 그 줄의 마지막 항목이고, 다음 열 `ITEMCD`는 다음 줄에서 시작한다. 긴 값이 줄 중간에 오는 형태는 쓰지 않는다.

```sql
    INSERT INTO TARGET
    (
           ORGDIV   , DOCNO  , SEQ
         , ITEMCD   , QTY    , UNITWGT
         , TOTWGT
    )
    SELECT @ORGDIV  , @DOCNO , ISNULL(C.SEQ, 0) + ROW_NUMBER() OVER (ORDER BY A.SEQ)
         , A.ITEMCD , A.QTY  , A.UNITWGT
         , A.QTY * A.UNITWGT * (CASE WHEN A.WGTUNIT = 'G' THEN 0.001 ELSE 1 END)
    FROM SOURCE A
```

쓰지 않는 형태: 긴 값이 줄 중간에 있어서 다른 줄의 같은 칸이 수십 칸씩 벌어진다.

```sql
    SELECT @ORGDIV , @DOCNO    , ISNULL(C.SEQ, 0) + ROW_NUMBER() OVER (ORDER BY A.SEQ) , A.ITEMCD
         , A.QTY   , A.UNITWGT , A.QTY * A.UNITWGT                                      , GETDATE()
```

긴 값 때문에 이미 벌어진 간격은 위처럼 줄을 넘겨 없앤다. 여러 줄 표현·주석이 있으면 최종 문자열에서 열/값의 의미와 시작 열을 직접 확인한다.
