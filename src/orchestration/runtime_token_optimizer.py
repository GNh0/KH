from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from src.contracts import WorkflowTaskResult
from src.orchestration.token_optimizer_provider import resolve_token_optimizer_provider
from src.skills.token_optimizer import (
    aggregate_token_usage_stats,
    estimate_token_count,
    summarize_agent_transcript,
    summarize_command_output,
)


def optimize_workflow_task_results(
    task_results: List[WorkflowTaskResult],
    metadata: Dict[str, Any] | None = None,
) -> Tuple[List[WorkflowTaskResult], Dict[str, Any]]:
    """Attach quality-preserving token optimization evidence to workflow results.

    Raw task metadata is preserved. Optimized display text and token usage
    statistics are written under each task's ``metadata.token_optimizer``.
    """
    metadata = metadata or {}
    provider = resolve_token_optimizer_provider(
        token_optimizer_provider=metadata.get("token_optimizer_provider", "kh"),
        command=metadata.get("token_optimizer_command", "workflow dispatch"),
        content_kind=metadata.get("token_optimizer_content_kind", "auto"),
        rtk_available=bool(metadata.get("rtk_available", False)),
        strict=bool(metadata.get("token_optimizer_strict", False)),
    )
    provider_dict = provider.to_dict()
    if provider.status == "blocked":
        return list(task_results), _report(
            status="blocked",
            provider=provider_dict,
            records=[],
            skipped_count=0,
            blocked_reason=provider.rationale,
        )
    if provider.provider == "passthrough":
        return list(task_results), _report(
            status="passthrough",
            provider=provider_dict,
            records=[],
            skipped_count=0,
            passthrough_reason=provider.rationale,
        )

    min_tokens = _int_metadata(metadata, "token_optimizer_min_tokens", 1_000)
    max_lines = _int_metadata(metadata, "token_optimizer_max_lines", 40)
    transcript_max_lines = _int_metadata(metadata, "token_optimizer_transcript_max_lines", 160)
    optimized_results: List[WorkflowTaskResult] = []
    all_records: List[Dict[str, Any]] = []
    skipped_count = 0

    for result in task_results:
        task_records: List[Dict[str, Any]] = []
        for source, command_output in _iter_command_outputs(result.metadata):
            raw_text = _join_channels(
                str(command_output.get("stdout", "")),
                str(command_output.get("stderr", "")),
            )
            if estimate_token_count(raw_text) < min_tokens:
                skipped_count += 1
                continue
            summary = summarize_command_output(
                command=str(command_output.get("command", "")),
                stdout=str(command_output.get("stdout", "")),
                stderr=str(command_output.get("stderr", "")),
                exit_code=_int_value(command_output.get("exit_code", command_output.get("returncode", 0))),
                max_lines=max_lines,
                execution_time=float(command_output.get("execution_time", 0.0) or 0.0),
            )
            record = {
                "kind": "command-output",
                "source": source,
                "task_id": result.task_id,
                "file_name": result.file_name,
                "role": result.role,
                "status": _record_status(summary.metadata),
                "command": summary.metadata.get("command", ""),
                "command_family": summary.metadata.get("command_family", "generic"),
                "exit_code": summary.exit_code,
                "stdout": summary.stdout,
                "stderr": summary.stderr,
                "raw_bytes": summary.metadata.get("raw_bytes", 0),
                "filtered_bytes": summary.metadata.get("filtered_bytes", 0),
                "raw_lines": summary.metadata.get("raw_lines", 0),
                "filtered_lines": summary.metadata.get("filtered_lines", 0),
                "fallback_reason": summary.metadata.get("fallback_reason", ""),
                "token_usage": dict(summary.metadata.get("token_usage", {})),
            }
            task_records.append(record)
            all_records.append(record)

        for source, transcript in _iter_transcripts(result.metadata):
            if estimate_token_count(transcript) < min_tokens:
                skipped_count += 1
                continue
            summary = summarize_agent_transcript(
                transcript,
                max_lines=transcript_max_lines,
                label=f"{result.role}:{source}",
            )
            record = {
                "kind": "agent-transcript",
                "source": source,
                "task_id": result.task_id,
                "file_name": result.file_name,
                "role": result.role,
                "status": _record_status(summary.metadata),
                "transcript": summary.stdout,
                "raw_bytes": summary.metadata.get("raw_bytes", 0),
                "filtered_bytes": summary.metadata.get("filtered_bytes", 0),
                "raw_lines": summary.metadata.get("raw_lines", 0),
                "filtered_lines": summary.metadata.get("filtered_lines", 0),
                "fallback_reason": summary.metadata.get("fallback_reason", ""),
                "token_usage": dict(summary.metadata.get("token_usage", {})),
            }
            task_records.append(record)
            all_records.append(record)

        if task_records:
            optimized_results.append(_with_token_optimizer_metadata(result, provider_dict, task_records))
        else:
            optimized_results.append(result)

    return optimized_results, _report(
        status=_workflow_status(all_records, skipped_count),
        provider={**provider_dict, "token_optimizer_min_tokens": min_tokens},
        records=all_records,
        skipped_count=skipped_count,
    )


def _with_token_optimizer_metadata(
    result: WorkflowTaskResult,
    provider: Dict[str, Any],
    records: List[Dict[str, Any]],
) -> WorkflowTaskResult:
    metadata = dict(result.metadata)
    status = _workflow_status(records, skipped_count=0)
    reason = _status_reason(status=status, provider=provider, records=records, skipped_count=0)
    metadata["token_optimizer"] = {
        "status": status,
        "token_optimizer_status_reason": reason,
        "provider": provider,
        "summary": aggregate_token_usage_stats([record.get("token_usage", {}) for record in records]),
        "rtk_style_stats": _rtk_style_stats(records),
        "records": records,
        "evidence": ["runtime_token_optimization"],
    }
    if status != "used":
        metadata["token_optimizer"]["not_used_reason"] = reason
    return WorkflowTaskResult(
        task_id=result.task_id,
        file_name=result.file_name,
        role=result.role,
        status=result.status,
        message=result.message,
        metadata=metadata,
    )


def _report(
    status: str,
    provider: Dict[str, Any],
    records: List[Dict[str, Any]],
    skipped_count: int,
    blocked_reason: str = "",
    passthrough_reason: str = "",
) -> Dict[str, Any]:
    public_records = [_public_record(record) for record in records]
    reason = _status_reason(
        status=status,
        provider=provider,
        records=records,
        skipped_count=skipped_count,
        blocked_reason=blocked_reason,
        passthrough_reason=passthrough_reason,
    )
    report = {
        "status": status,
        "token_optimizer_status_reason": reason,
        "provider": provider,
        "summary": aggregate_token_usage_stats([record.get("token_usage", {}) for record in records]),
        "rtk_style_stats": _rtk_style_stats(records),
        "records": public_records,
        "skipped_small_output_count": skipped_count,
        "blocked_reason": blocked_reason,
        "passthrough_reason": passthrough_reason,
        "evidence": ["runtime_token_optimization"] if status in {"used", "passthrough", "blocked"} else [],
    }
    if status != "used":
        report["not_used_reason"] = reason
    if status == "used":
        report["evidence"].append("token_usage_stats")
    return report


def _status_reason(
    *,
    status: str,
    provider: Dict[str, Any],
    records: List[Dict[str, Any]],
    skipped_count: int,
    blocked_reason: str = "",
    passthrough_reason: str = "",
) -> str:
    if status == "used":
        return "Token optimizer used; optimizer-local before/after telemetry is available."
    if status == "blocked":
        reason = blocked_reason or str(provider.get("rationale", ""))
        return _join_reason("Token optimizer not used because optimization was blocked", reason)
    if status == "passthrough":
        reason = passthrough_reason or _first_record_reason(records) or str(provider.get("rationale", ""))
        return _join_reason("Token optimizer not used because content was passed through unchanged", reason)
    if skipped_count:
        threshold = provider.get("min_tokens") or provider.get("token_optimizer_min_tokens")
        if threshold:
            return (
                "Token optimizer not used because all candidate command outputs or transcripts "
                f"were below the configured threshold ({threshold} tokens)."
            )
        return (
            "Token optimizer not used because all candidate command outputs or transcripts "
            "were below the configured threshold."
        )
    return "Token optimizer not used because no optimizable command output or transcript was found."


def _first_record_reason(records: List[Dict[str, Any]]) -> str:
    for record in records:
        reason = str(record.get("passthrough_reason") or record.get("fallback_reason") or "")
        if reason:
            return reason
    return ""


def _join_reason(prefix: str, reason: str) -> str:
    clean = str(reason or "").strip().rstrip(".")
    return f"{prefix}: {clean}." if clean else f"{prefix}."


def _rtk_style_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_family: Dict[str, Dict[str, Any]] = {}
    for record in records:
        if record.get("kind") != "command-output":
            continue
        family = str(record.get("command_family") or "generic")
        token_usage = dict(record.get("token_usage", {}))
        bucket = by_family.setdefault(
            family,
            {
                "case_count": 0,
                "without_token_optimizer": 0,
                "with_token_optimizer": 0,
                "estimated_tokens_saved": 0,
                "token_savings_ratio": 0.0,
                "actual_usage_scope": str(token_usage.get("actual_usage_scope", "actual_optimizer_input_output_payload")),
                "token_count_method": str(
                    token_usage.get("token_count_method", "deterministic_local_estimate_chars_div_4")
                ),
                "token_count_is_estimate": bool(token_usage.get("token_count_is_estimate", True)),
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
            },
        )
        bucket["case_count"] += 1
        bucket["without_token_optimizer"] += int(token_usage.get("without_token_optimizer", 0))
        bucket["with_token_optimizer"] += int(token_usage.get("with_token_optimizer", 0))
        bucket["estimated_tokens_saved"] += int(token_usage.get("estimated_tokens_saved", 0))
        bucket["actual_without_token_optimizer"] += int(token_usage.get("actual_without_token_optimizer", 0))
        bucket["actual_with_token_optimizer"] += int(token_usage.get("actual_with_token_optimizer", 0))
        bucket["actual_tokens_saved"] += int(token_usage.get("actual_tokens_saved", 0))
        bucket["actual_without_token_optimizer_bytes"] += int(
            token_usage.get("actual_without_token_optimizer_bytes", 0)
        )
        bucket["actual_with_token_optimizer_bytes"] += int(token_usage.get("actual_with_token_optimizer_bytes", 0))
        bucket["actual_bytes_saved"] += int(token_usage.get("actual_bytes_saved", 0))
        bucket["actual_without_token_optimizer_chars"] += int(
            token_usage.get("actual_without_token_optimizer_chars", 0)
        )
        bucket["actual_with_token_optimizer_chars"] += int(token_usage.get("actual_with_token_optimizer_chars", 0))
        bucket["actual_chars_saved"] += int(token_usage.get("actual_chars_saved", 0))
    for bucket in by_family.values():
        raw = bucket["without_token_optimizer"]
        saved = bucket["estimated_tokens_saved"]
        bucket["token_savings_ratio"] = round(saved / raw, 4) if raw else 0.0
        actual_raw = bucket["actual_without_token_optimizer"]
        actual_saved = bucket["actual_tokens_saved"]
        bucket["actual_token_savings_ratio"] = round(actual_saved / actual_raw, 4) if actual_raw else 0.0
        actual_raw_bytes = bucket["actual_without_token_optimizer_bytes"]
        actual_saved_bytes = bucket["actual_bytes_saved"]
        bucket["actual_byte_savings_ratio"] = round(actual_saved_bytes / actual_raw_bytes, 4) if actual_raw_bytes else 0.0
        actual_raw_chars = bucket["actual_without_token_optimizer_chars"]
        actual_saved_chars = bucket["actual_chars_saved"]
        bucket["actual_char_savings_ratio"] = round(actual_saved_chars / actual_raw_chars, 4) if actual_raw_chars else 0.0
    return {
        "style": "rtk-compatible-command-family-stats",
        "provider": "kh",
        "by_command_family": by_family,
        "note": "KH runtime emits RTK-style family savings without requiring RTK as a dependency.",
    }


def _workflow_status(records: List[Dict[str, Any]], skipped_count: int) -> str:
    if any(record.get("status") == "used" for record in records):
        return "used"
    if records:
        return "passthrough"
    if skipped_count:
        return "considered_not_needed"
    return "considered_not_needed"


def _record_status(metadata: Dict[str, Any]) -> str:
    token_usage = dict(metadata.get("token_usage", {}))
    if int(token_usage.get("actual_tokens_saved", token_usage.get("estimated_tokens_saved", 0))) > 0:
        return "used"
    if metadata.get("passthrough_reason") or metadata.get("fallback_reason"):
        return "passthrough"
    return "considered_not_needed"


def _iter_command_outputs(metadata: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    metadata = metadata or {}
    command_output = metadata.get("command_output")
    if isinstance(command_output, dict):
        yield "command_output", command_output
    command_outputs = metadata.get("command_outputs")
    if isinstance(command_outputs, list):
        for index, item in enumerate(command_outputs, start=1):
            if isinstance(item, dict):
                yield f"command_outputs[{index}]", item
    if any(key in metadata for key in ["stdout", "stderr"]) and metadata.get("command"):
        yield "metadata", metadata


def _iter_transcripts(metadata: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    metadata = metadata or {}
    for key in ["agent_transcript", "subagent_transcript", "transcript"]:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            yield key, value
    transcripts = metadata.get("subagent_transcripts")
    if isinstance(transcripts, list):
        for index, item in enumerate(transcripts, start=1):
            if isinstance(item, str) and item.strip():
                yield f"subagent_transcripts[{index}]", item
            elif isinstance(item, dict):
                text = str(item.get("transcript", "") or item.get("content", ""))
                if text.strip():
                    yield f"subagent_transcripts[{index}]", text


def _public_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"stdout", "stderr", "transcript"}
    }


def _join_channels(stdout: str, stderr: str) -> str:
    if stdout and stderr:
        return f"{stdout}\n{stderr}"
    return stdout or stderr


def _int_metadata(metadata: Dict[str, Any], key: str, default: int) -> int:
    return _int_value(metadata.get(key, default), default=default)


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
