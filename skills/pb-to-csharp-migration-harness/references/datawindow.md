# DataWindow와 화면 매핑

PBL/object와 상속 부모, 연결 DW, retrieve 인자, SQL, column/compute, protect/taborder, update 속성, 이벤트를 연결한다. HTML→XML 입력의 그룹·패널·그리드·caption·열 순서·기본값을 실제 레이아웃으로 반영한다.

원시 복합키 구성값은 보존하고 표시 키를 따로 만든다. 키 구성 개수·업무 이름은 입력에서 결정한다. read-only/수정 가능 상태, 목록/상세 연결, 선택/포커스, 사용자 권한, lookup/numeric/button Repository를 현재 C# 패턴으로 옮긴다.

보고서는 H/D/F·그룹·밴드·페이지 순서를 보존한다. 여러 보고서 HTML 변환은 공통 경로를 검토하되 생성자 부작용과 렌더 순서를 확인한다. 밴드가 없는 경우와 빈 값의 실제 계약을 확인한다. 단순 HTML 연결로 출력 동작을 대체하지 않는다.
# 생성 도구의 범위

`src.pb.datawindow`의 XML 생성·검사는 과거 DataWindowToXml 배치 템플릿을 재현한다. 이 템플릿의 Tahoma 9pt·표시값을 모든 기존 화면에 강제하지 않는다. 실제 DataWindow 캡션과 현재 Designer 속성을 먼저 읽는다.

`build_csharp_grid_column_designer_plan`은 새 구성 초안을 반환한다. 기존 화면 전체를 대체하는 도구가 아니다. 명시한 C# 이름을 사용할 수 있고 `column_properties`(필드명 또는 멤버명 → 속성/실제 C# 식), `view_properties`로 현재 Font·Visible·정렬 등을 템플릿보다 우선한다. 반환 코드에 실제 API/Designer 검증까지 끝났다는 뜻은 없다.
