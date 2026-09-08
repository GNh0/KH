# KH for Codex

KH 3.0.2는 현재 Codex 도구와 실제 소스에 맞춘 스킬 10개와 선택적 로컬 검사기다. [English](README.md)

작고 명확한 요청은 직접 처리한다. 필요한 도메인 스킬만 읽고, 현재 사용자 정정·원본·비교 화면·API를 기준으로 작업한다. 과거 세션과 `docs/kh`, `docs/skillbook`의 오래된 보고서는 참고 자료다.

새 그리드는 사용자가 제공한 [DataWindowToXml 기본 속성](skills/csharp-designer-style-harness/references/grid-layout.md)을 사용한다. 셀 TextOptions·SpinEdit EditMask·DisplayFormat·OptionsBehavior를 기본으로 덧붙이지 않고, 일반 편집 차단·버튼 동작 유지·편집 가능 컬럼을 구분한다. 기존 화면은 원본과 비교해 현재 설정을 보존한다.

## 스킬

| 스킬 | 적용할 작업 |
| --- | --- |
| [work-planning](skills/work-planning/SKILL.md) | 규모가 크거나 중요한 선택이 남은 작업의 계획 |
| [work-execution](skills/work-execution/SKILL.md) | 승인된 다단계 작업, 중단·재개, 현재 호스트 도구 사용 |
| [code-review](skills/code-review/SKILL.md) | 실제 변경과 요구 동작의 검토 |
| [systematic-debugging](skills/systematic-debugging/SKILL.md) | 실제 오류 단계와 경로의 원인 분석 |
| [sql-formatting](skills/sql-formatting/SKILL.md) | SQL 생성·정리·비교·수정과 최종 텍스트 확인 |
| [csharp-designer-style-harness](skills/csharp-designer-style-harness/SKILL.md) | WinForms/DevExpress/KoneLib 코드와 Designer |
| [pb-to-csharp-migration-harness](skills/pb-to-csharp-migration-harness/SKILL.md) | PB/PBL/DataWindow 분석 및 C#/SQL 이관 |
| [artifact-checks](skills/artifact-checks/SKILL.md) | 요청한 전달물의 내용·구조·렌더링 확인 |
| [context-handoff](skills/context-handoff/SKILL.md) | 현재 작업을 이어가기 위한 간결한 인계 |
| [kh-maintenance](skills/kh-maintenance/SKILL.md) | KH 자체 수정, 패키지·프로필·명시적 로그 감사 |

LINQ·중간 테이블·빌드는 비선호다. 피하면 구현이 어렵거나 대안의 성능이 극단적으로 불리한 경우에만 구체적 이유로 사용한다. 단순 코드 단축·편의·의례적인 검증은 예외 이유가 아니다. 현재 작업에서 사용자가 명시적으로 금지하면 그 지시를 따른다.

## 선택적 검사

Python 3.11 이상 표준 라이브러리를 사용한다. 서버 실행, API 키, DB 연결 또는 별도 Python 패키지 설치가 필요하지 않다. 명령의 `<...>`는 실제 절대 경로로 바꾼다.

```powershell
python -B <plugin-root>/scripts/kh_check.py sql <original.sql> <candidate.sql>
python -B <plugin-root>/scripts/kh_check.py sql <source.sql> --preserve-aliases
python -B <plugin-root>/scripts/kh_check.py csharp <candidate.cs> --original <original.cs> --designer <screen.Designer.cs>
python -B <plugin-root>/scripts/kh_check.py designer <after.Designer.cs> --original <before.Designer.cs> --preserve-property btn.Visible
python -B <plugin-root>/scripts/kh_check.py pb <source.srw> --encoding cp949
python -B <plugin-root>/scripts/kh_check.py artifact <document.docx>
python -B <plugin-root>/scripts/kh_check.py package <plugin-root>
```

일반 결과의 종료 코드는 0=수행한 검사 통과, 1=검사 오류 발견, 2=입력/검사 범위 미완성이다. 비선호·스타일 경고는 별도로 표시한다. `checked`, `not_checked`를 함께 읽는다. SQL 토큰 비교는 DB 의미 동등성 증명이 아니며, C# 정적 검사는 컴파일·UI 실행이 아니다. 파일 구조 검사는 실제 렌더링을 대신하지 않는다. `--normalize-layout`은 지원하는 JOIN/EXISTS 배치만 stdout으로 출력하며 원본을 쓰지 않는다.

PB의 ORCA probe/추출, DataWindow XML·Designer 초안, 이벤트/상태·SP 매개변수·결과 측정 비교는 [PB 참고 자료](skills/pb-to-csharp-migration-harness/SKILL.md)에 있다. 도구 출력이 실제 실행·전체 이관을 증명하지 않는 부분을 구분한다.

개발 검증은 저장소 루트에서 `python -B -m unittest discover -s tests/domain`으로 실행한다. [개발 검사](docs/development.md)는 고정 버전 Pyright로 전체 실행 모듈을 검사하고 입력 검증·공유 lexer에는 엄격한 타입 검사를 적용한다. Node/Pyright는 개발 검사에만 쓰며 KH 실행 의존성이 아니다. [시나리오 평가](skills/kh-maintenance/references/scenario-evaluation.md)는 실제 호스트 평가와 단위/모의 검사를 구분한다.

## 2.9에서 변경

필수 front door/intake, Python 호스트 실행 루프, 메타데이터만 만드는 역할 DAG, 중복 Goal/메모리/상태 저장소, HMAC·실행 영수증·자기평가 점수 체계와 관련 테스트를 제거했다. Goal·협업·예약·권한·중단은 현재 호스트 도구 계약과 사용자 요청을 따른다.

기존 `cli.py`, FastAPI 서버, root `plugin.json` 및 오래된 workflow API는 더 이상 제공하지 않는다. 유지한 순수 함수 일부만 `src/skills`의 작은 import 연결로 남겼다. 신규 API는 `src/sql`, `src/csharp`, `src/pb`, `src/common`, `src/artifacts`, `src/maintenance`에 있다. 자세한 변경과 검증 범위는 [문서 목록](docs/README.md)을 확인한다.

정식 manifest는 `.codex-plugin/plugin.json`이다. 원격 marketplace의 `kh-uaf` 이름과 `codex-runtime` ref는 유지한다. 이 작업 트리의 수정과 현재 설치된 캐시는 별개다. 설치·배포 요청이 있을 때 현재 plugin-creator 흐름으로 배포 대상을 확인하고 적용한다.
