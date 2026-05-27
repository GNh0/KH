from typing import Any, Callable, Dict, Optional
import functools

class Skill:
    """
    에이전트가 사용할 수 있는 스킬(도구)의 기본 인터페이스입니다.
    MCP(Model Context Protocol) 및 OpenAI/Claude Function Calling 스펙과 호환되도록 설계되었습니다.
    """
    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self.func = func

    def execute(self, **kwargs) -> Any:
        """스킬의 메인 로직을 실행합니다."""
        try:
            return self.func(**kwargs)
        except Exception as e:
            return f"Skill Execution Error: {str(e)}"

    def to_mcp_format(self) -> Dict[str, Any]:
        """MCP 또는 Function Calling 포맷으로 스킬 스키마를 반환합니다."""
        # 실제 구현에서는 inspect 모듈을 사용하여 파라미터 스키마를 동적으로 추출합니다.
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {}  # 동적 파라미터 파싱 로직 생략 (단순화)
        }

SKILL_REGISTRY = {}

def agent_skill(name: str, description: str):
    """
    일반 파이썬 함수를 에이전트 스킬로 변환하는 데코레이터입니다.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        # 래퍼 객체에 메타데이터 주입
        skill_meta = Skill(name, description, func)
        wrapper.__skill_meta__ = skill_meta
        SKILL_REGISTRY[name] = skill_meta
        return wrapper
    return decorator
