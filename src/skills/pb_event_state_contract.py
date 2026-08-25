"""Artifact-bound PB event/state parity contract.

This module compares a PB event graph with the graph used by the generated C#
screen.  The graph is read from the bound artifacts, rather than trusted from
caller-supplied ``status`` or ``verified`` fields.  It is intentionally generic:
the graph controls its own event names and transition vocabulary.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.contracts import HarnessResult


CONTRACT_ID = "pb-event-state-contract"
SCHEMA_VERSION = 1
MAX_ARTIFACT_BYTES = 32 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024
SHA256_RE = re.compile(r"^(?:sha256:)?[0-9a-fA-F]{64}$")

ISSUE_ARTIFACT_INVALID = "pb_event_state_artifact_invalid"
ISSUE_ARTIFACT_UNREADABLE = "pb_event_state_artifact_unreadable"
ISSUE_ARTIFACT_SHA256_INVALID = "pb_event_state_artifact_sha256_invalid"
ISSUE_ARTIFACT_SHA256_MISMATCH = "pb_event_state_artifact_sha256_mismatch"
ISSUE_ARTIFACT_SOURCE_MISMATCH = "pb_event_state_artifact_source_mismatch"
ISSUE_GRAPH_SHA256_INVALID = "pb_event_state_graph_sha256_invalid"
ISSUE_GRAPH_SHA256_MISMATCH = "pb_event_state_graph_sha256_mismatch"
ISSUE_GRAPH_JSON_INVALID = "pb_event_state_graph_json_invalid"
ISSUE_GRAPH_INPUT_MISMATCH = "pb_event_state_graph_input_mismatch"
ISSUE_NODE_DUPLICATE = "pb_event_state_node_duplicate"
ISSUE_EDGE_DUPLICATE = "pb_event_state_edge_duplicate"
ISSUE_NODE_OMITTED = "pb_event_state_node_omitted"
ISSUE_NODE_INVENTED = "pb_event_state_node_invented"
ISSUE_EDGE_OMITTED = "pb_event_state_edge_omitted"
ISSUE_EDGE_INVENTED = "pb_event_state_edge_invented"
ISSUE_ORDERING_DRIFT = "pb_event_state_ordering_drift"
ISSUE_TIMING_DRIFT = "pb_event_state_timing_drift"
ISSUE_COMMAND_DRIFT = "pb_event_state_command_drift"
ISSUE_PRECONDITION_DRIFT = "pb_event_state_precondition_drift"
ISSUE_STATE_MUTATION_DRIFT = "pb_event_state_state_mutation_drift"
ISSUE_CALL_DRIFT = "pb_event_state_call_drift"
ISSUE_SIDE_EFFECT_DRIFT = "pb_event_state_side_effect_drift"
ISSUE_GRAPH_MISMATCH = "pb_event_state_graph_mismatch"

_GRAPH_META_KEYS = {"artifact_sha256", "artifact_path", "graph_sha256"}


def _sha(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _norm_sha(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw.startswith("sha256:") else ("sha256:" + raw if raw else "")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "severity": "error", "message": message, **details}


def _result(success: bool, issues: list[dict[str, Any]], **metadata: Any) -> HarnessResult:
    payload = {
        "contract_id": CONTRACT_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if success else "blocked",
        "issues": list(issues),
        **metadata,
    }
    payload["receipt_sha256"] = _sha(_canonical(payload).encode("utf-8"))
    return HarnessResult(
        success=success,
        stdout=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        stderr="" if success else "PB event/state contract validation failed.",
        exit_code=0 if success else 1,
        metadata=payload,
    )


def _read_bounded(path_value: Any) -> tuple[Path, bytes, str]:
    path = Path(str(path_value or ""))
    if not path.is_absolute():
        raise ValueError("artifact path must be absolute")
    resolved = path.resolve(strict=True)
    before = resolved.stat()
    if not resolved.is_file():
        raise ValueError("artifact path must identify a regular file")
    if before.st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact exceeds bounded read limit")
    digest = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    with resolved.open("rb") as stream:
        while True:
            chunk = stream.read(READ_CHUNK_BYTES)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ARTIFACT_BYTES:
                raise ValueError("artifact exceeds bounded read limit")
            digest.update(chunk)
            chunks.append(chunk)
    after = resolved.stat()
    if total != before.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("artifact changed during bounded read")
    return resolved, b"".join(chunks), "sha256:" + digest.hexdigest()


def _graph_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    source = value.get("graph") if isinstance(value.get("graph"), Mapping) else value
    if not isinstance(source, Mapping):
        raise ValueError("graph must be an object")
    return dict(source)


def _graph_without_metadata(graph: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in graph.items() if key not in _GRAPH_META_KEYS}


def _extract_bound_graph(
    role: str,
    candidate: Mapping[str, Any] | None,
    artifact: Mapping[str, Any] | None,
    issues: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not isinstance(artifact, Mapping):
        issues.append(_issue(ISSUE_ARTIFACT_INVALID, f"{role} requires an artifact binding.", role=role))
        return None
    path = str(artifact.get("path") or artifact.get("source_path") or "")
    expected_sha = _norm_sha(artifact.get("sha256") or artifact.get("source_sha256"))
    expected_graph_sha = _norm_sha(artifact.get("graph_sha256") or artifact.get("graph_sha"))
    if not path or not os.path.isabs(path):
        issues.append(_issue(ISSUE_ARTIFACT_INVALID, f"{role} artifact path must be absolute.", role=role))
    if not SHA256_RE.fullmatch(str(artifact.get("sha256") or artifact.get("source_sha256") or "")):
        issues.append(_issue(ISSUE_ARTIFACT_SHA256_INVALID, f"{role} artifact requires a complete SHA-256.", role=role))
    if not SHA256_RE.fullmatch(str(artifact.get("graph_sha256") or artifact.get("graph_sha") or "")):
        issues.append(_issue(ISSUE_GRAPH_SHA256_INVALID, f"{role} artifact requires a complete graph SHA-256.", role=role))
    try:
        resolved, raw, actual_sha = _read_bounded(path)
    except (OSError, ValueError) as exc:
        issues.append(_issue(ISSUE_ARTIFACT_UNREADABLE, f"{role} artifact could not be read.", role=role, error=str(exc)))
        return None
    if actual_sha != expected_sha:
        issues.append(_issue(ISSUE_ARTIFACT_SHA256_MISMATCH, f"{role} artifact bytes do not match its SHA-256.", role=role, expected=expected_sha, actual=actual_sha))
    supplied = artifact.get("source") if "source" in artifact else artifact.get("source_text")
    if supplied is not None and str(supplied).encode("utf-8") != raw:
        issues.append(_issue(ISSUE_ARTIFACT_SOURCE_MISMATCH, f"{role} supplied source differs from artifact bytes.", role=role))
    try:
        decoded = raw.decode("utf-8-sig")
        parsed = json.loads(decoded)
        bound = _graph_payload(parsed)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        issues.append(_issue(ISSUE_GRAPH_JSON_INVALID, f"{role} artifact must contain a JSON event graph.", role=role, error=type(exc).__name__))
        return None
    if not isinstance(bound.get("nodes"), list) or not isinstance(bound.get("edges"), list):
        issues.append(_issue(ISSUE_GRAPH_JSON_INVALID, f"{role} graph requires nodes and edges arrays.", role=role))
        return None
    actual_graph_sha = _sha(_canonical(_graph_without_metadata(bound)).encode("utf-8"))
    if actual_graph_sha != expected_graph_sha:
        issues.append(_issue(ISSUE_GRAPH_SHA256_MISMATCH, f"{role} graph does not match its declared graph SHA-256.", role=role, expected=expected_graph_sha, actual=actual_graph_sha))
    if candidate is not None:
        try:
            candidate_graph = _graph_payload(candidate)
            if _canonical(_graph_without_metadata(candidate_graph)) != _canonical(_graph_without_metadata(bound)):
                issues.append(_issue(ISSUE_GRAPH_INPUT_MISMATCH, f"Caller graph for {role} differs from the artifact-bound graph.", role=role))
        except (TypeError, ValueError) as exc:
            issues.append(_issue(ISSUE_GRAPH_JSON_INVALID, f"Caller graph for {role} is invalid.", role=role, error=str(exc)))
    return bound


def _node_key(node: Mapping[str, Any]) -> str:
    return str(node.get("id") or "").strip()


def _edge_key(edge: Mapping[str, Any]) -> str:
    if str(edge.get("id") or "").strip():
        return "id:" + str(edge["id"]).strip()
    return _canonical({key: edge.get(key) for key in ("source", "from", "target", "to", "kind")})


def _validate_graph_shape(graph: Mapping[str, Any], role: str, issues: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    node_ids: list[str] = []
    edge_ids: list[str] = []
    seen_nodes: set[str] = set()
    seen_edges: set[str] = set()
    for index, raw in enumerate(graph.get("nodes", [])):
        if not isinstance(raw, Mapping) or not _node_key(raw):
            issues.append(_issue(ISSUE_GRAPH_JSON_INVALID, f"{role} node {index} requires a non-empty id.", role=role, index=index))
            continue
        key = _node_key(raw)
        node_ids.append(key)
        if key in seen_nodes:
            issues.append(_issue(ISSUE_NODE_DUPLICATE, f"{role} contains duplicate node {key}.", role=role, node_id=key))
        seen_nodes.add(key)
    for index, raw in enumerate(graph.get("edges", [])):
        if not isinstance(raw, Mapping):
            issues.append(_issue(ISSUE_GRAPH_JSON_INVALID, f"{role} edge {index} must be an object.", role=role, index=index))
            continue
        key = _edge_key(raw)
        if key == _canonical({"source": None, "from": None, "target": None, "to": None, "kind": None}):
            issues.append(_issue(ISSUE_GRAPH_JSON_INVALID, f"{role} edge {index} requires endpoints or an id.", role=role, index=index))
        edge_ids.append(key)
        if key in seen_edges:
            issues.append(_issue(ISSUE_EDGE_DUPLICATE, f"{role} contains duplicate edge {key}.", role=role, edge=key))
        seen_edges.add(key)
    return node_ids, edge_ids


def _compare_graphs(pb: Mapping[str, Any], csharp: Mapping[str, Any], issues: list[dict[str, Any]]) -> None:
    pb_node_ids, pb_edge_ids = _validate_graph_shape(pb, "pb", issues)
    cs_node_ids, cs_edge_ids = _validate_graph_shape(csharp, "csharp", issues)
    for node_id in sorted(set(pb_node_ids) - set(cs_node_ids)):
        issues.append(_issue(ISSUE_NODE_OMITTED, f"C# omits PB node {node_id}.", node_id=node_id))
    for node_id in sorted(set(cs_node_ids) - set(pb_node_ids)):
        issues.append(_issue(ISSUE_NODE_INVENTED, f"C# invents node {node_id}.", node_id=node_id))
    for edge_id in sorted(set(pb_edge_ids) - set(cs_edge_ids)):
        issues.append(_issue(ISSUE_EDGE_OMITTED, f"C# omits PB edge {edge_id}.", edge=edge_id))
    for edge_id in sorted(set(cs_edge_ids) - set(pb_edge_ids)):
        issues.append(_issue(ISSUE_EDGE_INVENTED, f"C# invents edge {edge_id}.", edge=edge_id))
    if pb_node_ids != cs_node_ids or pb_edge_ids != cs_edge_ids:
        issues.append(_issue(ISSUE_ORDERING_DRIFT, "Event graph node or edge order differs."))
    pb_by_id = {_node_key(node): node for node in pb.get("nodes", []) if isinstance(node, Mapping) and _node_key(node)}
    cs_by_id = {_node_key(node): node for node in csharp.get("nodes", []) if isinstance(node, Mapping) and _node_key(node)}
    field_issues = {
        "commands": ISSUE_COMMAND_DRIFT,
        "preconditions": ISSUE_PRECONDITION_DRIFT,
        "state_mutations": ISSUE_STATE_MUTATION_DRIFT,
        "calls": ISSUE_CALL_DRIFT,
        "side_effects": ISSUE_SIDE_EFFECT_DRIFT,
        "timing": ISSUE_TIMING_DRIFT,
    }
    for node_id in sorted(set(pb_by_id) & set(cs_by_id)):
        left, right = pb_by_id[node_id], cs_by_id[node_id]
        if left.get("order") != right.get("order") or list(pb_by_id).index(node_id) != list(cs_by_id).index(node_id):
            issues.append(_issue(ISSUE_ORDERING_DRIFT, f"Node {node_id} has ordering drift.", node_id=node_id))
        for field, code in field_issues.items():
            if _canonical(left.get(field, [] if field != "timing" else {})) != _canonical(right.get(field, [] if field != "timing" else {})):
                issues.append(_issue(code, f"Node {node_id} has {field} drift.", node_id=node_id, field=field))
        if _canonical(left) != _canonical(right):
            issues.append(_issue(ISSUE_GRAPH_MISMATCH, f"Node {node_id} differs between PB and C# graphs.", node_id=node_id))
    if _canonical(pb.get("edges", [])) != _canonical(csharp.get("edges", [])):
        issues.append(_issue(ISSUE_TIMING_DRIFT, "Event graph edge timing or transition metadata differs."))
    if _canonical(_graph_without_metadata(pb)) != _canonical(_graph_without_metadata(csharp)):
        issues.append(_issue(ISSUE_GRAPH_MISMATCH, "PB and C# event graphs are not semantically identical."))


def validate_pb_event_state_contract(
    pb_graph: Mapping[str, Any] | None = None,
    csharp_graph: Mapping[str, Any] | None = None,
    *,
    pb_artifact: Mapping[str, Any] | None = None,
    csharp_artifact: Mapping[str, Any] | None = None,
    artifact_bindings: Mapping[str, Mapping[str, Any]] | None = None,
    **aliases: Any,
) -> HarnessResult:
    """Validate generic ordered PB/C# event-state graphs.

    Artifacts must be JSON files containing ``nodes`` and ``edges`` (or a
    ``graph`` object), and must declare both their file ``sha256`` and the
    SHA-256 of the canonical graph payload in ``graph_sha256``.  Caller graph
    mappings are only cross-checks; the artifact readback is authoritative.
    """
    if pb_graph is None:
        pb_graph = aliases.get("pb_event_graph")
    if csharp_graph is None:
        csharp_graph = aliases.get("csharp_event_graph")
    if artifact_bindings:
        pb_artifact = pb_artifact or artifact_bindings.get("pb") or artifact_bindings.get("powerbuilder")
        csharp_artifact = csharp_artifact or artifact_bindings.get("csharp")
    pb_artifact = pb_artifact or aliases.get("pb_source_artifact")
    csharp_artifact = csharp_artifact or aliases.get("csharp_source_artifact")
    issues: list[dict[str, Any]] = []
    pb_bound = _extract_bound_graph("pb", pb_graph, pb_artifact, issues)
    cs_bound = _extract_bound_graph("csharp", csharp_graph, csharp_artifact, issues)
    if pb_bound is not None and cs_bound is not None:
        _compare_graphs(pb_bound, cs_bound, issues)
    issues.sort(key=lambda item: (str(item.get("code")), _canonical(item)))
    return _result(
        not issues,
        issues,
        verification_scope="artifact_bound_static_event_graph",
        actual_runtime_event_execution_observed=False,
        artifact_bindings={
            "pb": {"path": str((pb_artifact or {}).get("path") or (pb_artifact or {}).get("source_path") or "")},
            "csharp": {"path": str((csharp_artifact or {}).get("path") or (csharp_artifact or {}).get("source_path") or "")},
        },
    )


def verify_pb_event_state_contract(**kwargs: Any) -> HarnessResult:
    """Compatibility alias using the repository verifier naming convention."""

    return validate_pb_event_state_contract(**kwargs)


__all__ = [
    "validate_pb_event_state_contract",
    "verify_pb_event_state_contract",
    "MAX_ARTIFACT_BYTES",
]
