# 저장 예시

아래는 가상 계약이다. 실제 키·자료형·상태문자·XML 경로·트랜잭션은 대상 원본과 동작하는 같은 역할의 SAVE를 따른다.

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

기존 채번 범위·순서·동시성을 지킨다. XML 행 인덱스는 영구 키의 근거가 될 수 없다. 생성한 키를 기록할 필요가 있으면 스칼라·스테이징 갱신을 원래 책임에 둔다.

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
