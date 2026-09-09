# 사용자 그리드 기본 속성

2026-09-08에 사용자가 제공한 `DataWindowToXml.html`의 `generateDevExpressXml` 출력이 새 WinForms/DevExpress 그리드의 기본값이다. 다른 화면의 임의 옵션이나 DevExpress 예제의 권장 설정을 함께 복사하지 않는다. 기존 화면의 사용자 변경·실제 동작은 보존하고, 새 요구를 구현하는 데 필요한 속성만 바꾼다. 이 기준을 보고서나 다른 UI 프레임워크에 확대하지 않는다.

## Appearance

| 범위 | 기본으로 생성할 속성 |
| --- | --- |
| AppearanceCell | Options.UseFont=true, Font=Tahoma 9pt |
| AppearanceHeader | Options.UseFont=true, Options.UseTextOptions=true, TextOptions.HAlignment=Center, TextOptions.VAlignment=Center, Font=Tahoma 9pt |

셀의 `TextOptions`와 `Options.UseTextOptions`는 생략한다. Near·Far·Center 같은 기본값도 명시하지 않는다. 숫자·날짜·문자라는 이유로 별도 셀 정렬을 추가하지 않는다. 헤더의 UseTextOptions는 헤더 가운데 정렬을 적용하는 플래그이므로 유지한다. Tahoma 9pt는 이 HTML로 새로 만드는 그리드의 값이며, 기존 사용자가 바꾼 Font나 모든 UserControl의 폰트를 덮어쓰는 규칙이 아니다.

## 컬럼 편집

| 필요한 동작 | OptionsColumn.AllowEdit | OptionsColumn.ReadOnly |
| --- | --- | --- |
| 일반 편집 차단 | false | true |
| Button Repository 등 동작은 허용하고 값 수정은 차단 | 생략 | true |
| 편집 가능 / 별도 편집 요구 없는 HTML 기본 구성 | 생략 | 생략 |

생략은 `AllowEdit=true`나 `ReadOnly=false`를 쓰라는 뜻이 아니다. 기존 두 속성을 바꾸는 요청이면 불필요해진 대입문을 제거한다. 버튼 이름만 보고 동작을 단정하지 말고 실제 Repository 타입·연결 이벤트·요구 동작으로 구분한다.

`GridView.OptionsBehavior`는 이 HTML에 없다. 컬럼 편집 제한을 구현하려고 `Editable=false`·`ReadOnly=true`를 그리드 전체에 추가하지 않는다. 원래 값이 있으면 관련 없는 작업에서 추가·변경·삭제하지 않는다. [DevExpress Editable 문서](https://docs.devexpress.com/WindowsForms/DevExpress.XtraGrid.Views.Base.ColumnViewOptionsBehavior.Editable)에서도 뷰의 Editable은 셀 편집기와 Edit Form의 편집을 함께 제어한다. 컬럼의 [ReadOnly](https://docs.devexpress.com/WindowsForms/DevExpress.XtraGrid.Columns.OptionsColumn.ReadOnly)는 별도 속성이므로 둘을 대체 관계로 사용하지 않는다. 실제 설치 버전과 이벤트 동작은 필요한 범위에서 확인한다.

## 표시와 숫자 편집기

- `DisplayFormat`은 `FormatType`, `FormatString` 모두 기본으로 지정하지 않는다. 날짜 컬럼이라는 이유로 DateTime/`yyyy-MM-dd`를 추가하지 않는다.
- 숫자 컬럼은 실제 Spin Repository를 연결하되 `Mask.EditMask`를 자동 추가하지 않는다. `N0`·`N2`도 동일하다. 이 규칙으로 DateEdit의 필요한 입력 마스크를 일괄 제거하지 않는다.
- 표시 문제를 해결할 때는 실제 데이터 타입·바인딩·기존 Repository를 먼저 확인한다. 마스크나 형식 지정 없이는 요구 동작의 구현이 어려운 경우에만 필요한 속성을 좁혀 적용하고 이유를 남긴다. 편의상 기본값을 늘리는 것은 예외 사유가 아니다.

## Load Layout 기본값

| OptionsView | 값 |
| --- | --- |
| ShowViewCaption | false |
| EnableAppearanceEvenRow | true |
| ShowGroupPanel | false |
| ColumnAutoWidth | false |
| ShowFooter | true |
| ShowAutoFilterRow | true |

나머지 뷰 속성은 BestFitMaxRowCount=-1, PreviewLineCount=-1, HorzScrollStep=3, FocusRectStyle=CellFocus, ScrollStyle=LiveVertScroll/LiveHorzScroll, PreviewIndent=-1, LevelIndent=-1, GroupFooterShowMode=VisibleIfExpanded, SynchronizeClones=true, BorderStyle=Default, DetailHeight=350, DetailTabHeaderLocation=Top, ActiveFilterEnabled=true다. GroupPanelText·PreviewFieldName·VertScrollTipFieldName·NewItemRowText·ViewCaption은 빈 문자열이다. XML의 #LayoutVersion은 비어 있고 Name은 gridView1이며, C# 멤버 이름은 현재 프로젝트의 grd/gvw 이름을 쓴다.

컬럼은 Visible=true, VisibleIndex는 1부터 입력 순서, FieldName·Name·Caption은 원본 열 정보로 만든다. 실제 캡션·멤버명·폭·표시 여부가 제공되면 해당 값을 쓴다. HTML의 빈 ColumnEditName은 실제 숫자/lookup/button Repository를 연결하지 말라는 뜻이 아니다.

원본 HTML SHA-256: `95b2bbb456a999af84face42e7da005c081153ad6a825d245544d48aaa872358`. 회귀 fixture는 원본 함수를 실행해 일반 예시 필드 ITEMCD/QTY로 얻은 [XML](../../../tests/fixtures/datawindow_to_xml_defaults.xml)이다. 공통 기본값은 [grid_defaults.py](../../../src/common/grid_defaults.py)에서 XML/C# 생성과 검사에 공유한다.

## 변경 후 확인

새 기본값·컬럼 편집 모드를 검사하고, 기존 화면 수정은 원본과 비교해 요청하지 않은 옵션이 추가·변경·삭제되지 않았는지 확인한다. [검사 명령](checks.md)에 원본과 명시한 컬럼 모드를 전달할 수 있다. 결과의 스타일 경고는 검토 항목이며, 경고가 있다는 이유로 구현을 차단하거나 기존 옵션을 일괄 삭제하지 않는다. 검사 통과는 실제 Designer 실행이나 버튼 이벤트 동작의 증거가 아니다.

합계의 SummaryItem.DisplayFormat·Summary 생성자 형식 인수는 일반 셀/Repository의 DisplayFormat 설정과 적용 위치가 다르다. 필요한 합계 형식은 [사용자 지정 숫자 형식](coding-style.md)을 따르고, 이를 이유로 컬럼·Repository에 DisplayFormat·FormatType을 추가하지 않는다.
