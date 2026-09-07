# PB 추출 / ORCA

정확한 PBL과 사용자 지정 PB 버전, ORCA DLL, bitness, 의존 DLL, 자식 프로세스 PATH, 라이선스를 확인한다. PBL 헤더의 0600만 보고 PB 6이라고 단정하지 않는다. 실행 전 준비 결과는 실행 완료가 아니다.

`src.pb.orca`는 기존 PblScripter 실행 기능을 제공한다. 버전별 실제 도구 경로를 전달한다. export에는 명시적 출력 폴더를 사용하고 사용자 원본을 변경하지 않는다. helper 빌드가 필요한 환경이면 구현상 필요와 사용자의 현재 빌드 지시를 판단한다.

exit code 0이어도 Session open failed, Bad library, SySAM/license 오류나 빈 산출물이면 실패다. PATH 수정으로 한 번 해결됐다고 모든 이후 오류 원인으로 적용하지 않는다. 실제 출력과 대상 export를 확인한다. 추출이 안 되면 제공 export/붙여넣기 소스 범위에서 계속하고 누락된 증거를 명시한다.
# 로컬 도구 사용

`python -m src.pb.orca probe --pbl <absolute-pbl> --version <selected-version>`는 실행 환경만 읽는다. 추출이 필요할 때 `convert`를 사용한다. 정상 x86 helper가 없으면 기본값으로 컴파일하지 않는다. 다른 제공 export로 작업할 수 없고 추출용 helper가 필요한 경우에만 `--compile-helper`를 선택한다. 이것은 실행 옵션이며 별도 승인 서류를 요구하는 절차가 아니다.

종료 코드와 오류 진단, 새로 생성되거나 변경된 비어 있지 않은 PB export를 함께 확인한다. exit 0 + 오류 문구는 실패, 새 산출물 없는 exit 0은 미확인이다. 이 검사도 전체 애플리케이션 동작을 증명하지 않는다. 실제 외부 Export-PBL.ps1을 호출하기 전에는 그 스크립트의 대상 경로와 버전 옵션을 읽는다.
