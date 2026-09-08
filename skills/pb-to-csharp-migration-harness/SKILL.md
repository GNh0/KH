---
name: pb-to-csharp-migration-harness
description: Analyze PowerBuilder/PBL/DataWindow sources or migrate them to C# WinForms, Designer code, and SQL Server procedures with source-grounded behavior mapping.
---

# PB to C# migration

정확한 PBL/object, 상속 부모, 연결 DataWindow, 실제 이벤트·SQL·보고서 관계를 먼저 읽는다. 제공 export만 있으면 그 증명 범위를 사용하고 읽지 않은 전체 PBL 분석으로 확대하지 않는다.

- 추출이나 라이브러리 오류에는 [ORCA 실행](references/orca.md)을 읽는다.
- UI·DataWindow 매핑은 [DataWindow와 화면](references/datawindow.md)을 읽는다. 그리드 기본값과 편집 속성은 [사용자 HTML 기준](../csharp-designer-style-harness/references/grid-layout.md)을 적용한다.
- 이관 계획과 생성 결과는 [이관 검증](references/validation.md)을 사용한다.
- SQL 작업에는 [SELECT/SAVE 연결](references/sql.md)과 SQL 스킬의 스타일을 사용한다.
- 기존 사용자 스타일은 [범위별 프로필](references/default-profile.json)을 적용한다. 새 프로필 추출 요청 때만 KH 유지보수 지침을 읽는다.
- C#을 생성·수정할 때는 [사용자 작성 방식](../csharp-designer-style-harness/references/coding-style.md)도 읽는다. 참조 화면의 누락이나 미완성 구현으로 이미 합의한 C# 규칙을 완화하지 않는다.

원시 키 구성값과 표시 키를 구분하고 특정 ORD/PUR/REC 이름이나 구성 개수를 고정하지 않는다. 입력/조회/보호/저장/출력 흐름을 실제 소스에서 연결한다. 단순 SELECT 추출에 전체 이관 문서나 C# 생성을 강요하지 않는다.

이관 대상에 사용자 컨트롤이 없으면 사용 가능한 DevExpress 또는 기본 컨트롤로 동작을 보존한다. 검증한 정적 범위, 실행 결과, 미확인 화면·DB 동작을 구분해 전달한다.

사용 가능한 적절한 사용자 컨트롤이 있으면 해당 컨트롤과 초기화 기본값을 우선한다. KoneLib에 한정하지 않고 [사용자 컨트롤 선택·기본 초기화](../csharp-designer-style-harness/references/user-controls.md)를 적용한다. PB 속성이나 익숙한 DevExpress 옵션을 근거 없이 덧붙여 사용자 컨트롤 기본값을 덮어쓰지 않는다.
