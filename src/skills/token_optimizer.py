import ast
import re
from src.skills.base import agent_skill

IMPORTANT_LOG_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bFAILED\b",
        r"\bERROR\b",
        r"\bFAIL\b",
        r"\bTraceback\b",
        r"\bException\b",
        r"\bAssertionError\b",
        r"\bValueError\b",
        r"\bexit code\s*:\s*\d+",
        r"\breturncode\s*[:=]\s*\d+",
        r"\bline\s+\d+\b",
        r"\b[A-Za-z0-9_./\\-]+\.py::[A-Za-z0-9_./\\:-]+",
    ]
)

@agent_skill(name="minify_code", description="파이썬 코드에서 빈 줄, 주석, Docstring을 제거하여 LLM 컨텍스트 창의 토큰 소모를 극적으로 줄입니다.")
def minify_code(code: str) -> str:
    """AST 파싱을 통해 코드의 기능적 무결성을 유지한 채 주석과 docstring만 제거합니다."""
    try:
        parsed = ast.parse(code)
        
        # Docstring 제거
        for node in ast.walk(parsed):
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef, ast.Module)):
                continue
            if not len(node.body):
                continue
            if not isinstance(node.body[0], ast.Expr):
                continue
            if hasattr(node.body[0], 'value') and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)

        # Python 3.9+ ast.unparse 지원
        if hasattr(ast, 'unparse'):
            return ast.unparse(parsed)
        else:
            return code # 하위 호환성
    except SyntaxError:
        # 문법 에러가 있는 불완전한 코드인 경우 빈 줄만 제거 (Fallback)
        lines = [line for line in code.splitlines() if line.strip()]
        return "\n".join(lines)

@agent_skill(name="truncate_logs", description="엄청나게 긴 터미널 출력이나 에러 로그를 분석에 필요한 헤더와 꼬리 부분만 남기고 압축합니다.")
def truncate_logs(log_text: str, max_lines: int = 30) -> str:
    """Harness(샌드박스)에서 반환된 로그가 너무 길어 토큰을 낭비하는 것을 방지합니다."""
    lines = log_text.splitlines()
    if len(lines) <= max_lines:
        return log_text

    head_count = max(3, max_lines // 4)
    tail_count = max(3, max_lines // 4)
    critical_budget = max(0, max_lines - head_count - tail_count)
    head_indices = set(range(head_count))
    tail_start = max(len(lines) - tail_count, head_count)
    tail_indices = set(range(tail_start, len(lines)))
    critical_indices = _important_line_indices(lines, excluded=head_indices | tail_indices)
    critical_indices = critical_indices[:critical_budget]

    omitted = len(lines) - len(head_indices | tail_indices | set(critical_indices))
    sections = [
        "\n".join(lines[index] for index in sorted(head_indices)),
        f"... [토큰 최적화됨: {omitted} 줄 생략] ...",
    ]
    if critical_indices:
        sections.extend([
            "... [중요 실패 문맥 보존] ...",
            "\n".join(lines[index] for index in critical_indices),
            "... [중간 반복 로그 생략] ...",
        ])
    sections.append("\n".join(lines[index] for index in sorted(tail_indices)))
    return "\n\n".join(section for section in sections if section)


def _important_line_indices(lines: list[str], excluded: set[int]) -> list[int]:
    indices = []
    for index, line in enumerate(lines):
        if index in excluded:
            continue
        if any(pattern.search(line) for pattern in IMPORTANT_LOG_PATTERNS):
            indices.append(index)
    return indices
