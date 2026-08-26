from __future__ import annotations

import argparse
import ast
from array import array
from collections import deque
from collections.abc import Iterator, Mapping as MappingABC, Sequence as SequenceABC
from contextvars import ContextVar
from datetime import datetime
import hashlib
from itertools import islice
import json
import os
import re
import shlex
import sqlite3
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Set

from src.orchestration.goal_ledger import GoalLedger
from src.orchestration.plugin_composition import looks_like_sql_output_request
from src.orchestration.request_act_parser import parse_request_act
from src.orchestration.request_classifier import classify_request
from src.orchestration.session_postmortem import (
    PostmortemEventFeatures,
    analyze_codex_session_jsonl,
    extract_postmortem_event_features,
)
from src.skills.sql_formatting_provider import (
    DuplicateJsonKeyError,
    SqlFormattingCliArtifactError,
    _successful_sql_cli_input_errors,
    load_json_without_duplicate_keys,
    load_sql_formatting_cli_artifacts,
    sql_provider_selection_sha256,
    validate_sql_provider_selection_runtime_receipt,
    validate_sql_formatting_cli_runtime_receipt,
)
from src.skills.uaf_skill_catalog import collect_packaged_skills


STATUS_RANK = {
    "absent": 0,
    "claimed_unverified": 1,
    "mentioned": 1,
    "inspected": 2,
    "considered": 3,
    "procedural": 4,
    "applied": 5,
}

PASSIVE_REFERENCE_PREFIX = "__kh_passive_reference__ "
SQL_ANSWER_PATTERN = re.compile(
    r"\b(?:SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE|CREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE)\b[\s\S]{0,400}\b(?:FROM|WHERE|JOIN|SET|VALUES|ORDER\s+BY)\b",
    re.IGNORECASE,
)

RUNTIME_MARKERS = {
    "always-on-front-door": [
        "always-on-front-door",
        "kh_front_door",
        "src.orchestration.kh_front_door",
        "front_door_status",
        "runtime_applied_skills",
    ],
    "automatic-intake-harness": [
        "automatic-intake-harness",
        "kh_front_door",
        "src.orchestration.kh_front_door",
        "front_door_status",
    ],
    "token-optimizer": [
        "src.skills.token_optimizer",
        "src.orchestration.runtime_token_optimizer",
        "summarize_command_output",
        "optimize_context_content",
        "summarize_agent_transcript",
        "runtime_token_optimization",
        "estimated_tokens_saved",
        "estimated_payload_tokens_saved",
        "host_actual_tokens_used",
        "host_actual_token_evidence",
    ],
    "memory-state-harness": [
        "MemoryStore",
        "src.orchestration.memory_store",
        "src.orchestration.runtime_memory",
        "memory_context",
        "memory_candidates",
        "memory_candidates_recorded",
    ],
    "workflow-usability-harness": [
        "workflow_usability_auto",
        "apply_workflow_usability_runtime",
        "progress_panel",
        "session_start_context",
        "compound_handoff",
    ],
    "development-lifecycle-harness": [
        "development_lifecycle",
        "src.orchestration.development_progress",
        "validate_development_progress",
        "progress.json",
        "tdd_red_green",
        "development lifecycle applied",
    ],
    "worktree-isolation-harness": [
        "worktree-isolation-harness",
        "workspace_strategy",
        "project-local-worktree",
        "host-worktree",
        ".worktrees",
    ],
    "plan-execution-harness": [
        "plan-execution-harness",
        "progress.json",
        "active task",
        "next_task",
        "task_status",
    ],
    "systematic-debugging-harness": [
        "systematic-debugging-harness",
        "systematic_debugging",
        "debug_status",
        "regression evidence",
    ],
    "goal-state-harness": [
        "GoalState",
        "goal_ledger",
        "create_goal",
        "update_goal",
        "thread_goal_updated",
        "current_goal.json",
        "goal_state applied",
    ],
    "compound-engineering-harness": [
        "CompoundCapture",
        "compound_handoff",
        "compound_capture",
        "progress_compound_bridge",
    ],
    "workflow-skill-distiller": [
        "workflow-skill-distiller",
        "skill_candidates",
        "distilled skill",
    ],
    "subagent-review-pipeline": [
        "subagent_strategy",
        "spec-reviewer",
        "code-quality-reviewer",
        "WorkflowTaskResult",
    ],
    "role-execution-audit-harness": [
        "role_execution_audit",
        "audit_role_execution",
        "role execution audited",
    ],
    "parallel-orchestration-harness": [
        "parallel_wave_count",
        "parallel_strategy_decision",
        "parallel_strategy",
        "fan-out",
        "fan-in",
    ],
    "quality-gates-harness": [
        "tdd_red_green",
        "quality_gate",
        "quality_gates",
    ],
    "qa-gate-harness": [
        "qa_gate",
        "qa_evidence",
        "browser_qa_checks",
        "manual_test_mapping",
    ],
    "verification-before-completion-harness": [
        "verification-before-completion-harness",
        "fresh verification",
        "verification_status",
        "completion_claim",
        "verification_claim_guard",
    ],
    "branch-finishing-harness": [
        "branch-finishing-harness",
        "branch_finish_status",
        "commit_sha",
        "pr-ready",
    ],
    "review-gate-harness": [
        "review_gate",
        "review_status",
        "review_gate applied",
    ],
    "command-output-harness": [
        "summarize_command_output",
        "compression_policy",
        "command_output_harness",
        "tokens saved",
        "preserved_fact",
    ],
    "harness-evaluator": [
        "harness_evaluator",
        "src.harness.evaluator",
        "HarnessResult",
    ],
    "guard-policy-harness": [
        "guard_policy",
        "guard_evidence",
        "destructive-command",
        "permission gate",
        "edit boundary",
    ],
    "snapshot-state-harness": [
        "SnapshotManager",
        "snapshot_state",
        "rollback",
        "snapshot manifest",
    ],
    "request-complexity-router": [
        "request_complexity",
        "classify_request",
        "request classification",
    ],
    "plugin-composition-policy": [
        "plugin_composition",
        "compose_plugin_route",
        "plugin-composition-policy",
        "assistant provider",
    ],
    "skill-catalog": [
        "uaf_skill_catalog",
        "src.skills.uaf_skill_catalog",
        "total_skills_found",
        "catalog_summary",
    ],
    "scenario-evaluation-harness": [
        "scenario_evaluator",
        "src.orchestration.scenario_evaluator",
        "meaningful_signal",
    ],
    "sql-formatting-style-harness": [
        "sql-formatting-style-harness",
        "verify_sql_formatting_style",
        "src.skills.sql_formatting_style",
        "style_contract_source",
        "mechanical_checks",
    ],
}

_KNOWN_HOST_FRONT_DOOR_SOURCES = {
    "codex",
    "codex-host",
    "codex_host",
    "codex-runtime",
    "codex_runtime",
    "host",
    "host-runtime",
    "host_runtime",
}
_FRONT_DOOR_PACKET_HASH_KEYS = frozenset({"packet_sha256", "packet_hash"})
_FRONT_DOOR_PROVENANCE_KEYS = frozenset(
    {
        "boundary_id",
        "correlation_id",
        "external_authenticity",
        "packet_hash",
        "packet_sha256",
        "source",
        "tool_identity",
    }
)

_GENERAL_TOOL_PACKET_HASH_KEYS = frozenset({"packet_sha256", "packet_hash"})
_GENERAL_TOOL_PACKET_FIELDS = frozenset(
    {
        "arguments",
        "boundary_id",
        "call_id",
        "call_packet_sha256",
        "correlation_id",
        "exit_code",
        "host",
        "input",
        "name",
        "origin",
        "output",
        "return_code",
        "returncode",
        "source",
        "status",
        "success",
        "tool_call_id",
        "tool_identity",
        "type",
    }
)
_GENERAL_TOOL_EXACT_IDENTITIES = frozenset(
    {
        "apply_patch",
        "approve_memory_import",
        "browser_manual_qa",
        "computer_use",
        "create_agent",
        "exec",
        "exec_command",
        "functions.exec",
        "functions.shell_command",
        "inspect_runtime_capabilities",
        "mssql_run_sql_query",
        "memory_import_approval",
        "multi_agent_v1.spawn_agent",
        "multi_agent_v1.wait_agent",
        "multi_tool_use.parallel",
        "orchestrate_pb_migration_validation",
        "request_user_input",
        "run_command",
        "shell_command",
        "text",
        "validate_large_work_orchestration_bundle",
        "verify_migration_generated_csharp_style",
        "verify_sql_formatting_style",
        "view_image",
    }
)
_SESSION_INTEGRITY_SAMPLE_LIMIT = 8
_PB_FRONT_DOOR_HISTORY_SAMPLE_LIMIT = 32
_COMPATIBILITY_EVENT_LIMIT = 4096
_AUDIT_VALUE_SAMPLE_LIMIT = 64
_AUTHENTICATED_MEMORY_APPROVAL_TOOLS = frozenset(
    {
        "approve_memory_import",
        "memory_import_approval",
        "src.orchestration.runtime_memory.approve_memory_import",
        "src.orchestration.runtime_memory.record_memory_import_approval",
    }
)
_MEMORY_IMPORT_DIRECTIVE_KEYS = frozenset(
    {
        "claim_kind",
        "action",
        "memory_import_approved",
        "approval_state",
        "scope",
        "project",
        "conversation_id",
    }
)

ACCEPTANCE_OUTPUT_MARKERS = {
    "always-on-front-door": {
        "intake_evidence": ["kh_front_door", "front_door_status", "classification", "plugin_route"],
        "status_split": [
            "runtime_applied_skills",
            "selected_not_executed_skills",
            "skill_status_summary",
            "immediate_next_skills",
            "required_next_action_codes",
            "deferred_skill_count",
        ],
    },
    "automatic-intake-harness": {
        "intake_evidence": ["kh_front_door", "front_door_status", "classification", "plugin_route"],
        "status_split": [
            "runtime_applied_skills",
            "selected_not_executed_skills",
            "skill_status_summary",
            "immediate_next_skills",
            "required_next_action_codes",
            "deferred_skill_count",
        ],
    },
    "adapter-contract-harness": {
        "adapter_contract": ["adapterrequest", "adapterresult", "workflowdispatchresult", "adapter contract"],
        "host_boundary": ["codex", "antigravity", "claude code", "dispatcher", "platform"],
    },
    "architect-pipeline": {
        "design_artifact": ["design_doc", "architecture", "workdesign", "work design", "requirements"],
        "execution_inputs": ["target_files", "acceptance criteria", "implementation plan", "design blueprint"],
    },
    "artifact-render-qa-harness": {
        "artifact_type": ["docx", "xlsx", "svg", "dxf", "renderable"],
        "render_evidence": ["readable", "structurally valid", "render qa", "artifact_render"],
    },
    "brainstorming-harness": {
        "options": ["option", "candidate", "direction", "alternatives"],
        "decision": ["recommendation", "selected", "approved", "decision"],
        "session_record": ["brainstormsession", "validate_brainstorm_session", "decision_log", "target_user"],
        "handoff": ["brainstorm_handoff", "build_architect_handoff", ".kh/brainstorm", "docs/kh/handoffs"],
    },
    "branch-finishing-harness": {
        "integration_state": ["branch_finish_status", "commit_sha", "git push", "pr-ready", "merged", "local only"],
    },
    "command-hook-policy-harness": {
        "hook_policy": ["hook", "rewrite", "trust", "permission precedence", "non-blocking"],
    },
    "command-output-harness": {
        "command_result": ["exit code", "stdout", "stderr", "returncode"],
        "compression_policy": ["truncated", "filtered", "summarized", "tokens saved", "preserved"],
    },
    "compound-engineering-harness": {
        "compound_capture": ["compoundcapture", "compound_capture", "compound_handoff", "reusable learning"],
        "followup": ["memory_candidates", "skill_candidates", "scenario candidates", "no_reusable_learning"],
    },
    "context-state-harness": {
        "resume_state": ["resume_handoff", "session_start_context", "interruption", "checkpoint"],
    },
    "deliverable-template-quality-harness": {
        "template_quality": ["required section", "template quality", "section coverage", "deliverable"],
    },
    "development-lifecycle-harness": {
        "workspace": ["workspace_strategy", "worktree", "isolated branch", "current-checkout"],
        "verification": ["verification_status", "fresh verification", "test passed", "progress.json"],
    },
    "domain-orchestration-harness": {
        "domain_design": ["domainprofile", "workdesign", "domain design", "design artifacts"],
        "domain_gates": ["qa/qc", "risk", "policy", "final decision"],
    },
    "goal-state-harness": {
        "goal_state": ["goalstate", "goal_ledger", "create_goal", "update_goal"],
        "completion_evidence": ["evidence_required", "missing_evidence", "blocked_reason", "success_criteria"],
    },
    "guard-policy-harness": {
        "guard_evidence": ["destructive", "approval", "secret", "permission", "edit boundary"],
    },
    "harness-evaluator": {
        "evaluation": ["py_compile", "python -m unittest", "pytest", "compileall", "exit code"],
    },
    "health-check-harness": {
        "health": ["health summary", "release readiness", "quality score", "static checks"],
    },
    "host-agent-orchestration": {
        "host_plan": ["subagent_strategy", "adapterrequest", "tool permissions", "observability"],
        "accounting": ["subagent_summary", "spawned", "closed", "role results"],
    },
    "memory-state-harness": {
        "memory_scope": ["memory_scope", "memoryscope", "project/chat", "conversation", "scoped durable", "scoped memory"],
        "memory_record": ["memory_context", "memory_candidates", "memoryrecord", "memory record", "memorystore", "resume-checkpoint"],
    },
    "orchestration-role-graph": {
        "role_graph": ["role graph", "ceo", "advisor", "architect", "reviewer", "release"],
    },
    "parallel-orchestration-harness": {
        "parallel_strategy": ["parallel_strategy", "fan-out", "fan-in", "bounded", "parallel_wave_count"],
    },
    "plan-execution-harness": {
        "progress": ["progress.json", "task_status", "active task", "next_task"],
        "loop": ["red", "green", "review", "commit_sha"],
    },
    "plugin-composition-policy": {
        "composition": ["controller", "assistant provider", "plugin_composition", "capability fit", "routing"],
    },
    "qa-gate-harness": {
        "qa_evidence": ["qa", "regression", "manual test", "browser qa", "verification"],
    },
    "quality-gates-harness": {
        "quality_gate": ["red/green", "tdd", "failing-first", "review gate", "evidence"],
    },
    "request-complexity-router": {
        "classification": ["classify_request", "request_complexity", "classification", "route", "domain"],
    },
    "review-gate-harness": {
        "review_result": ["review_status", "findings", "with fixes", "reviewer", "approved"],
    },
    "role-execution-audit-harness": {
        "role_audit": ["role_execution_audit", "audit_role_execution", "role results", "parallel waves"],
    },
    "scenario-evaluation-harness": {
        "scenario_result": ["scenario_evaluator", "side", "scenario", "regression", "meaningful_signal"],
    },
    "skill-catalog": {
        "catalog_result": ["uaf_skill_catalog", "total_skills", "valid_skills", "invalid_skills"],
    },
    "sql-formatting-style-harness": {
        "verifier": ["verify_sql_formatting_style", "mechanical_checks", "style_contract_source"],
        "sql_passthrough": ["token_optimizer_status", "passthrough", "contract-sensitive"],
    },
    "pb-to-csharp-migration-harness": {
        "packaged_profile": [
            "packaged_sanitized_profile",
            "profile_id",
            "profile_version",
            "profile_hash",
        ],
        "csharp_verification": [
            "verify_migration_generated_csharp_style",
            "orchestrate_pb_migration_validation",
        ],
        "designer_verification": ["target_designer_path", "designer", "validate-csharp"],
        "sp_verification": ["validate-sp", "sp_contract_status"],
        "sql_binding_release": ["final-sql-binding", "sql_release_correlated"],
        "build_verification": ["dotnet build", "msbuild", "build_status"],
        "database_verification": ["sqlcmd", "invoke-sqlcmd", "database_verification"],
        "manual_qa": ["manual_qa", "manual qa", "browser qa"],
    },
    "snapshot-state-harness": {
        "snapshot": ["snapshot", "rollback", "checkpoint", "snapshotmanager"],
    },
    "subagent-review-pipeline": {
        "review_roles": ["implementer", "spec-reviewer", "code-quality-reviewer", "reviewer"],
    },
    "systematic-debugging-harness": {
        "debug_chain": ["debug_status", "root cause", "hypothesis", "reproduction", "regression evidence"],
    },
    "token-optimizer": {
        "token_decision": ["token_optimizer_status", "runtime_token_optimization", "token optimization"],
        "savings_or_passthrough": [
            "estimated_tokens_saved",
            "estimated_payload_tokens_saved",
            "host_actual_tokens_used",
            "host_actual_token_evidence",
            "tokens saved",
            "passthrough",
            "considered_not_needed",
            "blocked",
        ],
    },
    "traceability-matrix-harness": {
        "traceability": ["traceability", "requirements", "evidence keys", "review gates"],
    },
    "verification-before-completion-harness": {
        "completion_claim": ["completion_claim", "verification_status", "fresh verification"],
        "command_evidence": ["exit code", "passed", "failed", "blocked", "residual_risk"],
    },
    "workflow-skill-distiller": {
        "distillation": ["workflow-skill-distiller", "skill_candidates", "distilled skill", "reusable workflow"],
    },
    "workflow-usability-harness": {
        "usability_state": ["progress_panel", "host_panel", "session_start_context", "compound_handoff"],
    },
    "worktree-isolation-harness": {
        "workspace_strategy": ["workspace_strategy", "project-local-worktree", "host-worktree", "isolated-branch", ".worktrees"],
    },
}

ACCEPTANCE_SEVERITY = {
    "always-on-front-door": "P1",
    "automatic-intake-harness": "P1",
    "goal-state-harness": "P1",
    "token-optimizer": "P1",
    "review-gate-harness": "P1",
    "verification-before-completion-harness": "P1",
    "memory-state-harness": "P2",
    "host-agent-orchestration": "P2",
    "role-execution-audit-harness": "P2",
    "subagent-review-pipeline": "P2",
}


@dataclass(frozen=True)
class SessionTextRecord:
    text: str
    payload_type: str
    role: str = ""
    call_id: str = ""
    name: str = ""
    arguments: str = ""
    exit_codes: tuple[Any, ...] = ()
    trusted_host_native_fast_path: bool = False
    trusted_front_door_runtime: bool = False
    trusted_correlated_tool_runtime: bool = False
    sql_requirement: bool | None = None


@dataclass(frozen=True)
class EventEnvelope:
    """One physical JSONL record plus immutable source provenance."""

    source_line: int
    raw_text: str
    source_bytes: int
    event: Any
    duplicate_keys: tuple[str, ...] = ()
    parse_error: str = ""
    features: "EventFeatures | None" = None


@dataclass(frozen=True)
class EventFeatures:
    """Bounded audit fields paired with the compact persisted event."""

    event_type: str
    payload_type: str
    role: str
    call_id: str
    boundary_id: str
    correlation_id: str
    tool_identity: str
    packet_hash: str
    text: str
    lowered: str
    is_non_kh_work_start: bool
    is_sql_output_request: bool
    reducer_matches: tuple[tuple[str, str], ...]
    postmortem: PostmortemEventFeatures


@dataclass(frozen=True)
class EventSemanticFeatures:
    """Bounded facts extracted from the original event before compaction."""

    is_non_kh_work_start: bool
    is_sql_output_request: bool
    reducer_matches: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CorrelatedFrontDoorReceipt:
    call_index: int
    output_index: int
    data: Dict[str, Any]


@dataclass(frozen=True)
class CorrelatedToolReceipt:
    call_index: int
    output_index: int
    call: Dict[str, Any]
    output: Dict[str, Any]
    data: Dict[str, Any]
    duplicate_boundary: bool = False
    duplicate_packet_hash: bool = False


@dataclass(frozen=True)
class SessionSkillAudit:
    session_id: str
    path: str
    total_skills: int
    coverage: Dict[str, Any]
    usage_summary: Dict[str, Any] = field(default_factory=dict)
    skills: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    postmortem: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        values = asdict(self)
        return {key: values[key] for key in sorted(values)}


@dataclass(frozen=True)
class SessionEventIndex:
    path_key: str
    payload_events: "DiskBackedSessionEvents"
    metadata: Dict[str, Any]
    integrity_issues: List[Dict[str, Any]]
    raw_characters_seen: int
    max_source_line_characters: int
    indexed_disk_bytes: int
    retained_memory_bytes: int
    catalog: Dict[str, Any] = field(default_factory=dict)
    postmortem: Any = None
    stage_telemetry: Dict[str, Any] = field(default_factory=dict)

    def diagnostics(self, *, include_stage_telemetry: bool = False) -> Dict[str, Any]:
        diagnostics = self.payload_events.diagnostics()
        if include_stage_telemetry and self.stage_telemetry:
            diagnostics["stage_telemetry"] = dict(self.stage_telemetry)
        return diagnostics

    def close(self) -> None:
        self.payload_events.close()


_SESSION_EVENT_PAYLOAD_KEYS = frozenset(
    {
        "arguments",
        "call_id",
        "call_packet_sha256",
        "boundary_id",
        "correlation_id",
        "content",
        "event_id",
        "exit_code",
        "goal",
        "info",
        "input",
        "last_agent_message",
        "memory_citation",
        "memory_import_directive",
        "message",
        "name",
        "origin",
        "output",
        "packet",
        "packet_hash",
        "packet_sha256",
        "phase",
        "return_code",
        "returncode",
        "role",
        "source",
        "status",
        "success",
        "thread_source",
        "tool_call_id",
        "tool_identity",
        "host",
        "type",
    }
)
_SESSION_METADATA_KEYS = frozenset(
    {"cwd", "id", "source", "thread_id", "thread_source"}
)
_SESSION_INDEX_TEXT_CAPTURE_LIMIT = 64 * 1024
_SESSION_INDEX_TEXT_CAPTURE_EDGE = 4 * 1024
_SESSION_INDEX_REQUIRED_EVIDENCE_MARKERS = (
    "pb_migration_verifier_receipt",
    "sql_final_response_binding",
    "sql_verifier_history",
    "sql_formatting_verifier",
    "token_optimizer_decision",
    "runtime_token_optimization",
    "front_door_status",
    '"m":"kh_fd_micro"',
    '"m": "kh_fd_micro"',
)
_SESSION_TEXT_AGGREGATE_LIMIT = 64 * 1024
_SESSION_TEXT_AGGREGATE_ITEM_LIMIT = 4 * 1024
_SESSION_TEXT_AGGREGATE_SIGNALS = (
    "always-on-front-door",
    "brainstorm",
    "compound",
    "front_door_status",
    "function_call",
    "goal-state-harness",
    "memory-state-harness",
    "memory_candidates",
    "orchestration",
    "pb-to-csharp",
    "runtime_token_optimization",
    "spawn_agent",
    "sql-formatting",
    "task_complete",
    "token_optimizer",
    "verification",
    "worktree",
)


@dataclass
class _BoundedTextAccumulator:
    """Incrementally reproduce ``_bounded_text_aggregate`` with fixed memory."""

    max_characters: int = _SESSION_TEXT_AGGREGATE_LIMIT
    item_limit: int = _SESSION_TEXT_AGGREGATE_ITEM_LIMIT
    first: List[tuple[int, str]] = field(default_factory=list)
    last: deque[tuple[int, str]] = field(default_factory=lambda: deque(maxlen=3))
    signals: List[tuple[int, str]] = field(default_factory=list)
    signal_count: int = 0
    item_count: int = 0

    def add(self, raw_text: str, *, lowered: str | None = None) -> None:
        text = str(raw_text or "")
        if not text or self.max_characters <= 0 or self.item_limit <= 0:
            return
        if len(text) > self.item_limit:
            edge = max(1, self.item_limit // 2)
            marker = "\n[KH_TEXT_AGGREGATE_TRUNCATED]\n"
            text = text[:edge] + marker + text[-edge:]
            if lowered is not None:
                lowered = None
        indexed = (self.item_count, text)
        if len(self.first) < 3:
            self.first.append(indexed)
        self.last.append(indexed)
        lowered = text.lower() if lowered is None else lowered
        if any(signal in lowered for signal in _SESSION_TEXT_AGGREGATE_SIGNALS):
            self.signal_count += 1
            if len(self.signals) < 8:
                self.signals.append(indexed)
            else:
                slot = (self.signal_count * 2654435761) % self.signal_count
                if slot < 8:
                    self.signals[slot] = indexed
        self.item_count += 1

    def render(self) -> str:
        if self.item_count == 0:
            return ""
        parts: List[str] = []
        retained = 0
        selected = {
            index: text for index, text in (*self.first, *self.last, *self.signals)
        }
        for index in sorted(selected):
            text = selected[index]
            remaining = self.max_characters - retained
            if remaining <= 0:
                break
            if len(text) > remaining:
                text = text[:remaining]
            parts.append(text)
            retained += len(text) + 1
        return "\n".join(parts)


def _canonical_json(value: Any) -> str:
    """Return deterministic, non-executable JSON for temporary audit storage."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _json_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("utf-8")
    if not isinstance(value, str) or not value:
        return {}
    decoded = json.loads(value)
    return decoded if isinstance(decoded, dict) else {}


def _json_scalar_sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("utf-8")
    if not isinstance(value, str) or not value:
        return ()
    decoded = json.loads(value)
    if not isinstance(decoded, list):
        return ()
    return tuple(
        item if item is None or isinstance(item, (bool, int, float, str)) else str(item)
        for item in decoded
    )


def _canonical_scalar_field(payload: Mapping[str, Any], key: str) -> str:
    if key not in payload:
        return ""
    return _canonical_json(payload[key])


def _retained_payload_fragment(
    payload_type: str,
    payload: Mapping[str, Any],
) -> tuple[str, Dict[str, Any]]:
    fragment: Dict[str, Any] = {}
    kinds: List[str] = []
    if payload_type == "thread_goal_updated":
        kinds.append("goal")
        for key in ("goal", "info"):
            if key in payload:
                fragment[key] = payload[key]
    if payload.get("memory_citation") is not None:
        kinds.append("memory")
        fragment["memory_citation"] = payload["memory_citation"]
    if payload.get("memory_import_directive") is not None:
        if "memory" not in kinds:
            kinds.append("memory")
        fragment["memory_import_directive"] = payload["memory_import_directive"]
    return "+".join(kinds), fragment


_RETAINED_JSON_KEYS_BY_FACT_KIND = {
    "goal": frozenset({"goal", "info"}),
    "memory": frozenset({"memory_citation", "memory_import_directive"}),
    "goal+memory": frozenset(
        {"goal", "info", "memory_citation", "memory_import_directive"}
    ),
}


def _validated_retained_payload_fragment(
    payload_type: str,
    fact_kind: Any,
    value: Any,
) -> Dict[str, Any]:
    normalized_kind = str(fact_kind or "")
    allowed_keys = _RETAINED_JSON_KEYS_BY_FACT_KIND.get(normalized_kind)
    if allowed_keys is None:
        raise ValueError(f"unsupported retained JSON fact kind: {normalized_kind!r}")
    if "goal" in normalized_kind.split("+") and payload_type != "thread_goal_updated":
        raise ValueError(
            "goal retained JSON is only valid for thread_goal_updated payloads"
        )
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("utf-8")
    if not isinstance(value, str) or not value:
        raise ValueError("retained JSON must be a non-empty JSON object")
    decoded = load_json_without_duplicate_keys(value)
    if not isinstance(decoded, dict):
        raise ValueError("retained JSON must decode to an object")
    unexpected_keys = sorted(set(decoded) - allowed_keys)
    if unexpected_keys:
        raise ValueError(
            "unexpected retained JSON keys for "
            f"{normalized_kind}: {', '.join(unexpected_keys)}"
        )
    if "goal" in normalized_kind.split("+") and not set(decoded).intersection(
        _RETAINED_JSON_KEYS_BY_FACT_KIND["goal"]
    ):
        raise ValueError("goal retained JSON has no goal facts")
    if "memory" in normalized_kind.split("+") and not set(decoded).intersection(
        _RETAINED_JSON_KEYS_BY_FACT_KIND["memory"]
    ):
        raise ValueError("memory retained JSON has no memory facts")
    return decoded


def _stored_packet_hash_valid(payload: Mapping[str, Any]) -> bool:
    supplied = _general_tool_supplied_packet_hash(payload)
    if not supplied:
        return False
    try:
        return supplied == _general_tool_packet_sha256(payload)
    except (TypeError, ValueError, UnicodeError):
        return False


def _valid_stored_general_tool_pair(
    call: Mapping[str, Any],
    output: Mapping[str, Any],
    *,
    call_packet_hash_valid: bool,
    output_packet_hash_valid: bool,
) -> bool:
    call_id = _payload_call_id(dict(call))
    if not call_id or call_id != _payload_call_id(dict(output)):
        return False
    if (str(call.get("type", "")), str(output.get("type", ""))) not in {
        ("function_call", "function_call_output"),
        ("custom_tool_call", "custom_tool_call_output"),
    }:
        return False
    if _is_front_door_runtime_command(dict(call), _payload_text(dict(call)).lower()):
        return _valid_host_front_door_provenance(
            call,
            output,
            _json_object_from_text(_payload_text(dict(output))),
            duplicate_boundaries=frozenset(),
            duplicate_packet_hashes=frozenset(),
        )
    source = _front_door_provenance_value(call, "source", "host", "origin")
    output_source = _front_door_provenance_value(output, "source", "host", "origin")
    tool_identity = str(call.get("tool_identity", "") or "").strip().lower()
    output_identity = str(output.get("tool_identity", "") or "").strip().lower()
    boundary_id = str(call.get("boundary_id", "") or "").strip()
    call_packet_hash = _general_tool_supplied_packet_hash(call)
    return bool(
        source in _KNOWN_HOST_FRONT_DOOR_SOURCES
        and output_source == source
        and tool_identity
        and output_identity == tool_identity
        and _is_allowed_general_tool_identity(tool_identity)
        and str(call.get("name", "") or "").strip().lower() == tool_identity
        and str(call.get("correlation_id", "") or "").strip() == call_id
        and str(output.get("correlation_id", "") or "").strip() == call_id
        and boundary_id
        and boundary_id == str(output.get("boundary_id", "") or "").strip()
        and call_packet_hash
        and str(output.get("call_packet_sha256", "") or "").strip().lower()
        == call_packet_hash
        and _general_tool_supplied_packet_hash(output)
        and call_packet_hash_valid
        and output_packet_hash_valid
    )


_EVENT_PAYLOAD_VIEW_COLUMN_COUNT = 25


def _optional_json_scalar(value: Any) -> tuple[bool, Any]:
    if value is None or value == "":
        return False, None
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("utf-8")
    return True, json.loads(str(value))


def _payload_from_event_view_row(
    row: Sequence[Any],
    offset: int = 0,
) -> Dict[str, Any]:
    payload_type = str(row[offset + 2])
    payload: Dict[str, Any] = {"type": payload_type}
    for key, column_offset in (
        ("role", 3),
        ("call_id", 4),
        ("boundary_id", 5),
        ("correlation_id", 6),
        ("tool_identity", 7),
        ("name", 8),
    ):
        value = str(row[offset + column_offset] or "")
        if value:
            payload[key] = value
    packet_hash = str(row[offset + 9] or "")
    if packet_hash:
        payload["packet_sha256"] = packet_hash
    phase = str(row[offset + 11] or "")
    if phase:
        payload["phase"] = phase
    source = str(row[offset + 12] or "")
    if source:
        payload["source"] = source
    call_packet_sha256 = str(row[offset + 13] or "")
    if call_packet_sha256:
        payload["call_packet_sha256"] = call_packet_sha256
    status = str(row[offset + 14] or "")
    if status:
        payload["status"] = status
    for key, column_offset in (
        ("success", 15),
        ("exit_code", 16),
        ("return_code", 17),
        ("returncode", 18),
    ):
        present, value = _optional_json_scalar(row[offset + column_offset])
        if present:
            payload[key] = value

    text = str(row[offset + 20] or "")
    arguments = str(row[offset + 21] or "")
    if payload_type == "message":
        payload["content"] = text
    elif payload_type == "agent_message":
        payload["message"] = text
    elif payload_type in {"function_call", "custom_tool_call"}:
        payload["arguments"] = arguments
    elif payload_type in {"function_call_output", "custom_tool_call_output"}:
        payload["output"] = text
    elif payload_type in {"host_front_door", "host_native_front_door"}:
        payload["output"] = text
    elif payload_type == "task_complete":
        payload["last_agent_message"] = text

    retained_kind = row[offset + 23]
    retained = row[offset + 24]
    if retained not in (None, "", b""):
        payload.update(
            _validated_retained_payload_fragment(
                payload_type,
                retained_kind,
                retained,
            )
        )
    return payload


def _event_from_event_view_row(
    row: Sequence[Any],
    offset: int = 0,
) -> Dict[str, Any]:
    event = {
        "type": str(row[offset + 1]),
        "payload": _payload_from_event_view_row(row, offset),
    }
    timestamp_json = row[offset + 10]
    if isinstance(timestamp_json, (bytes, bytearray, memoryview)):
        timestamp_json = bytes(timestamp_json).decode("utf-8")
    timestamp = json.loads(str(timestamp_json))
    if timestamp is not None:
        event["timestamp"] = timestamp
    return event


def _text_record_from_joined_row(
    row: Sequence[Any],
    offset: int = 0,
) -> SessionTextRecord:
    stored_text = str(row[offset] or "")
    payload_type = str(row[offset + 1] or "")
    role = str(row[offset + 2] or "")
    call_id = str(row[offset + 3] or "")
    name = str(row[offset + 4] or "")
    arguments = str(row[offset + 5] or "")
    if payload_type in {"function_call", "custom_tool_call"}:
        stored_text = f"{name} {arguments}"
    if bool(row[offset + 9]):
        stored_text = PASSIVE_REFERENCE_PREFIX + stored_text
    exit_codes: List[Any] = []
    for column_offset in (6, 7, 8):
        present, value = _optional_json_scalar(row[offset + column_offset])
        if present:
            exit_codes.append(value)
    return SessionTextRecord(
        text=stored_text,
        payload_type=payload_type,
        role=role,
        call_id=call_id,
        name=name,
        arguments=arguments,
        exit_codes=tuple(exit_codes),
        trusted_host_native_fast_path=bool(row[offset + 10]),
        trusted_front_door_runtime=bool(row[offset + 11]),
        trusted_correlated_tool_runtime=bool(row[offset + 12]),
        sql_requirement=bool(row[offset + 13]),
    )


def _delete_sqlite_files(path: Path | None) -> None:
    if path is None:
        return
    for candidate in (
        path,
        Path(f"{path}-journal"),
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
    ):
        try:
            candidate.unlink()
        except FileNotFoundError:
            continue
        except OSError:
            # The primary connection is closed before this helper runs. A
            # cleanup failure must not hide the analysis result on Windows.
            continue


class DiskBackedSessionEvents(SequenceABC[Dict[str, Any]]):
    """SQLite-backed compatibility view over compact audit events.

    The object intentionally retains no event dictionaries, source-line arrays,
    or source hashes in Python memory. Random access and repeated legacy views
    are served from the temporary fact database while reducers migrate to
    direct indexed queries.
    """

    def __init__(self, catalog_skills: Sequence[Mapping[str, Any]] = ()) -> None:
        self._path: Path | None = None
        self._connection: sqlite3.Connection | None = None
        self._sealed = False
        self._closed = False
        handle = None
        try:
            handle = tempfile.NamedTemporaryFile(
                mode="wb",
                prefix="kh-session-audit-",
                suffix=".sqlite3",
                delete=False,
            )
            self._path = Path(handle.name)
            handle.close()
            handle = None
            self._connection = sqlite3.connect(str(self._path))
            connection = self._connection
            connection.execute("PRAGMA page_size=8192")
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute("PRAGMA locking_mode=EXCLUSIVE")
            connection.execute("PRAGMA temp_store=FILE")
            connection.execute("PRAGMA cache_size=-8192")
            connection.executescript(
                """
            CREATE TABLE events (
                seq INTEGER PRIMARY KEY,
                source_line INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_type TEXT NOT NULL,
                role TEXT NOT NULL,
                call_id TEXT NOT NULL,
                boundary_id TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                tool_identity TEXT NOT NULL,
                name TEXT NOT NULL,
                packet_hash TEXT NOT NULL,
                timestamp_json TEXT NOT NULL,
                source TEXT NOT NULL,
                call_packet_sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                success_json TEXT NOT NULL,
                exit_code_json TEXT NOT NULL,
                return_code_json TEXT NOT NULL,
                returncode_json TEXT NOT NULL,
                packet_hash_valid INTEGER NOT NULL,
                is_request_boundary INTEGER NOT NULL,
                phase TEXT NOT NULL,
                goal_status TEXT NOT NULL,
                is_non_kh_work_start INTEGER NOT NULL,
                is_sql_output_request INTEGER NOT NULL,
                trusted_host_native_fast_path INTEGER NOT NULL
            );
            CREATE INDEX events_payload_type_idx ON events(payload_type, seq);
            CREATE INDEX events_role_idx ON events(role, payload_type, seq);
            CREATE INDEX events_call_id_idx ON events(call_id, payload_type, seq);
            CREATE INDEX events_request_boundary_idx ON events(is_request_boundary, seq);
            CREATE TABLE retained_json (
                event_seq INTEGER PRIMARY KEY,
                fact_kind TEXT NOT NULL
                    CHECK(fact_kind IN ('goal', 'memory', 'goal+memory')),
                data_json TEXT NOT NULL
            );
            CREATE TABLE facts (
                seq INTEGER NOT NULL,
                kind TEXT NOT NULL,
                fact_key TEXT NOT NULL,
                fact_value TEXT NOT NULL,
                PRIMARY KEY (seq, kind, fact_key)
            ) WITHOUT ROWID;
            CREATE INDEX facts_kind_key_idx ON facts(kind, fact_key, seq);
            CREATE TABLE correlated_receipts (
                call_seq INTEGER PRIMARY KEY,
                output_seq INTEGER NOT NULL UNIQUE,
                succeeded INTEGER NOT NULL,
                is_implementation INTEGER NOT NULL,
                is_verification INTEGER NOT NULL
            );
            CREATE TABLE front_door_receipts (
                call_seq INTEGER PRIMARY KEY,
                output_seq INTEGER NOT NULL UNIQUE,
                data_json TEXT NOT NULL
            );
            CREATE TABLE front_door_claims (
                event_seq INTEGER PRIMARY KEY,
                data_json TEXT NOT NULL
            );
            CREATE TABLE pb_front_door_acceptance (
                output_seq INTEGER PRIMARY KEY,
                accepted INTEGER NOT NULL CHECK(accepted IN (0, 1))
            );
            CREATE TABLE pb_verified_corrections (
                correction_seq INTEGER PRIMARY KEY
            );
            CREATE TABLE pb_correction_candidates (
                correction_seq INTEGER PRIMARY KEY
            );
            CREATE TABLE pb_active_implementations (
                output_seq INTEGER PRIMARY KEY,
                targets_json TEXT NOT NULL
            );
            CREATE TABLE sql_provider_selections (
                output_record_seq INTEGER PRIMARY KEY,
                call_record_seq INTEGER NOT NULL,
                provider_id TEXT NOT NULL,
                provider_path TEXT NOT NULL,
                provider_source TEXT NOT NULL,
                selection_sha256 TEXT NOT NULL,
                receipt_id TEXT NOT NULL,
                provenance_valid INTEGER NOT NULL,
                provenance_errors_json TEXT NOT NULL
            );
            CREATE INDEX sql_provider_selection_receipt_idx
                ON sql_provider_selections(receipt_id, output_record_seq);
            CREATE TABLE sql_runtime_receipt_facts (
                record_seq INTEGER NOT NULL,
                receipt_kind TEXT NOT NULL,
                receipt_id TEXT NOT NULL,
                PRIMARY KEY(record_seq, receipt_kind, receipt_id)
            ) WITHOUT ROWID;
            CREATE INDEX sql_runtime_receipt_lookup_idx
                ON sql_runtime_receipt_facts(receipt_kind, receipt_id, record_seq);
            CREATE TABLE memory_decisions (
                event_seq INTEGER PRIMARY KEY,
                decision TEXT NOT NULL CHECK(decision IN ('approve', 'revoke'))
            );
            CREATE TABLE active_forbidden_claims (
                claim TEXT PRIMARY KEY,
                request_seq INTEGER NOT NULL,
                scanned INTEGER NOT NULL DEFAULT 0,
                matched INTEGER NOT NULL DEFAULT 0,
                scan_sample TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE correction_facts (
                event_seq INTEGER PRIMARY KEY,
                active_goal INTEGER NOT NULL,
                invalidated_json TEXT NOT NULL,
                replacements_json TEXT NOT NULL,
                related_to_previous INTEGER NOT NULL,
                prior_completion_seq INTEGER,
                sample TEXT NOT NULL
            );
            CREATE TABLE text_records (
                record_seq INTEGER PRIMARY KEY,
                event_seq INTEGER NOT NULL UNIQUE,
                text TEXT NOT NULL,
                arguments TEXT NOT NULL,
                passive INTEGER NOT NULL CHECK(passive IN (0, 1)),
                trusted_front_door_runtime INTEGER NOT NULL,
                trusted_correlated_tool_runtime INTEGER NOT NULL,
                sql_requirement INTEGER NOT NULL
            );
            CREATE TABLE catalog_candidate_records (
                record_seq INTEGER PRIMARY KEY
            );
            CREATE TABLE orchestration_protocol_calls (
                record_seq INTEGER PRIMARY KEY,
                validates_bundle INTEGER NOT NULL CHECK(validates_bundle IN (0, 1)),
                audits_roles INTEGER NOT NULL CHECK(audits_roles IN (0, 1))
            );
            CREATE VIEW event_payloads AS
            SELECT events.seq,
                   events.event_type,
                   events.payload_type,
                   events.role,
                   events.call_id,
                   events.boundary_id,
                   events.correlation_id,
                   events.tool_identity,
                   events.name,
                   events.packet_hash,
                   events.timestamp_json,
                   events.phase,
                   events.source,
                   events.call_packet_sha256,
                   events.status,
                   events.success_json,
                   events.exit_code_json,
                   events.return_code_json,
                   events.returncode_json,
                   events.packet_hash_valid,
                   COALESCE(text_records.text, ''),
                   COALESCE(text_records.arguments, ''),
                   COALESCE(text_records.passive, 0),
                   COALESCE(retained_json.fact_kind, ''),
                   COALESCE(retained_json.data_json, '')
            FROM events
            LEFT JOIN text_records ON text_records.event_seq = events.seq
            LEFT JOIN retained_json ON retained_json.event_seq = events.seq;
            CREATE TABLE reducer_summaries (
                reducer_name TEXT PRIMARY KEY,
                fact_kind TEXT NOT NULL,
                matched_count INTEGER NOT NULL,
                first_event_seq INTEGER,
                last_event_seq INTEGER,
                finalized INTEGER NOT NULL CHECK(finalized = 1)
            );
            CREATE TABLE reducer_samples (
                reducer_name TEXT NOT NULL,
                sample_seq INTEGER NOT NULL,
                event_seq INTEGER NOT NULL,
                fact_key TEXT NOT NULL,
                fact_value TEXT NOT NULL,
                PRIMARY KEY(reducer_name, sample_seq)
            ) WITHOUT ROWID;
            CREATE TABLE analysis_summaries (
                summary_name TEXT PRIMARY KEY,
                data_json TEXT NOT NULL
            ) WITHOUT ROWID;
            """
            )
        except Exception:
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
            if self._connection is not None:
                try:
                    self._connection.close()
                except Exception:
                    pass
                self._connection = None
            self._closed = True
            _delete_sqlite_files(self._path)
            raise
        self._disk_bytes = 0
        self._retained_record_count = 0
        self._original_passes = 0
        self._check_count = 0
        self._source_open_count = 0
        self._source_passes = 0
        self._source_bytes_read = 0
        self._reducer_count = 0
        self._reducer_finalize_count = 0
        self._reducer_evidence: List[Dict[str, Any]] = []
        self._receipts_ready = False
        self._ordered_correlation_replay_count = 0
        self._ordered_correlation_claim_count = 0
        self._protocol_correlation_replay_count = 0
        self._pb_correlation_replay_count = 0
        self._memory_decisions_ready = False
        self._text_records_ready = False
        self._text_record_count = 0
        self._analysis_summary_ready = False
        self._analysis_accumulators = {
            "combined_text": _BoundedTextAccumulator(),
            "decision_text": _BoundedTextAccumulator(),
            "sql_scope_text": _BoundedTextAccumulator(),
            "non_front_door_tool_text": _BoundedTextAccumulator(),
        }
        self._analysis_browser_or_local_app_qa = False
        self._catalog_skills = [
            {
                "name": str(skill.get("name", "")),
                "relative_path": str(skill.get("relative_path", "")),
            }
            for skill in catalog_skills
        ]
        self._catalog_observations_summary: Dict[str, Dict[str, Any]] = {
            str(skill.get("name", "")): _empty_observations()
            for skill in self._catalog_skills
        }
        self._catalog_observation_index = _build_catalog_observation_index(
            self._catalog_skills
        )

    @property
    def _db(self) -> sqlite3.Connection:
        connection = self._connection
        if self._closed or connection is None:
            raise RuntimeError("session event index is closed")
        return connection

    def append(
        self,
        event: Mapping[str, Any],
        *,
        source_line: int,
        features: EventFeatures | None = None,
    ) -> int:
        if self._sealed or self._closed:
            raise RuntimeError("session event index is not writable")
        record = dict(event)
        payload = record.get("payload", {})
        payload = payload if isinstance(payload, Mapping) else {}
        payload_type = features.payload_type if features is not None else str(payload.get("type", "") or "")
        call_id = features.call_id if features is not None else _payload_call_id(dict(payload))
        packet_hash = (
            features.packet_hash
            if features is not None
            else str(
                payload.get("packet_sha256", "") or payload.get("packet_hash", "") or ""
            ).strip().lower()
        )
        seq = self._retained_record_count
        text = features.text if features is not None else _payload_text(dict(payload))
        is_request_boundary = (
            payload_type == "task_complete"
            or (
                payload_type == "message"
                and str(payload.get("role", "") or "").strip().lower() == "user"
                and not _is_synthetic_context_message(text)
                and not _is_bounded_same_task_continuation(text)
            )
        )
        event_type = features.event_type if features is not None else str(record.get("type", "") or "")
        role = features.role if features is not None else str(payload.get("role", "") or "").strip().lower()
        boundary_id = features.boundary_id if features is not None else str(payload.get("boundary_id", "") or "").strip()
        correlation_id = features.correlation_id if features is not None else str(payload.get("correlation_id", "") or "").strip()
        tool_identity = features.tool_identity if features is not None else str(payload.get("tool_identity", "") or "").strip().lower()
        lowered = features.lowered if features is not None else text.lower()
        phase = str(payload.get("phase", "") or "").strip().lower()
        goal = payload.get("goal", {}) or {}
        goal_status = (
            str(goal.get("status", "") or "").strip().lower()
            if isinstance(goal, Mapping)
            else ""
        )
        is_non_kh_work_start = (
            features.is_non_kh_work_start
            if features is not None
            else _is_non_kh_work_start(dict(payload), lowered)
        )
        is_sql_output_request = (
            features.is_sql_output_request
            if features is not None
            else bool(
                payload_type == "message"
                and role == "user"
                and looks_like_sql_output_request(lowered)
            )
        )
        trusted_host_native_fast_path = bool(
            payload_type in {"host_front_door", "host_native_front_door"}
            and _has_trusted_host_native_fast_path_provenance(payload, text)
        )
        timestamp_json = _canonical_json(record.get("timestamp")) if "timestamp" in record else "null"
        source = _front_door_provenance_value(payload, "source", "host", "origin")
        retained_kind, retained_fragment = _retained_payload_fragment(payload_type, payload)
        self._db.execute(
            """
            INSERT INTO events (
                seq, source_line, event_type, payload_type,
                role, call_id, boundary_id, correlation_id, tool_identity,
                name, packet_hash, timestamp_json, source,
                call_packet_sha256, status, success_json,
                exit_code_json, return_code_json, returncode_json,
                packet_hash_valid,
                is_request_boundary, phase, goal_status, is_non_kh_work_start,
                is_sql_output_request, trusted_host_native_fast_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                seq,
                int(source_line),
                event_type,
                payload_type,
                role,
                call_id,
                boundary_id,
                correlation_id,
                tool_identity,
                str(payload.get("name", "") or "").strip(),
                packet_hash,
                timestamp_json,
                source,
                str(payload.get("call_packet_sha256", "") or "").strip().lower(),
                str(payload.get("status", "") or "").strip(),
                _canonical_scalar_field(payload, "success"),
                _canonical_scalar_field(payload, "exit_code"),
                _canonical_scalar_field(payload, "return_code"),
                _canonical_scalar_field(payload, "returncode"),
                int(_stored_packet_hash_valid(payload)),
                int(is_request_boundary),
                phase,
                goal_status,
                int(is_non_kh_work_start),
                int(is_sql_output_request),
                int(trusted_host_native_fast_path),
            ),
        )
        if retained_fragment:
            self._db.execute(
                "INSERT INTO retained_json(event_seq, fact_kind, data_json) VALUES (?, ?, ?)",
                (seq, retained_kind, _canonical_json(retained_fragment)),
            )
        if (
            payload_type in {
                "function_call",
                "custom_tool_call",
                "function_call_output",
                "custom_tool_call_output",
            }
            or boundary_id
            or packet_hash
            or payload.get("memory_citation") is not None
            or (
                payload_type == "message"
                and role == "user"
                and payload.get("memory_import_directive") is not None
            )
        ):
            self._record_facts(seq, payload_type, payload, features=features)
        self._retained_record_count += 1
        if self._retained_record_count % 16384 == 0:
            self._db.commit()
        return seq

    def append_unindexed(self, event: Mapping[str, Any]) -> None:
        # Session metadata is retained separately on SessionEventIndex. It is
        # not part of the audit payload sequence and no spool copy is needed.
        if self._sealed or self._closed:
            raise RuntimeError("session event index is not writable")

    def seal(self) -> None:
        if self._sealed or self._closed:
            return
        self._db.commit()
        self._sealed = True
        try:
            self._disk_bytes = self._path.stat().st_size if self._path is not None else 0
        except OSError:
            self._disk_bytes = 0

    @property
    def disk_bytes(self) -> int:
        return self._disk_bytes

    @property
    def retained_memory_bytes(self) -> int:
        self.seal()
        accumulator_state = {
            name: {
                "first": accumulator.first,
                "last": tuple(accumulator.last),
                "signals": accumulator.signals,
                "signal_count": accumulator.signal_count,
                "item_count": accumulator.item_count,
            }
            for name, accumulator in self._analysis_accumulators.items()
        }
        catalog_index = self._catalog_observation_index
        return _retained_python_bytes(
            {
                "analysis_accumulators": accumulator_state,
                "catalog_skills": self._catalog_skills,
                "catalog_observations": self._catalog_observations_summary,
                "catalog_specifications": (
                    catalog_index.specifications_by_name if catalog_index else {}
                ),
                "catalog_alias_owners": (
                    catalog_index.alias_owners if catalog_index else {}
                ),
                "catalog_runtime_owners": (
                    catalog_index.runtime_owners if catalog_index else {}
                ),
                "catalog_candidate_buckets": (
                    catalog_index.candidate_buckets if catalog_index else ()
                ),
                "reducer_evidence": self._reducer_evidence,
            }
        )

    @property
    def temp_path(self) -> Path:
        if self._path is None:
            raise RuntimeError("session event index has no temporary path")
        return self._path

    @property
    def closed(self) -> bool:
        return self._closed

    def __len__(self) -> int:
        return self._retained_record_count

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        self._ensure_readable()
        cursor = self._db.execute("SELECT * FROM event_payloads ORDER BY seq")
        return (_event_from_event_view_row(row) for row in cursor)

    def __getitem__(self, index: int | slice) -> Dict[str, Any] | List[Dict[str, Any]]:
        self._ensure_readable()
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step != 1:
                return [self[item] for item in range(start, stop, step)]
            rows = self._db.execute(
                "SELECT * FROM event_payloads WHERE seq >= ? AND seq < ? ORDER BY seq",
                (start, stop),
            )
            return [_event_from_event_view_row(row) for row in rows]
        normalized = index if index >= 0 else len(self) + index
        if normalized < 0 or normalized >= len(self):
            raise IndexError("session event index out of range")
        row = self._db.execute(
            "SELECT * FROM event_payloads WHERE seq = ?", (normalized,)
        ).fetchone()
        if row is None:
            raise IndexError("session event index out of range")
        return _event_from_event_view_row(row)

    def iter_events(
        self,
        *,
        payload_types: Iterable[str] | None = None,
        roles: Iterable[str] | None = None,
        event_types: Iterable[str] | None = None,
        start: int = 0,
        stop: int | None = None,
    ) -> Iterator[tuple[int, Dict[str, Any]]]:
        """Yield only indexed event classes needed by a reducer/check."""

        self._ensure_readable()
        clauses = ["seq >= ?"]
        parameters: List[Any] = [max(0, int(start))]
        if stop is not None:
            clauses.append("seq < ?")
            parameters.append(max(0, int(stop)))
        for column, values in (
            ("payload_type", payload_types),
            ("role", roles),
            ("event_type", event_types),
        ):
            normalized = tuple(dict.fromkeys(str(value) for value in (values or ())))
            if normalized:
                placeholders = ",".join("?" for _ in normalized)
                clauses.append(f"{column} IN ({placeholders})")
                parameters.extend(normalized)
        rows = self._db.execute(
            f"SELECT * FROM event_payloads WHERE {' AND '.join(clauses)} ORDER BY seq",
            parameters,
        )
        for row in rows:
            yield int(row[0]), _event_from_event_view_row(row)

    def iter_payloads(
        self,
        *,
        payload_types: Iterable[str] | None = None,
        roles: Iterable[str] | None = None,
        start: int = 0,
        stop: int | None = None,
    ) -> Iterator[tuple[int, Dict[str, Any]]]:
        self._ensure_readable()
        clauses = ["seq >= ?"]
        parameters: List[Any] = [max(0, int(start))]
        if stop is not None:
            clauses.append("seq < ?")
            parameters.append(max(0, int(stop)))
        for column, values in (("payload_type", payload_types), ("role", roles)):
            normalized = tuple(dict.fromkeys(str(value) for value in (values or ())))
            if normalized:
                placeholders = ",".join("?" for _ in normalized)
                clauses.append(f"{column} IN ({placeholders})")
                parameters.extend(normalized)
        rows = self._db.execute(
            f"SELECT * FROM event_payloads WHERE {' AND '.join(clauses)} ORDER BY seq",
            parameters,
        )
        for row in rows:
            yield int(row[0]), _payload_from_event_view_row(row)

    def iter_payloads_with_front_door_flag(
        self,
        *,
        payload_types: Iterable[str],
    ) -> Iterator[tuple[int, Dict[str, Any], bool]]:
        self._ensure_correlated_receipts()
        normalized = tuple(dict.fromkeys(str(value) for value in payload_types))
        if not normalized:
            return
        placeholders = ",".join("?" for _ in normalized)
        rows = self._db.execute(
            f"""
            SELECT payloads.*,
                   CASE WHEN receipts.output_seq IS NULL THEN 0 ELSE 1 END
            FROM event_payloads AS payloads
            LEFT JOIN front_door_receipts AS receipts
              ON receipts.output_seq = payloads.seq
            WHERE payloads.payload_type IN ({placeholders})
            ORDER BY payloads.seq
            """,
            normalized,
        )
        for row in rows:
            yield int(row[0]), _payload_from_event_view_row(row), bool(row[-1])

    def iter_front_door_audit_facts(
        self,
        *,
        payload_types: Iterable[str],
    ) -> Iterator[tuple[int, str, str, str, str, bool, bool, bool, bool]]:
        """Replay narrow front-door facts without decoding stored payload JSON."""

        self._ensure_correlated_receipts()
        normalized = tuple(dict.fromkeys(str(value) for value in payload_types))
        if not normalized:
            return
        placeholders = ",".join("?" for _ in normalized)
        rows = self._db.execute(
            f"""
            SELECT events.seq, events.payload_type, events.role,
                   CASE
                       WHEN events.payload_type IN (
                            'function_call', 'custom_tool_call'
                       ) THEN events.name || ' ' || COALESCE(text_records.arguments, '')
                       ELSE COALESCE(text_records.text, '')
                   END,
                   events.goal_status,
                   events.is_non_kh_work_start, events.is_sql_output_request,
                   events.trusted_host_native_fast_path,
                   CASE WHEN receipts.output_seq IS NULL THEN 0 ELSE 1 END
            FROM events
            LEFT JOIN text_records ON text_records.event_seq = events.seq
            LEFT JOIN front_door_receipts AS receipts
              ON receipts.output_seq = events.seq
            WHERE events.payload_type IN ({placeholders})
            ORDER BY events.seq
            """,
            normalized,
        )
        for row in rows:
            yield (
                int(row[0]),
                str(row[1]),
                str(row[2]),
                _strip_passive_prefix(str(row[3])),
                str(row[4]),
                bool(row[5]),
                bool(row[6]),
                bool(row[7]),
                bool(row[8]),
            )

    def iter_front_door_output_payloads(
        self,
    ) -> Iterator[tuple[int, Dict[str, Any], Dict[str, Any]]]:
        self._ensure_correlated_receipts()
        rows = self._db.execute(
            """
            SELECT outputs.*, receipts.data_json
            FROM front_door_receipts AS receipts
            JOIN event_payloads AS outputs ON outputs.seq = receipts.output_seq
            ORDER BY receipts.output_seq
            """
        )
        for row in rows:
            yield (
                int(row[0]),
                _payload_from_event_view_row(row),
                _json_mapping(row[-1]),
            )

    def append_front_door_claim(
        self,
        event_seq: int,
        data: Mapping[str, Any],
    ) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO front_door_claims(event_seq, data_json) VALUES (?, ?)",
            (int(event_seq), _canonical_json(dict(data))),
        )

    def iter_front_door_claim_payloads(
        self,
    ) -> Iterator[tuple[int, Dict[str, Any], Dict[str, Any]]]:
        rows = self._db.execute(
            """
            SELECT payloads.*, claims.data_json
            FROM front_door_claims AS claims
            JOIN event_payloads AS payloads ON payloads.seq = claims.event_seq
            ORDER BY claims.event_seq
            """
        )
        for row in rows:
            yield (
                int(row[0]),
                _payload_from_event_view_row(row),
                _json_mapping(row[-1]),
            )

    def iter_ordered_correlation_facts(
        self,
    ) -> Iterator[tuple[int, Dict[str, Any], Dict[str, Any], Dict[str, Any]]]:
        """Replay claims, events, and authenticated calls in one ordered query."""

        self._ensure_correlated_receipts()
        if self._db.execute("SELECT 1 FROM front_door_claims LIMIT 1").fetchone() is None:
            return
        self._ordered_correlation_replay_count += 1
        rows = self._db.execute(
            """
            SELECT payloads.*, claims.data_json, call_payloads.*
            FROM event_payloads AS payloads
            LEFT JOIN front_door_claims AS claims
              ON claims.event_seq = payloads.seq
            LEFT JOIN correlated_receipts AS receipts
              ON receipts.output_seq = payloads.seq
             AND receipts.succeeded = 1
            LEFT JOIN event_payloads AS call_payloads
              ON call_payloads.seq = receipts.call_seq
            ORDER BY payloads.seq
            """
        )
        call_offset = _EVENT_PAYLOAD_VIEW_COLUMN_COUNT + 1
        for row in rows:
            claim_data = (
                _json_mapping(row[_EVENT_PAYLOAD_VIEW_COLUMN_COUNT])
                if row[_EVENT_PAYLOAD_VIEW_COLUMN_COUNT] not in (None, "", b"")
                else {}
            )
            if claim_data:
                self._ordered_correlation_claim_count += 1
            correlated_call = (
                _payload_from_event_view_row(row, call_offset)
                if row[call_offset] is not None
                else {}
            )
            yield (
                int(row[0]),
                _payload_from_event_view_row(row),
                claim_data,
                correlated_call,
            )

    def iter_timed_payloads(
        self,
        *,
        payload_types: Iterable[str],
    ) -> Iterator[tuple[int, Dict[str, Any], Any]]:
        normalized = tuple(dict.fromkeys(str(value) for value in payload_types))
        if not normalized:
            return
        placeholders = ",".join("?" for _ in normalized)
        rows = self._db.execute(
            f"""
            SELECT *
            FROM event_payloads
            WHERE payload_type IN ({placeholders})
            ORDER BY seq
            """,
            normalized,
        )
        for row in rows:
            yield int(row[0]), _payload_from_event_view_row(row), json.loads(str(row[10]))

    def iter_payloads_with_memory_decision(
        self,
        *,
        payload_types: Iterable[str],
    ) -> Iterator[tuple[int, Dict[str, Any], str]]:
        normalized = tuple(dict.fromkeys(str(value) for value in payload_types))
        if not normalized:
            return
        placeholders = ",".join("?" for _ in normalized)
        rows = self._db.execute(
            f"""
            SELECT payloads.*,
                   COALESCE(decisions.decision, '')
            FROM event_payloads AS payloads
            LEFT JOIN memory_decisions AS decisions
              ON decisions.event_seq = payloads.seq
            WHERE payloads.payload_type IN ({placeholders})
            ORDER BY payloads.seq
            """,
            normalized,
        )
        for row in rows:
            yield int(row[0]), _payload_from_event_view_row(row), str(row[-1])

    def source_locator(self, index: int) -> Dict[str, Any]:
        self._ensure_readable()
        normalized = index if index >= 0 else len(self) + index
        if normalized < 0 or normalized >= len(self):
            raise IndexError("session event index out of range")
        row = self._db.execute(
            "SELECT source_line FROM events WHERE seq = ?",
            (normalized,),
        ).fetchone()
        if row is None:
            raise IndexError("session event index out of range")
        return {"source_line": int(row[0])}

    def set_pipeline_diagnostics(
        self,
        *,
        source_open_count: int,
        source_passes: int,
        source_bytes_read: int,
        reducer_count: int,
        reducer_finalize_count: int,
        reducer_evidence: Sequence[Mapping[str, Any]],
    ) -> None:
        self._source_open_count = int(source_open_count)
        self._source_passes = int(source_passes)
        self._source_bytes_read = int(source_bytes_read)
        self._reducer_count = int(reducer_count)
        self._reducer_finalize_count = int(reducer_finalize_count)
        self._reducer_evidence = [dict(item) for item in reducer_evidence]

    def note_original_pass(self) -> None:
        self._original_passes += 1

    def note_check(self) -> None:
        self._check_count += 1

    def diagnostics(self) -> Dict[str, Any]:
        self.seal()
        diagnostics: Dict[str, Any] = {
            "original_passes": self._original_passes,
            "retained_record_count": self._retained_record_count,
            "check_count": self._check_count,
            "source_open_count": self._source_open_count,
            "source_passes": self._source_passes,
            "source_bytes_read": self._source_bytes_read,
            "reducer_count": self._reducer_count,
            "registered_reducer_count": self._reducer_count,
            "reducer_finalize_count": self._reducer_finalize_count,
            "finalized_reducer_count": self._reducer_finalize_count,
        }
        if self._retained_record_count:
            diagnostics["reducer_evidence"] = [
                dict(item) for item in self._reducer_evidence
            ]
        return diagnostics

    def reducer_matched_count(self, reducer_name: str) -> int:
        row = self._db.execute(
            "SELECT matched_count FROM reducer_summaries WHERE reducer_name = ?",
            (str(reducer_name),),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def has_fact_kinds(self, kinds: Iterable[str]) -> bool:
        normalized = tuple(dict.fromkeys(str(kind) for kind in kinds))
        if not normalized:
            return False
        placeholders = ",".join("?" for _ in normalized)
        return self._db.execute(
            f"SELECT 1 FROM facts WHERE kind IN ({placeholders}) LIMIT 1",
            normalized,
        ).fetchone() is not None

    def close(self) -> None:
        if self._closed:
            return
        connection = self._connection
        path = self._path
        was_sealed = self._sealed
        self._sealed = True
        self._closed = True
        try:
            if connection is not None:
                if not was_sealed:
                    connection.rollback()
        finally:
            self._connection = None
            if connection is not None:
                try:
                    connection.close()
                finally:
                    _delete_sqlite_files(path)
            else:
                _delete_sqlite_files(path)

    def _ensure_readable(self) -> None:
        if self._closed:
            raise RuntimeError("session event index is closed")
        self.seal()

    def _record_facts(
        self,
        seq: int,
        payload_type: str,
        payload: Mapping[str, Any],
        *,
        features: EventFeatures | None = None,
    ) -> None:
        facts: List[tuple[int, str, str, str]] = []
        call_id = features.call_id if features is not None else _payload_call_id(dict(payload))
        if call_id and payload_type in {
            "function_call",
            "custom_tool_call",
            "function_call_output",
            "custom_tool_call_output",
        }:
            kind = "tool_call" if payload_type in {"function_call", "custom_tool_call"} else "tool_output"
            facts.append((seq, kind, call_id, payload_type))
        boundary_id = features.boundary_id if features is not None else str(payload.get("boundary_id", "") or "").strip()
        if boundary_id and payload_type in {"function_call", "custom_tool_call"}:
            facts.append((seq, "boundary", boundary_id, payload_type))
        packet_hash = (
            features.packet_hash
            if features is not None
            else str(
                payload.get("packet_sha256", "") or payload.get("packet_hash", "") or ""
            ).strip().lower()
        )
        if packet_hash:
            facts.append((seq, "packet_hash", packet_hash, payload_type))
        if payload.get("memory_citation") is not None:
            facts.append((seq, "memory_reference", "citation", "candidate"))
        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            if payload.get("memory_import_directive") is not None:
                facts.append((seq, "memory_approval", "embedded", "candidate"))
        if facts:
            self._db.executemany(
                "INSERT OR REPLACE INTO facts(seq, kind, fact_key, fact_value) VALUES (?, ?, ?, ?)",
                facts,
            )

    def duplicate_fact_keys(self, kind: str) -> List[str]:
        self._ensure_readable()
        rows = self._db.execute(
            """
            SELECT fact_key
            FROM facts
            WHERE kind = ?
            GROUP BY fact_key
            HAVING COUNT(*) > 1
            ORDER BY fact_key
            """,
            (kind,),
        )
        return [str(row[0]) for row in rows]

    def duplicate_tool_call_ids(self) -> List[str]:
        self._ensure_readable()
        rows = self._db.execute(
            """
            SELECT fact_key
            FROM facts
            WHERE kind IN ('tool_call', 'tool_output')
            GROUP BY fact_key
            HAVING SUM(CASE WHEN kind = 'tool_call' THEN 1 ELSE 0 END) > 1
                OR SUM(CASE WHEN kind = 'tool_output' THEN 1 ELSE 0 END) > 1
            ORDER BY fact_key
            """
        )
        return [str(row[0]) for row in rows]

    def correlated_tool_receipts(
        self,
        *,
        include_failed: bool,
    ) -> "DiskBackedToolReceipts":
        self._ensure_correlated_receipts()
        return DiskBackedToolReceipts(self, include_failed=include_failed)

    def successful_correlated_call_payload(self, output_seq: int) -> Dict[str, Any]:
        self._ensure_correlated_receipts()
        row = self._db.execute(
            """
            SELECT calls.*
            FROM correlated_receipts AS receipts
            JOIN event_payloads AS calls ON calls.seq = receipts.call_seq
            WHERE receipts.output_seq = ? AND receipts.succeeded = 1
            """,
            (int(output_seq),),
        ).fetchone()
        return _payload_from_event_view_row(row) if row is not None else {}

    @property
    def text_records_ready(self) -> bool:
        return self._text_records_ready

    def begin_text_records(self) -> None:
        self._ensure_readable()
        self._db.execute("DELETE FROM text_records")
        self._db.execute("DELETE FROM catalog_candidate_records")
        self._db.execute("DELETE FROM orchestration_protocol_calls")
        self._text_record_count = 0
        self._text_records_ready = False

    def append_text_record(
        self,
        event_seq: int,
        record: SessionTextRecord,
        *,
        lowered: str | None = None,
    ) -> None:
        passive = _is_passive_text(record.text)
        stored_text = _strip_passive_prefix(record.text)
        record_lowered = record.text.lower() if lowered is None else str(lowered)
        clean_lowered = stored_text.lower() if lowered is None else record_lowered
        analysis_text = stored_text
        if record.payload_type in {"function_call", "custom_tool_call"}:
            stored_text = ""
            analysis_text = f"{record.name} {record.arguments}"
            clean_lowered = analysis_text.lower()
        analysis_record = SessionTextRecord(
            text=(PASSIVE_REFERENCE_PREFIX + analysis_text if passive else analysis_text),
            payload_type=record.payload_type,
            role=record.role,
            call_id=record.call_id,
            name=record.name,
            arguments=record.arguments,
            exit_codes=record.exit_codes,
            trusted_host_native_fast_path=record.trusted_host_native_fast_path,
            trusted_front_door_runtime=record.trusted_front_door_runtime,
            trusted_correlated_tool_runtime=record.trusted_correlated_tool_runtime,
            sql_requirement=record.sql_requirement,
        )
        sql_requirement = _is_sql_requirement_record(
            analysis_record,
            lowered=clean_lowered,
        )
        if record.payload_type in {"host_front_door", "host_native_front_door"}:
            self._db.execute(
                "UPDATE events SET trusted_host_native_fast_path = ? WHERE seq = ?",
                (int(record.trusted_host_native_fast_path), int(event_seq)),
            )
        self._db.execute(
            """
            INSERT INTO text_records (
                record_seq, event_seq, text, arguments, passive,
                trusted_front_door_runtime, trusted_correlated_tool_runtime,
                sql_requirement
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._text_record_count,
                int(event_seq),
                stored_text,
                record.arguments,
                int(passive),
                int(record.trusted_front_door_runtime),
                int(record.trusted_correlated_tool_runtime),
                int(sql_requirement),
            ),
        )
        if not passive:
            self._analysis_accumulators["combined_text"].add(
                analysis_text,
                lowered=clean_lowered,
            )
            if not _looks_like_front_door_runtime_output(clean_lowered):
                self._analysis_accumulators["decision_text"].add(
                    analysis_text,
                    lowered=clean_lowered,
                )
                if _mentions_browser_or_local_app_qa(clean_lowered):
                    self._analysis_browser_or_local_app_qa = True
        if sql_requirement:
            self._analysis_accumulators["sql_scope_text"].add(
                analysis_text,
                lowered=clean_lowered,
            )
            if (
                "function_call" in clean_lowered
                and not _looks_like_front_door_prompt_bootstrap(clean_lowered)
                and "kh_front_door" not in clean_lowered
                and "always_on_front_door" not in clean_lowered
            ):
                self._analysis_accumulators["non_front_door_tool_text"].add(
                    clean_lowered,
                    lowered=clean_lowered,
                )
        if _has_catalog_candidate(record_lowered, self._catalog_observation_index):
            self._db.execute(
                "INSERT INTO catalog_candidate_records(record_seq) VALUES (?)",
                (self._text_record_count,),
            )
        if (
            not passive
            and record.payload_type in {"function_call", "custom_tool_call"}
        ):
            validates_bundle = (
                "validate_large_work_orchestration_bundle" in record_lowered
            )
            audits_roles = any(
                marker in record_lowered
                for marker in (
                    "audit_role_execution",
                    "dispatch_project_workflow",
                    "async_project_workflow",
                )
            )
            if validates_bundle or audits_roles:
                self._db.execute(
                    """
                    INSERT INTO orchestration_protocol_calls(
                        record_seq, validates_bundle, audits_roles
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        self._text_record_count,
                        int(validates_bundle),
                        int(audits_roles),
                    ),
                )
        if record.payload_type in {"function_call_output", "custom_tool_call_output"}:
            receipt_rows: List[tuple[int, str, str]] = []
            if "provider_selection_receipt" in record_lowered:
                selection_data = _front_door_json(_strip_passive_prefix(record.text))
                selection_receipt = selection_data.get("provider_selection_receipt")
                if isinstance(selection_receipt, Mapping):
                    receipt_id = selection_receipt.get("provider_selection_receipt_id")
                    if type(receipt_id) is str and receipt_id:
                        receipt_rows.append(
                            (self._text_record_count, "selection", receipt_id)
                        )
            if "runtime_receipt" in record_lowered and "cli_inputs" in record_lowered:
                binding_data = _sql_final_binding_receipt(
                    _strip_passive_prefix(record.text)
                )
                runtime_receipt = binding_data.get("runtime_receipt")
                if isinstance(runtime_receipt, Mapping):
                    receipt_id = runtime_receipt.get("receipt_id")
                    if type(receipt_id) is str and receipt_id:
                        receipt_rows.append(
                            (self._text_record_count, "binding", receipt_id)
                        )
            if receipt_rows:
                self._db.executemany(
                    """
                    INSERT OR IGNORE INTO sql_runtime_receipt_facts(
                        record_seq, receipt_kind, receipt_id
                    ) VALUES (?, ?, ?)
                    """,
                    receipt_rows,
                )
        self._text_record_count += 1

    def finalize_analysis_summary(self) -> None:
        if self._analysis_summary_ready:
            return
        self._finalize_analysis_scalar_facts()
        data = {
            name: accumulator.render()
            for name, accumulator in self._analysis_accumulators.items()
        }
        data["browser_or_local_app_qa"] = self._analysis_browser_or_local_app_qa
        data["catalog_observations"] = self._catalog_observations_summary
        self._db.execute(
            "INSERT OR REPLACE INTO analysis_summaries(summary_name, data_json) VALUES (?, ?)",
            ("text_analysis", _canonical_json(data)),
        )
        self._analysis_accumulators.clear()
        self._catalog_observations_summary.clear()
        self._catalog_skills.clear()
        self._catalog_observation_index = None
        self._analysis_summary_ready = True

    def _finalize_analysis_scalar_facts(self) -> None:
        if not self._catalog_skills:
            return
        rows = self._db.execute(
            """
            SELECT text_records.text, events.payload_type,
                   events.role, events.name, text_records.arguments,
                   text_records.passive, events.call_id,
                   events.trusted_host_native_fast_path,
                   text_records.trusted_front_door_runtime,
                   text_records.trusted_correlated_tool_runtime,
                   text_records.sql_requirement
            FROM catalog_candidate_records AS candidates
            JOIN text_records
              ON text_records.record_seq = candidates.record_seq
            JOIN events ON events.seq = text_records.event_seq
            ORDER BY candidates.record_seq
            """
        )

        def catalog_records() -> Iterator[SessionTextRecord]:
            for (
                stored_text,
                payload_type,
                role,
                name,
                arguments,
                passive,
                call_id,
                trusted_host_native_fast_path,
                trusted_front_door_runtime,
                trusted_correlated_tool_runtime,
                sql_requirement,
            ) in rows:
                record_text = str(stored_text)
                if str(payload_type) in {"function_call", "custom_tool_call"}:
                    record_text = f"{name} {arguments}"
                if bool(passive):
                    record_text = PASSIVE_REFERENCE_PREFIX + record_text
                record = SessionTextRecord(
                    text=record_text,
                    payload_type=str(payload_type),
                    role=str(role),
                    call_id=str(call_id),
                    name=str(name),
                    arguments=str(arguments),
                    trusted_host_native_fast_path=bool(
                        trusted_host_native_fast_path
                    ),
                    trusted_front_door_runtime=bool(trusted_front_door_runtime),
                    trusted_correlated_tool_runtime=bool(
                        trusted_correlated_tool_runtime
                    ),
                    sql_requirement=bool(sql_requirement),
                )
                yield record

        self._catalog_observations_summary = _catalog_observations(
            catalog_records(),
            self._catalog_skills,
            catalog_index=self._catalog_observation_index,
        )

    def analysis_summary(self) -> Dict[str, Any]:
        if not self._analysis_summary_ready:
            raise RuntimeError("session analysis summary was not finalized")
        row = self._db.execute(
            "SELECT data_json FROM analysis_summaries WHERE summary_name = ?",
            ("text_analysis",),
        ).fetchone()
        return _json_mapping(row[0]) if row is not None else {}

    def seal_text_records(self) -> "DiskBackedSessionTextRecords":
        self._db.commit()
        self._text_records_ready = True
        return DiskBackedSessionTextRecords(self)

    def text_records(self) -> "DiskBackedSessionTextRecords":
        if not self._text_records_ready:
            raise RuntimeError("session text records are not finalized")
        return DiskBackedSessionTextRecords(self)

    def _ensure_correlated_receipts(self) -> None:
        self._ensure_readable()
        if self._receipts_ready:
            return
        self._db.execute("DELETE FROM correlated_receipts")
        self._db.execute("DELETE FROM front_door_receipts")
        rows = self._db.execute(
            """
            SELECT calls.*, outputs.*
            FROM event_payloads AS calls
            JOIN event_payloads AS outputs ON outputs.call_id = calls.call_id
            WHERE calls.event_type = 'response_item'
              AND outputs.event_type = 'response_item'
              AND calls.payload_type IN ('function_call', 'custom_tool_call')
              AND outputs.payload_type IN ('function_call_output', 'custom_tool_call_output')
              AND calls.seq < outputs.seq
              AND calls.call_id IN (
                  SELECT fact_key
                  FROM facts
                  WHERE kind IN ('tool_call', 'tool_output')
                  GROUP BY fact_key
                  HAVING SUM(CASE WHEN kind = 'tool_call' THEN 1 ELSE 0 END) = 1
                     AND SUM(CASE WHEN kind = 'tool_output' THEN 1 ELSE 0 END) = 1
              )
              AND (
                    calls.boundary_id = '' OR
                    calls.boundary_id IN (
                        SELECT fact_key
                        FROM facts
                        WHERE kind = 'boundary'
                        GROUP BY fact_key
                        HAVING COUNT(*) = 1
                    )
              )
              AND (
                    calls.packet_hash = '' OR
                    calls.packet_hash IN (
                        SELECT fact_key
                        FROM facts
                        WHERE kind = 'packet_hash'
                        GROUP BY fact_key
                        HAVING COUNT(*) = 1
                    )
              )
              AND (
                    outputs.packet_hash = '' OR
                    outputs.packet_hash IN (
                        SELECT fact_key
                        FROM facts
                        WHERE kind = 'packet_hash'
                        GROUP BY fact_key
                        HAVING COUNT(*) = 1
                    )
              )
            ORDER BY calls.seq
            """
        )
        receipt_rows: List[tuple[int, int, int, int, int]] = []
        for row in rows:
            call_seq = int(row[0])
            output_offset = _EVENT_PAYLOAD_VIEW_COLUMN_COUNT
            output_seq = int(row[output_offset])
            call = _payload_from_event_view_row(row)
            output = _payload_from_event_view_row(row, output_offset)
            if not _valid_stored_general_tool_pair(
                call,
                output,
                call_packet_hash_valid=bool(row[19]),
                output_packet_hash_valid=bool(row[output_offset + 19]),
            ):
                continue
            succeeded = _runtime_tool_output_succeeded(output)
            receipt_rows.append(
                (
                    int(call_seq),
                    int(output_seq),
                    int(succeeded),
                    int(_is_implementation_call(call)),
                    int(_is_verification_call(call)),
                )
            )
            if len(receipt_rows) >= 1024:
                self._db.executemany(
                    """
                    INSERT INTO correlated_receipts(
                        call_seq, output_seq, succeeded,
                        is_implementation, is_verification
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    receipt_rows,
                )
                receipt_rows.clear()
            if not succeeded or not _is_front_door_runtime_command(
                call,
                _payload_text(call).lower(),
            ):
                continue
            if not _front_door_output_succeeded(output, call):
                continue
            if self._db.execute(
                """
                SELECT 1 FROM events
                WHERE is_request_boundary = 1 AND seq >= ? AND seq < ?
                LIMIT 1
                """,
                (int(call_seq), int(output_seq)),
            ).fetchone():
                continue
            raw_data = _json_object_from_text(_payload_text(output))
            data = _front_door_json(_payload_text(output))
            if not _has_normalized_front_door_receipt(data):
                continue
            if not _valid_host_front_door_provenance(
                call,
                output,
                raw_data,
                duplicate_boundaries=frozenset(),
                duplicate_packet_hashes=frozenset(),
            ):
                continue
            self._db.execute(
                "INSERT INTO front_door_receipts(call_seq, output_seq, data_json) VALUES (?, ?, ?)",
                (int(call_seq), int(output_seq), _canonical_json(data)),
            )
        if receipt_rows:
            self._db.executemany(
                """
                INSERT INTO correlated_receipts(
                    call_seq, output_seq, succeeded,
                    is_implementation, is_verification
                ) VALUES (?, ?, ?, ?, ?)
                """,
                receipt_rows,
            )
        self._db.execute(
            """
            UPDATE text_records
            SET trusted_front_door_runtime = CASE
                    WHEN event_seq IN (
                        SELECT call_seq FROM front_door_receipts
                        UNION ALL
                        SELECT output_seq FROM front_door_receipts
                    ) THEN 1 ELSE 0 END,
                trusted_correlated_tool_runtime = CASE
                    WHEN event_seq IN (
                        SELECT output_seq FROM correlated_receipts
                        WHERE succeeded = 1
                          AND output_seq NOT IN (SELECT output_seq FROM front_door_receipts)
                    ) THEN 1 ELSE 0 END
            """
        )
        self._db.commit()
        self._receipts_ready = True

    def correlated_front_door_receipts(self) -> "DiskBackedFrontDoorReceipts":
        self._ensure_correlated_receipts()
        return DiskBackedFrontDoorReceipts(self)

    def memory_import_decisions(
        self,
        metadata: Mapping[str, Any],
    ) -> "DiskBackedMemoryDecisions":
        self._ensure_correlated_receipts()
        if not self._memory_decisions_ready:
            self._db.execute("DELETE FROM memory_decisions")
            user_rows = self._db.execute(
                """
                SELECT *
                FROM event_payloads
                WHERE payload_type = 'message' AND role = 'user'
                ORDER BY seq
                """
            )
            for row in user_rows:
                decision = _structured_user_memory_import_decision(
                    _payload_from_event_view_row(row),
                    metadata,
                )
                if decision:
                    self._db.execute(
                        "INSERT INTO memory_decisions(event_seq, decision) VALUES (?, ?)",
                        (int(row[0]), decision),
                    )
            for receipt in DiskBackedToolReceipts(self, include_failed=False):
                decision = _authenticated_memory_import_decision(receipt, metadata)
                if decision:
                    self._db.execute(
                        "INSERT OR REPLACE INTO memory_decisions(event_seq, decision) VALUES (?, ?)",
                        (receipt.output_index, decision),
                    )
            self._db.commit()
            self._memory_decisions_ready = True
        return DiskBackedMemoryDecisions(self)

    def record_reducer_summary(
        self,
        *,
        reducer_name: str,
        fact_kind: str,
        matched_count: int,
        first_event_seq: int | None,
        last_event_seq: int | None,
        samples: Sequence[tuple[int, str, str]],
    ) -> None:
        self._db.execute(
            """
            INSERT INTO reducer_summaries (
                reducer_name, fact_kind, matched_count, first_event_seq,
                last_event_seq, finalized
            ) VALUES (?, ?, ?, ?, ?, 1)
            """,
            (
                reducer_name,
                fact_kind,
                int(matched_count),
                first_event_seq,
                last_event_seq,
            ),
        )
        if samples:
            self._db.executemany(
                """
                INSERT INTO reducer_samples (
                    reducer_name, sample_seq, event_seq, fact_key, fact_value
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (reducer_name, sample_seq, event_seq, fact_key, fact_value)
                    for sample_seq, (event_seq, fact_key, fact_value) in enumerate(samples)
                ],
            )


class DiskBackedToolReceipts(SequenceABC[CorrelatedToolReceipt]):
    """Replayable narrow receipt view without a Python receipt corpus."""

    def __init__(
        self,
        events: DiskBackedSessionEvents,
        *,
        include_failed: bool,
    ) -> None:
        self._events = events
        self._include_failed = include_failed

    def __len__(self) -> int:
        where = "" if self._include_failed else "WHERE succeeded = 1"
        row = self._events._db.execute(
            f"SELECT COUNT(*) FROM correlated_receipts {where}"
        ).fetchone()
        return int(row[0]) if row else 0

    def __iter__(self) -> Iterator[CorrelatedToolReceipt]:
        return self.iter_range()

    def iter_range(
        self,
        *,
        after_index: int = -1,
        before_index: int | None = None,
        require_succeeded: bool | None = None,
        implementation_only: bool = False,
        verification_only: bool = False,
    ) -> Iterator[CorrelatedToolReceipt]:
        clauses = ["receipts.call_seq > ?"]
        parameters: List[Any] = [int(after_index)]
        if before_index is not None:
            clauses.append("receipts.output_seq < ?")
            parameters.append(int(before_index))
        if require_succeeded is True or not self._include_failed:
            clauses.append("receipts.succeeded = 1")
        elif require_succeeded is False:
            clauses.append("receipts.succeeded = 0")
        if implementation_only:
            clauses.append("receipts.is_implementation = 1")
        if verification_only:
            clauses.append("receipts.is_verification = 1")
        rows = self._events._db.execute(
            f"""
            SELECT calls.*, outputs.*
            FROM correlated_receipts AS receipts
            JOIN event_payloads AS calls ON calls.seq = receipts.call_seq
            JOIN event_payloads AS outputs ON outputs.seq = receipts.output_seq
            WHERE {' AND '.join(clauses)}
            ORDER BY receipts.call_seq
            """,
            parameters,
        )
        for row in rows:
            output_offset = _EVENT_PAYLOAD_VIEW_COLUMN_COUNT
            call = _payload_from_event_view_row(row)
            output = _payload_from_event_view_row(row, output_offset)
            yield CorrelatedToolReceipt(
                call_index=int(row[0]),
                output_index=int(row[output_offset]),
                call=call,
                output=output,
                data=_json_object_from_text(_payload_text(output)),
            )

    def iter_ordered_by_output(self) -> Iterator[CorrelatedToolReceipt]:
        where = "" if self._include_failed else "WHERE receipts.succeeded = 1"
        rows = self._events._db.execute(
            f"""
            SELECT calls.*, outputs.*
            FROM correlated_receipts AS receipts
            JOIN event_payloads AS calls ON calls.seq = receipts.call_seq
            JOIN event_payloads AS outputs ON outputs.seq = receipts.output_seq
            {where}
            ORDER BY receipts.output_seq
            """
        )
        for row in rows:
            output_offset = _EVENT_PAYLOAD_VIEW_COLUMN_COUNT
            call = _payload_from_event_view_row(row)
            output = _payload_from_event_view_row(row, output_offset)
            yield CorrelatedToolReceipt(
                call_index=int(row[0]),
                output_index=int(row[output_offset]),
                call=call,
                output=output,
                data=_json_object_from_text(_payload_text(output)),
            )

    def __getitem__(self, index: int | slice):
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return list(islice(self, start, stop, step))
        normalized = index if index >= 0 else len(self) + index
        if normalized < 0 or normalized >= len(self):
            raise IndexError("tool receipt index out of range")
        return next(islice(self, normalized, normalized + 1))


class DiskBackedFrontDoorReceipts(MappingABC[int, CorrelatedFrontDoorReceipt]):
    """Indexed receipt mapping without retaining output-index keys in Python."""

    def __init__(self, events: DiskBackedSessionEvents) -> None:
        self._events = events

    def __len__(self) -> int:
        row = self._events._db.execute(
            "SELECT COUNT(*) FROM front_door_receipts"
        ).fetchone()
        return int(row[0]) if row else 0

    def __iter__(self) -> Iterator[int]:
        rows = self._events._db.execute(
            "SELECT output_seq FROM front_door_receipts ORDER BY output_seq"
        )
        return (int(row[0]) for row in rows)

    def __getitem__(self, output_index: int) -> CorrelatedFrontDoorReceipt:
        row = self._events._db.execute(
            """
            SELECT call_seq, output_seq, data_json
            FROM front_door_receipts
            WHERE output_seq = ?
            """,
            (int(output_index),),
        ).fetchone()
        if row is None:
            raise KeyError(output_index)
        return CorrelatedFrontDoorReceipt(
            call_index=int(row[0]),
            output_index=int(row[1]),
            data=_json_mapping(row[2]),
        )

    def items(self):
        rows = self._events._db.execute(
            """
            SELECT call_seq, output_seq, data_json
            FROM front_door_receipts
            ORDER BY output_seq
            """
        )
        for call_seq, output_seq, data_json in rows:
            output_index = int(output_seq)
            yield output_index, CorrelatedFrontDoorReceipt(
                call_index=int(call_seq),
                output_index=output_index,
                data=_json_mapping(data_json),
            )

    def values(self):
        for _output_index, receipt in self.items():
            yield receipt


class DiskBackedDuplicateFactKeys:
    """Membership-only duplicate lookup backed by the indexed fact table."""

    def __init__(self, events: DiskBackedSessionEvents, kind: str) -> None:
        self._events = events
        self._kind = kind

    def __contains__(self, value: object) -> bool:
        if not isinstance(value, str) or not value:
            return False
        row = self._events._db.execute(
            """
            SELECT 1
            FROM facts
            WHERE kind = ? AND fact_key = ?
            GROUP BY fact_key
            HAVING COUNT(*) > 1
            """,
            (self._kind, value),
        ).fetchone()
        return row is not None


class DiskBackedMemoryDecisions(MappingABC[int, str]):
    """Ordered scoped approval/revocation decisions stored in SQLite."""

    def __init__(self, events: DiskBackedSessionEvents) -> None:
        self._events = events

    def __len__(self) -> int:
        row = self._events._db.execute(
            "SELECT COUNT(*) FROM memory_decisions"
        ).fetchone()
        return int(row[0]) if row else 0

    def __iter__(self) -> Iterator[int]:
        rows = self._events._db.execute(
            "SELECT event_seq FROM memory_decisions ORDER BY event_seq"
        )
        return (int(row[0]) for row in rows)

    def __getitem__(self, event_seq: int) -> str:
        row = self._events._db.execute(
            "SELECT decision FROM memory_decisions WHERE event_seq = ?",
            (int(event_seq),),
        ).fetchone()
        if row is None:
            raise KeyError(event_seq)
        return str(row[0])

    def items(self):
        rows = self._events._db.execute(
            "SELECT event_seq, decision FROM memory_decisions ORDER BY event_seq"
        )
        for event_seq, decision in rows:
            yield int(event_seq), str(decision)

    def values(self):
        rows = self._events._db.execute(
            "SELECT decision FROM memory_decisions ORDER BY event_seq"
        )
        return (str(row[0]) for row in rows)


class DiskBackedVerifiedCorrectionIndexes:
    """Indexed PB correction-verification facts with bounded projection."""

    def __init__(self, events: DiskBackedSessionEvents) -> None:
        self._events = events

    def __len__(self) -> int:
        row = self._events._db.execute(
            "SELECT COUNT(*) FROM pb_verified_corrections"
        ).fetchone()
        return int(row[0]) if row else 0

    def __iter__(self) -> Iterator[int]:
        rows = self._events._db.execute(
            "SELECT correction_seq FROM pb_verified_corrections ORDER BY correction_seq"
        )
        return (int(row[0]) for row in rows)

    def has_after(self, event_seq: int) -> bool:
        return self._events._db.execute(
            """
            SELECT 1 FROM pb_verified_corrections
            WHERE correction_seq > ?
            LIMIT 1
            """,
            (int(event_seq),),
        ).fetchone() is not None

    def bounded_samples(self, limit: int = _PB_FRONT_DOOR_HISTORY_SAMPLE_LIMIT) -> List[int]:
        rows = self._events._db.execute(
            """
            SELECT correction_seq FROM pb_verified_corrections
            ORDER BY correction_seq
            LIMIT ?
            """,
            (max(0, int(limit)),),
        )
        return [int(row[0]) for row in rows]


class DiskBackedSessionTextRecords(SequenceABC[SessionTextRecord]):
    """Replayable text-feature sequence with only bounded synthetic tail rows."""

    def __init__(self, events: DiskBackedSessionEvents) -> None:
        self._events = events
        self._extras: List[SessionTextRecord] = []

    def append(self, record: SessionTextRecord) -> None:
        self._extras.append(record)

    def __len__(self) -> int:
        return self._events._text_record_count + len(self._extras)

    def __iter__(self) -> Iterator[SessionTextRecord]:
        for _record_seq, record in self.iter_indexed_records():
            yield record
        yield from self._extras

    def iter_indexed_records(
        self,
        *,
        start: int = 0,
        stop: int | None = None,
    ) -> Iterator[tuple[int, SessionTextRecord]]:
        clauses = ["text_records.record_seq >= ?"]
        parameters: List[Any] = [max(0, int(start))]
        if stop is not None:
            clauses.append("text_records.record_seq < ?")
            parameters.append(max(0, int(stop)))
        rows = self._events._db.execute(
            f"""
            SELECT text_records.text, events.payload_type, events.role,
                   events.call_id, events.name, text_records.arguments,
                   events.exit_code_json, events.return_code_json,
                   events.returncode_json, text_records.passive,
                   events.trusted_host_native_fast_path,
                   text_records.trusted_front_door_runtime,
                   text_records.trusted_correlated_tool_runtime,
                   text_records.sql_requirement
            FROM text_records
            JOIN events ON events.seq = text_records.event_seq
            WHERE {' AND '.join(clauses)}
            ORDER BY text_records.record_seq
            """,
            parameters,
        )
        for record_seq, row in enumerate(rows, start=max(0, int(start))):
            yield record_seq, _text_record_from_joined_row(row)

    def iter_text_values(self) -> Iterator[str]:
        rows = self._events._db.execute(
            """
            SELECT text_records.text, events.payload_type, events.name,
                   text_records.arguments, text_records.passive
            FROM text_records
            JOIN events ON events.seq = text_records.event_seq
            ORDER BY text_records.record_seq
            """
        )
        for row in rows:
            text = str(row[0])
            if str(row[1]) in {"function_call", "custom_tool_call"}:
                text = f"{row[2]} {row[3]}"
            if bool(row[4]):
                text = PASSIVE_REFERENCE_PREFIX + text
            yield text
        for record in self._extras:
            yield record.text

    def iter_observation_records(self) -> Iterator[SessionTextRecord]:
        rows = self._events._db.execute(
            """
            SELECT text_records.text, events.payload_type, events.role,
                   events.call_id, events.name, text_records.arguments,
                   events.exit_code_json, events.return_code_json,
                   events.returncode_json, text_records.passive,
                   events.trusted_host_native_fast_path,
                   text_records.trusted_front_door_runtime,
                   text_records.trusted_correlated_tool_runtime,
                   text_records.sql_requirement
            FROM text_records
            JOIN events ON events.seq = text_records.event_seq
            ORDER BY text_records.record_seq
            """
        )
        for row in rows:
            yield _text_record_from_joined_row(row)
        yield from self._extras

    def iter_sql_requirement_records(self) -> Iterator[SessionTextRecord]:
        rows = self._events._db.execute(
            """
            SELECT text_records.text, events.payload_type, events.role,
                   events.call_id, events.name, text_records.arguments,
                   events.exit_code_json, events.return_code_json,
                   events.returncode_json, text_records.passive,
                   events.trusted_host_native_fast_path,
                   text_records.trusted_front_door_runtime,
                   text_records.trusted_correlated_tool_runtime,
                   text_records.sql_requirement
            FROM text_records
            JOIN events ON events.seq = text_records.event_seq
            WHERE text_records.sql_requirement = 1
            ORDER BY text_records.record_seq
            """
        )
        for row in rows:
            yield _text_record_from_joined_row(row)
        yield from self._extras

    def iter_orchestration_protocol_calls(
        self,
    ) -> Iterator[tuple[int, SessionTextRecord, bool, bool]]:
        self._events._protocol_correlation_replay_count += 1
        rows = self._events._db.execute(
            """
            SELECT protocol.record_seq,
                   text_records.text, events.payload_type, events.role,
                   events.call_id, events.name, text_records.arguments,
                   events.exit_code_json, events.return_code_json,
                   events.returncode_json, text_records.passive,
                   events.trusted_host_native_fast_path,
                   text_records.trusted_front_door_runtime,
                   text_records.trusted_correlated_tool_runtime,
                   text_records.sql_requirement,
                   protocol.validates_bundle, protocol.audits_roles
            FROM orchestration_protocol_calls AS protocol
            JOIN text_records ON text_records.record_seq = protocol.record_seq
            JOIN events ON events.seq = text_records.event_seq
            ORDER BY protocol.record_seq
            """
        )
        for row in rows:
            yield (
                int(row[0]),
                _text_record_from_joined_row(row, 1),
                bool(row[15]),
                bool(row[16]),
            )

    def immediate_structured_output(self, call_record_index: int) -> Dict[str, Any]:
        row = self._events._db.execute(
            """
            SELECT outputs.text
            FROM text_records AS calls
            JOIN events AS call_events ON call_events.seq = calls.event_seq
            JOIN text_records AS outputs ON outputs.record_seq > calls.record_seq
            JOIN events AS output_events ON output_events.seq = outputs.event_seq
            WHERE calls.record_seq = ?
              AND output_events.payload_type IN (
                    'function_call_output', 'custom_tool_call_output'
              )
              AND (
                    call_events.call_id = '' OR
                    output_events.call_id = call_events.call_id
              )
              AND outputs.record_seq < COALESCE(
                    (
                        SELECT MIN(next_calls.record_seq)
                        FROM text_records AS next_calls
                        JOIN events AS next_events
                          ON next_events.seq = next_calls.event_seq
                        WHERE next_calls.record_seq > calls.record_seq
                          AND next_events.payload_type IN (
                                'function_call', 'custom_tool_call'
                          )
                    ),
                    ?
              )
            ORDER BY outputs.record_seq
            LIMIT 1
            """,
            (int(call_record_index), self._events._text_record_count + 1),
        ).fetchone()
        return _json_object_from_text(str(row[0])) if row is not None else {}

    def __getitem__(self, index: int | slice):
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return list(islice(self, start, stop, step))
        normalized = index if index >= 0 else len(self) + index
        if normalized < 0 or normalized >= len(self):
            raise IndexError("session text record index out of range")
        if normalized >= self._events._text_record_count:
            return self._extras[normalized - self._events._text_record_count]
        row = self._events._db.execute(
            """
            SELECT text_records.text, events.payload_type, events.role,
                   events.call_id, events.name, text_records.arguments,
                   events.exit_code_json, events.return_code_json,
                   events.returncode_json, text_records.passive,
                   events.trusted_host_native_fast_path,
                   text_records.trusted_front_door_runtime,
                   text_records.trusted_correlated_tool_runtime,
                   text_records.sql_requirement
            FROM text_records
            JOIN events ON events.seq = text_records.event_seq
            WHERE text_records.record_seq = ?
            """,
            (normalized,),
        ).fetchone()
        if row is None:
            raise IndexError("session text record index out of range")
        return _text_record_from_joined_row(row)

    @staticmethod
    def _record_from_row(row: Sequence[Any], offset: int) -> SessionTextRecord:
        return _text_record_from_joined_row(row, offset)

    def correlated_output_record_index(
        self,
        call_record_index: int,
        *,
        before_index: int,
    ) -> int:
        row = self._events._db.execute(
            """
            SELECT outputs.record_seq
            FROM text_records AS calls
            JOIN events AS call_events ON call_events.seq = calls.event_seq
            JOIN events AS output_events
              ON output_events.call_id = call_events.call_id
             AND output_events.payload_type = CASE call_events.payload_type
                   WHEN 'function_call' THEN 'function_call_output'
                   WHEN 'custom_tool_call' THEN 'custom_tool_call_output'
                   ELSE ''
                 END
            JOIN text_records AS outputs ON outputs.event_seq = output_events.seq
            WHERE calls.record_seq = ?
              AND call_events.call_id <> ''
              AND outputs.record_seq > calls.record_seq
              AND outputs.record_seq < ?
            ORDER BY outputs.record_seq
            LIMIT 1
            """,
            (int(call_record_index), int(before_index)),
        ).fetchone()
        return int(row[0]) if row is not None else -1

    def correlated_call_record_index(self, output_record_index: int) -> int:
        row = self._events._db.execute(
            """
            SELECT calls.record_seq
            FROM text_records AS outputs
            JOIN events AS output_events ON output_events.seq = outputs.event_seq
            JOIN events AS call_events
              ON call_events.call_id = output_events.call_id
             AND call_events.payload_type = CASE output_events.payload_type
                   WHEN 'function_call_output' THEN 'function_call'
                   WHEN 'custom_tool_call_output' THEN 'custom_tool_call'
                   ELSE ''
                 END
            JOIN text_records AS calls ON calls.event_seq = call_events.seq
            WHERE outputs.record_seq = ?
              AND output_events.call_id <> ''
              AND calls.record_seq < outputs.record_seq
            ORDER BY calls.record_seq DESC
            LIMIT 1
            """,
            (int(output_record_index),),
        ).fetchone()
        return int(row[0]) if row is not None else -1

    def iter_front_door_pairs(
        self,
        *,
        lower_bound: int,
        upper_bound: int,
    ) -> Iterator[
        tuple[
            int,
            SessionTextRecord,
            int,
            SessionTextRecord,
            Dict[str, Any],
            Dict[str, Any],
        ]
    ]:
        rows = self._events._db.execute(
            """
            SELECT calls.record_seq,
                   calls.text, call_events.payload_type, call_events.role,
                   call_events.call_id, call_events.name, calls.arguments,
                   call_events.exit_code_json, call_events.return_code_json,
                   call_events.returncode_json, calls.passive,
                   call_events.trusted_host_native_fast_path,
                   calls.trusted_front_door_runtime,
                   calls.trusted_correlated_tool_runtime,
                   calls.sql_requirement,
                   outputs.record_seq,
                   outputs.text, output_events.payload_type, output_events.role,
                   output_events.call_id, output_events.name, outputs.arguments,
                   output_events.exit_code_json, output_events.return_code_json,
                   output_events.returncode_json, outputs.passive,
                   output_events.trusted_host_native_fast_path,
                   outputs.trusted_front_door_runtime,
                   outputs.trusted_correlated_tool_runtime,
                   outputs.sql_requirement,
                   call_payloads.*, output_payloads.*
            FROM events AS call_events
            JOIN events AS output_events
              ON output_events.call_id = call_events.call_id
            JOIN text_records AS calls ON calls.event_seq = call_events.seq
            JOIN text_records AS outputs ON outputs.event_seq = output_events.seq
            JOIN event_payloads AS call_payloads ON call_payloads.seq = call_events.seq
            JOIN event_payloads AS output_payloads ON output_payloads.seq = output_events.seq
            WHERE calls.record_seq > ? AND outputs.record_seq < ?
              AND call_events.event_type = 'response_item'
              AND output_events.event_type = 'response_item'
              AND call_events.payload_type IN ('function_call', 'custom_tool_call')
              AND output_events.payload_type = CASE call_events.payload_type
                    WHEN 'function_call' THEN 'function_call_output'
                    ELSE 'custom_tool_call_output'
                  END
              AND call_events.seq < output_events.seq
              AND call_events.call_id <> ''
              AND call_events.call_id IN (
                  SELECT fact_key
                  FROM facts
                  WHERE kind IN ('tool_call', 'tool_output')
                  GROUP BY fact_key
                  HAVING SUM(CASE WHEN kind = 'tool_call' THEN 1 ELSE 0 END) = 1
                     AND SUM(CASE WHEN kind = 'tool_output' THEN 1 ELSE 0 END) = 1
              )
            ORDER BY outputs.record_seq
            """,
            (int(lower_bound), int(upper_bound)),
        )
        for row in rows:
            call_payload_offset = 30
            output_payload_offset = call_payload_offset + _EVENT_PAYLOAD_VIEW_COLUMN_COUNT
            yield (
                int(row[0]),
                self._record_from_row(row, 1),
                int(row[15]),
                self._record_from_row(row, 16),
                _payload_from_event_view_row(row, call_payload_offset),
                _payload_from_event_view_row(row, output_payload_offset),
            )


class DiskBackedSqlProviderSelections(SequenceABC[Dict[str, Any]]):
    """Narrow finalized SQL-provider selection facts."""

    def __init__(self, events: DiskBackedSessionEvents) -> None:
        self._events = events

    @staticmethod
    def _item(row: Sequence[Any]) -> Dict[str, Any]:
        return {
            "provider_id": str(row[0]),
            "provider_path": str(row[1]),
            "provider_source": str(row[2]),
            "call_index": int(row[3]),
            "output_index": int(row[4]),
            "selection_sha256": str(row[5]),
            "provenance_valid": bool(row[6]),
            "provenance_errors": list(_json_scalar_sequence(row[7])),
        }

    def __len__(self) -> int:
        row = self._events._db.execute(
            "SELECT COUNT(*) FROM sql_provider_selections"
        ).fetchone()
        return int(row[0]) if row else 0

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        rows = self._events._db.execute(
            """
            SELECT provider_id, provider_path, provider_source,
                   call_record_seq, output_record_seq, selection_sha256,
                   provenance_valid, provenance_errors_json
            FROM sql_provider_selections
            ORDER BY output_record_seq
            """
        )
        return (self._item(row) for row in rows)

    def __getitem__(self, index: int | slice):
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return list(islice(self, start, stop, step))
        normalized = index if index >= 0 else len(self) + index
        if normalized < 0 or normalized >= len(self):
            raise IndexError("SQL provider selection index out of range")
        row = self._events._db.execute(
            """
            SELECT provider_id, provider_path, provider_source,
                   call_record_seq, output_record_seq, selection_sha256,
                   provenance_valid, provenance_errors_json
            FROM sql_provider_selections
            ORDER BY output_record_seq
            LIMIT 1 OFFSET ?
            """,
            (normalized,),
        ).fetchone()
        if row is None:
            raise IndexError("SQL provider selection index out of range")
        return self._item(row)

    def has_valid_selection(self) -> bool:
        return self._events._db.execute(
            """
            SELECT 1 FROM sql_provider_selections
            WHERE provenance_valid = 1
            LIMIT 1
            """
        ).fetchone() is not None

    def latest_before(self, record_seq: int) -> Dict[str, Any]:
        row = self._events._db.execute(
            """
            SELECT provider_id, provider_path, provider_source,
                   call_record_seq, output_record_seq, selection_sha256,
                   provenance_valid, provenance_errors_json
            FROM sql_provider_selections
            WHERE output_record_seq < ?
            ORDER BY output_record_seq DESC
            LIMIT 1
            """,
            (int(record_seq),),
        ).fetchone()
        return self._item(row) if row is not None else {}


class SessionTextView(Iterable[str]):
    def __init__(
        self,
        records: Sequence[SessionTextRecord],
        *,
        sql_only: bool = False,
    ) -> None:
        self._records = records
        self._sql_only = sql_only

    def __iter__(self) -> Iterator[str]:
        if isinstance(self._records, DiskBackedSessionTextRecords):
            if not self._sql_only:
                for text in self._records.iter_text_values():
                    if not _is_passive_text(text):
                        yield _strip_passive_prefix(text)
                return
            records: Iterable[SessionTextRecord] = (
                self._records.iter_sql_requirement_records()
            )
        else:
            records = self._records
        for record in records:
            if _is_passive_text(record.text):
                continue
            if self._sql_only and not _is_sql_requirement_record(record):
                continue
            yield _strip_passive_prefix(record.text)


_SESSION_EVENT_INDEX: ContextVar[SessionEventIndex | None] = ContextVar(
    "session_skill_audit_event_index",
    default=None,
)


_AUDIT_REDUCER_NAMES = (
    "session_postmortem",
    "session_text_records",
    "merged_thread_goal_state",
    "kh_front_door",
    "immediate_next_skill",
    "front_door_execution_gate",
    "front_door_latency",
    "large_output_latency",
    "stale_skill_cache",
    "cross_scope_context",
    "target_substitution",
    "global_memory_scope",
    "project_discovery",
    "pb_migration",
    "brainstorm_target_inspection",
    "brainstorm_option_choice",
    "first_visible_brainstorm_response",
    "instruction_supersession",
    "aggregate_skill_runtime",
    "authoritative_reference_order",
    "forbidden_residual_completion",
    "required_delegation",
    "function_call_count",
    "implementation_tool_samples",
    "global_memory_import_request",
    "scoped_memory_import",
    "front_door_token_evidence",
    "duplicate_tool_identity",
    "auditable_user_request",
    "session_integrity",
    "skill_observations",
)


_REDUCER_SAMPLE_LIMIT = 3


def _derive_audit_reducer_matches(
    *,
    payload_type: str,
    role: str,
    literal_hits: frozenset[str],
    has_text: bool,
    call_id: str,
    boundary_id: str,
    packet_hash: str,
) -> Iterator[tuple[str, str]]:
    """Classify one original event into a fixed-size reducer fact tuple."""

    def hit(fragment: str) -> bool:
        return any(fragment in value for value in literal_hits)

    is_call = payload_type in {"function_call", "custom_tool_call"}
    is_output = payload_type in {"function_call_output", "custom_tool_call_output"}
    is_message = payload_type in {"message", "agent_message", "task_complete"}
    if payload_type in {
        "message",
        "agent_message",
        "task_complete",
        "thread_goal_updated",
        "function_call",
        "custom_tool_call",
        "function_call_output",
        "custom_tool_call_output",
    }:
        yield "session_postmortem", "postmortem_event"
    if has_text:
        yield "session_text_records", "text_record"
    if payload_type == "thread_goal_updated":
        yield "merged_thread_goal_state", "goal_update"
    if hit("front_door") or hit("always-on-front-door"):
        yield "kh_front_door", "front_door_signal"
    if hit("immediate_next_skill"):
        yield "immediate_next_skill", "immediate_skill_signal"
    if hit("execution_gate"):
        yield "front_door_execution_gate", "execution_gate_signal"
    if role == "user" or hit("front_door"):
        yield "front_door_latency", "latency_boundary"
    if is_output and has_text:
        yield "large_output_latency", "tool_output"
    if hit("kh-uaf-marketplace") and hit("skill"):
        yield "stale_skill_cache", "skill_cache_signal"
    if is_call and (hit("read_thread") or hit("rollout")):
        yield "cross_scope_context", "cross_scope_read"
    if role == "user" or is_call:
        yield "target_substitution", "target_path_signal"
    if hit("memory"):
        yield "global_memory_scope", "memory_scope_signal"
    if role == "user" and has_text:
        yield "project_discovery", "user_project_signal"
    if hit("powerbuilder") or hit("pb-to-csharp"):
        yield "pb_migration", "pb_signal"
    if hit("brainstorm") or (is_call and hit("get-childitem")):
        yield "brainstorm_target_inspection", "brainstorm_inspection_signal"
    if hit("option") or hit("choose") or hit("선택"):
        yield "brainstorm_option_choice", "option_choice_signal"
    if role == "assistant" and has_text:
        yield "first_visible_brainstorm_response", "assistant_response"
    if role in {"user", "assistant"}:
        yield "instruction_supersession", "instruction_signal"
    if hit("skill") or hit("harness") or hit("runtime"):
        yield "aggregate_skill_runtime", "skill_runtime_signal"
    if role == "user" or is_call:
        yield "authoritative_reference_order", "reference_order_signal"
    if role == "user" or is_call or payload_type == "task_complete":
        yield "forbidden_residual_completion", "residual_signal"
    if hit("subagent") or hit("parallel") or hit("delegate"):
        yield "required_delegation", "delegation_signal"
    if is_call:
        yield "function_call_count", "function_call"
        yield "implementation_tool_samples", "tool_call"
    if role == "user" and hit("memory"):
        yield "global_memory_import_request", "memory_request_signal"
    if hit("memory_import"):
        yield "scoped_memory_import", "memory_import_signal"
    if hit("token_optimizer") or hit("token_optimization"):
        yield "front_door_token_evidence", "token_signal"
    if (is_call or is_output) and call_id:
        yield "duplicate_tool_identity", "tool_identity"
    if role == "user" and is_message:
        yield "auditable_user_request", "user_request"
    if boundary_id or packet_hash:
        yield "session_integrity", "provenance"
    if has_text:
        yield "skill_observations", "observation_text"


def _audit_reducer_matches(
    features: EventFeatures,
) -> Iterator[tuple[str, str]]:
    """Replay reducer ownership already extracted from the original event."""

    yield from features.reducer_matches


@dataclass
class _AuditReducer:
    """A bounded reducer that owns domain facts and a deterministic final row."""

    name: str
    consume_count: int = 0
    matched_count: int = 0
    first_event_seq: int | None = None
    last_event_seq: int | None = None
    samples: List[tuple[int, str, str]] = field(default_factory=list)
    finalized: bool = False
    finalize_count: int = 0
    output_fact_kind: str = ""
    output: Dict[str, Any] | None = None
    previous_call_was_passive: bool = False
    untrusted_assessment_active: bool = False
    latest_user_trigger: str = ""
    work_activity_since_trigger: bool = False
    active_goal: bool = False
    latest_assistant_text: str = ""
    latest_completion_seq: int | None = None

    def consume(
        self,
        event_seq: int,
        event: Mapping[str, Any],
        features: EventFeatures,
        store: DiskBackedSessionEvents,
    ) -> None:
        if self.finalized:
            raise RuntimeError(f"audit reducer already finalized: {self.name}")
        self.consume_count += 1
        if self.name == "session_text_records":
            self._consume_text_record(event_seq, event, store, features=features)
        elif self.name == "instruction_supersession":
            self._consume_correction(event_seq, event, store)
        for reducer_name, fact_kind in _audit_reducer_matches(features):
            if reducer_name != self.name:
                continue
            fact_key = features.call_id or features.payload_type or features.event_type or "event"
            fact_value = _short(features.text, 180) if features.text else fact_key
            self.observe(event_seq, fact_kind, fact_key, fact_value)
            return

    def observe(
        self,
        event_seq: int,
        fact_kind: str,
        fact_key: str,
        fact_value: str,
    ) -> None:
        if self.finalized:
            raise RuntimeError(f"audit reducer already finalized: {self.name}")
        if not self.output_fact_kind:
            self.output_fact_kind = fact_kind
        self.matched_count += 1
        if self.first_event_seq is None:
            self.first_event_seq = event_seq
        self.last_event_seq = event_seq
        if len(self.samples) < _REDUCER_SAMPLE_LIMIT:
            self.samples.append((event_seq, fact_key, fact_value))

    def finalize(self, store: DiskBackedSessionEvents) -> None:
        if self.finalized:
            raise RuntimeError(f"audit reducer finalized more than once: {self.name}")
        fact_kind = self.output_fact_kind or f"{self.name}_fact"
        store.record_reducer_summary(
            reducer_name=self.name,
            fact_kind=fact_kind,
            matched_count=self.matched_count,
            first_event_seq=self.first_event_seq,
            last_event_seq=self.last_event_seq,
            samples=self.samples,
        )
        self.finalize_count += 1
        self.finalized = True
        self.output = {
            "fact_kind": fact_kind,
            "matched_count": self.matched_count,
            "first_event_seq": self.first_event_seq,
            "last_event_seq": self.last_event_seq,
            "sample_count": len(self.samples),
        }

    def evidence(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "consume_count": self.consume_count,
            "finalize_count": self.finalize_count,
            "finalized": self.finalized,
            "output": dict(self.output or {}),
        }

    def _consume_text_record(
        self,
        event_seq: int,
        event: Mapping[str, Any],
        store: DiskBackedSessionEvents,
        *,
        features: EventFeatures | None = None,
    ) -> None:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            self.previous_call_was_passive = False
            return
        payload_type = features.payload_type if features is not None else str(payload.get("type", ""))
        role = features.role if features is not None else str(payload.get("role", "")).lower()
        if payload_type == "message" and role in {"developer", "system"}:
            self.previous_call_was_passive = False
            return
        text = features.text if features is not None else _payload_text(payload)
        if not text:
            self.previous_call_was_passive = False
            return
        lowered = features.lowered if features is not None else text.lower()
        is_untrusted_assessment = _is_untrusted_assessment_transcript(lowered)
        if payload_type == "message" and role == "user":
            if is_untrusted_assessment:
                self.untrusted_assessment_active = True
            elif not _is_synthetic_context_message(text):
                self.untrusted_assessment_active = False
                self.latest_user_trigger = text
                self.work_activity_since_trigger = False
        trusted_fast_path = _is_trusted_host_native_fast_path_receipt(
            payload,
            text,
            self.latest_user_trigger,
            self.work_activity_since_trigger,
        )
        passive = (
            self.untrusted_assessment_active
            or _is_synthetic_context_message(text)
            or _passive_reference(lowered)
            or (
                payload_type in {"function_call_output", "custom_tool_call_output"}
                and self.previous_call_was_passive
            )
        )
        stored_text = PASSIVE_REFERENCE_PREFIX + text if passive else text
        store.append_text_record(
            event_seq,
            SessionTextRecord(
                text=stored_text,
                payload_type=payload_type,
                role=role,
                call_id=features.call_id if features is not None else _payload_call_id(payload),
                name=str(payload.get("name", "")),
                arguments=_payload_arguments_text(payload),
                exit_codes=_payload_exit_codes(payload),
                trusted_host_native_fast_path=trusted_fast_path,
                sql_requirement=(
                    features.is_sql_output_request
                    if features is not None
                    and payload_type == "message"
                    and role == "user"
                    else None
                ),
            ),
            lowered=lowered,
        )
        if (
            not trusted_fast_path
            and not (payload_type == "message" and role == "user")
            and _is_non_kh_work_start(payload, lowered)
        ):
            self.work_activity_since_trigger = True
        self.previous_call_was_passive = (
            payload_type in {"function_call", "custom_tool_call"} and passive
        )

    def _consume_correction(
        self,
        event_seq: int,
        event: Mapping[str, Any],
        store: DiskBackedSessionEvents,
    ) -> None:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            return
        payload_type = str(payload.get("type", ""))
        role = str(payload.get("role", "")).lower()
        if payload_type == "thread_goal_updated":
            goal = payload.get("goal", {}) or {}
            status = (
                str(goal.get("status", "") or "").strip().lower()
                if isinstance(goal, dict)
                else ""
            )
            if status == "active":
                self.active_goal = True
            elif status in {"complete", "blocked"}:
                self.active_goal = False
        if payload_type == "agent_message" or (
            payload_type == "message" and role == "assistant"
        ):
            self.latest_assistant_text = _payload_text(payload)
        if payload_type == "message" and role == "user":
            user_text = _payload_text(payload)
            if not _is_synthetic_context_message(user_text):
                if _is_bounded_pb_correction_text(user_text):
                    store._db.execute(
                        "INSERT OR IGNORE INTO pb_correction_candidates(correction_seq) VALUES (?)",
                        (event_seq,),
                    )
                correction = _correction_signal(user_text, self.latest_assistant_text)
                if correction["is_correction"]:
                    store._db.execute(
                        """
                        INSERT INTO correction_facts (
                            event_seq, active_goal, invalidated_json,
                            replacements_json, related_to_previous,
                            prior_completion_seq, sample
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_seq,
                            int(self.active_goal),
                            _canonical_json(correction["invalidated"]),
                            _canonical_json(correction["replacements"]),
                            int(correction["related_to_previous"]),
                            self.latest_completion_seq
                            if correction["related_to_previous"]
                            else None,
                            _short(user_text),
                        ),
                    )
                if self.latest_completion_seq is not None and not _is_same_task_followup(
                    user_text,
                    self.latest_assistant_text,
                    allow_acknowledgement=False,
                ):
                    self.latest_completion_seq = None
        if payload_type == "task_complete":
            self.latest_completion_seq = event_seq


class AuditStreamPipeline:
    """Decode the source once and fan ephemeral features into audit storage."""

    def __init__(
        self,
        path: Path,
        *,
        catalog: Mapping[str, Any] | None = None,
        collect_stage_telemetry: bool = False,
    ) -> None:
        self.path = Path(path)
        self.catalog = dict(catalog or {"skills": []})
        self.collect_stage_telemetry = bool(collect_stage_telemetry)
        self.stage_telemetry: Dict[str, Any] = (
            {
                "source_read_seconds": 0.0,
                "decode_json_seconds": 0.0,
                "event_consume_seconds": 0.0,
                "feature_extract_seconds": 0.0,
                "event_store_seconds": 0.0,
                "reducer_consume_seconds": 0.0,
                "downstream_seconds": 0.0,
                "stream_seconds": 0.0,
                "reducer_finalize_seconds": 0.0,
                "correlation_finalize_seconds": 0.0,
                "analysis_finalize_seconds": 0.0,
                "seal_seconds": 0.0,
                "finalize_seconds": 0.0,
                "source_line_count": 0,
                "event_count": 0,
            }
            if self.collect_stage_telemetry
            else {}
        )
        self.payload_events = DiskBackedSessionEvents(
            self.catalog.get("skills", []) or []
        )
        try:
            self.metadata: Dict[str, Any] = {}
            self.integrity_issue_groups: Dict[str, Dict[str, Any]] = {}
            self.raw_characters_seen = 0
            self.max_source_line_characters = 0
            self.source_open_count = 0
            self.source_passes = 0
            self.source_bytes_read = 0
            self.reducers = [_AuditReducer(name) for name in _AUDIT_REDUCER_NAMES]
            self._reducers_by_name = {reducer.name: reducer for reducer in self.reducers}
            self._event_count = 0
            self._started = False
            self._finished = False
            self._closed = False
        except Exception:
            self.payload_events.close()
            raise

    def stream(self) -> Iterator[EventEnvelope]:
        if self._started:
            raise RuntimeError("audit source stream can only be consumed once")
        self._started = True
        self.source_open_count += 1
        stream_started = perf_counter() if self.collect_stage_telemetry else 0.0
        try:
            with self.path.open("rb") as stream:
                if self.collect_stage_telemetry:
                    yield from self._stream_with_stage_telemetry(stream)
                else:
                    for line_number, raw_line in enumerate(stream, start=1):
                        self.source_bytes_read += len(raw_line)
                        envelope = self._decode_envelope(line_number, raw_line)
                        yield self._consume(envelope)
            self.source_passes += 1
            self.payload_events.note_original_pass()
            self._finished = True
            if self.collect_stage_telemetry:
                self.stage_telemetry["stream_seconds"] += (
                    perf_counter() - stream_started
                )
        except Exception:
            self.close()
            raise

    def _stream_with_stage_telemetry(
        self,
        stream: Iterable[bytes],
    ) -> Iterator[EventEnvelope]:
        iterator = iter(stream)
        line_number = 0
        while True:
            started = perf_counter()
            try:
                raw_line = next(iterator)
            except StopIteration:
                self.stage_telemetry["source_read_seconds"] += (
                    perf_counter() - started
                )
                break
            self.stage_telemetry["source_read_seconds"] += perf_counter() - started
            line_number += 1
            self.source_bytes_read += len(raw_line)
            started = perf_counter()
            envelope = self._decode_envelope(line_number, raw_line)
            self.stage_telemetry["decode_json_seconds"] += perf_counter() - started
            started = perf_counter()
            consumed = self._consume(envelope)
            self.stage_telemetry["event_consume_seconds"] += perf_counter() - started
            started = perf_counter()
            yield consumed
            self.stage_telemetry["downstream_seconds"] += perf_counter() - started
        self.stage_telemetry["source_line_count"] = line_number
        self.stage_telemetry["event_count"] = self._event_count

    def finalize(self, *, postmortem: Any = None) -> SessionEventIndex:
        if not self._finished:
            raise RuntimeError("audit source stream was not fully consumed")
        finalize_started = perf_counter() if self.collect_stage_telemetry else 0.0
        stage_started = perf_counter() if self.collect_stage_telemetry else 0.0
        for reducer in self.reducers:
            reducer.consume_count = self._event_count
            reducer.finalize(self.payload_events)
        if self.collect_stage_telemetry:
            self.stage_telemetry["reducer_finalize_seconds"] += (
                perf_counter() - stage_started
            )
        finalized_reducers = sum(1 for reducer in self.reducers if reducer.finalized)
        stage_started = perf_counter() if self.collect_stage_telemetry else 0.0
        self.payload_events._ensure_correlated_receipts()
        if self.collect_stage_telemetry:
            self.stage_telemetry["correlation_finalize_seconds"] += (
                perf_counter() - stage_started
            )
        stage_started = perf_counter() if self.collect_stage_telemetry else 0.0
        self.payload_events.finalize_analysis_summary()
        if self.collect_stage_telemetry:
            self.stage_telemetry["analysis_finalize_seconds"] += (
                perf_counter() - stage_started
            )
        stage_started = perf_counter() if self.collect_stage_telemetry else 0.0
        self.payload_events.seal_text_records()
        self.payload_events.seal()
        if self.collect_stage_telemetry:
            self.stage_telemetry["seal_seconds"] += perf_counter() - stage_started
            self.stage_telemetry["finalize_seconds"] += (
                perf_counter() - finalize_started
            )
        self.payload_events.set_pipeline_diagnostics(
            source_open_count=self.source_open_count,
            source_passes=self.source_passes,
            source_bytes_read=self.source_bytes_read,
            reducer_count=len(self.reducers),
            reducer_finalize_count=finalized_reducers,
            reducer_evidence=[reducer.evidence() for reducer in self.reducers],
        )
        integrity_issues = list(self.integrity_issue_groups.values())
        retained_memory_bytes = (
            self.payload_events.retained_memory_bytes
            + _retained_python_bytes(self.metadata)
            + _retained_python_bytes(integrity_issues)
        )
        return SessionEventIndex(
            path_key=_session_path_key(self.path),
            payload_events=self.payload_events,
            metadata=self.metadata,
            integrity_issues=integrity_issues,
            raw_characters_seen=self.raw_characters_seen,
            max_source_line_characters=self.max_source_line_characters,
            indexed_disk_bytes=self.payload_events.disk_bytes,
            retained_memory_bytes=retained_memory_bytes,
            catalog=self.catalog,
            postmortem=postmortem,
            stage_telemetry=dict(self.stage_telemetry),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.payload_events.close()

    def _decode_envelope(self, line_number: int, raw_line: bytes) -> EventEnvelope:
        encoding_error = ""
        try:
            line = raw_line.decode("utf-8")
        except UnicodeDecodeError as exc:
            encoding_error = f"invalid UTF-8: {exc}"
            line = raw_line.decode("utf-8", errors="replace")
        duplicate_keys: List[str] = []
        event: Any = None
        parse_error = encoding_error
        if line and not line.isspace():
            try:
                event = json.loads(
                    line,
                    object_pairs_hook=self._duplicate_tracking_hook(duplicate_keys),
                )
            except (json.JSONDecodeError, UnicodeError) as exc:
                parse_error = "; ".join(
                    part for part in (encoding_error, str(exc)) if part
                )
        return EventEnvelope(
            source_line=line_number,
            raw_text=line,
            source_bytes=len(raw_line),
            event=event,
            duplicate_keys=tuple(duplicate_keys),
            parse_error=parse_error,
        )

    def _consume(self, envelope: EventEnvelope) -> EventEnvelope:
        line = envelope.raw_text
        self.raw_characters_seen += len(line)
        self.max_source_line_characters = max(
            self.max_source_line_characters,
            len(line),
        )
        if not line or line.isspace():
            return envelope
        if envelope.duplicate_keys:
            _record_bounded_integrity_issue(
                self.integrity_issue_groups,
                _duplicate_json_key_integrity_issue(
                    line_number=envelope.source_line,
                    line=line,
                    duplicate_keys=envelope.duplicate_keys,
                ),
            )
        if envelope.parse_error:
            _, _, structure = _partial_session_json_string_fields(line)
            integrity_issue = _session_line_integrity_issue(
                line_number=envelope.source_line,
                line=line,
                duplicate_boundary_field=bool(structure.get("duplicate_boundary_field")),
                parse_error=envelope.parse_error,
            )
            if integrity_issue:
                _record_bounded_integrity_issue(
                    self.integrity_issue_groups,
                    integrity_issue,
                )
        event = envelope.event
        if envelope.duplicate_keys or not isinstance(event, Mapping):
            return envelope
        payload = event.get("payload")
        projected_event: Any = event
        if event.get("type") == "session_meta" and isinstance(payload, Mapping) and not self.metadata:
            self.metadata = _compact_session_metadata(payload)
            projected_event = {"type": "session_meta", "payload": self.metadata}
        if event.get("type") not in {"response_item", "event_msg"} or not isinstance(payload, Mapping):
            return EventEnvelope(
                source_line=envelope.source_line,
                raw_text=envelope.raw_text,
                source_bytes=envelope.source_bytes,
                event=projected_event,
                duplicate_keys=envelope.duplicate_keys,
                parse_error=envelope.parse_error,
            )
        stage_started = perf_counter() if self.collect_stage_telemetry else 0.0
        postmortem_features = extract_postmortem_event_features(
            dict(event),
            envelope.source_line,
            audit_extractor=self._semantic_features,
        )
        semantic_features = postmortem_features.audit_features
        if not isinstance(semantic_features, EventSemanticFeatures):
            raise RuntimeError("audit semantic feature extraction did not complete")
        compact_event = _compact_session_event(event)
        features = self._features(
            compact_event,
            semantic_features,
            postmortem_features,
        )
        if self.collect_stage_telemetry:
            self.stage_telemetry["feature_extract_seconds"] += (
                perf_counter() - stage_started
            )
        stage_started = perf_counter() if self.collect_stage_telemetry else 0.0
        event_seq = self.payload_events.append(
            compact_event,
            source_line=envelope.source_line,
            features=features,
        )
        self._event_count += 1
        if features.text and (
            "front_door_status" in features.lowered
            or "kh_fd_micro" in features.lowered
        ):
            front_door_claim = _front_door_json(features.text)
            if front_door_claim:
                self.payload_events.append_front_door_claim(
                    event_seq,
                    front_door_claim,
                )
        if self.collect_stage_telemetry:
            self.stage_telemetry["event_store_seconds"] += (
                perf_counter() - stage_started
            )
        stage_started = perf_counter() if self.collect_stage_telemetry else 0.0
        self._reducers_by_name["session_text_records"]._consume_text_record(
            event_seq,
            compact_event,
            self.payload_events,
            features=features,
        )
        if features.payload_type in {
            "message",
            "agent_message",
            "thread_goal_updated",
            "task_complete",
        }:
            self._reducers_by_name["instruction_supersession"]._consume_correction(
                event_seq,
                compact_event,
                self.payload_events,
            )
        fact_key = features.call_id or features.payload_type or features.event_type or "event"
        fact_value = _short(features.text, 180) if features.text else fact_key
        for reducer_name, fact_kind in _audit_reducer_matches(features):
            self._reducers_by_name[reducer_name].observe(
                event_seq,
                fact_kind,
                fact_key,
                fact_value,
            )
        if self.collect_stage_telemetry:
            self.stage_telemetry["reducer_consume_seconds"] += (
                perf_counter() - stage_started
            )
        return EventEnvelope(
            source_line=envelope.source_line,
            raw_text=envelope.raw_text,
            source_bytes=envelope.source_bytes,
            event=compact_event,
            duplicate_keys=envelope.duplicate_keys,
            parse_error=envelope.parse_error,
            features=features,
        )

    @staticmethod
    def _semantic_features(
        event: Mapping[str, Any],
        payload: Mapping[str, Any],
        text: str,
        lowered: str,
        literal_hits: frozenset[str],
        sql_hint: bool,
    ) -> EventSemanticFeatures:
        payload_type = str(payload.get("type", "") or "")
        role = str(payload.get("role", "") or "").strip().lower()
        call_id = _payload_call_id(payload)
        boundary_id = str(payload.get("boundary_id", "") or "").strip()
        packet_hash = str(
            payload.get("packet_sha256", "") or payload.get("packet_hash", "") or ""
        ).strip().lower()
        return EventSemanticFeatures(
            is_non_kh_work_start=_is_non_kh_work_start(dict(payload), lowered),
            is_sql_output_request=bool(
                payload_type == "message"
                and role == "user"
                and sql_hint
                and looks_like_sql_output_request(lowered)
            ),
            reducer_matches=tuple(
                _derive_audit_reducer_matches(
                    payload_type=payload_type,
                    role=role,
                    literal_hits=literal_hits,
                    has_text=bool(text),
                    call_id=call_id,
                    boundary_id=boundary_id,
                    packet_hash=packet_hash,
                )
            ),
        )

    @staticmethod
    def _features(
        event: Mapping[str, Any],
        semantic_features: EventSemanticFeatures,
        postmortem_features: PostmortemEventFeatures,
    ) -> EventFeatures:
        payload = event.get("payload", {})
        payload = payload if isinstance(payload, Mapping) else {}
        text = _payload_text(payload)
        payload_type = str(payload.get("type", "") or "")
        role = str(payload.get("role", "") or "").strip().lower()
        lowered = text.lower()
        return EventFeatures(
            event_type=str(event.get("type", "") or ""),
            payload_type=payload_type,
            role=role,
            call_id=_payload_call_id(payload),
            boundary_id=str(payload.get("boundary_id", "") or "").strip(),
            correlation_id=str(payload.get("correlation_id", "") or "").strip(),
            tool_identity=str(payload.get("tool_identity", "") or "").strip().lower(),
            packet_hash=str(
                payload.get("packet_sha256", "") or payload.get("packet_hash", "") or ""
            ).strip().lower(),
            text=text,
            lowered=lowered,
            is_non_kh_work_start=semantic_features.is_non_kh_work_start,
            is_sql_output_request=semantic_features.is_sql_output_request,
            reducer_matches=semantic_features.reducer_matches,
            postmortem=postmortem_features,
        )

    @staticmethod
    def _duplicate_tracking_hook(duplicate_keys: List[str]):
        def build_object(pairs):
            result = {}
            seen = set()
            for key, value in pairs:
                normalized = str(key)
                if normalized in seen:
                    duplicate_keys.append(normalized)
                seen.add(normalized)
                result[key] = value
            return result

        return build_object


def analyze_session_skills(session_path: str | Path) -> SessionSkillAudit:
    path = Path(session_path)
    index = _build_session_event_index(path)
    token = _SESSION_EVENT_INDEX.set(index)
    try:
        return _analyze_session_skills_impl(path)
    finally:
        _SESSION_EVENT_INDEX.reset(token)
        index.close()


def _analyze_session_skills_impl(session_path: str | Path) -> SessionSkillAudit:
    path = Path(session_path)
    event_index = _current_session_event_index(path)
    postmortem = (
        event_index.postmortem
        if event_index is not None and event_index.postmortem is not None
        else analyze_codex_session_jsonl(path)
    )
    postmortem_data = postmortem.to_dict()
    postmortem_data["path"] = str(path)
    front_door_token_receipts = _apply_front_door_token_optimizer_evidence(path, postmortem_data)
    supersession_issues = _user_instruction_supersession_issues(path)
    _apply_correction_completion_guard(postmortem_data, supersession_issues)
    scoped_goal_evidence = _scoped_current_goal_evidence(path)
    goal_terminal_evidence = _terminal_goal_state_evidence(
        path,
        postmortem_data,
        scoped_goal_evidence,
    )
    text_records = _session_text_records(path)
    if scoped_goal_evidence.get("valid") and str(
        (postmortem_data.get("completion_guard", {}) or {}).get("latest_goal_status", "")
    ) != "active":
        text_records.append(_goal_ledger_evidence_record(scoped_goal_evidence))
    sql_formatting_audit = _host_local_sql_formatting_audit(path)
    active_texts = SessionTextView(text_records)
    sql_scope_texts = SessionTextView(text_records, sql_only=True)
    analysis_summary = (
        text_records._events.analysis_summary()
        if isinstance(text_records, DiskBackedSessionTextRecords) and not text_records._extras
        else {}
    )
    combined_text = (
        str(analysis_summary.get("combined_text", ""))
        if "combined_text" in analysis_summary
        else _bounded_text_aggregate(active_texts)
    )
    decision_text = (
        str(analysis_summary.get("decision_text", ""))
        if "decision_text" in analysis_summary
        else _bounded_text_aggregate(_active_non_front_door_texts(path))
    )
    catalog = (
        dict(event_index.catalog)
        if event_index is not None and event_index.catalog
        else collect_packaged_skills()
    )
    skills = catalog.get("skills", [])
    observation_records = (
        text_records.iter_observation_records()
        if isinstance(text_records, DiskBackedSessionTextRecords)
        else text_records
    )
    observations_by_skill = (
        dict(analysis_summary.get("catalog_observations", {}) or {})
        if analysis_summary and "catalog_observations" in analysis_summary
        else _catalog_observations(observation_records, skills)
    )
    required = _required_skills(
        postmortem_data,
        combined_text,
        active_texts,
        sql_scope_texts=sql_scope_texts,
        analysis_summary=analysis_summary,
    )
    pb_migration_audit = _pb_migration_execution_audit(path)
    if pb_migration_audit["required"]:
        required.setdefault(
            "pb-to-csharp-migration-harness",
            "PB migration scope or routing requires post-write C#/Designer validation evidence",
        )
    if _has_auditable_user_request(path):
        required.setdefault(
            "always-on-front-door",
            "every new user request or task must enter KH front-door before another skill, work command, or final answer",
        )
    if front_door_token_receipts:
        required.setdefault(
            "token-optimizer",
            "KH front-door runtime receipt recorded an auditable token-optimizer decision",
        )
    front_door_issues, front_door_evidence = _kh_front_door_audit(path)
    skill_rows = []
    issues = []

    for skill in skills:
        name = str(skill.get("name", ""))
        observations = dict(observations_by_skill.get(name, _empty_observations()))
        status = observations["status"]
        is_required = name in required
        if (
            name == "always-on-front-door"
            and is_required
            and front_door_evidence["all_requests_satisfied"]
            and status != "claimed_unverified"
            and STATUS_RANK.get(status, 0) < STATUS_RANK["considered"]
        ):
            status = "considered"
            observations["inspections"] = max(1, int(observations["inspections"]))
            observations["evidence"] = list(observations["evidence"])
            observations["evidence"].append(
                "All audited requests recorded a direct, specialist, or governed selection path."
            )
        if name == "sql-formatting-style-harness" and sql_formatting_audit["required"]:
            if sql_formatting_audit["verifier_executed"]:
                status = "applied"
                observations["runtime_hits"] = max(1, int(observations["runtime_hits"]))
            elif status == "applied":
                status = "considered" if sql_formatting_audit["provider_selected"] else "mentioned"
                observations["runtime_hits"] = 0
        if name == "pb-to-csharp-migration-harness" and pb_migration_audit["relevant_writes"]:
            if pb_migration_audit["verifier_executed"]:
                status = "applied"
                observations["runtime_hits"] = max(1, int(observations["runtime_hits"]))
            else:
                status = "considered"
                observations["runtime_hits"] = 0
        if (
            name == "goal-state-harness"
            and goal_terminal_evidence.get("valid")
            and int((postmortem_data.get("completion_guard", {}) or {}).get("task_complete_count", 0) or 0) > 0
        ):
            status = "applied"
            observations["runtime_hits"] = max(1, int(observations["runtime_hits"]))
        acceptance = _acceptance_for_skill(
            skill_name=name,
            required=is_required,
            status=status,
            observations=observations,
            postmortem=postmortem_data,
        )
        if name == "always-on-front-door" and status == "considered":
            acceptance = _front_door_route_acceptance(
                front_door_evidence,
                default=acceptance,
            )
        if name == "sql-formatting-style-harness":
            acceptance = _sql_style_harness_acceptance(
                sql_formatting_audit,
                required=is_required,
                default=acceptance,
            )
        if name == "pb-to-csharp-migration-harness":
            acceptance = _pb_migration_harness_acceptance(
                pb_migration_audit,
                required=is_required,
                default=acceptance,
            )
        if name == "goal-state-harness":
            acceptance = _goal_terminal_acceptance(
                goal_terminal_evidence,
                postmortem_data,
                required=is_required,
                default=acceptance,
            )
        row = {
            "name": name,
            "execution_level": skill.get("execution_level", ""),
            "required": is_required,
            "required_reason": required.get(name, ""),
            "status": status,
            "acceptance": acceptance,
            "mentions": observations["mentions"],
            "inspections": observations["inspections"],
            "runtime_hits": observations["runtime_hits"],
            "passive_references": observations["passive_references"],
            "evidence": observations["evidence"][:8],
        }
        if name == "token-optimizer":
            row["token_optimizer_status"] = postmortem_data.get("token_optimizer_status", "")
            row["token_optimizer_status_reason"] = postmortem_data.get("token_optimizer_status_reason", "")
        skill_rows.append(row)
        if is_required and STATUS_RANK.get(status, 0) < STATUS_RANK["considered"]:
            issues.append(
                {
                    "skill": name,
                    "status": status,
                    "severity": "P1" if status in {"absent", "mentioned"} else "P2",
                    "reason": required[name],
                    "action": "Record considered/applied/blocked evidence for this required KH skill.",
                }
            )
        if acceptance["status"] == "missing_outputs":
            issues.append(
                {
                    "skill": name,
                    "status": "missing_outputs",
                    "severity": ACCEPTANCE_SEVERITY.get(name, "P3"),
                    "reason": (
                        f"{name} was observed as {status} but missing required output evidence: "
                        + ", ".join(acceptance["missing_outputs"])
                    ),
                    "action": "Produce the required skill outputs or record an explicit blocked/skipped rationale.",
                }
            )

    issues.extend(_session_integrity_issues(path))
    issues.extend(_duplicate_tool_call_identity_issues(path))
    issues.extend(_pb_migration_execution_issues(pb_migration_audit))
    issues.extend(_aggregate_skill_runtime_evidence_issues(path))
    issues.extend(supersession_issues)
    issues.extend(_authoritative_reference_order_issues(path))
    issues.extend(_forbidden_residual_completion_issues(path))
    issues.extend(front_door_issues)
    issues.extend(_immediate_next_skill_issues(path, skill_rows))
    issues.extend(_front_door_execution_gate_bypass_issues(path))
    issues.extend(_front_door_latency_issues(path))
    issues.extend(_large_output_latency_issues(path))
    issues.extend(_stale_skill_cache_issues(path))
    issues.extend(_cross_scope_context_issues(path))
    issues.extend(_global_memory_scope_issues(path))
    issues.extend(_target_substitution_issues(path))
    issues.extend(sql_formatting_audit["issues"])
    issues.extend(_brainstorming_target_inspection_issues(path))
    issues.extend(_brainstorm_option_choice_execution_issues(path))
    issues.extend(_brainstorming_depth_issues(path, active_text=decision_text))
    issues.extend(_subagent_strategy_issues(path, postmortem_data, active_text=decision_text))
    issues.extend(_orchestration_decision_issues(path, postmortem_data, active_text=decision_text))
    issues.extend(_required_delegation_issues(path))
    issues.extend(_postmortem_guard_issues(postmortem_data))
    issues.extend(
        _goal_state_completion_absence_issues(
            path,
            skill_rows,
            postmortem_data,
            terminal_evidence=goal_terminal_evidence,
        )
    )
    coverage = _coverage(skill_rows)
    usage_summary = _skill_usage_summary(skill_rows, issues, postmortem_data)
    usage_summary["sql_formatting_evidence"] = {
        key: value
        for key, value in sql_formatting_audit.items()
        if key != "issues"
    }
    usage_summary["pb_migration_evidence"] = dict(pb_migration_audit)
    if event_index is not None:
        usage_summary["session_event_index_diagnostics"] = event_index.diagnostics()
    return SessionSkillAudit(
        session_id=postmortem.session_id,
        path=str(path),
        total_skills=len(skill_rows),
        coverage=coverage,
        usage_summary=usage_summary,
        skills=skill_rows,
        issues=issues,
        postmortem={
            "token_optimizer_status": postmortem_data.get("token_optimizer_status", ""),
            "token_optimizer_status_reason": postmortem_data.get("token_optimizer_status_reason", ""),
            "token_gate": postmortem_data.get("token_gate", {}) or {},
            "token_optimizer_evidence": postmortem_data.get("token_optimizer_evidence", {}) or {},
            "review_status": postmortem.review_status,
            "subagent_summary": postmortem.subagent_summary,
            "completion_guard": postmortem_data.get("completion_guard", {}) or {},
            "verification_claim_guard": postmortem.verification_claim_guard,
            "scope_completion_delta": postmortem.scope_completion_delta,
            "user_stop_guard": postmortem.user_stop_guard,
            "assistant_stop_guard": postmortem.assistant_stop_guard,
            "archive_guard": postmortem.archive_guard,
            "resume_guard": postmortem.resume_guard,
            "recommended_actions": postmortem.recommended_actions,
        },
    )


def _postmortem_guard_issues(postmortem: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    token_status = postmortem.get("token_optimizer_status", "")
    if token_status == "blocked":
        token_reason = str(postmortem.get("token_optimizer_status_reason", "") or "")
        issues.append(
            {
                "skill": "token-optimizer",
                "status": "blocked",
                "severity": "P1",
                "reason": token_reason
                or "token gate required optimization but runtime usage or passthrough evidence was missing",
                "action": "Run token optimizer, record runtime token_optimization evidence, record explicit passthrough, or record explicit considered_not_needed with not_used_reason before completion.",
            }
        )
    review_status = postmortem.get("review_status", "")
    if review_status == "review_incomplete":
        issues.append(
            {
                "skill": "review-gate-harness",
                "status": "blocked",
                "severity": "P1",
                "reason": "reviewers timed out or were closed while still running",
                "action": "Re-run or explicitly account for incomplete reviewers before completion.",
            }
        )
    completion_guard = postmortem.get("completion_guard", {}) or {}
    if completion_guard.get("status") in {"blocked", "failed", "pending"}:
        issues.append(
            {
                "skill": "goal-state-harness",
                "status": str(completion_guard.get("status")),
                "severity": "P1",
                "reason": "; ".join(str(reason) for reason in completion_guard.get("reasons", []) or [])
                or "completion remains invalid until corrected completion evidence exists",
                "action": (
                    "Keep completion pending, apply the user's correction, and record corrected implementation "
                    "plus fresh verification evidence before claiming completion again."
                ),
            }
        )
    verification_guard = postmortem.get("verification_claim_guard", {}) or {}
    if verification_guard.get("status") == "blocked":
        issues.append(
            {
                "skill": "verification-before-completion-harness",
                "status": "blocked",
                "severity": "P1",
                "reason": "failed verification was not reflected in final completion claims",
                "action": "Report failed verification route and residual risk before claiming verified completion.",
            }
        )
    scope_delta = postmortem.get("scope_completion_delta", {}) or {}
    if scope_delta.get("status") == "blocked":
        issues.append(
            {
                "skill": "context-state-harness",
                "status": "blocked",
                "severity": "P1",
                "reason": "final milestone omitted objective markers from the active goal",
                "action": "Record scope_completion_delta and continue missing objective markers.",
            }
        )
    user_stop_guard = postmortem.get("user_stop_guard", {}) or {}
    if user_stop_guard.get("status") == "blocked":
        issues.append(
            {
                "skill": "goal-state-harness",
                "status": "blocked",
                "severity": "P0",
                "reason": "user stop request was followed by continued work or an active goal left open",
                "action": "Treat user stop/cancel as higher priority than goal_context; stop tools, write interruption evidence, and block the goal only when host policy permits.",
            }
        )
    assistant_stop_guard = postmortem.get("assistant_stop_guard", {}) or {}
    if assistant_stop_guard.get("status") == "blocked":
        issues.append(
            {
                "skill": "goal-state-harness",
                "status": "blocked",
                "severity": "P0",
                "reason": "assistant reported stopped or blocked without terminal GoalState evidence",
                "action": "Do not report a stopped/blocked final answer without terminal GoalState evidence; close/block the goal when allowed or report active_with_blocker with the next required action.",
            }
        )
    archive_guard = postmortem.get("archive_guard", {}) or {}
    if archive_guard.get("status") == "blocked":
        issues.append(
            {
                "skill": "workflow-usability-harness",
                "status": "blocked",
                "severity": "P0",
                "reason": "assistant emitted ::archive without an explicit user request to end or archive the conversation",
                "action": "Remove unsolicited archive directives; report ordinary partial/blocked status and keep the host thread open.",
            }
        )
    resume_guard = postmortem.get("resume_guard", {}) or {}
    if resume_guard.get("status") == "blocked":
        issues.append(
            {
                "skill": "workflow-usability-harness",
                "status": "blocked",
                "severity": "P1",
                "reason": "resume/restart continued implementation before KH resume context, token gate, or skill bundle evidence was established",
                "action": "Run session_start_context, token optimizer/passthrough, and large_work_orchestration_bundle before implementation tools after resume.",
            }
        )
    subagents = postmortem.get("subagent_summary", {}) or {}
    spawned = int(subagents.get("spawned", 0) or 0)
    closed = int(subagents.get("closed", 0) or 0)
    timed_out = int(subagents.get("timed_out", 0) or 0)
    closed_while_running = int(subagents.get("closed_while_running", 0) or 0)
    if spawned > closed or timed_out or closed_while_running:
        issues.append(
            {
                "skill": "host-agent-orchestration",
                "status": "blocked",
                "severity": "P2",
                "reason": "subagents were not cleanly closed/accounted or reviewers timed out",
                "action": "Close, resume, re-run, or explicitly account for every spawned/timed-out subagent.",
            }
        )
        issues.append(
            {
                "skill": "role-execution-audit-harness",
                "status": "blocked",
                "severity": "P2",
                "reason": "subagent or reviewer execution had incomplete accounting",
                "action": "Audit role/subagent outputs, timed-out reviewers, and fan-in evidence before completion.",
            }
        )
        issues.append(
            {
                "skill": "subagent-review-pipeline",
                "status": "blocked",
                "severity": "P2",
                "reason": "subagent review pipeline had incomplete or timed-out worker/reviewer execution",
                "action": "Re-run, close, or explicitly account for implementer/spec/code-quality reviewer outputs.",
            }
        )
    return issues


def _goal_state_completion_absence_issues(
    path: Path,
    skill_rows: List[Dict[str, Any]],
    postmortem: Dict[str, Any],
    *,
    terminal_evidence: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    completion_guard = postmortem.get("completion_guard", {}) or {}
    task_complete_count = int(completion_guard.get("task_complete_count", 0) or 0)
    if task_complete_count <= 0:
        return []

    latest_status = str(completion_guard.get("latest_goal_status", "") or "")
    goal_row = next((row for row in skill_rows if row.get("name") == "goal-state-harness"), {})
    goal_required = bool(goal_row.get("required")) or _front_door_selected_skill(path, "goal-state-harness")
    evidence = terminal_evidence or _terminal_goal_state_evidence(
        path,
        postmortem,
        _scoped_current_goal_evidence(path),
    )
    if evidence.get("valid"):
        return []
    if not goal_required and latest_status not in {"active", "complete", "blocked"} and not evidence.get("observed"):
        return []

    return [
        {
            "skill": "goal-state-harness",
            "status": "missing_terminal_goal_state",
            "severity": "P0",
            "reason": (
                "task_complete was emitted while the latest GoalState was active"
                if latest_status == "active"
                else "goal-state-harness was required or selected, but task_complete was emitted without "
                "validated terminal GoalState evidence"
            ),
            "action": (
                "Before final task_complete, create or update GoalState and close it as complete/blocked; "
                "if the host cannot do that, report blocked instead of claiming completion."
            ),
            "terminal_evidence_source": str(evidence.get("source", "")),
            "validation_errors": list(evidence.get("errors", [])),
        }
    ]


def _terminal_goal_state_evidence(
    path: Path,
    postmortem: Dict[str, Any],
    scoped_goal_evidence: Dict[str, Any],
) -> Dict[str, Any]:
    completion_guard = postmortem.get("completion_guard", {}) or {}
    latest_status = str(completion_guard.get("latest_goal_status", "") or "")
    thread_goal = _merged_thread_goal_state(path)
    thread_status = str(thread_goal.get("status", "") or latest_status)
    if latest_status == "active" or thread_status == "active":
        return {
            "valid": False,
            "observed": True,
            "source": "thread_goal_updated",
            "state": thread_goal,
            "errors": ["latest_goal_status_active"],
        }

    errors: List[str] = []
    if thread_status in {"complete", "blocked"}:
        validation = _validate_terminal_goal_state(thread_goal)
        if validation["valid"]:
            return {
                "valid": True,
                "observed": True,
                "source": "thread_goal_updated",
                "state": validation["state"],
                "errors": [],
            }
        errors.extend(validation["errors"])

    if scoped_goal_evidence.get("valid"):
        return dict(scoped_goal_evidence)
    errors.extend(str(item) for item in scoped_goal_evidence.get("errors", []) if str(item))
    return {
        "valid": False,
        "observed": bool(thread_goal or scoped_goal_evidence.get("observed")),
        "source": "thread_goal_updated" if thread_goal else str(scoped_goal_evidence.get("source", "")),
        "state": thread_goal or scoped_goal_evidence.get("state", {}),
        "errors": _dedupe_text(errors),
    }


def _merged_thread_goal_state(path: Path) -> Dict[str, Any]:
    state: Dict[str, Any] = {}
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("goal state merge requires indexed event facts")
    for _event_seq, payload in events.iter_payloads(
        payload_types=("thread_goal_updated",)
    ):
        goal = payload.get("goal", {}) or {}
        if not isinstance(goal, dict):
            continue
        objective = str(goal.get("objective", "") or "")
        if objective and state.get("objective") and objective != state.get("objective"):
            state = {}
        state.update(goal)
    return state


def _scoped_current_goal_evidence(path: Path) -> Dict[str, Any]:
    metadata = _session_metadata(path)
    project_dir = str(metadata.get("cwd", "") or "").strip()
    thread_id = str(metadata.get("id", "") or metadata.get("thread_id", "")).strip()
    if not project_dir:
        return {"valid": False, "observed": False, "source": "", "state": {}, "errors": []}

    candidates: List[tuple[str, Path]] = []
    try:
        if thread_id:
            candidates.append(("chat_current_goal", GoalLedger(project_dir, thread_id=thread_id).current_goal_path))
        candidates.append(("project_current_goal", GoalLedger(project_dir).current_goal_path))
    except (OSError, ValueError):
        return {
            "valid": False,
            "observed": False,
            "source": "",
            "state": {},
            "errors": ["scoped_current_goal_path_unavailable"],
        }

    observed = False
    errors: List[str] = []
    seen: Set[str] = set()
    for scope, candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if not candidate.is_file():
            continue
        observed = True
        try:
            if candidate.stat().st_size > 1_000_000:
                errors.append(f"{scope}:current_goal_too_large")
                continue
            raw = load_json_without_duplicate_keys(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, DuplicateJsonKeyError):
            errors.append(f"{scope}:current_goal_unreadable")
            continue
        if not isinstance(raw, dict):
            errors.append(f"{scope}:current_goal_not_object")
            continue
        validation = _validate_terminal_goal_state(raw)
        if validation["valid"]:
            return {
                "valid": True,
                "observed": True,
                "source": scope,
                "path": str(candidate),
                "state": validation["state"],
                "errors": [],
            }
        errors.extend(f"{scope}:{item}" for item in validation["errors"])
    return {
        "valid": False,
        "observed": observed,
        "source": "scoped_current_goal" if observed else "",
        "state": {},
        "errors": _dedupe_text(errors),
    }


def _validate_terminal_goal_state(raw: Dict[str, Any]) -> Dict[str, Any]:
    nested = raw.get("goal", {}) if isinstance(raw.get("goal"), dict) else {}
    state = dict(nested)
    errors: List[str] = []
    for key in [
        "objective",
        "status",
        "success_criteria",
        "evidence_required",
        "evidence",
        "blocked_reason",
        "metadata",
    ]:
        if key not in raw:
            continue
        if key in nested and nested.get(key) != raw.get(key):
            errors.append(f"inconsistent_{key}")
        state[key] = raw.get(key)

    schema_version = raw.get("schema_version")
    if schema_version is not None and (not isinstance(schema_version, int) or schema_version < 1):
        errors.append("invalid_schema_version")
    objective = str(state.get("objective", "") or "").strip()
    if not objective:
        errors.append("objective_missing")
    status = str(state.get("status", "") or "").strip().lower()
    if status not in {"complete", "blocked"}:
        errors.append("status_not_terminal")

    success_criteria = _validated_goal_list(state, "success_criteria", errors)
    evidence_required = _validated_goal_list(state, "evidence_required", errors)
    evidence = _validated_goal_list(state, "evidence", errors)
    metadata = state.get("metadata", {}) if isinstance(state.get("metadata"), dict) else {}
    metadata_value = state.get("metadata")
    if metadata_value is not None and metadata_value != {} and not isinstance(metadata_value, dict):
        errors.append("metadata_not_object")

    if status == "complete":
        if (success_criteria or evidence_required) and not evidence:
            errors.append("completion_evidence_missing")
        missing_evidence = metadata.get("missing_evidence", [])
        if isinstance(missing_evidence, list) and missing_evidence:
            errors.append("metadata_missing_evidence_not_empty")
        elif missing_evidence is not None and missing_evidence != []:
            errors.append("metadata_missing_evidence_invalid")
        evidence_values = {_normalized_goal_evidence(item) for item in evidence}
        alias_matches = metadata.get("evidence_alias_matches", {})
        if not isinstance(alias_matches, dict):
            alias_matches = {}
            errors.append("evidence_alias_matches_not_object")
        for required in evidence_required:
            required_key = _normalized_goal_evidence(required)
            alias_value = _normalized_goal_evidence(alias_matches.get(required, ""))
            if required_key not in evidence_values and (not alias_value or alias_value not in evidence_values):
                errors.append(f"required_evidence_missing:{required}")
    elif status == "blocked" and not str(state.get("blocked_reason", "") or "").strip():
        errors.append("blocked_reason_missing")

    state["status"] = status
    state["objective"] = objective
    state["success_criteria"] = success_criteria
    state["evidence_required"] = evidence_required
    state["evidence"] = evidence
    return {"valid": not errors, "state": state, "errors": _dedupe_text(errors)}


def _validated_goal_list(state: Dict[str, Any], key: str, errors: List[str]) -> List[str]:
    value = state.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{key}_not_list")
        return []
    return [str(item) for item in value if str(item).strip()]


def _normalized_goal_evidence(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _session_metadata(path: Path) -> Dict[str, Any]:
    index = _current_session_event_index(path)
    if index is None:
        index = _build_session_event_index(path)
        try:
            return dict(index.metadata)
        finally:
            index.close()
    return dict(index.metadata)


def _goal_ledger_evidence_record(evidence: Dict[str, Any]) -> SessionTextRecord:
    state = evidence.get("state", {}) if isinstance(evidence.get("state"), dict) else {}
    return SessionTextRecord(
        text=json.dumps(
            {
                "skill": "goal-state-harness",
                "status": "applied",
                "goalstate": "validated terminal state",
                "goal_ledger": evidence.get("path", "current_goal.json"),
                "success_criteria": state.get("success_criteria", []),
                "evidence_required": state.get("evidence_required", []),
                "missing_evidence": [],
                "blocked_reason": state.get("blocked_reason", ""),
            },
            ensure_ascii=False,
        ),
        payload_type="goal_ledger_evidence",
        role="runtime",
    )


def _goal_terminal_acceptance(
    terminal_evidence: Dict[str, Any],
    postmortem: Dict[str, Any],
    *,
    required: bool,
    default: Dict[str, Any],
) -> Dict[str, Any]:
    task_complete_count = int(
        ((postmortem.get("completion_guard", {}) or {}).get("task_complete_count", 0)) or 0
    )
    if task_complete_count <= 0:
        return default
    required_outputs = list(ACCEPTANCE_OUTPUT_MARKERS.get("goal-state-harness", {}).keys())
    if terminal_evidence.get("valid"):
        return {
            "status": "passed",
            "required_outputs": required_outputs,
            "satisfied_outputs": required_outputs,
            "missing_outputs": [],
        }
    if not required:
        return default
    return {
        "status": "blocked",
        "required_outputs": required_outputs,
        "satisfied_outputs": [],
        "missing_outputs": required_outputs,
    }


def _dedupe_text(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def _kh_front_door_audit(
    path: Path,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    events = _session_payload_events(path)
    request_count = 0
    satisfied_request_count = 0
    selection_modes: List[str] = []
    waiting_for_front_door = False
    front_door_seen = False
    trigger_sample = ""
    trigger_kind = ""
    kh_active_directive_seen = False
    kh_active_directive_sample = ""
    task_unfinished = False
    task_route_checked = False
    active_goal = False
    latest_assistant_text = ""
    trigger_text = ""
    work_activity_since_trigger = False
    runtime_attempted_for_request = False
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("front-door audit requires indexed event facts")
    relevant_types = (
        "message",
        "agent_message",
        "thread_goal_updated",
        "task_complete",
        "function_call",
        "custom_tool_call",
        "function_call_output",
        "custom_tool_call_output",
        "host_front_door",
        "host_native_front_door",
    )
    for (
        event_index,
        payload_type,
        role,
        text,
        goal_status,
        is_non_kh_work_start,
        is_sql_output_request,
        trusted_host_native_fast_path,
        is_front_door_receipt,
    ) in events.iter_front_door_audit_facts(payload_types=relevant_types):
        lowered = text.lower()

        if payload_type == "thread_goal_updated":
            if goal_status == "active":
                active_goal = True
            elif goal_status in {"complete", "blocked"}:
                active_goal = False

        if (
            payload_type == "agent_message"
            or (payload_type == "message" and role == "assistant")
        ):
            latest_assistant_text = text

        if payload_type == "message" and role == "user":
            if _is_synthetic_context_message(text):
                continue
            if task_route_checked and _is_same_task_followup(
                text,
                latest_assistant_text,
                allow_acknowledgement=task_unfinished,
            ):
                task_unfinished = True
                continue
            request_count += 1
            active_directive = _is_kh_active_directive(text)
            if active_directive:
                kh_active_directive_seen = True
                kh_active_directive_sample = _short(text)
            direct_code_question = _looks_like_direct_code_question(lowered)
            waiting_for_front_door = True
            front_door_seen = False
            task_route_checked = False
            task_unfinished = True
            trigger_sample = _short(text)
            trigger_text = text
            work_activity_since_trigger = False
            runtime_attempted_for_request = False
            if _is_kh_front_door_request(lowered):
                trigger_kind = "explicit_kh"
            elif is_sql_output_request:
                trigger_kind = "sql_formatting_request"
            elif direct_code_question:
                trigger_kind = "direct_code_question"
            elif active_directive:
                trigger_kind = "kh_active_directive"
            elif kh_active_directive_seen:
                trigger_kind = "deferred_kh_active"
            else:
                trigger_kind = "deferred_automatic_intake"
            if _host_native_fast_path_trigger_is_eligible(trigger_text):
                trigger_kind = "host_semantic_direct"
                front_door_seen = True
                task_route_checked = True
                waiting_for_front_door = False
                satisfied_request_count += 1
                selection_modes.append("direct")
            continue

        if (
            waiting_for_front_door
            and trusted_host_native_fast_path
            and not work_activity_since_trigger
            and _host_native_fast_path_trigger_is_eligible(trigger_text)
        ):
            front_door_seen = True
            task_route_checked = True
            waiting_for_front_door = False
            satisfied_request_count += 1
            selection_modes.append("host_receipt")
            continue

        if not waiting_for_front_door:
            if payload_type == "task_complete":
                task_unfinished = False
                active_goal = False
            continue

        if is_front_door_receipt:
            front_door_seen = True
            task_route_checked = True
            waiting_for_front_door = False
            satisfied_request_count += 1
            selection_modes.append("runtime")
            continue

        if (
            payload_type in {"function_call", "custom_tool_call"}
            and any(marker in lowered for marker in ("kh_front_door", "front_door.py"))
        ):
            runtime_attempted_for_request = True

        if (
            not runtime_attempted_for_request
            and _is_host_semantic_specialist_skill_read(payload_type, lowered)
        ):
            front_door_seen = True
            task_route_checked = True
            waiting_for_front_door = False
            satisfied_request_count += 1
            selection_modes.append("specialist")
            continue

        if is_non_kh_work_start and not front_door_seen:
            work_activity_since_trigger = True
            if trigger_kind == "deferred_kh_active":
                if _is_kh_active_followup_request(trigger_text):
                    trigger_kind = "kh_active_directive"
                elif _is_automatic_intake_request(trigger_text):
                    trigger_kind = "automatic_intake"
                else:
                    trigger_kind = "universal_request"
            elif trigger_kind == "deferred_automatic_intake":
                trigger_kind = (
                    "automatic_intake"
                    if _is_automatic_intake_request(trigger_text)
                    else "universal_request"
                )
            issues.append(
                {
                    "skill": "always-on-front-door",
                    "status": "missing_front_door",
                    "severity": "P1",
                    "reason": (
                        "A KH-capable session started governed work before recording either a matching "
                        "specialist skill selection or a deterministic front-door receipt."
                    ),
                    "action": (
                        "For clear requests, select and read only the matching specialist SKILL.md before governed work. "
                        "Use the Python front door only when deterministic audit evidence, provider conflict resolution, "
                        "or governed high-risk/large-workflow routing is required. Direct self-contained answers need neither."
                    ),
                    "trigger_kind": trigger_kind,
                    "trigger": trigger_sample,
                    "kh_active_directive": kh_active_directive_sample if trigger_kind == "kh_active_directive" else "",
                    "first_work": _short(text),
                }
            )
            waiting_for_front_door = False
            task_route_checked = True
        if payload_type == "task_complete":
            waiting_for_front_door = False
            task_unfinished = False
            active_goal = False
    return issues, {
        "request_count": request_count,
        "satisfied_request_count": satisfied_request_count,
        "selection_modes": selection_modes,
        "all_requests_satisfied": bool(
            request_count > 0
            and satisfied_request_count == request_count
            and not any(issue.get("status") == "missing_front_door" for issue in issues)
        ),
    }


def _kh_front_door_issues(path: Path) -> List[Dict[str, Any]]:
    return _kh_front_door_audit(path)[0]


@dataclass
class _ImmediateSkillSequenceState:
    immediate: List[str]
    front_door_sample: str
    resolved: Set[str] = field(default_factory=set)
    order_violations: Dict[str, str] = field(default_factory=dict)
    late_after_work: Dict[str, str] = field(default_factory=dict)
    samples: Dict[str, str] = field(default_factory=dict)
    pending_index: int = 0
    order_break_sample: str = ""
    previous_call_was_passive: bool = False
    task_completed: bool = False

    def consume(
        self,
        payload: Dict[str, Any],
        correlated_call: Mapping[str, Any] | None = None,
    ) -> bool:
        if payload.get("type") == "message" and str(payload.get("role", "")).lower() == "user":
            return bool(
                not self.order_break_sample
                or _is_immediate_sequence_stop_user_message(_payload_text(payload))
            )
        if payload.get("type") == "task_complete":
            self.task_completed = True
            return True
        text = _payload_text(payload)
        if not text:
            self.previous_call_was_passive = False
            return False
        clean_text = _strip_passive_prefix(text)
        lowered = clean_text.lower()
        payload_type = str(payload.get("type", ""))
        correlated_runtime_skills = {
            skill_name
            for skill_name in self.immediate
            if correlated_call
            and _is_immediate_skill_runtime_call(correlated_call, skill_name)
        }
        passive = _passive_reference(lowered) or (
            payload_type in {"function_call_output", "custom_tool_call_output"}
            and self.previous_call_was_passive
        )
        self.previous_call_was_passive = (
            payload_type in {"function_call", "custom_tool_call"} and passive
        )
        if _looks_like_front_door_runtime_output(lowered):
            return False
        if (
            self.pending_index < len(self.immediate)
            and not self.order_break_sample
            and _immediate_order_break(
                payload,
                lowered,
                self.immediate[self.pending_index],
            )
        ):
            self.order_break_sample = _short(clean_text)

        matches = []
        for position, skill_name in enumerate(self.immediate):
            if skill_name in self.resolved:
                continue
            status = _immediate_skill_event_status(
                payload,
                lowered,
                skill_name,
                passive,
                correlated_runtime_call=skill_name in correlated_runtime_skills,
            )
            if not status:
                continue
            sample = _short(clean_text)
            self.samples.setdefault(skill_name, sample)
            matches.append((position, skill_name, status, sample))
        if not matches:
            return False

        by_position = {
            position: (skill_name, status, sample)
            for position, skill_name, status, sample in matches
        }
        if self.pending_index not in by_position:
            for position, skill_name, _status, sample in matches:
                if position > self.pending_index:
                    self.order_violations.setdefault(skill_name, sample)
            return False

        while self.pending_index < len(self.immediate) and self.pending_index in by_position:
            skill_name, _status, _sample = by_position[self.pending_index]
            if self.order_break_sample:
                self.late_after_work.setdefault(
                    skill_name,
                    self.samples.get(skill_name, ""),
                )
            else:
                self.resolved.add(skill_name)
            self.pending_index += 1

        for position, skill_name, _status, sample in matches:
            if skill_name not in self.resolved and position > self.pending_index:
                self.order_violations.setdefault(skill_name, sample)
        return False

    def issues(self) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        for position, skill_name in enumerate(self.immediate):
            if skill_name in self.resolved and skill_name not in self.order_violations:
                continue
            order_violation = self.order_violations.get(skill_name, "")
            late_sample = self.late_after_work.get(skill_name, "")
            status = (
                "immediate_next_skill_order_violation"
                if order_violation
                else "immediate_next_skill_not_applied"
            )
            reason = (
                f"Front-door emitted `{skill_name}` in immediate_next_skills, but the same turn "
                "did not record concrete applied/skipped/blocked evidence before continuing."
            )
            if order_violation:
                expected = self.immediate[position - 1] if position > 0 else skill_name
                reason = (
                    f"Front-door required immediate_next_skills in order, but `{skill_name}` produced evidence "
                    "before preceding skill evidence was complete."
                )
                if position > 0:
                    reason += f" Expected prior skill: `{expected}`."
            if self.order_break_sample:
                reason += " Work continued before the immediate skill sequence completed."
            issues.append(
                {
                    "skill": skill_name,
                    "status": status,
                    "severity": "P0" if self.task_completed else "P1",
                    "reason": reason,
                    "action": (
                        "After front-door returns, execute immediate_next_skills first and in order. "
                        "A SKILL.md/support-file read or catalog lookup is only inspection evidence; "
                        "record runtime evidence, an explicit blocked reason, or an explicit "
                        "skipped_with_rationale before source exploration, implementation, verification, "
                        "or final claims."
                    ),
                    "front_door": self.front_door_sample,
                    "followup_sample": self.samples.get(skill_name, "") or late_sample,
                    "order_break_sample": self.order_break_sample,
                    "order_violation_sample": order_violation,
                    "expected_order": self.immediate,
                }
            )
        return issues


def _immediate_next_skill_issues(path: Path, skill_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    events = _session_payload_events(path)
    known_skills = {str(row.get("name", "")) for row in skill_rows}
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("immediate skill audit requires indexed event facts")
    active: List[_ImmediateSkillSequenceState] = []
    for _event_index, payload, claim_data, correlated_call in events.iter_ordered_correlation_facts():
        remaining: List[_ImmediateSkillSequenceState] = []
        for state in active:
            if state.consume(payload, correlated_call):
                issues.extend(state.issues())
            else:
                remaining.append(state)
        active = remaining
        if not claim_data:
            continue
        immediate = _ordered_unique(
            str(item)
            for item in claim_data.get("immediate_next_skills", []) or []
        )
        immediate = [skill for skill in immediate if skill in known_skills]
        if immediate:
            active.append(
                _ImmediateSkillSequenceState(
                    immediate=immediate,
                    front_door_sample=_short(_payload_text(payload)),
                )
            )
    for state in active:
        issues.extend(state.issues())
    return issues


def _ordered_unique(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    ordered: List[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _immediate_skill_sequence_issues(
    *,
    events: Sequence[Dict[str, Any]],
    start_index: int,
    immediate: List[str],
    front_door_sample: str,
) -> List[Dict[str, Any]]:
    resolved: Set[str] = set()
    order_violations: Dict[str, str] = {}
    late_after_work: Dict[str, str] = {}
    samples: Dict[str, str] = {}
    pending_index = 0
    order_break_sample = ""
    previous_call_was_passive = False
    task_completed = False
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("immediate skill sequencing requires the streaming fact store")

    for event_index, payload in events.iter_payloads(start=start_index):
        if payload.get("type") == "message" and str(payload.get("role", "")).lower() == "user":
            if not order_break_sample or _is_immediate_sequence_stop_user_message(_payload_text(payload)):
                break
            continue
        if payload.get("type") == "task_complete":
            task_completed = True
            break
        text = _payload_text(payload)
        if not text:
            previous_call_was_passive = False
            continue
        clean_text = _strip_passive_prefix(text)
        lowered = clean_text.lower()
        payload_type = str(payload.get("type", ""))
        correlated_runtime_skills: Set[str] = set()
        if payload_type in {"function_call_output", "custom_tool_call_output"}:
            correlated_call = events.successful_correlated_call_payload(event_index)
            correlated_runtime_skills = {
                skill_name
                for skill_name in immediate
                if correlated_call
                and _is_immediate_skill_runtime_call(correlated_call, skill_name)
            }
        passive = _passive_reference(lowered) or (
            payload_type in {"function_call_output", "custom_tool_call_output"}
            and previous_call_was_passive
        )
        previous_call_was_passive = (
            payload_type in {"function_call", "custom_tool_call"} and passive
        )
        if _looks_like_front_door_runtime_output(lowered):
            continue
        if pending_index < len(immediate) and not order_break_sample and _immediate_order_break(
            payload, lowered, immediate[pending_index]
        ):
            order_break_sample = _short(clean_text)

        matches = []
        for position, skill_name in enumerate(immediate):
            if skill_name in resolved:
                continue
            status = _immediate_skill_event_status(
                payload,
                lowered,
                skill_name,
                passive,
                correlated_runtime_call=skill_name in correlated_runtime_skills,
            )
            if not status:
                continue
            sample = _short(clean_text)
            samples.setdefault(skill_name, sample)
            matches.append((position, skill_name, status, sample))
        if not matches:
            continue

        by_position = {position: (skill_name, status, sample) for position, skill_name, status, sample in matches}
        if pending_index not in by_position:
            for position, skill_name, _status, sample in matches:
                if position > pending_index:
                    order_violations.setdefault(skill_name, sample)
            continue

        while pending_index < len(immediate) and pending_index in by_position:
            skill_name, _status, _sample = by_position[pending_index]
            if order_break_sample:
                late_after_work.setdefault(skill_name, samples.get(skill_name, ""))
            else:
                resolved.add(skill_name)
            pending_index += 1

        for position, skill_name, _status, sample in matches:
            if skill_name not in resolved and position > pending_index:
                order_violations.setdefault(skill_name, sample)

    issues: List[Dict[str, Any]] = []
    for position, skill_name in enumerate(immediate):
        if skill_name in resolved and skill_name not in order_violations:
            continue
        order_violation = order_violations.get(skill_name, "")
        late_sample = late_after_work.get(skill_name, "")
        status = "immediate_next_skill_order_violation" if order_violation else "immediate_next_skill_not_applied"
        reason = (
            f"Front-door emitted `{skill_name}` in immediate_next_skills, but the same turn "
            "did not record concrete applied/skipped/blocked evidence before continuing."
        )
        if order_violation:
            expected = immediate[position - 1] if position > 0 else skill_name
            reason = (
                f"Front-door required immediate_next_skills in order, but `{skill_name}` produced evidence "
                f"before preceding skill evidence was complete."
            )
            if position > 0:
                reason += f" Expected prior skill: `{expected}`."
        if order_break_sample:
            reason += " Work continued before the immediate skill sequence completed."
        issues.append(
            {
                "skill": skill_name,
                "status": status,
                "severity": "P0" if task_completed else "P1",
                "reason": reason,
                "action": (
                    "After front-door returns, execute immediate_next_skills first and in order. "
                    "A SKILL.md/support-file read or catalog lookup is only inspection evidence; "
                    "record runtime evidence, an explicit blocked reason, or an explicit "
                    "skipped_with_rationale before source exploration, implementation, verification, "
                    "or final claims."
                ),
                "front_door": front_door_sample,
                "followup_sample": samples.get(skill_name, "") or late_sample,
                "order_break_sample": order_break_sample,
                "order_violation_sample": order_violation,
                "expected_order": immediate,
            }
        )
    return issues


def _front_door_execution_gate_bypass_issues(path: Path) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    gate_active = False
    gate_status = ""
    front_door_sample = ""
    required_before: List[str] = []
    blocked_actions: List[str] = []
    immediate: List[str] = []

    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("execution-gate audit requires indexed event facts")
    for _event_seq, payload in events.iter_payloads(
        payload_types=(
            "message",
            "agent_message",
            "task_complete",
            "function_call",
            "custom_tool_call",
            "function_call_output",
            "custom_tool_call_output",
        )
    ):
        text = _payload_text(payload)
        clean_text = _strip_passive_prefix(text)
        lowered = clean_text.lower()

        data = _front_door_json(clean_text)
        if data:
            gate = data.get("execution_gate", {}) or {}
            auth = data.get("execution_authorization", {}) or {}
            gate_active = bool(
                gate.get("can_execute") is False
                or auth.get("must_stop_before_execution") is True
            )
            gate_status = str(gate.get("status") or auth.get("status") or "")
            front_door_sample = _short(clean_text)
            required_before = [
                str(item)
                for item in (
                    auth.get("required_before_execution")
                    or gate.get("required_before_execution")
                    or []
                )
            ]
            blocked_actions = [
                str(item)
                for item in (
                    auth.get("forbidden_next_actions")
                    or gate.get("blocked_actions")
                    or []
                )
            ]
            immediate = [str(item) for item in data.get("immediate_next_skills", []) or []]
            continue

        if not gate_active:
            continue
        if _execution_gate_release_evidence(lowered, required_before, immediate):
            gate_active = False
            continue
        if not _blocked_execution_work_start(payload, lowered):
            continue
        issues.append(
            {
                "skill": "always-on-front-door",
                "status": "front_door_execution_gate_bypassed",
                "severity": "P0",
                "reason": (
                    "Front-door returned an execution stop gate, but the session started task work "
                    "before required gate evidence or immediate-skill evidence existed."
                ),
                "action": (
                    "When `execution_authorization.must_stop_before_execution=true` or "
                    "`execution_gate.can_execute=false`, stop after intake. Only record the allowed "
                    "setup evidence and immediate skill applied/skipped/blocked statuses before source "
                    "exploration, implementation, DB/file writes, subagent dispatch, verification, or final claims."
                ),
                "gate_status": gate_status,
                "front_door": front_door_sample,
                "required_before_execution": required_before,
                "immediate_next_skills": immediate,
                "blocked_actions": blocked_actions,
                "first_blocked_work": _short(clean_text),
            }
        )
        gate_active = False
    return issues


def _execution_gate_release_evidence(
    lowered: str,
    required_before: Sequence[str],
    immediate: Sequence[str],
) -> bool:
    if not lowered:
        return False
    if "execution_authorization" in lowered and '"can_execute_now": true' in lowered:
        return True
    if immediate and not all(skill.lower() in lowered for skill in immediate):
        return False
    required = {str(item).lower() for item in required_before if str(item)}
    if not required:
        return False
    brainstorm_markers = [
        "brainstormsession",
        "decision_log",
        "validate_brainstorm_session",
        "brainstorm_handoff",
        "separate_implementation_approval",
    ]
    if "brainstorming-harness" in required:
        return all(marker in lowered for marker in brainstorm_markers)
    if _requires_large_work_preflight(required):
        return _large_work_preflight_release_evidence(lowered, required, immediate)
    return False


def _requires_large_work_preflight(required: Set[str]) -> bool:
    return bool(
        required
        & {
            "large_work_orchestration_bundle",
            "skill_statuses",
            "workspace_strategy",
            "token_optimizer_status",
            "token_optimizer_status_reason",
            "host_runtime",
            "nested_subagents_available_or_not_applicable",
            "subagent_strategy_with_rationale",
            "parallel_strategy_decision_with_rationale",
            "role_execution_audit.status_or_pre_role_skip",
            "guard_policy_or_rollback_strategy",
            "verification_plan",
            "immediate_next_skills_applied_skipped_or_blocked",
            "same_turn_immediate_skill_evidence",
        }
    )


def _large_work_preflight_release_evidence(
    lowered: str,
    required: Set[str],
    immediate: Sequence[str],
) -> bool:
    if immediate and not all(_has_gate_immediate_skill_resolution(lowered, skill) for skill in immediate):
        return False
    for requirement in required:
        if requirement in {str(skill).lower() for skill in immediate}:
            continue
        if requirement in {
            "immediate_next_skills_applied_skipped_or_blocked",
            "same_turn_immediate_skill_evidence",
        }:
            if not immediate or not all(_has_gate_immediate_skill_resolution(lowered, skill) for skill in immediate):
                return False
            continue
        if not _has_large_work_requirement_evidence(lowered, requirement):
            return False
    return True


def _has_large_work_requirement_evidence(lowered: str, requirement: str) -> bool:
    if requirement == "large_work_orchestration_bundle":
        return _has_field_assignment_or_recorded(lowered, "large_work_orchestration_bundle")
    if requirement == "skill_statuses":
        return _has_field_assignment_or_recorded(lowered, "skill_statuses") or _has_field_assignment_or_recorded(
            lowered,
            "skill_status_summary",
        )
    if requirement == "workspace_strategy":
        return _has_field_assignment(lowered, "workspace_strategy")
    if requirement == "token_optimizer_status":
        return _has_status_assignment(
            lowered,
            "token_optimizer_status",
            {"used", "considered_not_needed", "passthrough", "blocked", "skipped_with_rationale"},
        )
    if requirement == "token_optimizer_status_reason":
        return _has_field_assignment_or_recorded(lowered, "token_optimizer_status_reason") or (
            "token optimizer" in lowered and ("reason=" in lowered or "reason:" in lowered)
        )
    if requirement == "host_runtime":
        return _has_field_assignment(lowered, "host_runtime") or _has_field_assignment(lowered, "host")
    if requirement == "nested_subagents_available_or_not_applicable":
        return (
            _has_field_assignment(lowered, "nested_subagents_available")
            or "nested_subagents_unavailable" in lowered
            or "nested subagents unavailable" in lowered
            or "not_applicable" in lowered
        )
    if requirement == "subagent_strategy_with_rationale":
        return _has_subagent_strategy_rationale(lowered)
    if requirement == "parallel_strategy_decision_with_rationale":
        return _has_parallel_strategy_rationale(lowered)
    if requirement == "role_execution_audit.status_or_pre_role_skip":
        return _has_role_execution_audit_rationale(lowered)
    if requirement == "guard_policy_or_rollback_strategy":
        return any(
            marker in lowered
            for marker in [
                "guard_policy",
                "guard policy",
                "rollback_strategy",
                "rollback strategy",
                "rollback policy",
                "do not revert",
                "no revert",
                "snapshot strategy",
            ]
        )
    if requirement == "verification_plan":
        return _has_field_assignment_or_recorded(lowered, "verification_plan") or (
            "verification plan" in lowered and any(marker in lowered for marker in ["pytest", "test", "qa", "check"])
        )
    if requirement.endswith("-harness"):
        return _has_gate_immediate_skill_resolution(lowered, requirement)
    return requirement in lowered


def _has_gate_immediate_skill_resolution(lowered: str, skill_name: str) -> bool:
    aliases = [skill_name.lower(), skill_name.replace("-", "_").lower()]
    for alias in aliases:
        if alias not in lowered:
            continue
        window = _text_window(lowered, alias, radius=300)
        if _is_immediate_blocked_evidence(window) or _is_immediate_skipped_evidence(window):
            return True
        if _has_status_assignment(window, "status", {"applied"}) and any(
            marker in window
            for marker in [
                "evidence",
                "artifact",
                "objective",
                "goal",
                "runtime",
                "strategy",
                "progress",
                "host_runtime",
                "verification_plan",
            ]
        ):
            return True
        if skill_name == "goal-state-harness" and "thread_goal_updated" in window:
            return True
    return False


def _has_field_assignment(lowered: str, field: str) -> bool:
    return re.search(rf"['\"]?{re.escape(field)}['\"]?\s*[:=]\s*['\"]?[a-z0-9_.-]+", lowered) is not None


def _has_status_assignment(lowered: str, field: str, statuses: Set[str]) -> bool:
    pattern = "|".join(re.escape(status) for status in sorted(statuses))
    return re.search(rf"['\"]?{re.escape(field)}['\"]?\s*[:=]\s*['\"]?(?:{pattern})\b", lowered) is not None


def _has_field_assignment_or_recorded(lowered: str, field: str) -> bool:
    if _has_field_assignment(lowered, field):
        return True
    return any(
        marker in _text_window(lowered, field, radius=120)
        for marker in ["recorded", "applied", "ready", "present"]
    )


def _text_window(text: str, marker: str, radius: int = 200) -> str:
    index = text.find(marker)
    if index < 0:
        return ""
    start = max(0, index - radius)
    end = min(len(text), index + len(marker) + radius)
    return text[start:end]


def _blocked_execution_work_start(payload: Dict[str, Any], lowered: str) -> bool:
    payload_type = str(payload.get("type", ""))
    if payload_type == "task_complete":
        return True
    if payload_type in {"message", "agent_message"}:
        return False
    if payload_type not in {"function_call", "custom_tool_call"}:
        return False
    if _is_front_door_runtime_command(payload, lowered):
        return False
    if _is_gate_allowed_skill_doc_read(lowered):
        return False
    tool_name = str(payload.get("name", "")).lower()
    if tool_name == "apply_patch":
        return True
    if "mssql" in tool_name or "run_sql_query" in tool_name:
        return True
    if "spawn_agent" in tool_name or "send_message_to_thread" in tool_name:
        return True
    if tool_name in {
        "open",
        "web.run",
        "view_image",
        "functions.view_image",
        "browser",
        "browser.open",
        "read_file",
        "computer-use",
        "imagegen",
    }:
        return True
    if tool_name not in {"shell_command", "functions.shell_command"}:
        return False
    if "src.skills.uaf_skill_catalog --read" in lowered:
        return False
    if "python -m src.orchestration.kh_front_door" in lowered or "front_door.py" in lowered:
        return False
    return any(
        marker in lowered
        for marker in [
            "get-childitem",
            "test-path",
            "select-string",
            "rg ",
            "rg --files",
            "git ",
            "git show",
            "git diff",
            "git grep",
            "dir ",
            "ls ",
            "findstr",
            "get-content",
            "python ",
            "msbuild",
            "dotnet ",
            "npm ",
            "node ",
            "copy-item",
            "move-item",
            "remove-item",
            "set-content",
            "add-content",
        ]
    )


def _is_gate_allowed_skill_doc_read(lowered: str) -> bool:
    if "\\skills\\" not in lowered and "/skills/" not in lowered:
        return False
    return any(
        marker in lowered
        for marker in [
            "skill.md",
            "\\references\\",
            "/references/",
            "\\examples\\",
            "/examples/",
            "\\scripts\\smoke_check.py",
            "/scripts/smoke_check.py",
            "\\scripts\\demo.py",
            "/scripts/demo.py",
        ]
    )


def _is_host_semantic_specialist_skill_read(payload_type: str, lowered: str) -> bool:
    """Treat an observed specialist skill read as the host's semantic route receipt."""
    if payload_type not in {"function_call", "custom_tool_call"}:
        return False
    if not _is_gate_allowed_skill_doc_read(lowered):
        return False
    if "always_on_front_door" in lowered:
        return False
    if any(
        marker in lowered
        for marker in [
            "*** begin patch",
            "apply_patch",
            "set-content",
            "add-content",
            "remove-item",
            "move-item",
            "copy-item",
        ]
    ):
        return False
    return True


def _immediate_skill_event_status(
    payload: Dict[str, Any],
    lowered: str,
    skill_name: str,
    passive: bool,
    *,
    correlated_runtime_call: bool = False,
) -> str:
    if passive:
        return ""
    payload_type = str(payload.get("type", ""))
    if skill_name == "goal-state-harness" and payload_type == "thread_goal_updated":
        return "applied"
    structured_payload = _is_immediate_structured_runtime_payload(payload_type, lowered)
    if (
        skill_name == "brainstorming-harness"
        and payload_type in {"message", "agent_message", "task_complete"}
        and _looks_like_visible_brainstorming_application(lowered)
    ):
        return "applied"
    if payload_type in {"message", "agent_message", "task_complete"}:
        return ""
    aliases = {skill_name, skill_name.replace("-", "_")}
    runtime_markers = {marker.lower() for marker in RUNTIME_MARKERS.get(skill_name, [])}
    alias_hit = any(alias.lower() in lowered for alias in aliases)
    marker_hit = any(marker in lowered for marker in runtime_markers)
    if not alias_hit and not marker_hit:
        return ""
    if structured_payload and _is_immediate_blocked_evidence(lowered):
        return "blocked"
    if structured_payload and _is_immediate_skipped_evidence(lowered):
        return "skipped"
    if structured_payload and (
        _is_immediate_applied_evidence(lowered, aliases)
        or (marker_hit and _has_runtime_output_context(lowered))
    ):
        if (
            payload_type in {"function_call_output", "custom_tool_call_output"}
            and not correlated_runtime_call
        ):
            return ""
        return "applied"
    return ""


def _is_immediate_skill_runtime_call(
    payload: Dict[str, Any],
    skill_name: str,
) -> bool:
    if str(payload.get("type", "")) not in {"function_call", "custom_tool_call"}:
        return False
    lowered = _payload_text(payload).lower()
    if _is_current_skill_support_read(lowered, skill_name):
        return False

    tool_name = str(payload.get("name", "") or "").strip().lower()
    tool_tail = re.split(r"[.:]", tool_name)[-1]
    aliases = {
        skill_name.lower(),
        skill_name.replace("-", "_").lower(),
        skill_name.removesuffix("-harness").replace("-", "_").lower(),
    }
    runtime_markers = {
        str(marker).lower()
        for marker in RUNTIME_MARKERS.get(skill_name, [])
        if str(marker).strip()
    }
    if tool_name in aliases or tool_tail in aliases or tool_tail in runtime_markers:
        return True
    return any(marker in lowered for marker in runtime_markers)


def _is_immediate_sequence_stop_user_message(text: str) -> bool:
    lowered = text.lower()
    stop_markers = [
        "stop",
        "pause",
        "cancel",
        "abort",
        "new task",
        "different task",
        "\uc911\ub2e8",
        "\uba48\ucdb0",
        "\ucde8\uc18c",
        "\uc0c8 \uc791\uc5c5",
        "\ub2e4\ub978 \uc791\uc5c5",
    ]
    return any(marker in lowered for marker in stop_markers)


def _is_immediate_structured_runtime_payload(payload_type: str, lowered: str) -> bool:
    if payload_type in {"function_call_output", "custom_tool_call_output", "thread_goal_updated"}:
        return True
    return False


def _looks_like_visible_brainstorming_application(lowered: str) -> bool:
    option_shape = (
        ("1." in lowered and "2." in lowered)
        or any(marker in lowered for marker in ["option", "options", "alternatives", "\uc120\ud0dd\uc9c0", "\ub300\uc548"])
    )
    scope_shape = any(
        marker in lowered
        for marker in [
            "objective",
            "operator",
            "target user",
            "audience",
            "scope",
            "business scope",
            "\ubaa9\ud45c",
            "\uc6b4\uc601\uc790",
            "\uc5c5\ubb34 \ubc94\uc704",
            "\ubc94\uc704",
        ]
    )
    decision_question = any(
        marker in lowered
        for marker in [
            "which",
            "choose",
            "confirm",
            "approval",
            "\uc5b4\ub290",
            "\uc120\ud0dd",
            "\ud655\uc815",
            "\uc2b9\uc778",
            "\uac08\uae4c\uc694",
        ]
    )
    execution_deferred = any(
        marker in lowered
        for marker in [
            "before implementation",
            "not implemented",
            "no files",
            "\uad6c\ud604 \uc804",
            "\ud655\uc815 \uc804",
            "\ud30c\uc77c\uc740 \uc544\uc9c1",
            "\uc218\uc815\ud558\uc9c0 \uc54a\uc558",
            "\ud655\uc778/\uc218\uc815\ud558\uc9c0 \uc54a\uc558",
        ]
    )
    if not (option_shape and scope_shape and decision_question and execution_deferred):
        return False
    return not _brainstorm_response_missing_markers(lowered)


def _has_runtime_output_context(lowered: str) -> bool:
    return any(
        marker in lowered
        for marker in [
            '"status"',
            "'status'",
            '"application_mode"',
            "'application_mode'",
            '"evidence"',
            "'evidence'",
            '"artifacts"',
            "'artifacts'",
            '"source"',
            "'source'",
            ".kh/",
            ".uaf/",
            "current_goal.json",
            "goal_ledger",
            "host_panel",
            "artifact",
            "wrote",
            "written",
            "created",
            "updated",
        ]
    )


def _immediate_order_break(payload: Dict[str, Any], lowered: str, skill_name: str) -> bool:
    payload_type = str(payload.get("type", ""))
    if payload_type not in {"function_call", "custom_tool_call"}:
        return False
    if _is_current_skill_support_read(lowered, skill_name):
        return False
    if _is_immediate_skill_runtime_call(payload, skill_name):
        return False
    if _is_front_door_order_evidence(payload, lowered):
        return False
    return _is_non_kh_work_start(payload, lowered)


def _is_immediate_blocked_evidence(lowered: str) -> bool:
    status_seen = any(
        marker in lowered
        for marker in [
            '"status": "blocked"',
            "'status': 'blocked'",
            "status=blocked",
            "cannot apply",
            "cannot run",
            "unable to apply",
            "unable to run",
            "unavailable",
        ]
    )
    reason_seen = any(
        marker in lowered
        for marker in [
            "blocked_reason",
            "blocked reason",
            '"reason"',
            "'reason'",
            "reason=",
            "because",
            "missing",
            "unavailable",
        ]
    )
    recovery_seen = any(
        marker in lowered
        for marker in [
            "recovery",
            "retry",
            "next_action",
            "next action",
            "requires",
            "need ",
            "needs ",
            "permission",
            "approval",
            "install",
            "read-only",
            "fallback",
        ]
    )
    if status_seen and reason_seen and recovery_seen:
        return True
    false_markers = [
        "not blocked",
        "not currently blocked",
        "no blocker",
        "no blockers",
        "unblocked",
        "blocked_actions",
    ]
    if any(marker in lowered for marker in false_markers):
        return False
    return False


def _is_immediate_skipped_evidence(lowered: str) -> bool:
    status_seen = any(
        marker in lowered
        for marker in [
            '"status": "skipped"',
            "'status': 'skipped'",
            "status=skipped",
            "skipped_with_rationale",
            "considered_not_needed",
            "passthrough",
        ]
    )
    rationale_seen = any(
        marker in lowered
        for marker in [
            "rationale",
            "reason",
            "because",
            "not applicable",
            "not needed",
            "source-of-truth",
            "contract-sensitive",
            "blocked_reason",
        ]
    )
    return status_seen and rationale_seen


def _is_immediate_applied_evidence(lowered: str, aliases: Set[str]) -> bool:
    alias_set = {alias.lower() for alias in aliases}
    if not any(alias in lowered for alias in alias_set):
        return False
    data = _json_object_from_text(lowered)
    if not data:
        return False
    status = str(data.get("status", "")).lower()
    skill = str(data.get("skill", "") or data.get("name", "")).lower()
    mode = str(data.get("application_mode", "")).lower()
    if status != "applied":
        return False
    if skill and skill not in alias_set:
        return False
    if mode == "runtime":
        return True
    return any(key in data for key in ["evidence", "artifacts", "artifact", "source", "result", "metadata"])


def _is_current_skill_support_read(lowered: str, skill_name: str) -> bool:
    folder = skill_name.replace("-", "_").lower()
    if folder not in lowered:
        return False
    if "\\skills\\" not in lowered and "/skills/" not in lowered:
        return False
    support_markers = [
        "skill.md",
        "\\references\\",
        "/references/",
        "\\examples\\",
        "/examples/",
        "\\scripts\\smoke_check.py",
        "/scripts/smoke_check.py",
        "\\scripts\\demo.py",
        "/scripts/demo.py",
    ]
    return any(marker in lowered for marker in support_markers)


def _front_door_latency_issues(path: Path, threshold_seconds: float = 60.0) -> List[Dict[str, Any]]:
    skill_read_sample = ""
    skill_read_at: datetime | None = None
    front_door_sample = ""
    front_door_at: datetime | None = None
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("front-door latency requires indexed event facts")
    for _event_seq, payload, timestamp in events.iter_timed_payloads(
        payload_types=("function_call", "custom_tool_call")
    ):
        payload_type = str(payload.get("type", ""))
        text = _payload_text(payload)
        lowered = text.lower()
        ts = _event_timestamp({"timestamp": timestamp})
        if ts is None:
            continue

        if (
            skill_read_at is None
            and payload_type in {"function_call", "custom_tool_call"}
            and "always_on_front_door" in lowered
            and "skill.md" in lowered
        ):
            skill_read_at = ts
            skill_read_sample = _short(text)
            continue

        if _is_front_door_runtime_command(payload, lowered):
            front_door_at = ts
            front_door_sample = _short(text)
            break

    if skill_read_at is None or front_door_at is None:
        return []
    elapsed = (front_door_at - skill_read_at).total_seconds()
    if elapsed <= threshold_seconds:
        return []
    return [
        {
            "skill": "always-on-front-door",
            "status": "front_door_bootstrap_delay",
            "severity": "P1",
            "reason": (
                f"always-on-front-door SKILL.md was read, but runtime front-door command started "
                f"{elapsed:.1f}s later"
            ),
            "action": (
                "After reading always-on-front-door, run the front-door command as the next standalone "
                "tool call. Do not spend a long reasoning pass on source strategy before intake."
            ),
            "threshold_seconds": threshold_seconds,
            "elapsed_seconds": round(elapsed, 1),
            "skill_read": skill_read_sample,
            "front_door_call": front_door_sample,
        }
    ]


def _event_timestamp(event: Dict[str, Any]) -> datetime | None:
    raw = str(event.get("timestamp", "") or "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _large_output_latency_issues(
    path: Path,
    output_line_threshold: int = 300,
    delay_threshold_seconds: float = 60.0,
) -> List[Dict[str, Any]]:
    pending_output_sample = ""
    pending_at: datetime | None = None
    pending_lines = 0

    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("large-output latency requires indexed event facts")
    for _event_seq, payload, timestamp in events.iter_timed_payloads(
        payload_types=(
            "function_call_output",
            "custom_tool_call_output",
            "message",
            "agent_message",
            "function_call",
            "custom_tool_call",
            "task_complete",
        )
    ):
        payload_type = str(payload.get("type", ""))
        ts = _event_timestamp({"timestamp": timestamp})
        if ts is None:
            continue
        text = _payload_text(payload)

        if payload_type in {"function_call_output", "custom_tool_call_output"}:
            line_count = _reported_output_line_count(text)
            if line_count >= output_line_threshold:
                pending_output_sample = _short(text, 260)
                pending_at = ts
                pending_lines = line_count
            continue

        if not pending_output_sample or pending_at is None:
            continue
        if payload_type not in {"message", "agent_message", "function_call", "custom_tool_call", "task_complete"}:
            continue
        elapsed = (ts - pending_at).total_seconds()
        if elapsed <= delay_threshold_seconds:
            pending_output_sample = ""
            pending_at = None
            pending_lines = 0
            continue
        return [
            {
                "skill": "command-output-harness",
                "status": "large_output_reasoning_delay",
                "severity": "P1",
                "reason": (
                    f"A command returned about {pending_lines} output lines and the next agent action "
                    f"started {elapsed:.1f}s later"
                ),
                "action": (
                    "Use command-output-harness/token-optimizer behavior for broad searches: narrow the "
                    "query, cap output, preserve file/line/error facts, and avoid feeding 300+ raw lines "
                    "back into model context."
                ),
                "output_line_threshold": output_line_threshold,
                "delay_threshold_seconds": delay_threshold_seconds,
                "elapsed_seconds": round(elapsed, 1),
                "sample": pending_output_sample,
            }
        ]
    return []


def _reported_output_line_count(text: str) -> int:
    match = re.search(r"total output lines:\s*(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return text.count("\n") + 1 if text else 0


def _stale_skill_cache_issues(path: Path) -> List[Dict[str, Any]]:
    samples: List[str] = []
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("skill-cache audit requires indexed event facts")
    for _event_seq, payload in events.iter_payloads(
        payload_types=(
            "message",
            "agent_message",
            "task_complete",
            "function_call",
            "custom_tool_call",
            "function_call_output",
            "custom_tool_call_output",
        )
    ):
        text = _payload_text(payload)
        lowered = text.lower()
        if _is_synthetic_context_message(text):
            continue
        if not _is_stale_kh_skill_cache_failure(lowered):
            continue
        samples.append(_short(text))
        if len(samples) >= 3:
            break
    if not samples:
        return []
    return [
        {
            "skill": "skill-catalog",
            "status": "stale_skill_cache_path",
            "severity": "P1",
            "reason": (
                "KH skill loading failed because the session referenced an old Codex plugin cache path. "
                "This can make the host appear to have KH skills while actual SKILL.md reads fail."
            ),
            "action": (
                "Resolve KH skill sources from the current repository `skills/` folder or the latest installed "
                "kh-uaf cache version before claiming skill application. After a plugin upgrade, start a fresh "
                "session or re-run KH front-door routing against the current cache."
            ),
            "samples": samples,
        }
    ]


def _cross_scope_context_issues(path: Path) -> List[Dict[str, Any]]:
    active_target: Path | None = None
    trigger_sample = ""
    samples: List[str] = []

    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("cross-scope audit requires indexed event facts")
    for _event_seq, payload in events.iter_payloads(
        payload_types=("message", "function_call", "custom_tool_call")
    ):
        payload_type = str(payload.get("type", ""))
        text = _payload_text(payload)

        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            targets = _extract_windows_paths(text)
            active_target = _normalize_path(Path(targets[0])) if targets else None
            trigger_sample = _short(text) if targets else ""
            samples = []
            continue

        if active_target is None or payload_type not in {"function_call", "custom_tool_call"}:
            continue

        sample = _cross_scope_context_sample(active_target, text)
        if sample:
            samples.append(sample)
            if len(samples) >= 3:
                break

    if not samples:
        return []
    return [
        {
            "skill": "guard-policy-harness",
            "status": "cross_scope_context_leak",
            "severity": "P1",
            "reason": (
                "The session read a parent directory or sibling run folder while a specific target folder "
                "was requested. That can contaminate a blind or independent SIDE scenario with previous outputs."
            ),
            "action": (
                "Treat the run as contaminated unless the user explicitly requested comparison or reuse. "
                "Restart from the requested target boundary and inspect only that target after front-door routing."
            ),
            "trigger": trigger_sample,
            "samples": samples,
        }
    ]


def _target_substitution_issues(path: Path) -> List[Dict[str, Any]]:
    active_target: Path | None = None
    trigger_sample = ""
    samples: List[str] = []

    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("target-substitution audit requires indexed event facts")
    for _event_seq, payload in events.iter_payloads(
        payload_types=(
            "message",
            "agent_message",
            "task_complete",
            "function_call",
            "custom_tool_call",
            "function_call_output",
            "custom_tool_call_output",
        )
    ):
        payload_type = str(payload.get("type", ""))
        text = _payload_text(payload)

        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            targets = _extract_windows_paths(text)
            if targets:
                active_target = _normalize_path(Path(targets[0]))
                trigger_sample = _short(text)
                samples = []
            continue

        if active_target is None or payload_type not in {
            "message",
            "agent_message",
            "task_complete",
            "function_call",
            "custom_tool_call",
            "function_call_output",
            "custom_tool_call_output",
        }:
            continue

        sample = _target_substitution_sample(active_target, text)
        if sample:
            samples.append(sample)
            if len(samples) >= 3:
                break

    if not samples:
        return []
    return [
        {
            "skill": "guard-policy-harness",
            "status": "target_path_substitution",
            "severity": "P0",
            "reason": (
                "The user named an absolute target folder, but generated files were written to a relative "
                "substitute folder instead of the exact requested path."
            ),
            "action": (
                "Do not create staging or same-name relative folders for an absolute user target. If the "
                "exact target path is outside the writable workspace or needs permission, stop before "
                "generation and report blocked/permission-needed status."
            ),
            "trigger": trigger_sample,
            "samples": samples,
        }
    ]


def _global_memory_scope_issues(path: Path) -> List[Dict[str, Any]]:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("memory scope audit requires indexed event facts")
    if (
        events.reducer_matched_count("global_memory_scope") == 0
        and not events.has_fact_kinds(("memory_approval", "memory_reference"))
    ):
        return []
    front_door_brainstorm_gate = _front_door_selected_skill(path, "brainstorming-harness") or _front_door_blocks_execution(path)
    new_project_context = _session_has_new_project_discovery_request(path)
    _memory_import_approval_decisions(
        events,
        _session_metadata(path),
    )
    explicit_import_active = False
    read_samples: List[str] = []
    citation_samples: List[str] = []
    for _event_index, payload, decision in events.iter_payloads_with_memory_decision(
        payload_types=(
            "message",
            "agent_message",
            "task_complete",
            "function_call",
            "custom_tool_call",
            "function_call_output",
            "custom_tool_call_output",
        )
    ):
        payload_type = str(payload.get("type", ""))
        if payload_type == "message" and str(payload.get("role", "")).lower() in {"developer", "system"}:
            continue
        if _is_synthetic_context_message(_payload_text(payload)):
            continue
        if decision == "approve":
            explicit_import_active = True
        elif decision == "revoke":
            explicit_import_active = False
        if payload_type in {"function_call", "custom_tool_call"}:
            text = _payload_text(payload)
            sample = _global_codex_memory_sample(text)
            if sample and not explicit_import_active:
                read_samples.append(sample)
        sample = _global_codex_memory_citation_sample(payload)
        if sample and not explicit_import_active:
            citation_samples.append(sample)
        if len(read_samples) >= 3 and len(citation_samples) >= 3:
            break

    issues: List[Dict[str, Any]] = []
    if citation_samples:
        issues.append(
            {
                "skill": "memory-state-harness",
                "status": "global_memory_citation_without_scope_approval",
                "severity": "P1",
                "reason": (
                    "The session cited host-global Codex memory in its final/user-facing output without an "
                    "explicit global memory reuse request or approved cross-scope import. A citation proves "
                    "that global memory affected the answer, so it cannot be treated as project/chat-scoped KH memory."
                ),
                "action": (
                    "Do not use or cite `%CODEX_HOME%/memories/MEMORY.md` or `%CODEX_HOME%/memories/skills/...` "
                    "unless the user explicitly asks to reuse/import global memory. A session id authorizes reading "
                    "that session log, not broad MEMORY.md application."
                ),
                "samples": citation_samples[:3],
            }
        )

    if not read_samples:
        return issues

    if not front_door_brainstorm_gate and new_project_context:
        issues.append(
            {
                "skill": "memory-state-harness",
                "status": "global_memory_shortcut_without_brainstorm_gate",
                "severity": "P0",
                "reason": (
                    "A fresh or underspecified project request read global Codex memory or memory-skill notes "
                    "before KH established a brainstorming gate. This lets stale cross-chat implementation "
                    "patterns override current project/chat-scoped direction discovery."
                ),
                "action": (
                    "Treat new app/site/dashboard/project requests as brainstorming-gated before any "
                    "`%CODEX_HOME%/memories/MEMORY.md` or `%CODEX_HOME%/memories/skills/...` lookup. "
                    "If front-door fails to select brainstorming, stop and record router_failure instead of "
                    "using memory-derived implementation shortcuts."
                ),
                "samples": read_samples[:3],
            }
        )
        return issues
    if not front_door_brainstorm_gate:
        issues.append(
            {
                "skill": "memory-state-harness",
                "status": "global_memory_lookup_without_scope_approval",
                "severity": "P1",
                "reason": (
                    "The session read host-global Codex memory without an explicit prior-context request, "
                    "approved cross-scope import, or scoped KH memory evidence. Similar keywords in old chats "
                    "must not become current project/chat memory by default."
                ),
                "action": (
                    "Use project/chat-scoped KH memory by default. Read `%CODEX_HOME%/memories/...` only when "
                    "the user explicitly requests prior context or when memory-state-harness records "
                    "explicit_cross_scope_memory_import, parent_memory_access, or global_memory_candidate approval evidence."
                ),
                "samples": read_samples[:3],
            }
        )
        return issues
    issues.append(
        {
            "skill": "memory-state-harness",
            "status": "cross_chat_memory_leak",
            "severity": "P1",
            "reason": (
                "Front-door blocked execution for brainstorming, but the session read global Codex memory "
                "or memory-skill notes from another chat/subagent scope. That memory is not the current "
                "project/chat-scoped KH memory and must not override the current execution gate."
            ),
            "action": (
                "Do not read `%CODEX_HOME%/memories/MEMORY.md` or `%CODEX_HOME%/memories/skills/...` "
                "while `execution_gate.can_execute=false` unless the user explicitly asks for prior-context reuse. "
                "Use only current project/chat-scoped KH memory after scope resolution, or record memory_provider=blocked."
            ),
            "samples": read_samples[:3],
        }
    )
    return issues


def _session_has_new_project_discovery_request(path: Path) -> bool:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("project discovery requires indexed event facts")
    for _event_seq, payload in events.iter_payloads(
        payload_types=("message",),
        roles=("user",),
    ):
        text = _payload_text(payload)
        if _requires_fresh_brainstorming_direction(text):
            return True
    return False


def _requires_fresh_brainstorming_direction(text: str) -> bool:
    """Return true only for fresh, underspecified direction-discovery work."""

    lowered = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if not lowered or _is_synthetic_context_message(text):
        return False

    existing_artifact_signals = [
        r"\b[a-z][a-z0-9_]*\.(?:designer\.)?(?:cs|sql|py|js|ts|tsx|jsx|html|css|srd|srw|sru)\b",
        r"\b(?:select|insert|update|delete|merge|join|where|group\s+by|order\s+by)\b",
        r"\b(?:stored\s+procedure|procedure|function|class|method|designer|tabindex)\b",
        r"\b(?:error|exception|bug|failure|diagnos|debug|trace|inspect|format|refactor|fix|modify|rename)\w*\b",
        r"(?:오류|에러|버그|원인|진단|디버깅|추적|확인해|점검해|수정해|고쳐|추가해|정리해|포맷|별칭|쿼리|프로시저|디자이너|탭인덱스)",
    ]
    if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in existing_artifact_signals):
        return False

    domain_signals = [
        r"\b(?:product|project|app|application|website|web\s*site|webpage|homepage|dashboard|"
        r"workflow|process|policy|research|analysis|specification|drawing|operating\s+model)\b",
        r"(?:제품|프로젝트|앱|애플리케이션|사이트|웹사이트|웹페이지|홈페이지|대시보드|"
        r"업무\s*흐름|워크플로|프로세스|정책|리서치|연구|기획|설계도|도면|운영\s*모델)",
    ]
    discovery_signals = [
        r"\b(?:brainstorm|new|fresh|from\s+scratch|idea|direction|scope|options?|alternatives?|"
        r"requirements?|plan(?:ning)?|want\s+to\s+(?:build|create|make|design)|"
        r"help\s+me\s+(?:build|create|make|design))\b",
        r"(?:신규|새로|처음부터|아이디어|방향|범위|선택지|대안|요구사항|요건|계획|"
        r"기획|브레인스토밍|만들고\s*싶|만들어\s*보고\s*싶|구상|어떻게\s*구성)",
    ]
    has_domain = any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in domain_signals)
    has_discovery = any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in discovery_signals)
    return bool(has_domain and has_discovery)


def _active_non_front_door_texts(path: Path) -> Iterator[str]:
    for text in _session_texts(path):
        if _is_passive_text(text):
            continue
        clean_text = _strip_passive_prefix(text)
        if _looks_like_front_door_runtime_output(clean_text.lower()):
            continue
        yield clean_text


def _brainstorming_depth_issues(
    path: Path,
    *,
    active_text: str | None = None,
) -> List[Dict[str, Any]]:
    if active_text is None:
        active_text = _bounded_text_aggregate(_active_non_front_door_texts(path))
    lowered = active_text.lower()
    if looks_like_sql_output_request(lowered):
        return []
    front_door_selected_brainstorming = _front_door_selected_skill(path, "brainstorming-harness")
    front_door_blocked_execution = _front_door_blocks_execution(path)
    if not (_early_domain_discovery_text(lowered) or front_door_selected_brainstorming or front_door_blocked_execution):
        return []

    request_input_count = _function_call_count(path, {"request_user_input"})
    implementation_samples = _implementation_tool_samples(path)
    has_session_record = any(
        marker in lowered
        for marker in [
            "brainstormsession",
            "validate_brainstorm_session",
            "decision_log",
            "target_user",
        ]
    )
    has_handoff = any(
        marker in lowered
        for marker in [
            "brainstorm_handoff",
            "build_architect_handoff",
            ".kh/brainstorm",
            "docs/kh/handoffs",
        ]
    )
    has_options = any(marker in lowered for marker in ["option", "options", "direction", "alternatives", "recommendation"])
    first_response = _first_visible_brainstorm_response(path)
    missing_visible_markers = _brainstorm_response_missing_markers(first_response)
    unilateral_markers = _brainstorm_unilateral_decision_markers(first_response)

    issues: List[Dict[str, Any]] = []
    if missing_visible_markers:
        issues.append(
            {
                "skill": "brainstorming-harness",
                "status": "shallow_visible_brainstorming",
                "severity": "P1",
                "reason": (
                    "The visible brainstorming response did not meet the Superpowers-style multi-checkpoint "
                    "quality bar before asking for approval."
                ),
                "action": (
                    "Before approval, cover objective/operator, workflow boundary, success or constraints, "
                    "2-3 operating-model options with tradeoffs, required records/data, recommendation, "
                    "open questions, and one next approval question."
                ),
                "missing_markers": missing_visible_markers,
                "sample": _short(first_response, 420),
            }
        )
    if unilateral_markers:
        issues.append(
            {
                "skill": "brainstorming-harness",
                "status": "unilateral_brainstorm_decision",
                "severity": "P1",
                "reason": (
                    "The visible brainstorming response framed a recommendation as an agent-owned decision "
                    "before the user approved the operating model or implementation stack."
                ),
                "action": (
                    "Phrase recommendations as tentative advice, preserve open choices, ask the user to choose "
                    "or approve, and do not lock an implementation stack before the domain direction is approved."
                ),
                "matched_markers": unilateral_markers,
                "sample": _short(first_response, 420),
            }
        )
    if implementation_samples and not (has_session_record and has_handoff):
        status = (
            "brainstorming_execution_gate_bypassed"
            if front_door_selected_brainstorming or front_door_blocked_execution
            else "missing_brainstorm_handoff"
        )
        issues.append(
            {
                "skill": "brainstorming-harness",
                "status": status,
                "severity": "P0" if status == "brainstorming_execution_gate_bypassed" else "P1",
                "reason": (
                    "Front-door selected brainstorming, but the session moved into execution without "
                    "BrainstormSession validation, explicit later user approval, and brainstorm_handoff evidence."
                    if status == "brainstorming_execution_gate_bypassed"
                    else "Early domain discovery moved into execution without BrainstormSession "
                    "validation and brainstorm_handoff evidence."
                ),
                "action": (
                    "Honor execution_gate.can_execute=false: do not use memory-derived shortcuts, scaffold, "
                    "write files, create deliverables, or verify until the multi-checkpoint brainstorming flow "
                    "preserves BrainstormSession/decision_log, validates it, gets later user approval, and builds brainstorm_handoff."
                ),
                "samples": implementation_samples[:3],
            }
        )
    elif (
        request_input_count <= 1
        and has_options
        and not has_handoff
        and _claims_brainstorming_complete_or_next_stage(lowered)
    ):
        issues.append(
            {
                "skill": "brainstorming-harness",
                "status": "single_checkpoint_brainstorming",
                "severity": "P2",
                "reason": (
                    "The run looks like a one-question option picker rather than a Superpowers-style "
                    "multi-checkpoint brainstorm with preserved KH handoff evidence."
                ),
                "action": (
                    "Collect objective, target user, problem, constraints, success criteria, options, recommendation, "
                    "decision log, open questions, and handoff evidence before treating brainstorming as complete."
                ),
            }
        )
    return issues


def _host_local_sql_formatting_issues(path: Path) -> List[Dict[str, Any]]:
    return list(_host_local_sql_formatting_audit(path)["issues"])


def _pb_migration_execution_audit(
    path: Path,
) -> Dict[str, Any]:
    events = _session_payload_events(path)
    session_cwd = str(_session_metadata(path).get("cwd", "") or "").strip()
    duplicate_call_ids = _duplicate_tool_call_ids(events)
    duplicate_boundaries = _duplicate_front_door_boundaries(events)
    duplicate_packet_hashes = _duplicate_general_tool_packet_hashes(events)
    receipts = _correlated_tool_receipts(events, include_failed=True)
    front_door_candidates = _paired_front_door_candidates(events)
    front_door_history: List[Dict[str, Any]] = []
    front_door_history_total = 0
    front_door_accepted_total = 0
    latest_front_door_output = -1
    latest_accepted_front_door_output = -1
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("PB migration audit requires the streaming fact store")
    events._db.execute("DELETE FROM pb_front_door_acceptance")
    verified_correction_indexes = _verified_bounded_pb_correction_indexes(
        events,
        receipts,
        session_cwd=session_cwd,
    )
    for receipt in front_door_candidates:
        call_text = _payload_text(receipt.call)
        if not _is_front_door_runtime_command(receipt.call, call_text.lower()):
            continue
        data = _front_door_json(_payload_text(receipt.output))
        raw_data = _json_object_from_text(_payload_text(receipt.output))
        provenance_valid = _valid_host_front_door_provenance(
            receipt.call,
            receipt.output,
            raw_data,
            duplicate_boundaries=duplicate_boundaries,
            duplicate_packet_hashes=duplicate_packet_hashes,
        )
        selection_valid = bool(data and _structured_pb_migration_selection(data))
        execution_valid = bool(
            selection_valid
            and (
                _runtime_tool_output_succeeded(receipt.output)
                or _is_strict_blocked_front_door_packet(data)
            )
        )
        accepted = provenance_valid and execution_valid
        history_item = {
            "call_id": _payload_call_id(receipt.call),
            "call_index": receipt.call_index,
            "output_index": receipt.output_index,
            "status": "accepted" if accepted else "claimed_unverified",
            "provenance_valid": provenance_valid,
            "selection_valid": selection_valid,
            "execution_valid": execution_valid,
            "authoritative_style": False,
        }
        front_door_history_total += 1
        latest_front_door_output = receipt.output_index
        if accepted:
            front_door_accepted_total += 1
            latest_accepted_front_door_output = receipt.output_index
        events._db.execute(
            "INSERT INTO pb_front_door_acceptance(output_seq, accepted) VALUES (?, ?)",
            (receipt.output_index, int(accepted)),
        )
        if len(front_door_history) < _PB_FRONT_DOOR_HISTORY_SAMPLE_LIMIT:
            front_door_history.append(history_item)
        else:
            front_door_history[-1] = history_item
    for item in front_door_history:
        item["superseded_by_later_correction"] = verified_correction_indexes.has_after(
            item["output_index"]
        )
        item["current"] = bool(
            item["output_index"] == latest_front_door_output
            and not item["superseded_by_later_correction"]
        )
        item["current_accepted"] = (
            item["output_index"] == latest_accepted_front_door_output
            and not item["superseded_by_later_correction"]
        )

    routed = False
    contextual = False
    write_receipts = []
    for receipt in receipts.iter_range(
        require_succeeded=True,
        implementation_only=True,
    ):
        targets = _extract_pb_csharp_write_targets(receipt.call)
        if not targets:
            continue
        task_boundary, task_text = _latest_user_task_scope(events, receipt.call_index)
        write_contextual = _is_pb_migration_task_scope(task_text)
        write_routed = bool(
            events._db.execute(
                """
                SELECT 1
                FROM pb_front_door_acceptance
                WHERE accepted = 1 AND output_seq > ? AND output_seq < ?
                LIMIT 1
                """,
                (task_boundary, receipt.call_index),
            ).fetchone()
        )
        if not (write_contextual or write_routed):
            continue
        contextual = contextual or write_contextual
        routed = routed or write_routed
        write_receipts.append((receipt, targets))
    last_write_index = max((receipt.output_index for receipt, _ in write_receipts), default=-1)
    written_targets = {
        target
        for _, targets in write_receipts
        for target in targets
    }
    targets_extractable = bool(write_receipts) and all(targets for _, targets in write_receipts)
    verifier_receipts = []
    verifier_attempts = []
    invalid_invocations: List[Dict[str, Any]] = []
    verifier_evaluations: List[Dict[str, Any]] = []
    output_evidence: Dict[str, List[Dict[str, Any]]] = {
        name: [] for name in _PB_MIGRATION_REQUIRED_OUTPUTS
    }
    verification_receipts = (
        receipts.iter_range(after_index=last_write_index)
        if last_write_index >= 0
        else ()
    )
    for receipt in verification_receipts:
        invocation = _pb_migration_verifier_invocation(receipt.call)
        if invocation.get("identified") and not invocation["valid"]:
            invalid_invocations.append(
                {
                    "call_id": _payload_call_id(receipt.call),
                    "verifier_name": invocation.get("verifier_name", ""),
                    "reason": invocation.get("reason", "invalid_verifier_invocation"),
                    "claim_status": "claimed_unverified",
                }
            )
            continue
        if not invocation["valid"]:
            independent = _pb_independent_stage_receipt(
                receipt,
                session_cwd=session_cwd,
                written_targets=written_targets,
            )
            if independent:
                output_evidence[independent["output"]].append(independent)
            continue
        verifier_attempts.append(receipt)
        evaluation = _pb_verifier_receipt_evidence(
            receipt,
            invocation=invocation,
            written_targets=written_targets,
            session_cwd=session_cwd,
        )
        evaluation["call_id"] = _payload_call_id(receipt.call)
        verifier_evaluations.append(evaluation)
        if not evaluation["receipt_valid"]:
            continue
        verifier_receipts.append(receipt)
        for output_name in evaluation["satisfied_outputs"]:
            output_evidence[output_name].append(
                {
                    "call_id": _payload_call_id(receipt.call),
                    "verifier_name": invocation["verifier_name"],
                    "status": "passed",
                    "verified_targets": evaluation["verified_targets"],
                }
            )

    valid_evaluations = [item for item in verifier_evaluations if item.get("receipt_valid")]
    completion_requested = any(item.get("completion_requested") for item in valid_evaluations)
    completion_claims: Dict[str, Any] = {}
    for item in valid_evaluations:
        claims = item.get("completion_claims")
        if isinstance(claims, Mapping):
            completion_claims.update(dict(claims))
    designer_applicable = any(item.get("designer_applicable") for item in valid_evaluations)
    required_outputs = list(_PB_MIGRATION_CORE_OUTPUTS)
    if completion_requested:
        required_outputs.extend(["project_inclusion_verification", "build_verification"])
        if designer_applicable:
            required_outputs.append("designer_layout_verification")
        if completion_claims.get("database_equivalence") is True:
            required_outputs.append("database_verification")
        if completion_claims.get("deployment") is True:
            required_outputs.append("deployment_verification")
        required_outputs.append("manual_qa")
    satisfied_outputs = [name for name in _PB_MIGRATION_REQUIRED_OUTPUTS if output_evidence[name]]
    missing_outputs = [name for name in required_outputs if not output_evidence[name]]
    unverified_claims = _pb_unverified_execution_claims(
        events,
        after_index=last_write_index,
    )
    result = {
        "required": bool(write_receipts),
        "routed": routed,
        "contextual": contextual,
        "relevant_writes": [
            {
                "call_id": _payload_call_id(receipt.call),
                "output_index": receipt.output_index,
                "targets": sorted(targets),
                "sample": _short(_payload_text(receipt.call)),
            }
            for receipt, targets in write_receipts
        ],
        "last_write_index": last_write_index,
        "written_targets": sorted(written_targets),
        "targets_extractable": targets_extractable,
        "verifier_attempted": bool(verifier_attempts),
        "verifier_executed": bool(verifier_receipts),
        "draft_validated": any(
            item.get("receipt_valid") and item.get("core_validation_passed")
            for item in verifier_evaluations
        ),
        "completion_requested": completion_requested,
        "completion_claims": completion_claims,
        "verifier_completed": bool(
            completion_requested
            and not missing_outputs
            and any(
                item.get("receipt_valid") and item.get("completion_allowed")
                for item in verifier_evaluations
            )
        ),
        "verifier_call_ids": [_payload_call_id(receipt.call) for receipt in verifier_receipts],
        "verifier_receipts": verifier_evaluations,
        "invalid_verifier_invocations": invalid_invocations,
        "required_outputs": required_outputs,
        "satisfied_outputs": satisfied_outputs,
        "missing_outputs": missing_outputs,
        "output_evidence": output_evidence,
        "style_application_status": (
            "applied"
            if output_evidence["packaged_profile"]
            else "blocked_missing_packaged_fixed_profile_receipt"
        ),
        "authoritative_style_source": (
            "correlated_pb_verifier_receipt"
            if output_evidence["packaged_profile"]
            else "none"
        ),
        "front_door_history": front_door_history,
        "verified_correction_indexes": verified_correction_indexes.bounded_samples(),
        "claimed_unverified": unverified_claims,
        "duplicate_call_ids": duplicate_call_ids,
    }
    if front_door_history_total > len(front_door_history):
        result["front_door_history_total"] = front_door_history_total
        result["front_door_history_status_counts"] = {
            "accepted": front_door_accepted_total,
            "claimed_unverified": front_door_history_total - front_door_accepted_total,
        }
        result["front_door_history_truncated"] = True
    verified_correction_count = len(verified_correction_indexes)
    if verified_correction_count > len(result["verified_correction_indexes"]):
        result["verified_correction_index_total"] = verified_correction_count
        result["verified_correction_indexes_truncated"] = True
    return result


def _latest_user_task_scope(
    events: Sequence[Dict[str, Any]],
    before_index: int,
) -> tuple[int, str]:
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("PB task scope requires indexed event facts")
    task_boundary = -1
    task_text = ""
    for index, payload in events.iter_payloads(
        payload_types=("task_complete", "message"),
        stop=before_index,
    ):
        if str(payload.get("type", "")) == "task_complete":
            task_boundary = index
            task_text = ""
            continue
        if (
            str(payload.get("type", "")) == "message"
            and str(payload.get("role", "")).strip().lower() == "user"
        ):
            text = _strip_passive_prefix(_payload_text(payload))
            if text and not _is_synthetic_context_message(text):
                if (
                    task_text
                    and _is_pb_migration_task_scope(task_text)
                    and not _is_pb_migration_task_scope(text)
                    and not _is_pb_route_followup(text)
                ):
                    task_boundary = index
                    task_text = text[:_SESSION_TEXT_AGGREGATE_LIMIT]
                    continue
                if not task_text:
                    task_boundary = index
                task_text = _bounded_text_aggregate((task_text, text))
    return task_boundary, task_text


def _is_pb_route_followup(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if not normalized:
        return False
    if _is_explicit_new_objective_transition(normalized):
        return False
    return bool(
        re.search(
            r"^(?:continue|proceed|keep|also|same|again|계속|이어서|그대로|추가로|또한)\b",
            normalized,
        )
        or re.search(r"\b(?:routed|current correction|existing event|nested)\b", normalized)
        or "현재 라우팅된" in normalized
        or "기존 이벤트" in normalized
        or _is_bounded_pb_correction_text(normalized)
    )


def _is_bounded_pb_correction_text(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    has_correction = bool(
        re.search(r"\b(?:correct(?:ed|ion|ive)?|fix(?:ed|es|ing)?|baseline)\b", normalized)
        or "수정" in normalized
    )
    has_boundary = bool(
        re.search(r"\b(?:later|current|bounded|baseline|existing)\b", normalized)
        or re.search(r"\b[0-9a-f]{8,}\b", normalized)
    )
    return bool(has_correction and has_boundary and not _is_explicit_new_objective_transition(normalized))


def _paired_front_door_candidates(
    events: Sequence[Dict[str, Any]],
) -> Iterable[CorrelatedToolReceipt]:
    if isinstance(events, DiskBackedSessionEvents):
        rows = events._db.execute(
            """
            SELECT calls.*, outputs.*
            FROM event_payloads AS calls
            JOIN event_payloads AS outputs ON outputs.call_id = calls.call_id
            JOIN front_door_claims AS claims ON claims.event_seq = outputs.seq
            WHERE calls.event_type = 'response_item'
              AND outputs.event_type = 'response_item'
              AND calls.payload_type IN ('function_call', 'custom_tool_call')
              AND outputs.payload_type = CASE calls.payload_type
                    WHEN 'function_call' THEN 'function_call_output'
                    ELSE 'custom_tool_call_output'
                  END
              AND calls.seq < outputs.seq
              AND calls.call_id <> ''
              AND calls.call_id IN (
                  SELECT fact_key
                  FROM facts
                  WHERE kind IN ('tool_call', 'tool_output')
                  GROUP BY fact_key
                  HAVING SUM(CASE WHEN kind = 'tool_call' THEN 1 ELSE 0 END) = 1
                     AND SUM(CASE WHEN kind = 'tool_output' THEN 1 ELSE 0 END) = 1
              )
            ORDER BY calls.seq
            """
        )
        for row in rows:
            output_offset = _EVENT_PAYLOAD_VIEW_COLUMN_COUNT
            call = _payload_from_event_view_row(row)
            if not _is_front_door_runtime_command(call, _payload_text(call).lower()):
                continue
            output = _payload_from_event_view_row(row, output_offset)
            yield CorrelatedToolReceipt(
                call_index=int(row[0]),
                output_index=int(row[output_offset]),
                call=call,
                output=output,
                data=_json_object_from_text(_payload_text(output)),
            )
        return
    raise RuntimeError("front-door pairing requires the streaming fact store")


def _verified_bounded_pb_correction_indexes(
    events: Sequence[Dict[str, Any]],
    receipts: Sequence[CorrelatedToolReceipt],
    *,
    session_cwd: str,
) -> DiskBackedVerifiedCorrectionIndexes:
    if not isinstance(events, DiskBackedSessionEvents) or not isinstance(
        receipts, DiskBackedToolReceipts
    ):
        raise RuntimeError("PB correction verification requires indexed receipt facts")
    events._db.execute("DELETE FROM pb_verified_corrections")
    events._db.execute("DELETE FROM pb_active_implementations")
    events._pb_correlation_replay_count += 1
    correction_rows = iter(events._db.execute(
        """
        SELECT correction_seq
        FROM pb_correction_candidates
        ORDER BY correction_seq
        """
    ))
    boundary_rows = iter(events._db.execute(
        """
        SELECT seq
        FROM events
        WHERE payload_type = 'task_complete'
           OR (payload_type = 'message' AND role = 'user')
           OR (payload_type = 'thread_goal_updated'
               AND goal_status IN ('complete', 'blocked'))
        ORDER BY seq
        """
    ))
    receipt_rows = iter(receipts.iter_ordered_by_output())
    correction = next(correction_rows, None)
    boundary = next(boundary_rows, None)
    receipt = next(receipt_rows, None)
    active_correction = -1
    active_verified = False
    while correction is not None or boundary is not None or receipt is not None:
        choices: List[tuple[int, int, str]] = []
        if boundary is not None:
            choices.append((int(boundary[0]), 0, "boundary"))
        if correction is not None:
            choices.append((int(correction[0]), 1, "correction"))
        if receipt is not None:
            choices.append((int(receipt.output_index), 2, "receipt"))
        _index, _priority, kind = min(choices)
        if kind == "boundary":
            active_correction = -1
            events._db.execute("DELETE FROM pb_active_implementations")
            active_verified = False
            boundary = next(boundary_rows, None)
            continue
        if kind == "correction":
            active_correction = int(correction[0])
            events._db.execute("DELETE FROM pb_active_implementations")
            active_verified = False
            correction = next(correction_rows, None)
            continue

        current = receipt
        receipt = next(receipt_rows, None)
        if (
            active_correction < 0
            or active_verified
            or current.call_index <= active_correction
        ):
            continue
        if (
            _runtime_tool_output_succeeded(current.output)
            and _is_implementation_call(current.call)
        ):
            targets = _extract_pb_csharp_write_targets(current.call)
            if targets:
                events._db.execute(
                    """
                    INSERT OR REPLACE INTO pb_active_implementations(
                        output_seq, targets_json
                    ) VALUES (?, ?)
                    """,
                    (current.output_index, _canonical_json(sorted(targets))),
                )
            continue
        if not _runtime_tool_output_succeeded(current.output):
            continue
        for implementation_output, targets_json in events._db.execute(
            """
            SELECT output_seq, targets_json
            FROM pb_active_implementations
            WHERE output_seq < ?
            ORDER BY output_seq
            """,
            (current.call_index,),
        ):
            targets = {
                str(item)
                for item in _json_scalar_sequence(targets_json)
                if str(item)
            }
            if current.call_index <= implementation_output:
                continue
            if _pb_correction_verification_proves_targets(
                current,
                targets=targets,
                session_cwd=session_cwd,
            ):
                events._db.execute(
                    """
                    INSERT OR IGNORE INTO pb_verified_corrections(correction_seq)
                    VALUES (?)
                    """,
                    (active_correction,),
                )
                active_verified = True
                events._db.execute("DELETE FROM pb_active_implementations")
                break
    return DiskBackedVerifiedCorrectionIndexes(events)


def _pb_correction_evidence_boundary(
    events: Sequence[Dict[str, Any]],
    correction_index: int,
) -> int:
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("PB correction boundaries require indexed event facts")
    for index, payload in events.iter_payloads(
        payload_types=("task_complete", "message", "thread_goal_updated"),
        start=correction_index + 1,
    ):
        payload_type = str(payload.get("type", ""))
        if payload_type == "task_complete":
            return index
        if payload_type == "message" and str(payload.get("role", "")).strip().lower() == "user":
            return index
        if payload_type == "thread_goal_updated":
            goal = payload.get("goal", {})
            if isinstance(goal, Mapping) and str(goal.get("status", "")).strip().lower() in {
                "complete",
                "blocked",
            }:
                return index
    return len(events)


def _pb_correction_verification_proves_targets(
    receipt: CorrelatedToolReceipt,
    *,
    targets: Set[str],
    session_cwd: str,
) -> bool:
    invocation = _pb_migration_verifier_invocation(receipt.call)
    if not invocation.get("valid"):
        return False
    evaluation = _pb_verifier_receipt_evidence(
        receipt,
        invocation=invocation,
        written_targets=targets,
        session_cwd=session_cwd,
    )
    verified_targets = {
        _normalize_pb_target_path(str(value))
        for value in evaluation.get("verified_targets", [])
        if _normalize_pb_target_path(str(value))
    }
    normalized_targets = {
        _normalize_pb_target_path(value)
        for value in targets
        if _normalize_pb_target_path(value)
    }
    return bool(
        evaluation.get("receipt_valid") is True
        and "csharp_verification" in evaluation.get("satisfied_outputs", [])
        and normalized_targets
        and _pb_targets_cover(
            normalized_targets,
            verified_targets,
            session_cwd=session_cwd,
        )
    )


def _is_pb_migration_task_scope(text: str) -> bool:
    value = str(text or "")
    has_pb_artifact = bool(
        re.search(
            r"(?i)(?:\bpowerbuilder\b|\bpb\b|\bpbl\b|\bpbd\b|\bsru\b|\bsrd\b|\bsrw\b|"
            r"\bdata\s*window\b|\bdatawindow\b|\bgwerp\b)",
            value,
        )
    )
    has_csharp_target = bool(
        re.search(
            r"(?i)(?:c#|\.designer\.cs\b|(?<![a-z0-9_])\.cs\b|\bdesigner\b|"
            r"\bwinforms?\b|\bdevexpress\b|\bkonelib\b)",
            value,
        )
    )
    if not (has_pb_artifact and has_csharp_target):
        return False

    migration_intent = bool(
        re.search(
            r"(?i)\b(?:migrat(?:e|ed|ing|ion)|convert(?:ed|ing|ion)?|port(?:ed|ing)?|"
            r"reimplement(?:ed|ing|ation)?|rewrite|transform|translate)\b",
            value,
        )
        or re.search(
            "(?:\ub9c8\uc774\uadf8\ub808\uc774\uc158|\ubcc0\ud658|\uc774\uad00|\ud3ec\ud305|"
            "\uc7ac\uc791\uc131|\uc804\ud658|\uc62e\uaca8|\ubc14\uafd4|\uc0c8\ub85c\\s*\uac1c\ubc1c)",
            value,
        )
    )
    directional_transformation = bool(
        re.search(
            r"(?is)(?:\bpowerbuilder\b|\bpb\b|\bpbl\b|\bsru\b|\bsrd\b|\bsrw\b|\bdata\s*window\b)"
            r".{0,160}(?:\bto\b|\binto\b|\bas\b|->|=>).{0,80}(?:c#|\.designer\.cs\b|\bwinforms?\b)",
            value,
        )
        or re.search(
            r"(?is)(?:c#|\.designer\.cs\b|\bwinforms?\b).{0,120}\bfrom\b.{0,80}"
            r"(?:\bpowerbuilder\b|\bpb\b|\bpbl\b|\bsru\b|\bsrd\b|\bsrw\b|\bdata\s*window\b)",
            value,
        )
    )
    return migration_intent or directional_transformation


def _structured_pb_migration_selection(data: Mapping[str, Any]) -> bool:
    skill = "pb-to-csharp-migration-harness"
    for key in [
        "runtime_applied_skills",
        "selected_not_executed_skills",
        "immediate_next_skills",
        "recommended_skills",
    ]:
        value = data.get(key, [])
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if skill in {str(item) for item in value}:
                return True
    for key in ["skill_status_summary", "skill_statuses"]:
        statuses = data.get(key, {})
        if not isinstance(statuses, Mapping) or skill not in statuses:
            continue
        status = statuses.get(skill)
        if isinstance(status, Mapping):
            status = status.get("status", "")
        if str(status).strip().lower() not in {"", "absent", "not_required"}:
            return True
    return (
        str(data.get("skill", "")).strip() == skill
        and str(data.get("status", "")).strip().lower()
        not in {"", "absent", "not_required"}
    )


_PB_MIGRATION_VERIFIERS = {
    "verify_migration_generated_csharp_style",
    "orchestrate_pb_migration_validation",
}
_PB_ORCHESTRATE_REQUIRED_KEYWORDS = {
    "csharp_source_text",
    "designer_source_text",
    "original_sql_text",
    "formatted_sql_text",
    "profile_id",
    "profile_version",
    "profile_hash",
}
_PB_MIGRATION_CORE_OUTPUTS = (
    "packaged_profile",
    "csharp_verification",
    "designer_verification",
    "sp_verification",
    "sql_binding_release",
)
_PB_MIGRATION_COMPLETION_OUTPUTS = (
    "project_inclusion_verification",
    "build_verification",
    "designer_layout_verification",
    "database_verification",
    "deployment_verification",
    "manual_qa",
)
_PB_MIGRATION_REQUIRED_OUTPUTS = (
    *_PB_MIGRATION_CORE_OUTPUTS,
    *_PB_MIGRATION_COMPLETION_OUTPUTS,
)
_PB_PACKAGED_PROFILE_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "pb_to_csharp_migration_harness"
    / "references"
    / "packaged-style-contract.json"
)


def _pb_migration_verifier_invocation(payload: Dict[str, Any]) -> Dict[str, Any]:
    if str(payload.get("type", "")) not in {"function_call", "custom_tool_call"}:
        return {"identified": False, "valid": False, "targets": []}
    name = str(payload.get("name", "") or "").strip().lower().replace("-", "_")
    tail = re.split(r"[.:]", name)[-1]
    arguments = _payload_arguments_text(payload)
    if tail in _PB_MIGRATION_VERIFIERS:
        argument_mapping = _pb_payload_argument_mapping(payload)
        if argument_mapping is None:
            return {
                "identified": True,
                "valid": False,
                "verifier_name": tail,
                "targets": [],
                "reason": "verifier_arguments_must_be_a_json_object",
            }
        return _pb_validate_verifier_invocation_shape(
            tail,
            argument_names=set(argument_mapping),
            positional_count=0,
            literal_arguments=argument_mapping,
        )
    if any(marker in name for marker in ["read", "search", "find", "grep", "view", "open", "list", "text", "print"]):
        return {"identified": False, "valid": False, "targets": []}

    record = SessionTextRecord(
        text=_payload_text(payload),
        payload_type=str(payload.get("type", "")),
        name=str(payload.get("name", "")),
        arguments=arguments,
    )
    command = _exact_shell_command_text(record)
    if not command:
        return {"identified": False, "valid": False, "targets": []}
    return _python_command_pb_verifier_invocation(command)


def _pb_payload_argument_mapping(payload: Mapping[str, Any]) -> Dict[str, Any] | None:
    raw = payload.get("arguments")
    if raw is None:
        raw = payload.get("input")
    if isinstance(raw, Mapping):
        return dict(raw)
    if not isinstance(raw, str):
        return None
    try:
        parsed = load_json_without_duplicate_keys(raw)
    except (json.JSONDecodeError, DuplicateJsonKeyError):
        return None
    return dict(parsed) if isinstance(parsed, Mapping) else None


def _python_command_invokes_pb_verifier(command: str) -> bool:
    return bool(_python_command_pb_verifier_invocation(command)["valid"])


def _python_command_pb_verifier_invocation(command: str) -> Dict[str, Any]:
    if not command or _contains_unquoted_shell_control(command):
        return {"identified": False, "valid": False, "targets": []}
    try:
        tokens = [_strip_shell_token_quotes(item) for item in shlex.split(command, posix=False)]
    except ValueError:
        return {"identified": False, "valid": False, "targets": []}
    if not tokens or Path(tokens[0].replace("\\", "/")).name.lower() not in {
        "python",
        "python.exe",
        "python3",
        "python3.exe",
        "py",
        "py.exe",
    }:
        return {"identified": False, "valid": False, "targets": []}
    if len(tokens) >= 3 and tokens[1] == "-c":
        return _python_source_pb_verifier_invocation(tokens[2])
    return {"identified": False, "valid": False, "targets": []}


def _python_source_invokes_pb_verifier(source: str) -> bool:
    return bool(_python_source_pb_verifier_invocation(source)["valid"])


def _python_source_pb_verifier_invocation(source: str) -> Dict[str, Any]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"identified": False, "valid": False, "targets": []}
    module_name = "src.skills.pb_to_csharp_migration"
    imported_names: Dict[str, str] = {}
    imported_modules: Set[str] = set()
    for statement in tree.body:
        if isinstance(statement, ast.ImportFrom):
            if statement.module == module_name and statement.level == 0:
                for alias in statement.names:
                    if alias.name in _PB_MIGRATION_VERIFIERS:
                        imported_names[alias.asname or alias.name] = alias.name
            continue
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name == module_name and alias.asname:
                    imported_modules.add(alias.asname)
            continue

        call = _top_level_python_call(statement)
        verifier_name = (
            _imported_pb_verifier_name(
                call,
                imported_names=imported_names,
                imported_modules=imported_modules,
            )
            if call is not None
            else ""
        )
        if call is not None and verifier_name:
            return _pb_python_call_invocation(call, verifier_name)

        rebound = _python_statement_bound_names(statement)
        for rebound_name in rebound:
            imported_names.pop(rebound_name, None)
        imported_modules.difference_update(rebound)
    return {"identified": False, "valid": False, "targets": []}


def _top_level_python_call(statement: ast.stmt) -> ast.Call | None:
    value: ast.AST | None = None
    if isinstance(statement, ast.Expr):
        value = statement.value
    elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
        value = statement.value
    return value if isinstance(value, ast.Call) else None


def _is_imported_pb_verifier_call(
    call: ast.Call,
    *,
    imported_names: Mapping[str, str] | Set[str],
    imported_modules: Set[str],
) -> bool:
    normalized_names = (
        dict(imported_names)
        if isinstance(imported_names, Mapping)
        else {name: name for name in imported_names}
    )
    return bool(
        _imported_pb_verifier_name(
            call,
            imported_names=normalized_names,
            imported_modules=imported_modules,
        )
    )


def _imported_pb_verifier_name(
    call: ast.Call,
    *,
    imported_names: Mapping[str, str],
    imported_modules: Set[str],
) -> str:
    if isinstance(call.func, ast.Name):
        return str(imported_names.get(call.func.id, ""))
    if not (
        isinstance(call.func, ast.Attribute)
        and call.func.attr in _PB_MIGRATION_VERIFIERS
    ):
        return ""
    root = call.func.value
    while isinstance(root, ast.Attribute):
        root = root.value
    return call.func.attr if isinstance(root, ast.Name) and root.id in imported_modules else ""


def _python_statement_bound_names(statement: ast.stmt) -> Set[str]:
    return {
        node.id
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    } | {
        node.name
        for node in ast.walk(statement)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _pb_python_call_invocation(call: ast.Call, verifier_name: str) -> Dict[str, Any]:
    if any(isinstance(argument, ast.Starred) for argument in call.args):
        return {
            "identified": True,
            "valid": False,
            "verifier_name": verifier_name,
            "targets": [],
            "reason": "starred_verifier_arguments_are_not_auditable",
        }
    if any(keyword.arg is None for keyword in call.keywords):
        return {
            "identified": True,
            "valid": False,
            "verifier_name": verifier_name,
            "targets": [],
            "reason": "expanded_verifier_keyword_arguments_are_not_auditable",
        }
    literal_arguments: Dict[str, Any] = {}
    for keyword in call.keywords:
        try:
            literal_arguments[str(keyword.arg)] = ast.literal_eval(keyword.value)
        except (ValueError, TypeError):
            literal_arguments[str(keyword.arg)] = None
    return _pb_validate_verifier_invocation_shape(
        verifier_name,
        argument_names={str(keyword.arg) for keyword in call.keywords},
        positional_count=len(call.args),
        literal_arguments=literal_arguments,
    )


def _pb_validate_verifier_invocation_shape(
    verifier_name: str,
    *,
    argument_names: Set[str],
    positional_count: int,
    literal_arguments: Mapping[str, Any],
) -> Dict[str, Any]:
    reason = ""
    if verifier_name == "orchestrate_pb_migration_validation":
        missing = sorted(_PB_ORCHESTRATE_REQUIRED_KEYWORDS - argument_names)
        if positional_count:
            reason = "orchestrate_requires_keyword_only_arguments"
        elif missing:
            reason = "orchestrate_missing_required_keywords:" + ",".join(missing)
    elif verifier_name == "verify_migration_generated_csharp_style":
        source_count = positional_count + int("source_text" in argument_names)
        if positional_count > 1 or source_count != 1:
            reason = "csharp_verifier_requires_exactly_one_source_text_argument"

    artifact_bindings: Dict[str, Dict[str, str]] = {}
    for role in ("source", "designer"):
        path_value = literal_arguments.get(f"target_{role}_path")
        digest_value = literal_arguments.get(f"target_{role}_sha256")
        normalized_path = _normalize_pb_target_path(str(path_value or ""))
        normalized_digest = _pb_normalized_sha256(digest_value)
        if normalized_path or normalized_digest:
            artifact_bindings[role] = {
                "path": normalized_path,
                "sha256": normalized_digest,
            }
            if not normalized_path or not normalized_digest:
                reason = reason or f"target_{role}_artifact_binding_incomplete"

    required_roles = (
        {"source", "designer"}
        if verifier_name == "orchestrate_pb_migration_validation"
        else set()
    )
    if verifier_name == "verify_migration_generated_csharp_style" and not artifact_bindings:
        reason = reason or "csharp_verifier_target_artifact_binding_required"
    missing_roles = sorted(required_roles - set(artifact_bindings))
    if missing_roles:
        reason = reason or "orchestrate_missing_target_artifacts:" + ",".join(missing_roles)

    return {
        "identified": True,
        "valid": not reason,
        "verifier_name": verifier_name,
        "argument_names": sorted(argument_names),
        "positional_count": positional_count,
        "artifact_bindings": artifact_bindings,
        "completion_claims": (
            dict(literal_arguments.get("completion_claims") or {})
            if isinstance(literal_arguments.get("completion_claims"), Mapping)
            else {}
        ),
        "targets": sorted(
            binding["path"] for binding in artifact_bindings.values() if binding["path"]
        ),
        "reason": reason,
    }


def _pb_normalized_sha256(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized.startswith("sha256:"):
        normalized = normalized[7:]
    return normalized if re.fullmatch(r"[0-9a-f]{64}", normalized) else ""


def _pb_verifier_receipt_evidence(
    receipt: CorrelatedToolReceipt,
    *,
    invocation: Mapping[str, Any],
    written_targets: Set[str],
    session_cwd: str,
) -> Dict[str, Any]:
    reasons: List[str] = []
    data = receipt.data if isinstance(receipt.data, Mapping) else {}
    receipt_view = data.get("pb_migration_verifier_receipt", data)
    if not isinstance(receipt_view, Mapping):
        receipt_view = {}
    result = receipt_view.get("result", receipt_view)
    if not isinstance(result, Mapping):
        result = {}
    metadata = result.get("metadata", receipt_view.get("metadata", {}))
    if not isinstance(metadata, Mapping):
        metadata = {}

    verifier_names = {
        str(value).strip()
        for value in (
            receipt_view.get("verifier_name"),
            receipt_view.get("verifier"),
            result.get("verifier_name"),
            metadata.get("verifier_name"),
        )
        if str(value or "").strip()
    }
    verifier_name = next(iter(verifier_names), "") if len(verifier_names) == 1 else ""
    expected_verifier = str(invocation.get("verifier_name") or "")
    if len(verifier_names) > 1:
        reasons.append("conflicting_verifier_names")
    if verifier_name != expected_verifier:
        reasons.append("verifier_name_mismatch")

    success = result.get("success", receipt_view.get("success"))
    exit_code = result.get("exit_code", receipt_view.get("exit_code"))
    if type(success) is not bool:
        reasons.append("boolean_success_required")
    if type(exit_code) is not int:
        reasons.append("integer_exit_code_required")

    contract = metadata.get("validation_contract", receipt_view.get("validation_contract", {}))
    if not isinstance(contract, Mapping):
        contract = {}
    completion_values: List[bool] = []
    for control in (receipt_view, result, metadata, contract):
        if "completion_allowed" in control:
            value = control.get("completion_allowed")
            if type(value) is bool:
                completion_values.append(value)
            else:
                reasons.append("boolean_completion_allowed_required")
    completion_allowed: Any = completion_values[0] if completion_values else None
    if len(set(completion_values)) > 1:
        reasons.append("conflicting_completion_allowed_values")
    if expected_verifier == "orchestrate_pb_migration_validation":
        if type(completion_allowed) is not bool:
            if "boolean_completion_allowed_required" not in reasons:
                reasons.append("boolean_completion_allowed_required")
    elif completion_values and completion_allowed is not False:
        reasons.append("csharp_verifier_cannot_claim_migration_completion")
    else:
        completion_allowed = False

    output_text = _payload_text(receipt.output)
    output_exit_codes = [
        int(match.group(1))
        for match in re.finditer(r"(?im)^\s*exit\s+code\s*:\s*(-?\d+)\s*$", output_text)
    ]
    if type(exit_code) is int and any(code != exit_code for code in output_exit_codes):
        reasons.append("tool_output_exit_code_mismatch")
    explicit_failure_text = "\n".join(
        str(value or "")
        for value in (
            result.get("stderr"),
            receipt_view.get("stderr"),
            metadata.get("error"),
        )
        if str(value or "").strip()
    )
    if success is True and re.search(
        r"(?i)\bvalidation\s+failed\b|\berror\b",
        explicit_failure_text,
    ):
        reasons.append("successful_receipt_contains_failure_output")

    status = str(
        metadata.get("status")
        or result.get("status")
        or receipt_view.get("status")
        or ""
    ).strip().lower()
    valid_statuses = {"passed", "success", "succeeded", "ok"}
    if expected_verifier == "orchestrate_pb_migration_validation":
        valid_statuses.add("draft_validated")
    if success is False:
        if status != "blocked":
            reasons.append("failed_verifier_status_not_blocked")
    elif status not in valid_statuses:
        reasons.append("verifier_status_not_success_or_draft_validated")

    stage_statuses = _pb_receipt_stage_statuses(receipt_view, result, metadata, contract)
    if not stage_statuses:
        reasons.append("stage_status_required")
    if expected_verifier == "orchestrate_pb_migration_validation":
        reasons.extend(
            _pb_orchestrated_contract_errors(
                contract,
                stage_statuses=stage_statuses,
                completion_allowed=completion_allowed,
                metadata=metadata,
                success=success,
                exit_code=exit_code,
                status=status,
            )
        )
    elif "csharp" not in stage_statuses:
        reasons.append("csharp_stage_status_required")

    profile_records = _pb_profile_consumption_records(receipt_view, result, metadata)
    profile_valid = any(_pb_packaged_profile_record_valid(item) for item in profile_records)
    if not profile_valid:
        reasons.append("packaged_fixed_profile_receipt_invalid")

    artifact_results = _pb_validate_output_artifact_bindings(
        receipt_view,
        result,
        metadata,
        invocation=invocation,
        written_targets=written_targets,
        session_cwd=session_cwd,
    )
    reasons.extend(artifact_results["errors"])

    core_validation_passed = bool(
        contract.get("core_validation_passed") is True
        if expected_verifier == "orchestrate_pb_migration_validation"
        else success is True and exit_code == 0
    )
    completion_requested = bool(
        contract.get("completion_requested") is True
        if expected_verifier == "orchestrate_pb_migration_validation"
        else False
    )
    completion_claims = (
        dict(contract.get("completion_claims") or {})
        if isinstance(contract.get("completion_claims"), Mapping)
        else {}
    )
    invocation_completion_claims = invocation.get("completion_claims")
    if expected_verifier == "orchestrate_pb_migration_validation" and (
        not isinstance(invocation_completion_claims, Mapping)
        or dict(invocation_completion_claims) != completion_claims
    ):
        reasons.append("completion_claims_invocation_receipt_mismatch")
    receipt_valid = not reasons
    satisfied_outputs: List[str] = []
    if receipt_valid and profile_valid:
        satisfied_outputs.append("packaged_profile")
    if receipt_valid and stage_statuses.get("csharp") == "passed" and artifact_results["source_valid"]:
        satisfied_outputs.append("csharp_verification")
    if receipt_valid and (
        stage_statuses.get("designer") == "passed"
        or stage_statuses.get("csharp") == "passed"
    ) and artifact_results["designer_valid"]:
        satisfied_outputs.append("designer_verification")
    if receipt_valid and stage_statuses.get("sp") == "passed" and _pb_domain_profile_consumed(
        metadata,
        "sp",
    ):
        satisfied_outputs.append("sp_verification")
    if receipt_valid and stage_statuses.get("sql_binding_release") == "passed" and _pb_sql_release_receipt_valid(metadata):
        satisfied_outputs.append("sql_binding_release")

    return {
        "verifier_name": expected_verifier,
        "receipt_valid": receipt_valid,
        "claim_status": "observed" if receipt_valid else "claimed_unverified",
        "completion_allowed": completion_allowed is True,
        "completion_requested": completion_requested,
        "completion_claims": completion_claims,
        "core_validation_passed": core_validation_passed,
        "draft_validated": bool(receipt_valid and core_validation_passed and not completion_requested),
        "designer_applicable": bool(
            invocation.get("artifact_bindings", {}).get("designer")
            if isinstance(invocation.get("artifact_bindings"), Mapping)
            else False
        ),
        "stage_statuses": stage_statuses,
        "profile_valid": profile_valid,
        "verified_targets": artifact_results["verified_targets"],
        "satisfied_outputs": satisfied_outputs,
        "errors": reasons,
    }


def _pb_receipt_stage_statuses(
    receipt_view: Mapping[str, Any],
    result: Mapping[str, Any],
    metadata: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> Dict[str, str]:
    statuses: Dict[str, str] = {}

    def consume(value: Any) -> None:
        if isinstance(value, Mapping):
            for raw_name, raw_status in value.items():
                if isinstance(raw_status, Mapping):
                    raw_status = raw_status.get("status")
                name = _pb_normalized_stage_name(raw_name)
                status = str(raw_status or "").strip().lower()
                if name and status:
                    statuses[name] = status
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                if not isinstance(item, Mapping):
                    continue
                name = _pb_normalized_stage_name(item.get("name") or item.get("stage"))
                status = str(item.get("status") or "").strip().lower()
                if name and status:
                    statuses[name] = status

    for control in (contract, metadata, result, receipt_view):
        consume(control.get("stages"))
        consume(control.get("stage_statuses"))
        consume(control.get("stage_status"))
        if control.get("stage"):
            consume({control.get("stage"): control.get("status")})
    return statuses


def _pb_normalized_stage_name(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("_", "-")
    aliases = {
        "load-profile": "packaged_profile",
        "profile": "packaged_profile",
        "packaged-profile": "packaged_profile",
        "validate-csharp": "csharp",
        "csharp": "csharp",
        "designer": "designer",
        "validate-designer": "designer",
        "validate-sp": "sp",
        "sp": "sp",
        "stored-procedure": "sp",
        "final-sql-binding": "sql_binding_release",
        "sql-binding-release": "sql_binding_release",
        "sql-release-binding": "sql_binding_release",
        "build": "build",
        "database": "database",
        "db": "database",
        "manual-qa": "manual_qa",
        "manual": "manual_qa",
    }
    return aliases.get(normalized, "")


def _pb_orchestrated_contract_errors(
    contract: Mapping[str, Any],
    *,
    stage_statuses: Mapping[str, str],
    completion_allowed: Any,
    metadata: Mapping[str, Any],
    success: Any,
    exit_code: Any,
    status: str,
) -> List[str]:
    errors: List[str] = []
    required_order = ["load-profile", "validate-csharp", "validate-sp", "final-sql-binding"]
    if list(contract.get("required_stage_order") or []) != required_order:
        errors.append("orchestrate_required_stage_order_mismatch")
    stages = contract.get("stages")
    contract_stages = (
        [item for item in stages if isinstance(item, Mapping)]
        if isinstance(stages, Sequence) and not isinstance(stages, (str, bytes))
        else []
    )
    stage_names = [str(item.get("name") or "") for item in contract_stages]
    for item in contract_stages:
        normalized_name = _pb_normalized_stage_name(item.get("name"))
        contract_status = str(item.get("status") or "").strip().lower()
        if normalized_name and stage_statuses.get(normalized_name) != contract_status:
            errors.append(f"conflicting_stage_status:{normalized_name}")
    completed_order = list(contract.get("completed_stage_order") or [])
    if not stage_names or completed_order != stage_names:
        errors.append("orchestrate_completed_stage_order_mismatch")
    if completed_order != required_order[: len(completed_order)]:
        errors.append("orchestrate_stage_order_is_not_a_required_prefix")
    all_offline_stages_passed = bool(
        completed_order == required_order
        and all(
            stage_statuses.get(name) == "passed"
            for name in ("packaged_profile", "csharp", "sp", "sql_binding_release")
        )
        and contract.get("profile_identity_match") is True
        and contract.get("sql_release_correlated") is True
    )
    core_validation_passed = contract.get("core_validation_passed")
    completion_requested = contract.get("completion_requested")
    offline_draft_allowed = contract.get("offline_draft_allowed")
    if type(core_validation_passed) is not bool:
        errors.append("orchestrate_core_validation_passed_boolean_required")
    elif core_validation_passed is not all_offline_stages_passed:
        errors.append("orchestrate_core_validation_stage_mismatch")
    if type(completion_requested) is not bool:
        errors.append("orchestrate_completion_requested_boolean_required")
    if type(offline_draft_allowed) is not bool:
        errors.append("orchestrate_offline_draft_allowed_boolean_required")
    elif type(core_validation_passed) is bool and type(completion_requested) is bool:
        if offline_draft_allowed is not (core_validation_passed and not completion_requested):
            errors.append("orchestrate_offline_draft_allowed_mismatch")

    completion_claims = contract.get("completion_claims")
    if not isinstance(completion_claims, Mapping):
        errors.append("orchestrate_completion_claims_mapping_required")
        completion_claims = {}
    expected_completion_requested = bool(
        completion_claims.get("completion") is True
        or completion_claims.get("release") is True
        or completion_claims.get("implementation_complete") is True
    )
    if type(completion_requested) is bool and completion_requested is not expected_completion_requested:
        errors.append("orchestrate_completion_requested_claim_mismatch")

    completion_stages = contract.get("completion_stages")
    stage_rows = (
        [item for item in completion_stages if isinstance(item, Mapping)]
        if isinstance(completion_stages, Sequence) and not isinstance(completion_stages, (str, bytes))
        else []
    )
    expected_completion_stage_names = [
        "project-inclusion",
        "project-build",
        "designer-layout-load",
        "database-equivalence",
        "deployment",
        "manual-workflow",
    ]
    if [str(item.get("name") or "") for item in stage_rows] != expected_completion_stage_names:
        errors.append("orchestrate_completion_stage_contract_mismatch")
    for item in stage_rows:
        if type(item.get("required_for_claim")) is not bool:
            errors.append(f"completion_stage_required_flag_invalid:{item.get('name', '')}")
        if str(item.get("status") or "") not in {"passed", "blocked", "not_claimed"}:
            errors.append(f"completion_stage_status_invalid:{item.get('name', '')}")
        if not isinstance(item.get("evidence"), Mapping):
            errors.append(f"completion_stage_evidence_mapping_required:{item.get('name', '')}")
    required_completion_stages = [
        item for item in stage_rows if item.get("required_for_claim") is True
    ]
    expected_completion_allowed = bool(
        all_offline_stages_passed
        and required_completion_stages
        and all(item.get("status") == "passed" for item in required_completion_stages)
    )
    if type(completion_allowed) is bool and completion_allowed is not expected_completion_allowed:
        errors.append("orchestrate_completion_allowed_stage_mismatch")

    expected_success = bool(
        expected_completion_allowed
        if completion_requested is True
        else all_offline_stages_passed
    )
    if type(success) is bool and success is not expected_success:
        errors.append("orchestrate_success_contract_mismatch")
    if type(exit_code) is int and (exit_code == 0) is not expected_success:
        errors.append("orchestrate_exit_code_contract_mismatch")
    expected_status = (
        "passed"
        if expected_completion_allowed
        else "draft_validated"
        if all_offline_stages_passed and completion_requested is False
        else "blocked"
    )
    if status != expected_status:
        errors.append("orchestrate_status_contract_mismatch")
    if stage_statuses.get("sql_binding_release") == "passed" and not _pb_sql_release_receipt_valid(metadata):
        errors.append("sql_release_binding_receipt_invalid")
    return errors


def _pb_profile_consumption_records(
    receipt_view: Mapping[str, Any],
    result: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> List[Mapping[str, Any]]:
    records: List[Mapping[str, Any]] = []

    def append(value: Any) -> None:
        if not isinstance(value, Mapping):
            return
        nested = value.get("profile_consumption")
        if isinstance(nested, Mapping):
            records.append(nested)
        if any(key in value for key in ("profile_id", "profile_version", "profile_hash")):
            records.append(value)

    for control in (receipt_view, result, metadata):
        append(control.get("packaged_profile"))
        append(control.get("profile_consumption"))
    evidence = metadata.get("evidence")
    if isinstance(evidence, Mapping):
        append(evidence.get("profile"))
        append(evidence.get("csharp"))
        append(evidence.get("sp"))
    return records


def _pb_packaged_profile_identity() -> Dict[str, str]:
    try:
        raw_bytes = _PB_PACKAGED_PROFILE_PATH.read_bytes()
        data = load_json_without_duplicate_keys(raw_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJsonKeyError):
        return {}
    if not isinstance(data, Mapping):
        return {}
    profile_id = str(data.get("contract_id") or "").strip()
    profile_version = str(data.get("contract_version") or "").strip()
    if not profile_id or not profile_version:
        return {}
    return {
        "profile_id": profile_id,
        "profile_version": profile_version,
        "profile_hash": hashlib.sha256(raw_bytes).hexdigest(),
    }


def _pb_packaged_profile_record_valid(record: Mapping[str, Any]) -> bool:
    identity = _pb_packaged_profile_identity()
    if not identity:
        return False
    source = str(record.get("source") or record.get("profile_source") or "").strip().lower()
    profile_hash = _pb_normalized_sha256(record.get("profile_hash"))
    return bool(
        source == "packaged_sanitized_profile"
        and record.get("consumed") is True
        and record.get("sanitized") is True
        and record.get("profile_hash_verified") is True
        and str(record.get("profile_id") or "").strip() == identity["profile_id"]
        and str(record.get("profile_version") or record.get("version") or "").strip()
        == identity["profile_version"]
        and profile_hash == identity["profile_hash"]
    )


def _pb_domain_profile_consumed(metadata: Mapping[str, Any], domain: str) -> bool:
    evidence = metadata.get("evidence")
    if not isinstance(evidence, Mapping):
        return False
    domain_evidence = evidence.get(domain)
    if not isinstance(domain_evidence, Mapping):
        return False
    record = domain_evidence.get("profile_consumption")
    return isinstance(record, Mapping) and _pb_packaged_profile_record_valid(record)


def _pb_sql_release_receipt_valid(metadata: Mapping[str, Any]) -> bool:
    evidence = metadata.get("evidence")
    if not isinstance(evidence, Mapping):
        return False
    binding = evidence.get("sql_final_response_binding")
    release = evidence.get("sql_final_response_release")
    history = evidence.get("sql_verifier_history")
    correlation = evidence.get("sql_verifier_history_correlation")
    if not (
        isinstance(binding, Mapping)
        and binding.get("status") == "bound"
        and isinstance(release, Mapping)
        and release.get("status") == "passed"
        and release.get("binding") == binding
        and isinstance(history, Sequence)
        and not isinstance(history, (str, bytes))
        and history
        and all(isinstance(item, Mapping) for item in history)
        and release.get("verifier_history") == list(history)
        and isinstance(correlation, Mapping)
        and release.get("verifier_history_correlation") == correlation
    ):
        return False

    latest = history[-1]
    latest_metadata = latest.get("metadata")
    release_verification = release.get("verification")
    release_verification_metadata = (
        release_verification.get("metadata")
        if isinstance(release_verification, Mapping)
        else None
    )
    if not (
        latest.get("success") is True
        and type(latest.get("exit_code")) is int
        and latest.get("exit_code") == 0
        and isinstance(latest_metadata, Mapping)
        and isinstance(release_verification, Mapping)
        and release_verification.get("success") is True
        and type(release_verification.get("exit_code")) is int
        and release_verification.get("exit_code") == 0
        and isinstance(release_verification_metadata, Mapping)
    ):
        return False

    verification_id = str(latest_metadata.get("verification_id") or "").strip()
    original_sha256 = _pb_normalized_sha256(latest_metadata.get("original_sha256"))
    formatted_sha256 = _pb_normalized_sha256(latest_metadata.get("formatted_sha256"))
    if not (verification_id and original_sha256 and formatted_sha256):
        return False
    if any(
        str(release_verification_metadata.get(key) or "").strip().lower()
        != str(value).strip().lower()
        for key, value in {
            "verification_id": verification_id,
            "original_sha256": original_sha256,
            "formatted_sha256": formatted_sha256,
        }.items()
    ):
        return False
    if not (
        str(binding.get("verification_id") or "").strip() == verification_id
        and _pb_normalized_sha256(binding.get("original_sha256")) == original_sha256
        and _pb_normalized_sha256(binding.get("formatted_sha256")) == formatted_sha256
        and _pb_normalized_sha256(binding.get("final_response_sha256"))
        and binding.get("sql_fence_count") == 1
        and correlation.get("status") == "correlated"
        and correlation.get("attempt_count") == len(history)
        and str(correlation.get("binding_verification_id") or "").strip() == verification_id
        and str(correlation.get("history_verification_id") or "").strip() == verification_id
        and _pb_normalized_sha256(correlation.get("original_sha256")) == original_sha256
        and _pb_normalized_sha256(correlation.get("formatted_sha256")) == formatted_sha256
    ):
        return False
    provider_guard = release.get("provider_path_guard")
    return bool(
        isinstance(provider_guard, Mapping)
        and provider_guard.get("status") in {"accepted", "passed", "verified", "bound"}
        and str(provider_guard.get("provider_path") or "").strip()
        and provider_guard.get("provider_path")
        == provider_guard.get("selected_active_provider_path")
    )


def _pb_validate_output_artifact_bindings(
    receipt_view: Mapping[str, Any],
    result: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    invocation: Mapping[str, Any],
    written_targets: Set[str],
    session_cwd: str,
) -> Dict[str, Any]:
    errors: List[str] = []
    output_bindings = _pb_output_artifact_bindings(receipt_view, result, metadata)
    invocation_bindings = invocation.get("artifact_bindings")
    invocation_bindings = invocation_bindings if isinstance(invocation_bindings, Mapping) else {}
    verified_targets: Set[str] = set()
    valid_roles: Set[str] = set()

    for role, invocation_binding in invocation_bindings.items():
        if not isinstance(invocation_binding, Mapping):
            continue
        expected_path = str(invocation_binding.get("path") or "")
        expected_digest = _pb_normalized_sha256(invocation_binding.get("sha256"))
        matching_outputs = [
            item
            for item in output_bindings
            if item["role"] == role
            and _pb_target_paths_match(
                expected_path,
                item["path"],
                session_cwd=session_cwd,
            )
        ]
        if not matching_outputs:
            errors.append(f"{role}_artifact_receipt_missing")
            continue
        if len(matching_outputs) != 1:
            errors.append(f"{role}_artifact_receipt_ambiguous")
            continue
        matching_output = matching_outputs[0]
        actual_path = _pb_artifact_filesystem_path(matching_output["path"], session_cwd)
        try:
            raw_bytes = actual_path.read_bytes()
        except OSError:
            errors.append(f"{role}_artifact_unreadable")
            continue
        recalculated = hashlib.sha256(raw_bytes).hexdigest()
        receipt_digest = _pb_normalized_sha256(matching_output.get("sha256"))
        expected_receipt_digest = _pb_normalized_sha256(
            matching_output.get("expected_sha256")
        )
        if (
            matching_output.get("status") != "passed"
            or not expected_digest
            or expected_digest != recalculated
            or receipt_digest != recalculated
            or (expected_receipt_digest and expected_receipt_digest != recalculated)
        ):
            errors.append(f"{role}_artifact_sha256_mismatch")
            continue
        if matching_output.get("readback_matches_supplied_text") is not True:
            errors.append(f"{role}_artifact_readback_not_verified")
            continue
        normalized = _normalize_pb_target_path(str(actual_path.resolve()))
        verified_targets.add(normalized)
        valid_roles.add(str(role))

    if not invocation_bindings:
        errors.append("target_artifact_invocation_binding_required")
    if written_targets and not _pb_targets_cover(
        written_targets,
        verified_targets,
        session_cwd=session_cwd,
    ):
        errors.append("verified_artifacts_do_not_cover_written_targets")
    return {
        "errors": errors,
        "verified_targets": sorted(verified_targets),
        "source_valid": "source" in valid_roles,
        "designer_valid": "designer" in valid_roles,
    }


def _pb_output_artifact_bindings(
    receipt_view: Mapping[str, Any],
    result: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    bindings: List[Dict[str, Any]] = []

    def append(role: str, value: Any) -> None:
        if not isinstance(value, Mapping):
            return
        path = str(value.get("path") or value.get("target_path") or value.get("artifact_path") or "")
        if not _normalize_pb_target_path(path):
            return
        bindings.append(
            {
                "role": str(value.get("role") or role or _pb_artifact_role(path)).strip().lower(),
                "status": str(value.get("status") or "").strip().lower(),
                "path": path,
                "sha256": value.get("actual_sha256") or value.get("artifact_sha256") or value.get("sha256"),
                "expected_sha256": value.get("expected_sha256"),
                "readback_matches_supplied_text": value.get("readback_matches_supplied_text"),
            }
        )

    def consume(value: Any) -> None:
        if isinstance(value, Mapping):
            for role in ("source", "designer"):
                append(role, value.get(role))
            append(str(value.get("role") or ""), value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                append("", item)

    for control in (receipt_view, result, metadata):
        consume(control.get("target_artifact_binding"))
        consume(control.get("target_artifacts"))
    evidence = metadata.get("evidence")
    if isinstance(evidence, Mapping):
        csharp = evidence.get("csharp")
        if isinstance(csharp, Mapping):
            consume(csharp.get("target_artifact_binding"))
    return bindings


def _pb_artifact_filesystem_path(value: str, session_cwd: str) -> Path:
    path = Path(str(value or ""))
    if path.is_absolute():
        return path
    return Path(session_cwd) / path


def _pb_artifact_role(path: str) -> str:
    return "designer" if _normalize_pb_target_path(path).endswith(".designer.cs") else "source"


def _pb_independent_stage_receipt(
    receipt: CorrelatedToolReceipt,
    *,
    session_cwd: str,
    written_targets: Set[str],
) -> Dict[str, Any] | None:
    call_name = str(receipt.call.get("name") or "").strip().lower().replace("-", "_")
    record = SessionTextRecord(
        text=_payload_text(receipt.call),
        payload_type=str(receipt.call.get("type", "")),
        name=str(receipt.call.get("name", "")),
        arguments=_payload_arguments_text(receipt.call),
    )
    command = _exact_shell_command_text(record)
    host_result = _pb_host_command_result(receipt)
    if command and host_result is not None and _pb_trusted_shell_tool_name(call_name):
        project_target = _pb_command_project_target(command, session_cwd)
        if _pb_is_project_inclusion_command(command) and project_target is not None:
            output_text = host_result["output"]
            if _pb_project_inclusion_output_covers_targets(output_text, written_targets):
                return _pb_command_stage_evidence(
                    "project_inclusion_verification",
                    receipt,
                    command=command,
                    target_path=project_target,
                    output_text=output_text,
                )
        if _pb_is_build_command(command) and project_target is not None:
            return {
                "output": "build_verification",
                "call_id": _payload_call_id(receipt.call),
                "status": "passed",
                **_pb_command_stage_evidence_fields(
                    command=command,
                    target_path=project_target,
                    output_text=host_result["output"],
                ),
            }
        deployment_object = _pb_deployment_target_object(command)
        if deployment_object and _pb_is_database_verification_command(command):
            return {
                "output": "deployment_verification",
                "call_id": _payload_call_id(receipt.call),
                "status": "passed",
                "target_database_object": deployment_object,
                "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
                "output_sha256": hashlib.sha256(host_result["output"].encode("utf-8")).hexdigest(),
            }
        database_object = _pb_database_target_object(command)
        if database_object and _pb_is_database_verification_command(command):
            return {
                "output": "database_verification",
                "call_id": _payload_call_id(receipt.call),
                "status": "passed",
                "target_database_object": database_object,
                "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
                "output_sha256": hashlib.sha256(host_result["output"].encode("utf-8")).hexdigest(),
            }

    return _pb_gui_stage_receipt(
        receipt,
        call_name=call_name,
        session_cwd=session_cwd,
        written_targets=written_targets,
    )


def _pb_trusted_shell_tool_name(call_name: str) -> bool:
    return call_name in {"exec_command", "shell_command", "run_command"} or call_name.endswith(
        ("__exec_command", "__shell_command", "__run_command")
    )


def _pb_host_command_result(receipt: CorrelatedToolReceipt) -> Dict[str, Any] | None:
    data = receipt.data if isinstance(receipt.data, Mapping) else {}
    exit_code = data.get("exit_code")
    if type(exit_code) is not int or exit_code != 0:
        return None
    output = data.get("output", data.get("stdout"))
    if not isinstance(output, str) or not output.strip():
        return None
    if not _runtime_tool_output_succeeded(receipt.output):
        return None
    return {"exit_code": exit_code, "output": output}


def _pb_command_project_target(command: str, session_cwd: str) -> Path | None:
    try:
        tokens = [_strip_shell_token_quotes(item) for item in shlex.split(command, posix=False)]
    except ValueError:
        return None
    for token in tokens[1:]:
        if token.startswith("-") or token.startswith("/") and not re.match(r"^[a-zA-Z]:[/\\]", token):
            continue
        if not token.lower().endswith((".sln", ".slnx", ".csproj")):
            continue
        candidate = Path(token)
        if not candidate.is_absolute():
            candidate = Path(session_cwd) / candidate
        try:
            candidate = candidate.resolve()
        except OSError:
            return None
        return candidate if candidate.is_file() else None
    return None


def _pb_is_project_inclusion_command(command: str) -> bool:
    if not command or _contains_unquoted_shell_control(command):
        return False
    lowered = command.lower()
    return bool(
        re.search(r"(?i)(?:^|\s)dotnet(?:\.exe)?\s+msbuild\b", command)
        and re.search(r"(?i)(?:-|/)getitem:compile\b", lowered)
    )


def _pb_project_inclusion_output_covers_targets(
    output_text: str,
    written_targets: Set[str],
) -> bool:
    lowered = output_text.replace("\\", "/").casefold()
    required = [
        Path(target).name.casefold()
        for target in written_targets
        if str(target).lower().endswith((".cs", ".designer.cs"))
    ]
    return bool(required) and all(name in lowered for name in required)


def _pb_command_stage_evidence(
    output: str,
    receipt: CorrelatedToolReceipt,
    *,
    command: str,
    target_path: Path,
    output_text: str,
) -> Dict[str, Any]:
    return {
        "output": output,
        "call_id": _payload_call_id(receipt.call),
        "status": "passed",
        **_pb_command_stage_evidence_fields(
            command=command,
            target_path=target_path,
            output_text=output_text,
        ),
    }


def _pb_command_stage_evidence_fields(
    *,
    command: str,
    target_path: Path,
    output_text: str,
) -> Dict[str, Any]:
    raw_bytes = target_path.read_bytes()
    return {
        "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
        "target_path": str(target_path),
        "target_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "output_sha256": hashlib.sha256(output_text.encode("utf-8")).hexdigest(),
    }


def _pb_database_target_object(command: str) -> str:
    patterns = [
        r"(?i)object_id\s*\(\s*N?'([^']+)'",
        r"(?i)\bexec(?:ute)?\s+(?:N?'[^']+'\s*,\s*)?\[?([a-z0-9_]+)\]?\.\[?([a-z0-9_]+)\]?",
    ]
    for pattern in patterns:
        match = re.search(pattern, command)
        if match:
            return ".".join(group for group in match.groups() if group)
    return ""


def _pb_deployment_target_object(command: str) -> str:
    match = re.search(
        r"(?i)\b(?:create\s+(?:or\s+alter\s+)?|alter\s+)procedure\s+"
        r"(?:\[?([a-z0-9_]+)\]?\.)?\[?([a-z0-9_]+)\]?",
        command,
    )
    return ".".join(group for group in match.groups() if group) if match else ""


def _pb_gui_stage_receipt(
    receipt: CorrelatedToolReceipt,
    *,
    call_name: str,
    session_cwd: str,
    written_targets: Set[str],
) -> Dict[str, Any] | None:
    trusted = call_name in {
        "view_image",
        "computer_use",
        "control_in_app_browser",
        "control_chrome",
        "screenshot",
    } or call_name.endswith(
        ("__view_image", "__computer_use", "__control_in_app_browser", "__control_chrome", "__screenshot")
    )
    if not trusted or not _runtime_tool_output_succeeded(receipt.output):
        return None
    arguments = _pb_payload_argument_mapping(receipt.call)
    if not isinstance(arguments, Mapping):
        return None
    stage = _pb_normalized_completion_stage(arguments.get("stage") or arguments.get("evidence_type"))
    if stage not in {"designer_layout_verification", "manual_qa"}:
        return None
    evidence_path = str(
        arguments.get("evidence_path")
        or arguments.get("screenshot_path")
        or arguments.get("path")
        or ""
    ).strip()
    expected_digest = _pb_normalized_sha256(arguments.get("evidence_sha256"))
    candidate = Path(evidence_path)
    if not candidate.is_absolute():
        candidate = Path(session_cwd) / candidate
    try:
        candidate = candidate.resolve()
        actual_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    except OSError:
        return None
    if not expected_digest or actual_digest != expected_digest:
        return None
    if not _pb_gui_target_bindings_cover(arguments, written_targets, session_cwd):
        return None
    scenarios = arguments.get("scenarios")
    if stage == "manual_qa" and not (
        isinstance(scenarios, Sequence)
        and not isinstance(scenarios, (str, bytes))
        and all(str(item).strip() for item in scenarios)
    ):
        return None
    return {
        "output": stage,
        "call_id": _payload_call_id(receipt.call),
        "status": "passed",
        "tool_identity": call_name,
        "evidence_path": str(candidate),
        "evidence_sha256": actual_digest,
        "scenarios": [str(item) for item in scenarios] if stage == "manual_qa" else [],
    }


def _pb_gui_target_bindings_cover(
    arguments: Mapping[str, Any],
    written_targets: Set[str],
    session_cwd: str,
) -> bool:
    bindings = arguments.get("target_artifacts")
    if not isinstance(bindings, Sequence) or isinstance(bindings, (str, bytes)):
        return False
    verified: Set[str] = set()
    for item in bindings:
        if not isinstance(item, Mapping):
            return False
        raw_path = str(item.get("path") or "").strip()
        expected_digest = _pb_normalized_sha256(item.get("sha256"))
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = Path(session_cwd) / candidate
        try:
            candidate = candidate.resolve()
            actual_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        except OSError:
            return False
        if not expected_digest or actual_digest != expected_digest:
            return False
        verified.add(_normalize_pb_target_path(str(candidate)))
    return _pb_targets_cover(written_targets, verified, session_cwd=session_cwd)


def _pb_normalized_completion_stage(value: Any) -> str:
    normalized = str(value or "").strip().lower().replace("_", "-")
    return {
        "designer-layout-load": "designer_layout_verification",
        "designer-layout": "designer_layout_verification",
        "manual-workflow": "manual_qa",
        "manual-qa": "manual_qa",
    }.get(normalized, "")


def _pb_receipt_reports_success(payload: Mapping[str, Any]) -> bool:
    if not _runtime_tool_output_succeeded(dict(payload)):
        return False
    text = _payload_text(dict(payload))
    data = _json_object_from_text(text)
    explicit_codes: List[int] = []
    for control in (payload, data):
        if not isinstance(control, Mapping):
            continue
        for key in ("exit_code", "return_code", "returncode"):
            if type(control.get(key)) is int:
                explicit_codes.append(int(control[key]))
    explicit_codes.extend(
        int(match.group(1))
        for match in re.finditer(r"(?im)^\s*exit\s+code\s*:\s*(-?\d+)\s*$", text)
    )
    return bool(explicit_codes) and all(code == 0 for code in explicit_codes)


def _pb_is_build_command(command: str) -> bool:
    if not command or _contains_unquoted_shell_control(command):
        return False
    try:
        tokens = [_strip_shell_token_quotes(item) for item in shlex.split(command, posix=False)]
    except ValueError:
        return False
    if not tokens:
        return False
    executable = Path(tokens[0].replace("\\", "/")).name.lower()
    if executable in {"msbuild", "msbuild.exe"}:
        return True
    if executable in {"dotnet", "dotnet.exe"}:
        return len(tokens) > 1 and tokens[1].lower() in {"build", "test"}
    return executable in {"devenv", "devenv.exe"} and any(
        token.lower() in {"/build", "/rebuild"} for token in tokens[1:]
    )


def _pb_is_database_verification_command(command: str) -> bool:
    if not command or _contains_unquoted_shell_control(command):
        return False
    lowered = command.lower()
    if not re.search(r"(?i)\b(?:select|exec(?:ute)?|create\s+(?:or\s+alter\s+)?procedure|alter\s+procedure)\b", command):
        return False
    try:
        tokens = [_strip_shell_token_quotes(item) for item in shlex.split(command, posix=False)]
    except ValueError:
        return False
    executable = Path(tokens[0].replace("\\", "/")).name.lower() if tokens else ""
    return bool(
        executable in {"sqlcmd", "sqlcmd.exe"}
        or re.search(r"(?i)(?<![a-z0-9_-])invoke-sqlcmd\b", lowered)
    )


def _pb_unverified_execution_claims(
    events: Sequence[Dict[str, Any]],
    *,
    after_index: int,
) -> List[Dict[str, Any]]:
    claims: List[Dict[str, Any]] = []
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("PB claim audit requires indexed event facts")
    for index, payload in events.iter_payloads(
        payload_types=("message",),
        roles=("assistant",),
        start=after_index + 1,
    ):
        text = _payload_text(payload)
        if not _pb_text_claims_execution_verified(text):
            continue
        claims.append(
            {
                "event_index": index,
                "status": "claimed_unverified",
                "sample": _short(text),
            }
        )
    return claims


def _pb_text_claims_execution_verified(text: str) -> bool:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    lowered = value.lower()
    if any(
        marker in lowered
        for marker in (
            "verify_migration_generated_csharp_style",
            "orchestrate_pb_migration_validation",
            "completion_allowed",
            "validation passed",
            "manual qa passed",
            "build passed",
        )
    ):
        return True
    english_subject = r"(?:pb|powerbuilder|migration|c#|designer|build|manual\s+qa|database|deployment|verification)"
    english_result = r"(?:is\s+)?(?:complete(?:d)?|passed|verified|succeeded|ready)"
    if re.search(rf"(?i)\b{english_subject}\b.{{0,100}}\b{english_result}\b", value):
        return True
    if re.search(rf"(?i)\b{english_result}\b.{{0,80}}\b{english_subject}\b", value):
        return True

    korean_subject = (
        "(?:PB|PowerBuilder|C#|\ud30c\uc6cc\ube4c\ub354|\ub9c8\uc774\uadf8\ub808\uc774\uc158|"
        "\ub514\uc790\uc774\ub108|\ube4c\ub4dc|\uc218\ub3d9\\s*QA|DB|\ub370\uc774\ud130\ubca0\uc774\uc2a4|"
        "\ubc30\ud3ec|\uac80\uc99d)"
    )
    korean_result = (
        "(?:\uc644\ub8cc(?:\ud588|\ub410|\ub418\uc5c8|\uc785\ub2c8\ub2e4)|"
        "\ud1b5\uacfc(?:\ud588|\ub410|\uc785\ub2c8\ub2e4)|"
        "\uc131\uacf5(?:\ud588|\ub410|\uc785\ub2c8\ub2e4)|"
        "\uac80\uc99d(?:\ud588|\ub410|\ub418\uc5c8|\ub429\ub2c8\ub2e4)|"
        "\ubb38\uc81c\\s*\uc5c6(?:\uc2b5\ub2c8\ub2e4|\uc74c))"
    )
    claim = bool(
        re.search(rf"{korean_subject}.{{0,100}}{korean_result}", value, re.IGNORECASE)
        or re.search(rf"{korean_result}.{{0,80}}{korean_subject}", value, re.IGNORECASE)
    )
    if not claim:
        return False
    discussion_only = re.search(
        "(?:\uc644\ub8cc|\ud1b5\uacfc|\uc131\uacf5|\uac80\uc99d)"
        "(?:\uc600\ub294\uc9c0|\\s*\uc5ec\ubd80|\\s*\uc870\uac74|\\s*\uae30\uc900|\\s*\ud45c\ud604|"
        "\\s*\ubb38\uad6c|\ub77c\uace0\\s*(?:\ud558\uba74|\uc8fc\uc7a5)|\uc774\ub77c\ub294)",
        value,
    )
    return discussion_only is None


def _extract_pb_csharp_write_targets(payload: Dict[str, Any]) -> Set[str]:
    arguments = _payload_arguments_text(payload)
    targets = _extract_patch_csharp_paths(arguments)
    name = str(payload.get("name", "") or "").strip().lower().replace("-", "_")

    if any(marker in name for marker in ["write_file", "edit_file"]):
        targets.update(_extract_structured_write_csharp_paths(payload))

    record = SessionTextRecord(
        text=_payload_text(payload),
        payload_type=str(payload.get("type", "")),
        name=str(payload.get("name", "")),
        arguments=arguments,
    )
    command = _exact_shell_command_text(record)
    if command:
        targets.update(_extract_shell_write_csharp_paths(command))
    return targets


def _extract_patch_csharp_paths(text: str) -> Set[str]:
    candidates: List[str] = []
    candidates.extend(
        match.group("path")
        for match in re.finditer(
            r"(?im)^\s*\*{3}\s+(?:add|update|delete)\s+file:\s*(?P<path>[^\r\n]+\.cs)\s*$",
            str(text or ""),
        )
    )
    candidates.extend(
        match.group("path")
        for match in re.finditer(
            r"(?i)\*{3}\s+(?:add|update|delete)\s+file:\s*(?P<path>.*?\.cs)(?=\\n|\r?$)",
            str(text or ""),
            re.MULTILINE,
        )
    )
    return {
        normalized
        for candidate in candidates
        if (normalized := _normalize_pb_target_path(candidate))
    }


def _extract_structured_write_csharp_paths(payload: Mapping[str, Any]) -> Set[str]:
    raw = payload.get("arguments") or payload.get("input") or {}
    if isinstance(raw, str):
        try:
            raw = load_json_without_duplicate_keys(raw)
        except (json.JSONDecodeError, DuplicateJsonKeyError):
            return set()
    if not isinstance(raw, Mapping):
        return set()
    path_keys = {"path", "file_path", "target_path", "destination"}
    return {
        normalized
        for key, value in raw.items()
        if str(key).strip().lower() in path_keys
        if isinstance(value, str)
        if (normalized := _normalize_pb_target_path(value))
    }


def _extract_shell_write_csharp_paths(command: str) -> Set[str]:
    candidates: List[str] = []
    write_command = re.compile(
        r"(?is)(?<![a-z0-9_-])(?:set-content|add-content|clear-content|out-file|"
        r"new-item|copy-item|move-item|rename-item|remove-item)\b"
        r"(?P<body>[^|\r\n]*)"
    )
    target_flag = re.compile(
        r"(?i)-(?:literalpath|path|filepath|destination)\s+"
        r"(?P<path>\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s;|]+)"
    )
    for match in write_command.finditer(str(command or "")):
        flag = target_flag.search(match.group("body"))
        if flag:
            candidates.append(flag.group("path"))
    candidates.extend(
        match.group("path")
        for match in re.finditer(
            r"(?m)(?<!>)>{1,2}\s*(?P<path>\"[^\"\r\n]+\"|'[^'\r\n]+'|[^\s;|]+\.cs)",
            str(command or ""),
        )
    )
    return {
        normalized
        for candidate in candidates
        if (normalized := _normalize_pb_target_path(candidate))
    }


def _normalize_pb_target_path(value: str) -> str:
    normalized = str(value or "").strip().strip("\"'`<>()[]{}.,:;").replace("\\", "/")
    normalized = re.sub(r"/+", "/", normalized).lower()
    return normalized if normalized.endswith(".cs") else ""


def _pb_targets_cover(
    written_targets: Set[str],
    verifier_targets: Set[str],
    *,
    session_cwd: str = "",
) -> bool:
    if not written_targets or not verifier_targets:
        return False
    return all(
        any(
            _pb_target_paths_match(
                target,
                verifier_target,
                session_cwd=session_cwd,
            )
            for verifier_target in verifier_targets
        )
        for target in written_targets
    )


def _pb_target_paths_match(
    left: str,
    right: str,
    *,
    session_cwd: str = "",
) -> bool:
    left_path = _canonical_pb_target_path(left, session_cwd=session_cwd)
    right_path = _canonical_pb_target_path(right, session_cwd=session_cwd)
    if not left_path or not right_path:
        return False
    return left_path == right_path


def _canonical_pb_target_path(value: str, *, session_cwd: str) -> str:
    normalized = _normalize_pb_target_path(value)
    if not normalized:
        return ""
    if _is_absolute_pb_target_path(normalized):
        return _collapse_pb_path_components(normalized)
    base = str(session_cwd or "").strip().strip("\"'`").replace("\\", "/").lower()
    base = re.sub(r"/+", "/", base)
    if not _is_absolute_pb_target_path(base):
        return _collapse_pb_path_components(normalized)
    return _collapse_pb_path_components(f"{base.rstrip('/')}/{normalized}")


def _collapse_pb_path_components(value: str) -> str:
    prefix = ""
    remainder = str(value or "")
    if re.match(r"^[a-z]:/", remainder):
        prefix, remainder = remainder[:2], remainder[3:]
    elif remainder.startswith("/"):
        prefix, remainder = "/", remainder[1:]
    components: List[str] = []
    for component in remainder.split("/"):
        if component in {"", "."}:
            continue
        if component == "..":
            if not components:
                return ""
            components.pop()
            continue
        components.append(component)
    collapsed = "/".join(components)
    if prefix == "/":
        return f"/{collapsed}"
    if prefix:
        return f"{prefix}/{collapsed}"
    return collapsed


def _is_absolute_pb_target_path(value: str) -> bool:
    return bool(value.startswith("/") or re.match(r"^[a-z]:/", value))


def _pb_migration_harness_acceptance(
    audit: Mapping[str, Any],
    *,
    required: bool,
    default: Dict[str, Any],
) -> Dict[str, Any]:
    if not required or not audit.get("required"):
        return default
    required_outputs = list(audit.get("required_outputs") or _PB_MIGRATION_REQUIRED_OUTPUTS)
    satisfied_outputs = [
        name
        for name in required_outputs
        if name in set(audit.get("satisfied_outputs", []) or [])
    ]
    missing_outputs = [name for name in required_outputs if name not in satisfied_outputs]
    if missing_outputs:
        status = "missing_outputs"
    elif audit.get("completion_requested"):
        status = "passed" if audit.get("verifier_completed") else "completion_evidence_blocked"
    else:
        status = "draft_validated" if audit.get("draft_validated") else "missing_outputs"
    return {
        "status": status,
        "required_outputs": required_outputs,
        "satisfied_outputs": satisfied_outputs,
        "missing_outputs": missing_outputs,
    }


def _pb_migration_execution_issues(audit: Mapping[str, Any]) -> List[Dict[str, Any]]:
    if not audit.get("required"):
        return []
    writes = list(audit.get("relevant_writes", []) or [])
    issues: List[Dict[str, Any]] = []
    if not audit.get("verifier_executed"):
        issues.append({
            "skill": "pb-to-csharp-migration-harness",
            "status": "missing_post_write_migration_verification",
            "severity": "P0",
            "reason": (
                "PB migration C#/Designer writes lack a correlated verifier receipt with an exact "
                "call identity, target artifact readback SHA-256, packaged profile identity, stage "
                "statuses, and completion_allowed contract."
            ),
            "action": "Run the PB verifier after the last write and emit its complete structured receipt.",
            "samples": [str(item.get("sample", "")) for item in writes[-2:]],
        })
    missing_outputs = list(audit.get("missing_outputs", []) or [])
    if missing_outputs:
        issues.append(
            {
                "skill": "pb-to-csharp-migration-harness",
                "status": "missing_pb_migration_required_outputs",
                "severity": "P0",
                "reason": (
                    "PB migration completion requires independent evidence for every output; "
                    "one C# verifier result cannot satisfy SP, SQL release binding, build, DB, or manual QA."
                ),
                "missing_outputs": missing_outputs,
                "action": "Collect one correlated command/tool receipt for each missing PB migration output.",
                "samples": [],
            }
        )
    if audit.get("style_application_status") != "applied":
        issues.append(
            {
                "skill": "pb-to-csharp-migration-harness",
                "status": "pb_migration_style_application_blocked",
                "severity": "P0",
                "reason": (
                    "PB migration style application is blocked without a consumed packaged fixed-profile "
                    "receipt whose id, version, and hash match the packaged artifact."
                ),
                "action": "Emit and validate packaged_sanitized_profile consumption evidence.",
                "samples": [],
            }
        )
    return issues


def _scan_sql_audit_records(
    records: Sequence[SessionTextRecord],
) -> Dict[str, Any]:
    if not isinstance(records, DiskBackedSessionTextRecords):
        raise RuntimeError("SQL audit scanning requires indexed text facts")
    scan: Dict[str, Any] = {
        "request_index": -1,
        "action_index": -1,
        "action_kind": "",
        "verification_boundary_index": -1,
        "later_request_index": -1,
        "provider_inspection_calls": [],
        "verifier_calls": [],
        "verifier_outputs": [],
        "binder_candidates": [],
    }
    last_user_index = -1
    first_followup: tuple[int, SessionTextRecord] | None = None
    verifier_output_markers = (
        "original_sha256",
        "formatted_sha256",
        "style_contract_sha256",
        "verification_id",
        "mechanical_checks",
        "alias_role_plan_validation",
        "verify_sql_formatting_style",
        "src.skills.sql_formatting_style",
    )
    for index, record in records.iter_indexed_records():
        passive = _is_passive_text(record.text)
        lowered = record.text.lower()
        if scan["request_index"] < 0:
            if (
                record.role == "user"
                and not passive
                and looks_like_sql_output_request(lowered)
            ):
                scan["request_index"] = index
                last_user_index = index
            continue

        if record.role == "user" and not passive:
            last_user_index = index
            if scan["action_index"] >= 0:
                if first_followup is None:
                    first_followup = (index, record)
                if (
                    scan["later_request_index"] < 0
                    and _is_sql_follow_up_request(record.text)
                ):
                    scan["later_request_index"] = index
        elif (
            scan["action_index"] >= 0
            and first_followup is None
            and record.role == "assistant"
            and record.payload_type in {"message", "agent_message"}
            and not passive
        ):
            first_followup = (index, record)

        action_kind = ""
        if (
            record.role == "assistant"
            or record.payload_type in {"agent_message", "task_complete"}
        ) and _looks_like_sql_answer(lowered):
            action_kind = "sql_output"
        elif _looks_like_sql_db_write(record):
            action_kind = "db_write"
        if action_kind:
            scan["action_index"] = index
            scan["action_kind"] = action_kind
            scan["verification_boundary_index"] = max(
                scan["request_index"],
                last_user_index,
            )
            scan["later_request_index"] = -1
            first_followup = None

        if _looks_like_sql_formatting_provider_inspection(record):
            scan["provider_inspection_calls"].append(index)
        if _invokes_sql_formatting_verifier(record):
            scan["verifier_calls"].append(index)
        if (
            record.payload_type in {"function_call_output", "custom_tool_call_output"}
            and any(marker in lowered for marker in verifier_output_markers)
            and _is_sql_verifier_output_candidate(record)
        ):
            scan["verifier_outputs"].append(index)
        if _looks_like_sql_final_response_binder_attempt(record):
            scan["binder_candidates"].append(index)

    if (
        scan["action_kind"] == "sql_output"
        and first_followup is not None
        and first_followup[1].role == "user"
        and _is_short_contextual_sql_correction(first_followup[1].text)
    ):
        scan["later_request_index"] = first_followup[0]
    return scan


def _host_local_sql_formatting_audit(path: Path) -> Dict[str, Any]:
    records = _session_text_records(path)
    session_metadata = _session_metadata(path)
    raw_session_id = session_metadata.get("id")
    session_id = raw_session_id.strip() if type(raw_session_id) is str else ""
    session_cwd = str(session_metadata.get("cwd", "") or "").strip()
    result: Dict[str, Any] = {
        "required": False,
        "status": "not_required",
        "states": [],
        "provider_selected": False,
        "provider_inspected": False,
        "formatter_application_proven": False,
        "verifier_executed": False,
        "verifier_failed": False,
        "verifier_pending": False,
        "verifier_evidence_unbound": False,
        "final_response_bound": False,
        "verified_before_output": False,
        "verification_id": "",
        "binding_errors": [],
        "action_kind": "",
        "issues": [],
    }

    scan = _scan_sql_audit_records(records)
    request_index = int(scan["request_index"])
    if request_index < 0:
        return result

    action_index = int(scan["action_index"])
    action_kind = str(scan["action_kind"])
    if action_index < 0:
        return result

    later_request_index = int(scan["later_request_index"])
    if later_request_index >= 0:
        result["required"] = True
        result["action_kind"] = action_kind
        result["status"] = "formatter_application_not_proven"
        result["states"] = ["provider_selection_invalidated", "formatter_application_not_proven"]
        result["binding_errors"] = ["later_sql_request_without_new_bound_answer"]
        result["issues"] = [
            {
                "skill": "sql-formatting",
                "status": "missing_before_sql_output",
                "severity": "P1",
                "reason": (
                    "A later user SQL correction or new SQL request invalidated the prior provider selection, "
                    "verification, and final-response binding, but no newly bound answer followed."
                ),
                "action": "Rerun front-door provider selection, the verifier, and the final binder for the later request.",
                "binding_errors": ["later_sql_request_without_new_bound_answer"],
                "samples": [_short(records[later_request_index].text)],
            }
        ]
        return result

    result["required"] = True
    result["action_kind"] = action_kind
    verification_boundary_index = int(scan["verification_boundary_index"])
    provider_selections = _correlated_sql_provider_selections(
        records,
        lower_bound=verification_boundary_index,
        upper_bound=action_index,
    )
    provider_selected = (
        provider_selections.has_valid_selection()
        if isinstance(provider_selections, DiskBackedSqlProviderSelections)
        else any(item.get("provenance_valid") is True for item in provider_selections)
    )
    inspected_indices = []
    for index in scan["provider_inspection_calls"]:
        if not (request_index < index < action_index):
            continue
        output_index = _correlated_successful_provider_read_output(records, index, action_index)
        if output_index >= 0:
            inspected_indices.append(output_index)
    verifier_calls = [
        index
        for index in scan["verifier_calls"]
        if verification_boundary_index < index < action_index
    ]
    verifier_outputs = [
        index
        for index in scan["verifier_outputs"]
        if verification_boundary_index < index < action_index
    ]
    binder_candidates = [
        index
        for index in scan["binder_candidates"]
        if verification_boundary_index < index < action_index
    ]
    binding_calls = [
        index for index in binder_candidates if _invokes_sql_final_response_binder(records[index])
    ]

    result["provider_selected"] = provider_selected
    result["provider_inspected"] = bool(inspected_indices)
    result["verifier_executed"] = bool(verifier_calls or binding_calls)
    states: List[str] = []
    if result["provider_selected"]:
        states.append("provider_selected")
    if result["provider_inspected"]:
        states.append("provider_inspected")
    if result["verifier_executed"]:
        states.append("verifier_executed")

    final_sql = _extract_actionable_sql(records[action_index], action_kind)
    binding_errors: List[str] = []
    for candidate_index in binder_candidates:
        invocation = _sql_final_response_cli_invocation(records[candidate_index])
        if invocation.get("valid"):
            continue
        for error in invocation.get("errors", []):
            _append_unique_text(binding_errors, str(error))
    latest_evaluation: Dict[str, Any] = {}
    used_output_indices: Set[int] = set()
    for call_index in verifier_calls:
        output_index, correlation_error = _correlated_sql_verifier_output(
            records,
            call_index,
            action_index,
        )
        if correlation_error:
            _append_unique_text(binding_errors, correlation_error)
        if output_index < 0:
            latest_evaluation = {"status": "unbound", "errors": [correlation_error or "verifier_output_missing"]}
            continue
        used_output_indices.add(output_index)
        latest_evaluation = _evaluate_sql_verifier_output(
            records[output_index],
            records[call_index],
            final_sql,
            records=records,
            request_index=request_index,
            call_index=call_index,
        )
        if (
            latest_evaluation.get("status") in {"passed", "pending"}
            and not any(index < call_index for index in inspected_indices)
        ):
            latest_evaluation = {
                "status": "unbound",
                "errors": ["provider_inspection_not_before_verifier"],
            }
        for error in latest_evaluation.get("errors", []):
            _append_unique_text(binding_errors, str(error))

    if not verifier_calls and verifier_outputs:
        _append_unique_text(binding_errors, "verifier_output_without_call")
        latest_evaluation = {"status": "unbound", "errors": ["verifier_output_without_call"]}
    elif verifier_calls:
        unmatched_outputs = [index for index in verifier_outputs if index not in used_output_indices]
        if unmatched_outputs and not latest_evaluation:
            _append_unique_text(binding_errors, "verifier_output_without_correlated_call")
            latest_evaluation = {"status": "unbound", "errors": ["verifier_output_without_correlated_call"]}

    verifier_status = str(latest_evaluation.get("status", ""))
    if verifier_status in {"passed", "pending"} and binding_errors:
        verifier_status = "unbound"
    if verifier_status == "failed":
        result["verifier_failed"] = True
        states.append("verifier_failed")
    elif verifier_status == "pending":
        result["verifier_pending"] = True
        states.append("verifier_pending")
    elif verifier_status == "unbound":
        result["verifier_evidence_unbound"] = True
        states.append("verifier_evidence_unbound")

    verifier_bound = verifier_status == "passed"
    latest_binding: Dict[str, Any] = {}
    for call_index in binding_calls:
        output_index, correlation_error = _correlated_sql_final_binding_output(
            records,
            call_index,
            action_index,
        )
        if correlation_error:
            _append_unique_text(binding_errors, correlation_error)
        if output_index < 0:
            latest_binding = {
                "status": "unbound",
                "errors": [correlation_error or "final_response_binding_output_missing"],
            }
            continue
        latest_binding = _evaluate_sql_final_response_binding(
            records[output_index],
            records[call_index],
            records[action_index],
            final_sql,
            records=records,
            request_index=request_index,
            call_index=call_index,
            output_index=output_index,
            inspected_indices=inspected_indices,
            provider_selections=provider_selections,
            session_id=session_id,
            session_cwd=session_cwd,
        )
        for error in latest_binding.get("errors", []):
            _append_unique_text(binding_errors, str(error))

    binding_bound = latest_binding.get("status") == "bound"
    if action_kind == "sql_output" and not binding_bound:
        _append_unique_text(binding_errors, "final_response_binding_missing")
    if binding_bound:
        result["final_response_bound"] = True
        states.append("final_response_bound")

    verified = bool(
        result["provider_selected"]
        and
        result["provider_inspected"]
        and result["verifier_executed"]
        and (binding_bound if action_kind == "sql_output" else verifier_bound)
    )
    if verified:
        result["formatter_application_proven"] = True
        result["verified_before_output"] = True
        result["verification_id"] = str(
            (latest_binding if action_kind == "sql_output" else latest_evaluation).get(
                "verification_id", ""
            )
        )
        result["status"] = "verified_before_output"
        states.append("verified_before_output")
    else:
        result["status"] = (
            "verifier_failed"
            if result["verifier_failed"]
            else "verifier_pending"
            if result["verifier_pending"]
            else "verifier_evidence_unbound"
            if result["verifier_evidence_unbound"]
            else "formatter_application_not_proven"
        )
        states.append("formatter_application_not_proven")

    result["states"] = states
    result["binding_errors"] = binding_errors
    if verified:
        return result

    action_phrase = "DB write" if action_kind == "db_write" else "final SQL output"
    sample = [_short(records[action_index].text)]
    result["issues"].extend(
        [
            {
                "skill": "sql-formatting",
                "status": "missing_before_sql_output",
                "severity": "P1",
                "reason": (
                    f"An actionable SQL request reached {action_phrase} without provider inspection and "
                    "a correlated final-response binding receipt proving the exact formatted SQL. "
                    "Provider selection or verifier execution alone is not application."
                ),
                "action": (
                    "Inspect the host-local sql-formatting contract, apply it, then execute "
                    "`guard_and_bind_verified_sql_final_response` and emit only its bound final response."
                ),
                "evidence_states": list(states),
                "samples": sample,
            },
            {
                "skill": "sql-formatting",
                "status": "formatter_application_not_proven",
                "severity": "P1",
                "reason": (
                    "The session did not prove that the host-local SQL formatting contract was applied "
                    f"before {action_phrase}. Reading SKILL.md is inspection only."
                ),
                "action": (
                    "Require provider inspection plus a successful guard-and-bind receipt before actionable output."
                ),
                "evidence_states": list(states),
                "samples": sample,
            },
        ]
    )
    if result["verifier_pending"]:
        result["issues"].append(
            {
                "skill": "sql-formatting-style-harness",
                "status": "verifier_pending",
                "severity": "P1",
                "reason": (
                    "The scalar refactor is mechanically valid but remains pending authenticated "
                    "runtime semantic verification."
                ),
                "action": "Keep the refactor pending until release_readiness is ready.",
                "binding_errors": list(binding_errors),
                "samples": sample,
            }
        )
    elif result["verifier_failed"]:
        result["issues"].append(
            {
                "skill": "sql-formatting-style-harness",
                "status": "verifier_failed",
                "severity": "P1",
                "reason": "The executed SQL formatting verifier failed before actionable SQL was emitted.",
                "action": "Fix the mechanical or alias failures and rerun the verifier before output.",
                "binding_errors": list(binding_errors),
                "samples": sample,
            }
        )
    elif result["verifier_evidence_unbound"]:
        result["issues"].append(
            {
                "skill": "sql-formatting-style-harness",
                "status": "verifier_evidence_unbound",
                "severity": "P1",
                "reason": (
                    "SQL verifier evidence could not be bound to an actual preceding verifier call and the exact final SQL."
                ),
                "action": (
                    "Correlate call IDs when present; otherwise keep call/output adjacent and provide all verifier hashes, "
                    "verification_id, mechanical status, alias status, and exact final SQL binding."
                ),
                "binding_errors": list(binding_errors),
                "samples": sample,
            }
        )
    return result


def _looks_like_sql_formatting_provider_inspection(record: SessionTextRecord) -> bool:
    if record.payload_type not in {"function_call", "custom_tool_call"}:
        return False
    lowered = record.text.lower()
    if not re.search(r"(?:^|[\\/])sql[-_]formatting[\\/]skill\.md\b", lowered):
        return False
    return any(
        marker in lowered
        for marker in ["get-content", "read_file", "read_text", "open_file", "cat ", "type "]
    )


def _correlated_successful_provider_read_output(
    records: List[SessionTextRecord],
    call_index: int,
    action_index: int,
) -> int:
    call = records[call_index]
    if call.call_id:
        if isinstance(records, DiskBackedSessionTextRecords):
            index = records.correlated_output_record_index(
                call_index,
                before_index=action_index,
            )
            if index >= 0:
                return index if _successful_provider_read_output(records[index]) else -1
            return -1
        for index in range(call_index + 1, action_index):
            record = records[index]
            if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
                continue
            if record.call_id == call.call_id:
                return index if _successful_provider_read_output(record) else -1
        return -1

    limit = min(action_index, call_index + 7)
    for index in range(call_index + 1, limit):
        record = records[index]
        if record.payload_type in {"function_call", "custom_tool_call"}:
            break
        if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
            continue
        if record.call_id:
            return -1
        return index if _successful_provider_read_output(record) else -1
    return -1


def _successful_provider_read_output(record: SessionTextRecord) -> bool:
    text = record.text.strip()
    if not _successful_tool_output_text(text):
        return False
    return any(_valid_sql_formatting_skill_contract(item) for item in _provider_output_texts(text))


def _successful_tool_output_text(text: str) -> bool:
    if not text.strip():
        return False
    data = _json_object_from_text(text)
    if data:
        status = str(data.get("status", "") or "").strip().lower()
        success = data.get("success")
        exit_code = data.get("exit_code")
        if success is False or status in {"blocked", "error", "failed", "failure"}:
            return False
        if isinstance(exit_code, int) and exit_code != 0:
            return False
    lowered = text.lower()
    return not bool(
        re.search(r"\bexit code\s*:\s*[1-9]\d*\b", lowered)
        or any(
            marker in lowered
            for marker in [
                "script failed",
                "cannot find path",
                "no such file",
                "permission denied",
                "access is denied",
            ]
        )
    )


def _provider_output_texts(text: str) -> List[str]:
    candidates = [text, _strip_passive_prefix(text)]
    data = _json_object_from_text(text)
    for key in ["stdout", "output", "content", "text"]:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value)
    return candidates


def _valid_sql_formatting_skill_contract(text: str) -> bool:
    match = re.match(r"^\s*---\s*\r?\n(.*?)\r?\n---\s*\r?\n(.*)$", text, re.DOTALL)
    if not match:
        return False
    frontmatter, body = match.groups()
    name_match = re.search(r"(?im)^name\s*:\s*['\"]?([^'\"\r\n]+)", frontmatter)
    description_match = re.search(r"(?im)^description\s*:\s*\S", frontmatter)
    if not name_match or name_match.group(1).strip().lower() != "sql-formatting":
        return False
    if not description_match:
        return False
    lowered = body.lower()
    preservation_terms = [
        "preserve original sql logic",
        "preserve sql logic",
        "preserve string literals",
        "string literals unchanged",
        "without semantic changes",
        "must not drift into optimization",
    ]
    required_runtime_markers = [
        "verify_sql_formatting_style",
        "guard_and_bind_verified_sql_final_response",
    ]
    return (
        "sql" in lowered
        and any(marker in lowered for marker in preservation_terms)
        and all(marker in lowered for marker in required_runtime_markers)
    )


def _invokes_sql_formatting_verifier(record: SessionTextRecord) -> bool:
    if record.payload_type not in {"function_call", "custom_tool_call"}:
        return False
    name = record.name.lower().replace("-", "_")
    lowered = record.text.lower()
    if "verify_sql_formatting_style" in name:
        return True
    if name in {"src.skills.sql_formatting_style", "sql_formatting_style"}:
        return True
    if not any(marker in name for marker in ["shell", "exec", "command", "powershell"]):
        return False
    if any(marker in lowered for marker in ["get-content", "select-string", "rg ", "git grep"]):
        return False
    return bool(
        re.search(r"\bpython(?:\.exe)?\b[^\r\n]*(?:-m\s+src\.skills\.sql_formatting_style|sql_formatting_style\.py)", lowered)
        or re.search(r"\bpython(?:\.exe)?\b[^\r\n]*verify_sql_formatting_style\s*\(", lowered)
    )


def _invokes_sql_final_response_binder(record: SessionTextRecord) -> bool:
    return bool(_sql_final_response_cli_invocation(record).get("valid"))


def _looks_like_sql_final_response_binder_attempt(record: SessionTextRecord) -> bool:
    if record.payload_type not in {"function_call", "custom_tool_call"}:
        return False
    return "src.skills.sql_formatting_provider" in f"{record.text} {record.arguments}".lower()


def _sql_final_response_cli_invocation(record: SessionTextRecord) -> Dict[str, Any]:
    errors: List[str] = []
    if record.payload_type not in {"function_call", "custom_tool_call"}:
        return {"valid": False, "errors": ["sql_binder_not_tool_call"]}
    name = record.name.lower().replace("-", "_")
    if not any(marker in name for marker in ["shell", "exec", "command", "powershell"]):
        return {"valid": False, "errors": ["sql_binder_not_shell_tool"]}

    command = _exact_shell_command_text(record)
    if not command:
        error = (
            "sql_binder_exec_result_flow_invalid"
            if "exec" in name and "tools.shell_command" in str(record.arguments or "")
            else "sql_binder_command_not_extractable"
        )
        return {"valid": False, "errors": [error]}
    command = command.strip()
    if command.startswith("&"):
        if len(command) == 1 or not command[1].isspace():
            return {"valid": False, "errors": ["sql_binder_command_not_standalone"]}
        command = command[1:].lstrip()
    if not command or _contains_unquoted_shell_control(command):
        return {"valid": False, "errors": ["sql_binder_command_not_standalone"]}

    try:
        tokens = [_strip_shell_token_quotes(item) for item in shlex.split(command, posix=False)]
    except ValueError:
        return {"valid": False, "errors": ["sql_binder_command_parse_failed"]}
    if len(tokens) < 4:
        return {"valid": False, "errors": ["sql_binder_command_incomplete"]}
    executable = Path(tokens[0].replace("\\", "/")).name.lower()
    if executable not in {"python", "python.exe"}:
        errors.append("sql_binder_executable_not_python")
    if tokens[1:3] != ["-m", "src.skills.sql_formatting_provider"]:
        errors.append("sql_binder_module_mismatch")

    required_flags = {
        "--original-file",
        "--candidate-file",
        "--response-file",
        "--provider-path",
        "--selected-active-provider-path",
        "--provider-selection-file",
        "--session-id",
        "--invocation-nonce",
    }
    optional_flags = {
        "--style-contract",
        "--alias-role-plan-file",
        "--verifier-history-file",
        "--cte-temp-table-reason",
    }
    arguments: Dict[str, str] = {}
    index = 3
    while index < len(tokens):
        token = tokens[index]
        if not token.startswith("--"):
            errors.append("sql_binder_unexpected_positional_argument")
            break
        if token not in required_flags | optional_flags:
            errors.append(
                "sql_binder_skills_root_override_rejected"
                if token == "--skills-root"
                else "sql_binder_unknown_flag"
            )
            break
        if token in arguments:
            errors.append("sql_binder_duplicate_flag")
            break
        if index + 1 >= len(tokens) or tokens[index + 1].startswith("--"):
            errors.append("sql_binder_flag_value_missing")
            break
        arguments[token] = tokens[index + 1]
        index += 2
    missing = sorted(required_flags - set(arguments))
    if missing:
        errors.extend(f"sql_binder_required_flag_missing:{flag}" for flag in missing)
    nonce = arguments.get("--invocation-nonce", "")
    if nonce and not re.fullmatch(r"[A-Za-z0-9._:-]{16,128}", nonce):
        errors.append("sql_binder_invocation_nonce_invalid")
    return {
        "valid": not errors,
        "command": command,
        "arguments": arguments,
        "errors": errors,
    }


def _exact_shell_command_text(record: SessionTextRecord) -> str:
    value = str(record.arguments or "").strip()
    name = record.name.lower().replace("-", "_")
    if not value:
        return ""
    if "exec" not in name:
        try:
            parsed = load_json_without_duplicate_keys(value)
        except (json.JSONDecodeError, DuplicateJsonKeyError):
            parsed = None
        if isinstance(parsed, dict):
            command = parsed.get("command")
            return command if isinstance(command, str) else ""
        return value
    source = re.sub(
        r"^\s*//\s*@exec:[^\r\n]*(?:\r?\n|$)",
        "",
        value,
        count=1,
    )
    statement = re.fullmatch(
        r"\s*const\s+(?P<result>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
        r"await\s+tools\.shell_command\s*\(\s*(?P<arguments>\{[\s\S]*\})\s*\)\s*;\s*"
        r"text\s*\(\s*(?P=result)\s*\)\s*;\s*",
        source,
    )
    command_binding = None
    if statement is None:
        statement = re.fullmatch(
            r"\s*const\s+(?P<command_var>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
            r"(?P<command_literal>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')\s*;\s*"
            r"const\s+(?P<result>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
            r"await\s+tools\.shell_command\s*\(\s*(?P<arguments>\{[\s\S]*\})\s*\)\s*;\s*"
            r"text\s*\(\s*(?P=result)\s*\)\s*;\s*",
            source,
        )
        if statement is not None:
            try:
                command_binding = ast.literal_eval(statement.group("command_literal"))
            except (SyntaxError, ValueError):
                return ""
            if not isinstance(command_binding, str):
                return ""
    if (
        statement is None
        or source.count("tools.shell_command") != 1
        or len(re.findall(r"\bawait\s+tools\.", source)) != 1
        or len(re.findall(r"\bawait\b", source)) != 1
    ):
        return ""
    arguments_text = statement.group("arguments")
    if command_binding is not None:
        command_var = re.escape(statement.group("command_var"))
        arguments_text, replacements = re.subn(
            rf"(?P<prefix>[{{,]\s*)(?P<key>command|\"command\"|'command')\s*:\s*{command_var}(?P<suffix>\s*[,}}])",
            lambda match: (
                f'{match.group("prefix")}\"command\":{json.dumps(command_binding)}'
                f'{match.group("suffix")}'
            ),
            arguments_text,
        )
        if replacements != 1:
            return ""
    arguments_text = re.sub(
        r"(?P<prefix>[{,]\s*)(?P<key>[A-Za-z_$][A-Za-z0-9_$]*)\s*:",
        lambda match: f'{match.group("prefix")}\"{match.group("key")}\":',
        arguments_text,
    )
    try:
        parsed_arguments = load_json_without_duplicate_keys(arguments_text)
    except (json.JSONDecodeError, DuplicateJsonKeyError):
        return ""
    command = parsed_arguments.get("command") if isinstance(parsed_arguments, dict) else None
    return command if isinstance(command, str) else ""


def _contains_unquoted_shell_control(command: str) -> bool:
    quote = ""
    escaped = False
    for character in command:
        if escaped:
            escaped = False
            continue
        if quote == '"' and character == "\\":
            escaped = True
            continue
        if character in {"'", '"'}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
            continue
        if not quote and character in {"|", ";", ">", "<", "#", "\r", "\n", "&"}:
            return True
    return bool(quote)


def _strip_shell_token_quotes(value: str) -> str:
    text = str(value)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def _sql_cli_flag(call: SessionTextRecord, flag: str) -> str:
    invocation = _sql_final_response_cli_invocation(call)
    arguments = invocation.get("arguments")
    if not isinstance(arguments, dict):
        return ""
    return str(arguments.get(flag, "") or "").strip()


def _sql_cli_input_receipt_errors(
    receipt: Dict[str, Any],
    call: SessionTextRecord,
    binding: Dict[str, Any],
    *,
    session_cwd: str,
) -> tuple[List[str], Any]:
    cli_inputs = receipt.get("cli_inputs")
    if not isinstance(cli_inputs, dict):
        return ["cli_input_receipt_missing"], None
    errors: List[str] = list(_successful_sql_cli_input_errors(cli_inputs))
    module = cli_inputs.get("module")
    if type(module) is not str:
        errors.append("cli_input_module_not_string")
    elif module != "src.skills.sql_formatting_provider":
        errors.append("cli_input_module_mismatch")

    arguments = cli_inputs.get("arguments")
    if not isinstance(arguments, dict):
        errors.append("cli_input_arguments_missing")
        arguments = {}
    flag_map = {
        "original_file": "--original-file",
        "candidate_file": "--candidate-file",
        "response_file": "--response-file",
        "provider_path": "--provider-path",
        "selected_active_provider_path": "--selected-active-provider-path",
        "provider_selection_file": "--provider-selection-file",
        "session_id": "--session-id",
        "invocation_nonce": "--invocation-nonce",
    }
    exact_value_keys = {"session_id", "invocation_nonce"}
    for key, flag in flag_map.items():
        call_value = _sql_cli_flag(call, flag)
        raw_receipt_value = arguments.get(key)
        if type(raw_receipt_value) is not str:
            errors.append(f"cli_input_argument_{key}_not_string")
            receipt_value = ""
        else:
            receipt_value = raw_receipt_value.strip()
        if not call_value:
            errors.append(f"cli_input_{key}_call_scope_missing")
        elif key in exact_value_keys and call_value != receipt_value:
            errors.append(f"cli_input_{key}_mismatch")
        elif key not in exact_value_keys and _normalized_sql_provider_path(call_value) != _normalized_sql_provider_path(receipt_value):
            errors.append(f"cli_input_{key}_mismatch")

    hashes = cli_inputs.get("hashes")
    if not isinstance(hashes, dict):
        errors.append("cli_input_hashes_missing")
        hashes = {}
    hash_bindings = {
        "original_text_sha256": "original_sha256",
        "candidate_text_sha256": "formatted_sha256",
        "response_text_sha256": "final_response_sha256",
    }
    for receipt_key, binding_key in hash_bindings.items():
        raw_value = hashes.get(receipt_key)
        raw_expected = binding.get(binding_key)
        if type(raw_value) is not str:
            errors.append(f"cli_input_hash_{receipt_key}_not_string")
            value = ""
        else:
            value = raw_value.lower()
        expected = (
            raw_expected.lower() if type(raw_expected) is str else ""
        )
        if type(raw_expected) is not str:
            errors.append(f"{binding_key}_not_string")
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            errors.append(f"cli_input_{receipt_key}_missing_or_invalid")
        elif value != expected:
            errors.append(f"cli_input_{receipt_key}_mismatch")
    raw_selection_hash = hashes.get("provider_selection_sha256")
    if type(raw_selection_hash) is not str:
        errors.append("cli_input_hash_provider_selection_sha256_not_string")
        selection_hash = ""
    else:
        selection_hash = raw_selection_hash.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", selection_hash):
        errors.append("cli_input_provider_selection_sha256_missing_or_invalid")
    exit_status = cli_inputs.get("exit_status")
    if type(exit_status) is not int:
        errors.append("cli_input_exit_status_not_integer")
    elif exit_status != 0:
        errors.append("cli_input_exit_status_not_success")

    artifact_flags = {
        "original_file": "--original-file",
        "candidate_file": "--candidate-file",
        "response_file": "--response-file",
        "provider_selection_file": "--provider-selection-file",
    }
    actual_paths: Dict[str, str] = {}
    if all(_sql_cli_flag(call, flag) for flag in artifact_flags.values()):
        for key, flag in artifact_flags.items():
            supplied = Path(_sql_cli_flag(call, flag)).expanduser()
            if not supplied.is_absolute() and session_cwd:
                supplied = Path(session_cwd).expanduser() / supplied
            actual_paths[key] = str(supplied.resolve())
    artifacts = None
    if len(actual_paths) == len(artifact_flags):
        try:
            artifacts = load_sql_formatting_cli_artifacts(**actual_paths)
        except SqlFormattingCliArtifactError as exc:
            errors.append(f"cli_input_{exc.code}")
        except (OSError, ValueError, json.JSONDecodeError):
            errors.append("cli_input_artifact_reopen_failed")
    if artifacts is not None:
        resolved_paths = cli_inputs.get("resolved_paths")
        if not isinstance(resolved_paths, dict):
            errors.append("cli_input_resolved_paths_missing")
            resolved_paths = {}
        for key, actual_path in artifacts.resolved_paths.items():
            raw_receipt_path = resolved_paths.get(key)
            if type(raw_receipt_path) is not str:
                errors.append(f"cli_input_resolved_path_{key}_not_string")
                receipt_path = ""
            else:
                receipt_path = raw_receipt_path.strip()
            if not receipt_path:
                errors.append(f"cli_input_{key}_resolved_path_missing")
            elif _normalized_sql_provider_path(receipt_path) != _normalized_sql_provider_path(actual_path):
                errors.append(f"cli_input_{key}_resolved_path_mismatch")
        artifact_hash_bindings = {
            "original_file": ("original_text_sha256", "original_sha256"),
            "candidate_file": ("candidate_text_sha256", "formatted_sha256"),
            "response_file": ("response_text_sha256", "final_response_sha256"),
        }
        for artifact_name, (hash_key, binding_key) in artifact_hash_bindings.items():
            actual_hash = artifacts.hashes[hash_key]
            raw_receipt_hash = hashes.get(hash_key)
            raw_binding_hash = binding.get(binding_key)
            if type(raw_receipt_hash) is not str:
                errors.append(f"cli_input_hash_{hash_key}_not_string")
                receipt_hash = ""
            else:
                receipt_hash = raw_receipt_hash.lower()
            binding_hash = (
                raw_binding_hash.lower()
                if type(raw_binding_hash) is str
                else ""
            )
            if actual_hash != receipt_hash or actual_hash != binding_hash:
                errors.append(f"cli_input_{artifact_name}_hash_mismatch")
        actual_selection_hash = artifacts.hashes["provider_selection_sha256"]
        if actual_selection_hash != selection_hash:
            errors.append("cli_input_provider_selection_file_hash_mismatch")
        for artifact_name in artifact_flags:
            raw_hash_key = f"{artifact_name}_sha256"
            raw_receipt_raw_hash = hashes.get(raw_hash_key)
            if type(raw_receipt_raw_hash) is not str:
                errors.append(f"cli_input_hash_{raw_hash_key}_not_string")
                receipt_raw_hash = ""
            else:
                receipt_raw_hash = raw_receipt_raw_hash.lower()
            actual_raw_hash = artifacts.hashes[raw_hash_key]
            if not re.fullmatch(r"[0-9a-f]{64}", receipt_raw_hash):
                errors.append(
                    f"cli_input_{artifact_name}_raw_hash_missing_or_invalid"
                )
            elif actual_raw_hash != receipt_raw_hash:
                errors.append(f"cli_input_{artifact_name}_raw_hash_mismatch")
        provenance_errors = validate_sql_provider_selection_runtime_receipt(
            artifacts.provider_selection
        )
        if provenance_errors:
            errors.append("cli_input_provider_selection_provenance_invalid")
    return list(dict.fromkeys(errors)), artifacts


def _correlated_sql_final_binding_output(
    records: List[SessionTextRecord],
    call_index: int,
    action_index: int,
) -> tuple[int, str]:
    call = records[call_index]
    if not call.call_id:
        return -1, "final_response_binding_call_id_missing"
    if isinstance(records, DiskBackedSessionTextRecords):
        index = records.correlated_output_record_index(
            call_index,
            before_index=action_index,
        )
        if index >= 0:
            return index, ""
    for index in range(call_index + 1, action_index):
        record = records[index]
        if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
            continue
        if record.call_id == call.call_id:
            return index, ""
    if any(
        records[index].call_id
        and records[index].call_id != call.call_id
        and _sql_final_binding_receipt(records[index].text)
        for index in range(call_index + 1, action_index)
    ):
        return -1, "final_response_binding_call_id_mismatch"
    return -1, "final_response_binding_output_missing"


def _sql_binder_shell_output_status(
    record: SessionTextRecord,
) -> tuple[int | None, List[str]]:
    recorded: List[Any] = list(record.exit_codes)
    if any(type(value) is not int for value in recorded):
        return None, ["final_response_binding_shell_exit_status_invalid"]
    output_text = _strip_passive_prefix(record.text)
    textual_exit_lines = [
        line
        for line in output_text.splitlines()
        if re.match(r"(?i)^\s*exit\s+code\s*:", line)
    ]
    for line in textual_exit_lines:
        match = re.fullmatch(r"Exit code: (0|[1-9][0-9]*)", line)
        if match is None:
            return None, ["final_response_binding_shell_exit_status_invalid"]
        recorded.append(int(match.group(1)))
    root = _json_object_from_text(record.text)
    if root and not (
        isinstance(root.get("binding"), dict)
        and isinstance(root.get("provider_path_guard"), dict)
    ):
        for key in ["exit_code", "return_code", "returncode"]:
            if key not in root:
                continue
            if type(root[key]) is not int:
                return None, ["final_response_binding_shell_exit_status_invalid"]
            recorded.append(root[key])
    if not recorded:
        return None, ["final_response_binding_shell_exit_status_missing"]
    if len(set(recorded)) != 1:
        return None, ["final_response_binding_shell_exit_status_conflicting"]
    status = recorded[0]
    if status != 0:
        return status, ["final_response_binding_shell_exit_status_not_success"]
    return status, []


def _evaluate_sql_final_response_binding(
    record: SessionTextRecord,
    call: SessionTextRecord,
    final_record: SessionTextRecord,
    final_sql: str | None,
    *,
    records: List[SessionTextRecord],
    request_index: int,
    call_index: int,
    output_index: int,
    inspected_indices: List[int],
    provider_selections: Sequence[Dict[str, Any]],
    session_id: str,
    session_cwd: str,
) -> Dict[str, Any]:
    errors: List[str] = []
    receipt = _sql_final_binding_receipt(record.text)
    if not receipt:
        return {"status": "unbound", "errors": ["final_response_binding_receipt_invalid"]}
    runtime_receipt = receipt.get("runtime_receipt")
    receipt_id = (
        runtime_receipt.get("receipt_id")
        if isinstance(runtime_receipt, dict)
        else None
    )
    if type(receipt_id) is str and _sql_runtime_receipt_seen_before(
        records,
        output_index=output_index,
        receipt_id=receipt_id,
        selection=False,
    ):
        errors.append("sql_provider_runtime_receipt_replayed")

    provider_guard = receipt.get("provider_path_guard")
    binding = receipt.get("binding")
    release_status = receipt.get("status")
    if type(release_status) is not str or release_status != "passed":
        errors.append("final_response_binding_status_not_bound")
    if (
        not isinstance(provider_guard, dict)
        or type(provider_guard.get("status")) is not str
        or provider_guard.get("status") != "accepted"
    ):
        errors.append("provider_path_guard_not_accepted")
        provider_guard = {}
    if (
        not isinstance(binding, dict)
        or type(binding.get("status")) is not str
        or binding.get("status") != "bound"
    ):
        errors.append("final_response_binding_not_bound")
        binding = {}
    cli_input_errors, actual_artifacts = _sql_cli_input_receipt_errors(
        receipt,
        call,
        binding,
        session_cwd=session_cwd,
    )
    errors.extend(cli_input_errors)

    output_status, output_status_errors = _sql_binder_shell_output_status(record)
    errors.extend(output_status_errors)
    if output_status != 0:
        errors.append("final_response_binding_command_failed")

    invocation = _sql_final_response_cli_invocation(call)
    for error in invocation.get("errors", []):
        errors.append(str(error))

    provider_path = _sql_cli_flag(call, "--provider-path")
    selected_provider_path = _sql_cli_flag(call, "--selected-active-provider-path")
    provider_selection_file = _sql_cli_flag(call, "--provider-selection-file")
    invocation_session_id = _sql_cli_flag(call, "--session-id")
    invocation_nonce = _sql_cli_flag(call, "--invocation-nonce")
    if not provider_path:
        errors.append("provider_path_call_scope_missing")
    elif not _provider_path_inspected_before_binding(
        records,
        call_index=call_index,
        provider_path=provider_path,
        inspected_indices=inspected_indices,
    ):
        errors.append("bound_provider_path_not_inspected")
    if selected_provider_path and _normalized_sql_provider_path(selected_provider_path) != _normalized_sql_provider_path(provider_path):
        errors.append("selected_provider_path_mismatch")
    receipt_provider_path_value = provider_guard.get("provider_path")
    receipt_provider_path = (
        receipt_provider_path_value.strip()
        if type(receipt_provider_path_value) is str
        else ""
    )
    if type(receipt_provider_path_value) is not str:
        errors.append("provider_path_guard_provider_path_not_string")
    if provider_path and _normalized_sql_provider_path(receipt_provider_path) != _normalized_sql_provider_path(provider_path):
        errors.append("provider_path_receipt_mismatch")

    if isinstance(provider_selections, DiskBackedSqlProviderSelections):
        provider_selection = provider_selections.latest_before(call_index)
    else:
        provider_selection = {}
        for item in provider_selections:
            if int(item.get("output_index", -1)) < call_index:
                provider_selection = item
    selection_path = str(provider_selection.get("provider_path", "") or "").strip()
    selection_sha256 = str(provider_selection.get("selection_sha256", "") or "").strip().lower()
    if not provider_selection:
        errors.append("front_door_provider_selection_missing")
    else:
        for provenance_error in provider_selection.get("provenance_errors", []):
            errors.append(str(provenance_error))
        if _normalized_sql_provider_path(selection_path) != _normalized_sql_provider_path(provider_path):
            errors.append("front_door_provider_path_mismatch")
        if _normalized_sql_provider_path(selection_path) != _normalized_sql_provider_path(selected_provider_path):
            errors.append("front_door_selected_provider_path_mismatch")
        guard_selection_hash_value = provider_guard.get("provider_selection_sha256")
        guard_selection_hash = (
            guard_selection_hash_value.strip().lower()
            if type(guard_selection_hash_value) is str
            else ""
        )
        if type(guard_selection_hash_value) is not str:
            errors.append("provider_path_guard_provider_selection_sha256_not_string")
        if guard_selection_hash != selection_sha256:
            errors.append("provider_guard_selection_hash_mismatch")
        guard_provider_id = provider_guard.get("provider_id")
        selection_provider_id = provider_selection.get("provider_id")
        if (
            type(guard_provider_id) is not str
            or type(selection_provider_id) is not str
            or guard_provider_id != selection_provider_id
        ):
            errors.append("provider_guard_provider_id_mismatch")
        guard_provider_source = provider_guard.get("provider_source")
        selection_provider_source = provider_selection.get("provider_source")
        if (
            type(guard_provider_source) is not str
            or type(selection_provider_source) is not str
            or guard_provider_source != selection_provider_source
        ):
            errors.append("provider_guard_provider_source_mismatch")
        if (
            actual_artifacts is not None
            and actual_artifacts.hashes["provider_selection_sha256"]
            != selection_sha256
        ):
            errors.append("front_door_provider_selection_file_mismatch")
    if not provider_selection_file:
        errors.append("provider_selection_file_call_scope_missing")
    if not invocation_session_id or invocation_session_id != session_id:
        errors.append("provider_invocation_session_scope_mismatch")

    errors.extend(
        validate_sql_formatting_cli_runtime_receipt(
            receipt,
            expected_session_id=session_id,
            expected_invocation_nonce=invocation_nonce,
            expected_provider_selection_sha256=selection_sha256,
        )
    )

    hash_values: Dict[str, str] = {}
    for key in ["original_sha256", "formatted_sha256", "final_response_sha256"]:
        raw_value = binding.get(key)
        hash_values[key] = raw_value.strip().lower() if type(raw_value) is str else ""
        if type(raw_value) is not str:
            errors.append(f"{key}_not_string")
    original_hash = hash_values["original_sha256"]
    formatted_hash = hash_values["formatted_sha256"]
    final_response_hash = hash_values["final_response_sha256"]
    for key, value in [("original_sha256", original_hash), ("formatted_sha256", formatted_hash)]:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            errors.append(f"{key}_missing_or_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", final_response_hash):
        errors.append("final_response_sha256_missing_or_invalid")
    elif hashlib.sha256(final_record.text.encode("utf-8")).hexdigest() != final_response_hash:
        errors.append("final_response_changed_after_binding")
    if re.fullmatch(r"[0-9a-f]{64}", original_hash):
        if not _original_hash_bound_to_session_source(
            records,
            request_index=request_index,
            call_index=call_index,
            original_sha256=original_hash,
        ):
            errors.append("original_sql_not_bound_to_session_source")
    if final_sql is None:
        errors.append("final_sql_not_exactly_extractable")
    elif re.fullmatch(r"[0-9a-f]{64}", formatted_hash):
        if hashlib.sha256(final_sql.encode("utf-8")).hexdigest() != formatted_hash:
            errors.append("formatted_sha256_mismatch")

    verification_id_value = binding.get("verification_id")
    verification_id = (
        verification_id_value.strip()
        if type(verification_id_value) is str
        else ""
    )
    if type(verification_id_value) is not str:
        errors.append("verification_id_not_string")
    elif not re.fullmatch(r"[0-9a-fA-F]{64}", verification_id):
        errors.append("verification_id_missing_or_invalid")
    fence_count = binding.get("sql_fence_count")
    if type(fence_count) is not int:
        errors.append("sql_fence_count_not_integer")
    elif fence_count != 1:
        errors.append("sql_fence_count_not_one")
    return {
        "status": "unbound" if errors else "bound",
        "errors": errors,
        "verification_id": verification_id,
    }


def _sql_final_binding_receipt(text: str) -> Dict[str, Any]:
    root = _json_object_from_text(text)
    if not root:
        return {}
    pending: List[Dict[str, Any]] = [root]
    seen: Set[int] = set()
    while pending:
        current = pending.pop(0)
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        if (
            isinstance(current.get("binding"), dict)
            and isinstance(current.get("provider_path_guard"), dict)
        ) or (
            "runtime_receipt" in current and "cli_inputs" in current
        ):
            return current
        for key in ["metadata", "evidence", "verification", "release", "result"]:
            nested = current.get(key)
            if isinstance(nested, dict):
                pending.append(nested)
        stdout = current.get("stdout")
        if isinstance(stdout, str):
            nested_stdout = _json_object_from_text(stdout)
            if nested_stdout:
                pending.append(nested_stdout)
    return {}


def _provider_path_inspected_before_binding(
    records: List[SessionTextRecord],
    *,
    call_index: int,
    provider_path: str,
    inspected_indices: List[int],
) -> bool:
    target = _normalized_sql_provider_path(provider_path)
    if isinstance(records, DiskBackedSessionTextRecords):
        eligible = 0
        resolved = 0
        for output_index in inspected_indices:
            if not (output_index < call_index):
                continue
            eligible += 1
            inspection_index = records.correlated_call_record_index(output_index)
            if inspection_index < 0:
                continue
            resolved += 1
            inspection = records[inspection_index]
            if (
                _looks_like_sql_formatting_provider_inspection(inspection)
                and target in _normalized_sql_provider_path(inspection.text)
            ):
                return True
        if eligible and resolved == eligible:
            return False
    for index in range(call_index):
        if not _looks_like_sql_formatting_provider_inspection(records[index]):
            continue
        if _normalized_sql_provider_path(records[index].text).find(target) < 0:
            continue
        if any(index < output_index < call_index for output_index in inspected_indices):
            return True
    return False


def _normalized_sql_provider_path(value: str) -> str:
    return re.sub(r"/+", "/", str(value or "").replace("\\", "/")).strip().lower()


def _is_sql_verifier_output_candidate(record: SessionTextRecord) -> bool:
    if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
        return False
    layers = _sql_verifier_data_layers(record.text)
    if not layers:
        return False
    return any(
        _sql_evidence_value(layers, key) is not None
        and _sql_evidence_value(layers, key) != ""
        for key in [
            "original_sha256",
            "formatted_sha256",
            "style_contract_sha256",
            "verification_id",
            "mechanical_checks",
            "alias_role_plan_validation",
        ]
    ) or any(
        marker in record.text.lower()
        for marker in ["verify_sql_formatting_style", "src.skills.sql_formatting_style"]
    )


def _correlated_sql_verifier_output(
    records: List[SessionTextRecord],
    call_index: int,
    action_index: int,
) -> tuple[int, str]:
    call = records[call_index]
    if call.call_id:
        if isinstance(records, DiskBackedSessionTextRecords):
            index = records.correlated_output_record_index(
                call_index,
                before_index=action_index,
            )
            if index >= 0:
                return index, ""
        for index in range(call_index + 1, action_index):
            record = records[index]
            if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
                continue
            if record.call_id == call.call_id:
                return index, ""
        if any(
            records[index].call_id
            and records[index].call_id != call.call_id
            and _is_sql_verifier_output_candidate(records[index])
            for index in range(call_index + 1, action_index)
        ):
            return -1, "verifier_output_call_id_mismatch"
        return -1, "verifier_output_missing"

    limit = min(action_index, call_index + 7)
    for index in range(call_index + 1, limit):
        record = records[index]
        if _invokes_sql_formatting_verifier(record):
            break
        if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
            continue
        if record.call_id:
            return -1, "verifier_output_call_id_mismatch"
        return index, ""
    return -1, "verifier_output_missing"


def _evaluate_sql_verifier_output(
    record: SessionTextRecord,
    call: SessionTextRecord,
    final_sql: str | None,
    *,
    records: List[SessionTextRecord],
    request_index: int,
    call_index: int,
) -> Dict[str, Any]:
    layers = _sql_verifier_data_layers(record.text)
    if not layers:
        return {"status": "unbound", "errors": ["verifier_output_not_structured"]}

    overall_status = _normalized_evidence_status(_sql_evidence_value(layers, "status"))
    mechanical_status = _structured_evidence_status(layers, "mechanical_checks", "mechanical_status")
    alias_status = _alias_role_plan_validation_status(layers)
    success = _sql_evidence_value(layers, "success")
    exit_code = _sql_evidence_value(layers, "exit_code")
    error_count = _sql_evidence_value(layers, "error_count")
    pending_scalar_refactor = _is_pending_scalar_refactor(layers)
    failed_statuses = {"failed", "failure", "blocked", "error"}
    if (
        not pending_scalar_refactor
        and (
            success is False
            or overall_status in failed_statuses
            or mechanical_status in failed_statuses
            or alias_status in failed_statuses | {"required", "conflict"}
            or isinstance(exit_code, int) and exit_code != 0
            or isinstance(error_count, int) and error_count > 0
        )
    ):
        return {"status": "failed", "errors": []}

    errors: List[str] = []
    passed_statuses = {"passed", "pass", "ok", "success"}
    if not pending_scalar_refactor and success is not True and overall_status not in passed_statuses:
        errors.append("verifier_success_not_proven")
    if mechanical_status not in passed_statuses | {"mechanically_valid"}:
        errors.append("mechanical_status_not_passed")
    if not alias_status:
        errors.append("alias_role_plan_validation_missing")
    elif alias_status not in {"not_needed", "verified"}:
        errors.append("alias_role_plan_validation_not_accepted")

    hashes: Dict[str, str] = {}
    for key in ["original_sha256", "formatted_sha256", "style_contract_sha256"]:
        value = str(_sql_evidence_value(layers, key) or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            errors.append(f"{key}_missing_or_invalid")
        else:
            hashes[key] = value
    verification_id = str(_sql_evidence_value(layers, "verification_id") or "").strip()
    if not verification_id:
        errors.append("verification_id_missing")

    call_data = _json_object_from_text(call.text)
    call_original_sql = call_data.get("original_sql")
    call_formatted_sql = call_data.get("formatted_sql")
    if not isinstance(call_original_sql, str):
        errors.append("original_sql_call_scope_missing")
    elif hashes.get("original_sha256"):
        call_original_hash = hashlib.sha256(call_original_sql.encode("utf-8")).hexdigest()
        if hashes["original_sha256"] != call_original_hash:
            errors.append("original_sha256_mismatch")
        elif not _original_sql_bound_to_session_source(
            records,
            request_index=request_index,
            call_index=call_index,
            original_sql=call_original_sql,
        ):
            errors.append("original_sql_not_bound_to_session_source")
    if not isinstance(call_formatted_sql, str):
        errors.append("formatted_sql_call_scope_missing")
    elif hashes.get("formatted_sha256"):
        call_formatted_hash = hashlib.sha256(call_formatted_sql.encode("utf-8")).hexdigest()
        if hashes["formatted_sha256"] != call_formatted_hash:
            errors.append("formatted_sha256_call_mismatch")
    if final_sql is None:
        errors.append("final_sql_not_exactly_extractable")
    elif hashes.get("formatted_sha256"):
        actual_hash = hashlib.sha256(final_sql.encode("utf-8")).hexdigest()
        if hashes["formatted_sha256"] != actual_hash:
            errors.append("formatted_sha256_mismatch")

    return {
        "status": "unbound" if errors else ("pending" if pending_scalar_refactor else "passed"),
        "errors": errors,
        "verification_id": verification_id,
    }


def _is_pending_scalar_refactor(layers: List[Dict[str, Any]]) -> bool:
    operation = _normalized_evidence_status(_sql_evidence_value(layers, "operation"))
    overall_status = _normalized_evidence_status(_sql_evidence_value(layers, "status"))
    release_status = ""
    scalar_status = ""
    for layer in layers:
        release = layer.get("release_readiness")
        if isinstance(release, dict) and not release_status:
            release_status = _normalized_evidence_status(release.get("status"))
        semantic = layer.get("semantic_refactor_evidence")
        if isinstance(semantic, dict):
            scalar = semantic.get("scalar_function_refactor")
            if isinstance(scalar, dict) and not scalar_status:
                scalar_status = _normalized_evidence_status(scalar.get("status"))
    return (
        operation == "refactor"
        and overall_status == "pending"
        and release_status == "pending"
        and scalar_status == "mechanically_valid"
    )


def _original_sql_bound_to_session_source(
    records: List[SessionTextRecord],
    *,
    request_index: int,
    call_index: int,
    original_sql: str,
) -> bool:
    if not _looks_like_actionable_sql_source(original_sql):
        return False
    latest_user_sources = _latest_user_sql_sources(
        records,
        start_index=request_index,
        end_index=call_index,
    )
    if latest_user_sources:
        return any(source.strip() == original_sql.strip() for source in latest_user_sources)

    for index in range(request_index + 1, call_index):
        call = records[index]
        if not _looks_like_sql_source_artifact_read(call):
            continue
        if _correlated_successful_source_artifact_output(
            records,
            index,
            call_index,
            original_sql,
        ) >= 0:
            return True
    return False


def _original_hash_bound_to_session_source(
    records: List[SessionTextRecord],
    *,
    request_index: int,
    call_index: int,
    original_sha256: str,
) -> bool:
    latest_user_sources = _latest_user_sql_sources(
        records,
        start_index=request_index,
        end_index=call_index,
    )
    if latest_user_sources:
        return any(
            original_sha256 in _sql_text_hash_variants(candidate)
            for candidate in latest_user_sources
        )
    for index in range(request_index, call_index):
        record = records[index]
        if record.payload_type in {"function_call_output", "custom_tool_call_output"}:
            candidates = _extract_actionable_sql_sources(record.text)
        else:
            continue
        if any(original_sha256 in _sql_text_hash_variants(candidate) for candidate in candidates):
            return True
    return False


def _latest_user_sql_sources(
    records: List[SessionTextRecord],
    *,
    start_index: int,
    end_index: int,
) -> List[str]:
    latest: List[str] = []
    for index in range(start_index, end_index):
        if records[index].role != "user":
            continue
        candidates = _extract_actionable_sql_sources(records[index].text)
        if candidates:
            latest = candidates
    return latest


def _sql_text_hash_variants(text: str) -> Set[str]:
    value = str(text or "")
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    trimmed = normalized.rstrip("\n")
    variants = {
        value,
        normalized,
        trimmed,
        trimmed + "\n",
        trimmed.replace("\n", "\r\n") + "\r\n",
    }
    return {hashlib.sha256(item.encode("utf-8")).hexdigest() for item in variants}


def _looks_like_actionable_sql_source(text: str) -> bool:
    return bool(
        re.match(
            r"^\s*(?:with\b|select\b|insert\b|update\b|delete\b|merge\b|exec(?:ute)?\b|"
            r"create\s+(?:or\s+alter\s+)?(?:proc(?:edure)?|function|view)\b)",
            text,
            re.IGNORECASE,
        )
    )


def _looks_like_sql_source_artifact_read(record: SessionTextRecord) -> bool:
    if record.payload_type not in {"function_call", "custom_tool_call"}:
        return False
    lowered = record.text.lower()
    if not re.search(r"\.(?:sql|tsql|txt|srd|sru|srw)\b", lowered):
        return False
    return any(
        marker in lowered
        for marker in ["get-content", "read_file", "read_text", "open_file", "cat ", "type "]
    )


def _correlated_successful_source_artifact_output(
    records: List[SessionTextRecord],
    call_index: int,
    verifier_call_index: int,
    original_sql: str,
) -> int:
    call = records[call_index]
    for index in range(call_index + 1, verifier_call_index):
        record = records[index]
        if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
            continue
        if call.call_id and record.call_id != call.call_id:
            continue
        if not call.call_id and record.call_id:
            return -1
        return (
            index
            if _successful_tool_output_text(record.text)
            and _has_exact_actionable_sql_source(record.text, original_sql)
            else -1
        )
    return -1


def _has_exact_actionable_sql_source(text: str, original_sql: str) -> bool:
    target = str(original_sql or "").strip()
    if not target:
        return False
    return any(candidate.strip() == target for candidate in _extract_actionable_sql_sources(text))


def _extract_actionable_sql_sources(text: str) -> List[str]:
    source = str(text or "")
    candidates: List[str] = []
    fenced_pattern = re.compile(
        r"^[ \t]*```[ \t]*(?:sql|tsql|t-sql)[ \t]*\r?\n(.*?)^[ \t]*```[ \t]*$",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    inline_pattern = re.compile(
        r"(?ims)(^\s*(?:with\b|select\b|insert\b|update\b|delete\b|merge\b|exec(?:ute)?\b|"
        r"create\s+(?:or\s+alter\s+)?(?:proc(?:edure)?|function|view)\b)"
        r"[\s\S]*?(?:;(?=\s*(?:$|```))|(?=\r?\n\s*(?:format|rewrite|convert|clean|fix|please|"
        r"make|generate|draft|output|return|show|check|review|do\s+i\s+need|what|why|can\s+you|"
        r"is\s+this|should\s+i|how)\b)|$))"
    )

    for match in fenced_pattern.finditer(source):
        candidate = match.group(1).strip()
        if candidate:
            candidates.append(candidate)
    for match in inline_pattern.finditer(source):
        candidate = match.group(1).strip()
        if candidate:
            candidates.append(candidate)

    unique_candidates: List[str] = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def _sql_verifier_data_layers(text: str) -> List[Dict[str, Any]]:
    root = _json_object_from_text(text)
    if not root:
        return []
    layers: List[Dict[str, Any]] = []

    def collect(value: Dict[str, Any], depth: int = 0) -> None:
        if depth > 3:
            return
        layers.append(value)
        for key in ["metadata", "evidence", "verification"]:
            nested = value.get(key)
            if isinstance(nested, dict):
                collect(nested, depth + 1)
        stdout = value.get("stdout")
        if isinstance(stdout, str):
            nested_stdout = _json_object_from_text(stdout)
            if nested_stdout:
                collect(nested_stdout, depth + 1)

    collect(root)
    return layers


def _sql_evidence_value(layers: List[Dict[str, Any]], key: str) -> Any:
    for layer in layers:
        if key in layer:
            return layer.get(key)
    return None


def _structured_evidence_status(layers: List[Dict[str, Any]], key: str, flat_key: str) -> str:
    flat_value = _sql_evidence_value(layers, flat_key)
    if flat_value not in {None, ""}:
        return _normalized_evidence_status(flat_value)
    for layer in layers:
        value = layer.get(key)
        if isinstance(value, dict):
            return _normalized_evidence_status(value.get("status"))
    return ""


def _alias_role_plan_validation_status(layers: List[Dict[str, Any]]) -> str:
    for layer in layers:
        value = layer.get("alias_role_plan_validation")
        if isinstance(value, dict):
            return _normalized_evidence_status(value.get("status"))
    return ""


def _normalized_evidence_status(value: Any) -> str:
    if value is True:
        return "passed"
    if value is False:
        return "failed"
    return str(value or "").strip().lower()


def _extract_actionable_sql(record: SessionTextRecord, action_kind: str) -> str | None:
    if action_kind == "db_write":
        data = _json_object_from_text(record.text)
        for key in ["query", "sql", "statement"]:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    if _markdown_fenced_block_count(record.text) != 1:
        return None
    pattern = re.compile(
        r"^[ \t]*```[ \t]*(?:sql|tsql|t-sql)[ \t]*\r?\n(.*?)^[ \t]*```[ \t]*$",
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    blocks = [match.group(1) for match in pattern.finditer(record.text)]
    if len(blocks) != 1:
        return None
    sql = blocks[0]
    if sql.endswith("\r\n"):
        return sql[:-2]
    if sql.endswith("\n"):
        return sql[:-1]
    return sql


def _markdown_fenced_block_count(text: str) -> int:
    active_marker = ""
    count = 0
    pattern = re.compile(r"^[ ]{0,3}(?P<marker>`{3,}|~{3,})(?P<info>.*)$")
    for line in str(text or "").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        marker = match.group("marker")
        info = match.group("info").strip()
        if not active_marker:
            active_marker = marker
            count += 1
            continue
        if marker[0] == active_marker[0] and len(marker) >= len(active_marker) and not info:
            active_marker = ""
    return count


def _append_unique_text(items: List[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _sql_style_harness_acceptance(
    sql_audit: Dict[str, Any],
    *,
    required: bool,
    default: Dict[str, Any],
) -> Dict[str, Any]:
    if not required or not sql_audit.get("required"):
        return default
    required_outputs = list(ACCEPTANCE_OUTPUT_MARKERS.get("sql-formatting-style-harness", {}).keys())
    if sql_audit.get("verified_before_output"):
        return {
            "status": "passed",
            "required_outputs": required_outputs,
            "satisfied_outputs": required_outputs,
            "missing_outputs": [],
        }
    if sql_audit.get("verifier_failed"):
        return {
            "status": "blocked",
            "required_outputs": required_outputs,
            "satisfied_outputs": [],
            "missing_outputs": required_outputs,
        }
    if sql_audit.get("verifier_pending"):
        return {
            "status": "blocked",
            "required_outputs": required_outputs,
            "satisfied_outputs": [],
            "missing_outputs": required_outputs,
        }
    if sql_audit.get("verifier_executed"):
        return {
            "status": "missing_outputs",
            "required_outputs": required_outputs,
            "satisfied_outputs": [],
            "missing_outputs": required_outputs,
        }
    return default


def _has_sql_formatting_route_evidence(lowered: str) -> bool:
    if not ("sql-formatting" in lowered or "sql_formatting" in lowered or "sql formatting" in lowered):
        return False
    data = _json_object_from_text(lowered)
    if data:
        plugin_route = data.get("plugin_route", {}) if isinstance(data.get("plugin_route"), dict) else {}
        if not plugin_route and ("controller" in data or "assistants" in data):
            plugin_route = data
        if plugin_route:
            if _sql_formatting_role(plugin_route.get("controller")):
                return True
            assistants = plugin_route.get("assistants", []) or []
            if isinstance(assistants, list) and any(_sql_formatting_role(item) for item in assistants):
                return True
            return False
    return any(
        marker in lowered
        for marker in [
            '"controller": "sql-formatting"',
            "'controller': 'sql-formatting'",
            "controller=sql-formatting",
            "specialist_trigger:sql-formatting:sql_formatting",
            "explicit_user_request:sql-formatting",
        ]
    )


def _sql_formatting_role(value: Any) -> bool:
    if isinstance(value, str):
        return value == "sql-formatting"
    if not isinstance(value, dict):
        return False
    provider_id = str(value.get("provider_id", "") or value.get("id", "") or value.get("name", ""))
    capability = str(value.get("capability", ""))
    return provider_id == "sql-formatting" or capability == "sql_formatting"


def _sql_provider_role_evidence(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    provider_id = str(value.get("provider_id", "") or value.get("id", "") or "").strip()
    capability = str(value.get("capability", "") or "").strip()
    if provider_id != "sql-formatting" and capability != "sql_formatting":
        return {}
    metadata = value.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    provider_path = str(metadata.get("path", "") or "").strip()
    provider_source = str(metadata.get("source", "") or "").strip()
    compatibility = str(metadata.get("compatibility", "compatible") or "").strip().lower()
    if (
        not provider_path
        or provider_source not in {"host-local-skill", "packaged-kh-skill"}
        or compatibility not in {"compatible", "supported", "verified"}
    ):
        return {}
    return {
        "provider_id": provider_id or "sql-formatting",
        "provider_path": provider_path,
        "provider_source": provider_source,
    }


def _correlated_sql_provider_selections(
    records: Sequence[SessionTextRecord],
    *,
    lower_bound: int,
    upper_bound: int,
) -> Sequence[Dict[str, Any]]:
    if not isinstance(records, DiskBackedSessionTextRecords):
        raise RuntimeError("SQL provider selection requires indexed text facts")
    events = records._events
    events._db.execute("DELETE FROM sql_provider_selections")
    for (
        call_index,
        call,
        output_index,
        record,
        call_payload,
        output_payload,
    ) in records.iter_front_door_pairs(
        lower_bound=max(-1, lower_bound),
        upper_bound=min(len(records), upper_bound),
    ):
        if not _record_invokes_front_door(call):
            continue
        if not _front_door_output_succeeded(output_payload, call_payload):
            continue
        data = _front_door_json(record.text)
        if not _has_normalized_front_door_receipt(data):
            continue
        if str(data.get("front_door_status", "") or "").strip().lower() != "ok":
            continue
        route = data.get("plugin_route")
        if not isinstance(route, dict):
            continue
        matched_role: Dict[str, str] = {}
        matched_count = 0
        role_values: Iterable[Any] = (route.get("controller"),)
        assistants = route.get("assistants")
        if isinstance(assistants, list):
            role_values = (*role_values, *assistants)
        for role in role_values:
            role_evidence = _sql_provider_role_evidence(role)
            if not role_evidence:
                continue
            matched_count += 1
            if matched_count == 1:
                matched_role = role_evidence
            if matched_count > 1:
                break
        if matched_count != 1:
            continue
        provenance_details = validate_sql_provider_selection_runtime_receipt(data)
        raw_data = _json_object_from_text(record.text)
        if not _valid_host_front_door_provenance(
            call_payload,
            output_payload,
            raw_data,
            duplicate_boundaries=DiskBackedDuplicateFactKeys(events, "boundary"),
            duplicate_packet_hashes=DiskBackedDuplicateFactKeys(events, "packet_hash"),
        ):
            provenance_details.append("front_door_runtime_provenance_invalid")
        runtime_receipt = data.get("provider_selection_receipt")
        receipt_id = (
            runtime_receipt.get("provider_selection_receipt_id")
            if isinstance(runtime_receipt, dict)
            else None
        )
        normalized_receipt_id = receipt_id if type(receipt_id) is str else ""
        if normalized_receipt_id and events._db.execute(
            """
            SELECT 1 FROM sql_provider_selections
            WHERE receipt_id = ? AND output_record_seq < ?
            LIMIT 1
            """,
            (normalized_receipt_id, output_index),
        ).fetchone():
            provenance_details.append("provider_selection_runtime_receipt_replayed")
        provenance_errors = []
        if provenance_details:
            provenance_errors.append("front_door_provider_selection_provenance_invalid")
            if "provider_selection_runtime_receipt_replayed" in provenance_details:
                provenance_errors.append("provider_selection_runtime_receipt_replayed")
        events._db.execute(
            """
            INSERT INTO sql_provider_selections (
                output_record_seq, call_record_seq, provider_id,
                provider_path, provider_source, selection_sha256,
                receipt_id, provenance_valid, provenance_errors_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                output_index,
                call_index,
                matched_role["provider_id"],
                matched_role["provider_path"],
                matched_role["provider_source"],
                sql_provider_selection_sha256(data),
                normalized_receipt_id,
                int(not provenance_details),
                _canonical_json(provenance_errors),
            ),
        )
    return DiskBackedSqlProviderSelections(events)


def _sql_runtime_receipt_seen_before(
    records: Sequence[SessionTextRecord],
    *,
    output_index: int,
    receipt_id: str,
    selection: bool,
) -> bool:
    if isinstance(records, DiskBackedSessionTextRecords):
        receipt_kind = "selection" if selection else "binding"
        return records._events._db.execute(
            """
            SELECT 1
            FROM sql_runtime_receipt_facts
            WHERE receipt_kind = ? AND receipt_id = ? AND record_seq < ?
            LIMIT 1
            """,
            (receipt_kind, str(receipt_id), int(output_index)),
        ).fetchone() is not None
    for index in range(0, min(output_index, len(records))):
        record = records[index]
        if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
            continue
        data = _front_door_json(record.text) if selection else _sql_final_binding_receipt(record.text)
        receipt = data.get(
            "provider_selection_receipt" if selection else "runtime_receipt"
        )
        if not isinstance(receipt, dict):
            continue
        key = "provider_selection_receipt_id" if selection else "receipt_id"
        if type(receipt.get(key)) is str and receipt[key] == receipt_id:
            return True
    return False


def _record_invokes_front_door(record: SessionTextRecord) -> bool:
    payload = {
        "type": record.payload_type,
        "name": record.name,
        "arguments": record.arguments,
    }
    return _is_front_door_runtime_command(
        payload,
        f"{record.name} {record.arguments}".lower(),
    )


def _is_sql_follow_up_request(text: str) -> bool:
    lowered = str(text or "").lower()
    if looks_like_sql_output_request(lowered):
        return True
    if _is_sql_layout_correction(lowered):
        return True
    return any(
        marker in lowered
        for marker in [
            " sql",
            "sql ",
            "query",
            "join",
            "where",
            "group by",
            "order by",
            "alias",
            "format",
            "recheck",
            "correction",
            "쿼리",
            "별칭",
        ]
    )


def _immediate_contextual_sql_correction_index(
    records: Sequence[SessionTextRecord],
    action_index: int,
) -> int:
    for index in range(action_index + 1, len(records)):
        record = records[index]
        if record.role == "user" and not _is_passive_text(record.text):
            return index if _is_short_contextual_sql_correction(record.text) else -1
        if (
            record.role == "assistant"
            and record.payload_type in {"message", "agent_message"}
            and not _is_passive_text(record.text)
        ):
            return -1
    return -1


def _is_short_contextual_sql_correction(text: str) -> bool:
    value = str(text or "").strip().casefold()
    if not value or len(value) > 80 or "\n" in value or "\r" in value:
        return False
    if _is_sql_layout_correction(value):
        return True
    value = re.sub(r"['’]", "", value)
    value = re.sub(r"[^0-9a-z가-힣]+", " ", value).strip()
    return value in {
        "no thats wrong",
        "that is not what i asked",
        "try again",
        "아니요 틀렸습니다",
        "제가 요청한 내용이 아닙니다",
        "다시 해주세요",
    }


def _is_sql_layout_correction(text: str) -> bool:
    value = str(text or "").strip().casefold()
    if not value:
        return False
    has_sql_target = bool(
        re.search(r"\b(?:join|where|alias)\b", value)
        or (re.search(r"\bon\b", value) and re.search(r"\band\b", value))
        or any(marker in value for marker in ["별칭", "조인", "온절", "조건절", "조건"])
    )
    has_correction_intent = any(
        marker in value
        for marker in [
            "position",
            "align",
            "indent",
            "wrong",
            "incorrect",
            "fix",
            "again",
            "위치",
            "정렬",
            "들여쓰기",
            "틀",
            "잘못",
            "못",
            "고쳐",
            "수정",
            "다시",
            "잡",
        ]
    )
    return has_sql_target and has_correction_intent


def _looks_like_sql_answer(lowered: str) -> bool:
    if "```sql" in lowered:
        return True
    return bool(SQL_ANSWER_PATTERN.search(lowered))


def _looks_like_sql_db_write(record: SessionTextRecord) -> bool:
    if record.payload_type not in {"function_call", "custom_tool_call"}:
        return False
    lowered = record.text.lower()
    if not any(marker in lowered for marker in ["mssql_run_sql_query", "run_sql_query", "execute_sql", "sql_query"]):
        return False
    write_patterns = [
        r"\bcreate\s+(?:or\s+alter\s+)?(?:procedure|proc|function|table|view|trigger)\b",
        r"\balter\s+(?:procedure|proc|function|table|view|trigger)\b",
        r"\bdrop\s+(?:procedure|proc|function|table|view|trigger|index|database)\b",
        r"\btruncate\s+table\b",
        r"\binsert\s+into\b",
        r"\bupdate\s+[\[\]a-z0-9_.#]+\s+set\b",
        r"\bdelete\s+from\b",
        r"\bmerge\s+[\[\]a-z0-9_.#]+\b",
    ]
    return any(re.search(pattern, lowered) for pattern in write_patterns)


def _is_sql_requirement_record(
    record: SessionTextRecord,
    *,
    lowered: str | None = None,
) -> bool:
    if _is_passive_text(record.text):
        return False
    if _is_synthetic_context_message(record.text):
        return False
    if record.sql_requirement is not None:
        return bool(record.sql_requirement)
    if record.payload_type not in {"message", "agent_message", "task_complete"}:
        return False
    if record.payload_type == "message" and record.role in {"developer", "system"}:
        return False
    lowered = record.text.lower() if lowered is None else lowered
    if _looks_like_front_door_runtime_output(lowered):
        return False
    if record.payload_type == "message":
        if record.role == "user":
            return looks_like_sql_output_request(lowered)
        if record.role == "assistant":
            return _looks_like_sql_answer(lowered)
        return False
    if record.payload_type in {"agent_message", "task_complete"}:
        return _looks_like_sql_answer(lowered)
    return False


def _brainstorming_target_inspection_issues(path: Path) -> List[Dict[str, Any]]:
    events = _session_payload_events(path)
    active_target: Path | None = None
    gate_active = False
    samples: List[str] = []

    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("brainstorm target audit requires indexed event facts")
    for _event_seq, payload in events.iter_payloads(
        payload_types=(
            "message",
            "agent_message",
            "task_complete",
            "function_call",
            "custom_tool_call",
            "function_call_output",
            "custom_tool_call_output",
        )
    ):
        payload_type = str(payload.get("type", ""))
        text = _payload_text(payload)
        lowered = text.lower()

        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            if _is_synthetic_context_message(text):
                continue
            paths = _extract_windows_paths(text)
            if paths:
                active_target = Path(paths[0])
            continue

        data = _front_door_json(_strip_passive_prefix(text))
        if data:
            gate = data.get("execution_gate", {}) or {}
            gate_status = str(gate.get("status", ""))
            immediate = {str(item) for item in data.get("immediate_next_skills", []) or []}
            recommended = {str(item) for item in data.get("recommended_skills", []) or []}
            selected = {str(item) for item in data.get("selected_not_executed_skills", []) or []}
            if (
                gate_status == "blocked_until_brainstorming_handoff"
                or (
                    gate.get("can_execute") is False
                    and "brainstorming-harness" in immediate | recommended | selected
                )
            ):
                gate_active = True
            continue

        if not gate_active:
            continue
        if not _passive_reference(lowered) and _has_brainstorm_handoff_evidence(lowered):
            gate_active = False
            continue
        if payload_type not in {"function_call", "custom_tool_call"}:
            continue
        sample = (
            _target_folder_inspection_during_brainstorm_sample(active_target, text)
            if active_target is not None
            else _blocked_path_inspection_during_brainstorm_sample(text)
        )
        if sample:
            samples.append(sample)
            if len(samples) >= 3:
                break

    if not samples:
        return []
    return [
        {
            "skill": "brainstorming-harness",
            "status": "target_folder_inspection_before_brainstorm_handoff",
            "severity": "P1",
            "reason": (
                "Front-door selected brainstorming and kept execution closed, but the session inspected a target "
                "or filesystem path before BrainstormSession/handoff evidence existed."
            ),
            "action": (
                "For `blocked_until_brainstorming_handoff`, produce the visible domain-first brainstorm first. "
                "Do not run Test-Path, Get-ChildItem, rg, Get-Content, target write preflight, or source reads "
                "against the target path until the brainstorm handoff/spec and separate execution approval exist."
            ),
            "samples": samples,
        }
    ]


def _has_brainstorm_handoff_evidence(lowered: str) -> bool:
    return any(
        marker in lowered
        for marker in [
            "brainstorm_handoff",
            "brainstormsession",
            "validate_brainstorm_session",
            "build_architect_handoff",
            ".kh/brainstorm",
            "docs/kh/handoffs",
        ]
    )


def _target_folder_inspection_during_brainstorm_sample(target: Path, text: str) -> str:
    lowered = text.lower()
    if not any(marker in lowered for marker in ["get-childitem", "test-path", "get-content", "select-string", "rg "]):
        return ""
    target = _normalize_path(target)
    for raw_path in _extract_windows_paths(text):
        candidate = _normalize_path(Path(raw_path))
        if candidate == target or _path_is_relative_to(candidate, target):
            return _short(f"target folder inspection before brainstorm handoff: {raw_path}")
    return ""


def _blocked_path_inspection_during_brainstorm_sample(text: str) -> str:
    lowered = text.lower()
    if not any(marker in lowered for marker in ["get-childitem", "test-path", "get-content", "select-string", "rg "]):
        return ""
    for raw_path in _extract_windows_paths(text):
        normalized = raw_path.lower()
        if "\\skills\\" in normalized or "\\.codex\\plugins\\cache\\" in normalized:
            continue
        return _short(f"path inspection before brainstorm handoff: {raw_path}")
    if any(marker in lowered for marker in ["get-childitem", "test-path"]):
        return _short(f"path inspection before brainstorm handoff: {text}")
    return ""


def _brainstorm_option_choice_execution_issues(path: Path) -> List[Dict[str, Any]]:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("brainstorm option audit requires indexed event facts")
    choice_index = -1
    choice_text = ""
    for index, payload in events.iter_payloads(
        payload_types=("message",),
        roles=("user",),
    ):
        text = _payload_text(payload)
        lowered = text.lower()
        if _is_direction_choice_without_execution_text(lowered):
            choice_index = index
            choice_text = text
            break
    if choice_index < 0:
        return []

    issues: List[Dict[str, Any]] = []
    scope_lock_samples: List[str] = []
    samples: List[str] = []
    for _event_seq, payload in events.iter_payloads(
        payload_types=(
            "message",
            "agent_message",
            "task_complete",
            "function_call",
            "custom_tool_call",
        ),
        start=choice_index + 1,
    ):
        payload_type = str(payload.get("type", ""))
        if payload_type in {"message", "agent_message", "task_complete"}:
            text = _payload_text(payload)
            markers = _option_choice_scope_lock_markers(text)
            if markers:
                scope_lock_samples.append(_short(f"{', '.join(markers)}: {text}", 420))
                if len(scope_lock_samples) >= 3:
                    continue
        if payload_type not in {"function_call", "custom_tool_call"}:
            continue
        name = str(payload.get("name", ""))
        text = _payload_text(payload)
        lowered = text.lower()
        if _looks_like_front_door_prompt_bootstrap(lowered):
            continue
        if name in {"apply_patch", "imagegen"} or "apply_patch" in lowered:
            samples.append(_short(text))
        elif name == "shell_command" and any(
            marker in lowered
            for marker in [
                "new-item",
                "copy-item",
                "move-item",
                "set-content",
                "out-file",
                "python -m http.server",
                "node --check",
            ]
        ):
            samples.append(_short(text))
        if len(samples) >= 3:
            break

    if scope_lock_samples:
        issues.append(
            {
                "skill": "brainstorming-harness",
                "status": "option_choice_treated_as_scope_approval",
                "severity": "P0",
                "reason": (
                    "The user selected a brainstorm option, but the next agent response locked implementation "
                    "scope or asked for file-generation approval before a reviewed BrainstormSession/handoff existed."
                ),
                "action": (
                    "After an option choice, record the direction only and ask the next focused design/spec question. "
                    "Do not announce an implementation scope, storage model, KPI/table/file set, stack, target-folder "
                    "creation, QA, or deliverable generation until the reviewed handoff/spec and separate execution "
                    "approval exist."
                ),
                "choice": _short(choice_text, 220),
                "samples": scope_lock_samples,
            }
        )

    if samples:
        issues.append({
            "skill": "brainstorming-harness",
            "status": "option_choice_treated_as_execution_approval",
            "severity": "P0",
            "reason": (
                "The user selected a brainstorm option, but the session treated that direction choice as "
                "permission to implement or generate files. Superpowers-style brainstorming requires design/spec "
                "review before planning or implementation."
            ),
            "action": (
                "After an option choice, ask the next focused design/spec question and preserve a reviewed "
                "BrainstormSession/handoff. Do not scaffold, write files, verify, or generate deliverables until "
                "the user separately approves implementation after the design/spec review gate."
            ),
            "choice": _short(choice_text, 220),
            "samples": samples,
        })

    return issues


def _option_choice_scope_lock_markers(text: str) -> List[str]:
    if not text:
        return []
    lowered = text.lower()
    negations = [
        "not implementation scope",
        "not final implementation scope",
        "do not lock implementation scope",
        "\uad6c\ud604 \ubc94\uc704\ub97c \ud655\uc815\ud558\uc9c0",
        "\uad6c\ud604 \ubc94\uc704\ub294 \uc544\uc9c1 \ud655\uc815",
        "\uc544\uc9c1 \uad6c\ud604\ud558\uc9c0",
        "\uc544\uc9c1 \ud30c\uc77c\uc744 \uc0dd\uc131\ud558\uc9c0",
    ]
    if any(marker in lowered for marker in negations):
        return []
    marker_groups = {
        "implementation_scope_locked": [
            "implementation scope is",
            "scope for implementation",
            "i will build the following",
            "we will build the following",
            "\uad6c\ud604 \ubc94\uc704\ub294 \uc774\ub807\uac8c \uc7a1\uaca0\uc2b5\ub2c8\ub2e4",
            "\uad6c\ud604 \ubc94\uc704\ub294 \ub2e4\uc74c\uacfc \uac19\uc2b5\ub2c8\ub2e4",
            "\uad6c\ud604 \ubc94\uc704\ub294",
        ],
        "file_generation_approval_after_option": [
            "create the files",
            "generate files",
            "create a new folder",
            "\ud30c\uc77c\uc744 \uc0dd\uc131\ud574\ub3c4 \ub420\uae4c\uc694",
            "\ud654\uba74 \ud30c\uc77c\uc744 \uc0dd\uc131",
            "\uc0c8 \ud3f4\ub354\ub97c \ub9cc\ub4e4\uace0",
            "\ud574\ub2f9 \uacbd\ub85c\uc5d0 \uc0c8 \ud3f4\ub354",
        ],
        "implementation_detail_locked": [
            "top kpi",
            "kpi:",
            "storage method",
            "localstorage",
            "\uc0c1\ub2e8 kpi",
            "\uc800\uc7a5 \ubc29\uc2dd",
            "\ud604\uc7ac\uace0 \ud14c\uc774\ube14",
            "\uc785\ucd9c\uace0 \uc785\ub825",
            "\uc785\ucd9c\uace0 \uc774\ub825",
        ],
        "finalized_direction_as_agent_decision": [
            "\ud655\uc815\ud588\uc2b5\ub2c8\ub2e4",
            "is confirmed",
            "has been finalized",
        ],
    }
    matched = [
        name
        for name, markers in marker_groups.items()
        if any(marker in lowered for marker in markers)
    ]
    if "implementation_detail_locked" in matched and "finalized_direction_as_agent_decision" not in matched:
        if not any(marker in lowered for marker in ["\uad6c\ud604", "implementation", "build", "develop"]):
            matched.remove("implementation_detail_locked")
    return matched


def _is_direction_choice_without_execution_text(lowered: str) -> bool:
    if not lowered:
        return False
    choice_markers = [
        "option 1",
        "option 2",
        "option 3",
        "go with option",
        "proceed with option",
        "continue with option",
        "1\ubc88",
        "2\ubc88",
        "3\ubc88",
        "\ub2e8\uc21c \uc7ac\uace0 \uc6d0\uc7a5\ud615",
        "\ub2e8\uc21c \uc218\ubd88\uc7a5\ud615",
        "\uc704\uce58 \uad00\ub9ac\ud615",
        "\ub85c\ud2b8/\uc2dc\ub9ac\uc5bc",
    ]
    execution_markers = [
        "implement",
        "implementation",
        "build",
        "develop",
        "create files",
        "generate files",
        "write files",
        "write code",
        "scaffold",
        "\uad6c\ud604",
        "\uac1c\ubc1c",
        "\ud30c\uc77c \uc0dd\uc131",
        "\ucf54\ub4dc \uc791\uc131",
        "\uc2a4\uce90\ud3f4\ub4dc",
    ]
    return any(marker in lowered for marker in choice_markers) and not any(
        marker in lowered for marker in execution_markers
    )


def _first_visible_brainstorm_response(path: Path) -> str:
    user_messages = 0
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("brainstorm response audit requires indexed event facts")
    for _event_seq, payload in events.iter_payloads(
        payload_types=("message", "agent_message", "task_complete")
    ):
        payload_type = str(payload.get("type", ""))
        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            if _is_synthetic_context_message(_payload_text(payload)):
                continue
            user_messages += 1
            if user_messages > 1:
                break
            continue
        if user_messages < 1:
            continue
        if payload_type == "message" and str(payload.get("role", "")).lower() in {"developer", "system"}:
            continue
        if payload_type not in {"message", "agent_message", "task_complete"}:
            continue
        text = _payload_text(payload)
        lowered = text.lower()
        if not text or _is_passive_text(text) or _looks_like_front_door_runtime_output(lowered):
            continue
        if "::archive" in lowered:
            continue
        has_option_shape = (
            ("1." in text and "2." in text)
            or any(marker in lowered for marker in ["option", "options", "alternatives", "\uc120\ud0dd\uc9c0", "\ub300\uc548"])
        )
        has_decision_shape = any(
            marker in lowered
            for marker in [
                "recommend",
                "\ucd94\ucc9c",
                "approval",
                "\uc2b9\uc778",
                "which",
                "choose",
                "confirm",
                "\uc5b4\ub290",
                "\uc120\ud0dd",
                "\ud655\uc815",
                "\uac08\uae4c\uc694",
            ]
        )
        if has_option_shape and has_decision_shape:
            return text
    return ""


def _is_synthetic_context_message(text: str) -> bool:
    stripped = (text or "").lstrip().lower()
    wrapper_prefixes = (
        "<app-context>",
        "<apps_instructions>",
        "<developer_context>",
        "<environment_context>",
        "<goal_context>",
        "<permissions instructions>",
        "<permissions_instructions>",
        "<plugins_instructions>",
        "<recommended_plugins>",
        "<skills_instructions>",
        "<system_context>",
    )
    return (
        stripped.startswith(wrapper_prefixes)
        or stripped.startswith("# codex desktop context")
        or (
            stripped.startswith("## memory")
            and (
                "memory_summary" in stripped
                or "you have access to a memory folder" in stripped
            )
        )
        or (
            stripped.startswith(("## skills", "### available skills"))
            and ("### skill roots" in stripped or "skills_instructions" in stripped)
        )
        or _is_untrusted_assessment_transcript(stripped)
    )


def _is_untrusted_assessment_transcript(lowered: str) -> bool:
    return (
        (
            "treat the transcript, tool call arguments, tool results" in lowered
            or "treat the transcript delta, tool call arguments, tool results" in lowered
        )
        and "untrusted evidence" in lowered
        and (">>> transcript start" in lowered or ">>> transcript delta start" in lowered)
    )


def _brainstorm_response_missing_markers(text: str) -> List[str]:
    if not text:
        return []
    lowered = text.lower()
    marker_groups = {
        "objective_operator": [
            "objective",
            "operator",
            "target user",
            "audience",
            "\ubaa9\ud45c",
            "\ub2f4\ub2f9\uc790",
            "\uad00\ub9ac\uc790",
            "\uc0ac\uc6a9\uc790",
            "\uc6b4\uc601\uc790",
        ],
        "workflow_boundary": [
            "workflow",
            "boundary",
            "process",
            "inbound",
            "outbound",
            "\uc5c5\ubb34",
            "\ud504\ub85c\uc138\uc2a4",
            "\uc785\uace0",
            "\ucd9c\uace0",
            "\uc870\uc815",
            "\uc774\ub3d9",
        ],
        "success_constraints": [
            "success criteria",
            "constraint",
            "non-goal",
            "\uc131\uacf5",
            "\uc81c\uc57d",
            "\ube44\ubc94\uc704",
            "\uc131\uacf5 \uae30\uc900",
            "\uc81c\uc57d\uc0ac\ud56d",
        ],
        "operating_options_tradeoffs": [
            "tradeoff",
            "alternative",
            "option",
            "pros",
            "cons",
            "\uc120\ud0dd\uc9c0",
            "\uc7a5\ub2e8\uc810",
            "\ube44\uad50",
            "\ub300\uc548",
        ],
        "required_records_data": [
            "required data",
            "required records",
            "record",
            "data fields",
            "item code",
            "quantity",
            "transaction type",
            "safety stock",
            "\ud544\uc218 \ub370\uc774\ud130",
            "\ud544\uc694 \ub370\uc774\ud130",
            "\ud544\uc218 \uae30\ub85d",
            "\uae30\ub85d \ud56d\ubaa9",
            "\ub370\uc774\ud130 \ud56d\ubaa9",
            "\uc785\ub825 \ub370\uc774\ud130",
        ],
        "recommendation": ["recommend", "recommended", "\ucd94\ucc9c"],
        "open_questions": [
            "open question",
            "unresolved",
            "need to know",
            "needs confirmation",
            "\uc624\ud508 \uc9c8\ubb38",
            "\ubbf8\ud655\uc815",
            "\ud655\uc778 \ud544\uc694",
            "\ud655\uc778\ud574\uc57c",
            "\uc9c8\ubb38",
            "\uc815\ud574\uc57c",
        ],
        "approval_question": ["approval", "approve", "proceed", "\uc2b9\uc778", "\uc9c4\ud589\ud574\ub3c4"],
    }
    missing = [
        name
        for name, markers in marker_groups.items()
        if not any(marker in lowered for marker in markers)
    ]
    return missing


def _brainstorm_unilateral_decision_markers(text: str) -> List[str]:
    if not text:
        return []
    lowered = text.lower()
    markers = [
        "\ub85c \uac00\uaca0\uc2b5\ub2c8\ub2e4",
        "\uc73c\ub85c \uac00\uaca0\uc2b5\ub2c8\ub2e4",
        "\uae30\uc900\uc73c\ub85c \ub9cc\ub4e4\uaca0\uc2b5\ub2c8\ub2e4",
        "\uae30\uc900\uc73c\ub85c \uac1c\ubc1c\ud558\uaca0\uc2b5\ub2c8\ub2e4",
        "\ubc29\ud5a5\uc73c\ub85c \uc7a1\uaca0\uc2b5\ub2c8\ub2e4",
        "\uc0c8\ub85c \ub9cc\ub4e4\uc5b4\uc11c \uc9c4\ud589",
        "\ub9cc\ub4e4\uace0 \uad6c\ud604\ud574\ub3c4",
        "\ubc14\ub85c \uad6c\ud604",
        "\uc2b9\uc778\ud574\uc8fc\uc2dc\uba74",
        "\ud30c\uc77c\uc744 \uc0dd\uc131",
        "\ud654\uba74 \ud30c\uc77c\uc744 \uc0dd\uc131",
        "\uc0dd\uc131\ud574\uc11c \uac1c\ubc1c",
        "\uc0dd\uc131\ud558\uace0 \uac1c\ubc1c",
        "\uac1c\ubc1c\ud558\uaca0\uc2b5\ub2c8\ub2e4",
        "\uad6c\ud604\ud558\uaca0\uc2b5\ub2c8\ub2e4",
        "\uc791\uc5c5\uc744 \uc2dc\uc791",
        "\uac1c\ubc1c\uc744 \uc2dc\uc791",
        "i will go with",
        "i'll go with",
        "we will go with",
        "i will use",
        "we will use",
        "i will build",
        "we will build",
        "if you approve, i will create",
        "if approved, i will create",
        "if you approve, i will implement",
        "if approved, i will implement",
        "i can implement now",
        "start implementation",
        "begin implementation",
        "create the files",
        "generate files",
    ]
    matched = [marker for marker in markers if marker in lowered]
    execution_approval_markers = [
        "\uc2b9\uc778\ud574\uc8fc\uc2dc\uba74",
        "\uc2b9\uc778\ud574 \uc8fc\uc2dc\uba74",
        "\ub3d9\uc758\ud574\uc8fc\uc2dc\uba74",
        "\ub3d9\uc758\ud574 \uc8fc\uc2dc\uba74",
        "\ucd94\ucc9c\uc548\uc5d0 \ub3d9\uc758",
        "if you approve",
        "if approved",
        "once approved",
        "when you approve",
    ]
    execution_action_markers = [
        "\ubc14\ub85c \uad6c\ud604",
        "\uad6c\ud604\ud574\ub3c4 \ub420\uae4c\uc694",
        "\uac1c\ubc1c\ud574\ub3c4 \ub420\uae4c\uc694",
        "\uac1c\ubc1c\ud558\uaca0\uc2b5\ub2c8\ub2e4",
        "\uad6c\ud604\ud558\uaca0\uc2b5\ub2c8\ub2e4",
        "\ud30c\uc77c\uc744 \uc0dd\uc131",
        "\ud654\uba74 \ud30c\uc77c",
        "\uc791\uc5c5\uc744 \uc2dc\uc791",
        "\uac1c\ubc1c\uc744 \uc2dc\uc791",
        "implement now",
        "start implementation",
        "begin implementation",
        "create the files",
        "generate files",
    ]
    if any(marker in lowered for marker in execution_approval_markers) and any(
        marker in lowered for marker in execution_action_markers
    ):
        matched.append("premature_execution_approval_question")
    tech_stack_markers = [
        "html + css + javascript",
        "html/css/js",
        "react",
        "winforms",
        "database",
        "db ",
        "\uae30\uc220\uc2a4\ud0dd",
    ]
    approval_markers = ["\uad6c\ud604\ud574\ub3c4 \ub420\uae4c\uc694", "approve", "approval", "\uc2b9\uc778"]
    if any(marker in lowered for marker in tech_stack_markers) and any(
        marker in lowered for marker in approval_markers
    ):
        matched.append("premature_implementation_stack_choice")
    return matched


_CLAIM_TOKEN = r"(?:`[^`\r\n]+`|\"[^\"\r\n]+\"|'[^'\r\n]+'|[A-Za-z][A-Za-z0-9_.-]{2,})"


def _normalize_claim_token(raw: str) -> str:
    value = str(raw or "").strip().strip("`\"'").strip().lower()
    if not value or len(value) > 100:
        return ""
    if value in {
        "assumption",
        "behavior",
        "constant",
        "field",
        "invalid",
        "requirement",
        "value",
    }:
        return ""
    decorated = str(raw or "").strip().startswith(("`", "\"", "'"))
    if not decorated and not any(marker in value for marker in ["_", ".", "-"]):
        return ""
    return re.sub(r"\s+", " ", value)


def _extract_correction_claims(text: str) -> Dict[str, List[str]]:
    invalidated: List[str] = []
    replacements: List[str] = []

    def add(target: List[str], raw: str) -> None:
        value = _normalize_claim_token(raw)
        if value and value not in target:
            target.append(value)

    paired_patterns = [
        re.compile(rf"\breplace\s+({_CLAIM_TOKEN})\s+with\s+({_CLAIM_TOKEN})", re.IGNORECASE),
        re.compile(rf"\buse\s+({_CLAIM_TOKEN})\s*,?\s+not\s+({_CLAIM_TOKEN})", re.IGNORECASE),
        re.compile(rf"\bprefer\s+({_CLAIM_TOKEN})\s+(?:over|instead\s+of)\s+({_CLAIM_TOKEN})", re.IGNORECASE),
    ]
    for pattern in paired_patterns:
        for match in pattern.finditer(text):
            if pattern is paired_patterns[0]:
                add(invalidated, match.group(1))
                add(replacements, match.group(2))
            else:
                add(replacements, match.group(1))
                add(invalidated, match.group(2))

    korean_paired_patterns = [
        re.compile(rf"({_CLAIM_TOKEN})\s*(?:은|는|이|가)?\s*말고\s*({_CLAIM_TOKEN})", re.IGNORECASE),
        re.compile(rf"({_CLAIM_TOKEN})\s*(?:은|는|이|가)?\s*아니(?:라|고)\s*({_CLAIM_TOKEN})", re.IGNORECASE),
    ]
    for pattern in korean_paired_patterns:
        for match in pattern.finditer(text):
            add(invalidated, match.group(1))
            add(replacements, match.group(2))

    negative_patterns = [
        re.compile(
            rf"\b(?:must|should)\s+not\s+(?:contain|include|emit|use|keep|require|have)\s+({_CLAIM_TOKEN})",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\b(?:do\s+not|don't|never)\s+(?:contain|include|emit|use|keep|require|have)\s+({_CLAIM_TOKEN})",
            re.IGNORECASE,
        ),
        re.compile(rf"\b(?:remove|drop|exclude|forbid)\s+({_CLAIM_TOKEN})", re.IGNORECASE),
        re.compile(
            rf"({_CLAIM_TOKEN})\s+(?:is|was)\s+(?:invalid|wrong|incorrect|forbidden|obsolete)",
            re.IGNORECASE,
        ),
        re.compile(rf"({_CLAIM_TOKEN})\s+(?:must|should)\s+not\b", re.IGNORECASE),
    ]
    for pattern in negative_patterns:
        for match in pattern.finditer(text):
            add(invalidated, match.group(1))
    return {"invalidated": invalidated, "replacements": replacements}


_SQL_CORRECTION_SHAPES = (
    r"\b(?:outer|cross)\s+apply\b",
    r"\b(?:left|right|inner|full|cross)\s+(?:outer\s+)?join\b",
    r"\b(?:correlated|scalar)\s+subquery\b",
    r"\btop\s*\(\s*1\s*\)",
    r"\bcte\b",
)


def _sql_shape_claims(text: str) -> List[str]:
    lowered = str(text or "").lower()
    claims: List[str] = []
    for pattern in _SQL_CORRECTION_SHAPES:
        for match in re.finditer(pattern, lowered, flags=re.IGNORECASE):
            claim = re.sub(r"\s+", " ", match.group(0)).strip()
            if claim and claim not in claims:
                claims.append(claim)
    return claims


def _correction_signal(text: str, previous_assistant_text: str = "") -> Dict[str, Any]:
    if _is_synthetic_context_message(text):
        return {
            "is_correction": False,
            "related_to_previous": False,
            "invalidated": [],
            "replacements": [],
        }

    raw = str(text or "").strip()
    normalized = re.sub(r"\s+", " ", raw.lower())
    previous = str(previous_assistant_text or "")
    claims = _extract_correction_claims(raw)
    starts_with_rejection = bool(re.match(r"^(?:아니(?:요)?|그게\s+아니라)\b", normalized))
    has_korean_contrast = bool(re.search(r"(?:말고|아니라|아니고)", normalized))
    has_demonstrative_correction = bool(
        re.match(r"^(?:아니\s+)?(?:저건|그건|이건)\b", normalized)
        and re.search(r"(?:인데|이야|입니다|거야|건데)", normalized)
    )
    has_direct_rejection = any(
        marker in normalized
        for marker in [
            "그따구",
            "저따구",
            "이따구",
            "그런 식으로",
            "누가 그렇게",
            "누가 그걸",
            "쓰지 마",
            "쓰면 안",
            "유지하지 마",
        ]
    )
    english_correction = bool(
        re.search(
            r"\b(?:no[, ]|that(?:'s| is) not|i said\b|not what i (?:asked|said)|instead of)\b",
            normalized,
        )
    )
    relational_grammar = (
        starts_with_rejection
        or has_korean_contrast
        or has_demonstrative_correction
        or has_direct_rejection
        or english_correction
    )
    is_correction = bool(claims["invalidated"] or (previous and relational_grammar))

    invalidated = list(claims["invalidated"])
    previous_shapes = _sql_shape_claims(previous)
    current_shapes = _sql_shape_claims(raw)
    if is_correction and previous_shapes:
        rejected_shapes = [shape for shape in previous_shapes if shape in current_shapes]
        if not rejected_shapes and (starts_with_rejection or has_direct_rejection or has_demonstrative_correction):
            rejected_shapes = previous_shapes
        for shape in rejected_shapes:
            if shape not in invalidated:
                invalidated.append(shape)

    related_to_previous = bool(
        previous
        and (
            relational_grammar
            or any(_claim_in_text(claim, previous) for claim in invalidated)
            or any(_claim_in_text(claim, previous) for claim in claims["replacements"])
        )
    )
    return {
        "is_correction": is_correction,
        "related_to_previous": related_to_previous,
        "invalidated": invalidated,
        "replacements": list(claims["replacements"]),
    }


def _is_assistant_error_admission(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if re.search(
        r"(?:제가|제\s*(?:답|설명|안내|판단|이해|경로)|이전\s*(?:답|설명)).{0,80}"
        r"(?:잘못|틀렸|오해|엉뚱)",
        normalized,
    ):
        return True
    return bool(
        re.search(
            r"\b(?:i was wrong|i(?:'m| am) wrong|my (?:previous )?(?:answer|guidance) was wrong|"
            r"i misread|i misunderstood|my mistake|i incorrectly)\b",
            normalized,
        )
    )


def _correlated_tool_receipts(
    events: Sequence[Dict[str, Any]],
    *,
    include_failed: bool = False,
) -> Sequence[CorrelatedToolReceipt]:
    if isinstance(events, DiskBackedSessionEvents):
        return events.correlated_tool_receipts(include_failed=include_failed)
    if len(events) > _COMPATIBILITY_EVENT_LIMIT:
        raise RuntimeError(
            "compatibility receipt correlation is bounded; use DiskBackedSessionEvents"
        )
    store = DiskBackedSessionEvents()
    try:
        for index, event in enumerate(events):
            if not isinstance(event, Mapping):
                continue
            compact_event = _compact_session_event(event)
            store.append(
                compact_event,
                source_line=index + 1,
            )
        store.seal()
        return list(
            store.correlated_tool_receipts(include_failed=include_failed)
        )
    finally:
        store.close()


def _general_tool_packet_sha256(payload: Mapping[str, Any]) -> str:
    unsigned = {
        str(key): payload[key]
        for key in sorted(_GENERAL_TOOL_PACKET_FIELDS)
        if key in payload and key not in _GENERAL_TOOL_PACKET_HASH_KEYS
    }
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _general_tool_supplied_packet_hash(payload: Mapping[str, Any]) -> str:
    values = {
        str(payload.get(key, "") or "").strip().lower()
        for key in _GENERAL_TOOL_PACKET_HASH_KEYS
        if str(payload.get(key, "") or "").strip()
    }
    if len(values) != 1:
        return ""
    value = next(iter(values))
    return value if re.fullmatch(r"[0-9a-f]{64}", value) else ""


def _is_allowed_general_tool_identity(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if normalized in _GENERAL_TOOL_EXACT_IDENTITIES:
        return True
    if re.fullmatch(r"mcp__[a-z0-9_-]+__[a-z0-9_.-]+", normalized):
        return True
    if re.fullmatch(r"multi_agent_v1(?:__|\.)[a-z0-9_.-]+", normalized):
        return True
    if normalized.endswith(("__exec_command", "__shell_command", "__run_command")):
        return True
    if normalized.startswith(("src.skills.", "src.orchestration.")):
        tail = normalized.rsplit(".", 1)[-1]
        return bool(re.match(r"^(?:verify|validate|orchestrate|approve|record|build|run)_", tail))
    return False


def _duplicate_general_tool_boundaries(events: Sequence[Dict[str, Any]]) -> Any:
    if isinstance(events, DiskBackedSessionEvents):
        return DiskBackedDuplicateFactKeys(events, "boundary")
    counts: Dict[str, int] = {}
    for event in events:
        if str(event.get("type", "")) != "response_item":
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, Mapping):
            continue
        if str(payload.get("type", "")) not in {"function_call", "custom_tool_call"}:
            continue
        boundary_id = str(payload.get("boundary_id", "") or "").strip()
        if boundary_id:
            counts[boundary_id] = counts.get(boundary_id, 0) + 1
    return {boundary_id for boundary_id, count in counts.items() if count > 1}


def _duplicate_general_tool_packet_hashes(events: Sequence[Dict[str, Any]]) -> Any:
    if isinstance(events, DiskBackedSessionEvents):
        return DiskBackedDuplicateFactKeys(events, "packet_hash")
    counts: Dict[str, int] = {}
    for event in events:
        if str(event.get("type", "")) != "response_item":
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, Mapping):
            continue
        if str(payload.get("type", "")) not in {
            "function_call",
            "custom_tool_call",
            "function_call_output",
            "custom_tool_call_output",
        }:
            continue
        packet_hash = _general_tool_supplied_packet_hash(payload)
        if packet_hash:
            counts[packet_hash] = counts.get(packet_hash, 0) + 1
    return {packet_hash for packet_hash, count in counts.items() if count > 1}


def _valid_general_tool_call_provenance(
    call: Mapping[str, Any],
    *,
    duplicate_boundaries: Set[str],
    duplicate_packet_hashes: Set[str],
) -> bool:
    call_id = _payload_call_id(dict(call))
    source = _front_door_provenance_value(call, "source", "host", "origin")
    call_name = str(call.get("name", "") or "").strip().lower()
    tool_identity = str(call.get("tool_identity", "") or "").strip().lower()
    correlation_id = str(call.get("correlation_id", "") or "").strip()
    boundary_id = str(call.get("boundary_id", "") or "").strip()
    packet_hash = _general_tool_supplied_packet_hash(call)
    if _is_front_door_runtime_command(dict(call), _payload_text(dict(call)).lower()):
        return bool(
            call_id
            and source in _KNOWN_HOST_FRONT_DOOR_SOURCES
            and tool_identity == call_name
            and _is_allowed_general_tool_identity(tool_identity)
            and correlation_id == call_id
            and boundary_id
            and boundary_id not in duplicate_boundaries
        )
    return bool(
        call_id
        and source in _KNOWN_HOST_FRONT_DOOR_SOURCES
        and tool_identity == call_name
        and _is_allowed_general_tool_identity(tool_identity)
        and correlation_id == call_id
        and boundary_id
        and boundary_id not in duplicate_boundaries
        and packet_hash
        and packet_hash not in duplicate_packet_hashes
        and packet_hash == _general_tool_packet_sha256(call)
    )


def _valid_general_tool_output_provenance(
    call: Mapping[str, Any],
    output: Mapping[str, Any],
    *,
    duplicate_boundaries: Set[str],
    duplicate_packet_hashes: Set[str],
) -> bool:
    call_id = _payload_call_id(dict(call))
    if not call_id or call_id != _payload_call_id(dict(output)):
        return False
    call_type = str(call.get("type", ""))
    output_type = str(output.get("type", ""))
    if (call_type, output_type) not in {
        ("function_call", "function_call_output"),
        ("custom_tool_call", "custom_tool_call_output"),
    }:
        return False
    source = _front_door_provenance_value(call, "source", "host", "origin")
    output_source = _front_door_provenance_value(output, "source", "host", "origin")
    tool_identity = str(call.get("tool_identity", "") or "").strip().lower()
    output_identity = str(output.get("tool_identity", "") or "").strip().lower()
    boundary_id = str(call.get("boundary_id", "") or "").strip()
    output_boundary = str(output.get("boundary_id", "") or "").strip()
    call_packet_hash = _general_tool_supplied_packet_hash(call)
    output_packet_hash = _general_tool_supplied_packet_hash(output)
    if _is_front_door_runtime_command(dict(call), _payload_text(dict(call)).lower()):
        return _valid_host_front_door_provenance(
            call,
            output,
            _json_object_from_text(_payload_text(dict(output))),
            duplicate_boundaries=duplicate_boundaries,
            duplicate_packet_hashes=duplicate_packet_hashes,
        )
    return bool(
        source in _KNOWN_HOST_FRONT_DOOR_SOURCES
        and output_source == source
        and tool_identity
        and output_identity == tool_identity
        and _is_allowed_general_tool_identity(tool_identity)
        and str(call.get("name", "") or "").strip().lower() == tool_identity
        and str(call.get("correlation_id", "") or "").strip() == call_id
        and str(output.get("correlation_id", "") or "").strip() == call_id
        and boundary_id
        and boundary_id == output_boundary
        and boundary_id not in duplicate_boundaries
        and call_packet_hash
        and str(output.get("call_packet_sha256", "") or "").strip().lower() == call_packet_hash
        and output_packet_hash
        and output_packet_hash not in duplicate_packet_hashes
        and output_packet_hash == _general_tool_packet_sha256(output)
    )


def _duplicate_tool_call_ids(events: Sequence[Dict[str, Any]]) -> List[str]:
    if isinstance(events, DiskBackedSessionEvents):
        return events.duplicate_tool_call_ids()
    call_counts: Dict[str, int] = {}
    output_counts: Dict[str, int] = {}
    for event in events:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        call_id = _payload_call_id(payload)
        if not call_id:
            continue
        payload_type = str(payload.get("type", ""))
        if payload_type in {"function_call", "custom_tool_call"}:
            call_counts[call_id] = call_counts.get(call_id, 0) + 1
        elif payload_type in {"function_call_output", "custom_tool_call_output"}:
            output_counts[call_id] = output_counts.get(call_id, 0) + 1
    return sorted(
        call_id
        for call_id in set(call_counts) | set(output_counts)
        if call_counts.get(call_id, 0) > 1 or output_counts.get(call_id, 0) > 1
    )


def _is_implementation_call(payload: Dict[str, Any]) -> bool:
    if str(payload.get("type", "")) not in {"function_call", "custom_tool_call"}:
        return False
    name = str(payload.get("name", "") or "").lower()
    lowered = _payload_text(payload).lower()
    if any(marker in name for marker in ["apply_patch", "write_file", "edit_file"]):
        return True
    if re.search(r"\btools\.(?:apply_patch|write_file|edit_file)\s*\(", lowered):
        return True
    if ">" not in lowered and not any(
        marker in lowered for marker in _SHELL_WRITE_MARKERS
    ):
        return False
    record = SessionTextRecord(
        text=_payload_text(payload),
        payload_type=str(payload.get("type", "")),
        name=str(payload.get("name", "")),
        arguments=_payload_arguments_text(payload),
    )
    command = _exact_shell_command_text(record)
    if command and _shell_command_has_write_effect(command):
        return True
    if name != "shell_command" and "shell_command" not in name:
        return False
    return _shell_command_has_write_effect(lowered)


_SHELL_WRITE_MARKERS = {
    "apply_patch",
    "set-content",
    "add-content",
    "clear-content",
    "out-file",
    "new-item",
    "copy-item",
    "move-item",
    "rename-item",
    "remove-item",
}


def _shell_command_has_write_effect(command: str) -> bool:
    lowered = str(command or "").lower()
    if any(re.search(rf"(?<![a-z0-9_-]){re.escape(marker)}(?![a-z0-9_-])", lowered) for marker in _SHELL_WRITE_MARKERS):
        return True
    return _contains_unquoted_output_redirection(command)


def _contains_unquoted_output_redirection(command: str) -> bool:
    quote = ""
    escaped = False
    for character in str(command or ""):
        if escaped:
            escaped = False
            continue
        if quote == '"' and character == "\\":
            escaped = True
            continue
        if character in {"'", '"'}:
            if not quote:
                quote = character
            elif quote == character:
                quote = ""
            continue
        if not quote and character == ">":
            return True
    return False


def _is_verification_call(payload: Dict[str, Any]) -> bool:
    if str(payload.get("type", "")) not in {"function_call", "custom_tool_call"}:
        return False
    name = str(payload.get("name", "") or "").lower()
    lowered = _payload_text(payload).lower()
    if any(marker in name for marker in ["verify", "test", "check"]):
        return True
    return any(
        marker in lowered
        for marker in [
            "python -m unittest",
            "pytest",
            "dotnet test",
            "npm test",
            "npm run test",
            "cargo test",
            "go test",
        ]
    )


def _claim_in_text(claim: str, text: str) -> bool:
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9_.-]){re.escape(claim)}(?![A-Za-z0-9_.-])",
            str(text or "").lower(),
        )
    )


def _reasserted_invalidated_claims(text: str, claims: Sequence[str]) -> List[str]:
    lowered = str(text or "").lower()
    repeated: List[str] = []
    for claim in claims:
        match = re.search(
            rf"(?<![A-Za-z0-9_.-]){re.escape(claim)}(?![A-Za-z0-9_.-])",
            lowered,
        )
        if not match:
            continue
        window = lowered[max(0, match.start() - 70) : match.end() + 90]
        negative = any(
            marker in window
            for marker in [
                "removed",
                "remove ",
                "without ",
                "no longer",
                "must not",
                "should not",
                "do not",
                "forbidden",
                "invalid",
                "rejected",
                "exclude",
                "잘못",
                "틀렸",
                "제거",
                "빼",
                "쓰지",
                "사용하지",
                "유지하지",
            ]
        )
        affirmative = any(
            marker in window
            for marker in [
                " keep",
                "kept",
                "require",
                "include",
                "emit",
                "still",
                "must use",
                "remains",
                "retained",
                "added",
                "= true",
                "유지",
                "사용",
                "그대로",
                "포함",
            ]
        )
        if affirmative and not negative:
            repeated.append(claim)
    return repeated


def _correction_implementation_receipt(
    receipts: Sequence[CorrelatedToolReceipt],
    correction_index: int,
    completion_index: int,
    invalidated_claims: Sequence[str],
    replacement_claims: Sequence[str],
) -> CorrelatedToolReceipt | None:
    for receipt in receipts:
        if not (correction_index < receipt.call_index < receipt.output_index < completion_index):
            continue
        if not _is_implementation_call(receipt.call):
            continue
        call_text = _payload_text(receipt.call)
        if replacement_claims and all(
            _implementation_adds_or_selects_claim(claim, call_text)
            for claim in replacement_claims
        ):
            return receipt
        if invalidated_claims and not replacement_claims and all(
            _implementation_removes_claim(claim, call_text)
            for claim in invalidated_claims
        ):
            return receipt
    return None


def _implementation_adds_or_selects_claim(claim: str, text: str) -> bool:
    if not _claim_in_text(claim, text):
        return False
    lowered = str(text or "").lower()
    if "*** begin patch" not in lowered:
        return True
    return any(
        line.lstrip().startswith("+")
        and not line.lstrip().startswith("+++")
        and _claim_in_text(claim, line)
        for line in lowered.splitlines()
    )


def _implementation_removes_claim(claim: str, text: str) -> bool:
    lowered = str(text or "").lower()
    for match in re.finditer(
        rf"(?<![A-Za-z0-9_.-]){re.escape(claim)}(?![A-Za-z0-9_.-])",
        lowered,
    ):
        line_start = lowered.rfind("\n", 0, match.start()) + 1
        line_end = lowered.find("\n", match.end())
        line = lowered[line_start : len(lowered) if line_end < 0 else line_end]
        stripped = line.lstrip()
        if stripped.startswith("-") and not stripped.startswith("---"):
            return True
        window = lowered[max(0, match.start() - 70) : match.end() + 70]
        if any(
            marker in window
            for marker in [
                "remove",
                "removed",
                "drop",
                "exclude",
                "without",
                "no longer",
                "forbid",
                "delete",
            ]
        ):
            return True
    return False


def _fresh_verification_receipt(
    receipts: Sequence[CorrelatedToolReceipt],
    after_index: int,
    completion_index: int,
) -> CorrelatedToolReceipt | None:
    for receipt in receipts:
        if after_index < receipt.call_index < receipt.output_index < completion_index and _is_verification_call(receipt.call):
            return receipt
    return None


def _user_instruction_supersession_issues(path: Path) -> List[Dict[str, Any]]:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("instruction supersession requires the streaming fact store")
    receipts = _correlated_tool_receipts(events)
    issues: List[Dict[str, Any]] = []
    correction_rows = events._db.execute(
        """
        SELECT event_seq, active_goal, invalidated_json, replacements_json,
               related_to_previous, prior_completion_seq, sample
        FROM correction_facts
        ORDER BY event_seq
        """
    )
    for row in correction_rows:
        correction_index = int(row[0])
        active_goal = bool(row[1])
        invalidated = [str(value) for value in _json_scalar_sequence(row[2])]
        replacements = [str(value) for value in _json_scalar_sequence(row[3])]
        related_to_previous = bool(row[4])
        prior_completion_index = int(row[5]) if row[5] is not None else None
        correction_sample = str(row[6])
        completion_row = events._db.execute(
            """
            SELECT MIN(seq)
            FROM events
            WHERE payload_type = 'task_complete' AND seq > ?
            """,
            (correction_index,),
        ).fetchone()
        completion_index = (
            int(completion_row[0])
            if completion_row and completion_row[0] is not None
            else len(events)
        )
        repeated: List[str] = []
        repeated_sample = ""
        admission_sample = ""
        for _event_seq, payload in events.iter_payloads(
            payload_types=("message", "agent_message", "task_complete"),
            start=correction_index + 1,
            stop=completion_index + 1,
        ):
            payload_type = str(payload.get("type", ""))
            role = str(payload.get("role", "")).lower()
            if not (
                (payload_type == "message" and role == "assistant")
                or payload_type in {"agent_message", "task_complete"}
            ):
                continue
            candidate_text = _payload_text(payload)
            if not admission_sample and _is_assistant_error_admission(candidate_text):
                admission_sample = _short(candidate_text)
            repeated = _reasserted_invalidated_claims(candidate_text, invalidated)
            if repeated:
                repeated_sample = _short(candidate_text)
                break
        if (
            prior_completion_index is not None
            and related_to_previous
            and admission_sample
        ):
            implementation = _correction_implementation_receipt(
                receipts,
                correction_index,
                completion_index,
                invalidated,
                replacements,
            )
            verification = (
                _fresh_verification_receipt(receipts, implementation.output_index, completion_index)
                if implementation
                else None
            )
            issues.append(
                {
                    "skill": "verification-before-completion-harness",
                    "status": "premature_completion_corrected_after_task_complete",
                    "severity": "P0",
                    "reason": (
                        "A same-task user correction and the assistant's explicit error admission "
                        "invalidated an earlier task_complete claim."
                    ),
                    "action": (
                        "Do not claim completion until the correction is implemented and fresh evidence "
                        "verifies the corrected result."
                    ),
                    "prior_completion_index": prior_completion_index,
                    "correction": correction_sample,
                    "admission": admission_sample,
                    "corrected_completion_claimed": completion_index < len(events),
                    "corrected_completion_evidence": bool(implementation and verification),
                }
            )
        if repeated:
            issues.append(
                {
                    "skill": "context-state-harness",
                    "status": "invalidated_user_correction_repeated",
                    "severity": "P0" if completion_index < len(events) else "P1",
                    "reason": "The assistant reasserted a claim after the user explicitly invalidated it.",
                    "action": "Treat the latest user correction as authoritative and remove the invalidated assumption before completion.",
                    "invalidated_claims": repeated,
                    "correction": correction_sample,
                    "repetition": repeated_sample,
                }
            )
        if not active_goal or completion_index >= len(events):
            continue
        implementation = _correction_implementation_receipt(
            receipts,
            correction_index,
            completion_index,
            invalidated,
            replacements,
        )
        verification = (
            _fresh_verification_receipt(receipts, implementation.output_index, completion_index)
            if implementation
            else None
        )
        missing = []
        if not implementation:
            missing.append("correlated_implementation")
        if not verification:
            missing.append("fresh_verification")
        if missing:
            issues.append(
                {
                    "skill": "goal-state-harness",
                    "status": "corrective_feedback_unresolved",
                    "severity": "P0",
                    "reason": (
                        "Corrective feedback arrived while the Goal was active, but completion was emitted "
                        "without ordered implementation and verification receipts for that correction."
                    ),
                    "action": "Continue the same Goal, implement the correlated correction, then run fresh verification before task_complete.",
                    "missing_evidence": missing,
                    "correction": correction_sample,
                }
            )
    return issues


def _apply_correction_completion_guard(
    postmortem: Dict[str, Any],
    issues: Sequence[Dict[str, Any]],
) -> None:
    invalidations = [
        issue
        for issue in issues
        if issue.get("status") == "premature_completion_corrected_after_task_complete"
    ]
    unresolved = [
        issue for issue in invalidations if not issue.get("corrected_completion_evidence")
    ]
    if not unresolved:
        return

    guard = dict(postmortem.get("completion_guard", {}) or {})
    corrected_completion_claimed = any(
        bool(issue.get("corrected_completion_claimed")) for issue in unresolved
    )
    reasons = [str(reason) for reason in guard.get("reasons", []) or []]
    for reason in [
        "completion_invalidated_by_same_task_correction",
        "corrected_completion_evidence_missing",
    ]:
        if reason not in reasons:
            reasons.append(reason)
    guard.update(
        {
            "status": "failed" if corrected_completion_claimed else "pending",
            "reasons": reasons,
            "pending_correction_count": len(unresolved),
            "corrected_completion_evidence": False,
        }
    )
    postmortem["completion_guard"] = guard


def _aggregate_skill_runtime_evidence_issues(path: Path) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("aggregate runtime audit requires indexed event facts")
    for _event_seq, _payload, data in events.iter_front_door_claim_payloads():
        summary = data.get("skill_status_summary", {}) if data else {}
        if not isinstance(summary, dict):
            continue
        for skill_name, status_record in summary.items():
            if not isinstance(status_record, dict):
                continue
            if (
                str(status_record.get("status", "")) != "applied"
                or "runtime_evidence" not in status_record
                or status_record.get("runtime_evidence")
                or str(skill_name) in seen
            ):
                continue
            if len(seen) >= _AUDIT_VALUE_SAMPLE_LIMIT:
                continue
            seen.add(str(skill_name))
            issues.append(
                {
                    "skill": str(skill_name),
                    "status": "aggregate_applied_without_runtime_evidence",
                    "severity": "P1",
                    "reason": "Aggregate skill status claimed applied while its runtime_evidence collection was empty.",
                    "action": "Downgrade the aggregate status or attach non-empty runtime receipt evidence from the actual skill execution.",
                }
            )
    return issues


def _authoritative_references(text: str) -> List[str]:
    lowered = str(text or "").lower()
    if not any(
        marker in lowered
        for marker in [
            "authoritative",
            "source of truth",
            "canonical reference",
            "authoritative reference",
        ]
    ):
        return []
    candidates = re.findall(r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'", str(text or ""))
    values = [next((part for part in match if part), "") for match in candidates]
    values.extend(re.findall(r"https?://[^\s<>`\"']+", str(text or ""), flags=re.IGNORECASE))
    values.extend(re.findall(r"[A-Za-z]:\\[^\s<>`\"']+", str(text or "")))
    references: List[str] = []
    for raw in values:
        value = raw.strip().rstrip(".,;:)]}")
        if not value or not (
            "/" in value
            or "\\" in value
            or re.search(r"\.[A-Za-z0-9]{1,8}$", value)
        ):
            continue
        if value not in references:
            references.append(value)
    return references


def _normalized_reference(value: str) -> str:
    return str(value or "").replace("\\", "/").lower().strip()


def _is_reference_read_call(payload: Dict[str, Any], reference: str) -> bool:
    if str(payload.get("type", "")) not in {"function_call", "custom_tool_call"}:
        return False
    name = str(payload.get("name", "") or "").lower()
    lowered = _normalized_reference(_payload_text(payload))
    if _normalized_reference(reference) not in lowered:
        return False
    return any(
        marker in name or marker in lowered
        for marker in [
            "get-content",
            "read_file",
            "read_mcp_resource",
            "open",
            "cat ",
            "type ",
        ]
    )


def _introduces_constants_or_behavior(payload: Dict[str, Any]) -> bool:
    if not _is_implementation_call(payload):
        return False
    additions = "\n".join(
        line[1:]
        for line in _payload_text(payload).splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    if not additions:
        return False
    return bool(
        re.search(
            r"(?im)(?:\b(?:const|static|readonly|final|enum|def|class|return|if|switch|case)\b|^[A-Z][A-Z0-9_]{2,}\s*=)",
            additions,
        )
    )


def _authoritative_reference_order_issues(path: Path) -> List[Dict[str, Any]]:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("authoritative reference audit requires indexed event facts")
    receipts = _correlated_tool_receipts(events)
    if not isinstance(receipts, DiskBackedToolReceipts):
        raise RuntimeError("authoritative reference audit requires indexed receipts")
    issues: List[Dict[str, Any]] = []
    for user_index, payload in events.iter_payloads(
        payload_types=("message",),
        roles=("user",),
    ):
        for reference in _authoritative_references(_payload_text(payload)):
            boundary_row = events._db.execute(
                """
                SELECT MIN(seq) FROM events
                WHERE payload_type = 'task_complete' AND seq > ?
                """,
                (user_index,),
            ).fetchone()
            task_boundary = (
                int(boundary_row[0])
                if boundary_row and boundary_row[0] is not None
                else len(events)
            )
            read_output_index = min(
                (
                    receipt.output_index
                    for receipt in receipts.iter_range(
                        after_index=user_index,
                        before_index=task_boundary,
                    )
                    if _is_reference_read_call(receipt.call, reference)
                ),
                default=task_boundary,
            )
            premature = next(
                (
                    (index, candidate)
                    for index, candidate in events.iter_payloads(
                        payload_types=("function_call", "custom_tool_call"),
                        start=user_index + 1,
                        stop=read_output_index,
                    )
                    if _introduces_constants_or_behavior(candidate)
                ),
                None,
            )
            if not premature:
                continue
            issues.append(
                {
                    "skill": "context-state-harness",
                    "status": "authoritative_reference_not_read_first",
                    "severity": "P1",
                    "reason": "Constants or behavior were introduced before a correlated read receipt for the user-named authoritative reference.",
                    "action": "Read the named reference successfully, then derive constants and behavior from that evidence.",
                    "reference": reference,
                    "first_implementation": _short(_payload_text(premature[1])),
                }
            )
    return issues


def _is_residual_scan_call(payload: Dict[str, Any], patterns: Sequence[str]) -> bool:
    if str(payload.get("type", "")) not in {"function_call", "custom_tool_call"}:
        return False
    lowered = _payload_text(payload).lower()
    if not any(_claim_in_text(pattern, lowered) for pattern in patterns):
        return False
    return any(marker in lowered for marker in ["rg ", "select-string", "grep ", "findstr "])


def _residual_matches(text: str, patterns: Sequence[str]) -> List[str] | None:
    lowered = str(text or "").lower()
    matches = [pattern for pattern in patterns if _claim_in_text(pattern, lowered)]
    if matches:
        return matches
    if re.fullmatch(
        r"\s*(?:exit code:\s*[01]\s*)?"
        r"(?:no matches(?: found)?|0 matches|zero matches|not found|no residuals?)[.!]?\s*",
        lowered,
    ):
        return []
    return None


def _forbidden_residual_completion_issues(path: Path) -> List[Dict[str, Any]]:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("residual completion audit requires indexed event facts")
    receipts = _correlated_tool_receipts(events)
    if not isinstance(receipts, DiskBackedToolReceipts):
        raise RuntimeError("residual completion audit requires indexed receipts")
    events._db.execute("DELETE FROM active_forbidden_claims")
    issues: List[Dict[str, Any]] = []
    for index, payload in events.iter_payloads(
        payload_types=("message", "task_complete")
    ):
        payload_type = str(payload.get("type", ""))
        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            user_text = _payload_text(payload)
            if _is_synthetic_context_message(user_text):
                continue
            claims = _extract_correction_claims(user_text)
            for claim in claims["invalidated"]:
                events._db.execute(
                    """
                    INSERT OR REPLACE INTO active_forbidden_claims(
                        claim, request_seq, scanned, matched, scan_sample
                    ) VALUES (?, ?, 0, 0, '')
                    """,
                    (claim, index),
                )
        obligation_row = events._db.execute(
            "SELECT COUNT(*), MIN(request_seq) FROM active_forbidden_claims"
        ).fetchone()
        if (
            payload_type != "task_complete"
            or obligation_row is None
            or int(obligation_row[0]) == 0
        ):
            continue
        latest_row = events._db.execute(
            """
            SELECT MAX(output_seq) FROM correlated_receipts
            WHERE succeeded = 1 AND is_implementation = 1 AND output_seq < ?
            """,
            (index,),
        ).fetchone()
        latest_implementation = (
            int(latest_row[0])
            if latest_row and latest_row[0] is not None
            else -1
        )
        minimum_request = int(obligation_row[1])
        for receipt in receipts.iter_range(
            after_index=max(latest_implementation, minimum_request - 1),
            before_index=index,
        ):
            call_text = _payload_text(receipt.call)
            lowered_call = call_text.lower()
            if not any(
                marker in lowered_call
                for marker in ("rg ", "select-string", "grep ", "findstr ")
            ):
                continue
            claim_rows = events._db.execute(
                """
                SELECT claim FROM active_forbidden_claims
                WHERE request_seq < ?
                ORDER BY claim
                """,
                (receipt.call_index,),
            )
            for claim_row in claim_rows:
                claim = str(claim_row[0])
                if not _claim_in_text(claim, call_text):
                    continue
                found = _residual_matches(_payload_text(receipt.output), (claim,))
                if found is None:
                    continue
                events._db.execute(
                    """
                    UPDATE active_forbidden_claims
                    SET scanned = 1,
                        matched = CASE WHEN ? THEN 1 ELSE matched END,
                        scan_sample = CASE WHEN ? THEN ? ELSE scan_sample END
                    WHERE claim = ?
                    """,
                    (
                        int(bool(found)),
                        int(bool(found)),
                        _short(_payload_text(receipt.output)),
                        claim,
                    ),
                )
        for matched_value, status, reason, action in (
            (
                1,
                "forbidden_residuals_at_completion",
                "task_complete followed a fresh residual scan whose correlated output still contained user-forbidden patterns.",
                "Remove every reported residual and run a new clean scan before completion.",
            ),
            (
                0,
                "missing_fresh_residual_scan_at_completion",
                "task_complete was emitted with an active correction or forbidden-pattern obligation but no correlated residual scan receipt after the latest implementation.",
                "Run a fresh residual scan for every forbidden pattern and correlate its output before completion.",
            ),
        ):
            predicate = "matched = 1" if matched_value else "scanned = 0"
            count_row = events._db.execute(
                f"SELECT COUNT(*) FROM active_forbidden_claims WHERE {predicate}"
            ).fetchone()
            count = int(count_row[0]) if count_row else 0
            if not count:
                continue
            pattern_rows = events._db.execute(
                f"""
                SELECT claim FROM active_forbidden_claims
                WHERE {predicate}
                ORDER BY claim
                LIMIT ?
                """,
                (_AUDIT_VALUE_SAMPLE_LIMIT,),
            )
            issue = {
                "skill": "verification-before-completion-harness",
                "status": status,
                "severity": "P0",
                "reason": reason,
                "action": action,
                "forbidden_patterns": [str(row[0]) for row in pattern_rows],
            }
            if matched_value:
                sample_row = events._db.execute(
                    """
                    SELECT scan_sample FROM active_forbidden_claims
                    WHERE matched = 1 AND scan_sample <> ''
                    ORDER BY claim LIMIT 1
                    """
                ).fetchone()
                issue["scan_output"] = str(sample_row[0]) if sample_row else ""
            if count > len(issue["forbidden_patterns"]):
                issue["forbidden_pattern_count"] = count
                issue["forbidden_patterns_truncated"] = True
            issues.append(issue)
        events._db.execute("DELETE FROM active_forbidden_claims")
    return issues


def _explicit_user_delegation(text: str) -> bool:
    lowered = str(text or "").lower()
    if any(marker in lowered for marker in ["without delegation", "waive delegation", "single-controller waiver"]):
        return False
    return (
        any(marker in lowered for marker in ["delegate", "delegation", "dispatch", "use nested agents", "use subagents"])
        and any(marker in lowered for marker in ["agent", "subagent", "role", "implement", "review", "dispatch"])
    )


def _user_approved_delegation_waiver(text: str) -> bool:
    lowered = str(text or "").lower()
    return (
        any(marker in lowered for marker in ["without delegation", "waive delegation", "waiver", "single-controller"])
        and any(marker in lowered for marker in ["approve", "approved", "i waive", "proceed", "for this run"])
    )


def _nested_agents_availability_in_data(value: Any) -> bool | None:
    if isinstance(value, dict):
        for key in ["nested_subagents_available", "nested_agents_available"]:
            if isinstance(value.get(key), bool):
                return bool(value[key])
        for key in ["nested_agents", "nested_subagents"]:
            nested = value.get(key)
            if isinstance(nested, dict) and isinstance(nested.get("available"), bool):
                return bool(nested["available"])
        for item in value.values():
            availability = _nested_agents_availability_in_data(item)
            if availability is not None:
                return availability
    elif isinstance(value, list):
        for item in value:
            availability = _nested_agents_availability_in_data(item)
            if availability is not None:
                return availability
    return None


def _is_nested_capability_receipt(receipt: CorrelatedToolReceipt) -> bool:
    call_text = _payload_text(receipt.call).lower()
    return (
        any(marker in call_text for marker in ["runtime_capabil", "nested_agent", "nested_subagent"])
        and _nested_agents_availability_in_data(receipt.data) is not None
    )


def _is_dispatch_receipt(receipt: CorrelatedToolReceipt) -> bool:
    call_text = _payload_text(receipt.call).lower()
    if not any(
        marker in call_text
        for marker in ["spawn_agent", "dispatch_project_workflow", "async_project_workflow"]
    ):
        return False
    data = receipt.data
    return bool(
        data.get("agent_id")
        or data.get("thread_id")
        or data.get("dispatch_receipt")
        or data.get("role_results")
    )


def _is_fan_in_receipt(receipt: CorrelatedToolReceipt) -> bool:
    call_text = _payload_text(receipt.call).lower()
    if not any(marker in call_text for marker in ["wait_agent", "wait_for", "fan_in", "dispatch_project_workflow", "async_project_workflow"]):
        return False
    data = receipt.data
    if data.get("fan_in_complete") is True or data.get("fan_in_receipt"):
        return True
    results = data.get("results") or data.get("role_results")
    if not isinstance(results, list) or not results:
        return False
    terminal = {"complete", "completed", "success", "passed", "closed"}
    return all(
        isinstance(item, dict) and str(item.get("status", "")).lower() in terminal
        for item in results
    )


def _required_delegation_issues(path: Path) -> List[Dict[str, Any]]:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("delegation audit requires indexed event facts")
    receipts = _correlated_tool_receipts(events)
    if not isinstance(receipts, DiskBackedToolReceipts):
        raise RuntimeError("delegation audit requires indexed receipt facts")
    requirement_index: int | None = None
    requirement_sources: Set[str] = set()
    for index, payload in events.iter_payloads(
        payload_types=("message",),
        roles=("user",),
    ):
        if _explicit_user_delegation(_payload_text(payload)):
            requirement_index = index if requirement_index is None else min(requirement_index, index)
            requirement_sources.add("explicit_user_delegation")
    for output_index, receipt in _correlated_front_door_receipts(events).items():
        classification = receipt.data.get("classification", {}) or {}
        if isinstance(classification, dict) and str(classification.get("recommended_execution", "")) == "role_dag":
            requirement_index = (
                output_index
                if requirement_index is None
                else min(requirement_index, output_index)
            )
            requirement_sources.add("mandatory_role_dag")
    if requirement_index is None:
        return []
    terminal_row = events._db.execute(
        """
        SELECT MIN(seq) FROM events
        WHERE payload_type = 'task_complete' AND seq > ?
        """,
        (requirement_index,),
    ).fetchone()
    terminal_index = (
        int(terminal_row[0])
        if terminal_row and terminal_row[0] is not None
        else -1
    )
    implementation_index = next(
        (
            index
            for index, payload in events.iter_payloads(
                payload_types=("function_call", "custom_tool_call"),
                start=requirement_index + 1,
            )
            if _is_implementation_call(payload)
        ),
        -1,
    )
    decision_index = terminal_index if terminal_index >= 0 else implementation_index
    if decision_index < 0:
        return []
    dispatch_count = 0
    fan_in_count = 0
    latest_dispatch_output = -1
    availability_count = 0
    availability_true = False
    availability_observed = False
    for receipt in receipts.iter_range(
        after_index=requirement_index,
        before_index=decision_index,
    ):
        if _is_dispatch_receipt(receipt):
            dispatch_count += 1
            latest_dispatch_output = max(latest_dispatch_output, receipt.output_index)
        if (
            latest_dispatch_output >= 0
            and _is_fan_in_receipt(receipt)
            and latest_dispatch_output < receipt.call_index
        ):
            fan_in_count += 1
        if _is_nested_capability_receipt(receipt):
            availability_count += 1
            availability = _nested_agents_availability_in_data(receipt.data)
            availability_observed = availability_observed or availability is not None
            availability_true = availability_true or availability is True
    user_waiver = any(
        _user_approved_delegation_waiver(_payload_text(payload))
        for _index, payload in events.iter_payloads(
            payload_types=("message",),
            roles=("user",),
            start=requirement_index + 1,
            stop=decision_index,
        )
    )
    nested_available: bool | None
    if dispatch_count or availability_true:
        nested_available = True
    elif availability_observed:
        nested_available = False
    else:
        nested_available = None
    if (dispatch_count and fan_in_count) or user_waiver:
        return []
    explicit_user_requirement = "explicit_user_delegation" in requirement_sources
    if nested_available is False:
        return []
    if nested_available is None and not explicit_user_requirement:
        return []
    if nested_available is None:
        reason = (
            "Explicit user delegation reached the decision boundary without a correlated "
            "nested-agent availability receipt, ordered dispatch/fan-in receipts, or a user-approved waiver."
        )
    else:
        reason = (
            "Delegation was user-required or role_dag-mandated while nested agents were available, "
            "but no ordered dispatch/fan-in receipts or user-approved waiver were present."
        )
    return [
        {
            "skill": "host-agent-orchestration",
            "status": "missing_required_delegation_receipt",
            "severity": "P0" if terminal_index >= 0 else "P1",
            "reason": reason,
            "action": "Dispatch and fan in nested-agent work, or obtain an explicit waiver from the user; a controller-authored waiver is insufficient.",
            "requirement_sources": sorted(requirement_sources),
            "nested_agents_available": nested_available,
            "availability_receipt": bool(availability_count),
            "dispatch_receipts": dispatch_count,
            "fan_in_receipts": fan_in_count,
            "user_approved_waiver": user_waiver,
        }
    ]


def _front_door_selected_skill(path: Path, skill_name: str) -> bool:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("front-door selection requires indexed claim facts")
    for _event_seq, _payload, data in events.iter_front_door_claim_payloads():
        immediate = {str(item) for item in data.get("immediate_next_skills", []) or []}
        if skill_name in immediate:
            return True
        selected = {str(item) for item in data.get("selected_not_executed_skills", []) or []}
        if skill_name in selected:
            return True
        status_summary = data.get("skill_status_summary", {}) or {}
        if isinstance(status_summary, dict) and skill_name in status_summary:
            summary = status_summary.get(skill_name, {}) or {}
            if str(summary.get("status", "")) in {"skipped_with_rationale", "considered_not_needed", "blocked"}:
                return True
    return False


def _front_door_blocks_execution(path: Path) -> bool:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("front-door gate check requires indexed claim facts")
    for _event_seq, _payload, data in events.iter_front_door_claim_payloads():
        gate = data.get("execution_gate", {}) or {}
        if isinstance(gate, dict) and gate.get("can_execute") is False:
            return True
    return False


def _subagent_strategy_issues(
    path: Path,
    postmortem: Dict[str, Any],
    *,
    active_text: str | None = None,
) -> List[Dict[str, Any]]:
    if not _is_subagent_session(path):
        return []
    if active_text is None:
        active_text = _bounded_text_aggregate(_active_non_front_door_texts(path))
    lowered = active_text.lower()
    subagents = postmortem.get("subagent_summary", {}) or {}
    token_gate = postmortem.get("token_gate", {}) or {}
    if not (
        _implementation_tool_samples(path)
        or int(subagents.get("spawned", 0) or 0)
        or bool(token_gate.get("required"))
        or bool(postmortem.get("verification_commands"))
    ):
        return []
    if _has_subagent_strategy_rationale(lowered):
        return []
    return [
        {
            "skill": "host-agent-orchestration",
            "status": "missing_subagent_strategy",
            "severity": "P2",
            "reason": (
                "A subagent session performed non-trivial work but did not record whether nested subagents "
                "were available or why the controller chose single-agent execution."
            ),
            "action": (
                "Record host_runtime, nested-subagent availability, subagent_strategy="
                "dispatch|single-controller|review-only|blocked, and the no-subagent rationale before implementation."
            ),
        },
        {
            "skill": "subagent-review-pipeline",
            "status": "missing_subagent_strategy",
            "severity": "P2",
            "reason": (
                "Subagent review policy was not resolved for a subagent-run implementation; no dispatch, "
                "review-only, single-controller, or blocked rationale was preserved."
            ),
            "action": (
                "If nested subagents are unavailable or not useful, record subagent_strategy=single-controller "
                "with host-limited, sequential, tiny, or shared-state-heavy rationale."
            ),
        },
    ]


def _orchestration_decision_issues(
    path: Path,
    postmortem: Dict[str, Any],
    *,
    active_text: str | None = None,
) -> List[Dict[str, Any]]:
    if active_text is None:
        active_text = _bounded_text_aggregate(_active_non_front_door_texts(path))
    lowered = active_text.lower()

    if not _session_has_implementation_activity(path, postmortem, lowered):
        return []

    selected_orchestration = {
        "host-agent-orchestration": _front_door_selected_skill(path, "host-agent-orchestration"),
        "subagent-review-pipeline": _front_door_selected_skill(path, "subagent-review-pipeline"),
        "parallel-orchestration-harness": _front_door_selected_skill(path, "parallel-orchestration-harness"),
        "role-execution-audit-harness": _front_door_selected_skill(path, "role-execution-audit-harness"),
    }
    if not any(selected_orchestration.values()):
        return []

    validated_artifacts = _validated_orchestration_artifacts(path)

    issues: List[Dict[str, Any]] = []
    if (
        selected_orchestration["host-agent-orchestration"]
        or selected_orchestration["subagent-review-pipeline"]
    ) and not _has_subagent_strategy_rationale(lowered):
        issues.append(
            {
                "skill": "host-agent-orchestration",
                "status": "missing_orchestration_decision",
                "severity": "P1",
                "reason": (
                    "Implementation work ran after KH selected host/subagent orchestration, but the session did "
                    "not record dispatch, single-controller, review-only, or blocked strategy evidence."
                ),
                "action": (
                    "Before implementation, record host_runtime, nested_subagents_available, "
                    "subagent_strategy, and a concrete dispatch/no-dispatch rationale."
                ),
            }
        )
        issues.append(
            {
                "skill": "subagent-review-pipeline",
                "status": "missing_orchestration_decision",
                "severity": "P1",
                "reason": (
                    "The session could silently continue as a single agent because no subagent/reviewer "
                    "strategy was preserved before implementation."
                ),
                "action": (
                    "Dispatch independent roles when useful, or record subagent_strategy=single-controller, "
                    "review-only, or blocked with a host-limited, tiny, sequential, or shared-state rationale."
                ),
            }
        )
    if (
        selected_orchestration["parallel-orchestration-harness"]
        and not validated_artifacts["parallel_strategy"]
    ):
        issues.append(
            {
                "skill": "parallel-orchestration-harness",
                "status": "missing_parallel_strategy",
                "severity": "P1",
                "reason": (
                    "Implementation work ran after KH selected parallel orchestration, but no parallel, "
                    "sequential-with-rationale, read-only-side-agent, or blocked strategy was recorded."
                ),
                "action": (
                    "Record parallel_strategy_decision=parallel|sequential|read-only-side-agents|blocked "
                    "with fan-out/fan-in or no-parallel rationale before implementation."
                ),
            }
        )
    if (
        selected_orchestration["role-execution-audit-harness"]
        and not validated_artifacts["role_execution_audit"]
    ):
        issues.append(
            {
                "skill": "role-execution-audit-harness",
                "status": "missing_role_execution_audit",
                "severity": "P1",
                "reason": (
                    "Implementation work ran after KH selected role execution audit, but no role result, "
                    "parallel wave, skipped, or blocked role-audit evidence was recorded."
                ),
                "action": (
                    "Record role_execution_audit.status with required roles, role artifacts, parallel wave "
                    "count, or an explicit skipped/blocked rationale before completion."
                ),
            }
        )
    return issues


def _validated_orchestration_artifacts(path: Path) -> Dict[str, bool]:
    records = _session_text_records(path)
    if not isinstance(records, DiskBackedSessionTextRecords):
        raise RuntimeError("orchestration audit requires indexed protocol facts")
    evidence = {"parallel_strategy": False, "role_execution_audit": False}
    for call_index, call, validates_bundle, audits_roles in (
        records.iter_orchestration_protocol_calls()
    ):
        if validates_bundle:
            output = records.immediate_structured_output(call_index)
            call_data = _json_object_from_text(call.text)
            bundle = call_data.get("bundle", call_data) if isinstance(call_data, dict) else {}
            if _valid_large_work_bundle_artifact(output):
                decision = str(bundle.get("parallel_strategy_decision") or "").strip().lower()
                if decision and not decision.startswith("parallel") and _has_no_parallel_rationale(decision):
                    evidence["parallel_strategy"] = True
                role_statuses = bundle.get("skill_statuses", {})
                role_status = (
                    role_statuses.get("role-execution-audit-harness", {})
                    if isinstance(role_statuses, dict)
                    else {}
                )
                if _valid_pre_role_decision(role_status):
                    evidence["role_execution_audit"] = True
        if audits_roles:
            output = records.immediate_structured_output(call_index)
            audit = _find_nested_mapping(output, "role_execution_audit") or output
            if _valid_role_execution_audit_artifact(audit):
                evidence["role_execution_audit"] = True
                if _role_audit_proves_parallel_execution(audit):
                    evidence["parallel_strategy"] = True
    return evidence


def _valid_large_work_bundle_artifact(output: Dict[str, Any]) -> bool:
    return (
        output.get("valid") is True
        and not output.get("missing")
        and "parallel_strategy_decision" in set(output.get("evidence", []) or [])
    )


def _valid_pre_role_decision(status: Any) -> bool:
    if not isinstance(status, dict):
        return False
    return (
        str(status.get("status") or "")
        in {"considered_not_needed", "skipped_with_rationale", "blocked"}
        and bool(str(status.get("evidence_note") or "").strip())
    )


def _find_nested_mapping(value: Any, key: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    nested = value.get(key)
    if isinstance(nested, dict):
        return nested
    for candidate in value.values():
        found = _find_nested_mapping(candidate, key)
        if found:
            return found
    return {}


def _valid_role_execution_audit_artifact(audit: Any) -> bool:
    if not isinstance(audit, dict) or str(audit.get("status") or "") not in {"passed", "failed"}:
        return False
    checks = audit.get("checks", [])
    return bool(audit.get("evidence")) and any(
        isinstance(check, dict) and check.get("name") == "role-execution-audit"
        for check in checks
    )


def _role_audit_proves_parallel_execution(audit: Dict[str, Any]) -> bool:
    if audit.get("status") != "passed":
        return False
    for check in audit.get("checks", []) or []:
        if not isinstance(check, dict) or check.get("name") != "role-execution-audit":
            continue
        summary = check.get("summary", {})
        if not isinstance(summary, dict):
            continue
        return (
            summary.get("execution_model") == "dag-asyncio-role-waves"
            and int(summary.get("parallel_wave_count") or 0) > 0
        )
    return False


def _early_domain_discovery_text(lowered: str) -> bool:
    english_markers = [
        "brainstorm",
        "saas",
        "product idea",
        "build a product",
        "develop a product",
        "new product",
        "new app",
        "website",
        "web site",
        "webpage",
        "web page",
        "homepage",
        "web app",
        "project idea",
        "new workflow",
        "process design",
        "analysis plan",
        "research plan",
        "design a process",
        "create a specification",
        "make a drawing",
        "investment plan",
        "operating model",
    ]
    korean_markers = [
        "\uc81c\ud488",
        "\uc11c\ube44\uc2a4",
        "\ud504\ub85c\ub355\ud2b8",
        "\uc0ac\uc774\ud2b8",
        "\uc6f9",
        "\uc6f9\uc0ac\uc774\ud2b8",
        "\uc6f9\ud398\uc774\uc9c0",
        "\ud648\ud398\uc774\uc9c0",
        "\uc571",
        "\uc6f9\uc571",
        "\ub300\uc2dc\ubcf4\ub4dc",
        "\uae30\ud68d",
        "\uac1c\ubc1c\ud574\uc918",
        "\ub9cc\ub4e4\uc5b4\uc918",
        "\ubd84\uc11d",
        "\ub9ac\uc11c\uce58",
        "\uc5f0\uad6c",
        "\uc815\ucc45",
        "\ud504\ub85c\uc138\uc2a4",
        "\uc5c5\ubb34\ud750\ub984",
        "\uc124\uacc4\ub3c4",
        "\ub3c4\uba74",
        "\uaddc\uaca9",
        "\ud22c\uc790",
        "\uc6b4\uc601",
    ]
    return any(marker in lowered for marker in english_markers) or any(marker in lowered for marker in korean_markers)


def _function_call_count(path: Path, names: Set[str]) -> int:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("function-call counting requires indexed event facts")
    normalized = tuple(dict.fromkeys(str(name) for name in names))
    if not normalized:
        return 0
    placeholders = ",".join("?" for _ in normalized)
    row = events._db.execute(
        f"""
        SELECT COUNT(*) FROM events
        WHERE payload_type IN ('function_call', 'custom_tool_call')
          AND name IN ({placeholders})
        """,
        normalized,
    ).fetchone()
    return int(row[0]) if row else 0


def _implementation_tool_samples(path: Path) -> List[str]:
    samples: List[str] = []
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("implementation sampling requires indexed event facts")
    for _event_seq, payload in events.iter_payloads(
        payload_types=("function_call", "custom_tool_call")
    ):
        payload_type = str(payload.get("type", ""))
        if payload_type not in {"function_call", "custom_tool_call"}:
            continue
        name = str(payload.get("name", ""))
        text = _payload_text(payload)
        lowered = text.lower()
        if name == "shell_command" and _looks_like_front_door_prompt_bootstrap(lowered):
            continue
        if name in {"apply_patch", "imagegen"} or "apply_patch" in lowered:
            samples.append(_short(text))
        elif name == "shell_command" and any(
            marker in lowered
            for marker in [
                "new-item",
                "copy-item",
                "set-content",
                "out-file",
                "start-process",
                "node --check",
                "python -m http.server",
            ]
        ):
            samples.append(_short(text))
        if len(samples) >= 5:
            break
    return samples


def _claims_brainstorming_complete_or_next_stage(lowered: str) -> bool:
    return any(
        marker in lowered
        for marker in [
            "brainstorming complete",
            "brainstorming is complete",
            "handoff complete",
            "ready for planning",
            "ready to implement",
            "implementation scope",
            "next step is implementation",
            "i will implement",
            "i will create",
            "\ube0c\ub808\uc778\uc2a4\ud1a0\ubc0d \uc644\ub8cc",
            "\ud578\ub4dc\uc624\ud504 \uc644\ub8cc",
            "\uacc4\ud68d\uc73c\ub85c \ub118\uc5b4",
            "\uad6c\ud604 \ubc94\uc704",
            "\uad6c\ud604\ud558\uaca0\uc2b5\ub2c8\ub2e4",
            "\ud30c\uc77c\uc744 \uc0dd\uc131",
        ]
    )


def _is_subagent_session(path: Path) -> bool:
    payload = _session_metadata(path)
    if str(payload.get("thread_source", "")).lower() == "subagent":
        return True
    source = payload.get("source", {}) or {}
    return isinstance(source, dict) and isinstance(source.get("subagent"), dict)


def _has_subagent_strategy_rationale(lowered: str) -> bool:
    if "subagent_strategy=dispatch|single-controller" in lowered:
        return False
    match = re.search(r"\bsubagent_strategy\s*[:=]\s*(dispatch|single-controller|review-only|blocked)\b", lowered)
    if match:
        strategy = match.group(1)
        if strategy == "dispatch":
            return True
        return _has_no_subagent_rationale(lowered)
    if re.search(r"\bnested_subagents_available\s*[:=]\s*(true|false|yes|no)\b", lowered):
        return _has_no_subagent_rationale(lowered)
    return any(
        marker in lowered
        for marker in [
            "host-limited single-controller",
            "no-subagent rationale",
            "subagents unavailable",
            "subagents are unavailable",
        ]
    )


def _has_no_subagent_rationale(lowered: str) -> bool:
    return any(
        marker in lowered
        for marker in [
            "host_limited=true",
            "host-limited",
            "host limited",
            "nested_subagents_unavailable=true",
            "nested subagents unavailable",
            "nested subagents are unavailable",
            "subagents unavailable",
            "subagents are unavailable",
            "sequential",
            "tiny",
            "single file",
            "small task",
            "shared-state",
            "shared state",
            "shared write set",
            "too coupled",
            "not useful",
            "blocked",
            "permission",
            "review-only",
        ]
    )


def _has_parallel_strategy_rationale(lowered: str) -> bool:
    match = re.search(
        r"\bparallel_strategy(?:_decision)?\s*[:=]\s*"
        r"(parallel|sequential|read-only-side-agents|read_only_side_agents|blocked)\b",
        lowered,
    )
    if match:
        strategy = match.group(1).replace("_", "-")
        if strategy == "parallel":
            return _has_parallel_execution_evidence(lowered)
        return _has_no_parallel_rationale(lowered)
    if "parallel_strategy_decision=parallel" in lowered:
        return _has_parallel_execution_evidence(lowered)
    return any(
        marker in lowered
        for marker in [
            "parallel_strategy_decision=sequential",
            "parallel_strategy_decision=blocked",
            "parallel_strategy_decision=read-only-side-agents",
            "parallel not useful",
            "no-parallel rationale",
            "shared-state risk",
            "shared state risk",
            "sequential with rationale",
        ]
    )


def _has_no_parallel_rationale(lowered: str) -> bool:
    return any(
        marker in lowered
        for marker in [
            "sequential with rationale",
            "no-parallel rationale",
            "parallel not useful",
            "shared-state risk",
            "shared state risk",
            "shared-state",
            "shared state",
            "tiny",
            "single file",
            "small task",
            "blocked",
            "read-only-side-agents",
            "read_only_side_agents",
        ]
    )


def _has_parallel_execution_evidence(lowered: str) -> bool:
    return (
        ("fan-out" in lowered or "fan_out" in lowered)
        and ("fan-in" in lowered or "fan_in" in lowered)
    ) or any(
        marker in lowered
        for marker in [
            "parallel_wave_count",
            "parallel wave count",
            "parallel waves",
            "role results",
            "role_results",
            "fan_in_complete",
        ]
    )


def _has_role_execution_audit_rationale(lowered: str) -> bool:
    if re.search(r"\brole_execution_audit(?:\.status)?\s*[:=]\s*(passed|failed|skipped|blocked)\b", lowered):
        return True
    return any(
        marker in lowered
        for marker in [
            "role execution audited",
            "role_execution_audit.status",
            "role artifacts",
            "parallel wave",
            "role results",
            "skipped_with_rationale",
            "considered_not_needed",
            "blocked",
        ]
    )


def _session_has_implementation_activity(path: Path, postmortem: Dict[str, Any], lowered: str) -> bool:
    if _implementation_tool_samples(path):
        return True
    if postmortem.get("verification_commands"):
        return True
    return _has_implementation_execution_signal(lowered)


def _has_implementation_execution_signal(lowered: str) -> bool:
    non_prompt_write = any(
        marker in lowered
        for marker in [
            "*** begin patch",
            "add file:",
            "update file:",
            "apply_patch",
            "new-item",
            "out-file",
            "copy-item",
            "move-item",
            "files changed",
            "file changed",
            "created index.html",
            "created styles.css",
            "created app.js",
            "wrote index.html",
            "wrote styles.css",
            "wrote app.js",
        ]
    )
    if non_prompt_write:
        return True
    if "set-content" not in lowered:
        return False
    return not _looks_like_front_door_prompt_bootstrap(lowered)


def _looks_like_front_door_prompt_bootstrap(lowered: str) -> bool:
    return (
        "set-content" in lowered
        and "kh-front-door-prompt.txt" in lowered
        and ("front_door.py" in lowered or "kh_front_door" in lowered)
    )


def _cross_scope_context_sample(target: Path, text: str) -> str:
    lowered = text.lower()
    if not any(marker in lowered for marker in ["get-childitem", "get-content", "select-string", "rg ", "test-path"]):
        return ""
    parent = target.parent
    for raw_path in _extract_windows_paths(text):
        candidate = _normalize_path(Path(raw_path))
        if candidate == target or _path_is_relative_to(candidate, target):
            continue
        if candidate == parent:
            return _short(f"parent folder scan: {raw_path}")
        if not _path_is_relative_to(candidate, parent):
            continue
        try:
            sibling_name = candidate.relative_to(parent).parts[0]
        except ValueError:
            continue
        if sibling_name != target.name and _shares_run_prefix(sibling_name, target.name):
            return _short(f"sibling run read: {raw_path}")
    return ""


def _target_substitution_sample(target: Path, text: str) -> str:
    target_name = target.name
    if not target_name:
        return ""
    normalized_target = str(target).lower()
    normalized_text = (text or "").replace("\\", "/")
    lowered = normalized_text.lower()
    staging_markers = [
        "staging",
        "staged",
        "workspace-local",
        "workspace local",
        "current workspace",
        "created in workspace",
        "not placed in the final folder",
        "not copied to the final folder",
        "\uc2a4\ud14c\uc774\uc9d5",
        "\uc791\uc5c5\uacf5\uac04",
        "\ucd5c\uc885 \ud3f4\ub354\uc5d0\ub294 \uc544\uc9c1",
    ]
    artifact_markers = [
        "index.html",
        "styles.css",
        "style.css",
        "app.js",
        "script.js",
        "package.json",
        "readme.md",
    ]
    if any(marker in lowered for marker in staging_markers) and any(
        marker in lowered for marker in artifact_markers
    ):
        return _short(f"workspace staging used for absolute target {target}: {text}")

    if normalized_target.replace("\\", "/") in lowered:
        return ""
    relative_prefix = f"{target_name}/".lower()
    patch_markers = [
        f"*** add file: {relative_prefix}",
        f"*** update file: {relative_prefix}",
        f"*** delete file: {relative_prefix}",
        f"*** move to: {relative_prefix}",
    ]
    shell_markers = [
        f"new-item {relative_prefix}",
        f"set-content {relative_prefix}",
        f"out-file {relative_prefix}",
        f"copy-item {relative_prefix}",
    ]
    output_markers = [
        f"a {relative_prefix}",
        f"m {relative_prefix}",
        f"updated file: {relative_prefix}",
        f"created file: {relative_prefix}",
    ]
    root_artifact_markers = [
        "*** add file: index.html",
        "*** add file: styles.css",
        "*** add file: style.css",
        "*** add file: app.js",
        "*** add file: script.js",
        "new-item index.html",
        "set-content index.html",
        "out-file index.html",
        "created file: index.html",
        "updated file: index.html",
    ]
    if any(marker in lowered for marker in patch_markers + shell_markers + output_markers):
        return _short(f"relative substitute target for {target}: {text}")
    if any(marker in lowered for marker in root_artifact_markers):
        return _short(f"workspace-root artifact for absolute target {target}: {text}")
    return ""


def _global_codex_memory_sample(text: str) -> str:
    lowered = text.lower()
    normalized = lowered.replace("\\\\", "\\")
    if not any(marker in lowered for marker in ["get-content", "select-string", "rg ", "test-path"]):
        return ""
    if ".codex\\memories" in normalized or ".codex/memories" in normalized:
        return _short(f"global Codex memory read: {text}")
    if "\\memories\\memory.md" in normalized or "/memories/memory.md" in normalized:
        return _short(f"global memory index read: {text}")
    return ""


def _global_codex_memory_citation_sample(payload: Dict[str, Any]) -> str:
    if not _is_user_facing_memory_citation_payload(payload):
        return ""
    citation = payload.get("memory_citation")
    if isinstance(citation, dict):
        entries = citation.get("entries") or []
        cited_paths = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cited_path = str(entry.get("path", ""))
            normalized = cited_path.replace("\\", "/").lower()
            if normalized == "memory.md" or normalized.startswith("memories/"):
                cited_paths.append(cited_path)
        if cited_paths:
            return _short(f"global Codex memory citation: {', '.join(cited_paths)}")

    text = _payload_text(payload)
    lowered = text.lower()
    if "<oai-mem-citation>" not in lowered:
        return ""
    if re.search(r"(?:^|\n)\s*(?:memory\.md|memories[/\\][^:\n]+):\d+", lowered):
        return _short(f"global Codex memory citation: {text}")
    return ""


def _is_user_facing_memory_citation_payload(payload: Dict[str, Any]) -> bool:
    payload_type = str(payload.get("type", ""))
    role = str(payload.get("role", "")).lower()
    if payload_type == "message":
        return role == "assistant"
    if payload_type == "agent_message":
        phase = str(payload.get("phase", "")).lower()
        return phase == "final_answer"
    if payload_type == "task_complete":
        return True
    return False


def _extract_windows_paths(text: str) -> List[str]:
    paths = []
    for match in re.finditer(r"[A-Za-z]:\\[^\s\"'`<>|]+", text):
        value = match.group(0).rstrip(".,;:)]}")
        if value:
            paths.append(value)
    return paths


def _normalize_path(path: Path) -> Path:
    return Path(str(path).rstrip("\\/")).resolve(strict=False)


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _shares_run_prefix(left: str, right: str) -> bool:
    left_parts = left.lower().split("_")
    right_parts = right.lower().split("_")
    if len(left_parts) < 2 or len(right_parts) < 2:
        return False
    return left_parts[:-1] == right_parts[:-1]


def _payload_is_explicit_global_memory_import_request(payload: Dict[str, Any]) -> bool:
    if str(payload.get("type", "")) != "message":
        return False
    if str(payload.get("role", "")).lower() != "user":
        return False
    return _text_is_explicit_global_memory_import_request(_payload_text(payload))


def _text_is_explicit_global_memory_import_request(text: str) -> bool:
    scope_markers = [
        "global memory",
        "host global memory",
        "codex memory",
        "memory.md",
        ".codex\\memories",
        ".codex/memories",
        "\uc804\uc5ed \uba54\ubaa8\ub9ac",
        "\uc804\uc5ed \uae30\uc5b5",
        "\uc2dc\uc2a4\ud15c \uba54\ubaa8\ub9ac",
        "\uc2dc\uc2a4\ud15c \uae30\uc5b5",
        "\ucf54\ub371\uc2a4 \uba54\ubaa8\ub9ac",
        "\ucf54\ub371\uc2a4 \uae30\uc5b5",
        "\uae00\ub85c\ubc8c \uba54\ubaa8\ub9ac",
    ]
    cross_scope_markers = [
        "global memory",
        "host global memory",
        "codex memory",
        "memory.md",
        "memories",
        ".codex\\memories",
        ".codex/memories",
        "\uc804\uc5ed \uba54\ubaa8\ub9ac",
        "\uc804\uc5ed \uae30\uc5b5",
        "\uc2dc\uc2a4\ud15c \uba54\ubaa8\ub9ac",
        "\uc2dc\uc2a4\ud15c \uae30\uc5b5",
        "\ucf54\ub371\uc2a4 \uba54\ubaa8\ub9ac",
        "\ucf54\ub371\uc2a4 \uae30\uc5b5",
        "\uae00\ub85c\ubc8c \uba54\ubaa8\ub9ac",
    ]
    action_markers = [
        "read",
        "load",
        "import",
        "reuse",
        "use previous",
        "use prior",
        "reference",
        "look at",
        "check",
        "inspect",
        "analyze",
        "review the previous",
        "\uc77d",
        "\ubd10",
        "\ubcf4",
        "\uc870\ud68c",
        "\ud655\uc778",
        "\ucc38\uc870",
        "\uac00\uc838",
        "\ubd88\ub7ec",
        "\ubd84\uc11d",
        "\uc7ac\ud65c\uc6a9",
    ]
    negation_markers = [
        "do not read",
        "don't read",
        "do not use",
        "don't use",
        "without memory",
        "no memory",
        "\uc77d\uc9c0\ub9c8",
        "\uc77d\uc9c0 \ub9c8",
        "\uc4f0\uc9c0\ub9c8",
        "\uc4f0\uc9c0 \ub9c8",
        "\uc0ac\uc6a9\ud558\uc9c0\ub9c8",
        "\ucc38\uc870\ud558\uc9c0\ub9c8",
        "\uba54\ubaa8\ub9ac \uc5c6\uc774",
    ]
    lowered = text.lower()
    if any(marker in lowered for marker in negation_markers):
        return False
    has_scope_topic = any(marker in lowered for marker in scope_markers)
    has_cross_scope = any(marker in lowered for marker in cross_scope_markers)
    has_action = any(marker in lowered for marker in action_markers)
    if has_cross_scope and has_action:
        return True
    if "memory.md" in lowered and has_action:
        return True
    if has_scope_topic and has_action:
        return True
    return False


def _session_has_explicit_global_memory_import_request(path: Path) -> bool:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("memory import detection requires indexed event facts")
    return any(
        _payload_is_explicit_global_memory_import_request(payload)
        for _event_seq, payload in events.iter_payloads(
            payload_types=("message",),
            roles=("user",),
        )
    )


def _payload_has_scoped_memory_import_approval(
    payload: Dict[str, Any],
    metadata: Mapping[str, Any],
) -> bool:
    return _structured_user_memory_import_decision(payload, metadata) == "approve"


def _session_has_scoped_memory_import_evidence(path: Path) -> bool:
    events = _session_payload_events(path)
    active = False
    for decision in _memory_import_approval_decisions(
        events,
        _session_metadata(path),
    ).values():
        active = decision == "approve"
    return active


def _is_authenticated_memory_import_approval_receipt(
    receipt: CorrelatedToolReceipt,
    metadata: Mapping[str, Any],
) -> bool:
    return _authenticated_memory_import_decision(receipt, metadata) == "approve"


def _authenticated_memory_import_decision(
    receipt: CorrelatedToolReceipt,
    metadata: Mapping[str, Any],
) -> str:
    tool_identity = str(receipt.call.get("tool_identity", "") or "").strip().lower()
    if tool_identity not in _AUTHENTICATED_MEMORY_APPROVAL_TOOLS:
        return ""
    data = receipt.data if isinstance(receipt.data, Mapping) else {}
    approval = data.get("memory_import_approval", data)
    if not isinstance(approval, Mapping):
        return ""
    if str(approval.get("application_status", "") or "") != "applied":
        return ""
    return _validated_memory_import_decision(approval, metadata, exact_keys=False)


def _memory_import_approval_decisions(
    events: Sequence[Dict[str, Any]],
    metadata: Mapping[str, Any],
) -> Mapping[int, str]:
    if isinstance(events, DiskBackedSessionEvents):
        return events.memory_import_decisions(metadata)
    raise RuntimeError("memory approval decisions require the streaming fact store")


def _structured_user_memory_import_decision(
    payload: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> str:
    if str(payload.get("type", "")) != "message":
        return ""
    if str(payload.get("role", "")).strip().lower() != "user":
        return ""
    directive = _standalone_memory_import_directive(payload)
    if directive is None:
        return ""
    return _validated_memory_import_decision(directive, metadata, exact_keys=True)


def _standalone_memory_import_directive(
    payload: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    embedded = payload.get("memory_import_directive")
    if isinstance(embedded, Mapping):
        if _content_text(payload.get("content")).strip():
            return None
        return embedded

    content = payload.get("content")
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list) and len(content) == 1:
        item = content[0]
        if not isinstance(item, Mapping):
            return None
        if set(item) - {"type", "text"}:
            return None
        if str(item.get("type", "")) not in {"input_text", "text"}:
            return None
        if not isinstance(item.get("text"), str):
            return None
        text = str(item["text"])
    else:
        return None
    stripped = text.strip()
    if not stripped.startswith("{") or not stripped.endswith("}"):
        return None
    try:
        value = load_json_without_duplicate_keys(stripped)
    except (json.JSONDecodeError, DuplicateJsonKeyError):
        return None
    return value if isinstance(value, Mapping) else None


def _validated_memory_import_decision(
    directive: Mapping[str, Any],
    metadata: Mapping[str, Any],
    *,
    exact_keys: bool,
) -> str:
    if exact_keys and set(directive) != _MEMORY_IMPORT_DIRECTIVE_KEYS:
        return ""
    if not _MEMORY_IMPORT_DIRECTIVE_KEYS.issubset(directive):
        return ""
    if directive.get("claim_kind") != "kh_memory_import_approval":
        return ""
    if directive.get("scope") != "host-global":
        return ""
    expected_project = metadata.get("cwd")
    expected_conversation = metadata.get("thread_id") or metadata.get("id")
    if type(expected_project) is not str or not expected_project:
        return ""
    if type(expected_conversation) is not str or not expected_conversation:
        return ""
    project = directive.get("project")
    conversation_id = directive.get("conversation_id")
    if type(project) is not str or type(conversation_id) is not str:
        return ""
    if _session_path_key(Path(project)) != _session_path_key(Path(expected_project)):
        return ""
    if conversation_id != expected_conversation:
        return ""

    action = directive.get("action")
    approval_state = directive.get("approval_state")
    approved = directive.get("memory_import_approved")
    if action == "approve" and approval_state == "approved" and approved is True:
        return "approve"
    if action == "revoke" and approval_state == "revoked" and approved is False:
        return "revoke"
    return ""


def _is_stale_kh_skill_cache_failure(lowered: str) -> bool:
    if "kh-uaf-marketplace" not in lowered or "kh-uaf" not in lowered:
        return False
    if "\\skills\\" not in lowered and "/skills/" not in lowered:
        return False
    return any(
        marker in lowered
        for marker in [
            "not found",
            "does not exist",
            "cannot find path",
            "pathnotfound",
            "존재하지",
            "찾을 수 없습니다",
        ]
    )


def _session_payload_events(path: Path) -> Sequence[Dict[str, Any]]:
    index = _current_session_event_index(path)
    if index is None:
        index = _build_session_event_index(path)
    index.payload_events.note_check()
    return index.payload_events


def _session_path_key(path: Path) -> str:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path.absolute()
    return str(resolved).replace("\\", "/").casefold()


def _current_session_event_index(path: Path) -> SessionEventIndex | None:
    index = _SESSION_EVENT_INDEX.get()
    if index is None or index.path_key != _session_path_key(path):
        return None
    return index


def _session_index_text_requires_lossless_capture(root_key: str, value: str) -> bool:
    if root_key not in {"output", "packet"}:
        return False
    return any(marker in value for marker in _SESSION_INDEX_REQUIRED_EVIDENCE_MARKERS)


def _bounded_session_index_value(
    value: Any,
    *,
    root_key: str,
) -> Any:
    if isinstance(value, str):
        if len(value) <= _SESSION_INDEX_TEXT_CAPTURE_LIMIT or _session_index_text_requires_lossless_capture(
            root_key,
            value,
        ):
            return value
        marker = (
            "\n[KH_SESSION_INDEX_TRUNCATED "
            f"characters={len(value)}]\n"
        )
        return (
            value[:_SESSION_INDEX_TEXT_CAPTURE_EDGE]
            + marker
            + value[-_SESSION_INDEX_TEXT_CAPTURE_EDGE:]
        )
    if isinstance(value, Mapping):
        return {
            str(key): _bounded_session_index_value(
                item,
                root_key=root_key,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _bounded_session_index_value(
                item,
                root_key=root_key,
            )
            for item in value
        ]
    return value


def _compact_session_event(event: Mapping[str, Any]) -> Dict[str, Any]:
    payload = event.get("payload")
    compact_payload: Dict[str, Any] = {}
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key not in _SESSION_EVENT_PAYLOAD_KEYS:
                continue
            compact_payload[key] = _bounded_session_index_value(
                value,
                root_key=key,
            )
    compact_event: Dict[str, Any] = {
        "type": str(event.get("type") or ""),
        "payload": compact_payload,
    }
    if "timestamp" in event:
        compact_event["timestamp"] = event.get("timestamp")
    return compact_event


def _compact_session_metadata(payload: Mapping[str, Any]) -> Dict[str, Any]:
    metadata = {
        key: _bounded_session_index_value(
            payload[key],
            root_key=key,
        )
        for key in _SESSION_METADATA_KEYS
        if key in payload
    }
    return metadata


def _retained_python_bytes(value: Any, seen: Set[int] | None = None) -> int:
    seen = seen if seen is not None else set()
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    size = sys.getsizeof(value)
    if isinstance(value, Mapping):
        size += sum(
            _retained_python_bytes(key, seen) + _retained_python_bytes(item, seen)
            for key, item in value.items()
        )
    elif isinstance(value, (list, tuple, set, frozenset)):
        size += sum(_retained_python_bytes(item, seen) for item in value)
    return size


def _build_session_event_index(
    path: Path,
    *,
    collect_stage_telemetry: bool = False,
) -> SessionEventIndex:
    catalog = collect_packaged_skills()
    pipeline = AuditStreamPipeline(
        path,
        catalog=catalog,
        collect_stage_telemetry=collect_stage_telemetry,
    )
    try:
        postmortem = analyze_codex_session_jsonl(path, event_stream=pipeline.stream())
        index = pipeline.finalize(postmortem=postmortem)
        return index
    except Exception:
        pipeline.close()
        raise


def _payload_call_id(payload: Dict[str, Any]) -> str:
    return str(payload.get("call_id", "") or payload.get("tool_call_id", "")).strip()


def _correlated_front_door_receipts(
    events: Sequence[Dict[str, Any]],
) -> Mapping[int, CorrelatedFrontDoorReceipt]:
    if isinstance(events, DiskBackedSessionEvents):
        return events.correlated_front_door_receipts()
    raise RuntimeError("front-door receipts require the streaming fact store")


def _duplicate_front_door_boundaries(events: Sequence[Dict[str, Any]]) -> Any:
    if isinstance(events, DiskBackedSessionEvents):
        return DiskBackedDuplicateFactKeys(events, "boundary")
    counts: Dict[str, int] = {}
    for event in events:
        if str(event.get("type", "")) != "response_item":
            continue
        payload = event.get("payload", {})
        if not isinstance(payload, Mapping):
            continue
        if str(payload.get("type", "")) not in {"function_call", "custom_tool_call"}:
            continue
        boundary_id = str(payload.get("boundary_id", "") or "").strip()
        if boundary_id:
            counts[boundary_id] = counts.get(boundary_id, 0) + 1
    return {boundary_id for boundary_id, count in counts.items() if count > 1}


def _valid_host_front_door_provenance(
    call: Mapping[str, Any],
    output: Mapping[str, Any],
    packet: Mapping[str, Any],
    *,
    duplicate_boundaries: Set[str],
    duplicate_packet_hashes: Set[str] | None = None,
) -> bool:
    """Validate structural host provenance; JSONL authenticity is not established here."""
    call_id = _payload_call_id(dict(call))
    if not call_id or call_id != _payload_call_id(dict(output)):
        return False

    source = _front_door_provenance_value(call, "source", "host", "origin")
    output_source = _front_door_provenance_value(output, "source", "host", "origin")
    if source not in _KNOWN_HOST_FRONT_DOOR_SOURCES or output_source != source:
        return False

    tool_identity = str(call.get("tool_identity", "") or "").strip().lower()
    output_tool_identity = str(output.get("tool_identity", "") or "").strip().lower()
    call_name = str(call.get("name", "") or "").strip().lower()
    if not tool_identity or tool_identity != output_tool_identity or tool_identity != call_name:
        return False
    if not _is_front_door_runtime_command(dict(call), _payload_text(dict(call)).lower()):
        return False

    boundary_id = str(call.get("boundary_id", "") or "").strip()
    if (
        not boundary_id
        or boundary_id in duplicate_boundaries
        or str(output.get("boundary_id", "") or "").strip() != boundary_id
        or (
            str(packet.get("boundary_id", "") or "").strip()
            and str(packet.get("boundary_id", "") or "").strip() != boundary_id
        )
    ):
        return False

    correlation_id = str(
        packet.get("correlation_id", "")
        or output.get("correlation_id", "")
    ).strip()
    if (
        correlation_id != call_id
        or str(call.get("correlation_id", "") or "").strip() != call_id
        or str(output.get("correlation_id", "") or "").strip() != call_id
    ):
        return False

    packet_hash = _front_door_packet_hash_value(packet)
    supplied_packet_hash = str(
        packet.get("packet_sha256", "")
        or packet.get("packet_hash", "")
        or output.get("packet_sha256", "")
        or output.get("packet_hash", "")
    ).strip().lower()
    if (
        not packet_hash
        or not supplied_packet_hash
        or packet_hash != supplied_packet_hash
        or packet_hash in (duplicate_packet_hashes or set())
    ):
        return False
    return str(output.get("packet_sha256", "") or output.get("packet_hash", "")).strip().lower() == packet_hash


def _front_door_provenance_value(payload: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = str(payload.get(key, "") or "").strip().lower()
        if value:
            return value
    return ""


def _front_door_packet_hash_value(
    packet: Mapping[str, Any],
    *,
    supplied: bool = False,
) -> str:
    if supplied:
        return str(packet.get("packet_sha256", "") or packet.get("packet_hash", "")).strip().lower()
    unsigned = {
        str(key): value
        for key, value in packet.items()
        if str(key) not in _FRONT_DOOR_PACKET_HASH_KEYS
    }
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _front_door_output_succeeded(
    payload: Dict[str, Any],
    call_payload: Dict[str, Any],
) -> bool:
    recorded_exit_codes: List[int] = []
    for key in ["exit_code", "return_code"]:
        if key in payload:
            if type(payload[key]) is not int:
                return False
            recorded_exit_codes.append(payload[key])
    text = _strip_passive_prefix(_payload_text(payload))
    textual_exit_lines = [
        line
        for line in text.splitlines()
        if re.match(r"(?i)^\s*exit\s+code\s*:", line)
    ]
    for line in textual_exit_lines:
        match = re.fullmatch(r"Exit code: (0|[1-9][0-9]*)", line)
        if match is None:
            return False
        recorded_exit_codes.append(int(match.group(1)))
    if any(code != 0 for code in recorded_exit_codes):
        return False

    status = str(payload.get("status", "") or "").strip().lower()
    if status in {"error", "failed", "failure"} or payload.get("success") is False:
        return False
    call_name = str(call_payload.get("name", "") or "").strip().lower()
    if _is_trusted_front_door_tool_name(call_name):
        return bool(recorded_exit_codes) and all(code == 0 for code in recorded_exit_codes)
    return bool(recorded_exit_codes) and all(code == 0 for code in recorded_exit_codes)


def _is_strict_blocked_front_door_packet(data: Dict[str, Any]) -> bool:
    if _is_valid_verbose_blocked_front_door_packet(data):
        return str(data.get("front_door_status", "")).strip().lower() == "ok"
    if not (
        _is_valid_compact_front_door_packet(data)
        or _is_valid_normalized_micro_front_door_packet(data)
    ):
        return False
    if str(data.get("front_door_status", "")).strip().lower() != "ok":
        return False

    route = data.get("plugin_route", {}) or {}
    return bool(
        route.get("route") in {"single", "hybrid", "clarify"}
        and _has_blocked_front_door_contract(data)
    )


def _is_valid_verbose_blocked_front_door_packet(data: Dict[str, Any]) -> bool:
    classification = data.get("classification", {})
    route = data.get("plugin_route", {})
    gate = data.get("execution_gate", {})
    authorization = data.get("execution_authorization", {})
    return bool(
        isinstance(data.get("token_optimizer_decision"), dict)
        and isinstance(classification, dict)
        and str(classification.get("complexity", "")).strip()
        and str(classification.get("recommended_execution", "")).strip()
        and isinstance(route, dict)
        and route.get("route") in {"direct", "single", "hybrid", "clarify"}
        and isinstance(gate, dict)
        and isinstance(authorization, dict)
        and _has_blocked_front_door_contract(data)
    )


def _has_blocked_front_door_contract(data: Mapping[str, Any]) -> bool:
    gate = data.get("execution_gate", {}) or {}
    authorization = data.get("execution_authorization", {}) or {}
    action_codes = data.get("required_next_action_codes")
    if not isinstance(gate, Mapping) or not isinstance(authorization, Mapping):
        return False
    gate_status = str(gate.get("status", "") or "").strip().lower()
    authorization_status = str(authorization.get("status", "") or "").strip().lower()
    current_gate_contract = bool(
        gate.get("can_execute") is False and gate_status.startswith("blocked_")
    )
    legacy_gate_contract = bool(
        gate.get("can_execute") is True
        and gate_status == "execution_allowed_after_selected_skill_setup"
    )
    return bool(
        (current_gate_contract or legacy_gate_contract)
        and authorization.get("must_stop_before_execution") is True
        and authorization_status
        in {
            "blocked_by_execution_gate",
            "blocked_by_pending_immediate_skill_gate",
        }
        and isinstance(action_codes, list)
        and action_codes
        and all(isinstance(code, str) and code.strip() for code in action_codes)
        and "stop_before_task_work" in action_codes
        and "apply_immediate_next_skills" in action_codes
    )


def _latest_actual_runtime_token_optimizer_decision(
    events: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    if isinstance(events, DiskBackedSessionEvents):
        latest: Dict[str, Any] = {}
        latest_seq = -1
        for event_seq, payload in events.iter_payloads(
            payload_types=("thread_goal_updated",)
        ):
            if not _has_explicit_token_optimizer_runtime_source(payload):
                continue
            decision = _actual_runtime_token_optimizer_decision(
                _canonical_json(payload)
            )
            if decision and event_seq > latest_seq:
                latest_seq = event_seq
                latest = decision
        for receipt in events.correlated_tool_receipts(include_failed=False):
            if not _is_token_optimizer_runtime_command(
                _payload_text(receipt.call).lower()
            ):
                continue
            decision = _actual_runtime_token_optimizer_decision(
                _payload_text(receipt.output)
            )
            if decision and receipt.output_index > latest_seq:
                latest_seq = receipt.output_index
                latest = decision
        return latest
    raise RuntimeError("token optimizer correlation requires the streaming fact store")


def _runtime_tool_output_succeeded(payload: Dict[str, Any]) -> bool:
    controls: List[Dict[str, Any]] = [payload]
    text = _payload_text(payload)
    data = _json_object_from_text(text)
    if data:
        controls.append(data)

    if any(_runtime_mapping_failed(control) for control in controls):
        return False

    if re.search(r"(?im)\bexit\s+code\s*:\s*(?!0\b)-?\d+\b", text):
        return False
    return "script failed" not in text.lower()


def _runtime_mapping_failed(control: Dict[str, Any]) -> bool:
    status = str(control.get("status", "") or "").strip().lower()
    if status in {"error", "failed", "failure"} or control.get("success") is False:
        return True
    for key in ["exit_code", "return_code", "returncode"]:
        if key not in control:
            continue
        try:
            if int(control[key]) != 0:
                return True
        except (TypeError, ValueError):
            return True
    return False


def _actual_runtime_token_optimizer_decision(text: str) -> Dict[str, Any]:
    data = _json_object_from_text(text)
    if not data:
        return {}
    candidates: List[Dict[str, Any]] = []

    def visit(value: Any, runtime_scope: bool = False) -> None:
        if isinstance(value, dict):
            if _runtime_mapping_failed(value):
                return
            source = str(value.get("source", "") or "").lower()
            scoped = runtime_scope or any(
                marker in source
                for marker in [
                    "src.skills.token_optimizer",
                    "src.orchestration.runtime_token_optimizer",
                    "optimize_workflow_task_results",
                ]
            )
            status = str(value.get("status", "") or value.get("token_optimizer_status", "")).strip()
            reason = str(
                value.get("blocked_reason", "")
                or value.get("not_used_reason", "")
                or value.get("reason_code", "")
                or value.get("token_optimizer_status_reason", "")
            ).strip()
            provider = str(
                value.get("token_optimizer_provider", "")
                or value.get("provider", "")
            ).strip()
            explicit_runtime_source = _has_explicit_token_optimizer_runtime_source(value)
            valid_passthrough = bool(
                status == "passthrough"
                and provider in {"kh", "rtk", "hybrid"}
                and explicit_runtime_source
                and reason
            )
            if scoped and (status in {"used", "blocked"} or valid_passthrough):
                candidates.append(
                    {
                        "status": status,
                        "reason": reason or f"runtime_optimizer_status_{status}",
                    }
                )
            for key, item in value.items():
                visit(
                    item,
                    scoped
                    or str(key).lower()
                    in {"runtime_token_optimization", "runtime_token_optimizer", "token_optimization"},
                )
        elif isinstance(value, list):
            for item in value:
                visit(item, runtime_scope)

    visit(data)
    return candidates[-1] if candidates else {}


def _has_explicit_token_optimizer_runtime_source(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in {"source", "decision_source"}:
                source = str(item).lower()
                if any(
                    marker in source
                    for marker in [
                        "src.skills.token_optimizer",
                        "src.orchestration.runtime_token_optimizer",
                        "optimize_workflow_task_results",
                    ]
                ):
                    return True
            if _has_explicit_token_optimizer_runtime_source(item):
                return True
    elif isinstance(value, list):
        return any(_has_explicit_token_optimizer_runtime_source(item) for item in value)
    return False


def _has_full_summary_token_output(events: Sequence[Dict[str, Any]]) -> bool:
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("token output detection requires indexed event facts")
    for _index, payload in events.iter_payloads(
        payload_types=("function_call_output", "custom_tool_call_output")
    ):
        data = _json_object_from_text(_payload_text(payload))
        if isinstance(data.get("token_optimizer_decision"), dict):
            return True
    return False


def _threshold_token_gate_required(token_gate: Dict[str, Any]) -> bool:
    reasons = {str(reason) for reason in token_gate.get("reasons", []) or []}
    return bool(
        token_gate.get("required")
        and reasons
        & {"cumulative_tokens_above_threshold", "context_ratio_above_threshold"}
    )


def _apply_front_door_token_optimizer_evidence(
    path: Path,
    postmortem: Dict[str, Any],
) -> int:
    events = _session_payload_events(path)
    correlated_receipts = _correlated_front_door_receipts(events)
    full_summary_token_output = _has_full_summary_token_output(events)
    decision_count = 0
    latest_front_door_decision: Dict[str, Any] = {}
    for receipt in correlated_receipts.values():
        data = receipt.data
        token_decision = data.get("token_optimizer", {}) or {}
        if isinstance(token_decision, dict) and str(token_decision.get("status", "")).strip():
            decision_count += 1
            latest_front_door_decision = token_decision

    latest_actual = _latest_actual_runtime_token_optimizer_decision(events)
    has_correlated_runtime_activity = any(
        not _is_front_door_runtime_command(
            receipt.call,
            _payload_text(receipt.call).lower(),
        )
        for receipt in _correlated_tool_receipts(events, include_failed=True)
    )

    evidence = dict(postmortem.get("token_optimizer_evidence", {}) or {})
    evidence["front_door_runtime_provenance"] = {
        "status": "structural_jsonl_correlation_only",
        "external_authenticity": "unverified",
        "note": (
            "The audit proves ordered host call/output correlation, identity, boundary, "
            "correlation, and packet-hash consistency; it cannot prove file-level cryptographic authenticity."
        ),
    }
    existing_receipts = any(
        int(evidence.get(key, 0) or 0) > 0
        for key in [
            "runtime_calls",
            "explicit_usage_records",
            "explicit_passthrough_records",
            "structured_used_records",
            "considered_not_needed_records",
            "blocked_reason_records",
        ]
    )
    full_summary_only_evidence = full_summary_token_output and not latest_actual
    if full_summary_only_evidence:
        existing_receipts = False
    token_gate = dict(postmortem.get("token_gate", {}) or {})
    token_evidence_checked = bool(
        existing_receipts or decision_count or latest_actual or full_summary_only_evidence
    )
    if token_evidence_checked:
        token_gate["checked"] = bool(existing_receipts or decision_count or latest_actual)

    if latest_actual:
        status = str(latest_actual.get("status", "")).strip()
        postmortem["token_optimizer_status"] = status
        postmortem["token_optimizer_status_reason"] = str(latest_actual.get("reason", "") or status)
        token_gate["decision_source"] = "runtime_token_optimizer"
        evidence["latest_actual_runtime_status"] = status
        evidence["latest_actual_runtime_decision"] = dict(latest_actual)
    elif (
        decision_count
        and str(latest_front_door_decision.get("status", "")) == "considered_not_needed"
        and _threshold_token_gate_required(token_gate)
    ):
        status = "blocked"
        reason = (
            "Token gate required by cumulative/context threshold; the front-door "
            "considered_not_needed planning decision is not independent runtime "
            "optimizer, passthrough, or blocked evidence."
        )
        token_gate["decision_source"] = "kh_front_door_planning_insufficient"
        postmortem["token_optimizer_status"] = status
        postmortem["token_optimizer_status_reason"] = reason
        token_gate["satisfied"] = status in {"used", "passthrough"}
    elif decision_count:
        latest = latest_front_door_decision
        status = str(latest.get("status", "")).strip()
        postmortem["token_optimizer_status"] = status
        postmortem["token_optimizer_status_reason"] = str(
            latest.get("reason_code", "") or status
        )
        token_gate["decision_source"] = "kh_front_door_runtime_receipt"
        evidence["front_door_runtime_receipts"] = decision_count
        evidence["latest_front_door_decision"] = dict(latest)
    else:
        evidence.setdefault("front_door_runtime_receipts", 0)
        if not existing_receipts and full_summary_only_evidence:
            postmortem["token_optimizer_status"] = "not_checked"
            postmortem["token_optimizer_status_reason"] = "no runtime token-optimizer receipt"
        elif (
            not existing_receipts
            and not has_correlated_runtime_activity
            and postmortem.get("token_optimizer_status") == "considered_not_needed"
        ):
            token_gate["checked"] = False
            postmortem["token_optimizer_status"] = "not_checked"
            postmortem["token_optimizer_status_reason"] = "no runtime token-optimizer receipt"

    evidence["front_door_runtime_receipts"] = decision_count
    if decision_count:
        evidence["latest_front_door_decision"] = dict(latest_front_door_decision)

    postmortem["token_gate"] = token_gate
    postmortem["token_optimizer_evidence"] = evidence
    return decision_count


def _has_normalized_front_door_receipt(data: Dict[str, Any]) -> bool:
    if not data:
        return False
    status = str(data.get("front_door_status", "")).strip().lower()
    route = data.get("plugin_route", {})
    gate = data.get("execution_gate", {})
    return bool(
        status in {"ok", "success", "passed", "blocked"}
        and isinstance(route, dict)
        and "route" in route
        and isinstance(gate, dict)
        and "can_execute" in gate
    )


def _session_integrity_issues(path: Path) -> List[Dict[str, Any]]:
    index = _current_session_event_index(path)
    if index is None:
        index = _build_session_event_index(path)
        try:
            return [dict(issue) for issue in index.integrity_issues]
        finally:
            index.close()
    return [dict(issue) for issue in index.integrity_issues]


def _duplicate_tool_call_identity_issues(path: Path) -> List[Dict[str, Any]]:
    duplicate_call_ids = _duplicate_tool_call_ids(_session_payload_events(path))
    if not duplicate_call_ids:
        return []
    return [
        {
            "skill": "verification-before-completion-harness",
            "status": "ambiguous_duplicate_tool_call_identity",
            "severity": "P1",
            "reason": (
                "Duplicate function-call or function-output call_id values make tool provenance "
                "ambiguous; no receipt with an ambiguous identity is accepted."
            ),
            "action": "Regenerate the affected tool calls with unique host-issued call_id values.",
            "call_ids": duplicate_call_ids,
            "samples": [],
        }
    ]


def _duplicate_json_key_integrity_issue(
    *,
    line_number: int,
    line: str,
    duplicate_keys: Sequence[str],
) -> Dict[str, Any]:
    keys = _ordered_unique(
        _short(str(key or ""), 160)
        for key in duplicate_keys
    )[:20]
    return {
        "skill": "always-on-front-door",
        "status": "session_jsonl_integrity_error",
        "issue_type": "input_integrity",
        "blocking": True,
        "integrity_code": "duplicate_json_key",
        "severity": "P0",
        "reason": (
            "Duplicate JSON keys make the decoded session event ambiguous; the entire record "
            "is excluded from postmortem and audit semantics instead of accepting last-key-wins values."
        ),
        "action": (
            "Repair or regenerate the duplicate-key session event before accepting any audit result."
        ),
        "line_number": int(line_number),
        "error": "duplicate JSON keys: " + ", ".join(keys),
        "duplicate_keys": keys,
        "sample": _short(line),
    }


def _session_line_integrity_issue(
    *,
    line_number: int,
    line: str,
    duplicate_boundary_field: bool,
    parse_error: str,
) -> Dict[str, Any] | None:
    if parse_error and not duplicate_boundary_field and not _malformed_line_can_hide_task_boundary(line):
        return None
    if not duplicate_boundary_field and not parse_error:
        return None
    duplicate_reason = (
        "Duplicate boundary-bearing JSON keys make a session event ambiguous even when the JSON "
        "is syntactically valid."
    )
    malformed_reason = (
        "Malformed session JSONL can hide a user-request or task-complete boundary, "
        "so front-door acknowledgement reuse cannot be audited safely."
    )
    return {
        "skill": "always-on-front-door",
        "status": "session_jsonl_integrity_error",
        "integrity_code": (
            "duplicate_boundary_field"
            if duplicate_boundary_field
            else "malformed_task_boundary"
        ),
        "severity": "P0",
        "reason": duplicate_reason if duplicate_boundary_field else malformed_reason,
        "action": (
            "Repair or regenerate the ambiguous session event before accepting front-door "
            "ordering or same-task acknowledgement reuse."
        ),
        "line_number": line_number,
        "error": parse_error or "duplicate boundary-bearing JSON key",
        "sample": _short(line),
    }


def _record_bounded_integrity_issue(
    groups: Dict[str, Dict[str, Any]],
    issue: Mapping[str, Any],
) -> None:
    code = str(issue.get("integrity_code", "unknown_integrity_issue") or "unknown_integrity_issue")
    line_number = int(issue.get("line_number", 0) or 0)
    sample = {
        "line_number": line_number,
        "error": str(issue.get("error", "") or ""),
        "sample": str(issue.get("sample", "") or ""),
    }
    current = groups.get(code)
    if current is None:
        current = dict(issue)
        current["occurrences"] = 1
        current["sample_line_numbers"] = [line_number] if line_number else []
        current["samples"] = [sample]
        groups[code] = current
        return
    current["occurrences"] = int(current.get("occurrences", 0) or 0) + 1
    samples = current.get("samples")
    if not isinstance(samples, list):
        samples = []
        current["samples"] = samples
    if len(samples) >= _SESSION_INTEGRITY_SAMPLE_LIMIT:
        return
    samples.append(sample)
    line_numbers = current.get("sample_line_numbers")
    if not isinstance(line_numbers, list):
        line_numbers = []
        current["sample_line_numbers"] = line_numbers
    if line_number:
        line_numbers.append(line_number)


def _malformed_line_can_hide_task_boundary(line: str) -> bool:
    event_fields, payload_fields, structure = _partial_session_json_string_fields(line)
    if structure.get("duplicate_boundary_field"):
        return True
    event_type, event_type_closed = event_fields.get("type", ("", False))
    event_type = _partial_boundary_value(event_type).lower()
    if not event_type:
        if not structure.get("payload_first") or not (
            structure.get("root_unclosed") or structure.get("root_closed_trailing_garbage")
        ):
            return False
        payload_type, payload_type_closed = payload_fields.get("type", ("", False))
        if not payload_type_closed:
            return False
        payload_type = _partial_boundary_value(payload_type).lower()
        if payload_type == "task_complete":
            return True
        if payload_type != "message":
            return False
        role, role_closed = payload_fields.get("role", ("", False))
        return bool(role_closed and _partial_boundary_value(role).lower() == "user")

    if event_type_closed:
        if event_type not in {"response_item", "event_msg"}:
            return False
    elif not any(
        len(event_type) >= 4 and expected.startswith(event_type)
        for expected in ["response_item", "event_msg"]
    ):
        return False

    payload_type, payload_type_closed = payload_fields.get("type", ("", False))
    payload_type = _partial_boundary_value(payload_type).lower()
    if event_type == "event_msg":
        return bool(
            payload_type == "task_complete"
            or (
                not payload_type_closed
                and len(payload_type) >= 4
                and "task_complete".startswith(payload_type)
            )
        )

    if payload_type != "message":
        return bool(
            not payload_type_closed
            and len(payload_type) >= 4
            and "message".startswith(payload_type)
        )

    role, role_closed = payload_fields.get("role", ("", False))
    if not role:
        return True
    role = _partial_boundary_value(role).lower()
    if role_closed:
        return role == "user"
    return "user".startswith(role)


def _partial_boundary_value(value: str) -> str:
    """Ignore line terminators and undecodable trailing bytes in a partial JSON string."""
    return str(value or "").rstrip("\r\n\ufffd")


def _partial_session_json_string_fields(
    line: str,
) -> tuple[
    Dict[str, tuple[str, bool]],
    Dict[str, tuple[str, bool]],
    Dict[str, bool],
]:
    text = str(line or "").rstrip("\r\n")
    if not text.lstrip().startswith("{"):
        return {}, {}, {"payload_first": False, "root_unclosed": False}

    event_fields: Dict[str, tuple[str, bool]] = {}
    payload_fields: Dict[str, tuple[str, bool]] = {}
    first_root_key = ""
    payload_seen = False
    event_keys_seen: Set[str] = set()
    payload_keys_seen: Set[str] = set()
    duplicate_boundary_field = False
    depth = 0
    payload_depth = 0
    root_closed_at = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            if depth == payload_depth:
                payload_depth = 0
            if depth == 1 and not root_closed_at:
                root_closed_at = index + 1
            depth = max(0, depth - 1)
            index += 1
            continue
        if char != '"':
            index += 1
            continue

        key, next_index, key_closed = _scan_partial_json_string(text, index)
        if not key_closed:
            break
        value_index = next_index
        while value_index < len(text) and text[value_index].isspace():
            value_index += 1
        if value_index >= len(text) or text[value_index] != ":":
            index = next_index
            continue
        value_index += 1
        while value_index < len(text) and text[value_index].isspace():
            value_index += 1

        normalized_key = key.lower()
        if depth == 1 and not first_root_key:
            first_root_key = normalized_key
        target = event_fields if depth == 1 else payload_fields if depth == payload_depth else None
        if target is event_fields:
            if normalized_key in {"type", "payload"} and normalized_key in event_keys_seen:
                duplicate_boundary_field = True
            event_keys_seen.add(normalized_key)
        elif target is payload_fields:
            if normalized_key in {"type", "role"} and normalized_key in payload_keys_seen:
                duplicate_boundary_field = True
            payload_keys_seen.add(normalized_key)
        if value_index < len(text) and text[value_index] == '"':
            value, index, value_closed = _scan_partial_json_string(text, value_index)
            if target is not None:
                target[normalized_key] = (value, value_closed)
            continue
        if value_index < len(text) and text[value_index] == "{":
            if depth == 1 and normalized_key == "payload":
                payload_seen = True
                payload_depth = depth + 1
            index = value_index
            continue
        index = max(value_index, next_index)

    return event_fields, payload_fields, {
        "payload_first": payload_seen and first_root_key == "payload",
        "root_unclosed": depth > 0,
        "root_closed_trailing_garbage": bool(
            root_closed_at and text[root_closed_at:].strip()
        ),
        "duplicate_boundary_field": duplicate_boundary_field,
    }


def _scan_partial_json_string(text: str, start: int) -> tuple[str, int, bool]:
    value: List[str] = []
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == '"':
            return "".join(value), index + 1, True
        if char != "\\":
            value.append(char)
            index += 1
            continue
        if index + 1 >= len(text):
            value.append("\ufffd")
            return "".join(value), len(text), False

        escape = text[index + 1]
        simple_escapes = {
            '"': '"',
            "\\": "\\",
            "/": "/",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
        }
        if escape in simple_escapes:
            value.append(simple_escapes[escape])
            index += 2
            continue
        if escape == "u":
            digits = text[index + 2 : index + 6]
            if len(digits) == 4 and re.fullmatch(r"[0-9a-fA-F]{4}", digits):
                value.append(chr(int(digits, 16)))
                index += 6
                continue
        value.append("\ufffd")
        index += 2
    return "".join(value), len(text), False


def _has_auditable_user_request(path: Path) -> bool:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("user request detection requires indexed event facts")
    for _event_seq, payload in events.iter_payloads(
        payload_types=("message",),
        roles=("user",),
    ):
        text = _payload_text(payload)
        if text.strip() and not _is_synthetic_context_message(text):
            return True
    return False


_SAME_TASK_ACKNOWLEDGEMENTS = {
    "y",
    "yes",
    "ok",
    "okay",
    "sure",
    "approved",
    "approve",
    "continue",
    "continue please",
    "go ahead",
    "proceed",
    "thanks",
    "thank you",
    "thank you so much",
    "gracias",
    "merci",
    "danke",
    "s\u00ed",
    "si",
    "oui",
    "ja",
    "\u306f\u3044",
    "\u3042\u308a\u304c\u3068\u3046",
    "\u662f",
    "\u597d\u7684",
    "\u8c22\u8c22",
    "네",
    "예",
    "응",
    "ㅇㅇ",
    "그래",
    "좋아",
    "맞아",
    "알겠어",
    "진행",
    "진행해",
    "진행해줘",
    "계속",
    "계속해",
    "그대로",
    "감사",
    "감사합니다",
    "고마워",
    "고마워요",
}


def _is_explicit_new_objective_transition(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return any(
        marker in normalized
        for marker in [
            "그건 이제 됐고",
            "이건 이제 됐고",
            "그거 말고 다음",
            "다음 작업",
            "다음은 ",
            "새 작업",
            "new task",
            "next task",
            "now inspect the other",
            "now work on the other",
            "switch to the other",
        ]
    )


def _is_same_task_followup(
    text: str,
    previous_assistant_text: str,
    *,
    allow_acknowledgement: bool,
) -> bool:
    raw = str(text or "").strip()
    normalized = re.sub(r"\s+", " ", raw.lower())
    if not normalized or _is_explicit_new_objective_transition(normalized):
        return False
    if _correction_signal(raw, previous_assistant_text)["is_correction"]:
        return True
    if normalized.startswith("# files mentioned by the user:") or "<image name=" in normalized:
        return True
    if re.search(r"(?:^|[\\/])[^\r\n]+\.(?:png|jpe?g|gif|webp|bmp)(?:\s|$)", raw, re.IGNORECASE):
        return True
    if any(
        marker in normalized
        for marker in [
            "스크린샷",
            "첨부한 화면",
            "오류 화면",
            "방금 새로 발급",
            "새로 발급한 거고",
            "메일 주소도 맞",
            "일단 메일주소는 맞",
            "evidence attached",
            "attached screenshot",
        ]
    ):
        return True
    return allow_acknowledgement and _is_bounded_same_task_continuation(raw)


def _is_bounded_same_task_continuation(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
    normalized = normalized.strip(".!?~。！？,，;；:：")
    if not normalized or len(normalized) > 48 or len(normalized.split()) > 6:
        return False
    if normalized in _SAME_TASK_ACKNOWLEDGEMENTS:
        return True
    return bool(
        re.fullmatch(
            r"\d+\s*(?:번|option)?\s*(?:으로|로)?\s*(?:(?:진행|선택)(?:해|해주세요|해줘)?|해|해주세요|해줘)?",
            normalized,
        )
    )


def _is_kh_front_door_request(lowered: str) -> bool:
    if "kh" not in lowered:
        return False
    return any(
        marker in lowered
        for marker in [
            "plugin",
            "플러그",
            "skill",
            "스킬",
            "harness",
            "하네스",
            "uaf",
            "사용",
            "써",
            "쓰",
        ]
    )


def _is_kh_active_directive(text: str) -> bool:
    lowered = text.lower()
    if (
        any(marker in lowered for marker in ["kh", "uaf"])
        and any(marker in lowered for marker in ["\uc2a4\ud0ac", "\ud558\ub124\uc2a4", "skill", "harness"])
        and any(
            marker in lowered
            for marker in ["\uc368", "\uc0ac\uc6a9", "\ud65c\uc6a9", "\uc801\uc6a9", "\ubd88\ub7ec", "use", "apply"]
        )
        and any(
            marker in lowered
            for marker in [
                "\uc55e\uc73c\ub85c",
                "\ud56d\uc0c1",
                "\uae30\ubcf8",
                "\uacc4\uc18d",
                "\uc801\uadf9",
                "\ud6c4\uc18d",
                "\ub098\uc911",
                "\uba85\uc2dc\ud558\uc9c0",
                "\uc790\ub3d9",
                "always",
                "default",
                "actively",
                "future",
            ]
        )
    ):
        return True
    if not any(marker in lowered for marker in ["kh", "uaf"]):
        return False
    if not any(marker in lowered for marker in ["skill", "skills", "harness", "harnesses", "스킬", "하네스"]):
        return False
    if not any(
        marker in lowered
        for marker in [
            "use",
            "using",
            "apply",
            "applied",
            "활용",
            "사용",
            "쓰",
            "적용",
            "불러",
        ]
    ):
        return False
    return any(
        marker in lowered
        for marker in [
            "always",
            "default",
            "by default",
            "keep using",
            "actively",
            "active",
            "subsequent",
            "future",
            "later",
            "without mentioning",
            "do not require",
            "앞으로",
            "항상",
            "기본",
            "계속",
            "적극",
            "후속",
            "나중",
            "언급하지",
            "명시하지",
        ]
    )


def _is_kh_active_followup_request(text: str) -> bool:
    if _is_automatic_intake_request(text):
        return True
    lowered = text.lower()
    if _is_kh_front_door_evidence(lowered):
        return False
    if any(
        marker in lowered
        for marker in [
            "\ud3f4\ub354",
            "\ud30c\uc77c",
            "\ud504\ub85c\uc81d\ud2b8",
            "\ub300\uc2dc\ubcf4\ub4dc",
            "\ub9cc\ub4e4",
            "\uc218\uc815",
            "\uace0\uccd0",
            "\uc791\uc5c5",
            "\ucc98\ub9ac",
            "\uc9c4\ud589",
            "\ud655\uc778",
            "\uac80\uc99d",
            "\ud14c\uc2a4\ud2b8",
            "\ucee4\ubc0b",
            "\ud478\uc2dc",
            "\uc5c5\ub370\uc774\ud2b8",
        ]
    ):
        return True
    if "?" in text and not any(marker in lowered for marker in ["check", "verify", "review", "봐", "확인", "검증"]):
        return False
    return any(
        marker in lowered
        for marker in [
            "continue",
            "finish",
            "handle",
            "work on",
            "do it",
            "make it",
            "update",
            "fix",
            "verify",
            "review",
            "test",
            "commit",
            "push",
            "처리",
            "작업",
            "진행",
            "마무리",
            "수정",
            "고쳐",
            "만들",
            "확인",
            "검증",
            "테스트",
            "커밋",
            "푸쉬",
            "업데이트",
        ]
    )


def _is_automatic_intake_request(text: str) -> bool:
    lowered = text.lower()
    if _is_kh_front_door_evidence(lowered):
        return False
    if looks_like_sql_output_request(lowered):
        return False
    if _looks_like_external_specialist_direct_question(lowered):
        return False
    if _looks_like_direct_code_question(lowered):
        return False
    try:
        classification = classify_request(text, {"kh_session_audit": True})
    except Exception:
        return _fallback_nontrivial_user_request(lowered)
    if classification.complexity in {"heavy", "high_risk"}:
        return True
    if classification.complexity == "medium":
        return any(
            marker in lowered
            for marker in [
                "file",
                "folder",
                "repo",
                "project",
                "code",
                "html",
                "test",
                "log",
                "document",
                "report",
                "deliverable",
                "verify",
                "review",
                "파일",
                "폴더",
                "코드",
                "로그",
                "문서",
                "보고서",
                "산출물",
                "검증",
                "리뷰",
            ]
        )
    return False


def _is_environment_context_message(text: str) -> bool:
    return str(text or "").lstrip().lower().startswith("<environment_context>")


def _fallback_nontrivial_user_request(lowered: str) -> bool:
    return any(
        marker in lowered
        for marker in [
            "implement",
            "build",
            "fix",
            "create",
            "modify",
            "refactor",
            "verify",
            "review",
            "test",
            "log",
            "docx",
            "xlsx",
            "html",
            "만들",
            "구현",
            "고쳐",
            "수정",
            "검증",
            "테스트",
            "로그",
            "문서",
            "산출물",
        ]
    )


def _is_kh_front_door_evidence(lowered: str) -> bool:
    return any(
        marker in lowered
        for marker in [
            "uaf_skill_catalog",
            "src.skills.uaf_skill_catalog",
            "kh-uaf",
            "universal-agent-framework",
            "kh front-door",
            "kh_front_door",
            "src.orchestration.kh_front_door",
            "front_door.py",
            "always_on_front_door",
            "automatic-intake-harness",
            "always-on-front-door",
            "front_door_auto_route",
            "front_door_status",
            "plugin_composition",
            "plugin-composition-policy",
            "request_complexity",
            "classify_request",
            "skill_application",
            "large_work_orchestration_bundle",
            "session_start_context",
            "workflow_usability_auto",
        ]
    )


def _is_front_door_order_evidence(payload: Dict[str, Any], lowered: str) -> bool:
    payload_type = str(payload.get("type", ""))
    if payload_type in {"function_call_output", "custom_tool_call_output"}:
        return _has_front_door_success_or_blocked_evidence(lowered)
    return False


def _is_front_door_runtime_command(payload: Dict[str, Any], lowered: str) -> bool:
    payload_type = str(payload.get("type", ""))
    if payload_type not in {"function_call", "custom_tool_call"}:
        return False
    tool_name = str(payload.get("name", "") or "").strip().lower()
    if _is_trusted_front_door_tool_name(tool_name):
        return True
    raw = payload.get("arguments") or payload.get("input") or ""
    raw_hint = str(raw).lower()
    if not any(
        marker in lowered or marker in raw_hint
        for marker in ("kh_front_door", "front_door.py")
    ):
        return False
    return any(
        _command_invokes_front_door(command)
        for command in _runtime_command_candidates(payload)
    )


def _is_trusted_front_door_tool_name(tool_name: str) -> bool:
    normalized = str(tool_name or "").strip().lower()
    if normalized in {
        "src.orchestration.kh_front_door",
        "src.orchestration.kh_front_door.build_kh_front_door",
        "kh_uaf.front_door",
        "kh_uaf.kh_front_door",
        "kh-uaf.front_door",
        "kh-uaf.kh_front_door",
    }:
        return True
    if not normalized.startswith("mcp__"):
        return False
    parts = [part for part in normalized.split("__") if part]
    return bool(
        len(parts) >= 3
        and parts[1] in {"kh", "kh_uaf", "kh-uaf"}
        and parts[-1] in {"front_door", "kh_front_door"}
    )


def _runtime_command_candidates(payload: Dict[str, Any]) -> List[str]:
    raw = payload.get("arguments") or payload.get("input") or ""
    candidates: List[str] = []
    if isinstance(raw, dict):
        command = raw.get("command")
        if isinstance(command, str) and command.strip():
            candidates.append(command)
        return candidates
    if not isinstance(raw, str) or not raw.strip():
        return candidates

    tool_name = str(payload.get("name", "") or "").strip().lower()
    tool_tail = re.split(r"[.:]", tool_name)[-1]
    if tool_tail == "shell_command":
        candidates.append(raw)

    try:
        structured = load_json_without_duplicate_keys(raw)
    except (TypeError, json.JSONDecodeError, DuplicateJsonKeyError):
        structured = None
    if isinstance(structured, dict):
        command = structured.get("command")
        if isinstance(command, str) and command.strip():
            candidates.append(command)

    if tool_tail == "exec":
        exact_command = _exact_shell_command_text(
            SessionTextRecord(
                text=raw,
                payload_type=str(payload.get("type", "")),
                name=str(payload.get("name", "")),
                arguments=raw,
            )
        )
        if exact_command:
            return [exact_command]
        return []

    command_literal = re.compile(
        r'(?:[\"\']command[\"\']|\bcommand)\s*:\s*'
        r'(?P<literal>\"(?:\\.|[^\"\\])*\"|\'(?:\\.|[^\'\\])*\')'
    )
    for match in command_literal.finditer(raw):
        command = _decode_command_literal(match.group("literal"))
        if command:
            candidates.append(command)

    return _dedupe_text(candidates)


def _decode_command_literal(literal: str) -> str:
    if literal.startswith('"'):
        try:
            value = json.loads(literal)
        except json.JSONDecodeError:
            return ""
        return value if isinstance(value, str) else ""
    if literal.startswith("'") and literal.endswith("'"):
        return literal[1:-1].replace("\\'", "'").replace("\\\\", "\\")
    return ""


def _command_invokes_front_door(command: str) -> bool:
    value = str(command or "").strip()
    if value.startswith("&"):
        if len(value) == 1 or not value[1].isspace():
            return False
        value = value[1:].lstrip()
    if not value or _contains_unquoted_shell_control(value):
        return False
    try:
        tokens = [_strip_shell_token_quotes(item) for item in shlex.split(value, posix=False)]
    except ValueError:
        return False
    if len(tokens) < 3:
        return False
    executable = tokens[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    if executable not in {"python", "python.exe", "python3", "python3.exe", "py", "py.exe"}:
        return False

    index = 1
    while index < len(tokens):
        token = tokens[index]
        lowered_token = token.lower()
        if lowered_token in {"-c", "-"}:
            return False
        if lowered_token == "-m":
            return bool(
                index + 1 < len(tokens)
                and tokens[index + 1].lower() == "src.orchestration.kh_front_door"
            )
        if lowered_token == "--":
            index += 1
            if index >= len(tokens):
                return False
            token = tokens[index]
            lowered_token = token.lower()
        if lowered_token.startswith("-"):
            index += 2 if lowered_token in {"-w", "-x"} else 1
            continue
        return _is_trusted_front_door_script_path(token)
    return False


def _is_trusted_front_door_script_path(value: str) -> bool:
    normalized = str(value or "").strip().replace("\\", "/").lower()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    relative_path = "skills/always_on_front_door/scripts/front_door.py"
    if normalized == relative_path:
        return True
    suffix = f"/{relative_path}"
    if not normalized.endswith(suffix):
        return False

    prefix = normalized[: -len(suffix)].rstrip("/")
    if re.search(
        r"/(?:\.codex|\.claude|\.gemini)/(?:plugins/cache/)?"
        r"kh-uaf-marketplace/kh-uaf/[^/]+$",
        prefix,
    ):
        return True
    if re.search(r"/(?:\.codex|\.claude|\.gemini)$", prefix):
        return True

    segments = [segment for segment in prefix.split("/") if segment]
    repo_names = {"kh", "kh-uaf", "universal-agent-framework"}
    if segments and segments[-1] in repo_names:
        return True
    return any(
        segment == ".worktrees" and index > 0 and segments[index - 1] in repo_names
        for index, segment in enumerate(segments)
    )


def _shell_command_segments(command: str) -> List[str]:
    segments: List[str] = []
    current: List[str] = []
    quote = ""
    index = 0
    while index < len(command):
        char = command[index]
        if quote:
            current.append(char)
            if char == "\\" and index + 1 < len(command):
                index += 1
                current.append(command[index])
            elif char == quote:
                quote = ""
        elif char in {"\"", "'"}:
            quote = char
            current.append(char)
        elif char in {"\r", "\n", ";", "|", "&"}:
            segment = "".join(current).strip()
            if segment:
                segments.append(segment)
            current = []
        else:
            current.append(char)
        index += 1
    segment = "".join(current).strip()
    if segment:
        segments.append(segment)
    return segments


def _shell_command_tokens(segment: str) -> List[str]:
    tokens = re.findall(
        r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[^\s]+',
        segment,
    )
    return [
        token[1:-1] if len(token) >= 2 and token[0] == token[-1] and token[0] in {"\"", "'"} else token
        for token in tokens
    ]


def _is_non_kh_work_start(payload: Dict[str, Any], lowered: str) -> bool:
    payload_type = str(payload.get("type", ""))
    if payload_type == "agent_message":
        phase = str(payload.get("phase", "")).lower()
        if phase in {"commentary", "analysis"}:
            return False
        if phase in {"final", "final_answer"}:
            return bool(lowered.strip())
        return bool(lowered.strip()) and not _looks_like_progress_commentary(lowered)
    if payload_type == "task_complete":
        return True
    if payload_type == "message":
        if str(payload.get("role", "")).lower() != "assistant" or not lowered.strip():
            return False
        phase = str(payload.get("phase", "")).lower()
        if phase in {"commentary", "analysis"}:
            return False
        if phase in {"final", "final_answer"}:
            return True
        return not _looks_like_progress_commentary(lowered)
    if payload_type not in {"function_call", "custom_tool_call"}:
        return False
    if _is_non_bootstrap_kh_skill_read(payload, lowered):
        return True
    if _is_front_door_runtime_command(payload, lowered):
        return False
    if _is_bootstrap_front_door_skill_read(payload, lowered):
        return False
    tool_name = str(payload.get("name", "")).lower()
    if tool_name in {"apply_patch"}:
        return True
    if tool_name in {
        "open",
        "web.run",
        "view_image",
        "functions.view_image",
        "browser",
        "browser.open",
        "read_file",
        "computer-use",
        "mcp__codex_apps__github__search",
    }:
        return True
    if tool_name not in {"shell_command", "functions.shell_command"}:
        return False
    return any(
        marker in lowered
        for marker in [
            "get-childitem",
            "test-path",
            "select-string",
            "rg ",
            "rg --files",
            "git ",
            "git show",
            "git diff",
            "git grep",
            "dir ",
            "ls ",
            "findstr",
            "get-content",
            "python ",
            "copy-item",
            "move-item",
            "remove-item",
            "set-content",
            "add-content",
        ]
    )


def _looks_like_progress_commentary(lowered: str) -> bool:
    text = re.sub(r"\s+", " ", str(lowered or "").strip())
    if not text:
        return False
    english = re.match(
        r"^(?:i(?:'ll| will| am|'m)\b|let me\b|next[, ]+i(?:'ll| will)\b|"
        r"(?:now )?(?:checking|inspecting|reading|running|testing|reviewing|tracing|investigating)\b)",
        text,
    )
    if english and any(
        marker in text
        for marker in [
            "check",
            "inspect",
            "read",
            "run",
            "test",
            "review",
            "trace",
            "investigat",
            "look",
            "examin",
            "patch",
            "edit",
            "update",
        ]
    ):
        return True
    return any(
        marker in text
        for marker in [
            "\ud655\uc778\ud558\uaca0\uc2b5\ub2c8\ub2e4",
            "\uc0b4\ud3b4\ubcf4\uaca0\uc2b5\ub2c8\ub2e4",
            "\ucd94\uc801\ud558\uaca0\uc2b5\ub2c8\ub2e4",
            "\ud14c\uc2a4\ud2b8\ud558\uaca0\uc2b5\ub2c8\ub2e4",
            "\uc9c4\ud589 \uc911\uc785\ub2c8\ub2e4",
            "\ud655\uc778 \uc911\uc785\ub2c8\ub2e4",
        ]
    )


def _is_non_bootstrap_kh_skill_read(payload: Dict[str, Any], lowered: str) -> bool:
    tool_name = str(payload.get("name", "")).lower()
    if tool_name not in {"shell_command", "functions.shell_command"}:
        return False
    if "kh-uaf-marketplace" not in lowered and "\\kh-uaf\\" not in lowered and "/kh-uaf/" not in lowered:
        return False
    if "skill.md" not in lowered or "\\skills\\" not in lowered and "/skills/" not in lowered:
        return False
    return "always_on_front_door" not in lowered


def _is_bootstrap_front_door_skill_read(payload: Dict[str, Any], lowered: str) -> bool:
    tool_name = str(payload.get("name", "")).lower()
    if tool_name not in {"shell_command", "functions.shell_command"}:
        return False
    return bool(
        "skill.md" in lowered
        and "always_on_front_door" in lowered
        and any(
            marker in lowered
            for marker in [
                "get-content",
                "read_text",
                "select-string",
                "findstr",
                "rg ",
            ]
        )
        and not any(
            marker in lowered
            for marker in [
                "apply_patch",
                "set-content",
                "add-content",
                "remove-item",
                "move-item",
                "copy-item",
            ]
        )
    )


def summarize_session_skill_audits(paths: Iterable[str | Path]) -> Dict[str, Any]:
    audits = [analyze_session_skills(path).to_dict() for path in paths]
    aggregate_issues: Dict[str, int] = {}
    aggregate_statuses: Dict[str, int] = {}
    aggregate_verdicts: Dict[str, int] = {}
    for audit in audits:
        usage_summary = audit.get("usage_summary", {}) or {}
        verdict = str(usage_summary.get("verdict", "unknown"))
        aggregate_verdicts[verdict] = aggregate_verdicts.get(verdict, 0) + 1
        for status, count in (usage_summary.get("status_counts", {}) or {}).items():
            status = str(status)
            aggregate_statuses[status] = aggregate_statuses.get(status, 0) + int(count or 0)
        for issue in audit.get("issues", []):
            skill = str(issue.get("skill", ""))
            aggregate_issues[skill] = aggregate_issues.get(skill, 0) + 1
    return {
        "session_count": len(audits),
        "audits": audits,
        "aggregate": {
            "issue_count": sum(len(audit.get("issues", [])) for audit in audits),
            "issues_by_skill": dict(sorted(aggregate_issues.items())),
            "skill_status_counts": dict(sorted(aggregate_statuses.items())),
            "verdict_counts": dict(sorted(aggregate_verdicts.items())),
        },
    }


def _skill_usage_summary(
    skill_rows: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    postmortem: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a compact, user-readable execution accounting table.

    This is intentionally derived from generic audit rows and issues, not from
    one-off session ids. It separates execution from inspection so downstream
    reports cannot turn "read the SKILL.md" into "used the harness".
    """

    status_counts: Dict[str, int] = {}
    acceptance_counts: Dict[str, int] = {}
    for row in skill_rows:
        status = str(row.get("status", "unknown"))
        status_counts[status] = status_counts.get(status, 0) + 1
        acceptance_status = str((row.get("acceptance", {}) or {}).get("status", "unknown"))
        acceptance_counts[acceptance_status] = acceptance_counts.get(acceptance_status, 0) + 1

    issue_rows = _issues_by_skill(issues)
    runtime_applied = _skill_names_with_status(skill_rows, {"applied"})
    selected_not_executed = _skill_names_with_status(skill_rows, {"considered", "procedural"})
    inspected_only = _skill_names_with_status(skill_rows, {"inspected"})
    mentioned_only = _skill_names_with_status(skill_rows, {"mentioned"})
    required_missing_or_unaccepted = [
        {
            "name": str(row.get("name", "")),
            "status": str(row.get("status", "")),
            "acceptance_status": str((row.get("acceptance", {}) or {}).get("status", "")),
            "required_reason": str(row.get("required_reason", "")),
            "issues": issue_rows.get(str(row.get("name", "")), [])[:5],
        }
        for row in skill_rows
        if row.get("required")
        and (
            STATUS_RANK.get(str(row.get("status", "")), 0) < STATUS_RANK["considered"]
            or str((row.get("acceptance", {}) or {}).get("status", ""))
            in {"missing_application", "missing_outputs", "blocked"}
            or issue_rows.get(str(row.get("name", "")))
        )
    ]
    immediate_next_not_applied = _dedupe_immediate_next_issues(issues)
    token_row = next((row for row in skill_rows if row.get("name") == "token-optimizer"), {})
    token_optimizer = {
        "skill_row_status": str(token_row.get("status", "absent") or "absent"),
        "required": bool(token_row.get("required")),
        "acceptance_status": str((token_row.get("acceptance", {}) or {}).get("status", "")),
        "runtime_status": str(postmortem.get("token_optimizer_status", "")),
        "runtime_status_reason": str(postmortem.get("token_optimizer_status_reason", "")),
        "token_gate": postmortem.get("token_gate", {}) or {},
    }
    issue_severities = {str(issue.get("severity", "")) for issue in issues}
    if "P0" in issue_severities:
        verdict = "failed_p0"
    elif "P1" in issue_severities:
        verdict = "failed_p1"
    elif issues:
        verdict = "issues_found"
    else:
        verdict = "passed"
    return {
        "verdict": verdict,
        "status_counts": dict(sorted(status_counts.items())),
        "acceptance_counts": dict(sorted(acceptance_counts.items())),
        "runtime_applied_skills": runtime_applied,
        "selected_not_executed_skills": selected_not_executed,
        "inspected_only_skills": inspected_only,
        "mentioned_only_skills": mentioned_only,
        "required_missing_or_unaccepted": required_missing_or_unaccepted,
        "immediate_next_not_applied": immediate_next_not_applied,
        "token_optimizer": token_optimizer,
        "subagent_summary": postmortem.get("subagent_summary", {}) or {},
        "recommended_actions": list(postmortem.get("recommended_actions", []) or []),
    }


def _skill_names_with_status(skill_rows: List[Dict[str, Any]], statuses: Set[str]) -> List[str]:
    return [
        str(row.get("name", ""))
        for row in skill_rows
        if str(row.get("status", "")) in statuses
    ]


def _issues_by_skill(issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for issue in issues:
        skill = str(issue.get("skill", ""))
        grouped.setdefault(skill, []).append(
            {
                "status": str(issue.get("status", "")),
                "severity": str(issue.get("severity", "")),
                "reason": _short(str(issue.get("reason", "")), 180),
            }
        )
    return grouped


def _dedupe_immediate_next_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    for issue in issues:
        status = str(issue.get("status", ""))
        if not status.startswith("immediate_next_skill"):
            continue
        skill = str(issue.get("skill", ""))
        reason = str(issue.get("reason", ""))
        expected_order = [str(item) for item in issue.get("expected_order", []) or []]
        key = (skill, status, "|".join(expected_order))
        if key not in grouped:
            grouped[key] = {
                "skill": skill,
                "status": status,
                "severity": str(issue.get("severity", "")),
                "reason": reason,
                "expected_order": expected_order,
                "occurrences": 0,
            }
        grouped[key]["occurrences"] += 1
    return list(grouped.values())


def _session_texts(path: Path) -> Iterable[str]:
    records = _session_text_records(path)
    if isinstance(records, DiskBackedSessionTextRecords):
        return records.iter_text_values()
    return (record.text for record in records)


def _session_text_records(path: Path) -> Sequence[SessionTextRecord]:
    events = _session_payload_events(path)
    if not isinstance(events, DiskBackedSessionEvents):
        raise RuntimeError("session text records require the streaming fact store")
    if not events.text_records_ready:
        raise RuntimeError("session text reducer was not finalized")
    return events.text_records()


def _payload_text(payload: Dict[str, Any]) -> str:
    payload_type = payload.get("type")
    if payload_type == "message":
        return _content_text(payload.get("content"))
    if payload_type == "agent_message":
        return _content_text(payload.get("message") or payload.get("content"))
    if payload_type in {"host_front_door", "host_native_front_door"}:
        packet = payload.get("packet") or payload.get("content") or payload.get("output")
        if isinstance(packet, Mapping):
            return json.dumps(dict(packet), ensure_ascii=False, sort_keys=True)
        return _content_text(packet)
    if payload_type in {"function_call", "custom_tool_call"}:
        return f"{payload.get('name', '')} {payload.get('arguments') or payload.get('input') or ''}"
    if payload_type in {"function_call_output", "custom_tool_call_output"}:
        return _content_text(payload.get("output") or payload.get("content"))
    if payload_type == "thread_goal_updated":
        goal = payload.get("goal", {}) or {}
        return json.dumps(
            {
                "type": "thread_goal_updated",
                "skill": "goal-state-harness",
                "status": "applied",
                "goal_status": goal.get("status", ""),
                "objective": goal.get("objective", ""),
            },
            ensure_ascii=False,
        )
    if payload_type == "task_complete":
        return str(payload.get("last_agent_message", ""))
    return ""


def _payload_arguments_text(payload: Dict[str, Any]) -> str:
    if str(payload.get("type", "")) not in {"function_call", "custom_tool_call"}:
        return ""
    value = payload.get("arguments")
    if value is None:
        value = payload.get("input")
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        command = value.get("command")
        if isinstance(command, str):
            return command
        return json.dumps(dict(value), ensure_ascii=False, sort_keys=True)
    return str(value or "")


def _payload_exit_codes(payload: Dict[str, Any]) -> tuple[Any, ...]:
    if str(payload.get("type", "")) not in {
        "function_call_output",
        "custom_tool_call_output",
    }:
        return ()
    values: List[Any] = []
    for key in ["exit_code", "return_code", "returncode"]:
        if key not in payload:
            continue
        values.append(payload[key])
    return tuple(values)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    return str(content or "")


def _skill_aliases(skill: Dict[str, Any]) -> Set[str]:
    name = str(skill.get("name", ""))
    relative = str(skill.get("relative_path", ""))
    folder = relative.split("/", 1)[0].split("\\", 1)[0]
    aliases = {name, name.replace("-", "_"), folder, folder.replace("_", "-")}
    return {alias for alias in aliases if alias}


@dataclass(frozen=True)
class _CatalogObservationIndex:
    specifications_by_name: Dict[str, Set[str]]
    alias_owners: Dict[str, Set[str]]
    runtime_owners: Dict[str, Set[str]]
    candidate_needles: tuple[str, ...]
    candidate_buckets: tuple[tuple[str, tuple[str, ...]], ...]


def _literal_suffix_buckets(
    needles: Iterable[str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    buckets: Dict[str, List[str]] = {}
    for needle in sorted(set(needles)):
        buckets.setdefault(needle[-4:], []).append(needle)
    return tuple(
        (suffix, tuple(bucket_needles))
        for suffix, bucket_needles in sorted(buckets.items())
    )


def _build_catalog_observation_index(
    skills: Sequence[Mapping[str, Any]],
) -> _CatalogObservationIndex:
    specifications_by_name: Dict[str, Set[str]] = {}
    alias_owners: Dict[str, Set[str]] = {}
    runtime_owners: Dict[str, Set[str]] = {}
    catalog_needles: Set[str] = {
        "front_door_status",
        "kh_fd_micro",
        "host_native_semantic_fast_path",
    }
    for skill in skills:
        skill_dict = dict(skill)
        name = str(skill_dict.get("name", ""))
        aliases = _skill_aliases(skill_dict)
        lowered_aliases = tuple(alias.lower() for alias in aliases)
        runtime_markers = tuple(
            marker.lower() for marker in RUNTIME_MARKERS.get(name, [])
        )
        specifications_by_name[name] = aliases
        for alias in lowered_aliases:
            alias_owners.setdefault(alias, set()).add(name)
        for marker in runtime_markers:
            runtime_owners.setdefault(marker, set()).add(name)
        catalog_needles.update(lowered_aliases)
        catalog_needles.update(runtime_markers)
    candidate_needles = tuple(sorted(catalog_needles))
    return _CatalogObservationIndex(
        specifications_by_name=specifications_by_name,
        alias_owners=alias_owners,
        runtime_owners=runtime_owners,
        candidate_needles=candidate_needles,
        candidate_buckets=_literal_suffix_buckets(candidate_needles),
    )


def _has_catalog_candidate(
    lowered: str,
    catalog_index: _CatalogObservationIndex,
) -> bool:
    for suffix, needles in catalog_index.candidate_buckets:
        if suffix not in lowered:
            continue
        if any(needle in lowered for needle in needles):
            return True
    return False


def _catalog_owner_hits(
    lowered: str,
    buckets: Sequence[tuple[str, tuple[str, ...]]],
    owners_by_needle: Mapping[str, Set[str]],
) -> Set[str]:
    hits: Set[str] = set()
    for suffix, needles in buckets:
        if suffix not in lowered:
            continue
        for needle in needles:
            owners = owners_by_needle.get(needle)
            if owners and needle in lowered:
                hits.update(owners)
    return hits


def _empty_observations() -> Dict[str, Any]:
    return {
        "status": "absent",
        "mentions": 0,
        "inspections": 0,
        "runtime_hits": 0,
        "claimed_unverified": 0,
        "passive_references": 0,
        "considered": 0,
        "evidence": [],
        "active_evidence": [],
    }


def _set_catalog_observation_status(observation: Dict[str, Any]) -> None:
    status = "absent"
    if observation["mentions"]:
        status = "mentioned"
    if observation["claimed_unverified"] and not observation["runtime_hits"]:
        status = "claimed_unverified"
    if observation["inspections"]:
        status = "inspected"
    if observation["considered"] and not observation["runtime_hits"]:
        status = "considered"
    if observation["runtime_hits"]:
        status = "applied"
    observation["status"] = status


def _merge_catalog_observations(
    target: Dict[str, Dict[str, Any]],
    partial: Mapping[str, Mapping[str, Any]],
) -> None:
    for skill_name, incoming in partial.items():
        observation = target.setdefault(str(skill_name), _empty_observations())
        for key in (
            "mentions",
            "inspections",
            "runtime_hits",
            "claimed_unverified",
            "passive_references",
            "considered",
        ):
            observation[key] += int(incoming.get(key, 0) or 0)
        for key in ("evidence", "active_evidence"):
            remaining = 8 - len(observation[key])
            if remaining > 0:
                observation[key].extend(list(incoming.get(key, []) or [])[:remaining])
        _set_catalog_observation_status(observation)


def _catalog_observations(
    texts: Iterable[SessionTextRecord | str],
    skills: Sequence[Mapping[str, Any]],
    *,
    catalog_index: _CatalogObservationIndex | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Evaluate every catalog skill in one replay of the finalized text facts."""

    index = catalog_index or _build_catalog_observation_index(skills)
    specifications_by_name = index.specifications_by_name
    alias_owners = index.alias_owners
    runtime_owners = index.runtime_owners
    results: Dict[str, Dict[str, Any]] = {
        name: _empty_observations() for name in specifications_by_name
    }

    for item in texts:
        if isinstance(item, SessionTextRecord):
            text = item.text
            payload_type = item.payload_type
            role = item.role
            name = item.name
            arguments = item.arguments
            trusted_host_native_fast_path = item.trusted_host_native_fast_path
            trusted_front_door_runtime = item.trusted_front_door_runtime
            trusted_correlated_tool_runtime = item.trusted_correlated_tool_runtime
        else:
            text = str(item)
            payload_type = ""
            role = ""
            name = ""
            arguments = ""
            trusted_host_native_fast_path = False
            trusted_front_door_runtime = False
            trusted_correlated_tool_runtime = False

        passive = _is_passive_text(text)
        clean_text = _strip_passive_prefix(text)
        lowered = clean_text.lower()
        alias_hits = _catalog_owner_hits(
            lowered,
            index.candidate_buckets,
            alias_owners,
        )
        runtime_marker_hits = _catalog_owner_hits(
            lowered,
            index.candidate_buckets,
            runtime_owners,
        )
        host_native_packet_shape = _is_valid_host_native_front_door_packet(clean_text)
        host_native_front_door = bool(
            host_native_packet_shape and trusted_host_native_fast_path
        )
        normalized_front_door = _front_door_json(clean_text)
        front_door_runtime_command = bool(
            payload_type in {"function_call", "custom_tool_call"}
            and _is_front_door_runtime_command(
                {
                    "type": payload_type,
                    "name": name,
                    "arguments": arguments,
                },
                lowered,
            )
        )
        front_door_packet_claim = bool(
            host_native_packet_shape
            or normalized_front_door
            or _looks_like_front_door_runtime_output(lowered)
            or front_door_runtime_command
        )
        structured_application_claim = _looks_like_structured_skill_application_claim(
            clean_text
        )
        untrusted_front_door_claim = bool(
            (front_door_packet_claim or structured_application_claim)
            and not trusted_front_door_runtime
            and not trusted_correlated_tool_runtime
            and not host_native_front_door
        )

        if untrusted_front_door_claim:
            sample = ""
            candidate_names = set(alias_hits)
            if host_native_packet_shape or normalized_front_door:
                candidate_names.update(results)
            for skill_name in candidate_names:
                front_door_claim_status = _front_door_skill_status_from_data(
                    normalized_front_door,
                    skill_name,
                )
                claim_mentions_skill = bool(
                    (host_native_packet_shape and skill_name == "always-on-front-door")
                    or (normalized_front_door and skill_name == "always-on-front-door")
                    or front_door_claim_status
                    or skill_name in alias_hits
                )
                if not claim_mentions_skill:
                    continue
                observation = results[skill_name]
                observation["mentions"] += 1
                observation["claimed_unverified"] += 1
                if len(observation["evidence"]) < 8:
                    if not sample:
                        sample = _short(clean_text)
                    observation["evidence"].append(sample)
            continue

        sample = ""
        normalized_evidence = ""
        candidate_names = set(alias_hits) | set(runtime_marker_hits)
        if host_native_front_door or normalized_front_door:
            candidate_names.update(results)
        for skill_name in candidate_names:
            aliases = specifications_by_name[skill_name]
            observation = results[skill_name]
            front_door_claim_status = _front_door_skill_status_from_data(
                normalized_front_door,
                skill_name,
            )
            front_door_status = (
                front_door_claim_status if trusted_front_door_runtime else ""
            )
            if host_native_front_door and skill_name == "always-on-front-door":
                front_door_status = "considered"
            if (
                skill_name == "token-optimizer"
                and front_door_status
                and payload_type not in {"function_call_output", "custom_tool_call_output"}
            ):
                front_door_status = ""
            alias_hit = bool(front_door_status) or skill_name in alias_hits
            runtime_marker_hit = bool(
                not host_native_front_door
                and not front_door_status
                and skill_name in runtime_marker_hits
            )
            if skill_name == "token-optimizer" and runtime_marker_hit:
                runtime_marker_hit = _is_token_optimizer_runtime_source(
                    payload_type,
                    role,
                    lowered,
                )
            runtime_hit = front_door_status == "applied" or runtime_marker_hit
            if not alias_hit and not runtime_hit:
                continue

            observation["mentions"] += 1
            if passive or "skill.md" in lowered or "\\skills\\" in lowered or "/skills/" in lowered:
                observation["inspections"] += 1
            if passive:
                observation["passive_references"] += 1
            if skill_name == "token-optimizer" and front_door_status != "applied":
                explicit_hit = False
            else:
                explicit_hit = (
                    False
                    if front_door_status and front_door_status != "applied"
                    else _explicit_application(lowered, aliases)
                )
            if not passive and (runtime_hit or explicit_hit):
                observation["runtime_hits"] += 1
            if not passive and (
                front_door_status in {"selected", "considered", "skipped", "blocked"}
                or any(
                    marker in lowered
                    for marker in (
                        "considered_not_needed",
                        "skipped_with_rationale",
                        "blocked",
                        "passthrough",
                    )
                )
            ):
                observation["considered"] += 1
            if len(observation["evidence"]) < 8:
                if not sample:
                    sample = _short(clean_text)
                observation["evidence"].append(sample)
            if not passive and len(observation["active_evidence"]) < 8:
                if normalized_front_door and payload_type in {
                    "function_call_output",
                    "custom_tool_call_output",
                }:
                    if not normalized_evidence:
                        normalized_evidence = json.dumps(
                            normalized_front_door,
                            sort_keys=True,
                        )
                    observation["active_evidence"].append(normalized_evidence)
                else:
                    observation["active_evidence"].append(clean_text)

    for observation in results.values():
        _set_catalog_observation_status(observation)
    return results


def _observations(texts: List[SessionTextRecord] | List[str], aliases: Set[str], skill_name: str) -> Dict[str, Any]:
    mentions = 0
    inspections = 0
    runtime_hits = 0
    passive_references = 0
    considered = 0
    claimed_unverified = 0
    evidence: List[str] = []
    active_evidence: List[str] = []
    runtime_markers = RUNTIME_MARKERS.get(skill_name, [])

    for item in texts:
        if isinstance(item, SessionTextRecord):
            text = item.text
            payload_type = item.payload_type
            role = item.role
            trusted_host_native_fast_path = item.trusted_host_native_fast_path
            trusted_front_door_runtime = item.trusted_front_door_runtime
            trusted_correlated_tool_runtime = item.trusted_correlated_tool_runtime
        else:
            text = str(item)
            payload_type = ""
            role = ""
            trusted_host_native_fast_path = False
            trusted_front_door_runtime = False
            trusted_correlated_tool_runtime = False
        passive = _is_passive_text(text)
        clean_text = _strip_passive_prefix(text)
        lowered = clean_text.lower()
        host_native_packet_shape = _is_valid_host_native_front_door_packet(clean_text)
        host_native_front_door = bool(
            host_native_packet_shape and trusted_host_native_fast_path
        )
        normalized_front_door = _front_door_json(clean_text)
        front_door_runtime_command = bool(
            payload_type in {"function_call", "custom_tool_call"}
            and _is_front_door_runtime_command(
                {
                    "type": payload_type,
                    "name": item.name if isinstance(item, SessionTextRecord) else "",
                    "arguments": item.arguments if isinstance(item, SessionTextRecord) else "",
                },
                lowered,
            )
        )
        front_door_claim_status = _front_door_skill_status(clean_text, skill_name)
        front_door_packet_claim = bool(
            host_native_packet_shape
            or normalized_front_door
            or _looks_like_front_door_runtime_output(lowered)
            or front_door_runtime_command
        )
        structured_application_claim = _looks_like_structured_skill_application_claim(
            clean_text
        )
        untrusted_front_door_claim = bool(
            (front_door_packet_claim or structured_application_claim)
            and not trusted_front_door_runtime
            and not trusted_correlated_tool_runtime
            and not host_native_front_door
        )
        if untrusted_front_door_claim:
            claim_mentions_skill = bool(
                (host_native_packet_shape and skill_name == "always-on-front-door")
                or (normalized_front_door and skill_name == "always-on-front-door")
                or front_door_claim_status
                or any(alias.lower() in lowered for alias in aliases)
            )
            if claim_mentions_skill:
                mentions += 1
                claimed_unverified += 1
                if len(evidence) < 8:
                    evidence.append(_short(clean_text))
            continue
        front_door_status = (
            front_door_claim_status
            if trusted_front_door_runtime
            else ""
        )
        if host_native_front_door and skill_name == "always-on-front-door":
            front_door_status = "considered"
        if (
            skill_name == "token-optimizer"
            and front_door_status
            and payload_type not in {"function_call_output", "custom_tool_call_output"}
        ):
            front_door_status = ""
        alias_hit = bool(front_door_status) or any(alias.lower() in lowered for alias in aliases)
        runtime_marker_hit = bool(
            not host_native_front_door
            and not front_door_status
            and any(marker.lower() in lowered for marker in runtime_markers)
        )
        if skill_name == "token-optimizer" and runtime_marker_hit:
            runtime_marker_hit = _is_token_optimizer_runtime_source(payload_type, role, lowered)
        runtime_hit = front_door_status == "applied" or runtime_marker_hit
        if not alias_hit and not runtime_hit:
            continue
        mentions += 1
        if passive or "skill.md" in lowered or "\\skills\\" in lowered or "/skills/" in lowered:
            inspections += 1
        if passive:
            passive_references += 1
        if skill_name == "token-optimizer" and front_door_status != "applied":
            explicit_hit = False
        else:
            explicit_hit = False if front_door_status and front_door_status != "applied" else _explicit_application(lowered, aliases)
        if not passive and (runtime_hit or explicit_hit):
            runtime_hits += 1
        if not passive and (
            front_door_status in {"selected", "considered", "skipped", "blocked"}
            or any(marker in lowered for marker in ["considered_not_needed", "skipped_with_rationale", "blocked", "passthrough"])
        ):
            considered += 1
        if len(evidence) < 8:
            evidence.append(_short(clean_text))
        if not passive and len(active_evidence) < 8:
            if normalized_front_door and payload_type in {
                "function_call_output",
                "custom_tool_call_output",
            }:
                active_evidence.append(json.dumps(normalized_front_door, sort_keys=True))
            else:
                active_evidence.append(clean_text)

    status = "absent"
    if mentions:
        status = "mentioned"
    if claimed_unverified and not runtime_hits:
        status = "claimed_unverified"
    if inspections:
        status = "inspected"
    if considered and not runtime_hits:
        status = "considered"
    if runtime_hits:
        status = "applied"
    return {
        "status": status,
        "mentions": mentions,
        "inspections": inspections,
        "runtime_hits": runtime_hits,
        "claimed_unverified": claimed_unverified,
        "passive_references": passive_references,
        "evidence": evidence,
        "active_evidence": active_evidence,
    }


def _is_token_optimizer_runtime_source(payload_type: str, role: str = "", lowered: str = "") -> bool:
    payload_type = str(payload_type)
    role = str(role).lower()
    lowered = str(lowered).lower()
    if payload_type in {"function_call", "custom_tool_call"}:
        return _is_token_optimizer_runtime_command(lowered)
    if payload_type in {"function_call_output", "custom_tool_call_output"}:
        return _looks_like_token_optimizer_runtime_output(lowered)
    if payload_type == "thread_goal_updated":
        return True
    if payload_type in {"message", "agent_message"} and role in {"assistant", "agent"}:
        return False
    return False


def _is_token_optimizer_runtime_command(lowered: str) -> bool:
    read_only_markers = [
        "rg ",
        "select-string",
        "get-content",
        "findstr",
        "type ",
        "grep ",
        "git grep",
        "git diff",
        "git show",
    ]
    if any(marker in lowered for marker in read_only_markers):
        return False
    return any(
        marker in lowered
        for marker in [
            "python -m src.skills.token_optimizer",
            "src.skills.token_optimizer",
            "summarize_command_output(",
            "optimize_context_content(",
            "summarize_agent_transcript(",
            "compare_token_usage(",
            "aggregate_token_usage_stats(",
            "optimize_workflow_task_results(",
        ]
    )


def _looks_like_token_optimizer_runtime_output(lowered: str) -> bool:
    if "{" not in lowered or "}" not in lowered:
        return False
    if not any(
        marker in lowered
        for marker in [
            "estimated_tokens_saved",
            "estimated_payload_tokens_saved",
            "token_savings_ratio",
            "host_actual_tokens_used",
            "host_actual_token_evidence",
            "token_usage",
        ]
    ):
        return False
    return any(
        marker in lowered
        for marker in [
            "runtime_token_optimization",
            "metadata.token_optimizer",
            "token_optimizer",
            "token_usage",
        ]
    )


def _front_door_skill_status(text: str, skill_name: str) -> str:
    data = _front_door_json(text)
    return _front_door_skill_status_from_data(data, skill_name)


def _front_door_skill_status_from_data(
    data: Mapping[str, Any],
    skill_name: str,
) -> str:
    if not data:
        return ""
    status_summary = data.get("skill_status_summary", {}) or {}
    summary = (
        status_summary.get(skill_name, {})
        if isinstance(status_summary, dict)
        else {}
    )
    if (
        isinstance(summary, dict)
        and str(summary.get("status", "")) == "applied"
        and "runtime_evidence" in summary
        and not summary.get("runtime_evidence")
    ):
        return "selected"
    runtime_applied = {str(item) for item in data.get("runtime_applied_skills", []) or []}
    if skill_name in runtime_applied:
        return "applied"
    if skill_name == "token-optimizer":
        token_decision = data.get("token_optimizer", {}) or {}
        if isinstance(token_decision, dict):
            token_status = str(token_decision.get("status", "")).strip()
            if token_status == "used" or token_decision.get("used") is True:
                return "applied"
            if token_status == "blocked":
                return "blocked"
            if token_status:
                return "considered"
    immediate = {str(item) for item in data.get("immediate_next_skills", []) or []}
    if skill_name in immediate:
        return "selected"
    selected = {str(item) for item in data.get("selected_not_executed_skills", []) or []}
    if skill_name in selected:
        return "selected"
    if isinstance(status_summary, dict) and skill_name in status_summary:
        status = str(summary.get("status", ""))
        if status == "applied":
            return "applied"
        if status == "blocked":
            return "blocked"
        if status == "pending_immediate_execution":
            return "selected"
        if status:
            return "skipped"
    return ""


def _front_door_json(text: str) -> Dict[str, Any]:
    data = _json_object_from_text(text)
    if not data:
        return {}
    if data.get("m") == "kh_fd_micro":
        if not _is_valid_micro_front_door_packet(data):
            return {}
        return _normalize_micro_front_door_packet(data)
    if _is_valid_compact_front_door_packet(data):
        return data
    if not _looks_like_front_door_runtime_output(text.lower()):
        return {}
    if "token_optimizer_decision" in data:
        return _normalize_full_summary_front_door_packet(data)
    return data


def _is_valid_host_native_front_door_packet(text: str) -> bool:
    data = _standalone_json_object_from_text(text)
    if not data:
        return False
    runtime_applied = data.get("runtime_applied_skills")
    return bool(
        data.get("intake_mode") == "host_native_semantic_fast_path"
        and data.get("route") == "direct"
        and type(data.get("governed_runtime_executed")) is bool
        and data["governed_runtime_executed"] is False
        and isinstance(runtime_applied, list)
        and not runtime_applied
        and data.get("token_optimizer_status") in {"considered_not_needed", "passthrough"}
        and str(data.get("eligibility_rationale", "")).strip()
        and "front_door_status" not in data
    )


def _is_trusted_host_native_fast_path_receipt(
    payload: Mapping[str, Any],
    text: str,
    trigger_text: str,
    work_activity_since_trigger: bool,
) -> bool:
    return bool(
        _has_trusted_host_native_fast_path_provenance(payload, text)
        and not work_activity_since_trigger
        and _host_native_fast_path_trigger_is_eligible(trigger_text)
    )


def _has_trusted_host_native_fast_path_provenance(
    payload: Mapping[str, Any],
    text: str,
) -> bool:
    if not _is_valid_host_native_front_door_packet(text):
        return False
    payload_type = str(payload.get("type", ""))
    if payload_type in {"host_front_door", "host_native_front_door"}:
        return bool(
            str(payload.get("origin", "")).strip().lower() == "host"
            and str(payload.get("event_id", "")).strip()
        )
    return False


def _host_native_fast_path_trigger_is_eligible(trigger_text: str) -> bool:
    if not str(trigger_text or "").strip():
        return False
    if _is_bounded_same_task_continuation(trigger_text):
        return False
    try:
        request_act = parse_request_act(trigger_text)
    except Exception:
        return False
    if _host_native_explicit_noop_lookup(trigger_text, request_act):
        return True
    lowered = str(trigger_text).lower()
    if _is_kh_front_door_request(lowered) or _is_kh_active_directive(trigger_text):
        return False
    if _host_native_fast_path_trigger_requires_runtime(trigger_text, request_act):
        return False
    if (
        _host_native_visible_context_only_question(trigger_text)
        or _host_native_stable_word_definition(trigger_text, request_act)
        or _host_native_stable_concept_question(trigger_text)
        or _host_native_technology_concept_question(trigger_text)
        or _host_native_dynamic_domain_concept_question(trigger_text)
    ):
        return True
    try:
        classification = classify_request(
            trigger_text,
            {"kh_session_audit": True, "host_native_fast_path_check": True},
        )
    except Exception:
        return False
    return bool(
        classification.complexity == "light"
        and classification.recommended_execution == "direct_answer"
        and not classification.evidence_required
    )


_HOST_NATIVE_NAMED_RESOURCE_RE = re.compile(
    r"(?:[a-z]:[\\/]|(?:^|[\s`\"'])(?:\.{0,2}[\\/]|[a-z0-9_.-]+[\\/])[a-z0-9_.\\/-]+)"
    r"|\b[a-z0-9_.-]+\.(?:cs|css|csv|html?|ini|java|js|json|md|py|sql|toml|ts|tsx|xml|ya?ml)\b",
    re.IGNORECASE,
)
_HOST_NATIVE_ACCESS_ACTION_RE = re.compile(
    r"\b(?:check|count|enumerate|find|inspect|list|load|look\s+up|open|read|report|scan|search|show|summarize|verify)\b"
    r"|\b(?:tell\s+me|update\s+me\s+on)\b"
    r"|(?:\ud655\uc778|\uc810\uac80|\uac80\uc99d|\ucc3e|\uac80\uc0c9|\uc870\ud68c|\uc77d|\uc5f4|\ubaa9\ub85d|\ubcf4\uc5ec|\ub85c\ub4dc|\uc694\uc57d|"
    r"\uc54c\ub824\s*(?:\uc918|\uc8fc\uc138\uc694|\uc8fc\uc2ed\uc2dc\uc624)|"
    r"\ubcf4\uc5ec\s*(?:\uc918|\uc8fc\uc138\uc694)|\uc815\ub9ac\ud574\s*(?:\uc918|\uc8fc\uc138\uc694)|"
    r"\uc694\uc57d\ud574\s*(?:\uc918|\uc8fc\uc138\uc694))",
    re.IGNORECASE,
)
_HOST_NATIVE_DYNAMIC_STATE_QUERY_RE = re.compile(
    r"\b(?:active|available|current(?:ly)?|exists?|installed|latest|loaded|running|status)\b"
    r"|(?:\ud604\uc7ac|\ucd5c\uc2e0|\uc124\uce58|\ub85c\ub4dc|\uc2e4\ud589\s*\uc911|\ud65c\uc131|\uc0c1\ud0dc|\uc874\uc7ac|\ubc84\uc804)",
    re.IGNORECASE,
)
_HOST_NATIVE_STABLE_CURRENT_CONCEPT_RE = re.compile(
    r"\b(?:electric(?:al)?\s+)?current\b[^.!?]{0,64}"
    r"\b(?:amperage|circuit|electricity|resistance|voltage)\b"
    r"|\b(?:amperage|circuit|electricity|resistance|voltage)\b[^.!?]{0,64}"
    r"\b(?:electric(?:al)?\s+)?current\b",
    re.IGNORECASE,
)
_HOST_NATIVE_VERSION_QUERY_RE = re.compile(r"\bversions?\b", re.IGNORECASE)
_HOST_NATIVE_CONCEPTUAL_PREFIX_RE = re.compile(
    r"^\s*(?:(?:can|could|would)\s+you\s+(?:please\s+)?(?:define|describe|explain)|"
    r"(?:please\s+)?(?:define|describe|explain)(?:\s+how|\s+what|\s+why)?|"
    r"(?:please\s+)?(?:outline|summarize)\s+(?:how|what|why)|"
    r"how\s+(?:can|do|does)|what\s+(?:are|does|is)(?!\s+in\b)|why\s+(?:do|does|is))\b"
    r"|^\s*[\w.+#-]{1,40}(?:\uc774|\uac00|\uc740|\ub294)\s*"
    r"(?:\ubb50\uc57c|\ubb50\uc608\uc694|\ubb34\uc5c7\uc774\uc57c|\ubb34\uc2a8\s*\ub73b\uc774\uc57c)"
    r"|^\s*.+(?:\ub77c\ub294|\uc774\ub77c\ub294)\s*(?:\ub9d0|\ub2e8\uc5b4|\uc6a9\uc5b4).*(?:\ubb50\uc57c|\ubb34\uc2a8\s*\ub73b)"
    r"|^\s*.+(?:\uac1c\ub150|\ub73b|\uc758\ubbf8|\ucc28\uc774|\ube44\uad50).*(?:\uc124\uba85|\uc54c\ub824)",
    re.IGNORECASE,
)
_HOST_NATIVE_WORKSPACE_TARGET_RE = re.compile(
    r"\b(?:branch(?:es)?|checkouts?|codebases?|cwd|repositories|repository|repos?|source\s+trees?|"
    r"working\s+director(?:y|ies)|working\s+trees?|workspaces?|worktrees?)\b"
    r"|(?:\ube0c\ub79c\uce58|\uc800\uc7a5\uc18c|\ub808\ud3ec\uc9c0\ud1a0\ub9ac|\uccb4\ud06c\uc544\uc6c3|"
    r"\uc791\uc5c5\s*\uacf5\uac04|\uc6cc\ud06c\s*\uc2a4\ud398\uc774\uc2a4|\uc791\uc5c5\s*\ud2b8\ub9ac|\uc6cc\ud06c\s*\ud2b8\ub9ac|"
    r"(?:\ud604\uc7ac|\uc791\uc5c5)\s*(?:\uacbd\ub85c|\ub514\ub809\ud130\ub9ac))",
    re.IGNORECASE,
)
_HOST_NATIVE_SOURCE_ARTIFACT_RE = re.compile(
    r"\b(?:changelogs?|change\s+logs?|commit\s+histor(?:y|ies)|git\s+status|release\s+histor(?:y|ies)|"
    r"release\s+notes?|revision\s+histor(?:y|ies)|update\s+(?:histor(?:y|ies)|logs?))\b"
    r"|(?:\ubcc0\uacbd\s*(?:\ub0b4\uc5ed|\uc774\ub825|\uae30\ub85d|\ub85c\uadf8|\uc0ac\ud56d)|"
    r"(?:\uac31\uc2e0|\uc5c5\ub370\uc774\ud2b8)\s*(?:\ub0b4\uc5ed|\uc774\ub825|\uae30\ub85d|\ub85c\uadf8|\uc0ac\ud56d)|"
    r"\ub9b4\ub9ac\uc2a4\s*(?:\ub178\ud2b8|\ub0b4\uc5ed|\uc774\ub825|\uae30\ub85d)|"
    r"\ucee4\ubc0b\s*(?:\ub0b4\uc5ed|\uc774\ub825)|\uae43\s*\uc0c1\ud0dc)",
    re.IGNORECASE,
)
_HOST_NATIVE_FILESYSTEM_COLLECTION_RE = re.compile(
    r"\b(?:directories|directory|files?|folders?|paths?)\b"
    r"|(?:\ud30c\uc77c|\ud3f4\ub354|\ub514\ub809\ud130\ub9ac|\uacbd\ub85c)",
    re.IGNORECASE,
)
_HOST_NATIVE_INFORMATION_REQUEST_RE = re.compile(
    r"\?|\b(?:how\s+many|what|which|where)\b|"
    r"^\s*(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|please\s+)?"
    r"(?:check|count|enumerate|find|give\s+me|identify|inspect|list|locate|name|read|report|scan|search|show|state|summarize|"
    r"tell\s+me|update\s+me\s+on|verify)\b|"
    r"(?:\uc54c\ub824\s*(?:\uc918|\uc8fc\uc138\uc694|\uc8fc\uc2ed\uc2dc\uc624)|"
    r"\ubcf4\uc5ec\s*(?:\uc918|\uc8fc\uc138\uc694)|\uc815\ub9ac\ud574\s*(?:\uc918|\uc8fc\uc138\uc694)|"
    r"\uc694\uc57d\ud574\s*(?:\uc918|\uc8fc\uc138\uc694)|\uba87\s*\uac1c(?:\uc57c|\uc608\uc694|\uc778\uc9c0)?|"
    r"\uac1c\uc218|\ubaa9\ub85d|"
    r"(?:\ubb50|\ubb34\uc5c7)(?:\uc774|\uac00)?\s*.*(?:\ub4e4\uc5b4|\ub2f4\uaca8|\uc788|\uc801\ud600)|"
    r"\ubb50\uc57c|\ubb50\uc608\uc694|\ubb50\uc9c0|\uc5b4\ub514\uc57c|\uc5b4\ub514\uc608\uc694|\uc5b4\ub514\uc9c0|"
    r"\uc5b4\ub290\b.*\uc778\uc9c0|\uc5b4\ub5bb\uac8c\s*\ub3fc)",
    re.IGNORECASE,
)
_HOST_NATIVE_CONTEXT_BOUND_RE = re.compile(
    r"\b(?:active|checked\s+out|current(?:ly)?|here|latest|local|my|our|this|these|those|your)\b"
    r"|\b(?:are|do)\s+we\b|\bwe\s+(?:are|have|use)\b|"
    r"(?:\ud604\uc7ac|\ud65c\uc131|\uc5ec\uae30|\uc6b0\ub9ac|\ub0b4)\b|"
    r"(?:\uc774|\uadf8|\uc800|\uc704|\uc55e\uc758)\s*(?:\ud504\ub85c\uc81d\ud2b8|\ube0c\ub79c\uce58|\uc800\uc7a5\uc18c|"
    r"\ub808\ud3ec\uc9c0\ud1a0\ub9ac|\uccb4\ud06c\uc544\uc6c3|\uc791\uc5c5\s*\uacf5\uac04|\uc6cc\ud06c\s*\uc2a4\ud398\uc774\uc2a4|"
    r"\uc791\uc5c5\s*\ud2b8\ub9ac|\uc6cc\ud06c\s*\ud2b8\ub9ac|\ud30c\uc77c|\ud3f4\ub354|\ub514\ub809\ud130\ub9ac|\uacbd\ub85c)",
    re.IGNORECASE,
)
_HOST_NATIVE_COLLECTION_SCOPE_RE = re.compile(
    r"\b(?:in|inside|under|within|from)\s+(?:the\s+)?(?:current\s+)?"
    r"(?:checkout|codebase|cwd|project|repo|repository|source|src|tests?|workspace|worktree)\b|"
    r"(?:\ud504\ub85c\uc81d\ud2b8|\uc800\uc7a5\uc18c|\ub808\ud3ec\uc9c0\ud1a0\ub9ac|\uc791\uc5c5\s*\uacf5\uac04|"
    r"\uc6cc\ud06c\s*\uc2a4\ud398\uc774\uc2a4|src|tests?)\s*(?:\uc548|\uc544\ub798|\ub0b4\ubd80|\uc5d0|\uc5d0\uc11c|\uc758)",
    re.IGNORECASE,
)
_HOST_NATIVE_DEFINITE_WORKSPACE_RE = re.compile(
    r"\bthe\s+(?:active\s+|current\s+|local\s+)?"
    r"(?:branch|checkout|codebase|repository|repo|workspace|worktree)\b",
    re.IGNORECASE,
)
_HOST_NATIVE_VISIBLE_CONTEXT_RE = re.compile(
    r"\bwhat\s+did\s+(?:i|you)\s+just\s+(?:ask|say|write)\b|"
    r"\b(?:answer|message|paragraph|question|request|sentence|text|wording)\s+"
    r"(?:that\s+)?(?:i|you)\s+just\s+(?:asked|said|wrote)\b|"
    r"\b(?:my|the|your)\s+(?:last|previous)\s+"
    r"(?:answer|message|paragraph|question|request|sentence|text|wording)\b|"
    r"\b(?:answer|message|paragraph|question|request|sentence|text|wording)\s+above\b|"
    r"(?:\ubc29\uae08|\uc9c1\uc804|\uc774\uc804|(?:\ubc14\ub85c\s*)?\uc704(?:\uc5d0)?|(?:\ubc14\ub85c\s*)?\uc55e(?:\uc5d0|\uc5d0\uc11c)?)\s*"
    r"(?:\ub0b4\uac00|\ub124\uac00|\uc0ac\uc6a9\uc790\uac00)?\s*"
    r"(?:\uc4f4|\uc791\uc131\ud55c|\ub9d0\ud55c|\ubb3c\uc740|\ubcf4\ub0b8)?\s*"
    r"(?:\ubb38\uc7a5|\uba54\uc2dc\uc9c0|\uc9c8\ubb38|\uc694\uccad|\ub2f5\ubcc0|\uae00|\ud14d\uc2a4\ud2b8|\ub0b4\uc6a9)|"
    r"(?:\ub0b4\uac00|\ub124\uac00|\uc0ac\uc6a9\uc790\uac00)\s*\ubc29\uae08\s*"
    r"(?:\uc4f4|\uc791\uc131\ud55c|\ub9d0\ud55c|\ubb3c\uc740|\ubcf4\ub0b8)\s*"
    r"(?:\ubb38\uc7a5|\uba54\uc2dc\uc9c0|\uc9c8\ubb38|\uc694\uccad|\ub2f5\ubcc0|\uae00|\ud14d\uc2a4\ud2b8|\ub0b4\uc6a9)",
    re.IGNORECASE,
)
_HOST_NATIVE_VISIBLE_CONTEXT_ACTION_RE = re.compile(
    r"^\s*(?:what\s+did\s+(?:i|you)\s+just\s+(?:ask|say|write)|"
    r"(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+)?"
    r"(?:paraphrase|quote|repeat|restate|summarize|translate)\b|"
    r".*(?:\uc694\uc57d|\uc815\ub9ac|\ub2e4\uc2dc\s*\ub9d0|\ubc14\uafd4\s*\ub9d0|\ubc18\ubcf5|\ubc88\uc5ed|\uc778\uc6a9)"
    r"(?:\ud574\s*)?(?:\uc918|\uc8fc\uc138\uc694))",
    re.IGNORECASE,
)
_HOST_NATIVE_WORD_DEFINITION_FORM_RE = re.compile(
    r"^\s*(?:define\b|explain\s+(?:the\s+)?(?:concept|meaning|term)\b|what\s+(?:does\b.*\bmean|is|are)\b)|"
    r"^\s*[\w.+#-]{1,40}(?:\uc774|\uac00|\uc740|\ub294)\s*"
    r"(?:\ubb50\uc57c|\ubb50\uc608\uc694|\ubb34\uc5c7\uc774\uc57c|\ubb34\uc2a8\s*\ub73b\uc774\uc57c)|"
    r"(?:\ub77c\ub294|\uc774\ub77c\ub294)\s*(?:\ub9d0|\ub2e8\uc5b4|\uc6a9\uc5b4).*(?:\ubb50\uc57c|\ubb34\uc2a8\s*\ub73b)|"
    r"(?:\uac1c\ub150|\ub73b|\uc758\ubbf8).*(?:\uc124\uba85|\uc54c\ub824)",
    re.IGNORECASE,
)
_HOST_NATIVE_PROPER_TECHNOLOGY_RE = re.compile(
    r"\b[A-Z][A-Za-z0-9+_-]*\.[A-Za-z][A-Za-z0-9]*\b"
)
_HOST_NATIVE_STATE_SUBJECT_RE = re.compile(
    r"\b(?:app|application|branch|checkout|deployment|environment|installation|package|plugin|process|"
    r"release|repo|repository|runtime|service|session|status|version|workspace|worktree)\b|"
    r"(?:\uc571|\uc560\ud50c\ub9ac\ucf00\uc774\uc158|\ube0c\ub79c\uce58|\uccb4\ud06c\uc544\uc6c3|\ubc30\ud3ec|\ud658\uacbd|\uc124\uce58|"
    r"\ud328\ud0a4\uc9c0|\ud50c\ub7ec\uadf8\uc778|\ud504\ub85c\uc138\uc2a4|\ub9b4\ub9ac\uc2a4|\ub7f0\ud0c0\uc784|\uc11c\ube44\uc2a4|"
    r"\uc138\uc158|\uc0c1\ud0dc|\ubc84\uc804|\uc800\uc7a5\uc18c|\uc791\uc5c5\s*\uacf5\uac04|\uc6cc\ud06c\s*\ud2b8\ub9ac)",
    re.IGNORECASE,
)


def _host_native_visible_context_only_question(text: str) -> bool:
    return bool(
        _HOST_NATIVE_VISIBLE_CONTEXT_RE.search(text)
        and _HOST_NATIVE_VISIBLE_CONTEXT_ACTION_RE.search(text)
    )


def _host_native_stable_word_definition(text: str, request_act: Any) -> bool:
    if not _HOST_NATIVE_WORD_DEFINITION_FORM_RE.search(text):
        return False
    clauses = tuple(getattr(request_act, "clauses", ()) or ())
    if any(
        clause.authorized or (clause.mutating and not clause.negated)
        for clause in clauses
    ):
        return False
    return not bool(
        _HOST_NATIVE_CONTEXT_BOUND_RE.search(text)
        or _HOST_NATIVE_COLLECTION_SCOPE_RE.search(text)
        or _HOST_NATIVE_DEFINITE_WORKSPACE_RE.search(text)
        or _HOST_NATIVE_NAMED_RESOURCE_RE.search(text)
        or _HOST_NATIVE_STATE_SUBJECT_RE.search(text)
    )


_HOST_NATIVE_GENERIC_MECHANISM_RE = re.compile(
    r"^\s*(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+)?"
    r"(?:describe|explain|outline|summarize)\s+how\b.*\b(?:behaves?|functions?|works?)\b",
    re.IGNORECASE,
)


def _host_native_stable_concept_question(text: str) -> bool:
    if (
        _HOST_NATIVE_CONTEXT_BOUND_RE.search(text)
        or _HOST_NATIVE_COLLECTION_SCOPE_RE.search(text)
        or _HOST_NATIVE_DEFINITE_WORKSPACE_RE.search(text)
        or _HOST_NATIVE_NAMED_RESOURCE_RE.search(text)
    ):
        return False
    if _HOST_NATIVE_GENERIC_MECHANISM_RE.search(text):
        return True
    return bool(
        _HOST_NATIVE_CONCEPTUAL_PREFIX_RE.search(text)
        and not _HOST_NATIVE_ACCESS_ACTION_RE.search(text)
    )


def _host_native_technology_concept_question(text: str) -> bool:
    return bool(
        _HOST_NATIVE_PROPER_TECHNOLOGY_RE.search(text)
        and _HOST_NATIVE_CONCEPTUAL_PREFIX_RE.search(text)
        and not _HOST_NATIVE_ACCESS_ACTION_RE.search(text)
        and not _HOST_NATIVE_CONTEXT_BOUND_RE.search(text)
        and not _HOST_NATIVE_STATE_SUBJECT_RE.search(text)
    )


def _host_native_dynamic_domain_concept_question(text: str) -> bool:
    return bool(
        _HOST_NATIVE_STABLE_CURRENT_CONCEPT_RE.search(text)
        and _HOST_NATIVE_CONCEPTUAL_PREFIX_RE.search(text)
        and not _HOST_NATIVE_ACCESS_ACTION_RE.search(text)
        and not _HOST_NATIVE_STATE_SUBJECT_RE.search(text)
    )


def _host_native_named_resource_requires_runtime(text: str) -> bool:
    if not _HOST_NATIVE_NAMED_RESOURCE_RE.search(text):
        return False
    return not _host_native_technology_concept_question(text)


def _host_native_dynamic_state_requires_runtime(text: str) -> bool:
    if not _HOST_NATIVE_DYNAMIC_STATE_QUERY_RE.search(text):
        return False
    return not _host_native_dynamic_domain_concept_question(text)


def _host_native_clause_requests_authorized_mutation(clause: Any) -> bool:
    return bool(
        clause.authorized
        and (clause.mutating or "execute" in clause.action_classes)
    )


def _host_native_explicit_noop_lookup(text: str, request_act: Any) -> bool:
    clauses = tuple(getattr(request_act, "clauses", ()) or ())
    return bool(
        clauses
        and _HOST_NATIVE_ACCESS_ACTION_RE.search(text)
        and any("inspect" in clause.action_classes for clause in clauses)
        and not any(clause.authorized for clause in clauses)
        and all(clause.negated or clause.explicit_nonexecution for clause in clauses)
    )


def _host_native_source_or_workspace_query_requires_runtime(text: str) -> bool:
    workspace_target = bool(_HOST_NATIVE_WORKSPACE_TARGET_RE.search(text))
    source_artifact = bool(_HOST_NATIVE_SOURCE_ARTIFACT_RE.search(text))
    collection_target = bool(_HOST_NATIVE_FILESYSTEM_COLLECTION_RE.search(text))
    if not (workspace_target or source_artifact or collection_target):
        return False
    if not _HOST_NATIVE_INFORMATION_REQUEST_RE.search(text):
        return False

    context_bound = bool(
        _HOST_NATIVE_CONTEXT_BOUND_RE.search(text)
        or _HOST_NATIVE_COLLECTION_SCOPE_RE.search(text)
        or _HOST_NATIVE_DEFINITE_WORKSPACE_RE.search(text)
    )
    stable_conceptual = bool(
        not context_bound and _host_native_stable_concept_question(text)
    )
    if stable_conceptual:
        return False

    if workspace_target or source_artifact:
        return True
    return bool(
        context_bound
        or _HOST_NATIVE_ACCESS_ACTION_RE.search(text)
        or re.search(r"\bhow\s+many\b", text, re.IGNORECASE)
        or re.search(r"(?:\uba87\s*\uac1c|\uac1c\uc218)", text)
    )


def _host_native_fast_path_trigger_requires_runtime(
    trigger_text: str,
    request_act: Any = None,
) -> bool:
    text = str(trigger_text or "").strip()
    if not text:
        return True
    if request_act is None:
        try:
            request_act = parse_request_act(text)
        except Exception:
            return True

    if _host_native_explicit_noop_lookup(text, request_act):
        return False

    if any(
        _host_native_clause_requests_authorized_mutation(clause)
        for clause in request_act.clauses
    ):
        return True
    if _host_native_named_resource_requires_runtime(text):
        return True
    if _host_native_source_or_workspace_query_requires_runtime(text):
        return True

    action_requires_access = bool(_HOST_NATIVE_ACCESS_ACTION_RE.search(text))
    dynamic_state_lookup = _host_native_dynamic_state_requires_runtime(text)
    version_lookup = bool(
        action_requires_access and _HOST_NATIVE_VERSION_QUERY_RE.search(text)
    )
    if dynamic_state_lookup or version_lookup:
        return True

    conceptual = bool(_HOST_NATIVE_CONCEPTUAL_PREFIX_RE.search(text))
    if conceptual:
        return False

    stateful_targets = {
        "cloud_resource",
        "credential",
        "database",
        "filesystem",
        "orchestrated_resource",
        "protection",
        "source",
        "storage_device",
    }
    target_classes = {
        target
        for clause in request_act.clauses
        for target in clause.target_classes
    }
    return bool(action_requires_access and target_classes & stateful_targets)


def _is_valid_micro_front_door_packet(data: Dict[str, Any]) -> bool:
    if data.get("m") != "kh_fd_micro" or type(data.get("v")) is not int or data.get("v") != 1:
        return False
    if str(data.get("s", "")) not in {"ok", "blocked"}:
        return False

    classification = data.get("cls")
    route = data.get("r")
    gate = data.get("g")
    goal = data.get("ga")
    token = data.get("t")
    if not all(isinstance(value, dict) for value in [classification, route, gate, goal, token]):
        return False
    if str(classification.get("c", "")) not in {"l", "m", "h", "a"}:
        return False
    if str(classification.get("x", "")) not in {"direct", "skill", "dag", "clarify"}:
        return False
    if "d" in classification and str(classification.get("d", "")) not in {
        "sw",
        "db",
        "product",
        "ops",
        "doc",
        "general",
    }:
        return False

    if str(route.get("r", "")) not in {"direct", "single", "hybrid", "clarify"}:
        return False
    if "c" in route and not str(route.get("c", "")).strip():
        return False

    gate_status = str(gate.get("s", ""))
    if gate_status not in {"ok", "preflight", "brainstorm", "clarify", "credential", "stop"}:
        return False
    if type(gate.get("ok")) is not bool:
        return False
    if bool(gate["ok"]) != (gate_status == "ok"):
        return False

    if type(goal.get("r")) is not bool:
        return False
    if str(goal.get("s", "")) not in {"p", "e", "n", "u"}:
        return False
    if str(goal.get("b", "")) not in {"k", "h", "y", "u"}:
        return False

    token_status = str(token.get("s", ""))
    if token_status not in {"used", "not_needed", "pass", "blocked"}:
        return False
    if type(token.get("u")) is not bool or not str(token.get("why", "")).strip():
        return False
    if bool(token["u"]) != (token_status == "used"):
        return False
    if token_status == "used":
        if type(token.get("saved")) is not int or token.get("saved", -1) < 0:
            return False
        ratio = token.get("ratio")
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 <= ratio <= 1:
            return False

    authorization = data.get("auth")
    if authorization is not None:
        if not isinstance(authorization, dict) or type(authorization.get("stop")) is not bool:
            return False
        if "s" in authorization and str(authorization.get("s", "")) not in {
            "gate_block",
            "next_block",
            "ok",
        }:
            return False
    return True


def _is_valid_compact_front_door_packet(data: Dict[str, Any]) -> bool:
    classification = data.get("classification", {})
    route = data.get("plugin_route", {})
    gate = data.get("execution_gate", {})
    token_decision = data.get("token_optimizer", {})
    skill_source = data.get("skill_source", {})
    return bool(
        data.get("summary_mode") == "ultra_compact"
        and str(data.get("front_door_status", "")).strip()
        and isinstance(classification, dict)
        and "complexity" in classification
        and "recommended_execution" in classification
        and isinstance(route, dict)
        and "route" in route
        and isinstance(gate, dict)
        and "status" in gate
        and "can_execute" in gate
        and isinstance(token_decision, dict)
        and _is_valid_normalized_front_door_token_decision(token_decision)
        and isinstance(skill_source, dict)
        and bool(skill_source)
    )


def _is_valid_normalized_micro_front_door_packet(data: Dict[str, Any]) -> bool:
    protocol = data.get("micro_protocol", {})
    route = data.get("plugin_route", {})
    gate = data.get("execution_gate", {})
    token_decision = data.get("token_optimizer", {})
    authorization = data.get("execution_authorization", {})
    actions = data.get("required_next_action_codes")
    return bool(
        data.get("summary_mode") == "micro"
        and protocol == {"marker": "kh_fd_micro", "version": 1}
        and str(data.get("front_door_status", "")) in {"ok", "blocked"}
        and isinstance(route, dict)
        and route.get("route") in {"direct", "single", "hybrid", "clarify"}
        and isinstance(gate, dict)
        and type(gate.get("can_execute")) is bool
        and isinstance(token_decision, dict)
        and _is_valid_normalized_front_door_token_decision(token_decision)
        and isinstance(authorization, dict)
        and type(authorization.get("must_stop_before_execution")) is bool
        and isinstance(actions, list)
        and all(isinstance(action, str) and action for action in actions)
    )


def _is_valid_normalized_front_door_token_decision(
    decision: Dict[str, Any],
) -> bool:
    status = str(decision.get("status", ""))
    if status not in {"used", "considered_not_needed", "passthrough", "blocked"}:
        return False
    if type(decision.get("used")) is not bool or decision["used"] != (status == "used"):
        return False
    if not str(decision.get("reason_code", "")).strip():
        return False
    if status != "used":
        return True
    saved = decision.get("saved")
    ratio = decision.get("ratio")
    return bool(
        type(saved) is int
        and saved >= 0
        and not isinstance(ratio, bool)
        and isinstance(ratio, (int, float))
        and 0 <= ratio <= 1
    )


def _normalize_full_summary_front_door_packet(data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(data)
    normalized.pop("token_optimizer", None)
    token_decision = _normalize_full_summary_token_optimizer_decision(
        data.get("token_optimizer_decision")
    )
    if token_decision:
        normalized["token_optimizer"] = token_decision
    if "required_next_action_codes" not in normalized:
        action_codes = _normalized_full_summary_action_codes(data)
        if action_codes:
            normalized["required_next_action_codes"] = action_codes
    return normalized


def _normalized_full_summary_action_codes(data: Mapping[str, Any]) -> List[str]:
    actions = data.get("required_next_actions")
    immediate = data.get("immediate_next_skills")
    gate = data.get("execution_gate", {}) or {}
    authorization = data.get("execution_authorization", {}) or {}
    if not (
        isinstance(actions, list)
        and actions
        and all(isinstance(action, str) and action.strip() for action in actions)
        and isinstance(immediate, list)
        and immediate
        and all(isinstance(skill, str) and skill.strip() for skill in immediate)
        and isinstance(gate, Mapping)
        and isinstance(authorization, Mapping)
    ):
        return []

    stop_prefix = (
        "BLOCKING FRONT-DOOR RESULT: "
        "`execution_authorization.must_stop_before_execution=true`."
    )
    has_stop = any(action.startswith(stop_prefix) for action in actions)
    has_immediate = any(
        action.startswith("NEXT SKILL EXECUTION: apply `")
        and all(f"`{skill}`" in action for skill in immediate)
        for action in actions
    )
    if not (has_stop and has_immediate):
        return []

    codes = ["stop_before_task_work", "apply_immediate_next_skills"]
    gate_requirements = gate.get("required_before_execution")
    if (
        str(gate.get("status", "") or "").strip().lower()
        == "blocked_until_large_work_preflight"
        and isinstance(gate_requirements, list)
        and "large_work_orchestration_bundle" in gate_requirements
        and any(action.startswith("HARD PRE-FLIGHT STOP:") for action in actions)
    ):
        codes.append("large_work_preflight")
    return codes


def _normalize_full_summary_token_optimizer_decision(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    status = str(value.get("token_optimizer_status", "")).strip()
    reason = str(value.get("token_optimizer_status_reason", "")).strip()
    provider = str(
        value.get("token_optimizer_provider", "") or value.get("provider", "")
    ).strip()
    expected_used = status == "used"
    if status not in {"used", "considered_not_needed", "passthrough", "blocked"}:
        return {}
    if not reason or provider not in {"kh", "rtk", "hybrid"}:
        return {}
    if (
        value.get("token_optimizer_gate_status") != "checked"
        or value.get("front_door_gate") is not True
    ):
        return {}
    if str(value.get("actual_optimization_status", "")).strip() != status:
        return {}
    for key in [
        "optimization_applied",
        "actual_optimization_used",
        "actual_optimization_claimed",
    ]:
        if type(value.get(key)) is not bool or value[key] != expected_used:
            return {}
    evidence = value.get("evidence")
    if (
        not isinstance(evidence, list)
        or "front_door_token_optimizer_gate" not in evidence
    ):
        return {}
    if not expected_used and not str(value.get("not_used_reason", "")).strip():
        return {}

    normalized: Dict[str, Any] = {
        "status": status,
        "used": expected_used,
        "reason_code": _full_summary_token_reason_code(value),
    }
    if expected_used:
        normalized.update(
            {
                "provider": provider,
                "saved": value.get("estimated_payload_tokens_saved"),
                "ratio": value.get("estimated_payload_token_savings_ratio"),
            }
        )
    if not _is_valid_normalized_front_door_token_decision(normalized):
        return {}
    return normalized


def _full_summary_token_reason_code(decision: Dict[str, Any]) -> str:
    status = str(decision.get("token_optimizer_status", "")).strip()
    if status in {"used", "passthrough", "blocked"}:
        return status
    reason = str(
        decision.get("not_used_reason", "")
        or decision.get("token_optimizer_status_reason", "")
    ).lower()
    if (
        "no command output" in reason
        or "subagent transcript" in reason
        or "compressible artifact" in reason
    ):
        return "no_candidate_output"
    if "too small" in reason or "small" in reason:
        return "small_input"
    if "contract" in reason or "source-of-truth" in reason or "preserve" in reason:
        return "quality_passthrough"
    return status


def _normalize_micro_front_door_packet(data: Dict[str, Any]) -> Dict[str, Any]:
    status = str(data.get("s", "")).strip().lower()
    route = data.get("r", {}) or {}
    gate = data.get("g", {}) or {}
    if not status or not isinstance(route, dict) or not isinstance(gate, dict):
        return {}

    plugin_route: Dict[str, Any] = {"route": str(route.get("r", "") or "")}
    controller = str(route.get("c", "") or "")
    if controller:
        plugin_route["controller"] = controller

    gate_status_codes = {
        "ok": "allowed",
        "preflight": "blocked_until_large_work_preflight",
        "brainstorm": "blocked_until_brainstorming_handoff",
        "clarify": "blocked_until_clarification",
        "credential": "blocked_until_credential_safety_gate",
        "stop": "blocked_until_user_stop_checkpoint",
    }
    skill_codes = {
        "brainstorm": "brainstorming-harness",
        "goal": "goal-state-harness",
        "workflow": "workflow-usability-harness",
        "host": "host-agent-orchestration",
        "parallel": "parallel-orchestration-harness",
        "pb2cs": "pb-to-csharp-migration-harness",
        "sql-style": "sql-formatting-style-harness",
        "review": "review-gate-harness",
        "qa": "qa-gate-harness",
        "verify": "verification-before-completion-harness",
    }
    immediate = [
        skill_codes.get(str(item), str(item))
        for item in data.get("next", []) or []
        if str(item).strip()
    ]
    normalized: Dict[str, Any] = {
        "summary_mode": "micro",
        "micro_protocol": {"marker": "kh_fd_micro", "version": 1},
        "front_door_status": status,
        "plugin_route": plugin_route,
        "execution_gate": {
            "status": gate_status_codes.get(
                str(gate.get("s", "") or ""),
                str(gate.get("s", "") or ""),
            ),
            "can_execute": bool(gate.get("ok")),
        },
        "immediate_next_skills": immediate,
    }
    action_codes = {
        "stop": "stop_before_task_work",
        "next": "apply_immediate_next_skills",
        "preflight": "large_work_preflight",
        "brainstorm": "brainstorming_handoff",
        "provider": "apply_selected_provider",
    }
    normalized["required_next_action_codes"] = [
        action_codes.get(str(item), str(item))
        for item in data.get("act", []) or []
        if str(item).strip()
    ]
    authorization = data.get("auth", {}) or {}
    if isinstance(authorization, dict) and "stop" in authorization:
        authorization_statuses = {
            "gate_block": "blocked_by_execution_gate",
            "next_block": "blocked_by_pending_immediate_skill_gate",
            "ok": "allowed",
        }
        normalized["execution_authorization"] = {
            "must_stop_before_execution": bool(authorization.get("stop")),
            "status": authorization_statuses.get(
                str(authorization.get("s", "") or ""),
                str(authorization.get("s", "") or ""),
            ),
        }
    token_decision = data.get("t", {}) or {}
    if isinstance(token_decision, dict) and str(token_decision.get("s", "")).strip():
        token_status_codes = {
            "not_needed": "considered_not_needed",
            "pass": "passthrough",
        }
        normalized_token = {
            "status": token_status_codes.get(
                str(token_decision.get("s", "")),
                str(token_decision.get("s", "")),
            ),
            "used": bool(token_decision.get("u")),
            "reason_code": str(token_decision.get("why", "") or ""),
        }
        for key in ["saved", "ratio"]:
            if key in token_decision:
                normalized_token[key] = token_decision[key]
        normalized["token_optimizer"] = normalized_token
    if status in {"ok", "success", "passed"}:
        normalized["runtime_applied_skills"] = ["always-on-front-door"]
    return normalized


def _json_object_from_text(text: str) -> Dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        data = load_json_without_duplicate_keys(text[start : end + 1])
    except (json.JSONDecodeError, DuplicateJsonKeyError):
        return {}
    return data if isinstance(data, dict) else {}


def _standalone_json_object_from_text(text: str) -> Dict[str, Any]:
    candidate = str(text or "").strip()
    if not candidate.startswith("{") or not candidate.endswith("}"):
        return {}
    try:
        data = load_json_without_duplicate_keys(candidate)
    except (json.JSONDecodeError, DuplicateJsonKeyError):
        return {}
    return data if isinstance(data, dict) else {}


def _structured_front_door_acceptance_outputs(
    skill_name: str,
    observations: Dict[str, Any],
) -> Set[str]:
    if skill_name not in {"always-on-front-door", "automatic-intake-harness"}:
        return set()

    satisfied: Set[str] = set()
    split_fields = ACCEPTANCE_OUTPUT_MARKERS[skill_name]["status_split"]
    for text in observations.get("active_evidence", []):
        clean_text = _strip_passive_prefix(str(text))
        if _is_valid_host_native_front_door_packet(clean_text):
            satisfied.update({"intake_evidence", "status_split"})
            continue
        data = _front_door_json(clean_text)
        if not _is_valid_compact_front_door_packet(data):
            continue
        satisfied.add("intake_evidence")
        classification = data.get("classification", {})
        route = data.get("plugin_route", {})
        gate = data.get("execution_gate", {})
        if (
            classification.get("recommended_execution") == "direct_answer"
            and route.get("route") == "direct"
            and gate.get("can_execute") is True
            and not any(data.get(field) for field in split_fields)
        ):
            satisfied.add("status_split")
    return satisfied


def _acceptance_for_skill(
    *,
    skill_name: str,
    required: bool,
    status: str,
    observations: Dict[str, Any],
    postmortem: Dict[str, Any],
) -> Dict[str, Any]:
    if not required:
        return {
            "status": "not_required",
            "required_outputs": [],
            "satisfied_outputs": [],
            "missing_outputs": [],
        }

    required_outputs = list(ACCEPTANCE_OUTPUT_MARKERS.get(skill_name, {}).keys())
    if STATUS_RANK.get(status, 0) < STATUS_RANK["considered"]:
        return {
            "status": "missing_application",
            "required_outputs": required_outputs,
            "satisfied_outputs": [],
            "missing_outputs": required_outputs,
        }

    if status in {"considered", "procedural"} and not required_outputs and _has_resolution_rationale(observations):
        return {
            "status": "resolved_by_rationale",
            "required_outputs": required_outputs,
            "satisfied_outputs": [],
            "missing_outputs": [],
        }

    guard_status = _postmortem_acceptance_status(skill_name, postmortem)
    if guard_status == "blocked":
        return {
            "status": "blocked",
            "required_outputs": required_outputs,
            "satisfied_outputs": [],
            "missing_outputs": required_outputs,
        }
    if guard_status == "passed":
        return {
            "status": "passed",
            "required_outputs": required_outputs,
            "satisfied_outputs": required_outputs,
            "missing_outputs": [],
        }

    if not required_outputs:
        return {
            "status": "not_evaluable",
            "required_outputs": [],
            "satisfied_outputs": [],
            "missing_outputs": [],
        }

    active_text = _bounded_text_aggregate(observations.get("active_evidence", []))
    lowered = active_text.lower()
    structured_outputs = _structured_front_door_acceptance_outputs(skill_name, observations)
    satisfied_outputs = []
    missing_outputs = []
    for output_name, markers in ACCEPTANCE_OUTPUT_MARKERS.get(skill_name, {}).items():
        if output_name in structured_outputs or any(marker.lower() in lowered for marker in markers):
            satisfied_outputs.append(output_name)
        else:
            missing_outputs.append(output_name)

    status_value = "passed" if not missing_outputs else "missing_outputs"
    return {
        "status": status_value,
        "required_outputs": required_outputs,
        "satisfied_outputs": satisfied_outputs,
        "missing_outputs": missing_outputs,
    }


def _front_door_route_acceptance(
    evidence: Mapping[str, Any],
    *,
    default: Dict[str, Any],
) -> Dict[str, Any]:
    request_count = int(evidence.get("request_count", 0) or 0)
    satisfied_count = int(evidence.get("satisfied_request_count", 0) or 0)
    selection_modes = list(evidence.get("selection_modes", []) or [])
    valid_modes = {"direct", "host_receipt", "runtime", "specialist"}
    if not (
        evidence.get("all_requests_satisfied") is True
        and request_count > 0
        and satisfied_count == request_count
        and len(selection_modes) == request_count
        and all(mode in valid_modes for mode in selection_modes)
    ):
        return default
    return {
        "status": "passed",
        "required_outputs": ["routing_evidence", "selection_evidence"],
        "satisfied_outputs": ["routing_evidence", "selection_evidence"],
        "missing_outputs": [],
    }


def _postmortem_acceptance_status(skill_name: str, postmortem: Dict[str, Any]) -> str:
    if skill_name == "token-optimizer":
        token_status = postmortem.get("token_optimizer_status", "")
        if token_status == "blocked":
            return "blocked"
        if token_status in {"used", "passthrough", "considered_not_needed"}:
            return "passed"
    if skill_name == "review-gate-harness":
        if postmortem.get("review_status") == "review_incomplete":
            return "blocked"
        if postmortem.get("review_status") in {"passed", "with_fixes"}:
            return "passed"
    if skill_name == "goal-state-harness":
        completion_guard = postmortem.get("completion_guard", {}) or {}
        user_stop_guard = postmortem.get("user_stop_guard", {}) or {}
        if completion_guard.get("status") in {"blocked", "failed", "pending"} or user_stop_guard.get("status") == "blocked":
            return "blocked"
        if completion_guard.get("status") == "passed":
            latest_status = str(completion_guard.get("latest_goal_status", "") or "")
            task_complete_count = int(completion_guard.get("task_complete_count", 0) or 0)
            if task_complete_count <= 0 or latest_status in {"complete", "blocked"}:
                return "passed"
            return ""
    if skill_name in {"host-agent-orchestration", "role-execution-audit-harness", "subagent-review-pipeline"}:
        subagents = postmortem.get("subagent_summary", {}) or {}
        if (
            int(subagents.get("spawned", 0) or 0) > int(subagents.get("closed", 0) or 0)
            or int(subagents.get("timed_out", 0) or 0)
            or int(subagents.get("closed_while_running", 0) or 0)
        ):
            return "blocked"
        if int(subagents.get("spawned", 0) or 0):
            return "passed"
    if skill_name == "verification-before-completion-harness":
        verification_guard = postmortem.get("verification_claim_guard", {}) or {}
        if verification_guard.get("status") == "blocked":
            return "blocked"
        if verification_guard.get("status") == "passed":
            return "passed"
    return ""


def _has_resolution_rationale(observations: Dict[str, Any]) -> bool:
    text = _bounded_text_aggregate(observations.get("active_evidence", [])).lower()
    return any(
        marker in text
        for marker in [
            "considered_not_needed",
            "skipped_with_rationale",
            "blocked",
            "passthrough",
            "no_reusable_learning",
        ]
    )


def _explicit_application(lowered: str, aliases: Set[str]) -> bool:
    if not any(alias.lower() in lowered for alias in aliases):
        return False
    if any(
        marker in lowered
        for marker in [
            "not used",
            "did not use",
            "was not used",
            "not applied",
            "did not apply",
            "was not applied",
            "not executed",
            "did not execute",
        ]
    ):
        return False
    return any(
        marker in lowered
        for marker in [
            '"status": "applied"',
            "'status': 'applied'",
            "status=applied",
            " was used",
            " used ",
            " was applied",
            " applied ",
            " executed",
            " ran ",
            "application_mode",
            '"runtime"',
            "'runtime'",
            "runtime-applied",
            "runtime evidence",
        ]
    )


def _passive_reference(lowered: str) -> bool:
    if lowered.startswith(PASSIVE_REFERENCE_PREFIX):
        return True
    if _looks_like_front_door_runtime_output(lowered):
        return False
    if _looks_like_read_only_command(lowered):
        return True
    if _looks_like_skill_doc_output(lowered):
        return True
    if _looks_like_skill_catalog_listing(lowered):
        return True
    if "skill.md" in lowered and (
        "get-content" in lowered
        or "\\skills\\" in lowered
        or "/skills/" in lowered
        or lowered.lstrip().startswith("---")
        or lowered.lstrip().startswith("# ")
    ):
        return True
    if "uaf_skill_catalog" in lowered and any(flag in lowered for flag in ["--list", "--read", "--check"]):
        return True
    if "defaultprompt" in lowered or '"defaultprompt"' in lowered:
        return True
    if '"skills": "./skills/"' in lowered or "available skills" in lowered:
        return True
    if "\\plugins\\cache\\" in lowered and "\\skills\\" in lowered:
        return True
    return False


def _looks_like_read_only_command(lowered: str) -> bool:
    read_markers = [
        "get-content",
        "select-string",
        "get-childitem",
        "test-path",
        "rg --files",
        "rg -n",
        "rg ",
        "git status",
        "git diff",
        "git show",
        "git grep",
        "git log",
        "git branch",
    ]
    if not any(marker in lowered for marker in read_markers):
        return False
    write_or_runtime_markers = [
        "kh_front_door",
        "front_door.py",
        "apply_patch",
        "python -m src.",
        "python scripts/",
        "new-item",
        "set-content",
        "add-content",
        "remove-item",
        "move-item",
        "copy-item",
        "git commit",
        "git push",
    ]
    return not any(marker in lowered for marker in write_or_runtime_markers)


def _looks_like_external_specialist_direct_question(lowered: str) -> bool:
    if not any(marker in lowered for marker in ["openai", "chatgpt", "codex", "gpt", "api", "model"]):
        return False
    if any(
        marker in lowered
        for marker in [
            "repo",
            "repository",
            "folder",
            "path",
            "file",
            "implement",
            "fix",
            "patch",
            "test",
            "review this code",
            "sql",
        ]
    ):
        return False
    return any(marker in lowered for marker in ["latest", "docs", "documentation", "model", "pricing", "limit", "release", "how do i", "what is", "\ucd94\ucc9c", "\ubb38\uc11c", "\ucd5c\uc2e0", "\ubaa8\ub378"])


def _looks_like_direct_code_question(lowered: str) -> bool:
    if _contains_standalone_action_verb(lowered):
        return False
    question_markers = [
        "?",
        "\ud544\uc694\ud560\uae4c",
        "\uad1c\ucc2e",
        "\ub9de",
        "\uc65c",
        "\uc124\uba85",
        "what",
        "why",
        "do i need",
        "is this needed",
    ]
    if not any(marker in lowered for marker in question_markers):
        return False
    code_markers = [
        "```",
        ";",
        "{",
        "}",
        "if (",
        "try {",
        ".tostring(",
        "dataset",
        "datarow",
        "xtrareport",
        "activator.createinstance",
        "return;",
    ]
    return sum(1 for marker in code_markers if marker in lowered) >= 2


def _contains_standalone_action_verb(lowered: str) -> bool:
    action_verbs = [
        "implement",
        "build",
        "fix",
        "create",
        "modify",
        "refactor",
        "verify",
        "review",
        "test",
        "patch",
        "write",
        "generate",
    ]
    return any(
        re.search(rf"(?<![a-z0-9_]){re.escape(verb)}(?![a-z0-9_])", lowered)
        for verb in action_verbs
    )


def _looks_like_front_door_runtime_output(lowered: str) -> bool:
    if "{" not in lowered or "}" not in lowered:
        return False
    if (
        ('"m": "kh_fd_micro"' in lowered or '"m":"kh_fd_micro"' in lowered)
        and '"s"' in lowered
        and '"r"' in lowered
        and '"g"' in lowered
    ):
        return True
    has_status = '"front_door_status"' in lowered or "'front_door_status'" in lowered
    if not has_status:
        return False
    has_full_status_split = (
        ('"runtime_applied_skills"' in lowered or "'runtime_applied_skills'" in lowered)
        and ('"selected_not_executed_skills"' in lowered or "'selected_not_executed_skills'" in lowered)
    )
    has_followup_markers = (
        '"skill_status_summary"' in lowered
        or "'skill_status_summary'" in lowered
        or '"immediate_next_skills"' in lowered
        or "'immediate_next_skills'" in lowered
    )
    if has_full_status_split and has_followup_markers:
        return True
    return (
        "ultra_compact" in lowered
        and ('"plugin_route"' in lowered or "'plugin_route'" in lowered)
        and ('"execution_gate"' in lowered or "'execution_gate'" in lowered)
        and (
            '"immediate_next_skills"' in lowered
            or "'immediate_next_skills'" in lowered
            or '"required_next_action_codes"' in lowered
            or "'required_next_action_codes'" in lowered
        )
    )


_STRUCTURED_SKILL_CLAIM_KEYS = {
    "application_mode",
    "runtime_applied_skills",
    "runtime_evidence",
    "selected_not_executed_skills",
    "skill_status_summary",
}


def _looks_like_structured_skill_application_claim(text: str) -> bool:
    lowered = str(text or "").lower()
    if "{" not in lowered or "}" not in lowered:
        return False
    data = _json_object_from_text(text)
    if data and _contains_structured_skill_application_claim(data):
        return True
    has_skill_accounting = any(
        f'"{key}"' in lowered or f"'{key}'" in lowered
        for key in _STRUCTURED_SKILL_CLAIM_KEYS
    )
    has_applied_claim = any(
        marker in lowered
        for marker in [
            '"status": "applied"',
            '"status":"applied"',
            "'status': 'applied'",
            "'status':'applied'",
            "runtime-applied",
        ]
    )
    return has_skill_accounting and has_applied_claim


def _contains_structured_skill_application_claim(value: Any) -> bool:
    if isinstance(value, Mapping):
        normalized = {str(key).strip().lower(): item for key, item in value.items()}
        if set(normalized) & _STRUCTURED_SKILL_CLAIM_KEYS:
            return True
        if str(normalized.get("status", "")).strip().lower() == "applied" and (
            set(normalized) & {"name", "skill", "skill_name", "provider"}
        ):
            return True
        return any(
            _contains_structured_skill_application_claim(item)
            for item in normalized.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_structured_skill_application_claim(item) for item in value)
    return False


def _has_front_door_success_or_blocked_evidence(text: str) -> bool:
    data = _front_door_json(text)
    if not data:
        return False
    status = str(data.get("front_door_status", "")).strip().lower()
    runtime_applied = {str(item).strip() for item in data.get("runtime_applied_skills", []) or []}
    if status in {"ok", "success", "passed"} and "always-on-front-door" in runtime_applied:
        return True
    if status in {"ok", "success", "passed"} and data.get("summary_mode") == "ultra_compact":
        return "plugin_route" in data and "execution_gate" in data
    if status == "blocked":
        return _is_immediate_blocked_evidence(text.lower())
    return False


def _looks_like_skill_doc_output(lowered: str) -> bool:
    if "---" in lowered and "name:" in lowered and "description: use when" in lowered:
        return True
    return "usage reference" in lowered and "when to use" in lowered and "uaf" in lowered


def _looks_like_skill_catalog_listing(lowered: str) -> bool:
    marker_hits = sum(
        1
        for marker in [
            "adapter_contract_harness",
            "command_output_harness",
            "parallel_orchestration_harness",
            "request_complexity_router",
            "subagent_review_pipeline",
            "workflow_usability_harness",
        ]
        if marker in lowered
    )
    return marker_hits >= 3


def _is_passive_text(text: str) -> bool:
    return str(text).startswith(PASSIVE_REFERENCE_PREFIX)


def _strip_passive_prefix(text: str) -> str:
    if _is_passive_text(text):
        return text[len(PASSIVE_REFERENCE_PREFIX) :]
    return text


def _bounded_text_aggregate(
    texts: Iterable[str],
    *,
    max_characters: int = _SESSION_TEXT_AGGREGATE_LIMIT,
    item_limit: int = _SESSION_TEXT_AGGREGATE_ITEM_LIMIT,
) -> str:
    if max_characters <= 0 or item_limit <= 0:
        return ""
    first: List[tuple[int, str]] = []
    last: deque[tuple[int, str]] = deque(maxlen=3)
    signals: List[tuple[int, str]] = []
    signal_count = 0
    item_index = 0
    for raw_text in texts:
        text = str(raw_text or "")
        if not text:
            continue
        if len(text) > item_limit:
            edge = max(1, item_limit // 2)
            text = text[:edge] + "\n[KH_TEXT_AGGREGATE_TRUNCATED]\n" + text[-edge:]
        indexed = (item_index, text)
        if len(first) < 3:
            first.append(indexed)
        last.append(indexed)
        lowered = text.lower()
        if any(signal in lowered for signal in _SESSION_TEXT_AGGREGATE_SIGNALS):
            signal_count += 1
            if len(signals) < 8:
                signals.append(indexed)
            else:
                slot = (signal_count * 2654435761) % signal_count
                if slot < 8:
                    signals[slot] = indexed
        item_index += 1
    if item_index == 0:
        return ""

    parts: List[str] = []
    retained = 0
    selected = {index: text for index, text in (*first, *last, *signals)}
    for index in sorted(selected):
        text = selected[index]
        remaining = max_characters - retained
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining]
        parts.append(text)
        retained += len(text) + 1
    return "\n".join(parts)


def _required_skills(
    postmortem: Dict[str, Any],
    text: str,
    active_texts: List[str] | None = None,
    sql_scope_texts: List[str] | None = None,
    analysis_summary: Mapping[str, Any] | None = None,
) -> Dict[str, str]:
    required: Dict[str, str] = {}
    lowered = text.lower()
    summary = analysis_summary or {}
    sql_lowered = (
        str(summary.get("sql_scope_text", "")).lower()
        if "sql_scope_text" in summary
        else _bounded_text_aggregate(
            sql_scope_texts if sql_scope_texts is not None else (active_texts or [text])
        ).lower()
    )
    token_gate = postmortem.get("token_gate", {}) or {}
    subagents = postmortem.get("subagent_summary", {}) or {}
    verification_commands = postmortem.get("verification_commands", []) or []
    sql_output_request = bool(sql_lowered and looks_like_sql_output_request(sql_lowered))
    sql_specialist_scope = _is_sql_specialist_answer_scope(
        postmortem,
        sql_lowered,
        sql_scope_texts,
        sql_output_request=sql_output_request,
        non_front_door_tool_text=(
            str(summary.get("non_front_door_tool_text", ""))
            if "non_front_door_tool_text" in summary
            else None
        ),
    )

    if token_gate.get("required"):
        token_reason = "token gate requires a runtime token-optimizer decision"
        if "subagent_transcripts_require_token_decision" in {
            str(reason) for reason in token_gate.get("reasons", []) or []
        }:
            token_reason = "subagent packets/transcripts require a token decision"
        _add(required, "token-optimizer", token_reason)

    if sql_specialist_scope:
        _add(
            required,
            "sql-formatting-style-harness",
            "actionable SQL output should be checked against the host-local sql-formatting style contract",
        )
        return required

    if _has_nontrivial_work_signals(postmortem, lowered):
        _add(required, "always-on-front-door", "each new user request or task should enter KH front-door before any other work")
        _add(required, "automatic-intake-harness", "each new user request or task should start with automatic intake")
        _add(required, "plugin-composition-policy", "automatic intake should choose direct, single-provider, hybrid, or clarify route")
        _add(required, "request-complexity-router", "automatic intake should classify request complexity before work")
        _add(required, "skill-catalog", "automatic intake should resolve the packaged skill source before claiming skill use")
    if sql_output_request:
        _add(
            required,
            "sql-formatting-style-harness",
            "actionable SQL output should be checked against the host-local sql-formatting style contract",
        )
    if token_gate.get("required") or _large_session(postmortem):
        token_reason = "large or token-heavy session"
        if "subagent_transcripts_require_token_decision" in {
            str(reason) for reason in token_gate.get("reasons", []) or []
        }:
            token_reason = "subagent packets/transcripts require a token decision"
        _require_core_large_work(required, token_reason)
    if subagents.get("spawned", 0) or "spawn_agent" in lowered:
        _add(required, "host-agent-orchestration", "subagents or host delegation appeared in the session")
        _add(required, "subagent-review-pipeline", "subagent work requires packet/review policy")
        _add(required, "role-execution-audit-harness", "claimed subagent/reviewer work needs role execution audit evidence")
        _add(required, "token-optimizer", "subagent packets/transcripts require a token decision")
        if int(subagents.get("spawned", 0) or 0) > 1 or "parallel" in lowered:
            _add(required, "parallel-orchestration-harness", "multiple subagents or parallel work appeared")
    if _has_implementation_execution_signal(lowered):
        _add(required, "host-agent-orchestration", "implementation work should record host/subagent strategy before silently continuing")
        _add(required, "subagent-review-pipeline", "implementation work should record dispatch, review-only, single-controller, or blocked strategy")
        _add(required, "parallel-orchestration-harness", "implementation work should record parallel, sequential, read-only side-agent, or blocked strategy")
        _add(required, "role-execution-audit-harness", "implementation work should record role execution audit or explicit skipped/blocked rationale")
    if postmortem.get("review_status") != "pending" or "reviewer" in lowered or "with fixes" in lowered:
        _add(required, "review-gate-harness", "review findings or reviewer activity appeared")
        _add(required, "quality-gates-harness", "reviewed development work needs quality gates")
    if verification_commands or _mentions_verification(lowered):
        _add(required, "verification-before-completion-harness", "completion or verification claims require fresh verification evidence")
        _add(required, "qa-gate-harness", "verification commands or QA claims appeared")
        _add(required, "quality-gates-harness", "verification needs evidence-before-completion gate")
        _add(required, "command-output-harness", "command output should preserve exit code and actionable failure lines")
        _add(required, "harness-evaluator", "Python/test checks appeared")
    if _mentions_worktree_workflow(lowered):
        _add(required, "worktree-isolation-harness", "git/worktree implementation workflow appeared")
        _add(required, "branch-finishing-harness", "commit, push, branch, or cleanup evidence appeared")
        _add(required, "development-lifecycle-harness", "git/worktree implementation workflow appeared")
        _add(required, "snapshot-state-harness", "large generated changes should record checkpoint or no-snapshot rationale")
    if any(marker in lowered for marker in ["progress.json", "task 1", "task 2", "next_task", "task_status"]):
        _add(required, "plan-execution-harness", "task-plan progress or next-task handoff appeared")
    if any(marker in lowered for marker in ["root cause", "hypothesis", "debug", "unexpected failure", "traceback"]):
        _add(required, "systematic-debugging-harness", "bug diagnosis or unexpected failure appeared")
    if "compound" in lowered or "compound_handoff" in lowered or "memory_candidates" in lowered:
        _add(required, "compound-engineering-harness", "compound handoff or memory candidates appeared")
        _add(required, "workflow-skill-distiller", "compound learning should route to reusable skill/scenario/memory follow-up")
    if "memory_candidates" in lowered or "memory-state-harness" in lowered or "persistent memory" in lowered or "영구메모리" in text:
        _add(required, "memory-state-harness", "memory candidates or persistent memory appeared")
    browser_or_local_app_qa = (
        bool(summary.get("browser_or_local_app_qa"))
        if "browser_or_local_app_qa" in summary
        else any(
            _mentions_browser_or_local_app_qa(chunk.lower())
            for chunk in (active_texts or [text])
            if not _looks_like_front_door_runtime_output(chunk.lower())
        )
    )
    if browser_or_local_app_qa:
        _add(required, "qa-gate-harness", "browser or local app QA appeared")
    if _renderable_artifact_required(lowered):
        _add(required, "artifact-render-qa-harness", "renderable deliverables or artifacts appeared")
        _add(required, "deliverable-template-quality-harness", "deliverables need template quality evidence")
        _add(required, "traceability-matrix-harness", "deliverables should map requirements to evidence")
    if any(marker in lowered for marker in ["adapter-contract", "adapterrequest", "host adapter", "antigravity bridge", "claude code adapter"]):
        _add(required, "adapter-contract-harness", "host/plugin/adapter behavior appeared")
        _add(required, "plugin-composition-policy", "multiple plugins or providers may apply")
    if any(marker in lowered for marker in ["delete ", "remove-item", "drop table", "secret", "api_key", "token=", "permission denied", "destructive", "requires approval"]):
        _add(required, "guard-policy-harness", "permission, secret, or destructive-action risk appeared")
    if (
        _early_domain_discovery_text(lowered)
        and not sql_output_request
        and not _looks_like_direct_code_question(lowered)
    ):
        _add(required, "brainstorming-harness", "early domain discovery appeared")
    if _mentions_architecture_workflow(lowered):
        _add(required, "architect-pipeline", "design or architecture planning appeared")
    if any(marker in lowered for marker in ["domain-orchestration-harness", "work_design", "role_decomposition", "qa/qc", "risk_policy"]):
        _add(required, "domain-orchestration-harness", "domain design/decomposition appeared")
    return required


def _is_sql_specialist_answer_scope(
    postmortem: Dict[str, Any],
    lowered: str,
    active_texts: List[str] | None = None,
    *,
    sql_output_request: bool | None = None,
    non_front_door_tool_text: str | None = None,
) -> bool:
    if not (
        looks_like_sql_output_request(lowered)
        if sql_output_request is None
        else sql_output_request
    ):
        return False
    subagents = postmortem.get("subagent_summary", {}) or {}
    if int(subagents.get("spawned", 0) or 0):
        return False
    if _renderable_artifact_required(lowered):
        return False
    disqualifying_markers = [
        "*** begin patch",
        "apply_patch",
        "add file:",
        "update file:",
        "new-item",
        "out-file",
        "copy-item",
        "move-item",
        "git commit",
        "git push",
        "python -m unittest",
        "pytest",
        "npm test",
        "npm.cmd run test",
        "node --check",
        "browser qa",
        "browser verification",
        "screenshot",
        "worktree",
        "spawn_agent",
    ]
    if any(marker in lowered for marker in disqualifying_markers):
        return False
    if non_front_door_tool_text is None:
        texts = active_texts or [lowered]
        non_front_door_tool_text = _bounded_text_aggregate(
            text.lower()
            for text in texts
            if "function_call" in text.lower()
            and not _looks_like_front_door_prompt_bootstrap(text.lower())
            and "kh_front_door" not in text.lower()
            and "always_on_front_door" not in text.lower()
        )
    if any(marker in non_front_door_tool_text for marker in ["set-content", "remove-item", "invoke-webrequest"]):
        return False
    return True


def _renderable_artifact_required(lowered: str) -> bool:
    if any(
        marker in lowered
        for marker in [
            "render_docx",
            "artifact_render",
            "artifact-render-qa",
            "deliverable_template_quality",
            "export_user_facing_deliverables",
        ]
    ):
        return True
    return bool(
        re.search(
            r"\b(create|created|export|exported|render|rendered|write|wrote|generated|saved)\b"
            r".{0,160}\.(docx|xlsx|svg|dxf|pdf|png)\b",
            lowered,
            re.IGNORECASE | re.DOTALL,
        )
    )


def _mentions_worktree_workflow(lowered: str) -> bool:
    if ".worktrees" in lowered:
        return True
    if any(marker in lowered for marker in ["git worktree", "git commit", "git push"]):
        return True
    without_skill_names = lowered.replace("worktree-isolation-harness", "")
    for negated in [
        "no git or worktree command",
        "no worktree command",
        "without worktree",
        "not using worktree",
        "did not use worktree",
    ]:
        without_skill_names = without_skill_names.replace(negated, "")
    return bool(re.search(r"\bworktree\b", without_skill_names))


def _mentions_architecture_workflow(lowered: str) -> bool:
    without_skill_names = lowered.replace("architect-pipeline", "")
    return any(
        marker in without_skill_names
        for marker in [
            "architecture",
            "design doc",
            "system design",
            "development design",
            "technical spec",
            "functional spec",
            "요구정의",
            "기능정의",
            "개발설계",
            "설계서",
        ]
    )


def _require_core_large_work(required: Dict[str, str], reason: str) -> None:
    for skill in [
        "request-complexity-router",
        "goal-state-harness",
        "development-lifecycle-harness",
        "worktree-isolation-harness",
        "plan-execution-harness",
        "token-optimizer",
        "verification-before-completion-harness",
        "workflow-usability-harness",
        "context-state-harness",
    ]:
        _add(required, skill, reason)


def _add(required: Dict[str, str], skill: str, reason: str) -> None:
    required.setdefault(skill, reason)


def _has_nontrivial_work_signals(postmortem: Dict[str, Any], lowered: str) -> bool:
    token_gate = postmortem.get("token_gate", {}) or {}
    subagents = postmortem.get("subagent_summary", {}) or {}
    if token_gate.get("required"):
        return True
    if int(subagents.get("spawned", 0) or 0):
        return True
    if postmortem.get("verification_commands"):
        return True
    if postmortem.get("review_status") not in {"", "pending", None}:
        return True
    work_tool_markers = [
        "apply_patch",
        "shell_command",
        "custom_tool_call",
        "git commit",
        "git push",
        "python -b",
        "python -m",
        "pytest",
        "unittest",
    ]
    if any(marker in lowered for marker in work_tool_markers):
        return True
    if _looks_like_direct_code_question(lowered):
        return False
    return any(
        marker in lowered
        for marker in [
            "apply_patch",
            "shell_command",
            "custom_tool_call",
            "git commit",
            "git push",
            "build",
            "create",
            "make",
            "implement",
            "fix",
            "modify",
            "refactor",
            "dashboard",
            "verify",
            "python -b",
            "python -m",
            "pytest",
            "unittest",
            "docx",
            "xlsx",
            "svg",
            "dxf",
            "index.html",
            "requirements",
            "architecture",
            "deliverable",
            "verification_status",
            "검증",
            "문서",
            "산출물",
            "요구정의",
        ]
    )


def _large_session(postmortem: Dict[str, Any]) -> bool:
    return int(postmortem.get("line_count", 0) or 0) >= 500 or int(postmortem.get("byte_count", 0) or 0) >= 1_000_000


def _mentions_verification(lowered: str) -> bool:
    return any(
        marker in lowered
        for marker in [
            "python -m unittest",
            "pytest",
            "npm.cmd run test",
            "npm test",
            "node --check",
            "git diff --check",
            "verified",
        ]
    )


def _mentions_browser_or_local_app_qa(lowered: str) -> bool:
    explicit_qa_markers = [
        "browser qa",
        "browser verification",
        "browser check",
        "browser smoke",
        "browser test",
        "in-app browser",
        "playwright",
        "screenshot",
        "localhost",
        "127.0.0.1",
        "file://",
        "http://localhost",
        "opened in browser",
        "rendered in browser",
        "브라우저 검증",
        "브라우저 qa",
        "브라우저 테스트",
        "브라우저 확인",
        "스크린샷",
        "화면 검증",
        "렌더링 검증",
    ]
    if any(marker in lowered for marker in explicit_qa_markers):
        return True
    if "browser" not in lowered and "브라우저" not in lowered:
        return False
    qa_context = ["verify", "verified", "verification", "qa", "smoke", "checked", "검증", "확인"]
    browser_actions = [
        "open browser",
        "opened",
        "navigate",
        "navigated",
        "rendered",
        "inspect",
        "열고",
        "열어",
        "렌더",
        "클릭해",
        "클릭했",
    ]
    return any(marker in lowered for marker in qa_context) and any(marker in lowered for marker in browser_actions)


def _coverage(skill_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    required = [row for row in skill_rows if row["required"]]
    considered_or_better = [row for row in required if STATUS_RANK.get(row["status"], 0) >= STATUS_RANK["considered"]]
    required_applied = [row for row in required if row["status"] == "applied"]
    runtime_applied = [row for row in skill_rows if row["status"] == "applied"]
    runtime_or_considered = [
        row
        for row in skill_rows
        if STATUS_RANK.get(row["status"], 0) >= STATUS_RANK["considered"]
    ]
    accepted = [
        row
        for row in required
        if row.get("acceptance", {}).get("status")
        in {"passed", "resolved_by_rationale", "not_evaluable"}
    ]
    unaccepted = [
        row
        for row in required
        if row.get("acceptance", {}).get("status")
        in {"missing_application", "missing_outputs", "blocked"}
    ]
    return {
        "total_skills": len(skill_rows),
        "observed_skills": sum(1 for row in skill_rows if row["status"] != "absent"),
        "runtime_applied_skills": len(runtime_applied),
        "runtime_applied_skill_names": [row["name"] for row in runtime_applied],
        "active_or_considered_skills": len(runtime_or_considered),
        "required_skills": len(required),
        "required_considered_or_better": len(considered_or_better),
        "required_with_evidence": len(considered_or_better),
        "required_applied": len(required_applied),
        "required_applied_skill_names": [row["name"] for row in required_applied],
        "required_missing_evidence": len(required) - len(considered_or_better),
        "required_missing_skill_names": [row["name"] for row in required if STATUS_RANK.get(row["status"], 0) < STATUS_RANK["considered"]],
        "required_accepted": len(accepted),
        "required_unaccepted": len(unaccepted),
        "required_unaccepted_skill_names": [row["name"] for row in unaccepted],
    }


def _short(text: str, limit: int = 260) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Codex session logs against the full KH skill catalog.")
    parser.add_argument("sessions", nargs="+", help="Codex session JSONL paths")
    parser.add_argument("--summary", action="store_true", help="Print compact summary instead of full skill rows")
    args = parser.parse_args()
    report = summarize_session_skill_audits(args.sessions)
    if args.summary:
        summary = {
            "session_count": report["session_count"],
            "aggregate": report["aggregate"],
            "sessions": [
                {
                    "session_id": audit["session_id"],
                    "coverage": audit["coverage"],
                    "usage_summary": audit.get("usage_summary", {}),
                    "postmortem": audit["postmortem"],
                    "issues": audit["issues"][:12],
                }
                for audit in report["audits"]
            ],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
