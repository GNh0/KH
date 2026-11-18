# C_KONE120 · FrmDevBase의 데이터 바인딩

적용 대상은 C_KONE120의 `KonesystemPlatform/KoneLib.DevBase`다. 다른 체크아웃에서는 같은 메서드의 오버로드와 실제 호출을 먼저 확인한다. 아래는 구현을 찾아갈 기준과 데이터 계약이다.

| 작업 | 확인된 동작 | 소스 위치 |
| --- | --- | --- |
| 한 행 → 패널 | `devFnc.DataRowToPanel`이 자식 컨트롤을 재귀 순회한다. 지원 편집기의 `BindingField`에 해당하는 열이 있을 때 값을 표시한다. 숨김 여부로 제외하지 않는다. | `DevFunction.cs` · `DataRowToPanel` |
| 패널 → 마스터 | `MasterToDataTable`은 입력 스키마를 복제하고 `MakeDataRow`가 패널 자식을 순회해 대응 열을 채운다. 반환 표에는 한 행이 있다. `AcceptChanges` 후 New는 Added, Mod는 Modified로 표시한다. | `DevFunction.cs` · `MasterToDataTable`, `MakeDataRow` |
| 숨은 키 | `_isPKValue`는 편집 보호에서 사용한다. 패널↔행 매핑은 지원 컨트롤의 `BindingField`, 스키마, 컨테이너가 결정한다. | `DevFunction.cs`, `PR200100.Designer.cs` · 숨은 PRODSEQ·PRODNUM |
| 표 → XML | `DataTableToXml(dt)`는 편집을 끝내고 Added·Modified·Deleted 행을 고른다. 상태 인자는 비트 조합이다. Unchanged를 명시하면 조회한 원본 행도 포함한다. 삭제 행은 Original 값을 쓴다. | `DataUtil.cs` · `DataTableToXml` |
| XML 행·속성 | 루트는 `ROOT`, 행명은 `TableName`(빈 이름은 `Table`)이다. 각 행에 상태별 `GBN` 속성(NEW·MOD·DEL·UNC)을 먼저 쓴다. 원본 표에 GBN 열을 추가하지 않는다. 원본에 같은 이름의 열이 있으면 뒤의 열 직렬화가 해당 속성을 덮을 수 있다. 대상 행이 없으면 루트만 반환한다. | `DataUtil.cs` · 행 생성 및 열 순회 |
| Decimal NULL | 기본 오버로드는 세 번째 인자에 `true`를 넘긴다. 비삭제 행에서 Decimal NULL은 0 속성, `false`면 해당 속성 생략이다. 삭제 행은 원본의 NULL 속성을 생략한다. | `DataUtil.cs` · 세 인자 오버로드 |
| 콤보 코드 | `syCode.BindingCode(id, …)`와 `BindingorgdivCode(id, orgdiv, …)`는 공통 코드 목록에 id가 있으면 같은 CODE/NAME 경로를 사용한다. 이 경로는 사업장 필터를 추가하지 않는다. 목록 밖의 id는 각각 `GetCode(id)`, `GetorgdivCode(id, orgdiv)`로 조회한 뒤 편집기에 바인딩한다. | `SystemCode.cs` · 두 Binding 메서드, `BindControls` |

예를 들어 스키마와 숨은 컨트롤의 `BindingField`가 모두 `ROW_KEY`면 해당 키가 마스터 행에 들어간다. 예시 행명이 `SAMPLE_ROWS`이면 SAVE의 경로는 `/ROOT/SAMPLE_ROWS`와 맞아야 한다. GBN을 소비하는 SAVE는 행 상태와 실제 XML 속성까지 대조한다.

화면 사용처는 `Konesystem.PR/PR200100.cs`의 콤보 초기화, 상세 바인딩, XML 작성이다. `Base/FrmDevBase.cs`에서 이 화면에 제공하는 `devFnc`와 `syCode`를 확인할 수 있다.
