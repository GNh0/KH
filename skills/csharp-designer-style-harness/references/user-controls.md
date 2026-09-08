# 사용자 컨트롤 선택과 기본 초기화

이 기준은 KoneLib에 한정되지 않는다. 현재 프로젝트에서 사용할 수 있고 요청한 역할에 맞는 모든 사용자 컨트롤에 적용한다. UI 생성·수정, Designer, PB→C# 이관 모두 같은 기준을 쓴다.

1. 현재 솔루션·프로젝트 참조와 비교 화면에서 사용할 컨트롤을 확인한다. 해당 역할의 사용자 컨트롤이 있으면 우선 사용한다. 익숙하다는 이유로 기본 DevExpress/WinForms 컨트롤을 새로 선택하지 않는다. 특수 용도의 파생 컨트롤이 있다는 이유만으로 기존의 적절한 사용자 컨트롤까지 바꾸지 않는다.
2. 선택한 컨트롤의 생성자, InitializeComponent, 호출하는 초기화 helper와 상속 부모를 읽는다. 폰트·높이·최소/최대 크기·AutoHeight·정렬·색상·테두리·버튼·입력 마스크·편집/표시 서식·Enter/Tab 이동 등은 그 구현이 정한 기본값을 따른다. 문화권·모드별 분기나 이벤트에서 바뀌는 값을 전역 기본값으로 복사하지 않는다.
3. 화면에서는 이름, 위치/부모 배치, 표시 문구, 실제 바인딩·이벤트와 현재 요청에 필요한 속성만 지정한다. 사용자 컨트롤의 기본 속성을 중복 대입하거나 다른 값으로 덮어쓰지 않는다. 이름/위치처럼 화면이 정해야 하는 항목과 높이/Font처럼 이미 컨트롤이 정한 항목을 구분한다. Visual Studio가 재직렬화한 동일 기본값을 무조건 삭제하는 정리 작업으로 확대하지 않는다.
4. 속성 변경이 필요하면 현재 요구와 해당 속성의 역할을 연결한다. 다른 화면에서 본 설정, 보기 좋을 것이라는 추측, 자료형만 보고 붙인 서식은 변경 근거가 아니다. 기존 사용자가 바꾼 값과 명시적 예외는 보존한다. 실제 사용 가능한 컨트롤이나 API 제약 때문에 기본 컨트롤이 필요한 경우에는 그 근거로 구현한다.

기본값을 아직 읽지 못했다면 모델이 기억하는 DevExpress 기본값이나 다른 프로젝트의 KoneLib 값으로 채우지 않는다. 현재 대상의 선언·초기화 경로를 확인한다. 이 확인은 작업 중 소스 읽기이며, 매번 사용자에게 같은 설명·승인·프로필 파일을 요구하는 절차가 아니다.

## 이름과 날짜 컨트롤

날짜 입력은 `ymd`와 실제 필드 의미를 결합한다. 예를 들어 FRDT/TODT이면 `ymdFRDT`/`ymdTODT`다. DateEdit라는 타입 이름에서 `deFRDT`를 새로 만들지 않는다. 선언·생성·Name·이벤트 연결·code-behind 참조를 함께 맞춘다. 기존 이름을 바꾸는 것이 현재 범위인지 먼저 판단한다.

다른 입력은 현재 사용자 컨트롤과 비교 화면의 접두사·바인딩을 따른다. BA·SA·MA에서는 txt/cbo/btn/memo, grd/gvw/col/rps, grp/pn 등이 반복된다. 자동 생성 이름이나 불일치가 있는 일부 샘플로 기존 명명 합의를 완화하지 않는다. 모든 컨트롤에 임의의 새 접두사를 정하지 않는다.

3.0.0 이전 하네스에 있던 다음 작성 규칙을 유지한다. 새 입력의 Field는 실제 바인딩 필드, 컨테이너의 Role은 실제 화면 역할이다. 샘플의 `panMaster`, `repositoryItem...1` 등은 기존 합의를 바꾸는 근거가 아니다.

| 역할 | 이름 |
| --- | --- |
| 텍스트·숫자·날짜 입력 | `txt<Field>`, `Spin<Field>`, `ymd<Field>` |
| 룩업·버튼·체크·메모 입력 | `cbo<Field>`, `btn<FieldOrRole>`, `Chk<Field>`, `memo<Field>` |
| 패널·그룹·그리드·뷰 | `pn<Role>`, `grp<Role>`, `grd<Role>`, `gvw<Role>` |
| 컬럼 | `col<Role>_<FIELD>` |
| 숫자·룩업·버튼·체크 Repository | `rpsSpin<Field>`, `rpscbo<Field>`, `rpsbtn<Field>`, `rpschk<Field>` |
| 라벨·탭·트리 | `lbl<FieldOrRole>`, `tab<Role>`, `treeList<Role>` |

숫자 Repository 기본 이름은 `rpsSpin<Field>`다. 같은 화면의 다른 그리드에 동일 필드의 Repository가 추가로 필요하면 `rps<Role>Spin<Field>`로 구분한다. 예를 들어 List의 `rpsSpinQTY`가 이미 있고 Detail에서도 QTY에 별도 Repository가 필요하면 기존 이름은 유지하고 `rpsDetailSpinQTY`를 만든다. Role은 `grdDetail`의 Detail처럼 해당 그리드 역할이며 `rpsSpinDetailQTY`처럼 Spin 뒤로 옮기거나 충돌을 숫자 접미사로 덮지 않는다. 현재 화면에 이미 확립된 Repository 공유 동작을 국소 이름 수정만으로 분리하지 않는다.

`gridControl1`, `gridView1`, `gridColumn1`, `repositoryItem...1`, `textEdit1` 같은 자동 생성 이름을 새 화면에 그대로 남기지 않는다. 현재 사용자가 이름을 별도로 지정하면 그 지시를 따른다. 기존 화면 전체를 규칙에 맞춰 강제 개명하지 않는다. 이름만 맞추고 BindingField·FieldName·ColumnEdit·이벤트 연결이 빠지면 완료가 아니다.

DateEdit도 기본 초기화 원칙을 그대로 따른다. 날짜라는 이유만으로 DisplayFormat·EditFormat·EditMask·Mask 설정을 덧붙이지 않는다. 연→월→일 자동 이동처럼 사용자가 요구한 입력 동작은 먼저 컨트롤이 이미 구현하는지 확인하고, 부족한 부분에 필요한 속성만 적용한다. 마스크를 전역 금지하거나 표시 서식 정리를 이유로 필요한 입력 동작을 지우지 않는다.

사용자가 별도로 정한 [그리드 HTML 기본값](grid-layout.md)과 세 가지 컬럼 편집 규칙은 명시적 화면 기준으로 함께 적용한다. 그리드 규칙을 모든 TextEdit/버튼/패널의 속성 값으로 확대하지 않는다.

## 선택적 정적 비교

검사기에는 실제 대상에서 선택한 사용자 컨트롤 C# 소스를 `--control-source`로 전달할 수 있다. 별도 JSON 기본값 목록을 만들 필요가 없다.

```powershell
python <plugin-root>/scripts/kh_check.py designer <after.Designer.cs> --original <before.Designer.cs> --control-source <actual-InputBox.cs> --control-source <actual-DateBox.cs>
```

이름과 네임스페이스에 관계없이 제공한 상속 선언으로 기본 컨트롤 선택을 검토한다. 직접 기본 생성자와 함께 제공한 부모 생성자의 대입값을 비교하여 새 기본값 덮어쓰기는 경고, 같은 값의 재대입은 정보로 표시한다. 기존과 같은 화면 대입은 일괄 정리 대상으로 경고하지 않는다. 특정 요구 속성은 기존 `--allow-property-change member.Property`를 사용하며 명시한 보존 계약을 무효화하지 않는다.

이 검사는 컨트롤 라이브러리를 실행하거나 기본값 전체를 알아내는 도구가 아니다. 소스의 단순 상속·직접 대입만 확인하고, 초기화 helper/제공되지 않은 partial·부모/조건·실행 중 값과 실제 프로젝트 참조는 별도 확인한다. 조건부로 덮어쓴 속성은 확정 기본값에서 제외한다. 소스를 주지 않으면 컨트롤 우선 선택·기본값 덮어쓰기 검증은 미확인으로 남는다. 코드 작성자는 검사기 범위와 관계없이 위의 실제 초기화 경로를 읽는다.
