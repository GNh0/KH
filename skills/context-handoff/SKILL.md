---
name: context-handoff
description: Capture or restore a compact checkpoint for an ongoing task when the user requests handoff or long work needs reliable continuation.
---

# Context handoff

현재 목표·승인 범위·최신 정정·변경 파일·검증 결과·다음 작업을 짧게 남긴다. 장문의 도구 출력을 복사하지 말고 필요한 실제 파일과 오류 위치를 연결한다.

재개할 때 현재 파일/프로세스와 중단 상태를 확인한다. 완료한 단계는 반복하지 않고 새 피드백을 기존 목표에 반영한다. 사용자의 중단과 예약 재개 시각을 유지한다.

인계문에 적힌 스킬 이름·캐시 버전 경로는 현재 세션의 스킬 목록과 대조한다. 현재 경로가 제공되면 그 경로를 사용하고, 제거된 하네스의 검색이나 사용 여부 표를 인수인계 절차에 추가하지 않는다.

이것은 현재 작업의 인계 자료다. 자동 영구 메모리, 전체 세션 검색, 별도 Goal ledger, snapshot/rollback 시스템을 만들지 않는다. 메모리 갱신이나 다른 작업 생성은 현재 사용자의 명시적 요청과 호스트 도구 계약을 따른다.
