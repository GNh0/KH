import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


SENSITIVE_PATTERNS = (
    (
        "database_url_password",
        re.compile(
            r"((?:postgres(?:ql)?|mysql|mariadb|redis|mongodb)"
            r"(?:\+[a-z0-9_]+)?://[^:\s/@]+:)([^@\s]+)(@)",
            re.IGNORECASE,
        ),
    ),
    ("pgpassword", re.compile(r"(\bPGPASSWORD\s*=\s*['\"]?)([^'\"\s;]+)", re.IGNORECASE)),
    (
        "generic_password",
        re.compile(
            r"(\b(?:password|passwd|pwd|token|api[_-]?key|secret)\b\s*[:=]\s*['\"]?)([^'\"\s;,]+)",
            re.IGNORECASE,
        ),
    ),
)

SKILL_PATTERNS = {
    "kh-uaf": re.compile(r"\bkh-uaf\b|\\kh-uaf-marketplace\\|/kh:", re.IGNORECASE),
    "superpowers": re.compile(r"\bsuperpowers\b|\\superpowers\\", re.IGNORECASE),
    "token-optimizer": re.compile(r"\btoken[-_]optimizer\b|token_optimizer_status", re.IGNORECASE),
    "goal-state-harness": re.compile(r"\bgoal[-_]state[-_]harness\b|get_goal|create_goal|update_goal", re.IGNORECASE),
    "development-lifecycle-harness": re.compile(r"\bdevelopment[-_]lifecycle[-_]harness\b|progress\.json", re.IGNORECASE),
    "parallel-orchestration-harness": re.compile(r"\bparallel[-_]orchestration[-_]harness\b|spawn_agent|subagent", re.IGNORECASE),
    "workflow-usability-harness": re.compile(r"\bworkflow[-_]usability[-_]harness\b|workflow_usability_auto", re.IGNORECASE),
    "compound-engineering-harness": re.compile(r"\bcompound[-_]engineering[-_]harness\b|CompoundCapture|compound_handoff", re.IGNORECASE),
}

REVIEWER_PATTERN = re.compile(r"\b(spec|code[- ]quality|reviewer|review)\b|리뷰어|검토", re.IGNORECASE)
FAILURE_PATTERN = re.compile(
    r"fail|failed|failure|error|not available|module not found|unavailable|실패|오류|불가|미완료",
    re.IGNORECASE,
)
COMPLETION_PATTERN = re.compile(
    r"\b(done|complete|completed|finished|verified|pushed|shipped)\b|완료|끝났|마무리|푸시|검증",
    re.IGNORECASE,
)
PARTIAL_MILESTONE_PATTERN = re.compile(
    r"\b(scaffold|skeleton|starter|initial|first slice|vertical slice|mvp slice)\b|스캐폴드|골격|초안|초기|첫|1차",
    re.IGNORECASE,
)

SCOPE_MARKER_PATTERNS = {
    "data_collection": re.compile(
        r"\b(data collection|ingestion|ohlcv|crawler|collector|market data)\b|데이터\s*수집|수집",
        re.IGNORECASE,
    ),
    "features": re.compile(
        r"\b(feature|features|indicator|signal|technical analysis)\b|피처|특징|지표|인디케이터|시그널",
        re.IGNORECASE,
    ),
    "model_training": re.compile(
        r"\b(train|training|model|ml|machine learning)\b|모델\s*학습|학습|훈련",
        re.IGNORECASE,
    ),
    "backtest": re.compile(r"\b(backtest|backtesting)\b|백테스트", re.IGNORECASE),
    "paper_trading": re.compile(
        r"\b(paper[- ]?trading|paper order|simulated order|paper broker)\b|페이퍼\s*트레이딩|모의\s*매매",
        re.IGNORECASE,
    ),
    "db_persistence": re.compile(
        r"\b(database|db|repository|persistence|sqlite|postgres|postgresql)\b|데이터베이스|DB\s*저장|영속|저장",
        re.IGNORECASE,
    ),
    "dashboard_bot": re.compile(
        r"\b(dashboard|bot|streamlit|web ui|monitoring)\b|대시보드|봇|모니터링",
        re.IGNORECASE,
    ),
}

VERIFICATION_COMMAND_PATTERNS = (
    re.compile(r"\bpython\s+-m\s+unittest\b", re.IGNORECASE),
    re.compile(r"\bpython\s+-m\s+py_compile\b", re.IGNORECASE),
    re.compile(r"\bpython\s+-m\s+compileall\b", re.IGNORECASE),
    re.compile(r"\bpytest\b", re.IGNORECASE),
    re.compile(r"\bnpm(?:\.cmd)?\s+(?:run\s+)?(?:test|lint|typecheck|build|qa)\b", re.IGNORECASE),
    re.compile(r"\bnode\s+--check\b", re.IGNORECASE),
    re.compile(r"\bInvoke-WebRequest\b|\bInvoke-RestMethod\b", re.IGNORECASE),
    re.compile(r"\bgit\s+diff\s+--check\b", re.IGNORECASE),
)

USER_STOP_PATTERN = re.compile(
    r"\b(?:stop|pause|cancel|abort|halt)\b|멈추|멈춰|스탑|중단|그만|정지",
    re.IGNORECASE,
)
USER_RESUME_PATTERN = re.compile(
    r"\b(?:resume|continue|proceed|go on)\b|계속|이어|재개|진행해|다시\s*시작",
    re.IGNORECASE,
)
GOAL_CONTEXT_PATTERN = re.compile(r"<goal_context>|Continue working toward the active thread goal", re.IGNORECASE)
STOP_ACK_PATTERN = re.compile(r"멈|스탑|중단|stop|pause|cancel|halt", re.IGNORECASE)
WORK_CONTINUATION_PATTERN = re.compile(
    r"\b(?:continue|resume|proceed|implement|patch|test|verify|run)\b|"
    r"이어서|재개|진행|구현|패치|테스트|검증|작업 범위",
    re.IGNORECASE,
)
ALLOWED_STOP_CHECK_PATTERNS = (
    re.compile(r"\bgit\s+status\b", re.IGNORECASE),
    re.compile(r"\bgit\s+diff(?:\s+--stat)?\b", re.IGNORECASE),
    re.compile(r"\bgit\s+log\b", re.IGNORECASE),
    re.compile(r"\bgit\s+branch\b", re.IGNORECASE),
    re.compile(r"\bGet-ChildItem\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class SecretFinding:
    line: int
    kind: str
    redacted_sample: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SessionPostmortem:
    session_id: str
    cwd: str
    path: str
    line_count: int
    byte_count: int
    skills_observed: List[str] = field(default_factory=list)
    token_optimizer_status: str = "considered_not_needed"
    token_optimizer_provider: str = "kh"
    token_gate: Dict[str, Any] = field(default_factory=dict)
    token_optimizer_evidence: Dict[str, Any] = field(default_factory=dict)
    subagent_summary: Dict[str, Any] = field(default_factory=dict)
    review_status: str = "pending"
    completion_guard: Dict[str, Any] = field(default_factory=dict)
    verification_claim_guard: Dict[str, Any] = field(default_factory=dict)
    scope_completion_delta: Dict[str, Any] = field(default_factory=dict)
    user_stop_guard: Dict[str, Any] = field(default_factory=dict)
    resume_guard: Dict[str, Any] = field(default_factory=dict)
    secret_findings: List[SecretFinding] = field(default_factory=list)
    git_integration: Dict[str, Any] = field(default_factory=dict)
    verification_commands: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["secret_findings"] = [finding.to_dict() for finding in self.secret_findings]
        return data


def redact_sensitive_text(text: str) -> str:
    """Redact common secret shapes before writing logs, handoffs, or memory candidates."""
    redacted = str(text or "")
    for _, pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(r"\1***", redacted)
    return redacted


def find_secret_findings(text: str, line_number: int) -> List[SecretFinding]:
    findings: List[SecretFinding] = []
    for kind, pattern in SENSITIVE_PATTERNS:
        if pattern.search(text or ""):
            findings.append(
                SecretFinding(
                    line=line_number,
                    kind=kind,
                    redacted_sample=_short(redact_sensitive_text(text), 260),
                )
            )
    return findings


def analyze_codex_session_jsonl(
    session_path: str | Path,
    *,
    token_threshold: int = 50_000,
    context_ratio_threshold: float = 0.50,
    max_secret_findings: int = 20,
    max_verification_commands: int = 20,
) -> SessionPostmortem:
    """Build a quality-first postmortem from a Codex Desktop rollout JSONL file."""
    path = Path(session_path)
    session_id = ""
    cwd = ""
    line_count = 0
    skills = set()
    token_info = _empty_token_gate(token_threshold, context_ratio_threshold)
    token_optimizer_evidence = {
        "runtime_calls": 0,
        "skill_doc_reads": 0,
        "explicit_usage_records": 0,
        "status_mentions": 0,
    }
    subagents = {
        "spawned": 0,
        "closed": 0,
        "timed_out": 0,
        "closed_while_running": 0,
        "reviewer_mentions": 0,
    }
    goal_state = {
        "latest_status": "",
        "latest_objective": "",
        "active_updates": 0,
        "complete_updates": 0,
        "terminal_updates": 0,
    }
    stop_state = {
        "requests": [],
        "resume_signals": [],
        "goal_context_after_stop": 0,
        "active_goal_updates_after_stop": 0,
        "terminal_goal_updates_after_stop": 0,
        "latest_goal_status_after_stop": "",
        "continued_tool_calls": [],
        "continued_work_messages": [],
    }
    resume_state = {
        "requests": [],
        "session_start_context_after_resume": 0,
        "runtime_token_evidence_after_resume": 0,
        "large_work_bundle_after_resume": 0,
        "implementation_tools_after_resume": [],
    }
    active_stop_line = 0
    active_resume_line = 0
    task_complete_count = 0
    final_assistant_messages: List[str] = []
    verification_failures: List[Dict[str, Any]] = []
    review_with_fixes = False
    secret_findings: List[SecretFinding] = []
    git_state = {
        "status_checked": False,
        "staged": False,
        "committed": False,
        "pushed": False,
        "remote_checked": False,
        "branch_checked": False,
    }
    verification_commands: List[str] = []

    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        line_count += 1
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue

        if event.get("type") == "session_meta":
            session_id = str(payload.get("id", ""))
            cwd = str(payload.get("cwd", ""))

        payload_type = str(payload.get("type", ""))
        text = _payload_text(payload)
        instruction_context = payload_type == "message" and str(payload.get("role", "")) in {"developer", "system"}
        message_role = str(payload.get("role", ""))

        if payload_type == "thread_goal_updated":
            _merge_goal_state(goal_state, payload)
            if active_stop_line:
                goal = payload.get("goal", {}) or {}
                status = str(goal.get("status", ""))
                if status:
                    stop_state["latest_goal_status_after_stop"] = status
                if status == "active":
                    stop_state["active_goal_updates_after_stop"] += 1
                elif status in {"blocked", "complete"}:
                    stop_state["terminal_goal_updates_after_stop"] += 1
        if payload_type == "task_complete":
            task_complete_count += 1
            last_message = str(payload.get("last_agent_message", ""))
            if last_message:
                final_assistant_messages.append(last_message)

        if text and not instruction_context:
            if payload_type == "message" and message_role == "user":
                if GOAL_CONTEXT_PATTERN.search(text):
                    if active_stop_line:
                        stop_state["goal_context_after_stop"] += 1
                elif _is_user_stop_request(text):
                    active_stop_line = line_number
                    stop_state["requests"].append(
                        {
                            "line": line_number,
                            "sample": _short(redact_sensitive_text(text), 220),
                        }
                    )
                elif active_stop_line and _is_user_resume_request(text):
                    stop_state["resume_signals"].append(
                        {
                            "line": line_number,
                            "sample": _short(redact_sensitive_text(text), 220),
                        }
                    )
                    resume_state["requests"].append(
                        {
                            "line": line_number,
                            "sample": _short(redact_sensitive_text(text), 220),
                        }
                    )
                    active_resume_line = line_number
                    active_stop_line = 0
                elif _is_user_resume_request(text):
                    resume_state["requests"].append(
                        {
                            "line": line_number,
                            "sample": _short(redact_sensitive_text(text), 220),
                        }
                    )
                    active_resume_line = line_number

            if active_stop_line and (
                payload_type == "agent_message" or (payload_type == "message" and message_role == "assistant")
            ):
                if _is_work_continuation_message(text):
                    stop_state["continued_work_messages"].append(
                        {
                            "line": line_number,
                            "sample": _short(redact_sensitive_text(text), 260),
                        }
                    )
            if active_resume_line:
                _merge_resume_guard_evidence(resume_state, text)

            for skill, pattern in SKILL_PATTERNS.items():
                if pattern.search(text):
                    skills.add(skill)
            if payload_type not in {"function_call", "custom_tool_call"}:
                _merge_token_optimizer_evidence(token_optimizer_evidence, text)
            if REVIEWER_PATTERN.search(text):
                subagents["reviewer_mentions"] += 1
            if re.search(r"with fixes|blocking issues|findings|critical|high:", text, re.IGNORECASE):
                review_with_fixes = True
            if len(secret_findings) < max_secret_findings:
                secret_findings.extend(
                    find_secret_findings(text, line_number)[: max_secret_findings - len(secret_findings)]
                )

        if payload_type == "token_count":
            _merge_token_gate(token_info, payload, token_threshold, context_ratio_threshold)
            continue

        if payload_type in {"function_call", "custom_tool_call"}:
            name = str(payload.get("name", ""))
            raw_arguments = payload.get("arguments") or payload.get("input")
            arguments = _parse_arguments(raw_arguments)
            command = str(arguments.get("command", ""))
            if active_resume_line:
                _merge_resume_guard_evidence(resume_state, command or str(raw_arguments or ""))
                if _is_resume_implementation_tool(name, command or str(raw_arguments or "")):
                    resume_state["implementation_tools_after_resume"].append(
                        {
                            "line": line_number,
                            "name": name,
                            "command": _short(redact_sensitive_text(command or str(raw_arguments or "")), 260),
                        }
                    )
            if active_stop_line and not _is_allowed_after_stop_tool(name, command):
                stop_state["continued_tool_calls"].append(
                    {
                        "line": line_number,
                        "name": name,
                        "command": _short(redact_sensitive_text(command or str(raw_arguments or "")), 260),
                    }
                )
            if name in {"spawn_agent", "create_agent"}:
                subagents["spawned"] += 1
            elif name in {"close_agent", "finish_agent"}:
                subagents["closed"] += 1
            if command:
                _merge_token_optimizer_evidence(token_optimizer_evidence, command)
                _update_git_state(git_state, command)
                if _is_verification_command(command) and len(verification_commands) < max_verification_commands:
                    verification_commands.append(redact_sensitive_text(command))
            continue

        if active_stop_line and payload_type in {"patch_apply_end", "patch_apply_begin"}:
            stop_state["continued_tool_calls"].append(
                {
                    "line": line_number,
                    "name": payload_type,
                    "command": _short(redact_sensitive_text(_payload_text(payload) or payload_type), 260),
                }
            )

        if payload_type in {"function_call_output", "custom_tool_call_output"}:
            if _payload_has_timeout(payload):
                subagents["timed_out"] += 1
            output_text = _payload_text(payload)
            if '"previous_status":"running"' in output_text or "'previous_status': 'running'" in output_text:
                subagents["closed_while_running"] += 1
            failure = _verification_failure_from_output(output_text)
            if failure:
                verification_failures.append({"line": line_number, **failure})

    token_status = _token_optimizer_status(token_info, token_optimizer_evidence)
    review_status = _derive_review_status(subagents, review_with_fixes)
    completion_guard = _build_completion_guard(goal_state, task_complete_count, final_assistant_messages)
    verification_claim_guard = _build_verification_claim_guard(verification_failures, final_assistant_messages)
    scope_completion_delta = _build_scope_completion_delta(goal_state, final_assistant_messages)
    user_stop_guard = _build_user_stop_guard(stop_state, goal_state)
    resume_guard = _build_resume_guard(resume_state, token_info)
    actions = _recommended_actions(
        token_status=token_status,
        token_optimizer_evidence=token_optimizer_evidence,
        review_status=review_status,
        completion_guard=completion_guard,
        verification_claim_guard=verification_claim_guard,
        scope_completion_delta=scope_completion_delta,
        user_stop_guard=user_stop_guard,
        resume_guard=resume_guard,
        secret_findings=secret_findings,
        git_state=git_state,
        subagents=subagents,
    )
    evidence = [
        "codex_session_postmortem",
        "token_gate",
        "token_optimizer_evidence",
        "subagent_summary",
        "review_status",
        "active_goal_completion_guard",
        "verification_claim_guard",
        "scope_completion_delta",
        "user_stop_guard",
        "resume_guard",
        "secret_redaction_scan",
        "git_integration_status",
    ]
    return SessionPostmortem(
        session_id=session_id,
        cwd=cwd,
        path=str(path),
        line_count=line_count,
        byte_count=path.stat().st_size,
        skills_observed=sorted(skills),
        token_optimizer_status=token_status,
        token_optimizer_provider="kh",
        token_gate=token_info,
        token_optimizer_evidence=token_optimizer_evidence,
        subagent_summary=subagents,
        review_status=review_status,
        completion_guard=completion_guard,
        verification_claim_guard=verification_claim_guard,
        scope_completion_delta=scope_completion_delta,
        user_stop_guard=user_stop_guard,
        resume_guard=resume_guard,
        secret_findings=secret_findings[:max_secret_findings],
        git_integration=git_state,
        verification_commands=verification_commands,
        recommended_actions=actions,
        evidence=evidence,
    )


def render_session_postmortem(postmortem: SessionPostmortem) -> str:
    lines = [
        "KH Session Postmortem",
        f"Session: {postmortem.session_id or '<unknown>'}",
        f"Workspace: {postmortem.cwd or '<unknown>'}",
        f"Token optimizer: {postmortem.token_optimizer_status}",
        f"Review: {postmortem.review_status}",
        f"Completion guard: {postmortem.completion_guard.get('status', 'unknown')}",
        f"Verification guard: {postmortem.verification_claim_guard.get('status', 'unknown')}",
        f"User stop guard: {postmortem.user_stop_guard.get('status', 'unknown')}",
        f"Resume guard: {postmortem.resume_guard.get('status', 'unknown')}",
        (
            "Subagents: "
            f"{postmortem.subagent_summary.get('spawned', 0)} spawned, "
            f"{postmortem.subagent_summary.get('timed_out', 0)} timed out, "
            f"{postmortem.subagent_summary.get('closed_while_running', 0)} closed while running"
        ),
        (
            "Git: "
            f"staged={postmortem.git_integration.get('staged', False)}, "
            f"committed={postmortem.git_integration.get('committed', False)}, "
            f"pushed={postmortem.git_integration.get('pushed', False)}"
        ),
    ]
    if postmortem.skills_observed:
        lines.append("Skills: " + ", ".join(postmortem.skills_observed))
    if postmortem.secret_findings:
        lines.append(f"Secret findings: {len(postmortem.secret_findings)} redacted")
    if postmortem.recommended_actions:
        lines.append("Recommended actions:")
        lines.extend(f"- {action}" for action in postmortem.recommended_actions)
    return "\n".join(lines).rstrip() + "\n"


def _empty_token_gate(token_threshold: int, context_ratio_threshold: float) -> Dict[str, Any]:
    return {
        "required": False,
        "threshold_tokens": token_threshold,
        "context_ratio_threshold": context_ratio_threshold,
        "max_total_tokens": 0,
        "max_last_input_tokens": 0,
        "model_context_window": 0,
        "max_context_ratio": 0.0,
        "reasons": [],
    }


def _merge_token_gate(
    token_gate: Dict[str, Any],
    payload: Dict[str, Any],
    token_threshold: int,
    context_ratio_threshold: float,
) -> None:
    info = payload.get("info", {}) or {}
    total = info.get("total_token_usage", {}) or {}
    last = info.get("last_token_usage", {}) or {}
    context_window = int(info.get("model_context_window", 0) or 0)
    total_tokens = int(total.get("total_tokens", 0) or 0)
    last_input_tokens = int(last.get("input_tokens", 0) or 0)
    ratio = (last_input_tokens / context_window) if context_window else 0.0
    token_gate["max_total_tokens"] = max(int(token_gate["max_total_tokens"]), total_tokens)
    token_gate["max_last_input_tokens"] = max(int(token_gate["max_last_input_tokens"]), last_input_tokens)
    token_gate["model_context_window"] = max(int(token_gate["model_context_window"]), context_window)
    token_gate["max_context_ratio"] = max(float(token_gate["max_context_ratio"]), ratio)
    if total_tokens >= token_threshold:
        token_gate["required"] = True
        _append_unique(token_gate["reasons"], "total_tokens_above_threshold")
    if ratio >= context_ratio_threshold:
        token_gate["required"] = True
        _append_unique(token_gate["reasons"], "context_ratio_above_threshold")


def _token_optimizer_status(token_gate: Dict[str, Any], evidence: Dict[str, Any]) -> str:
    if evidence.get("runtime_calls") or evidence.get("explicit_usage_records"):
        return "used"
    if token_gate.get("required"):
        return "blocked"
    return "considered_not_needed"


def _merge_token_optimizer_evidence(evidence: Dict[str, Any], text: str) -> None:
    if not text:
        return
    if re.search(r"name:\s*token-optimizer|# Token Optimizer Skill", text, re.IGNORECASE):
        evidence["skill_doc_reads"] = int(evidence.get("skill_doc_reads", 0)) + 1
        return
    if re.search(r"token[-_]optimizer|token_optimizer_status", text, re.IGNORECASE):
        evidence["status_mentions"] = int(evidence.get("status_mentions", 0)) + 1
    if re.search(r"token_optimizer[/\\]SKILL\.md|token_optimizer\\SKILL\.md|token_optimizer/SKILL\.md", text, re.IGNORECASE):
        evidence["skill_doc_reads"] = int(evidence.get("skill_doc_reads", 0)) + 1
        return
    if re.search(
        r"src\.skills\.token_optimizer|python\s+-m\s+src\.skills\.token_optimizer|"
        r"src\.orchestration\.runtime_token_optimizer|optimize_workflow_task_results|"
        r"runtime_token_optimization|metadata\.token_optimizer|"
        r"summarize_command_output|optimize_context_content|summarize_agent_transcript|"
        r"aggregate_token_usage_stats|compare_token_usage",
        text,
        re.IGNORECASE,
    ):
        evidence["runtime_calls"] = int(evidence.get("runtime_calls", 0)) + 1
    if re.search(r"token_savings_ratio|estimated_tokens_saved|without_token_optimizer|with_token_optimizer", text, re.IGNORECASE):
        evidence["explicit_usage_records"] = int(evidence.get("explicit_usage_records", 0)) + 1


def _merge_resume_guard_evidence(resume_state: Dict[str, Any], text: str) -> None:
    if not text:
        return
    if re.search(r"session_start_context|build_session_start_context|read_latest_interruption_checkpoint", text, re.IGNORECASE):
        resume_state["session_start_context_after_resume"] = int(
            resume_state.get("session_start_context_after_resume", 0)
        ) + 1
    if re.search(
        r"src\.skills\.token_optimizer|src\.orchestration\.runtime_token_optimizer|"
        r"runtime_token_optimization|estimated_tokens_saved|summarize_command_output|"
        r"optimize_workflow_task_results|metadata\.token_optimizer",
        text,
        re.IGNORECASE,
    ):
        resume_state["runtime_token_evidence_after_resume"] = int(
            resume_state.get("runtime_token_evidence_after_resume", 0)
        ) + 1
    if re.search(r"large_work_orchestration_bundle|skill_statuses|skill_transition_handoff", text, re.IGNORECASE):
        resume_state["large_work_bundle_after_resume"] = int(
            resume_state.get("large_work_bundle_after_resume", 0)
        ) + 1


def _derive_review_status(subagents: Dict[str, Any], review_with_fixes: bool) -> str:
    if subagents.get("timed_out") or subagents.get("closed_while_running"):
        return "review_incomplete"
    if review_with_fixes:
        return "with_fixes"
    if subagents.get("reviewer_mentions") and subagents.get("closed"):
        return "passed_or_no_blocking_findings"
    return "pending"


def _merge_goal_state(goal_state: Dict[str, Any], payload: Dict[str, Any]) -> None:
    goal = payload.get("goal", {}) or {}
    status = str(goal.get("status", ""))
    objective = str(goal.get("objective", ""))
    if status:
        goal_state["latest_status"] = status
        if status == "active":
            goal_state["active_updates"] += 1
        elif status == "complete":
            goal_state["complete_updates"] += 1
            goal_state["terminal_updates"] += 1
        elif status == "blocked":
            goal_state["terminal_updates"] += 1
    if objective:
        goal_state["latest_objective"] = objective


def _build_completion_guard(
    goal_state: Dict[str, Any],
    task_complete_count: int,
    final_messages: List[str],
) -> Dict[str, Any]:
    latest_status = str(goal_state.get("latest_status", ""))
    final_claims_completion = any(_claims_completion(message) for message in final_messages)
    blocked = latest_status == "active" and task_complete_count > 0 and final_claims_completion
    reasons: List[str] = []
    if blocked:
        reasons.append("task_complete_emitted_while_goal_active")
    return {
        "status": "blocked" if blocked else "passed",
        "latest_goal_status": latest_status,
        "task_complete_count": task_complete_count,
        "final_claims_completion": final_claims_completion,
        "reasons": reasons,
    }


def _build_verification_claim_guard(
    verification_failures: List[Dict[str, Any]],
    final_messages: List[str],
) -> Dict[str, Any]:
    final_mentions_failure = any(FAILURE_PATTERN.search(message) for message in final_messages)
    return {
        "status": "blocked" if verification_failures and not final_mentions_failure else "passed",
        "failed_verification_count": len(verification_failures),
        "final_report_mentions_failure": final_mentions_failure,
        "failures": verification_failures[:10],
    }


def _build_scope_completion_delta(
    goal_state: Dict[str, Any],
    final_messages: List[str],
) -> Dict[str, Any]:
    objective = str(goal_state.get("latest_objective", ""))
    final_text = "\n".join(final_messages)
    objective_markers = _scope_markers(objective)
    completed_markers = _scope_markers(final_text)
    missing = [marker for marker in objective_markers if marker not in completed_markers]
    partial_only = bool(missing and _mentions_partial_milestone(final_text))
    return {
        "status": "blocked" if partial_only else "passed",
        "objective_markers": objective_markers,
        "completed_markers": completed_markers,
        "missing_markers": missing,
        "partial_milestone_claimed": partial_only,
    }


def _build_user_stop_guard(
    stop_state: Dict[str, Any],
    goal_state: Dict[str, Any],
) -> Dict[str, Any]:
    requests = list(stop_state.get("requests", []) or [])
    continued_tool_calls = list(stop_state.get("continued_tool_calls", []) or [])
    continued_work_messages = list(stop_state.get("continued_work_messages", []) or [])
    latest_goal_status = str(stop_state.get("latest_goal_status_after_stop") or goal_state.get("latest_status") or "")
    terminal_updates_after_stop = int(stop_state.get("terminal_goal_updates_after_stop", 0) or 0)
    active_goal_left_open = bool(requests and latest_goal_status == "active" and terminal_updates_after_stop == 0)
    reasons: List[str] = []
    if continued_tool_calls:
        reasons.append("tool_call_after_user_stop")
    if continued_work_messages:
        reasons.append("work_continuation_after_user_stop")
    if active_goal_left_open:
        reasons.append("user_stop_left_goal_active")
    if requests and int(stop_state.get("goal_context_after_stop", 0) or 0) and active_goal_left_open:
        reasons.append("goal_context_reactivated_after_user_stop")
    return {
        "status": "blocked" if reasons else "passed",
        "stop_request_count": len(requests),
        "latest_stop_line": requests[-1]["line"] if requests else 0,
        "goal_context_after_stop": int(stop_state.get("goal_context_after_stop", 0) or 0),
        "latest_goal_status_after_stop": latest_goal_status,
        "terminal_goal_updates_after_stop": terminal_updates_after_stop,
        "continued_tool_calls": continued_tool_calls[:10],
        "continued_work_messages": continued_work_messages[:10],
        "reasons": reasons,
    }


def _build_resume_guard(resume_state: Dict[str, Any], token_gate: Dict[str, Any]) -> Dict[str, Any]:
    requests = list(resume_state.get("requests", []) or [])
    implementation_tools = list(resume_state.get("implementation_tools_after_resume", []) or [])
    session_context_count = int(resume_state.get("session_start_context_after_resume", 0) or 0)
    token_runtime_count = int(resume_state.get("runtime_token_evidence_after_resume", 0) or 0)
    bundle_count = int(resume_state.get("large_work_bundle_after_resume", 0) or 0)
    reasons: List[str] = []
    if requests and implementation_tools and not session_context_count:
        reasons.append("resume_without_session_start_context")
    if requests and implementation_tools and token_gate.get("required") and not token_runtime_count:
        reasons.append("resume_without_runtime_token_optimizer")
    if requests and implementation_tools and not bundle_count:
        reasons.append("resume_without_large_work_skill_bundle")
    return {
        "status": "blocked" if reasons else "passed",
        "resume_request_count": len(requests),
        "latest_resume_line": requests[-1]["line"] if requests else 0,
        "session_start_context_after_resume": session_context_count,
        "runtime_token_evidence_after_resume": token_runtime_count,
        "large_work_bundle_after_resume": bundle_count,
        "implementation_tools_after_resume": implementation_tools[:10],
        "reasons": reasons,
    }


def _recommended_actions(
    *,
    token_status: str,
    token_optimizer_evidence: Dict[str, Any],
    review_status: str,
    completion_guard: Dict[str, Any],
    verification_claim_guard: Dict[str, Any],
    scope_completion_delta: Dict[str, Any],
    user_stop_guard: Dict[str, Any],
    resume_guard: Dict[str, Any],
    secret_findings: List[SecretFinding],
    git_state: Dict[str, Any],
    subagents: Dict[str, Any],
) -> List[str]:
    actions: List[str] = []
    if token_status == "blocked":
        actions.append("Run token-optimizer or record passthrough before continuing the large session.")
        if token_optimizer_evidence.get("skill_doc_reads") and not token_optimizer_evidence.get("runtime_calls"):
            actions.append("Reading token-optimizer docs is inspection, not usage; require runtime evidence or explicit passthrough.")
    if review_status == "review_incomplete":
        actions.append("Treat timed-out or running-closed reviewers as review_incomplete; re-review before completion.")
    if completion_guard.get("status") == "blocked":
        actions.append("Do not emit task_complete as final completion while the user goal is still active; report partial progress and next task.")
    if verification_claim_guard.get("status") == "blocked":
        actions.append("Report failed or unavailable verification explicitly before claiming the run is verified.")
    if scope_completion_delta.get("status") == "blocked":
        actions.append("Record scope_completion_delta and continue the missing objective markers instead of stopping at a scaffold milestone.")
    if user_stop_guard.get("status") == "blocked":
        actions.append(
            "User stop/cancel requests override goal_context; stop new work, block the active goal only when host policy allows it, otherwise write interruption checkpoint evidence and ignore automated goal_context until a fresh user resume."
        )
    if resume_guard.get("status") == "blocked":
        actions.append(
            "Resume/restart requests must run KH session_start_context, runtime token optimization or passthrough, and large_work_orchestration_bundle evidence before implementation tools."
        )
    if secret_findings:
        actions.append("Redact secret-like command text before writing handoffs, memory candidates, or reports.")
    if git_state.get("staged") and not git_state.get("committed"):
        actions.append("Finish commit_sha evidence or report integration_status=staged_only.")
    if git_state.get("committed") and not git_state.get("pushed"):
        actions.append("Finish push evidence or report integration_status=committed_only.")
    if subagents.get("spawned", 0) > subagents.get("closed", 0):
        actions.append("Close or account for every spawned subagent before final status.")
    return actions


def _payload_text(payload: Dict[str, Any]) -> str:
    payload_type = payload.get("type")
    if payload_type == "message":
        return _content_text(payload.get("content"))
    if payload_type == "agent_message":
        return _content_text(payload.get("message") or payload.get("content"))
    if payload_type == "function_call":
        return str(payload.get("name", "")) + " " + str(payload.get("arguments", ""))
    if payload_type in {"function_call_output", "custom_tool_call_output"}:
        return _content_text(payload.get("output") or payload.get("content"))
    if payload_type == "custom_tool_call":
        return str(payload.get("name", "")) + " " + str(payload.get("input") or payload.get("arguments") or "")
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
                parts.append(str(item.get("text") or item.get("input_text") or item.get("output_text") or ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False, sort_keys=True)
    return str(content or "")


def _parse_arguments(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _payload_has_timeout(payload: Dict[str, Any]) -> bool:
    output = payload.get("output")
    if isinstance(output, dict):
        return bool(output.get("timed_out"))
    text = _content_text(output)
    return '"timed_out":true' in text.replace(" ", "").lower()


def _verification_failure_from_output(output_text: str) -> Dict[str, Any]:
    text = output_text or ""
    compact = text.lower()
    if '"ok":false' in compact or "'ok': false" in compact:
        return {"kind": "tool_verification_failed", "sample": _short(redact_sensitive_text(text), 300)}
    if "module not found: playwright" in compact:
        return {"kind": "browser_qa_unavailable", "sample": _short(redact_sensitive_text(text), 300)}
    if re.search(r"\b(exit code|return)\s*[:=]?\s*(?:1|2|124)\b", text, re.IGNORECASE):
        if FAILURE_PATTERN.search(text) or re.search(r"\b(fatal|traceback)\b", text, re.IGNORECASE):
            return {"kind": "command_verification_failed", "sample": _short(redact_sensitive_text(text), 300)}
    return {}


def _update_git_state(state: Dict[str, Any], command: str) -> None:
    normalized = re.sub(r"\s+", " ", command.strip()).lower()
    if re.search(r"\bgit\s+status\b", normalized):
        state["status_checked"] = True
    if re.search(r"\bgit\s+add\b", normalized):
        state["staged"] = True
    if re.search(r"\bgit\s+commit\b", normalized):
        state["committed"] = True
    if re.search(r"\bgit\s+push\b", normalized):
        state["pushed"] = True
    if re.search(r"\bgit\s+remote\b", normalized):
        state["remote_checked"] = True
    if re.search(r"\bgit\s+(?:branch|checkout|switch)\b", normalized):
        state["branch_checked"] = True


def _is_verification_command(command: str) -> bool:
    return any(pattern.search(command) for pattern in VERIFICATION_COMMAND_PATTERNS)


def _append_unique(items: List[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _short(text: str, max_length: int) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    return compact[:max_length] + ("..." if len(compact) > max_length else "")


def _claims_completion(text: str) -> bool:
    return bool(COMPLETION_PATTERN.search(text or ""))


def _mentions_partial_milestone(text: str) -> bool:
    return bool(PARTIAL_MILESTONE_PATTERN.search(text or ""))


def _is_user_stop_request(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized or GOAL_CONTEXT_PATTERN.search(normalized):
        return False
    lowered = normalized.lower()
    if "stop loss" in lowered or "stop-loss" in lowered:
        return False
    return bool(USER_STOP_PATTERN.search(normalized))


def _is_user_resume_request(text: str) -> bool:
    normalized = (text or "").strip()
    return bool(normalized and USER_RESUME_PATTERN.search(normalized))


def _is_work_continuation_message(text: str) -> bool:
    normalized = text or ""
    return bool(WORK_CONTINUATION_PATTERN.search(normalized) and not STOP_ACK_PATTERN.search(normalized))


def _is_allowed_after_stop_tool(name: str, command: str) -> bool:
    normalized_name = str(name or "")
    if normalized_name == "update_plan":
        return True
    if normalized_name != "shell_command":
        return False
    normalized_command = re.sub(r"\s+", " ", command or "").strip()
    return bool(normalized_command and any(pattern.search(normalized_command) for pattern in ALLOWED_STOP_CHECK_PATTERNS))


def _is_resume_implementation_tool(name: str, command: str) -> bool:
    normalized_name = str(name or "")
    normalized_command = re.sub(r"\s+", " ", command or "").strip()
    if normalized_name in {"apply_patch", "custom_tool_call"}:
        return True
    if normalized_name != "shell_command":
        return False
    if not normalized_command:
        return False
    if re.search(r"\b(git\s+commit|git\s+push|git\s+add)\b", normalized_command, re.IGNORECASE):
        return True
    if _is_verification_command(normalized_command):
        return True
    return False


def _scope_markers(text: str) -> List[str]:
    markers = []
    for marker, pattern in SCOPE_MARKER_PATTERNS.items():
        if pattern.search(text or ""):
            markers.append(marker)
    return markers


__all__ = [
    "SecretFinding",
    "SessionPostmortem",
    "analyze_codex_session_jsonl",
    "find_secret_findings",
    "redact_sensitive_text",
    "render_session_postmortem",
]
