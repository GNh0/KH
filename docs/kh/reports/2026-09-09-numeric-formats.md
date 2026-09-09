# KH 3.0.5: 숫자 형식 선호와 DisplayFormat 적용 위치

숫자 형식이 필요한 위치에서는 표준 N 형식보다 사용자 지정 형식을 우선하도록 C# 스킬과 검사기를 보완했다. 이 선호는 DisplayFormat이나 EditMask 속성을 추가하는 근거가 아니다.

| 기존 표기 | 우선 예시 | 허용하는 다른 사용자 지정 형식 |
| --- | --- | --- |
| N0 / {0:N0} | #,##0 / {0:#,##0} | #,### / {0:#,###} |
| N2 / {0:N2} | #,##0.## / {0:#,##0.##} | #,###.## / {0:#,###.##} |

0 표시와 고정/최대 소수 자리는 실제 요구를 따른다. #,###은 0을 생략할 수 있고, 소수부 ##는 불필요한 뒤쪽 0을 채우지 않는다. 두 자리를 항상 표시해야 하면 #,##0.00을 쓴다. 문화권·반올림·음수 표시·수치 데이터 타입은 임의로 바꾸지 않는다. [Microsoft 형식 설명](https://learn.microsoft.com/en-us/dotnet/standard/base-types/custom-numeric-format-strings)

## DisplayFormat 지적과 이후의 명시적 요청

사용자가 지정한 작업에서 숫자 편집기 연결을 의심하는 지적 뒤에 Repository 3개에 DisplayFormat.FormatString·FormatType 대입 6개를 추가했고, 해당 속성의 검사 경고도 출력됐다. 스킬 3.0.4를 읽은 기록이 있어 이 시점의 임의 추가를 단순한 구버전 사용이나 검사 누락으로 설명할 수 없다.

후속 대화와 실제 소스를 추가로 대조하자, 비교 화면에는 공통 폼에서 호출하는 초기화 helper가 있고 그 안에서 Spin Repository에 Numeric과 `"{0:#,###,###,##0.####}"`를 적용하고 있었다. 대상 모니터링에는 그 초기화 경로가 없었다. 사용자는 이 차이를 확인한 뒤 같은 설정을 적용하라고 명시했고 정확한 형식 문자열도 지정했다. 따라서 그 이후 여섯 화면에 동일 형식을 적용하는 것은 사용자가 요청한 변경이다. 앞선 감사는 이 후속 요청을 확인하기 전에 판단한 범위가 불완전했으며, 승인 전 임의 추가와 승인 후 적용을 구분하도록 정정했다.

SpinEdit 연결은 선언·생성·등록·ColumnEdit·재생성 경로로 확인한다. 소수점 뒤 0이 보인다는 사실만으로 연결 실패를 확정하지 않는다. 기본값 설명에는 실제 공통 초기화 호출과 적용 조건을 포함한다. 이미 실행되는 초기화는 Designer에 중복 대입하지 않으며, 그 경로가 없는 대상에 동일 동작을 명시적으로 요청하면 확인한 형식과 정밀도를 적용한다. 최대 네 자리 형식을 일반적인 두 자리 예시로 줄이거나 다른 옵션까지 복사하지 않는다. 이번 작업은 KH를 수정했으며 진행 중인 다른 작업의 업무 파일은 읽기만 했다.

합계용 SummaryItem.DisplayFormat과 Summary 생성자의 형식 인수는 실제 합계 표시 위치다. [DevExpress 합계 속성](https://docs.devexpress.com/WindowsForms/DevExpress.XtraGrid.GridSummaryItem.DisplayFormat)에 사용자 지정 형식을 쓰는 요청을 일반 셀·Repository의 DisplayFormat 설정으로 확대하지 않는다.

## 구현과 검증

- [숫자 형식 검사](../../../src/csharp/numeric_format.py)는 직접 형식 대입, Summary 생성자, ToString, string.Format과 정적 보간 형식을 검토한다. 일반 문자열·주석·이스케이프 중괄호·연결식 조각을 형식으로 오인하지 않도록 회귀 사례를 추가했다.
- C#·Designer 명령 모두 numeric_format_preference를 표시한다. 원본의 같은 문맥/형식 발생은 보존하며 소스 자동 치환은 하지 않는다.
- [그리드 검사](../../../src/csharp/grid_style.py)는 SummaryItem.DisplayFormat을 일반 셀 기본값과 구분한다. 셀·Repository DisplayFormat에는 # 형식이어도 기본값 경고가 유지되고, 중첩 컨트롤의 DisplayFormat도 계속 검토한다.
- 속성의 기본 스타일 예외를 지정해도 숫자 형식 선택의 검토는 남긴다. 확인한 공통 형식의 명시적 적용 요청에는 정확한 두 속성의 예외를 허용하는 사례도 검증했다. status=passed만으로 스타일 준수를 보고하지 않고 issues와 현재 사용자 요구를 대조한다.
- Python 3.12.14·3.14.2에서 도메인 검사 211개 통과, Pyright 1.1.413에서 실행 파일 58개 오류·경고 0.
- Windows PowerShell의 .NET Framework decimal 형식으로 33개 표시 사례를 확인했다. 0/양수/음수, 선택 소수 자리와 고정 소수 자리, 요청한 복합 형식의 `283.0000 → 283`, `2.5000 → 2.5`, 소수 네 자리 보존을 포함한다. ERP 빌드나 DevExpress 화면 실행을 수행한 결과는 아니다.

동적 형식 변수·임의의 formatter·실제 오버로드 타입·런타임 문화권은 정적으로 확정하지 않는다. string.Format의 문화권 인수는 직접 보이는 CultureInfo 표현만 구분한다. 경고는 표기 선호의 검토 자료이며 전체 C# 의미 검사나 앞으로의 모든 에이전트 준수를 보장하지 않는다. 자세한 사용 기준은 [C# 작성 방식](../../../skills/csharp-designer-style-harness/references/coding-style.md)과 [검사 범위](../../../skills/csharp-designer-style-harness/references/checks.md)에 있다.
