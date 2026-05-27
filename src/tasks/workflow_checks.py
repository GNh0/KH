from dataclasses import dataclass, field
from typing import Dict, List

from src.orchestration.evidence_producers import collect_metadata_evidence
from src.tasks.browser_qa import BrowserQACheckInput, BrowserQACheckRunner, BrowserQASidecarAdapter
from src.tasks.checks import (
    CommandCheckInput,
    CommandCheckRunner,
    command_check_preset,
    command_check_preset_evidence_key,
)


@dataclass(frozen=True)
class WorkflowCheckResults:
    command_results: List[dict] = field(default_factory=list)
    browser_qa_results: List[dict] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(
            result.get("status") == "passed"
            for result in self.command_results + self.browser_qa_results
        )

    @property
    def evidence(self) -> List[str]:
        return collect_metadata_evidence(
            {"evidence_records": self.command_results + self.browser_qa_results}
        )

    def to_metadata(self) -> Dict[str, List[dict]]:
        return {
            "command_check_results": list(self.command_results),
            "browser_qa_results": list(self.browser_qa_results),
        }


class WorkflowCheckStage:
    def __init__(self, command_runner: CommandCheckRunner = None):
        self.command_runner = command_runner or CommandCheckRunner()

    def required_evidence(self, metadata: dict) -> List[str]:
        required: List[str] = []
        for evidence_key in (
            _command_check_required_evidence(metadata)
            + _browser_qa_required_evidence(metadata)
        ):
            if evidence_key and evidence_key not in required:
                required.append(evidence_key)
        return required

    def run(self, project_dir: str, metadata: dict) -> WorkflowCheckResults:
        command_results = self._run_command_checks(project_dir, metadata)
        browser_qa_results = self._run_browser_qa_checks(metadata)
        return WorkflowCheckResults(
            command_results=command_results,
            browser_qa_results=browser_qa_results,
        )

    def _run_command_checks(self, project_dir: str, metadata: dict) -> List[dict]:
        results: List[dict] = []
        checks = _explicit_command_check_inputs(project_dir, metadata)
        for preset_name in _command_check_preset_names(metadata):
            try:
                checks.append(command_check_preset(project_dir=project_dir, preset_name=preset_name))
            except ValueError as exc:
                results.append(_unknown_command_check_preset_result(project_dir, preset_name, exc))

        for check in checks:
            results.append(self.command_runner.run(check).to_dict())
        return results

    def _run_browser_qa_checks(self, metadata: dict) -> List[dict]:
        runner = BrowserQACheckRunner(adapter=_browser_qa_adapter(metadata))
        return [
            runner.run(check).to_dict()
            for check in _browser_qa_check_inputs(metadata)
        ]


def goal_with_check_requirements(goal: dict, metadata: dict) -> dict:
    if not goal:
        return {}

    updated_goal = dict(goal)
    evidence_required = list(updated_goal.get("evidence_required", []))
    for evidence_key in WorkflowCheckStage().required_evidence(metadata):
        if evidence_key not in evidence_required:
            evidence_required.append(evidence_key)
    updated_goal["evidence_required"] = evidence_required
    return updated_goal


def _command_check_specs(metadata: dict) -> List[dict]:
    return [
        spec
        for spec in metadata.get("command_checks", []) or []
        if isinstance(spec, dict)
    ]


def _command_check_preset_names(metadata: dict) -> List[str]:
    return [
        preset_name
        for preset_name in metadata.get("command_check_presets", []) or []
        if isinstance(preset_name, str) and preset_name
    ]


def _command_check_required_evidence(metadata: dict) -> List[str]:
    required: List[str] = []
    for spec in _command_check_specs(metadata):
        evidence_key = spec.get("evidence_key", "")
        if evidence_key and evidence_key not in required:
            required.append(evidence_key)
    for preset_name in _command_check_preset_names(metadata):
        try:
            evidence_key = command_check_preset_evidence_key(preset_name)
        except ValueError:
            continue
        if evidence_key and evidence_key not in required:
            required.append(evidence_key)
    return required


def _browser_qa_check_specs(metadata: dict) -> List[dict]:
    return [
        spec
        for spec in metadata.get("browser_qa_checks", []) or []
        if isinstance(spec, dict)
    ]


def _browser_qa_required_evidence(metadata: dict) -> List[str]:
    required: List[str] = []
    for spec in _browser_qa_check_specs(metadata):
        evidence_key = spec.get("evidence_key", "")
        if evidence_key and evidence_key not in required:
            required.append(evidence_key)
    return required


def _explicit_command_check_inputs(project_dir: str, metadata: dict) -> List[CommandCheckInput]:
    checks: List[CommandCheckInput] = []
    for spec in _command_check_specs(metadata):
        command = spec.get("command", [])
        if isinstance(command, str):
            command = [command]
        checks.append(
            CommandCheckInput(
                project_dir=project_dir,
                command=list(command),
                evidence_key=spec.get("evidence_key", ""),
                timeout_seconds=float(spec.get("timeout_seconds", 30.0)),
                metadata=dict(spec.get("metadata", {})),
            )
        )
    return checks


def _browser_qa_check_inputs(metadata: dict) -> List[BrowserQACheckInput]:
    checks: List[BrowserQACheckInput] = []
    for spec in _browser_qa_check_specs(metadata):
        checks.append(
            BrowserQACheckInput(
                target=spec.get("target", ""),
                evidence_key=spec.get("evidence_key", ""),
                scenario=spec.get("scenario", ""),
                timeout_seconds=float(spec.get("timeout_seconds", 30.0)),
                metadata=dict(spec.get("metadata", {})),
            )
        )
    return checks


def _browser_qa_adapter(metadata: dict):
    if metadata.get("browser_qa_adapter"):
        return metadata.get("browser_qa_adapter")

    sidecar = metadata.get("browser_qa_sidecar", {}) or {}
    command = sidecar.get("command", [])
    if command:
        return BrowserQASidecarAdapter(
            command=list(command),
            cwd=sidecar.get("cwd"),
            env=dict(sidecar.get("env", {}) or {}),
            timeout_seconds=sidecar.get("timeout_seconds"),
        )
    return None


def _unknown_command_check_preset_result(project_dir: str, preset_name: str, exc: Exception) -> dict:
    return {
        "source": "command",
        "status": "failed",
        "evidence": [],
        "metadata": {
            "command": "",
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
            "runner": "command-check",
            "project_dir": project_dir,
            "timeout_seconds": 0.0,
            "error_type": type(exc).__name__,
            "preset": preset_name,
        },
    }
