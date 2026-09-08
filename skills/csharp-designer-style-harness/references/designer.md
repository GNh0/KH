# WinForms / Designer

정적 필드·컨트롤·컬럼·Repository 생성과 배치·속성은 Designer에 둔다. Visual Studio Designer가 읽지 못하는 helper 생성 구문은 호환성 문제다. 업무·동적 바인딩은 현재 프레임워크의 code-behind에 둔다.

현재 UserControl 기본 폭·높이·AutoHeight·버튼·정렬을 읽고 덮어쓰지 않는다. 모든 컨트롤에 100x25나 특정 font를 고정하지 않는다. 사용자가 바꾼 font·Visible 값을 보존한다. TabIndex는 지정한 입력 순서와 컨테이너 순서까지 맞춘다.

그리드의 기본 속성·Appearance·편집 구분은 [DataWindowToXml 기준](grid-layout.md)을 따른다. 헤더 가운데 정렬을 셀 정렬로 확대하지 않는다. 숫자는 실제 Spin Repository, 코드/표시는 lookup 바인딩, 버튼은 실제 기능을 연결한다. Spin Repository를 쓰라는 요구만으로 EditMask를 붙이지 않는다. DisplayFormat은 FormatString과 FormatType 모두 기본으로 지정하지 않는다. 보고서의 허용된 표현 서식까지 금지하지 않는다.

기본 건수·합계·group footer/merge/EvenRow와 지정된 표시 위치를 확인한다. colList_/colDetail_/colTABLE_FIELD 등 현재 프로젝트 명명을 사용한다. 이름만 맞고 바인딩이 없는 상태는 완료가 아니다.

실제 DevExpress 참조 버전과 API, csproj/.resx 등록을 확인한다. MAUI/PDA에는 이 UI 계약을 일괄 적용하지 않는다.
