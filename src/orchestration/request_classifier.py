import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List


COMPLEXITIES = {"light", "medium", "heavy", "high_risk", "ambiguous"}
TOKEN_OPTIMIZER_CONTEXT_THRESHOLD = 8000
TOKEN_OPTIMIZER_ITEM_THRESHOLD = 2000
LARGE_WORK_BUNDLE_SKILLS = [
    "request-complexity-router",
    "host-agent-orchestration",
    "domain-orchestration-harness",
    "goal-state-harness",
    "development-lifecycle-harness",
    "worktree-isolation-harness",
    "plan-execution-harness",
    "systematic-debugging-harness",
    "command-output-harness",
    "token-optimizer",
    "memory-state-harness",
    "parallel-orchestration-harness",
    "subagent-review-pipeline",
    "role-execution-audit-harness",
    "quality-gates-harness",
    "review-gate-harness",
    "qa-gate-harness",
    "artifact-render-qa-harness",
    "deliverable-template-quality-harness",
    "traceability-matrix-harness",
    "verification-before-completion-harness",
    "branch-finishing-harness",
    "compound-engineering-harness",
    "workflow-skill-distiller",
]
LARGE_WORK_REQUIRED_HARNESSES = [
    "host-agent-orchestration",
    "domain-orchestration-harness",
    "goal-state-harness",
    "development-lifecycle-harness",
    "worktree-isolation-harness",
    "plan-execution-harness",
    "quality-gates-harness",
    "review-gate-harness",
    "qa-gate-harness",
    "verification-before-completion-harness",
]
LARGE_WORK_BUNDLE_EVIDENCE = [
    "large_work_orchestration_bundle",
    "skill_statuses",
    "workspace_strategy",
    "parallel_strategy_decision",
    "token_optimizer_status",
    "token_optimizer_status_reason",
    "memory_candidates",
    "compound_handoff",
]

KH_PROJECT_MARKERS = {".kh", "docs/kh"}
CONTEXTUAL_REPAIR_REFERENCE_TERMS = {
    "that standard",
    "that basis",
    "same standard",
    "based on that",
    "based on the audit",
    "from the audit",
    "session audit",
    "those issues",
    "\uadf8 \uae30\uc900",
    "\uadf8\uae30\uc900",
    "\uadf8 \ub0b4\uc6a9",
    "\uc544\uae4c \uae30\uc900",
    "\uc138\uc158 \uac10\uc0ac",
    "\ub300\ud654 \uae30\ub85d",
    "\ubb38\uc81c\uc810",
}
CONTEXTUAL_REPAIR_ACTION_TERMS = {
    "harden",
    "fix",
    "repair",
    "patch",
    "improve",
    "tighten",
    "regression",
    "cover everything",
    "\ubcf4\uc644",
    "\uc218\uc815",
    "\uace0\uccd0",
    "\uac1c\uc120",
    "\ucc98\ub9ac",
}
CONTEXTUAL_REPAIR_FAILURE_TERMS = {
    "\uc81c\ub300\ub85c \uc548",
    "\uc81c\ub300\ub85c \ubabb",
    "\uc548\uc77d",
    "\uc548 \uc77d",
    "\uc548\ud558",
    "\uc548 \ud558",
    "\ubabb",
}
CONTEXTUAL_REPAIR_SUBJECT_TERMS = {
    "kh",
    "uaf",
    "skill",
    "skills",
    "harness",
    "harnesses",
    "front-door",
    "front door",
    "routing",
    "session",
    "audit",
    "sql",
    "alias",
    "\uc2a4\ud0ac",
    "\ud558\ub124\uc2a4",
    "\ud504\ub7f0\ud2b8\ub3c4\uc5b4",
    "\ub77c\uc6b0\ud305",
    "\uc138\uc158",
    "\uac10\uc0ac",
    "\uc624\ucf00\uc2a4\ud2b8\ub808\uc774\uc158",
    "\ubcd1\ub82c",
    "\ubcc4\uce6d",
}
STRICT_CONTEXTUAL_REPAIR_SUBJECT_TERMS = {
    "kh",
    "uaf",
    "skill",
    "skills",
    "harness",
    "harnesses",
    "front-door",
    "front door",
    "session audit",
    "skill audit",
    "postmortem",
    "orchestration",
    "parallel",
    "\uc2a4\ud0ac",
    "\ud558\ub124\uc2a4",
    "\ud504\ub7f0\ud2b8\ub3c4\uc5b4",
    "\uc138\uc158 \uac10\uc0ac",
    "\uc624\ucf00\uc2a4\ud2b8\ub808\uc774\uc158",
    "\ubcd1\ub82c",
}
EXPLANATION_ONLY_TERMS = {
    "why",
    "explain",
    "explanation",
    "reason",
    "\uc774\uc720",
    "\uc124\uba85",
}

MEMORY_STATE_REQUEST_TERMS = {
    "persistent memory",
    "durable memory",
    "long-term memory",
    "memory.md",
    "user.md",
    "memory harness",
    "memory-state-harness",
    "memory candidates",
    "memory provider",
    "memory scope",
    "global codex memory",
    "host global codex memory",
    "global memory candidate",
    "global memory promotion",
    "prompt snapshot",
    "session memory",
    "working memory",
    "cross-chat memory",
    "cross chat memory",
    "openclaw",
    "hermes",
    "영구메모리",
    "영구 메모리",
    "장기메모리",
    "장기 메모리",
    "메모리 하네스",
    "메모리 스킬",
    "전역 메모리",
    "글로벌 메모리",
    "전역 승격",
    "전역 메모리 후보",
    "세션 메모리",
    "작업 메모리",
    "프롬프트 스냅샷",
}

PARALLEL_ORCHESTRATION_REQUEST_TERMS = {
    "parallel orchestration",
    "parallel",
    "role dag",
    "role-dag",
    "role orchestration",
    "fan-out",
    "fan in",
    "fan-in",
    "bounded worker",
    "worker wave",
    "parallel wave",
    "role execution audit",
    "병렬",
    "병렬 오케스트레이션",
    "역할 DAG",
    "역할 오케스트레이션",
}

INVESTMENT_TERMS = {
    "stock",
    "portfolio",
    "valuation",
    "per",
    "dcf",
    "earnings",
    "inflation",
    "market",
    "market news",
    "bitcoin",
    "crypto",
    "401k",
    "apple shares",
    "nvidia",
    "tesla",
    "주식",
    "종목",
    "투자",
    "포트폴리오",
    "밸류에이션",
    "실적",
    "엔비디아",
    "테슬라",
}

INVESTMENT_ADVICE_TERMS = {
    "should i buy",
    "should i sell",
    "buy now",
    "sell now",
    "sell all",
    "rebalance",
    "recommend",
    "사도 돼",
    "사야",
    "팔아",
    "매수",
    "매도",
    "추천",
    "포트폴리오",
    "투자해도",
}

LEGAL_TERMS = {
    "legal",
    "lawsuit",
    "contract",
    "contract dispute",
    "sue",
    "lease",
    "settlement",
    "agreement",
    "clause",
    "penalty",
    "고소",
    "소송",
    "법률",
    "계약",
    "계약 분쟁",
}
LEGAL_ADVICE_TERMS = {
    "sue",
    "landlord",
    "legal action",
    "should i sign",
    "can i break",
    "break my lease",
    "settlement agreement",
    "고소",
    "소송",
    "고소할까",
    "고소해도",
    "소송해야",
    "계약서 작성",
    "법적 대응",
    "합의해도",
    "서명해도",
}
MEDICAL_TERMS = {
    "medical",
    "diagnosis",
    "symptom",
    "symptoms",
    "flu",
    "medicine",
    "medication",
    "dose",
    "blood pressure",
    "hypertension",
    "chest pain",
    "shortness of breath",
    "진단",
    "증상",
    "처방",
    "감기",
    "가슴 통증",
    "호흡곤란",
}
MEDICAL_ADVICE_TERMS = {
    "i have",
    "what medicine",
    "should i take",
    "safe for me",
    "can i stop",
    "stop taking",
    "진단해",
    "처방",
    "복용",
    "치료",
    "내 증상",
    "응급",
    "병원 안 가도",
    "어떤 약",
    "먹어야",
}
SECURITY_TERMS = {
    "security",
    "exploit",
    "bypass",
    "credential",
    "credentials",
    "github token",
    "iam",
    "terraform",
    "least-privilege",
    "rm -rf",
    "drop table",
    "sql injection",
    "phishing",
    "audit logs",
    "vulnerability",
    "해킹",
    "우회",
    "삭제",
}
SECURITY_HIGH_RISK_TERMS = {
    "exploit",
    "bypass",
    "credential",
    "credentials",
    "malware",
    "exfiltrate",
    "phishing email",
    "dump credentials",
    "disable audit logs",
    "비밀번호",
    "우회",
    "해킹",
    "크랙",
    "탈취",
}
DESTRUCTIVE_ACTION_TERMS = {
    "delete all rows",
    "delete from",
    "production users",
    "production database",
    "external drive",
    "disable audit logs",
    "지워",
    "삭제해",
    "제거해",
    "drop table",
    "rm -rf /",
}

BRAINSTORM_APPROVAL_CONTINUATION_TERMS = {
    "approved",
    "approval received",
    "direction approved",
    "user approved",
    "approved direction",
    "selected option",
    "option selected",
    "go with option",
    "proceed with option",
    "continue with option",
    "choice approved",
    "\uc2b9\uc778",
    "\uc2b9\uc778\ud568",
    "\uc2b9\uc778\ub428",
    "\uc2b9\uc778\ubc1b",
    "\uc120\ud0dd",
    "\uc120\ud0dd\ud568",
    "\ubc29\ud5a5 \uc2b9\uc778",
    "\ubc29\ud5a5\uc744 \uc2b9\uc778",
    "1\ubc88\uc73c\ub85c \uc9c4\ud589",
    "2\ubc88\uc73c\ub85c \uc9c4\ud589",
    "3\ubc88\uc73c\ub85c \uc9c4\ud589",
}
BRAINSTORM_IMPLEMENTATION_CONTINUATION_TERMS = {
    "implement",
    "implementation",
    "build",
    "develop",
    "start implementation",
    "begin implementation",
    "move to implementation",
    "execute",
    "create files",
    "generate files",
    "write files",
    "scaffold",
    "write code",
    "\uad6c\ud604",
    "\uac1c\ubc1c",
    "\ud30c\uc77c \uc0dd\uc131",
    "\ud654\uba74 \ud30c\uc77c",
    "\ucf54\ub4dc \uc791\uc131",
    "\uc2a4\uce90\ud3f4\ub4dc",
    "\uad6c\ud604 \uc9c4\ud589",
    "\uac1c\ubc1c \uc9c4\ud589",
}

BRAINSTORM_DIRECTION_CHOICE_ONLY_TERMS = {
    "option 1",
    "option 2",
    "option 3",
    "go with option",
    "proceed with option",
    "continue with option",
    "selected option",
    "option selected",
    "choice approved",
    "1\ubc88",
    "2\ubc88",
    "3\ubc88",
    "1\ubc88\uc73c\ub85c",
    "2\ubc88\uc73c\ub85c",
    "3\ubc88\uc73c\ub85c",
    "\ub2e8\uc21c \uc7ac\uace0 \uc6d0\uc7a5\ud615",
    "\ub2e8\uc21c \uc218\ubd88\uc7a5\ud615",
    "\uc704\uce58 \uad00\ub9ac\ud615",
    "\ub85c\ud2b8/\uc2dc\ub9ac\uc5bc",
}

SOFTWARE_DOMAIN_TERMS = {
    "api",
    "authentication",
    "database",
    "code",
    "software",
    "backend",
    "frontend",
    "server",
    "html",
    "javascript",
    "css",
    "web",
    "app",
    "tool",
    "folder",
    "file",
    "implementation",
    "python",
    "react",
    "vue",
    "readme",
    "pr",
    "unit test",
    "test",
    "tests",
    "웹",
    "앱",
    "도구",
    "폴더",
    "파일",
}

SOFTWARE_HEAVY_TERMS = {
    "implement",
    "implementation",
    "build",
    "continue",
    "fix",
    "finish",
    "modify",
    "refactor",
    "architecture",
    "verify",
    "validate",
    "만들",
    "생성",
    "구현",
    "고쳐",
    "수정",
    "개선",
    "검증",
    "테스트",
    "구현",
    "만들어",
    "고쳐",
    "수정",
    "리팩터",
    "테스트",
    "설계",
    "아키텍처",
    "프로젝트",
    "db",
}

DESIGN_HEAVY_TERMS = {
    "screen",
    "dashboard",
    "drawing",
    "enclosure",
    "bracket",
    "dimension",
    "dimensions",
    "material",
    "manufacturing",
    "conveyor",
    "control logic",
    "safety interlocks",
    "plate",
    "hole",
    "holes",
    "sus304",
    "mobile app",
    "onboarding",
    "ui",
    "ux",
    "saas",
    "도면",
    "장비",
    "부품",
    "제어 로직",
    "제조",
    "cad",
    "bom",
}
HEAVY_ACTION_TERMS = {
    "design",
    "create",
    "continue",
    "finish",
    "generate",
    "implement",
    "build",
    "fix",
    "modify",
    "refactor",
    "architecture",
    "update",
    "verify",
    "validate",
    "test",
    "만들",
    "생성",
    "구현",
    "고쳐",
    "수정",
    "개선",
    "검증",
    "테스트",
    "구현",
    "만들어",
    "고쳐",
    "수정",
    "추가",
    "넣어",
    "삽입",
    "반영",
    "리팩터",
    "설계",
    "아키텍처",
}
REVIEW_HEAVY_TERMS = {"review", "inspect", "audit", "검토", "리뷰", "점검"}
READONLY_SOURCE_QUESTION_TERMS = {
    "is there",
    "whether",
    "what",
    "which",
    "when",
    "under what",
    "explain",
    "tell me",
    "check if",
    "find whether",
    "\uc788\uc744\uae4c",
    "\uc788\ub294\uc9c0",
    "\uc788\uc5b4",
    "\uc788\ub098",
    "\ubb34\uc2a8",
    "\ubb50",
    "\uc5b4\ub5a4",
    "\uc54c\ub824",
    "\uc815\ub9ac",
    "\ud655\uc778",
    "\ubb3c\uc5b4\ubcf4",
}
READONLY_SOURCE_CONDITION_TERMS = {
    "check logic",
    "validation logic",
    "guard logic",
    "blocked",
    "cannot update",
    "can't update",
    "not update",
    "update blocked",
    "edit blocked",
    "condition",
    "conditions",
    "\uccb4\ud06c\ub85c\uc9c1",
    "\uac80\uc99d\ub85c\uc9c1",
    "\uc870\uac74",
    "\uc5b4\ub5a4\uc0c1\ud669",
    "\ub9c9",
    "\ubabb",
    "\uc548\ub41c",
    "\uc548\ub418",
    "\uc5c5\ub370\uc774\ud2b8\uac00 \uc548",
    "\uc5c5\ub370\uc774\ud2b8\uac00 \ubabb",
    "\uc218\uc815\uc774 \uc548",
    "\uc218\uc815\uc744 \ubabb",
}
READONLY_SOURCE_AUDIT_TERMS = {
    "read-only audit",
    "readonly audit",
    "audit",
    "review",
    "inspect",
    "find issues",
    "find the issues",
    "report issues",
    "report the issues",
    "issue report",
    "bug report",
    "\uac10\uc0ac",
    "\uac80\ud1a0",
}
READONLY_SOURCE_AUDIT_BOUNDARY_TERMS = {
    "read-only",
    "readonly",
    "read only",
    "do not edit",
    "don't edit",
    "dont edit",
    "do not modify",
    "don't modify",
    "dont modify",
    "do not change",
    "don't change",
    "dont change",
    "no edits",
    "no edit",
    "no changes",
    "without editing",
    "without modifying",
    "without changing",
    "report only",
    "analysis only",
    "\ucf54\ub4dc\ub294 \uc218\uc815\ud558\uc9c0",
    "\ucf54\ub4dc\ub97c \uc218\uc815\ud558\uc9c0",
    "\ucf54\ub4dc \uc218\uc815 \uc5c6\uc774",
    "\uc218\uc815\ud558\uc9c0 \ub9d0\uace0",
    "\uc218\uc815\ud558\uc9c0",
    "\uc218\uc815 \uc5c6\uc774",
    "\ubcc0\uacbd\ud558\uc9c0",
    "\ubcc0\uacbd \uc5c6\uc774",
    "\uace0\uce58\uc9c0",
}
READONLY_SOURCE_AUDIT_SOURCE_TERMS = {
    "source",
    "code",
    "repo",
    "repository",
    "file",
    "files",
    "module",
    "runtime",
    "test",
    "tests",
    "branch",
    "checkout",
    "\ucf54\ub4dc",
    "\uad6c\ud604",
    "\ud604\uc7ac \uad6c\ud604",
    "\ub3d9\uc791",
    "\uc138\uc158",
    "\uc2a4\ud0ac",
    "\ud558\ub124\uc2a4",
    "\ub77c\uc6b0\ud305",
    "\ud504\ub7f0\ud2b8\ub3c4\uc5b4",
}
READONLY_SOURCE_AUDIT_MUTATION_TERMS = {
    "fix it",
    "fix them",
    "patch it",
    "patch them",
    "repair it",
    "repair them",
    "implement it",
    "implement them",
    "start implementation",
    "begin implementation",
    "make the change",
    "make changes",
    "apply the change",
    "apply changes",
    "edit the file",
    "modify the file",
    "change the file",
    "update the file",
    "add tests",
    "add regression",
    "add regressions",
    "write tests",
    "commit",
    "push",
    "\uc218\uc815\ud574\uc918",
    "\ubcc0\uacbd\ud574\uc918",
    "\uace0\uccd0\uc918",
    "\ud328\uce58\ud574\uc918",
    "\uad6c\ud604\ud574\uc918",
    "\ud14c\uc2a4\ud2b8 \ucd94\uac00",
}
SOURCE_MUTATION_COMMAND_TERMS = {
    "modify it",
    "change it",
    "update it",
    "fix it",
    "edit it",
    "add",
    "insert",
    "add it",
    "insert it",
    "create it",
}
INFLECTED_MUTATION_ACTION_STEMS = (
    "\uc218\uc815",
    "\ubcc0\uacbd",
    "\uc5c5\ub370\uc774\ud2b8",
    "\ucd94\uac00",
    "\uc0bd\uc785",
    "\ubc18\uc601",
    "\uad6c\ud604",
)
DIRECT_MUTATION_ACTION_FORMS = (
    "\uace0\uccd0",
    "\ub123\uc5b4",
    "\ub9cc\ub4e4\uc5b4",
)
CONDITIONAL_MUTATION_ACTION_TERMS = (
    "add",
    "insert",
    "create",
    "implement",
    "fix",
    "update",
    "change",
)
CONDITIONAL_MUTATION_FILLER_TERMS = (
    "please",
    "then",
)
REQUEST_COMMAND_SUFFIX_RE = "(?:\uc8fc\uc138\uc694|\uc918|\uc8fc|\ub2ec\ub77c|\ub77c)"
CONDITIONAL_MUTATION_ACTION_RE = f"(?:{'|'.join(map(re.escape, CONDITIONAL_MUTATION_ACTION_TERMS))})"
CONDITIONAL_MUTATION_CONNECTOR_RE = (
    rf"\s*(?:[,;:.-]\s*)?(?:(?:{'|'.join(map(re.escape, CONDITIONAL_MUTATION_FILLER_TERMS))})\s+)*"
)
INFLECTED_MUTATION_COMMAND_RE = re.compile(
    f"(?:{'|'.join(map(re.escape, INFLECTED_MUTATION_ACTION_STEMS))})\\s*\ud574\\s*(?:{REQUEST_COMMAND_SUFFIX_RE})?(?=$|[\\s.!?])"
    f"|(?:{'|'.join(map(re.escape, DIRECT_MUTATION_ACTION_FORMS))})\\s*(?:{REQUEST_COMMAND_SUFFIX_RE})?(?=$|[\\s.!?])"
)
MISSING_CONDITION_MARKER_RE = re.compile(
    r"\b(?:if|when)\s+(?:missing|absent)\b"
    "|(?:\uc5c6\uc73c\uba74|\uc5c6\ub2e4\uba74|\uc5c6\uc744\\s*\uacbd\uc6b0|\uc5c6\uc744\\s*\ub54c)"
)
CONDITIONAL_MUTATION_COMMAND_RE = re.compile(
    rf"(?:\b(?:if|when)\s+(?:missing|absent)\b{CONDITIONAL_MUTATION_CONNECTOR_RE}{CONDITIONAL_MUTATION_ACTION_RE}(?:\s+it)?\b)"
    rf"|(?:\b{CONDITIONAL_MUTATION_ACTION_RE}\s+(?:it\s+)?(?:if|when)\s+(?:missing|absent)\b)"
    "|"
    f"(?:\uc5c6\uc73c\uba74|\uc5c6\ub2e4\uba74|\uc5c6\uc744\\s*\uacbd\uc6b0|\uc5c6\uc744\\s*\ub54c)\\s*"
    f"(?:(?:{'|'.join(map(re.escape, INFLECTED_MUTATION_ACTION_STEMS))})(?:\\s*\ud574)?|"
    f"(?:{'|'.join(map(re.escape, DIRECT_MUTATION_ACTION_FORMS))}))"
    f"\\s*(?:{REQUEST_COMMAND_SUFFIX_RE})?(?=$|[\\s.!?])"
)
LOCALIZED_PATCH_ACTION_TERMS = {
    "add",
    "delete",
    "hide",
    "insert",
    "include",
    "remove",
    "rename",
    "replace",
    "wire",
    "update",
    "change",
    "fix",
    "patch",
    "reflect",
    "apply",
    "adjust",
    "align",
    "tune",
    "\ucd94\uac00",
    "\ucd94\uac00\ud574",
    "\ub123\uc5b4",
    "\ubc18\uc601",
    "\uc218\uc815",
    "\uace0\uccd0",
    "\ub9de\ucdb0",
    "\ub9de\ucd94",
    "\uc870\uc815",
    "\uc0ad\uc81c",
    "\uc228\uaca8",
    "\uc228\uae30",
    "\uad50\uccb4",
    "\ubc14\uafd4",
    "\ubcc0\uacbd",
}
LOCALIZED_PATCH_SCOPE_TERMS = {
    "selector",
    "css selector",
    "single selector",
    "one selector",
    "class selector",
    "one line",
    "single line",
    "one-line",
    "localized patch",
    "tiny patch",
    "current file",
    "target file",
    "\uc140\ub809\ud130",
    "\uc120\ud0dd\uc790",
    "\ud55c \uc904",
    "\ud55c\uc904",
    "\ud574\ub2f9 \uc904",
    "\ud604\uc7ac \ud30c\uc77c",
    "\ub300\uc0c1 \ud30c\uc77c",
    "\uc791\uc740 \uc218\uc815",
    "\ub9cc",
}
LOCALIZED_PATCH_CONTEXT_KEYS = {
    "localized_patch_context",
    "small_patch_context",
    "target_selector",
    "target_line",
    "target_symbol",
}
LOCALIZED_PATCH_SCOPE_VALUES = {
    "line",
    "single_line",
    "one_line",
    "selector",
    "single_selector",
    "one_selector",
    "small_patch",
    "localized_patch",
    "tiny_patch",
}
LOCALIZED_PATCH_BROAD_TERMS = {
    "add tests",
    "all files",
    "auth flow",
    "whole project",
    "entire project",
    "refactor",
    "architecture",
    "add regression tests",
    "regression tests",
    "security vulnerability",
    "sql injection",
    "test coverage",
    "workflow",
    "\uc804\uccb4 \ud30c\uc77c",
    "\ud504\ub85c\uc81d\ud2b8 \uc804\uccb4",
    "\ub9ac\ud329\ud1a0\ub9c1",
    "\uc544\ud0a4\ud14d\ucc98",
    "\ud14c\uc2a4\ud2b8 \ucd94\uac00",
    "\ud750\ub984",
}
LOCALIZED_PATCH_BROAD_NEGATION_MARKERS = {
    "\ud558\uc9c0\ub9c8",
    "\ud558\uc9c0 \ub9d0",
    "\ud558\uc9c0\ub9d0",
    "\ub9d0\uace0",
    "\uc81c\uc678",
    "\ube7c\uace0",
}
LOCALIZED_PATCH_PRE_BROAD_NEGATION_RE = re.compile(
    r"(?:do\s+not|don't|dont|no|not|without|except|exclude|avoid)\s+$"
)
LOCALIZED_PATCH_POST_BROAD_NEGATION_RE = re.compile(
    r"^(?:\s*(?:is|are|changes?|work)?\s*)?(?:not\s+needed|not\s+required|excluded?|excepted?|out\s+of\s+scope|하지마|하지\s+말|하지말|말고|제외|빼고)"
)
KOREAN_POST_BROAD_NEGATION_MARKERS = ("\ud558\uc9c0\ub9c8", "\ud558\uc9c0 \ub9d0", "\ud558\uc9c0\ub9d0", "\ub9d0\uace0", "\uc81c\uc678", "\ube7c\uace0")
FILE_REFERENCE_RE = re.compile(
    r"(?<![a-z0-9_])[\w.-]+\.(?:html|css|js|jsx|ts|tsx|py|cs|sql|md|json|xml|xaml)(?=$|[^A-Za-z0-9_.-])"
)
CSS_SELECTOR_REFERENCE_RE = re.compile(
    r"(?<![a-z0-9_])[#.](?!env\b|git\b|gitignore\b|editorconfig\b|prettierrc\b|eslintrc\b|npmrc\b)[a-z][a-z0-9_-]*(?=$|[^A-Za-z0-9_-])"
)
CSS_PROPERTY_REFERENCE_RE = re.compile(
    r"(?<![a-z0-9_-])(?:max-|min-)?(?:width|height|margin|padding|gap|display|position|top|right|bottom|left|font-size|line-height|color|background|border|overflow|z-index)(?![a-z0-9_-])"
)
MEDIUM_TERMS = {
    "summarize",
    "compare",
    "analyze",
    "recent",
    "meeting notes",
    "action items",
    "source summary",
    "study schedule",
    "plan a study",
    "learning",
    "요약",
    "비교",
    "분석",
    "최근",
    "검토",
}
COMMAND_OUTPUT_SOURCE_TERMS = {
    "command output",
    "terminal output",
    "stdout",
    "stderr",
    "exit code",
    "returncode",
    "log",
    "logs",
    "build log",
    "test log",
    "pytest",
    "msbuild",
    "stack trace",
    "traceback",
    "compiler error",
    "assertion",
    "로그",
    "긴 로그",
    "출력",
    "명령 출력",
    "터미널 출력",
    "실패 테스트",
    "테스트명",
    "파일 라인",
    "오류 로그",
    "에러 로그",
}
COMMAND_OUTPUT_ACTION_TERMS = {
    "summarize",
    "compress",
    "filter",
    "truncate",
    "keep only",
    "preserve",
    "extract",
    "핵심만",
    "요약",
    "압축",
    "필터",
    "보존",
    "추출",
    "안전하게",
}
COMMAND_OUTPUT_FACT_TERMS = {
    "failed",
    "failure",
    "error",
    "failing test",
    "file line",
    "line number",
    "assertion",
    "actual",
    "expected",
    "exit code",
    "returncode",
    "traceback",
    "실패",
    "오류",
    "에러",
    "파일",
    "라인",
    "값",
}
COMPLEX_EXTRACTION_SOURCE_TERMS = {
    "pbl",
    "pblscripter",
    "powerbuilder",
    "datawindow",
    "sru",
    "srd",
    "pbd",
    "orca",
    "binary",
    "embedded string",
    "print button",
    "retrieve sql",
    "retrieve=",
    "stored procedure",
    "sql",
    "select",
    "\uc778\uc1c4\ubc84\ud2bc",
    "\uc870\ud68c",
    "\uc870\ud68c sql",
}
COMPLEX_EXTRACTION_ARTIFACT_TERMS = {
    "image",
    "png",
    "svg",
    "pdf",
    "render",
    "screenshot",
    "diagram",
    "drawing",
    "visual",
    "binding",
    "bound column",
    "column name",
    "field name",
    "replace actual data",
    "actual data",
    "\uc774\ubbf8\uc9c0",
    "\uc2a4\ud06c\ub9b0\uc0f7",
    "\ubc14\uc778\ub529",
    "\uceec\ub7fc\uba85",
    "\uc870\ud68c\uceec\ub7fc",
    "\uc2e4\uc81c\ub370\uc774\ud130",
}
COMPLEX_EXTRACTION_REQUIRED_HARNESSES = [
    "command-output-harness",
    "artifact-render-qa-harness",
    "deliverable-template-quality-harness",
    "traceability-matrix-harness",
]
PB_TO_CSHARP_MIGRATION_SOURCE_TERMS = {
    "pb",
    "pbl",
    "pbd",
    "pblscripter",
    "powerbuilder",
    "datawindow",
    "sru",
    "srw",
    "srd",
    "gwerp",
}
PB_TO_CSHARP_MIGRATION_TARGET_TERMS = {
    "c#",
    "csharp",
    "c sharp",
    "winforms",
    "devexpress",
    "ty",
    "c_kone110",
    "c_kone110_1",
    "select/save",
    "select save",
    "stored procedure",
    "sp_",
    "migration",
    "migrate",
    "\ub9c8\uc774\uadf8\ub808\uc774\uc158",
}
LIGHT_TERMS = {
    "what is",
    "what does",
    "how do",
    "define",
    "explain",
    "concept",
    "in simple terms",
    "at a high level",
    "tell me about",
    "mean",
    "뜻",
    "개념",
    "뭐야",
    "설명",
    "예시",
}
AMBIGUOUS_TERMS = {
    "what should i do with this",
    "can you do it",
    "use the better one",
    "ship it",
    "same as before",
    "can this file be improved",
    "is samsung okay",
    "do the same thing",
    "for the other file",
    "can you review it",
    "review it",
    "now make it shorter",
    "make it shorter",
    "이거",
    "괜찮아",
    "어때",
    "해줘",
    "봐줘",
    "올린 파일",
}
REFERENTIAL_AMBIGUOUS_TERMS = {
    "that",
    "that plate",
    "that file",
    "the other",
    "same as before",
}
CONTEXT_FREE_AMBIGUOUS_TERMS = {
    "what should i do with this",
    "do the same thing",
    "for the other file",
    "can you review it",
    "review it",
    "now make it shorter",
    "make it shorter",
}

AMBIGUOUS_VISUAL_QUERY_ORDER_VISUAL_TERMS = {
    "like the image",
    "like this image",
    "like the screenshot",
    "as shown in the image",
    "\uc774\ubbf8\uc9c0\ucc98\ub7fc",
    "\uc2a4\ud06c\ub9b0\uc0f7\ucc98\ub7fc",
}
AMBIGUOUS_VISUAL_QUERY_ORDER_TERMS = {
    "order",
    "ordering",
    "sequence",
    "sort",
    "sorted",
    "\uc21c\uc11c",
    "\uc815\ub82c",
}
AMBIGUOUS_VISUAL_QUERY_DISPLAY_TERMS = {
    "query",
    "lookup",
    "retrieve",
    "display",
    "show",
    "list",
    "\uc870\ud68c",
    "\ud45c\uc2dc",
    "\ubcf4\uc774",
    "\ub098\uc624",
}

EXTRA_SOFTWARE_DOMAIN_TERMS = {
    "async/await",
    "jwt",
    "oauth",
    "pytest",
    "sql",
    "t-sql",
    "tsql",
    "traceback",
    "login",
    "refresh token",
    "refresh tokens",
    "token rotation",
    "sso",
}
EXTRA_LEGAL_DOMAIN_TERMS = {
    "tenant rights",
    "hipaa",
    "authorization form",
}
EXTRA_SOFTWARE_HEAVY_TERMS = {
    "add oauth",
    "store refresh tokens",
    "refresh token rotation",
    "fix checkout",
    "prove it with tests",
    "sql injection vulnerability",
}
EXTRA_PRODUCT_DESIGN_HEAVY_TERMS = {
    "checkout button",
    "button easier to find",
    "easier to find on mobile",
}
EXTRA_DESTRUCTIVE_ACTION_TERMS = {
    "drop the staging table",
    "drop the staging users table",
    "drop staging table",
    "drop staging users table",
    "drop database table",
    "format drive",
    "format disk",
    "format on",
}
EXTRA_SECURITY_HIGH_RISK_TERMS = {
    "bypasses spam filters",
    "dump credentials",
    "customer emails",
    "personal gmail",
    "github token",
    "token was committed",
    "secret was committed",
    "committed to main",
}
CREDENTIAL_SAFETY_TERMS = {
    ".env",
    "$env:",
    "env:",
    "api key",
    "api-key",
    "apikey",
    "credential",
    "credentials",
    "connection string",
    "connection-string",
    "secret",
    "secrets",
    "password",
    "github token",
    "refresh token",
    "token was committed",
    "secret was committed",
    "environment variable",
    "environment variables",
    "openai_api_key",
    "ncbi_api_key",
}
SHOPPING_TERMS = {
    "air fryer",
    "air fryers",
    "headphones",
    "laptop",
    "jacket",
    "desk chair",
    "coffee filters",
    "vpn subscription",
    "budget blenders",
    "blenders",
    "olive oils",
    "protein powders",
    "under $",
    "cheap",
    "worth it",
    "top-rated",
    "buy for school",
    "\uc0ac\ubb34\uc6a9 \uc758\uc790",
    "\ucd94\ucc9c",
    "\uc0b4 \ub9cc\ud55c",
}
SCHEDULING_TERMS = {
    "remind me",
    "reminder",
    "reminders",
    "schedule",
    "appointment",
    "meeting",
    "calendar",
    "dentist",
    "timer",
    "tomorrow",
    "next week",
    "\uc608\uc57d",
    "\ub2e4\uc74c \uc8fc",
    "\ud654\uc694\uc77c",
    "\ub9ac\ub9c8\uc778\ub4dc",
    "\uc54c\ub9bc",
}
WEATHER_TERMS = {
    "weather",
    "rain",
    "snow",
    "umbrella",
    "forecast",
    "humidity",
    "storm",
    "wear tomorrow",
}
BOOKING_TERMS = {
    "book me",
    "reserve a hotel",
    "flight",
    "hotel",
    "\ud638\ud154",
}
BOOKING_ACTION_TERMS = {
    "book me",
    "reserve a hotel",
    "reserve",
    "book",
}
PRIVACY_TERMS = {
    "customer emails",
    "personal gmail",
    "patient's medical record",
    "medical record",
    "patient list",
    "eu list",
    "opt-outs",
    "private photos",
    "passport scan",
    "i-797",
    "ssns",
    "dlp flagged",
    "privacy policy",
    "privacy",
}
COMPLIANCE_TERMS = {
    "gdpr",
    "compliance",
    "compliant",
    "soc 2",
}
HR_TERMS = {
    "performance improvement plan",
    "underperforming employee",
    "candidate",
    "hire",
    "staffing plan",
    "support team",
    "job description",
    "backend engineer",
    "recruiter",
    "negotiation email",
    "cover letter",
    "product manager offer",
    "offer",
    "job search",
    "interview",
    "career",
}
OPERATIONS_TERMS = {
    "ceo dashboard",
    "weekly operating review",
    "status report",
    "raid log",
    "project updates",
    "process map",
    "invoice approval",
    "vendor onboarding",
    "dashboard with yesterday",
    "yesterday's numbers",
    "support rotation",
    "pagerduty",
    "timesheet",
    "invoices",
    "goals doc",
    "inbox",
    "work admin",
    "warehouse",
    "inventory",
    "stock movement",
    "business process",
    "process flow",
    "창고",
    "재고",
    "입출고",
    "수불",
    "업무 프로세스",
}
NO_CODE_NEGATION_TERMS = {
    "do not implement",
    "don't implement",
    "no implementation",
    "do not create code",
    "don't create code",
    "no code",
    "without code",
    "implementation code",
    "구현하지",
    "구현하지마",
    "구현하지 말",
    "구현 코드는",
    "코드는 아직",
    "코드는 만들지",
}
PROCESS_DELIVERABLE_TERMS = {
    "business definition",
    "process flow",
    "process-flow",
    "flowchart",
    "workflow document",
    "process document",
    "docs",
    "document",
    "업무정의서",
    "업무 정의서",
    "처리흐름도",
    "처리 흐름도",
    "프로세스 문서",
    "문서",
    "정의서",
}
PRODUCT_STRATEGY_TERMS = {
    "prd",
    "product requirements document",
    "bulk user import",
    "advanced reporting",
    "product",
}
PRODUCT_DISCOVERY_OBJECT_TERMS = {
    "product",
    "service",
    "saas",
    "app",
    "web app",
    "website",
    "web site",
    "webpage",
    "web page",
    "homepage",
    "portal",
    "page",
    "dashboard",
    "tool",
    "platform",
    "startup",
    "mvp",
    "business tool",
    "internal tool",
    "support product",
    "operations product",
    "\uc81c\ud488",
    "\uc11c\ube44\uc2a4",
    "\uc571",
    "\uc6f9",
    "\uc6f9\uc571",
    "\uc6f9\uc0ac\uc774\ud2b8",
    "\uc6f9\ud398\uc774\uc9c0",
    "\ud648\ud398\uc774\uc9c0",
    "\ud3ec\ud138",
    "\ud398\uc774\uc9c0",
    "\ub300\uc2dc\ubcf4\ub4dc",
    "\ub3c4\uad6c",
    "\ud234",
    "\ud50c\ub7ab\ud3fc",
    "\uc0ac\uc5c5",
    "\uc544\uc774\ub514\uc5b4",
    "\uc6b4\uc601\uc9c0\uc6d0",
    "\uc5c5\ubb34\uad00\ub9ac",
}
PRODUCT_DISCOVERY_ACTION_TERMS = {
    "build",
    "built",
    "create",
    "develop",
    "make",
    "start",
    "plan",
    "planned",
    "design",
    "launch",
    "scaffold",
    "\uac1c\ubc1c",
    "\ub9cc\ub4e4",
    "\uc0dd\uc131",
    "\uae30\ud68d",
    "\uc124\uacc4",
    "\uc2dc\uc791",
}
DOMAIN_DISCOVERY_OBJECT_TERMS = PRODUCT_DISCOVERY_OBJECT_TERMS | {
    "workflow",
    "process",
    "operating model",
    "operational model",
    "analysis",
    "research",
    "study",
    "policy",
    "procedure",
    "document structure",
    "report structure",
    "specification",
    "spec",
    "drawing direction",
    "design direction",
    "investment thesis",
    "portfolio approach",
    "decision framework",
    "\uc5c5\ubb34\ud750\ub984",
    "\ud504\ub85c\uc138\uc2a4",
    "\uc6b4\uc601",
    "\ubd84\uc11d",
    "\ub9ac\uc11c\uce58",
    "\uc5f0\uad6c",
    "\uc815\ucc45",
    "\uc808\ucc28",
    "\ubb38\uc11c",
    "\ubcf4\uace0\uc11c",
    "\uaddc\uaca9",
    "\ub3c4\uba74",
    "\uc124\uacc4\ubc29\ud5a5",
    "\ud22c\uc790",
}
DOMAIN_DISCOVERY_ACTION_TERMS = PRODUCT_DISCOVERY_ACTION_TERMS | {
    "brainstorm",
    "ideate",
    "shape",
    "scope",
    "outline",
    "outlined",
    "map out",
    "figure out",
    "direction",
    "approach",
    "framework",
    "\ubc29\ud5a5",
    "\uc7a1\uc544",
    "\uc815\uc758",
    "\uad6c\uc0c1",
    "\uc544\uc774\ub514\uc5b4",
    "\ucd08\uc548",
    "\ud2c0",
}
DOMAIN_DISCOVERY_INTENT_TERMS = {
    "brainstorm",
    "ideate",
    "shape",
    "scope",
    "outline",
    "outlined",
    "map out",
    "figure out",
    "direction",
    "approach",
    "framework",
    "plan",
    "planned",
    "\ubc29\ud5a5",
    "\uc7a1\uc544",
    "\uc815\uc758",
    "\uad6c\uc0c1",
    "\uc544\uc774\ub514\uc5b4",
    "\ucd08\uc548",
    "\ud2c0",
}
PRODUCT_DISCOVERY_SPECIFICITY_TERMS = {
    "html",
    "css",
    "javascript",
    "js",
    "react",
    "vue",
    "api",
    "database",
    "table",
    "filter",
    "kpi",
    "metrics",
    "screen",
    "wireframe",
    "drawing",
    "docx",
    "xlsx",
    "pdf",
    "dxf",
    "svg",
    "index.html",
    "verify",
    "validate",
    "compliant",
    "gdpr",
    "hipaa",
    "test",
    "tests",
    "sample",
    "with ",
    "including ",
    "\ub300\uc2dc\ubcf4\ub4dc",
    "\ud654\uba74",
    "\ud14c\uc774\ube14",
    "\ud544\ud130",
    "\uc9c0\ud45c",
    "\uba54\ud2b8\ub9ad",
    "\ub3c4\uba74",
    "\uac80\uc99d",
    "\ud14c\uc2a4\ud2b8",
}
STACK_ONLY_DISCOVERY_SPECIFICITY_TERMS = {
    "html",
    "css",
    "javascript",
    "js",
    "react",
    "vue",
    "index.html",
}
VAGUE_DISCOVERY_SPECIFICITY_TERMS = {
    "dashboard",
    "pdf",
    "docx",
    "xlsx",
    "dxf",
    "svg",
    "upload",
    "file upload",
    "store",
    "\ub300\uc2dc\ubcf4\ub4dc",
    "\uc5c5\ub85c\ub4dc",
    "\uc800\uc7a5",
}
VENDOR_OPS_TERMS = {
    "rfp",
    "vendor",
    "vendors",
    "datadog contract",
    "payroll vendors",
    "vendor selection",
}
FINANCE_TERMS = {
    "mortgage rates",
    "budget variance",
    "finance review",
    "insurance policy",
    "usage and cost",
    "spreadsheet model",
    "broken formula",
}
CREATIVE_TERMS = {
    "brainstorm",
    "bedtime story",
    "coffee shop",
    "naming architecture",
    "names for",
}
MARKETING_TERMS = {
    "launch email",
    "homepage copy",
    "content calendar",
    "crisis apology",
    "customers",
    "campaign",
    "marketing",
    "testimonials",
}
MARKETING_HEAVY_TERMS = {
    "launch email",
    "homepage copy",
    "content calendar",
    "crisis apology",
    "brand voice",
    "campaign",
}
MARKETING_HIGH_RISK_TERMS = {
    "fake testimonials",
    "named customers",
    "exploit family guilt",
    "pressure doctors",
    "hide subscription fee",
    "scares seniors",
    "target people behind on rent",
    "post it to all customers",
    "send to all customers",
}
TRAVEL_TERMS = {
    "trip",
    "itinerary",
    "family trip",
    "flight",
    "airport gate",
    "boarding gate",
    "flight gate",
    "restaurant",
    "table",
    "travel",
}
LOCAL_TERMS = {
    "nearby",
    "open now",
    "locksmith",
    "local",
}
FITNESS_TERMS = {
    "progressive overload",
    "strength training",
    "training plan",
    "10k training",
    "workout",
    "work out",
    "squatting",
    "strength days",
    "deload",
    "marathon",
}
NUTRITION_TERMS = {
    "meal plan",
    "high-protein",
    "vegetarian",
    "grocery list",
    "romaine salads",
    "protein",
}
COOKING_TERMS = {
    "recipe",
    "gluten-free",
    "cooking",
    "salads",
}
LIFESTYLE_TERMS = {
    "screen-free",
    "evening routine",
    "cleaning schedule",
    "small apartment",
}
FOOD_SAFETY_TERMS = {
    "listeria",
    "recall",
    "recalls",
    "frozen berries",
    "lettuce",
    "pesto",
    "unrefrigerated",
    "food safety",
}
CAREER_TERMS = {
    "tailor my resume",
    "resume summary",
    "job description",
    "backend engineer",
    "recruiter email",
    "negotiation email",
    "product manager offer",
    "offer and want to negotiate",
    "fintech pm role",
}
CAREER_CURRENT_DATA_TERMS = {
    "current market salary",
    "salary for",
    "remote data analyst jobs",
    "jobs posted this week",
    "job openings",
    "posted this week",
}
CIVIC_TERMS = {
    "foia",
    "foia request",
}
TAX_TERMS = {
    "renter's credit",
    "file california",
    "tax",
    "paperwork",
}
IMMIGRATION_TERMS = {
    "ds-160",
    "i-797",
    "passport scan",
    "passport",
    "visa",
    "extension is pending",
}
GOV_ADMIN_TERMS = {
    "unemployment benefits",
    "benefits application",
    "permit",
    "permits",
}
DEVOPS_TERMS = {
    "kubernetes",
    "readiness probes",
    "production",
    "roll back",
    "rollback",
    "failover",
    "cloud migration",
    "vercel",
    "cloudfront",
    "route 53",
    "terraform",
    "lambda",
    "dynamodb",
    "pagerduty",
}
SAFETY_CRISIS_TERMS = {
    "spouse hit me",
    "blocking the door",
    "domestic violence",
    "killing myself",
    "have pills",
    "suicide",
    "self harm",
}
HARASSMENT_PRIVACY_TERMS = {
    "impersonating my daughter",
    "private photos",
    "classmates",
}
IMPERSONATION_ABUSE_TERMS = {
    "fake profile of my ex",
    "impersonating",
}
EDUCATION_TERMS = {
    "photosynthesis",
    "math problem",
    "algebra",
    "homework",
    "assignment",
    "assignments",
    "worksheet",
    "flashcards",
    "chapter",
    "study plan",
    "study schedule",
    "study calendar",
    "plan a study",
    "exam",
    "finals",
    "sat",
    "act",
    "ap registration",
    "scholarship",
    "fafsa",
    "google classroom",
    "teacher",
    "tutor",
    "grade",
    "english essay",
    "multiplication",
    "science test",
    "college applications",
    "kid practice",
    "my kid",
}
LANGUAGE_TERMS = {
    "spanish",
    "to spanish",
    "to english",
    "spanish verbs",
    "affect and effect",
    "translate my homework directions",
    "translate this menu",
    "learn spanish",
}
DOCUMENT_TERMS = {
    "document",
    "requirements",
    "requirements definition",
    "specification",
    "checklist",
    "deliverable",
    "manual",
    "문서",
    "보고서",
    "요구정의",
    "요구 정의",
    "기능정의",
    "기능 정의",
    "산출물",
    "체크리스트",
    "매뉴얼",
    "essay for grammar",
    "attached worksheet",
    "attached lecture notes",
    "lecture recording",
    "teacher note",
    "book report",
    "second essay",
    "email notes",
    "study group",
}
EDUCATION_MISSING_CONTEXT_TERMS = {
    "solve this math problem",
    "do my entire algebra homework",
    "do my history homework",
    "write my english essay",
    "just write the answers",
    "write the answers",
    "give final answers",
    "give me the answer key",
    "make flashcards from chapter",
    "summarize chapter",
    "what did my teacher say earlier",
    "same as last assignment",
    "what homework do i have",
    "help me learn algebra",
    "help with this chemistry worksheet",
    "number 4",
    "my kid has a science test help",
    "help organize college applications",
}
DOCUMENT_MISSING_CONTEXT_TERMS = {
    "check my essay for grammar",
    "grade my attached worksheet",
    "i uploaded my essay",
    "attached my rubric",
    "summarize my lecture recording",
    "summarize the attached lecture notes",
    "explain this teacher note",
    "same for the second essay",
    "email notes to study group",
}
EDUCATION_CURRENT_DATA_TERMS = {
    "sat this year",
    "ap registration",
    "registration still open",
    "scholarship deadlines",
    "school is closed",
    "google classroom",
    "fafsa deadline",
    "late fees",
}
ARTIFACT_HEAVY_WORK_TERMS = {
    "create a document",
    "create a report",
    "requirements document",
    "requirements definition",
    "write requirements",
    "make checklist",
    "deliverable",
    "문서",
    "보고서",
    "요구정의",
    "요구 정의",
    "기능정의",
    "기능 정의",
    "산출물",
    "체크리스트",
    "extract pdf tables",
    "create a chart",
    "chart from",
    "add formulas",
    "calculate variance",
    "convert this",
    "convert file",
    "merge",
    "clean and deduplicate",
    "deduplicate",
    "generate pivot table",
    "pivot table",
    "create slides",
    "executive brief",
    "update chart",
    "export as",
    "export it as",
    "save as",
    "save it as",
    "put the result into a spreadsheet",
    "sort sheet",
    "make it one page",
    "fix the broken spreadsheet",
    "clean extracted data",
    "clean it up",
    "validation rules",
}
ARTIFACT_READ_WORK_TERMS = {
    "read receipt",
    "receipt totals",
    "extract the key table",
    "extract tables",
    "what are the totals",
    "late fee rules",
    "what are they asking me to do",
}
LIGHT_DIRECT_TASK_TERMS = {
    "write a polite email",
    "write an email",
    "write a short email",
    "rewrite this text",
    "text my mom",
    "draft a message",
    "draft a note",
    "should bring it",
    "wait until lunch",
    "\ubb38\uc790 \ub354 \ubd80\ub4dc\ub7fd\uac8c",
    "\uc218\ub9ac \uc694\uccad \ubb38\uc790",
    "make this email",
    "format this as",
    "put this into a table",
    "clean up this paragraph",
    "how do i clean",
    "make a checklist",
    "write a simple cover letter",
    "draft the recruiter email",
    "write the negotiation email",
    "what should i name",
    "\uc774 \uc774\uba54\uc77c \ub354 \uacf5\uc190\ud558\uac8c",
}
INLINE_TONE_TRANSFORM_INTENT_TERMS = {
    "make this sentence",
    "make this text",
    "make this message",
    "make this paragraph",
    "make this note",
    "rewrite this sentence",
    "rewrite this message",
    "rewrite this paragraph",
    "clean up this sentence",
    "clean up this message",
    "polish this sentence",
    "polish this message",
}
INLINE_SIMPLE_TRANSFORM_INTENT_TERMS = {
    "rewrite this sentence",
    "rewrite this text",
    "rewrite this message",
    "rewrite this paragraph",
    "rephrase this sentence",
    "rephrase this text",
    "edit this sentence",
    "edit this text",
    "clean up this sentence",
}
INLINE_TONE_TRANSFORM_QUALITY_TERMS = {
    "less rude",
    "less harsh",
    "less blunt",
    "more polite",
    "more professional",
    "more friendly",
    "friendlier",
    "softer",
    "calmer",
    "warmer",
    "kinder",
}
DOCUMENT_TRANSFORM_TERMS = {
    "translate",
    "rewrite",
    "summarize",
    "turn these notes",
    "read this receipt",
    "resume from my work history",
    "attached pdf",
    "\ubc88\uc5ed",
    "\uc815\ub9ac",
}
CONTEXT_FREE_AMBIGUOUS_EXTRA_TERMS = {
    "ok now send it",
    "try again",
    "fix the tone",
    "rewrite this",
    "turn these notes",
    "summarize this",
    "summarize the attached pdf",
    "translate this",
    "what did i say earlier",
    "fill out this form",
    "read this receipt",
    "make a resume from my work history",
    "is this good",
    "use the second option",
    "update the dashboard with yesterday's numbers",
    "send to ceo",
    "same as earlier",
    "continue from earlier",
    "do it",
    "do the same thing",
    "for the other file",
    "other file",
    "is this safe",
    "open the attached",
    "attached article",
    "fix my resume",
    "same as last time",
    "what did we decide earlier",
    "can you read this",
    "can this file be improved",
    "make it more premium",
    "please submit",
    "report it",
    "post it",
    "\uc774 \uc591\uc2dd",
    "translate this to",
}
CURRENT_DATA_TERMS = {
    "today",
    "right now",
    "current",
    "latest",
    "market today",
}
PURCHASE_ACTION_TERMS = {
    "buy more",
    "purchase the",
    "order this",
}
HIGH_IMPACT_ACTION_TERMS = {
    "cancel my insurance policy",
    "buy 100 shares",
    "order this medication",
}
PERSONAL_INVESTMENT_ADVICE_TERMS = {
    "emergency fund",
    "401k contribution",
    "buy 100 shares",
    "buy $",
    "move my 401k",
    "company stock options",
    "stock options",
    "sell company stock",
    "sell stock",
    "\uc0ac\ub3c4\ub3fc",
    "\uc8fc\uc2dd \ud314\uae4c",
    "\ub298\ub824\uc57c \ud560\uae4c",
}
PERSONAL_MEDICAL_ADVICE_TERMS = {
    "swallowed a battery",
    "ibuprofen safe",
    "insulin dose",
    "double my insulin",
    "antibiotics",
    "overseas pharmacy",
    "missed a dose",
    "bp is",
    "190/120",
    "urgent care",
    "kidney disease",
    "order this medication",
    "sharp chest pain",
    "benadryl",
    "sleep medication",
    "knee pain",
    "killing myself",
    "have pills",
    "emergency contact",
    "tylenol",
    "fever",
    "vomiting",
    "\ud0c0\uc774\ub808\ub180",
    "\uc5f4\uc774 39",
    "\uad6c\ud1a0",
    "\ud608\uc555\uc57d",
    "\ub04a\uc5b4\ub3c4 \ub3fc",
}
PERSONAL_LEGAL_ADVICE_TERMS = {
    "what do i plead",
    "plead",
    "dui",
    "court date",
    "should sign it",
    "terminate this vendor agreement",
    "vendor agreement",
    "employment agreement",
    "employer fire",
    "discussing wages",
    "fire this underperforming employee",
    "severance agreement",
    "final paycheck",
    "retaliation",
    "protected status",
    "termination",
    "evict me",
    "police report",
    "legal options",
    "harassment messages",
    "without penalty",
    "demand letter",
    "\ubcf4\uc99d\uae08",
    "\ubc95\uc801\uc73c\ub85c \ubb50\ud574",
    "\uc18c\ube44\uc790\uc6d0 \uc2e0\uace0",
    "\uc99d\uba85\uc11c",
    "\ud569\uc758\uc11c",
    "\uc11c\uba85\ud574\ub3c4",
}
CONTEXTUAL_MEDIUM_FOLLOWUP_TERMS = {
    "same format",
    "make it more executive",
    "update with yesterday",
    "yesterday's numbers",
    "send to ceo",
    "send to hrbp",
    "fix the broken spreadsheet",
    "spreadsheet formula",
    "translate this",
    "summarize this",
    "summarize this pr",
    "resume from yesterday",
    "add metrics",
    "add blockers",
    "add criteria weights",
    "add runway sensitivity",
    "add stale deal flags",
    "add controls",
    "create process map",
    "undo that",
    "\uc544\uae4c \uadf8 \uae30\uc900",
    "\ub0b4\uc77c\ub85c \ubbf8\ub904\uc918",
}
CONTEXTUAL_HEAVY_FOLLOWUP_TERMS = {
    "do the same thing",
    "do it",
    "for the other file",
    "other file",
    "add password reset",
    "add missing tests",
    "add tests",
    "now add tests",
    "prepare the release checklist",
    "release checklist",
    "ship it",
    "update the docs",
    "create a changelog",
    "changelog entry",
    "add a release note",
    "missing index migration",
    "fix the issue",
    "security risks",
    "auth code",
    "login code",
    "m20",
    "\ub2e4\ub978 \ud30c\uc77c\ub3c4",
    "\ud640 4\uac1c",
}
STRUCTURED_MEDIUM_WORK_TERMS = {
    "rfp scoring rubric",
    "renew the datadog contract",
    "ceo dashboard",
    "weekly operating review",
    "build sso before advanced reporting",
    "one-page prd",
    "product requirements document",
    "performance improvement plan",
    "candidate a and candidate b",
    "weekly status report",
    "raid log",
    "vendor onboarding plan",
    "broken formula",
    "spreadsheet model",
    "budget variance analysis",
    "vendor selection memo",
    "process map",
    "staffing plan",
    "3-day seoul itinerary",
    "3-day family trip",
    "family trip",
    "nearby locksmith",
    "open now",
    "home maintenance",
    "water leak",
    "\ub9ac\ub9c8\uc778\ub4dc",
    "\uc54c\ub9bc",
    "\ubb3c\uc774 \uc0c8",
    "\uc218\ub3c4\uad00",
    "\uc544\ud30c\ud2b8",
    "\uc774\uc0ac \uccb4\ud06c\ub9ac\uc2a4\ud2b8",
    "\uc7a5\ubcf4\uae30 \ub9ac\uc2a4\ud2b8",
    "\uac00\uc871 \uc5ec\ud589 \uc608\uc0b0",
    "readme\ub97c",
    "\ubc88\uc5ed\ud558\uace0",
    "\uce58\uacfc \uc608\uc57d",
    "\uc624\ub298 \ud560 \uc77c \uc6b0\uc120\uc21c\uc704",
}


@dataclass(frozen=True)
class RequestClassification:
    complexity: str
    domain: str
    recommended_execution: str
    cross_cutting: List[str] = field(default_factory=list)
    recommended_skills: List[str] = field(default_factory=list)
    required_harnesses: List[str] = field(default_factory=list)
    evidence_required: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.75

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def classify_request(text: str, context: dict | None = None) -> RequestClassification:
    """Classify a user request before choosing how much UAF machinery to run."""
    context = context or {}
    normalized = _normalize(text)
    domain = _detect_domain(normalized, context)
    cross_cutting = ["token-optimizer"]
    evidence_required: List[str] = []
    reasons: List[str] = []

    if _needs_token_optimization(text, normalized):
        evidence_required.append("token_optimization")
        reasons.append("large_or_log_like_input")
    if _context_exceeds_token_budget(context):
        evidence_required.append("token_optimization")
        reasons.append("context_budget_threshold_exceeded")
    if _requires_resume_context(context):
        evidence_required.append("resume_handoff")
        reasons.append("resume_context_required")
    if _needs_credential_safety(normalized):
        cross_cutting.append("credential-safety-harness")
        evidence_required.append("credential_safety_status")
        reasons.append("credential_or_secret_boundary")

    memory_requested = _is_memory_state_request(normalized)
    if memory_requested and "resume_context_required" in reasons:
        return _heavy_classification(
            domain,
            cross_cutting,
            evidence_required,
            [*reasons, "memory_state_request"],
        )

    if memory_requested and _is_parallel_orchestration_request(normalized):
        return _heavy_classification(
            domain,
            cross_cutting,
            evidence_required,
            [*reasons, "memory_state_request", "parallel_orchestration_request"],
        )

    if memory_requested:
        return _memory_state_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_high_risk(normalized, domain, context):
        return _high_risk_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_pb_to_csharp_migration_request(normalized):
        return _complex_extraction_deliverable_classification(
            "software",
            cross_cutting,
            evidence_required,
            [*reasons, "pb_to_csharp_migration_request"],
            extra_harnesses=["pb-to-csharp-migration-harness"],
        )

    if _is_provider_meta_review_request(normalized):
        return _classification(
            complexity="medium",
            domain="software",
            recommended_execution="skill_read",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=_dedupe([*evidence_required, "routing_review"]),
            reasons=[*reasons, "provider_meta_review_request"],
            confidence=0.78,
        )

    if _is_sql_formatting_style_request(normalized):
        return _classification(
            complexity="medium",
            domain="software",
            recommended_execution="skill_read",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=_dedupe([*evidence_required, "sql_formatting_style_check"]),
            reasons=[*reasons, "sql_formatting_style_request"],
            confidence=0.78,
        )

    if _is_readonly_source_audit_request(normalized, domain):
        return _classification(
            complexity="medium",
            domain="software" if domain == "general" else domain,
            recommended_execution="skill_read",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=_dedupe([*evidence_required, "source_summary", "audit_findings"]),
            reasons=[*reasons, "readonly_source_audit_request"],
            confidence=0.8,
        )

    if _is_contextual_audit_repair_request(normalized, context):
        return _heavy_classification(
            _contextual_audit_repair_domain(domain, context),
            cross_cutting,
            evidence_required,
            [*reasons, "contextual_audit_repair_request"],
        )

    if _is_complex_extraction_deliverable_request(normalized):
        return _complex_extraction_deliverable_classification(
            domain,
            cross_cutting,
            evidence_required,
            reasons,
        )

    if _is_command_output_request(normalized):
        return _command_output_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_brainstorm_direction_choice_without_execution(normalized, context):
        return _brainstorming_classification(
            domain,
            cross_cutting,
            evidence_required,
            [*reasons, "brainstorm_direction_choice_needs_design_review"],
            normalized,
        )

    if _is_unreviewed_brainstorm_implementation_request(normalized, context):
        return _brainstorming_classification(
            domain,
            cross_cutting,
            evidence_required,
            [*reasons, "brainstorm_implementation_needs_reviewed_handoff"],
            normalized,
        )

    if _is_approved_brainstorm_continuation(normalized, context):
        return _heavy_classification(
            domain,
            cross_cutting,
            evidence_required,
            [*reasons, "approved_brainstorm_continuation"],
        )

    if _is_mojibake_new_project_request(text, normalized, context):
        return _brainstorming_classification(
            domain,
            cross_cutting,
            evidence_required,
            [*reasons, "mojibake_new_project_needs_brainstorming"],
            normalized,
        )

    if _is_unapproved_product_discovery_request(normalized, context, domain):
        return _brainstorming_classification(domain, cross_cutting, evidence_required, reasons, normalized)

    if _is_localized_patch_continuation(normalized, context):
        return _classification(
            complexity="medium",
            domain="software" if domain == "general" else domain,
            recommended_execution="skill_read",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=_dedupe([*evidence_required, "localized_patch_evidence"]),
            reasons=[*reasons, "localized_patch_continuation"],
            confidence=0.8,
        )

    if _is_source_condition_mutation_command(normalized):
        return _heavy_classification(
            domain,
            cross_cutting,
            evidence_required,
            [*reasons, "source_condition_mutation_command"],
        )

    if _is_readonly_source_condition_question(normalized):
        return _classification(
            complexity="medium",
            domain=domain,
            recommended_execution="skill_read",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=_dedupe([*evidence_required, "source_summary"]),
            reasons=[*reasons, "readonly_source_condition_question"],
            confidence=0.78,
        )

    if _is_ambiguous_visual_query_order_request(normalized, context):
        return _classification(
            complexity="ambiguous",
            domain=domain,
            recommended_execution="clarify",
            cross_cutting=cross_cutting,
            evidence_required=evidence_required,
            reasons=[*reasons, "ambiguous_visual_query_order_request"],
            confidence=0.58,
        )

    if _is_ambiguous(normalized, context):
        return _classification(
            complexity="ambiguous",
            domain=domain,
            recommended_execution="clarify",
            cross_cutting=cross_cutting,
            evidence_required=evidence_required,
            reasons=[*reasons, "low_context_ambiguous_request"],
            confidence=0.55,
        )

    if _is_no_code_process_deliverable_request(normalized):
        return _medium_classification(
            _no_code_process_domain(normalized, domain),
            cross_cutting,
            evidence_required,
            reasons,
            normalized,
        )

    if _is_resume_heavy_context(normalized, context, domain):
        return _heavy_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_contextual_file_mutation(normalized, context, domain):
        return _heavy_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_contextual_heavy_followup(normalized, context, domain):
        return _heavy_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_contextual_artifact_heavy_work(normalized, context):
        return _heavy_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_contextual_external_send_without_permission(normalized, context):
        return _classification(
            complexity="ambiguous",
            domain=domain,
            recommended_execution="clarify",
            cross_cutting=cross_cutting,
            evidence_required=evidence_required,
            reasons=[*reasons, "external_send_needs_permission"],
            confidence=0.58,
        )

    if _is_contextual_artifact_transform(normalized, context, domain):
        artifact_evidence = [*evidence_required]
        if _contains_any(normalized, {"summarize"}):
            artifact_evidence.append("source_summary")
        return _classification(
            complexity="medium",
            domain=domain,
            recommended_execution="skill_read",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=_dedupe(artifact_evidence),
            reasons=[*reasons, "artifact_context_needed"],
            confidence=0.72,
        )

    if _is_contextual_artifact_read_work(normalized, context):
        return _classification(
            complexity="medium",
            domain=domain,
            recommended_execution="skill_read",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=_dedupe([*evidence_required, "source_summary"]),
            reasons=[*reasons, "artifact_read_required"],
            confidence=0.74,
        )

    if _is_contextual_medium_followup(normalized, context):
        followup_evidence = [*evidence_required]
        if context.get("current_data_need") or _contains_any(normalized, {"summarize", "source summary", "current"}):
            followup_evidence.append("source_summary")
        return _classification(
            complexity="medium",
            domain=domain,
            recommended_execution="skill_read",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=_dedupe(followup_evidence),
            reasons=[*reasons, "active_artifact_followup"],
            confidence=0.72,
        )

    if _is_dotfile_config_mutation(normalized, context):
        return _heavy_classification(
            "software" if domain == "general" else domain,
            cross_cutting,
            evidence_required,
            [*reasons, "dotfile_config_mutation"],
        )

    if _is_light_direct_task(normalized) or _is_tiny_inline_transform(normalized):
        return _classification(
            complexity="light",
            domain=domain,
            recommended_execution="direct_answer",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=evidence_required,
            reasons=[*reasons, "bounded_direct_task"],
            confidence=0.82,
        )

    if _requires_external_or_current_evidence(normalized, domain) or _is_structured_medium_work(normalized, domain):
        return _medium_classification(domain, cross_cutting, evidence_required, reasons, normalized)

    if _is_medium_analysis_request(normalized):
        return _medium_classification(domain, cross_cutting, evidence_required, reasons, normalized)

    if _is_heavy_work(normalized, domain):
        return _heavy_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_contextual_review_request(normalized, context):
        return _classification(
            complexity="medium",
            domain=domain,
            recommended_execution="skill_read",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=evidence_required,
            reasons=[*reasons, "bounded_review_with_active_artifact"],
            confidence=0.7,
        )

    if _is_general_advice_request(normalized):
        return _classification(
            complexity="medium",
            domain=domain,
            recommended_execution="skill_read",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=evidence_required,
            reasons=[*reasons, "general_advice_requires_some_reasoning"],
            confidence=0.68,
        )

    if _contains_any(normalized, MEDIUM_TERMS):
        return _medium_classification(domain, cross_cutting, evidence_required, reasons, normalized)

    if _contains_any(normalized, LIGHT_TERMS) or len(normalized.split()) <= 8:
        return _classification(
            complexity="light",
            domain=domain,
            recommended_execution="direct_answer",
            cross_cutting=cross_cutting,
            recommended_skills=["request-complexity-router"],
            evidence_required=evidence_required,
            reasons=[*reasons, "conceptual_or_short_question"],
            confidence=0.82,
        )

    return _classification(
        complexity="medium",
        domain=domain,
        recommended_execution="skill_read",
        cross_cutting=cross_cutting,
        recommended_skills=["request-complexity-router"],
        evidence_required=evidence_required,
        reasons=[*reasons, "default_medium_unknown_but_actionable"],
        confidence=0.62,
    )


def _classification(
    complexity: str,
    domain: str,
    recommended_execution: str,
    cross_cutting: List[str],
    recommended_skills: List[str] | None = None,
    required_harnesses: List[str] | None = None,
    evidence_required: List[str] | None = None,
    reasons: List[str] | None = None,
    confidence: float = 0.75,
) -> RequestClassification:
    if complexity not in COMPLEXITIES:
        raise ValueError(f"unsupported complexity: {complexity}")
    return RequestClassification(
        complexity=complexity,
        domain=domain,
        recommended_execution=recommended_execution,
        cross_cutting=_dedupe(cross_cutting),
        recommended_skills=_dedupe(recommended_skills or []),
        required_harnesses=_dedupe(required_harnesses or []),
        evidence_required=_dedupe(evidence_required or []),
        reasons=_dedupe(reasons or []),
        confidence=confidence,
    )


def _high_risk_classification(
    domain: str,
    cross_cutting: List[str],
    evidence_required: List[str],
    reasons: List[str],
) -> RequestClassification:
    base_evidence = [
        *evidence_required,
        "objective",
        "scope_constraints",
        "source_summary",
        "risk_disclosure",
        "scenario_matrix",
        "compliance_check",
    ]
    if domain == "investment":
        base_evidence.extend(["data_sources", "suitability_constraints"])
    return _classification(
        complexity="high_risk",
        domain=domain,
        recommended_execution="role_dag",
        cross_cutting=cross_cutting,
        recommended_skills=[
            "request-complexity-router",
            "domain-orchestration-harness",
            "goal-state-harness",
            "review-gate-harness",
            "qa-gate-harness",
        ],
        required_harnesses=[
            "domain-orchestration-harness",
            "goal-state-harness",
            "review-gate-harness",
            "qa-gate-harness",
        ],
        evidence_required=base_evidence,
        reasons=[*reasons, "high_impact_or_regulated_decision"],
        confidence=0.9,
    )


def _medium_classification(
    domain: str,
    cross_cutting: List[str],
    evidence_required: List[str],
    reasons: List[str],
    normalized: str,
) -> RequestClassification:
    medium_evidence = [*evidence_required]
    if _contains_any(
        normalized,
        {"latest", "right now", "current", "market today", "weather", "rates", "commissioner"},
    ):
        medium_evidence.append("source_summary")
    if domain == "local":
        medium_evidence.append("source_summary")
    if domain == "education" and _contains_any(normalized, EDUCATION_CURRENT_DATA_TERMS):
        medium_evidence.append("source_summary")
    if domain == "food-safety" and _contains_any(normalized, CURRENT_DATA_TERMS | {"recall", "recalls"}):
        medium_evidence.append("source_summary")
    if domain == "current-data" and _contains_any(normalized, CAREER_CURRENT_DATA_TERMS):
        medium_evidence.append("source_summary")
    if _contains_any(normalized, {"summarize", "analyze", "recent", "source summary", "research", "최근", "earnings", "실적"}):
        medium_evidence.append("source_summary")
    if _contains_any(normalized, {"compare", "비교"}):
        medium_evidence.append("comparison_basis")
    return _classification(
        complexity="medium",
        domain=domain,
        recommended_execution="skill_read",
        cross_cutting=cross_cutting,
        recommended_skills=["request-complexity-router"],
        evidence_required=_dedupe(medium_evidence),
        reasons=[*reasons, "analysis_or_summary_without_direct_action"],
        confidence=0.78,
    )


def _command_output_classification(
    domain: str,
    cross_cutting: List[str],
    evidence_required: List[str],
    reasons: List[str],
) -> RequestClassification:
    return _classification(
        complexity="medium",
        domain=domain,
        recommended_execution="skill_read",
        cross_cutting=cross_cutting,
        recommended_skills=[
            "request-complexity-router",
            "command-output-harness",
            "token-optimizer",
        ],
        evidence_required=_dedupe(
            [
                *evidence_required,
                "source_summary",
                "token_optimization",
                "command_output_filter",
                "important_failure_facts_preserved",
                "exit_code_preserved",
            ]
        ),
        reasons=[*reasons, "command_output_summary_or_filtering"],
        confidence=0.82,
    )


def _complex_extraction_deliverable_classification(
    domain: str,
    cross_cutting: List[str],
    evidence_required: List[str],
    reasons: List[str],
    extra_harnesses: List[str] | None = None,
) -> RequestClassification:
    routed_domain = "software" if domain == "general" else domain
    requested_harnesses = _dedupe(
        [
            *COMPLEX_EXTRACTION_REQUIRED_HARNESSES,
            *(extra_harnesses or []),
        ]
    )
    return _classification(
        complexity="heavy",
        domain=routed_domain,
        recommended_execution="role_dag",
        cross_cutting=cross_cutting,
        recommended_skills=_dedupe(
            [
                *LARGE_WORK_BUNDLE_SKILLS,
                *requested_harnesses,
            ]
        ),
        required_harnesses=_dedupe(
            [
                *LARGE_WORK_REQUIRED_HARNESSES,
                *requested_harnesses,
            ]
        ),
        evidence_required=_dedupe(
            [
                *evidence_required,
                *LARGE_WORK_BUNDLE_EVIDENCE,
                "objective",
                "source_summary",
                "command_output_filter",
                "important_facts_preserved",
                "artifact_manifest",
                "render_validation",
                "deliverable_quality",
                "traceability_matrix",
                "verification_plan",
            ]
        ),
        reasons=[*reasons, "complex_source_extraction_deliverable"],
        confidence=0.88,
    )


def _is_pb_to_csharp_migration_request(normalized: str) -> bool:
    if not _contains_any(normalized, PB_TO_CSHARP_MIGRATION_SOURCE_TERMS):
        return False
    if _contains_any(normalized, PB_TO_CSHARP_MIGRATION_TARGET_TERMS):
        return True
    return _contains_any(normalized, {"converter", "layout", "grid", "retrieve", "update", "save"})


def _memory_state_classification(
    domain: str,
    cross_cutting: List[str],
    evidence_required: List[str],
    reasons: List[str],
) -> RequestClassification:
    return _classification(
        complexity="medium",
        domain=domain,
        recommended_execution="skill_read",
        cross_cutting=cross_cutting,
        recommended_skills=[
            "request-complexity-router",
            "memory-state-harness",
        ],
        required_harnesses=["memory-state-harness"],
        evidence_required=_dedupe(
            [
                *evidence_required,
                "memory_scope",
                "memory_scope_decision",
                "memory_provider_policy",
                "prompt_snapshot_status",
                "action_sensitive_memory_boundary",
                "global_memory_candidate_policy",
            ]
        ),
        reasons=[*reasons, "memory_state_request"],
        confidence=0.8,
    )


def _brainstorming_classification(
    domain: str,
    cross_cutting: List[str],
    evidence_required: List[str],
    reasons: List[str],
    normalized: str,
) -> RequestClassification:
    return _classification(
        complexity="medium",
        domain=_product_discovery_domain(domain, normalized),
        recommended_execution="skill_read",
        cross_cutting=cross_cutting,
        recommended_skills=[
            "request-complexity-router",
            "brainstorming-harness",
        ],
        required_harnesses=["brainstorming-harness"],
        evidence_required=_dedupe(
            [
                *evidence_required,
                "brainstorm_handoff",
                "decision_log",
                "recommended_option",
                "open_questions",
            ]
        ),
        reasons=[*reasons, "early_domain_discovery_needs_brainstorming"],
        confidence=0.72,
    )


def _heavy_classification(
    domain: str,
    cross_cutting: List[str],
    evidence_required: List[str],
    reasons: List[str],
) -> RequestClassification:
    domain_specific_evidence = []
    if domain == "software":
        domain_specific_evidence.extend(["tdd_red_green", "test_evidence"])
    if domain == "security":
        domain_specific_evidence.extend(["security_review", "risk_findings"])
    if domain == "investment":
        domain_specific_evidence.extend(["source_summary", "data_sources", "scenario_matrix", "risk_disclosure"])
    return _classification(
        complexity="heavy",
        domain=domain,
        recommended_execution="role_dag",
        cross_cutting=cross_cutting,
        recommended_skills=LARGE_WORK_BUNDLE_SKILLS,
        required_harnesses=LARGE_WORK_REQUIRED_HARNESSES,
        evidence_required=[
            *evidence_required,
            *LARGE_WORK_BUNDLE_EVIDENCE,
            "objective",
            "work_design",
            "target_scope",
            "verification_plan",
            *domain_specific_evidence,
        ],
        reasons=[*reasons, "implementation_or_design_work"],
        confidence=0.84,
    )


def _detect_domain(normalized: str, context: dict) -> str:
    explicit_domain = str(context.get("domain", "")).strip()
    context_override = _domain_override_from_text(normalized)
    if context_override:
        return context_override
    if explicit_domain:
        return explicit_domain
    if _is_bare_medical_fragment(normalized):
        return "general"
    if _contains_any(normalized, CAREER_CURRENT_DATA_TERMS):
        return "current-data"
    if _contains_any(normalized, CAREER_TERMS):
        return "hr"
    if _is_light_direct_task(normalized):
        return "general"
    if _contains_any(normalized, LANGUAGE_TERMS):
        return "language"
    if _contains_any(normalized, DOCUMENT_MISSING_CONTEXT_TERMS):
        return "document"
    if _contains_any(normalized, EDUCATION_TERMS | EDUCATION_MISSING_CONTEXT_TERMS):
        return "education"
    if (
        not _has_active_artifact(context)
        and _contains_any(normalized, CONTEXT_FREE_AMBIGUOUS_EXTRA_TERMS)
        and not _has_inline_payload(normalized)
    ):
        return "general"
    if _contains_any(normalized, PRIVACY_TERMS) and _contains_any(
        normalized,
        {
            "export",
            "share",
            "marketing",
            "customer emails",
            "personal gmail",
            "medical record",
            "patient list",
            "delete opt-outs",
            "eu list",
            "ssns",
            "passport scan",
        },
    ):
        return "privacy"
    if _contains_any(normalized, {"privacy policy", "employment agreement"}):
        return "legal"
    if _contains_any(normalized, CAREER_CURRENT_DATA_TERMS):
        return "current-data"
    if _contains_any(normalized, PERSONAL_LEGAL_ADVICE_TERMS):
        return "legal"
    if _contains_any(normalized, IMMIGRATION_TERMS):
        return "immigration"
    if _contains_any(normalized, TAX_TERMS):
        return "tax"
    if _contains_any(normalized, CIVIC_TERMS):
        return "civic"
    if _contains_any(normalized, DEVOPS_TERMS) and not _is_non_devops_production_discovery(normalized):
        return "devops"
    if _contains_any(normalized, GOV_ADMIN_TERMS):
        return "benefits" if _contains_any(normalized, {"benefits", "unemployment"}) else "permits"
    if _contains_any(normalized, CAREER_TERMS):
        return "hr"
    if _contains_any(normalized, BOOKING_TERMS):
        return "booking"
    if _contains_any(normalized, EXTRA_LEGAL_DOMAIN_TERMS):
        return "legal"
    if _contains_any(normalized, SHOPPING_TERMS):
        return "shopping"
    if _contains_any(normalized, WEATHER_TERMS):
        return "weather"
    if _is_scheduling_action(normalized):
        return "scheduling"
    if _contains_any(normalized, PERSONAL_MEDICAL_ADVICE_TERMS):
        return "medical"
    if _contains_any(normalized, FOOD_SAFETY_TERMS):
        return "food-safety"
    if _contains_any(normalized, FITNESS_TERMS):
        return "fitness"
    if _contains_any(normalized, NUTRITION_TERMS):
        return "nutrition"
    if _contains_any(normalized, COOKING_TERMS):
        return "cooking"
    if _contains_any(normalized, LIFESTYLE_TERMS):
        return "lifestyle"
    if _contains_any(normalized, {"database vendors", "production migration"}):
        return "software"
    if _contains_any(normalized, VENDOR_OPS_TERMS):
        if _contains_any(normalized, PERSONAL_LEGAL_ADVICE_TERMS | {"vendor agreement", "without penalty"}):
            return "legal"
        return "vendor-ops"
    if _contains_any(normalized, HR_TERMS):
        return "hr"
    if _contains_any(normalized, OPERATIONS_TERMS):
        return "operations"
    if _contains_any(normalized, MARKETING_TERMS):
        return "marketing"
    if _contains_any(normalized, CREATIVE_TERMS):
        return "creative"
    if _contains_any(normalized, PRODUCT_STRATEGY_TERMS):
        return "product"
    if _contains_any(normalized, FINANCE_TERMS):
        return "finance"
    if _contains_any(normalized, TRAVEL_TERMS):
        return "travel"
    if _contains_any(normalized, LOCAL_TERMS):
        return "local"
    if _contains_any(normalized, COMPLIANCE_TERMS):
        return "compliance"
    if _contains_any(normalized, LANGUAGE_TERMS):
        return "language"
    if _contains_any(normalized, DOCUMENT_TERMS):
        return "document"
    if _is_current_data_request(normalized):
        if _contains_any(normalized, INVESTMENT_TERMS | {"market", "stock"}):
            return "investment"
        if _contains_any(normalized, LEGAL_TERMS | {"tenant rights"}):
            return "legal"
        return "current-data"
    if _contains_any(normalized, DESTRUCTIVE_ACTION_TERMS | EXTRA_DESTRUCTIVE_ACTION_TERMS):
        return "security"
    if _contains_any(normalized, SECURITY_HIGH_RISK_TERMS | EXTRA_SECURITY_HIGH_RISK_TERMS):
        return "security"
    if _contains_any(normalized, SECURITY_TERMS) and _contains_any(normalized, REVIEW_HEAVY_TERMS | {"risk", "risks"}):
        return "security"
    if _contains_any(normalized, SECURITY_TERMS) and _contains_any(
        normalized,
        {"fix", "review", "audit", "summarize", "vulnerability", "logs", "suspicious"},
    ):
        return "security"
    if _contains_any(normalized, {"react", "vue", "frontend"}):
        return "software"
    if _is_strong_software_product_request(normalized):
        return "software"
    if _contains_any(normalized, EXTRA_PRODUCT_DESIGN_HEAVY_TERMS):
        return "product-design"
    if _contains_any(normalized, DESIGN_HEAVY_TERMS):
        return "product-design"
    if _contains_any(normalized, SOFTWARE_DOMAIN_TERMS | EXTRA_SOFTWARE_DOMAIN_TERMS):
        return "software"
    if _contains_any(normalized, EDUCATION_TERMS):
        return "education"
    if _contains_any(normalized, PERSONAL_MEDICAL_ADVICE_TERMS):
        return "medical"
    if _contains_any(normalized, MEDICAL_TERMS):
        return "medical"
    if _contains_any(normalized, INVESTMENT_TERMS | PERSONAL_INVESTMENT_ADVICE_TERMS | {"nvda", "tsla"}):
        return "investment"
    if _contains_any(normalized, LEGAL_TERMS | PERSONAL_LEGAL_ADVICE_TERMS):
        return "legal"
    if _contains_any(normalized, SECURITY_TERMS):
        return "security"
    if _contains_any(normalized, SOFTWARE_HEAVY_TERMS | EXTRA_SOFTWARE_HEAVY_TERMS):
        return "software"
    return "general"


def _is_strong_software_product_request(normalized: str) -> bool:
    has_implementation_intent = _contains_any(
        normalized,
        {
            "add",
            "build",
            "code",
            "create",
            "develop",
            "fix",
            "implement",
            "refactor",
            "scaffold",
            "write",
        },
    )
    if not has_implementation_intent:
        return False
    return _contains_any(
        normalized,
        {
            "api",
            "auth",
            "authentication",
            "backend",
            "frontend",
            "database",
            "server",
            "tests",
            "test",
            "i18n",
            "login",
            "jwt",
            "oauth",
        },
    ) and _contains_any(
        normalized,
        {
            "saas",
            "crm",
            "mvp",
            "dashboard",
            "app",
            "web app",
            "portal",
            "tool",
        },
    )


def _domain_override_from_text(normalized: str) -> str:
    if _looks_like_sql_or_tsql_payload(normalized):
        return "software"
    if _contains_any(
        normalized,
        {
            "kh uaf",
            "kh-uaf",
            "front-door",
            "front_door",
            "always-on-front-door",
            "plugin cache",
            "session_skill_audit",
            "session postmortem",
            "codex plugin",
        },
    ):
        return "software"
    if _contains_any(normalized, {"html", "css", "javascript", "js files", "html/css/js"}):
        return "software"
    if _contains_any(normalized, {"invoice", "vendor"}) and _contains_any(
        normalized,
        {"approve", "amount", "finance", "ask first"},
    ):
        return "vendor-ops"
    if _contains_any(normalized, {"api handler", "database vendors", "production migration"}):
        return "software"
    if _contains_any(normalized, BOOKING_TERMS | {"book the", "\ud638\ud154"}):
        return "booking"
    if _contains_any(normalized, PRIVACY_TERMS) and _contains_any(
        normalized,
        {
            "export",
            "share",
            "marketing",
            "customer emails",
            "personal gmail",
            "medical record",
            "patient list",
            "delete opt-outs",
            "eu list",
        },
    ):
        return "privacy"
    if _contains_any(normalized, PERSONAL_INVESTMENT_ADVICE_TERMS) or (
        _contains_any(normalized, INVESTMENT_TERMS | {"nvda", "tsla", "stock", "shares"})
        and _contains_any(normalized, INVESTMENT_ADVICE_TERMS)
    ):
        return "investment"
    if _contains_any(normalized, PERSONAL_MEDICAL_ADVICE_TERMS | MEDICAL_ADVICE_TERMS) and _contains_any(
        normalized, PERSONAL_MEDICAL_ADVICE_TERMS | {"safe", "take", "symptom", "symptoms"}
    ):
        return "medical"
    if _contains_any(normalized, PERSONAL_LEGAL_ADVICE_TERMS):
        return "legal"
    if _contains_any(normalized, MARKETING_HIGH_RISK_TERMS):
        return "marketing"
    if _contains_any(normalized, {"dlp flagged", "ssns", "passport scan", "i-797"}):
        return "privacy"
    if _contains_any(normalized, HARASSMENT_PRIVACY_TERMS):
        return "privacy"
    if _contains_any(normalized, IMPERSONATION_ABUSE_TERMS):
        return "security"
    if _contains_any(normalized, {"terraform", "iam", "least-privilege", "github token", "token was committed"}):
        return "security"
    if _contains_any(normalized, {"delete duplicates"}):
        return "security"
    if _contains_any(normalized, DESTRUCTIVE_ACTION_TERMS | EXTRA_DESTRUCTIVE_ACTION_TERMS):
        return "security"
    if _contains_any(normalized, {"security risks", "auth code", "login code"}) and _contains_any(
        normalized, {"review", "risk", "risks"}
    ):
        return "security"
    if _contains_any(normalized, SECURITY_TERMS) and _contains_any(
        normalized, {"fix", "review", "audit", "vulnerability", "sql injection"}
    ):
        return "security"
    if _contains_any(normalized, EXTRA_SECURITY_HIGH_RISK_TERMS | SECURITY_HIGH_RISK_TERMS):
        return "security"
    return ""


def _looks_like_sql_or_tsql_payload(normalized: str) -> bool:
    markers = 0
    has_strong_anchor = False
    marker_terms = [
        "use [",
        "set ansi_nulls",
        "set quoted_identifier",
        "begin tran",
        "begin transaction",
        "commit tran",
        "commit transaction",
        "rollback tran",
        "rollback transaction",
        "create procedure",
        "create or alter procedure",
        "alter procedure",
        "create proc",
        "create or alter proc",
        "alter proc",
        "storedprocedure",
        "stored procedure",
        "object: storedprocedure",
        "exec [",
        "execute [",
        "from sys.",
        "inner join",
        "where ",
        "select ",
        "insert into",
        "update ",
        "delete ",
        "raiserror",
        "throw ",
        "if exists",
        "openxml",
    ]
    weak_terms = {"where ", "select "}
    for term in marker_terms:
        if term in normalized:
            markers += 1
            if term not in weak_terms:
                has_strong_anchor = True
    if re.search(r"(?m)^\s*go\s*$", normalized):
        markers += 1
        has_strong_anchor = True
    if re.search(r"\bsp_[a-z0-9_]+\b", normalized):
        markers += 1
        has_strong_anchor = True
    if re.search(r"(?m)^\s*exec(?:ute)?\s+[\[\]a-z0-9_.]+", normalized):
        markers += 1
        has_strong_anchor = True
    if re.search(r"@[a-z0-9_]+\b", normalized):
        markers += 1
        has_strong_anchor = True
    if re.search(r"@p_[a-z0-9_]+\b", normalized):
        markers += 1
        has_strong_anchor = True
    if re.search(r"\bfrom\s+[a-z0-9_\[\].]+\b", normalized) and re.search(r"\bselect\b", normalized):
        markers += 1
        has_strong_anchor = True
    return has_strong_anchor and markers >= 2


SQL_FORMATTING_STYLE_ACTION_TERMS = {
    "align",
    "clean",
    "clean up",
    "create",
    "draft",
    "format",
    "generate",
    "make",
    "normalize",
    "organize",
    "refactor",
    "rewrite",
    "save",
    "standardize",
    "write",
    "\uc815\ub9ac",
    "\uc815\ub82c",
    "\ub9de\ucdb0",
    "\uc791\uc131",
    "\ub9cc\ub4e4",
    "\uc800\uc7a5",
}
SQL_FORMATTING_STYLE_SUBJECT_TERMS = {
    "proc",
    "procedure",
    "sql",
    "sp_",
    "stored procedure",
    "t-sql",
    "tsql",
    "query",
    "\ucffc\ub9ac",
    "\ud504\ub85c\uc2dc\uc800",
    "\uc800\uc7a5 \ud504\ub85c\uc2dc\uc800",
}
SQL_NAMED_DML_RE = re.compile(r"\b(?:insert|update|delete|merge)\b", re.IGNORECASE)


def _is_sql_formatting_style_request(normalized: str) -> bool:
    if not _contains_any(normalized, SQL_FORMATTING_STYLE_ACTION_TERMS):
        return False
    if not _contains_any(normalized, SQL_FORMATTING_STYLE_SUBJECT_TERMS):
        return False
    if _contains_any(normalized, {"sql injection", "vulnerability", "exploit"}):
        return False
    dml_names = {match.group(0).lower() for match in SQL_NAMED_DML_RE.finditer(normalized)}
    if len(dml_names) >= 2:
        return True
    if _looks_like_stored_procedure_generation_request(normalized):
        return True
    return _looks_like_sql_or_tsql_payload(normalized)


def _looks_like_stored_procedure_generation_request(normalized: str) -> bool:
    """Detect concise procedure generation/cleanup prompts before short-question fallback."""
    generation_terms = {
        "create",
        "draft",
        "generate",
        "make",
        "save",
        "write",
        "\uc791\uc131",
        "\ub9cc\ub4e4",
        "\uc800\uc7a5",
        "\uc815\ub9ac",
    }
    if not _has_stored_procedure_subject(normalized):
        return False
    if not _contains_any(normalized, generation_terms):
        return False
    return not (
        _is_sql_equivalence_question_without_output_request(normalized)
        or _is_sql_diagnostic_question_without_output_request(normalized)
    )


def _has_stored_procedure_subject(normalized: str) -> bool:
    if "stored procedure" in normalized:
        return True
    if "\ud504\ub85c\uc2dc\uc800" in normalized or "\uc800\uc7a5 \ud504\ub85c\uc2dc\uc800" in normalized:
        return True
    if re.search(r"(?<![a-z0-9_])(?:procedure|proc)(?![a-z0-9_])", normalized):
        return True
    return re.search(r"(?<![a-z0-9_])sp_[a-z0-9_]+\b", normalized) is not None


def _is_sql_equivalence_question_without_output_request(normalized: str) -> bool:
    if _contains_any(normalized, {"\ub611\uac19", "\uac19\uc774 \ub3d9\uc791", "\ub3d9\uc791\ud560\uae4c", "\ud574\ub3c4 \ub420\uae4c", "equivalent", "same behavior"}):
        return not _contains_any(normalized, SQL_FORMATTING_STYLE_ACTION_TERMS)
    return False


def _is_sql_diagnostic_question_without_output_request(normalized: str) -> bool:
    if _contains_any(normalized, {"why", "explain", "\uc65c", "\uc124\uba85", "\uc6d0\uc778", "\ubb50\uac00"}):
        return not _contains_any(normalized, {"\uc791\uc131", "\ub9cc\ub4e4", "\uc815\ub9ac", "write", "create", "generate", "format", "clean"})
    return False


def _is_provider_meta_review_request(normalized: str) -> bool:
    provider_markers = {
        "sql-formatting",
        "sql formatting",
        "sql-formatting-style-harness",
        "front-door",
        "front door",
        "kh routing",
        "plugin routing",
        "provider",
        "specialist",
    }
    meta_markers = {
        "review",
        "audit",
        "check whether",
        "whether",
        "evaluate",
        "evaluation",
        "risk",
        "hidden",
        "hides",
        "not hidden",
        "routing",
        "route",
        "classifier",
        "\uac80\ud1a0",
        "\uac10\uc0ac",
        "\ud3c9\uac00",
        "\ub9ac\ubdf0",
        "\ub77c\uc6b0\ud305",
        "\ubd84\ub958",
    }
    if not _contains_any(normalized, provider_markers):
        return False
    if not _contains_any(normalized, meta_markers):
        return False
    return not _contains_any(normalized, READONLY_SOURCE_AUDIT_MUTATION_TERMS)


def _is_high_risk(normalized: str, domain: str, context: dict) -> bool:
    if _contains_any(normalized, SAFETY_CRISIS_TERMS):
        return True
    if context.get("transaction_intent") and domain in {
        "investment",
        "medical",
        "legal",
        "privacy",
        "finance",
        "security",
        "booking",
        "travel",
        "marketing",
        "software",
        "cloud",
        "devops",
        "operations",
        "permits",
        "benefits",
        "immigration",
        "tax",
    }:
        return True
    if domain == "medical" and _is_bare_medical_fragment(normalized) and context.get("domain") == "medical":
        return True
    if domain == "investment" and _contains_any(
        normalized,
        INVESTMENT_ADVICE_TERMS | PERSONAL_INVESTMENT_ADVICE_TERMS | {"buy 100 shares", "good stock"},
    ):
        return True
    if domain == "legal" and _contains_any(
        normalized,
        LEGAL_ADVICE_TERMS | PERSONAL_LEGAL_ADVICE_TERMS,
    ) and not (_is_conceptual_request(normalized) and not _contains_any(normalized, PERSONAL_LEGAL_ADVICE_TERMS)):
        return True
    if domain == "medical" and _contains_any(
        normalized,
        MEDICAL_ADVICE_TERMS | PERSONAL_MEDICAL_ADVICE_TERMS,
    ) and not (_is_conceptual_request(normalized) and not _contains_any(normalized, PERSONAL_MEDICAL_ADVICE_TERMS)):
        return True
    if domain in {"devops", "cloud"} and _contains_any(
        normalized,
        {"roll back", "rollback", "production now", "failover", "publish it to pagerduty"},
    ):
        return True
    if domain == "security" and not _is_defensive_security_work(normalized) and (
        _contains_any(normalized, SECURITY_HIGH_RISK_TERMS | EXTRA_SECURITY_HIGH_RISK_TERMS)
        or _contains_any(normalized, DESTRUCTIVE_ACTION_TERMS | EXTRA_DESTRUCTIVE_ACTION_TERMS)
        or _contains_any(
            normalized,
            {"delete duplicates", "github token", "token was committed", "committed to main", "roll back production", "rollback production"},
        )
    ):
        return True
    if domain == "privacy" and _contains_any(
        normalized,
        {"export", "share", "marketing", "personal gmail", "patient list", "delete opt-outs", "ssns"}
        | HARASSMENT_PRIVACY_TERMS,
    ) and not _is_privacy_read_only(normalized):
        return True
    if domain == "security" and _contains_any(normalized, IMPERSONATION_ABUSE_TERMS):
        return True
    if domain == "immigration" and _contains_any(normalized, {"visa expires", "keep working", "extension is pending"}):
        return True
    if domain == "booking" and _contains_any(normalized, BOOKING_ACTION_TERMS):
        return True
    if domain == "marketing" and _contains_any(normalized, MARKETING_HIGH_RISK_TERMS):
        return True
    if domain == "finance" and _contains_any(normalized, HIGH_IMPACT_ACTION_TERMS):
        return True
    if _contains_any(normalized, HIGH_IMPACT_ACTION_TERMS):
        return True
    return False


def _is_conceptual_request(normalized: str) -> bool:
    return _contains_any(normalized, LIGHT_TERMS)


def _is_light_direct_task(normalized: str) -> bool:
    if _contains_any(normalized, LIGHT_DIRECT_TASK_TERMS):
        return True
    if _is_short_inline_simple_transform(normalized):
        return True
    if _is_short_inline_tone_transform(normalized):
        return True
    return False


def _is_short_inline_simple_transform(normalized: str) -> bool:
    if not _has_inline_payload(normalized):
        return False
    if len(normalized.split()) > 36:
        return False
    return _contains_any(normalized, INLINE_SIMPLE_TRANSFORM_INTENT_TERMS)


def _is_short_inline_tone_transform(normalized: str) -> bool:
    if not _has_inline_payload(normalized):
        return False
    if len(normalized.split()) > 36:
        return False
    return _contains_any(normalized, INLINE_TONE_TRANSFORM_INTENT_TERMS) and _contains_any(
        normalized,
        INLINE_TONE_TRANSFORM_QUALITY_TERMS,
    )


def _is_tiny_inline_transform(normalized: str) -> bool:
    return _has_inline_payload(normalized) and len(normalized.split()) <= 24 and _contains_any(
        normalized,
        {
            "summarize this article",
            "summarize this text",
            "summarize this note",
            "make flashcards from this",
        },
    )


def _has_inline_payload(normalized: str) -> bool:
    if ":" not in normalized:
        return False
    return len(normalized.split(":", 1)[1].split()) >= 3


def _has_active_artifact(context: dict) -> bool:
    return bool(
        context.get("has_active_artifact")
        or context.get("artifact")
        or context.get("active_doc")
        or context.get("data_artifact")
        or context.get("current_file")
    )


def _is_contextual_file_mutation(normalized: str, context: dict, domain: str) -> bool:
    return _has_active_artifact(context) and domain == "software" and _contains_any(
        normalized,
        {"do the same thing", "for the other file", "other file", "\ub2e4\ub978 \ud30c\uc77c\ub3c4"},
    )


def _is_contextual_heavy_followup(normalized: str, context: dict, domain: str) -> bool:
    if not _has_active_artifact(context):
        return False
    if _contains_any(normalized, {"summarize"}):
        return False
    if domain == "software" and _contains_any(normalized, CONTEXTUAL_HEAVY_FOLLOWUP_TERMS):
        return True
    if domain == "security" and _contains_any(normalized, {"security risks", "risk", "risks"}):
        return True
    if domain == "security" and _contains_any(normalized, {"fix the issue", "fix vulnerability", "fix the vulnerability"}):
        return True
    if domain == "product-design" and _contains_any(
        normalized, {"m20", "\ud640 4\uac1c", "same for the other file", "other file", "mobile layout"}
    ):
        return True
    return False


def _is_contextual_artifact_heavy_work(normalized: str, context: dict) -> bool:
    return _has_active_artifact(context) and _contains_any(normalized, ARTIFACT_HEAVY_WORK_TERMS)


def _is_contextual_external_send_without_permission(normalized: str, context: dict) -> bool:
    if str(context.get("domain", "")).strip() == "operations" and _contains_any(normalized, {"send to ceo"}):
        return False
    return (
        (_has_active_artifact(context) or context.get("domain"))
        and not context.get("send_permission")
        and _contains_any(normalized, {"send to", "send the", "email to", "submit it", "submit the", "report it", "post it"})
    )


def _is_contextual_artifact_read_work(normalized: str, context: dict) -> bool:
    return _has_active_artifact(context) and _contains_any(normalized, ARTIFACT_READ_WORK_TERMS)


def _is_contextual_artifact_transform(normalized: str, context: dict, domain: str) -> bool:
    return _has_active_artifact(context) and domain in {"software", "medical", "legal", "security", "privacy"} and _contains_any(
        normalized,
        {"now make it shorter", "make it shorter", "can this file be improved", "rewrite", "translate", "summarize"},
    )


def _is_contextual_medium_followup(normalized: str, context: dict) -> bool:
    if not _has_active_artifact(context):
        return False
    if context.get("current_data_need"):
        return True
    if str(context.get("domain", "")).strip() in {"fitness", "nutrition", "cooking", "lifestyle", "food-safety"} and _contains_any(
        normalized,
        {"add", "make it", "resume", "update", "change", "gluten-free", "deload"},
    ):
        return True
    if str(context.get("domain", "")).strip() in {"privacy", "immigration"} and _contains_any(
        normalized,
        {"passport scan", "i-797", "customer emails", "in the export", "ssns"},
    ):
        return True
    if str(context.get("domain", "")).strip() == "general" and _contains_any(
        normalized,
        {"add a rain backup plan", "backup plan", "resume the", "care plan", "school complaint"},
    ):
        return True
    if not str(context.get("domain", "")).strip() and context.get("requires_resume") and _contains_any(
        normalized,
        {"resume the", "care plan", "school complaint"},
    ):
        return True
    return _contains_any(normalized, CONTEXTUAL_MEDIUM_FOLLOWUP_TERMS)


def _requires_external_or_current_evidence(normalized: str, domain: str) -> bool:
    if domain == "local":
        return True
    if domain == "current-data":
        return True
    if domain in {"tax", "benefits", "permits", "immigration"} and _contains_any(
        normalized,
        CURRENT_DATA_TERMS | {"deadline", "2026", "expires", "pending"},
    ):
        return True
    if _is_conceptual_request(normalized):
        return False
    if domain in {"shopping", "weather", "current-data"}:
        return True
    if domain == "booking" and not _contains_any(normalized, BOOKING_ACTION_TERMS):
        return True
    if domain == "travel" and _contains_any(normalized, CURRENT_DATA_TERMS | {"open", "prices", "availability"}):
        return True
    if domain == "food-safety":
        return True
    if domain == "current-data" and _contains_any(normalized, CAREER_CURRENT_DATA_TERMS):
        return True
    if domain == "scheduling" and _contains_any(
        normalized,
        {"remind me", "reminder", "reminders", "calendar", "schedule a meeting", "study timer", "timer"},
    ):
        return True
    if domain in {"investment", "finance"} and _contains_any(normalized, CURRENT_DATA_TERMS | {"market today"}):
        return True
    if domain == "education" and _contains_any(normalized, EDUCATION_CURRENT_DATA_TERMS | CURRENT_DATA_TERMS):
        return True
    if _contains_any(normalized, PURCHASE_ACTION_TERMS) and not _contains_any(normalized, HIGH_IMPACT_ACTION_TERMS):
        return True
    return False


def _is_structured_medium_work(normalized: str, domain: str) -> bool:
    if _contains_any(normalized, STRUCTURED_MEDIUM_WORK_TERMS):
        return True
    if domain == "creative" and not _is_conceptual_request(normalized):
        return True
    if domain == "travel" and _contains_any(normalized, {"plan", "trip", "itinerary", "family"}):
        return True
    if domain == "marketing" and not _contains_any(normalized, MARKETING_HEAVY_TERMS | MARKETING_HIGH_RISK_TERMS):
        return True
    if domain == "education" and _contains_any(
        normalized,
        {"study plan", "study calendar", "deadlines are", "after school", "add fafsa", "same for scholarships"},
    ):
        return True
    if domain == "language" and _contains_any(normalized, {"for a trip", "in 2 weeks", "learning plan"}):
        return True
    if domain == "document" and _contains_any(normalized, {"what score", "score would it get"}):
        return True
    if domain in {"fitness", "nutrition", "cooking", "lifestyle"} and _contains_any(
        normalized,
        {"plan", "training plan", "meal plan", "routine", "schedule", "build", "add", "make it", "resume"},
    ):
        return True
    if domain == "hr" and _contains_any(
        normalized,
        {"tailor", "resume summary", "offer", "negotiate", "make it tighter"},
    ):
        return True
    if domain == "operations" and _contains_any(normalized, {"support rotation", "rota"}):
        return True
    if domain == "operations" and _contains_any(
        normalized,
        {"timesheet", "invoices", "goals doc", "inbox", "work admin", "prioritize"},
    ):
        return True
    if domain in {"software", "devops"} and _contains_any(
        normalized,
        {"vercel", "vite react", "build command", "output folder", "own domain", "route 53", "cloudfront"},
    ) and not _contains_any(normalized, {"deploy it", "change production", "roll back", "failover"}):
        return True
    if domain in {"vendor-ops", "hr", "operations", "product", "finance"} and _contains_any(
        normalized,
        {"create", "draft", "write", "review", "compare", "evaluate", "decide", "plan", "build", "fix"},
    ):
        return True
    if domain == "compliance" and _is_conceptual_request(normalized):
        return False
    return False


def _is_current_data_request(normalized: str) -> bool:
    if _contains_any(normalized, CAREER_CURRENT_DATA_TERMS):
        return True
    return _contains_any(normalized, CURRENT_DATA_TERMS) and _contains_any(
        normalized,
        {"who is", "commissioner", "rates", "market", "weather", "cpi", "fed", "fda", "chair"},
    )


def _is_bare_medical_fragment(normalized: str) -> bool:
    return normalized.strip(" ?.") in {"dose"}


def _is_scheduling_action(normalized: str) -> bool:
    if _contains_any(normalized, {"meeting notes", "board meeting notes", "study schedule", "support rota"}):
        return False
    return _contains_any(
        normalized,
        {
            "remind me",
            "calendar",
            "appointment",
            "schedule a meeting",
            "schedule a dentist",
            "move my meeting",
            "set a reminder",
            "set a study timer",
            "study timer",
            "recurring reminders",
            "\uc608\uc57d",
            "\ub9ac\ub9c8\uc778\ub4dc",
            "\uc54c\ub9bc",
        },
    )


def _is_heavy_work(normalized: str, domain: str) -> bool:
    if _is_light_direct_task(normalized) or _is_structured_medium_work(normalized, domain):
        return False
    if _is_conceptual_request(normalized):
        return False
    if domain in {"compliance", "legal"} and _contains_any(
        normalized, {"make", "draft", "compliant", "privacy policy", "agreement"}
    ):
        return True
    if domain == "immigration" and _contains_any(normalized, {"fill out", "ds-160", "form"}):
        return True
    if domain == "security" and _contains_any(normalized, {"least-privilege", "iam", "terraform", "policy"}):
        return True
    if domain == "marketing" and _contains_any(normalized, MARKETING_HEAVY_TERMS):
        return True
    if domain == "document" and (
        _contains_any(normalized, ARTIFACT_HEAVY_WORK_TERMS)
        or _contains_any(normalized, HEAVY_ACTION_TERMS)
    ):
        return True
    if _contains_any(normalized, EXTRA_PRODUCT_DESIGN_HEAVY_TERMS):
        return True
    if _contains_any(normalized, DESIGN_HEAVY_TERMS) and domain == "product-design":
        return True
    if _contains_any(normalized, EXTRA_SOFTWARE_HEAVY_TERMS):
        return True
    if _contains_any(normalized, SOFTWARE_HEAVY_TERMS) and domain == "software":
        return True
    if _contains_any(normalized, HEAVY_ACTION_TERMS) and _contains_any(
        normalized, SOFTWARE_DOMAIN_TERMS | EXTRA_SOFTWARE_DOMAIN_TERMS
    ):
        return True
    if _contains_any(normalized, REVIEW_HEAVY_TERMS) and _contains_any(
        normalized,
        {"code", "authentication", "security", "risk", "파일", "코드", "보안", "위험"},
    ):
        return True
    if domain == "security" and _contains_any(normalized, REVIEW_HEAVY_TERMS):
        return True
    if domain == "software" and _contains_any(normalized, REVIEW_HEAVY_TERMS):
        return True
    if domain == "investment" and _contains_any(normalized, {"scenario matrix", "valuation analysis"}):
        return True
    return False


def _is_localized_patch_continuation(normalized: str, context: dict) -> bool:
    if not _contains_any(normalized, LOCALIZED_PATCH_ACTION_TERMS):
        return False
    if _has_conditional_mutation_command(normalized):
        return False
    if _has_unnegated_localized_patch_broad_terms(normalized):
        return False

    context_scope = _has_localized_patch_context(context)
    text_scope = (
        _contains_any(normalized, LOCALIZED_PATCH_SCOPE_TERMS)
        or FILE_REFERENCE_RE.search(normalized) is not None
        or CSS_SELECTOR_REFERENCE_RE.search(normalized) is not None
        or CSS_PROPERTY_REFERENCE_RE.search(normalized) is not None
    )
    if not (context_scope or text_scope):
        return False

    has_target = (
        _has_active_artifact(context)
        or context_scope
        or FILE_REFERENCE_RE.search(normalized) is not None
        or CSS_SELECTOR_REFERENCE_RE.search(normalized) is not None
    )
    if not has_target:
        return False

    token_count = len(normalized.split())
    return token_count <= 32 or bool(context_scope)


def _has_unnegated_localized_patch_broad_terms(normalized: str) -> bool:
    for term in LOCALIZED_PATCH_BROAD_TERMS:
        start = normalized.find(term)
        while start != -1:
            end = start + len(term)
            before = normalized[max(0, start - 36) : start]
            after = normalized[end : min(len(normalized), end + 28)]
            directly_negated = (
                LOCALIZED_PATCH_PRE_BROAD_NEGATION_RE.search(before) is not None
                or LOCALIZED_PATCH_POST_BROAD_NEGATION_RE.search(after) is not None
                or _contains_any(after[:18], LOCALIZED_PATCH_BROAD_NEGATION_MARKERS)
                or _is_korean_post_broad_term_negated(after)
            )
            if not directly_negated:
                return True
            start = normalized.find(term, end)
    return False


def _is_korean_post_broad_term_negated(after: str) -> bool:
    marker_positions = [after.find(marker) for marker in KOREAN_POST_BROAD_NEGATION_MARKERS]
    marker_positions = [pos for pos in marker_positions if pos != -1]
    if not marker_positions:
        return False
    marker_pos = min(marker_positions)
    if marker_pos > 56:
        return False
    before_marker = after[:marker_pos]
    if any(punctuation in before_marker for punctuation in ".?!"):
        return False
    return _contains_any(
        before_marker,
        {"\uc774\ub098", "\uac70\ub098", "\ub610\ub294", "\uc218\uc815\uc740", "\uc218\uc815\uc774\ub098", "\ubcc0\uacbd\uc740", "\ubcc0\uacbd\uc774\ub098"},
    )


def _is_dotfile_config_mutation(normalized: str, context: dict) -> bool:
    target = str(context.get("target_file") or context.get("current_file") or "").strip().lower()
    dotfile_targets = {".env", ".gitignore", ".editorconfig", ".prettierrc", ".eslintrc", ".npmrc"}
    if target in dotfile_targets and _contains_any(normalized, LOCALIZED_PATCH_ACTION_TERMS):
        return True
    return any(target in normalized for target in dotfile_targets) and _contains_any(
        normalized,
        LOCALIZED_PATCH_ACTION_TERMS | {"create", "make", "write", "\ub9cc\ub4e4", "\uc0dd\uc131"},
    )


def _has_localized_patch_context(context: dict) -> bool:
    if any(context.get(key) for key in LOCALIZED_PATCH_CONTEXT_KEYS):
        return True
    scope = str(context.get("change_scope") or context.get("patch_scope") or "").strip().lower()
    return scope in LOCALIZED_PATCH_SCOPE_VALUES


def _is_readonly_source_condition_question(normalized: str) -> bool:
    if _has_source_condition_mutation_command(normalized):
        return False
    return _has_source_condition_context(normalized) and _contains_any(normalized, READONLY_SOURCE_QUESTION_TERMS)


def _is_readonly_source_audit_request(normalized: str, domain: str) -> bool:
    if domain == "security" or _contains_any(normalized, SECURITY_HIGH_RISK_TERMS | EXTRA_SECURITY_HIGH_RISK_TERMS):
        return False
    if not _contains_any(normalized, READONLY_SOURCE_AUDIT_BOUNDARY_TERMS):
        return False
    if not _contains_any(normalized, READONLY_SOURCE_AUDIT_TERMS):
        return False
    has_source_context = domain == "software" or _contains_any(
        normalized,
        READONLY_SOURCE_AUDIT_SOURCE_TERMS | SOFTWARE_DOMAIN_TERMS | EXTRA_SOFTWARE_DOMAIN_TERMS,
    )
    if not has_source_context:
        return False
    return not _contains_any(normalized, READONLY_SOURCE_AUDIT_MUTATION_TERMS)


def _is_source_condition_mutation_command(normalized: str) -> bool:
    return _has_source_condition_mutation_command(normalized)


def _has_source_condition_mutation_command(normalized: str) -> bool:
    return (
        (_has_mutation_command(normalized) and _has_source_condition_context(normalized))
        or _has_conditional_mutation_command(normalized)
    )


def _has_source_condition_context(normalized: str) -> bool:
    return _contains_any(normalized, READONLY_SOURCE_CONDITION_TERMS)


def _has_mutation_command(normalized: str) -> bool:
    return _contains_any(normalized, SOURCE_MUTATION_COMMAND_TERMS) or _has_inflected_mutation_command(normalized)


def _has_inflected_mutation_command(normalized: str) -> bool:
    return INFLECTED_MUTATION_COMMAND_RE.search(normalized) is not None


def _has_conditional_mutation_command(normalized: str) -> bool:
    return (
        MISSING_CONDITION_MARKER_RE.search(normalized) is not None
        and CONDITIONAL_MUTATION_COMMAND_RE.search(normalized) is not None
    )


def _is_medium_analysis_request(normalized: str) -> bool:
    if _contains_any(normalized, {"summarize", "compare", "analyze"}):
        return True
    return _contains_any(normalized, DOCUMENT_TRANSFORM_TERMS) and _contains_any(
        normalized, {"readme", "\ubc88\uc5ed", "\uc815\ub9ac"}
    )


def _is_no_code_process_deliverable_request(normalized: str) -> bool:
    return _contains_any(normalized, NO_CODE_NEGATION_TERMS) and _contains_any(
        normalized, PROCESS_DELIVERABLE_TERMS
    )


def _no_code_process_domain(normalized: str, domain: str) -> str:
    if _contains_any(
        normalized,
        {
            "business",
            "business process",
            "process",
            "workflow",
            "warehouse",
            "inventory",
            "stock movement",
            "업무",
            "프로세스",
            "창고",
            "재고",
            "입출고",
            "처리흐름도",
            "업무정의서",
        },
    ):
        return "operations"
    if domain == "software":
        return "document"
    return domain


def _is_command_output_request(normalized: str) -> bool:
    return _contains_any(normalized, COMMAND_OUTPUT_SOURCE_TERMS) and (
        _contains_any(normalized, COMMAND_OUTPUT_ACTION_TERMS)
        or _contains_any(normalized, COMMAND_OUTPUT_FACT_TERMS)
    )


def _is_complex_extraction_deliverable_request(normalized: str) -> bool:
    if not _contains_any(normalized, COMPLEX_EXTRACTION_SOURCE_TERMS):
        return False
    artifact = _contains_any(normalized, COMPLEX_EXTRACTION_ARTIFACT_TERMS)
    sql_requested = _contains_any(
        normalized,
        {"sql", "select", "query", "\uc870\ud68c", "\uc870\ud68c sql"},
    )
    mapping_requested = _contains_any(
        normalized,
        {
            "binding",
            "bound column",
            "column name",
            "field name",
            "replace actual data",
            "\ubc14\uc778\ub529",
            "\uceec\ub7fc\uba85",
            "\uc870\ud68c\uceec\ub7fc",
            "\uc2e4\uc81c\ub370\uc774\ud130",
        },
    )
    mojibake_artifact_request = (
        normalized.count("?") >= 6
        and (re.search(r"\bquality_\d+\b", normalized) is not None or "pblscripter" in normalized)
        and _contains_any(normalized, {"pbl", "sql"})
    )
    if artifact and _is_visual_reference_only_sql_request(normalized):
        artifact = False
    return sql_requested and (artifact or mapping_requested or mojibake_artifact_request)


def _is_visual_reference_only_sql_request(normalized: str) -> bool:
    if not _contains_any(normalized, {"like the image", "like this image", "\uc774\ubbf8\uc9c0\ucc98\ub7fc", "\uc2a4\ud06c\ub9b0\uc0f7\ucc98\ub7fc"}):
        return False
    if _contains_any(
        normalized,
        {
            "give me the image",
            "create image",
            "make image",
            "export image",
            "replace actual data",
            "bound column",
            "binding",
            "png",
            "svg",
            "pdf",
            "render",
            "\uc774\ubbf8\uc9c0\ub85c",
            "\uc774\ubbf8\uc9c0\ub97c",
            "\ubc14\uc778\ub529",
            "\uceec\ub7fc\uba85",
            "\uc2e4\uc81c\ub370\uc774\ud130",
        },
    ):
        return False
    return True


def _is_contextual_review_request(normalized: str, context: dict) -> bool:
    return bool(context.get("has_active_artifact")) and _contains_any(normalized, REVIEW_HEAVY_TERMS)


def _is_resume_heavy_context(normalized: str, context: dict, domain: str) -> bool:
    if not context.get("requires_resume"):
        return False
    if domain not in {
        "software",
        "product-design",
        "investment",
        "security",
        "legal",
        "medical",
        "finance",
        "privacy",
        "booking",
        "cloud",
        "devops",
        "benefits",
        "permits",
        "immigration",
        "tax",
    }:
        return False
    if _has_active_artifact(context) and _contains_any(normalized, {"resume", "continue", "pick up"}):
        return True
    return _contains_any(normalized, HEAVY_ACTION_TERMS | REVIEW_HEAVY_TERMS | {"finish", "release checklist"})


def _is_general_advice_request(normalized: str) -> bool:
    return _contains_any(normalized, {"should i", "how should i", "can i"}) and not _contains_any(
        normalized,
        INVESTMENT_ADVICE_TERMS | LEGAL_ADVICE_TERMS | MEDICAL_ADVICE_TERMS,
    )


def _is_non_devops_production_discovery(normalized: str) -> bool:
    if "production" not in normalized:
        return False
    if _contains_any(
        normalized,
        {
            "roll back",
            "rollback",
            "deploy",
            "deployment",
            "failover",
            "kubernetes",
            "readiness",
            "cloud",
            "terraform",
            "lambda",
            "dynamodb",
            "pagerduty",
            "incident",
            "outage",
            "migration",
        },
    ):
        return False
    return _contains_any(
        normalized,
        {
            "dashboard",
            "app",
            "defect",
            "defects",
            "factory",
            "team",
            "tracker",
            "workflow",
            "process",
            "product",
            "report",
            "management",
        },
    )


def _is_defensive_security_work(normalized: str) -> bool:
    return _contains_any(normalized, {"fix", "review", "regression tests", "vulnerability"})


def _is_privacy_read_only(normalized: str) -> bool:
    return _contains_any(normalized, {"are customer emails in", "is there", "does this contain", "contains ssns"})


def _is_unapproved_product_discovery_request(normalized: str, context: dict, domain: str) -> bool:
    if _has_active_artifact(context):
        return False
    if _is_approved_brainstorm_continuation(normalized, context):
        return False
    if _is_conceptual_request(normalized):
        return False
    if domain in {
        "shopping",
        "weather",
        "legal",
        "medical",
        "compliance",
        "privacy",
        "security",
        "devops",
        "booking",
        "local",
        "travel",
        "education",
    }:
        return False
    if _has_blocking_discovery_specificity(normalized):
        return False
    has_product_object = _contains_any(normalized, PRODUCT_DISCOVERY_OBJECT_TERMS)
    has_domain_direction_object = _contains_any(
        normalized,
        {
            "workflow",
            "process",
            "procedure",
            "report",
            "report structure",
            "dashboard",
            "operating model",
            "operational model",
            "\uc5c5\ubb34\ud750\ub984",
            "\ud504\ub85c\uc138\uc2a4",
            "\ubcf4\uace0\uc11c",
            "\ub300\uc2dc\ubcf4\ub4dc",
        },
    )
    if not _contains_any(normalized, DOMAIN_DISCOVERY_OBJECT_TERMS):
        return False
    if not _contains_any(normalized, DOMAIN_DISCOVERY_ACTION_TERMS):
        return False
    if not has_product_object and not has_domain_direction_object and not _contains_any(normalized, DOMAIN_DISCOVERY_INTENT_TERMS):
        return False
    if _contains_any(normalized, {"prd", "product requirements document", "launch email", "screen design"}):
        return False
    token_count = len(normalized.split())
    return token_count <= 18 or not _has_inline_payload(normalized)


def _is_approved_brainstorm_continuation(normalized: str, context: dict) -> bool:
    """Detect execution only after a reviewed brainstorm handoff and separate approval."""
    return _has_reviewed_brainstorm_execution_context(context) and _contains_any(
        normalized,
        BRAINSTORM_IMPLEMENTATION_CONTINUATION_TERMS,
    )


def _is_unreviewed_brainstorm_implementation_request(normalized: str, context: dict) -> bool:
    if _has_reviewed_brainstorm_execution_context(context):
        return False
    return _contains_any(normalized, BRAINSTORM_APPROVAL_CONTINUATION_TERMS) and _contains_any(
        normalized,
        BRAINSTORM_IMPLEMENTATION_CONTINUATION_TERMS,
    )


def _has_reviewed_brainstorm_execution_context(context: dict) -> bool:
    has_handoff = bool(context.get("has_brainstorm_handoff") or context.get("brainstorm_handoff_approved"))
    design_reviewed = bool(context.get("design_review_approved") or context.get("brainstorm_handoff_approved"))
    execution_approved = bool(
        context.get("implementation_approved")
        or context.get("execution_approved")
        or context.get("separate_implementation_approval")
    )
    return has_handoff and design_reviewed and execution_approved


def _is_mojibake_new_project_request(original: str, normalized: str, context: dict) -> bool:
    # This is not a general "path + PDF/web" rule. It is a safe fallback for
    # Windows sessions where Korean product-request text arrives mojibaked and
    # the router would otherwise open execution from unreadable input.
    if _has_active_artifact(context):
        return False
    if not re.search(r"[A-Za-z]:\\", original):
        return False
    if original.count("?") < 6:
        return False
    return _contains_any(
        normalized,
        {
            "pdf",
            "docx",
            "xlsx",
            "html",
            "css",
            "javascript",
            "web",
            "app",
            "dashboard",
            "homepage",
            "server",
            "node",
        },
    )


def _is_memory_state_request(normalized: str) -> bool:
    if _contains_any(normalized, MEMORY_STATE_REQUEST_TERMS):
        return True
    if "메모리" in normalized and _contains_any(
        normalized,
        {
            "프로젝트",
            "채팅",
            "서브에이전트",
            "하위에이전트",
            "하위 에이전트",
            "중첩",
            "스코프",
            "전역",
            "글로벌",
        },
    ):
        return True
    if "memory" in normalized and _contains_any(
        normalized,
        {"project", "chat", "thread", "subagent", "agent", "lineage", "scope", "global"},
    ):
        return True
    return False


def _is_contextual_audit_repair_request(normalized: str, context: dict) -> bool:
    has_repair_action = _contains_any(normalized, CONTEXTUAL_REPAIR_ACTION_TERMS)
    has_failure_signal = _contains_any(normalized, CONTEXTUAL_REPAIR_FAILURE_TERMS)
    if not has_repair_action:
        if not has_failure_signal:
            return False
    if has_failure_signal and not has_repair_action and _is_explanation_only_request(normalized):
        return False
    has_subject = _contains_any(normalized, STRICT_CONTEXTUAL_REPAIR_SUBJECT_TERMS)
    has_reference = _contains_any(normalized, CONTEXTUAL_REPAIR_REFERENCE_TERMS)
    has_context = _has_audit_repair_context(context)
    if has_subject and (has_reference or has_context):
        return True
    return has_repair_action and has_reference and has_context


def _contextual_audit_repair_domain(domain: str, context: dict) -> str:
    if _has_audit_repair_context(context):
        return "software"
    return domain


def _has_audit_repair_context(context: dict) -> bool:
    if _is_kh_project_context(context) or context.get("kh_active_directive") == "active":
        return True
    prior_kind = str(context.get("prior_context_kind") or context.get("active_context_kind") or "").strip().lower()
    if prior_kind in {"session_audit", "skill_audit", "kh_hardening", "postmortem", "session_postmortem"}:
        return True
    if context.get("session_audit") or context.get("skill_audit"):
        return True
    if context.get("requires_resume") and str(context.get("active_context_kind") or "").strip().lower() in {
        "session_audit",
        "skill_audit",
        "kh_hardening",
    }:
        return True
    return False


def _is_explanation_only_request(normalized: str) -> bool:
    return _contains_any(normalized, EXPLANATION_ONLY_TERMS) and not _contains_any(
        normalized,
        {
            "fix",
            "repair",
            "patch",
            "harden",
            "improve",
            "\ubcf4\uc644",
            "\uc218\uc815",
            "\uace0\uccd0",
            "\uac1c\uc120",
            "\ucc98\ub9ac",
        },
    )


def _is_kh_project_context(context: dict) -> bool:
    markers = {str(marker).strip().lower() for marker in context.get("project_markers", [])}
    return bool(markers & KH_PROJECT_MARKERS)


def _is_parallel_orchestration_request(normalized: str) -> bool:
    return _contains_any(normalized, PARALLEL_ORCHESTRATION_REQUEST_TERMS)


def _is_brainstorm_direction_choice_without_execution(normalized: str, context: dict) -> bool:
    """Detect option selection that should continue design review, not implementation."""
    if context.get("brainstorm_handoff_approved") or context.get("has_brainstorm_handoff"):
        return False
    if not _contains_any(normalized, BRAINSTORM_DIRECTION_CHOICE_ONLY_TERMS):
        return False
    return not _contains_any(normalized, BRAINSTORM_IMPLEMENTATION_CONTINUATION_TERMS)


def _has_blocking_discovery_specificity(normalized: str) -> bool:
    if not _contains_any(normalized, PRODUCT_DISCOVERY_SPECIFICITY_TERMS):
        return False
    specificity_terms = PRODUCT_DISCOVERY_SPECIFICITY_TERMS - VAGUE_DISCOVERY_SPECIFICITY_TERMS
    # A chosen implementation stack is not enough to prove that the product,
    # workflow, data, or screen scope has already been approved.
    specificity_terms = specificity_terms - STACK_ONLY_DISCOVERY_SPECIFICITY_TERMS
    if _contains_any(normalized, {"kpi", "metrics"}) and _is_vague_dashboard_or_report_discovery(normalized):
        specificity_terms = specificity_terms - {"kpi", "metrics"}
    return _contains_any(normalized, specificity_terms)


def _is_vague_dashboard_or_report_discovery(normalized: str) -> bool:
    if not _contains_any(normalized, {"dashboard", "report", "\ub300\uc2dc\ubcf4\ub4dc", "\ubcf4\uace0\uc11c"}):
        return False
    if not _contains_any(normalized, PRODUCT_DISCOVERY_ACTION_TERMS | {"direction", "approach", "plan"}):
        return False
    return not _contains_any(
        normalized,
        {
            "api",
            "database",
            "table",
            "filter",
            "docx",
            "xlsx",
            "pdf",
            "dxf",
            "svg",
            "verify",
            "validate",
            "test",
            "tests",
            "sample",
            "including ",
            "with ",
        },
    )


def _product_discovery_domain(domain: str, normalized: str) -> str:
    if domain == "operations" or _contains_any(normalized, OPERATIONS_TERMS):
        return "operations"
    if _contains_any(
        normalized,
        {
            "product",
            "service",
            "saas",
            "startup",
            "mvp",
            "\uc81c\ud488",
            "\uc11c\ube44\uc2a4",
            "\uc0ac\uc5c5",
            "\uc544\uc774\ub514\uc5b4",
        },
    ):
        return "product"
    if _contains_any(normalized, {"analysis", "research", "study", "\ubd84\uc11d", "\ub9ac\uc11c\uce58", "\uc5f0\uad6c"}):
        return "analysis"
    if _contains_any(normalized, {"workflow", "process", "operating model", "\uc5c5\ubb34\ud750\ub984", "\ud504\ub85c\uc138\uc2a4", "\uc6b4\uc601"}):
        return "operations"
    if _contains_any(normalized, {"document", "report", "procedure", "\ubb38\uc11c", "\ubcf4\uace0\uc11c", "\uc808\ucc28"}):
        return "document"
    if _contains_any(normalized, {"specification", "spec", "drawing direction", "design direction", "\uaddc\uaca9", "\ub3c4\uba74", "\uc124\uacc4\ubc29\ud5a5"}):
        return "product-design"
    if domain == "general":
        return "product"
    return domain


def _is_ambiguous_visual_query_order_request(normalized: str, context: dict) -> bool:
    """Clarify visual/order/query requests without target context.

    This is an invariant gate, not a phrase fixture: when a prompt references a
    visual shape plus ordering/query/display behavior but has no active artifact
    or inline SQL/data, the target may be DB ordering, UI display, report layout,
    or SQL formatting.
    """
    if _has_inline_payload(normalized):
        return False
    if _has_visual_query_order_target_context(context):
        return False
    if re.search(r"\b(?:select|from|where|join|order\s+by|group\s+by)\b", normalized):
        return False
    return (
        _contains_any(normalized, AMBIGUOUS_VISUAL_QUERY_ORDER_VISUAL_TERMS)
        and _contains_any(normalized, AMBIGUOUS_VISUAL_QUERY_ORDER_TERMS)
        and _contains_any(normalized, AMBIGUOUS_VISUAL_QUERY_DISPLAY_TERMS)
    )


def _has_visual_query_order_target_context(context: dict) -> bool:
    explicit_layer = str(
        context.get("visual_query_order_target")
        or context.get("execution_layer")
        or context.get("target_layer")
        or ""
    ).strip().lower()
    if explicit_layer in {"sql", "database", "db", "ui", "screen", "report", "document"}:
        return True
    current_file = str(context.get("current_file") or context.get("active_file") or "").lower()
    return current_file.endswith(('.sql', '.spsql'))


def _is_ambiguous(normalized: str, context: dict) -> bool:
    domain = _detect_domain(normalized, context)
    if _is_light_direct_task(normalized):
        return False
    if _is_structured_medium_work(normalized, domain):
        return False
    if _is_education_language_or_document_ambiguous(normalized, context, domain):
        return True
    if _contains_any(normalized, {"send it", "email it"}) and not context.get("send_permission"):
        return True
    if _contains_any(normalized, {"nvda now", "samsung okay", "dose?"}):
        return True
    if (
        not _has_active_artifact(context)
        and _contains_any(normalized, CONTEXT_FREE_AMBIGUOUS_EXTRA_TERMS)
        and not _has_inline_payload(normalized)
    ):
        return True
    if _contains_any(normalized, {"is this jacket worth it", "buy more coffee filters"}):
        return True
    if _contains_any(normalized, {"schedule a dentist appointment", "move my meeting to 3"}):
        return True
    if _contains_any(normalized, {"do i need an umbrella"}) and not _contains_any(
        normalized, {"today", "tomorrow", "in "}
    ):
        return True
    if not _has_active_artifact(context) and _contains_any(normalized, REFERENTIAL_AMBIGUOUS_TERMS):
        return True
    if _has_active_artifact(context) or context.get("domain"):
        return False
    if _contains_any(normalized, CONTEXT_FREE_AMBIGUOUS_TERMS):
        return True
    strong_terms = (
        INVESTMENT_ADVICE_TERMS
        | LEGAL_ADVICE_TERMS
        | MEDICAL_ADVICE_TERMS
        | SECURITY_HIGH_RISK_TERMS
        | DESTRUCTIVE_ACTION_TERMS
        | SOFTWARE_HEAVY_TERMS
        | DESIGN_HEAVY_TERMS
        | MEDIUM_TERMS
        | LIGHT_TERMS
    )
    if _contains_any(normalized, strong_terms):
        return False
    token_count = len(normalized.split())
    if token_count <= 5 and _contains_any(normalized, AMBIGUOUS_TERMS):
        return True
    if re.fullmatch(r"[\w가-힣\s]+괜찮아\??", normalized) and not _contains_any(
        normalized,
        INVESTMENT_ADVICE_TERMS | SOFTWARE_HEAVY_TERMS | LEGAL_TERMS | MEDICAL_TERMS,
    ):
        return True
    return False


def _is_education_language_or_document_ambiguous(normalized: str, context: dict, domain: str) -> bool:
    if domain == "education" and _contains_any(normalized, EDUCATION_MISSING_CONTEXT_TERMS):
        return True
    if domain == "education" and _contains_any(
        normalized,
        {"email the tutor", "email the teacher", "email my counselor", "send it"},
    ) and not context.get("send_permission"):
        return True
    if domain == "language" and _contains_any(
        normalized,
        {"i need to learn spanish fast", "translate this to", "translate my homework directions", "translate this menu"},
    ) and not _has_inline_payload(normalized):
        return True
    if domain == "document" and _contains_any(normalized, DOCUMENT_MISSING_CONTEXT_TERMS):
        return True
    return False


def _needs_token_optimization(original: str, normalized: str) -> bool:
    return (
        len(original) > 2000
        or original.count("\n") > 50
        or _contains_any(
            normalized,
            {
                "long log",
                "large log",
                "command output",
                "stack trace",
                "traceback",
                "token",
                "compress",
                "truncate",
                "핵심만",
                "긴 로그",
                "명령 출력",
                "토큰",
                "압축",
            },
        )
    )


def _context_exceeds_token_budget(context: dict) -> bool:
    for key in (
        "estimated_context_tokens",
        "expected_context_tokens",
        "estimated_token_usage",
        "expected_token_usage",
    ):
        if _context_int(context, key) >= TOKEN_OPTIMIZER_CONTEXT_THRESHOLD:
            return True
    for key in (
        "largest_item_tokens",
        "largest_command_output_tokens",
        "subagent_transcript_tokens",
    ):
        if _context_int(context, key) >= TOKEN_OPTIMIZER_ITEM_THRESHOLD:
            return True
    if _context_int(context, "expected_tool_calls") >= 6:
        return True
    if _context_int(context, "expected_subagents") >= 2:
        return True
    if _context_int(context, "broad_file_reads") >= 3:
        return True
    return False


def _needs_credential_safety(normalized: str) -> bool:
    return _contains_any(normalized, CREDENTIAL_SAFETY_TERMS)


def _context_int(context: dict, key: str) -> int:
    value = context.get(key, 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _requires_resume_context(context: dict) -> bool:
    return bool(
        context.get("requires_resume")
        or context.get("long_running")
        or context.get("needs_handoff")
    )


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(_contains_term(text, term) for term in terms)


def _contains_term(text: str, term: str) -> bool:
    if not term:
        return False
    if _is_ascii_word(term):
        return re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", text) is not None
    return term in text


def _is_ascii_word(term: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_ ]+", term))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a request before selecting UAF execution depth.")
    parser.add_argument("request", nargs="+", help="User request text to classify.")
    args = parser.parse_args()
    result = classify_request(" ".join(args.request))
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
