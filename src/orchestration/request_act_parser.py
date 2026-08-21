from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left
from dataclasses import dataclass
from typing import FrozenSet, Mapping, Tuple


MUTATING_ACTION_CLASSES = frozenset({"mutate", "execute", "destructive"})

_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
)


@dataclass(frozen=True)
class PayloadSpan:
    start: int
    end: int
    kind: str
    text: str


@dataclass(frozen=True)
class RequestClause:
    text: str
    normalized: str
    connector: str
    negated: bool
    question: bool
    advisory: bool
    explicit_nonexecution: bool
    readonly_boundary: bool
    approval_state: str
    action_verbs: Tuple[str, ...]
    action_classes: FrozenSet[str]
    target_classes: FrozenSet[str]
    scopes: FrozenSet[str]
    authorized: bool
    apparent_change_obligation: bool
    referential_target: bool

    @property
    def mutating(self) -> bool:
        return bool(self.action_classes & MUTATING_ACTION_CLASSES)


@dataclass(frozen=True)
class RequestActAnalysis:
    text: str
    outer_text: str
    payload_spans: Tuple[PayloadSpan, ...]
    clauses: Tuple[RequestClause, ...]
    context_execution_approved: bool | None

    @property
    def has_sql_payload(self) -> bool:
        return any(span.kind == "sql" for span in self.payload_spans)

    @property
    def sql_payload_is_destructive(self) -> bool:
        return any(
            span.kind == "sql" and _SQL_DESTRUCTIVE_RE.search(span.text)
            for span in self.payload_spans
        )

    @property
    def authorized_clauses(self) -> Tuple[RequestClause, ...]:
        return tuple(clause for clause in self.clauses if clause.authorized)

    @property
    def has_mutation_authorization(self) -> bool:
        return any(clause.authorized and clause.mutating for clause in self.clauses)

    @property
    def approval_blocked(self) -> bool:
        return any(
            clause.approval_state in {"denied", "pending", "questioned"}
            for clause in self.clauses
        )

    @property
    def has_question(self) -> bool:
        return any(clause.question for clause in self.clauses)

    @property
    def has_inspection(self) -> bool:
        return any("inspect" in clause.action_classes for clause in self.clauses)

    @property
    def has_readonly_boundary(self) -> bool:
        return any(
            clause.readonly_boundary or (clause.negated and clause.mutating)
            for clause in self.clauses
        )

    @property
    def readonly_inspection(self) -> bool:
        if self.has_mutation_authorization:
            return False
        has_source_inspection = any(
            "inspect" in clause.action_classes
            and "source" in clause.target_classes
            and not clause.negated
            for clause in self.clauses
        )
        return bool(has_source_inspection and self.has_readonly_boundary)

    @property
    def unresolved_referential_mutation(self) -> bool:
        referential_command = any(
            clause.authorized and clause.mutating and clause.referential_target
            for clause in self.clauses
        )
        if not referential_command:
            return False
        if self.approval_blocked:
            return True
        return self.context_execution_approved is not True

    @property
    def outer_database_execution(self) -> bool:
        if not self.has_sql_payload:
            return False
        for clause in self.clauses:
            if not clause.authorized or "execute" not in clause.action_classes:
                continue
            if (
                "database" in clause.target_classes
                or clause.referential_target
                or clause.scopes & {"production", "live", "staging"}
            ):
                return True
        return False

    @property
    def bounded_sql_request(self) -> bool:
        if not self.has_sql_payload or self.outer_database_execution:
            return False
        return any(
            "transform" in clause.action_classes
            or set(clause.action_verbs)
            & {
                "analyze",
                "check",
                "inspect",
                "review",
                "\ud655\uc778",
                "\uac80\ud1a0",
                "\ub9ac\ubdf0",
                "\uc810\uac80",
            }
            for clause in self.clauses
        )

    @property
    def authorized_high_impact_destructive(self) -> bool:
        for clause in self.clauses:
            destructive_command = bool(
                clause.authorized and "destructive" in clause.action_classes
            )
            structural_whole_set_directive = _is_structural_whole_set_directive(
                clause.normalized,
                clause.action_classes,
                clause.target_classes,
                clause.scopes,
                question=clause.question,
                negated=clause.negated,
                advisory=clause.advisory,
                explicit_nonexecution=clause.explicit_nonexecution,
                readonly_boundary=clause.readonly_boundary,
            )
            if not (destructive_command or structural_whole_set_directive):
                continue
            if structural_whole_set_directive:
                return True
            targets = clause.target_classes
            scopes = clause.scopes
            replacement_lifecycle = bool(
                "constructive" in clause.action_classes
                and "destructive" in clause.action_classes
            )
            if targets & {"credential", "protection"}:
                return True
            if targets & {"cloud_resource", "orchestrated_resource"}:
                if replacement_lifecycle:
                    continue
                return True
            if "storage_device" in targets:
                return True
            if "database" in targets and (
                scopes & {"all", "production", "live"}
                or clause.action_verbs and clause.action_verbs[0] in {"drop", "truncate"}
            ):
                return True
            if "filesystem" in targets and scopes & {
                "all",
                "production",
                "live",
                "recursive",
                "root",
            }:
                return True
        return bool(
            self.outer_database_execution
            and self.sql_payload_is_destructive
            and any(
                clause.scopes & {"production", "live"}
                or "database" in clause.target_classes
                for clause in self.authorized_clauses
            )
        )

    @property
    def credential_access_requested(self) -> bool:
        credential_clauses = [
            clause for clause in self.clauses if "credential" in clause.target_classes
        ]
        if not credential_clauses:
            return False
        for clause in credential_clauses:
            if clause.negated or clause.explicit_nonexecution:
                continue
            store_access = _CREDENTIAL_STORE_RE.search(clause.normalized) is not None
            source_branch_inspection = bool(
                "source" in clause.target_classes
                and "inspect" in clause.action_classes
                and not store_access
            )
            if source_branch_inspection:
                continue
            if clause.authorized or store_access or "inspect" in clause.action_classes:
                return True
        return False

    @property
    def nonexecuting_destructive_discussion(self) -> bool:
        if self.has_mutation_authorization or self.outer_database_execution:
            return False
        if self.has_sql_payload and self.bounded_sql_request:
            return False
        destructive_language = bool(
            _DESTRUCTIVE_LANGUAGE_RE.search(self.text)
            or _has_high_impact_surface(self.text)
        )
        quoted_destructive = any(
            span.kind == "quote"
            and (
                _DESTRUCTIVE_LANGUAGE_RE.search(span.text)
                or _has_high_impact_surface(span.text)
            )
            for span in self.payload_spans
        )
        nonexecution = any(
            clause.explicit_nonexecution
            or clause.readonly_boundary
            or (clause.negated and clause.mutating)
            for clause in self.clauses
        )
        discussion = any(
            clause.question
            or clause.advisory
            or "inspect" in clause.action_classes
            for clause in self.clauses
        )
        explanation_only = bool(
            _has_outer_explanatory_act(self.outer_text)
            or re.search(
                r"\b(?:advisory|discussion|explanation|policy|review|example)\s+only\b"
                r"|(?:\uc124\uba85|\uac80\ud1a0|\ub17c\uc758)\ub9cc",
                self.outer_text,
                re.IGNORECASE,
            )
        )
        return bool(
            destructive_language
            and discussion
            and (nonexecution or quoted_destructive or explanation_only)
        )


_ENGLISH_ACTION_CLASSES = {
    "add": {"constructive", "mutate"},
    "alter": {"mutate"},
    "annihilate": {"destructive", "mutate"},
    "apply": {"execute", "mutate"},
    "build": {"constructive", "mutate"},
    "carry": {"execute", "mutate"},
    "change": {"mutate"},
    "clear": {"destructive", "mutate"},
    "continue": {"continue"},
    "correct": {"mutate"},
    "create": {"constructive", "mutate"},
    "recreate": {"constructive", "mutate"},
    "delete": {"destructive", "mutate"},
    "deploy": {"execute", "mutate"},
    "eradicate": {"destructive", "mutate"},
    "destroy": {"destructive", "mutate"},
    "disable": {"destructive", "mutate"},
    "drop": {"destructive", "mutate"},
    "edit": {"mutate"},
    "eliminate": {"destructive", "mutate"},
    "empty": {"destructive", "mutate"},
    "erase": {"destructive", "mutate"},
    "expunge": {"destructive", "mutate"},
    "exterminate": {"destructive", "mutate"},
    "execute": {"execute", "mutate"},
    "fix": {"mutate"},
    "implement": {"constructive", "mutate"},
    "modify": {"mutate"},
    "patch": {"mutate"},
    "proceed": {"execute", "mutate"},
    "publish": {"execute", "mutate"},
    "purge": {"destructive", "mutate"},
    "remove": {"destructive", "mutate"},
    "repair": {"mutate"},
    "refactor": {"transform"},
    "reset": {"destructive", "mutate"},
    "resume": {"continue"},
    "run": {"execute", "mutate"},
    "shred": {"destructive", "mutate"},
    "style": {"transform"},
    "truncate": {"destructive", "mutate"},
    "vaporize": {"destructive", "mutate"},
    "update": {"mutate"},
    "wipe": {"destructive", "mutate"},
    "write": {"constructive", "mutate"},
    "align": {"transform"},
    "analyze": {"inspect"},
    "check": {"inspect"},
    "clean": {"transform"},
    "explain": {"inspect"},
    "format": {"transform"},
    "inspect": {"inspect"},
    "normalize": {"transform"},
    "nuke": {"destructive", "mutate"},
    "obliterate": {"destructive", "mutate"},
    "read": {"inspect"},
    "report": {"inspect"},
    "review": {"inspect"},
    "rewrite": {"transform"},
    "summarize": {"inspect"},
    "trace": {"inspect"},
}

_KOREAN_ACTION_CLASSES = {
    "\ucd94\uac00": {"constructive", "mutate"},
    "\uc801\uc6a9": {"execute", "mutate"},
    "\ubc18\uc601": {"execute", "mutate"},
    "\uc0dd\uc131": {"constructive", "mutate"},
    "\uc0ad\uc81c": {"destructive", "mutate"},
    "\uc81c\uac70": {"destructive", "mutate"},
    "\ubc30\ud3ec": {"execute", "mutate"},
    "\ube44\ud65c\uc131\ud654": {"destructive", "mutate"},
    "\ube44\uc6b0": {"destructive", "mutate"},
    "\ube44\uc6cc": {"destructive", "mutate"},
    "\ub0a0\ub9ac": {"destructive", "mutate"},
    "\ub0a0\ub824": {"destructive", "mutate"},
    "\uc9c0\uc6b0": {"destructive", "mutate"},
    "\uc9c0\uc6cc": {"destructive", "mutate"},
    "\uc5c6\uc560": {"destructive", "mutate"},
    "\ucd08\uae30\ud654": {"destructive", "mutate"},
    "\ud30c\uae30": {"destructive", "mutate"},
    "\ub9d0\uc18c": {"destructive", "mutate"},
    "\uc2e4\ud589": {"execute", "mutate"},
    "\ub3cc\ub9ac": {"execute", "mutate"},
    "\ub3cc\ub824": {"execute", "mutate"},
    "\uc9c4\ud589": {"execute", "mutate"},
    "\ucc29\uc218": {"execute", "mutate"},
    "\uace0\uce58": {"mutate"},
    "\uc218\uc815": {"mutate"},
    "\ubcf4\uc644": {"mutate"},
    "\ud328\uce58": {"mutate"},
    "\uad6c\ud604": {"constructive", "mutate"},
    "\ubcc0\uacbd": {"mutate"},
    "\uc791\uc131": {"constructive", "mutate"},
    "\ub9cc\ub4e4": {"constructive", "mutate"},
    "\ud655\uc778": {"inspect"},
    "\uac80\ud1a0": {"inspect"},
    "\ub9ac\ubdf0": {"inspect"},
    "\uc810\uac80": {"inspect"},
    "\ucd94\uc801": {"inspect"},
    "\uc77d": {"inspect"},
    "\uc124\uba85": {"inspect"},
    "\ubcf4\uace0": {"inspect"},
    "\uc870\uc5b8": {"inspect"},
    "\ud3ec\ub9f7": {"transform"},
    "\uc815\ub9ac": {"transform"},
    "\uc815\ub82c": {"transform"},
    "\uc870\ud68c": {"inspect"},
}

_TARGET_PATTERNS = {
    "database": re.compile(
        r"\b(?:database|db|entries?|ledgers?|records?|rows?|schemas?|tables?)\b"
        r"|(?:\ub370\uc774\ud130\ubca0\uc774\uc2a4|\uae30\ub85d|\ub808\ucf54\ub4dc|\uc6d0\uc7a5|(?<![\uac00-\ud7a3])\ud589(?![\uac00-\ud7a3])|\uc2a4\ud0a4\ub9c8|\ud14c\uc774\ube14|\uc6b4\uc601\s*db|\uc2e4\s*db)",
        re.IGNORECASE,
    ),
    "filesystem": re.compile(
        r"(?:^|\s)(?:[a-z]:\\|/)[^\s;]*"
        r"|\b(?:directories|directory|disks?|drives?|files?|filesystem|folders?|mounts?|paths?|servers?|volumes?)\b"
        r"|(?:\ub514\ub809\ud130\ub9ac|\ub514\ub809\ud1a0\ub9ac|\ub514\uc2a4\ud06c|\ub4dc\ub77c\uc774\ube0c|\ud30c\uc77c|\ud30c\uc77c\uc2dc\uc2a4\ud15c|\ud3f4\ub354|\uacbd\ub85c|\ub9c8\uc6b4\ud2b8|\uc11c\ubc84|\ubcfc\ub968)",
        re.IGNORECASE,
    ),
    "storage_device": re.compile(
        r"\b(?:disks?|drives?|mounts?|volumes?)\b"
        r"|(?:\ub514\uc2a4\ud06c|\ub4dc\ub77c\uc774\ube0c|\ub9c8\uc6b4\ud2b8|\ubcfc\ub968)",
        re.IGNORECASE,
    ),
    "protection": re.compile(
        r"\b(?:audit\s+logs?|backups?|recovery|snapshots?|vaults?)\b"
        r"|(?:\uac10\uc0ac\s*\ub85c\uadf8|\ubc31\uc5c5|\ubcf5\uad6c|\uc2a4\ub0c5\uc0f7|\ubcfc\ud2b8|\ubcf4\uad00\uc18c)",
        re.IGNORECASE,
    ),
    "credential": re.compile(
        r"(?<![a-z0-9_])(?:api[_ -]?keys?|connection\s+strings?|credentials?|passwords?|secrets?|tokens?)(?![a-z0-9_])"
        r"|(?<![a-z0-9_])(?:[a-z0-9]+_)*(?:api_?key|access_?token|secret|password)(?![a-z0-9_])"
        r"|(?:\uc790\uaca9\s*\uc99d\uba85|\ube44\ubc00\ubc88\ud638|\ube44\ubc00\ud0a4|\uc2dc\ud06c\ub9bf|\ud1a0\ud070|\uc5f0\uacb0\s*\ubb38\uc790\uc5f4|\ud658\uacbd\ubcc0\uc218.{0,24}\ud0a4|\.env.{0,24}\ud0a4)",
        re.IGNORECASE,
    ),
    "cloud_resource": re.compile(
        r"\b(?:cloud|clusters?|kubernetes|k8s|namespaces?|resources?)\b"
        r"|(?:\ud074\ub77c\uc6b0\ub4dc|\ud074\ub7ec\uc2a4\ud130|\ucfe0\ubc84\ub124\ud2f0\uc2a4|k8s|\ub124\uc784\uc2a4\ud398\uc774\uc2a4|\ub9ac\uc18c\uc2a4)",
        re.IGNORECASE,
    ),
    "orchestrated_resource": re.compile(
        r"\b(?:clusters?|kubernetes|k8s|namespaces?|resources?)\b"
        r"|(?:\ud074\ub7ec\uc2a4\ud130|\ucfe0\ubc84\ub124\ud2f0\uc2a4|k8s|\ub124\uc784\uc2a4\ud398\uc774\uc2a4|\ub9ac\uc18c\uc2a4)",
        re.IGNORECASE,
    ),
    "source": re.compile(
        r"(?<![a-z0-9_])(?:code|source|router|classifier|repository|repo|tests?|provider|implementation|module|runtime)(?![a-z0-9_])"
        r"|(?:\ucf54\ub4dc|\uc18c\uc2a4|\ub77c\uc6b0\ud130|\ubd84\ub958\uae30|\uc800\uc7a5\uc18c|\ud14c\uc2a4\ud2b8|\ud504\ub85c\ubc14\uc774\ub354|\uad6c\ud604|\ubaa8\ub4c8|\ub7f0\ud0c0\uc784)",
        re.IGNORECASE,
    ),
}

_SCOPE_PATTERNS = {
    "all": re.compile(
        r"\b(?:all|descendants?|entire|every|everything|full|whole)\b"
        r"|(?:\uc804\uccb4|\uc804\ubd80|\uc804\ubd84|\uc804\ub7c9|\ubaa8\ub4e0|\ubaa8\ub450|\ud1b5\uc9f8\ub85c)"
    ),
    "production": re.compile(
        r"\bproduction\b|(?:\ud504\ub85c\ub355\uc158|\uc2e4\uc11c\ube44\uc2a4|\uc2e4\uc6b4\uc601|\uc6b4\uc601\uacc4|\uc6b4\uc601\b|"
        r"\uc6b4\uc601\s*(?:db|\ub370\uc774\ud130\ubca0\uc774\uc2a4|\uc11c\ubc84|\ud658\uacbd|\ub370\uc774\ud130|\ub808\ucf54\ub4dc|\ud14c\uc774\ube14|\ud074\ub77c\uc6b0\ub4dc|\ucfe0\ubc84\ub124\ud2f0\uc2a4|\ud074\ub7ec\uc2a4\ud130|\ub124\uc784\uc2a4\ud398\uc774\uc2a4|\ub9ac\uc18c\uc2a4|\uacbd\ub85c|\ud30c\uc77c\uc2dc\uc2a4\ud15c|\uacc4\uc815|\uc790\uaca9\s*\uc99d\uba85))",
        re.IGNORECASE,
    ),
    "live": re.compile(r"\blive\b|(?:\uc2e4\s*db|\uc2e4\uc11c\ubc84)"),
    "staging": re.compile(r"\b(?:stage|staging)\b|(?:\uc2a4\ud14c\uc774\uc9d5|\uac80\uc99d\uacc4)"),
    "recursive": re.compile(
        r"\b(?:descendants?|recursiv(?:e|ely))\b"
        r"|(?:\uc7ac\uadc0|\ud558\uc704\s*(?:\uacbd\ub85c|\ub514\ub809\ud130\ub9ac|\ud3f4\ub354|\ub9ac\uc18c\uc2a4|\ud56d\ubaa9|\ub300\uc0c1).{0,12}(?:\uae4c\uc9c0|\ud3ec\ud568)?|\uadf8\s*\uc548\uc758)"
    ),
    "root": re.compile(r"\broot\b|\ub8e8\ud2b8"),
    "system": re.compile(r"\bsystem\b|\uc2dc\uc2a4\ud15c"),
    "local": re.compile(r"\blocal\b|\ub85c\uceec"),
    "noncritical": re.compile(r"\bnoncritical\b|\ube44\uc911\uc694"),
}

_SQL_STATEMENT_RE = re.compile(
    r"(?<![a-z0-9_])(?:"
    r"select\b(?=[\s\S]{0,160}\bfrom\b)"
    r"|insert\s+(?:into\s+)?[\[\]a-z0-9_.]+"
    r"|update\s+[\[\]a-z0-9_.]+(?:\s+with\s*\([^)]*\))?\s+set\b"
    r"|delete\s+(?:top\s*\([^)]*\)\s+)?(?:[\[\]a-z0-9_]+\s+)?from\s+[\[\]a-z0-9_.]+"
    r"|merge\s+(?:into\s+)?[\[\]a-z0-9_.]+"
    r"|(?:drop|truncate|alter)\s+(?:table|database|schema|view|index|procedure)\b"
    r"|create\s+(?:or\s+alter\s+)?(?:table|database|schema|view|index|procedure|function|trigger)\b"
    r")",
    re.IGNORECASE,
)
_SQL_DESTRUCTIVE_RE = re.compile(
    r"\b(?:delete\s+(?:top\s*\([^)]*\)\s+)?(?:[\[\]a-z0-9_]+\s+)?from"
    r"|drop\s+(?:table|database|schema)|truncate\s+table)\b",
    re.IGNORECASE,
)
_DESTRUCTIVE_LANGUAGE_RE = re.compile(
    r"\b(?:annihilate|clear|delete|destroy|disable|drop|eliminate|empty|eradicate|erase|"
    r"expunge|exterminate|nuke|obliterate|purge|remove|reset|shred|truncate|vaporize|wipe)\b"
    r"|(?:\uc0ad\uc81c|\uc81c\uac70|\ube44\ud65c\uc131\ud654|\ube44\uc6b0|\ube44\uc6cc|\ub0a0\ub9ac|\ub0a0\ub824|\uc9c0\uc6b0|\uc9c0\uc6cc|\ucd08\uae30\ud654|\ud30c\uae30|\ub9d0\uc18c)",
    re.IGNORECASE,
)
_CREDENTIAL_STORE_RE = re.compile(
    r"(?:\.env|environment\s+variables?|configured|configuration|exists?|presence|show|print|reveal|value)"
    r"|(?:\ud658\uacbd\ubcc0\uc218|\uc124\uc815|\uc800\uc7a5|\uc788\ub294\uc9c0|\uc874\uc7ac|\uac12|\ucd9c\ub825|\ubcf4\uc5ec)",
    re.IGNORECASE,
)

_LITERAL_PATTERNS = (
    (
        "sql",
        re.compile(
            r"```[ \t]*(?:sql|t-sql|tsql)\b[^\r\n]*(?:\r?\n|\s)[\s\S]*?```",
            re.IGNORECASE,
        ),
    ),
    ("code", re.compile(r"```[\s\S]*?```")),
    ("code", re.compile(r"`[^`\r\n]*`")),
    ("quote", re.compile(r'"(?:\\.|[^"\\])*"')),
    ("quote", re.compile(r"(?<!\w)'(?:\\.|[^'\\])*'(?![a-z0-9_])", re.IGNORECASE)),
    ("quote", re.compile(r"[\u201c\u2018\u300c\u300e][\s\S]*?[\u201d\u2019\u300d\u300f]")),
)

_OUTER_EXECUTION_START_RE = re.compile(
    r"(?<![a-z0-9_])(?:execute|apply|run|deploy|proceed)(?![a-z0-9_])"
    r"|(?:\uc2e4\ud589|\uc801\uc6a9|\ubc18\uc601|\ubc30\ud3ec|\ub3cc\ub824|\ub3cc\ub9ac|\uc9c4\ud589)",
    re.IGNORECASE,
)

_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?P<punct>[!?;\u2014\u2013]+|\.(?=\s|$))\s*"
    r"|(?:,\s*)?(?P<connector>\b(?:but|however|yet|then|next|after\s+(?:review|that|this))\b|"
    r"(?<![\uac00-\ud7a3])(?:\ud558\uc9c0\ub9cc|\uadf8\ub7ec\ub098|\uadf8\ub7f0\ub370)|"
    r"\uadf8\s*\ub4a4|\uc774\ud6c4|\ub2e4\uc74c(?:\uc73c\ub85c)?|\uac80\ud1a0\s*\ud6c4|\ub9d0\uace0)(?:\s*,\s*)?",
    re.IGNORECASE,
)
_INTERRUPTIVE_DASH_PAIR_RE = re.compile(r"[\u2014\u2013][^\u2014\u2013\r\n]{1,160}[\u2014\u2013]")
_TOKEN_RE = re.compile(r"[a-z][a-z0-9_-]*|[\uac00-\ud7a3]+", re.IGNORECASE)
_ENGLISH_ACTION_PHRASE_RE = re.compile(
    r"\b(?P<phrase>carry\s+out|go\s+ahead|turn\s+off|shut\s+off)\b",
    re.IGNORECASE,
)
_ENGLISH_ACTION_PHRASE_CANONICAL = {
    "carry out": "proceed",
    "go ahead": "proceed",
    "turn off": "disable",
    "shut off": "disable",
}


def parse_request_act(text: str, context: Mapping[str, object] | None = None) -> RequestActAnalysis:
    source = _canonicalize_text(text)
    payloads = _payload_spans(source)
    outer_text = _outer_text(source, payloads)
    clauses = tuple(_split_clauses(outer_text))
    return RequestActAnalysis(
        text=source,
        outer_text=outer_text,
        payload_spans=payloads,
        clauses=clauses,
        context_execution_approved=_strict_execution_approval(context or {}),
    )


def _payload_spans(text: str) -> Tuple[PayloadSpan, ...]:
    literal_candidates = []
    for priority, (kind, pattern) in enumerate(_LITERAL_PATTERNS):
        for match in pattern.finditer(text):
            literal_candidates.append(
                (
                    match.start(),
                    match.end(),
                    priority,
                    PayloadSpan(match.start(), match.end(), kind, match.group(0)),
                )
            )
    literal_spans = tuple(
        PayloadSpan(span.start, span.end, "sql", span.text)
        if (
            span.kind == "code"
            and span.text.lstrip().startswith("```")
            and _SQL_STATEMENT_RE.search(span.text)
        )
        else span
        for span in _ordered_nonoverlapping_spans(literal_candidates)
    )

    masked = _mask(text, literal_spans)
    sql_spans = []
    cursor = 0
    while cursor < len(masked):
        match = _SQL_STATEMENT_RE.search(masked, cursor)
        if match is None:
            break
        end = _sql_payload_end(masked, match.start(), match.end())
        sql_spans.append(PayloadSpan(match.start(), end, "sql", text[match.start() : end]))
        if end <= match.start():
            break
        if end >= len(masked):
            break
        cursor = end

    spans = sorted(
        [*literal_spans, *sql_spans],
        key=lambda span: (span.start, span.end),
    )
    return tuple(spans)


def _ordered_nonoverlapping_spans(candidates) -> Tuple[PayloadSpan, ...]:
    """Resolve ordered literal candidates with a single forward overlap pass."""
    ordered = sorted(candidates, key=lambda item: (item[0], item[2], -item[1]))
    merged = []
    cursor = -1
    for start, end, _priority, span in ordered:
        if start < cursor:
            continue
        merged.append(span)
        cursor = end
    return tuple(merged)


def _sql_payload_end(masked: str, start: int, statement_end: int) -> int:
    for boundary in re.finditer(r"\r?\n", masked[statement_end:]):
        boundary_start = statement_end + boundary.start()
        tail_start = statement_end + boundary.end()
        stripped = masked[tail_start:].lstrip(" \t")
        if not stripped or stripped.startswith(("\r", "\n")):
            continue
        if _SQL_STATEMENT_RE.match(stripped):
            continue
        if _looks_like_outer_clause(stripped):
            return boundary_start
    for boundary in re.finditer(r"[.!?]\s+", masked[statement_end:]):
        boundary_start = statement_end + boundary.start()
        tail_start = statement_end + boundary.end()
        stripped = masked[tail_start:].lstrip()
        if stripped and _looks_like_outer_clause(stripped):
            return boundary_start
    for boundary in re.finditer(r"\r?\n[ \t]*\r?\n", masked[statement_end:]):
        boundary_start = statement_end + boundary.start()
        tail_start = statement_end + boundary.end()
        stripped = masked[tail_start:].lstrip()
        if not stripped or _SQL_STATEMENT_RE.match(stripped):
            continue
        if _looks_like_outer_clause(stripped):
            return boundary_start
    for semicolon in re.finditer(r";", masked[start:]):
        absolute_end = start + semicolon.end()
        outer_execution_start = _outer_execution_start(
            masked,
            statement_end,
            absolute_end,
        )
        if 0 <= outer_execution_start < absolute_end:
            return outer_execution_start
        tail = masked[absolute_end:]
        stripped = tail.lstrip()
        if not stripped:
            return len(masked)
        if _SQL_STATEMENT_RE.match(stripped):
            continue
        if _looks_like_outer_clause(stripped):
            return absolute_end
    closing_parens = list(re.finditer(r"\)", masked[statement_end:]))
    for closing in reversed(closing_parens):
        absolute_end = statement_end + closing.end()
        stripped = masked[absolute_end:].lstrip()
        if stripped and _looks_like_outer_clause(stripped):
            return absolute_end
    outer_execution_start = _outer_execution_start(masked, statement_end)
    if outer_execution_start >= 0:
        return outer_execution_start
    return len(masked)


def _outer_execution_start(text: str, start: int, end: int | None = None) -> int:
    search_end = len(text) if end is None else min(len(text), end)
    for match in _OUTER_EXECUTION_START_RE.finditer(text, start, search_end):
        clause_end_match = re.search(r"[;\r\n]", text[match.start() : search_end])
        clause_end = (
            match.start() + clause_end_match.start()
            if clause_end_match is not None
            else search_end
        )
        clause = _build_clause(text[match.start() : clause_end], "sequence")
        if (
            clause.authorized
            and "execute" in clause.action_classes
            and (
                clause.referential_target
                or "database" in clause.target_classes
                or clause.scopes & {"production", "live", "staging"}
            )
        ):
            return match.start()
    return -1


def _looks_like_outer_clause(text: str) -> bool:
    sample = re.split(r";", text, maxsplit=1)[0]
    clauses = _split_clauses(sample)
    return any(
        clause.authorized
        or clause.action_classes & {"inspect", "transform"}
        or clause.question
        for clause in clauses
    )


def _outer_text(text: str, spans: Tuple[PayloadSpan, ...]) -> str:
    parts = []
    cursor = 0
    for span in spans:
        if span.start < cursor:
            continue
        parts.append(text[cursor : span.start])
        placeholder = " sql payload; " if span.kind == "sql" else f" {span.kind} payload "
        parts.append(placeholder)
        cursor = span.end
    parts.append(text[cursor:])
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _split_clauses(text: str):
    clauses = []
    cursor = 0
    connector = "start"
    interruptive_spans = tuple(
        (match.start(), match.end())
        for match in _INTERRUPTIVE_DASH_PAIR_RE.finditer(text)
    )
    for match in _CLAUSE_BOUNDARY_RE.finditer(text):
        if any(start <= match.start() < end for start, end in interruptive_spans):
            continue
        segment = text[cursor : match.start()]
        punct = match.group("punct") or ""
        if segment.strip():
            trailing_connector = match.group("connector") or ""
            if _normalize(trailing_connector) == "\ub9d0\uace0":
                segment = f"{segment} {trailing_connector}"
            clauses.append(_build_clause(f"{segment}{punct}", connector))
        if match.group("connector"):
            connector = _connector_kind(match.group("connector"))
        else:
            connector = "sequence" if punct == ";" else "sentence"
        cursor = match.end()
    tail = text[cursor:]
    if tail.strip():
        clauses.append(_build_clause(tail, connector))
    return clauses


def _build_clause(text: str, connector: str) -> RequestClause:
    normalized = _normalize(text.strip(" ,"))
    action_matches = _action_matches(normalized)
    action_verbs = tuple(dict.fromkeys(match[0] for match in action_matches))
    action_classes = set()
    for _, classes, _, _ in action_matches:
        action_classes.update(classes)
    target_classes = {
        name for name, pattern in _TARGET_PATTERNS.items() if pattern.search(normalized)
    }
    scopes = {
        name for name, pattern in _SCOPE_PATTERNS.items() if pattern.search(normalized)
    }
    if re.search(r"(?:[a-z]:\\|\.?[a-z0-9_/-]*[a-z0-9_-])\.[a-z0-9]{1,12}\b", normalized):
        scopes.add("named_file")
        target_classes.add("filesystem")
    if "format" in action_verbs and "filesystem" in target_classes:
        action_classes.update({"destructive", "mutate"})

    question = _is_question(normalized)
    advisory = _is_advisory(normalized, question)
    explicit_nonexecution = _is_explicit_nonexecution(normalized)
    readonly_boundary = _has_readonly_boundary(normalized)
    negated = _is_negated_action(normalized, action_matches)
    approval_state = _approval_state(normalized, question)
    authorized = _is_authorized_action(
        normalized,
        action_matches,
        frozenset(action_classes),
        negated=negated,
        question=question,
        advisory=advisory,
        explicit_nonexecution=explicit_nonexecution,
    )
    apparent_change_obligation = _is_apparent_change_obligation(
        normalized,
        frozenset(action_classes),
        frozenset(target_classes),
        frozenset(scopes),
        authorized=authorized,
        negated=negated,
        question=question,
        advisory=advisory,
        explicit_nonexecution=explicit_nonexecution,
        readonly_boundary=readonly_boundary,
    )
    return RequestClause(
        text=text.strip(),
        normalized=normalized,
        connector=connector,
        negated=negated,
        question=question,
        advisory=advisory,
        explicit_nonexecution=explicit_nonexecution,
        readonly_boundary=readonly_boundary,
        approval_state=approval_state,
        action_verbs=action_verbs,
        action_classes=frozenset(action_classes),
        target_classes=frozenset(target_classes),
        scopes=frozenset(scopes),
        authorized=authorized,
        apparent_change_obligation=apparent_change_obligation,
        referential_target=_has_referential_target(normalized),
    )


def _is_apparent_change_obligation(
    normalized: str,
    action_classes: FrozenSet[str],
    target_classes: FrozenSet[str],
    scopes: FrozenSet[str],
    *,
    authorized: bool,
    negated: bool,
    question: bool,
    advisory: bool,
    explicit_nonexecution: bool,
    readonly_boundary: bool,
) -> bool:
    if negated or advisory or explicit_nonexecution or readonly_boundary:
        return False
    if _is_structural_whole_set_directive(
        normalized,
        action_classes,
        target_classes,
        scopes,
        question=question,
        negated=negated,
        advisory=advisory,
        explicit_nonexecution=explicit_nonexecution,
        readonly_boundary=readonly_boundary,
    ):
        return True
    if question and not authorized:
        return False
    if not _has_high_impact_surface(
        normalized,
        target_classes=target_classes,
        scopes=scopes,
    ):
        return False
    if action_classes & {"inspect", "transform"} and not action_classes & MUTATING_ACTION_CLASSES:
        return False
    if authorized:
        if action_classes & {"destructive", "execute"}:
            return True
        if "constructive" in action_classes:
            return False
        return bool(action_classes & MUTATING_ACTION_CLASSES)
    if action_classes:
        return False
    return _has_directive_speech_act(normalized, question)


def _is_structural_whole_set_directive(
    normalized: str,
    action_classes: FrozenSet[str],
    target_classes: FrozenSet[str],
    scopes: FrozenSet[str],
    *,
    question: bool,
    negated: bool,
    advisory: bool,
    explicit_nonexecution: bool,
    readonly_boundary: bool,
) -> bool:
    if (
        negated
        or _has_structural_action_negation(normalized)
        or advisory
        or explicit_nonexecution
        or readonly_boundary
    ):
        return False
    critical_targets = target_classes & {
        "cloud_resource",
        "database",
        "filesystem",
        "orchestrated_resource",
        "protection",
        "storage_device",
    }
    production_bulk = bool(
        scopes & {"production", "live"}
        and scopes & {"all", "recursive"}
    )
    root_recursive = bool(
        scopes & {"root", "system"}
        and "recursive" in scopes
        and target_classes & {"filesystem", "storage_device"}
    )
    protection_bypass = bool(
        scopes & {"production", "live"}
        and critical_targets
        and _has_protection_bypass_signal(normalized)
    )
    if not (production_bulk or root_recursive or protection_bypass):
        return False
    if "constructive" in action_classes and "destructive" not in action_classes:
        return False
    if _has_active_inspection_directive(normalized, action_classes):
        return False
    return _has_structural_execution_speech_act(normalized, question)


def _has_structural_execution_speech_act(normalized: str, question: bool) -> bool:
    if re.search(
        r"(?:\ud574|\ud558\uc5ec)\s*(?:\uc8fc\uc2ed\uc2dc\uc624|\uc8fc\uc2dc\uaca0(?:\uc2b5\ub2c8\uae4c|\uc5b4\uc694|\ub098\uc694)|"
        r"\uc8fc\uc154\uc57c\s*\ud569\ub2c8\ub2e4|\uc8fc\uc2dc\uba74\s*\uac10\uc0ac\ud558\uaca0\uc2b5\ub2c8\ub2e4)\s*[.!?]*$",
        normalized,
    ):
        return True
    return _has_directive_speech_act(normalized, question)


def _has_protection_bypass_signal(normalized: str) -> bool:
    return bool(
        re.search(
            r"\bwithout\s+(?:(?:keeping|retaining|taking)\s+)?(?:a\s+)?(?:backups?|snapshots?)\b",
            normalized,
        )
        or re.search(
            r"(?:\ubc31\uc5c5|\uc2a4\ub0c5\uc0f7)(?:\uc744|\ub97c)?\s*(?:\uc5c6\uc774|\ub0a8\uae30\uc9c0\s*\uc54a\uace0)",
            normalized,
        )
    )


def _has_active_inspection_directive(
    normalized: str,
    action_classes: FrozenSet[str],
) -> bool:
    if "inspect" not in action_classes or action_classes & MUTATING_ACTION_CLASSES:
        return False
    if re.search(
        r"^(?:(?:please|kindly|now)\s+)*(?:analy[sz]e|check|describe|explain|inspect|read|report|review|summarize)\b"
        r"|\b(?:can|could|would|will)\s+you\s+(?:analy[sz]e|check|describe|explain|inspect|read|report|review|summarize)\b"
        r"|\b(?:must|need(?:s)?\s+to|ha(?:s|ve)\s+to)\s+(?:analy[sz]e|check|describe|explain|inspect|read|report|review|summarize)\b",
        normalized,
    ):
        return True
    return bool(
        re.search(
            r"(?:\ud655\uc778|\uac80\ud1a0|\ub9ac\ubdf0|\uc810\uac80|\ucd94\uc801|\uc77d|\uc124\uba85|\ubcf4\uace0|\uc870\ud68c)"
            r"(?:\uc744|\ub97c)?\s*(?:\ud574\s*)?"
            r"(?:\uc8fc\uc138\uc694|\uc8fc\uc2ed\uc2dc\uc624|\uc8fc\uc2dc\uaca0\uc2b5\ub2c8\uae4c|\ud558\uc138\uc694|\ud574\uc57c\s*\ud569\ub2c8\ub2e4)\s*[.!?]*$",
            normalized,
        )
    )


def _has_structural_action_negation(normalized: str) -> bool:
    if re.match(
        r"^\s*(?:do\s+not|don't|dont|never)\b(?!\s+(?:fail|forget|hesitate|neglect)\b)",
        normalized,
    ):
        return True
    return bool(
        re.search(
            r"(?:\ud558\uc9c0\s*(?:\ub9d0|\ub9c8|\uc54a)|\ud558\uc9c0\ub9c8|\uae08\uc9c0)",
            normalized,
        )
    )


def _has_high_impact_surface(
    text: str,
    *,
    target_classes: FrozenSet[str] | None = None,
    scopes: FrozenSet[str] | None = None,
) -> bool:
    targets = target_classes or frozenset(
        name for name, pattern in _TARGET_PATTERNS.items() if pattern.search(text)
    )
    detected_scopes = scopes or frozenset(
        name for name, pattern in _SCOPE_PATTERNS.items() if pattern.search(text)
    )
    if targets & {"cloud_resource", "credential", "orchestrated_resource", "protection", "storage_device"}:
        return True
    if "database" in targets and detected_scopes & {"all", "production", "live"}:
        return True
    return bool(
        "filesystem" in targets
        and detected_scopes & {"all", "production", "live", "recursive", "root"}
    )


def _has_directive_speech_act(normalized: str, question: bool) -> bool:
    polite_request = bool(
        re.search(r"\b(?:can|could|would|will)\s+you\b|\b(?:please|kindly)\b", normalized)
    )
    obligation = bool(
        re.search(
            r"\b(?:must|need(?:s)?\s+to|ha(?:s|ve)\s+to|"
            r"(?:is|are)\s+(?:required|obligated|expected)\s+to|"
            r"(?:required|obligated|expected)\s+to)\b",
            normalized,
        )
    )
    korean_directive = bool(
        re.search(
            r"(?:\ud574\s*(?:\uc8fc\uc138\uc694|\uc918|\uc8fc\ub77c|\ub77c|\uc57c\s*(?:\ud569\ub2c8\ub2e4|\ud55c\ub2e4|\ud574))|"
            r"(?:\ud574|\ud558\uc5ec)\s*(?:\uc8fc\uc2dc\uaca0(?:\uc2b5\ub2c8\uae4c|\uc5b4\uc694|\ub098\uc694)|\uc8fc\uc154\uc57c\s*\ud569\ub2c8\ub2e4|\uc8fc\uc2dc\uba74\s*\uac10\uc0ac\ud558\uaca0\uc2b5\ub2c8\ub2e4)|"
            r"\ud558\uc138\uc694|\ud558\uc2ed\uc2dc\uc624|\ud558\ub77c|\ud574\uc57c\s*(?:\ud569\ub2c8\ub2e4|\ud55c\ub2e4|\ud574)|"
            r"\ud560\s*(?:\ud544\uc694|\uc758\ubb34)|\uc8fc\uc138\uc694|\uc918|\uc2dc\uc624|\ub77c)\s*[.!?]*$",
            normalized,
        )
    )
    if polite_request or obligation or korean_directive:
        return True
    if question:
        return False
    english_imperative = re.match(
        r"^(?:(?:now|immediately)\s+)*(?:[a-z][a-z0-9_-]*ly\s+)*[a-z][a-z0-9_-]*\b",
        normalized,
    )
    if not english_imperative:
        return False
    first = english_imperative.group(0).split()[-1]
    return first not in {
        "a",
        "an",
        "i",
        "it",
        "our",
        "that",
        "the",
        "their",
        "these",
        "they",
        "this",
        "those",
        "we",
        "you",
        "your",
    }


def _action_matches(normalized: str):
    matches = []
    tokens = list(_TOKEN_RE.finditer(normalized))
    token_starts = [token.start() for token in tokens]
    for phrase_match in _ENGLISH_ACTION_PHRASE_RE.finditer(normalized):
        phrase = re.sub(r"\s+", " ", phrase_match.group("phrase").lower())
        canonical = _ENGLISH_ACTION_PHRASE_CANONICAL[phrase]
        matches.append(
            (
                canonical,
                frozenset(_ENGLISH_ACTION_CLASSES[canonical]),
                phrase_match.start(),
                bisect_left(token_starts, phrase_match.start()),
            )
        )
    for index, token_match in enumerate(tokens):
        token = token_match.group(0).lower()
        canonical = _canonical_english_action(token)
        if canonical:
            if _is_nominal_action_use(normalized, tokens, index, canonical):
                continue
            classes = _ENGLISH_ACTION_CLASSES[canonical]
            if canonical == "update" and re.match(
                r"update\s+me\s+(?:on|about)\b",
                normalized[token_match.start() :],
            ):
                canonical = "report"
                classes = _ENGLISH_ACTION_CLASSES[canonical]
            matches.append(
                (canonical, frozenset(classes), token_match.start(), index)
            )
    for stem, classes in _KOREAN_ACTION_CLASSES.items():
        start = normalized.find(stem)
        while start != -1:
            token_index = bisect_left(token_starts, start)
            matches.append((stem, frozenset(classes), start, token_index))
            start = normalized.find(stem, start + len(stem))
    return sorted(matches, key=lambda item: (item[2], item[0]))


def _is_nominal_action_use(normalized: str, tokens, index: int, canonical: str) -> bool:
    """Ignore action-shaped nouns governed by an earlier construction verb."""
    if canonical in {"change", "patch", "reset", "update"} and index >= 1:
        prior = tokens[index - 1]
        prior_action = _canonical_english_action(prior.group(0).lower())
        between = normalized[prior.end() : tokens[index].start()]
        if (
            prior_action
            and _ENGLISH_ACTION_CLASSES[prior_action] & MUTATING_ACTION_CLASSES
            and re.search(r"(?:[,;]|\b(?:and|but|or|then)\b)", between) is None
        ):
            return True
    if canonical not in {"reset"} or index < 2:
        return False
    for prior in reversed(tokens[max(0, index - 4) : index]):
        prior_action = _canonical_english_action(prior.group(0).lower())
        if prior_action not in {"add", "build", "create", "implement"}:
            continue
        between = normalized[prior.end() : tokens[index].start()]
        return re.search(r"(?:[,;]|\b(?:and|but|then)\b)", between) is None
    return False


def _canonical_english_action(token: str) -> str:
    irregular = {
        "built": "build",
        "ran": "run",
        "written": "write",
        "wrote": "write",
    }
    if token in _ENGLISH_ACTION_CLASSES:
        return token
    if token in irregular:
        return irregular[token]
    candidates = []
    if token.endswith("ies"):
        candidates.append(token[:-3] + "y")
    if token.endswith("ing"):
        candidates.extend((token[:-3], token[:-3] + "e"))
    if token.endswith("ed"):
        candidates.extend((token[:-2], token[:-1]))
    if token.endswith("s"):
        candidates.append(token[:-1])
    return next((candidate for candidate in candidates if candidate in _ENGLISH_ACTION_CLASSES), "")


def _is_authorized_action(
    normalized: str,
    action_matches,
    action_classes: FrozenSet[str],
    *,
    negated: bool,
    question: bool,
    advisory: bool,
    explicit_nonexecution: bool,
) -> bool:
    if not action_classes & MUTATING_ACTION_CLASSES:
        return False
    active_mutating_matches = [
        match
        for match in action_matches
        if match[1] & MUTATING_ACTION_CLASSES
        and not _action_is_negated(normalized, match)
    ]
    if not active_mutating_matches or explicit_nonexecution or _is_modal_risk_description(normalized):
        return False

    polite_request = bool(
        re.search(r"\b(?:can|could|would|will)\s+you\b|\b(?:please|kindly)\b", normalized)
    )
    obligation = bool(
        re.search(
            r"\b(?:must|should|need(?:s)?\s+to|ha(?:s|ve)\s+to|"
            r"(?:is|are)\s+(?:required|obligated|expected)\s+to|"
            r"(?:required|obligated|expected)\s+to)\b",
            normalized,
        )
        or re.search(r"\bshouldn'?t\s+you\b", normalized)
    )
    korean_command = _has_korean_mutation_command(normalized, action_matches)
    lets_request = re.search(r"\blet(?:'|\u2019)?s\b", normalized) is not None
    reminder_obligation = any(
        re.search(r"\bdo\s+not\s+forget\s+to\s*$", normalized[:match[2]])
        for match in active_mutating_matches
    )
    if advisory and not polite_request:
        return False
    if question and not (polite_request or korean_command or lets_request):
        return False
    if polite_request or obligation or korean_command or lets_request or reminder_obligation:
        return True

    _, _, char_start, _ = active_mutating_matches[0]
    prefix = normalized[:char_start]
    if re.match(r"^(?:after|if|once|when)\b[\s\S]*,\s*$", prefix):
        return True
    prefix_tokens = [token.lower() for token in _TOKEN_RE.findall(normalized[:char_start])]
    if not prefix_tokens:
        return True
    allowed_prefixes = {"go", "ahead", "let", "lets", "now", "please", "kindly"}
    return all(token in allowed_prefixes or token.endswith("ly") for token in prefix_tokens)


def _is_negated_action(normalized: str, action_matches) -> bool:
    mutating_matches = [
        match for match in action_matches if match[1] & MUTATING_ACTION_CLASSES
    ]
    if not mutating_matches:
        return False
    return all(_action_is_negated(normalized, match) for match in mutating_matches)


def _action_is_negated(normalized: str, action_match) -> bool:
    verb, _, char_start, _ = action_match
    prefix = normalized[max(0, char_start - 72) : char_start]
    suffix = normalized[char_start + len(verb) : char_start + len(verb) + 28]

    if re.search(r"\bdo\s+not\s+forget\s+to\s*$", prefix):
        return False
    if re.match(r"^do\s+not\b", normalized):
        leading_scope = normalized[:char_start]
        negation_canceller = re.match(
            r"^do\s+not\s+(?:fail|forget|hesitate|neglect)\b",
            leading_scope,
        )
        scope_turn = re.search(
            r"\b(?:but|however|instead|then|yet)\b",
            leading_scope,
        )
        if not negation_canceller and not scope_turn:
            return True
    if re.search(
        r"(?:\bdo\s+not|\bdon't|\bdont|\bnever|\bmust\s+not|\bshould\s+not|\bwithout)"
        r"(?:\s+(?:ever|actually|directly))?\s*$",
        prefix,
    ):
        return True
    if re.search(
        r"\b(?:do\s+not|don't|dont|never|must\s+not|should\s+not)\b"
        r"[^.;!?]{0,64}\b(?:and|or)\s*$",
        prefix,
    ):
        return True
    if re.search(r"(?:^|\s)(?:\uc548|\ubabb)\s*$", prefix):
        return True
    if re.match(
        r"\s*(?:\uc740|\ub294|\uc744|\ub97c)?\s*(?:\ud558)?\uc9c0\s*(?:\ub9d0|\ub9c8|\uc54a)"
        r"|\s*(?:\ud558\uc9c0\ub9d0|\uae08\uc9c0)",
        suffix,
    ):
        return True
    return False


def _has_korean_mutation_command(normalized: str, action_matches) -> bool:
    for verb, classes, char_start, _ in action_matches:
        if verb not in _KOREAN_ACTION_CLASSES or not classes & MUTATING_ACTION_CLASSES:
            continue
        tail = normalized[char_start + len(verb) : char_start + len(verb) + 28]
        if re.match(
            r"\s*(?:"
            r"(?:\uc5b4|\uc544|\uc5ec)?\s*(?:\ud574\s*)?\uc8fc\uc2dc\uaca0(?:\uc2b5\ub2c8\uae4c|\uc5b4\uc694|\ub098\uc694)\s*(?=$|[.!?,:;\u2014\u2013])"
            r"|(?:\uc5b4|\uc544|\uc5ec)?\s*(?:\ud574\s*)?\uc8fc\uc2e4\s+\uc218\s+\uc788(?:\uc2b5\ub2c8\uae4c|\ub098\uc694|\uc744\uae4c\uc694)\s*(?=$|[.!?,:;\u2014\u2013])"
            r"|"
            r"(?:\uc5b4|\uc544|\uc5ec)?\s*(?:\uc904\ub798|\uc918|\uc8fc\uc138\uc694)\s*(?=$|[.!?,:;\u2014\u2013])"
            r"|"
            r"\ud574\s*(?:\uc8fc\uc138\uc694|\uc918|\uc8fc|\ub77c|\uc2ed\uc2dc\uc624|\uc138\uc694|\uc8fc\uc154\uc57c\s*\ud569\ub2c8\ub2e4|\uc8fc\uc5b4\uc57c\s*\ud569\ub2c8\ub2e4|\uc918\uc57c\s*\ud569\ub2c8\ub2e4)?\s*(?=$|[.!?,:;\u2014\u2013])"
            r"|(?:\uc8fc\uc138\uc694|\uc8fc\uc2ed\uc2dc\uc624|\uc8fc\uc2dc\uae30\s*\ubc14\ub78d\ub2c8\ub2e4|\uc8fc\uc154\uc57c\s*\ud569\ub2c8\ub2e4|\uc8fc\uc5b4\uc57c\s*\ud569\ub2c8\ub2e4|\uc918\uc57c\s*\ud569\ub2c8\ub2e4)\s*(?=$|[.!?,:;\u2014\u2013])"
            r"|\ud558\ub77c|\ud558\uc790|\ud574\uc57c|\ud558\uc5ec\uc57c|\ud560\s*\ud544\uc694|\ud560\s*\uc758\ubb34"
            r"|(?:\uc8fc\uc138\uc694|\uc918|\uc8fc|\ub77c|\uc2ed\uc2dc\uc624|\uc138\uc694)(?=$|[.!?,:;])"
            r"|(?=$|[.!?,:;]))",
            tail,
        ):
            return True
    return False


def _is_modal_risk_description(normalized: str) -> bool:
    if re.search(r"\b(?:can|could|would|will)\s+you\b", normalized):
        return False
    return bool(
        re.search(
            r"\b(?:risk\s+(?:is\s+)?(?:that\s+)?|may|might|could|can\s+accidentally)\b",
            normalized,
        )
    )


def _is_question(normalized: str) -> bool:
    if (
        "?" not in normalized
        and re.match(r"^(?:after|if|once|when)\b[\s\S]*,\s*", normalized)
    ):
        return False
    return bool(
        "?" in normalized
        or re.search(
            r"^(?:why|how|what|which|when|where|whether)\b"
            r"|^do\s+(?:i|you|we|they|these|those|the)\b"
            r"|^does\s+(?:it|this|that|he|she|the)\b"
            r"|^(?:is|are|can|could|would|should)\s+(?:i|you|we|they|it|this|that|the)\b",
            normalized,
        )
        or re.search(
            r"(?:\uc65c|\uc5b4\ub5bb\uac8c|\ubb34\uc5c7|\ubb50|\uc5b4\ub5a4|\uc5b8\uc81c|\uc5b4\ub514|\uc778\uc9c0|\uac74\uac00|\uc77c\uae4c|\ud560\uae4c|\ub418\ub098|\ub418\ub0d0|\uac19\ub2e4)\s*[?.!]*$",
            normalized,
        )
    )


def _is_advisory(normalized: str, question: bool) -> bool:
    return bool(
        _has_outer_explanatory_act(normalized)
        or re.search(
            r"\b(?:advise|advice|recommend|example\s+only|for\s+example\s+only|"
            r"advisory\s+only|whether\s+(?:i|we)\s+should|should\s+(?:i|we))\b",
            normalized,
        )
        or re.search(
            r"(?:\uc870\uc5b8|\uc124\uba85\ub9cc|\ubb38\uad6c|\ud45c\ud604|\ud574\ub3c4\s*\ub418\ub294\uc9c0|\ud574\uc57c\s*\ud558\ub098|\ud560\uae4c)",
            normalized,
        )
        or (question and re.search(r"\bshould\s+(?:i|we)\b", normalized))
    )


def _is_explicit_nonexecution(normalized: str) -> bool:
    return bool(
        re.search(
            r"\b(?:do\s+not|don't|dont|never)\s+(?:apply|deploy|execute|implement|run)\b"
            r"|\bdo\s+not\s+perform\b"
            r"|\bwithout\s+(?:applying|deploying|executing|implementing|performing|running)\b"
            r"|\bno\s+(?:action|execution|operation)(?:\s+is)?\s+requested\b"
            r"|\bnot\s+an?\s+(?:action|execution|implementation|operation)\s+request\b",
            normalized,
        )
        or re.search(
            r"(?:\uc2e4\ud589|\uc801\uc6a9|\ubc18\uc601|\ubc30\ud3ec|\uad6c\ud604)(?:\uc740|\ub294|\uc744|\ub97c)?\s*\ud558\uc9c0\s*(?:\ub9d0|\ub9c8)"
            r"|(?:\uc2e4\ud589|\uc801\uc6a9|\ubc18\uc601|\ubc30\ud3ec|\uad6c\ud604|\uc791\uc5c5)\s*\uc694\uccad(?:\uc740|\uc774)?\s*(?:\uc544\ub2c8|\uc544\ub2d8)",
            normalized,
        )
    )


def _has_readonly_boundary(normalized: str) -> bool:
    return bool(
        re.search(
            r"\b(?:read[ -]?only|do\s+not|don't|dont|never)\s+(?:apply|deploy|edit|execute|modify|change|implement|run|write)\b"
            r"|\b(?:no|without)\s+(?:edits?|changes?|implementation|file\s+changes?)\b"
            r"|\b(?:report|analysis|review)\s+only\b",
            normalized,
        )
        or re.search(
            r"(?:\uc218\uc815|\ubcc0\uacbd|\uad6c\ud604|\uc2e4\ud589|\uc801\uc6a9|\ubc18\uc601|\ubc30\ud3ec|\ud30c\uc77c\s*\ubcc0\uacbd)(?:\uc740|\ub294|\uc744|\ub97c)?\s*\ud558\uc9c0\s*(?:\ub9d0|\ub9c8)"
            r"|(?:\ubc14\uafb8|\uace0\uce58|\uc190\ub300|\uac74\ub4dc\ub9ac)\uc9c0\s*(?:\ub9d0|\ub9c8)"
            r"|(?:\uc218\uc815|\ubcc0\uacbd)\s*\uc5c6\uc774|(?:\ubcf4\uace0|\ub9ac\ubdf0|\uac80\ud1a0|\ud655\uc778)\ub9cc",
            normalized,
        )
    )


def _has_outer_explanatory_act(normalized: str) -> bool:
    english_inspection = re.search(
        r"\b(?:analy[sz]e|describe|explain|report|review|summarize)\b",
        normalized,
    )
    english_context = re.search(
        r"\b(?:danger|dangerous|document|note|quoted|reason|risk|training|wording)\b",
        normalized,
    )
    english_exclusive = re.search(r"\b(?:just|only)\b", normalized)
    korean_inspection = re.search(
        r"(?:\ubd84\uc11d|\uc124\uba85|\ubcf4\uace0|\ub9ac\ubdf0|\uac80\ud1a0|\uc694\uc57d)",
        normalized,
    )
    korean_context = re.search(
        r"(?:\ubb38\uc11c|\uba54\ubaa8|\uc778\uc6a9|\ubb38\uad6c|\uc774\uc720|\uc704\ud5d8|\ud6c8\ub828)",
        normalized,
    )
    korean_exclusive = "\ub9cc" in normalized
    return bool(
        english_inspection and (english_context or english_exclusive)
        or korean_inspection and (korean_context or korean_exclusive)
    )


def _approval_state(normalized: str, question: bool) -> str:
    has_approval = bool(
        re.search(r"\b(?:accept(?:ed|ance)?|approv(?:e|ed|al)|authoriz(?:e|ed|ation))\b", normalized)
        or re.search(r"(?:\uc2b9\uc778|\uc218\ub77d|\ud5c8\uc6a9|\ud655\uc815)", normalized)
    )
    if not has_approval:
        return "absent"
    denied = bool(
        re.search(
            r"\b(?:not|never|un)\s*-?(?:approved|accepted|authorized)\b|\bunapproved\b"
            r"|\b(?:isn't|isnt|aren't|arent|wasn't|wasnt|weren't|werent)\s+"
            r"(?:approved|accepted|authorized)\b",
            normalized,
        )
        or re.search(
            r"(?:\uc2b9\uc778|\uc218\ub77d|\ud5c8\uc6a9).{0,16}"
            r"(?:\uc544\ub2c8|\uc544\ub2d9|\uc548\s*\ub410|\ub418\uc9c0\s*\uc54a|\uac70\ubd80)",
            normalized,
        )
    )
    if denied:
        return "denied"
    pending = bool(
        re.search(
            r"\b(?:approval|acceptance|authorization)\s+(?:is\s+)?(?:still\s+|currently\s+)?(?:awaiting|pending|outstanding)\b"
            r"|\b(?:awaiting|pending)\s+(?:approval|acceptance|authorization)\b",
            normalized,
        )
        or re.search(
            r"(?:\uc2b9\uc778|\uc218\ub77d|\ud5c8\uc6a9).{0,12}(?:\ub300\uae30|\ubcf4\ub958|\ubbf8\uc644\ub8cc|\uc544\uc9c1)",
            normalized,
        )
    )
    if pending:
        return "pending"
    if question:
        return "questioned"
    return "granted"


def _has_referential_target(normalized: str) -> bool:
    return bool(
        re.search(
            r"\b(?:apply|change|correct|delete|drop|execute|fix|implement|modify|patch|remove|repair|run|update)\s+"
            r"(?:it|that|this|them|these|those)\b"
            r"|\b(?:apply|deploy|execute|implement|run)\s+(?:the\s+)?(?:batch|changes?|edits?|patch|revision)\b"
            r"|\bcarry\s+(?:the\s+)?(?:remaining|reviewed|approved|current)?\s*(?:changes?|edits?|patch|revision)\s+into\b"
            r"|\bproceed\s+with\s+(?:it|that|this|the\s+current\s+(?:change|patch)|current\s+(?:change|patch))\b"
            r"|\bcarry\s+(?:it|that|this)\s+out\b"
            r"|\b(?:current|approved)\s+(?:change|patch)\b"
            r"|(?:\uadf8\uac70|\uadf8\uac83|\uadf8\uac78|\uc774\uac70|\uc774\uac83|\uc774\uac78|\uc800\uac70|\uc800\uac83|\uc800\uac78).{0,20}"
            r"(?:\uace0\uce58|\uad6c\ud604|\ubc18\uc601|\ubcf4\uc644|\ubcc0\uacbd|\uc0ad\uc81c|\uc218\uc815|\uc2e4\ud589|\uc801\uc6a9|\uc81c\uac70|\uc9c0\uc6b0|\ud328\uce58)"
            r"|(?:\ud604\uc7ac\s*\ud328\uce58|\uadf8\s*\ubcc0\uacbd)",
            normalized,
        )
    )


def _strict_execution_approval(context: Mapping[str, object]) -> bool | None:
    values = []
    structured = context.get("request_intent")
    if isinstance(structured, Mapping):
        values.append(structured.get("execution_authorization"))
    for key in (
        "execution_approved",
        "execution_authorized",
        "execution_accepted",
        "implementation_approved",
        "separate_implementation_approval",
        "change_approved",
        "change_accepted",
    ):
        values.append(context.get(key))
    exact = [value for value in values if type(value) is bool]
    if any(value is False for value in exact):
        return False
    if any(value is True for value in exact):
        return True
    return None


def _connector_kind(connector: str) -> str:
    normalized = _normalize(connector)
    if normalized in {"but", "however", "yet", "\ud558\uc9c0\ub9cc", "\uadf8\ub7ec\ub098", "\uadf8\ub7f0\ub370", "\ub9d0\uace0"}:
        return "adversative"
    return "sequence"


def _mask(text: str, spans) -> str:
    chars = list(text)
    for span in spans:
        chars[span.start : span.end] = " " * (span.end - span.start)
    return "".join(chars)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", _canonicalize_text(text).strip().lower())


def _canonicalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").translate(_PUNCTUATION_TRANSLATION)
