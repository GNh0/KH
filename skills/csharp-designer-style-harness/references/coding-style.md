# C# 작성 방식

## Priority of requirements

최신 요청과 합의한 규칙을 우선한다. 지정 비교 프로그램은 미지정 작성 방식의 근거다. 대상의 기존 속성·분기·트랜잭션·바인딩은 요청 범위에서만 바꾼다. 다른 UI 구조는 해당 프로젝트를 따른다.

## Syntax and naming

- 공백 4칸, 괄호는 별도 줄. 한 줄 return도 if/else·반복문의 중괄호 안에 둔다. 기존 else-if와 조기 반환을 유지한다.
- DataTable·DataRow·DataSet·기본형을 명시한다. get 블록, 명시적 대입, switch 분기를 유지한다. 지역명은 str/dt/dr/ds와 화면 관례를 따른다.
- TryParse 성공 여부와 변환 값은 별도 if로 확인한다. 화면 표시 문자열 조합은 보간을 쓴다. SQL·XML·키의 형식과 외부 식별자는 보존한다. 앱 액션 Tag와 대응 case는 대문자로 맞춘다.

```csharp
DataTable dtList
{
    get
    {
        return grdList.DataSource as DataTable;
    }
}
```

## Screen structure and events

- FrmDevBase에서 실제 화면의 enum, 상태/데이터 속성, 생성자, 명령, 조회·저장 메서드 순서를 따른다. 여러 줄 인자와 enum 멤버는 선행 쉼표로 맞춘다. 날짜 입력명은 ymd와 필드명이다.
- 정적 배치는 Designer에 둔다. 대상이 InitializeComponent 후 구독하면 그곳에 이름 있는 핸들러를 연결한다. 양쪽 파일에서 중복 구독, 동적 해제, Repository ButtonClick·Grid RowCellClick의 중복 팝업을 확인한다.
- 기존 조회·저장 호출에서 인자·반환, 실패·취소, 초기화·보호·재조회를 확인한다. 공유 핸들러·헬퍼는 실제 필요에 맞춰 쓴다.

## Database and row handling

- DbParameter는 한 줄에 하나씩, 실제 인자 순서와 선행 쉼표를 쓴다. ExecSP/ExecSPTrn, 편집 모드, XML TableName과 행 상태, 결과표 순서를 보존한다.
- DataTable·DataRow에 직접 추가한다. 스키마 복제나 중간 표가 필요하면 기존 헬퍼의 반환을 먼저 확인한다. 체크/포커스 행, 실제 예외와 ShowMessage 경로를 대조한다.

```csharp
DataRow drNew = dtList.NewRow();
drNew["ITEMCD"] = drItem["ITEMCD"];
dtList.Rows.Add(drNew);
```

## Numeric display formats

| 요청 | 형식 | 0 숨김을 요청한 경우 |
| --- | --- | --- |
| 천 단위 정수 | `#,##0` | `#,###` |
| 소수 최대 두 자리 | `#,##0.##` | `#,###.##` |
| 소수 두 자리 고정 | `#,##0.00` | 요청한 표기를 확인 |

- 요구 형식이 있으면 그대로 쓰고 그 외에는 N0/N2보다 사용자 지정 형식을 우선한다. 생성자·공통 Repository 초기화를 먼저 확인한다.
- 합계는 SummaryItem.DisplayFormat 또는 GridColumnSummaryItem에 둔다. 접미사·정렬·SummaryType·FieldName을 보존하고 관련 ToString·string.Format·보간 표기도 맞춘다.
- 타입·정밀도·반올림·문화권·음수/0 표기를 보존한다. 셀 표시·입력 마스크·Repository는 해당 속성 변경이 필요할 때 수정한다. [숫자 형식](https://learn.microsoft.com/en-us/dotnet/standard/base-types/custom-numeric-format-strings), [DevExpress 합계](https://docs.devexpress.com/WindowsForms/DevExpress.XtraGrid.GridSummaryItem.DisplayFormat).
