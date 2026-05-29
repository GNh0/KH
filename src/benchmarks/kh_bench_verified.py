import argparse
import asyncio
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.contracts import MemoryRecord, MemoryScope, WorkflowDispatchResult
from src.core.snapshot_manager import SnapshotManager
from src.orchestration.artifacts import build_design_stage
from src.orchestration.goal_ledger import GoalLedger
from src.orchestration.handoff import ResumeHandoff
from src.orchestration.memory_store import MemoryStore
from src.orchestration.quality_harnesses import audit_role_execution
from src.orchestration.role_orchestrator import RoleOrchestrator
from src.skills.token_optimizer import optimize_context_content
from src.tasks.runners import LLMCodeGenerationAdapter, LocalTaskRunner, WorkflowTaskInput
from src.tasks.workflows import dispatch_project_workflow


BENCHMARK_NAME = "KH-Bench Verified"
TASK_SCHEMA_VERSION = "1.0"
SCORE_SCHEMA_VERSION = "kh-bench-score/v1"


def load_verified_tasks() -> List[Dict[str, Any]]:
    """Return the fixed practical task set for local KH UAF verification."""
    return json.loads(json.dumps(_TASKS))


def run_kh_bench_verified(
    output_root: Optional[Path] = None,
    task_ids: Optional[Iterable[str]] = None,
    candidate_runner: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run all selected verified tasks and return a SWE-bench-style score report."""
    started = time.perf_counter()
    output_root = Path(output_root or tempfile.gettempdir()).resolve()
    run_id = f"khbench-run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{_short_hash(str(time.time_ns()))}"
    run_root = output_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)

    selected = _select_tasks(load_verified_tasks(), set(task_ids or []))
    runner = candidate_runner or KHBaselineCandidateRunner()
    results = [run_verified_task(task, run_root, runner) for task in selected]
    summary = _score_summary(results)
    report = {
        "schema_version": TASK_SCHEMA_VERSION,
        "score_schema_version": SCORE_SCHEMA_VERSION,
        "benchmark": BENCHMARK_NAME,
        "suite_id": "kh-bench-verified",
        "run_id": run_id,
        "generated_at": _utc_now(),
        "duration_seconds": round(time.perf_counter() - started, 6),
        "task_count": len(results),
        "resolved_count": summary["passed"],
        "resolved_rate": summary["pass_rate"],
        "summary": summary,
        "categories": sorted({result["category"] for result in results}),
        "unresolved": [result["instance_id"] for result in results if not result["resolved"]],
        "results": results,
        "runtime": {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "output_root": str(output_root),
            "candidate_runner": getattr(runner, "name", runner.__class__.__name__),
        },
    }
    (run_root / "kh_bench_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return report


class KHBaselineCandidateRunner:
    """Built-in baseline runner used to score KH UAF itself against the task set."""

    name = "kh-uaf-baseline"

    def run(self, task: Dict[str, Any], workspace: Path, runtime_root: Path) -> Dict[str, Any]:
        return _execute_candidate_profile(task, workspace, runtime_root)


def run_verified_task(task: Dict[str, Any], run_root: Path, candidate_runner: Optional[Any] = None) -> Dict[str, Any]:
    task_root = run_root / task["instance_id"]
    workspace = task_root / "workspace"
    runtime_root = task_root / "runtime"
    workspace.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)
    _materialize_base_workspace(workspace, task.get("base_workspace", {}))

    context: Dict[str, Any] = {
        "workspace": workspace,
        "runtime_root": runtime_root,
        "artifacts": [],
        "workflow": {},
    }
    pre_results = _evaluate_phase(task.get("pre_validation", []), context, expected_failure_phase=True)
    status = "failed"
    failure_reason = ""
    candidate_result: Dict[str, Any] = {}

    try:
        previous_runtime_root = os.environ.get("UAF_RUNTIME_ROOT")
        previous_project_local_state = os.environ.get("UAF_PROJECT_LOCAL_STATE")
        os.environ["UAF_RUNTIME_ROOT"] = str(runtime_root)
        os.environ["UAF_PROJECT_LOCAL_STATE"] = "0"
        try:
            runner = candidate_runner or KHBaselineCandidateRunner()
            candidate_view = task if isinstance(runner, KHBaselineCandidateRunner) else _public_task_view(task)
            candidate_result = runner.run(candidate_view, workspace, runtime_root)
        finally:
            if previous_runtime_root is None:
                os.environ.pop("UAF_RUNTIME_ROOT", None)
            else:
                os.environ["UAF_RUNTIME_ROOT"] = previous_runtime_root
            if previous_project_local_state is None:
                os.environ.pop("UAF_PROJECT_LOCAL_STATE", None)
            else:
                os.environ["UAF_PROJECT_LOCAL_STATE"] = previous_project_local_state
        context.update({
            "artifacts": candidate_result.get("artifacts", []),
            "workflow": candidate_result.get("workflow", {}),
        })
        fail_to_pass = _evaluate_phase(task.get("fail_to_pass", []), context)
        pass_to_pass = _evaluate_phase(task.get("pass_to_pass", []), context)
        resolved = (
            pre_results["passed"] == pre_results["total"]
            and fail_to_pass["passed"] == fail_to_pass["total"]
            and pass_to_pass["passed"] == pass_to_pass["total"]
        )
        status = "passed" if resolved else "failed"
        if not resolved:
            failure_reason = _first_failure_reason(pre_results, fail_to_pass, pass_to_pass)
    except Exception as exc:
        fail_to_pass = _empty_phase(task.get("fail_to_pass", []), f"candidate runner raised {type(exc).__name__}: {exc}")
        pass_to_pass = _empty_phase(task.get("pass_to_pass", []), "candidate runner did not complete")
        resolved = False
        status = "infra_error"
        failure_reason = str(exc)

    result = {
        "schema_version": TASK_SCHEMA_VERSION,
        "instance_id": task["instance_id"],
        "title": task["title"],
        "category": task["category"],
        "difficulty": task["difficulty"],
        "status": status,
        "resolved": resolved,
        "score": 1.0 if resolved else 0.0,
        "workspace": str(workspace),
        "runtime_root": str(runtime_root),
        "pre_validation": pre_results,
        "fail_to_pass": fail_to_pass,
        "pass_to_pass": pass_to_pass,
        "evidence": candidate_result.get("evidence", []),
        "artifacts": context["artifacts"],
        "runtime_contract": candidate_result.get("runtime_contract", {}),
        "candidate_runner": getattr(candidate_runner or KHBaselineCandidateRunner(), "name", (candidate_runner or KHBaselineCandidateRunner()).__class__.__name__),
        "failure_reason": failure_reason,
    }
    (run_root / task["instance_id"] / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return result


def evaluate_validator(validator: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate one validator in fail-closed form."""
    validator_type = validator.get("type", "")
    name = validator.get("name", validator_type or "validator")
    try:
        if validator_type == "file_exists":
            path = _workspace_path(context, validator["path"])
            passed = path.exists() and path.is_file()
            return _validator_result(name, passed, f"{path.name} exists" if passed else f"missing file: {validator['path']}")
        if validator_type == "file_contains":
            path = _workspace_path(context, validator["path"])
            if not path.exists():
                return _validator_result(name, False, f"missing file: {validator['path']}")
            text = path.read_text(encoding="utf-8")
            missing = [value for value in validator.get("must_include", []) if str(value) not in text]
            return _validator_result(name, not missing, "required text present" if not missing else f"missing text: {missing}")
        if validator_type == "file_glob_count":
            matches = _workspace_glob(context, validator["pattern"])
            minimum = int(validator.get("minimum", 1))
            return _validator_result(name, len(matches) >= minimum, f"matched {len(matches)} file(s), expected >= {minimum}")
        if validator_type == "runtime_glob_count":
            matches = _runtime_glob(context, validator["pattern"])
            minimum = int(validator.get("minimum", 1))
            return _validator_result(name, len(matches) >= minimum, f"matched {len(matches)} runtime file(s), expected >= {minimum}")
        if validator_type == "json_file_field_equals":
            data = _read_workspace_json(context, validator["path"])
            actual = _lookup(data, validator["field"])
            expected = validator.get("value")
            return _validator_result(name, actual == expected, f"expected {expected!r}, got {actual!r}")
        if validator_type == "json_file_field_at_least":
            data = _read_workspace_json(context, validator["path"])
            actual = _lookup(data, validator["field"])
            if isinstance(actual, list):
                actual_value = len(actual)
            else:
                actual_value = actual
            minimum = validator.get("minimum", 0)
            passed = isinstance(actual_value, (int, float)) and actual_value >= minimum
            return _validator_result(name, passed, f"expected >= {minimum}, got {actual_value!r}")
        if validator_type == "json_file_field_contains_all":
            data = _read_workspace_json(context, validator["path"])
            actual = str(_lookup(data, validator["field"]) or "")
            missing = [value for value in validator.get("values", []) if str(value) not in actual]
            return _validator_result(name, not missing, "all required facts present" if not missing else f"missing facts: {missing}")
        if validator_type == "json_runtime_glob_field_equals":
            data = _first_runtime_json(context, validator["pattern"])
            actual = _lookup(data, validator["field"])
            expected = validator.get("value")
            return _validator_result(name, actual == expected, f"expected {expected!r}, got {actual!r}")
        if validator_type == "artifact_glob_formats":
            matches = _workspace_glob(context, validator["pattern"])
            formats = {_artifact_format(path) for path in matches}
            required = set(validator.get("formats", []))
            missing = sorted(required.difference(formats))
            return _validator_result(name, not missing, "required formats exist" if not missing else f"missing formats: {missing}")
        if validator_type == "renderable_artifacts":
            matches = _workspace_glob(context, validator["pattern"])
            failures = [str(path.name) for path in matches if not _is_renderable_artifact(path)]
            passed = bool(matches) and not failures
            return _validator_result(name, passed, f"renderable files: {len(matches)}" if passed else f"unrenderable artifacts: {failures}")
        if validator_type == "file_glob_text_contains_all":
            matches = _workspace_glob(context, validator["pattern"])
            combined = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in matches
                if _artifact_format(path) in {"md", "json", "svg", "dxf", "txt"}
            )
            missing = [value for value in validator.get("values", []) if str(value) not in combined]
            passed = bool(matches) and not missing
            return _validator_result(name, passed, "all required text present" if passed else f"missing text: {missing}")
        if validator_type == "snapshot_log_bundle_count":
            logs = _runtime_glob(context, "**/.snapshots/commit_log.json")
            entries: List[Dict[str, Any]] = []
            for log_path in logs:
                entries.extend(json.loads(log_path.read_text(encoding="utf-8")))
            bundle_count = sum(1 for entry in entries if entry.get("kind") == "bundle")
            minimum = int(validator.get("minimum", 1))
            return _validator_result(name, bundle_count >= minimum, f"bundle count: {bundle_count}")
        if validator_type == "memory_file_records_at_least":
            data = _read_workspace_json(context, validator["path"])
            count = len(data.get("records", []))
            minimum = int(validator.get("minimum", 1))
            return _validator_result(name, count >= minimum, f"memory record count: {count}")
        return _validator_result(name, False, f"unknown validator type: {validator_type}")
    except Exception as exc:
        return _validator_result(name, False, f"{type(exc).__name__}: {exc}")


def _execute_candidate_profile(task: Dict[str, Any], workspace: Path, runtime_root: Path) -> Dict[str, Any]:
    profile = task.get("candidate_profile", "")
    if profile == "context_optimization":
        return _baseline_context_optimization(task, workspace)
    if profile == "coding_workflow":
        return _baseline_coding_workflow(task, workspace)
    if profile == "domain_deliverables":
        return _baseline_domain_deliverables(task, workspace)
    if profile == "role_orchestration":
        return _baseline_role_orchestration(task, workspace)
    if profile == "snapshot_state":
        return _baseline_snapshot_state(task, workspace)
    if profile == "goal_memory":
        return _baseline_goal_memory(task, workspace)
    if profile == "side_markdown_generation":
        return _baseline_side_markdown_generation(task, workspace)
    if profile == "side_product_spec_deliverables":
        return _baseline_side_product_spec_deliverables(task, workspace)
    raise ValueError(f"unknown candidate profile: {profile}")


def _public_task_view(task: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "schema_version",
        "instance_id",
        "title",
        "category",
        "difficulty",
        "human_verified",
        "skills",
        "problem_statement",
        "base_workspace",
    }
    return json.loads(json.dumps({key: task[key] for key in allowed if key in task}))


def _baseline_context_optimization(task: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    log_text = (workspace / "logs" / "pytest.log").read_text(encoding="utf-8")
    result = optimize_context_content(
        log_text,
        content_kind="log",
        command="pytest tests",
        exit_code=1,
        max_lines=18,
    )
    report_path = workspace / "reports" / "token_summary.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return {
        "artifacts": [_artifact_record(report_path, workspace, "json", "token-optimizer-report")],
        "workflow": {"success": result.exit_code == 1},
        "evidence": ["command output optimized", "required failure facts preserved"],
        "runtime_contract": {"type": "HarnessResult", "fields": sorted(result.to_dict())},
    }


def _baseline_coding_workflow(task: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    metadata = {
        "domain_hint": "software-development",
        "scope": "Create a deterministic tiny app artifact and docs through the UAF workflow dispatcher.",
        "goal": {
            "objective": task["problem_statement"],
            "status": "active",
            "success_criteria": ["workflow succeeds", "role audit passes", "target files are generated"],
            "evidence_required": [
                "design_doc",
                "target_files",
                "workflow dispatch completed",
                "task runner completed",
                "role execution audited",
            ],
            "evidence": [],
            "metadata": {},
        },
    }
    result = dispatch_project_workflow(
        project_dir=str(workspace),
        file_list=["src/bench_app.py", "README.md"],
        design_doc="# KH workflow coding task\nCreate a deterministic local app artifact.",
        platform_mode="local",
        metadata=metadata,
    )
    result_dict = result.to_dict()
    role_audit = result.metadata.get("role_execution_audit", {})
    report_path = workspace / "reports" / "workflow_result.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result_dict, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    artifacts = _workflow_artifacts(result, workspace)
    artifacts.append(_artifact_record(report_path, workspace, "json", "workflow-dispatch-result"))
    return {
        "artifacts": artifacts,
        "workflow": result_dict,
        "evidence": ["workflow dispatch completed", "role execution audited", "target files generated"],
        "runtime_contract": {"type": "WorkflowDispatchResult", "fields": sorted(result_dict)},
    }


def _baseline_domain_deliverables(task: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    stage = build_design_stage(
        project_dir=str(workspace),
        workflow_id="workflow_khbench_product",
        design_doc="# Cable gland plate design\n22kw / CABLE GLAND PLATE 389 concept drawing and dimension package.",
        file_list=["22kw", "CABLE GLAND PLATE 389"],
        metadata={
            "domain_hint": "product-design",
            "scope": "Generate type-aware design deliverables from a compact product specification.",
            "deliverables": ["product design document", "dimension BOM", "concept SVG", "concept DXF"],
        },
    )
    exports = stage["deliverable_exports"]
    deliverables = exports.get("deliverables", [])
    report_path = workspace / "reports" / "deliverable_exports.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(exports, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    artifacts = [
        _artifact_record(Path(item["path"]), workspace, item.get("format", ""), item.get("artifact_type", ""))
        for item in deliverables
    ]
    artifacts.append(_artifact_record(report_path, workspace, "json", "deliverable-export-result"))
    return {
        "artifacts": artifacts,
        "workflow": {"success": exports.get("quality", {}).get("status") == "passed", "deliverable_exports": exports},
        "evidence": list(exports.get("evidence", [])),
        "runtime_contract": {"type": "deliverable_exports", "fields": sorted(exports)},
    }


def _baseline_role_orchestration(task: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    context = {
        "workflow_id": "workflow_khbench_roles",
        "project_dir": str(workspace),
        "work_design": {
            "objective": "Run all default KH UAF roles with artifact evidence.",
            "deliverables": ["role audit report"],
        },
        "metadata": {"thread_id": "khbench-roles"},
    }
    orchestration = RoleOrchestrator().run_sync(context)
    role_metadata = {
        "summary": {
            "execution_model": "dag-asyncio-role-waves",
            "success": orchestration.get("success", False),
            "wave_count": len(orchestration.get("waves", [])),
            "parallel_wave_count": sum(1 for wave in orchestration.get("waves", []) if wave.get("parallel")),
            "implementation_required": True,
            "role_count": len(orchestration.get("results", [])),
        },
        "results": orchestration.get("results", []),
    }
    audit = audit_role_execution(role_metadata)
    report_payload = {"summary": role_metadata["summary"], "results": role_metadata["results"], "audit": audit}
    report_path = workspace / "reports" / "role_orchestration.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    artifacts = []
    for result in role_metadata["results"]:
        metadata = result.get("metadata", {}) or {}
        for artifact in metadata.get("role_artifacts", []) or []:
            artifacts.append(_artifact_record(Path(artifact["path"]), workspace, "md", "role-stage-output"))
    artifacts.append(_artifact_record(report_path, workspace, "json", "role-orchestration-result"))
    return {
        "artifacts": artifacts,
        "workflow": {"success": audit.get("status") == "passed", "role_metadata": role_metadata},
        "evidence": list(audit.get("evidence", [])),
        "runtime_contract": {"type": "role_orchestration", "fields": ["summary", "results", "waves"]},
    }


def _baseline_snapshot_state(task: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    manager = SnapshotManager(str(workspace), thread_id="khbench-snapshot")
    version_id = manager.commit_many(["src/app.py", "README.md"], "benchmark work snapshot")
    (workspace / "src" / "app.py").write_text("BROKEN = True\n", encoding="utf-8")
    (workspace / "README.md").write_text("broken\n", encoding="utf-8")
    restored = manager.rollback_result(version_id)
    log_entries = json.loads(Path(manager.log_file).read_text(encoding="utf-8"))
    bundle_path = Path(manager.snapshot_dir) / version_id
    report_payload = {"version_id": version_id, "restored": restored, "log_entries": log_entries}
    report_path = workspace / "reports" / "snapshot_result.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return {
        "artifacts": [
            _artifact_record(bundle_path, workspace, "json.gz", "work-snapshot-bundle"),
            _artifact_record(report_path, workspace, "json", "snapshot-result"),
        ],
        "workflow": {"success": restored.get("status") == "restored", "snapshot": restored},
        "evidence": ["work snapshot created", "work snapshot restored"],
        "runtime_contract": {"type": "SnapshotManager.commit_many", "version_id": version_id},
    }


def _baseline_goal_memory(task: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    ledger = GoalLedger(str(workspace), thread_id="khbench-goal")
    goal = {
        "objective": "Persist a verified goal, memory record, and resume handoff.",
        "status": "complete",
        "success_criteria": ["goal saved", "memory saved", "handoff saved"],
        "evidence_required": ["goal saved", "memory saved", "handoff saved"],
        "evidence": ["goal saved", "memory saved", "handoff saved"],
        "metadata": {"decisions": ["KH-Bench task completed"]},
    }
    ledger.save_current_goal(goal, next_recommended_action="ready for score report")
    ledger.append_event("goal_completed", {"objective": goal["objective"], "status": "complete"})
    scope = MemoryScope(
        kind="project",
        namespace="project:khbench",
        project_id="khbench",
        thread_id="khbench-goal",
        root_path=str(workspace),
    )
    memory = MemoryStore(str(workspace / ".khbench-memory"), scope)
    memory.save_record(
        MemoryRecord(
            record_id="bench-memory-001",
            kind="decision",
            content="KH-Bench goal-memory baseline stores non-secret workflow evidence.",
            scope=scope.kind,
            source="kh-bench",
            confidence="high",
        )
    )
    handoff = ResumeHandoff(str(workspace), thread_id="khbench-goal").save()
    context = memory.build_context()
    report_payload = {"memory_context": context, "handoff": handoff.get("snapshot", {})}
    report_path = workspace / "reports" / "goal_memory_result.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return {
        "artifacts": [
            _artifact_record(ledger.current_goal_path, workspace, "json", "goal-state"),
            _artifact_record(memory.records_path, workspace, "json", "memory-records"),
            _artifact_record(Path(handoff["paths"]["json_path"]), workspace, "json", "resume-handoff"),
            _artifact_record(Path(handoff["paths"]["markdown_path"]), workspace, "md", "resume-handoff"),
            _artifact_record(report_path, workspace, "json", "goal-memory-result"),
        ],
        "workflow": {"success": True, "handoff": handoff.get("snapshot", {})},
        "evidence": ["goal saved", "memory saved", "handoff saved"],
        "runtime_contract": {"type": "GoalLedger+MemoryStore+ResumeHandoff", "fields": ["goal", "memory", "handoff"]},
    }


def _baseline_side_markdown_generation(task: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    class MarkdownRouter:
        def chat(self, system_prompt: str, user_prompt: str) -> str:
            return "\n".join([
                "# Usage Guide",
                "",
                "This section must survive extraction even when the response contains an embedded code fence.",
                "",
                "```python",
                "print('hello')",
                "```",
                "",
                "Done criteria: prose and fenced code are both preserved.",
            ])

    runner = LocalTaskRunner(adapter=LLMCodeGenerationAdapter(MarkdownRouter()))
    task_input = WorkflowTaskInput(
        project_dir=str(workspace),
        file_name="README.md",
        design_doc="Create a markdown README that preserves prose and embedded fenced code.",
        platform_mode="local",
        role="implementer",
    )
    result = asyncio.run(runner.run(task_input))
    result_dict = result.to_dict()
    report_path = workspace / "reports" / "markdown_generation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result_dict, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    artifacts = [_artifact_record(report_path, workspace, "json", "markdown-generation-result")]
    target_path = workspace / "README.md"
    if target_path.exists():
        artifacts.append(_artifact_record(target_path, workspace, "md", "generated-markdown"))
    return {
        "artifacts": artifacts,
        "workflow": result_dict,
        "evidence": ["markdown prose preserved", "embedded fenced code preserved"],
        "runtime_contract": {"type": "WorkflowTaskResult", "fields": sorted(result_dict)},
    }


def _baseline_side_product_spec_deliverables(task: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    stage = build_design_stage(
        project_dir=str(workspace),
        workflow_id="workflow_side_product_spec",
        design_doc=(
            "# Cable gland plate design\n"
            "22kw / CABLE GLAND PLATE 389. Plate size 200x120 mm, material SUS304, "
            "four M20 cable gland holes. Produce type-aware design handoff artifacts."
        ),
        file_list=["22kw", "CABLE GLAND PLATE 389", "200x120", "SUS304", "four M20"],
        metadata={
            "domain_hint": "product-design",
            "scope": "SIDE regression for compact product specs flowing into drawing deliverables.",
            "deliverables": ["product design document", "dimension BOM", "concept SVG", "concept DXF"],
        },
    )
    exports = stage["deliverable_exports"]
    deliverables = exports.get("deliverables", [])
    report_path = workspace / "reports" / "side_product_spec_exports.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(exports, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    artifacts = [
        _artifact_record(Path(item["path"]), workspace, item.get("format", ""), item.get("artifact_type", ""))
        for item in deliverables
    ]
    artifacts.append(_artifact_record(report_path, workspace, "json", "side-product-spec-export-result"))
    return {
        "artifacts": artifacts,
        "workflow": {"success": exports.get("quality", {}).get("status") == "passed", "deliverable_exports": exports},
        "evidence": list(exports.get("evidence", [])) + ["SIDE product spec facts preserved"],
        "runtime_contract": {"type": "deliverable_exports", "fields": sorted(exports)},
    }


def _evaluate_phase(validators: Iterable[Dict[str, Any]], context: Dict[str, Any], expected_failure_phase: bool = False) -> Dict[str, Any]:
    checks = []
    for validator in validators:
        raw = evaluate_validator(validator, context)
        if expected_failure_phase and validator.get("expect") == "fail":
            check = dict(raw)
            check["raw_passed"] = raw["passed"]
            check["passed"] = not raw["passed"]
            check["message"] = f"expected precondition failure observed: {raw['message']}" if check["passed"] else "precondition unexpectedly passed"
        else:
            check = raw
        checks.append(check)
    passed_count = sum(1 for check in checks if check["passed"])
    return {
        "passed": passed_count,
        "total": len(checks),
        "checks": checks,
    }


def _empty_phase(validators: Iterable[Dict[str, Any]], message: str) -> Dict[str, Any]:
    checks = [
        _validator_result(validator.get("name", validator.get("type", "validator")), False, message)
        for validator in validators
    ]
    return {"passed": 0, "total": len(checks), "checks": checks}


def _materialize_base_workspace(workspace: Path, spec: Dict[str, Any]) -> None:
    for file_spec in spec.get("files", []) or []:
        target = _workspace_path({"workspace": workspace}, file_spec["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(file_spec.get("content", "")), encoding="utf-8")


def _workspace_path(context: Dict[str, Any], relative_path: str) -> Path:
    workspace = Path(context["workspace"]).resolve()
    target = (workspace / relative_path).resolve()
    try:
        common = Path(_commonpath(workspace, target))
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {relative_path}") from exc
    if common != workspace:
        raise ValueError(f"path escapes workspace: {relative_path}")
    return target


def _runtime_path(context: Dict[str, Any]) -> Path:
    return Path(context["runtime_root"]).resolve()


def _workspace_glob(context: Dict[str, Any], pattern: str) -> List[Path]:
    workspace = Path(context["workspace"]).resolve()
    matches = sorted(path for path in workspace.glob(pattern) if path.is_file())
    return [path for path in matches if path.resolve().is_relative_to(workspace)]


def _runtime_glob(context: Dict[str, Any], pattern: str) -> List[Path]:
    runtime_root = _runtime_path(context)
    matches = sorted(path for path in runtime_root.glob(pattern) if path.is_file())
    return [path for path in matches if path.resolve().is_relative_to(runtime_root)]


def _read_workspace_json(context: Dict[str, Any], relative_path: str) -> Dict[str, Any]:
    path = _workspace_path(context, relative_path)
    if not path.exists():
        raise FileNotFoundError(relative_path)
    return json.loads(path.read_text(encoding="utf-8"))


def _first_runtime_json(context: Dict[str, Any], pattern: str) -> Dict[str, Any]:
    matches = _runtime_glob(context, pattern)
    if not matches:
        raise FileNotFoundError(pattern)
    return json.loads(matches[0].read_text(encoding="utf-8"))


def _artifact_format(path: Path) -> str:
    suffixes = [suffix.lstrip(".").lower() for suffix in path.suffixes]
    if suffixes[-2:] == ["json", "gz"]:
        return "json.gz"
    return suffixes[-1] if suffixes else ""


def _is_renderable_artifact(path: Path) -> bool:
    fmt = _artifact_format(path)
    if fmt in {"docx", "xlsx"}:
        import zipfile

        try:
            with zipfile.ZipFile(path) as package:
                names = set(package.namelist())
            if fmt == "docx":
                return "word/document.xml" in names
            return "xl/workbook.xml" in names and "xl/worksheets/sheet1.xml" in names
        except zipfile.BadZipFile:
            return False
    if fmt == "svg":
        text = path.read_text(encoding="utf-8", errors="ignore").lstrip()
        return text.startswith("<svg") or "<svg" in text[:200]
    if fmt == "dxf":
        text = path.read_text(encoding="utf-8", errors="ignore")
        return "SECTION" in text and "EOF" in text
    if fmt in {"json", "md", "py"}:
        return path.stat().st_size > 0
    return path.exists() and path.stat().st_size > 0


def _commonpath(root: Path, target: Path) -> str:
    import os

    return os.path.commonpath([str(root), str(target)])


def _artifact_record(path: Path, workspace: Path, file_format: str, artifact_type: str) -> Dict[str, Any]:
    path = path.resolve()
    workspace = workspace.resolve()
    exists = path.exists()
    return {
        "path": str(path),
        "relative_path": str(path.relative_to(workspace)) if exists and path.is_relative_to(workspace) else str(path),
        "format": file_format,
        "artifact_type": artifact_type,
        "exists": exists,
        "bytes": path.stat().st_size if exists else 0,
        "checksum": _file_checksum(path) if exists else "",
    }


def _workflow_artifacts(result: WorkflowDispatchResult, workspace: Path) -> List[Dict[str, Any]]:
    artifacts: List[Dict[str, Any]] = []
    for task_result in result.task_results:
        path = Path(task_result.metadata.get("target_path", ""))
        if path.exists():
            artifacts.append(_artifact_record(path, workspace, path.suffix.lstrip("."), "generated-target-file"))
    exports = result.metadata.get("deliverable_exports", {}) or {}
    for record in exports.get("deliverables", []) or []:
        path = Path(record.get("path", ""))
        if path.exists():
            artifacts.append(_artifact_record(path, workspace, record.get("format", ""), record.get("artifact_type", "")))
    return artifacts


def _validator_result(name: str, passed: bool, message: str) -> Dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "status": "passed" if passed else "failed",
        "message": message,
    }


def _lookup(data: Dict[str, Any], dotted_key: str) -> Any:
    current: Any = data
    for part in dotted_key.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _select_tasks(tasks: List[Dict[str, Any]], task_ids: set) -> List[Dict[str, Any]]:
    if not task_ids:
        return tasks
    selected = [task for task in tasks if task["instance_id"] in task_ids]
    missing = sorted(task_ids.difference(task["instance_id"] for task in selected))
    if missing:
        raise ValueError(f"unknown KH-Bench task id(s): {', '.join(missing)}")
    return selected


def _score_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(results)
    passed = sum(1 for result in results if result["status"] == "passed")
    failed = sum(1 for result in results if result["status"] == "failed")
    infra_error = sum(1 for result in results if result["status"] == "infra_error")
    invalid = sum(1 for result in results if result["status"] == "invalid")
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "invalid": invalid,
        "infra_error": infra_error,
        "pass_rate": round(passed / total, 4) if total else 0.0,
    }


def _first_failure_reason(*phases: Dict[str, Any]) -> str:
    for phase in phases:
        for check in phase.get("checks", []) or []:
            if not check.get("passed"):
                return check.get("message", "validator failed")
    return "unknown failure"


def _file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _pytest_failure_log() -> str:
    passing = "\n".join(f"tests/test_order.py::test_bulk_save[{index}] PASSED" for index in range(1, 220))
    return "\n".join([
        "============================= test session starts =============================",
        passing,
        "tests/test_invoice.py::test_total_rounding FAILED",
        "________________________________ test_total_rounding ________________________________",
        "test_invoice.py line 87",
        "AssertionError: assert 119999 == 120000",
        "E       assert 119999 == 120000",
        "=========================== short test summary info ===========================",
        "FAILED tests/test_invoice.py::test_total_rounding - AssertionError",
        "exit code: 1",
    ])


_TASKS: List[Dict[str, Any]] = [
    {
        "schema_version": TASK_SCHEMA_VERSION,
        "instance_id": "khbench-context-optimization-001",
        "title": "Preserve failing pytest facts while compressing noisy output",
        "category": "context-optimization",
        "difficulty": "standard",
        "human_verified": True,
        "skills": ["token-optimizer", "command-output-harness"],
        "problem_statement": "Compress a long pytest log without losing the failing test, file line, assertion, values, or exit code.",
        "base_workspace": {"files": [{"path": "logs/pytest.log", "content": _pytest_failure_log()}]},
        "pre_validation": [{"name": "optimized output absent before run", "type": "file_exists", "path": "reports/token_summary.json", "expect": "fail"}],
        "candidate_profile": "context_optimization",
        "expected_artifacts": ["reports/token_summary.json"],
        "fail_to_pass": [
            {"name": "optimizer report written", "type": "file_exists", "path": "reports/token_summary.json"},
            {
                "name": "failure facts preserved",
                "type": "json_file_field_contains_all",
                "path": "reports/token_summary.json",
                "field": "stdout",
                "values": ["test_total_rounding", "test_invoice.py line 87", "AssertionError", "119999 == 120000", "exit code: 1"],
            },
            {"name": "token savings above 80 percent", "type": "json_file_field_at_least", "path": "reports/token_summary.json", "field": "metadata.token_savings_ratio", "minimum": 0.8},
        ],
        "pass_to_pass": [
            {"name": "exit code preserved", "type": "json_file_field_equals", "path": "reports/token_summary.json", "field": "exit_code", "value": 1},
            {"name": "summary artifact written", "type": "file_exists", "path": "reports/token_summary.json"},
        ],
    },
    {
        "schema_version": TASK_SCHEMA_VERSION,
        "instance_id": "khbench-coding-workflow-001",
        "title": "Dispatch a local coding workflow with role and evidence gates",
        "category": "coding-workflow",
        "difficulty": "standard",
        "human_verified": True,
        "skills": ["parallel-orchestration-harness", "development-lifecycle-harness", "role-execution-audit-harness"],
        "problem_statement": "Run a local workflow that creates target files and proves role execution plus gate evidence.",
        "base_workspace": {"files": []},
        "pre_validation": [{"name": "target file absent before dispatch", "type": "file_exists", "path": "src/bench_app.py", "expect": "fail"}],
        "candidate_profile": "coding_workflow",
        "expected_artifacts": ["src/bench_app.py", "README.md"],
        "fail_to_pass": [
            {"name": "workflow result succeeded", "type": "json_file_field_equals", "path": "reports/workflow_result.json", "field": "success", "value": True},
            {"name": "target file generated", "type": "file_exists", "path": "src/bench_app.py"},
            {"name": "role audit passed", "type": "json_file_field_equals", "path": "reports/workflow_result.json", "field": "metadata.role_execution_audit.status", "value": "passed"},
        ],
        "pass_to_pass": [
            {"name": "generated content includes runner marker", "type": "file_contains", "path": "src/bench_app.py", "must_include": ["Generated by UAF LocalTaskRunner"]},
            {"name": "parallel role wave recorded", "type": "json_file_field_at_least", "path": "reports/workflow_result.json", "field": "metadata.role_orchestration.parallel_wave_count", "minimum": 1},
            {"name": "role artifacts written", "type": "runtime_glob_count", "pattern": "**/.uaf/artifacts/roles/*.md", "minimum": 11},
        ],
    },
    {
        "schema_version": TASK_SCHEMA_VERSION,
        "instance_id": "khbench-domain-deliverables-001",
        "title": "Export type-aware product design deliverables",
        "category": "domain-deliverables",
        "difficulty": "standard",
        "human_verified": True,
        "skills": ["domain-orchestration-harness", "artifact-render-qa-harness", "deliverable-template-quality-harness"],
        "problem_statement": "Create product-design deliverables from a compact spec and validate DOCX, XLSX, SVG, and DXF outputs.",
        "base_workspace": {"files": []},
        "pre_validation": [{"name": "deliverables absent before design stage", "type": "file_glob_count", "pattern": "docs/*", "minimum": 1, "expect": "fail"}],
        "candidate_profile": "domain_deliverables",
        "expected_artifacts": ["docs/*.docx", "docs/*.xlsx", "docs/*.svg", "docs/*.dxf"],
        "fail_to_pass": [
            {"name": "deliverable quality passed", "type": "json_file_field_equals", "path": "reports/deliverable_exports.json", "field": "quality.status", "value": "passed"},
            {"name": "all required formats exported", "type": "artifact_glob_formats", "pattern": "docs/*", "formats": ["docx", "xlsx", "svg", "dxf"]},
            {"name": "artifacts are renderable", "type": "renderable_artifacts", "pattern": "docs/*"},
        ],
        "pass_to_pass": [
            {"name": "export report written", "type": "file_exists", "path": "reports/deliverable_exports.json"},
            {"name": "deliverable count at least four", "type": "json_file_field_at_least", "path": "reports/deliverable_exports.json", "field": "deliverables", "minimum": 4},
        ],
    },
    {
        "schema_version": TASK_SCHEMA_VERSION,
        "instance_id": "khbench-side-regression-markdown-001",
        "title": "Preserve Markdown prose and embedded code fences from an LLM adapter",
        "category": "side-regression",
        "difficulty": "hard",
        "human_verified": True,
        "skills": ["adapter-contract-harness", "development-lifecycle-harness", "quality-gates-harness"],
        "problem_statement": "SIDE regression: README generation must not drop prose when an LLM response contains an embedded fenced code block.",
        "base_workspace": {"files": []},
        "pre_validation": [{"name": "README absent before generation", "type": "file_exists", "path": "README.md", "expect": "fail"}],
        "candidate_profile": "side_markdown_generation",
        "expected_artifacts": ["README.md", "reports/markdown_generation.json"],
        "fail_to_pass": [
            {"name": "markdown generation succeeded", "type": "json_file_field_equals", "path": "reports/markdown_generation.json", "field": "status", "value": "success"},
            {"name": "README written", "type": "file_exists", "path": "README.md"},
            {
                "name": "prose and code fence preserved",
                "type": "file_contains",
                "path": "README.md",
                "must_include": ["# Usage Guide", "This section must survive", "```python", "print('hello')"],
            },
        ],
        "pass_to_pass": [
            {"name": "adapter metadata recorded", "type": "json_file_field_equals", "path": "reports/markdown_generation.json", "field": "metadata.source", "value": "llm"},
            {"name": "target path recorded", "type": "json_file_field_contains_all", "path": "reports/markdown_generation.json", "field": "metadata.target_path", "values": ["README.md"]},
        ],
    },
    {
        "schema_version": TASK_SCHEMA_VERSION,
        "instance_id": "khbench-side-regression-product-spec-001",
        "title": "Carry compact product specs into SVG and DXF deliverables",
        "category": "side-regression",
        "difficulty": "hard",
        "human_verified": True,
        "skills": ["domain-orchestration-harness", "artifact-render-qa-harness", "deliverable-template-quality-harness"],
        "problem_statement": "SIDE regression: compact product specs such as 200x120, SUS304, and four M20 holes must flow into generated DOCX/XLSX/SVG/DXF deliverables.",
        "base_workspace": {"files": []},
        "pre_validation": [{"name": "SIDE product deliverables absent before run", "type": "file_glob_count", "pattern": "docs/*", "minimum": 1, "expect": "fail"}],
        "candidate_profile": "side_product_spec_deliverables",
        "expected_artifacts": ["docs/*.docx", "docs/*.xlsx", "docs/*.svg", "docs/*.dxf", "reports/side_product_spec_exports.json"],
        "fail_to_pass": [
            {"name": "SIDE export report written", "type": "file_exists", "path": "reports/side_product_spec_exports.json"},
            {"name": "SIDE deliverable quality passed", "type": "json_file_field_equals", "path": "reports/side_product_spec_exports.json", "field": "quality.status", "value": "passed"},
            {"name": "all required formats exported", "type": "artifact_glob_formats", "pattern": "docs/*", "formats": ["docx", "xlsx", "svg", "dxf"]},
        ],
        "pass_to_pass": [
            {
                "name": "drawing text preserves compact spec facts",
                "type": "file_glob_text_contains_all",
                "pattern": "docs/*",
                "values": ["200", "120", "SUS304", "4 x M20", "4xM20"],
            },
            {"name": "artifacts are renderable", "type": "renderable_artifacts", "pattern": "docs/*"},
        ],
    },
    {
        "schema_version": TASK_SCHEMA_VERSION,
        "instance_id": "khbench-role-orchestration-001",
        "title": "Run full role DAG with parallel waves and artifacts",
        "category": "role-orchestration",
        "difficulty": "standard",
        "human_verified": True,
        "skills": ["orchestration-role-graph", "host-agent-orchestration", "role-execution-audit-harness"],
        "problem_statement": "Run every default role, prove parallel waves occurred, and audit role artifacts.",
        "base_workspace": {"files": []},
        "pre_validation": [{"name": "role audit absent before run", "type": "file_exists", "path": "reports/role_orchestration.json", "expect": "fail"}],
        "candidate_profile": "role_orchestration",
        "expected_artifacts": ["runtime role artifact markdown files"],
        "fail_to_pass": [
            {"name": "role audit passed", "type": "json_file_field_equals", "path": "reports/role_orchestration.json", "field": "audit.status", "value": "passed"},
            {"name": "parallel waves at least two", "type": "json_file_field_at_least", "path": "reports/role_orchestration.json", "field": "summary.parallel_wave_count", "minimum": 2},
        ],
        "pass_to_pass": [
            {"name": "all default roles executed", "type": "json_file_field_at_least", "path": "reports/role_orchestration.json", "field": "summary.role_count", "minimum": 12},
            {"name": "role artifacts written", "type": "runtime_glob_count", "pattern": "**/.uaf/artifacts/roles/*.md", "minimum": 12},
        ],
    },
    {
        "schema_version": TASK_SCHEMA_VERSION,
        "instance_id": "khbench-state-snapshot-001",
        "title": "Create and restore one work-level snapshot bundle",
        "category": "state-snapshot",
        "difficulty": "smoke",
        "human_verified": True,
        "skills": ["snapshot-state-harness", "guard-policy-harness"],
        "problem_statement": "Snapshot multiple project files as one work bundle, mutate them, and restore the original contents.",
        "base_workspace": {
            "files": [
                {"path": "src/app.py", "content": "VALUE = 'original'\n"},
                {"path": "README.md", "content": "# Original\n"},
            ]
        },
        "pre_validation": [{"name": "snapshot not restored before run", "type": "file_exists", "path": "reports/snapshot_result.json", "expect": "fail"}],
        "candidate_profile": "snapshot_state",
        "expected_artifacts": ["thread-scoped snapshot bundle"],
        "fail_to_pass": [
            {"name": "snapshot restored", "type": "json_file_field_equals", "path": "reports/snapshot_result.json", "field": "restored.status", "value": "restored"},
            {"name": "source restored", "type": "file_contains", "path": "src/app.py", "must_include": ["VALUE = 'original'"]},
        ],
        "pass_to_pass": [
            {"name": "only one work bundle is recorded", "type": "snapshot_log_bundle_count", "minimum": 1},
            {"name": "snapshot bundle artifact exists", "type": "runtime_glob_count", "pattern": "**/.snapshots/*.json.gz", "minimum": 1},
        ],
    },
    {
        "schema_version": TASK_SCHEMA_VERSION,
        "instance_id": "khbench-goal-memory-001",
        "title": "Persist goal, scoped memory, and resume handoff",
        "category": "goal-memory",
        "difficulty": "smoke",
        "human_verified": True,
        "skills": ["goal-state-harness", "memory-state-harness", "context-state-harness"],
        "problem_statement": "Store a completed goal, one scoped memory record, and a resumable handoff snapshot without leaking secrets.",
        "base_workspace": {"files": []},
        "pre_validation": [{"name": "goal state absent before run", "type": "runtime_glob_count", "pattern": "**/.uaf/state/current_goal.json", "minimum": 1, "expect": "fail"}],
        "candidate_profile": "goal_memory",
        "expected_artifacts": ["current_goal.json", "project_memory.json", "resume_handoff.json", "resume_handoff.md"],
        "fail_to_pass": [
            {"name": "goal state written", "type": "runtime_glob_count", "pattern": "**/.uaf/state/current_goal.json", "minimum": 1},
            {"name": "goal state complete", "type": "json_runtime_glob_field_equals", "pattern": "**/.uaf/state/current_goal.json", "field": "status", "value": "complete"},
            {"name": "memory record persisted", "type": "memory_file_records_at_least", "path": ".khbench-memory/project_memory.json", "minimum": 1},
        ],
        "pass_to_pass": [
            {"name": "resume handoff complete", "type": "json_runtime_glob_field_equals", "pattern": "**/.uaf/state/resume_handoff.json", "field": "status", "value": "complete"},
            {"name": "memory file exists", "type": "file_exists", "path": ".khbench-memory/project_memory.json"},
        ],
    },
]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run KH-Bench Verified local benchmark tasks.")
    parser.add_argument("--output-dir", default="", help="Directory for benchmark run outputs.")
    parser.add_argument("--task-id", action="append", default=[], help="Run only a specific task id; repeatable.")
    parser.add_argument("--summary", action="store_true", help="Print only the top-level summary JSON.")
    args = parser.parse_args(argv)
    report = run_kh_bench_verified(
        output_root=Path(args.output_dir) if args.output_dir else None,
        task_ids=args.task_id or None,
    )
    payload = {
        "benchmark": report["benchmark"],
        "run_id": report["run_id"],
        "summary": report["summary"],
        "unresolved": report["unresolved"],
    } if args.summary else report
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if report["resolved_count"] == report["task_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
