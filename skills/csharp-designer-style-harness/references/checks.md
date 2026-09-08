# 선택적 C# 정적 검사

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
