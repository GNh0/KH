import ast
from src.skills.base import agent_skill

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
    
    half = max_lines // 2
    head = "\n".join(lines[:half])
    tail = "\n".join(lines[-half:])
    return f"{head}\n\n... [토큰 최적화됨: {len(lines) - max_lines} 줄 생략] ...\n\n{tail}"
