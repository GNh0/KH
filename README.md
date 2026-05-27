# 🤖 Universal Agent Framework (UAF) · V2.5

**Antigravity, Codex, Claude Code** 등 로컬 AI 에이전트를 위한  
**Zero-Dependency, Pure Python, Windows 완벽 호환** 오케스트레이션 엔진.

외부 브로커(Redis, RabbitMQ, Celery) 설치 없이 `python cli.py run` 한 줄로 모든 것이 동작합니다.

---

## ✨ V2.5 핵심 특징

| 기능 | 설명 |
|------|------|
| 🚀 **원클릭 런처** | `cli.py` 하나로 웹훅 서버 + 에이전트 루프 동시 구동 |
| ⚡ **Pure Asyncio 큐** | Celery 제거 → 파이썬 내장 `asyncio.Queue` 기반 초경량 병렬 처리 |
| 🛡️ **Windows 완벽 호환 샌드박스** | `signal.alarm` 제거 → `multiprocessing` 기반 타임아웃 강제 킬(Kill) |
| 💾 **GZIP 스냅샷** | 코드 백업 시 `gzip` 압축으로 디스크 용량 90% 절약, 무손실 롤백 |
| 🔒 **비동기 DB (aiosqlite + WAL)** | 동기식 sqlite3 제거 → `aiosqlite` + WAL 모드로 병렬 쓰기 병목 해소 |
| ♻️ **가비지 컬렉션 보장** | `try...finally`로 에러/타임아웃 시에도 임시 폴더 누수 원천 차단 |
| 🎛️ **환경변수 단일 관리** | 모든 설정값은 `.env.example` 참조, 코드 내 하드코딩 0개 |
| 🧩 **내장 스킬/하네스 카탈로그** | Antigravity, Superpowers, RTK 계열 패턴을 UAF-native `skills/<name>/SKILL.md`로 패키징 |

---

## 📁 프로젝트 구조

```
universal_agent_framework/
├── cli.py                    # ← AI 에이전트의 진입점 (여기만 실행하면 됨)
├── SKILL.md                  # 안티그래비티 Skill 플러그인 등록 설명서
├── .env.example              # 환경변수 전체 목록 및 기본값 문서
├── src/
│   ├── api/
│   │   └── server.py         # FastAPI Webhook (aiosqlite + WAL + API Key 인증)
│   ├── core/
│   │   ├── architect.py      # 요구사항 → 설계 문서(design_doc.md) 생성
│   │   └── snapshot_manager.py # gzip 기반 코드 버전 롤백 시스템
│   ├── harness/
│   │   └── sandbox.py        # AST 검증 + multiprocessing 타임아웃 샌드박스
│   ├── orchestration/
│   │   ├── agent_loop.py     # 메인 오케스트레이션 루프
│   │   └── llm_router.py     # LLM 통신 추상화 레이어
│   ├── platforms/
│   │   └── dispatcher_factory.py # 플랫폼별 디스패처 선택기
│   └── tasks/
│       └── workflows.py      # asyncio.Queue 기반 병렬 워커 엔진
└── skills/                   # UAF-native 에이전트 스킬/하네스 카탈로그
    ├── antigravity_agent_orchestration/
    ├── development_lifecycle_harness/
    ├── subagent_review_pipeline/
    ├── quality_gates_harness/
    ├── rtk_command_output_harness/
    └── command_hook_policy_harness/
```

---

## 🚀 빠른 시작

### 1. 의존성 설치
```bash
pip install fastapi uvicorn aiosqlite httpx pydantic
```

### 2. 실행 (한 줄로 끝)
```bash
# 기본 실행
python cli.py run --prompt "FastAPI 백엔드 서버 만들어줘"

# 특정 프로젝트 디렉토리 지정
python cli.py run --project ./my_app --prompt "쇼핑몰 만들어줘"

# 고급 옵션 (워커 수 조절 + 상세 로그)
python cli.py run --prompt "게임 만들어줘" --workers 20 --verbose

# 디버그용 (샌드박스 OFF)
python cli.py run --prompt "테스트" --no-sandbox

# 웹훅 서버만 단독 실행
python cli.py server --port 9000
```

---

## 🧩 내장 스킬/하네스 카탈로그

이 프로젝트는 외부 Gemini/Antigravity/RTK/Superpowers 설치 폴더를 런타임에 읽지 않습니다. 필요한 패턴은 저장소 내부의 `skills/<skill-folder>/SKILL.md`로 독립 패키징되어 있습니다.

### 참조 기반 핵심 하네스

| 계열 | UAF 스킬 | 용도 |
|------|----------|------|
| Antigravity | `antigravity-agent-orchestration` | agent/subagent, tool permission, lifecycle hook, observability |
| Superpowers | `development-lifecycle-harness` | 설계, 계획, TDD, 리뷰, 검증, 브랜치 완료 흐름 |
| Superpowers | `subagent-review-pipeline` | implementer → spec-reviewer → code-quality-reviewer 역할 파이프라인 |
| Superpowers | `quality-gates-harness` | failing-test-first, systematic debugging, evidence-before-completion |
| RTK | `rtk-command-output-harness` | 명령 출력 압축, grouping/truncation/dedup, exit code 보존 |
| RTK | `command-hook-policy-harness` | hook trust, permission precedence, integrity, fail-safe passthrough |

### 카탈로그 확인

```bash
# 전체 내장 스킬 목록
python -m src.skills.uaf_skill_catalog --list

# 특정 스킬 읽기
python -m src.skills.uaf_skill_catalog --read antigravity-agent-orchestration
python -m src.skills.uaf_skill_catalog --read rtk-command-output-harness
```

### 새 스킬 추가 방식

새 스킬은 별도 코드 등록 없이 `skills/<skill-folder>/SKILL.md`를 만들면 카탈로그에 잡힙니다. `SKILL.md`에는 YAML frontmatter의 `name`, `description`과 UAF 구현 타깃을 적으면 됩니다.

---

## ⚙️ 환경변수

모든 설정은 `.env.example`을 참조하세요. 주요 변수:

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `AG_WEBHOOK_URL` | `http://127.0.0.1:8000/...` | 웹훅 서버 주소 |
| `AG_API_KEY` | `antigravity-secret-key-v2` | API 인증 키 (서버/워커 동기화) |
| `AG_MAX_WORKERS` | `50` | 최대 워커 수 (CPU 코어×10 초과 불가) |
| `AG_NO_SANDBOX` | `0` | `1`로 설정 시 샌드박스 비활성화 (디버그 전용) |
| `AG_VERBOSE` | `0` | `1`로 설정 시 서버 상세 로그 출력 |

---

## 🏛️ 아키텍처 흐름

```
cli.py run
  │
  ├─ [1] FastAPI 서버 → 백그라운드 프로세스로 구동 (daemon=True)
  │         └─ /api/health 폴링으로 기동 확인 (최대 3초, 무한 대기 없음)
  │
  └─ [2] AgentLoop.run()
            ├─ SystemArchitect  → 요구사항 분석 & design_doc.md 생성
            ├─ DispatcherFactory → 대상 파일 목록 추출
            └─ asyncio.Queue    → 병렬 워커 N개 동시 실행
                  └─ 각 워커: 코드 생성 → Sandbox 검증 → Webhook 결과 전송
                        └─ Snapshot: gzip 압축 백업 / 롤백 지원
```

---

## 🔒 보안 아키텍처

- **AST 정적 분석**: `os`, `subprocess`, `sys`, `eval`, `exec` 등 위험 키워드 사전 차단
- **문자열 꼼수 방어**: f-string 등으로 블랙리스트를 우회하는 시도 차단
- **프로세스 격리**: 샌드박스 코드는 독립 자식 프로세스에서 실행, 타임아웃 초과 시 OS 단 강제 종료
- **경로 순회 방지**: `SnapshotManager`의 모든 경로는 `os.path.abspath` 검증 통과 필수
- **스냅샷 보호구역**: `.snapshots/` 내부 파일은 Commit/Rollback 대상에서 원천 제외

---

## 🗺️ 로드맵

- [x] V2.2 · aiosqlite + WAL 비동기 DB
- [x] V2.3 · Celery 제거 + asyncio 큐 + gzip 스냅샷 + Windows 샌드박스
- [x] V2.4 · 원클릭 CLI 런처 + 스마트 폴링 + 고급 옵션
- [x] V2.5 · 워커 하드 리미트 + 치명적 버그 수정 + 환경변수 단일화 + UAF-native 스킬/하네스 카탈로그
- [ ] V3.0 · OpenClaw / Hermes 분산 서버 연동 (예정)
