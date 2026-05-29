from typing import Any, Dict, List, Optional

from src.orchestration.evidence_producers import (
    collect_metadata_evidence,
    qa_result_evidence,
    review_result_evidence,
)


SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
VALID_QA_STATUSES = {"passed", "failed", "blocked", "skipped"}


def _evidence_record(record) -> Dict[str, Any]:
    return record.to_dict()


def _goal_blocked_by_evidence(goal: Optional[Dict[str, Any]]) -> bool:
    if not goal:
        return False
    return goal.get("status") == "blocked" and bool(
        goal.get("metadata", {}).get("missing_evidence", [])
    )


def _missing_goal_evidence(goal: Optional[Dict[str, Any]]) -> List[str]:
    if not goal:
        return []
    return list(goal.get("metadata", {}).get("missing_evidence", []))


def _failed_tasks(task_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        result
        for result in task_results
        if result.get("status") != "success"
    ]


def _task_label(task: Dict[str, Any]) -> str:
    return task.get("file_name", task.get("task_id", "unknown task"))


def _missing_task_evidence(task_results: List[Dict[str, Any]]) -> List[str]:
    findings: List[str] = []
    for task in task_results:
        if task.get("status") != "success":
            continue
        if task.get("role", "implementer") != "implementer":
            continue
        evidence = collect_metadata_evidence(task.get("metadata", {}) or {})
        if not evidence:
            findings.append(f"{_task_label(task)} missing implementation evidence")
    return findings


def _quality_findings(task_results: List[Dict[str, Any]]) -> List[str]:
    findings: List[str] = []
    for task in task_results:
        metadata = task.get("metadata", {}) or {}
        task_findings = list(metadata.get("quality_findings", []) or [])
        task_findings.extend(metadata.get("code_quality_findings", []) or [])
        for finding in task_findings:
            if isinstance(finding, dict):
                message = finding.get("message", "review finding")
            else:
                message = str(finding)
            findings.append(f"{_task_label(task)}: {message}")
    return findings


def _structured_quality_findings(task_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for task in task_results:
        metadata = task.get("metadata", {}) or {}
        raw_findings = list(metadata.get("quality_findings", []) or [])
        raw_findings.extend(metadata.get("code_quality_findings", []) or [])
        default_file = task.get("file_name", "")
        findings.extend(normalize_review_findings(raw_findings, default_file=default_file))
    return findings


def build_review_finding(
    severity: str,
    message: str,
    file_path: str = "",
    line: Optional[int] = None,
    suggested_fix: str = "",
    needs_approval: bool = False,
    category: str = "quality",
) -> Dict[str, Any]:
    normalized_severity = severity if severity in SEVERITY_ORDER else "medium"
    return {
        "severity": normalized_severity,
        "category": category,
        "message": message,
        "file_path": file_path,
        "line": line,
        "suggested_fix": suggested_fix,
        "needs_approval": bool(needs_approval),
        "next_action": "ask" if needs_approval else "fix",
    }


def normalize_review_findings(
    findings: List[Any],
    default_file: str = "",
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for finding in findings:
        if isinstance(finding, dict):
            normalized.append(
                build_review_finding(
                    severity=str(finding.get("severity", "medium")),
                    message=str(finding.get("message", "review finding")),
                    file_path=str(finding.get("file_path") or default_file),
                    line=finding.get("line"),
                    suggested_fix=str(finding.get("suggested_fix", "")),
                    needs_approval=bool(finding.get("needs_approval", False)),
                    category=str(finding.get("category", "quality")),
                )
            )
        else:
            normalized.append(
                build_review_finding(
                    severity="medium",
                    message=str(finding),
                    file_path=default_file,
                )
            )
    return sorted(
        normalized,
        key=lambda item: SEVERITY_ORDER.get(item.get("severity", "medium"), 2),
        reverse=True,
    )


def build_qa_check(
    requirement_id: str,
    check_type: str,
    description: str,
    status: str,
    evidence: Optional[List[str]] = None,
    notes: str = "",
    scope: str = "",
) -> Dict[str, Any]:
    normalized_status = status if status in VALID_QA_STATUSES else "blocked"
    return {
        "requirement_id": requirement_id,
        "check_type": check_type,
        "description": description,
        "status": normalized_status,
        "evidence": list(evidence or []),
        "notes": notes,
        "scope": scope,
    }


def evaluate_spec_review_gate(task_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    failed_tasks = _failed_tasks(task_results)
    if failed_tasks:
        findings = [
            f"{_task_label(task)} failed"
            for task in failed_tasks
        ]
        blocked_reason = f"{len(failed_tasks)} implementer task(s) failed"
        return {
            "role": "spec-reviewer",
            "status": "failed",
            "message": blocked_reason,
            "blocks_on": ["implementer"],
            "findings": findings,
            "evidence_records": [
                _evidence_record(
                    review_result_evidence(
                        role="spec-reviewer",
                        passed=False,
                        evidence_key="spec review passed",
                        findings=findings,
                    )
                )
            ],
        }

    missing_evidence = _missing_task_evidence(task_results)
    if missing_evidence:
        return {
            "role": "spec-reviewer",
            "status": "failed",
            "message": f"missing implementation evidence for {len(missing_evidence)} task(s)",
            "blocks_on": ["implementer"],
            "findings": missing_evidence,
            "evidence_records": [
                _evidence_record(
                    review_result_evidence(
                        role="spec-reviewer",
                        passed=False,
                        evidence_key="spec review passed",
                        findings=missing_evidence,
                    )
                )
            ],
        }

    return {
        "role": "spec-reviewer",
        "status": "passed",
        "message": "all implementer tasks reported success with evidence",
        "blocks_on": ["implementer"],
        "findings": [],
        "evidence_records": [
            _evidence_record(
                review_result_evidence(
                    role="spec-reviewer",
                    passed=True,
                    evidence_key="spec review passed",
                )
            )
        ],
    }


def evaluate_code_quality_gate(
    spec_gate: Dict[str, Any],
    task_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if spec_gate.get("status") != "passed":
        return {
            "role": "code-quality-reviewer",
            "status": "blocked",
            "message": "spec review did not pass",
            "blocks_on": ["spec-reviewer"],
            "findings": [],
            "evidence_records": [
                _evidence_record(
                    review_result_evidence(
                        role="code-quality-reviewer",
                        passed=False,
                        evidence_key="code quality review passed",
                    )
                )
            ],
        }

    findings = _quality_findings(task_results or [])
    structured_findings = _structured_quality_findings(task_results or [])
    if findings:
        return {
            "role": "code-quality-reviewer",
            "status": "failed",
            "message": f"{len(findings)} quality finding(s) reported",
            "blocks_on": ["spec-reviewer"],
            "findings": findings,
            "structured_findings": structured_findings,
            "evidence_records": [
                _evidence_record(
                    review_result_evidence(
                        role="code-quality-reviewer",
                        passed=False,
                        evidence_key="code quality review passed",
                        findings=findings,
                    )
                )
            ],
        }

    return {
        "role": "code-quality-reviewer",
        "status": "passed",
        "message": "no failed task output or quality findings to block review",
        "blocks_on": ["spec-reviewer"],
        "findings": [],
        "structured_findings": [],
        "evidence_records": [
            _evidence_record(
                review_result_evidence(
                    role="code-quality-reviewer",
                    passed=True,
                    evidence_key="code quality review passed",
                )
            )
        ],
    }


def evaluate_qa_checks(
    quality_gate: Dict[str, Any],
    checks: List[Dict[str, Any]],
    goal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if quality_gate.get("status") != "passed":
        return {
            "role": "qa-verifier",
            "status": "blocked",
            "message": "quality review did not pass",
            "blocks_on": ["code-quality-reviewer"],
            "checks": list(checks),
            "findings": [],
            "evidence_records": [
                _evidence_record(
                    qa_result_evidence(
                        passed=False,
                        evidence_key="qa gate passed",
                        checks=["quality review"],
                    )
                )
            ],
        }

    if _goal_blocked_by_evidence(goal):
        missing_evidence = _missing_goal_evidence(goal)
        blocked_reason = goal.get("blocked_reason", "missing required goal evidence")
        return {
            "role": "qa-verifier",
            "status": "blocked",
            "message": f"missing goal evidence: {', '.join(missing_evidence)}",
            "blocks_on": ["code-quality-reviewer"],
            "blocked_reason": blocked_reason,
            "missing_evidence": missing_evidence,
            "goal_status": goal.get("status"),
            "checks": list(checks),
            "findings": list(missing_evidence),
            "evidence_records": [
                _evidence_record(
                    qa_result_evidence(
                        passed=False,
                        evidence_key="qa gate passed",
                        checks=missing_evidence,
                    )
                )
            ],
        }

    if not checks:
        return {
            "role": "qa-verifier",
            "status": "blocked",
            "message": "no QA checks were supplied",
            "blocks_on": ["code-quality-reviewer"],
            "checks": [],
            "findings": ["no QA checks were supplied"],
            "evidence_records": [
                _evidence_record(
                    qa_result_evidence(
                        passed=False,
                        evidence_key="qa gate passed",
                        checks=["no QA checks supplied"],
                    )
                )
            ],
        }

    skip_findings = _invalid_skip_findings(checks)
    if skip_findings:
        return {
            "role": "qa-verifier",
            "status": "blocked",
            "message": f"{len(skip_findings)} QA skip record(s) are not scoped or evidenced",
            "blocks_on": ["code-quality-reviewer"],
            "checks": list(checks),
            "findings": skip_findings,
            "evidence_records": [
                _evidence_record(
                    qa_result_evidence(
                        passed=False,
                        evidence_key="qa gate passed",
                        checks=["invalid QA skip record"],
                    )
                )
            ],
        }

    findings = [
        f"{check.get('requirement_id', 'REQ')} {check.get('status')}: {check.get('description', 'qa check')}"
        for check in checks
        if check.get("status") in {"failed", "blocked"}
    ]
    status = "passed"
    if any(check.get("status") == "failed" for check in checks):
        status = "failed"
    elif any(check.get("status") == "blocked" for check in checks):
        status = "blocked"

    gate = {
        "role": "qa-verifier",
        "status": status,
        "message": "all QA checks passed" if status == "passed" else f"{len(findings)} QA check(s) need attention",
        "blocks_on": ["code-quality-reviewer"],
        "checks": list(checks),
        "findings": findings,
        "evidence_records": [
            _evidence_record(
                qa_result_evidence(
                    passed=status == "passed",
                    evidence_key="qa gate passed",
                    checks=[check.get("requirement_id", "") for check in checks],
                )
            )
        ],
    }
    if goal:
        gate["goal_status"] = goal.get("status")
    return gate


def _invalid_skip_findings(checks: List[Dict[str, Any]]) -> List[str]:
    findings: List[str] = []
    for check in checks:
        if check.get("status") != "skipped":
            continue
        evidence = list(check.get("evidence", []) or [])
        notes = str(check.get("notes", "") or "")
        scope = str(check.get("scope", "") or check.get("requirement_id", "") or "")
        if not evidence or not notes or not scope:
            findings.append(
                f"{check.get('requirement_id', 'QA-SKIP')} skipped QA check requires scope, notes, and evidence"
            )
    return findings


def evaluate_qa_gate(
    quality_gate: Dict[str, Any],
    goal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if quality_gate.get("status") != "passed":
        return {
            "role": "qa-verifier",
            "status": "blocked",
            "message": "quality review did not pass",
            "blocks_on": ["code-quality-reviewer"],
            "findings": [],
            "evidence_records": [
                _evidence_record(
                    qa_result_evidence(
                        passed=False,
                        evidence_key="qa gate passed",
                        checks=["quality review"],
                    )
                )
            ],
        }

    if _goal_blocked_by_evidence(goal):
        missing_evidence = _missing_goal_evidence(goal)
        blocked_reason = goal.get("blocked_reason", "missing required goal evidence")
        return {
            "role": "qa-verifier",
            "status": "blocked",
            "message": f"missing goal evidence: {', '.join(missing_evidence)}",
            "blocks_on": ["code-quality-reviewer"],
            "blocked_reason": blocked_reason,
            "missing_evidence": missing_evidence,
            "goal_status": goal.get("status"),
            "findings": list(missing_evidence),
            "evidence_records": [
                _evidence_record(
                    qa_result_evidence(
                        passed=False,
                        evidence_key="qa gate passed",
                        checks=missing_evidence,
                    )
                )
            ],
        }

    gate = {
        "role": "qa-verifier",
        "status": "passed",
        "message": "all task evidence is successful",
        "blocks_on": ["code-quality-reviewer"],
        "findings": [],
        "evidence_records": [
            _evidence_record(
                qa_result_evidence(
                    passed=True,
                    evidence_key="qa gate passed",
                    checks=["task evidence"],
                )
            )
        ],
    }
    if goal:
        gate["goal_status"] = goal.get("status")
    return gate


def evaluate_security_gate(
    quality_gate: Dict[str, Any],
    task_results: List[Dict[str, Any]],
    goal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if quality_gate.get("status") != "passed":
        return {
            "role": "security-reviewer",
            "status": "blocked",
            "message": "quality review did not pass",
            "blocks_on": ["code-quality-reviewer"],
            "findings": [],
            "evidence_records": [
                _evidence_record(
                    review_result_evidence(
                        role="security-reviewer",
                        passed=False,
                        evidence_key="security review passed",
                    )
                )
            ],
        }

    findings = []
    for result in task_results:
        metadata = result.get("metadata", {}) or {}
        findings.extend(metadata.get("security_findings", []) or [])

    status = "failed" if findings else "passed"
    gate = {
        "role": "security-reviewer",
        "status": status,
        "message": "no task-level security blocker reported" if not findings else f"{len(findings)} security finding(s) reported",
        "blocks_on": ["code-quality-reviewer"],
        "findings": findings,
        "evidence_records": [
            _evidence_record(
                review_result_evidence(
                    role="security-reviewer",
                    passed=status == "passed",
                    evidence_key="security review passed",
                    findings=findings,
                )
            )
        ],
    }
    if goal:
        gate["goal_status"] = goal.get("status")
    return gate


def evaluate_release_gate(
    qa_gate: Dict[str, Any],
    security_gate: Dict[str, Any],
    goal: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if qa_gate.get("status") != "passed" or security_gate.get("status") != "passed":
        missing_evidence = list(qa_gate.get("missing_evidence", []))
        blocked_reason = qa_gate.get("blocked_reason") or security_gate.get("blocked_reason", "")
        message = "goal evidence gate did not pass" if missing_evidence else "verification and security gates did not pass"
        gate = {
            "role": "release-manager",
            "status": "blocked",
            "message": message,
            "blocks_on": ["qa-verifier", "security-reviewer"],
            "blocked_reason": blocked_reason,
            "missing_evidence": missing_evidence,
            "findings": list(qa_gate.get("findings", [])) + list(security_gate.get("findings", [])),
            "evidence_records": [
                _evidence_record(
                    review_result_evidence(
                        role="release-manager",
                        passed=False,
                        evidence_key="release gate passed",
                    )
                )
            ],
        }
        if goal:
            gate["goal_status"] = goal.get("status")
        return gate

    gate = {
        "role": "release-manager",
        "status": "passed",
        "message": "review, verification, and security gates passed",
        "blocks_on": ["qa-verifier", "security-reviewer"],
        "findings": [],
        "evidence_records": [
            _evidence_record(
                review_result_evidence(
                    role="release-manager",
                    passed=True,
                    evidence_key="release gate passed",
                )
            )
        ],
    }
    if goal:
        gate["goal_status"] = goal.get("status")
    return gate


def build_gate_results(
    task_results: List[Dict[str, Any]],
    goal: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    spec_gate = evaluate_spec_review_gate(task_results)
    quality_gate = evaluate_code_quality_gate(spec_gate, task_results=task_results)
    qa_gate = evaluate_qa_gate(quality_gate, goal=goal)
    security_gate = evaluate_security_gate(quality_gate, task_results, goal=goal)
    release_gate = evaluate_release_gate(qa_gate, security_gate, goal=goal)
    return [
        spec_gate,
        quality_gate,
        qa_gate,
        security_gate,
        release_gate,
    ]
