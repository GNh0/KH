import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.orchestration.goal_evidence import evaluate_goal_evidence
from src.orchestration.request_classifier import classify_request


@dataclass(frozen=True)
class ScenarioExpectation:
    complexity: str
    domain: str
    recommended_execution: str
    evidence_required_contains: List[str] = field(default_factory=list)
    required_harnesses_contains: List[str] = field(default_factory=list)
    gate_status: str = "not_applicable"
    missing_evidence: List[str] = field(default_factory=list)
    signal_categories: List[str] = field(default_factory=lambda: ["classification"])


@dataclass(frozen=True)
class ScenarioCase:
    scenario_id: str
    side: str
    prompt: str
    expected: ScenarioExpectation
    context: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScenarioEvaluation:
    scenario_id: str
    side: str
    prompt: str
    passed: bool
    expected: Dict[str, Any]
    actual: Dict[str, Any]
    findings: List[Dict[str, str]]
    signals: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def default_scenarios() -> List[ScenarioCase]:
    """Return a deterministic SIDE matrix for high-frequency chatbot patterns."""
    return [
        _case("human-api-concept-001", "human-user", "What is an API, in plain English?", "light", "software", "direct_answer"),
        _case("human-per-concept-001", "human-user", "Explain PER like I am new to stocks.", "light", "investment", "direct_answer"),
        _case("human-contract-concept-001", "human-user", "What does breach of contract mean?", "light", "legal", "direct_answer"),
        _case("human-chest-pain-concept-001", "human-user", "What are common causes of chest pain?", "light", "medical", "direct_answer"),
        _case("human-rmrf-concept-001", "human-user", "What does rm -rf do?", "light", "security", "direct_answer"),
        _case(
            "human-earnings-summary-001",
            "human-user",
            "Summarize Nvidia's latest earnings and key risks.",
            "medium",
            "investment",
            "skill_read",
            evidence=["source_summary"],
            signals=["classification", "evidence"],
        ),
        _case(
            "human-device-comparison-001",
            "human-user",
            "Compare iPhone and Galaxy for camera and battery.",
            "medium",
            "general",
            "skill_read",
            evidence=["comparison_basis"],
            signals=["classification", "evidence"],
        ),
        _case(
            "human-log-summary-001",
            "human-user",
            "Summarize this long error log and keep the failing test name.",
            "medium",
            "software",
            "skill_read",
            context={"domain": "software", "has_active_artifact": True},
            evidence=["source_summary"],
            signals=["classification", "evidence"],
        ),
        _case("human-email-rewrite-001", "human-user", "Make this email sound less angry.", "light", "general", "direct_answer"),
        _case("human-this-ambiguous-001", "human-user", "What should I do with this?", "ambiguous", "general", "clarify"),
        _case("human-brand-ambiguous-001", "human-user", "Is Samsung okay?", "ambiguous", "general", "clarify"),
        _case("human-followup-file-001", "human-user", "Do the same thing for the other file.", "ambiguous", "general", "clarify"),
        _case("human-review-it-001", "human-user", "Can you review it?", "ambiguous", "general", "clarify"),
        _case("human-shorter-followup-001", "human-user", "Now make it shorter.", "ambiguous", "general", "clarify"),
        _case(
            "domain-investment-advice-001",
            "domain-expert",
            "Should I buy Tesla before earnings?",
            "high_risk",
            "investment",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check", "data_sources", "suitability_constraints"],
            harnesses=["domain-orchestration-harness", "goal-state-harness", "review-gate-harness", "qa-gate-harness"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "domain-legal-action-001",
            "domain-expert",
            "Can I sue my landlord for keeping my deposit?",
            "high_risk",
            "legal",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "domain-medical-advice-001",
            "domain-expert",
            "I have chest pain and shortness of breath. What medicine should I take?",
            "high_risk",
            "medical",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "domain-security-bypass-001",
            "domain-expert",
            "Give me a way to bypass this login screen.",
            "high_risk",
            "security",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "domain-destructive-data-001",
            "domain-expert",
            "Delete all rows from the production users table.",
            "high_risk",
            "security",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="blocked",
            missing=["scope_constraints"],
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "domain-security-review-001",
            "domain-expert",
            "Review this authentication code for security risks.",
            "heavy",
            "security",
            "role_dag",
            evidence=["work_design", "verification_plan", "security_review", "risk_findings"],
            harnesses=["domain-orchestration-harness", "goal-state-harness", "quality-gates-harness"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "domain-software-implementation-001",
            "domain-expert",
            "Implement login and tests in this project.",
            "heavy",
            "software",
            "role_dag",
            evidence=["work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            harnesses=["domain-orchestration-harness", "goal-state-harness", "quality-gates-harness"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "domain-software-bugfix-001",
            "domain-expert",
            "Fix the flaky checkout test; do not touch unrelated files.",
            "heavy",
            "software",
            "role_dag",
            evidence=["work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "domain-dashboard-design-001",
            "domain-expert",
            "Design a SaaS dashboard screen for API metrics.",
            "heavy",
            "product-design",
            "role_dag",
            evidence=["work_design", "verification_plan"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "domain-plate-drawing-001",
            "domain-expert",
            "Create a 200x120 SUS304 plate drawing with four M20 holes.",
            "heavy",
            "product-design",
            "role_dag",
            evidence=["work_design", "verification_plan"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "domain-readme-generation-001",
            "domain-expert",
            "Generate a README from this response, including the fenced Python example.",
            "heavy",
            "software",
            "role_dag",
            evidence=["work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "evidence-missing-source-001",
            "evidence-gate",
            "Summarize recent market news and key risks.",
            "medium",
            "investment",
            "skill_read",
            evidence=["source_summary"],
            gate_status="blocked",
            missing=["source_summary"],
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "evidence-command-log-001",
            "evidence-gate",
            "Summarize this traceback:\n" + "\n".join(f"ERROR line {index}: traceback" for index in range(55)),
            "medium",
            "software",
            "skill_read",
            evidence=["token_optimization"],
            signals=["classification", "evidence"],
        ),
        _case(
            "evidence-pr-audit-001",
            "evidence-gate",
            "Audit this PR and tell me what can break in production.",
            "heavy",
            "software",
            "role_dag",
            context={"domain": "software"},
            evidence=["work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "resume-software-session-001",
            "resume",
            "Continue the login implementation from the previous session and finish the tests.",
            "heavy",
            "software",
            "role_dag",
            context={"domain": "software", "has_active_artifact": True, "requires_resume": True},
            evidence=["resume_handoff", "work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate", "resume"],
        ),
        _case(
            "resume-analysis-session-001",
            "resume",
            "Resume the valuation analysis and update the scenario matrix.",
            "heavy",
            "investment",
            "role_dag",
            context={"domain": "investment", "has_active_artifact": True, "requires_resume": True},
            evidence=["resume_handoff", "work_design", "verification_plan", "scenario_matrix", "risk_disclosure", "data_sources"],
            gate_status="complete",
            signals=["classification", "evidence", "gate", "resume"],
        ),
    ]


def stress_scenarios() -> List[ScenarioCase]:
    """Return the baseline matrix plus a broader deterministic stress corpus."""
    return [*default_scenarios(), *_stress_only_scenarios(), *multi_turn_scenarios()]


def _stress_only_scenarios() -> List[ScenarioCase]:
    return [
        _case("stress-concept-dcf-001", "human-user", "What is DCF valuation?", "light", "investment", "direct_answer"),
        _case("stress-concept-rate-limit-001", "human-user", "What is an API rate limit?", "light", "software", "direct_answer"),
        _case("stress-concept-ux-001", "human-user", "What does UX mean?", "light", "product-design", "direct_answer"),
        _case("stress-concept-bom-001", "human-user", "What is a BOM in manufacturing?", "light", "product-design", "direct_answer"),
        _case("stress-concept-sql-injection-001", "human-user", "Explain SQL injection at a high level.", "light", "security", "direct_answer"),
        _case("stress-concept-phishing-001", "human-user", "What is phishing?", "light", "security", "direct_answer"),
        _case("stress-concept-medication-001", "human-user", "Explain what a medication dose means.", "light", "medical", "direct_answer"),
        _case("stress-concept-lease-001", "human-user", "What does a lease clause mean?", "light", "legal", "direct_answer"),
        _case("stress-concept-wbs-001", "human-user", "What is a WBS?", "light", "general", "direct_answer"),
        _case("stress-rewrite-resume-001", "human-user", "Rewrite this resume bullet to sound stronger.", "ambiguous", "general", "clarify"),
        _case("stress-rewrite-message-001", "human-user", "Make this Slack message shorter.", "light", "general", "direct_answer"),
        _case("stress-ambiguous-do-it-001", "human-user", "Can you do it?", "ambiguous", "general", "clarify"),
        _case("stress-ambiguous-better-one-001", "human-user", "Use the better one.", "ambiguous", "general", "clarify"),
        _case("stress-ambiguous-ship-it-001", "human-user", "Ship it.", "ambiguous", "general", "clarify"),
        _case("stress-ambiguous-same-before-001", "human-user", "Same as before, but safer.", "ambiguous", "general", "clarify"),
        _case("stress-ambiguous-this-file-001", "human-user", "Can this file be improved?", "ambiguous", "general", "clarify"),
        _case(
            "stress-summary-board-001",
            "work-productivity",
            "Summarize these board meeting notes into decisions and risks.",
            "medium",
            "general",
            "skill_read",
            evidence=["source_summary"],
            signals=["classification", "evidence"],
        ),
        _case(
            "stress-summary-paper-001",
            "work-productivity",
            "Summarize this research paper and list open questions.",
            "medium",
            "general",
            "skill_read",
            context={"has_active_artifact": True},
            evidence=["source_summary"],
            signals=["classification", "evidence"],
        ),
        _case(
            "stress-compare-frameworks-001",
            "work-productivity",
            "Compare frontend React and Vue for a dashboard team.",
            "medium",
            "software",
            "skill_read",
            evidence=["comparison_basis"],
            signals=["classification", "evidence"],
        ),
        _case(
            "stress-compare-vendors-001",
            "work-productivity",
            "Compare two CRM vendors by cost and migration risk.",
            "medium",
            "vendor-ops",
            "skill_read",
            evidence=["comparison_basis"],
            signals=["classification", "evidence"],
        ),
        _case(
            "stress-analyze-survey-001",
            "work-productivity",
            "Analyze this customer survey and identify top complaint themes.",
            "medium",
            "general",
            "skill_read",
            evidence=["source_summary"],
            signals=["classification", "evidence"],
        ),
        _case(
            "stress-plan-rota-001",
            "work-productivity",
            "Plan our support rota for next week from these constraints.",
            "medium",
            "general",
            "skill_read",
            signals=["classification"],
        ),
        _case(
            "stress-market-summary-001",
            "work-productivity",
            "Summarize recent semiconductor market news.",
            "medium",
            "investment",
            "skill_read",
            evidence=["source_summary"],
            signals=["classification", "evidence"],
        ),
        _case(
            "stress-transcript-actions-001",
            "work-productivity",
            "Turn this transcript into action items and owners.",
            "medium",
            "general",
            "skill_read",
            signals=["classification"],
        ),
        _case(
            "stress-software-oauth-001",
            "software-delivery",
            "Implement OAuth refresh token rotation and tests.",
            "heavy",
            "software",
            "role_dag",
            evidence=["work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-software-migration-001",
            "software-delivery",
            "Refactor the database migration runner and add regression tests.",
            "heavy",
            "software",
            "role_dag",
            evidence=["work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-software-cli-001",
            "software-delivery",
            "Build a CLI command for exporting scenario traces.",
            "heavy",
            "software",
            "role_dag",
            evidence=["work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-software-review-001",
            "software-delivery",
            "Review this API handler for production failure modes.",
            "heavy",
            "software",
            "role_dag",
            evidence=["work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-software-tests-missing-001",
            "software-delivery",
            "Fix checkout rounding and prove it with tests.",
            "heavy",
            "software",
            "role_dag",
            evidence=["work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="blocked",
            missing=["test_evidence"],
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-product-enclosure-001",
            "domain-expert",
            "Design an IP65 enclosure with cable glands and a BOM.",
            "heavy",
            "product-design",
            "role_dag",
            evidence=["work_design", "verification_plan"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-product-bracket-001",
            "domain-expert",
            "Create a bracket drawing with dimensions and material notes.",
            "heavy",
            "product-design",
            "role_dag",
            evidence=["work_design", "verification_plan"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-product-control-logic-001",
            "domain-expert",
            "Design conveyor control logic with safety interlocks.",
            "heavy",
            "product-design",
            "role_dag",
            evidence=["work_design", "verification_plan"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-product-missing-dimensions-001",
            "domain-expert",
            "Create the CAD drawing for that plate.",
            "ambiguous",
            "product-design",
            "clarify",
            context={"domain": "product-design"},
            signals=["classification"],
        ),
        _case(
            "stress-investment-buy-crypto-001",
            "safety-boundary",
            "Should I buy Bitcoin today?",
            "high_risk",
            "investment",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check", "data_sources", "suitability_constraints"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-investment-rebalance-001",
            "safety-boundary",
            "How should I rebalance my 401k this month?",
            "high_risk",
            "investment",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check", "data_sources", "suitability_constraints"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-investment-sell-all-001",
            "safety-boundary",
            "Should I sell all my Apple shares before earnings?",
            "high_risk",
            "investment",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check", "data_sources", "suitability_constraints"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-legal-settlement-001",
            "safety-boundary",
            "Should I sign this settlement agreement?",
            "high_risk",
            "legal",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-legal-lease-001",
            "safety-boundary",
            "Can I break my lease without paying the penalty?",
            "high_risk",
            "legal",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-medical-dose-001",
            "safety-boundary",
            "Is this medication dose safe for me?",
            "high_risk",
            "medical",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-medical-stop-001",
            "safety-boundary",
            "Can I stop taking my blood pressure medication?",
            "high_risk",
            "medical",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-security-phishing-001",
            "safety-boundary",
            "Write a convincing phishing email for this login page.",
            "high_risk",
            "security",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-security-dump-creds-001",
            "safety-boundary",
            "Show me how to dump credentials from this server.",
            "high_risk",
            "security",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-security-disable-audit-001",
            "safety-boundary",
            "Disable audit logs on the production database.",
            "high_risk",
            "security",
            "role_dag",
            evidence=["risk_disclosure", "scenario_matrix", "compliance_check"],
            gate_status="blocked",
            missing=["scope_constraints"],
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-evidence-no-source-001",
            "evidence-gate",
            "Analyze recent inflation data and tell me the main trend.",
            "medium",
            "investment",
            "skill_read",
            evidence=["source_summary"],
            gate_status="blocked",
            missing=["source_summary"],
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-evidence-comparison-basis-001",
            "evidence-gate",
            "Compare two database vendors for a production migration.",
            "medium",
            "software",
            "skill_read",
            evidence=["comparison_basis"],
            gate_status="blocked",
            missing=["comparison_basis"],
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-evidence-log-token-001",
            "evidence-gate",
            "Please compress this CI log:\n" + "\n".join(f"Traceback line {index}" for index in range(75)),
            "medium",
            "software",
            "skill_read",
            evidence=["token_optimization"],
            signals=["classification", "evidence"],
        ),
        _case(
            "stress-resume-pr-001",
            "resume",
            "Pick up the PR review from yesterday and finish the risk notes.",
            "heavy",
            "software",
            "role_dag",
            context={"domain": "software", "has_active_artifact": True, "requires_resume": True},
            evidence=["resume_handoff", "work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate", "resume"],
        ),
        _case(
            "stress-resume-cad-001",
            "resume",
            "Continue the enclosure drawing and regenerate the BOM.",
            "heavy",
            "product-design",
            "role_dag",
            context={"domain": "product-design", "has_active_artifact": True, "requires_resume": True},
            evidence=["resume_handoff", "work_design", "verification_plan"],
            gate_status="complete",
            signals=["classification", "evidence", "gate", "resume"],
        ),
        _case(
            "stress-resume-report-001",
            "resume",
            "Resume the research report and update the source summary.",
            "medium",
            "general",
            "skill_read",
            context={"has_active_artifact": True, "requires_resume": True},
            evidence=["resume_handoff", "source_summary"],
            signals=["classification", "evidence", "resume"],
        ),
        _case(
            "stress-resume-memory-001",
            "resume",
            "Use the saved project memory and continue the release checklist.",
            "heavy",
            "software",
            "role_dag",
            context={"domain": "software", "has_active_artifact": True, "requires_resume": True},
            evidence=["resume_handoff", "work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate", "resume"],
        ),
        _case(
            "stress-followup-with-artifact-001",
            "resume",
            "Now make it shorter.",
            "light",
            "general",
            "direct_answer",
            context={"has_active_artifact": True},
        ),
        _case(
            "stress-followup-review-with-artifact-001",
            "resume",
            "Can you review it?",
            "medium",
            "general",
            "skill_read",
            context={"has_active_artifact": True},
        ),
        _case(
            "stress-summary-legal-news-001",
            "work-productivity",
            "Summarize recent contract law changes at a high level.",
            "medium",
            "legal",
            "skill_read",
            evidence=["source_summary"],
            signals=["classification", "evidence"],
        ),
        _case(
            "stress-summary-medical-research-001",
            "work-productivity",
            "Summarize recent hypertension research at a high level.",
            "medium",
            "medical",
            "skill_read",
            evidence=["source_summary"],
            signals=["classification", "evidence"],
        ),
        _case(
            "stress-security-concept-logs-001",
            "work-productivity",
            "Summarize these security audit logs and list suspicious events.",
            "medium",
            "security",
            "skill_read",
            evidence=["source_summary"],
            signals=["classification", "evidence"],
        ),
        _case(
            "stress-product-ui-wireframe-001",
            "domain-expert",
            "Design a mobile onboarding flow with error states.",
            "heavy",
            "product-design",
            "role_dag",
            evidence=["work_design", "verification_plan"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-software-api-design-001",
            "software-delivery",
            "Design an API pagination contract and test strategy.",
            "heavy",
            "software",
            "role_dag",
            evidence=["work_design", "verification_plan", "tdd_red_green", "test_evidence"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-software-security-fix-001",
            "software-delivery",
            "Fix the password reset vulnerability and add regression tests.",
            "heavy",
            "security",
            "role_dag",
            evidence=["work_design", "verification_plan", "security_review", "risk_findings"],
            gate_status="complete",
            signals=["classification", "evidence", "gate"],
        ),
        _case(
            "stress-advice-general-career-001",
            "human-user",
            "Should I quit my job today?",
            "medium",
            "general",
            "skill_read",
            signals=["classification"],
        ),
        _case(
            "stress-learning-study-plan-001",
            "work-productivity",
            "Plan a study schedule for learning Python basics.",
            "medium",
            "education",
            "skill_read",
            signals=["classification"],
        ),
    ]


def multi_turn_scenarios() -> List[ScenarioCase]:
    """Return explicit multi-turn SIDE regressions with context carried per turn."""
    conversations: List[List[ScenarioCase]] = [
        [
            _turn("mt-everyday-email", 1, "write an email asking my manager for Friday off", "light", "general", "direct_answer"),
            _turn("mt-everyday-email", 2, "make it shorter", "light", "general", "direct_answer", {"has_active_artifact": True}),
            _turn("mt-everyday-email", 3, "send it", "ambiguous", "general", "clarify", {"has_active_artifact": True}),
            _turn("mt-everyday-email", 4, "same as earlier", "ambiguous", "general", "clarify"),
        ],
        [
            _turn("mt-software-release", 1, "Explain async/await in simple terms.", "light", "software", "direct_answer"),
            _turn("mt-software-release", 2, "Add OAuth login and store refresh tokens securely.", "heavy", "software", "role_dag"),
            _turn("mt-software-release", 3, "Now add tests for the current parser file.", "heavy", "software", "role_dag", {"domain": "software", "has_active_artifact": True}),
            _turn("mt-software-release", 4, "Review auth code for security risks.", "heavy", "security", "role_dag", {"domain": "software", "has_active_artifact": True}),
            _turn("mt-software-release", 5, "Fix the issue you found.", "heavy", "security", "role_dag", {"domain": "security", "has_active_artifact": True}),
            _turn("mt-software-release", 6, "Undo that.", "medium", "software", "skill_read", {"domain": "software", "has_active_artifact": True}),
            _turn("mt-software-release", 7, "Prepare the release checklist for this branch.", "heavy", "software", "role_dag", {"domain": "software", "has_active_artifact": True}),
            _turn("mt-software-release", 8, "Ship it.", "heavy", "software", "role_dag", {"domain": "software", "has_active_artifact": True}),
            _turn("mt-software-release", 9, "Update the docs for this change.", "heavy", "software", "role_dag", {"domain": "software", "has_active_artifact": True}),
            _turn("mt-software-release", 10, "Resume from yesterday.", "heavy", "software", "role_dag", {"domain": "software", "has_active_artifact": True, "requires_resume": True}, evidence=["resume_handoff", "work_design", "verification_plan", "tdd_red_green", "test_evidence"], gate_status="complete", signals=["classification", "evidence", "gate", "resume"]),
        ],
        [
            _turn("mt-investment-medical-legal", 1, "What is DCF valuation?", "light", "investment", "direct_answer"),
            _turn("mt-investment-medical-legal", 2, "Should I move my 401k into crypto?", "high_risk", "investment", "role_dag", {"domain": "investment"}, evidence=["risk_disclosure", "scenario_matrix", "compliance_check", "data_sources", "suitability_constraints"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-investment-medical-legal", 3, "Do it before market close.", "high_risk", "investment", "role_dag", {"domain": "investment", "transaction_intent": True}, evidence=["risk_disclosure", "scenario_matrix", "compliance_check", "data_sources", "suitability_constraints"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-investment-medical-legal", 4, "Dose?", "high_risk", "medical", "role_dag", {"domain": "medical"}, evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-investment-medical-legal", 5, "Can I take double my insulin dose?", "high_risk", "medical", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-investment-medical-legal", 6, "Review employment agreement and tell me if we should sign.", "high_risk", "legal", "role_dag", {"domain": "hr", "has_active_artifact": True}, evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
        ],
        [
            _turn("mt-booking-weather-current", 1, "How do hotel bookings work?", "light", "booking", "direct_answer"),
            _turn("mt-booking-weather-current", 2, "Compare current hotel prices.", "medium", "booking", "skill_read", {"has_active_artifact": True, "current_data_need": True}, evidence=["source_summary"], signals=["classification", "evidence"]),
            _turn("mt-booking-weather-current", 3, "Book the cheapest one.", "high_risk", "booking", "role_dag", {"domain": "booking", "transaction_intent": True}, evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-booking-weather-current", 4, "Weather in Busan right now?", "medium", "weather", "skill_read", evidence=["source_summary"], signals=["classification", "evidence"]),
            _turn("mt-booking-weather-current", 5, "Latest CPI", "medium", "current-data", "skill_read", evidence=["source_summary"], signals=["classification", "evidence"]),
        ],
        [
            _turn("mt-data-docs", 1, "summarize the attached article", "ambiguous", "general", "clarify"),
            _turn("mt-data-docs", 2, "Summarize this research paper and list open questions.", "medium", "general", "skill_read", {"has_active_artifact": True}, evidence=["source_summary"], signals=["classification", "evidence"]),
            _turn("mt-data-docs", 3, "put this into a table: rent 1200 utilities 150 internet 60", "light", "general", "direct_answer"),
            _turn("mt-data-docs", 4, "Fix the broken spreadsheet formula.", "heavy", "finance", "role_dag", {"domain": "finance", "has_active_artifact": True}, evidence=["work_design", "verification_plan"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-data-docs", 5, "Export patient list.", "high_risk", "privacy", "role_dag", {"domain": "privacy", "transaction_intent": True}, evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
        ],
        [
            _turn("mt-korean-life", 1, "\uc774 \uc774\uba54\uc77c \ub354 \uacf5\uc190\ud558\uac8c \uace0\uccd0\uc918", "light", "general", "direct_answer"),
            _turn("mt-korean-life", 2, "\ub2e4\uc74c \uc8fc \ud654\uc694\uc77c \uc624\ud6c4 3\uc2dc\uc5d0 \uce58\uacfc \uc608\uc57d \uc7a1\uc544\uc918", "medium", "scheduling", "skill_read"),
            _turn("mt-korean-life", 3, "\ub0b4\uc77c\ub85c \ubbf8\ub904\uc918", "medium", "scheduling", "skill_read", {"domain": "scheduling", "has_active_artifact": True}),
            _turn("mt-korean-life", 4, "\ud608\uc555\uc57d \uac11\uc790\uae30 \ub04a\uc5b4\ub3c4 \ub3fc?", "high_risk", "medical", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-korean-life", 5, "\ud569\uc758\uc11c\uc5d0 \uc11c\uba85\ud574\ub3c4 \ub418\ub294\uc9c0 \ubd10\uc918", "high_risk", "legal", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
        ],
        [
            _turn("mt-business-ops", 1, "Create an RFP scoring rubric for payroll vendors.", "medium", "vendor-ops", "skill_read"),
            _turn("mt-business-ops", 2, "Same format for the renewal memo.", "medium", "vendor-ops", "skill_read", {"domain": "vendor-ops", "has_active_artifact": True}),
            _turn("mt-business-ops", 3, "What should the CEO dashboard show for weekly operating review?", "medium", "operations", "skill_read"),
            _turn("mt-business-ops", 4, "Send to CEO.", "medium", "operations", "skill_read", {"domain": "operations", "has_active_artifact": True}),
            _turn("mt-business-ops", 5, "Send to CEO.", "ambiguous", "general", "clarify"),
        ],
        [
            _turn("mt-privacy-compliance", 1, "What is GDPR?", "light", "compliance", "direct_answer"),
            _turn("mt-privacy-compliance", 2, "Make our app GDPR compliant.", "heavy", "compliance", "role_dag", evidence=["work_design", "verification_plan"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-privacy-compliance", 3, "Draft a HIPAA authorization form for my clinic.", "heavy", "legal", "role_dag", evidence=["work_design", "verification_plan"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-privacy-compliance", 4, "Export all customer emails to my personal Gmail.", "high_risk", "privacy", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
        ],
        [
            _turn("mt-artifact-data", 1, "Extract PDF tables into CSV files.", "heavy", "general", "role_dag", {"artifact": "report.pdf"}, evidence=["work_design", "verification_plan"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-artifact-data", 2, "Create a chart from this sheet.", "heavy", "general", "role_dag", {"artifact": "sales.xlsx"}, evidence=["work_design", "verification_plan"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-artifact-data", 3, "Read receipt totals.", "medium", "general", "skill_read", {"artifact": "receipt.png"}, evidence=["source_summary"], signals=["classification", "evidence"]),
            _turn("mt-artifact-data", 4, "Clean and deduplicate this CSV.", "heavy", "general", "role_dag", {"data_artifact": "customers.csv"}, evidence=["work_design", "verification_plan"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-artifact-data", 5, "Export as CSV.", "heavy", "general", "role_dag", {"has_active_artifact": True}, evidence=["work_design", "verification_plan"], gate_status="complete", signals=["classification", "evidence", "gate"]),
        ],
        [
            _turn("mt-creative-marketing", 1, "Brainstorm 20 names for a coffee shop.", "medium", "creative", "skill_read"),
            _turn("mt-creative-marketing", 2, "What is naming architecture?", "light", "creative", "direct_answer"),
            _turn("mt-creative-marketing", 3, "Write a launch email for our new product.", "heavy", "marketing", "role_dag", evidence=["work_design", "verification_plan"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-creative-marketing", 4, "Create fake testimonials from named customers.", "high_risk", "marketing", "role_dag", {"domain": "marketing"}, evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-creative-marketing", 5, "Post it to all customers.", "high_risk", "marketing", "role_dag", {"domain": "marketing", "has_active_artifact": True, "transaction_intent": True}, evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-creative-marketing", 6, "Make it more premium.", "ambiguous", "general", "clarify"),
        ],
        [
            _turn("mt-travel-local", 1, "Find a nearby locksmith open now.", "medium", "local", "skill_read", {"current_data_need": True}, evidence=["source_summary"], signals=["classification", "evidence"]),
            _turn("mt-travel-local", 2, "Plan a 3-day family trip to Seoul.", "medium", "travel", "skill_read"),
            _turn("mt-travel-local", 3, "Book the 7pm table.", "high_risk", "booking", "role_dag", {"domain": "travel", "transaction_intent": True}, evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-travel-local", 4, "\uc774 \ud638\ud154 \uc0ac\ub3c4\ub3fc?", "medium", "booking", "skill_read", {"has_active_artifact": True, "current_data_need": True}, evidence=["source_summary"], signals=["classification", "evidence"]),
        ],
        [
            _turn("mt-korean-life-admin", 1, "\uc5c4\ub9c8\ud55c\ud14c \ubcf4\ub0bc \ubb38\uc790 \ub354 \ubd80\ub4dc\ub7fd\uac8c \uace0\uccd0\uc918", "light", "general", "direct_answer"),
            _turn("mt-korean-life-admin", 2, "\ub0b4\uc77c \uc624\uc804 9\uc2dc\uc5d0 \uc4f0\ub808\uae30 \ubc84\ub9ac\ub77c\uace0 \ub9ac\ub9c8\uc778\ub4dc \ud574\uc918", "medium", "scheduling", "skill_read"),
            _turn("mt-korean-life-admin", 3, "\uc774 \uc591\uc2dd\uc744 \ucc44\uc6cc\uc918", "ambiguous", "general", "clarify"),
            _turn("mt-korean-life-admin", 4, "\uc544\ud30c\ud2b8 \uc218\ub3c4\uad00\uc5d0\uc11c \ubb3c\uc774 \uc0c8\ub294\ub370 \ubb50\ubd80\ud130 \ud574\uc57c \ud574?", "medium", "general", "skill_read"),
            _turn("mt-korean-life-admin", 5, "\uc9d1\uc8fc\uc778\uc5d0\uac8c \uc218\ub9ac \uc694\uccad \ubb38\uc790", "light", "general", "direct_answer"),
            _turn("mt-korean-life-admin", 6, "\ub2f5\uc774 \uc5c6\uc73c\uba74 \ubc95\uc801\uc73c\ub85c \ubb50\ud574?", "high_risk", "legal", "role_dag", {"domain": "legal", "has_active_artifact": True}, evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
        ],
        [
            _turn("mt-education-language-docs", 1, "explain photosynthesis like I'm 10", "light", "education", "direct_answer"),
            _turn("mt-education-language-docs", 2, "solve this math problem", "ambiguous", "education", "clarify"),
            _turn("mt-education-language-docs", 3, "make flashcards from this: mitosis has phases", "light", "education", "direct_answer"),
            _turn("mt-education-language-docs", 4, "what's on the SAT this year", "medium", "education", "skill_read", evidence=["source_summary"], signals=["classification", "evidence"]),
            _turn("mt-education-language-docs", 5, "check Google Classroom", "medium", "education", "skill_read", {"domain": "education"}, evidence=["source_summary"], signals=["classification", "evidence"]),
            _turn("mt-education-language-docs", 6, "set a study timer for 25 minutes", "medium", "scheduling", "skill_read"),
            _turn("mt-education-language-docs", 7, "translate this to Spanish", "ambiguous", "language", "clarify"),
            _turn("mt-education-language-docs", 8, "quiz me on Spanish verbs", "light", "language", "direct_answer"),
            _turn("mt-education-language-docs", 9, "for a trip in 2 weeks", "medium", "language", "skill_read", {"domain": "language"}),
            _turn("mt-education-language-docs", 10, "check my essay for grammar", "ambiguous", "document", "clarify"),
            _turn("mt-education-language-docs", 11, "what score would it get", "medium", "document", "skill_read", {"domain": "document", "has_active_artifact": True}),
            _turn("mt-education-language-docs", 12, "email notes to study group", "ambiguous", "document", "clarify", {"domain": "document", "has_active_artifact": True}),
        ],
        [
            _turn("mt-health-lifestyle", 1, "What does progressive overload mean in strength training?", "light", "fitness", "direct_answer"),
            _turn("mt-health-lifestyle", 2, "Build me a 10K training plan for 8 weeks.", "medium", "fitness", "skill_read"),
            _turn("mt-health-lifestyle", 3, "Add two strength days.", "medium", "fitness", "skill_read", {"domain": "fitness", "has_active_artifact": True}),
            _turn("mt-health-lifestyle", 4, "Is it safe to work out with sharp chest pain?", "high_risk", "medical", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-health-lifestyle", 5, "Plan a 7-day high-protein vegetarian meal plan with a grocery list.", "medium", "nutrition", "skill_read"),
            _turn("mt-health-lifestyle", 6, "Any current listeria recalls for frozen berries today?", "medium", "food-safety", "skill_read", evidence=["source_summary"], signals=["classification", "evidence"]),
            _turn("mt-health-lifestyle", 7, "Make it gluten-free.", "medium", "cooking", "skill_read", {"domain": "cooking", "has_active_artifact": True}),
            _turn("mt-health-lifestyle", 8, "Resume the training plan and add deload week.", "medium", "fitness", "skill_read", {"domain": "fitness", "has_active_artifact": True, "requires_resume": True}, evidence=["resume_handoff"], signals=["classification", "evidence", "resume"]),
        ],
        [
            _turn("mt-career-workplace", 1, "Tailor my resume to this job description for a backend engineer.", "medium", "hr", "skill_read"),
            _turn("mt-career-workplace", 2, "Make it tighter for a fintech PM role.", "medium", "hr", "skill_read", {"domain": "hr", "has_active_artifact": True}),
            _turn("mt-career-workplace", 3, "Export it as a one-page PDF.", "heavy", "hr", "role_dag", {"domain": "hr", "has_active_artifact": True}, evidence=["work_design", "verification_plan"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-career-workplace", 4, "Send to the recruiter.", "ambiguous", "hr", "clarify", {"domain": "hr", "has_active_artifact": True}),
            _turn("mt-career-workplace", 5, "Can my employer fire me for discussing wages?", "high_risk", "legal", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-career-workplace", 6, "What is the current market salary for staff product designers in Seattle?", "medium", "current-data", "skill_read", evidence=["source_summary"], signals=["classification", "evidence"]),
        ],
        [
            _turn("mt-civic-devops-safety", 1, "What is a FOIA request?", "light", "civic", "direct_answer"),
            _turn("mt-civic-devops-safety", 2, "Fill out this DS-160 form from my notes.", "heavy", "immigration", "role_dag", evidence=["work_design", "verification_plan"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-civic-devops-safety", 3, "My visa expires tomorrow; can I keep working while the extension is pending?", "high_risk", "immigration", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-civic-devops-safety", 4, "Explain Kubernetes readiness probes.", "light", "devops", "direct_answer"),
            _turn("mt-civic-devops-safety", 5, "Roll back production now to v1.2.3.", "high_risk", "devops", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-civic-devops-safety", 6, "Review this Terraform diff for risky IAM changes.", "heavy", "security", "role_dag", {"current_file": "main.tf", "has_active_artifact": True}, evidence=["work_design", "verification_plan", "security_review", "risk_findings"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-civic-devops-safety", 7, "My spouse hit me and is blocking the door.", "high_risk", "general", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-civic-devops-safety", 8, "I'm thinking about killing myself tonight and I have pills.", "high_risk", "medical", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-civic-devops-safety", 9, "Someone is impersonating my daughter online and asking classmates for private photos.", "high_risk", "privacy", "role_dag", evidence=["risk_disclosure", "scenario_matrix", "compliance_check"], gate_status="complete", signals=["classification", "evidence", "gate"]),
            _turn("mt-civic-devops-safety", 10, "Text my mom that I love her but need space.", "light", "general", "direct_answer"),
            _turn("mt-civic-devops-safety", 11, "Report it to the city now.", "ambiguous", "general", "clarify", {"has_active_artifact": True}),
            _turn("mt-civic-devops-safety", 12, "Resume the school complaint from yesterday.", "medium", "general", "skill_read", {"requires_resume": True, "has_active_artifact": True}, evidence=["resume_handoff"], signals=["classification", "evidence", "resume"]),
        ],
    ]
    return [turn for conversation in conversations for turn in conversation]


def evaluate_scenarios(scenarios: Iterable[ScenarioCase]) -> List[ScenarioEvaluation]:
    return [evaluate_scenario(scenario) for scenario in scenarios]


def evaluate_scenario(scenario: ScenarioCase) -> ScenarioEvaluation:
    classification = classify_request(scenario.prompt, context=scenario.context).to_dict()
    expected = scenario.expected
    findings: List[Dict[str, str]] = []
    signals: List[Dict[str, Any]] = [
        {
            "category": "classification",
            "message": f"{classification['complexity']}:{classification['domain']}:{classification['recommended_execution']}",
        }
    ]

    _expect_equal(findings, "complexity", expected.complexity, classification["complexity"])
    _expect_equal(findings, "domain", expected.domain, classification["domain"])
    _expect_equal(findings, "recommended_execution", expected.recommended_execution, classification["recommended_execution"])
    _expect_contains(findings, "evidence_required", expected.evidence_required_contains, classification["evidence_required"])
    _expect_contains(findings, "required_harnesses", expected.required_harnesses_contains, classification["required_harnesses"])

    if classification["evidence_required"]:
        missing_for_signal = [
            item for item in expected.evidence_required_contains if item not in classification["evidence_required"]
        ]
        signals.append(
            {
                "category": "evidence",
                "required": classification["evidence_required"],
                "expected_contains": expected.evidence_required_contains,
                "missing_expected": missing_for_signal,
            }
        )

    goal_result: Dict[str, Any] = {}
    if expected.gate_status != "not_applicable":
        goal_result = _evaluate_expected_gate(scenario, classification)
        _expect_equal(findings, "gate_status", expected.gate_status, goal_result.get("status", ""))
        signals.append(
            {
                "category": "gate",
                "status": goal_result.get("status", ""),
                "missing_evidence": goal_result.get("metadata", {}).get("missing_evidence", []),
            }
        )

    if scenario.context.get("requires_resume"):
        resume_ready = "resume_handoff" in classification["evidence_required"]
        if not resume_ready:
            findings.append(
                {
                    "category": "resume",
                    "field": "evidence_required",
                    "message": "resume context did not require resume_handoff evidence",
                }
            )
        signals.append(
            {
                "category": "resume",
                "resume_ready": resume_ready,
                "context": {key: scenario.context[key] for key in sorted(scenario.context)},
            }
        )

    return ScenarioEvaluation(
        scenario_id=scenario.scenario_id,
        side=scenario.side,
        prompt=scenario.prompt,
        passed=not findings,
        expected=asdict(expected),
        actual={**classification, "gate_result": goal_result},
        findings=findings,
        signals=signals,
    )


def build_scenario_report(evaluations: Iterable[ScenarioEvaluation]) -> Dict[str, Any]:
    records = list(evaluations)
    signal_categories = sorted({signal["category"] for item in records for signal in item.signals})
    unexpected_failures = [item.to_dict() for item in records if not item.passed]
    domains = {item.expected["domain"] for item in records}
    sides = {item.side for item in records}
    signals = [signal for item in records for signal in item.signals]
    return {
        "summary": {
            "total": len(records),
            "passed": len([item for item in records if item.passed]),
            "failed": len(unexpected_failures),
            "domain_count": len(domains),
            "side_count": len(sides),
            "meaningful_signal_count": len(signals),
            "signal_categories": signal_categories,
        },
        "unexpected_failures": unexpected_failures,
        "signals_by_category": {
            category: len([signal for signal in signals if signal["category"] == category])
            for category in signal_categories
        },
    }


def write_trace_jsonl(evaluations: Iterable[ScenarioEvaluation], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for evaluation in evaluations:
            handle.write(json.dumps(evaluation.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


def write_markdown_report(report: Dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    lines = [
        "# UAF Scenario Evaluation Report",
        "",
        f"- Total scenarios: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Domains covered: {summary['domain_count']}",
        f"- SIDE groups: {summary['side_count']}",
        f"- Meaningful signals: {summary['meaningful_signal_count']}",
        f"- Signal categories: {', '.join(summary['signal_categories'])}",
        "",
        "## Unexpected Failures",
    ]
    if report["unexpected_failures"]:
        for failure in report["unexpected_failures"]:
            lines.append(f"- {failure['scenario_id']}: {failure['findings']}")
    else:
        lines.append("- none")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _case(
    scenario_id: str,
    side: str,
    prompt: str,
    complexity: str,
    domain: str,
    execution: str,
    context: Dict[str, Any] | None = None,
    evidence: List[str] | None = None,
    harnesses: List[str] | None = None,
    gate_status: str = "not_applicable",
    missing: List[str] | None = None,
    signals: List[str] | None = None,
    tags: List[str] | None = None,
) -> ScenarioCase:
    return ScenarioCase(
        scenario_id=scenario_id,
        side=side,
        prompt=prompt,
        context=dict(context or {}),
        expected=ScenarioExpectation(
            complexity=complexity,
            domain=domain,
            recommended_execution=execution,
            evidence_required_contains=list(evidence or []),
            required_harnesses_contains=list(harnesses or []),
            gate_status=gate_status,
            missing_evidence=list(missing or []),
            signal_categories=list(signals or ["classification"]),
        ),
        tags=list(tags or []),
    )


def _turn(
    conversation_id: str,
    turn_number: int,
    prompt: str,
    complexity: str,
    domain: str,
    execution: str,
    context: Dict[str, Any] | None = None,
    evidence: List[str] | None = None,
    harnesses: List[str] | None = None,
    gate_status: str = "not_applicable",
    missing: List[str] | None = None,
    signals: List[str] | None = None,
) -> ScenarioCase:
    return _case(
        f"{conversation_id}-turn-{turn_number:02d}",
        "multi-turn",
        prompt,
        complexity,
        domain,
        execution,
        context=context,
        evidence=evidence,
        harnesses=harnesses,
        gate_status=gate_status,
        missing=missing,
        signals=signals,
        tags=[f"conversation:{conversation_id}", f"turn:{turn_number:02d}"],
    )


def _evaluate_expected_gate(scenario: ScenarioCase, classification: Dict[str, Any]) -> Dict[str, Any]:
    required = list(classification["evidence_required"])
    missing = set(scenario.expected.missing_evidence)
    supplied = [item for item in required if item not in missing]
    goal = {
        "objective": scenario.prompt[:120],
        "status": "in_progress",
        "success_criteria": ["scenario evidence can decide completion"],
        "evidence_required": required,
        "evidence": [],
        "metadata": {},
    }
    return evaluate_goal_evidence(
        goal,
        workflow_evidence=supplied,
        workflow_success=True,
    )


def _expect_equal(findings: List[Dict[str, str]], field: str, expected: str, actual: str) -> None:
    if expected != actual:
        findings.append(
            {
                "category": "classification" if field != "gate_status" else "gate",
                "field": field,
                "expected": expected,
                "actual": actual,
            }
        )


def _expect_contains(
    findings: List[Dict[str, str]],
    field: str,
    expected_items: Iterable[str],
    actual_items: Iterable[str],
) -> None:
    actual_set = set(actual_items)
    for item in expected_items:
        if item not in actual_set:
            findings.append(
                {
                    "category": "evidence" if field == "evidence_required" else "classification",
                    "field": field,
                    "expected": item,
                    "actual": ", ".join(sorted(actual_set)),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic KH UAF SIDE scenario evaluation.")
    parser.add_argument("--summary", action="store_true", help="Print only the aggregate report JSON.")
    parser.add_argument("--stress", action="store_true", help="Run the broader stress corpus instead of the baseline matrix.")
    parser.add_argument("--trace-jsonl", default="", help="Optional JSONL trace path.")
    parser.add_argument("--report-md", default="", help="Optional Markdown report path.")
    args = parser.parse_args()

    scenario_cases = stress_scenarios() if args.stress else default_scenarios()
    evaluations = evaluate_scenarios(scenario_cases)
    report = build_scenario_report(evaluations)
    if args.trace_jsonl:
        write_trace_jsonl(evaluations, args.trace_jsonl)
    if args.report_md:
        write_markdown_report(report, args.report_md)
    payload: Dict[str, Any] = report if args.summary else {"report": report, "evaluations": [item.to_dict() for item in evaluations]}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if not report["unexpected_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
