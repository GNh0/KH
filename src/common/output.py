"""Bounded output with explicit truncation and original exit status."""
from dataclasses import dataclass
from io import TextIOWrapper
import re
import sys


def configure_utf8_streams() -> None:
    """Configure real console/pipe wrappers while leaving injected StringIO streams usable."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding='utf-8')

_ASSIGNMENT = re.compile(r'(?i)(\b(?:password|passwd|pwd|api[_-]?key|access[_-]?token|client[_-]?secret)\b\s*[=:]\s*)(?:"[^"\r\n]*"|\'[^\'\r\n]*\'|[^\s;,]+)')
_TOKENS = re.compile(r'(?i)\bBearer\s+[^\s"\']+|\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}')
_SENSITIVE_KOREAN = re.compile(r'(?i)(비밀번호|패스워드)\s*(?:는|은|가|:|=)?\s*\S+')


def redact(text: str) -> str:
    """Best-effort log masking; never a license to dump credential configuration."""
    text = _ASSIGNMENT.sub(lambda m: m.group(1) + "[REDACTED]", text)
    text = _TOKENS.sub("[REDACTED]", text)
    return _SENSITIVE_KOREAN.sub(lambda m: m.group(1) + " [REDACTED]", text)


@dataclass(frozen=True)
class CommandOutput:
    exit_code: int
    stdout: str
    stderr: str
    omitted_characters: int


def compact_output(stdout: str, stderr: str, exit_code: int, *, limit: int = 12000) -> CommandOutput:
    if limit < 100:
        raise ValueError("limit must leave room for a meaningful failure excerpt")
    original = len(stdout) + len(stderr)
    stdout, stderr = redact(stdout), redact(stderr)
    # stderr gets half the budget even if stdout is noisy. Keep both ends.
    def bounded(value: str, budget: int) -> str:
        if len(value) <= budget:
            return value
        marker = "\n[... output truncated ...]\n"
        side = max(0, (budget - len(marker)) // 2)
        return value[:side] + marker + value[-side:]
    error_budget = min(len(stderr), limit // 2)
    out = bounded(stdout, limit - error_budget)
    err = bounded(stderr, limit - len(out))
    return CommandOutput(exit_code, out, err, max(0, original - len(out) - len(err)))
