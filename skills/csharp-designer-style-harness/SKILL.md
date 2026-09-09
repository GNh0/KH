---
name: csharp-designer-style-harness
description: Generate, modify, or review WinForms/DevExpress/KoneLib C# and Designer code against the exact project patterns, bindings, and save contracts.
---

# C# and Designer

현재 파일, 사용자 수정, 지정한 비교 화면과 실제 프레임워크 호출 경로를 읽는다. 이 스킬의 WinForms 규칙을 MAUI/PDA나 다른 C# 프로젝트에 일괄 적용하지 않는다.

컨트롤 작업에서는 현재 프로젝트에 사용 가능한 적절한 사용자 컨트롤을 우선 선택한다. KoneLib에 한정하지 않는다. [사용자 컨트롤 기준](references/user-controls.md)에 따라 생성자·초기화 helper·상속의 기본 속성을 읽고 유지하며, 화면의 요청 동작에 필요한 속성만 추가한다. 모델이 임의로 기본 속성을 보충하거나 덮어쓰지 않는다. 날짜 컨트롤 이름은 ymd와 실제 필드명을 따른다.

- C# 코드 작성·수정은 [사용자 작성 방식](references/coding-style.md)을 읽는다. 이미 합의한 규칙과 다른 참조 소스는 놓친 부분일 수 있으므로 그 차이로 기존 규칙을 완화하지 않는다.
- UI·Designer 작업은 [화면 스타일](references/designer.md)을 읽는다. 그리드 작업은 [HTML 기본 속성](references/grid-layout.md)도 읽는다.
- 조회/저장/업로드/행 선택 작업은 [데이터와 이벤트 계약](references/data-flow.md)을 읽는다.
- 모니터링·여러 UserControl·반복 조회·그리드 재바인딩은 [화면 동작 계약](references/screen-behavior.md)을 읽는다. 사용자 수정값을 다시 덮는 이벤트와 실제 조회 시점을 확인한다.
- 프로젝트 스타일을 확인할 때 [범위별 기본 프로필](references/default-profile.json)을 사용한다. 작성자를 매 작업마다 다시 검색하지 않는다.
- 자동 정적 비교가 필요하면 [검사기](references/checks.md)를 사용한다.

정적 컨트롤과 배치는 Designer, 바인딩·업무 동작은 실제 code-behind 패턴을 따른다. 이벤트 구독은 기존 생성자의 이름 있는 핸들러 연결 방식을 따르고 중복 연결하지 않는다. 해당 프로젝트의 DevExpress 버전/API와 csproj 등록을 확인한다. 기존 helper를 활용하고 새 추상화·LINQ·중간 테이블·불필요한 빌드는 [필요성 기준](../work-execution/references/preferences.md)으로 판단한다.

그리드 기본값은 사용자가 제공한 DataWindowToXml.html의 Load Layout 속성을 따른다. 기본으로 셀 TextOptions, SpinEdit EditMask, DisplayFormat(FormatType 포함), OptionsBehavior를 덧붙이지 않는다. 편집 차단 컬럼은 AllowEdit=false와 ReadOnly=true, 동작을 남길 버튼 등의 컬럼은 ReadOnly=true만, 편집 가능 컬럼은 둘 다 생략한다. 기존 화면의 속성을 일괄 초기화하지 않고, 별도 동작에 필요한 변경만 현재 요구와 실제 소스로 판단한다.

숫자 형식이 필요한 합계·문자열 표시는 [사용자 지정 숫자 형식](references/coding-style.md)을 따른다. N0·N2보다 #,##0·#,##0.## 등을 우선한다. 합계 형식이나 Spin 연결 확인 요청을 셀·Repository DisplayFormat 추가 근거로 확장하지 않는다.

기본값은 사용자 컨트롤 생성자뿐 아니라 실제 호출되는 공통 폼 초기화·helper까지 추적한다. 그 경로가 없는 대상에 같은 표시를 적용하라는 현재 명시적 요청이 있으면, 확인한 형식과 소수 정밀도를 그대로 적용할 수 있다. 이전 미사용 지시만으로 이후의 구체적인 요청을 차단하지 않는다.

검사 경고를 없애기 위해 변경 속성을 임의로 --allow-property-change에 넣지 않는다. 예외로 제외한 검사는 통과 근거가 아니며 실제 요구·필요성은 별도로 확인한다.

전체 화면 요청은 전체 생명주기를 확인하고 국소 수정은 그 범위로 제한한다. 최종 확인은 실제 요구 동작으로 하며 빌드 결과로 UI나 저장 동작을 보증하지 않는다.
# 제공 조각의 한계

프로젝트 없이 코드 조각·fixture만 주어졌다면 그 범위에서 가능한 수정을 진행한다. DevExpress 버전·csproj·상속 구현은 미확인으로 남기고, 그 정보가 없는 것만으로 명확한 국소 수정을 차단하거나 다른 프로젝트를 대신 읽지 않는다. API 차이가 실제 해결을 좌우할 때 필요한 정보만 확인한다.
