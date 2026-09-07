---
name: code-review
description: Review actual changes for correctness, source-contract regressions, and appropriate verification before reporting completion.
---

# Code review

최신 diff와 실제 호출자를 읽고 사용자가 원한 결과를 기준으로 검토한다. 다른 프로젝트나 과거 복사본을 현재 동작 근거로 대신하지 않는다. 스타일 선호, 데이터/호환성 오류, 미확인 범위를 구분한다.

회귀 가능성이 있는 변경은 그 동작을 검증하는 테스트를 실행한다. 구현 문구를 그대로 확인하는 테스트와 고정된 리뷰어·점수·전체 테스트 반복은 피한다. LINQ·중간 테이블·빌드는 [선호와 예외](../work-execution/references/preferences.md)의 좁은 필요성 기준을 따른다.

발견 사항은 파일·위치·실제 영향·재현 조건으로 설명한다. 빌드 통과는 화면 레이아웃·DB 저장·실제 에이전트 실행의 증거가 아니다. 사용자의 완료 기대가 실제 적용을 포함하면 파일 생성과 적용 상태를 구분하고 허용된 적용까지 끝낸다. 확인하지 못한 항목은 명확히 남긴다.
