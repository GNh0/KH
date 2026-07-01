import argparse
import ast
import json
import re
import sys
from typing import Any, Dict, Tuple

from src.contracts import HarnessResult
from src.skills.base import agent_skill


TOKEN_USAGE_SCOPE = "actual_optimizer_input_output_payload"
TOKEN_COUNT_METHOD = "deterministic_local_estimate_chars_div_4"
TOKEN_COUNT_NOTE = (
    "Counts are derived from the actual optimizer input/output text with KH's local token estimator; "
    "provider billing token usage is not exposed to this harness."
)


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
        r"^\s*Ran\s+\d+\s+tests?\s+in\s+",
        r"^\s*OK\s*$",
        r"\bexit code\s*:\s*\d+",
        r"\breturncode\s*[:=]\s*\d+",
        r"\bline\s+\d+\b",
        r"\b[A-Za-z0-9_./\\-]+\.(?:py|js|ts|tsx|cs|java|sql|md):\d+\b",
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
        if _looks_like_codex_session_jsonl(content):
            result = summarize_session_jsonl(content, max_lines=max_lines)
            metadata = dict(result.metadata)
            metadata["strategy"] = "session-jsonl"
            metadata["content_kind"] = detected_kind
            return HarnessResult(
                success=result.success,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                execution_time=result.execution_time,
                metadata=metadata,
            )
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
    name="summarize_agent_transcript",
    description="Compress long agent workflow transcripts while preserving task, review, verification, and commit evidence.",
)
def summarize_agent_transcript(
    transcript: str,
    max_lines: int = 160,
    label: str = "agent-transcript",
) -> HarnessResult:
    """Summarize agent transcripts without dropping lifecycle evidence."""
    lines = transcript.splitlines()
    raw_bytes = len(transcript.encode("utf-8"))
    if len(lines) <= max_lines:
        metadata = {
            "strategy": "passthrough",
            "content_kind": "agent-transcript",
            "raw_bytes": raw_bytes,
            "filtered_bytes": raw_bytes,
            "raw_lines": len(lines),
            "filtered_lines": len(lines),
            "token_savings_ratio": 0.0,
            "token_usage": compare_token_usage(
                transcript,
                transcript,
                strategy="passthrough",
                label=label,
            ),
        }
        return HarnessResult(success=True, stdout=transcript, stderr="", exit_code=0, metadata=metadata)

    selected = _agent_transcript_selected_indices(lines, max_lines=max_lines)
    required = [index for index, line in enumerate(lines) if _agent_transcript_line_priority(line) >= 90]
    selected = sorted(set(selected) | set(required))
    omitted = len(lines) - len(selected)
    sections = [f"... [agent-transcript optimized: {omitted} lines omitted] ..."]
    sections.extend(lines[index] for index in selected)
    optimized = "\n".join(sections)
    missing = _missing_agent_transcript_facts(lines, optimized)
    fallback_reason = ""
    if missing:
        optimized = _append_missing_facts(optimized, missing)
        fallback_reason = "required lifecycle facts were appended after preservation check"
    filtered_bytes = len(optimized.encode("utf-8"))
    metadata = {
        "strategy": "agent-transcript",
        "content_kind": "agent-transcript",
        "raw_bytes": raw_bytes,
        "filtered_bytes": filtered_bytes,
        "raw_lines": len(lines),
        "filtered_lines": len(optimized.splitlines()),
        "omitted_lines": omitted,
        "token_savings_ratio": _savings_ratio(raw_bytes, filtered_bytes),
        "fallback_reason": fallback_reason,
        "preserved_fact_count": len(required),
        "token_usage": compare_token_usage(
            transcript,
            optimized,
            strategy="agent-transcript",
            label=label,
        ),
    }
    return HarnessResult(success=True, stdout=optimized, stderr="", exit_code=0, metadata=metadata)


@agent_skill(
    name="summarize_session_jsonl",
    description="Compress Codex session JSONL while preserving audit-relevant events and dropping huge prompt/encrypted payloads.",
)
def summarize_session_jsonl(session_jsonl: str, max_lines: int = 80) -> HarnessResult:
    raw_lines = session_jsonl.splitlines()
    if not raw_lines:
        return HarnessResult(success=True, stdout="", stderr="", exit_code=0, metadata={})

    compact_records: list[tuple[int, int, str]] = []
    host_actual_token_evidence = extract_host_actual_token_evidence(session_jsonl)
    for index, line in enumerate(raw_lines):
        compact = _compact_session_jsonl_event(line, index + 1)
        if compact is not None:
            compact_records.append(compact)

    if not compact_records:
        return summarize_command_output(
            command="codex-session-jsonl",
            stdout=session_jsonl,
            stderr="",
            exit_code=0,
            max_lines=max_lines,
        )

    limit = max(1, max_lines - 1)
    if len(compact_records) <= limit:
        selected = compact_records
    else:
        selected_indices = set()
        selected_indices.add(0)
        tail_count = min(8, max(1, limit // 4))
        selected_indices.update(range(max(0, len(compact_records) - tail_count), len(compact_records)))
        budget = max(0, limit - len(selected_indices))
        prioritized = sorted(
            ((-priority, order) for order, (priority, _, _) in enumerate(compact_records) if order not in selected_indices)
        )
        selected_indices.update(order for _, order in prioritized[:budget])
        selected = [compact_records[order] for order in sorted(selected_indices)]

    omitted = max(0, len(compact_records) - len(selected))
    header = {
        "kh_token_optimizer": "session-jsonl",
        "raw_lines": len(raw_lines),
        "compact_records": len(compact_records),
        "kept_records": len(selected),
        "omitted_records": omitted,
    }
    output_lines = [json.dumps(header, ensure_ascii=False, sort_keys=True)]
    output_lines.extend(record for _, _, record in selected)
    optimized = "\n".join(output_lines)
    raw_bytes = len(session_jsonl.encode("utf-8", errors="replace"))
    filtered_bytes = len(optimized.encode("utf-8", errors="replace"))
    metadata = {
        "strategy": "session-jsonl",
        "raw_bytes": raw_bytes,
        "filtered_bytes": filtered_bytes,
        "raw_lines": len(raw_lines),
        "filtered_lines": len(output_lines),
        "omitted_lines": max(0, len(raw_lines) - len(output_lines)),
        "token_savings_ratio": _savings_ratio(raw_bytes, filtered_bytes),
        "host_actual_token_evidence": host_actual_token_evidence,
        "host_actual_tokens_available": host_actual_token_evidence["host_actual_tokens_available"],
        "host_actual_tokens_used": host_actual_token_evidence["host_actual_tokens_used"],
        "host_actual_token_source": host_actual_token_evidence["host_actual_token_source"],
        "token_usage": compare_token_usage(
            session_jsonl,
            optimized,
            strategy="session-jsonl",
            label="codex-session-jsonl",
        ),
    }
    return HarnessResult(success=True, stdout=optimized, stderr="", exit_code=0, metadata=metadata)


@agent_skill(
    name="compare_token_usage",
    description="Report before/after token use for actual optimizer input and output text.",
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
    host_actual_token_evidence = extract_host_actual_token_evidence(raw_text)
    return {
        "label": label,
        "strategy": strategy,
        "where_saved": _where_saved_payload(strategy=strategy, label=label),
        "without_token_optimizer": without_optimizer,
        "with_token_optimizer": with_optimizer,
        "estimated_tokens_saved": saved,
        "token_savings_ratio": _savings_ratio(without_optimizer, with_optimizer),
        "estimated_payload_without_optimizer": without_optimizer,
        "estimated_payload_with_optimizer": with_optimizer,
        "estimated_payload_tokens_saved": saved,
        "estimated_payload_token_savings_ratio": _savings_ratio(without_optimizer, with_optimizer),
        "payload_token_count_method": TOKEN_COUNT_METHOD,
        "payload_token_count_is_estimate": True,
        "host_actual_tokens_available": host_actual_token_evidence["host_actual_tokens_available"],
        "host_actual_tokens_used": host_actual_token_evidence["host_actual_tokens_used"],
        "host_actual_token_source": host_actual_token_evidence["host_actual_token_source"],
        "host_actual_token_evidence": host_actual_token_evidence,
        **_actual_usage_metrics(
            raw_text=raw_text,
            optimized_text=optimized_text,
            without_optimizer=without_optimizer,
            with_optimizer=with_optimizer,
        ),
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
    actual_without_optimizer = sum(record["actual_without_token_optimizer"] for record in normalized)
    actual_with_optimizer = sum(record["actual_with_token_optimizer"] for record in normalized)
    actual_saved = max(0, actual_without_optimizer - actual_with_optimizer)
    actual_without_bytes = sum(record["actual_without_token_optimizer_bytes"] for record in normalized)
    actual_with_bytes = sum(record["actual_with_token_optimizer_bytes"] for record in normalized)
    actual_without_chars = sum(record["actual_without_token_optimizer_chars"] for record in normalized)
    actual_with_chars = sum(record["actual_with_token_optimizer_chars"] for record in normalized)
    host_actual_token_evidence = _aggregate_host_actual_token_evidence(
        [record["host_actual_token_evidence"] for record in normalized]
    )
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
                "actual_usage_scope": TOKEN_USAGE_SCOPE,
                "token_count_method": TOKEN_COUNT_METHOD,
                "token_count_is_estimate": True,
                "billing_tokens_available": False,
                "actual_without_token_optimizer": 0,
                "actual_with_token_optimizer": 0,
                "actual_tokens_saved": 0,
                "actual_token_savings_ratio": 0.0,
                "actual_without_token_optimizer_bytes": 0,
                "actual_with_token_optimizer_bytes": 0,
                "actual_bytes_saved": 0,
                "actual_byte_savings_ratio": 0.0,
                "actual_without_token_optimizer_chars": 0,
                "actual_with_token_optimizer_chars": 0,
                "actual_chars_saved": 0,
                "actual_char_savings_ratio": 0.0,
                "estimated_payload_without_optimizer": 0,
                "estimated_payload_with_optimizer": 0,
                "estimated_payload_tokens_saved": 0,
                "estimated_payload_token_savings_ratio": 0.0,
                "host_actual_tokens_available": False,
                "host_actual_tokens_used": 0,
            },
        )
        bucket["case_count"] += 1
        bucket["without_token_optimizer"] += record["without_token_optimizer"]
        bucket["with_token_optimizer"] += record["with_token_optimizer"]
        bucket["estimated_tokens_saved"] += record["estimated_tokens_saved"]
        bucket["actual_without_token_optimizer"] += record["actual_without_token_optimizer"]
        bucket["actual_with_token_optimizer"] += record["actual_with_token_optimizer"]
        bucket["actual_tokens_saved"] += record["actual_tokens_saved"]
        bucket["actual_without_token_optimizer_bytes"] += record["actual_without_token_optimizer_bytes"]
        bucket["actual_with_token_optimizer_bytes"] += record["actual_with_token_optimizer_bytes"]
        bucket["actual_bytes_saved"] += record["actual_bytes_saved"]
        bucket["actual_without_token_optimizer_chars"] += record["actual_without_token_optimizer_chars"]
        bucket["actual_with_token_optimizer_chars"] += record["actual_with_token_optimizer_chars"]
        bucket["actual_chars_saved"] += record["actual_chars_saved"]
        bucket["estimated_payload_without_optimizer"] += record["estimated_payload_without_optimizer"]
        bucket["estimated_payload_with_optimizer"] += record["estimated_payload_with_optimizer"]
        bucket["estimated_payload_tokens_saved"] += record["estimated_payload_tokens_saved"]
        if record["host_actual_tokens_available"]:
            bucket["host_actual_tokens_available"] = True
            bucket["host_actual_tokens_used"] = max(bucket["host_actual_tokens_used"], record["host_actual_tokens_used"])
    for bucket in by_strategy.values():
        bucket["token_savings_ratio"] = _savings_ratio(
            bucket["without_token_optimizer"],
            bucket["with_token_optimizer"],
        )
        bucket["estimated_payload_token_savings_ratio"] = _savings_ratio(
            bucket["estimated_payload_without_optimizer"],
            bucket["estimated_payload_with_optimizer"],
        )
        bucket["actual_token_savings_ratio"] = _savings_ratio(
            bucket["actual_without_token_optimizer"],
            bucket["actual_with_token_optimizer"],
        )
        bucket["actual_byte_savings_ratio"] = _savings_ratio(
            bucket["actual_without_token_optimizer_bytes"],
            bucket["actual_with_token_optimizer_bytes"],
        )
        bucket["actual_char_savings_ratio"] = _savings_ratio(
            bucket["actual_without_token_optimizer_chars"],
            bucket["actual_with_token_optimizer_chars"],
        )
    return {
        "case_count": len(normalized),
        "without_token_optimizer": without_optimizer,
        "with_token_optimizer": with_optimizer,
        "estimated_tokens_saved": saved,
        "token_savings_ratio": _savings_ratio(without_optimizer, with_optimizer),
        "estimated_payload_without_optimizer": without_optimizer,
        "estimated_payload_with_optimizer": with_optimizer,
        "estimated_payload_tokens_saved": saved,
        "estimated_payload_token_savings_ratio": _savings_ratio(without_optimizer, with_optimizer),
        "payload_token_count_method": TOKEN_COUNT_METHOD,
        "payload_token_count_is_estimate": True,
        "actual_usage_scope": TOKEN_USAGE_SCOPE,
        "token_count_method": TOKEN_COUNT_METHOD,
        "token_count_note": TOKEN_COUNT_NOTE,
        "token_count_is_estimate": True,
        "billing_tokens_available": False,
        "host_actual_tokens_available": host_actual_token_evidence["host_actual_tokens_available"],
        "host_actual_tokens_used": host_actual_token_evidence["host_actual_tokens_used"],
        "host_actual_token_source": host_actual_token_evidence["host_actual_token_source"],
        "host_actual_token_evidence": host_actual_token_evidence,
        "actual_without_token_optimizer": actual_without_optimizer,
        "actual_with_token_optimizer": actual_with_optimizer,
        "actual_tokens_saved": actual_saved,
        "actual_token_savings_ratio": _savings_ratio(actual_without_optimizer, actual_with_optimizer),
        "actual_without_token_optimizer_bytes": actual_without_bytes,
        "actual_with_token_optimizer_bytes": actual_with_bytes,
        "actual_bytes_saved": max(0, actual_without_bytes - actual_with_bytes),
        "actual_byte_savings_ratio": _savings_ratio(actual_without_bytes, actual_with_bytes),
        "actual_without_token_optimizer_chars": actual_without_chars,
        "actual_with_token_optimizer_chars": actual_with_chars,
        "actual_chars_saved": max(0, actual_without_chars - actual_with_chars),
        "actual_char_savings_ratio": _savings_ratio(actual_without_chars, actual_with_chars),
        "actual_usage": _aggregate_actual_usage(
            actual_without_optimizer=actual_without_optimizer,
            actual_with_optimizer=actual_with_optimizer,
            actual_without_bytes=actual_without_bytes,
            actual_with_bytes=actual_with_bytes,
            actual_without_chars=actual_without_chars,
            actual_with_chars=actual_with_chars,
        ),
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


@agent_skill(
    name="extract_host_actual_token_evidence",
    description="Extract host-visible actual token evidence such as Codex token_count events and GoalState tokensUsed.",
)
def extract_host_actual_token_evidence(text: str) -> Dict[str, Any]:
    """Extract host-visible token evidence without claiming counterfactual billing savings."""
    token_count_events: list[Dict[str, Any]] = []
    goal_token_events: list[Dict[str, Any]] = []
    max_total_tokens = 0
    max_last_input_tokens = 0
    latest_session_total_tokens = 0
    latest_goal_tokens_used = 0
    model_context_window = 0

    for line_number, line in enumerate((text or "").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        payload = event.get("payload", {}) or {}
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        if payload_type == "token_count":
            info = payload.get("info", {}) or {}
            if not isinstance(info, dict):
                continue
            total = info.get("total_token_usage", {}) or {}
            last = info.get("last_token_usage", {}) or {}
            if not isinstance(total, dict) or not isinstance(last, dict):
                continue
            total_tokens = _int_value(total.get("total_tokens", 0))
            last_input_tokens = _int_value(last.get("input_tokens", 0))
            last_output_tokens = _int_value(last.get("output_tokens", 0))
            context_window = _int_value(info.get("model_context_window", 0))
            latest_session_total_tokens = total_tokens or latest_session_total_tokens
            max_total_tokens = max(max_total_tokens, total_tokens)
            max_last_input_tokens = max(max_last_input_tokens, last_input_tokens)
            model_context_window = context_window or model_context_window
            token_count_events.append(
                {
                    "line": line_number,
                    "source": "session_jsonl.token_count",
                    "total_tokens": total_tokens,
                    "last_input_tokens": last_input_tokens,
                    "last_output_tokens": last_output_tokens,
                    "model_context_window": context_window,
                }
            )
            continue
        if payload_type == "thread_goal_updated":
            goal = payload.get("goal", {}) or {}
            if not isinstance(goal, dict):
                continue
            tokens_used = _int_value(goal.get("tokensUsed", 0))
            if tokens_used <= 0:
                continue
            latest_goal_tokens_used = tokens_used
            goal_token_events.append(
                {
                    "line": line_number,
                    "source": "goal.tokensUsed",
                    "status": str(goal.get("status", "")),
                    "tokens_used": tokens_used,
                    "time_used_seconds": _int_value(goal.get("timeUsedSeconds", 0)),
                }
            )

    host_actual_tokens_used = latest_goal_tokens_used or latest_session_total_tokens
    host_actual_token_source = (
        "goal.tokensUsed"
        if latest_goal_tokens_used
        else "session_jsonl.token_count"
        if latest_session_total_tokens
        else "unavailable"
    )
    host_actual_tokens_available = host_actual_tokens_used > 0
    evidence_events = [*goal_token_events[-3:], *token_count_events[-3:]]
    return {
        "host_actual_tokens_available": host_actual_tokens_available,
        "host_actual_tokens_used": host_actual_tokens_used,
        "host_actual_token_source": host_actual_token_source,
        "latest_goal_tokens_used": latest_goal_tokens_used,
        "latest_session_total_tokens": latest_session_total_tokens,
        "max_session_total_tokens": max_total_tokens,
        "max_last_input_tokens": max_last_input_tokens,
        "model_context_window": model_context_window,
        "token_count_event_count": len(token_count_events),
        "goal_token_event_count": len(goal_token_events),
        "evidence_event_count": len(token_count_events) + len(goal_token_events),
        "evidence_events": evidence_events,
        "missing_reason": ""
        if host_actual_tokens_available
        else "no Codex token_count or GoalState tokensUsed events found in optimizer input",
        "interpretation": (
            "Host actual tokens describe observed session or goal usage. Payload savings remain estimated unless "
            "the host exposes billing telemetry for both raw and optimized counterfactual calls."
        ),
    }


def _where_saved_payload(strategy: str, label: str) -> Dict[str, Any]:
    return {
        "strategy": strategy or "unknown",
        "label": label or "",
        "scope": label or strategy or "optimizer-payload",
    }


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _aggregate_host_actual_token_evidence(evidence_records: list[Dict[str, Any]]) -> Dict[str, Any]:
    available = [record for record in evidence_records if record.get("host_actual_tokens_available")]
    if not available:
        return {
            "host_actual_tokens_available": False,
            "host_actual_tokens_used": 0,
            "host_actual_token_source": "unavailable",
            "latest_goal_tokens_used": 0,
            "latest_session_total_tokens": 0,
            "max_session_total_tokens": 0,
            "max_last_input_tokens": 0,
            "model_context_window": 0,
            "token_count_event_count": 0,
            "goal_token_event_count": 0,
            "evidence_event_count": 0,
            "evidence_events": [],
            "missing_reason": "no host token evidence in aggregated optimizer records",
        }
    latest = available[-1]
    return {
        "host_actual_tokens_available": True,
        "host_actual_tokens_used": _int_value(latest.get("host_actual_tokens_used", 0)),
        "host_actual_token_source": str(latest.get("host_actual_token_source", "")),
        "latest_goal_tokens_used": max(_int_value(record.get("latest_goal_tokens_used", 0)) for record in available),
        "latest_session_total_tokens": max(
            _int_value(record.get("latest_session_total_tokens", 0)) for record in available
        ),
        "max_session_total_tokens": max(_int_value(record.get("max_session_total_tokens", 0)) for record in available),
        "max_last_input_tokens": max(_int_value(record.get("max_last_input_tokens", 0)) for record in available),
        "model_context_window": max(_int_value(record.get("model_context_window", 0)) for record in available),
        "token_count_event_count": sum(_int_value(record.get("token_count_event_count", 0)) for record in available),
        "goal_token_event_count": sum(_int_value(record.get("goal_token_event_count", 0)) for record in available),
        "evidence_event_count": sum(_int_value(record.get("evidence_event_count", 0)) for record in available),
        "evidence_events": [event for record in available for event in record.get("evidence_events", [])][-6:],
        "missing_reason": "",
    }


def _actual_usage_metrics(
    raw_text: str,
    optimized_text: str,
    without_optimizer: int,
    with_optimizer: int,
) -> Dict[str, Any]:
    raw_bytes = len(raw_text.encode("utf-8", errors="replace"))
    optimized_bytes = len(optimized_text.encode("utf-8", errors="replace"))
    raw_chars = len(raw_text)
    optimized_chars = len(optimized_text)
    token_saved = max(0, without_optimizer - with_optimizer)
    bytes_saved = max(0, raw_bytes - optimized_bytes)
    chars_saved = max(0, raw_chars - optimized_chars)
    return {
        "actual_usage_scope": TOKEN_USAGE_SCOPE,
        "token_count_method": TOKEN_COUNT_METHOD,
        "token_count_note": TOKEN_COUNT_NOTE,
        "token_count_is_estimate": True,
        "billing_tokens_available": False,
        "actual_without_token_optimizer": without_optimizer,
        "actual_with_token_optimizer": with_optimizer,
        "actual_tokens_saved": token_saved,
        "actual_token_savings_ratio": _savings_ratio(without_optimizer, with_optimizer),
        "actual_without_token_optimizer_bytes": raw_bytes,
        "actual_with_token_optimizer_bytes": optimized_bytes,
        "actual_bytes_saved": bytes_saved,
        "actual_byte_savings_ratio": _savings_ratio(raw_bytes, optimized_bytes),
        "actual_without_token_optimizer_chars": raw_chars,
        "actual_with_token_optimizer_chars": optimized_chars,
        "actual_chars_saved": chars_saved,
        "actual_char_savings_ratio": _savings_ratio(raw_chars, optimized_chars),
        "actual_usage": _actual_usage_payload(
            without_optimizer=without_optimizer,
            with_optimizer=with_optimizer,
            raw_bytes=raw_bytes,
            optimized_bytes=optimized_bytes,
            raw_chars=raw_chars,
            optimized_chars=optimized_chars,
        ),
    }


def _actual_usage_payload(
    without_optimizer: int,
    with_optimizer: int,
    raw_bytes: int,
    optimized_bytes: int,
    raw_chars: int,
    optimized_chars: int,
) -> Dict[str, Any]:
    return {
        "scope": TOKEN_USAGE_SCOPE,
        "token_count_method": TOKEN_COUNT_METHOD,
        "token_count_note": TOKEN_COUNT_NOTE,
        "token_count_is_estimate": True,
        "billing_tokens_available": False,
        "without_optimizer": {
            "tokens": without_optimizer,
            "bytes": raw_bytes,
            "characters": raw_chars,
        },
        "with_optimizer": {
            "tokens": with_optimizer,
            "bytes": optimized_bytes,
            "characters": optimized_chars,
        },
        "saved": {
            "tokens": max(0, without_optimizer - with_optimizer),
            "bytes": max(0, raw_bytes - optimized_bytes),
            "characters": max(0, raw_chars - optimized_chars),
        },
        "savings_ratio": {
            "tokens": _savings_ratio(without_optimizer, with_optimizer),
            "bytes": _savings_ratio(raw_bytes, optimized_bytes),
            "characters": _savings_ratio(raw_chars, optimized_chars),
        },
    }


def _aggregate_actual_usage(
    actual_without_optimizer: int,
    actual_with_optimizer: int,
    actual_without_bytes: int,
    actual_with_bytes: int,
    actual_without_chars: int,
    actual_with_chars: int,
) -> Dict[str, Any]:
    return _actual_usage_payload(
        without_optimizer=actual_without_optimizer,
        with_optimizer=actual_with_optimizer,
        raw_bytes=actual_without_bytes,
        optimized_bytes=actual_with_bytes,
        raw_chars=actual_without_chars,
        optimized_chars=actual_with_chars,
    )


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
    host_actual_token_evidence = (
        token_usage.get("host_actual_token_evidence")
        if isinstance(token_usage.get("host_actual_token_evidence"), dict)
        else {}
    )
    if not host_actual_token_evidence:
        host_actual_token_evidence = {
            "host_actual_tokens_available": bool(token_usage.get("host_actual_tokens_available", False)),
            "host_actual_tokens_used": int(token_usage.get("host_actual_tokens_used", 0)),
            "host_actual_token_source": str(token_usage.get("host_actual_token_source", "unavailable")),
            "latest_goal_tokens_used": int(token_usage.get("host_actual_tokens_used", 0))
            if str(token_usage.get("host_actual_token_source", "")) == "goal.tokensUsed"
            else 0,
            "latest_session_total_tokens": int(token_usage.get("host_actual_tokens_used", 0))
            if str(token_usage.get("host_actual_token_source", "")) == "session_jsonl.token_count"
            else 0,
            "max_session_total_tokens": 0,
            "max_last_input_tokens": 0,
            "model_context_window": 0,
            "token_count_event_count": 0,
            "goal_token_event_count": 0,
            "evidence_event_count": 0,
            "evidence_events": [],
            "missing_reason": "host token evidence not present on this token usage record",
        }
    actual_usage = token_usage.get("actual_usage") if isinstance(token_usage.get("actual_usage"), dict) else {}
    actual_without = int(
        token_usage.get(
            "actual_without_token_optimizer",
            actual_usage.get("without_optimizer", {}).get("tokens", without_optimizer)
            if isinstance(actual_usage.get("without_optimizer"), dict)
            else without_optimizer,
        )
    )
    actual_with = int(
        token_usage.get(
            "actual_with_token_optimizer",
            actual_usage.get("with_optimizer", {}).get("tokens", with_optimizer)
            if isinstance(actual_usage.get("with_optimizer"), dict)
            else with_optimizer,
        )
    )
    actual_saved = max(0, actual_without - actual_with)
    actual_without_bytes = int(
        token_usage.get(
            "actual_without_token_optimizer_bytes",
            actual_usage.get("without_optimizer", {}).get("bytes", 0)
            if isinstance(actual_usage.get("without_optimizer"), dict)
            else 0,
        )
    )
    actual_with_bytes = int(
        token_usage.get(
            "actual_with_token_optimizer_bytes",
            actual_usage.get("with_optimizer", {}).get("bytes", 0)
            if isinstance(actual_usage.get("with_optimizer"), dict)
            else 0,
        )
    )
    actual_without_chars = int(
        token_usage.get(
            "actual_without_token_optimizer_chars",
            actual_usage.get("without_optimizer", {}).get("characters", 0)
            if isinstance(actual_usage.get("without_optimizer"), dict)
            else 0,
        )
    )
    actual_with_chars = int(
        token_usage.get(
            "actual_with_token_optimizer_chars",
            actual_usage.get("with_optimizer", {}).get("characters", 0)
            if isinstance(actual_usage.get("with_optimizer"), dict)
            else 0,
        )
    )
    return {
        "label": str(token_usage.get("label", "")),
        "strategy": str(token_usage.get("strategy", "")),
        "where_saved": token_usage.get("where_saved")
        if isinstance(token_usage.get("where_saved"), dict)
        else _where_saved_payload(
            strategy=str(token_usage.get("strategy", "")),
            label=str(token_usage.get("label", "")),
        ),
        "without_token_optimizer": without_optimizer,
        "with_token_optimizer": with_optimizer,
        "estimated_tokens_saved": int(token_usage.get("estimated_tokens_saved", saved)),
        "token_savings_ratio": float(token_usage.get("token_savings_ratio", _savings_ratio(without_optimizer, with_optimizer))),
        "estimated_payload_without_optimizer": int(
            token_usage.get("estimated_payload_without_optimizer", without_optimizer)
        ),
        "estimated_payload_with_optimizer": int(token_usage.get("estimated_payload_with_optimizer", with_optimizer)),
        "estimated_payload_tokens_saved": int(token_usage.get("estimated_payload_tokens_saved", saved)),
        "estimated_payload_token_savings_ratio": float(
            token_usage.get("estimated_payload_token_savings_ratio", _savings_ratio(without_optimizer, with_optimizer))
        ),
        "payload_token_count_method": str(token_usage.get("payload_token_count_method", TOKEN_COUNT_METHOD)),
        "payload_token_count_is_estimate": bool(token_usage.get("payload_token_count_is_estimate", True)),
        "host_actual_tokens_available": bool(host_actual_token_evidence.get("host_actual_tokens_available", False)),
        "host_actual_tokens_used": int(host_actual_token_evidence.get("host_actual_tokens_used", 0)),
        "host_actual_token_source": str(host_actual_token_evidence.get("host_actual_token_source", "unavailable")),
        "host_actual_token_evidence": host_actual_token_evidence,
        "actual_usage_scope": str(token_usage.get("actual_usage_scope", TOKEN_USAGE_SCOPE)),
        "token_count_method": str(token_usage.get("token_count_method", TOKEN_COUNT_METHOD)),
        "token_count_is_estimate": bool(token_usage.get("token_count_is_estimate", True)),
        "billing_tokens_available": bool(token_usage.get("billing_tokens_available", False)),
        "actual_without_token_optimizer": actual_without,
        "actual_with_token_optimizer": actual_with,
        "actual_tokens_saved": int(token_usage.get("actual_tokens_saved", actual_saved)),
        "actual_token_savings_ratio": float(
            token_usage.get("actual_token_savings_ratio", _savings_ratio(actual_without, actual_with))
        ),
        "actual_without_token_optimizer_bytes": actual_without_bytes,
        "actual_with_token_optimizer_bytes": actual_with_bytes,
        "actual_bytes_saved": int(token_usage.get("actual_bytes_saved", max(0, actual_without_bytes - actual_with_bytes))),
        "actual_byte_savings_ratio": float(
            token_usage.get("actual_byte_savings_ratio", _savings_ratio(actual_without_bytes, actual_with_bytes))
        ),
        "actual_without_token_optimizer_chars": actual_without_chars,
        "actual_with_token_optimizer_chars": actual_with_chars,
        "actual_chars_saved": int(token_usage.get("actual_chars_saved", max(0, actual_without_chars - actual_with_chars))),
        "actual_char_savings_ratio": float(
            token_usage.get("actual_char_savings_ratio", _savings_ratio(actual_without_chars, actual_with_chars))
        ),
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
    if re.search(r"^\s*ran\s+\d+\s+tests?\s+in\s+", lowered):
        return 82
    if lowered.strip() in {"ok", "success"}:
        return 80
    if re.search(r"\btraceback\b", lowered):
        return 80
    if re.search(r"\b(user_constraint|decision|evidence|blocker|p[0-2])\b", lowered):
        return 75
    if re.search(
        r"\bline\s+\d+\b|:\d+:\d+|\(\d+,\d+\)|\b[A-Za-z0-9_./\\-]+\.(?:py|js|ts|tsx|cs|java|sql|md):\d+\b",
        lowered,
    ):
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


def _agent_transcript_selected_indices(lines: list[str], max_lines: int) -> list[int]:
    head_count = min(6, len(lines))
    tail_count = min(6, max(0, len(lines) - head_count))
    selected = set(range(head_count))
    selected.update(range(max(head_count, len(lines) - tail_count), len(lines)))
    weighted = []
    for index, line in enumerate(lines):
        if index in selected:
            continue
        priority = _agent_transcript_line_priority(line)
        if priority > 0:
            weighted.append((-priority, index))
    budget = max(0, max_lines - len(selected))
    selected.update(index for _, index in sorted(weighted)[:budget])
    return sorted(selected)


def _agent_transcript_line_priority(line: str) -> int:
    lowered = line.lower()
    if any(
        marker in lowered
        for marker in [
            "task_status",
            "review_status",
            "commit_sha",
            "next_task",
            "token_optimizer_status",
            "workspace_strategy",
        ]
    ):
        return 110
    if "red/green" in lowered or re.search(r"\b(red|green|tdd|failing-first)\b", lowered):
        return 105
    if re.search(r"\b(exit code|returncode)\s*[:=]\s*\d+", lowered):
        return 105
    if "sandbox retry" in lowered or ("sandbox" in lowered and "access is denied" in lowered):
        return 102
    if "reviewer severity" in lowered or re.search(r"\bp[0-3]\b", lowered):
        return 100
    if re.search(r"\b(important|critical|with fixes|approved|blocking issue)\b", lowered):
        return 100
    if "worktree" in lowered or ".worktrees" in lowered:
        return 98
    if "file references" in lowered or re.search(r"[A-Za-z0-9_./\\ -]+\.[A-Za-z0-9]+:\d+", line):
        return 100
    if re.search(r"\b[0-9a-f]{7,40}\b", lowered):
        return 96
    if re.search(r"\btask\s+\d+", lowered):
        return 94
    if any(marker in lowered for marker in ["spec compliant", "issues found", "quality with fixes", "approved"]):
        return 92
    if any(marker in lowered for marker in ["failed", "error", "assertionerror", "traceback", "access is denied"]):
        return 90
    if any(marker in lowered for marker in ["npm.cmd", "python -m", "git commit", "git status", "git diff"]):
        return 80
    if any(marker in lowered for marker in ["changed files", "commands run", "evidence", "blocked", "approval"]):
        return 75
    return 0


def _missing_agent_transcript_facts(lines: list[str], optimized: str) -> list[str]:
    missing = []
    for line in lines:
        if _agent_transcript_line_priority(line) >= 90 and line not in optimized:
            missing.append(line)
    return missing


def _looks_like_codex_session_jsonl(text: str) -> bool:
    sample = [line for line in (text or "").splitlines()[:20] if line.strip()]
    if not sample:
        return False
    parsed = 0
    session_markers = 0
    for line in sample:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        parsed += 1
        if payload.get("type") in {"session_meta", "response_item", "event_msg"}:
            session_markers += 1
    return parsed >= 1 and session_markers >= 1


def _compact_session_jsonl_event(line: str, line_number: int) -> tuple[int, int, str] | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        priority = _line_priority(line)
        if priority <= 0:
            return None
        record = {"line": line_number, "type": "raw", "sample": _short_text(line, 500)}
        return priority, line_number, json.dumps(record, ensure_ascii=False, sort_keys=True)

    event_type = str(event.get("type", ""))
    payload = event.get("payload", {}) or {}
    if not isinstance(payload, dict):
        return None
    payload_type = str(payload.get("type", ""))

    if event_type == "session_meta":
        record = {
            "line": line_number,
            "type": "session_meta",
            "id": payload.get("id", ""),
            "cwd": payload.get("cwd", ""),
            "thread_source": payload.get("thread_source", ""),
            "agent_nickname": payload.get("agent_nickname", ""),
            "agent_role": payload.get("agent_role", ""),
            "cli_version": payload.get("cli_version", ""),
        }
        return 95, line_number, json.dumps(record, ensure_ascii=False, sort_keys=True)

    if payload_type in {"reasoning"}:
        return None

    if payload_type == "token_count":
        info = payload.get("info", {}) or {}
        total = info.get("total_token_usage", {}) or {}
        last = info.get("last_token_usage", {}) or {}
        record = {
            "line": line_number,
            "type": "token_count",
            "total_tokens": total.get("total_tokens", 0),
            "last_input_tokens": last.get("input_tokens", 0),
            "context_window": info.get("model_context_window", 0),
        }
        return 35, line_number, json.dumps(record, ensure_ascii=False, sort_keys=True)

    if payload_type == "thread_goal_updated":
        goal = payload.get("goal", {}) or {}
        record = {
            "line": line_number,
            "type": "thread_goal_updated",
            "status": goal.get("status", ""),
            "objective": _short_text(str(goal.get("objective", "")), 240),
            "tokensUsed": goal.get("tokensUsed", 0),
            "timeUsedSeconds": goal.get("timeUsedSeconds", 0),
        }
        return 120, line_number, json.dumps(record, ensure_ascii=False, sort_keys=True)

    if payload_type == "task_complete":
        record = {
            "line": line_number,
            "type": "task_complete",
            "last_agent_message": _short_text(str(payload.get("last_agent_message", "")), 500),
        }
        return 125, line_number, json.dumps(record, ensure_ascii=False, sort_keys=True)

    if payload_type in {"message", "agent_message"}:
        text = _session_payload_text(payload)
        if not text.strip():
            return None
        priority = 80
        lowered = text.lower()
        if any(marker in lowered for marker in ["error", "failed", "blocked", "stopped", "중단", "차단", "실패"]):
            priority = 115
        if payload.get("phase") == "final_answer":
            priority = max(priority, 110)
        record = {
            "line": line_number,
            "type": payload_type,
            "role": payload.get("role", ""),
            "phase": payload.get("phase", ""),
            "text": _short_text(text, 500),
        }
        return priority, line_number, json.dumps(record, ensure_ascii=False, sort_keys=True)

    if payload_type in {"function_call", "custom_tool_call"}:
        raw_arguments = payload.get("arguments") or payload.get("input") or ""
        record = {
            "line": line_number,
            "type": payload_type,
            "name": payload.get("name", ""),
            "arguments": _short_text(str(raw_arguments), 500),
        }
        return 90, line_number, json.dumps(record, ensure_ascii=False, sort_keys=True)

    if payload_type in {"function_call_output", "custom_tool_call_output"}:
        output = _session_payload_text(payload)
        if not output.strip():
            return None
        priority = 45
        lowered = output.lower()
        if any(marker in lowered for marker in ["error", "failed", "blocked", "traceback", "exception", "exit code", "returncode"]):
            priority = 115
        record = {
            "line": line_number,
            "type": payload_type,
            "output": _short_text(output, 500),
        }
        return priority, line_number, json.dumps(record, ensure_ascii=False, sort_keys=True)

    return None


def _session_payload_text(payload: Dict[str, Any]) -> str:
    if "message" in payload:
        return _content_to_text(payload.get("message"))
    if "content" in payload:
        return _content_to_text(payload.get("content"))
    if "output" in payload:
        return _content_to_text(payload.get("output"))
    return ""


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("input_text") or item.get("output_text") or ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False, sort_keys=True)
    return str(content or "")


def _short_text(text: str, max_length: int) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    return compact[:max_length] + ("..." if len(compact) > max_length else "")


def _safe_stdout_write(text: str) -> None:
    output = (text or "") + "\n"
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(output.encode("utf-8", errors="replace"))
        sys.stdout.flush()
        return
    sys.stdout.write(output)


def _write_cli_result(result: HarnessResult, report_json: bool) -> None:
    if report_json:
        _safe_stdout_write(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
        return
    _safe_stdout_write(result.stdout)


def _read_cli_text_file(path: str) -> str:
    with open(path, "rb") as handle:
        data = handle.read()
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp949", "mbcs"):
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compress logs, command output, or Python source for UAF workflows.")
    parser.add_argument("--log-file", help="Read terminal output from a file and print a compact version.")
    parser.add_argument("--code-file", help="Read Python source from a file and print a minified version.")
    parser.add_argument("--max-lines", type=int, default=30, help="Maximum approximate lines to keep for logs.")
    parser.add_argument("--command", default="", help="Original command, used to select a family-specific output filter.")
    parser.add_argument("--exit-code", type=int, default=0, help="Original command exit code for preservation checks.")
    parser.add_argument("--report-json", action="store_true", help="Print HarnessResult JSON with token usage metadata instead of compact text only.")
    parser.add_argument(
        "--kind",
        choices=["auto", "log", "python-code", "contract-sensitive", "text"],
        default="auto",
        help="Input content kind. auto keeps contract-sensitive text unchanged.",
    )
    args = parser.parse_args()

    if args.log_file:
        result = optimize_context_content(
            _read_cli_text_file(args.log_file),
            content_kind=args.kind if args.kind != "auto" else "log",
            command=args.command,
            exit_code=args.exit_code,
            max_lines=args.max_lines,
        )
        _write_cli_result(result, args.report_json)
        return 0
    if args.code_file:
        source = _read_cli_text_file(args.code_file)
        minified = minify_code(source)
        if args.report_json:
            result = HarnessResult(
                success=True,
                stdout=minified,
                metadata={
                    "strategy": "minify-code",
                    "token_usage": compare_token_usage(
                        source,
                        minified,
                        strategy="minify-code",
                        label="python-code",
                    ),
                },
            )
            _write_cli_result(result, True)
        else:
            _safe_stdout_write(minified)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
