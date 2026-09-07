# KH 개발 검사

실행 검사기는 Python 3.11 이상 표준 라이브러리만 사용한다. 스킬 지침은 Markdown이다. 타입 검사 도구는 개발 단계에만 필요하다.

저장소 루트에서 실행한다.

```powershell
python -B -m unittest discover -s tests/domain
npx --yes pyright@1.1.413 --project pyrightconfig.json
python -B scripts/kh_check.py package <absolute-plugin-root>
```

Pyright 범위는 `src`, `scripts`, PB 스킬의 실행 스크립트 전체다. `standard` 모드에 더해 C#/PB lexer와 측정 입력 검증 모듈에는 `strict`를 적용한다. 검사 오류를 없애려고 전체 규칙을 끄거나 외부 입력을 `Any`로 단정하지 않는다. GitHub의 `KH checks` 작업은 Windows/Python 3.11·3.14 단위 검사와 타입·패키지 검사를 수행한다. 설정 존재와 실제 작업 통과는 구분한다.

정적 타입 검사는 함수 계약의 모순을 찾는 데 쓰고, JSON 등 외부 입력은 실행 시 별도로 검증한다. [Python 타입 주석은 실행 시 자동 강제되지 않으며](https://docs.python.org/3/library/typing.html), [TypeScript 타입 주석도 출력 코드에서 지워진다](https://www.typescriptlang.org/docs/handbook/2/basic-types.html). 파서의 잘못된 가정, 오탐·누락, 업무 의미는 언어 전환만으로 해결되지 않는다. 새 반례는 원본/대상 자료와 기대 동작을 보존하고 실제 실패를 확인한 후 고친다.

타입 검사 0건, 단위 검사 통과는 C# 컴파일·Designer 실행·PB/ORCA 실환경·SQL Server 결과를 대신하지 않는다. 독립적인 사용 평가는 필요한 최소 원본과 작업 요청으로 수행하고, 구현자의 정답을 평가자에게 전달하지 않는다.
