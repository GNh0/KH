import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.orchestration.evidence_producers import (
    EvidenceProducerResult,
    qa_result_evidence,
)


class BrowserQAAdapterNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class BrowserQACheckInput:
    target: str
    evidence_key: str
    scenario: str = ""
    timeout_seconds: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "evidence_key": self.evidence_key,
            "scenario": self.scenario,
            "timeout_seconds": self.timeout_seconds,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrowserQACheckResult:
    status: str
    message: str = ""
    checks: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "checks": list(self.checks),
            "findings": list(self.findings),
            "artifacts": dict(self.artifacts),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrowserQACheckResult":
        return cls(
            status=data.get("status", ""),
            message=data.get("message", ""),
            checks=list(data.get("checks", [])),
            findings=list(data.get("findings", [])),
            artifacts=dict(data.get("artifacts", {})),
            metadata=dict(data.get("metadata", {})),
        )


class BrowserQASidecarAdapter:
    name = "browser-qa-sidecar"

    def __init__(
        self,
        command: List[str],
        cwd: str = None,
        env: Dict[str, str] = None,
        timeout_seconds: float = None,
    ):
        self.command = list(command)
        self.cwd = cwd
        self.env = dict(env or {})
        self.timeout_seconds = timeout_seconds

    def run(self, check: BrowserQACheckInput) -> BrowserQACheckResult:
        if not self.command:
            return BrowserQACheckResult(
                status="failed",
                message="browser QA sidecar command is empty",
                metadata={"error_type": "ValueError"},
            )

        timeout_seconds = self.timeout_seconds or check.timeout_seconds
        env = os.environ.copy()
        env.update(self.env)
        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(check.to_dict()),
                cwd=self.cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            return BrowserQACheckResult(
                status="failed",
                message=exc.stderr or "browser QA sidecar timed out",
                metadata={
                    "sidecar_command": list(self.command),
                    "sidecar_exit_code": 124,
                    "sidecar_stdout": exc.stdout or "",
                    "sidecar_stderr": exc.stderr or "browser QA sidecar timed out",
                    "error_type": type(exc).__name__,
                },
            )
        except Exception as exc:
            return BrowserQACheckResult(
                status="failed",
                message=str(exc),
                metadata={
                    "sidecar_command": list(self.command),
                    "sidecar_exit_code": 1,
                    "sidecar_stdout": "",
                    "sidecar_stderr": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

        if completed.returncode != 0:
            return BrowserQACheckResult(
                status="failed",
                message=completed.stderr or completed.stdout,
                findings=[completed.stderr or completed.stdout],
                metadata={
                    "sidecar_command": list(self.command),
                    "sidecar_exit_code": completed.returncode,
                    "sidecar_stdout": completed.stdout,
                    "sidecar_stderr": completed.stderr,
                },
            )

        try:
            payload = json.loads(completed.stdout or "{}")
            result = BrowserQACheckResult.from_dict(payload)
        except Exception as exc:
            return BrowserQACheckResult(
                status="failed",
                message=str(exc),
                metadata={
                    "sidecar_command": list(self.command),
                    "sidecar_exit_code": completed.returncode,
                    "sidecar_stdout": completed.stdout,
                    "sidecar_stderr": completed.stderr,
                    "error_type": type(exc).__name__,
                },
            )

        metadata = dict(result.metadata)
        metadata.update(
            {
                "sidecar_command": list(self.command),
                "sidecar_exit_code": completed.returncode,
                "sidecar_stdout": completed.stdout,
                "sidecar_stderr": completed.stderr,
            }
        )
        return BrowserQACheckResult(
            status=result.status,
            message=result.message,
            checks=list(result.checks),
            findings=list(result.findings),
            artifacts=dict(result.artifacts),
            metadata=metadata,
        )


class BrowserQACheckRunner:
    name = "browser-qa"

    def __init__(self, adapter=None):
        self.adapter = adapter

    def run(self, check: BrowserQACheckInput) -> EvidenceProducerResult:
        if not self.adapter:
            return EvidenceProducerResult(
                source="qa",
                status="blocked",
                evidence=[],
                metadata={
                    "runner": self.name,
                    "adapter": "",
                    "target": check.target,
                    "scenario": check.scenario,
                    "timeout_seconds": check.timeout_seconds,
                    "error_type": BrowserQAAdapterNotConfigured.__name__,
                    "message": "browser QA adapter is not configured",
                },
            )

        adapter_name = getattr(self.adapter, "name", self.adapter.__class__.__name__)
        try:
            result = self.adapter.run(check)
            passed = result.status == "passed"
            evidence = qa_result_evidence(
                passed=passed,
                evidence_key=check.evidence_key,
                checks=result.checks or [check.scenario],
            )
            metadata = dict(evidence.metadata)
            metadata.update(
                {
                    "runner": self.name,
                    "adapter": adapter_name,
                    "target": check.target,
                    "scenario": check.scenario,
                    "timeout_seconds": check.timeout_seconds,
                    "message": result.message,
                    "findings": list(result.findings),
                    "artifacts": dict(result.artifacts),
                    **dict(result.metadata),
                    **dict(check.metadata),
                }
            )
            return EvidenceProducerResult(
                source=evidence.source,
                status="passed" if passed else result.status or "failed",
                evidence=list(evidence.evidence),
                metadata=metadata,
            )
        except Exception as exc:
            return EvidenceProducerResult(
                source="qa",
                status="failed",
                evidence=[],
                metadata={
                    "runner": self.name,
                    "adapter": adapter_name,
                    "target": check.target,
                    "scenario": check.scenario,
                    "timeout_seconds": check.timeout_seconds,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
            )
