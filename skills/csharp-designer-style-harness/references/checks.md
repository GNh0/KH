# C# 검사 실행

KH 루트의 `scripts/kh_check.py`에 실제 변경 전 원본, 대상 라이브러리, 같은 역할 비교 화면을 준다.

| 확인 대상 | 명령 인자 |
| --- | --- |
| 화면과 Designer | `csharp <screen.cs> --designer <screen.Designer.cs>` |
| 컨트롤 속성 | `designer <수정본.Designer.cs> --original <원본.Designer.cs> --control-source <control.cs> --style-reference-designer <비교.Designer.cs>` |
| 단일 호출의 파라미터 | `sp-call <단일호출.cs> <SP.sql>` |
| 화면↔프로시저 | `screen-contract <caller.cs> <SELECT.sql> <SAVE.sql> --designer <Designer.cs>` |

높이는 같은 화면의 보이는 동종 컨트롤·제약과 대조한다. 폰트·정렬은 실제 생성자·초기화·기존 비교 소스와 대조한다. 동적 모드·XML·결과 바인딩 또는 누락된 입력은 양쪽 원본에서 확인한다. 전체 교정에서는 차이 검사에서 제외된 기존 설정도 검토한다. 옵션·개별 진단은 [C# 체커 상세](../../../docs/checkers/csharp.md)를 참조한다.
