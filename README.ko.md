# KH Universal Agent Framework

[English](README.md) | [Korean](README.ko.md)

KH UAF는 Codex, Antigravity 계열 에이전트, Claude Code, 로컬 워커를 위한 개인 독립형 UAF 스킬북이자 오케스트레이션 런타임입니다. 목표는 특정 호스트의 전역 스킬 폴더에 의존하지 않고, 설치된 marketplace 플러그인 캐시만으로 동작해야 합니다.

KH는 Superpowers식 작업 흐름, Compound 학습, RTK식 토큰 게이트, OpenClaw/Hermes식 scoped memory, 역할 오케스트레이션, specialist composition을 하나의 개인용 스킬/하네스 프로젝트로 묶습니다.

## 포함 항목

- 지원 파일, smoke check, demo를 갖춘 42개 packaged skill/harness
- `always-on-front-door`: 비사소한 작업 전에 먼저 실행되는 bootstrap skill
- `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`
- `brainstorming-harness`, `compound-engineering-harness`, `workflow-usability-harness`
- `pb-to-csharp-migration-harness`: PowerBuilder/PBL/DataWindow/GWERP를 TY/C_KONE110 C# 및 SELECT/SAVE SP 스타일로 마이그레이션
- GoalState, scoped memory, snapshot, resume handoff, progress panel, host panel JSON
- 리뷰, QA, 보안, release evidence gate와 session skill audit/postmortem
- KH-Bench Verified, SIDE regression, practical quality gate

## 기본 흐름

1. 사용자가 KH나 개별 skill 이름을 말하지 않아도 비사소한 작업은 front-door intake를 먼저 실행합니다.
2. front-door는 실제 적용된 skill, 다음에 바로 적용해야 하는 skill, 아직 실행되지 않은 후보 skill을 분리합니다.
3. 방향이 승인되지 않은 앱, 제품, 업무, 문서, 분석, 설계 요청은 먼저 brainstorming-harness로 범위와 선택지를 정리합니다.
4. 승인된 방향에 맞춰 스택, 아키텍처, 산출물 유형, 검증 방식을 선택합니다.
5. 구현, 리뷰, QA, 검증, branch finishing은 증거가 있을 때만 완료로 보고합니다.

## 산출물 경계

사용자에게 필요한 산출물은 요청한 프로젝트 경로에 생성합니다. 예를 들어 문서, 스프레드시트, PDF, 도면, 웹 파일, 데이터 파일은 목적과 승인된 산출물 유형에 맞춰 생성됩니다.

KH 내부 작업 자료, GoalState, memory candidate, review evidence, token optimizer evidence는 기본적으로 KH runtime state에 저장합니다. 사용자 프로젝트 루트에 `.uaf`나 `.snapshots`를 기본 생성하지 않습니다. 프로젝트 로컬 상태가 필요하면 명시적인 opt-in이 있어야 합니다.

## Front-Door Intake

프로젝트 파일, 코드 변경, 산출물, 긴 로그, 리뷰, QA, 검증, branch finishing, subagent, 지속 상태, 고위험 작업이 포함되면 먼저 front-door intake를 실행합니다.

```bash
python skills/always_on_front_door/scripts/front_door.py --prompt-file "<utf8 prompt file>" --project "<target project>" --host codex --summary --strict-execution-gate
```

비 ASCII 또는 여러 줄 prompt는 `--prompt-file`을 사용합니다. 짧은 ASCII prompt에서만 inline `--prompt` 옵션을 사용할 수 있습니다. KH repo root에서 실행 중이면 `python -m src.orchestration.kh_front_door ...`도 같은 런타임 경로입니다.

front-door는 다음 값을 반환합니다.

- `runtime_applied_skills`: 런타임에서 실제 적용된 skill
- `immediate_next_skills`: source 탐색이나 파일 수정 전에 적용, skip, block 증거가 필요한 skill
- `selected_not_executed_skills`: 아직 실행 증거가 없는 후보
- `skill_status_summary`: 각 skill의 적용 방식, 근거, 차단 이유

KH는 intake를 요구하고 audit할 수 있지만, host나 subagent가 항상 자동으로 따르는 것을 보장하지는 않습니다. 누락되면 stale session, plugin injection 문제, 또는 host-compliance 문제로 보고 session log에서 `kh-uaf:always-on-front-door`와 설치 cache wrapper 경로를 확인합니다.

## Codex 플러그인 설치

Codex에서 `Plugins -> Manage -> Add marketplace`를 열고 다음 값을 입력합니다.

```text
Source: https://github.com/GNh0/KH.git
Git ref: main
Sparse path: .agents/plugins
```

`Git ref: main`은 marketplace descriptor를 읽기 위한 ref입니다. 실제 설치되는 plugin source ref는 descriptor 안에서 `codex-runtime`을 가리킵니다. 설치 cache 경로인 `$CODEX_HOME/plugins/cache/.../kh-uaf/<version>`은 생성된 복사본이며 source branch가 아닙니다.

업그레이드 참고: Codex는 manifest version 기준으로 cache를 갱신합니다. 새 빌드를 배포할 때는 `.codex-plugin/plugin.json`, root `plugin.json`, `.agents/plugins/kh-uaf/plugin.json`의 버전 bump를 함께 처리합니다. 업그레이드 후에는 새 thread를 열어 최신 plugin prompt와 skill 파일을 다시 로드합니다.

상태 점검:

```bash
python -m src.orchestration.plugin_install_audit --summary
```

## Antigravity 플러그인 설치

Antigravity 계열 호스트에서는 repo의 `.agents/plugins/kh-uaf` wrapper를 plugin marker로 사용할 수 있습니다. 이 wrapper는 KH runtime source를 직접 복제하지 않고, 설치된 marketplace plugin cache와 root runtime 계약을 가리키는 얇은 연결 계층입니다.

예시 경로:

```text
~/.gemini/config/plugins/kh-uaf
.agents/plugins/kh-uaf
```

## 빠른 시작

```bash
pip install -r requirements.txt
python cli.py run --project ./my_app --prompt "Create a small demo app"
```

기본 provider는 smoke-only 확인용 `offline`입니다. 실제 요구사항을 충족하는 산출물이 필요하면 `local`, `openai`, `codex`, `claude` 같은 model-backed provider를 사용합니다.

```bash
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider local --base-url http://localhost:11434/v1
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider openai --model gpt-5
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --platform antigravity
```

## 검증

`codex-runtime` branch에서는 runtime 포장 상태를 중심으로 확인합니다.

```bash
python -B -m src.skills.uaf_skill_catalog --check --summary
python -B -m src.orchestration.plugin_install_audit --summary
python -m json.tool plugin.json
python -m json.tool .codex-plugin/plugin.json
```

전체 practical quality gate와 fixture 기반 테스트는 개발 checkout인 `main`에서 실행합니다. `codex-runtime`에는 runtime 설치에 불필요한 테스트 파일이 없을 수 있습니다.
