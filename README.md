# Universal Agent Framework (UAF)

Codex, Antigravity, Claude Code 같은 로컬 AI 코딩 에이전트에서 공통으로 쓸 수 있는 범용 오케스트레이션/스킬 하네스입니다.

핵심 목표는 외부 Gemini/Antigravity/RTK/Superpowers 설치 폴더에 의존하지 않고, 이 저장소 안의 `skills/<skill-folder>/SKILL.md`와 Python 계약만으로 역할, 병렬 작업, 리뷰, 검증 흐름을 재사용하는 것입니다.

## Quick Start

```bash
pip install -r requirements.txt
python cli.py run --project ./my_app --prompt "FastAPI 백엔드 서버 만들어줘"
```

자주 쓰는 명령:

```bash
# 내장 스킬 목록
python -m src.skills.uaf_skill_catalog --list

# 특정 스킬 읽기
python -m src.skills.uaf_skill_catalog --read orchestration-role-graph
python -m src.skills.uaf_skill_catalog --read antigravity-agent-orchestration

# 테스트
python -m unittest discover -s tests -v
```

## Core Flow

```text
cli.py run
  -> SystemArchitect creates design_doc.md
  -> AgentLoop attaches the default role graph
  -> DispatcherFactory selects local or Antigravity dispatch
  -> asyncio workers process file tasks
  -> sandbox / webhook / metadata report results
```

기본 병렬 worker는 현재 `implementer` 역할로 실행됩니다. `ceo`, `advisor`, reviewer, QA, security, release 역할은 `AdapterRequest.metadata`의 role graph에 포함되어 후속 게이트와 외부 에이전트 런타임이 사용할 수 있게 전달됩니다.

## Default Roles

기본 역할 그래프는 `src.orchestration.roles`가 원본입니다.

```text
ceo
advisor
product-strategist
system-architect
implementation-planner
controller
implementer
spec-reviewer
code-quality-reviewer
qa-verifier
security-reviewer
release-manager
```

## Packaged Skills

카탈로그는 `skills/` 폴더를 스캔합니다. 새 스킬은 `skills/<skill-folder>/SKILL.md`를 추가하면 됩니다.

| Skill | Purpose |
|------|---------|
| `orchestration-role-graph` | CEO, advisor, architect, controller, implementer, reviewer, QA, security, release 역할 계약 |
| `antigravity-agent-orchestration` | Antigravity식 agent/subagent/tool permission/hook/observability 패턴 |
| `parallel-orchestration-harness` | fan-out/fan-in, 병렬 worker, task aggregation |
| `subagent-review-pipeline` | implementer -> spec-reviewer -> code-quality-reviewer 리뷰 파이프라인 |
| `development-lifecycle-harness` | 설계, 계획, TDD, 리뷰, 검증, 브랜치 완료 흐름 |
| `quality-gates-harness` | TDD, systematic debugging, evidence-before-completion |
| `rtk-command-output-harness` | 명령 출력 압축, grouping/truncation/dedup, exit code 보존 |
| `command-hook-policy-harness` | hook trust, permission precedence, integrity, fail-safe passthrough |
| `adapter-contract-harness` | Codex/Antigravity/Claude/local adapter 계약 |
| `architect-pipeline` | 요구사항에서 설계 문서 생성 |
| `harness-evaluator` | Python 코드 샌드박스 평가 |
| `skill-catalog` | 내장 UAF 스킬 목록/읽기 |
| `token-optimizer` | 긴 로그와 코드 출력 압축 |
| `workflow-skill-distiller` | 반복 workflow를 새 스킬로 패키징 |

## Project Layout

```text
cli.py
plugin.json
SKILL.md
requirements.txt
src/
  contracts.py
  orchestration/
    agent_loop.py
    roles.py
    llm_router.py
  platforms/
    dispatcher_factory.py
  tasks/
    workflows.py
  harness/
    sandbox.py
    evaluator.py
  skills/
    uaf_skill_catalog.py
skills/
  <skill-folder>/SKILL.md
tests/
```

## Environment

주요 환경변수는 필요할 때만 설정하면 됩니다.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AG_WEBHOOK_URL` | `http://127.0.0.1:8000/api/webhook/subagent-result` | subagent result webhook |
| `AG_API_KEY` | `antigravity-secret-key-v2` | webhook API key |
| `AG_MAX_WORKERS` | `50` | max async workers, clamped by CPU |
| `AG_NO_SANDBOX` | `0` | disable sandbox when set to `1` |
| `AG_VERBOSE` | `0` | verbose server logs |

## Verification

```bash
python -m json.tool plugin.json
python -m unittest discover -s tests -v
python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]"
python -m src.skills.uaf_skill_catalog --list
```
