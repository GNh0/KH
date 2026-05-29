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
            "general",
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
    parser.add_argument("--trace-jsonl", default="", help="Optional JSONL trace path.")
    parser.add_argument("--report-md", default="", help="Optional Markdown report path.")
    args = parser.parse_args()

    evaluations = evaluate_scenarios(default_scenarios())
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
