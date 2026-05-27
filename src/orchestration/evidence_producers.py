from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List

from src.orchestration.goal_evidence import normalize_evidence_key


@dataclass(frozen=True)
class EvidenceProducerResult:
    source: str
    status: str
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status,
            "evidence": list(self.evidence),
            "metadata": dict(self.metadata),
        }


def _append_unique(items: List[str], value: Any) -> None:
    normalized = normalize_evidence_key(value)
    if normalized and normalized not in items:
        items.append(normalized)


def _passed_evidence(passed: bool, evidence_key: str) -> List[str]:
    evidence: List[str] = []
    if passed:
        _append_unique(evidence, evidence_key)
    return evidence


def command_result_evidence(
    command: str,
    exit_code: int,
    evidence_key: str = "",
    stdout: str = "",
    stderr: str = "",
) -> EvidenceProducerResult:
    passed = int(exit_code) == 0
    key = evidence_key or f"command passed: {command}"
    return EvidenceProducerResult(
        source="command",
        status="passed" if passed else "failed",
        evidence=_passed_evidence(passed, key),
        metadata={
            "command": command,
            "exit_code": int(exit_code),
            "stdout": stdout,
            "stderr": stderr,
        },
    )


def review_result_evidence(
    role: str,
    passed: bool,
    evidence_key: str = "",
    findings: Iterable[str] = None,
) -> EvidenceProducerResult:
    key = evidence_key or f"{role} review passed"
    return EvidenceProducerResult(
        source="review",
        status="passed" if passed else "failed",
        evidence=_passed_evidence(passed, key),
        metadata={
            "role": role,
            "findings": list(findings or []),
        },
    )


def qa_result_evidence(
    passed: bool,
    evidence_key: str = "qa passed",
    checks: Iterable[str] = None,
) -> EvidenceProducerResult:
    return EvidenceProducerResult(
        source="qa",
        status="passed" if passed else "failed",
        evidence=_passed_evidence(passed, evidence_key),
        metadata={
            "checks": list(checks or []),
        },
    )


def collect_metadata_evidence(metadata: Dict[str, Any]) -> List[str]:
    evidence: List[str] = []
    if not metadata:
        return evidence

    for item in metadata.get("evidence", []) or []:
        _append_unique(evidence, item)

    for record in metadata.get("evidence_records", []) or []:
        if isinstance(record, EvidenceProducerResult):
            record_items = record.evidence
        elif isinstance(record, dict):
            record_items = record.get("evidence", []) or []
        else:
            record_items = []

        for item in record_items:
            _append_unique(evidence, item)

    return evidence
