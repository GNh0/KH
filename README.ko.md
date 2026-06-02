# KH Universal Agent Framework

[English](README.md) | [한국어](README.ko.md)

KH UAF는 Codex, Antigravity 계열 에이전트, Claude Code, 로컬 워커에서 공통으로 쓰기 위한 로컬 우선 스킬/하네스 프레임워크입니다.

핵심 목표는 사용자가 `KH`, `UAF`, 특정 스킬명, 하네스명을 직접 말하지 않아도 일반적인 작업 요청에서 필요한 스킬과 하네스가 자동으로 선택되고, 실제 실행 증거가 남도록 하는 것입니다.

## 포함 항목

- `skills/<skill-folder>/SKILL.md` 기반 패키지 스킬/하네스 40개
- 비명시 요청을 먼저 잡는 `always-on-front-door`
- 실제 intake를 수행하는 `automatic-intake-harness`
- KH front-door 자동 라우팅과 plugin composition 정책
- CEO, advisor, architect, planner, controller, implementer, reviewer, QA, security, release 역할 DAG
- 역할별 산출물, 병렬 오케스트레이션, role execution audit
- GoalState, memory, snapshot, resume handoff
- review, QA, security, release evidence gate
- 긴 명령 출력과 subagent transcript를 위한 token/command-output 최적화
- 작업 유형별 사용자 산출물 export
- KH-Bench, SIDE 평가 테스트, practical quality gate

## 자동 인테이크 계약

사용자가 내부 이름을 모르더라도, 요청이 다음 중 하나를 포함하면 소스 탐색이나 수정 전에 KH front-door를 먼저 실행해야 합니다.

- 프로젝트 파일 작업
- 코드 수정 또는 구현
- 사용자 산출물 생성
- 긴 로그 또는 명령 출력 요약
- 리뷰, QA, 검증
- 브랜치 마무리
- 서브에이전트 사용
- 지속 상태, 메모리, resume
- 고위험 또는 파괴적 작업

권장 실행:

```bash
python skills/always_on_front_door/scripts/front_door.py --prompt "<user request>" --project "<target project>" --host codex --summary
```

front-door 결과는 다음을 구분해야 합니다.

- `runtime_applied_skills`: 실제 런타임에서 적용된 스킬
- `selected_not_executed_skills`: 다음 단계 후보로 선택됐지만 아직 실행 증거가 없는 스킬
- `skill_status_summary`: 각 스킬의 적용 상태, 적용 방식, 근거, 차단 이유

단순 개념 설명, 짧은 번역, 한 줄 답변처럼 light/direct로 분류되는 요청은 무겁게 처리하지 않습니다.

사용자가 한 번이라도 "앞으로 KH 스킬/하네스를 적극적으로 써라", "항상 KH를 활용해라"처럼 대화나 프로젝트 범위의 지시를 했다면 이후 작업성 요청에는 `kh_active_directive=active`가 유지되어야 합니다. 후속 요청에서 KH 이름을 다시 말하지 않아도 front-door를 먼저 실행해야 하며, 이를 빼먹으면 `session-skill-audit`가 P1 누락으로 잡습니다.

## Codex 플러그인 설치

Codex 앱에서 `Plugins -> Manage -> Add marketplace`를 열고 다음 값을 입력합니다.

```text
Source: https://github.com/GNh0/KH.git
Git ref: main
Sparse path: .agents/plugins
```

`main`은 marketplace 설정을 제공하고, 실제 플러그인은 `codex-runtime` 브랜치에서 설치되도록 구성되어 있습니다. 설치 또는 업그레이드 후에는 새 세션을 열어 Codex가 최신 스킬 파일을 다시 로드하게 해야 합니다.

업그레이드 참고: 새 플러그인 빌드를 배포할 때는 `.codex-plugin/plugin.json`과 루트 `plugin.json`의 `version`을 함께 올려야 합니다. marketplace가 최신이어도 설치 캐시가 이전 버전이면 Codex에서 업그레이드한 뒤 새 세션으로 다시 검증해야 합니다. 이 작업은 버전 bump가 필요합니다.

Codex 서브에이전트 참고: 일부 Codex Desktop 서브에이전트 세션은 `$CODEX_HOME/skills`의 개인 스킬은 받지만, 부모 세션의 개인 marketplace 플러그인 스킬은 받지 못할 수 있습니다. 블라인드 서브에이전트 테스트에서 KH 스킬이 목록에 없다면 KH 플러그인 설치 후 얇은 전역 bootstrap 스킬을 설치합니다.

```powershell
$env:CODEX_HOME="$env:USERPROFILE\.codex"
python scripts\install_codex_global_bootstrap.py --codex-home "$env:CODEX_HOME"
```

이 명령은 `$CODEX_HOME/skills/kh-uaf-front-door/SKILL.md`를 만듭니다. 이 전역 스킬은 KH UAF를 복제하지 않고 최신 `kh-uaf@kh-uaf-marketplace` 설치 캐시를 찾아 `skills/always_on_front_door/scripts/front_door.py`를 먼저 실행하게 합니다.

설치 상태 점검:

```bash
python -m src.orchestration.plugin_install_audit --summary
```

## Antigravity 플러그인 설치

전역 설치 예시:

```bash
git clone https://github.com/GNh0/KH.git ~/.gemini/config/plugins/kh-uaf
cd ~/.gemini/config/plugins/kh-uaf
python -m src.skills.uaf_skill_catalog --check
```

워크스페이스 로컬 bootstrap 경로:

```text
<workspace-root>/.agents/plugins/kh-uaf/
```

## 빠른 시작

```bash
pip install -r requirements.txt
python cli.py run --project ./my_app --prompt "Create a small demo app"
```

기본 provider는 smoke-only 확인용 `offline`입니다. 실제 요구사항을 만족하는 생성이 필요하면 `local`, `openai`, `codex`, `claude` provider를 사용합니다.

```bash
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider local --base-url http://localhost:11434/v1
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider openai --model gpt-5
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --platform antigravity
```

## 기본 흐름

```text
front-door intake
  -> request classification
  -> plugin composition
  -> skill bundle selection
  -> role/workflow execution when needed
  -> review, QA, verification, release gate
  -> user deliverables under docs/
  -> KH runtime evidence under .kh or UAF runtime store
```

## 산출물과 런타임 상태

KH는 사용자 산출물과 내부 작업 상태를 분리합니다.

- 사용자에게 보여줄 문서와 결과물은 대상 프로젝트의 `docs/`
- KH 작업 노트와 handoff는 `.kh/<skill>/<run-id>/`
- 내부 state, memory, snapshot은 기본적으로 외부 KH-UAF runtime store
- 프로젝트 안에 `.uaf/` 상태를 남기고 싶을 때만 `UAF_PROJECT_LOCAL_STATE=1`

스킬/하네스 감사, traceability row, render QA 결과 같은 harness-only 데이터는 사용자가 명시적으로 요청하지 않는 한 `docs/`로 export하지 않습니다.

## 검증

릴리즈 전 최소 검증:

```bash
python -B -m src.skills.uaf_skill_catalog --check
python -B -m src.benchmarks.kh_bench_verified --summary
python -B -m src.benchmarks.practical_quality_gate --summary
```

자동 점수만으로 릴리즈를 판단하지 않습니다. 실제 판단은 KH-Bench, SIDE/E2E 평가, 설치 후 블라인드 세션 테스트 결과를 함께 봅니다.

전체 practical quality gate는 테스트와 감사 fixture가 있는 `main` 개발 체크아웃에서 실행합니다. `codex-runtime`은 Codex marketplace 설치 캐시에 들어가는 슬림 런타임 브랜치라 개발 테스트 파일이 없을 수 있습니다.

## 설치 캐시 주의

Codex에서 플러그인을 업그레이드하기 전의 기존 세션과 서브에이전트는 이전 캐시를 계속 사용할 수 있습니다.

예를 들어 배포가 `2.9.36`이어도 현재 세션이 `C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\2.9.35`에서 시작했다면 새 스킬은 바로 적용되지 않을 수 있습니다.

이 경우:

1. 변경 사항을 push합니다.
2. Codex 플러그인 관리 화면에서 KH UAF를 업그레이드합니다.
3. 새 세션을 엽니다.
4. KH 이름을 언급하지 않는 일반 요청으로 front-door 자동 인테이크가 동작하는지 다시 검증합니다.

## 감사 문서

자동 인테이크와 블라인드 세션 검증 기록:

```text
docs/kh/qa/2026-06-01-automatic-intake-routing-audit.md
docs/kh/qa/2026-06-01-post-upgrade-blind-subagent-audit.md
docs/kh/qa/2026-06-01-always-on-front-door-regression.md
```
