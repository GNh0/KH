import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.orchestration.request_classifier import resolve_request_intent


MAX_INTEGRITY_SAMPLES = 20
MAX_GUARD_SAMPLES = 10
MAX_ASSISTANT_STOP_SAMPLES = 5
MAX_ARCHIVE_SAMPLES = 5
MAX_VERIFICATION_FAILURE_SAMPLES = 10
MAX_VERIFICATION_COMMAND_CHARS = 4_096
MAX_GOAL_OBJECTIVE_CHARS = 2_048
MAX_POSTMORTEM_SCALAR_BYTES = 4_096
MAX_PAYLOAD_TYPE_BYTES = 256
MAX_ROLE_BYTES = 128
MAX_GOAL_STATUS_BYTES = 256
MAX_CALL_NAME_BYTES = 512
_SESSION_TEXT_SCAN_REGEX_THRESHOLD = 64 * 1024


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

SKILL_PATTERN_HINTS = {
    "kh-uaf": ("kh-uaf", "/kh:"),
    "superpowers": ("superpowers",),
    "token-optimizer": ("token-optimizer", "token_optimizer"),
    "goal-state-harness": (
        "goal-state-harness",
        "goal_state_harness",
        "get_goal",
        "create_goal",
        "update_goal",
    ),
    "development-lifecycle-harness": (
        "development-lifecycle-harness",
        "development_lifecycle_harness",
        "progress.json",
    ),
    "parallel-orchestration-harness": (
        "parallel-orchestration-harness",
        "parallel_orchestration_harness",
        "spawn_agent",
        "subagent",
    ),
    "workflow-usability-harness": (
        "workflow-usability-harness",
        "workflow_usability_harness",
        "workflow_usability_auto",
    ),
    "compound-engineering-harness": (
        "compound-engineering-harness",
        "compound_engineering_harness",
        "compoundcapture",
        "compound_handoff",
    ),
}

_POSTMORTEM_SKILL_HINT_PATTERN = re.compile(
    "|".join(
        sorted(
            {
                re.escape(hint)
                for hints in SKILL_PATTERN_HINTS.values()
                for hint in hints
            },
            key=len,
            reverse=True,
        )
    )
)
_POSTMORTEM_TOKEN_HINT_PATTERN = re.compile(
    r"token|summarize_command_output|optimize_context_content|"
    r"summarize_agent_transcript|compare_token_usage|"
    r"aggregate_token_usage_stats|optimize_workflow_task_results"
)
_POSTMORTEM_REVIEW_HINT_PATTERN = re.compile(
    r"spec|code|quality|reviewer|review|리뷰어|검토|"
    r"with fixes|blocking issues|findings|critical|high:"
)
_POSTMORTEM_SECRET_HINT_PATTERN = re.compile(
    r"postgres|mysql|mariadb|redis|mongodb|pgpassword|"
    r"password|passwd|pwd|token|api_key|api-key|secret"
)
_HINT_SKILL = 1 << 0
_HINT_TOKEN = 1 << 1
_HINT_REVIEW = 1 << 2
_HINT_SECRET = 1 << 3
_HINT_RESUME_CONTEXT = 1 << 4
_HINT_RESUME_TOKEN = 1 << 5
_HINT_RESUME_BUNDLE = 1 << 6
_HINT_SQL = 1 << 7
_HINT_COMPLETION = 1 << 8
_HINT_FAILURE = 1 << 9
_HINT_SCOPE = 1 << 10
_HINT_PARTIAL = 1 << 11
_HINT_ARCHIVE = 1 << 12
_HINT_SELF_STOP = 1 << 13
_HINT_WORK = 1 << 14

_POSTMORTEM_AUDIT_LITERALS = (
    "front_door",
    "always-on-front-door",
    "immediate_next_skill",
    "execution_gate",
    "kh-uaf-marketplace",
    "skills",
    "read_thread",
    "rollout",
    "memory",
    "powerbuilder",
    "pb-to-csharp",
    "brainstorm",
    "get-childitem",
    "option",
    "choose",
    "선택",
    "skill",
    "harness",
    "runtime",
    "subagent",
    "parallel",
    "delegate",
    "memory_import",
    "token_optimizer",
    "token_optimization",
)
_POSTMORTEM_SQL_HINT_PATTERN = re.compile(
    r"sql|select|insert|update|delete|merge|drop|truncate|alter|create|"
    r"exec|raiserror|openxml|procedure|프로시저|query|쿼리"
)


def _literal_hint_map() -> Dict[str, int]:
    values: Dict[str, int] = {}

    def add(bit: int, literals: Iterable[str]) -> None:
        for literal in literals:
            normalized = str(literal).lower()
            values[normalized] = values.get(normalized, 0) | bit

    add(
        _HINT_SKILL,
        {
            hint
            for hints in SKILL_PATTERN_HINTS.values()
            for hint in hints
        },
    )
    add(
        _HINT_TOKEN,
        (
            "token",
            "token-optimizer",
            "token_optimizer",
            "token_optimizer_status",
            "summarize_command_output",
            "optimize_context_content",
            "summarize_agent_transcript",
            "compare_token_usage",
            "aggregate_token_usage_stats",
            "optimize_workflow_task_results",
        ),
    )
    add(
        _HINT_REVIEW,
        (
            "spec",
            "code",
            "quality",
            "reviewer",
            "review",
            "리뷰어",
            "검토",
            "with fixes",
            "blocking issues",
            "findings",
            "critical",
            "high:",
        ),
    )
    add(
        _HINT_SECRET,
        (
            "postgres",
            "mysql",
            "mariadb",
            "redis",
            "mongodb",
            "pgpassword",
            "password",
            "passwd",
            "pwd",
            "token",
            "api_key",
            "api-key",
            "secret",
        ),
    )
    add(
        _HINT_RESUME_CONTEXT,
        (
            "session_start_context",
            "build_session_start_context",
            "read_latest_interruption_checkpoint",
        ),
    )
    add(
        _HINT_RESUME_TOKEN,
        (
            "src.skills.token_optimizer",
            "src.orchestration.runtime_token_optimizer",
            "runtime_token_optimization",
            "estimated_tokens_saved",
            "actual_tokens_saved",
            "summarize_command_output",
            "optimize_workflow_task_results",
            "metadata.token_optimizer",
        ),
    )
    add(
        _HINT_RESUME_BUNDLE,
        (
            "large_work_orchestration_bundle",
            "skill_statuses",
            "skill_transition_handoff",
        ),
    )
    add(
        _HINT_SQL,
        (
            "sql",
            "select",
            "insert",
            "update",
            "delete",
            "merge",
            "drop",
            "truncate",
            "alter",
            "create",
            "exec",
            "raiserror",
            "openxml",
            "procedure",
            "프로시저",
            "query",
            "쿼리",
        ),
    )
    add(
        _HINT_COMPLETION,
        (
            "done",
            "complete",
            "finished",
            "verified",
            "pushed",
            "shipped",
            "release-ready",
            "ready for release",
            "delivered",
            "완료",
            "끝냈",
            "마무리",
            "검증",
            "출시",
            "배포",
            "전달",
            "제공",
        ),
    )
    add(
        _HINT_FAILURE,
        (
            "fail",
            "error",
            "not available",
            "module not found",
            "unavailable",
            "실패",
            "오류",
            "불가",
            "미완료",
        ),
    )
    add(
        _HINT_SCOPE,
        (
            "data collection",
            "ingestion",
            "ohlcv",
            "crawler",
            "collector",
            "market data",
            "feature",
            "indicator",
            "signal",
            "technical analysis",
            "train",
            "model",
            "machine learning",
            "backtest",
            "paper",
            "database",
            "repository",
            "persistence",
            "sqlite",
            "postgres",
            "dashboard",
            "bot",
            "streamlit",
            "web ui",
            "monitoring",
            "수집",
            "피처",
            "특징",
            "지표",
            "시그널",
            "학습",
            "훈련",
            "백테스트",
            "모의",
            "데이터베이스",
            "저장",
            "영속",
            "대시보드",
            "모니터링",
        ),
    )
    add(
        _HINT_PARTIAL,
        (
            "scaffold",
            "skeleton",
            "starter",
            "initial",
            "first slice",
            "vertical slice",
            "mvp slice",
            "스캐폴드",
            "골격",
            "초안",
            "초기",
            "1차",
        ),
    )
    add(_HINT_ARCHIVE, ("::archive",))
    add(
        _HINT_SELF_STOP,
        (
            "stopped",
            "stopping",
            "blocked",
            "cannot continue",
            "unable to continue",
            "work stopped",
            "pausing",
            "중단",
            "종료",
            "멈춥니다",
            "차단",
        ),
    )
    add(
        _HINT_WORK,
        (
            "continue",
            "resume",
            "proceed",
            "implement",
            "patch",
            "test",
            "verify",
            "run",
            "이어서",
            "재개",
            "진행",
            "구현",
            "패치",
            "테스트",
            "검증",
            "작업 범위",
        ),
    )
    add(0, _POSTMORTEM_AUDIT_LITERALS)
    return values


_POSTMORTEM_LITERAL_HINTS = _literal_hint_map()
_POSTMORTEM_LITERAL_PATTERN = re.compile(
    "|".join(
        re.escape(value)
        for value in sorted(
            _POSTMORTEM_LITERAL_HINTS,
            key=len,
            reverse=True,
        )
    )
)

REVIEWER_PATTERN = re.compile(r"\b(spec|code[- ]quality|reviewer|review)\b|리뷰어|검토", re.IGNORECASE)
FAILURE_PATTERN = re.compile(
    r"fail|failed|failure|error|not available|module not found|unavailable|실패|오류|불가|미완료",
    re.IGNORECASE,
)
VERIFICATION_EXIT_CODE_PATTERN = re.compile(
    r"\b(exit code|return)\s*[:=]?\s*(?:1|2|124)\b",
    re.IGNORECASE,
)
VERIFICATION_FATAL_PATTERN = re.compile(r"\b(fatal|traceback)\b", re.IGNORECASE)
COMPLETION_PATTERN = re.compile(
    r"\b(done|complete|completed|finished|verified|pushed|shipped)\b|완료|끝났|마무리|푸시|검증",
    re.IGNORECASE,
)
COMPLETION_PATTERN = re.compile(
    r"\b(?:done|complete|completed|finished|verified|pushed|shipped|"
    r"release[- ]ready|ready\s+for\s+release|fully\s+delivered|delivered\s+in\s+full)\b|"
    r"완료|끝냈|마무리(?:했|됐|되었)|검증(?:했|됐|되었)|"
    r"(?:출시|배포)\s*준비\s*완료|완전히\s*(?:전달|제공)(?:했|됐|되었|되었습니다)?",
    re.IGNORECASE,
)
COMPLETION_NEGATION_PATTERNS = (
    re.compile(
        r"\b(?:not|never|isn't|is\s+not|wasn't|was\s+not|aren't|are\s+not)\s+"
        r"(?:fully\s+)?(?:done|complete|completed|finished|verified|pushed|shipped|"
        r"release[- ]ready|ready\s+for\s+release|delivered)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:has|have|had)\s+not\s+been\s+"
        r"(?:completed|finished|verified|pushed|shipped|delivered)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:cannot|can't|could\s+not|couldn't|failed\s+to|unable\s+to)\s+"
        r"(?:be\s+)?(?:complete|completed|finish|finished|verify|push|ship|deliver)\w*\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:incomplete|unfinished|not\s+ready\s+for\s+release)\b", re.IGNORECASE),
    re.compile(
        r"(?:완료|마무리|검증|전달|제공)(?:가|는|이)?\s*"
        r"(?:되지\s*않|되지\s*못|하지\s*않|하지\s*못|안\s*되|불가|실패)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:출시|배포)\s*준비(?:가|는|이)?\s*(?:되지\s*않|되지\s*못|안\s*되|미완료|불가)",
        re.IGNORECASE,
    ),
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

GOAL_CONTEXT_PATTERN = re.compile(r"<goal_context>|Continue working toward the active thread goal", re.IGNORECASE)
STOP_ACK_PATTERN = re.compile(r"멈|스탑|중단|stop|pause|cancel|halt", re.IGNORECASE)
ASSISTANT_SELF_STOP_PATTERN = re.compile(
    r"\b(?:stopped|stopping|blocked|cannot continue|unable to continue|work stopped|pausing)\b|"
    r"\uc791\uc5c5\s*\uc911\ub2e8|\uc911\ub2e8\ud569\ub2c8\ub2e4|"
    r"\uc911\ub2e8\ud558\uace0\s*\uc885\ub8cc|\uc911\ub2e8.*\uc885\ub8cc|"
    r"\uc885\ub8cc\ud569\ub2c8\ub2e4|"
    r"\uc77c\ub2e8\s*\uc911\ub2e8|\uba48\ucda5\ub2c8\ub2e4|"
    r"\uc9c4\ud589\ud560\s*\uc218\s*\uc5c6\uc2b5\ub2c8\ub2e4|"
    r"\ucc28\ub2e8\ub418\uc5b4|\ucc28\ub2e8\ub410",
    re.IGNORECASE,
)
ARCHIVE_DIRECTIVE_PATTERN = re.compile(r"::archive\s*\{", re.IGNORECASE)
USER_ARCHIVE_REQUEST_PATTERN = re.compile(
    r"\b(?:archive|close conversation|close this conversation|end conversation|end this thread)\b|"
    r"\ub300\ud654\s*\uc885\ub8cc|\ucc44\ud305\s*\uc885\ub8cc|\uc2a4\ub808\ub4dc\s*\uc885\ub8cc|"
    r"\uc774\s*\ub300\ud654\s*\ub05d|\ub300\ud654\ub97c\s*\ub2eb|\ucc44\ud305\uc744\s*\ub2eb",
    re.IGNORECASE,
)
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
class PostmortemEventFeatures:
    """Bounded semantic facts extracted once from one decoded event."""

    payload_type: str = ""
    role: str = ""
    session_id: str = ""
    cwd: str = ""
    goal_status: str = ""
    goal_objective: str = ""
    goal_scope_markers: tuple[str, ...] = ()
    text_present: bool = False
    user_goal_context: bool = False
    user_archive_request: bool = False
    user_stop_request: bool = False
    user_resume_request: bool = False
    work_continuation: bool = False
    resume_session_context: bool = False
    resume_runtime_token: bool = False
    resume_large_bundle: bool = False
    skills: tuple[str, ...] = ()
    token_optimizer_delta: tuple[tuple[str, int], ...] = ()
    reviewer_mention: bool = False
    review_with_fixes: bool = False
    secret_findings: tuple[SecretFinding, ...] = ()
    final_claims_completion: bool = False
    final_mentions_failure: bool = False
    final_scope_markers: tuple[str, ...] = ()
    final_partial_milestone: bool = False
    archive_directive: bool = False
    assistant_self_stop: bool = False
    sample_220: str = ""
    sample_260: str = ""
    call_name: str = ""
    call_token_optimizer_runtime: bool | None = None
    call_resume_session_context: bool = False
    call_resume_runtime_token: bool = False
    call_resume_large_bundle: bool = False
    call_resume_implementation: bool = False
    call_allowed_after_stop: bool = False
    call_spawned: int = 0
    call_closed: int = 0
    call_sample_260: str = ""
    command_token_optimizer_delta: tuple[tuple[str, int], ...] = ()
    git_flags: tuple[str, ...] = ()
    verification_command: str = ""
    output_timeout: bool = False
    output_closed_while_running: bool = False
    verification_failure: tuple[tuple[str, str], ...] = ()
    patch_activity: bool = False
    audit_features: Any = None


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
    token_optimizer_status_reason: str = ""
    token_gate: Dict[str, Any] = field(default_factory=dict)
    token_optimizer_evidence: Dict[str, Any] = field(default_factory=dict)
    subagent_summary: Dict[str, Any] = field(default_factory=dict)
    review_status: str = "pending"
    completion_guard: Dict[str, Any] = field(default_factory=dict)
    verification_claim_guard: Dict[str, Any] = field(default_factory=dict)
    scope_completion_delta: Dict[str, Any] = field(default_factory=dict)
    user_stop_guard: Dict[str, Any] = field(default_factory=dict)
    assistant_stop_guard: Dict[str, Any] = field(default_factory=dict)
    archive_guard: Dict[str, Any] = field(default_factory=dict)
    resume_guard: Dict[str, Any] = field(default_factory=dict)
    secret_findings: List[SecretFinding] = field(default_factory=list)
    input_integrity: Dict[str, Any] = field(default_factory=dict)
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


def find_secret_findings(
    text: str,
    line_number: int,
    *,
    lowered: str | None = None,
) -> List[SecretFinding]:
    findings: List[SecretFinding] = []
    lowered = str(text or "").lower() if lowered is None else lowered
    for kind, pattern in SENSITIVE_PATTERNS:
        if kind == "database_url_password" and not (
            "://" in lowered
            and "@" in lowered
            and any(
                provider in lowered
                for provider in ("postgres", "mysql", "mariadb", "redis", "mongodb")
            )
        ):
            continue
        if kind == "pgpassword" and "pgpassword" not in lowered:
            continue
        if kind == "generic_password" and not any(
            marker in lowered
            for marker in (
                "password",
                "passwd",
                "pwd",
                "token",
                "api_key",
                "api-key",
                "secret",
            )
        ):
            continue
        if pattern.search(text or ""):
            findings.append(
                SecretFinding(
                    line=line_number,
                    kind=kind,
                    redacted_sample=_bounded_redacted_short(text, 260),
                )
            )
    return findings


_TOKEN_OPTIMIZER_EVIDENCE_KEYS = (
    "runtime_calls",
    "skill_doc_reads",
    "explicit_usage_records",
    "explicit_passthrough_records",
    "structured_used_records",
    "considered_not_needed_records",
    "blocked_reason_records",
    "status_mentions",
)


def _empty_token_optimizer_evidence() -> Dict[str, int]:
    return {key: 0 for key in _TOKEN_OPTIMIZER_EVIDENCE_KEYS}


def _counter_delta(values: Dict[str, Any]) -> tuple[tuple[str, int], ...]:
    return tuple(
        (key, int(values.get(key, 0) or 0))
        for key in _TOKEN_OPTIMIZER_EVIDENCE_KEYS
        if int(values.get(key, 0) or 0)
    )


def _merge_counter_delta(
    target: Dict[str, Any],
    delta: tuple[tuple[str, int], ...],
) -> None:
    for key, value in delta:
        target[key] = int(target.get(key, 0) or 0) + int(value)


def _bounded_redacted_short(
    text: str,
    max_length: int,
    *,
    redact: bool = True,
) -> str:
    value = str(text or "")

    def finish(sample: str) -> str:
        bounded = redact_sensitive_text(sample) if redact else sample
        return _bounded_utf8_text(bounded, max_length)

    if len(value) <= 8_192:
        sample = _short(value, max_length)
        return finish(sample)
    pieces: List[str] = []
    retained = 0
    matches = iter(re.finditer(r"\S+", value))
    for match in matches:
        word = match.group(0)
        prefix = " " if pieces else ""
        available = max_length - retained
        addition = prefix + word
        if len(addition) > available:
            pieces.append(addition[:available])
            sample = "".join(pieces) + "..."
            return finish(sample)
        pieces.append(addition)
        retained += len(addition)
        if retained == max_length:
            try:
                next(matches)
            except StopIteration:
                sample = "".join(pieces)
                return finish(sample)
            sample = "".join(pieces) + "..."
            return finish(sample)
    sample = "".join(pieces)
    return finish(sample)


def _scan_literal_hints(
    lowered: str,
    *,
    payload_type: str = "",
    role: str = "",
) -> tuple[int, frozenset[str]]:
    bits = 0
    hits: set[str] = set()
    if len(lowered) <= _SESSION_TEXT_SCAN_REGEX_THRESHOLD:
        for literal in _POSTMORTEM_AUDIT_LITERALS:
            if literal in lowered:
                hits.add(literal)
        if _POSTMORTEM_SKILL_HINT_PATTERN.search(lowered):
            bits |= _HINT_SKILL
        if _POSTMORTEM_TOKEN_HINT_PATTERN.search(lowered):
            bits |= _HINT_TOKEN
        if _POSTMORTEM_REVIEW_HINT_PATTERN.search(lowered):
            bits |= _HINT_REVIEW
        if _POSTMORTEM_SECRET_HINT_PATTERN.search(lowered):
            bits |= _HINT_SECRET
        context = any(
            marker in lowered
            for marker in (
                "session_start_context",
                "build_session_start_context",
                "read_latest_interruption_checkpoint",
            )
        )
        token = any(
            marker in lowered
            for marker in (
                "src.skills.token_optimizer",
                "src.orchestration.runtime_token_optimizer",
                "runtime_token_optimization",
                "estimated_tokens_saved",
                "actual_tokens_saved",
                "summarize_command_output",
                "optimize_workflow_task_results",
                "metadata.token_optimizer",
            )
        )
        bundle = any(
            marker in lowered
            for marker in (
                "large_work_orchestration_bundle",
                "skill_statuses",
                "skill_transition_handoff",
            )
        )
        bits |= _HINT_RESUME_CONTEXT if context else 0
        bits |= _HINT_RESUME_TOKEN if token else 0
        bits |= _HINT_RESUME_BUNDLE if bundle else 0
        if (
            payload_type == "message"
            and role == "user"
            and _POSTMORTEM_SQL_HINT_PATTERN.search(lowered)
        ):
            bits |= _HINT_SQL
        if payload_type == "task_complete":
            bits |= _HINT_COMPLETION
            bits |= _HINT_FAILURE
            bits |= _HINT_SCOPE
            bits |= _HINT_PARTIAL
            bits |= _HINT_ARCHIVE
            bits |= _HINT_SELF_STOP
        if payload_type == "agent_message" or (
            payload_type == "message" and role == "assistant"
        ):
            bits |= _HINT_WORK
    else:
        for match in _POSTMORTEM_LITERAL_PATTERN.finditer(lowered):
            literal = match.group(0)
            hits.add(literal)
            bits |= _POSTMORTEM_LITERAL_HINTS[literal]
    return bits, frozenset(hits)


def _token_optimizer_event_delta(
    text: str,
    *,
    payload_type: str,
    role: str,
    lowered: str,
    hinted: bool = False,
) -> tuple[tuple[str, int], ...]:
    if not text or (
        not hinted and _POSTMORTEM_TOKEN_HINT_PATTERN.search(lowered) is None
    ):
        return ()
    decision_source = _is_token_optimizer_decision_source(
        payload_type,
        role,
        text,
        lowered=lowered,
    )
    runtime_source = _is_token_optimizer_runtime_source(
        payload_type,
        role,
        text,
        lowered=lowered,
    )
    if not decision_source and not runtime_source:
        evidence = _empty_token_optimizer_evidence()
        if re.search(
            r"name:\s*token-optimizer|# Token Optimizer Skill",
            text,
            re.IGNORECASE,
        ):
            evidence["skill_doc_reads"] = 1
            return _counter_delta(evidence)
        if re.search(
            r"token[-_]optimizer|token_optimizer_status",
            text,
            re.IGNORECASE,
        ):
            evidence["status_mentions"] += 1
        if re.search(
            r"token_optimizer[/\\]SKILL\.md|token_optimizer\\SKILL\.md|"
            r"token_optimizer/SKILL\.md",
            text,
            re.IGNORECASE,
        ):
            evidence["skill_doc_reads"] += 1
            return _counter_delta(evidence)
        if re.search(
            r"src\.skills\.token_optimizer|python\s+-m\s+src\.skills\.token_optimizer|"
            r"src\.orchestration\.runtime_token_optimizer|optimize_workflow_task_results|"
            r"runtime_token_optimization|metadata\.token_optimizer|"
            r"summarize_command_output|optimize_context_content|summarize_agent_transcript|"
            r"aggregate_token_usage_stats|compare_token_usage",
            text,
            re.IGNORECASE,
        ):
            evidence["status_mentions"] += 1
        return _counter_delta(evidence)
    evidence = _empty_token_optimizer_evidence()
    _merge_token_optimizer_evidence(
        evidence,
        text,
        payload_type=payload_type,
        role=role,
        lowered=lowered,
    )
    return _counter_delta(evidence)


def extract_postmortem_event_features(
    event: Dict[str, Any],
    line_number: int,
    *,
    audit_extractor: Any = None,
) -> PostmortemEventFeatures:
    """Scan original semantic text once and retain only bounded event facts."""

    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        return PostmortemEventFeatures()
    payload_type = _bounded_utf8_text(
        str(payload.get("type", "")),
        MAX_PAYLOAD_TYPE_BYTES,
    )
    role = _bounded_utf8_text(
        str(payload.get("role", "")),
        MAX_ROLE_BYTES,
    )
    text = _payload_text(payload)
    lowered = text.lower() if text else ""
    hint_bits, literal_hits = (
        _scan_literal_hints(
            lowered,
            payload_type=payload_type,
            role=role,
        )
        if lowered
        else (0, frozenset())
    )
    instruction_context = payload_type == "message" and role in {"developer", "system"}
    audit_features = (
        audit_extractor(
            event,
            payload,
            text,
            lowered,
            literal_hits,
            bool(hint_bits & _HINT_SQL),
        )
        if audit_extractor is not None
        else None
    )

    session_id = ""
    cwd = ""
    if event.get("type") == "session_meta":
        session_id = _bounded_utf8_text(
            str(payload.get("id", "")),
            MAX_POSTMORTEM_SCALAR_BYTES,
        )
        cwd = _bounded_utf8_text(
            str(payload.get("cwd", "")),
            MAX_POSTMORTEM_SCALAR_BYTES,
        )

    goal_status = ""
    goal_objective = ""
    goal_scope_markers: tuple[str, ...] = ()
    if payload_type == "thread_goal_updated":
        goal = payload.get("goal", {}) or {}
        if isinstance(goal, dict):
            goal_status = _bounded_utf8_text(
                str(goal.get("status", "")),
                MAX_GOAL_STATUS_BYTES,
            )
            objective = str(goal.get("objective", ""))
            if objective:
                goal_objective = _bounded_utf8_text(
                    objective,
                    MAX_GOAL_OBJECTIVE_CHARS,
                )
                objective_hints, _ = _scan_literal_hints(
                    objective.lower(),
                    payload_type="task_complete",
                )
                if objective_hints & _HINT_SCOPE:
                    goal_scope_markers = tuple(_scope_markers(objective))

    user_goal_context = False
    user_archive_request = False
    user_stop_request = False
    user_resume_request = False
    if text and payload_type == "message" and role == "user":
        normalized = text.strip()
        user_goal_context = bool(GOAL_CONTEXT_PATTERN.search(normalized))
        user_archive_request = bool(
            normalized and USER_ARCHIVE_REQUEST_PATTERN.search(normalized)
        )
        if normalized and not user_goal_context:
            intent = resolve_request_intent(normalized)
            user_stop_request = intent["conversation_pause_requested"] is True
            user_resume_request = bool(
                not user_stop_request
                and (
                    intent["persistence_requested"] is True
                    or re.match(
                        r"^(?:please\s+)?(?:resume|continue|proceed|go on|restart)\b|"
                        r"^(?:계속|이어서|재개|진행해|다시\s*시작)",
                        normalized,
                        re.IGNORECASE,
                    )
                )
            )

    resume_session_context = False
    resume_runtime_token = False
    resume_large_bundle = False
    if text:
        resume_session_context = bool(hint_bits & _HINT_RESUME_CONTEXT)
        resume_runtime_token = bool(hint_bits & _HINT_RESUME_TOKEN)
        resume_large_bundle = bool(hint_bits & _HINT_RESUME_BUNDLE)

    skills: tuple[str, ...] = ()
    token_optimizer_delta: tuple[tuple[str, int], ...] = ()
    reviewer_mention = False
    review_with_fixes = False
    secret_findings: tuple[SecretFinding, ...] = ()
    if text and not instruction_context:
        if hint_bits & _HINT_SKILL:
            skills = tuple(
                skill
                for skill, pattern in SKILL_PATTERNS.items()
                if any(hint in lowered for hint in SKILL_PATTERN_HINTS[skill])
                and pattern.search(text)
            )
        if (
            payload_type not in {"function_call", "custom_tool_call"}
            and hint_bits & _HINT_TOKEN
        ):
            token_optimizer_delta = _token_optimizer_event_delta(
                text,
                payload_type=payload_type,
                role=role,
                lowered=lowered,
                hinted=bool(hint_bits & _HINT_TOKEN),
            )
        if hint_bits & _HINT_REVIEW:
            reviewer_mention = bool(
                any(
                    marker in lowered
                    for marker in (
                        "spec",
                        "code",
                        "quality",
                        "reviewer",
                        "review",
                        "리뷰어",
                        "검토",
                    )
                )
                and REVIEWER_PATTERN.search(text)
            )
            review_with_fixes = any(
                marker in lowered
                for marker in (
                    "with fixes",
                    "blocking issues",
                    "findings",
                    "critical",
                    "high:",
                )
            )
        if hint_bits & _HINT_SECRET:
            secret_findings = tuple(
                find_secret_findings(text, line_number, lowered=lowered)
            )

    final_claims_completion = False
    final_mentions_failure = False
    final_scope_markers: tuple[str, ...] = ()
    final_partial_milestone = False
    archive_directive = False
    assistant_self_stop = False
    if payload_type == "task_complete" and text:
        if hint_bits & _HINT_COMPLETION:
            final_claims_completion = _claims_completion(text)
        if hint_bits & _HINT_FAILURE:
            final_mentions_failure = bool(FAILURE_PATTERN.search(text))
        if hint_bits & _HINT_SCOPE:
            final_scope_markers = tuple(_scope_markers(text))
        if hint_bits & _HINT_PARTIAL:
            final_partial_milestone = _mentions_partial_milestone(text)
        if hint_bits & _HINT_ARCHIVE:
            archive_directive = bool(ARCHIVE_DIRECTIVE_PATTERN.search(text))
        if hint_bits & _HINT_SELF_STOP:
            assistant_self_stop = _claims_assistant_self_stop(text)

    call_name = ""
    call_token_optimizer_runtime: bool | None = None
    call_resume_session_context = False
    call_resume_runtime_token = False
    call_resume_large_bundle = False
    call_resume_implementation = False
    call_allowed_after_stop = False
    call_spawned = 0
    call_closed = 0
    command_token_optimizer_delta: tuple[tuple[str, int], ...] = ()
    git_flags: tuple[str, ...] = ()
    verification_command = ""
    call_sample_260 = ""
    if payload_type in {"function_call", "custom_tool_call"}:
        call_name = _bounded_utf8_text(
            str(payload.get("name", "")),
            MAX_CALL_NAME_BYTES,
        )
        raw_arguments = payload.get("arguments") or payload.get("input")
        arguments = _parse_arguments(raw_arguments)
        command = str(arguments.get("command", ""))
        call_text = command or str(raw_arguments or "")
        call_lowered = lowered if call_text == text else call_text.lower()
        call_token_optimizer_runtime = _is_token_optimizer_runtime_command(
            call_lowered
        )
        call_resume_session_context = bool(hint_bits & _HINT_RESUME_CONTEXT)
        call_resume_runtime_token = bool(hint_bits & _HINT_RESUME_TOKEN)
        call_resume_large_bundle = bool(hint_bits & _HINT_RESUME_BUNDLE)
        call_resume_implementation = _is_resume_implementation_tool(
            call_name,
            call_text,
        )
        call_allowed_after_stop = _is_allowed_after_stop_tool(call_name, command)
        call_sample_260 = _bounded_redacted_short(
            call_text,
            260,
            redact=bool(hint_bits & _HINT_SECRET),
        )
        if _tool_name_matches(call_name, {"spawn_agent", "create_agent"}):
            call_spawned += 1
        elif _tool_name_matches(call_name, {"close_agent", "finish_agent"}):
            call_closed += 1
        for wrapped_name in _wrapped_tool_names(arguments):
            if _tool_name_matches(wrapped_name, {"spawn_agent", "create_agent"}):
                call_spawned += 1
            elif _tool_name_matches(wrapped_name, {"close_agent", "finish_agent"}):
                call_closed += 1
        if command:
            command_token_optimizer_delta = _token_optimizer_event_delta(
                command,
                payload_type=payload_type,
                role=role,
                lowered=call_lowered,
                hinted=bool(hint_bits & _HINT_TOKEN),
            )
            command_git_state = {
                "status_checked": False,
                "staged": False,
                "committed": False,
                "pushed": False,
                "remote_checked": False,
                "branch_checked": False,
            }
            _update_git_state(command_git_state, command)
            git_flags = tuple(
                key for key, enabled in command_git_state.items() if enabled
            )
            if _is_verification_command(command):
                verification_command = _bounded_utf8_text(
                    command,
                    MAX_VERIFICATION_COMMAND_CHARS,
                )
                verification_command = redact_sensitive_text(
                    verification_command
                )
                verification_command = _bounded_utf8_text(
                    verification_command,
                    MAX_VERIFICATION_COMMAND_CHARS,
                )

    output_timeout = False
    output_closed_while_running = False
    verification_failure: tuple[tuple[str, str], ...] = ()
    if payload_type in {"function_call_output", "custom_tool_call_output"}:
        output_timeout = _payload_has_timeout(payload, lowered_output=lowered)
        output_closed_while_running = bool(
            '"previous_status":"running"' in text
            or "'previous_status': 'running'" in text
        )
        failure = _verification_failure_from_output(text, lowered=lowered)
        if failure:
            verification_failure = tuple(
                (str(key), str(value)) for key, value in failure.items()
            )

    sample_260 = (
        _bounded_redacted_short(
            text,
            260,
            redact=bool(hint_bits & _HINT_SECRET),
        )
        if text
        else ""
    )
    sample_220 = _bounded_utf8_text(sample_260, 220)
    return PostmortemEventFeatures(
        payload_type=payload_type,
        role=role,
        session_id=session_id,
        cwd=cwd,
        goal_status=goal_status,
        goal_objective=goal_objective,
        goal_scope_markers=goal_scope_markers,
        text_present=bool(text),
        user_goal_context=user_goal_context,
        user_archive_request=user_archive_request,
        user_stop_request=user_stop_request,
        user_resume_request=user_resume_request,
        work_continuation=bool(
            text
            and (
                payload_type == "agent_message"
                or (payload_type == "message" and role == "assistant")
            )
            and hint_bits & _HINT_WORK
            and _is_work_continuation_message(text)
        ),
        resume_session_context=resume_session_context,
        resume_runtime_token=resume_runtime_token,
        resume_large_bundle=resume_large_bundle,
        skills=skills,
        token_optimizer_delta=token_optimizer_delta,
        reviewer_mention=reviewer_mention,
        review_with_fixes=review_with_fixes,
        secret_findings=secret_findings,
        final_claims_completion=final_claims_completion,
        final_mentions_failure=final_mentions_failure,
        final_scope_markers=final_scope_markers,
        final_partial_milestone=final_partial_milestone,
        archive_directive=archive_directive,
        assistant_self_stop=assistant_self_stop,
        sample_220=sample_220,
        sample_260=sample_260,
        call_name=call_name,
        call_token_optimizer_runtime=call_token_optimizer_runtime,
        call_resume_session_context=call_resume_session_context,
        call_resume_runtime_token=call_resume_runtime_token,
        call_resume_large_bundle=call_resume_large_bundle,
        call_resume_implementation=call_resume_implementation,
        call_allowed_after_stop=call_allowed_after_stop,
        call_spawned=call_spawned,
        call_closed=call_closed,
        call_sample_260=call_sample_260,
        command_token_optimizer_delta=command_token_optimizer_delta,
        git_flags=git_flags,
        verification_command=verification_command,
        output_timeout=output_timeout,
        output_closed_while_running=output_closed_while_running,
        verification_failure=verification_failure,
        patch_activity=payload_type in {"patch_apply_end", "patch_apply_begin"},
        audit_features=audit_features,
    )


def analyze_codex_session_jsonl(
    session_path: str | Path,
    *,
    token_threshold: int = 50_000,
    context_ratio_threshold: float = 0.50,
    max_secret_findings: int = 20,
    max_verification_commands: int = 20,
    event_stream: Iterable[Any] | None = None,
) -> SessionPostmortem:
    """Build a quality-first postmortem from a Codex Desktop rollout JSONL file."""
    path = Path(session_path)
    session_id = ""
    cwd = ""
    line_count = 0
    skills = set()
    token_info = _empty_token_gate(token_threshold, context_ratio_threshold)
    token_optimizer_evidence = _empty_token_optimizer_evidence()
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
        "latest_objective_markers": [],
        "active_updates": 0,
        "complete_updates": 0,
        "terminal_updates": 0,
    }
    stop_state = {
        "request_count": 0,
        "latest_stop_line": 0,
        "resume_signal_count": 0,
        "goal_context_after_stop": 0,
        "active_goal_updates_after_stop": 0,
        "terminal_goal_updates_after_stop": 0,
        "latest_goal_status_after_stop": "",
        "continued_tool_call_count": 0,
        "continued_tool_call_samples": [],
        "continued_work_message_count": 0,
        "continued_work_message_samples": [],
    }
    assistant_stop_state = {
        "event_count": 0,
        "event_samples": [],
        "active_event_count": 0,
        "active_event_samples": [],
    }
    archive_state = {
        "directive_count": 0,
        "latest_directive_line": 0,
        "directive_samples": [],
        "user_request_count": 0,
        "user_request_samples": [],
    }
    resume_state = {
        "request_count": 0,
        "latest_resume_line": 0,
        "session_start_context_after_resume": 0,
        "runtime_token_evidence_after_resume": 0,
        "large_work_bundle_after_resume": 0,
        "implementation_tool_count": 0,
        "implementation_tool_samples": [],
    }
    active_stop_line = 0
    active_resume_line = 0
    task_complete_count = 0
    final_message_state = {
        "claims_completion": False,
        "mentions_failure": False,
        "scope_markers": set(),
        "partial_milestone_claimed": False,
    }
    verification_failure_state = {
        "count": 0,
        "samples": [],
    }
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
    last_tool_call_was_token_optimizer_runtime: bool | None = None
    input_integrity = {
        "status": "passed",
        "read_strategy": "single_pass_streaming",
        "stream_passes": 1,
        "temporary_artifacts_created": 0,
        "valid_event_count": 0,
        "malformed_line_count": 0,
        "malformed_lines": [],
        "duplicate_key_count": 0,
        "duplicate_key_line_count": 0,
        "duplicate_key_lines": [],
        "invalid_event_count": 0,
        "invalid_event_lines": [],
    }

    for (
        line_number,
        line,
        event,
        duplicate_keys,
        parse_error,
        event_features,
    ) in _iter_postmortem_records(
        path,
        event_stream,
    ):
        if not line or line.isspace():
            continue
        line_count += 1
        if parse_error:
            input_integrity["malformed_line_count"] += 1
            if len(input_integrity["malformed_lines"]) < MAX_INTEGRITY_SAMPLES:
                input_integrity["malformed_lines"].append(
                    _integrity_line_record(line_number, line, error=parse_error)
                )
            continue

        if duplicate_keys:
            input_integrity["duplicate_key_count"] += len(duplicate_keys)
            input_integrity["duplicate_key_line_count"] += 1
            if len(input_integrity["duplicate_key_lines"]) < MAX_INTEGRITY_SAMPLES:
                record = _integrity_line_record(line_number, line)
                record["keys"] = _ordered_unique(
                    _bounded_utf8_text(key, 160) for key in duplicate_keys
                )[:20]
                input_integrity["duplicate_key_lines"].append(record)
            continue

        if not isinstance(event, dict):
            input_integrity["invalid_event_count"] += 1
            if len(input_integrity["invalid_event_lines"]) < MAX_INTEGRITY_SAMPLES:
                record = _integrity_line_record(line_number, line)
                record["root_type"] = type(event).__name__
                input_integrity["invalid_event_lines"].append(record)
            continue

        input_integrity["valid_event_count"] += 1

        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue

        features = event_features
        if not isinstance(features, PostmortemEventFeatures):
            features = extract_postmortem_event_features(event, line_number)

        if event.get("type") == "session_meta":
            session_id = features.session_id
            cwd = features.cwd

        payload_type = features.payload_type
        message_role = features.role
        instruction_context = payload_type == "message" and message_role in {
            "developer",
            "system",
        }

        if payload_type == "thread_goal_updated":
            status = features.goal_status
            if status:
                goal_state["latest_status"] = status
                if status == "active":
                    goal_state["active_updates"] += 1
                elif status == "complete":
                    goal_state["complete_updates"] += 1
                    goal_state["terminal_updates"] += 1
                elif status == "blocked":
                    goal_state["terminal_updates"] += 1
            if features.goal_objective:
                goal_state["latest_objective"] = features.goal_objective
                goal_state["latest_objective_markers"] = list(
                    features.goal_scope_markers
                )
            if active_stop_line:
                if status:
                    stop_state["latest_goal_status_after_stop"] = status
                if status == "active":
                    stop_state["active_goal_updates_after_stop"] += 1
                elif status in {"blocked", "complete"}:
                    stop_state["terminal_goal_updates_after_stop"] += 1

        if payload_type == "task_complete":
            task_complete_count += 1
            final_message_state["claims_completion"] = bool(
                final_message_state["claims_completion"]
                or features.final_claims_completion
            )
            final_message_state["mentions_failure"] = bool(
                final_message_state["mentions_failure"]
                or features.final_mentions_failure
            )
            final_message_state["partial_milestone_claimed"] = bool(
                final_message_state["partial_milestone_claimed"]
                or features.final_partial_milestone
            )
            final_message_state["scope_markers"].update(
                features.final_scope_markers
            )
            if features.archive_directive:
                archive_state["directive_count"] += 1
                archive_state["latest_directive_line"] = line_number
                _append_bounded_sample(
                    archive_state,
                    "directive_samples",
                    {"line": line_number, "sample": features.sample_260},
                    MAX_ARCHIVE_SAMPLES,
                )
            if features.assistant_self_stop:
                stop_event = {
                    "line": line_number,
                    "goal_status_at_stop": str(goal_state.get("latest_status", "")),
                    "sample": features.sample_260,
                }
                assistant_stop_state["event_count"] += 1
                _append_bounded_sample(
                    assistant_stop_state,
                    "event_samples",
                    stop_event,
                    MAX_ASSISTANT_STOP_SAMPLES,
                )
                if stop_event["goal_status_at_stop"] == "active":
                    assistant_stop_state["active_event_count"] += 1
                    _append_bounded_sample(
                        assistant_stop_state,
                        "active_event_samples",
                        stop_event,
                        MAX_ASSISTANT_STOP_SAMPLES,
                    )

        if payload_type not in {
            "function_call",
            "custom_tool_call",
            "function_call_output",
            "custom_tool_call_output",
        }:
            last_tool_call_was_token_optimizer_runtime = None

        if features.text_present and not instruction_context:
            if payload_type == "message" and message_role == "user":
                if features.user_goal_context:
                    if active_stop_line:
                        stop_state["goal_context_after_stop"] += 1
                elif features.user_archive_request:
                    archive_state["user_request_count"] += 1
                    _append_bounded_sample(
                        archive_state,
                        "user_request_samples",
                        {"line": line_number, "sample": features.sample_220},
                        MAX_ARCHIVE_SAMPLES,
                    )
                elif features.user_stop_request:
                    active_stop_line = line_number
                    stop_state["request_count"] += 1
                    stop_state["latest_stop_line"] = line_number
                elif active_stop_line and features.user_resume_request:
                    stop_state["resume_signal_count"] += 1
                    resume_state["request_count"] += 1
                    resume_state["latest_resume_line"] = line_number
                    active_resume_line = line_number
                    active_stop_line = 0
                elif features.user_resume_request:
                    resume_state["request_count"] += 1
                    resume_state["latest_resume_line"] = line_number
                    active_resume_line = line_number

            if active_stop_line and (
                payload_type == "agent_message"
                or (payload_type == "message" and message_role == "assistant")
            ) and features.work_continuation:
                stop_state["continued_work_message_count"] += 1
                _append_bounded_sample(
                    stop_state,
                    "continued_work_message_samples",
                    {"line": line_number, "sample": features.sample_260},
                    MAX_GUARD_SAMPLES,
                )
            if active_resume_line:
                resume_state["session_start_context_after_resume"] += int(
                    features.resume_session_context
                )
                resume_state["runtime_token_evidence_after_resume"] += int(
                    features.resume_runtime_token
                )
                resume_state["large_work_bundle_after_resume"] += int(
                    features.resume_large_bundle
                )

            skills.update(features.skills)
            token_output_allowed = (
                payload_type
                not in {"function_call_output", "custom_tool_call_output"}
                or last_tool_call_was_token_optimizer_runtime is not False
            )
            if token_output_allowed:
                _merge_counter_delta(
                    token_optimizer_evidence,
                    features.token_optimizer_delta,
                )
            if features.reviewer_mention:
                subagents["reviewer_mentions"] += 1
            if features.review_with_fixes:
                review_with_fixes = True
            if len(secret_findings) < max_secret_findings:
                secret_findings.extend(
                    list(features.secret_findings)[
                        : max_secret_findings - len(secret_findings)
                    ]
                )

        if payload_type == "token_count":
            _merge_token_gate(
                token_info,
                payload,
                token_threshold,
                context_ratio_threshold,
            )
            continue

        if payload_type in {"function_call", "custom_tool_call"}:
            last_tool_call_was_token_optimizer_runtime = (
                features.call_token_optimizer_runtime
            )
            if active_resume_line:
                resume_state["session_start_context_after_resume"] += int(
                    features.call_resume_session_context
                )
                resume_state["runtime_token_evidence_after_resume"] += int(
                    features.call_resume_runtime_token
                )
                resume_state["large_work_bundle_after_resume"] += int(
                    features.call_resume_large_bundle
                )
                if features.call_resume_implementation:
                    resume_state["implementation_tool_count"] += 1
                    _append_bounded_sample(
                        resume_state,
                        "implementation_tool_samples",
                        {
                            "line": line_number,
                            "name": features.call_name,
                            "command": features.call_sample_260,
                        },
                        MAX_GUARD_SAMPLES,
                    )
            if active_stop_line and not features.call_allowed_after_stop:
                stop_state["continued_tool_call_count"] += 1
                _append_bounded_sample(
                    stop_state,
                    "continued_tool_call_samples",
                    {
                        "line": line_number,
                        "name": features.call_name,
                        "command": features.call_sample_260,
                    },
                    MAX_GUARD_SAMPLES,
                )
            subagents["spawned"] += features.call_spawned
            subagents["closed"] += features.call_closed
            _merge_counter_delta(
                token_optimizer_evidence,
                features.command_token_optimizer_delta,
            )
            for key in features.git_flags:
                git_state[key] = True
            if (
                features.verification_command
                and len(verification_commands) < max_verification_commands
            ):
                verification_commands.append(features.verification_command)
            continue

        if active_stop_line and features.patch_activity:
            stop_state["continued_tool_call_count"] += 1
            _append_bounded_sample(
                stop_state,
                "continued_tool_call_samples",
                {
                    "line": line_number,
                    "name": payload_type,
                    "command": features.sample_260 or payload_type,
                },
                MAX_GUARD_SAMPLES,
            )

        if payload_type in {"function_call_output", "custom_tool_call_output"}:
            if features.output_timeout:
                subagents["timed_out"] += 1
            if features.output_closed_while_running:
                subagents["closed_while_running"] += 1
            if features.verification_failure:
                verification_failure_state["count"] += 1
                _append_bounded_sample(
                    verification_failure_state,
                    "samples",
                    {"line": line_number, **dict(features.verification_failure)},
                    MAX_VERIFICATION_FAILURE_SAMPLES,
                )
            last_tool_call_was_token_optimizer_runtime = None

    integrity_issue_count = (
        int(input_integrity["malformed_line_count"])
        + int(input_integrity["duplicate_key_count"])
        + int(input_integrity["invalid_event_count"])
    )
    input_integrity["status"] = "with_issues" if integrity_issue_count else "passed"
    input_integrity["issue_count"] = integrity_issue_count

    _merge_subagent_token_gate(token_info, subagents)
    token_status = _token_optimizer_status(token_info, token_optimizer_evidence)
    token_status_reason = _token_optimizer_status_reason(token_status, token_info, token_optimizer_evidence)
    review_status = _derive_review_status(subagents, review_with_fixes)
    completion_guard = _build_completion_guard(goal_state, task_complete_count, final_message_state)
    verification_claim_guard = _build_verification_claim_guard(
        verification_failure_state,
        final_message_state,
    )
    scope_completion_delta = _build_scope_completion_delta(goal_state, final_message_state)
    user_stop_guard = _build_user_stop_guard(stop_state, goal_state)
    assistant_stop_guard = _build_assistant_stop_guard(
        goal_state,
        task_complete_count,
        [],
        assistant_stop_state,
    )
    archive_guard = _build_archive_guard(archive_state)
    resume_guard = _build_resume_guard(resume_state, token_info)
    actions = _recommended_actions(
        token_status=token_status,
        token_optimizer_evidence=token_optimizer_evidence,
        review_status=review_status,
        completion_guard=completion_guard,
        verification_claim_guard=verification_claim_guard,
        scope_completion_delta=scope_completion_delta,
        user_stop_guard=user_stop_guard,
        assistant_stop_guard=assistant_stop_guard,
        archive_guard=archive_guard,
        resume_guard=resume_guard,
        secret_findings=secret_findings,
        git_state=git_state,
        subagents=subagents,
    )
    if input_integrity["status"] != "passed":
        actions.append(
            "Treat malformed JSONL lines, duplicate JSON keys, and invalid root events as input-integrity findings before relying on the postmortem."
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
        "assistant_stop_guard",
        "archive_guard",
        "resume_guard",
        "secret_redaction_scan",
        "input_integrity",
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
        token_optimizer_status_reason=token_status_reason,
        token_gate=token_info,
        token_optimizer_evidence=token_optimizer_evidence,
        subagent_summary=subagents,
        review_status=review_status,
        completion_guard=completion_guard,
        verification_claim_guard=verification_claim_guard,
        scope_completion_delta=scope_completion_delta,
        user_stop_guard=user_stop_guard,
        assistant_stop_guard=assistant_stop_guard,
        archive_guard=archive_guard,
        resume_guard=resume_guard,
        secret_findings=secret_findings[:max_secret_findings],
        input_integrity=input_integrity,
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
        f"Token optimizer reason: {postmortem.token_optimizer_status_reason or '<unknown>'}",
        f"Review: {postmortem.review_status}",
        f"Completion guard: {postmortem.completion_guard.get('status', 'unknown')}",
        f"Verification guard: {postmortem.verification_claim_guard.get('status', 'unknown')}",
        f"User stop guard: {postmortem.user_stop_guard.get('status', 'unknown')}",
        f"Assistant stop guard: {postmortem.assistant_stop_guard.get('status', 'unknown')}",
        f"Archive guard: {postmortem.archive_guard.get('status', 'unknown')}",
        f"Resume guard: {postmortem.resume_guard.get('status', 'unknown')}",
        (
            "Input integrity: "
            f"{postmortem.input_integrity.get('status', 'unknown')} "
            f"({postmortem.input_integrity.get('issue_count', 0)} issues)"
        ),
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
        "cumulative_threshold_tokens": max(token_threshold * 4, token_threshold),
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
    cumulative_threshold = int(token_gate.get("cumulative_threshold_tokens", token_threshold * 4) or token_threshold * 4)
    if total_tokens >= cumulative_threshold and ratio >= (context_ratio_threshold / 2):
        token_gate["required"] = True
        _append_unique(token_gate["reasons"], "cumulative_tokens_above_threshold")
    if ratio >= context_ratio_threshold:
        token_gate["required"] = True
        _append_unique(token_gate["reasons"], "context_ratio_above_threshold")


def _merge_subagent_token_gate(token_gate: Dict[str, Any], subagents: Dict[str, Any]) -> None:
    if int(subagents.get("spawned", 0) or 0) <= 0:
        return
    token_gate["required"] = True
    _append_unique(token_gate["reasons"], "subagent_transcripts_require_token_decision")


def _token_optimizer_status(token_gate: Dict[str, Any], evidence: Dict[str, Any]) -> str:
    if evidence.get("structured_used_records") or evidence.get("explicit_usage_records"):
        return "used"
    if evidence.get("explicit_passthrough_records"):
        return "passthrough"
    if evidence.get("blocked_reason_records"):
        return "blocked"
    if evidence.get("considered_not_needed_records"):
        return "considered_not_needed"
    if evidence.get("runtime_calls"):
        return "blocked"
    if token_gate.get("required"):
        return "blocked"
    return "considered_not_needed"


def _token_optimizer_status_reason(
    status: str,
    token_gate: Dict[str, Any],
    evidence: Dict[str, Any],
) -> str:
    if status == "used":
        return "Token optimizer used; runtime optimizer evidence or token-savings telemetry was recorded."
    if status == "passthrough":
        return "Token optimizer not used because explicit passthrough evidence was recorded for quality-sensitive content."
    if status == "blocked":
        if evidence.get("runtime_calls") and not any(
            evidence.get(key)
            for key in [
                "structured_used_records",
                "explicit_usage_records",
                "explicit_passthrough_records",
                "blocked_reason_records",
                "considered_not_needed_records",
            ]
        ):
            return (
                "Token optimizer not used because a runtime optimizer call was observed, "
                "but no structured used/passthrough/blocked/considered_not_needed record "
                "with token telemetry or not-used rationale was recorded."
            )
        if evidence.get("skill_doc_reads") and not evidence.get("runtime_calls"):
            return "Token optimizer not used because only the skill documentation was read; no runtime optimizer or passthrough evidence was recorded."
        if evidence.get("blocked_reason_records"):
            return "Token optimizer not used because a blocked/fallback reason was recorded, but no recovery, runtime optimizer, or passthrough evidence was recorded."
        if token_gate.get("required"):
            reasons = ", ".join(
                _token_gate_reason_label(str(reason))
                for reason in token_gate.get("reasons", [])
                if reason
            )
            suffix = f" Token gate reasons: {reasons}." if reasons else ""
            return (
                "Token optimizer not used even though the token gate was required; "
                "no runtime optimizer or passthrough evidence was recorded."
                + suffix
            )
        return "Token optimizer not used because no valid runtime optimizer or passthrough evidence was recorded."
    if evidence.get("considered_not_needed_records"):
        return "Token optimizer not used because explicit considered_not_needed evidence and not-used rationale were recorded."
    if evidence.get("runtime_calls"):
        return (
            "Token optimizer runtime was observed, but it did not include structured usage telemetry; "
            "treated as considered_not_needed because the token gate was not required."
        )
    return "Token optimizer not used because the token gate was checked and optimization was not needed for this session."


def _tool_name_matches(name: str, expected: set[str]) -> bool:
    normalized = str(name or "").strip().lower()
    if normalized in expected:
        return True
    tail = re.split(r"[.:]", normalized)[-1]
    return tail in expected


def _wrapped_tool_names(arguments: Dict[str, Any]) -> List[str]:
    tool_uses = arguments.get("tool_uses")
    if not isinstance(tool_uses, list):
        return []
    names: List[str] = []
    for item in tool_uses:
        if not isinstance(item, dict):
            continue
        name = item.get("recipient_name") or item.get("name") or item.get("tool_name")
        if name:
            names.append(str(name))
    return names


def _token_gate_reason_label(reason: str) -> str:
    labels = {
        "subagent_transcripts_require_token_decision": "a subagent was spawned, but no token optimizer decision was recorded for its packet or transcript",
        "cumulative_tokens_above_threshold": "cumulative token usage crossed the configured threshold",
        "context_ratio_above_threshold": "the last input approached the model context threshold",
    }
    return labels.get(reason, reason)


def _merge_token_optimizer_evidence(
    evidence: Dict[str, Any],
    text: str,
    *,
    payload_type: str = "",
    role: str = "",
    lowered: str | None = None,
) -> None:
    if not text:
        return
    lowered = text.lower() if lowered is None else lowered
    if not any(
        marker in lowered
        for marker in (
            "token",
            "summarize_command_output",
            "optimize_context_content",
            "summarize_agent_transcript",
            "compare_token_usage",
            "aggregate_token_usage_stats",
            "optimize_workflow_task_results",
        )
    ):
        return
    if re.search(r"name:\s*token-optimizer|# Token Optimizer Skill", text, re.IGNORECASE):
        evidence["skill_doc_reads"] = int(evidence.get("skill_doc_reads", 0)) + 1
        return
    if re.search(r"token[-_]optimizer|token_optimizer_status", text, re.IGNORECASE):
        evidence["status_mentions"] = int(evidence.get("status_mentions", 0)) + 1
    structured_status = _structured_token_optimizer_status(text)
    decision_source = _is_token_optimizer_decision_source(
        payload_type,
        role,
        text,
        lowered=lowered,
    )
    runtime_source = _is_token_optimizer_runtime_source(
        payload_type,
        role,
        text,
        lowered=lowered,
    )
    structured_counted = bool(structured_status and (decision_source or runtime_source))
    if structured_counted and structured_status == "used":
        evidence["structured_used_records"] = int(evidence.get("structured_used_records", 0)) + 1
    elif structured_counted and structured_status == "passthrough":
        evidence["explicit_passthrough_records"] = int(evidence.get("explicit_passthrough_records", 0)) + 1
    elif structured_counted and structured_status == "blocked":
        evidence["blocked_reason_records"] = int(evidence.get("blocked_reason_records", 0)) + 1
    elif (
        structured_counted
        and structured_status == "considered_not_needed"
        and _has_token_not_used_reason(text)
    ):
        evidence["considered_not_needed_records"] = int(evidence.get("considered_not_needed_records", 0)) + 1
    if structured_status != "passthrough" and decision_source and re.search(
        r"token_optimizer_status\s*[:=]\s*['\"]?passthrough|status\s*[:=]\s*['\"]?passthrough|contract-sensitive|raw passthrough",
        text,
        re.IGNORECASE,
    ):
        evidence["explicit_passthrough_records"] = int(evidence.get("explicit_passthrough_records", 0)) + 1
    if structured_status != "blocked" and decision_source and re.search(
        r"token_optimizer_status\s*[:=]\s*['\"]?blocked|blocked_reason|fallback_reason|provider_unavailable|unavailable",
        text,
        re.IGNORECASE,
    ):
        evidence["blocked_reason_records"] = int(evidence.get("blocked_reason_records", 0)) + 1
    if re.search(r"token_optimizer[/\\]SKILL\.md|token_optimizer\\SKILL\.md|token_optimizer/SKILL\.md", text, re.IGNORECASE):
        evidence["skill_doc_reads"] = int(evidence.get("skill_doc_reads", 0)) + 1
        return
    runtime_evidence = bool(
        re.search(
            r"src\.skills\.token_optimizer|python\s+-m\s+src\.skills\.token_optimizer|"
            r"src\.orchestration\.runtime_token_optimizer|optimize_workflow_task_results|"
            r"runtime_token_optimization|metadata\.token_optimizer|"
            r"summarize_command_output|optimize_context_content|summarize_agent_transcript|"
            r"aggregate_token_usage_stats|compare_token_usage",
            text,
            re.IGNORECASE,
        )
    )
    explicit_usage = bool(
        re.search(
            r"token_savings_ratio|estimated_tokens_saved|without_token_optimizer|with_token_optimizer|"
            r"actual_token_savings_ratio|actual_tokens_saved|actual_without_token_optimizer|"
            r"actual_with_token_optimizer|actual_usage_scope|actual_usage",
            text,
            re.IGNORECASE,
        )
    )
    if runtime_evidence and runtime_source:
        evidence["runtime_calls"] = int(evidence.get("runtime_calls", 0)) + 1
    elif runtime_evidence:
        evidence["status_mentions"] = int(evidence.get("status_mentions", 0)) + 1
    if explicit_usage and runtime_source and structured_status in {"", "used"}:
        evidence["explicit_usage_records"] = int(evidence.get("explicit_usage_records", 0)) + 1




def _structured_token_optimizer_status(text: str) -> str:
    data = _parse_json_object_from_text(text)
    if not isinstance(data, dict):
        return ""
    statuses: List[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered_key = str(key).lower()
                if lowered_key in {"status", "token_optimizer_status"}:
                    candidate = str(child).strip()
                    if candidate in {"used", "passthrough", "blocked", "considered_not_needed"}:
                        statuses.append(candidate)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    for preferred in ["used", "passthrough", "blocked", "considered_not_needed"]:
        if preferred in statuses:
            return preferred
    return ""


def _has_token_not_used_reason(text: str) -> bool:
    data = _parse_json_object_from_text(text)
    if not isinstance(data, dict):
        return False

    def visit(value: Any) -> bool:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered_key = str(key).lower()
                if lowered_key == "not_used_reason" and str(child).strip():
                    return True
                if visit(child):
                    return True
        elif isinstance(value, list):
            return any(visit(child) for child in value)
        return False

    return visit(data)


def _parse_json_object_from_text(text: str) -> Dict[str, Any] | None:
    raw = str(text or "").strip()
    if not raw or "{" not in raw or "}" not in raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _is_token_optimizer_decision_source(
    payload_type: str,
    role: str = "",
    text: str = "",
    *,
    lowered: str | None = None,
) -> bool:
    payload_type = str(payload_type)
    role = str(role).lower()
    lowered = str(text).lower() if lowered is None else lowered
    if payload_type in {"function_call_output", "custom_tool_call_output", "thread_goal_updated"}:
        return _looks_like_token_optimizer_decision_output(lowered)
    if payload_type in {"function_call", "custom_tool_call"}:
        return _is_token_optimizer_runtime_command(lowered)
    if payload_type in {"message", "agent_message"} and role in {"assistant", "agent"}:
        return False
    return False

def _is_token_optimizer_runtime_source(
    payload_type: str,
    role: str = "",
    text: str = "",
    *,
    lowered: str | None = None,
) -> bool:
    payload_type = str(payload_type)
    role = str(role).lower()
    lowered = str(text).lower() if lowered is None else lowered
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


def _looks_like_token_optimizer_decision_output(lowered: str) -> bool:
    if _looks_like_token_optimizer_runtime_output(lowered):
        return True
    if "{" not in lowered or "}" not in lowered:
        return False
    if "token_optimizer_status" not in lowered and "token_optimizer" not in lowered:
        return False
    return any(
        marker in lowered
        for marker in [
            "passthrough_reason",
            "fallback_reason",
            "blocked_reason",
            "provider_unavailable",
            "token_optimizer_provider",
            '"provider"',
            "'provider'",
            '"strategy"',
            "'strategy'",
            "quality_rationale",
            "decision_source",
        ]
    )


def _merge_resume_guard_evidence(resume_state: Dict[str, Any], text: str) -> None:
    if not text:
        return
    if re.search(r"session_start_context|build_session_start_context|read_latest_interruption_checkpoint", text, re.IGNORECASE):
        resume_state["session_start_context_after_resume"] = int(
            resume_state.get("session_start_context_after_resume", 0)
        ) + 1
    if re.search(
        r"src\.skills\.token_optimizer|src\.orchestration\.runtime_token_optimizer|"
        r"runtime_token_optimization|estimated_tokens_saved|actual_tokens_saved|summarize_command_output|"
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
        goal_state["latest_objective"] = _bounded_text(objective, MAX_GOAL_OBJECTIVE_CHARS)
        goal_state["latest_objective_markers"] = _scope_markers(objective)


def _merge_final_message_state(state: Dict[str, Any], message: str) -> None:
    """Retain only final-message facts needed by the public result guards."""
    text = str(message or "")
    state["claims_completion"] = bool(state.get("claims_completion")) or _claims_completion(text)
    state["mentions_failure"] = bool(state.get("mentions_failure")) or bool(
        FAILURE_PATTERN.search(text)
    )
    state["partial_milestone_claimed"] = bool(
        state.get("partial_milestone_claimed")
    ) or _mentions_partial_milestone(text)
    markers = state.setdefault("scope_markers", set())
    markers.update(_scope_markers(text))


def _append_bounded_sample(
    state: Dict[str, Any],
    key: str,
    sample: Dict[str, Any],
    limit: int,
) -> None:
    samples = state[key]
    if len(samples) < limit:
        samples.append(sample)


def _build_completion_guard(
    goal_state: Dict[str, Any],
    task_complete_count: int,
    final_message_state: Dict[str, Any],
) -> Dict[str, Any]:
    latest_status = str(goal_state.get("latest_status", ""))
    final_claims_completion = bool(final_message_state.get("claims_completion"))
    active_task_complete = latest_status == "active" and task_complete_count > 0
    non_complete_claim = bool(latest_status != "complete" and final_claims_completion)
    blocked = active_task_complete or non_complete_claim
    reasons: List[str] = []
    if active_task_complete:
        reasons.append("task_complete_emitted_while_goal_active")
    if non_complete_claim:
        reasons.append("completion_claim_emitted_while_goal_not_complete")
    return {
        "status": "blocked" if blocked else "passed",
        "latest_goal_status": latest_status,
        "task_complete_count": task_complete_count,
        "final_claims_completion": final_claims_completion,
        "reasons": reasons,
    }


def _build_verification_claim_guard(
    verification_failure_state: Dict[str, Any],
    final_message_state: Dict[str, Any],
) -> Dict[str, Any]:
    final_mentions_failure = bool(final_message_state.get("mentions_failure"))
    failure_count = int(verification_failure_state.get("count", 0) or 0)
    failure_samples = list(verification_failure_state.get("samples", []) or [])
    return {
        "status": "blocked" if failure_count and not final_mentions_failure else "passed",
        "failed_verification_count": failure_count,
        "final_report_mentions_failure": final_mentions_failure,
        "failures": failure_samples,
    }


def _build_scope_completion_delta(
    goal_state: Dict[str, Any],
    final_message_state: Dict[str, Any],
) -> Dict[str, Any]:
    objective_markers = list(goal_state.get("latest_objective_markers", []) or [])
    observed_markers = set(final_message_state.get("scope_markers", set()) or set())
    completed_markers = [
        marker for marker in SCOPE_MARKER_PATTERNS if marker in observed_markers
    ]
    missing = [marker for marker in objective_markers if marker not in completed_markers]
    partial_only = bool(missing and final_message_state.get("partial_milestone_claimed"))
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
    request_count = int(stop_state.get("request_count", 0) or 0)
    continued_tool_call_count = int(stop_state.get("continued_tool_call_count", 0) or 0)
    continued_work_message_count = int(
        stop_state.get("continued_work_message_count", 0) or 0
    )
    continued_tool_calls = list(stop_state.get("continued_tool_call_samples", []) or [])
    continued_work_messages = list(
        stop_state.get("continued_work_message_samples", []) or []
    )
    latest_goal_status = str(
        stop_state.get("latest_goal_status_after_stop")
        or goal_state.get("latest_status")
        or ""
    )
    terminal_updates_after_stop = int(
        stop_state.get("terminal_goal_updates_after_stop", 0) or 0
    )
    active_goal_left_open = bool(
        request_count and latest_goal_status == "active" and terminal_updates_after_stop == 0
    )
    reasons: List[str] = []
    if continued_tool_call_count:
        reasons.append("tool_call_after_user_stop")
    if continued_work_message_count:
        reasons.append("work_continuation_after_user_stop")
    if active_goal_left_open:
        reasons.append("user_stop_left_goal_active")
    if (
        request_count
        and int(stop_state.get("goal_context_after_stop", 0) or 0)
        and active_goal_left_open
    ):
        reasons.append("goal_context_reactivated_after_user_stop")
    return {
        "status": "blocked" if reasons else "passed",
        "stop_request_count": request_count,
        "latest_stop_line": int(stop_state.get("latest_stop_line", 0) or 0),
        "goal_context_after_stop": int(stop_state.get("goal_context_after_stop", 0) or 0),
        "latest_goal_status_after_stop": latest_goal_status,
        "terminal_goal_updates_after_stop": terminal_updates_after_stop,
        "continued_tool_calls": continued_tool_calls,
        "continued_work_messages": continued_work_messages,
        "reasons": reasons,
    }


def _build_assistant_stop_guard(
    goal_state: Dict[str, Any],
    task_complete_count: int,
    final_messages: List[str],
    assistant_stop_state: Dict[str, Any],
) -> Dict[str, Any]:
    latest_status = str(goal_state.get("latest_status", ""))
    stop_event_count = int(assistant_stop_state.get("event_count", 0) or 0)
    active_stop_event_count = int(
        assistant_stop_state.get("active_event_count", 0) or 0
    )
    stop_events = list(assistant_stop_state.get("event_samples", []) or [])
    active_stop_events = list(
        assistant_stop_state.get("active_event_samples", []) or []
    )
    stop_messages = [
        str(event.get("sample", "")) for event in stop_events if event.get("sample")
    ]
    terminal_status = latest_status in {"blocked", "complete"}
    blocked = bool(
        task_complete_count > 0
        and (active_stop_event_count or (stop_event_count and not terminal_status))
    )
    reasons: List[str] = []
    if active_stop_event_count:
        reasons.append("assistant_stop_left_goal_active")
    if stop_event_count and not terminal_status:
        reasons.append("assistant_stop_without_terminal_goal")
    return {
        "status": "blocked" if blocked else "passed",
        "latest_goal_status": latest_status,
        "task_complete_count": task_complete_count,
        "assistant_claims_stop": bool(stop_event_count),
        "stop_event_count": stop_event_count,
        "active_stop_events": active_stop_events,
        "final_stop_messages": stop_messages,
        "reasons": reasons,
    }


def _build_archive_guard(archive_state: Dict[str, Any]) -> Dict[str, Any]:
    directive_count = int(archive_state.get("directive_count", 0) or 0)
    user_request_count = int(archive_state.get("user_request_count", 0) or 0)
    directives = list(archive_state.get("directive_samples", []) or [])
    user_requests = list(archive_state.get("user_request_samples", []) or [])
    reasons: List[str] = []
    if directive_count and not user_request_count:
        reasons.append("archive_directive_without_user_request")
    return {
        "status": "blocked" if reasons else "passed",
        "archive_directive_count": directive_count,
        "user_archive_request_count": user_request_count,
        "latest_archive_line": int(archive_state.get("latest_directive_line", 0) or 0),
        "archive_directives": directives,
        "user_archive_requests": user_requests,
        "reasons": reasons,
    }


def _build_resume_guard(resume_state: Dict[str, Any], token_gate: Dict[str, Any]) -> Dict[str, Any]:
    request_count = int(resume_state.get("request_count", 0) or 0)
    implementation_tool_count = int(
        resume_state.get("implementation_tool_count", 0) or 0
    )
    implementation_tools = list(resume_state.get("implementation_tool_samples", []) or [])
    session_context_count = int(
        resume_state.get("session_start_context_after_resume", 0) or 0
    )
    token_runtime_count = int(
        resume_state.get("runtime_token_evidence_after_resume", 0) or 0
    )
    bundle_count = int(resume_state.get("large_work_bundle_after_resume", 0) or 0)
    reasons: List[str] = []
    if request_count and implementation_tool_count and not session_context_count:
        reasons.append("resume_without_session_start_context")
    if (
        request_count
        and implementation_tool_count
        and token_gate.get("required")
        and not token_runtime_count
    ):
        reasons.append("resume_without_runtime_token_optimizer")
    if request_count and implementation_tool_count and not bundle_count:
        reasons.append("resume_without_large_work_skill_bundle")
    return {
        "status": "blocked" if reasons else "passed",
        "resume_request_count": request_count,
        "latest_resume_line": int(resume_state.get("latest_resume_line", 0) or 0),
        "session_start_context_after_resume": session_context_count,
        "runtime_token_evidence_after_resume": token_runtime_count,
        "large_work_bundle_after_resume": bundle_count,
        "implementation_tools_after_resume": implementation_tools,
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
    assistant_stop_guard: Dict[str, Any],
    archive_guard: Dict[str, Any],
    resume_guard: Dict[str, Any],
    secret_findings: List[SecretFinding],
    git_state: Dict[str, Any],
    subagents: Dict[str, Any],
) -> List[str]:
    actions: List[str] = []
    if token_status == "blocked":
        actions.append("Run token-optimizer or record passthrough before continuing the large session.")
        if token_optimizer_evidence.get("blocked_reason_records"):
            actions.append("Token optimizer blockage has a reason record, but the workflow still needs passthrough or recovery evidence before completion.")
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
    if assistant_stop_guard.get("status") == "blocked":
        actions.append(
            "Do not emit a stopped/blocked final answer without terminal GoalState evidence; either close/block the goal when policy permits, or report active_with_blocker and the next required action without declaring stop."
        )
    if archive_guard.get("status") == "blocked":
        actions.append(
            "Do not emit ::archive unless the user explicitly asked to end/archive the conversation; report the failed handoff as an ordinary status instead."
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


def _iter_session_lines(path: Path):
    """Yield JSONL lines once without materializing the rollout file."""
    with path.open("r", encoding="utf-8", errors="replace", newline="") as stream:
        for line_number, line in enumerate(stream, start=1):
            yield line_number, line


def _iter_postmortem_records(
    path: Path,
    event_stream: Iterable[Any] | None,
):
    """Yield decoded records from either the shared pipeline or standalone IO."""
    if event_stream is not None:
        for envelope in event_stream:
            event_features = getattr(envelope, "features", None)
            if not isinstance(event_features, PostmortemEventFeatures):
                event_features = getattr(event_features, "postmortem", None)
            if (
                not isinstance(event_features, PostmortemEventFeatures)
                and isinstance(envelope.event, dict)
                and not envelope.parse_error
                and not envelope.duplicate_keys
            ):
                event_features = extract_postmortem_event_features(
                    envelope.event,
                    int(envelope.source_line),
                )
            yield (
                int(envelope.source_line),
                str(envelope.raw_text),
                envelope.event,
                list(envelope.duplicate_keys),
                str(envelope.parse_error or ""),
                event_features,
            )
        return

    for line_number, line in _iter_session_lines(path):
        duplicate_keys: List[str] = []
        event: Any = None
        parse_error = ""
        if line and not line.isspace():
            try:
                event = json.loads(
                    line,
                    object_pairs_hook=_duplicate_tracking_hook(duplicate_keys),
                )
            except (json.JSONDecodeError, UnicodeError) as exc:
                parse_error = str(exc)
        event_features = (
            extract_postmortem_event_features(event, line_number)
            if isinstance(event, dict) and not parse_error and not duplicate_keys
            else None
        )
        yield line_number, line, event, duplicate_keys, parse_error, event_features


def _duplicate_tracking_hook(duplicate_keys: List[str]):
    """Preserve json.loads last-key-wins behavior while recording duplicate keys."""

    def build_object(pairs):
        result = {}
        seen = set()
        for key, value in pairs:
            normalized_key = str(key)
            if normalized_key in seen:
                duplicate_keys.append(normalized_key)
            seen.add(normalized_key)
            result[key] = value
        return result

    return build_object


def _integrity_line_record(line_number: int, line: str, *, error: str = "") -> Dict[str, Any]:
    encoded = line.encode("utf-8", errors="replace")
    record: Dict[str, Any] = {
        "line": int(line_number),
        "char_count": len(line),
        "byte_count": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }
    if error:
        record["error"] = _bounded_text(error, 240)
    return record


def _ordered_unique(items) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _bounded_text(text: str, max_length: int) -> str:
    """Keep small text exact and summarize oversized retained text with recovery metadata."""
    value = str(text or "")
    limit = max(128, int(max_length))
    if len(value) <= limit:
        return value
    digest = hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()
    marker = f"\n...[truncated chars={len(value)} sha256={digest}]...\n"
    available = max(2, limit - len(marker))
    head_length = available // 2
    tail_length = available - head_length
    return value[:head_length] + marker + value[-tail_length:]


def _bounded_utf8_text(text: str, max_bytes: int) -> str:
    """Retain a deterministic UTF-8 representation no larger than max_bytes."""
    value = str(text or "")
    limit = max(128, int(max_bytes))
    if len(value) <= limit // 4:
        return value
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return value
    digest = hashlib.sha256(encoded).hexdigest()
    marker = (
        f"\n...[truncated bytes={len(encoded)} sha256={digest}]...\n"
    ).encode("ascii")
    if len(marker) >= limit:
        return encoded[:limit].decode("utf-8", errors="ignore")
    available = limit - len(marker)
    head_length = available // 2
    tail_length = available - head_length
    head = encoded[:head_length].decode("utf-8", errors="ignore")
    tail = encoded[-tail_length:].decode("utf-8", errors="ignore")
    return head + marker.decode("ascii") + tail


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


def _payload_has_timeout(
    payload: Dict[str, Any],
    *,
    lowered_output: str = "",
) -> bool:
    output = payload.get("output")
    if isinstance(output, dict):
        return bool(output.get("timed_out"))
    text = _content_text(output)
    lowered = lowered_output or text.lower()
    if '"timed_out"' not in lowered:
        return False
    return '"timed_out":true' in lowered.replace(" ", "")


def _verification_failure_from_output(
    output_text: str,
    *,
    lowered: str | None = None,
) -> Dict[str, Any]:
    text = output_text or ""
    compact = text.lower() if lowered is None else lowered
    if '"ok":false' in compact or "'ok': false" in compact:
        return {"kind": "tool_verification_failed", "sample": _bounded_redacted_short(text, 300)}
    if "module not found: playwright" in compact:
        return {"kind": "browser_qa_unavailable", "sample": _bounded_redacted_short(text, 300)}
    if ("exit code" in compact or "return" in compact) and VERIFICATION_EXIT_CODE_PATTERN.search(text):
        if FAILURE_PATTERN.search(text) or VERIFICATION_FATAL_PATTERN.search(text):
            return {"kind": "command_verification_failed", "sample": _bounded_redacted_short(text, 300)}
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
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not COMPLETION_PATTERN.search(normalized):
        return False
    for pattern in COMPLETION_NEGATION_PATTERNS:
        normalized = pattern.sub(" ", normalized)
    return bool(COMPLETION_PATTERN.search(normalized))


def _claims_assistant_self_stop(text: str) -> bool:
    return bool(ASSISTANT_SELF_STOP_PATTERN.search(text or ""))


def _mentions_partial_milestone(text: str) -> bool:
    return bool(PARTIAL_MILESTONE_PATTERN.search(text or ""))


def _is_user_stop_request(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized or GOAL_CONTEXT_PATTERN.search(normalized):
        return False
    return resolve_request_intent(normalized)["conversation_pause_requested"] is True


def _is_user_archive_request(text: str) -> bool:
    normalized = (text or "").strip()
    return bool(normalized and USER_ARCHIVE_REQUEST_PATTERN.search(normalized))


def _is_user_resume_request(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False
    intent = resolve_request_intent(normalized)
    if intent["conversation_pause_requested"] is True:
        return False
    if intent["persistence_requested"] is True:
        return True
    return bool(
        re.match(
            r"^(?:please\s+)?(?:resume|continue|proceed|go on|restart)\b|"
            r"^(?:계속|이어서|재개|진행해|다시\s*시작)",
            normalized,
            re.IGNORECASE,
        )
    )


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
