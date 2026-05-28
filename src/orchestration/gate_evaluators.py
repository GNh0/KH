from typing import Any, Dict, List, Optional

from src.orchestration.evidence_producers import (
    collect_metadata_evidence,
    qa_result_evidence,
    review_result_evidence,
)


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
            findings.append(f"{_task_label(task)}: {finding}")
    return findings


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
    if findings:
        return {
            "role": "code-quality-reviewer",
            "status": "failed",
            "message": f"{len(findings)} quality finding(s) reported",
            "blocks_on": ["spec-reviewer"],
            "findings": findings,
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

    gate = {
        "role": "security-reviewer",
        "status": "passed",
        "message": "no task-level security blocker reported",
        "blocks_on": ["code-quality-reviewer"],
        "findings": findings,
        "evidence_records": [
            _evidence_record(
                review_result_evidence(
                    role="security-reviewer",
                    passed=True,
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
