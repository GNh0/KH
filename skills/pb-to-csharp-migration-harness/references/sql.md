# C#와 SELECT/SAVE

PB의 retrieve/update 경로와 C#가 보내는 파라미터/XML, SP의 결과 테이블·채번·NEW/MOD/DEL·검증 위치를 대응시킨다. SELECT/SAVE 둘 다 필요한 요청을 한쪽만 완료하지 않는다. 원본 검증을 삭제하거나 C#에서 일괄 덮어쓰는 방식으로 대체하지 않는다.

선택한 호출 한 개와 실제 SP 정의의 매개변수 이름/필수값은 다음 명령으로 비교한다. 화면 전체 대신 해당 호출 조각을 제공한다.

```powershell
python <plugin-root>/scripts/kh_check.py sp-call <absolute-selected-call.cs> <absolute-procedure.sql>
```

계산으로 정해지는 매개변수 이름은 미확인으로 남긴다. 통과는 이름/필수 매개변수 비교 범위이며 OUTPUT/INPUTOUTPUT 방향, 반환값 회수, XML 내용, 실제 API의 기본값은 별도 확인한다.

SQL 생성·정리는 [SQL 스타일](../../sql-formatting/references/style.md)을 사용한다. 단순 스타일 비교는 데이터 동작의 증거가 아니다. 실제 DB 수정 요청에서는 정확한 서버/DB/대상과 사후 결과를 확인한다. DB 전용 SQL 파일을 C# 프로젝트 항목에 자동 등록하지 않는다.

`scripts/extract_sql.py` 출력의 `datawindow_retrieve`는 DW의 따옴표 값에서 추출한 조회문, `embedded_sql`은 PowerScript SQL 문장, `string_candidate`는 조립 여부를 확인할 문자열 조각이다. `complete`는 추출 경계가 확인됐다는 뜻이며 SQL 유효성이나 실행 성공을 뜻하지 않는다. 줄·offset·source_name으로 원본을 확인한다. 동적인 `DataObject` 대입은 `unresolved_dataobjects`로 남기고 이름을 추정하지 않는다.
