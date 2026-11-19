# 저장 예시

아래는 가상 계약이다. 실제 키·자료형·상태문자·XML 경로·트랜잭션은 대상 원본과 동작하는 같은 역할의 SAVE를 따른다.

## SAVE 고정 규칙

사용자가 따로 말하지 않아도 SAVE를 새로 쓰거나 기존 SAVE의 로직을 고칠 때 지킨다. 원본에 아래와 다른 형태가 있으면 그것도 고친다. 서식 정리만 맡았으면 바꾸지 않고 해당 위치를 보고한다.

| 금지 | 대신 |
| --- | --- |
| `WITH (UPDLOCK, HOLDLOCK)` 등 잠금 힌트(원본·참고 SP에 있던 것 포함) | 힌트 없이 조회한다. 사용자가 이번 작업에서 명시 요청한 힌트만 남긴다. |
| `IF @WORKTYPE = 'DELETE' BEGIN … COMMIT … RETURN END` 뒤에 나머지 모드를 조건 없이 이어 쓰기, 여러 곳의 COMMIT | 아래 골격의 IF/ELSE IF 분기, 끝에서 COMMIT 한 번 |
| `@NEWCOUNT`·`@MODCOUNT`·`@DELCOUNT` 같은 건수 변수, `IF @@ROWCOUNT <> @변수`, `IF @CNT > 0` | 쓰기 전 `IF EXISTS` / `IF NOT EXISTS` 검증(전체 키, LEFT OUTER JOIN … IS NULL, 중복 키 GROUP BY HAVING) |
| `SELECT @LASTSEQ = ISNULL(MAX(…), 0)` 뒤 `@LASTSEQ + RN`, 스테이징에 순번을 먼저 `UPDATE` | INSERT 안에서 `ISNULL(C.SEQ, 0) + ROW_NUMBER() OVER (ORDER BY …)`와 파생 MAX JOIN. 뒤 단계는 쓴 대상 행을 업무 키로 JOIN한다. |
| 한 번 대입하고 한 번 읽는 변수, 선언만 하거나 대입만 하고 읽지 않는 변수, 헤더 테이블 변수 값을 복사한 변수 | 그 자리에서 식을 쓰거나 테이블 변수·대상 행을 JOIN해 읽는다. |
| `INSERT INTO @TMPISSUE … SELECT … FROM 실제 테이블`처럼 중간 결과를 테이블 변수·임시 테이블에 담았다가 다시 읽기 | 최종 INSERT/UPDATE/DELETE 안의 JOIN·파생 테이블로 바로 계산한다. 테이블 변수는 XML 파싱(`FROM OPENXML`)에만 쓴다. |

`@변수`는 최소화한다. 남기는 변수는 T-SQL이 변수를 요구하는 경우뿐이다.

| 남기는 변수 | 이유 |
| --- | --- |
| `@DOC_ID` | `SP_XML_PREPAREDOCUMENT`의 OUTPUT 핸들 |
| `@NEWSEQ`, `@OUTSEQ` | 채번 프로시저의 OUTPUT 인자 |
| `@PURDT` 같은 채번 기준일 | EXEC 인자에는 식·하위 쿼리를 쓸 수 없다 |
| `@PURNUM` 같은 문서번호 | NEW에서 생성해 여러 문장에서 쓴다 |
| `@STARTTRANCOUNT` | 시작 시점의 `@@TRANCOUNT`를 저장한다 |

Codex 산출물 폴더를 거치지 않은 근호 작성 SAVE(`sp_MA000100_SAVE`의 `@REQNUM`·`@REQDT`·`@NEWSEQ`, `sp_QC100100_SAVE`의 `@QCNUM`)도 이 범위다. 그 밖의 헤더 값은 `@TMP_HEADER`를 JOIN해 읽는다.

```sql
IF @STARTTRANCOUNT = 0
BEGIN
    BEGIN TRANSACTION
END

IF @WORKTYPE IN ('EDIT', 'DELETE')
BEGIN
    IF EXISTS (
               SELECT 1
               FROM @TMP_HEADER A
                       LEFT OUTER JOIN DOCUMENT_HEADER B
                                    ON B.COMPANY_ID = @COMPANY_ID
                                    AND A.DOCUMENT_NO = B.DOCUMENT_NO
               WHERE B.DOCUMENT_NO IS NULL
              )
    BEGIN
        RAISERROR('The document does not exist.', 16, 1);
        RETURN;
    END
END

IF @WORKTYPE = 'DELETE'
BEGIN
    DELETE A
    FROM DOCUMENT_DETAIL A
            INNER JOIN @TMP_HEADER B
                    ON A.DOCUMENT_NO = B.DOCUMENT_NO
    WHERE A.COMPANY_ID = @COMPANY_ID

    DELETE A
    FROM DOCUMENT_HEADER A
            INNER JOIN @TMP_HEADER B
                    ON A.DOCUMENT_NO = B.DOCUMENT_NO
    WHERE A.COMPANY_ID = @COMPANY_ID
END
ELSE IF @WORKTYPE IN ('NEW', 'EDIT')
BEGIN
    -- NEW/EDIT 공통 상세 XML 파싱·검증

    IF @WORKTYPE = 'NEW'
    BEGIN
        EXEC SP_DOCUMENT_KEYCODE @COMPANY_ID, @DOCUMENT_DT, @NEWSEQ OUTPUT
        SET @DOCUMENT_NO = @DOCUMENT_DT + '-' + CONVERT(VARCHAR(10), @NEWSEQ)

        -- 헤더 INSERT
    END
    ELSE IF @WORKTYPE = 'EDIT'
    BEGIN
        IF EXISTS (
                   SELECT 1
                   FROM @TMP_DETAIL A
                           LEFT OUTER JOIN DOCUMENT_DETAIL B
                                        ON B.COMPANY_ID = @COMPANY_ID
                                        AND B.DOCUMENT_NO = @DOCUMENT_NO
                                        AND A.LINE_NO = B.LINE_NO
                   WHERE A.CHANGE_STATE IN ('MOD', 'DEL')
                     AND B.LINE_NO IS NULL
                  )
        BEGIN
            RAISERROR('A modified or deleted line does not exist.', 16, 1);
            RETURN;
        END

        -- 헤더 UPDATE, 상세 MOD UPDATE / DEL DELETE
    END

    INSERT INTO DOCUMENT_DETAIL
    (
           COMPANY_ID  , DOCUMENT_NO  , LINE_NO                                                     , ITEM_CODE
    )
    SELECT @COMPANY_ID , @DOCUMENT_NO , ISNULL(C.LINE_NO, 0) + ROW_NUMBER() OVER (ORDER BY A.SEQ) , A.ITEM_CODE
    FROM @TMP_DETAIL A
            LEFT OUTER JOIN (
                             SELECT T.COMPANY_ID
                                  , T.DOCUMENT_NO
                                  , MAX(T.LINE_NO) AS LINE_NO
                             FROM DOCUMENT_DETAIL T
                             WHERE T.COMPANY_ID = @COMPANY_ID
                               AND T.DOCUMENT_NO = @DOCUMENT_NO
                             GROUP BY T.COMPANY_ID, T.DOCUMENT_NO
                            ) C
                            ON C.COMPANY_ID = @COMPANY_ID
                            AND C.DOCUMENT_NO = @DOCUMENT_NO
    WHERE A.CHANGE_STATE = 'NEW'

    SET @OUTPUT = @DOCUMENT_NO
END

IF @STARTTRANCOUNT = 0
BEGIN
    COMMIT TRANSACTION
END
```

검증 실패는 분기 안에서 `RAISERROR … RETURN`으로 끝내고 CATCH가 롤백한다. 쓰기 뒤에 건수를 다시 세지 않는다. 같은 업무의 모드 조건을 준비·검증·쓰기마다 반복하지 않는다. 검사기는 잠금 힌트(`locking_hint`), 쓰기 후 RETURN하는 모드 블록(`save_mode_early_exit`), 여러 COMMIT(`save_multiple_commit`), 건수 변수(`count_variable`, `rowcount_count_variable`), MAX 순번 변수(`scalar_sequence_base`), 순번 스테이징 UPDATE(`staging_sequence_update`), 중간 결과 테이블(`intermediate_table`), 읽지 않는 변수(`unused_variable`), 한 번만 쓰는 변수(`single_use_variable`)를 원본에 있던 것까지 오류로 보고한다. 참고 SP에 같은 형태가 있어도 근거가 아니다.

## Parsed rows and NEW

XML은 기존 처리 범위에서 한 번 파싱한다. 필요한 열·타입을 정의하고 파싱한 행을 INSERT SELECT에 직접 쓴다. 할당한 문서 핸들은 정상·예외 경로에서 해제한다. 정상 해제 후 핸들을 비워 뒤의 오류가 이중 해제를 유발하지 않게 한다.

```sql
INSERT INTO CONTACTS
(
       COMPANY_ID  , CUSTOMER_ID  , CONTACT_ID   , CONTACT_NAME
)
SELECT @COMPANY_ID , @CUSTOMER_ID , A.CONTACT_ID , A.CONTACT_NAME
FROM @TMP_CONTACT A
WHERE A.CHANGE_STATE = 'NEW'
```

기존 채번 범위·순서를 지킨다. 상세 순번은 [고정 규칙](#save-고정-규칙)의 파생 MAX + ROW_NUMBER로 매긴다. XML 행 인덱스는 영구 키의 근거가 될 수 없다. 생성한 상세 키가 뒤 단계에 필요하면 쓴 대상 행을 업무 키로 JOIN해 읽는다.

## Operation ownership

| 업무 | 분기 위치 |
| --- | --- |
| 신규 모드에만 필요한 검증·헤더·상세 쓰기 | 같은 신규 분기에서 실행 순서대로 처리 |
| 이름 변경에만 필요한 수정 | 해당 변경 분기 안에서 처리 |
| 두 모드가 같은 결과를 반환하거나 같은 해제를 수행 | 자료 의존성이 같은 공통 위치에서 한 번 실행 |

같은 모드를 준비·검증·쓰기마다 다시 검사하지 않는다. 기존 호출자가 요구하는 공통 XML 전처리·검증·트랜잭션의 시작/종료·오류 처리는 해당 범위에 둔다. 검증을 바꾸면 [실제 입력과 수량 검증 예시](validation-patterns.md)를 대조한다.

## MOD and DEL

한 고객의 선택된 연락처를 수정·삭제하는 경우다. 회사·고객·연락처가 전체 키다.

```sql
UPDATE A
SET CONTACT_NAME = B.CONTACT_NAME
  , MODIFIED_AT = GETDATE()
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

## Multiple-master-delete

여러 문서의 삭제 키를 받은 경우 선택한 전체 키 집합을 끝까지 유지한다. 삭제 가능 조건을 확인하고 원래 트랜잭션에서 연관 상세를 먼저, 헤더를 다음에 삭제한다.

```sql
DELETE A
FROM DOCUMENT_DETAIL A
        INNER JOIN @TMP_DOCUMENT B
                ON A.COMPANY_ID = B.COMPANY_ID
                AND A.DOCUMENT_NO = B.DOCUMENT_NO
WHERE A.COMPANY_ID = @COMPANY_ID
  AND B.CHANGE_STATE = 'DEL'
```

같은 키 조건으로 해당 헤더를 처리한다. 선택 2건, 미선택 1건, 다른 회사의 동일 번호로 대상·제외 결과를 확인한다.
