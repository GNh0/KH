# KONE 개발 플러그인 공유 안내

공유본 **1.4.1**, 정리 기준 **2026-11-10**. SQL·PowerBuilder·C# 개발에 필요한 공통 기능을 KONE Development로 묶고, 직원 개인 스타일은 설치 폴더 밖에서 관리한다. 개인 GitHub 계정이나 원본 저장소 연결 없이 ZIP과 로컬 마켓플레이스로 배포한다.

## 1. 공유 범위

### 공통으로 배포하는 11개 스킬

| 분류 | 스킬 | 적용하는 작업 |
| --- | --- | --- |
| 개발 | SQL formatting | SQL·프로시저 작성/수정, 실제 호출·키·결과·저장 계약 확인 |
| 개발 | C# and Designer | C#, WinForms/DevExpress, Designer, 보고서와 실제 컨트롤/API/바인딩 확인 |
| 개발 | PowerBuilder | PB/PBL/DataWindow 분석·수정 및 필요한 C#/SQL 이관 |
| 품질 | Code review | 실제 최종 변경과 호출부 검토 |
| 품질 | Rule audit | 적용 규칙 대조, 위반 부분 수정·재감사 및 영향 확인 |
| 품질 | Systematic debugging | 실제 실행 경로와 재현 조건으로 원인 진단 |
| 산출물 | Artifact checks | 문서·Excel·보고서 등 전달물의 내용·구조·표시 결과 확인 |
| 작업 | Work planning | 설계 선택이나 의존성이 있는 작업의 계획 |
| 작업 | Work execution | 승인된 작업의 실행·통합·완료 범위 확인 |
| 작업 | Runtime cleanup | 필요 없어진 작업 소유 프로세스·REPL·연결·임시 자원 정리 |
| 작업 | Context handoff | 진행 상태·검증 범위·남은 작업의 간결한 인계 |

설치된 스킬 11개를 매 요청마다 모두 읽는 방식이 아니다. 관련 작업에 맞는 진입점과 필요한 참고만 읽는다. 계획·디버깅·인계·산출물 검사는 그 역할이 필요한 경우에 적용한다. 코드 작업은 실제 비교 소스 확인과 최종 코드 감사를 거친다.

### 필요한 경우만 사용하는 4개 역할

| 역할 | 맡길 수 있는 범위 |
| --- | --- |
| kone-sql-worker | 독립된 SQL/프로시저 작업 |
| kone-csharp-worker | 독립된 C#/Designer/보고서 작업 |
| kone-pb-worker | 독립된 PB 분석·이관 작업 |
| kone-rule-auditor | 실제 변경의 독립 감사 |

기본은 메인 에이전트가 구현과 통합을 처리하는 것이다. 전문 처리를 분리하거나 독립 검토할 이점이 있을 때만 역할을 사용한다. 모든 작업을 서브에이전트로 돌리지 않는다. 특정 모델·추론 수준은 공통 패키지에 고정하지 않고 현재 사용자 선택과 호스트 정책을 따른다.

역할 파일은 실행 가능한 에이전트 프로그램이 아니라 호스트 서브에이전트에 전달할 지침이다. Codex의 네이티브 에이전트 유형을 자동 등록한다고 가정하지 않는다. 메인은 실제 도구가 허용하는 방식으로 역할 파일과 작업 근거를 전달한다. 도구가 없으면 메인이 해당 소스 대조·감사를 수행한다. 사용 방식은 `plugins/kone-dev/skills/work-execution/references/delegation.md`에 있다.

### 공유본에 넣지 않는 내용

- 개인 원본 플러그인의 유지보수·게시 전용 스킬
- 개인 GitHub 주소·인증·Git 이력·과거 채팅/감사 로그
- 개인의 고정 폰트·컨트롤 이름·SQL 별칭/정렬·숫자 서식·LINQ/빌드 취향
- 회사/고객의 실제 업무 소스·DB 접속정보·MCP 자격증명
- 개발 중 임시 SQL·추출물·프로브·설치 캐시

## 2. 공통 규칙과 개인 스타일의 경계

| 위치 | 관리하는 내용 |
| --- | --- |
| 회사/프로젝트의 AGENTS.md 등 | 회사가 정한 필수 규칙, 허용 작업 범위, 승인된 프로젝트 기준 |
| 공유 플러그인 | 실제 소스·계약 확인, 변경 범위 보존, 검토·재감사, 임시 자원 정리 |
| 직원의 개인 스타일 파일 | SQL/C#/PB 형식, 이름, 선호/피할 패턴, 승인된 예시 위치, 작업 전달 선호 |
| 실제 프로젝트 소스·스키마 | API, 컨트롤 초기화, 키, 타입, 단위, XML/SP, 저장과 조회의 실제 동작 |

직원 스타일로 데이터 의미나 회사의 필수 규칙을 임의로 바꾸지 않는다. 개인 스타일이 비어 있으면 승인된 프로젝트 예제를 따른다. 다른 직원의 설정을 찾아 읽거나 원본 작성자의 취향을 회사 기본값으로 적용하지 않는다.

컨트롤 기본값은 실제 프로젝트의 라이브러리·공통 초기화·화면을 따라 확인한다. 특정 회사와 무관한 고정 크기·정렬·폰트 값을 이 패키지가 강제하지 않는다.

## 3. 직원 설치

현재 ZIP은 **Codex용 로컬 마켓플레이스**다. 회사 저장소/서버나 개인 GitHub 연결은 필요 없다.

1. 소스 프로젝트 밖의 고정 폴더, 예를 들어 `C:\CompanyTools\kone-dev`에 압축을 푼다. 그 폴더 바로 아래에 `.agents`, `plugins`, `README.ko.md`가 있어야 한다.
2. 지원되는 Codex CLI에서 로컬 마켓플레이스를 등록한다.

   ```powershell
   codex plugin marketplace add "C:\CompanyTools\kone-dev"
   ```

3. 앱을 다시 시작하고 플러그인 화면에서 KONE Development 마켓플레이스의 kone-dev 플러그인을 설치한다. 새 대화에서 스킬이 보이는지 확인한다.
4. Python 3.11 이상이 있으면 개인 스타일의 빈 항목을 생성한다.

   ```powershell
   python -B "C:\CompanyTools\kone-dev\plugins\kone-dev\scripts\kone_style.py" init
   ```

생성 명령은 기존 개인 파일을 덮어쓰지 않는다. Python은 선택적 검사·개인 설정 도구·PBL 추출에 필요하고, 스킬 문서는 별도로 읽을 수 있다.

## 4. 직원별 커스텀

기본 위치는 `%CODEX_HOME%\kone-dev-style`이며, CODEX_HOME이 없으면 `%USERPROFILE%\.codex\kone-dev-style`이다. `KONE_DEV_STYLE_HOME`에 별도 절대 경로를 지정할 수도 있다. 개인 파일은 플러그인/설치 폴더 밖에 둔다.

이전 company-dev 공유본의 `COMPANY_DEV_STYLE_HOME`도 호환한다. 새 기본 폴더가 없고 기존 `company-dev-style` 폴더가 있으면 기존 폴더를 계속 사용하며 파일을 이동하거나 덮어쓰지 않는다. 경로 선택 순서는 명시한 `--directory`, `KONE_DEV_STYLE_HOME`, 이전 환경변수, 기본 폴더다.

| 파일 | 직원이 설정할 내용 |
| --- | --- |
| sql.md | 대소문자, 들여쓰기·괄호·JOIN 배치, 별칭, CTE·서브쿼리·중간 테이블 선호 |
| csharp.md | 코드 형식, 변수·컨트롤·Repository 이름, 숫자 서식, LINQ·빌드 선호 |
| pb.md | PowerScript·DataWindow 이름/형식, PB 분석·이관 선호 |
| work.md | 응답 언어·길이, 전달물 형식, 전문 작업·독립 검토 선호 |

각 언어 파일에 선호하는 형태, 피할 패턴, 기준 소스의 경로/메서드/분기, 필요한 예외를 함께 적을 수 있다. 설명용 코드가 필요하면 가상 예시로 작성한다. 실제 업무 코드는 플러그인에 복사하지 않고 작업 중 승인된 소스를 직접 참고한다.

스킬은 필요한 언어의 파일만 `kone_style.py show sql` 같은 명령으로 읽는다. 새 Markdown 파일을 호스트가 자동 발견한다고 가정하지 않는다. 같은 작업에서는 이미 읽은 설정을 재사용하고 변경된 경우에 다시 읽는다.

Python이 없으면 개인 파일을 직접 만들고 작업에서 해당 파일의 절대 경로를 알려준다. 개인 취향을 바꾸기 위해 공유 스킬 파일을 직접 수정하지 않는다.

## 5. 검증과 감사

회사용 검사 도구는 `plugins/kone-dev/scripts/kone_check.py`다. 지원 명령은 sql, csharp, designer, sp-call, pb, artifact, package다. 개인 원본 작성자의 스타일 검사를 끄고 실제 소스/계약 검사에 사용한다.

```powershell
python -B "C:\CompanyTools\kone-dev\plugins\kone-dev\scripts\kone_check.py" sql "C:\Temp\before.sql" "C:\Temp\after.sql" --preserve-aliases
python -B "C:\CompanyTools\kone-dev\plugins\kone-dev\scripts\kone_check.py" csharp "C:\Project\Screen.cs" --designer "C:\Project\Screen.Designer.cs"
```

- 작성 전에는 실제 비교 프로그램과 대상 계약을 확인한다.
- 작성 후에는 실제 최종 파일을 개인 스타일·프로젝트 기준·요구사항과 대조한다.
- 확인된 위반 부분을 수정하고 영향을 받은 범위를 재감사한다. 독립 감사를 선택했으면 해당 수정도 독립 재검토한다.
- 마지막에는 수정 때문에 관련 호출·컨트롤·데이터 흐름에 회귀가 생겼는지 확인한다.

검사 결과의 checked, not_checked, 경고와 review_status를 함께 읽는다. status가 passed라도 needs_review나 미검증 범위가 남으면 전체 감사 완료로 해석하지 않는다. 개인의 자유 형식 스타일 문장 전부를 검사기가 자동 판단하는 것은 아니며, 이 패키지에 감사 자동 실행·완료 차단 훅은 없다.

SQL 토큰 비교는 DB 의미 동등성/배포의 증명이 아니다. C# 정적 검사는 컴파일·Designer/UI 실행의 증명이 아니다. 수행하지 못한 범위는 미검증으로 남긴다.

## 6. PB 추출과 자원 정리

PB 스킬에는 export 스크립트와 x86 추출기를 함께 넣었다. 별도 PblScripter 설치 없이 사용 가능한 설치 PB/ORCA 런타임을 선택한다. Python 3.11+, Windows PowerShell과 호환되는 정식 PB/ORCA 설치가 필요하다. vendor DLL이나 PB 라이선스는 제공하지 않는다. 상세 조건은 스킬의 references/tools.md를 따른다.

작업용 추출·검사·렌더링 임시 파일은 소스 밖에서 만들고 사용이 끝나면 정리한다. 최종 전달물과 재개에 필요한 증거는 보존한다. Windows 실행기는 새로 시작한 작업 소유 명령 트리의 종료를 검증하지만, 기존 공유 MCP 서버나 앱 내부 캐시를 임의로 종료하지 않는다.

## 7. 배포와 업데이트

당장은 ZIP을 사내 공유폴더 등으로 전달한다. 직원은 같은 로컬 마켓플레이스 폴더를 새 배포본으로 교체한다. 개인 설정 파일은 그 폴더 밖에 있으므로 교체하지 않는다.

1.4.0의 company-dev와 1.4.1의 kone-dev는 플러그인 식별자가 다르다. 이전 공유본을 설치했다면 KONE Development 마켓플레이스를 등록하고 kone-dev를 설치한 뒤 이전 company-dev를 비활성화해 중복 적용을 피한다. 기존 개인 스타일은 위 호환 경로로 보존한다.

앱은 설치 캐시 복사본을 사용한다. 원본 폴더를 바꾼 뒤 마켓플레이스 갱신·플러그인 업데이트를 확인하고 새 대화에서 적용을 확인한다. 클라이언트가 갱신을 제공하지 않으면 공식 설치 경로로 재설치한다. 설치 캐시를 직접 편집하지 않는다.

회사 소유 저장소가 정해지면 이 마켓플레이스 루트를 그 저장소로 옮길 수 있다. SVN은 배포 원본 관리에 사용할 수 있다. 직원에게 개인 원본 GitHub 연결을 요구하지 않는다.

공식 근거: [로컬 마켓플레이스와 플러그인 패키징](https://developers.openai.com/plugins/build/plugins).

## 8. 유지보수 담당자

company 폴더는 배포 템플릿이다. 빌더가 공통 Python 모듈, source-style-cycle, rule-audit, runtime-cleanup, 보고서 참고와 PB 추출 도구를 합쳐 완전한 패키지를 만든다.

```powershell
python -B scripts/build_company_bundle.py --output "C:\CompanyTools\releases\kone-dev-1.4.1.zip"
```

Git 추적 목록의 파일만 수집하며 내용은 현재 작업 트리에서 읽는다. 새 배포 파일은 검토 후 추적 목록에 추가해야 한다. Git 목록을 확인할 수 없으면 폴더 전체 수집으로 우회하지 않고 실패한다. 이 Git 요구는 유지보수 담당자의 빌드에만 적용되고, 직원 PC에서는 원래 저장소 조회나 Git 인증이 필요 없다.

패키지 버전은 KONE manifest에서 별도로 관리한다. ZIP 검증과 직원 PC의 실제 앱 설치/스킬 선택 검증은 구분한다.
