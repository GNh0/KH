# Universal Agent Framework (UAF)

[English](README.md) | [Korean](README.ko.md)

KH UAF는 Codex, Antigravity 계열 에이전트, Claude Code, 로컬 워커에서 공통으로 쓰기 위한 로컬 우선 스킬/하네스 프레임워크입니다.

구성은 크게 세 가지입니다.

- `skills/<skill-folder>/SKILL.md` 아래의 호스트가 읽을 수 있는 스킬
- `src/` 아래의 실행 계약, 디스패처, 역할 오케스트레이션, 게이트, 상태 저장소, 검증기
- 릴리즈 검증용 품질 체크와 SWE-bench 스타일의 실전 벤치마크

목표는 특정 벤더의 로컬 스킬 폴더에 의존하지 않는 독자적인 범용 스킬/하네스 패키지를 제공하는 것입니다.

## 포함 항목

- 27개 패키지 스킬/하네스, 지원 문서, smoke check, runnable demo.
- Codex 플러그인 매니페스트: `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`.
- Antigravity 전역/워크스페이스 플러그인 부트스트랩.
- CEO, 자문, 설계자, 계획자, controller, implementer, reviewer, QA, security, release 역할을 포함한 DAG 기반 역할 오케스트레이션.
- 제한된 로컬 워커 디스패치와 review, QA, security, release, evidence gate.
- 목표 상태, 범위별 메모리, resume handoff, snapshot, 런타임 상태 저장.
- 작업 유형에 맞는 사용자용 산출물을 대상 프로젝트의 `docs/` 아래에 생성.
- render QA, template quality, traceability, role audit 하네스.
- 내부 품질 점수와 분리된 실전 태스크 벤치마크 `KH-Bench Verified`.

기본값에서는 사용자에게 필요한 산출물만 대상 프로젝트에 저장하고, UAF 내부 상태는 프로젝트 루트 밖의 KH-UAF runtime store에 저장합니다. 프로젝트 안에 `.uaf`와 snapshot 상태를 남기고 싶을 때만 `UAF_PROJECT_LOCAL_STATE=1`을 설정합니다.

## 빠른 시작

```bash
pip install -r requirements.txt
python cli.py run --project ./my_app --prompt "Create a small demo app"
```

CLI 기본 provider는 deterministic `offline`이므로, 첫 smoke run은 로컬 LLM이나 외부 API 없이 실행할 수 있습니다.

실제 모델을 쓸 때는 provider를 지정합니다.

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

설치 또는 업그레이드 후에는 새 thread를 시작해야 스킬이 다시 로드됩니다.

Windows 직접 clone:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\plugins\kh-uaf"
cd "$env:USERPROFILE\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

루트의 `plugin.json`은 UAF 런타임 매니페스트이고, Codex 플러그인 매니페스트는 `.codex-plugin/plugin.json`입니다.

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

워크스페이스 로컬 부트스트랩 경로:

```text
<workspace-root>/.agents/plugins/kh-uaf/
```

여러 워크스페이스에서 모든 KH UAF 스킬을 쓰려면 전역 clone 방식을 권장합니다.

## 기본 흐름

```text
cli.py run
  -> 설계 문서와 domain profile 생성
  -> WorkDesign과 사용자 산출물 계획 생성
  -> 역할 DAG와 제한된 worker dispatch 실행
  -> review, QA, security, release, evidence gate 실행
  -> 사용자용 문서는 docs/에 저장
  -> UAF 상태, 메모리, snapshot, 역할 산출물, handoff는 runtime state에 저장
```

## 산출물

UAF는 고정된 확장자 목록이 아니라 작업 유형에 따라 사용자용 산출물을 생성합니다.

- 소프트웨어 개발: 요구정의서, 기능정의서, 개발설계서, 화면/API 정의서, 데이터 정의서, 테스트 계획서, 위험/정책 체크리스트.
- 일반 오케스트레이션: 요구정의서, 오케스트레이션 설계서, 처리흐름도, 역할별 작업분해표, 증거계획서, 위험/정책 체크리스트.
- 제품/기계 설계: 제품 설계 문서, 치수/BOM 워크북, SVG 개념도, 입력이 충분한 경우 DXF handoff.
- 투자/분석: 분석 보고서, 시나리오 워크북, 위험/정책 워크북.
- 매뉴얼은 조건부입니다. 사용자 또는 운영자가 실제로 따라야 할 절차가 필요한 경우에만 생성합니다.

traceability rows, render QA, role audit, template quality 같은 하네스 내부 결과는 사용자가 명시적으로 요청하지 않는 한 사용자 산출물로 내보내지 않고 runtime metadata에 남깁니다.

## 스킬 구조

각 패키지 스킬은 다음 구조를 가집니다.

```text
skills/<skill-folder>/SKILL.md
skills/<skill-folder>/references/usage.md
skills/<skill-folder>/examples/minimal-workflow.md
skills/<skill-folder>/scripts/smoke_check.py
skills/<skill-folder>/scripts/demo.py
```

자주 쓰는 명령:

```bash
python -m src.skills.uaf_skill_catalog --list
python -m src.skills.uaf_skill_catalog --read orchestration-role-graph
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
python skills/token_optimizer/scripts/demo.py --output-dir ./tmp/token-demo
```

## KH-Bench Verified

내부 품질 점수는 스킬이 얕지 않은지 확인합니다. `KH-Bench Verified`는 UAF가 실제 작업을 실행하고 검증할 수 있는지 확인합니다.

```bash
python -m src.benchmarks.kh_bench_verified --summary
python -m unittest tests.test_kh_bench_verified
```

각 태스크는 clean workspace와 태스크별 `UAF_RUNTIME_ROOT`에서 실행됩니다. 벤치마크는 실행 중 `UAF_PROJECT_LOCAL_STATE=0`도 강제하므로, 호스트 환경값 때문에 runtime state가 프로젝트 안으로 새지 않습니다.

- `pre_validation`: 실행 전 실패해야 하는 체크
- `fail_to_pass`: 실행 후 통과해야 하는 체크
- `pass_to_pass`: 계속 통과해야 하는 회귀 체크
- resolved rate, evidence, runtime contract, artifact, unresolved task ID를 포함한 JSON score output

현재 태스크 범주는 coding workflow dispatch, product/domain deliverables, role DAG orchestration, snapshot rollback, goal/memory/handoff state, token-safe command-output compression입니다.

CLI는 내장 `KHBaselineCandidateRunner`로 KH UAF 자체를 평가합니다. Python 호출자는 `run_kh_bench_verified(...)`에 다른 candidate runner를 넘길 수 있습니다. 외부 candidate runner에는 sealed public task view만 전달되며, validator, expected artifacts, baseline profile metadata는 grader 안에 남습니다. validator는 runner가 만든 custom flag를 믿지 않고 실제 파일, runtime artifact, report JSON을 읽어서 채점합니다.

## 검증

배포 전 권장 검증:

```bash
python -m json.tool plugin.json
python -m json.tool .codex-plugin/plugin.json
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
python -m src.benchmarks.kh_bench_verified --summary
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

| 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `AG_PLATFORM_MODE` | `local` | 디스패처 모드 |
| `AG_LLM_PROVIDER` | `offline` | 기본 CLI provider |
| `AG_LLM_BASE_URL` | `http://localhost:11434/v1` | 로컬 OpenAI-compatible endpoint |
| `AG_MAX_WORKERS` | `50` | 요청 async worker 제한 |
| `UAF_RUNTIME_ROOT` | `%LOCALAPPDATA%/KH-UAF` | 런타임 상태 루트 |
| `UAF_PROJECT_LOCAL_STATE` | unset | 프로젝트 안에 `.uaf` 상태를 남겨야 할 때만 `1`로 설정 |
