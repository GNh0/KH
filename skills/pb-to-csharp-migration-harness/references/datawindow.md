# DataWindow와 화면 매핑

PBL/object와 상속 부모, 연결 DW, retrieve 인자, SQL, column/compute, protect/taborder, update 속성, 이벤트를 연결한다. HTML→XML 입력의 그룹·패널·그리드·caption·열 순서·기본값을 실제 레이아웃으로 반영한다.

원시 복합키 구성값은 보존하고 표시 키를 따로 만든다. 키 구성 개수·업무 이름은 입력에서 결정한다. read-only/수정 가능 상태, 목록/상세 연결, 선택/포커스, 사용자 권한, lookup/numeric/button Repository를 현재 C# 패턴으로 옮긴다.

보고서는 H/D/F·그룹·밴드·페이지 순서를 보존한다. 여러 보고서 HTML 변환은 공통 경로를 검토하되 생성자 부작용과 렌더 순서를 확인한다. 밴드가 없는 경우와 빈 값의 실제 계약을 확인한다. 단순 HTML 연결로 출력 동작을 대체하지 않는다.
# 생성 도구의 범위

`src.pb.datawindow`의 XML 생성·검사는 사용자가 2026-09-08에 다시 지정한 DataWindowToXml 기본 속성을 재현한다. [그리드 기본값](../../csharp-designer-style-harness/references/grid-layout.md)을 C# 화면에도 적용한다. 이 템플릿의 Tahoma 9pt·표시값을 모든 기존 화면에 강제하지 않는다. 실제 DataWindow 캡션과 현재 Designer 속성을 먼저 읽는다.

`build_csharp_grid_column_designer_plan`은 새 구성 초안을 반환한다. 기존 화면 전체를 대체하는 도구가 아니다. 명시한 C# 이름을 사용할 수 있고 `column_properties`(필드명 또는 멤버명 → 속성/실제 C# 식), `view_properties`로 현재 Font·Visible·정렬 등을 템플릿보다 우선한다. 속성 값 `None`은 해당 대입문을 생략한다. 반환 코드에 실제 API/Designer 검증까지 끝났다는 뜻은 없다.

기본 호출은 HTML처럼 AllowEdit·ReadOnly·OptionsBehavior를 생성하지 않는다. `column_edit_modes={'FIELD': 'read_only', 'colAction': 'action', 'EDITFIELD': 'editable'}`로 필요한 컬럼만 지정한다. read_only는 AllowEdit=false와 ReadOnly=true, action은 ReadOnly=true만, editable은 둘 다 생략한다. 기존 인자 `default_allow_edit=False`를 명시하면 일반 편집 차단 두 속성을 생성하며, True이면 둘 다 생략한다. 명시한 모드와 속성 override가 모순되면 실패로 반환한다. Spin Repository 연결에 EditMask·DisplayFormat을 덧붙이지 않는다.

같은 화면의 다른 그리드에 동일 숫자 필드 Repository가 있으면 생성기에 `existing_repository_names=["rpsSpinQTY"]`를 전달한다. Detail 그리드는 `rpsDetailSpinQTY`를 생성하고 ColumnEdit·선언·등록·Name을 함께 연결한다. 기본 역할은 생성할 grd 이름에서 가져오며 실제 역할이 다르면 `repository_role`을 명시한다. 기존 Repository 이름은 변경하지 않는다. 역할을 넣은 이름도 이미 있으면 숫자 접미사를 임의로 붙이지 않고 이름 충돌을 보고한다.
