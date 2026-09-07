---
name: work-execution
description: Carry out an approved multi-step plan with current Codex tools, scoped changes, and resumable progress when coordination is needed.
---

# Work execution

승인된 결과까지 현재 계획을 이어서 수행한다. 후속 정정과 사용자가 직접 바꾼 현재 파일을 매 변경의 기준으로 삼는다. 중단 요청이면 진행 중 프로세스와 위임도 멈추고 명시적 재개 또는 사용자가 예약한 시각에 이어간다.

Goal을 요청하면 현재 native Goal 도구를 사용한다. 요청하지 않은 토큰 예산이나 별도 KH 목표 저장소를 만들지 않는다. 호스트가 지원하지 않는 인자를 추측하지 않는다. 하위 에이전트와 사용자의 별도 작업 생성은 구분하고 현재 협업 정책을 따른다.

완료와 blocked 판정은 현재 Goal 도구 계약을 따른다. 첫 실패·단순 대기·정적 검사만으로 전체 완료를 선언하지 않는다. 사용자 중단 뒤 자동 Goal 메시지가 와도 명시적 재개 또는 예약 시각 전에는 작업을 계속하지 않는다.

- 독립 위임이 실제로 필요하고 허용되면 [작업 전달](references/delegation.md)을 읽는다.
- Windows 명령·백그라운드 프로그램은 [Windows 실행](references/windows-commands.md)을 참고한다.
- 실제 비밀 정보가 포함된 입력을 다룰 때만 [비밀 정보 취급](references/secret-handling.md)을 읽는다.
- 비선호 방식의 필요성을 판단할 때는 [선호와 예외](references/preferences.md)를 읽는다.

작업과 의미 있는 진행을 전달한다. 오류·중단·미실행을 성공으로 기록하지 않는다. 사용자가 원하는 전체 코드/SQL 또는 최종 교체문을 완성해 제공하고 변경한 프로그램 ID와 확인 범위를 알린다.

사용자의 언어와 원하는 상세도에 맞춰 결론부터 차분하게 답한다. 모든 사용자에게 한국어를 강제하지 않는다. 모델·도구 비교에는 확인 날짜와 실제 제품·버전·근거를 구분한다.
