# User-control selection and default initialization

- 같은 역할의 실제 프로젝트 컨트롤에서 생성자·InitializeComponent·헬퍼·기반 클래스를 확인한다. 이벤트·문화권·편집 모드별 변경은 상시 기본값과 구별한다. 표준 컨트롤 사용은 대상의 API·가용성을 따른다.
- 화면은 이름·배치·텍스트·바인딩·이벤트를 소유한다. 실제 요구가 있는 속성만 덮어쓰고 기존 직렬화와 사용자 편집은 보존한다. 서식·마스크·이동·색·테두리가 콜백에서 바뀌는지도 확인한다.
- 라벨/한 줄 입력 높이는 같은 화면의 보이는 같은 역할과 대조한다. Size·제약·AutoHeight·버튼 공간을 함께 본다. 짧은 내용은 기본 폭을 쓰고 긴 내용은 필요한 만큼 넓힌다.
- 라벨의 Font·H/V 정렬·UseTextOptions·AutoSizeMode는 실제 초기화에 맞춘다. 확인한 u_Label은 Default를 Far/Center로 해석하고 명시된 정렬값은 유지한다. 화면 전용 큰 글꼴은 기존 사용자 설정·같은 역할 컨트롤·승인된 비교 Designer에서 근거를 찾는다.
- 편집기·캘린더의 필수 Buttons.AddRange를 보존한다. 공통 초기화에서 나중에 가리는 버튼도 구성한다. RepositoryItem은 해당 클래스의 초기화와 속성 경로를 본다.

## Naming and date controls

입력명은 바인딩 필드, 컨테이너명은 화면 역할을 따른다. 기존 공유는 보존하고 이름 변경은 요청 범위에서 한다.

| Role | Name |
| --- | --- |
| Text, numeric, date | `txt<Field>`, `Spin<Field>`, `ymd<Field>` |
| Lookup, button, check, memo | `cbo<Field>`, `btn<FieldOrRole>`, `Chk<Field>`, `memo<Field>` |
| Panel, group, grid, view | `pn<Role>`, `grp<Role>`, `grd<Role>`, `gvw<Role>` |
| Column | `col<Role>_<FIELD>` |
| Numeric, lookup, button, check Repository | `rpsSpin<Field>`, `rpscbo<Field>`, `rpsbtn<Field>`, `rpschk<Field>` |
| Label, tab, tree | `lbl<FieldOrRole>`, `tab<Role>`, `treeList<Role>` |

예를 들어 날짜 범위는 `ymdFRDT`/`ymdTODT`다. 실제로 필요해 별도 생성한 수량 Repository는 `rpsSpinQTY`와 `rpsDetailSpinQTY`를 구별한다. 선언·생성·Name·이벤트·FieldName·ColumnEdit을 맞춘다.

날짜 표시는 기존 표시 경로를 쓴다. 편집/달력 팝업이 필요할 때 DateEdit Repository를 연결하고 마스크·이동·시간 정밀도와 SQL 타입을 확인한다. 그리드 열은 [HTML 기본 규칙](grid-layout.md)을 적용한다.

## Optional static comparison

원본·컨트롤 소스·같은 역할 Designer로 [정적 비교](checks.md)를 실행한다. 해당 변경에 근거가 있는 속성만 `--allow-property-change member.Property`로 지정한다. 실제 높이·정렬은 대상 화면 DPI와 레이아웃에서 확인한다.
