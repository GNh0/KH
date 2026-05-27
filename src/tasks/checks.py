import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from src.orchestration.evidence_producers import (
    EvidenceProducerResult,
    command_result_evidence,
)


@dataclass(frozen=True)
class CommandCheckInput:
    project_dir: str
    command: List[str]
    evidence_key: str
    timeout_seconds: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_dir": self.project_dir,
            "command": list(self.command),
            "evidence_key": self.evidence_key,
            "timeout_seconds": self.timeout_seconds,
            "metadata": dict(self.metadata),
        }


_COMMAND_CHECK_PRESETS: Dict[str, Dict[str, Any]] = {
    "plugin-json": {
        "command": [sys.executable, "-m", "json.tool", "plugin.json"],
        "evidence_key": "plugin json valid",
        "timeout_seconds": 10.0,
    },
    "python-compile": {
        "command": [
            sys.executable,
            "-B",
            "-c",
            (
                "import pathlib; "
                "[compile(p.read_text(encoding='utf-8'), str(p), 'exec') "
                "for p in pathlib.Path('.').rglob('*.py')]"
            ),
        ],
        "evidence_key": "python compile passed",
        "timeout_seconds": 30.0,
    },
    "python-unittest": {
        "command": [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        "evidence_key": "unit tests passed",
        "timeout_seconds": 120.0,
    },
    "skill-catalog": {
        "command": [sys.executable, "-m", "src.skills.uaf_skill_catalog", "--check"],
        "evidence_key": "skill catalog valid",
        "timeout_seconds": 30.0,
    },
}


def available_command_check_presets() -> List[str]:
    return sorted(_COMMAND_CHECK_PRESETS)


def command_check_preset_evidence_key(preset_name: str) -> str:
    preset = _COMMAND_CHECK_PRESETS.get(preset_name)
    if not preset:
        raise ValueError(f"unknown command check preset: {preset_name}")
    return preset["evidence_key"]


def command_check_preset(
    project_dir: str,
    preset_name: str,
    metadata: Dict[str, Any] = None,
) -> CommandCheckInput:
    preset = _COMMAND_CHECK_PRESETS.get(preset_name)
    if not preset:
        raise ValueError(f"unknown command check preset: {preset_name}")

    check_metadata = dict(metadata or {})
    check_metadata["preset"] = preset_name
    return CommandCheckInput(
        project_dir=project_dir,
        command=list(preset["command"]),
        evidence_key=preset["evidence_key"],
        timeout_seconds=float(preset["timeout_seconds"]),
        metadata=check_metadata,
    )


def command_check_presets(
    project_dir: str,
    preset_names: List[str],
    metadata: Dict[str, Any] = None,
) -> List[CommandCheckInput]:
    return [
        command_check_preset(project_dir, preset_name, metadata=metadata)
        for preset_name in preset_names
    ]


class CommandCheckRunner:
    name = "command-check"

    def run(self, check: CommandCheckInput) -> EvidenceProducerResult:
        start = time.perf_counter()
        try:
            project_root = _resolve_project_dir(check.project_dir)
            if not check.command:
                raise ValueError("command must contain at least one argument")

            completed = subprocess.run(
                check.command,
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=check.timeout_seconds,
                shell=False,
            )
            elapsed = time.perf_counter() - start
            result = command_result_evidence(
                command=" ".join(check.command),
                exit_code=completed.returncode,
                evidence_key=check.evidence_key,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
            metadata = dict(result.metadata)
            metadata.update(
                {
                    "runner": self.name,
                    "project_dir": str(project_root),
                    "timeout_seconds": check.timeout_seconds,
                    "elapsed_seconds": elapsed,
                    **dict(check.metadata),
                }
            )
            return EvidenceProducerResult(
                source=result.source,
                status=result.status,
                evidence=list(result.evidence),
                metadata=metadata,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - start
            return EvidenceProducerResult(
                source="command",
                status="failed",
                evidence=[],
                metadata={
                    "command": " ".join(check.command),
                    "exit_code": 124,
                    "stdout": exc.stdout or "",
                    "stderr": exc.stderr or "command timed out",
                    "runner": self.name,
                    "project_dir": check.project_dir,
                    "timeout_seconds": check.timeout_seconds,
                    "elapsed_seconds": elapsed,
                    "error_type": type(exc).__name__,
                },
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start
            return EvidenceProducerResult(
                source="command",
                status="failed",
                evidence=[],
                metadata={
                    "command": " ".join(check.command),
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": str(exc),
                    "runner": self.name,
                    "project_dir": check.project_dir,
                    "timeout_seconds": check.timeout_seconds,
                    "elapsed_seconds": elapsed,
                    "error_type": type(exc).__name__,
                },
            )


def _resolve_project_dir(project_dir: str) -> Path:
    project_root = Path(project_dir).resolve()
    if not project_root.exists() or not project_root.is_dir():
        raise ValueError(f"project_dir does not exist or is not a directory: {project_dir}")
    return project_root
