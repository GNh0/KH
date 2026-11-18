# Antigravity에서 KH 사용

Antigravity용 정의는 `.antigravity-plugin/plugin.json`과 루트의 `hooks.json`이다. 호스트가 플러그인 루트에서 `python -B scripts/kh_antigravity.py`를 시작한다. `agy plugin validate --json <KH>`로 설치 전 로더를 확인할 수 있다. 데스크톱 앱과 CLI는 따로 배포될 수 있다. [플러그인 형식과 검증](https://antigravity.google/docs/build-plugins)

- **선택**  예를 들어 `/sql-formatting edit Query.sql`은 이 패키지의 SKILL.md를 `view_file(IsSkillFile=true)`로 여는 데 성공한 뒤 해당 파일에 적용한다. `$kh-uaf:sql-formatting --target Query.sql`은 KH와 소유 파일을 직접 지정한다. 여러 파일은 `--target`을 반복한다. C#과 PB에는 해당 스킬명을 쓴다. 수정 대상이 모호하거나 검토 요청인 경우, 같은 작업공간의 다른 파일과 타 패키지의 동명 스킬은 자동 검사에서 제외한다.
- **저장 확인**  명시한 대상의 `write_to_file`, `replace_file_content`, `multi_replace_file_content`에서 원본과 복원 가능한 초안의 차이를 검사한다. 호스트의 기존 승인 결정을 유지한다. 성공 후 실제 저장본 해시와 호출 단계가 일치해야 차이 검사 결과를 사용한다. 원본이 없거나 저장 결과가 다르면 저장본 단독 검사로 표시한다. 오류가 난 호출, 셸·외부 프로그램의 수정, 동적 경로에는 자동 검사 결과가 없다.
- **연속 저장과 인계**  진단을 전달하기 전에 같은 파일을 여러 번 저장하면 최초 수정 직전 원본과 마지막 저장본을 대조한다. 원본은 대화·작업공간별 KH 임시 저장소에 파일당 최대 1 MiB, 최대 16개까지 보관한다. 전달·종료·요청 변경 시 더 이상 쓰이지 않는 사본을 지운다. 요청 본문은 저장하지 않는다.
- **결과 전달**  다음 `PreInvocation`에서 저장본별 진단을 한 번 전달한다. 그 전에 정상 종료가 오면 `fullyIdle`과 종료 이유를 확인해 남은 검토 항목을 한 번 전달한다.
- **확인 범위**  Google의 PostToolUse에는 도구 인자와 오류만 전달된다. 에이전트가 실제로 받은 본문, 비교 소스 읽기·적용 영수증, 전체 SP 작성자 선택, 하위 작업 종료·독립 검토는 자동 확인할 수 없다. Codex/Claude용 `apply` 인자는 이 어댑터에 발급되지 않는다. 실제 원본·비교 프로그램과 변경 전후 대조는 도메인 스킬 절차로 확인한다. [훅 이벤트 계약](https://antigravity.google/docs/hooks)

패키지 회귀 검사는 공식 형식의 stdin/stdout과 실제 테스트 파일을 사용한다. 로컬 앱의 플러그인 설치·활성화·호스트 호출 여부는 해당 호스트에서 별도로 확인한다.
