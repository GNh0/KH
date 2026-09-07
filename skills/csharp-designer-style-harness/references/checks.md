# 선택적 C# 정적 검사

`python <plugin-root>/scripts/kh_check.py csharp <absolute-source.cs> [--designer <absolute-Designer.cs>] [--original <absolute-before.cs>]`로 정적 UI 소유권·이벤트 참조·국소 코드 변경을 확인한다.

명시적으로 유지할 Designer 속성은 별도 비교 명령으로 전달한다. `csharp --designer`만 실행한 결과는 해당 속성 보존의 증거가 아니다.

```powershell
python <plugin-root>/scripts/kh_check.py designer <absolute-after.Designer.cs> --original <absolute-before.Designer.cs> --preserve-property txtState.Text --preserve-property txtState.Visible
```

`--preserve-property`는 필요한 만큼 반복한다. 이벤트 구현도 확인하려면 `--code-behind <absolute-source.cs>`를 추가한다. 문자열 줄바꿈도 값의 일부이므로 LF와 CRLF를 임의로 같다고 처리하지 않는다.

검사기는 C# 컴파일러나 Visual Studio Designer가 아니다. 실제 프로젝트에서 허용되는 동적 UI·helper·변경은 현재 지시/소스 근거와 함께 검토한다. 스타일 경고를 전역 금지나 별도 서명 승인으로 바꾸지 않는다. 복잡한 데이터 경로·DB 동작은 실제 소스와 도구로 확인한다.

LINQ 후보와 트랜잭션 이름 계열 변화는 검토 경고다. 메서드 이름만으로 LINQ 확장 메서드나 트랜잭션 손실을 확정하지 않는다. 실제 선언·인자·wrapper 본문과 프레임워크 API를 확인한다. Designer의 명시적 보존 속성은 문장 경계로 비교하며 일반·verbatim·raw 상수 문자열은 값으로 비교한다. 동적 식의 의미 동등성은 검사 범위 밖이다.
