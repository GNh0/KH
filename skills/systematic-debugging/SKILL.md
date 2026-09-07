---
name: systematic-debugging
description: Diagnose an unclear failure by tracing the actual execution path, reproducing its conditions, and testing a focused causal hypothesis.
---

# Systematic debugging

현재 파일·프로시저·연결 대상과 정확한 오류 단계를 먼저 확인한다. 관찰 사실, 가설, 사용자 보고를 구분한다. 예외가 Connect에서 발생했다면 인증·relay 문제를 확인 없이 같은 원인으로 설명하지 않는다.

재현 입력과 실행 경로를 좁힌 후 최소한의 비교로 가설을 검사한다. SQL 실행, 데이터 전송, C# 바인딩과 BestFit 비용은 같은 파라미터·행 수로 나누어 측정한다. 짧은 도구 성공 메시지나 exit code만으로 실제 산출물 정상 여부를 단정하지 않는다.

원인이 명확해지면 해당 범위만 수정하고 실패 조건을 다시 확인한다. 사용자 자체 해결이나 재현 불가 상태는 원인 확정으로 바꾸지 않는다. 변화 없는 검사나 같은 실패 가설을 반복하지 않는다.
