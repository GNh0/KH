# WinForms / Designer

## Migration with source preservation

- 원본 C#·Designer·resx를 비교용으로 확보한다. 원본 화면을 가져올 때는 기존 Designer·resx를 복사하고 요청한 이름·삭제·수정만 반영한다. 스크린샷은 대상과 범위를 확인하는 데 쓴다.
- 이름 변경은 선언·Name·참조·이벤트·resx 키를 맞춘다. 삭제는 필드·생성·등록·이벤트·리소스까지 확인한다. 대상 API 차이로 교체하는 부분은 필요한 차이만 반영한다.
- 남는 컨트롤의 Font·Size·AutoHeight·정렬·버튼·마스크·표시 속성·Visible은 원본 diff와 대조한다. 원본과 명시적 rename 매핑은 [검사](checks.md)의 `--preserve-existing`, `--member-rename`에 사용한다. 간접 초기화·리소스는 별도로 확인한다.

## New controls and general structural review

- 슬라이드가 요구사항이면 전체 렌더링의 글·도형·표·이미지와 최신 정정을 함께 본다. 최종 캡션·필드 순서·편집 가능 열을 대조한다. 임시 추출물은 소스 밖에 둔다.
- 필드와 정적 컨트롤·열·Repository 생성·배치·속성은 Visual Studio Designer가 읽는 형식으로 둔다. 동적 바인딩·업무 코드는 코드비하인드, 명명한 핸들러는 기존 구독 위치에 한 번만 연결한다.
- [컨트롤 기본값](user-controls.md)의 생성자·상속·초기화 값을 유지한다. 폭 축소는 요청 범위, 긴 내용은 필요한 폭, 라벨·한 줄 입력 높이는 같은 화면의 같은 역할이 기준이다. 버튼 있는 우측 공간과 TabIndex·컨테이너 순서도 확인한다.
- 그리드는 [HTML 기본값](grid-layout.md) 기준이다. 머리글 가운데 정렬, 셀 표시, 뷰 속성은 각 범위에서 수정한다. 숫자는 실제 Spin, 코드는 값/표시 Lookup, 버튼은 이벤트까지 연결한다. Spin 요청만으로 EditMask를 추가하지 않는다.
- 합계·건수·표시 위치, 그룹 푸터/병합/EvenRow와 colList_/colDetail_/colTABLE_FIELD의 실제 바인딩을 확인한다. 조회·리사이즈 후 덮이는 속성은 [실행 경로](screen-behavior.md)를 따른다.
- 참조 DevExpress 버전의 API와 csproj/resx 등록을 확인한다. 더 이상 지원하지 않는 속성은 같은 동작의 지원 속성으로 교체한다. DB·Task 종료 정리는 기존 코드비하인드의 종료/취소 경로에서 처리하고 상속·partial Dispose와 중복되지 않게 한다.
