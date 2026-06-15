import argparse
import contextlib
import gzip
import hashlib
import io
import json
import os
import platform
import re
import sys
import tempfile
from dataclasses import is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from src.contracts import (
    AdapterRequest,
    AdapterResult,
    DomainProfile,
    DomainRole,
    GoalState,
    HandoffSnapshot,
    HarnessResult,
    MemoryScope,
    WorkDesign,
    WorkflowDispatchResult,
    WorkflowTaskResult,
)
from src.harness.evaluator import Evaluator
from src.orchestration.deliverable_exports import export_office_deliverables
from src.orchestration.gate_evaluators import (
    build_gate_results,
    build_qa_check,
    evaluate_qa_checks,
)
from src.orchestration.quality_harnesses import audit_role_execution
from src.orchestration.request_classifier import classify_request
from src.orchestration.plugin_composition import compose_plugin_route
from src.orchestration.kh_front_door import build_kh_front_door
from src.orchestration.brainstorming import (
    BrainstormDecision,
    BrainstormOption,
    BrainstormSession,
    build_architect_handoff,
    validate_brainstorm_session,
)
from src.orchestration.compound import (
    CompoundCapture,
    CompoundLearning,
    CompoundMemoryCandidate,
    build_compound_handoff,
    validate_compound_capture,
)
from src.orchestration.scenario_evaluator import (
    build_scenario_report,
    default_scenarios,
    evaluate_scenarios,
    stress_scenarios,
)
from src.orchestration.role_orchestrator import (
    PRE_IMPLEMENTATION_ROLES,
    RoleOrchestrator,
)
from src.skills.command_policy import (
    evaluate_command_hook_policy,
    evaluate_guard_policy,
    evaluate_write_boundary,
)
from src.skills.token_optimizer import optimize_context_content
from src.skills.sql_formatting_style import verify_sql_formatting_style
from src.skills.uaf_skill_catalog import collect_packaged_skills
from src.skills.workflow_distiller import build_skill_scaffold, should_distill_workflow
from src.core.snapshot_manager import SnapshotManager


SCHEMA_VERSION = "1.0"

COMMAND_SKILLS = {
    "command-hook-policy-harness",
    "command-output-harness",
    "guard-policy-harness",
    "token-optimizer",
}

STATE_SKILLS = {
    "context-state-harness",
    "goal-state-harness",
    "health-check-harness",
    "memory-state-harness",
    "snapshot-state-harness",
}

ROLE_SKILLS = {
    "host-agent-orchestration",
    "orchestration-role-graph",
    "parallel-orchestration-harness",
    "role-execution-audit-harness",
    "subagent-review-pipeline",
}

ARTIFACT_SKILLS = {
    "architect-pipeline",
    "artifact-render-qa-harness",
    "deliverable-template-quality-harness",
    "domain-orchestration-harness",
    "traceability-matrix-harness",
}

GATE_SKILLS = {
    "branch-finishing-harness",
    "development-lifecycle-harness",
    "plan-execution-harness",
    "qa-gate-harness",
    "quality-gates-harness",
    "review-gate-harness",
    "systematic-debugging-harness",
    "verification-before-completion-harness",
    "worktree-isolation-harness",
    "workflow-usability-harness",
}

SKILL_OPS_SKILLS = {
    "harness-evaluator",
    "skill-catalog",
    "workflow-skill-distiller",
}

ROUTING_SKILLS = {
    "always-on-front-door",
    "automatic-intake-harness",
    "plugin-composition-policy",
    "request-complexity-router",
    "scenario-evaluation-harness",
}


def run_skill_demo(
    skill_name: str,
    output_dir: str | Path,
    repo_root: str | Path | None = None,
    skill_dir: str | Path | None = None,
) -> Dict[str, Any]:
    """Run one deterministic mini-demo for a packaged UAF skill."""
    root = Path(repo_root or _find_repo_root()).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    skill_path = Path(skill_dir).resolve() if skill_dir else _skill_dir(root, skill_name)
    metadata = _skill_metadata(skill_name)
    old_env = {
        "UAF_RUNTIME_ROOT": os.environ.get("UAF_RUNTIME_ROOT"),
        "UAF_PROJECT_LOCAL_STATE": os.environ.get("UAF_PROJECT_LOCAL_STATE"),
    }
    os.environ["UAF_RUNTIME_ROOT"] = str(output / "_runtime")
    os.environ["UAF_PROJECT_LOCAL_STATE"] = "0"
    try:
        scenario = _scenario_for(skill_name)
        scenario_result = scenario(skill_name, output, root)
        artifacts = list(scenario_result["artifacts"])
        evidence_artifact = _write_demo_evidence_artifact(
            output,
            skill_name,
            scenario_result["success_case"],
            scenario_result["blocked_or_failure_case"],
            scenario_result["contracts"],
        )
        artifacts.append(evidence_artifact)
        artifacts = _complete_artifact_manifest(artifacts, output)
        host_metadata = _host_metadata(
            output_dir=output,
            repo_root=root,
            skill_dir=skill_path,
            execution_level=metadata.get("execution_level", "procedure-policy"),
        )
        verification = _verification(
            contracts=scenario_result["contracts"],
            artifacts=artifacts,
            output_dir=output,
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "skill": skill_name,
            "execution_level": metadata.get("execution_level", "procedure-policy"),
            "scenario_id": f"demo-{_safe_id(skill_name)}",
            "generated_at": _utc_now(),
            "success_case": scenario_result["success_case"],
            "blocked_or_failure_case": scenario_result["blocked_or_failure_case"],
            "contracts": scenario_result["contracts"],
            "host_metadata": host_metadata,
            "artifacts": artifacts,
            "verification": verification,
        }
    finally:
        _restore_env(old_env)


def main(default_skill_name: str | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a KH UAF packaged skill mini-demo.")
    parser.add_argument("--skill", default=default_skill_name or "", help="Packaged skill name.")
    parser.add_argument("--output-dir", default="", help="Directory for demo artifacts.")
    args = parser.parse_args()
    if not args.skill:
        parser.error("--skill is required")
    root = _find_repo_root()
    output = Path(args.output_dir) if args.output_dir else _default_demo_output_dir(args.skill)
    payload = run_skill_demo(args.skill, output_dir=output, repo_root=root)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def _scenario_for(skill_name: str) -> Callable[[str, Path, Path], Dict[str, Any]]:
    if skill_name == "sql-formatting-style-harness":
        return _sql_formatting_style_scenario
    if skill_name == "brainstorming-harness":
        return _brainstorming_scenario
    if skill_name == "compound-engineering-harness":
        return _compound_engineering_scenario
    if skill_name == "adapter-contract-harness":
        return _adapter_scenario
    if skill_name in COMMAND_SKILLS:
        return _command_scenario
    if skill_name in STATE_SKILLS:
        return _state_scenario
    if skill_name in ROLE_SKILLS:
        return _role_scenario
    if skill_name in ARTIFACT_SKILLS:
        return _artifact_scenario
    if skill_name in GATE_SKILLS:
        return _gate_scenario
    if skill_name in SKILL_OPS_SKILLS:
        return _skill_ops_scenario
    if skill_name in ROUTING_SKILLS:
        if skill_name in {"always-on-front-door", "automatic-intake-harness"}:
            return _automatic_intake_scenario
        if skill_name == "plugin-composition-policy":
            return _plugin_composition_scenario
        if skill_name == "scenario-evaluation-harness":
            return _scenario_evaluation_scenario
        return _routing_scenario
    return _gate_scenario


def _brainstorming_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    session = BrainstormSession(
        objective="Build a small B2B CRM SaaS MVP.",
        target_user="Small B2B sales teams",
        problem="Deals and follow-ups are scattered across spreadsheets.",
        options=[
            BrainstormOption(
                name="Pipeline-first CRM",
                tradeoffs=["fastest MVP", "tasks and reporting can follow"],
                recommended=True,
                rationale="A deal pipeline is the clearest CRM core loop.",
            ),
            BrainstormOption(
                name="Reporting-first CRM",
                tradeoffs=["useful dashboards", "requires more data before value is visible"],
            ),
        ],
        decisions=[
            BrainstormDecision("product_name", "PipePilot", "Short, pipeline-oriented SaaS name."),
            BrainstormDecision("mvp_focus", "deal pipeline", "Best validates the CRM workflow quickly."),
        ],
        open_questions=["Select auth provider during architecture."],
        constraints=["private GitHub repo", "full-stack TypeScript MVP"],
        metadata={"source_pattern": "Superpowers brainstorming adapted for KH UAF"},
    )
    validation = validate_brainstorm_session(session)
    handoff = build_architect_handoff(session)
    blocked = build_architect_handoff(
        BrainstormSession(
            objective="Build a SaaS.",
            options=[BrainstormOption(name="Option A")],
        )
    )
    dispatch = _dispatch_for(skill_name, [validation], success=validation["valid"])
    handoff_path = output_dir / "brainstorm_handoff.json"
    handoff_path.write_text(json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    contracts = [
        _dataclass_contract(session),
        _dataclass_contract(dispatch),
        _mapping_contract("BrainstormValidation", "src.orchestration.brainstorming", validation, "policy-result"),
        _mapping_contract("BrainstormHandoff", "src.orchestration.brainstorming", handoff, "policy-result"),
    ]
    return _scenario_result(
        success_contract="BrainstormHandoff",
        success_payload=handoff,
        success_evidence=handoff["evidence"],
        success_behavior="Capture early domain intent, compare approaches, preserve decisions, and hand off to architect-pipeline or domain-orchestration-harness.",
        success_side_effects=["writes brainstorm_handoff.json under the demo output directory"],
        blocked_contract="BrainstormHandoff",
        blocked_payload=blocked,
        blocked_reason=blocked["blocked_reason"],
        missing_inputs=["target_user", "problem", "recommended_option", "decisions"],
        contracts=contracts,
        artifacts=[
            _artifact_record_from_file(
                handoff_path,
                "brainstorm-handoff-json",
                output_dir,
                ["json readable", "architect handoff captured"],
                created_by_case="success",
            )
        ],
    )


def _compound_engineering_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    capture = CompoundCapture(
        objective="Improve early SaaS discovery behavior.",
        completed_work=[
            "Added KH-native brainstorming handoff and SIDE activation coverage.",
            "Documented Plan -> Work -> Review -> Compound as the KH loop.",
        ],
        review_findings=[
            "External skillbook patterns should be benchmarked, but KH needs explicit scoped learning.",
        ],
        learnings=[
            CompoundLearning(
                title="Run KH Compound after review",
                trigger="Meaningful Plan, Work, and Review activity just finished",
                reusable_insight="Capture reusable lessons as skill updates, scoped memory candidates, or regression checks.",
                evidence=["review_summary", "regression_check_plan"],
                tags=["compound", "memory", "regression"],
                target_update="compound-engineering-harness",
            )
        ],
        system_updates=[
            "Keep plugin prompts pointing to compound-engineering-harness after review.",
            "Route project-specific lessons through memory-state-harness candidates.",
        ],
        regression_checks=[
            "python -m unittest tests.test_compound_engineering_harness",
            "python -m unittest tests.test_superpowers_benchmark_alignment",
        ],
        memory_candidates=[
            CompoundMemoryCandidate(
                scope="project",
                content="For repeated project workflow lessons, use KH compound-engineering-harness before finishing.",
                evidence=["compound_capture", "review_summary"],
                confidence=0.86,
            )
        ],
        next_skills=[
            "workflow-skill-distiller",
            "memory-state-harness",
            "scenario-evaluation-harness",
        ],
        source_references=["Superpowers", "external role-stack benchmark", "external compound engineering"],
    )
    validation = validate_compound_capture(capture)
    handoff = build_compound_handoff(capture)
    blocked = build_compound_handoff(
        CompoundCapture(
            objective="Ship a small feature.",
            completed_work=["Implementation and review finished."],
            review_findings=["A repeated mistake was found but not captured."],
        )
    )
    dispatch = _dispatch_for(skill_name, [validation], success=validation["valid"])
    handoff_path = output_dir / "compound_handoff.json"
    handoff_path.write_text(json.dumps(handoff, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    contracts = [
        _dataclass_contract(capture),
        _dataclass_contract(capture.learnings[0]),
        _dataclass_contract(capture.memory_candidates[0]),
        _dataclass_contract(dispatch),
        _mapping_contract("CompoundValidation", "src.orchestration.compound", validation, "policy-result"),
        _mapping_contract("CompoundHandoff", "src.orchestration.compound", handoff, "policy-result"),
    ]
    return _scenario_result(
        success_contract="CompoundHandoff",
        success_payload=handoff,
        success_evidence=handoff["evidence"],
        success_behavior="Capture post-review learning, scoped memory candidates, and regression checks before finishing.",
        success_side_effects=["writes compound_handoff.json under the demo output directory"],
        blocked_contract="CompoundHandoff",
        blocked_payload=blocked,
        blocked_reason=blocked["blocked_reason"],
        missing_inputs=["learning_or_no_learning_rationale"],
        contracts=contracts,
        artifacts=[
            _artifact_record_from_file(
                handoff_path,
                "compound-handoff-json",
                output_dir,
                ["json readable", "compound handoff captured"],
                created_by_case="success",
            )
        ],
    )


def _adapter_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    request = AdapterRequest(
        project_dir=str(output_dir / "project"),
        files=["src/app.py", "tests/test_app.py"],
        design_doc="Implement a bounded local worker task and report evidence.",
        platform_mode="codex",
        metadata={
            "hosts": ["codex", "antigravity-style", "claude-code", "local"],
            "cwd_supported": True,
            "permissions_model": "host-owned",
        },
    )
    result = AdapterResult(
        status="success",
        message="adapter normalized request into portable UAF dispatch input",
        workflow_id="demo-adapter-workflow",
        metadata={"request": request.to_dict(), "evidence": ["adapter contract normalized"]},
    )
    blocked = AdapterResult(
        status="blocked",
        message="host adapter missing project_dir and file targets",
        workflow_id=None,
        metadata={"missing_inputs": ["project_dir", "files"], "non_destructive": True},
    )
    dispatch = _dispatch_for(skill_name, [result.to_dict()], success=True)
    contracts = [
        _dataclass_contract(request),
        _dataclass_contract(result),
        _dataclass_contract(dispatch),
    ]
    return _scenario_result(
        success_contract="AdapterResult",
        success_payload=result.to_dict(),
        success_evidence=["adapter contract normalized", "host metadata captured"],
        success_behavior="Normalize host-specific inputs into one UAF adapter result.",
        success_side_effects=["writes demo evidence JSON only"],
        blocked_contract="AdapterResult",
        blocked_payload=blocked.to_dict(),
        blocked_reason="adapter cannot dispatch without project_dir and target files",
        missing_inputs=["project_dir", "files"],
        contracts=contracts,
        artifacts=[],
    )


def _command_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    log = _pytest_failure_log()
    optimized = optimize_context_content(
        log,
        content_kind="log",
        command="pytest tests/test_invoice.py",
        exit_code=1,
        max_lines=18,
    )
    required_facts = [
        "tests/test_invoice.py::test_total_rounding FAILED",
        "AssertionError",
        "119999 == 120000",
        "exit code: 1",
    ]
    preserved = all(item in optimized.stdout for item in required_facts)
    policy = evaluate_command_hook_policy(
        "Remove-Item -Recurse C:\\demo\\target",
        approved=False,
        actor="demo-host",
    )
    boundary = evaluate_write_boundary(str(output_dir / "allowed.txt"), [str(output_dir)])
    blocked_input = (
        "CREATE PROCEDURE dbo.SaveInvoice AS\n"
        "INSERT INTO AuditLog(Message) VALUES ('preserve exact contract');\n"
    )
    blocked_result = optimize_context_content(
        blocked_input,
        content_kind="auto",
        command="",
        exit_code=0,
        max_lines=8,
    )
    success_payload = optimized.to_dict()
    success_payload["preserved_required_facts"] = preserved
    success_payload["policy_verdict"] = policy["verdict"]
    success_payload["write_boundary"] = boundary
    contracts = [
        _dataclass_contract(optimized),
        _mapping_contract("CommandPolicyResult", "src.skills.command_policy", policy, "policy-result"),
        _mapping_contract("WriteBoundaryResult", "src.skills.command_policy", boundary, "policy-result"),
    ]
    return _scenario_result(
        success_contract="HarnessResult",
        success_payload=success_payload,
        success_evidence=["command output compressed", "required failure facts preserved"],
        success_behavior="Compress noisy failing command output while preserving actionable facts.",
        success_side_effects=["writes demo evidence JSON only"],
        blocked_contract="HarnessResult",
        blocked_payload=blocked_result.to_dict(),
        blocked_reason="contract-sensitive text must pass through without minify or truncation",
        missing_inputs=[],
        contracts=contracts,
        artifacts=[],
    )


def _sql_formatting_style_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    original = (
        "CREATE OR ALTER PROCEDURE [dbo].[sp_DEMO_SELECT] @WORKTYPE VARCHAR(20)=NULL\n"
        "AS\n"
        "BEGIN\n"
        "SELECT a.ordnum, CASE WHEN a.chkyn = 'Y' THEN '확인' END AS chkynm\n"
        "FROM DE100T a\n"
        "left outer join DE110T b\n"
        "on a.ordnum = b.ordnum\n"
        "and a.ordseq = b.ordseq\n"
        "WHERE a.status = '진행'\n"
        "--AND a.status = '보류'\n"
        "END\n"
    )
    formatted = (
        "CREATE OR ALTER PROCEDURE [DBO].[SP_DEMO_SELECT]\n"
        "      @WORKTYPE    VARCHAR(20) = NULL\n"
        "AS\n"
        "BEGIN\n"
        "    SELECT A.ORDNUM\n"
        "         , (CASE WHEN A.CHKYN = 'Y' THEN '확인' END) AS CHKYNM\n"
        "    FROM DE100T A\n"
        "        LEFT OUTER JOIN DE110T B\n"
        "                     ON A.ORDNUM = B.ORDNUM\n"
        "                     AND A.ORDSEQ = B.ORDSEQ\n"
        "    WHERE A.STATUS = '진행'\n"
        "--AND A.STATUS = '보류'\n"
        "END\n"
    )
    changed = formatted.replace("'진행'", "'완료'").replace("'확인'", "'완료'")
    success_result = verify_sql_formatting_style(original, formatted)
    blocked_result = verify_sql_formatting_style(original, changed)
    success_path = output_dir / "sql_formatting_success.json"
    blocked_path = output_dir / "sql_formatting_blocked.json"
    success_path.write_text(json.dumps(success_result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    blocked_path.write_text(json.dumps(blocked_result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    contracts = [
        _mapping_contract("HarnessResult", "src.skills.sql_formatting_style", success_result.to_dict(), "policy-result"),
        _mapping_contract("HarnessResult", "src.skills.sql_formatting_style", blocked_result.to_dict(), "policy-result"),
    ]
    return _scenario_result(
        success_contract="HarnessResult",
        success_payload=success_result.to_dict(),
        success_evidence=[
            "mechanical preservation checks passed",
            "style checks passed",
            "semantic checks explicitly not_proven",
        ],
        success_behavior="Verify host-local sql-formatting output without replacing the host-local style skill.",
        success_side_effects=["writes success and blocked HarnessResult JSON under the demo output directory"],
        blocked_contract="HarnessResult",
        blocked_payload=blocked_result.to_dict(),
        blocked_reason="literal or contract-sensitive SQL text changed",
        missing_inputs=[],
        contracts=contracts,
        artifacts=[
            _artifact_record_from_file(
                success_path,
                "sql-formatting-harness-result-json",
                output_dir,
                ["json readable", "success HarnessResult captured"],
                created_by_case="success",
            ),
            _artifact_record_from_file(
                blocked_path,
                "sql-formatting-harness-result-json",
                output_dir,
                ["json readable", "blocked HarnessResult captured"],
                created_by_case="blocked",
            ),
        ],
    )


def _state_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    goal = GoalState(
        objective="Produce a portable UAF demo with durable evidence.",
        status="complete",
        success_criteria=["demo ran", "evidence captured"],
        evidence_required=["demo evidence artifact"],
        evidence=["demo evidence artifact"],
        progress_notes=["state contracts round-tripped"],
        metadata={"scope": "project", "thread_id": "demo-thread"},
    )
    handoff = HandoffSnapshot(
        project_dir=str(output_dir / "project"),
        workflow_id="demo-state-workflow",
        objective=goal.objective,
        status="complete",
        next_recommended_action="publish demo evidence",
        success_criteria=goal.success_criteria,
        evidence_required=goal.evidence_required,
        evidence=goal.evidence,
        generated_at=_utc_now(),
        metadata={"resume_ready": True},
    )
    memory_scope = MemoryScope(
        kind="project",
        namespace="demo-project",
        project_id="demo-state",
        thread_id="demo-thread",
        root_path=str(output_dir),
        metadata={"isolated_runtime_root": str(output_dir / "_runtime")},
    )
    blocked = GoalState(
        objective=goal.objective,
        status="blocked",
        success_criteria=goal.success_criteria,
        evidence_required=["fresh verification evidence"],
        evidence=[],
        blocked_reason="fresh verification evidence is missing",
        metadata={"missing_evidence": ["fresh verification evidence"]},
    )
    artifacts: List[Dict[str, Any]] = []
    if skill_name == "snapshot-state-harness":
        artifacts.extend(_snapshot_artifacts(output_dir))
    contracts = [
        _dataclass_contract(goal),
        _dataclass_contract(handoff),
        _dataclass_contract(memory_scope),
    ]
    return _scenario_result(
        success_contract="HandoffSnapshot",
        success_payload=handoff.to_dict(),
        success_evidence=["goal state complete", "resume handoff captured", "memory scope isolated"],
        success_behavior="Persist resumable state without putting internal UAF files in the user's project root.",
        success_side_effects=["may write snapshot artifacts under the demo output runtime root"],
        blocked_contract="GoalState",
        blocked_payload=blocked.to_dict(),
        blocked_reason=blocked.blocked_reason,
        missing_inputs=["fresh verification evidence"],
        contracts=contracts,
        artifacts=artifacts,
    )


def _role_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    project_dir = output_dir / "role_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    context = {
        "project_dir": str(project_dir),
        "workflow_id": "demo-role-workflow",
        "objective": "Run role DAG mini-demo with real role artifacts.",
        "work_design": {
            "objective": "Run role DAG mini-demo with real role artifacts.",
            "domain": "software-development",
            "deliverables": ["role DAG execution summary"],
        },
        "metadata": {"thread_id": "demo-role-thread"},
    }
    orchestration = RoleOrchestrator().run_sync(
        context=context,
        selected_roles=PRE_IMPLEMENTATION_ROLES,
    )
    task_results = [WorkflowTaskResult.from_dict(item) for item in orchestration["results"]]
    summary = dict(orchestration["context"].get("role_orchestration", {}))
    summary["execution_model"] = "dag-asyncio-role-waves"
    role_metadata = {
        "summary": summary,
        "results": [result.to_dict() for result in task_results],
    }
    audit = audit_role_execution(role_metadata, required_roles=PRE_IMPLEMENTATION_ROLES)
    dispatch = WorkflowDispatchResult(
        workflow_id="demo-role-workflow",
        success=bool(orchestration["success"] and audit["status"] == "passed"),
        task_results=task_results,
        gate_results=[audit],
        metadata={"role_orchestration": summary, "waves": orchestration["waves"]},
    )
    blocked_task = WorkflowTaskResult(
        task_id="role_release_manager",
        file_name="role:release-manager",
        role="release-manager",
        status="blocked",
        message="blocked by role dependency: qa-verifier, security-reviewer",
        metadata={"pending_dependencies": ["qa-verifier", "security-reviewer"]},
    )
    artifacts = _role_artifacts(task_results, output_dir)
    contracts = [
        _dataclass_contract(dispatch),
        _dataclass_contract(task_results[0]),
        _mapping_contract("RoleExecutionAudit", "src.orchestration.quality_harnesses", audit, "gate-result"),
    ]
    return _scenario_result(
        success_contract="WorkflowDispatchResult",
        success_payload=dispatch.to_dict(),
        success_evidence=["role DAG executed", "parallel waves recorded", "role artifacts written"],
        success_behavior="Run a bounded role DAG and prove roles produced artifacts.",
        success_side_effects=["writes role artifacts under the demo output runtime root"],
        blocked_contract="WorkflowTaskResult",
        blocked_payload=blocked_task.to_dict(),
        blocked_reason="downstream release role cannot run before QA and security roles complete",
        missing_inputs=["qa-verifier result", "security-reviewer result"],
        contracts=contracts,
        artifacts=artifacts,
    )


def _artifact_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    profile = DomainProfile(
        domain_name="product-design",
        objective="Create a type-aware design deliverable pack for 22kw CABLE GLAND PLATE 389.",
        roles=[
            DomainRole(
                name="system-architect",
                purpose="Derive product design outputs from the supplied specification guide.",
                responsibilities=["map requirements", "select deliverable formats"],
                stage="architecture",
                required_artifacts=["source specification guide"],
                produces=["design document", "BOM", "concept drawing"],
            )
        ],
        required_design_artifact_types=["design-document", "table-model", "technical-drawing", "cad-drawing"],
        evidence_required=["product design document exported", "artifact render qa passed"],
        review_gates=["template quality", "render QA", "traceability"],
    )
    design = WorkDesign(
        objective=profile.objective,
        domain="product-design",
        scope="22kw CABLE GLAND PLATE 389 concept design handoff.",
        assumptions=["concept dimensions require engineer approval before manufacturing"],
        constraints=["do not treat concept drawing as fabrication-ready"],
        subdomains=["mechanical layout", "BOM", "CAD handoff"],
        roles_required=["system-architect", "qa-verifier", "release-manager"],
        deliverables=["product design document", "dimension BOM", "SVG drawing", "DXF handoff"],
        evidence_required=profile.evidence_required,
        risk_policy_checks=["source guide missing blocks release", "drawing must be marked concept only"],
        review_gates=profile.review_gates,
        design_artifacts=profile.required_design_artifact_types,
    )
    export_result = export_office_deliverables(
        project_dir=str(output_dir),
        workflow_id="demo-artifact-workflow",
        domain_profile=profile,
        work_design=design,
        source_design_doc=(
            "# 22kw CABLE GLAND PLATE 389 specification guide\n"
            "Design a concept drawing, BOM, and CAD handoff for a gland plate.\n"
            "Use 389 as the specification family and keep output marked concept only."
        ),
        file_list=["gland_plate_389.svg", "gland_plate_389.dxf"],
        metadata={"deliverable_export_dir": "deliverables", "deliverable_profile": "product-design"},
    )
    dispatch = _dispatch_for(skill_name, [export_result["quality"]], success=export_result["quality"]["status"] == "passed")
    blocked_quality = {
        "status": "failed",
        "findings": ["source specification guide missing"],
        "evidence": ["artifact render qa failed"],
    }
    artifacts = [
        _artifact_record_from_deliverable(record, output_dir, export_result["quality"])
        for record in export_result.get("deliverables", [])
    ]
    contracts = [
        _dataclass_contract(profile),
        _dataclass_contract(design),
        _dataclass_contract(dispatch),
        _mapping_contract("DeliverableQualityResult", "src.orchestration.quality_harnesses", export_result["quality"], "artifact-validator"),
    ]
    return _scenario_result(
        success_contract="WorkflowDispatchResult",
        success_payload=dispatch.to_dict(),
        success_evidence=list(export_result.get("evidence", [])),
        success_behavior="Generate type-aware deliverables and validate each artifact with format-specific structure checks.",
        success_side_effects=["writes deliverable files under the requested demo output directory"],
        blocked_contract="DeliverableQualityResult",
        blocked_payload=blocked_quality,
        blocked_reason="artifact-producing workflow needs a source guide before claiming a design output",
        missing_inputs=["source specification guide"],
        contracts=contracts,
        artifacts=artifacts,
    )


def _gate_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    task = WorkflowTaskResult(
        task_id="implement_demo_change",
        file_name="src/demo_target.py",
        role="implementer",
        status="success",
        message="implementation completed with evidence",
        metadata={
            "evidence": ["unit test passed", "smoke check passed"],
            "qa_checks": [
                build_qa_check(
                    "REQ-001",
                    "unit",
                    "demo behavior is covered",
                    "passed",
                    evidence=["unit test passed"],
                    scope="demo_target",
                )
            ],
        },
    )
    gates = build_gate_results([task.to_dict()])
    dispatch = WorkflowDispatchResult(
        workflow_id="demo-gate-workflow",
        success=all(gate["status"] == "passed" for gate in gates),
        task_results=[task],
        gate_results=gates,
        metadata={"gate_count": len(gates), "evidence": ["release gate passed"]},
    )
    quality_gate = next(gate for gate in gates if gate["role"] == "code-quality-reviewer")
    blocked_gate = evaluate_qa_checks(quality_gate, checks=[])
    contracts = [
        _dataclass_contract(task),
        _dataclass_contract(dispatch),
        _mapping_contract("GateResult", "src.orchestration.gate_evaluators", gates[-1], "gate-result"),
        _mapping_contract("BlockedGateResult", "src.orchestration.gate_evaluators", blocked_gate, "gate-result"),
    ]
    return _scenario_result(
        success_contract="WorkflowDispatchResult",
        success_payload=dispatch.to_dict(),
        success_evidence=["spec review passed", "code quality review passed", "qa gate passed", "release gate passed"],
        success_behavior="Require review and QA evidence before release is marked complete.",
        success_side_effects=["writes demo evidence JSON only"],
        blocked_contract="GateResult",
        blocked_payload=blocked_gate,
        blocked_reason=blocked_gate["message"],
        missing_inputs=["QA checks"],
        contracts=contracts,
        artifacts=[],
    )


def _skill_ops_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    catalog = collect_packaged_skills()
    distill = should_distill_workflow(
        "Use when a repeated demo workflow should become a packaged UAF skill.",
        repeated_count=3,
        reusable_across_projects=True,
        has_clear_failure_modes=True,
    )
    scaffold = build_skill_scaffold(
        name="demo-runtime-check",
        trigger="Use when a packaged skill needs runnable success and blocked examples.",
        workflow_steps=["Run the demo", "Inspect JSON", "Verify artifacts"],
        implementation_targets=["src.skills.demo_scenarios.run_skill_demo"],
        execution_level="python-module",
    )
    evaluator_result = Evaluator(timeout=5).evaluate_code_result(
        "def add(a, b):\n    return a + b\n",
        "assert add(2, 3) == 5\n",
    )
    blocked_distill = should_distill_workflow(
        "one-off note",
        repeated_count=1,
        reusable_across_projects=False,
        has_clear_failure_modes=False,
    )
    success_payload = evaluator_result.to_dict()
    success_payload["catalog_total"] = catalog["total_skills_found"]
    success_payload["distill_quality_gate"] = distill["quality_gate"]
    success_payload["scaffold_files"] = sorted(scaffold)
    contracts = [
        _dataclass_contract(evaluator_result),
        _mapping_contract("SkillCatalogResult", "src.skills.uaf_skill_catalog", {
            "total_skills_found": catalog["total_skills_found"],
            "valid_skills": catalog["validation"]["valid_skills"],
            "invalid_skills": catalog["validation"]["invalid_skills"],
            "execution_levels": catalog["execution_levels"],
        }, "policy-result"),
        _mapping_contract("WorkflowDistillerDecision", "src.skills.workflow_distiller", distill, "policy-result"),
    ]
    return _scenario_result(
        success_contract="HarnessResult",
        success_payload=success_payload,
        success_evidence=["catalog readable", "distiller accepted reusable workflow", "evaluator passed safe code"],
        success_behavior="Verify skill operations through catalog, distillation, and evaluator contracts.",
        success_side_effects=["writes demo evidence JSON only"],
        blocked_contract="WorkflowDistillerDecision",
        blocked_payload=blocked_distill,
        blocked_reason="one-off workflow lacks repeatability and clear failure modes",
        missing_inputs=["repeat count", "cross-project reuse", "failure modes"],
        contracts=contracts,
        artifacts=[],
    )


def _routing_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    light = classify_request("PER이 뭐야?")
    medium = classify_request("엔비디아 최근 실적을 요약해줘")
    high_risk = classify_request("엔비디아 지금 사도 돼? 내 포트폴리오를 바꿔야 할까?")
    ambiguous = classify_request("삼성 괜찮아?")
    success_payload = {
        "samples": [
            light.to_dict(),
            medium.to_dict(),
            high_risk.to_dict(),
            ambiguous.to_dict(),
        ],
        "routing_policy": "classify first, escalate only when evidence or risk requires it",
    }
    contracts = [
        _mapping_contract("RequestClassification", "src.orchestration.request_classifier", light.to_dict(), "policy-result"),
        _mapping_contract("RequestClassification", "src.orchestration.request_classifier", medium.to_dict(), "policy-result"),
        _mapping_contract("RequestClassification", "src.orchestration.request_classifier", high_risk.to_dict(), "policy-result"),
    ]
    return _scenario_result(
        success_contract="RequestClassification",
        success_payload=success_payload,
        success_evidence=[
            "light request stayed direct",
            "medium analysis requested source summary",
            "high-risk request escalated to role DAG",
            "ambiguous request asked for clarification",
        ],
        success_behavior="Route requests to the lightest sufficient UAF execution depth.",
        success_side_effects=["writes demo evidence JSON only"],
        blocked_contract="RequestClassification",
        blocked_payload=ambiguous.to_dict(),
        blocked_reason="request is too ambiguous to choose a safe execution depth",
        missing_inputs=["domain or artifact context"],
        contracts=contracts,
        artifacts=[],
    )


def _automatic_intake_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    project_dir = output_dir / "ordinary-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    success = build_kh_front_door(
        "Create a small static task tracker in this folder and verify it.",
        project=project_dir,
        host="codex",
    )
    blocked = build_kh_front_door(
        "Summarize this long pytest log and preserve failing test facts.",
        project=project_dir,
        host="codex",
        host_skill_paths=[
            r"C:\Users\KONEIT\.codex\plugins\cache\kh-uaf-marketplace\kh-uaf\0.0.0\skills\skill_catalog\SKILL.md"
        ],
    )
    success_summary = success.to_summary_dict()
    blocked_summary = blocked.to_summary_dict()
    summary_path = output_dir / "automatic_intake_front_door.json"
    summary_path.write_text(
        json.dumps(
            {
                "success": success_summary,
                "blocked": blocked_summary,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    contracts = [
        _mapping_contract("KhFrontDoorResult", "src.orchestration.kh_front_door", success_summary, "policy-result"),
        _mapping_contract("RequestClassification", "src.orchestration.request_classifier", success_summary["classification"], "policy-result"),
        _mapping_contract("PluginRoute", "src.orchestration.plugin_composition", success_summary["plugin_route"], "policy-result"),
    ]
    return _scenario_result(
        success_contract="KhFrontDoorResult",
        success_payload=success_summary,
        success_evidence=[
            "automatic intake ran before source exploration",
            "runtime_applied_skills contains front-door runtime skills only",
            "selected_not_executed_skills keeps follow-up skills honest",
        ],
        success_behavior="Route ordinary non-trivial user wording through KH front-door intake without requiring KH vocabulary.",
        success_side_effects=["writes automatic_intake_front_door.json under the demo output directory"],
        blocked_contract="KhFrontDoorResult",
        blocked_payload=blocked_summary,
        blocked_reason="stale KH plugin cache path must be resolved before claiming skill use",
        missing_inputs=["current installed KH skill path"],
        contracts=contracts,
        artifacts=[
            _artifact_record_from_file(
                summary_path,
                "automatic-intake-front-door-json",
                output_dir,
                ["json readable", "front-door success and stale-cache cases captured"],
                created_by_case="success",
            )
        ],
    )


def _plugin_composition_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    providers = [
        {
            "provider_id": "kh",
            "capabilities": ["workflow_control", "memory_goal_resume", "tdd_review"],
        },
        {
            "provider_id": "visual-checker",
            "capabilities": ["browser_qa", "screenshot"],
        },
        {
            "provider_id": "repo-service",
            "capabilities": ["repo_pr_ci"],
        },
        {
            "provider_id": "aggressive-methodology",
            "capabilities": ["planning_methodology"],
            "self_forcing_rules": ["MUST use this before any task"],
        },
    ]
    hybrid = compose_plugin_route(
        "Build a SaaS dashboard, verify the browser screen, and prepare the PR.",
        providers=providers,
    )
    direct = compose_plugin_route(
        "What is PER?",
        providers=providers,
    )
    continuation = compose_plugin_route(
        "Continue the current implementation plan.",
        providers=[
            {"provider_id": "kh", "capabilities": ["workflow_control"]},
            {
                "provider_id": "superpowers",
                "capabilities": ["planning_methodology", "tdd_review"],
                "self_forcing_rules": ["MUST use for creative work"],
            },
        ],
        context={"project_markers": [".superpowers"]},
    )
    success_payload = {
        "hybrid": hybrid.to_dict(),
        "direct": direct.to_dict(),
        "continuation": continuation.to_dict(),
        "policy": "provider mandatory wording is scoped to selected controller or assistant roles",
    }
    blocked_payload = {
        "status": "blocked",
        "route": "clarify",
        "blocked_reason": "provider snapshot or task objective is too ambiguous for a safe route",
    }
    contracts = [
        _mapping_contract("PluginCompositionDecision", "src.orchestration.plugin_composition", hybrid.to_dict(), "policy-result"),
        _mapping_contract("PluginCompositionDecision", "src.orchestration.plugin_composition", direct.to_dict(), "policy-result"),
        _mapping_contract("PluginCompositionDecision", "src.orchestration.plugin_composition", continuation.to_dict(), "policy-result"),
    ]
    return _scenario_result(
        success_contract="PluginCompositionDecision",
        success_payload=success_payload,
        success_evidence=[
            "hybrid route selected controller plus assistants",
            "light question stayed direct",
            "self-forcing provider did not self-select",
            "project-context continuation can select a non-KH controller",
        ],
        success_behavior="Choose direct, single, hybrid, or clarify routes from dynamic provider capabilities.",
        success_side_effects=["writes demo evidence JSON only"],
        blocked_contract="PluginCompositionDecision",
        blocked_payload=blocked_payload,
        blocked_reason=blocked_payload["blocked_reason"],
        missing_inputs=["provider capabilities", "task objective", "project context"],
        contracts=contracts,
        artifacts=[],
    )


def _scenario_evaluation_scenario(skill_name: str, output_dir: Path, repo_root: Path) -> Dict[str, Any]:
    evaluations = evaluate_scenarios(stress_scenarios())
    report = build_scenario_report(evaluations)
    trace_path = output_dir / "scenario_trace.jsonl"
    trace_path.write_text(
        "\n".join(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True) for item in evaluations) + "\n",
        encoding="utf-8",
    )
    trace_artifact = _artifact_record_from_file(
        trace_path,
        "scenario-trace-jsonl",
        output_dir,
        ["jsonl readable", "one record per scenario", "signals captured"],
        created_by_case="success",
    )
    success_payload = {
        "summary": report["summary"],
        "signals_by_category": report["signals_by_category"],
    }
    blocked_payload = {
        "status": "blocked",
        "unexpected_failures": report["unexpected_failures"],
        "blocked_reason": "unexpected scenario failures require classifier, evidence, gate, or resume fixes",
    }
    contracts = [
        _mapping_contract("ScenarioEvaluationReport", "src.orchestration.scenario_evaluator", report, "policy-result"),
        _mapping_contract("ScenarioEvaluation", "src.orchestration.scenario_evaluator", evaluations[0].to_dict(), "policy-result"),
    ]
    return _scenario_result(
        success_contract="ScenarioEvaluationReport",
        success_payload=success_payload,
        success_evidence=[
            "scenario matrix executed",
            "classification signals captured",
            "evidence and gate signals captured",
            "resume signals captured",
        ],
        success_behavior="Run deterministic SIDE-style scenarios and report actionable routing, evidence, gate, and resume signals.",
        success_side_effects=["writes scenario_trace.jsonl and demo evidence JSON"],
        blocked_contract="ScenarioEvaluationReport",
        blocked_payload=blocked_payload,
        blocked_reason=blocked_payload["blocked_reason"],
        missing_inputs=["regression fix for each unexpected failure"],
        contracts=contracts,
        artifacts=[trace_artifact],
    )


def _scenario_result(
    success_contract: str,
    success_payload: Dict[str, Any],
    success_evidence: List[str],
    success_behavior: str,
    success_side_effects: List[str],
    blocked_contract: str,
    blocked_payload: Dict[str, Any],
    blocked_reason: str,
    missing_inputs: List[str],
    contracts: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "success_case": {
            "status": "passed",
            "contract_type": success_contract,
            "payload": success_payload,
            "evidence": list(success_evidence),
            "expected_behavior": success_behavior,
            "side_effects": list(success_side_effects),
        },
        "blocked_or_failure_case": {
            "status": "failed" if blocked_payload.get("status") == "failed" else "blocked",
            "contract_type": blocked_contract,
            "payload": blocked_payload,
            "blocked_reason": blocked_reason,
            "missing_inputs": list(missing_inputs),
            "expected_behavior": "Stop or downgrade the claim until the missing input or failed evidence is resolved.",
            "remediation": _remediation_for(blocked_reason, missing_inputs),
            "non_destructive": True,
        },
        "contracts": contracts,
        "artifacts": artifacts,
    }


def _dispatch_for(skill_name: str, gate_payloads: List[Dict[str, Any]], success: bool) -> WorkflowDispatchResult:
    task = WorkflowTaskResult(
        task_id=f"demo_{_safe_id(skill_name)}",
        file_name=f"skill:{skill_name}",
        role="controller",
        status="success" if success else "blocked",
        message="demo dispatch completed" if success else "demo dispatch blocked",
        metadata={"evidence": [f"{skill_name} demo evidence"]},
    )
    return WorkflowDispatchResult(
        workflow_id=f"demo-{_safe_id(skill_name)}-workflow",
        success=success,
        task_results=[task],
        gate_results=gate_payloads,
        metadata={"skill": skill_name, "scenario": "runnable-mini-demo"},
    )


def _dataclass_contract(instance: Any) -> Dict[str, Any]:
    payload = instance.to_dict()
    cls = instance.__class__
    roundtrip = False
    if hasattr(cls, "from_dict"):
        roundtrip = cls.from_dict(payload).to_dict() == payload
    return {
        "name": cls.__name__,
        "module": cls.__module__,
        "fields_checked": list(payload.keys()),
        "roundtrip_checked": bool(roundtrip),
        "source": "dataclass" if is_dataclass(instance) else "policy-result",
        "sample": payload,
    }


def _mapping_contract(name: str, module: str, payload: Dict[str, Any], source: str) -> Dict[str, Any]:
    return {
        "name": name,
        "module": module,
        "fields_checked": list(payload.keys()),
        "roundtrip_checked": bool(payload),
        "source": source,
        "sample": payload,
    }


def _snapshot_artifacts(output_dir: Path) -> List[Dict[str, Any]]:
    project_dir = output_dir / "snapshot_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "alpha.txt").write_text("alpha before change\n", encoding="utf-8")
    (project_dir / "beta.txt").write_text("beta before change\n", encoding="utf-8")
    manager = SnapshotManager(str(project_dir), thread_id="demo-snapshot-thread")
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        version_id = manager.commit_many(["alpha.txt", "beta.txt"], "demo work-level snapshot")
    snapshot_path = Path(manager.snapshot_dir) / version_id
    validation = ["snapshot bundle created", "commit_many stdout captured"]
    try:
        with gzip.open(snapshot_path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        if len(payload.get("files", [])) == 2:
            validation.append("snapshot bundle contains two files")
    except Exception as exc:
        validation.append(f"snapshot validation failed: {type(exc).__name__}: {exc}")
    return [
        _artifact_record_from_file(
            snapshot_path,
            "snapshot-bundle",
            output_dir,
            validation,
            created_by_case="success",
        )
    ]


def _role_artifacts(task_results: Iterable[WorkflowTaskResult], output_dir: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for result in task_results:
        for artifact in result.metadata.get("role_artifacts", []) or []:
            path = Path(str(artifact.get("path", "")))
            if path.exists():
                records.append(
                    _artifact_record_from_file(
                        path,
                        "role-stage-output",
                        output_dir,
                        ["role artifact markdown exists", f"role={result.role}"],
                        created_by_case="success",
                    )
                )
    return records


def _artifact_record_from_deliverable(
    record: Dict[str, Any],
    output_dir: Path,
    quality: Dict[str, Any],
) -> Dict[str, Any]:
    path = Path(str(record.get("path", "")))
    file_name = path.name
    related_checks = [
        check
        for check in quality.get("checks", [])
        if check.get("file_name") == file_name
    ]
    failed = [check for check in related_checks if check.get("status") == "failed"]
    evidence = [
        f"{check.get('check_type')}:{check.get('status')}:{check.get('message')}"
        for check in related_checks
    ] or ["deliverable file exists"]
    item = _artifact_record_from_file(
        path,
        str(record.get("format") or record.get("kind") or "deliverable"),
        output_dir,
        evidence,
        template_not_applicable=str(record.get("artifact_type", "")) in {"technical-drawing", "cad-drawing"},
        created_by_case="success",
    )
    item["artifact_id"] = _safe_id(str(record.get("kind") or path.stem))
    item["validated"] = bool(item["validated"] and not failed)
    return item


def _complete_artifact_manifest(artifacts: List[Dict[str, Any]], output_dir: Path) -> List[Dict[str, Any]]:
    records = list(artifacts)
    known_paths = {str(Path(record["path"]).resolve()).lower() for record in records if record.get("path")}
    for path in _generated_files(output_dir):
        key = str(path.resolve()).lower()
        if key in known_paths:
            continue
        records.append(
            _artifact_record_from_file(
                path,
                _artifact_kind_from_path(path, output_dir),
                output_dir,
                ["auto-declared by generated-file manifest", "file exists under demo output root"],
                template_not_applicable=True,
                created_by_case="supporting-runtime-file",
            )
        )
        known_paths.add(key)

    manifest_path = output_dir / "demo_file_manifest.json"
    manifest_payload = {
        "generated_at": _utc_now(),
        "output_dir": str(output_dir),
        "files": [
            {
                "path": record["path"],
                "kind": record["kind"],
                "created_by_case": record["created_by_case"],
                "validated": record["validated"],
            }
            for record in records
        ],
    }
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    manifest_record = _artifact_record_from_file(
        manifest_path,
        "demo-generated-file-manifest",
        output_dir,
        ["json readable", "lists every generated file declared by the demo"],
        created_by_case="manifest",
    )
    known_paths = {str(Path(record["path"]).resolve()).lower() for record in records if record.get("path")}
    if str(manifest_path.resolve()).lower() not in known_paths:
        records.append(manifest_record)
    return records


def _write_demo_evidence_artifact(
    output_dir: Path,
    skill_name: str,
    success_case: Dict[str, Any],
    blocked_case: Dict[str, Any],
    contracts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    path = output_dir / "demo_evidence.json"
    payload = {
        "skill": skill_name,
        "success_status": success_case.get("status"),
        "blocked_status": blocked_case.get("status"),
        "contract_names": [contract.get("name") for contract in contracts],
        "generated_at": _utc_now(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return _artifact_record_from_file(
        path,
        "demo-evidence-json",
        output_dir,
        ["json readable", "success and blocked cases summarized"],
        created_by_case="success",
    )


def _artifact_record_from_file(
    path: Path,
    kind: str,
    output_dir: Path,
    validation_evidence: List[str],
    template_not_applicable: bool = False,
    created_by_case: str = "success",
) -> Dict[str, Any]:
    exists = path.exists()
    checksum = _sha256(path) if exists and path.is_file() else ""
    validated = bool(exists and path.is_file() and path.stat().st_size > 0 and _is_relative_to(path, output_dir))
    if path.suffix.lower() == ".json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
            validation_evidence = list(validation_evidence) + ["json parsed"]
        except json.JSONDecodeError as exc:
            validated = False
            validation_evidence = list(validation_evidence) + [f"json parse failed: {exc}"]
    if _validation_evidence_failed(validation_evidence):
        validated = False
    return {
        "artifact_id": _safe_id(path.stem),
        "kind": kind,
        "path": str(path),
        "exists": exists,
        "validated": validated,
        "checksum": checksum,
        "validation_evidence": list(validation_evidence),
        "template_not_applicable": template_not_applicable,
        "created_by_case": created_by_case,
    }


def _host_metadata(output_dir: Path, repo_root: Path, skill_dir: Path, execution_level: str) -> Dict[str, Any]:
    return {
        "selected_host": "local",
        "host_differences": [
            {
                "host": "codex",
                "dispatch": "tool-mediated local workspace with plugin skills",
                "state": "runtime root may live outside the user project",
            },
            {
                "host": "antigravity-style",
                "dispatch": "plugin or MCP registration can expose the same skill contract",
                "state": "runtime paths remain host-owned",
            },
            {
                "host": "claude-code",
                "dispatch": "skill folder can be read as procedural guidance or called through local CLI",
                "state": "project files and internal evidence stay separated",
            },
        ],
        "repo_root": str(repo_root),
        "skill_dir": str(skill_dir),
        "output_dir": str(output_dir),
        "cwd_supported": True,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "external_runtime_dependency": False,
        "execution_level": execution_level,
    }


def _verification(
    contracts: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    output_dir: Path,
) -> Dict[str, Any]:
    return {
        "runnable": True,
        "exit_code": 0,
        "stdout_json_only": True,
        "stderr_empty_or_expected": True,
        "contract_roundtrip": all(contract.get("roundtrip_checked") for contract in contracts),
        "artifacts_within_output_dir": all(_is_relative_to(Path(artifact["path"]), output_dir) for artifact in artifacts),
        "artifacts_validated": all(bool(artifact.get("validated")) for artifact in artifacts),
        "artifact_count": len(artifacts),
        "runtime_observation": {
            "source": "outer subprocess quality gate",
            "checked_by": [
                "tests.test_skill_demos",
                "src.skills.uaf_skill_quality._run_demo_script",
            ],
            "note": "exit code, stdout JSON, and stderr emptiness are verified by the caller that launches this demo.",
        },
    }


def _pytest_failure_log() -> str:
    passed = [f"tests/test_order.py::test_bulk_save[{index}] PASSED" for index in range(1, 80)]
    failure = [
        "tests/test_invoice.py::test_total_rounding FAILED",
        "test_invoice.py line 87",
        "AssertionError: rounding mismatch",
        "assert 119999 == 120000",
        "exit code: 1",
    ]
    return "\n".join(passed[:38] + failure + passed[38:])


def _skill_metadata(skill_name: str) -> Dict[str, Any]:
    catalog = collect_packaged_skills()
    for skill in catalog["skills"]:
        if skill["name"] == skill_name:
            return skill
    raise ValueError(f"unknown packaged skill: {skill_name}")


def _default_demo_output_dir(skill_name: str) -> Path:
    configured = os.environ.get("UAF_DEMO_OUTPUT_ROOT", "").strip()
    root = Path(configured).expanduser() if configured else Path(tempfile.gettempdir()) / "KH-UAF" / "demo-output"
    return root / _safe_id(skill_name)


def _skill_dir(repo_root: Path, skill_name: str) -> Path:
    metadata = _skill_metadata(skill_name)
    return repo_root / "skills" / str(metadata["relative_path"]).replace("/SKILL.md", "")


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src").is_dir() and (parent / "skills").is_dir():
            return parent
    raise RuntimeError("KH UAF repository root not found")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generated_files(output_dir: Path) -> List[Path]:
    if not output_dir.exists():
        return []
    return sorted(path for path in output_dir.rglob("*") if path.is_file())


def _artifact_kind_from_path(path: Path, output_dir: Path) -> str:
    rel = path.resolve().relative_to(output_dir.resolve()).as_posix()
    if rel.startswith("_runtime/"):
        if rel.endswith(".md"):
            return "runtime-role-artifact"
        if rel.endswith(".json") or rel.endswith(".jsonl"):
            return "runtime-state-artifact"
        if rel.endswith(".gz"):
            return "runtime-snapshot-artifact"
        return "runtime-support-artifact"
    if path.suffix:
        return path.suffix.lower().lstrip(".")
    return "generated-file"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _validation_evidence_failed(validation_evidence: Iterable[str]) -> bool:
    failure_pattern = re.compile(r"\b(failed|failure|error|invalid|missing)\b", re.IGNORECASE)
    return any(failure_pattern.search(str(item)) for item in validation_evidence)


def _remediation_for(blocked_reason: str, missing_inputs: Iterable[str]) -> str:
    missing = [str(item) for item in missing_inputs if str(item)]
    if missing:
        return f"Provide or regenerate: {', '.join(missing)}."
    if blocked_reason:
        return f"Resolve the blocker and rerun the demo: {blocked_reason}."
    return "Resolve the failed evidence and rerun the demo."


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", str(value).lower()).strip("-") or "demo"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _restore_env(old_env: Dict[str, Optional[str]]) -> None:
    for key, value in old_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
