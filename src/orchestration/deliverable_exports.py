import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from xml.sax.saxutils import escape

from src.contracts import DomainProfile, DomainRole, WorkDesign
from src.orchestration.quality_harnesses import (
    build_traceability_matrix_rows,
    evaluate_deliverable_quality,
)


DELIVERABLE_EVIDENCE = [
    "requirements brief exported",
    "orchestration design exported",
    "deliverable definition exported",
    "process flow exported",
    "role task breakdown exported",
    "evidence plan exported",
    "risk policy checklist exported",
]


def export_office_deliverables(
    project_dir: str,
    workflow_id: str,
    domain_profile: DomainProfile,
    work_design: WorkDesign,
    source_design_doc: str = "",
    file_list: Iterable[str] = None,
    metadata: Dict[str, Any] = None,
) -> Dict[str, Any]:
    metadata = metadata or {}
    project_root = Path(project_dir).resolve()
    export_dir = _resolve_project_path(project_root, str(metadata.get("deliverable_export_dir", "docs")))
    export_dir.mkdir(parents=True, exist_ok=True)

    files = [str(item) for item in (file_list or [])]
    source_title = _first_heading(source_design_doc) or work_design.objective
    profile_name = _deliverable_profile(domain_profile, work_design, files, metadata, source_design_doc)
    manual_required = _should_export_manual(domain_profile, work_design, files, metadata)

    if profile_name == "software-development":
        return _export_software_development(
            export_dir,
            workflow_id,
            domain_profile,
            work_design,
            source_design_doc,
            files,
            profile_name,
            manual_required,
            metadata,
        )
    if profile_name == "product-design":
        return _export_product_design(
            export_dir, workflow_id, domain_profile, work_design, source_design_doc, files, profile_name
        )
    if profile_name == "investment-analysis":
        return _export_investment_analysis(
            export_dir, workflow_id, domain_profile, work_design, source_design_doc, files, profile_name
        )
    return _export_general_orchestration(
        export_dir,
        workflow_id,
        domain_profile,
        work_design,
        source_design_doc,
        files,
        profile_name,
        source_title,
        manual_required,
        metadata,
    )


def _export_general_orchestration(
    export_dir: Path,
    workflow_id: str,
    profile: DomainProfile,
    design: WorkDesign,
    source_design_doc: str,
    file_list: List[str],
    profile_name: str,
    source_title: str,
    manual_required: bool,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    evidence = list(DELIVERABLE_EVIDENCE)
    deliverables = [
        _write_docx_deliverable(
            export_dir / "requirements_brief.docx",
            workflow_id,
            "requirements-brief",
            "Requirements Brief",
            "requirements brief exported",
            _requirements_sections(profile, design, source_title, source_design_doc),
        ),
        _write_docx_deliverable(
            export_dir / "orchestration_design.docx",
            workflow_id,
            "orchestration-design",
            "Orchestration Design",
            "orchestration design exported",
            _orchestration_sections(profile, design),
        ),
        _write_docx_deliverable(
            export_dir / "deliverable_definition.docx",
            workflow_id,
            "deliverable-definition",
            "Deliverable Definition",
            "deliverable definition exported",
            _deliverable_sections(design, file_list),
        ),
        _write_docx_deliverable(
            export_dir / "process_flow.docx",
            workflow_id,
            "process-flow",
            "Process Flow",
            "process flow exported",
            _process_flow_sections(design),
        ),
        _write_xlsx_deliverable(
            export_dir / "role_task_breakdown.xlsx",
            workflow_id,
            "role-task-breakdown",
            "Role Task Breakdown",
            "role task breakdown exported",
            _role_task_rows(profile, design, file_list),
        ),
        _write_xlsx_deliverable(
            export_dir / "evidence_plan.xlsx",
            workflow_id,
            "evidence-plan",
            "Evidence Plan",
            "evidence plan exported",
            _evidence_rows(design, evidence),
        ),
        _write_xlsx_deliverable(
            export_dir / "risk_policy_checklist.xlsx",
            workflow_id,
            "risk-policy-checklist",
            "Risk Policy Checklist",
            "risk policy checklist exported",
            _risk_policy_rows(design),
        ),
    ]
    if manual_required:
        evidence.append("manual exported")
        deliverables.append(
            _write_docx_deliverable(
                export_dir / "user_manual.docx",
                workflow_id,
                "user-manual",
                "User Manual",
                "manual exported",
                _manual_sections(workflow_id, profile, design, file_list, metadata),
            )
        )
    return _final_export_result(export_dir, workflow_id, profile_name, design, deliverables, evidence)


def _export_software_development(
    export_dir: Path,
    workflow_id: str,
    profile: DomainProfile,
    design: WorkDesign,
    source_design_doc: str,
    file_list: List[str],
    profile_name: str,
    manual_required: bool,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    features = _software_feature_names(design, source_design_doc, file_list)
    evidence = [
        "requirements brief exported",
        "functional specification exported",
        "development design exported",
        "screen api definition exported",
        "data definition exported",
        "role task breakdown exported",
        "test verification plan exported",
        "risk policy checklist exported",
    ]
    deliverables = [
        _write_docx_deliverable(
            export_dir / "requirements_brief.docx",
            workflow_id,
            "requirements-brief",
            "Requirements Brief",
            "requirements brief exported",
            _requirements_sections(profile, design, _first_heading(source_design_doc), source_design_doc),
            artifact_type="requirements-brief",
        ),
        _write_docx_deliverable(
            export_dir / "functional_specification.docx",
            workflow_id,
            "functional-specification",
            "Functional Specification",
            "functional specification exported",
            _functional_spec_sections(profile, design, features, source_design_doc),
            artifact_type="functional-specification",
        ),
        _write_docx_deliverable(
            export_dir / "development_design.docx",
            workflow_id,
            "development-design",
            "Development Design",
            "development design exported",
            _development_design_sections(profile, design, features, file_list),
            artifact_type="development-design",
        ),
        _write_docx_deliverable(
            export_dir / "screen_api_definition.docx",
            workflow_id,
            "screen-api-definition",
            "Screen and API Definition",
            "screen api definition exported",
            _screen_api_sections(features, source_design_doc),
            artifact_type="screen-api-definition",
        ),
        _write_xlsx_deliverable(
            export_dir / "data_definition.xlsx",
            workflow_id,
            "data-definition",
            "Data Definition",
            "data definition exported",
            _software_data_rows(features),
            artifact_type="data-definition",
        ),
        _write_xlsx_deliverable(
            export_dir / "role_task_breakdown.xlsx",
            workflow_id,
            "role-task-breakdown",
            "Role Task Breakdown",
            "role task breakdown exported",
            _role_task_rows(profile, design, file_list),
            artifact_type="role-task-breakdown",
        ),
        _write_xlsx_deliverable(
            export_dir / "test_verification_plan.xlsx",
            workflow_id,
            "test-verification-plan",
            "Test Verification Plan",
            "test verification plan exported",
            _software_test_rows(features, design),
            artifact_type="test-verification-plan",
        ),
        _write_xlsx_deliverable(
            export_dir / "risk_policy_checklist.xlsx",
            workflow_id,
            "risk-policy-checklist",
            "Risk Policy Checklist",
            "risk policy checklist exported",
            _risk_policy_rows(design),
            artifact_type="risk-policy-checklist",
        ),
    ]
    if manual_required:
        evidence.append("manual exported")
        deliverables.append(
            _write_docx_deliverable(
                export_dir / "user_manual.docx",
                workflow_id,
                "user-manual",
                "User Manual",
                "manual exported",
                _manual_sections(workflow_id, profile, design, file_list, metadata),
                artifact_type="user-manual",
            )
        )
    return _final_export_result(export_dir, workflow_id, profile_name, design, deliverables, evidence)


def _export_product_design(
    export_dir: Path,
    workflow_id: str,
    profile: DomainProfile,
    design: WorkDesign,
    source_design_doc: str,
    file_list: List[str],
    profile_name: str,
) -> Dict[str, Any]:
    product_name = _product_name(design, source_design_doc, file_list)
    evidence = [
        "product design document exported",
        "dimension bom exported",
        "technical drawing exported",
        "cad drawing exported",
    ]
    deliverables = [
        _write_docx_deliverable(
            export_dir / "product_design_document.docx",
            workflow_id,
            "product-design-document",
            "Product Design Document",
            "product design document exported",
            _product_design_sections(profile, design, source_design_doc, product_name),
            artifact_type="design-document",
        ),
        _write_xlsx_deliverable(
            export_dir / "dimension_bom.xlsx",
            workflow_id,
            "dimension-bom",
            "Dimension BOM",
            "dimension bom exported",
            _dimension_bom_rows(design, source_design_doc, product_name),
            artifact_type="table-model",
        ),
        _write_svg_deliverable(
            export_dir / "concept_drawing.svg",
            workflow_id,
            "concept-drawing-svg",
            "Concept Drawing",
            "technical drawing exported",
            _concept_svg(product_name, design, source_design_doc),
            artifact_type="technical-drawing",
        ),
        _write_dxf_deliverable(
            export_dir / "concept_drawing.dxf",
            workflow_id,
            "concept-drawing-dxf",
            "Concept Drawing DXF",
            "cad drawing exported",
            _concept_dxf(product_name, source_design_doc),
            artifact_type="cad-drawing",
        ),
    ]
    return _final_export_result(export_dir, workflow_id, profile_name, design, deliverables, evidence)


def _export_investment_analysis(
    export_dir: Path,
    workflow_id: str,
    profile: DomainProfile,
    design: WorkDesign,
    source_design_doc: str,
    file_list: List[str],
    profile_name: str,
) -> Dict[str, Any]:
    evidence = [
        "investment analysis report exported",
        "scenario model exported",
        "risk policy checklist exported",
    ]
    deliverables = [
        _write_docx_deliverable(
            export_dir / "investment_analysis_report.docx",
            workflow_id,
            "investment-analysis-report",
            "Investment Analysis Report",
            "investment analysis report exported",
            _investment_analysis_sections(profile, design, source_design_doc),
            artifact_type="analysis-report",
        ),
        _write_xlsx_deliverable(
            export_dir / "scenario_model.xlsx",
            workflow_id,
            "scenario-model",
            "Scenario Model",
            "scenario model exported",
            _scenario_model_rows(design, file_list),
            artifact_type="scenario-model",
        ),
        _write_xlsx_deliverable(
            export_dir / "risk_policy_checklist.xlsx",
            workflow_id,
            "risk-policy-checklist",
            "Risk Policy Checklist",
            "risk policy checklist exported",
            _risk_policy_rows(design),
            artifact_type="risk-policy-checklist",
        ),
    ]
    return _final_export_result(export_dir, workflow_id, profile_name, design, deliverables, evidence)


def _requirements_sections(
    profile: DomainProfile,
    design: WorkDesign,
    source_title: str,
    source_design_doc: str,
) -> List[Dict[str, Any]]:
    return [
        {"heading": "Document Info", "items": _document_info_lines("Requirements Brief", design)},
        {"heading": "Revision History", "items": _revision_history_lines()},
        {"heading": "Background and Purpose", "paragraphs": [source_title or design.objective or profile.objective]},
        {"heading": "Scope", "paragraphs": [design.scope or "Scope is not specified yet."]},
        {"heading": "Terms and Abbreviations", "items": ["Evidence: structured proof for completion or gate passage", "Gate: review point for quality, risk, QA, or release decisions"]},
        {"heading": "Stakeholders", "items": _role_summary_lines(profile, design)},
        {"heading": "Functional Requirements", "items": _functional_requirement_lines(design)},
        {"heading": "Non-Functional Requirements", "items": [
            "Deliverables must be readable in their target format.",
            "Internal workflow state must stay separate from user-facing project artifacts.",
            "Completion must be based on evidence and gate results.",
        ]},
        {"heading": "Acceptance Criteria", "items": _acceptance_criteria_lines(design)},
        {"heading": "Open Questions", "items": _open_question_lines(design, source_design_doc)},
    ]


def _orchestration_sections(profile: DomainProfile, design: WorkDesign) -> List[Dict[str, Any]]:
    return [
        {"heading": "Document Info", "items": _document_info_lines("Orchestration Design", design)},
        {"heading": "Design Principles", "items": [
            "Separate user deliverables from internal runtime state.",
            "Route unclear objectives through brainstorming or design before implementation.",
            "Use bounded parallel execution only when dependencies and shared state are clear.",
        ]},
        {"heading": "Role DAG", "items": _role_dag_lines(profile, design)},
        {"heading": "Dependencies", "items": _dependency_lines(profile, design)},
        {"heading": "Parallel Execution Strategy", "items": [
            "Fan out independent roles or file tasks after scope approval.",
            "Fan in task results, artifacts, and evidence before review gates.",
            "Block downstream roles when prerequisite gates fail.",
        ]},
        {"heading": "State Stores", "items": [
            "User deliverables: project docs folder.",
            "Runtime state: UAF runtime root.",
            "Memory candidates: scoped candidate store, not host-global memory by default.",
        ]},
        {"heading": "Gate Design", "items": _gate_design_lines(design)},
        {"heading": "Failure and Rework Procedure", "items": [
            "Failed review returns work to the responsible role.",
            "Failed QA requires additional verification evidence.",
            "Failed risk/policy checks require owner, mitigation, and approval conditions.",
        ]},
    ]


def _deliverable_sections(design: WorkDesign, file_list: List[str]) -> List[Dict[str, Any]]:
    return [
        {"heading": "Deliverable List", "items": list(design.deliverables) or ["final output"]},
        {"heading": "Deliverable Definitions", "items": _deliverable_detail_lines(design, file_list)},
        {"heading": "Input Materials", "items": file_list or ["user prompt and approved design"]},
        {"heading": "Quality Criteria", "items": [
            "Each deliverable has a clear purpose, input, validation method, and blocking criteria.",
            "Typed files pass structural QA before completion is claimed.",
        ]},
        {"heading": "Approval Criteria", "items": _acceptance_criteria_lines(design)},
        {"heading": "Storage Location", "items": ["User-facing deliverables are written under project docs."]},
    ]


def _process_flow_sections(design: WorkDesign) -> List[Dict[str, Any]]:
    return [
        {"heading": "Process Overview", "items": [
            "1. Intake objective, target, expected deliverables, and constraints.",
            "2. Classify domain and required deliverable profile.",
            "3. Prepare WorkDesign with scope, roles, evidence, and risk gates.",
            "4. Separate user deliverables from runtime artifacts.",
            "5. Dispatch approved independent roles or file tasks.",
            "6. Fan in task results, role artifacts, and evidence records.",
            "7. Run review, QA, security, and release gates.",
            "8. Complete only when required evidence is present; otherwise remain blocked.",
        ]},
        {"heading": "Swimlanes", "items": [
            "Requester: objective, constraints, and approval.",
            "Controller: planning, role assignment, progress state.",
            "Specialists: deliverable production and evidence capture.",
            "Review/QA/Risk: verification and release decision.",
        ]},
        {"heading": "Step-by-Step Flow", "items": list(design.design_artifacts or design.deliverables) or ["No task breakdown provided yet."]},
        {"heading": "Decision Points", "items": [
            "Is the objective approved?",
            "Are required inputs present?",
            "Can work be parallelized without shared-state conflict?",
            "Did every required gate pass?",
        ]},
        {"heading": "Exception Flow", "items": [
            "Missing input: ask for the smallest required clarification.",
            "Failed verification: record the failing evidence and rework loop.",
            "Policy block: record owner, mitigation, and approval condition.",
        ]},
        {"heading": "Rework Loop", "items": ["Finding -> owner assignment -> patch or revision -> focused verification -> gate re-run."]},
    ]


def _manual_sections(
    workflow_id: str,
    profile: DomainProfile,
    design: WorkDesign,
    file_list: List[str],
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    revision = str(metadata.get("manual_revision") or "Rev. 1.0")
    note = str(metadata.get("manual_revision_note") or "Initial manual")
    return [
        {"heading": "Revision History", "items": [f"{revision}: {note}"]},
        {"heading": "Audience", "items": ["Operators, reviewers, maintainers, and handoff recipients."]},
        {"heading": "Prerequisites", "items": file_list or ["Approved objective and generated deliverables."]},
        {"heading": "Procedure", "items": [
            "Open the relevant deliverable for the task.",
            "Check the evidence plan before claiming completion.",
            "Use the risk checklist when blocked or uncertain.",
        ]},
        {"heading": "Troubleshooting", "items": [
            "If evidence is missing, inspect the evidence plan and gate findings.",
            "If a file cannot be opened, re-run artifact render QA.",
        ]},
        {"heading": "Support", "items": [f"Workflow ID: {workflow_id}", f"Domain: {profile.domain_name}"]},
    ]


def _functional_spec_sections(
    profile: DomainProfile,
    design: WorkDesign,
    features: List[str],
    source_design_doc: str,
) -> List[Dict[str, Any]]:
    return [
        {"heading": "Document Info", "items": _document_info_lines("Functional Specification", design)},
        {"heading": "Revision History", "items": _revision_history_lines()},
        {"heading": "Feature Overview", "paragraphs": ["This document defines implementable feature boundaries, inputs, outputs, validation, and acceptance criteria."]},
        {"heading": "Feature List", "items": _feature_list_lines(features)},
        {"heading": "Feature Details", "items": _feature_detail_lines(features)},
        {"heading": "Screens and Menus", "items": _screen_definition_lines(features)},
        {"heading": "Permissions", "items": _permission_lines(source_design_doc)},
        {"heading": "Input and Output", "items": _io_lines(features)},
        {"heading": "Processing Rules", "items": _processing_rule_lines(features)},
        {"heading": "Exception and Validation Rules", "items": _validation_rule_lines(features)},
        {"heading": "Acceptance Criteria", "items": _software_acceptance_lines(features, design)},
        {"heading": "Traceability", "items": _software_traceability_lines(features, design)},
    ]


def _development_design_sections(
    profile: DomainProfile,
    design: WorkDesign,
    features: List[str],
    file_list: List[str],
) -> List[Dict[str, Any]]:
    return [
        {"heading": "Document Info", "items": _document_info_lines("Development Design", design)},
        {"heading": "System Context", "items": _system_context_lines(profile, design, file_list)},
        {"heading": "Architecture", "items": _architecture_lines(profile, design, file_list)},
        {"heading": "Module Design", "items": _module_design_lines(features, file_list)},
        {"heading": "Interface Design", "items": _api_definition_lines(features)},
        {"heading": "Database Design", "items": _database_design_lines(features)},
        {"heading": "Processing Flow", "items": _data_flow_lines(features)},
        {"heading": "Error Handling and Logging", "items": _error_handling_lines(features)},
        {"heading": "Security and Permissions", "items": _security_lines(design)},
        {"heading": "Deployment and Operations", "items": _deployment_operation_lines()},
        {"heading": "Test Strategy", "items": _test_strategy_lines(features)},
    ]


def _screen_api_sections(features: List[str], source_design_doc: str) -> List[Dict[str, Any]]:
    return [
        {"heading": "Screen List", "items": _screen_definition_lines(features)},
        {"heading": "Screen Layout", "items": _screen_layout_lines(features)},
        {"heading": "Screen Field Definitions", "items": _screen_field_lines(features)},
        {"heading": "Event Definitions", "items": _user_action_lines(features)},
        {"heading": "API List", "items": _api_definition_lines(features)},
        {"heading": "API Definition", "items": _api_definition_lines(features)},
        {"heading": "Request and Response", "items": _request_response_lines(features)},
        {"heading": "Status Codes", "items": _screen_api_error_lines(features)},
        {"heading": "Permissions", "items": _permission_lines(source_design_doc)},
    ]


def _product_design_sections(
    profile: DomainProfile,
    design: WorkDesign,
    source_design_doc: str,
    product_name: str,
) -> List[Dict[str, Any]]:
    return [
        {"heading": "Document Info", "items": _document_info_lines("Product Design Document", design)},
        {"heading": "Revision History", "items": _revision_history_lines()},
        {"heading": "Design Overview", "paragraphs": [design.objective or profile.objective]},
        {"heading": "Product and Specification Identity", "paragraphs": [product_name]},
        {"heading": "Specification Summary", "items": _product_spec_summary_lines(source_design_doc, product_name)},
        {"heading": "Design Requirements", "items": _product_requirement_lines(design, source_design_doc)},
        {"heading": "Dimension Basis", "items": _dimension_basis_lines(source_design_doc)},
        {"heading": "BOM", "items": _product_bom_summary_lines(product_name)},
        {"heading": "Drawing List", "items": ["product_design_document.docx", "dimension_bom.xlsx", "concept_drawing.svg", "concept_drawing.dxf"]},
        {"heading": "Verification Method", "items": _product_verification_lines(design)},
        {"heading": "Manufacturing Readiness Checks", "items": [
            "Treat drawings as concept deliverables when dimensions, tolerances, or materials are incomplete.",
            "Verify the source specification, measured data, and approval drawing number before manufacturing.",
        ]},
        {"heading": "Approval Criteria", "items": _product_approval_lines()},
        {"heading": "Source Specification or Request", "paragraphs": [_compact_text(source_design_doc)]},
    ]


def _investment_analysis_sections(
    profile: DomainProfile,
    design: WorkDesign,
    source_design_doc: str,
) -> List[Dict[str, Any]]:
    return [
        {"heading": "Document Info", "items": _document_info_lines("Investment Analysis Report", design)},
        {"heading": "Executive Summary", "paragraphs": ["Summarize the decision context, assumptions, scenarios, risks, and evidence conditions."]},
        {"heading": "Investment Overview", "paragraphs": [design.objective or profile.objective]},
        {"heading": "Analysis Scope", "paragraphs": [design.scope or "not specified"]},
        {"heading": "Key Assumptions", "items": _investment_assumption_lines(source_design_doc)},
        {"heading": "Scenario Analysis", "items": _investment_scenario_lines()},
        {"heading": "Return and Risk Analysis", "items": _investment_risk_return_lines(design)},
        {"heading": "Core Deliverables", "items": ["investment_analysis_report.docx", "scenario_model.xlsx", "risk_policy_checklist.xlsx"]},
        {"heading": "Review Criteria", "items": design.evidence_required},
        {"heading": "Risks", "items": design.risk_policy_checks},
        {"heading": "Final View", "items": ["Proceed, hold, reject, or request more evidence based on collected data."]},
        {"heading": "Disclaimer", "items": ["This deliverable is decision-support material, not definitive investment, legal, tax, or financial advice."]},
        {"heading": "Source Request", "paragraphs": [_compact_text(source_design_doc)]},
    ]


def _role_task_rows(profile: DomainProfile, design: WorkDesign, file_list: List[str]) -> List[List[str]]:
    rows = [["WBS ID", "Task Name", "Input", "Output", "Done Criteria", "Dependency", "Priority", "Evidence"]]
    roles = list(profile.roles) or [DomainRole(name="controller", purpose="plan and coordinate work", produces=["work design"])]
    for index, role in enumerate(roles, start=1):
        rows.append([
            f"WBS-{index:03d}",
            role.name,
            ", ".join(file_list) or design.scope or design.objective,
            ", ".join(role.produces or design.deliverables or ["final output"]),
            _role_done_definition(role, design),
            "previous gate" if index > 1 else "scope approval",
            _role_priority(role),
            _role_evidence_text(role, design),
        ])
    while len(rows) < 10:
        index = len(rows)
        rows.append([f"WBS-X{index:02d}", "quality follow-up", "gate finding", "updated evidence", "gate passes", "review", "medium", "quality evidence"])
    return rows


def _evidence_rows(design: WorkDesign, export_evidence: List[str]) -> List[List[str]]:
    rows = [["Evidence ID", "Evidence Key", "Deliverable", "Verification Method", "Collection Point", "Owner", "Pass Criteria", "Block Criteria"]]
    for index, evidence in enumerate(_unique(list(export_evidence) + list(design.evidence_required)), start=1):
        rows.append([f"EV-{index:03d}", evidence, "deliverable or runtime evidence", "structural check and review gate", "before completion", "controller", "evidence is present and readable", "evidence missing or failed"])
    while len(rows) < 10:
        index = len(rows)
        rows.append([f"EV-X{index:02d}", "additional evidence", "final output", "manual review", "release", "reviewer", "accepted", "unresolved finding"])
    return rows


def _risk_policy_rows(design: WorkDesign) -> List[List[str]]:
    rows = [["Risk ID", "Category", "Risk Item", "Impact", "Probability", "Risk Level", "Mitigation", "Owner", "Block Criteria"]]
    risks = list(design.risk_policy_checks) or ["missing evidence", "unsafe file operation", "scope drift"]
    for index, risk in enumerate(risks, start=1):
        rows.append([f"RISK-{index:03d}", _risk_category(risk), risk, _risk_impact(risk), _risk_probability(risk), _risk_level(risk), _risk_mitigation(risk), "controller", _risk_block_condition(risk)])
    while len(rows) < 8:
        index = len(rows)
        rows.append([f"RISK-X{index:02d}", "quality", "unreviewed output", "medium", "medium", "medium", "run review gate", "reviewer", "review missing"])
    return rows


def _software_data_rows(features: List[str]) -> List[List[str]]:
    rows = [["Table Name", "Column Name", "Field Name", "Data Type", "Length", "PK", "FK", "Required", "Default", "Description", "Validation Rule"]]
    for index, feature in enumerate(features, start=1):
        entity = _entity_name(feature, index)
        rows.extend([
            [entity, "id", "id", "string", "64", "Y", "", "Y", "", "identifier", "unique"],
            [entity, "name", "name", "string", "200", "", "", "Y", "", "display name", "not empty"],
            [entity, "status", "status", "string", "40", "", "", "Y", "active", "state", "known state"],
            [entity, "updated_at", "updated_at", "datetime", "", "", "", "Y", "now", "audit timestamp", "valid datetime"],
        ])
    return rows[: max(8, len(rows))]


def _software_test_rows(features: List[str], design: WorkDesign) -> List[List[str]]:
    rows = [["Test ID", "Test Type", "Feature", "Scenario", "Precondition", "Input", "Steps", "Expected Result", "Verification Method", "Evidence Key", "Owner", "Block Criteria"]]
    for index, feature in enumerate(features, start=1):
        rows.append([f"TC-{index:03d}-happy", "functional", feature, "happy path", "valid input", "sample data", "execute main action", "expected output is visible", "unit/integration/browser or command check", _evidence_for_index(design, index), "qa", "failed assertion"])
        rows.append([f"TC-{index:03d}-validation", "negative", feature, "invalid input", "invalid input", "bad data", "submit invalid data", "clear validation error", "focused test", _evidence_for_index(design, index), "qa", "missing validation"])
    while len(rows) < 8:
        index = len(rows)
        rows.append([f"TC-X{index:02d}", "regression", "shared behavior", "gate regression", "buildable project", "sample", "run verification", "no regression", "test command", "verification evidence", "qa", "test failed"])
    return rows


def _dimension_bom_rows(design: WorkDesign, source_design_doc: str, product_name: str) -> List[List[str]]:
    spec = _product_spec_from_text(source_design_doc)
    dimensions = spec["dimensions"] or "TBD"
    material = spec["material"] or "TBD"
    hole_spec = spec["hole_spec"] or "TBD"
    hole_count = str(spec["hole_count"] or "TBD")
    return [
        ["Part No", "Part Name", "Material", "Specification", "Dimension", "Quantity", "Tolerance", "Basis", "Notes"],
        ["P-001", product_name, material, "CABLE GLAND PLATE", dimensions, "1", "TBD", "user input", "concept only until approved drawing"],
        ["H-001", "Cable gland holes", material, hole_spec, dimensions, hole_count, "TBD", "user input", "verify pitch, edge distance, and tolerance"],
        ["E-001", "Power rating reference", "N/A", _extract_power_rating(source_design_doc), "N/A", "1", "N/A", "user input", "electrical rating is not enough to finalize mechanical dimensions"],
        ["D-001", "Concept SVG drawing", "N/A", "review drawing", "concept", "1", "N/A", "UAF export", "review before manufacturing release"],
        ["D-002", "Concept DXF drawing", "N/A", "CAD handoff", "concept", "1", "N/A", "UAF export", "review before manufacturing release"],
        ["Q-001", "Verification evidence", "N/A", "; ".join(design.evidence_required), "N/A", "1", "N/A", "work design", "approval required before manufacture"],
    ]


def _scenario_model_rows(design: WorkDesign, file_list: List[str]) -> List[List[str]]:
    return [
        ["Scenario", "Assumption Item", "Base Value", "Upside", "Base", "Downside", "Sensitivity", "Basis", "Notes"],
        ["Upside", "growth / return", "to be filled from source data", "high", "", "", "high", "source data", "optimistic assumption"],
        ["Base", "growth / return", "to be filled from source data", "", "base", "", "medium", "source data", "base assumption"],
        ["Downside", "growth / return", "to be filled from source data", "", "", "low", "high", "source data", "conservative assumption"],
        ["Input", "target", "; ".join(file_list) or "investment thesis", "", "base", "", "medium", "user input", "analysis target"],
        ["Evidence", "required evidence", "; ".join(design.evidence_required), "", "required", "", "high", "work design", "block if missing"],
    ]


def _document_info_lines(title: str, design: WorkDesign) -> List[str]:
    return [
        f"Document Name: {title}",
        f"Generated At: {datetime.now(timezone.utc).isoformat()}",
        f"Objective: {design.objective or 'not specified'}",
        f"Scope: {design.scope or 'not specified'}",
    ]


def _revision_history_lines() -> List[str]:
    return ["Rev. 1.0: Initial generated deliverable."]


def _role_summary_lines(profile: DomainProfile, design: WorkDesign) -> List[str]:
    roles = list(profile.roles) or []
    if not roles:
        return ["controller: coordinate work, evidence, review, and release gates"]
    return [f"{role.name}: {role.purpose}; {'; '.join(role.responsibilities)}" for role in roles]


def _functional_requirement_lines(design: WorkDesign) -> List[str]:
    deliverables = list(design.deliverables) or ["final output"]
    return [f"FR-{index:03d}: Produce and verify {item}." for index, item in enumerate(deliverables, start=1)]


def _acceptance_criteria_lines(design: WorkDesign) -> List[str]:
    evidence = list(design.evidence_required) or ["workflow dispatch completed"]
    return [
        "Every required deliverable exists and passes format-specific structural checks.",
        "Review, QA, risk, and release gates either pass or record explicit blocking reasons.",
    ] + [f"Evidence required: {item}" for item in evidence]


def _open_question_lines(design: WorkDesign, source_design_doc: str) -> List[str]:
    questions = []
    if not design.scope:
        questions.append("Confirm the exact scope boundary.")
    if not design.evidence_required:
        questions.append("Confirm required completion evidence.")
    if "TBD" in source_design_doc.upper():
        questions.append("Resolve TBD values before release.")
    return questions or ["No open questions recorded at generation time."]


def _role_dag_lines(profile: DomainProfile, design: WorkDesign) -> List[str]:
    roles = list(profile.roles) or []
    if not roles:
        return ["controller -> specialist -> reviewer -> QA -> release"]
    return [f"{index}. {role.name}: {role.purpose}; {'; '.join(role.responsibilities)}" for index, role in enumerate(roles, start=1)]


def _dependency_lines(profile: DomainProfile, design: WorkDesign) -> List[str]:
    return [
        "Scope approval precedes implementation.",
        "Independent role or file tasks can run in parallel after planning.",
        "Review and QA gates require task results plus evidence records.",
    ]


def _gate_design_lines(design: WorkDesign) -> List[str]:
    gates = list(design.review_gates) or ["review gate", "qa gate", "release gate"]
    return [f"{gate}: verify deliverables, evidence, and blocking findings." for gate in gates]


def _deliverable_detail_lines(design: WorkDesign, file_list: List[str]) -> List[str]:
    deliverables = list(design.deliverables) or ["final output"]
    return [f"{item}: generated from {', '.join(file_list) if file_list else 'approved source material'} and validated before completion." for item in deliverables]


def _feature_list_lines(features: List[str]) -> List[str]:
    return [f"F-{index:03d}: {feature}" for index, feature in enumerate(features, start=1)]


def _feature_detail_lines(features: List[str]) -> List[str]:
    lines = []
    for index, feature in enumerate(features, start=1):
        lines.extend([
            f"F-{index:03d} purpose: enable the user to complete {feature} with clear input and output.",
            "Normal flow: validate input, execute use case, persist or read data, return result.",
            "Postcondition: result is visible and audit or evidence data is recorded.",
        ])
    return lines


def _screen_definition_lines(features: List[str]) -> List[str]:
    return [f"SCR-{index:03d}: {feature} view includes input/search, result, and error/status areas." for index, feature in enumerate(features, start=1)]


def _permission_lines(source_design_doc: str) -> List[str]:
    return [
        "viewer/end user: read and confirm results",
        "operator: create, update, or execute permitted actions",
        "approver: approve, reject, or hold when workflow requires it",
        "administrator: configure data, permissions, and correction rules",
    ]


def _io_lines(features: List[str]) -> List[str]:
    lines = []
    for feature in features:
        lines.append(f"{feature} input: user request, required identifiers, filters, and change data.")
        lines.append(f"{feature} output: success/failure status, visible message, updated data, or API response.")
    return lines


def _processing_rule_lines(features: List[str]) -> List[str]:
    return [
        "Common order: permission check -> input validation -> use case execution -> persistence/read -> response -> evidence.",
        "Avoid partial writes when validation or downstream persistence fails.",
    ] + [f"{feature}: validate before and after processing." for feature in features]


def _validation_rule_lines(features: List[str]) -> List[str]:
    return [
        "Required values, data type errors, permission failures, duplicate identifiers, and unsafe paths must produce clear errors.",
        "Failures should preserve retry or correction paths.",
    ] + [f"{feature}: verify happy path, validation failure, permission failure, and duplicate/conflict flow." for feature in features]


def _software_acceptance_lines(features: List[str], design: WorkDesign) -> List[str]:
    lines = [
        "AC-DEV-001: Every feature is traced to implementation or an explicit exclusion.",
        "AC-DEV-002: Each feature has happy path and validation failure verification.",
        "AC-DEV-003: Code quality findings, failed tests, or missing evidence block release.",
    ]
    for index, feature in enumerate(features, start=1):
        lines.append(f"AC-F-{index:03d}: {feature} satisfies input, processing, output, and error handling criteria.")
    return lines


def _software_traceability_lines(features: List[str], design: WorkDesign) -> List[str]:
    evidence = list(design.evidence_required) or ["verification evidence"]
    return [
        f"{feature} -> requirement F-{index:03d} -> test TC-{index:03d}-happy/validation -> evidence {evidence[(index - 1) % len(evidence)]}"
        for index, feature in enumerate(features, start=1)
    ]


def _system_context_lines(profile: DomainProfile, design: WorkDesign, file_list: List[str]) -> List[str]:
    return [
        f"Domain: {profile.domain_name}",
        f"Objective: {design.objective or profile.objective}",
        f"Target files/components: {', '.join(file_list) if file_list else 'to be selected after design'}",
    ]


def _architecture_lines(profile: DomainProfile, design: WorkDesign, file_list: List[str]) -> List[str]:
    return [
        "Presentation/UI layer: screen state, user input, and validation messages.",
        "Application/API layer: feature use cases, permissions, transaction boundaries, and error mapping.",
        "Data layer: persistence, query/filter, and audit fields.",
        "Verification layer: unit, integration, browser, or command checks converted to evidence.",
    ]


def _module_design_lines(features: List[str], file_list: List[str]) -> List[str]:
    targets = file_list or ["target module to be selected"]
    return [f"MOD-{index:03d}: {feature} -> target={targets[(index - 1) % len(targets)]} -> separate handler/service/test responsibilities." for index, feature in enumerate(features, start=1)]


def _api_definition_lines(features: List[str]) -> List[str]:
    return [f"API-{index:03d}: /api/{_api_slug(feature, index)} handles {feature} request/response and error mapping." for index, feature in enumerate(features, start=1)]


def _database_design_lines(features: List[str]) -> List[str]:
    return [f"{_entity_name(feature, index)}: id, name, status, updated_at, audit fields, and feature-specific attributes." for index, feature in enumerate(features, start=1)]


def _data_flow_lines(features: List[str]) -> List[str]:
    return [f"{feature}: UI/API request -> validation -> use case -> data access -> response/evidence." for feature in features]


def _error_handling_lines(features: List[str]) -> List[str]:
    return [
        "ValidationError: classify as user-correctable input problem.",
        "PermissionError: block without data mutation.",
        "ConflictError: require latest-state review.",
        "UnhandledError: hide internal details from user-facing output and keep diagnostic evidence.",
    ] + [f"{feature}: preserve rollback or no-op state on failure." for feature in features]


def _security_lines(design: WorkDesign) -> List[str]:
    return [
        "Validate input at UI/API boundaries and never skip server-side validation.",
        "Put role or permission checks before protected feature flows.",
        "Do not store secrets, tokens, personal data, or credentials in logs, deliverables, or durable memory.",
        "Risk checklist blockers must be evaluated at release gate.",
    ]


def _deployment_operation_lines() -> List[str]:
    return [
        "Build and verification commands should be documented with exit codes.",
        "Runtime configuration should be separated from generated deliverables.",
        "Rollback or no-op behavior should be defined for failed writes.",
    ]


def _test_strategy_lines(features: List[str]) -> List[str]:
    return [f"{feature}: cover happy path, validation failure, permission failure, and regression evidence." for feature in features]


def _screen_layout_lines(features: List[str]) -> List[str]:
    return [f"{feature}: top filter/input area, central data/result area, bottom status/error area." for feature in features]


def _screen_field_lines(features: List[str]) -> List[str]:
    rows = []
    for feature in features:
        rows.extend([
            f"{feature}-id: identifier / read-only or hidden / required for update/delete",
            f"{feature}-name: display name or title / text / required",
            f"{feature}-status: status / select or badge / required",
            f"{feature}-message: error and guidance message / display / optional",
        ])
    return rows


def _user_action_lines(features: List[str]) -> List[str]:
    return [f"ACT-{index:03d}: user can search, input/update, save/execute, and confirm result for {feature}." for index, feature in enumerate(features, start=1)]


def _request_response_lines(features: List[str]) -> List[str]:
    return [f"{feature}: request includes identifiers and payload; response includes status, message, data, and evidence/audit reference." for feature in features]


def _screen_api_error_lines(features: List[str]) -> List[str]:
    return [
        "200 OK: success",
        "400 Validation Error: user-correctable input problem",
        "403 Forbidden: permission denied",
        "409 Conflict: duplicate or stale state",
        "500 Internal Error: unexpected failure with diagnostic evidence",
    ]


def _product_spec_summary_lines(source_design_doc: str, product_name: str) -> List[str]:
    spec = _product_spec_from_text(source_design_doc)
    return [
        f"Product/specification name: {product_name}",
        f"Power rating: {_extract_power_rating(source_design_doc)}",
        f"Dimension reference: {spec['dimensions'] or 'not specified'}",
        f"Material reference: {spec['material'] or 'not specified'}",
        f"Hole reference: {spec['hole_count'] or 'not specified'} x {spec['hole_spec'] or 'not specified'}",
        "Applied basis: supplied specification guide or user-provided specification.",
        "Drawing level: concept handoff when dimensions or tolerances are incomplete.",
    ]


def _product_requirement_lines(design: WorkDesign, source_design_doc: str) -> List[str]:
    return [
        "REQ-MECH-001: record product identity, specification name, and input guide source.",
        "REQ-MECH-002: distinguish confirmed dimensions, tolerances, materials, quantities, and TBD values.",
        "REQ-MECH-003: mark SVG/DXF outputs as concept or manufacturing-ready.",
        f"REQ-MECH-004: source request trace = {_compact_text(source_design_doc)}",
    ] + [f"Evidence: {item}" for item in design.evidence_required]


def _dimension_basis_lines(source_design_doc: str) -> List[str]:
    spec = _product_spec_from_text(source_design_doc)
    return [
        f"Overall dimensions: {spec['dimensions'] or 'source guide confirmation required'}",
        f"Hole/punch count and type: {spec['hole_count'] or 'source guide confirmation required'} x {spec['hole_spec'] or 'source guide confirmation required'}",
        f"Material: {spec['material'] or 'manufacturer/customer confirmation required'}",
        "Tolerance: manufacturer standard or customer approval required.",
        f"Power input reference: {_extract_power_rating(source_design_doc)}",
    ]


def _product_bom_summary_lines(product_name: str) -> List[str]:
    return [
        f"P-001 {product_name}: main plate or assembly",
        "E-001 power/spec reference: non-mechanical reference",
        "D-001/D-002 concept drawing outputs: SVG/DXF",
    ]


def _product_verification_lines(design: WorkDesign) -> List[str]:
    return [
        "Specification comparison: verify all dimensions and tolerances against source guide.",
        "Drawing review: verify SVG/DXF shape, hole count, labels, and scale note.",
        "BOM review: verify part number, name, material, quantity, tolerance, and basis.",
    ] + [f"Evidence required: {item}" for item in design.evidence_required]


def _product_approval_lines() -> List[str]:
    return [
        "Dimensions, tolerances, and materials must trace to source guide.",
        "Approved drawing number or approver must be recorded before manufacturing release.",
        "Do not approve as manufacturing-ready while TBD items remain.",
    ]


def _investment_assumption_lines(source_design_doc: str) -> List[str]:
    return [
        "Market/business assumption: requires source data or user-provided material.",
        "Financial assumption: revenue, cost, growth rate, discount rate, or return must be stated.",
        "Period assumption: analysis date and investment/exit period must be stated.",
        f"Source request summary: {_compact_text(source_design_doc)}",
    ]


def _investment_scenario_lines() -> List[str]:
    return [
        "Upside: separate optimistic assumption and sensitivity.",
        "Base: record base assumption and core evidence.",
        "Downside: record loss possibility and defensive condition.",
    ]


def _investment_risk_return_lines(design: WorkDesign) -> List[str]:
    return [
        "Expected return: calculate with return or cashflow when source data is available.",
        "Risk: separate market, execution, liquidity, regulation, and information-risk factors.",
        "Decision gate: hold conclusion when evidence or risk checks are insufficient.",
    ] + [f"Evidence required: {item}" for item in design.evidence_required]


def _role_done_definition(role: DomainRole, design: WorkDesign) -> str:
    return f"{role.name} outputs are present and mapped to evidence."


def _role_evidence_text(role: DomainRole, design: WorkDesign) -> str:
    evidence = list(design.evidence_required) or ["role artifact"]
    return evidence[0]


def _role_priority(role: DomainRole) -> str:
    name = role.name.lower()
    if any(token in name for token in ["ceo", "controller", "architect", "qa", "risk", "review"]):
        return "high"
    return "medium"


def _risk_category(item: str) -> str:
    lowered = item.lower()
    if any(token in lowered for token in ["security", "secret", "permission", "unsafe"]):
        return "security"
    if any(token in lowered for token in ["qa", "test", "quality", "evidence"]):
        return "quality"
    if any(token in lowered for token in ["scope", "policy", "approval"]):
        return "policy"
    return "execution"


def _risk_impact(item: str) -> str:
    return "high" if _risk_category(item) in {"security", "policy"} else "medium"


def _risk_probability(item: str) -> str:
    return "medium"


def _risk_level(item: str) -> str:
    return "high" if _risk_impact(item) == "high" else "medium"


def _risk_mitigation(item: str) -> str:
    return f"Assign owner, collect evidence, and re-run the relevant gate for: {item}"


def _risk_block_condition(item: str) -> str:
    return f"Block release while unresolved: {item}"


def _evidence_for_index(design: WorkDesign, index: int) -> str:
    evidence = list(design.evidence_required) or ["verification evidence"]
    return evidence[(index - 1) % len(evidence)]


def _software_feature_names(design: WorkDesign, source_design_doc: str, file_list: List[str]) -> List[str]:
    candidates = []
    candidates.extend(str(item) for item in design.deliverables if item)
    candidates.extend(str(item) for item in file_list if item)
    for line in source_design_doc.splitlines():
        stripped = line.strip(" #-*\t")
        if stripped and len(stripped) <= 80 and not stripped.lower().startswith("create "):
            candidates.append(stripped)
    cleaned = []
    for item in candidates:
        value = Path(item).stem if any(sep in item for sep in ["/", "\\"]) else item
        value = re.sub(r"[_-]+", " ", value).strip()
        if value and value.lower() not in {"docs", "src", "app", "index"}:
            cleaned.append(value)
    result = _unique(cleaned)[:6]
    return result or ["core workflow", "data management", "user interface"]


def _entity_name(feature: str, index: int) -> str:
    words = re.findall(r"[A-Za-z0-9]+", feature)
    base = "_".join(words[:3]).lower() or f"entity_{index}"
    return base[:40]


def _api_slug(feature: str, index: int) -> str:
    words = re.findall(r"[A-Za-z0-9]+", feature.lower())
    return "-".join(words[:4]) or f"feature-{index}"


def _concept_svg(product_name: str, design: WorkDesign, source_design_doc: str = "") -> str:
    spec = _product_spec_from_text(source_design_doc)
    width = spec.get("width") or 200.0
    height = spec.get("height") or 120.0
    hole_count = _parse_count(str(spec.get("hole_count") or "4"))
    hole_label = spec.get("hole_spec") or "M20"
    material = spec.get("material") or "TBD"
    circles = []
    positions = _hole_positions(width, height, hole_count)
    for x, y in positions:
        circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="none" stroke="#2563eb" stroke-width="2" />')
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width + 80:.0f}" height="{height + 90:.0f}" viewBox="0 0 {width + 80:.0f} {height + 90:.0f}">',
        '<rect width="100%" height="100%" fill="#ffffff" />',
        f'<rect x="40" y="40" width="{width:.1f}" height="{height:.1f}" fill="#f8fafc" stroke="#111827" stroke-width="2" />',
        *circles,
        f'<text x="40" y="{height + 70:.1f}" font-family="Arial" font-size="14">{escape(product_name)}</text>',
        f'<text x="40" y="25" font-family="Arial" font-size="13">Material: {escape(material)} | Holes: {hole_count} x {escape(hole_label)} | Size: {_format_number(width)}x{_format_number(height)}</text>',
        '</svg>',
    ])


def _concept_dxf(product_name: str, source_design_doc: str = "") -> str:
    spec = _product_spec_from_text(source_design_doc)
    width = spec.get("width") or 200.0
    height = spec.get("height") or 120.0
    hole_count = _parse_count(str(spec.get("hole_count") or "4"))
    material = spec.get("material") or "TBD"
    lines = [
        "0", "SECTION", "2", "ENTITIES",
        "0", "LWPOLYLINE", "8", "PLATE", "90", "4", "70", "1",
        "10", "0", "20", "0",
        "10", _format_number(width), "20", "0",
        "10", _format_number(width), "20", _format_number(height),
        "10", "0", "20", _format_number(height),
    ]
    for x, y in _hole_positions(width, height, hole_count):
        lines.extend(["0", "CIRCLE", "8", "HOLES", "10", _format_number(x), "20", _format_number(y), "40", "8"])
    lines.extend([
        "0", "TEXT", "8", "NOTES", "10", "0", "20", str(int(height + 20)), "40", "5",
        "1", _ascii_dxf_text(f"{product_name} {int(width)}x{int(height)} {material} {hole_count}x{spec.get('hole_spec') or 'M20'}"),
        "0", "ENDSEC", "0", "EOF",
    ])
    return "\n".join(lines)


def _hole_positions(width: float, height: float, count: int) -> List[tuple]:
    count = max(1, min(count, 12))
    if count == 1:
        return [(40 + width / 2, 40 + height / 2)]
    if count == 4:
        margin_x = min(35.0, width / 4)
        margin_y = min(25.0, height / 4)
        return [
            (40 + margin_x, 40 + margin_y),
            (40 + width - margin_x, 40 + margin_y),
            (40 + margin_x, 40 + height - margin_y),
            (40 + width - margin_x, 40 + height - margin_y),
        ]
    step = width / (count + 1)
    return [(40 + step * i, 40 + height / 2) for i in range(1, count + 1)]


def _deliverable_profile(
    profile: DomainProfile,
    design: WorkDesign,
    file_list: List[str],
    metadata: Dict[str, Any],
    source_design_doc: str,
) -> str:
    explicit = str(metadata.get("deliverable_profile") or metadata.get("artifact_profile") or "").strip().lower()
    if explicit:
        return explicit
    domain_hint = str(metadata.get("domain_hint") or profile.domain_name or design.domain or "").strip().lower()
    if domain_hint in {"software-development", "product-design", "investment-analysis", "general-orchestration"}:
        return domain_hint
    haystack = " ".join([
        domain_hint,
        str(metadata.get("scope") or ""),
        profile.domain_name,
        design.objective,
        design.scope,
        source_design_doc,
        " ".join(file_list),
        " ".join(design.deliverables),
    ]).lower()
    if _has_any(haystack, ["product", "drawing", "dxf", "svg", "bom", "dimension", "mechanical", "plate", "gland", "specification"]):
        return "product-design"
    if _has_any(haystack, ["investment", "portfolio", "valuation", "scenario", "return", "risk analysis", "research"]):
        return "investment-analysis"
    if _has_any(haystack, ["software", "application", "app", "api", "ui", "web", "database", "crud", "dashboard", "feature", "screen"]):
        return "software-development"
    return "general-orchestration"


def _should_export_manual(
    profile: DomainProfile,
    design: WorkDesign,
    file_list: List[str],
    metadata: Dict[str, Any],
) -> bool:
    if "export_manual" in metadata:
        return bool(metadata.get("export_manual"))
    haystack = " ".join([
        str(metadata.get("scope") or ""),
        profile.domain_name,
        design.objective,
        design.scope,
        " ".join(file_list),
        " ".join(design.deliverables),
    ]).lower()
    return _has_any(haystack, ["manual", "handoff", "operation", "procedure", "runbook", "training"])


def _write_docx_deliverable(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    evidence: str,
    sections: List[Dict[str, Any]],
    artifact_type: str = "",
    language: str = "en",
) -> Dict[str, str]:
    _write_docx(path, title, sections)
    return _deliverable_record(path, workflow_id, kind, title, "docx", evidence, artifact_type, language)


def _write_xlsx_deliverable(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    evidence: str,
    rows: List[List[str]],
    artifact_type: str = "",
    language: str = "en",
) -> Dict[str, str]:
    _write_xlsx(path, title, rows)
    return _deliverable_record(path, workflow_id, kind, title, "xlsx", evidence, artifact_type, language)


def _write_svg_deliverable(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    evidence: str,
    content: str,
    artifact_type: str = "",
    language: str = "en",
) -> Dict[str, str]:
    path.write_text(content, encoding="utf-8")
    return _deliverable_record(path, workflow_id, kind, title, "svg", evidence, artifact_type, language)


def _write_dxf_deliverable(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    evidence: str,
    content: str,
    artifact_type: str = "",
    language: str = "en",
) -> Dict[str, str]:
    path.write_text(content, encoding="ascii")
    return _deliverable_record(path, workflow_id, kind, title, "dxf", evidence, artifact_type, language)


def _final_export_result(
    export_dir: Path,
    workflow_id: str,
    profile_name: str,
    work_design: WorkDesign,
    deliverables: List[Dict[str, str]],
    evidence: List[str],
) -> Dict[str, Any]:
    traceability_rows = build_traceability_matrix_rows(work_design, deliverables)
    quality = evaluate_deliverable_quality({
        "profile": profile_name,
        "deliverables": deliverables,
        "traceability_rows": traceability_rows,
    })
    evidence.extend(quality.get("evidence", []))
    return {
        "export_dir": str(export_dir),
        "profile": profile_name,
        "plan": _plan_from_records(deliverables, profile_name),
        "deliverables": deliverables,
        "quality": quality,
        "internal_artifacts": {
            "traceability_matrix": {
                "storage": "metadata",
                "row_count": len(traceability_rows),
                "rows": traceability_rows,
            },
        },
        "evidence": _unique(evidence),
    }


def _write_docx(path: Path, title: str, sections: List[Dict[str, Any]]) -> None:
    document_xml = _docx_document_xml(title, sections)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", _docx_content_types())
        package.writestr("_rels/.rels", _docx_root_rels())
        package.writestr("docProps/core.xml", _core_props(title))
        package.writestr("docProps/app.xml", _app_props())
        package.writestr("word/document.xml", document_xml)


def _write_xlsx(path: Path, sheet_name: str, rows: List[List[str]]) -> None:
    sheet_xml = _xlsx_sheet_xml(rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", _xlsx_content_types())
        package.writestr("_rels/.rels", _xlsx_root_rels())
        package.writestr("docProps/core.xml", _core_props(sheet_name))
        package.writestr("docProps/app.xml", _app_props())
        package.writestr("xl/workbook.xml", _workbook_xml(sheet_name))
        package.writestr("xl/_rels/workbook.xml.rels", _workbook_rels())
        package.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def _docx_document_xml(title: str, sections: List[Dict[str, Any]]) -> str:
    body = [_docx_paragraph(title, bold=True)]
    for section in sections:
        heading = str(section.get("heading", "Section"))
        body.append(_docx_paragraph(heading, bold=True))
        for paragraph in section.get("paragraphs", []) or []:
            body.append(_docx_paragraph(str(paragraph)))
        for item in section.get("items", []) or []:
            body.append(_docx_paragraph(f"- {item}"))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body)}<w:sectPr/></w:body></w:document>"
    )


def _docx_paragraph(text: str, bold: bool = False) -> str:
    text_xml = escape(str(text))
    bold_xml = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:p><w:r>{bold_xml}<w:t xml:space=\"preserve\">{text_xml}</w:t></w:r></w:p>"


def _xlsx_sheet_xml(rows: List[List[str]]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            ref = f"{_column_name(col_index)}{row_index}"
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData></worksheet>'
    )


def _column_name(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _docx_content_types() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )


def _xlsx_content_types() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )


def _docx_root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _xlsx_root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _workbook_xml(sheet_name: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_name[:31])}" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )


def _workbook_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )


def _core_props(title: str) -> str:
    now = datetime.now(timezone.utc).isoformat()
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape(title)}</dc:title><dc:creator>KH UAF</dc:creator>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _app_props() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        "<Application>KH UAF</Application></Properties>"
    )


def _deliverable_record(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    file_format: str,
    evidence: str,
    artifact_type: str = "",
    language: str = "en",
) -> Dict[str, str]:
    return {
        "workflow_id": workflow_id,
        "kind": kind,
        "artifact_type": artifact_type or kind,
        "title": title,
        "format": file_format,
        "path": str(path),
        "evidence": evidence,
        "language": language,
    }


def _plan_from_records(deliverables: List[Dict[str, str]], profile_name: str) -> List[Dict[str, str]]:
    return [
        {
            "profile": profile_name,
            "kind": item.get("kind", ""),
            "artifact_type": item.get("artifact_type", item.get("kind", "")),
            "format": item.get("format", ""),
            "title": item.get("title", ""),
            "path": item.get("path", ""),
            "evidence": item.get("evidence", ""),
            "language": item.get("language", "en"),
        }
        for item in deliverables
    ]


def _first_heading(text: str) -> str:
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.strip("# ").strip()
    return ""


def _compact_text(text: str) -> str:
    compact = " ".join((text or "").split())
    return compact or "not specified"


def _product_name(design: WorkDesign, source_design_doc: str, file_list: List[str]) -> str:
    heading = _first_heading(source_design_doc)
    if heading:
        return heading
    if file_list:
        return Path(file_list[0]).stem
    return design.objective or "Product Concept"


def _extract_power_rating(text: str) -> str:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(kw|kW|KW|w|W)\b", text or "")
    return match.group(0) if match else "not specified"


def _product_spec_from_text(text: str) -> Dict[str, Any]:
    source = text or ""
    dim_match = re.search(r"(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)\s*(mm|MM|cm|CM|m|M)?", source)
    material_match = re.search(r"\b(SUS\d+|SS\d+|AL\d+|STEEL|ALUMINUM|PVC|ABS|SPCC|STS\d+)\b", source, re.IGNORECASE)
    hole_match = re.search(r"(?:(\d+|one|two|three|four|five|six|eight|ten|twelve)\s+)?(?:M\s*)?(\d{1,3})\s*(?:cable\s*)?(?:gland\s*)?holes?", source, re.IGNORECASE)
    hole_spec_match = re.search(r"\bM\s*(\d{1,3})\b", source, re.IGNORECASE)
    width = _number_from_match(dim_match, 1) if dim_match else None
    height = _number_from_match(dim_match, 2) if dim_match else None
    dimensions = f"{_format_number(width)}x{_format_number(height)}" if width and height else ""
    hole_count = _parse_count(hole_match.group(1)) if hole_match and hole_match.group(1) else None
    if hole_count is None and "four" in source.lower():
        hole_count = 4
    hole_spec = f"M{hole_spec_match.group(1)}" if hole_spec_match else ""
    return {
        "width": width,
        "height": height,
        "dimensions": dimensions,
        "material": material_match.group(1).upper() if material_match else "",
        "hole_count": hole_count,
        "hole_spec": hole_spec,
    }


def _number_from_match(match: Optional[re.Match], group: int) -> Optional[float]:
    if not match:
        return None
    try:
        return float(match.group(group))
    except (TypeError, ValueError):
        return None


def _format_number(value: Optional[float]) -> str:
    if value is None:
        return "0"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _parse_count(value: str) -> int:
    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "eight": 8,
        "ten": 10,
        "twelve": 12,
    }
    lowered = str(value or "").lower().strip()
    if lowered in words:
        return words[lowered]
    try:
        return int(float(lowered))
    except ValueError:
        return 4


def _ascii_dxf_text(text: str) -> str:
    return "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in text)


def _resolve_project_path(project_root: Path, relative_path: str) -> Path:
    candidate = (project_root / relative_path).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"deliverable export path escapes project root: {relative_path}") from exc
    return candidate


def _unique(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _has_any(text: str, markers: Iterable[str]) -> bool:
    for marker in markers:
        if " " in marker:
            if marker in text:
                return True
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", text):
            return True
    return False
