---
name: sql-formatting
description: Generate, edit, or format SQL/T-SQL using the scoped KH layout while preserving query behavior and explicit alias-preservation requests.
---

# SQL formatting

SQL 생성·수정·정리는 [사용자 SQL 스타일](references/style.md)을 적용한다. 파생 FROM/JOIN은 여는 괄호에 닫는 괄호를 맞추고 내부 절은 한 칸 오른쪽, 파생 JOIN의 ON/AND는 괄호와 같은 열에 둔다. 일반 테이블 JOIN의 ON/AND는 JOIN의 I 열이다. 이 사용자의 일반적인 “정리”에는 업무 역할별 별칭 정규화가 포함된다. “별칭 그대로”, “정렬만”이면 원래 별칭을 유지한다. 역할은 테이블명/MAINCD만으로 결정하지 않는다.

제공된 SQL만 정리하는 요청은 완성된 SQL을 바로 전달한다. 단순 비교·이유 질문에는 재작성하거나 DB에 접속하지 않는다. 의미·JOIN 종류/순서·조건·리터럴·한글·기존 주석과 출력 열을 보존한다. SQL 생성과 DB 실행은 서로 다른 요청 범위다.

정리 의미 비교나 복잡한 중첩 JOIN 검사가 도움이 될 때만 [검사기 사용법](references/checks.md)을 읽는다. 함수→JOIN 등 의미가 달라질 수 있는 변경은 실제 정의·NULL·중복·행 수·성능을 확인한다. 검사기는 DB 실행을 대신하지 않는다.

불필요한 CTE·중간 테이블·WHERE/SELECT 서브쿼리를 습관적으로 추가하지 않는다. [선호와 예외](../work-execution/references/preferences.md)를 적용하되 의미가 바뀌는 기계적 JOIN 치환은 하지 않는다. 요청한 전체 SQL 또는 정확한 교체 블록으로 답한다.
