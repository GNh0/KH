---
name: kh-maintenance
description: Maintain or audit this KH plugin, its SQL/C#/PB checkers, scoped profiles, packaging, and explicitly requested conversation-history scenarios.
---

# KH maintenance

KH 자체의 스킬·검사기·패키지·대화 감사 요청에 사용한다. 일반 업무 작업의 선행 관문으로 실행하지 않는다.

스킬 변경에는 현재 skill-creator 지침을 적용한다. 기존 오류 하나나 예시 이름을 전역 금지 규칙으로 추가하지 않는다. 실제 소스/API·사용자 요구·검증된 프로필과 검사 결과를 구분한다.

- 패키지 확인: `python <plugin-root>/scripts/kh_check.py package <absolute-plugin-root>`.
- 검사기 변경의 타입·회귀 검증: [개발 검사](../../docs/development.md).
- 프로필 유지보수: [PB/C# 프로필](references/pb-profile-maintenance.md).
- 명시적 대화 감사: [원문 로그 감사](references/session-audit.md).
- 현실적인 동작 평가: [시나리오 평가](references/scenario-evaluation.md).

실제 발견된 스킬과 경로를 검사한다. 테스트 수, 자기평가 점수, 역할 JSON, 모의 실행을 실제 Codex 실행으로 기록하지 않는다. source/branch/manifest/설치 cache를 구분하고 설치·배포는 실제 요청 범위에서 처리한다.
