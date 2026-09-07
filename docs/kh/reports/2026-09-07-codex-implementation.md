# KH Codex 재구성 결과 — 2026-09-07

KH 소스 패키지를 3.0.0 구조로 재구성했다. 45개 스킬을 10개로 통합하고 중복 실행 체계를 제거했다. 아래의 반영 상태와 실제 검증 범위를 구분한다. 현재 설치 캐시는 이번 로컬 수정으로 갱신되지 않았다.

## 실제 변경

- 기준 commit: `c6a3de2f61c02cec108cabda18a7d5598e9cf296`. 추적 파일 442개 삭제, 11개 수정. 새 스킬·소스·테스트는 별도 새 파일이다.
- 필수 front door/intake, Python 서버·호스트 루프·다른 호스트 dispatcher, 메타데이터 역할 DAG, HMAC/영수증, 중복 Goal·memory·상태 저장과 관련 고정 점수/통과 테스트를 제거했다.
- SQL 스코프·별칭 참조·토큰/한글/주석 보존, C# 메서드·트랜잭션/Designer 비교, PB export·DataWindow·이벤트/상태·SP 매개변수·실측 결과 비교를 목적별 모듈로 분리했다.
- LINQ·중간 테이블·빌드는 비선호다. 피하면 구현이 어렵거나 대안 성능이 극단적으로 불리할 때만 사용한다. 편의·단축·의례적인 검증은 이유가 아니다. 현재 명시적 금지는 우선한다.
- 생성 기본 이름·폰트·Visible이 현재 사용자 설정을 덮지 않도록 명시한 이름/속성 입력과 보존 검사를 추가했다. ORCA exit 0 + 오류·새 PB 출력 없음/잘못된 출력은 성공으로 처리하지 않는다.
- 원래 untracked 파일 23개와 원격 marketplace 파일은 해시가 같다. 과거 runtime 데이터, `.worktrees`, 감사/계획 원문과 역사 문서는 보존했다. 폐기한 소스의 생성 bytecode 197개만 추가 정리했다.
- root `cli.py`/서버/workflow API는 호환성이 깨지는 삭제다. `src/skills`에는 일부 순수 함수의 import 연결만 남겼다. 모든 예전 인자/호출을 호환한다고 주장하지 않는다.

## 이전 에이전트 실패와 이번 대응

로컬 원문 감사의 25개 사건은 확정·한계 있음·미해결·긍정 반례를 구분한다. 모든 과거 실패를 한 원인이나 KH 탓으로 묶지 않는다. 대화 원문과 상세 감사 자료는 공개 패키지에 포함하지 않는다.

| 관찰한 원인 | 이번 변경 |
| --- | --- |
| 요청 범위보다 앞선 intake/상태/서명 절차와 불필요한 재승인 | 직접 처리와 필요한 스킬만 남기고 해당 실행 코드를 제거 |
| 별칭 정리를 빠뜨리거나 사용자 정정을 반대로 문서/테스트에 고정 | 정리 기본값·명시적 보존을 분리하고 중첩 스코프/독립 실제 답변으로 확인 |
| DefaultRoleRunner의 역할 파일 생성과 실제 에이전트 실행 혼동 | 역할 시뮬레이터 제거, 현재 협업 도구의 생성/결과/실패를 구분 |
| 고정 스타일·이름·폰트, SAVE 일부 또는 빌드 성공을 전체 화면 완료로 확대 | 실제 대상/사용자 속성과 전체 요청 범위 확인, 정적/실행 증거 분리 |
| 잘못된 ORCA 버전 추정·exit code만 확인, 오류 단계 혼동 | 명시한 버전과 x86/PATH/출력 검사를 유지하고 실패 진단 보강 |
| 중단 뒤 자동 Goal 재개, 협업 API의 지원하지 않는 인자 사용 | 자체 continuation 제거, 현재 native 도구 계약과 중단/예약 지시를 적용 |
| 체크아웃과 설치 캐시 불일치 | 소스 manifest와 실제 설치본을 구분하며 배포 요청 때만 설치 흐름 진행 |

## 검증과 한계

- 도메인 검사 86개: Python 3.14 및 번들 Python 3.12.14에서 통과. ORCA 프로세스·DLL은 fixture/모의 환경이며 실제 ERP 빌드는 수행하지 않았다.
- 공식 plugin-creator validator 통과, skill-creator quick_validate에서 스킬 10개 통과. 검증기만 필요한 PyYAML은 임시 폴더에 받았고 KH 런타임 의존성에 추가하지 않았다.
- 실제 신규 모듈 import 43개와 Python 3.11 문법 AST 확인, 패키지/참조/import 검사 통과. Python 3.11 실행 검증은 별도 수행하지 않았다.
- SQL 독립 사용 평가: A/B/C와 내부 T 별칭으로 결과 SQL 생성, 최종 검사 issues 0. 발견한 JOIN 문서 예시 불일치·파생 JOIN 예시 누락을 수정하고 normalizer의 제한 범위를 설명했다.
- C# 독립 사용 평가: 포커스 DataRow와 null 검사 적용, 기존 helper·Designer 바이트 보존. 프로젝트 없는 입력의 버전/API 확인 한계 안내를 추가했다.
- 36개 전체 시나리오를 실호스트에서 실행한 것은 아니다. SQL/C# 독립 평가 2건과 이 작업의 native Goal 관찰을 기록했다. 나머지 실제 앱/DB/설치/중단 이벤트 평가는 통과로 표시하지 않는다.
- 토큰 비교는 완전한 T-SQL 의미 증명이 아니고 C#·PB 분석기는 전체 컴파일러가 아니다. ZIP/XML/header는 내용·UI·보고서 렌더링 검증을 대신하지 않는다.
- 비교 대상이 없는 소스, 동적 호출·상속/조건부 프로젝트 항목, 실제 DB 타입·XML 스키마·런타임 바인딩은 결과의 `not_checked`/`incomplete`와 소스 검토로 다룬다.

[최종 검증 기록](2026-09-07-codex-verification.json)에 실행 결과와 검증한 소스 해시를 저장했다. 독립 평가 입력/출력과 실행 상세는 로컬 작업 자료로 보존했다. 독립 평가의 결과를 고정 정답으로 입력 fixture에 섞지 않았다.

## 48개 요구의 반영 위치

각 행의 검사는 해당 규칙 일부를 확인하는 범위다. **지침으로 반영한 운영/업무 판단을 전부 자동 검증한 것으로 해석하지 않는다.** 원문 증거와 정정 순서는 기존 감사에 있고, 아래 JSON은 새 구현 위치를 연결한다.

| 요구 | 반영 위치 | 확인 범위 |
| --- | --- | --- |
| R01 현재 원본·정확한 프로젝트·사용자 수정 보호 | [SKILL.md](../../../skills/csharp-designer-style-harness/SKILL.md), [files.py](../../../src/common/files.py), [designer.py](../../../src/csharp/designer.py) | 현재 파일의 변경 충돌과 명시한 Designer 속성 보존을 검사한다. [test_common.py](../../../tests/domain/test_common.py), [test_csharp.py](../../../tests/domain/test_csharp.py) |
| R02 명시한 비교 화면과 코드 패턴 적용 | [SKILL.md](../../../skills/csharp-designer-style-harness/SKILL.md), [data-flow.md](../../../skills/csharp-designer-style-harness/references/data-flow.md) | 지정 비교 화면과 현재 helper/명령 패턴을 기준으로 한다. 독립 C# 평가에서도 기존 helper를 보존했다. [test_csharp.py](../../../tests/domain/test_csharp.py) |
| R03 SQL 정리의 별칭 정규화 기본값 | [SKILL.md](../../../skills/sql-formatting/SKILL.md), [style.md](../../../skills/sql-formatting/references/style.md) | 일반 정리에 역할별 별칭 정규화를 포함하며 독립 SQL 평가에서 실제 적용했다. [test_sql.py](../../../tests/domain/test_sql.py) |
| R04 SQL 별칭을 업무 역할과 스코프로 분류 | [style.md](../../../skills/sql-formatting/references/style.md), [aliases.py](../../../src/sql/aliases.py), [scopes.py](../../../src/sql/scopes.py) | 역할 판단은 현재 쿼리에서 하고, 도구는 명시한 스코프·참조만 변경한다. [test_sql.py](../../../tests/domain/test_sql.py) |
| R05 JOIN·ON·AND와 파생 테이블 정렬 | [style.md](../../../skills/sql-formatting/references/style.md), [layout.py](../../../src/sql/layout.py) | JOIN/ON/AND 및 파생 JOIN 예시를 독립 평가의 진단과 맞췄다. [test_sql.py](../../../tests/domain/test_sql.py) |
| R06 선행 쉼표·대문자·CASE·괄호·절 배치 | [style.md](../../../skills/sql-formatting/references/style.md), [layout.py](../../../src/sql/layout.py) | 선행 쉼표·CASE·IF EXISTS·GROUP/ORDER와 테이블/컬럼 AS를 구분한다. 자동 검사는 토큰/배치의 일부 범위다. [test_sql.py](../../../tests/domain/test_sql.py) |
| R07 INSERT 열과 SELECT 값의 줄 묶음 대응 | [style.md](../../../skills/sql-formatting/references/style.md), [layout.py](../../../src/sql/layout.py), [compare.py](../../../src/sql/compare.py) | 열/값의 묶음 배치와 토큰 순서 변경을 구분한다. [test_sql.py](../../../tests/domain/test_sql.py) |
| R08 SQL 의미·주석·문자열·출력 계약 보존 | [lexer.py](../../../src/sql/lexer.py), [compare.py](../../../src/sql/compare.py) | 리터럴·한글·주석·JOIN 종류·출력 열/값 순서와 허용된 별칭 변경을 비교한다. [test_sql.py](../../../tests/domain/test_sql.py), [test_cli.py](../../../tests/domain/test_cli.py) |
| R09 정리·생성·리팩터링·실행 범위 구분 | [SKILL.md](../../../skills/sql-formatting/SKILL.md), [checks.py](../../../src/sql/checks.py) | 정리/생성/비교/실행을 구분한다. 의미 변환은 별도 실제 검토 대상이다. [test_sql.py](../../../tests/domain/test_sql.py), [test_cli.py](../../../tests/domain/test_cli.py) |
| R10 간결하고 전체 붙여넣기 가능한 SQL·코드 | [SKILL.md](../../../skills/sql-formatting/SKILL.md), [SKILL.md](../../../skills/work-execution/SKILL.md) | 요청한 전체 붙여넣기 SQL·코드 또는 정확한 교체문을 전달한다. 두 독립 평가에서 결과 파일을 생성했다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R11 단순 UPDATE에 불필요한 실행 절차를 추가하지 않음 | [style.md](../../../skills/sql-formatting/references/style.md) | UPDATE 전달만이면 요청한 UPDATE FROM/CROSS APPLY 형태를 완성하고 불필요한 실행 절차를 붙이지 않는다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R12 업무 계산은 현재 함수와 저장 계약에서 도출 | [style.md](../../../skills/sql-formatting/references/style.md), [data-flow.md](../../../skills/csharp-designer-style-harness/references/data-flow.md) | 현재 계산 함수와 XML/SAVE 계약을 읽으며 GET_CHGRAT 대신 환율을 하드코딩하지 않는다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R13 선호 SQL 형태와 필요성에 따른 제한적 예외 | [SKILL.md](../../../skills/sql-formatting/SKILL.md), [preferences.md](../../../skills/work-execution/references/preferences.md), [checks.py](../../../src/sql/checks.py) | 기본 선호를 적용하되 의미가 바뀌는 기계적 JOIN 치환은 하지 않는다. 중간 테이블 진단은 경고다. [test_sql.py](../../../tests/domain/test_sql.py) |
| R14 작성자 스타일을 검증 후 패키지 프로필에 고정 | [default-profile.json](../../../skills/csharp-designer-style-harness/references/default-profile.json), [default-profile.json](../../../skills/pb-to-csharp-migration-harness/references/default-profile.json), [pb-profile-maintenance.md](../../../skills/kh-maintenance/references/pb-profile-maintenance.md) | 범위별 검증 패턴을 보관하고 일반 작업의 작성자 재검색·프로필 서명 요구를 제거했다. [test_maintenance.py](../../../tests/domain/test_maintenance.py) |
| R15 구체 예시 이름·업무 규칙의 범용화 방지 | [default-profile.md](../../../skills/pb-to-csharp-migration-harness/references/default-profile.md), [keys.py](../../../src/pb/keys.py), [layout.py](../../../src/pb/layout.py) | 임의 개수의 원시 키를 보존하고, 명시한 컨트롤 이름·바인딩이 기본 예시보다 우선한다. [test_pb.py](../../../tests/domain/test_pb.py) |
| R16 정적 UI와 Designer 소유권 | [designer.md](../../../skills/csharp-designer-style-harness/references/designer.md), [designer.py](../../../src/csharp/designer.py), [checks.py](../../../src/csharp/checks.py) | 정적 UI는 Designer, 동적 업무는 실제 code-behind 패턴을 따른다. factory와 새 정적 UI 대입을 검토 진단한다. [test_csharp.py](../../../tests/domain/test_csharp.py) |
| R17 프레임워크 명령·초기화·이벤트 위치 | [data-flow.md](../../../skills/csharp-designer-style-harness/references/data-flow.md) | Load/initControl/명령 이벤트 위치와 중복 초기화·메시지를 실제 프레임워크에서 확인한다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R18 실제 컨트롤·컬럼·메서드 명명 규칙 | [designer.md](../../../skills/csharp-designer-style-harness/references/designer.md), [datawindow.py](../../../src/pb/datawindow.py), [layout.py](../../../src/pb/layout.py) | 현재 명명과 명시한 매핑을 사용하고 중복·유효하지 않은 생성 멤버를 검사한다. [test_pb.py](../../../tests/domain/test_pb.py) |
| R19 HTML·DataWindow의 구조와 레이아웃 보존 | [datawindow.md](../../../skills/pb-to-csharp-migration-harness/references/datawindow.md), [datawindow.py](../../../src/pb/datawindow.py), [designer.py](../../../src/csharp/designer.py) | HTML/DW 레이아웃을 실제 입력으로 취급한다. DW 열·caption·순서와 지정 TabIndex를 검사하며 실제 HTML/UI 렌더링은 별도다. [test_pb.py](../../../tests/domain/test_pb.py), [test_csharp.py](../../../tests/domain/test_csharp.py) |
| R20 헤더와 셀 정렬·서머리·그룹·lookup·버튼 | [designer.md](../../../skills/csharp-designer-style-harness/references/designer.md), [datawindow.py](../../../src/pb/datawindow.py), [designer.py](../../../src/csharp/designer.py) | 헤더/셀과 lookup/숫자 Repository/등록을 구분한다. summary·그룹·버튼 업무 동작은 실제 화면 검토가 필요하다. [test_pb.py](../../../tests/domain/test_pb.py), [test_csharp.py](../../../tests/domain/test_csharp.py) |
| R21 UserControl 기본값과 대상별 폰트·Visible 상태 | [designer.md](../../../skills/csharp-designer-style-harness/references/designer.md), [designer.py](../../../src/csharp/designer.py), [datawindow.py](../../../src/pb/datawindow.py) | UserControl 기본 크기를 가정하지 않고 명시한 Font/Visible 보존과 생성 템플릿 override를 지원한다. [test_csharp.py](../../../tests/domain/test_csharp.py), [test_pb.py](../../../tests/domain/test_pb.py) |
| R22 포커스 행과 체크 선택 행 구분 | [data-flow.md](../../../skills/csharp-designer-style-harness/references/data-flow.md) | 포커스와 체크 선택을 구분한다. 독립 C# 평가에서 GetFocusedDataRow와 null 검사를 적용했다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R23 SAVE 외 화면 생명주기 전체 비교 | [data-flow.md](../../../skills/csharp-designer-style-harness/references/data-flow.md), [validation.md](../../../skills/pb-to-csharp-migration-harness/references/validation.md), [events.py](../../../src/pb/events.py) | 전체 화면에는 전체 생명주기를 매핑한다. 누락 이벤트 검사는 일부 자동화이며 실제 전체 화면 실행 검증은 별도다. [test_pb.py](../../../tests/domain/test_pb.py) |
| R24 NEW/MOD/DEL 변경분 저장과 필드 소유권 | [data-flow.md](../../../skills/csharp-designer-style-harness/references/data-flow.md), [delta.py](../../../src/sql/delta.py), [events.py](../../../src/pb/events.py), [checks.py](../../../src/csharp/checks.py) | NEW/MOD/DEL·필드 소유권을 보존하며 전체 삭제/재등록과 모든 행 재작성은 검토 대상으로 남긴다. [test_sql.py](../../../tests/domain/test_sql.py), [test_pb.py](../../../tests/domain/test_pb.py) |
| R25 검증 위치와 C#·SP 인터페이스 | [data-flow.md](../../../skills/csharp-designer-style-harness/references/data-flow.md), [sql.md](../../../skills/pb-to-csharp-migration-harness/references/sql.md), [sql.py](../../../src/pb/sql.py) | 실제 SP 정의의 필수/선택 매개변수를 선택 호출과 비교한다. 타입·XML·동적 호출·검증 위치는 실제 소스 검토 사항이다. [test_pb.py](../../../tests/domain/test_pb.py) |
| R26 LINQ·중간 테이블 비선호와 좁은 예외 | [preferences.md](../../../skills/work-execution/references/preferences.md), [checks.py](../../../src/csharp/checks.py), [checks.py](../../../src/sql/checks.py) | LINQ·중간 테이블은 좁은 필요성 예외가 있는 비선호 경고이며 전역 금지가 아니다. [test_csharp.py](../../../tests/domain/test_csharp.py), [test_sql.py](../../../tests/domain/test_sql.py) |
| R27 불필요한 헬퍼·추상화·중복 코드 억제 | [SKILL.md](../../../skills/csharp-designer-style-harness/SKILL.md), [data-flow.md](../../../skills/csharp-designer-style-harness/references/data-flow.md), [checks.py](../../../src/csharp/checks.py) | 새 추상화나 중복 helper를 관성적으로 만들지 않으며 현재 메서드·트랜잭션 계열 변경을 확인한다. [test_csharp.py](../../../tests/domain/test_csharp.py) |
| R28 Excel 실제 시트·행·거래처 매칭·오류 모음 | [data-flow.md](../../../skills/csharp-designer-style-harness/references/data-flow.md) | 실제 시트/헤더/셀/키를 읽는다. 해당 업로드 패턴은 정상 행 직접 추가와 오류 모음이며 모든 업로드로 확대하지 않는다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R29 새 파일·프로젝트 등록·Designer 지원 구문 | [designer.md](../../../skills/csharp-designer-style-harness/references/designer.md), [preflight.py](../../../src/pb/preflight.py), [designer.py](../../../src/csharp/designer.py) | 실제 project 선언·소스 가용성·SDK 제외/조건·Designer 구문을 확인하고 MSBuild/Designer 실행과 구분한다. [test_pb.py](../../../tests/domain/test_pb.py), [test_csharp.py](../../../tests/domain/test_csharp.py) |
| R30 PB 정확한 PBL·객체·상속·이벤트 원본 추출 | [SKILL.md](../../../skills/pb-to-csharp-migration-harness/SKILL.md), [source.py](../../../src/pb/source.py), [checks.py](../../../src/pb/checks.py) | 제공 export의 객체·부모·이벤트·연결 DW 범위를 추출한다. 미제공 객체 전체를 읽었다고 하지 않는다. [test_pb.py](../../../tests/domain/test_pb.py) |
| R31 PB 분석 자료가 실제 구현 가능한 수준인지 확인 | [validation.md](../../../skills/pb-to-csharp-migration-harness/references/validation.md), [planning.py](../../../src/pb/planning.py) | 범위에 맞는 구현 순서와 연결 정보를 계획하며 SQL만 요청한 작업에 화면 생성을 강제하지 않는다. [test_pb.py](../../../tests/domain/test_pb.py) |
| R32 ORCA 환경·실제 출력·오류 진단 | [orca.md](../../../skills/pb-to-csharp-migration-harness/references/orca.md), [orca.py](../../../src/pb/orca.py) | 선택 버전·x86·자식 PATH·인코딩과 오류 진단/새 PB 출력 확인을 유지했다. 실제 ORCA 설치 환경 실행은 이번 범위 밖이다. [test_orca.py](../../../tests/domain/test_orca.py) |
| R33 보고서 밴드와 실제 렌더링·출력 검증 | [datawindow.md](../../../skills/pb-to-csharp-migration-harness/references/datawindow.md), [SKILL.md](../../../skills/artifact-checks/SKILL.md), [checks.py](../../../src/artifacts/checks.py) | 공통 보고서 변환 경로와 H/D/F·그룹·밴드·생성자 부작용을 검토한다. 구조 통과와 렌더링 성공을 분리한다. [test_maintenance.py](../../../tests/domain/test_maintenance.py) |
| R34 빌드 비선호와 필요한 검증만 수행 | [preferences.md](../../../skills/work-execution/references/preferences.md), [SKILL.md](../../../skills/csharp-designer-style-harness/SKILL.md), [orca.py](../../../src/pb/orca.py) | 의례적 빌드를 피하고 추출 helper가 실제 필요한 경우에만 선택하도록 했다. C# 독립 평가에서는 빌드를 수행하지 않았다. [test_orca.py](../../../tests/domain/test_orca.py) |
| R35 중단 우선과 자동 Goal 재개 차단 | [SKILL.md](../../../skills/work-execution/SKILL.md), [SKILL.md](../../../skills/context-handoff/SKILL.md) | 중단 후 자동 Goal 메시지로 작업을 재개하지 않는다. 기존 자동 continuation 상태 코드를 제거했다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R36 현재 사용자 승인·범위·후속 정정 유지 | [SKILL.md](../../../skills/work-planning/SKILL.md), [SKILL.md](../../../skills/work-execution/SKILL.md), [SKILL.md](../../../skills/context-handoff/SKILL.md) | 현재 승인과 최신 정정을 유지하고 계획 서식 재승인을 요구하지 않는다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R37 읽기·확인 요청을 변경 작업으로 확대하지 않음 | [SKILL.md](../../../skills/sql-formatting/SKILL.md), [SKILL.md](../../../skills/work-planning/SKILL.md) | 확인·비교 요청을 쓰기 작업으로 확대하지 않는다. CLI도 입력 파일을 변경하지 않는다. [test_cli.py](../../../tests/domain/test_cli.py) |
| R38 실제 실패 단계와 원인 확인 후 최소 수정 | [SKILL.md](../../../skills/systematic-debugging/SKILL.md), [equivalence.py](../../../src/pb/equivalence.py), [orca.py](../../../src/pb/orca.py) | 실패 단계와 실제 측정 조건을 구분하며 exit 0·부분 결과만으로 원인을 확정하지 않는다. [test_pb.py](../../../tests/domain/test_pb.py), [test_orca.py](../../../tests/domain/test_orca.py) |
| R39 현재 사용 가능한 스킬·도구와 일관된 규칙 | [SKILL.md](../../../skills/kh-maintenance/SKILL.md), [package_check.py](../../../src/maintenance/package_check.py), [plugin.json](../../../.codex-plugin/plugin.json) | 실제 발견된 스킬·참조·import와 공식 manifest 형식을 검증한다. [test_maintenance.py](../../../tests/domain/test_maintenance.py) |
| R40 호스트 도구 중심 실행과 실제 위임 증명 | [delegation.md](../../../skills/work-execution/references/delegation.md), [session_report.py](../../../src/maintenance/session_report.py) | 현재 협업 도구만 사용하고 생성/결과/실패를 구분한다. 실제 독립 평가 2건을 수행했다. [test_maintenance.py](../../../tests/domain/test_maintenance.py) |
| R41 Goal은 요청 시에만 생성하고 완료 근거 확인 | [SKILL.md](../../../skills/work-execution/SKILL.md) | 사용자가 요청한 native Goal을 사용하며 별도 KH ledger와 임의 token_budget를 만들지 않는다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R42 자기평가·정해진 테스트 통과와 실제 품질 구분 | [scenario-evaluation.md](../../../skills/kh-maintenance/references/scenario-evaluation.md), [results.py](../../../src/common/results.py) | 단위·모의·실제 호스트·UI/DB 증거를 구분한다. 고정 점수와 역할 JSON 성공 판정을 제거했다. [test_maintenance.py](../../../tests/domain/test_maintenance.py) |
| R43 단순 요청의 불필요한 지연·절차·출력 억제 | [SKILL.md](../../../skills/work-planning/SKILL.md), [SKILL.md](../../../skills/sql-formatting/SKILL.md), [SKILL.md](../../../skills/kh-maintenance/SKILL.md) | 작고 명확한 요청을 직접 처리하도록 하고 catch-all intake/전체 스킬 로드를 제거했다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R44 현재 체크아웃·브랜치·설치 캐시 구분 | [SKILL.md](../../../skills/kh-maintenance/SKILL.md), [README.ko.md](../../../README.ko.md), [marketplace.json](../../../.agents/plugins/marketplace.json) | 소스 3.0.0과 설치 캐시를 구분하며 원격 이름/ref를 보존했다. 이번 작업은 로컬 변경이다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R45 업무 DB 변경의 정확한 대상·거래·검증 | [style.md](../../../skills/sql-formatting/references/style.md) | 실제 DB 변경 요청에는 정확한 연결/DB/대상 키/트랜잭션/사후 값과 제외 행을 확인한다. 이번 작업에서 업무 DB 변경은 없다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R46 대화 언어와 직접적인 답변 | [SKILL.md](../../../skills/work-execution/SKILL.md), [SKILL.md](../../../skills/work-planning/SKILL.md) | 사용자 언어와 상세도에 맞춰 결과부터 설명하고 프로그램/확인 범위를 알려준다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |
| R47 원시 로그와 기억·인용된 평가 구분 | [session-audit.md](../../../skills/kh-maintenance/references/session-audit.md), [session_report.py](../../../src/maintenance/session_report.py) | 원문 위치·인접 event/response 중복·자식 문맥·tool return을 구분한다. 인용·철회·자동 메시지 의미는 원문 순서로 별도 판단한다. [test_maintenance.py](../../../tests/domain/test_maintenance.py) |
| R48 역사 지시를 참고로만 취급하고 특수 규칙 누적 방지 | [SKILL.md](../../../skills/kh-maintenance/SKILL.md), [README.md](../../README.md), [SKILL.md](../../../skills/context-handoff/SKILL.md) | 과거 지시를 현재 승인으로 재사용하지 않으며 기존 감사/계획/역사 문서를 원문 그대로 보존한다. 스킬 지침/호스트 행동; 전체 자동 검증 없음 |

## 시나리오와 다음 실행 범위

[36개 시나리오와 현재 평가 상태](../../../tests/scenarios/cases.json) · [독립 평가 방법](../../../tests/scenarios/README.md) · [기계가 읽는 반영표](2026-09-07-codex-implementation.json)

GitHub 게시 대상은 `main`과 `codex-runtime`이다. 두 브랜치에 같은 3.0.0 패키지를 제공하며 원격 marketplace의 기존 `kh-uaf`/`codex-runtime` 연결은 유지한다. 대화 감사 원문과 기존 임시 파일은 로컬에 보존한다. 게시와 설치 캐시 갱신은 별도이며, 이번 게시 검증은 실제 Codex에서 새 스킬이 로드된다는 증거를 포함하지 않는다.
