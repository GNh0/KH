# 선택적 SQL 검사

`python <plugin-root>/scripts/kh_check.py sql <absolute-original.sql> <absolute-candidate.sql>`로 리터럴·주석·토큰·별칭 참조 보존과 스타일 진단을 확인한다. `--preserve-aliases`는 명시적 별칭 유지에 사용한다. 결과는 SQL Server 실행 증명이 아니다.

`--normalize-layout`은 입력의 지원되는 JOIN/EXISTS 공백만 정리해 stdout으로 반환한다. 파일은 자동 덮어쓰지 않는다. 별칭의 업무 역할은 Codex가 현재 쿼리와 사용자 지시로 판단한다. `src.sql.aliases`는 명시한 스코프/별칭 변경만 기계적으로 적용한다.

오류는 실제 보존 위반, 경고는 스타일/비선호 확인 항목이다. 지원하지 않는 구문이나 의미 변경은 미확인으로 남기고 성공으로 설명하지 않는다. 서명·provider 영수증·해시를 받기 위한 별도 재시도 절차는 없다.
