---
name: csharp-designer-style-harness
description: Develop or review WinForms/DevExpress source, Designer layouts and XtraReports against actual project contracts (C# 화면·폼·그리드·컨트롤·Designer·보고서 수정).
---

# C# 화면 수정

사용자가 지정한 **비교 프로젝트의 같은 역할 프로그램**에서 작성 방식을 확인한다. 실제 대상의 호출부·컨트롤·라이브러리에서 동작을 확인한다. WinForms와 다른 구조에서는 대상 프로젝트의 방식을 따른다.

| 바꾸는 부분 | 먼저 볼 내용 |
| --- | --- |
| 메서드·이벤트 | [작성 규칙](references/coding-style.md). 실제 호출자와 피호출자의 전체 메서드에서 인자, 반환, 초기화, 취소·오류 처리를 확인한다. |
| 컨트롤·Repository·ColumnEdit | [컨트롤 기본값](references/user-controls.md). 코드비하인드에서 만드는 경우도 생성자·공통 초기화·나중 대입을 확인한다. |
| Designer·그리드 | [Designer](references/designer.md), 그리드 변경 시 [그리드](references/grid-layout.md). 지정한 멤버만 수정하고 기존 속성·이벤트를 보존한다. |
| 조회·저장·삭제 | [데이터 흐름](references/data-flow.md). 선택 키 → 행 상태 → XML → SP → 결과표·성공 후 재조회까지 따라간다. |
| 출력·주기적 재조회 | 변경하는 쪽의 [보고서](references/reports.md) 또는 [모니터링](references/screen-behavior.md)을 적용한다. |

라벨·한 줄 입력의 높이는 같은 화면의 같은 역할 컨트롤과 대조한다. 폰트·정렬·버튼은 실제 초기화 값을 유지한다. 표시 형식 요청은 해당 표시 속성에서 해결한다. 조회·저장·출력은 각각 해당 비교 프로그램을 확인한다.

외부 헬퍼에 그리드를 넘기는 호출을 추가·변경하면 인자의 실제 타입, 헬퍼를 소유한 타입과 호출된 오버로드를 확인한다. 본문과 위임 호출에서 그리드·열·Repository 속성을 바꾸면 그리드 작업으로 등록한다. 값 조회만 수행하면 기존 역할을 유지한다. 구현을 확인할 수 없으면 호출 위치와 필요한 메서드를 미확인 근거로 남긴다.

호스트가 파일 작업 범위를 발급하면 [apply](../work-execution/references/application.md)에 실제 대상과 역할을 등록한다. 해당 필수 범위와 현재 비교 소스를 읽고 [작성 전·후 대조](../work-execution/references/source-style-cycle.md)를 수행한다. 붙여넣은 조각은 요청 범위에서 고치고 확인할 수 없는 프로젝트 의존성만 밝힌다.

PROJECT_A의 조회·저장 컨트롤과 XML을 다룰 때는 [ExampleLib 계약표](references/project-a-framework.md)를 사용한다. 다른 프로젝트에서는 그 프로젝트의 구현을 확인한다.

화면과 SP가 함께 동작하면 두 쪽의 최종 파일로 `python -B <KH>/scripts/kh_check.py screen-contract <caller.cs> <SELECT.sql> <SAVE.sql> --designer <Designer.cs>`를 실행한다. 누락·동적 입력은 실제 호출부와 결과 바인딩에서 대조한다. 개별 소스 검사는 [실행 예](references/checks.md)와 [비교 프로필](references/default-profile.json)을 참고한다.

기본 담당자는 메인 에이전트다. 필요 시 [위임 기준](../work-execution/references/delegation.md), 임시 파일은 [작업 경로](../work-execution/references/workspace-files.md), 중간 테이블·LINQ·빌드는 [사용자 기준](../work-execution/references/preferences.md)을 따른다.
