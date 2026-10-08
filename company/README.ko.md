# 회사 개발 플러그인

개인 GitHub 계정·저장소 연결 없이 배포하는 독립 패키지다. ZIP을 사내 공유폴더로 전달하고 직원은 자기 PC에 압축을 풀어 설치한다. 회사 저장소가 정해지면 이 마켓플레이스 루트를 회사 소유 Git 저장소로 옮길 수 있다. SVN은 ZIP/로컬 폴더 배포본의 원본 관리에 사용할 수 있다.

## 포함하는 9개 스킬

| 분류 | 스킬 | 용도 |
| --- | --- | --- |
| 언어·화면 개발 | SQL formatting | SQL 작성·수정·정리와 호출/저장 계약 검토 |
| 언어·화면 개발 | C# and Designer | C# 및 WinForms/Designer 작업, 실제 컨트롤/API/바인딩 확인 |
| 언어·화면 개발 | PowerBuilder | PB/PBL/DataWindow 분석·수정과 필요한 C#/SQL 이관 |
| 공통 개발 | Code review | 실제 변경과 호출부 검토 |
| 공통 개발 | Systematic debugging | 실제 실행 경로에 따른 원인 진단 |
| 작업 관리 | Work planning | 설계 선택·의존성이 있는 큰 작업의 계획 |
| 작업 관리 | Work execution | 승인된 작업 실행과 현재 호스트 도구 사용 |
| 작업 관리 | Context handoff | 긴 작업의 간결한 인계와 재개 |
| 산출물 | Artifact checks | Excel·문서·보고서 등 전달물 검증 |

`KH maintenance`는 직원 배포본에서 제외한다. 플러그인 원본 유지보수 담당자가 별도로 관리한다. 사용자 개인 KH의 이름·폰트·SQL 괄호 정렬·숫자 서식·LINQ/중간 테이블/빌드 비선호는 회사의 필수 규칙으로 복사하지 않는다.

PowerBuilder 스킬에는 export 스크립트와 x86 추출기를 함께 넣었다. 별도의 PblScripter 설치 없이 설치된 PB 7.0·10.5·12.5에서 실제 추출이 되는 런타임을 자동 선택한다. Python 3.11+, Windows PowerShell과 사용 가능한 정식 PB/ORCA 설치가 필요하며, PB의 vendor DLL은 ZIP에 포함하지 않는다. 사용법은 스킬의 `references/tools.md`를 따른다.

공통 `skills/work-execution/references/workspace-files.md` 지침은 빌더가 ZIP에 함께 넣는다. 작업 완료 전 분석용 추출·검증·렌더링 임시 파일을 정리하고, 최종 결과물과 재개에 필요한 증거는 보존한다. 정리 실패나 보관이 필요한 파일은 경로와 이유를 전달한다.

## 직원 설치

1. ZIP을 소스 프로젝트 밖의 고정 폴더(예: `C:\CompanyTools\company-dev`)에 압축 해제한다. 그 폴더에 `.agents`와 `plugins`가 있어야 한다.
2. 지원되는 Codex CLI에서 마켓플레이스를 등록한다.

   ```powershell
   codex plugin marketplace add "C:\CompanyTools\company-dev"
   ```

3. Codex 앱의 플러그인 화면에서 **Company Development** 마켓플레이스의 **Company Development** 플러그인을 설치하고 새 대화에서 확인한다.
4. Python 3.11 이상이 있으면 개인 설정 파일을 한 번 생성한다. Python은 선택적인 검사·설정·PBL 추출 도구에 필요하고, 스킬 문서는 별도로 사용할 수 있다.

   ```powershell
   python -B "C:\CompanyTools\company-dev\plugins\company-dev\scripts\company_style.py" init
   ```

개인 설정 기본 위치는 `%CODEX_HOME%\company-dev-style`이다. `CODEX_HOME`이 없으면 `%USERPROFILE%\.codex\company-dev-style`을 사용한다. `COMPANY_DEV_STYLE_HOME`에 별도 **절대 경로**를 지정하면 그 위치를 사용한다. 생성 명령은 기존 파일을 덮어쓰지 않는다.

## 직원별 커스텀

| 파일 | 직원이 작성할 내용 |
| --- | --- |
| `sql.md` | 대소문자, 들여쓰기, 괄호/JOIN 배치, 별칭, CTE·중간 테이블 선호 |
| `csharp.md` | 코드 형식, 변수·컨트롤·Repository 이름, 숫자 서식, LINQ·빌드 선호 |
| `pb.md` | PowerScript·DataWindow 명명/형식과 분석·이관 선호 |
| `work.md` | 응답 형식, 전달물 형식 등 작업 선호 |

빈 항목은 현재 프로젝트의 승인된 예제를 따른다. 다른 직원의 파일이나 전체 KH 문서를 읽게 하지 않는다. 실제 API·컨트롤 초기화·XML/SP·키·저장 동작은 스타일과 분리해서 확인한다. 회사 필수 규칙은 해당 프로젝트의 `AGENTS.md` 등 회사가 관리하는 지침에 둔다.

스킬은 관련 작업에서 `company_style.py show sql`처럼 **해당 언어의 파일만** 조회하도록 연결돼 있다. 별도 Markdown 파일을 Codex가 자동으로 발견한다고 가정하지 않는다. 개인 스타일을 모델이 읽고 적용하는 방식이며, 임의의 문장으로 작성한 취향 전부를 Python 검사가 자동 강제하는 기능은 아니다.

Python 없이 사용할 때는 개인 파일을 같은 위치에 직접 만들고, 현재 작업에서 해당 파일의 절대 경로를 알려준다.

## 업데이트와 검증

새 배포본은 마켓플레이스 폴더에 교체한다. 개인 설정은 그 폴더 밖에 있으므로 교체 대상에 포함되지 않는다. Codex는 설치된 캐시 복사본을 사용하므로 원본 파일 교체만으로 현재 대화가 바뀌지는 않는다. 앱에서 마켓플레이스 갱신과 플러그인 업데이트를 확인하고, 로컬 배포본 업데이트가 제공되지 않으면 플러그인을 제거 후 다시 설치해 새 대화에서 확인한다. 설치 캐시를 직접 수정하지 않는다.

선택적 검사는 `plugins\company-dev\scripts\company_check.py`를 사용한다. 지원 명령은 `sql`, `csharp`, `designer`, `sp-call`, `pb`, `artifact`, `package`다. 검사 결과의 `checked`, `not_checked`, 경고를 함께 확인한다. 회사용 래퍼는 개인 KH 스타일 검사를 적용하지 않는다. SQL 토큰 비교는 DB 의미 동등성 증명이 아니고 C# 정적 검사는 컴파일·UI 실행이 아니다.

```powershell
python -B "C:\CompanyTools\company-dev\plugins\company-dev\scripts\company_check.py" sql "C:\Temp\before.sql" "C:\Temp\after.sql" --preserve-aliases
python -B "C:\CompanyTools\company-dev\plugins\company-dev\scripts\company_check.py" csharp "C:\Project\Screen.cs" --designer "C:\Project\Screen.Designer.cs"
```

회사명과 저장소 주소가 아직 정해지지 않았으므로 `Company Development`라는 중립 이름을 사용했다. 배포 담당자는 manifest의 표시 이름·작성자를 회사 이름으로 바꿀 수 있다. 개인 GitHub URL이나 Git 이력, 과거 대화·감사 로그, 임시 SQL, 설치 캐시는 포함하지 않는다.

설치 방식의 근거: [공식 플러그인 패키징/로컬 마켓플레이스 문서](https://developers.openai.com/plugins/build/plugins), [프로젝트 AGENTS.md 지침](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## 배포 담당자

현재 KH 개발 원본에서 최초 회사 ZIP을 만드는 명령은 다음과 같다. `company` 폴더는 배포용 템플릿이며, 빌더가 공통 Python 실행 모듈과 UI 메타데이터를 합쳐 완전한 패키지를 만든다.

```powershell
python -B scripts/build_company_bundle.py --output "C:\CompanyTools\releases\company-dev-1.0.2.zip"
```

ZIP에는 실행에 필요한 공통 소스가 함께 들어 있다. 이후 회사 소유 원본으로 복사해 유지보수할 수 있고, 직원 PC에서 원래 KH 저장소를 조회하거나 Git 인증을 할 필요가 없다. 배포 버전은 회사 manifest에서 별도로 관리한다.
