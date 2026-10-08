# KH Skills

**Claude와 Codex에서 사용하는 SQL·C#/Designer·PowerBuilder 개발 스킬.**

KH 3.0.26은 스킬 10개와 선택형 로컬 검사기를 하나의 저장소로 제공합니다. 두 플랫폼은 같은 `skills/`, `src/`, `scripts/`를 공유하며, 각 플랫폼용 manifest와 marketplace가 설치를 담당합니다.

[English](README.md) · [스킬](#스킬) · [로컬 검사](#선택형-로컬-검사) · [개발 검사](docs/development.md)

## 설치

### Claude Code

Claude Code 대화에서 다음 명령을 실행합니다.

```text
/plugin marketplace add GNh0/KH
/plugin install kh-skills@gnho-labs
```

설치 후 스킬 이름으로 호출할 수 있습니다.

```text
/kh-skills:sql-formatting
/kh-skills:csharp-designer-style-harness
/kh-skills:pb-to-csharp-migration-harness
```

로컬 소스를 시험하려면 저장소를 복제한 뒤 `claude --plugin-dir /absolute/path/to/KH`로 실행합니다. Claude용 설치 정보는 `.claude-plugin/plugin.json`과 `.claude-plugin/marketplace.json`에 있습니다.

Claude Code 터미널과 Desktop의 로컬 Code 세션은 사용자 범위의 플러그인 설정을 공유합니다. 다른 Claude 화면은 사용할 수 있는 플러그인 구성요소가 다르며, Python/PB 검사기는 로컬 파일을 실행할 수 있는 환경이 필요합니다. 화면·요금제별 조건은 [Anthropic 공식 문서](https://code.claude.com/docs/en/plugins)를 참고하세요.

### Codex

기존 저장소 marketplace를 등록합니다.

```sh
codex plugin marketplace add GNh0/KH
```

앱의 플러그인 목록에서 **KH Skills**를 선택해 설치합니다. 기술 식별자 `kh-uaf`와 marketplace 이름 `kh-uaf-marketplace`는 유지하고, Claude와 Codex 모두 공통 `release` 브랜치에서 설치합니다. 이전 설치를 업데이트할 때는 marketplace를 먼저 새로 고칩니다.

`$sql-formatting`처럼 필요한 스킬을 지정하거나 작업을 자연어로 요청합니다. Codex가 스킬 설명을 보고 관련 지침을 읽습니다. marketplace 등록과 설치 흐름은 [OpenAI 공식 문서](https://developers.openai.com/plugins/build/plugins)를 참고하세요.

### 필요한 스킬만 사용

전체 플러그인을 쓰지 않으려면 `skills/`에서 필요한 폴더를 해당 에이전트의 스킬 위치에 복사할 수 있습니다. 일부 참고 파일과 검사기는 저장소 루트 기준 상대 경로를 사용하므로 연결된 자료도 유지해야 합니다. SQL·C#·PB 도메인 스킬은 전체 플러그인 설치를 권장합니다.

KH 자체에 AI 모델, 에이전트 실행기 또는 API 크레딧이 들어 있지는 않습니다. 사용할 Claude·Codex 계정과 해당 환경의 권한이 필요합니다.

## 스킬

| 스킬 | 적용할 작업 |
| --- | --- |
| [sql-formatting](skills/sql-formatting/SKILL.md) | SQL/T-SQL 생성·정리·비교, 별칭 보존 |
| [csharp-designer-style-harness](skills/csharp-designer-style-harness/SKILL.md) | WinForms·DevExpress·프로젝트 컨트롤·Designer |
| [pb-to-csharp-migration-harness](skills/pb-to-csharp-migration-harness/SKILL.md) | PBL·DataWindow 분석과 원본에 근거한 C#/SQL 이관 |
| [work-planning](skills/work-planning/SKILL.md) | 규모가 크거나 중요한 선택이 남은 작업의 계획 |
| [work-execution](skills/work-execution/SKILL.md) | 승인된 다단계 작업과 진행·중단·재개 |
| [code-review](skills/code-review/SKILL.md) | 실제 변경, 요구 동작과 회귀 검토 |
| [systematic-debugging](skills/systematic-debugging/SKILL.md) | 오류 재현과 실제 실행 경로의 원인 분석 |
| [artifact-checks](skills/artifact-checks/SKILL.md) | 전달물 내용·파일 구조·렌더링 확인 |
| [context-handoff](skills/context-handoff/SKILL.md) | 진행 중인 작업을 이어가기 위한 간결한 인계 |
| [kh-maintenance](skills/kh-maintenance/SKILL.md) | KH 패키지·검사기·프로필·요청한 소스 로그 감사 |

## 작업 방식

현재 요청, 원본 소스, 실제 프로젝트 API와 사용자의 정정을 기준으로 작업합니다. 작고 명확한 수정은 직접 처리하고, 계획·검토는 해당 작업에 도움이 될 때 사용합니다. 공유 스킬은 현재 에이전트 환경에서 제공하는 도구를 따릅니다.

C# 작업은 같은 화면의 이벤트 흐름, 컨트롤 기본값, 이름과 조회·저장 계약을 유지합니다. 새 DevExpress 그리드는 사용자가 제공한 [DataWindowToXml 기본 속성](skills/csharp-designer-style-harness/references/grid-layout.md)을 사용하며, [코딩 방식](skills/csharp-designer-style-harness/references/coding-style.md)과 [컨트롤 초기화](skills/csharp-designer-style-harness/references/user-controls.md)를 함께 적용합니다. 기존 화면은 실제 원본을 비교 기준으로 삼습니다.

SQL 검사기는 지원하는 토큰과 배치를 확인하고, 업무 의미는 쿼리와 사용자 지시를 바탕으로 판단합니다. PB 이관은 원본 이벤트·상태·DataWindow·SP 매개변수와 결과를 먼저 연결합니다.

포함된 프로젝트 스타일에서 LINQ·중간 테이블·빌드는 비선호입니다. 피하면 구현이 어렵거나 대안의 성능이 극단적으로 불리할 때 구체적인 이유로 사용합니다. 현재 사용자의 명시적 지시가 우선합니다.

## 선택형 로컬 검사

Python 3.11 이상 표준 라이브러리만 사용합니다. API 키, 서버, DB 연결 또는 추가 Python 패키지 설치는 필요하지 않습니다. `<...>`를 실제 절대 경로로 바꿉니다.

```sh
python -B <KH-root>/scripts/kh_check.py sql <original.sql> <candidate.sql>
python -B <KH-root>/scripts/kh_check.py sql <source.sql> --preserve-aliases
python -B <KH-root>/scripts/kh_check.py csharp <candidate.cs> --original <original.cs> --designer <screen.Designer.cs>
python -B <KH-root>/scripts/kh_check.py designer <after.Designer.cs> --original <before.Designer.cs> --preserve-property btn.Visible
python -B <KH-root>/scripts/kh_check.py pb <source.srw> --encoding cp949
python -B <KH-root>/scripts/kh_check.py artifact <document.docx>
python -B <KH-root>/scripts/kh_check.py package <KH-root>
```

일반 검사의 종료 코드는 **0=수행한 검사 통과**, **1=오류 발견**, **2=입력 또는 검사 범위 미완성**입니다. `checked`와 `not_checked`를 함께 확인합니다. 정적 검사는 SQL 실행, C# 컴파일, Designer 동작, 전체 이관이나 실제 렌더링을 증명하지 않습니다. `sql --normalize-layout`은 지원하는 배치 변경을 stdout으로 출력합니다.

PB 스킬에는 PblScripter export 스크립트와 x86 추출기가 포함되어 있습니다. [내장 실행기](skills/pb-to-csharp-migration-harness/references/orca.md)가 설치된 PB 7.0·10.5·12.5를 시도하고 실제 추출에 성공한 런타임을 선택합니다. Windows PowerShell과 사용할 수 있는 정식 PB/ORCA 설치가 필요합니다.

개인 GitHub 의존성을 없애고 직원별 스타일을 적용하는 회사 배포는 별도의 [회사 ZIP 번들](company/README.ko.md)을 사용합니다. 회사 번들은 KH의 개인 스타일 기본값과 다른 project 정책을 적용하며, 현재 Codex marketplace 형식으로 제공합니다.

## 패키지와 검증

```text
.codex-plugin/plugin.json        Codex 설치 정보; 기존 kh-uaf 식별자
.agents/plugins/marketplace.json Codex marketplace; release 배포
.claude-plugin/plugin.json       Claude 설치 정보; kh-skills 식별자
.claude-plugin/marketplace.json  Claude marketplace; gnho-labs, release 배포
skills/                         공통 스킬과 참고 자료
src/ + scripts/                 공통 선택형 검사기
```

두 플랫폼 manifest는 같은 버전과 같은 스킬 트리를 사용합니다. 저장소 검증은 다음과 같이 실행합니다.

```sh
python -B -m unittest discover -s tests/domain
python -B scripts/kh_check.py package /absolute/path/to/KH
claude plugin validate /absolute/path/to/KH/.claude-plugin/plugin.json --strict
claude plugin validate /absolute/path/to/KH/.claude-plugin/marketplace.json --strict
```

[개발 검사](docs/development.md)는 고정 버전 Pyright와 CI도 실행합니다. 단위 검사·manifest 검증은 수행한 패키지 검사 범위를 확인하며, 모델의 실제 작업과 목표 환경은 별도로 검증해야 합니다. GitHub 공개와 이미 설치된 플러그인 캐시 갱신도 별도 단계입니다.

과거의 필수 intake, Python 호스트 루프, 역할 DAG 모의 실행, 중복 Goal·메모리·상태 저장소는 제거되었습니다. Goal·협업·권한·중단은 현재 호스트 도구를 따릅니다. [역사 문서](docs/README.md)는 이전 버전의 자료이며 현재 실행 지침으로 쓰지 않습니다.
