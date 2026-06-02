from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

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
        "savings_or_passthrough": ["estimated_tokens_saved", "tokens saved", "passthrough", "considered_not_needed", "blocked"],
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
    texts = _session_texts(path)
    active_texts = [_strip_passive_prefix(text) for text in texts if not _is_passive_text(text)]
    combined_text = "\n".join(active_texts)
    catalog = collect_packaged_skills()
    skills = catalog.get("skills", [])
    required = _required_skills(postmortem.to_dict(), combined_text)
    skill_rows = []
    issues = []

    for skill in skills:
        name = str(skill.get("name", ""))
        aliases = _skill_aliases(skill)
        observations = _observations(texts, aliases, name)
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
    issues.extend(_stale_skill_cache_issues(path))
    issues.extend(_cross_scope_context_issues(path))
    issues.extend(_postmortem_guard_issues(postmortem.to_dict()))
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
            "token_gate": postmortem.token_gate,
            "review_status": postmortem.review_status,
            "subagent_summary": postmortem.subagent_summary,
            "completion_guard": postmortem.completion_guard,
            "verification_claim_guard": postmortem.verification_claim_guard,
            "scope_completion_delta": postmortem.scope_completion_delta,
            "user_stop_guard": postmortem.user_stop_guard,
            "resume_guard": postmortem.resume_guard,
            "recommended_actions": postmortem.recommended_actions,
        },
    )


def _postmortem_guard_issues(postmortem: Dict[str, Any]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    token_status = postmortem.get("token_optimizer_status", "")
    if token_status == "blocked":
        issues.append(
            {
                "skill": "token-optimizer",
                "status": "blocked",
                "severity": "P1",
                "reason": "token gate required optimization but runtime usage or passthrough evidence was missing",
                "action": "Run token optimizer, record runtime token_optimization evidence, or record explicit passthrough before completion.",
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
                or _is_automatic_intake_request(text)
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


def _brainstorming_depth_issues(path: Path) -> List[Dict[str, Any]]:
    active_text = "\n".join(_strip_passive_prefix(text) for text in _session_texts(path) if not _is_passive_text(text))
    lowered = active_text.lower()
    if not _early_domain_discovery_text(lowered):
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

    issues: List[Dict[str, Any]] = []
    if implementation_samples and not (has_session_record and has_handoff):
        issues.append(
            {
                "skill": "brainstorming-harness",
                "status": "missing_brainstorm_handoff",
                "severity": "P1",
                "reason": (
                    "Early domain discovery moved into execution without BrainstormSession "
                    "validation and brainstorm_handoff evidence."
                ),
                "action": (
                    "Run the multi-checkpoint brainstorming flow, preserve BrainstormSession/decision_log, "
                    "validate it, build brainstorm_handoff, then hand off to architect-pipeline before implementation."
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


def _subagent_strategy_issues(path: Path, postmortem: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not _is_subagent_session(path):
        return []
    active_text = "\n".join(_strip_passive_prefix(text) for text in _session_texts(path) if not _is_passive_text(text))
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


def _early_domain_discovery_text(lowered: str) -> bool:
    english_markers = [
        "brainstorm",
        "saas",
        "product idea",
        "build a product",
        "develop a product",
        "new product",
        "new app",
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
    return any(
        marker in lowered
        for marker in [
            "subagent_strategy",
            "single-controller",
            "review-only",
            "host-limited",
            "nested subagent",
            "nested-subagent",
            "no-subagent rationale",
            "subagents unavailable",
            "subagents are unavailable",
        ]
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
        if event.get("type") == "response_item" and isinstance(event.get("payload"), dict):
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
    tool_name = str(payload.get("name", "")).lower()
    if payload_type in {"function_call", "custom_tool_call"}:
        if tool_name in {"shell_command", "functions.shell_command"}:
            return (
                "src.orchestration.kh_front_door" in lowered
                or " -m src.orchestration.kh_front_door" in lowered
                or "python -m src.orchestration.kh_front_door" in lowered
            )
        return False
    if payload_type == "function_call_output":
        return _looks_like_front_door_runtime_output(lowered)
    return False


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
    if tool_name not in {"shell_command", "functions.shell_command"}:
        return False
    return any(
        marker in lowered
        for marker in [
            "get-childitem",
            "test-path",
            "select-string",
            "rg ",
            "git ",
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
    texts: List[str] = []
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
            payload_type = payload.get("type")
            passive = _passive_reference(text.lower()) or (
                payload_type in {"function_call_output", "custom_tool_call_output"}
                and previous_call_was_passive
            )
            if passive:
                text = PASSIVE_REFERENCE_PREFIX + text
            texts.append(text)
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


def _observations(texts: List[str], aliases: Set[str], skill_name: str) -> Dict[str, Any]:
    mentions = 0
    inspections = 0
    runtime_hits = 0
    passive_references = 0
    considered = 0
    evidence: List[str] = []
    active_evidence: List[str] = []
    runtime_markers = RUNTIME_MARKERS.get(skill_name, [])

    for text in texts:
        passive = _is_passive_text(text)
        clean_text = _strip_passive_prefix(text)
        lowered = clean_text.lower()
        front_door_status = _front_door_skill_status(clean_text, skill_name)
        alias_hit = bool(front_door_status) or any(alias.lower() in lowered for alias in aliases)
        runtime_hit = (
            front_door_status == "applied"
            or (not front_door_status and any(marker.lower() in lowered for marker in runtime_markers))
        )
        if not alias_hit and not runtime_hit:
            continue
        mentions += 1
        if passive or "skill.md" in lowered or "\\skills\\" in lowered or "/skills/" in lowered:
            inspections += 1
        if passive:
            passive_references += 1
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


def _front_door_skill_status(text: str, skill_name: str) -> str:
    data = _front_door_json(text)
    if not data:
        return ""
    runtime_applied = {str(item) for item in data.get("runtime_applied_skills", []) or []}
    if skill_name in runtime_applied:
        return "applied"
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
        if status:
            return "skipped"
    return ""


def _front_door_json(text: str) -> Dict[str, Any]:
    lowered = text.lower()
    if not _looks_like_front_door_runtime_output(lowered):
        return {}
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
            return "passed"
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


def _looks_like_front_door_runtime_output(lowered: str) -> bool:
    return (
        "front_door_status" in lowered
        and "runtime_applied_skills" in lowered
        and "selected_not_executed_skills" in lowered
        and "skill_status_summary" in lowered
    )


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


def _required_skills(postmortem: Dict[str, Any], text: str) -> Dict[str, str]:
    required: Dict[str, str] = {}
    lowered = text.lower()
    token_gate = postmortem.get("token_gate", {}) or {}
    subagents = postmortem.get("subagent_summary", {}) or {}
    verification_commands = postmortem.get("verification_commands", []) or []

    if _has_nontrivial_work_signals(postmortem, lowered):
        _add(required, "always-on-front-door", "non-trivial KH-capable session should enter KH front-door before any other work")
        _add(required, "automatic-intake-harness", "non-trivial KH-capable session should start with automatic intake")
        _add(required, "plugin-composition-policy", "automatic intake should choose direct, single-provider, hybrid, or clarify route")
        _add(required, "request-complexity-router", "automatic intake should classify request complexity before work")
        _add(required, "skill-catalog", "automatic intake should resolve the packaged skill source before claiming skill use")
    if token_gate.get("required") or _large_session(postmortem):
        _require_core_large_work(required, "large or token-heavy session")
    if subagents.get("spawned", 0) or "spawn_agent" in lowered:
        _add(required, "host-agent-orchestration", "subagents or host delegation appeared in the session")
        _add(required, "subagent-review-pipeline", "subagent work requires packet/review policy")
        _add(required, "role-execution-audit-harness", "claimed subagent/reviewer work needs role execution audit evidence")
        _add(required, "token-optimizer", "subagent packets/transcripts require a token decision")
        if int(subagents.get("spawned", 0) or 0) > 1 or "parallel" in lowered:
            _add(required, "parallel-orchestration-harness", "multiple subagents or parallel work appeared")
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
    if any(marker in lowered for marker in ["browser", "playwright", "screenshot", "localhost"]):
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
    if _early_domain_discovery_text(lowered):
        _add(required, "brainstorming-harness", "early domain discovery appeared")
    if _mentions_architecture_workflow(lowered):
        _add(required, "architect-pipeline", "design or architecture planning appeared")
    if any(marker in lowered for marker in ["domain-orchestration-harness", "work_design", "role_decomposition", "qa/qc", "risk_policy"]):
        _add(required, "domain-orchestration-harness", "domain design/decomposition appeared")
    return required


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
