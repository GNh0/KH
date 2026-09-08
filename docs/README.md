# KH 문서

현재 사용법은 [한국어 README](../README.ko.md)와 `skills/*/SKILL.md`다. 실행 지침으로 쓰는 문서는 현재 스킬에서 연결한 참고 파일이다.

## 2026-09-07 재구성

- [구현 및 검증 결과](kh/reports/2026-09-07-codex-implementation.md): 실제 변경, 요구별 반영 위치와 수행한 검사 및 미확인 범위.
- [3.0.1 검사기 보강](kh/reports/2026-09-07-checker-hardening.md): 실제 평가 반례, 타입 검증과 독립 사용 평가 결과.
- [3.0.2 그리드 기본값](kh/reports/2026-09-08-grid-style.md): 사용자 HTML 출력, Appearance·편집·표시 속성과 실제 독립 작성 평가.
- [3.0.3 C#·사용자 컨트롤](kh/reports/2026-09-08-csharp-user-controls.md): 실제 작성 방식, 모든 사용자 컨트롤의 기본값 유지, Name 규칙 복구와 두 건의 독립 작성 평가.
- 설계 계획과 C#·PB·SQL 대화 감사 원문은 로컬 작업 자료로 보존한다. 공개 보고서에는 48개 요구의 반영 위치와 관찰한 실패 원인 요약을 담았다.

## GitHub 배포

`main`과 `codex-runtime`은 같은 소스 패키지를 제공하며 버전은 `.codex-plugin/plugin.json`을 기준으로 확인한다. 기존 마켓플레이스 이름 `kh-uaf-marketplace`, 플러그인 이름 `kh-uaf`, 설치 대상 ref `codex-runtime`을 유지한다. GitHub 다운로드에도 현재 문서와 테스트 입력을 포함한다. 원격 게시와 사용 중인 Codex 설치 캐시의 갱신은 별도 단계다.

## 역사 자료

이 재구성 이전의 `kh/front-door-*`, `kh/handoffs`, `kh/qa`, `kh/reports` 문서와 `skillbook` 전체는 2.9 계열의 역사 자료로 원문을 보존한다. 삭제된 소스·명령·스킬을 가리키는 과거 링크는 당시 상태를 설명한다. 자동 intake·HMAC·역할 DAG·자기평가·중복 상태 관리 지침을 현재 작업에 적용하지 않는다. 당시 수치와 통과 기록은 현재 설치본이나 새 코드의 성공 증거가 아니다.
