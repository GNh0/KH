import functools
from typing import Any, Callable, Dict


class Skill:
    """Basic callable skill wrapper compatible with MCP-style tool metadata."""

    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self.func = func

    def execute(self, **kwargs) -> Any:
        """Execute the wrapped skill function."""
        try:
            return self.func(**kwargs)
        except Exception as exc:
            return f"Skill Execution Error: {exc}"

    def to_mcp_format(self) -> Dict[str, Any]:
        """Return a minimal MCP/function-calling compatible schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {},
        }


SKILL_REGISTRY = {}


def agent_skill(name: str, description: str):
    """Register a normal Python function as a built-in UAF skill."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        skill_meta = Skill(name, description, func)
        wrapper.__skill_meta__ = skill_meta
        SKILL_REGISTRY[name] = skill_meta
        return wrapper

    return decorator
