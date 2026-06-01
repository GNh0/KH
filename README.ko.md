# Universal Agent Framework (UAF)

[English](README.md) | [Korean](README.ko.md)

KH UAF는 Codex, Antigravity 계열 에이전트, Claude Code, 로컬 워커에서 공통으로 사용할 수 있는 로컬 우선 스킬/하네스 프레임워크입니다.

이 프로젝트는 특정 벤더의 로컬 스킬 폴더에 의존하지 않습니다. 필요한 스킬과 하네스를 저장소 안에 독립적으로 패키징하고, Python 런타임 계약과 검증 도구로 실제 동작을 확인합니다.

## KH 자동 라우팅

사용자가 KH 스킬이나 하네스 이름을 하나하나 지정할 필요는 없습니다. 사용자가 KH, KH UAF, KH 플러그인, KH 스킬, 또는 `/kh:*` 역할 명령을 사용하라고 요청하면, 호스트는 소스 탐색이나 수정 전에 먼저 KH front door를 실행해야 합니다.

1. KH 루트 가이드 또는 패키지된 스킬 카탈로그를 확인합니다.
2. `plugin-composition-policy`와 `request-complexity-router`로 요청을 분류합니다.
3. 필요한 최소 스킬 묶음을 자동으로 선택합니다.
4. 선택, 고려, 생략, 차단된 스킬을 evidence와 함께 기록합니다.
5. 그 다음에 소스 읽기, 수정, 역할 DAG 실행, 산출물 생성을 시작합니다.

이 규칙은 KH가 수동 체크리스트가 되는 것을 막기 위한 계약입니다. `session-skill-audit`는 KH 사용 요청 후 front door 없이 작업 명령이 먼저 시작되면 P1 `missing_front_door` 이슈로 표시합니다.

## 포함 항목

- 38개 패키지 스킬/하네스와 `SKILL.md`, 사용 가이드, 예제, smoke check, runnable demo
- Codex 플러그인 매니페스트: `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`
- Antigravity 전역/워크스페이스 설치용 bootstrap 파일
- CEO, advisor, architect, planner, controller, implementer, reviewer, QA, security, release 역할을 포함한 DAG 역할 오케스트레이션
- 제한된 로컬 워커 실행, review/QA/security/release/evidence gate
- goal state, scoped memory, resume handoff, snapshot, runtime state
- 작업 유형별 사용자 산출물을 대상 프로젝트의 `docs/` 아래로 export
- render QA, template QA, traceability, role execution audit 하네스
- 내부 스킬 점수와 분리된 실전 태스크 벤치마크 `KH-Bench Verified`
- KH-Bench/SIDE/E2E 결과를 주 품질 신호로 보는 `KH Practical Quality Gate`
- 요청 라우팅, evidence, gate, resume 동작을 반복 검증하는 deterministic SIDE 스타일 `scenario-evaluation-harness`

기본적으로 사용자에게 보여줄 산출물은 대상 프로젝트에 저장하고, UAF 내부 런타임 상태는 프로젝트 밖 KH-UAF 런타임 저장소에 저장합니다. 프로젝트 안에 `.uaf`와 snapshot 상태를 남기고 싶을 때만 `UAF_PROJECT_LOCAL_STATE=1`을 설정합니다.

## 빠른 시작

```bash
pip install -r requirements.txt
python cli.py run --project ./my_app --prompt "Create a small demo app"
```

CLI 기본 provider는 결정론적 `offline`입니다. 이 모드는 로컬 LLM이나 외부 API 없이 packaging, dispatch, state, gate가 실행되는지 확인하는 smoke-only run입니다. 실제 요청을 충실히 구현하는 모드가 아니므로, 실제 결과물이 필요하면 `local`, `openai`, `codex`, `claude` 같은 모델 기반 provider를 사용합니다.

```bash
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider local --base-url http://localhost:11434/v1
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider openai --model gpt-5
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --platform antigravity
```

## Codex 플러그인 설치

Codex에서 Plugins -> Manage -> Add marketplace를 열고 다음 값을 입력합니다.

```text
Source: https://github.com/GNh0/KH.git
Git ref: main
Sparse path: .agents/plugins
```

마켓플레이스 파일은 `main`에 있지만, 실제 플러그인은 `codex-runtime` 브랜치에서 설치되도록 설정되어 있습니다. `main`은 테스트, 감사 문서, 개발 기록을 보관하고, `codex-runtime`은 Codex 설치 캐시에 들어가는 슬림 런타임 브랜치입니다.

설치 또는 업그레이드 후에는 새 thread를 시작해야 Codex가 스킬을 다시 로드합니다.

업그레이드 참고: Codex는 플러그인 매니페스트 버전별로 설치 캐시를 만듭니다. 새 플러그인 빌드를 배포할 때는 `.codex-plugin/plugin.json`과 루트 `plugin.json`의 version을 함께 올려야 합니다. marketplace clone은 최신인데 설치된 플러그인이 `kh-uaf/2.8.0` 같은 예전 캐시 경로에 남아 있으면, 버전 bump 이후 다시 설치하거나 업그레이드합니다.

Windows 직접 clone:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\plugins\kh-uaf"
cd "$env:USERPROFILE\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

루트 `plugin.json`은 UAF 런타임 매니페스트이고, Codex 플러그인 매니페스트는 `.codex-plugin/plugin.json`입니다.

저장소 정리 기준: `tests/`와 `docs/skillbook/`은 개발/검증용 증거이며 플러그인 런타임에는 필요하지 않습니다. 마켓플레이스 설치는 `codex-runtime` ref를 사용해 Codex 플러그인 캐시에 `.codex-plugin/`, `skills/`, `src/`, 런타임 매니페스트 중심으로 들어가게 합니다.

## Antigravity 플러그인 설치

Windows 전역 설치:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\.gemini\config\plugins\kh-uaf"
cd "$env:USERPROFILE\.gemini\config\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

macOS/Linux 전역 설치:

```bash
git clone https://github.com/GNh0/KH.git ~/.gemini/config/plugins/kh-uaf
cd ~/.gemini/config/plugins/kh-uaf
python -m src.skills.uaf_skill_catalog --check
```

워크스페이스 로컬 bootstrap 경로:

```text
<workspace-root>/.agents/plugins/kh-uaf/
```

여러 워크스페이스에서 모든 KH UAF 스킬을 쓰려면 전역 clone 방식을 권장합니다.

## 기본 흐름

```text
cli.py run
  -> design document와 domain profile 생성
  -> WorkDesign과 사용자 산출물 계획 생성
  -> 역할 DAG와 제한된 worker dispatch 실행
  -> review, QA, security, release, evidence gate 실행
  -> 사용자 산출물은 docs/에 저장
  -> UAF state, memory, snapshot, role artifacts, handoff는 runtime state에 저장
```

## 산출물

UAF는 고정된 확장자 목록이 아니라 작업 유형에 맞춰 사용자 산출물을 만듭니다.

- 소프트웨어 개발: 요구정의서, 기능정의서, 개발설계서, 화면/API 정의서, 데이터 정의서, 테스트 계획서, 위험/정책 체크리스트
- 일반 오케스트레이션: 요구정의서, 오케스트레이션 설계서, 처리흐름도, 역할별 작업분해표, 증거계획서, 위험/정책 파일
- 제품/기계 설계: 제품 설계 문서, 치수/BOM 워크북, SVG 개념도, 입력이 충분할 경우 DXF handoff
- 투자/분석: 분석 보고서, 시나리오 워크북, 위험/정책 워크북
- 매뉴얼: 사용자 또는 운영자가 실제로 따라야 할 절차가 필요한 경우에만 조건부로 생성

Traceability row, render QA, role audit, template quality 같은 하네스 내부 결과는 사용자가 명시적으로 요청하지 않는 한 사용자 문서로 export하지 않고 runtime metadata에 보관합니다.

## 스킬 구조

각 패키지 스킬은 다음 구조를 가집니다.

```text
skills/<skill-folder>/SKILL.md
skills/<skill-folder>/references/usage.md
skills/<skill-folder>/examples/minimal-workflow.md
skills/<skill-folder>/scripts/smoke_check.py
skills/<skill-folder>/scripts/demo.py
```

유용한 명령:

```bash
python -m src.skills.uaf_skill_catalog --list
python -m src.skills.uaf_skill_catalog --read orchestration-role-graph
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
python skills/token_optimizer/scripts/demo.py --output-dir ./tmp/token-demo
```

## KH-Bench Verified

내부 품질 점수는 스킬 구조가 얕지 않은지 확인합니다. `KH-Bench Verified`는 UAF가 실제 작업을 실행하고 검증할 수 있는지 확인합니다.

```bash
python -m src.benchmarks.kh_bench_verified --summary
python -m src.benchmarks.practical_quality_gate --summary
python -m unittest tests.test_kh_bench_verified
```

각 태스크는 깨끗한 작업 폴더와 태스크 전용 `UAF_RUNTIME_ROOT`에서 실행됩니다. 실행 중에는 `UAF_PROJECT_LOCAL_STATE=0`을 강제해서 호스트 환경 설정 때문에 내부 상태가 프로젝트에 섞이지 않게 합니다.

- `pre_validation`: 실행 전에 실패해야 하는 사전 검증
- `fail_to_pass`: 실행 후 통과해야 하는 검증
- `pass_to_pass`: 계속 통과해야 하는 회귀 검증
- resolved rate, evidence, runtime contract, artifact, unresolved task ID가 포함된 JSON 점수 출력

현재 태스크 범주는 coding workflow dispatch, product/domain deliverables, role DAG orchestration, snapshot rollback, goal/memory/handoff state, token-safe command-output compression, Markdown extraction SIDE regression, compact product-spec drawing export SIDE regression을 포함합니다.

배포 판단에는 `lowest_quality_score`만 보지 말고 `python -m src.benchmarks.practical_quality_gate --summary`를 우선 사용합니다. 정적 10점 스킬 점수는 구조 검사용 보조 신호이고, KH-Bench 또는 SIDE regression 태스크가 실패하면 release-ready가 아닙니다.

## 검증

배포 전 실행:

```bash
python -m json.tool plugin.json
python -m json.tool .codex-plugin/plugin.json
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
python -m src.benchmarks.kh_bench_verified --summary
python -m src.benchmarks.practical_quality_gate --summary
python -m unittest discover -s tests
```

## 프로젝트 구조

```text
.codex-plugin/
.agents/plugins/
cli.py
plugin.json
SKILL.md
src/
  benchmarks/
  contracts.py
  core/
  harness/
  orchestration/
  platforms/
  skills/
  tasks/
skills/
docs/
tests/
```

## 환경 변수

| Variable | Default | Purpose |
| --- | --- | --- |
| `AG_PLATFORM_MODE` | `local` | Dispatcher mode |
| `AG_LLM_PROVIDER` | `offline` | 기본 CLI provider |
| `AG_LLM_BASE_URL` | `http://localhost:11434/v1` | 로컬 OpenAI-compatible endpoint |
| `AG_MAX_WORKERS` | `50` | 요청 async worker 제한 |
| `UAF_RUNTIME_ROOT` | `%LOCALAPPDATA%/KH-UAF` | 런타임 상태 루트 |
| `UAF_PROJECT_LOCAL_STATE` | unset | 프로젝트 로컬 `.uaf` 상태가 필요할 때만 `1`로 설정 |
