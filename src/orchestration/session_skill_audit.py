from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

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

RUNTIME_MARKERS = {
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
        "progress.json",
        "RED",
        "GREEN",
        "workspace_strategy",
        "task_status",
    ],
    "goal-state-harness": [
        "GoalState",
        "goal_ledger",
        "create_goal",
        "update_goal",
        "evidence_required",
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
        "subagent",
        "spec-reviewer",
        "code-quality-reviewer",
        "reviewer",
    ],
    "role-execution-audit-harness": [
        "role_execution_audit",
        "audit_role_execution",
        "role execution audited",
    ],
    "parallel-orchestration-harness": [
        "parallel",
        "spawn_agent",
        "create_agent",
        "parallel_wave_count",
        "worktree",
    ],
    "quality-gates-harness": [
        "TDD",
        "RED/GREEN",
        "failing-first",
        "test passed",
        "verification",
    ],
    "qa-gate-harness": [
        "qa gate",
        "QA",
        "browser qa",
        "manual test",
        "verification",
    ],
    "review-gate-harness": [
        "review gate",
        "review_status",
        "with fixes",
        "findings",
    ],
    "command-output-harness": [
        "command output",
        "exit code",
        "stderr",
        "stdout",
        "returncode",
    ],
    "harness-evaluator": [
        "py_compile",
        "compileall",
        "python -m unittest",
        "pytest",
    ],
    "guard-policy-harness": [
        "destructive",
        "permission",
        "approval",
        "secret",
        "delete",
    ],
    "snapshot-state-harness": [
        "SnapshotManager",
        "snapshot",
        "rollback",
        "worktree",
    ],
    "request-complexity-router": [
        "request_complexity",
        "classify_request",
        "light",
        "medium",
        "heavy",
    ],
    "plugin-composition-policy": [
        "plugin_composition",
        "plugin-composition-policy",
        "controller",
        "assistant provider",
    ],
    "skill-catalog": [
        "uaf_skill_catalog",
        "--list",
        "--check",
        "total_skills_found",
    ],
    "scenario-evaluation-harness": [
        "scenario_evaluator",
        "SIDE",
        "scenario",
        "regression",
    ],
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
    combined_text = "\n".join(texts)
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
        row = {
            "name": name,
            "execution_level": skill.get("execution_level", ""),
            "required": is_required,
            "required_reason": required.get(name, ""),
            "status": status,
            "mentions": observations["mentions"],
            "inspections": observations["inspections"],
            "runtime_hits": observations["runtime_hits"],
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
                "skill": "qa-gate-harness",
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
    subagents = postmortem.get("subagent_summary", {}) or {}
    if int(subagents.get("spawned", 0) or 0) > int(subagents.get("closed", 0) or 0):
        issues.append(
            {
                "skill": "host-agent-orchestration",
                "status": "blocked",
                "severity": "P2",
                "reason": "spawned subagents outnumber closed/accounted subagents",
                "action": "Close, resume, or explicitly account for every spawned subagent.",
            }
        )
    return issues


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
        text = _payload_text(payload)
        if text:
            texts.append(text)
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
    considered = 0
    evidence: List[str] = []
    runtime_markers = RUNTIME_MARKERS.get(skill_name, [])

    for text in texts:
        lowered = text.lower()
        alias_hit = any(alias.lower() in lowered for alias in aliases)
        runtime_hit = any(marker.lower() in lowered for marker in runtime_markers)
        if not alias_hit and not runtime_hit:
            continue
        mentions += 1
        if "skill.md" in lowered or "\\skills\\" in lowered or "/skills/" in lowered:
            inspections += 1
        if runtime_hit or _explicit_application(lowered, aliases):
            runtime_hits += 1
        if any(marker in lowered for marker in ["considered_not_needed", "skipped_with_rationale", "blocked", "passthrough"]):
            considered += 1
        if len(evidence) < 8:
            evidence.append(_short(text))

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
        "evidence": evidence,
    }


def _explicit_application(lowered: str, aliases: Set[str]) -> bool:
    if not any(alias.lower() in lowered for alias in aliases):
        return False
    return any(
        marker in lowered
        for marker in [
            '"status": "applied"',
            "'status': 'applied'",
            "application_mode",
            '"runtime"',
            "'runtime'",
            "runtime evidence",
            "used",
        ]
    )


def _required_skills(postmortem: Dict[str, Any], text: str) -> Dict[str, str]:
    required: Dict[str, str] = {}
    lowered = text.lower()
    token_gate = postmortem.get("token_gate", {}) or {}
    subagents = postmortem.get("subagent_summary", {}) or {}
    verification_commands = postmortem.get("verification_commands", []) or []

    if token_gate.get("required") or _large_session(postmortem):
        _require_core_large_work(required, "large or token-heavy session")
    if subagents.get("spawned", 0) or "spawn_agent" in lowered or "subagent" in lowered:
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
        _add(required, "qa-gate-harness", "verification commands or QA claims appeared")
        _add(required, "quality-gates-harness", "verification needs evidence-before-completion gate")
        _add(required, "command-output-harness", "command output should preserve exit code and actionable failure lines")
        _add(required, "harness-evaluator", "Python/test checks appeared")
    if "worktree" in lowered or ".worktrees" in lowered or "git commit" in lowered:
        _add(required, "development-lifecycle-harness", "git/worktree implementation workflow appeared")
        _add(required, "snapshot-state-harness", "large generated changes should record checkpoint or no-snapshot rationale")
    if "compound" in lowered or "compound_handoff" in lowered or "memory_candidates" in lowered:
        _add(required, "compound-engineering-harness", "compound handoff or memory candidates appeared")
        _add(required, "workflow-skill-distiller", "compound learning should route to reusable skill/scenario/memory follow-up")
    if "memory_candidates" in lowered or "memory-state-harness" in lowered or "persistent memory" in lowered or "영구메모리" in text:
        _add(required, "memory-state-harness", "memory candidates or persistent memory appeared")
    if any(marker in lowered for marker in ["browser", "playwright", "screenshot", "localhost"]):
        _add(required, "qa-gate-harness", "browser or local app QA appeared")
    if any(marker in lowered for marker in ["docx", "xlsx", "svg", "dxf", "deliverable", "artifact"]):
        _add(required, "artifact-render-qa-harness", "renderable deliverables or artifacts appeared")
        _add(required, "deliverable-template-quality-harness", "deliverables need template quality evidence")
        _add(required, "traceability-matrix-harness", "deliverables should map requirements to evidence")
    if any(marker in lowered for marker in ["adapter", "codex", "antigravity", "claude code", "plugin", "marketplace"]):
        _add(required, "adapter-contract-harness", "host/plugin/adapter behavior appeared")
        _add(required, "plugin-composition-policy", "multiple plugins or providers may apply")
    if any(marker in lowered for marker in ["delete", "drop table", "secret", "api_key", "token=", "permission", "approval"]):
        _add(required, "guard-policy-harness", "permission, secret, or destructive-action risk appeared")
    if any(marker in lowered for marker in ["brainstorm", "saas", "product idea"]):
        _add(required, "brainstorming-harness", "early product/project discovery appeared")
    if any(marker in lowered for marker in ["architecture", "design doc", "spec", "requirements", "설계"]):
        _add(required, "architect-pipeline", "design or architecture planning appeared")
        _add(required, "domain-orchestration-harness", "domain design/decomposition appeared")
    return required


def _require_core_large_work(required: Dict[str, str], reason: str) -> None:
    for skill in [
        "request-complexity-router",
        "goal-state-harness",
        "development-lifecycle-harness",
        "token-optimizer",
        "workflow-usability-harness",
        "context-state-harness",
    ]:
        _add(required, skill, reason)


def _add(required: Dict[str, str], skill: str, reason: str) -> None:
    required.setdefault(skill, reason)


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
    applied = [row for row in required if STATUS_RANK.get(row["status"], 0) >= STATUS_RANK["considered"]]
    return {
        "total_skills": len(skill_rows),
        "observed_skills": sum(1 for row in skill_rows if row["status"] != "absent"),
        "required_skills": len(required),
        "required_with_evidence": len(applied),
        "required_missing_evidence": len(required) - len(applied),
        "required_missing_skill_names": [row["name"] for row in required if STATUS_RANK.get(row["status"], 0) < STATUS_RANK["considered"]],
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
