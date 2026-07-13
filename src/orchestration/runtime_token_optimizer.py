from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Iterable, MutableMapping
from typing import Any, Callable, Dict, List, Tuple

from src.contracts import WorkflowTaskResult
from src.skills.token_optimizer import (
    estimate_token_count,
    is_contract_sensitive_text,
    required_command_facts,
    summarize_command_output,
)


_DEFAULT_MARGIN_TOKENS = 16
_DEFAULT_MARGIN_RATIO = 0.05
_KNOWN_COMMAND_FAMILIES = {"test", "build"}
_QUALITY_SENSITIVE_KINDS = {
    "contract-sensitive",
    "requirements",
    "review-finding",
    "security",
    "source-of-truth",
}


def build_canonical_model_view(task_results: Iterable[WorkflowTaskResult]) -> List[Dict[str, Any]]:
    """Return the only task representation that may be serialized for the model."""
    return [result.to_dict() for result in task_results]


def serialize_canonical_model_view(task_results: Iterable[WorkflowTaskResult]) -> str:
    """Serialize task results with stable ordering and no side-channel report payload."""
    return json.dumps(
        build_canonical_model_view(task_results),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def hash_command_output_payload(stdout: str, stderr: str) -> str:
    """Hash the exact two-channel output contract used by raw refs and RTK receipts."""
    payload = _serialize_command_output_payload(stdout, stderr).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def optimize_workflow_task_results(
    task_results: List[WorkflowTaskResult],
    metadata: Dict[str, Any] | None = None,
    *,
    raw_store: MutableMapping[str, str] | None = None,
    rtk_adapter: Callable[[Dict[str, Any]], Any] | None = None,
) -> Tuple[List[WorkflowTaskResult], Dict[str, Any]]:
    """Return a canonical model view or exact passthrough.

    Compression is enabled only when the caller explicitly selects the canonical
    model view and provides project/chat/run scope plus either a caller-owned raw
    result contract or an external raw store. The input list remains the raw,
    caller-owned recovery object in caller-owned mode.
    """
    options = dict(metadata or {})
    raw_results = list(task_results)
    baseline = serialize_canonical_model_view(raw_results)
    command_items = list(_iter_command_outputs(raw_results))
    transcript_count = sum(1 for result in raw_results for _ in _iter_transcripts(result.metadata))

    requested_provider = str(options.get("token_optimizer_provider", "kh") or "kh").strip().lower()
    strict_rtk = bool(options.get("token_optimizer_strict", False))

    if requested_provider == "rtk" and strict_rtk:
        strict_candidates = [
            item
            for _, _, item in command_items
            if _command_family(str(item.get("command", ""))) in _KNOWN_COMMAND_FAMILIES
        ]
        if not command_items or (strict_candidates and rtk_adapter is None):
            return raw_results, _no_use_report(
                status="blocked",
                reason_code="rtk_receipt_missing_or_invalid",
                provider="kh",
                provider_reason_code="rtk_strict_requires_runtime_adapter",
            )

    if not command_items:
        has_general_content = transcript_count > 0 or any(bool(result.metadata) for result in raw_results)
        status = "passthrough" if has_general_content else "considered_not_needed"
        reason_code = "unverified_general_content" if has_general_content else "no_optimizable_payload"
        return raw_results, _no_use_report(
            status=status,
            reason_code=reason_code,
            provider="kh",
            provider_reason_code="kh_selected",
        )

    path = _canonical_path(options, raw_store)
    if path is None:
        return raw_results, _no_use_report(
            status="passthrough",
            reason_code="canonical_view_unavailable",
            provider="kh",
            provider_reason_code="canonical_view_unavailable",
        )

    content_kind = str(options.get("token_optimizer_content_kind", "auto") or "auto").strip().lower()
    if content_kind in _QUALITY_SENSITIVE_KINDS:
        return raw_results, _no_use_report(
            status="passthrough",
            reason_code="quality_sensitive_passthrough",
            provider="kh",
            provider_reason_code="kh_quality_passthrough",
        )

    max_lines = _int_option(options, "token_optimizer_max_lines", 40)
    margin_tokens = _int_option(options, "token_optimizer_net_gain_margin_tokens", _DEFAULT_MARGIN_TOKENS)
    margin_ratio = _float_option(options, "token_optimizer_net_gain_margin_ratio", _DEFAULT_MARGIN_RATIO)

    current_results = raw_results
    current_serialized = baseline
    accepted: List[Dict[str, Any]] = []
    decisions: List[Tuple[str, str]] = []
    used_providers: set[str] = set()
    provider_reason_code = "kh_selected"
    provider_receipts: List[Dict[str, Any]] = []
    provider_invocation_receipts: List[Dict[str, Any]] = []
    provider_claims: List[Dict[str, Any]] = []

    for task_index, source, command_output in command_items:
        raw_stdout = str(command_output.get("stdout", ""))
        raw_stderr = str(command_output.get("stderr", ""))
        raw_text = _join_channels(raw_stdout, raw_stderr)
        command = str(command_output.get("command", ""))
        exit_code = _int_value(command_output.get("exit_code", command_output.get("returncode", 0)))
        command_family = _command_family(command)
        claim = _claimed_rtk_provider_data(raw_results[task_index], source, command_output)
        if claim is not None:
            provider_claims.append(claim)

        if _is_binary_or_high_entropy(raw_text):
            decisions.append(("passthrough", "binary_or_high_entropy_passthrough"))
            continue
        if is_contract_sensitive_text(raw_text):
            decisions.append(("passthrough", "contract_sensitive_passthrough"))
            continue
        if command_family not in _KNOWN_COMMAND_FAMILIES:
            decisions.append(("passthrough", "unsupported_command_family"))
            continue

        required_facts, facts_source = _required_facts(command_output, raw_text, command_family, exit_code)
        if not required_facts:
            decisions.append(("passthrough", "required_facts_unavailable"))
            continue
        if any(fact not in raw_text for fact in required_facts):
            decisions.append(("passthrough", "required_fact_not_in_raw_output"))
            continue

        compact_stdout = ""
        compact_stderr = ""
        item_provider = "kh"
        receipt: Dict[str, Any] | None = None

        if requested_provider in {"rtk", "hybrid"} and rtk_adapter is not None:
            rtk_result, invocation_receipt = _invoke_rtk_adapter(
                rtk_adapter,
                path=path,
                task=raw_results[task_index],
                source=source,
                command=command,
                raw_stdout=raw_stdout,
                raw_stderr=raw_stderr,
                exit_code=exit_code,
                required_facts=required_facts,
            )
            provider_invocation_receipts.append(
                {
                    "task_id": raw_results[task_index].task_id,
                    "source": source,
                    "provider": "rtk",
                    "correlation_id": invocation_receipt["correlation_id"],
                    "receipt": invocation_receipt,
                }
            )
            if rtk_result is not None:
                compact_stdout, compact_stderr = rtk_result
                receipt = invocation_receipt
                item_provider = "rtk"
                provider_reason_code = "rtk_runtime_adapter_invoked"
            elif strict_rtk and requested_provider == "rtk":
                decisions.append(("blocked", "rtk_receipt_missing_or_invalid"))
                continue
            else:
                provider_reason_code = "rtk_receipt_missing_fallback_kh"
        elif requested_provider in {"rtk", "hybrid"}:
            provider_reason_code = (
                "rtk_claimed_data_unverified_fallback_kh"
                if claim is not None
                else "rtk_receipt_missing_fallback_kh"
            )

        if item_provider == "kh":
            summary = summarize_command_output(
                command=command,
                stdout=raw_stdout,
                stderr=raw_stderr,
                exit_code=exit_code,
                max_lines=max_lines,
                execution_time=float(command_output.get("execution_time", 0.0) or 0.0),
                required_facts=required_facts,
            )
            if not bool(summary.metadata.get("compression_applied", False)):
                decisions.append(
                    (
                        "passthrough",
                        str(summary.metadata.get("fallback_reason_code") or "command_filter_passthrough"),
                    )
                )
                continue
            compact_stdout = summary.stdout
            compact_stderr = summary.stderr

        compact_text = _join_channels(compact_stdout, compact_stderr)
        if any(fact not in compact_text for fact in required_facts):
            decisions.append(("passthrough", "required_fact_preservation_failed"))
            continue

        raw_ref, raw_payload = _raw_reference(
            path=path,
            task=current_results[task_index],
            source=source,
            stdout=raw_stdout,
            stderr=raw_stderr,
        )
        compact_output = _compact_command_output(
            command_output,
            stdout=compact_stdout,
            stderr=compact_stderr,
            raw_ref=raw_ref,
        )
        candidate_results = _replace_command_output(
            current_results,
            task_index=task_index,
            source=source,
            command_output=compact_output,
        )
        candidate_serialized = serialize_canonical_model_view(candidate_results)
        gain = _canonical_gain(
            before=current_serialized,
            after=candidate_serialized,
            margin_tokens=margin_tokens,
            margin_ratio=margin_ratio,
        )
        if not gain["net_gain_passed"]:
            decisions.append(("considered_not_needed", "canonical_net_gain_below_margin"))
            continue
        if not _persist_raw(path, raw_store, raw_ref["uri"], raw_payload):
            decisions.append(("passthrough", "raw_store_write_failed"))
            continue

        current_results = candidate_results
        current_serialized = candidate_serialized
        used_providers.add(item_provider)
        decisions.append(("used", "positive_canonical_net_gain"))
        accepted.append(
            {
                "task_id": raw_results[task_index].task_id,
                "source": source,
                "provider": item_provider,
                "facts_source": facts_source,
                "required_fact_count": len(required_facts),
                "raw_ref": raw_ref,
            }
        )
        if receipt is not None:
            provider_receipts.append(
                {
                    "task_id": raw_results[task_index].task_id,
                    "source": source,
                    "provider": item_provider,
                    "correlation_id": receipt["correlation_id"],
                    "receipt": receipt,
                }
            )

    if not accepted:
        status, reason_code = _no_use_status(decisions)
        provider = "kh"
        if status == "blocked" and requested_provider == "rtk":
            provider_reason_code = "rtk_receipt_missing_or_invalid"
        return raw_results, _no_use_report(
            status=status,
            reason_code=reason_code,
            provider=provider,
            provider_reason_code=provider_reason_code,
        )

    final_gain = _canonical_gain(
        before=baseline,
        after=current_serialized,
        margin_tokens=0,
        margin_ratio=0.0,
    )
    if not final_gain["net_gain_passed"]:
        return raw_results, _no_use_report(
            status="passthrough",
            reason_code="final_canonical_net_gain_failed",
            provider="kh",
            provider_reason_code="canonical_validation_failed",
        )

    provider = "hybrid" if len(used_providers) > 1 else next(iter(used_providers))
    if provider == "hybrid":
        provider_reason_code = "hybrid_item_providers_verified"
    report: Dict[str, Any] = {
        "status": "used",
        "reason_code": "positive_canonical_net_gain",
        "provider": provider,
        "provider_reason_code": provider_reason_code,
        "token_optimizer_status_reason": "Token optimizer used: canonical model payload reduced.",
        "canonical": final_gain,
        "used_count": len(accepted),
        "raw_refs": [record["raw_ref"] for record in accepted],
        "provider_receipts": provider_receipts,
        "provider_invocation_receipts": provider_invocation_receipts,
        "provider_claims": provider_claims,
    }
    if provider == "rtk" and len(provider_receipts) == 1:
        report["rtk_receipt"] = provider_receipts[0]["receipt"]
    return current_results, report


def _canonical_path(
    options: Dict[str, Any],
    raw_store: MutableMapping[str, str] | None,
) -> Dict[str, str] | None:
    if options.get("token_optimizer_canonical_view") is not True:
        return None
    scope = options.get("token_optimizer_raw_scope")
    if not isinstance(scope, dict):
        return None
    normalized = {key: str(scope.get(key, "")).strip() for key in ("project", "chat", "run")}
    if not all(normalized.values()):
        return None
    owner = "external" if raw_store is not None else str(options.get("token_optimizer_raw_owner", "")).strip()
    if owner not in {"caller", "external"}:
        return None
    return {**normalized, "owner": owner}


def _iter_command_outputs(
    task_results: List[WorkflowTaskResult],
) -> Iterable[Tuple[int, str, Dict[str, Any]]]:
    for task_index, result in enumerate(task_results):
        metadata = result.metadata or {}
        command_output = metadata.get("command_output")
        if isinstance(command_output, dict):
            yield task_index, "command_output", command_output
        command_outputs = metadata.get("command_outputs")
        if isinstance(command_outputs, list):
            for index, item in enumerate(command_outputs):
                if isinstance(item, dict):
                    yield task_index, f"command_outputs[{index}]", item
        if any(key in metadata for key in ("stdout", "stderr")) and metadata.get("command"):
            yield task_index, "metadata", metadata


def _iter_transcripts(metadata: Dict[str, Any]) -> Iterable[str]:
    for key in ("agent_transcript", "subagent_transcript", "transcript"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            yield value
    transcripts = metadata.get("subagent_transcripts")
    if isinstance(transcripts, list):
        for item in transcripts:
            if isinstance(item, str) and item.strip():
                yield item
            elif isinstance(item, dict):
                value = str(item.get("transcript", "") or item.get("content", ""))
                if value.strip():
                    yield value


def _replace_command_output(
    task_results: List[WorkflowTaskResult],
    *,
    task_index: int,
    source: str,
    command_output: Dict[str, Any],
) -> List[WorkflowTaskResult]:
    results = list(task_results)
    result = results[task_index]
    task_metadata = copy.deepcopy(result.metadata)
    if source == "command_output":
        task_metadata["command_output"] = command_output
    elif source == "metadata":
        task_metadata = command_output
    else:
        match = re.fullmatch(r"command_outputs\[(\d+)\]", source)
        if match is None:
            raise ValueError(f"unsupported command output source: {source}")
        task_metadata["command_outputs"][int(match.group(1))] = command_output
    results[task_index] = WorkflowTaskResult(
        task_id=result.task_id,
        file_name=result.file_name,
        role=result.role,
        status=result.status,
        message=result.message,
        metadata=task_metadata,
    )
    return results


def _compact_command_output(
    command_output: Dict[str, Any],
    *,
    stdout: str,
    stderr: str,
    raw_ref: Dict[str, Any],
) -> Dict[str, Any]:
    compact = {
        key: copy.deepcopy(value)
        for key, value in command_output.items()
        if key not in {"stdout", "stderr", "required_facts", "rtk_adapter_receipt", "rtk_compact_output"}
    }
    compact.update({"stdout": stdout, "stderr": stderr, "raw_ref": raw_ref})
    return compact


def _required_facts(
    command_output: Dict[str, Any],
    raw_text: str,
    command_family: str,
    exit_code: int,
) -> Tuple[List[str], str]:
    supplied = command_output.get("required_facts")
    if isinstance(supplied, list):
        facts = list(dict.fromkeys(str(item) for item in supplied if str(item)))
        return facts, "caller"
    return required_command_facts(raw_text, command_family, exit_code), "command-family-failure"


def _invoke_rtk_adapter(
    adapter: Callable[[Dict[str, Any]], Any],
    *,
    path: Dict[str, str],
    task: WorkflowTaskResult,
    source: str,
    command: str,
    raw_stdout: str,
    raw_stderr: str,
    exit_code: int,
    required_facts: List[str],
) -> Tuple[Tuple[str, str] | None, Dict[str, Any]]:
    input_sha256 = hash_command_output_payload(raw_stdout, raw_stderr)
    correlation_seed = "\0".join(
        [path["project"], path["chat"], path["run"], task.task_id, source, input_sha256]
    )
    correlation_id = f"rtk-{hashlib.sha256(correlation_seed.encode('utf-8')).hexdigest()[:32]}"
    receipt: Dict[str, Any] = {
        "adapter": "rtk",
        "adapter_callable": str(
            getattr(adapter, "__qualname__", "") or getattr(adapter, "__name__", "") or type(adapter).__name__
        ),
        "correlation_id": correlation_id,
        "invoked": True,
        "input_sha256": input_sha256,
        "receipt_origin": "runtime",
        "provenance_status": "runtime_invoked_adapter",
        "runtime_invocation_verified": True,
        "provider_authenticity_verified": False,
    }
    request = {
        "correlation_id": correlation_id,
        "task_id": task.task_id,
        "source": source,
        "command": command,
        "stdout": raw_stdout,
        "stderr": raw_stderr,
        "exit_code": exit_code,
        "required_facts": list(required_facts),
    }
    try:
        response = adapter(copy.deepcopy(request))
    except Exception as exc:
        receipt.update({"status": "failed", "error_type": type(exc).__name__})
        return None, receipt
    if not isinstance(response, dict):
        receipt.update({"status": "rejected", "reason_code": "adapter_response_not_mapping"})
        return None, receipt
    compact_stdout = str(response.get("stdout", ""))
    compact_stderr = str(response.get("stderr", ""))
    compact_text = _join_channels(compact_stdout, compact_stderr)
    if any(fact not in compact_text for fact in required_facts):
        receipt.update({"status": "rejected", "reason_code": "required_fact_preservation_failed"})
        return None, receipt
    receipt.update(
        {
            "status": "succeeded",
            "output_sha256": hash_command_output_payload(compact_stdout, compact_stderr),
            "integrity_hashes_correlated": True,
            "cryptographic_authenticity_proven": False,
        }
    )
    return (compact_stdout, compact_stderr), receipt


def _claimed_rtk_provider_data(
    task: WorkflowTaskResult,
    source: str,
    command_output: Dict[str, Any],
) -> Dict[str, Any] | None:
    if "rtk_adapter_receipt" not in command_output and "rtk_compact_output" not in command_output:
        return None
    return {
        "task_id": task.task_id,
        "source": source,
        "provider": "rtk",
        "provenance_status": "claimed_unverified",
        "runtime_invocation_verified": False,
        "provider_authenticity_verified": False,
        "claimed_receipt_present": isinstance(command_output.get("rtk_adapter_receipt"), dict),
        "claimed_compact_output_present": isinstance(command_output.get("rtk_compact_output"), dict),
    }


def _raw_reference(
    *,
    path: Dict[str, str],
    task: WorkflowTaskResult,
    source: str,
    stdout: str,
    stderr: str,
) -> Tuple[Dict[str, Any], str]:
    payload = _serialize_command_output_payload(stdout, stderr)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    scope_digest = hashlib.sha256(
        f"{path['project']}\0{path['chat']}\0{path['run']}".encode("utf-8")
    ).hexdigest()[:16]
    scheme = "caller" if path["owner"] == "caller" else "raw"
    uri = (
        f"{scheme}://{scope_digest}/{_safe_ref_segment(task.task_id)}/"
        f"{_safe_ref_segment(source)}/{digest[:16]}"
    )
    return {
        "uri": uri,
        "sha256": digest,
        "bytes": len(payload.encode("utf-8")),
    }, payload


def _persist_raw(
    path: Dict[str, str],
    raw_store: MutableMapping[str, str] | None,
    uri: str,
    payload: str,
) -> bool:
    if path["owner"] == "caller":
        return True
    if raw_store is None:
        return False
    try:
        raw_store[uri] = payload
    except Exception:
        return False
    return raw_store.get(uri) == payload


def _canonical_gain(
    *,
    before: str,
    after: str,
    margin_tokens: int,
    margin_ratio: float,
) -> Dict[str, Any]:
    before_bytes = len(before.encode("utf-8"))
    after_bytes = len(after.encode("utf-8"))
    before_chars = len(before)
    after_chars = len(after)
    before_tokens = estimate_token_count(before)
    after_tokens = estimate_token_count(after)
    estimated_saved = before_tokens - after_tokens
    required_margin = max(
        max(0, margin_tokens),
        int(math.ceil(before_tokens * max(0.0, margin_ratio))),
    )
    return {
        "estimated_payload_bytes_before": before_bytes,
        "estimated_payload_bytes_after": after_bytes,
        "estimated_payload_bytes_delta": before_bytes - after_bytes,
        "estimated_payload_characters_before": before_chars,
        "estimated_payload_characters_after": after_chars,
        "estimated_payload_characters_delta": before_chars - after_chars,
        "estimated_payload_tokens_before": before_tokens,
        "estimated_payload_tokens_after": after_tokens,
        "estimated_payload_tokens_saved": estimated_saved,
        "estimated_payload_token_savings_ratio": (
            round(estimated_saved / before_tokens, 4) if before_tokens else 0.0
        ),
        "estimated_payload_token_count_method": "deterministic_local_estimate_chars_div_4",
        "estimated_payload_token_count_is_estimate": True,
        "billing_tokens_available": False,
        "billing_counterfactual_available": False,
        "required_margin_tokens": required_margin,
        "net_gain_passed": (
            after_bytes < before_bytes
            and after_chars < before_chars
            and after_tokens < before_tokens
            and estimated_saved >= required_margin
        ),
    }


def _no_use_status(decisions: List[Tuple[str, str]]) -> Tuple[str, str]:
    for preferred in ("blocked", "passthrough", "considered_not_needed"):
        for status, reason_code in decisions:
            if status == preferred:
                return status, reason_code
    return "considered_not_needed", "no_optimizable_payload"


def _no_use_report(
    *,
    status: str,
    reason_code: str,
    provider: str,
    provider_reason_code: str,
) -> Dict[str, Any]:
    report = {
        "status": status,
        "reason_code": reason_code,
        "provider": provider,
        "token_optimizer_status_reason": f"Token optimizer {status}: {reason_code}.",
    }
    if provider_reason_code not in {"", "kh_selected", reason_code}:
        report["provider_reason_code"] = provider_reason_code
    return report


def _command_family(command: str) -> str:
    lowered = str(command or "").lower()
    if any(
        token in lowered
        for token in (
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
        )
    ):
        return "test"
    if any(
        token in lowered
        for token in (
            "msbuild",
            "dotnet build",
            "npm run build",
            "cargo build",
            "go build",
            "mvn package",
            "gradle build",
            "tsc",
            "build ",
        )
    ):
        return "build"
    return "generic"


def _is_binary_or_high_entropy(text: str) -> bool:
    if not text:
        return False
    if "\x00" in text or "\ufffd" in text:
        return True
    control_count = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")
    if control_count / max(1, len(text)) >= 0.01:
        return True
    compact = "".join(text.split())
    if len(compact) < 512:
        return False
    base64ish = sum(char.isalnum() or char in "+/=_-" for char in compact) / len(compact)
    return base64ish >= 0.98 and len(set(compact)) >= 48 and " " not in text[:256]


def _serialize_command_output_payload(stdout: str, stderr: str) -> str:
    return json.dumps(
        {"stderr": str(stderr), "stdout": str(stdout)},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _safe_ref_segment(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-.")
    return normalized[:64] or "unknown"


def _join_channels(stdout: str, stderr: str) -> str:
    if stdout and stderr:
        return f"{stdout}\n{stderr}"
    return stdout or stderr


def _int_option(options: Dict[str, Any], key: str, default: int) -> int:
    return _int_value(options.get(key, default), default)


def _float_option(options: Dict[str, Any], key: str, default: float) -> float:
    try:
        return float(options.get(key, default))
    except (TypeError, ValueError):
        return default


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
