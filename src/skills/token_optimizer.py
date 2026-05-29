import argparse
import ast
import re
import sys
from typing import Any, Dict, Tuple

from src.contracts import HarnessResult
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
        r"\bBuild FAILED\b",
        r"\berror\s+[A-Z]{2,}\d+\b",
        r"\bassert\b.*\b==\b",
        r"^\s*E\s+[-+]\s+",
        r"\b(expected|actual)\s*:",
        r"\b\d+\s*==\s*\d+\b",
        r"\bexit code\s*:\s*\d+",
        r"\breturncode\s*[:=]\s*\d+",
        r"\bline\s+\d+\b",
        r"\b[A-Za-z0-9_./\\-]+\.py::[A-Za-z0-9_./\\:-]+",
        r"\b(USER_CONSTRAINT|DECISION|EVIDENCE|BLOCKER|P[0-2])\b",
    ]
)


@agent_skill(
    name="minify_code",
    description="Remove comments and Python docstrings to reduce LLM context size while preserving executable logic.",
)
def minify_code(code: str) -> str:
    """Remove Python comments and docstrings while preserving syntax when possible."""
    if is_contract_sensitive_text(code):
        return code
    try:
        parsed = ast.parse(code)

        # Remove module, class, function, and async-function docstrings.
        for node in ast.walk(parsed):
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef, ast.Module)):
                continue
            if not node.body:
                continue
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
                if isinstance(first.value.value, str):
                    node.body.pop(0)

        if hasattr(ast, "unparse"):
            return ast.unparse(parsed)
        return code
    except SyntaxError:
        lines = [line for line in code.splitlines() if line.strip()]
        return "\n".join(lines)


@agent_skill(
    name="optimize_context_content",
    description="Optimize context only when quality-preserving compression is safe; otherwise return passthrough content.",
)
def optimize_context_content(
    content: str,
    content_kind: str = "auto",
    command: str = "",
    exit_code: int = 0,
    max_lines: int = 30,
) -> HarnessResult:
    """Quality-first entrypoint for logs, Python code, and contract-sensitive text."""
    detected_kind = _detect_content_kind(content, content_kind, command)
    if detected_kind == "contract-sensitive":
        return HarnessResult(
            success=exit_code == 0,
            stdout=content,
            stderr="",
            exit_code=exit_code,
            metadata={
                "strategy": "passthrough",
                "content_kind": detected_kind,
                "passthrough_reason": "contract-sensitive content must preserve original text",
                "raw_bytes": len(content.encode("utf-8")),
                "filtered_bytes": len(content.encode("utf-8")),
                "token_savings_ratio": 0.0,
                "token_usage": compare_token_usage(
                    content,
                    content,
                    strategy="passthrough",
                    label="contract-sensitive",
                ),
            },
        )
    if detected_kind == "python-code":
        minified = minify_code(content)
        return HarnessResult(
            success=exit_code == 0,
            stdout=minified,
            stderr="",
            exit_code=exit_code,
            metadata={
                "strategy": "minify-code" if minified != content else "passthrough",
                "content_kind": detected_kind,
                "passthrough_reason": "contract-sensitive Python comments detected" if minified == content else "",
                "raw_bytes": len(content.encode("utf-8")),
                "filtered_bytes": len(minified.encode("utf-8")),
                "token_savings_ratio": _savings_ratio(len(content.encode("utf-8")), len(minified.encode("utf-8"))),
                "token_usage": compare_token_usage(
                    content,
                    minified,
                    strategy="minify-code" if minified != content else "passthrough",
                    label="python-code",
                ),
            },
        )
    if detected_kind == "log":
        result = summarize_command_output(
            command=command,
            stdout=content,
            stderr="",
            exit_code=exit_code,
            max_lines=max_lines,
        )
        metadata = dict(result.metadata)
        metadata["strategy"] = "command-output"
        metadata["content_kind"] = detected_kind
        return HarnessResult(
            success=result.success,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            execution_time=result.execution_time,
            metadata=metadata,
        )
    return HarnessResult(
        success=exit_code == 0,
        stdout=content,
        stderr="",
        exit_code=exit_code,
        metadata={
            "strategy": "passthrough",
            "content_kind": detected_kind,
            "passthrough_reason": "content kind is not safe to compress automatically",
            "raw_bytes": len(content.encode("utf-8")),
            "filtered_bytes": len(content.encode("utf-8")),
            "token_savings_ratio": 0.0,
            "token_usage": compare_token_usage(
                content,
                content,
                strategy="passthrough",
                label="text",
            ),
        },
    )


@agent_skill(
    name="truncate_logs",
    description="Compress long terminal output while preserving headers, tails, exit status, and failure context.",
)
def truncate_logs(log_text: str, max_lines: int = 30) -> str:
    """Compress logs for agent context while keeping actionable failure lines."""
    lines = log_text.splitlines()
    if len(lines) <= max_lines:
        return log_text

    if max_lines <= 0:
        return ""

    head_count = max(3, max_lines // 4)
    tail_count = max(3, max_lines // 4)
    critical_budget = max(0, max_lines - head_count - tail_count)
    head_indices = set(range(min(head_count, len(lines))))
    tail_start = max(len(lines) - tail_count, len(head_indices))
    tail_indices = set(range(tail_start, len(lines)))
    ordered_important = _important_line_indices(lines, excluded=head_indices | tail_indices)
    required_indices = [index for index in ordered_important if _line_priority(lines[index]) >= 70]
    optional_indices = [index for index in ordered_important if _line_priority(lines[index]) < 70]
    remaining_budget = max(0, critical_budget - len(required_indices))
    critical_indices = required_indices + optional_indices[:remaining_budget]

    kept = head_indices | tail_indices | set(critical_indices)
    omitted = len(lines) - len(kept)
    sections = [
        "\n".join(lines[index] for index in sorted(head_indices)),
        f"... [token optimized: {omitted} lines omitted] ...",
    ]
    if critical_indices:
        sections.extend([
            "... [important failure context kept] ...",
            "\n".join(lines[index] for index in critical_indices),
            "... [middle repeated output omitted] ...",
        ])
    sections.append("\n".join(lines[index] for index in sorted(tail_indices)))
    return "\n\n".join(section for section in sections if section)


@agent_skill(
    name="summarize_command_output",
    description="Return a HarnessResult with filtered command output, preserved exit code, and token savings metadata.",
)
def summarize_command_output(
    command: str,
    stdout: str = "",
    stderr: str = "",
    exit_code: int = 0,
    max_lines: int = 30,
    execution_time: float = 0.0,
) -> HarnessResult:
    command_family = _command_family(command)
    filtered_stdout, stdout_fallback = _safe_filter_channel(stdout, max_lines, exit_code, command_family)
    filtered_stderr, stderr_fallback = _safe_filter_channel(stderr, max_lines, exit_code, command_family)
    raw_bytes = len(stdout.encode("utf-8")) + len(stderr.encode("utf-8"))
    filtered_bytes = len(filtered_stdout.encode("utf-8")) + len(filtered_stderr.encode("utf-8"))
    fallback_reason = stdout_fallback or stderr_fallback

    metadata: Dict[str, Any] = {
        "command": command,
        "command_family": command_family,
        "raw_bytes": raw_bytes,
        "filtered_bytes": filtered_bytes,
        "raw_lines": len(stdout.splitlines()) + len(stderr.splitlines()),
        "filtered_lines": len(filtered_stdout.splitlines()) + len(filtered_stderr.splitlines()),
        "token_savings_ratio": _savings_ratio(raw_bytes, filtered_bytes),
        "fallback_reason": fallback_reason,
        "output_filter": "command_family" if command_family != "generic" else "truncate_logs",
    }
    metadata["token_usage"] = compare_token_usage(
        _join_channels(stdout, stderr),
        _join_channels(filtered_stdout, filtered_stderr),
        strategy="command-output" if command_family != "generic" else "truncate_logs",
        label=command or command_family,
    )

    return HarnessResult(
        success=exit_code == 0,
        stdout=filtered_stdout,
        stderr=filtered_stderr,
        exit_code=exit_code,
        execution_time=execution_time,
        metadata=metadata,
    )


@agent_skill(
    name="compare_token_usage",
    description="Estimate token use before and after token optimization for reporting savings.",
)
def compare_token_usage(
    raw_text: str,
    optimized_text: str,
    strategy: str = "unknown",
    label: str = "",
) -> Dict[str, Any]:
    without_optimizer = estimate_token_count(raw_text)
    with_optimizer = estimate_token_count(optimized_text)
    saved = max(0, without_optimizer - with_optimizer)
    return {
        "label": label,
        "strategy": strategy,
        "without_token_optimizer": without_optimizer,
        "with_token_optimizer": with_optimizer,
        "estimated_tokens_saved": saved,
        "token_savings_ratio": _savings_ratio(without_optimizer, with_optimizer),
    }


@agent_skill(
    name="aggregate_token_usage_stats",
    description="Aggregate token optimizer before/after records into workflow-level savings statistics.",
)
def aggregate_token_usage_stats(records: list[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = [_token_usage_record(record) for record in records if record]
    without_optimizer = sum(record["without_token_optimizer"] for record in normalized)
    with_optimizer = sum(record["with_token_optimizer"] for record in normalized)
    saved = max(0, without_optimizer - with_optimizer)
    by_strategy: Dict[str, Dict[str, Any]] = {}
    for record in normalized:
        strategy = record["strategy"] or "unknown"
        bucket = by_strategy.setdefault(
            strategy,
            {
                "case_count": 0,
                "without_token_optimizer": 0,
                "with_token_optimizer": 0,
                "estimated_tokens_saved": 0,
                "token_savings_ratio": 0.0,
            },
        )
        bucket["case_count"] += 1
        bucket["without_token_optimizer"] += record["without_token_optimizer"]
        bucket["with_token_optimizer"] += record["with_token_optimizer"]
        bucket["estimated_tokens_saved"] += record["estimated_tokens_saved"]
    for bucket in by_strategy.values():
        bucket["token_savings_ratio"] = _savings_ratio(
            bucket["without_token_optimizer"],
            bucket["with_token_optimizer"],
        )
    return {
        "case_count": len(normalized),
        "without_token_optimizer": without_optimizer,
        "with_token_optimizer": with_optimizer,
        "estimated_tokens_saved": saved,
        "token_savings_ratio": _savings_ratio(without_optimizer, with_optimizer),
        "by_strategy": by_strategy,
    }


@agent_skill(
    name="estimate_token_count",
    description="Return a deterministic approximate token count for local savings reports.",
)
def estimate_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _important_line_indices(lines: list[str], excluded: set[int]) -> list[int]:
    weighted = []
    for index, line in enumerate(lines):
        if index in excluded:
            continue
        priority = _line_priority(line)
        if priority > 0:
            weighted.append((-priority, index))
    return [index for _, index in sorted(weighted)]


def _safe_filter_channel(text: str, max_lines: int, exit_code: int, command_family: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    filtered = filter_command_output(text, max_lines=max_lines, command_family=command_family, exit_code=exit_code)
    if exit_code != 0 and not filtered.strip():
        return text, "filtered output was empty for failing command"
    missing = _missing_required_facts(text, filtered, command_family, exit_code)
    if missing:
        filtered = _append_missing_facts(filtered, missing)
        return filtered, "required facts were appended after preservation check"
    return filtered, ""


@agent_skill(
    name="filter_command_output",
    description="Apply command-family-specific filtering before falling back to generic log truncation.",
)
def filter_command_output(
    text: str,
    max_lines: int = 30,
    command_family: str = "generic",
    exit_code: int = 0,
) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    if command_family == "generic":
        return truncate_logs(text, max_lines=max_lines)

    important = _family_important_line_indices(lines, command_family)
    if not important:
        return truncate_logs(text, max_lines=max_lines)

    budget = max(1, max_lines - 2)
    selected = sorted(important[:budget])
    omitted = len(lines) - len(selected)
    output = [f"... [command-output optimized: {omitted} lines omitted; family={command_family}] ..."]
    output.extend(lines[index] for index in selected)
    return "\n".join(output)


@agent_skill(
    name="is_contract_sensitive_text",
    description="Detect text that should not be minified because exact wording, comments, or order matter.",
)
def is_contract_sensitive_text(text: str) -> bool:
    lowered = (text or "").lower()
    contract_markers = [
        "create procedure",
        "alter procedure",
        "insert into",
        "select ",
        "where ",
        " join ",
        "copyright",
        "license",
        "security:",
        "security ",
        "security review",
        "type: ignore",
        "noqa",
        "pylint:",
        "pragma:",
        "important",
        "warning",
        "compatibility",
        "coding:",
        "#!",
        "do not remove",
        "business rule",
        "business contract",
        "contract:",
        "contract ",
    ]
    return any(marker in lowered for marker in contract_markers)


def _command_family(command: str) -> str:
    lowered = (command or "").lower()
    if any(token in lowered for token in [
        "pytest",
        "unittest",
        "npm test",
        "cargo test",
        "go test",
        "dotnet test",
        "mvn test",
        "gradle test",
        "jest",
        "vitest",
    ]):
        return "test"
    if any(token in lowered for token in [
        "msbuild",
        "dotnet build",
        "npm run build",
        "cargo build",
        "go build",
        "mvn package",
        "gradle build",
        "tsc",
        "build ",
    ]):
        return "build"
    if any(token in lowered for token in ["git status", "git diff", "git show"]):
        return "git-read"
    if any(token in lowered for token in ["pip install", "npm install", "pnpm install", "yarn install"]):
        return "dependency"
    if any(token in lowered for token in ["python -m", "python "]):
        return "python"
    return "generic"


def _detect_content_kind(content: str, content_kind: str, command: str) -> str:
    explicit = (content_kind or "auto").lower()
    if explicit in {"log", "python-code", "contract-sensitive", "text"}:
        return explicit
    if is_contract_sensitive_text(content):
        return "contract-sensitive"
    if command or any(marker in content for marker in ["Traceback", "FAILED", "ERROR", "Build FAILED", "exit code:", "returncode="]):
        return "log"
    try:
        ast.parse(content)
        return "python-code"
    except SyntaxError:
        return "text"


def _savings_ratio(raw_bytes: int, filtered_bytes: int) -> float:
    if raw_bytes <= 0:
        return 0.0
    saved = max(0, raw_bytes - filtered_bytes)
    return round(saved / raw_bytes, 4)


def _join_channels(stdout: str, stderr: str) -> str:
    if stdout and stderr:
        return f"{stdout}\n{stderr}"
    return stdout or stderr


def _token_usage_record(record: Dict[str, Any]) -> Dict[str, Any]:
    token_usage = record.get("token_usage") if isinstance(record.get("token_usage"), dict) else record
    without_optimizer = int(token_usage.get("without_token_optimizer", 0))
    with_optimizer = int(token_usage.get("with_token_optimizer", 0))
    saved = max(0, without_optimizer - with_optimizer)
    return {
        "label": str(token_usage.get("label", "")),
        "strategy": str(token_usage.get("strategy", "")),
        "without_token_optimizer": without_optimizer,
        "with_token_optimizer": with_optimizer,
        "estimated_tokens_saved": int(token_usage.get("estimated_tokens_saved", saved)),
        "token_savings_ratio": float(token_usage.get("token_savings_ratio", _savings_ratio(without_optimizer, with_optimizer))),
    }


def _line_priority(line: str) -> int:
    lowered = line.lower()
    if " passed" in lowered and "failed" not in lowered and "error" not in lowered:
        return 0
    if re.search(r"\b(failed|error|exception|assertionerror|valueerror|build failed)\b", lowered):
        return 100
    if re.search(r"\berror\s+[a-z]{2,}\d+\b", lowered):
        return 95
    if re.search(r"^\s*e\s+[-+]\s+|\b(expected|actual)\s*:", lowered):
        return 92
    if re.search(r"\bassert\b.*\b==\b|\b\d+\s*==\s*\d+\b", lowered):
        return 90
    if re.search(r"\b(exit code|returncode)\s*[:=]\s*\d+\b", lowered):
        return 85
    if re.search(r"\btraceback\b", lowered):
        return 80
    if re.search(r"\b(user_constraint|decision|evidence|blocker|p[0-2])\b", lowered):
        return 75
    if re.search(r"\bline\s+\d+\b|:\d+:\d+|\(\d+,\d+\)", lowered):
        return 70
    if any(pattern.search(line) for pattern in IMPORTANT_LOG_PATTERNS):
        return 50
    return 0


def _family_important_line_indices(lines: list[str], command_family: str) -> list[int]:
    weighted = []
    for index, line in enumerate(lines):
        priority = _line_priority(line)
        lowered = line.lower()
        if command_family == "test":
            if " passed" in lowered and "failed" not in lowered:
                priority = 0
            if ".py::" in line and any(term in lowered for term in ["failed", "error"]):
                priority = max(priority, 100)
        elif command_family == "build":
            if "error " in lowered or "build failed" in lowered:
                priority = max(priority, 100)
        elif command_family == "git-read":
            if any(term in lowered for term in ["modified:", "deleted:", "renamed:", "diff --git", "+++", "---"]):
                priority = max(priority, 80)
        if priority > 0:
            weighted.append((-priority, index))
    return [index for _, index in sorted(weighted)]


def _missing_required_facts(raw: str, filtered: str, command_family: str, exit_code: int) -> list[str]:
    if exit_code == 0:
        return []
    required_lines = []
    raw_lines = raw.splitlines()
    for index in _family_important_line_indices(raw_lines, command_family):
        line = raw_lines[index]
        if _line_priority(line) >= 70:
            required_lines.append(line)
    if not required_lines and command_family == "generic":
        for index in _important_line_indices(raw_lines, excluded=set()):
            line = raw_lines[index]
            if _line_priority(line) >= 70:
                required_lines.append(line)
    return [line for line in required_lines if line and line not in filtered]


def _append_missing_facts(filtered: str, missing: list[str]) -> str:
    if not missing:
        return filtered
    sections = [filtered.rstrip(), "... [required facts appended after preservation check] ..."]
    sections.extend(missing)
    return "\n".join(section for section in sections if section)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compress logs, command output, or Python source for UAF workflows.")
    parser.add_argument("--log-file", help="Read terminal output from a file and print a compact version.")
    parser.add_argument("--code-file", help="Read Python source from a file and print a minified version.")
    parser.add_argument("--max-lines", type=int, default=30, help="Maximum approximate lines to keep for logs.")
    parser.add_argument("--command", default="", help="Original command, used to select a family-specific output filter.")
    parser.add_argument("--exit-code", type=int, default=0, help="Original command exit code for preservation checks.")
    parser.add_argument(
        "--kind",
        choices=["auto", "log", "python-code", "contract-sensitive", "text"],
        default="auto",
        help="Input content kind. auto keeps contract-sensitive text unchanged.",
    )
    args = parser.parse_args()

    if args.log_file:
        with open(args.log_file, "r", encoding="utf-8") as handle:
            result = optimize_context_content(
                handle.read(),
                content_kind=args.kind if args.kind != "auto" else "log",
                command=args.command,
                exit_code=args.exit_code,
                max_lines=args.max_lines,
            )
            print(result.stdout)
        return 0
    if args.code_file:
        with open(args.code_file, "r", encoding="utf-8") as handle:
            print(minify_code(handle.read()))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
