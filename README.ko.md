# KH Universal Agent Framework

[English](README.md) | [Korean](README.ko.md)

KH UAF는 Codex, Antigravity 계열 에이전트, Claude Code, 로컬 워커를 위한 개인 독립형 UAF 스킬북이자 오케스트레이션 표면입니다. 목표는 특정 호스트의 전역 스킬 폴더에 의존하지 않고, 설치된 플러그인 캐시 안의 스킬과 런타임 계약으로 작업을 라우팅하고 감사할 수 있게 하는 것입니다.

KH는 다음 흐름을 하나의 제품 표면으로 묶습니다.

- Superpowers식 작업 흐름: 브레인스토밍, 계획, worktree/TDD, 디버깅, 리뷰, 검증, 마무리
- Compound 학습: 리뷰 이후 재사용 가능한 교훈, scoped memory 후보, 회귀 시나리오 캡처
- RTK식 토큰 게이트: 긴 명령 출력과 subagent transcript를 보존 가능한 범위에서만 최적화
- OpenClaw/Hermes식 scoped memory: 프로젝트/대화/하위 에이전트 범위를 분리하고, 전역 메모리 승격은 명시 승인으로만 처리
- 역할 오케스트레이션과 specialist composition: KH가 컨트롤러가 될 수도 있고, GitHub/브라우저/문서/SQL 같은 전문 도구를 위임 범위 안에서 사용할 수도 있음

## 포함 항목

- 지원 파일, smoke check, demo를 갖춘 41개 packaged skill/harness
- `always-on-front-door`: 비사소한 작업 전에 실행해야 하는 host-visible bootstrap skill
- `automatic-intake-harness`, `plugin-composition-policy`, `request-complexity-router`
- `brainstorming-harness`, `compound-engineering-harness`, `workflow-usability-harness`
- GoalState, scoped memory, snapshot, resume handoff, progress panel, host panel JSON
- 리뷰/QA/보안/release evidence gate와 session skill audit/postmortem
- KH-Bench Verified, SIDE regression, practical quality gate

## Front-Door Intake

사용자가 KH나 개별 skill 이름을 말하지 않아도, 프로젝트 파일, 코드 변경, 산출물, 긴 로그, 리뷰, QA, 검증, branch finishing, subagent, 지속 상태, 고위험 작업이 포함되면 먼저 front-door intake를 실행해야 합니다.

```bash
python skills/always_on_front_door/scripts/front_door.py --prompt-file "<utf8 prompt file>" --project "<target project>" --host codex --summary --strict-execution-gate
```

비 ASCII 또는 여러 줄 prompt는 `--prompt-file`을 사용합니다. 짧은 ASCII prompt에서만 inline `--prompt` 옵션을 사용할 수 있습니다. KH repo root에서 실행 중이면 `python -m src.orchestration.kh_front_door ...`도 같은 런타임 경로입니다.

front-door는 다음을 반환합니다.

- `runtime_applied_skills`: 런타임에서 실제 적용된 skill
- `immediate_next_skills`: source 탐색이나 파일 수정 전에 적용, skip, block 증거가 필요한 skill
- `selected_not_executed_skills`: 아직 실행 증거가 없는 후보
- `skill_status_summary`: 각 skill의 적용 방식, 근거, 차단 이유

KH는 intake를 요구하고 audit할 수 있지만, host나 subagent가 항상 자동으로 따르는 것을 보장하지는 않습니다. 누락되면 stale session, plugin injection 문제, 또는 host-compliance 문제로 보고 session log에서 `kh-uaf:always-on-front-door`와 설치 cache wrapper 경로를 확인합니다.

## Codex Plugin 설치

Codex에서 `Plugins -> Manage -> Add marketplace`를 열고 다음 값을 입력합니다.

```text
Source: https://github.com/GNh0/KH.git
Git ref: main
Sparse path: .agents/plugins
```

`Git ref: main`은 marketplace descriptor를 읽기 위한 ref입니다. 실제 설치되는 plugin source ref는 그 descriptor 안에서 `codex-runtime`을 가리킵니다. 설치 cache 경로인 `$CODEX_HOME/plugins/cache/.../kh-uaf/<version>`은 생성된 복사본이며 source branch가 아닙니다.

설치 또는 업그레이드 후에는 새 thread를 열어 Codex가 최신 plugin prompt와 skill 파일을 다시 로드하게 합니다. 배포할 때는 `.codex-plugin/plugin.json`과 root `plugin.json`의 version을 함께 올립니다.

상태 점검:

```bash
python -m src.orchestration.plugin_install_audit --summary
```

`main`은 테스트, audit, 개발 문서를 보관하는 개발 checkout입니다. `codex-runtime`은 Codex marketplace cache 설치용 slim runtime branch입니다. cache가 이전 version을 가리키거나 active session skill path가 오래된 cache에 남아 있으면 stale로 봅니다.

## 빠른 시작

```bash
pip install -r requirements.txt
python cli.py run --project ./my_app --prompt "Create a small demo app"
```

기본 provider는 smoke 확인용 `offline`입니다. 실제 요구사항을 충족하는 산출물이 필요하면 `local`, `openai`, `codex`, `claude` 같은 model-backed provider를 사용합니다.

```bash
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider local --base-url http://localhost:11434/v1
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider openai --model gpt-5
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --platform antigravity
```

## 문서 경계

현재 제품 표면과 설치/운영 기준은 `README.md`, `README.ko.md`, `SKILL.md`, `.codex-plugin/plugin.json`, `plugin.json`, `docs/README.md`를 기준으로 봅니다.

`docs/skillbook/**`와 날짜가 붙은 `docs/kh/qa/**`, `docs/kh/reports/**`는 과거 설계, 감사, 회귀 증거입니다. 배경 자료로는 유용하지만 현재 설치 계약이나 host prompt보다 우선하지 않습니다.

## 검증

`codex-runtime` branch에서는 runtime 포장 상태를 중심으로 확인합니다.

```bash
python -B -m src.skills.uaf_skill_catalog --check
python -B -m src.orchestration.plugin_install_audit --summary
python -m json.tool plugin.json
python -m json.tool .codex-plugin/plugin.json
```

전체 practical quality gate와 fixture 기반 테스트는 개발 checkout인 `main`에서 실행합니다. `codex-runtime`에는 runtime 설치에 불필요한 테스트 파일이 없을 수 있습니다.
