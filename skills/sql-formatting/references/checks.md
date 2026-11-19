# SQL 검사 실행

KH 루트의 `scripts/kh_check.py`에 원본과 초안/저장본을 전달한다.

| 작업 | 명령 인자 |
| --- | --- |
| 기존 SP 로직 변경 전·후 | `sql <원본.sql> <후보.sql> --review-changes --procedure-header` |
| 신규 SP | `sql <신규.sql> --procedure-header --author <확인한 이름>` |
| 의미 보존 서식 정리 | `sql <원본.sql> <정리본.sql>`. 별칭 유지 요청은 `--preserve-aliases` 추가 |
| SELECT·SAVE를 쓰는 화면 | `screen-contract <caller.cs> <SELECT.sql> <SAVE.sql> --designer <Designer.cs>` |

`locking_hint`, `save_mode_early_exit`, `save_multiple_commit`, `count_variable`, `rowcount_count_variable`, `scalar_sequence_base`, `staging_sequence_update`, `intermediate_table`, `unused_variable`, `single_use_variable`은 원본에 있던 형태도 오류로 보고한다. 근거를 설명해 넘기지 말고 [SAVE 고정 규칙](save-patterns.md#save-고정-규칙)대로 고친다. 사용자가 이번 작업에서 잠금 힌트를 명시 요청했을 때만 `--allow-locking-hints`를 붙인다. 서식 정리 비교(`sql <원본> <정리본>`)에서는 같은 항목이 info로 표시되며 바꾸지 않고 보고한다.

후보에서 추가·변경한 모드, 쓰기, 호출 위치와 반환 형식을 요청·실제 호출자·선택한 작성자의 같은 역할 SP와 대조한다. 초안은 실행·롤백 테스트 전에 확인하고 저장된 정의에서 다시 검사한다. 변경 전 원본이 없으면 보존 여부는 미확인이다. 같은 파일을 원본·후보로 중복 전달하지 않는다.

헤더는 [작성자 규칙](procedure-authorship.md)을 따른다. 기존 로직 전체의 교정을 요청받으면 저장본 단독 검사도 함께 확인한다. 경고나 불완전 결과는 해당 원본·실행 흐름을 점검한다. 옵션·진단 범위는 [SQL 체커 상세](../../../docs/checkers/sql.md)를 참조한다.
