---
name: sql-formatting
description: Create, change, format or review SQL/T-SQL query and procedure artifacts using the user's style (SQL 정리·작성, 쿼리, SP·프로시저 조회/저장 수정).
---

# SQL 작성·정리

| 요청 | 적용 |
| --- | --- |
| 정렬·정리 | [SQL 서식](references/style.md). “별칭 그대로/정렬만”이면 별칭 유지, 일반 “정리”면 [별칭 역할표](references/style.md#별칭-역할)를 먼저 만든다. 주 대상은 A, 이미 글자를 받은 테이블과 같은 업무면 그 글자에 번호(A1·B1·C1…), 새 업무면 다음 글자를 쓴다. 완성 SQL 또는 요청한 교체 블록을 반환한다. |
| SELECT 작성 | 결과 한 행의 단위, 포함·제외 조건, 표시용 JOIN과 필수 JOIN을 확인한다. [조회 예시](references/select-patterns.md) |
| SELECT/SAVE 프로시저 | [작성자와 참고 SP](references/procedure-authorship.md)를 정하고 실제 호출부·같은 역할 참고 SP 전체와 [프로시저 계약](references/procedure-contracts.md)을 대조한다. |
| SAVE 작성 | 호출 모드와 선택 키·XML 행 상태를 맞춘다. [저장 예시](references/save-patterns.md), 업무 검증 변경 시 [검증 예시](references/validation-patterns.md) |

- 원래 JOIN 종류·순서, 조건, 출력 형식·순서, 리터럴, 한글, 주석을 보존한다. 함수 → JOIN 변경은 실제 정의·NULL·중복·건수·성능을 확인한다.
- 조회·합산·제외는 전체 키와 행 수를 지키는 JOIN을 우선한다. 수정·검토 요청에서 WHERE의 EXISTS·IN 서브쿼리는 [EXISTS → JOIN](references/select-patterns.md#exists--join)대로 JOIN으로 바꾼다. 상관 조건의 `OR`는 갈래별 파생으로 나눈다. SAVE의 필수 `IF EXISTS`, 채번·출력 변수는 유지한다.
- SAVE를 작성·수정할 때는 [SAVE 고정 규칙](references/save-patterns.md#save-고정-규칙)을 지킨다. **잠금 힌트(UPDLOCK·HOLDLOCK 등)는 쓰지 않는다**. 원본·참고 SP에 있어도 사용자가 이번 작업에서 명시 요청하지 않았으면 제거한다. WORKTYPE은 `IF 'DELETE' … ELSE IF IN ('NEW','EDIT')`로 나누고 COMMIT은 끝에서 한 번 한다. 건수 변수·`@@ROWCOUNT` 비교·MAX 순번 변수 대신 `IF EXISTS` 검증과 파생 MAX + ROW_NUMBER를 쓴다. XML 파싱 외의 중간 결과를 테이블 변수에 담았다가 다시 읽지 않고, 순번을 스테이징에 먼저 UPDATE하지 않는다. 최종 INSERT/UPDATE 안의 JOIN·파생으로 계산한다. 행 단위 처리(WHILE·커서·`SELECT TOP 1 @변수`)를 남발하지 않고 배분·INSERT는 [집합 기반 한 문장](references/save-patterns.md#배분-insert)으로 쓴다. NEW/EDIT 공통 처리는 분기마다 복사하지 않고 공통 위치에 한 번 둔다. `@변수`는 최소화한다. 문법상 필요한 경우(OUTPUT 인자, XML 핸들, EXEC·RAISERROR 인자, `@@TRANCOUNT` 저장, 여러 문장이 쓰는 생성 번호)만 둔다. 원본 보존은 이 규칙보다 우선하지 않는다. 서식 정리만 요청받았으면 바꾸지 않고 보고한다.
- 저장·조회 값의 **신규·변경 대체값은 사용자 명시 요청이 필요하다**. 산술식의 `ISNULL(..., 0)`도 해당한다. 입력 컨트롤 초기값은 해당 초기화에서만 적용한다.
- 기존 SP는 쓰기·실행 전에 원본↔초안, 저장 후 원본↔저장본을 비교한다. 새 모드·쓰기·호출 위치·결과 형식마다 실제 요구와 호출 근거를 확인한다. 같은 모드의 결과는 한 분기 안에서 호출 순서대로 반환한다. [변경 검사](references/checks.md)
- 화면 계약 변경 시 `python -B <KH>/scripts/kh_check.py screen-contract <caller.cs> <SELECT.sql> <SAVE.sql> --designer <Designer.cs>`로 최종 양쪽을 맞춘다. 입력이 부족하면 빠진 SP·모드·결과를 실제 소스로 검증한다.

호스트가 파일 작업 범위를 발급하면 [apply](../work-execution/references/application.md)에 실제 파일과 역할을 등록한다. [작성 전·후 대조](../work-execution/references/source-style-cycle.md)는 해당 원본으로 수행한다. 대화에 붙인 SQL은 직접 정리한다. 비교·설명은 제공 자료로 답하고 DB 실행은 사용자가 지정한 범위를 따른다.

작업용 파일은 [임시 경로](../work-execution/references/workspace-files.md)에 둔다. 메인이 직접 작업하며 위임이 필요한 경우 [역할별 인계](../work-execution/references/delegation.md)를 따른다.
