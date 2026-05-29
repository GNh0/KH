# Universal Agent Framework (UAF)

[English](README.md) | [한국어](README.ko.md)

UAF는 Codex, Antigravity, Claude Code, 기타 에이전트 호스트에서 사용할 수 있는 Python 우선, 로컬 우선 오케스트레이션 프레임워크입니다.

이 저장소는 두 가지를 패키징합니다.

- `src/` 아래의 런타임 계약, 디스패처, 게이트, 상태, 하네스
- `skills/<skill-folder>/SKILL.md` 아래의 호스트가 읽을 수 있는 스킬

목적은 계획, 도메인 프로파일링, 역할 오케스트레이션, 워커 디스패치, 리뷰/QA 게이트, 스냅샷, 메모리, 목표 상태, 사용자용 산출물을 특정 벤더의 로컬 스킬 폴더에 의존하지 않고 여러 에이전트 호스트에서 재사용할 수 있게 만드는 것입니다.

## 포함 항목

- 27개 KH UAF 스킬/하네스 카탈로그
- 로컬 프로젝트 워크플로우용 CLI 러너
- Codex 플러그인 매니페스트: `.codex-plugin/plugin.json`
- Codex 마켓플레이스 파일: `.agents/plugins/marketplace.json`
- Antigravity 워크스페이스 부트스트랩: `.agents/plugins/kh-uaf`
- Local/Antigravity 디스패처 계약
- CEO, 자문, 아키텍트, 플래너, 컨트롤러, 구현자, 리뷰어, QA, 보안, 릴리스 역할을 포함한 DAG 기반 역할 오케스트레이션
- Goal ledger, scoped memory store, resume handoff, 런타임 상태 저장소
- 대상 프로젝트의 `docs/` 폴더에 생성되는 유형별 사용자 산출물
- 메타데이터 전용 품질, 렌더 QA, 추적성, 역할 실행 감사 하네스
- 로컬 LLM 없이 설치 직후 smoke run이 가능한 deterministic `offline` provider
- OpenAI-compatible, Anthropic, custom LLM provider 훅

기본적으로 내부 상태는 대상 프로젝트 루트에 쓰지 않습니다. 사용자용 파일은 대상 프로젝트의 `docs/` 아래에 생성되고, UAF 런타임 상태는 보통 `%LOCALAPPDATA%/KH-UAF/projects/<project-key>/.uaf/` 아래에 저장됩니다.

## 빠른 시작

```bash
pip install -r requirements.txt
python cli.py run --project ./my_app --prompt "Create a small demo app"
```

CLI 기본 provider는 `offline`입니다. 첫 smoke run은 Ollama, OpenAI, Anthropic, 로컬 API 서버 없이 동작합니다.

실제 모델 기반 생성을 원하면 provider를 지정합니다.

```bash
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider local --base-url http://localhost:11434/v1
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --provider openai --model gpt-5
python cli.py run --project ./my_app --prompt "Create a FastAPI backend" --platform antigravity
```

자주 쓰는 명령:

```bash
python -m src.skills.uaf_skill_catalog --list
python -m src.skills.uaf_skill_catalog --read orchestration-role-graph
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
python -m unittest tests.test_skill_demos
python -m unittest discover -s tests
```

## Codex 플러그인 설치

이 저장소는 `.codex-plugin/plugin.json`을 포함하므로 Codex 플러그인으로 설치할 수 있습니다.

Codex에서 Plugins -> Manage -> Add marketplace를 열고 아래 값을 입력합니다.

```text
Source: https://github.com/GNh0/KH.git
Git ref: main
Sparse path: .agents/plugins
```

`Sparse path`는 `.agents/plugins/marketplace.json`을 가리키며, 이 파일이 `KH UAF` 플러그인 항목을 노출합니다. 설치 또는 업그레이드 후에는 새 thread를 시작해야 스킬이 다시 로드됩니다.

CLI 환경에서는 다음처럼 추가할 수 있습니다.

```bash
codex plugin marketplace add https://github.com/GNh0/KH.git --ref main --sparse .agents/plugins
```

Windows에서 직접 clone할 때 권장 경로:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\plugins\kh-uaf"
cd "$env:USERPROFILE\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

루트 `plugin.json`은 UAF 런타임 매니페스트이고, Codex 플러그인 매니페스트는 `.codex-plugin/plugin.json`입니다.

## Antigravity 플러그인 설치

Antigravity에서는 KH UAF를 global plugin 또는 workspace bootstrap 방식으로 사용할 수 있습니다.

Windows global install:

```powershell
git clone https://github.com/GNh0/KH.git "$env:USERPROFILE\.gemini\config\plugins\kh-uaf"
cd "$env:USERPROFILE\.gemini\config\plugins\kh-uaf"
python -m src.skills.uaf_skill_catalog --check
```

macOS/Linux global install:

```bash
git clone https://github.com/GNh0/KH.git ~/.gemini/config/plugins/kh-uaf
cd ~/.gemini/config/plugins/kh-uaf
python -m src.skills.uaf_skill_catalog --check
```

워크스페이스 로컬 부트스트랩 경로:

```text
<workspace-root>/.agents/plugins/kh-uaf/
```

워크스페이스 부트스트랩은 의도적으로 작게 유지합니다. `kh-uaf` 스킬을 노출하고, 호스트가 이 저장소의 루트 `skills/`, `SKILL.md`, 검증 명령을 사용하도록 안내합니다. 모든 KH UAF 스킬을 여러 워크스페이스에서 쓰려면 global clone 방식을 사용합니다.

## 핵심 흐름

```text
cli.py run
  -> SystemArchitect가 design_doc.md 작성
  -> AgentLoop가 role graph와 GoalState metadata 부착
  -> DomainProfile과 WorkDesign 생성
  -> 사용자용 산출물을 docs/로 라우팅
  -> DispatcherFactory가 local 또는 Antigravity mode 선택
  -> role DAG와 bounded worker가 작업 실행
  -> review, QA, security, release, evidence gate 실행
  -> GoalLedger, memory, artifacts, resume handoff를 runtime state에 저장
```

로컬 경로는 deterministic `offline` provider로 smoke test를 수행할 수 있습니다. 실제 모델 기반 작업은 `local`, `openai`, `codex`, `claude` 또는 `LLMRouter.register_provider(...)`로 등록한 custom provider를 사용합니다.

## 산출물

UAF는 고정된 확장자 목록이 아니라 작업 유형에 맞춰 사용자용 산출물을 생성합니다.

- 소프트웨어 작업: `요구정의서.docx`, `기능정의서.docx`, `개발설계서.docx`, `화면_API_정의서.docx`, data/test/risk XLSX 파일
- 일반 오케스트레이션: 요구정의, 오케스트레이션 설계, 처리흐름, 역할별 작업분해, 증거계획, 위험/정책 파일
- 제품/기계 설계: 설계서, 치수/BOM workbook, SVG 개념도, 입력이 충분할 때 DXF handoff
- 투자/분석: 분석보고서, 시나리오 workbook, 위험/정책 workbook
- 매뉴얼은 조건부입니다. `사용_매뉴얼.docx`는 사용자/운영 지침이 필요하거나 manual revision metadata가 있을 때만 생성됩니다.

traceability rows, render QA checks, role audit findings, template quality checks 같은 하네스 전용 결과는 사용자가 명시적으로 산출물로 요청하지 않는 한 runtime metadata에만 남습니다.

## 패키징된 스킬

카탈로그는 `skills/`를 스캔하고 각 `SKILL.md`를 `src.skills.uaf_skill_catalog`로 노출합니다.

주요 그룹:

| 그룹 | 스킬 |
| --- | --- |
| 오케스트레이션/어댑터 | `orchestration-role-graph`, `adapter-contract-harness`, `host-agent-orchestration`, `parallel-orchestration-harness`, `subagent-review-pipeline` |
| 계획/라이프사이클 | `architect-pipeline`, `development-lifecycle-harness`, `domain-orchestration-harness`, `quality-gates-harness`, `workflow-skill-distiller` |
| 품질/산출물 | `deliverable-template-quality-harness`, `artifact-render-qa-harness`, `traceability-matrix-harness`, `role-execution-audit-harness`, `health-check-harness` |
| 게이트/상태 | `goal-state-harness`, `memory-state-harness`, `context-state-harness`, `review-gate-harness`, `qa-gate-harness` |
| 안전/운영 | `guard-policy-harness`, `command-hook-policy-harness`, `command-output-harness`, `snapshot-state-harness`, `token-optimizer`, `harness-evaluator`, `skill-catalog` |

새 스킬을 추가할 때 기본 구조:

```text
skills/<skill-folder>/SKILL.md
skills/<skill-folder>/references/usage.md
skills/<skill-folder>/examples/minimal-workflow.md
skills/<skill-folder>/scripts/smoke_check.py
skills/<skill-folder>/scripts/demo.py
```

추가 후 catalog/quality check를 실행합니다.

각 패키지 스킬에는 실행 가능한 demo도 포함됩니다.

```bash
python skills/token_optimizer/scripts/demo.py --output-dir ./tmp/token-demo
```

demo는 `success_case`, `blocked_or_failure_case`, `contracts`, `host_metadata`, `artifacts`, `verification`을 포함한 JSON을 출력합니다. `--output-dir`를 생략하면 demo 파일은 저장소 루트가 아니라 OS temp의 KH-UAF demo 디렉터리에 생성됩니다.

## Maintainer 품질 게이트

KH UAF 배포 전 이 저장소의 `skills/` 패키지를 검증합니다.

```bash
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
```

품질 검사는 KH UAF release gate이며, 외부 스킬을 평가하는 범용 ranking 도구가 아닙니다. 이 저장소에 포함된 스킬의 support-file wiring, smoke execution, runnable demo execution, implementation-target resolution, test evidence를 확인합니다. 상세 rubric과 최신 scorecard는 `docs/skillbook/audits/` 아래에 있습니다.

## 프로젝트 구조

```text
.codex-plugin/
  plugin.json
.agents/
  plugins/
    marketplace.json
    kh-uaf/
cli.py
plugin.json
SKILL.md
requirements.txt
src/
  contracts.py
  core/
  orchestration/
  platforms/
  tasks/
  harness/
  skills/
skills/
  <skill-folder>/SKILL.md
docs/
  skillbook/
tests/
```

## 환경 변수

기본값을 바꿔야 할 때만 설정합니다.

| 변수 | 기본값 | 용도 |
| --- | --- | --- |
| `AG_PLATFORM_MODE` | `local` | CLI와 runner 경로의 dispatcher mode |
| `AG_LLM_PROVIDER` | `offline` | 기본 CLI provider. 설정된 경우 `local`, `openai`, `codex`, `claude` 사용 |
| `AG_LLM_BASE_URL` | `http://localhost:11434/v1` | `--provider local`에서 사용하는 OpenAI-compatible local endpoint |
| `AG_WEBHOOK_URL` | unset | 외부 host callback용 optional subagent result webhook |
| `AG_API_KEY` | `antigravity-secret-key-v2` | webhook reporting이 켜졌을 때만 사용하는 API key |
| `AG_MAX_WORKERS` | `50` | CPU 기준으로 clamp되는 최대 async worker 수 |
| `AG_NO_SANDBOX` | `0` | `1`이면 sandbox 비활성화 |
| `AG_VERBOSE` | `0` | verbose server log |
| `UAF_RUNTIME_ROOT` | `%LOCALAPPDATA%/KH-UAF` | runtime state root |
| `UAF_PROJECT_LOCAL_STATE` | unset | 대상 프로젝트 안에 `.uaf/`를 써야 할 때만 `1`로 설정 |

## 검증

branch가 준비됐다고 말하기 전에 아래를 실행합니다.

```bash
python -m json.tool plugin.json
python -m json.tool .codex-plugin/plugin.json
python -m src.skills.uaf_skill_catalog --check
python -m src.skills.uaf_skill_quality
python -m unittest discover -s tests
python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"
```
