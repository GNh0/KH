# 사용자 C# 작성 방식

WinForms/DevExpress/KoneLib 화면을 작성하거나 수정할 때 적용한다. 사용자 지정 BA·SA·MA의 현재 솔루션에 등록된 7개 화면에서 반복된 작성 방식으로 보완했다. BACKUP이나 솔루션 밖 복사 프로젝트를 기준으로 삼지 않는다.

## 기준의 우선순위

현재 사용자 지시와 이미 합의한 C# 규칙을 먼저 적용한다. 참조 소스에서 다른 표현이 나와도 새 예외로 받아들이지 않는다. 사용자는 그런 차이가 놓친 부분일 가능성이 크다고 명시했다. 소스의 반복 패턴은 아직 정하지 않은 작성 방식을 보완하는 근거다.

실제 대상의 바인딩·SP·행 상태·트랜잭션·상속 API는 별도로 보존해야 할 동작 계약이다. 스타일을 맞춘다는 이유로 호출 의미를 바꾸지 않는다. 미완성 메서드, 주석 처리된 저장 코드, 사용하지 않는 using, 오래된 복사 코드는 따라 할 작성 규칙이 아니다. MAUI/PDA·비동기 서비스 등 다른 C# 구조로 이 화면 패턴을 확대하지 않는다.

원본을 유지하고 일부만 고치라는 현재 요청은 일반적인 새 코드 작성 선호보다 구체적이다. 해당 범위에서는 원본 속성·분기를 관례대로 다시 정리하지 않는다. 명명·중괄호 등 필요한 스타일 수정과 업무 조건 추가를 구분한다. 기존 if/else를 삼항식으로 줄이거나 별도 bool 상태를 만들어 편집·첨부·버튼 동작을 제한하는 것은 단순 스타일 수정이 아니다.

## 구문과 이름

- 메서드와 제어문의 중괄호는 별도 줄에 배치하고 4칸 들여쓰기를 따른다. `if`·`else`·`for`·`foreach`·`while`·`do`는 한 줄 return/대입이라도 본문 중괄호를 쓴다. `else if` 연결은 유지한다. 참조에 중괄호가 빠진 사례가 있어도 이 규칙을 낮추지 않는다.
- DataTable/DataRow/DataSet, string/int/decimal/bool 등 명시적 타입을 우선한다. `var` 일괄 변환이나 기존 파일 전체 정리는 하지 않는다. 프로퍼티는 `get { ... }` 블록으로 작성하고 식 본문으로 축약하지 않는다.
- 기존 `str...`, `dt...`, `dr...`, `ds...`와 `grd/gvw/col/rps/txt/btn` 계열 이름을 따른다. 수치·상태 변수의 접두사와 대소문자는 현재 파일을 따른다. 샘플의 특정 업무명이나 접두사 하나를 전역 명명 규칙으로 강제하지 않는다.
- 조기 return, 명시적인 대입과 기존 switch 분기를 유지한다. 파싱 성공 판정과 이후 값 비교는 별도 if로 쓴다. 참조의 인라인 TryParse/삼항식이 이 합의를 무효화하지 않으며 모든 삼항식을 금지하는 뜻도 아니다.

```csharp
DataTable dtList
{
    get
    {
        return grdList.DataSource as DataTable;
    }
}

private void AddItem(DataRow drItem)
{
    if (drItem == null)
    {
        return;
    }

    DataRow drNew = dtList.NewRow();
    drNew["ITEMCD"] = drItem["ITEMCD"];
    dtList.Rows.Add(drNew);
}
```

위 예시는 표현 방식만 보여준다. 실제 화면에서는 대상 테이블 초기화·중복 기준·필수 필드와 행 상태를 확인한다.

## 화면 구성과 이벤트

컨트롤 선택·기본 초기화·명명은 [사용자 컨트롤 기준](user-controls.md)을 먼저 적용한다. 사용 가능한 사용자 컨트롤을 우선하며 라이브러리 이름에 한정하지 않는다. 날짜 입력은 ymd와 실제 필드명을 사용한다.

기존 FrmDevBase 화면의 SelectType enum → 상태 필드·DataTable 프로퍼티 → 생성자 → 화면 명령 이벤트 → 조회/저장·포커스/팝업 helper 구성을 따른다. enum 항목과 여러 줄 DB 인자는 현재 소스처럼 다음 줄 앞에 쉼표를 두고 정렬한다. 국소 수정에서 기존 멤버 전체를 재배치하지 않는다.

정적 컨트롤 선언·생성·배치·속성은 Designer에 둔다. 이벤트 구독은 실제 화면의 생성자에서 `InitializeComponent()` 다음에 이름 있는 핸들러로 연결하는 방식을 따른다. Load/SearchCommand/NewCommand/EditCommand/SaveCommand/DeleteCommand/ClearCommand와 그리드·버튼·Repository 이벤트를 임의로 람다로 바꾸거나 Designer로 옮기지 않는다. 이미 Designer나 다른 초기화 경로에서 연결한 이벤트는 중복 구독하지 않는다. 동적으로 구독·해제하는 실제 요구는 해당 이벤트 수명에 맞춘다.

조회·저장은 기존 `CallSelectProcedure`·`CallSaveProcedure`에 두고 화면 명령 이벤트는 그 흐름을 연결한다. `fnFocusedRowChanged`, `SetEditMode`, `PopUpItems` 등 실제 역할이 있는 기존 helper를 재사용한다. 짧은 코드마다 새 helper나 범용 계층을 만들지 않는다.

## 데이터베이스와 행 처리

여러 줄 호출은 기존 들여쓰기에 맞춰 DbParameter 하나를 한 줄에 두고 줄 앞 쉼표를 사용한다.

```csharp
DataSet ds = dbClient.GetDataSetFromSP("sp_SAMPLE_SELECT"
                                  , new DbParameter("@WORKTYPE", _selectType.ToString())
                                  , new DbParameter("@KEYCODE", strKeycode)
                                   );
```

실제 프로시저명·매개변수명·순서·타입·WORKTYPE과 결과 테이블은 대상 계약을 읽어 결정한다. 예시 이름을 제품 코드에 복사하지 않는다. `ExecSP`/`ExecSPTrn`, `m_Editmode.ToString()`/`GetEditModeWorkType()`는 의미가 다를 수 있으므로 외형을 통일하지 않는다.

DataTable/DataRow 직접 처리와 `NewRow` → 필드 대입 → `Rows.Add`를 우선한다. 저장은 실제 TableName·DataRowState와 `DataUtil.DataTableToXml` 계약을 따른다. 포커스 행과 체크 선택 행, 버튼 Tag/FieldName 분기는 [데이터와 이벤트 계약](data-flow.md)을 적용한다.

`dtMasterToDataTable` 같은 기존 helper는 실제 본문을 확인하고 재사용한다. helper가 이미 스키마를 복제한다면 참조 화면의 추가 `Clone()`을 관례로 복사하지 않는다. LINQ·중간 테이블·빌드는 [필요성 기준](../../work-execution/references/preferences.md)을 따른다. 사용하지 않으면 구현이 어렵거나 대안의 성능이 극단적으로 불리할 때만 사용하며, 짧아진다는 이유로 선택하지 않는다.

조회/저장의 예외와 사용자 메시지는 실제 프레임워크의 ShowMessage 계열 및 예외 표시 helper를 사용한다. helper 이름·시그니처를 임의로 교정하거나 모든 이벤트에 try/catch를 추가하지 않는다. null/false 반환은 호출부 처리와 함께 확인한다. DB 호출이 비어 있는데 true를 반환하는 참조 메서드를 완성된 저장 흐름으로 복제하지 않는다.

그리드 속성은 [사용자가 정정한 HTML 기본값](grid-layout.md)을 우선한다. 참조 Designer의 셀 정렬·마스크·DisplayFormat·OptionsBehavior 또는 편집 속성 누락을 새 기본값으로 학습하지 않는다.

## 숫자 표시 형식

숫자 형식이 필요한 위치에서는 N0·N2 등 표준 N 형식보다 사용자 지정 형식을 우선한다. 이 기준은 형식 문자열을 고르는 기준이다. 그리드 컬럼이나 Repository의 DisplayFormat·FormatType·EditMask를 새로 추가하는 근거로 사용하지 않는다.

| 표시 요구 | 우선 예시 | 0을 생략하는 기존 요구가 있을 때 |
| --- | --- | --- |
| 천 단위 구분, 소수 없음 | #,##0 | #,### |
| 천 단위 구분, 소수 최대 2자리 | #,##0.## | #,###.## |

위 표는 형식을 고를 때의 예시이며 기존 초기화의 소수 정밀도를 변경하는 규칙이 아니다. 사용자 컨트롤 생성자와 상속 클래스뿐 아니라 공통 폼에서 호출하는 초기화 helper, Repository 순회와 적용 조건까지 확인한다. 실제 경로에서 이미 숫자 표시를 처리하면 화면 Designer에 중복 대입하지 않는다.

공통 초기화가 없는 대상에 같은 표시를 적용하라고 사용자가 명시한 경우에는 확인한 설정을 적용한다. 예를 들어 원본 경로가 Numeric과 `"{0:#,###,###,##0.####}"`를 사용하고 사용자가 그 값을 지정했다면, 정확히 그 형식을 따른다. 임의로 `#,##0.##`로 줄이거나 형식 외의 버튼·마스크·정렬 속성을 함께 복사하지 않는다. 이 구체적인 요청은 해당 대상에 적용하며 다른 화면의 새 기본값으로 확대하지 않는다.

합계 표시는 기존 SummaryItem.DisplayFormat 또는 GridColumnSummaryItem의 형식 인수에 {0:#,##0}, {0:#,##0.##}처럼 넣는다. 기존 {0:N0} 건의 접미사, 자리 정렬, SummaryType, FieldName, 집계 계산은 유지한다. 합계 형식 요구를 일반 셀·Repository의 DisplayFormat 설정으로 확장하지 않는다. 실제 숫자의 ToString, string.Format, 보간 문자열에도 같은 표기 선호를 적용하되, 형식 때문에 새 보간식·helper를 만들지 않는다.

#,##0은 0을 표시하며 #,###은 0의 숫자 자리를 생략할 수 있다. 소수부 ##는 최대 자리수이므로 N2의 고정 두 자리와 표시 결과가 같다고 단정하지 않는다. 고정 두 자리가 실제 요구이면 #,##0.00을 사용한다. 기존 문화권·숫자 타입·반올림·음수/0 표시를 임의로 바꾸거나, 표시를 맞추려고 수치 데이터를 문자열로 바꾸지 않는다. 실제 API가 N 형식을 요구하는 제약은 현재 사용자 지시와 함께 판단하며 편의만으로 예외를 만들지 않는다.

문법 근거는 [Microsoft 사용자 지정 숫자 형식](https://learn.microsoft.com/en-us/dotnet/standard/base-types/custom-numeric-format-strings)과 [DevExpress 합계 형식](https://docs.devexpress.com/WindowsForms/DevExpress.XtraGrid.GridSummaryItem.DisplayFormat)이다.
