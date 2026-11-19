---
name: sql-formatting
description: Create, change, format or review SQL/T-SQL query and procedure artifacts using the user's style (SQL 정리·작성, 쿼리, SP·프로시저 조회/저장 수정).
---

# SQL 작성·정리

| 요청 | 적용 |
| --- | --- |
| 정렬·정리 | [SQL 서식](references/style.md). “별칭 그대로/정렬만”이면 별칭 유지, 일반 “정리”면 업무 역할별로 정돈한다. 완성 SQL 또는 요청한 교체 블록을 반환한다. |
| SELECT 작성 | 결과 한 행의 단위, 포함·제외 조건, 표시용 JOIN과 필수 JOIN을 확인한다. [조회 예시](references/select-patterns.md) |
| SELECT/SAVE 프로시저 | [작성자와 참고 SP](references/procedure-authorship.md)를 정하고 실제 호출부·같은 역할 참고 SP 전체와 [프로시저 계약](references/procedure-contracts.md)을 대조한다. |
| SAVE 작성 | 호출 모드와 선택 키·XML 행 상태를 맞춘다. [저장 예시](references/save-patterns.md), 업무 검증 변경 시 [검증 예시](references/validation-patterns.md) |

- 원래 JOIN 종류·순서, 조건, 출력 형식·순서, 리터럴, 한글, 주석을 보존한다. 함수 → JOIN 변경은 실제 정의·NULL·중복·건수·성능을 확인한다.
- 조회·합산·제외는 전체 키와 행 수를 지키는 JOIN을 우선한다. SAVE의 필수 `IF EXISTS`, 채번·출력 변수는 유지한다.
- 저장·조회 값의 **신규·변경 대체값은 사용자 명시 요청이 필요하다**. 산술식의 `ISNULL(..., 0)`도 해당한다. 입력 컨트롤 초기값은 해당 초기화에서만 적용한다.
- 기존 SP는 쓰기·실행 전에 원본↔초안, 저장 후 원본↔저장본을 비교한다. 새 모드·쓰기·호출 위치·결과 형식마다 실제 요구와 호출 근거를 확인한다. 같은 모드의 결과는 한 분기 안에서 호출 순서대로 반환한다. [변경 검사](references/checks.md)
- 화면 계약 변경 시 `python -B <KH>/scripts/kh_check.py screen-contract <caller.cs> <SELECT.sql> <SAVE.sql> --designer <Designer.cs>`로 최종 양쪽을 맞춘다. 입력이 부족하면 빠진 SP·모드·결과를 실제 소스로 검증한다.

호스트가 파일 작업 범위를 발급하면 [apply](../work-execution/references/application.md)에 실제 파일과 역할을 등록한다. [작성 전·후 대조](../work-execution/references/source-style-cycle.md)는 해당 원본으로 수행한다. 대화에 붙인 SQL은 직접 정리한다. 비교·설명은 제공 자료로 답하고 DB 실행은 사용자가 지정한 범위를 따른다.

작업용 파일은 [임시 경로](../work-execution/references/workspace-files.md)에 둔다. 메인이 직접 작업하며 위임이 필요한 경우 [역할별 인계](../work-execution/references/delegation.md)를 따른다.
