from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set

from src.orchestration.goal_ledger import GoalLedger
from src.orchestration.plugin_composition import looks_like_sql_output_request
from src.orchestration.request_classifier import classify_request
from src.orchestration.session_postmortem import analyze_codex_session_jsonl
from src.skills.uaf_skill_catalog import collect_packaged_skills


STATUS_RANK = {
    "absent": 0,
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
        return asdict(self)


def analyze_session_skills(session_path: str | Path) -> SessionSkillAudit:
    path = Path(session_path)
    postmortem = analyze_codex_session_jsonl(path)
    postmortem_data = postmortem.to_dict()
    front_door_token_receipts = _apply_front_door_token_optimizer_evidence(path, postmortem_data)
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
    texts = [record.text for record in text_records]
    active_texts = [_strip_passive_prefix(text) for text in texts if not _is_passive_text(text)]
    sql_scope_texts = [
        _strip_passive_prefix(record.text)
        for record in text_records
        if _is_sql_requirement_record(record)
    ]
    combined_text = "\n".join(active_texts)
    catalog = collect_packaged_skills()
    skills = catalog.get("skills", [])
    required = _required_skills(
        postmortem_data,
        combined_text,
        active_texts,
        sql_scope_texts=sql_scope_texts,
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
    skill_rows = []
    issues = []

    for skill in skills:
        name = str(skill.get("name", ""))
        aliases = _skill_aliases(skill)
        observations = _observations(text_records, aliases, name)
        status = observations["status"]
        is_required = name in required
        if name == "sql-formatting-style-harness" and sql_formatting_audit["required"]:
            if sql_formatting_audit["verifier_executed"]:
                status = "applied"
                observations["runtime_hits"] = max(1, int(observations["runtime_hits"]))
            elif status == "applied":
                status = "considered" if sql_formatting_audit["provider_selected"] else "mentioned"
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
        if name == "sql-formatting-style-harness":
            acceptance = _sql_style_harness_acceptance(
                sql_formatting_audit,
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
    issues.extend(_aggregate_skill_runtime_evidence_issues(path))
    issues.extend(_user_instruction_supersession_issues(path))
    issues.extend(_authoritative_reference_order_issues(path))
    issues.extend(_forbidden_residual_completion_issues(path))
    issues.extend(_kh_front_door_issues(path))
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
    issues.extend(_brainstorming_depth_issues(path))
    issues.extend(_subagent_strategy_issues(path, postmortem_data))
    issues.extend(_orchestration_decision_issues(path, postmortem_data))
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
            "completion_guard": postmortem.completion_guard,
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
    if completion_guard.get("status") == "blocked":
        issues.append(
            {
                "skill": "goal-state-harness",
                "status": "blocked",
                "severity": "P1",
                "reason": "task_complete was emitted while the user goal was still active",
                "action": "Keep the goal active, report partial progress, and carry next_task/missing evidence forward.",
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
    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("type", "")) != "thread_goal_updated":
            continue
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
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
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
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "session_meta" and isinstance(event.get("payload"), dict):
            return dict(event["payload"])
    return {}


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


def _kh_front_door_issues(path: Path) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    events = _session_payload_events(path)
    correlated_receipts = _correlated_front_door_receipts(events)
    waiting_for_front_door = False
    front_door_seen = False
    trigger_sample = ""
    trigger_kind = ""
    kh_active_directive_seen = False
    kh_active_directive_sample = ""
    task_unfinished = False
    active_goal = False

    for event_index, event in enumerate(events):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        text = _payload_text(payload)
        lowered = text.lower()

        if payload_type == "thread_goal_updated":
            goal = payload.get("goal", {}) or {}
            if isinstance(goal, dict):
                status = str(goal.get("status", "") or "").strip().lower()
                if status == "active":
                    active_goal = True
                elif status in {"complete", "blocked"}:
                    active_goal = False

        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            if _is_synthetic_context_message(text):
                continue
            if front_door_seen and task_unfinished and (
                _is_bounded_same_task_continuation(text)
                or (active_goal and bool(_extract_correction_claims(text)["invalidated"]))
            ):
                continue
            active_directive = _is_kh_active_directive(text)
            if active_directive:
                kh_active_directive_seen = True
                kh_active_directive_sample = _short(text)
            direct_code_question = _looks_like_direct_code_question(lowered)
            waiting_for_front_door = True
            front_door_seen = False
            task_unfinished = True
            trigger_sample = _short(text)
            if _is_kh_front_door_request(lowered):
                trigger_kind = "explicit_kh"
            elif looks_like_sql_output_request(lowered):
                trigger_kind = "sql_formatting_request"
            elif direct_code_question:
                trigger_kind = "direct_code_question"
            elif active_directive or (kh_active_directive_seen and _is_kh_active_followup_request(text)):
                trigger_kind = "kh_active_directive"
            elif _is_automatic_intake_request(text):
                trigger_kind = "automatic_intake"
            else:
                trigger_kind = "universal_request"
            continue

        if not waiting_for_front_door:
            if payload_type == "task_complete":
                front_door_seen = False
                task_unfinished = False
                active_goal = False
            continue

        if event_index in correlated_receipts:
            front_door_seen = True
            continue

        if _is_non_kh_work_start(payload, lowered) and not front_door_seen:
            issues.append(
                {
                    "skill": "always-on-front-door",
                    "status": "missing_front_door",
                    "severity": "P1",
                    "reason": (
                        "A KH-capable session started another skill, work command, or final answer before "
                        "always-on front-door runtime intake for the current user request."
                    ),
                    "action": (
                        "For every new user request or task, the first standalone skill/runtime call must run "
                        "KH front-door via `always_on_front_door/scripts/front_door.py` or "
                        "`python -m src.orchestration.kh_front_door ... --summary`, or record a blocked runtime result. "
                        "Reading SKILL.md, listing the catalog, mentioning always-on-front-door, or running target-folder checks in the "
                        "same pre-intake batch does not satisfy the entry contract. Users should not need to name KH, skills, or harnesses. "
                        "If an earlier user message requested active KH skill/harness use, carry that kh_active_directive into later work-bearing turns."
                    ),
                    "trigger_kind": trigger_kind,
                    "trigger": trigger_sample,
                    "kh_active_directive": kh_active_directive_sample if trigger_kind == "kh_active_directive" else "",
                    "first_work": _short(text),
                }
            )
            waiting_for_front_door = False
        if payload_type == "task_complete":
            waiting_for_front_door = False
            front_door_seen = False
            task_unfinished = False
            active_goal = False
    return issues


def _immediate_next_skill_issues(path: Path, skill_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    events = _session_payload_events(path)
    known_skills = {str(row.get("name", "")) for row in skill_rows}

    for index, event in enumerate(events):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        data = _front_door_json(_strip_passive_prefix(_payload_text(payload)))
        if not data:
            continue
        immediate = _ordered_unique(str(item) for item in data.get("immediate_next_skills", []) or [])
        immediate = [skill for skill in immediate if skill in known_skills]
        if not immediate:
            continue
        issues.extend(
            _immediate_skill_sequence_issues(
                events=events,
                start_index=index + 1,
                immediate=immediate,
                front_door_sample=_short(_payload_text(payload)),
            )
        )
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
    events: List[Dict[str, Any]],
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
    pending_runtime_calls: Dict[str, Set[str]] = {}

    for event in events[start_index:]:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
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
        call_id = _payload_call_id(payload)
        correlated_runtime_skills: Set[str] = set()
        if payload_type in {"function_call", "custom_tool_call"} and call_id:
            pending_runtime_calls[call_id] = {
                skill_name
                for skill_name in immediate
                if _is_immediate_skill_runtime_call(payload, skill_name)
            }
        elif payload_type in {"function_call_output", "custom_tool_call_output"} and call_id:
            correlated_runtime_skills = pending_runtime_calls.pop(call_id, set())
            if not _runtime_tool_output_succeeded(payload):
                correlated_runtime_skills = set()
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

    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
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
    skill_read_event: Dict[str, Any] | None = None
    skill_read_at: datetime | None = None
    front_door_event: Dict[str, Any] | None = None
    front_door_at: datetime | None = None

    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        text = _payload_text(payload)
        lowered = text.lower()
        ts = _event_timestamp(event)
        if ts is None:
            continue

        if (
            skill_read_at is None
            and payload_type in {"function_call", "custom_tool_call"}
            and "always_on_front_door" in lowered
            and "skill.md" in lowered
        ):
            skill_read_at = ts
            skill_read_event = event
            continue

        if _is_front_door_runtime_command(payload, lowered):
            front_door_at = ts
            front_door_event = event
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
            "skill_read": _short(_payload_text(skill_read_event.get("payload", {})) if skill_read_event else ""),
            "front_door_call": _short(_payload_text(front_door_event.get("payload", {})) if front_door_event else ""),
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
    pending_output: Dict[str, Any] | None = None
    pending_at: datetime | None = None
    pending_lines = 0

    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        ts = _event_timestamp(event)
        if ts is None:
            continue
        text = _payload_text(payload)

        if payload_type in {"function_call_output", "custom_tool_call_output"}:
            line_count = _reported_output_line_count(text)
            if line_count >= output_line_threshold:
                pending_output = event
                pending_at = ts
                pending_lines = line_count
            continue

        if pending_output is None or pending_at is None:
            continue
        if payload_type not in {"message", "agent_message", "function_call", "custom_tool_call", "task_complete"}:
            continue
        elapsed = (ts - pending_at).total_seconds()
        if elapsed <= delay_threshold_seconds:
            pending_output = None
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
                "sample": _short(_payload_text(pending_output.get("payload", {})), 260),
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
    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
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

    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        text = _payload_text(payload)

        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            targets = _extract_windows_paths(text)
            active_target = Path(targets[0]) if targets else None
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

    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        text = _payload_text(payload)

        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            targets = _extract_windows_paths(text)
            if targets:
                active_target = Path(targets[0])
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
    front_door_brainstorm_gate = _front_door_selected_skill(path, "brainstorming-harness") or _front_door_blocks_execution(path)
    new_project_context = _session_has_new_project_discovery_request(path)
    explicit_import_active = False
    read_samples: List[str] = []
    citation_samples: List[str] = []
    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        if payload_type == "message" and str(payload.get("role", "")).lower() in {"developer", "system"}:
            continue
        if _is_synthetic_context_message(_payload_text(payload)):
            continue
        if _payload_is_explicit_global_memory_import_request(payload) or _payload_has_scoped_memory_import_approval(payload):
            explicit_import_active = True
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
    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("type", "")) != "message":
            continue
        if str(payload.get("role", "")).lower() != "user":
            continue
        text = _payload_text(payload)
        lowered = text.lower()
        if _early_domain_discovery_text(lowered):
            return True
        if _extract_windows_paths(text) and any(
            marker in lowered
            for marker in [
                "pdf",
                "docx",
                "xlsx",
                "html",
                "css",
                "javascript",
                "index.html",
                "styles.css",
                "app.js",
                "website",
                "webpage",
                "homepage",
                "dashboard",
            ]
        ):
            return True
    return False


def _brainstorming_depth_issues(path: Path) -> List[Dict[str, Any]]:
    evidence_texts: List[str] = []
    for text in _session_texts(path):
        if _is_passive_text(text):
            continue
        clean_text = _strip_passive_prefix(text)
        if _looks_like_front_door_runtime_output(clean_text.lower()):
            continue
        evidence_texts.append(clean_text)
    active_text = "\n".join(evidence_texts)
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
                "severity": "P1",
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


def _host_local_sql_formatting_audit(path: Path) -> Dict[str, Any]:
    records = _session_text_records(path)
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
        "verified_before_output": False,
        "verification_id": "",
        "binding_errors": [],
        "action_kind": "",
        "issues": [],
    }

    request_index = next(
        (
            index
            for index, record in enumerate(records)
            if record.role == "user"
            and not _is_passive_text(record.text)
            and looks_like_sql_output_request(record.text.lower())
        ),
        -1,
    )
    if request_index < 0:
        return result

    action_index = -1
    action_kind = ""
    for index, record in enumerate(records[request_index + 1 :], request_index + 1):
        lowered = record.text.lower()
        if (
            record.role == "assistant"
            or record.payload_type in {"agent_message", "task_complete"}
        ) and _looks_like_sql_answer(lowered):
            action_index = index
            action_kind = "sql_output"
            break
        if _looks_like_sql_db_write(record):
            action_index = index
            action_kind = "db_write"
            break
    if action_index < 0:
        return result

    result["required"] = True
    result["action_kind"] = action_kind
    before_action = range(request_index + 1, action_index)
    selected_indices = [
        index
        for index in before_action
        if records[index].payload_type in {"function_call_output", "custom_tool_call_output"}
        and _has_sql_formatting_route_evidence(records[index].text.lower())
    ]
    inspected_indices = []
    for index in before_action:
        if not _looks_like_sql_formatting_provider_inspection(records[index]):
            continue
        output_index = _correlated_successful_provider_read_output(records, index, action_index)
        if output_index >= 0:
            inspected_indices.append(output_index)
    verifier_calls = [
        index
        for index in before_action
        if _invokes_sql_formatting_verifier(records[index])
    ]
    verifier_outputs = [
        index
        for index in before_action
        if _is_sql_verifier_output_candidate(records[index])
    ]

    result["provider_selected"] = bool(selected_indices)
    result["provider_inspected"] = bool(inspected_indices)
    result["verifier_executed"] = bool(verifier_calls)
    states: List[str] = []
    if result["provider_selected"]:
        states.append("provider_selected")
    if result["provider_inspected"]:
        states.append("provider_inspected")
    if result["verifier_executed"]:
        states.append("verifier_executed")

    final_sql = _extract_actionable_sql(records[action_index], action_kind)
    binding_errors: List[str] = []
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
    verified = bool(result["provider_inspected"] and result["verifier_executed"] and verifier_bound)
    if verified:
        result["formatter_application_proven"] = True
        result["verified_before_output"] = True
        result["verification_id"] = str(latest_evaluation.get("verification_id", ""))
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
                    "bound verifier evidence proving the formatted SQL. Provider selection alone is not application."
                ),
                "action": (
                    "Inspect the host-local sql-formatting contract, apply it, then execute "
                    "`verify_sql_formatting_style` and bind its successful evidence to the final SQL."
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
                "action": "Require provider inspection plus successful, bound SQL verifier execution before actionable output.",
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
    ]
    return "sql" in lowered and any(marker in lowered for marker in preservation_terms)


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
    request = records[request_index]
    if request.role == "user" and _has_exact_actionable_sql_source(request.text, original_sql):
        return True

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


def _is_sql_requirement_record(record: SessionTextRecord) -> bool:
    if _is_passive_text(record.text):
        return False
    lowered = record.text.lower()
    if _is_synthetic_context_message(record.text):
        return False
    if _looks_like_front_door_runtime_output(lowered):
        return False
    if record.payload_type == "message":
        if record.role in {"developer", "system"}:
            return False
        if record.role == "user":
            return looks_like_sql_output_request(lowered)
        if record.role == "assistant":
            return _looks_like_sql_answer(lowered)
        return False
    if record.payload_type in {"agent_message", "task_complete"}:
        return _looks_like_sql_answer(lowered)
    return False


def _brainstorming_target_inspection_issues(path: Path) -> List[Dict[str, Any]]:
    events = list(_session_payload_events(path))
    active_target: Path | None = None
    gate_active = False
    samples: List[str] = []

    for event in events:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
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
    events = list(_session_payload_events(path))
    choice_index = -1
    choice_text = ""
    for index, event in enumerate(events):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("type", "")) != "message":
            continue
        if str(payload.get("role", "")).lower() != "user":
            continue
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
    for event in events[choice_index + 1 :]:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
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
    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
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
    return (
        stripped.startswith("<environment_context>")
        or stripped.startswith("<goal_context>")
        or stripped.startswith("<recommended_plugins>")
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
        re.compile(rf"\bnot\s+({_CLAIM_TOKEN})", re.IGNORECASE),
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


def _correlated_tool_receipts(
    events: Sequence[Dict[str, Any]],
) -> List[CorrelatedToolReceipt]:
    pending: Dict[str, tuple[int, Dict[str, Any]]] = {}
    receipts: List[CorrelatedToolReceipt] = []
    for index, event in enumerate(events):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        call_id = _payload_call_id(payload)
        if payload_type in {"function_call", "custom_tool_call"}:
            if call_id:
                pending[call_id] = (index, payload)
            continue
        if payload_type not in {"function_call_output", "custom_tool_call_output"} or not call_id:
            continue
        call_record = pending.pop(call_id, None)
        if call_record is None or not _runtime_tool_output_succeeded(payload):
            continue
        call_index, call = call_record
        receipts.append(
            CorrelatedToolReceipt(
                call_index=call_index,
                output_index=index,
                call=call,
                output=payload,
                data=_json_object_from_text(_payload_text(payload)),
            )
        )
    return receipts


def _is_implementation_call(payload: Dict[str, Any]) -> bool:
    if str(payload.get("type", "")) not in {"function_call", "custom_tool_call"}:
        return False
    name = str(payload.get("name", "") or "").lower()
    lowered = _payload_text(payload).lower()
    if any(marker in name for marker in ["apply_patch", "write_file", "edit_file"]):
        return True
    if name != "shell_command" and "shell_command" not in name:
        return False
    return any(
        marker in lowered
        for marker in [
            "apply_patch",
            "set-content",
            "out-file",
            "new-item",
            "copy-item",
            "move-item",
        ]
    )


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
    receipts = _correlated_tool_receipts(events)
    corrections: List[Dict[str, Any]] = []
    active_goal = False
    completion_indexes: List[int] = []
    for index, event in enumerate(events):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        if payload_type == "thread_goal_updated":
            goal = payload.get("goal", {}) or {}
            status = str(goal.get("status", "") or "").strip().lower() if isinstance(goal, dict) else ""
            if status == "active":
                active_goal = True
            elif status in {"complete", "blocked"}:
                active_goal = False
        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            claims = _extract_correction_claims(_payload_text(payload))
            if claims["invalidated"]:
                corrections.append(
                    {
                        "index": index,
                        "active_goal": active_goal,
                        "invalidated": claims["invalidated"],
                        "replacements": claims["replacements"],
                        "sample": _short(_payload_text(payload)),
                    }
                )
        if payload_type == "task_complete":
            completion_indexes.append(index)

    issues: List[Dict[str, Any]] = []
    for correction in corrections:
        correction_index = int(correction["index"])
        invalidated = list(correction["invalidated"])
        completion_index = next(
            (index for index in completion_indexes if index > correction_index),
            len(events),
        )
        repeated: List[str] = []
        repeated_sample = ""
        for event in events[correction_index + 1 : completion_index + 1]:
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                continue
            payload_type = str(payload.get("type", ""))
            role = str(payload.get("role", "")).lower()
            if not (
                (payload_type == "message" and role == "assistant")
                or payload_type in {"agent_message", "task_complete"}
            ):
                continue
            repeated = _reasserted_invalidated_claims(_payload_text(payload), invalidated)
            if repeated:
                repeated_sample = _short(_payload_text(payload))
                break
        if repeated:
            issues.append(
                {
                    "skill": "context-state-harness",
                    "status": "invalidated_user_correction_repeated",
                    "severity": "P0" if completion_index < len(events) else "P1",
                    "reason": "The assistant reasserted a claim after the user explicitly invalidated it.",
                    "action": "Treat the latest user correction as authoritative and remove the invalidated assumption before completion.",
                    "invalidated_claims": repeated,
                    "correction": correction["sample"],
                    "repetition": repeated_sample,
                }
            )
        if not correction["active_goal"] or completion_index >= len(events):
            continue
        implementation = _correction_implementation_receipt(
            receipts,
            correction_index,
            completion_index,
            invalidated,
            list(correction["replacements"]),
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
                    "correction": correction["sample"],
                }
            )
    return issues


def _aggregate_skill_runtime_evidence_issues(path: Path) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("type", "")) not in {"function_call_output", "custom_tool_call_output"}:
            continue
        data = _front_door_json(_payload_text(payload))
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
    receipts = _correlated_tool_receipts(events)
    issues: List[Dict[str, Any]] = []
    for user_index, event in enumerate(events):
        payload = event.get("payload", {})
        if not isinstance(payload, dict) or not (
            str(payload.get("type", "")) == "message"
            and str(payload.get("role", "")).lower() == "user"
        ):
            continue
        for reference in _authoritative_references(_payload_text(payload)):
            task_boundary = next(
                (
                    index
                    for index, candidate in enumerate(events[user_index + 1 :], start=user_index + 1)
                    if isinstance(candidate.get("payload"), dict)
                    and str(candidate["payload"].get("type", "")) == "task_complete"
                ),
                len(events),
            )
            read_output_index = min(
                (
                    receipt.output_index
                    for receipt in receipts
                    if receipt.call_index > user_index
                    and receipt.output_index < task_boundary
                    and _is_reference_read_call(receipt.call, reference)
                ),
                default=task_boundary,
            )
            premature = next(
                (
                    (index, candidate.get("payload", {}))
                    for index, candidate in enumerate(events[user_index + 1 : read_output_index], start=user_index + 1)
                    if isinstance(candidate.get("payload"), dict)
                    and _introduces_constants_or_behavior(candidate["payload"])
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
    receipts = _correlated_tool_receipts(events)
    forbidden: Dict[str, int] = {}
    issues: List[Dict[str, Any]] = []
    for index, event in enumerate(events):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            claims = _extract_correction_claims(_payload_text(payload))
            for claim in claims["invalidated"]:
                forbidden[claim] = index
        if payload_type != "task_complete" or not forbidden:
            continue
        latest_implementation = max(
            (
                receipt.output_index
                for receipt in receipts
                if receipt.output_index < index and _is_implementation_call(receipt.call)
            ),
            default=-1,
        )
        matched: List[str] = []
        scanned: Set[str] = set()
        scan_sample = ""
        for receipt in receipts:
            eligible = [
                claim
                for claim, request_index in forbidden.items()
                if max(request_index, latest_implementation) < receipt.call_index < receipt.output_index < index
            ]
            if not eligible or not _is_residual_scan_call(receipt.call, eligible):
                continue
            scanned_by_call = [
                claim
                for claim in eligible
                if _claim_in_text(claim, _payload_text(receipt.call))
            ]
            found = _residual_matches(_payload_text(receipt.output), scanned_by_call)
            if found is None:
                continue
            scanned.update(scanned_by_call)
            if found:
                matched.extend(claim for claim in found if claim not in matched)
                scan_sample = _short(_payload_text(receipt.output))
        if matched:
            issues.append(
                {
                    "skill": "verification-before-completion-harness",
                    "status": "forbidden_residuals_at_completion",
                    "severity": "P0",
                    "reason": "task_complete followed a fresh residual scan whose correlated output still contained user-forbidden patterns.",
                    "action": "Remove every reported residual and run a new clean scan before completion.",
                    "forbidden_patterns": matched,
                    "scan_output": scan_sample,
                }
            )
        missing_scans = [claim for claim in forbidden if claim not in scanned]
        if missing_scans:
            issues.append(
                {
                    "skill": "verification-before-completion-harness",
                    "status": "missing_fresh_residual_scan_at_completion",
                    "severity": "P0",
                    "reason": (
                        "task_complete was emitted with an active correction or forbidden-pattern "
                        "obligation but no correlated residual scan receipt after the latest implementation."
                    ),
                    "action": "Run a fresh residual scan for every forbidden pattern and correlate its output before completion.",
                    "forbidden_patterns": missing_scans,
                }
            )
        forbidden.clear()
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
    receipts = _correlated_tool_receipts(events)
    requirement_indexes: List[int] = []
    requirement_sources: List[str] = []
    for index, event in enumerate(events):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if (
            str(payload.get("type", "")) == "message"
            and str(payload.get("role", "")).lower() == "user"
            and _explicit_user_delegation(_payload_text(payload))
        ):
            requirement_indexes.append(index)
            requirement_sources.append("explicit_user_delegation")
    for output_index, receipt in _correlated_front_door_receipts(events).items():
        classification = receipt.data.get("classification", {}) or {}
        if isinstance(classification, dict) and str(classification.get("recommended_execution", "")) == "role_dag":
            requirement_indexes.append(output_index)
            requirement_sources.append("mandatory_role_dag")
    if not requirement_indexes:
        return []
    requirement_index = min(requirement_indexes)
    terminal_index = min(
        (
            index
            for index, event in enumerate(events)
            if isinstance(event.get("payload"), dict)
            and str(event["payload"].get("type", "")) == "task_complete"
            and index > requirement_index
        ),
        default=-1,
    )
    implementation_index = min(
        (
            index
            for index, event in enumerate(events)
            if index > requirement_index
            and isinstance(event.get("payload"), dict)
            and _is_implementation_call(event["payload"])
        ),
        default=-1,
    )
    decision_index = terminal_index if terminal_index >= 0 else implementation_index
    if decision_index < 0:
        return []
    relevant_receipts = [
        receipt
        for receipt in receipts
        if requirement_index < receipt.call_index < receipt.output_index < decision_index
    ]
    dispatches = [receipt for receipt in relevant_receipts if _is_dispatch_receipt(receipt)]
    fan_ins = [
        receipt
        for receipt in relevant_receipts
        if _is_fan_in_receipt(receipt)
        and any(dispatch.output_index < receipt.call_index for dispatch in dispatches)
    ]
    user_waiver = any(
        requirement_index < index < decision_index
        and isinstance(event.get("payload"), dict)
        and str(event["payload"].get("type", "")) == "message"
        and str(event["payload"].get("role", "")).lower() == "user"
        and _user_approved_delegation_waiver(_payload_text(event["payload"]))
        for index, event in enumerate(events)
    )
    availability_receipts = [
        receipt for receipt in relevant_receipts if _is_nested_capability_receipt(receipt)
    ]
    availability_values = [
        _nested_agents_availability_in_data(receipt.data)
        for receipt in availability_receipts
    ]
    nested_available: bool | None
    if dispatches or any(value is True for value in availability_values):
        nested_available = True
    elif availability_values:
        nested_available = False
    else:
        nested_available = None
    if (dispatches and fan_ins) or user_waiver:
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
            "requirement_sources": sorted(set(requirement_sources)),
            "nested_agents_available": nested_available,
            "availability_receipt": bool(availability_receipts),
            "dispatch_receipts": len(dispatches),
            "fan_in_receipts": len(fan_ins),
            "user_approved_waiver": user_waiver,
        }
    ]


def _front_door_selected_skill(path: Path, skill_name: str) -> bool:
    for text in _session_texts(path):
        data = _front_door_json(_strip_passive_prefix(text))
        if not data:
            continue
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
    for text in _session_texts(path):
        data = _front_door_json(_strip_passive_prefix(text))
        if not data:
            continue
        gate = data.get("execution_gate", {}) or {}
        if isinstance(gate, dict) and gate.get("can_execute") is False:
            return True
    return False


def _subagent_strategy_issues(path: Path, postmortem: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not _is_subagent_session(path):
        return []
    evidence_texts = []
    for text in _session_texts(path):
        if _is_passive_text(text):
            continue
        clean_text = _strip_passive_prefix(text)
        if _looks_like_front_door_runtime_output(clean_text.lower()):
            continue
        evidence_texts.append(clean_text)
    active_text = "\n".join(evidence_texts)
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


def _orchestration_decision_issues(path: Path, postmortem: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence_texts = []
    for text in _session_texts(path):
        if _is_passive_text(text):
            continue
        clean_text = _strip_passive_prefix(text)
        if _looks_like_front_door_runtime_output(clean_text.lower()):
            continue
        evidence_texts.append(clean_text)
    active_text = "\n".join(evidence_texts)
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
    evidence = {"parallel_strategy": False, "role_execution_audit": False}
    for call_index, call in enumerate(records):
        if call.payload_type not in {"function_call", "custom_tool_call"} or _is_passive_text(call.text):
            continue
        lowered = call.text.lower()
        if "validate_large_work_orchestration_bundle" in lowered:
            output = _correlated_structured_tool_output(records, call_index)
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
        if any(
            marker in lowered
            for marker in ["audit_role_execution", "dispatch_project_workflow", "async_project_workflow"]
        ):
            output = _correlated_structured_tool_output(records, call_index)
            audit = _find_nested_mapping(output, "role_execution_audit") or output
            if _valid_role_execution_audit_artifact(audit):
                evidence["role_execution_audit"] = True
                if _role_audit_proves_parallel_execution(audit):
                    evidence["parallel_strategy"] = True
    return evidence


def _correlated_structured_tool_output(
    records: List[SessionTextRecord], call_index: int
) -> Dict[str, Any]:
    call = records[call_index]
    for record in records[call_index + 1 :]:
        if record.payload_type in {"function_call", "custom_tool_call"}:
            break
        if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
            continue
        if call.call_id and record.call_id != call.call_id:
            continue
        return _json_object_from_text(record.text)
    return {}


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
    count = 0
    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if payload.get("type") in {"function_call", "custom_tool_call"} and str(payload.get("name", "")) in names:
            count += 1
    return count


def _implementation_tool_samples(path: Path) -> List[str]:
    samples: List[str] = []
    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
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
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "session_meta":
            continue
        payload = event.get("payload", {}) or {}
        if not isinstance(payload, dict):
            continue
        if str(payload.get("thread_source", "")).lower() == "subagent":
            return True
        source = payload.get("source", {}) or {}
        return isinstance(source, dict) and isinstance(source.get("subagent"), dict)
    return False


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
    target = _normalize_path(target)
    parent = _normalize_path(target.parent)
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
    normalized_target = str(_normalize_path(target)).lower()
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
    return any(
        _payload_is_explicit_global_memory_import_request(event.get("payload", {}))
        for event in _session_payload_events(path)
        if isinstance(event.get("payload"), dict)
    )


def _payload_has_scoped_memory_import_approval(payload: Dict[str, Any]) -> bool:
    return _text_has_scoped_memory_import_approval(_payload_text(payload))


def _session_has_scoped_memory_import_evidence(path: Path) -> bool:
    for record in _session_text_records(path):
        if _is_passive_text(record.text):
            continue
        if _text_has_scoped_memory_import_approval(record.text):
            return True
    return False


def _text_has_scoped_memory_import_approval(text: str) -> bool:
    lowered = text.lower()
    truthy_patterns = [
        r"\bmemory_import_approved\b\s*[:=]\s*(?:true|yes|approved|1)\b",
        r'"memory_import_approved"\s*:\s*true\b',
        r"'memory_import_approved'\s*:\s*true\b",
        r"\bparent_memory_access_approved\b\s*[:=]\s*(?:true|yes|approved|1)\b",
        r'"parent_memory_access_approved"\s*:\s*true\b',
        r"'parent_memory_access_approved'\s*:\s*true\b",
    ]
    if any(re.search(pattern, lowered) for pattern in truthy_patterns):
        return True
    if "explicit_cross_scope_memory_import" in lowered and any(
        marker in lowered
        for marker in [
            "approval_state=approved",
            '"approval_state": "approved"',
            "'approval_state': 'approved'",
            "application_status=applied",
            '"application_status": "applied"',
            "'application_status': 'applied'",
        ]
    ):
        return True
    return False


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


def _session_payload_events(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") in {"response_item", "event_msg"} and isinstance(event.get("payload"), dict):
            events.append(event)
    return events


def _payload_call_id(payload: Dict[str, Any]) -> str:
    return str(payload.get("call_id", "") or payload.get("tool_call_id", "")).strip()


def _correlated_front_door_receipts(
    events: Sequence[Dict[str, Any]],
) -> Dict[int, CorrelatedFrontDoorReceipt]:
    pending_calls: Dict[str, tuple[int, Dict[str, Any]]] = {}
    receipts: Dict[int, CorrelatedFrontDoorReceipt] = {}
    latest_request_boundary = -1
    for index, event in enumerate(events):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        call_id = _payload_call_id(payload)
        text = _payload_text(payload)
        lowered = text.lower()
        if (
            payload_type == "message"
            and str(payload.get("role", "")).lower() == "user"
            and not _is_synthetic_context_message(text)
            and not _is_bounded_same_task_continuation(text)
        ) or payload_type == "task_complete":
            latest_request_boundary = index
        if payload_type in {"function_call", "custom_tool_call"}:
            if call_id and _is_front_door_runtime_command(payload, lowered):
                pending_calls[call_id] = (index, payload)
            continue
        if payload_type not in {"function_call_output", "custom_tool_call_output"} or not call_id:
            continue
        pending = pending_calls.pop(call_id, None)
        if pending is None or not _front_door_output_succeeded(payload):
            continue
        call_index, _call = pending
        if call_index <= latest_request_boundary:
            continue
        data = _front_door_json(_payload_text(payload))
        if _has_normalized_front_door_receipt(data):
            receipts[index] = CorrelatedFrontDoorReceipt(
                call_index=call_index,
                output_index=index,
                data=data,
            )
    return receipts


def _front_door_output_succeeded(payload: Dict[str, Any]) -> bool:
    recorded_exit_codes: List[int] = []
    for key in ["exit_code", "return_code"]:
        if key in payload:
            try:
                recorded_exit_codes.append(int(payload[key]))
            except (TypeError, ValueError):
                return False
    text = _payload_text(payload)
    recorded_exit_codes.extend(
        int(code)
        for code in re.findall(r"(?im)\bexit\s+code\s*:\s*(-?\d+)\b", text)
    )
    if any(code not in {0, 1, 3} for code in recorded_exit_codes):
        return False
    if 1 in recorded_exit_codes:
        if any(code != 1 for code in recorded_exit_codes):
            return False
        return _is_strict_blocked_front_door_packet(_front_door_json(text))
    if 3 in recorded_exit_codes:
        if any(code != 3 for code in recorded_exit_codes):
            return False
        return _is_strict_blocked_front_door_packet(_front_door_json(text))

    status = str(payload.get("status", "") or "").strip().lower()
    if status in {"error", "failed", "failure"} or payload.get("success") is False:
        return False
    return not recorded_exit_codes or all(code == 0 for code in recorded_exit_codes)


def _is_strict_blocked_front_door_packet(data: Dict[str, Any]) -> bool:
    if not (
        _is_valid_compact_front_door_packet(data)
        or _is_valid_normalized_micro_front_door_packet(data)
    ):
        return False
    if str(data.get("front_door_status", "")).strip().lower() != "ok":
        return False

    route = data.get("plugin_route", {}) or {}
    gate = data.get("execution_gate", {}) or {}
    authorization = data.get("execution_authorization", {}) or {}
    action_codes = data.get("required_next_action_codes")
    gate_status = str(gate.get("status", "")).strip()
    authorization_status = str(authorization.get("status", "")).strip().lower()
    current_gate_contract = bool(
        gate.get("can_execute") is False and gate_status.startswith("blocked_")
    )
    legacy_gate_contract = bool(
        gate.get("can_execute") is True
        and gate_status == "execution_allowed_after_selected_skill_setup"
    )
    return bool(
        route.get("route") in {"single", "hybrid", "clarify"}
        and (current_gate_contract or legacy_gate_contract)
        and authorization.get("must_stop_before_execution") is True
        and ("blocked" in authorization_status or "pending" in authorization_status)
        and isinstance(action_codes, list)
        and action_codes
        and all(isinstance(code, str) and code.strip() for code in action_codes)
        and "stop_before_task_work" in action_codes
        and "apply_immediate_next_skills" in action_codes
    )


def _latest_actual_runtime_token_optimizer_decision(
    events: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    pending_calls: Dict[str, Dict[str, Any]] = {}
    latest: Dict[str, Any] = {}
    for event in events:
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        call_id = _payload_call_id(payload)
        lowered = _payload_text(payload).lower()
        if payload_type == "thread_goal_updated":
            if not _has_explicit_token_optimizer_runtime_source(payload):
                continue
            decision = _actual_runtime_token_optimizer_decision(
                json.dumps(payload, ensure_ascii=False)
            )
            if decision:
                latest = decision
            continue
        if payload_type in {"function_call", "custom_tool_call"}:
            if call_id and _is_token_optimizer_runtime_command(lowered):
                pending_calls[call_id] = payload
            continue
        if payload_type not in {"function_call_output", "custom_tool_call_output"} or not call_id:
            continue
        if pending_calls.pop(call_id, None) is None:
            continue
        if not _runtime_tool_output_succeeded(payload):
            continue
        decision = _actual_runtime_token_optimizer_decision(_payload_text(payload))
        if decision:
            latest = decision
    return latest


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


def _full_summary_token_output_indexes(events: Sequence[Dict[str, Any]]) -> Set[int]:
    indexes: Set[int] = set()
    for index, event in enumerate(events):
        payload = event.get("payload", {})
        if not isinstance(payload, dict) or str(payload.get("type", "")) not in {
            "function_call_output",
            "custom_tool_call_output",
        }:
            continue
        data = _json_object_from_text(_payload_text(payload))
        if isinstance(data.get("token_optimizer_decision"), dict):
            indexes.add(index)
    return indexes


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
    full_summary_token_outputs = _full_summary_token_output_indexes(events)
    decisions: List[Dict[str, Any]] = []
    for receipt in correlated_receipts.values():
        data = receipt.data
        token_decision = data.get("token_optimizer", {}) or {}
        if isinstance(token_decision, dict) and str(token_decision.get("status", "")).strip():
            decisions.append(token_decision)

    latest_actual = _latest_actual_runtime_token_optimizer_decision(events)

    evidence = dict(postmortem.get("token_optimizer_evidence", {}) or {})
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
    full_summary_only_evidence = bool(full_summary_token_outputs) and not latest_actual
    if full_summary_only_evidence:
        existing_receipts = False
    token_gate = dict(postmortem.get("token_gate", {}) or {})
    token_gate["checked"] = bool(existing_receipts or decisions or latest_actual)

    if latest_actual:
        status = str(latest_actual.get("status", "")).strip()
        postmortem["token_optimizer_status"] = status
        postmortem["token_optimizer_status_reason"] = str(latest_actual.get("reason", "") or status)
        token_gate["decision_source"] = "runtime_token_optimizer"
        evidence["latest_actual_runtime_status"] = status
        evidence["latest_actual_runtime_decision"] = dict(latest_actual)
    elif (
        decisions
        and str(decisions[-1].get("status", "")) == "considered_not_needed"
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
    elif decisions:
        latest = decisions[-1]
        status = str(latest.get("status", "")).strip()
        postmortem["token_optimizer_status"] = status
        postmortem["token_optimizer_status_reason"] = str(
            latest.get("reason_code", "") or status
        )
        token_gate["decision_source"] = "kh_front_door_runtime_receipt"
        evidence["front_door_runtime_receipts"] = len(decisions)
        evidence["latest_front_door_decision"] = dict(latest)
    else:
        evidence.setdefault("front_door_runtime_receipts", 0)
        if not existing_receipts and (
            full_summary_only_evidence
            or postmortem.get("token_optimizer_status") == "considered_not_needed"
        ):
            postmortem["token_optimizer_status"] = "not_checked"
            postmortem["token_optimizer_status_reason"] = "no runtime token-optimizer receipt"

    evidence["front_door_runtime_receipts"] = len(decisions)
    if decisions:
        evidence["latest_front_door_decision"] = dict(decisions[-1])

    postmortem["token_gate"] = token_gate
    postmortem["token_optimizer_evidence"] = evidence
    return len(decisions)


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
    issues: List[Dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        _, _, structure = _partial_session_json_string_fields(line)
        duplicate_boundary_field = bool(structure.get("duplicate_boundary_field"))
        error = ""
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            if not duplicate_boundary_field and not _malformed_line_can_hide_task_boundary(line):
                continue
            error = str(exc)
        if not duplicate_boundary_field and not error:
            continue
        duplicate_reason = (
            "Duplicate boundary-bearing JSON keys make a session event ambiguous even when the JSON "
            "is syntactically valid."
        )
        malformed_reason = (
            "Malformed session JSONL can hide a user-request or task-complete boundary, "
            "so front-door acknowledgement reuse cannot be audited safely."
        )
        issues.append(
            {
                "skill": "always-on-front-door",
                "status": "session_jsonl_integrity_error",
                "severity": "P0",
                "reason": duplicate_reason if duplicate_boundary_field else malformed_reason,
                "action": (
                    "Repair or regenerate the ambiguous session event before accepting front-door "
                    "ordering or same-task acknowledgement reuse."
                ),
                "line_number": line_number,
                "error": error or "duplicate boundary-bearing JSON key",
                "sample": _short(line),
            }
        )
    return issues


def _malformed_line_can_hide_task_boundary(line: str) -> bool:
    event_fields, payload_fields, structure = _partial_session_json_string_fields(line)
    if structure.get("duplicate_boundary_field"):
        return True
    event_type, event_type_closed = event_fields.get("type", ("", False))
    event_type = event_type.lower()
    if not event_type:
        if not structure.get("payload_first") or not (
            structure.get("root_unclosed") or structure.get("root_closed_trailing_garbage")
        ):
            return False
        payload_type, payload_type_closed = payload_fields.get("type", ("", False))
        if not payload_type_closed:
            return False
        payload_type = payload_type.lower()
        if payload_type == "task_complete":
            return True
        if payload_type != "message":
            return False
        role, role_closed = payload_fields.get("role", ("", False))
        return bool(role_closed and role.lower() == "user")

    if event_type_closed:
        if event_type not in {"response_item", "event_msg"}:
            return False
    elif not any(
        len(event_type) >= 4 and expected.startswith(event_type)
        for expected in ["response_item", "event_msg"]
    ):
        return False

    payload_type, payload_type_closed = payload_fields.get("type", ("", False))
    payload_type = payload_type.lower()
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
    role = role.lower()
    if role_closed:
        return role == "user"
    return "user".startswith(role)


def _partial_session_json_string_fields(
    line: str,
) -> tuple[
    Dict[str, tuple[str, bool]],
    Dict[str, tuple[str, bool]],
    Dict[str, bool],
]:
    text = str(line or "")
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
    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "message" or str(payload.get("role", "")).lower() != "user":
            continue
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
        structured = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        structured = None
    if isinstance(structured, dict):
        command = structured.get("command")
        if isinstance(command, str) and command.strip():
            candidates.append(command)

    command_literal = re.compile(
        r'(?:[\"\']command[\"\']|\bcommand)\s*:\s*'
        r'(?P<literal>\"(?:\\.|[^\"\\])*\"|\'(?:\\.|[^\'\\])*\')'
    )
    for match in command_literal.finditer(raw):
        command = _decode_command_literal(match.group("literal"))
        if command:
            candidates.append(command)

    if tool_tail == "exec" and not candidates and re.match(
        r"\s*(?:python|python3|py)(?:\.exe)?\b", raw, re.IGNORECASE
    ):
        candidates.append(raw)
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
    for segment in _shell_command_segments(command):
        tokens = _shell_command_tokens(segment)
        if not tokens:
            continue
        executable = tokens[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
        if executable not in {"python", "python.exe", "python3", "python3.exe", "py", "py.exe"}:
            continue

        index = 1
        while index < len(tokens):
            token = tokens[index]
            lowered_token = token.lower()
            if lowered_token in {"-c", "-"}:
                break
            if lowered_token == "-m":
                return bool(
                    index + 1 < len(tokens)
                    and tokens[index + 1].lower() == "src.orchestration.kh_front_door"
                )
            if lowered_token == "--":
                index += 1
                if index >= len(tokens):
                    break
                token = tokens[index]
                lowered_token = token.lower()
            if lowered_token.startswith("-"):
                index += 2 if lowered_token in {"-w", "-x"} else 1
                continue
            return _is_trusted_front_door_script_path(token)
        continue
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


def _session_texts(path: Path) -> List[str]:
    return [record.text for record in _session_text_records(path)]


def _session_text_records(path: Path) -> List[SessionTextRecord]:
    texts: List[SessionTextRecord] = []
    previous_call_was_passive = False
    untrusted_assessment_active = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") == "message":
            role = str(payload.get("role", "")).lower()
            if role in {"developer", "system"}:
                previous_call_was_passive = False
                continue
        text = _payload_text(payload)
        if text:
            payload_type = str(payload.get("type", ""))
            role = str(payload.get("role", "")).lower()
            lowered = text.lower()
            is_untrusted_assessment = _is_untrusted_assessment_transcript(lowered)
            if payload_type == "message" and role == "user":
                if is_untrusted_assessment:
                    untrusted_assessment_active = True
                elif not _is_synthetic_context_message(text):
                    untrusted_assessment_active = False
            passive = untrusted_assessment_active or _is_synthetic_context_message(text) or _passive_reference(lowered) or (
                payload_type in {"function_call_output", "custom_tool_call_output"}
                and previous_call_was_passive
            )
            if passive:
                text = PASSIVE_REFERENCE_PREFIX + text
            texts.append(
                SessionTextRecord(
                    text=text,
                    payload_type=payload_type,
                    role=role,
                    call_id=str(payload.get("call_id", "") or payload.get("tool_call_id", "")),
                    name=str(payload.get("name", "")),
                )
            )
            previous_call_was_passive = payload_type in {"function_call", "custom_tool_call"} and passive
        else:
            previous_call_was_passive = False
    return texts


def _payload_text(payload: Dict[str, Any]) -> str:
    payload_type = payload.get("type")
    if payload_type == "message":
        return _content_text(payload.get("content"))
    if payload_type == "agent_message":
        return _content_text(payload.get("message") or payload.get("content"))
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


def _observations(texts: List[SessionTextRecord] | List[str], aliases: Set[str], skill_name: str) -> Dict[str, Any]:
    mentions = 0
    inspections = 0
    runtime_hits = 0
    passive_references = 0
    considered = 0
    evidence: List[str] = []
    active_evidence: List[str] = []
    runtime_markers = RUNTIME_MARKERS.get(skill_name, [])

    for item in texts:
        if isinstance(item, SessionTextRecord):
            text = item.text
            payload_type = item.payload_type
            role = item.role
        else:
            text = str(item)
            payload_type = ""
            role = ""
        passive = _is_passive_text(text)
        clean_text = _strip_passive_prefix(text)
        lowered = clean_text.lower()
        normalized_front_door = _front_door_json(clean_text)
        front_door_status = _front_door_skill_status(clean_text, skill_name)
        if (
            skill_name == "token-optimizer"
            and front_door_status
            and payload_type not in {"function_call_output", "custom_tool_call_output"}
        ):
            front_door_status = ""
        alias_hit = bool(front_door_status) or any(alias.lower() in lowered for alias in aliases)
        runtime_marker_hit = not front_door_status and any(marker.lower() in lowered for marker in runtime_markers)
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
    return normalized


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
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
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
        data = _front_door_json(_strip_passive_prefix(str(text)))
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

    active_text = "\n".join(observations.get("active_evidence", []))
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
        if completion_guard.get("status") == "blocked" or user_stop_guard.get("status") == "blocked":
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
    text = "\n".join(observations.get("active_evidence", [])).lower()
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


def _required_skills(
    postmortem: Dict[str, Any],
    text: str,
    active_texts: List[str] | None = None,
    sql_scope_texts: List[str] | None = None,
) -> Dict[str, str]:
    required: Dict[str, str] = {}
    lowered = text.lower()
    sql_lowered = "\n".join(sql_scope_texts if sql_scope_texts is not None else (active_texts or [text])).lower()
    token_gate = postmortem.get("token_gate", {}) or {}
    subagents = postmortem.get("subagent_summary", {}) or {}
    verification_commands = postmortem.get("verification_commands", []) or []
    sql_specialist_scope = _is_sql_specialist_answer_scope(postmortem, sql_lowered, sql_scope_texts)

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
    if looks_like_sql_output_request(sql_lowered):
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
    qa_scan_texts = active_texts or [text]
    if any(
        _mentions_browser_or_local_app_qa(chunk.lower())
        for chunk in qa_scan_texts
        if not _looks_like_front_door_runtime_output(chunk.lower())
    ):
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
        and not looks_like_sql_output_request(sql_lowered)
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
) -> bool:
    if not looks_like_sql_output_request(lowered):
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
    texts = active_texts or [lowered]
    non_front_door_tool_text = "\n".join(
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
