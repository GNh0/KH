# 실제 데이터와 이벤트 흐름

전체 화면 요청은 Load/initControl → Search → 상세 → 보호 → 추가/복사/수정/삭제/저장/취소 → 재조회/포커스 복원까지 확인한다. BA060T 등 실제 권한과 CustomButton/SimpleButton/U_BUTTON 동작도 연결한다. 국소 수정에 전 생명주기 재구현을 강제하지 않는다.

현재 SearchCommand/NewCommand/DeleteCommand·m_Editmode 흐름을 따른다. 기존 처리를 중복 초기화하거나 확인 메시지를 두 번 띄우지 않는다. 포커스는 GetFocusedDataRow()/FocusedRowHandle, 체크 선택은 실제 선택 컬렉션으로 구분한다. 화면 정렬 순서와 선택 반환 순서를 혼동하지 않는다.

NEW/MOD/DEL과 Added/Modified/Deleted를 실제 XML 생성기와 SELECT/SAVE 분기에 맞춘다. 전체 삭제/재등록·모든 행 수정·일괄 원자성을 임의로 추가하지 않는다. SAVE에서 하라고 한 검증을 C#에 중복하지 않는다. 파라미터·XML 필드·채번·고정값·결과 테이블을 대조한다.

기존 for/DataTable.Select/NewRow/Rows.Add를 우선한다. 해당 업로드 사례는 정상 행을 바로 대상에 추가하고 오류 행은 건너뛰어 한 번에 알려준다. 다른 업로드의 원자성을 이 사례로 결정하지 않는다. 실제 Excel 시트·셀 타입·헤더·키·날짜를 읽는다.

TY 사용자 lookup은 요구 범위에서 조회 RTRUSER, 입력·수정 USER를 구분한다. get 블록과 파싱/비교 if 분리 등 지정한 기존 C# 스타일을 지킨다. 공통 기능 재사용은 반복 제거 필요가 있을 때 실제 helper 계약을 읽어 적용한다.
