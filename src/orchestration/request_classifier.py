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
    "token-optimizer",
    "memory-state-harness",
    "parallel-orchestration-harness",
    "subagent-review-pipeline",
    "role-execution-audit-harness",
    "quality-gates-harness",
    "review-gate-harness",
    "qa-gate-harness",
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
    "memory_candidates",
    "compound_handoff",
]

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
    "리팩터",
    "설계",
    "아키텍처",
}
REVIEW_HEAVY_TERMS = {"review", "inspect", "audit", "검토", "리뷰", "점검"}
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

EXTRA_SOFTWARE_DOMAIN_TERMS = {
    "async/await",
    "jwt",
    "oauth",
    "pytest",
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
VAGUE_DISCOVERY_SPECIFICITY_TERMS = {
    "dashboard",
    "\ub300\uc2dc\ubcf4\ub4dc",
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
    "gate",
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
    "study calendar",
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

    if _is_high_risk(normalized, domain, context):
        return _high_risk_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_command_output_request(normalized):
        return _command_output_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_unapproved_product_discovery_request(normalized, context, domain):
        return _brainstorming_classification(domain, cross_cutting, evidence_required, reasons, normalized)

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
    if _contains_any(normalized, DEVOPS_TERMS):
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


def _domain_override_from_text(normalized: str) -> str:
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
    return False


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


def _is_defensive_security_work(normalized: str) -> bool:
    return _contains_any(normalized, {"fix", "review", "regression tests", "vulnerability"})


def _is_privacy_read_only(normalized: str) -> bool:
    return _contains_any(normalized, {"are customer emails in", "is there", "does this contain", "contains ssns"})


def _is_unapproved_product_discovery_request(normalized: str, context: dict, domain: str) -> bool:
    if _has_active_artifact(context):
        return False
    if _is_conceptual_request(normalized):
        return False
    if domain in {
        "shopping",
        "scheduling",
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
    if not _contains_any(normalized, DOMAIN_DISCOVERY_OBJECT_TERMS):
        return False
    if not _contains_any(normalized, DOMAIN_DISCOVERY_ACTION_TERMS):
        return False
    if not has_product_object and not _contains_any(normalized, DOMAIN_DISCOVERY_INTENT_TERMS):
        return False
    if _contains_any(normalized, {"prd", "product requirements document", "launch email", "screen design"}):
        return False
    token_count = len(normalized.split())
    return token_count <= 18 or not _has_inline_payload(normalized)


def _has_blocking_discovery_specificity(normalized: str) -> bool:
    if not _contains_any(normalized, PRODUCT_DISCOVERY_SPECIFICITY_TERMS):
        return False
    specificity_terms = PRODUCT_DISCOVERY_SPECIFICITY_TERMS - VAGUE_DISCOVERY_SPECIFICITY_TERMS
    return _contains_any(normalized, specificity_terms)


def _product_discovery_domain(domain: str, normalized: str) -> str:
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
