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
            _evidence_rows(work_design),
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
    return {
        "export_dir": str(export_dir),
        "deliverables": deliverables,
        "evidence": list(DELIVERABLE_EVIDENCE),
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


def _evidence_rows(design: WorkDesign) -> List[List[str]]:
    rows = [["증거 키", "출처", "상태", "비고"]]
    for item in _unique(list(design.evidence_required) + list(DELIVERABLE_EVIDENCE)):
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


def _write_docx_deliverable(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    evidence: str,
    sections: List[Dict[str, Any]],
) -> Dict[str, str]:
    _write_docx(path, title, sections)
    return _deliverable_record(path, workflow_id, kind, title, "docx", evidence)


def _write_xlsx_deliverable(
    path: Path,
    workflow_id: str,
    kind: str,
    title: str,
    evidence: str,
    rows: List[List[str]],
) -> Dict[str, str]:
    _write_xlsx(path, title, rows)
    return _deliverable_record(path, workflow_id, kind, title, "xlsx", evidence)


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
) -> Dict[str, str]:
    return {
        "workflow_id": workflow_id,
        "kind": kind,
        "title": title,
        "format": file_format,
        "path": str(path),
        "evidence": evidence,
    }


def _first_heading(text: str) -> str:
    for line in (text or "").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped.strip("# ").strip()
    return ""


def _compact_text(text: str) -> str:
    compact = " ".join((text or "").split())
    return compact or "not specified"


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
