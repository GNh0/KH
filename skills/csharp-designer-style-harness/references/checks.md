# 선택적 C# 정적 검사

결과의 `status=passed`는 검사한 항목에 오류가 없다는 뜻이다. C# 결과는 경고가 있으면 `review_status=needs_review`, 없으면 `static_checks_only`를 표시하며 `project_style_verified=false`를 명시한다. 이는 작업 완료 판정을 하지 않는다는 의미다. 현재 사용자 요구와 이벤트 상태·API·저장 계약의 대조를 생략하는 통과 증거로 쓰지 않는다.

`comparison_baselines`는 원본 제공 여부다. 원본 없는 단일 파일 검사는 변경·보존 검증이 아니다. C#/Designer/SQL에서 원본과 후보에 같은 파일(링크로 같은 파일인 경우 포함)을 넘기면 입력 오류로 처리한다. 원본은 수정 전 사본 또는 사용자가 지정한 실제 이관 원본을 사용한다. 수정 후 사본을 만들어 원본이라고 입력하는 것도 보존 증거가 되지 않는다. 내용이 같은 별도의 정상 사본은 비교할 수 있으며, 검사기가 그 사본의 생성 시점·출처까지 보증하지 않는다.

`python <plugin-root>/scripts/kh_check.py csharp <absolute-source.cs> [--designer <absolute-Designer.cs>] [--original <absolute-before.cs>]`로 정적 UI 소유권·이벤트 참조·국소 코드 변경을 확인한다.

그리드 밖 컨트롤도 [사용자 컨트롤 기준](user-controls.md)을 적용한다. 새 컨트롤의 Spin/ymd/pn/grd/gvw/col/rps 등 합의한 명명, 멤버/Name 불일치, DateEdit의 EditFormat/입력 마스크 추가를 검토한다. `--control-source <absolute-control.cs>`를 반복하여 현재 프로젝트의 사용자 컨트롤 구현을 제공하면, 라이브러리 이름에 관계없이 상속 선언과 직접 기본 생성자 대입을 기준으로 타입 선택·기본값 덮어쓰기도 확인한다. C#과 Designer 양쪽 명령에서 지원한다. 소스가 없거나 helper·조건·동적 값인 부분은 자동 검증했다고 표시하지 않는다.

새로 작성하거나 바꾼 if/else/for/foreach/while/do 본문에서 중괄호가 빠지면 `control_body_braces` 경고를 낸다. 한 줄 return도 포함하며 else if 연결과 do 뒤의 while 조건은 구분한다. 문자열·주석은 코드로 취급하지 않으며 보간식 안의 실행 코드는 검사한다. 원본과 동일한 문장은 기존 코드 전체 정리 대상으로 다시 경고하지 않는다. 전처리 분기를 평가하지 않고 불완전하거나 지원하지 않는 문장의 구문 유효성은 확정하지 않는다. 줄 배치·명명·명시적 타입·helper 구성 등 작성 방식 전체를 자동 검증하는 포매터는 아니다.

명시적으로 유지할 Designer 속성은 별도 비교 명령으로 전달한다. `csharp --designer`만 실행한 결과는 해당 속성 보존의 증거가 아니다.

```powershell
python <plugin-root>/scripts/kh_check.py designer <absolute-after.Designer.cs> --original <absolute-before.Designer.cs> --preserve-property txtState.Text --preserve-property txtState.Visible
```

`--preserve-property`는 필요한 만큼 반복한다. 이벤트 구현도 확인하려면 `--code-behind <absolute-source.cs>`를 추가한다. 문자열 줄바꿈도 값의 일부이므로 LF와 CRLF를 임의로 같다고 처리하지 않는다.

그리드 작업은 셀/헤더 Appearance, SpinEdit의 EditMask, DisplayFormat의 FormatType/FormatString, 컬럼 편집 옵션, 새 OptionsBehavior·HTML 밖 옵션을 함께 검토한다. 원본이 있으면 기존과 같은 스타일은 다시 정리하라고 경고하지 않는다. OptionsBehavior는 제거도 변경으로 검토한다. 원본이 없으면 추가 여부를 확정하지 않고 현재 대입문을 검토 대상으로 표시한다.

```powershell
python <plugin-root>/scripts/kh_check.py designer <absolute-after.Designer.cs> --original <absolute-before.Designer.cs> --column-mode colLocked=read_only --column-mode colOpen=action --column-mode colInput=editable
```

명시한 컬럼 모드와 실제 속성이 다르면 계약 오류다. 모드를 지정하지 않은 검사는 AllowEdit=false의 ReadOnly 누락, 불필요한 기본값 대입 등을 경고할 수 있지만, 모든 컬럼의 업무상 편집 가능 여부를 추측하지 않는다. 버튼 Repository는 실제 선언 타입으로 확인하며, 이름만으로 판정하지 않는다.

특정 옵션을 바꾸라는 현재 지시나 구현 필요성을 확인한 경우 `--allow-property-change gvwList.OptionsView.ShowFooter`처럼 정확한 속성만 전달할 수 있다. 별도 승인 절차나 서명 파일은 필요 없다. 이 인자는 스타일 경고만 제외하며 명시한 컬럼 모드·보존 계약을 무효화하지 않는다. `csharp --designer` 검사에 Designer 원본도 제공하려면 `--designer-original <absolute-before.Designer.cs>`를 사용한다. code-behind의 동일 옵션 추가도 검사하며, Spin 등의 타입은 함께 제공한 Designer 선언에서 확인한다. 실제 선언을 확인한 KoneLib.Controls의 컨트롤은 알려진 기본 타입으로 다루며, 다른 사용자 컨트롤은 제공된 --control-source의 상속 선언을 따라 검사한다. using 별칭이나 제공되지 않은 임의의 상속 관계는 해석하지 않는다. 동적 런타임 속성·간접 변수도 정적으로 확정하지 못한다.

검사기는 C# 컴파일러나 Visual Studio Designer가 아니다. 실제 프로젝트에서 허용되는 동적 UI·helper·변경은 현재 지시/소스 근거와 함께 검토한다. 스타일 경고를 전역 금지나 별도 서명 승인으로 바꾸지 않는다. 복잡한 데이터 경로·DB 동작은 실제 소스와 도구로 확인한다.

LINQ 후보와 트랜잭션 이름 계열 변화는 검토 경고다. 메서드 이름만으로 LINQ 확장 메서드나 트랜잭션 손실을 확정하지 않는다. 실제 선언·인자·wrapper 본문과 프레임워크 API를 확인한다. Designer의 명시적 보존 속성은 문장 경계로 비교하며 일반·verbatim·raw 상수 문자열은 값으로 비교한다. 동적 식의 의미 동등성은 검사 범위 밖이다.

## 새 이벤트·데이터 처리 검토

C# 검사는 현재 메서드와 원본을 비교하여 다음 후보를 경고한다. 기존 같은 처리는 보존하며, 호출을 다른 이벤트로 옮기거나 다시 추가한 경우도 검토한다.

- `new_ui_data_helper`: 새로 선언한 조회·선택 행·테이블 복제 wrapper. 기존 메서드의 빈 본문을 구현하는 것과 구분한다.
- `entry_query_review`: NewCommand/EditCommand 형태의 이벤트에 추가한 조회. 빈 테이블 스키마 조회 등 필요한 경우도 있으므로 자동 제거하지 않는다.
- `save_gate_review`: 저장 이벤트/CallSaveProcedure에 추가한 메시지와 return 조건. 기존 검증·실패 처리 및 현재 요청과 대조한다.
- `manual_selected_row_delete`, `client_sequence_review`, `row_header_propagation_review`: 수동 선택 행 삭제, RowVersion과 최대값을 이용한 순번 후보, 새 행으로의 헤더/문맥 필드 복사. 실제 API와 XML/SP의 담당 범위를 확인한다.
- `date_helper_review`: 원본의 같은 멤버가 SetToDay를 쓰거나, `--control-source`로 제공한 실제 타입이 SetToDay(int)를 제공하는데 DateTime.Today/Now를 직접 대입한 경우. 제공되지 않은 API를 추측하지 않는다.
- `ui_state_policy_review`: bool 필드가 새로 편집 모드·Enabled/ReadOnly·입력 취소·컨트롤 보호·이벤트 제한에 쓰이는 경우. 기존 필드라도 제한 적용 위치가 바뀌면 검토한다. 필드 선언부터 초기화·조회 대입·사용처까지 대조하며, 이름 변경과 실제 정책 변경을 구분한다. 상수·읽기 전용 필드와 단순 지역 bool은 이 후보에 포함하지 않는다.

이 항목은 구조를 인식하는 경고이며 모든 검증·반복문·helper·재조회를 금지하지 않는다. 메서드 별칭, 간접 호출, 지역 함수 내부, 조건별 실행 순서, 실제 서버 채번·필수 필드는 자동 판정하지 못한다. 원본 주석 본문의 완전한 보존도 이 검사에 포함되지 않으므로 해당 요청은 실제 본문으로 따로 대조한다. 새 helper 추가 여부를 비교하려면 `--original`이 필요하다. 필요한 실제 컨트롤 소스는 기존 `--control-source` 인자로 전달하며 사용자에게 새 프로필이나 승인 파일을 요구하지 않는다.

## 원본 Designer 속성 보존

원본 유지 이관은 C#의 `--original`, `--designer-original`을 제공하고 `--preserve-existing`으로 남긴 컨트롤과 폼의 명시적 대입을 비교한다. Designer 단독 명령도 `--original`과 `--preserve-existing`을 지원한다. 이름이 바뀌면 `--member-rename oldName=newName`을 반복한다. 예:

```text
python <plugin-root>/scripts/kh_check.py csharp <after.cs> --original <source.cs> --designer <after.Designer.cs> --designer-original <source.Designer.cs> --preserve-existing --member-rename txt_old=txtOld
```

이름 대응은 메모리 안에서 식별자·Name·직접 resources.GetObject/GetString 키에 적용하며 실제 원본 파일은 수정하지 않는다. 일반 Text·BindingField 문자열은 이름과 같아도 바꾸지 않는다. 존재하지 않는 원본 멤버·중복 대상·원본 멤버 충돌은 오류다.

결과의 `designer_preservation`에서 비교한 멤버 수, 속성 차이, 대응되지 않은 원본 멤버와 새 멤버를 확인한다. 차이는 컨트롤별 `designer_existing_properties_changed` 경고로 나온다. 필요한 바인딩·위치 변경 등은 실제 요청을 근거로 `--allow-property-change currentMember.Property`를 지정할 수 있다. 폼 속성은 `form.ClientSize`처럼 지정한다. 제외 항목은 검증 완료가 아니며, 기존 `--preserve-property`의 명시적 보존 오류를 지우지 않는다.

삭제·새 컨트롤이 자동 승인된다는 뜻은 아니다. 대응되지 않은 목록을 요청한 삭제·추가 목록 및 resx 참조와 대조한다. 전부 이름이 달라 비교 대상이 없으면 incomplete다. 컬렉션 Add/AddRange, 초기화 순서, 조건·간접 대입, 실제 자원 본문과 런타임 동작은 별도 확인한다.

## 실제 숫자 컬럼과 검사 예외

C#/Designer 명령의 --numeric-column colList_QTY를 반복해 실제 숫자 컬럼의 Spin Repository 연결을 확인한다. 필드명으로 숫자 타입을 추측하지 않으며, 명시한 연결은 원본과 같아도 검사한다. csharp --designer 명령은 명시적인 code-behind ColumnEdit 덮어쓰기도 확인한다. designer 명령의 숫자 연결 검사는 제공한 Designer 대입을 대상으로 한다. 조건별 실행·동적 컬럼 생성은 정적 검사로 확정하지 않는다.

--allow-property-change를 사용하면 결과의 style_exemptions와 not_checked에 제외 범위를 남긴다. 변경 목록을 그대로 예외 목록으로 복사해 통과시키지 않는다. 해당 옵션은 사용자 허가나 비선호의 필요성 근거가 아니며, --preserve-property 등 명시적 보존 계약을 무효화하지 않는다.

공통 초기화가 없는 대상에 같은 숫자 표시를 적용하라는 현재 명시적 요청과 실제 원본 설정을 확인했다면, 해당 Repository의 DisplayFormat.FormatString·FormatType만 정확히 예외로 전달할 수 있다. 이는 불필요한 기본값 추가와 구분한다. 검사기는 공통 helper 호출 여부나 대화의 최신 요청을 자동 판정하지 않으므로, 그 근거와 적용 범위를 별도로 확인한다. 제외 결과 자체가 같은 근거를 대신하지는 않는다.

전체 스타일 재검토 요청에서는 원본 보존 비교와 후보 자체의 스타일 검사를 함께 판단한다. 원본을 준 변경분 검사에서 기존 코드가 그대로라는 이유만으로, 전체 소스의 중괄호·명명·연결이 맞는다고 보고하지 않는다. 스타일 수정 범위와 사용자 변경 보존은 동시에 지킨다.

## 숫자 형식의 표기와 설정 위치

numeric_format_preference는 새 N0·N2·Nn 형식 사용을 검토 경고로 표시한다. 직접 FormatString/DisplayFormat/EditMask 대입, GridColumnSummaryItem·GridGroupSummaryItem 생성자의 복합 형식, ToString의 첫 형식 인수, string.Format, 보간식의 정적 형식 지정자를 확인한다. 문자열·주석의 단순 N0와 이스케이프된 중괄호는 형식 사용으로 간주하지 않는다. 원본이 있으면 같은 문맥/형식의 기존 발생 수를 제외하며 기존 파일을 자동 수정하지 않는다.

알 수 없는 형식 변수·연결식·사용자 정의 formatter·실제 오버로드 타입은 확정하지 않는다. string.Format의 문화권 오버로드는 직접 보이는 CultureInfo 인수만 구분한다. 일반 C# 문자열 변수가 숫자인지는 이 검사로 증명하지 못한다. 사용자 지정 형식 후보가 표시되어도 0·고정 소수·문화권·반올림 의미를 대조해야 한다.

SummaryItem.DisplayFormat은 합계 형식이므로 일반 셀의 display_format_preference 대상에서 구분한다. 컬럼/Repository의 DisplayFormat은 # 형식을 사용해도 기존 기본값 검토가 그대로 적용된다. --allow-property-change는 속성의 기본 스타일 검사를 제외할 뿐 N 형식을 쓰라는 요구를 만들지 않으며 숫자 표기 검토는 별도로 남긴다.

status=passed와 종료 코드 0만으로 스타일 준수를 보고하지 않는다. display_format_preference가 있으면 현재 사용자의 미사용 지시·설정 위치·실제 초기화와 대조한다. Spin 연결이나 소수점 표시 문제를 임의의 속성 추가 예외로 판단하지 않는다.
