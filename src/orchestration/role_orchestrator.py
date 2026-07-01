import asyncio
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from src.contracts import WorkflowTaskResult
from src.orchestration.evidence_producers import (
    collect_metadata_evidence,
    qa_result_evidence,
    review_result_evidence,
)
from src.orchestration.gate_evaluators import (
    build_qa_check,
    evaluate_code_quality_gate,
    evaluate_qa_checks,
    evaluate_qa_gate,
    evaluate_release_gate,
    evaluate_security_gate,
    evaluate_spec_review_gate,
)
from src.orchestration.roles import RoleProfile, default_role_profiles
from src.orchestration.runtime_paths import project_artifact_role_dir


PRE_IMPLEMENTATION_ROLES: Tuple[str, ...] = (
    "ceo",
    "advisor",
    "product-strategist",
    "system-architect",
    "implementation-planner",
    "controller",
)

REVIEW_RELEASE_ROLES: Tuple[str, ...] = (
    "spec-reviewer",
    "code-quality-reviewer",
    "qa-verifier",
    "security-reviewer",
    "release-manager",
)


class DefaultRoleRunner:
    async def run_role(self, profile: RoleProfile, context: Dict[str, Any]) -> WorkflowTaskResult:
        await asyncio.sleep(0)
        deliverable_names = _deliverable_names(context)
        deliverable_profile = _deliverable_profile(context)
        evidence = _role_evidence_key(profile.name)
        role_artifacts = _write_role_artifacts(profile, context)
        return WorkflowTaskResult(
            task_id=f"role_{_safe_id(profile.name)}",
            file_name=f"role:{profile.name}",
            role=profile.name,
            status="success",
            message=f"{profile.name} completed",
            metadata={
                "execution_model": "parallel-role-stage",
                "stage": profile.stage,
                "purpose": profile.purpose,
                "inputs": list(profile.inputs),
                "outputs": list(profile.outputs),
                "required_deliverables": _role_deliverables(profile.name, deliverable_names, deliverable_profile),
                "role_artifacts": role_artifacts,
                "evidence": [evidence],
                "completed_at": _utc_now(),
            },
        )


class GateRoleRunner(DefaultRoleRunner):
    async def run_role(self, profile: RoleProfile, context: Dict[str, Any]) -> WorkflowTaskResult:
        await asyncio.sleep(0)
        role_gate_results = context.setdefault("role_gate_results", {})
        task_results = context.get("implementation_task_results", [])
        goal = context.get("goal", {})

        if profile.name == "spec-reviewer":
            gate = evaluate_spec_review_gate(task_results)
        elif profile.name == "code-quality-reviewer":
            gate = evaluate_code_quality_gate(
                role_gate_results.get("spec-reviewer", {}),
                task_results=task_results,
            )
        elif profile.name == "qa-verifier":
            checks = _qa_checks_from_context(context)
            gate = evaluate_qa_checks(role_gate_results.get("code-quality-reviewer", {}), checks=checks, goal=goal)
        elif profile.name == "security-reviewer":
            gate = evaluate_security_gate(
                role_gate_results.get("code-quality-reviewer", {}),
                task_results,
                goal=goal,
            )
        elif profile.name == "release-manager":
            gate = evaluate_release_gate(
                role_gate_results.get("qa-verifier", {}),
                role_gate_results.get("security-reviewer", {}),
                goal=goal,
            )
        else:
            return await super().run_role(profile, context)

        role_gate_results[profile.name] = gate
        deliverable_names = _deliverable_names(context)
        deliverable_profile = _deliverable_profile(context)
        metadata = {
            "execution_model": "parallel-role-stage",
            "stage": profile.stage,
            "gate": gate,
            "required_deliverables": _role_deliverables(profile.name, deliverable_names, deliverable_profile),
            "role_artifacts": _write_role_artifacts(profile, context, gate=gate),
            "evidence_records": list(gate.get("evidence_records", [])),
            "completed_at": _utc_now(),
        }
        evidence = collect_metadata_evidence(metadata)
        if evidence:
            metadata["evidence"] = evidence
        return WorkflowTaskResult(
            task_id=f"role_{_safe_id(profile.name)}",
            file_name=f"role:{profile.name}",
            role=profile.name,
            status=_task_status_from_gate(gate),
            message=gate.get("message", f"{profile.name} completed"),
            metadata=metadata,
        )

    async def blocked_role_result(
        self,
        profile: RoleProfile,
        context: Dict[str, Any],
        pending_dependencies: List[str],
    ) -> WorkflowTaskResult:
        await asyncio.sleep(0)
        role_gate_results = context.setdefault("role_gate_results", {})
        gate = _blocked_gate(
            profile,
            context.get("goal", {}),
            pending_dependencies,
            role_gate_results=role_gate_results,
        )
        role_gate_results[profile.name] = gate
        deliverable_names = _deliverable_names(context)
        deliverable_profile = _deliverable_profile(context)
        metadata = {
            "execution_model": "parallel-role-stage",
            "stage": profile.stage,
            "pending_dependencies": list(pending_dependencies),
            "gate": gate,
            "required_deliverables": _role_deliverables(profile.name, deliverable_names, deliverable_profile),
            "evidence_records": list(gate.get("evidence_records", [])),
            "completed_at": _utc_now(),
        }
        return WorkflowTaskResult(
            task_id=f"role_{_safe_id(profile.name)}",
            file_name=f"role:{profile.name}",
            role=profile.name,
            status="blocked",
            message=gate.get("message", f"{profile.name} blocked"),
            metadata=metadata,
        )


class RoleOrchestrator:
    def __init__(
        self,
        profiles: Optional[Sequence[RoleProfile]] = None,
        runner: Optional[Any] = None,
    ):
        self.profiles = tuple(profiles or default_role_profiles())
        self.runner = runner or DefaultRoleRunner()
        self._profiles_by_name = {profile.name: profile for profile in self.profiles}
        if len(self._profiles_by_name) != len(self.profiles):
            raise ValueError("role profile names must be unique")

    def run_sync(
        self,
        context: Optional[Dict[str, Any]] = None,
        selected_roles: Optional[Iterable[str]] = None,
        satisfied_dependencies: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        return asyncio.run(
            self.run(
                context=context,
                selected_roles=selected_roles,
                satisfied_dependencies=satisfied_dependencies,
            )
        )

    async def run(
        self,
        context: Optional[Dict[str, Any]] = None,
        selected_roles: Optional[Iterable[str]] = None,
        satisfied_dependencies: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        role_names = _selected_role_names(self.profiles, selected_roles)
        selected = set(role_names)
        satisfied = set(satisfied_dependencies or [])
        pending = set(role_names)
        completed: Dict[str, WorkflowTaskResult] = {}
        failed: Dict[str, WorkflowTaskResult] = {}
        waves: List[Dict[str, Any]] = []
        shared_context = context if context is not None else {}

        while pending:
            ready = [
                name
                for name in role_names
                if name in pending and self._dependencies_satisfied(name, selected, satisfied, completed)
            ]
            if not ready:
                blocked_results = [
                    await self._blocked_result(
                        self._profiles_by_name[name],
                        shared_context,
                        [
                            dependency
                            for dependency in self._profiles_by_name[name].blocks_on
                            if dependency in selected and dependency not in completed and dependency not in satisfied
                        ],
                    )
                    for name in role_names
                    if name in pending
                ]
                waves.append({
                    "index": len(waves),
                    "parallel": len(blocked_results) > 1,
                    "roles": [result.role for result in blocked_results],
                    "results": [result.to_dict() for result in blocked_results],
                })
                for result in blocked_results:
                    failed[result.role] = result
                pending.clear()
                break

            tasks = [
                asyncio.create_task(self._run_named_role(name, shared_context))
                for name in ready
            ]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)
            wave_results: List[WorkflowTaskResult] = []
            for name, raw_result in zip(ready, raw_results):
                if isinstance(raw_result, Exception):
                    result = _failed_role_result(self._profiles_by_name[name], raw_result)
                else:
                    result = raw_result
                wave_results.append(result)
                pending.remove(name)
                if result.status == "success":
                    completed[name] = result
                else:
                    failed[name] = result

            waves.append({
                "index": len(waves),
                "parallel": len(wave_results) > 1,
                "runtime_overlap": _wave_has_runtime_overlap(wave_results),
                "roles": [result.role for result in wave_results],
                "results": [result.to_dict() for result in wave_results],
            })

            if failed:
                blocked_results = [
                    await self._blocked_result(
                        self._profiles_by_name[name],
                        shared_context,
                        [
                            dependency
                            for dependency in self._profiles_by_name[name].blocks_on
                            if dependency in selected
                            and dependency not in completed
                            and dependency not in satisfied
                        ],
                    )
                    for name in role_names
                    if name in pending
                ]
                if blocked_results:
                    waves.append({
                        "index": len(waves),
                        "parallel": len(blocked_results) > 1,
                        "roles": [result.role for result in blocked_results],
                        "results": [result.to_dict() for result in blocked_results],
                    })
                    for result in blocked_results:
                        failed[result.role] = result
                    pending.difference_update(result.role for result in blocked_results)
                break

        results = [result for wave in waves for result in wave["results"]]
        shared_context["role_orchestration"] = {
            "execution_model": "dag-asyncio-role-waves",
            "role_count": len(role_names),
            "wave_count": len(waves),
            "parallel_wave_count": sum(1 for wave in waves if wave.get("parallel")),
            "runtime_overlap_wave_count": sum(1 for wave in waves if wave.get("runtime_overlap")),
            "roles": list(role_names),
            "success": not failed and not pending,
        }
        shared_context["role_task_results"] = list(results)
        return {
            "success": not failed and not pending,
            "results": results,
            "waves": waves,
            "context": shared_context,
        }

    def _dependencies_satisfied(
        self,
        role_name: str,
        selected: Set[str],
        satisfied: Set[str],
        completed: Dict[str, WorkflowTaskResult],
    ) -> bool:
        profile = self._profiles_by_name[role_name]
        dependencies = [
            dependency
            for dependency in profile.blocks_on
            if dependency in selected
        ]
        return all(dependency in completed or dependency in satisfied for dependency in dependencies)

    async def _blocked_result(
        self,
        profile: RoleProfile,
        context: Dict[str, Any],
        pending_dependencies: List[str],
    ) -> WorkflowTaskResult:
        if hasattr(self.runner, "blocked_role_result"):
            return await self.runner.blocked_role_result(profile, context, pending_dependencies)
        return _blocked_role_result(profile, pending_dependencies)

    async def _run_named_role(self, role_name: str, context: Dict[str, Any]) -> WorkflowTaskResult:
        profile = self._profiles_by_name[role_name]
        started_at = datetime.now(timezone.utc)
        result = await self.runner.run_role(profile, context)
        finished_at = datetime.now(timezone.utc)
        return _with_runtime_metadata(result, started_at, finished_at, self.runner)


def _with_runtime_metadata(
    result: WorkflowTaskResult,
    started_at: datetime,
    finished_at: datetime,
    runner: Any,
) -> WorkflowTaskResult:
    metadata = dict(result.metadata)
    metadata.setdefault("started_at_utc", started_at.isoformat())
    metadata.setdefault("finished_at_utc", finished_at.isoformat())
    metadata.setdefault("duration_seconds", round(max(0.0, (finished_at - started_at).total_seconds()), 6))
    metadata.setdefault("runner_type", runner.__class__.__name__)
    metadata.setdefault("adapter_name", getattr(runner, "name", runner.__class__.__name__))
    metadata.setdefault("independent_process", False)
    return WorkflowTaskResult(
        task_id=result.task_id,
        file_name=result.file_name,
        role=result.role,
        status=result.status,
        message=result.message,
        metadata=metadata,
    )


def _wave_has_runtime_overlap(results: List[WorkflowTaskResult]) -> bool:
    if len(results) < 2:
        return False
    intervals = []
    for result in results:
        metadata = dict(result.metadata)
        start = _parse_datetime(metadata.get("started_at_utc"))
        finish = _parse_datetime(metadata.get("finished_at_utc"))
        if start is None or finish is None:
            return False
        intervals.append((start, finish))
    latest_start = max(start for start, _ in intervals)
    earliest_finish = min(finish for _, finish in intervals)
    return latest_start < earliest_finish


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


async def run_pre_implementation_roles(context: Dict[str, Any]) -> Dict[str, Any]:
    return await RoleOrchestrator().run(
        context=context,
        selected_roles=PRE_IMPLEMENTATION_ROLES,
    )


async def run_review_release_roles(context: Dict[str, Any]) -> Dict[str, Any]:
    return await RoleOrchestrator(runner=GateRoleRunner()).run(
        context=context,
        selected_roles=REVIEW_RELEASE_ROLES,
        satisfied_dependencies=set(PRE_IMPLEMENTATION_ROLES) | {"implementer"},
    )


def _selected_role_names(
    profiles: Sequence[RoleProfile],
    selected_roles: Optional[Iterable[str]],
) -> Tuple[str, ...]:
    if selected_roles is None:
        return tuple(profile.name for profile in profiles)
    selected = set(selected_roles)
    missing = selected.difference(profile.name for profile in profiles)
    if missing:
        raise ValueError(f"unknown role(s): {', '.join(sorted(missing))}")
    return tuple(profile.name for profile in profiles if profile.name in selected)


def _task_status_from_gate(gate: Dict[str, Any]) -> str:
    status = gate.get("status", "")
    if status == "passed":
        return "success"
    if status == "blocked":
        return "blocked"
    return "failed"


def _blocked_role_result(profile: RoleProfile, pending_dependencies: List[str]) -> WorkflowTaskResult:
    return WorkflowTaskResult(
        task_id=f"role_{_safe_id(profile.name)}",
        file_name=f"role:{profile.name}",
        role=profile.name,
        status="blocked",
        message=f"blocked by role dependency: {', '.join(pending_dependencies)}",
        metadata={
            "execution_model": "parallel-role-stage",
            "stage": profile.stage,
            "pending_dependencies": list(pending_dependencies),
        },
    )


def _write_role_artifacts(
    profile: RoleProfile,
    context: Dict[str, Any],
    gate: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    project_dir = context.get("project_dir", "")
    workflow_id = context.get("workflow_id", "")
    if not project_dir or not workflow_id:
        return []

    metadata = context.get("metadata", {}) or {}
    app_context = metadata.get("app_context", {}) or {}
    thread_id = metadata.get("thread_id", "") or app_context.get("thread_id", "")
    artifact_dir = project_artifact_role_dir(project_dir, thread_id=thread_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{_safe_id(profile.name)}.md"
    deliverable_names = _deliverable_names(context)
    content = _role_artifact_markdown(profile, context, deliverable_names, gate)
    artifact_path.write_text(content, encoding="utf-8")
    return [
        {
            "workflow_id": workflow_id,
            "role": profile.name,
            "artifact_type": "role-stage-output",
            "title": profile.title,
            "path": str(artifact_path),
            "evidence": _role_evidence_key(profile.name),
        }
    ]


def _role_artifact_markdown(
    profile: RoleProfile,
    context: Dict[str, Any],
    deliverable_names: List[str],
    gate: Optional[Dict[str, Any]] = None,
) -> str:
    work_design = context.get("work_design", {}) or {}
    objective = work_design.get("objective", "") or context.get("objective", "")
    lines = [
        f"# {profile.title}",
        "",
        f"- Role: {profile.name}",
        f"- Stage: {profile.stage}",
        f"- Purpose: {profile.purpose}",
        f"- Objective: {objective or 'not specified'}",
        "",
        "## Responsibilities",
    ]
    lines.extend(f"- {item}" for item in profile.responsibilities)
    lines.extend([
        "",
        "## Expected Outputs",
    ])
    lines.extend(f"- {item}" for item in profile.outputs)
    if deliverable_names:
        lines.extend([
            "",
            "## Available User Deliverables",
        ])
        lines.extend(f"- {item}" for item in deliverable_names)
    if gate:
        lines.extend([
            "",
            "## Gate Result",
            f"- Status: {gate.get('status', '')}",
            f"- Message: {gate.get('message', '')}",
        ])
        findings = gate.get("findings", []) or []
        if findings:
            lines.append("- Findings:")
            lines.extend(f"  - {item}" for item in findings)
    lines.append("")
    return "\n".join(lines)


def _failed_role_result(profile: RoleProfile, exc: Exception) -> WorkflowTaskResult:
    return WorkflowTaskResult(
        task_id=f"role_{_safe_id(profile.name)}",
        file_name=f"role:{profile.name}",
        role=profile.name,
        status="failed",
        message=str(exc),
        metadata={
            "execution_model": "parallel-role-stage",
            "stage": profile.stage,
            "error_type": type(exc).__name__,
        },
    )


def _blocked_gate(
    profile: RoleProfile,
    goal: Dict[str, Any],
    pending_dependencies: List[str],
    role_gate_results: Dict[str, Any] = None,
) -> Dict[str, Any]:
    missing_evidence = list((goal or {}).get("metadata", {}).get("missing_evidence", []))
    upstream_findings = _upstream_gate_findings(role_gate_results or {}, pending_dependencies)
    blocked_reason = (goal or {}).get("blocked_reason", "") or f"blocked by role dependency: {', '.join(pending_dependencies)}"
    message = "goal evidence gate did not pass" if profile.name == "release-manager" and missing_evidence else blocked_reason
    evidence_key = _gate_evidence_key(profile.name)
    if profile.name == "qa-verifier":
        evidence_record = qa_result_evidence(
            passed=False,
            evidence_key=evidence_key,
            checks=missing_evidence or pending_dependencies,
        )
    else:
        evidence_record = review_result_evidence(
            role=profile.name,
            passed=False,
            evidence_key=evidence_key,
            findings=missing_evidence or upstream_findings or pending_dependencies,
        )
    gate = {
        "role": profile.name,
        "status": "blocked",
        "message": message,
        "blocks_on": list(profile.blocks_on),
        "blocked_reason": blocked_reason,
        "missing_evidence": missing_evidence,
        "findings": missing_evidence or upstream_findings or list(pending_dependencies),
        "evidence_records": [evidence_record.to_dict()],
    }
    if goal:
        gate["goal_status"] = goal.get("status")
    return gate


def _qa_checks_from_context(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    metadata = context.get("metadata", {}) or {}
    goal = context.get("goal", {}) or {}
    goal_metadata = goal.get("metadata", {}) or {}
    checks = (
        context.get("qa_checks")
        or metadata.get("qa_checks")
        or goal_metadata.get("qa_checks")
        or []
    )
    if checks:
        return [dict(check) for check in checks if isinstance(check, dict)]
    if metadata.get("qa_skip_approved") or goal_metadata.get("qa_skip_approved"):
        reason = str(metadata.get("qa_skip_reason") or goal_metadata.get("qa_skip_reason") or "QA explicitly marked not applicable")
        return [
            build_qa_check(
                requirement_id="QA-SKIP",
                check_type="approved-skip",
                description=reason,
                status="skipped",
                evidence=["qa skip approved"],
                scope="explicit-workflow-qa-skip",
                notes="Completion is allowed because an explicit scoped QA skip record exists.",
            )
        ]
    return []


def _upstream_gate_findings(role_gate_results: Dict[str, Any], dependencies: List[str]) -> List[str]:
    findings: List[str] = []
    for dependency in dependencies:
        gate = role_gate_results.get(dependency, {}) or {}
        findings.extend(str(item) for item in gate.get("findings", []) or [])
        for item in gate.get("structured_findings", []) or []:
            if isinstance(item, dict):
                findings.append(str(item.get("message", "")))
    return [item for item in findings if item]


def _gate_evidence_key(role_name: str) -> str:
    return {
        "spec-reviewer": "spec review passed",
        "code-quality-reviewer": "code quality review passed",
        "qa-verifier": "qa gate passed",
        "security-reviewer": "security review passed",
        "release-manager": "release gate passed",
    }.get(role_name, f"{role_name} gate passed")


def _deliverable_names(context: Dict[str, Any]) -> List[str]:
    return [
        str(item.get("path", "")).replace("\\", "/").split("/")[-1]
        for item in context.get("deliverable_exports", {}).get("deliverables", [])
        if item.get("path")
    ]


def _deliverable_profile(context: Dict[str, Any]) -> str:
    exports = context.get("deliverable_exports", {}) or {}
    profile = str(exports.get("profile") or context.get("deliverable_profile") or "general-orchestration")
    return profile.strip().lower() or "general-orchestration"


def _role_deliverables(role_name: str, names: List[str], profile_name: str = "general-orchestration") -> List[str]:
    general_by_role = {
        "product-strategist": ["requirements_brief.docx", "deliverable_definition.docx"],
        "system-architect": ["orchestration_design.docx", "process_flow.docx"],
        "implementation-planner": ["role_task_breakdown.xlsx"],
        "qa-verifier": ["evidence_plan.xlsx"],
        "security-reviewer": ["risk_policy_checklist.xlsx"],
        "release-manager": list(names),
    }
    software_by_role = {
        "product-strategist": ["requirements_brief.docx", "functional_specification.docx"],
        "system-architect": ["development_design.docx", "screen_api_definition.docx", "data_definition.xlsx"],
        "implementation-planner": ["role_task_breakdown.xlsx"],
        "qa-verifier": ["test_verification_plan.xlsx"],
        "security-reviewer": ["risk_policy_checklist.xlsx"],
        "release-manager": list(names),
    }
    product_by_role = {
        "product-strategist": ["product_design_document.docx"],
        "system-architect": ["concept_drawing.svg", "concept_drawing.dxf", "dimension_bom.xlsx"],
        "implementation-planner": ["dimension_bom.xlsx"],
        "qa-verifier": ["product_design_document.docx"],
        "security-reviewer": [],
        "release-manager": list(names),
    }
    investment_by_role = {
        "product-strategist": ["investment_analysis_report.docx"],
        "system-architect": ["scenario_model.xlsx"],
        "implementation-planner": ["scenario_model.xlsx"],
        "qa-verifier": ["investment_analysis_report.docx"],
        "security-reviewer": ["risk_policy_checklist.xlsx"],
        "release-manager": list(names),
    }
    profile_map = {
        "software-development": software_by_role,
        "product-design": product_by_role,
        "investment-analysis": investment_by_role,
        "general-orchestration": general_by_role,
    }
    by_role = profile_map.get(profile_name, general_by_role)
    expected = by_role.get(role_name, [])
    if not expected:
        return []
    available = set(names)
    return [name for name in expected if name in available]


def _role_evidence_key(role_name: str) -> str:
    readable = role_name.replace("-", " ")
    return f"{readable} role task completed"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "role"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
