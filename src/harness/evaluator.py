from src.contracts import HarnessResult
from src.harness.sandbox import CodeSandbox


class Evaluator:
    """Run agent code plus tests through the local sandbox and normalize feedback."""

    def __init__(self, timeout: int = 10):
        self.sandbox = CodeSandbox(timeout=timeout)

    def evaluate_code(self, agent_code: str, test_code: str) -> dict:
        """Combine agent code and verification code, run them, and return a compact result."""
        combined_code = f"{agent_code}\n\n# --- Test Code ---\n{test_code}"
        result = self.sandbox.run_python_code(combined_code)

        feedback = {
            "passed": result["success"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "execution_time": result["execution_time"],
        }

        if result["success"]:
            feedback["message"] = "[SUCCESS] All tests passed."
        else:
            feedback["message"] = "[FAIL] Tests failed. Inspect stderr and fix the code."

        return feedback

    def evaluate_code_result(self, agent_code: str, test_code: str) -> HarnessResult:
        """Evaluate code and return the standard UAF HarnessResult contract."""
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
    evaluator = Evaluator()

    agent_code = """
def add(a, b):
    return a + b
"""

    test_code_pass = """
assert add(2, 3) == 5, "2+3 should equal 5"
print("test passed")
"""

    test_code_fail = """
assert add(2, 3) == 6, "2+3 should equal 6"
"""

    print("--- 1. Passing scenario ---")
    print(evaluator.evaluate_code(agent_code, test_code_pass))

    print("\n--- 2. Failing scenario ---")
    print(evaluator.evaluate_code(agent_code, test_code_fail))
