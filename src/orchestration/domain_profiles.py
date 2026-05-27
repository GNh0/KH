from typing import Iterable, List

from src.contracts import DomainProfile, DomainRole, WorkDesign


BASE_DESIGN_ARTIFACTS = [
    "work-design",
    "role-task-plan",
    "evidence-plan",
    "risk-policy-checklist",
]

BASE_EVIDENCE = [
    "work design saved",
    "artifact manifest saved",
    "required design artifacts saved",
    "risk policy checked",
]


class DomainProfileBuilder:
    @staticmethod
    def build(
        objective: str,
        domain_hint: str = "",
        subdomains: Iterable[str] = None,
        artifact_types: Iterable[str] = None,
    ) -> DomainProfile:
        domain_name = (domain_hint or "generic").strip().lower() or "generic"
        required_artifacts = _unique(BASE_DESIGN_ARTIFACTS + list(artifact_types or []))
        return DomainProfile(
            domain_name=domain_name,
            objective=objective,
            subdomains=_unique(list(subdomains or ["discovery", "design", "execution", "review", "risk"])),
            roles=_default_domain_roles(required_artifacts),
            required_design_artifact_types=required_artifacts,
            evidence_required=list(BASE_EVIDENCE),
            review_gates=[
                "design review completed",
                "qa qc review completed",
                "final decision gate completed",
            ],
            risk_policy_gates=[
                "risk policy checked",
                "sensitive information checked",
                "missing evidence checked",
            ],
            metadata={
                "source": "domain_profile_builder",
                "dynamic_domain": not bool(domain_hint),
            },
        )


def work_design_from_profile(
    profile: DomainProfile,
    scope: str = "",
    assumptions: Iterable[str] = None,
    constraints: Iterable[str] = None,
    deliverables: Iterable[str] = None,
) -> WorkDesign:
    return WorkDesign(
        objective=profile.objective,
        domain=profile.domain_name,
        scope=scope,
        assumptions=list(assumptions or ["Inputs are limited to the current request and attached artifacts."]),
        constraints=list(constraints or ["Do not store secrets or unsupported claims as durable facts."]),
        subdomains=list(profile.subdomains),
        roles_required=[role.name for role in profile.roles],
        deliverables=list(deliverables or ["final synthesized output"]),
        evidence_required=list(profile.evidence_required),
        risk_policy_checks=list(profile.risk_policy_gates),
        review_gates=list(profile.review_gates),
        design_artifacts=list(profile.required_design_artifact_types),
        metadata={"source": "domain_profile_builder"},
    )


def render_work_design_markdown(work_design: WorkDesign) -> str:
    sections = [
        "# Work Design",
        "",
        f"Objective: {work_design.objective}",
        f"Domain: {work_design.domain}",
        f"Scope: {work_design.scope or 'not specified'}",
        "",
        "## Subdomains",
        _bullet_list(work_design.subdomains),
        "",
        "## Roles Required",
        _bullet_list(work_design.roles_required),
        "",
        "## Deliverables",
        _bullet_list(work_design.deliverables),
        "",
        "## Required Design Artifacts",
        _bullet_list(work_design.design_artifacts),
        "",
        "## Evidence Required",
        _bullet_list(work_design.evidence_required),
        "",
        "## Review Gates",
        _bullet_list(work_design.review_gates),
        "",
        "## Risk And Policy Checks",
        _bullet_list(work_design.risk_policy_checks),
        "",
        "## Assumptions",
        _bullet_list(work_design.assumptions),
        "",
        "## Constraints",
        _bullet_list(work_design.constraints),
        "",
    ]
    return "\n".join(sections)


def _default_domain_roles(required_artifacts: List[str]) -> List[DomainRole]:
    return [
        DomainRole(
            name="ceo",
            purpose="Set objective, priorities, and final decision criteria.",
            responsibilities=["define success", "resolve priority conflicts"],
            stage="governance",
            required_artifacts=["work-design"],
            produces=["decision criteria"],
        ),
        DomainRole(
            name="advisor",
            purpose="Challenge assumptions and surface missing perspectives.",
            responsibilities=["identify blind spots", "suggest alternatives"],
            stage="governance",
            required_artifacts=["work-design"],
            produces=["advisory notes"],
        ),
        DomainRole(
            name="domain-designer",
            purpose="Create mandatory work design and required artifact list.",
            responsibilities=["classify domain", "define subdomains", "define artifacts"],
            stage="design",
            required_artifacts=[],
            produces=list(required_artifacts),
        ),
        DomainRole(
            name="decomposition-planner",
            purpose="Split the work into bounded role tasks.",
            responsibilities=["map artifacts to tasks", "sequence review gates"],
            stage="planning",
            required_artifacts=["work-design", "role-task-plan"],
            produces=["task plan"],
        ),
        DomainRole(
            name="specialist",
            purpose="Execute assigned domain-specific work.",
            responsibilities=["produce assigned deliverables", "record evidence"],
            stage="execution",
            required_artifacts=["work-design", "role-task-plan"],
            produces=["specialist result"],
        ),
        DomainRole(
            name="reviewer",
            purpose="Review outputs against the design artifacts.",
            responsibilities=["find contradictions", "find missing requirements"],
            stage="review",
            required_artifacts=["work-design", "evidence-plan"],
            produces=["review findings"],
        ),
        DomainRole(
            name="qa-qc-verifier",
            purpose="Verify quality, completeness, and evidence coverage.",
            responsibilities=["check deliverables", "check evidence"],
            stage="qa",
            required_artifacts=["evidence-plan"],
            produces=["qa qc result"],
        ),
        DomainRole(
            name="risk-policy-reviewer",
            purpose="Check safety, risk, policy, and sensitive information concerns.",
            responsibilities=["check risks", "check sensitive data", "check policy constraints"],
            stage="risk",
            required_artifacts=["risk-policy-checklist"],
            produces=["risk policy result"],
        ),
        DomainRole(
            name="final-decision-manager",
            purpose="Decide whether the workflow is complete or blocked.",
            responsibilities=["inspect evidence", "approve final output or request iteration"],
            stage="final",
            required_artifacts=list(required_artifacts),
            produces=["final decision"],
        ),
    ]


def _bullet_list(items: Iterable[str]) -> str:
    values = list(items or [])
    if not values:
        return "- none"
    return "\n".join(f"- {item}" for item in values)


def _unique(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    for item in items:
        value = str(item).strip()
        if value and value not in result:
            result.append(value)
    return result
