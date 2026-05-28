import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List
from xml.sax.saxutils import escape

from src.contracts import DomainProfile, DomainRole, WorkDesign


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
    export_dir = _resolve_project_path(project_root, metadata.get("deliverable_export_dir", "docs"))
    export_dir.mkdir(parents=True, exist_ok=True)
    files = [str(item) for item in (file_list or [])]
    source_title = _first_heading(source_design_doc) or work_design.objective
    profile_name = _deliverable_profile(domain_profile, work_design, files, metadata, source_design_doc)
    if profile_name == "product-design":
        return _export_product_design_deliverables(
            export_dir=export_dir,
            workflow_id=workflow_id,
            domain_profile=domain_profile,
            work_design=work_design,
            source_design_doc=source_design_doc,
            file_list=files,
            profile_name=profile_name,
        )
    if profile_name == "investment-analysis":
        return _export_investment_analysis_deliverables(
            export_dir=export_dir,
            workflow_id=workflow_id,
            domain_profile=domain_profile,
            work_design=work_design,
            source_design_doc=source_design_doc,
            file_list=files,
            profile_name=profile_name,
        )

    manual_required = _should_export_manual(domain_profile, work_design, files, metadata)
    evidence = list(DELIVERABLE_EVIDENCE)

    deliverables = [
        _write_docx_deliverable(
            export_dir / "요구정의서.docx",
            workflow_id,
            "requirements-brief",
            "요구정의서",
            "requirements brief exported",
            _requirements_sections(domain_profile, work_design, source_title, source_design_doc),
        ),
        _write_docx_deliverable(
            export_dir / "오케스트레이션_설계서.docx",
            workflow_id,
            "orchestration-design",
            "오케스트레이션 설계서",
            "orchestration design exported",
            _orchestration_sections(domain_profile, work_design),
        ),
        _write_docx_deliverable(
            export_dir / "산출물_정의서.docx",
            workflow_id,
            "deliverable-definition",
            "산출물 정의서",
            "deliverable definition exported",
            _deliverable_sections(work_design, files),
        ),
        _write_docx_deliverable(
            export_dir / "처리흐름도.docx",
            workflow_id,
            "process-flow",
            "처리흐름도",
            "process flow exported",
            _process_flow_sections(work_design),
        ),
        _write_xlsx_deliverable(
            export_dir / "역할별_작업분해표.xlsx",
            workflow_id,
            "role-task-breakdown",
            "역할별 작업분해표",
            "role task breakdown exported",
            _role_task_rows(domain_profile, work_design, files),
        ),
        _write_xlsx_deliverable(
            export_dir / "증거계획서.xlsx",
            workflow_id,
            "evidence-plan",
            "증거계획서",
            "evidence plan exported",
            _evidence_rows(work_design, evidence),
        ),
        _write_xlsx_deliverable(
            export_dir / "위험_정책_체크리스트.xlsx",
            workflow_id,
            "risk-policy-checklist",
            "위험 정책 체크리스트",
            "risk policy checklist exported",
            _risk_policy_rows(work_design),
        ),
    ]
    if manual_required:
        evidence.append("manual exported")
        deliverables.append(
            _write_docx_deliverable(
                export_dir / "사용_매뉴얼.docx",
                workflow_id,
                "user-manual",
                "사용 매뉴얼",
                "manual exported",
                _manual_sections(workflow_id, domain_profile, work_design, files, metadata),
            )
        )
    return {
        "export_dir": str(export_dir),
        "profile": profile_name,
        "plan": _plan_from_records(deliverables, profile_name),
        "deliverables": deliverables,
        "evidence": evidence,
    }


def _export_product_design_deliverables(
    export_dir: Path,
    workflow_id: str,
    domain_profile: DomainProfile,
    work_design: WorkDesign,
    source_design_doc: str,
    file_list: List[str],
    profile_name: str,
) -> Dict[str, Any]:
    product_name = _product_name(work_design, source_design_doc, file_list)
    evidence = [
        "product design document exported",
        "dimension bom exported",
        "technical drawing exported",
        "cad drawing exported",
    ]
    deliverables = [
        _write_docx_deliverable(
            export_dir / "제품_설계서.docx",
            workflow_id,
            "product-design-document",
            "제품 설계서",
            "product design document exported",
            _product_design_sections(domain_profile, work_design, source_design_doc, product_name),
            artifact_type="design-document",
        ),
        _write_xlsx_deliverable(
            export_dir / "치수_BOM.xlsx",
            workflow_id,
            "dimension-bom",
            "치수 BOM",
            "dimension bom exported",
            _dimension_bom_rows(work_design, source_design_doc, product_name),
            artifact_type="table-model",
        ),
        _write_svg_deliverable(
            export_dir / "개념_설계도.svg",
            workflow_id,
            "concept-drawing-svg",
            "개념 설계도",
            "technical drawing exported",
            _concept_svg(product_name, work_design),
            artifact_type="technical-drawing",
        ),
        _write_dxf_deliverable(
            export_dir / "개념_설계도.dxf",
            workflow_id,
            "concept-drawing-dxf",
            "개념 설계도 DXF",
            "cad drawing exported",
            _concept_dxf(product_name),
            artifact_type="cad-drawing",
        ),
    ]
    return {
        "export_dir": str(export_dir),
        "profile": profile_name,
        "plan": _plan_from_records(deliverables, profile_name),
        "deliverables": deliverables,
        "evidence": evidence,
    }


def _export_investment_analysis_deliverables(
    export_dir: Path,
    workflow_id: str,
    domain_profile: DomainProfile,
    work_design: WorkDesign,
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
            export_dir / "투자_분석보고서.docx",
            workflow_id,
            "investment-analysis-report",
            "투자 분석보고서",
            "investment analysis report exported",
            _investment_analysis_sections(domain_profile, work_design, source_design_doc),
            artifact_type="analysis-report",
        ),
        _write_xlsx_deliverable(
            export_dir / "가정_시나리오.xlsx",
            workflow_id,
            "scenario-model",
            "가정 시나리오",
            "scenario model exported",
            _scenario_model_rows(work_design, file_list),
            artifact_type="scenario-model",
        ),
        _write_xlsx_deliverable(
            export_dir / "위험_정책_체크리스트.xlsx",
            workflow_id,
            "risk-policy-checklist",
            "위험 정책 체크리스트",
            "risk policy checklist exported",
            _risk_policy_rows(work_design),
            artifact_type="risk-policy-checklist",
        ),
    ]
    return {
        "export_dir": str(export_dir),
        "profile": profile_name,
        "plan": _plan_from_records(deliverables, profile_name),
        "deliverables": deliverables,
        "evidence": evidence,
    }


def _requirements_sections(
    profile: DomainProfile,
    design: WorkDesign,
    source_title: str,
    source_design_doc: str,
) -> List[Dict[str, Any]]:
    return [
        {"heading": "요청 요약", "paragraphs": [source_title]},
        {"heading": "목표", "paragraphs": [design.objective or profile.objective]},
        {"heading": "도메인", "paragraphs": [profile.domain_name or design.domain or "generic"]},
        {"heading": "범위", "paragraphs": [design.scope or "not specified"]},
        {"heading": "필수 산출물", "items": design.deliverables},
        {"heading": "가정", "items": design.assumptions},
        {"heading": "제약", "items": design.constraints},
        {"heading": "원본 요청", "paragraphs": [_compact_text(source_design_doc)]},
    ]


def _orchestration_sections(profile: DomainProfile, design: WorkDesign) -> List[Dict[str, Any]]:
    return [
        {"heading": "오케스트레이션 목표", "paragraphs": [design.objective]},
        {"heading": "하위 도메인", "items": design.subdomains},
        {"heading": "필요 역할", "items": design.roles_required},
        {"heading": "설계 산출물", "items": design.design_artifacts},
        {"heading": "검토 게이트", "items": design.review_gates},
        {"heading": "위험 및 정책 게이트", "items": design.risk_policy_checks},
        {
            "heading": "역할 그래프",
            "items": [
                f"{role.name}: {role.purpose}"
                for role in profile.roles
            ],
        },
    ]


def _deliverable_sections(design: WorkDesign, file_list: List[str]) -> List[Dict[str, Any]]:
    return [
        {"heading": "사용자 산출물", "items": design.deliverables},
        {"heading": "작업 대상", "items": file_list or ["final output"]},
        {"heading": "증거 요구사항", "items": design.evidence_required},
        {
            "heading": "기본 export 파일",
            "items": [
                "요구정의서.docx",
                "오케스트레이션_설계서.docx",
                "산출물_정의서.docx",
                "처리흐름도.docx",
                "역할별_작업분해표.xlsx",
                "증거계획서.xlsx",
                "위험_정책_체크리스트.xlsx",
                "사용_매뉴얼.docx",
            ],
        },
    ]


def _process_flow_sections(design: WorkDesign) -> List[Dict[str, Any]]:
    return [
        {
            "heading": "기본 흐름",
            "items": [
                "목표 접수",
                "도메인 및 하위 도메인 식별",
                "역할과 책임 배정",
                "WorkDesign 작성",
                "사용자 산출물 export",
                "작업 실행",
                "검토 및 QA/QC",
                "위험/정책 점검",
                "완료 또는 차단 결정",
            ],
        },
        {"heading": "검토 게이트", "items": design.review_gates},
        {"heading": "차단 조건", "items": design.risk_policy_checks},
    ]


def _role_task_rows(
    profile: DomainProfile,
    design: WorkDesign,
    file_list: List[str],
) -> List[List[str]]:
    rows = [["역할", "단계", "목적", "필요 산출물", "생성물", "책임"]]
    roles = profile.roles or [
        DomainRole(name=name, purpose="Execute assigned orchestration responsibility.")
        for name in design.roles_required
    ]
    for role in roles:
        rows.append([
            role.name,
            role.stage,
            role.purpose,
            "; ".join(role.required_artifacts),
            "; ".join(role.produces),
            "; ".join(role.responsibilities),
        ])
    if file_list:
        rows.append([
            "implementer",
            "execution",
            "Produce requested target deliverables.",
            "work-design; role-task-plan",
            "; ".join(file_list),
            "execute assigned outputs; record evidence",
        ])
    return rows


def _evidence_rows(design: WorkDesign, export_evidence: List[str]) -> List[List[str]]:
    rows = [["증거 키", "출처", "상태", "비고"]]
    for item in _unique(list(design.evidence_required) + list(export_evidence)):
        rows.append([item, "workflow/design-stage", "planned", "required when goal evidence asks for it"])
    for item in design.review_gates:
        rows.append([item, "review-gate", "planned", "review gate output"])
    return rows


def _risk_policy_rows(design: WorkDesign) -> List[List[str]]:
    rows = [["체크 항목", "담당 역할", "상태", "차단 기준"]]
    for item in design.risk_policy_checks:
        rows.append([item, "risk-policy-reviewer", "planned", "missing or failed check blocks completion"])
    if len(rows) == 1:
        rows.append(["missing evidence checked", "risk-policy-reviewer", "planned", "required evidence is absent"])
    return rows


def _manual_sections(
    workflow_id: str,
    profile: DomainProfile,
    design: WorkDesign,
    file_list: List[str],
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    revision = str(metadata.get("manual_revision", "Rev. 1.0"))
    revision_note = str(metadata.get("manual_revision_note", "Initial generated manual."))
    return [
        {
            "heading": "리비전 버전 관리",
            "items": [
                f"Revision: {revision}",
                f"Workflow: {workflow_id}",
                f"Change: {revision_note}",
            ],
        },
        {"heading": "목적", "paragraphs": [design.objective or profile.objective]},
        {
            "heading": "운영 대상",
            "items": list(design.deliverables) or file_list or ["final output"],
        },
        {
            "heading": "사용 절차",
            "items": [
                "요구정의서에서 목표와 범위를 확인한다.",
                "오케스트레이션 설계서에서 역할, 흐름, 게이트를 확인한다.",
                "산출물 정의서에서 최종 결과물과 작업 대상을 확인한다.",
                "역할별 작업분해표에 따라 담당 작업을 수행한다.",
                "증거계획서와 위험 정책 체크리스트를 기준으로 완료 여부를 검증한다.",
            ],
        },
        {"heading": "검증 기준", "items": design.evidence_required},
        {"heading": "운영 중 차단 조건", "items": design.risk_policy_checks},
        {
            "heading": "인수 확인",
            "items": [
                "필수 산출물이 모두 존재한다.",
                "필수 증거가 goal evidence에 기록되어 있다.",
                "QA, 보안, release gate가 통과했거나 차단 사유가 명확하다.",
            ],
        },
    ]


def _product_design_sections(
    profile: DomainProfile,
    design: WorkDesign,
    source_design_doc: str,
    product_name: str,
) -> List[Dict[str, Any]]:
    return [
        {"heading": "제품/규격 식별", "paragraphs": [product_name]},
        {"heading": "설계 목표", "paragraphs": [design.objective or profile.objective]},
        {"heading": "적용 범위", "paragraphs": [design.scope or "not specified"]},
        {
            "heading": "도면 산출물",
            "items": [
                "제품_설계서.docx: 설계 기준과 가정",
                "치수_BOM.xlsx: 치수, 부품, 가공 데이터",
                "개념_설계도.svg: 검토용 개념 도면",
                "개념_설계도.dxf: CAD handoff용 2D 개념 도면",
            ],
        },
        {
            "heading": "주의",
            "items": [
                "입력 가이드에 정확한 치수, 공차, 재질이 없으면 제조용 최종 도면이 아니라 개념 도면으로 취급한다.",
                "제조 전에는 원 규격서, 실측 데이터, 승인 도면 번호를 확인해야 한다.",
            ],
        },
        {"heading": "원본 규격/요청", "paragraphs": [_compact_text(source_design_doc)]},
    ]


def _dimension_bom_rows(
    design: WorkDesign,
    source_design_doc: str,
    product_name: str,
) -> List[List[str]]:
    return [
        ["분류", "항목", "값", "근거", "비고"],
        ["제품", "식별명", product_name, "user input", ""],
        ["전기", "용량", _extract_power_rating(source_design_doc), "user input", "전기 용량은 기구 치수 확정 근거가 아님"],
        ["기구", "판넬/플레이트", "CABLE GLAND PLATE", "user input", "정확 치수는 규격 가이드 필요"],
        ["도면", "도면 수준", "concept", "UAF export", "제조용 최종 도면 전 검토 필요"],
        ["검증", "필요 증거", "; ".join(design.evidence_required), "work design", ""],
    ]


def _investment_analysis_sections(
    profile: DomainProfile,
    design: WorkDesign,
    source_design_doc: str,
) -> List[Dict[str, Any]]:
    return [
        {"heading": "분석 목적", "paragraphs": [design.objective or profile.objective]},
        {"heading": "분석 범위", "paragraphs": [design.scope or "not specified"]},
        {"heading": "핵심 산출물", "items": ["투자_분석보고서.docx", "가정_시나리오.xlsx", "위험_정책_체크리스트.xlsx"]},
        {"heading": "검토 기준", "items": design.evidence_required},
        {"heading": "위험 및 정책 체크", "items": design.risk_policy_checks},
        {"heading": "원본 요청", "paragraphs": [_compact_text(source_design_doc)]},
    ]


def _scenario_model_rows(design: WorkDesign, file_list: List[str]) -> List[List[str]]:
    return [
        ["분류", "항목", "기준/값", "비고"],
        ["시나리오", "Base", "to be filled from source data", "기본 가정"],
        ["시나리오", "Upside", "to be filled from source data", "긍정 가정"],
        ["시나리오", "Downside", "to be filled from source data", "보수 가정"],
        ["입력", "대상", "; ".join(file_list) or "investment thesis", ""],
        ["증거", "필수 증거", "; ".join(design.evidence_required), ""],
    ]


def _concept_svg(product_name: str, design: WorkDesign) -> str:
    title = escape(product_name)
    note = escape(design.scope or "Concept drawing; verify dimensions against supplied guide.")
    return (
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"900\" height=\"620\" viewBox=\"0 0 900 620\">"
        "<rect width=\"900\" height=\"620\" fill=\"#ffffff\"/>"
        "<text x=\"40\" y=\"50\" font-family=\"Arial\" font-size=\"26\" font-weight=\"700\">"
        f"{title}</text>"
        "<rect x=\"180\" y=\"140\" width=\"540\" height=\"300\" fill=\"none\" stroke=\"#111827\" stroke-width=\"4\"/>"
        "<circle cx=\"330\" cy=\"290\" r=\"42\" fill=\"none\" stroke=\"#2563eb\" stroke-width=\"4\"/>"
        "<circle cx=\"450\" cy=\"290\" r=\"42\" fill=\"none\" stroke=\"#2563eb\" stroke-width=\"4\"/>"
        "<circle cx=\"570\" cy=\"290\" r=\"42\" fill=\"none\" stroke=\"#2563eb\" stroke-width=\"4\"/>"
        "<line x1=\"180\" y1=\"470\" x2=\"720\" y2=\"470\" stroke=\"#374151\" stroke-width=\"2\"/>"
        "<text x=\"360\" y=\"505\" font-family=\"Arial\" font-size=\"18\">overall width TBD</text>"
        "<line x1=\"750\" y1=\"140\" x2=\"750\" y2=\"440\" stroke=\"#374151\" stroke-width=\"2\"/>"
        "<text x=\"770\" y=\"300\" font-family=\"Arial\" font-size=\"18\" transform=\"rotate(90 770 300)\">height TBD</text>"
        "<text x=\"40\" y=\"560\" font-family=\"Arial\" font-size=\"16\">"
        f"{note}</text>"
        "</svg>"
    )


def _concept_dxf(product_name: str) -> str:
    title = _ascii_dxf_text(product_name)
    return "\n".join([
        "0", "SECTION", "2", "ENTITIES",
        "0", "LWPOLYLINE", "8", "PLATE", "90", "4", "70", "1",
        "10", "0", "20", "0",
        "10", "540", "20", "0",
        "10", "540", "20", "300",
        "10", "0", "20", "300",
        "0", "CIRCLE", "8", "GLAND_HOLES", "10", "150", "20", "150", "40", "42",
        "0", "CIRCLE", "8", "GLAND_HOLES", "10", "270", "20", "150", "40", "42",
        "0", "CIRCLE", "8", "GLAND_HOLES", "10", "390", "20", "150", "40", "42",
        "0", "TEXT", "8", "NOTES", "10", "0", "20", "340", "40", "18", "1", title,
        "0", "TEXT", "8", "NOTES", "10", "0", "20", "365", "40", "12", "1",
        "CONCEPT ONLY - VERIFY DIMENSIONS AND TOLERANCES AGAINST SOURCE GUIDE",
        "0", "ENDSEC", "0", "EOF", "",
    ])


def _deliverable_profile(
    profile: DomainProfile,
    design: WorkDesign,
    file_list: List[str],
    metadata: Dict[str, Any],
    source_design_doc: str,
) -> str:
    explicit = str(metadata.get("deliverable_profile", "") or metadata.get("artifact_profile", "")).strip().lower()
    if explicit:
        return explicit.replace("_", "-")
    haystack = " ".join([
        profile.domain_name,
        design.domain,
        design.scope,
        " ".join(design.deliverables),
        " ".join(file_list),
        source_design_doc,
    ]).lower()
    product_markers = [
        "product",
        "mechanical",
        "cad",
        "dxf",
        "drawing",
        "gland plate",
        "cable gland",
        "specification guide",
        "제품",
        "기구",
        "도면",
        "설계도",
        "규격",
    ]
    if any(marker in haystack for marker in product_markers):
        return "product-design"
    investment_markers = [
        "investment",
        "finance",
        "valuation",
        "portfolio",
        "research",
        "analysis",
        "투자",
        "분석",
        "리서치",
    ]
    if any(marker in haystack for marker in investment_markers):
        return "investment-analysis"
    return "general-orchestration"


def _should_export_manual(
    profile: DomainProfile,
    design: WorkDesign,
    file_list: List[str],
    metadata: Dict[str, Any],
) -> bool:
    if "export_manual" in metadata:
        return bool(metadata.get("export_manual"))
    if metadata.get("manual_revision") or metadata.get("manual_revision_note"):
        return True

    haystack = " ".join([
        profile.domain_name,
        design.domain,
        design.scope,
        " ".join(design.deliverables),
        " ".join(file_list),
    ]).lower()
    skip_markers = [
        "investment",
        "finance",
        "valuation",
        "portfolio",
        "research",
        "analysis",
        "리서치",
        "분석",
        "투자",
    ]
    if any(marker in haystack for marker in skip_markers):
        return False

    include_markers = [
        "operation",
        "ops",
        "workflow",
        "handoff",
        "runbook",
        "system",
        "service",
        "training",
        "onboarding",
        "process",
        "운영",
        "인수인계",
        "절차",
        "프로세스",
        "시스템",
        "서비스",
    ]
    return any(marker in haystack for marker in include_markers)


def _write_docx_deliverable(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    evidence: str,
    sections: List[Dict[str, Any]],
    artifact_type: str = "",
) -> Dict[str, str]:
    _write_docx(path, title, sections)
    return _deliverable_record(path, workflow_id, kind, title, "docx", evidence, artifact_type)


def _write_xlsx_deliverable(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    evidence: str,
    rows: List[List[str]],
    artifact_type: str = "",
) -> Dict[str, str]:
    _write_xlsx(path, title, rows)
    return _deliverable_record(path, workflow_id, kind, title, "xlsx", evidence, artifact_type)


def _write_svg_deliverable(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    evidence: str,
    content: str,
    artifact_type: str = "",
) -> Dict[str, str]:
    path.write_text(content, encoding="utf-8")
    return _deliverable_record(path, workflow_id, kind, title, "svg", evidence, artifact_type)


def _write_dxf_deliverable(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    evidence: str,
    content: str,
    artifact_type: str = "",
) -> Dict[str, str]:
    path.write_text(content, encoding="ascii")
    return _deliverable_record(path, workflow_id, kind, title, "dxf", evidence, artifact_type)


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
    body: List[str] = [_docx_paragraph(title, bold=True)]
    for section in sections:
        heading = section.get("heading", "")
        if heading:
            body.append(_docx_paragraph(heading, bold=True))
        for paragraph in section.get("paragraphs", []) or []:
            body.append(_docx_paragraph(str(paragraph)))
        for item in section.get("items", []) or []:
            body.append(_docx_paragraph(f"- {item}"))
    body.append(
        "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        "<w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\""
        " w:header=\"720\" w:footer=\"720\" w:gutter=\"0\"/></w:sectPr>"
    )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{''.join(body)}</w:body></w:document>"
    )


def _docx_paragraph(text: str, bold: bool = False) -> str:
    run_props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:p><w:r>{run_props}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"


def _xlsx_sheet_xml(rows: List[List[str]]) -> str:
    row_xml = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_column_name(column_index)}{row_index}"
            cells.append(
                f"<c r=\"{cell_ref}\" t=\"inlineStr\"><is><t>{escape(str(value))}</t></is></c>"
            )
        row_xml.append(f"<row r=\"{row_index}\">{''.join(cells)}</row>")
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
        f"<sheetData>{''.join(row_xml)}</sheetData></worksheet>"
    )


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _docx_content_types() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>"
        "<Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>"
        "<Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>"
        "</Types>"
    )


def _xlsx_content_types() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        "<Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>"
        "<Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>"
        "<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
        "<Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
        "</Types>"
    )


def _docx_root_rels() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>"
        "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>"
        "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>"
        "</Relationships>"
    )


def _xlsx_root_rels() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>"
        "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>"
        "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>"
        "</Relationships>"
    )


def _workbook_xml(sheet_name: str) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">"
        f"<sheets><sheet name=\"{escape(sheet_name[:31])}\" sheetId=\"1\" r:id=\"rId1\"/></sheets>"
        "</workbook>"
    )


def _workbook_rels() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>"
        "</Relationships>"
    )


def _core_props(title: str) -> str:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" "
        "xmlns:dc=\"http://purl.org/dc/elements/1.1/\" "
        "xmlns:dcterms=\"http://purl.org/dc/terms/\" "
        "xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" "
        "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
        f"<dc:title>{escape(title)}</dc:title>"
        "<dc:creator>KH UAF</dc:creator>"
        f"<dcterms:created xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:created>"
        f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{now}</dcterms:modified>"
        "</cp:coreProperties>"
    )


def _app_props() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" "
        "xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">"
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
) -> Dict[str, str]:
    return {
        "workflow_id": workflow_id,
        "kind": kind,
        "artifact_type": artifact_type or kind,
        "title": title,
        "format": file_format,
        "path": str(path),
        "evidence": evidence,
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


def _product_name(
    design: WorkDesign,
    source_design_doc: str,
    file_list: List[str],
) -> str:
    if file_list:
        return file_list[0]
    return _first_heading(source_design_doc) or design.objective or "Product Design"


def _extract_power_rating(text: str) -> str:
    import re

    match = re.search(r"\b\d+(?:\.\d+)?\s*kW\b", text or "", flags=re.IGNORECASE)
    return match.group(0) if match else "not specified"


def _ascii_dxf_text(text: str) -> str:
    value = text.encode("ascii", errors="ignore").decode("ascii").strip()
    return value or "CONCEPT DRAWING"


def _resolve_project_path(project_root: Path, relative_path: str) -> Path:
    raw_path = Path(str(relative_path or "docs"))
    candidate = raw_path if raw_path.is_absolute() else project_root / raw_path
    resolved = candidate.resolve()
    try:
        common_root = os.path.commonpath([str(project_root), str(resolved)])
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {relative_path}") from exc
    if common_root != str(project_root):
        raise ValueError(f"path escapes project root: {relative_path}")
    return resolved


def _unique(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    for item in items:
        value = str(item).strip()
        if value and value not in result:
            result.append(value)
    return result
