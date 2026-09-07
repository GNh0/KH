# C#와 SELECT/SAVE

PB의 retrieve/update 경로와 C#가 보내는 파라미터/XML, SP의 결과 테이블·채번·NEW/MOD/DEL·검증 위치를 대응시킨다. SELECT/SAVE 둘 다 필요한 요청을 한쪽만 완료하지 않는다. 원본 검증을 삭제하거나 C#에서 일괄 덮어쓰는 방식으로 대체하지 않는다.

SQL 생성·정리는 [SQL 스타일](../../sql-formatting/references/style.md)을 사용한다. 단순 스타일 비교는 데이터 동작의 증거가 아니다. 실제 DB 수정 요청에서는 정확한 서버/DB/대상과 사후 결과를 확인한다. DB 전용 SQL 파일을 C# 프로젝트 항목에 자동 등록하지 않는다.
