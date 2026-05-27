import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.contracts import WorkflowTaskResult


@dataclass(frozen=True)
class AntigravityNativeDispatchResult:
    status: str
    message: str = ""
    task_results: List[WorkflowTaskResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "task_results": [result.to_dict() for result in self.task_results],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AntigravityNativeDispatchResult":
        return cls(
            status=data.get("status", ""),
            message=data.get("message", ""),
            task_results=[
                WorkflowTaskResult.from_dict(result)
                for result in data.get("task_results", [])
            ],
            metadata=dict(data.get("metadata", {})),
        )


class AntigravityNativeAdapter:
    name = "antigravity-native"

    def dispatch(self, request) -> AntigravityNativeDispatchResult:
        raise NotImplementedError("Antigravity native host dispatch is not configured")


class AntigravityNativeSidecarAdapter(AntigravityNativeAdapter):
    name = "antigravity-native-sidecar"

    def __init__(
        self,
        command: List[str],
        cwd: str = None,
        env: Dict[str, str] = None,
        timeout_seconds: float = 120.0,
    ):
        self.command = list(command)
        self.cwd = cwd
        self.env = dict(env or {})
        self.timeout_seconds = timeout_seconds

    def dispatch(self, request) -> AntigravityNativeDispatchResult:
        if not self.command:
            return AntigravityNativeDispatchResult(
                status="failed",
                message="Antigravity native sidecar command is empty",
                metadata={"error_type": "ValueError"},
            )

        env = os.environ.copy()
        env.update(self.env)
        try:
            completed = subprocess.run(
                self.command,
                input=json.dumps(request.to_dict()),
                cwd=self.cwd,
                env=env,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            return AntigravityNativeDispatchResult(
                status="failed",
                message=exc.stderr or "Antigravity native sidecar timed out",
                metadata={
                    "sidecar_command": list(self.command),
                    "sidecar_exit_code": 124,
                    "sidecar_stdout": exc.stdout or "",
                    "sidecar_stderr": exc.stderr or "Antigravity native sidecar timed out",
                    "error_type": type(exc).__name__,
                },
            )
        except Exception as exc:
            return AntigravityNativeDispatchResult(
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
            return AntigravityNativeDispatchResult(
                status="failed",
                message=completed.stderr or completed.stdout,
                metadata={
                    "sidecar_command": list(self.command),
                    "sidecar_exit_code": completed.returncode,
                    "sidecar_stdout": completed.stdout,
                    "sidecar_stderr": completed.stderr,
                },
            )

        try:
            result = AntigravityNativeDispatchResult.from_dict(json.loads(completed.stdout or "{}"))
        except Exception as exc:
            return AntigravityNativeDispatchResult(
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
        return AntigravityNativeDispatchResult(
            status=result.status,
            message=result.message,
            task_results=list(result.task_results),
            metadata=metadata,
        )
