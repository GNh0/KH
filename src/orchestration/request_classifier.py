import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List


COMPLEXITIES = {"light", "medium", "heavy", "high_risk", "ambiguous"}

INVESTMENT_TERMS = {
    "stock",
    "portfolio",
    "valuation",
    "per",
    "dcf",
    "earnings",
    "market",
    "market news",
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

LEGAL_TERMS = {"legal", "lawsuit", "contract", "contract dispute", "sue", "고소", "소송", "법률", "계약", "계약 분쟁"}
LEGAL_ADVICE_TERMS = {
    "sue",
    "landlord",
    "legal action",
    "should i sign",
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
    "medicine",
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
SECURITY_TERMS = {"security", "exploit", "bypass", "credential", "rm -rf", "drop table", "해킹", "우회", "삭제"}
SECURITY_HIGH_RISK_TERMS = {
    "exploit",
    "bypass",
    "credential",
    "password",
    "malware",
    "exfiltrate",
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
    "external drive",
    "실행",
    "지워",
    "삭제해",
    "제거해",
    "drop table",
    "rm -rf /",
    "format",
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
    "implementation",
    "python",
    "readme",
    "pr",
    "unit test",
    "test",
    "tests",
}

SOFTWARE_HEAVY_TERMS = {
    "implement",
    "implementation",
    "build",
    "continue",
    "fix",
    "finish",
    "generate",
    "modify",
    "refactor",
    "architecture",
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
    "구현",
    "만들어",
    "고쳐",
    "수정",
    "리팩터",
    "설계",
    "아키텍처",
}
REVIEW_HEAVY_TERMS = {"review", "inspect", "audit", "검토", "리뷰", "점검"}
MEDIUM_TERMS = {"summarize", "compare", "analyze", "recent", "meeting notes", "action items", "요약", "비교", "분석", "최근", "검토"}
LIGHT_TERMS = {
    "what is",
    "define",
    "explain",
    "concept",
    "in simple terms",
    "at a high level",
    "tell me about",
    "뜻",
    "개념",
    "뭐야",
    "설명",
    "예시",
}
AMBIGUOUS_TERMS = {
    "what should i do with this",
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
CONTEXT_FREE_AMBIGUOUS_TERMS = {
    "what should i do with this",
    "do the same thing",
    "for the other file",
    "can you review it",
    "review it",
    "now make it shorter",
    "make it shorter",
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
    if _requires_resume_context(context):
        evidence_required.append("resume_handoff")
        reasons.append("resume_context_required")

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

    if _is_high_risk(normalized, domain):
        return _high_risk_classification(domain, cross_cutting, evidence_required, reasons)

    if _is_heavy_work(normalized, domain):
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
            recommended_skills=[
                "request-complexity-router",
                "domain-orchestration-harness",
                "goal-state-harness",
                "quality-gates-harness",
            ],
            required_harnesses=[
                "domain-orchestration-harness",
                "goal-state-harness",
                "quality-gates-harness",
                "review-gate-harness",
                "qa-gate-harness",
            ],
            evidence_required=[
                *evidence_required,
                "objective",
                "work_design",
                "target_scope",
                "verification_plan",
                *domain_specific_evidence,
            ],
            reasons=[*reasons, "implementation_or_design_work"],
            confidence=0.84,
        )

    if _contains_any(normalized, MEDIUM_TERMS):
        medium_evidence = [*evidence_required]
        if _contains_any(normalized, {"summarize", "analyze", "recent", "최근", "earnings", "실적"}):
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


def _detect_domain(normalized: str, context: dict) -> str:
    explicit_domain = str(context.get("domain", "")).strip()
    if explicit_domain:
        return explicit_domain
    if _contains_any(normalized, DESTRUCTIVE_ACTION_TERMS):
        return "security"
    if _contains_any(normalized, SECURITY_HIGH_RISK_TERMS):
        return "security"
    if _contains_any(normalized, SECURITY_TERMS) and _contains_any(normalized, REVIEW_HEAVY_TERMS | {"risk", "risks"}):
        return "security"
    if _contains_any(normalized, DESIGN_HEAVY_TERMS):
        return "product-design"
    if _contains_any(normalized, SOFTWARE_DOMAIN_TERMS):
        return "software"
    if _contains_any(normalized, MEDICAL_TERMS):
        return "medical"
    if _contains_any(normalized, INVESTMENT_TERMS):
        return "investment"
    if _contains_any(normalized, LEGAL_TERMS):
        return "legal"
    if _contains_any(normalized, SECURITY_TERMS):
        return "security"
    if _contains_any(normalized, SOFTWARE_HEAVY_TERMS):
        return "software"
    return "general"


def _is_high_risk(normalized: str, domain: str) -> bool:
    if domain == "investment" and _contains_any(normalized, INVESTMENT_ADVICE_TERMS):
        return True
    if domain == "legal" and _contains_any(normalized, LEGAL_ADVICE_TERMS) and not _is_conceptual_request(normalized):
        return True
    if domain == "medical" and _contains_any(normalized, MEDICAL_ADVICE_TERMS) and not _is_conceptual_request(normalized):
        return True
    if domain == "security" and (
        _contains_any(normalized, SECURITY_HIGH_RISK_TERMS)
        or _contains_any(normalized, DESTRUCTIVE_ACTION_TERMS)
    ):
        return True
    return False


def _is_conceptual_request(normalized: str) -> bool:
    return _contains_any(normalized, LIGHT_TERMS)


def _is_heavy_work(normalized: str, domain: str) -> bool:
    if _is_conceptual_request(normalized) and not _contains_any(normalized, HEAVY_ACTION_TERMS | REVIEW_HEAVY_TERMS):
        return False
    if _contains_any(normalized, DESIGN_HEAVY_TERMS):
        return True
    if _contains_any(normalized, SOFTWARE_HEAVY_TERMS):
        return True
    if _contains_any(normalized, HEAVY_ACTION_TERMS) and _contains_any(normalized, SOFTWARE_DOMAIN_TERMS):
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


def _is_ambiguous(normalized: str, context: dict) -> bool:
    if context.get("has_active_artifact") or context.get("domain"):
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


def _needs_token_optimization(original: str, normalized: str) -> bool:
    return (
        len(original) > 2000
        or original.count("\n") > 50
        or _contains_any(normalized, {"긴 로그", "stack trace", "traceback", "토큰", "압축", "핵심만"})
    )


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
