from src.contracts import HarnessResult
from src.harness.sandbox import CodeSandbox

class Evaluator:
    """
    에이전트가 작성한 코드와 테스트 코드를 결합하여 평가 하네스(Sandbox)에서 실행하고,
    테스트 통과 여부를 판단하는 모듈입니다.
    """
    def __init__(self, timeout: int = 10):
        self.sandbox = CodeSandbox(timeout=timeout)

    def evaluate_code(self, agent_code: str, test_code: str) -> dict:
        """
        에이전트의 코드와 검증용 테스트 코드를 결합하여 샌드박스에서 실행합니다.
        
        Args:
            agent_code (str): 에이전트가 작성한 메인 로직
            test_code (str): 메인 로직을 검증할 assert문 혹은 pytest 스크립트
            
        Returns:
            dict: 실행 결과 및 피드백 메시지
        """
        # 에이전트 코드와 테스트 코드를 하나의 스크립트로 결합
        # 실제 고도화된 하네스에서는 별도의 파일로 분리하고 pytest를 호출할 수도 있습니다.
        combined_code = f"{agent_code}\n\n# --- Test Code ---\n{test_code}"
        
        result = self.sandbox.run_python_code(combined_code)
        
        # 평가 결과 포맷팅 (에이전트가 이해하기 쉬운 형태로 가공)
        feedback = {
            "passed": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "execution_time": result["execution_time"]
        }
        
        if result["success"]:
            feedback["message"] = "[SUCCESS] 모든 테스트를 성공적으로 통과했습니다!"
        else:
            feedback["message"] = "[FAIL] 테스트 실패. 제공된 에러 메시지(stderr)를 분석하여 코드를 수정하세요."
            
        return feedback

    def evaluate_code_result(self, agent_code: str, test_code: str) -> HarnessResult:
        """
        Evaluate code and return the standard UAF HarnessResult contract.
        """
        feedback = self.evaluate_code(agent_code, test_code)
        return HarnessResult(
            success=bool(feedback["passed"]),
            stdout=feedback["stdout"],
            stderr=feedback["stderr"],
            exit_code=0 if feedback["passed"] else 1,
            execution_time=float(feedback["execution_time"]),
            metadata={
                "message": feedback["message"],
                "passed": bool(feedback["passed"]),
                "harness": "Evaluator.evaluate_code_result",
            },
        )

if __name__ == "__main__":
    # 자체 테스트
    evaluator = Evaluator()
    
    agent_code = """
def add(a, b):
    return a + b
"""
    
    test_code_pass = """
assert add(2, 3) == 5, "2+3은 5여야 합니다."
print("덧셈 테스트 통과")
"""

    test_code_fail = """
assert add(2, 3) == 6, "2+3은 6이어야 합니다."
"""

    print("--- 1. 테스트 통과 시나리오 ---")
    print(evaluator.evaluate_code(agent_code, test_code_pass))
    
    print("\n--- 2. 테스트 실패 시나리오 ---")
    print(evaluator.evaluate_code(agent_code, test_code_fail))
