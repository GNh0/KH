from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

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
        "actual_tokens_saved",
        "actual_usage",
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
        "status_split": ["runtime_applied_skills", "selected_not_executed_skills", "skill_status_summary"],
    },
    "automatic-intake-harness": {
        "intake_evidence": ["kh_front_door", "front_door_status", "classification", "plugin_route"],
        "status_split": ["runtime_applied_skills", "selected_not_executed_skills", "skill_status_summary"],
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
            "actual_tokens_saved",
            "actual_usage",
            "estimated_tokens_saved",
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


@dataclass(frozen=True)
class SessionSkillAudit:
    session_id: str
    path: str
    total_skills: int
    coverage: Dict[str, Any]
    skills: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    postmortem: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def analyze_session_skills(session_path: str | Path) -> SessionSkillAudit:
    path = Path(session_path)
    postmortem = analyze_codex_session_jsonl(path)
    text_records = _session_text_records(path)
    texts = [record.text for record in text_records]
    active_texts = [_strip_passive_prefix(text) for text in texts if not _is_passive_text(text)]
    combined_text = "\n".join(active_texts)
    catalog = collect_packaged_skills()
    skills = catalog.get("skills", [])
    required = _required_skills(postmortem.to_dict(), combined_text, active_texts)
    skill_rows = []
    issues = []

    for skill in skills:
        name = str(skill.get("name", ""))
        aliases = _skill_aliases(skill)
        observations = _observations(text_records, aliases, name)
        status = observations["status"]
        is_required = name in required
        acceptance = _acceptance_for_skill(
            skill_name=name,
            required=is_required,
            status=status,
            observations=observations,
            postmortem=postmortem.to_dict(),
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
            row["token_optimizer_status"] = postmortem.token_optimizer_status
            row["token_optimizer_status_reason"] = postmortem.token_optimizer_status_reason
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

    issues.extend(_kh_front_door_issues(path))
    issues.extend(_immediate_next_skill_issues(path, skill_rows))
    issues.extend(_front_door_latency_issues(path))
    issues.extend(_large_output_latency_issues(path))
    issues.extend(_stale_skill_cache_issues(path))
    issues.extend(_cross_scope_context_issues(path))
    issues.extend(_global_memory_scope_issues(path))
    issues.extend(_target_substitution_issues(path))
    issues.extend(_host_local_sql_formatting_issues(path))
    issues.extend(_brainstorm_option_choice_execution_issues(path))
    issues.extend(_brainstorming_depth_issues(path))
    issues.extend(_subagent_strategy_issues(path, postmortem.to_dict()))
    issues.extend(_orchestration_decision_issues(path, postmortem.to_dict()))
    issues.extend(_postmortem_guard_issues(postmortem.to_dict()))
    issues.extend(_goal_state_completion_absence_issues(path, skill_rows, postmortem.to_dict()))
    coverage = _coverage(skill_rows)
    return SessionSkillAudit(
        session_id=postmortem.session_id,
        path=str(path),
        total_skills=len(skill_rows),
        coverage=coverage,
        skills=skill_rows,
        issues=issues,
        postmortem={
            "token_optimizer_status": postmortem.token_optimizer_status,
            "token_optimizer_status_reason": postmortem.token_optimizer_status_reason,
            "token_gate": postmortem.token_gate,
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
) -> List[Dict[str, Any]]:
    goal_row = next((row for row in skill_rows if row.get("name") == "goal-state-harness"), {})
    goal_required = bool(goal_row.get("required")) or _front_door_selected_skill(path, "goal-state-harness")
    if not goal_required:
        return []

    completion_guard = postmortem.get("completion_guard", {}) or {}
    task_complete_count = int(completion_guard.get("task_complete_count", 0) or 0)
    if task_complete_count <= 0:
        return []

    latest_status = str(completion_guard.get("latest_goal_status", "") or "")
    if latest_status == "active":
        return []
    if _has_terminal_goal_state_evidence(path, latest_status):
        return []

    return [
        {
            "skill": "goal-state-harness",
            "status": "missing_terminal_goal_state",
            "severity": "P0",
            "reason": (
                "goal-state-harness was required or selected, but task_complete was emitted without "
                "terminal GoalState evidence"
            ),
            "action": (
                "Before final task_complete, create or update GoalState and close it as complete/blocked; "
                "if the host cannot do that, report blocked instead of claiming completion."
            ),
        }
    ]


def _has_terminal_goal_state_evidence(path: Path, latest_status: str) -> bool:
    if latest_status in {"complete", "blocked"}:
        return True
    terminal_updates = 0
    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if str(payload.get("type", "")) != "thread_goal_updated":
            continue
        goal = payload.get("goal", {}) or {}
        status = str(goal.get("status", ""))
        if status in {"complete", "blocked"}:
            terminal_updates += 1
    return terminal_updates > 0


def _kh_front_door_issues(path: Path) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    waiting_for_front_door = False
    front_door_seen = False
    trigger_sample = ""
    trigger_kind = ""
    kh_active_directive_seen = False
    kh_active_directive_sample = ""

    for event in _session_payload_events(path):
        payload = event.get("payload", {})
        if not isinstance(payload, dict):
            continue
        payload_type = str(payload.get("type", ""))
        text = _payload_text(payload)
        lowered = text.lower()

        if payload_type == "message" and str(payload.get("role", "")).lower() == "user":
            active_directive = _is_kh_active_directive(text)
            if active_directive:
                kh_active_directive_seen = True
                kh_active_directive_sample = _short(text)
                if not _is_kh_active_followup_request(text):
                    continue

            if (
                _is_kh_front_door_request(lowered)
                or (_is_automatic_intake_request(text) and not _looks_like_external_specialist_direct_question(lowered))
                or (kh_active_directive_seen and _is_kh_active_followup_request(text))
            ):
                waiting_for_front_door = True
                front_door_seen = False
                trigger_sample = _short(text)
                if kh_active_directive_seen and not _is_kh_front_door_request(lowered):
                    trigger_kind = "kh_active_directive"
                else:
                    trigger_kind = "explicit_kh" if _is_kh_front_door_request(lowered) else "automatic_intake"
            continue

        if not waiting_for_front_door:
            continue

        if _is_front_door_order_evidence(payload, lowered):
            front_door_seen = True
            continue

        if _is_non_kh_work_start(payload, lowered) and not front_door_seen:
            issues.append(
                {
                    "skill": "always-on-front-door",
                    "status": "missing_front_door",
                    "severity": "P1",
                    "reason": (
                        "A KH-capable session started non-trivial source/work commands before "
                        "always-on front-door runtime intake."
                    ),
                    "action": (
                        "For non-trivial work, the first standalone work-bearing tool call must run "
                        "KH front-door via `always_on_front_door/scripts/front_door.py` or "
                        "`python -m src.orchestration.kh_front_door ... --summary`, or record an explicit blocked/direct rationale. "
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
            status = _immediate_skill_event_status(payload, lowered, skill_name, passive)
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


def _immediate_skill_event_status(
    payload: Dict[str, Any],
    lowered: str,
    skill_name: str,
    passive: bool,
) -> str:
    if passive:
        return ""
    payload_type = str(payload.get("type", ""))
    if skill_name == "goal-state-harness" and payload_type == "thread_goal_updated":
        return "applied"
    structured_payload = _is_immediate_structured_runtime_payload(payload_type, lowered)
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
        return "applied"
    return ""


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
    elif request_input_count <= 1 and has_options and not has_handoff:
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
    records = [
        record
        for record in _session_text_records(path)
        if not _is_passive_text(record.text)
    ]
    request_index = -1
    for index, record in enumerate(records):
        if record.role == "user" and looks_like_sql_output_request(record.text.lower()):
            request_index = index
            break
    if request_index < 0:
        return []

    first_sql_answer_index = -1
    first_sql_skill_index = -1
    for index, record in enumerate(records[request_index + 1 :], request_index + 1):
        lowered = record.text.lower()
        if first_sql_skill_index < 0 and _looks_like_sql_formatting_application(record):
            first_sql_skill_index = index
        if record.role == "assistant" and _looks_like_sql_answer(lowered):
            first_sql_answer_index = index
            break

    if first_sql_answer_index < 0:
        return []
    if first_sql_skill_index >= 0 and first_sql_skill_index < first_sql_answer_index:
        first_verifier_index = -1
        first_blocked_index = -1
        for index, record in enumerate(records[first_sql_skill_index + 1 : first_sql_answer_index], first_sql_skill_index + 1):
            if first_verifier_index < 0 and _looks_like_sql_formatting_style_verifier(record):
                first_verifier_index = index
            if first_blocked_index < 0 and _looks_like_sql_style_verifier_blocked(record):
                first_blocked_index = index
        if first_verifier_index >= 0 or first_blocked_index >= 0:
            return []
        return [
            {
                "skill": "sql-formatting-style-harness",
                "status": "missing_sql_formatting_style_verifier",
                "severity": "P1",
                "reason": "SQL formatting routed through the host-local skill, but KH did not record verifier evidence before SQL output.",
                "action": "Run or record `verify_sql_formatting_style` / `src.skills.sql_formatting_style` evidence before emitting final SQL, or record a blocked reason before output.",
                "samples": [_short(records[first_sql_answer_index].text)],
            }
        ]

    return [
        {
            "skill": "sql-formatting",
            "status": "missing_before_sql_output",
            "severity": "P1",
            "reason": (
                "An actionable SQL output request received SQL before the host-local "
                "sql-formatting skill or sql-formatting provider route was applied."
            ),
            "action": (
                "Route actionable SQL output through the host-local sql-formatting skill first, "
                "then use sql-formatting-style-harness when KH verification evidence is required."
            ),
            "samples": [_short(records[first_sql_answer_index].text)],
        }
    ]


def _looks_like_sql_formatting_application(record: SessionTextRecord) -> bool:
    lowered = record.text.lower()
    if record.payload_type in {"function_call", "custom_tool_call"}:
        return (
            ("sql-formatting" in lowered or "sql_formatting" in lowered or "sql formatting" in lowered)
            and ("skill.md" in lowered or "\\sql-formatting\\" in lowered or "/sql-formatting/" in lowered)
        )
    if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
        return False
    return _has_sql_formatting_route_evidence(lowered)

def _looks_like_sql_formatting_style_verifier(record: SessionTextRecord) -> bool:
    lowered = record.text.lower()
    if record.payload_type not in {"function_call", "custom_tool_call", "function_call_output", "custom_tool_call_output"}:
        return False
    if not any(
        marker in lowered
        for marker in [
            "verify_sql_formatting_style",
            "src.skills.sql_formatting_style",
            "sql-formatting-style-harness",
            "sql_formatting_style",
            "mechanical_checks",
            "style_contract_source",
        ]
    ):
        return False
    if record.payload_type in {"function_call", "custom_tool_call"}:
        return False
    if _looks_like_sql_style_verifier_blocked(record):
        return False
    return any(marker in lowered for marker in ["passed", "issues", "mechanical_checks", "style_contract_source", "token_optimizer_status"])


def _looks_like_sql_style_verifier_blocked(record: SessionTextRecord) -> bool:
    lowered = record.text.lower()
    if record.payload_type not in {"function_call_output", "custom_tool_call_output"}:
        return False
    if not any(marker in lowered for marker in ["sql-formatting-style-harness", "verify_sql_formatting_style", "src.skills.sql_formatting_style"]):
        return False
    return _is_immediate_blocked_evidence(lowered)


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
        has_decision_shape = any(marker in lowered for marker in ["recommend", "\ucd94\ucc9c", "approval", "\uc2b9\uc778"])
        if has_option_shape and has_decision_shape:
            return text
    return ""


def _is_synthetic_context_message(text: str) -> bool:
    stripped = (text or "").lstrip().lower()
    return stripped.startswith("<environment_context>") or stripped.startswith("<goal_context>")


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
    if "required_records_data" in missing or "open_questions" in missing or len(missing) >= 2:
        return missing
    return []


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
    if selected_orchestration["parallel-orchestration-harness"] and not _has_parallel_strategy_rationale(lowered):
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
    if selected_orchestration["role-execution-audit-harness"] and not _has_role_execution_audit_rationale(lowered):
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
    if _looks_like_external_specialist_direct_question(lowered):
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
    return any(
        marker in lowered
        for marker in [
            "src.orchestration.kh_front_door",
            "kh_front_door",
            "front_door.py",
            "always_on_front_door",
        ]
    )


def _is_non_kh_work_start(payload: Dict[str, Any], lowered: str) -> bool:
    payload_type = str(payload.get("type", ""))
    if payload_type not in {"function_call", "custom_tool_call"}:
        return False
    if _is_non_bootstrap_kh_skill_read(payload, lowered):
        return True
    if _is_kh_front_door_evidence(lowered):
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


def _is_non_bootstrap_kh_skill_read(payload: Dict[str, Any], lowered: str) -> bool:
    tool_name = str(payload.get("name", "")).lower()
    if tool_name not in {"shell_command", "functions.shell_command"}:
        return False
    if "kh-uaf-marketplace" not in lowered and "\\kh-uaf\\" not in lowered and "/kh-uaf/" not in lowered:
        return False
    if "skill.md" not in lowered or "\\skills\\" not in lowered and "/skills/" not in lowered:
        return False
    return "always_on_front_door" not in lowered


def summarize_session_skill_audits(paths: Iterable[str | Path]) -> Dict[str, Any]:
    audits = [analyze_session_skills(path).to_dict() for path in paths]
    aggregate_issues: Dict[str, int] = {}
    for audit in audits:
        for issue in audit.get("issues", []):
            skill = str(issue.get("skill", ""))
            aggregate_issues[skill] = aggregate_issues.get(skill, 0) + 1
    return {
        "session_count": len(audits),
        "audits": audits,
        "aggregate": {
            "issue_count": sum(len(audit.get("issues", [])) for audit in audits),
            "issues_by_skill": dict(sorted(aggregate_issues.items())),
        },
    }


def _session_texts(path: Path) -> List[str]:
    return [record.text for record in _session_text_records(path)]


def _session_text_records(path: Path) -> List[SessionTextRecord]:
    texts: List[SessionTextRecord] = []
    previous_call_was_passive = False
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
            passive = _passive_reference(text.lower()) or (
                payload_type in {"function_call_output", "custom_tool_call_output"}
                and previous_call_was_passive
            )
            if passive:
                text = PASSIVE_REFERENCE_PREFIX + text
            texts.append(SessionTextRecord(text=text, payload_type=payload_type, role=role))
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
        front_door_status = _front_door_skill_status(clean_text, skill_name)
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
            "token_savings_ratio",
            "actual_tokens_saved",
            "actual_token_savings_ratio",
            "actual_usage",
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
    runtime_applied = {str(item) for item in data.get("runtime_applied_skills", []) or []}
    if skill_name in runtime_applied:
        return "applied"
    immediate = {str(item) for item in data.get("immediate_next_skills", []) or []}
    if skill_name in immediate:
        return "selected"
    selected = {str(item) for item in data.get("selected_not_executed_skills", []) or []}
    if skill_name in selected:
        return "selected"
    status_summary = data.get("skill_status_summary", {}) or {}
    if isinstance(status_summary, dict) and skill_name in status_summary:
        summary = status_summary.get(skill_name, {}) or {}
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
    lowered = text.lower()
    if not _looks_like_front_door_runtime_output(lowered):
        return {}
    return _json_object_from_text(text)


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

    if status in {"considered", "procedural"} and _has_resolution_rationale(observations):
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
    satisfied_outputs = []
    missing_outputs = []
    for output_name, markers in ACCEPTANCE_OUTPUT_MARKERS.get(skill_name, {}).items():
        if any(marker.lower() in lowered for marker in markers):
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


def _looks_like_front_door_runtime_output(lowered: str) -> bool:
    if "{" not in lowered or "}" not in lowered:
        return False
    return (
        ('"front_door_status"' in lowered or "'front_door_status'" in lowered)
        and ('"runtime_applied_skills"' in lowered or "'runtime_applied_skills'" in lowered)
        and ('"selected_not_executed_skills"' in lowered or "'selected_not_executed_skills'" in lowered)
        and (
            '"skill_status_summary"' in lowered
            or "'skill_status_summary'" in lowered
            or '"immediate_next_skills"' in lowered
            or "'immediate_next_skills'" in lowered
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


def _required_skills(postmortem: Dict[str, Any], text: str, active_texts: List[str] | None = None) -> Dict[str, str]:
    required: Dict[str, str] = {}
    lowered = text.lower()
    token_gate = postmortem.get("token_gate", {}) or {}
    subagents = postmortem.get("subagent_summary", {}) or {}
    verification_commands = postmortem.get("verification_commands", []) or []
    sql_specialist_scope = _is_sql_specialist_answer_scope(postmortem, lowered, active_texts)

    if _has_nontrivial_work_signals(postmortem, lowered):
        _add(required, "always-on-front-door", "non-trivial KH-capable session should enter KH front-door before any other work")
        _add(required, "automatic-intake-harness", "non-trivial KH-capable session should start with automatic intake")
        _add(required, "plugin-composition-policy", "automatic intake should choose direct, single-provider, hybrid, or clarify route")
        _add(required, "request-complexity-router", "automatic intake should classify request complexity before work")
        _add(required, "skill-catalog", "automatic intake should resolve the packaged skill source before claiming skill use")
    if looks_like_sql_output_request(lowered):
        _add(
            required,
            "sql-formatting-style-harness",
            "actionable SQL output should be checked against the host-local sql-formatting style contract",
        )
    if sql_specialist_scope:
        return required
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
    if _early_domain_discovery_text(lowered) and not looks_like_sql_output_request(lowered):
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
